#!/usr/bin/env python3
"""
Анализ доменов с низким покрытием sitemap
"""

import pandas as pd
import json
from pathlib import Path
from urllib.parse import urlparse
import re

def analyze_low_coverage_domains():
    """Анализ доменов с низким покрытием (<90%)"""
    
    # Читаем результаты
    df = pd.read_csv('results/sitemap_quality_top100.csv')
    
    # Фильтруем домены с низким покрытием (<90%)
    low_coverage = df[df['recall'] < 90.0]
    
    print(f"Всего доменов: {len(df)}")
    print(f"Домены с низким покрытием (<90%): {len(low_coverage)}")
    print("\n" + "="*80)
    
    # Анализируем каждый проблемный домен
    for _, row in low_coverage.iterrows():
        domain = row['domain']
        recall = row['recall']
        expected = row['expected_count']
        sitemap_count = row['sitemap_count']
        matches = row['matches']
        status = row['status']
        
        print(f"\n🔍 Анализ домена: {domain}")
        print(f"   Покрытие: {recall:.1f}% (ожидалось: {expected}, найдено: {matches}, sitemap: {sitemap_count})")
        print(f"   Статус: {status}")
        
        # Проверяем наличие кэшированных URL
        cache_file = Path(f"data/sitemaps_top100_cache/{domain}_urls.jsonl")
        if cache_file.exists():
            print(f"   ✅ Кэш sitemap найден")
            
            # Читаем несколько URL для анализа
            urls = []
            with open(cache_file, 'r') as f:
                for i, line in enumerate(f):
                    if i >= 10:  # Ограничиваем количество для анализа
                        break
                    try:
                        data = json.loads(line.strip())
                        urls.append(data['loc'])
                    except:
                        continue
            
            if urls:
                print(f"   Примеры URL из sitemap:")
                for url in urls[:3]:
                    print(f"     - {url}")
        else:
            print(f"   ❌ Кэш sitemap не найден")
        
        # Проверяем наличие выборки URL
        sample_file = Path(f"data/sitemaps_top100_cache/{domain}_sample.json")
        if sample_file.exists():
            print(f"   ✅ Выборка URL найдена")
            
            # Читаем выборку
            try:
                with open(sample_file, 'r') as f:
                    sample_data = json.load(f)
                    sample_urls = sample_data.get('urls', [])
                    print(f"   Примеры URL из выборки:")
                    for url in sample_urls[:3]:
                        print(f"     - {url}")
            except:
                print(f"   ❌ Ошибка чтения выборки")
        else:
            print(f"   ❌ Выборка URL не найдена")
        
        # Определяем вероятную причину низкого покрытия
        determine_cause(domain, recall, expected, matches, sitemap_count, status)

def determine_cause(domain, recall, expected, matches, sitemap_count, status):
    """Определение причины низкого покрытия"""
    print(f"   🔍 Вероятная причина:")
    
    if status == 'empty_sitemap':
        print(f"     ❌ Пустой sitemap (sitemap_count=0)")
        return "empty_sitemap"
    
    elif status == 'no_data':
        print(f"     ❌ Нет данных (не удалось получить sitemap)")
        return "no_data"
    
    elif sitemap_count == 0:
        print(f"     ❌ Sitemap пустой или недоступен")
        return "sitemap_empty"
    
    elif matches == 0:
        print(f"     ❌ Нет совпадений между выборкой и sitemap")
        print(f"     💡 Возможные причины:")
        print(f"       - Разные структуры URL (региональные поддомены, параметры)")
        print(f"       - Разные домены в выборке и sitemap")
        print(f"       - Проблемы с нормализацией URL")
        return "no_matches"
    
    elif recall < 50:
        print(f"     ❌ Очень низкое покрытие (<50%)")
        print(f"     💡 Возможные причины:")
        print(f"       - Серьезные различия в структуре URL")
        print(f"       - Региональные поддомены не учтены")
        print(f"       - Динамические параметры в URL")
        return "very_low_coverage"
    
    elif recall < 90:
        print(f"     ⚠️ Умеренно низкое покрытие (50-90%)")
        print(f"     💡 Возможные причины:")
        print(f"       - Небольшие различия в структуре URL")
        print(f"       - Отсутствие некоторых страниц в sitemap")
        print(f"       - Проблемы с нормализацией параметров")
        return "moderate_low_coverage"
    
    else:
        print(f"     ✅ Покрытие в норме")
        return "normal"

def analyze_url_patterns(domain):
    """Анализ паттернов URL для домена"""
    cache_file = Path(f"data/sitemaps_top100_cache/{domain}_urls.jsonl")
    if not cache_file.exists():
        return
    
    print(f"\n   📊 Анализ паттернов URL для {domain}:")
    
    urls = []
    with open(cache_file, 'r') as f:
        for line in f:
            try:
                data = json.loads(line.strip())
                urls.append(data['loc'])
            except:
                continue
    
    if not urls:
        return
    
    # Анализируем структуру URL
    patterns = {}
    for url in urls[:100]:  # Ограничиваем для анализа
        parsed = urlparse(url)
        
        # Анализ пути
        path_parts = parsed.path.split('/')
        if len(path_parts) > 1:
            pattern = '/'.join(path_parts[:min(3, len(path_parts))])
            patterns[pattern] = patterns.get(pattern, 0) + 1
    
    # Выводим топ-5 паттернов
    top_patterns = sorted(patterns.items(), key=lambda x: x[1], reverse=True)[:5]
    print(f"   Топ-5 паттернов URL:")
    for pattern, count in top_patterns:
        print(f"     - {pattern} ({count} URL)")

if __name__ == "__main__":
    analyze_low_coverage_domains()