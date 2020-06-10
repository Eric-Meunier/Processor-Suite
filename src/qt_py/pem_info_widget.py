import math
import os
import re
import sys
import natsort
import pandas as pd
from copy import deepcopy
from PyQt5 import (QtCore, QtGui, uic)
from PyQt5.QtWidgets import (QWidget, QTableWidgetItem, QAction, QMenu, QInputDialog, QMessageBox,
                             QFileDialog, QErrorMessage, QHeaderView)
from collections import OrderedDict
from src.gps.gps_editor import TransmitterLoop, SurveyLine, BoreholeCollar, BoreholeSegments, BoreholeGeometry
from src.pem.pem_file_editor import PEMFileEditor
from src._legacy.ri.ri_file import RIFile

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


def convert_station(station):
    """
    Converts a single station name into a number, negative if the stations was S or W
    :return: Integer station number
    """
    if re.match(r"\d+(S|W)", station):
        station = (-int(re.sub(r"\D", "", station)))
    else:
        station = (int(re.sub(r"\D", "", station)))
    return station


class PEMFileInfoWidget(QWidget, Ui_PEMInfoWidget):
    refresh_tables_signal = QtCore.pyqtSignal()  # Send a signal to PEMEditor to refresh its main table.

    def __init__(self):
        super().__init__()
        self.parent = None
        self.pem_file = None
        self.ri_file = None
        self.file_editor = PEMFileEditor()
        self.ri_editor = RIFile()
        self.dialog = QFileDialog()
        self.error = QErrorMessage()
        self.message = QMessageBox()
        self.message.setIcon(QMessageBox.Information)

        self.last_stn_gps_shift_amt = 0
        self.last_loop_elev_shift_amt = 0
        self.last_stn_shift_amt = 0
        self.num_repeat_stations = 0
        self.suffix_warnings = 0

        self.station_columns = ['Tag', 'Easting', 'Northing', 'Elevation', 'Units', 'Station']
        self.loop_columns = ['Tag', 'Easting', 'Northing', 'Elevation', 'Units']
        self.dataTable_columns = ['Station', 'Component', 'Reading index', 'Reading number', 'Number of stacks', 'ZTS']

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

    def initSignals(self):
        # Buttons
        # self.sortStationsButton.clicked.connect(self.sort_station_gps)
        # self.sortLoopButton.clicked.connect(self.sort_loop_gps)
        self.cullStationGPSButton.clicked.connect(self.cull_station_gps)
        self.changeStationSuffixButton.clicked.connect(self.change_station_suffix)
        self.changeComponentButton.clicked.connect(self.change_component)
        # self.moveUpButton.clicked.connect(self.move_table_row_up)
        # self.moveDownButton.clicked.connect(self.move_table_row_down)

        self.flip_station_numbers_button.clicked.connect(self.reverse_station_gps_numbers)
        self.flip_station_signs_button.clicked.connect(self.flip_station_gps_polarity)
        self.stations_from_data_btn.clicked.connect(self.stations_from_data)
        self.reversePolarityButton.clicked.connect(self.reverse_polarity)
        self.rename_repeat_stations_btn.clicked.connect(self.rename_repeat_stations)

        self.export_station_gps_btn.clicked.connect(lambda: self.export_gps('station'))
        self.export_loop_gps_btn.clicked.connect(lambda: self.export_gps('loop'))

        # Radio buttons
        self.station_sort_rbtn.clicked.connect(self.fill_data_table)
        self.component_sort_rbtn.clicked.connect(self.fill_data_table)
        self.reading_num_sort_rbtn.clicked.connect(self.fill_data_table)

        # Table changes
        self.stationGPSTable.cellChanged.connect(self.check_station_duplicates)
        self.stationGPSTable.cellChanged.connect(self.check_station_order)
        self.stationGPSTable.cellChanged.connect(self.check_missing_gps)
        self.stationGPSTable.itemSelectionChanged.connect(self.calc_distance)
        self.stationGPSTable.itemSelectionChanged.connect(lambda: self.reset_spinbox(self.shiftStationGPSSpinbox))

        # self.loopGPSTable.itemSelectionChanged.connect(self.toggle_loop_move_buttons)
        self.loopGPSTable.itemSelectionChanged.connect(lambda: self.reset_spinbox(self.shift_elevation_spinbox))

        self.dataTable.itemSelectionChanged.connect(lambda: self.reset_spinbox(self.shiftStationSpinbox))
        self.dataTable.cellChanged.connect(self.update_pem_from_table)

        # Spinboxes
        self.shiftStationGPSSpinbox.valueChanged.connect(self.shift_gps_station_numbers)
        self.shift_elevation_spinbox.valueChanged.connect(self.shift_loop_elev)
        self.shiftStationSpinbox.valueChanged.connect(self.shift_station_numbers)

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
        """
        Action of opening a PEM file.
        :param pem_file: PEMFile object.
        :param parent: parent widget (PEMEditor)
        :return: PEMFileInfoWidget object
        """
        print(f'PEMFileInfoWidget - Opening PEM File {os.path.basename(pem_file.filepath)}')
        self.pem_file = pem_file
        self.parent = parent
        self.initTables()
        if self.pem_file.is_borehole():
            self.fill_gps_table(self.pem_file.geometry.get_collar(), self.collarGPSTable)
            self.fill_gps_table(self.pem_file.geometry.get_segments(), self.geometryTable)
        else:
            self.fill_gps_table(self.pem_file.line.get_line(sorted=self.parent.autoSortStationsCheckbox.isChecked()),
                                self.stationGPSTable)
        self.fill_info_tab()
        self.fill_gps_table(self.pem_file.loop.get_loop(sorted=self.parent.autoSortLoopsCheckbox.isChecked()),
                            self.loopGPSTable)
        self.fill_data_table()
        return self

    def open_ri_file(self, filepath):
        """
        Action of opening an RI file. Adds the contents of the RI file to the RIFileTable.
        :param filepath: Filepath of the RI file.
        :return: None
        """
        def make_ri_table():
            columns = self.ri_file.columns
            self.riTable.setColumnCount(len(columns))
            self.riTable.setHorizontalHeaderLabels(columns)

        def fill_ri_table():
            self.clear_table(self.riTable)

            for i, row in enumerate(self.ri_file.data):
                row_pos = self.riTable.rowCount()
                self.riTable.insertRow(row_pos)
                items = [QTableWidgetItem(row[key]) for key in self.ri_file.columns]

                for m, item in enumerate(items):
                    item.setTextAlignment(QtCore.Qt.AlignCenter)
                    self.riTable.setItem(row_pos, m, item)

        def add_header_from_pem():
            # header_keys = ['Client', 'Grid', 'Loop', 'Timebase', 'Date']
            # for key in header_keys:
            #     self.ri_file.header[key] = self.pem_file.header[key]
            self.ri_file.header['Client'] = self.pem_file.client
            self.ri_file.header['Grid'] = self.pem_file.grid
            self.ri_file.header['Loop'] = self.pem_file.loop_name
            self.ri_file.header['Timebase'] = self.pem_file.timebase
            self.ri_file.header['Date'] = self.pem_file.date
            self.ri_file.header['Current'] = self.pem_file.current
            self.ri_file.survey = self.pem_file.get_survey_type()

        self.ri_file = self.ri_editor.open(filepath)
        make_ri_table()
        fill_ri_table()
        add_header_from_pem()

    def initTables(self):
        """
        Adds the columns and formats each table.
        :return: None
        """
        if not self.pem_file.is_borehole():
            self.tabs.removeTab(self.tabs.indexOf(self.Geometry_Tab))
            self.stationGPSTable.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            # self.stationGPSTable.setSizeAdjustPolicy(
            #     QAbstractScrollArea.AdjustToContents)
            # self.stationGPSTable.resizeColumnsToContents()

        elif self.pem_file.is_borehole():
            self.tabs.removeTab(self.tabs.indexOf(self.Station_GPS_Tab))
            self.geometryTable.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            self.collarGPSTable.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            # self.geometryTable.setSizeAdjustPolicy(
            #     QAbstractScrollArea.AdjustToContents)
            # self.geometryTable.resizeColumnsToContents()

            # self.collarGPSTable.setSizeAdjustPolicy(
            #     QAbstractScrollArea.AdjustToContents)
            # tag_item = QTableWidgetItem('<P00>')
            # units_item = QTableWidgetItem('0')
            # tag_item.setTextAlignment(QtCore.Qt.AlignCenter)
            # units_item.setTextAlignment(QtCore.Qt.AlignCenter)
            # self.collarGPSTable.setItem(0, 0, tag_item)
            # self.collarGPSTable.setItem(0, 4, units_item)
            # self.collarGPSTable.resizeColumnsToContents()

        self.loopGPSTable.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.dataTable.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        # self.loopGPSTable.setSizeAdjustPolicy(
        #     QAbstractScrollArea.AdjustToContents)
        # self.loopGPSTable.resizeColumnsToContents()

        # self.dataTable.blockSignals(True)
        # self.dataTable.setColumnCount(len(self.data_columns))
        # self.dataTable.setHorizontalHeaderLabels(self.data_columns)
        # self.dataTable.setSizeAdjustPolicy(
        #     QAbstractScrollArea.AdjustToContents)
        # self.dataTable.resizeColumnsToContents()
        # self.dataTable.blockSignals(False)

    def clear_table(self, table):
        """
        Clear a given table
        """
        table.blockSignals(True)
        while table.rowCount() > 0:
            table.removeRow(0)
        table.blockSignals(False)

    def make_qt_row(self, df_row, table):
        """
        Add items from a pandas data frame row to a QTableWidget row
        :param df_row: pandas Series object
        :param table: QTableWidget table
        :return: None
        """
        row_pos = table.rowCount()
        # Add a new row to the table
        table.insertRow(row_pos)

        items = df_row.map(lambda x: QTableWidgetItem(str(x))).to_list()
        # Format each item of the table to be centered
        for m, item in enumerate(items):
            item.setTextAlignment(QtCore.Qt.AlignCenter)
            table.setItem(row_pos, m, item)

    def fill_info_tab(self):
        """
        Adds all information from the header, tags, and notes into the info_table.
        :return: None
        """
        self.clear_table(self.info_table)
        bold_font = QtGui.QFont()
        bold_font.setBold(True)
        f = self.pem_file
        info = OrderedDict({
            'Operator': f.operator,
            'Format': f.format,
            'Units': f.units,
            'Timebase': f.timebase,
            'Number of Channels': f.number_of_channels,
            'Number of Readings': f.number_of_readings,
            'Primary Field Value': f.primary_field_value,
            'Loop Dimensions': ' x '.join(f.loop_dimensions.split()[:-1]),
            'Loop Polairty': f.loop_polarity,
            'Normalized': f.normalized,
            'Rx Number': f.rx_number,
            'Rx File Name': f.rx_file_name,
            'Rx Software Ver.': f.rx_software_version,
            'Rx Software Ver. Date': f.rx_software_version_date,
            'Survey Type': f.survey_type,
            'Sync': f.sync,
            'Convention': f.convention
        })
        for i, (key, value) in enumerate(info.items()):
            row = self.info_table.rowCount()
            self.info_table.insertRow(row)

            key_item = QTableWidgetItem(key)
            key_item.setFont(bold_font)
            value_item = QTableWidgetItem(str(value))

            self.info_table.setItem(row, 0, key_item)
            self.info_table.setItem(row, 1, value_item)

        span_start = self.info_table.rowCount()
        for note in f.notes:
            row = self.info_table.rowCount()
            self.info_table.insertRow(row)

            note_item = QTableWidgetItem(note)
            self.info_table.setItem(row, 1, note_item)

        notes_key_item = QTableWidgetItem('Notes')
        notes_key_item.setFont(bold_font)
        self.info_table.setSpan(span_start, 0, len(f.notes), 1)
        self.info_table.setItem(span_start, 0, notes_key_item)

    def fill_gps_table(self, data, table):
        """
        Fill a given GPS table using the information from a data frame
        :param data: pandas DataFrame for one of the GPS data frames only (not for PEM data)
        :param table: QTableWidget to fill
        :return: None
        """
        data = deepcopy(data)
        if data.empty:
            return

        # data.reset_index(inplace=True)
        self.clear_table(table)
        table.blockSignals(True)

        if table == self.loopGPSTable:
            tags = [f"<L{n:02}>" for n in range(len(data.index))]
        else:
            tags = [f"<P{n:02}>" for n in range(len(data.index))]
        data.insert(0, 'Tag', tags)
        data.apply(lambda x: self.make_qt_row(x, table), axis=1)

        if table == self.stationGPSTable:
            self.check_station_duplicates()
            self.check_station_order()
            self.check_missing_gps()
        table.resizeColumnsToContents()
        table.blockSignals(False)

    def fill_data_table(self):
        """
        Fill the dataTable with given PEMFile data
        :param data: PEMFile data
        """
        data = self.get_sorted_data()
        if data.empty:
            return
        else:
            self.clear_table(self.dataTable)
            self.dataTable.blockSignals(True)
            data.apply(lambda x: self.make_qt_row(pd.Series([x.Station,
                                                             x.Component,
                                                             x['Reading index'],
                                                             x['Reading number'],
                                                             x['Number of stacks'],
                                                             x.ZTS]), self.dataTable), axis=1)
            self.color_data_table()
            self.dataTable.resizeColumnsToContents()
            self.dataTable.blockSignals(False)

    def get_sorted_data(self):
        data = self.pem_file.data

        if self.station_sort_rbtn.isChecked():
            data = data.reindex(index=natsort.order_by_index(
                data.index, natsort.index_natsorted(zip(data.Station, data.Component, data['Reading number']))))
            data.reset_index(drop=True, inplace=True)

        elif self.component_sort_rbtn.isChecked():
            data = data.reindex(index=natsort.order_by_index(
                data.index, natsort.index_natsorted(zip(data.Component, data.Station, data['Reading number']))))
            data.reset_index(drop=True, inplace=True)

        elif self.reading_num_sort_rbtn.isChecked():
            data = data.reindex(index=natsort.order_by_index(
                data.index, natsort.index_natsorted(zip(data['Reading number'], data['Reading index']))))
            data.reset_index(drop=True, inplace=True)

        return data

    def update_data_table(self):
        """
        Updates the table based on the values in the PEM File object (self.pem_file)
        """
        self.dataTable.blockSignals(True)
        for station, row in zip(self.pem_file.data, range(self.dataTable.rowCount())):
            items = [QTableWidgetItem(station[j]) for j in self.dataTable_columns]

            for m, item in enumerate(items):
                item.setTextAlignment(QtCore.Qt.AlignCenter)
                self.dataTable.setItem(row, m, item)

        self.color_data_table()
        self.check_missing_gps()
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
        """
        Colors the rows and cells of the dataTable based on several criteria.
        :return: None
        """

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
                item = self.dataTable.item(row, self.dataTable_columns.index('Component'))
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
            Color the dataTable rows where the station suffix is different from the mode
            """

            if not self.pem_file.is_borehole():
                correct_suffix = self.pem_file.data.Station.map(lambda x: re.findall('[NSEW]', x.upper())).mode().to_list()
                while not isinstance(correct_suffix, str):
                    correct_suffix = correct_suffix[0]
                count = 0
                for row in range(self.dataTable.rowCount()):
                    item = self.dataTable.item(row, self.dataTable_columns.index('Station'))
                    if item:
                        station_suffix = re.findall('[NSEW]', item.text().upper())
                        if not station_suffix or station_suffix[0] != correct_suffix:
                            count += 1
                            item.setForeground(QtGui.QColor('red'))
                        else:
                            item.setForeground(QtGui.QColor('black'))
                self.suffix_warnings = count

        def bolden_repeat_stations():
            """
            Makes the station number cell bold if it ends with either 1, 4, 5, 9.
            """
            repeats = 0
            boldFont = QtGui.QFont()
            boldFont.setBold(True)
            normalFont = QtGui.QFont()
            normalFont.setBold(False)
            for row in range(self.dataTable.rowCount()):
                item = self.dataTable.item(row, self.dataTable_columns.index('Station'))
                if item:
                    station_num = re.findall('\d+', item.text())[0]
                    if station_num[-1] == '1' or station_num[-1] == '4' or station_num[-1] == '6' or station_num[-1] == '9':
                        repeats += 1
                        item.setFont(boldFont)
                    else:
                        item.setFont(normalFont)
            return repeats

        color_rows_by_component()
        color_wrong_suffix()
        self.num_repeat_stations = bolden_repeat_stations()
        self.refresh_tables_signal.emit()
        self.lcdRepeats.display(self.num_repeat_stations)

    def check_station_duplicates(self):
        """
        Colors stationGPS table rows to indicate duplicate station numbers in the GPS.
        :return: None
        """
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
        """
        Colors the stationGPS rows, station number column, based on issues with the ordering of the station numbers.
        This is done by first creating a list of ordered numbers based on the first and last GPS station numbers,
        then comparing these values with the coinciding value in the table.
        :return: None
        """
        self.stationGPSTable.blockSignals(True)
        stations = self.get_line().df.Station.map(convert_station).to_list()
        sorted_stations = sorted(stations, reverse=bool(stations[0] > stations[-1]))

        blue_color, red_color = QtGui.QColor('blue'), QtGui.QColor('red')
        blue_color.setAlpha(50)
        red_color.setAlpha(50)
        station_col = self.station_columns.index('Station')

        for row in range(self.stationGPSTable.rowCount()):
            if self.stationGPSTable.item(row, station_col) and stations[row] > sorted_stations[row]:
                self.stationGPSTable.item(row, station_col).setBackground(blue_color)
            elif self.stationGPSTable.item(row, station_col) and stations[row] < sorted_stations[row]:
                self.stationGPSTable.item(row, station_col).setBackground(red_color)
            else:
                self.stationGPSTable.item(row, station_col).setBackground(QtGui.QColor('white'))
        self.stationGPSTable.blockSignals(False)

    def check_missing_gps(self):
        """
        Find stations that are in the Data but aren't in the GPS. Missing GPS are added to the missing_gps_table.
        :return: None
        """
        self.clear_table(self.missing_gps_table)
        data_stations = self.pem_file.data.Station.map(convert_station).unique()
        gps_stations = self.get_line().df.Station.map(convert_station).unique()
        missing_gps = []
        for station in data_stations:
            if station not in gps_stations:
                missing_gps.append(str(station))
        for i, station in enumerate(missing_gps):
            row = i
            self.missing_gps_table.insertRow(row)
            item = QTableWidgetItem(station)
            item.setTextAlignment(QtCore.Qt.AlignCenter)
            item.setForeground(QtGui.QColor('red'))
            self.missing_gps_table.setItem(row, 0, item)

    def remove_table_row_selection(self, table):
        """
        Remove a selected row from a given table
        :param table: QTableWidget table. Either the loop, station, or geometry tables. Not dataTable and not collarGPS table.
        :return: None
        """
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

        if table == self.dataTable or table == self.collarGPSTable:
            return

        selected_rows = self.get_selected_rows(table)
        for row in reversed(selected_rows):
            table.removeRow(row)

        if table == self.stationGPSTable:
            self.check_station_duplicates()
            self.check_missing_gps()
            add_tags()
        elif table == self.loopGPSTable:
            add_tags()
        self.refresh_tables_signal.emit()

    def remove_data_row(self):
        """
        Remove a row from the data table.
        :return: None
        """
        selected_rows = self.get_selected_rows(self.dataTable)

        for row in reversed(selected_rows):
            del self.pem_file.data[row]
            self.dataTable.removeRow(row)

        self.dataTable.blockSignals(True)
        self.color_data_table()
        self.dataTable.blockSignals(False)

    def remove_ri_file(self):
        """
        Remove an RI file
        :return: None
        """
        while self.riTable.rowCount() > 0:
            self.riTable.removeRow(0)
        self.ri_file = None

    def cull_station_gps(self):
        """
        Remove all station GPS from the stationGPSTable where the station number isn't in the PEM data
        :return: None
        """
        gps = self.get_line()
        # Get unique stations in the data
        em_stations = self.pem_file.data.Station.map(convert_station).unique()
        # Create a filter for GPS stations that are in the data stations
        filt = gps.df.Station.astype(int).isin(em_stations)
        gps = gps.df.loc[filt]

        self.fill_gps_table(gps, self.stationGPSTable)

    # def sort_station_gps(self):
    #     line = self.get_line()
    #     sorted_line = line.get_line(sorted=True)
    #     self.fill_station_table(sorted_line)
    #
    # def sort_loop_gps(self):
    #     loop = self.get_loop()
    #     sorted_loop = loop.get_loop(sorted=True)
    #     self.fill_loop_table(sorted_loop)

    # def move_table_row_up(self):
    #     """
    #     Move selected rows of the LoopGPSTable up.
    #     :return: None
    #     """
    #     rows = self.get_selected_rows(self.loopGPSTable)
    #     loop_gps = self.get_loop()
    #
    #     for row in rows:
    #         removed_row = loop_gps.pop(row)
    #         loop_gps.insert(row-1, removed_row)
    #
    #     self.fill_loop_table(loop_gps)
    #     self.loopGPSTable.setSelectionMode(QtGui.QAbstractItemView.MultiSelection)
    #     [self.loopGPSTable.selectRow(row-1) for row in rows]
    #     self.loopGPSTable.setSelectionMode(QtGui.QAbstractItemView.ExtendedSelection)
    #
    # def move_table_row_down(self):
    #     """
    #     Move selected rows of the LoopGPSTable down.
    #     :return: None
    #     """
    #     rows = self.get_selected_rows(self.loopGPSTable)
    #     loop_gps = self.get_loop()
    #
    #     for row in rows:
    #         removed_row = loop_gps.pop(row)
    #         loop_gps.insert(row + 1, removed_row)
    #
    #     self.fill_loop_table(loop_gps)
    #     self.loopGPSTable.setSelectionMode(QtGui.QAbstractItemView.MultiSelection)
    #     [self.loopGPSTable.selectRow(row + 1) for row in rows]
    #     self.loopGPSTable.setSelectionMode(QtGui.QAbstractItemView.ExtendedSelection)
    #
    # def toggle_loop_move_buttons(self):
    #     """
    #     Slot: Enables or disables the loopGPS arrow buttons whenever a row in the table is selected or de-selected.
    #     :return: None
    #     """
    #     if self.loopGPSTable.selectionModel().selectedRows():
    #         self.moveUpButton.setEnabled(True)
    #         self.moveDownButton.setEnabled(True)
    #     else:
    #         self.moveUpButton.setEnabled(False)
    #         self.moveDownButton.setEnabled(False)

    def shift_gps_station_numbers(self):
        """
        Shift the station GPS number from the selected rows of the StationGPSTable. If no rows are currently selected,
        it will do the shift for the entire table.
        :return: None
        """
        print('Shifting station GPS numbers')
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
        """
        Shift the station GPS easting from the selected rows of the StationGPSTable. If no rows are currently selected,
        it will do the shift for the entire table.
        :return: None
        """
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
        """
        Shift the station GPS northing from the selected rows of the StationGPSTable. If no rows are currently selected,
        it will do the shift for the entire table.
        :return: None
        """
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
        """
        Shift the loop GPS elevation from the selected rows of the LoopGPSTable. If no rows are currently selected,
        it will do the shift for the entire table.
        :return: None
        """
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
        """
        Multiplies the station number of the selected rows of the StationGPSTable by -1. If no rows are selected it will
        do so for all rows.
        :return: None
        """

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
        """
        Flips the station numbers from the StationGPSTable head-over-heals.
        :return: None
        """
        gps = self.get_line()
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

    def stations_from_data(self):
        """
        Fills the GPS station numbers in the StationGPSTable using the station numbers in the data.
        :return: None
        """
        data_stations = self.pem_file.get_converted_unique_stations()
        station_column = 5
        for row, station in enumerate(data_stations):
            item = QTableWidgetItem(str(station))
            item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.stationGPSTable.setItem(row, station_column, item)

    def calc_distance(self):
        """
        Calculate the distance between the two rows of GPS points and sets the LCD to this number.
        :return: None
        """
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

    def shift_station_numbers(self):
        """
        Shift the data station number.
        :return: None
        """
        selected_rows = self.get_selected_rows(self.dataTable)
        if not selected_rows:
            selected_rows = range(self.dataTable.rowCount())
        shift_amount = self.shiftStationSpinbox.value()
        self.pem_file = self.file_editor.shift_stations(self.pem_file, shift_amount - self.last_stn_shift_amt,
                                                        rows=selected_rows)
        self.update_data_table()
        self.dataTable.resizeColumnsToContents()
        self.last_stn_shift_amt = shift_amount

    def reset_spinbox(self, spinbox):
        """
        Reset the spinbox value to 0 when a table selection is changed without triggering the spinbox signals
        :param spinbox: QSpinbox object, the one associated with the table.
        :return: None
        """
        spinbox.blockSignals(True)
        spinbox.setValue(0)
        self.last_stn_gps_shift_amt = 0
        self.last_loop_elev_shift_amt = 0
        self.last_stn_shift_amt = 0
        spinbox.blockSignals(False)

    def reverse_polarity(self, selected_rows=None, component=None):
        """
        Reverse the polarity of selected readings
        :param selected_rows: Selected rows from the dataTable to be changed. If none is selected, it will reverse
        the polarity for all rows.
        :param component: Selected component to be changed. If none is selected, it will reverse the polarity for
        all rows.
        :return: None
        """
        print(f'Reversing polarity of rows {selected_rows}, component {component}')
        if not component:
            selected_rows = self.get_selected_rows(self.dataTable)
        if component or selected_rows:
            if component and component in self.pem_file.get_components():
                note = f"<HE3> {component.upper()} component polarity reversed"
                if note not in self.pem_file.notes:
                    self.pem_file.notes.append(note)
                else:
                    self.pem_file.notes.remove(note)
            self.pem_file = self.file_editor.reverse_polarity(self.pem_file, rows=selected_rows, component=component)
            self.update_data_table()
            self.dataTable.resizeColumnsToContents()
            self.window().statusBar().showMessage('Polarity flipped.', 2000)

    def change_station_suffix(self):
        """
        Change the suffix letter from the station number for selected rows in the dataTable. Only for surface files.
        Input suffix must be either N, S, E, or W, case doesn't matter.
        :return: None
        """
        if self.pem_file.is_borehole():  # Shouldn't be needed since the button is disabled for boreholes
            return

        suffix, okPressed = QInputDialog.getText(self, "Change Station Suffix", "New Suffix:")
        if okPressed and suffix.upper() in ['N', 'E', 'S', 'W']:
            station_col = self.data_columns.index('Station')
            rows = self.get_selected_rows(self.dataTable)
            if not rows:
                rows = range(self.dataTable.rowCount())
            for row in rows:
                station = self.dataTable.item(row, station_col).text()
                new_station = re.sub('[NESW]', suffix.upper(), station)

                new_station_item = QTableWidgetItem(new_station)
                new_station_item.setTextAlignment(QtCore.Qt.AlignCenter)
                self.dataTable.setItem(row, station_col, new_station_item)
        elif okPressed:
            self.message.setWindowTitle('Invalid Suffix')
            self.message.setText('Suffix must be one of [NSEW]')
            self.message.setStandardButtons(QMessageBox.Ok)
            self.message.buttonClicked.connect(self.message.close)
            self.message.exec()

    def change_component(self):
        """
        Change the component of selected readings based on user input
        :return: None
        """
        new_comp, okPressed = QInputDialog.getText(self, "Change Component", "New Component:")
        if okPressed and new_comp.upper() in ['Z', 'X', 'Y']:
            rows = self.get_selected_rows(self.dataTable)
            for row in rows:
                new_comp_item = QTableWidgetItem(new_comp.upper())
                new_comp_item.setTextAlignment(QtCore.Qt.AlignCenter)
                self.dataTable.setItem(row, self.data_columns.index('Comp.'), new_comp_item)
        elif okPressed:
            self.message.setWindowTitle('Invalid Component')
            self.message.setText('Component must be one of [Z, X, Y]')
            self.message.setStandardButtons(QMessageBox.Ok)
            self.message.buttonClicked.connect(self.message.close)
            self.message.exec()

    def rename_repeat_stations(self):
        """
        Change any station name in the dataTable that is a repeat station
        (i.e. any station ending in 1,4,6,9 to 0,5,5,0 respectively).
        :return: None
        """
        if self.num_repeat_stations > 0:
            self.pem_file = self.file_editor.rename_repeats(self.pem_file)
            self.update_data_table()
            self.refresh_tables_signal.emit()
            self.window().statusBar().showMessage(
                f'{self.num_repeat_stations} repeat station(s) automatically renamed.', 2000)
        else:
            pass

    def get_selected_rows(self, table):
        """
        Return the rows that are currently selected from a given table.
        :param table: QTableWidget table.
        :return: List of rows that are selected.
        """
        return [model.row() for model in table.selectionModel().selectedRows()]

    def get_loop(self):
        """
        Create a TransmitterLoop object using the information in the loopGPSTable
        :return: TransmitterLoop object
        """
        gps = {
            'Easting': [],
            'Northing': [],
            'Elevation': [],
            'Unit': [],
        }
        for row in range(self.loopGPSTable.rowCount()):
            gps['Easting'].append(self.loopGPSTable.item(row, 1).text())
            gps['Northing'].append(self.loopGPSTable.item(row, 2).text())
            gps['Elevation'].append(self.loopGPSTable.item(row, 3).text())
            gps['Unit'].append(self.loopGPSTable.item(row, 4).text())
        return TransmitterLoop(pd.DataFrame(gps))

    def get_line(self):
        """
        Create a SurveyLine object using the information in the stationGPSTable
        :return: SurveyLine object
        """
        gps = {
            'Easting': [],
            'Northing': [],
            'Elevation': [],
            'Unit': [],
            'Station': []
        }
        for row in range(self.stationGPSTable.rowCount()):
            gps['Easting'].append(self.stationGPSTable.item(row, 1).text())
            gps['Northing'].append(self.stationGPSTable.item(row, 2).text())
            gps['Elevation'].append(self.stationGPSTable.item(row, 3).text())
            gps['Unit'].append(self.stationGPSTable.item(row, 4).text())
            gps['Station'].append(self.stationGPSTable.item(row, 5).text())
        return SurveyLine(pd.DataFrame(gps))

    def get_collar(self):
        """
        Create a BoreholeCollar object from the information in the collarGPSTable
        :return: BoreholeCollar object
        """
        gps = {
            'Easting': [],
            'Northing': [],
            'Elevation': [],
            'Unit': []
        }
        for row in range(self.collarGPSTable.rowCount()):
            gps['Easting'].append(self.collarGPSTable.item(row, 1).text())
            gps['Northing'].append(self.collarGPSTable.item(row, 2).text())
            gps['Elevation'].append(self.collarGPSTable.item(row, 3).text())
            gps['Unit'].append(self.collarGPSTable.item(row, 4).text())
        return BoreholeCollar(pd.DataFrame(gps))

    def get_segments(self):
        """
        Create a BoreholeSegments object using the information in the geometryTable
        :return: BoreholeSegments object
        """
        gps = {
            'Azimuth': [],
            'Dip': [],
            'Segment length': [],
            'Unit': [],
            'Depth': []
        }
        for row in range(self.geometryTable.rowCount()):
            gps['Azimuth'].append(self.geometryTable.item(row, 1).text())
            gps['Dip'].append(self.geometryTable.item(row, 2).text())
            gps['Segment length'].append(self.geometryTable.item(row, 3).text())
            gps['Unit'].append(self.geometryTable.item(row, 4).text())
            gps['Depth'].append(self.geometryTable.item(row, 5).text())

        return BoreholeSegments(pd.DataFrame(gps))

    def get_geometry(self):
        """
        Create a BoreholeGeometry object from the information in the collarGPSTable and geometryTable
        :return: BoreholeGeometry object
        """
        return BoreholeGeometry(self.get_collar(), self.get_segments())

    def export_gps(self, type):
        """
        Export the GPS in the station GPS table to a text or CSV file.
        :type: str: 'station' or 'loop'
        :return: None
        """
        if type == 'station':
            gps = self.get_line()
        else:
            gps = self.get_loop()

        if gps:
            gps_str = ''
            for line in gps:
                gps_str += ' '.join(line) + '\n'

            default_path = os.path.dirname(self.pem_file.filepath)
            selected_path = self.dialog.getSaveFileName(self, 'Save File', directory=default_path,
                                                        filter='Text files (*.txt);; CSV files (*.csv);; All files(*.*)')
            if selected_path[0]:
                with open(selected_path[0], 'w+') as file:
                    file.write(gps_str)
                os.startfile(selected_path[0])
            else:
                self.window().statusBar().showMessage('Cancelled.', 2000)

