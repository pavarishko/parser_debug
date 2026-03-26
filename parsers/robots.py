"""robots.txt parsing utilities based on Protego."""

from __future__ import annotations

import logging
from typing import Optional

from protego import Protego

from models import RobotsAnalysis


logger = logging.getLogger(__name__)


class RobotsParser:
    """Parse robots.txt and expose simple crawl-access checks."""

    def parse(self, content: str, url: str, http_status: Optional[int]) -> RobotsAnalysis:
        """Parse robots.txt response into a structured `RobotsAnalysis` object."""
        if http_status != 200 or not content:
            return RobotsAnalysis(
                url=url,
                http_status=http_status,
                exists=http_status == 200,
                status=self._status_bucket(http_status),
                error="empty_content" if http_status == 200 else None,
            )

        try:
            robot_rules = Protego.parse(content)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to parse robots.txt for %s: %s", url, exc)
            return RobotsAnalysis(
                url=url,
                http_status=http_status,
                exists=True,
                status="error",
                error=f"parse_error:{type(exc).__name__}",
            )

        lines = [line.strip() for line in content.splitlines() if line.strip()]
        user_agent_count = sum(line.lower().startswith("user-agent:") for line in lines)
        disallow_count = sum(line.lower().startswith("disallow:") for line in lines)
        has_crawl_delay = any(line.lower().startswith("crawl-delay:") for line in lines)

        return RobotsAnalysis(
            url=url,
            http_status=http_status,
            exists=True,
            status="ok",
            sitemaps=list(robot_rules.sitemaps),
            raw_content=content[:10_000],
            total_rules=int(user_agent_count + disallow_count),
            has_crawl_delay=has_crawl_delay,
            recommended_delay=None,
        )

    def is_allowed(self, robots_content: str, target_url: str, user_agent: str = "*") -> Optional[bool]:
        """Return crawl-allow decision for target URL.

        Returns None when robots.txt cannot be parsed.
        """
        if not robots_content:
            return None
        try:
            robot_rules = Protego.parse(robots_content)
        except Exception:  # noqa: BLE001
            return None
        return bool(robot_rules.can_fetch(target_url, user_agent))

    @staticmethod
    def _status_bucket(code: Optional[int]) -> str:
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
