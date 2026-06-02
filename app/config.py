# -*- coding: utf-8 -*-
"""РљРѕРЅС„РёРіСѓСЂР°С†РёСЏ РїСЂРёР»РѕР¶РµРЅРёСЏ."""

from pydantic import field_validator
from pydantic_settings import BaseSettings
from typing import Dict, Optional


class Settings(BaseSettings):
    """РќР°СЃС‚СЂРѕР№РєРё РїСЂРёР»РѕР¶РµРЅРёСЏ."""
    
    # Debug
    DEBUG: bool = False
    
    # Selenium
    HEADLESS: bool = False
    CHROME_VERSION_MAIN: Optional[int] = 148
    SELENIUM_URL: str = "http://localhost:4444/wd/hub"  # Р”Р»СЏ remote WebDriver
    
    # РџР°СЂСЃРµСЂ
    PAGE_SIZE: int = 12
    REQUEST_DELAY_MIN: float = 0.05
    REQUEST_DELAY_MAX: float = 0.15
    PAGE_TIMEOUT: int = 20
    ELEMENT_TIMEOUT: int = 12
    PARSER_WORKERS: int = 1
    
    # Р—Р°РґР°С‡Рё
    MAX_CONCURRENT_TASKS: int = 3
    TASK_TTL_HOURS: int = 1
    
    # User Agent
    USER_AGENT: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
    
    # Excel
    EXCEL_DIR: str = "exports"

    
    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug_flag(cls, value):
        if isinstance(value, str) and value.strip().lower() in {
            "release",
            "prod",
            "production",
        }:
            return False
        return value

    class Config:
        env_file = ".env"
        case_sensitive = True


# РЎР»РѕРІР°СЂСЊ РёР·РІРµСЃС‚РЅС‹С… РіРѕСЂРѕРґРѕРІ: slug -> РЅР°Р·РІР°РЅРёРµ
# Р”Р»СЏ СЌС‚РёС… РіРѕСЂРѕРґРѕРІ РЅРµ С‚СЂРµР±СѓРµС‚СЃСЏ РїРѕРёСЃРє С‡РµСЂРµР· Selenium
CITIES_DATABASE: Dict[str, str] = {
    'aktau': 'Актау',
    # РњРѕСЃРєРІР° Рё РЎР°РЅРєС‚-РџРµС‚РµСЂР±СѓСЂРі
    'moscow': 'РњРѕСЃРєРІР°',
    'spb': 'РЎР°РЅРєС‚-РџРµС‚РµСЂР±СѓСЂРі',
    
    # РўР°С‚Р°СЂСЃС‚Р°РЅ
    'aznakaevo': 'РђР·РЅР°РєР°РµРІРѕ',
    'kazan': 'РљР°Р·Р°РЅСЊ',
    'almetevsk': 'РђР»СЊРјРµС‚СЊРµРІСЃРє',
    'bavly': 'Р‘Р°РІР»С‹',
    'bugulma': 'Р‘СѓРіСѓР»СЊРјР°',
    'buinsk': 'Р‘СѓРёРЅСЃРє',
    'elabuga': 'Р•Р»Р°Р±СѓРіР°',
    'zainsk': 'Р—Р°РёРЅСЃРє',
    'zelenodolsk': 'Р—РµР»РµРЅРѕРґРѕР»СЊСЃРє',
    'leninogorsk': 'Р›РµРЅРёРЅРѕРіРѕСЂСЃРє',
    'nabchelny': 'РќР°Р±РµСЂРµР¶РЅС‹Рµ Р§РµР»РЅС‹',
    'nizhnekamsk': 'РќРёР¶РЅРµРєР°РјСЃРє',
    'nurlat': 'РќСѓСЂР»Р°С‚',
    'chistopol': 'Р§РёСЃС‚РѕРїРѕР»СЊ',
    
    # РљСЂСѓРїРЅС‹Рµ РіРѕСЂРѕРґР° Р РѕСЃСЃРёРё
    'novosibirsk': 'РќРѕРІРѕСЃРёР±РёСЂСЃРє',
    'ekaterinburg': 'Р•РєР°С‚РµСЂРёРЅР±СѓСЂРі',
    'krasnoyarsk': 'РљСЂР°СЃРЅРѕСЏСЂСЃРє',
    'ufa': 'РЈС„Р°',
    'samara': 'РЎР°РјР°СЂР°',
    'omsk': 'РћРјСЃРє',
    'chelyabinsk': 'Р§РµР»СЏР±РёРЅСЃРє',
    'rostov': 'Р РѕСЃС‚РѕРІ-РЅР°-Р”РѕРЅСѓ',
    'voronezh': 'Р’РѕСЂРѕРЅРµР¶',
    'perm': 'РџРµСЂРјСЊ',
    'volgograd': 'Р’РѕР»РіРѕРіСЂР°Рґ',
    'tyumen': 'РўСЋРјРµРЅСЊ',
    'tolyatti': 'РўРѕР»СЊСЏС‚С‚Рё',
    'izhevsk': 'РР¶РµРІСЃРє',
    'barnaul': 'Р‘Р°СЂРЅР°СѓР»',
    'irkutsk': 'РСЂРєСѓС‚СЃРє',
    'ulyanovsk': 'РЈР»СЊСЏРЅРѕРІСЃРє',
    'khabarovsk': 'РҐР°Р±Р°СЂРѕРІСЃРє',
    'vladivostok': 'Р’Р»Р°РґРёРІРѕСЃС‚РѕРє',
    'yaroslavl': 'РЇСЂРѕСЃР»Р°РІР»СЊ',
    'tomsk': 'РўРѕРјСЃРє',
    'orenburg': 'РћСЂРµРЅР±СѓСЂРі',
    'kemerovo': 'РљРµРјРµСЂРѕРІРѕ',
    'ryazan': 'Р СЏР·Р°РЅСЊ',
    'astrakhan': 'РђСЃС‚СЂР°С…Р°РЅСЊ',
    'saratov': 'РЎР°СЂР°С‚РѕРІ',
    'kirov': 'РљРёСЂРѕРІ',
    'sochi': 'РЎРѕС‡Рё',
    'kursk': 'РљСѓСЂСЃРє',
    'stavropol': 'РЎС‚Р°РІСЂРѕРїРѕР»СЊ',
    'tula': 'РўСѓР»Р°',
    'tver': 'РўРІРµСЂСЊ',
    'magnitogorsk': 'РњР°РіРЅРёС‚РѕРіРѕСЂСЃРє',
    'surgut': 'РЎСѓСЂРіСѓС‚',
    'nizhnevartovsk': 'РќРёР¶РЅРµРІР°СЂС‚РѕРІСЃРє',
    'ntagil': 'РќРёР¶РЅРёР№ РўР°РіРёР»',
    'nnovgorod': 'РќРёР¶РЅРёР№ РќРѕРІРіРѕСЂРѕРґ',
    'kaliningrad': 'РљР°Р»РёРЅРёРЅРіСЂР°Рґ',
    'krasnodar': 'РљСЂР°СЃРЅРѕРґР°СЂ',
    'lipetsk': 'Р›РёРїРµС†Рє',
    'belgorod': 'Р‘РµР»РіРѕСЂРѕРґ',
    'bryansk': 'Р‘СЂСЏРЅСЃРє',
    'murmansk': 'РњСѓСЂРјР°РЅСЃРє',
    'arkhangelsk': 'РђСЂС…Р°РЅРіРµР»СЊСЃРє',
    'kaluga': 'РљР°Р»СѓРіР°',
    'vladimir': 'Р’Р»Р°РґРёРјРёСЂ',
    'cheboksary': 'Р§РµР±РѕРєСЃР°СЂС‹',
    'penza': 'РџРµРЅР·Р°',
    'novokuznetsk': 'РќРѕРІРѕРєСѓР·РЅРµС†Рє',
    'yakutsk': 'РЇРєСѓС‚СЃРє',
    'saransk': 'РЎР°СЂР°РЅСЃРє',
    'tambov': 'РўР°РјР±РѕРІ',
    'syktyvkar': 'РЎС‹РєС‚С‹РІРєР°СЂ',
    'yoshkarola': 'Р™РѕС€РєР°СЂ-РћР»Р°',
    'grozniy': 'Р“СЂРѕР·РЅС‹Р№',
    'makhachkala': 'РњР°С…Р°С‡РєР°Р»Р°',
    'vladikavkaz': 'Р’Р»Р°РґРёРєР°РІРєР°Р·',
    'petrozavodsk': 'РџРµС‚СЂРѕР·Р°РІРѕРґСЃРє',
    'smolensk': 'РЎРјРѕР»РµРЅСЃРє',
    'chita': 'Р§РёС‚Р°',
    'ulan_ude': 'РЈР»Р°РЅ-РЈРґСЌ',
    'blagoveshensk': 'Р‘Р»Р°РіРѕРІРµС‰РµРЅСЃРє',
    'yuzhno_sahalinsk': 'Р®Р¶РЅРѕ-РЎР°С…Р°Р»РёРЅСЃРє',
    'komsomolsk': 'РљРѕРјСЃРѕРјРѕР»СЊСЃРє-РЅР°-РђРјСѓСЂРµ',
    'pskov': 'РџСЃРєРѕРІ',
    'kostroma': 'РљРѕСЃС‚СЂРѕРјР°',
    'vologda': 'Р’РѕР»РѕРіРґР°',
    'kurgan': 'РљСѓСЂРіР°РЅ',
    'orel': 'РћСЂС‘Р»',
    'ivanovo': 'РРІР°РЅРѕРІРѕ',
    'novgorod': 'Р’РµР»РёРєРёР№ РќРѕРІРіРѕСЂРѕРґ',
}

# URL С€Р°Р±Р»РѕРЅ РґР»СЏ РїРѕРёСЃРєР°
SEARCH_URL_TEMPLATE = 'https://2gis.ru/{city}/search/{query}/page/{page}'


settings = Settings()
