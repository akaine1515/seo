from core.domains import site_domain
from urllib.parse import urlparse
import ipaddress
from typing import Dict, List, Any, Optional


class CompetitorDiscovery:
    """
    Enterprise-grade SEO Competitor Discovery & Ranking Engine (Non-AI).
    Features strict type safety, robust URL/IP/Localhost validation,
    unbounded project aggregation, and multi-key stable sorting.
    """

    # پسوندهای چندبخشی متداول برای پوشش دقیق‌تر دامنه‌های ساختاری
    MULTI_PART_TLDS = {
        "co.uk", "gov.uk", "ac.uk", "net.uk", "sch.uk",
        "co.ir", "ac.ir", "gov.ir", "net.ir", "org.ir",
        "com.au", "net.au", "edu.au", "gov.au",
        "co.jp", "ne.jp", "ac.jp", "go.jp",
        "com.br", "net.br", "edu.br",
        "co.in", "net.in", "ac.in", "gov.in"
    }

    def __init__(self, target_domain: str, max_competitors: int = 5):
        if not target_domain or not isinstance(target_domain, str):
            raise ValueError("Target domain must be a valid non-empty string.")
        
        cleaned_target = self._clean_domain(target_domain)
        if not cleaned_target:
            raise ValueError(f"Invalid target domain provided: '{target_domain}'")
        self.target_domain = cleaned_target

        self.max_competitors = self._validate_positive_int(max_competitors, "max_competitors")

    @staticmethod
    def _validate_positive_int(val: Any, name: str) -> int:
        """Strict integer validation preventing silent float truncation (e.g. 5.8 -> 5) or bool acceptance."""
        if isinstance(val, bool):
            raise TypeError(f"Parameter '{name}' must be an integer, got bool.")
        
        if isinstance(val, float):
            if not val.is_integer():
                raise ValueError(f"Parameter '{name}' cannot be a float with decimals, got {val}.")
            val = int(val)
        
        if isinstance(val, str):
            stripped = val.strip()
            if not stripped.isdigit():
                raise ValueError(f"Parameter '{name}' must be a valid integer string, got '{val}'.")
            val = int(val)

        if not isinstance(val, int) or val <= 0:
            raise ValueError(f"Parameter '{name}' must be a positive integer greater than 0, got {val}.")
        
        return val

    @staticmethod
    def _is_valid_url(url: Any) -> bool:
        """Performs rigorous structural URL validation, rejecting raw IPs, localhost, and malformed strings."""
        if not url or not isinstance(url, str):
            return False

        cleaned = url.strip()
        if not cleaned or " " in cleaned:
            return False

        try:
            parsed = urlparse(cleaned)
            if parsed.scheme not in ("http", "https"):
                return False

            hostname = parsed.hostname
            if not hostname:
                return False

            if parsed.username or parsed.password:
                return False
            _ = parsed.port  # Reject malformed and out-of-range ports.
            hostname_lower = hostname.lower().rstrip(".")
            labels = hostname_lower.split(".")
            if len(labels) < 2 or any(
                not label or len(label) > 63 or label.startswith("-") or label.endswith("-")
                or not all(c.isalnum() or c == "-" for c in label)
                for label in labels
            ):
                return False

            # جلوگیری از پذیرش آدرس‌های لوکال‌هست
            if hostname_lower in ("localhost", "127.0.0.1", "::1") or hostname_lower.endswith(".local"):
                return False

            # جلوگیری از پذیرش IP آدرس‌های خام به عنوان رقیب سئو
            try:
                ipaddress.ip_address(hostname)
                return False  # اگر IP باشد معتبر برای دامنه رقیب نیست
            except ValueError:
                pass  # نام دامنه است و IP نیست

            return True
        except Exception:
            return False

    @classmethod
    def _clean_domain(cls, url_or_domain: str) -> Optional[str]:
        """Extracts and normalizes the root domain securely."""
        if not isinstance(url_or_domain, str) or not url_or_domain.strip():
            return None

        cleaned_input = url_or_domain.strip()

        # بررسی ساختار طرح (scheme) جهت جلوگیری از خطای تفسیر URLهای ناقص نظیر https://
        if "://" in cleaned_input:
            if not cls._is_valid_url(cleaned_input):
                return None
            cleaned = cleaned_input
        else:
            test_url = "http://" + cleaned_input
            if not cls._is_valid_url(test_url):
                return None
            cleaned = test_url

        try:
            parsed = urlparse(cleaned)
            hostname = parsed.hostname
            if not hostname:
                return None

            hostname = hostname.lower().strip().rstrip(".")
            if hostname.startswith("www."):
                hostname = hostname[4:]

            return site_domain(cleaned) or None

        except Exception:
            return None

    def _is_target_domain(self, domain: str) -> bool:
        """Strict domain boundary check."""
        if not domain:
            return False
        return domain == self.target_domain or domain.endswith("." + self.target_domain)

    @staticmethod
    def _sanitize_and_group_serp(serp_results: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Sanitizes input SERP records and merges duplicate keyword entries."""
        if not isinstance(serp_results, list):
            raise TypeError("serp_results must be a list.")

        grouped_serp = {}

        for serp_item in serp_results:
            if not isinstance(serp_item, dict):
                continue

            raw_keyword = serp_item.get("keyword")
            if not raw_keyword or not isinstance(raw_keyword, str):
                continue

            keyword = " ".join(raw_keyword.strip().lower().split())
            if not keyword:
                continue

            organic_results = serp_item.get("organic_results", [])
            if not isinstance(organic_results, list):
                continue

            if keyword not in grouped_serp:
                grouped_serp[keyword] = []
            
            grouped_serp[keyword].extend(organic_results)

        return grouped_serp

    def _extract_keyword_competitors(self, serp_results: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Core internal method to extract and map unique competitors per keyword retaining best positions."""
        grouped_serp = self._sanitize_and_group_serp(serp_results)
        results_per_keyword = {}

        for keyword, organic_results in grouped_serp.items():
            keyword_competitors = {}

            for res in organic_results:
                if not isinstance(res, dict):
                    continue

                url = res.get("url")
                position = res.get("position")

                if not self._is_valid_url(url) or position is None:
                    continue

                try:
                    pos_int = self._validate_positive_int(position, "position")
                except (ValueError, TypeError):
                    continue

                domain = self._clean_domain(url)
                if not domain or self._is_target_domain(domain):
                    continue

                if domain in keyword_competitors:
                    if pos_int < keyword_competitors[domain]["position"]:
                        keyword_competitors[domain]["position"] = pos_int
                        keyword_competitors[domain]["url"] = url
                else:
                    keyword_competitors[domain] = {
                        "domain": domain,
                        "position": pos_int,
                        "url": url
                    }

            # مرتب‌سازی پایدار برای هر کلمه: ابتدا رتبه، سپس الفبای دامنه
            sorted_kw_comps = sorted(
                keyword_competitors.values(),
                key=lambda x: (x["position"], x["domain"])
            )
            results_per_keyword[keyword] = sorted_kw_comps

        return results_per_keyword

    def discover_competitors_per_keyword(
        self, 
        serp_results: List[Dict[str, Any]], 
        max_per_keyword: Optional[int] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Identifies and ranks top competitors for EACH individual keyword,
        enforcing max_per_keyword truncation if provided.
        """
        limit = self.max_competitors if max_per_keyword is None else self._validate_positive_int(max_per_keyword, "max_per_keyword")
        per_keyword_data = self._extract_keyword_competitors(serp_results)

        trimmed_results = {}
        for kw, comps in per_keyword_data.items():
            trimmed_results[kw] = comps[:limit]

        return trimmed_results

    def aggregate_project_competitors(self, serp_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Aggregates competitors across the entire project without arbitrary truncation limits,
        calculating metrics and applying multi-key stable sorting.
        """
        per_keyword_data = self._extract_keyword_competitors(serp_results)
        
        project_stats = {}

        for keyword, comps in per_keyword_data.items():
            for comp in comps:
                domain = comp["domain"]
                position = comp["position"]

                if domain not in project_stats:
                    project_stats[domain] = {
                        "domain": domain,
                        "appearance_count": 0,
                        "best_position": position,
                        "total_position_sum": 0,
                        "keywords_targeted": set()
                    }

                stats = project_stats[domain]
                stats["appearance_count"] += 1
                stats["total_position_sum"] += position
                stats["keywords_targeted"].add(keyword)

                if position < stats["best_position"]:
                    stats["best_position"] = position

        ranked_competitors = []
        for domain, data in project_stats.items():
            count = data["appearance_count"]
            avg_pos = data["total_position_sum"] / count if count > 0 else 99.0

            competitiveness_score = count * (20.0 / (avg_pos + 5.0))

            ranked_competitors.append({
                "domain": domain,
                "appearance_count": count,
                "best_position": data["best_position"],
                "average_position": round(avg_pos, 2),
                "keywords_count": len(data["keywords_targeted"]),
                "competitiveness_score": round(competitiveness_score, 4)
            })

        # مرتب‌سازی پایدار کلان پروژه با ۵ کلید ترتیبی
        ranked_competitors.sort(
            key=lambda x: (
                -x["competitiveness_score"],
                -x["keywords_count"],
                x["best_position"],
                x["average_position"],
                x["domain"]
            )
        )

        return ranked_competitors[:self.max_competitors]