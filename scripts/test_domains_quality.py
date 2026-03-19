import asyncio
import json
import sys
import os
import csv
import re
import argparse
from urllib.parse import urlparse
from collections import defaultdict
from datetime import datetime

# Add project root to python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from parsers.sitemap_full import SitemapParser
from config import HTTP_TIMEOUT
from utils import normalize_url, urls_match_fuzzy

async def load_domains(json_path: str) -> list:
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: File {json_path} not found.")
        return []
    except json.JSONDecodeError:
        print(f"Error: File {json_path} is not valid JSON.")
        return []

async def load_expected_urls_for_domains(json_path: str, target_domains: set) -> dict:
    """
    Loads URLs from the large JSON file ONLY for the specified domains.
    Returns a dict: {domain: set(urls)}
    """
    print(f"Loading expected URLs from {json_path} for {len(target_domains)} domains...")
    domain_urls = defaultdict(set)
    count = 0
    
    # Normalize target domains for matching (remove www)
    normalized_targets = set()
    for d in target_domains:
        d = d.lower()
        if d.startswith('www.'):
            d = d[4:]
        normalized_targets.add(d)
    
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    url_data = json.loads(line)
                    url = url_data.get('url') if isinstance(url_data, dict) else url_data
                    
                    if url:
                        # Extract domain to group
                        parsed = urlparse(url)
                        domain = parsed.netloc.lower()
                        # Remove www. if present for better matching key
                        if domain.startswith('www.'):
                            domain = domain[4:]
                        
                        # Only store if it matches one of our target domains
                        if domain in normalized_targets:
                            domain_urls[domain].add(url)
                            count += 1
                        
                        if count > 0 and count % 10000 == 0:
                            print(f"Loaded {count} relevant URLs...", end='\r')
                            
                except json.JSONDecodeError:
                    continue
    except FileNotFoundError:
        print(f"Error: File {json_path} not found.")
        return {}
        
    print(f"\nFinished loading {count} URLs for {len(domain_urls)} domains.")
    return domain_urls

async def get_sitemap_urls(domain: str, cache_dir: str) -> list:
    """
    Get sitemap URLs either from cache file or by parsing.
    """
    os.makedirs(cache_dir, exist_ok=True)
    cache_file = os.path.join(cache_dir, f"{domain}_urls.jsonl")
    
    # 1. Try to load from cache
    if os.path.exists(cache_file):
        print(f"Loading cached sitemap URLs for {domain}...")
        urls = []
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        urls.append(json.loads(line))
            print(f"Loaded {len(urls)} URLs from cache.")
            return urls
        except Exception as e:
            print(f"Error loading cache for {domain}: {e}")
            # If cache is corrupted, re-parse
            pass

    # 2. Parse if not cached
    print(f"Parsing sitemap for {domain}...")
    parser = SitemapParser()
    result = await parser.parse_from_domain(domain)
    if not result.urls:
        print(f"No URLs found in sitemap for {domain} (status: {result.status})")
        return []
        
    sitemap_urls = [url.loc for url in result.urls if url and url.loc]
    print(f"Found {len(sitemap_urls)} URLs in sitemap.")
    
    # 3. Save to cache
    try:
        with open(cache_file, 'w', encoding='utf-8') as f:
            for url in sitemap_urls:
                f.write(json.dumps(url) + '\n')
        print(f"Saved URLs to {cache_file}")
    except Exception as e:
        print(f"Error saving cache for {domain}: {e}")
        
    return sitemap_urls

async def test_domain(domain: str, expected_urls: set, cache_dir: str) -> dict:
    print(f"\nTesting domain: {domain}")
    print(f"Expected URLs: {len(expected_urls)}")
    
    # Парсим sitemap даже если нет ожидаемых URL
    # if not expected_urls:
    #     print(f"Skipping {domain} - no expected URLs found in source file.")
    #     return {
    #         'domain': domain,
    #         'expected_count': 0,
    #         'sitemap_count': 0,
    #         'matches': 0,
    #         'missing': 0,
    #         'recall': 0.0,
    #         'status': 'no_data'
    #     }

    try:
        sitemap_urls = await get_sitemap_urls(domain, cache_dir)
        
        if sitemap_urls is None:
             return {
                'domain': domain,
                'expected_count': len(expected_urls),
                'sitemap_count': 0,
                'matches': 0,
                'missing': len(expected_urls),
                'recall': 0.0,
                'status': 'error: sitemap fetch failed'
            }

        if not sitemap_urls:
             return {
                'domain': domain,
                'expected_count': len(expected_urls),
                'sitemap_count': 0,
                'matches': 0,
                'missing': len(expected_urls),
                'recall': 0.0,
                'status': 'empty_sitemap'
            }

        # Если нет ожидаемых URL, просто возвращаем информацию о sitemap
        if not expected_urls:
            return {
                'domain': domain,
                'expected_count': 0,
                'sitemap_count': len(sitemap_urls),
                'matches': 0,
                'missing': 0,
                'recall': 0.0,
                'status': 'no_expected_urls'
            }

        # Normalize sitemap URLs for comparison (remove all query params)
        sitemap_set = {normalize_url(u, remove_all_query=True) for u in sitemap_urls}
        
        # Optimization: create a set of "fuzzy" sitemap paths (stripped punctuation)
        sitemap_fuzzy_set = {re.sub(r'[-_]', '', urlparse(u).path) for u in sitemap_set}
        
        found_and_valid = 0
        not_found = 0
        
        for expected in expected_urls:
            normalized_expected = normalize_url(expected, remove_all_query=True)
            
            # 1. Exact match (fastest)
            if normalized_expected in sitemap_set:
                found_and_valid += 1
                continue
                
            # 2. Fuzzy match (check if stripped path exists)
            expected_path_fuzzy = re.sub(r'[-_]', '', urlparse(normalized_expected).path)
            if expected_path_fuzzy in sitemap_fuzzy_set:
                found_and_valid += 1
            else:
                not_found += 1
                
        total_expected = len(expected_urls)
        recall = (found_and_valid / total_expected * 100) if total_expected > 0 else 0
        
        print(f"Recall: {recall:.2f}% ({found_and_valid}/{total_expected})")
        
        return {
            'domain': domain,
            'expected_count': total_expected,
            'sitemap_count': len(sitemap_urls),
            'matches': found_and_valid,
            'missing': not_found,
            'recall': recall,
            'status': 'success'
        }
        
    except Exception as e:
        print(f"Error testing {domain}: {e}")
        return {
            'domain': domain,
            'expected_count': len(expected_urls),
            'sitemap_count': 0,
            'matches': 0,
            'missing': len(expected_urls),
            'recall': 0.0,
            'status': f'error: {str(e)}'
        }

async def main():
    parser = argparse.ArgumentParser(description='Test sitemap quality for a list of domains.')
    parser.add_argument('--domains', required=True, help='Path to JSON file with list of domains')
    parser.add_argument('--urls', required=True, help='Path to JSONL file with expected URLs')
    parser.add_argument('--output', default='results/sitemap_quality.csv', help='Path to output CSV file')
    parser.add_argument('--cache-dir', default='data/sitemaps_cache', help='Directory to cache sitemap URLs')
    
    args = parser.parse_args()
    
    # 1. Load domains list
    domains = await load_domains(args.domains)
    if not domains:
        print("No domains to test.")
        return

    print(f"Loaded {len(domains)} domains to test.")

    # 2. Load expected URLs (filtered by domains)
    all_expected_urls = await load_expected_urls_for_domains(args.urls, set(domains))
    
    # 3. Prepare results file
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    fieldnames = ['domain', 'expected_count', 'sitemap_count', 'matches', 'missing', 'recall', 'status']
    
    # Write header if file doesn't exist or we are starting fresh
    # Here we overwrite for simplicity of a new run
    with open(args.output, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

    print(f"\nStarting test...")
    
    # 4. Iterate and test
    for i, domain in enumerate(domains):
        print(f"\n[{i+1}/{len(domains)}] Processing {domain}...")
        
        # Find expected URLs for this domain
        domain_key = domain.lower()
        if domain_key.startswith('www.'):
            domain_key = domain_key[4:]
            
        expected = all_expected_urls.get(domain_key, set())
        
        # If not found, try looking for www. version
        if not expected:
            expected = all_expected_urls.get(f"www.{domain_key}", set())
            
        try:
            result = await test_domain(domain, expected, args.cache_dir)
        except Exception as e:
            print(f"Error testing {domain}: {e}")
            result = {
                'domain': domain,
                'expected_count': len(expected),
                'sitemap_count': 0,
                'matches': 0,
                'missing': len(expected),
                'recall': 0.0,
                'status': f'error: {str(e)}'
            }
        
        # Save result immediately
        with open(args.output, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writerow(result)
            
    print(f"\nTest completed. Results saved to {args.output}")

if __name__ == "__main__":
    asyncio.run(main())