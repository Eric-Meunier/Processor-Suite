import os
import sys
import logging
from src.gps.station_gps import StationGPSParser
from src.gps.loop_gps import LoopGPSParser
from PyQt5.QtWidgets import (QWidget, QMainWindow, QApplication, QGridLayout, QDesktopWidget, QMessageBox, QTabWidget,
                             QFileDialog, QAbstractScrollArea, QTableWidgetItem, QMenuBar, QAction, QMenu, QDockWidget,
                             QHeaderView, QListWidget, QTextBrowser, QPlainTextEdit, QStackedWidget, QTextEdit)
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
    def __init__(self, pem_file, parent=None):
        super().__init__()
        self.parent = parent
        self.pem_file = pem_file
        self.station_gps = None
        self.loop_gps = None
        self.station_gps_parser = StationGPSParser()
        self.loop_gps_parser = LoopGPSParser()
        self.setupUi(self)
        self.initActions()
        self.fill_info()

        if parent.share_loop_gps_checkbox.isChecked():
            self.sort_loop_button.setEnabled(False)
        else:
            self.sort_loop_button.setEnabled(True)

    def initActions(self):
        self.sort_stations_button.toggled.connect(self.sort_station_gps)
        self.sort_loop_button.toggled.connect(self.sort_loop_gps)

        self.format_station_gps_button.clicked.connect(self.format_station_gps_text)
        self.format_loop_gps_button.clicked.connect(self.format_loop_gps_text)

    def fill_info(self):
        header = self.pem_file.header
        survey_type = self.pem_file.survey_type
        if 'surface' in survey_type.lower():
            linetype = 'Line'
        else:
            linetype = 'Hole'

        # Fill the info tab
        for k, v in header.items():
            unwanted_keys = ['Convension', 'IsNormalized', 'PrimeFieldValue','ChannelTimes']
            if k not in unwanted_keys:
                if k == 'LineHole':
                    k = linetype
                self.info_text_edit.append('<html><b>{k}:</b</html>\t{v}'.format(k=k, v=v))

        self.info_text_edit.append('<html><b>Notes: </b</html> {notes}'.format(notes='\n'.join(self.pem_file.notes)))

        # Fill station GPS
        try:
            self.station_gps = self.station_gps_parser.parse_text(self.pem_file.get_line_coords())
        except ValueError:
            self.station_gps = None

        if self.station_gps:
            if self.sort_stations_button.isChecked():
                self.station_gps_text.setPlainText('\n'.join(self.station_gps.get_sorted_gps()))
            else:
                self.station_gps_text.setPlainText('\n'.join(self.station_gps.get_gps()))
        else:
            self.station_gps_text.setPlainText('')

        # Fill loop GPS
        try:
            self.loop_gps = self.loop_gps_parser.parse_text(self.pem_file.get_loop_coords())
        except ValueError:
            self.loop_gps = None

        if self.parent.share_loop_gps_checkbox.isChecked() and len(self.parent.pem_files) > 0:
                first_file_loop = self.parent.stackedWidget.widget(0).tabs.findChild(QTextEdit, 'loop_gps_text').toPlainText()
                self.loop_gps_text.setPlainText(first_file_loop)
        else:
            if self.loop_gps:
                if self.parent.sort_loop_button.isChecked():
                    self.loop_gps_text.setPlainText('\n'.join(self.loop_gps.get_sorted_gps()))
                else:
                    if self.sort_loop_button.isChecked():
                        self.loop_gps_text.setPlainText('\n'.join(self.loop_gps.get_sorted_gps()))
                    else:
                        self.loop_gps_text.setPlainText('\n'.join(self.loop_gps.get_gps()))
            else:
                self.loop_gps_text.setPlainText('')

    def sort_station_gps(self):
        if self.station_gps:
            if self.sort_stations_button.isChecked():
                self.station_gps_text.setPlainText('\n'.join(self.station_gps.get_sorted_gps()))
            else:
                self.station_gps_text.setPlainText('\n'.join(self.station_gps.get_gps()))
        else:
            pass

    def sort_loop_gps(self):
        if self.loop_gps:
            if self.sort_loop_button.isChecked():
                self.loop_gps_text.setPlainText('\n'.join(self.loop_gps.get_sorted_gps()))
            else:
                self.loop_gps_text.setPlainText('\n'.join(self.loop_gps.get_gps()))
        else:
            pass

    def format_station_gps_text(self):
        if self.station_gps:
            current_text = self.tabs.findChild(QTextEdit, 'station_gps_text').toPlainText()
            self.station_gps = self.station_gps_parser.parse_text(current_text)

            if self.sort_stations_button.isChecked():
                self.tabs.findChild(QTextEdit, 'station_gps_text').setPlainText('\n'.join(self.station_gps.get_sorted_gps()))
            else:
                self.tabs.findChild(QTextEdit, 'station_gps_text').setPlainText('\n'.join(self.station_gps.get_gps()))
        else:
            pass

    def format_loop_gps_text(self):
        if self.loop_gps:
            current_text = self.tabs.findChild(QTextEdit, 'loop_gps_text').toPlainText()
            self.loop_gps = self.loop_gps_parser.parse_text(current_text)

            if self.sort_loop_button.isChecked():
                self.tabs.findChild(QTextEdit, 'loop_gps_text').setPlainText('\n'.join(self.loop_gps.get_sorted_gps()))
            else:
                self.tabs.findChild(QTextEdit, 'loop_gps_text').setPlainText('\n'.join(self.loop_gps.get_gps()))
        else:
            pass
