import copy
import datetime
import os
import re
import csv
import sys
import time
import pandas as pd
import numpy as np
import simplekml
import natsort
import stopit
from pathlib import Path
from shutil import copyfile
from itertools import groupby
from PyQt5 import (QtCore, QtGui, uic)
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (QWidget, QMainWindow, QApplication, QDesktopWidget, QMessageBox, QFileDialog, QHeaderView,
                             QTableWidgetItem, QAction, QMenu, QGridLayout, QTextBrowser, QFileSystemModel,QProgressBar,
                             QInputDialog, QErrorMessage, QLabel, QLineEdit, QPushButton, QAbstractItemView,
                             QVBoxLayout)
# from pyqtspinner.spinner import WaitingSpinner
import geomag

from src.gps.gps_editor import (SurveyLine, TransmitterLoop, BoreholeCollar, BoreholeSegments,
                                GPXEditor, CRS)
from src.gps.gpx_creator import GPXCreator

from src.pem.pem_file import PEMFile, PEMParser, DMPParser, StationConverter
from src.pem.pem_plotter import PEMPrinter, CustomProgressBar
from src.qt_py.pem_planner import LoopPlanner, GridPlanner

from src.qt_py.pem_info_widget import PEMFileInfoWidget
from src.qt_py.unpacker import Unpacker
from src.qt_py.ri_importer import BatchRIImporter
from src.qt_py.gps_adder import LineAdder, LoopAdder
from src.qt_py.name_editor import BatchNameEditor
from src.qt_py.station_splitter import StationSplitter
from src.qt_py.map_widgets import Map3DViewer, ContourMapViewer, FoliumMap
from src.qt_py.derotator import Derotator
from src.qt_py.pem_geometry import PEMGeometry
from src.qt_py.pem_plot_editor import PEMPlotEditor

from src.damp.db_plot import DBPlot

__version__ = '0.11.0'

sys._excepthook = sys.excepthook


def exception_hook(exctype, value, traceback):
    print(exctype, value, traceback)
    sys._excepthook(exctype, value, traceback)
    sys.exit(1)


sys.excepthook = exception_hook

# Modify the paths for when the script is being run in a frozen state (i.e. as an EXE)
if getattr(sys, 'frozen', False):
    application_path = sys._MEIPASS
    pemhubWindowCreatorFile = 'qt_ui\\pem_hub.ui'
    planMapOptionsCreatorFile = 'qt_ui\\plan_map_options.ui'
    pdfPrintOptionsCreatorFile = 'qt_ui\\pdf_plot_printer.ui'
    icons_path = 'icons'
else:
    application_path = os.path.dirname(os.path.abspath(__file__))
    pemhubWindowCreatorFile = os.path.join(os.path.dirname(application_path), 'qt_ui\\pem_hub.ui')
    planMapOptionsCreatorFile = os.path.join(os.path.dirname(application_path), 'qt_ui\\plan_map_options.ui')
    pdfPrintOptionsCreatorFile = os.path.join(os.path.dirname(application_path), 'qt_ui\\pdf_plot_printer.ui')
    icons_path = os.path.join(os.path.dirname(application_path), "qt_ui\\icons")

# Load Qt ui file into a class
Ui_PEMHubWindow, QtBaseClass = uic.loadUiType(pemhubWindowCreatorFile)
Ui_PlanMapOptionsWidget, QtBaseClass = uic.loadUiType(planMapOptionsCreatorFile)
Ui_PDFPlotPrinterWidget, QtBaseClass = uic.loadUiType(pdfPrintOptionsCreatorFile)


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
        self.text_browsers = []
        self.pb = CustomProgressBar()
        self.pb_win = QWidget()  # Progress bar window
        self.pb_win.resize(400, 45)
        self.pb_win.setLayout(QVBoxLayout())
        self.pb_win.setWindowTitle('Saving PDF Plots...')
        self.pb_win.layout().addWidget(self.pb)

        # Status bar formatting
        self.selection_label = QLabel()
        self.selection_label.setIndent(5)
        self.spacer_label = QLabel()
        self.project_dir_label = QLabel()
        self.project_dir_label.setIndent(5)

        # Format the borders of the items in the status bar
        self.setStyleSheet("QStatusBar::item {border-left: 1px solid gray; border-top: 1px solid gray}")
        self.status_bar.setStyleSheet("border-top: 1px solid gray; border-top: None")

        self.status_bar.addWidget(self.selection_label, 0)
        self.status_bar.addWidget(self.spacer_label, 1)
        self.status_bar.addWidget(self.project_dir_label, 0)

        # Widgets
        # self.gpx_editor = GPXEditor()
        self.station_splitter = StationSplitter(parent=self)
        self.grid_planner = GridPlanner(parent=self)
        self.loop_planner = LoopPlanner(parent=self)
        self.db_plot = DBPlot(parent=self)
        self.unpacker = Unpacker(parent=self)
        self.gpx_creator = GPXCreator(parent=self)
        self.map_viewer_3d = Map3DViewer(parent=self)
        self.freq_con = FrequencyConverter(parent=self)
        self.contour_viewer = ContourMapViewer(parent=self)
        self.folium_map = FoliumMap()

        # Project tree
        self.project_dir = None
        self.file_sys_model = QFileSystemModel()
        self.file_sys_model.setRootPath(QtCore.QDir.rootPath())
        self.project_tree.setModel(self.file_sys_model)
        self.project_tree.setColumnHidden(1, True)
        self.project_tree.setColumnHidden(2, True)
        self.project_tree.setColumnHidden(3, True)
        self.project_tree.clicked.connect(self.project_dir_changed)
        # self.move_dir_tree_to(self.file_sys_model.rootPath())
        self.available_pems = []
        self.available_gps = []

        self.init_menus()
        self.init_signals()

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
            'Repeat\nStations'
        ]
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)

        for i, col in enumerate(self.table_columns[1:]):
            header.setSectionResizeMode(i + 1, QHeaderView.ResizeToContents)

        self.gps_systems = ['', 'UTM']
        self.gps_zones = [''] + [f"{num} North" for num in range(1, 61)] + [f"{num} South" for num in range(1, 61)]
        self.gps_datums = ['', 'NAD 1927', 'NAD 1983', 'WGS 1984']
        for system in self.gps_systems:
            self.gps_system_cbox.addItem(system)
        for zone in self.gps_zones:
            self.gps_zone_cbox.addItem(zone)
        for datum in self.gps_datums:
            self.gps_datum_cbox.addItem(datum)

        # Actions
        self.actionDel_File = QAction("&Remove File", self)
        self.actionDel_File.setShortcut("Del")
        self.actionDel_File.triggered.connect(self.remove_file)
        self.addAction(self.actionDel_File)
        self.actionDel_File.setEnabled(False)

        # self.actionClear_Files = QAction("&Clear All Files", self)
        # self.actionClear_Files.setShortcut("Shift+Del")
        # self.actionClear_Files.setStatusTip("Clear all files")
        # self.actionClear_Files.setToolTip("Clear all files")
        # self.actionClear_Files.triggered.connect(lambda: self.remove_file(rows=np.arange(self.table.rowCount())))

        self.merge_action = QAction("&Merge", self)
        self.merge_action.triggered.connect(lambda: self.merge_pem_files(selected=True))
        self.merge_action.setShortcut("Shift+M")

    def init_ui(self):
        """
        Initializing the UI.
        :return: None
        """

        self.setupUi(self)
        self.setAcceptDrops(True)
        self.setWindowTitle("PEMPro  v" + str(__version__))
        self.setWindowIcon(
            QIcon(os.path.join(icons_path, 'conder.png')))
        self.resize(1700, 900)
        self.center_window()

        self.refresh_pem_list_btn.setIcon(QIcon(os.path.join(icons_path, 'refresh.png')))
        self.refresh_gps_list_btn.setIcon(QIcon(os.path.join(icons_path, 'refresh.png')))
        self.refresh_pem_list_btn.setText('')
        self.refresh_gps_list_btn.setText('')

        # self.stackedWidget.hide()
        self.piw_frame.hide()
        self.table.horizontalHeader().hide()
        # self.pemInfoDockWidget.hide()

    def init_menus(self):
        """
        Initializing all actions.
        :return: None
        """
        # 'File' menu
        self.actionOpenFile.setShortcut("Ctrl+O")
        self.actionOpenFile.setStatusTip('Open file')
        self.actionOpenFile.setToolTip('Open file')
        self.actionOpenFile.setIcon(QIcon(os.path.join(icons_path, 'open.png')))
        self.actionOpenFile.triggered.connect(self.open_file_dialog)

        self.actionSaveFiles.setShortcut("Ctrl+S")
        self.actionSaveFiles.setIcon(QIcon(os.path.join(icons_path, 'save.png')))
        self.actionSaveFiles.setStatusTip("Save all files")
        self.actionSaveFiles.setToolTip("Save all files")
        self.actionSaveFiles.triggered.connect(lambda: self.save_pem_files(selected=False))

        self.actionSave_Files_as_XYZ.setStatusTip("Save all files as XYZ files. Only for surface surveys.")
        self.actionSave_Files_as_XYZ.triggered.connect(lambda: self.save_as_xyz(selected=False))

        self.actionExport_Files.setShortcut("F11")
        self.actionExport_Files.setStatusTip("Export all files to a specified location.")
        self.actionExport_Files.setToolTip("Export all files to a specified location.")
        self.actionExport_Files.triggered.connect(lambda: self.export_pem_files(selected=False,
                                                                                export_final=False))

        self.actionExport_Final_PEM_Files.setShortcut("F9")
        self.actionExport_Final_PEM_Files.setStatusTip("Export the final PEM files")
        self.actionExport_Final_PEM_Files.setToolTip("Export the final PEM files")
        self.actionExport_Final_PEM_Files.triggered.connect(lambda: self.export_pem_files(selected=False,
                                                                                          export_final=True))

        # self.actionPrint_Plots_to_PDF.setShortcut("F12")
        # self.actionPrint_Plots_to_PDF.setStatusTip("Print plots to a PDF file")
        # self.actionPrint_Plots_to_PDF.setToolTip("Print plots to a PDF file")
        # self.actionPrint_Plots_to_PDF.triggered.connect(self.open_pdf_plot_printer)

        self.actionBackup_Files.setStatusTip("Backup all files in the table.")
        self.actionBackup_Files.setToolTip("Backup all files in the table.")
        self.actionBackup_Files.triggered.connect(self.backup_files)

        self.actionImport_RI_Files.setShortcut("Ctrl+I")
        self.actionImport_RI_Files.setStatusTip("Import multiple RI files")
        self.actionImport_RI_Files.setToolTip("Import multiple RI files")
        self.actionImport_RI_Files.triggered.connect(self.open_ri_importer)

        # PEM menu
        self.actionRename_All_Lines_Holes.setStatusTip("Rename all line/hole names")
        self.actionRename_All_Lines_Holes.setToolTip("Rename all line/hole names")
        self.actionRename_All_Lines_Holes.triggered.connect(lambda: self.open_batch_renamer(type='Line'))

        self.actionRename_All_Files.setStatusTip("Rename all file names")
        self.actionRename_All_Files.setToolTip("Rename all file names")
        self.actionRename_All_Files.triggered.connect(lambda: self.open_batch_renamer(type='File'))

        self.actionAverage_All_PEM_Files.setStatusTip("Average all PEM files")
        self.actionAverage_All_PEM_Files.setToolTip("Average all PEM files")
        self.actionAverage_All_PEM_Files.setIcon(QIcon(os.path.join(icons_path, 'average.png')))
        self.actionAverage_All_PEM_Files.setShortcut("F5")
        self.actionAverage_All_PEM_Files.triggered.connect(lambda: self.average_pem_data(selected=False))
        # self.actionAverage_All_PEM_Files.triggered.connect(self.refresh_table)

        self.actionSplit_All_PEM_Files.setStatusTip("Remove on-time channels for all PEM files")
        self.actionSplit_All_PEM_Files.setToolTip("Remove on-time channels for all PEM files")
        self.actionSplit_All_PEM_Files.setIcon(QIcon(os.path.join(icons_path, 'split.png')))
        self.actionSplit_All_PEM_Files.setShortcut("F6")
        self.actionSplit_All_PEM_Files.triggered.connect(lambda: self.split_pem_channels(selected=False))
        # self.actionSplit_All_PEM_Files.triggered.connect(self.refresh_table)

        self.actionScale_All_Currents.setStatusTip("Scale the current of all PEM Files to the same value")
        self.actionScale_All_Currents.setToolTip("Scale the current of all PEM Files to the same value")
        self.actionScale_All_Currents.setIcon(QIcon(os.path.join(icons_path, 'current.png')))
        self.actionScale_All_Currents.setShortcut("F7")
        self.actionScale_All_Currents.triggered.connect(lambda: self.scale_pem_current(selected=False))

        self.actionChange_All_Coil_Areas.setStatusTip("Scale all coil areas to the same value")
        self.actionChange_All_Coil_Areas.setToolTip("Scale all coil areas to the same value")
        self.actionChange_All_Coil_Areas.setIcon(QIcon(os.path.join(icons_path, 'coil.png')))
        self.actionChange_All_Coil_Areas.setShortcut("F8")
        self.actionChange_All_Coil_Areas.triggered.connect(lambda: self.scale_pem_coil_area(selected=False))

        # GPS menu
        self.actionSave_as_KMZ.setStatusTip("Create a KMZ file using all GPS in the opened PEM file(s)")
        self.actionSave_as_KMZ.setToolTip("Create a KMZ file using all GPS in the opened PEM file(s)")
        self.actionSave_as_KMZ.setIcon(QIcon(os.path.join(icons_path, 'google_earth.png')))
        self.actionSave_as_KMZ.triggered.connect(self.save_as_kmz)

        self.actionExport_All_GPS.setStatusTip("Export all GPS in the opened PEM file(s) to separate CSV files")
        self.actionExport_All_GPS.setToolTip("Export all GPS in the opened PEM file(s) to separate CSV files")
        self.actionExport_All_GPS.setIcon(QIcon(os.path.join(icons_path, 'csv.png')))
        self.actionExport_All_GPS.triggered.connect(self.export_all_gps)

        # Map menu
        self.actionPlan_Map.setStatusTip("Plot all PEM files on an interactive plan map")
        self.actionPlan_Map.setToolTip("Plot all PEM files on an interactive plan map")
        self.actionPlan_Map.setIcon(QIcon(os.path.join(icons_path, 'folium.png')))
        self.actionPlan_Map.triggered.connect(lambda: self.folium_map.open(self.get_updated_pem_files(), self.get_crs()))

        self.action3D_Map.setStatusTip("Show 3D map of all PEM files")
        self.action3D_Map.setToolTip("Show 3D map of all PEM files")
        self.action3D_Map.setShortcut('Ctrl+M')
        self.action3D_Map.setIcon(QIcon(os.path.join(icons_path, '3d_map2.png')))
        self.action3D_Map.triggered.connect(lambda: self.map_viewer_3d.open(self.get_updated_pem_files()))

        self.actionContour_Map.setIcon(QIcon(os.path.join(icons_path, 'contour_map3.png')))
        self.actionContour_Map.setStatusTip("Show a contour map of surface PEM files")
        self.actionContour_Map.setToolTip("Show a contour map of surface PEM files")
        self.actionContour_Map.triggered.connect(lambda: self.contour_viewer.open(self.get_updated_pem_files()))

        # Tools menu
        self.actionLoop_Planner.setStatusTip("Loop planner")
        self.actionLoop_Planner.setToolTip("Loop planner")
        self.actionLoop_Planner.setIcon(QIcon(os.path.join(icons_path, 'loop_planner.png')))
        self.actionLoop_Planner.triggered.connect(lambda: self.loop_planner.show())

        self.actionGrid_Planner.setStatusTip("Grid planner")
        self.actionGrid_Planner.setToolTip("Grid planner")
        self.actionGrid_Planner.setIcon(QIcon(os.path.join(icons_path, 'grid_planner.png')))
        self.actionGrid_Planner.triggered.connect(lambda: self.grid_planner.show())

        self.actionConvert_Timebase_Frequency.setStatusTip("Two way conversion between timebase and frequency")
        self.actionConvert_Timebase_Frequency.setToolTip("Two way conversion between timebase and frequency")
        self.actionConvert_Timebase_Frequency.setIcon(QIcon(os.path.join(icons_path, 'freq_timebase_calc.png')))
        self.actionConvert_Timebase_Frequency.triggered.connect(lambda: self.freq_con.show())

        self.actionDamping_Box_Plotter.setStatusTip("Plot damping box data")
        self.actionDamping_Box_Plotter.setToolTip("Plot damping box data")
        self.actionDamping_Box_Plotter.setIcon(QIcon(os.path.join(icons_path, 'db_plot 32.png')))
        self.actionDamping_Box_Plotter.triggered.connect(lambda: self.db_plot.show())

        self.actionUnpacker.setStatusTip("Unpack and organize a raw folder")
        self.actionUnpacker.setToolTip("Unpack and organize a raw folder")
        self.actionUnpacker.setIcon(QIcon(os.path.join(icons_path, 'unpacker_1.png')))
        self.actionUnpacker.triggered.connect(lambda: self.unpacker.show())

        self.actionGPX_Creator.setStatusTip("GPX file creator")
        self.actionGPX_Creator.setToolTip("GPX file creator")
        self.actionGPX_Creator.setIcon(QIcon(os.path.join(icons_path, 'gpx_creator_4.png')))
        self.actionGPX_Creator.triggered.connect(lambda: self.gpx_creator.show())

    def init_signals(self):
        """
        Initializing all signals.
        :return: None
        """

        def set_shared_header(header):
            """
            Signal slot, change the header information for each file in the table when the shared header LineEdits are
            changed
            :param header: str, either 'client', 'grid', or 'loop'.
            """

            def color_cell(row, column, color, alpha=50):
                """
                Color an entire table row
                :param row: Int, Row of the table to color
                :param column: Int, Column of the table to color
                :param color: str, The desired color
                :return: None
                """
                color = QtGui.QColor(color)
                color.setAlpha(alpha)
                self.table.item(row, column).setBackground(color)

            self.table.blockSignals(True)

            bold_font, normal_font = QtGui.QFont(), QtGui.QFont()
            bold_font.setBold(True)
            normal_font.setBold(False)

            files, rows = self.pem_files, np.arange(self.table.rowCount())
            for file, row in zip(files, rows):

                if header == 'client':
                    client = self.client_edit.text() if self.share_client_cbox.isChecked() else file.client

                    item = QTableWidgetItem(str(client))
                    if client != file.client:
                        item.setFont(bold_font)
                    else:
                        item.setFont(normal_font)

                elif header == 'grid':
                    grid = self.grid_edit.text() if self.share_grid_cbox.isChecked() else file.grid

                    item = QTableWidgetItem(str(grid))
                    if grid != file.grid:
                        item.setFont(bold_font)
                    else:
                        item.setFont(normal_font)

                elif header == 'loop':
                    loop = self.loop_edit.text() if self.share_loop_cbox.isChecked() else file.loop_name

                    item = QTableWidgetItem(str(loop))
                    if loop != file.loop:
                        item.setFont(bold_font)
                    else:
                        item.setFont(normal_font)

                else:
                    raise ValueError(f"{header} is not a valid header")

                column = self.table_columns.index(header.title())

                item.setTextAlignment(QtCore.Qt.AlignCenter)
                self.table.setItem(row, column, item)
                color_cell(row, column, 'white' if file.has_all_gps() else 'magenta')

            self.table.blockSignals(False)

        def toggle_pem_list_buttons():
            if self.pem_list.selectedItems():
                self.add_pem_btn.setEnabled(True)
                self.remove_pem_btn.setEnabled(True)
            else:
                self.add_pem_btn.setEnabled(False)
                self.remove_pem_btn.setEnabled(False)

        def toggle_gps_list_buttons():
            if self.gps_list.selectedItems():
                self.add_gps_btn.setEnabled(True)
                self.remove_gps_btn.setEnabled(True)
            else:
                self.add_gps_btn.setEnabled(False)
                self.remove_gps_btn.setEnabled(False)

        def add_pem_list_files():
            selected_rows = [self.pem_list.row(i) for i in self.pem_list.selectedItems()]
            filepaths = [str(self.available_pems[j]) for j in selected_rows]
            self.open_pem_files(filepaths)

        def add_gps_list_files():
            selected_rows = [self.gps_list.row(i) for i in self.gps_list.selectedItems()]
            filepaths = [str(self.available_gps[j]) for j in selected_rows]
            self.open_gps_files(filepaths)

        def remove_pem_list_files():
            selected_rows = [self.pem_list.row(i) for i in self.pem_list.selectedItems()]
            for row in sorted(selected_rows, reverse=True):
                self.pem_list.takeItem(row)
                self.available_pems.pop(row)

        def remove_gps_list_files():
            selected_rows = [self.gps_list.row(i) for i in self.gps_list.selectedItems()]
            for row in sorted(selected_rows, reverse=True):
                self.gps_list.takeItem(row)
                self.available_gps.pop(row)

        def update_selection_text():
            """
            Change the information of the selected pem file(s) in the status bar
            """
            pem_files, rows = self.get_selected_pem_files(updated=False)
            info = ''
            if len(pem_files) == 1:
                file = pem_files[0]
                name = f"File: {file.filepath.name}"
                client = f"Client: {file.client}"
                line_name = f"Line/Hole: {file.line_name}"
                loop_name = f"Loop: {file.loop_name}"
                timebase = f"Timebase: {file.timebase}ms"
                survey_type = f"Survey Type: {file.get_survey_type()}"
                info = '    '.join([name, client, line_name, loop_name, timebase, survey_type])
            elif len(pem_files) > 1:
                info = f"{len(pem_files)} selected"
            else:
                pass

            self.selection_label.setText(info)

        self.table.viewport().installEventFilter(self)
        self.table.installEventFilter(self)
        self.table.setFocusPolicy(QtCore.Qt.StrongFocus)

        self.table.itemSelectionChanged.connect(lambda: self.stackedWidget.setCurrentIndex(self.table.currentRow()))
        self.table.itemSelectionChanged.connect(update_selection_text)
        self.table.cellChanged.connect(self.table_value_changed)

        self.print_plots_btn.clicked.connect(self.open_pdf_plot_printer)

        self.share_client_cbox.stateChanged.connect(
            lambda: self.client_edit.setEnabled(self.share_client_cbox.isChecked()))
        self.share_grid_cbox.stateChanged.connect(
            lambda: self.grid_edit.setEnabled(self.share_grid_cbox.isChecked()))
        self.share_loop_cbox.stateChanged.connect(
            lambda: self.loop_edit.setEnabled(self.share_loop_cbox.isChecked()))
        # single_row must be explicitly stated since stateChanged returns an int based on the state
        self.share_client_cbox.stateChanged.connect(lambda: set_shared_header('client'))
        self.share_grid_cbox.stateChanged.connect(lambda: set_shared_header('grid'))
        self.share_loop_cbox.stateChanged.connect(lambda: set_shared_header('loop'))

        self.client_edit.textChanged.connect(lambda: set_shared_header('client'))
        self.grid_edit.textChanged.connect(lambda: set_shared_header('grid'))
        self.loop_edit.textChanged.connect(lambda: set_shared_header('loop'))

        # self.share_range_cbox.toggled.connect(
        #     lambda: self.min_range_edit.setEnabled(self.share_range_cbox.isChecked()))
        # self.share_range_cbox.toggled.connect(
        #     lambda: self.max_range_edit.setEnabled(self.share_range_cbox.isChecked()))
        # self.share_range_cbox.stateChanged.connect(self.refresh_table)

        # self.min_range_edit.editingFinished.connect(lambda: self.refresh_table(single_row=False))
        # self.max_range_edit.editingFinished.connect(lambda: self.refresh_table(single_row=False))

        self.auto_name_line_btn.clicked.connect(self.auto_name_lines)
        self.auto_merge_files_btn.clicked.connect(lambda: self.merge_pem_files(auto_select=True))

        self.reverse_all_z_btn.clicked.connect(lambda: self.reverse_all_data(comp='Z'))
        self.reverse_all_x_btn.clicked.connect(lambda: self.reverse_all_data(comp='X'))
        self.reverse_all_y_btn.clicked.connect(lambda: self.reverse_all_data(comp='Y'))
        self.rename_all_repeat_stations_btn.clicked.connect(self.rename_all_repeat_stations)

        self.gps_system_cbox.currentIndexChanged.connect(
            lambda: self.gps_zone_cbox.setEnabled(True if self.gps_system_cbox.currentText() == 'UTM' else False))

        self.refresh_pem_list_btn.clicked.connect(self.fill_pem_list)
        self.refresh_gps_list_btn.clicked.connect(self.fill_gps_list)

        self.pem_list.itemSelectionChanged.connect(toggle_pem_list_buttons)
        self.gps_list.itemSelectionChanged.connect(toggle_gps_list_buttons)

        self.add_pem_btn.clicked.connect(add_pem_list_files)
        self.add_gps_btn.clicked.connect(add_gps_list_files)
        self.remove_pem_btn.clicked.connect(remove_pem_list_files)
        self.remove_gps_btn.clicked.connect(remove_gps_list_files)

    def center_window(self):
        qt_rectangle = self.frameGeometry()
        center_point = QDesktopWidget().availableGeometry().center()
        qt_rectangle.moveCenter(center_point)
        self.move(qt_rectangle.topLeft())

    def contextMenuEvent(self, event):
        """
        Right-click context menu items.
        :param event: Right-click event.
        :return: None
        """

        if self.table.underMouse():
            if self.table.selectionModel().selectedIndexes():
                selected_pems, rows = self.get_selected_pem_files()

                menu = QMenu(self.table)
                remove_file_action = QAction("&Remove", self)
                remove_file_action.triggered.connect(self.remove_file)
                remove_file_action.setIcon(QIcon(os.path.join(icons_path, 'remove.png')))

                open_file_action = QAction("&Open", self)
                open_file_action.triggered.connect(self.open_in_text_editor)
                open_file_action.setIcon(QIcon(os.path.join(icons_path, 'txt_file.png')))

                save_file_action = QAction("&Save", self)
                save_file_action.setIcon(QIcon(os.path.join(icons_path, 'save.png')))
                save_file_action.triggered.connect(lambda: self.save_pem_files(selected=True))

                export_pem_action = QAction("&Export...", self)
                export_pem_action.triggered.connect(lambda: self.export_pem_files(selected=True))

                save_file_as_action = QAction("&Save As...", self)
                save_file_as_action.triggered.connect(self.save_pem_file_as)

                save_as_xyz_action = QAction("&Save As XYZ...", self)
                save_as_xyz_action.triggered.connect(lambda: self.save_as_xyz(selected=True))

                print_plots_action = QAction("&Print Plots", self)
                print_plots_action.setIcon(QIcon(os.path.join(icons_path, 'pdf.png')))
                print_plots_action.triggered.connect(lambda: self.open_pdf_plot_printer(selected_files=True))

                extract_stations_action = QAction("&Extract Stations", self)
                extract_stations_action.triggered.connect(
                    lambda: self.station_splitter.open(selected_pems[0]))

                calc_mag_dec = QAction("&Magnetic Declination", self)
                calc_mag_dec.setIcon(QIcon(os.path.join(icons_path, 'mag_field.png')))
                calc_mag_dec.triggered.connect(lambda: self.open_mag_dec(selected_pems[0]))

                # self.table.view_3d_section_action = QAction("&View 3D Section", self)
                # self.table.view_3d_section_action.setIcon(QIcon(os.path.join(icons_path, 'section_3d.png')))
                # self.table.view_3d_section_action.triggered.connect(self.show_section_3d_viewer)

                open_plot_editor_action = QAction("&Plot", self)
                open_plot_editor_action.triggered.connect(self.open_pem_plot_editor)
                open_plot_editor_action.setIcon(QIcon(os.path.join(icons_path, 'plot_editor.png')))

                average_action = QAction("&Average", self)
                average_action.triggered.connect(lambda: self.average_pem_data(selected=True))
                average_action.setIcon(QIcon(os.path.join(icons_path, 'average.png')))

                split_action = QAction("&Split Channels", self)
                split_action.triggered.connect(lambda: self.split_pem_channels(selected=True))
                split_action.setIcon(QIcon(os.path.join(icons_path, 'split.png')))

                scale_current_action = QAction("&Scale Current", self)
                scale_current_action.triggered.connect(lambda: self.scale_pem_current(selected=True))
                scale_current_action.setIcon(QIcon(os.path.join(icons_path, 'current.png')))

                scale_ca_action = QAction("&Scale Coil Area", self)
                scale_ca_action.triggered.connect(lambda: self.scale_pem_coil_area(selected=True))
                scale_ca_action.setIcon(QIcon(os.path.join(icons_path, 'coil.png')))

                derotate_action = QAction("&De-rotate XY", self)
                derotate_action.triggered.connect(self.open_derotator)
                derotate_action.setIcon(QIcon(os.path.join(icons_path, 'derotate.png')))

                get_geometry_action = QAction("&Geometry", self)
                get_geometry_action.triggered.connect(self.open_pem_geometry)
                get_geometry_action.setIcon(QIcon(os.path.join(icons_path, 'pem_geometry.png')))

                share_loop_action = QAction("&Share Loop", self)
                share_loop_action.triggered.connect(self.share_loop)

                share_collar_action = QAction("&Share Collar", self)
                share_collar_action.triggered.connect(self.share_collar)

                share_segments_action = QAction("&Share Geometry", self)
                share_segments_action.triggered.connect(self.share_segments)

                share_station_gps_action = QAction("&Share Station GPS", self)
                share_station_gps_action.triggered.connect(self.share_station_gps)

                rename_lines_action = QAction("&Rename Lines/Holes", self)
                rename_lines_action.triggered.connect(lambda: self.open_batch_renamer(type='Line'))

                rename_files_action = QAction("&Rename Files", self)
                rename_files_action.triggered.connect(lambda: self.open_batch_renamer(type='File'))

                menu.addAction(open_file_action)
                menu.addAction(save_file_action)
                if len(self.table.selectionModel().selectedRows()) == 1:
                    menu.addAction(save_file_as_action)
                    menu.addAction(save_as_xyz_action)
                    menu.addAction(extract_stations_action)
                    menu.addAction(calc_mag_dec)
                else:
                    menu.addAction(save_as_xyz_action)
                    menu.addAction(export_pem_action)
                menu.addSeparator()
                menu.addAction(print_plots_action)
                menu.addSeparator()
                if len(self.table.selectionModel().selectedRows()) > 1:
                    menu.addAction(self.merge_action)
                menu.addAction(open_plot_editor_action)
                menu.addAction(average_action)
                menu.addAction(split_action)
                menu.addAction(scale_current_action)
                menu.addAction(scale_ca_action)
                menu.addSeparator()
                if all([f.is_borehole() for f in selected_pems]):
                    if len(self.table.selectionModel().selectedRows()) == 1:
                        menu.addAction(derotate_action)
                    menu.addAction(get_geometry_action)
                    menu.addSeparator()
                menu.addAction(share_loop_action)
                if all([f.is_borehole() for f in selected_pems]):
                    menu.addAction(share_collar_action)
                    menu.addAction(share_segments_action)
                else:
                    menu.addAction(share_station_gps_action)
                if len(self.table.selectionModel().selectedRows()) > 1:
                    menu.addSeparator()
                    menu.addAction(rename_lines_action)
                    menu.addAction(rename_files_action)
                menu.addSeparator()
                menu.addAction(remove_file_action)

                menu.popup(QtGui.QCursor.pos())

    def eventFilter(self, source, event):
        # Clear the selection when clicking away from any file
        if (event.type() == QtCore.QEvent.MouseButtonPress and
                source is self.table.viewport() and
                self.table.itemAt(event.pos()) is None):
            self.table.clearSelection()
        # Change the focus to the table so the 'Del' key works
        elif source == self.table and event.type() == QtCore.QEvent.FocusIn:
            self.actionDel_File.setEnabled(True)
        elif source == self.table and event.type() == QtCore.QEvent.FocusOut:
            self.actionDel_File.setEnabled(False)

        # Change the selected PIW widget when the arrow keys are pressed, and clear selection when Esc is pressed
        elif source == self.table and event.type() == QtCore.QEvent.KeyPress:
            if len(self.pem_files) > 0:
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
        elif source == self.table and event.type() == QtCore.QEvent.Wheel and event.modifiers() == QtCore.Qt.ShiftModifier:
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
        pem_files = False
        dmp_files = False
        text_files = False
        ri_files = False
        inf_files = False
        gpx_files = False

        # Files must all be the same extension
        if all([url.lower().endswith('pem') for url in urls]):
            pem_files = True
        elif all([url.lower().endswith('dmp') or url.lower().endswith('dmp2') for url in urls]):
            dmp_files = True
        elif all([url.lower().endswith('txt') or url.lower().endswith('csv') or url.lower().endswith(
                'seg') or url.lower().endswith('xyz') for url in
                  urls]):
            text_files = True
        elif all([url.lower().endswith('ri1') or url.lower().endswith('ri2') or url.lower().endswith(
                'ri3') for url in urls]):
            ri_files = True
        elif all([url.lower().endswith('inf') or url.lower().endswith('log') for url in urls]):
            inf_files = True
        elif all([url.lower().endswith('gpx') for url in urls]):
            gpx_files = True

        pem_conditions = bool(all([
            bool(e.answerRect().intersects(self.table.geometry())),
            bool(pem_files or dmp_files),
        ]))

        # When no PEM files are open, only open PEM files and not any other kind of file
        if not self.pem_files:
            if pem_conditions is True:
                e.acceptProposedAction()
            else:
                e.ignore()

        else:
            eligible_tabs = [self.stackedWidget.currentWidget().station_gps_tab,
                             self.stackedWidget.currentWidget().loop_gps_tab,
                             self.stackedWidget.currentWidget().geometry_tab]

            gps_conditions = bool(all([
                e.answerRect().intersects(self.piw_frame.geometry()),
                text_files is True or gpx_files is True,
                self.stackedWidget.currentWidget().tabs.currentWidget() in eligible_tabs,
                len(self.pem_files) > 0
            ]))

            ri_conditions = bool(all([
                e.answerRect().intersects(self.piw_frame.geometry()),
                ri_files is True,
                self.stackedWidget.currentWidget().tabs.currentWidget() == self.stackedWidget.currentWidget().ri_tab,
                len(self.pem_files) > 0
            ]))

            inf_conditions = bool(all([
                e.answerRect().intersects(self.project_crs_box.geometry()),
                inf_files is True or gpx_files is True,
            ]))

            if any([pem_conditions, gps_conditions, ri_conditions, inf_conditions]):
                e.acceptProposedAction()
            else:
                e.ignore()

    def dropEvent(self, e):
        urls = [url.toLocalFile() for url in e.mimeData().urls()]

        pem_files = [file for file in urls if file.lower().endswith('pem')]
        dmp_files = [file for file in urls if file.lower().endswith('dmp') or file.lower().endswith('dmp2')]
        gps_files = [file for file in urls if
                     file.lower().endswith('txt') or file.lower().endswith('csv') or file.lower().endswith(
                         'seg') or file.lower().endswith('xyz') or file.lower().endswith('gpx')]
        ri_files = [file for file in urls if
                    file.lower().endswith('ri1') or file.lower().endswith('ri2') or file.lower().endswith('ri3')]
        inf_files = [file for file in urls if file.lower().endswith('inf') or file.lower().endswith('log')]

        if pem_files:
            self.open_pem_files(pem_files)

        elif dmp_files:
            self.open_dmp_files(dmp_files)

        elif gps_files:
            self.open_gps_files(gps_files)

        elif ri_files:
            self.open_ri_file(ri_files)

        elif inf_files:
            self.open_inf_file(inf_files)

    def change_pem_info_tab(self, tab_num):
        """
        Slot: Change the tab for each pemInfoWidget to the same
        :param tab_num: tab index number to change to
        """
        self.tab_num = tab_num
        if len(self.pem_info_widgets) > 0:
            for widget in self.pem_info_widgets:
                widget.tabs.setCurrentIndex(self.tab_num)

    def block_signals(self, block_status):
        print(f'Blocking all signals {block_status}')
        for thing in [self.table, self.client_edit, self.grid_edit, self.loop_edit, self.min_range_edit,
                      self.max_range_edit]:
            thing.blockSignals(block_status)

    def start_pb(self, start=0, end=100, title=''):
        """
        Add the progress bar to the status bar and make it visible.
        :param start: Starting value of the progress bar, usually 0.
        :param end: Maximum value of the progress bar.
        :param title: Title of the progress bar window.
        """
        self.pb.setValue(start)
        self.pb.setMaximum(end)
        self.pb.setText('')
        self.pb_win.setWindowTitle(title)
        # self.status_bar.addPermanentWidget(self.pb)
        self.pb_win.show()
        QApplication.processEvents()

    def end_pb(self):
        """
        Reset the progress bar and hide its window
        """
        self.pb.setValue(0)
        self.pb.setMaximum(1)
        self.pb.setText('')
        self.pb_win.hide()

    def reset_crs(self):
        self.gps_system_cbox.setCurrentIndex(0)
        self.gps_zone_cbox.setCurrentIndex(0)
        self.gps_datum_cbox.setCurrentIndex(0)

    def remove_file(self, rows=None):
        """
        Removes PEM files from the main table, along with any associated widgets.
        :param rows: list: Table rows of the PEM files.
        :return: None
        """
        if not rows:
            pem_files, rows = self.get_selected_pem_files()

        if not isinstance(rows, list):
            rows = [rows]

        self.setUpdatesEnabled(False)
        for row in rows:
            self.table.removeRow(row)
            self.stackedWidget.removeWidget(self.stackedWidget.widget(row))
            del self.pem_files[row]
            del self.pem_info_widgets[row]

        if len(self.pem_files) == 0:
            # if not self.isMaximized():
            #     self.resize(self.width() - 425, self.height())
            self.piw_frame.hide()
            self.table.horizontalHeader().hide()
            self.client_edit.setText('')
            self.grid_edit.setText('')
            self.loop_edit.setText('')
            self.reset_crs()
            # self.project_dir = self.file_sys_model.rootPath()
        self.setUpdatesEnabled(True)

    def open_dmp_files(self, dmp_files):
        """
        Convert and open a .DMP or .DMP2 file
        :param dmp_files: list of str, filepaths of .DMP or .DMP2 files
        """
        if not isinstance(dmp_files, list):
            dmp_files = [dmp_files]

        parser = DMPParser()
        pem_files = []
        count = 0
        self.start_pb(start=count, end=len(dmp_files), title='Converting DMP Files...')

        for file in dmp_files:
            self.pb.setText(f"Converting {Path(file).name}")
            try:
                pem_file = parser.parse_dmp(file)
            except Exception as e:
                self.error.setWindowTitle('Error converting DMP file')
                self.error.showMessage(str(e))
                self.end_pb()
                return
            else:
                pem_files.append(pem_file)
                count += 1
                self.pb.setValue(count)

        self.end_pb()
        self.open_pem_files(pem_files)

    def open_pem_files(self, pem_files):
        """
        Action of opening a PEM file. Will not open a PEM file if it is already opened.
        :param pem_files: list, Filepaths for the PEM Files
        """
        def is_opened(path):
            if isinstance(path, PEMFile):
                path = path.filepath

            if self.pem_files:
                existing_filepaths = [file.filepath.absolute for file in self.pem_files]
                if path.absolute in existing_filepaths:
                    self.status_bar.showMessage(f"{path.name} is already opened", 2000)
                    return True
                else:
                    return False
            else:
                return False

        def add_info_widget(pem_file):
            """
            Create the PEMFileInfoWidget for the PEM file
            :param pem_file: PEMFile object
            :return: None
            """
            pem_info_widget = PEMFileInfoWidget()
            pem_info_widget.blockSignals(True)

            # Create the PEMInfoWidget for the PEM file
            pem_widget = pem_info_widget.open_file(pem_file, parent=self)
            # Change the current tab of this widget to the same as the opened ones
            pem_widget.tabs.setCurrentIndex(self.tab_num)
            # Connect a signal to change the tab when another PIW tab is changed
            pem_widget.tabs.currentChanged.connect(self.change_pem_info_tab)

            # Connect a signal to refresh the main table row when changes are made in the pem_info_widget tables.
            pem_info_widget.refresh_tables_signal.connect(lambda: self.refresh_rows(current_index=True))
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
            if crs and crs.is_valid():
                self.gps_system_cbox.setCurrentIndex(self.gps_systems.index(crs.system))
                if crs.system == 'UTM':
                    hemis = 'North' if crs.north is True else 'South'
                    self.gps_zone_cbox.setCurrentIndex(self.gps_zones.index(f"{crs.zone_number} {hemis}"))
                self.gps_datum_cbox.setCurrentIndex(self.gps_datums.index(crs.datum))

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

        if not isinstance(pem_files, list):
            pem_files = [pem_files]

        if not pem_files:
            return

        t1 = time.time()
        parser = PEMParser()
        self.setUpdatesEnabled(False)
        # self.table.setUpdatesEnabled(False)

        # Start the progress bar
        self.start_pb(start=0, end=len(pem_files), title='Opening PEM Files...')
        count = 0

        for pem_file in pem_files:
            # Create a PEMFile object if a filepath was passed
            if not isinstance(pem_file, PEMFile):
                try:
                    pem_file = parser.parse(pem_file)
                except Exception as e:
                    self.error.setWindowTitle('Error parsing PEM file')
                    self.error.showMessage(str(e))
                    self.end_pb()
                    return

            # Check if the file is already opened in the table. Won't open if it is.
            if is_opened(pem_file):
                self.status_bar.showMessage(f"{pem_file.filepath.name} is already opened", 2000)
            else:
                self.pb.setText(f"Opening {pem_file.filepath.name}")
                # Create the PEMInfoWidget
                pem_widget = add_info_widget(pem_file)

                # Fill the shared header text boxes and move the project directory
                if not self.pem_files:
                    share_header(pem_file)
                    self.piw_frame.show()
                    self.move_dir_tree_to(pem_file.filepath.parent)

                # Fill CRS from the file if project CRS currently empty
                if self.gps_system_cbox.currentText() == '' and self.gps_datum_cbox.currentText() == '':
                    fill_crs(pem_file)

                i = get_insertion_point(pem_file)
                self.pem_files.insert(i, pem_file)
                self.pem_info_widgets.insert(i, pem_widget)
                self.stackedWidget.insertWidget(i, pem_widget)
                self.table.insertRow(i)
                self.fill_pem_row(pem_file, i)

                # Progress the progress bar
                count += 1
                self.pb.setValue(count)

        self.setUpdatesEnabled(True)
        # self.table.setUpdatesEnabled(True)
        self.end_pb()
        self.table.horizontalHeader().show()
        print(f"PEMHub - Time to open all PEM files: {time.time() - t1}")

    def open_gps_files(self, gps_files):
        """
        Adds GPS information from the gps_files to the PEMFile object
        :param gps_files: list or str, filepaths of text file or GPX files
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
                if file.endswith('gpx'):
                    # Convert the GPX file to string
                    gps, zone, hemisphere = gpx_editor.get_utm(file, as_string=True)
                    merged_file.append(gps)
                else:
                    with open(file, mode='rt') as in_file:
                        contents = in_file.readlines()
                        merged_file.extend(contents)
            return merged_file

        file = merge_files(gps_files)
        pem_info_widget = self.stackedWidget.currentWidget()
        current_tab = pem_info_widget.tabs.currentWidget()
        crs = self.get_crs()

        if current_tab == pem_info_widget.station_gps_tab:
            line_adder = LineAdder(parent=self)
            line = SurveyLine(file, crs=crs)
            line_adder.write_widget = pem_info_widget
            line_adder.open(line)

        elif current_tab == pem_info_widget.geometry_tab:
            collar = BoreholeCollar(file, crs=crs)
            segments = BoreholeSegments(file)
            if not collar.df.empty:
                pem_info_widget.fill_gps_table(collar.df, pem_info_widget.collar_table)
            if not segments.df.empty:
                pem_info_widget.fill_gps_table(segments.df, pem_info_widget.segments_table)

        elif current_tab == pem_info_widget.loop_gps_tab:
            loop_adder = LoopAdder(parent=self)
            loop = TransmitterLoop(file, crs=crs)
            loop_adder.write_widget = pem_info_widget
            loop_adder.open(loop)

        else:
            pass

    def open_ri_file(self, ri_files):
        """
        Adds RI file information to the associated PEMFile object. Only accepts 1 file.
        :param ri_files: list, str filepaths with step plot information in them
        """
        ri_file = ri_files[0]
        pem_info_widget = self.stackedWidget.currentWidget()
        pem_info_widget.open_ri_file(ri_file)

    def open_inf_file(self, inf_files):
        """
        Parses a .INF file to extract the CRS information in ti and set the CRS drop-down values.
        :param inf_files: List of .INF files. Will only use the first file.
        :return: None
        """
        def get_crs(filepath):
            crs = {}
            with open(filepath, 'r') as in_file:
                file = in_file.read()

            crs['System'] = re.findall('Coordinate System:\W+(?P<System>.*)', file)[0]
            crs['Zone'] = re.findall('Coordinate Zone:\W+(?P<Zone>.*)', file)[0]
            crs['Datum'] = re.findall('Datum:\W+(?P<Datum>.*)', file)[0]
            return crs

        inf_file = inf_files[0]  # Filepath, only accept the first one
        crs = get_crs(inf_file)
        coord_sys = crs.get('System')
        coord_zone = crs.get('Zone')
        datum = crs.get('Datum')
        if 'NAD 1983' in datum:
            datum = 'NAD 1983'
        elif 'NAD 1927' in datum:
            datum = 'NAD 1927'
        self.gps_system_cbox.setCurrentIndex(self.gps_systems.index(coord_sys))
        self.gps_zone_cbox.setCurrentIndex(self.gps_zones.index(coord_zone))
        self.gps_datum_cbox.setCurrentIndex(self.gps_datums.index(datum))

    def open_in_text_editor(self):
        """
        Open the selected PEM File in a text editor
        """
        pem_files, rows = self.get_selected_pem_files()
        self.text_browsers = []
        for pem_file in pem_files:
            pem_str = pem_file.to_string()
            browser = QTextBrowser()
            self.text_browsers.append(browser)
            browser.setText(pem_str)
            browser.resize(600, 800)
            browser.setWindowIcon(QIcon(os.path.join(icons_path, 'txt_file.png')))
            browser.setWindowTitle('Text View')
            browser.show()
            # os.startfile(pem_file.filepath)

    def open_file_dialog(self):
        """
        Open files through the file dialog
        """
        files = self.dialog.getOpenFileNames(self, 'Open File', filter='PEM files (*.pem);; All files(*.*)')
        if files[0] != '':
            for file in files[0]:
                if file.lower().endswith('.pem'):
                    self.open_files(file)

    def open_pem_plot_editor(self):
        """
        Open the PEMPlotEditor for each PEMFile selected
        """

        def save_editor_pem(pem_file):
            """
            Re-open the PEM file
            :param pem_file: PEMFile object emitted by the signal
            """
            self.refresh_pem(pem_file)

        def close_editor(editor):
            """
            Remove the editor from the list of pem_editors
            :param editor: PEMPlotEditor object emitted by the signal
            """
            self.pem_editor_widgets.remove(editor)

        pem_files, rows = self.get_selected_pem_files(updated=True)
        for pem_file in pem_files:
            editor = PEMPlotEditor(parent=self)
            self.pem_editor_widgets.append(editor)
            # Connect the 'save' and 'close' signals
            editor.save_sig.connect(save_editor_pem)
            editor.close_sig.connect(close_editor)
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

        pem_files, rows = self.get_selected_pem_files(updated=True)
        assert len(pem_files) == 1, 'Can only de-rotate one file at a time.'

        pem_file, row = pem_files[0], rows[0]
        derotator = Derotator(parent=self)
        derotator.accept_sig.connect(accept_file)
        derotator.open(pem_file)

    def open_pem_geometry(self):
        """
        Open the PEMGeometry window
        """

        def accept_geometry(seg):
            for file in pem_files:
                file.geometry.segments = seg
                self.refresh_pem(file)
            self.status_bar.showMessage(f"Geometry updated for {', '.join([file.filepath.name for file in pem_files])}."
                                        , 2000)

        pem_files, rows = self.get_selected_pem_files(updated=False)

        pem_geometry = PEMGeometry(parent=self)
        pem_geometry.accepted_sig.connect(accept_geometry)
        pem_geometry.open(pem_files)

    def open_pdf_plot_printer(self, selected_files=False):
        """
        Open an instance of PDFPlotPrinter, which has all the options for printing plots.
        :param selected_files: bool, False will pass all opened PEM files, True will only pass selected PEM files
        """

        if not self.pem_files:
            return

        if selected_files is True:
            pem_files, rows = self.get_selected_pem_files(updated=True)
        else:
            pem_files, rows = self.get_updated_pem_files(), range(0, len(self.pem_files))

        # Gather the RI files
        ri_files = []
        for row, pem_file in zip(rows, pem_files):
            ri_files.append(self.pem_info_widgets[row].ri_file)

        pdf_plot_printer = PDFPlotPrinter(parent=self)
        pdf_plot_printer.open(pem_files, ri_files=ri_files, crs=self.get_crs())

    def open_mag_dec(self, pem_file):
        """
        Opens the MagDeclinationCalculator widget to calculate the magnetic declination of the selected file.
        :param pem_file: PEMFile object
        """
        crs = self.get_crs()
        if crs.is_nad27():
            self.message.information(self, 'Error', 'Incompatible datum. Must be either NAD 1983 or WGS 1984')
            return
        if not crs.is_valid():
            self.message.information(self, 'Error', 'GPS coordinate system information is incomplete')
            return

        m = MagDeclinationCalculator(parent=self)
        m.calc_mag_dec(pem_file, self.get_crs())
        m.show()

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

    def open_batch_renamer(self, type):
        """
        Opens the BatchNameEditor for renaming multiple file names and/or line/hole names.
        :param type: str, either 'Line' to change the line names or 'File' to change file names
        :return: None
        """

        def rename_pem_files():
            """
            Retrieve and open the PEM files from the batch_name_editor object
            :return: None
            """
            if len(batch_name_editor.pem_files) > 0:
                batch_name_editor.accept_changes()
                for i, row in enumerate(rows):
                    self.pem_files[row] = batch_name_editor.pem_files[i]
                self.refresh_rows(rows=rows)

        pem_files, rows = self.get_selected_pem_files()
        if not pem_files:
            pem_files, rows = self.pem_files, np.arange(self.table.rowCount())

        batch_name_editor = BatchNameEditor(parent=self)
        batch_name_editor.open(pem_files, type=type)
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
                self.status_bar.showMessage(f"Imported {str(len(ri_filepaths))} RI files", 2000)
            else:
                pass

        ri_importer = BatchRIImporter(parent=self)
        ri_importer.open_pem_files(self.pem_files)
        ri_importer.acceptImportSignal.connect(open_ri_files)
        ri_importer.show()

    # def get_project_path(self):
    #     """
    #     Return the path of the selected directory tree item.
    #     :return: str: filepath
    #     """
    #     index = self.project_tree.currentIndex()
    #     index_item = self.file_sys_model.index(index.row(), 0, index.parent())
    #     path = self.file_sys_model.filePath(index_item)
    #     return path

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
            print(f"New project dir: {str(path)}")
            self.project_dir_label.setText(f"Project directory: {str(path)}")

            # self.fill_gps_list()
            # self.fill_pem_list()

    def fill_gps_list(self):
        """
        Populate the GPS files list based on the files found in the nearest 'GPS' folder in the project directory
        """

        @stopit.threading_timeoutable()
        def find_gps_dir():
            # Try to find the 'GPS' folder in the current directory
            search_result = list(self.project_dir.rglob('GPS'))
            if search_result:
                gps_dir = search_result[0]
                print(f"GPS dir found: {str(gps_dir)}")
                return gps_dir

        if not self.project_dir:
            self.message.information(self, 'Error', 'No project directory has been selected.')
            return

        self.gps_list.clear()
        # Try to find a GPS folder, but time out after 3 seconds
        gps_dir = find_gps_dir(timeout=3)

        if gps_dir is None:
            self.message.information(self, 'Timeout', 'Searching for the GPS folder timed out.')
            return
        else:
            if gps_dir:
                self.available_gps = list(gps_dir.rglob('*.txt'))
                self.available_gps.extend(gps_dir.rglob('*.csv'))
                self.available_gps.extend(gps_dir.rglob('*.gpx'))

                for file in self.available_gps:
                    self.gps_list.addItem(f"{file.parent.name}/{file.name}")

    def fill_pem_list(self):
        """
        Populate the pem_list with all *.pem files found in the project_dir.
        """

        @stopit.threading_timeoutable()
        def find_pem_files():
            # Find all .PEM files in the project directory
            return list(self.project_dir.rglob('*.PEM'))

        if not self.project_dir:
            self.message.information(self, 'Error', 'No project directory has been selected.')
            return

        self.pem_list.clear()

        # Try to find .PEM files, but time out after 3 seconds
        self.available_pems = find_pem_files(timeout=3)

        if self.available_pems is None:
            self.message.information(self, 'Timeout', 'Searching for PEM files timed out.')
            return
        else:
            for file in self.available_pems:
                self.pem_list.addItem(f"{file.parent.name}/{file.name}")

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

    def save_pem_file(self, pem_file, dir=None, tag=None, backup=False, remove_old=False):
        """
        Action of saving a PEM file to a .PEM file.
        :param pem_file: PEMFile object to be saved.
        :param dir: str, save file path. If None, uses the parent of the first PEM file as the default.
        :param tag: str: Tag to append to the file name ('[A]', '[S]', '[M]'...)
        :param backup: Bool: If true, will save file to a '[Backup]' folder.
        :param remove_old: Bool: If true, will delete the old file.
        :return: None
        """
        if dir is None:
            file_dir = pem_file.filepath.parent
        else:
            file_dir = dir
        file_name = pem_file.filepath.stem
        extension = pem_file.filepath.suffix

        # Create a backup folder if it doesn't exist, and use it as the new file dir.
        if backup is True:
            pem_file.old_filepath = Path(os.path.join(file_dir, file_name + extension))
            if not os.path.exists(os.path.join(file_dir, '[Backup]')):
                print('Creating back up folder')
                os.mkdir(os.path.join(file_dir, '[Backup]'))
            file_dir = os.path.join(file_dir, '[Backup]')
            extension += '.bak'

        if tag and tag not in file_name:
            file_name += tag

        pem_file.filepath = Path(os.path.join(file_dir, file_name + extension))
        pem_file.save()
        # pem_text = pem_file.to_string()
        # print(pem_text, file=open(str(pem_file.filepath), 'w+'))

        # Remove the old filepath if the filename was changed.
        if pem_file.old_filepath and remove_old is True:
            print(f'Removing old file {pem_file.old_filepath.name}')
            if pem_file.old_filepath.is_file():
                pem_file.old_filepath.unlink()
                pem_file.old_filepath = None

    def save_pem_files(self, selected=False):
        """
        Save all selected PEM files.
        :param selected: Bool: if True, saves all opened PEM files instead of only the selected ones.
        :return: None
        """
        pem_files = self.get_updated_pem_files(selected=selected)
        self.start_pb(0, len(pem_files), title='Saving PEM Files...')

        count = 0
        for pem_file in pem_files:
            self.pb.setText(f"Saving {pem_file.filepath.name}")
            self.save_pem_file(pem_file)
            self.refresh_pem(pem_file)
            # Block the signals because it only updates the row corresponding to the current stackedWidget.
            # self.pem_info_widgets[row].blockSignals(True)
            # self.pem_info_widgets[row].open_file(pem_file, parent=self)  # Updates the PEMInfoWidget tables
            # self.pem_info_widgets[row].blockSignals(False)
            count += 1
            self.pb.setValue(count)

        self.end_pb()
        self.status_bar.showMessage(f'Save Complete. {len(pem_files)} file(s) saved.', 2000)

    def save_pem_file_as(self):
        """
        Saves a single PEM file to a selected location.
        :return: None
        """
        row = self.table.currentRow()
        default_path = os.path.split(self.pem_files[-1].filepath)[0]
        # self.dialog.setFileMode(QFileDialog.ExistingFiles)
        # self.dialog.setAcceptMode(QFileDialog.AcceptSave)
        # self.dialog.setDirectory(default_path)
        self.status_bar.showMessage('Saving PEM files...')

        file_path = QFileDialog.getSaveFileName(self, '', default_path, 'PEM Files (*.PEM)')[0]  # Returns full filepath

        if file_path:
            pem_file = copy.deepcopy(self.pem_files[row])
            pem_file.filepath = Path(file_path)
            updated_file = self.update_pem_from_table(pem_file, row, filepath=file_path)

            self.save_pem_file(updated_file)
            self.status_bar.showMessage(f'Save Complete. PEM file saved as {file_path.name}', 2000)
            # Must open and not update the PEM since it is being copied
            self.open_pem_files(updated_file)
        else:
            self.status_bar.showMessage('Cancelled.', 2000)

    def save_as_kmz(self):
        """
        Saves all GPS from the opened PEM files as a KMZ file. Utilizes 'simplekml' module. Only works with NAD 83
        or WGS 84.
        :return: None
        """
        crs = self.get_crs()

        if not self.pem_files:
            return

        if not any([pem_file.has_any_gps() for pem_file in self.pem_files]):
            self.message.information(self, 'Missing GPS', 'A file is missing required GPS')
            return

        if crs.is_nad27():
            self.message.information(self, 'Invalid Datum', 'Incompatible datum. Must be either NAD 1983 or WGS 1984')
            return

        if not crs.is_valid():
            self.message.information(self, 'Incomplete CRS', 'GPS coordinate system information is incomplete')
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
        loop_names = []
        lines = []
        line_names = []
        traces = []
        hole_names = []

        # Grouping up the loops, lines and boreholes into lists.
        for pem_file in pem_files:
            loop_gps = pem_file.loop.get_loop(closed=True, crs=crs)
            loop_gps.append(loop_gps)
            loop_name = pem_file.loop_name
            if not loop_gps.empty and loop_gps not in loops:
                loops.append(loop_gps)
                loop_names.append(loop_name)
            if not pem_file.is_borehole():
                line_gps = pem_file.line.get_line(crs=crs)
                line_name = pem_file.line_name
                if not line_gps.empty and line_gps not in lines:
                    lines.append(line_gps)
                    line_names.append(line_name)
            else:
                bh_projection = pem_file.geometry.get_projection(num_segments=100)
                hole_name = pem_file.line_name
                if not bh_projection.empty and bh_projection not in traces:
                    traces.append(bh_projection)
                    hole_names.append(hole_name)

        # Creates KMZ objects for the loops.
        for loop_gps, name in zip(loops, loop_names):
            ls = kml.newlinestring(name=name)
            ls.coords = loop_gps.loc[:, ['Longitude', 'Latitude']].to_numpy()
            ls.extrude = 1
            ls.style = loop_style

        # Creates KMZ objects for the lines.
        for line_gps, name in zip(lines, line_names):
            folder = kml.newfolder(name=name)
            new_point = line_gps.apply(
                lambda x: folder.newpoint(name=str(x.Station), coords=[(x.Longitude, x.Latitude)]), axis=1)
            new_point.style = station_style

            ls = folder.newlinestring(name=name)
            ls.coords = line_gps.loc[:, ['Longitude', 'Latitude']].to_numpy()
            ls.extrude = 1
            ls.style = trace_style

        # Creates KMZ objects for the boreholes.
        for trace_gps, name in zip(traces, hole_names):
            folder = kml.newfolder(name=name)
            collar = folder.newpoint(name=name, coords=[trace_gps.loc[0, ['Longitude', 'Latitude']].to_numpy()])
            collar.style = collar_style
            ls = folder.newlinestring(name=name)
            ls.coords = trace_gps.loc[:, ['Longitude', 'Latitude']].to_numpy()
            ls.extrude = 1
            ls.style = trace_style

        default_path = os.path.split(self.pem_files[-1].filepath)[0]
        self.dialog.setDirectory(default_path)
        save_dir = self.dialog.getSaveFileName(self, 'Save KMZ File', default_path, 'KMZ Files (*.KMZ)')[0]
        if save_dir:
            kmz_save_dir = os.path.splitext(save_dir)[0] + '.kmz'
            kml.savekmz(kmz_save_dir, format=False)
            os.startfile(kmz_save_dir)
        else:
            self.status_bar.showMessage('Cancelled.', 2000)

    def save_as_xyz(self, selected=False):
        """
        Save the selected PEM files as XYZ files. Only for surface PEM files.
        :param selected: bool: Save selected files. False means all opened files will be saved.
        :return: None
        """

        if selected:
            pem_files, rows = self.get_selected_pem_files()
        else:
            pem_files, rows = self.pem_files, np.arange(self.table.rowCount())

        if not pem_files:
            return

        default_path = os.path.split(self.pem_files[-1].filepath)[0]
        file_dir = self.dialog.getExistingDirectory(self, '', default_path, QFileDialog.DontUseNativeDialog)

        if file_dir:
            for pem_file in pem_files:
                if not pem_file.is_borehole():
                    file_name = os.path.splitext(pem_file.filepath)[0] + '.xyz'
                    xyz_file = pem_file.to_xyz()
                    with open(file_name, 'w+') as file:
                        file.write(xyz_file)
                    os.startfile(file_name)

    def export_pem_files(self, selected=False, export_final=False):
        """
        Saves all PEM files to a desired location (keeps them opened) and removes any tags.
        :param selected: bool, True will only export selected rows.
        :param export_final: bool, True will perform a final file export where the file names are modified automatically.
        :return: None
        """
        crs = self.get_crs()
        if selected is True:
            pem_files, rows = self.get_selected_pem_files()
        else:
            pem_files, rows = self.pem_files, np.arange(self.table.rowCount())

        self.status_bar.showMessage(f"Saving PEM {'file' if len(pem_files) == 1 else 'files'}...")
        if not crs.is_valid():
            response = self.message.question(self, 'Invalid CRS',
                                             'The CRS information is invalid.'
                                             'Do you wish to proceed with no CRS information?',
                                             self.message.Yes | self.message.No)
            if response == self.message.No:
                return

        default_path = os.path.split(self.pem_files[-1].filepath)[0]
        self.dialog.setDirectory(default_path)
        file_dir = self.dialog.getExistingDirectory(self, '', default_path, QFileDialog.DontUseNativeDialog)

        if file_dir:
            for pem_file, row in zip(pem_files, rows):
                updated_file = self.update_pem_from_table(pem_file, row)
                file_name = os.path.splitext(os.path.basename(pem_file.filepath))[0]
                extension = os.path.splitext(pem_file.filepath)[-1]
                if export_final is True:
                    # Make sure the file is averaged and split
                    if not pem_file.is_split():
                        pem_file = pem_file.split()
                    if not pem_file.is_averaged():
                        pem_file = pem_file.average()
                    # Remove underscore-dates and tags
                    file_name = re.sub('_\d+', '', re.sub('\[-?\w\]', '', file_name))
                    if not pem_file.is_borehole():
                        file_name = file_name.upper()
                        if file_name.lower()[0] == 'c':
                            file_name = file_name[1:]
                        if pem_file.is_averaged() and 'av' not in file_name.lower():
                            file_name = file_name + 'Av'

                updated_file.filepath = Path(os.path.join(file_dir, file_name + extension))
                self.save_pem_file(updated_file, dir=file_dir, remove_old=False)
            self.refresh_rows(rows='all')
            self.status_bar.showMessage(
                f"Save complete. {len(pem_files)} PEM {'file' if len(pem_files) == 1 else 'files'} exported", 2000)
        else:
            self.status_bar.showMessage('Cancelled.', 2000)
            pass

    def export_all_gps(self):
        """
        Exports all GPS from all opened PEM files to separate CSV files. Creates folders for each loop.
        Doesn't repeat if a line/hole/loop has been done already.
        :return: None
        """
        if self.pem_files:
            crs = self.get_crs()

            if not crs.is_valid():
                self.message.information(self, 'Invalid CRS', 'CRS is incomplete and/or invalid.')
                return

            system = crs.system
            # zone = ' Zone ' + self.gps_zone_cbox.currentText() if self.gps_zone_cbox.isEnabled() else ''
            zone = ' Zone ' + crs.zone if self.gps_zone_cbox.isEnabled() else ''
            datum = crs.datum

            loops = []
            lines = []
            collars = []

            default_path = os.path.dirname(self.pem_files[0].filepath)
            export_folder = self.dialog.getExistingDirectory(
                self, 'Select Destination Folder', default_path, QFileDialog.DontUseNativeDialog)
            if export_folder != '':
                for loop, pem_files in groupby(self.pem_files, key=lambda x: x.loop_name):
                    pem_files = list(pem_files)
                    try:
                        # Creates a new folder for each loop, where each CSV will be saved for that loop.
                        os.mkdir(os.path.join(export_folder, loop))
                    except FileExistsError:
                        pass
                    folder = os.path.join(export_folder, loop)
                    for pem_file in pem_files:
                        if pem_file.has_loop_gps():
                            loop = pem_file.get_loop(closed=False)
                            if loop.to_string() not in loops:
                                loop_name = pem_file.loop_name
                                print(f"Creating CSV file for loop {loop_name}")
                                loops.append(loop.to_string())
                                csv_filepath = os.path.join(folder, loop_name + '.csv')
                                with open(csv_filepath, 'w') as csvfile:
                                    filewriter = csv.writer(csvfile,
                                                            delimiter=',',
                                                            lineterminator='\n',
                                                            quotechar='"',
                                                            quoting=csv.QUOTE_MINIMAL)
                                    filewriter.writerow([f"Loop {loop_name} - {system} {zone} {datum}"])
                                    filewriter.writerow(['Easting', 'Northing', 'Elevation'])
                                    loop.apply(lambda x: filewriter.writerow([x.Easting, x.Northing, x.Elevation]),
                                               axis=1)

                        if pem_file.has_station_gps():
                            line = pem_file.line.get_line()
                            if line.to_string() not in lines:
                                line_name = pem_file.line_name
                                print(f"Creating CSV file for line {line_name}")
                                lines.append(line.to_string())
                                csv_filepath = os.path.join(folder, f"{line_name}.csv")
                                with open(csv_filepath, 'w') as csvfile:
                                    filewriter = csv.writer(csvfile,
                                                            delimiter=',',
                                                            lineterminator='\n',
                                                            quotechar='"',
                                                            quoting=csv.QUOTE_MINIMAL)
                                    filewriter.writerow([f"Line {line_name} - {system} {zone} {datum}"])
                                    filewriter.writerow(['Easting', 'Northing', 'Elevation', 'Station Number'])
                                    line.apply(
                                        lambda x: filewriter.writerow([x.Easting, x.Northing, x.Elevation, x.Station]),
                                        axis=1)

                        if pem_file.has_collar_gps():
                            collar = pem_file.geometry.get_collar()
                            if collar.to_string() not in collars:
                                hole_name = pem_file.line_name
                                print(f"Creating CSV file for hole {hole_name}")
                                collars.append(collar.to_string())
                                csv_filepath = os.path.join(folder, hole_name + '.csv')
                                with open(csv_filepath, 'w') as csvfile:
                                    filewriter = csv.writer(csvfile,
                                                            delimiter=',',
                                                            lineterminator='\n',
                                                            quotechar='"',
                                                            quoting=csv.QUOTE_MINIMAL)
                                    filewriter.writerow([f"Hole {hole_name} - {system} {zone} {datum}"])
                                    filewriter.writerow(['Easting', 'Northing', 'Elevation'])
                                    collar.apply(lambda x: filewriter.writerow([x.Easting, x.Northing, x.Elevation]),
                                                 axis=1)
                self.status_bar.showMessage("Export complete.", 2000)
            else:
                self.status_bar.showMessage("No files to export.", 2000)

    def fill_pem_row(self, pem_file, row):
        """
        Adds the information from a PEM file to the main table. Blocks the table signals while doing so.
        :param pem_file: PEMFile object
        :param row: int, row of the PEM file in the table
        :return: None
        """

        def color_table_row_text(row):
            """
            Color cells of the main table based on conditions. Ex: Red text if the PEM file isn't averaged.
            :param row: Row of the main table to check and color
            :return: None
            """

            def color_row(rowIndex, color, alpha=50):
                """
                Color an entire table row
                :param rowIndex: Int: Row of the table to color
                :param color: str: The desired color
                :return: None
                """
                self.table.blockSignals(True)
                color = QtGui.QColor(color)
                color.setAlpha(alpha)
                for j in range(self.table.columnCount()):
                    self.table.item(rowIndex, j).setBackground(color)
                if self.allow_signals:
                    self.table.blockSignals(False)

            self.table.blockSignals(True)
            average_col = self.table_columns.index('Averaged')
            split_col = self.table_columns.index('Split')
            suffix_col = self.table_columns.index('Suffix\nWarnings')
            repeat_col = self.table_columns.index('Repeat\nStations')
            pem_has_gps = self.pem_files[row].has_all_gps()

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
                color_row(row, 'magenta')

            if self.allow_signals:
                self.table.blockSignals(False)

        print(f"Filling {pem_file.filepath.name}'s information to the table")
        self.table.blockSignals(True)

        info_widget = self.pem_info_widgets[row]

        # Get the information for each column
        row_info = [
            pem_file.filepath.name,
            pem_file.date,
            self.client_edit.text() if self.share_client_cbox.isChecked() else pem_file.client,
            self.grid_edit.text() if self.share_grid_cbox.isChecked() else pem_file.grid,
            pem_file.line_name,
            self.loop_edit.text() if self.share_loop_cbox.isChecked() else pem_file.loop_name,
            pem_file.current,
            pem_file.coil_area,
            pem_file.get_stations(converted=True).min(),
            pem_file.get_stations(converted=True).max(),
            pem_file.is_averaged(),
            pem_file.is_split(),
            str(info_widget.suffix_warnings),
            str(info_widget.num_repeat_stations)
        ]

        # Set the information into each cell. Columns from First Station and on can't be edited.
        for i, info in enumerate(row_info):
            item = QTableWidgetItem(str(info))
            item.setTextAlignment(QtCore.Qt.AlignCenter)
            # Disable editing of columns past First Station
            if i > self.table_columns.index('Coil\nArea'):
                item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
            self.table.setItem(row, i, item)

        color_table_row_text(row)
        self.check_for_table_changes(pem_file, row)
        self.check_for_table_anomalies()
        if self.allow_signals:
            self.table.blockSignals(False)

    def table_value_changed(self, row, col):
        """
        Signal Slot: Action taken when a value in the main table was changed. Example: Changing the coil area of the data if the
        coil area cell is changed, or changing the filepath of a PEM file when the file name cell is changed.
        :param row: Row of the main table that the change was made.
        :param col: Column of the main table that the change was made.
        :return: None
        """
        print(f'Table value changed at row {row} and column {col}')

        self.table.blockSignals(True)
        pem_file = self.pem_files[row]

        if col == self.table_columns.index('Coil\nArea') + 1:
            pem_file = self.pem_files[row]
            old_value = pem_file.coil_area
            try:
                new_value = int(self.table.item(row, col).text())
            except ValueError:
                self.message.information(self, 'Invalid coil area', 'Coil area must be an integer number.')
                print("Value is not an integer.")
                pass
            else:
                if int(old_value) != int(new_value):
                    pem_file = pem_file.scale_coil_area(new_value)
                    self.status_bar.showMessage(
                        f"Coil area changed from {old_value} to {new_value}", 2000)

        # Changing the name of a file
        if col == self.table_columns.index('File'):
            pem_file = self.pem_files[row]
            old_path = copy.deepcopy(pem_file.filepath)
            new_value = self.table.item(row, col).text()

            if new_value != os.path.basename(pem_file.filepath) and new_value:
                pem_file.old_filepath = old_path
                new_path = Path(os.path.join(old_path.parent, new_value))
                print(f"Renaming {old_path.name} to {new_path.name}")

                # Create a copy and delete the old one.
                copyfile(old_path, new_path)
                pem_file.filepath = new_path
                os.remove(old_path)

                self.status_bar.showMessage(f"File renamed to {str(new_value)}", 2000)

        # self.color_table_row_text(row)
        self.check_for_table_changes(pem_file, row)
        self.check_for_table_anomalies()
        if self.allow_signals:
            self.table.blockSignals(False)

    def check_for_table_anomalies(self):
        """
        Change the text color of table cells where the value warrants attention. An example of this is where the
        date might be wrong.
        :return: None
        """
        self.table.blockSignals(True)
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
        if self.allow_signals:
            self.table.blockSignals(False)

    def check_for_table_changes(self, pem_file, row):
        """
        Bolden table cells where the value in the cell is different then what is the PEM file memory.
        :param pem_file: PEMFile object
        :param row: Corresponding table row of the PEM file.
        :return: None
        """
        self.table.blockSignals(True)
        boldFont, normalFont = QtGui.QFont(), QtGui.QFont()
        boldFont.setBold(True)
        normalFont.setBold(False)

        info_widget = self.pem_info_widgets[self.pem_files.index(pem_file)]

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
            str(info_widget.suffix_warnings),
            str(info_widget.num_repeat_stations)
        ]

        for column in range(self.table.columnCount()):
            if self.table.item(row, column):
                original_value = str(row_info[column])
                if self.table.item(row, column).text() != original_value:
                    self.table.item(row, column).setFont(boldFont)
                else:
                    self.table.item(row, column).setFont(normalFont)

        if self.allow_signals:
            self.table.blockSignals(False)

    def refresh_pem(self, pem_file):
        """
        Refresh the PEM file by re-opening its PIW and refreshing the information in its row in PEMHub.
        File must be in the list of PEM Files opened in PEMHUb (cannot be a copy).
        :param pem_file: PEMFile object
        """
        if pem_file in self.pem_files:
            ind = self.pem_files.index(pem_file)
            self.pem_info_widgets[ind].open_file(pem_file, parent=self)
            self.refresh_rows([ind])

    def refresh_rows(self, rows=None, current_index=False):
        """
        Clear the row and fill in the PEM file's information
        :param rows: Corresponding row of the PEM file in the main table
        :param current_index: bool, whether to refresh the row corresponding to the currently opened PEMInfoWidget
        :return: None
        """
        if current_index:
            rows = [self.stackedWidget.currentIndex()]
        else:
            if isinstance(rows, str):
                if rows == 'all':
                    rows = np.arange(self.table.rowCount())
            elif not isinstance(rows, list) and not isinstance(rows, np.ndarray):
                rows = [rows]

        for row in rows:
            self.table.blockSignals(True)
            pem_file = self.pem_files[row]
            # Reset the row
            for i, column in enumerate(self.table_columns):
                item = QTableWidgetItem('')
                item.setTextAlignment(QtCore.Qt.AlignCenter)
                self.table.setItem(row, i, item)
            self.fill_pem_row(pem_file, row)
        if self.allow_signals:
            self.table.blockSignals(False)

    def update_pem_from_table(self, pem_file, table_row, filepath=None):
        """
        Saves the pem file in memory using the information in the table.
        :param pem_file: PEM file object to save.
        :param table_row: Corresponding row of the PEM file in the main table.
        :param filepath: New filepath to be given to the PEM file. If None is given, it will use the filename in the
        table.
        :return: the PEM File object with updated information
        """

        def add_crs_tag():
            """
            Add the CRS from the table as a note to the PEM file.
            :return: None
            """
            system = self.gps_system_cbox.currentText()
            zone = ' Zone ' + self.gps_zone_cbox.currentText() if self.gps_zone_cbox.isEnabled() else ''
            datum = self.gps_datum_cbox.currentText()

            if any([system, zone, datum]):
                for note in reversed(pem_file.notes):
                    if '<GEN> CRS' in note:
                        del pem_file.notes[pem_file.notes.index(note)]

                pem_file.notes.append(f"<GEN> CRS: {system}{zone}, {datum}")

        if filepath is None:
            pem_file.filepath = Path(os.path.join(pem_file.filepath.parent,
                                                  self.table.item(table_row, self.table_columns.index('File')).text()))
        else:
            if not isinstance(filepath, Path):
                filepath = Path(filepath)
            pem_file.filepath = filepath

        add_crs_tag()
        pem_file.date = self.table.item(table_row, self.table_columns.index('Date')).text()
        pem_file.client = self.table.item(table_row, self.table_columns.index('Client')).text()
        pem_file.grid = self.table.item(table_row, self.table_columns.index('Grid')).text()
        pem_file.line_name = self.table.item(table_row, self.table_columns.index('Line/Hole')).text()
        pem_file.loop_name = self.table.item(table_row, self.table_columns.index('Loop')).text()
        pem_file.current = float(self.table.item(table_row, self.table_columns.index('Current')).text())

        crs = self.get_crs()
        pem_file.loop = self.stackedWidget.widget(table_row).get_loop()
        pem_file.loop.crs = crs
        if pem_file.is_borehole():
            pem_file.geometry = self.stackedWidget.widget(table_row).get_geometry()
            pem_file.geometry.collar.crs = crs
        else:
            pem_file.line = self.stackedWidget.widget(table_row).get_line()
            pem_file.line.crs = crs

        return pem_file

    def backup_files(self):
        """
        Create a backup (.bak) file for each opened PEM file, saved in a backup folder.
        :return: None
        """
        for pem_file in self.pem_files:
            print(f"Backing up {pem_file.filepath.name}")
            pem_file = copy.deepcopy(pem_file)
            self.save_pem_file(pem_file, backup=True, tag='[B]', remove_old=False)
        self.status_bar.showMessage(f'Backup complete. Backed up {len(self.pem_files)} PEM files.', 2000)

    def get_selected_pem_files(self, updated=False):
        """
        Return the corresponding pem_files and rows which are currently selected in the table
        :return: pem_file objects and corresponding row indexes
        """
        selected_pem_files = []
        rows = [model.row() for model in self.table.selectionModel().selectedRows()]
        rows.sort(reverse=True)
        for row in rows:
            selected_pem_files.append(self.pem_files[row])

        if updated is True:
            selected_pem_files = [self.update_pem_from_table(f, r) for f, r in zip(selected_pem_files, rows)]

        return selected_pem_files, rows

    def get_updated_pem_files(self, selected=False):
        """
        Return the updated version of the opened PEM files
        :return: list, updated PEM files
        """
        if selected is True:
            updated_files = self.get_selected_pem_files(updated=True)
        else:
            files, rows = self.pem_files, np.arange(self.table.rowCount())
            updated_files = [self.update_pem_from_table(copy.deepcopy(file), row) for file, row in zip(files, rows)]
        return updated_files

    def get_crs(self):
        """
        Return a CRS object based on the CRS information in the PEM Editor window
        :return: CRS object
        """
        system = self.gps_system_cbox.currentText()
        zone = self.gps_zone_cbox.currentText()
        datum = self.gps_datum_cbox.currentText()

        crs_dict = {'System': system, 'Zone': zone, 'Datum': datum}
        crs = CRS().from_dict(crs_dict)
        return crs

    def average_pem_data(self, selected=False):
        """
        Average the data of each PEM File selected
        :param selected: bool, True will only export selected rows.
        """
        if selected is True:
            pem_files, rows = self.get_selected_pem_files()
        else:
            pem_files, rows = self.pem_files, np.arange(self.table.rowCount())

        if not pem_files:
            return

        # Zip the pem_files and rows so they can be filtered together
        l = zip(pem_files, rows)
        # Filter the pem_files to only keep un-averaged files
        filt_list = list(filter(lambda x: not x[0].is_averaged(), l))

        if len(filt_list) == 0:
            return

        self.start_pb(start=0, end=len(filt_list), title='Averaging PEM Files...')
        count = 0
        for pem_file, row in filt_list:
            print(f"Averaging {pem_file.filepath.name}")
            self.pb.setText(f"Averaging {pem_file.filepath.name}")
            # Save a backup of the un-averaged file first
            if self.auto_create_backup_files_cbox.isChecked():
                self.save_pem_file(copy.deepcopy(pem_file), backup=True, tag='[-A]', remove_old=False)
            pem_file = pem_file.average()
            self.refresh_pem(pem_file)
            count += 1
            self.pb.setValue(count)
        self.end_pb()

    def split_pem_channels(self, selected=False):
        """
        Removes the on-time channels of each selected PEM File
        :param selected: bool, True will only export selected rows.
        """
        if selected is True:
            pem_files, rows = self.get_selected_pem_files()
        else:
            pem_files, rows = self.pem_files, np.arange(self.table.rowCount())

        if not pem_files:
            return

        # Zip the pem_files and rows so they can be filtered together
        l = zip(pem_files, rows)
        # Filter the pem_files to only keep un-averaged files
        filt_list = list(filter(lambda x: not x[0].is_split(), l))

        if len(filt_list) == 0:
            return

        self.start_pb(start=0, end=len(filt_list), title='Splitting PEM Files...')
        count = 0
        for pem_file, row in filt_list:
            print(f"Splitting channels for {pem_file.filepath.name}")
            self.pb.setText(f"Splitting channels for {pem_file.filepath.name}")
            if self.auto_create_backup_files_cbox.isChecked():
                self.save_pem_file(copy.deepcopy(pem_file), backup=True, tag='[-S]', remove_old=False)
            pem_file = pem_file.split()
            self.refresh_pem(pem_file)
            count += 1
            self.pb.setValue(count)
        self.end_pb()

    def scale_pem_coil_area(self, coil_area=None, selected=False):
        """
        Scales the data according to the coil area change
        :param coil_area: int:  coil area to scale to
        :param selected: bool, True will only export selected rows.
        """
        if not coil_area:
            coil_area, ok_pressed = QInputDialog.getInt(self, "Set Coil Areas", "Coil Area:")
            if not ok_pressed:
                return

        if selected is True:
            pem_files, rows = self.get_selected_pem_files()
        else:
            pem_files, rows = self.pem_files, np.arange(self.table.rowCount())

        for pem_file, row in zip(pem_files, rows):
            pem_file = pem_file.scale_coil_area(coil_area)
            self.refresh_pem(pem_file)

    def scale_pem_current(self, selected=False):
        """
        Scale the data by current for the selected PEM Files
        :param selected: bool, True will only export selected rows.
        :return: None
        """
        current, ok_pressed = QInputDialog.getDouble(self, "Scale Current", "Current:")
        if ok_pressed:
            if selected is True:
                pem_files, rows = self.get_selected_pem_files()
            else:
                pem_files, rows = self.pem_files, np.arange(self.table.rowCount())

            for pem_file, row in zip(pem_files, rows):
                print(f"Performing current change for {pem_file.filepath.name}")
                pem_file = pem_file.scale_current(current)
                self.refresh_rows(rows=row)

    def reverse_all_data(self, comp):
        """
        Reverse the polarity of all data of a given component for all opened PEM files.
        :param comp: str, either Z, X, or Y
        :return: None
        """
        if len(self.pem_files) > 0:
            for pem_file, pem_info_widget in zip(self.pem_files, self.pem_info_widgets):
                pem_info_widget.reverse_polarity(component=comp)
                pem_file = pem_info_widget.pem_file

    def merge_pem_files(self, selected=False, auto_select=False):
        """
        Action of merging multiple PEM files.
        :param selected: Bool, use selected PEM files
        :param auto_select: Bool, automatically select which PEM files to merge
        """

        def merge_pems(pem_files):
            """
            Merge the list of PEM files into a single PEM file.
            :param pem_files: list, PEMFile objects.
            :return: single PEMFile object
            """
            if isinstance(pem_files, list) and len(pem_files) > 1:
                print(f"Merging {', '.join([f.filepath.name for f in pem_files])}")
                # Data merging section
                currents = [pem_file.current for pem_file in pem_files]
                coil_areas = [pem_file.coil_area for pem_file in pem_files]

                # If any currents are different
                if not all([current == currents[0] for current in currents]):
                    response = self.message.question(self, 'Warning - Different currents',
                                                     f"{', '.join([f.filepath.name for f in pem_files])} do not have the same current. Proceed with merging anyway?",
                                                     self.message.Yes | self.message.No)
                    if response == self.message.No:
                        self.status_bar.showMessage('Aborted.', 2000)
                        return

                # If any coil areas are different
                if not all([coil_area == coil_areas[0] for coil_area in coil_areas]):
                    response = self.message.question(self, 'Warning - Different coil areas',
                                                     f"{', '.join([f.filepath.name for f in pem_files])} do not have the same coil area. Proceed with merging anyway?",
                                                     self.message.Yes | self.message.No)
                    if response == self.message.No:
                        self.status_bar.showMessage('Aborted.', 2000)
                        return

                # If the files aren't all split or un-split
                if any([pem_file.is_split() for pem_file in pem_files]) and any(
                        [not pem_file.is_split() for pem_file in pem_files]):
                    response = self.message.question(self, 'Warning - Different channel split states',
                                                     'There is a mix of channel splitting in the selected files. '
                                                     'Would you like to split the unsplit file(s) and proceed with merging?',
                                                     self.message.Yes | self.message.No)
                    if response == self.message.Yes:
                        for pem_file in pem_files:
                            pem_file = pem_file.split()
                    else:
                        return

                # If the files aren't all de-rotated
                if any([pem_file.is_rotated() for pem_file in pem_files]) and any(
                        [not pem_file.is_rotated() for pem_file in pem_files]):
                    self.message.information(self, 'Error - Different states of XY de-rotation',
                                             'There is a mix of XY de-rotation in the selected files.')

                merged_pem = copy.deepcopy(pem_files[0])
                merged_pem.data = pd.concat([pem_file.data for pem_file in pem_files], axis=0, ignore_index=True)
                merged_pem.number_of_readings = sum([f.number_of_readings for f in pem_files])
                merged_pem.is_merged = True
                merged_pem.filepath = pem_files[0].filepath

                # Add the M tag
                if '[M]' not in pem_files[0].filepath.name:
                    merged_pem.filepath = merged_pem.filepath.with_name(
                        merged_pem.filepath.stem + '[M]' + merged_pem.filepath.suffix)

                self.save_pem_file(merged_pem)
                return merged_pem

        files_to_open = []
        files_to_remove = []

        if selected is True:
            pem_files, rows = self.get_selected_pem_files()
            if len(pem_files) < 2:
                self.message.information(self, 'Error', 'Must select multiple PEM Files')
                return

            # Update the PEM Files from the table
            for pem_file, row in zip(pem_files, rows):
                self.update_pem_from_table(pem_file, row)
            # Merge the files
            merged_pem = merge_pems(pem_files)

            if merged_pem is not None:
                files_to_open.append(merged_pem)
                files_to_remove.extend(pem_files)

        elif auto_select is True:
            if not self.pem_files:
                return

            pem_files, rows = copy.deepcopy(self.pem_files), np.arange(self.table.rowCount())
            pem_files = [self.update_pem_from_table(pem_file, row) for pem_file, row in zip(pem_files, rows)]

            bh_files = [f for f in pem_files if f.is_borehole()]
            sf_files = [f for f in pem_files if f not in bh_files]

            # Merge surface files
            # Group the files by loop name
            for loop, loop_files in groupby(sf_files, key=lambda x: x.loop_name):
                loop_files = list(loop_files)
                print(f"Auto merging loop {loop}")

                # Group the files by line name
                for line, line_files in groupby(loop_files, key=lambda x: x.line_name):
                    line_files = list(line_files)
                    if len(line_files) > 1:
                        print(f"Auto merging line {line}: {[f.filepath.name for f in line_files]}")

                        # Merge the files
                        merged_pem = merge_pems(line_files)

                        if merged_pem is not None:
                            files_to_open.append(merged_pem)
                            files_to_remove.extend(line_files)

            # Merge borehole files
            # Group the files by loop
            for loop, loop_files in groupby(bh_files, key=lambda x: x.loop_name):
                print(f"Loop {loop}")
                loop_files = list(loop_files)

                # Group the files by hole name
                for hole, hole_files in groupby(loop_files, key=lambda x: x.line_name):
                    print(f"Hole {hole}")
                    hole_files = sorted(list(hole_files), key=lambda x: x.get_components())

                    # Group the files by their components
                    for components, comp_files in groupby(hole_files, key=lambda x: x.get_components()):
                        print(f"Components {components}")
                        comp_files = list(comp_files)
                        if len(comp_files) > 1:
                            print(f"Auto merging hole {hole}: {[f.filepath.name for f in comp_files]}")

                            # Merge the files
                            merged_pem = merge_pems(comp_files)

                            if merged_pem is not None:
                                files_to_open.append(merged_pem)
                                files_to_remove.extend(comp_files)

        rows = [pem_files.index(f) for f in files_to_remove]

        if self.auto_create_backup_files_cbox.isChecked():
            for file in reversed(files_to_remove):
                self.save_pem_file(copy.deepcopy(file),
                                   tag='[-M]',
                                   backup=True,
                                   remove_old=self.delete_merged_files_cbox.isChecked())

        if self.delete_merged_files_cbox.isChecked():
            self.remove_file(rows=rows)

        self.open_pem_files(files_to_open)

    def share_loop(self):
        """
        Share the loop GPS of one file with all other opened PEM files.
        :return: None
        """
        widget = self.pem_info_widgets[self.table.currentRow()]
        widget_loop = widget.get_loop().df
        if not widget_loop.empty:
            for widget in self.pem_info_widgets:
                widget.fill_gps_table(widget_loop, widget.loop_table)

    def share_collar(self):
        """
        Share the collar GPS of one file with all other opened PEM files. Will only do so for borehole files.
        :return: None
        """
        widget = self.pem_info_widgets[self.table.currentRow()]
        widget_collar = widget.get_collar().df
        if not widget_collar.empty:
            for widget in list(filter(lambda x: x.pem_file.is_borehole(), self.pem_info_widgets)):
                widget.fill_gps_table(widget_collar, widget.collar_table)

    def share_segments(self):
        """
        Share the segments of one file with all other opened PEM files. Will only do so for borehole files.
        :return: None
        """
        widget = self.pem_info_widgets[self.table.currentRow()]
        wigdet_segments = widget.get_segments().df
        if not wigdet_segments.empty:
            for widget in list(filter(lambda x: x.pem_file.is_borehole(), self.pem_info_widgets)):
                widget.fill_gps_table(wigdet_segments, widget.segments_table)

    def share_station_gps(self):
        """
        Share the station GPS of one file with all other opened PEM files. Will only do so for surface files.
        :return: None
        """
        widget = self.pem_info_widgets[self.table.currentRow()]
        widget_line = widget.get_line().df
        if not widget_line.empty:
            for widget in list(filter(lambda x: not x.pem_file.is_borehole(), self.pem_info_widgets)):
                widget.fill_gps_table(widget_line, widget.line_table)

    def auto_name_lines(self):
        """
        Rename the line and hole names based on the file name. For boreholes, looks for a space character, and uses
        everything before the space (if it exists) as the new name. If there's no space it will use the entire filename
        (minus the extension) as the new name. For surface, it looks for numbers followed by any suffix (NSEW) and uses
        that (with the suffix) as the new name. Makes the change in the table and saves it in the PEM file in memory.
        :return: None
        """
        if any(self.pem_files):
            file_name_column = self.table_columns.index('File')
            line_name_column = self.table_columns.index('Line/Hole')
            new_name = ''
            for row in range(self.table.rowCount()):
                pem_file = self.pem_files[row]
                # survey_type = pem_file.survey_type.lower()
                file_name = self.table.item(row, file_name_column).text()
                if pem_file.is_borehole():
                    # hole_name = re.findall('(.*)(xy|XY|z|Z)', file_name)
                    hole_name = os.path.splitext(file_name)
                    if hole_name:
                        new_name = re.split('\s', hole_name[0])[0]
                else:
                    line_name = re.findall('\d+[nsewNSEW]', file_name)
                    if line_name:
                        new_name = line_name[0].strip()

                pem_file.line_name = new_name
                name_item = QTableWidgetItem(new_name)
                name_item.setTextAlignment(QtCore.Qt.AlignCenter)
                self.table.setItem(row, line_name_column, name_item)
            self.refresh_rows(rows='all')

    def rename_all_repeat_stations(self):
        """
        Rename all repeat stations (i.e. stations ending in 1, or 6... to a 0 or 5).
        :return: None
        """
        if any(self.pem_files):
            num_repeat_stations = 0
            for i, widget in enumerate(self.pem_info_widgets):
                num_repeat_stations += widget.num_repeat_stations
                widget.rename_repeat_stations()
            self.refresh_rows(rows='all')
            # self.refresh_table()
            self.status_bar.showMessage(f'{num_repeat_stations} repeat station(s) automatically renamed.',
                                                  2000)


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
                print('Not a number')
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
                print('Not a number')
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

        self.pem_files = []
        self.ri_files = []
        self.crs = CRS()

        self.plan_map_options = PlanMapOptions(parent=self)
        self.message = QMessageBox()
        self.pb_win = QWidget()  # Progress bar window
        self.pb_win.resize(400, 45)
        self.pb_win.setLayout(QVBoxLayout())
        self.pb_win.setWindowTitle('Saving PDF Plots...')

        # self.pb_text = QLabel('')
        # self.pb_win.layout().addWidget(self.pb_text)

        # Set validations
        int_validator = QtGui.QIntValidator()
        self.max_range_edit.setValidator(int_validator)
        self.min_range_edit.setValidator(int_validator)
        self.section_depth_edit.setValidator(int_validator)

        # Signals
        self.print_btn.clicked.connect(self.print_pdfs)
        self.cancel_btn.clicked.connect(self.close)
        self.plan_map_options_btn.clicked.connect(self.plan_map_options.show)

    def keyPressEvent(self, e):
        if e.key() == QtCore.Qt.Key_Escape:
            self.close()

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

        self.show()

    def print_pdfs(self):

        def get_save_file():
            default_path = self.pem_files[-1].filepath.parent
            # self.dialog.setDirectory(str(default_path))
            save_dir = QFileDialog.getSaveFileName(self, '', str(default_path))[0]
            print(f"Saving PDFs to {save_dir}")
            return save_dir

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

        # Make sure CRS is passed and valid if making a plan map
        if self.make_plan_maps_gbox.isChecked():
            if not self.crs.is_valid():
                response = self.message.question(self, 'No CRS',
                                                 'No CRS has been selected. ' +
                                                 'Do you wish to proceed without a plan map?',
                                                 self.message.Yes | self.message.No)
                if response == self.message.No:
                    self.close()

        save_dir = get_save_file()
        if save_dir:

            def pb_close(e):
                # Tell the printer to stop printing
                printer.stop = True
                print(f"Printing cancelled")

            save_dir = os.path.splitext(save_dir)[0]
            printer = PEMPrinter(parent=self, **plot_kwargs)
            # Connect the closing of the progress bar window to the pb_close function, which stops the running function
            self.pb_win.closeEvent = pb_close
            # Add the printer's progress bar to the progress bar window
            self.pb_win.layout().insertWidget(0, printer.pb)
            self.pb_win.show()
            QApplication.processEvents()

            try:
                # PEM Files and RI files zipped together for when they get sorted
                printer.print_files(save_dir, files=list(zip(self.pem_files, self.ri_files)))
            except FileNotFoundError:
                self.message.information(self, 'Error', f'{save_dir} does not exist')
            except IOError:
                self.message.information(self, 'Error', f'{save_dir} is currently opened')
            finally:
                self.pb_win.layout().removeWidget(printer.pb)
                self.pb_win.hide()
                self.close()
        else:
            self.close()


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
        self.initSignals()

    def initSignals(self):
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


class MagDeclinationCalculator(QMainWindow):
    """
    Converts the first coordinates found into lat lon. Must have GPS information in order to convert to lat lon.
    """
    def __init__(self, parent=None):
        super().__init__()
        self.parent = parent
        self.setWindowTitle('Magnetic Declination')
        self.setWindowIcon(QIcon(os.path.join(icons_path, 'mag_field.png')))
        self.setGeometry(600, 300, 300, 200)
        self.statusBar().showMessage('', 10)

        self.message = QMessageBox()
        self.layout = QGridLayout()
        self.layout.setColumnStretch(1, 4)
        self.layout.setColumnStretch(2, 4)

        self.mag_widget = QWidget()
        self.mag_widget.setLayout(self.layout)
        self.setCentralWidget(self.mag_widget)
        self.layout.addWidget(QLabel(f'Latitude (°)'), 0, 0)
        self.layout.addWidget(QLabel(f'Longitude (°)'), 1, 0)
        self.layout.addWidget(QLabel('Declination (°)'), 2, 0)
        self.layout.addWidget(QLabel('Inclination (°)'), 3, 0)
        self.layout.addWidget(QLabel('Total Field (nT)'), 4, 0)

        self.lat_edit = QPushButton()
        self.lat_edit.clicked.connect(lambda: self.copy_text(self.lat_edit.text()))
        self.lon_edit = QPushButton()
        self.lon_edit.clicked.connect(lambda: self.copy_text(self.lon_edit.text()))
        self.dec_edit = QPushButton()
        self.dec_edit.clicked.connect(lambda: self.copy_text(self.dec_edit.text()))
        self.inc_edit = QPushButton()
        self.inc_edit.clicked.connect(lambda: self.copy_text(self.inc_edit.text()))
        self.tf_edit = QPushButton()
        self.tf_edit.clicked.connect(lambda: self.copy_text(self.tf_edit.text()))

        self.layout.addWidget(self.lat_edit, 0, 2)
        self.layout.addWidget(self.lon_edit, 1, 2)
        self.layout.addWidget(self.dec_edit, 2, 2)
        self.layout.addWidget(self.inc_edit, 3, 2)
        self.layout.addWidget(self.tf_edit, 4, 2)

    def copy_text(self, str_value):
        """
        Copy the str_value to the clipboard
        :param str_value: str
        :return None
        """
        cb = QtGui.QApplication.clipboard()
        cb.clear(mode=cb.Clipboard)
        cb.setText(str_value, mode=cb.Clipboard)
        self.statusBar().showMessage(f"{str_value} copied to clipboard", 1000)

    def calc_mag_dec(self, pem_file, crs):
        """
        Calculate the magnetic declination for the PEM file.
        :param pem_file: PEMFile object
        :param crs: CRS object
        :return: None
        """
        if not pem_file:
            return

        # if crs.is_nad27():
        #     self.message.information(self, 'Incompatible datum. Must be either NAD 1983 or WGS 1984')
        #     return
        if not crs.is_valid():
            self.message.information(self, 'Error', 'GPS coordinate system information is invalid')
            return

        if pem_file.has_collar_gps():
            coords = pem_file.geometry.collar
        elif pem_file.has_loop_gps():
            coords = pem_file.loop
        elif pem_file.has_line_coords():
            coords = pem_file.line
        else:
            self.message.information(self, 'Error', 'No GPS')
            return

        coords.crs = crs
        coords = coords.to_latlon().df
        lat, lon, elevation = coords.iloc[0]['Northing'], coords.iloc[0]['Easting'], coords.iloc[0]['Elevation']

        gm = geomag.geomag.GeoMag()
        mag = gm.GeoMag(lat, lon, elevation)
        self.lat_edit.setText(f"{lat:.4f}")
        self.lon_edit.setText(f"{lon:.4f}")
        self.dec_edit.setText(f"{mag.dec:.2f}")
        self.inc_edit.setText(f"{mag.dip:.2f}")
        self.tf_edit.setText(f"{mag.ti:.2f}")


def main():
    from src.pem.pem_getter import PEMGetter
    app = QApplication(sys.argv)
    mw = PEMHub()
    # mw.show()

    pg = PEMGetter()
    # pem_files = pg.get_pems(client='PEM Rotation', file='BR01.PEM')
    # pem_files = pg.get_pems(client='PEM Rotation', number=4)
    # pem_files = pg.get_pems(client='Minera', subfolder='CPA-5051', number=4)

    # file = r'C:\Users\Mortulo\PycharmProjects\PEMPro\sample_files\DMP files\DMP\KIS0015\pp.dmp'
    # mw.open_dmp_files(file)
    mw.show()

    # mw.show()
    # mw.open_pem_files(pem_files)
    # mw.delete_merged_files_cbox.setChecked(False)

    # mw.merge_pem_files(pem_files)
    # mw.average_pem_data()
    # mw.split_pem_channels(pem_files[0])
    # mw.open_pdf_plot_printer(selected_files=False)

    app.exec_()


if __name__ == '__main__':
    main()
    # cProfile.run('main()', 'restats')
    # p = pstats.Stats('restats')
    # p.sort_stats('cumulative').print_stats(.5)

    # p.sort_stats('time', 'cumulative').print_stats()
    # p.strip_dirs().sort_stats(-1).print_stats()