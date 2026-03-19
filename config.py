"""Централизованная конфигурация проекта."""

# HTTP настройки
HTTP_TIMEOUT = 30.0  # Единый таймаут для всех HTTP запросов (30 секунд)
HTTP_CONCURRENCY = 50  # Максимум одновременных запросов
DOMAIN_DELAY = 3.0  # Increased delay to avoid 502/429 errors
MAX_RETRIES = 3  # Enable retries for transient errors

# Лимиты размеров
MAX_HOME_BYTES = 1_500_000  # 1.5MB для homepage
MAX_ROBOTS_BYTES = 512_000  # 512KB для robots.txt

# Sitemap настройки
MAX_SITEMAP_URLS = 50_000_000  # Максимум URL из sitemap (увеличено для полного покрытия)
MAX_SITEMAP_CHILDREN = 50_000_000  # Максимум дочерних sitemap

# User-Agent
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"