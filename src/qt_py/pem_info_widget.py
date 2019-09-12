import os
import re
import sys
import logging
import copy
import numpy as np
import math
from scipy import spatial
from itertools import chain
from src.gps.station_gps import StationGPSParser
from src.gps.loop_gps import LoopGPSParser
from src.gps.hole_geometry import GeometryParser
from PyQt5.QtWidgets import (QWidget, QMainWindow, QApplication, QGridLayout, QDesktopWidget, QMessageBox, QTabWidget,
                             QFileDialog, QAbstractScrollArea, QTableWidgetItem, QMenuBar, QAction, QMenu, QDockWidget,
                             QHeaderView, QListWidget, QTextBrowser, QPlainTextEdit, QStackedWidget, QTextEdit,
                             QShortcut)
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
    # loop_change_signal = QtCore.pyqtSignal()

    def __init__(self):
        super().__init__()
        self.parent = None
        self.pem_file = None
        self.station_gps = None
        self.loop_gps = None
        self.last_stn_shift_amt = 0
        self.last_loop_elev_shift_amt = 0
        self.station_gps_parser = StationGPSParser()
        self.loop_gps_parser = LoopGPSParser()
        self.geometry_parser = GeometryParser()
        self.setupUi(self)
        self.initActions()
        self.initSignals()

    def initActions(self):
        self.loopGPSTable.installEventFilter(self)
        self.stationGPSTable.installEventFilter(self)
        self.collarGPSTable.installEventFilter(self)
        self.geometryTable.installEventFilter(self)
        self.loopGPSTable.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.stationGPSTable.setFocusPolicy(QtCore.Qt.StrongFocus)

        self.loopGPSTable.remove_row_action = QAction("&Remove", self)
        self.addAction(self.loopGPSTable.remove_row_action)
        self.loopGPSTable.remove_row_action.triggered.connect(
            lambda: self.remove_table_row_selection(self.loopGPSTable))
        self.loopGPSTable.remove_row_action.setShortcut('Del')
        self.loopGPSTable.remove_row_action.setEnabled(False)

        self.stationGPSTable.remove_row_action = QAction("&Remove", self)
        self.addAction(self.stationGPSTable.remove_row_action)
        self.stationGPSTable.remove_row_action.triggered.connect(
            lambda: self.remove_table_row_selection(self.stationGPSTable))
        self.stationGPSTable.remove_row_action.setShortcut('Del')
        self.stationGPSTable.remove_row_action.setEnabled(False)

        self.collarGPSTable.remove_row_action = QAction("&Remove", self)
        self.addAction(self.collarGPSTable.remove_row_action)
        self.collarGPSTable.remove_row_action.triggered.connect(
            lambda: self.remove_table_row_selection(self.collarGPSTable))
        self.collarGPSTable.remove_row_action.setShortcut('Del')
        self.collarGPSTable.remove_row_action.setEnabled(False)

        self.geometryTable.remove_row_action = QAction("&Remove", self)
        self.addAction(self.geometryTable.remove_row_action)
        self.geometryTable.remove_row_action.triggered.connect(
            lambda: self.remove_table_row_selection(self.geometryTable))
        self.geometryTable.remove_row_action.setShortcut('Del')
        self.geometryTable.remove_row_action.setEnabled(False)

        # self.stationGPSTable.cull_gps_action = QAction("&Cull GPS", self)
        # self.stationGPSTable.cull_gps_action.triggered.connect(self.cull_station_gps)

    def initSignals(self):
        self.sort_station_gps_button.toggled.connect(self.sort_station_gps)
        self.sort_loop_button.toggled.connect(self.sort_loop_gps)
        self.cull_station_gps_button.clicked.connect(self.cull_station_gps)

        self.flip_station_numbers_button.clicked.connect(self.reverse_station_numbers)
        self.flip_station_signs_button.clicked.connect(self.flip_station_polarity)

        self.shift_stations_spinbox.valueChanged.connect(self.shift_station_numbers)
        self.shift_elevation_spinbox.valueChanged.connect(self.shift_loop_elev)

        self.stationGPSTable.cellChanged.connect(self.check_station_duplicates)
        self.stationGPSTable.itemSelectionChanged.connect(self.calc_distance)

        self.format_station_gps_button.clicked.connect(self.format_station_gps_text)
        self.format_loop_gps_button.clicked.connect(self.format_loop_gps_text)

    def contextMenuEvent(self, event):
        if self.stationGPSTable.underMouse():
            if self.stationGPSTable.selectionModel().selectedIndexes():
                self.stationGPSTable.menu = QMenu(self.stationGPSTable)
                self.stationGPSTable.menu.addAction(self.stationGPSTable.remove_row_action)
                self.stationGPSTable.menu.popup(QtGui.QCursor.pos())
                self.stationGPSTable.remove_row_action.setEnabled(True)
            else:
                pass
        elif self.loopGPSTable.underMouse():
            if self.loopGPSTable.selectionModel().selectedIndexes():
                self.loopGPSTable.menu = QMenu(self.loopGPSTable)
                self.loopGPSTable.menu.addAction(self.loopGPSTable.remove_row_action)
                self.loopGPSTable.menu.popup(QtGui.QCursor.pos())
                self.loopGPSTable.remove_row_action.setEnabled(True)
            else:
                pass
        elif self.collarGPSTable.underMouse():
            if self.collarGPSTable.selectionModel().selectedIndexes():
                self.collarGPSTable.menu = QMenu(self.collarGPSTable)
                self.collarGPSTable.menu.addAction(self.collarGPSTable.remove_row_action)
                self.collarGPSTable.menu.popup(QtGui.QCursor.pos())
                self.collarGPSTable.remove_row_action.setEnabled(True)
            else:
                pass
        elif self.geometryTable.underMouse():
            if self.geometryTable.selectionModel().selectedIndexes():
                self.geometryTable.menu = QMenu(self.geometryTable)
                self.geometryTable.menu.addAction(self.geometryTable.remove_row_action)
                self.geometryTable.menu.popup(QtGui.QCursor.pos())
                self.geometryTable.remove_row_action.setEnabled(True)
            else:
                pass
        else:
            pass

    def eventFilter(self, source, event):
        if source is self.stationGPSTable:  # Makes the 'Del' shortcut work when the table is in focus
            if event.type() == QtCore.QEvent.FocusIn:
                self.stationGPSTable.remove_row_action.setEnabled(True)
            elif event.type() == QtCore.QEvent.FocusOut:
                self.stationGPSTable.remove_row_action.setEnabled(False)
        elif source is self.loopGPSTable:
            if event.type() == QtCore.QEvent.FocusIn:
                self.loopGPSTable.remove_row_action.setEnabled(True)
            elif event.type() == QtCore.QEvent.FocusOut:
                self.loopGPSTable.remove_row_action.setEnabled(False)
        elif source is self.collarGPSTable:
            if event.type() == QtCore.QEvent.FocusIn:
                self.collarGPSTable.remove_row_action.setEnabled(True)
            elif event.type() == QtCore.QEvent.FocusOut:
                self.collarGPSTable.remove_row_action.setEnabled(False)
        elif source is self.geometryTable:
            if event.type() == QtCore.QEvent.FocusIn:
                self.geometryTable.remove_row_action.setEnabled(True)
            elif event.type() == QtCore.QEvent.FocusOut:
                self.geometryTable.remove_row_action.setEnabled(False)
        return super(QWidget, self).eventFilter(source, event)

    def open_file(self, pem_file, parent):
        self.pem_file = pem_file
        self.parent = parent
        self.initTables()
        self.fill_info()

        return self

    def initTables(self):
        if 'surface' in self.pem_file.survey_type.lower():
            self.tabs.removeTab(self.tabs.indexOf(self.Geometry_Tab))
            self.station_columns = ['Tags', 'Easting', 'Northing', 'Elevation', 'Units', 'Station']
            self.stationGPSTable.setColumnCount(len(self.station_columns))
            self.stationGPSTable.setHorizontalHeaderLabels(self.station_columns)
            self.stationGPSTable.setSizeAdjustPolicy(
                QAbstractScrollArea.AdjustToContents)
            self.stationGPSTable.resizeColumnsToContents()

        elif 'borehole' in self.pem_file.survey_type.lower():
            self.tabs.removeTab(self.tabs.indexOf(self.Station_GPS_Tab))
            self.geometry_columns = ['Tags', 'Azimuth', 'Dip', 'Seg. Length', 'Units', 'Depth']
            self.geometryTable.setColumnCount(len(self.geometry_columns))
            self.geometryTable.setHorizontalHeaderLabels(self.geometry_columns)
            self.geometryTable.setSizeAdjustPolicy(
                QAbstractScrollArea.AdjustToContents)
            self.geometryTable.resizeColumnsToContents()

            self.collar_columns = ['Tags', 'Easting', 'Northing', 'Elevation', 'Units']
            self.collarGPSTable.setColumnCount(len(self.collar_columns))
            self.collarGPSTable.setHorizontalHeaderLabels(self.collar_columns)
            self.collarGPSTable.setSizeAdjustPolicy(
                QAbstractScrollArea.AdjustToContents)
            self.collarGPSTable.resizeColumnsToContents()

        self.loop_columns = ['Tags', 'Easting', 'Northing', 'Elevation', 'Units']
        self.loopGPSTable.setColumnCount(len(self.loop_columns))
        self.loopGPSTable.setHorizontalHeaderLabels(self.loop_columns)
        self.loopGPSTable.setSizeAdjustPolicy(
            QAbstractScrollArea.AdjustToContents)

        self.loopGPSTable.resizeColumnsToContents()

        self.data_columns = ['Station', 'Comp.', 'R. Index', 'Reading #', 'Stacks', 'ZTS']
        self.dataTable.setColumnCount(len(self.data_columns))
        self.dataTable.setHorizontalHeaderLabels(self.data_columns)
        self.dataTable.setSizeAdjustPolicy(
            QAbstractScrollArea.AdjustToContents)

        self.dataTable.resizeColumnsToContents()

    def fill_station_table(self, gps):  # GPS in list form
        self.clear_table(self.stationGPSTable)
        self.stationGPSTable.blockSignals(True)
        logging.info('Filling station table')

        for i, row in enumerate(gps):
            row_pos = self.stationGPSTable.rowCount()
            self.stationGPSTable.insertRow(row_pos)
            if re.match('<P.*>', row[0]):
                row.pop(0)
            tag_item = QTableWidgetItem("<P" + '{num:02d}'.format(num=i) + ">")
            items = [QTableWidgetItem(row[j]) for j in range(len(row))]
            items.insert(0, tag_item)

            for m, item in enumerate(items):
                item.setTextAlignment(QtCore.Qt.AlignCenter)
                self.stationGPSTable.setItem(row_pos, m, item)

        self.stationGPSTable.resizeColumnsToContents()
        self.check_station_duplicates()
        self.stationGPSTable.blockSignals(False)

    def fill_collar_gps_table(self, gps):  # GPS in list form
        self.clear_table(self.collarGPSTable)
        logging.info('Filling collar GPS')

        self.collarGPSTable.insertRow(0)
        if re.match('<P.*>', gps[0]):
            gps.pop(0)
        tag_item = QTableWidgetItem("<P00>")
        items = [QTableWidgetItem(gps[j]) for j in range(len(gps))]
        items.insert(0, tag_item)

        for m, item in enumerate(items):
            item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.collarGPSTable.setItem(0, m, item)

        self.collarGPSTable.resizeColumnsToContents()

    def fill_geometry_table(self, segments):  # GPS in list form
        self.clear_table(self.geometryTable)
        logging.info('Filling geometry table')

        for i, row in enumerate(segments):
            row_pos = self.geometryTable.rowCount()
            self.geometryTable.insertRow(row_pos)
            if re.match('<P.*>', row[0]):
                row.pop(0)
            tag_item = QTableWidgetItem("<P" + '{num:02d}'.format(num=i + 1) + ">")
            items = [QTableWidgetItem(row[j]) for j in range(len(row))]
            items.insert(0, tag_item)

            for m, item in enumerate(items):
                item.setTextAlignment(QtCore.Qt.AlignCenter)
                self.geometryTable.setItem(row_pos, m, item)

        self.geometryTable.resizeColumnsToContents()

    def fill_loop_table(self, gps):
        self.clear_table(self.loopGPSTable)
        for i, row in enumerate(gps):
            row_pos = self.loopGPSTable.rowCount()
            self.loopGPSTable.insertRow(row_pos)
            if re.match('<L.*>', row[0]):
                row.pop(0)
            tag_item = QTableWidgetItem("<L" + '{num:02d}'.format(num=i) + ">")
            items = [QTableWidgetItem(row[j]) for j in range(len(row))]
            items.insert(0, tag_item)

            for m, item in enumerate(items):
                item.setTextAlignment(QtCore.Qt.AlignCenter)
                self.loopGPSTable.setItem(row_pos, m, item)

        self.loopGPSTable.resizeColumnsToContents()

    def fill_data_table(self, data):
        self.dataTable.blockSignals(True)
        self.clear_table(self.dataTable)
        column_keys = ['Station', 'Component', 'ReadingIndex', 'ReadingNumber', 'NumStacks', 'ZTS']
        for i, station in enumerate(data):
            row_pos = self.dataTable.rowCount()
            self.dataTable.insertRow(row_pos)
            items = [QTableWidgetItem(station[j]) for j in column_keys]

            for m, item in enumerate(items):
                item.setTextAlignment(QtCore.Qt.AlignCenter)
                self.dataTable.setItem(row_pos, m, item)

        self.dataTable.resizeColumnsToContents()
        self.dataTable.blockSignals(False)

    def fill_info(self):
        logging.info('PEMInfoWidget: fill_info')

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
                unwanted_keys = ['Convension', 'IsNormalized', 'PrimeFieldValue', 'ChannelTimes']
                if k not in unwanted_keys:
                    if k == 'LineHole':
                        k = linetype
                    self.info_text_edit.append('<html><b>{k}:</b</html>\t{v}'.format(k=k, v=v))

            self.info_text_edit.append(
                '<html><b>Notes: </b</html> {notes}'.format(notes='\n'.join(self.pem_file.notes)))

        def fill_station_text():
            # Fill station GPS
            self.station_gps = self.station_gps_parser.parse(self.pem_file.get_line_coords())
            if self.station_gps:
                if self.sort_station_gps_button.isChecked():
                    self.fill_station_table(self.station_gps.get_sorted_gps())
                else:
                    self.fill_station_table(self.station_gps.get_gps())

        def fill_collar_gps_text():
            # Fill hole collar GPS
            self.collar_gps = self.geometry_parser.parse_collar_gps(self.pem_file.get_line_coords())
            if self.collar_gps:
                self.fill_collar_gps_table(self.collar_gps)

        def fill_geometry_text():
            # Fill hole geometry segments
            self.geometry_text = self.geometry_parser.parse_segments(self.pem_file.get_line_coords())
            if self.geometry_text:
                self.fill_geometry_table(self.geometry_text)

        def fill_loop_text():
            # Fill loop GPS
            self.loop_gps = self.loop_gps_parser.parse(self.pem_file.get_loop_coords())
            if self.loop_gps:
                if self.sort_loop_button.isChecked():
                    self.fill_loop_table(self.loop_gps.get_sorted_gps())
                else:
                    self.fill_loop_table(self.loop_gps.get_gps())

        header = self.pem_file.header

        fill_info_tab()
        if 'surface' in self.pem_file.survey_type.lower():
            fill_station_text()
        else:
            fill_collar_gps_text()
            fill_geometry_text()
        fill_loop_text()
        self.fill_data_table(self.pem_file.data)

    def clear_table(self, table):
        table.blockSignals(True)
        while table.rowCount() > 0:
            table.removeRow(0)
        table.blockSignals(False)

    def check_station_duplicates(self):
        self.stationGPSTable.blockSignals(True)
        stations_column = 5
        stations = []
        for row in range(self.stationGPSTable.rowCount()):
            if self.stationGPSTable.item(row, stations_column):
                station = self.stationGPSTable.item(row, stations_column).text()
                if station in stations:
                    other_station_index = stations.index(station)
                    self.stationGPSTable.item(row, stations_column).setForeground(QtGui.QColor('red'))
                    self.stationGPSTable.item(other_station_index, stations_column).setForeground(QtGui.QColor('red'))
                else:
                    self.stationGPSTable.item(row, stations_column).setForeground(QtGui.QColor('black'))
                stations.append(station)
        self.stationGPSTable.blockSignals(False)

    def remove_table_row_selection(self, table):
        # Table (QWidgetTable) is either the loop, station, collar GPS, or geometry tables

        def add_tags():  # tag is either 'P' or 'L'
            if table == self.loopGPSTable:
                tag = 'L'
            else:
                tag = 'P'
            for row in range(table.rowCount()):
                offset = 1 if table == self.geometryTable else 0
                tag_item = QTableWidgetItem("<"+tag + '{num:02d}'.format(num=row+offset) + ">")
                tag_item.setTextAlignment(QtCore.Qt.AlignCenter)
                table.setItem(row, 0, tag_item)

        selected_rows = [model.row() for model in table.selectionModel().selectedRows()]
        for row in reversed(selected_rows):
            table.removeRow(row)

        if table == self.stationGPSTable:
            self.check_station_duplicates()
        add_tags()

    def cull_station_gps(self):
        if self.station_gps:
            culled_gps = []
            gps = self.get_station_gps()
            gps_stations = list(map(lambda x: x[-1], gps))
            em_stations = list(map(lambda x: str(x), self.pem_file.get_converted_unique_stations()))
            for i, station in enumerate(gps_stations):
                if station in em_stations:
                    culled_gps.append(gps[i])
            self.fill_station_table(culled_gps)
        else:
            pass

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
        else:
            pass

    def shift_station_numbers(self):

        def apply_station_shift(row):
            station_column = 5
            station = int(self.stationGPSTable.item(row, station_column).text()) if self.stationGPSTable.item(row,
                                                                                                              station_column) else None
            if station is not None or station == 0:
                new_station_item = QTableWidgetItem(str(station + (shift_amount - self.last_stn_shift_amt)))
                new_station_item.setTextAlignment(QtCore.Qt.AlignCenter)
                self.stationGPSTable.setItem(row, station_column, new_station_item)
            else:
                pass

        selected_rows = []
        for i in self.stationGPSTable.selectedIndexes():
            if i.row() not in selected_rows:
                selected_rows.append(i.row())

        shift_amount = self.shift_stations_spinbox.value()

        if selected_rows:
            for row in selected_rows:
                try:
                    apply_station_shift(row)
                except Exception as e:
                    print(str(e))
                    pass
        else:
            for row in range(self.stationGPSTable.rowCount()):
                try:
                    apply_station_shift(row)
                except Exception as e:
                    print(str(e))
                    pass
        self.last_stn_shift_amt = shift_amount

    def shift_station_easting(self):

        def apply_station_shift(row):
            easting_column = 1
            station = int(self.stationGPSTable.item(row, easting_column).text()) if self.stationGPSTable.item(row,
                                                                                                              easting_column) else None
            if station is not None or station == 0:
                new_station_item = QTableWidgetItem(str(station + (shift_amount - self.last_stn_shift_amt)))
                new_station_item.setTextAlignment(QtCore.Qt.AlignCenter)
                self.stationGPSTable.setItem(row, easting_column, new_station_item)
            else:
                pass

        selected_rows = []
        for i in self.stationGPSTable.selectedIndexes():
            if i.row() not in selected_rows:
                selected_rows.append(i.row())

        shift_amount = self.shift_stations_spinbox.value()

        if selected_rows:
            for row in selected_rows:
                try:
                    apply_station_shift(row)
                except Exception as e:
                    print(str(e))
                    pass
        else:
            for row in range(self.stationGPSTable.rowCount()):
                try:
                    apply_station_shift(row)
                except Exception as e:
                    print(str(e))
                    pass
        self.last_stn_shift_amt = shift_amount

    def shift_station_northing(self):

        def apply_station_shift(row):
            station_column = 5
            station = int(self.stationGPSTable.item(row, station_column).text()) if self.stationGPSTable.item(row,
                                                                                                              station_column) else None
            if station is not None or station == 0:
                new_station_item = QTableWidgetItem(str(station + (shift_amount - self.last_stn_shift_amt)))
                new_station_item.setTextAlignment(QtCore.Qt.AlignCenter)
                self.stationGPSTable.setItem(row, station_column, new_station_item)
            else:
                pass

        selected_rows = []
        for i in self.stationGPSTable.selectedIndexes():
            if i.row() not in selected_rows:
                selected_rows.append(i.row())

        shift_amount = self.shift_stations_spinbox.value()

        if selected_rows:
            for row in selected_rows:
                try:
                    apply_station_shift(row)
                except Exception as e:
                    print(str(e))
                    pass
        else:
            for row in range(self.stationGPSTable.rowCount()):
                try:
                    apply_station_shift(row)
                except Exception as e:
                    print(str(e))
                    pass
        self.last_stn_shift_amt = shift_amount

    def shift_loop_elev(self):

        def apply_elevation_shift(row):
            elevation_column = 3
            elevation = float(self.loopGPSTable.item(row, elevation_column).text()) if self.loopGPSTable.item(row,
                                                                                                              elevation_column) else None
            if elevation is not None or elevation == 0:
                new_elevation = elevation + (shift_amount - self.last_loop_elev_shift_amt)
                new_elevation_item = QTableWidgetItem('{:.2f}'.format(new_elevation))
                new_elevation_item.setTextAlignment(QtCore.Qt.AlignCenter)
                self.loopGPSTable.setItem(row, elevation_column, new_elevation_item)
            else:
                pass

        # TODO Add shifting based on table selection, also deleting rows and such
        selected_rows = []
        for i in self.loopGPSTable.selectedIndexes():
            if i.row() not in selected_rows:
                selected_rows.append(i.row())

        shift_amount = self.shift_elevation_spinbox.value()

        if selected_rows:
            for row in selected_rows:
                try:
                    apply_elevation_shift(row)
                except Exception as e:
                    print(str(e))
                    pass
        else:
            for row in range(self.loopGPSTable.rowCount()):
                try:
                    apply_elevation_shift(row)
                except Exception as e:
                    print(str(e))
                    pass
        self.last_loop_elev_shift_amt = shift_amount

    def flip_station_polarity(self):
        # Multiplies the station number by -1

        def flip_stn_num(row):
            station_column = 5
            station = int(self.stationGPSTable.item(row, station_column).text()) if self.stationGPSTable.item(row,
                                                                                                              station_column) else None
            if station is not None or station == 0:
                new_station_item = QTableWidgetItem(str(station * -1))
                new_station_item.setTextAlignment(QtCore.Qt.AlignCenter)
                self.stationGPSTable.setItem(row, station_column, new_station_item)
            else:
                pass

        selected_rows = []
        for i in self.stationGPSTable.selectedIndexes():
            if i.row() not in selected_rows:
                selected_rows.append(i.row())

        if selected_rows:
            for row in selected_rows:
                flip_stn_num(row)
        else:
            for row in range(self.stationGPSTable.rowCount()):
                try:
                    flip_stn_num(row)
                except Exception as e:
                    print(str(e))
                    pass

    def reverse_station_numbers(self):
        # Flips the station numbers head-over-heals
        gps = self.get_station_gps()
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
        try:
            current_gps = self.station_gps_parser.parse(self.get_station_gps())
        except ValueError:
            current_gps = None
        if current_gps:
            if self.sort_station_gps_button.isChecked():
                self.fill_station_table(current_gps.get_sorted_gps())
            else:
                self.fill_station_table(current_gps.get_gps())
        else:
            pass

    def format_loop_gps_text(self):
        try:
            current_gps = self.loop_gps_parser.parse(self.get_loop_gps())
        except ValueError:
            current_gps = None
        if current_gps:
            if self.sort_station_gps_button.isChecked():
                self.fill_loop_table(current_gps.get_sorted_gps())
            else:
                self.fill_loop_table(current_gps.get_gps())
        else:
            pass

    def calc_distance(self):

        def get_row_gps(row):
            east_col = self.station_columns.index('Easting')
            north_col = self.station_columns.index('Northing')
            try:
                easting = float(self.stationGPSTable.item(row, east_col).text())
            except ValueError:
                easting = None
            try:
                northing = float(self.stationGPSTable.item(row, north_col).text())
            except ValueError:
                northing = None
            if easting and northing:
                return float(easting), float(northing)
            else:
                return None

        selected_rows = [model.row() for model in self.stationGPSTable.selectionModel().selectedRows()]
        if len(selected_rows) > 1:
            min_row, max_row = min(selected_rows), max(selected_rows)
            first_point = get_row_gps(min_row)
            second_point = get_row_gps(max_row)
            if first_point and second_point:
                distance = math.sqrt((first_point[0]-second_point[0])**2+(first_point[1]-second_point[1])**2)
                self.lcdDistance.display(f'{distance:.1f}')
            else:
                self.lcdDistance.display(0)
        else:
            self.lcdDistance.display(0)

    def get_loop_gps(self):
        table_gps = []
        for row in range(self.loopGPSTable.rowCount()):
            row_list = []
            for i, column in enumerate(self.loop_columns):
                if self.loopGPSTable.item(row, i):  # Check if an item exists before trying to read it
                    row_list.append(self.loopGPSTable.item(row, i).text())
                else:
                    row_list.append('')
            table_gps.append(row_list)
        return table_gps

    def get_station_gps(self):
        table_gps = []
        for row in range(self.stationGPSTable.rowCount()):
            row_list = []
            for i, column in enumerate(self.station_columns):
                if self.stationGPSTable.item(row, i):  # Check if an item exists before trying to read it
                    row_list.append(self.stationGPSTable.item(row, i).text())
                else:
                    row_list.append('')
            table_gps.append(row_list)
        return table_gps

    def get_collar_gps(self):
        row_list = []
        for i, column in enumerate(self.collar_columns):
            if self.collarGPSTable.item(0, i):  # Check if an item exists before trying to read it
                row_list.append(self.collarGPSTable.item(0, i).text())
            else:
                row_list.append('')
        return row_list

    def get_geometry_segments(self):
        table_gps = []
        for row in range(self.geometryTable.rowCount()):
            row_list = []
            for i, column in enumerate(self.geometry_columns):
                if self.geometryTable.item(row, i):  # Check if an item exists before trying to read it
                    row_list.append(self.geometryTable.item(row, i).text())
                else:
                    row_list.append('')
            table_gps.append(row_list)
        return table_gps
