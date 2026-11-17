from datetime import datetime, timezone
from typing import Any, Dict, List
from urllib.parse import urlparse, urljoin

from bs4 import BeautifulSoup
from modules.crawler.robots import RobotsManager
from modules.competitors.discovery import CompetitorDiscovery


class CompetitorAnalyzer:
    """Analyze selected pages through CrawlerEngine.request_page and PageParser.

    Links use exact hostname equality (subdomains are external). Keyword metrics
    are attached by the orchestrator after computing one shared corpus.
    """

    def __init__(self, crawler_engine: Any, page_parser: Any, tf_idf_analyzer: Any = None):
        self.crawler_engine = crawler_engine
        self.page_parser = page_parser
        self.tf_idf_analyzer = tf_idf_analyzer
        self._robots = {}

    def analyze_competitor_page(self, url: str) -> Dict[str, Any]:
        result = {"url": url, "success": False,
                  "retrieved_at": datetime.now(timezone.utc).isoformat()}
        response = None
        try:
            if not CompetitorDiscovery._is_valid_url(url):
                raise ValueError("Invalid competitor HTTP URL")
            crawler = self.crawler_engine
            crawler.base_url = crawler.normalize_url(url)
            crawler.base_domain = urlparse(crawler.base_url).netloc
            origin = urlparse(crawler.base_url)
            origin_url = f"{origin.scheme}://{origin.netloc}/"
            if origin_url not in self._robots:
                self._robots[origin_url] = RobotsManager(origin_url, user_agent=crawler.USER_AGENT, request_policy=crawler.request_policy)
            crawler.robots = self._robots[origin_url]
            fetched = crawler.request_page(url)
            response = fetched.get("response")
            result.update(final_url=fetched.get("final_url", url),
                          redirect_chain=fetched.get("redirect_chain", []))
            if fetched.get("status") != "success" or response is None:
                raise ValueError(fetched.get("status", "Missing crawl response"))
            result["status_code"] = response.status_code
            if not 200 <= response.status_code < 300:
                raise ValueError(f"HTTP {response.status_code}")
            content_type = response.headers.get("Content-Type", "").lower()
            if content_type and "html" not in content_type:
                raise ValueError("Response is not HTML")
            if not response.text.strip():
                raise ValueError("Empty HTML response")
            parsed = self.page_parser.parse(response.text, result["final_url"],
                                            response.status_code, response.headers)
            links = BeautifulSoup(response.text, "lxml").find_all("a", href=True)
            internal, external = set(), set()
            host = urlparse(result["final_url"]).hostname
            for link in links:
                link_url = self.page_parser.normalize_link_url(urljoin(result["final_url"], link["href"]))
                if not link_url:
                    continue
                (internal if urlparse(link_url).hostname == host else external).add(link_url)
            result.update(success=True, seo= {k: v for k, v in parsed.items() if k != "text_content"},
                          performance=getattr(response, "seo_metrics", {}), raw_text=parsed["text_content"],
                          structure={"title": parsed["title"],
                                     "meta_description": parsed["meta_description"],
                                     "h1": parsed["h1_list"], "h2": parsed["h2_list"],
                                     "h3": parsed["h3_list"], "word_count": parsed["word_count"]},
                          linking={"internal_links": sorted(internal),
                                   "internal_links_count": len(internal),
                                   "external_links_count": len(external)})
            if self.tf_idf_analyzer:
                result["keyword_warning"] = "Compute TF-IDF over a shared corpus in the pipeline."
        except Exception as error:
            result.update(success=False, error=str(error))
        finally:
            if response is not None:
                response.close()
        return result

    def analyze_batch(self, competitor_urls: List[str]) -> List[Dict[str, Any]]:
        """Keep failures local to each URL, including invalid batch entries."""
        if not isinstance(competitor_urls, list):
            raise TypeError("competitor_urls must be a list.")
        results = []
        for url in competitor_urls:
            if self.crawler_engine._check_cancelled():
                break
            results.append(self.analyze_competitor_page(url))
        return results
