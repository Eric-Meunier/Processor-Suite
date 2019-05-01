import logging
import sys


class Color:
    normal = "\033[0m"
    black = "\033[30m"
    red = "\033[31m"
    green = "\033[32m"
    yellow = "\033[33m"
    blue = "\033[34m"
    purple = "\033[35m"
    cyan = "\033[36m"
    grey = "\033[37m"

    bold = "\033[1m"
    uline = "\033[4m"
    blink = "\033[5m"
    invert = "\033[7m"


class Logger:
    # class LoggerAdapter(logging.LoggerAdapter):
    #     def __init__(self, logger, prefix):
    #         super(LoggerAdapter, self).__init__(logger, {})
    #         self.prefix = prefix
    #
    #     def process(self, msg, kwargs):
    #         return '[%s] %s' % (self.prefix, msg), kwargs

    def __init__(self, module_name=''):
        logger = logging.getLogger(module_name)

        handler = logging.StreamHandler(sys.stdout)

        base_format = '%(asctime)s %(name)-12s %(levelname)-8s %(message)s'
        self.normal_formatter = logging.Formatter(base_format)
        self.red_formatter = logging.Formatter(Color.red + base_format)
        self.yellow_formatter = logging.Formatter(Color.blue + base_format)

        handler.setFormatter(self.normal_formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        # logger = LoggerAdapter(logger, 'Test')

        self.handler = handler
        self.logger = logger

    def info(self, *args):
        self.logger.info(''.join(str(i) for i in args))

    def debug(self, *args):
        self.logger.debug(''.join(str(i) for i in args))

    def warning(self, *args):
        self.handler.setFormatter(self.yellow_formatter)
        self.logger.warning(''.join(str(i) for i in args) +
                            Color.normal)
        self.handler.setFormatter(self.normal_formatter)

    def error(self, *args):
        self.handler.setFormatter(self.red_formatter)
        self.logger.error(''.join(str(i) for i in args) +
                          Color.normal)
        self.handler.setFormatter(self.normal_formatter)

    def exception(self, *args):
        self.handler.setFormatter(self.red_formatter)
        self.logger.exception(''.join(str(i) for i in args) +
                              Color.normal)
        self.handler.setFormatter(self.normal_formatter)
