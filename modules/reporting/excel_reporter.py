import os
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
import pandas as pd
from openpyxl.styles import Font, PatternFill, Alignment


class ExcelReportGenerator:
    """
    Enterprise Multi-Sheet Excel Report Generator (Step 18 - Phase G).
    Exports SEO Intelligence V2 analysis results into a formatted, multi-sheet .xlsx workbook.
    """

    def __init__(self):
        self.header_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
        self.header_font = Font(color="FFFFFF", bold=True, size=11)
        self.header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    def _style_worksheet(self, worksheet, df: pd.DataFrame) -> None:
        """Applies clean corporate styling, auto-column widths, and frozen header panes."""
        worksheet.freeze_panes = "A2"
        worksheet.auto_filter.ref = worksheet.dimensions

        # استایل‌دهی به ردیف هدر
        for col_idx in range(1, len(df.columns) + 1):
            cell = worksheet.cell(row=1, column=col_idx)
            cell.fill = self.header_fill
            cell.font = self.header_font
            cell.alignment = self.header_alignment

        # تنظیم خودکار عرض ستون‌ها بر اساس محتوا (با سقف منطقی)
        for col_idx, column in enumerate(df.columns, start=1):
            col_letter = worksheet.cell(row=1, column=col_idx).column_letter
            max_length = len(str(column))
            
            for row_idx in range(2, len(df) + 2):
                val = worksheet.cell(row=row_idx, column=col_idx).value
                if val is not None:
                    val_len = len(str(val))
                    if val_len > max_length:
                        max_length = val_len
            
            adjusted_width = min(max_length + 4, 60)
            worksheet.column_dimensions[col_letter].width = max(adjusted_width, 14)

    def generate_report(self, output_path: str, project_data: Dict[str, Any]) -> str:
        """
        Generates the complete multi-sheet Excel report from aggregated analysis data.
        Returns the absolute path of the generated file.
        """
        if not output_path or not isinstance(output_path, str):
            raise ValueError("A valid output_path string must be provided.")
        if not isinstance(project_data, dict):
            raise TypeError("project_data must be a dictionary.")

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        # استخراج بخش‌های مختلف داده با مقادیر پیش‌فرض ایمن
        meta = project_data.get("meta", {})
        audit_summary = project_data.get("audit_summary", {})
        issues = audit_summary.get("issues", [])
        cannibalization = project_data.get("cannibalization_issues", [])
        competitors = project_data.get("project_competitors", [])
        gap_analysis = project_data.get("content_gap_analysis", {})
        content_gaps = gap_analysis.get("content_gaps", [])
        keyword_overlaps = gap_analysis.get("keyword_overlaps", [])

        # ۱. آماده‌سازی داده‌های شیت Project Overview
        sev_dist = audit_summary.get("severity_distribution", {})
        overview_rows = [
            {"Metric": "Project / Target Domain", "Value": meta.get("target_domain", "N/A")},
            {"Metric": "Report Generated At", "Value": datetime.now().strftime("%Y-%m-%d %H:%M:%S")},
            {"Metric": "Total Pages Audited", "Value": audit_summary.get("total_pages_audited", 0)},
            {"Metric": "Total Technical/On-Page Issues", "Value": audit_summary.get("total_issues_found", 0)},
            {"Metric": "Critical Issues", "Value": sev_dist.get("Critical", 0)},
            {"Metric": "High Severity Issues", "Value": sev_dist.get("High", 0)},
            {"Metric": "Medium Severity Issues", "Value": sev_dist.get("Medium", 0)},
            {"Metric": "Low Severity Issues", "Value": sev_dist.get("Low", 0)},
            {"Metric": "Keyword Cannibalization Cases", "Value": len(cannibalization)},
            {"Metric": "Top Competitors Identified", "Value": len(competitors)},
            {"Metric": "Content Gaps Identified", "Value": len(content_gaps)},
            {"Metric": "Keyword Overlaps Identified", "Value": len(keyword_overlaps)},
        ]
        overview_rows.extend([
            {"Metric": "Analysis run ID", "Value": meta.get("analysis_run_id", "")},
            {"Metric": "Competitor stage", "Value": project_data.get("competitor_status", "unknown")},
            {"Metric": "Content gap stage", "Value": gap_analysis.get("status", "unknown")},
            {"Metric": "Limitations", "Value": " | ".join(meta.get("warnings", []))},
        ])
        overview_rows.extend([
            {"Metric": "Analysis status", "Value": meta.get('pipeline_status', 'unknown')},
            {"Metric": "Crawl status", "Value": meta.get('crawl_status', 'unknown')},
            {"Metric": "Observed crawl coverage", "Value": json.dumps(meta.get('coverage', {}), ensure_ascii=False)},
        ])
        df_overview = pd.DataFrame(overview_rows)

        # ۲. آماده‌سازی شیت Technical & On-Page Audit
        audit_rows = []
        for iss in issues:
            audit_rows.append({
                "Rule ID": iss.get("rule_id", ""),
                "Severity": iss.get("severity", ""),
                "Category": iss.get("category", ""),
                "Title": iss.get("title", ""),
                "Affected URL": iss.get("url", ""),
                "Description": iss.get("description", ""),
                "Recommendation": iss.get("recommendation", ""),
                "Evidence": json.dumps(iss.get("evidence", {}), ensure_ascii=False)
            })
        df_audit = pd.DataFrame(audit_rows) if audit_rows else pd.DataFrame(
            columns=["Rule ID", "Severity", "Category", "Title", "Affected URL", "Description", "Recommendation"]
        )

        # ۳. آماده‌سازی شیت Keyword Cannibalization
        cannib_rows = []
        for item in cannibalization:
            comp_pages = ", ".join([p.get("url", "") for p in item.get("competing_pages", [])])
            cannib_rows.append({
                "Term / Keyword": item.get("term", ""),
                "Competing Pages Count": item.get("competing_pages_count", 0),
                "Competing URLs": comp_pages,
                "Severity": item.get("severity", ""),
                "Recommendation": item.get("recommendation", "")
            })
        df_cannib = pd.DataFrame(cannib_rows) if cannib_rows else pd.DataFrame(
            columns=["Term / Keyword", "Competing Pages Count", "Competing URLs", "Severity", "Recommendation"]
        )

        # ۴. آماده‌سازی شیت Competitors
        comp_rows = []
        for comp in competitors:
            comp_rows.append({
                "Competitor Domain": comp.get("domain", ""),
                "Competitiveness Index": comp.get("competitiveness_score", 0),
                "Keywords Targeted": comp.get("keywords_count", 0),
                "SERP Appearances": comp.get("appearance_count", 0),
                "Best Position": comp.get("best_position", ""),
                "Average Position": comp.get("average_position", "")
            })
        df_competitors = pd.DataFrame(comp_rows) if comp_rows else pd.DataFrame(
            columns=["Competitor Domain", "Competitiveness Index", "Keywords Targeted", "SERP Appearances", "Best Position", "Average Position"]
        )

        # ۵. آماده‌سازی شیت Content Gaps
        gap_rows = []
        for gap in content_gaps:
            gap_rows.append({
                "Missing Term / Topic": gap.get("term", ""),
                "Priority": gap.get("priority", ""),
                "Unique Competitors Covering": gap.get("competitor_domains_count", 0),
                "Competitor Domains": ", ".join(gap.get("competitor_domains", [])),
                "Evidence URLs": ", ".join(gap.get("evidence_urls", [])[:3]),
                "Recommended Action": gap.get("recommended_action", "")
            })
        df_gaps = pd.DataFrame(gap_rows) if gap_rows else pd.DataFrame(
            columns=["Missing Term / Topic", "Priority", "Unique Competitors Covering", "Competitor Domains", "Evidence URLs", "Recommended Action"]
        )

        # ۶. آماده‌سازی شیت Keyword Overlaps
        overlap_rows = []
        for ov in keyword_overlaps:
            overlap_rows.append({
                "Shared Term": ov.get("term", ""),
                "Unique Competitors Covering": ov.get("competitor_domains_count", 0),
                "Competitor Domains": ", ".join(ov.get("competitor_domains", [])),
                "Evidence URLs": ", ".join(ov.get("evidence_urls", [])[:3])
            })
        df_overlaps = pd.DataFrame(overlap_rows) if overlap_rows else pd.DataFrame(
            columns=["Shared Term", "Unique Competitors Covering", "Competitor Domains", "Evidence URLs"]
        )

        # نوشتن تمام شیت‌ها در فایل اکسل با فرمت‌بندی
        sheets_map = {
            "Project Overview": df_overview,
            "Technical Audit": df_audit,
            "Cannibalization": df_cannib,
            "Competitors": df_competitors,
            "Content Gaps": df_gaps,
            "Keyword Overlaps": df_overlaps
        }

        def rows_frame(rows):
            cleaned = [{key: json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else value
                        for key, value in row.items()} for row in rows]
            return pd.DataFrame(cleaned)

        keyword_analysis = project_data.get('keyword_analysis', {})
        for name, rows in {
            'Pages': project_data.get('crawled_pages', []),
            'Crawl HTTP Results': project_data.get('crawl_observations', []),
            'Keywords': keyword_analysis.get('keywords', []),
            'Keyword Clusters': keyword_analysis.get('clusters', []),
            'Keyword Opportunities': keyword_analysis.get('opportunities', []),
            'Competitor Pages': [{k: v for k, v in row.items() if k != 'raw_text'} for row in project_data.get('competitor_analysis', [])],
            'SEO Roadmap': project_data.get('seo_roadmap', []),
        }.items():
            if name in project_data or rows:
                sheets_map[name] = rows_frame(rows)

        extended = {
            'Page SEO Details': project_data.get('page_details'),
            'Keyword Children': project_data.get('keyword_inventory'),
            'Keyword Strategy': project_data.get('keyword_strategies'),
            'Keyword Mindmaps': project_data.get('keyword_mindmaps'),
        }
        if 'page_details' in project_data:
            extended['Images'] = [dict(image, page_url=page['url']) for page in project_data['page_details'] for image in page.get('images', [])]
            extended['HTML Tags'] = [{'url': page['url'], 'tag': tag, 'count': count}
                                     for page in project_data['page_details'] for tag, count in page.get('tag_counts', {}).items()]
            extended['HTTP Performance'] = [dict(page.get('performance', {}), url=page['url']) for page in project_data['page_details']]
        if 'keyword_strategies' in project_data:
            extended['Competitor Patterns'] = [p for plan in project_data['keyword_strategies'] for p in plan['competitor_patterns']]
            extended['Analysis Limitations'] = [{'limitation': item} for item in project_data.get('analysis_limitations', [])]
        if 'serp' in project_data:
            serp = project_data['serp']
            extended['SERP Results'] = [dict(row, keyword=entry['keyword'], source=serp.get('source'), retrieved_at=serp.get('retrieved_at'))
                                        for entry in serp.get('results', []) for row in entry.get('organic_results', [])]
        if 'competitor_selections' in project_data:
            extended['Competitor Choices'] = [{'keyword': term, 'domains': domains}
                                               for term, domains in project_data['competitor_selections'].items()]
        for name, rows in extended.items():
            if rows is not None:
                sheets_map[name] = rows_frame(rows)

        sheets_map['Run Metadata'] = rows_frame([meta])

        # Force cells to text when external strings resemble spreadsheet formulas.
        for frame in sheets_map.values():
            for column in frame.columns:
                frame[column] = frame[column].map(lambda value: "'" + value
                    if isinstance(value, str) and value.startswith(('=', '+', '-', '@')) else value)

        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            for sheet_name, df in sheets_map.items():
                df.to_excel(writer, sheet_name=sheet_name, index=False)
                worksheet = writer.sheets[sheet_name]
                self._style_worksheet(worksheet, df)

        return os.path.abspath(output_path)