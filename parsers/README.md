# Parsers

## `robots.py`

`RobotsParser` is responsible for two things:

1. Parse raw `robots.txt` into `RobotsAnalysis`
2. Answer crawl-access checks for a specific URL (`is_allowed`)

### Public API

- `parse(content: str, url: str, http_status: Optional[int]) -> RobotsAnalysis`
  - Handles non-200 and empty responses
  - Parses rules with Protego
  - Extracts sitemap entries and basic diagnostics

- `is_allowed(robots_content: str, target_url: str, user_agent: str = "*") -> Optional[bool]`
  - Returns `True` / `False` when parse is successful
  - Returns `None` when robots content is invalid

### Notes

- This is a **crawl** permission check, not a guaranteed indexing status.
- Indexing can still depend on page-level signals (`noindex`, canonicals, etc.).
