import copy
import csv
import datetime
import keyboard
import logging
import natsort
import os
import re
import shutil
import simplekml
import stopit
import subprocess
import sys
import warnings
from itertools import groupby
from pathlib import Path

import numpy as np
import pandas as pd
import pyqtgraph as pg
from PySide2.QtGui import QIcon, QColor, QFont, QIntValidator, QCursor
from PySide2.QtCore import Qt, QDir, Signal, QEvent, QTimer, QSettings, QSize, QPoint
from PySide2.QtWebEngineWidgets import QWebEngineView
from PySide2.QtWidgets import (QMainWindow, QMessageBox, QGridLayout, QWidget, QMenu, QAction, QErrorMessage,
                               QFileDialog, QVBoxLayout, QLabel, QApplication, QFrame, QHBoxLayout, QLineEdit,
                               QCalendarWidget, QFileSystemModel, QDoubleSpinBox, QHeaderView, QInputDialog, QTableWidgetItem, QGroupBox, QFormLayout, QTextBrowser, QDialogButtonBox,
                               QTableWidget, QShortcut, QSizePolicy, QPushButton, QComboBox, QListWidgetItem,
                               QAbstractItemView, QCheckBox)
from matplotlib import pyplot as plt
from matplotlib.colors import LinearSegmentedColormap as LCMap
import matplotlib.cbook
from pyproj import CRS

from src import __version__, app_data_dir
from src.qt_py import (icons_path, get_extension_icon, get_icon, CustomProgressDialog, read_file, light_palette,
                       dark_palette, get_line_color)
from src.qt_py.db_plot import DBPlotter
from src.qt_py.pem_geometry import PEMGeometry
from src.gps.gps_editor import (SurveyLine, TransmitterLoop, BoreholeCollar, BoreholeSegments, BoreholeGeometry)
from src.qt_py.gpx_creator import GPXCreator
from src.qt_py.loop_calculator import LoopCalculator
from src.qt_py.mag_dec_widget import MagDeclinationCalculator
from src.pem.pem_file import PEMFile, PEMParser, DMPParser
from src.pem.pem_plotter import PEMPrinter
from src.qt_py.gps_conversion import GPSConversionWidget
from src.dxf.pem_dxf import PEMDXFDrawing
from src.qt_py.derotator import Derotator
from src.qt_py.extractor_widgets import StationSplitter
from src.qt_py.map_widgets import Map3DViewer, ContourMapViewer, TileMapViewer, GPSViewer
from src.qt_py.pem_info_widget import PEMFileInfoWidget
from src.qt_py.pem_merger import PEMMerger
from src.qt_py.pem_planner import LoopPlanner, GridPlanner
from src.qt_py.pem_plot_editor import PEMPlotEditor
from src.qt_py.ri_importer import BatchRIImporter
from src.qt_py.unpacker import Unpacker
from src.ui.pdf_plot_printer import Ui_PDFPlotPrinter
from src.ui.pem_hub import Ui_PEMHub
from src.ui.plan_map_options import Ui_PlanMapOptions

logger = logging.getLogger(__name__)

# TODO Add quick view to unpacker? Or separate EXE entirely?
# TODO Look into slowness when changing station number and such in pem plot editor
# TODO Move progress dialog or error box when there's an error.
# TODO create large PDF with summary of file, including 3d map.
# TODO Hybrid PEMGeometry selection
# TODO Plot some profile channels on plan map
# TODO Log recently opened files.
# TODO Add GPS errors to table

# Keep a list of widgets so they don't get garbage collected
refs = []

pg.setConfigOptions(antialias=True)
pg.setConfigOption('crashWarning', True)
warnings.filterwarnings("ignore",category=matplotlib.cbook.mplDeprecation)  # Ignore MatplotlibDeprecationWarning


class PEMHub(QMainWindow, Ui_PEMHub):

    def __init__(self, app, parent=None, splash_screen=None):
        super().__init__()

        def init_ui():
            if splash_screen:
                splash_screen.showMessage("Initializing UI")
            self.setupUi(self)
            self.app.setStyle("Fusion")
            self.setAcceptDrops(True)

            self.setWindowTitle("PEMPro  v" + str(__version__))
            self.setWindowIcon(get_icon('conder.png'))

            self.table.horizontalHeader().hide()

            # Set icons
            self.actionOpenFile.setIcon(get_icon("open.png"))
            self.actionSaveFiles.setIcon(get_icon("save.png"))
            self.menuExport_Files.setIcon(get_icon("export.png"))
            self.actionPrint_Plots_to_PDF.setIcon(get_icon("pdf.png"))

            self.actionAverage_All_PEM_Files.setIcon(get_icon("average.png"))
            self.actionSplit_All_PEM_Files.setIcon(get_icon("split.png"))
            self.actionScale_All_Currents.setIcon(get_icon("current.png"))
            self.actionChange_All_Coil_Areas.setIcon(get_icon("coil.png"))
            self.menuReverse_Polarity.setIcon(get_icon("reverse.png"))

            self.actionSave_as_KMZ.setIcon(get_icon("google_earth.png"))
            self.actionExport_All_GPS.setIcon(get_icon("csv.png"))
            self.actionConvert_GPS.setIcon(get_icon("convert_gps.png"))

            self.actionQuick_Map.setIcon(get_icon("gps_viewer.png"))
            self.actionTile_Map.setIcon(get_icon("folium.png"))
            self.actionContour_Map.setIcon(get_icon("contour_map.png"))
            self.action3D_Map.setIcon(get_icon("3d_map.png"))
            self.actionGoogle_Earth.setIcon(get_icon("google_earth.png"))
            self.actionMake_DXF.setIcon(get_icon("dxf.png"))

            self.actionUnpacker.setIcon(get_icon("unpacker.png"))
            self.actionDamping_Box_Plotter.setIcon(get_icon("db_plot.png"))
            self.actionLoop_Planner.setIcon(get_icon("loop_planner.png"))
            self.actionGrid_Planner.setIcon(get_icon("grid_planner.png"))
            self.actionLoop_Current_Calculator.setIcon(get_icon("voltmeter.png"))
            self.actionNRCan_Declination_Calculator.setIcon(get_icon("canada.png"))
            self.actionConvert_Timebase_Frequency.setIcon(get_icon("freq_timebase_calc.png"))
            self.actionGPX_Creator.setIcon(get_icon("garmin_file.png"))

            self.actionSave_Settings.setIcon(get_icon("save.png"))
            self.actionReset_Settings.setIcon(get_icon("undo.png"))
            self.actionView_Logs.setIcon(get_icon("txt_file.png"))

            self.refresh_pem_list_btn.setIcon(get_icon("refresh.png"))
            self.filter_pem_list_btn.setIcon(get_icon("filter.png"))
            self.add_pem_btn.setIcon(get_icon("add_square.png"))
            self.remove_pem_btn.setIcon(get_icon("remove.png"))
            self.refresh_gps_list_btn.setIcon(get_icon("refresh.png"))
            self.filter_gps_list_btn.setIcon(get_icon("filter.png"))
            self.add_gps_btn.setIcon(get_icon("add_square.png"))
            self.remove_gps_btn.setIcon(get_icon("remove.png"))

        def init_actions():
            def share_gps(obj_str):
                """
                Helper function to run self.open_gps_share
                :param obj_str: str, either 'loop', 'line', 'collar', or 'segments'
                """
                piw_widget = self.pem_info_widgets[self.table.currentRow()]
                if obj_str == 'loop':
                    gps_obj = piw_widget.get_loop()
                elif obj_str == 'line':
                    gps_obj = piw_widget.get_line()
                elif obj_str == 'collar':
                    gps_obj = piw_widget.get_collar()
                elif obj_str == 'segments':
                    gps_obj = piw_widget.get_segments()
                else:
                    gps_obj = 'all'

                self.open_gps_share(gps_obj, piw_widget)

            if splash_screen:
                splash_screen.showMessage("Initializing actions")

            self.actionDel_File.setShortcut("Del")
            self.actionDel_File.triggered.connect(self.remove_pem_file)
            self.addAction(self.actionDel_File)
            self.actionDel_File.setEnabled(False)

            # Remove, open, and save PEM files
            self.remove_file_action.triggered.connect(self.remove_pem_file)
            self.remove_file_action.setIcon(get_icon('remove.png'))
            self.open_file_action.triggered.connect(self.open_in_text_editor)
            self.open_file_action.setIcon(get_icon('txt_file.png'))
            self.save_file_action.setIcon(get_icon('save.png'))
            self.save_file_action.triggered.connect(lambda: self.save_pem_files(selected=True))
            self.save_file_as_action.setIcon(get_icon('save_as.png'))
            self.save_file_as_action.triggered.connect(self.save_pem_file_as)
            self.copy_to_cliboard_action.setIcon(get_icon('copy.png'))
            self.copy_to_cliboard_action.triggered.connect(self.copy_pems_to_clipboard)

            # Exports
            self.export_pem_action.setIcon(get_icon('crone_logo.png'))
            self.export_pem_action.triggered.connect(lambda: self.export_pem_files(selected=True, processed=False))
            self.export_dad_action.triggered.connect(self.export_dad)
            self.export_gps_action.triggered.connect(lambda: self.export_gps(selected=True))

            # View channel table
            self.action_view_channels.setIcon(get_icon("table.png"))
            self.action_view_channels.triggered.connect(self.open_channel_table_viewer)

            # Merge PEM files
            self.merge_action.setIcon(get_icon('pem_merger.png'))
            self.merge_action.triggered.connect(self.open_pem_merger)

            # Print PDFs
            self.print_plots_action.setIcon(get_icon('pdf.png'))
            self.print_plots_action.triggered.connect(lambda: self.open_pdf_plot_printer(selected=True))

            # Extract stations
            self.extract_stations_action.triggered.connect(self.open_station_splitter)

            self.extract_x_action.triggered.connect(lambda: self.extract_component("X"))
            self.extract_y_action.triggered.connect(lambda: self.extract_component("Y"))
            self.extract_z_action.triggered.connect(lambda: self.extract_component("Z"))

            # Magnetic declination calculator
            self.calc_mag_dec_action.setIcon(get_icon('mag_field.png'))
            self.calc_mag_dec_action.triggered.connect(self.open_mag_dec)

            # View GPS
            self.view_loop_action.triggered.connect(lambda: self.pem_info_widgets[self.table.currentRow()].add_loop())
            self.view_line_action.triggered.connect(lambda: self.pem_info_widgets[self.table.currentRow()].add_line())

            # Share GPS
            self.share_loop_action.triggered.connect(lambda: share_gps('loop'))
            self.share_line_action.triggered.connect(lambda: share_gps('line'))
            self.share_collar_action.triggered.connect(lambda: share_gps('collar'))
            self.share_segments_action.triggered.connect(lambda: share_gps('segments'))
            self.share_all_action.triggered.connect(lambda: share_gps('all'))

            # Plot editor
            self.open_plot_editor_action.triggered.connect(self.open_pem_plot_editor)
            self.open_plot_editor_action.setIcon(get_icon('plot_editor.png'))

            # Quick Map
            self.open_quick_map_action.triggered.connect(lambda: self.open_quick_map(selected=True))
            self.open_quick_map_action.setIcon(get_icon('gps_viewer.png'))

            # Data editing/processing
            self.average_action.triggered.connect(lambda: self.average_pem_data(selected=True))
            self.average_action.setIcon(get_icon('average.png'))
            self.split_action.triggered.connect(lambda: self.split_pem_channels(selected=True))
            self.split_action.setIcon(get_icon('split.png'))
            self.scale_current_action.triggered.connect(lambda: self.scale_pem_current(selected=True))
            self.scale_current_action.setIcon(get_icon('current.png'))
            self.scale_ca_action.triggered.connect(lambda: self.scale_pem_coil_area(selected=True))
            self.scale_ca_action.setIcon(get_icon('coil.png'))
            # self.mag_offset_action = QAction("Mag Offset", self)
            # self.mag_offset_action.triggered.connect(lambda: self.mag_offset_lastchn(selected=True))

            # Reversing
            self.reverse_x_component_action.triggered.connect(
                lambda: self.reverse_component_data(comp='X', selected=True))
            self.reverse_y_component_action.triggered.connect(
                lambda: self.reverse_component_data(comp='Y', selected=True))
            self.reverse_z_component_action.triggered.connect(
                lambda: self.reverse_component_data(comp='Z', selected=True))

            self.reverse_station_order_action.triggered.connect(
                lambda: self.reverse_station_order(selected=True))

            # Derotation
            self.derotate_action.triggered.connect(self.open_derotator)
            self.derotate_action.setIcon(get_icon('derotate.png'))

            # Borehole geometry
            self.get_geometry_action.triggered.connect(self.open_pem_geometry)
            self.get_geometry_action.setIcon(get_icon('pem_geometry.png'))

            # Rename lines and files
            self.rename_lines_action.triggered.connect(lambda: self.open_name_editor('Line', selected=True))
            self.rename_files_action.triggered.connect(lambda: self.open_name_editor('File', selected=True))

            self.actionNRCan_Declination_Calculator.triggered.connect(self.open_nrcan_calculator)

        def init_signals():
            if splash_screen:
                splash_screen.showMessage("Initializing signals")

            def table_value_changed(row, col):
                """
                Signal Slot: Action taken when a value in the main table was changed.
                :param row: Row of the main table that the change was made.
                :param col: Column of the main table that the change was made.
                :return: None
                """
                self.table.blockSignals(True)
                pem_file = self.pem_files[row]
                value = self.table.item(row, col).text()

                # Rename a file when the 'File' column is changed
                if col == self.table_columns.index('File'):
                    old_path = pem_file.filepath
                    new_value = self.table.item(row, col).text()

                    if new_value:
                        new_path = old_path.parent.joinpath(new_value)
                        logger.info(f"Renaming {old_path.name} to {new_path.name}.")

                        try:
                            os.rename(str(old_path), str(new_path))
                        except Exception as e:
                            # Keep the old name if the new file name already exists
                            logger.error(f"{e}.")
                            self.message.critical(self, 'File Error', f"{e}.")
                            item = QTableWidgetItem(str(old_path.name))
                            item.setTextAlignment(Qt.AlignCenter)
                            self.table.setItem(row, col, item)
                        else:
                            pem_file.filepath = new_path
                            self.fill_pem_list()
                            self.status_bar.showMessage(f"{old_path.name} renamed to {str(new_value)}", 2000)

                elif col == self.table_columns.index('Date'):
                    pem_file.date = value

                elif col == self.table_columns.index('Client'):
                    pem_file.client = value

                elif col == self.table_columns.index('Grid'):
                    pem_file.grid = value

                elif col == self.table_columns.index('Line/Hole'):
                    pem_file.line_name = value

                elif col == self.table_columns.index('Loop'):
                    pem_file.loop_name = value

                elif col == self.table_columns.index('Current'):
                    try:
                        value = float(value)
                    except ValueError:
                        logger.error(f"{value} is not a number.")
                        self.message.critical(self, 'Invalid Value', f"Current must be a number")
                        self.add_pem_to_table(pem_file, row)
                    else:
                        pem_file.current = value

                elif col == self.table_columns.index('Coil\nArea'):
                    try:
                        float(value)
                    except ValueError:
                        logger.error(f"{value} is not a number.")
                        self.message.critical(self, 'Invalid Value', f"Coil area Must be a number")
                        self.add_pem_to_table(pem_file, row)
                    else:
                        pem_file.coil_area = value

                self.format_row(row)
                self.color_table_by_values()

                if self.allow_signals:
                    self.table.blockSignals(False)

            def cell_clicked(row, col):
                """
                Open the plot editor when a row is alt + clicked
                :param row: int, click cell's row
                :param col: int, click cell's column
                """
                update_selection_text()

                if self.actionAlt_Click_Plotting.isChecked():
                    if keyboard.is_pressed('alt'):
                        self.open_pem_plot_editor()

            def table_value_double_clicked(row, col):
                """
                When a cell is double clicked. Used for the date column only, to open a calender widget.
                :param row: int
                :param col: int
                """

                pem_file = self.pem_files[row]

                def accept_change(data):
                    """
                    Signal slot, update the station names of the PEM file.
                    :param data: pd.DataFrame of the data with the stations re-named.
                    """
                    pem_file.data = data
                    self.refresh_pem(pem_file)

                if col == self.table_columns.index('Date'):
                    self.calender.show()

                    # Create global variables to be used by set_date
                    global current_row, current_col
                    current_row, current_col = row, col

                elif col == self.table_columns.index('Suffix\nWarnings'):
                    if self.table.item(row, col).text() != '0' and not pem_file.is_borehole():

                        suffix_viewer = WarningViewer(pem_file, warning_type='suffix')
                        refs.append(suffix_viewer)
                        suffix_viewer.accept_sig.connect(accept_change)
                    else:
                        self.status_bar.showMessage(f"No suffix warnings to show.", 1000)

                elif col == self.table_columns.index('Repeat\nWarnings'):
                    if self.table.item(row, col).text() != '0':

                        repeat_viewer = WarningViewer(pem_file, warning_type='repeat')
                        refs.append(repeat_viewer)
                        repeat_viewer.accept_sig.connect(accept_change)
                    else:
                        self.status_bar.showMessage(f"No repeats to show.", 1000)

            def set_date(date):
                """
                Change the date in the selected PEM file to that of the calender widget
                :param date: QDate object from the calender widget
                """
                item = QTableWidgetItem(date.toString('MMMM dd, yyyy'))
                item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(current_row, current_col, item)

            def apply_header():
                """
                Update the header of each PEM file when the Apply button is clicked for the shared header.
                """
                if self.share_client_cbox.isChecked():
                    for row in range(self.table.rowCount()):
                        self.table.item(row, 2).setText(self.client_edit.text())

                if self.share_grid_cbox.isChecked():
                    for row in range(self.table.rowCount()):
                        self.table.item(row, 3).setText(self.grid_edit.text())

                if self.share_loop_cbox.isChecked():
                    for row in range(self.table.rowCount()):
                        self.table.item(row, 5).setText(self.loop_edit.text())

            def toggle_pem_list_buttons():
                """
                Signal slot, enable and disable the add/remove buttons tied to the PEM list based on whether any list items
                are currently selected.
                """
                if self.pem_list.selectedItems():
                    self.add_pem_btn.setEnabled(True)
                    self.remove_pem_btn.setEnabled(True)
                else:
                    self.add_pem_btn.setEnabled(False)
                    self.remove_pem_btn.setEnabled(False)

            def toggle_gps_list_buttons():
                """
                Signal slot, enable and disable the add/remove buttons tied to the GPS list based on whether any list items
                are currently selected.
                """
                if self.gps_list.selectedItems():
                    self.add_gps_btn.setEnabled(True)
                    self.remove_gps_btn.setEnabled(True)
                else:
                    self.add_gps_btn.setEnabled(False)
                    self.remove_gps_btn.setEnabled(False)

            def open_project_file(item):
                """
                Signal slot, open the file that was double clicked in the project tree.
                :param item: QListWidget item
                """
                os.startfile(str(self.get_current_project_path()))

            def open_list_file(item):
                """
                Signal slot, open the file that was double clicked in the PEM or GPS lists.
                :param item: QListWidget item
                """
                os.startfile(str(self.project_dir.joinpath(item.text())))

            def add_pem_list_files():
                """
                Signal slot, open the selected PEM files in to the PEM list
                """
                selected_files = [Path(self.project_dir, i.text()) for i in self.pem_list.selectedItems()]

                pem_filepaths = [j for j in selected_files if j.suffix.lower() == '.pem']
                dmp_filepaths = [k for k in selected_files if k.suffix.lower() in ['.dmp', '.dmp2', '.dmp3', '.dmp4']]

                self.add_dmp_files(dmp_filepaths)
                self.add_pem_files(pem_filepaths)

            def add_gps_list_files():
                """
                Signal slot, open the selected GPS files in to the GPS list
                """
                selected_files = [Path(self.project_dir, i.text()) for i in self.gps_list.selectedItems()]
                self.add_gps_files(selected_files)

            def remove_pem_list_files():
                """
                Signal slot, delete selected PEM files.
                """
                response = self.message.question(self, "Confirm Delete", f"Delete selected PEM file(s)?",
                                                 self.message.Yes, self.message.No)
                if response == self.message.Yes:
                    selected_rows = [self.pem_list.row(i) for i in self.pem_list.selectedItems()]
                    for row in sorted(selected_rows, reverse=True):
                        print(f"Deleting {self.available_pems[row]}")
                        os.remove(self.available_pems[row])
                        self.pem_list.takeItem(row)
                        self.available_pems.pop(row)

            def remove_gps_list_files():
                """
                Signal slot, delete selected GPS files.
                """
                response = self.message.question(self, "Confirm Delete", f"Delete selected GPS file(s)?",
                                                 self.message.Yes, self.message.No)
                if response == self.message.Yes:
                    selected_rows = [self.gps_list.row(i) for i in self.gps_list.selectedItems()]
                    for row in sorted(selected_rows, reverse=True):
                        print(f"Deleting {self.available_gps[row]}")
                        os.remove(self.available_gps[row])
                        self.gps_list.takeItem(row)
                        self.available_gps.pop(row)

            def update_selection_text():
                """
                Change the information of the selected pem file(s) in the status bar
                """
                pem_files, rows = self.get_pem_files(selected=True)

                if not pem_files:
                    return

                if len(pem_files) == 1:
                    file = pem_files[0]
                    timebase = f"Timebase: {file.timebase}ms"
                    zts = f"ZTS: {', '.join(file.data.ZTS.unique().astype(int).astype(str))}"
                    survey_type = f"Survey Type: {file.get_survey_type()}"
                    if file.is_pp():
                        survey_type += " PP"

                    if file.is_borehole() and file.has_xy():
                        derotated = f"De-rotated: {file.is_derotated()}"
                    else:
                        derotated = ""
                else:
                    timebase = f"Timebase(s): {', '.join(natsort.os_sorted(np.unique([str(f.timebase) + 'ms' for f in pem_files])))}"
                    zts = f"ZTS: {', '.join(np.unique(np.concatenate([f.data.ZTS.unique().astype(int).astype(str) for f in pem_files])))}"
                    survey_type = f"Survey Type(s): {', '.join(np.unique([f.get_survey_type() for f in pem_files]))}"
                    derotated = ""

                self.selection_files_label.setText(f"Selected: {len(pem_files)}")
                self.selection_timebase_label.setText(timebase)
                self.selection_zts_label.setText(zts)
                self.selection_survey_label.setText(survey_type)
                self.selection_derotation_label.setText(derotated)

            def open_logs():
                log_file = app_data_dir.joinpath('logs.txt')
                if log_file.exists():
                    os.startfile(str(log_file))
                else:
                    self.message.critical(self, 'File Not Found', f"'{log_file}' file not found.")

            def add_mapbox_token():
                token, ok_pressed = QInputDialog.getText(self, "Mapbox Access Token", "Enter Mapbox Access Token:")
                if ok_pressed and token:
                    app_data_dir = Path(os.getenv('APPDATA')).joinpath("PEMPro")
                    token_file = open(str(app_data_dir.joinpath(".mapbox")), 'w+')
                    token_file.write(token)
                    token_file.close()
                    self.statusBar().showMessage("Mapbox token updated.", 1500)

            # Widgets
            self.pem_list_filter.accept_sig.connect(self.fill_pem_list)
            self.gps_list_filter.accept_sig.connect(self.fill_gps_list)
            self.calender.clicked.connect(set_date)

            # Buttons
            self.apply_shared_header_btn.clicked.connect(apply_header)
            self.filter_pem_list_btn.clicked.connect(self.pem_list_filter.show)
            self.filter_gps_list_btn.clicked.connect(self.gps_list_filter.show)

            # Table
            self.table.viewport().installEventFilter(self)
            self.table.installEventFilter(self)
            self.table.setFocusPolicy(Qt.StrongFocus)

            self.table.itemSelectionChanged.connect(lambda: self.stackedWidget.setCurrentIndex(self.table.currentRow()))
            self.table.itemSelectionChanged.connect(update_selection_text)
            self.table.cellChanged.connect(table_value_changed)
            self.table.cellClicked.connect(cell_clicked)
            self.table.cellDoubleClicked.connect(table_value_double_clicked)

            # Project Tree
            self.project_dir_edit.returnPressed.connect(self.set_project_dir)
            self.project_tree.clicked.connect(self.project_dir_changed)
            self.project_tree.doubleClicked.connect(open_project_file)

            self.refresh_pem_list_btn.clicked.connect(self.fill_pem_list)
            self.refresh_gps_list_btn.clicked.connect(self.fill_gps_list)

            self.pem_list.itemSelectionChanged.connect(toggle_pem_list_buttons)
            self.gps_list.itemSelectionChanged.connect(toggle_gps_list_buttons)
            self.pem_list.itemDoubleClicked.connect(open_list_file)
            self.gps_list.itemDoubleClicked.connect(open_list_file)

            self.add_pem_btn.clicked.connect(add_pem_list_files)
            self.add_gps_btn.clicked.connect(add_gps_list_files)
            self.remove_pem_btn.clicked.connect(remove_pem_list_files)
            self.remove_gps_btn.clicked.connect(remove_gps_list_files)

            # Project Panel
            self.share_client_cbox.stateChanged.connect(
                lambda: self.client_edit.setEnabled(self.share_client_cbox.isChecked()))
            self.share_grid_cbox.stateChanged.connect(
                lambda: self.grid_edit.setEnabled(self.share_grid_cbox.isChecked()))
            self.share_loop_cbox.stateChanged.connect(
                lambda: self.loop_edit.setEnabled(self.share_loop_cbox.isChecked()))

            # 'File' menu
            self.actionOpenFile.triggered.connect(self.open_file_dialog)
            self.actionSaveFiles.triggered.connect(lambda: self.save_pem_files(selected=False))
            self.actionExport_As_XYZ.triggered.connect(self.export_as_xyz)
            self.actionHeader_CSV.triggered.connect(self.export_pem_headers)
            self.actionExport_As_PEM.triggered.connect(lambda: self.export_pem_files(selected=False,
                                                                                     processed=False))
            self.actionExport_Processed_PEM.triggered.connect(lambda: self.export_pem_files(selected=False,
                                                                                            processed=True))
            self.actionExport_Legacy_PEM.triggered.connect(lambda: self.export_pem_files(selected=False,
                                                                                         legacy=True))
            self.actionBackup_Files.triggered.connect(self.backup_files)
            self.actionImport_RI_Files.triggered.connect(self.open_ri_importer)
            self.actionImport_RI_Files.setShortcut("Ctrl+I")

            self.actionPrint_Plots_to_PDF.triggered.connect(self.open_pdf_plot_printer)

            # PEM menu
            self.actionRename_Lines_Holes.triggered.connect(lambda: self.open_name_editor('Line', selected=False))
            self.actionRename_Files.triggered.connect(lambda: self.open_name_editor('File', selected=False))
            self.actionAverage_All_PEM_Files.triggered.connect(lambda: self.average_pem_data(selected=False))
            self.actionSplit_All_PEM_Files.triggered.connect(lambda: self.split_pem_channels(selected=False))
            self.actionScale_All_Currents.triggered.connect(lambda: self.scale_pem_current(selected=False))
            self.actionChange_All_Coil_Areas.triggered.connect(lambda: self.scale_pem_coil_area(selected=False))
            # self.actionOffset_Mag.triggered.connect(lambda: self.mag_offset_lastchn(selected=False))
            self.actionAuto_Name_Lines_Holes.triggered.connect(self.auto_name_lines)

            self.actionReverseX_Component.triggered.connect(
                lambda: self.reverse_component_data(comp='X', selected=False))
            self.actionReverseY_Component.triggered.connect(
                lambda: self.reverse_component_data(comp='Y', selected=False))
            self.actionReverseZ_Component.triggered.connect(
                lambda: self.reverse_component_data(comp='Z', selected=False))
            self.actionStation_Order.triggered.connect(lambda: self.reverse_station_order(selected=False))

            # Map menu
            self.actionQuick_Map.triggered.connect(self.open_quick_map)
            self.actionTile_Map.triggered.connect(self.open_tile_map)
            self.actionContour_Map.triggered.connect(self.open_contour_map)
            self.action3D_Map.triggered.connect(self.open_3d_map)
            self.actionGoogle_Earth.triggered.connect(lambda: self.save_as_kmz(save=False))
            self.actionMake_DXF.triggered.connect(self.make_dxf)

            # GPS menu
            self.actionExport_All_GPS.triggered.connect(lambda: self.export_gps(selected=False))
            self.actionConvert_GPS.triggered.connect(self.open_gps_conversion)
            self.actionSave_as_KMZ.triggered.connect(lambda: self.save_as_kmz(save=True))

            # Tools menu
            self.actionLoop_Planner.triggered.connect(self.open_loop_planner)
            self.actionGrid_Planner.triggered.connect(self.open_grid_planner)
            self.actionLoop_Current_Calculator.triggered.connect(self.open_loop_calculator)
            self.actionConvert_Timebase_Frequency.triggered.connect(self.open_freq_converter)
            self.actionDamping_Box_Plotter.triggered.connect(self.open_db_plot)
            self.actionUnpacker.triggered.connect(self.open_unpacker)
            self.actionGPX_Creator.triggered.connect(self.open_gpx_creator)

            # Settings menu
            self.actionSave_Settings.triggered.connect(self.save_settings)
            self.actionSave_Settings.triggered.connect(lambda: self.status_bar.showMessage("Settings saved.", 1500))
            self.actionReset_Settings.triggered.connect(self.reset_settings)
            self.actionAdd_Mapbox_Token.triggered.connect(add_mapbox_token)
            self.actionDark_Theme.triggered.connect(self.set_dark_mode)

            # Help menu
            self.actionView_Logs.triggered.connect(open_logs)
            self.enable_menus(False)

        def init_crs():
            """
            Populate the CRS drop boxes and connect all their signals
            """
            if splash_screen:
                splash_screen.showMessage("Initializing CRS")

            def toggle_gps_system(set_warning=True):
                """
                Toggle the datum and zone combo boxes and change their options based on the selected CRS system.
                """
                current_zone = self.gps_zone_cbox.currentText()
                datum = self.gps_datum_cbox.currentText()
                system = self.gps_system_cbox.currentText()

                if system == '':
                    self.gps_zone_cbox.setEnabled(False)
                    self.gps_datum_cbox.setEnabled(False)

                elif system == 'Lat/Lon':
                    self.gps_datum_cbox.setCurrentText('WGS 1984')
                    self.gps_zone_cbox.setCurrentText('')
                    self.gps_datum_cbox.setEnabled(False)
                    self.gps_zone_cbox.setEnabled(False)

                    if set_warning:
                        self.message.warning(self, 'Geographic CRS',
                                             "Some features such as maps don't work with a geographic CRS.")

                elif system == 'UTM':
                    self.gps_datum_cbox.setEnabled(True)

                    if datum == '':
                        self.gps_zone_cbox.setEnabled(False)
                        return
                    else:
                        self.gps_zone_cbox.clear()
                        self.gps_zone_cbox.setEnabled(True)

                    # NAD 27 and 83 only have zones from 1N to 22N/23N
                    if datum == 'NAD 1927':
                        zones = [''] + [f"{num} North" for num in range(1, 23)] + ['59 North', '60 North']
                    elif datum == 'NAD 1983':
                        zones = [''] + [f"{num} North" for num in range(1, 24)] + ['59 North', '60 North']
                    # WGS 84 has zones from 1N and 1S to 60N and 60S
                    else:
                        zones = [''] + [f"{num} North" for num in range(1, 61)] + [f"{num} South" for num in
                                                                                   range(1, 61)]

                    for zone in zones:
                        self.gps_zone_cbox.addItem(zone)

                    # Keep the same zone number if possible
                    self.gps_zone_cbox.setCurrentText(current_zone)

            def toggle_crs_rbtn():
                """
                Toggle the radio buttons for the project CRS box, switching between the CRS drop boxes and the EPSG edit.
                """
                if self.crs_rbtn.isChecked():
                    # Enable the CRS drop boxes and disable the EPSG line edit
                    self.gps_system_cbox.setEnabled(True)
                    toggle_gps_system(set_warning=False)

                    self.epsg_edit.setEnabled(False)
                else:
                    # Disable the CRS drop boxes and enable the EPSG line edit
                    self.gps_system_cbox.setEnabled(False)
                    self.gps_datum_cbox.setEnabled(False)
                    self.gps_zone_cbox.setEnabled(False)

                    self.epsg_edit.setEnabled(True)

                update_pem_files_crs()

            def check_epsg():
                """
                Try to convert the EPSG code to a Proj CRS object, reject the input if it doesn't work.
                """
                epsg_code = self.epsg_edit.text()
                self.epsg_edit.blockSignals(True)

                if epsg_code:
                    try:
                        crs = CRS.from_epsg(epsg_code)
                    except Exception as e:
                        logger.critical(f"{epsg_code} is not a valid EPSG code.")
                        self.message.critical(self, 'Invalid EPSG Code', f"{epsg_code} is not a valid EPSG code.")
                        self.epsg_edit.setText('')
                    else:
                        if crs.is_geographic:
                            logger.warning(f"Geographics CRS selected.")
                            self.message.warning(self, 'Geographic CRS',
                                                 "Some features such as maps don't work with a geographic CRS.")
                    finally:
                        set_epsg_label()

                self.epsg_edit.blockSignals(False)

            def set_epsg_label():
                """
                Convert the current project CRS combo box values into the EPSG code and set the status bar label.
                """
                epsg_code = self.get_epsg()
                if epsg_code:
                    crs = CRS.from_epsg(epsg_code)
                    self.epsg_label.setText(f"Project CRS: {crs.name} - EPSG:{epsg_code} ({crs.type_name})")
                else:
                    self.epsg_label.setText('')

            def update_pem_files_crs():
                """
                Update the CRS in all opened PEMFiles
                """
                crs = self.get_crs()
                if crs:
                    for pem_file in self.pem_files:
                        pem_file.set_crs(crs)

            # Add the GPS system and datum drop box options
            gps_systems = ['', 'Lat/Lon', 'UTM']
            for system in gps_systems:
                self.gps_system_cbox.addItem(system)

            datums = ['', 'WGS 1984', 'NAD 1927', 'NAD 1983']
            for datum in datums:
                self.gps_datum_cbox.addItem(datum)

            # Signals
            # Combo boxes
            self.gps_system_cbox.currentIndexChanged.connect(toggle_gps_system)
            self.gps_system_cbox.currentIndexChanged.connect(set_epsg_label)
            self.gps_system_cbox.currentIndexChanged.connect(update_pem_files_crs)
            self.gps_datum_cbox.currentIndexChanged.connect(toggle_gps_system)
            self.gps_datum_cbox.currentIndexChanged.connect(set_epsg_label)
            self.gps_datum_cbox.currentIndexChanged.connect(update_pem_files_crs)
            self.gps_zone_cbox.currentIndexChanged.connect(set_epsg_label)
            self.gps_zone_cbox.currentIndexChanged.connect(update_pem_files_crs)

            # Radio buttons
            self.crs_rbtn.clicked.connect(toggle_crs_rbtn)
            self.crs_rbtn.clicked.connect(set_epsg_label)
            self.epsg_rbtn.clicked.connect(toggle_crs_rbtn)
            self.epsg_rbtn.clicked.connect(set_epsg_label)

            # Line edit
            self.epsg_edit.editingFinished.connect(check_epsg)
            self.epsg_edit.editingFinished.connect(update_pem_files_crs)

        def init_project_directory():
            if splash_screen:
                splash_screen.showMessage("Initializing directory")

            # Project directory frame
            self.dir_frame.setLayout(QHBoxLayout())
            self.dir_frame.layout().setContentsMargins(3, 0, 3, 0)
            self.dir_frame.layout().setSpacing(2)
            self.project_dir_edit.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
            self.project_dir_edit.setMinimumWidth(250)
            self.project_dir_btn.setFlat(True)
            self.project_dir_btn.clicked.connect(lambda: self.move_dir_tree(self.project_dir_edit.text()))
            self.dir_frame.layout().addWidget(self.project_dir_btn)
            self.dir_frame.layout().addWidget(self.project_dir_edit)

            # Project tree
            self.file_sys_model.setRootPath(QDir.rootPath())
            self.project_tree.setModel(self.file_sys_model)
            self.project_tree.setColumnHidden(1, True)
            self.project_tree.setColumnHidden(2, True)
            self.project_tree.setColumnHidden(3, True)
            self.project_tree.setHeaderHidden(True)
            self.project_tree.setContextMenuPolicy(Qt.CustomContextMenu)
            self.project_tree.customContextMenuRequested.connect(self.open_dir_tree_context_menu)
            self.project_tree.setAutoScroll(False)
            # self.move_dir_tree_to(self.file_sys_model.rootPath())

        def init_status_bar():
            if splash_screen:
                splash_screen.showMessage("Initializing status bar")

            # Status bar formatting
            self.selection_files_label.setMargin(3)
            self.selection_timebase_label.setMargin(3)
            self.selection_zts_label.setMargin(3)
            self.selection_survey_label.setMargin(3)
            self.selection_derotation_label.setMargin(3)
            self.epsg_label.setMargin(3)

            self.status_bar.addPermanentWidget(self.selection_files_label, 0)
            self.status_bar.addPermanentWidget(self.selection_timebase_label, 0)
            self.status_bar.addPermanentWidget(self.selection_zts_label, 0)
            self.status_bar.addPermanentWidget(self.selection_survey_label, 0)
            self.status_bar.addPermanentWidget(self.selection_derotation_label, 0)
            # self.status_bar.addPermanentWidget(QLabel(), 0)  # Spacer
            self.status_bar.addPermanentWidget(self.epsg_label, 0)
            self.status_bar.addPermanentWidget(self.dir_frame, 0)

        self.app = app
        self.parent = parent

        self.pem_files = []
        self.pem_info_widgets = []
        self.pem_editor_widgets = []
        self.tab_num = 1
        self.allow_signals = True
        self.darkmode = False
        self.text_browsers = []
        self.channel_tables = []
        self.pem_dir = None
        self.gps_dir = None
        self.available_pems = []
        self.available_gps = []

        if splash_screen:
            splash_screen.showMessage("Initializing widgets")

        # Widgets
        self.file_dialog = QFileDialog()
        self.message = QMessageBox()
        self.error = QErrorMessage()
        self.calender = QCalendarWidget()
        self.calender.setWindowTitle('Select Date')
        self.pem_list_filter = PathFilter('PEM', parent=self)
        self.gps_list_filter = PathFilter('GPS', parent=self)
        self.unpacker = Unpacker(parent=self)
        self.selection_files_label = QLabel()
        self.selection_timebase_label = QLabel()
        self.selection_zts_label = QLabel()
        self.selection_survey_label = QLabel()
        self.selection_derotation_label = QLabel()
        self.epsg_label = QLabel()

        init_ui()
        init_crs()

        # Menus
        self.menu = QMenu(self.table)  # Main right-click menu
        self.view_menu = QMenu('View', self.menu)
        self.view_menu.setIcon(get_icon('view.png'))
        self.export_menu = QMenu('Export...', self.menu)
        self.export_menu.setIcon(get_icon('export.png'))
        self.extract_menu = QMenu('Extract...', self.menu)
        self.extract_menu.setIcon(get_icon('station_splitter.png'))
        self.share_menu = QMenu('Share', self.menu)
        self.share_menu.setIcon(get_icon('share_gps.png'))
        self.reverse_menu = QMenu('Reverse', self.menu)
        self.reverse_menu.setIcon(get_icon('reverse.png'))

        # Actions
        self.actionDel_File = QAction("&Remove File", self)
        self.remove_file_action = QAction("Remove", self)
        self.open_file_action = QAction("Open", self)
        self.save_file_action = QAction("Save", self)
        self.save_file_as_action = QAction("Save As...", self)
        self.copy_to_cliboard_action = QAction("Copy to Clipboard", self)
        self.export_pem_action = QAction("PEM", self)
        self.export_dad_action = QAction("DAD", self)
        self.export_gps_action = QAction("GPS", self)
        self.action_view_channels = QAction("Channel Table", self)
        self.merge_action = QAction("Merge", self)
        self.print_plots_action = QAction("Print Plots", self)
        self.extract_stations_action = QAction("Stations", self)
        self.extract_x_action = QAction("X Component", self)
        self.extract_y_action = QAction("Y Component", self)
        self.extract_z_action = QAction("Z Component", self)
        self.calc_mag_dec_action = QAction("Magnetic Declination", self)
        self.view_loop_action = QAction("Loop GPS", self)
        self.view_line_action = QAction("Line GPS", self)
        self.share_loop_action = QAction("Loop GPS", self)
        self.share_line_action = QAction("Line GPS", self)
        self.share_collar_action = QAction("Collar GPS", self)
        self.share_segments_action = QAction("Segments", self)
        self.share_all_action = QAction("All", self)
        self.open_plot_editor_action = QAction("Plot", self)
        self.open_quick_map_action = QAction("Quick Map", self)
        self.average_action = QAction("Average", self)
        self.split_action = QAction("Split Channels", self)
        self.scale_current_action = QAction("Scale Current", self)
        self.scale_ca_action = QAction("Scale Coil Area", self)
        self.reverse_x_component_action = QAction("X Polarity", self)
        self.reverse_y_component_action = QAction("Y Polarity", self)
        self.reverse_z_component_action = QAction("Z Polarity", self)
        self.reverse_station_order_action = QAction("Station Order", self)
        self.derotate_action = QAction("De-rotate XY", self)
        self.get_geometry_action = QAction("Geometry", self)
        self.rename_lines_action = QAction("Rename Lines/Holes", self)
        self.rename_files_action = QAction("Rename Files", self)
        init_actions()

        # Project Directory
        self.dir_frame = QFrame()
        self.project_dir_edit = QLineEdit('')
        self.project_dir_btn = QPushButton('Project Directory:')
        self.project_dir = None
        self.file_sys_model = QFileSystemModel()
        init_project_directory()

        # Table
        if splash_screen:
            splash_screen.showMessage("Initializing table")
        self.table_columns = [
            'File',
            'Date',
            'Client',
            'Grid',
            'Line/Hole',
            'Loop',
            'Current',
            'Coil\nArea',
            'First\nStation',
            'Last\nStation',
            'Averaged',
            'Split',
            'Suffix\nWarnings',
            'Repeat\nWarnings',
            'Polarity\nWarnings'
        ]
        header = self.table.horizontalHeader()
        header.hide()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        for i, col in enumerate(self.table_columns[1:]):
            header.setSectionResizeMode(i + 1, QHeaderView.ResizeToContents)

        init_status_bar()
        init_signals()

        self.load_settings()
        self.fill_pem_list()
        self.fill_gps_list()
        self.set_dark_mode()

    def center(self):
        """
        Center the widget to the screen.
        :return: None
        """
        frame_geo = self.frameGeometry()
        screen = self.window().windowHandle().screen()
        center_loc = screen.geometry().center()
        frame_geo.moveCenter(center_loc)
        self.move(frame_geo.topLeft())

    def save_settings(self):
        settings = QSettings("Crone Geophysics", "PEMPro")
        settings.beginGroup("MainWindow")

        # Window geometry
        settings.setValue("size", self.size())
        settings.setValue("pos", self.pos())

        # Setting options
        settings.setValue("actionDark_Theme", self.darkmode)
        settings.setValue("actionAlt_Click_Plotting", self.actionAlt_Click_Plotting.isChecked())
        settings.setValue("auto_sort_files_cbox", self.auto_sort_files_cbox.isChecked())
        settings.setValue("auto_create_backup_files_cbox", self.auto_create_backup_files_cbox.isChecked())
        settings.setValue("delete_merged_files_cbox", self.delete_merged_files_cbox.isChecked())
        settings.setValue("actionRename_Merged_Files", self.actionRename_Merged_Files.isChecked())

        # Project directory
        settings.setValue("project_dir", self.project_dir)

        # Files
        settings.setValue("last_opened_files", self.pem_files)

        # File filters
        settings.setValue("PEM_filter", self.pem_list_filter.get_settings())
        settings.setValue("GPS_filter", self.gps_list_filter.get_settings())

        settings.endGroup()

        settings.beginGroup("Unpacker")
        settings.setValue("open_damp_files_cbox", self.unpacker.open_damp_files_cbox.isChecked())

        settings.endGroup()

    def load_settings(self):
        settings = QSettings("Crone Geophysics", "PEMPro")
        settings.beginGroup("MainWindow")

        # Window geometry
        self.resize(settings.value("size", QSize(1700, 900)))
        self.move(settings.value("pos", QPoint(100, 50)))

        # Setting options
        self.actionDark_Theme.setChecked(True if settings.value("actionDark_Theme") == "true" else False)
        self.actionAlt_Click_Plotting.setChecked(True if settings.value("actionAlt_Click_Plotting") == "true" else False)
        self.auto_sort_files_cbox.setChecked(False if settings.value("auto_sort_files_cbox") == "false" else True)
        self.auto_create_backup_files_cbox.setChecked(False if settings.value("auto_create_backup_files_cbox") == "false" else True)
        self.delete_merged_files_cbox.setChecked(False if settings.value("delete_merged_files_cbox") == "false" else True)
        self.actionRename_Merged_Files.setChecked(False if settings.value("actionRename_Merged_Files") == "false" else True)

        # Project directory
        # self.project_dir_edit.setText(str(self.file_sys_model.rootPath()))  # In case no valid project dir is saved
        project_dir = settings.value("project_dir")
        if project_dir:
            if Path(project_dir).is_dir():
                self.move_dir_tree(str(project_dir), start_up=True)

        # Files
        last_opened_pems = settings.value("last_opened_files")
        if last_opened_pems:
            response = self.message.question(self, 'Open Previous Files', "Open the last previously opened PEM files?",
                                             self.message.Yes | self.message.No)
            if response == self.message.Yes:
                self.add_pem_files(last_opened_pems)

        # File filters
        self.pem_list_filter.set_settings(settings.value("PEM_filter"), refresh=False)
        self.gps_list_filter.set_settings(settings.value("GPS_filter"), refresh=False)

        settings.endGroup()

        settings.beginGroup("Unpacker")
        self.unpacker.open_damp_files_cbox.setChecked(False if settings.value("open_damp_files_cbox") == "false" else True)
        settings.endGroup()

    def reset_settings(self):
        settings = QSettings("Crone Geophysics", "PEMPro")
        settings.clear()
        self.resize(1700, 900)
        self.center()
        if self.darkmode:
            self.actionDark_Theme.trigger()
        self.actionAlt_Click_Plotting.setChecked(True)
        self.auto_sort_files_cbox.setChecked(True)
        self.auto_create_backup_files_cbox.setChecked(True)
        self.delete_merged_files_cbox.setChecked(True)
        self.actionRename_Merged_Files.setChecked(True)

        self.project_dir = None
        self.project_dir_edit.setText("")

        self.unpacker.open_damp_files_cbox.setChecked(True)

        self.pem_list_filter.reset()
        self.gps_list_filter.reset()

        self.save_settings()

    def contextMenuEvent(self, event):
        """
        Right-click context menu items.
        :param event: Right-click event.
        :return: None
        """
        if not self.table.underMouse():
            return

        if self.table.selectionModel().selectedIndexes():
            selected_pems, rows = self.get_pem_files(selected=True)

            # Clear the menu
            self.menu.clear()
            self.view_menu.clear()
            self.extract_menu.clear()
            self.export_menu.clear()
            self.share_menu.clear()
            self.reverse_menu.clear()

            # Add all the actions to the menu
            self.menu.addAction(self.open_file_action)
            self.menu.addAction(self.save_file_action)

            # Only for single file selection
            if len(self.table.selectionModel().selectedRows()) == 1:
                pem_file = selected_pems[0]

                self.menu.addAction(self.save_file_as_action)
                self.menu.addAction(self.copy_to_cliboard_action)
                self.menu.addSeparator()

                # View menu
                self.menu.addMenu(self.view_menu)
                self.view_menu.addAction(self.calc_mag_dec_action)
                if pem_file.has_any_gps():
                    self.calc_mag_dec_action.setDisabled(False)
                else:
                    self.calc_mag_dec_action.setDisabled(True)
                self.view_menu.addAction(self.action_view_channels)
                self.view_menu.addSeparator()

                # View Loop
                self.view_menu.addAction(self.view_loop_action)
                if not pem_file.has_loop_gps():
                    self.view_loop_action.setDisabled(True)
                else:
                    self.view_loop_action.setDisabled(False)

                # View Line
                if not pem_file.is_borehole():
                    self.view_menu.addAction(self.view_line_action)
                    if not pem_file.has_station_gps():
                        self.view_line_action.setDisabled(True)
                    else:
                        self.view_line_action.setDisabled(False)

                # self.menu.addSeparator()

                # Add the export menu
                self.menu.addMenu(self.export_menu)
                self.export_menu.addAction(self.export_pem_action)
                if pem_file.is_borehole():
                    self.export_menu.addAction(self.export_dad_action)
                    # Disable the export dad button if there's no geometry and it's not an XY file
                    if not any([pem_file.has_geometry(), pem_file.has_xy()]):
                        self.export_dad_action.setDisabled(True)
                    else:
                        self.export_dad_action.setDisabled(False)
                self.export_menu.addAction(self.export_gps_action)
                if not pem_file.has_any_gps():
                    self.export_gps_action.setDisabled(True)
                else:
                    self.export_gps_action.setDisabled(False)

                # Add the extract menu
                self.menu.addMenu(self.extract_menu)
                self.extract_menu.addAction(self.extract_stations_action)
                self.extract_menu.addSeparator()

                components = pem_file.get_components()
                self.extract_menu.addAction(self.extract_x_action)
                self.extract_menu.addAction(self.extract_y_action)
                self.extract_menu.addAction(self.extract_z_action)
                if "X" not in components:
                    self.extract_x_action.setDisabled(True)
                else:
                    self.extract_x_action.setDisabled(False)
                if "Y" not in components:
                    self.extract_y_action.setDisabled(True)
                else:
                    self.extract_y_action.setDisabled(False)
                if "Z" not in components:
                    self.extract_z_action.setDisabled(True)
                else:
                    self.extract_z_action.setDisabled(False)

                # Add the share menu
                self.menu.addMenu(self.share_menu)

                # Share loop
                self.share_menu.addAction(self.share_loop_action)
                if pem_file.has_loop_gps() and len(self.pem_files) > 1:
                    self.share_loop_action.setDisabled(False)
                else:
                    self.share_loop_action.setDisabled(True)

                # Share line GPS
                if not pem_file.is_borehole():
                    self.share_menu.addAction(self.share_line_action)
                    if pem_file.has_station_gps() and len(self.pem_files) > 1:
                        self.share_line_action.setDisabled(False)
                    else:
                        self.share_line_action.setDisabled(True)

                # Share Collar and Segments
                else:
                    self.share_menu.addAction(self.share_collar_action)
                    self.share_menu.addAction(self.share_segments_action)
                    if pem_file.has_collar_gps() and len(self.pem_files) > 1:
                        self.share_collar_action.setDisabled(False)
                    else:
                        self.share_collar_action.setDisabled(True)
                    if pem_file.has_geometry() and len(self.pem_files) > 1:
                        self.share_segments_action.setDisabled(False)
                    else:
                        self.share_segments_action.setDisabled(True)

                self.share_menu.addSeparator()
                self.share_menu.addAction(self.share_all_action)
                if pem_file.has_any_gps() and len(self.pem_files) > 1:
                    self.share_all_action.setDisabled(False)
                else:
                    self.share_all_action.setDisabled(True)
            else:
                self.menu.addAction(self.copy_to_cliboard_action)

            self.menu.addSeparator()
            # Plot
            self.menu.addAction(self.open_plot_editor_action)
            self.menu.addAction(self.open_quick_map_action)
            self.menu.addSeparator()

            # Merge PEMs
            if len(self.table.selectionModel().selectedRows()) == 2:
                self.menu.addAction(self.merge_action)

            # Data editing
            self.menu.addAction(self.average_action)
            self.menu.addAction(self.split_action)
            self.menu.addAction(self.scale_current_action)
            self.menu.addAction(self.scale_ca_action)
            # self.menu.addAction(self.mag_offset_action)
            self.menu.addSeparator()

            # Add the reverse data menu
            self.menu.addMenu(self.reverse_menu)
            self.reverse_menu.addAction(self.reverse_x_component_action)
            self.reverse_menu.addAction(self.reverse_y_component_action)
            self.reverse_menu.addAction(self.reverse_z_component_action)
            self.reverse_menu.addSeparator()
            self.reverse_menu.addAction(self.reverse_station_order_action)

            self.menu.addSeparator()

            # For boreholes only, do-rotate and geometry
            if all([f.is_borehole() for f in selected_pems]):
                if len(self.table.selectionModel().selectedRows()) == 1:
                    self.menu.addAction(self.derotate_action)
                    if not pem_file.has_xy():
                        self.derotate_action.setDisabled(True)
                    else:
                        self.derotate_action.setDisabled(False)
                self.menu.addAction(self.get_geometry_action)
                self.menu.addSeparator()

            if len(self.table.selectionModel().selectedRows()) > 1:
                self.menu.addSeparator()
                self.menu.addAction(self.rename_files_action)
                self.menu.addAction(self.rename_lines_action)

            self.menu.addSeparator()
            self.menu.addAction(self.print_plots_action)
            self.menu.addSeparator()
            self.menu.addAction(self.remove_file_action)

            self.menu.popup(QCursor.pos())

    def eventFilter(self, source, event):
        # # Clear the selection when clicking away from any file
        if (event.type() == QEvent.MouseButtonPress and
                source is self.table.viewport() and
                self.table.itemAt(event.pos()) is None):
            self.reset_selection_labels()
        #     self.table.clearSelection()

        if source == self.table:
            # Change the focus to the table so the 'Del' key works
            if event.type() == QEvent.FocusIn:
                self.actionDel_File.setEnabled(True)
            elif event.type() == QEvent.FocusOut:
                self.actionDel_File.setEnabled(False)

            # Change the selected PIW widget when the arrow keys are pressed, and clear selection when Esc is pressed
            if event.type() == QEvent.KeyPress:
                if self.pem_files:
                    if event.key() == Qt.Key_Left:
                        current_tab = self.pem_info_widgets[0].tabs.currentIndex()
                        self.change_pem_info_tab(current_tab - 1)
                        return True
                    elif event.key() == Qt.Key_Right:
                        current_tab = self.pem_info_widgets[0].tabs.currentIndex()
                        self.change_pem_info_tab(current_tab + 1)
                        return True
                    elif event.key() == Qt.Key_Escape:
                        self.table.clearSelection()
                        self.reset_selection_labels()
                        return True

        return super(QWidget, self).eventFilter(source, event)

    def dragEnterEvent(self, e):
        e.acceptProposedAction()

    def dragMoveEvent(self, e):
        """
        Controls which files can be drag-and-dropped into the program. Conditions are based on the file type of each
        file being dragged, and which widget they are being dragged onto.
        :param e: PyQT event
        """
        urls = [Path(url.toLocalFile()) for url in e.mimeData().urls()]

        # PEM, DMP, and DUMP folders can be opened with no PEM files currently opened.
        # PEM and DMP files
        if all([file.suffix.lower() in ['.pem'] or file.suffix.lower() in ['.dmp', '.dmp2', '.dmp3', '.dmp4'] for file in urls]):
            if e.answerRect().intersects(self.table.geometry()):
                e.acceptProposedAction()
                return

        # Dump folder
        elif len(urls) == 1 and (urls[0].is_dir() or urls[0].suffix.lower() in ['.zip', '.7z', '.rar']):
            e.acceptProposedAction()
            return

        # Rest of the file types can only be opened if a PEM file is opened.
        else:
            if not self.pem_files:
                e.ignore()
                return

            current_piw = self.stackedWidget.currentWidget()
            eligible_tabs = [current_piw.station_gps_tab,
                             current_piw.loop_gps_tab,
                             current_piw.geometry_tab]

            # GPS files
            if all([Path(file).suffix.lower() in ['.txt', '.csv', '.seg', '.xyz', '.gpx', '.xlsx', '.xls'] for file in urls]):
                if all([e.answerRect().intersects(self.piw_frame.geometry()),
                        current_piw.tabs.currentWidget() in eligible_tabs,
                        self.pem_files]):
                    e.acceptProposedAction()
                    return

            # RI files
            elif all([file.suffix.lower() in ['.ri1', '.ri2', '.ri3'] for file in urls]):
                if all([e.answerRect().intersects(self.piw_frame.geometry()),
                        current_piw.tabs.currentWidget() == current_piw.ri_tab,
                        self.pem_files]):
                    e.acceptProposedAction()
                    return

            elif all([file.suffix.lower() in ['.inf', '.log', '.gpx'] for file in urls]):
                if e.answerRect().intersects(self.project_crs_box.geometry()):
                    e.acceptProposedAction()
                    return

            else:
                e.ignore()

    def dropEvent(self, e):
        urls = [Path(url.toLocalFile()) for url in e.mimeData().urls()]

        if all([file.suffix.lower() in ['.pem'] or
                file.suffix.lower() in ['.dmp', '.dmp2', '.dmp3', '.dmp4']
                for file in urls]):
            pem_files = [url for url in urls if url.suffix.lower() == '.pem']
            dmp_files = [url for url in urls if url.suffix.lower() in ['.dmp', '.dmp2', '.dmp3', '.dmp4']]
            if pem_files:
                self.add_pem_files(pem_files)
            if dmp_files:
                self.add_dmp_files(dmp_files)

        elif all([Path(file).suffix.lower() in ['.dmp', '.dmp2', '.dmp3', '.dmp4'] for file in urls]):
            self.add_dmp_files(urls)

        elif all([Path(file).suffix.lower() in ['.txt', '.csv', '.seg', '.xyz', '.gpx', '.xlsx', '.xls'] for file in urls]):
            self.add_gps_files(urls)

        elif all([Path(file).suffix.lower() in ['.ri1', '.ri2', '.ri3'] for file in urls]):
            self.add_ri_file(urls)

        elif all([Path(file).suffix.lower() in ['.inf', '.log'] for file in urls]):
            self.read_inf_file(urls[0])

        elif len(urls) == 1 and (Path(urls[0]).is_dir() or Path(urls[0]).suffix.lower() in ['.zip', '.7z', '.rar']):
            self.open_unpacker(folder=urls[0])

    def closeEvent(self, e):
        self.save_settings()
        sys.exit(self.app.exec_())  # Close any other opened widgets
        e.accept()

    def is_opened(self, file):
        """
        Check if the PEMFile is currently opened.
        :param file: Union, PEMFile object or Path object
        """
        if isinstance(file, PEMFile):
            file = file.filepath

        if self.pem_files:
            existing_filepaths = [file.filepath.absolute for file in self.pem_files]
            if file.absolute in existing_filepaths:
                logger.info(f"{file.name} is already opened.")
                self.status_bar.showMessage(f"{file.name} is already opened", 2000)
                return True
            else:
                return False
        else:
            return False

    def change_pem_info_tab(self, tab_num):
        """
        Slot: Change the tab for each pemInfoWidget to the same
        :param tab_num: tab index number to change to
        """
        self.tab_num = tab_num
        if len(self.pem_info_widgets) > 0:
            for widget in self.pem_info_widgets:
                widget.tabs.setCurrentIndex(self.tab_num)

    def add_dmp_files(self, dmp_files):
        """
        Convert and open a .DMP or .DMP2 file
        :param dmp_files: list of str, filepaths of .DMP or .DMP2 files
        """
        if not dmp_files:
            return

        if not isinstance(dmp_files, list):
            dmp_files = [dmp_files]

        dmp_files = [Path(f) for f in dmp_files]

        dmp_parser = DMPParser()
        pem_files = []

        with CustomProgressDialog("Converting DMP Files...", 0, len(dmp_files)) as dlg:
            for file in dmp_files:
                if dlg.wasCanceled():
                    break
                dlg.setLabelText(f"Converting {Path(file).name}")

                if not file.exists():
                    self.message.critical(self, "Error", f"{file.name} does not exist.")
                    continue

                try:
                    pem_file, inf_errors = dmp_parser.parse(file)
                except Exception as e:
                    logger.critical(f"{e}")
                    self.error.showMessage(f"Error converting DMP file: {str(e)}")
                    dlg += 1
                    continue
                else:
                    if not inf_errors.empty:
                        error_str = inf_errors.loc[:, ['Station', 'Component', 'Reading_number']].to_string()
                        self.message.warning(self, f'{Path(file).name} Data Errors',
                                             f'The following readings had INF values:\n{error_str}')
                    pem_files.append(pem_file)
                finally:
                    dlg += 1

        self.add_pem_files(pem_files)

    def add_pem_files(self, pem_files):
        """
        Action of opening a PEM file. Will not open a PEM file if it is already opened.
        :param pem_files: list or str/Path, Filepaths for the PEM Files
        """
        def add_piw_widget(pem_file):
            """
            Create the PEMFileInfoWidget for the PEM file
            :param pem_file: PEMFile object
            :return: None
            """
            def share_gps_object(obj):
                """
                Share a GPS object (loop, line, collar, segments) of one file with all other opened PEM files.
                :param obj: BaseGPS object, which GPS object to share
                """
                df = obj.df.dropna()
                if df.empty:
                    return

                self.open_gps_share(obj, pem_info_widget)

            pem_info_widget = PEMFileInfoWidget(parent=self, darkmode=self.darkmode)
            pem_info_widget.blockSignals(True)

            # Create the PEMInfoWidget for the PEM file
            pem_info_widget.open_file(pem_file)
            # Change the current tab of this widget to the same as the opened ones
            pem_info_widget.tabs.setCurrentIndex(self.tab_num)
            # Connect a signal to change the tab when another PIW tab is changed
            pem_info_widget.tabs.currentChanged.connect(self.change_pem_info_tab)

            # Connect a signal to refresh the main table row when changes are made in the pem_info_widget tables
            pem_info_widget.refresh_row_signal.connect(lambda: self.refresh_pem(pem_info_widget.pem_file))
            # Ensure the CRS of each GPS object is always up to date
            pem_info_widget.refresh_row_signal.connect(lambda: pem_file.set_crs(self.get_crs()))
            # pem_info_widget.add_geometry_signal.connect(self.open_pem_geometry)

            pem_info_widget.share_loop_signal.connect(share_gps_object)
            pem_info_widget.share_line_signal.connect(share_gps_object)
            pem_info_widget.share_collar_signal.connect(share_gps_object)
            pem_info_widget.share_segments_signal.connect(share_gps_object)

            pem_info_widget.blockSignals(False)
            return pem_info_widget

        def get_insertion_point(pem_file):
            """
            Find the index to insert the pem_file (and associated widget)
            :param pem_file: PEMFile object
            :return: int, position to insert the file and widget
            """
            if not self.pem_files:
                i = 0
            elif self.auto_sort_files_cbox.isChecked() is False:
                i = self.table.rowCount()
            else:
                pems = copy.deepcopy(self.pem_files)
                pems.append(pem_file)
                pems = natsort.os_sorted(pems, key=lambda x: x.filepath.name)
                i = pems.index(pem_file)
            return i

        def share_header(pem_file):
            """
            Fill the shared header text boxes using the header information in the pem_file
            :param pem_file: PEMFile object
            """
            if self.client_edit.text() == '':
                self.client_edit.setText(pem_file.client)
            if self.grid_edit.text() == '':
                self.grid_edit.setText(pem_file.grid)
            if self.loop_edit.text() == '':
                self.loop_edit.setText(pem_file.loop_name)

        if not pem_files:
            return

        if not isinstance(pem_files, list):
            pem_files = [pem_files]

        count = 0
        parser = PEMParser()
        self.table.blockSignals(True)
        self.allow_signals = False
        self.table.setUpdatesEnabled(False)  # Suspends the animation of the table getting populated
        current_crs = self.get_crs()

        with CustomProgressDialog("Opening PEMs Files...", 0, len(pem_files)) as dlg:
            for pem_file in pem_files:
                if dlg.wasCanceled():
                    break

                # Create a PEMFile object if a filepath was passed
                if not isinstance(pem_file, PEMFile):
                    try:
                        pem_file = parser.parse(pem_file)
                    except Exception as e:
                        logger.critical(str(e))
                        self.error.setWindowTitle(f'Error parsing {pem_file}')
                        self.error.showMessage(str(e))
                        dlg += 1
                        continue

                logger.info(f"Adding {pem_file.filepath.name} to hub.")
                # Check if the file is already opened in the table. Won't open if it is.
                if self.is_opened(pem_file):
                    logger.info(f"{pem_file.filepath.name} already opened.")
                    self.status_bar.showMessage(f"{pem_file.filepath.name} is already opened", 2000)
                    dlg += 1
                else:
                    dlg.setLabelText(f"Opening {pem_file.filepath.name}")

                    # Create the PEMInfoWidget
                    pem_widget = add_piw_widget(pem_file)

                    # Fill the shared header text boxes and move the project directory
                    if not self.pem_files:
                        share_header(pem_file)
                        self.enable_menus(True)
                        # self.move_dir_tree(pem_file.filepath.parent)
                        # self.piw_frame.show()
                    if self.project_dir_edit.text() == '':
                        self.move_dir_tree(pem_file.filepath.parent)

                    # Update project CRS
                    pem_crs = pem_file.get_crs()
                    if pem_crs is not None:
                        if current_crs is None:
                            self.set_crs(pem_crs)
                        else:
                            if pem_crs != current_crs:
                                response = self.message.question(self, "Change CRS",
                                                                 F"CRS from {pem_file.filepath.name} is different than the "
                                                                 F"current project CRS ({pem_crs.name} vs {current_crs.name}).\n"
                                                                 F"Change CRS to {pem_crs.name}?", self.message.Yes, self.message.No)
                                if response == self.message.Yes:
                                    self.set_crs(pem_crs)
                                    current_crs = pem_crs
                                else:
                                    pass

                    i = get_insertion_point(pem_file)
                    self.pem_files.insert(i, pem_file)
                    self.pem_info_widgets.insert(i, pem_widget)
                    self.stackedWidget.insertWidget(i, pem_widget)
                    self.table.insertRow(i)
                    self.add_pem_to_table(pem_file, i)

                    count += 1
                    dlg += 1

        self.color_table_by_values()

        self.allow_signals = True
        self.table.setUpdatesEnabled(True)
        self.table.blockSignals(False)

        self.table.horizontalHeader().show()
        self.status_bar.showMessage(f"{count} PEM files opened.", 1500)

    def add_gps_files(self, gps_files):
        """
        Adds GPS information from the gps_files to the PEMFile object
        :param gps_files: list or str, filepaths of text file or GPX files
        """
        pem_info_widget = self.stackedWidget.currentWidget()
        current_crs = self.get_crs()

        if not isinstance(gps_files, list):
            gps_files = [gps_files]

        gps_files = [Path(file) for file in gps_files]
        logger.info(f"Opening GPS files {', '.join([f.name for f in gps_files])}")
        crs = pem_info_widget.open_gps_files(gps_files)

        # Set the project CRS if a .inf or .log file is in the directory and the project CRS is currently empty
        if current_crs is None and crs is None:
            crs_files = list(gps_files[0].parent.glob('*.inf'))
            crs_files.extend(gps_files[0].parent.glob('*.log'))
            if crs_files:
                self.read_inf_file(crs_files[0])
                self.status_bar.showMessage(F"Project CRS automatically filled using information from {crs_files[0]}.",
                                            2000)
            else:
                logger.debug(f"No CRS files found.")
        else:
            if crs is not None:
                if current_crs is not None and current_crs != crs:
                    response = self.message.question(self, "Change CRS",
                                                     F"CRS from GPS file(s) is different then the current project "
                                                     F"CRS ({crs.name} vs {current_crs.name}).\n"
                                                     F"Change CRS to {crs.name}?", self.message.Yes, self.message.No)
                    if response == self.message.Yes:
                        logger.debug(f"Changing CRS to {crs.name}.")
                        self.set_crs(crs)
                    else:
                        pass
                else:
                    self.set_crs(crs)

    def add_ri_file(self, ri_files):
        """
        Adds RI file information to the associated PEMFile object. Only accepts 1 file.
        :param ri_files: list, str filepaths with step plot information in them
        """
        ri_file = ri_files[0]
        pem_info_widget = self.stackedWidget.currentWidget()
        pem_info_widget.open_ri_file(ri_file)

    def enable_menus(self, enable):
        """
        Enable/Disable menus which required PEM files
        """
        self.actionSaveFiles.setEnabled(enable)
        self.menuExport_Files.setEnabled(enable)
        self.actionBackup_Files.setEnabled(enable)
        self.actionImport_RI_Files.setEnabled(enable)
        self.actionPrint_Plots_to_PDF.setEnabled(enable)

        self.menuPEM.setEnabled(enable)
        self.menuGPS.setEnabled(enable)
        self.menuMap.setEnabled(enable)

    def remove_pem_file(self, rows=None):
        """
        Removes PEM files from the main table, along with any associated widgets.
        :param rows: list: Table rows of the PEM files.
        :return: None
        """

        def reset_crs():
            self.gps_system_cbox.setCurrentText('')
            self.gps_zone_cbox.setCurrentText('')
            self.gps_datum_cbox.setCurrentText('')
            self.epsg_edit.setText("")

        if not rows:
            pem_files, rows = self.get_pem_files(selected=True)

        if not isinstance(rows, list):
            rows = [rows]

        self.setUpdatesEnabled(False)
        for row in rows:
            self.table.removeRow(row)
            self.stackedWidget.removeWidget(self.stackedWidget.widget(row))
            del self.pem_files[row]
            self.pem_info_widgets[row].close()
            del self.pem_info_widgets[row]

        if len(self.pem_files) == 0:
            self.table.horizontalHeader().hide()
            self.client_edit.setText('')
            self.grid_edit.setText('')
            self.loop_edit.setText('')
            reset_crs()
            self.enable_menus(False)
        else:
            # Only color the number columns if there are PEM files left
            self.color_table_by_values()

        self.reset_selection_labels()
        self.setUpdatesEnabled(True)

    def open_in_text_editor(self):
        """
        Open the selected PEM File in a text editor
        """

        def on_browser_close(browser):
            """
            Remove the browser from 'self.text_browsers' on close so it can be garbage collected.
            :param browser: PEMBrowser object
            """
            ind = self.text_browsers.index(browser)
            del self.text_browsers[ind]

        pem_files, rows = self.get_pem_files(selected=True)
        for pem_file in pem_files:
            # pem_str = pem_file.to_string()
            if not pem_file.filepath.is_file():
                logger.warning(f"{pem_file.filepath} does not exist.")
                self.status_bar.showMessage(f"{pem_file.filepath} does not exist.", 2000)
                return

            browser = PEMBrowser(pem_file)
            browser.close_request.connect(on_browser_close)
            self.text_browsers.append(browser)
            browser.show()

    def open_file_dialog(self):
        """
        Open files through the file dialog
        """
        files = QFileDialog().getOpenFileNames(self, 'Open PEM Files', self.project_dir_edit.text(),
                                               filter='PEM files (*.pem)')[0]
        if files:
            self.add_pem_files(files)

    def open_pem_plot_editor(self):
        """
        Open the PEMPlotEditor for each PEMFile selected
        """
        def save_editor_pem(pem_file):
            """
            Re-open the PEM file. File is actually saved in PEMPlotEditor.
            :param pem_file: PEMFile object emitted by the signal
            """
            self.refresh_pem(pem_file)

        def close_editor(editor):
            """
            Remove the editor from the list of pem_editors, and update the information in the table.
            :param editor: PEMPlotEditor object emitted by the signal
            """
            self.refresh_pem(editor.pem_file)
            self.pem_editor_widgets.remove(editor)

        def reset_file(files):
            """
            Reset the PEM file. Ensures the reset file is in self.pem_files for when the file is refreshed.
            :param files: tuple, current PEMFile and fallback PEMFile objects
            """
            pem_file = files[0]
            fallback_file = files[1]

            ind = self.pem_files.index(pem_file)
            self.pem_files[ind] = fallback_file
            self.refresh_pem(fallback_file)

        pem_files, rows = self.get_pem_files(selected=True)

        # Open individual editors for each PEMFile
        for pem_file in pem_files:
            editor = PEMPlotEditor(parent=self, darkmode=self.darkmode)
            self.pem_editor_widgets.append(editor)
            # Connect the 'save' and 'close' signals
            editor.save_sig.connect(save_editor_pem)
            editor.close_sig.connect(close_editor)
            editor.reset_file_sig.connect(reset_file)
            editor.open(pem_file)

    def open_derotator(self):
        def accept_file(rotated_pem):
            self.pem_files[row] = rotated_pem
            self.refresh_pem(rotated_pem)

        pem_files, rows = self.get_pem_files(selected=True)
        assert len(pem_files) == 1, 'Can only de-rotate one file at a time.'

        pem_file, row = pem_files[0], rows[0]

        derotator = Derotator(parent=self, darkmode=self.darkmode)
        refs.append(derotator)
        derotator.accept_sig.connect(accept_file)
        derotator.open(pem_file)

    def open_pem_geometry(self):
        def accept_geometry(seg):
            for file in pem_files:
                file.segments = seg
                self.refresh_pem(file)
            self.status_bar.showMessage(f"Geometry updated for {', '.join([file.filepath.name for file in pem_files])}."
                                        , 2000)

        pem_files, rows = self.get_pem_files(selected=True)

        print(f"Pre PEMGeometry darkmode: {self.darkmode}")
        pem_geometry = PEMGeometry(parent=self, darkmode=self.darkmode)
        refs.append(pem_geometry)
        pem_geometry.accepted_sig.connect(accept_geometry)
        pem_geometry.open(pem_files)

    def open_pem_merger(self):
        def check_pems():
            f1, f2 = pem_files[0], pem_files[1]

            if not f1.is_borehole() == f2.is_borehole():
                logger.error(f"{f1.filepath.name} is a {f1.get_survey_type()} and"
                             f" {f2.filepath.name} is a {f2.get_survey_type()}.")
                self.message.information(self, 'Error', f"Cannot merge a borehole survey with a surface survey.")
                return False
            if not f1.is_fluxgate() == f2.is_fluxgate():
                logger.error(f"{f1.filepath.name} is a {f1.get_survey_type()} and"
                             f" {f2.filepath.name} is a {f2.get_survey_type()}.")
                self.message.information(self, 'Error', f"Cannot merge a fluxgate survey with an induction survey.")
                return False
            if not f1.timebase == f2.timebase:
                logger.error(f"{f1.filepath.name} has a timebase of {f1.timebase} and"
                             f" {f2.filepath.name} has a timebase of {f2.timebase}.")
                self.message.information(self, 'Error', f"Both files must have the same timebase.")
                return False
            if not f1.number_of_channels == f2.number_of_channels:
                logger.error(f"{f1.filepath.name} has {len(f1.channel_times)} channels and"
                             f" {f2.filepath.name} has {len(f2.channel_times)} channels.")
                self.message.information(self, 'Error', f"Both files must have the same number of channels.")
                return False

            # If the files aren't all de-rotated (only for XY files)
            if all([f1.has_xy(), f2.has_xy()]) and all([f1.is_borehole(), f2.is_borehole()]):
                if not all([f.is_derotated() == pem_files[0].is_derotated() for f in pem_files]):
                    logger.warning(f"Mixed states of XY de-rotation between {f1.filepath.name} and {f2.filepath.name}.")
                    self.message.warning(self, 'Warning - Different states of XY de-rotation',
                                         'There is a mix of XY de-rotation in the selected files.')

            if f1.ramp != f2.ramp:
                logger.warning(
                    f"{f1.filepath.name} has a ramp of {f1.ramp}. {f2.filepath.name} has a ramp of {f2.ramp}.")
                self.message.warning(self, 'Warning - Different ramp lengths.',
                                     'The two files have different ramp lengths.')

            return True

        def accept_merge(filepath):
            """
            Open the new merged PEMFile, and remove the old ones if the delete_merged_files_cbox is checked.
            :param filepath: str.
            """
            filepath = Path(filepath)
            project_dir = self.project_dir_edit.text()
            removal_rows = []
            if self.actionRename_Merged_Files.isChecked():
                for row in rows:
                    name = self.table.item(row, self.table_columns.index("File")).text()
                    if name != filepath.name:
                        removal_rows.append(row)
                        if Path(project_dir + name).is_file():
                            new_name = "[M]" + name
                            # Also triggers file re-name.
                            self.table.item(row, self.table_columns.index("File")).setText(new_name)

            if self.delete_merged_files_cbox.isChecked():
                self.remove_pem_file(removal_rows)

            self.add_pem_files(filepath)
            self.fill_pem_list()

        pem_files, rows = self.get_pem_files(selected=True)
        if len(pem_files) != 2:
            logger.error(f"PEMMerger must have two PEM files, not {len(pem_files)}.")
            self.message.critical(self, 'Error', f'Must select two PEM Files, not {len(pem_files)}.')
            return

        if check_pems():
            merger = PEMMerger(parent=self, darkmode=self.darkmode)
            refs.append(merger)
            merger.accept_sig.connect(accept_merge)
            merger.open(pem_files)

    def open_pdf_plot_printer(self, selected=False):
        """
        Open an instance of PDFPlotPrinter, which has all the options for printing plots.
        :param selected: bool, False will pass all opened PEM files, True will only pass selected PEM files
        """

        if not self.pem_files:
            self.status_bar.showMessage(f"No PEM files opened.", 2000)
            return

        pem_files, rows = self.get_pem_files(selected=selected)
        pdf_plot_printer = PDFPlotPrinter(parent=self, darkmode=self.darkmode)
        refs.append(pdf_plot_printer)

        # Gather the RI files
        ri_files = []
        for row, pem_file in zip(rows, pem_files):
            ri_files.append(self.pem_info_widgets[row].ri_file)

        # Disable plan map creation if no CRS is selected or if the CRS is geographic.
        crs = self.get_crs()
        if not crs:
            response = self.message.question(self, 'No CRS',
                                             'Invalid CRS selected. ' +
                                             'Do you wish to proceed without a plan map?',
                                             self.message.Yes | self.message.No)
            if response == self.message.No:
                self.status_bar.showMessage("Cancelled.", 1000)
                return
            else:
                pdf_plot_printer.make_plan_maps_gbox.setChecked(False)
                pdf_plot_printer.make_plan_maps_gbox.setEnabled(False)

        elif crs.is_geographic:
            response = self.message.question(self, 'Geographic CRS',
                                             'Map creation with geographic CRS has not yet been implemented. ' +
                                             'Do you wish to proceed without a plan map?',
                                             self.message.Yes | self.message.No)
            if response == self.message.No:
                self.status_bar.showMessage("Cancelled.", 1000)
                return
            else:
                pdf_plot_printer.make_plan_maps_gbox.setChecked(False)
                pdf_plot_printer.make_plan_maps_gbox.setEnabled(False)

        # Disable the section plots if no file can produce one
        if not any([f.is_borehole() and f.has_all_gps() for f in pem_files]):
            pdf_plot_printer.make_section_plots_gbox.setChecked(False)
            pdf_plot_printer.make_section_plots_gbox.setEnabled(False)

        pdf_plot_printer.open(pem_files, ri_files=ri_files, crs=self.get_crs())

    def open_mag_dec(self):
        """
        Opens the MagDeclinationCalculator widget to calculate the magnetic declination of the selected file.
        """
        pem_files, rows = self.get_pem_files(selected=True)
        crs = self.get_crs()
        if not crs:
            logger.warning(f"No CRS.")
            self.message.information(self, 'Error', 'GPS coordinate system information is incomplete')
            return

        mag_calculator = MagDeclinationCalculator(parent=self)
        refs.append(mag_calculator)
        mag_calculator.calc_mag_dec(pem_files[0])
        mag_calculator.show()

    def open_db_plot(self):
        """Open the damping box plotter."""
        db_plot = DBPlotter(parent=self, darkmode=self.darkmode)
        refs.append(db_plot)
        db_plot.show()

    def open_name_editor(self, kind, selected=False):
        """
        Opens the BatchNameEditor for renaming multiple file names and/or line/hole names.
        :param kind: str, either 'Line' to change the line names or 'File' to change file names
        :param selected: bool, whether to only open selected PEMFiles or all of them.
        """
        def rename_pem_files(new_names):
            """
            Retrieve and open the PEM files from the batch_name_editor object
            :param new_names: list of str, new names
            """
            if kind == 'File':
                col = self.table_columns.index('File')
            else:
                col = self.table_columns.index('Line/Hole')

            for i, row in enumerate(rows):
                item = QTableWidgetItem(new_names[i])
                item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row, col, item)
            batch_name_editor.open(pem_files, kind=kind)

        pem_files, rows = self.get_pem_files(selected=selected)

        if not pem_files:
            logger.warning("No PEM files selected.")
            self.status_bar.showMessage(f"No PEM files selected.", 2000)
            return

        batch_name_editor = BatchNameEditor(parent=self)
        refs.append(batch_name_editor)
        batch_name_editor.open(pem_files, kind=kind)
        batch_name_editor.acceptChangesSignal.connect(rename_pem_files)

    def open_ri_importer(self):
        """
        Opens BatchRIImporter for bulk importing RI files.
        :return: None
        """
        def open_ri_files(files):
            if len(files) > 0:
                for pem_file, ri_file in files.items():
                    ind = self.pem_files.index(pem_file)
                    self.pem_info_widgets[ind].open_ri_file(ri_file)
                self.status_bar.showMessage(f"Imported {len(files)} RI files", 2000)
            else:
                pass

        ri_importer = BatchRIImporter(parent=self)
        refs.append(ri_importer)
        ri_importer.open_pem_files(self.pem_files)
        ri_importer.acceptImportSignal.connect(open_ri_files)
        ri_importer.show()

    def open_quick_map(self, selected=False):
        """
        Open the GPSViewer if there's any GPS in any of the opened PEM files.
        """
        quick_map = GPSViewer(parent=self, darkmode=self.darkmode)
        refs.append(quick_map)

        pem_files, rows = self.get_pem_files(selected=selected)

        if not pem_files:
            logger.warning(f"No PEM files opened.")
            self.status_bar.showMessage(f"No PEM files opened.", 2000)

        elif not any([f.has_any_gps() for f in pem_files]):
            logger.warning(f"No GPS found in any file.")
            self.message.information(self, 'Error', 'No file has any GPS to plot.')
        else:
            quick_map.open(pem_files)

    def open_tile_map(self):
        """
        Open the MapboxViewer if there's any GPS in any of the opened PEM files.
        """
        if not self.get_crs():
            self.message.information(self, 'Error', 'No CRS selected.')
            return

        tile_map = TileMapViewer(parent=self)
        refs.append(tile_map)

        if not self.pem_files:
            logger.warning(f"No PEM files opened.")
            self.status_bar.showMessage(f"No PEM files opened.", 1500)

        elif not any([f.has_any_gps() for f in self.pem_files]):
            logger.warning(f"No GPS found in any file.")
            self.message.information(self, 'Error', 'No file has any GPS to plot.')
        else:
            tile_map.open(self.pem_files)

    def open_3d_map(self):
        """
        Open the Map3DViewer if there's any GPS in any of the opened PEM files.
        """
        map_3d = Map3DViewer(parent=self, darkmode=self.darkmode)
        refs.append(map_3d)

        if not self.pem_files:
            logger.warning(f"No PEM files opened.")
            self.status_bar.showMessage(f"No PEM files opened.", 2000)
            return

        elif not any([f.has_any_gps() for f in self.pem_files]):
            logger.warning(f"No GPS found in any file.")
            self.message.information(self, 'Error', 'No file has any GPS to plot.')
            return

        else:
            map_3d.open(self.pem_files)

    def open_gps_conversion(self):
        """
        Open the GPS conversion widget.
        """
        def convert_gps(epsg_code):
            """
            Convert the GPS of all GPS objects to the new EPSG code.
            :param epsg_code: int
            """
            logger.info(f"Converting all GPS to EPSG:{epsg_code} ({CRS(epsg_code).name})")

            with CustomProgressDialog("Converting DMP Files...", 0, len(self.pem_files)) as dlg:

                # Convert all GPS of each PEMFile
                for pem_file in self.pem_files:
                    if dlg.wasCanceled():
                        break

                    pem_file.set_crs(crs)  # Ensure the current CRS is set
                    dlg.setLabelText(f"Converting GPS of {pem_file.filepath.name}")
                    logger.info(f"Converting GPS of {pem_file.filepath.name}")

                    if not pem_file.loop.df.empty:
                        pem_file.loop = pem_file.loop.to_epsg(epsg_code)

                    if pem_file.is_borehole():
                        if not pem_file.collar.df.empty:
                            pem_file.collar = pem_file.collar.to_epsg(epsg_code)

                    else:
                        if not pem_file.line.df.empty:
                            pem_file.line = pem_file.line.to_epsg(epsg_code)

                    self.refresh_pem(pem_file)
                    dlg += 1

                # Set the EPSG text in the status bar and click the EPSG radio button after conversion is complete,
                # or else changing the text in the epsg_edit will trigger signals and change the pem_file's CRS.
                self.epsg_edit.setText(str(epsg_code))
                self.epsg_edit.editingFinished.emit()
                self.epsg_rbtn.click()

                self.status_bar.showMessage(f"Process complete. GPS converted to {crs.name}.", 2000)

            self.set_crs(crs)

        crs = self.get_crs()

        if not crs:
            logger.error(f"No CRS.")
            self.message.critical(self, 'Invalid CRS', 'Project CRS is invalid.')
            return

        converter = GPSConversionWidget()
        refs.append(converter)
        converter.open(crs)
        converter.accept_signal.connect(convert_gps)

    def open_gps_share(self, gps_object, source_widget):
        """
        Open the GPSShare widget to select PEMFiles.
        :param gps_object: BaseGPS Object to be shared.
        :param source_widget: PEMInfoWidget object of the file that is being shared.
        """
        def share_gps(mask):
            """
            Add the gps_object to the selected files.
            :param mask: list, mask of which files were selected
            """
            pem_info_widgets = np.array(piws)[mask]  # Filtered PIWs

            with CustomProgressDialog('Sharing GPS...', 0, len(pem_info_widgets)) as dlg:

                # Share each GPS object
                if gps_object == 'all':
                    for widget in pem_info_widgets:
                        if dlg.wasCanceled():
                            break
                        dlg.setLabelText(f"Setting GPS of {widget.pem_file.filepath.name}")

                        # Share the collar and segments if the source is a borehole
                        if source_widget.pem_file.is_borehole():
                            widget.fill_gps_table(source_widget.get_collar().df, widget.collar_table)
                            widget.fill_gps_table(source_widget.get_segments().df, widget.segments_table)
                            widget.gps_object_changed(widget.collar_table, refresh=False)
                            widget.gps_object_changed(widget.segments_table, refresh=False)
                        # Share the line GPS if it's a surface line
                        else:
                            widget.fill_gps_table(source_widget.get_line().df, widget.line_table)
                            widget.gps_object_changed(widget.line_table, refresh=False)

                        # Share the loop
                        widget.fill_gps_table(source_widget.get_loop().df, widget.loop_table)
                        widget.gps_object_changed(widget.loop_table, refresh=True)  # Only refresh at the end
                        dlg += 1

                else:
                    # Detect what kind of GPS object is being shared and share that object.
                    if isinstance(gps_object, TransmitterLoop):
                        for widget in pem_info_widgets:
                            if dlg.wasCanceled():
                                break
                            dlg.setLabelText(f"Setting GPS of {widget.pem_file.filepath.name}")

                            widget.fill_gps_table(gps_object.df, widget.loop_table)
                            widget.gps_object_changed(widget.loop_table, refresh=True)
                            dlg += 1

                    elif isinstance(gps_object, SurveyLine):
                        for widget in pem_info_widgets:
                            if dlg.wasCanceled():
                                break
                            dlg.setLabelText(f"Setting GPS of {widget.pem_file.filepath.name}")

                            widget.fill_gps_table(gps_object.df, widget.line_table)
                            widget.gps_object_changed(widget.line_table, refresh=True)
                            dlg += 1

                    elif isinstance(gps_object, BoreholeCollar):
                        for widget in pem_info_widgets:
                            if dlg.wasCanceled():
                                break
                            dlg.setLabelText(f"Setting GPS of {widget.pem_file.filepath.name}")

                            widget.fill_gps_table(gps_object.df, widget.collar_table)
                            widget.gps_object_changed(widget.collar_table, refresh=True)
                            dlg += 1

                    elif isinstance(gps_object, BoreholeSegments):
                        for widget in pem_info_widgets:
                            if dlg.wasCanceled():
                                break
                            dlg.setLabelText(f"Setting GPS of {widget.pem_file.filepath.name}")

                            widget.fill_gps_table(gps_object.df, widget.segments_table)
                            widget.gps_object_changed(widget.segments_table, refresh=True)
                            dlg += 1

        if gps_object == 'all':
            is_borehole = source_widget.pem_file.is_borehole()
            # Filter PEM files to only include the same survey type as the selected file.
            pem_files, piws = zip(*filter(lambda x: x[0].is_borehole() == is_borehole,
                                          zip(self.pem_files, self.pem_info_widgets)))
        else:
            # Filter the PEM Files and PIWs based on the GPS object
            if isinstance(gps_object, TransmitterLoop):
                pem_files, piws = self.pem_files, self.pem_info_widgets

            elif isinstance(gps_object, SurveyLine):
                pem_files, piws = zip(*filter(lambda x: not x[0].is_borehole(),
                                              zip(self.pem_files, self.pem_info_widgets)))

            elif isinstance(gps_object, BoreholeCollar):
                pem_files, piws = zip(*filter(lambda x: x[0].is_borehole(),
                                              zip(self.pem_files, self.pem_info_widgets)))

            elif isinstance(gps_object, BoreholeSegments):
                pem_files, piws = zip(*filter(lambda x: x[0].is_borehole(),
                                              zip(self.pem_files, self.pem_info_widgets)))
            else:
                pem_files = []

        if len(pem_files) < 2:
            return

        source_index = piws.index(source_widget)

        gps_share = GPSShareWidget()
        refs.append(gps_share)
        gps_share.open(pem_files, source_index)
        gps_share.accept_sig.connect(share_gps)

    def open_channel_table_viewer(self):
        def on_close(channel_table):
            ind = self.channel_tables.index(channel_table)
            print(f"Closing table {ind}")
            del self.channel_tables[ind]

        pem_files, rows = self.get_pem_files(selected=True)
        pem_file = pem_files[0]

        channel_viewer = ChannelTimeViewer(pem_file, parent=self)
        channel_viewer.close_request.connect(on_close)
        self.channel_tables.append(channel_viewer)
        channel_viewer.show()

    def open_grid_planner(self):
        grid_planner = GridPlanner(parent=self, darkmode=self.darkmode)
        refs.append(grid_planner)
        grid_planner.show()

    def open_loop_planner(self):
        loop_planner = LoopPlanner(parent=self, darkmode=self.darkmode)
        refs.append(loop_planner)
        loop_planner.show()

    def open_unpacker(self, folder=None):
        def open_unpacker_dir(folder_dir):
            self.set_project_dir(folder_dir)
            self.move_dir_tree(folder_dir)

        self.unpacker.open_project_folder_sig.connect(open_unpacker_dir)
        if folder:
            self.unpacker.open_folder(folder, project_dir=self.project_dir)
        self.unpacker.show()

    def open_gpx_creator(self):
        gpx_creator = GPXCreator(parent=self)
        refs.append(gpx_creator)
        gpx_creator.show()

    def open_contour_map(self):
        if not self.pem_files:
            logger.warning(f"No PEM files opened.")
            self.status_bar.showMessage(f"No PEM files opened.", 2000)
            return

        elif not any([f.has_any_gps() for f in self.pem_files]):
            logger.warning(f"No GPS found in any file.")
            self.message.information(self, 'Error', 'No file has any GPS to plot.')
            return

        contour_map = ContourMapViewer(parent=self, darkmode=self.darkmode)
        refs.append(contour_map)
        contour_map.open(self.pem_files)

    def open_freq_converter(self):
        freq_converter = FrequencyConverter(parent=self)
        refs.append(freq_converter)
        freq_converter.show()

    def open_gps_converter(self):
        gps_converter = GPSConversionWidget(parent=self)
        refs.append(gps_converter)
        gps_converter.show()

    def open_loop_calculator(self):
        loop_calculator = LoopCalculator(parent=self, darkmode=self.darkmode)
        refs.append(loop_calculator)
        loop_calculator.show()

    def open_station_splitter(self):
        pem_files, rows = self.get_pem_files(selected=True)
        if not self.pem_files:
            logger.warning(f"No PEM files selected.")
            self.status_bar.showMessage(f"No PEM files selected.", 2000)
            return

        pem_file = pem_files[0]

        ss = StationSplitter(pem_file, parent=self)
        refs.append(ss)
        ss.show()

    def open_nrcan_calculator(self):
        """NRCan website for magnetic field values"""
        view = QWebEngineView()
        refs.append(view)
        view.setWindowIcon(get_icon("canada.png"))
        view.setWindowTitle("NRCan Magnetic Field Calculator")
        view.setContentsMargins(0, 0, 0, 0)
        view.setUrl("https://geomag.nrcan.gc.ca/calc/mfcal-en.php")
        view.show()

    def open_dir_tree_context_menu(self, position):
        """
        Right click context menu for directory tree
        :param position: QPoint, position of mouse at time of right-click
        """
        def open_step():
            # Open the Step window at the selected location in the project tree
            path = self.get_current_project_path()

            os.chdir(str(path))
            os.system('cmd /c "step"')

        def create_delivery_folder():
            """
            Gather and copy PEM, STP, and PDF files to a deliverable folder and compress it to a .ZIP file.
            """
            folder_name, ok_pressed = QInputDialog.getText(self, "Select Folder Name", "Folder Name:",
                                                           text=self.project_dir.parent.name)
            if ok_pressed and folder_name:
                path = self.get_current_project_path()
                zip_path = path.joinpath(folder_name.strip())
                if zip_path.exists():
                    response = self.message.question(self, "Existing Directory",
                                                     f"Folder '{folder_name}' already exists. Copy and overwrite files "
                                                     f"to this folder?", self.message.Yes, self.message.No)
                    if response == self.message.No:
                        return

                pem_files = list(path.glob("*.PEM"))
                step_files = list(path.glob("*.STP"))
                pdf_files = list(path.glob("*.PDF"))
                files = np.concatenate([pem_files, step_files, pdf_files])
                if not any(files):
                    self.status_bar.showMessage(f"No processed files found in {path}.", 1500)
                    return

                logger.debug(f"Delivery folder path: {str(zip_path)}")
                zip_path.mkdir(exist_ok=True)

                for file in files:
                    logger.debug(f"Moving {file} to {zip_path.joinpath(file.name)}.")
                    shutil.copyfile(file, zip_path.joinpath(file.name))

                shutil.make_archive(str(zip_path), 'zip', str(zip_path))
                self.status_bar.showMessage(f"{folder_name}.zip created successfully.", 1500)

        def rename():
            """
            Rename the selected folder. Folders usually can't be renamed normally when PEMPro is still open.
            :return: None
            """
            folder_name, ok_pressed = QInputDialog.getText(self, "Select Folder Name", "Folder Name:",
                                                           text=self.project_dir.name)
            if ok_pressed and folder_name:
                path = self.get_current_project_path()
                path.rename(path.with_name(folder_name))

        menu = QMenu()
        menu.addAction('Run Step', open_step)
        menu.addSeparator()
        menu.addAction('Create Delivery Folder', create_delivery_folder)
        menu.addAction('Rename Folder', rename)
        menu.exec_(self.project_tree.viewport().mapToGlobal(position))

    def move_dir_tree(self, dir_path, start_up=False):
        """
        Changes the directory tree to show the dir_path. Will find the nearest folder upward if dir_path is a file
        :param dir_path: Path object or str, directory path of the desired directory
        :return: None
        """
        if not dir_path:
            return

        if not isinstance(dir_path, Path):
            dir_path = Path(dir_path)

        # Find the nearest (moving upwards) folder
        while dir_path.is_file():
            dir_path = dir_path.parent

        model = self.file_sys_model.index(str(dir_path))

        # Set the model to be selected in the tree
        self.project_tree.setCurrentIndex(model)
        self.project_tree.expand(model)

        # Adds a timer or else it doesn't actually scroll to it properly.
        # Two timers are used, first one so it can be quick, another follow-up one when the first one doesn't work /
        # because it was too quick
        QTimer.singleShot(50, lambda: self.project_tree.scrollTo(self.project_tree.currentIndex(),
                                                                 QAbstractItemView.PositionAtCenter))
        QTimer.singleShot(300, lambda: self.project_tree.scrollTo(self.project_tree.currentIndex(),
                                                                 QAbstractItemView.PositionAtCenter))

        # Update the GPS and PEM trees
        self.project_dir_changed(model)

        if start_up is True:
            # Again for when the program just started and needs more time
            QTimer.singleShot(500, lambda: self.project_tree.scrollTo(self.project_tree.currentIndex(),
                                                                     QAbstractItemView.PositionAtCenter))

        self.project_tree.resizeColumnToContents(0)

    def project_dir_changed(self, model):
        """
        Signal slot, changes the project directory to the path clicked in the project_tree
        :param model: signal passed var, QModelIndex
        :return:
        """
        path = Path(self.file_sys_model.filePath(model))

        # Only fill the files lists if the project directory changed
        if str(path) != str(self.project_dir):
            self.project_dir = path
            logger.info(f"New project directory: {str(path)}")
            self.project_dir_edit.setText(str(path))

            self.fill_gps_list()
            self.fill_pem_list()

    def fill_gps_list(self):
        """
        Populate the GPS files list based on the files found in the nearest 'GPS' folder in the project directory
        """
        @stopit.threading_timeoutable(default='timeout')
        def find_gps_files():
            files = list(natsort.os_sorted(self.project_dir.rglob('*.txt')))
            files.extend(natsort.os_sorted(self.project_dir.rglob('*.csv')))
            files.extend(natsort.os_sorted(self.project_dir.rglob('*.gpx')))
            files.extend(natsort.os_sorted(self.project_dir.rglob('*.xlsx')))
            files.extend(natsort.os_sorted(self.project_dir.rglob('*.xls')))
            return files

        def get_filtered_gps(gps_files):
            """
            Filter the list of GPS files based on filepath names from the user inputs in GPSPathFilter.
            :return: list of GPS files.
            """
            def strip(arr):
                """Strips all elements in an array"""
                stripped_arr = []
                for r in arr:
                    stripped_arr.append(r.strip())
                return stripped_arr

            filtered_gps = gps_files

            # Filter the GPS files by file name
            include_files = strip(self.gps_list_filter.include_files_edit.text().split(','))
            exclude_files = strip(self.gps_list_filter.exclude_files_edit.text().split(','))

            # Filter the GPS files by folder names
            include_folders = strip(self.gps_list_filter.include_folders_edit.text().split(','))
            exclude_folders = strip(self.gps_list_filter.exclude_folders_edit.text().split(','))

            # Filter by date
            if self.gps_list_filter.date_filter_cbox.isChecked():
                date = self.gps_list_filter.calendar.selectedDate()
                date_str = f'_{date.month():02d}{date.day():02d}'
                filtered_gps = [p for p in filtered_gps if date_str in str(p.name)]

            # Inclusive files
            if any(include_files):
                filtered_gps = [p for p in filtered_gps if any(
                    [f.lower() in str(p.name).lower() for f in include_files if f]
                )]

            # Exclusive files
            if any(exclude_files):
                filtered_gps = [p for p in filtered_gps if all(
                    [f.lower() not in str(p.name).lower() for f in exclude_files if f]
                )]

            # Inclusive folders
            if any(include_folders):
                filtered_gps = [p for p in filtered_gps if any(
                    [f.lower() in str(p.parent).lower() for f in include_folders if f]
                )]

            # Exclusive folders
            if any(exclude_folders):
                filtered_gps = [p for p in filtered_gps if all(
                    [f.lower() not in str(p.parent).lower() for f in exclude_folders if f]
                )]

            include_exts = strip(self.gps_list_filter.include_exts_edit.text().split(','))
            exclude_exts = strip(self.gps_list_filter.exclude_exts_edit.text().split(','))

            # Filter the PEM files by file extension
            # Inclusive extensions
            if any(include_exts):
                filtered_gps = [p for p in filtered_gps if any(
                    [re.sub(r'[\*\.]', '', f.lower()) == p.suffix.lower()[1:] for f in include_exts if f]
                )]
            # Exclusive extensions
            if any(exclude_exts):
                filtered_gps = [p for p in filtered_gps if all(
                    [re.sub(r'[\*\.]', '', f.lower()) != p.suffix.lower()[1:] for f in exclude_exts if f]
                )]

            # Manually remove the '.txt' file if it exists
            for file in filtered_gps:
                if file.stem == '.txt':
                    filtered_gps.remove(file)
            return filtered_gps

        if not self.project_dir:
            logger.info('No projected directory selected')
            self.status_bar.showMessage('No valid project directory has been selected.', 2000)
            return

        self.gps_list.clear()

        # Try to find a GPS folder, but time out after 0.5 second
        gps_files = find_gps_files(timeout=0.5)

        if gps_files is None:
            return
        elif gps_files == 'timeout':
            logger.warning(f"Searching for GPS files timed out.")
            self.status_bar.showMessage(f"Searching for GPS files timed out.", 1000)
            return
        else:
            self.available_gps = get_filtered_gps(gps_files)
            for file in self.available_gps:
                self.gps_list.addItem(QListWidgetItem(get_extension_icon(file),
                                                      f"{str(file.relative_to(self.project_dir))}"))

    def fill_pem_list(self):
        """
        Populate the pem_list with all *.pem files found in the project_dir.
        """
        @stopit.threading_timeoutable(default='timeout')
        def find_pem_files():
            files = []
            # Find all .PEM, .DMP, and .DMP2 files in the project directory
            files.extend(natsort.os_sorted(list(self.project_dir.rglob('*.PEM'))))
            files.extend(natsort.os_sorted(list(self.project_dir.rglob('*.DMP'))))
            files.extend(natsort.os_sorted(list(self.project_dir.rglob('*.DMP2'))))
            return files

        def get_filtered_pems(pem_files):
            """
            Filter the list of PEM files based on filepath names from the user inputs in PathFilter.
            :return: list of PEM files.
            """
            def strip(arr):
                """Strips all elements in an array"""
                stripped_arr = []
                for r in arr:
                    stripped_arr.append(r.strip())
                return stripped_arr

            filtered_pems = pem_files

            # Filter the PEM files by file name
            include_files = strip(self.pem_list_filter.include_files_edit.text().split(','))
            exclude_files = strip(self.pem_list_filter.exclude_files_edit.text().split(','))

            # Filter the PEM files by folder names
            include_folders = strip(self.pem_list_filter.include_folders_edit.text().split(','))
            exclude_folders = strip(self.pem_list_filter.exclude_folders_edit.text().split(','))

            # Filter by date
            if self.pem_list_filter.date_filter_cbox.isChecked():
                date = self.pem_list_filter.calendar.selectedDate()
                date_str = f'_{date.month():02d}{date.day():02d}'
                filtered_pems = [p for p in filtered_pems if date_str in str(p.name)]

            # Inclusive files
            if any(include_files):
                filtered_pems = [p for p in filtered_pems if any(
                    [f.lower() in str(p.name).lower() for f in include_files if f]
                )]

            # Exclusive files
            if any(exclude_files):
                filtered_pems = [p for p in filtered_pems if all(
                    [f.lower() not in str(p.name).lower() for f in exclude_files if f]
                )]

            # Inclusive folders
            if any(include_folders):
                filtered_pems = [p for p in filtered_pems if any(
                    [f.lower() in str(p.parent).lower() for f in include_folders if f]
                )]

            # Exclusive folders
            if any(exclude_folders):
                filtered_pems = [p for p in filtered_pems if all(
                    [f.lower() not in str(p.parent).lower() for f in exclude_folders if f]
                )]

            include_exts = strip(self.pem_list_filter.include_exts_edit.text().split(','))
            exclude_exts = strip(self.pem_list_filter.exclude_exts_edit.text().split(','))

            # Filter the PEM files by file extension
            # Inclusive extensions
            if any(include_exts):
                filtered_pems = [p for p in filtered_pems if any(
                    [re.sub(r'[\*\.]', '', f.lower()) == p.suffix.lower()[1:] for f in include_exts if f]
                )]
            # Exclusive extensions
            if any(exclude_exts):
                filtered_pems = [p for p in filtered_pems if all(
                    [re.sub(r'[\*\.]', '', f.lower()) != p.suffix.lower()[1:] for f in exclude_exts if f]
                )]

            return filtered_pems

        if not self.project_dir:
            logger.info('No projected directory selected')
            self.status_bar.showMessage('No valid project directory has been selected.', 2000)
            return

        self.pem_list.clear()

        # Try to find .PEM files, but time out after 0.5 seconds
        pem_files = find_pem_files(timeout=0.5)

        if pem_files is None:
            return
        elif pem_files == 'timeout':
            logger.warning(f"Searching for PEM/DMP files timed out.")
            self.status_bar.showMessage(f"Searching for PEM/DMP files timed out.", 1000)
            return
        else:
            self.available_pems = get_filtered_pems(pem_files)
            for file in self.available_pems:
                self.pem_list.addItem(QListWidgetItem(get_extension_icon(file),
                                                      f"{str(file.relative_to(self.project_dir))}"))

    def parse_crs(self, filepath):
        """
        Read and extract CRs information from a .inf or .log file output by pathfinder.
        :param filepath: str
        :return: dict with crs system, zone, and datum
        """
        file = read_file(filepath)
        crs_dict = dict()
        crs_dict['System'] = re.search(r'Coordinate System:\W+(?P<System>.*)', file).group(1)
        crs_dict['Zone'] = re.search(r'Coordinate Zone:\W+(?P<Zone>.*)', file).group(1)
        crs_dict['Datum'] = re.search(r'Datum:\W+(?P<Datum>.*)', file).group(1).split(' (')[0]
        logger.info(f"Parsing INF file {Path(filepath).name}:\n"
                    f"System: {crs_dict['System']}. Zone: {crs_dict['Zone']}. Datum: {crs_dict['Datum']}")
        return crs_dict

    def save_pem_files(self, selected=False):
        """
        Save PEM files.
        :param selected: Bool: if True, saves all opened PEM files instead of only the selected ones.
        """
        pem_files, rows = self.get_pem_files(selected=selected)
        crs = self.get_crs()

        with CustomProgressDialog('Saving PEM Files...', 0, len(pem_files)) as dlg:
            for pem_file in pem_files:
                if dlg.wasCanceled():
                    break

                dlg.setLabelText(f"Saving {pem_file.filepath.name}")

                # Add the CRS note if CRS isn't None
                if crs:
                    pem_file.set_crs(crs)

                # Save the PEM file and refresh it in the table
                pem_file.save()
                self.refresh_pem(pem_file)
                dlg += 1

        self.fill_pem_list()
        self.status_bar.showMessage(f'Save Complete. {len(pem_files)} file(s) saved.', 2000)

    def save_pem_file_as(self):
        """
        Serialize the currently selected PEMFile as a .PEM or .XYZ file.
        """

        def save_pem():
            # Create a copy of the PEM file, then update the copy
            new_pem = pem_file.copy()
            new_pem.filepath = Path(save_path)
            new_pem.save(legacy='legacy' in save_type.lower(), processed='processed' in save_type.lower())

            self.status_bar.showMessage(f'Save Complete. PEM file saved as {new_pem.filepath.name}', 2000)

            # Open the new PEM. If it is already opened, refresh it. This way the file remembers to save as legacy.
            if self.is_opened(new_pem):
                ind = self.pem_files.index(pem_file)
                self.pem_files[ind] = new_pem
                self.refresh_pem(new_pem)
            else:
                self.add_pem_files(new_pem)

            # Refresh the PEM list
            self.fill_pem_list()

        def save_xyz():
            xyz_file = pem_file.to_xyz()
            with open(save_path, 'w+') as file:
                file.write(xyz_file)
                try:
                    os.startfile(save_path)
                except OSError:
                    logger.error(f"Cannot open {Path(save_path).name} because there is no"
                                 f" application associated with it.")

        pem_files, rows = self.get_pem_files(selected=True)
        pem_file = pem_files[0]
        default_path = str(pem_file.filepath)
        save_path, save_type = self.file_dialog.getSaveFileName(self, '', default_path, 'PEM File (*.PEM);; '
                                                                                        'Legacy PEM File (*.PEM);;'
                                                                                        'Processed PEM File (*.PEM);;'
                                                                                        'XYZ File (*.XYZ)')

        if save_path:
            if 'XYZ' in save_type:
                save_xyz()
            else:
                if save_type == "Processed PEM File (*.PEM)":
                    # Make sure there's a valid CRS when doing a final export
                    crs = self.get_crs()
                    if not crs:
                        response = self.message.question(self, 'Invalid CRS',
                                                         'The CRS information is invalid. '
                                                         'Do you wish to proceed with no CRS information?',
                                                         self.message.Yes | self.message.No)
                        if response == self.message.No:
                            self.status_bar.showMessage(f"Cancelled.", 2000)
                            return

                    # Check if there are any suffix or repeat warnings.
                    for warning in ['Suffix\nWarnings', 'Repeat\nWarnings']:
                        if any([self.table.item(row, self.table_columns.index(warning)).text() != '0' for row in rows]):
                            warning_str = re.sub(r'\n', ' ', warning)
                            response = self.message.question(self, warning_str.title(),
                                                             f"One or more files have {warning_str.lower()}.\n"
                                                             "Continue with export?",
                                                             self.message.Yes | self.message.No)
                            if response == self.message.No:
                                self.status_bar.showMessage(f"Cancelled.", 2000)
                                return
                save_pem()

    def make_dxf(self):
        pem_files = self.get_pem_files(selected=False)[0]
        if not pem_files:
            logger.warning(f"No PEM files selected.")
            self.status_bar.showMessage(f"No PEM files selected.", 2000)
            return

        # Get output dir from user
        save_path = self.file_dialog.getExistingDirectory(self, '', str(self.pem_files[-1].filepath.parent))
        # Escape statement
        if not save_path: return

        choices = ("Loop", "Survey Line/Borehole", "Both")
        choice, ok = QInputDialog.getItem(self, "DXF", "DXF Plot Options", choices, 0, False)
        # Escape statement
        if not ok: return

        for pf in pem_files:
            pf: PEMFile
            dwg = PEMDXFDrawing()
            refs.append(dwg)
            if choice == "Loop" or choice == "Both" and not pf.loop.df.empty:
                dwg.add_loop(pf)
            if choice == "Survey Line/Borehole" or choice == "Both":
                # Check if the pem even has a loaded segment or line
                if not pf.segments.df.empty or not pf.line.df.empty:
                    dwg.add_surveyline(pf)
            # Save out to the dir using the PEMFile names
            fname = os.path.splitext(os.path.split(pf.filepath)[-1])[0] + ".dxf"
            outpath = os.path.join(save_path, fname)
            dwg.save_dxf(outpath)

    def copy_pems_to_clipboard(self):
        """
        Copy the information from the selected PEM files to the clipboard, to be entered into the geophysics sheet.
        """
        pem_files, rows = self.get_pem_files(selected=True)

        if not pem_files:
            return

        info = []
        for pem_file in sorted(pem_files, key=lambda x: x.get_date(), reverse=True):
            info.append(pem_file.get_clipboard_info())

        df = pd.DataFrame(info)
        df.to_clipboard(excel=True, index=False, header=False)
        self.status_bar.showMessage(f"Information copied to clipboard", 1500)

    def save_as_kmz(self, save=False):
        """
        Saves all GPS from the opened PEM files as a KMZ file. Utilizes 'simplekml' module.
        :param save: bool, save the file with FileDialog or simply save as a temporary file.
        :return: None
        """
        crs = self.get_crs()

        if not self.pem_files:
            logger.error("No PEM files opened.")
            self.status_bar.showMessage(f"No PEM files opened.", 2000)
            return

        if not any([pem_file.has_any_gps() for pem_file in self.pem_files]):
            logger.error("No GPS found in any PEM file.")
            self.message.information(self, 'No GPS', 'No file has any GPS to save.')
            return

        if not crs:
            logger.error("No CRS.")
            self.message.information(self, 'Invalid CRS', 'GPS coordinate system information is invalid.')
            return

        kml = simplekml.Kml()
        pem_files = [pem_file for pem_file in self.pem_files if pem_file.has_any_gps()]

        line_style = simplekml.Style()
        line_style.linestyle.width = 4
        line_style.linestyle.color = simplekml.Color.magenta

        loop_style = simplekml.Style()
        loop_style.linestyle.width = 4
        loop_style.linestyle.color = simplekml.Color.yellow

        station_style = simplekml.Style()
        station_style.iconstyle.icon.href = 'http://maps.google.com/mapfiles/kml/shapes/placemark_circle.png'
        station_style.iconstyle.color = simplekml.Color.magenta

        trace_style = simplekml.Style()
        trace_style.linestyle.width = 2
        trace_style.linestyle.color = simplekml.Color.magenta

        collar_style = simplekml.Style()
        collar_style.iconstyle.icon.href = 'http://maps.google.com/mapfiles/kml/paddle/wht-stars.png'
        collar_style.iconstyle.color = simplekml.Color.magenta

        loops = []
        loop_ids = []
        loop_names = []

        lines = []
        line_ids = []
        line_names = []

        traces = []
        trace_ids = []
        hole_names = []

        # Grouping up the loops, lines and boreholes into lists.
        for pem_file in pem_files:
            pem_file = pem_file.copy()  # Copy the PEM file so the GPS conversions don't affect the original
            pem_file.set_crs(crs)

            # Save the loop
            loop_gps = pem_file.loop.to_latlon().get_loop(closed=True)
            loop_name = pem_file.loop_name

            if not loop_gps.empty and loop_gps.to_string() not in loop_ids:
                loops.append(loop_gps)
                loop_ids.append(loop_gps.to_string())
                loop_names.append(loop_name)

            # Save the line
            if not pem_file.is_borehole():
                line_gps = pem_file.line.to_latlon().get_line()
                line_name = pem_file.line_name

                if not line_gps.empty and line_gps.to_string() not in line_ids:
                    lines.append(line_gps)
                    line_ids.append(line_gps.to_string())
                    line_names.append(line_name)
            else:
                # Save the borehole collar and trace
                if pem_file.has_collar_gps():
                    pem_file.geometry = BoreholeGeometry(pem_file.collar, pem_file.segments)
                    bh_projection = pem_file.geometry.get_projection(num_segments=100, latlon=True)
                    hole_name = pem_file.line_name
                    if not bh_projection.empty and bh_projection.to_string() not in trace_ids:
                        traces.append(bh_projection)
                        trace_ids.append(bh_projection.to_string())
                        hole_names.append(hole_name)

        # Creates KMZ objects for the loops.
        for loop_gps, name in zip(loops, loop_names):
            ls = kml.newlinestring(name=name)
            ls.coords = loop_gps.loc[:, ['Easting', 'Northing']].to_numpy()
            ls.extrude = 1
            ls.style = loop_style

        # Creates KMZ objects for the lines.
        for line_gps, name in zip(lines, line_names):
            folder = kml.newfolder(name=name)
            new_point = line_gps.apply(
                lambda x: folder.newpoint(name=str(x.Station), coords=[(x.Easting, x.Northing)]), axis=1)
            new_point.style = station_style

            ls = folder.newlinestring(name=name)
            ls.coords = line_gps.loc[:, ['Easting', 'Northing']].to_numpy()
            ls.extrude = 1
            ls.style = trace_style

        # Creates KMZ objects for the boreholes.
        for trace_gps, name in zip(traces, hole_names):
            folder = kml.newfolder(name=name)
            collar = folder.newpoint(name=name, coords=[trace_gps.loc[0, ['Easting', 'Northing']].to_numpy()])
            collar.style = collar_style
            ls = folder.newlinestring(name=name)
            ls.coords = trace_gps.loc[:, ['Easting', 'Northing']].to_numpy()
            ls.extrude = 1
            ls.style = trace_style

        if save:
            # Save the file using the user-input save path
            default_path = str(self.pem_files[-1].filepath.parent)
            save_dir = self.file_dialog.getSaveFileName(self, 'Save KMZ File', default_path, 'KMZ Files (*.KMZ)')[0]
            if save_dir:
                kmz_save_dir = str(Path(save_dir).with_suffix('.kmz'))
                kml.savekmz(kmz_save_dir, format=False)
                # os.startfile(kmz_save_dir)
        else:
            # Save the file and open Google Earth using a temporary file
            google_earth_exe = Path(os.environ["ProgramFiles"]).joinpath(
                r'Google/Google Earth Pro/client/googleearth.exe')
            if google_earth_exe.is_file():
                # Create the temp file
                kmz_save_dir = str(app_data_dir.joinpath("temp.kmz").resolve())  # Gets the absolute path
                # Save the file
                kml.savekmz(kmz_save_dir, format=False)
                # Open Google Earth
                cmd = [str(google_earth_exe), kmz_save_dir]
                subprocess.Popen(cmd)
            else:
                logger.error(f"Cannot find Google Earth Pro.")
                self.message.information(self, "Error", "Cannot find Google Earth Pro.")

    def export_pem_headers(self):
        """
        Export PEMFile information into report-friendly information into a single csv
        """
        pem_files, rows = self.get_pem_files(selected=False)
        if not pem_files:
            logger.error(f"No PEM files opened.")
            self.status_bar.showMessage(f"No PEM files opened.", 2000)
            return

        file_dir = self.file_dialog.getSaveFileName(self, '', str(self.project_dir), 'CSV Files (*.CSV)')[0]

        if file_dir is None:
            return
        dfs = [pf.to_headerdf() for pf in pem_files]
        concated = pd.concat(dfs, axis=0)
        concated.reset_index(drop=True, inplace=True)
        concated.to_csv(file_dir)

    def export_as_xyz(self):
        """
        Save the selected PEM files as XYZ files
        :return: None
        """
        pem_files, rows = self.get_pem_files(selected=False)

        if not pem_files:
            logger.error(f"No PEM files opened.")
            self.status_bar.showMessage(f"No PEM files opened.", 2000)
            return

        file_dir = self.file_dialog.getExistingDirectory(self, '', str(self.project_dir))

        if file_dir:
            with CustomProgressDialog("Exporting XYZ Files...", 0, len(pem_files)) as dlg:

                for pem_file in pem_files:
                    if dlg.wasCanceled():
                        break

                    file_name = str(Path(file_dir).joinpath(pem_file.filepath.name).with_suffix(".XYZ"))
                    dlg.setLabelText(f"Exporting {file_name}")
                    try:
                        xyz_file = pem_file.to_xyz()
                    except Exception as e:
                        logger.critical(f"{e}")
                        self.message.critical(self, 'Error', str(e))
                        continue
                    else:
                        logger.info(F"Exporting {file_name}.")
                        with open(file_name, 'w+') as file:
                            file.write(xyz_file)
                    finally:
                        dlg += 1

    def export_pem_files(self, selected=False, legacy=False, processed=False):
        """
        Saves all PEM files to a desired location (keeps them opened) and removes any tags.
        :param selected: bool, True will only export selected rows.
        :param legacy: bool, Save the PEM Files as legacy format, compatible with Step.
        :param processed: bool, Save the PEM files as processed and legacy format. Will average, split,
        de-rotated (if applicable), and re-name the file names.
        """
        pem_files, rows = self.get_pem_files(selected=selected)
        crs = self.get_crs()

        if not pem_files:
            logger.error(f"No PEM files opened.")
            return

        # Make sure there's a valid CRS when doing a final export
        if processed is True:
            if not crs:
                response = self.message.question(self, 'Invalid CRS',
                                                 'The CRS information is invalid. '
                                                 'Do you wish to proceed with no CRS information?',
                                                 self.message.Yes | self.message.No)
                if response == self.message.No:
                    self.status_bar.showMessage(f"Cancelled.", 2000)
                    return

            # Check if there are any suffix or repeat warnings.
            for warning in ['Suffix\nWarnings', 'Repeat\nWarnings']:
                if any([self.table.item(row, self.table_columns.index(warning)).text() != '0' for row in rows]):
                    warning_str = re.sub(r'\n', ' ', warning)
                    response = self.message.question(self, warning_str.title(),
                                                     f"One or more files have {warning_str.lower()}.\n"
                                                     "Continue with export?",
                                                     self.message.Yes | self.message.No)
                    if response == self.message.No:
                        self.status_bar.showMessage(f"Cancelled.", 2000)
                        return

        file_dir = self.file_dialog.getExistingDirectory(self, '', str(self.project_dir))
        # file_dir = r"C:\Users\Eric\PycharmProjects\PEMPro\sample_files\Raw Boreholes\EB-21-52\Final"
        if not file_dir:
            self.status_bar.showMessage('Cancelled.', 2000)
            return

        with CustomProgressDialog("Exporting PEM Files...", 0, len(pem_files)) as dlg:
            for pem_file, row in zip(pem_files, rows):
                if dlg.wasCanceled():
                    break

                pem_file.set_crs(crs)
                if all([pem_file.is_borehole(), pem_file.has_xy(), not pem_file.is_derotated(), processed is True]):
                    response = self.message.question(self, 'Rotated XY',
                                                     f'File {pem_file.filepath.name} has not been de-rotated. '
                                                     f'Do you wish to automatically de-rotate it?',
                                                     self.message.Yes | self.message.No)
                    if response == self.message.No:
                        continue

                pem_file: PEMFile
                file_name = pem_file.filepath.name
                pem_file = pem_file.copy()
                logger.info(f"Exporting {file_name}.")

                pem_file.filepath = Path(file_dir).joinpath(file_name)
                pem_file.save(legacy=legacy, processed=processed, rename=True)
                dlg += 1

        self.fill_pem_list()
        self.status_bar.showMessage(f"Save complete. {len(pem_files)} PEM file(s) exported", 2000)

    def export_gps(self, selected=False):
        """
        Exports all GPS from all opened PEM files to separate CSV files. Creates folders for each loop.
        Doesn't repeat if a line/hole/loop has been done already.
        :param selected: Bool, only use selected PEM files.
        """
        pem_files, rows = self.get_pem_files(selected=selected)
        if not pem_files:
            logger.warning(f"No PEM files opened.")
            self.status_bar.showMessage(f"No PEM files opened.", 2000)
            return

        crs = self.get_crs()

        if not crs:
            logger.error(f"No CRS.")
            self.message.information(self, 'Invalid CRS', 'CRS is incomplete and/or invalid.')
            return

        loops = []
        lines = []
        collars = []

        default_path = str(pem_files[0].filepath.parent)
        export_folder = self.file_dialog.getExistingDirectory(self, 'Select Destination Folder', default_path)

        if export_folder:
            with CustomProgressDialog("Exporting GPS...", 0, len(pem_files)) as dlg:
                for loop, pem_files in groupby(pem_files, key=lambda x: x.loop_name):
                    if dlg.wasCanceled():
                        break

                    pem_files = list(pem_files)

                    # Creates a new folder for each loop, where each CSV will be saved for that loop.
                    folder = Path(export_folder).joinpath(loop)
                    folder.mkdir(parents=True, exist_ok=True)

                    for pem_file in pem_files:
                        if pem_file.has_loop_gps():
                            loop = pem_file.get_loop(closed=False)
                            if loop.to_string() not in loops:
                                loop_name = pem_file.loop_name
                                logger.info(f"Creating CSV file for loop {loop_name}.")
                                loops.append(loop.to_string())
                                csv_filepath = str(folder.joinpath(loop_name).with_suffix('.csv'))

                                with open(csv_filepath, 'w') as csvfile:
                                    filewriter = csv.writer(csvfile,
                                                            delimiter=',',
                                                            lineterminator='\n',
                                                            quotechar='"',
                                                            quoting=csv.QUOTE_MINIMAL)
                                    filewriter.writerow([f"Loop {loop_name} - {crs.name}"])
                                    filewriter.writerow(['Easting', 'Northing', 'Elevation'])
                                    loop.apply(lambda x: filewriter.writerow([x.Easting, x.Northing, x.Elevation]),
                                               axis=1)

                        if pem_file.has_station_gps():
                            line = pem_file.line.get_line()
                            if line.to_string() not in lines:
                                line_name = pem_file.line_name
                                logger.info(f"Creating CSV file for line {line_name}.")
                                lines.append(line.to_string())
                                csv_filepath = str(folder.joinpath(line_name).with_suffix('.csv'))

                                with open(csv_filepath, 'w') as csvfile:
                                    filewriter = csv.writer(csvfile,
                                                            delimiter=',',
                                                            lineterminator='\n',
                                                            quotechar='"',
                                                            quoting=csv.QUOTE_MINIMAL)
                                    filewriter.writerow([f"Line {line_name} - {crs.name}"])
                                    filewriter.writerow(['Easting', 'Northing', 'Elevation', 'Station Number'])
                                    line.apply(
                                        lambda x: filewriter.writerow([x.Easting, x.Northing, x.Elevation, x.Station]),
                                        axis=1)

                        if pem_file.has_collar_gps():
                            collar = pem_file.get_collar()
                            if collar.to_string() not in collars:
                                hole_name = pem_file.line_name
                                logger.info(f"Creating CSV file for hole {hole_name}.")
                                collars.append(collar.to_string())
                                csv_filepath = str(folder.joinpath(hole_name).with_suffix('.csv'))

                                with open(csv_filepath, 'w') as csvfile:
                                    filewriter = csv.writer(csvfile,
                                                            delimiter=',',
                                                            lineterminator='\n',
                                                            quotechar='"',
                                                            quoting=csv.QUOTE_MINIMAL)
                                    filewriter.writerow([f"Hole {hole_name} - {crs.name}"])
                                    filewriter.writerow(['Easting', 'Northing', 'Elevation'])
                                    collar.apply(lambda x: filewriter.writerow([x.Easting, x.Northing, x.Elevation]),
                                                 axis=1)

                        dlg += 1

            self.status_bar.showMessage("Export complete.", 2000)

    def export_dad(self):
        """
        Export the DAD information of a borehole survey to a CSV file.
        """
        pem_files, rows = self.get_pem_files(selected=True)
        if not pem_files:
            logger.warning(f"No PEM files selected.")
            return

        file_dir = self.file_dialog.getExistingDirectory(self, '', str(self.project_dir))
        if not file_dir:
            self.status_bar.showMessage('Cancelled.', 2000)
            return

        with CustomProgressDialog("Exporting PEM Files...", 0, len(pem_files)) as dlg:
            for pem_file, row in zip(pem_files, rows):
                if dlg.wasCanceled():
                    break
                elif all([not pem_file.is_borehole(), not pem_file.has_geometry(), not pem_file.has_xy()]):
                    dlg += 1
                    continue

                dad = pem_file.get_dad()
                dad.to_csv(Path(file_dir).joinpath(pem_file.filepath.with_suffix('.csv').name),
                           float_format='%.2f',
                           index=False,
                           header=True,
                           na_rep='None')

                dlg += 1

        self.status_bar.showMessage('Export complete.', 1000)

    def extract_component(self, component):
        """
        Create a new PEM file with the only the component selected.
        """
        # pem_files, rows = self.get_pem_files(selected=True)
        pem_files, rows = self.get_pem_files(selected=False)
        if not pem_files:
            logger.warning(f"No PEM files selected.")
            return

        pem_file = pem_files[0]
        if component not in pem_file.get_components():
            self.message.information(self, "Invalid Component", f"{component} is not in {pem_file.filepath.name}.")
            return

        fp = pem_file.filepath
        new_file, ext = self.file_dialog.getSaveFileName(self, 'Output File Name',
                                                         str(fp.with_name(
                                                             fp.stem + ' ' + component + fp.suffix)))

        if new_file:
            new_pem = pem_file.copy()
            new_pem.data = new_pem.data[new_pem.data.Component == component]
            new_pem.filepath = Path(new_file)
            new_pem.save()

            self.fill_pem_list()
            self.status_bar.showMessage(F"{Path(new_file).name} saved successfully.", 1500)

    def reset_selection_labels(self):
        for label in [self.selection_files_label,
                      self.selection_timebase_label,
                      self.selection_zts_label,
                      self.selection_survey_label,
                      self.selection_derotation_label]:
            label.setText("")

    def format_row(self, row):

        def color_row():
            """
            Color cells of the main table based on conditions. Ex: Red text if the PEM file isn't averaged.
            :return: None
            """
            def has_all_gps(piw_widget):
                if piw_widget.pem_file.is_borehole():
                    if any([piw_widget.get_loop().df.dropna().empty,
                            piw_widget.get_collar().df.dropna().empty,
                            piw_widget.get_segments().df.dropna().empty,
                            ]):
                        return False
                    else:
                        return True

                else:
                    if any([piw_widget.get_line().df.dropna().empty,
                            piw_widget.get_loop().df.dropna().empty,
                            ]):
                        return False
                    else:
                        return True

            def color_row_background(row_index, color):
                """
                Color an entire table row
                :param row_index: Int: Row of the table to color
                :param color: str: The desired color
                :return: None
                """
                color = QColor(color)
                color.setAlpha(50)
                for j in range(self.table.columnCount()):
                    self.table.item(row_index, j).setBackground(color)

            average_col = self.table_columns.index('Averaged')
            split_col = self.table_columns.index('Split')
            suffix_col = self.table_columns.index('Suffix\nWarnings')
            repeat_col = self.table_columns.index('Repeat\nWarnings')
            polarity_col = self.table_columns.index('Polarity\nWarnings')
            pem_has_gps = has_all_gps(self.pem_info_widgets[row])

            if not pem_has_gps:
                color_row_background(row, 'blue')

            for col in [average_col, split_col, suffix_col, repeat_col, polarity_col]:
                item = self.table.item(row, col)
                if item:
                    value = item.text()
                    if col == average_col:
                        if value == 'False':
                            item.setForeground(QColor('red'))
                        # else:
                        #     item.setForeground(QColor('black'))
                    elif col == split_col:
                        if value == 'False':
                            item.setForeground(QColor('red'))
                        # else:
                        #     item.setForeground(QColor('black'))
                    elif col == suffix_col:
                        if int(value) > 0:
                            item.setBackground(QColor('red'))
                            item.setForeground(QColor('white'))
                    elif col == repeat_col:
                        if int(value) > 0:
                            item.setBackground(QColor('red'))
                            item.setForeground(QColor('white'))
                    elif col == polarity_col:
                        if re.match("[XYZ]", value):
                            item.setBackground(QColor('red'))
                            item.setForeground(QColor('white'))

        def color_anomalies():
            """
            Change the text color of table cells where the value warrants attention. An example of this is where the
            date might be wrong.
            """
            date_column = self.table_columns.index('Date')
            current_year = str(datetime.datetime.now().year)
            dark_mode = self.darkmode
            red_color = QColor("#FFC0C0" if dark_mode else "#FF4040")
            default_color = Qt.white if dark_mode else Qt.black

            for row in range(self.table.rowCount()):
                if self.table.item(row, date_column):
                    date = self.table.item(row, date_column).text()
                    year = str(date.split(' ')[-1])
                    if year != current_year:
                        self.table.item(row, date_column).setForeground(red_color)
                    else:
                        self.table.item(row, date_column).setForeground(default_color)

        def color_changes():
            """
            Bolden table cells where the value in the cell is different then what is the PEM file memory.
            """
            bold_font, normal_font = QFont(), QFont()
            bold_font.setBold(True)
            normal_font.setBold(False)

            # Get the original information in the PEM file
            row_info = [
                pem_file.filepath.name,
                pem_file.date,
                pem_file.client,
                pem_file.grid,
                pem_file.line_name,
                pem_file.loop_name,
                pem_file.current,
                pem_file.coil_area,
                pem_file.get_stations(converted=True).min(),
                pem_file.get_stations(converted=True).max(),
                pem_file.is_averaged(),
                pem_file.is_split(),
                str(len(pem_file.get_suffix_warnings())),
                str(len(pem_file.get_repeats()))
            ]

            # If the value in the table is different then in the PEM file, make the value bold.
            for column in range(self.table.columnCount()):
                if self.table.item(row, column):
                    original_value = str(row_info[column])
                    if self.table.item(row, column).text() != original_value:
                        self.table.item(row, column).setFont(bold_font)
                    else:
                        self.table.item(row, column).setFont(normal_font)

        self.table.blockSignals(True)

        pem_file = self.pem_files[row]
        color_row()
        color_anomalies()

        if self.allow_signals:
            self.table.blockSignals(False)

    def color_table_by_values(self):
        """
        Color the background of the cells based on their values for the current, coil area, and station ranges.
        """
        if not self.pem_files:
            return

        self.table.blockSignals(True)
        mpl_red, mpl_blue = np.array([34, 79, 214]) / 256, np.array([247, 42, 42]) / 256
        alpha = 250

        def color_currents():
            current_col = self.table_columns.index("Current")
            currents = np.array([self.table.item(row, current_col).text() for row in range(self.table.rowCount())],
                                dtype=float)

            # Normalize column values for color mapping
            mn, mx, count = currents.min(), currents.max(), len(currents)
            norm = plt.Normalize(mn, mx)

            # Create a custom color map
            cm = LCMap.from_list('Custom', [mpl_red, mpl_blue])

            # Apply the color map to the values in the column
            colors = cm(norm(currents))

            for row in range(self.table.rowCount()):
                item = self.table.item(row, current_col)

                # Color the text
                item.setForeground(QColor(255, 255, 255))
                item.setTextAlignment(Qt.AlignCenter)

                # Color the background based on the value
                color = QColor(colors[row][0] * 255,
                               colors[row][1] * 255,
                               colors[row][2] * 255,
                               alpha)
                item.setBackground(color)

                count += 1

        def color_coil_areas():
            coil_area_col = self.table_columns.index("Coil\nArea")
            coil_areas = np.array([self.table.item(row, coil_area_col).text() for row in range(self.table.rowCount())],
                                  dtype=float)

            # Normalize column values for color mapping
            mn, mx, count = coil_areas.min(), coil_areas.max(), len(coil_areas)
            norm = plt.Normalize(mn, mx)

            # Create a custom color map
            cm = LCMap.from_list('Custom', [mpl_red, mpl_blue])

            # Apply the color map to the values in the column
            colors = cm(norm(coil_areas))

            for row in range(self.table.rowCount()):
                item = self.table.item(row, coil_area_col)

                # Color the text
                item.setForeground(QColor(255, 255, 255))
                item.setTextAlignment(Qt.AlignCenter)

                # Color the background based on the value
                color = QColor(colors[row][0] * 255,
                                     colors[row][1] * 255,
                                     colors[row][2] * 255,
                                     alpha)
                item.setBackground(color)

                count += 1

        def color_station_starts():
            start_col = self.table_columns.index("First\nStation")

            station_starts = np.array([self.table.item(row, start_col).text() for row in range(self.table.rowCount())],
                                      dtype=float)

            # Normalize column values for color mapping
            mn, mx, count = station_starts.min(), station_starts.max(), len(station_starts)
            norm = plt.Normalize(mn, mx)

            # Create a custom color map
            cm = LCMap.from_list('Custom', [mpl_red, mpl_blue])

            # Apply the color map to the values in the column
            colors = cm(norm(station_starts))

            for row in range(self.table.rowCount()):
                item = self.table.item(row, start_col)

                # Color the text
                item.setForeground(QColor(255, 255, 255))
                item.setTextAlignment(Qt.AlignCenter)

                # Color the background based on the value
                color = QColor(colors[row][0] * 255,
                                     colors[row][1] * 255,
                                     colors[row][2] * 255,
                                     alpha)
                item.setBackground(color)

                count += 1

        def color_station_ends():
            end_col = self.table_columns.index("Last\nStation")

            station_ends = np.array([self.table.item(row, end_col).text() for row in range(self.table.rowCount())],
                                      dtype=float)

            # Normalize column values for color mapping
            mn, mx, count = station_ends.min(), station_ends.max(), len(station_ends)
            norm = plt.Normalize(mn, mx)

            # Create a custom color map
            cm = LCMap.from_list('Custom', [mpl_red, mpl_blue])

            # Apply the color map to the values in the column
            colors = cm(norm(station_ends))

            for row in range(self.table.rowCount()):
                item = self.table.item(row, end_col)

                # Color the text
                item.setForeground(QColor(255, 255, 255))
                item.setTextAlignment(Qt.AlignCenter)

                # Color the background based on the value
                color = QColor(colors[row][0] * 255,
                                     colors[row][1] * 255,
                                     colors[row][2] * 255,
                                     alpha)
                item.setBackground(color)

                count += 1

        color_currents()
        color_coil_areas()
        color_station_starts()
        color_station_ends()

        self.table.blockSignals(False)

    def add_pem_to_table(self, pem_file, row):
        """
        Adds the information from a PEM file to the main table. Blocks the table signals while doing so.
        :param pem_file: PEMFile object
        :param row: int, row of the PEM file in the table
        :return: None
        """
        logger.info(f"Adding {pem_file.filepath.name} to the table.")
        self.table.blockSignals(True)

        # Get the information for each column
        row_info = [
            pem_file.filepath.name,
            pem_file.date,
            pem_file.client,
            pem_file.grid,
            pem_file.line_name,
            pem_file.loop_name,
            pem_file.current,
            pem_file.coil_area,
            pem_file.get_stations(converted=True).min(),
            pem_file.get_stations(converted=True).max(),
            pem_file.is_averaged(),
            pem_file.is_split(),
            len(pem_file.get_suffix_warnings()),
            len(pem_file.get_repeats()),
            "N/A" if not pem_file.has_all_gps() else ', '.join(pem_file.get_reversed_components())
        ]

        # Set the information into each cell. Columns from First Station and on can't be edited.
        for i, info in enumerate(row_info):
            item = QTableWidgetItem(str(info))
            item.setTextAlignment(Qt.AlignCenter)
            # Disable editing of columns past First Station and for the date
            if i > self.table_columns.index('Coil\nArea') or i == self.table_columns.index('Date'):
                item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            self.table.setItem(row, i, item)

        self.format_row(row)

        if self.allow_signals:
            self.table.blockSignals(False)

    def refresh_table(self):
        for row in range(self.table.rowCount()):
            self.format_row(row)
        self.color_table_by_values()

    def refresh_pem(self, pem_file):
        """
        Refresh the PEM file by re-opening its PIW and refreshing the information in its row in PEMHub.
        File must be in the list of PEM Files opened in PEMHub (cannot be a copy).
        :param pem_file: PEMFile object
        """
        if pem_file in self.pem_files:
            logger.info(f"Refreshing {pem_file.filepath.name}.")
            ind = self.pem_files.index(pem_file)
            self.pem_info_widgets[ind].open_file(pem_file)
            self.add_pem_to_table(pem_file, ind)
            self.format_row(ind)
            self.color_table_by_values()
        else:
            logger.error(f"PEMFile ID {id(pem_file)} is not in the table.")
            raise IndexError(f"PEMFile ID {id(pem_file)} is not in the table.")

    def backup_files(self):
        """
        Create a backup (.bak) file for each opened PEM file, saved in a backup folder.
        :return: None
        """
        logger.info(f"Backing up PEM files.")
        for pem_file in self.pem_files:
            pem_file.save(backup=True)
        self.status_bar.showMessage(f'Backup complete. Backed up {len(self.pem_files)} PEM files.', 2000)

    def get_current_project_path(self):
        """
        Return the path of the selected directory tree item.
        :return: Path object, filepath
        """
        index = self.project_tree.currentIndex()
        index_item = self.file_sys_model.index(index.row(), 0, index.parent())
        path = self.file_sys_model.filePath(index_item)
        return Path(path)

    def get_pem_files(self, selected=False):
        """
        Return the PEMFiles in the project. If selected is True, will only return the files selected in the table,
        otherwise returns all opened PEMFiles.
        :param selected: bool, return PEMFiles which are selected in the table
        :return: tuple, list of PEMFiles and list of their corresponding rows in the table.
        """
        if selected is False:
            pem_files, rows = self.pem_files, np.arange(self.table.rowCount())
            return pem_files, rows
        
        else:
            selected_pem_files = []
            rows = [model.row() for model in self.table.selectionModel().selectedRows()]

            if rows:
                rows.sort(reverse=True)
                for row in rows:
                    selected_pem_files.append(self.pem_files[row])

            return selected_pem_files, rows

    def get_epsg(self):
        """
        Return the EPSG code currently selected. Will convert the drop boxes to EPSG code.
        :return: str, EPSG code
        """

        def convert_to_epsg():
            """
            Convert and return the EPSG code of the project CRS combo boxes
            :return: str
            """
            system = self.gps_system_cbox.currentText()
            zone = self.gps_zone_cbox.currentText()
            datum = self.gps_datum_cbox.currentText()

            if system == '':
                return None

            elif system == 'Lat/Lon':
                return '4326'

            else:
                if not zone or not datum:
                    return None

                s = zone.split()
                zone_number = int(s[0])
                north = True if s[1] == 'North' else False

                if datum == 'WGS 1984':
                    if north:
                        epsg_code = f'326{zone_number:02d}'
                    else:
                        epsg_code = f'327{zone_number:02d}'
                elif datum == 'NAD 1927':
                    epsg_code = f'267{zone_number:02d}'
                elif datum == 'NAD 1983':
                    epsg_code = f'269{zone_number:02d}'
                else:
                    logger.warning(f"CRS string not implemented.")
                    print(f"CRS string not implemented.")
                    return None

                return epsg_code

        if self.epsg_rbtn.isChecked():
            epsg_code = self.epsg_edit.text()
        else:
            epsg_code = convert_to_epsg()

        return epsg_code

    def get_crs(self):
        """
        Return a CRS object based on the CRS information in the PEM Editor window
        :return: CRS object
        """
        epsg_code = self.get_epsg()
        if epsg_code:
            try:
                crs = CRS.from_epsg(epsg_code)
            except Exception as e:
                logger.error(f"{e}.")
                self.error.showMessage(f"Invalid EPSG code: {str(e)}")
            else:
                logger.debug(f"Project CRS: {crs.name}")
                return crs
        else:
            return None

    def read_inf_file(self, inf_file):
        """
        Parses a .INF file to extract the CRS information in ti and set the CRS drop-down values.
        :param inf_file: str, .INF filepath
        """
        crs_dict = self.parse_crs(inf_file)
        coord_sys = crs_dict.get('System').strip()
        coord_zone = crs_dict.get('Zone').strip()
        datum = crs_dict.get('Datum').strip()
        logger.info(f"Reading INF file {Path(inf_file).name}.\nSystem: {coord_sys}, Datum: {datum}, Zone: {coord_zone}")
        if all([coord_sys in [self.gps_system_cbox.itemText(i) for i in range(self.gps_system_cbox.count())],
                # coord_zone in [self.gps_zone_cbox.itemText(i) for i in range(self.gps_zone_cbox.count())],  # Isn't populated until later
                datum in [self.gps_datum_cbox.itemText(i) for i in range(self.gps_datum_cbox.count())]]):
            self.gps_system_cbox.setCurrentText(coord_sys)
            self.gps_datum_cbox.setCurrentText(datum)
            self.gps_zone_cbox.setCurrentText(coord_zone)

    def set_crs(self, crs):
        """
        Set the project's CRS
        :param crs: pyproj CRS object
        """
        if crs:
            name = crs.name
            logger.debug(F"Setting project CRS to {name} (EPSG {crs.to_epsg()}).")
            self.epsg_edit.setText(str(crs.to_epsg()))

            if name == 'WGS 84':
                datum = 'WGS 1984'
                system = 'Lat/Lon'
                zone = None

            elif 'UTM' in name:
                system = 'UTM'
                sc = name.split(' / ')
                datum = re.sub(r'\s+', '', sc[0])  # Remove any spaces
                if datum == 'WGS84':
                    datum = 'WGS 1984'
                elif datum == 'NAD83':
                    datum = 'NAD 1983'
                elif datum == 'NAD27':
                    datum = 'NAD 1927'
                else:
                    self.epsg_rbtn.click()
                    return

                zone = sc[1].split(' ')[-1]
                zone_number = zone[:-1]
                north = 'North' if zone[-1] == 'N' else 'South'
                zone = f'{zone_number} {north}'
            else:
                logger.info(f"{name} parsing is not currently implemented.")
                return

            self.gps_system_cbox.setCurrentText(system)
            self.gps_datum_cbox.setCurrentText(datum)
            if zone:
                self.gps_zone_cbox.setCurrentText(zone)

            if self.epsg_rbtn.isChecked():
                self.gps_system_cbox.setEnabled(False)
                self.gps_datum_cbox.setEnabled(False)
                self.gps_zone_cbox.setEnabled(False)

        self.status_bar.showMessage(f"CRS information changed to {crs.name}.", 2000)

    def set_dark_mode(self):
        self.darkmode = self.actionDark_Theme.isChecked()
        self.app.setPalette(dark_palette if self.darkmode else light_palette)
        pg.setConfigOption('background', get_line_color("background", "pyqt", self.darkmode))
        pg.setConfigOption('foreground', get_line_color("foreground", "pyqt", self.darkmode))

        text_color = f"rgb{str(tuple(get_line_color('single_blue', 'mpl', self.darkmode)))}"
        self.selection_files_label.setStyleSheet(f'color: {text_color}')
        self.selection_timebase_label.setStyleSheet(f'color: {text_color}')
        self.selection_zts_label.setStyleSheet(f'color: {text_color}')
        self.selection_survey_label.setStyleSheet(f'color: {text_color}')
        self.selection_derotation_label.setStyleSheet(f'color: {text_color}')

        for piw in self.pem_info_widgets:
            piw.darkmode = self.darkmode

        self.refresh_table()

    def set_project_dir(self, path=None):
        """
        Move the directory tree and fill the project directory filepath
        """
        if path is None:
            path = Path(self.project_dir_edit.text())

        if path.exists():
            self.move_dir_tree(Path(path))
            if self.project_dir_edit.text != str(path):
                self.project_dir_edit.setText(str(path))
        else:
            logger.error(f"{str(path)} does not exist.")
            self.message.information(self, "Invalid Path", f"{str(path)} does not exist.")
            self.project_dir_edit.setText(str(self.get_current_project_path()))
        self.fill_pem_list()
        self.fill_gps_list()

    def average_pem_data(self, selected=False):
        """
        Average the data of each PEM File selected
        :param selected: bool, True will only export selected rows.
        """
        pem_files, rows = self.get_pem_files(selected=selected)
        if not pem_files:
            logger.error(f"No PEM files opened.")
            self.status_bar.showMessage(f"No PEM files opened.", 2000)
            return

        pem_files = [f for f in pem_files if not f.is_averaged()]
        if not pem_files:
            logger.error(f"No un-averaged PEM files opened.")
            self.status_bar.showMessage(f"No un-averaged PEM files opened.", 2000)
            return

        with CustomProgressDialog('Averaging PEM Files...', 0, len(pem_files)) as dlg:
            for pem_file in pem_files:
                if dlg.wasCanceled():
                    break

                dlg.setLabelText(f"Averaging {pem_file.filepath.name}")

                if pem_file.is_borehole() and pem_file.has_xy() and not pem_file.is_derotated():
                    logger.warning(f"{pem_file.filepath.name} is a borehole file with rotated XY data.")
                    response = self.message.question(self, 'Rotated PEM File',
                                                     f"{pem_file.filepath.name} has not been de-rotated. "
                                                     f"Continue with averaging?",
                                                     self.message.Yes, self.message.No)
                    if response == self.message.Yes:
                        pass
                    else:
                        continue

                # Save a backup of the un-averaged file first
                if self.auto_create_backup_files_cbox.isChecked():
                    pem_file.save(backup=True, tag='[-A]')

                pem_file = pem_file.average()
                self.refresh_pem(pem_file)
                dlg += 1

        self.status_bar.showMessage(f"Process complete. {len(pem_files)} PEM files averaged.", 2000)

    def split_pem_channels(self, selected=False):
        """
        Removes the on-time channels of each selected PEM File
        :param selected: bool, True will only export selected rows.
        """
        pem_files, rows = self.get_pem_files(selected=selected)

        if not pem_files:
            logger.warning(f"No PEM files opened.")
            self.status_bar.showMessage(f"No PEM files opened.", 2000)
            return

        # Filter the pem_files to only keep un-averaged files
        filt_list = [f for f in pem_files if not f.is_split()]

        if len(filt_list) == 0:
            logger.warning(f"No un-split PEM files opened.")
            self.status_bar.showMessage(f"No un-split PEM files opened.", 2000)
            return

        with CustomProgressDialog('Splitting PEM Files...', 0, len(filt_list)) as dlg:
            for pem_file in filt_list:
                if dlg.wasCanceled():
                    break

                dlg.setLabelText(f"Splitting channels for {pem_file.filepath.name}")

                # Save a backup file
                if self.auto_create_backup_files_cbox.isChecked():
                    pem_file.save(backup=True, tag='[-S]')

                pem_file = pem_file.split()
                self.refresh_pem(pem_file)
                dlg += 1

        self.status_bar.showMessage(f"Process complete. {len(filt_list)} PEM files split.", 2000)

    def scale_pem_coil_area(self, coil_area=None, selected=False):
        """
        Scales the data according to the coil area change
        :param coil_area: int:  coil area to scale to
        :param selected: bool, True will only export selected rows.
        """
        pem_files, rows = self.get_pem_files(selected=selected)
        if not pem_files:
            logger.warning(f"No PEM files opened.")
            self.status_bar.showMessage(f"No PEM files opened.", 2000)
            return

        if not coil_area:
            default = pem_files[0].coil_area
            coil_area, ok_pressed = QInputDialog.getInt(self, "Set Coil Areas", "Coil Area:", value=default)
            # coil_area, ok_pressed = QInputDialog.getInt(self, "Set Coil Areas", "Coil Area:", QLineEdit.Normal, default)
            # coil_area, ok_pressed = QInputDialog.getInt(self, "Set Coil Areas", "Coil Area:", default, -1e6, 1e6, 50)
            if not ok_pressed:
                return

        with CustomProgressDialog('Scaling PEM File Coil Area...', 0, len(pem_files)) as dlg:
            for pem_file, row in zip(pem_files, rows):
                if dlg.wasCanceled():
                    break
                dlg.setLabelText(f"Scaling coil area of {pem_file.filepath.name}")

                pem_file = pem_file.scale_coil_area(coil_area)
                self.refresh_pem(pem_file)
                dlg += 1

        self.status_bar.showMessage(f"Process complete. "
                                    f"Coil area of {len(pem_files)} PEM files scaled to {coil_area}.", 2000)

    def scale_pem_current(self, selected=False):
        """
        Scale the data by current for the selected PEM Files
        :param selected: bool, True will only export selected rows.
        :return: None
        """
        pem_files, rows = self.get_pem_files(selected=selected)
        if not pem_files:
            logger.warning(f"No PEM files opened.")
            self.status_bar.showMessage(f"No PEM files opened.", 2000)
            return

        default = pem_files[0].current
        current, ok_pressed = QInputDialog.getDouble(self, "Scale Current", "Current:", default)
        if ok_pressed:
            with CustomProgressDialog('Scaling PEM File Current...', 0, len(pem_files)) as dlg:
                for pem_file, row in zip(pem_files, rows):
                    dlg.setLabelText(f"Scaling current of {pem_file.filepath.name}")

                    pem_file = pem_file.scale_current(current)
                    self.refresh_pem(pem_file)
                    dlg += 1

            self.status_bar.showMessage(f"Process complete. "
                                        f"Current of {len(pem_files)} PEM files scaled to {current}.", 2000)

    def mag_offset_lastchn(self, selected=False):
        """
        Offset the amplitude of the last channel (assumed to be mag) from each channel in the selected PEM files.
        """
        pem_files, rows = self.get_pem_files(selected=selected)

        if not pem_files:
            logger.warning(f"No PEM files opened.")
            self.status_bar.showMessage(f"No PEM files opened.", 2000)
            return

        with CustomProgressDialog(f'Mag offsetting to last channel...', 0, len(pem_files)) as dlg:
            for pem_file, row in zip(pem_files, rows):
                dlg.setLabelText(f"Mag offsetting data of {pem_file.filepath.name}")
                pem_file: PEMFile
                pem_file = pem_file.mag_offset()
                self.refresh_pem(pem_file)
                dlg += 1

        self.status_bar.showMessage(f"Process complete. "
                                    f"Mag offset of {len(pem_files)} PEM file(s) complete.", 2000)

    def reverse_component_data(self, comp, selected=False):
        """
        Reverse the polarity of all data of a given component for all opened PEM files.
        :param comp: str, either Z, X, or Y
        :param selected: bool, only use selected PEMFiles or not.
        """
        pem_files, rows = self.get_pem_files(selected=selected)

        if not pem_files:
            logger.warning(f"No PEM files opened.")
            self.status_bar.showMessage(f"No PEM files opened.", 2000)
            return

        with CustomProgressDialog(f'Reversing {comp} Component Polarity...', 0, len(pem_files)) as dlg:
            for pem_file, row in zip(pem_files, rows):
                dlg.setLabelText(f"Reversing {comp} component data of {pem_file.filepath.name}")
                pem_file = pem_file.reverse_component(comp)
                self.refresh_pem(pem_file)
                dlg += 1

        self.status_bar.showMessage(f"Process complete. "
                                    f"{comp.upper()} of {len(pem_files)} PEM file(s) reversed.", 2000)

    def reverse_station_order(self, selected=False):
        pem_files, rows = self.get_pem_files(selected=selected)

        if not pem_files:
            logger.warning(f"No PEM files opened.")
            self.status_bar.showMessage(f"No PEM files opened.", 2000)
            return

        with CustomProgressDialog('Reversing Station Order...', 0, len(pem_files)) as dlg:
            for pem_file, row in zip(pem_files, rows):
                dlg.setLabelText(f"Reversing station order of {pem_file.filepath.name}")
                pem_file = pem_file.reverse_station_order()
                self.refresh_pem(pem_file)
                dlg += 1

        self.status_bar.showMessage(f"Process complete. "
                                    f"Station order of {len(pem_files)} PEM file(s) reversed.", 2000)

    # def auto_merge_pem_files(self):
    #
    #     def merge_pems(pem_files):
    #         """
    #         Merge the list of PEM files into a single PEM file.
    #         :param pem_files: list, PEMFile objects.
    #         :return: single PEMFile object
    #         """
    #         if isinstance(pem_files, list) and len(pem_files) > 1:
    #             logger.info(f"Merging {', '.join([f.filepath.name for f in pem_files])}.")
    #             # Data merging section
    #             currents = [pem_file.current for pem_file in pem_files]
    #             coil_areas = [pem_file.coil_area for pem_file in pem_files]
    #
    #             # If any currents are different
    #             if not all([current == currents[0] for current in currents]):
    #                 response = self.message.question(self, 'Warning - Different currents',
    #                                                  f"{', '.join([f.filepath.name for f in pem_files])} do not have "
    #                                                  f"the same current. Proceed with merging anyway?",
    #                                                  self.message.Yes | self.message.No)
    #                 if response == self.message.No:
    #                     self.status_bar.showMessage('Aborted.', 2000)
    #                     return
    #
    #             # If any coil areas are different
    #             if not all([coil_area == coil_areas[0] for coil_area in coil_areas]):
    #                 response = self.message.question(self, 'Warning - Different coil areas',
    #                                                  f"{', '.join([f.filepath.name for f in pem_files])} do not have "
    #                                                  f"the same coil area. Proceed with merging anyway?",
    #                                                  self.message.Yes | self.message.No)
    #                 if response == self.message.No:
    #                     self.status_bar.showMessage('Aborted.', 2000)
    #                     return
    #
    #             # If the files aren't all split or un-split
    #             if any([pem_file.is_split() for pem_file in pem_files]) and any(
    #                     [not pem_file.is_split() for pem_file in pem_files]):
    #                 response = self.message.question(self, 'Warning - Different channel split states',
    #                                                  'There is a mix of channel splitting in the selected files. '
    #                                                  'Would you like to split the unsplit file(s) '
    #                                                  'and proceed with merging?',
    #                                                  self.message.Yes | self.message.No)
    #                 if response == self.message.Yes:
    #                     for pem_file in pem_files:
    #                         pem_file = pem_file.split()
    #                 else:
    #                     return
    #
    #             # If the files aren't all de-rotated
    #             if any([pem_file.is_derotated() for pem_file in pem_files]) and any(
    #                     [not pem_file.is_derotated() for pem_file in pem_files]):
    #                 self.message.information(self, 'Error - Different states of XY de-rotation',
    #                                          'There is a mix of XY de-rotation in the selected files.')
    #
    #             merged_pem = pem_files[0].copy()
    #             merged_pem.data = pd.concat([pem_file.data for pem_file in pem_files], axis=0, ignore_index=True)
    #             merged_pem.number_of_readings = sum([f.number_of_readings for f in pem_files])
    #             merged_pem.is_merged = True
    #
    #             # Add the M tag
    #             if '[M]' not in pem_files[0].filepath.name:
    #                 merged_pem.filepath = merged_pem.filepath.with_name(
    #                     merged_pem.filepath.stem + '[M]' + merged_pem.filepath.suffix)
    #
    #             merged_pem.save()
    #             return merged_pem
    #
    #     files_to_open = []
    #     files_to_remove = []
    #
    #     if not self.pem_files:
    #         logger.warning(f"No PEM files opened.")
    #         self.status_bar.showMessage(f"No PEM files opened.", 2000)
    #         return
    #
    #     pem_files, rows = copy.deepcopy(self.pem_files), np.arange(self.table.rowCount())
    #
    #     bh_files = [f for f in pem_files if f.is_borehole()]
    #     sf_files = [f for f in pem_files if f not in bh_files]
    #
    #     # Merge surface files
    #     # Group the files by loop name
    #     for loop, loop_files in groupby(sf_files, key=lambda x: x.loop_name):
    #         loop_files = list(loop_files)
    #         logger.info(f"Auto merging loop {loop}.")
    #
    #         # Group the files by line name
    #         for line, line_files in groupby(loop_files, key=lambda x: x.line_name):
    #             line_files = list(line_files)
    #             if len(line_files) > 1:
    #                 logger.info(f"Auto merging line {line}: {[f.filepath.name for f in line_files]}.")
    #
    #                 # Merge the files
    #                 merged_pem = merge_pems(line_files)
    #
    #                 if merged_pem is not None:
    #                     files_to_open.append(merged_pem)
    #                     files_to_remove.extend(line_files)
    #
    #     # Merge borehole files
    #     # Group the files by loop
    #     for loop, loop_files in groupby(bh_files, key=lambda x: x.loop_name):
    #         loop_files = list(loop_files)
    #
    #         # Group the files by hole name
    #         for hole, hole_files in groupby(loop_files, key=lambda x: x.line_name):
    #             hole_files = sorted(list(hole_files), key=lambda x: x.get_components())
    #
    #             # Group the files by their components
    #             for components, comp_files in groupby(hole_files, key=lambda x: x.get_components()):
    #                 comp_files = list(comp_files)
    #                 if len(comp_files) > 1:
    #                     logger.info(f"Auto merging hole {hole}: {[f.filepath.name for f in comp_files]}")
    #
    #                     # Merge the files
    #                     merged_pem = merge_pems(comp_files)
    #
    #                     if merged_pem is not None:
    #                         files_to_open.append(merged_pem)
    #                         files_to_remove.extend(comp_files)
    #
    #     rows = [pem_files.index(f) for f in files_to_remove]
    #
    #     if self.delete_merged_files_cbox.isChecked():
    #         logger.warning(f"Removing rows {', '.join(rows)}.")
    #         self.remove_pem_file(rows=rows)
    #
    #     self.add_pem_files(files_to_open)

    def auto_name_lines(self):
        """
        Rename the line and hole names based on the file name. For boreholes, looks for a space character, and uses
        everything before the space (if it exists) as the new name. If there's no space it will use the entire filename
        (minus the extension) as the new name. For surface, it looks for numbers followed by any suffix (NSEW) and uses
        that (with the suffix) as the new name. Makes the change in the table and saves it in the PEM file in memory.
        :return: None
        """
        if not self.pem_files:
            logger.warning(f"No PEM files opened.")
            self.status_bar.showMessage(f"No PEM files opened.", 2000)
            return

        file_name_column = self.table_columns.index('File')
        line_name_column = self.table_columns.index('Line/Hole')
        new_name = ''
        for row in range(self.table.rowCount()):
            pem_file = self.pem_files[row]
            file_name = self.table.item(row, file_name_column).text()
            if pem_file.is_borehole():
                # hole_name = re.findall('(.*)(xy|XY|z|Z)', file_name)
                hole_name = os.path.splitext(file_name)
                if hole_name:
                    new_name = re.split(r'\s', hole_name[0])[0]
            else:
                line_name = re.findall(r'\d+[nsewNSEW]', file_name)
                if line_name:
                    new_name = line_name[0].strip()

            name_item = QTableWidgetItem(new_name)
            name_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, line_name_column, name_item)


class PathFilter(QWidget):
    accept_sig = Signal()

    def __init__(self, filetype, parent=None):
        """
        Widget that holds the filepath filtering information for the GPS list in PEMHub.
        :param filetype: str, either 'PEM' or 'GPS'. 
        :param parent: Qt widget object.
        """
        super().__init__()
        self.filetype = filetype
        self.parent = parent
        self.setWindowTitle(f"{filetype} File Filter")
        self.setWindowIcon(get_icon('filter.png'))

        self.include_files_edit = QLineEdit()
        self.include_files_edit.setToolTip("Separate items with commas [,]")

        self.exclude_files_edit = QLineEdit('DTL, exp, Correct' if self.filetype == 'GPS' else '')
        self.exclude_files_edit.setToolTip("Separate items with commas [,]")

        self.date_filter_cbox = QCheckBox("Filter by date")
        self.calendar = QCalendarWidget()

        self.include_folders_edit = QLineEdit('GPS' if self.filetype == 'GPS' else '')
        self.include_folders_edit.setToolTip("Separate items with commas [,]")

        self.exclude_folders_edit = QLineEdit('DUMP')
        self.exclude_folders_edit.setToolTip("Separate items with commas [,]")

        self.include_exts_edit = QLineEdit()
        self.include_exts_edit.setToolTip("Separate items with commas [,]")

        self.exclude_exts_edit = QLineEdit()
        self.exclude_exts_edit.setToolTip("Separate items with commas [,]")

        # Buttons frame
        frame = QFrame()
        frame.setLayout(QHBoxLayout())
        frame.setContentsMargins(0, 0, 0, 0)
        self.accept_btn = QPushButton("&Accept")
        self.accept_btn.setShortcut('Return')
        self.reset_btn = QPushButton("&Reset")

        frame.layout().addWidget(self.accept_btn)
        frame.layout().addWidget(self.reset_btn)

        self.setLayout(QFormLayout())
        self.layout().setContentsMargins(8, 3, 8, 3)
        self.layout().setHorizontalSpacing(10)
        self.layout().setVerticalSpacing(2)

        files_gbox = QGroupBox('Files')
        files_gbox.setAlignment(Qt.AlignCenter)
        files_gbox.setLayout(QFormLayout())
        files_gbox.layout().addRow(QLabel("Include:"), self.include_files_edit)
        files_gbox.layout().addRow(QLabel("Exclude:"), self.exclude_files_edit)
        files_gbox.layout().addRow(self.date_filter_cbox)
        files_gbox.layout().addRow(self.calendar)

        self.layout().addRow(files_gbox)

        folders_gbox = QGroupBox('Folders')
        folders_gbox.setAlignment(Qt.AlignCenter)
        folders_gbox.setLayout(QFormLayout())
        folders_gbox.layout().addRow(QLabel("Include:"), self.include_folders_edit)
        folders_gbox.layout().addRow(QLabel("Exclude:"), self.exclude_folders_edit)

        self.layout().addRow(folders_gbox)

        extensions_gbox = QGroupBox('Extensions')
        extensions_gbox.setAlignment(Qt.AlignCenter)
        extensions_gbox.setLayout(QFormLayout())
        extensions_gbox.layout().addRow(QLabel("Include:"), self.include_exts_edit)
        extensions_gbox.layout().addRow(QLabel("Exclude:"), self.exclude_exts_edit)

        self.layout().addRow(extensions_gbox)

        self.layout().addRow(frame)

        # Signals
        self.reset_btn.clicked.connect(self.reset)
        self.accept_btn.clicked.connect(self.accept_sig.emit)
        self.accept_btn.clicked.connect(self.hide)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.close()

    def close(self):
        self.accept_sig.emit()
        self.hide()

    def reset(self):
        self.include_files_edit.setText('')
        self.exclude_files_edit.setText('DTL, exp, Correct' if self.filetype == 'GPS' else '')
        self.include_folders_edit.setText('GPS' if self.filetype == 'GPS' else '')
        self.exclude_folders_edit.setText('DUMP')
        self.include_exts_edit.setText('')
        self.exclude_exts_edit.setText('')

    def get_settings(self):
        filter_settings = []
        for filts in [self.include_files_edit, self.exclude_files_edit, self.include_folders_edit,
                      self.exclude_folders_edit, self.include_exts_edit, self.exclude_exts_edit]:
            filter_settings.append(filts.text())
        return filter_settings

    def set_settings(self, settings, refresh=True):
        if settings is None:
            return

        edits = [self.include_files_edit, self.exclude_files_edit, self.include_folders_edit,
                      self.exclude_folders_edit, self.include_exts_edit, self.exclude_exts_edit]
        for setting, edit in zip(settings, edits):
            edit.setText(setting)
        if refresh is True:
            self.accept_sig.emit()

class PEMBrowser(QTextBrowser):
    close_request = Signal(object)

    def __init__(self, pem_file):
        super().__init__()
        self.resize(600, 800)
        self.setWindowIcon(get_icon('txt_file.png'))
        self.setWindowTitle(f"{pem_file.filepath.name}")

        with open(str(pem_file.filepath), 'r') as file:
            pem_str = file.read()

        self.setText(pem_str)

    def closeEvent(self, e):
        self.close_request.emit(self)
        e.accept()
        self.deleteLater()


class FrequencyConverter(QWidget):
    """
    Converts timebase to frequency and vise-versa.
    """
    def __init__(self, parent=None):
        super().__init__()
        self.parent = parent

        self.setWindowTitle('Timebase / Frequency Converter')
        self.setWindowIcon(QIcon(os.path.join(icons_path, 'freq_timebase_calc.png')))
        self.layout = QGridLayout()
        self.setLayout(self.layout)

        self.timebase_label = QLabel('Timebase (ms)')
        self.freq_label = QLabel('Frequency (Hz)')

        self.timebase_sbox = QDoubleSpinBox()
        self.timebase_sbox.setMaximum(10000)
        self.freq_sbox = QDoubleSpinBox()
        self.freq_sbox.setMaximum(10000)

        self.layout.addWidget(self.timebase_label, 0, 0)
        self.layout.addWidget(self.timebase_sbox, 0, 1)
        self.layout.addWidget(self.freq_label, 2, 0)
        self.layout.addWidget(self.freq_sbox, 2, 1)

        def convert_freq_to_timebase():
            self.freq_sbox.blockSignals(True)
            self.timebase_sbox.blockSignals(True)

            freq = self.freq_sbox.value()
            if freq == 0.:
                self.timebase_sbox.setValue(0.)
            else:
                timebase = (1 / freq) * (1000 / 4)
                self.timebase_sbox.setValue(timebase)

            self.freq_sbox.blockSignals(False)
            self.timebase_sbox.blockSignals(False)

        def convert_timebase_to_freq():
            self.freq_sbox.blockSignals(True)
            self.timebase_sbox.blockSignals(True)

            timebase = self.timebase_sbox.value()
            if timebase == 0.:
                self.freq_sbox.setValue(0.)
            else:
                freq = (1 / (4 * timebase / 1000))
                self.freq_sbox.setValue(freq)

            self.freq_sbox.blockSignals(False)
            self.timebase_sbox.blockSignals(False)

        self.timebase_sbox.valueChanged.connect(convert_timebase_to_freq)
        self.freq_sbox.valueChanged.connect(convert_freq_to_timebase)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.close()

    def closeEvent(self, e):
        self.deleteLater()
        e.accept()


class PDFPlotPrinter(QWidget, Ui_PDFPlotPrinter):
    """
    Widget to handle printing PDF plots for PEM/RI files.
    """
    def __init__(self, parent=None, darkmode=False):
        super().__init__()
        self.parent = parent
        self.darkmode = darkmode
        plt.style.use('default')
        self.setupUi(self)
        self.setWindowTitle("PDF Printing Options")
        self.setWindowIcon(get_icon('pdf.png'))

        self.pem_files = []
        self.ri_files = []
        self.crs = None

        # self.printer = None
        self.plan_map_options = PlanMapOptions(parent=self)
        self.message = QMessageBox()

        self.print_btn.setDefault(True)
        self.print_btn.setFocus()

        # Set validations
        int_validator = QIntValidator()
        self.max_range_edit.setValidator(int_validator)
        self.min_range_edit.setValidator(int_validator)
        self.section_depth_edit.setValidator(int_validator)

        # Signals
        def get_save_file():
            default_path = self.pem_files[-1].filepath.parent
            save_dir = QFileDialog().getSaveFileName(self, '', str(default_path), 'PDF Files (*.PDF)')[0]

            if save_dir:
                logger.info(f"Saving PDFs to {save_dir}.")
                self.save_path_edit.setText(save_dir)

        self.print_btn.clicked.connect(self.print_pdfs)
        self.cancel_btn.clicked.connect(self.close)
        self.plan_map_options_btn.clicked.connect(self.plan_map_options.show)
        self.change_save_path_btn.clicked.connect(get_save_file)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.close()
        # elif e.key() == Qt.Key_Enter:
        #     self.print_pdfs()

    def close(self):
        self.hide()

    def open(self, pem_files, ri_files=None, crs=None):

        def fill_share_range():
            """
            Calculates the minimum and maximum station numbers between all opened PEM files, and uses this to fill out
            the shared range values
            """
            if self.pem_files:
                min_stations = [f.get_stations(converted=True).min() for f in self.pem_files]
                max_stations = [f.get_stations(converted=True).max() for f in self.pem_files]
                min_range, max_range = min(min_stations), max(max_stations)
                self.min_range_edit.setText(str(min_range))
                self.max_range_edit.setText(str(max_range))
            else:
                self.min_range_edit.setText('')
                self.max_range_edit.setText('')

        self.pem_files = copy.deepcopy(pem_files)
        self.ri_files = ri_files
        self.crs = crs

        for pem_file in self.pem_files:
            if not pem_file.is_averaged():
                pem_file = pem_file.average()
            if not pem_file.is_split():
                pem_file = pem_file.split()

        fill_share_range()

        # Fill the default path to be the name of the 2nd parent folder located at the same directory as pem_file[0].
        self.save_path_edit.setText(str(self.pem_files[0].filepath.with_name(
            self.pem_files[0].filepath.parents[1].stem + '.PDF')))

        self.show()

    def print_pdfs(self):
        plot_kwargs = {
            'parent': self,
            'CRS': self.crs,
            'share_range': self.share_range_cbox.isChecked(),
            'hide_gaps': self.hide_gaps_cbox.isChecked(),
            'annotate_loop': self.show_loop_anno_cbox.isChecked(),
            'is_moving_loop': self.moving_loop_cbox.isChecked(),
            'draw_title_box': self.plan_map_options.title_box_cbox.isChecked(),
            'draw_grid': self.plan_map_options.grid_cbox.isChecked(),
            'draw_scale_bar': self.plan_map_options.scale_bar_cbox.isChecked(),
            'draw_north_arrow': self.plan_map_options.north_arrow_cbox.isChecked(),
            'draw_legend': self.plan_map_options.legend_cbox.isChecked(),
            'draw_loops': self.plan_map_options.draw_loops_cbox.isChecked(),
            'draw_lines': self.plan_map_options.draw_lines_cbox.isChecked(),
            'draw_collars': self.plan_map_options.draw_hole_collars_cbox.isChecked(),
            'draw_hole_traces': self.plan_map_options.draw_hole_traces_cbox.isChecked(),
            'make_lin_plots': bool(self.make_profile_plots_gbox.isChecked() and self.output_lin_cbox.isChecked()),
            'make_log_plots': bool(self.make_profile_plots_gbox.isChecked() and self.output_log_cbox.isChecked()),
            'make_step_plots': bool(self.make_profile_plots_gbox.isChecked() and self.output_step_cbox.isChecked()),
            'make_plan_map': self.make_plan_maps_gbox.isChecked(),
            'make_section_plots': self.make_section_plots_gbox.isChecked(),
            'label_loops': self.plan_map_options.loop_labels_cbox.isChecked(),
            'label_lines': self.plan_map_options.line_labels_cbox.isChecked(),
            'label_collars': self.plan_map_options.hole_collar_labels_cbox.isChecked(),
            'label_hole_depths': self.plan_map_options.hole_depth_labels_cbox.isChecked(),
            'label_segments': self.label_section_depths_cbox.isChecked(),
            'section_depth': self.section_depth_edit.text()
        }

        # Fill the shared range boxes
        if self.share_range_cbox.isChecked():
            plot_kwargs['x_min'] = int(self.min_range_edit.text())
            plot_kwargs['x_max'] = int(self.max_range_edit.text())
        else:
            plot_kwargs['x_min'] = None
            plot_kwargs['x_max'] = None

        save_dir = self.save_path_edit.text()
        if save_dir:
            save_dir = os.path.splitext(save_dir)[0]
            printer = PEMPrinter(**plot_kwargs)
            printer.print_files(save_dir, files=list(zip(self.pem_files, self.ri_files)))
            os.startfile(save_dir + ".PDF")
            plt.style.use('dark_background' if self.darkmode else 'default')  # Reset darkmode theme
            self.close()
        else:
            logger.error(f"No file name passed.")
            self.message.critical(self, 'Error', 'Invalid file name')


class PlanMapOptions(QWidget, Ui_PlanMapOptions):
    """
    GUI to display checkboxes for display options when creating the final Plan Map PDF. Buttons aren't attached
    to any signals. The state of the checkboxes are read from PEMEditor.
    """

    def __init__(self, parent=None):
        super().__init__()
        self.parent = parent
        self.setupUi(self)
        self.setWindowTitle("Plan Map Options")
        self.init_signals()

    def init_signals(self):
        self.all_btn.clicked.connect(self.toggle_all)
        self.none_btn.clicked.connect(self.toggle_none)
        self.buttonBox.rejected.connect(self.close)
        self.buttonBox.accepted.connect(self.close)

    def toggle_all(self):
        self.title_box_cbox.setChecked(True)
        self.grid_cbox.setChecked(True)
        self.north_arrow_cbox.setChecked(True)
        self.scale_bar_cbox.setChecked(True)
        self.legend_cbox.setChecked(True)
        self.draw_loops_cbox.setChecked(True)
        self.draw_lines_cbox.setChecked(True)
        self.draw_hole_collars_cbox.setChecked(True)
        self.draw_hole_traces_cbox.setChecked(True)
        self.loop_labels_cbox.setChecked(True)
        self.line_labels_cbox.setChecked(True)
        self.hole_collar_labels_cbox.setChecked(True)
        self.hole_depth_labels_cbox.setChecked(True)

    def toggle_none(self):
        self.title_box_cbox.setChecked(False)
        self.grid_cbox.setChecked(False)
        self.north_arrow_cbox.setChecked(False)
        self.scale_bar_cbox.setChecked(False)
        self.legend_cbox.setChecked(False)
        self.draw_loops_cbox.setChecked(False)
        self.draw_lines_cbox.setChecked(False)
        self.draw_hole_collars_cbox.setChecked(False)
        self.draw_hole_traces_cbox.setChecked(False)
        self.loop_labels_cbox.setChecked(False)
        self.line_labels_cbox.setChecked(False)
        self.hole_collar_labels_cbox.setChecked(False)
        self.hole_depth_labels_cbox.setChecked(False)

    def closeEvent(self, e):
        self.hide()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.close()
        elif e.key() == Qt.Key_Return:
            self.close()


class GPSShareWidget(QWidget):
    accept_sig = Signal(object)

    def __init__(self, parent=None):
        super().__init__()
        self.parent = parent
        self.pem_files = []
        self.cboxes = []

        # Format window
        self.setWindowTitle(f"Share GPS")
        self.setWindowIcon(get_icon('share_gps.png'))

        self.layout = QFormLayout()
        self.setLayout(self.layout)
        self.layout.setHorizontalSpacing(100)
        self.layout.setVerticalSpacing(8)

        # Create the horizontal line for the header
        h_line = QFrame()
        h_line.setFrameShape(QFrame().HLine)
        h_line.setFrameShadow(QFrame().Sunken)

        # Create the header checkbox
        self.check_all_cbox = QCheckBox()
        self.check_all_cbox.setChecked(True)
        self.check_all_cbox.setToolTip('Check All')
        self.accept_btn = QPushButton('Accept')
        self.accept_btn.setShortcut('Return')
        self.accept_btn.setFocusPolicy(Qt.StrongFocus)

        # Create the header label
        header_label = QLabel('File')
        header_label.setFont(QFont('Arial', 10))

        # Add them to the layout
        self.layout.addRow(header_label, self.check_all_cbox)
        self.layout.addRow(h_line)
        self.layout.addRow(self.accept_btn)

        # Signals
        def toggle_all():
            for cbox in self.cboxes:
                if cbox.isEnabled():
                    cbox.setChecked(self.check_all_cbox.isChecked())

        self.check_all_cbox.toggled.connect(toggle_all)
        self.accept_btn.clicked.connect(self.accept)

    def accept(self):
        self.accept_sig.emit([c.isChecked() for c in self.cboxes])
        self.close()

    def open(self, pem_files, index_of_source):
        """
        Add the PEMFiles to the widget as labels with checkboxes.
        :param pem_files: list, PEMFile objects
        :param index_of_source: int, index of the file/widget that is sharing its GPS.
        """

        for i, pem_file in enumerate(pem_files):
            cbox = QCheckBox()
            cbox.setChecked(True)
            self.cboxes.append(cbox)

            label = QLabel(pem_file.filepath.name)
            label.setFont(QFont('Arial', 10))
            self.layout.insertRow(i + 2, label, cbox)

            if i == index_of_source:
                cbox.setEnabled(False)
                label.setEnabled(False)

        self.show()


class ChannelTimeViewer(QMainWindow):
    close_request = Signal(object)

    def __init__(self, pem_file, parent=None):
        """
        Class that visualizes channel times in a PEMFile using a color gradient table.
        :param pem_file: PEMFile object
        :param parent: Qt parent object
        """
        super().__init__()
        self.pem_file = pem_file
        self.parent = parent
        self.df = pd.DataFrame()
        self.text_format = ""

        self.table = pg.TableWidget()

        # Format window
        self.setLayout(QVBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().addWidget(self.table)
        self.setCentralWidget(self.table)

        self.sizePolicy().setHorizontalPolicy(QSizePolicy.Maximum)
        self.resize(600, 600)
        self.setWindowTitle(f"Channel Times - {self.pem_file.filepath.name}")
        self.setWindowIcon(get_icon("table.png"))

        # Status bar
        self.survey_type_label = QLabel(f" {self.pem_file.get_survey_type()} Survey ")
        self.timebase_label = QLabel(f" Timebase: {self.pem_file.timebase}ms ")
        off_time_channels = len(self.pem_file.channel_times[~self.pem_file.channel_times.Remove.astype(bool)])
        on_time_channels = len(self.pem_file.channel_times[self.pem_file.channel_times.Remove])
        self.num_channels = QLabel(f" Channels: {on_time_channels} On-Time / {off_time_channels} Off-Time ")

        self.units_combo = QComboBox()
        self.units_combo.addItem('µs')
        self.units_combo.addItem('ms')
        self.units_combo.addItem('s')
        self.units_combo.setCurrentText('ms')

        self.statusBar().addWidget(self.survey_type_label)
        self.statusBar().addWidget(self.timebase_label)
        self.statusBar().addWidget(self.num_channels)
        self.statusBar().addPermanentWidget(self.units_combo)
        self.statusBar().show()

        # Right-click menu
        self.table.setContextMenuPolicy(Qt.ActionsContextMenu)
        # self.table.viewport().installEventFilter(self)
        self.table.installEventFilter(self)
        self.menu = QMenu(self.table)
        delete_action = QAction('Delete', self)
        delete_action.triggered.connect(self.delete_channel)
        self.menu.addAction(delete_action)

        # Format table
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.sizePolicy().setHorizontalPolicy(QSizePolicy.Maximum)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setFrameStyle(QFrame.NoFrame)

        # Signals
        self.table.cellDoubleClicked.connect(self.change_remove_flag)
        self.units_combo.currentTextChanged.connect(self.fill_channel_table)
        self.copy_table_action = QShortcut("Ctrl+C", self)
        self.copy_table_action.activated.connect(self.copy_table)

        self.fill_channel_table()

    def closeEvent(self, e):
        self.close_request.emit(self)
        e.accept()
        self.deleteLater()

    def contextMenuEvent(self, event):
        print(f"Table right-clicked.")
        self.menu.popup(QCursor.pos())

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Delete:
            self.delete_channel()

    def copy_table(self):
        df = self.df.loc[:, "Start":"Width"].copy()

        # Add a "Channel" column, and rename the others to include the units
        df.reset_index(inplace=True)
        units = self.units_combo.currentText()
        columns = [f"{c} ({units})" for c in df.columns]
        columns[0] = "Channel"
        df.columns = columns

        df.to_clipboard(excel=True, header=True, index=False, float_format=self.text_format)
        self.statusBar().showMessage("Table copied to clipboard.", 1500)

    def fill_channel_table(self):
        """
        Fill and color the table with the channel times of the PEMFile.
        """

        def color_table():
            """
            Color the background of the cells based on their values. Also colors the text and aligns the text.
            """
            mpl_red, mpl_blue = np.array([34, 79, 214]) / 256, np.array([247, 42, 42]) / 256
            q_red = QColor(mpl_red[0] * 255,
                                 mpl_red[1] * 255,
                                 mpl_red[2] * 255)
            q_blue = QColor(mpl_blue[0] * 255,
                                  mpl_blue[1] * 255,
                                  mpl_blue[2] * 255)

            for i, column in enumerate(self.df.columns):

                if column != 'Remove':
                    # Normalize column values for color mapping
                    mn, mx, count = self.df[column].min(), self.df[column].max(), len(self.df[column])
                    norm = plt.Normalize(mn, mx)

                    # Create a custom color map
                    cm = LCMap.from_list('Custom', [mpl_red, mpl_blue])

                    # Apply the color map to the values in the column
                    colors = cm(norm(self.df[column].to_numpy()))

                for row in range(self.table.rowCount()):
                    item = self.table.item(row, i)

                    # Color the text
                    item.setForeground(QColor(255, 255, 255))
                    item.setTextAlignment(Qt.AlignCenter)

                    if column == 'Remove':
                        # Color the Remove column
                        if item.text() == 'False':
                            item.setBackground(q_red)
                        else:
                            item.setBackground(q_blue)

                    else:
                        # Color the background based on the value
                        color = QColor(colors[row][0] * 255,
                                             colors[row][1] * 255,
                                             colors[row][2] * 255)
                        item.setBackground(color)

        self.df = self.pem_file.channel_times.copy()
        # print(F"Channel times given to table viewer: {self.df.to_string(index=False)}")

        if self.units_combo.currentText() == 'µs':
            self.df.loc[:, 'Start':'Width'] = self.df.loc[:, 'Start':'Width'] * 1000000
            self.text_format = '%0.0f'
        elif self.units_combo.currentText() == 'ms':
            self.df.loc[:, 'Start':'Width'] = self.df.loc[:, 'Start':'Width'] * 1000
            self.text_format = '%0.3f'
        else:
            self.df.loc[:, 'Start':'Width'] = self.df.loc[:, 'Start':'Width']
            self.text_format = '%0.6f'

        self.table.setData(self.df.to_dict('index'))
        self.table.setFormat(self.text_format)
        self.table.resizeRowsToContents()

        color_table()

    def delete_channel(self):
        """
        Delete a channel from the table and the EM data.
        :return: None
        """
        print("Deleting channels")
        selected_rows = [model.row() for model in self.table.selectionModel().selectedRows()]
        if selected_rows:
            self.pem_file.channel_times = self.pem_file.channel_times.drop(selected_rows).reset_index(drop=True)
            self.pem_file.number_of_channels = len(self.pem_file.channel_times)
            self.pem_file.data.Reading = self.pem_file.data.Reading.map(lambda x: np.delete(x, selected_rows))
            self.fill_channel_table()

    def change_remove_flag(self, row, col):
        print(f"Changing remove flag of row {row}")
        self.df.loc[row, "Remove"] = not self.df.loc[row, "Remove"]

        if self.units_combo.currentText() == 'µs':
            self.df.loc[:, 'Start':'Width'] = self.df.loc[:, 'Start':'Width'] / 1000000
            self.text_format = '%0.0f'
        elif self.units_combo.currentText() == 'ms':
            self.df.loc[:, 'Start':'Width'] = self.df.loc[:, 'Start':'Width'] / 1000
            self.text_format = '%0.3f'
        else:
            self.df.loc[:, 'Start':'Width'] = self.df.loc[:, 'Start':'Width']
            self.text_format = '%0.6f'

        self.pem_file.channel_times = self.df
        self.fill_channel_table()


class SuffixWarningViewer(QMainWindow):

    def __init__(self, pem_file, parent=None):
        super().__init__()
        self.parent = parent

        assert not pem_file.is_borehole(), f"{pem_file.filepath.name} is a borehole file."

        self.pem_file = pem_file
        self.suffixes = self.pem_file.get_suffix_warnings()
        self.suffixes = self.suffixes[['Station', 'Component', 'Reading_index', 'Reading_number']]
        if self.suffixes.empty:
            logger.error(f"No suffixes to view in {pem_file.filepath.name}.")
            return

        self.setWindowTitle(f"Suffix Warnings Viewer - {pem_file.filepath.name}")

        self.setLayout(QVBoxLayout())
        self.table = pg.TableWidget()
        self.layout().addWidget(self.table)
        self.setCentralWidget(self.table)

        self.table.setData(self.suffixes.to_dict('index'))
        self.show()


class WarningViewer(QMainWindow):
    accept_sig = Signal(object)

    def __init__(self, pem_file, warning_type=None, parent=None):
        """
        Widget to view Repeat and Suffix warnings, and allow to fix them easily.
        :param pem_file: PEMFile object
        :param warning_type: str, either "suffix" or "repeat" for which kind of warning to present.
        :param parent: PyQt parent object
        """
        super().__init__()
        self.parent = parent

        self.pem_file = pem_file
        self.warning_type = warning_type

        if self.warning_type == 'suffix':
            assert not pem_file.is_borehole(), f"{pem_file.filepath.name} is a borehole file."

            def get_new_name(station):
                """
                Automatically rename the repeat.
                :param station: str, station name to be re-named.
                :return: str
                """
                new_station = re.sub(r'[NSEWnsew]', mode, station)
                return new_station

            self.warnings = self.pem_file.get_suffix_warnings().Station.to_frame()
            self.warnings[''] = '→'
            mode = self.pem_file.get_suffix_mode()
            self.warnings['To'] = self.warnings.Station.map(get_new_name)
            self.setWindowTitle(f"Suffix Warnings - {pem_file.filepath.name}")

        else:

            def get_new_name(station):
                """
                Automatically rename the repeat.
                :param station: str, station name to be re-named.
                :return: str
                """
                station_num = re.search(r'\d+', station).group()
                if station_num[-1] == '1' or station_num[-1] == '6':
                    station_num = str(int(station_num) - 1)
                elif station_num[-1] == '4' or station_num[-1] == '9':
                    station_num = str(int(station_num) + 1)

                new_station = re.sub(r'\d+', station_num, station)
                return new_station

            self.warnings = self.pem_file.get_repeats().Station.to_frame()
            self.warnings[''] = '→'
            self.warnings['To'] = self.warnings.Station.map(get_new_name)
            self.setWindowTitle(f"Repeat Warnings - {pem_file.filepath.name}")

        if self.warnings.empty:
            logger.error(f"No warnings to view in {pem_file.filepath.name}.")
            return

        # Format that window
        self.setLayout(QVBoxLayout())

        self.widget = QWidget()
        self.widget.setLayout(QVBoxLayout())
        self.setCentralWidget(self.widget)

        # Add the widgets
        self.table = pg.TableWidget()
        self.table.horizontalHeader().hide()
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.widget.layout().addWidget(self.table)

        self.accept_btn = QPushButton('Rename')
        self.widget.layout().addWidget(self.accept_btn)

        self.table.setData(self.warnings.to_dict('index'))
        self.format_table()

        # Init the signals
        self.accept_btn.clicked.connect(self.accept_rename)
        self.show()

    def accept_rename(self):
        data = self.pem_file.data
        data.loc[self.warnings.index, 'Station'] = self.warnings['To']
        self.accept_sig.emit(data)
        self.close()

    def format_table(self):
        for row in range(self.table.rowCount()):
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                item.setTextAlignment(Qt.AlignCenter)
        self.table.resizeRowsToContents()


class BatchNameEditor(QWidget):
    """
    Class to bulk rename PEM File line/hole names or file names.
    """
    acceptChangesSignal = Signal(object)

    def __init__(self, parent=None):
        super().__init__()
        self.parent = parent
        self.pem_files = []
        self.kind = None

        self.addEdit = QLineEdit()
        self.replaceEdit = QLineEdit()
        self.withEdit = QLineEdit()
        self.table = QTableWidget()
        self.table_columns = ['Old Name', 'New Name']
        self.table.setColumnCount(len(self.table_columns))
        self.table.setHorizontalHeaderLabels(self.table_columns)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Close)
        self.button_box.setCenterButtons(True)

        self.setLayout(QFormLayout())
        self.layout().addRow("Replace:", self.replaceEdit)
        self.layout().addRow("With:", self.withEdit)
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        self.layout().addRow(line)
        self.layout().addRow("Add:", self.addEdit)
        self.layout().addRow(self.table)
        self.layout().addRow(self.button_box)

        self.addEdit.textEdited.connect(self.update_table)
        self.replaceEdit.textEdited.connect(self.update_table)
        self.withEdit.textEdited.connect(self.update_table)
        self.button_box.rejected.connect(self.close)
        self.button_box.accepted.connect(self.accept_changes)

    def open(self, pem_files, kind=None):
        """
        Open the pem_files
        :param pem_files: list, PEMFile objects
        :param kind: str, either 'Line' to change the line names or 'File' to change file names
        :return: None
        """
        # Reset
        self.addEdit.setText('[n]')
        self.replaceEdit.setText('')
        self.withEdit.setText('')
        while self.table.rowCount() > 0:
            self.table.removeRow(0)

        self.pem_files = pem_files
        self.kind = kind

        if self.kind == 'Line':
            self.setWindowTitle('Rename lines/holes names')
        else:
            self.setWindowTitle('Rename files names')

        for pem_file in self.pem_files:
            self.add_to_table(pem_file)

        self.show()

    def add_to_table(self, pem_file):
        """
        Add the PEM files to the table.
        :param pem_file: PEMFile object
        """
        row_pos = self.table.rowCount()
        self.table.insertRow(row_pos)

        if self.kind == 'Line':
            item = QTableWidgetItem(pem_file.line_name)
            item2 = QTableWidgetItem(pem_file.line_name)
        elif self.kind == 'File':
            item = QTableWidgetItem(pem_file.filepath.name)
            item2 = QTableWidgetItem(pem_file.filepath.name)
        else:
            raise ValueError(f'{self.kind} is not a valid option.')

        item.setTextAlignment(Qt.AlignCenter)
        item2.setTextAlignment(Qt.AlignCenter)

        self.table.setItem(row_pos, 0, item)
        self.table.setItem(row_pos, 1, item2)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.close()
        elif e.key() == Qt.Key_Return:
            self.accept_changes()

    def update_table(self):
        """
        Every time a change is made in the line edits, this function is called and updates the entries in the table
        """
        for row in range(self.table.rowCount()):
            # Split the text based on '[n]'. Anything before it becomes the prefix,
            # and everything after is added as a suffix
            name = Path(re.sub(re.escape(self.replaceEdit.text()),
                               re.escape(self.withEdit.text()),
                               self.table.item(row, 0).text()))
            suffix = self.addEdit.text().rsplit('[n]')[-1]
            prefix = self.addEdit.text().rsplit('[n]')[0]
            if self.kind == 'Line':
                # Immediately replace what's in the removeEdit object with nothing
                output = prefix + str(name) + suffix
            else:
                output = str(name.with_name(prefix + str(name) + suffix))

            item = QTableWidgetItem(output)
            item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 1, item)

    def accept_changes(self):
        """
        Create a list of the new names and emit them as a signal
        """
        new_names = []
        for i, pem_file in enumerate(self.pem_files):
            new_name = self.table.item(i, 1).text()
            new_names.append(new_name)

        self.acceptChangesSignal.emit(new_names)


def main():
    from src.pem.pem_getter import PEMGetter
    app = QApplication(sys.argv)
    mw = PEMHub(app)
    # mw.actionDark_Theme.trigger()
    pem_getter = PEMGetter()
    pem_parser = PEMParser()
    dmp_parser = DMPParser()
    samples_folder = Path(__file__).parents[2].joinpath('sample_files')

    # pem_files = [pem_parser.parse(samples_folder.joinpath(r"Test PEMS\223XYT.PEM"))]
    # dmp_files = samples_folder.joinpath(r"TMC/Loop G/RAW/_31_ppp0131.dmp2")
    # ri_files = list(samples_folder.joinpath(r"RI files\PEMPro RI and Suffix Error Files\KBNorth").glob("*.RI*"))
    # pem_files = [pem_parser.parse(r"C:\_Data\2021\TMC\Murchison\Barraute B\RAW\3000E_0814.PEM")]
    # gps_files = r"C:\_Data\2021\TMC\Murchison\Barraute B\GPS\L3000E_0814.GPX"
    # pem_files.extend(pem_getter.get_pems(folder="Raw Boreholes", file="em21-156 xy_0416.PEM"))

    # pem_files = pem_getter.get_pems(folder="Raw Boreholes", file=r"EB-21-52\RAW\xy_0720.PEM")
    # pem_files = pem_getter.get_pems(number=15, random=True)
    # pem_files = pem_getter.get_pems(folder="Raw Surface", subfolder=r"Loop 4\Final", number=3)
    # pem_files = pem_getter.get_pems(folder='Iscaycruz', subfolder='Loop 1', number=4)
    # pem_files = pem_getter.get_pems(folder="Raw Boreholes\EB-21-68\RAW", number=1)
    pem_files = pem_getter.get_pems(folder='PEM Merging', file=r"Nantou Loop 5\[M]line19000e_0823.PEM")
    pem_files.extend(pem_getter.get_pems(folder='PEM Merging', file=r"Nantou Loop 5\[M]line19000e_0824.PEM"))
    # pem_files.extend(pem_getter.get_pems(folder="Raw Boreholes", file="XY.PEM"))
    # pem_files = pem_getter.get_pems(folder="Raw Boreholes", file="em10-10z_0403.PEM")
    # assert len(pem_files) == len(ri_files)

    # mw.project_dir_edit.setText(str(samples_folder.joinpath(r"Final folders\Birchy 2\Final")))
    # mw.open_project_dir()
    # mw.show()
    app.processEvents()

    # mw.add_pem_files(pem_files)

    # mw.open_3d_map()
    # mw.add_dmp_files(dmp_files)
    # mw.table.selectRow(0)
    # mw.table.selectAll()
    # mw.open_pem_merger()
    # mw.open_pem_geometry()
    # mw.open_pem_plot_editor()
    # mw.open_channel_table_viewer()
    # mw.open_pdf_plot_printer()
    # mw.open_name_editor('Line', selected=False)
    # mw.open_ri_importer()
    # mw.save_pem_file_as()¶
    # mw.pem_info_widgets[0].tabs.setCurrentIndex(2)
    # mw.add_gps_files(gps_files)

    """ Attempting to re-create printing bug """
    # mw.open_unpacker(folder=samples_folder.joinpath(r"Raw Boreholes\EB-21-52\DUMP\July 20, 2021"))
    # mw.unpacker.accept()
    #
    # dmp_files = [samples_folder.joinpath(r"Raw Boreholes\EB-21-52\RAW\xy_0720.dmp2")]
    # dmp_files.extend([samples_folder.joinpath(r"Raw Boreholes\EB-21-52\RAW\z_0720.dmp2")])
    # mw.add_dmp_files(dmp_files)
    # mw.table.selectRow(0)
    # mw.add_gps_files(samples_folder.joinpath(r"Raw Boreholes\EB-21-52\GPS\LOOP EB-1_0718.txt"))
    # mw.stackedWidget.currentWidget().loop_adder.accept()
    # mw.pem_info_widgets[0].tabs.setCurrentIndex(2)
    # mw.add_gps_files(samples_folder.joinpath(r"Raw Boreholes\EB-21-52\GPS\EB-21-52_0719.txt"))
    # mw.open_pem_geometry()
    # mw.pem_geometry.az_output_combo.setCurrentIndex(1)
    # mw.pem_geometry.dip_output_combo.setCurrentIndex(1)
    # mw.pem_geometry.accept()
    # mw.open_gps_share('all', mw.pem_info_widgets[0])
    # mw.gps_share.accept()
    # mw.open_derotator()
    # mw.derotator.accept()
    #
    # mw.open_pem_plot_editor()
    # mw.pem_editor_widgets[0].auto_clean()
    # mw.pem_editor_widgets[0].close()
    # mw.table.selectRow(1)
    # mw.open_pem_plot_editor()
    # mw.pem_editor_widgets[0].auto_clean()
    # mw.pem_editor_widgets[0].close()
    #
    # mw.save_pem_files(selected=False)
    #
    # mw.export_pem_files(selected=False, processed=True)
    # mw.remove_pem_file()
    # mw.table.selectRow(0)
    # mw.remove_pem_file()
    # mw.add_pem_files([samples_folder.joinpath(r"Raw Boreholes\EB-21-52\Final\xy.pem"),
    #                  samples_folder.joinpath(r"Raw Boreholes\EB-21-52\Final\z.pem")])

    """"""

    mw.show()
    # mw.open_pdf_plot_printer(selected=False)
    app.exec_()


if __name__ == '__main__':

    logger = logging.getLogger(__name__)
    main()
    # cProfile.run('main()', 'restats')
    # p = pstats.Stats('restats')
    # p.sort_stats('cumulative').print_stats(.5)

    # p.sort_stats('time', 'cumulative').print_stats()
    # p.strip_dirs().sort_stats(-1).print_stats()
