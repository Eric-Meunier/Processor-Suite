import os
import sys
import logging
from src.qt_py.pem_hub import PEMHub
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer

logger = logging.getLogger(__name__)
handler = logging.StreamHandler(stream=sys.stdout)
logger.addHandler(handler)


def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    logger.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))


sys.excepthook = handle_exception

# if getattr(sys, 'frozen', False):
#     # If the application is run as a bundle, the pyInstaller bootloader
#     # extends the sys module by a flag frozen=True and sets the app
#     # path into variable _MEIPASS'.
#     application_path = os.path.dirname(sys.executable)
# else:
#     application_path = os.path.dirname(os.path.abspath(__file__))
#
# src_dir = os.path.join(application_path, "src")
#
# print('src directory: '+src_dir)

# Needed to keep run.py outside of src directory
# os.chdir(src_dir)
# sys.path.append(src_dir)


def main():
    # TODO Make dedicated Application class
    app = QApplication(sys.argv)
    window = PEMHub()
    window.show()
    timer = QTimer()
    timer.timeout.connect(lambda: None)
    timer.start(100)

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
