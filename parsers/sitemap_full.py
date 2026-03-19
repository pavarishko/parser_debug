"""Sitemap parser using Ultimate Sitemap Parser (USP) library."""
import logging
import contextlib
import io
from typing import Optional, Tuple, List
import aiohttp
from urllib.parse import urlparse
from models import SitemapURL, SitemapAnalysis
from utils import normalize_url, normalize_domain
from config import HTTP_TIMEOUT, MAX_SITEMAP_URLS

logger = logging.getLogger(__name__)


class SitemapParser:
    """Parse and analyze sitemaps using aio-ultimate-sitemap-parser."""
    
    def __init__(self, max_urls: int = MAX_SITEMAP_URLS, max_concurrent: int = 20):
        """
        Initialize sitemap parser.
        
        Args:
            max_urls: Maximum URLs to extract from sitemaps
            max_concurrent: Maximum concurrent sitemap downloads
        """
        self.max_urls = max_urls
        self.max_concurrent = max_concurrent
    
    async def _try_local_sitemap(self, domain: str, session: aiohttp.ClientSession) -> Optional[str]:
        """
        Try to fetch sitemap from common local paths on the domain.
        
        Args:
            domain: Domain to check
            session: aiohttp session
            
        Returns:
            Sitemap URL if found, None otherwise
        """
        logger.info(f"🔍 STEP 1: Trying local sitemap paths for {domain}")
        
        common_paths = [
            f"https://{domain}/sitemap.xml",
            f"https://{domain}/sitemap_index.xml",
            f"https://{domain}/sitemap1.xml",
            f"https://{domain}/sitemap/sitemap.xml",
        ]
        
        for sitemap_url in common_paths:
            try:
                logger.info(f"  → Checking {sitemap_url}...")
                # Try HEAD first
                async with session.head(sitemap_url, allow_redirects=True) as response:
                    if response.status == 200:
                        logger.info(f"  ✅ Found accessible sitemap at {sitemap_url}")
                        return str(response.url)
                    elif response.status == 405: # Method Not Allowed
                        logger.info(f"  ⚠️ HEAD not allowed for {sitemap_url}, trying GET...")
                        async with session.get(sitemap_url, allow_redirects=True) as get_response:
                            if get_response.status == 200:
                                logger.info(f"  ✅ Found accessible sitemap at {sitemap_url} (via GET)")
                                return str(get_response.url)
            except Exception as e:
                logger.debug(f"  ❌ Failed to check {sitemap_url}: {e}")
                continue
        
        return None
    
    async def _get_sitemap_from_robots(self, domain: str, session: aiohttp.ClientSession) -> Optional[str]:
        """Fetch robots.txt and extract Sitemap URL."""
        logger.info(f"🔍 STEP 2: Checking robots.txt for {domain}")
        robots_url = f"https://{domain}/robots.txt"
        try:
            async with session.get(robots_url) as response:
                if response.status == 200:
                    text = await response.text()
                    for line in text.splitlines():
                        if line.lower().startswith('sitemap:'):
                            url = line.split(':', 1)[1].strip()
                            logger.info(f"  ✅ Found sitemap in robots.txt: {url}")
                            return url
        except Exception as e:
            logger.warning(f"Failed to fetch/parse robots.txt for {domain}: {e}")
        return None

    async def _fetch_and_parse_sitemap_parallel(self, url: str, session: aiohttp.ClientSession, visited: set = None, max_concurrent: int = None) -> List[SitemapURL]:
        """Fetch and parse sitemaps in parallel using asyncio tasks."""
        if visited is None:
            visited = set()
        
        if url in visited:
            return []
        visited.add(url)
        
        # Use instance max_concurrent if not provided
        if max_concurrent is None:
            max_concurrent = self.max_concurrent
        
        logger.info(f"  → Fetching sitemap {url}...")
        print(f"    [Downloading] {url}...", end='\r', flush=True)
        urls = []
        try:
            # Implement simple retry logic for 5xx errors
            for attempt in range(3):
                try:
                    async with session.get(url) as response:
                        if response.status == 200:
                            # Handle GZIP content manually if needed
                            content_bytes = await response.read()
                            
                            # Check for GZIP magic bytes (0x1f 0x8b)
                            if content_bytes.startswith(b'\x1f\x8b'):
                                import gzip
                                try:
                                    content_str = gzip.decompress(content_bytes).decode('utf-8', errors='replace')
                                except Exception as e:
                                    logger.warning(f"  ❌ Failed to decompress GZIP content from {url}: {e}")
                                    return []
                            else:
                                # Try to decode as text
                                try:
                                    content_str = content_bytes.decode('utf-8', errors='replace')
                                except Exception as e:
                                    logger.warning(f"  ❌ Failed to decode content from {url}: {e}")
                                    return []
                            
                            from usp.tree import sitemap_from_str
                            
                            # Debug content
                            logger.info(f"    Content preview for {url}: {content_str[:100]}...")

                            # Parse content
                            try:
                                sitemap = sitemap_from_str(content_str)
                            except Exception as e:
                                logger.warning(f"  ❌ USP failed to parse content from {url}: {e}")
                                return []
                            
                            if not sitemap:
                                logger.warning(f"  ❌ USP returned None for {url}")
                                return []
                            
                            # If it's an index sitemap, process children in parallel
                            if hasattr(sitemap, 'sub_sitemaps') and sitemap.sub_sitemaps:
                                logger.info(f"  ℹ️ Found index sitemap with {len(sitemap.sub_sitemaps)} children")
                                
                                # Filter valid sub-sitemaps
                                valid_subs = []
                                for sub in sitemap.sub_sitemaps:
                                    if hasattr(sub, 'url') and sub.url and sub.url not in visited:
                                        valid_subs.append(sub.url)
                                
                                # Process sub-sitemaps in parallel with semaphore
                                import asyncio
                                semaphore = asyncio.Semaphore(max_concurrent)
                                
                                async def process_sub_sitemap(sub_url: str) -> List[SitemapURL]:
                                    async with semaphore:
                                        return await self._fetch_and_parse_sitemap_parallel(sub_url, session, visited, max_concurrent)
                                
                                # Create tasks for all sub-sitemaps
                                tasks = [process_sub_sitemap(sub_url) for sub_url in valid_subs]
                                
                                # Process in batches to avoid overwhelming the server
                                batch_size = max_concurrent
                                for i in range(0, len(tasks), batch_size):
                                    batch = tasks[i:i + batch_size]
                                    batch_results = await asyncio.gather(*batch, return_exceptions=True)
                                    
                                    for result in batch_results:
                                        if isinstance(result, Exception):
                                            logger.warning(f"  ⚠️ Error processing sub-sitemap: {result}")
                                        elif isinstance(result, list):
                                            urls.extend(result)
                                            if len(urls) >= self.max_urls:
                                                break
                                    
                                    if len(urls) >= self.max_urls:
                                        break
                                        
                            elif hasattr(sitemap, 'sub_sitemaps'):
                                logger.info(f"  ℹ️ Index sitemap {url} has empty sub_sitemaps list")
                            
                            # Extract pages
                            if hasattr(sitemap, 'pages'):
                                count = 0
                                for page in sitemap.pages:
                                    # Convert USP page to our SitemapURL
                                    normalized_url = normalize_url(page.url)
                                    url_obj = SitemapURL(
                                        loc=normalized_url,
                                        lastmod=page.last_modified.isoformat() if page.last_modified else None,
                                        changefreq=page.change_frequency.value if page.change_frequency else None,
                                        priority=float(page.priority) if page.priority else None,
                                    )
                                    urls.append(url_obj)
                                    count += 1
                                    if len(urls) >= self.max_urls:
                                        break
                                logger.info(f"  ✅ Extracted {count} URLs from {url}")
                                print(f"    [Parsed] {url}: {count} URLs found", flush=True)
                            
                            break # Success, exit retry loop

                        elif 500 <= response.status < 600:
                            if attempt < 2:
                                logger.warning(f"  ⚠️ Server error {response.status} for {url}. Retrying in 5s...")
                                import asyncio
                                await asyncio.sleep(5)
                                continue
                            else:
                                logger.warning(f"  ❌ Failed to fetch sitemap {url} after 3 attempts: {response.status}")
                                return []
                        else:
                            logger.warning(f"  ❌ Failed to fetch sitemap {url}: {response.status}")
                            return []
                except Exception as e:
                    if attempt < 2:
                        logger.warning(f"  ⚠️ Connection error for {url}: {e}. Retrying in 5s...")
                        import asyncio
                        await asyncio.sleep(5)
                        continue
                    raise e
                      
        except Exception as e:
            logger.error(f"  ❌ Error parsing sitemap {url}: {e}")
            print(f"    [Error] {url}: {e}", flush=True)
            
        return urls

    async def _fetch_and_parse_sitemap_recursively(self, url: str, session: aiohttp.ClientSession, visited: set = None) -> List[SitemapURL]:
        """Recursively fetch and parse sitemaps using aiohttp + USP."""
        # Use parallel version by default with instance max_concurrent
        return await self._fetch_and_parse_sitemap_parallel(url, session, visited, max_concurrent=self.max_concurrent)

    async def parse_from_domain(self, domain: str) -> SitemapAnalysis:
        """
        Discover and parse sitemaps for a domain.
        """
        original_domain = domain
        
        timeout_cfg = aiohttp.ClientTimeout(total=HTTP_TIMEOUT)
        connector = aiohttp.TCPConnector(ssl=False)  # Ignore SSL certificate errors
        
        try:
            async with aiohttp.ClientSession(timeout=timeout_cfg, connector=connector) as session:
                # 1. Try local paths
                sitemap_url = await self._try_local_sitemap(original_domain, session)
                discovered_via = "common_path" if sitemap_url else "none"
                
                # 2. If not found, try robots.txt
                if not sitemap_url:
                    sitemap_url = await self._get_sitemap_from_robots(original_domain, session)
                    if sitemap_url:
                        discovered_via = "robots"
                
                urls = []
                sitemap_urls = []
                
                if sitemap_url:
                    sitemap_urls = [sitemap_url]
                    urls = await self._fetch_and_parse_sitemap_recursively(sitemap_url, session)
                
                has_priorities = any(u.priority is not None for u in urls)
                has_changefreq = any(u.changefreq is not None for u in urls)
                has_lastmod = any(u.lastmod is not None for u in urls)

                if not urls and not sitemap_urls:
                     return SitemapAnalysis(
                            discovered_via="none",
                            url=None,
                            http_status=None,
                            exists=False,
                            status="not_found",
                        )

                return SitemapAnalysis(
                    discovered_via=discovered_via,
                    url=sitemap_url,
                    http_status=200,
                    exists=True,
                    status="ok",
                    is_index=len(sitemap_urls) > 1, # Simplified logic
                    child_sitemaps=sitemap_urls if len(sitemap_urls) > 1 else None,
                    urls=urls,
                    total_url_count=len(urls),
                    format_type="xml",
                    has_priorities=has_priorities,
                    has_changefreq=has_changefreq,
                    has_lastmod=has_lastmod,
                )
            
        except Exception as e:
            logger.error(f"Sitemap discovery failed for {original_domain}: {type(e).__name__}: {e}")
            return SitemapAnalysis(
                discovered_via="none",
                url=None,
                http_status=None,
                exists=False,
                status="error",
                error=f"discovery_failed:{type(e).__name__}",
            )