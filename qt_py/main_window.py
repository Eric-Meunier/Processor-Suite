import sys
from PyQt5.QtWidgets import *
from PyQt5 import uic
import os

from qt_py.pem_file_widget import PEMFileWidget

# Load Qt ui file into a class
qtCreatorFile = "qt_ui/main_window.ui"
Ui_MainWindow, QtBaseClass = uic.loadUiType(qtCreatorFile)


class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self):
        QMainWindow.__init__(self)
        Ui_MainWindow.__init__(self)
        self.setupUi(self)

        self.menubar.setNativeMenuBar(False)

        # Connect signals to slots
        self.action_open_file.triggered.connect(self.on_file_open)

    def on_file_open(self):
        # Will eventually hold logic for choosing between different file types
        # TODO Add logger class
        print("Entering file dialog")
        dlg = QFileDialog()
        dlg.setFileMode(QFileDialog.ExistingFile)
        #dlg.setFilter("Text files (*.txt)")

        filename = dlg.getOpenFileName()[0]
        print("Opening " + filename + "...")

        # For debug
        # filename = "/home/victor/Desktop/Crone/CH934ZM.PEM"

        # Set the central widget to a contain content for working with PEMFile
        file_widget = PEMFileWidget(self)
        file_widget.open_file(os.path.basename(filename))
        self.setCentralWidget(file_widget)
        # self.centralWidget().layout().addWidget(file_widget)

        # For debug
        # p = self.centralWidget().palette()
        # p.setColor(self.centralWidget().backgroundRole(), Qt.cyan)
        # self.centralWidget().setPalette(p)
        # self.label.setParent(None)


if __name__ == "__main__":
    # Code to test MainWindow if running main_window.py
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())