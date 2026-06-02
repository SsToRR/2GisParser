# -*- coding: utf-8 -*-
"""Pydantic СЃС…РµРјС‹ РґР»СЏ API."""

from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
from datetime import datetime

from app.models.domain import TaskStatus



class ParseUrlRequestSchema(BaseModel):
    """Request schema for parsing a pasted 2GIS URL."""
    url: str = Field(..., min_length=10, max_length=2000, description="2GIS URL")
    max_pages: int = Field(50, ge=1, le=200, description="Maximum search pages to scan")
    max_filials: int = Field(100, ge=1, le=5000, description="Maximum filial cards to parse")
    workers: int = Field(1, ge=1, le=4, description="Parallel browser workers for filial cards")
    columns: List[str] = Field(
        ...,
        min_length=1,
        description="Колонки для сбора (что парсить и выгружать)",
    )

    @field_validator('url')
    @classmethod
    def validate_url(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("URL is required")
        return v

    @field_validator('columns')
    @classmethod
    def validate_columns(cls, v: List[str]) -> List[str]:
        from app.services.export import normalize_export_columns
        return normalize_export_columns(v)


class ParseResponseSchema(BaseModel):
    """РЎС…РµРјР° РѕС‚РІРµС‚Р° РЅР° Р·Р°РїСЂРѕСЃ РїР°СЂСЃРёРЅРіР°."""
    task_id: str
    status: str
    message: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "task_id": "abc12345",
                "status": "pending",
                "message": "Р—Р°РґР°С‡Р° СЃРѕР·РґР°РЅР° Рё РїРѕСЃС‚Р°РІР»РµРЅР° РІ РѕС‡РµСЂРµРґСЊ"
            }
        }


class TaskStatusSchema(BaseModel):
    """РЎС…РµРјР° СЃС‚Р°С‚СѓСЃР° Р·Р°РґР°С‡Рё."""
    task_id: str
    status: TaskStatus
    progress: int = Field(..., ge=0, le=100, description="РџСЂРѕС†РµРЅС‚ РІС‹РїРѕР»РЅРµРЅРёСЏ")
    current_city: Optional[str] = None
    current_city_index: int = 0
    total_cities: int = 0
    current_page: int = 0
    total_pages: int = 0
    firms_processed: int = 0
    firms_total: int = 0
    message: Optional[str] = None
    errors: List[str] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "task_id": "abc12345",
                "status": "running",
                "progress": 45,
                "current_city": "РљР°Р·Р°РЅСЊ",
                "current_city_index": 2,
                "total_cities": 5,
                "current_page": 3,
                "total_pages": 10,
                "firms_processed": 25,
                "firms_total": 55,
                "message": "РџР°СЂСЃРёРЅРі РІ РїСЂРѕС†РµСЃСЃРµ",
                "errors": []
            }
        }


class SocialLinksSchema(BaseModel):
    """РЎС…РµРјР° СЃРѕС†РёР°Р»СЊРЅС‹С… СЃСЃС‹Р»РѕРє."""
    vk: Optional[str] = None
    youtube: Optional[str] = None
    ok: Optional[str] = None
    telegram: Optional[str] = None
    whatsapp: Optional[str] = None
    instagram: Optional[str] = None


class FirmSchema(BaseModel):
    """РЎС…РµРјР° РґР°РЅРЅС‹С… С„РёСЂРјС‹."""
    name: str = ""
    rating: str = ""
    city: str
    address: str
    schedule: str
    phones: List[str]
    email: str
    website: str
    social: SocialLinksSchema
    whatsapp_numbers: List[str] = Field(default_factory=list)
    telegram_username: str = ""
    other_social: List[str] = Field(default_factory=list)
    info: List[str]
    source_url: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "city": "РљР°Р·Р°РЅСЊ",
                "address": "СѓР». РџСѓС€РєРёРЅР°, Рґ. 10",
                "schedule": "РџРЅ-РџС‚: 9:00-18:00",
                "phones": ["+7 (843) 123-45-67"],
                "email": "info@example.com",
                "website": "https://example.com",
                "social": {
                    "vk": "https://vk.com/example",
                    "youtube": None,
                    "ok": None,
                    "telegram": None,
                    "whatsapp": None
                },
                "info": ["РћРћРћ", "РРќРќ: 1234567890"],
                "source_url": "https://2gis.ru/kazan/firm/123456"
            }
        }


class ExportColumnsSchema(BaseModel):
    """Доступные колонки для экспорта CSV."""
    columns: List[str]


class ResultsSchema(BaseModel):
    """РЎС…РµРјР° СЂРµР·СѓР»СЊС‚Р°С‚РѕРІ РїР°СЂСЃРёРЅРіР°."""
    task_id: str
    firms: List[FirmSchema]
    total_count: int
    export_columns: List[str] = Field(default_factory=list)
    page: int = 1
    per_page: int = 20
    total_pages: int = 1
    
    class Config:
        json_schema_extra = {
            "example": {
                "task_id": "abc12345",
                "firms": [],
                "total_count": 0,
                "page": 1,
                "per_page": 20,
                "total_pages": 1
            }
        }
