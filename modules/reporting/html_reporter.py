import os
from html import escape
from urllib.parse import urlparse
from datetime import datetime
from typing import Dict, Any


class HTMLReportGenerator:
    """
    Enterprise Interactive HTML Report Generator (Step 18 - Phase G).
    Produces a standalone, highly responsive dark/light corporate HTML dashboard 
    with built-in search, filtering, and metric visualizations (Non-AI).
    """

    @staticmethod
    def generate_report(output_path: str, project_data: Dict[str, Any]) -> str:
        """
        Generates a self-contained interactive HTML SEO audit report.
        Returns the absolute path of the generated HTML file.
        """
        if not output_path or not isinstance(output_path, str):
            raise ValueError("A valid output_path string must be provided.")
        if not isinstance(project_data, dict):
            raise TypeError("project_data must be a dictionary.")

        def safe_data(value, key=None):
            if isinstance(value, dict):
                return {escape(str(k), quote=True): safe_data(v, k) for k, v in value.items()}
            if isinstance(value, list):
                return [safe_data(v) for v in value]
            if isinstance(value, str):
                if key == "url" and urlparse(value).scheme not in ("http", "https"):
                    return "#"
                return escape(value, quote=True)
            return value

        project_data = safe_data(project_data)
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        meta = project_data.get("meta", {})
        target_domain = meta.get("target_domain", "Unknown Project")
        generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        audit_summary = project_data.get("audit_summary", {})
        total_pages = audit_summary.get("total_pages_audited", 0)
        total_issues = audit_summary.get("total_issues_found", 0)
        sev_dist = audit_summary.get("severity_distribution", {})
        critical_count = sev_dist.get("Critical", 0)
        high_count = sev_dist.get("High", 0)

        issues = audit_summary.get("issues", [])
        competitors = project_data.get("project_competitors", [])
        gap_analysis = project_data.get("content_gap_analysis", {})
        content_gaps = gap_analysis.get("content_gaps", [])

        # ساخت ردیف‌های جدول ممیزی
        issues_rows_html = ""
        for iss in issues:
            sev = iss.get("severity", "Low")
            badge_class = "badge-low"
            if sev == "Critical":
                badge_class = "badge-critical"
            elif sev == "High":
                badge_class = "badge-high"
            elif sev == "Medium":
                badge_class = "badge-medium"

            issues_rows_html += f"""
            <tr>
                <td><code>{iss.get('rule_id', '')}</code></td>
                <td><span class="badge {badge_class}">{sev}</span></td>
                <td>{iss.get('category', '')}</td>
                <td><strong>{iss.get('title', '')}</strong><br><small class="text-muted">{iss.get('description', '')}</small></td>
                <td><a href="{iss.get('url', '#')}" target="_blank" class="url-link">{iss.get('url', '')}</a></td>
                <td>{iss.get('recommendation', '')}</td>
            </tr>
            """

        # ساخت ردیف‌های جدول رقبا
        competitors_rows_html = ""
        for comp in competitors:
            competitors_rows_html += f"""
            <tr>
                <td><strong>{comp.get('domain', '')}</strong></td>
                <td>{comp.get('competitiveness_score', 0)}</td>
                <td>{comp.get('keywords_count', 0)}</td>
                <td>{comp.get('appearance_count', 0)}</td>
                <td>{comp.get('best_position', '')}</td>
                <td>{comp.get('average_position', '')}</td>
            </tr>
            """

        # ساخت ردیف‌های جدول Content Gaps
        gaps_rows_html = ""
        for gap in content_gaps:
            gaps_rows_html += f"""
            <tr>
                <td><strong>{gap.get('term', '')}</strong></td>
                <td><span class="badge badge-high">{gap.get('priority', 'Medium')}</span></td>
                <td>{gap.get('competitor_domains_count', 0)}</td>
                <td>{', '.join(gap.get('competitor_domains', []))}</td>
                <td>{gap.get('recommended_action', '')}</td>
            </tr>
            """

        availability_html = ("Analysis: " + str(meta.get('pipeline_status', 'unknown'))
                             + " | Crawl: " + str(meta.get('crawl_status', 'unknown'))
                             + "<br>Observed coverage: " + str(meta.get('coverage', {}))
                             + "<br>" + "<br>".join(meta.get("warnings", [])))
        availability_html += "<br>Competitors: " + str(project_data.get("competitor_status", "unknown"))
        availability_html += " | Content gaps: " + str(gap_analysis.get("status", "unknown"))
        empty_gap_message = ("No content gaps detected in analyzed evidence."
                             if gap_analysis.get("status") == "completed" else
                             "Content gap analysis unavailable or incomplete; this is not evidence of no gaps.")
        def data_table(title, rows, table_id):
            if not rows:
                return ""
            columns = list(dict.fromkeys(key for row in rows for key in row))
            cells = "".join("<tr>" + "".join("<td>" + str(row.get(key, "")) + "</td>" for key in columns) + "</tr>" for row in rows)
            heads = "".join("<th>" + key + "</th>" for key in columns)
            return (f'<div class="section-card"><h2>{title}</h2>'
                    f'<input id="{table_id}Search" class="search-box" placeholder="Search..." oninput="filterTable(\'{table_id}\', \'{table_id}Search\')">'
                    f'<table id="{table_id}"><thead><tr>{heads}</tr></thead><tbody>{cells}</tbody></table></div>')

        roadmap_html = data_table("SEO Roadmap (heuristic priorities)", project_data.get('seo_roadmap', []), 'roadmapTable')
        keywords_html = data_table("Keywords", project_data.get('keyword_analysis', {}).get('keywords', []), 'keywordsTable')
        extended_html = ''
        for title, key in [('جزئیات سئوی صفحات، تگ‌ها، تصاویر و دریافت HTTP', 'page_details'),
                           ('کلمات استفاده‌شده و عبارت‌های فرزند', 'keyword_inventory'),
                           ('استراتژی و شواهد هر کلمه', 'keyword_strategies')]:
            extended_html += data_table(title, project_data.get(key, []), key)
        def branch(node):
            url = node.get('url')
            text = node.get('label', '')
            if url and url != '#':
                text += f' <a href="{url}" target="_blank" rel="noopener noreferrer">صفحه منبع</a>'
            children = node.get('children', [])
            return ('<li><details open><summary>' + text + '</summary><ul>' + ''.join(branch(c) for c in children) + '</ul></details></li>') if children else '<li>' + text + '</li>'
        maps = project_data.get('keyword_mindmaps', [])
        if maps:
            extended_html += '<div class="section-card" dir="rtl"><h2>مایندمپ کلمات کلیدی</h2><p>شاخه‌ها باز و بسته می‌شوند؛ روابط فرزند از عبارت‌های مشاهده‌شده‌اند.</p><ul>' + ''.join(branch(m) for m in maps) + '</ul></div>'
        if project_data.get('analysis_limitations'):
            extended_html = '<div class="section-card" dir="rtl"><h2>محدوده و محدودیت‌های تحلیل</h2>' + '<br>'.join(project_data['analysis_limitations']) + '</div>' + extended_html
        source_info = project_data.get('serp', {})
        provenance_html = (f"Run ID: {meta.get('analysis_run_id', '')} | SERP source: {source_info.get('source', '')} | "
                           f"Source timestamp: {source_info.get('retrieved_at', '')}")
        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SEO Intelligence V2 - Audit Report for {target_domain}</title>
    <style>
        :root {{
            --bg-color: #f8f9fa;
            --card-bg: #ffffff;
            --text-color: #333333;
            --text-muted: #6c757d;
            --border-color: #dee2e6;
            --primary-color: #1f4e78;
            --primary-hover: #163757;
            --accent-color: #007bff;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
            margin: 0;
            padding: 20px;
        }}
        .container {{
            max-width: 1300px;
            margin: 0 auto;
        }}
        header {{
            background: var(--card-bg);
            padding: 25px 30px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            margin-bottom: 25px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        header h1 {{
            margin: 0;
            color: var(--primary-color);
            font-size: 24px;
        }}
        header p {{
            margin: 5px 0 0 0;
            color: var(--text-muted);
            font-size: 14px;
        }}
        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 25px;
        }}
        .kpi-card {{
            background: var(--card-bg);
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            border-left: 4px solid var(--primary-color);
        }}
        .kpi-card.critical {{ border-left-color: #dc3545; }}
        .kpi-card.high {{ border-left-color: #fd7e14; }}
        .kpi-card h3 {{
            margin: 0;
            font-size: 14px;
            color: var(--text-muted);
            text-transform: uppercase;
        }}
        .kpi-card .value {{
            font-size: 28px;
            font-weight: bold;
            margin: 10px 0 0 0;
            color: var(--text-color);
        }}
        .section-card {{
            background: var(--card-bg);
            padding: 25px 30px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            margin-bottom: 25px;
        }}
        .section-card h2 {{
            margin-top: 0;
            color: var(--primary-color);
            font-size: 18px;
            border-bottom: 2px solid var(--border-color);
            padding-bottom: 10px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
            font-size: 14px;
        }}
        td {{ overflow-wrap: anywhere; }}
        details {{ margin: 8px 0; }}
        summary {{ cursor: pointer; }}
        th, td {{
            padding: 12px 15px;
            text-align: left;
            border-bottom: 1px solid var(--border-color);
        }}
        th {{
            background-color: #f1f3f5;
            color: var(--primary-color);
            font-weight: 600;
        }}
        tr:hover {{
            background-color: #f8f9fa;
        }}
        .badge {{
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: bold;
            text-transform: uppercase;
        }}
        .badge-critical {{ background-color: #f8d7da; color: #721c24; }}
        .badge-high {{ background-color: #ffe8d6; color: #b7410e; }}
        .badge-medium {{ background-color: #fff3cd; color: #856404; }}
        .badge-low {{ background-color: #d1ecf1; color: #0c5460; }}
        .url-link {{
            color: var(--accent-color);
            text-decoration: none;
            word-break: break-all;
        }}
        .url-link:hover {{ text-decoration: underline; }}
        .search-box {{
            padding: 8px 12px;
            width: 300px;
            border: 1px solid var(--border-color);
            border-radius: 4px;
            font-size: 14px;
            margin-bottom: 15px;
        }}
        footer {{
            text-align: center;
            color: var(--text-muted);
            font-size: 13px;
            margin: 40px 0;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div>
                <h1>SEO Intelligence V2 - Audit Dashboard</h1>
                <p>Target Domain: <strong>{target_domain}</strong></p>
            </div>
            <div>
                <p>Generated At: <strong>{generated_at}</strong></p>
            </div>
        </header>

        <div class="section-card"><h2>Analysis availability</h2><p>{availability_html}</p></div>
        <div class="kpi-grid">
            <div class="kpi-card">
                <h3>Total Pages Audited</h3>
                <div class="value">{total_pages}</div>
            </div>
            <div class="kpi-card">
                <h3>Total Issues Found</h3>
                <div class="value">{total_issues}</div>
            </div>
            <div class="kpi-card critical">
                <h3>Critical Issues</h3>
                <div class="value">{critical_count}</div>
            </div>
            <div class="kpi-card high">
                <h3>High Severity</h3>
                <div class="value">{high_count}</div>
            </div>
        </div>

        <div class="section-card">
            <h2>Technical & On-Page SEO Issues</h2>
            <input type="text" id="issueSearch" class="search-box" placeholder="Search issues..." oninput="filterTable('issuesTable', 'issueSearch')">
            <table id="issuesTable">
                <thead>
                    <tr>
                        <th>Rule ID</th>
                        <th>Severity</th>
                        <th>Category</th>
                        <th>Title & Description</th>
                        <th>Affected URL</th>
                        <th>Recommendation</th>
                    </tr>
                </thead>
                <tbody>
                    {issues_rows_html if issues_rows_html else '<tr><td colspan="6" style="text-align:center;">No technical issues found.</td></tr>'}
                </tbody>
            </table>
        </div>

        <div class="section-card">
            <h2>Top Competitors Analysis</h2>
            <table>
                <thead>
                    <tr>
                        <th>Competitor Domain</th>
                        <th>Competitiveness Index</th>
                        <th>Keywords Targeted</th>
                        <th>SERP Appearances</th>
                        <th>Best Position</th>
                        <th>Average Position</th>
                    </tr>
                </thead>
                <tbody>
                    {competitors_rows_html if competitors_rows_html else '<tr><td colspan="6" style="text-align:center;">No competitor data available.</td></tr>'}
                </tbody>
            </table>
        </div>

        <div class="section-card">
            <h2>Content Gaps (Missing Topics)</h2>
            <table>
                <thead>
                    <tr>
                        <th>Missing Term / Topic</th>
                        <th>Priority</th>
                        <th>Unique Competitors</th>
                        <th>Competitor Domains</th>
                        <th>Recommended Action</th>
                    </tr>
                </thead>
                <tbody>
                    {gaps_rows_html if gaps_rows_html else '<tr><td colspan="5" style="text-align:center;">' + empty_gap_message + '</td></tr>'}
                </tbody>
            </table>
        </div>

        {roadmap_html}
        {keywords_html}
        {extended_html}
        <div class="section-card"><h2>Data provenance</h2><p>{provenance_html}</p></div>
        <footer>
            <p>Generated by SEO Intelligence V2 (Non-AI Algorithmic SEO Engine) • Desktop Application for Windows</p>
        </footer>
    </div>

    <script>
        function filterTable(tableId, inputId) {{
            let input = document.getElementById(inputId);
            let filter = input.value.toLowerCase();
            let table = document.getElementById(tableId);
            let tr = table.getElementsByTagName("tr");

            for (let i = 1; i < tr.length; i++) {{
                let td = tr[i].getElementsByTagName("td");
                let match = false;
                for (let j = 0; j < td.length; j++) {{
                    if (td[j]) {{
                        if (td[j].innerHTML.toLowerCase().indexOf(filter) > -1) {{
                            match = true;
                            break;
                        }}
                    }}
                }}
                tr[i].style.display = match ? "" : "none";
            }}
        }}
    </script>
</body>
</html>
"""

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        return os.path.abspath(output_path)