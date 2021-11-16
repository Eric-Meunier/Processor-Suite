import logging
import math
import os
import sys
import copy
from collections import OrderedDict
from pathlib import Path

import numpy as np
import pandas as pd
from PySide2.QtCore import Qt, Signal, QEvent
from PySide2.QtGui import QColor, QFont, QBrush
from PySide2.QtWidgets import (QMessageBox, QWidget, QAction, QErrorMessage,
                               QFileDialog, QApplication, QHeaderView, QTableWidgetItem, QItemDelegate)

from src.gps.gps_editor import TransmitterLoop, SurveyLine, BoreholeCollar, BoreholeSegments, BoreholeGeometry, read_gps
from src.pem import convert_station
from src.qt_py import clear_table, table_to_df, df_to_table, get_line_color, get_icon
from src.qt_py.gps_tools import LoopAdder, LineAdder, CollarPicker, ExcelTablePicker
from src.qt_py.pem_geometry import PEMGeometry
from src.qt_py.ri_importer import RIFile
from src.ui.pem_info_widget import Ui_PEMInfoWidget

logger = logging.getLogger(__name__)

refs = []


class PEMFileInfoWidget(QWidget, Ui_PEMInfoWidget):
    refresh_row_signal = Signal()  # Send a signal to PEMEditor to refresh its main table.

    share_loop_signal = Signal(object)
    share_line_signal = Signal(object)
    share_collar_signal = Signal(object)
    share_segments_signal = Signal(object)

    def __init__(self, parent=None, darkmode=False):
        super().__init__()
        self.setupUi(self)
        self.parent = parent
        self.darkmode = darkmode

        self.blue_color = QColor(get_line_color("blue", "mpl", self.darkmode, alpha=255))
        self.red_color = QColor(get_line_color("red", "mpl", self.darkmode, alpha=255))
        self.single_red_color = QColor(get_line_color("single_red", "mpl", self.darkmode, alpha=255))
        self.gray_color = QColor(get_line_color("gray", "mpl", self.darkmode, alpha=255))
        self.foreground_color = QColor(get_line_color("foreground", "mpl", self.darkmode, alpha=255))
        self.background_color = QColor(get_line_color("background", "mpl", self.darkmode, alpha=255))

        self.pem_file = None
        self.ri_file = None
        self.selected_row_info = None
        self.active_table = None

        self.ri_editor = RIFile()
        self.dialog = QFileDialog()
        self.error = QErrorMessage()
        self.message = QMessageBox()
        self.picker = None
        self.line_adder = None
        self.loop_adder = None

        self.last_stn_gps_shift_amt = 0
        self.last_loop_elev_shift_amt = 0
        self.last_stn_shift_amt = 0

        self.installEventFilter(self)
        self.loop_table.installEventFilter(self)
        self.line_table.installEventFilter(self)
        self.collar_table.installEventFilter(self)
        self.segments_table.installEventFilter(self)
        self.ri_table.installEventFilter(self)
        self.loop_table.setFocusPolicy(Qt.StrongFocus)
        self.line_table.setFocusPolicy(Qt.StrongFocus)
        self.collar_table.setFocusPolicy(Qt.StrongFocus)
        self.segments_table.setFocusPolicy(Qt.StrongFocus)
        self.ri_table.setFocusPolicy(Qt.StrongFocus)

        self.line_table_columns = [self.line_table.horizontalHeaderItem(i).text() for i in range(
            self.line_table.columnCount())]
        self.loop_table_columns = [self.loop_table.horizontalHeaderItem(i).text() for i in range(
            self.loop_table.columnCount())]
        self.station_column = self.line_table_columns.index('Station')

        self.missing_gps_frame.hide()
        self.extra_gps_frame.hide()

        # Actions
        self.loop_table.remove_row_action = QAction("&Remove", self)
        self.addAction(self.loop_table.remove_row_action)
        self.loop_table.remove_row_action.setShortcut('Del')
        self.loop_table.remove_row_action.setEnabled(False)

        self.line_table.remove_row_action = QAction("&Remove", self)
        self.addAction(self.line_table.remove_row_action)
        self.line_table.remove_row_action.setShortcut('Del')
        self.line_table.remove_row_action.setEnabled(False)

        self.collar_table.remove_row_action = QAction("&Remove", self)
        self.addAction(self.collar_table.remove_row_action)
        self.collar_table.remove_row_action.setShortcut('Del')
        self.collar_table.remove_row_action.setEnabled(False)

        self.segments_table.remove_row_action = QAction("&Remove", self)
        self.addAction(self.segments_table.remove_row_action)
        self.segments_table.remove_row_action.setShortcut('Del')
        self.segments_table.remove_row_action.setEnabled(False)

        self.ri_table.remove_ri_file_action = QAction("&Remove RI File", self)
        self.addAction(self.ri_table.remove_ri_file_action)
        self.ri_table.remove_ri_file_action.setStatusTip("Remove the RI file")
        self.ri_table.remove_ri_file_action.setShortcut('Shift+Del')
        self.ri_table.remove_ri_file_action.setEnabled(False)

        self.init_ui()
        self.init_signals()

    def init_ui(self):
        self.cullStationGPSButton.setIcon(get_icon("remove"))
        self.stations_from_data_btn.setIcon(get_icon("add_square"))

        self.open_station_gps_btn.setIcon(get_icon("open"))
        self.open_loop_gps_btn.setIcon(get_icon("open"))
        self.open_collar_gps_btn.setIcon(get_icon("open"))
        self.add_segments_btn.setIcon(get_icon("open"))

        self.export_station_gps_btn.setIcon(get_icon("export"))
        self.export_loop_gps_btn.setIcon(get_icon("export"))
        self.export_collar_gps_btn.setIcon(get_icon("export"))
        self.export_segments_btn.setIcon(get_icon("export"))

        self.view_loop_btn.setIcon(get_icon("view"))
        self.view_line_btn.setIcon(get_icon("view"))

        self.share_loop_gps_btn.setIcon(get_icon("share_gps"))
        self.share_line_gps_btn.setIcon(get_icon("share_gps"))
        self.share_collar_gps_btn.setIcon(get_icon("share_gps"))
        self.share_segments_btn.setIcon(get_icon("share_gps"))

    def init_signals(self):
        def reverse_loop():
            loop_df = table_to_df(self.loop_table)
            if loop_df.empty:
                return

            reversed_loop_df = loop_df.iloc[::-1]
            self.fill_gps_table(reversed_loop_df, self.loop_table)
            self.gps_object_changed(self.loop_table, refresh=False)

        # Buttons
        self.cullStationGPSButton.clicked.connect(self.remove_extra_gps)

        self.flip_station_numbers_button.clicked.connect(self.reverse_station_gps_order)
        self.flip_station_signs_button.clicked.connect(self.flip_station_gps_polarity)
        self.stations_from_data_btn.clicked.connect(self.generate_station_names)

        self.open_station_gps_btn.clicked.connect(self.open_gps_file_dialog)
        self.open_loop_gps_btn.clicked.connect(self.open_gps_file_dialog)
        self.open_collar_gps_btn.clicked.connect(self.open_gps_file_dialog)
        self.add_segments_btn.clicked.connect(self.open_pem_geometry)

        self.export_station_gps_btn.clicked.connect(lambda: self.export_gps('station'))
        self.export_loop_gps_btn.clicked.connect(lambda: self.export_gps('loop'))
        self.export_collar_gps_btn.clicked.connect(lambda: self.export_gps('collar'))
        self.export_segments_btn.clicked.connect(lambda: self.export_gps('segments'))

        self.reverse_loop_btn.clicked.connect(reverse_loop)
        self.view_loop_btn.clicked.connect(lambda: self.add_loop(loop_content=self.get_loop()))
        self.view_line_btn.clicked.connect(lambda: self.add_line(line_content=self.get_line()))

        self.share_loop_gps_btn.clicked.connect(lambda: self.share_loop_signal.emit(self.get_loop()))
        self.share_line_gps_btn.clicked.connect(lambda: self.share_line_signal.emit(self.get_line()))
        self.share_collar_gps_btn.clicked.connect(lambda: self.share_collar_signal.emit(self.get_collar()))
        self.share_segments_btn.clicked.connect(lambda: self.share_segments_signal.emit(self.get_segments()))

        # Table changes
        self.line_table.cellChanged.connect(self.update_line_gps)
        self.line_table.cellChanged.connect(lambda: self.gps_object_changed(self.line_table, refresh=True))
        self.line_table.itemSelectionChanged.connect(self.calc_distance)
        self.line_table.itemSelectionChanged.connect(lambda: self.reset_spinbox(self.shiftStationGPSSpinbox))

        self.loop_table.itemSelectionChanged.connect(lambda: self.reset_spinbox(self.shift_elevation_spinbox))
        self.loop_table.cellChanged.connect(lambda: self.gps_object_changed(self.loop_table, refresh=True))

        self.collar_table.cellChanged.connect(lambda: self.gps_object_changed(self.collar_table, refresh=True))

        # Spinboxes
        self.shiftStationGPSSpinbox.valueChanged.connect(self.shift_gps_station_numbers)
        self.shift_elevation_spinbox.valueChanged.connect(self.shift_loop_elevation)

        # Actions
        self.loop_table.remove_row_action.triggered.connect(lambda: self.remove_table_row(self.loop_table))
        self.loop_table.remove_row_action.triggered.connect(lambda:
                                                            self.view_loop_btn.setEnabled(
                                                                True if self.loop_table.rowCount() > 0 else False))

        self.line_table.remove_row_action.triggered.connect(lambda: self.remove_table_row(self.line_table))
        self.line_table.remove_row_action.triggered.connect(lambda:
                                                            self.view_line_btn.setEnabled(
                                                                True if self.line_table.rowCount() > 0 else False))

        self.collar_table.remove_row_action.triggered.connect(lambda: self.remove_table_row(self.collar_table))

        self.segments_table.remove_row_action.triggered.connect(lambda: self.remove_table_row(self.segments_table))

        self.ri_table.remove_ri_file_action.triggered.connect(self.remove_ri_file)

    def init_tables(self):
        """
        Adds the columns and formats each table.
        :return: None
        """
        float_delegate = QItemDelegate()  # Must keep this reference or else it is garbage collected
        self.loop_table.setItemDelegate(float_delegate)
        self.line_table.setItemDelegate(float_delegate)
        self.collar_table.setItemDelegate(float_delegate)

        self.loop_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.line_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.collar_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.segments_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        if not self.pem_file.is_borehole():
            self.tabs.removeTab(self.tabs.indexOf(self.geometry_tab))
        else:
            self.tabs.removeTab(self.tabs.indexOf(self.station_gps_tab))

    def eventFilter(self, source, event):
        if event.type() == QEvent.Close:
            event.accept()
            self.deleteLater()

        if source is self.line_table:  # Makes the 'Del' shortcut work when the table is in focus
            if event.type() == QEvent.FocusIn:
                self.line_table.remove_row_action.setEnabled(True)
            elif event.type() == QEvent.FocusOut:
                self.line_table.remove_row_action.setEnabled(False)
            elif event.type() == QEvent.KeyPress:
                if event.key() == Qt.Key_Escape:
                    self.line_table.clearSelection()
                    return True

        elif source is self.loop_table:
            if event.type() == QEvent.FocusIn:
                self.loop_table.remove_row_action.setEnabled(True)
            elif event.type() == QEvent.FocusOut:
                self.loop_table.remove_row_action.setEnabled(False)
            elif event.type() == QEvent.KeyPress:
                if event.key() == Qt.Key_Escape:
                    self.loop_table.clearSelection()
                    return True

        elif source is self.collar_table:
            if event.type() == QEvent.FocusIn:
                self.collar_table.remove_row_action.setEnabled(True)
            elif event.type() == QEvent.FocusOut:
                self.collar_table.remove_row_action.setEnabled(False)
            elif event.type() == QEvent.KeyPress:
                if event.key() == Qt.Key_Escape:
                    self.collar_table.clearSelection()
                    return True

        elif source is self.segments_table:
            if event.type() == QEvent.FocusIn:
                self.segments_table.remove_row_action.setEnabled(True)
            elif event.type() == QEvent.FocusOut:
                self.segments_table.remove_row_action.setEnabled(False)
            elif event.type() == QEvent.KeyPress:
                if event.key() == Qt.Key_Escape:
                    self.segments_table.clearSelection()
                    return True

        elif source is self.ri_table:
            if event.type() == QEvent.FocusIn:
                self.ri_table.remove_ri_file_action.setEnabled(True)
            elif event.type() == QEvent.FocusOut:
                self.ri_table.remove_ri_file_action.setEnabled(False)
            elif event.type() == QEvent.KeyPress:
                if event.key() == Qt.Key_Escape:
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

    def open_pem_file(self, pem_file, refresh=False):
        """
        Action of opening a PEM file.
        :param pem_file: PEMFile object.
        :param refresh: bool, don't re-initialize the tables if refreshing the PEM file.
        """
        self.pem_file = pem_file

        if refresh is False:
            self.init_tables()  # Fixes it crashing when changing a value in any of the tables.

        if self.pem_file.is_borehole():
            self.fill_gps_table(self.pem_file.get_collar_gps(), self.collar_table)
            self.fill_gps_table(self.pem_file.get_segments(), self.segments_table)
        else:
            self.fill_gps_table(self.pem_file.get_line_gps(), self.line_table)
        self.fill_info_tab()
        self.fill_gps_table(self.pem_file.get_loop_gps(), self.loop_table)

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
                    item.setTextAlignment(Qt.AlignCenter)
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
        default_path = str(self.pem_file.parent)
        files = self.dialog.getOpenFileNames(self, 'Open GPS File(s)', default_path,
                                             filter='TXT files (*.txt);; CSV files (*.csv);; '
                                                    'GPX files (*.gpx);; All files(*.*)')[0]
        if not files:
            return

        self.open_gps_files(files)

    def open_gps_files(self, files):
        """
        Open GPS files
        :param files: list or str, filepath(s) of GPS files
        """
        def merge_files(files, collar=False):
            """
            Merge contents of files into one data frame
            :param files: list of str, filepaths of text file or GPX files
            :param collar: bool, if the files are for a collar, which will return a dict if an Excel file is passed.
            :return: str
            """
            crs = None
            merged_file = pd.DataFrame()
            for file in files:
                contents, _, crs = read_gps(file)
                if collar is True:
                    return contents, crs

                merged_file = pd.concat([contents, merged_file])
            return merged_file, crs

        if not isinstance(files, list):
            files = [files]
        files = [Path(f) for f in files]

        current_tab = self.tabs.currentWidget()
        if current_tab == self.geometry_tab:
            file = files[0]  # Only accepts the first file for adding collars.
            self.add_collar(file)
            return

        try:
            gps_df, crs = merge_files(files, collar=bool(current_tab == self.geometry_tab))
        except Exception as e:
            self.message.critical(self, "Error opening GPS file", str(e))
            return

        # Add survey line GPS
        if current_tab == self.station_gps_tab:
            self.add_line(gps_df)

        # Add loop GPS
        elif current_tab == self.loop_gps_tab:
            self.add_loop(gps_df)

        else:
            pass

        return crs

    def open_pem_geometry(self):
        def accept_geometry(seg):
            self.pem_file.segments = seg
            self.refresh_row_signal.emit()

        if not self.pem_file.has_d7() and not self.pem_file.has_geometry():
            logger.error(f"PEM files must have D7 RAD tool objects or P tag geometry.")
            self.message.information(self, "Invalid File", f"The PEM file must have D7 RAD tool values and must have"
                                                           f"geometry information.")
            return

        pem_geometry = PEMGeometry(parent=self, darkmode=self.darkmode)
        refs.append(pem_geometry)
        pem_geometry.accepted_sig.connect(accept_geometry)
        pem_geometry.open(self.pem_file)

    def add_line(self, line_content=None):
        """
        Open the LineAdder and add the SurveyLine
        :param line_content: str or Path or pd DataFrame. If None is passed, will use what's in the self.line_table.
        """
        def line_accept_sig_wrapper(data):
            self.fill_gps_table(data, self.line_table)

        # global line_adder
        self.line_adder = LineAdder(self.pem_file, parent=self, darkmode=self.darkmode)
        self.line_adder.accept_sig.connect(line_accept_sig_wrapper)
        self.line_adder.accept_sig.connect(lambda: self.gps_object_changed(self.line_table, refresh=True))

        if line_content is None:
            line_content = self.get_line()

        try:
            line = SurveyLine(line_content)
            if line.df.empty:
                self.message.information(self, 'No GPS Found', f"{line.error_msg}.")
            else:
                self.line_adder.open(line)
        except Exception as e:
            logger.critical(str(e))
            self.error.showMessage(f"Error adding line: {str(e)}.")

    def add_loop(self, loop_content=None):
        """
        Open the LoopAdder and add the TransmitterLoop
        :param loop_content: str or Path or pd DataFrame. If None is passed, will use what's in the loop_table.
        """
        def loop_accept_sig_wrapper(data):
            self.fill_gps_table(data, self.loop_table)

        # global loop_adder
        self.loop_adder = LoopAdder(self.pem_file, parent=self, darkmode=self.darkmode)
        self.loop_adder.accept_sig.connect(loop_accept_sig_wrapper)
        self.loop_adder.accept_sig.connect(lambda: self.gps_object_changed(self.loop_table, refresh=True))

        if loop_content is None:
            loop_content = self.get_loop()

        # try:
        loop = TransmitterLoop(loop_content)
        if loop.df.empty:
            self.message.information(self, 'No GPS Found', f"{loop.error_msg}")
            return
        self.loop_adder.open(loop)
        # except Exception as e:
        #     logger.critical(f"{e}.")
        #     self.error.showMessage(f"Error adding loop: {str(e)}")

    def add_collar(self, file):
        """
        Open the CollarPicker (if needed) and add the collarGPS.
        :param file: filepath of text, excel/CSV file, or GPX file
        """
        def accept_collar(data):
            try:
                collar = BoreholeCollar(data)
                errors = collar.get_errors()
                if not errors.empty:
                    self.message.warning(self, 'Parsing Error',
                                         f"The following rows could not be parsed:\n\n{errors.to_string()}.")
                if collar.df.empty:
                    self.message.warning(self, 'No GPS Found', f"{collar.error_msg}")

                self.fill_gps_table(collar.df, self.collar_table)
                self.gps_object_changed(self.collar_table, refresh=True)
            except Exception as e:
                logger.critical(f"{e}.")
                self.error.showMessage(f"Error adding borehole collar: {str(e)}.")

        if isinstance(file, Path):
            if file.suffix in [".xlsx", ".xls", ".csv"]:
                self.picker = ExcelTablePicker(darkmode=self.darkmode)
                self.picker.open(file)
                self.picker.accept_sig.connect(accept_collar)
            else:
                self.picker = CollarPicker(self.pem_file, darkmode=self.darkmode)
                self.picker.open(file)
                self.picker.accept_sig.connect(accept_collar)
        else:
            print(F"add_color, non-file was passed.")  # Testing if this ever happens
            accept_collar(file)

    def fill_info_tab(self):
        """
        Adds all information from the header, tags, and notes into the info_table.
        :return: None
        """
        clear_table(self.info_table)
        bold_font = QFont()
        bold_font.setBold(True)
        f = self.pem_file

        info = OrderedDict(sorted({
            "Format": f.format,
            "Units": f.units,
            "Operator": f.operator,
            "Probes": [f"{key}: {value}" for key, value in zip(f.probes.keys(), f.probes.values())],
            "Current": f.current,
            "Loop_dimensions": f.loop_dimensions,
            "Client": f.client,
            "Grid": f.grid,
            "Line_name": f.line_name,
            "Loop_name": f.loop_name,
            "Date": f.date,
            "Survey_type": f.survey_type,
            "Convention": f.convention,
            "Sync": f.sync,
            "Timebase": f.timebase,
            "Ramp": f.ramp,
            "Number_of_channels": f"{f.number_of_channels} ({len(f.channel_times)})",
            "Number_of_readings": f"{f.number_of_readings} ({len(f.data)})",
            "Rx_number": f.rx_number,
            "Rx_software_version": f.rx_software_version,
            "Rx_software_version_date": f.rx_software_version_date,
            "Rx_file_name": f.rx_file_name,
            "Normalized": f.normalized,
            "Primary_field_value": f.primary_field_value,
            "Coil_area": f.coil_area,
            "Loop_polarity": f.loop_polarity,
            "Notes": f.notes,
            "Filepath": str(f.filepath),
            "CRS": f.crs.name if f.crs else None,
            "Prepped_for_rotation": f.prepped_for_rotation,
            "Legacy": f.legacy,
        }.items()))

        for key, value in info.items():
            key_item = QTableWidgetItem(key)
            key_item.setFont(bold_font)

            if key == "Probes" or key == "Notes":
                span_row = self.info_table.rowCount()
                for v in value:
                    row = self.info_table.rowCount()
                    self.info_table.insertRow(row)

                    value_item = QTableWidgetItem(str(v))
                    self.info_table.setItem(row, 1, value_item)

                self.info_table.setSpan(span_row, 0, len(value), 1)
                self.info_table.setItem(span_row, 0, key_item)

            else:
                row = self.info_table.rowCount()
                self.info_table.insertRow(row)

                value_item = QTableWidgetItem(str(value))

                self.info_table.setItem(row, 0, key_item)
                self.info_table.setItem(row, 1, value_item)

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
        if data.empty:
            return

        if table in [self.line_table, self.loop_table, self.collar_table]:
            data.loc[:, ["Easting", "Northing", "Elevation"]] = data.loc[:, ["Easting", "Northing", "Elevation"]].round(2)

        # Store vertical scroll bar position to be restored after
        slider_position = table.verticalScrollBar().sliderPosition()

        # data.reset_index(inplace=True)
        clear_table(table)
        table.blockSignals(True)  # Block signals after clearing table as clear_table() unblocks at the end.
        table.verticalHeader().show()

        df_to_table(data, table, set_role=True)

        if table == self.line_table:
            self.update_line_gps()

        # Restore scroll bar position
        table.verticalScrollBar().setSliderPosition(slider_position)

        table.blockSignals(False)

    def update_line_gps(self):
        """
        Add coloring to the table based on values, and add missing and extra GPS to their respective lists.
        :return: None
        """
        self.color_line_table()
        self.check_missing_gps()
        self.check_extra_gps()

    def color_line_table(self):
        """
        Colors the line_table rows, station number column, based on issues with the ordering of the station numbers.
        This is done by first creating a list of ordered numbers based on the first and last GPS station numbers,
        then comparing these values with the coinciding value in the table.
        :return: None
        """
        self.line_table.blockSignals(True)

        line_gps = self.get_line()
        stations = line_gps.df.Station.map(convert_station).to_list()
        warnings = line_gps.get_warnings(stations=self.pem_file.get_stations(converted=True, incl_deleted=False))
        duplicates = warnings.get("Duplicates")
        elevation_warnings = warnings.get("Elevation Warnings")
        sorted_stations = sorted(stations, reverse=bool(stations[0] > stations[-1]))
        elevation_column = self.line_table_columns.index("Elevation")

        for row in range(self.line_table.rowCount()):
            table_value = stations[row]
            sorted_value = sorted_stations[row]

            if row in duplicates.index:
                self.line_table.item(row, self.station_column).setForeground(self.single_red_color)

            if row in elevation_warnings.index:
                self.line_table.item(row, elevation_column).setForeground(self.single_red_color)
            else:
                # Can immediately reset colow for elevation since it isn't affected by anything else
                self.line_table.item(row, elevation_column).setForeground(QBrush())

            # Color sorting errors
            if table_value > sorted_value:
                # Only change the foreground color if it's not a duplicate, for better contrast
                if row not in duplicates.index:
                    self.line_table.item(row, self.station_column).setForeground(self.background_color)
                self.line_table.item(row, self.station_column).setBackground(self.blue_color)
            elif table_value < sorted_value:
                # Only change the foreground color if it's not a duplicate, for better contrast
                if row not in duplicates.index:
                    self.line_table.item(row, self.station_column).setForeground(self.background_color)
                self.line_table.item(row, self.station_column).setBackground(self.red_color)
            else:
                # Prevent duplicates to be reset
                if row not in duplicates.index:
                    self.line_table.item(row, self.station_column).setForeground(QBrush())  # Reset the background
                self.line_table.item(row, self.station_column).setBackground(QBrush())  # Reset the background

        self.line_table.blockSignals(False)

    def check_missing_gps(self):
        """
        Find stations that are in the EM data but aren't in the GPS. Missing GPS are added to the missing_gps_list.
        :return: None
        """
        assert not self.pem_file.is_borehole(), f"Missing GPS only applies to surface surveys."
        self.missing_gps_list.clear()
        warnings = self.get_line().get_warnings(stations=self.pem_file.get_stations(converted=True, incl_deleted=False))
        missing_gps = warnings.get("Missing GPS")

        if len(missing_gps) > 0:
            self.missing_gps_frame.show()
        else:
            self.missing_gps_frame.hide()
            return

        # Add the missing GPS stations to the missing_gps_list
        for station in missing_gps.to_numpy():
            self.missing_gps_list.addItem(str(station))

    def check_extra_gps(self):
        """
        Find GPS entries whose station number does not exist in the PEM file's EM data.
        :return: None
        """
        assert not self.pem_file.is_borehole(), f"Extra GPS only applies to surface surveys."
        self.extra_gps_list.clear()

        gps_stations = self.get_line().df.Station.map(convert_station).to_list()
        em_stations = self.pem_file.get_stations(converted=True, incl_deleted=False)
        extra_stations = [station for station in gps_stations if station not in em_stations]

        if len(extra_stations) > 0:
            self.extra_gps_frame.show()
        else:
            self.extra_gps_frame.hide()
            return

        # Add the extra GPS stations to the extra_gps_list
        for i, station in enumerate(extra_stations):
            self.extra_gps_list.addItem(str(station))

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
            self.update_line_gps()

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

    def remove_extra_gps(self):
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
            selected_path = self.dialog.getSaveFileName(self, 'Save File', default_path,
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
            selected_path = self.dialog.getSaveFileName(self, 'Save File', default_path,
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

        shift_amount = self.shiftStationGPSSpinbox.value()

        selected_rows = self.get_selected_rows(self.line_table)
        rows = range(self.line_table.rowCount()) if not selected_rows else selected_rows

        for row in rows:
            station = int(self.line_table.item(row, self.station_column).text())
            new_station = station + (shift_amount - self.last_stn_gps_shift_amt)
            self.line_table.item(row, self.station_column).setData(Qt.EditRole, new_station)

        self.last_stn_gps_shift_amt = shift_amount

        self.gps_object_changed(self.line_table, refresh=False)
        self.update_line_gps()
        self.line_table.blockSignals(False)

    def shift_loop_elevation(self):
        """
        Shift the loop GPS elevation from the selected rows of the LoopGPSTable. If no rows are currently selected,
        it will do the shift for the entire table.
        :return: None
        """
        self.loop_table.blockSignals(True)

        shift_amount = self.shift_elevation_spinbox.value()
        elevation_column = self.loop_table_columns.index('Elevation')
        selected_rows = self.get_selected_rows(self.loop_table)
        rows = range(self.loop_table.rowCount()) if not selected_rows else selected_rows

        for row in rows:
            elevation = float(self.loop_table.item(row, elevation_column).text())
            new_elevation = elevation + (shift_amount - self.last_loop_elev_shift_amt)
            self.loop_table.item(row, elevation_column).setData(Qt.EditRole, new_elevation)

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

        selected_rows = self.get_selected_rows(self.line_table)
        rows = range(self.line_table.rowCount()) if not selected_rows else selected_rows

        for row in rows:
            new_station = int(self.line_table.item(row, self.station_column).text())
            self.line_table.item(row, self.station_column).setData(Qt.EditRole, new_station * -1)

        self.gps_object_changed(self.line_table, refresh=True)
        self.update_line_gps()
        self.line_table.blockSignals(False)

    def reverse_station_gps_order(self):
        """
        Reverse the order of station numbers in the StationGPSTable.
        :return: None
        """
        self.line_table.blockSignals(True)

        selected_rows = self.get_selected_rows(self.line_table)
        rows = range(self.line_table.rowCount()) if not selected_rows else selected_rows
        stations = [int(self.line_table.item(row, self.station_column).text()) for row in rows]
        rev_stations = stations[::-1]

        for row, station in zip(rows, rev_stations):
            self.line_table.item(row, self.station_column).setData(Qt.EditRole, station)

        self.gps_object_changed(self.line_table, refresh=False)
        self.update_line_gps()
        self.line_table.blockSignals(False)

    def generate_station_names(self):
        """
        Fills the GPS station numbers in the StationGPSTable using the station numbers in the data.
        :return: None
        """
        self.line_table.blockSignals(True)

        data_stations = self.pem_file.get_stations(converted=True)
        for row, station in enumerate(data_stations):
            if row > self.line_table.rowCount():
                print(f"Line table row count reached. Breaking...")
                break
            # station must be cast as int, since the int32 that is default from the numpy array causes the values to be
            # empty in the table.
            self.line_table.item(row, self.station_column).setData(Qt.EditRole, int(station))

        self.gps_object_changed(self.line_table, refresh=True)
        self.update_line_gps()

        self.line_table.blockSignals(False)

    def calc_distance(self):
        """
        Calculate the distance between the two rows of GPS points and sets the LCD to this number.
        :return: None
        """
        def get_row_gps(row):
            east_col = self.line_table_columns.index('Easting')
            north_col = self.line_table_columns.index('Northing')
            easting = float(self.line_table.item(row, east_col).text())
            northing = float(self.line_table.item(row, north_col).text())
            return float(easting), float(northing)

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
        gps = table_to_df(self.loop_table, dtypes=float, nan_replacement=np.nan)

        self.share_loop_gps_btn.setEnabled(False if len(gps) == 0 else True)
        self.view_loop_btn.setEnabled(False if len(gps) == 0 else True)
        self.export_loop_gps_btn.setEnabled(False if len(gps) == 0 else True)
        self.reverse_loop_btn.setEnabled(False if len(gps) == 0 else True)
        self.shift_elevation_spinbox.setEnabled(False if len(gps) == 0 else True)

        return TransmitterLoop(gps)

    def get_line(self):
        """
        Create a SurveyLine object using the information in the line_table
        :return: SurveyLine object
        """
        gps = table_to_df(self.line_table, dtypes=float, nan_replacement=np.nan)

        self.view_line_btn.setEnabled(False if len(gps) == 0 else True)
        self.export_station_gps_btn.setEnabled(False if len(gps) == 0 else True)
        self.share_line_gps_btn.setEnabled(False if len(gps) == 0 else True)
        self.flip_station_signs_button.setEnabled(False if len(gps) == 0 else True)
        self.flip_station_numbers_button.setEnabled(False if len(gps) == 0 else True)
        self.stations_from_data_btn.setEnabled(False if len(gps) == 0 else True)
        self.cullStationGPSButton.setEnabled(False if len(gps) == 0 else True)
        self.shiftStationGPSSpinbox.setEnabled(False if len(gps) == 0 else True)

        return SurveyLine(gps)

    def get_collar(self):
        """
        Create a BoreholeCollar object from the information in the collar_table
        :return: BoreholeCollar object
        """
        gps = table_to_df(self.collar_table, nan_replacement=np.nan)
        # There's always a row for the collar, so disabling the buttons using len(gps) won't work.
        collar = BoreholeCollar(gps)

        self.export_collar_gps_btn.setEnabled(False if collar.df.empty else True)
        self.share_collar_gps_btn.setEnabled(False if collar.df.empty else True)

        return collar

    def get_segments(self):
        """
        Create a BoreholeSegments object using the information in the segments_table
        :return: BoreholeSegments object
        """
        gps = table_to_df(self.segments_table, dtypes=float, nan_replacement=np.nan)

        self.export_segments_btn.setEnabled(False if len(gps) == 0 else True)
        self.share_segments_btn.setEnabled(False if len(gps) == 0 else True)

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
        if table == self.loop_table:
            self.pem_file.loop = self.get_loop()

        elif table == self.line_table:
            self.pem_file.line = self.get_line()

        elif table == self.collar_table:
            self.pem_file.collar = self.get_collar()

        elif table == self.segments_table:
            self.pem_file.segments = self.get_segments()

        if refresh:
            self.refresh_row_signal.emit()


if __name__ == "__main__":
    from src.pem.pem_file import PEMGetter
    samples_folder = Path(__file__).parents[2].joinpath('sample_files')
    app = QApplication(sys.argv)

    pem_file = PEMGetter().parse(samples_folder.joinpath(r"GPX files\Loop L\RAW\100E.PEM"))
    # file1 = samples_folder.joinpath(r"GPX files\100E_0601.gpx")
    # file2 = samples_folder.joinpath(r"GPX files\100E_0604.gpx")
    file = r"C:\_Data\2021\Trevali Peru\Borehole\_SAN-0251-21\GPS\SAN-0251-21.xlsx"

    win = PEMFileInfoWidget()
    win.tabs.setCurrentIndex(3)
    win.open_pem_file(pem_file)
    # win.open_gps_files([file1, file2])
    win.open_gps_files(file)
    # cp = CollarPicker(None)
    # cp.show()

    app.exec_()
