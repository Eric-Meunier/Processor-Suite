import logging
import sys
from copy import copy
from logging.config import dictConfig

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QApplication, QErrorMessage

from src.qt_py.pem_hub import PEMHub

MAPPING = {
    'DEBUG': 37,  # white
    'INFO': 36,  # cyan
    'WARNING': 33,  # yellow
    'ERROR': 31,  # red
    'CRITICAL': 41,  # white on red bg
}
PREFIX = '\033['
SUFFIX = '\033[0m'


class ColoredFormatter(logging.Formatter):

    def __init__(self, format=None):
        logging.Formatter.__init__(self, format)

    def format(self, record):
        colored_record = copy(record)

        levelname = colored_record.levelname
        msg = colored_record.msg

        seq = MAPPING.get(levelname, 38)  # default white
        colored_levelname = f'{PREFIX}{seq}m{levelname}{SUFFIX}'  # Color the level name
        colored_msg = f'{PREFIX}{38}m{msg}{SUFFIX}'  # Color the message itself white.

        colored_record.levelname = colored_levelname
        colored_record.msg = colored_msg
        return logging.Formatter.format(self, colored_record)


# Create a root logger. These configurations will be used by all loggers when calling logging.getLogger().
log_config = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'file': {
            'format': '>>%(asctime)s [%(levelname)s] %(filename)s (%(funcName)s:%(lineno)d):\n %(message)s',
            'datefmt': '%I:%M:%S %p'
        },
        'stream': {
            '()': ColoredFormatter,
            'format': '>>[%(levelname)s] %(filename)s (%(funcName)s:%(lineno)d):\n %(message)s'
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
            'filename': 'tmp.log',
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
logger.debug('debug test')
logger.info('Info test')
logger.warning('Warning test')
logger.error('Error test')
logger.critical('critical test')


def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    logger.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

    global error_box
    error_box = QErrorMessage()
    error_box.setWindowTitle('Error')
    error_box.showMessage(open('tmp.log').read())
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
    pass
    # main()
