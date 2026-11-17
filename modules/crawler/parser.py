
import hashlib
import json
from collections import Counter
import re
import trafilatura

from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, urldefrag


class PageParser:
    """
    Extract SEO, content, image and link information from HTML pages.
    """

    # -------------------------------------------------
    # TEXT CLEANING
    # -------------------------------------------------

    @staticmethod
    def clean_text(value):
        if not value:
            return None

        cleaned = re.sub(r"\s+", " ", str(value)).strip()

        return cleaned if cleaned else None

    # -------------------------------------------------
    # META EXTRACTION
    # -------------------------------------------------

    @staticmethod
    def get_meta_content(soup, name):

        tag = soup.find(
            "meta",
            attrs={
                "name": lambda value:
                    isinstance(value, str)
                    and value.lower() == name.lower()
            }
        )

        if not tag:
            return None

        return PageParser.clean_text(
            tag.get("content")
        )

    # -------------------------------------------------
    # HEADING EXTRACTION
    # -------------------------------------------------

    @staticmethod
    def get_headings(soup, tag_name):

        headings = []

        for tag in soup.find_all(tag_name):

            text = PageParser.clean_text(
                tag.get_text(" ", strip=True)
            )

            if text:
                headings.append(text)

        return headings

    # -------------------------------------------------
    # URL NORMALIZATION FOR LINK COMPARISON
    # -------------------------------------------------

    @staticmethod
    def normalize_link_url(url):

        if not url:
            return None

        try:
            url = url.strip()

            absolute_url = urldefrag(url)[0]
            parsed = urlparse(absolute_url)

            if parsed.scheme.lower() not in ("http", "https"):
                return None

            if not parsed.netloc:
                return None

            scheme = parsed.scheme.lower()
            hostname = (parsed.hostname or "").lower().rstrip(".")

            if not hostname:
                return None

            try:
                port = parsed.port
            except ValueError:
                return None

            if port and not (
                (scheme == "http" and port == 80)
                or (scheme == "https" and port == 443)
            ):
                netloc = f"{hostname}:{port}"
            else:
                netloc = hostname

            if parsed.username or parsed.password:
                return None

            path = parsed.path or "/"

            return (
                f"{scheme}://{netloc}"
                f"{path}"
                f"?{parsed.query}"
            ) if parsed.query else (
                f"{scheme}://{netloc}{path}"
            )

        except Exception:
            return None

    # -------------------------------------------------
    # ROBOTS DIRECTIVE PARSING
    # -------------------------------------------------

    @staticmethod
    def parse_robots_directives(directive_text):

        if not directive_text:
            return set()

        normalized = directive_text.lower()

        directives = set()

        # Robots directives may be separated by commas,
        # semicolons or whitespace.
        tokens = re.split(r"[\s,;]+", normalized)

        for token in tokens:

            token = token.strip()

            if not token:
                continue

            # Handles forms such as:
            # googlebot:noindex
            if ":" in token:
                token = token.split(":")[-1]

            token = token.strip()

            if token in {
                "noindex",
                "nofollow",
                "none",
                "index",
                "follow",
                "all",
                "noarchive",
                "nosnippet",
                "noimageindex",
                "notranslate",
            }:
                directives.add(token)

        return directives

    # -------------------------------------------------
    # RESPONSE HEADER EXTRACTION
    # -------------------------------------------------

    @staticmethod
    def get_x_robots_headers(response_headers):

        values = []

        for header_name, header_value in response_headers.items():

            if header_name.lower() != "x-robots-tag":
                continue

            if isinstance(header_value, (list, tuple)):
                values.extend(
                    str(value).strip()
                    for value in header_value
                    if value
                )
            elif header_value:
                values.append(str(header_value).strip())

        return values

    # -------------------------------------------------
    # LINK ANALYSIS
    # -------------------------------------------------

    @staticmethod
    def analyze_links(soup, page_url):

        internal_links = set()
        external_links = set()

        internal_links_count = 0
        external_links_count = 0
        nofollow_links_count = 0

        page_host = (
            (urlparse(page_url).hostname or "")
            .lower()
            .rstrip(".")
        )

        for link in soup.find_all("a", href=True):

            href = link.get("href", "").strip()

            if not href:
                continue

            absolute_url = urljoin(page_url, href)

            normalized_url = PageParser.normalize_link_url(
                absolute_url
            )

            if not normalized_url:
                continue

            parsed_link = urlparse(normalized_url)

            link_host = (
                (parsed_link.hostname or "")
                .lower()
                .rstrip(".")
            )

            if link_host == page_host:

                internal_links_count += 1
                internal_links.add(normalized_url)

            else:

                external_links_count += 1
                external_links.add(normalized_url)

            rel_values = link.get("rel", [])

            if isinstance(rel_values, str):
                rel_values = rel_values.split()

            rel_values = {
                str(value).lower()
                for value in rel_values
            }

            if "nofollow" in rel_values:
                nofollow_links_count += 1

        return {
            "internal_links_count": internal_links_count,
            "external_links_count": external_links_count,

            "unique_internal_links_count": len(internal_links),
            "unique_external_links_count": len(external_links),

            "nofollow_links_count": nofollow_links_count,
        }

    # -------------------------------------------------
    # MAIN CONTENT EXTRACTION
    # -------------------------------------------------

    @staticmethod
    def extract_main_content(html):

        try:
            extracted = trafilatura.extract(
                html,
                include_links=False,
                include_images=False,
                include_tables=True,
                favor_precision=True
            )

            text_content = PageParser.clean_text(
                extracted
            )

            return text_content or ""

        except Exception:
            return ""

    # -------------------------------------------------
    # MAIN PARSER
    # -------------------------------------------------

    @staticmethod
    def parse(
        html,
        url,
        status_code=None,
        response_headers=None
    ):
        """
        Parse HTML and extract SEO information.

        Returns a dictionary compatible with the
        SEO Intelligence database and crawler engine.
        """

        if isinstance(html, bytes):
            html = html.decode(
                "utf-8",
                errors="replace"
            )

        if not isinstance(html, str):
            html = str(html or "")

        response_headers = response_headers or {}

        soup = BeautifulSoup(html, "lxml")

        # -----------------------------------------
        # TITLE
        # -----------------------------------------

        title_tag = soup.find("title")

        title = (
            PageParser.clean_text(
                title_tag.get_text(" ", strip=True)
            )
            if title_tag else None
        )

        title_length = len(title) if title else 0

        # -----------------------------------------
        # META DESCRIPTION
        # -----------------------------------------

        meta_description = PageParser.get_meta_content(
            soup,
            "description"
        )

        meta_description_length = (
            len(meta_description)
            if meta_description else 0
        )

        # -----------------------------------------
        # HEADINGS
        # -----------------------------------------

        h1_list = PageParser.get_headings(soup, "h1")
        h2_list = PageParser.get_headings(soup, "h2")
        h3_list = PageParser.get_headings(soup, "h3")

        h1 = h1_list[0] if h1_list else None

        h1_count = len(h1_list)
        h2_count = len(h2_list)
        h3_count = len(h3_list)

        # -----------------------------------------
        # CANONICAL
        # -----------------------------------------

        canonical_tags = soup.find_all(
            "link",
            rel=lambda value:
                value and "canonical" in [
                    item.lower()
                    for item in (
                        value if isinstance(value, list)
                        else value.split()
                    )
                ]
        )

        canonical_url = None
        canonical_status = "missing"

        if canonical_tags:

            canonical_href = canonical_tags[0].get("href")

            if canonical_href:

                candidate = urljoin(
                    url,
                    canonical_href.strip()
                )

                parsed_canonical = urlparse(candidate)

                if (
                    parsed_canonical.scheme.lower()
                    in ("http", "https")
                    and parsed_canonical.netloc
                ):
                    canonical_url = candidate
                    canonical_status = "present"

                else:
                    canonical_status = "invalid"

            else:
                canonical_status = "invalid"

            if len(canonical_tags) > 1:
                canonical_status = "multiple"

        # -----------------------------------------
        # ROBOTS DIRECTIVES
        # -----------------------------------------

        robots_directives = []

        meta_robots = PageParser.get_meta_content(
            soup,
            "robots"
        )

        meta_googlebot = PageParser.get_meta_content(
            soup,
            "googlebot"
        )

        if meta_robots:
            robots_directives.append(meta_robots)

        if meta_googlebot:
            robots_directives.append(meta_googlebot)

        x_robots_values = PageParser.get_x_robots_headers(
            response_headers
        )

        robots_directives.extend(x_robots_values)

        x_robots_tag = (
            ", ".join(x_robots_values)
            if x_robots_values else None
        )

        robots_directive = (
            ", ".join(robots_directives)
            if robots_directives else None
        )

        parsed_directives = (
            PageParser.parse_robots_directives(
                robots_directive
            )
        )

        is_noindex = (
            "noindex" in parsed_directives
            or "none" in parsed_directives
        )

        is_nofollow = (
            "nofollow" in parsed_directives
            or "none" in parsed_directives
        )

        is_indexable = not is_noindex

        # -----------------------------------------
        # MAIN CONTENT
        # -----------------------------------------

        text_content = PageParser.extract_main_content(
            html
        )

        words = text_content.split()

        word_count = len(words)

        # Empty pages should not share a duplicate hash.
        content_hash = (
            hashlib.sha256(
                text_content.encode("utf-8")
            ).hexdigest()
            if text_content else None
        )

        # -----------------------------------------
        # IMAGE ANALYSIS
        # -----------------------------------------

        images = soup.find_all("img")

        image_count = len(images)

        images_without_alt = sum(
            1
            for image in images
            if not str(image.get("alt") or "").strip()
        )

        # -----------------------------------------
        # LINK ANALYSIS
        # -----------------------------------------

        link_data = PageParser.analyze_links(
            soup,
            url
        )

        headings = [{'level': int(t.name[1]), 'text': t.get_text(' ', strip=True)}
                    for t in soup.find_all(re.compile(r'^h[1-6]$'))]
        image_details = [{'url': PageParser.normalize_link_url(urljoin(url, t.get('src', ''))) if t.get('src') else None,
                          'alt': t.get('alt'), 'width': t.get('width'), 'height': t.get('height'),
                          'loading': t.get('loading'), 'srcset': t.get('srcset'),
                          'dimensions_source': 'HTML attributes, not measured pixels',
                          'file_bytes': None} for t in images]
        structured = []
        for tag in soup.find_all('script', attrs={'type': 'application/ld+json'}):
            try:
                data = json.loads(tag.string or tag.get_text())
                structured.append({'valid_json': True, 'data': data})
            except (ValueError, TypeError):
                structured.append({'valid_json': False, 'data': None})

        # -----------------------------------------
        # FINAL RESULT
        # -----------------------------------------

        return {

            "mixed_content_urls": sorted({urljoin(url, tag.get(attr))
                for tag, attr in [(t, a) for a in ('src', 'href') for t in soup.find_all(attrs={a: True})]
                if url.startswith('https://') and tag.name in ('img', 'script', 'link', 'iframe', 'video', 'audio')
                and (tag.name != 'link' or set(tag.get('rel', [])).intersection({'stylesheet', 'icon', 'preload', 'modulepreload'}))
                and urljoin(url, tag.get(attr)).startswith('http://')}),

            'headings': headings,
            'h4_list': PageParser.get_headings(soup, 'h4'),
            'h5_list': PageParser.get_headings(soup, 'h5'),
            'h6_list': PageParser.get_headings(soup, 'h6'),
            'tag_counts': dict(Counter(t.name for t in soup.find_all(True))),
            'meta_tags': [dict(t.attrs) for t in soup.find_all('meta')],
            'language': soup.html.get('lang') if soup.html else None,
            'viewport': PageParser.get_meta_content(soup, 'viewport'),
            'images': image_details,
            'structured_data': structured,
            'resource_counts': {'scripts': len(soup.find_all('script', src=True)),
                                'stylesheets': len(soup.select('link[rel~=stylesheet]'))},
            # Basic information
            "url": url,
            "status_code": status_code,
            "content_type": "text/html",

            # Title
            "title": title,
            "title_length": title_length,

            # Meta description
            "meta_description": meta_description,
            "meta_description_length": meta_description_length,

            # Headings
            "h1": h1,
            "h1_list": h1_list,
            "h1_count": h1_count,

            "h2_list": h2_list,
            "h2_count": h2_count,

            "h3_list": h3_list,
            "h3_count": h3_count,

            # Canonical
            "canonical_url": canonical_url,
            "canonical_status": canonical_status,

            # Robots
            "robots_directive": robots_directive,
            "x_robots_tag": x_robots_tag,
            "is_indexable": int(is_indexable),
            "is_nofollow": int(is_nofollow),

            # Content
            "word_count": word_count,
            "text_content": text_content,
            "content_hash": content_hash,

            # Images
            "image_count": image_count,
            "images_without_alt": images_without_alt,

            # Links
            "internal_links_count":
                link_data["internal_links_count"],

            "external_links_count":
                link_data["external_links_count"],

            "unique_internal_links_count":
                link_data["unique_internal_links_count"],

            "unique_external_links_count":
                link_data["unique_external_links_count"],

            "nofollow_links_count":
                link_data["nofollow_links_count"],
        }
