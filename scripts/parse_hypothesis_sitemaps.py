#!/usr/bin/env python3
"""
Script for re-parsing sitemaps for hypothesis testing.
This script uses the existing sitemap parser to re-parse sitemaps for selected domains
and saves results to a new directory with timestamp.
"""

import asyncio
import json
import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import List

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from models import DomainInput
from analyzer import WebsiteAnalyzer
from config import HTTP_CONCURRENCY, HTTP_TIMEOUT, MAX_RETRIES, DOMAIN_DELAY


def setup_logging():
    """Configure logging."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stderr)
        ]
    )


async def parse_sitemaps_for_hypothesis(input_file: str, output_dir: str):
    """
    Parse sitemaps for hypothesis testing.
    
    Args:
        input_file: Path to JSON file with domains
        output_dir: Directory to save results
    """
    logger = logging.getLogger(__name__)
    
    # Load domains
    with open(input_file, 'r', encoding='utf-8') as f:
        domains_data = json.load(f)
    
    domains = [DomainInput(domain=item['domain']) for item in domains_data]
    logger.info(f"Loaded {len(domains)} domains for hypothesis testing")
    
    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Initialize analyzer with full sitemap parsing
    analyzer = WebsiteAnalyzer(
        concurrency=20,  # Reduced concurrency to avoid rate limiting
        domain_delay=DOMAIN_DELAY,
        timeout=HTTP_TIMEOUT,
        max_retries=MAX_RETRIES,
        fast_sitemap_mode=False  # Use full sitemap parsing
    )
    
    try:
        # Process domains one by one with progress tracking
        for i, domain_input in enumerate(domains, 1):
            logger.info(f"Processing domain {i}/{len(domains)}: {domain_input.domain}")
            
            try:
                # Analyze domain
                result = await analyzer.analyze_domain(domain_input)
                
                # Extract URLs from sitemap analysis
                urls = []
                if result.sitemap and result.sitemap.urls:
                    urls = [url.loc for url in result.sitemap.urls]
                
                # Save URLs to JSONL file
                output_file = output_path / f"{domain_input.domain}_urls.jsonl"
                with open(output_file, 'w', encoding='utf-8') as f:
                    for url in urls:
                        f.write(json.dumps(url, ensure_ascii=False) + '\n')
                
                logger.info(f"Saved {len(urls)} URLs for {domain_input.domain}")
                
            except Exception as e:
                logger.error(f"Failed to process {domain_input.domain}: {e}")
                # Create empty file for failed domains
                output_file = output_path / f"{domain_input.domain}_urls.jsonl"
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write("")
                
    finally:
        await analyzer.close()
    
    logger.info("Hypothesis testing sitemap parsing complete")


async def main():
    """Main function."""
    setup_logging()
    
    # Configuration
    input_file = "hypothesis_test_domains.json"
    timestamp = datetime.now().strftime("%Y-%m-%d")
    output_dir = f"data/sitemaps_top100_cache_{timestamp}"
    
    await parse_sitemaps_for_hypothesis(input_file, output_dir)


if __name__ == "__main__":
    asyncio.run(main())