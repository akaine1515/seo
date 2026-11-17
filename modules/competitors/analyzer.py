from typing import Dict, List, Any, Optional
from urllib.parse import urlparse, urljoin


class CompetitorAnalyzer:
    """
    Enterprise-grade Competitor Analysis Engine (Step 11).
    Reuses existing CrawlerEngine and PageParser infrastructure to crawl,
    extract structural content, analyze TF-IDF/keywords, and map internal links securely.
    """

    def __init__(self, crawler_engine: Any, page_parser: Any, tf_idf_analyzer: Any = None):
        self.crawler_engine = crawler_engine
        self.page_parser = page_parser
        self.tf_idf_analyzer = tf_idf_analyzer

    @staticmethod
    def _extract_competitor_domain(url: str) -> str:
        """Extracts clean domain to identify internal links within the competitor's website."""
        try:
            parsed = urlparse(url)
            hostname = parsed.hostname or ""
            if hostname.startswith("www."):
                hostname = hostname[4:]
            return hostname.lower()
        except Exception:
            return ""

    @staticmethod
    def _is_valid_http_url(url: str) -> bool:
        """Checks if the URL is a valid http/https web link (excluding mailto, tel, javascript, etc.)."""
        try:
            parsed = urlparse(url)
            return parsed.scheme in ("http", "https") and bool(parsed.netloc)
        except Exception:
            return False

    def analyze_competitor_page(self, url: str) -> Dict[str, Any]:
        """
        Crawls and extracts structural content from a single competitor URL safely.
        """
        if not url or not isinstance(url, str):
            raise ValueError("Invalid URL provided for competitor analysis.")

        try:
            # ۱. خزش صفحه با استفاده از موتور خزشگر موجود
            crawl_response = self.crawler_engine.fetch(url)
            if not crawl_response or not crawl_response.get("success", False):
                error_msg = crawl_response.get("error", "Unknown crawl failure") if crawl_response else "Crawl response returned None"
                return {
                    "url": url,
                    "success": False,
                    "error": error_msg
                }

            html_content = crawl_response.get("html", "")
            final_url = crawl_response.get("final_url", url)

            # ۲. استخراج ساختار صفحه با استفاده از پارسر موجود
            parsed_data = self.page_parser.parse(html_content, final_url)

            title = parsed_data.get("title", "")
            meta_description = parsed_data.get("meta_description", "")
            h1_list = parsed_data.get("h1", [])
            h2_list = parsed_data.get("h2", [])
            h3_list = parsed_data.get("h3", [])
            body_text = parsed_data.get("body_text", "")
            word_count = len(body_text.split()) if body_text else 0

            # ۳. تحلیل لینک‌ها و حل دقیق لینک‌های نسبی با urljoin
            raw_links = parsed_data.get("links", [])
            comp_domain = self._extract_competitor_domain(final_url)
            
            internal_links = []
            external_links_count = 0

            for link in raw_links:
                link_url = link.get("url", "")
                if not link_url:
                    continue

                # حل لینک‌های نسبی نسبت به URL نهایی صفحه
                absolute_link_url = urljoin(final_url, link_url)

                # حذف لینک‌های غیر وب (مثل mailto، tel، javascript و غیره)
                if not self._is_valid_http_url(absolute_link_url):
                    continue

                link_domain = self._extract_competitor_domain(absolute_link_url)
                
                if link_domain == comp_domain or not link_domain:
                    if absolute_link_url not in internal_links:
                        internal_links.append(absolute_link_url)
                else:
                    external_links_count += 1

            analysis_result = {
                "url": url,
                "final_url": final_url,
                "success": True,
                "structure": {
                    "title": title,
                    "meta_description": meta_description,
                    "h1": h1_list,
                    "h2": h2_list,
                    "h3": h3_list,
                    "word_count": word_count
                },
                "linking": {
                    "internal_links_count": len(internal_links),
                    "internal_links": internal_links,
                    "external_links_count": external_links_count
                },
                "raw_text": body_text
            }

            # ۴. تحلیل کلمات کلیدی (در صورت وجود تحلیل‌گر TF-IDF)
            if self.tf_idf_analyzer and body_text:
                try:
                    keywords_analysis = self.tf_idf_analyzer.analyze_text(body_text)
                    analysis_result["keywords_analysis"] = keywords_analysis
                except Exception as e:
                    analysis_result["keywords_analysis_error"] = str(e)

            return analysis_result

        except Exception as e:
            return {
                "url": url,
                "success": False,
                "error": f"Unexpected analysis exception: {str(e)}"
            }

    def analyze_batch(self, competitor_urls: List[str]) -> List[Dict[str, Any]]:
        """
        Analyzes a batch of competitor URLs independently, ensuring failure in one page 
        does not halt or crash the entire batch.
        """
        if not isinstance(competitor_urls, list):
            raise TypeError("competitor_urls must be a list.")

        results = []
        for url in competitor_urls:
            result = self.analyze_competitor_page(url)
            results.append(result)

        return results