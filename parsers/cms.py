"""CMS detection using python-Wappalyzer library."""
import logging
from typing import Dict, List, Optional
from Wappalyzer import Wappalyzer, WebPage
from models import CMSEvidence, CMSDetection


logger = logging.getLogger(__name__)


class CMSDetector:
    """Detect CMS and technology stack using Wappalyzer."""
    
    def __init__(self):
        """Initialize Wappalyzer detector."""
        try:
            self.wappalyzer = Wappalyzer.latest()
        except Exception as e:
            logger.error(f"Failed to initialize Wappalyzer: {type(e).__name__}: {e}")
            self.wappalyzer = None
    
    def detect(self, html: str, headers: Dict[str, str], base_url: str = 'https://example.com') -> CMSDetection:
        """
        Detect CMS platform and technology stack using Wappalyzer.
        
        Args:
            html: HTML content of the page
            headers: HTTP response headers (lowercase keys)
            base_url: Base URL of the page (used by Wappalyzer for relative path resolution)
            
        Returns:
            CMSDetection with detected technologies
        """
        if not self.wappalyzer or not html:
            return CMSDetection(
                detected=False,
                evidence=[],
            )
        
        try:
            webpage = WebPage(url=base_url, html=html, headers=headers)
            technologies = self.wappalyzer.analyze(webpage)
        except Exception as e:
            logger.error(f"Wappalyzer analysis failed: {type(e).__name__}: {e}")
            return CMSDetection(
                detected=False,
                evidence=[CMSEvidence(
                    source='error',
                    pattern='wappalyzer_error',
                    matched_value=str(e)[:100],
                    confidence_weight=0.0
                )],
            )
        
        if not technologies:
            return CMSDetection(
                detected=False,
                evidence=[],
            )
        
        cms_platforms = self._identify_cms_platforms(technologies)
        evidence_list = self._build_evidence(technologies)
        
        if not cms_platforms:
            return CMSDetection(
                detected=True,
                platform='Unknown CMS',
                confidence_score=0.3,
                evidence=evidence_list,
                detected_technologies=list(technologies),
            )
        
        primary_cms = cms_platforms[0]
        
        version = None
        for tech in technologies:
            if primary_cms.lower() in tech.lower() and '/' in tech:
                version = tech.split('/', 1)[1]
                break
        
        confidence = self._calculate_confidence(primary_cms, technologies)
        
        alternatives = [
            {'platform': cms, 'confidence_score': round(confidence * 0.8, 2)}
            for cms in cms_platforms[1:3]
        ]
        
        return CMSDetection(
            detected=True,
            platform=primary_cms,
            confidence_score=confidence,
            version=version,
            evidence=evidence_list,
            alternative_platforms=alternatives if alternatives else None,
            detected_technologies=list(technologies),
        )
    
    def _identify_cms_platforms(self, technologies: set) -> List[str]:
        """Identify CMS platforms from detected technologies."""
        cms_keywords = [
            'WordPress', 'Joomla', 'Drupal', 'Magento', 'PrestaShop',
            'OpenCart', 'Shopify', 'WooCommerce', 'BigCommerce',
            '1C-Bitrix', 'MODX', 'Tilda', 'Wix', 'Squarespace',
            'Weebly', 'Webflow', 'Ghost', 'Contentful', 'Strapi'
        ]
        
        found_cms = []
        for tech in technologies:
            for cms in cms_keywords:
                if cms.lower() in tech.lower():
                    found_cms.append(cms)
                    break
        
        return found_cms
    
    def _build_evidence(self, technologies: set) -> List[CMSEvidence]:
        """Build evidence list from detected technologies."""
        evidence = []
        
        for tech in technologies:
            evidence.append(CMSEvidence(
                source='wappalyzer',
                pattern=tech,
                matched_value=tech,
                confidence_weight=0.8
            ))
        
        return evidence[:20]
    
    def _calculate_confidence(self, cms: str, technologies: set) -> float:
        """Calculate confidence score based on number of related technologies."""
        base_confidence = 0.7
        
        related_count = sum(1 for t in technologies if cms.lower() in t.lower())
        
        if related_count >= 3:
            return min(base_confidence + 0.3, 1.0)
        elif related_count == 2:
            return min(base_confidence + 0.2, 1.0)
        elif related_count == 1:
            return base_confidence
        else:
            return 0.5