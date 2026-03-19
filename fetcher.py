"""HTTP fetcher with rate limiting, retry logic, and timeout handling."""
import asyncio
import logging
from typing import Dict, Optional, Tuple
from urllib.parse import urlparse

import httpx
from config import HTTP_TIMEOUT, HTTP_CONCURRENCY, DOMAIN_DELAY, MAX_RETRIES, USER_AGENT


logger = logging.getLogger(__name__)


class RateLimitedFetcher:
    """HTTP fetcher with per-domain rate limiting and retry logic."""
    
    def __init__(
        self,
        concurrency: int = HTTP_CONCURRENCY,
        domain_delay: float = DOMAIN_DELAY,
        timeout: float = HTTP_TIMEOUT,
        max_retries: int = MAX_RETRIES,
        user_agent: str = USER_AGENT,
    ):
        """
        Initialize rate-limited fetcher.
        
        Args:
            concurrency: Maximum concurrent requests across all domains
            domain_delay: Minimum delay between requests to same domain (seconds)
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries for failed requests
            user_agent: User-Agent header value
        """
        self.concurrency = concurrency
        self.domain_delay = domain_delay
        self.timeout = timeout
        self.max_retries = max_retries
        self.user_agent = user_agent
        
        # Per-domain rate limiting
        self.domain_locks: Dict[str, asyncio.Lock] = {}
        self.domain_last_request: Dict[str, float] = {}
        
        # Global semaphore
        self.semaphore = asyncio.Semaphore(concurrency)
        
        # HTTP client
        limits = httpx.Limits(
            max_connections=concurrency,
            max_keepalive_connections=min(20, concurrency)
        )
        self.client = httpx.AsyncClient(
            headers={'User-Agent': user_agent, 'Accept': '*/*'},
            limits=limits,
            http2=True,
            verify=False,  # Ignore SSL certificate errors
            follow_redirects=True,
        )
    
    async def fetch(
        self,
        url: str,
        max_bytes: Optional[int] = None,
    ) -> Tuple[Optional[int], Optional[bytes], Dict[str, str], Optional[str]]:
        """
        Fetch URL with rate limiting and retry logic.
        
        Args:
            url: URL to fetch
            max_bytes: Maximum bytes to read (None = unlimited)
            
        Returns:
            Tuple of (status_code, content, headers_dict, error_message)
        """
        domain = self._extract_domain(url)
        
        # Get or create domain lock
        if domain not in self.domain_locks:
            self.domain_locks[domain] = asyncio.Lock()
        
        async with self.semaphore:
            async with self.domain_locks[domain]:
                # Enforce domain delay
                await self._wait_for_domain_delay(domain)
                
                # Try fetch with retries
                for attempt in range(self.max_retries + 1):
                    try:
                        status, content, headers, error = await self._do_fetch(url, max_bytes)
                        
                        # Update last request time
                        self.domain_last_request[domain] = asyncio.get_event_loop().time()
                        
                        # Don't retry on success or client errors (4xx)
                        if status is not None:
                            if 200 <= status < 300 or 400 <= status < 500:
                                return status, content, headers, error
                        
                        # Retry on server errors (5xx) or network errors
                        if attempt < self.max_retries:
                            delay = (2 ** attempt) * 0.5  # Exponential backoff
                            logger.debug(f"Retrying {url} after {delay}s (attempt {attempt + 1}/{self.max_retries})")
                            await asyncio.sleep(delay)
                            continue
                        
                        return status, content, headers, error
                        
                    except Exception as e:
                        error_msg = f"{type(e).__name__}:{str(e)[:100]}"
                        logger.debug(f"Fetch error for {url}: {error_msg}")
                        
                        if attempt < self.max_retries:
                            delay = (2 ** attempt) * 0.5
                            await asyncio.sleep(delay)
                            continue
                        
                        # All retries exhausted - log final failure
                        logger.error(f"Failed to fetch {url} after {self.max_retries + 1} attempts: {error_msg}")
                        return None, None, {}, error_msg
                
                return None, None, {}, "max_retries_exceeded"
    
    async def _do_fetch(
        self,
        url: str,
        max_bytes: Optional[int],
    ) -> Tuple[Optional[int], Optional[bytes], Dict[str, str], Optional[str]]:
        """Perform actual HTTP fetch."""
        try:
            if max_bytes is not None:
                # Stream response to enforce size limit
                # Use separate timeouts: connect=timeout, read=None (unlimited)
                timeout_config = httpx.Timeout(self.timeout, connect=self.timeout, read=None, write=self.timeout, pool=self.timeout)
                async with self.client.stream('GET', url, timeout=timeout_config) as response:
                    chunks = []
                    total_size = 0
                    
                    async for chunk in response.aiter_bytes(chunk_size=8192):
                        chunks.append(chunk)
                        total_size += len(chunk)
                        
                        if total_size >= max_bytes:
                            break
                    
                    content = b''.join(chunks)[:max_bytes]
                    headers = {k.lower(): v for k, v in response.headers.items()}
                    return response.status_code, content, headers, None
            else:
                # Simple fetch without size limit
                # Use separate timeouts: connect=timeout, read=None (unlimited)
                timeout_config = httpx.Timeout(self.timeout, connect=self.timeout, read=None, write=self.timeout, pool=self.timeout)
                response = await self.client.get(url, timeout=timeout_config)
                content = response.content
                headers = {k.lower(): v for k, v in response.headers.items()}
                return response.status_code, content, headers, None
                
        except httpx.TimeoutException:
            return None, None, {}, "timeout"
        except httpx.ConnectError:
            return None, None, {}, "connection_error"
        except httpx.TooManyRedirects:
            return None, None, {}, "too_many_redirects"
        except httpx.HTTPStatusError as e:
            return e.response.status_code, None, {}, f"http_error:{e.response.status_code}"
        except Exception as e:
            return None, None, {}, f"{type(e).__name__}"
    
    async def _wait_for_domain_delay(self, domain: str):
        """Wait if needed to respect domain delay."""
        if domain in self.domain_last_request:
            elapsed = asyncio.get_event_loop().time() - self.domain_last_request[domain]
            if elapsed < self.domain_delay:
                await asyncio.sleep(self.domain_delay - elapsed)
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        parsed = urlparse(url)
        return parsed.netloc or 'unknown'
    
    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()