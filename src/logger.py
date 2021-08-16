import functools
import logging
import os
from pathlib import Path
from copy import copy
from logging.config import dictConfig
from src import app_data_dir

logger = logging.getLogger('decorator-log')

# Create a custom formatter to change the color of the stream logs
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


# Create the .log file in the AppData folder.
f = open(app_data_dir.joinpath("logs.txt"), "w")  # Create the file
f.close()

# Create a root logger. These configurations will be used by all loggers when calling logging.getLogger().
log_config = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'file': {
            'format': '>>%(asctime)s [%(levelname)s] %(filename)s (%(funcName)s:%(lineno)d):\n %(message)s',
            'datefmt': '%m/%d/%Y %I:%M:%S %p'
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
            'filename': str(app_data_dir.joinpath("logs.txt")),
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

dictConfig(log_config)  # Apply the log configuration


class Log(object):
    def __init__(self):
        """
        Logger decorator class for easy logging.
        """
        self.logger = logging.getLogger('decorator-log')

    def __call__(self, fn):
        @functools.wraps(fn)
        def decorated(*args, **kwargs):
            try:
                self.logger.info(f"::IN: {fn.__name__} - {args}, {kwargs}")
                result = fn(*args, **kwargs)
                self.logger.info(f"::OUT: {result}")
                return result
            except Exception as ex:
                self.logger.info(f"Exception {ex}")
                raise ex
            # return result
        return decorated
