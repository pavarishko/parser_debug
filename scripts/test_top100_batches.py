import asyncio
import json
import sys
import os
import csv
import argparse
from urllib.parse import urlparse
from collections import defaultdict
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

# Add project root to python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.test_domains_quality import load_domains, load_expected_urls_for_domains, test_domain

# Configuration
DEFAULT_DOMAINS_FILE = 'top100-domains.json'
URLS_FILE = 'all_urls_from_top100-domains.json'
DEFAULT_RESULTS_FILE = 'results/sitemap_quality_top100.csv'
CACHE_DIR = 'data/sitemaps_top100_cache'
CONCURRENCY = 1  # Number of parallel domains to process

async def process_domain_safe(domain: str, expected_urls: set, cache_dir: str, results_file: str, file_lock: asyncio.Lock, semaphore: asyncio.Semaphore, index: int, total: int):
    async with semaphore:
        print(f"[{index}/{total}] Starting {domain}...")
        try:
            result = await test_domain(domain, expected_urls, cache_dir)
            
            # Write result safely
            async with file_lock:
                with open(results_file, 'a', newline='', encoding='utf-8') as f:
                    fieldnames = ['domain', 'expected_count', 'sitemap_count', 'matches', 'missing', 'recall', 'precision', 'status']
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writerow(result)
            
            print(f"[{index}/{total}] Finished {domain}: {result['status']} (Recall: {result['recall']:.1f}%)")
        except Exception as e:
            print(f"[{index}/{total}] Error processing {domain}: {e}")

async def main():
    parser = argparse.ArgumentParser(description='Test sitemap quality for domains.')
    parser.add_argument('--domains', type=str, default=None, help='Path to JSON file with domains list')
    parser.add_argument('--output', type=str, default=DEFAULT_RESULTS_FILE, help='Path to output CSV file')
    args = parser.parse_args()

    domains_file = args.domains
    results_file = args.output

    # 1. Load domains
    if domains_file:
        print(f"Loading domains from {domains_file}...")
        with open(domains_file, 'r') as f:
            all_domains = json.load(f)
    elif os.path.exists('sorted_domains.json'):
        print(f"Loading sorted domains from sorted_domains.json...")
        with open('sorted_domains.json', 'r') as f:
            all_domains = json.load(f)
    else:
        print(f"Loading domains from {DEFAULT_DOMAINS_FILE}...")
        all_domains = await load_domains(DEFAULT_DOMAINS_FILE)
    
    if not all_domains:
        print("No domains found.")
        return
    
    print(f"Total domains to process: {len(all_domains)}")

    # 2. Load all URLs (once!)
    print(f"Loading all expected URLs from {URLS_FILE}...")
    # We pass set(all_domains) to filter only relevant URLs
    all_expected_urls = await load_expected_urls_for_domains(URLS_FILE, set(all_domains))
    
    # 3. Prepare results file
    os.makedirs(os.path.dirname(results_file), exist_ok=True)
    fieldnames = ['domain', 'expected_count', 'sitemap_count', 'matches', 'missing', 'recall', 'precision', 'status']
    
    # Initialize file with header if not exists, and load processed domains
    processed_domains = set()
    if os.path.exists(results_file):
        with open(results_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                processed_domains.add(row['domain'])
        print(f"Found {len(processed_domains)} already processed domains in {results_file}. Skipping them.")
    else:
        with open(results_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

    # 4. Process concurrently
    semaphore = asyncio.Semaphore(CONCURRENCY)
    file_lock = asyncio.Lock()
    tasks = []
    
    print(f"\nStarting parallel test with concurrency {CONCURRENCY}...")
    
    for i, domain in enumerate(all_domains):
        if domain in processed_domains:
            continue
            
        # Find expected URLs for this domain
        domain_key = domain.lower()
        if domain_key.startswith('www.'):
            domain_key = domain_key[4:]
            
        expected = all_expected_urls.get(domain_key, set())
        if not expected:
            expected = all_expected_urls.get(f"www.{domain_key}", set())
            
        task = asyncio.create_task(
            process_domain_safe(domain, expected, CACHE_DIR, results_file, file_lock, semaphore, i + 1, len(all_domains))
        )
        tasks.append(task)
    
    await asyncio.gather(*tasks)

    print(f"\nAll batches completed. Results saved to {results_file}")

if __name__ == "__main__":
    asyncio.run(main())
