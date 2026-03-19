import unittest

from parsers.sitemap_full import SitemapParser
from utils import normalize_url, urls_match


class UrlNormalizationTests(unittest.TestCase):
    def test_keeps_regional_subdomain_by_default(self):
        u = "https://spb.example.ru/catalog/?utm_source=ad&x=1"
        self.assertEqual(normalize_url(u), "https://spb.example.ru/catalog?x=1")

    def test_query_is_sorted_and_tracking_removed(self):
        u = "https://example.com/p?a=2&utm_medium=cpc&b=1"
        self.assertEqual(normalize_url(u), "https://example.com/p?a=2&b=1")

    def test_default_port_is_removed(self):
        self.assertEqual(normalize_url("https://example.com:443/p"), "https://example.com/p")

    def test_url_match_ignores_fragment(self):
        self.assertTrue(urls_match("https://example.com/p#x", "https://example.com/p#y"))


class SitemapParserTests(unittest.TestCase):
    def setUp(self):
        self.parser = SitemapParser()

    def test_parse_urlset(self):
        xml = b"""<?xml version='1.0' encoding='UTF-8'?>
        <urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>
          <url><loc>https://example.com/a/</loc><lastmod>2026-01-01</lastmod></url>
          <url><loc>https://example.com/b?utm_source=x</loc></url>
        </urlset>"""
        child, urls = self.parser._parse_sitemap_document(xml, "application/xml", "https://example.com/sitemap.xml")
        self.assertEqual(child, [])
        self.assertEqual(len(urls), 2)
        self.assertEqual(urls[0].loc, "https://example.com/a")
        self.assertEqual(urls[1].loc, "https://example.com/b")

    def test_parse_sitemap_index(self):
        xml = b"""<?xml version='1.0' encoding='UTF-8'?>
        <sitemapindex xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>
          <sitemap><loc>https://example.com/s1.xml</loc></sitemap>
          <sitemap><loc>https://example.com/s2.xml</loc></sitemap>
        </sitemapindex>"""
        child, urls = self.parser._parse_sitemap_document(xml, "application/xml", "https://example.com/root.xml")
        self.assertEqual(len(child), 2)
        self.assertEqual(urls, [])


if __name__ == "__main__":
    unittest.main()
