#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import csv

input_file = 'results/sitemap_quality_filtered.csv'
output_file = 'results/sitemap_quality_summary.csv'

try:
    with open(input_file, 'r') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        
    total_domains = len(rows)
    found_sitemaps = 0
    recall_sum_found = 0.0
    recall_sum_total = 0.0
    
    for row in rows:
        recall = float(row['recall'])
        status = row['status']
        
        # Считаем sitemap найденным, если статус success (даже если recall 0, но sitemap был распарсен)
        # Или если recall > 0
        # В текущей логике: success означает, что sitemap был скачан и распарсен.
        # empty_sitemap - скачан, но пуст.
        # no_data - ошибка скачивания.
        
        if status == 'success' or (status == 'empty_sitemap' and recall > 0): 
             # empty_sitemap с recall > 0 быть не может, но на всякий случай.
             # Будем считать "найденным sitemap" только success, так как empty_sitemap бесполезен.
             pass

        if status == 'success':
            found_sitemaps += 1
            recall_sum_found += recall
            
        recall_sum_total += recall

    percent_found = (found_sitemaps / float(total_domains) * 100) if total_domains > 0 else 0
    avg_recall_found = (recall_sum_found / found_sitemaps) if found_sitemaps > 0 else 0
    avg_recall_total = (recall_sum_total / total_domains) if total_domains > 0 else 0
    
    print("Total domains: {}".format(total_domains))
    print("Found sitemaps: {} ({:.2f}%)".format(found_sitemaps, percent_found))
    print("Avg Recall (found): {:.2f}%".format(avg_recall_found))
    print("Avg Recall (total): {:.2f}%".format(avg_recall_total))
    
    with open(output_file, 'w') as f_out:
        writer = csv.writer(f_out)
        writer.writerow(['Metric', 'Value'])
        writer.writerow(['Total Domains', total_domains])
        writer.writerow(['Found Sitemaps Count', found_sitemaps])
        writer.writerow(['Found Sitemaps %', "{:.2f}%".format(percent_found)])
        writer.writerow(['Avg Recall (among found)', "{:.2f}%".format(avg_recall_found)])
        writer.writerow(['Avg Recall (total)', "{:.2f}%".format(avg_recall_total)])
        
    print("Summary saved to {}".format(output_file))

except Exception as e:
    print("Error: {}".format(e))