#!/usr/bin/env python3
"""
Script for comparing sitemap URLs between old and new parsing results.
Calculates diff metrics: added URLs, removed URLs, and net changes.
"""

import json
import csv
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Set


def setup_logging():
    """Configure logging."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def load_urls_from_jsonl(file_path: Path) -> Set[str]:
    """Load URLs from JSONL file."""
    urls = set()
    if file_path.exists():
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        url = json.loads(line)
                        if isinstance(url, str):
                            urls.add(url)
                    except json.JSONDecodeError:
                        logging.warning(f"Invalid JSON line in {file_path}: {line}")
    return urls


def compare_sitemaps(old_dir: Path, new_dir: Path, domains: List[str]) -> Dict[str, Dict]:
    """
    Compare sitemap URLs between old and new directories.
    
    Args:
        old_dir: Path to directory with old sitemap results
        new_dir: Path to directory with new sitemap results
        domains: List of domains to compare
        
    Returns:
        Dictionary with comparison results for each domain
    """
    results = {}
    
    for domain in domains:
        old_file = old_dir / f"{domain}_urls.jsonl"
        new_file = new_dir / f"{domain}_urls.jsonl"
        
        # Load URLs
        old_urls = load_urls_from_jsonl(old_file)
        new_urls = load_urls_from_jsonl(new_file)
        
        # Calculate diff
        added_urls = new_urls - old_urls
        removed_urls = old_urls - new_urls
        common_urls = old_urls & new_urls
        
        # Calculate metrics
        old_count = len(old_urls)
        new_count = len(new_urls)
        added_count = len(added_urls)
        removed_count = len(removed_urls)
        net_change = added_count - removed_count
        
        if old_count > 0:
            change_percent = (net_change / old_count) * 100
        else:
            change_percent = float('inf') if new_count > 0 else 0.0
        
        results[domain] = {
            'old_count': old_count,
            'new_count': new_count,
            'added_count': added_count,
            'removed_count': removed_count,
            'net_change': net_change,
            'change_percent': round(change_percent, 2),
            'common_count': len(common_urls),
            'added_urls': list(added_urls)[:100],  # Keep first 100 for analysis
            'removed_urls': list(removed_urls)[:100],  # Keep first 100 for analysis
            'old_file_exists': old_file.exists(),
            'new_file_exists': new_file.exists()
        }
        
        logging.info(f"{domain}: {old_count} → {new_count} URLs (+{added_count}, -{removed_count}, Δ{net_change})")
    
    return results


def save_diff_results(results: Dict[str, Dict], output_file: Path):
    """Save diff results to CSV file."""
    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        
        # Write header
        writer.writerow([
            'domain',
            'old_count',
            'new_count',
            'added_count',
            'removed_count',
            'net_change',
            'change_percent',
            'common_count',
            'old_file_exists',
            'new_file_exists'
        ])
        
        # Write data
        for domain, data in results.items():
            writer.writerow([
                domain,
                data['old_count'],
                data['new_count'],
                data['added_count'],
                data['removed_count'],
                data['net_change'],
                data['change_percent'],
                data['common_count'],
                data['old_file_exists'],
                data['new_file_exists']
            ])
    
    logging.info(f"Saved diff results to {output_file}")


def save_detailed_urls(results: Dict[str, Dict], output_dir: Path):
    """Save detailed URL changes for each domain."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    for domain, data in results.items():
        # Save added URLs
        if data['added_urls']:
            added_file = output_dir / f"{domain}_added_urls.json"
            with open(added_file, 'w', encoding='utf-8') as f:
                json.dump(data['added_urls'], f, ensure_ascii=False, indent=2)
        
        # Save removed URLs
        if data['removed_urls']:
            removed_file = output_dir / f"{domain}_removed_urls.json"
            with open(removed_file, 'w', encoding='utf-8') as f:
                json.dump(data['removed_urls'], f, ensure_ascii=False, indent=2)


def main():
    """Main function."""
    setup_logging()
    
    # Configuration
    domains_file = "hypothesis_test_domains.json"
    old_dir = Path("data/sitemaps_top100_cache")
    timestamp = datetime.now().strftime("%Y-%m-%d")
    new_dir = Path(f"data/sitemaps_top100_cache_{timestamp}")
    
    # Load domains
    with open(domains_file, 'r', encoding='utf-8') as f:
        domains_data = json.load(f)
    domains = [item['domain'] for item in domains_data]
    
    logging.info(f"Comparing sitemaps for {len(domains)} domains")
    
    # Compare sitemaps
    results = compare_sitemaps(old_dir, new_dir, domains)
    
    # Save results
    results_dir = Path("results")
    results_dir.mkdir(exist_ok=True)
    
    # Save CSV summary
    csv_file = results_dir / f"sitemap_diff_analysis_{timestamp}.csv"
    save_diff_results(results, csv_file)
    
    # Save detailed URL changes
    urls_dir = results_dir / f"sitemap_url_changes_{timestamp}"
    save_detailed_urls(results, urls_dir)
    
    # Print summary
    total_added = sum(data['added_count'] for data in results.values())
    total_removed = sum(data['removed_count'] for data in results.values())
    total_net_change = sum(data['net_change'] for data in results.values())
    
    logging.info(f"\n=== Summary ===")
    logging.info(f"Total domains compared: {len(results)}")
    logging.info(f"Total URLs added: {total_added}")
    logging.info(f"Total URLs removed: {total_removed}")
    logging.info(f"Net change: {total_net_change}")
    
    # Top domains by change
    domains_by_growth = sorted(results.items(), key=lambda x: x[1]['net_change'], reverse=True)[:5]
    logging.info(f"\nTop 5 domains by growth:")
    for domain, data in domains_by_growth:
        logging.info(f"  {domain}: +{data['added_count']} -{data['removed_count']} = Δ{data['net_change']}")


if __name__ == "__main__":
    main()