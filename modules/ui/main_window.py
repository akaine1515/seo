import os
from typing import Dict, Any
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QLineEdit, QPushButton, QProgressBar, 
    QTextEdit, QFileDialog, QMessageBox, QTabWidget,
    QTableWidget, QTableWidgetItem, QFrame, QSplitter
)
from modules.ui.worker import SEOAnalysisWorker
from modules.reporting.excel_reporter import ExcelReportGenerator
from modules.reporting.html_reporter import HTMLReportGenerator


class MainWindow(QMainWindow):
    """
    Enterprise-grade Desktop UI for SEO Intelligence V2.
    Inspired by professional SEO platforms (Crawlix & SEO Engine).
    """

    def __init__(self, orchestrator_engine: Any = None):
        super().__init__()
        self.orchestrator = orchestrator_engine
        self.worker = None
        self.last_result_data = {}

        self.setWindowTitle("SEO Intelligence V2 - Enterprise SEO Audit & Strategy Suite")
        self.resize(1300, 800)
        self.setStyleSheet("""
            QMainWindow { background-color: #0f172a; color: #f8fafc; }
            QLabel { color: #e2e8f0; font-family: 'Segoe UI', sans-serif; }
            QLineEdit { background-color: #1e293b; color: #ffffff; border: 1px solid #334155; border-radius: 6px; padding: 10px; font-size: 14px; }
            QPushButton { background-color: #2563eb; color: white; border: none; border-radius: 6px; padding: 10px 20px; font-weight: bold; font-size: 14px; }
            QPushButton:hover { background-color: #1d4ed8; }
            QPushButton:disabled { background-color: #475569; color: #94a3b8; }
            QTabWidget::pane { border: 1px solid #334155; background: #1e293b; border-radius: 8px; }
            QTabBar::tab { background: #0f172a; color: #94a3b8; padding: 10px 20px; border-top-left-radius: 6px; border-top-right-radius: 6px; font-weight: bold; }
            QTabBar::tab:selected { background: #1e293b; color: #ffffff; border-bottom: 2px solid #2563eb; }
            QTableWidget { background-color: #1e293b; color: #f8fafc; gridline-color: #334155; border: none; font-size: 13px; }
            QHeaderView::section { background-color: #0f172a; color: #cbd5e1; padding: 8px; border: none; font-weight: bold; }
            QProgressBar { background-color: #1e293b; border: 1px solid #334155; border-radius: 6px; text-align: center; color: white; font-weight: bold; }
            QProgressBar::chunk { background-color: #2563eb; border-radius: 5px; }
        """)

        self._init_ui()

    def _init_ui(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)

        # ۱. سایدبار ناوبری سمت چپ
        sidebar = QFrame()
        sidebar.setFixedWidth(240)
        sidebar.setStyleSheet("background-color: #1e293b; border-radius: 10px; padding: 10px;")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        logo_label = QLabel("🚀 SEO Intelligence V2")
        logo_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #38bdf8; margin-bottom: 20px;")
        sidebar_layout.addWidget(logo_label)

        nav_items = ["Overview & Health", "Technical Audit", "Keywords & Clusters", "Competitors & Gaps", "Execution Logs"]
        self.nav_buttons = []
        for i, item in enumerate(nav_items):
            btn = QPushButton(item)
            btn.setStyleSheet("text-align: left; background-color: transparent; color: #cbd5f1; padding: 12px; border-radius: 6px;")
            btn.clicked.connect(lambda checked=False, idx=i: self.switch_tab(idx))
            sidebar_layout.addWidget(btn)
            self.nav_buttons.append(btn)

        main_layout.addWidget(sidebar)

        # ۲. پنل اصلی سمت راست
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(15)

        # نوار بالای ورودی URL و دکمه اجرا
        top_bar = QHBoxLayout()
        self.url_input = QLineEdit(self)
        self.url_input.setPlaceholderText("Enter target URL (e.g., https://example.com)...")
        
        self.run_btn = QPushButton("Start Full SEO Audit")
        self.run_btn.setStyleSheet("background-color: #10b981; color: white; padding: 10px 25px;")
        self.run_btn.clicked.connect(self.start_analysis)

        top_bar.addWidget(QLabel("Target URL:"))
        top_bar.addWidget(self.url_input)
        top_bar.addWidget(self.run_btn)
        right_layout.addLayout(top_bar)

        # نوار پیشرفت زنده
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(22)
        right_layout.addWidget(self.progress_bar)

        # تب‌های محتوایی (مطابق ساختار حرفه‌ای)
        self.tabs = QTabWidget(self)
        self.tabs.tabBar().setVisible(False)  # مخفی کردن تب‌بار بالا چون با سایدبار کنترل می‌شود

        # تب ۱: نمای کلی و سلامت
        self.overview_widget = QWidget()
        self._init_overview_tab()
        self.tabs.addTab(self.overview_widget, "Overview")

        # تب ۲: ممیزی فنی
        self.technical_table = QTableWidget(0, 6)
        self.technical_table.setHorizontalHeaderLabels(["Rule ID", "Severity", "Category", "Title", "Affected URL", "Recommendation"])
        self.tabs.addTab(self.technical_table, "Technical Audit")

        # تب ۳: کلمات کلیدی و خوشه‌ها
        self.keywords_table = QTableWidget(0, 4)
        self.keywords_table.setHorizontalHeaderLabels(["Keyword Term", "Frequency", "TF-IDF Score", "Cluster"])
        self.tabs.addTab(self.keywords_table, "Keywords")

        # تب ۴: رقبا و شکاف محتوایی
        self.competitors_table = QTableWidget(0, 4)
        self.competitors_table.setHorizontalHeaderLabels(["Competitor Domain", "Competitiveness Index", "Keywords Count", "Content Gap Action"])
        self.tabs.addTab(self.competitors_table, "Competitors")

        # تب ۵: لاگ‌های اجرایی
        self.log_output = QTextEdit(self)
        self.log_output.setReadOnly(True)
        self.log_output.setStyleSheet("font-family: Consolas; font-size: 13px; background-color: #0f172a; color: #38bdf8;")
        self.tabs.addTab(self.log_output, "Logs")

        right_layout.addWidget(self.tabs)

        # دکمه‌های خروجی پایین صفحه
        export_layout = QHBoxLayout()
        self.export_excel_btn = QPushButton("Export Multi-Sheet Excel Report")
        self.export_excel_btn.setEnabled(False)
        self.export_excel_btn.clicked.connect(self.export_excel)

        self.export_html_btn = QPushButton("Export Interactive HTML Dashboard")
        self.export_html_btn.setEnabled(False)
        self.export_html_btn.clicked.connect(self.export_html)

        export_layout.addStretch()
        export_layout.addWidget(self.export_excel_btn)
        export_layout.addWidget(self.export_html_btn)
        right_layout.addLayout(export_layout)

        main_layout.addWidget(right_panel)

    def _init_overview_tab(self):
        layout = QVBoxLayout(self.overview_widget)
        self.kpi_label = QLabel("Welcome! Enter a target domain and click 'Start Full SEO Audit' to begin deep algorithmic analysis.")
        self.kpi_label.setStyleSheet("font-size: 16px; color: #94a3b8; padding: 20px;")
        layout.addWidget(self.kpi_label)
        layout.addStretch()

    def switch_tab(self, index: int):
        self.tabs.setCurrentIndex(index)
        for i, btn in enumerate(self.nav_buttons):
            if i == index:
                btn.setStyleSheet("text-align: left; background-color: #334155; color: #38bdf8; padding: 12px; border-radius: 6px; font-weight: bold;")
            else:
                btn.setStyleSheet("text-align: left; background-color: transparent; color: #cbd5e1; padding: 12px; border-radius: 6px;")

    def log_message(self, message: str):
        self.log_output.append(message)

    def start_analysis(self):
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Validation Error", "Please enter a valid target URL.")
            return

        self.run_btn.setEnabled(False)
        self.export_excel_btn.setEnabled(False)
        self.export_html_btn.setEnabled(False)
        self.log_output.clear()
        self.progress_bar.setValue(5)

        self.worker = SEOAnalysisWorker(url, {}, self.orchestrator)
        self.worker.progress_updated.connect(self.on_progress_update)
        self.worker.analysis_finished.connect(self.on_analysis_finished)
        self.worker.error_occurred.connect(self.on_error)
        self.worker.start()

    def on_progress_update(self, message: str, progress: int):
        self.progress_bar.setValue(progress)
        self.log_message(f"[{progress}%] {message}")

    def on_analysis_finished(self, result_data: Dict[str, Any]):
        self.last_result_data = result_data
        self.progress_bar.setValue(100)
        self.run_btn.setEnabled(True)
        self.export_excel_btn.setEnabled(True)
        self.export_html_btn.setEnabled(True)

        # به‌روزرسانی جدول ممیزی فنی
        audit = result_data.get("audit_summary", {})
        issues = audit.get("issues", [])
        self.technical_table.setRowCount(len(issues))
        for row, iss in enumerate(issues):
            self.technical_table.setItem(row, 0, QTableWidgetItem(str(iss.get("rule_id", ""))))
            self.technical_table.setItem(row, 1, QTableWidgetItem(str(iss.get("severity", ""))))
            self.technical_table.setItem(row, 2, QTableWidgetItem(str(iss.get("category", ""))))
            self.technical_table.setItem(row, 3, QTableWidgetItem(str(iss.get("title", ""))))
            self.technical_table.setItem(row, 4, QTableWidgetItem(str(iss.get("url", ""))))
            self.technical_table.setItem(row, 5, QTableWidgetItem(str(iss.get("recommendation", ""))))

        # به‌روزرسانی جدول کلمات کلیدی
        kw_data = result_data.get("keyword_analysis", {}).get("keywords", [])
        self.keywords_table.setRowCount(len(kw_data))
        for row, kw in enumerate(kw_data):
            self.keywords_table.setItem(row, 0, QTableWidgetItem(str(kw.get("term", ""))))
            self.keywords_table.setItem(row, 1, QTableWidgetItem(str(kw.get("frequency", ""))))
            self.keywords_table.setItem(row, 2, QTableWidgetItem(str(kw.get("tfidf", ""))))
            self.keywords_table.setItem(row, 3, QTableWidgetItem(str(kw.get("cluster", ""))))

        # به‌روزرسانی جدول رقبا
        comps = result_data.get("project_competitors", [])
        self.competitors_table.setRowCount(len(comps))
        for row, comp in enumerate(comps):
            self.competitors_table.setItem(row, 0, QTableWidgetItem(str(comp.get("domain", ""))))
            self.competitors_table.setItem(row, 1, QTableWidgetItem(str(comp.get("competitiveness_score", ""))))
            self.competitors_table.setItem(row, 2, QTableWidgetItem(str(comp.get("keywords_count", ""))))
            self.competitors_table.setItem(row, 3, QTableWidgetItem("بررسی شکاف محتوایی و تولید مقاله تخصصی"))

        QMessageBox.information(self, "Success", "Full SEO Intelligence pipeline completed successfully!")

    def on_error(self, error_msg: str):
        self.progress_bar.setValue(0)
        self.log_message(f"ERROR: {error_msg}")
        self.run_btn.setEnabled(True)
        QMessageBox.critical(self, "Execution Error", f"An error occurred:\n{error_msg}")

    def export_excel(self):
        if not self.last_result_data:
            return
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Excel Report", "seo_audit_report.xlsx", "Excel Files (*.xlsx)")
        if file_path:
            try:
                reporter = ExcelReportGenerator()
                saved_path = reporter.generate_report(file_path, self.last_result_data)
                QMessageBox.information(self, "Exported", f"Excel report saved to:\n{saved_path}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", str(e))

    def export_html(self):
        if not self.last_result_data:
            return
        file_path, _ = QFileDialog.getSaveFileName(self, "Save HTML Dashboard", "seo_dashboard.html", "HTML Files (*.html)")
        if file_path:
            try:
                saved_path = HTMLReportGenerator.generate_report(file_path, self.last_result_data)
                QMessageBox.information(self, "Exported", f"HTML dashboard saved to:\n{saved_path}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", str(e))