"""Offline domain identity using the PSL snapshot shipped with tldextract 5.3.0.

Private suffixes are included: a.github.io and b.github.io are separate sites.
No DNS or PSL download is performed. Unknown suffixes retain the whole hostname.
"""
from urllib.parse import urlparse
import tldextract

_extract = tldextract.TLDExtract(suffix_list_urls=(), cache_dir=None,
                               include_psl_private_domains=True)


def site_domain(url: str) -> str:
    parsed = urlparse(url if '://' in url else 'https://' + url)
    host = (parsed.hostname or '').lower().rstrip('.')
    result = _extract(host)
    return result.top_domain_under_public_suffix or (host if not result.suffix else '')
