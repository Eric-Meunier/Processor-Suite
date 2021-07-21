import time
import logging
import sys
import os
from pathlib import Path
from PySide2 import QtCore, QtGui, QtWidgets
from src.ui.splash_screen import Ui_SplashScreen
# from src.qt_py.pem_hub import __version__

__version__ = '0.11.6'
if getattr(sys, 'frozen', False):
    application_path = Path(sys.executable).parent
    icons_path = application_path.joinpath(r"ui\icons")
else:
    application_path = Path(__file__).absolute().parents[1]
    icons_path = application_path.joinpath(r"PEMPro\src\ui\icons")
app_data_dir = Path(os.getenv('APPDATA'))
logger = logging.getLogger(__name__)


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

counter = 0


class SplashScreen(QtWidgets.QWidget, Ui_SplashScreen):

    def __init__(self, version):
        super().__init__()
        self.setupUi(self)
        self.setWindowFlag(QtCore.Qt.FramelessWindowHint)
        self.version_label.setText(f"Version {version}")
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)

        self.shadow = QtWidgets.QGraphicsDropShadowEffect(self)
        self.shadow.setBlurRadius(20)
        self.shadow.setXOffset(0)
        self.shadow.setXOffset(0)
        self.shadow.setColor(QtGui.QColor(0, 0, 0, 60))
        self.frame.setGraphicsEffect(self.shadow)

        # Progress bar
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.progress)
        self.timer.start(35)

        self.show()

    def showMessage(self, msg):
        self.message_label.setText(msg)
        app.processEvents()

    def progress(self):
        global counter
        self.progressBar.setValue(counter)

        if counter > 100:
            self.timer.stop()

        counter += 1


# Splash screen
app = QtWidgets.QApplication(sys.argv)
path = icons_path.joinpath(r"crone_logo.png")
pixmap = QtGui.QPixmap(str(path))
# splash = QtWidgets.QSplashScreen(pixmap)
splash = SplashScreen(__version__)
# splash.show()
# color = QtCore.Qt.white
app.processEvents()


def main():
    splash.showMessage("Importing PEMHub")
    t = time.time()
    from src.qt_py.pem_hub import PEMHub
    print(f"Time to import PEMHub: {time.time() - t:.2f}s")

    splash.showMessage("Initializing PEMHub")
    # window = PEMHub(splash_screen=splash)
    # window.show()
    # splash.close()

    timer = QtCore.QTimer()
    timer.timeout.connect(lambda: None)
    timer.start(100)

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
