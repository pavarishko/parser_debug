"""Robots.txt parser using Protego library."""
from typing import Optional
import logging
from protego import Protego
from models import RobotsAnalysis


logger = logging.getLogger(__name__)


class RobotsParser:
    """Parse and analyze robots.txt files using Protego."""
    
    def parse(self, content: str, url: str, http_status: Optional[int]) -> RobotsAnalysis:
        """
        Parse robots.txt content using Protego library.
        
        Args:
            content: Raw robots.txt content
            url: URL of the robots.txt file
            http_status: HTTP status code from fetch
            
        Returns:
            RobotsAnalysis with parsed data and metrics
        """
        if http_status != 200 or not content:
            return RobotsAnalysis(
                url=url,
                http_status=http_status,
                exists=http_status == 200,
                status=self._status_bucket(http_status),
                error="empty_content" if http_status == 200 else None,
            )
        
        try:
            rp = Protego.parse(content)
        except Exception as e:
            logger.warning(f"Failed to parse robots.txt for {url}: {type(e).__name__}: {e}")
            return RobotsAnalysis(
                url=url,
                http_status=http_status,
                exists=True,
                status="error",
                error=f"parse_error:{type(e).__name__}",
            )
        
        # Extract sitemaps from Protego
        sitemaps = list(rp.sitemaps)
        
        # Basic metrics from content (simple line counting)
        lines = content.strip().split('\n')
        user_agent_count = sum(1 for line in lines if line.strip().lower().startswith('user-agent:'))
        disallow_count = sum(1 for line in lines if line.strip().lower().startswith('disallow:'))
        
        # Check for crawl-delay directive
        has_crawl_delay = any('crawl-delay:' in line.lower() for line in lines)
        
        return RobotsAnalysis(
            url=url,
            http_status=http_status,
            exists=True,
            status="ok",
            sitemaps=sitemaps,
            raw_content=content[:10000],  # Store first 10KB for debugging
            total_rules=user_agent_count + disallow_count,
            has_crawl_delay=has_crawl_delay,
            recommended_delay=None,  # Protego doesn't expose this easily
        )
    
    def _status_bucket(self, code: Optional[int]) -> str:
        """Categorize HTTP status code."""
        if code == 200:
            return "ok"
        if code == 404:
            return "not_found"
        if code in (401, 403):
            return "forbidden"
        if code and 500 <= code < 600:
            return "server_error"
        if code and 300 <= code < 400:
            return "redirect"
        return "error"