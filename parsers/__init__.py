"""Parsers package with lazy exports.

Avoid importing heavy optional dependencies at module import time.
"""

__all__ = ["RobotsParser", "SitemapParser", "SitemapFastChecker", "CMSDetector"]


def __getattr__(name):
    if name == "RobotsParser":
        from parsers.robots import RobotsParser

        return RobotsParser
    if name == "SitemapParser":
        from parsers.sitemap_full import SitemapParser

        return SitemapParser
    if name == "SitemapFastChecker":
        from parsers.sitemap_fast import SitemapFastChecker

        return SitemapFastChecker
    if name == "CMSDetector":
        from parsers.cms import CMSDetector

        return CMSDetector
    raise AttributeError(name)
