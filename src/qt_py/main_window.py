import sys
import copy
import inspect
from PyQt5.QtWidgets import *
from PyQt5 import uic
from PyQt5 import QtCore
from PyQt5.QtWidgets import QFileDialog, QMainWindow, QLabel, QGridLayout, QWidget, QDesktopWidget
import os
from cfg import list_of_files
from log import Logger
logger = Logger(__name__)

from qt_py.pem_file_widget import PEMFileWidget
from qt_py.file_browser_widget import FileBrowser

# Load Qt ui file into a class
qtCreatorFile = os.path.join(os.path.dirname(os.path.realpath(__file__)),  "../qt_ui/main_window.ui")
Ui_MainWindow, QtBaseClass = uic.loadUiType(qtCreatorFile)


class ExceptionHandler(QtCore.QObject):

    errorSignal = QtCore.pyqtSignal()
    silentSignal = QtCore.pyqtSignal()

    def __init__(self):
        super(ExceptionHandler, self).__init__()

    def handler(self, exctype, value, traceback):
        self.errorSignal.emit()
        sys._excepthook(exctype, value, traceback)


exceptionHandler = ExceptionHandler()
sys._excepthook = sys.excepthook
sys.excepthook = exceptionHandler.handler


class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self):
        QMainWindow.__init__(self)
        Ui_MainWindow.__init__(self)
        self.setupUi(self)

        self.menubar.setNativeMenuBar(False)
        self.setAcceptDrops(True)

        # Connect signals to slots
        self.action_open_file.triggered.connect(self.on_file_open)
        self.action_print.triggered.connect(self.on_print)
        self.action_print_all.triggered.connect(self.on_print_all)
        self.sldInterp.valueChanged.connect(self.update_lcd)
        self.pshRecalc.clicked.connect(self.regen_plots)
        self.sldInterp.setValue(100)

        self.action_print.setShortcut("Ctrl+P")

        self.file_browser = None

        self.move(400, 0)

    def update_lcd(self):
        val = self.sldInterp.value()
        self.lcdInterp.display(val)

    def regen_plots(self):
        templist = copy.deepcopy(list_of_files)
        if len(list_of_files) != 0:
            for i in range(0,len(list_of_files)):
                self.file_browser.removeTab(0)
            self.labeltest.show()
            item = self.plotLayout.takeAt(1)
            widget = item.widget()
            widget.deleteLater()
            list_of_files.clear()
            self.open_files(templist)

    def on_print(self):
        logger.info("Entering directory dialog for saving to PDF")
        file_dialog = QFileDialog()
        file_dialog.setFileMode(QFileDialog.Directory)
        file_dialog.setOption(QFileDialog.ShowDirsOnly)
        name = QFileDialog.getExistingDirectory(self, '', 'Plots')

        if name == "":
            logger.info("No directory chosen, aborted save to PDF")
            return

        # TODO Make sure active editor field is valid
        logger.info('Saving plots to PDFs in directory "{}"'.format(name))
        self.file_browser.currentWidget().print(name)

    def on_print_all(self):
        # TODO Add method of sorting between PEM and other file types.
        logger.info("Entering directory dialog for saving to PDF")
        file_dialog = QFileDialog()
        file_dialog.setFileMode(QFileDialog.Directory)
        file_dialog.setOption(QFileDialog.ShowDirsOnly)
        name = QFileDialog.getExistingDirectory(self, '', 'Plots')

        if name == "":
            logger.info("No directory chosen, aborted save to PDF")
            return

        # TODO Make sure active editor field is valid
        logger.info('Saving plots to PDFs in directory "{}"'.format(name))
        self.file_browser.print_files(name)


    def on_file_open(self):
        # Will eventually hold logic for choosing between different file types
        # TODO Add logger class
        logger.info("Entering file dialog")

        dlg = QFileDialog()
        dlg.setNameFilter("PEM (*.pem)");

        filenames = dlg.getOpenFileNames()[0]

        if len(filenames) == 0:
            logger.info("No Files Selected")
            return
        else:
            self.open_files(filenames)

    def dragEnterEvent(self, e):
        #if e.mimeData().hasFormat('text/plain'):
        e.accept()

    def dropEvent(self, e):
        logger.info("File dropped into main window")
        urls = [url.toLocalFile() for url in e.mimeData().urls()]

        self.open_files(urls)

    def open_files(self, filenames):
        # # Set the central widget to a contain content for working with PEMFile
        # file_widget = PEMFileWidget(self)
        # file_widget.open_file(filename)
        # self.setCentralWidget(file_widget)
        # # self.centralWidget().layout().addWidget(file_widget)

        if not isinstance(filenames, list) and isinstance(filenames, str):
            filenames = [filenames]

        self.pshRecalc.setEnabled(False)
        self.pshRecalc.setText('Processing...')
        logger.info("Opening " + ', '.join(filenames) + "...")

        if not self.file_browser:
            self.file_browser = FileBrowser()

            if self.labeltest.isVisible():
                self.labeltest.hide()
                self.plotLayout.addWidget(self.file_browser)
        try:
            self.file_browser.open_files(filenames)
        except:
            self.pshRecalc.setText('Error in input, please restart')
        else:
            self.pshRecalc.setText('Regen Plots')
            self.pshRecalc.setEnabled(True)
        list_of_files.extend(filenames)


if __name__ == "__main__":
    # Code to test MainWindow if running main_window.py
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())