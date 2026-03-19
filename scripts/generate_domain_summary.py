#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для генерации общей статистики по всем доменам из sitemap_quality_filtered.csv
"""

import pandas as pd
import os

def calculate_domain_statistics():
    """Рассчитывает статистику по всем доменам"""
    
    # Читаем данные из CSV файла
    df = pd.read_csv('results/sitemap_quality_filtered.csv')
    
    # Общее количество доменов
    total_domains = len(df)
    
    # Домены с найденным sitemap (sitemap_count > 0)
    domains_with_sitemap = df[df['sitemap_count'] > 0]
    domains_without_sitemap = df[df['sitemap_count'] == 0]
    
    # Статистика
    stats = {
        'total_domains': total_domains,
        'domains_with_sitemap': len(domains_with_sitemap),
        'domains_without_sitemap': len(domains_without_sitemap),
        'sitemap_found_percentage': (len(domains_with_sitemap) / total_domains) * 100,
        'avg_recall_with_sitemap': domains_with_sitemap['recall'].mean(),
        'avg_recall_all_domains': df['recall'].mean()
    }
    
    return stats

def create_summary_table(stats):
    """Создает таблицу с общей статистикой"""
    
    summary_df = pd.DataFrame([{
        'Показатель': 'Общее количество доменов',
        'Значение': stats['total_domains'],
        'Процент': ''
    }, {
        'Показатель': 'Домены с найденным sitemap',
        'Значение': stats['domains_with_sitemap'],
        'Процент': '{:.2f}%'.format(stats['sitemap_found_percentage'])
    }, {
        'Показатель': 'Средний recall среди доменов с найденным sitemap',
        'Значение': '{:.2f}%'.format(stats['avg_recall_with_sitemap']),
        'Процент': ''
    }, {
        'Показатель': 'Средний recall среди всех доменов',
        'Значение': '{:.2f}%'.format(stats['avg_recall_all_domains']),
        'Процент': ''
    }])
    
    return summary_df

def main():
    """Основная функция"""
    
    print("Генерация статистики по доменам...")
    
    # Рассчитываем статистику
    stats = calculate_domain_statistics()
    
    # Создаем таблицу
    summary_df = create_summary_table(stats)
    
    # Сохраняем результаты
    output_file = 'results/domain_summary_statistics.csv'
    summary_df.to_csv(output_file, index=False, encoding='utf-8')
    
    print("Статистика сохранена в файл: {}".format(output_file))
    print("\nРезультаты:")
    print(summary_df.to_string(index=False))
    
    # Дополнительная информация
    print("\nДополнительная информация:")
    print("Всего доменов: {}".format(stats['total_domains']))
    print("Домены с sitemap: {} ({:.2f}%)".format(stats['domains_with_sitemap'], stats['sitemap_found_percentage']))
    print("Домены без sitemap: {}".format(stats['domains_without_sitemap']))
    print("Средний recall (с sitemap): {:.2f}%".format(stats['avg_recall_with_sitemap']))
    print("Средний recall (все домены): {:.2f}%".format(stats['avg_recall_all_domains']))

if __name__ == "__main__":
    main()