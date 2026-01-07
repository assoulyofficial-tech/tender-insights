"""
Tender AI Platform - Headless Scraper Service
Refactored from tkinter GUI version to headless, memory-only operation
"""

import asyncio
import io
import zipfile
from datetime import datetime, timedelta
from typing import List, Tuple, Dict, Optional, Callable
from dataclasses import dataclass, field
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
from loguru import logger

from app.core.config import settings


@dataclass
class ScraperProgress:
    """Progress tracking for scraper operations"""
    phase: str = "Initializing"
    total: int = 0
    downloaded: int = 0
    failed: int = 0
    elapsed_seconds: float = 0
    logs: List[Dict] = field(default_factory=list)
    is_running: bool = False
    
    def log(self, level: str, message: str):
        """Add log entry"""
        self.logs.append({
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "level": level,
            "message": message
        })
        # Also log to console
        getattr(logger, level)(message)


@dataclass
class DownloadedTender:
    """In-memory tender download result"""
    index: int
    url: str
    success: bool
    error: str = ""
    # In-memory ZIP content
    zip_bytes: Optional[bytes] = None
    suggested_filename: str = ""
    
    def get_files(self) -> Dict[str, io.BytesIO]:
        """Extract files from ZIP to memory"""
        if not self.zip_bytes:
            return {}
        
        files = {}
        try:
            with zipfile.ZipFile(io.BytesIO(self.zip_bytes), 'r') as zf:
                for name in zf.namelist():
                    # Skip directories
                    if name.endswith('/'):
                        continue
                    files[name] = io.BytesIO(zf.read(name))
        except Exception as e:
            logger.error(f"Failed to extract ZIP: {e}")
        
        return files


class TenderScraper:
    """
    Headless tender scraper for marchespublics.gov.ma
    All downloads are kept in memory (io.BytesIO)
    """
    
    def __init__(
        self,
        on_progress: Optional[Callable[[ScraperProgress], None]] = None
    ):
        self.progress = ScraperProgress()
        self.on_progress = on_progress
        self._stop_requested = False
        
    def _update_progress(self):
        """Notify progress listeners"""
        if self.on_progress:
            self.on_progress(self.progress)
    
    def stop(self):
        """Request graceful stop"""
        self._stop_requested = True
        self.progress.log("warning", "Stop requested...")
        
    async def collect_tender_links(
        self, 
        page, 
        start_date: str, 
        end_date: Optional[str] = None
    ) -> List[str]:
        """
        Navigate to search page and collect tender URLs
        
        Args:
            page: Playwright page instance
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format (defaults to start_date)
        
        Returns:
            List of tender URLs
        """
        # Use same date if end_date not provided
        if not end_date:
            end_date = start_date
            
        # Convert date format (YYYY-MM-DD to DD/MM/YYYY)
        def format_date(date_str: str) -> str:
            parts = date_str.split('-')
            return f"{parts[2]}/{parts[1]}/{parts[0]}"
        
        formatted_start = format_date(start_date)
        formatted_end = format_date(end_date)
        
        self.progress.log("info", f"Date de mise en ligne: {formatted_start} → {formatted_end}")
        self.progress.log("info", "Category: Fournitures (2)")
        
        # Navigate to homepage
        await page.goto(settings.TARGET_HOMEPAGE)
        
        # Click search tab
        await page.click('text=Consultations en cours')
        
        # Set category filter
        await page.select_option(
            '#ctl0_CONTENU_PAGE_AdvancedSearch_categorie', 
            value=settings.CATEGORY_FILTER
        )
        
        # Set date range (start and end dates)
        section_locator = page.locator('text="Date de mise en ligne :"').locator('..')
        await section_locator.locator('input').nth(0).fill(formatted_start)
        await section_locator.locator('input').nth(1).fill(formatted_end)
        
        # Clear deadline date fields
        section_limite = page.locator('text="Date limite de remise des plis :"').locator('..')
        for i in range(2):
            input_field = section_limite.locator('input').nth(i)
            await input_field.click()
            await page.keyboard.press('Control+A')
            await page.keyboard.press('Delete')
        
        # Execute search
        await page.locator('input[title="Lancer la recherche"]').nth(0).click()
        await page.wait_for_load_state("networkidle")
        
        # Set page size to 500
        await page.select_option(
            '#ctl0_CONTENU_PAGE_resultSearch_listePageSizeTop', 
            value="500"
        )
        
        # Wait for results
        try:
            await page.wait_for_selector(
                "a[href*='EntrepriseDetailConsultation']", 
                timeout=20000
            )
        except PlaywrightTimeout:
            self.progress.log("warning", "No tenders found for this date")
            return []
        
        # Extract all tender links
        all_links = await page.eval_on_selector_all(
            "a", 
            "els => els.map(el => el.href)"
        )
        
        # Filter and deduplicate
        tender_links = list(set(
            link for link in all_links 
            if link and link.startswith(settings.TARGET_LINK_PREFIX)
        ))
        
        self.progress.log("success", f"Found {len(tender_links)} tender links")
        return tender_links
    
    async def download_single_tender(
        self,
        context,
        tender_url: str,
        idx: int,
        semaphore: asyncio.Semaphore
    ) -> DownloadedTender:
        """
        Download a single tender to memory
        
        Returns:
            DownloadedTender with ZIP bytes in memory
        """
        async with semaphore:
            if self._stop_requested:
                return DownloadedTender(idx, tender_url, False, "Stopped by user")
            
            tender_page = None
            try:
                tender_page = await context.new_page()
                
                # Navigate to tender page
                await tender_page.goto(
                    tender_url, 
                    timeout=settings.SCRAPER_TIMEOUT_PAGE
                )
                
                # Click download button
                await tender_page.click(
                    'a[id="ctl0_CONTENU_PAGE_linkDownloadDce"]',
                    timeout=settings.SCRAPER_TIMEOUT_PAGE // 2
                )
                
                # Wait for form
                await tender_page.wait_for_selector(
                    '#ctl0_CONTENU_PAGE_EntrepriseFormulaireDemande_nom',
                    timeout=settings.SCRAPER_TIMEOUT_PAGE // 2
                )
                
                # Fill form
                await tender_page.check(
                    '#ctl0_CONTENU_PAGE_EntrepriseFormulaireDemande_accepterConditions'
                )
                await tender_page.fill(
                    '#ctl0_CONTENU_PAGE_EntrepriseFormulaireDemande_nom',
                    settings.FORM_NOM
                )
                await tender_page.fill(
                    '#ctl0_CONTENU_PAGE_EntrepriseFormulaireDemande_prenom',
                    settings.FORM_PRENOM
                )
                await tender_page.fill(
                    '#ctl0_CONTENU_PAGE_EntrepriseFormulaireDemande_email',
                    settings.FORM_EMAIL
                )
                
                # Submit form
                await tender_page.click('#ctl0_CONTENU_PAGE_validateButton')
                
                # Wait for download button
                await tender_page.wait_for_selector(
                    '#ctl0_CONTENU_PAGE_EntrepriseDownloadDce_completeDownload',
                    timeout=settings.SCRAPER_TIMEOUT_PAGE // 2
                )
                
                # Trigger download and capture to memory
                async with tender_page.expect_download(
                    timeout=settings.SCRAPER_TIMEOUT_DOWNLOAD
                ) as download_info:
                    await tender_page.click(
                        '#ctl0_CONTENU_PAGE_EntrepriseDownloadDce_completeDownload'
                    )
                
                download = await download_info.value
                
                # Read download to memory (NO DISK WRITE)
                # Playwright requires saving to get bytes, so we use a temp approach
                # that reads immediately into memory
                path = await download.path()
                if path:
                    with open(path, 'rb') as f:
                        zip_bytes = f.read()
                else:
                    # Fallback: stream directly
                    zip_bytes = await download.read_bytes() if hasattr(download, 'read_bytes') else None
                
                self.progress.downloaded += 1
                self.progress.log(
                    "success", 
                    f"Downloaded: tender_{idx}_{download.suggested_filename[:30]}"
                )
                self._update_progress()
                
                return DownloadedTender(
                    index=idx,
                    url=tender_url,
                    success=True,
                    zip_bytes=zip_bytes,
                    suggested_filename=download.suggested_filename
                )
                
            except PlaywrightTimeout as e:
                self.progress.failed += 1
                self.progress.log("error", f"Timeout on tender #{idx}")
                self._update_progress()
                return DownloadedTender(idx, tender_url, False, f"Timeout: {str(e)[:100]}")
                
            except Exception as e:
                self.progress.failed += 1
                self.progress.log("error", f"Failed tender #{idx}: {type(e).__name__}")
                self._update_progress()
                return DownloadedTender(idx, tender_url, False, f"{type(e).__name__}: {str(e)[:100]}")
                
            finally:
                if tender_page:
                    await tender_page.close()
    
    async def run(
        self, 
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[DownloadedTender]:
        """
        Execute full scraping run
        
        Args:
            start_date: Start date to scrape (YYYY-MM-DD). Defaults to yesterday.
            end_date: End date to scrape (YYYY-MM-DD). Defaults to start_date.
        
        Returns:
            List of DownloadedTender objects with ZIP bytes in memory
        """
        self._stop_requested = False
        self.progress = ScraperProgress(is_running=True)
        
        # Default to yesterday
        if not start_date:
            yesterday = datetime.today() - timedelta(days=1)
            start_date = yesterday.strftime('%Y-%m-%d')
        
        # Default end_date to start_date (single day)
        if not end_date:
            end_date = start_date
        
        self.progress.log("info", "=" * 50)
        self.progress.log("info", f"Starting scraper")
        self.progress.log("info", f"Date range: {start_date} → {end_date}")
        self.progress.log("info", "=" * 50)
        
        start_time = datetime.now()
        results: List[DownloadedTender] = []
        
        async with async_playwright() as p:
            # Phase 1: Browser init
            self.progress.phase = "Launching browser"
            self._update_progress()
            
            browser = await p.chromium.launch(headless=settings.SCRAPER_HEADLESS)
            context = await browser.new_context(accept_downloads=True)
            self.progress.log("success", "Browser ready (headless)")
            
            try:
                # Phase 2: Collect links
                self.progress.phase = "Collecting tender links"
                self._update_progress()
                
                page = await context.new_page()
                tender_links = await self.collect_tender_links(page, start_date, end_date)
                await page.close()
                
                self.progress.total = len(tender_links)
                self._update_progress()
                
                if not tender_links:
                    self.progress.log("warning", "No tenders found")
                    return []
                
                # Phase 3: Download tenders
                self.progress.phase = f"Downloading {len(tender_links)} tenders"
                self.progress.log("info", f"Using {settings.SCRAPER_MAX_CONCURRENT} concurrent workers")
                self._update_progress()
                
                semaphore = asyncio.Semaphore(settings.SCRAPER_MAX_CONCURRENT)
                
                # Create download tasks
                tasks = [
                    self.download_single_tender(context, url, idx, semaphore)
                    for idx, url in enumerate(tender_links, 1)
                ]
                
                # Execute with gather
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Filter out exceptions
                results = [
                    r for r in results 
                    if isinstance(r, DownloadedTender)
                ]
                
            finally:
                await browser.close()
        
        # Finalize
        elapsed = (datetime.now() - start_time).total_seconds()
        self.progress.elapsed_seconds = elapsed
        self.progress.phase = "Completed"
        self.progress.is_running = False
        
        success_count = sum(1 for r in results if r.success)
        fail_count = sum(1 for r in results if not r.success)
        
        self.progress.log("info", "=" * 50)
        self.progress.log("success", f"Downloaded: {success_count}/{len(tender_links)}")
        self.progress.log("error" if fail_count else "success", f"Failed: {fail_count}")
        self.progress.log("info", f"Time: {elapsed:.1f}s")
        self.progress.log("info", "=" * 50)
        
        self._update_progress()
        
        return results
