import logging
import posixpath
import re
from typing import Set
from urllib.parse import parse_qsl, quote, urlencode, urlparse, urlunparse

logger = logging.getLogger(__name__)

TRACKING_PARAMS: Set[str] = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "utm_id",
    "utm_source_platform",
    "utm_creative_format",
    "utm_marketing_tactic",
    "gclid",
    "gclsrc",
    "_ga",
    "ga_source",
    "ga_medium",
    "ga_campaign",
    "fbclid",
    "fb_action_ids",
    "fb_action_types",
    "fb_source",
    "fb_ref",
    "yclid",
    "_openstat",
    "ymclid",
    "from",
    "msclkid",
    "mc_cid",
    "mc_eid",
    "ref",
    "referrer",
    "source",
    "_hsenc",
    "_hsmi",
    "hsctatracking",
    "mkt_tok",
}

WWW_PREFIXES: Set[str] = {"www", "www1", "www2", "www3", "www4", "m", "mobile"}
_DEFAULT_PORTS = {"http": "80", "https": "443"}
_UNRESERVED = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~")


def normalize_url(
    url: str,
    *,
    remove_www: bool = True,
    remove_tracking: bool = True,
    remove_all_query: bool = False,
    remove_fragment: bool = True,
    sort_query: bool = True,
    strip_trailing_slash: bool = True,
    remove_regional_subdomains: bool = False,
) -> str:
    """Normalize URL for high-volume sitemap matching using stdlib only."""
    if not url or not url.strip():
        return url

    try:
        prepared = url.strip()
        if "://" not in prepared:
            prepared = f"https://{prepared}"

        parsed = urlparse(prepared)

        scheme = (parsed.scheme or "https").lower()
        netloc = _normalize_netloc(parsed.netloc, scheme)
        path = _normalize_path(parsed.path or "/")
        query = parsed.query
        fragment = "" if remove_fragment else parsed.fragment

        if remove_www and netloc:
            netloc = _remove_www_prefix(netloc)

        if remove_regional_subdomains and netloc:
            netloc = _remove_regional_subdomain(netloc)

        if remove_all_query:
            query = ""
        elif query:
            query_pairs = parse_qsl(query, keep_blank_values=True)
            if remove_tracking:
                query_pairs = [(k, v) for (k, v) in query_pairs if k.lower() not in TRACKING_PARAMS]
            if sort_query:
                query_pairs = sorted(query_pairs)
            query = urlencode(query_pairs, doseq=True)

        if strip_trailing_slash and path != "/" and path.endswith("/"):
            path = path.rstrip("/")

        return urlunparse((scheme, netloc, path, "", query, fragment))
    except Exception as e:  # noqa: BLE001
        logger.warning("URL normalization failed for %s: %s", url, e)
        return url.strip()


def normalize_domain(domain: str, *, remove_www: bool = True) -> str:
    if not domain or not domain.strip():
        return domain

    domain = domain.strip()
    if "://" in domain:
        try:
            domain = urlparse(domain).netloc or domain
        except Exception:
            pass

    if ":" in domain and not domain.startswith("["):
        domain = domain.rsplit(":", 1)[0]

    domain = domain.lower()

    if remove_www:
        domain = _remove_www_prefix(domain)

    try:
        return domain.encode("idna").decode("ascii")
    except Exception:
        return domain


def extract_domain(url: str, *, normalize: bool = True) -> str:
    if not url:
        return ""
    try:
        domain = urlparse(url).netloc
        return normalize_domain(domain) if normalize and domain else domain
    except Exception:
        return ""


def urls_match(
    url1: str,
    url2: str,
    *,
    ignore_query: bool = False,
    ignore_fragment: bool = True,
) -> bool:
    if not url1 or not url2:
        return False
    try:
        norm1 = normalize_url(url1, remove_fragment=ignore_fragment, remove_all_query=ignore_query)
        norm2 = normalize_url(url2, remove_fragment=ignore_fragment, remove_all_query=ignore_query)
        return norm1 == norm2
    except Exception:
        return False


def urls_match_fuzzy(
    url1: str,
    url2: str,
    *,
    ignore_query: bool = True,
) -> bool:
    if urls_match(url1, url2, ignore_query=ignore_query):
        return True

    try:
        norm1 = normalize_url(url1, remove_all_query=ignore_query)
        norm2 = normalize_url(url2, remove_all_query=ignore_query)

        parsed1 = urlparse(norm1)
        parsed2 = urlparse(norm2)

        if parsed1.netloc != parsed2.netloc:
            return False

        path1_clean = re.sub(r"[-_]", "", parsed1.path)
        path2_clean = re.sub(r"[-_]", "", parsed2.path)

        return path1_clean == path2_clean
    except Exception:
        return False


def _normalize_netloc(netloc: str, scheme: str) -> str:
    if not netloc:
        return ""

    userinfo = ""
    hostport = netloc
    if "@" in hostport:
        userinfo, hostport = hostport.rsplit("@", 1)

    host = hostport
    port = ""

    if hostport.startswith("[") and "]" in hostport:
        # IPv6 literal
        close_idx = hostport.find("]")
        host = hostport[: close_idx + 1].lower()
        rest = hostport[close_idx + 1 :]
        if rest.startswith(":"):
            port = rest[1:]
    elif ":" in hostport:
        host, port = hostport.rsplit(":", 1)

    host = host.lower()
    try:
        host = host.encode("idna").decode("ascii")
    except Exception:
        pass

    if port and port == _DEFAULT_PORTS.get(scheme):
        port = ""

    normalized = host if not port else f"{host}:{port}"
    return f"{userinfo}@{normalized}" if userinfo else normalized


def _normalize_path(path: str) -> str:
    decoded = _decode_unreserved(path)
    clean = posixpath.normpath(decoded)
    if decoded.endswith("/") and not clean.endswith("/"):
        clean += "/"
    if not clean.startswith("/"):
        clean = "/" + clean
    return quote(clean, safe="/-._~%")


def _decode_unreserved(path: str) -> str:
    """Decode only unreserved percent-encoded octets.

    Keep reserved escapes (e.g. %2F) intact to avoid changing URL semantics.
    """

    def _replace(match):
        hex_part = match.group(1)
        try:
            ch = bytes.fromhex(hex_part).decode("utf-8")
        except Exception:
            return match.group(0)
        return ch if ch in _UNRESERVED else match.group(0).upper()

    return re.sub(r"%([0-9a-fA-F]{2})", _replace, path)


def _remove_www_prefix(domain: str) -> str:
    has_port = False
    port = ""
    if ":" in domain and not domain.startswith("["):
        domain, port = domain.rsplit(":", 1)
        has_port = True

    parts = domain.split(".")
    if len(parts) > 1 and parts[0] in WWW_PREFIXES:
        domain = ".".join(parts[1:])

    if has_port:
        domain = f"{domain}:{port}"

    return domain


def _remove_regional_subdomain(domain: str) -> str:
    """Optional heuristic; off by default to avoid false positives."""
    parts = domain.split(".")
    if len(parts) <= 2:
        return domain

    tld = parts[-1]
    if tld in {"ru", "su", "by", "kz", "ua", "рф"}:
        return ".".join(parts[-2:])

    return domain
