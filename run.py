import logging
import sys
import time
from pathlib import Path

from PySide2.QtCore import Qt, QTimer
from PySide2.QtGui import (QColor, QIcon)
from PySide2.QtWebEngineWidgets import QWebEngineView  # If loaded after QApplication, will break OpenGL, which breaks 3D map and Tile map.
from PySide2.QtWidgets import (QWidget, QErrorMessage, QApplication, QGraphicsDropShadowEffect)

from src import __version__, app_data_dir
from src.ui.splash_screen import Ui_SplashScreen

if getattr(sys, 'frozen', False):
    application_path = Path(sys.executable).parent
    icons_path = application_path.joinpath(r"ui\icons")
else:
    application_path = Path(__file__).absolute().parents[1]
    icons_path = application_path.joinpath(r"PEMPro\src\ui\icons")
logger = logging.getLogger(__name__)


def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    logger.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

    global error_box
    error_box = QErrorMessage()
    error_box.setWindowTitle('Error')
    error_box.showMessage(open(app_data_dir.joinpath(r'logs.txt'), "w+").read())

    # sys.exit(1)


sys.excepthook = handle_exception


class SplashScreen(QWidget, Ui_SplashScreen):

    def __init__(self, version):
        super().__init__()
        self.setupUi(self)
        self.setWindowFlag(Qt.FramelessWindowHint)
        self.version_label.setText(f"Version {version}")
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle(f"PEMPro {version}")
        self.setWindowIcon(QIcon(str(icons_path.joinpath("conder.ico"))))

        self.shadow = QGraphicsDropShadowEffect(self)
        self.shadow.setBlurRadius(20)
        self.shadow.setXOffset(0)
        self.shadow.setXOffset(0)
        self.shadow.setColor(QColor(0, 0, 0, 60))
        self.frame.setGraphicsEffect(self.shadow)

        self.counter = 0
        self.progressBar.setMaximum(10)
        self.show()

    def showMessage(self, msg):
        self.message_label.setText(msg)
        self.progress()

    def progress(self):
        self.counter += 1
        self.progressBar.setValue(self.counter)
        app.processEvents()


# Splash screen
app = QApplication(sys.argv)
path = icons_path.joinpath(r"crone_logo.png")
splash = SplashScreen(__version__)
app.processEvents()


def main():
    splash.showMessage("Loading modules...")
    t = time.time()
    from src.qt_py.pem_hub import PEMHub
    print(f"Time to import PEMHub: {time.time() - t:.2f}s")

    splash.showMessage("Initializing PEMHub")
    window = PEMHub(splash_screen=splash)
    window.show()
    splash.close()

    timer = QTimer()
    timer.timeout.connect(lambda: None)
    timer.start(100)

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
