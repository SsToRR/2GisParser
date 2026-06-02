# -*- coding: utf-8 -*-
"""API endpoints."""

import asyncio
import os
from fastapi import APIRouter, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect, Query, Request
from typing import List, Optional

from fastapi.responses import HTMLResponse

from app.models.schemas import (
    ParseUrlRequestSchema, ParseResponseSchema,
    TaskStatusSchema, ResultsSchema, FirmSchema, SocialLinksSchema,
    ExportColumnsSchema,
)
from app.models.domain import ParseRequest, ParseProgress, TaskStatus
from app.core.exceptions import TaskNotFoundError, InvalidRequestError
from app.services.task_manager import task_manager
from app.services.parser import Parser2GIS
from app.services.export import (
    exporter, EXPORT_HEADERS, normalize_export_columns,
)
from app.api.dependencies import get_task_or_404
from app.utils.resources import resource_path



router = APIRouter()


def _city_from_address(address: str) -> str:
    parts = [part.strip() for part in (address or '').split(',')]
    return parts[1] if len(parts) > 1 else ""




def run_url_parser_task(
    task_id: str,
    url: str,
    max_pages: int,
    max_filials: int,
    workers: int,
    export_columns: List[str],
):
    """Run direct 2GIS URL parsing in background."""
    from app.services.scrape_fields import ScrapeFields

    def progress_callback(progress: ParseProgress):
        task_manager.update_progress(task_id, progress)

    scrape_fields = ScrapeFields(export_columns)
    parser = Parser2GIS(
        progress_callback=progress_callback,
        scrape_fields=scrape_fields,
    )
    task_manager.set_parser(task_id, parser)

    result = parser.parse_url(
        url,
        max_pages=max_pages,
        max_filials=max_filials,
        workers=workers,
        export_columns=scrape_fields.columns,
    )
    result.task_id = task_id

    if result.firms:
        result.excel_path = exporter.export_to_file(
            task_id,
            result.firms,
            columns=scrape_fields.columns,
        )

    task_manager.set_result(task_id, result)


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Р“Р»Р°РІРЅР°СЏ СЃС‚СЂР°РЅРёС†Р°."""
    from fastapi.templating import Jinja2Templates
    templates = Jinja2Templates(directory=str(resource_path("templates")))
    return templates.TemplateResponse("index.html", {"request": request})




@router.post("/api/v1/parse-url", response_model=ParseResponseSchema)
async def start_parse_url(request: ParseUrlRequestSchema, background_tasks: BackgroundTasks):
    """Start parsing from a pasted 2GIS URL."""
    from app.utils.helpers import UrlExtractor

    if not UrlExtractor.is_2gis_url(request.url):
        raise InvalidRequestError("Вставьте корректную ссылку 2ГИС")

    parse_request = ParseRequest(
        query=request.url,
        cities=["2gis-url"],
        export_columns=request.columns,
    )
    task_id = task_manager.create_task(parse_request)
    background_tasks.add_task(
        run_url_parser_task,
        task_id,
        request.url,
        request.max_pages,
        request.max_filials,
        request.workers,
        request.columns,
    )

    return ParseResponseSchema(
        task_id=task_id,
        status="pending",
        message="Парсинг ссылки 2ГИС запущен"
    )


@router.get("/api/v1/tasks/{task_id}", response_model=TaskStatusSchema)
async def get_task_status(task_id: str):
    """РџРѕР»СѓС‡РµРЅРёРµ СЃС‚Р°С‚СѓСЃР° Р·Р°РґР°С‡Рё."""
    task = get_task_or_404(task_id)
    
    task_dict = task_manager.get_task_dict(task_id)
    if not task_dict:
        raise TaskNotFoundError(f"Р—Р°РґР°С‡Р° {task_id} РЅРµ РЅР°Р№РґРµРЅР°")
    
    return TaskStatusSchema(**task_dict)


@router.get("/api/v1/tasks/{task_id}/results", response_model=ResultsSchema)
async def get_task_results(
    task_id: str,
    page: int = Query(1, ge=1, description="РќРѕРјРµСЂ СЃС‚СЂР°РЅРёС†С‹"),
    per_page: int = Query(20, ge=1, le=100, description="Р—Р°РїРёСЃРµР№ РЅР° СЃС‚СЂР°РЅРёС†Сѓ")
):
    """РџРѕР»СѓС‡РµРЅРёРµ СЂРµР·СѓР»СЊС‚Р°С‚РѕРІ РїР°СЂСЃРёРЅРіР°."""
    task = get_task_or_404(task_id)
    
    if task.progress.status != TaskStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail="Р—Р°РґР°С‡Р° РµС‰Рµ РЅРµ Р·Р°РІРµСЂС€РµРЅР°"
        )
    
    # РџР°РіРёРЅР°С†РёСЏ
    total_count = len(task.firms)
    total_pages = (total_count + per_page - 1) // per_page
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    firms_page = task.firms[start_idx:end_idx]
    
    # РџСЂРµРѕР±СЂР°Р·РѕРІР°РЅРёРµ РІ СЃС…РµРјС‹
    firms_schemas = []
    for firm in firms_page:
        firms_schemas.append(FirmSchema(
            name=firm.name,
            rating=firm.rating,
            city=firm.city or _city_from_address(firm.address),
            address=firm.address,
            schedule=firm.schedule,
            phones=firm.phones,
            email=firm.email,
            website=firm.website,
            social=SocialLinksSchema(
                vk=firm.social.vk or None,
                youtube=firm.social.youtube or None,
                ok=firm.social.ok or None,
                telegram=firm.social.telegram or None,
                whatsapp=firm.social.whatsapp or None,
                instagram=firm.social.instagram or None
            ),
            whatsapp_numbers=firm.whatsapp_numbers,
            telegram_username=firm.telegram_username,
            other_social=firm.other_social,
            info=firm.info,
            source_url=firm.source_url
        ))
    
    export_columns = task.request.export_columns or list(EXPORT_HEADERS)

    return ResultsSchema(
        task_id=task_id,
        firms=firms_schemas,
        total_count=total_count,
        export_columns=export_columns,
        page=page,
        per_page=per_page,
        total_pages=total_pages
    )


@router.get("/api/v1/export/columns", response_model=ExportColumnsSchema)
async def get_export_columns():
    """Список колонок, доступных для выгрузки CSV."""
    return ExportColumnsSchema(columns=list(EXPORT_HEADERS))


@router.get("/api/v1/tasks/{task_id}/download")
async def download_excel(
    task_id: str,
    columns: Optional[List[str]] = Query(
        None,
        description="Колонки для экспорта (можно передать несколько раз)",
    ),
):
    """Скачать CSV с результатами; колонки выбираются через query-параметр columns."""
    task = get_task_or_404(task_id)

    if task.progress.status != TaskStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail='Задача ещё не завершена',
        )

    if not task.firms:
        raise HTTPException(status_code=404, detail='Нет данных для экспорта')

    if not columns and task.request.export_columns:
        columns = task.request.export_columns

    try:
        selected = normalize_export_columns(columns)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    filename = f'2gis_export_{task_id}.csv'
    task_columns = normalize_export_columns(
        task.request.export_columns or None
    )
    use_cached = (
        selected == task_columns
        and task.excel_path
        and os.path.isfile(task.excel_path)
    )
    if use_cached:
        return exporter.get_file_response(task.excel_path, filename=filename)

    content = exporter.build_csv_bytes(task.firms, selected)
    return exporter.get_bytes_response(content, filename)


@router.delete("/api/v1/tasks/{task_id}")
async def cancel_task(task_id: str):
    """РћС‚РјРµРЅР° Р·Р°РґР°С‡Рё."""
    success = task_manager.cancel_task(task_id)
    
    if not success:
        raise TaskNotFoundError(f"Р—Р°РґР°С‡Р° {task_id} РЅРµ РЅР°Р№РґРµРЅР°")
    
    return {"message": "Р—Р°РґР°С‡Р° РѕС‚РјРµРЅРµРЅР°", "task_id": task_id}


@router.websocket("/ws/tasks/{task_id}")
async def websocket_task_progress(websocket: WebSocket, task_id: str):
    """WebSocket РґР»СЏ РѕС‚СЃР»РµР¶РёРІР°РЅРёСЏ РїСЂРѕРіСЂРµСЃСЃР° РІ СЂРµР°Р»СЊРЅРѕРј РІСЂРµРјРµРЅРё."""
    await websocket.accept()
    
    try:
        last_status = None
        while True:
            # РџСЂРѕРІРµСЂРєР° СЃСѓС‰РµСЃС‚РІРѕРІР°РЅРёСЏ Р·Р°РґР°С‡Рё
            task = task_manager.get_task(task_id)
            if not task:
                await websocket.send_json({
                    "error": "Р—Р°РґР°С‡Р° РЅРµ РЅР°Р№РґРµРЅР°"
                })
                break
            
            # РџРѕР»СѓС‡РµРЅРёРµ С‚РµРєСѓС‰РµРіРѕ СЃС‚Р°С‚СѓСЃР°
            task_dict = task_manager.get_task_dict(task_id)
            if not task_dict:
                break
            
            # РћС‚РїСЂР°РІРєР° С‚РѕР»СЊРєРѕ РµСЃР»Рё СЃС‚Р°С‚СѓСЃ РёР·РјРµРЅРёР»СЃСЏ
            if task_dict != last_status:
                await websocket.send_json(task_dict)
                last_status = task_dict.copy() if isinstance(task_dict, dict) else task_dict
            
            # Р•СЃР»Рё Р·Р°РґР°С‡Р° Р·Р°РІРµСЂС€РµРЅР°, РѕС‚РїСЂР°РІР»СЏРµРј С„РёРЅР°Р»СЊРЅРѕРµ СЃРѕРѕР±С‰РµРЅРёРµ Рё Р·Р°РєСЂС‹РІР°РµРј
            if task_dict['status'] in ['completed', 'failed', 'cancelled']:
                await asyncio.sleep(1)  # РќРµР±РѕР»СЊС€Р°СЏ Р·Р°РґРµСЂР¶РєР° РїРµСЂРµРґ Р·Р°РєСЂС‹С‚РёРµРј
                break
            
            await asyncio.sleep(2)  # РћР±РЅРѕРІР»РµРЅРёРµ РєР°Р¶РґС‹Рµ 2 СЃРµРєСѓРЅРґС‹
    
    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"error": str(e)})
        except Exception:
            pass
