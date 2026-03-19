# Анализ технической инфраструктуры сайтов

Инструмент для автоматического анализа robots.txt, sitemap и определения CMS.

## Как работает

### Robots.txt
- **Библиотека**: [Protego](https://github.com/scrapy/protego)
- **Что делает**: Парсит robots.txt, извлекает правила (Allow/Disallow), Sitemap URLs, Crawl-Delay
- **Режимы**: Работает одинаково в полном и быстром режиме

### Sitemap
**Полный режим** (`--full-sitemap-parsing`):
- **Библиотека**: [Ultimate Sitemap Parser](https://github.com/GateNLP/ultimate-sitemap-parser) (async)
- **Что делает**: Рекурсивно парсит все sitemap (включая sitemap indexes), извлекает все URLs с метаданными (lastmod, priority, changefreq)

**Быстрый режим** (по умолчанию):
- **Метод**: HTTP HEAD/GET запросы
- **Что делает**: Проверяет только существование sitemap файлов (не парсит содержимое)

### CMS Detection
- **Библиотека**: [python-Wappalyzer](https://github.com/chorsley/python-Wappalyzer)
- **Что делает**: Анализирует HTML, HTTP headers, JavaScript, CSS для определения CMS и технологий
- **Режимы**: Работает одинаково в полном и быстром режиме
- **Определяет**: WordPress, Bitrix, Magento, Shopify, Tilda, OpenCart, PrestaShop, Drupal, Joomla и др.

## Быстрый старт

### 1. Тест на одном домене

```bash
# Создайте тестовый файл
echo '{"domain": "ozon.ru", "curr_gmv_tier": "test", "curr_industry": "test"}' > test.jsonl

# Запустите анализ
.venv/bin/python3 -m cli -i test.jsonl -o result.jsonl --full-sitemap-parsing -c 1 -d 0.5 -v

# Посмотрите результат
cat result.jsonl | jq '.'
```

### 2. Массовый анализ (весь файл)

```bash
# Запустите на всех доменах
.venv/bin/python3 -m cli -i top500-domains.json -o results.jsonl --full-sitemap-parsing -c 30 -d 0.5 -v
```

**Параметры:**
- `-i` - входной файл (формат JSONL)
- `-o` - выходной файл (формат JSONL)
- `--full-sitemap-parsing` - полный парсинг sitemap (медленно, но находит больше)
- `-c 30` - 30 параллельных запросов
- `-d 0.5` - задержка 0.5 сек между запросами к одному домену
- `-v` - подробное логирование

## Что получим в output

Каждая строка - это JSON с анализом домена:

```json
{
  "domain": "example.com",
  "base_url": "https://example.com/",
  "home_http_status": 200,
  "home_accessible": true,
  "robots": {
    "exists": true,
    "url": "https://example.com/robots.txt",
    "http_status": 200,
    "sitemaps": ["https://example.com/sitemap.xml"],
    "total_rules": 5
  },
  "sitemap": {
    "exists": true,
    "url": "https://example.com/sitemap.xml",
    "discovered_via": "robots",
    "total_url_count": 1234
  },
  "cms": {
    "detected": true,
    "platform": "WordPress",
    "confidence_score": 0.95,
    "detected_technologies": ["WordPress", "PHP"]
  }
}
```

## Установка зависимостей

```bash
pip install -r requirements.txt
