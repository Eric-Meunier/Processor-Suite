import logging
import os
import sys
from collections import OrderedDict
from copy import deepcopy

import math
import numpy as np
import pandas as pd
from pathlib import Path
from PyQt5 import (QtCore, QtGui, uic)
from PyQt5.QtWidgets import (QWidget, QTableWidgetItem, QAction, QMessageBox, QItemDelegate,
                             QFileDialog, QErrorMessage, QHeaderView)

from src.gps.gps_editor import TransmitterLoop, SurveyLine, BoreholeCollar, BoreholeSegments, BoreholeGeometry, \
    GPXEditor
from src.pem.pem_file import StationConverter
from src.geometry.pem_geometry import PEMGeometry
from src.gps.gps_adder import LoopAdder, LineAdder
from src.qt_py.ri_importer import RIFile

logger = logging.getLogger(__name__)

if getattr(sys, 'frozen', False):
    application_path = os.path.dirname(sys.executable)
    pemInfoWidgetCreatorFile = 'ui\\pem_info_widget.ui'
    icons_path = 'ui\\icons'
else:
    application_path = os.path.dirname(os.path.abspath(__file__))
    pemInfoWidgetCreatorFile = os.path.join(os.path.dirname(application_path), 'ui\\pem_info_widget.ui')
    icons_path = os.path.join(os.path.dirname(application_path), "ui\\icons")

# Load Qt ui file into a class
Ui_PEMInfoWidget, QtBaseClass = uic.loadUiType(pemInfoWidgetCreatorFile)
logger = logging.getLogger(__name__)


def clear_table(table):
    """
    Clear a given table
    """
    table.blockSignals(True)
    while table.rowCount() > 0:
        table.removeRow(0)
    table.blockSignals(False)


class PEMFileInfoWidget(QWidget, Ui_PEMInfoWidget):
    refresh_row_signal = QtCore.pyqtSignal()  # Send a signal to PEMEditor to refresh its main table.

    share_loop_signal = QtCore.pyqtSignal(object)
    share_line_signal = QtCore.pyqtSignal(object)
    share_collar_signal = QtCore.pyqtSignal(object)
    share_segments_signal = QtCore.pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__()
        self.setupUi(self)

        self.parent = parent
        self.pem_file = None
        self.ri_file = None
        self.selected_row_info = None
        self.active_table = None

        self.converter = StationConverter()
        self.ri_editor = RIFile()
        self.dialog = QFileDialog()
        self.error = QErrorMessage()
        self.message = QMessageBox()

        self.last_stn_gps_shift_amt = 0
        self.last_loop_elev_shift_amt = 0
        self.last_stn_shift_amt = 0

        self.installEventFilter(self)
        self.loop_table.installEventFilter(self)
        self.line_table.installEventFilter(self)
        self.collar_table.installEventFilter(self)
        self.segments_table.installEventFilter(self)
        self.ri_table.installEventFilter(self)
        self.loop_table.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.line_table.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.collar_table.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.segments_table.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.ri_table.setFocusPolicy(QtCore.Qt.StrongFocus)

        self.line_table_columns = ['Easting', 'Northing', 'Elevation', 'Units', 'Station']
        self.loop_table_columns = ['Easting', 'Northing', 'Elevation', 'Units']

        self.init_actions()
        self.init_signals()

    def init_actions(self):
        self.loop_table.remove_row_action = QAction("&Remove", self)
        self.addAction(self.loop_table.remove_row_action)
        self.loop_table.remove_row_action.triggered.connect(lambda: self.remove_table_row(self.loop_table))
        self.loop_table.remove_row_action.triggered.connect(lambda:
                                                            self.edit_loop_btn.setEnabled(
                                                                True if self.loop_table.rowCount() > 0 else False))
        self.loop_table.remove_row_action.setShortcut('Del')
        self.loop_table.remove_row_action.setEnabled(False)

        self.line_table.remove_row_action = QAction("&Remove", self)
        self.addAction(self.line_table.remove_row_action)
        self.line_table.remove_row_action.triggered.connect(lambda: self.remove_table_row(self.line_table))
        self.line_table.remove_row_action.triggered.connect(lambda:
                                                            self.edit_line_btn.setEnabled(
                                                                True if self.line_table.rowCount() > 0 else False))
        self.line_table.remove_row_action.setShortcut('Del')
        self.line_table.remove_row_action.setEnabled(False)

        self.collar_table.remove_row_action = QAction("&Remove", self)
        self.addAction(self.collar_table.remove_row_action)
        self.collar_table.remove_row_action.triggered.connect(
            lambda: self.remove_table_row(self.collar_table))
        self.collar_table.remove_row_action.setShortcut('Del')
        self.collar_table.remove_row_action.setEnabled(False)

        self.segments_table.remove_row_action = QAction("&Remove", self)
        self.addAction(self.segments_table.remove_row_action)
        self.segments_table.remove_row_action.triggered.connect(
            lambda: self.remove_table_row(self.segments_table))
        self.segments_table.remove_row_action.setShortcut('Del')
        self.segments_table.remove_row_action.setEnabled(False)

        self.ri_table.remove_ri_file_action = QAction("&Remove RI File", self)
        self.addAction(self.ri_table.remove_ri_file_action)
        self.ri_table.remove_ri_file_action.triggered.connect(self.remove_ri_file)
        self.ri_table.remove_ri_file_action.setStatusTip("Remove the RI file")
        self.ri_table.remove_ri_file_action.setShortcut('Shift+Del')
        self.ri_table.remove_ri_file_action.setEnabled(False)

    def init_signals(self):
        # Buttons
        self.cullStationGPSButton.clicked.connect(self.cull_station_gps)

        self.flip_station_numbers_button.clicked.connect(self.reverse_station_gps_numbers)
        self.flip_station_signs_button.clicked.connect(self.flip_station_gps_polarity)
        self.flip_station_signs_button.clicked.connect(self.check_missing_gps)
        self.stations_from_data_btn.clicked.connect(self.stations_from_data)
        self.stations_from_data_btn.clicked.connect(self.check_missing_gps)

        self.open_station_gps_btn.clicked.connect(self.open_gps_file_dialog)
        self.open_loop_gps_btn.clicked.connect(self.open_gps_file_dialog)
        self.open_collar_gps_btn.clicked.connect(self.open_gps_file_dialog)
        self.add_segments_btn.clicked.connect(self.open_pem_geometry)

        self.export_station_gps_btn.clicked.connect(lambda: self.export_gps('station'))
        self.export_loop_gps_btn.clicked.connect(lambda: self.export_gps('loop'))
        self.export_collar_gps_btn.clicked.connect(lambda: self.export_gps('collar'))
        self.export_segments_btn.clicked.connect(lambda: self.export_gps('segments'))

        self.edit_loop_btn.clicked.connect(lambda: self.add_loop(loop_content=self.get_loop()))
        self.edit_line_btn.clicked.connect(lambda: self.add_line(line_content=self.get_line()))

        self.share_loop_gps_btn.clicked.connect(lambda: self.share_loop_signal.emit(self.get_loop()))
        self.share_line_gps_btn.clicked.connect(lambda: self.share_line_signal.emit(self.get_line()))
        self.share_collar_gps_btn.clicked.connect(lambda: self.share_collar_signal.emit(self.get_collar()))
        self.share_segments_btn.clicked.connect(lambda: self.share_segments_signal.emit(self.get_segments()))

        # Table changes
        self.line_table.cellChanged.connect(self.check_station_duplicates)
        self.line_table.cellChanged.connect(self.color_line_table)
        self.line_table.cellChanged.connect(self.check_missing_gps)
        self.line_table.cellChanged.connect(lambda: self.gps_object_changed(self.line_table, refresh=True))
        self.line_table.itemSelectionChanged.connect(self.calc_distance)
        self.line_table.itemSelectionChanged.connect(lambda: self.reset_spinbox(self.shiftStationGPSSpinbox))

        self.loop_table.itemSelectionChanged.connect(lambda: self.reset_spinbox(self.shift_elevation_spinbox))
        self.loop_table.cellChanged.connect(lambda: self.gps_object_changed(self.loop_table, refresh=True))

        self.collar_table.cellChanged.connect(lambda: self.gps_object_changed(self.collar_table, refresh=True))

        # Spinboxes
        self.shiftStationGPSSpinbox.valueChanged.connect(self.shift_gps_station_numbers)
        self.shift_elevation_spinbox.valueChanged.connect(self.shift_loop_elevation)

    def init_tables(self):
        """
        Adds the columns and formats each table.
        :return: None
        """
        self.tabs.removeTab(4)
        float_delegate = FloatDelegate(2)  # Must keep this reference or else it is garbage collected

        if not self.pem_file.is_borehole():
            self.tabs.removeTab(self.tabs.indexOf(self.geometry_tab))
            self.line_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            self.line_table.setItemDelegateForColumn(0, float_delegate)
            self.line_table.setItemDelegateForColumn(1, float_delegate)
            self.line_table.setItemDelegateForColumn(2, float_delegate)

        elif self.pem_file.is_borehole():
            self.tabs.removeTab(self.tabs.indexOf(self.station_gps_tab))
            self.segments_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            self.collar_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            self.collar_table.setItemDelegateForColumn(0, float_delegate)
            self.collar_table.setItemDelegateForColumn(1, float_delegate)
            self.collar_table.setItemDelegateForColumn(2, float_delegate)

        self.loop_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.loop_table.setItemDelegateForColumn(0, float_delegate)
        self.loop_table.setItemDelegateForColumn(1, float_delegate)
        self.loop_table.setItemDelegateForColumn(2, float_delegate)

    def eventFilter(self, source, event):
        if event.type() == QtCore.QEvent.Close:
            print(f"Closing PIW")
            event.accept()
            self.deleteLater()

        if source is self.line_table:  # Makes the 'Del' shortcut work when the table is in focus
            if event.type() == QtCore.QEvent.FocusIn:
                self.line_table.remove_row_action.setEnabled(True)
            elif event.type() == QtCore.QEvent.FocusOut:
                self.line_table.remove_row_action.setEnabled(False)
            elif event.type() == QtCore.QEvent.KeyPress:
                if event.key() == QtCore.Qt.Key_Escape:
                    self.line_table.clearSelection()
                    return True

        elif source is self.loop_table:
            if event.type() == QtCore.QEvent.FocusIn:
                self.loop_table.remove_row_action.setEnabled(True)
            elif event.type() == QtCore.QEvent.FocusOut:
                self.loop_table.remove_row_action.setEnabled(False)
            elif event.type() == QtCore.QEvent.KeyPress:
                if event.key() == QtCore.Qt.Key_Escape:
                    self.loop_table.clearSelection()
                    return True

        elif source is self.collar_table:
            if event.type() == QtCore.QEvent.FocusIn:
                self.collar_table.remove_row_action.setEnabled(True)
            elif event.type() == QtCore.QEvent.FocusOut:
                self.collar_table.remove_row_action.setEnabled(False)
            elif event.type() == QtCore.QEvent.KeyPress:
                if event.key() == QtCore.Qt.Key_Escape:
                    self.collar_table.clearSelection()
                    return True

        elif source is self.segments_table:
            if event.type() == QtCore.QEvent.FocusIn:
                self.segments_table.remove_row_action.setEnabled(True)
            elif event.type() == QtCore.QEvent.FocusOut:
                self.segments_table.remove_row_action.setEnabled(False)
            elif event.type() == QtCore.QEvent.KeyPress:
                if event.key() == QtCore.Qt.Key_Escape:
                    self.segments_table.clearSelection()
                    return True

        elif source is self.ri_table:
            if event.type() == QtCore.QEvent.FocusIn:
                self.ri_table.remove_ri_file_action.setEnabled(True)
            elif event.type() == QtCore.QEvent.FocusOut:
                self.ri_table.remove_ri_file_action.setEnabled(False)
            elif event.type() == QtCore.QEvent.KeyPress:
                if event.key() == QtCore.Qt.Key_Escape:
                    self.ri_table.clearSelection()
                    return True

        return super(QWidget, self).eventFilter(source, event)

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

    def open_file(self, pem_file):
        """
        Action of opening a PEM file.
        :param pem_file: PEMFile object.
        """
        self.pem_file = pem_file

        self.init_tables()
        if self.pem_file.is_borehole():
            self.fill_gps_table(self.pem_file.get_collar(), self.collar_table)
            self.fill_gps_table(self.pem_file.get_segments(), self.segments_table)
        else:
            self.fill_gps_table(self.pem_file.get_line(), self.line_table)
        self.fill_info_tab()
        self.fill_gps_table(self.pem_file.loop.get_loop(), self.loop_table)

    def open_ri_file(self, filepath):
        """
        Action of opening an RI file. Adds the contents of the RI file to the RIFileTable.
        :param filepath: Filepath of the RI file.
        :return: None
        """
        def make_ri_table():
            columns = self.ri_file.columns
            self.ri_table.setColumnCount(len(columns))
            self.ri_table.setHorizontalHeaderLabels(columns)

        def fill_ri_table():
            clear_table(self.ri_table)

            for i, row in enumerate(self.ri_file.data):
                row_pos = self.ri_table.rowCount()
                self.ri_table.insertRow(row_pos)
                items = [QTableWidgetItem(row[key]) for key in self.ri_file.columns]

                for m, item in enumerate(items):
                    item.setTextAlignment(QtCore.Qt.AlignCenter)
                    self.ri_table.setItem(row_pos, m, item)

        def add_header_from_pem():
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

    def open_gps_file_dialog(self):
        """
        Open GPS files through the file dialog
        """
        files = self.dialog.getOpenFileNames(self, 'Open GPS File', filter='TXT files (*.txt);; CSV files (*.csv);; '
                                                                           'GPX files (*.gpx);; All files(*.*)')[0]
        if not files:
            return

        self.add_gps(files)

    def open_gps_files(self, files):
        """
        Open GPS files
        :param files: list or str, filepath(s) of GPS files
        :param crs: Proj CRS object for the GPS objects
        """

        def merge_files(files):
            """
            Merge contents of files into one list
            :param files: list of str, filepaths of text file or GPX files
            :return: str
            """
            merged_file = []
            gpx_editor = GPXEditor()
            for file in files:
                if file.suffix.lower() == '.gpx':
                    # Convert the GPX file to string
                    gps, zone, hemisphere = gpx_editor.get_utm(file, as_string=True)
                    contents = [c.strip().split() for c in gps]
                else:
                    if file.suffix.lower() == '.csv':
                        contents = pd.read_csv(file, delim_whitespace=False, header=None).to_numpy()

                    elif file.suffix.lower() in ['.xlsx', '.xls']:
                        contents = pd.read_excel(file, delim_whitespace=False, header=None).to_numpy()

                    else:
                        contents = open(file, mode='rt').readlines()
                        contents = [c.strip().split() for c in contents]

                merged_file.extend(contents)
            return merged_file

        if not isinstance(files, list):
            files = [files]

        files = [Path(f) for f in files]

        file_contents = merge_files(files)
        current_tab = self.tabs.currentWidget()

        # Add survey line GPS
        if current_tab == self.station_gps_tab:
            self.add_line(file_contents)

        # Add borehole collar GPS
        elif current_tab == self.geometry_tab:
            try:
                collar = BoreholeCollar(file_contents)
                errors = collar.get_errors()
                if not errors.empty:
                    self.message.warning(self, 'Parsing Error',
                                         f"The following rows could not be parsed:\n\n{errors.to_string()}.")
                if not collar.df.empty:
                    self.fill_gps_table(collar.df, self.collar_table)
                    self.gps_object_changed(self.collar_table, refresh=True)
                else:
                    self.message.information(self, 'No GPS Found', f"{collar.error_msg}")
            except Exception as e:
                logger.critical(f"{e}.")
                self.error.showMessage(f"Error adding borehole collar: {str(e)}.")

        # Add loop GPS
        elif current_tab == self.loop_gps_tab:
            self.add_loop(file_contents)

        else:
            pass

    def open_pem_geometry(self):
        """
        Open the PEMGeometry window
        """

        def accept_geometry(seg):
            self.pem_file.segments = seg
            self.refresh_row_signal.emit()

        global pem_geometry
        pem_geometry = PEMGeometry(parent=self)
        pem_geometry.accepted_sig.connect(accept_geometry)
        pem_geometry.open(self.pem_file)

    def add_line(self, line_content=None):
        """
        Open the LineAdder and add the SurveyLine
        :param line_content: str or Path, SurveyLine object, or pd DataFrame. If None is passed, will take the line
        in the line_table.
        """

        def line_accept_sig_wrapper(data):
            self.fill_gps_table(data, self.line_table)

        global line_adder
        line_adder = LineAdder(parent=self)
        line_adder.accept_sig.connect(line_accept_sig_wrapper)
        line_adder.accept_sig.connect(lambda: self.gps_object_changed(self.line_table, refresh=True))

        if line_content is None:
            line_content = self.get_line()

        try:
            line = SurveyLine(line_content)
            if line.df.empty:
                self.message.information(self, 'No GPS Found', f"{line.error_msg}.")
            else:
                line_adder.open(line, name=self.pem_file.line_name)
        except Exception as e:
            logger.critical(str(e))
            self.error.showMessage(f"Error adding line: {str(e)}.")

    def add_loop(self, loop_content=None):
        """
        Open the LoopAdder and add the TransmitterLoop
        :param loop_content: str or Path, TransmitterLoop object, or pd DataFrame. If None is passed, will take the loop
        in the loop_table.
        """

        def loop_accept_sig_wrapper(data):
            self.fill_gps_table(data, self.loop_table)

        global loop_adder
        loop_adder = LoopAdder(parent=self)
        loop_adder.accept_sig.connect(loop_accept_sig_wrapper)
        loop_adder.accept_sig.connect(lambda: self.gps_object_changed(self.loop_table, refresh=True))

        if loop_content is None:
            loop_content = self.get_loop()

        try:
            loop = TransmitterLoop(loop_content)
            if loop.df.empty:
                self.message.information(self, 'No GPS Found', f"{loop.error_msg}")
            loop_adder.open(loop, name=self.pem_file.loop_name)
        except Exception as e:
            logger.critical(f"{e}.")
            self.error.showMessage(f"Error adding loop: {str(e)}")

    def fill_info_tab(self):
        """
        Adds all information from the header, tags, and notes into the info_table.
        :return: None
        """
        clear_table(self.info_table)
        bold_font = QtGui.QFont()
        bold_font.setBold(True)
        f = self.pem_file
        info = OrderedDict({
            'Operator': f.operator,
            'Format': f.format,
            'Units': f.units,
            'Timebase': f.timebase,
            'Ramp': f.ramp,
            'Number of Channels': f.number_of_channels,
            'Number of Readings': f.number_of_readings,
            'Primary Field Value': f.primary_field_value,
            'Loop Dimensions': ' x '.join(f.loop_dimensions.split()[:-1]),
            'Loop Polarity': f.loop_polarity,
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
        # Set the Notes cell to span multiple notes
        self.info_table.setSpan(span_start, 0, len(f.notes), 1)
        self.info_table.setItem(span_start, 0, notes_key_item)

        # Set the column widths
        header = self.info_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)

    def fill_gps_table(self, data, table):
        """
        Fill a given GPS table using the information from a data frame
        :param data: pandas DataFrame for one of the GPS data frames only (not for PEM data)
        :param table: QTableWidget to fill
        :return: None
        """

        def write_row(df_row, table):
            """
            Add items from a pandas data frame row to a QTableWidget row
            :param df_row: pandas Series object
            :param table: QTableWidget table
            :return: None
            """
            def series_to_items(x):
                # if isinstance(x, float):
                    # item = QTableWidgetItem(f"{x:.2f}")
                item = QTableWidgetItem()
                item.setData(QtCore.Qt.EditRole, x)
                return item
                    # return QTableWidgetItem(f"{x}")
                # else:
                #     return QTableWidgetItem(str(x))

            # Add a new row to the table
            row_pos = table.rowCount()
            table.insertRow(row_pos)

            items = df_row.map(series_to_items).to_list()
            # Format each item of the table to be centered
            for m, item in enumerate(items):
                item.setTextAlignment(QtCore.Qt.AlignCenter)
                table.setItem(row_pos, m, item)

        data = deepcopy(data)
        if data.empty:
            return

        # data.reset_index(inplace=True)
        clear_table(table)
        table.blockSignals(True)

        if table == self.loop_table:
            self.edit_loop_btn.setEnabled(True)
            table.verticalHeader().show()
        elif table == self.line_table:
            self.edit_line_btn.setEnabled(True)
            table.verticalHeader().show()
        elif table == self.segments_table:
            table.verticalHeader().show()

        data.apply(lambda x: write_row(x, table), axis=1)

        if table == self.line_table:
            self.check_station_duplicates()
            self.color_line_table()
            self.check_missing_gps()
        table.blockSignals(False)

    def color_line_table(self):
        """
        Colors the line_table rows, station number column, based on issues with the ordering of the station numbers.
        This is done by first creating a list of ordered numbers based on the first and last GPS station numbers,
        then comparing these values with the coinciding value in the table.
        :return: None
        """
        self.line_table.blockSignals(True)
        stations = self.get_line().df.Station.map(self.converter.convert_station).to_list()
        sorted_stations = sorted(stations, reverse=bool(stations[0] > stations[-1]))

        blue_color, red_color = QtGui.QColor('blue'), QtGui.QColor('red')
        blue_color.setAlpha(50)
        red_color.setAlpha(50)
        station_col = self.line_table_columns.index('Station')

        for row in range(self.line_table.rowCount()):
            table_value = stations[row]
            sorted_value = sorted_stations[row]
            if self.line_table.item(row, station_col) and table_value > sorted_value:
                self.line_table.item(row, station_col).setBackground(blue_color)
            elif self.line_table.item(row, station_col) and table_value < sorted_value:
                self.line_table.item(row, station_col).setBackground(red_color)
            else:
                self.line_table.item(row, station_col).setBackground(QtGui.QColor('white'))
        self.line_table.blockSignals(False)

    def check_station_duplicates(self):
        """
        Colors stationGPS table rows to indicate duplicate station numbers in the GPS.
        :return: None
        """
        self.line_table.blockSignals(True)
        stations_column = self.line_table_columns.index('Station')
        stations = []
        for row in range(self.line_table.rowCount()):
            if self.line_table.item(row, stations_column):
                station = self.line_table.item(row, stations_column).text()
                if station in stations:
                    other_station_index = stations.index(station)
                    self.line_table.item(row, stations_column).setForeground(QtGui.QColor('red'))
                    self.line_table.item(other_station_index, stations_column).setForeground(QtGui.QColor('red'))
                else:
                    self.line_table.item(row, stations_column).setForeground(QtGui.QColor('black'))
                stations.append(station)
        self.line_table.blockSignals(False)

    def check_missing_gps(self):
        """
        Find stations that are in the EM data but aren't in the GPS. Missing GPS are added to the missing_gps_list.
        :return: None
        """
        self.missing_gps_list.clear()
        data_stations = self.pem_file.get_stations(converted=True)
        gps_stations = self.get_line().df.Station.astype(int).unique()
        filt = np.isin(data_stations, gps_stations, invert=True)
        missing_gps = data_stations[filt]

        # Add the missing GPS stations to the missing_gps_list
        for i, station in enumerate(missing_gps):
            self.missing_gps_list.addItem(str(station))

    def remove_table_row(self, table):
        """
        Remove a selected row from a given table
        :param table: QTableWidget table. Either the loop, station, or geometry tables. Not data_table and not collarGPS table.
        :return: None
        """
        table.blockSignals(True)

        if table == self.collar_table:
            self.collar_table.clearContents()
            return

        selected_rows = self.get_selected_rows(table)
        for row in reversed(selected_rows):
            table.removeRow(row)

        if table == self.line_table:
            self.check_station_duplicates()
            self.check_missing_gps()

        table.blockSignals(False)
        self.gps_object_changed(table, refresh=True)

    def remove_ri_file(self):
        """
        Remove an RI file
        :return: None
        """
        while self.ri_table.rowCount() > 0:
            self.ri_table.removeRow(0)
        self.ri_file = None

    def cull_station_gps(self):
        """
        Remove all station GPS from the line_table where the station number isn't in the PEM data
        :return: None
        """
        gps = self.get_line()
        # Get unique stations in the data
        em_stations = self.pem_file.get_stations(converted=True)
        # Create a filter for GPS stations that are in the data stations
        filt = gps.df.Station.astype(int).isin(em_stations)
        gps = gps.df.loc[filt]

        self.fill_gps_table(gps, self.line_table)
        self.gps_object_changed(self.line_table, refresh=True)

    def export_gps(self, type):
        """
        Export the GPS in the station GPS table to a text or CSV file.
        :type: type: 'station' or 'loop'
        :return: None
        """
        if type == 'station':
            gps = self.get_line()
        elif type == 'loop':
            gps = self.get_loop()
        elif type == 'collar':
            gps = self.get_collar()
        elif type == 'segments':
            gps = self.get_segments()
        else:
            raise ValueError(f"{type} is not a valid GPS type to export.")

        if gps.df.empty:
            logger.warning(f"No GPS to export.")
            return

        default_path = str(self.pem_file.filepath.parent)
        if type in ['station', 'loop', 'collar']:
            selected_path = self.dialog.getSaveFileName(self, 'Save File',
                                                        directory=default_path,
                                                        filter='Text file (*.txt);; CSV file (*.csv);;')
            if selected_path[0]:
                if selected_path[0].endswith('txt'):
                    gps_str = gps.to_string()
                elif selected_path[0].endswith('csv'):
                    gps_str = gps.to_csv()
                else:
                    self.message.information(self, 'Invalid file type', f"Selected file type is invalid. Must be either"
                                                                        f"'txt' or 'csv'")
                    return
            else:
                return
        else:
            selected_path = self.dialog.getSaveFileName(self, 'Save File',
                                                        directory=default_path,
                                                        filter='SEG files (*.seg)')
            if selected_path[0]:
                gps_str = gps.to_string()
            else:
                return

        with open(selected_path[0], 'w+') as file:
            file.write(gps_str)
        os.startfile(selected_path[0])

    def shift_gps_station_numbers(self):
        """
        Shift the station GPS number from the selected rows of the StationGPSTable. If no rows are currently selected,
        it will do the shift for the entire table.
        :return: None
        """
        self.line_table.blockSignals(True)

        def apply_station_shift(row):
            station_column = self.line_table_columns.index('Station')
            station_item = self.line_table.item(row, station_column)
            if station_item:
                station = station_item.text()
            else:
                return

            try:
                station = int(station)
            except ValueError:
                logger.error(f"{station} is not an integer.")
                return
            else:
                new_station_item = QTableWidgetItem(str(station + (shift_amount - self.last_stn_gps_shift_amt)))
                new_station_item.setTextAlignment(QtCore.Qt.AlignCenter)
                self.line_table.setItem(row, station_column, new_station_item)

        shift_amount = self.shiftStationGPSSpinbox.value()

        selected_rows = self.get_selected_rows(self.line_table)
        rows = range(self.line_table.rowCount()) if not selected_rows else selected_rows

        for row in rows:
            apply_station_shift(row)

        self.last_stn_gps_shift_amt = shift_amount

        # self.setSelectedRange(10)  # for testing errors
        self.line_table.blockSignals(False)
        self.gps_object_changed(self.line_table, refresh=False)

        # Color the table
        self.color_line_table()
        self.check_station_duplicates()
        self.check_missing_gps()

    def shift_loop_elevation(self):
        """
        Shift the loop GPS elevation from the selected rows of the LoopGPSTable. If no rows are currently selected,
        it will do the shift for the entire table.
        :return: None
        """
        self.loop_table.blockSignals(True)

        def apply_elevation_shift(row):
            elevation_item = self.loop_table.item(row, self.loop_table_columns.index('Elevation'))
            if elevation_item:
                elevation = float(elevation_item.text())
            else:
                return

            new_elevation = elevation + (shift_amount - self.last_loop_elev_shift_amt)
            new_elevation_item = QTableWidgetItem('{:.2f}'.format(new_elevation))
            new_elevation_item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.loop_table.setItem(row, self.loop_table_columns.index('Elevation'), new_elevation_item)

        shift_amount = self.shift_elevation_spinbox.value()

        selected_rows = self.get_selected_rows(self.loop_table)
        rows = range(self.loop_table.rowCount()) if not selected_rows else selected_rows

        for row in rows:
            apply_elevation_shift(row)

        self.last_loop_elev_shift_amt = shift_amount

        self.loop_table.blockSignals(False)
        self.gps_object_changed(self.loop_table, refresh=False)

    def flip_station_gps_polarity(self):
        """
        Multiplies the station number of the selected rows of the StationGPSTable by -1. If no rows are selected it will
        do so for all rows.
        :return: None
        """
        self.line_table.blockSignals(True)
        station_column = self.line_table_columns.index('Station')

        def flip_stn_num(row):
            station_item = self.line_table.item(row, station_column)
            if station_item:
                station = int(station_item.text())
            else:
                return

            new_station_item = QTableWidgetItem(str(station * -1))
            new_station_item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.line_table.setItem(row, station_column, new_station_item)

        selected_rows = self.get_selected_rows(self.loop_table)
        rows = range(self.loop_table.rowCount()) if not selected_rows else selected_rows

        for row in rows:
            flip_stn_num(row)

        self.line_table.blockSignals(False)

        self.gps_object_changed(self.line_table, refresh=False)

    def reverse_station_gps_numbers(self):
        """
        Flips the station numbers from the StationGPSTable head-over-heels.
        :return: None
        """
        gps = self.get_line().df
        if not gps.empty:
            stations = gps.Station.to_list()
            rev_stations = stations[::-1]
            gps.Station = rev_stations
            self.fill_gps_table(gps, self.line_table)
            self.gps_object_changed(self.line_table, refresh=False)
        else:
            pass

    def stations_from_data(self):
        """
        Fills the GPS station numbers in the StationGPSTable using the station numbers in the data.
        :return: None
        """
        self.line_table.blockSignals(True)

        data_stations = self.pem_file.get_stations(converted=True)
        for row, station in enumerate(data_stations):
            item = QTableWidgetItem(str(station))
            item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.line_table.setItem(row, self.line_table_columns.index('Station'), item)
            self.gps_object_changed(self.line_table, refresh=False)

        self.line_table.blockSignals(False)

    def calc_distance(self):
        """
        Calculate the distance between the two rows of GPS points and sets the LCD to this number.
        :return: None
        """
        def get_row_gps(row):
            east_col = self.line_table_columns.index('Easting')
            north_col = self.line_table_columns.index('Northing')
            try:
                easting = float(self.line_table.item(row, east_col).text())
            except ValueError as e:
                logger.error(f"{e}.")
                easting = None
            try:
                northing = float(self.line_table.item(row, north_col).text())
            except ValueError as e:
                logger.error(f"{e}.")
                northing = None
            if easting and northing:
                return float(easting), float(northing)
            else:
                return None

        selected_rows = self.get_selected_rows(self.line_table)
        if len(selected_rows) > 1:
            min_row, max_row = min(selected_rows), max(selected_rows)
            first_point = get_row_gps(min_row)
            second_point = get_row_gps(max_row)
            if first_point and second_point:
                distance = math.sqrt((first_point[0] - second_point[0]) ** 2 + (first_point[1] - second_point[1]) ** 2)
                self.lcdDistance.display(f'{distance:.1f}')
                self.setToolTip(f'{distance:.1f}')
            else:
                self.lcdDistance.display(0)
        else:
            self.lcdDistance.display(0)

    @staticmethod
    def get_selected_rows(table):
        """
        Return the rows that are currently selected from a given table.
        :param table: QTableWidget table.
        :return: List of rows that are selected.
        """
        return [model.row() for model in table.selectionModel().selectedRows()]

    def get_loop(self):
        """
        Create a TransmitterLoop object using the information in the loop_table
        :return: TransmitterLoop object
        """
        gps = []
        for row in range(self.loop_table.rowCount()):
            gps_row = list()
            for col in range(self.loop_table.columnCount()):
                v = self.loop_table.item(row, col).text()
                if v == '':
                    v = np.nan
                gps_row.append(v)
            gps.append(gps_row)
        return TransmitterLoop(gps)

    def get_line(self):
        """
        Create a SurveyLine object using the information in the line_table
        :return: SurveyLine object
        """
        gps = []
        for row in range(self.line_table.rowCount()):
            gps_row = list()
            for col in range(self.line_table.columnCount()):
                v = self.line_table.item(row, col).text()
                if v == '':
                    v = np.nan
                gps_row.append(v)
            gps.append(gps_row)
        return SurveyLine(gps)

    def get_collar(self):
        """
        Create a BoreholeCollar object from the information in the collar_table
        :return: BoreholeCollar object
        """
        gps = []
        for row in range(self.collar_table.rowCount()):
            gps_row = list()
            for col in range(self.collar_table.columnCount()):
                v = self.collar_table.item(row, col).text()
                if v == '':
                    v = np.nan
                gps_row.append(v)
            gps.append(gps_row)
        return BoreholeCollar(gps)

    def get_segments(self):
        """
        Create a BoreholeSegments object using the information in the segments_table
        :return: BoreholeSegments object
        """
        gps = []
        for row in range(self.segments_table.rowCount()):
            gps_row = list()
            for col in range(self.segments_table.columnCount()):
                v = self.segments_table.item(row, col).text()
                if v == '':
                    v = np.nan
                gps_row.append(v)
            gps.append(gps_row)
        return BoreholeSegments(gps)

    def get_geometry(self):
        """
        Create a BoreholeGeometry object from the information in the collar_table and segments_table
        :return: BoreholeGeometry object
        """
        return BoreholeGeometry(self.get_collar(), self.get_segments())

    def gps_object_changed(self, table, refresh=False):
        """
        Update the PEMFile's GPS object when it is modified in the table
        :param table: QTableWidget table
        :param refresh: bool, if the signal for the parent to refresh the PEMFile should be emitted. Should be false
        the GPS object isn't losing or gaining any rows.
        """
        print(f"Table changed.")
        if table == self.loop_table:
            self.pem_file.loop = self.get_loop()

        elif table == self.line_table:
            self.pem_file.line = self.get_line()

        elif table == self.collar_table:
            self.pem_file.collar = self.get_collar()

        elif table == self.segments_table:
            self.pem_file.segments = self.get_segments()

        else:
            logger.error(f"{table} is not a valid PIW table.")
            return

        if refresh:
            self.refresh_row_signal.emit()


class FloatDelegate(QItemDelegate):
    def __init__(self, decimals, parent=None):
        QItemDelegate.__init__(self, parent=parent)
        self.nDecimals = decimals

    def paint(self, painter, option, index):
        value = index.model().data(index, QtCore.Qt.EditRole)
        # if index in [0, 1]:
        try:
            number = float(value)
            painter.drawText(option.rect, QtCore.Qt.AlignCenter, f"{number:.{self.nDecimals}f}")
        except Exception:
            QItemDelegate.paint(self, painter, option, index)
        # else:
        #     QItemDelegate.paint(self, painter, option, index)
