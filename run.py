import logging
import sys
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QApplication, QErrorMessage

from src.qt_py.pem_hub import PEMHub

logger = logging.getLogger(__name__)


def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    logger.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

    global error_box
    error_box = QErrorMessage()
    error_box.setWindowTitle('Error')
    error_box.showMessage(open('.log').read())
    # sys.exit(1)


sys.excepthook = handle_exception
# logger.info('test')
# logger.error('error')


def main():
    app = QApplication(sys.argv)
    window = PEMHub()
    window.show()
    timer = QTimer()
    timer.timeout.connect(lambda: None)
    timer.start(100)

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
