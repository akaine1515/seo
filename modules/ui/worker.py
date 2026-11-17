from PySide6.QtCore import QThread, Signal
from typing import Dict, Any
import threading


class SEOAnalysisWorker(QThread):
    """
    Background worker thread for running SEO crawler, audits, and report generation 
    without freezing the PySide6 user interface.
    """
    progress_updated = Signal(str, int)  # ارسال پیام وضعیت و درصد پیشرفت
    analysis_finished = Signal(dict)     # ارسال نتایج نهایی پس از اتمام
    error_occurred = Signal(str)         # ارسال پیام خطا در صورت بروز استثنا

    def __init__(self, target_url: str, options: Dict[str, Any], engine_orchestrator: Any, source_run_id=None):
        super().__init__()
        self.cancel_event = threading.Event()
        self.target_url = target_url
        self.options = options
        self.engine_orchestrator = engine_orchestrator
        self.source_run_id = source_run_id

    def cancel(self):
        self.cancel_event.set()

    def run(self):
        try:
            self.progress_updated.emit("Loading saved crawl for competitor analysis..." if self.source_run_id is not None
                                       else "Initializing crawler and analyzing target domain...", 10)
            
            # ایجاد یک تابع واسط ایمن برای ارسال سیگنال به پایپ‌لاین
            def callback_wrapper(msg: str, val: int):
                self.progress_updated.emit(msg, val)

            # اجرای فرآیند تحلیلی با استفاده از کالبک ایمن
            if self.source_run_id is None:
                result_data = self.engine_orchestrator.run_full_pipeline(self.target_url, self.options, callback_wrapper, cancel_event=self.cancel_event)
            else:
                result_data = self.engine_orchestrator.run_competitor_stage(self.source_run_id, self.options, callback_wrapper, cancel_event=self.cancel_event)
            
            self.progress_updated.emit("Results saved with coverage and stage status.", 100)
            self.analysis_finished.emit(result_data)

        except Exception as e:
            self.error_occurred.emit(str(e))
