import sys
from PyQt5.QtWidgets import *
from PyQt5 import uic
import os
from log import Logger
logger = Logger(__name__)

from qt_py.pem_file_widget import PEMFileWidget
from qt_py.file_browser_widget import FileBrowser

# Load Qt ui file into a class
qtCreatorFile = os.path.join(os.path.dirname(os.path.realpath(__file__)),  "../qt_ui/main_window.ui")
Ui_MainWindow, QtBaseClass = uic.loadUiType(qtCreatorFile)


class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self):
        QMainWindow.__init__(self)
        Ui_MainWindow.__init__(self)
        self.setupUi(self)

        self.menubar.setNativeMenuBar(False)
        self.setAcceptDrops(True)

        # Connect signals to slots
        self.action_open_file.triggered.connect(self.on_file_open)
        self.file_browser = None

    def on_file_open(self):
        # Will eventually hold logic for choosing between different file types
        # TODO Add logger class
        logger.info("Entering file dialog")
        dlg = QFileDialog()
        dlg.setFileMode(QFileDialog.ExistingFile)
        #dlg.setFilter("Text files (*.txt)")

        filename = dlg.getOpenFileName()[0]

        # For debug
        # filename = "/home/victor/Desktop/Crone/CH934ZM.PEM"

        self.open_file(filename)

    def dragEnterEvent(self, e):
        #if e.mimeData().hasFormat('text/plain'):
        e.accept()

    def dropEvent(self, e):
        logger.info("File dropped into main window")
        urls = [url.toLocalFile() for url in e.mimeData().urls()]
        if len(urls) > 1:
            # Currently do nothing when multiple files are dropped in
            logger.error('Multiple files not yet supported!')
            # TODO When tabs are implemented, ensure multiple files can be dragged in
            pass
        elif len(urls) == 1:
            self.open_file(urls[0])

    def open_file(self, filename):
        # # Set the central widget to a contain content for working with PEMFile
        # file_widget = PEMFileWidget(self)
        # file_widget.open_file(filename)
        # self.setCentralWidget(file_widget)
        # # self.centralWidget().layout().addWidget(file_widget)

        logger.info("Opening " + filename + "...")

        if not self.file_browser:
            self.file_browser = FileBrowser()
            self.setCentralWidget(self.file_browser)

        self.file_browser.open_file(filename)


if __name__ == "__main__":
    # Code to test MainWindow if running main_window.py
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())