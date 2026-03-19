#!/usr/bin/env python3
"""
Script for analyzing hypothesis test results about new offers appearing in sitemaps.
Generates statistical analysis and comprehensive report.
"""

import json
import csv
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List
from statistics import mean, median, stdev


def setup_logging():
    """Configure logging."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def load_diff_results(csv_file: Path) -> List[Dict]:
    """Load diff results from CSV file."""
    results = []
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Convert numeric fields
            row['old_count'] = int(row['old_count'])
            row['new_count'] = int(row['new_count'])
            row['added_count'] = int(row['added_count'])
            row['removed_count'] = int(row['removed_count'])
            row['net_change'] = int(row['net_change'])
            row['change_percent'] = float(row['change_percent'])
            row['common_count'] = int(row['common_count'])
            row['old_file_exists'] = row['old_file_exists'] == 'True'
            row['new_file_exists'] = row['new_file_exists'] == 'True'
            results.append(row)
    return results


def calculate_statistics(results: List[Dict]) -> Dict:
    """Calculate statistical metrics."""
    added_counts = [r['added_count'] for r in results]
    removed_counts = [r['removed_count'] for r in results]
    net_changes = [r['net_change'] for r in results]
    change_percents = [r['change_percent'] for r in results if r['change_percent'] != float('inf')]
    
    stats = {
        'total_domains': len(results),
        'domains_with_growth': sum(1 for r in results if r['net_change'] > 0),
        'domains_with_decline': sum(1 for r in results if r['net_change'] < 0),
        'domains_no_change': sum(1 for r in results if r['net_change'] == 0),
        
        'total_added': sum(added_counts),
        'total_removed': sum(removed_counts),
        'total_net_change': sum(net_changes),
        
        'avg_added': round(mean(added_counts), 2),
        'median_added': round(median(added_counts), 2),
        'max_added': max(added_counts),
        'min_added': min(added_counts),
        
        'avg_removed': round(mean(removed_counts), 2),
        'median_removed': round(median(removed_counts), 2),
        'max_removed': max(removed_counts),
        'min_removed': min(removed_counts),
        
        'avg_net_change': round(mean(net_changes), 2),
        'median_net_change': round(median(net_changes), 2),
        'max_net_change': max(net_changes),
        'min_net_change': min(net_changes),
        
        'avg_change_percent': round(mean(change_percents), 2) if change_percents else 0,
        'median_change_percent': round(median(change_percents), 2) if change_percents else 0,
    }
    
    # Add standard deviation if we have enough data
    if len(added_counts) > 1:
        stats['std_added'] = round(stdev(added_counts), 2)
    if len(removed_counts) > 1:
        stats['std_removed'] = round(stdev(removed_counts), 2)
    if len(net_changes) > 1:
        stats['std_net_change'] = round(stdev(net_changes), 2)
    
    return stats


def get_top_domains(results: List[Dict], metric: str, n: int = 10) -> List[Dict]:
    """Get top N domains by specified metric."""
    return sorted(results, key=lambda x: x[metric], reverse=True)[:n]


def generate_markdown_report(stats: Dict, top_growth: List[Dict], top_decline: List[Dict], 
                            top_added: List[Dict], top_removed: List[Dict]) -> str:
    """Generate markdown report."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    report = f"""# Sitemap Hypothesis Test Report

**Generated:** {timestamp}

## Executive Summary

This report analyzes the hypothesis that new offers appear in sitemaps over time. 
The test compared sitemap data from 10 days ago with fresh data for 20 top e-commerce domains.

### Key Findings

- **Total domains analyzed:** {stats['total_domains']}
- **Domains with URL growth:** {stats['domains_with_growth']} ({stats['domains_with_growth']/stats['total_domains']*100:.1f}%)
- **Domains with URL decline:** {stats['domains_with_decline']} ({stats['domains_with_decline']/stats['total_domains']*100:.1f}%)
- **Domains with no change:** {stats['domains_no_change']} ({stats['domains_no_change']/stats['total_domains']*100:.1f}%)

### Overall Statistics

| Metric | Value |
|--------|-------|
| **Total URLs added** | {stats['total_added']:,} |
| **Total URLs removed** | {stats['total_removed']:,} |
| **Net change** | {stats['total_net_change']:+,} |
| **Average URLs added per domain** | {stats['avg_added']:,} |
| **Median URLs added per domain** | {stats['median_added']:,} |
| **Average URLs removed per domain** | {stats['avg_removed']:,} |
| **Median URLs removed per domain** | {stats['median_removed']:,} |
| **Average net change per domain** | {stats['avg_net_change']:+,} |
| **Median net change per domain** | {stats['median_net_change']:+,} |
| **Average change percentage** | {stats['avg_change_percent']:+.2f}% |
| **Median change percentage** | {stats['median_change_percent']:+.2f}% |

## Top 10 Domains by URL Growth

| Rank | Domain | Old Count | New Count | Added | Removed | Net Change | Change % |
|------|--------|-----------|-----------|-------|---------|------------|----------|
"""
    for i, domain in enumerate(top_growth, 1):
        report += f"| {i} | {domain['domain']} | {domain['old_count']:,} | {domain['new_count']:,} | +{domain['added_count']:,} | -{domain['removed_count']:,} | {domain['net_change']:+,} | {domain['change_percent']:+.2f}% |\n"
    
    report += "\n## Top 10 Domains by URL Decline\n\n"
    report += "| Rank | Domain | Old Count | New Count | Added | Removed | Net Change | Change % |\n"
    report += "|------|--------|-----------|-----------|-------|---------|------------|----------|\n"
    for i, domain in enumerate(top_decline, 1):
        report += f"| {i} | {domain['domain']} | {domain['old_count']:,} | {domain['new_count']:,} | +{domain['added_count']:,} | -{domain['removed_count']:,} | {domain['net_change']:+,} | {domain['change_percent']:+.2f}% |\n"
    
    report += "\n## Top 10 Domains by New URLs Added\n\n"
    report += "| Rank | Domain | URLs Added | URLs Removed | Net Change |\n"
    report += "|------|--------|-----------|--------------|------------|\n"
    for i, domain in enumerate(top_added, 1):
        report += f"| {i} | {domain['domain']} | +{domain['added_count']:,} | -{domain['removed_count']:,} | {domain['net_change']:+,} |\n"
    
    report += "\n## Top 10 Domains by URLs Removed\n\n"
    report += "| Rank | Domain | URLs Removed | URLs Added | Net Change |\n"
    report += "|------|--------|-------------|-----------|------------|\n"
    for i, domain in enumerate(top_removed, 1):
        report += f"| {i} | {domain['domain']} | -{domain['removed_count']:,} | +{domain['added_count']:,} | {domain['net_change']:+,} |\n"
    
    report += "\n## Hypothesis Validation\n\n"
    
    if stats['domains_with_growth'] > stats['domains_with_decline']:
        report += "### ✅ Hypothesis Supported\n\n"
        report += f"The data supports the hypothesis that new offers appear in sitemaps over time. "
        report += f"{stats['domains_with_growth']} out of {stats['total_domains']} domains ({stats['domains_with_growth']/stats['total_domains']*100:.1f}%) "
        report += f"showed net growth in URLs, with a total of {stats['total_added']:,} new URLs added across all domains.\n\n"
    elif stats['domains_with_growth'] < stats['domains_with_decline']:
        report += "### ❌ Hypothesis Not Supported\n\n"
        report += f"The data does not support the hypothesis. More domains ({stats['domains_with_decline']}) showed a decline in URLs "
        report += f"than growth ({stats['domains_with_growth']}). This could indicate:\n"
        report += f"- Seasonal changes in product catalogs\n"
        report += f"- Cleanup of old/outdated URLs\n"
        report += f"- Changes in sitemap generation strategies\n\n"
    else:
        report += "### ⚠️ Mixed Results\n\n"
        report += f"The results are inconclusive. Equal numbers of domains showed growth ({stats['domains_with_growth']}) "
        report += f"and decline ({stats['domains_with_decline']}). Further analysis with a larger sample or longer time period may be needed.\n\n"
    
    report += "## Recommendations\n\n"
    report += "1. **Monitor High-Growth Domains:** Focus on domains with significant URL growth for potential new offer discovery.\n"
    report += "2. **Investigate Decline Patterns:** Analyze domains with URL decline to understand if this represents seasonal changes or technical issues.\n"
    report += "3. **Regular Monitoring:** Implement regular sitemap monitoring to track URL changes over time.\n"
    report += "4. **URL Pattern Analysis:** Analyze the types of URLs being added/removed (product pages, category pages, etc.).\n"
    report += "5. **Expand Sample Size:** Consider testing with a larger sample of domains for more statistically significant results.\n\n"
    
    report += "---\n\n"
    report += "*This report was generated automatically by the sitemap hypothesis testing framework.*\n"
    
    return report


def main():
    """Main function."""
    setup_logging()
    
    # Configuration
    timestamp = datetime.now().strftime("%Y-%m-%d")
    csv_file = Path(f"results/sitemap_diff_analysis_{timestamp}.csv")
    report_file = Path(f"results/hypothesis_test_report_{timestamp}.md")
    
    # Load diff results
    logging.info(f"Loading diff results from {csv_file}")
    results = load_diff_results(csv_file)
    
    if not results:
        logging.error("No results found. Please run compare_sitemap_diff.py first.")
        return
    
    # Calculate statistics
    logging.info("Calculating statistics...")
    stats = calculate_statistics(results)
    
    # Get top domains
    top_growth = get_top_domains(results, 'net_change', 10)
    top_decline = get_top_domains(results, 'net_change', 10)
    top_decline = sorted(top_decline, key=lambda x: x['net_change'])  # Sort ascending for decline
    top_added = get_top_domains(results, 'added_count', 10)
    top_removed = get_top_domains(results, 'removed_count', 10)
    
    # Generate report
    logging.info("Generating report...")
    report = generate_markdown_report(stats, top_growth, top_decline, top_added, top_removed)
    
    # Save report
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    
    logging.info(f"Report saved to {report_file}")
    
    # Print summary to console
    logging.info(f"\n=== Hypothesis Test Summary ===")
    logging.info(f"Total domains: {stats['total_domains']}")
    logging.info(f"Domains with growth: {stats['domains_with_growth']} ({stats['domains_with_growth']/stats['total_domains']*100:.1f}%)")
    logging.info(f"Domains with decline: {stats['domains_with_decline']} ({stats['domains_with_decline']/stats['total_domains']*100:.1f}%)")
    logging.info(f"Total URLs added: {stats['total_added']:,}")
    logging.info(f"Total URLs removed: {stats['total_removed']:,}")
    logging.info(f"Net change: {stats['total_net_change']:+,}")
    logging.info(f"Average change per domain: {stats['avg_net_change']:+,.2f}")


if __name__ == "__main__":
    main()
