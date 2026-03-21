"""High-throughput asynchronous sitemap parser.

This parser is designed for very large sitemap trees:
- discovers sitemap roots from robots.txt + common paths
- parses sitemap index and urlset files asynchronously
- supports .xml, .xml.gz and plain-text sitemap formats
- limits memory usage with queue-based crawling and deduplication sets
"""

from __future__ import annotations

import asyncio
import gzip
import logging
import re
from dataclasses import dataclass
from typing import Iterable, List, Optional, Set, Tuple
from urllib.parse import urljoin
import xml.etree.ElementTree as ET

import aiohttp

from config import HTTP_TIMEOUT, MAX_SITEMAP_CHILDREN, MAX_SITEMAP_URLS
from models import SitemapAnalysis, SitemapURL
from utils import normalize_url


logger = logging.getLogger(__name__)

_XML_LOC_RE = re.compile(r"<loc>\s*(.*?)\s*</loc>", flags=re.IGNORECASE | re.DOTALL)


@dataclass(slots=True)
class _SitemapFetchResult:
    status: int
    body: bytes
    content_type: str
    content_encoding: str


class SitemapParser:
    """Parse sitemap trees for a domain using a fully async queue-based crawler."""

    COMMON_PATHS: Tuple[str, ...] = (
        "/sitemap.xml",
        "/sitemap_index.xml",
        "/sitemap-index.xml",
        "/sitemap.xml.gz",
        "/sitemap_index.xml.gz",
        "/sitemap.txt",
    )

    def __init__(
        self,
        max_urls: int = MAX_SITEMAP_URLS,
        max_concurrent: int = 20,
        max_sitemaps: int = MAX_SITEMAP_CHILDREN,
    ):
        self.max_urls = max_urls
        self.max_concurrent = max_concurrent
        self.max_sitemaps = max_sitemaps

    async def parse_from_domain(self, domain: str) -> SitemapAnalysis:
        timeout_cfg = aiohttp.ClientTimeout(total=HTTP_TIMEOUT)
        connector = aiohttp.TCPConnector(ssl=False)

        async with aiohttp.ClientSession(timeout=timeout_cfg, connector=connector) as session:
            roots, discovered_via = await self._discover_root_sitemaps(domain, session)
            if not roots:
                return SitemapAnalysis(
                    discovered_via="none",
                    url=None,
                    http_status=None,
                    exists=False,
                    status="not_found",
                )

            urls, visited_sitemaps = await self._crawl_sitemaps(session, roots)

            if not urls and not visited_sitemaps:
                return SitemapAnalysis(
                    discovered_via=discovered_via,
                    url=roots[0],
                    http_status=None,
                    exists=False,
                    status="error",
                    error="sitemap_unreadable",
                )

            has_priorities = any(u.priority is not None for u in urls)
            has_changefreq = any(u.changefreq is not None for u in urls)
            has_lastmod = any(u.lastmod is not None for u in urls)

            return SitemapAnalysis(
                discovered_via=discovered_via,
                url=roots[0],
                http_status=200,
                exists=True,
                status="ok",
                is_index=len(visited_sitemaps) > 1,
                child_sitemaps=sorted(visited_sitemaps) if len(visited_sitemaps) > 1 else None,
                urls=urls,
                total_url_count=len(urls),
                format_type="xml",
                has_priorities=has_priorities,
                has_changefreq=has_changefreq,
                has_lastmod=has_lastmod,
            )

    async def _discover_root_sitemaps(
        self,
        domain: str,
        session: aiohttp.ClientSession,
    ) -> Tuple[List[str], str]:
        """Discover root sitemap candidates using robots.txt then common paths."""
        for scheme in ("https", "http"):
            base = f"{scheme}://{domain}"
            robots_url = f"{base}/robots.txt"
            discovered = await self._extract_robots_sitemaps(session, robots_url)
            if discovered:
                return discovered, "robots"

        # Fallback: common sitemap paths.
        candidates = [f"https://{domain}{path}" for path in self.COMMON_PATHS]
        existing: List[str] = []
        for candidate in candidates:
            if await self._exists(session, candidate):
                existing.append(candidate)

        if existing:
            return existing, "common_path"

        return [], "none"

    async def _extract_robots_sitemaps(self, session: aiohttp.ClientSession, robots_url: str) -> List[str]:
        discovered: List[str] = []
        try:
            async with session.get(robots_url, allow_redirects=True) as response:
                if response.status != 200:
                    return []
                text = await response.text(errors="replace")
                for line in text.splitlines():
                    line_clean = line.strip()
                    if not line_clean.lower().startswith("sitemap:"):
                        continue
                    value = line_clean.split(":", 1)[1].strip()
                    if not value:
                        continue
                    discovered.append(urljoin(robots_url, value))
        except Exception as exc:  # noqa: BLE001
            logger.debug("robots.txt fetch failed for %s: %s", robots_url, exc)
            return []

        return self._unique_urls(discovered)

    async def _exists(self, session: aiohttp.ClientSession, url: str) -> bool:
        try:
            async with session.head(url, allow_redirects=True) as response:
                if 200 <= response.status < 300:
                    return True
                if response.status in (403, 405):
                    # Some CDNs block HEAD. Try GET fallback.
                    pass
                else:
                    return False
        except Exception:
            pass

        try:
            async with session.get(url, allow_redirects=True) as response:
                return 200 <= response.status < 300
        except Exception:
            return False

    async def _crawl_sitemaps(
        self,
        session: aiohttp.ClientSession,
        roots: List[str],
    ) -> Tuple[List[SitemapURL], Set[str]]:
        """Crawl sitemap graph with bounded async workers."""
        queue: asyncio.Queue[str] = asyncio.Queue()
        enqueued: Set[str] = set()
        for root in roots:
            if root not in enqueued:
                enqueued.add(root)
                await queue.put(root)

        visited_sitemaps: Set[str] = set()
        seen_urls: Set[str] = set()
        collected: List[SitemapURL] = []
        state_lock = asyncio.Lock()
        stop_event = asyncio.Event()

        async def worker() -> None:
            while True:
                sitemap_url = await queue.get()
                try:
                    if stop_event.is_set():
                        continue

                    async with state_lock:
                        if sitemap_url in visited_sitemaps:
                            continue
                        if len(visited_sitemaps) >= self.max_sitemaps:
                            stop_event.set()
                            continue
                        visited_sitemaps.add(sitemap_url)

                    fetch_result = await self._fetch_sitemap(session, sitemap_url)
                    if fetch_result is None:
                        continue

                    child_sitemaps, page_urls = self._parse_sitemap_document(
                        body=fetch_result.body,
                        content_type=fetch_result.content_type,
                        content_encoding=fetch_result.content_encoding,
                        sitemap_url=sitemap_url,
                    )

                    async with state_lock:
                        # Enqueue children while respecting limits.
                        for child in child_sitemaps:
                            if child in enqueued:
                                continue
                            if len(enqueued) >= self.max_sitemaps:
                                stop_event.set()
                                break
                            enqueued.add(child)
                            await queue.put(child)

                        if not page_urls or len(collected) >= self.max_urls:
                            if len(collected) >= self.max_urls:
                                stop_event.set()
                            continue

                        for entry in page_urls:
                            if entry.loc in seen_urls:
                                continue
                            seen_urls.add(entry.loc)
                            collected.append(entry)
                            if len(collected) >= self.max_urls:
                                stop_event.set()
                                break
                finally:
                    queue.task_done()

        workers = [asyncio.create_task(worker()) for _ in range(self.max_concurrent)]
        await queue.join()

        for task in workers:
            task.cancel()
        await asyncio.gather(*workers, return_exceptions=True)

        return collected, visited_sitemaps

    async def _fetch_sitemap(
        self,
        session: aiohttp.ClientSession,
        url: str,
    ) -> Optional[_SitemapFetchResult]:
        """Fetch sitemap content with retry for transient failures."""
        for attempt in range(3):
            try:
                async with session.get(url, allow_redirects=True) as response:
                    if response.status == 200:
                        body = await response.read()
                        content_type = response.headers.get("Content-Type", "").lower()
                        content_encoding = response.headers.get("Content-Encoding", "").lower()
                        return _SitemapFetchResult(
                            status=response.status,
                            body=body,
                            content_type=content_type,
                            content_encoding=content_encoding,
                        )

                    if 500 <= response.status < 600 and attempt < 2:
                        await asyncio.sleep(0.5 * (2**attempt))
                        continue
                    return None
            except Exception as exc:  # noqa: BLE001
                if attempt < 2:
                    await asyncio.sleep(0.5 * (2**attempt))
                    continue
                logger.debug("Sitemap fetch failed (%s): %s", url, exc)
        return None

    def _parse_sitemap_document(
        self,
        body: bytes,
        content_type: str,
        content_encoding: str,
        sitemap_url: str,
    ) -> Tuple[List[str], List[SitemapURL]]:
        """Parse sitemap payload into child sitemap links and page URLs."""
        raw = body
        has_gzip_magic = body.startswith(b"\x1f\x8b")
        has_gzip_encoding = "gzip" in content_encoding
        has_gzip_suffix = sitemap_url.endswith(".gz")
        should_decompress = has_gzip_magic or has_gzip_encoding or has_gzip_suffix
        if should_decompress:
            try:
                raw = gzip.decompress(body)
            except Exception:
                # Some sites return plain XML from *.xml.gz endpoints.
                # If gzip is only inferred from URL suffix, continue as plain text.
                if has_gzip_magic or has_gzip_encoding:
                    logger.debug("Failed to decompress gzip sitemap: %s", sitemap_url)
                    return [], []

        text = raw.decode("utf-8", errors="replace").strip()
        xml_start = text.find("<")
        if xml_start > 0:
            text = text[xml_start:]
        if not text:
            return [], []

        # Plain text sitemap format (one URL per line)
        if "<" not in text[:200] and "xml" not in content_type:
            urls = [line.strip() for line in text.splitlines() if line.strip().startswith(("http://", "https://"))]
            return [], [SitemapURL(loc=normalize_url(u)) for u in urls]

        child_sitemaps: List[str] = []
        page_urls: List[SitemapURL] = []

        try:
            root = ET.fromstring(text)
        except ET.ParseError:
            # Fallback parser for invalid but frequent XML where loc tags still exist.
            locs = [m.strip() for m in _XML_LOC_RE.findall(text)]
            valid_locs = [loc for loc in locs if loc.startswith(("http://", "https://"))]
            if "<sitemapindex" in text.lower():
                return self._unique_urls(valid_locs), []
            page_urls.extend(SitemapURL(loc=normalize_url(loc)) for loc in valid_locs)
            return [], page_urls

        tag = self._strip_ns(root.tag)
        if tag == "sitemapindex":
            for sitemap_node in root.findall("{*}sitemap"):
                loc = sitemap_node.findtext("{*}loc")
                if not loc:
                    continue
                child_sitemaps.append(urljoin(sitemap_url, loc.strip()))
        elif tag == "urlset":
            for url_node in root.findall("{*}url"):
                loc = url_node.findtext("{*}loc")
                if not loc:
                    continue
                lastmod = url_node.findtext("{*}lastmod")
                changefreq = url_node.findtext("{*}changefreq")
                priority_raw = url_node.findtext("{*}priority")
                priority = None
                if priority_raw:
                    try:
                        priority = float(priority_raw)
                    except ValueError:
                        priority = None

                page_urls.append(
                    SitemapURL(
                        loc=normalize_url(loc.strip()),
                        lastmod=lastmod.strip() if lastmod else None,
                        changefreq=changefreq.strip() if changefreq else None,
                        priority=priority,
                    )
                )

        return self._unique_urls(child_sitemaps), page_urls

    @staticmethod
    def _strip_ns(tag: str) -> str:
        if "}" in tag:
            return tag.split("}", 1)[1]
        return tag

    @staticmethod
    def _unique_urls(urls: Iterable[str]) -> List[str]:
        seen: Set[str] = set()
        out: List[str] = []
        for url in urls:
            value = url.strip()
            if not value or value in seen:
                continue
            seen.add(value)
            out.append(value)
        return out
