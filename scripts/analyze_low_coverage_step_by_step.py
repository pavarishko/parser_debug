#!/usr/bin/env python3
"""
Анализ доменов с низким покрытием - пошаговый подход
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import pandas as pd
from pathlib import Path
from urllib.parse import urlparse
from utils import normalize_url, normalize_domain, urls_match

def analyze_single_domain(domain, recall, expected, matches, missing):
    """Анализ одного домена"""
    
    print(f"\n📊 Домен: {domain}")
    print(f"   📈 Покрытие: {recall:.1f}% (ожидалось: {expected}, найдено: {matches}, пропущено: {missing})")
    
    result = {
        'domain': domain,
        'recall': recall,
        'expected': expected,
        'matches': matches,
        'missing': missing,
        'cause': 'unknown',
        'details': '',
        'regional_domains': [],
        'normalization_issues': []
    }
    
    # Проверяем наличие кэша sitemap
    cache_file = Path(f"data/sitemaps_top100_cache/{domain}_urls.jsonl")
    if not cache_file.exists():
        print(f"   ❌ Кэш sitemap не найден")
        result['cause'] = 'no_sitemap_cache'
        result['details'] = 'Файл кэша sitemap отсутствует'
        return result
    
    # Читаем первые 100 URL из sitemap
    sitemap_urls = []
    with open(cache_file, 'r') as f:
        for i, line in enumerate(f):
            if i >= 100:  # Ограничиваем для производительности
                break
            try:
                # Пробуем прочитать как JSON объект
                data = json.loads(line.strip())
                if isinstance(data, dict) and 'loc' in data:
                    sitemap_urls.append(data['loc'])
                else:
                    # Если это строка URL, используем как есть
                    sitemap_urls.append(line.strip().strip('"'))
            except:
                # Если не JSON, используем строку как URL
                sitemap_urls.append(line.strip().strip('"'))
    
    if not sitemap_urls:
        print(f"   ❌ Нет URL в sitemap")
        result['cause'] = 'empty_sitemap'
        result['details'] = 'Sitemap пустой'
        return result
    
    print(f"   ✅ Sitemap содержит URL (проверено первых {len(sitemap_urls)})")
    
    # Проверяем наличие выборки URL
    sample_file = Path(f"data/sitemaps_top100_cache/{domain}_sample.json")
    if not sample_file.exists():
        print(f"   ❌ Выборка URL не найдена")
        result['cause'] = 'no_sample_data'
        result['details'] = 'Файл с выборкой URL отсутствует'
        return result
    
    # Читаем выборку
    try:
        with open(sample_file, 'r') as f:
            sample_data = json.load(f)
            sample_urls = sample_data.get('urls', [])
    except:
        print(f"   ❌ Ошибка чтения выборки")
        result['cause'] = 'sample_read_error'
        result['details'] = 'Ошибка при чтении файла выборки'
        return result
    
    if not sample_urls:
        print(f"   ❌ Выборка пустая")
        result['cause'] = 'empty_sample'
        result['details'] = 'Выборка URL пустая'
        return result
    
    print(f"   ✅ Выборка содержит {len(sample_urls)} URL")
    
    # Анализируем первые 5 URL из выборки
    print(f"   🔍 Анализ нормализации:")
    
    analyzed_count = min(5, len(sample_urls))
    regional_issues = []
    missing_issues = []
    normalization_examples = []
    
    for i in range(analyzed_count):
        sample_url = sample_urls[i]
        normalized_sample = normalize_url(sample_url)
        
        # Ищем совпадение в sitemap
        found = False
        for sitemap_url in sitemap_urls:
            if urls_match(sample_url, sitemap_url):
                found = True
                break
            
            # Проверяем региональные поддомены
            normalized_sitemap = normalize_url(sitemap_url)
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
            
            # Сохраняем пример для анализа
            normalization_examples.append({
                'original': sample_url,
                'normalized': normalized_sample
            })
            
            print(f"     ❌ Не найден: {sample_url[:80]}...")
            print(f"       Нормализован: {normalized_sample[:80]}...")
    
    # Определяем причину низкого покрытия
    if regional_issues:
        result['cause'] = 'regional_subdomains'
        regional_domains = set()
        for issue in regional_issues:
            regional_domains.add(issue['sitemap_domain'])
        result['regional_domains'] = list(regional_domains)
        result['details'] = f"Региональные поддомены: {', '.join(sorted(regional_domains))}"
        print(f"   🌍 Обнаружены региональные поддомены: {result['details']}")
    
    elif missing_issues:
        result['cause'] = 'normalization_issue'
        result['details'] = f"{len(missing_issues)} из {analyzed_count} URL не найдены в sitemap"
        result['normalization_issues'] = normalization_examples
        print(f"   🔧 Проблемы с нормализацией: {result['details']}")
    
    else:
        result['cause'] = 'sample_mismatch'
        result['details'] = "Выборка не соответствует sitemap"
        print(f"   ⚠️  Несоответствие выборки и sitemap")
    
    return result

def main():
    """Основная функция"""
    
    # Читаем результаты
    df = pd.read_csv('results/sitemap_quality_top100.csv')
    
    # Фильтруем домены с низким покрытием
    low_coverage = df[(df['recall'] < 90) & (df['status'] == 'success')]
    
    print("🔍 Анализ доменов с низким покрытием (recall < 90%)")
    print("=" * 100)
    print(f"Найдено доменов для анализа: {len(low_coverage)}")
    
    results = []
    
    # Анализируем по одному домену
    for i, (_, row) in enumerate(low_coverage.iterrows()):
        domain = row['domain']
        recall = row['recall']
        expected = row['expected_count']
        matches = row['matches']
        missing = row['missing']
        
        print(f"\n[{i+1}/{len(low_coverage)}] Анализ домена: {domain}")
        
        try:
            result = analyze_single_domain(domain, recall, expected, matches, missing)
            results.append(result)
            
            # Сохраняем промежуточные результаты
            with open('results/low_coverage_analysis_partial.json', 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            print(f"   ❌ Ошибка анализа: {e}")
            results.append({
                'domain': domain,
                'recall': recall,
                'cause': 'analysis_error',
                'details': str(e)
            })
    
    # Генерируем отчет
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
    
    # Сохраняем финальные результаты
    output_file = "results/low_coverage_analysis_final.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 Результаты сохранены в {output_file}")

if __name__ == "__main__":
    main()