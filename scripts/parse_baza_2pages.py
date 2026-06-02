# -*- coding: utf-8 -*-
"""
Тестовый парсер баз отдыха: 2 страницы результатов поиска.

Запуск из корня проекта:
    python scripts/parse_baza_2pages.py

Опции:
    --max-firms N   ограничить число карточек организаций (для быстрой проверки)
"""

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Быстрый режим по умолчанию
os.environ.setdefault("HEADLESS", "true")

from app.config import settings
from app.services.parser import SearchUrlParser
from app.services.export import csv_exporter, EXPORT_HEADERS
from app.services.scrape_fields import ScrapeFields
from app.utils.progress_log import ParseProgressLog

SEARCH_URLS = [
    "https://2gis.kz/almaty/search/%D0%B1%D0%B0%D0%B7%D0%B0%20%D0%BE%D1%82%D0%B4%D1%8B%D1%85%D0%B0?m=81.598325%2C45.946169%2F12.94",
    "https://2gis.kz/almaty/search/%D0%B1%D0%B0%D0%B7%D0%B0%20%D0%BE%D1%82%D0%B4%D1%8B%D1%85%D0%B0?m=81.676235%2C45.85915%2F14.06",
    "https://2gis.kz/semey/search/%D0%B1%D0%B0%D0%B7%D0%B0%20%D0%BE%D1%82%D0%B4%D1%8B%D1%85%D0%B0?m=82.054756%2C46.072574%2F13.6",
]


def _safe_console(text: str) -> str:
    """Безопасный вывод для Windows cp1251-консоли."""
    if text is None:
        return ""
    return str(text).replace("‒", "-").replace("—", "-")


def main() -> None:
    parser = argparse.ArgumentParser(description="Парсер баз отдыха 2GIS")
    parser.add_argument(
        "--max-firms",
        type=int,
        default=None,
        help="Ограничить число организаций (по умолчанию — все с 2 страниц)",
    )
    parser.add_argument(
        "--url-index",
        type=int,
        default=0,
        choices=range(len(SEARCH_URLS)),
        help="Какую из трёх ссылок использовать (0=Алматы1, 1=Алматы2, 2=Семей)",
    )
    parser.add_argument(
        "--all-urls",
        action="store_true",
        default=True,
        help="Запустить парсинг сразу по всем 3 ссылкам",
    )
    parser.add_argument(
        "--single-url",
        action="store_true",
        help="Parse only one URL selected by --url-index",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=50,
        help="Лимит страниц на каждую ссылку (по умолчанию 50)",
    )
    parser.add_argument(
        "--show-browser",
        action="store_true",
        help="Показать окно Chrome (по умолчанию headless для скорости)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=settings.PARSER_WORKERS,
        help="Количество параллельных воркеров для карточек",
    )
    parser.add_argument(
        "--columns",
        nargs="+",
        default=None,
        metavar="COL",
        help=(
            "Какие поля собирать (названия колонок CSV). "
            f"Пример: --columns Название Адрес Телефоны. "
            f"По умолчанию — все ({len(EXPORT_HEADERS)} полей)."
        ),
    )
    args = parser.parse_args()

    settings.HEADLESS = not args.show_browser
    settings.PARSER_WORKERS = max(1, args.workers)
    if args.show_browser:
        os.environ["HEADLESS"] = "false"

    selected_urls = [SEARCH_URLS[args.url_index]] if args.single_url else SEARCH_URLS
    max_pages = max(1, args.max_pages)
    progress = ParseProgressLog()
    progress.step("Старт парсера баз отдыха")
    if args.show_browser:
        progress.detail("Режим: видимый Chrome (окно откроется на экране)")
    else:
        progress.detail("Режим: headless (быстрее)")
    progress.detail(f"Воркеров: {settings.PARSER_WORKERS}")
    progress.detail(f"Ссылок в запуске: {len(selected_urls)}")
    if not args.single_url:
        for idx, url in enumerate(selected_urls, 1):
            progress.detail(f"[{idx}] {url}")
    else:
        progress.detail(f"Поиск: {selected_urls[0]}")
    progress.detail(f"Лимит страниц на ссылку: {max_pages}")

    scrape_fields = ScrapeFields(args.columns)
    progress.detail(f"Поля для сбора: {', '.join(scrape_fields.columns)}")

    scraper = SearchUrlParser(
        max_pages=max_pages,
        max_firms=args.max_firms,
        progress=progress,
        headless=settings.HEADLESS,
        workers=settings.PARSER_WORKERS,
        scrape_fields=scrape_fields,
    )
    firms, firm_urls = scraper.parse(selected_urls)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    task_id = f"baza_{stamp}"

    progress.step("Сохраняю результаты в CSV…")
    urls_csv = csv_exporter.export_urls(task_id, firm_urls)
    data_csv = (
        csv_exporter.export_to_file(
            task_id, firms, columns=scrape_fields.columns
        )
        if firms
        else ""
    )
    progress.done("Файлы сохранены")

    print(f"\nСсылок на организации (до {max_pages} стр. на каждую ссылку): {len(firm_urls)}")
    print(f"Ссылки CSV: {urls_csv}")
    print(f"Собрано карточек: {len(firms)}")
    if data_csv:
        print(f"Данные CSV: {data_csv}")
    for i, firm in enumerate(firms[:5], 1):
        phones = ", ".join(firm.phones) if firm.phones else "-"
        print(f"\n--- {i} ---")
        print(f"  Название: {_safe_console(firm.name or '-')}")
        print(f"  Оценка: {_safe_console(firm.rating or '-')}")
        print(f"  Адрес: {_safe_console(firm.address or '-')}")
        print(f"  Телефоны: {_safe_console(phones)}")
        wa_nums = ", ".join(firm.whatsapp_numbers) if firm.whatsapp_numbers else "-"
        print(f"  Instagram: {_safe_console(firm.social.instagram or '-')}")
        print(f"  WhatsApp ссылка: {_safe_console(firm.social.whatsapp or '-')}")
        print(f"  WhatsApp номера: {_safe_console(wa_nums)}")
        print(f"  Telegram: {_safe_console(firm.social.telegram or '-')}")
        if firm.telegram_username:
            print(f"  Telegram ник: {_safe_console(firm.telegram_username)}")
        print(f"  URL: {_safe_console(firm.source_url)}")


if __name__ == "__main__":
    main()
