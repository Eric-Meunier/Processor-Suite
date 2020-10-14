import sys
from src.qt_py.pem_hub import PEMHub
from PyQt5.QtWidgets import QApplication, QErrorMessage
from PyQt5.QtCore import QTimer

import logging
from logging.config import dictConfig

# Create a root logger. These configurations will be used by all loggers when calling logging.getLogger().
log_config = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'stream': {
            'format': '>>[%(levelname)s] %(filename)s (%(funcName)s:%(lineno)d):\n %(message)s'
        },
        'file': {
            'format': '>>%(asctime)s [%(levelname)s] %(filename)s (%(funcName)s:%(lineno)d):\n %(message)s',
            'datefmt': '%m/%d/%Y %I:%M:%S %p'
        },
    },
    'handlers': {
        'stream_handler': {
            'level': 'DEBUG',
            'formatter': 'stream',
            'class': 'logging.StreamHandler',
        },
        'file_handler': {
            'level': 'DEBUG',
            'formatter': 'file',
            'class': 'logging.FileHandler',
            'filename': 'logs.log',
            'mode': 'w',
        }
    },
    'loggers': {
        '': {
            'handlers': ['stream_handler', 'file_handler'],
            'level': 'INFO',
            'propagate': True
        },
    }
}

dictConfig(log_config)

logger = logging.getLogger(__name__)


def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    logger.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

    global error_box
    error_box = QErrorMessage()
    error_box.setWindowTitle('Error')
    error_box.showMessage(open('logger.log').read())
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
