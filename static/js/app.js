let currentTaskId = null;
let websocket = null;
let pollingInterval = null;

const perPage = 10;
let exportColumns = [];
let taskExportColumns = [];
let columnMultiselectReady = false;

document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('parse-form').addEventListener('submit', handleFormSubmit);
    document.getElementById('cancel-btn').addEventListener('click', cancelTask);
    document.getElementById('download-btn').addEventListener('click', downloadCsv);
    document.getElementById('new-search-btn').addEventListener('click', newSearch);
    initColumnMultiselect();
    loadExportColumns();
});

async function handleFormSubmit(event) {
    event.preventDefault();

    const url = normalize2gisUrl(document.getElementById('gis-url').value);
    const maxPages = Number(document.getElementById('max-pages').value || 50);
    const maxFilials = Number(document.getElementById('max-filials').value || 100);
    const workers = 1;

    if (!is2gisUrl(url)) {
        showError('Вставьте корректную ссылку 2ГИС.');
        return;
    }

    const columns = getSelectedExportColumns();
    if (!columns.length) {
        showError('Выберите хотя бы одно поле для сбора данных.');
        return;
    }

    const submitBtn = document.getElementById('submit-btn');
    submitBtn.disabled = true;
    submitBtn.querySelector('span').textContent = 'Запуск';
    setStatus('В работе', true);
    hideError();

    try {
        const response = await fetch('/api/v1/parse-url', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                url,
                max_pages: maxPages,
                max_filials: maxFilials,
                workers,
                columns,
            }),
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Не удалось запустить парсер.');
        }

        const data = await response.json();
        currentTaskId = data.task_id;
        showProgressSection();
        connectWebSocket(currentTaskId);
        startPolling(currentTaskId);
    } catch (error) {
        showError(error.message);
        resetSubmitButton();
        setStatus('Готов', false);
    }
}

function is2gisUrl(url) {
    try {
        const parsed = new URL(url);
        return /(^|\.)2gis\.(ru|kz|com)$/i.test(parsed.hostname)
            || /^(go|link)\.2gis\.com$/i.test(parsed.hostname);
    } catch {
        return false;
    }
}

function normalize2gisUrl(value) {
    const text = String(value || '').trim();
    const match = text.match(/https?:\/\/[^\s<>"']+/i);
    return (match ? match[0] : text).replace(/[),.;]+$/g, '');
}

function showProgressSection() {
    document.getElementById('search-section').classList.add('hidden');
    document.getElementById('progress-section').classList.remove('hidden');
    document.getElementById('results-section').classList.add('hidden');
}

function connectWebSocket(taskId) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    websocket = new WebSocket(`${protocol}//${window.location.host}/ws/tasks/${taskId}`);

    websocket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        updateProgress(data);
        handleTerminalStatus(data);
    };

    websocket.onerror = () => {
        websocket = null;
    };
}

function startPolling(taskId) {
    stopPolling(false);
    pollingInterval = setInterval(async () => {
        try {
            const response = await fetch(`/api/v1/tasks/${taskId}`);
            if (!response.ok) return;
            const data = await response.json();
            updateProgress(data);
            handleTerminalStatus(data);
        } catch {
            // WebSocket usually covers transient polling failures.
        }
    }, 1500);
}

function handleTerminalStatus(data) {
    if (data.status === 'completed') {
        stopPolling();
        setStatus('Готово', false);
        loadResults(currentTaskId);
    } else if (data.status === 'failed') {
        stopPolling();
        setStatus('Ошибка', false);
        showError((data.errors && data.errors[0]) || data.message || 'Парсер завершился с ошибкой.');
        resetSubmitButton();
    } else if (data.status === 'cancelled') {
        stopPolling();
        setStatus('Отменено', false);
        showError('Парсинг отменен.');
        resetSubmitButton();
    }
}

function stopPolling(closeSocket = true) {
    if (pollingInterval) {
        clearInterval(pollingInterval);
        pollingInterval = null;
    }
    if (closeSocket && websocket) {
        websocket.close();
        websocket = null;
    }
}

function updateProgress(data) {
    const progress = data.progress || 0;
    document.getElementById('progress-bar').style.width = `${progress}%`;
    document.getElementById('progress-percent').textContent = `${progress}%`;
    document.getElementById('current-city').textContent = decodeMojibake(data.current_city) || '-';
    document.getElementById('page-progress').textContent = `${data.current_page || 0} / ${data.total_pages || 0}`;
    document.getElementById('firms-progress').textContent = `${data.firms_processed || 0} / ${data.firms_total || 0}`;
    document.getElementById('progress-message').textContent = decodeMojibake(data.message) || 'Идет обработка...';
}

async function cancelTask() {
    if (!currentTaskId) return;

    try {
        await fetch(`/api/v1/tasks/${currentTaskId}`, {method: 'DELETE'});
        stopPolling();
        setStatus('Отменено', false);
        newSearch();
    } catch (error) {
        showError(`Не удалось отменить задачу: ${error.message}`);
    }
}

async function loadResults(taskId) {
    try {
        const response = await fetch(`/api/v1/tasks/${taskId}/results?page=1&per_page=${perPage}`);
        if (!response.ok) throw new Error('Не удалось загрузить результаты.');

        const data = await response.json();
        document.getElementById('progress-section').classList.add('hidden');
        document.getElementById('results-section').classList.remove('hidden');
        document.getElementById('results-count').textContent =
            `${data.total_count} ${pluralRu(data.total_count, 'филиал', 'филиала', 'филиалов')}`;

        taskExportColumns = data.export_columns || [];
        renderTable(data.firms, taskExportColumns);
        renderPreviewNotice(data.total_count, data.firms.length);
        updateExportSummary();
        resetSubmitButton();
    } catch (error) {
        showError(error.message);
    }
}

async function loadExportColumns() {
    try {
        const response = await fetch('/api/v1/export/columns');
        if (!response.ok) return;
        const data = await response.json();
        exportColumns = data.columns || [];
        renderColumnOptions(exportColumns);
    } catch {
        // Columns will stay empty until API is available.
    }
}

function initColumnMultiselect() {
    if (columnMultiselectReady) return;
    columnMultiselectReady = true;

    const root = document.getElementById('column-multiselect');
    const trigger = document.getElementById('column-multiselect-trigger');
    const panel = document.getElementById('column-multiselect-panel');

    trigger.addEventListener('click', (event) => {
        event.stopPropagation();
        const open = root.classList.toggle('open');
        panel.classList.toggle('hidden', !open);
        trigger.setAttribute('aria-expanded', open ? 'true' : 'false');
    });

    document.getElementById('columns-select-all').addEventListener('click', () => {
        setAllColumnChecks(true);
    });
    document.getElementById('columns-select-none').addEventListener('click', () => {
        setAllColumnChecks(false);
    });

    document.addEventListener('click', (event) => {
        if (!root.contains(event.target)) {
            closeColumnMultiselect();
        }
    });

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') {
            closeColumnMultiselect();
        }
    });
}

function closeColumnMultiselect() {
    const root = document.getElementById('column-multiselect');
    const panel = document.getElementById('column-multiselect-panel');
    const trigger = document.getElementById('column-multiselect-trigger');
    root.classList.remove('open');
    panel.classList.add('hidden');
    trigger.setAttribute('aria-expanded', 'false');
}

function renderColumnOptions(columns) {
    const container = document.getElementById('column-options');
    container.innerHTML = '';

    for (const name of columns) {
        const label = document.createElement('label');
        label.className = 'multiselect-option';

        const input = document.createElement('input');
        input.type = 'checkbox';
        input.value = name;
        input.checked = true;
        input.addEventListener('change', updateColumnMultiselectLabel);

        const text = document.createElement('span');
        text.textContent = decodeMojibake(name);

        label.appendChild(input);
        label.appendChild(text);
        container.appendChild(label);
    }

    updateColumnMultiselectLabel();
}

function setAllColumnChecks(checked) {
    document
        .querySelectorAll('#column-options input[type="checkbox"]')
        .forEach((input) => {
            input.checked = checked;
        });
    updateColumnMultiselectLabel();
}

function getSelectedExportColumns() {
    return Array.from(
        document.querySelectorAll('#column-options input[type="checkbox"]:checked')
    ).map((input) => input.value);
}

function updateColumnMultiselectLabel() {
    const label = document.getElementById('column-multiselect-label');
    const total = exportColumns.length
        || document.querySelectorAll('#column-options input[type="checkbox"]').length;
    const selected = getSelectedExportColumns().length;

    if (!total) {
        label.textContent = 'Колонки';
    } else if (selected === 0) {
        label.textContent = 'Ничего не выбрано';
    } else if (selected === total) {
        label.textContent = `Все колонки (${total})`;
    } else {
        label.textContent = `Выбрано: ${selected} из ${total}`;
    }
}

function renderTable(firms, columns = []) {
    const visibleColumns = columns.length ? columns : exportColumns;
    const headerRow = document.querySelector('.table-wrap thead tr');
    const tbody = document.getElementById('results-tbody');

    headerRow.innerHTML = visibleColumns
        .map((column) => `<th>${escapeHtml(decodeMojibake(column))}</th>`)
        .join('');
    tbody.innerHTML = '';

    if (!firms.length) {
        tbody.innerHTML = `<tr><td colspan="${Math.max(visibleColumns.length, 1)}" class="empty">Филиалы не найдены.</td></tr>`;
        return;
    }

    for (const firm of firms) {
        const row = document.createElement('tr');
        row.innerHTML = visibleColumns
            .map((column) => `<td>${renderPreviewCell(column, firm)}</td>`)
            .join('');
        tbody.appendChild(row);
    }
}

function renderPreviewCell(column, firm) {
    const key = decodeMojibake(column);
    const social = firm.social || {};
    const valueByColumn = {
        'Название': firm.name,
        'Оценка': firm.rating,
        'Город': firm.city,
        'Адрес': firm.address,
        'Расписание': firm.schedule,
        'Телефоны': firm.phones,
        'Почта': firm.email,
        'Сайт': firm.website,
        'Whatsapp номер 1': (firm.whatsapp_numbers || [])[0],
        'Whatsapp номер 2': (firm.whatsapp_numbers || [])[1],
        'Whatsapp ссылка': social.whatsapp,
        'Telegram ссылка': social.telegram,
        'Telegram ник': firm.telegram_username,
        'Instagram': social.instagram,
        'Youtube': social.youtube,
        'VK': social.vk,
        'OK': social.ok,
        'Другие соцсети': firm.other_social,
        'Информация': firm.info,
        'URL': firm.source_url,
    };
    const value = valueByColumn[key];

    if (['Сайт', 'Whatsapp ссылка', 'Telegram ссылка', 'Instagram', 'Youtube', 'VK', 'OK', 'URL'].includes(key)) {
        return renderLink(value);
    }
    if (key === 'Телефоны') {
        return escapeHtml(formatPreviewValue(value).replace(/[-‐‑‒–—―]+/g, ''));
    }
    return escapeHtml(formatPreviewValue(value));
}

function formatPreviewValue(value) {
    if (Array.isArray(value)) {
        return value.filter(Boolean).join(', ') || '-';
    }
    return value || '-';
}

function renderLink(value) {
    if (!value) return '-';
    return `<a href="${escapeAttr(value)}" target="_blank" rel="noreferrer">${escapeHtml(shortUrl(value))}</a>`;
}

function renderPreviewNotice(totalCount, visibleCount) {
    const pagination = document.getElementById('pagination');
    pagination.innerHTML = totalCount
        ? `Предпросмотр: ${visibleCount} из ${totalCount}. CSV содержит все найденные филиалы.`
        : '';
}

function updateExportSummary() {
    const el = document.getElementById('export-summary');
    if (!el) return;
    const count = taskExportColumns.length;
    el.textContent = count ? `В CSV: ${count} ${pluralRu(count, 'поле', 'поля', 'полей')}` : '';
}

async function downloadCsv() {
    if (!currentTaskId) return;

    closeColumnMultiselect();

    const url = `/api/v1/tasks/${currentTaskId}/download`;
    const downloadBtn = document.getElementById('download-btn');
    downloadBtn.disabled = true;

    try {
        const response = await fetch(url);
        if (!response.ok) {
            let detail = 'Не удалось скачать CSV.';
            try {
                const error = await response.json();
                detail = error.detail || detail;
            } catch {
                // ignore
            }
            throw new Error(detail);
        }

        const blob = await response.blob();
        const objectUrl = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = objectUrl;
        link.download = `2gis_export_${currentTaskId}.csv`;
        document.body.appendChild(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(objectUrl);
    } catch (error) {
        showError(error.message);
    } finally {
        downloadBtn.disabled = false;
    }
}

function newSearch() {
    currentTaskId = null;
    taskExportColumns = [];
    closeColumnMultiselect();
    stopPolling();
    document.getElementById('parse-form').reset();
    document.getElementById('max-pages').value = 50;
    document.getElementById('max-filials').value = 100;
    document.getElementById('workers').value = 1;
    document.getElementById('search-section').classList.remove('hidden');
    document.getElementById('progress-section').classList.add('hidden');
    document.getElementById('results-section').classList.add('hidden');
    resetSubmitButton();
    setStatus('Готов', false);
    hideError();
}

function resetSubmitButton() {
    const submitBtn = document.getElementById('submit-btn');
    submitBtn.disabled = false;
    submitBtn.querySelector('span').textContent = 'Начать';
}

function setStatus(text, active) {
    const status = document.getElementById('app-status');
    status.lastChild.textContent = ` ${decodeMojibake(text)}`;
    status.classList.toggle('active', active);
}

function showError(message) {
    document.getElementById('error-message').textContent = decodeMojibake(message);
    document.getElementById('error-alert').classList.remove('hidden');
}

function hideError() {
    document.getElementById('error-alert').classList.add('hidden');
}

function shortUrl(url) {
    try {
        const parsed = new URL(url);
        return parsed.hostname.replace(/^www\./, '');
    } catch {
        return url;
    }
}

function pluralRu(count, one, few, many) {
    const n = Math.abs(Number(count)) % 100;
    const n1 = n % 10;
    if (n > 10 && n < 20) return many;
    if (n1 > 1 && n1 < 5) return few;
    if (n1 === 1) return one;
    return many;
}

function decodeMojibake(value) {
    const text = String(value || '');
    if (!/[РСЃЋЌЊЏЂВ]/.test(text)) return text;

    const cp1251Extra = {
        0x0402: 0x80, 0x0403: 0x81, 0x201A: 0x82, 0x0453: 0x83,
        0x201E: 0x84, 0x2026: 0x85, 0x2020: 0x86, 0x2021: 0x87,
        0x20AC: 0x88, 0x2030: 0x89, 0x0409: 0x8A, 0x2039: 0x8B,
        0x040A: 0x8C, 0x040C: 0x8D, 0x040B: 0x8E, 0x040F: 0x8F,
        0x0452: 0x90, 0x2018: 0x91, 0x2019: 0x92, 0x201C: 0x93,
        0x201D: 0x94, 0x2022: 0x95, 0x2013: 0x96, 0x2014: 0x97,
        0x2122: 0x99, 0x0459: 0x9A, 0x203A: 0x9B, 0x045A: 0x9C,
        0x045C: 0x9D, 0x045B: 0x9E, 0x045F: 0x9F, 0x040E: 0xA1,
        0x045E: 0xA2, 0x0408: 0xA3, 0x0490: 0xA5, 0x0401: 0xA8,
        0x0404: 0xAA, 0x0407: 0xAF, 0x0451: 0xB8, 0x0454: 0xBA,
        0x0458: 0xBC, 0x0405: 0xBD, 0x0455: 0xBE, 0x0457: 0xBF,
    };
    const bytes = [];
    for (const ch of text) {
        const code = ch.charCodeAt(0);
        if (code >= 0x0410 && code <= 0x044F) {
            bytes.push(code - 0x0350);
        } else if (cp1251Extra[code] !== undefined) {
            bytes.push(cp1251Extra[code]);
        } else if (code <= 0xFF) {
            bytes.push(code);
        } else {
            return text;
        }
    }

    try {
        const decoded = new TextDecoder('utf-8', {fatal: true}).decode(new Uint8Array(bytes));
        return decoded || text;
    } catch {
        return text;
    }
}

function escapeHtml(value) {
    const div = document.createElement('div');
    div.textContent = value || '';
    return div.innerHTML;
}

function escapeAttr(value) {
    return String(value || '').replace(/"/g, '&quot;');
}
