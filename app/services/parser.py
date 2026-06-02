# -*- coding: utf-8 -*-
"""РЎРµСЂРІРёСЃ РїР°СЂСЃРёРЅРіР° 2GIS."""

import re
import math
import time
import random
import uuid
from threading import Lock
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Callable, List, Set
from urllib.parse import quote, urljoin, urlsplit, urlunsplit, parse_qsl, urlencode

from selenium import webdriver
import undetected_chromedriver as uc
from selenium_stealth import stealth
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    StaleElementReferenceException,
    WebDriverException,
)

from app.config import settings, CITIES_DATABASE, SEARCH_URL_TEMPLATE
from app.models.domain import (
    FirmData, SocialLinks, ParseProgress, ParseRequest,
    ParseResult, TaskStatus, SocialNetwork
)
from app.utils.helpers import TextCleaner, UrlExtractor
from app.utils.progress_log import ParseProgressLog
from app.services.scrape_fields import ScrapeFields


def _patch_uc_destructor() -> None:
    """РџРѕРґР°РІР»РµРЅРёРµ С€СѓРјРЅРѕРіРѕ __del__ РІ uc РЅР° Windows."""
    try:
        original_del = uc.Chrome.__del__
    except Exception:
        return

    def _safe_del(self):
        try:
            original_del(self)
        except Exception:
            # РРЅРѕРіРґР° uc Р±СЂРѕСЃР°РµС‚ OSError [WinError 6] РїСЂРё С„РёРЅР°Р»РёР·Р°С†РёРё.
            # РќР° СЂРµР·СѓР»СЊС‚Р°С‚ РїР°СЂСЃРёРЅРіР° СЌС‚Рѕ РЅРµ РІР»РёСЏРµС‚.
            pass

    try:
        uc.Chrome.__del__ = _safe_del
    except Exception:
        pass


_patch_uc_destructor()


def _safe_quit_driver(driver) -> None:
    """Р‘РµР·РѕРїР°СЃРЅРѕРµ Р·Р°РєСЂС‹С‚РёРµ РґСЂР°Р№РІРµСЂР° Р±РµР· С€СѓРјРЅС‹С… РёСЃРєР»СЋС‡РµРЅРёР№."""
    if not driver:
        return
    try:
        driver.quit()
    except Exception:
        pass


def _split_chunks(values: List[str], parts: int) -> List[List[str]]:
    """Р Р°Р·Р±РёС‚СЊ СЃРїРёСЃРѕРє РЅР° N РЅРµРїСѓСЃС‚С‹С… С‡Р°РЅРєРѕРІ."""
    if parts <= 1 or len(values) <= 1:
        return [values]
    chunk_size = max(1, math.ceil(len(values) / parts))
    return [values[i:i + chunk_size] for i in range(0, len(values), chunk_size)]


def _dismiss_overlays(driver: webdriver.Chrome) -> None:
    """Р—Р°РєСЂС‹С‚РёРµ cookie-Р±Р°РЅРЅРµСЂР° Рё РїСЂРѕС‡РёС… РѕРІРµСЂР»РµРµРІ."""
    xpaths = [
        "//button[contains(., 'РџСЂРёРЅСЏС‚СЊ')]",
        "//button[contains(., 'РЎРѕРіР»Р°СЃРµРЅ')]",
        "//button[contains(., 'РҐРѕСЂРѕС€Рѕ')]",
        "//button[contains(., 'РџРѕРЅСЏС‚РЅРѕ')]",
        "//button[contains(., 'OK')]",
        "//*[contains(@class, 'cookie')]//button",
        "//a[contains(., 'РџРѕРґСЂРѕР±РЅРµРµ')]/following::button[1]",
    ]
    for xpath in xpaths:
        try:
            buttons = driver.find_elements(By.XPATH, xpath)
            for btn in buttons:
                if btn.is_displayed():
                    driver.execute_script("arguments[0].click();", btn)
                    return
        except Exception:
            continue


def _wait_for_search_results(driver: webdriver.Chrome, timeout: int = 35) -> bool:
    """РћР¶РёРґР°РЅРёРµ РїРѕСЏРІР»РµРЅРёСЏ РєР°СЂС‚РѕС‡РµРє РѕСЂРіР°РЅРёР·Р°С†РёР№ РІ СЃРїРёСЃРєРµ."""
    def _has_firm_links(d: webdriver.Chrome) -> bool:
        return len(d.find_elements(By.CSS_SELECTOR, 'a[href*="/firm/"]')) > 0

    try:
        WebDriverWait(driver, timeout).until(_has_firm_links)
        return True
    except TimeoutException:
        return False


def _scroll_results_panel(driver: webdriver.Chrome) -> None:
    """РџСЂРѕРєСЂСѓС‚РєР° СЃРїРёСЃРєР° СЂРµР·СѓР»СЊС‚Р°С‚РѕРІ РґР»СЏ РїРѕРґРіСЂСѓР·РєРё РєР°СЂС‚РѕС‡РµРє."""
    driver.execute_script(
        """
        const list = document.querySelector('[class*="_1rkbbi"]')
            || document.querySelector('div[class*="scroll"]');
        if (list) { list.scrollTop = list.scrollHeight / 2; }
        window.scrollBy(0, 400);
        """
    )


def _wait_dom_ready(driver: webdriver.Chrome, timeout: int = 12) -> bool:
    """РћР¶РёРґР°РЅРёРµ РїРѕР»РЅРѕР№ Р·Р°РіСЂСѓР·РєРё DOM."""
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: d.execute_script("return document.readyState") in ("interactive", "complete")
        )
        return True
    except TimeoutException:
        return False


# РўРёРї callback-С„СѓРЅРєС†РёРё РґР»СЏ РѕС‚С‡С‘С‚Р° Рѕ РїСЂРѕРіСЂРµСЃСЃРµ
ProgressCallback = Callable[[ParseProgress], None]

# РњР°РєСЃРёРјР°Р»СЊРЅРѕРµ РєРѕР»РёС‡РµСЃС‚РІРѕ СЃС‚СЂР°РЅРёС† РїРѕРґСЂСЏРґ СЃ РґСѓР±Р»РёРєР°С‚Р°РјРё РїРµСЂРµРґ РѕСЃС‚Р°РЅРѕРІРєРѕР№
MAX_CONSECUTIVE_DUPLICATE_PAGES = 10


class WebDriverFactory:
    """Р¤Р°Р±СЂРёРєР° РґР»СЏ СЃРѕР·РґР°РЅРёСЏ WebDriver."""

    @staticmethod
    def create(headless: Optional[bool] = None):
        """РЎРѕР·РґР°РЅРёРµ WebDriver (Р»РѕРєР°Р»СЊРЅС‹Р№ РёР»Рё СѓРґР°Р»С‘РЅРЅС‹Р№)."""
        import logging
        logger = logging.getLogger(__name__)
        use_headless = settings.HEADLESS if headless is None else headless
        
        # Р•СЃР»Рё СѓРєР°Р·Р°РЅ SELENIUM_URL - РёСЃРїРѕР»СЊР·СѓРµРј СѓРґР°Р»С‘РЅРЅС‹Р№ Selenium
        if settings.SELENIUM_URL and settings.SELENIUM_URL != "http://localhost:4444/wd/hub":
            logger.info(f"РџРѕРґРєР»СЋС‡РµРЅРёРµ Рє СѓРґР°Р»С‘РЅРЅРѕРјСѓ Selenium: {settings.SELENIUM_URL}")
            
            options = webdriver.ChromeOptions()
            options.page_load_strategy = 'eager'
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument('--disable-infobars')
            options.add_argument('--disable-extensions')
            options.add_argument('--window-size=1920,1080')
            options.add_argument(f'user-agent={settings.USER_AGENT}')
            options.add_experimental_option(
                "prefs",
                {
                    "profile.managed_default_content_settings.images": 2,
                    "profile.default_content_setting_values.notifications": 2,
                }
            )
            
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            
            if use_headless:
                options.add_argument('--headless=new')
            
            try:
                driver = webdriver.Remote(
                    command_executor=settings.SELENIUM_URL,
                    options=options
                )
                logger.info("WebDriver СЃРѕР·РґР°РЅ СѓСЃРїРµС€РЅРѕ")
                
                # РњР°СЃРєРёСЂРѕРІРєР° С‡РµСЂРµР· CDP
                try:
                    driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                        'source': '''
                            Object.defineProperty(navigator, 'webdriver', {
                                get: () => undefined
                            });
                        '''
                    })
                    logger.info("CDP РјР°СЃРєРёСЂРѕРІРєР° РїСЂРёРјРµРЅРµРЅР°")
                except Exception as e:
                    logger.warning(f"CDP РЅРµ РїРѕРґРґРµСЂР¶РёРІР°РµС‚СЃСЏ: {e}")
                    
            except Exception as e:
                logger.error(f"РћС€РёР±РєР° СЃРѕР·РґР°РЅРёСЏ WebDriver: {e}")
                raise
            
        else:
            # Р›РѕРєР°Р»СЊРЅС‹Р№ Р·Р°РїСѓСЃРє СЃ undetected-chromedriver
            logger.info("Р›РѕРєР°Р»СЊРЅС‹Р№ Р·Р°РїСѓСЃРє СЃ undetected-chromedriver")
            
            options = uc.ChromeOptions()
            options.page_load_strategy = 'eager'
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-popup-blocking')
            options.add_argument('--start-maximized')
            options.add_argument('--window-size=1920,1080')
            options.add_experimental_option(
                "prefs",
                {
                    "profile.managed_default_content_settings.images": 2,
                    "profile.default_content_setting_values.notifications": 2,
                }
            )
            if not use_headless:
                options.add_argument('--start-maximized')
            else:
                options.add_argument('--disable-gpu')

            chrome_version = getattr(settings, 'CHROME_VERSION_MAIN', None)
            logger.info(
                "Chrome: headless=%s, version_main=%s",
                use_headless,
                chrome_version,
            )
            driver = uc.Chrome(
                options=options,
                use_subprocess=True,
                headless=use_headless,
                version_main=chrome_version,
            )

        try:
            driver.set_page_load_timeout(settings.PAGE_TIMEOUT)
            driver.implicitly_wait(0)
        except Exception:
            pass

        try:
            driver.maximize_window()
        except Exception:
            pass

        return driver        

class CitySlugResolver:
    """РљР»Р°СЃСЃ РґР»СЏ РїРѕР»СѓС‡РµРЅРёСЏ slug РіРѕСЂРѕРґР° С‡РµСЂРµР· 2GIS."""
    
    @staticmethod
    def get_city_slug(city_name: str) -> Optional[str]:
        """
        РџРѕР»СѓС‡РµРЅРёРµ slug РіРѕСЂРѕРґР°.
        РЎРЅР°С‡Р°Р»Р° РїСЂРѕРІРµСЂСЏРµС‚ CITIES_DATABASE, РµСЃР»Рё РЅРµ РЅР°Р№РґРµРЅРѕ - РёС‰РµС‚ С‡РµСЂРµР· Selenium.
        """
        # РџСЂРѕРІРµСЂСЏРµРј, РµСЃС‚СЊ Р»Рё РіРѕСЂРѕРґ РІ Р±Р°Р·Рµ (РёС‰РµРј РїРѕ РЅР°Р·РІР°РЅРёСЋ)
        for slug, name in CITIES_DATABASE.items():
            if name.lower() == city_name.lower():
                return slug
        
        # Р•СЃР»Рё РЅРµ РЅР°С€Р»Рё - РёС‰РµРј С‡РµСЂРµР· Selenium
        return CitySlugResolver._search_city_slug(city_name)
    
    @staticmethod
    def _search_city_slug(city_name: str) -> Optional[str]:
        """РџРѕРёСЃРє slug РіРѕСЂРѕРґР° С‡РµСЂРµР· 2GIS СЃ РїРѕРјРѕС‰СЊСЋ Selenium."""
        options = webdriver.ChromeOptions()
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--window-size=1920,1080")
        options.add_argument(f"user-agent={settings.USER_AGENT}")
        
        driver = webdriver.Chrome(options=options)
        
        try:
            driver.get("https://2gis.ru")
            start_url = driver.current_url
            
            # Р–РґРµРј Рё РЅР°С…РѕРґРёРј РїРѕР»Рµ РїРѕРёСЃРєР°
            wait = WebDriverWait(driver, 15)
            search_input = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "input[placeholder='РџРѕРёСЃРє РІ 2Р“РРЎ']"))
            )
            
            # Р’РІРѕРґРёРј РіРѕСЂРѕРґ
            search_input.send_keys(city_name)
            time.sleep(0.5)
            search_input.send_keys(Keys.ENTER)
            
            # РћР¶РёРґР°РЅРёРµ СЃРјРµРЅС‹ URL
            def url_changed_to_city(d):
                current = d.current_url
                return current != start_url and "/search/" not in current
            
            try:
                wait.until(url_changed_to_city)
                time.sleep(1.5)
            except TimeoutException:
                pass
            
            final_url = driver.current_url
            
            # РР·РІР»РµРєР°РµРј slug РіРѕСЂРѕРґР° РёР· URL
            match = re.search(r'2gis\.ru/([^/]+)', final_url)
            
            if match:
                city_slug = match.group(1).split('?')[0]
                return city_slug
            
            return None
            
        except Exception as e:
            if settings.DEBUG:
                print(f"РћС€РёР±РєР° РїРѕРёСЃРєР° slug РґР»СЏ РіРѕСЂРѕРґР° {city_name}: {e}")
            return None
        finally:
            driver.quit()


class FirmScraper:
    """РЎРєСЂР°РїРµСЂ РґР°РЅРЅС‹С… С„РёСЂРјС‹."""
    
    def __init__(
        self,
        driver: webdriver.Chrome,
        progress: Optional[ParseProgressLog] = None,
        scrape_fields: Optional[ScrapeFields] = None,
    ):
        self.driver = driver
        self.cleaner = TextCleaner()
        self.progress = progress or ParseProgressLog()
        self.fields = scrape_fields or ScrapeFields.all()
    
    def scrape(
        self,
        firm_url: str,
        city_name: str,
        index: int = 0,
        total: int = 0,
    ) -> FirmData:
        """РЎР±РѕСЂ РґР°РЅРЅС‹С… Рѕ С„РёСЂРјРµ."""
        firm = FirmData(
            city=city_name if self.fields.wants('\u0413\u043e\u0440\u043e\u0434') else '',
            source_url=firm_url if self.fields.wants('URL') else '',
        )
        label = f" ({index}/{total})" if total else ""
        fields = self.fields

        try:
            self.progress.step(f"РћС‚РєСЂС‹РІР°СЋ РєР°СЂС‚РѕС‡РєСѓ{label}вЂ¦")
            self.driver.get(firm_url)
            _wait_dom_ready(self.driver, timeout=settings.ELEMENT_TIMEOUT)
            _dismiss_overlays(self.driver)

            if fields.needs_phone_button:
                self.progress.step(f"РЎРѕР±РёСЂР°СЋ С‚РµР»РµС„РѕРЅ{label}вЂ¦")
                self._click_show_phones()

            if fields.needs_name:
                self.progress.step(f"РЎРѕР±РёСЂР°СЋ РЅР°Р·РІР°РЅРёРµ{label}вЂ¦")
                firm.name = self._get_name()

            if fields.needs_rating:
                self.progress.detail("РЎРѕР±РёСЂР°СЋ РѕС†РµРЅРєСѓвЂ¦")
                firm.rating = self._get_rating()

            needs_city = fields.wants('\u0413\u043e\u0440\u043e\u0434')
            if fields.needs_address or needs_city:
                self.progress.step(f"РЎРѕР±РёСЂР°СЋ Р°РґСЂРµСЃ{label}вЂ¦")
                address = self._get_address()
                if fields.needs_address:
                    firm.address = address
                if needs_city:
                    firm.city = self._city_from_address(address) or firm.city

            if fields.needs_schedule:
                self.progress.detail("РЎРѕР±РёСЂР°СЋ СЂР°СЃРїРёСЃР°РЅРёРµвЂ¦")
                firm.schedule = self._get_schedule()

            if fields.needs_phones:
                self.progress.detail("РЎРѕР±РёСЂР°СЋ РЅРѕРјРµСЂР°вЂ¦")
                firm.phones = self._get_phones()

            if fields.needs_any_contact_step:
                self.progress.step(f"РЎРѕР±РёСЂР°СЋ РєРѕРЅС‚Р°РєС‚С‹{label}вЂ¦")

            if fields.needs_email:
                firm.email = self._get_email()

            if fields.needs_website:
                firm.website = self._get_website()

            if fields.needs_social_links:
                firm.social, firm.other_social = self._collect_social_links()
                fields.trim_social(firm.social)
                if not fields.wants('Р”СЂСѓРіРёРµ СЃРѕС†СЃРµС‚Рё'):
                    firm.other_social = []

            if fields.needs_whatsapp_numbers:
                numbers = self._get_whatsapp_numbers()
                if firm.social.whatsapp:
                    wa_from_link = UrlExtractor.extract_whatsapp_number(
                        firm.social.whatsapp
                    )
                    if wa_from_link and wa_from_link not in numbers:
                        numbers.append(wa_from_link)
                firm.whatsapp_numbers = numbers
            elif fields.wants('Whatsapp СЃСЃС‹Р»РєР°') and firm.social.whatsapp:
                wa_from_link = UrlExtractor.extract_whatsapp_number(
                    firm.social.whatsapp
                )
                if wa_from_link:
                    firm.whatsapp_numbers = [wa_from_link]

            if fields.needs_telegram_username and firm.social.telegram:
                firm.telegram_username = UrlExtractor.extract_telegram_username(
                    firm.social.telegram
                )

            if fields.needs_info:
                firm.info = self._get_info()

            name_part = firm.name or f"РєР°СЂС‚РѕС‡РєР° {index or ''}".strip() or "Р±РµР· РЅР°Р·РІР°РЅРёСЏ"
            self.progress.done(f"{name_part}: РіРѕС‚РѕРІРѕ")
            
        except Exception as e:
            self.progress.warn(f"РћС€РёР±РєР° РєР°СЂС‚РѕС‡РєРё: {e}")
            if settings.DEBUG:
                print(f"РћС€РёР±РєР° РїСЂРё СЃР±РѕСЂРµ С„РёСЂРјС‹ {firm_url}: {e}")
        
        return firm
    
    def _click_show_phones(self) -> None:
        """РљР»РёРє РїРѕ РєРЅРѕРїРєРµ РїРѕРєР°Р·Р° С‚РµР»РµС„РѕРЅРѕРІ."""
        try:
            button = WebDriverWait(self.driver, 6).until(
                EC.presence_of_element_located((By.CLASS_NAME, '_1tkj2hw'))
            )
            self.driver.execute_script(
                "arguments[0].scrollIntoView({block:'center'});", button
            )
            self.driver.execute_script("arguments[0].click();", button)
        except TimeoutException:
            pass
    
    def _get_name(self) -> str:
        """РџРѕР»СѓС‡РµРЅРёРµ РЅР°Р·РІР°РЅРёСЏ РєРѕРјРїР°РЅРёРё."""
        selectors = [
            'h1._1x89xo5',
            'h1[data-testid="card-title"]',
            'h1[class*="_"]',
            'h1',
        ]

        for selector in selectors:
            try:
                heading = WebDriverWait(self.driver, 4).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )

                # РЎРЅР°С‡Р°Р»Р° РїСЂРѕР±СѓРµРј span-С‡Р°СЃС‚Рё, РїРѕС‚РѕРј РїРѕР»РЅС‹Р№ С‚РµРєСЃС‚ h1
                for span in heading.find_elements(By.TAG_NAME, 'span'):
                    text = self.cleaner.clean(span.text)
                    if text and text.lower() != '2РіРёСЃ':
                        return text

                full_text = self.cleaner.clean(
                    heading.get_attribute('innerText') or heading.text
                )
                if full_text and full_text.lower() != '2РіРёСЃ':
                    return full_text
            except TimeoutException:
                continue
            except Exception:
                continue

        # Fallback 1: РјРµС‚Р°-С‚РµРі og:title
        try:
            og_title = self.driver.execute_script(
                "const el=document.querySelector('meta[property=\"og:title\"]');"
                "return el ? el.getAttribute('content') : '';"
            )
            og_title = self.cleaner.clean(og_title)
            if og_title:
                return og_title.split('вЂ”')[0].strip()
        except Exception:
            pass

        # Fallback 2: title СЃС‚СЂР°РЅРёС†С‹
        try:
            title = self.cleaner.clean(self.driver.title)
            if title:
                return title.split('вЂ”')[0].strip()
        except Exception:
            pass

        return ""

    def _get_rating_legacy(self) -> str:
        """РџРѕР»СѓС‡РµРЅРёРµ РѕС†РµРЅРєРё С„РёР»РёР°Р»Р° (div._y10azs)."""
        try:
            elements = WebDriverWait(self.driver, 6).until(
                EC.presence_of_all_elements_located(
                    (By.CSS_SELECTOR, 'div._y10azs')
                )
            )
            for element in elements:
                text = self.cleaner.clean(element.text)
                if not text:
                    continue
                match = re.search(r'\d+(?:[.,]\d+)?', text)
                if match:
                    return match.group(0).replace(',', '.')
        except TimeoutException:
            pass
        return ""

    def _get_rating(self) -> str:
        """Get filial rating from visible block, meta data, or nearby rating text."""
        try:
            element = WebDriverWait(self.driver, 6).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'div._y10azs'))
            )
            rating = self._normalize_rating_candidate(
                self.driver.execute_script(
                    "return arguments[0].innerText || arguments[0].textContent || '';",
                    element,
                )
            )
            if rating:
                return rating
        except TimeoutException:
            pass
        except Exception:
            pass

        selectors = (
            'div._y10azs',
            '[class*="_y10azs"]',
            '[itemprop="ratingValue"]',
            'meta[itemprop="ratingValue"]',
            'meta[property="product:rating:value"]',
        )

        try:
            for selector in selectors:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for element in elements:
                    text = self.driver.execute_script(
                        "return arguments[0].content || arguments[0].innerText || arguments[0].textContent || '';",
                        element,
                    )
                    rating = self._normalize_rating_candidate(text)
                    if rating:
                        return rating
        except Exception:
            pass

        try:
            text = self.driver.execute_script(
                """
                const parts = [];
                for (const el of document.querySelectorAll('[aria-label], [title]')) {
                    parts.push(el.getAttribute('aria-label') || '');
                    parts.push(el.getAttribute('title') || '');
                }
                parts.push(document.body ? document.body.innerText : '');
                return parts.filter(Boolean).join('\\n');
                """
            )
            rating = self._normalize_rating_candidate(text, contextual=True)
            if rating:
                return rating
        except Exception:
            pass

        return ""

    @staticmethod
    def _normalize_rating_candidate(text: str, contextual: bool = False) -> str:
        if not text:
            return ""

        source = str(text).replace('\xa0', ' ')
        patterns = (
            r'(?i)(?:СЂРµР№С‚РёРЅРі|РѕС†РµРЅРєР°|rating|rate)[^\d]{0,40}([1-5](?:[.,]\d)?)',
            r'\b([1-5][.,]\d)\b',
        ) if contextual else (
            r'\b([1-5](?:[.,]\d)?)\b',
        )

        for pattern in patterns:
            match = re.search(pattern, source)
            if not match:
                continue
            value = match.group(1).replace(',', '.')
            try:
                number = float(value)
            except ValueError:
                continue
            if 0 < number <= 5:
                return f'{number:.1f}'.rstrip('0').rstrip('.')
        return ""

    def _get_address(self) -> str:
        """РџРѕР»СѓС‡РµРЅРёРµ Р°РґСЂРµСЃР°."""
        try:
            full = self.driver.find_elements(By.CSS_SELECTOR, 'div._1p8iqzw')
            if full:
                text = self.cleaner.clean(full[0].text)
                if text:
                    return text
        except Exception:
            pass

        try:
            parts = []
            for span in self.driver.find_elements(
                By.CSS_SELECTOR, 'span._14quei span._wrdavn'
            ):
                part = self.cleaner.clean(span.text)
                if part:
                    parts.append(part)
            if parts:
                return ', '.join(parts)
        except Exception:
            pass

        try:
            element = WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, 'span._wrdavn a._2lcm958')
                )
            )
            return self.cleaner.clean(element.text)
        except TimeoutException:
            return ""

    @staticmethod
    def _city_from_address(address: str) -> str:
        parts = [part.strip() for part in (address or '').split(',')]
        return parts[1] if len(parts) > 1 else ""
    
    def _get_schedule(self) -> str:
        """РџРѕР»СѓС‡РµРЅРёРµ СЂР°СЃРїРёСЃР°РЅРёСЏ."""
        try:
            element = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, '_ksc2xc'))
            )
            return self.cleaner.clean(
                self.driver.execute_script("return arguments[0].innerText;", element)
            )
        except TimeoutException:
            return ""
    
    def _get_phones(self) -> List[str]:
        """РџРѕР»СѓС‡РµРЅРёРµ С‚РµР»РµС„РѕРЅРѕРІ."""
        phones = []
        try:
            for anchor in self.driver.find_elements(
                By.CSS_SELECTOR, 'a._2lcm958[href^="tel:"]'
            ):
                phone = self._normalize_phone(self.cleaner.clean(anchor.text))
                if phone and phone not in phones:
                    phones.append(phone)
        except Exception:
            pass
        return phones

    @staticmethod
    def _normalize_phone(phone: str) -> str:
        return re.sub(r'[-вЂђвЂ‘вЂ’вЂ“вЂ”вЂ•]+', '', phone or '').strip()
    
    def _get_email(self) -> str:
        """РџРѕР»СѓС‡РµРЅРёРµ email."""
        try:
            # РЎРЅР°С‡Р°Р»Р° РёС‰РµРј РІ mailto СЃСЃС‹Р»РєР°С…
            for anchor in self.driver.find_elements(
                By.CSS_SELECTOR, 'a[href^="mailto:"]'
            ):
                href = anchor.get_attribute('href') or ''
                match = re.search(r'mailto:([^?]+)', href, flags=re.I)
                if match:
                    return match.group(1).strip()
            
            # Р•СЃР»Рё РЅРµ РЅР°С€Р»Рё, РёС‰РµРј РІ С‚РµРєСЃС‚Рµ СЃС‚СЂР°РЅРёС†С‹
            body_text = self.driver.execute_script("return document.body.innerText;")
            emails = re.findall(
                r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}',
                body_text
            )
            return emails[0] if emails else ""
        except Exception:
            return ""
    
    def _get_website(self) -> str:
        """РџРѕР»СѓС‡РµРЅРёРµ СЃР°Р№С‚Р°."""
        try:
            contact_rows = WebDriverWait(self.driver, 8).until(
                EC.presence_of_all_elements_located(
                    (By.CSS_SELECTOR, 'div._172gbf8[data-divider="true"]')
                )
            )
            
            for row in contact_rows:
                anchors = row.find_elements(
                    By.CSS_SELECTOR,
                    'a[target="_blank"][href], a._1rehek[href]'
                )
                for anchor in anchors:
                    href = anchor.get_attribute('href') or ''
                    if href.startswith(('tel:', 'mailto:')):
                        continue
                    
                    label = self.cleaner.clean(
                        anchor.text or anchor.get_attribute('aria-label') or ''
                    )
                    real_url = UrlExtractor.extract_real_url(href, label)
                    
                    if real_url and not UrlExtractor.is_2gis_url(real_url):
                        # РџСЂРѕРІРµСЂСЏРµРј, С‡С‚Рѕ СЌС‚Рѕ РЅРµ СЃРѕС†СЃРµС‚СЊ
                        if UrlExtractor.categorize_social(real_url) == SocialNetwork.OTHER:
                            return real_url
        except TimeoutException:
            pass
        return ""
    
    def _collect_social_links(self) -> tuple:
        """РЎСЃС‹Р»РєРё РЅР° СЃРѕС†СЃРµС‚Рё РёР· Р±Р»РѕРєР° РєРѕРЅС‚Р°РєС‚РѕРІ (div._2fgdxvm / div._14uxmys)."""
        social = SocialLinks()
        other_links: List[str] = []
        seen_urls: Set[str] = set()

        def process_anchor(anchor) -> None:
            href = anchor.get_attribute('href') or ''
            if not href or href.startswith(('tel:', 'mailto:')):
                return
            label = self.cleaner.clean(
                anchor.get_attribute('aria-label')
                or anchor.text or ''
            )
            real_url = UrlExtractor.extract_real_url(href, label)
            if not real_url or UrlExtractor.is_2gis_url(real_url):
                return
            if real_url in seen_urls:
                return
            seen_urls.add(real_url)
            contact_type = UrlExtractor.extract_contact_type(href)
            if not self._assign_social(
                social, real_url, label, contact_type
            ):
                other_links.append(real_url)

        blocks = self.driver.find_elements(
            By.CSS_SELECTOR, 'div._2fgdxvm div._14uxmys'
        )
        if blocks:
            for block in blocks:
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block:'center'});", block
                )
                for anchor in block.find_elements(
                    By.CSS_SELECTOR, 'a._1rehek[href], a[href^="http"]'
                ):
                    process_anchor(anchor)
        else:
            for selector in ('div._2fgdxvm', 'div._14uxmys'):
                try:
                    containers = WebDriverWait(self.driver, 4).until(
                        EC.presence_of_all_elements_located(
                            (By.CSS_SELECTOR, selector)
                        )
                    )
                except TimeoutException:
                    continue
                for container in containers:
                    self.driver.execute_script(
                        "arguments[0].scrollIntoView({block:'center'});",
                        container,
                    )
                    for anchor in container.find_elements(
                        By.CSS_SELECTOR,
                        'a._1rehek[href], a[href^="http"]',
                    ):
                        process_anchor(anchor)
                if seen_urls:
                    break

        return social, other_links

    def _assign_social(
        self,
        social: SocialLinks,
        url: str,
        label: str = '',
        contact_type: str = '',
    ) -> bool:
        """Р—Р°РїРёСЃСЊ СЃСЃС‹Р»РєРё РІ РїРѕР»Рµ СЃРѕС†СЃРµС‚Рё. True вЂ” РёР·РІРµСЃС‚РЅР°СЏ СЃРµС‚СЊ, РЅРµ РІ В«Р”СЂСѓРіРёРµВ»."""
        label_lower = label.lower()
        ctype = (contact_type or '').lower()

        type_to_field = {
            'instagram': 'instagram',
            'whatsapp': 'whatsapp',
            'telegram': 'telegram',
            'vk': 'vk',
            'vkontakte': 'vk',
            'youtube': 'youtube',
            'ok': 'ok',
            'odnoklassniki': 'ok',
        }
        if ctype in type_to_field:
            field = type_to_field[ctype]
            if not getattr(social, field):
                setattr(social, field, url)
            return True

        network = UrlExtractor.categorize_social(url)
        field_map = {
            SocialNetwork.VK: 'vk',
            SocialNetwork.YOUTUBE: 'youtube',
            SocialNetwork.OK: 'ok',
            SocialNetwork.TELEGRAM: 'telegram',
            SocialNetwork.WHATSAPP: 'whatsapp',
            SocialNetwork.INSTAGRAM: 'instagram',
        }
        if network in field_map:
            field = field_map[network]
            if not getattr(social, field):
                setattr(social, field, url)
            return True

        label_hints = (
            ('instagram', 'instagram'),
            ('whatsapp', 'whatsapp'),
            ('telegram', 'telegram'),
            ('РІРєРѕРЅС‚Р°РєС‚', 'vk'),
            ('youtube', 'youtube'),
            ('РѕРґРЅРѕРєР»Р°СЃСЃ', 'ok'),
        )
        for hint, field in label_hints:
            if hint in label_lower:
                if not getattr(social, field):
                    setattr(social, field, url)
                return True

        return False

    def _get_whatsapp_numbers(self) -> List[str]:
        """РЎР±РѕСЂ WhatsApp-РЅРѕРјРµСЂРѕРІ РёР· РєРѕРЅС‚Р°РєС‚РЅС‹С… СЃСЃС‹Р»РѕРє."""
        numbers: List[str] = []
        seen: Set[str] = set()
        anchors = self.driver.find_elements(
            By.CSS_SELECTOR, 'a[href^="http"], a._1rehek[href]'
        )
        for anchor in anchors:
            href = anchor.get_attribute('href') or ''
            if not href:
                continue
            label = self.cleaner.clean(
                anchor.text or anchor.get_attribute('aria-label') or ''
            )
            real_url = UrlExtractor.extract_real_url(href, label)
            if UrlExtractor.categorize_social(real_url) != SocialNetwork.WHATSAPP:
                continue
            number = UrlExtractor.extract_whatsapp_number(real_url)
            if number and number not in seen:
                seen.add(number)
                numbers.append(number)
        return numbers
    
    def _get_info(self) -> List[str]:
        """РџРѕР»СѓС‡РµРЅРёРµ РёРЅС„РѕСЂРјР°С†РёРё СЃ РІРєР»Р°РґРєРё 'РРЅС„Рѕ'."""
        info_lines = []
        
        try:
            # РџРѕРёСЃРє СЃСЃС‹Р»РєРё РЅР° РІРєР»Р°РґРєСѓ РРЅС„Рѕ
            nav_links = WebDriverWait(self.driver, 8).until(
                EC.presence_of_all_elements_located(
                    (By.CSS_SELECTOR, 'a._2lcm958')
                )
            )
            
            info_link = None
            for link in nav_links:
                href = link.get_attribute('href') or ''
                text = (link.text or '').strip()
                if text == 'РРЅС„Рѕ' or '/tab/info' in href:
                    info_link = link
                    break
            
            if not info_link:
                return info_lines
            
            # РџРµСЂРµС…РѕРґ РЅР° РІРєР»Р°РґРєСѓ
            self.driver.execute_script(
                "arguments[0].scrollIntoView({block:'center'});", info_link
            )
            try:
                self.driver.execute_script("arguments[0].click();", info_link)
            except Exception:
                href = info_link.get_attribute('href')
                if href:
                    if href.startswith('/'):
                        href = urljoin(self.driver.current_url, href)
                    self.driver.get(href)
            
            try:
                WebDriverWait(self.driver, 5).until(EC.url_contains('/tab/info'))
            except TimeoutException:
                pass
            
            # РџР°СЂСЃРёРЅРі РёРЅС„РѕСЂРјР°С†РёРё
            info_root = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'div._8sgdp4'))
            )
            rows = info_root.find_elements(By.CSS_SELECTOR, 'div._172gbf8')
            
            for row in rows:
                # РџСЂРѕРїСѓСЃРєР°РµРј Р·Р°РіРѕР»РѕРІРєРё СЃРµРєС†РёР№
                if row.find_elements(By.CSS_SELECTOR, 'span._elk1c2r'):
                    continue
                
                line = self._extract_row_text(row)
                if line and not self.cleaner.is_parking_line(line):
                    if line not in info_lines:
                        info_lines.append(line)
        
        except TimeoutException:
            pass
        
        return info_lines
    
    def _extract_row_text(self, row) -> str:
        """РР·РІР»РµС‡РµРЅРёРµ С‚РµРєСЃС‚Р° РёР· СЃС‚СЂРѕРєРё РёРЅС„РѕСЂРјР°С†РёРё."""
        try:
            wrap = row.find_elements(By.CSS_SELECTOR, 'span._14quei')
            if wrap:
                parts = []
                for w in row.find_elements(By.CSS_SELECTOR, 'span._14quei span._wrdavn'):
                    btn = w.find_elements(
                        By.CSS_SELECTOR, 'button._1rehek, a._1rehek'
                    )
                    if btn:
                        val = self.cleaner.clean(btn[0].get_attribute('innerText'))
                    else:
                        val = self.cleaner.clean(w.get_attribute('innerText'))
                    if val:
                        parts.append(val)
                return ' '.join(parts).strip()
            
            btn = row.find_elements(By.CSS_SELECTOR, 'button._1rehek, a._1rehek')
            if btn:
                return self.cleaner.clean(btn[0].get_attribute('innerText'))
            
            return self.cleaner.clean(
                row.get_attribute('innerText') or row.text
            )
        except Exception:
            return self.cleaner.clean(row.text)


class SearchUrlParser:
    """РџР°СЂСЃРµСЂ РїРѕ РїСЂСЏРјС‹Рј СЃСЃС‹Р»РєР°Рј РЅР° РїРѕРёСЃРє 2GIS (2gis.kz Рё РґСЂ.)."""

    def __init__(
        self,
        max_pages: int = 2,
        max_firms: Optional[int] = None,
        progress: Optional[ParseProgressLog] = None,
        headless: bool = True,
        workers: int = 1,
        scrape_fields: Optional[ScrapeFields] = None,
    ):
        self.max_pages = max_pages
        self.max_firms = max_firms
        self.headless = headless
        self.workers = max(1, workers)
        self.progress = progress or ParseProgressLog()
        self.scrape_fields = scrape_fields or ScrapeFields.all()
        self.driver: Optional[webdriver.Chrome] = None
        self.scraper: Optional[FirmScraper] = None
        self._seen_firms: Set[str] = set()

    def parse(self, search_urls: List[str]) -> tuple[List[FirmData], List[str]]:
        """РЎР±РѕСЂ С„РёСЂРј СЃРѕ СЃС‚СЂР°РЅРёС† РїРѕРёСЃРєР°. Р’РѕР·РІСЂР°С‰Р°РµС‚ (РґР°РЅРЅС‹Рµ, РІСЃРµ URL РѕСЂРіР°РЅРёР·Р°С†РёР№)."""
        firms: List[FirmData] = []
        all_firm_urls: List[str] = []
        total_pages_visited = 0
        try:
            mode = "СЃРєСЂС‹С‚С‹Р№" if self.headless else "РІРёРґРёРјС‹Р№"
            self.progress.step(f"Р—Р°РїСѓСЃРєР°СЋ Р±СЂР°СѓР·РµСЂ Chrome ({mode})вЂ¦")
            if not self.headless:
                self.progress.detail(
                    "РЎРµР№С‡Р°СЃ РґРѕР»Р¶РЅРѕ РѕС‚РєСЂС‹С‚СЊСЃСЏ РѕРєРЅРѕ Chrome вЂ” РЅРµ Р·Р°РєСЂС‹РІР°Р№С‚Рµ РµРіРѕ"
                )
            self.driver = WebDriverFactory.create(headless=self.headless)
            self.scraper = FirmScraper(
                self.driver,
                progress=self.progress,
                scrape_fields=self.scrape_fields,
            )
            self.progress.done(f"Р‘СЂР°СѓР·РµСЂ РіРѕС‚РѕРІ ({mode} СЂРµР¶РёРј)")

            for search_url in search_urls:
                for page in range(1, self.max_pages + 1):
                    page_url = UrlExtractor.build_search_page_url(search_url, page)
                    self.progress.step(
                        f"РћС‚РєСЂС‹РІР°СЋ СЃС‚СЂР°РЅРёС†Сѓ РїРѕРёСЃРєР° {page}/{self.max_pages}вЂ¦"
                    )
                    total_pages_visited += 1
                    if not self._open_search_page(page_url, page, search_url):
                        self.progress.warn(
                            f"2GIS could not open page {page}; "
                            "stopping this search URL"
                        )
                        break
                    self.progress.detail("Р–РґСѓ Р·Р°РіСЂСѓР·РєСѓ СЃС‚СЂР°РЅРёС†С‹ РІ Р±СЂР°СѓР·РµСЂРµвЂ¦")
                    _wait_dom_ready(self.driver, timeout=settings.PAGE_TIMEOUT)
                    _dismiss_overlays(self.driver)
                    _dismiss_overlays(self.driver)

                    if not _wait_for_search_results(self.driver):
                        self.progress.warn(
                            "РљР°СЂС‚РѕС‡РєРё РЅРµ РїРѕСЏРІРёР»РёСЃСЊ вЂ” РїСЂРѕРєСЂСѓС‡РёРІР°СЋ СЃРїРёСЃРѕРє Рё Р¶РґСѓ РµС‰С‘вЂ¦"
                        )
                    _scroll_results_panel(self.driver)
                    _scroll_results_panel(self.driver)
                    _wait_for_search_results(self.driver, timeout=15)

                    self.progress.step(
                        f"РЎРѕР±РёСЂР°СЋ СЃСЃС‹Р»РєРё РЅР° РѕСЂРіР°РЅРёР·Р°С†РёРё (СЃС‚СЂ. {page})вЂ¦"
                    )
                    page_urls = self._collect_firm_urls_from_search(page)
                    all_firm_urls.extend(page_urls)
                    self.progress.done(
                        f"РЎС‚СЂ. {page}: РЅР°Р№РґРµРЅРѕ {len(page_urls)} РЅРѕРІС‹С… СЃСЃС‹Р»РѕРє "
                        f"(РІСЃРµРіРѕ {len(all_firm_urls)})"
                    )

            if not all_firm_urls:
                self.progress.warn(
                    "РЎСЃС‹Р»РєРё РЅРµ РЅР°Р№РґРµРЅС‹. РџСЂРѕРІРµСЂСЊС‚Рµ РёРЅС‚РµСЂРЅРµС‚, cookie-Р±Р°РЅРЅРµСЂ "
                    "РёР»Рё РѕС‚РєСЂРѕР№С‚Рµ HEADLESS=false РІ .env"
                )
                self.progress.done(
                    f"РЎС‚СЂР°РЅРёС† РїСЂРѕР№РґРµРЅРѕ: {total_pages_visited} РёР· "
                    f"{len(search_urls) * self.max_pages}"
                )
                return firms, all_firm_urls

            scrape_urls = all_firm_urls
            if self.max_firms:
                scrape_urls = all_firm_urls[: self.max_firms]

            total = len(scrape_urls)
            self.progress.step(
                f"РџР°СЂСЃРёРЅРі РєР°СЂС‚РѕС‡РµРє: {total} РёР· {len(all_firm_urls)} СЃСЃС‹Р»РѕРєвЂ¦"
            )

            if self.workers > 1 and total > 1:
                self.progress.step(
                    f"Р—Р°РїСѓСЃРєР°СЋ РїР°СЂР°Р»Р»РµР»СЊРЅС‹Р№ СЃР±РѕСЂ РєР°СЂС‚РѕС‡РµРє: {self.workers} РІРѕСЂРєРµСЂР°"
                )
                firms = self._scrape_parallel(scrape_urls)
            else:
                for idx, url in enumerate(scrape_urls, 1):
                    firm = self.scraper.scrape(url, city_name="", index=idx, total=total)
                    firms.append(firm)
                    delay = random.uniform(
                        settings.REQUEST_DELAY_MIN,
                        settings.REQUEST_DELAY_MAX
                    )
                    time.sleep(delay)
        finally:
            self.progress.done(
                f"РЎС‚СЂР°РЅРёС† РїСЂРѕР№РґРµРЅРѕ: {total_pages_visited} РёР· "
                f"{len(search_urls) * self.max_pages}"
            )
            self.progress.step("Р—Р°РєСЂС‹РІР°СЋ Р±СЂР°СѓР·РµСЂвЂ¦")
            if self.driver:
                _safe_quit_driver(self.driver)
                self.driver = None
            self.progress.done("РџР°СЂСЃРёРЅРі Р·Р°РІРµСЂС€С‘РЅ")
        return firms, all_firm_urls

    def _scrape_parallel(self, urls: List[str]) -> List[FirmData]:
        """РџР°СЂР°Р»Р»РµР»СЊРЅС‹Р№ СЃР±РѕСЂ РєР°СЂС‚РѕС‡РµРє СЂР°Р·РЅС‹РјРё РґСЂР°Р№РІРµСЂР°РјРё."""
        chunks = _split_chunks(urls, self.workers)
        firms: List[FirmData] = []

        def _worker(worker_idx: int, worker_urls: List[str]) -> List[FirmData]:
            driver = None
            out: List[FirmData] = []
            try:
                driver = WebDriverFactory.create(headless=self.headless)
                scraper = FirmScraper(
                    driver,
                    progress=self.progress,
                    scrape_fields=self.scrape_fields,
                )
                total_local = len(worker_urls)
                for idx, url in enumerate(worker_urls, 1):
                    out.append(
                        scraper.scrape(
                            url,
                            city_name="",
                            index=idx,
                            total=total_local,
                        )
                    )
                    time.sleep(
                        random.uniform(
                            settings.REQUEST_DELAY_MIN,
                            settings.REQUEST_DELAY_MAX
                        )
                    )
            finally:
                _safe_quit_driver(driver)
            self.progress.done(
                f"Р’РѕСЂРєРµСЂ {worker_idx}: РѕР±СЂР°Р±РѕС‚Р°РЅРѕ РєР°СЂС‚РѕС‡РµРє {len(out)}"
            )
            return out

        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            futures = [
                executor.submit(_worker, idx + 1, chunk)
                for idx, chunk in enumerate(chunks)
                if chunk
            ]
            for future in as_completed(futures):
                firms.extend(future.result())

        return firms

    def _open_search_page(self, page_url: str, page: int, search_url: str) -> bool:
        """Open the first search page by URL, then use 2GIS pagination links."""
        if page <= 1:
            self.driver.get(page_url)
            _wait_dom_ready(self.driver, timeout=settings.PAGE_TIMEOUT)
            self.progress.detail(f"URL requested: {page_url}")
            self.progress.detail(f"URL opened: {self.driver.current_url}")
            return True

        if self._is_expected_search_page(page):
            return True

        if self._click_pagination_link(page):
            self.progress.detail(f"Clicked pagination link for page {page}")
            self.progress.detail(f"URL opened: {self.driver.current_url}")
            return True

        # If a previous card changed the route, restore the search and try the UI link again.
        self.driver.get(UrlExtractor.build_search_page_url(search_url, 1))
        _wait_dom_ready(self.driver, timeout=settings.PAGE_TIMEOUT)
        _dismiss_overlays(self.driver)
        _wait_for_search_results(self.driver, timeout=15)
        if self._click_pagination_link(page):
            self.progress.detail(f"Clicked pagination link for page {page}")
            self.progress.detail(f"URL opened: {self.driver.current_url}")
            return True

        self.progress.warn(f"Pagination link for page {page} was not found")
        return False

    def _click_pagination_link(self, page: int) -> bool:
        href_part = f"/page/{page}"
        selectors = [
            f'a[href*="{href_part}"]',
            f'a[href$="{href_part}"]',
        ]

        for _ in range(3):
            for selector in selectors:
                try:
                    links = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for link in links:
                        if not link.is_displayed():
                            continue
                        before_url = self.driver.current_url
                        self.driver.execute_script(
                            "arguments[0].scrollIntoView({block:'center'});",
                            link,
                        )
                        time.sleep(0.2)
                        self.driver.execute_script("arguments[0].click();", link)
                        try:
                            WebDriverWait(self.driver, settings.PAGE_TIMEOUT).until(
                                lambda d: self._is_expected_search_page(page)
                                or d.current_url != before_url
                            )
                        except TimeoutException:
                            pass
                        _wait_dom_ready(self.driver, timeout=settings.PAGE_TIMEOUT)
                        return self._is_expected_search_page(page)
                except StaleElementReferenceException:
                    continue
                except Exception:
                    continue
            self._scroll_to_pagination()
        return False

    def _scroll_to_pagination(self) -> None:
        try:
            self.driver.execute_script(
                """
                const link = document.querySelector('a[href*="/page/"]');
                if (link) {
                    link.scrollIntoView({block: 'center'});
                    return;
                }
                const scrollers = Array.from(document.querySelectorAll('*'))
                    .filter(el => el.scrollHeight > el.clientHeight + 80)
                    .sort((a, b) => b.scrollHeight - a.scrollHeight);
                const el = scrollers[0] || document.scrollingElement;
                el.scrollTop = el.scrollHeight;
                """
            )
            time.sleep(0.4)
        except Exception:
            pass

    def _is_expected_search_page(self, page: int) -> bool:
        current = urlsplit(self.driver.current_url).path.rstrip("/")
        return current.endswith(f"/page/{page}")

    @staticmethod
    def _strip_map_query(url: str) -> str:
        parts = urlsplit(url)
        query = urlencode(
            [
                (key, value)
                for key, value in parse_qsl(parts.query, keep_blank_values=True)
                if key != "m"
            ],
            doseq=True,
        )
        return urlunsplit((parts.scheme, parts.netloc, parts.path, query, parts.fragment))

    def _collect_firm_urls_from_search_legacy(self, page: int) -> List[str]:
        """РЎР±РѕСЂ URL С„РёСЂРј СЃРѕ СЃС‚СЂР°РЅРёС†С‹ РїРѕРёСЃРєР°."""
        urls: List[str] = []
        anchors = self.driver.find_elements(
            By.CSS_SELECTOR, 'div._zjunba a[href*="/firm/"]'
        )
        if not anchors:
            anchors = self.driver.find_elements(
                By.CSS_SELECTOR, 'a[href*="/firm/"]'
            )

        if not anchors:
            self.progress.warn(
                f"РЎС‚СЂ. {page}: СЃСЃС‹Р»РѕРє /firm/ РЅР° СЃС‚СЂР°РЅРёС†Рµ РЅРµС‚. "
                f"URL: {self.driver.current_url}"
            )
            return urls

        self.progress.detail(f"РќР°Р№РґРµРЅРѕ СЌР»РµРјРµРЅС‚РѕРІ РЅР° СЃС‚СЂР°РЅРёС†Рµ: {len(anchors)}")

        for anchor in anchors:
            href = anchor.get_attribute('href')
            if not href:
                continue
            if href.startswith('/'):
                href = urljoin(self.driver.current_url, href)

            key = UrlExtractor.extract_firm_key(href)
            if not key or key in self._seen_firms:
                continue

            self._seen_firms.add(key)
            canonical = UrlExtractor.canonicalize_firm_url(href)
            if canonical:
                urls.append(canonical)

        return urls


    def _collect_firm_urls_from_search(self, page: int) -> List[str]:
        """Collect firm URLs from a 2GIS search page, including virtualized rows."""
        urls: List[str] = []
        total_seen_on_page = 0

        def collect_visible() -> int:
            nonlocal total_seen_on_page
            before = len(urls)
            anchors = self.driver.find_elements(
                By.CSS_SELECTOR, 'div._zjunba a[href*="/firm/"]'
            )
            if not anchors:
                anchors = self.driver.find_elements(
                    By.CSS_SELECTOR, 'a[href*="/firm/"]'
                )

            total_seen_on_page = max(total_seen_on_page, len(anchors))
            for anchor in anchors:
                href = anchor.get_attribute('href')
                if not href:
                    continue
                if href.startswith('/'):
                    href = urljoin(self.driver.current_url, href)

                key = UrlExtractor.extract_firm_key(href)
                canonical = UrlExtractor.canonicalize_firm_url(href)
                if not key or not canonical:
                    repaired = self._repair_firm_url_without_city(href)
                    if repaired:
                        key = UrlExtractor.extract_firm_key(repaired)
                        canonical = UrlExtractor.canonicalize_firm_url(repaired)

                if not key or key in self._seen_firms:
                    continue

                self._seen_firms.add(key)
                if canonical:
                    urls.append(canonical)

            return len(urls) - before

        collect_visible()
        self._scan_scrollable_results(collect_visible)

        if not urls:
            self.progress.warn(
                f"Р РЋРЎвЂљРЎР‚. {page}: РЎРѓРЎРѓРЎвЂ№Р В»Р С•Р С” /firm/ Р Р…Р В° РЎРѓРЎвЂљРЎР‚Р В°Р Р…Р С‘РЎвЂ Р Вµ Р Р…Р ВµРЎвЂљ. "
                f"URL: {self.driver.current_url}"
            )
            return urls

        self.progress.detail(
            f"DOM firm links max: {total_seen_on_page}, collected after scroll: {len(urls)}"
        )

        return urls

    def _scan_scrollable_results(self, collect_visible: Callable[[], int]) -> None:
        """Scroll the 2GIS virtualized results panel and collect links at each step."""
        try:
            panel = self.driver.execute_script(
                """
                const links = Array.from(document.querySelectorAll('a[href*="/firm/"]'));
                const candidates = [];
                for (const link of links) {
                    let el = link.parentElement;
                    while (el && el !== document.body) {
                        if (el.scrollHeight > el.clientHeight + 80) {
                            candidates.push(el);
                        }
                        el = el.parentElement;
                    }
                }
                candidates.sort((a, b) => b.scrollHeight - a.scrollHeight);
                return candidates[0] || document.scrollingElement;
                """
            )
        except Exception:
            panel = None

        if not panel:
            return

        try:
            self.driver.execute_script("arguments[0].scrollTop = 0;", panel)
            time.sleep(0.3)
            collect_visible()

            stagnant_steps = 0
            previous_position = -1
            for _ in range(40):
                metrics = self.driver.execute_script(
                    """
                    const el = arguments[0];
                    const step = Math.max(300, Math.floor(el.clientHeight * 0.85));
                    el.scrollTop = Math.min(el.scrollTop + step, el.scrollHeight);
                    return {
                        top: el.scrollTop,
                        height: el.scrollHeight,
                        client: el.clientHeight
                    };
                    """,
                    panel,
                )
                time.sleep(0.35)
                added = collect_visible()
                current_position = int(metrics.get("top", 0))
                at_bottom = (
                    current_position + int(metrics.get("client", 0))
                    >= int(metrics.get("height", 0)) - 5
                )

                if added == 0 and current_position == previous_position:
                    stagnant_steps += 1
                else:
                    stagnant_steps = 0

                if at_bottom or stagnant_steps >= 3:
                    break
                previous_position = current_position
        except Exception:
            return

    def _repair_firm_url_without_city(self, href: str) -> str:
        """Repair /firm/id links by taking the city slug from current search URL."""
        firm_id_match = re.search(r'/firm/(\d+)', href, flags=re.I)
        city_match = re.search(
            r'2gis\.(?:ru|kz|com)/([^/?#]+)/',
            self.driver.current_url,
            flags=re.I,
        )
        if not firm_id_match or not city_match:
            return ""
        city = city_match.group(1)
        if city.lower() in ('search', 'firm'):
            return ""
        return f"https://2gis.kz/{city}/firm/{firm_id_match.group(1)}"


class Parser2GIS:
    """РћСЃРЅРѕРІРЅРѕР№ РєР»Р°СЃСЃ РїР°СЂСЃРµСЂР° 2GIS."""
    
    def __init__(
        self,
        progress_callback: ProgressCallback = None,
        scrape_fields: Optional[ScrapeFields] = None,
    ):
        self.progress_callback = progress_callback
        self.scrape_fields = scrape_fields or ScrapeFields.all()
        self.driver: Optional[webdriver.Chrome] = None
        self.scraper: Optional[FirmScraper] = None
        self._cancelled = False
        self._seen_firms: Set[str] = set()
    
    def parse(self, request: ParseRequest) -> ParseResult:
        """РћСЃРЅРѕРІРЅРѕР№ РјРµС‚РѕРґ РїР°СЂСЃРёРЅРіР°."""
        # Р’Р°Р»РёРґР°С†РёСЏ
        errors = request.validate()
        if errors:
            result = ParseResult(task_id="", request=request)
            result.progress.status = TaskStatus.FAILED
            result.progress.errors = errors
            return result
        
        result = ParseResult(
            task_id=self._generate_task_id(),
            request=request
        )
        result.progress.status = TaskStatus.RUNNING
        result.progress.total_cities = len(request.cities)

        if request.export_columns:
            self.scrape_fields = ScrapeFields(request.export_columns)
        
        try:
            self._init_driver()
            query_encoded = quote(request.query)
            
            for city_idx, city_item in enumerate(request.cities):
                if self._cancelled:
                    result.progress.status = TaskStatus.CANCELLED
                    break
                
                # city_item РјРѕР¶РµС‚ Р±С‹С‚СЊ slug (РёР· Р±Р°Р·С‹) РёР»Рё РЅР°Р·РІР°РЅРёРµРј РіРѕСЂРѕРґР°
                # РџРѕР»СѓС‡Р°РµРј slug Рё РЅР°Р·РІР°РЅРёРµ
                city_slug, city_name = self._resolve_city(city_item)
                
                if not city_slug:
                    result.progress.errors.append(f"РќРµ СѓРґР°Р»РѕСЃСЊ РЅР°Р№С‚Рё РіРѕСЂРѕРґ: {city_item}")
                    continue
                
                result.progress.current_city = city_name
                result.progress.current_city_index = city_idx + 1
                self._report_progress(result.progress)
                
                firms = self._parse_city(city_slug, city_name, query_encoded, result)
                result.firms.extend(firms)
            
            if result.progress.status != TaskStatus.CANCELLED:
                result.progress.status = TaskStatus.COMPLETED
            
        except Exception as e:
            result.progress.status = TaskStatus.FAILED
            result.progress.errors.append(str(e))
        
        finally:
            self._cleanup()
        
        self._report_progress(result.progress)
        return result

    def parse_url(
        self,
        url: str,
        max_pages: int = 50,
        max_filials: int = 100,
        workers: Optional[int] = None,
        export_columns: Optional[List[str]] = None,
    ) -> ParseResult:
        """Parse firms from a pasted 2GIS firm or search URL."""
        columns = self.scrape_fields.columns
        if export_columns:
            self.scrape_fields = ScrapeFields(export_columns)
            columns = self.scrape_fields.columns
        request = ParseRequest(
            query=url,
            cities=["2gis-url"],
            export_columns=columns,
        )
        result = ParseResult(task_id=self._generate_task_id(), request=request)
        progress = result.progress
        progress.status = TaskStatus.RUNNING
        progress.total_cities = 1
        progress.current_city = self._city_hint_from_url(url)
        progress.current_city_index = 1
        progress.message = "Открываю ссылку 2ГИС"
        self._report_progress(progress)

        if not UrlExtractor.is_2gis_url(url):
            progress.status = TaskStatus.FAILED
            progress.errors.append("Вставьте корректную ссылку 2ГИС")
            self._report_progress(progress)
            return result

        try:
            self._init_driver()
            firm_urls = self._collect_firm_urls_from_url(
                url,
                max_pages,
                max_filials,
                progress,
            )
            progress.firms_total = len(firm_urls)
            progress.total_pages = max(progress.total_pages, 1)
            progress.message = f"Ссылки карточек сохранены: {len(firm_urls)}"
            self._report_progress(progress)

            if not firm_urls:
                progress.status = TaskStatus.COMPLETED
                progress.message = "Ссылки на филиалы не найдены"
                return result

            worker_count = workers if workers is not None else settings.PARSER_WORKERS
            worker_count = min(max(1, worker_count), 4, len(firm_urls))
            if worker_count > 1:
                progress.message = f"Параллельный парсинг филиалов: {worker_count} воркера"
                self._report_progress(progress)
                self._cleanup()
                result.firms.extend(
                    self._scrape_firm_urls_parallel(
                        firm_urls,
                        progress.current_city or "",
                        progress,
                        worker_count,
                    )
                )
            else:
                for index, firm_url in enumerate(firm_urls, 1):
                    if self._cancelled:
                        progress.status = TaskStatus.CANCELLED
                        break

                    progress.message = f"Парсинг филиала {index} из {len(firm_urls)}"
                    self._report_progress(progress)
                    firm = self.scraper.scrape(
                        firm_url,
                        city_name=progress.current_city or "",
                        index=index,
                        total=len(firm_urls),
                    )
                    result.firms.append(firm)
                    progress.firms_processed += 1
                    self._report_progress(progress)

                    delay = random.uniform(
                        settings.REQUEST_DELAY_MIN,
                        settings.REQUEST_DELAY_MAX,
                    )
                    time.sleep(delay)

            if progress.status != TaskStatus.CANCELLED:
                progress.status = TaskStatus.COMPLETED
                progress.message = f"Готово: обработано филиалов {len(result.firms)}"

        except Exception as e:
            progress.status = TaskStatus.FAILED
            progress.errors.append(str(e))
            progress.message = "Парсинг завершился с ошибкой"
        finally:
            self._cleanup()

        self._report_progress(progress)
        return result

    def _scrape_firm_urls_parallel(
        self,
        firm_urls: List[str],
        city_name: str,
        progress: ParseProgress,
        workers: int,
    ) -> List[FirmData]:
        indexed_urls = list(enumerate(firm_urls, 1))
        chunks = _split_chunks(indexed_urls, workers)
        progress_lock = Lock()
        driver_start_lock = Lock()
        indexed_firms: List[tuple[int, FirmData]] = []
        failed_urls: List[tuple[int, str]] = []
        total = len(firm_urls)

        def _create_driver():
            # undetected_chromedriver is unstable when several Chrome instances
            # are created at the exact same moment on Windows.
            with driver_start_lock:
                driver = WebDriverFactory.create()
                time.sleep(0.7)
                return driver

        def _worker(worker_index: int, urls_chunk: List[tuple[int, str]]) -> List[tuple[int, FirmData]]:
            driver = None
            out: List[tuple[int, FirmData]] = []
            try:
                driver = _create_driver()
                scraper = FirmScraper(driver, scrape_fields=self.scrape_fields)
                for index, firm_url in urls_chunk:
                    if self._cancelled:
                        break

                    with progress_lock:
                        progress.message = f"Воркер {worker_index}: филиал {index} из {total}"
                        self._report_progress(progress)

                    firm = None
                    for attempt in range(2):
                        try:
                            firm = scraper.scrape(
                                firm_url,
                                city_name=city_name,
                                index=index,
                                total=total,
                            )
                            break
                        except Exception:
                            _safe_quit_driver(driver)
                            driver = _create_driver()
                            scraper = FirmScraper(driver, scrape_fields=self.scrape_fields)

                    if firm is None:
                        failed_urls.append((index, firm_url))
                    else:
                        out.append((index, firm))

                    with progress_lock:
                        if firm is not None:
                            progress.firms_processed += 1
                        self._report_progress(progress)

                    time.sleep(
                        random.uniform(
                            settings.REQUEST_DELAY_MIN,
                            settings.REQUEST_DELAY_MAX,
                        )
                    )
            except Exception as exc:
                failed_urls.extend(urls_chunk)
                with progress_lock:
                    progress.errors.append(f"Воркер {worker_index}: {exc}")
            finally:
                _safe_quit_driver(driver)
            return out

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [
                executor.submit(_worker, worker_index + 1, chunk)
                for worker_index, chunk in enumerate(chunks)
                if chunk
            ]
            for future in as_completed(futures):
                try:
                    indexed_firms.extend(future.result())
                except Exception as exc:
                    progress.errors.append(str(exc))

        completed = {index for index, _ in indexed_firms}
        missing_urls = [
            (index, firm_url)
            for index, firm_url in indexed_urls
            if index not in completed
        ]
        if missing_urls:
            progress.message = f"Добираю карточки после сбоя воркера: {len(missing_urls)}"
            self._report_progress(progress)
            indexed_firms.extend(
                self._scrape_firm_urls_fallback(missing_urls, city_name, progress)
            )

        indexed_firms.sort(key=lambda item: item[0])
        return [firm for _, firm in indexed_firms]

    def _scrape_firm_urls_fallback(
        self,
        indexed_urls: List[tuple[int, str]],
        city_name: str,
        progress: ParseProgress,
    ) -> List[tuple[int, FirmData]]:
        driver = None
        out: List[tuple[int, FirmData]] = []
        total = progress.firms_total or len(indexed_urls)
        try:
            driver = WebDriverFactory.create()
            scraper = FirmScraper(driver, scrape_fields=self.scrape_fields)
            for index, firm_url in indexed_urls:
                if self._cancelled:
                    break
                progress.message = f"Повторный проход: филиал {index} из {total}"
                self._report_progress(progress)
                firm = scraper.scrape(
                    firm_url,
                    city_name=city_name,
                    index=index,
                    total=total,
                )
                out.append((index, firm))
                progress.firms_processed += 1
                self._report_progress(progress)
        finally:
            _safe_quit_driver(driver)
        return out

    def _collect_firm_urls_from_url(
        self,
        url: str,
        max_pages: int,
        max_filials: int,
        progress: ParseProgress,
    ) -> List[str]:
        """Collect firm URLs from a 2GIS firm card or search/list URL."""
        direct_firm_url = UrlExtractor.canonicalize_firm_url(url)
        collector = SearchUrlParser(max_pages=max_pages)
        collector.driver = self.driver
        collector._seen_firms = self._seen_firms

        urls: List[str] = []
        if direct_firm_url:
            key = UrlExtractor.extract_firm_key(direct_firm_url)
            if key:
                self._seen_firms.add(key)
            urls.append(direct_firm_url)

        empty_pages = 0
        for page in range(1, max_pages + 1):
            if self._cancelled:
                break

            page_url = url if direct_firm_url else UrlExtractor.build_search_page_url(url, page)
            progress.current_page = page
            progress.total_pages = max(progress.total_pages, page)
            progress.message = f"РЎРєР°РЅРёСЂСѓСЋ СЃС‚СЂР°РЅРёС†Сѓ 2Р“РРЎ: {page}"
            self._report_progress(progress)

            try:
                self.driver.get(page_url)
            except WebDriverException:
                self._restart_driver()
                collector.driver = self.driver
                self.driver.get(page_url)
            _wait_dom_ready(self.driver, timeout=settings.PAGE_TIMEOUT)
            _dismiss_overlays(self.driver)
            _wait_for_search_results(self.driver, timeout=15)
            _scroll_results_panel(self.driver)

            page_urls = collector._collect_firm_urls_from_search(page)
            if page_urls:
                urls.extend(page_urls)
                empty_pages = 0
            else:
                empty_pages += 1

            if direct_firm_url or empty_pages >= 2 or len(urls) >= max_filials:
                break

        seen = set()
        unique_urls = []
        for firm_url in urls:
            key = UrlExtractor.extract_firm_key(firm_url) or firm_url
            if key in seen:
                continue
            seen.add(key)
            unique_urls.append(firm_url)
            if len(unique_urls) >= max_filials:
                break
        return unique_urls

    @staticmethod
    def _city_hint_from_url(url: str) -> str:
        match = re.search(r'2gis\.(?:ru|kz|com)/([^/?#]+)', url, flags=re.I)
        if not match:
            return ""
        city_slug = match.group(1)
        return CITIES_DATABASE.get(city_slug, city_slug)
    
    def _resolve_city(self, city_item: str) -> tuple:
        """
        РћРїСЂРµРґРµР»РµРЅРёРµ slug Рё РЅР°Р·РІР°РЅРёСЏ РіРѕСЂРѕРґР°.
        Р’РѕР·РІСЂР°С‰Р°РµС‚ (slug, name) РёР»Рё (None, None) РµСЃР»Рё РЅРµ РЅР°Р№РґРµРЅРѕ.
        """
        # РџСЂРѕРІРµСЂСЏРµРј, СЌС‚Рѕ slug РёР»Рё РЅР°Р·РІР°РЅРёРµ
        if city_item in CITIES_DATABASE:
            # Р­С‚Рѕ slug РёР· Р±Р°Р·С‹
            return city_item, CITIES_DATABASE[city_item]
        
        # РџСЂРѕРІРµСЂСЏРµРј, СЌС‚Рѕ РЅР°Р·РІР°РЅРёРµ РёР· Р±Р°Р·С‹
        for slug, name in CITIES_DATABASE.items():
            if name.lower() == city_item.lower():
                return slug, name
        
        # РС‰РµРј С‡РµСЂРµР· Selenium
        slug = CitySlugResolver.get_city_slug(city_item)
        if slug:
            return slug, city_item
        
        return None, None
    
    def cancel(self) -> None:
        """РћС‚РјРµРЅР° РїР°СЂСЃРёРЅРіР°."""
        self._cancelled = True
    
    def _parse_city(
        self,
        city_slug: str,
        city_name: str,
        query_encoded: str,
        result: ParseResult
    ) -> List[FirmData]:
        """РџР°СЂСЃРёРЅРі РѕРґРЅРѕРіРѕ РіРѕСЂРѕРґР°."""
        firms = []
        
        # РџРѕР»СѓС‡Р°РµРј РѕР±С‰РµРµ РєРѕР»РёС‡РµСЃС‚РІРѕ СЂРµР·СѓР»СЊС‚Р°С‚РѕРІ
        first_url = SEARCH_URL_TEMPLATE.format(
            city=city_slug, query=query_encoded, page=1
        )
        self.driver.get(first_url)
        
        total = self._get_total_count()
        if not total:
            result.progress.message = f"РќРµС‚ СЂРµР·СѓР»СЊС‚Р°С‚РѕРІ РІ {city_name}"
            self._report_progress(result.progress)
            return firms
        
        total_pages = math.ceil(total / settings.PAGE_SIZE)
        result.progress.total_pages = total_pages
        result.progress.firms_total += total
        
        if settings.DEBUG:
            print(f"Р“РѕСЂРѕРґ {city_name}: {total} СЂРµР·СѓР»СЊС‚Р°С‚РѕРІ, {total_pages} СЃС‚СЂР°РЅРёС†")
        
        # РЎС‡С‘С‚С‡РёРє СЃС‚СЂР°РЅРёС† РїРѕРґСЂСЏРґ СЃ РґСѓР±Р»РёРєР°С‚Р°РјРё
        consecutive_duplicate_pages = 0
        
        for page in range(1, total_pages + 1):
            if self._cancelled:
                break
            
            # РџСЂРѕРІРµСЂРєР° РЅР° РїСЂРµРІС‹С€РµРЅРёРµ Р»РёРјРёС‚Р° РґСѓР±Р»РёСЂСѓСЋС‰РёС… СЃС‚СЂР°РЅРёС†
            if consecutive_duplicate_pages >= MAX_CONSECUTIVE_DUPLICATE_PAGES:
                result.progress.message = f"РћСЃС‚Р°РЅРѕРІРєР° РІ {city_name}: {MAX_CONSECUTIVE_DUPLICATE_PAGES} СЃС‚СЂР°РЅРёС† РїРѕРґСЂСЏРґ СЃ СѓР¶Рµ СЃРѕР±СЂР°РЅРЅС‹РјРё РєРѕРјРїР°РЅРёСЏРјРё"
                self._report_progress(result.progress)
                if settings.DEBUG:
                    print(f"Р“РѕСЂРѕРґ {city_name}: РѕСЃС‚Р°РЅРѕРІРєР° РїРѕСЃР»Рµ {MAX_CONSECUTIVE_DUPLICATE_PAGES} СЃС‚СЂР°РЅРёС† СЃ РґСѓР±Р»РёРєР°С‚Р°РјРё")
                break
            
            result.progress.current_page = page
            self._report_progress(result.progress)
            
            page_url = SEARCH_URL_TEMPLATE.format(
                city=city_slug, query=query_encoded, page=page
            )
            self.driver.get(page_url)
            
            # РЎРѕР±РёСЂР°РµРј URL С„РёСЂРј Рё РїСЂРѕРІРµСЂСЏРµРј, РµСЃС‚СЊ Р»Рё РЅРѕРІС‹Рµ
            firm_urls = self._collect_firm_urls(city_slug)
            
            # Р•СЃР»Рё РЅР° СЃС‚СЂР°РЅРёС†Рµ РЅРµ РЅР°С€Р»Рё РЅРѕРІС‹С… С„РёСЂРј - СѓРІРµР»РёС‡РёРІР°РµРј СЃС‡С‘С‚С‡РёРє
            if len(firm_urls) == 0:
                consecutive_duplicate_pages += 1
                if settings.DEBUG:
                    print(f"РЎС‚СЂР°РЅРёС†Р° {page}: РІСЃРµ С„РёСЂРјС‹ СѓР¶Рµ СЃРѕР±СЂР°РЅС‹ (РїРѕРґСЂСЏРґ: {consecutive_duplicate_pages})")
            else:
                # РЎР±СЂР°СЃС‹РІР°РµРј СЃС‡С‘С‚С‡РёРє, РµСЃР»Рё РЅР°С€Р»Рё РЅРѕРІС‹Рµ С„РёСЂРјС‹
                consecutive_duplicate_pages = 0
            
            for url in firm_urls:
                if self._cancelled:
                    break
                
                firm = self.scraper.scrape(url, city_name)
                firms.append(firm)
                result.progress.firms_processed += 1
                self._report_progress(result.progress)
                
                # Р—Р°РґРµСЂР¶РєР° РјРµР¶РґСѓ Р·Р°РїСЂРѕСЃР°РјРё
                delay = random.uniform(
                    settings.REQUEST_DELAY_MIN,
                    settings.REQUEST_DELAY_MAX
                )
                time.sleep(delay)
        
        return firms
    
    def _collect_firm_urls(self, city_slug: str) -> List[str]:
        """РЎР±РѕСЂ URL С„РёСЂРј СЃРѕ СЃС‚СЂР°РЅРёС†С‹ РїРѕРёСЃРєР°."""
        urls = []
        
        try:
            WebDriverWait(self.driver, settings.PAGE_TIMEOUT).until(
                EC.presence_of_all_elements_located(
                    (By.CSS_SELECTOR, f'a[href*="/{city_slug}/firm/"]')
                )
            )
        except TimeoutException:
            return urls
        
        anchors = self.driver.find_elements(
            By.CSS_SELECTOR, f'a[href*="/{city_slug}/firm/"]'
        )
        
        for anchor in anchors:
            href = anchor.get_attribute('href')
            if not href:
                continue
            
            key = UrlExtractor.extract_firm_key(href)
            if not key or key in self._seen_firms:
                continue
            
            self._seen_firms.add(key)
            canonical = UrlExtractor.canonicalize_firm_url(href)
            if canonical:
                urls.append(canonical)
        
        return urls
    
    def _get_total_count(self) -> Optional[int]:
        """РџРѕР»СѓС‡РµРЅРёРµ РѕР±С‰РµРіРѕ РєРѕР»РёС‡РµСЃС‚РІР° СЂРµР·СѓР»СЊС‚Р°С‚РѕРІ."""
        try:
            element = WebDriverWait(self.driver, 15).until(
                EC.visibility_of_element_located(
                    (By.CSS_SELECTOR, 'span._1xhlznaa')
                )
            )
            text = element.text.replace('\xa0', ' ')
            return int(re.sub(r'\D+', '', text))
        except Exception:
            return None
    
    def _init_driver(self) -> None:
        """РРЅРёС†РёР°Р»РёР·Р°С†РёСЏ WebDriver."""
        self.driver = WebDriverFactory.create()
        self.scraper = FirmScraper(
            self.driver,
            scrape_fields=self.scrape_fields,
        )
    
    def _cleanup(self) -> None:
        """РћС‡РёСЃС‚РєР° СЂРµСЃСѓСЂСЃРѕРІ."""
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None
            self.scraper = None

    def _restart_driver(self) -> None:
        self._cleanup()
        self._init_driver()
    
    def _report_progress(self, progress: ParseProgress) -> None:
        """РћС‚РїСЂР°РІРєР° РїСЂРѕРіСЂРµСЃСЃР° С‡РµСЂРµР· callback."""
        if self.progress_callback:
            self.progress_callback(progress)
    
    @staticmethod
    def _generate_task_id() -> str:
        """Р“РµРЅРµСЂР°С†РёСЏ ID Р·Р°РґР°С‡Рё."""
        return str(uuid.uuid4())[:8]
