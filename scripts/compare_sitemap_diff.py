#!/usr/bin/env python3
"""Compare old/new sitemap URL dumps for high-recall domains.

Use case from current workflow:
- previous dump: data/sitemaps_top100_cache
- latest dump: all/data/sitemaps_top100_cache_new (or any provided path)
- quality table with recall: results/sitemap_quality_top100.csv

Outputs:
1) CSV summary with growth/churn metrics
2) Optional JSON examples for added/removed URLs
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Set

# Add project root to python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import normalize_url


def setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )


def load_urls_from_jsonl(file_path: Path, normalize: bool = True) -> Set[str]:
    urls: Set[str] = set()
    if not file_path.exists():
        return urls

    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                value = json.loads(line)
                if isinstance(value, dict):
                    # tolerate legacy format
                    value = value.get("loc") or value.get("url")
                if isinstance(value, str) and value:
                    urls.add(normalize_url(value) if normalize else value)
            except json.JSONDecodeError:
                logging.debug("Skipping invalid JSON line in %s", file_path)
                continue

    return urls


def load_high_recall_domains(results_csv: Path, threshold: float) -> List[str]:
    selected: List[str] = []
    with open(results_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            status = (row.get("status") or "").strip()
            if status != "success":
                continue
            try:
                recall = float(row.get("recall", 0) or 0)
            except ValueError:
                recall = 0.0
            if recall >= threshold:
                selected.append((row.get("domain") or "").strip())

    return [d for d in selected if d]


def compute_metrics(old_urls: Set[str], new_urls: Set[str]) -> Dict[str, float]:
    added = new_urls - old_urls
    removed = old_urls - new_urls
    common = old_urls & new_urls

    old_count = len(old_urls)
    new_count = len(new_urls)

    retention_rate = (len(common) / old_count * 100) if old_count else 0.0
    churn_rate = (len(added) + len(removed)) / max(1, old_count) * 100
    net_change = new_count - old_count
    net_change_pct = (net_change / old_count * 100) if old_count else (100.0 if new_count else 0.0)

    return {
        "old_count": old_count,
        "new_count": new_count,
        "added_count": len(added),
        "removed_count": len(removed),
        "common_count": len(common),
        "retention_rate": round(retention_rate, 2),
        "churn_rate": round(churn_rate, 2),
        "net_change": net_change,
        "net_change_pct": round(net_change_pct, 2),
        "added_urls": sorted(added)[:200],
        "removed_urls": sorted(removed)[:200],
    }


def compare_domains(
    domains: Iterable[str],
    old_dir: Path,
    new_dir: Path,
    normalize: bool,
) -> Dict[str, Dict[str, float]]:
    results: Dict[str, Dict[str, float]] = {}

    for domain in domains:
        old_file = _resolve_domain_file(old_dir, domain)
        new_file = _resolve_domain_file(new_dir, domain)

        old_urls = load_urls_from_jsonl(old_file, normalize=normalize)
        new_urls = load_urls_from_jsonl(new_file, normalize=normalize)

        metrics = compute_metrics(old_urls, new_urls)
        metrics["old_exists"] = old_file.exists()
        metrics["new_exists"] = new_file.exists()
        metrics["old_file"] = str(old_file)
        metrics["new_file"] = str(new_file)
        results[domain] = metrics

        logging.info(
            "%s: %s -> %s (added=%s removed=%s retention=%.2f%%)",
            domain,
            metrics["old_count"],
            metrics["new_count"],
            metrics["added_count"],
            metrics["removed_count"],
            metrics["retention_rate"],
        )

    return results


def _resolve_domain_file(base_dir: Path, domain: str) -> Path:
    """Resolve cache filename for domain with tiny compatibility fallbacks."""
    direct = base_dir / f"{domain}_urls.jsonl"
    if direct.exists():
        return direct

    # Some historical runs saved `www.` stripped names inconsistently.
    if domain.startswith("www."):
        alt = base_dir / f"{domain[4:]}_urls.jsonl"
        if alt.exists():
            return alt
    else:
        alt = base_dir / f"www.{domain}_urls.jsonl"
        if alt.exists():
            return alt

    return direct


def validate_inputs(results_csv: Path, old_dir: Path, new_dir: Path) -> None:
    if not results_csv.exists():
        raise FileNotFoundError(f"Results CSV not found: {results_csv}")
    if not old_dir.exists():
        raise FileNotFoundError(f"Old cache dir not found: {old_dir}")
    if not new_dir.exists():
        raise FileNotFoundError(f"New cache dir not found: {new_dir}")


def save_summary_csv(results: Dict[str, Dict[str, float]], output_csv: Path) -> None:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "domain",
        "old_exists",
        "new_exists",
        "old_count",
        "new_count",
        "added_count",
        "removed_count",
        "common_count",
        "retention_rate",
        "churn_rate",
        "net_change",
        "net_change_pct",
    ]

    with open(output_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for domain, data in sorted(results.items()):
            row = {"domain": domain}
            row.update({k: data[k] for k in fieldnames if k != "domain"})
            writer.writerow(row)


def save_details(results: Dict[str, Dict[str, float]], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for domain, data in results.items():
        payload = {
            "domain": domain,
            "added_urls_sample": data["added_urls"],
            "removed_urls_sample": data["removed_urls"],
        }
        with open(output_dir / f"{domain}_diff_sample.json", "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare old/new sitemap dumps for high-recall domains")
    parser.add_argument("--results-csv", default="results/sitemap_quality_top100.csv")
    parser.add_argument("--recall-threshold", type=float, default=80.0)
    parser.add_argument("--old-dir", default="data/sitemaps_top100_cache")
    parser.add_argument("--new-dir", default="all/data/sitemaps_top100_cache_new")
    parser.add_argument("--output-csv", default="results/sitemap_diff_high_recall.csv")
    parser.add_argument("--details-dir", default="results/sitemap_diff_high_recall_details")
    parser.add_argument("--no-normalize", action="store_true", help="Compare raw URLs without normalization")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    setup_logging(args.verbose)

    results_csv = Path(args.results_csv)
    old_dir = Path(args.old_dir)
    new_dir = Path(args.new_dir)

    validate_inputs(results_csv, old_dir, new_dir)

    domains = load_high_recall_domains(results_csv, args.recall_threshold)
    logging.info("Selected %d domains with recall >= %.1f", len(domains), args.recall_threshold)

    comparison = compare_domains(domains, old_dir, new_dir, normalize=not args.no_normalize)
    save_summary_csv(comparison, Path(args.output_csv))
    save_details(comparison, Path(args.details_dir))

    totals = {
        "old": sum(v["old_count"] for v in comparison.values()),
        "new": sum(v["new_count"] for v in comparison.values()),
        "added": sum(v["added_count"] for v in comparison.values()),
        "removed": sum(v["removed_count"] for v in comparison.values()),
    }
    logging.info(
        "TOTALS: old=%s new=%s added=%s removed=%s net=%s",
        totals["old"],
        totals["new"],
        totals["added"],
        totals["removed"],
        totals["new"] - totals["old"],
    )

    both_missing = sum(1 for r in comparison.values() if not r["old_exists"] and not r["new_exists"])
    if both_missing == len(comparison) and comparison:
        logging.warning(
            "All compared domains are missing in both directories. "
            "Check paths and run command in one line or with '\\' line continuations."
        )
        sample_domain = next(iter(comparison))
        logging.warning(
            "Sample expected files for %s: old=%s new=%s",
            sample_domain,
            comparison[sample_domain]["old_file"],
            comparison[sample_domain]["new_file"],
        )


if __name__ == "__main__":
    main()
