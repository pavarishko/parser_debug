"""Data models for website audit tool."""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime


@dataclass
class DomainInput:
    """Input domain information."""
    domain: str
    curr_gmv_tier: Optional[str] = None
    curr_industry: Optional[str] = None


@dataclass
class RobotsAnalysis:
    """Comprehensive robots.txt analysis."""
    url: str
    http_status: Optional[int]
    exists: bool
    status: str  # ok, not_found, forbidden, error
    error: Optional[str] = None
    
    # Parsed content
    sitemaps: List[str] = field(default_factory=list)
    raw_content: Optional[str] = None
    
    # Analysis metrics
    total_rules: int = 0
    has_crawl_delay: bool = False
    recommended_delay: Optional[float] = None


@dataclass
class SitemapURL:
    """Individual URL from sitemap."""
    loc: str
    lastmod: Optional[str] = None
    changefreq: Optional[str] = None
    priority: Optional[float] = None


@dataclass
class SitemapAnalysis:
    """Comprehensive sitemap analysis."""
    discovered_via: str  # robots, common_path, none
    url: Optional[str] = None
    http_status: Optional[int] = None
    exists: bool = False
    status: str = "not_found"
    error: Optional[str] = None
    
    # Parsed content
    is_index: bool = False
    child_sitemaps: Optional[List[str]] = None
    urls: Optional[List[SitemapURL]] = None
    total_url_count: int = 0
    
    # Metadata
    format_type: Optional[str] = None  # xml, rss, txt, gzip
    has_priorities: bool = False
    has_changefreq: bool = False
    has_lastmod: bool = False


@dataclass
class CMSEvidence:
    """Evidence for CMS detection."""
    source: str  # html, header, meta, js, css
    pattern: str
    matched_value: str
    confidence_weight: float


@dataclass
class CMSDetection:
    """CMS detection results with confidence scoring."""
    detected: bool = False
    platform: Optional[str] = None
    confidence_score: float = 0.0
    version: Optional[str] = None
    evidence: List[CMSEvidence] = field(default_factory=list)
    alternative_platforms: List[Dict[str, Any]] = field(default_factory=list)
    detected_technologies: List[str] = field(default_factory=list)


@dataclass
class AuditResult:
    """Complete audit result for a domain."""
    # Input data
    domain: str
    curr_gmv_tier: Optional[str]
    curr_industry: Optional[str]
    
    # Analysis metadata
    analysis_timestamp: str
    processing_time_seconds: float
    base_url: Optional[str] = None
    
    # Home page
    home_http_status: Optional[int] = None
    home_accessible: bool = False
    home_error: Optional[str] = None
    
    # Components
    robots: Optional[RobotsAnalysis] = None
    sitemap: Optional[SitemapAnalysis] = None
    cms: Optional[CMSDetection] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'domain': self.domain,
            'curr_gmv_tier': self.curr_gmv_tier,
            'curr_industry': self.curr_industry,
            'analysis_timestamp': self.analysis_timestamp,
            'processing_time_seconds': round(self.processing_time_seconds, 2),
            'base_url': self.base_url,
            'home_http_status': self.home_http_status,
            'home_accessible': self.home_accessible,
            'home_error': self.home_error,
            'robots': self._robots_to_dict(),
            'sitemap': self._sitemap_to_dict(),
            'cms': self._cms_to_dict(),
        }
    
    def _robots_to_dict(self) -> Optional[Dict[str, Any]]:
        """Convert robots analysis to dict."""
        if not self.robots:
            return None
        return {
            'url': self.robots.url,
            'http_status': self.robots.http_status,
            'exists': self.robots.exists,
            'status': self.robots.status,
            'error': self.robots.error,
            'sitemaps': self.robots.sitemaps,
            'total_rules': self.robots.total_rules,
            'has_crawl_delay': self.robots.has_crawl_delay,
            'recommended_delay': self.robots.recommended_delay,
        }
    
    def _sitemap_to_dict(self) -> Optional[Dict[str, Any]]:
        """Convert sitemap analysis to dict."""
        if not self.sitemap:
            return None
        return {
            'discovered_via': self.sitemap.discovered_via,
            'url': self.sitemap.url,
            'http_status': self.sitemap.http_status,
            'exists': self.sitemap.exists,
            'status': self.sitemap.status,
            'error': self.sitemap.error,
            'is_index': self.sitemap.is_index,
            'child_sitemaps_count': len(self.sitemap.child_sitemaps) if self.sitemap.child_sitemaps else 0,
            'total_url_count': self.sitemap.total_url_count,
            'format_type': self.sitemap.format_type,
            'has_priorities': self.sitemap.has_priorities,
            'has_changefreq': self.sitemap.has_changefreq,
            'has_lastmod': self.sitemap.has_lastmod,
        }
    
    def _cms_to_dict(self) -> Optional[Dict[str, Any]]:
        """Convert CMS detection to dict."""
        if not self.cms:
            return None
        return {
            'detected': self.cms.detected,
            'platform': self.cms.platform,
            'confidence_score': round(self.cms.confidence_score, 2),
            'version': self.cms.version,
            'evidence_count': len(self.cms.evidence),
            'evidence': [
                {
                    'source': e.source,
                    'pattern': e.pattern,
                    'confidence_weight': e.confidence_weight,
                }
                for e in self.cms.evidence[:10]
            ],
            'alternative_platforms': self.cms.alternative_platforms[:3] if self.cms.alternative_platforms else None,
            'detected_technologies': self.cms.detected_technologies[:20] if self.cms.detected_technologies else [],
        }