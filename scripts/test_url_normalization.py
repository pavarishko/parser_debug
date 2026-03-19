#!/usr/bin/env python3
"""
Тестирование нормализации URL для проблемных доменов
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
from pathlib import Path
from urllib.parse import urlparse
from utils import normalize_url, normalize_domain

def test_problematic_domains():
    """Тестирование нормализации для доменов с низким покрытием"""
    
    problem_domains = [
        # Домены с 0% покрытия
        "budzdorov.ru", "emex.ru", "zhivika.ru", "santehnika-online.ru", 
        "okeydostavka.ru", "rigla.ru", "re-store.ru", "pitergsm.ru", "mosautoshina.ru",
        
        # Домены с очень низким покрытием
        "askona.ru", "asna.ru", "divan.ru", "gorzdrav.org", "limestore.com",
        "sunlight.net", "komus.ru", "kuper.ru", "lamoda.ru", "lavka.yandex.ru",
        "labirint.ru", "sima-land.ru", "vseinstrumenti.ru", "vprok.ru",
        "planetazdorovo.ru", "winelab.ru", "aptekiplus.ru", "flowwow.com"
    ]
    
    print("🔍 Тестирование нормализации URL для проблемных доменов")
    print("=" * 80)
    
    for domain in problem_domains:
        print(f"\n📊 Домен: {domain}")
        
        # Проверяем наличие кэша sitemap
        cache_file = Path(f"data/sitemaps_top100_cache/{domain}_urls.jsonl")
        if not cache_file.exists():
            print(f"   ❌ Кэш sitemap не найден")
            continue
            
        # Читаем несколько URL из sitemap
        sitemap_urls = []
        with open(cache_file, 'r') as f:
            for i, line in enumerate(f):
                if i >= 5:  # Ограничиваем количество для анализа
                    break
                try:
                    data = json.loads(line.strip())
                    sitemap_urls.append(data['loc'])
                except:
                    continue
        
        if not sitemap_urls:
            print(f"   ❌ Нет URL в sitemap")
            continue
            
        print(f"   ✅ Найдено {len(sitemap_urls)} URL в sitemap")
        
        # Анализируем нормализацию
        print(f"   🔍 Анализ нормализации:")
        for url in sitemap_urls[:3]:  # Анализируем первые 3 URL
            normalized = normalize_url(url)
            parsed_orig = urlparse(url)
            parsed_norm = urlparse(normalized)
            
            print(f"     Оригинал: {url}")
            print(f"     Нормализован: {normalized}")
            
            # Сравниваем компоненты
            if parsed_orig.netloc != parsed_norm.netloc:
                print(f"     ⚠️  Изменен домен: {parsed_orig.netloc} -> {parsed_norm.netloc}")
            
            if parsed_orig.path != parsed_norm.path:
                print(f"     ⚠️  Изменен путь: {parsed_orig.path} -> {parsed_norm.path}")
            
            if parsed_orig.query != parsed_norm.query:
                print(f"     ⚠️  Изменены параметры: {parsed_orig.query} -> {parsed_norm.query}")
            
            print()
        
        # Проверяем наличие выборки URL
        sample_file = Path(f"data/sitemaps_top100_cache/{domain}_sample.json")
        if sample_file.exists():
            print(f"   🔍 Сравнение с выборкой:")
            try:
                with open(sample_file, 'r') as f:
                    sample_data = json.load(f)
                    sample_urls = sample_data.get('urls', [])
                    
                    if sample_urls:
                        sample_url = sample_urls[0]  # Берем первый URL из выборки
                        normalized_sample = normalize_url(sample_url)
                        print(f"     Выборка: {sample_url}")
                        print(f"     Нормализована: {normalized_sample}")
                        
                        # Сравниваем с первым URL из sitemap
                        sitemap_url = sitemap_urls[0]
                        normalized_sitemap = normalize_url(sitemap_url)
                        
                        if normalized_sample == normalized_sitemap:
                            print(f"     ✅ URL совпадают после нормализации")
                        else:
                            print(f"     ❌ URL не совпадают после нормализации")
                            print(f"       Sitemap: {normalized_sitemap}")
                            print(f"       Выборка: {normalized_sample}")
            except Exception as e:
                print(f"     ❌ Ошибка чтения выборки: {e}")
        else:
            print(f"   ❌ Выборка URL не найдена")

def analyze_regional_subdomains():
    """Анализ региональных поддоменов в проблемных доменах"""
    
    print("\n" + "=" * 80)
    print("🔍 Анализ региональных поддоменов")
    print("=" * 80)
    
    domains_with_regional = [
        "askona.ru", "divan.ru", "lamoda.ru", "vseinstrumenti.ru", "planetazdorovo.ru"
    ]
    
    for domain in domains_with_regional:
        print(f"\n📊 Домен: {domain}")
        
        cache_file = Path(f"data/sitemaps_top100_cache/{domain}_urls.jsonl")
        if not cache_file.exists():
            continue
            
        # Собираем статистику по поддоменам
        subdomain_stats = {}
        with open(cache_file, 'r') as f:
            for line in f:
                try:
                    data = json.loads(line.strip())
                    url = data['loc']
                    parsed = urlparse(url)
                    subdomain = parsed.netloc
                    
                    if domain in subdomain and subdomain != domain:
                        # Извлекаем региональную часть
                        regional_part = subdomain.replace(f".{domain}", "")
                        subdomain_stats[regional_part] = subdomain_stats.get(regional_part, 0) + 1
                except:
                    continue
        
        if subdomain_stats:
            print(f"   📊 Статистика региональных поддоменов:")
            for subdomain, count in sorted(subdomain_stats.items(), key=lambda x: x[1], reverse=True)[:5]:
                print(f"     {subdomain}.{domain}: {count} URL")
        else:
            print(f"   ℹ️  Региональные поддомены не обнаружены")

if __name__ == "__main__":
    test_problematic_domains()
    analyze_regional_subdomains()