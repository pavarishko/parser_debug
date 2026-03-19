import logging
import re
from urllib.parse import urlparse, urlunparse
from typing import Optional, Set

from w3lib.url import url_query_cleaner
from url_normalize import url_normalize

logger = logging.getLogger(__name__)

TRACKING_PARAMS: Set[str] = {
    'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
    'utm_id', 'utm_source_platform', 'utm_creative_format', 'utm_marketing_tactic',
    'gclid', 'gclsrc', '_ga', 'ga_source', 'ga_medium', 'ga_campaign',
    'fbclid', 'fb_action_ids', 'fb_action_types', 'fb_source', 'fb_ref',
    'yclid', '_openstat', 'ymclid', 'from',
    'msclkid', 'mc_cid', 'mc_eid', 'ref', 'referrer', 'source',
    '_hsenc', '_hsmi', 'hsCtaTracking', 'mkt_tok',
}

WWW_PREFIXES: Set[str] = {
    'www', 'www1', 'www2', 'www3', 'www4',
    'm', 'mobile',
}

def normalize_url(
    url: str,
    *,
    remove_www: bool = True,
    remove_tracking: bool = True,
    remove_all_query: bool = False,
    remove_fragment: bool = True,
    sort_query: bool = True,
    strip_trailing_slash: bool = True,
    remove_regional_subdomains: bool = True,
) -> str:
    if not url or not url.strip():
        return url
    
    try:
        # 1. Remove tracking params (business logic)
        if remove_tracking and not remove_all_query:
            url = url_query_cleaner(url, parameterlist=list(TRACKING_PARAMS), remove=True)
        
        # 2. Robust normalization (RFC compliance)
        normalized = url_normalize(url)
        
        # 3. Custom post-processing
        parsed = urlparse(normalized)
        scheme = parsed.scheme
        netloc = parsed.netloc
        path = parsed.path
        params = parsed.params
        query = parsed.query
        fragment = parsed.fragment if not remove_fragment else ''

        # 3.1 Remove regional subdomains (e.g., barnaul.askona.ru -> askona.ru)
        if remove_regional_subdomains and netloc:
            if '.' in netloc:
                parts = netloc.split('.')
                # If domain has more than 2 parts (regional subdomain), keep only main domain
                if len(parts) > 2 and not parts[-2].startswith('co'):  # Exclude .co.uk etc.
                    # For Russian domains: keep last 2 parts
                    if parts[-1] in ['ru', 'su', 'рф'] and len(parts) > 2:
                        netloc = '.'.join(parts[-2:])
                    # For international domains: keep last 2-3 parts depending on TLD
                    elif len(parts) > 3:
                        netloc = '.'.join(parts[-3:])
        
        # 3.2 Remove www prefix
        if remove_www and netloc:
            netloc = _remove_www_prefix(netloc)
        
        if remove_all_query:
            query = ''
            
        if strip_trailing_slash and path and path != '/' and path.endswith('/'):
            path = path.rstrip('/')
            
        return urlunparse((scheme, netloc, path, params, query, fragment))
        
    except Exception as e:
        logger.warning(f"URL normalization failed for {url}: {e}")
        return url.strip()

def normalize_domain(domain: str, *, remove_www: bool = True) -> str:
    if not domain or not domain.strip():
        return domain
    
    domain = domain.strip()
    if '://' in domain:
        try:
            domain = urlparse(domain).netloc or domain
        except Exception:
            pass
    
    if ':' in domain and not domain.startswith('['):
        domain = domain.rsplit(':', 1)[0]
    
    domain = domain.lower()
    
    if remove_www:
        domain = _remove_www_prefix(domain)
    
    try:
        return domain.encode('idna').decode('ascii')
    except Exception:
        return domain

def extract_domain(url: str, *, normalize: bool = True) -> str:
    if not url:
        return ''
    try:
        domain = urlparse(url).netloc
        return normalize_domain(domain) if normalize and domain else domain
    except Exception:
        return ''

def urls_match(
    url1: str,
    url2: str,
    *,
    ignore_query: bool = False,
    ignore_fragment: bool = True,
) -> bool:
    if not url1 or not url2:
        return False
    try:
        norm1 = normalize_url(url1, remove_fragment=ignore_fragment, remove_all_query=ignore_query)
        norm2 = normalize_url(url2, remove_fragment=ignore_fragment, remove_all_query=ignore_query)
        return norm1 == norm2
    except Exception:
        return False

def urls_match_fuzzy(
    url1: str,
    url2: str,
    *,
    ignore_query: bool = True,
) -> bool:
    if urls_match(url1, url2, ignore_query=ignore_query):
        return True
        
    try:
        norm1 = normalize_url(url1, remove_all_query=ignore_query)
        norm2 = normalize_url(url2, remove_all_query=ignore_query)
        
        parsed1 = urlparse(norm1)
        parsed2 = urlparse(norm2)
        
        if parsed1.netloc != parsed2.netloc:
            return False
            
        path1_clean = re.sub(r'[-_]', '', parsed1.path)
        path2_clean = re.sub(r'[-_]', '', parsed2.path)
        
        return path1_clean == path2_clean
    except Exception:
        return False

def _remove_www_prefix(domain: str) -> str:
    has_port = False
    port = ''
    if ':' in domain and not domain.startswith('['):
        domain, port = domain.rsplit(':', 1)
        has_port = True
    
    parts = domain.split('.')
    if len(parts) > 1 and parts[0] in WWW_PREFIXES:
        domain = '.'.join(parts[1:])
    
    if has_port:
        domain = f"{domain}:{port}"
    
    return domain