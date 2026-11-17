from modules.crawler.transport import RequestPolicy
import json
from urllib.parse import urljoin, urlparse, urlunparse, urldefrag

import requests
from bs4 import BeautifulSoup

from modules.crawler.robots import RobotsManager
from modules.crawler.sitemap import SitemapManager
from modules.crawler.parser import PageParser

from database.repository import (
    AnalysisRepository,
    PageRepository,
    PageContentRepository,
    CrawlQueueRepository,
    PageLinkRepository,
    CrawlEventRepository,
    CrawlSummaryRepository,
)


class CrawlerEngine:
    """
    Main website crawler.

    Features:
    - Persistent crawl queue using SQLite.
    - Analysis lifecycle management.
    - Heartbeat updates during crawling.
    - Controlled cancellation.
    - robots.txt verification before every request.
    - Manual redirect handling.
    - Maximum attempted URL limit.
    - Page, page content, and link storage.
    - Crawl event logging.
    - Recovery of interrupted queue items.
    - Guaranteed resource cleanup.
    """

    REDIRECT_CODES = {
        301,
        302,
        303,
        307,
        308,
    }

    MAX_REDIRECTS = 10

    USER_AGENT = "SEOIntelligenceBot/1.0"

    def __init__(
        self,
        analysis_run_id,
        max_pages=50,
        timeout=15
    ):

        self.analysis_run_id = int(analysis_run_id)
        self.max_pages = max(1, int(max_pages))
        self.timeout = max(1, int(timeout))

        self.request_policy = RequestPolicy()
        self.max_depth = None
        self.excluded_paths = []
        self.progress_callback = None
        self.cancel_event = None
        self.scope_skipped = set()
        self.http_results = []
        self.sitemap_urls = []
        self.session = requests.Session()

        self.session.headers.update({
            "User-Agent": self.USER_AGENT,
            "Accept": (
                "text/html,application/xhtml+xml,"
                "application/xml;q=0.9,*/*;q=0.8"
            ),
        })

        self.visited = set()
        self.queued_urls = set()

        self.base_url = None
        self.base_domain = None

        self.robots = None

        self.sitemap_manager = SitemapManager(
            timeout=self.timeout,
            user_agent=self.USER_AGENT
        )

        self.parser = PageParser()

        self.stats = {
            "attempted": 0,
            "crawled": 0,
            "saved": 0,
            "contents_saved": 0,
            "failed": 0,
            "blocked": 0,
            "skipped": 0,
            "links_saved": 0,
        }

        self._closed = False
        self._cancel_requested = False
        self._started = False

    # --------------------------------------------------
    # CONTROL
    # --------------------------------------------------

    def request_cancel(self):
        """
        Request controlled cancellation.

        This method can be called from another thread,
        for example from the desktop application's UI.
        """

        self._cancel_requested = True

    def _check_cancelled(self):
        return self._cancel_requested or (self.cancel_event is not None and self.cancel_event.is_set())

    def _heartbeat_or_raise(self):
        """
        Update analysis heartbeat.

        A failed heartbeat means that this run is no
        longer in a valid running state.
        """

        if self._check_cancelled():
            return False

        updated = AnalysisRepository.heartbeat_analysis_run(
            self.analysis_run_id
        )

        if not updated:
            raise RuntimeError(
                "Analysis heartbeat failed. "
                "The analysis run may no longer be running."
            )

        return True

    # --------------------------------------------------
    # URL NORMALIZATION
    # --------------------------------------------------

    @staticmethod
    def normalize_url(url: str) -> str:

        if not url:
            return ""

        try:
            url = urldefrag(str(url).strip())[0]

            parsed = urlparse(url)

            scheme = parsed.scheme.lower()

            if scheme not in ("http", "https"):
                return ""

            if not parsed.netloc:
                return ""

            if parsed.username or parsed.password:
                return ""

            hostname = parsed.hostname

            if not hostname:
                return ""

            hostname = hostname.lower()

            port = parsed.port

            if port and not (
                (scheme == "http" and port == 80)
                or (scheme == "https" and port == 443)
            ):
                netloc = f"{hostname}:{port}"
            else:
                netloc = hostname

            return urlunparse((
                scheme,
                netloc,
                parsed.path or "/",
                parsed.params,
                parsed.query,
                ""
            ))

        except (ValueError, TypeError):
            return ""

    # --------------------------------------------------
    # INTERNAL URL CHECK
    # --------------------------------------------------

    def is_internal_url(self, url: str) -> bool:

        if not url or not self.base_domain:
            return False

        try:
            parsed = urlparse(url)

            return (
                parsed.scheme.lower() in ("http", "https")
                and parsed.hostname is not None
                and parsed.hostname.lower() == self.base_domain
            )

        except (ValueError, TypeError):
            return False

    # --------------------------------------------------
    # EVENT LOGGING
    # --------------------------------------------------

    def log_event(
        self,
        event_type,
        message,
        url=None,
        severity="info",
        details=None
    ):

        try:
            details_json = None

            if details is not None:
                details_json = json.dumps(
                    details,
                    ensure_ascii=False
                )

            CrawlEventRepository.log_event(
                analysis_run_id=self.analysis_run_id,
                event_type=event_type,
                message=message,
                url=url,
                severity=severity,
                details_json=details_json
            )

        except Exception as error:
            print(
                f"[EVENT LOG WARNING] "
                f"Could not save event: {error}"
            )

    # --------------------------------------------------
    # QUEUE MANAGEMENT
    # --------------------------------------------------

    def add_to_queue(
        self,
        url,
        depth=0,
        parent_url=None,
        discovered_from="crawler",
        priority=0
    ):

        normalized = self.normalize_url(url)

        if not normalized:
            return False

        if not self.is_internal_url(normalized):
            return False

        if ((self.max_depth is not None and depth > self.max_depth)
                or any(urlparse(normalized).path.startswith(path) for path in self.excluded_paths)):
            self.scope_skipped.add(normalized)
            return False

        if normalized in self.visited:
            return False

        if normalized in self.queued_urls:
            return False

        try:
            queue_id = CrawlQueueRepository.add_url(
                analysis_run_id=self.analysis_run_id,
                url=normalized,
                normalized_url=normalized,
                depth=max(0, int(depth)),
                parent_url=parent_url,
                discovered_from=discovered_from,
                priority=priority
            )

            if queue_id is not None:
                self.queued_urls.add(normalized)
                return True

        except Exception as error:
            self.log_event(
                event_type="queue_error",
                message=str(error),
                url=normalized,
                severity="high"
            )

            print(
                f"[QUEUE ERROR] {normalized} - {error}"
            )

        return False

    # --------------------------------------------------
    # LINK EXTRACTION
    # --------------------------------------------------

    def extract_links(
        self,
        html,
        current_url,
        current_depth=0
    ):

        if not html:
            return []

        soup = BeautifulSoup(html, "lxml")

        extracted_links = []

        position = 0

        for tag in soup.find_all("a", href=True):

            href = tag.get("href", "").strip()

            if not href:
                continue

            absolute_url = urljoin(
                current_url,
                href
            )

            normalized = self.normalize_url(
                absolute_url
            )

            if not normalized:
                continue

            is_internal = self.is_internal_url(
                normalized
            )

            rel_values = tag.get("rel", [])

            if isinstance(rel_values, str):
                rel_values = rel_values.split()

            rel = (
                " ".join(rel_values)
                if rel_values
                else None
            )

            anchor_text = tag.get_text(
                separator=" ",
                strip=True
            )

            link_data = {
                "target_url": normalized,
                "source_url": current_url,
                "anchor_text": anchor_text,
                "rel": rel,
                "is_internal": is_internal,
                "link_type": "html",
                "link_position": position,
            }

            extracted_links.append(link_data)

            if is_internal:
                self.add_to_queue(
                    normalized,
                    depth=current_depth + 1,
                    parent_url=current_url,
                    discovered_from="internal_link",
                    priority=0
                )

            position += 1

        return extracted_links

    # --------------------------------------------------
    # MANUAL REDIRECT HANDLING
    # --------------------------------------------------

    def request_page(self, initial_url):

        current_url = self.normalize_url(
            initial_url
        )

        redirect_chain = []

        for redirect_number in range(
            self.MAX_REDIRECTS + 1
        ):

            if self._check_cancelled():
                return {
                    "status": "cancelled",
                    "response": None,
                    "final_url": current_url,
                    "redirect_chain": redirect_chain,
                }

            if any(urlparse(current_url).path.startswith(path) for path in self.excluded_paths):
                return {"status": "excluded", "response": None, "final_url": current_url,
                        "redirect_chain": redirect_chain}
            if not self.is_internal_url(current_url):
                return {
                    "status": "external_redirect",
                    "response": None,
                    "final_url": current_url,
                    "redirect_chain": redirect_chain,
                }

            if not self.robots.can_fetch(current_url):
                return {
                    "status": "blocked",
                    "response": None,
                    "final_url": current_url,
                    "redirect_chain": redirect_chain,
                }

            response = self.request_policy.get(
                self.session, current_url,
                timeout=self.timeout,
                allow_redirects=False
            )

            self.http_results.append({"url": initial_url, "final_url": current_url,
                                      "status_code": response.status_code,
                                      "redirect_chain": list(redirect_chain)})
            if response.status_code not in self.REDIRECT_CODES:
                return {
                    "status": "success",
                    "response": response,
                    "final_url": current_url,
                    "redirect_chain": redirect_chain,
                }

            location = response.headers.get("Location")

            if not location:
                return {
                    "status": "success",
                    "response": response,
                    "final_url": current_url,
                    "redirect_chain": redirect_chain,
                }

            destination = self.normalize_url(
                urljoin(current_url, location)
            )

            redirect_chain.append({
                "from": current_url,
                "to": destination,
                "status_code": response.status_code,
            })

            response.close()

            if not destination:
                return {
                    "status": "invalid_redirect",
                    "response": None,
                    "final_url": current_url,
                    "redirect_chain": redirect_chain,
                }

            if not self.is_internal_url(destination):
                return {
                    "status": "external_redirect",
                    "response": None,
                    "final_url": destination,
                    "redirect_chain": redirect_chain,
                }

            current_url = destination

        return {
            "status": "too_many_redirects",
            "response": None,
            "final_url": current_url,
            "redirect_chain": redirect_chain,
        }

    # --------------------------------------------------
    # PAGE STORAGE
    # --------------------------------------------------

    def save_page(
        self,
        page_data,
        depth=0,
        parent_url=None
    ):

        page_data = dict(page_data)

        page_data["depth"] = depth
        page_data["parent_url"] = parent_url

        page_data["redirect_chain_json"] = (
            page_data.get("redirect_chain_json") or "[]"
        )

        page_data["crawl_status"] = "success"
        page_data["crawl_error"] = None

        page_id = PageRepository.save_page(
            self.analysis_run_id,
            page_data
        )

        if page_id is None:
            raise RuntimeError(
                "PageRepository did not return a page ID."
            )

        self.stats["saved"] += 1

        return page_id

    # --------------------------------------------------
    # PAGE CONTENT STORAGE
    # --------------------------------------------------

    def save_page_content(
        self,
        page_id,
        page_data
    ):

        content_id = PageContentRepository.save_page_content(
            page_id=page_id,
            text_content=page_data.get("text_content", ""),
            h1_list=page_data.get("h1_list", []),
            h2_list=page_data.get("h2_list", []),
            h3_list=page_data.get("h3_list", []),
            content_hash=page_data.get("content_hash")
        )

        if content_id is None:
            raise RuntimeError(
                "PageContentRepository did not return a content ID."
            )

        self.stats["contents_saved"] += 1

        return content_id

    # --------------------------------------------------
    # LINK STORAGE
    # --------------------------------------------------

    def save_links(
        self,
        page_id,
        page_url,
        links
    ):

        saved_count = PageLinkRepository.save_links(
            analysis_run_id=self.analysis_run_id,
            source_page_id=page_id,
            links=links
        )

        if saved_count is None:
            saved_count = len(links)

        self.stats["links_saved"] += saved_count

        return saved_count

    # --------------------------------------------------
    # CRAWL SINGLE PAGE
    # --------------------------------------------------

    def crawl_page(
        self,
        url,
        depth=0,
        parent_url=None
    ):

        if self._check_cancelled():
            return "cancelled"

        self.stats["attempted"] += 1

        normalized_url = self.normalize_url(url)

        try:

            if not self.robots.can_fetch(normalized_url):

                self.stats["blocked"] += 1

                self.log_event(
                    "robots_blocked",
                    "URL blocked by robots.txt",
                    normalized_url,
                    severity="medium"
                )

                print(
                    f"[BLOCKED] robots.txt: {normalized_url}"
                )

                return "blocked"

            result = self.request_page(
                normalized_url
            )

            redirect_chain = result["redirect_chain"]

            if result["status"] == "cancelled":
                return "cancelled"

            if result["status"] == "blocked":

                self.stats["blocked"] += 1

                self.log_event(
                    "robots_blocked",
                    "Redirect destination blocked by robots.txt",
                    result["final_url"],
                    severity="medium"
                )

                print(
                    f"[BLOCKED] Redirect destination: "
                    f"{result['final_url']}"
                )

                return "blocked"

            if result["status"] == "external_redirect":

                self.stats["skipped"] += 1

                print(
                    f"[SKIPPED] External redirect: "
                    f"{normalized_url}"
                )

                return "completed"

            if result["status"] != "success":

                self.stats["failed"] += 1

                self.log_event(
                    "redirect_error",
                    result["status"],
                    normalized_url,
                    severity="high"
                )

                print(
                    f"[REDIRECT ERROR] {normalized_url}: "
                    f"{result['status']}"
                )

                return "failed"

            response = result["response"]

            try:

                response.raise_for_status()

                final_url = self.normalize_url(
                    response.url
                )

                if not self.is_internal_url(final_url):
                    self.stats["skipped"] += 1
                    return "completed"

                content_type = response.headers.get(
                    "Content-Type",
                    ""
                ).lower()

                if "text/html" not in content_type:

                    self.stats["skipped"] += 1

                    self.log_event(
                        "non_html_skipped",
                        "Non-HTML resource skipped",
                        final_url
                    )

                    print(
                        f"[SKIPPED] Non-HTML content: "
                        f"{final_url}"
                    )

                    return "completed"

                page_data = self.parser.parse(
                    response.text,
                    final_url,
                    status_code=response.status_code,
                    response_headers=response.headers
                )

                self.log_event("page_observation", "Parsed page evidence", final_url,
                               details={**{k: v for k, v in page_data.items() if k != 'text_content'},
                                        'performance': getattr(response, 'seo_metrics', {})})
                page_data["url"] = final_url
                page_data["final_url"] = final_url
                page_data["content_type"] = content_type

                page_data["redirect_chain_json"] = json.dumps(
                    redirect_chain,
                    ensure_ascii=False
                )

                page_id = self.save_page(
                    page_data,
                    depth=depth,
                    parent_url=parent_url
                )

                self.save_page_content(
                    page_id,
                    page_data
                )

                links = self.extract_links(
                    response.text,
                    final_url,
                    current_depth=depth
                )

                self.save_links(
                    page_id,
                    final_url,
                    links
                )

                self.stats["crawled"] += 1

                self.visited.add(normalized_url)
                self.visited.add(final_url)

                print(
                    f"[CRAWLED] "
                    f"{self.stats['crawled']} successful pages | "
                    f"{final_url}"
                )

                return "completed"

            finally:
                response.close()

        except requests.exceptions.Timeout as error:

            self.stats["failed"] += 1

            self.log_event(
                "request_timeout",
                str(error),
                normalized_url,
                severity="high"
            )

            print(
                f"[TIMEOUT] {normalized_url}"
            )

            return "failed"

        except requests.exceptions.RequestException as error:

            self.stats["failed"] += 1

            self.log_event(
                "request_error",
                str(error),
                normalized_url,
                severity="high"
            )

            print(
                f"[REQUEST ERROR] {normalized_url} - {error}"
            )

            return "failed"

        except Exception as error:

            self.stats["failed"] += 1

            self.log_event(
                "crawler_error",
                str(error),
                normalized_url,
                severity="high"
            )

            print(
                f"[CRAWLER ERROR] {normalized_url} - {error}"
            )

            return "failed"

    # --------------------------------------------------
    # CRAWL SUMMARY
    # --------------------------------------------------

    def print_summary(self):

        try:
            summary = CrawlSummaryRepository.get_run_summary(
                self.analysis_run_id
            )

            print("\n[DATABASE SUMMARY]")
            print(json.dumps(
                summary,
                ensure_ascii=False,
                indent=2,
                default=str
            ))

        except Exception as error:
            print(
                f"[SUMMARY WARNING] {error}"
            )

    # --------------------------------------------------
    # RESOURCE MANAGEMENT
    # --------------------------------------------------

    def close(self):

        if self._closed:
            return

        self._closed = True

        try:
            self.session.close()
        except Exception:
            pass

        try:
            self.sitemap_manager.close()
        except Exception:
            pass

    # --------------------------------------------------
    # FINAL STATISTICS
    # --------------------------------------------------

    def _get_queue_stats(self):

        try:
            return CrawlQueueRepository.get_queue_stats(
                self.analysis_run_id
            )
        except Exception as error:
            print(f"[QUEUE SUMMARY WARNING] {error}")
            return {}

    def _print_final_statistics(
        self,
        final_status,
        remaining_urls
    ):

        print("\n===================================")
        print(f" CRAWLING {final_status.upper()}")
        print("===================================")

        print(
            f"Attempted URLs: {self.stats['attempted']}"
        )

        print(
            f"Successfully crawled: {self.stats['crawled']}"
        )

        print(
            f"Saved pages: {self.stats['saved']}"
        )

        print(
            f"Saved page contents: {self.stats['contents_saved']}"
        )

        print(
            f"Failed requests: {self.stats['failed']}"
        )

        print(
            f"Blocked by robots.txt: {self.stats['blocked']}"
        )

        print(
            f"Skipped resources: {self.stats['skipped']}"
        )

        print(
            f"Saved links: {self.stats['links_saved']}"
        )

        print(
            f"Remaining URLs in queue: {remaining_urls}"
        )

        print("===================================\n")

    # --------------------------------------------------
    # MAIN CRAWLING PROCESS
    # --------------------------------------------------

    def run(self, website_url: str):
        """
        Execute a complete analysis run.

        Lifecycle contract:
        pending -> running -> completed / failed / cancelled
        """

        started = AnalysisRepository.start_analysis_run(
            self.analysis_run_id
        )

        if not started:
            raise RuntimeError(
                f"Could not start analysis run "
                f"{self.analysis_run_id}. "
                "The run may not be pending."
            )

        self._started = True

        final_status = "failed"
        completion_reason = None
        error_message = None
        remaining_urls = None

        try:

            if not isinstance(website_url, str):
                raise ValueError(
                    "Website URL must be a string."
                )

            website_url = website_url.strip()

            if not website_url:
                raise ValueError(
                    "Website URL cannot be empty."
                )

            if not website_url.startswith(
                ("http://", "https://")
            ):
                website_url = "https://" + website_url

            self.base_url = self.normalize_url(
                website_url
            )

            if not self.base_url:
                raise ValueError(
                    "Invalid website URL."
                )

            parsed_base = urlparse(
                self.base_url
            )

            self.base_domain = parsed_base.hostname.lower()

            print("\n===================================")
            print(" SEO INTELLIGENCE - CRAWLER")
            print("===================================")
            print(f"Analysis Run ID: {self.analysis_run_id}")
            print(f"Website: {self.base_url}")
            print(f"Maximum attempted URLs: {self.max_pages}")
            print("===================================\n")

            if not self._heartbeat_or_raise():
                final_status = "cancelled"
                completion_reason = "user_requested_cancellation"

            else:

                self.robots = RobotsManager(
                    self.base_url,
                    user_agent=self.USER_AGENT,
                    request_policy=self.request_policy
                )

                if not self.robots.can_fetch(self.base_url):
                    raise RuntimeError(
                        "Crawling stopped: robots.txt does not allow "
                        "access to the target URL or could not be verified."
                    )

                # --------------------------------------
                # Recover interrupted queue items
                # --------------------------------------

                recovered = (
                    CrawlQueueRepository.recover_processing_items(
                        self.analysis_run_id
                    )
                )

                if recovered:
                    print(
                        f"[INFO] Recovered interrupted URLs: "
                        f"{recovered}"
                    )

                # --------------------------------------
                # Add website root
                # --------------------------------------

                self.add_to_queue(
                    self.base_url,
                    depth=0,
                    parent_url=None,
                    discovered_from="website_root",
                    priority=100
                )

                # --------------------------------------
                # Sitemap discovery
                # --------------------------------------

                if not self._check_cancelled():

                    try:

                        self.sitemap_manager.request_policy = self.request_policy
                        sitemap_urls = self.sitemap_manager.discover(
                            self.base_url,
                            self.robots
                        )

                        self.sitemap_urls = list(sitemap_urls)
                        sitemap_added = 0

                        for sitemap_url in sitemap_urls:

                            if self._check_cancelled():
                                break

                            added = self.add_to_queue(
                                sitemap_url,
                                depth=0,
                                parent_url=None,
                                discovered_from="sitemap",
                                priority=50
                            )

                            if added:
                                sitemap_added += 1

                        print(
                            f"[INFO] Sitemap URLs discovered: "
                            f"{len(sitemap_urls)}"
                        )

                        print(
                            f"[INFO] Sitemap URLs added to queue: "
                            f"{sitemap_added}"
                        )

                    except Exception as error:

                        self.log_event(
                            "sitemap_error",
                            str(error),
                            self.base_url,
                            severity="medium"
                        )

                        print(
                            f"[SITEMAP WARNING] {error}"
                        )

                # --------------------------------------
                # Main persistent queue loop
                # --------------------------------------

                while (
                    not self._check_cancelled()
                    and self.stats["attempted"] < self.max_pages
                ):

                    self._heartbeat_or_raise()

                    if self._check_cancelled():
                        break

                    queue_item = CrawlQueueRepository.get_next_url(
                        self.analysis_run_id
                    )

                    if queue_item is None:
                        completion_reason = "queue_empty"
                        break

                    queue_id = queue_item["id"]
                    current_url = queue_item["url"]

                    normalized_url = self.normalize_url(
                        current_url
                    )

                    if not normalized_url:

                        CrawlQueueRepository.update_status(
                            queue_id,
                            "failed",
                            last_error="Invalid URL"
                        )

                        continue

                    if normalized_url in self.visited:

                        CrawlQueueRepository.update_status(
                            queue_id,
                            "completed"
                        )

                        continue

                    self.visited.add(normalized_url)

                    depth = queue_item.get("depth", 0) or 0

                    parent_url = queue_item.get(
                        "parent_url"
                    )

                    if self.progress_callback:
                        self.progress_callback(f"Checking URL {self.stats['attempted'] + 1}: {normalized_url}",
                                               10 + int(30 * self.stats['attempted'] / self.max_pages))
                    status = self.crawl_page(
                        normalized_url,
                        depth=depth,
                        parent_url=parent_url
                    )

                    if status == "cancelled":

                        # Keep the current item available
                        # for a future retry.
                        CrawlQueueRepository.update_status(
                            queue_id,
                            "queued"
                        )

                        break

                    if status == "completed":

                        CrawlQueueRepository.update_status(
                            queue_id,
                            "completed"
                        )

                    elif status == "blocked":

                        CrawlQueueRepository.update_status(
                            queue_id,
                            "blocked",
                            last_error="Blocked by robots.txt"
                        )

                    else:

                        CrawlQueueRepository.update_status(
                            queue_id,
                            "failed",
                            last_error="Crawl request failed"
                        )

                # --------------------------------------
                # Determine final state
                # --------------------------------------

                if self._check_cancelled():

                    final_status = "cancelled"
                    completion_reason = (
                        "user_requested_cancellation"
                    )

                else:

                    if (
                        self.stats["attempted"] >= self.max_pages
                    ):
                        completion_reason = "max_pages_reached"

                    elif completion_reason is None:
                        completion_reason = "queue_finished"

                    final_status = "completed"

        except Exception as error:

            final_status = "failed"
            completion_reason = "fatal_error"
            error_message = str(error)

            self.log_event(
                "analysis_failed",
                error_message,
                self.base_url,
                severity="critical"
            )

            print(
                f"\n[ANALYSIS FAILED] {error_message}"
            )

        finally:

            # Always release network resources.
            self.close()

            queue_stats = self._get_queue_stats()

            remaining_urls = queue_stats.get(
                "queued"
            )

            # ------------------------------------------
            # Finish analysis lifecycle
            # ------------------------------------------

            try:

                finished = AnalysisRepository.finish_analysis_run(
                    run_id=self.analysis_run_id,
                    status=final_status,
                    error_message=error_message,
                    completion_reason=completion_reason,
                    summary=self.stats
                )

                if not finished:
                    print(
                        "[LIFECYCLE ERROR] "
                        "Repository could not finish the analysis run."
                    )

            except Exception as finish_error:

                print(
                    f"[LIFECYCLE ERROR] "
                    f"Could not save final analysis status: "
                    f"{finish_error}"
                )

                if final_status == "completed":
                    final_status = "failed"

        self._print_final_statistics(
            final_status,
            remaining_urls
        )

        self.print_summary()

        if final_status == "failed":
            raise RuntimeError(
                error_message or
                "Crawler analysis failed. "
                "Check the crawl events and application logs."
            )

        return self.stats

    # --------------------------------------------------
    # CONTEXT MANAGER
    # --------------------------------------------------

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False