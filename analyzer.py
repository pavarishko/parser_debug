"""Main analyzer orchestrating website audits."""
import asyncio
import logging
import time
from datetime import datetime
from typing import List, Optional
from urllib.parse import urljoin

from models import DomainInput, AuditResult, RobotsAnalysis, SitemapAnalysis
from fetcher import RateLimitedFetcher
from parsers import RobotsParser, SitemapParser, SitemapFastChecker, CMSDetector
from config import (
    HTTP_TIMEOUT,
    HTTP_CONCURRENCY,
    DOMAIN_DELAY,
    MAX_RETRIES,
    MAX_HOME_BYTES,
    MAX_ROBOTS_BYTES,
    MAX_SITEMAP_URLS,
)


logger = logging.getLogger(__name__)


class WebsiteAnalyzer:
    """Analyze website technical infrastructure."""
    
    def __init__(
        self,
        concurrency: int = HTTP_CONCURRENCY,
        domain_delay: float = DOMAIN_DELAY,
        timeout: float = HTTP_TIMEOUT,
        max_retries: int = MAX_RETRIES,
        max_sitemap_urls: int = MAX_SITEMAP_URLS,
        max_sitemap_children: int = 100,
        fast_sitemap_mode: bool = True,
    ):
        """
        Initialize website analyzer.
        
        Args:
            concurrency: Maximum concurrent requests
            domain_delay: Delay between requests to same domain (seconds)
            timeout: Request timeout (seconds)
            max_retries: Maximum retry attempts
            max_sitemap_urls: Maximum URLs to extract from a sitemap
            max_sitemap_children: Maximum child sitemaps to process
            fast_sitemap_mode: Use fast checker (existence only) instead of full parser
        """
        self.concurrency = concurrency
        self.max_sitemap_children = max_sitemap_children
        self.fast_sitemap_mode = fast_sitemap_mode
        
        # Initialize components
        self.fetcher = RateLimitedFetcher(
            concurrency=concurrency,
            domain_delay=domain_delay,
            timeout=timeout,
            max_retries=max_retries,
        )
        self.robots_parser = RobotsParser()
        
        # Choose sitemap parser based on mode
        if fast_sitemap_mode:
            self.sitemap_parser = SitemapFastChecker()
        else:
            self.sitemap_parser = SitemapParser(max_urls=max_sitemap_urls)
        
        self.cms_detector = CMSDetector()
    
    async def analyze_domain(self, domain_input: DomainInput) -> AuditResult:
        """
        Analyze a single domain.
        
        Args:
            domain_input: Domain information to analyze
            
        Returns:
            AuditResult with all analysis data
        """
        start_time = time.time()
        domain = domain_input.domain
        
        logger.info(f"Analyzing {domain}")
        
        # Try HTTPS first, fallback to HTTP
        base_url, home_status, home_data, home_headers, home_error = await self._fetch_homepage(domain)
        
        # Decode HTML (even if homepage failed, try to get what we can)
        home_html = self._decode_content(home_data) if home_data else ""
        
        # ALWAYS check robots.txt and sitemap, even if homepage is inaccessible
        # (robots.txt might be accessible even with 403/404 homepage)
        robots = await self._analyze_robots(base_url)
        sitemap = await self._analyze_sitemap(base_url, robots)
        
        # Detect CMS (cms_detector.detect() handles empty HTML gracefully)
        cms = self.cms_detector.detect(home_html, home_headers, base_url)
        
        processing_time = time.time() - start_time
        
        return AuditResult(
            domain=domain,
            curr_gmv_tier=domain_input.curr_gmv_tier,
            curr_industry=domain_input.curr_industry,
            analysis_timestamp=datetime.utcnow().isoformat(),
            processing_time_seconds=processing_time,
            base_url=base_url,
            home_http_status=home_status,
            home_accessible=home_status == 200,
            home_error=home_error,
            robots=robots,
            sitemap=sitemap,
            cms=cms,
        )
    
    async def _fetch_homepage(self, domain: str):
        """Fetch homepage, trying HTTPS then HTTP."""
        # Try HTTPS first
        https_url = f"https://{domain}/"
        status, data, headers, error = await self.fetcher.fetch(https_url, MAX_HOME_BYTES)
        
        if status is not None and 200 <= status < 400:
            return https_url, status, data, headers, error
        
        # Fallback to HTTP
        http_url = f"http://{domain}/"
        status2, data2, headers2, error2 = await self.fetcher.fetch(http_url, MAX_HOME_BYTES)
        
        if status2 is not None and 200 <= status2 < 400:
            return http_url, status2, data2, headers2, error2
        
        # Both failed, but still return HTTPS URL for robots.txt/sitemap checks
        # (robots.txt might be accessible even if homepage returns 403/404)
        final_status = status or status2
        final_data = data or data2
        final_headers = headers or headers2
        final_error = error or error2
        base_url = https_url if status is not None else http_url
        
        return base_url, final_status, final_data, final_headers, final_error
    
    async def _analyze_robots(self, base_url: str) -> RobotsAnalysis:
        """Analyze robots.txt file."""
        robots_url = urljoin(base_url, '/robots.txt')
        
        status, data, headers, error = await self.fetcher.fetch(robots_url, MAX_ROBOTS_BYTES)
        
        content = self._decode_content(data) if data else ""
        
        return self.robots_parser.parse(content, robots_url, status)
    
    async def _analyze_sitemap(self, base_url: str, robots: Optional[RobotsAnalysis]) -> SitemapAnalysis:
        """Analyze sitemap using USP (fast or full mode)."""
        from urllib.parse import urlparse
        parsed = urlparse(base_url)
        domain = parsed.netloc
        
        if self.fast_sitemap_mode:
            # Fast mode: use robots.txt data + HTTP checks
            return await self.sitemap_parser.check_from_robots(base_url, robots)
        else:
            # Full mode: parse all URLs with USP
            return await self.sitemap_parser.parse_from_domain(domain)
    
    def _decode_content(self, data: bytes) -> str:
        """Decode bytes to string, trying multiple encodings."""
        if not data:
            return ""
        
        for encoding in ['utf-8', 'latin-1', 'cp1251']:
            try:
                return data.decode(encoding, errors='replace')
            except Exception as e:
                logger.error(f"Unexpected decode error with {encoding}: {type(e).__name__}: {e}")
                continue
        
        return data.decode('utf-8', errors='replace')
    
    async def close(self):
        """Close resources."""
        await self.fetcher.close()


async def analyze_batch(
    domains: List[DomainInput],
    concurrency: int = HTTP_CONCURRENCY,
    domain_delay: float = DOMAIN_DELAY,
    timeout: float = HTTP_TIMEOUT,
    max_retries: int = MAX_RETRIES,
    progress_callback=None,
    fast_sitemap_mode: bool = True,
) -> List[AuditResult]:
    """
    Analyze a batch of domains in parallel.
    
    Args:
        domains: List of domains to analyze
        concurrency: Maximum concurrent requests
        domain_delay: Delay between requests to same domain
        timeout: Request timeout in seconds
        max_retries: Maximum retry attempts
        progress_callback: Optional callback(completed, total) for progress tracking
        fast_sitemap_mode: Use fast sitemap checker (recommended for bulk processing)
        
    Returns:
        List of AuditResult objects
    """
    analyzer = WebsiteAnalyzer(
        concurrency=concurrency,
        domain_delay=domain_delay,
        timeout=timeout,
        max_retries=max_retries,
        fast_sitemap_mode=fast_sitemap_mode,
    )
    
    try:
        # Create all tasks for parallel execution
        tasks = [analyzer.analyze_domain(d) for d in domains]
        total = len(tasks)
        
        # Process tasks as they complete for progress tracking
        results = []
        for i, coro in enumerate(asyncio.as_completed(tasks)):
            result = await coro
            results.append(result)
            
            if progress_callback:
                progress_callback(i + 1, total)
        
        return results
        
    finally:
        await analyzer.close()


async def analyze_batch_streaming(
    domains: List[DomainInput],
    output_callback,
    concurrency: int = HTTP_CONCURRENCY,
    domain_delay: float = DOMAIN_DELAY,
    timeout: float = HTTP_TIMEOUT,
    max_retries: int = MAX_RETRIES,
    fast_sitemap_mode: bool = True,
) -> None:
    """
    Analyze domains in parallel with streaming output via callback.
    
    Args:
        domains: List of domains to analyze
        output_callback: Callback(result, completed, total) called for each result
        concurrency: Maximum concurrent requests
        domain_delay: Delay between requests to same domain
        timeout: Request timeout in seconds
        max_retries: Maximum retry attempts
        fast_sitemap_mode: Use fast sitemap checker (recommended for bulk processing)
    """
    analyzer = WebsiteAnalyzer(
        concurrency=concurrency,
        domain_delay=domain_delay,
        timeout=timeout,
        max_retries=max_retries,
        fast_sitemap_mode=fast_sitemap_mode,
    )
    
    try:
        # Create all tasks for parallel execution
        tasks = [analyzer.analyze_domain(d) for d in domains]
        total = len(tasks)
        
        # Process tasks as they complete and stream results
        for i, coro in enumerate(asyncio.as_completed(tasks)):
            result = await coro
            output_callback(result, i + 1, total)
        
    finally:
        await analyzer.close()