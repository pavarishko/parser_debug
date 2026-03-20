#!/usr/bin/env python3
import os
import json

cache_dir = "/home/krmoty/junk/krmoty/parser_debug/data/sitemaps_top100_cache"

domain_sizes = []

for filename in os.listdir(cache_dir):
    if filename.endswith("_urls.jsonl"):
        filepath = os.path.join(cache_dir, filename)
        domain = filename.replace("_urls.jsonl", "")
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                count = sum(1 for _ in f)
            domain_sizes.append((count, domain))
        except Exception as e:
            print(f"Error reading {filename}: {e}")

# Sort by count (ascending)
domain_sizes.sort()

# Print sorted list
for count, domain in domain_sizes:
    print(f"{count} {domain}")

# Create sorted domains list
sorted_domains = [domain for count, domain in domain_sizes]

# Save to JSON
output_file = "/home/krmoty/junk/krmoty/parser_debug/all/domains/top100-domains-sorted-by-size.json"
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(sorted_domains, f, indent=2, ensure_ascii=False)

print(f"\nSaved {len(sorted_domains)} domains to {output_file}")
