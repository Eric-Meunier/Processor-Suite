import functools
import logging
import sys

logger = logging.getLogger('decorator-log')
logger.setLevel(logging.INFO)

# formatter = logging.Formatter('%(filename)s (%(funcName)s)\n%(message)s\n ',
#                               datefmt='%m/%d/%Y %I:%M:%S %p')

stream_handler = logging.StreamHandler(stream=sys.stdout)
stream_handler.setLevel(logging.INFO)
# stream_handler.setFormatter(formatter)

file_handler = logging.FileHandler(filename='err.log', mode='w')
file_handler.setLevel(logging.INFO)
# file_handler.setFormatter(formatter)

logger.addHandler(stream_handler)
logger.addHandler(file_handler)


class Log(object):
    def __init__(self):
        self.logger = logging.getLogger('decorator-log')

    def __call__(self, fn):
        @functools.wraps(fn)
        def decorated(*args, **kwargs):
            try:
                self.logger.info(f"IN: {fn.__name__} - {args}, {kwargs}")
                result = fn(*args, **kwargs)
                self.logger.info(f"OUT: {result}")
                return result
            except Exception as ex:
                self.logger.info(f"Exception {ex}")
                raise ex
            return result
        return decorated
