#!/usr/bin/env python3
"""
Анализ доменов с низким покрытием и выявление причин
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import pandas as pd
from pathlib import Path
from urllib.parse import urlparse
from utils import normalize_url, normalize_domain, urls_match

def analyze_low_coverage_domains():
    """Анализ доменов с низким покрытием"""
    
    # Читаем результаты
    df = pd.read_csv('results/sitemap_quality_top100.csv')
    
    # Фильтруем домены с низким покрытием
    low_coverage = df[(df['recall'] < 90) & (df['status'] == 'success')]
    
    print("🔍 Анализ доменов с низким покрытием (recall < 90%)")
    print("=" * 100)
    
    results = []
    
    for _, row in low_coverage.iterrows():
        domain = row['domain']
        recall = row['recall']
        expected = row['expected_count']
        matches = row['matches']
        missing = row['missing']
        
        print(f"\n📊 Домен: {domain}")
        print(f"   📈 Покрытие: {recall:.1f}% (ожидалось: {expected}, найдено: {matches}, пропущено: {missing})")
        
        # Проверяем наличие кэша sitemap
        cache_file = Path(f"data/sitemaps_top100_cache/{domain}_urls.jsonl")
        if not cache_file.exists():
            print(f"   ❌ Кэш sitemap не найден")
            results.append({
                'domain': domain,
                'recall': recall,
                'cause': 'no_sitemap_cache',
                'details': 'Файл кэша sitemap отсутствует'
            })
            continue
        
        # Читаем URL из sitemap
        sitemap_urls = []
        with open(cache_file, 'r') as f:
            for line in f:
                try:
                    data = json.loads(line.strip())
                    sitemap_urls.append(data['loc'])
                except:
                    continue
        
        if not sitemap_urls:
            print(f"   ❌ Нет URL в sitemap")
            results.append({
                'domain': domain,
                'recall': recall,
                'cause': 'empty_sitemap',
                'details': 'Sitemap пустой'
            })
            continue
        
        print(f"   ✅ Sitemap содержит {len(sitemap_urls)} URL")
        
        # Проверяем наличие выборки URL
        sample_file = Path(f"data/sitemaps_top100_cache/{domain}_sample.json")
        if not sample_file.exists():
            print(f"   ❌ Выборка URL не найдена")
            results.append({
                'domain': domain,
                'recall': recall,
                'cause': 'no_sample_data',
                'details': 'Файл с выборкой URL отсутствует'
            })
            continue
        
        # Читаем выборку
        try:
            with open(sample_file, 'r') as f:
                sample_data = json.load(f)
                sample_urls = sample_data.get('urls', [])
        except:
            print(f"   ❌ Ошибка чтения выборки")
            results.append({
                'domain': domain,
                'recall': recall,
                'cause': 'sample_read_error',
                'details': 'Ошибка при чтении файла выборки'
            })
            continue
        
        if not sample_urls:
            print(f"   ❌ Выборка пустая")
            results.append({
                'domain': domain,
                'recall': recall,
                'cause': 'empty_sample',
                'details': 'Выборка URL пустая'
            })
            continue
        
        print(f"   ✅ Выборка содержит {len(sample_urls)} URL")
        
        # Анализируем первые несколько URL для выявления паттернов
        print(f"   🔍 Анализ нормализации:")
        
        # Берем первые 3 URL из выборки и пытаемся найти их в sitemap
        analyzed_count = min(3, len(sample_urls))
        normalization_issues = []
        regional_issues = []
        missing_issues = []
        
        for i in range(analyzed_count):
            sample_url = sample_urls[i]
            normalized_sample = normalize_url(sample_url)
            
            # Ищем совпадение в sitemap
            found = False
            for sitemap_url in sitemap_urls[:100]:  # Проверяем первые 100 URL
                normalized_sitemap = normalize_url(sitemap_url)
                
                if urls_match(sample_url, sitemap_url):
                    found = True
                    break
                
                # Проверяем региональные поддомены
                parsed_sample = urlparse(normalized_sample)
                parsed_sitemap = urlparse(normalized_sitemap)
                
                if parsed_sample.path == parsed_sitemap.path and parsed_sample.query == parsed_sitemap.query:
                    # Путь и параметры совпадают, но домены разные - региональная проблема
                    if domain in parsed_sample.netloc and domain in parsed_sitemap.netloc:
                        regional_issues.append({
                            'sample': sample_url,
                            'sitemap': sitemap_url,
                            'sample_domain': parsed_sample.netloc,
                            'sitemap_domain': parsed_sitemap.netloc
                        })
            
            if not found:
                missing_issues.append(sample_url)
                
                # Анализируем нормализацию
                print(f"     ❌ Не найден: {sample_url}")
                print(f"       Нормализован: {normalized_sample}")
                
                # Проверяем, есть ли похожие URL в sitemap
                similar_urls = []
                for sitemap_url in sitemap_urls[:50]:
                    if sample_url.split('/')[-1] in sitemap_url or sitemap_url.split('/')[-1] in sample_url:
                        similar_urls.append(sitemap_url)
                
                if similar_urls:
                    print(f"       Похожие URL в sitemap:")
                    for similar in similar_urls[:3]:
                        print(f"         - {similar}")
        
        # Определяем причину низкого покрытия
        cause = "unknown"
        details = ""
        
        if regional_issues:
            cause = "regional_subdomains"
            regional_domains = set()
            for issue in regional_issues:
                regional_domains.add(issue['sitemap_domain'])
            details = f"Региональные поддомены: {', '.join(sorted(regional_domains))}"
            print(f"   🌍 Обнаружены региональные поддомены: {details}")
        
        elif missing_issues:
            cause = "normalization_issue"
            details = f"{len(missing_issues)} из {analyzed_count} URL не найдены в sitemap"
            print(f"   🔧 Проблемы с нормализацией: {details}")
        
        else:
            cause = "sample_mismatch"
            details = "Выборка не соответствует sitemap"
            print(f"   ⚠️  Несоответствие выборки и sitemap")
        
        results.append({
            'domain': domain,
            'recall': recall,
            'cause': cause,
            'details': details,
            'regional_domains': list(regional_domains) if regional_issues else []
        })
    
    return results

def generate_analysis_report(results):
    """Генерация отчета по анализу"""
    
    print("\n" + "=" * 100)
    print("📊 ОТЧЕТ ПО АНАЛИЗУ ДОМЕНОВ С НИЗКИМ ПОКРЫТИЕМ")
    print("=" * 100)
    
    # Группируем по причинам
    causes = {}
    for result in results:
        cause = result['cause']
        if cause not in causes:
            causes[cause] = []
        causes[cause].append(result)
    
    # Выводим статистику по причинам
    print(f"\n📈 Статистика по причинам низкого покрытия:")
    for cause, domains in causes.items():
        print(f"   {cause}: {len(domains)} доменов")
    
    # Детальный анализ по каждой причине
    print(f"\n🔍 Детальный анализ:")
    
    for cause, domains in causes.items():
        print(f"\n📋 Причина: {cause}")
        print("-" * 50)
        
        for domain in domains:
            print(f"   • {domain['domain']}: {domain['recall']:.1f}% - {domain['details']}")
            if domain.get('regional_domains'):
                print(f"     Региональные поддомены: {', '.join(domain['regional_domains'])}")

def main():
    """Основная функция"""
    results = analyze_low_coverage_domains()
    generate_analysis_report(results)
    
    # Сохраняем результаты в файл
    output_file = "results/low_coverage_analysis.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 Результаты сохранены в {output_file}")

if __name__ == "__main__":
    main()