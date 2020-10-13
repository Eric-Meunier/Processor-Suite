import sys
from src.qt_py.pem_hub import PEMHub
from PyQt5.QtWidgets import QApplication, QErrorMessage
from PyQt5.QtCore import QTimer

import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

file_format = logging.Formatter('\n%(asctime)s - %(filename)s (%(funcName)s - %(lineno)d)\n%(levelname)s: %(message)s',
                                datefmt='%m/%d/%Y %I:%M:%S %p')
stream_format = logging.Formatter('%(filename)s (%(funcName)s)\n%(levelname)s: %(message)s')

stream_handler = logging.StreamHandler(stream=sys.stdout)
stream_handler.setLevel(logging.WARNING)
stream_handler.setFormatter(stream_format)

file_handler = logging.FileHandler(filename='err.log', mode='w')
file_handler.setLevel(logging.WARNING)
file_handler.setFormatter(file_format)

logger.addHandler(stream_handler)
logger.addHandler(file_handler)


def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    logger.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

    global error_box
    error_box = QErrorMessage()
    error_box.setWindowTitle('Error')
    error_box.showMessage(open('err.log').read())
    # sys.exit(1)


sys.excepthook = handle_exception


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
