"""Fast sitemap checker - uses robots.txt + HTTP HEAD checks."""
import logging
from typing import Optional
import aiohttp
from models import SitemapAnalysis, RobotsAnalysis
from config import HTTP_TIMEOUT


logger = logging.getLogger(__name__)


class SitemapFastChecker:
    """
    Ultra-fast sitemap existence checker.
    
    Uses robots.txt data + HTTP HEAD requests instead of USP parsing.
    Falls back to common paths if robots.txt has no sitemaps.
    """
    
    # Common sitemap paths (fallback if robots.txt has no sitemaps)
    COMMON_PATHS = [
        '/sitemap.xml',
        '/sitemap_index.xml',
        '/sitemap-index.xml',
        '/sitemap.xml.gz',
        '/sitemap_index.xml.gz',
    ]
    
    def __init__(self):
        """Initialize fast sitemap checker."""
        pass
    
    async def check_from_robots(
        self,
        base_url: str,
        robots: Optional[RobotsAnalysis]
    ) -> SitemapAnalysis:
        """
        Fast sitemap check using robots.txt data + HTTP verification.
        
        Strategy:
        1. If robots.txt has sitemaps → verify with HTTP HEAD
        2. Otherwise → try common sitemap paths
        3. Return immediately on first found
        
        Args:
            base_url: Base URL (e.g., "https://example.com/")
            robots: Already parsed RobotsAnalysis (or None)
            
        Returns:
            SitemapAnalysis with existence check only (no URL parsing)
        """
        timeout_cfg = aiohttp.ClientTimeout(total=HTTP_TIMEOUT)
        connector = aiohttp.TCPConnector(ssl=False)  # Ignore SSL certificate errors
        
        async with aiohttp.ClientSession(timeout=timeout_cfg, connector=connector) as session:
            # Strategy 1: Check sitemaps from robots.txt
            if robots and robots.exists and robots.sitemaps:
                sitemap_urls = robots.sitemaps
                
                # Verify first sitemap exists
                if await self._verify_sitemap(session, sitemap_urls[0]):
                    return SitemapAnalysis(
                        discovered_via="robots",
                        url=sitemap_urls[0],
                        http_status=200,
                        exists=True,
                        status="ok",
                        is_index=len(sitemap_urls) > 1,
                        child_sitemaps=sitemap_urls if len(sitemap_urls) > 1 else None,
                        urls=None,
                        total_url_count=0,
                        format_type="xml",
                        has_priorities=None,
                        has_changefreq=None,
                        has_lastmod=None,
                    )
            
            # Strategy 2: Try common sitemap paths (fallback)
            for path in self.COMMON_PATHS:
                sitemap_url = f"{base_url.rstrip('/')}{path}"
                if await self._verify_sitemap(session, sitemap_url):
                    return SitemapAnalysis(
                        discovered_via="common_path",
                        url=sitemap_url,
                        http_status=200,
                        exists=True,
                        status="ok",
                        is_index='index' in path.lower(),
                        child_sitemaps=None,
                        urls=None,
                        total_url_count=0,
                        format_type="xml",
                        has_priorities=None,
                        has_changefreq=None,
                        has_lastmod=None,
                    )
        
        # No sitemap found
        return SitemapAnalysis(
            discovered_via="none",
            url=None,
            http_status=None,
            exists=False,
            status="not_found",
        )
    
    async def _verify_sitemap(self, session: aiohttp.ClientSession, url: str) -> bool:
        """Quickly verify sitemap URL exists with HEAD request."""
        try:
            async with session.head(url, allow_redirects=True, timeout=aiohttp.ClientTimeout(total=HTTP_TIMEOUT)) as response:
                return response.status == 200
        except Exception as e:
            logger.error(f"HEAD request failed for {url}: {type(e).__name__}")
        
        # Fallback to GET if HEAD fails (some servers don't support HEAD)
        try:
            async with session.get(url, allow_redirects=True, timeout=aiohttp.ClientTimeout(total=HTTP_TIMEOUT)) as response:
                return response.status == 200
        except Exception as e:
            logger.error(f"GET request failed for {url}: {type(e).__name__}")
            return False