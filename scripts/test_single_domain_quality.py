import asyncio
import json
import sys
import os
import re
import argparse
from urllib.parse import urlparse

# Add project root to python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from parsers.sitemap_full import SitemapParser
from config import HTTP_TIMEOUT
from utils import normalize_url

async def load_expected_urls(domain: str, json_path: str) -> set:
    expected_urls = set()
    print(f"Loading expected URLs for {domain} from {json_path}...")
    
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    url_data = json.loads(line)
                    url = url_data.get('url') if isinstance(url_data, dict) else url_data
                    
                    if url and domain in urlparse(url).netloc:
                        expected_urls.add(url)
                except json.JSONDecodeError:
                    continue
    except FileNotFoundError:
        print(f"Error: File {json_path} not found.")
        return set()
        
    print(f"Found {len(expected_urls)} expected URLs for {domain}")
    return expected_urls

async def test_domain(domain: str, urls_path: str):
    print(f"Starting test for domain: {domain}")
    print(f"Timeout configuration: {HTTP_TIMEOUT} seconds")
    
    expected_urls = await load_expected_urls(domain, urls_path)
    if not expected_urls:
        print("Warning: No expected URLs found. Proceeding anyway to check sitemap discovery.")

    # Normalize expected URLs for comparison
    normalized_expected = {normalize_url(u, remove_all_query=True) for u in expected_urls}
    
    # Check cache first
    cache_path = f"data/sitemaps_top100_cache/{domain}_urls.jsonl"
    sitemap_urls_count = 0
    found_urls = set()
    
    if os.path.exists(cache_path):
        print(f"Using cached sitemap from {cache_path}")
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        url = json.loads(line)
                        sitemap_urls_count += 1
                        
                        # Normalize and check against expected
                        norm_url = normalize_url(url, remove_all_query=True)
                        
                        if norm_url in normalized_expected:
                            found_urls.add(norm_url)
                            
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            print(f"Error reading cache: {e}")
    else:
        print(f"Cache not found. Fetching sitemap for {domain}...")
        parser = SitemapParser()
        result = await parser.parse_from_domain(domain)
        
        if not result.urls:
            print(f"No URLs found in sitemap for {domain} (status: {result.status})")
        else:
            for url_obj in result.urls:
                if url_obj and url_obj.loc:
                    sitemap_urls_count += 1
                    norm_url = normalize_url(url_obj.loc, remove_all_query=True)
                    if norm_url in normalized_expected:
                        found_urls.add(norm_url)

    print(f"Found {sitemap_urls_count} URLs in sitemap")
    
    found_count = len(found_urls)
    missing_count = len(expected_urls) - found_count
    recall = (found_count / len(expected_urls) * 100) if expected_urls else 0
    
    print("\n" + "="*50)
    print(f"RESULTS FOR {domain}")
    print("="*50)
    print(f"Expected URLs (from JSON): {len(expected_urls)}")
    print(f"Found in Sitemap (Total): {sitemap_urls_count}")
    print(f"Matches: {found_count}")
    print(f"Missing: {missing_count}")
    print(f"Recall: {recall:.2f}%")
    
    if missing_count > 0:
        print("\n--- Missing URLs Analysis ---")
        print(f"Showing first {min(10, missing_count)} missing URLs:")
        
        missing_list = []
        for url in expected_urls:
            norm = normalize_url(url, remove_all_query=True)
            if norm not in found_urls:
                missing_list.append(url)
                
        for i, url in enumerate(missing_list[:10]):
            print(f"{i+1}. {url}")
            print(f"   Normalized: {normalize_url(url, remove_all_query=True)}")

    print("="*50)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Test sitemap quality for a single domain.')
    parser.add_argument('--domain', required=True, help='Domain to test')
    parser.add_argument('--urls', default='all_urls_from_top100-domains.json', help='Path to JSON file with expected URLs')
    
    args = parser.parse_args()
    
    asyncio.run(test_domain(args.domain, args.urls))