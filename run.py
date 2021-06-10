print(f"Initializing program.")
import logging
import sys
import os
from pathlib import Path
from PySide2 import QtCore, QtGui, QtWidgets

from src.qt_py.pem_hub import PEMHub

logger = logging.getLogger(__name__)

if getattr(sys, 'frozen', False):
    application_path = Path(sys.executable).parent
    icons_path = application_path.joinpath(r"ui\icons")
else:
    application_path = Path(__file__).absolute().parents[1]
    icons_path = application_path.joinpath(r"PEMPro\src\ui\icons")
app_data_dir = Path(os.getenv('APPDATA'))


def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    logger.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

    global error_box
    error_box = QtWidgets.QErrorMessage()
    error_box.setWindowTitle('Error')
    error_box.showMessage(open(app_data_dir.joinpath(r'PEMPro\logs.txt'), "w+").read())

    # sys.exit(1)


sys.excepthook = handle_exception


def main():
    print(f"Starting app.")
    app = QtWidgets.QApplication(sys.argv)

    # path = icons_path.joinpath(r"Crone\HRES Logo.svg")
    path = icons_path.joinpath(r"crone_logo.png")
    pixmap = QtGui.QPixmap(str(path))
    splash = QtWidgets.QSplashScreen(pixmap)
    splash.show()
    # splash.showMessage("Loaded modules", color=QtCore.Qt.white)
    app.processEvents()
    # splash.resize(600, 600)

    window = PEMHub()
    splash.finish(window)
    window.show()

    timer = QtCore.QTimer()
    timer.timeout.connect(lambda: None)
    timer.start(100)

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
