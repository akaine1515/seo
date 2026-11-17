from PySide6.QtCore import QThread, Signal
from typing import Dict, Any


class SEOAnalysisWorker(QThread):
    """
    Background worker thread for running SEO crawler, audits, and report generation 
    without freezing the PySide6 user interface.
    """
    progress_updated = Signal(str, int)  # ارسال پیام وضعیت و درصد پیشرفت
    analysis_finished = Signal(dict)     # ارسال نتایج نهایی پس از اتمام
    error_occurred = Signal(str)         # ارسال پیام خطا در صورت بروز استثنا

    def __init__(self, target_url: str, options: Dict[str, Any], engine_orchestrator: Any):
        super().__init__()
        self.target_url = target_url
        self.options = options
        self.engine_orchestrator = engine_orchestrator

    def run(self):
        try:
            self.progress_updated.emit("Initializing crawler and analyzing target domain...", 10)
            
            # ایجاد یک تابع واسط ایمن برای ارسال سیگنال به پایپ‌لاین
            def callback_wrapper(msg: str, val: int):
                self.progress_updated.emit(msg, val)

            # اجرای فرآیند تحلیلی با استفاده از کالبک ایمن
            result_data = self.engine_orchestrator.run_full_pipeline(self.target_url, self.options, callback_wrapper)
            
            self.progress_updated.emit("Pipeline completed successfully. Preparing reports...", 90)
            self.analysis_finished.emit(result_data)

        except Exception as e:
            self.error_occurred.emit(str(e))