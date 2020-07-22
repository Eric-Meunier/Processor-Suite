import os
import re
import sys
from collections import OrderedDict
from copy import deepcopy

import math
import natsort
import numpy as np
import pandas as pd
from PyQt5 import (QtCore, QtGui, uic)
from PyQt5.QtWidgets import (QWidget, QTableWidgetItem, QAction, QMenu, QInputDialog, QMessageBox,
                             QFileDialog, QErrorMessage, QHeaderView)

from src.gps.gps_editor import TransmitterLoop, SurveyLine, BoreholeCollar, BoreholeSegments, BoreholeGeometry
from src.pem._legacy.pem_file_editor import PEMFileEditor
from src.qt_py.ri_importer import RIFile
from src.qt_py.gps_adder import LoopAdder, LineAdder

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

sys._excepthook = sys.excepthook


def exception_hook(exctype, value, traceback):
    print(exctype, value, traceback)
    sys._excepthook(exctype, value, traceback)
    sys.exit(1)


sys.excepthook = exception_hook


def convert_station(station):
    """
    Converts a single station name into a number, negative if the stations was S or W
    :return: Integer station number
    """
    if re.match(r"\d+(S|W)", station):
        station = (-int(re.sub(r"[SW]", "", station.upper())))
    else:
        station = (int(re.sub(r"[EN]", "", station.upper())))
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
        self.loop_adder = LoopAdder(parent=self)
        self.loop_adder.write_widget = self
        self.line_adder = LineAdder(parent=self)
        self.line_adder.write_widget = self

        self.last_stn_gps_shift_amt = 0
        self.last_loop_elev_shift_amt = 0
        self.last_stn_shift_amt = 0
        self.num_repeat_stations = 0
        self.suffix_warnings = 0

        self.line_table_columns = ['Easting', 'Northing', 'Elevation', 'Units', 'Station']
        self.loop_table_columns = ['Easting', 'Northing', 'Elevation', 'Units']
        self.data_table_columns = ['index', 'Station', 'Comp.', 'Reading_index', 'Reading_number', 'Number_of_stacks', 'ZTS']

        self.setupUi(self)
        self.init_actions()
        self.init_signals()

    def init_actions(self):
        self.loop_table.installEventFilter(self)
        self.line_table.installEventFilter(self)
        self.collar_table.installEventFilter(self)
        self.segments_table.installEventFilter(self)
        self.data_table.installEventFilter(self)
        self.ri_table.installEventFilter(self)
        self.loop_table.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.line_table.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.collar_table.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.segments_table.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.data_table.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.ri_table.setFocusPolicy(QtCore.Qt.StrongFocus)

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

        self.data_table.remove_data_row_action = QAction("&Remove", self)
        self.addAction(self.data_table.remove_data_row_action)
        self.data_table.remove_data_row_action.triggered.connect(self.remove_data_row)
        self.data_table.remove_data_row_action.setShortcut('Del')
        self.data_table.remove_data_row_action.setEnabled(False)

        self.data_table.reverse_polarity_action = QAction("&Reverse Polarity", self)
        self.data_table.reverse_polarity_action.triggered.connect(self.reverse_polarity)

        self.ri_table.remove_ri_file_action = QAction("&Remove RI File", self)
        self.addAction(self.ri_table.remove_ri_file_action)
        self.ri_table.remove_ri_file_action.triggered.connect(self.remove_ri_file)
        self.ri_table.remove_ri_file_action.setStatusTip("Remove the RI file")
        self.ri_table.remove_ri_file_action.setShortcut('Shift+Del')
        self.ri_table.remove_ri_file_action.setEnabled(False)

    def init_signals(self):
        # Buttons
        self.cullStationGPSButton.clicked.connect(self.cull_station_gps)
        self.changeStationSuffixButton.clicked.connect(self.change_station_suffix)
        self.changeComponentButton.clicked.connect(self.change_component)

        self.flip_station_numbers_button.clicked.connect(self.reverse_station_gps_numbers)
        self.flip_station_signs_button.clicked.connect(self.flip_station_gps_polarity)
        self.stations_from_data_btn.clicked.connect(self.stations_from_data)
        self.reversePolarityButton.clicked.connect(self.reverse_polarity)
        self.rename_repeat_stations_btn.clicked.connect(self.rename_repeat_stations)

        self.export_station_gps_btn.clicked.connect(lambda: self.export_gps('station'))
        self.export_loop_gps_btn.clicked.connect(lambda: self.export_gps('loop'))

        self.edit_loop_btn.clicked.connect(lambda:
                                           self.loop_adder.open(
                                               self.get_loop().get_loop(
                                                   sorted=self.parent.auto_sort_loops_cbox.isChecked(),
                                                   closed=True)))
        self.edit_line_btn.clicked.connect(lambda:
                                           self.line_adder.open(
                                               self.get_line().get_line(
                                                   sorted=self.parent.auto_sort_stations_cbox.isChecked())))

        # Radio buttons
        self.station_sort_rbtn.clicked.connect(self.fill_data_table)
        self.component_sort_rbtn.clicked.connect(self.fill_data_table)
        self.reading_num_sort_rbtn.clicked.connect(self.fill_data_table)

        # Table changes
        self.line_table.cellChanged.connect(self.check_station_duplicates)
        self.line_table.cellChanged.connect(self.color_line_table)
        self.line_table.cellChanged.connect(self.check_missing_gps)
        self.line_table.itemSelectionChanged.connect(self.calc_distance)
        self.line_table.itemSelectionChanged.connect(lambda: self.reset_spinbox(self.shiftStationGPSSpinbox))

        self.loop_table.itemSelectionChanged.connect(lambda: self.reset_spinbox(self.shift_elevation_spinbox))

        self.data_table.itemSelectionChanged.connect(lambda: self.reset_spinbox(self.shiftStationSpinbox))
        self.data_table.itemSelectionChanged.connect(self.toggle_change_station_btn)
        self.data_table.cellChanged.connect(self.update_pem_from_table)

        # Spinboxes
        self.shiftStationGPSSpinbox.valueChanged.connect(self.shift_gps_station_numbers)
        self.shift_elevation_spinbox.valueChanged.connect(self.shift_loop_elevation)
        self.shiftStationSpinbox.valueChanged.connect(self.shift_station_numbers)

    def toggle_change_station_btn(self):
        selected_rows = self.get_selected_rows(self.data_table)
        if selected_rows:
            self.changeStationSuffixButton.setEnabled(True)
        else:
            self.changeStationSuffixButton.setEnabled(False)

    def init_tables(self):
        """
        Adds the columns and formats each table.
        :return: None
        """
        if not self.pem_file.is_borehole():
            self.tabs.removeTab(self.tabs.indexOf(self.geometry_tab))
            self.line_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        elif self.pem_file.is_borehole():
            self.tabs.removeTab(self.tabs.indexOf(self.station_gps_tab))
            self.segments_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            self.collar_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        self.loop_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.data_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.data_table.setColumnHidden(0, True)

    def contextMenuEvent(self, event):
        if self.line_table.underMouse():
            if self.line_table.selectionModel().selectedIndexes():
                self.line_table.menu = QMenu(self.line_table)
                self.line_table.menu.addAction(self.line_table.remove_row_action)
                self.line_table.menu.popup(QtGui.QCursor.pos())
                self.line_table.remove_row_action.setEnabled(True)
            else:
                pass
        elif self.loop_table.underMouse():
            if self.loop_table.selectionModel().selectedIndexes():
                self.loop_table.menu = QMenu(self.loop_table)
                self.loop_table.menu.addAction(self.loop_table.remove_row_action)
                self.loop_table.menu.addAction(self.loop_table.move_row_up_action)
                self.loop_table.menu.addAction(self.loop_table.move_row_down_action)
                self.loop_table.menu.popup(QtGui.QCursor.pos())
                self.loop_table.remove_row_action.setEnabled(True)
            else:
                pass
        elif self.collar_table.underMouse():
            if self.collar_table.selectionModel().selectedIndexes():
                self.collar_table.menu = QMenu(self.collar_table)
                self.collar_table.menu.addAction(self.collar_table.remove_row_action)
                self.collar_table.menu.popup(QtGui.QCursor.pos())
                self.collar_table.remove_row_action.setEnabled(True)
            else:
                pass
        elif self.segments_table.underMouse():
            if self.segments_table.selectionModel().selectedIndexes():
                self.segments_table.menu = QMenu(self.segments_table)
                self.segments_table.menu.addAction(self.segments_table.remove_row_action)
                self.segments_table.menu.popup(QtGui.QCursor.pos())
                self.segments_table.remove_row_action.setEnabled(True)
        elif self.data_table.underMouse():
            if self.data_table.selectionModel().selectedIndexes():
                self.data_table.menu = QMenu(self.data_table)
                self.data_table.menu.addAction(self.data_table.reverse_polarity_action)
                self.data_table.menu.addSeparator()
                self.data_table.menu.addAction(self.data_table.remove_data_row_action)
                self.data_table.menu.popup(QtGui.QCursor.pos())
                self.data_table.remove_data_row_action.setEnabled(True)
                # self.data_table.remove_row_action.setEnabled(True)
            else:
                pass
        elif self.ri_table.underMouse():
            if self.ri_table.selectionModel().selectedIndexes():
                self.ri_table.menu = QMenu(self.ri_table)
                self.ri_table.menu.addAction(self.ri_table.remove_ri_file_action)
                self.ri_table.menu.popup(QtGui.QCursor.pos())
                self.ri_table.remove_ri_file_action.setEnabled(True)
        else:
            pass

    def eventFilter(self, source, event):
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
        elif source is self.data_table:
            if event.type() == QtCore.QEvent.KeyPress:
                if event.key() == QtCore.Qt.Key_F and event.modifiers() == QtCore.Qt.ShiftModifier:
                    self.reverse_polarity()
                    return True
                elif event.key() == QtCore.Qt.Key_C and event.modifiers() == QtCore.Qt.ShiftModifier:
                    self.change_component()
                    return True
                elif event.key() == QtCore.Qt.Key_Escape:
                    self.data_table.clearSelection()
                    return True
            elif event.type() == QtCore.QEvent.FocusIn:
                self.data_table.remove_data_row_action.setEnabled(True)
            elif event.type() == QtCore.QEvent.FocusOut:
                self.data_table.remove_data_row_action.setEnabled(False)
        elif source is self.ri_table:
            if event.type() == QtCore.QEvent.Wheel:
                # TODO Make sideways scrolling work correctly. Won't scroll sideways without also going vertically
                if event.modifiers() == QtCore.Qt.ShiftModifier:
                    pos = self.ri_table.horizontalScrollBar().value()
                    if event.angleDelta().y() < 0:  # Wheel moved down so scroll to the right
                        self.ri_table.horizontalScrollBar().setValue(pos + 2)
                    else:
                        self.ri_table.horizontalScrollBar().setValue(pos - 2)
                    return True
            elif event.type() == QtCore.QEvent.FocusIn:
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

    def open_file(self, pem_file, parent):
        """
        Action of opening a PEM file.
        :param pem_file: PEMFile object.
        :param parent: parent widget (PEMEditor)
        :return: PEMFileInfoWidget object
        """
        print(f'PEMFileInfoWidget - Opening PEM File {pem_file.filepath.name}')
        self.pem_file = pem_file
        self.parent = parent
        self.init_tables()
        if self.pem_file.is_borehole():
            self.fill_gps_table(self.pem_file.geometry.get_collar(), self.collar_table)
            self.fill_gps_table(self.pem_file.geometry.get_segments(), self.segments_table)
        else:
            self.fill_gps_table(self.pem_file.line.get_line(sorted=self.parent.auto_sort_stations_cbox.isChecked()),
                                self.line_table)
        self.fill_info_tab()
        self.fill_gps_table(self.pem_file.loop.get_loop(sorted=self.parent.auto_sort_loops_cbox.isChecked()),
                            self.loop_table)
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
            self.ri_table.setColumnCount(len(columns))
            self.ri_table.setHorizontalHeaderLabels(columns)

        def fill_ri_table():
            self.clear_table(self.ri_table)

            for i, row in enumerate(self.ri_file.data):
                row_pos = self.ri_table.rowCount()
                self.ri_table.insertRow(row_pos)
                items = [QTableWidgetItem(row[key]) for key in self.ri_file.columns]

                for m, item in enumerate(items):
                    item.setTextAlignment(QtCore.Qt.AlignCenter)
                    self.ri_table.setItem(row_pos, m, item)

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

    def clear_table(self, table):
        """
        Clear a given table
        """
        table.blockSignals(True)
        while table.rowCount() > 0:
            table.removeRow(0)
        table.blockSignals(False)

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
            # Add a new row to the table
            row_pos = table.rowCount()
            table.insertRow(row_pos)

            items = df_row.map(lambda x: QTableWidgetItem(str(x))).to_list()
            # Format each item of the table to be centered
            for m, item in enumerate(items):
                item.setTextAlignment(QtCore.Qt.AlignCenter)
                table.setItem(row_pos, m, item)

        data = deepcopy(data)
        if data.empty:
            return

        # data.reset_index(inplace=True)
        self.clear_table(table)
        table.blockSignals(True)

        if table == self.loop_table:
            self.edit_loop_btn.setEnabled(True)
            table.verticalHeader().show()
        elif table == self.line_table:
            self.edit_line_btn.setEnabled(True)
            table.verticalHeader().show()
        elif table == self.segments_table:
            table.verticalHeader().show()
        #     tags = [f"<L{n:02}>" for n in range(len(data.index))]
        # elif table == self.segments_table:
        #     tags = [f"<P{n + 1:02}>" for n in range(len(data.index))]
        # else:
        #     tags = [f"<P{n:02}>" for n in range(len(data.index))]
        #
        # data.insert(0, 'Tag', tags)
        data.apply(lambda x: write_row(x, table), axis=1)

        if table == self.line_table:
            self.check_station_duplicates()
            self.color_line_table()
            self.check_missing_gps()
        # table.resizeColumnsToContents()
        table.blockSignals(False)

    def fill_data_table(self):
        """
        Fill the data_table with given PEMFile data
        :param data: PEMFile data
        """

        def get_sorted_data():
            """
            Returns the sorted data in the PEMFile
            :return: PEMFile Data data frame
            """
            data = self.pem_file.data

            if self.station_sort_rbtn.isChecked():
                data = data.reindex(index=natsort.order_by_index(
                    data.index, natsort.index_natsorted(zip(data.Station, data.Component, data['Reading_number']))))
                # data.reset_index(drop=True, inplace=True)

            elif self.component_sort_rbtn.isChecked():
                data = data.reindex(index=natsort.order_by_index(
                    data.index, natsort.index_natsorted(zip(data.Component, data.Station, data['Reading_number']))))
                # data.reset_index(drop=True, inplace=True)

            elif self.reading_num_sort_rbtn.isChecked():
                data = data.reindex(index=natsort.order_by_index(
                    data.index, natsort.index_natsorted(zip(data['Reading_number'], data['Reading_index']))))
                # data.reset_index(drop=True, inplace=True)

            return data

        def write_data_row(df_row):
            # Add a new row to the table
            row_pos = self.data_table.rowCount()
            self.data_table.insertRow(row_pos)

            items = df_row.map(lambda x: QTableWidgetItem(str(x))).to_list()
            items.insert(0, QTableWidgetItem(str(df_row.name)))
            # Format each item of the table to be centered
            for m, item in enumerate(items):
                item.setTextAlignment(QtCore.Qt.AlignCenter)
                self.data_table.setItem(row_pos, m, item)

        data = get_sorted_data()
        if data.empty:
            return
        else:
            self.clear_table(self.data_table)
            self.data_table.blockSignals(True)

            data.loc[:, ['Station', 'Component', 'Reading_index', 'Reading_number', 'Number_of_stacks', 'ZTS']].apply(
                write_data_row, axis=1)

            self.color_data_table()
            self.data_table.resizeColumnsToContents()
            self.data_table.blockSignals(False)

    def color_data_table(self):
        """
        Colors the rows and cells of the data_table based on several criteria.
        :return: None
        """

        def color_rows_by_component():
            """
            Color the rows in data_table by component
            """

            def color_row(row, color):
                for col in range(self.data_table.columnCount()):
                    item = self.data_table.item(row, col)
                    item.setBackground(color)

            z_color = QtGui.QColor('cyan')
            z_color.setAlpha(50)
            x_color = QtGui.QColor('magenta')
            x_color.setAlpha(50)
            y_color = QtGui.QColor('yellow')
            y_color.setAlpha(50)
            white_color = QtGui.QColor('white')
            for row in range(self.data_table.rowCount()):
                item = self.data_table.item(row, self.data_table_columns.index('Comp.'))
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
            Color the data_table rows where the station suffix is different from the mode
            """

            if not self.pem_file.is_borehole():
                correct_suffix = self.pem_file.data.Station.map(lambda x: re.findall('[NSEW]', x.upper())).mode().to_list()
                while not isinstance(correct_suffix, str):
                    correct_suffix = correct_suffix[0]
                count = 0
                for row in range(self.data_table.rowCount()):
                    item = self.data_table.item(row, self.data_table_columns.index('Station'))
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
            for row in range(self.data_table.rowCount()):
                item = self.data_table.item(row, self.data_table_columns.index('Station'))
                if item:
                    station_num = re.findall('\d+', item.text())
                    if station_num:
                        station_num = station_num[0]
                        if station_num[-1] == '1' or station_num[-1] == '4' or station_num[-1] == '6' or station_num[-1] == '9':
                            repeats += 1
                            item.setFont(boldFont)
                        else:
                            item.setFont(normalFont)
                    else:
                        break
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

    def color_line_table(self):
        """
        Colors the line_table rows, station number column, based on issues with the ordering of the station numbers.
        This is done by first creating a list of ordered numbers based on the first and last GPS station numbers,
        then comparing these values with the coinciding value in the table.
        :return: None
        """
        self.line_table.blockSignals(True)
        stations = self.get_line().df.Station.map(convert_station).to_list()
        sorted_stations = sorted(stations, reverse=bool(stations[0] > stations[-1]))

        blue_color, red_color = QtGui.QColor('blue'), QtGui.QColor('red')
        blue_color.setAlpha(50)
        red_color.setAlpha(50)
        station_col = self.line_table_columns.index('Station')

        for row in range(self.line_table.rowCount()):
            if self.line_table.item(row, station_col) and stations[row] > sorted_stations[row]:
                self.line_table.item(row, station_col).setBackground(blue_color)
            elif self.line_table.item(row, station_col) and stations[row] < sorted_stations[row]:
                self.line_table.item(row, station_col).setBackground(red_color)
            else:
                self.line_table.item(row, station_col).setBackground(QtGui.QColor('white'))
        self.line_table.blockSignals(False)

    def check_missing_gps(self):
        """
        Find stations that are in the Data but aren't in the GPS. Missing GPS are added to the missing_gps_table.
        :return: None
        """
        self.clear_table(self.missing_gps_table)
        data_stations = self.pem_file.get_stations(converted=True)
        gps_stations = self.get_line().df.Station.astype(int).unique()
        filt = np.isin(data_stations, gps_stations, invert=True)
        missing_gps = data_stations[filt]

        # Add the missing GPS stations to the missing_gps_table
        for i, station in enumerate(missing_gps):
            self.missing_gps_table.insertRow(i)
            item = QTableWidgetItem(str(station))
            item.setTextAlignment(QtCore.Qt.AlignCenter)
            item.setForeground(QtGui.QColor('red'))
            self.missing_gps_table.setItem(i, 0, item)

    def update_pem_from_table(self, table_row, table_col):
        """
        Signal slot: Update the pem file using the values in the data_table.
        :param table_row: event row
        :param table_col: event column
        """
        self.data_table.blockSignals(True)
        data = self.pem_file.data
        df_col = self.data_table_columns[table_col]
        df_row = int(self.data_table.item(table_row, self.data_table_columns.index('index')).text())

        table_value = self.data_table.item(table_row, table_col).text()
        data.loc[df_row, df_col] = table_value

        self.pem_file.data = data
        self.color_data_table()
        self.data_table.blockSignals(False)

    def remove_table_row(self, table):
        """
        Remove a selected row from a given table
        :param table: QTableWidget table. Either the loop, station, or geometry tables. Not data_table and not collarGPS table.
        :return: None
        """
        def add_tags():
            """
            Re-numbers the tags so no numbers are skipped due to the deleted row
            :return:
            """
            if table == self.loop_table:
                tag = 'L'
            else:
                tag = 'P'
            for row in range(table.rowCount()):
                offset = 1 if table == self.segments_table else 0
                tag_item = QTableWidgetItem("<" + tag + '{num:02d}'.format(num=row + offset) + ">")
                tag_item.setTextAlignment(QtCore.Qt.AlignCenter)
                table.setItem(row, 0, tag_item)

        if table == self.data_table or table == self.collar_table:
            return

        selected_rows = self.get_selected_rows(table)
        for row in reversed(selected_rows):
            table.removeRow(row)

        if table == self.line_table:
            self.check_station_duplicates()
            self.check_missing_gps()
            # add_tags()
        # elif table == self.loop_table:
            # add_tags()
        self.refresh_tables_signal.emit()

    def remove_data_row(self):
        """
        Remove a row from the data table.
        :return: None
        """
        selected_rows = self.get_selected_rows(self.data_table)

        for row in reversed(selected_rows):
            # Find the data frame index of the selected row
            ind = int(self.data_table.item(row, self.data_table_columns.index('index')).text())
            self.pem_file.data.drop(index=ind, axis=1, inplace=True)
            self.data_table.removeRow(row)
        self.data_table.blockSignals(True)
        self.color_data_table()
        self.data_table.blockSignals(False)

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
    #     rows = self.get_selected_rows(self.loop_table)
    #     loop_gps = self.get_loop()
    #
    #     for row in rows:
    #         removed_row = loop_gps.pop(row)
    #         loop_gps.insert(row-1, removed_row)
    #
    #     self.fill_loop_table(loop_gps)
    #     self.loop_table.setSelectionMode(QtGui.QAbstractItemView.MultiSelection)
    #     [self.loop_table.selectRow(row-1) for row in rows]
    #     self.loop_table.setSelectionMode(QtGui.QAbstractItemView.ExtendedSelection)
    #
    # def move_table_row_down(self):
    #     """
    #     Move selected rows of the LoopGPSTable down.
    #     :return: None
    #     """
    #     rows = self.get_selected_rows(self.loop_table)
    #     loop_gps = self.get_loop()
    #
    #     for row in rows:
    #         removed_row = loop_gps.pop(row)
    #         loop_gps.insert(row + 1, removed_row)
    #
    #     self.fill_loop_table(loop_gps)
    #     self.loop_table.setSelectionMode(QtGui.QAbstractItemView.MultiSelection)
    #     [self.loop_table.selectRow(row + 1) for row in rows]
    #     self.loop_table.setSelectionMode(QtGui.QAbstractItemView.ExtendedSelection)
    #
    # def toggle_loop_move_buttons(self):
    #     """
    #     Slot: Enables or disables the loopGPS arrow buttons whenever a row in the table is selected or de-selected.
    #     :return: None
    #     """
    #     if self.loop_table.selectionModel().selectedRows():
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
                print(f"{station} cannot be converted to Int")
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
        self.line_table.blockSignals(False)

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

    def shift_station_numbers(self):
        """
        Shift the data station number.
        :return: None
        """
        shift_amount = self.shiftStationSpinbox.value()

        def apply_shift(station, shift_value):
            # Isolate the numbers only
            station_num = re.search('\d+', station).group(0)
            try:
                station_num = int(station_num)
            except ValueError:
                return station
            else:
                # Apply the shift to the number and then replace the numbers in the original station with the new number
                new_value = str(station_num - shift_value)
                return re.sub('\d+', new_value, station)

        # Find the corresponding data frame rows
        df_rows = self.get_df_rows()
        stations = self.pem_file.data.loc[df_rows, 'Station']
        stations = stations.map(lambda x: apply_shift(x, self.last_stn_shift_amt - shift_amount))

        self.pem_file.data.loc[df_rows, 'Station'] = stations
        self.fill_data_table()
        # self.data_table.resizeColumnsToContents()
        self.last_stn_shift_amt = shift_amount

    def flip_station_gps_polarity(self):
        """
        Multiplies the station number of the selected rows of the StationGPSTable by -1. If no rows are selected it will
        do so for all rows.
        :return: None
        """
        self.line_table.blockSignals(True)

        def flip_stn_num(row):
            station_column = 5
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

    def reverse_polarity(self, component=None):
        """
        Reverse the polarity of selected readings
        :param selected_rows: Selected rows from the data_table to be changed. If none is selected, it will reverse
        the polarity for all rows.
        :param component: Selected component to be changed. If none is selected, it will reverse the polarity for
        all rows.
        :return: None
        """
        self.line_table.blockSignals(True)

        df_rows = self.get_df_rows()

        if component:
            rows = self.pem_file.data['Component'] == component
            print(f'Reversing data polarity for {component} component')
            self.window().statusBar().showMessage(f'Reversing data polarity for {component} component', 2000)
        else:
            rows = df_rows
            print(f'Reversing data polarity for {len(rows)} rows')
            self.window().statusBar().showMessage(f'Reversing data polarity for {len(rows)} rows', 2000)

        self.pem_file.data.loc[rows, 'Reading'] = self.pem_file.data.loc[rows, 'Reading'].map(lambda x: x * -1)

        # Add the HE tag as a note in the PEM file, or remove it if it was there previously
        if component and component in self.pem_file.get_components():
            note = f"<HE3> {component.upper()} component polarity reversed"
            if note not in self.pem_file.notes:
                self.pem_file.notes.append(note)
            else:
                self.pem_file.notes.remove(note)

        self.fill_data_table()
        self.data_table.resizeColumnsToContents()

        self.line_table.blockSignals(False)

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
        else:
            pass

    def stations_from_data(self):
        """
        Fills the GPS station numbers in the StationGPSTable using the station numbers in the data.
        :return: None
        """
        data_stations = self.pem_file.get_stations(converted=True)
        for row, station in enumerate(data_stations):
            item = QTableWidgetItem(str(station))
            item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.line_table.setItem(row, self.line_table_columns.index('Station'), item)

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
            except ValueError:
                easting = None
            try:
                northing = float(self.line_table.item(row, north_col).text())
            except ValueError:
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
            else:
                self.lcdDistance.display(0)
        else:
            self.lcdDistance.display(0)

    def change_station_suffix(self):
        """
        Change the suffix letter from the station number for selected rows in the data_table. Only for surface files.
        Input suffix must be either N, S, E, or W, case doesn't matter.
        :return: None
        """
        if self.pem_file.is_borehole():  # Shouldn't be needed since the button is disabled for boreholes
            return

        suffix, okPressed = QInputDialog.getText(self, "Change Station Suffix", "New Suffix:")
        if okPressed and suffix.upper() in ['N', 'E', 'S', 'W']:
            df_rows = self.get_df_rows()
            stations = self.pem_file.data.loc[df_rows, 'Station']
            stations = stations.map(lambda x: re.sub('[NESW]', suffix.upper(), x))

            self.pem_file.data.loc[df_rows, 'Station'] = stations
            self.fill_data_table()

        elif okPressed:
            self.message.information(self, 'Invalid Suffix', 'Suffix must be one of [NSEW]')

    def change_component(self):
        """
        Change the component of selected readings based on user input
        :return: None
        """
        new_comp, okPressed = QInputDialog.getText(self, "Change Component", "New Component:")
        if okPressed and new_comp.upper() in ['Z', 'X', 'Y']:
            df_rows = self.get_df_rows()
            components = self.pem_file.data.loc[df_rows, 'Component']
            components = components.map(lambda x: new_comp)

            self.pem_file.data.loc[df_rows, 'Component'] = components
            self.fill_data_table()
        elif okPressed:
            self.message.information(self, 'Invalid Component', 'Component must be one of [Z, X, Y]')

    def rename_repeat_stations(self):
        """
        Change any station name in the data_table that is a repeat station
        (i.e. any station ending in 1,4,6,9 to 0,5,5,0 respectively).
        :return: None
        """
        def rename_repeat(station):
            """
            Applies the appropriate change to the station number
            :param station: str, station number
            :return: str, station number with number changed
            """
            station_num = int(re.findall('-?\d+', station)[0])
            if str(station_num)[-1] in ['1', '4', '6', '9']:
                if str(station_num)[-1] == '1' or str(station_num)[-1] == '6':
                    print(f"station {station_num} changed to {station_num-1}")
                    station_num -= 1
                elif str(station_num)[-1] == '4' or str(station_num)[-1] == '9':
                    print(f"station {station_num} changed to {station_num + 1}")
                    station_num += 1
                station = re.sub('\d+', str(station_num), station)
            return station

        if self.num_repeat_stations > 0:
            self.pem_file.data.Station = self.pem_file.data.Station.map(rename_repeat)
            self.fill_data_table()
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

    def get_df_rows(self):
        rows = self.get_selected_rows(self.data_table)
        if not rows:
            rows = range(self.data_table.rowCount())

        df_rows = [int(self.data_table.item(row, self.data_table_columns.index('index')).text()) for row in rows]
        return df_rows

    def get_loop(self):
        """
        Create a TransmitterLoop object using the information in the loop_table
        :return: TransmitterLoop object
        """
        gps = {
            'Easting': [],
            'Northing': [],
            'Elevation': [],
            'Unit': [],
        }
        for row in range(self.loop_table.rowCount()):
            gps['Easting'].append(self.loop_table.item(row, 0).text())
            gps['Northing'].append(self.loop_table.item(row, 1).text())
            gps['Elevation'].append(self.loop_table.item(row, 2).text())
            gps['Unit'].append(self.loop_table.item(row, 3).text())
        return TransmitterLoop(pd.DataFrame(gps))

    def get_line(self):
        """
        Create a SurveyLine object using the information in the line_table
        :return: SurveyLine object
        """
        gps = {
            'Easting': [],
            'Northing': [],
            'Elevation': [],
            'Unit': [],
            'Station': []
        }
        for row in range(self.line_table.rowCount()):
            gps['Easting'].append(self.line_table.item(row, 0).text())
            gps['Northing'].append(self.line_table.item(row, 1).text())
            gps['Elevation'].append(self.line_table.item(row, 2).text())
            gps['Unit'].append(self.line_table.item(row, 3).text())
            gps['Station'].append(self.line_table.item(row, 4).text())
        return SurveyLine(pd.DataFrame(gps))

    def get_collar(self):
        """
        Create a BoreholeCollar object from the information in the collar_table
        :return: BoreholeCollar object
        """
        gps = {
            'Easting': [],
            'Northing': [],
            'Elevation': [],
            'Unit': []
        }
        for row in range(self.collar_table.rowCount()):
            gps['Easting'].append(self.collar_table.item(row, 0).text())
            gps['Northing'].append(self.collar_table.item(row, 1).text())
            gps['Elevation'].append(self.collar_table.item(row, 2).text())
            gps['Unit'].append(self.collar_table.item(row, 3).text())
        return BoreholeCollar(pd.DataFrame(gps))

    def get_segments(self):
        """
        Create a BoreholeSegments object using the information in the segments_table
        :return: BoreholeSegments object
        """
        gps = {
            'Azimuth': [],
            'Dip': [],
            'Segment length': [],
            'Unit': [],
            'Depth': []
        }
        for row in range(self.segments_table.rowCount()):
            gps['Azimuth'].append(self.segments_table.item(row, 0).text())
            gps['Dip'].append(self.segments_table.item(row, 1).text())
            gps['Segment length'].append(self.segments_table.item(row, 2).text())
            gps['Unit'].append(self.segments_table.item(row, 3).text())
            gps['Depth'].append(self.segments_table.item(row, 4).text())

        return BoreholeSegments(pd.DataFrame(gps))

    def get_geometry(self):
        """
        Create a BoreholeGeometry object from the information in the collar_table and segments_table
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

        default_path = self.pem_file.filepath.parent
        selected_path = self.dialog.getSaveFileName(self, 'Save File', directory=default_path,
                                                    filter='Text files (*.txt);; CSV files (*.csv);; All files(*.*)')
        if selected_path[0]:
            if selected_path[0].endswith('txt'):
                gps_str = gps.to_string()
            elif selected_path[0].endswith('csv'):
                gps_str = gps.to_csv()
            else:
                self.message.information(self, 'Invalid file type', f"Selected file type is invalid. Must be either"
                f"'txt' or 'csv'")
                return

            with open(selected_path[0], 'w+') as file:
                file.write(gps_str)
            os.startfile(selected_path[0])
        else:
            self.window().statusBar().showMessage('Cancelled.', 2000)

