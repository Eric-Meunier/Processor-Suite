import logging
import math
import os
import re
import statistics
import sys
import numpy as np
from PyQt5 import (QtCore, QtGui, uic)
from PyQt5.QtWidgets import (QWidget, QAbstractScrollArea, QTableWidgetItem, QAction, QMenu)

from src.gps.gps_editor import GPSParser, GPSEditor
from src.pem.pem_file_editor import PEMFileEditor
from src.ri.ri_file import RIFile

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
        self.ri_file = None
        self.gps_editor = GPSEditor()
        self.gps_parser = GPSParser()
        self.file_editor = PEMFileEditor()
        self.ri_editor = RIFile()
        self.last_stn_gps_shift_amt = 0
        self.last_loop_elev_shift_amt = 0
        self.last_stn_shift_amt = 0
        self.setupUi(self)
        self.initActions()
        self.initSignals()

    def initActions(self):
        self.loopGPSTable.installEventFilter(self)
        self.stationGPSTable.installEventFilter(self)
        self.collarGPSTable.installEventFilter(self)
        self.geometryTable.installEventFilter(self)
        self.dataTable.installEventFilter(self)
        self.riTable.installEventFilter(self)
        self.loopGPSTable.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.stationGPSTable.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.collarGPSTable.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.geometryTable.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.dataTable.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.riTable.setFocusPolicy(QtCore.Qt.StrongFocus)

        self.loopGPSTable.remove_row_action = QAction("&Remove", self)
        self.addAction(self.loopGPSTable.remove_row_action)
        self.loopGPSTable.remove_row_action.triggered.connect(
            lambda: self.remove_table_row_selection(self.loopGPSTable))
        self.loopGPSTable.remove_row_action.setShortcut('Del')
        self.loopGPSTable.remove_row_action.setEnabled(False)

        self.loopGPSTable.move_row_up_action = QAction("&Move Up", self)
        self.addAction(self.loopGPSTable.move_row_up_action)
        self.loopGPSTable.move_row_up_action.triggered.connect(lambda: self.move_table_row_up(self.loopGPSTable))

        self.loopGPSTable.move_row_down_action = QAction("&Move Down", self)
        self.addAction(self.loopGPSTable.move_row_down_action)
        self.loopGPSTable.move_row_down_action.triggered.connect(lambda: self.move_table_row_down(self.loopGPSTable))

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

        self.dataTable.remove_data_row_action = QAction("&Remove", self)
        self.addAction(self.dataTable.remove_data_row_action)
        self.dataTable.remove_data_row_action.triggered.connect(self.remove_data_row)
        self.dataTable.remove_data_row_action.setShortcut('Del')
        self.dataTable.remove_data_row_action.setEnabled(False)

        self.dataTable.reverse_polarity_action = QAction("&Reverse Polarity", self)
        self.dataTable.reverse_polarity_action.triggered.connect(self.reverse_polarity)

        self.riTable.remove_ri_file_action = QAction("&Remove RI File", self)
        self.addAction(self.riTable.remove_ri_file_action)
        self.riTable.remove_ri_file_action.triggered.connect(self.remove_ri_file)
        self.riTable.remove_ri_file_action.setStatusTip("Remove the RI file")
        self.riTable.remove_ri_file_action.setShortcut('Shift+Del')
        self.riTable.remove_ri_file_action.setEnabled(False)

        # self.stationGPSTable.cull_gps_action = QAction("&Cull GPS", self)
        # self.stationGPSTable.cull_gps_action.triggered.connect(self.cull_station_gps)

    def initSignals(self):
        # Buttons
        self.sortStationsButton.clicked.connect(self.sort_station_gps)
        self.sortLoopButton.clicked.connect(self.sort_loop_gps)
        self.cullStationGPSButton.clicked.connect(self.cull_station_gps)
        self.changeStationSuffixButton.clicked.connect(self.change_station_suffix)
        self.changeComponentButton.clicked.connect(self.change_component)
        self.moveUpButton.clicked.connect(self.move_table_row_up)
        self.moveDownButton.clicked.connect(self.move_table_row_down)

        self.flip_station_numbers_button.clicked.connect(self.reverse_station_gps_numbers)
        self.flip_station_signs_button.clicked.connect(self.flip_station_gps_polarity)

        self.reversePolarityButton.clicked.connect(self.reverse_polarity)

        # Table changes
        self.stationGPSTable.cellChanged.connect(self.check_station_duplicates)
        self.stationGPSTable.cellChanged.connect(self.check_station_order)
        self.stationGPSTable.itemSelectionChanged.connect(self.calc_distance)

        self.loopGPSTable.itemSelectionChanged.connect(self.toggle_loop_move_buttons)
        self.dataTable.cellChanged.connect(self.update_pem_from_table)

        # Spinboxes
        self.shiftStationGPSSpinbox.valueChanged.connect(self.shift_gps_station_numbers)
        self.shift_elevation_spinbox.valueChanged.connect(self.shift_loop_elev)
        self.shiftStationSpinbox.valueChanged.connect(self.shift_station_numbers)

        # self.format_station_gps_button.clicked.connect(self.format_station_gps_text)
        # self.format_loop_gps_button.clicked.connect(self.format_loop_gps_text)

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
                self.loopGPSTable.menu.addAction(self.loopGPSTable.move_row_up_action)
                self.loopGPSTable.menu.addAction(self.loopGPSTable.move_row_down_action)
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
        elif self.dataTable.underMouse():
            if self.dataTable.selectionModel().selectedIndexes():
                self.dataTable.menu = QMenu(self.dataTable)
                self.dataTable.menu.addAction(self.dataTable.reverse_polarity_action)
                self.dataTable.menu.addSeparator()
                self.dataTable.menu.addAction(self.dataTable.remove_data_row_action)
                self.dataTable.menu.popup(QtGui.QCursor.pos())
                self.dataTable.remove_data_row_action.setEnabled(True)
                # self.dataTable.remove_row_action.setEnabled(True)
            else:
                pass
        elif self.riTable.underMouse():
            if self.riTable.selectionModel().selectedIndexes():
                self.riTable.menu = QMenu(self.riTable)
                self.riTable.menu.addAction(self.riTable.remove_ri_file_action)
                self.riTable.menu.popup(QtGui.QCursor.pos())
                self.riTable.remove_ri_file_action.setEnabled(True)
        else:
            pass

    def eventFilter(self, source, event):
        if source is self.stationGPSTable:  # Makes the 'Del' shortcut work when the table is in focus
            if event.type() == QtCore.QEvent.FocusIn:
                self.stationGPSTable.remove_row_action.setEnabled(True)
            elif event.type() == QtCore.QEvent.FocusOut:
                self.stationGPSTable.remove_row_action.setEnabled(False)
            elif event.type() == QtCore.QEvent.KeyPress:
                if event.key() == QtCore.Qt.Key_Escape:
                    self.stationGPSTable.clearSelection()
                    return True
        elif source is self.loopGPSTable:
            if event.type() == QtCore.QEvent.FocusIn:
                self.loopGPSTable.remove_row_action.setEnabled(True)
            elif event.type() == QtCore.QEvent.FocusOut:
                self.loopGPSTable.remove_row_action.setEnabled(False)
            elif event.type() == QtCore.QEvent.KeyPress:
                if event.key() == QtCore.Qt.Key_Escape:
                    self.loopGPSTable.clearSelection()
                    return True
        elif source is self.collarGPSTable:
            if event.type() == QtCore.QEvent.FocusIn:
                self.collarGPSTable.remove_row_action.setEnabled(True)
            elif event.type() == QtCore.QEvent.FocusOut:
                self.collarGPSTable.remove_row_action.setEnabled(False)
            elif event.type() == QtCore.QEvent.KeyPress:
                if event.key() == QtCore.Qt.Key_Escape:
                    self.collarGPSTable.clearSelection()
                    return True
        elif source is self.geometryTable:
            if event.type() == QtCore.QEvent.FocusIn:
                self.geometryTable.remove_row_action.setEnabled(True)
            elif event.type() == QtCore.QEvent.FocusOut:
                self.geometryTable.remove_row_action.setEnabled(False)
            elif event.type() == QtCore.QEvent.KeyPress:
                if event.key() == QtCore.Qt.Key_Escape:
                    self.geometryTable.clearSelection()
                    return True
        elif source is self.dataTable:
            if event.type() == QtCore.QEvent.KeyPress:
                if event.key() == QtCore.Qt.Key_F and event.modifiers() == QtCore.Qt.ShiftModifier:
                    self.reverse_polarity()
                    return True
                elif event.key() == QtCore.Qt.Key_C and event.modifiers() == QtCore.Qt.ShiftModifier:
                    self.change_component()
                    return True
                elif event.key() == QtCore.Qt.Key_Escape:
                    self.dataTable.clearSelection()
                    return True
            elif event.type() == QtCore.QEvent.FocusIn:
                self.dataTable.remove_data_row_action.setEnabled(True)
            elif event.type() == QtCore.QEvent.FocusOut:
                self.dataTable.remove_data_row_action.setEnabled(False)
        elif source is self.riTable:
            if event.type() == QtCore.QEvent.Wheel:
                # TODO Make sideways scrolling work correctly. Won't scroll sideways without also going vertically
                if event.modifiers() == QtCore.Qt.ShiftModifier:
                    pos = self.riTable.horizontalScrollBar().value()
                    if event.angleDelta().y() < 0:  # Wheel moved down so scroll to the right
                        self.riTable.horizontalScrollBar().setValue(pos + 2)
                    else:
                        self.riTable.horizontalScrollBar().setValue(pos - 2)
                    return True
            elif event.type() == QtCore.QEvent.FocusIn:
                self.riTable.remove_ri_file_action.setEnabled(True)
            elif event.type() == QtCore.QEvent.FocusOut:
                self.riTable.remove_ri_file_action.setEnabled(False)
            elif event.type() == QtCore.QEvent.KeyPress:
                if event.key() == QtCore.Qt.Key_Escape:
                    self.riTable.clearSelection()
                    return True

        return super(QWidget, self).eventFilter(source, event)

    def open_file(self, pem_file, parent):
        self.pem_file = pem_file
        self.parent = parent
        self.initTables()
        self.fill_info()

        return self

    def open_ri_file(self, filepath):

        def make_ri_table():
            columns = self.ri_file.columns
            self.riTable.setColumnCount(len(columns))
            self.riTable.setHorizontalHeaderLabels(columns)

        def fill_ri_table():
            logging.info('Filling RI table')
            self.clear_table(self.riTable)

            for i, row in enumerate(self.ri_file.data):
                row_pos = self.riTable.rowCount()
                self.riTable.insertRow(row_pos)
                items = [QTableWidgetItem(row[key]) for key in self.ri_file.columns]

                for m, item in enumerate(items):
                    item.setTextAlignment(QtCore.Qt.AlignCenter)
                    self.riTable.setItem(row_pos, m, item)

        def add_header_from_pem():
            header_keys = ['Client', 'Grid', 'Loop', 'Timebase', 'Date']
            for key in header_keys:
                self.ri_file.header[key] = self.pem_file.header[key]
            self.ri_file.header['Current'] = self.pem_file.tags.get('Current')
            self.ri_file.survey = self.pem_file.survey_type

        self.ri_file = self.ri_editor.open(filepath)
        make_ri_table()
        fill_ri_table()
        add_header_from_pem()

    def initTables(self):
        if 'surface' in self.pem_file.survey_type.lower() or 'squid' in self.pem_file.survey_type.lower():
            self.tabs.removeTab(self.tabs.indexOf(self.Geometry_Tab))
            self.station_columns = ['Tag', 'Easting', 'Northing', 'Elevation', 'Units', 'Station']
            self.stationGPSTable.setColumnCount(len(self.station_columns))
            self.stationGPSTable.setHorizontalHeaderLabels(self.station_columns)
            self.stationGPSTable.setSizeAdjustPolicy(
                QAbstractScrollArea.AdjustToContents)
            self.stationGPSTable.resizeColumnsToContents()

        elif 'borehole' in self.pem_file.survey_type.lower():
            self.tabs.removeTab(self.tabs.indexOf(self.Station_GPS_Tab))
            self.geometry_columns = ['Tag', 'Azimuth', 'Dip', 'Seg. Length', 'Units', 'Depth']
            self.geometryTable.setColumnCount(len(self.geometry_columns))
            self.geometryTable.setHorizontalHeaderLabels(self.geometry_columns)
            self.geometryTable.setSizeAdjustPolicy(
                QAbstractScrollArea.AdjustToContents)
            self.geometryTable.resizeColumnsToContents()

            self.collar_columns = ['Tag', 'Easting', 'Northing', 'Elevation', 'Units']
            self.collarGPSTable.setColumnCount(len(self.collar_columns))
            self.collarGPSTable.setHorizontalHeaderLabels(self.collar_columns)
            self.collarGPSTable.setSizeAdjustPolicy(
                QAbstractScrollArea.AdjustToContents)
            self.collarGPSTable.resizeColumnsToContents()

            self.changeStationSuffixButton.setEnabled(False)

        self.loop_columns = ['Tag', 'Easting', 'Northing', 'Elevation', 'Units']
        self.loopGPSTable.setColumnCount(len(self.loop_columns))
        self.loopGPSTable.setHorizontalHeaderLabels(self.loop_columns)
        self.loopGPSTable.setSizeAdjustPolicy(
            QAbstractScrollArea.AdjustToContents)

        self.loopGPSTable.resizeColumnsToContents()

        self.data_columns = ['Station', 'Comp.', 'R. Index', 'Reading #', 'Stacks', 'ZTS']
        self.dataTable.blockSignals(True)
        self.dataTable.setColumnCount(len(self.data_columns))
        self.dataTable.setHorizontalHeaderLabels(self.data_columns)
        self.dataTable.setSizeAdjustPolicy(
            QAbstractScrollArea.AdjustToContents)

        self.dataTable.resizeColumnsToContents()
        self.dataTable.blockSignals(False)

    def fill_station_table(self, gps):  # GPS in list form
        """
        Fill the stationGPSTable with given gps data
        :param gps: station gps as a list
        """
        if gps:
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
            self.check_station_order()
            self.stationGPSTable.blockSignals(False)
        else:
            pass

    def fill_collar_gps_table(self, gps):  # GPS in list form
        """
        Fill the collarGPSTable with given collar gps data
        :param gps: collar gps as a list
        """

        if gps:
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
        else:
            pass

    def fill_geometry_table(self, segments):  # GPS in list form
        """
        Fill the geometryTable with given segments data
        :param segments: hole segments (as a list)
        """
        if segments:
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
        else:
            pass

    def fill_loop_table(self, gps):
        """
        Fill the loopGPSTable with given gps data
        :param gps: loop gps as a list
        """
        if gps:
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
        else:
            pass

    def fill_data_table(self, data):
        """
        Fill the dataTable with given PEMFile data
        :param data: PEMFile object data
        """
        if data:
            self.clear_table(self.dataTable)
            self.dataTable.blockSignals(True)
            column_keys = ['Station', 'Component', 'ReadingIndex', 'ReadingNumber', 'NumStacks', 'ZTS']
            for i, station in enumerate(data):
                row_pos = self.dataTable.rowCount()
                self.dataTable.insertRow(row_pos)
                items = [QTableWidgetItem(station[j]) for j in column_keys]

                for m, item in enumerate(items):
                    item.setTextAlignment(QtCore.Qt.AlignCenter)
                    self.dataTable.setItem(row_pos, m, item)

            self.color_data_table()
            self.dataTable.resizeColumnsToContents()
            self.dataTable.blockSignals(False)
        else:
            pass

    def update_data_table(self):
        """
        Updates the table based on the values in the PEM File object (self.pem_file)
        """
        self.dataTable.blockSignals(True)
        column_keys = ['Station', 'Component', 'ReadingIndex', 'ReadingNumber', 'NumStacks', 'ZTS']
        for station, row in zip(self.pem_file.data, range(self.dataTable.rowCount())):
            items = [QTableWidgetItem(station[j]) for j in column_keys]

            for m, item in enumerate(items):
                item.setTextAlignment(QtCore.Qt.AlignCenter)
                self.dataTable.setItem(row, m, item)

        self.color_data_table()
        self.dataTable.blockSignals(False)

    def update_pem_from_table(self, table_row, table_col):
        """
        Signal slot: Update the pem file using the values in the dataTable.
        :param table_row: event row
        :param table_col: event column
        """
        self.dataTable.blockSignals(True)
        column_keys = ['Station', 'Component', 'ReadingIndex', 'ReadingNumber', 'NumStacks', 'ZTS']
        data = self.pem_file.data
        table_value = self.dataTable.item(table_row, table_col).text()
        data[table_row][column_keys[table_col]] = table_value

        self.color_data_table()
        self.dataTable.blockSignals(False)

    def color_data_table(self):

        def color_rows_by_component():
            """
            Color the rows in dataTable by component
            """

            def color_row(row, color):
                for col in range(self.dataTable.columnCount()):
                    item = self.dataTable.item(row, col)
                    item.setBackground(color)

            z_color = QtGui.QColor('cyan')
            z_color.setAlpha(50)
            x_color = QtGui.QColor('magenta')
            x_color.setAlpha(50)
            y_color = QtGui.QColor('yellow')
            y_color.setAlpha(50)
            white_color = QtGui.QColor('white')
            for row in range(self.dataTable.rowCount()):
                item = self.dataTable.item(row, self.data_columns.index('Comp.'))
                if item:
                    component = item.text()
                    if component == 'Z':
                        color_row(row, z_color)
                    elif component == 'X':
                        color_row(row, x_color)
                    elif component == 'Y':
                        color_row(row, y_color)
                    else:
                        color_row(row, white_color)

        def color_wrong_suffix():
            """
            Color the dataTable rows where the suffix is different from the mode
            """

            def most_common_suffix():
                suffixes = []
                for reading in self.pem_file.data:
                    station = reading['Station'].upper()
                    suffix = re.findall('[NSEW]', station)
                    if suffix:
                        suffixes.append(suffix[0])
                return statistics.mode(suffixes)

            if 'surface' in self.pem_file.survey_type.lower() or 'squid' in self.pem_file.survey_type.lower():
                correct_suffix = most_common_suffix()

                for row in range(self.dataTable.rowCount()):
                    item = self.dataTable.item(row, self.data_columns.index('Station'))
                    if item:
                        station_suffix = re.findall('[NSEW]', item.text().upper())
                        if not station_suffix or station_suffix[0] != correct_suffix:
                            item.setForeground(QtGui.QColor('red'))
                        else:
                            item.setForeground(QtGui.QColor('black'))

        def bolden_repeat_stations():
            """
            Makes the station number cell bold if it ends with '1'
            """
            duplicates = 0
            boldFont = QtGui.QFont()
            boldFont.setBold(True)
            normalFont = QtGui.QFont()
            normalFont.setBold(False)
            for row in range(self.dataTable.rowCount()):
                item = self.dataTable.item(row, self.data_columns.index('Station'))
                if item:
                    station_num = re.findall('\d+', item.text())[0]
                    if station_num[-1] == '1' or station_num[-1] == '6':
                        duplicates += 1
                        item.setFont(boldFont)
                        item.setForeground(QtGui.QColor('red'))
                    else:
                        item.setFont(normalFont)
                        item.setForeground(QtGui.QColor('black'))
            return duplicates

        color_rows_by_component()
        color_wrong_suffix()
        duplicates_num = bolden_repeat_stations()
        self.lcdDuplicates.display(duplicates_num)

    def fill_info(self):
        logging.info('PEMInfoWidget: fill_info')

        def init_info_tab():
            survey_type = self.pem_file.survey_type
            operator = self.pem_file.tags.get('Operator')
            loop_size = ' x '.join(self.pem_file.tags.get('LoopSize').split(' ')[0:2])

            if 'surface' in survey_type.lower():
                linetype = 'Line'
            else:
                linetype = 'Hole'

            # Set text first to remove anything that was there bofore
            self.info_text_edit.setText('<html><b>Operator: </b</html> {operator}'.format(operator=operator))
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

        def init_station_text():
            # Fill station GPS
            pem_station_gps = self.pem_file.get_line_coords()
            self.add_station_gps(pem_station_gps)

        def init_geometry_text():
            # Fill hole geometry collar GPS segments
            pem_geometry_text = self.pem_file.get_line_coords()
            self.add_geometry(pem_geometry_text)

        def init_loop_text():
            # Fill loop GPS
            pem_loop_gps = self.pem_file.get_loop_coords()
            self.add_loop_gps(pem_loop_gps)

        header = self.pem_file.header

        init_info_tab()
        if 'surface' in self.pem_file.survey_type.lower():
            init_station_text()
        else:
            # init_collar_gps_text()
            init_geometry_text()
        init_loop_text()
        self.fill_data_table(self.pem_file.data)

    def add_loop_gps(self, file):
        # gps = self.gps_parser.parse_loop_gps(file)
        # if gps:
        if self.parent.autoSortLoopsCheckbox.isChecked():
            self.fill_loop_table(self.gps_editor.get_sorted_loop_gps(file))
        else:
            self.fill_loop_table(self.gps_editor.get_loop_gps(file))

    def add_station_gps(self, file):
        # gps = self.gps_parser.parse_station_gps(file)
        # if gps:
        if self.parent.autoSortStationsCheckbox.isChecked():
            self.fill_station_table(self.gps_editor.get_sorted_station_gps(file))
        else:
            self.fill_station_table(self.gps_editor.get_station_gps(file))

    def add_geometry(self, file):
        gps = self.gps_parser.parse_collar_gps(file)
        segments = self.gps_parser.parse_segments(file)
        if gps:
            self.fill_collar_gps_table(self.gps_editor.get_collar_gps(file))
        if segments:
            self.fill_geometry_table(self.gps_editor.get_geometry(file))

    def clear_table(self, table):
        table.blockSignals(True)
        while table.rowCount() > 0:
            table.removeRow(0)
        table.blockSignals(False)

    def check_station_duplicates(self):
        self.stationGPSTable.blockSignals(True)
        stations_column = self.station_columns.index('Station')
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

    def check_station_order(self):
        self.stationGPSTable.blockSignals(True)
        stations = [int(row[-1]) for row in self.get_station_gps()]
        order = 'asc' if stations[-1] > stations[0] else 'desc'
        sorted_stations = sorted(stations) if order == 'asc' else sorted(stations, reverse=True)

        blue_color = QtGui.QColor('blue')
        blue_color.setAlpha(50)
        red_color = QtGui.QColor('red')
        red_color.setAlpha(50)
        for row in range(self.stationGPSTable.rowCount()):
            if self.stationGPSTable.item(row, self.station_columns.index('Station')) and stations[row] > \
                    sorted_stations[row]:
                self.stationGPSTable.item(row, self.station_columns.index('Station')).setBackground(blue_color)
            elif self.stationGPSTable.item(row, self.station_columns.index('Station')) and stations[row] < \
                    sorted_stations[row]:
                self.stationGPSTable.item(row, self.station_columns.index('Station')).setBackground(red_color)
            else:
                self.stationGPSTable.item(row, self.station_columns.index('Station')).setBackground(
                    QtGui.QColor('white'))
        self.stationGPSTable.blockSignals(False)

    def remove_table_row_selection(self, table):
        # Table (QWidgetTable) is either the loop, station, collar GPS, or geometry tables. Not dataTable.

        def add_tags():  # tag is either 'P' or 'L'
            if table == self.loopGPSTable:
                tag = 'L'
            else:
                tag = 'P'
            for row in range(table.rowCount()):
                offset = 1 if table == self.geometryTable else 0
                tag_item = QTableWidgetItem("<" + tag + '{num:02d}'.format(num=row + offset) + ">")
                tag_item.setTextAlignment(QtCore.Qt.AlignCenter)
                table.setItem(row, 0, tag_item)

        selected_rows = self.get_selected_rows(table)
        for row in reversed(selected_rows):
            table.removeRow(row)

        if table == self.stationGPSTable:
            self.check_station_duplicates()
            add_tags()
        elif table == self.loopGPSTable:
            add_tags()

    def remove_data_row(self):
        selected_rows = self.get_selected_rows(self.dataTable)

        for row in reversed(selected_rows):
            del self.pem_file.data[row]
            self.dataTable.removeRow(row)

        self.dataTable.blockSignals(True)
        self.color_data_table()
        self.dataTable.blockSignals(False)

    def remove_ri_file(self):
        while self.riTable.rowCount() > 0:
            self.riTable.removeRow(0)
        self.ri_file = None

    def cull_station_gps(self):
        gps = self.get_station_gps()
        if gps:
            culled_gps = []
            gps_stations = list(map(lambda x: x[-1], gps))
            em_stations = list(map(lambda x: str(x), self.pem_file.get_converted_unique_stations()))
            for i, station in enumerate(gps_stations):
                if station in em_stations:
                    culled_gps.append(gps[i])
            self.fill_station_table(culled_gps)
        else:
            pass

    def sort_station_gps(self):
        station_gps = self.get_station_gps()
        if station_gps:
            self.fill_station_table(self.gps_editor.get_sorted_station_gps(station_gps))
        else:
            pass

    def sort_loop_gps(self):
        loop = self.get_loop_gps()
        if loop:
            self.fill_loop_table(self.gps_editor.get_sorted_loop_gps(loop))
        else:
            pass

    def move_table_row_up(self):
        rows = self.get_selected_rows(self.loopGPSTable)
        loop_gps = self.get_loop_gps()

        for row in rows:
            removed_row = loop_gps.pop(row)
            loop_gps.insert(row-1, removed_row)

        self.fill_loop_table(loop_gps)
        self.loopGPSTable.setSelectionMode(QtGui.QAbstractItemView.MultiSelection)
        [self.loopGPSTable.selectRow(row-1) for row in rows]
        self.loopGPSTable.setSelectionMode(QtGui.QAbstractItemView.ExtendedSelection)

    def move_table_row_down(self):
        rows = self.get_selected_rows(self.loopGPSTable)
        loop_gps = self.get_loop_gps()

        for row in rows:
            removed_row = loop_gps.pop(row)
            loop_gps.insert(row + 1, removed_row)

        self.fill_loop_table(loop_gps)
        self.loopGPSTable.setSelectionMode(QtGui.QAbstractItemView.MultiSelection)
        [self.loopGPSTable.selectRow(row + 1) for row in rows]
        self.loopGPSTable.setSelectionMode(QtGui.QAbstractItemView.ExtendedSelection)

    def toggle_loop_move_buttons(self):
        if self.loopGPSTable.selectionModel().selectedRows():
            self.moveUpButton.setEnabled(True)
            self.moveDownButton.setEnabled(True)
        else:
            self.moveUpButton.setEnabled(False)
            self.moveDownButton.setEnabled(False)

    def shift_gps_station_numbers(self):
        def apply_station_shift(row):
            station_column = self.station_columns.index('Station')
            station = int(self.stationGPSTable.item(row, station_column).text()) if self.stationGPSTable.item(row,
                                                                                                              station_column) else None
            if station is not None or station == 0:
                new_station_item = QTableWidgetItem(str(station + (shift_amount - self.last_stn_gps_shift_amt)))
                new_station_item.setTextAlignment(QtCore.Qt.AlignCenter)
                self.stationGPSTable.setItem(row, station_column, new_station_item)
            else:
                pass

        selected_rows = self.get_selected_rows(self.stationGPSTable)

        shift_amount = self.shiftStationGPSSpinbox.value()

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
        self.last_stn_gps_shift_amt = shift_amount

    def shift_station_easting(self):
        def apply_station_shift(row):
            easting_column = 1
            station = int(self.stationGPSTable.item(row, easting_column).text()) if self.stationGPSTable.item(row,
                                                                                                              easting_column) else None
            if station is not None or station == 0:
                new_station_item = QTableWidgetItem(str(station + (shift_amount - self.last_stn_gps_shift_amt)))
                new_station_item.setTextAlignment(QtCore.Qt.AlignCenter)
                self.stationGPSTable.setItem(row, easting_column, new_station_item)
            else:
                pass

        selected_rows = self.get_selected_rows(self.stationGPSTable)

        shift_amount = self.shiftStationGPSSpinbox.value()

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
        self.last_stn_gps_shift_amt = shift_amount

    def shift_station_northing(self):
        def apply_station_shift(row):
            station_column = 5
            station = int(self.stationGPSTable.item(row, station_column).text()) if self.stationGPSTable.item(row,
                                                                                                              station_column) else None
            if station is not None or station == 0:
                new_station_item = QTableWidgetItem(str(station + (shift_amount - self.last_stn_gps_shift_amt)))
                new_station_item.setTextAlignment(QtCore.Qt.AlignCenter)
                self.stationGPSTable.setItem(row, station_column, new_station_item)
            else:
                pass

        selected_rows = self.get_selected_rows(self.stationGPSTable)

        shift_amount = self.shiftStationGPSSpinbox.value()

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
        self.last_stn_gps_shift_amt = shift_amount

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

        selected_rows = [model.row() for model in self.loopGPSTable.selectionModel().selectedRows()]

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

    def flip_station_gps_polarity(self):
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

        selected_rows = self.get_selected_rows(self.stationGPSTable)

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

    def reverse_station_gps_numbers(self):
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

    # def format_station_gps_text(self):
    #     current_gps = self.station_gps_parser.parse(self.get_station_gps())
    #     if current_gps:
    #         if self.parent.autoSortStationsCheckbox.isChecked():
    #             self.fill_station_table(current_gps.get_sorted_gps())
    #         else:
    #             self.fill_station_table(current_gps.get_gps())
    #     else:
    #         pass

    # def format_loop_gps_text(self):
    #     loop = self.get_loop_gps()
    #     if loop:
    #         if self.parent.autoSortLoopsCheckbox.isChecked():
    #             self.fill_loop_table(self.gps_editor.get_sorted_gps(loop))
    #         else:
    #             self.fill_loop_table(self.gps_editor.get_gps(loop))
    #     else:
    #         pass

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

        selected_rows = self.get_selected_rows(self.stationGPSTable)
        if len(selected_rows) > 1:
            min_row, max_row = min(selected_rows), max(selected_rows)
            first_point = get_row_gps(min_row)
            second_point = get_row_gps(max_row)
            if first_point and second_point:
                distance = math.sqrt((first_point[0] - second_point[0]) ** 2 + (first_point[1] - second_point[1]) ** 2)
                self.lcdDistance.display(f'{distance:.1f}')
            else:
                self.lcdDistance.display(0)
        else:
            self.lcdDistance.display(0)

    # def shift_station_numbers(self):
    #     def apply_station_shift(row):
    #         station_column = self.data_columns.index('Station')
    #         if self.dataTable.item(row, station_column):
    #             station = self.dataTable.item(row, station_column).text()
    #         else:
    #             station = None
    #
    #         if station is not None or station == 0:
    #             station_num = int(re.findall('\d+', station)[0])
    #             new_station_num = station_num + (shift_amount - self.last_stn_shift_amt)
    #             new_station = re.sub(str(station_num), str(new_station_num), station)
    #             new_station_item = QTableWidgetItem(str(new_station))
    #             new_station_item.setTextAlignment(QtCore.Qt.AlignCenter)
    #             self.pem_file.data[row]['Station'] = new_station
    #             self.dataTable.setItem(row, station_column, new_station_item)
    #         else:
    #             pass
    #
    #     selected_rows = [model.row() for model in self.dataTable.selectionModel().selectedRows()]
    #     shift_amount = self.shiftStationSpinbox.value()
    #
    #     if selected_rows:
    #         for row in selected_rows:
    #             apply_station_shift(row)
    #
    #     else:
    #         if self.dataTable.rowCount() > 0:
    #             for row in range(self.dataTable.rowCount()):
    #                 apply_station_shift(row)
    #     self.last_stn_shift_amt = shift_amount

    def shift_station_numbers(self):
        # Shift the station number
        selected_rows = self.get_selected_rows(self.dataTable)
        if not selected_rows:
            selected_rows = range(self.dataTable.rowCount())
        shift_amount = self.shiftStationSpinbox.value()
        self.pem_file = self.file_editor.shift_stations(self.pem_file, shift_amount - self.last_stn_shift_amt,
                                                        rows=selected_rows)
        self.update_data_table()
        self.dataTable.resizeColumnsToContents()
        self.last_stn_shift_amt = shift_amount

    def reverse_polarity(self, selected_rows=None, component=None):
        # Reverse the polarity of selected readings
        if not component:
            selected_rows = self.get_selected_rows(self.dataTable)
        if component or selected_rows:
            self.pem_file = self.file_editor.reverse_polarity(self.pem_file, rows=selected_rows, component=component)
            self.update_data_table()
            self.dataTable.resizeColumnsToContents()
            self.window().statusBar().showMessage('Polarity flipped.', 2000)

    def change_station_suffix(self):
        print('Suffix changed')
        pass

    def change_component(self):
        components = ['Z', 'X', 'Y']
        rows = self.get_selected_rows(self.dataTable)
        for row in rows:
            table_comp = self.dataTable.item(row, self.data_columns.index('Comp.')).text()
            index = components.index(table_comp)
            if index or index == 0:
                new_comp = components[(index+1) % 3]
                new_comp_item = QTableWidgetItem(new_comp)
                new_comp_item.setTextAlignment(QtCore.Qt.AlignCenter)
                self.dataTable.setItem(row, self.data_columns.index('Comp.'), new_comp_item)

    def get_selected_rows(self, table):
        return [model.row() for model in table.selectionModel().selectedRows()]

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
                pass
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
