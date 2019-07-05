import sys
import copy

import PyQt5
from PyQt5.QtWidgets import *
from PyQt5 import uic
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5.QtWidgets import QFileDialog, QMainWindow
import os
# from cfg import list_of_files
from log import Logger
import numpy as np
import time
from scipy import stats

from src.pem.pem_editor import PEMFileEditor
from qt_py.pem_file_widget import PEMFileWidget
from qt_py.file_browser_widget import FileBrowser

logger = Logger(__name__)

# Load Qt ui file into a class
qtCreatorFile = os.path.join(os.path.dirname(os.path.realpath(__file__)), "../qt_ui/main_window.ui")
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

        self.editor = PEMFileEditor()
        self.file_browser = FileBrowser()

        self.menubar.setNativeMenuBar(False)
        self.statusBar().showMessage('Ready')

        self.setAcceptDrops(True)
        self.setWindowIcon(
            QtGui.QIcon(os.path.join(os.path.dirname(os.path.realpath(__file__)), "../qt_ui/crone_logo.ico")))

        # Connect signals to slots
        self.action_open_file.triggered.connect(self.on_file_open)
        self.action_print.triggered.connect(self.on_print)
        self.action_print.setShortcut("Ctrl+P")
        self.action_print_all.triggered.connect(self.on_print_all)
        self.action_print_all.setShortcut('Ctrl+Alt+P')
        self.btn_redraw.clicked.connect(self.redraw_plots)

        self.hideGapsToggle.stateChanged.connect(self.toggle_gaps)
        self.shareTitleToggle.stateChanged.connect(self.toggle_header_info)
        self.stnLimitToggle.stateChanged.connect(self.toggle_station_limits)

        # self.list_of_files = self.file_browser.files
        self.list_of_files = []
        self.list_widget_layout.addWidget(self.file_browser.list_widget)

        self.move(350, 0)

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
        dlg.setNameFilter("PEM (*.pem)")

        filenames = dlg.getOpenFileNames()[0]

        if len(filenames) == 0:
            logger.info("No Files Selected")
            return
        else:
            self.open_files(filenames)

    def dragEnterEvent(self, e):
        # if e.mimeData().hasFormat('text/plain'):
        e.accept()

    def dropEvent(self, e):
        logger.info("File dropped into main window")
        urls = [url.toLocalFile() for url in e.mimeData().urls()]
        self.list_of_files.extend(urls)
        self.open_files(urls)

    def open_files(self, filepaths): #, redraw=False):
        # # Set the central widget to a contain content for working with PEMFile
        # file_widget = PEMFileWidget(self)
        # file_widget.open_file(filename)
        # self.setCentralWidget(file_widget)
        # # self.centralWidget().layout().addWidget(file_widget)

        self.statusBar().showMessage('Loading...')

        if not isinstance(filepaths, list) and isinstance(filepaths, str):
            filepaths = [filepaths]

        # list_of_files.extend(filepaths)

        # if not self.file_browser:
        #     self.file_browser = FileBrowser()

        if self.labeltest.isVisible():
            self.labeltest.hide()
            self.plotLayout.addWidget(self.file_browser)

        # self.progress_bar = QProgressBar()
        self.statusBar().addPermanentWidget(self.file_browser.pbar)
        # self.progress_bar.setGeometry(0, 0, 500, 10)
        # self.progress_bar.setValue(0)

        # for i, file in enumerate(filepaths):
        #     f = filepaths[i]
        #     self.editor.open_file(f)
        #     components = self.editor.active_file.get_components()
        #     header = self.editor.active_file.get_header()
        #     survey_type = self.editor.active_file.get_survey_type()

        self.toggle_station_limits()
        self.fill_header_info()
        self.toggle_gaps()

        self.btn_redraw.setEnabled(False)

        logger.info("Opening " + ', '.join(filepaths) + "...")

        lbound, rbound = self.fill_station_limits()
        gap = self.get_gap_input()

        kwargs = {"lbound": lbound,
                  "rbound": rbound,
                  "hide_gaps": self.hideGapsToggle.isChecked(),
                  "gap": gap,
                  "Client": self.clientEdit.text(),
                  "Grid": self.gridEdit.text(),
                  "Loop": self.loopEdit.text(),
                  "Interp": self.comboBoxInterpMethod.currentText()}

        try:
            # self.timer.start()
            self.file_browser.open_files(filepaths, **kwargs)
            self.file_browser.pbar.setValue(100)
            time.sleep(0.5)
            self.statusBar().removeWidget(self.file_browser.pbar)
            self.statusBar().showMessage('Ready')
        except:
            self.central_widget.setEnabled(False)
            self.plotLayout.setEnabled(False)
            self.statusBar().showMessage('Error in input, please restart')
            raise
        else:
            self.btn_redraw.setEnabled(True)

    def redraw_plots(self):
        self.list_of_files = self.file_browser.files
        if len( self.list_of_files) != 0:
            for i in range(len( self.list_of_files)):
                self.file_browser.removeTab(0)
            self.file_browser.list_widget.clear()
            self.open_files(self.list_of_files)

    def toggle_station_limits(self):
        if self.stnLimitToggle.isChecked():
            self.lineRight.setEnabled(True)
            self.lineLeft.setEnabled(True)
            self.calc_stn_limits()
        else:
            # self.lineLeft.setText(None)
            # self.lineRight.setText(None)
            self.lineRight.setEnabled(False)
            self.lineLeft.setEnabled(False)

    def fill_station_limits(self):
        if self.lineLeft.isEnabled():
            try:
                lbound = float(self.lineLeft.text())
            except ValueError:
                lbound = None
        else:
            lbound = None

        if self.lineRight.isEnabled():
            try:
                rbound = float(self.lineRight.text())
            except ValueError:
                rbound = None
        else:
            rbound = None
        return lbound, rbound

    def calc_stn_limits(self):
        # self.pushCalcLimits.setEnabled(False)
        # self.pushCalcLimits.setText('Working...')
        if len(self.list_of_files) != 0:
            minimum = []
            maximum = []

            for f in self.list_of_files:
                self.editor.open_file(f)
                stations = self.editor.get_stations()
                minimum.append(min(stations))
                maximum.append(max(stations))

            absmin = min(minimum)
            absmax = max(maximum)
            self.lineLeft.setText(str(absmin))
            self.lineRight.setText(str(absmax))
        # self.pushCalcLimits.setText('Calculate Limits')
        # self.pushCalcLimits.setEnabled(True)

    def toggle_gaps(self):
        if self.hideGapsToggle.isChecked():
            self.calc_gap_thresh()
            self.editGapThresh.setEnabled(True)
            # self.calcGapThresh.setEnabled(True)
        else:
            self.editGapThresh.setEnabled(False)
            # self.calcGapThresh.setEnabled(False)

    def calc_gap_thresh(self):
        if len(self.list_of_files) != 0:
            gap_list = []

            for f in self.list_of_files:
                self.editor.open_file(f)
                stations = self.editor.get_stations()
                survey_type = self.editor.active_file.survey_type

                if 'borehole' in survey_type.casefold():
                    min_gap = 50
                elif 'surface' in survey_type.casefold():
                    min_gap = 200

                station_gaps = np.diff(stations)
                gap = max(int(stats.mode(station_gaps)[0] * 2), min_gap)

                gap_list.append(gap)

            self.editGapThresh.setText(str(min(gap_list)))

    def get_gap_input(self):
        try:
            gap = float(self.editGapThresh.text())
        except ValueError:
            gap = None
        return gap

    def toggle_header_info(self):
        if self.shareTitleToggle.isChecked():
            self.clientEdit.setEnabled(True)
            self.gridEdit.setEnabled(True)
            self.loopEdit.setEnabled(True)
            self.fill_header_info()
        else:
            self.clientEdit.setEnabled(False)
            self.gridEdit.setEnabled(False)
            self.loopEdit.setEnabled(False)

    def fill_header_info(self):
        if len(self.list_of_files) != 0:

            f = self.list_of_files[0]
            self.editor.open_file(f)
            header = self.editor.active_file.get_header()

            if not self.clientEdit.text():
                self.clientEdit.setText(header['Client'])
            if not self.gridEdit.text():
                self.gridEdit.setText(header['Grid'])
            if not self.loopEdit.text():
                self.loopEdit.setText(header['Loop'])


if __name__ == "__main__":
    # Code to test MainWindow if running main_window.py
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
