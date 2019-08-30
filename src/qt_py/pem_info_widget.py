import os
import re
import sys
import logging
import copy
from itertools import chain
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

logging.info('PEMFileInfoWidget')


class PEMFileInfoWidget(QWidget, Ui_PEMInfoWidget):
    loop_change_signal = QtCore.pyqtSignal()

    def __init__(self):
        super().__init__()
        self.parent = None
        self.pem_file = None
        self.station_gps = None
        self.loop_gps = None
        self.last_stn_shift_amt = 0
        self.last_loop_elev_shift_amt = 0
        # self.selection_row_start = None
        # self.selection_row_end = None
        self.station_gps_parser = StationGPSParser()
        self.loop_gps_parser = LoopGPSParser()
        self.setupUi(self)
        self.initActions()
        self.initTables()

    def initActions(self):
        self.sort_station_gps_button.toggled.connect(self.sort_station_gps)
        self.sort_loop_button.toggled.connect(self.sort_loop_gps)
        self.flip_station_numbers_button.clicked.connect(self.reverse_station_numbers)
        self.flip_station_signs_button.clicked.connect(self.flip_station_polarity)
        # self.station_gps_text.selectionChanged.connect(self.current_selection)

        self.shift_stations_spinbox.valueChanged.connect(self.shift_station_numbers)
        self.shift_elevation_spinbox.valueChanged.connect(self.shift_loop_elev)

        self.loopGPSTable.cellChanged.connect(self.loop_change_signal.emit)

        self.format_station_gps_button.clicked.connect(self.format_station_gps_text)
        self.format_loop_gps_button.clicked.connect(self.format_loop_gps_text)

    def open_file(self, pem_file, parent):
        self.pem_file = pem_file
        self.parent = parent

        self.fill_info()

        if parent.share_loop_gps_checkbox.isChecked():
            self.sort_loop_button.setEnabled(False)
        else:
            self.sort_loop_button.setEnabled(True)

        return self

    def initTables(self):
        self.station_columns = ['Tags', 'Easting', 'Northing', 'Elevation', 'Units', 'Station']
        self.stationGPSTable.setColumnCount(len(self.station_columns))
        self.stationGPSTable.setHorizontalHeaderLabels(self.station_columns)
        self.stationGPSTable.setSizeAdjustPolicy(
            QAbstractScrollArea.AdjustToContents)

        self.loop_columns = ['Tags', 'Easting', 'Northing', 'Elevation', 'Units']
        self.loopGPSTable.setColumnCount(len(self.loop_columns))
        self.loopGPSTable.setHorizontalHeaderLabels(self.loop_columns)
        self.loopGPSTable.setSizeAdjustPolicy(
            QAbstractScrollArea.AdjustToContents)

    def fill_station_table(self, gps, tags=False):  # GPS in list form
        self.clear_table(self.stationGPSTable)
        logging.info('Filling station table')
        for i, row in enumerate(gps):
            row_pos = self.stationGPSTable.rowCount()
            self.stationGPSTable.insertRow(row_pos)
            if re.match('\<P.*\>', row[0]):
                row.pop(0)
            tag_item = QTableWidgetItem("<P" + '{num:02d}'.format(num=i) + ">")
            items = [QTableWidgetItem(row[j]) for j in range(len(row))]
            items.insert(0, tag_item)

            for m, item in enumerate(items):
                item.setTextAlignment(QtCore.Qt.AlignCenter)
                self.stationGPSTable.setItem(row_pos, m, item)

        self.stationGPSTable.resizeColumnsToContents()

    def fill_loop_table(self, gps):
        self.clear_table(self.loopGPSTable)
        for i, row in enumerate(gps):
            row_pos = self.loopGPSTable.rowCount()
            self.loopGPSTable.insertRow(row_pos)
            if re.match('\<L.*\>', row[0]):
                row.pop(0)
            tag_item = QTableWidgetItem("<L" + '{num:02d}'.format(num=i) + ">")
            items = [QTableWidgetItem(row[j]) for j in range(len(row))]
            items.insert(0, tag_item)

            for m, item in enumerate(items):
                item.setTextAlignment(QtCore.Qt.AlignCenter)
                self.loopGPSTable.setItem(row_pos, m, item)

        self.loopGPSTable.resizeColumnsToContents()

    def clear_table(self, table):
        while table.rowCount() > 0:
            table.removeRow(0)

    def fill_info(self):

        def fill_info_tab():
            survey_type = self.pem_file.survey_type
            operator = self.pem_file.tags.get('Operator')
            loop_size = ' x '.join(self.pem_file.tags.get('LoopSize').split(' ')[0:2])

            if 'surface' in survey_type.lower():
                linetype = 'Line'
            else:
                linetype = 'Hole'

            self.info_text_edit.append('<html><b>Operator: </b</html> {operator}'.format(operator=operator))
            self.info_text_edit.append('<html><b>Loop Size: </b</html> {loop_size}'.format(loop_size=loop_size))
            # Fill the info tab
            for k, v in header.items():
                unwanted_keys = ['Convension', 'IsNormalized', 'PrimeFieldValue','ChannelTimes']
                if k not in unwanted_keys:
                    if k == 'LineHole':
                        k = linetype
                    self.info_text_edit.append('<html><b>{k}:</b</html>\t{v}'.format(k=k, v=v))

            self.info_text_edit.append('<html><b>Notes: </b</html> {notes}'.format(notes='\n'.join(self.pem_file.notes)))

        def fill_station_text():
            # Fill station GPS
            try:
                self.station_gps = self.station_gps_parser.parse_text(self.pem_file.get_line_coords())
            except ValueError:
                self.station_gps = None

            if self.station_gps:
                if self.sort_station_gps_button.isChecked():
                    self.fill_station_table(self.station_gps.get_sorted_gps())
                    # self.fill_loop_table(self.station_gps.get_sorted_gps()))
                else:
                    self.fill_station_table(self.station_gps.get_gps())
            else:
                # self.station_gps_text.setPlainText('')
                pass

        def fill_loop_text():
            # Fill loop GPS
            try:
                self.loop_gps = self.loop_gps_parser.parse_text(self.pem_file.get_loop_coords())
            except ValueError:
                self.loop_gps = None

            if self.parent.share_loop_gps_checkbox.isChecked() and len(self.parent.pem_files) > 0:
                first_file_loop = self.parent.stackedWidget.widget(0).get_loop_gps_text()
                self.fill_loop_table(first_file_loop)
            else:
                if self.loop_gps:
                    if self.sort_loop_button.isChecked():
                        self.fill_loop_table(self.loop_gps.get_sorted_gps())
                    else:
                        self.fill_loop_table(self.loop_gps.get_gps())
                else:
                    # self.loop_gps_text.setPlainText('')
                    pass

        header = self.pem_file.header
        fill_info_tab()
        fill_station_text()
        fill_loop_text()

    def sort_station_gps(self):
        if self.station_gps:
            if self.sort_station_gps_button.isChecked():
                self.fill_station_table(self.station_gps.get_sorted_gps())
            else:
                self.fill_station_table(self.station_gps.get_gps())
        else:
            pass

    def sort_loop_gps(self):
        if self.loop_gps:
            if self.sort_loop_button.isChecked():
                self.fill_loop_table(self.loop_gps.get_sorted_gps())
            else:
                self.fill_loop_table(self.loop_gps.get_gps())

    def shift_station_numbers(self):

        def apply_station_shift(row):
            # row_list = row.split(' ')
            station = row.pop(-1)
            new_station = int(station) + (shift_amount - self.last_stn_shift_amt)
            row.append(str(new_station))
            return row

        # TODO Add shifting based on table selection, also deleting rows and such
        # selection = self.station_gps_text.textCursor().selectedText()
        cursor = self.station_gps_text.textCursor()
        start, end = cursor.selectionStart(), cursor.selectionEnd()
        selection = cursor.selectedText()

        gps = selection.split('\n') if selection else self.get_station_gps_text().split('\n')

        if gps[0] is not '':
            shift_amount = self.shift_stations_spinbox.value()
            try:
                shifted_gps = list(map(apply_station_shift, gps))
            except Exception as e:
                print(str(e))
                pass
            else:
                if selection:
                    self.station_gps_text.insertPlainText('\n'.join(shifted_gps))

                    cursor.setPosition(start)
                    cursor.setPosition(end, QtGui.QTextCursor.KeepAnchor)
                    self.station_gps_text.setTextCursor(cursor)
                else:
                    self.fill_loop_table(shifted_gps)
                self.last_stn_shift_amt = shift_amount
        else:
            pass

    def shift_loop_elev(self):

        def apply_elev_shift(row):
            elev = row.pop(-2)
            new_elev = float(elev) + (shift_amount - self.last_loop_elev_shift_amt)
            row.insert(3, str(new_elev))
            return row

        gps = self.get_loop_gps_text()
        if gps:
            shift_amount = self.shift_elevation_spinbox.value()
            shifted_gps = list(map(apply_elev_shift, gps))
            self.fill_loop_table(shifted_gps)
            self.last_loop_elev_shift_amt = shift_amount
        else:
            pass

    def flip_station_polarity(self):
        # Multiplies the station number by -1

        def flip_stn_num(row):
            station = row.pop(-1)
            new_station = int(station) * -1
            row.append(str(new_station))
            return row

        gps = self.get_station_gps_text()
        if gps:
            flipped_gps = list(map(flip_stn_num, copy.copy(gps)))
            self.fill_station_table(flipped_gps)
        else:
            pass

    def reverse_station_numbers(self):
        # Flips the station numbers head-over-heals
        gps = self.get_station_gps_text()
        if gps:
            reversed_stations = list(reversed(list(map(lambda x: int(x[-1]), gps))))
            reversed_gps = []
            for i, station in enumerate(reversed_stations):
                row = gps[i][:-1]
                row.append(str(station))
                reversed_gps.append(row)
            self.fill_station_table(reversed_gps)
        else:
            pass

    def format_station_gps_text(self):
        current_gps = self.station_gps_parser.parse_text(self.get_station_gps_text())
        if current_gps:
            if self.sort_station_gps_button.isChecked():
                self.fill_station_table(current_gps.get_sorted_gps())
            else:
                self.fill_station_table(current_gps.get_gps())
        else:
            pass

    def format_loop_gps_text(self):
        current_gps = self.loop_gps_parser.parse_text(self.get_loop_gps_text())
        if current_gps:
            if self.sort_station_gps_button.isChecked():
                self.fill_loop_table(current_gps.get_sorted_gps())
            else:
                self.fill_loop_table(current_gps.get_gps())
        else:
            pass

    def get_loop_gps_text(self):
        table_gps = []
        for row in range(self.loopGPSTable.rowCount()):
            row_list = []
            for i, column in enumerate(self.loop_columns):
                row_list.append(self.loopGPSTable.item(row, i).text())
            table_gps.append(row_list)
        return table_gps

    def get_loop_gps_obj(self):
        return self.loop_gps

    def get_station_gps_text(self):
        table_gps = []
        for row in range(self.stationGPSTable.rowCount()):
            row_list = []
            for i, column in enumerate(self.station_columns):
                row_list.append(self.stationGPSTable.item(row, i).text())
            table_gps.append(row_list)
        return table_gps

    def get_station_gps_obj(self):
        return self.station_gps

