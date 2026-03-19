#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import csv
import os

INPUT_FILE = 'results/sitemap_quality_top100.csv'
OUTPUT_FILE = 'results/SITEMAP_QUALITY_TOP100_REPORT.md'

def generate_report():
    if not os.path.exists(INPUT_FILE):
        print(f"Error: Input file {INPUT_FILE} not found.")
        return

    rows = []
    with open(INPUT_FILE, 'r') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    total_domains = len(rows)
    success_count = 0
    empty_count = 0
    no_data_count = 0
    
    recall_sum = 0.0
    successful_rows = []
    
    for row in rows:
        status = row['status']
        recall = float(row['recall'])
        
        if status == 'success':
            success_count += 1
            recall_sum += recall
            successful_rows.append(row)
        elif status == 'empty_sitemap':
            empty_count += 1
        elif status == 'no_data':
            no_data_count += 1

    avg_recall = (recall_sum / success_count) if success_count > 0 else 0
    
    # Sort successful rows by recall (descending)
    successful_rows.sort(key=lambda x: float(x['recall']), reverse=True)

    with open(OUTPUT_FILE, 'w') as f:
        f.write("# Sitemap Quality Analysis Report (Top 100)\n\n")
        
        # 1. Overall Statistics
        f.write("## 1. Overall Statistics\n\n")
        f.write(f"- **Total Domains Processed:** {total_domains}\n")
        f.write(f"- **Successfully Parsed:** {success_count} ({success_count/total_domains*100:.1f}%)\n")
        f.write(f"- **Empty Sitemaps (Found but empty):** {empty_count} ({empty_count/total_domains*100:.1f}%)\n")
        f.write(f"- **No Data (Failed to fetch):** {no_data_count} ({no_data_count/total_domains*100:.1f}%)\n")
        f.write(f"- **Average Recall (among successful):** {avg_recall:.2f}%\n\n")
        
        # 2. Top Performers (100% Recall)
        f.write("## 2. Top Performers (100% Recall)\n\n")
        f.write("| Domain | URLs in Sitemap | Matches | Missing |\n")
        f.write("|---|---|---|---|\n")
        perfect_domains = [row for row in successful_rows if float(row['recall']) == 100.0]
        for row in perfect_domains:
            f.write(f"| {row['domain']} | {row['sitemap_count']} | {row['matches']} | {row['missing']} |\n")
        f.write("\n")

        # 3. High Performers (90-99% Recall)
        f.write("## 3. High Performers (90-99% Recall)\n\n")
        f.write("| Domain | Recall | URLs in Sitemap | Matches | Missing |\n")
        f.write("|---|---|---|---|---|\n")
        high_performers = [row for row in successful_rows if 90.0 <= float(row['recall']) < 100.0]
        for row in high_performers:
             f.write(f"| {row['domain']} | {float(row['recall']):.2f}% | {row['sitemap_count']} | {row['matches']} | {row['missing']} |\n")
        f.write("\n")

        # 4. Low Performers (< 50% Recall)
        f.write("## 4. Low Performers (< 50% Recall)\n\n")
        f.write("| Domain | Recall | URLs in Sitemap | Matches | Missing |\n")
        f.write("|---|---|---|---|---|\n")
        low_performers = [row for row in successful_rows if float(row['recall']) < 50.0]
        for row in low_performers:
             f.write(f"| {row['domain']} | {float(row['recall']):.2f}% | {row['sitemap_count']} | {row['matches']} | {row['missing']} |\n")
        f.write("\n")

        # 5. Failed / Empty Domains
        f.write("## 5. Failed / Empty Domains\n\n")
        f.write("| Domain | Status | Notes |\n")
        f.write("|---|---|---|\n")
        failed_rows = [row for row in rows if row['status'] != 'success']
        for row in failed_rows:
             f.write(f"| {row['domain']} | {row['status']} | - |\n")
        f.write("\n")
        
        # 6. Full Results Table
        f.write("## 6. Full Results Table\n\n")
        f.write("| Domain | Status | Recall | Expected | Found in Sitemap | Matches | Missing |\n")
        f.write("|---|---|---|---|---|---|---|\n")
        for row in rows:
            recall_val = f"{float(row['recall']):.2f}%" if row['recall'] else "N/A"
            f.write(f"| {row['domain']} | {row['status']} | {recall_val} | {row['expected_count']} | {row['sitemap_count']} | {row['matches']} | {row['missing']} |\n")

    print(f"Report generated: {OUTPUT_FILE}")

if __name__ == "__main__":
    generate_report()