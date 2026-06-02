# -*- coding: utf-8 -*-
"""Утилиты для парсера 2GIS."""

import re
import base64
from urllib.parse import unquote, urlparse, parse_qs
from typing import Optional, List

from app.models.domain import SocialNetwork


class TextCleaner:
    """Очистка и нормализация текста."""
    
    @staticmethod
    def clean(text: Optional[str]) -> str:
        """Очистка текста от лишних символов."""
        if not text:
            return ""
        text = text.replace('\u00A0', ' ').replace('\u200B', '')
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()
    
    @staticmethod
    def is_parking_line(text: str) -> bool:
        """Проверка на строку о парковках."""
        return bool(re.search(r'парковк', text, flags=re.I))


class UrlExtractor:
    """Извлечение и обработка URL."""
    
    # Домены 2GIS
    _2GIS_DOMAINS = ('2gis.ru', '2gis.com', '2gis.kz')
    
    # Маппинг социальных сетей
    _SOCIAL_PATTERNS = {
        SocialNetwork.VK: ['vk.com'],
        SocialNetwork.YOUTUBE: ['youtube.com', 'youtu.be'],
        SocialNetwork.OK: ['ok.ru', 'odnoklassniki.ru'],
        SocialNetwork.TELEGRAM: ['t.me', 'telegram.org', 'telegram.me'],
        SocialNetwork.WHATSAPP: ['wa.me', 'whatsapp.com'],
        SocialNetwork.INSTAGRAM: ['instagram.com'],
    }
    
    @classmethod
    def is_2gis_url(cls, url: str) -> bool:
        """Проверка на внутреннюю ссылку 2GIS."""
        try:
            host = urlparse(url).netloc.lower()
        except Exception:
            return False
        
        for domain in cls._2GIS_DOMAINS:
            if host == domain or host.endswith(f'.{domain}'):
                return True
        return False
    
    @classmethod
    def categorize_social(cls, url: str) -> SocialNetwork:
        """Определение типа социальной сети по URL."""
        try:
            host = urlparse(url).netloc.lower()
        except Exception:
            return SocialNetwork.OTHER
        
        for network, domains in cls._SOCIAL_PATTERNS.items():
            for domain in domains:
                if domain in host:
                    return network
        
        return SocialNetwork.OTHER
    
    @classmethod
    def extract_base64_urls(cls, text: str) -> List[str]:
        """Извлечение URL из base64 закодированных строк."""
        urls = []
        for match in re.findall(r'(?:^|/)(aHR0[0-9A-Za-z+/=]+)', text):
            padding = '=' * (-len(match) % 4)
            try:
                decoded = base64.b64decode(match + padding).decode('utf-8', 'ignore')
                found = re.findall(r'https?://[^\s"\'<>]+', decoded, flags=re.I)
                urls.extend(found)
            except Exception:
                continue
        return urls
    
    @classmethod
    def extract_real_url(cls, href: str, label: str = "") -> str:
        """Извлечение реального URL из link.2gis.ru."""
        if not href:
            return ""
        
        # Если это не редирект 2GIS, проверяем на внутреннюю ссылку
        if not re.match(r'https://link\.2gis\.(?:ru|com|kz)/', href):
            return "" if cls.is_2gis_url(href) else href
        
        decoded = unquote(href)
        
        # 1. Ищем в payload.contact.value
        match = re.search(
            r'"contact"\s*:\s*\{\s*"value"\s*:\s*"(https?://[^"]+)"',
            decoded
        )
        if match:
            real_url = match.group(1).strip()
            if not cls.is_2gis_url(real_url):
                return real_url
        
        # 2. Собираем кандидаты из base64 и прямых ссылок
        candidates = []
        
        # Base64 кандидаты
        for url in cls.extract_base64_urls(decoded) + cls.extract_base64_urls(href):
            if not cls.is_2gis_url(url):
                candidates.append(url)
        
        # Прямые ссылки
        for url in re.findall(r'https?://[^\s"\'<>]+', decoded, flags=re.I):
            if not cls.is_2gis_url(url):
                candidates.append(url)
        
        # Убираем дубликаты, сохраняя порядок
        seen = set()
        candidates = [u for u in candidates if not (u in seen or seen.add(u))]
        
        # Приоритизация по label
        if label and candidates:
            label_lower = label.lower()
            priority_map = {
                'vk': ['vk.com'],
                'вконтакт': ['vk.com'],
                'youtube': ['youtube.com', 'youtu.be'],
                'ok': ['ok.ru'],
                'однокласс': ['ok.ru'],
                'tele': ['t.me', 'telegram.'],
                'whatsapp': ['wa.me', 'whatsapp.com'],
                'instagram': ['instagram.com'],
            }
            
            for keyword, domains in priority_map.items():
                if keyword in label_lower:
                    for domain in domains:
                        for url in candidates:
                            if domain in url.lower():
                                return url
        
        return candidates[0] if candidates else ""
    
    @classmethod
    def _firm_url_match(cls, url: str) -> Optional[re.Match]:
        parsed = urlparse(url)

        match = re.search(
            r'https?://2gis\.(?:ru|kz|com)/([^/]+)/firm/(\d+)',
            url,
            flags=re.I,
        )
        if match:
            city = match.group(1).lower()
            if city in cls._2GIS_DOMAINS or '.' in city:
                return None
            return match

        path = parsed.path if parsed.scheme or parsed.netloc else url
        match = re.search(r'/(?!firm/)([^/]+)/firm/(\d+)', path, flags=re.I)
        if not match:
            return None

        city = match.group(1).lower()
        if city in cls._2GIS_DOMAINS or '.' in city:
            return None
        return match

    @classmethod
    def canonicalize_firm_url(cls, url: str) -> Optional[str]:
        """Канонизация URL фирмы."""
        match = cls._firm_url_match(url)
        if not match:
            return None
        parsed = urlparse(url)
        host = parsed.netloc.lower() or '2gis.kz'
        city, firm_id = match.group(1), match.group(2)
        return f'https://{host}/{city}/firm/{firm_id}'

    @classmethod
    def extract_firm_key(cls, url: str) -> Optional[str]:
        """Извлечение уникального ключа фирмы (city:id)."""
        match = cls._firm_url_match(url)
        if match:
            return f"{match.group(1)}:{match.group(2)}"
        return None

    @classmethod
    def build_search_page_url(cls, base_url: str, page: int) -> str:
        """Построение URL страницы поиска (page=1 — без /page/1)."""
        url = re.sub(r'/page/\d+', '', base_url.rstrip('/'))
        if page <= 1:
            return url
        if '?' in url:
            path, query = url.split('?', 1)
            return f"{path}/page/{page}?{query}"
        return f"{url}/page/{page}"

    @classmethod
    def extract_contact_type(cls, href: str) -> str:
        """Тип контакта из payload ссылки 2GIS (instagram, whatsapp, ...)."""
        if not href:
            return ""
        decoded = unquote(href)
        match = re.search(r'"type"\s*:\s*"([^"]+)"', decoded, flags=re.I)
        return match.group(1).lower() if match else ""

    @classmethod
    def extract_telegram_username(cls, url: str) -> str:
        """Ник Telegram из ссылки t.me/..."""
        if not url:
            return ""
        try:
            parsed = urlparse(url)
        except Exception:
            return ""

        host = parsed.netloc.lower()
        if 't.me' not in host and 'telegram.' not in host:
            return ""

        username = parsed.path.strip('/').split('/')[0]
        if username and username not in ('joinchat', 'addstickers', 'share'):
            return username.lstrip('@')
        return ""

    @classmethod
    def extract_whatsapp_number(cls, url: str) -> str:
        """Извлечение номера телефона из ссылки WhatsApp."""
        if not url:
            return ""
        try:
            parsed = urlparse(url)
        except Exception:
            return ""

        host = parsed.netloc.lower()
        if 'wa.me' in host:
            number = re.sub(r'\D+', '', parsed.path)
            return number

        if 'whatsapp.com' in host:
            query = parse_qs(parsed.query)
            phone = query.get('phone', [''])[0]
            number = re.sub(r'\D+', '', phone)
            if number:
                return number

        return ""
