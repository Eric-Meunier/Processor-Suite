import sys
from src.qt_py.pem_hub import PEMHub
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer

import logging

logger = logging.getLogger(__name__)
handler = logging.StreamHandler(stream=sys.stdout)
logger.addHandler(handler)


def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    logger.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))
    sys.exit(1)


sys.excepthook = handle_exception

logging.basicConfig(filename='err.log',
                    filemode='w',
                    level=logging.INFO,
                    format='\n%(asctime)s - %(filename)s\n%(levelname)s: %(message)s',
                    datefmt='%m/%d/%Y %I:%M:%S %p')


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
