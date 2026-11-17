from typing import Dict, List, Any, Optional


class PageAuditRules:
    """
    Technical SEO Page-Level Audit Rules Engine (Step 13).
    Evaluates individual parsed pages against standard SEO best practices (Non-AI).
    """

    @staticmethod
    def audit_page(page_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Runs all page-level audit checks on a single parsed page dictionary 
        and returns a list of identified issues/audits.
        """
        issues = []

        if not isinstance(page_data, dict):
            return issues

        url = page_data.get("url") or page_data.get("final_url", "unknown_url")
        status_code = page_data.get("status_code", 200)

        # ۱. بررسی خطاهای وضعیت HTTP (صفحات 4xx یا 5xx)
        if isinstance(status_code, int) and status_code >= 400:
            issues.append({
                "rule_id": "HTTP_ERROR_STATUS",
                "category": "Technical",
                "severity": "Critical" if status_code >= 500 else "High",
                "title": f"HTTP Error Status Code: {status_code}",
                "description": f"The page returned an error status code {status_code}.",
                "url": url,
                "evidence": {"status_code": status_code},
                "recommendation": "Fix server errors (5xx) or broken/missing page links resulting in 4xx."
            })
            # اگر صفحه خطا داشته باشد، ادامه بررسی‌های محتوایی ممکن است نامعتبر باشد
            return issues

        # ساختار محتوایی و متادیتا
        structure = page_data.get("structure", {})
        if not structure and "title" in page_data:
            # اگر ساختار تخت بود
            structure = page_data

        title = structure.get("title", "")
        meta_description = structure.get("meta_description", "")
        h1_list = structure.get("h1", [])
        if isinstance(h1_list, str):
            h1_list = [h1_list]
        word_count = structure.get("word_count", 0)

        # ۲. بررسی Title
        if not title or not title.strip():
            issues.append({
                "rule_id": "PAGE_TITLE_MISSING",
                "category": "On-Page",
                "severity": "High",
                "title": "Missing Page Title",
                "description": "The page does not have a Title tag, which is critical for search engine rankings.",
                "url": url,
                "evidence": {"title": title},
                "recommendation": "Add a unique, descriptive Title tag (ideal length: 50-60 characters)."
            })
        else:
            title_len = len(title.strip())
            if title_len < 10:
                issues.append({
                    "rule_id": "PAGE_TITLE_TOO_SHORT",
                    "category": "On-Page",
                    "severity": "Medium",
                    "title": "Title Tag Too Short",
                    "description": f"Page title is too short ({title_len} characters).",
                    "url": url,
                    "evidence": {"title": title, "length": title_len},
                    "recommendation": "Expand the title to provide more context and target keywords (target 50-60 chars)."
                })
            elif title_len > 70:
                issues.append({
                    "rule_id": "PAGE_TITLE_TOO_LONG",
                    "category": "On-Page",
                    "severity": "Low",
                    "title": "Title Tag Too Long",
                    "description": f"Page title is too long ({title_len} characters) and may be truncated in SERPs.",
                    "url": url,
                    "evidence": {"title": title, "length": title_len},
                    "recommendation": "Shorten the title to under 60 characters."
                })

        # ۳. بررسی Meta Description
        if not meta_description or not meta_description.strip():
            issues.append({
                "rule_id": "META_DESCRIPTION_MISSING",
                "category": "On-Page",
                "severity": "Medium",
                "title": "Missing Meta Description",
                "description": "The page lacks a meta description tag.",
                "url": url,
                "evidence": {"meta_description": meta_description},
                "recommendation": "Add a compelling meta description (ideal length: 120-160 characters)."
            })
        else:
            desc_len = len(meta_description.strip())
            if desc_len < 50:
                issues.append({
                    "rule_id": "META_DESCRIPTION_TOO_SHORT",
                    "category": "On-Page",
                    "severity": "Low",
                    "title": "Meta Description Too Short",
                    "description": f"Meta description is too short ({desc_len} characters).",
                    "url": url,
                    "evidence": {"meta_description": meta_description, "length": desc_len},
                    "recommendation": "Expand meta description to summarize content effectively (target 120-160 chars)."
                })
            elif desc_len > 170:
                issues.append({
                    "rule_id": "META_DESCRIPTION_TOO_LONG",
                    "category": "On-Page",
                    "severity": "Low",
                    "title": "Meta Description Too Long",
                    "description": f"Meta description is too long ({desc_len} characters) and may be truncated.",
                    "url": url,
                    "evidence": {"meta_description": meta_description, "length": desc_len},
                    "recommendation": "Shorten meta description to under 160 characters."
                })

        # ۴. بررسی تگ H1
        if not h1_list or len(h1_list) == 0:
            issues.append({
                "rule_id": "H1_MISSING",
                "category": "On-Page",
                "severity": "High",
                "title": "Missing H1 Heading",
                "description": "The page does not contain any H1 heading tag.",
                "url": url,
                "evidence": {"h1_count": 0},
                "recommendation": "Add a single, clear H1 heading reflecting the main topic of the page."
            })
        elif len(h1_list) > 1:
            issues.append({
                "rule_id": "H1_MULTIPLE",
                "category": "On-Page",
                "severity": "Medium",
                "title": "Multiple H1 Headings Found",
                "description": f"The page contains {len(h1_list)} H1 tags. Best practice is to have exactly one H1.",
                "url": url,
                "evidence": {"h1_count": len(h1_list), "h1_list": h1_list},
                "recommendation": "Consolidate into a single H1 heading per page and use H2/H3 for subheadings."
            })

        # ۵. بررسی Thin Content (محتوای بسیار کم)
        if word_count > 0 and word_count < 200:
            issues.append({
                "rule_id": "THIN_CONTENT",
                "category": "Content",
                "severity": "Medium",
                "title": "Thin Content Detected",
                "description": f"Page has very low word count ({word_count} words).",
                "url": url,
                "evidence": {"word_count": word_count},
                "recommendation": "Expand page content with valuable, in-depth information or consider setting canonical/noindex if page is utility-based."
            })
        elif word_count == 0:
            issues.append({
                "rule_id": "EMPTY_CONTENT",
                "category": "Content",
                "severity": "High",
                "title": "Empty Page Content",
                "description": "No readable body text content extracted from the page.",
                "url": url,
                "evidence": {"word_count": 0},
                "recommendation": "Check if page requires JavaScript rendering or if it returns empty response."
            })

        return issues