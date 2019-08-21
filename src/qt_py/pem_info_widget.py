import os
import sys
import logging
from PyQt5.QtWidgets import (QWidget, QMainWindow, QApplication, QGridLayout, QDesktopWidget, QMessageBox, QTabWidget,
                             QFileDialog, QAbstractScrollArea, QTableWidgetItem, QMenuBar, QAction, QMenu, QDockWidget,
                             QHeaderView, QListWidget, QTextBrowser, QPlainTextEdit, QStackedWidget)
from PyQt5 import (QtCore, QtGui, uic)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s', datefmt='%d-%b-%y %H:%M:%S')

if getattr(sys, 'frozen', False):
    # If the application is run as a bundle, the pyInstaller bootloader
    # extends the sys module by a flag frozen=True and sets the app
    # path into variable _MEIPASS'.
    application_path = sys._MEIPASS
    pemInfoWidgetCreatorFile = 'qt_ui\\pem_info_widget.ui'
    icons_path = 'icons'
else:
    application_path = os.path.dirname(os.path.abspath(__file__))
    pemInfoWidgetCreatorFile = os.path.join(os.path.dirname(application_path), 'qt_ui\\pem_info_widget.ui')
    icons_path = os.path.join(os.path.dirname(application_path), "qt_ui\\icons")

# Load Qt ui file into a class
Ui_PEMInfoWidget, QtBaseClass = uic.loadUiType(pemInfoWidgetCreatorFile)


class PEMFileInfoWidget(QWidget, Ui_PEMInfoWidget):
    def __init__(self, pem_file):
        super().__init__()
        self.pem_file = pem_file
        self.setupUi(self)
        self.fill_info()
        # self.tabs = QTabWidget()
        # self.station_gps_text = QPlainTextEdit()
        # self.station_gps_text.setObjectName('Station GPS')
        # self.station_gps_text.setAcceptDrops(False)
        # self.loop_gps_text = QPlainTextEdit()
        # self.loop_gps_text.setObjectName('Loop GPS')
        # self.loop_gps_text.setAcceptDrops(False)
        # self.initUi()

    # def initUi(self):
    #     self.layout = QGridLayout()
    #     self.setLayout(self.layout)
    #     self.layout.addWidget(self.tabs)
    #
    #     # self.tabs.addTab('', 'PEM Info')
    #     self.tabs.addTab(self.station_gps_text, 'Station GPS')
    #     self.tabs.addTab(self.loop_gps_text, 'Loop GPS')

    def fill_info(self):
        header = self.pem_file.header
        self.station_gps = self.pem_file.get_line_coords()
        self.station_gps_text.setPlainText('\n'.join(self.station_gps))
        self.loop_gps = self.pem_file.get_loop_coords()
        self.loop_gps_text.setPlainText('\n'.join(self.loop_gps))

