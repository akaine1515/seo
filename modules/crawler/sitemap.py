from modules.crawler.transport import RequestPolicy

from collections import deque
from urllib.parse import urlsplit, urlunsplit
from xml.etree import ElementTree

import requests


class SitemapManager:
    """
    Sitemap discovery manager.

    Responsibilities:
    - Discover sitemap URLs from robots.txt and common locations.
    - Parse sitemapindex and urlset XML documents.
    - Support nested sitemap indexes.
    - Validate discovered URLs.
    - Apply configurable resource limits.
    - Reuse HTTP connections through requests.Session.

    This module only discovers URLs.
    The crawler engine remains responsible for robots.txt checks
    before fetching individual pages.
    """

    DEFAULT_TIMEOUT = 15
    DEFAULT_MAX_SITEMAPS = 500
    DEFAULT_MAX_URLS = 50000
    DEFAULT_MAX_RESPONSE_BYTES = 10 * 1024 * 1024

    def __init__(
        self,
        timeout=DEFAULT_TIMEOUT,
        max_sitemaps=DEFAULT_MAX_SITEMAPS,
        max_urls=DEFAULT_MAX_URLS,
        max_response_bytes=DEFAULT_MAX_RESPONSE_BYTES,
        user_agent="SEOIntelligenceBot",
        session=None
    ):
        self.request_policy = RequestPolicy(max_bytes=max_response_bytes)
        self.timeout = timeout
        self.max_sitemaps = max_sitemaps
        self.max_urls = max_urls
        self.max_response_bytes = max_response_bytes
        self.user_agent = user_agent

        self.session = session or requests.Session()
        self._owns_session = session is None

        self.session.headers.update({
            "User-Agent": self.user_agent,
            "Accept": "application/xml,text/xml,*/*"
        })

    # ---------------------------------------------------------
    # URL VALIDATION
    # ---------------------------------------------------------

    @staticmethod
    def normalize_url(url):
        """
        Normalize an HTTP/HTTPS URL.

        Removes fragments and normalizes scheme and hostname.
        Keeps path and query string.
        """

        if not isinstance(url, str):
            return None

        url = url.strip()

        if not url:
            return None

        try:
            parsed = urlsplit(url)

            scheme = parsed.scheme.lower()

            if scheme not in ("http", "https"):
                return None

            if not parsed.hostname:
                return None

            if parsed.username or parsed.password:
                return None

            hostname = parsed.hostname.lower()

            # Preserve IPv6 brackets.
            if ":" in hostname and not hostname.startswith("["):
                hostname = f"[{hostname}]"

            port = parsed.port

            if port is not None:
                if not (
                    (scheme == "http" and port == 80)
                    or (scheme == "https" and port == 443)
                ):
                    netloc = f"{hostname}:{port}"
                else:
                    netloc = hostname
            else:
                netloc = hostname

            path = parsed.path or "/"

            return urlunsplit((
                scheme,
                netloc,
                path,
                parsed.query,
                ""
            ))

        except (ValueError, TypeError):
            return None

    # ---------------------------------------------------------
    # HTTP REQUEST
    # ---------------------------------------------------------

    def _download_xml(self, sitemap_url):
        """
        Download XML with a maximum response size.

        Returns raw response bytes.
        Raises exceptions for request, HTTP and size errors.
        """

        response = self.request_policy.get(
            self.session, sitemap_url,
            timeout=self.timeout,
            allow_redirects=False
        )

        try:
            response.raise_for_status()
            if response.status_code != 200:
                raise ValueError("Unexpected sitemap HTTP status")

            chunks = []
            total_size = 0

            for chunk in response.iter_content(chunk_size=65536):
                if not chunk:
                    continue

                total_size += len(chunk)

                if total_size > self.max_response_bytes:
                    raise ValueError(
                        "Sitemap response exceeded maximum allowed size."
                    )

                chunks.append(chunk)

            return b"".join(chunks)

        finally:
            response.close()

    # ---------------------------------------------------------
    # XML PARSING
    # ---------------------------------------------------------

    @staticmethod
    def _local_name(tag):
        """
        Remove XML namespace from an element name.
        """

        if not isinstance(tag, str):
            return ""

        return tag.rsplit("}", 1)[-1].lower()

    def _parse_sitemap_xml(self, xml_content):
        """
        Parse sitemap XML.

        Returns:
            sitemap_type: 'sitemapindex', 'urlset', or 'unknown'
            locations: list of discovered loc values
        """

        root = ElementTree.fromstring(xml_content)

        root_type = self._local_name(root.tag)

        if root_type not in ("sitemapindex", "urlset"):
            return "unknown", []

        locations = []

        expected_child = (
            "sitemap"
            if root_type == "sitemapindex"
            else "url"
        )

        for child in root:
            if self._local_name(child.tag) != expected_child:
                continue

            for element in child:
                if self._local_name(element.tag) != "loc":
                    continue

                if element.text:
                    location = element.text.strip()

                    if location:
                        locations.append(location)

                    break

        return root_type, locations

    # ---------------------------------------------------------
    # SINGLE SITEMAP FETCH
    # ---------------------------------------------------------

    def _fetch_sitemap_data(self, sitemap_url):
        """
        Internal method.

        Returns:
            (sitemap_type, validated_locations)
        """

        normalized_url = self.normalize_url(sitemap_url)

        if not normalized_url:
            print(
                f"[SITEMAP] Invalid sitemap URL: {sitemap_url}"
            )
            return "unknown", []

        try:
            xml_content = self._download_xml(normalized_url)

            sitemap_type, locations = self._parse_sitemap_xml(
                xml_content
            )

            if sitemap_type == "unknown":
                print(
                    f"[SITEMAP] Unsupported XML root: {normalized_url}"
                )
                return "unknown", []

            validated_locations = []
            seen = set()

            for location in locations:
                normalized_location = self.normalize_url(location)

                if not normalized_location:
                    continue

                if normalized_location in seen:
                    continue

                seen.add(normalized_location)
                validated_locations.append(normalized_location)

            return sitemap_type, validated_locations

        except requests.RequestException as error:
            print(
                f"[SITEMAP] Request error: {normalized_url} - {error}"
            )

        except ElementTree.ParseError as error:
            print(
                f"[SITEMAP] Invalid XML: {normalized_url} - {error}"
            )

        except (ValueError, TypeError) as error:
            print(
                f"[SITEMAP] Processing error: {normalized_url} - {error}"
            )

        except Exception as error:
            print(
                f"[SITEMAP] Unexpected error: {normalized_url} - {error}"
            )

        return "unknown", []

    def fetch_sitemap(self, sitemap_url):
        """
        Public compatibility method.

        Returns a list of validated locations.
        """

        _, locations = self._fetch_sitemap_data(sitemap_url)

        return locations

    # ---------------------------------------------------------
    # SITEMAP DISCOVERY
    # ---------------------------------------------------------

    @staticmethod
    def _get_base_url(base_url):
        """
        Extract website origin from a URL.
        """

        normalized = SitemapManager.normalize_url(base_url)

        if not normalized:
            return None

        parsed = urlsplit(normalized)

        return f"{parsed.scheme}://{parsed.netloc}"

    def _get_initial_candidates(self, base_url, robots_manager=None):
        """
        Collect initial sitemap candidates.
        """

        candidates = []

        if robots_manager:
            try:
                robots_sitemaps = robots_manager.get_sitemaps()

                if robots_sitemaps:
                    candidates.extend(robots_sitemaps)

            except Exception as error:
                print(
                    f"[SITEMAP] Could not read robots sitemap entries: {error}"
                )

        candidates.extend([
            f"{base_url}/sitemap.xml",
            f"{base_url}/sitemap_index.xml"
        ])

        normalized_candidates = []
        seen = set()

        for candidate in candidates:
            normalized = self.normalize_url(candidate)

            if not normalized:
                continue

            if normalized in seen:
                continue

            seen.add(normalized)
            normalized_candidates.append(normalized)

        return normalized_candidates

    def discover(self, base_url, robots_manager=None):
        """
        Discover page URLs from a website's sitemap structure.

        Supports:
        - Sitemap URLs declared in robots.txt
        - Common sitemap locations
        - Sitemap indexes
        - Nested sitemap indexes
        - Multiple sitemap files

        Returns:
            Sorted list of unique page URLs.

        Important:
            This method does not fetch discovered pages.
            Robots permission must be checked by CrawlerEngine
            before every page request.
        """

        root_url = self._get_base_url(base_url)

        if not root_url:
            print(
                f"[SITEMAP] Invalid website URL: {base_url}"
            )
            return []

        candidates = self._get_initial_candidates(
            root_url,
            robots_manager
        )

        queue = deque(candidates)

        visited_sitemaps = set()
        discovered_urls = set()

        processed_sitemaps = 0

        while queue:
            if processed_sitemaps >= self.max_sitemaps:
                print(
                    "[SITEMAP] Maximum sitemap limit reached: "
                    f"{self.max_sitemaps}"
                )
                break

            if len(discovered_urls) >= self.max_urls:
                print(
                    "[SITEMAP] Maximum URL limit reached: "
                    f"{self.max_urls}"
                )
                break

            sitemap_url = queue.popleft()

            normalized_sitemap_url = self.normalize_url(
                sitemap_url
            )

            if not normalized_sitemap_url:
                continue

            if normalized_sitemap_url in visited_sitemaps:
                continue

            visited_sitemaps.add(normalized_sitemap_url)
            processed_sitemaps += 1

            sitemap_type, locations = self._fetch_sitemap_data(
                normalized_sitemap_url
            )

            if sitemap_type == "sitemapindex":

                for location in locations:
                    if len(discovered_urls) >= self.max_urls:
                        break

                    if location in visited_sitemaps:
                        continue

                    queue.append(location)

            elif sitemap_type == "urlset":

                for location in locations:
                    if len(discovered_urls) >= self.max_urls:
                        break

                    discovered_urls.add(location)

        results = sorted(discovered_urls)

        print("\n[SITEMAP] Discovery completed")
        print(f"[SITEMAP] Processed sitemap files: {processed_sitemaps}")
        print(f"[SITEMAP] Discovered page URLs: {len(results)}")
        print(f"[SITEMAP] Remaining sitemap queue: {len(queue)}")

        return results

    # ---------------------------------------------------------
    # RESOURCE MANAGEMENT
    # ---------------------------------------------------------

    def close(self):
        """
        Close the internally created HTTP session.
        """

        if self._owns_session and self.session:
            self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
