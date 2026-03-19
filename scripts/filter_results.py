import csv

target_domains = {
    "4lapy.ru", "apteka-april.ru", "coolclever.ru", "askona.ru",
    "av.ru", "divan.ru", "exist.ru", "citilink.ru", "goldapple.ru", "etm.ru",
    "dns-shop.ru", "eapteka.ru", "farmlend.ru", "autodoc.ru", "eldorado.ru",
    "limestore.com", "pm.ru", "ostin.com",
    "sokolov.ru", "sunlight.net", "officemag.ru", "petrovich.ru", "5ka.ru",
    "585zolotoy.ru", "auchan.ru", "faberlic.com", "detmir.ru", "hoff.ru",
    "holodilnik.ru", "komus.ru", "chitai-gorod.ru", "kuper.ru", "lamoda.ru",
    "lenta.com", "labirint.ru", "letu.ru", "minicen.ru", "miuz.ru", "megapteka.ru"
}

input_file = 'results/sitemap_quality_top100.csv'
output_file = 'results/sitemap_quality_filtered.csv'

try:
    with open(input_file, 'r', encoding='utf-8') as f_in, \
         open(output_file, 'w', encoding='utf-8', newline='') as f_out:
        
        reader = csv.DictReader(f_in)
        fieldnames = reader.fieldnames
        writer = csv.DictWriter(f_out, fieldnames=fieldnames)
        
        writer.writeheader()
        
        count = 0
        for row in reader:
            if row['domain'] in target_domains:
                writer.writerow(row)
                count += 1
                
    print(f"Filtered results saved to {output_file}")
    print(f"Total domains: {count}")
    
except Exception as e:
    print(f"Error: {e}")
