"""Desktop entry point; the analysis pipeline is also usable without Qt."""
import sys
from core.engine import SEOOrchestrator


def main():
    from PySide6.QtWidgets import QApplication
    from modules.ui.main_window import MainWindow

    app = QApplication(sys.argv)
    main_window = MainWindow(orchestrator_engine=SEOOrchestrator())
    main_window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
