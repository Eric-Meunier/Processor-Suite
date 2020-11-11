import copy
import csv
import datetime
import logging
import os
import re
import subprocess
import sys
from itertools import groupby
from pathlib import Path

import keyboard
import natsort
import numpy as np
import pandas as pd
import pyqtgraph as pg
import simplekml
import stopit
from PyQt5 import (QtCore, QtGui, uic)
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtWidgets import (QWidget, QMainWindow, QApplication, QDesktopWidget, QMessageBox, QFileDialog, QHeaderView,
                             QTableWidgetItem, QAction, QMenu, QGridLayout, QTextBrowser, QFileSystemModel, QHBoxLayout,
                             QInputDialog, QErrorMessage, QLabel, QLineEdit, QPushButton, QAbstractItemView,
                             QVBoxLayout, QCalendarWidget, QFormLayout, QCheckBox, QSizePolicy, QFrame, QGroupBox,
                             QComboBox, QListWidgetItem)
from matplotlib import pyplot as plt
from matplotlib.colors import LinearSegmentedColormap as LCMap
from pyproj import CRS

from src.mag_field.mag_dec_widget import MagDeclinationCalculator
from src.damp.db_plot import DBPlotter
from src.gps.gps_editor import (SurveyLine, TransmitterLoop, BoreholeCollar, BoreholeSegments, BoreholeGeometry,
                                GPSConversionWidget)
from src.qt_py.loop_calculator import LoopCalculator
from src.gps.gpx_creator import GPXCreator
from src.pem.pem_file import PEMFile, PEMParser, DMPParser, StationConverter
from src.pem.pem_plotter import PEMPrinter
from src.qt_py.custom_qt_widgets import CustomProgressBar
from src.pem.derotator import Derotator
from src.qt_py.map_widgets import Map3DViewer, ContourMapViewer, TileMapViewer, GPSViewer
from src.qt_py.name_editor import BatchNameEditor
from src.geometry.pem_geometry import PEMGeometry
from src.pem.pem_info_widget import PEMFileInfoWidget
from src.pem.pem_merger import PEMMerger
from src.qt_py.pem_planner import LoopPlanner, GridPlanner
from src.pem.pem_plot_editor import PEMPlotEditor
from src.qt_py.ri_importer import BatchRIImporter
from src.pem.station_splitter import StationSplitter
from src.qt_py.unpacker import Unpacker

logger = logging.getLogger(__name__)

__version__ = '0.11.0e'

# Modify the paths for when the script is being run in a frozen state (i.e. as an EXE)
if getattr(sys, 'frozen', False):
    application_path = os.path.dirname(sys.executable)
    pemhubWindowCreatorFile = 'qt_ui\\pem_hub.ui'
    planMapOptionsCreatorFile = 'qt_ui\\plan_map_options.ui'
    pdfPrintOptionsCreatorFile = 'qt_ui\\pdf_plot_printer.ui'
    gpsConversionWindow = 'qt_ui\\gps_conversion.ui'
    icons_path = 'qt_ui\\icons'
else:
    application_path = os.path.dirname(os.path.abspath(__file__))
    pemhubWindowCreatorFile = os.path.join(os.path.dirname(application_path), 'qt_ui\\pem_hub.ui')
    planMapOptionsCreatorFile = os.path.join(os.path.dirname(application_path), 'qt_ui\\plan_map_options.ui')
    pdfPrintOptionsCreatorFile = os.path.join(os.path.dirname(application_path), 'qt_ui\\pdf_plot_printer.ui')
    gpsConversionWindow = os.path.join(os.path.dirname(application_path), 'qt_ui\\gps_conversion.ui')
    icons_path = os.path.join(os.path.dirname(application_path), "qt_ui\\icons")

# Load Qt ui file into a class
Ui_PEMHubWindow, _ = uic.loadUiType(pemhubWindowCreatorFile)
Ui_PlanMapOptionsWidget, _ = uic.loadUiType(planMapOptionsCreatorFile)
Ui_PDFPlotPrinterWidget, _ = uic.loadUiType(pdfPrintOptionsCreatorFile)
Ui_GPSConversionWidget, _ = uic.loadUiType(gpsConversionWindow)


def get_icon(filepath):
    ext = filepath.suffix.lower()
    if ext in ['.xls', '.xlsx', '.csv']:
        icon_pix = QPixmap(os.path.join(icons_path, 'excel_file.png'))
        icon = QIcon(icon_pix)
    elif ext in ['.rtf', '.docx', '.doc']:
        icon_pix = QPixmap(os.path.join(icons_path, 'word_file.png'))
        icon = QIcon(icon_pix)
    elif ext in ['.log', '.txt', '.xyz', '.seg', '.dad']:
        icon_pix = QPixmap(os.path.join(icons_path, 'txt_file.png'))
        icon = QIcon(icon_pix)
    elif ext in ['.pem']:
        icon_pix = QPixmap(os.path.join(icons_path, 'crone_logo.png'))
        icon = QIcon(icon_pix)
    elif ext in ['.dmp', '.dmp2', '.dmp3', '.dmp4']:
        icon_pix = QPixmap(os.path.join(icons_path, 'dmp.png'))
        icon = QIcon(icon_pix)
    elif ext in ['.gpx', '.gdb']:
        icon_pix = QPixmap(os.path.join(icons_path, 'garmin_file.png'))
        icon = QIcon(icon_pix)
    elif ext in ['.ssf']:
        icon_pix = QPixmap(os.path.join(icons_path, 'ssf_file.png'))
        icon = QIcon(icon_pix)
    elif ext in ['.cor']:
        icon_pix = QPixmap(os.path.join(icons_path, 'cor_file.png'))
        icon = QIcon(icon_pix)
    else:
        icon_pix = QPixmap(os.path.join(icons_path, 'none_file.png'))
        icon = QIcon(icon_pix)
    return icon


class PEMHub(QMainWindow, Ui_PEMHubWindow):

    def __init__(self, parent=None):
        super().__init__()
        self.parent = parent
        self.init_ui()

        self.pem_files = []
        self.pem_info_widgets = []
        self.pem_editor_widgets = []
        self.tab_num = 1
        self.allow_signals = True

        self.converter = StationConverter()
        self.dialog = QFileDialog()
        self.message = QMessageBox()
        self.error = QErrorMessage()
        self.calender = QCalendarWidget()
        self.calender.setWindowTitle('Select Date')
        self.text_browsers = []

        # Status bar formatting
        self.selection_label = QLabel()
        self.selection_label.setIndent(5)
        self.epsg_label = QLabel()

        # Project directory frame
        dir_frame = QFrame()
        dir_frame.setLayout(QHBoxLayout())
        dir_frame.layout().setContentsMargins(2, 0, 2, 0)
        dir_frame.layout().setSpacing(2)
        label = QLabel('Project Directory:')
        self.project_dir_edit = QLineEdit('')
        self.project_dir_edit.setSizePolicy(QtGui.QSizePolicy.Preferred, QtGui.QSizePolicy.Preferred)
        self.project_dir_edit.setMinimumWidth(250)
        dir_frame.layout().addWidget(label)
        dir_frame.layout().addWidget(self.project_dir_edit)

        self.status_bar.addPermanentWidget(self.selection_label, 0)
        self.status_bar.addPermanentWidget(QLabel(), 0)  # Spacer
        self.status_bar.addPermanentWidget(self.epsg_label, 0)
        self.status_bar.addPermanentWidget(dir_frame, 0)

        # Widgets
        self.station_splitter = StationSplitter(parent=self)
        self.grid_planner = GridPlanner(parent=self)
        self.loop_planner = LoopPlanner(parent=self)
        self.unpacker = Unpacker(parent=self)
        self.gpx_creator = GPXCreator(parent=self)
        self.freq_con = FrequencyConverter(parent=self)
        self.contour_map = ContourMapViewer(parent=self)
        self.gps_conversion_widget = GPSConversionWidget(parent=self)
        self.pem_list_filter = PathFilter('PEM', parent=self)
        self.gps_list_filter = PathFilter('GPS', parent=self)
        self.loop_calculator = LoopCalculator()

        # Project tree
        self.project_dir = None
        self.file_sys_model = QFileSystemModel()
        self.file_sys_model.setRootPath(QtCore.QDir.rootPath())
        self.project_tree.setModel(self.file_sys_model)
        self.project_tree.setColumnHidden(1, True)
        self.project_tree.setColumnHidden(2, True)
        self.project_tree.setColumnHidden(3, True)
        self.project_tree.setHeaderHidden(True)
        # self.move_dir_tree_to(self.file_sys_model.rootPath())
        self.pem_dir = None
        self.gps_dir = None
        self.available_pems = []
        self.available_gps = []

        self.init_menus()
        self.init_signals()
        self.init_crs()

        # Table
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
            'Repeat\nWarnings'
        ]
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        for i, col in enumerate(self.table_columns[1:]):
            header.setSectionResizeMode(i + 1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().hide()

        # Actions
        self.actionDel_File = QAction("&Remove File", self)
        self.actionDel_File.setShortcut("Del")
        self.actionDel_File.triggered.connect(self.remove_file)
        self.addAction(self.actionDel_File)
        self.actionDel_File.setEnabled(False)

        # self.merge_action = QAction("&Merge", self)
        # self.merge_action.triggered.connect(lambda: self.merge_pem_files(selected=True))
        # self.merge_action.setShortcut("Shift+M")

    def init_ui(self):
        """
        Initializing the UI.
        :return: None
        """

        def center_window():
            qt_rectangle = self.frameGeometry()
            center_point = QDesktopWidget().availableGeometry().center()
            qt_rectangle.moveCenter(center_point)
            self.move(qt_rectangle.topLeft())

        self.setupUi(self)
        self.setAcceptDrops(True)
        self.setWindowTitle("PEMPro  v" + str(__version__))
        self.setWindowIcon(
            QIcon(os.path.join(icons_path, 'conder.png')))
        self.resize(1700, 900)
        center_window()

        self.table.horizontalHeader().hide()

    def init_menus(self):
        """
        Initializing all actions.
        :return: None
        """
        # 'File' menu
        self.actionOpenFile.triggered.connect(self.open_file_dialog)

        self.actionSaveFiles.triggered.connect(lambda: self.save_pem_files(selected=False))

        self.actionExport_As_XYZ.triggered.connect(self.export_as_xyz)

        self.actionExport_As_PEM.triggered.connect(lambda: self.export_pem_files(selected=False,
                                                                                 processed=False))

        self.actionExport_Processed_PEM.triggered.connect(lambda: self.export_pem_files(selected=False,
                                                                                        processed=True))
        self.actionExport_Legacy_PEM.triggered.connect(lambda: self.export_pem_files(selected=False,
                                                                                     legacy=True))

        self.actionBackup_Files.triggered.connect(self.backup_files)
        self.actionImport_RI_Files.triggered.connect(self.open_ri_importer)

        self.actionPrint_Plots_to_PDF.triggered.connect(self.open_pdf_plot_printer)

        # PEM menu
        self.actionRename_Lines_Holes.triggered.connect(lambda: self.open_name_editor('Line', selected=False))

        self.actionRename_Files.triggered.connect(lambda: self.open_name_editor('File', selected=False))

        self.actionAverage_All_PEM_Files.triggered.connect(lambda: self.average_pem_data(selected=False))

        self.actionSplit_All_PEM_Files.triggered.connect(lambda: self.split_pem_channels(selected=False))

        self.actionScale_All_Currents.triggered.connect(lambda: self.scale_pem_current(selected=False))

        self.actionChange_All_Coil_Areas.triggered.connect(lambda: self.scale_pem_coil_area(selected=False))

        self.actionAuto_Name_Lines_Holes.triggered.connect(self.auto_name_lines)
        self.actionAuto_Merge_All_Files.triggered.connect(self.auto_merge_pem_files)

        self.actionReverseX_Component.triggered.connect(lambda: self.reverse_component_data(comp='X', selected=False))
        self.actionReverseY_Component.triggered.connect(lambda: self.reverse_component_data(comp='Y', selected=False))
        self.actionReverseZ_Component.triggered.connect(lambda: self.reverse_component_data(comp='Z', selected=False))

        # Map menu
        self.actionQuick_Map.triggered.connect(self.open_quick_map)
        self.actionTile_Map.triggered.connect(self.open_tile_map)
        self.actionContour_Map.triggered.connect(lambda: self.contour_map.open(self.pem_files))
        self.action3D_Map.triggered.connect(self.open_3d_map)
        self.actionGoogle_Earth.triggered.connect(lambda: self.save_as_kmz(save=False))

        # GPS menu
        self.actionExport_All_GPS.triggered.connect(self.export_all_gps)

        self.actionConvert_GPS.triggered.connect(self.open_gps_conversion)

        self.actionSave_as_KMZ.triggered.connect(lambda: self.save_as_kmz(save=True))

        # Tools menu
        self.actionLoop_Planner.triggered.connect(lambda: self.loop_planner.show())

        self.actionGrid_Planner.triggered.connect(lambda: self.grid_planner.show())

        self.actionLoop_Current_Calculator.triggered.connect(lambda: self.loop_calculator.show())

        self.actionConvert_Timebase_Frequency.triggered.connect(lambda: self.freq_con.show())

        self.actionDamping_Box_Plotter.triggered.connect(self.open_db_plot)

        self.actionUnpacker.triggered.connect(self.open_unpacker)

        self.actionGPX_Creator.triggered.connect(lambda: self.gpx_creator.show())

        # Help menu
        def open_logs():
            log_file = Path(r'.log')
            if log_file.exists():
                os.startfile(str(log_file))
            else:
                self.message.error(self, 'File Not Found', f"'{log_file}' file not found.")

        self.actionView_Logs.triggered.connect(open_logs)

    def init_signals(self):
        """
        Initializing all signals.
        :return: None
        """

        def table_value_changed(row, col):
            """
            Signal Slot: Action taken when a value in the main table was changed.
            :param row: Row of the main table that the change was made.
            :param col: Column of the main table that the change was made.
            :return: None
            """
            logger.info(f'Table value changed at row {row} and column {col}')

            self.table.blockSignals(True)
            pem_file = self.pem_files[row]
            value = self.table.item(row, col).text()

            # Rename a file when the 'File' column is changed
            if col == self.table_columns.index('File'):
                old_path = pem_file.filepath
                new_value = self.table.item(row, col).text()

                if new_value:
                    new_path = old_path.parent.joinpath(new_value)
                    logger.info(f"Renaming {old_path.name} to {new_path.name}")

                    try:
                        os.rename(str(old_path), str(new_path))
                    except OSError:
                        # Keep the old name if the new file name already exists
                        logger.error(f"{new_path.name} already exists.")
                        self.message.critical(self, 'File Error', f"{new_path.name} already exists.")
                        item = QTableWidgetItem(str(old_path.name))
                        item.setTextAlignment(QtCore.Qt.AlignCenter)
                        self.table.setItem(row, col, item)
                    else:
                        pem_file.filepath = new_path
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
                    float(value)
                except ValueError:
                    logger.error(f"{value} is not a number.")
                    self.message.critical(self, 'Invalid Value', f"Current must be a number")
                    self.pem_to_table(pem_file, row)
                else:
                    pem_file.current = value

            elif col == self.table_columns.index('Coil\nArea'):
                try:
                    float(value)
                except ValueError:
                    logger.error(f"{value} is not a number.")
                    self.message.critical(self, 'Invalid Value', f"Coil area Must be a number")
                    self.pem_to_table(pem_file, row)
                else:
                    pem_file.coil_area = value

            self.format_row(row)

            if self.allow_signals:
                self.table.blockSignals(False)

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
                :param data: DataFrame of the data with the stations re-named.
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

                    global suffix_viewer
                    suffix_viewer = WarningViewer(pem_file, warning_type='suffix')
                    suffix_viewer.accept_sig.connect(accept_change)
                else:
                    self.status_bar.showMessage(f"No suffix warnings to show.", 1000)

            elif col == self.table_columns.index('Repeat\nWarnings'):
                if self.table.item(row, col).text() != '0':

                    global repeat_viewer
                    repeat_viewer = WarningViewer(pem_file, warning_type='repeat')
                    repeat_viewer.accept_sig.connect(accept_change)
                else:
                    self.status_bar.showMessage(f"No repeats to show.", 1000)

        def set_date(date):
            """
            Change the date in the selected PEM file to that of the calender widget
            :param date: QDate object from the calender widget
            """
            item = QTableWidgetItem(date.toString('MMMM dd, yyyy'))
            item.setTextAlignment(QtCore.Qt.AlignCenter)
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

        def open_project_dir():
            """
            Move the directory tree when a path is entered in the status bar LineEdit widget.
            """
            path = Path(self.project_dir_edit.text())
            if path.exists():
                self.move_dir_tree_to(Path(self.project_dir_edit.text()))
            else:
                logger.error(f"{str(path)} does not exist.")
                self.message.information(self, "Invalid Path", f"{str(path)} does not exist.")
                self.project_dir_edit.setText(str(self.get_current_path()))

        def open_project_file(item):
            """
            Signal slot, open the file that was double clicked in the project tree.
            :param item: QListWidget item
            """
            os.startfile(str(self.get_current_path()))

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

            self.open_dmp_files(dmp_filepaths)
            self.open_pem_files(pem_filepaths)

        def add_gps_list_files():
            """
            Signal slot, open the selected GPS files in to the GPS list
            """
            selected_files = [Path(self.project_dir, i.text()) for i in self.gps_list.selectedItems()]
            self.open_gps_files(selected_files)

        def remove_pem_list_files():
            """
            Signal slot, remove the selected items from the list. Can be brought back by refreshing.
            """
            selected_rows = [self.pem_list.row(i) for i in self.pem_list.selectedItems()]
            for row in sorted(selected_rows, reverse=True):
                self.pem_list.takeItem(row)
                self.available_pems.pop(row)

        def remove_gps_list_files():
            """
            Signal slot, remove the selected items from the list. Can be brought back by refreshing.
            """
            selected_rows = [self.gps_list.row(i) for i in self.gps_list.selectedItems()]
            for row in sorted(selected_rows, reverse=True):
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
                selection_info = []

                timebase = f"Timebase: {file.timebase}ms"
                survey_type = f"Survey Type: {file.get_survey_type()}"
                selection_info.extend([timebase, survey_type])

                if file.is_borehole() and file.has_xy():
                    rotated = f"De-rotated: {file.is_derotated()}"
                    selection_info.extend([rotated])

                info_str = ' | '.join(selection_info)
            else:
                info_str = f"{len(pem_files)} selected"

            self.selection_label.setText(f"{info_str} ")

        def cell_clicked(row, col):
            """
            Open the plot editor when a row is alt + clicked
            :param row: int, click cell's row
            :param col: int, click cell's column
            """
            update_selection_text()

            if keyboard.is_pressed('alt'):
                self.open_pem_plot_editor()

        def open_unpacker_dir(folder_dir):
            self.project_dir_edit.setText(str(folder_dir))
            open_project_dir()

        # Widgets
        self.pem_list_filter.accept_sig.connect(self.fill_pem_list)
        self.gps_list_filter.accept_sig.connect(self.fill_gps_list)
        # self.unpacker.open_project_folder_sig.connect(self.move_dir_tree_to)
        self.unpacker.open_project_folder_sig.connect(open_unpacker_dir)
        self.calender.clicked.connect(set_date)

        # Buttons
        self.apply_shared_header_btn.clicked.connect(apply_header)
        self.project_dir_edit.returnPressed.connect(open_project_dir)
        self.filter_pem_list_btn.clicked.connect(self.pem_list_filter.show)
        self.filter_gps_list_btn.clicked.connect(self.gps_list_filter.show)

        # Table
        self.table.viewport().installEventFilter(self)
        self.table.installEventFilter(self)
        self.table.setFocusPolicy(QtCore.Qt.StrongFocus)

        self.table.itemSelectionChanged.connect(lambda: self.stackedWidget.setCurrentIndex(self.table.currentRow()))
        self.table.itemSelectionChanged.connect(update_selection_text)
        self.table.cellChanged.connect(table_value_changed)
        self.table.cellClicked.connect(cell_clicked)
        self.table.cellDoubleClicked.connect(table_value_double_clicked)

        # Project Tree
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
        # self.share_client_cbox.stateChanged.connect(lambda: set_shared_header('client'))
        # self.share_grid_cbox.stateChanged.connect(lambda: set_shared_header('grid'))
        # self.share_loop_cbox.stateChanged.connect(lambda: set_shared_header('loop'))

        # self.client_edit.textChanged.connect(lambda: set_shared_header('client'))
        # self.grid_edit.textChanged.connect(lambda: set_shared_header('grid'))
        # self.loop_edit.textChanged.connect(lambda: set_shared_header('loop'))

    def init_crs(self):
        """
        Populate the CRS drop boxes and connect all their signals
        """

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

    def contextMenuEvent(self, event):
        """
        Right-click context menu items.
        :param event: Right-click event.
        :return: None
        """

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
                obj_str = 'all'

            self.open_gps_share(gps_obj, piw_widget)

        if self.table.underMouse():
            if self.table.selectionModel().selectedIndexes():
                selected_pems, rows = self.get_pem_files(selected=True)

                # Create all the actions
                # Remove, open, and save PEM files
                remove_file_action = QAction("Remove", self)
                remove_file_action.triggered.connect(self.remove_file)
                remove_file_action.setIcon(QIcon(os.path.join(icons_path, 'remove.png')))
                open_file_action = QAction("Open", self)
                open_file_action.triggered.connect(self.open_in_text_editor)
                open_file_action.setIcon(QIcon(os.path.join(icons_path, 'txt_file.png')))
                save_file_action = QAction("Save", self)
                save_file_action.setIcon(QIcon(os.path.join(icons_path, 'save.png')))
                save_file_action.triggered.connect(lambda: self.save_pem_files(selected=True))
                export_pem_action = QAction("Export...", self)
                export_pem_action.setIcon(QIcon(os.path.join(icons_path, 'export.png')))
                export_pem_action.triggered.connect(lambda: self.export_pem_files(selected=True, processed=False))
                save_file_as_action = QAction("Save As...", self)
                save_file_as_action.setIcon(QIcon(os.path.join(icons_path, 'save_as.png')))
                save_file_as_action.triggered.connect(self.save_pem_file_as)

                # View channel table
                action_view_channels = QAction("Channel Table", self)
                action_view_channels.triggered.connect(self.open_channel_table_viewer)

                # Merge PEM files
                merge_action = QAction("Merge", self)
                merge_action.setIcon(QIcon(os.path.join(icons_path, 'pem_merger.png')))
                merge_action.triggered.connect(self.open_pem_merger)

                # Print PDFs
                print_plots_action = QAction("Print Plots", self)
                print_plots_action.setIcon(QIcon(os.path.join(icons_path, 'pdf.png')))
                print_plots_action.triggered.connect(lambda: self.open_pdf_plot_printer(selected_files=True))

                # Extract stations
                extract_stations_action = QAction("Extract Stations", self)
                extract_stations_action.setIcon(QIcon(os.path.join(icons_path, 'station_splitter.png')))
                extract_stations_action.triggered.connect(
                    lambda: self.station_splitter.open(selected_pems[0]))

                # Magnetic declination calculator
                calc_mag_dec_action = QAction("Magnetic Declination", self)
                calc_mag_dec_action.setIcon(QIcon(os.path.join(icons_path, 'mag_field.png')))
                calc_mag_dec_action.triggered.connect(lambda: self.open_mag_dec(selected_pems[0]))

                # View GPS
                view_loop_action = QAction("Loop GPS", self)
                view_loop_action.triggered.connect(lambda: self.pem_info_widgets[self.table.currentRow()].edit_loop())
                view_line_action = QAction("Line GPS", self)
                view_line_action.triggered.connect(lambda: self.pem_info_widgets[self.table.currentRow()].edit_line())

                # Share GPS
                share_loop_action = QAction("Loop GPS", self)
                share_loop_action.triggered.connect(lambda: share_gps('loop'))
                share_line_action = QAction("Line GPS", self)
                share_line_action.triggered.connect(lambda: share_gps('line'))
                share_collar_action = QAction("Collar GPS", self)
                share_collar_action.triggered.connect(lambda: share_gps('collar'))
                share_segments_action = QAction("Segments", self)
                share_segments_action.triggered.connect(lambda: share_gps('segments'))
                share_all_action = QAction("All", self)
                share_all_action.triggered.connect(lambda: share_gps('all'))

                # self.table.view_3d_section_action = QAction("&View 3D Section", self)
                # self.table.view_3d_section_action.setIcon(QIcon(os.path.join(icons_path, 'section_3d.png')))
                # self.table.view_3d_section_action.triggered.connect(self.show_section_3d_viewer)

                # Plot editor
                open_plot_editor_action = QAction("&Plot", self)
                open_plot_editor_action.triggered.connect(self.open_pem_plot_editor)
                open_plot_editor_action.setIcon(QIcon(os.path.join(icons_path, 'plot_editor.png')))

                # Data editing/processing
                average_action = QAction("Average", self)
                average_action.triggered.connect(lambda: self.average_pem_data(selected=True))
                average_action.setIcon(QIcon(os.path.join(icons_path, 'average.png')))
                split_action = QAction("Split Channels", self)
                split_action.triggered.connect(lambda: self.split_pem_channels(selected=True))
                split_action.setIcon(QIcon(os.path.join(icons_path, 'split.png')))
                scale_current_action = QAction("Scale Current", self)
                scale_current_action.triggered.connect(lambda: self.scale_pem_current(selected=True))
                scale_current_action.setIcon(QIcon(os.path.join(icons_path, 'current.png')))
                scale_ca_action = QAction("Scale Coil Area", self)
                scale_ca_action.triggered.connect(lambda: self.scale_pem_coil_area(selected=True))
                scale_ca_action.setIcon(QIcon(os.path.join(icons_path, 'coil.png')))

                # Reversing component data
                reverse_x_component_action = QAction("X Component", self)
                reverse_x_component_action.triggered.connect(
                    lambda: self.reverse_component_data(comp='X', selected=True))
                reverse_y_component_action = QAction("Y Component", self)
                reverse_y_component_action.triggered.connect(
                    lambda: self.reverse_component_data(comp='Y', selected=True))
                reverse_z_component_action = QAction("Z Component", self)
                reverse_z_component_action.triggered.connect(
                    lambda: self.reverse_component_data(comp='Z', selected=True))

                # Derotation
                derotate_action = QAction("De-rotate XY", self)
                derotate_action.triggered.connect(self.open_derotator)
                derotate_action.setIcon(QIcon(os.path.join(icons_path, 'derotate.png')))

                # Borehole geometry
                get_geometry_action = QAction("Geometry", self)
                get_geometry_action.triggered.connect(self.open_pem_geometry)
                get_geometry_action.setIcon(QIcon(os.path.join(icons_path, 'pem_geometry.png')))

                # Rename lines and files
                rename_lines_action = QAction("Rename Lines/Holes", self)
                rename_lines_action.triggered.connect(lambda: self.open_name_editor('Line', selected=True))
                rename_files_action = QAction("Rename Files", self)
                rename_files_action.triggered.connect(lambda: self.open_name_editor('File', selected=True))

                # Create a menu
                menu = QMenu(self.table)

                # Add all the actions to the menu
                menu.addAction(open_file_action)
                menu.addAction(save_file_action)

                # Only for single file selection
                if len(self.table.selectionModel().selectedRows()) == 1:
                    pem_file = selected_pems[0]

                    menu.addAction(save_file_as_action)
                    menu.addAction(extract_stations_action)

                    menu.addAction(calc_mag_dec_action)
                    if pem_file.has_any_gps():
                        calc_mag_dec_action.setDisabled(False)
                    else:
                        calc_mag_dec_action.setDisabled(True)
                    menu.addSeparator()

                    # View menu
                    view_menu = menu.addMenu('View')
                    view_menu.addAction(action_view_channels)
                    view_menu.setIcon(QIcon(os.path.join(icons_path, 'view.png')))
                    view_menu.addSeparator()

                    # View Loop
                    view_menu.addAction(view_loop_action)
                    if not pem_file.has_loop_gps():
                        view_loop_action.setDisabled(True)

                    # View Line
                    if not pem_file.is_borehole():
                        view_menu.addAction(view_line_action)
                        if not pem_file.has_station_gps():
                            view_line_action.setDisabled(True)

                    menu.addSeparator()

                    # Share menu
                    share_menu = menu.addMenu('Share')
                    share_menu.setIcon(QIcon(os.path.join(icons_path, 'share_gps.png')))

                    # Share loop
                    share_menu.addAction(share_loop_action)
                    if not pem_file.has_loop_gps():
                        share_loop_action.setDisabled(True)

                    # Share line GPS
                    if not pem_file.is_borehole():
                        share_menu.addAction(share_line_action)
                        if not pem_file.has_station_gps():
                            share_line_action.setDisabled(True)

                    # Share Collar and Segments
                    else:
                        share_menu.addAction(share_collar_action)
                        share_menu.addAction(share_segments_action)
                        if not pem_file.has_collar_gps():
                            share_collar_action.setDisabled(True)
                        if not pem_file.has_geometry():
                            share_segments_action.setDisabled(True)

                    share_menu.addSeparator()
                    share_menu.addAction(share_all_action)
                    if not pem_file.has_any_gps():
                        share_all_action.setDisabled(True)
                else:
                    menu.addAction(export_pem_action)

                menu.addSeparator()
                # Plot
                menu.addAction(open_plot_editor_action)
                menu.addSeparator()

                # Merge PEMs
                if len(self.table.selectionModel().selectedRows()) == 2:
                    menu.addAction(merge_action)

                # Data editing
                menu.addAction(average_action)
                menu.addAction(split_action)
                menu.addAction(scale_current_action)
                menu.addAction(scale_ca_action)
                menu.addSeparator()

                # Reverse data menu
                share_menu = menu.addMenu('Reverse')
                share_menu.setIcon(QIcon(os.path.join(icons_path, 'reverse.png')))
                share_menu.addAction(reverse_x_component_action)
                share_menu.addAction(reverse_y_component_action)
                share_menu.addAction(reverse_z_component_action)
                menu.addSeparator()

                # For boreholes only, do-rotate and geometry
                if all([f.is_borehole() for f in selected_pems]):
                    if len(self.table.selectionModel().selectedRows()) == 1:
                        menu.addAction(derotate_action)
                        if not pem_file.has_xy():
                            derotate_action.setDisabled(True)
                    menu.addAction(get_geometry_action)
                    menu.addSeparator()

                if len(self.table.selectionModel().selectedRows()) > 1:
                    menu.addSeparator()
                    menu.addAction(rename_files_action)
                    menu.addAction(rename_lines_action)

                menu.addSeparator()
                menu.addAction(print_plots_action)
                menu.addSeparator()
                menu.addAction(remove_file_action)

                menu.popup(QtGui.QCursor.pos())

    def eventFilter(self, source, event):
        # # Clear the selection when clicking away from any file
        # if (event.type() == QtCore.QEvent.MouseButtonPress and
        #         source is self.table.viewport() and
        #         self.table.itemAt(event.pos()) is None):
        #     self.table.clearSelection()

        if source == self.table:
            # Change the focus to the table so the 'Del' key works
            if event.type() == QtCore.QEvent.FocusIn:
                self.actionDel_File.setEnabled(True)
            elif event.type() == QtCore.QEvent.FocusOut:
                self.actionDel_File.setEnabled(False)

            # Change the selected PIW widget when the arrow keys are pressed, and clear selection when Esc is pressed
            if event.type() == QtCore.QEvent.KeyPress:
                if self.pem_files:
                    if event.key() == QtCore.Qt.Key_Left:
                        current_tab = self.pem_info_widgets[0].tabs.currentIndex()
                        self.change_pem_info_tab(current_tab - 1)
                        return True
                    elif event.key() == QtCore.Qt.Key_Right:
                        current_tab = self.pem_info_widgets[0].tabs.currentIndex()
                        self.change_pem_info_tab(current_tab + 1)
                        return True
                    elif event.key() == QtCore.Qt.Key_Escape:
                        self.table.clearSelection()
                        return True

            # Attempt to side scroll when Shift scrolling, but doesn't work well.
            elif event.type() == QtCore.QEvent.Wheel:
                if event.modifiers() == QtCore.Qt.ShiftModifier:
                    pos = self.table.horizontalScrollBar().value()
                    if event.angleDelta().y() < 0:  # Wheel moved down so scroll to the right
                        self.table.horizontalScrollBar().setValue(pos + 20)
                    else:
                        self.table.horizontalScrollBar().setValue(pos - 20)
                    return True

        return super(QWidget, self).eventFilter(source, event)

    def dragEnterEvent(self, e):
        e.accept()

    def dragMoveEvent(self, e):
        """
        Controls which files can be drag-and-dropped into the program. Conditions are based on the file type of each
        file being dragged, and which widget they are being dragged onto.
        :param e: PyQT event
        """
        urls = [url.toLocalFile() for url in e.mimeData().urls()]

        # PEM, DMP, and DUMP folders can be opened with no PEM files currently opened.
        # PEM files
        if all([Path(file).suffix.lower() in ['.pem'] for file in urls]):
            if e.answerRect().intersects(self.table.geometry()):
                e.acceptProposedAction()
                return

        # DMP files
        elif all([Path(file).suffix.lower() in ['.dmp', '.dmp2', '.dmp3', '.dmp4'] for file in urls]):
            if e.answerRect().intersects(self.table.geometry()):
                e.acceptProposedAction()
                return

        # Dump folder
        elif len(urls) == 1 and (Path(urls[0]).is_dir() or Path(urls[0]).suffix.lower() in ['.zip', '.7z', '.rar']):
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
            if all([Path(file).suffix.lower() in ['.txt', '.csv', '.seg', '.xyz', '.gpx'] for file in urls]):
                if all([e.answerRect().intersects(self.piw_frame.geometry()),
                        current_piw.tabs.currentWidget() in eligible_tabs,
                        self.pem_files]):
                    e.acceptProposedAction()
                    return

            # RI files
            elif all([Path(file).suffix.lower() in ['.ri1', '.ri2', '.ri3'] for file in urls]):
                if all([e.answerRect().intersects(self.piw_frame.geometry()),
                        current_piw.tabs.currentWidget() == current_piw.ri_tab,
                        self.pem_files]):
                    e.acceptProposedAction()
                    return

            elif all([Path(file).suffix.lower() in ['.inf', '.log', '.gpx'] for file in urls]):
                if e.answerRect().intersects(self.project_crs_box.geometry()):
                    e.acceptProposedAction()
                    return

            else:
                e.ignore()

    def dropEvent(self, e):
        urls = [url.toLocalFile() for url in e.mimeData().urls()]

        if all([Path(file).suffix.lower() in ['.pem'] for file in urls]):
            self.open_pem_files(urls)

        elif all([Path(file).suffix.lower() in ['.dmp', '.dmp2', '.dmp3', '.dmp4'] for file in urls]):
            self.open_dmp_files(urls)

        elif all([Path(file).suffix.lower() in ['.txt', '.csv', '.seg', '.xyz', '.gpx'] for file in urls]):
            self.open_gps_files(urls)

        elif all([Path(file).suffix.lower() in ['.ri1', '.ri2', '.ri3'] for file in urls]):
            self.open_ri_file(urls)

        elif all([Path(file).suffix.lower() in ['.inf', '.log'] for file in urls]):
            self.open_inf_file(urls[0])

        elif len(urls) == 1 and (Path(urls[0]).is_dir() or Path(urls[0]).suffix.lower() in ['.zip', '.7z', '.rar']):
            self.open_unpacker(folder=urls[0])

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

    def remove_file(self, rows=None):
        """
        Removes PEM files from the main table, along with any associated widgets.
        :param rows: list: Table rows of the PEM files.
        :return: None
        """

        def reset_crs():
            self.gps_system_cbox.setCurrentText('')
            self.gps_zone_cbox.setCurrentText('')
            self.gps_datum_cbox.setCurrentText('')

        if not rows:
            pem_files, rows = self.get_pem_files(selected=True)

        if not isinstance(rows, list):
            rows = [rows]

        self.setUpdatesEnabled(False)
        for row in rows:
            self.table.removeRow(row)
            self.stackedWidget.removeWidget(self.stackedWidget.widget(row))
            del self.pem_files[row]
            del self.pem_info_widgets[row]

        if len(self.pem_files) == 0:
            self.table.horizontalHeader().hide()
            self.client_edit.setText('')
            self.grid_edit.setText('')
            self.loop_edit.setText('')
            reset_crs()

        self.setUpdatesEnabled(True)

    def open_dmp_files(self, dmp_files):
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
        bar = CustomProgressBar()
        bar.setMaximum(len(dmp_files))

        with pg.ProgressDialog("Converting DMP Files...", 0, len(dmp_files)) as dlg:
            dlg.setBar(bar)
            dlg.setWindowTitle("Converting DMP Files")

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

        self.open_pem_files(pem_files)

    def open_pem_files(self, pem_files):
        """
        Action of opening a PEM file. Will not open a PEM file if it is already opened.
        :param pem_files: list, Filepaths for the PEM Files
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

            pem_info_widget = PEMFileInfoWidget(parent=self)
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
                pems = natsort.humansorted(pems, key=lambda x: x.filepath.name)
                i = pems.index(pem_file)
            return i

        def fill_crs(pem_file):
            """
            Fill CRS from the file to the main table's CRS drop down menus
            :param pem_file: PEMFile object
            """
            crs = pem_file.get_crs()
            if crs:
                name = crs.name

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
                        logger.error(f"{datum} has not been implemented for PEMPro.")
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

        # Start the progress bar
        bar = CustomProgressBar()
        bar.setMaximum(len(pem_files))

        with pg.ProgressDialog("Opening PEMs Files...", 0, len(pem_files), busyCursor=False) as dlg:
            dlg.setBar(bar)
            dlg.setWindowTitle('Opening PEM Files')

            for pem_file in pem_files:
                if dlg.wasCanceled():
                    break

                # Create a PEMFile object if a filepath was passed
                if not isinstance(pem_file, PEMFile):
                    try:
                        pem_file = parser.parse(pem_file)
                    except Exception as e:
                        logger.critical(str(e))
                        self.error.setWindowTitle('Error parsing PEM file')
                        self.error.showMessage(f"Error parsing PEM file: {str(e)}")
                        dlg += 1
                        continue

                # Check if the file is already opened in the table. Won't open if it is.
                if self.is_opened(pem_file):
                    self.status_bar.showMessage(f"{pem_file.filepath.name} is already opened", 2000)
                    dlg += 1
                else:
                    dlg.setLabelText(f"Opening {pem_file.filepath.name}")

                    # Create the PEMInfoWidget
                    pem_widget = add_piw_widget(pem_file)

                    # Fill the shared header text boxes and move the project directory
                    if not self.pem_files:
                        share_header(pem_file)
                        # self.piw_frame.show()
                    if self.project_dir_edit.text() == '':
                        self.move_dir_tree_to(pem_file.filepath.parent)

                    # Fill CRS from the file if project CRS currently empty
                    if self.gps_system_cbox.currentText() == '':
                        fill_crs(pem_file)

                    i = get_insertion_point(pem_file)
                    self.pem_files.insert(i, pem_file)
                    self.pem_info_widgets.insert(i, pem_widget)
                    self.stackedWidget.insertWidget(i, pem_widget)
                    self.table.insertRow(i)
                    self.pem_to_table(pem_file, i)

                    count += 1
                    # Progress the progress bar
                    dlg += 1
                    # self.total_opened += 1

        self.allow_signals = True
        self.table.setUpdatesEnabled(True)
        self.table.blockSignals(False)

        self.table.horizontalHeader().show()
        self.status_bar.showMessage(f"{count} PEM files opened.", 2000)

    def open_gps_files(self, gps_files):
        """
        Adds GPS information from the gps_files to the PEMFile object
        :param gps_files: list or str, filepaths of text file or GPX files
        """
        pem_info_widget = self.stackedWidget.currentWidget()
        crs = self.get_crs()
        pem_info_widget.open_gps_files(gps_files)

    def open_ri_file(self, ri_files):
        """
        Adds RI file information to the associated PEMFile object. Only accepts 1 file.
        :param ri_files: list, str filepaths with step plot information in them
        """
        ri_file = ri_files[0]
        pem_info_widget = self.stackedWidget.currentWidget()
        pem_info_widget.open_ri_file(ri_file)

    def open_inf_file(self, inf_file):
        """
        Parses a .INF file to extract the CRS information in ti and set the CRS drop-down values.
        :param inf_file: str, .INF filepath
        """
        def get_inf_crs(filepath):
            with open(filepath, 'rt') as f:
                file = f.read()
            crs = dict()
            crs['System'] = re.search(r'Coordinate System:\W+(?P<System>.*)', file).group(1)
            crs['Zone'] = re.search(r'Coordinate Zone:\W+(?P<Zone>.*)', file).group(1)
            crs['Datum'] = re.search(r'Datum:\W+(?P<Datum>.*)', file).group(1).split(' (')[0]
            logger.info(f"Parsing INF file: System: {crs['System']}. Zone: {crs['Zone']}. Datum: {crs['Datum']}")
            return crs

        crs = get_inf_crs(inf_file)
        coord_sys = crs.get('System')
        coord_zone = crs.get('Zone')
        datum = crs.get('Datum')
        self.gps_system_cbox.setCurrentText(coord_sys)
        self.gps_datum_cbox.setCurrentText(datum)
        self.gps_zone_cbox.setCurrentText(coord_zone)

        self.status_bar.showMessage(f"CRS information filled.", 2000)

    def open_in_text_editor(self):
        """
        Open the selected PEM File in a text editor
        """
        pem_files, rows = self.get_pem_files(selected=True)
        for pem_file in pem_files:
            # pem_str = pem_file.to_string()
            with open(str(pem_file.filepath), 'r') as file:
                pem_str = file.read()
            browser = QTextBrowser()
            self.text_browsers.append(browser)
            browser.setText(pem_str)
            browser.resize(600, 800)
            browser.setWindowIcon(QIcon(os.path.join(icons_path, 'txt_file.png')))
            browser.setWindowTitle(f"{pem_file.filepath.name}")
            browser.show()

    def open_file_dialog(self):
        """
        Open files through the file dialog
        """
        files = self.dialog.getOpenFileNames(self, 'Open PEM Files', filter='PEM files (*.pem)')[0]
        if files:
            self.open_pem_files(files)

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
            Remove the editor from the list of pem_editors
            :param editor: PEMPlotEditor object emitted by the signal
            """
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
            editor = PEMPlotEditor(parent=self)
            self.pem_editor_widgets.append(editor)
            # Connect the 'save' and 'close' signals
            editor.save_sig.connect(save_editor_pem)
            editor.close_sig.connect(close_editor)
            editor.reset_file_sig.connect(reset_file)
            editor.open(pem_file)

    def open_derotator(self):
        """
        Open the XY de-rotator
        """

        def accept_file(rotated_pem):
            rotation_note = derotator.rotation_note
            if rotation_note is not None:
                rotated_pem.notes.append(rotation_note)

            self.pem_files[row] = rotated_pem
            self.refresh_pem(rotated_pem)

            derotator.close()

        pem_files, rows = self.get_pem_files(selected=True)
        assert len(pem_files) == 1, 'Can only de-rotate one file at a time.'

        pem_file, row = pem_files[0], rows[0]

        global derotator
        derotator = Derotator(parent=self)
        derotator.accept_sig.connect(accept_file)
        derotator.open(pem_file)

    def open_pem_geometry(self):
        """
        Open the PEMGeometry window
        """

        def accept_geometry(seg):
            for file in pem_files:
                file.segments = seg
                self.refresh_pem(file)
            self.status_bar.showMessage(f"Geometry updated for {', '.join([file.filepath.name for file in pem_files])}."
                                        , 2000)

        pem_files, rows = self.get_pem_files(selected=True)

        global pem_geometry
        pem_geometry = PEMGeometry(parent=self)
        pem_geometry.accepted_sig.connect(accept_geometry)
        pem_geometry.open(pem_files)

    def open_pem_merger(self):
        """
        Merge two PEM files with PEMMerger.
        """

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
                logger.error(f"{f1.filepath.name} has {len(f1.channel_table)} channels and"
                             f" {f2.filepath.name} has {len(f2.channel_table)} channels.")
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
            :param filepath: Path object.
            """

            if self.delete_merged_files_cbox.isChecked():
                self.remove_file(rows)

            self.open_pem_files(filepath)

        pem_files, rows = self.get_pem_files(selected=True)
        if len(pem_files) != 2:
            logger.error(f"PEMMerger must have two PEM files, not {len(pem_files)}.")
            self.message.critical(self, 'Error', f'Must select two PEM Files, not {len(pem_files)}.')
            return

        if check_pems():
            global merger
            merger = PEMMerger(parent=self)
            merger.accept_sig.connect(accept_merge)
            merger.open(pem_files)

    def open_pdf_plot_printer(self, selected_files=False):
        """
        Open an instance of PDFPlotPrinter, which has all the options for printing plots.
        :param selected_files: bool, False will pass all opened PEM files, True will only pass selected PEM files
        """

        if not self.pem_files:
            self.status_bar.showMessage(f"No PEM files opened.", 2000)
            return

        pem_files, rows = self.get_pem_files(selected=selected_files)

        # Gather the RI files
        ri_files = []
        for row, pem_file in zip(rows, pem_files):
            ri_files.append(self.pem_info_widgets[row].ri_file)

        global pdf_plot_printer
        pdf_plot_printer = PDFPlotPrinter(parent=self)

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

        pdf_plot_printer.open(pem_files, ri_files=ri_files, crs=self.get_crs())

    def open_mag_dec(self, pem_file):
        """
        Opens the MagDeclinationCalculator widget to calculate the magnetic declination of the selected file.
        :param pem_file: PEMFile object
        """
        crs = self.get_crs()
        if not crs:
            logger.warning(f"No CRS.")
            self.message.information(self, 'Error', 'GPS coordinate system information is incomplete')
            return

        global m
        m = MagDeclinationCalculator(parent=self)
        m.calc_mag_dec(pem_file)
        m.show()

    def open_unpacker(self, folder=None):
        self.unpacker.show()
        if folder:
            self.unpacker.open_folder(folder, project_dir=self.project_dir)

    def open_db_plot(self):
        """
        Open the damping box plotter.
        """
        global db_plot
        db_plot = DBPlotter(parent=self)
        db_plot.show()

    # def show_section_3d_viewer(self):
    #     """
    #     Opens the 3D Borehole Section Viewer window
    #     :return: None
    #     """
    #     pem_file, row = self.get_selected_pem_files()
    #     if 'borehole' in pem_file[0].survey_type.lower():
    #         self.section_3d_viewer = Section3DViewer(pem_file[0], parent=self)
    #         self.section_3d_viewer.show()
    #     else:
    #         self.status_bar.showMessage('Invalid survey type', 2000)

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
                item.setTextAlignment(QtCore.Qt.AlignCenter)
                self.table.setItem(row, col, item)
            batch_name_editor.open(pem_files, kind=kind)

        pem_files, rows = self.get_pem_files(selected=selected)

        if not pem_files:
            logger.warning("No PEM files selected.")
            self.status_bar.showMessage(f"No PEM files selected.", 2000)
            return

        global batch_name_editor
        batch_name_editor = BatchNameEditor(parent=self)
        batch_name_editor.open(pem_files, kind=kind)
        batch_name_editor.acceptChangesSignal.connect(rename_pem_files)

    def open_ri_importer(self):
        """
        Opens BatchRIImporter for bulk importing RI files.
        :return: None
        """

        def open_ri_files():
            ri_filepaths = ri_importer.ri_files
            if len(ri_filepaths) > 0:
                for i, ri_filepath in enumerate(ri_filepaths):
                    self.pem_info_widgets[i].open_ri_file(ri_filepath)
                self.status_bar.showMessage(f"Imported {len(ri_filepaths)} RI files", 2000)
            else:
                pass

        ri_importer = BatchRIImporter(parent=self)
        ri_importer.open_pem_files(self.pem_files)
        ri_importer.acceptImportSignal.connect(open_ri_files)
        ri_importer.show()

    def open_quick_map(self, selected=False):
        """
        Open the GPSViewer if there's any GPS in any of the opened PEM files.
        """
        global quick_map
        quick_map = GPSViewer(parent=self)

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
        global tile_map
        tile_map = TileMapViewer(parent=self)

        if not self.pem_files:
            logger.warning(f"No PEM files opened.")
            self.status_bar.showMessage(f"No PEM files opened.", 2000)

        elif not any([f.has_any_gps() for f in self.pem_files]):
            logger.warning(f"No GPS found in any file.")
            self.message.information(self, 'Error', 'No file has any GPS to plot.')
        else:
            tile_map.open(self.pem_files)

    def open_3d_map(self):
        """
        Open the Map3DViewer if there's any GPS in any of the opened PEM files.
        """
        global map_3d
        map_3d = Map3DViewer(parent=self)

        if not self.pem_files:
            logger.warning(f"No PEM files opened.")
            self.status_bar.showMessage(f"No PEM files opened.", 2000)

        elif not any([f.has_any_gps() for f in self.pem_files]):
            logger.warning(f"No GPS found in any file.")
            self.message.information(self, 'Error', 'No file has any GPS to plot.')

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

            # Set up the progress bar
            bar = CustomProgressBar()
            bar.setMaximum(len(self.pem_files))

            with pg.ProgressDialog("Converting DMP Files...", 0, len(self.pem_files)) as dlg:
                dlg.setBar(bar)
                dlg.setWindowTitle("Converting DMP Files")

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

                self.status_bar.showMessage(f"Process complete. GPS converted to {crs.to_string()}.", 2000)

        crs = self.get_crs()

        if not crs:
            logger.error(f"No CRS.")
            self.message.critical(self, 'Invalid CRS', 'Project CRS is invalid.')
            return

        self.gps_conversion_widget.open(crs)
        self.gps_conversion_widget.accept_signal.connect(convert_gps)

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

            if gps_object == 'all':
                # Share each GPS object
                for widget in pem_info_widgets:
                    # Share the collar and segments if the source is a borehole
                    if source_widget.pem_file.is_borehole():
                        widget.fill_gps_table(source_widget.get_collar(), widget.collar_table)
                        widget.fill_gps_table(source_widget.get_segments(), widget.segments_table)
                        widget.gps_object_changed(widget.collar_table, refresh=False)
                        widget.gps_object_changed(widget.segments_table, refresh=False)
                    # Share the line GPS if it's a surface line
                    else:
                        widget.fill_gps_table(source_widget.get_line(), widget.line_table)
                        widget.gps_object_changed(widget.line_table, refresh=False)

                    # Share the loop
                    widget.fill_gps_table(source_widget.get_loop(), widget.loop_table)
                    widget.gps_object_changed(widget.loop_table, refresh=True)  # Only refresh at the end

            else:
                if isinstance(gps_object, TransmitterLoop):
                    for widget in pem_info_widgets:
                        widget.fill_gps_table(gps_object.df, widget.loop_table)
                        widget.gps_object_changed(widget.loop_table, refresh=True)

                elif isinstance(gps_object, SurveyLine):
                    for widget in pem_info_widgets:
                        widget.fill_gps_table(gps_object.df, widget.line_table)
                        widget.gps_object_changed(widget.line_table, refresh=True)

                elif isinstance(gps_object, BoreholeCollar):
                    for widget in pem_info_widgets:
                        widget.fill_gps_table(gps_object.df, widget.collar_table)
                        widget.gps_object_changed(widget.collar_table, refresh=True)

                elif isinstance(gps_object, BoreholeSegments):
                    for widget in pem_info_widgets:
                        widget.fill_gps_table(gps_object.df, widget.segments_table)
                        widget.gps_object_changed(widget.segments_table, refresh=True)

        if gps_object == 'all':
            survey_type = source_widget.pem_file.get_survey_type()
            # Filter PEM files to only include the same survey type as the selected file.
            pem_files, piws = zip(*filter(lambda x: x.get_survey_type() == survey_type,
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

        source_index = piws.index(source_widget)

        global gps_share
        gps_share = GPSShareWidget()
        gps_share.open(pem_files, source_index)
        gps_share.accept_sig.connect(share_gps)

    def open_channel_table_viewer(self):
        """
        Open the ChannelTimeViewer table for the selected PEMFile.
        """

        pem_files, rows = self.get_pem_files(selected=True)
        pem_file = pem_files[0]

        global win
        win = ChannelTimeViewer(pem_file, parent=self)

    def project_dir_changed(self, model):
        """
        Signal slot, changes the project director to the path clicked in the project_tree
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
            files = list(self.project_dir.rglob('*.txt'))
            files.extend(self.project_dir.rglob('*.csv'))
            files.extend(self.project_dir.rglob('*.gpx'))
            files.extend(self.project_dir.rglob('*.xlsx'))
            files.extend(self.project_dir.rglob('*.xls'))
            return files

        def get_filtered_gps():
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

            filtered_gps = self.available_gps

            # Filter the GPS files by file name
            include_files = strip(self.gps_list_filter.include_files_edit.text().split(','))
            logger.info(f"Include files: {include_files}")
            exclude_files = strip(self.gps_list_filter.exclude_files_edit.text().split(','))
            logger.info(f"Include files: {exclude_files}")

            # Filter the GPS files by folder names
            include_folders = strip(self.gps_list_filter.include_folders_edit.text().split(','))
            logger.info(f"Include folders: {include_folders}")
            exclude_folders = strip(self.gps_list_filter.exclude_folders_edit.text().split(','))
            logger.info(f"Exclude folders: {exclude_folders}")

            # Inclusive files
            if any(include_files):
                filtered_gps = [p for p in filtered_gps if any(
                    [f.lower() in str(p.name).lower() for f in include_files if f]
                )]

            # Inclusive files
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
            logger.info(f"Include extensions: {include_exts}")
            exclude_exts = strip(self.gps_list_filter.exclude_exts_edit.text().split(','))
            logger.info(f"Exclude extensions: {exclude_exts}")

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

            return filtered_gps

        if not self.project_dir:
            logger.error('No projected directory selected')
            self.message.information(self, 'Error', 'No project directory has been selected.')
            return

        self.gps_list.clear()
        # Try to find a GPS folder, but time out after 1 second
        self.available_gps = find_gps_files(timeout=1)

        if self.available_gps is None:
            return
        elif self.available_gps == 'timeout':
            logger.warning(f"Searching for GPS files timed out.")
            self.status_bar.showMessage(f"Searching for GPS files timed out.", 1000)
            return
        else:
            gps_files = get_filtered_gps()
            for file in gps_files:
                if file.stem != '.txt':
                    self.gps_list.addItem(QListWidgetItem(get_icon(file), f"{str(file.relative_to(self.project_dir))}"))

    def fill_pem_list(self):
        """
        Populate the pem_list with all *.pem files found in the project_dir.
        """

        @stopit.threading_timeoutable(default='timeout')
        def find_pem_files():
            files = []
            # Find all .PEM, .DMP, and .DMP2 files in the project directory
            files.extend(list(self.project_dir.rglob('*.PEM')))
            files.extend(list(self.project_dir.rglob('*.DMP')))
            files.extend(list(self.project_dir.rglob('*.DMP2')))
            return files

        def get_filtered_pems():
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

            filtered_pems = self.available_pems

            # Filter the PEM files by file name
            include_files = strip(self.pem_list_filter.include_files_edit.text().split(','))
            logger.info(f"Include files: {include_files}")
            exclude_files = strip(self.pem_list_filter.exclude_files_edit.text().split(','))
            logger.info(f"Include files: {exclude_files}")

            # Filter the PEM files by folder names
            include_folders = strip(self.pem_list_filter.include_folders_edit.text().split(','))
            logger.info(f"Include folders: {include_folders}")
            exclude_folders = strip(self.pem_list_filter.exclude_folders_edit.text().split(','))
            logger.info(f"Exclude folders: {exclude_folders}")

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
            logger.info(f"Include extensions: {include_exts}")
            exclude_exts = strip(self.pem_list_filter.exclude_exts_edit.text().split(','))
            logger.info(f"Exclude extensions: {exclude_exts}")

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

            pem_str = '\n'.join([str(f) for f in filtered_pems])
            logger.info(f"Filtered pems: {pem_str}")
            return filtered_pems

        if not self.project_dir:
            logger.error('No projected directory selected')
            self.message.information(self, 'Error', 'No project directory has been selected.')
            return

        self.pem_list.clear()

        # Try to find .PEM files, but time out after 1 second
        self.available_pems = find_pem_files(timeout=1)

        if self.available_pems is None:
            return
        elif self.available_pems == 'timeout':
            logger.warning(f"Searching for PEM/DMP files timed out.")
            self.status_bar.showMessage(f"Searching for PEM/DMP files timed out.", 1000)
            return
        else:
            pem_files = get_filtered_pems()
            for file in pem_files:
                self.pem_list.addItem(QListWidgetItem(get_icon(file), f"{str(file.relative_to(self.project_dir))}"))

    def move_dir_tree_to(self, dir_path):
        """
        Changes the directory tree to show the dir_path. Will find the nearest folder upward if dir_path is a file
        :param dir_path: Path object or str, directory path of the desired directory
        :return: None
        """
        if not isinstance(dir_path, Path):
            dir_path = Path(dir_path)

        while dir_path.is_file():
            dir_path = dir_path.parent

        model = self.file_sys_model.index(str(dir_path))

        # Adds a timer or else it doesn't actually scroll to it properly.
        QtCore.QTimer.singleShot(150, lambda: self.project_tree.scrollTo(model, QAbstractItemView.EnsureVisible))

        # Expands the path folder
        self.project_tree.expand(model)

        # Set the model to be selected in the tree
        self.project_tree.setCurrentIndex(model)

        # Update the GPS and PEM trees
        self.project_dir_changed(model)

    def save_pem_files(self, selected=False):
        """
        Save all selected PEM files.
        :param selected: Bool: if True, saves all opened PEM files instead of only the selected ones.
        :return: None
        """
        def add_crs_tag():
            """
            Add the CRS from the table as a note to the PEM file.
            """
            # Remove any existing CRS tag
            for note in reversed(pem_file.notes):
                if '<GEN> CRS' in note or '<CRS>' in note:
                    del pem_file.notes[pem_file.notes.index(note)]

            pem_file.notes.append(f"<GEN>/<CRS> {crs.name}")

        pem_files, rows = self.get_pem_files(selected=selected)
        crs = self.get_crs()

        bar = CustomProgressBar()
        bar.setMaximum(len(pem_files))

        with pg.ProgressDialog('Saving PEM Files...', 0, len(pem_files)) as dlg:
            dlg.setBar(bar)
            dlg.setWindowTitle('Saving PEM Files')

            for pem_file in pem_files:
                if dlg.wasCanceled():
                    break

                dlg.setLabelText(f"Saving {pem_file.filepath.name}")

                # Add the CRS note if CRS isn't None
                if crs:
                    add_crs_tag()

                # Save the PEM file and refresh it in the table
                pem_file.save()
                self.refresh_pem(pem_file)
                dlg += 1

        self.status_bar.showMessage(f'Save Complete. {len(pem_files)} file(s) saved.', 2000)

    def save_pem_file_as(self):
        """
        Serialize the currently selected PEMFile as a .PEM or .XYZ file.
        """

        def save_pem():
            # Create a copy of the PEM file, then update the copy
            new_pem = pem_file.copy()
            new_pem.filepath = Path(save_path)
            new_pem.save(legacy='legacy' in save_type.lower())

            self.status_bar.showMessage(f'Save Complete. PEM file saved as {new_pem.filepath.name}', 2000)

            # Open the new PEM. If it is already opened, refresh it. This way the file remembers to save as legacy.
            if self.is_opened(new_pem):
                ind = self.pem_files.index(pem_file)
                self.pem_files[ind] = new_pem
                self.refresh_pem(new_pem)
            else:
                self.open_pem_files(new_pem)

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

        pem_file = self.pem_files[self.table.currentRow()]
        default_path = str(pem_file.filepath)
        save_path, save_type = QFileDialog.getSaveFileName(self, '', default_path, 'PEM File (*.PEM);; '
                                                                                   'Legacy PEM File (*.PEM);;'
                                                                                   'XYZ File (*.XYZ)')

        if save_path:
            if 'XYZ' in save_type:
                save_xyz()
            else:
                save_pem()

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
            save_dir = self.dialog.getSaveFileName(self, 'Save KMZ File', default_path, 'KMZ Files (*.KMZ)')[0]
            if save_dir:
                kmz_save_dir = str(Path(save_dir).with_suffix('.kmz'))
                kml.savekmz(kmz_save_dir, format=False)
                # os.startfile(kmz_save_dir)
        else:
            # Save the file and open Google Earth using a temporary file
            prog = Path(os.environ["ProgramFiles"]).joinpath(r'Google/Google Earth Pro/client/googleearth.exe')
            if prog.is_file():
                # Create the temp folder
                Path('temp').mkdir(exist_ok=True)
                # Temp file name
                kmz_save_dir = str(Path(r'temp/temp.kmz').resolve())  # Gets the absolute path
                # Save the file
                kml.savekmz(kmz_save_dir, format=False)
                # Open Google Earth
                cmd = [str(prog), kmz_save_dir]
                subprocess.Popen(cmd)
            else:
                logger.error(f"Cannot find Google Earth Pro.")
                self.message.information(self, "Error", "Cannot find Google Earth Pro.")

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

        file_dir = self.dialog.getExistingDirectory(self, '', str(self.project_dir))

        if file_dir:
            bar = CustomProgressBar()
            bar.setMaximum(len(pem_files))

            with pg.ProgressDialog("Exporting XYZ Files...", 0, len(pem_files)) as dlg:
                dlg.setBar(bar)
                dlg.setWindowTitle('Exporting XYZ Files')

                for pem_file in pem_files:
                    if dlg.wasCanceled():
                        break

                    file_name = str(pem_file.filepath.with_suffix('.xyz'))
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
        if not pem_files:
            logger.error(f"No PEM files opened.")
            return

        # Make sure there's a valid CRS when doing a final export
        if processed is True:
            crs = self.get_crs()
            if not crs:
                response = self.message.question(self, 'Invalid CRS',
                                                 'The CRS information is invalid. '
                                                 'Do you wish to proceed with no CRS information?',
                                                 self.message.Yes | self.message.No)
                if response == self.message.No:
                    self.status_bar.showMessage(f"Cancelled.", 2000)

        file_dir = self.dialog.getExistingDirectory(self, '', str(self.project_dir))
        if not file_dir:
            self.status_bar.showMessage('Cancelled.', 2000)
            return

        bar = CustomProgressBar()
        bar.setMaximum(len(pem_files))
        with pg.ProgressDialog("Exporting PEM Files...", 0, len(pem_files)) as dlg:
            dlg.setBar(bar)
            dlg.setWindowTitle('Exporting PEM Files')

            for pem_file, row in zip(pem_files, rows):
                if dlg.wasCanceled():
                    break

                file_name = pem_file.filepath.name
                pem_file = pem_file.copy()
                logger.info(f"Exporting {file_name}.")

                pem_file.filepath = Path(file_dir).joinpath(file_name)
                pem_file.save(legacy=legacy, processed=processed)
                dlg += 1

        self.status_bar.showMessage(f"Save complete. {len(pem_files)} PEM file(s) exported", 2000)

    def export_all_gps(self):
        """
        Exports all GPS from all opened PEM files to separate CSV files. Creates folders for each loop.
        Doesn't repeat if a line/hole/loop has been done already.
        :return: None
        """
        if not self.pem_files:
            logger.error(f"No PEM files opened.")
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

        default_path = os.path.dirname(self.pem_files[0].filepath)
        export_folder = self.dialog.getExistingDirectory(self, 'Select Destination Folder', default_path)

        if export_folder:
            bar = CustomProgressBar()
            bar.setMaximum(len(self.pem_files))
            with pg.ProgressDialog("Exporting GPS...", 0, len(self.pem_files)) as dlg:
                dlg.setBar(bar)
                dlg.setWindowTitle('Exporting GPS')

                for loop, pem_files in groupby(self.pem_files, key=lambda x: x.loop_name):
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
                                csv_filepath = str(folder.joinpath(loop_name).with_suffix('csv'))

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
                                csv_filepath = str(folder.joinpath(line_name).with_suffix('csv'))

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
                                csv_filepath = str(folder.joinpath(hole_name).with_suffix('csv'))

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

            def color_background(row_index, color):
                """
                Color an entire table row
                :param row_index: Int: Row of the table to color
                :param color: str: The desired color
                :return: None
                """
                color = QtGui.QColor(color)
                color.setAlpha(50)
                for j in range(self.table.columnCount()):
                    self.table.item(row_index, j).setBackground(color)

            average_col = self.table_columns.index('Averaged')
            split_col = self.table_columns.index('Split')
            suffix_col = self.table_columns.index('Suffix\nWarnings')
            repeat_col = self.table_columns.index('Repeat\nWarnings')
            pem_has_gps = has_all_gps(self.pem_info_widgets[row])

            for col in [average_col, split_col, suffix_col, repeat_col]:
                item = self.table.item(row, col)
                if item:
                    value = item.text()
                    if col == average_col:
                        if value == 'False':
                            item.setForeground(QtGui.QColor('red'))
                        else:
                            item.setForeground(QtGui.QColor('black'))
                    elif col == split_col:
                        if value == 'False':
                            item.setForeground(QtGui.QColor('red'))
                        else:
                            item.setForeground(QtGui.QColor('black'))
                    elif col == suffix_col:
                        if int(value) > 0:
                            item.setForeground(QtGui.QColor('red'))
                        else:
                            item.setForeground(QtGui.QColor('black'))
                    elif col == repeat_col:
                        if int(value) > 0:
                            item.setForeground(QtGui.QColor('red'))
                        else:
                            item.setForeground(QtGui.QColor('black'))

            if not pem_has_gps:
                color_background(row, 'blue')

        def color_anomalies():
            """
            Change the text color of table cells where the value warrants attention. An example of this is where the
            date might be wrong.
            :return: None
            """
            date_column = self.table_columns.index('Date')
            current_year = str(datetime.datetime.now().year)

            for row in range(self.table.rowCount()):
                if self.table.item(row, date_column):
                    date = self.table.item(row, date_column).text()
                    year = str(date.split(' ')[-1])
                    if year != current_year:
                        self.table.item(row, date_column).setForeground(QtGui.QColor('red'))
                    else:
                        self.table.item(row, date_column).setForeground(QtGui.QColor('black'))

        def color_changes():
            """
            Bolden table cells where the value in the cell is different then what is the PEM file memory.
            """
            bold_font, normal_font = QtGui.QFont(), QtGui.QFont()
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
        color_changes()

        if self.allow_signals:
            self.table.blockSignals(False)

    def pem_to_table(self, pem_file, row):
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
        ]

        # Set the information into each cell. Columns from First Station and on can't be edited.
        for i, info in enumerate(row_info):
            item = QTableWidgetItem(str(info))
            item.setTextAlignment(QtCore.Qt.AlignCenter)
            # Disable editing of columns past First Station and for the date
            if i > self.table_columns.index('Coil\nArea') or i == self.table_columns.index('Date'):
                item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
            self.table.setItem(row, i, item)

        self.format_row(row)

        if self.allow_signals:
            self.table.blockSignals(False)

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
            self.pem_to_table(pem_file, ind)
            self.format_row(ind)
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

    def get_current_path(self):
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
                logger.info(f"Project CRS: {crs.name}")
                return crs
        else:
            return None

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

        bar = CustomProgressBar()
        bar.setMaximum(len(pem_files))

        with pg.ProgressDialog('Averaging PEM Files...', 0, len(pem_files)) as dlg:
            dlg.setBar(bar)
            dlg.setWindowTitle('Averaging PEM Files')

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

        # Zip the pem_files and rows so they can be filtered together
        pems_rows = zip(pem_files, rows)
        # Filter the pem_files to only keep un-averaged files
        filt_list = list(filter(lambda x: not x[0].is_split(), pems_rows))

        if len(filt_list) == 0:
            logger.warning(f"No un-split PEM files opened.")
            self.status_bar.showMessage(f"No un-split PEM files opened.", 2000)
            return

        bar = CustomProgressBar()
        bar.setMaximum(len(pem_files))

        with pg.ProgressDialog('Splitting PEM Files...', 0, len(filt_list)) as dlg:
            dlg.setBar(bar)
            dlg.setWindowTitle('Splitting PEM File Channels')

            for pem_file, row in filt_list:
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
            coil_area, ok_pressed = QInputDialog.getInt(self, "Set Coil Areas", "Coil Area:", default)
            if not ok_pressed:
                return

        bar = CustomProgressBar()
        bar.setMaximum(len(pem_files))

        with pg.ProgressDialog('Scaling PEM File Coil Area...', 0, len(pem_files)) as dlg:
            dlg.setBar(bar)
            dlg.setWindowTitle('Scaling PEM File Coil Area')

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
            bar = CustomProgressBar()
            bar.setMaximum(len(pem_files))

            with pg.ProgressDialog('Scaling PEM File Current...', 0, len(pem_files)) as dlg:
                dlg.setBar(bar)
                dlg.setWindowTitle('Scaling PEM File Current')

                for pem_file, row in zip(pem_files, rows):
                    dlg.setLabelText(f"Scaling current of {pem_file.filepath.name}")

                    pem_file = pem_file.scale_current(current)
                    self.refresh_pem(pem_file)
                    dlg += 1

            self.status_bar.showMessage(f"Process complete. "
                                        f"Current of {len(pem_files)} PEM files scaled to {current}.", 2000)

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

        for pem_file in pem_files:
            logger.info(f"Reversing {comp} data of {pem_file.filepath.name}.")
            filt = pem_file.data.Component == comp.upper()

            if filt.any():
                data = pem_file.data[filt]

                data.loc[:, 'Reading'] = data.loc[:, 'Reading'] * -1

                pem_file.data[filt] = data
                self.refresh_pem(pem_file)
            else:
                logger.warning(f"{pem_file.filepath.name} has no {comp} data.")

        self.status_bar.showMessage(f"Process complete. "
                                    f"{comp.upper()} of {len(pem_files)} PEM file(s) reversed.", 2000)

    def auto_merge_pem_files(self):

        def merge_pems(pem_files):
            """
            Merge the list of PEM files into a single PEM file.
            :param pem_files: list, PEMFile objects.
            :return: single PEMFile object
            """
            if isinstance(pem_files, list) and len(pem_files) > 1:
                logger.info(f"Merging {', '.join([f.filepath.name for f in pem_files])}.")
                # Data merging section
                currents = [pem_file.current for pem_file in pem_files]
                coil_areas = [pem_file.coil_area for pem_file in pem_files]

                # If any currents are different
                if not all([current == currents[0] for current in currents]):
                    response = self.message.question(self, 'Warning - Different currents',
                                                     f"{', '.join([f.filepath.name for f in pem_files])} do not have "
                                                     f"the same current. Proceed with merging anyway?",
                                                     self.message.Yes | self.message.No)
                    if response == self.message.No:
                        self.status_bar.showMessage('Aborted.', 2000)
                        return

                # If any coil areas are different
                if not all([coil_area == coil_areas[0] for coil_area in coil_areas]):
                    response = self.message.question(self, 'Warning - Different coil areas',
                                                     f"{', '.join([f.filepath.name for f in pem_files])} do not have "
                                                     f"the same coil area. Proceed with merging anyway?",
                                                     self.message.Yes | self.message.No)
                    if response == self.message.No:
                        self.status_bar.showMessage('Aborted.', 2000)
                        return

                # If the files aren't all split or un-split
                if any([pem_file.is_split() for pem_file in pem_files]) and any(
                        [not pem_file.is_split() for pem_file in pem_files]):
                    response = self.message.question(self, 'Warning - Different channel split states',
                                                     'There is a mix of channel splitting in the selected files. '
                                                     'Would you like to split the unsplit file(s) '
                                                     'and proceed with merging?',
                                                     self.message.Yes | self.message.No)
                    if response == self.message.Yes:
                        for pem_file in pem_files:
                            pem_file = pem_file.split()
                    else:
                        return

                # If the files aren't all de-rotated
                if any([pem_file.is_derotated() for pem_file in pem_files]) and any(
                        [not pem_file.is_derotated() for pem_file in pem_files]):
                    self.message.information(self, 'Error - Different states of XY de-rotation',
                                             'There is a mix of XY de-rotation in the selected files.')

                merged_pem = pem_files[0].copy()
                merged_pem.data = pd.concat([pem_file.data for pem_file in pem_files], axis=0, ignore_index=True)
                merged_pem.number_of_readings = sum([f.number_of_readings for f in pem_files])
                merged_pem.is_merged = True

                # Add the M tag
                if '[M]' not in pem_files[0].filepath.name:
                    merged_pem.filepath = merged_pem.filepath.with_name(
                        merged_pem.filepath.stem + '[M]' + merged_pem.filepath.suffix)

                merged_pem.save()
                return merged_pem

        files_to_open = []
        files_to_remove = []

        if not self.pem_files:
            logger.warning(f"No PEM files opened.")
            self.status_bar.showMessage(f"No PEM files opened.", 2000)
            return

        pem_files, rows = copy.deepcopy(self.pem_files), np.arange(self.table.rowCount())

        bh_files = [f for f in pem_files if f.is_borehole()]
        sf_files = [f for f in pem_files if f not in bh_files]

        # Merge surface files
        # Group the files by loop name
        for loop, loop_files in groupby(sf_files, key=lambda x: x.loop_name):
            loop_files = list(loop_files)
            logger.info(f"Auto merging loop {loop}.")

            # Group the files by line name
            for line, line_files in groupby(loop_files, key=lambda x: x.line_name):
                line_files = list(line_files)
                if len(line_files) > 1:
                    logger.info(f"Auto merging line {line}: {[f.filepath.name for f in line_files]}.")

                    # Merge the files
                    merged_pem = merge_pems(line_files)

                    if merged_pem is not None:
                        files_to_open.append(merged_pem)
                        files_to_remove.extend(line_files)

        # Merge borehole files
        # Group the files by loop
        for loop, loop_files in groupby(bh_files, key=lambda x: x.loop_name):
            loop_files = list(loop_files)

            # Group the files by hole name
            for hole, hole_files in groupby(loop_files, key=lambda x: x.line_name):
                hole_files = sorted(list(hole_files), key=lambda x: x.get_components())

                # Group the files by their components
                for components, comp_files in groupby(hole_files, key=lambda x: x.get_components()):
                    comp_files = list(comp_files)
                    if len(comp_files) > 1:
                        logger.info(f"Auto merging hole {hole}: {[f.filepath.name for f in comp_files]}")

                        # Merge the files
                        merged_pem = merge_pems(comp_files)

                        if merged_pem is not None:
                            files_to_open.append(merged_pem)
                            files_to_remove.extend(comp_files)

        rows = [pem_files.index(f) for f in files_to_remove]

        if self.delete_merged_files_cbox.isChecked():
            logger.warning(f"Removing rows {', '.join(rows)}.")
            self.remove_file(rows=rows)

        self.open_pem_files(files_to_open)

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
            name_item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.table.setItem(row, line_name_column, name_item)


class PathFilter(QWidget):
    accept_sig = QtCore.pyqtSignal()

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
        self.setWindowIcon(QIcon(os.path.join(icons_path, 'filter.png')))

        self.include_files_edit = QLineEdit()
        self.include_files_edit.setToolTip("Separate items with commas [,]")

        self.exclude_files_edit = QLineEdit('DTL, exp, Correct' if self.filetype == 'GPS' else '')
        self.exclude_files_edit.setToolTip("Separate items with commas [,]")

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
        files_gbox.setAlignment(QtCore.Qt.AlignCenter)
        files_gbox.setLayout(QFormLayout())
        files_gbox.layout().addRow(QLabel("Include:"), self.include_files_edit)
        files_gbox.layout().addRow(QLabel("Exclude:"), self.exclude_files_edit)

        self.layout().addRow(files_gbox)

        folders_gbox = QGroupBox('Folders')
        folders_gbox.setAlignment(QtCore.Qt.AlignCenter)
        folders_gbox.setLayout(QFormLayout())
        folders_gbox.layout().addRow(QLabel("Include:"), self.include_folders_edit)
        folders_gbox.layout().addRow(QLabel("Exclude:"), self.exclude_folders_edit)

        self.layout().addRow(folders_gbox)

        extensions_gbox = QGroupBox('Extensions')
        extensions_gbox.setAlignment(QtCore.Qt.AlignCenter)
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
        if e.key() == QtCore.Qt.Key_Escape:
            self.close()

    def reset(self):
        self.include_files_edit.setText('')
        self.exclude_files_edit.setText('DTL, exp, Correct' if self.filetype == 'GPS' else '')
        self.include_folders_edit.setText('GPS' if self.filetype == 'GPS' else '')
        self.exclude_folders_edit.setText('')
        self.include_exts_edit.setText('')
        self.exclude_exts_edit.setText('')

    def close(self):
        self.accept_sig.emit()
        self.hide()


class FrequencyConverter(QWidget):
    """
    Converts timebase to frequency and vise-versa.
    """
    def __init__(self, parent=None):
        super().__init__()
        self.parent = parent

        def convert_freq_to_timebase():
            freq_edit.blockSignals(True)
            timebase_edit.blockSignals(True)
            timebase_edit.setText('')

            try:
                freq = float(freq_edit.text())
            except ValueError:
                logger.error(f'{freq_edit.text()} is not a number.')
            else:
                timebase = (1 / freq) * (1000 / 4)
                timebase_edit.setText(f"{timebase:.2f}")

            freq_edit.blockSignals(False)
            timebase_edit.blockSignals(False)

        def convert_timebase_to_freq():
            freq_edit.blockSignals(True)
            timebase_edit.blockSignals(True)
            freq_edit.setText('')

            try:
                timebase = float(timebase_edit.text())
            except ValueError:
                logger.error(f'{timebase_edit.text()} is not a number.')
            else:
                freq = (1 / (4 * timebase / 1000))
                freq_edit.setText(f"{freq:.2f}")

            freq_edit.blockSignals(False)
            timebase_edit.blockSignals(False)

        self.setWindowTitle('Timebase / Frequency Converter')
        self.setWindowIcon(QIcon(os.path.join(icons_path, 'freq_timebase_calc.png')))
        layout = QGridLayout()
        self.setLayout(layout)

        timebase_label = QLabel('Timebase (ms)')
        freq_label = QLabel('Freqency (Hz)')
        timebase_edit = QLineEdit()
        timebase_edit.textEdited.connect(convert_timebase_to_freq)
        freq_edit = QLineEdit()
        freq_edit.textEdited.connect(convert_freq_to_timebase)

        layout.addWidget(timebase_label, 0, 0)
        layout.addWidget(timebase_edit, 0, 1)
        layout.addWidget(freq_label, 2, 0)
        layout.addWidget(freq_edit, 2, 1)

    def keyPressEvent(self, e):
        if e.key() == QtCore.Qt.Key_Escape:
            self.close()


class PDFPlotPrinter(QWidget, Ui_PDFPlotPrinterWidget):
    """
    Widget to handle printing PDF plots for PEM/RI files.
    """

    def __init__(self, parent=None):
        super().__init__()
        self.parent = parent
        self.setupUi(self)
        self.setWindowTitle("PDF Printing Options")
        self.setWindowIcon(QIcon(os.path.join(icons_path, 'pdf.png')))

        self.pem_files = []
        self.ri_files = []
        self.crs = None

        self.plan_map_options = PlanMapOptions(parent=self)
        self.message = QMessageBox()

        # Set validations
        int_validator = QtGui.QIntValidator()
        self.max_range_edit.setValidator(int_validator)
        self.min_range_edit.setValidator(int_validator)
        self.section_depth_edit.setValidator(int_validator)

        # Signals
        def get_save_file():
            default_path = self.pem_files[-1].filepath.parent
            save_dir = QFileDialog.getSaveFileName(self, '', str(default_path), 'PDF Files (*.PDF)')[0]
            logger.info(f"Saving PDFs to {save_dir}.")
            if save_dir:
                self.save_path_edit.setText(save_dir)

        self.print_btn.clicked.connect(self.print_pdfs)
        self.cancel_btn.clicked.connect(self.close)
        self.plan_map_options_btn.clicked.connect(self.plan_map_options.show)
        self.change_save_path_btn.clicked.connect(get_save_file)

    def keyPressEvent(self, e):
        if e.key() == QtCore.Qt.Key_Escape:
            self.close()
        elif e.key() == QtCore.Qt.Key_Enter:
            self.print_pdfs()

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
            printer = PEMPrinter(parent=self, **plot_kwargs)

            try:
                # PEM Files and RI files zipped together for when they get sorted
                printer.print_files(save_dir, files=list(zip(self.pem_files, self.ri_files)))
            except FileNotFoundError:
                logger.critical(f'{save_dir} does not exist.')
                self.message.information(self, 'Error', f'{save_dir} does not exist')
            except IOError:
                logger.critical(f"{save_dir} is currently opened.")
                self.message.information(self, 'Error', f'{save_dir} is currently opened')
            except Exception as e:
                logger.critical(f"{e}.")
                self.message.critical(self, 'Error', str(e))
            finally:
                self.close()
        else:
            logger.error(f"No file name passed.")
            self.message.critical(self, 'Error', 'Invalid file name')


class PlanMapOptions(QWidget, Ui_PlanMapOptionsWidget):
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
        e.accept()

    def keyPressEvent(self, e):
        if e.key() == QtCore.Qt.Key_Escape:
            self.close()
        elif e.key() == QtCore.Qt.Key_Return:
            self.close()


class GPSShareWidget(QWidget):
    accept_sig = QtCore.pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__()
        self.parent = parent
        self.pem_files = []
        self.cboxes = []

        # Format window
        self.setWindowTitle(f"Share GPS")
        self.setWindowIcon(QIcon(os.path.join(icons_path, 'share_gps.png')))

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
        self.accept_btn.setFocusPolicy(QtCore.Qt.StrongFocus)

        # Create the header label
        header_label = QLabel('File')
        header_label.setFont(QtGui.QFont('Arial', 10))

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
        self.accept_btn.clicked.connect(lambda: self.accept_sig.emit([c.isChecked() for c in self.cboxes]))
        self.accept_btn.clicked.connect(self.close)

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
            label.setFont(QtGui.QFont('Arial', 10))
            self.layout.insertRow(i + 2, label, cbox)

            if i == index_of_source:
                cbox.setEnabled(False)
                label.setEnabled(False)

        self.show()


class ChannelTimeViewer(QMainWindow):

    def __init__(self, pem_file, parent=None):
        """
        Class that visualizes channel times in a PEMFile using a color gradient table.
        :param pem_file: PEMFile object
        :param parent: Qt parent object
        """
        super().__init__()

        self.pem_file = pem_file
        self.parent = parent

        # Format window
        self.setLayout(QVBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)

        self.sizePolicy().setHorizontalPolicy(QSizePolicy.Maximum)
        self.resize(600, 600)
        self.setWindowTitle(f"Channel Times - {self.pem_file.filepath.name}")

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

        # Format table
        self.table = pg.TableWidget()
        self.layout().addWidget(self.table)
        self.setCentralWidget(self.table)

        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.sizePolicy().setHorizontalPolicy(QSizePolicy.Maximum)
        self.table.setFrameStyle(QFrame.NoFrame)

        # Signals
        self.units_combo.currentTextChanged.connect(self.fill_channel_table)

        self.fill_channel_table()
        self.show()

    def fill_channel_table(self):
        """
        Fill and color the table with the channel times of the PEMFile.
        """

        def color_table():
            """
            Color the background of the cells based on their values. Also colors the text and aligns the text.
            """
            mpl_red, mpl_blue = np.array([34, 79, 214]) / 256, np.array([247, 42, 42]) / 256
            q_red = QtGui.QColor(mpl_red[0] * 255,
                                 mpl_red[1] * 255,
                                 mpl_red[2] * 255)
            q_blue = QtGui.QColor(mpl_blue[0] * 255,
                                  mpl_blue[1] * 255,
                                  mpl_blue[2] * 255)

            for i, column in enumerate(df.columns):

                if column != 'Remove':
                    # Normalize column values for color mapping
                    mn, mx, count = df[column].min(), df[column].max(), len(df[column])
                    norm = plt.Normalize(mn, mx)

                    # Create a custom color map
                    cm = LCMap.from_list('Custom', [mpl_red, mpl_blue])

                    # Apply the color map to the values in the column
                    colors = cm(norm(df[column].to_numpy()))

                for row in range(self.table.rowCount()):
                    item = self.table.item(row, i)

                    # Color the text
                    item.setForeground(QtGui.QColor(255, 255, 255))
                    item.setTextAlignment(QtCore.Qt.AlignCenter)

                    if column == 'Remove':
                        # Color the Remove column
                        if item.text() == 'False':
                            item.setBackground(q_red)
                        else:
                            item.setBackground(q_blue)

                    else:
                        # Color the background based on the value
                        color = QtGui.QColor(colors[row][0] * 255,
                                             colors[row][1] * 255,
                                             colors[row][2] * 255)
                        item.setBackground(color)

        df = self.pem_file.channel_times.copy()

        if self.units_combo.currentText() == 'µs':
            df.loc[:, 'Start':'Width'] = df.loc[:, 'Start':'Width'] * 1000000
            text_format = '%0.0f'
        elif self.units_combo.currentText() == 'ms':
            df.loc[:, 'Start':'Width'] = df.loc[:, 'Start':'Width'] * 1000
            text_format = '%0.3f'
        else:
            df.loc[:, 'Start':'Width'] = df.loc[:, 'Start':'Width']
            text_format = '%0.6f'

        self.table.setData(df.to_dict('index'))
        self.table.setFormat(text_format)
        # self.table.resizeColumnsToContents()
        self.table.resizeRowsToContents()
        # self.resize(self.table.size())

        color_table()


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
    accept_sig = QtCore.pyqtSignal(object)

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
                item.setTextAlignment(QtCore.Qt.AlignCenter)
        self.table.resizeRowsToContents()


def main():
    from src.pem.pem_getter import PEMGetter
    app = QApplication(sys.argv)
    mw = PEMHub()
    pg = PEMGetter()
    pem_parser = PEMParser()

    # ff = PathFilter()
    # ff.show()

    mw.show()
    pem_files = [r'C:\_Data\2020\Wolfden\G-040\DUMP\November 07, 2020\DMP\xy-040.DMP2']
    # pem_files = [pem_parser.parse(r'C:\_Data\2020\Juno\Borehole\TME-08-02\RAW\tme-08-02 flux_13.PEM')]
    # pem_files = pg.get_pems(file=r'g6-09-01 flux_08.PEM')
    # pem_files = pg.get_pems(client='Raglan', file='718-3755 XYZT.PEM')
    # pem_files = pg.get_pems(client='Kazzinc', number=4)
    # pem_files = pg.get_pems(client='Minera', subfolder='CPA-5051', number=4)
    # pem_files = pg.get_pems(client='Minera', number=1)
    # pem_files = pg.get_pems(random=True, number=1)
    # pem_files = [r'C:\_Data\2020\Juno\Borehole\DDH5-01-38\Final\ddh5-01-38.PEM']

    mw.open_dmp_files(pem_files)
    # mw.open_pem_files(pem_files)
    # mw.open_mag_dec(mw.pem_files[0])

    # mw.project_dir_edit.setText(r'C:\_Data\2020\Juno\Borehole')
    # mw.move_dir_tree_to(r'C:\_Data\2020\Juno\Borehole')
    # mw.pem_list_filter.exclude_files_edit.setText('XYT.pem, xyg.pem')
    #
    # mw.pem_list_filter.include_folders_edit.setText('final')
    #
    # mw.pem_list_filter.exclude_folders_edit.setText('backup')
    # mw.pem_list_filter.accept_sig.emit()

    app.exec_()


if __name__ == '__main__':
    logger = logging.getLogger(__name__)

    main()
    # cProfile.run('main()', 'restats')
    # p = pstats.Stats('restats')
    # p.sort_stats('cumulative').print_stats(.5)

    # p.sort_stats('time', 'cumulative').print_stats()
    # p.strip_dirs().sort_stats(-1).print_stats()
