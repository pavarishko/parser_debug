import asyncio
import aiohttp
import json
import csv
import os
import sys
from urllib.parse import urlparse

# Add project root to python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from parsers.sitemap_full import SitemapParser

DOMAINS_FILE = 'top100-domains.json'
RESULTS_FILE = 'results/sitemap_quality_top100.csv'

async def get_remaining_domains():
    # Load all domains
    with open(DOMAINS_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
        # Handle both list of dicts and list of strings if needed, though top100 is list of dicts
        all_domains = [d['domain'] if isinstance(d, dict) else d for d in data]
    
    # Load processed domains
    processed = set()
    if os.path.exists(RESULTS_FILE):
        with open(RESULTS_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                processed.add(row['domain'])
    
    remaining = [d for d in all_domains if d not in processed]
    return remaining

async def estimate_size(domain, session):
    parser = SitemapParser()
    
    # Try to find sitemap URL from robots.txt
    # Accessing private method for quick estimation
    sitemap_url = await parser._get_sitemap_from_robots(domain, session)
    
    if not sitemap_url:
        # Try common paths
        common_paths = [
            f"https://{domain}/sitemap.xml",
            f"https://{domain}/sitemap_index.xml",
        ]
        for url in common_paths:
            try:
                async with session.head(url, timeout=5) as resp:
                    if resp.status == 200:
                        sitemap_url = url
                        break
            except:
                pass
    
    if not sitemap_url:
        return domain, 0, "not_found"

    try:
        # Get Content-Length if possible
        async with session.head(sitemap_url, timeout=10) as resp:
            size = int(resp.headers.get('Content-Length', 0))
            
            # If size is small, it might be an index. Let's peek at content.
            if size < 1024 * 1024: # < 1MB
                 async with session.get(sitemap_url, timeout=10) as get_resp:
                     content = await get_resp.text()
                     # Count <sitemap> tags (indicates index) or <url> tags
                     sitemap_count = content.count('<sitemap>')
                     url_count = content.count('<url>')
                     
                     if sitemap_count > 0:
                         # It's an index. Rough estimate: each child has ~10k URLs?
                         # Let's just use child count as complexity metric
                         return domain, sitemap_count * 10000, f"index ({sitemap_count} children)"
                     else:
                         return domain, url_count, f"direct ({url_count} urls)"
            
            return domain, size, f"size ({size} bytes)"
            
    except Exception as e:
        return domain, 999999999, f"error: {str(e)}"

async def main():
    domains = await get_remaining_domains()
    print(f"Found {len(domains)} remaining domains.")
    
    results = []
    async with aiohttp.ClientSession() as session:
        tasks = [estimate_size(d, session) for d in domains]
        for coro in asyncio.as_completed(tasks):
            res = await coro
            results.append(res)
            print(f"Checked {res[0]}: {res[2]}")
            
    # Sort by estimated size
    results.sort(key=lambda x: x[1])
    
    print("\nSorted domains (smallest to largest):")
    for domain, size, info in results:
        print(f"{domain}: {info}")
        
    # Save sorted list to file for batch processing
    sorted_domains = [r[0] for r in results]
    with open('sorted_domains.json', 'w') as f:
        json.dump(sorted_domains, f, indent=2)
    print(f"\nSaved {len(sorted_domains)} sorted domains to sorted_domains.json")

if __name__ == "__main__":
    asyncio.run(main())