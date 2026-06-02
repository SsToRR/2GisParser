#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Скрипт для запуска приложения."""

import uvicorn
from app.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8002,
        reload=settings.DEBUG
    )

