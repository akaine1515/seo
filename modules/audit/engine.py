from typing import Dict, List, Any, Optional
from modules.audit.page_rules import PageAuditRules


class TechnicalSEOAuditEngine:
    """
    Enterprise-grade Technical SEO Audit Orchestration Engine (Step 13).
    Coordinates page-level and site-level technical audits, aggregating issues,
    severity distributions, and structured summary metrics (Non-AI).
    """

    def __init__(self):
        self.page_rules = PageAuditRules()

    def audit_pages_batch(self, pages_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Runs comprehensive technical and on-page SEO audits across a batch of crawled/parsed pages.
        """
        if not isinstance(pages_data, list):
            raise TypeError("pages_data must be a list of page dictionaries.")

        all_issues = []
        pages_audited_count = 0
        severity_summary = {
            "Critical": 0,
            "High": 0,
            "Medium": 0,
            "Low": 0
        }
        category_summary = {}

        for page in pages_data:
            if not isinstance(page, dict):
                continue

            pages_audited_count += 1
            page_issues = self.page_rules.audit_page(page)

            for issue in page_issues:
                all_issues.append(issue)
                
                # آمارگیری بر اساس شدت (Severity)
                sev = issue.get("severity", "Low")
                if sev in severity_summary:
                    severity_summary[sev] += 1
                else:
                    severity_summary["Low"] += 1

                # آمارگیری بر اساس دسته‌بندی (Category)
                cat = issue.get("category", "General")
                category_summary[cat] = category_summary.get(cat, 0) + 1

        # مرتب‌سازی مشکلات بر اساس سطح اهمیت (Critical -> High -> Medium -> Low)
        severity_weight = {"Critical": 4, "High": 3, "Medium": 2, "Low": 1}
        all_issues.sort(
            key=lambda x: (
                -severity_weight.get(x.get("severity", "Low"), 1),
                x.get("url", ""),
                x.get("rule_id", "")
            )
        )

        return {
            "total_pages_audited": pages_audited_count,
            "total_issues_found": len(all_issues),
            "severity_distribution": severity_summary,
            "category_distribution": category_summary,
            "issues": all_issues
        }

    def audit_site_architecture(self, all_crawled_urls: List[str], sitemap_urls: List[str]) -> List[Dict[str, Any]]:
        """
        Performs site-level architectural audits (e.g. comparing sitemap URLs with crawled pages, orphan detection).
        """
        site_issues = []
        
        if not isinstance(all_crawled_urls, list) or not isinstance(sitemap_urls, list):
            return site_issues

        crawled_set = set(all_crawled_urls)
        sitemap_set = set(sitemap_urls)

        # شناسایی صفحاتی که در Sitemap هستند اما خزش نشده‌اند یا یافت نشدند
        sitemap_missing_in_crawl = sitemap_set - crawled_set
        if sitemap_missing_in_crawl:
            site_issues.append({
                "rule_id": "SITE_SITEMAP_URLS_NOT_CRAWLED",
                "category": "Architecture",
                "severity": "Medium",
                "title": "Sitemap URLs Not Crawled or Unreachable",
                "description": f"Found {len(sitemap_missing_in_crawl)} URLs listed in XML sitemap that were not successfully crawled.",
                "url": "sitemap.xml",
                "evidence": {"missing_count": len(sitemap_missing_in_crawl), "sample_urls": list(sitemap_missing_in_crawl)[:10]},
                "recommendation": "Check if these URLs return 4xx/5xx or are blocked by robots.txt."
            })

        return site_issues