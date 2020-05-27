import copy
import datetime
import logging
import os
import re
import csv
import sys
import time
import utm
import pandas as pd
import numpy as np
import pyqtgraph as pg
import simplekml
import natsort
import keyboard
from shutil import copyfile
from itertools import chain, groupby
from PyQt5 import (QtCore, QtGui, uic)
from PyQt5.QtWidgets import (QWidget, QMainWindow, QApplication, QDesktopWidget, QMessageBox, QFileDialog,
                             QAbstractScrollArea, QTableWidgetItem, QAction, QMenu, QGridLayout,
                             QInputDialog, QHeaderView, QTableWidget, QErrorMessage, QDialogButtonBox, QVBoxLayout,
                             QLabel, QLineEdit, QPushButton, QAbstractItemView, QShortcut)
import matplotlib.pyplot as plt
# from pyqtspinner.spinner import WaitingSpinner
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas, \
    NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.ticker import FixedLocator
from src.geomag import geomag
from src.pem.pem_file import PEMFile, PEMParser
from src.gps.gps_editor import SurveyLine, TransmitterLoop, BoreholeCollar, BoreholeGeometry, INFParser, GPXEditor
from src.pem.pem_file_editor import PEMFileEditor
from src.qt_py.custom_tables import UnpackerTable
from src.pem.pem_plotter import PEMPrinter, Map3D, Section3D, CustomProgressBar, MapPlotMethods, ContourMap, FoliumMap
from src.pem.pem_planner import LoopPlanner, GridPlanner
from src.pem.pem_serializer import PEMSerializer
from src.pem.xyz_serializer import XYZSerializer
from src.qt_py.pem_info_widget import PEMFileInfoWidget
from src.ri.ri_file import RIFile

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s', datefmt='%d-%b-%y %H:%M:%S')

if getattr(sys, 'frozen', False):
    # If the application is run as a bundle, the pyInstaller bootloader
    # extends the sys module by a flag frozen=True and sets the app
    # path into variable _MEIPASS'.
    application_path = sys._MEIPASS
    editorWindowCreatorFile = 'qt_ui\\pem_editor.ui'
    lineNameEditorCreatorFile = 'qt_ui\\line_name_editor.ui'
    planMapOptionsCreatorFile = 'qt_ui\\plan_map_options.ui'
    pemFileSplitterCreatorFile = 'qt_ui\\pem_file_splitter.ui'
    map3DCreatorFile = 'qt_ui\\3D_map.ui'
    section3DCreatorFile = 'qt_ui\\3D_section.ui'
    contourMapCreatorFile = 'qt_ui\\contour_map.ui'
    icons_path = 'icons'
else:
    application_path = os.path.dirname(os.path.abspath(__file__))
    editorWindowCreatorFile = os.path.join(os.path.dirname(application_path), 'qt_ui\\pem_editor.ui')
    lineNameEditorCreatorFile = os.path.join(os.path.dirname(application_path), 'qt_ui\\line_name_editor.ui')
    planMapOptionsCreatorFile = os.path.join(os.path.dirname(application_path), 'qt_ui\\plan_map_options.ui')
    pemFileSplitterCreatorFile = os.path.join(os.path.dirname(application_path), 'qt_ui\\pem_file_splitter.ui')
    map3DCreatorFile = os.path.join(os.path.dirname(application_path), 'qt_ui\\3D_map.ui')
    section3DCreatorFile = os.path.join(os.path.dirname(application_path), 'qt_ui\\3D_section.ui')
    contourMapCreatorFile = os.path.join(os.path.dirname(application_path), 'qt_ui\\contour_map.ui')
    icons_path = os.path.join(os.path.dirname(application_path), "qt_ui\\icons")

# Load Qt ui file into a class
Ui_PEMEditorWindow, QtBaseClass = uic.loadUiType(editorWindowCreatorFile)
Ui_LineNameEditorWidget, QtBaseClass = uic.loadUiType(lineNameEditorCreatorFile)
Ui_PlanMapOptionsWidget, QtBaseClass = uic.loadUiType(planMapOptionsCreatorFile)
Ui_PEMFileSplitterWidget, QtBaseClass = uic.loadUiType(pemFileSplitterCreatorFile)
Ui_Map3DWidget, QtBaseClass = uic.loadUiType(map3DCreatorFile)
Ui_Section3DWidget, QtBaseClass = uic.loadUiType(section3DCreatorFile)
Ui_ContourMapCreatorFile, QtBaseClass = uic.loadUiType(contourMapCreatorFile)

# sys._excepthook = sys.excepthook
#
#
# def exception_hook(exctype, value, traceback):
#     print(exctype, value, traceback)
#     sys._excepthook(exctype, value, traceback)
#     sys.exit(1)
#
#
# sys.excepthook = exception_hook


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


class PEMEditorWindow(QMainWindow, Ui_PEMEditorWindow):

    def __init__(self, parent=None):
        super().__init__()
        self.parent = parent
        self.initUi()

        self.pem_files = []
        self.pem_info_widgets = []
        self.tab_num = 1
        self.allow_signals = True

        self.dialog = QFileDialog()
        self.pem_parser = PEMParser()
        self.line_adder = LineAdder()
        self.loop_adder = LoopAdder()
        self.file_editor = PEMFileEditor()
        self.message = QMessageBox()
        self.error = QErrorMessage()
        self.gpx_editor = GPXEditor()
        self.gps_adder = GPSAdder()
        self.serializer = PEMSerializer()
        self.mpm = MapPlotMethods()
        self.pg = CustomProgressBar()

        # self.spinner = WaitingSpinner(self.table)
        self.ri_importer = BatchRIImporter(parent=self)
        self.plan_map_options = PlanMapOptions(parent=self)
        self.map_viewer_3d = None
        self.section_viewer_3d = None
        self.pem_file_splitter = None
        self.contour_viewer = None
        self.loop_planner = None

        self.initMenus()
        self.initSignals()

        self.table_columns = [
            'File',
            'Date',
            'Client',
            'Grid',
            'Line/Hole'
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
        # self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.gps_systems = ['', 'UTM']
        self.gps_zones = [''] + [f"{num} North" for num in range(1, 61)] + [f"{num} South" for num in range(1, 61)]
        self.gps_datums = ['', 'NAD 1927', 'NAD 1983', 'WGS 1984']
        for system in self.gps_systems:
            self.systemCBox.addItem(system)
        for zone in self.gps_zones:
            self.zoneCBox.addItem(zone)
        for datum in self.gps_datums:
            self.datumCBox.addItem(datum)

        # Set validations
        int_validator = QtGui.QIntValidator()
        self.max_range_edit.setValidator(int_validator)
        self.min_range_edit.setValidator(int_validator)
        self.section_depth_edit.setValidator(int_validator)

    def initUi(self):
        """
        Initializing the UI.
        :return: None
        """
        def center_window(self):
            qtRectangle = self.frameGeometry()
            centerPoint = QDesktopWidget().availableGeometry().center()
            qtRectangle.moveCenter(centerPoint)
            self.move(qtRectangle.topLeft())

        self.setupUi(self)
        self.setAcceptDrops(True)
        self.setWindowTitle("PEMEditor")
        self.setWindowIcon(
            QtGui.QIcon(os.path.join(icons_path, 'pem_editor_3.png')))
        self.setGeometry(500, 300, 1700, 900)
        center_window(self)

        self.stackedWidget.hide()
        self.pemInfoDockWidget.hide()
        self.plotsDockWidget.hide()
        # self.plotsDockWidget.setWidget(self.tabWidget)
        # self.addDockWidget(QtCore.Qt.RightDockWidgetArea, self.stackedWidget)

    def initMenus(self):
        """
        Initializing all actions.
        :return: None
        """
        # 'File' menu
        self.actionOpenFile.setShortcut("Ctrl+O")
        self.actionOpenFile.setStatusTip('Open file')
        self.actionOpenFile.setToolTip('Open file')
        self.actionOpenFile.setIcon(QtGui.QIcon(os.path.join(icons_path, 'open.png')))
        self.actionOpenFile.triggered.connect(self.open_file_dialog)

        self.actionSaveFiles.setShortcut("Ctrl+S")
        self.actionSaveFiles.setIcon(QtGui.QIcon(os.path.join(icons_path, 'save.png')))
        self.actionSaveFiles.setStatusTip("Save all files")
        self.actionSaveFiles.setToolTip("Save all files")
        self.actionSaveFiles.triggered.connect(lambda: self.save_pem_files(all=True))

        self.actionSave_Files_as_XYZ.setStatusTip("Save all files as XYZ files. Only for surface surveys.")
        self.actionSave_Files_as_XYZ.triggered.connect(lambda: self.save_as_xyz(selected_files=False))

        self.actionExport_Files.setShortcut("F11")
        self.actionExport_Files.setStatusTip("Export all files to a specified location.")
        self.actionExport_Files.setToolTip("Export all files to a specified location.")
        self.actionExport_Files.triggered.connect(lambda: self.export_pem_files(all=True))

        self.actionExport_Final_PEM_Files.setShortcut("F9")
        self.actionExport_Final_PEM_Files.setStatusTip("Export the final PEM files")
        self.actionExport_Final_PEM_Files.setToolTip("Export the final PEM files")
        self.actionExport_Final_PEM_Files.triggered.connect(lambda: self.export_pem_files(export_final=True))

        self.actionPrint_Plots_to_PDF.setShortcut("F12")
        self.actionPrint_Plots_to_PDF.setStatusTip("Print plots to a PDF file")
        self.actionPrint_Plots_to_PDF.setToolTip("Print plots to a PDF file")
        self.actionPrint_Plots_to_PDF.triggered.connect(self.print_plots)

        self.actionBackup_Files.setStatusTip("Backup all files in the table.")
        self.actionBackup_Files.setToolTip("Backup all files in the table.")
        self.actionBackup_Files.triggered.connect(self.backup_files)

        self.actionImport_RI_Files.setShortcut("Ctrl+I")
        self.actionImport_RI_Files.setStatusTip("Import multiple RI files")
        self.actionImport_RI_Files.setToolTip("Import multiple RI files")
        self.actionImport_RI_Files.triggered.connect(self.import_ri_files)

        # PEM menu
        self.actionRename_All_Lines_Holes.setStatusTip("Rename all line/hole names")
        self.actionRename_All_Lines_Holes.setToolTip("Rename all line/hole names")
        self.actionRename_All_Lines_Holes.triggered.connect(lambda: self.batch_rename(type='Line'))

        self.actionRename_All_Files.setStatusTip("Rename all file names")
        self.actionRename_All_Files.setToolTip("Rename all file names")
        self.actionRename_All_Files.triggered.connect(lambda: self.batch_rename(type='File'))

        self.actionAverage_All_PEM_Files.setStatusTip("Average all PEM files")
        self.actionAverage_All_PEM_Files.setToolTip("Average all PEM files")
        self.actionAverage_All_PEM_Files.setIcon(QtGui.QIcon(os.path.join(icons_path, 'average.png')))
        self.actionAverage_All_PEM_Files.setShortcut("F5")
        self.actionAverage_All_PEM_Files.triggered.connect(lambda: self.average_pem_data(all=True))

        self.actionSplit_All_PEM_Files.setStatusTip("Remove on-time channels for all PEM files")
        self.actionSplit_All_PEM_Files.setToolTip("Remove on-time channels for all PEM files")
        self.actionSplit_All_PEM_Files.setIcon(QtGui.QIcon(os.path.join(icons_path, 'split.png')))
        self.actionSplit_All_PEM_Files.setShortcut("F6")
        self.actionSplit_All_PEM_Files.triggered.connect(lambda: self.split_pem_channels(all=True))

        self.actionScale_All_Currents.setStatusTip("Scale the current of all PEM Files to the same value")
        self.actionScale_All_Currents.setToolTip("Scale the current of all PEM Files to the same value")
        self.actionScale_All_Currents.setIcon(QtGui.QIcon(os.path.join(icons_path, 'current.png')))
        self.actionScale_All_Currents.setShortcut("F7")
        self.actionScale_All_Currents.triggered.connect(lambda: self.scale_pem_current(all=True))

        self.actionChange_All_Coil_Areas.setStatusTip("Scale all coil areas to the same value")
        self.actionChange_All_Coil_Areas.setToolTip("Scale all coil areas to the same value")
        self.actionChange_All_Coil_Areas.setIcon(QtGui.QIcon(os.path.join(icons_path, 'coil.png')))
        self.actionChange_All_Coil_Areas.setShortcut("F8")
        self.actionChange_All_Coil_Areas.triggered.connect(lambda: self.scale_pem_coil_area(all=True))

        # GPS menu
        self.actionSave_as_KMZ.setStatusTip("Create a KMZ file using all GPS in the opened PEM file(s)")
        self.actionSave_as_KMZ.setToolTip("Create a KMZ file using all GPS in the opened PEM file(s)")
        self.actionSave_as_KMZ.setIcon(QtGui.QIcon(os.path.join(icons_path, 'google_earth.png')))
        self.actionSave_as_KMZ.triggered.connect(self.save_as_kmz)

        self.actionExport_All_GPS.setStatusTip("Export all GPS in the opened PEM file(s) to separate CSV files")
        self.actionExport_All_GPS.setToolTip("Export all GPS in the opened PEM file(s) to separate CSV files")
        self.actionExport_All_GPS.setIcon(QtGui.QIcon(os.path.join(icons_path, 'csv.png')))
        self.actionExport_All_GPS.triggered.connect(self.export_all_gps)

        # Map menu
        self.actionPlan_Map.setStatusTip("Plot all PEM files on an interactive plan map")
        self.actionPlan_Map.setToolTip("Plot all PEM files on an interactive plan map")
        self.actionPlan_Map.setIcon(QtGui.QIcon(os.path.join(icons_path, 'folium.png')))
        self.actionPlan_Map.triggered.connect(self.show_plan_map)

        self.action3D_Map.setStatusTip("Show 3D map of all PEM files")
        self.action3D_Map.setToolTip("Show 3D map of all PEM files")
        self.action3D_Map.setShortcut('Ctrl+M')
        self.action3D_Map.setIcon(QtGui.QIcon(os.path.join(icons_path, '3d_map2.png')))
        self.action3D_Map.triggered.connect(self.show_map_3d_viewer)

        self.actionContour_Map.setIcon(QtGui.QIcon(os.path.join(icons_path, 'contour_map3.png')))
        self.actionContour_Map.setStatusTip("Show a contour map of surface PEM files")
        self.actionContour_Map.setToolTip("Show a contour map of surface PEM files")
        self.actionContour_Map.triggered.connect(self.show_contour_map_viewer)

        # Tools menu
        self.actionLoop_Planner.setStatusTip("Loop planner")
        self.actionLoop_Planner.setToolTip("Loop planner")
        self.actionLoop_Planner.setIcon(
            QtGui.QIcon(os.path.join(icons_path, 'loop_planner.png')))
        self.actionLoop_Planner.triggered.connect(self.show_loop_planner)

        self.actionGrid_Planner.setStatusTip("Grid planner")
        self.actionGrid_Planner.setToolTip("Grid planner")
        self.actionGrid_Planner.setIcon(
            QtGui.QIcon(os.path.join(icons_path, 'grid_planner.png')))
        self.actionGrid_Planner.triggered.connect(self.show_grid_planner)

        self.actionConvert_Timebase_Frequency.setStatusTip("Two way conversion between timebase and frequency")
        self.actionConvert_Timebase_Frequency.setToolTip("Two way conversion between timebase and frequency")
        self.actionConvert_Timebase_Frequency.setIcon(QtGui.QIcon(os.path.join(icons_path, 'freq_timebase_calc.png')))
        self.actionConvert_Timebase_Frequency.triggered.connect(self.timebase_freqency_converter)

        # Actions
        self.actionDel_File = QAction("&Remove File", self)
        self.actionDel_File.setShortcut("Del")
        self.actionDel_File.triggered.connect(self.remove_file_selection)
        self.addAction(self.actionDel_File)
        self.actionDel_File.setEnabled(False)

        self.actionClear_Files = QAction("&Clear All Files", self)
        self.actionClear_Files.setShortcut("Shift+Del")
        self.actionClear_Files.setStatusTip("Clear all files")
        self.actionClear_Files.setToolTip("Clear all files")
        self.actionClear_Files.triggered.connect(self.clear_files)

        self.merge_action = QAction("&Merge", self)
        self.merge_action.triggered.connect(self.merge_pem_files_selection)
        self.merge_action.setShortcut("Shift+M")

    def initSignals(self):
        """
        Initializing all signals.
        :return: None
        """
        self.table.viewport().installEventFilter(self)
        self.table.installEventFilter(self)
        self.table.setFocusPolicy(QtCore.Qt.StrongFocus)

        self.table.itemSelectionChanged.connect(lambda: self.stackedWidget.setCurrentIndex(self.table.currentRow()))
        self.table.cellChanged.connect(self.table_value_changed)

        self.plan_map_options_btn.clicked.connect(self.plan_map_options.show)
        self.print_plots_btn.clicked.connect(self.print_plots)

        self.share_client_cbox.stateChanged.connect(
            lambda: self.client_edit.setEnabled(self.share_client_cbox.isChecked()))
        self.share_grid_cbox.stateChanged.connect(
            lambda: self.grid_edit.setEnabled(self.share_grid_cbox.isChecked()))
        self.share_loop_cbox.stateChanged.connect(
            lambda: self.loop_edit.setEnabled(self.share_loop_cbox.isChecked()))
        # single_row must be explicitly stated since stateChanged returns an int based on the state
        self.share_client_cbox.stateChanged.connect(lambda: self.refresh_table(single_row=False))
        self.share_grid_cbox.stateChanged.connect(lambda: self.refresh_table(single_row=False))
        self.share_loop_cbox.stateChanged.connect(lambda: self.refresh_table(single_row=False))

        self.client_edit.textChanged.connect(lambda: self.refresh_table(single_row=False))
        self.grid_edit.textChanged.connect(lambda: self.refresh_table(single_row=False))
        self.loop_edit.textChanged.connect(lambda: self.refresh_table(single_row=False))

        self.share_range_cbox.stateChanged.connect(
            lambda: self.min_range_edit.setEnabled(self.share_range_cbox.isChecked()))
        self.share_range_cbox.stateChanged.connect(
            lambda: self.max_range_edit.setEnabled(self.share_range_cbox.isChecked()))
        # self.share_range_cbox.stateChanged.connect(self.refresh_table)

        # TODO Change this once pandas is added
        self.reset_range_btn.clicked.connect(self.fill_share_range)

        # self.min_range_edit.editingFinished.connect(lambda: self.refresh_table(single_row=False))
        # self.max_range_edit.editingFinished.connect(lambda: self.refresh_table(single_row=False))

        self.auto_name_line_btn.clicked.connect(self.auto_name_lines)
        self.auto_merge_files_btn.clicked.connect(self.auto_merge_pem_files)

        self.reverseAllZButton.clicked.connect(lambda: self.reverse_all_data(comp='Z'))
        self.reverseAllXButton.clicked.connect(lambda: self.reverse_all_data(comp='X'))
        self.reverseAllYButton.clicked.connect(lambda: self.reverse_all_data(comp='Y'))
        self.rename_all_repeat_stations_btn.clicked.connect(self.rename_all_repeat_stations)

        self.systemCBox.currentIndexChanged.connect(
            lambda: self.zoneCBox.setEnabled(True if self.systemCBox.currentText() == 'UTM' else False))

        self.reset_crs_btn.clicked.connect(lambda: self.systemCBox.setCurrentIndex(0))
        self.reset_crs_btn.clicked.connect(lambda: self.zoneCBox.setCurrentIndex(0))
        self.reset_crs_btn.clicked.connect(lambda: self.datumCBox.setCurrentIndex(0))

    def contextMenuEvent(self, event):
        """
        Right-click context menu items.
        :param event: Right-click event.
        :return: None
        """
        if self.table.underMouse():
            if self.table.selectionModel().selectedIndexes():
                selected_pems, rows = self.get_selected_pem_files()
                survey_type = selected_pems[0].survey_type.lower()

                self.table.menu = QMenu(self.table)
                self.table.remove_file_action = QAction("&Remove", self)
                self.table.remove_file_action.triggered.connect(self.remove_file_selection)
                self.table.remove_file_action.setIcon(QtGui.QIcon(os.path.join(icons_path, 'remove.png')))

                self.table.open_file_action = QAction("&Open", self)
                self.table.open_file_action.triggered.connect(self.open_in_text_editor)
                self.table.open_file_action.setIcon(QtGui.QIcon(os.path.join(icons_path, 'txt_file.png')))

                self.table.save_file_action = QAction("&Save", self)
                self.table.save_file_action.setIcon(QtGui.QIcon(os.path.join(icons_path, 'save.png')))
                self.table.save_file_action.triggered.connect(self.save_pem_files)

                self.table.export_pem_action = QAction("&Export...", self)
                self.table.export_pem_action.triggered.connect(self.export_pem_files)

                self.table.save_file_as_action = QAction("&Save As...", self)
                self.table.save_file_as_action.triggered.connect(self.save_pem_file_as)

                self.table.save_as_xyz_action = QAction("&Save As XYZ...", self)
                self.table.save_as_xyz_action.triggered.connect(lambda: self.save_as_xyz(selected_files=True))

                self.table.print_plots_action = QAction("&Print Plots", self)
                self.table.print_plots_action.setIcon(QtGui.QIcon(os.path.join(icons_path, 'pdf.png')))
                self.table.print_plots_action.triggered.connect(lambda: self.print_plots(selected_files=True))

                self.table.extract_stations_action = QAction("&Extract Stations", self)
                self.table.extract_stations_action.triggered.connect(self.extract_stations)

                self.table.calc_mag_dec = QAction("&Magnetic Declination", self)
                self.table.calc_mag_dec.setIcon(QtGui.QIcon(os.path.join(icons_path, 'mag_field.png')))
                self.table.calc_mag_dec.triggered.connect(lambda: self.calc_mag_declination(selected_pems[0]))

                self.table.view_3d_section_action = QAction("&View 3D Section", self)
                self.table.view_3d_section_action.setIcon(QtGui.QIcon(os.path.join(icons_path, 'section_3d.png')))
                self.table.view_3d_section_action.triggered.connect(self.show_section_3d_viewer)

                self.table.average_action = QAction("&Average", self)
                self.table.average_action.triggered.connect(self.average_pem_data)
                self.table.average_action.setIcon(QtGui.QIcon(os.path.join(icons_path, 'average.png')))

                self.table.split_action = QAction("&Split Channels", self)
                self.table.split_action.triggered.connect(self.split_pem_channels)
                self.table.split_action.setIcon(QtGui.QIcon(os.path.join(icons_path, 'split.png')))

                self.table.scale_current_action = QAction("&Scale Current", self)
                self.table.scale_current_action.triggered.connect(self.scale_pem_current)
                self.table.scale_current_action.setIcon(QtGui.QIcon(os.path.join(icons_path, 'current.png')))

                self.table.scale_ca_action = QAction("&Scale Coil Area", self)
                self.table.scale_ca_action.triggered.connect(self.scale_pem_coil_area)
                self.table.scale_ca_action.setIcon(QtGui.QIcon(os.path.join(icons_path, 'coil.png')))

                self.table.share_loop_action = QAction("&Share Loop", self)
                self.table.share_loop_action.triggered.connect(self.share_loop)

                self.table.share_collar_action = QAction("&Share Collar", self)
                self.table.share_collar_action.triggered.connect(self.share_collar)

                self.table.share_segments_action = QAction("&Share Geometry", self)
                self.table.share_segments_action.triggered.connect(self.share_segments)

                self.table.share_station_gps_action = QAction("&Share Station GPS", self)
                self.table.share_station_gps_action.triggered.connect(self.share_station_gps)

                self.table.rename_lines_action = QAction("&Rename Lines/Holes", self)
                self.table.rename_lines_action.triggered.connect(lambda: self.batch_rename(type='Line'))

                self.table.rename_files_action = QAction("&Rename Files", self)
                self.table.rename_files_action.triggered.connect(lambda: self.batch_rename(type='File'))

                self.table.menu.addAction(self.table.open_file_action)
                self.table.menu.addAction(self.table.save_file_action)
                if len(self.table.selectionModel().selectedRows()) == 1:
                    self.table.menu.addAction(self.table.save_file_as_action)
                    self.table.menu.addAction(self.table.save_as_xyz_action)
                    self.table.menu.addAction(self.table.extract_stations_action)
                    self.table.menu.addAction(self.table.calc_mag_dec)
                else:
                    self.table.menu.addAction(self.table.save_as_xyz_action)
                    self.table.menu.addAction(self.table.export_pem_action)
                self.table.menu.addSeparator()
                self.table.menu.addAction(self.table.print_plots_action)
                self.table.menu.addSeparator()
                if len(self.table.selectionModel().selectedRows()) > 1:
                    self.table.menu.addAction(self.merge_action)
                self.table.menu.addAction(self.table.average_action)
                self.table.menu.addAction(self.table.split_action)
                self.table.menu.addAction(self.table.scale_current_action)
                self.table.menu.addAction(self.table.scale_ca_action)
                if len(self.pem_files) > 1 and len(self.table.selectionModel().selectedRows()) == 1:
                    self.table.menu.addSeparator()
                    self.table.menu.addAction(self.table.share_loop_action)
                    if 'borehole' in survey_type:
                        self.table.menu.addAction(self.table.share_collar_action)
                        self.table.menu.addAction(self.table.share_segments_action)
                    elif 'surface' in survey_type or 'squid' in survey_type:
                        self.table.menu.addAction(self.table.share_station_gps_action)
                if len(self.table.selectionModel().selectedRows()) > 1:
                    self.table.menu.addSeparator()
                    self.table.menu.addAction(self.table.rename_lines_action)
                    self.table.menu.addAction(self.table.rename_files_action)
                self.table.menu.addSeparator()
                if 'borehole' in survey_type:
                    self.table.menu.addAction(self.table.view_3d_section_action)
                    self.table.menu.addSeparator()
                self.table.menu.addAction(self.table.remove_file_action)

                self.table.menu.popup(QtGui.QCursor.pos())
            else:
                pass
        else:
            pass

    def eventFilter(self, source, event):
        if (event.type() == QtCore.QEvent.MouseButtonPress and
                source is self.table.viewport() and
                self.table.itemAt(event.pos()) is None):
            self.table.clearSelection()
        elif source == self.table and event.type() == QtCore.QEvent.FocusIn:
            self.actionDel_File.setEnabled(True)  # Makes the 'Del' shortcut work when the table is in focus
        elif source == self.table and event.type() == QtCore.QEvent.FocusOut:
            self.actionDel_File.setEnabled(False)
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
        urls = [url.toLocalFile() for url in e.mimeData().urls()]
        pem_files = False
        text_files = False
        ri_files = False
        inf_files = False
        gpx_files = False

        if all([url.lower().endswith('pem') for url in urls]):
            pem_files = True
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
            pem_files,
        ]))

        # When no PEM files are open, only open PEM files and not any other kind of file
        if not self.pem_files:
            if pem_conditions is True:
                e.acceptProposedAction()
            else:
                e.ignore()

        else:
            eligible_tabs = [self.stackedWidget.currentWidget().Station_GPS_Tab,
                             self.stackedWidget.currentWidget().Loop_GPS_Tab,
                             self.stackedWidget.currentWidget().Geometry_Tab]

            gps_conditions = bool(all([
                e.answerRect().intersects(self.pemInfoDockWidget.geometry()),
                text_files is True or gpx_files is True,
                self.stackedWidget.currentWidget().tabs.currentWidget() in eligible_tabs,
                len(self.pem_files) > 0
            ]))

            ri_conditions = bool(all([
                e.answerRect().intersects(self.pemInfoDockWidget.geometry()),
                ri_files is True,
                self.stackedWidget.currentWidget().tabs.currentWidget() == self.stackedWidget.currentWidget().RI_Tab,
                len(self.pem_files) > 0
            ]))

            inf_conditions = bool(all([
                e.answerRect().intersects(self.main_frame_gps_tab.geometry()),
                inf_files is True or gpx_files is True,
            ]))

            if pem_conditions is True or gps_conditions is True or ri_conditions is True or inf_conditions is True:
                e.acceptProposedAction()
            else:
                e.ignore()

    def dropEvent(self, e):
        urls = [url.toLocalFile() for url in e.mimeData().urls()]

        pem_files = [file for file in urls if file.lower().endswith('pem')]
        gps_files = [file for file in urls if
                     file.lower().endswith('txt') or file.lower().endswith('csv') or file.lower().endswith(
                         'seg') or file.lower().endswith('xyz')]
        ri_files = [file for file in urls if
                    file.lower().endswith('ri1') or file.lower().endswith('ri2') or file.lower().endswith('ri3')]
        inf_files = [file for file in urls if file.lower().endswith('inf') or file.lower().endswith('log')]
        gpx_files = [file for file in urls if file.lower().endswith('gpx')]

        start_time = time.time()
        if pem_files:
            self.open_pem_files(pem_files)
            print(f'open_pem_files time: {time.time() - start_time} seconds')

        if gps_files:
            self.open_gps_files(gps_files)
            print(f'open_gps_files time: {time.time() - start_time} seconds')

        if ri_files:
            self.open_ri_file(ri_files)

        if inf_files:
            self.open_inf_file(inf_files)

        if gpx_files:
            self.open_gpx_files(gpx_files)

    def open_pem_files(self, pem_files):
        """
        Action of opening a PEM file. Will not open a PEM file if it is already opened.
        :param pem_files: list: Filepaths for the PEM Files
        """

        def is_opened(pem_file):
            if isinstance(pem_file, PEMFile):
                pem_file = pem_file.filepath

            if self.pem_files:
                existing_filepaths = [os.path.abspath(file.filepath) for file in self.pem_files]
                if os.path.abspath(pem_file) in existing_filepaths:
                    self.window().statusBar().showMessage(f"{pem_file} is already opened", 2000)
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
            self.pg.setText(f"Opening {pem_file.filename}")

            pemInfoWidget = PEMFileInfoWidget()
            pemInfoWidget.refresh_tables_signal.connect(lambda: self.refresh_table(single_row=True))
            pemInfoWidget.blockSignals(True)

            # Create the PEMInfoWidget for the PEM file
            pem_widget = pemInfoWidget.open_file(pem_file, parent=self)
            # Change the current tab of this widget to the same as the opened ones
            pem_widget.tabs.setCurrentIndex(self.tab_num)
            pem_widget.tabs.currentChanged.connect(self.change_pem_info_tab)

            self.pem_files.append(pem_file)
            self.pem_info_widgets.append(pem_widget)
            self.stackedWidget.addWidget(pem_widget)
            pemInfoWidget.blockSignals(False)

        def sort_files():
            """
            Sort the PEM files (and their associated files/widget) in the main table.
            :return: None
            """
            if len(self.pem_files) > 0:
                print('Sorting the table\n')
                # Cannot simply sort the widgets in stackedWidget so they are removed and re-added.
                [self.stackedWidget.removeWidget(widget) for widget in self.pem_info_widgets]

                # Sorting the pem_files and pem_file_widgets using the pem_file basename as key.
                sorted_files = [(pem_file, piw) for pem_file, piw in
                                natsort.humansorted(zip(self.pem_files, self.pem_info_widgets),
                                key=lambda pair: pair[0].filename,
                                reverse=False)]

                self.pem_files = [pair[0] for pair in sorted_files]
                self.pem_info_widgets = [pair[1] for pair in sorted_files]
                # Re-adding the pem_info_widgets
                [self.stackedWidget.addWidget(widget) for widget in self.pem_info_widgets]
                # self.refresh_table()

        if not isinstance(pem_files, list):
            pem_files = [pem_files]

        # Block all table signals
        self.block_signals()
        self.allow_signals = False
        self.stackedWidget.show()
        self.pemInfoDockWidget.show()
        files_to_add = []
        # Start the progress bar
        self.start_pg(min=0, max=len(pem_files))
        count = 0

        if not self.autoSortLoopsCheckbox.isChecked():
            self.message.warning(self, 'Warning', "Loops aren't being sorted.")

        for pem_file in pem_files:
            # Create a PEMFile object if a filepath was passed
            if not isinstance(pem_file, PEMFile):
                print(f'Parsing {os.path.basename(pem_file)}')
                pem_file = self.pem_parser.parse(pem_file)

            # Check if the file is already opened in the table. Won't open if it is.
            if is_opened(pem_file):
                self.statusBar().showMessage(f"{pem_file.filename} is already opened", 2000)
            else:
                # Create the PEMInfoWidget
                add_info_widget(pem_file)
                # Add PEM files to a list to be added to the table all at once
                files_to_add.append(pem_file)

                # Fill CRS from the file if project CRS currently empty
                if self.systemCBox.currentText() == '' and self.datumCBox.currentText() == '':
                    crs = pem_file.get_crs()
                    if crs:
                        self.systemCBox.setCurrentIndex(self.gps_systems.index(crs['System']))
                        if crs['System'] == 'UTM':
                            hemis = 'North' if crs['North'] is True else 'South'
                            self.zoneCBox.setCurrentIndex(self.gps_zones.index(f"{crs['Zone']} {hemis}"))
                        self.datumCBox.setCurrentIndex(self.gps_datums.index(crs['Datum']))

                # Fill the shared header and station info if it's the first PEM File opened
                if len(self.pem_files) == 1:
                    if self.client_edit.text() == '':
                        self.client_edit.setText(pem_file.client)
                    if self.grid_edit.text() == '':
                        self.grid_edit.setText(pem_file.grid)
                    if self.loop_edit.text() == '':
                        self.loop_edit.setText(pem_file.loop_name)

                # Progress the progress bar
                count += 1
                self.pg.setValue(count)

        # Set the shared range boxes
        self.fill_share_range()
        # Add all files to the table at once for aesthetics.
        [self.add_pem_to_table(pem_file) for pem_file in files_to_add]

        if self.auto_sort_files_cbox.isChecked():
            sort_files()

        # Only refresh the table if there were already opened files
        if len(files_to_add) != len(self.pem_files):
            self.refresh_table()
        self.allow_signals = True
        self.enable_signals()
        self.pg.hide()
        self.table.resizeColumnsToContents()

    def open_gps_files(self, gps_files):
        """
        Adds GPS information from the gps_files to the PEMFile object
        :param gps_files: Text or gpx file(s) with GPS information in them
        """
        def read_gps_files(gps_files):  # Merges files together if there are multiple files
            if len(gps_files) > 1:
                merged_file = []
                for file in gps_files:
                    with open(file, mode='rt') as in_file:
                        contents = in_file.readlines()
                        merged_file.append(contents)
                return merged_file
            else:
                with open(gps_files[0], mode='rt') as in_file:
                    file = in_file.readlines()
                return file

        if len(gps_files) > 0:
            file = read_gps_files(gps_files)
            pem_info_widget = self.stackedWidget.currentWidget()
            current_tab = pem_info_widget.tabs.currentWidget()

            if current_tab == pem_info_widget.Station_GPS_Tab:
                line = SurveyLine(file)
                self.line_adder.add_df(line.get_line(sorted=True))
                self.line_adder.write_widget = pem_info_widget
            elif current_tab == pem_info_widget.Geometry_Tab:
                collar = BoreholeCollar(file)
                geom = BoreholeGeometry(file)
                if not collar.df.empty:
                    pem_info_widget.fill_gps_table(collar.df, pem_info_widget.collarGPSTable)
                if not geom.df.empty:
                    pem_info_widget.fill_gps_table(geom.df, pem_info_widget.geometryTable)
            elif current_tab == pem_info_widget.Loop_GPS_Tab:
                loop = TransmitterLoop(file)
                self.loop_adder.add_df(loop.get_loop(sorted=True))
                self.loop_adder.write_widget = pem_info_widget
            else:
                pass

    def open_ri_file(self, ri_files):
        """
        Adds RI file information to the associated PEMFile object. Only accepts 1 file.
        :param ri_file: Text file with step plot information in them
        """
        ri_file = ri_files[0]  # Filepath
        pem_info_widget = self.stackedWidget.currentWidget()
        pem_info_widget.open_ri_file(ri_file)

    def open_inf_file(self, inf_files):
        """
        Parses a .INF file to extract the CRS information in ti and set the CRS drop-down values.
        :param inf_files: List of .INF files. Will only use the first file.
        :return: None
        """
        inf_file = inf_files[0]  # Filepath, only accept the first one
        inf_parser = INFParser()
        crs = inf_parser.get_crs(inf_file)
        coord_sys = crs.get('System')
        coord_zone = crs.get('Zone')
        datum = crs.get('Datum')
        if 'NAD 1983' in datum:
            datum = 'NAD 1983'
        elif 'NAD 1927' in datum:
            datum = 'NAD 1927'
        self.systemCBox.setCurrentIndex(self.gps_systems.index(coord_sys))
        self.zoneCBox.setCurrentIndex(self.gps_zones.index(coord_zone))
        self.datumCBox.setCurrentIndex(self.gps_datums.index(datum))

    def open_gpx_files(self, gpx_files):
        if len(gpx_files) > 0:
            file = []
            zone, hemisphere = None, None
            for gpx_file in gpx_files:
                gps, zone, hemisphere = self.gpx_editor.get_utm(gpx_file)
                file += gps

            if zone and hemisphere:
                self.systemCBox.setCurrentIndex(self.gps_systems.index('UTM'))
                self.zoneCBox.setCurrentIndex(self.gps_zones.index(f"{zone} {hemisphere.title()}"))
                self.datumCBox.setCurrentIndex(self.gps_datums.index('WGS 1984'))

            pem_info_widget = self.stackedWidget.currentWidget()
            station_gps_tab = pem_info_widget.Station_GPS_Tab
            geometry_tab = pem_info_widget.Geometry_Tab
            loop_gps_tab = pem_info_widget.Loop_GPS_Tab
            current_tab = pem_info_widget.tabs.currentWidget()

            if station_gps_tab == current_tab:
                pem_info_widget.add_station_gps(file)
            elif geometry_tab == current_tab:
                # pem_info_widget.add_collar_gps(file)
                pem_info_widget.add_geometry(file)
            elif loop_gps_tab == current_tab:
                pem_info_widget.add_loop_gps(file)
            else:
                pass

    def open_in_text_editor(self):
        """
        Open the selected PEM File in a text editor
        """
        pem_files, rows = self.get_selected_pem_files()
        for pem_file in pem_files:
            os.startfile(pem_file.filepath)

    def open_file_dialog(self):
        """
        Open files through the file dialog
        """
        files = self.dialog.getOpenFileNames(self, 'Open File', filter='PEM files (*.pem);; All files(*.*)')
        if files[0] != '':
            for file in files[0]:
                if file.lower().endswith('.pem'):
                    self.open_files(file)
                else:
                    pass
        else:
            pass

    def block_signals(self):
        print('Blocking all signals')
        for thing in [self.table, self.client_edit, self.grid_edit, self.loop_edit, self.min_range_edit,
                      self.max_range_edit]:
            thing.blockSignals(True)

    def enable_signals(self):
        if self.allow_signals:
            print('Enabling all signals')
            for thing in [self.table, self.client_edit, self.grid_edit, self.loop_edit, self.min_range_edit,
                          self.max_range_edit]:
                thing.blockSignals(False)

    def start_pg(self, min=0, max=100):
        """
        Add the progress bar to the status bar and make it visible.
        :param min: Starting value of the progress bar, usually 0.
        :param max: Maximum value of the progress bar.
        :return: None
        """
        self.pg.setValue(min)
        self.pg.setMaximum(max)
        self.pg.setText('')
        self.window().statusBar().addPermanentWidget(self.pg)
        self.pg.show()

    def add_pem_to_table(self, pem_file):
        """
        Add a new row to the table and fill in the row with the PEM file's information.
        :param pem_file: PEMFile object
        :return: None
        """
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.fill_pem_row(pem_file, row)

    def fill_pem_row(self, pem_file, row):
        """
        Adds the information from a PEM file to the main table. Blocks the table signals while doing so.
        :param pem_file: PEMFile object
        :param row: int: row of the PEM file in the table
        :param special_cols_only: bool: Whether to only fill in the information from the non-editable columns (i.e.
        from the 'First Station' column to the end.
        :return: None
        """
        print(f"Adding {pem_file.filename} to table")
        self.table.blockSignals(True)

        info_widget = self.pem_info_widgets[row]

        # Get the information for each column
        row_info = [
            pem_file.filename,
            pem_file.date,
            self.client_edit.text() if self.share_client_cbox.isChecked() else pem_file.client,
            self.grid_edit.text() if self.share_grid_cbox.isChecked() else pem_file.grid,
            pem_file.line_name,
            self.loop_edit.text() if self.share_loop_cbox.isChecked() else pem_file.loop_name,
            pem_file.current,
            pem_file.coil_area,
            pem_file.data.Station.map(convert_station).min(),
            pem_file.data.Station.map(convert_station).max(),
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
            if i > self.table_columns.index('First\nStation'):
                item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
            self.table.setItem(row, i, item)

        self.color_table_row_text(row)
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
                    self.window().statusBar().showMessage(
                        f"Coil area changed from {old_value} to {new_value}", 2000)

        # Changing the name of a file
        if col == self.table_columns.index('File'):
            pem_file = self.pem_files[row]
            old_path = copy.deepcopy(pem_file.filepath)
            new_value = self.table.item(row, col).text()

            if new_value != os.path.basename(pem_file.filepath) and new_value:
                pem_file.old_filepath = old_path
                new_path = os.path.join(os.path.dirname(old_path), new_value)
                print(f"Renaming {os.path.basename(old_path)} to {os.path.basename(new_path)}")

                # Create a copy and delete the old one.
                copyfile(old_path, new_path)
                pem_file.filepath = new_path
                pem_file.filename = os.path.basename(new_path)
                os.remove(old_path)

                self.window().statusBar().showMessage(f"File renamed to {str(new_value)}", 2000)

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
            pem_file.filename,
            pem_file.date,
            pem_file.client,
            pem_file.grid,
            pem_file.line_name,
            pem_file.loop_name,
            pem_file.current,
            pem_file.coil_area,
            pem_file.data.Station.map(convert_station).min(),
            pem_file.data.Station.map(convert_station).max(),
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
        self.table.resizeColumnsToContents()

        if self.allow_signals:
            self.table.blockSignals(False)

    def color_table_row_text(self, row):
        """
        Color cells of the main table based on conditions. Ex: Red text if the PEM file isn't averaged.
        :param row: Row of the main table to check and color
        :return: None
        """

        def color_row(table, rowIndex, color, alpha=50):
            """
            Color an entire table row
            :param rowIndex: Int: Row of the table to color
            :param color: str: The desired color
            :return: None
            """
            table.blockSignals(True)
            color = QtGui.QColor(color)
            color.setAlpha(alpha)
            for j in range(table.columnCount()):
                table.item(rowIndex, j).setBackground(color)
            if self.allow_signals:
                table.blockSignals(False)

        self.table.blockSignals(True)
        average_col = self.table_columns.index('Averaged') + 1
        split_col = self.table_columns.index('Split') + 1
        suffix_col = self.table_columns.index('Suffix\nWarnings') + 1
        repeat_col = self.table_columns.index('Repeat\nStations') + 1
        pem_has_gps = self.pem_files[row].has_all_gps()

        for col in [average_col, split_col, suffix_col, repeat_col]:
            item = self.table.item(row, col)
            if item:
                value = item.text()
                if col == average_col:
                    if value.lower() == 'false':
                        item.setForeground(QtGui.QColor('red'))
                    else:
                        item.setForeground(QtGui.QColor('black'))
                elif col == split_col:
                    if value.lower() == 'false':
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
            color_row(self.table, row, 'magenta')

        if self.allow_signals:
            self.table.blockSignals(False)

    def refresh_table(self, single_row=False):
        """
        Deletes and re-populates the table rows with the new information. Blocks table signals while doing so.
        :return: None
        """
        if self.pem_files:
            self.table.blockSignals(True)
            if single_row:
                index = self.stackedWidget.currentIndex()
                print(f'Refreshing table row {index}')
                self.refresh_table_row(self.pem_files[index], index)
            else:
                print('Refreshing entire table')
                while self.table.rowCount() > 0:
                    self.table.removeRow(0)
                for pem_file in self.pem_files:
                    self.add_pem_to_table(pem_file)
            if self.allow_signals:
                self.table.blockSignals(False)
        else:
            pass

    def refresh_table_row(self, pem_file, row):
        """
        Clear the row and fill in the PEM file's information
        :param pem_file: PEMFile object
        :param row: Corresponding row of the PEM file in the main table
        :return: None
        """
        self.table.blockSignals(True)
        for i, column in enumerate(self.table_columns):
            item = QTableWidgetItem('')
            item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.table.setItem(row, i, item)
        self.fill_pem_row(pem_file, row)
        if self.allow_signals:
            self.table.blockSignals(False)

    def update_pem_file_from_table(self, pem_file, table_row, filepath=None):
        """
        Saves the pem file in memory using the information in the table.
        :param pem_file: PEM file object to save.
        :param table_row: Corresponding row of the PEM file in the main table.
        :param filepath: New filepath to be given to the PEM file. If None is given, it will use the filename in the
        table.
        :return: the PEM File object with updated information
        """

        def add_crs_tag():
            system = self.systemCBox.currentText()
            zone = ' Zone ' + self.zoneCBox.currentText() if self.zoneCBox.isEnabled() else ''
            datum = self.datumCBox.currentText()

            if any([system, zone, datum]):
                for note in reversed(pem_file.notes):
                    if '<GEN> CRS' in note:
                        del pem_file.notes[pem_file.notes.index(note)]

                pem_file.notes.append(f"<GEN> CRS: {system}{zone}, {datum}")

        if filepath is None:
            pem_file.filepath = os.path.join(os.path.split(pem_file.filepath)[0],
                                             self.table.item(table_row, self.table_columns.index('File')).text())
        else:
            pem_file.filepath = filepath

        add_crs_tag()
        pem_file.header['Date'] = self.table.item(table_row, self.table_columns.index('Date')).text()
        pem_file.header['Client'] = self.table.item(table_row, self.table_columns.index('Client')).text()
        pem_file.header['Grid'] = self.table.item(table_row, self.table_columns.index('Grid')).text()
        pem_file.header['LineHole'] = self.table.item(table_row, self.table_columns.index('Line/Hole')).text()
        pem_file.header['Loop'] = self.table.item(table_row, self.table_columns.index('Loop')).text()
        pem_file.tags['Current'] = self.table.item(table_row, self.table_columns.index('Current')).text()
        pem_file.loop_coords = self.stackedWidget.widget(table_row).get_loop_gps()

        if 'surface' in pem_file.survey_type.lower() or 'squid' in pem_file.survey_type.lower():
            pem_file.line_coords = self.stackedWidget.widget(table_row).get_station_gps()
        elif 'borehole' in pem_file.survey_type.lower():
            collar_gps = self.stackedWidget.widget(table_row).get_collar_gps()
            if not collar_gps:
                collar_gps = ['<P00>']
            segments = self.stackedWidget.widget(table_row).get_geometry_segments()
            pem_file.line_coords = [collar_gps] + segments

        return pem_file

    def clear_files(self):
        """
        Remove all files
        """
        while self.table.rowCount() > 0:
            self.table.removeRow(0)
        for i in reversed(range(self.stackedWidget.count())):
            widget = self.stackedWidget.widget(i)
            self.stackedWidget.removeWidget(widget)
        self.pem_files.clear()
        self.min_range_edit.setText('')
        self.max_range_edit.setText('')
        self.client_edit.setText('')
        self.grid_edit.setText('')
        self.loop_edit.setText('')
        self.window().statusBar().showMessage('All files removed', 2000)

    def backup_files(self):
        """
        Create a backup (.bak) file for each opened PEM file, saved in a backup folder.
        :return: None
        """
        if len(self.pem_files) > 0:
            for pem_file in self.pem_files:
                print(f"Backing up {os.path.basename(pem_file.filepath)}")
                pem_file = copy.deepcopy(pem_file)
                self.write_pem_file(pem_file, backup=True, tag='[B]', remove_old=False)
            self.window().statusBar().showMessage(f'Backup complete. Backed up {len(self.pem_files)} PEM files.', 2000)

    def remove_file(self, table_row):
        """
        Removes PEM files from the main table, along with any associated widgets.
        :param table_row: Table row of the PEM file.
        :return: None
        """
        self.table.removeRow(table_row)
        self.stackedWidget.removeWidget(self.stackedWidget.widget(table_row))
        del self.pem_files[table_row]
        del self.pem_info_widgets[table_row]

        if len(self.pem_files) == 0:
            self.stackedWidget.hide()
            self.pemInfoDockWidget.hide()
            self.client_edit.setText('')
            self.grid_edit.setText('')
            self.loop_edit.setText('')
            self.min_range_edit.setText('')
            self.max_range_edit.setText('')
            self.reset_crs()

    def remove_file_selection(self):
        pem_files, rows = self.get_selected_pem_files()
        for row in rows:
            self.remove_file(row)
        self.window().statusBar().showMessage(f"{len(rows)} files removed.", 2000)

    def get_selected_pem_files(self):
        """
        Return the corresponding pem_files and rows which are currently selected in the table
        :return: pem_file objects and corresponding row indexes
        """
        selected_pem_files = []
        rows = [model.row() for model in self.table.selectionModel().selectedRows()]
        rows.sort(reverse=True)
        for row in rows:
            selected_pem_files.append(self.pem_files[row])
        return selected_pem_files, rows

    def change_pem_info_tab(self, tab_num):
        """
        Slot: Change the tab for each pemInfoWidget to the same
        :param tab_num: tab index number to change to
        """
        self.tab_num = tab_num
        if len(self.pem_info_widgets) > 0:
            for widget in self.pem_info_widgets:
                widget.tabs.setCurrentIndex(self.tab_num)

    def write_pem_file(self, pem_file, dir=None, tag=None, backup=False, remove_old=False):
        """
        Action of saving a PEM file to a .PEM file.
        :param pem_file: PEMFile object to be saved.
        :param dir: Save file location. If None, is uses the file directory of the first PEM file as the default.
        :param tag: str: Tag to append to the file name ('[A]', '[S]', '[M]'...)
        :param backup: Bool: If true, will save file to a '[Backup]' folder.
        :param remove_old: Bool: If true, will delete the old file.
        :return: None
        """
        if dir is None:
            file_dir = os.path.split(pem_file.filepath)[0]
        else:
            file_dir = dir
        file_name = os.path.splitext(os.path.basename(pem_file.filepath))[0]
        extension = os.path.splitext(pem_file.filepath)[-1]

        # Create a backup folder if it doesn't exist, and use it as the new file dir.
        if backup is True:
            pem_file.old_filepath = os.path.join(file_dir, file_name + extension)
            if not os.path.exists(os.path.join(file_dir, '[Backup]')):
                print('Creating back up folder')
                os.mkdir(os.path.join(file_dir, '[Backup]'))
            file_dir = os.path.join(file_dir, '[Backup]')
            extension += '.bak'

        if tag and tag not in file_name:
            file_name += tag

        pem_file.filepath = os.path.join(file_dir, file_name + extension)
        print(f"Saving file {file_name}")
        save_file = self.serializer.serialize(pem_file)
        print(save_file, file=open(pem_file.filepath, 'w+'))

        # Remove the old filepath if the filename was changed.
        if pem_file.old_filepath and remove_old is True:
            print(f'Removing old file {os.path.basename(pem_file.old_filepath)}')
            try:
                os.remove(pem_file.old_filepath)
            except FileNotFoundError:
                print(f'File not found, assuming it was already removed')
            finally:
                pem_file.old_filepath = None

    def save_pem_files(self, all=False):
        """
        Save all selected PEM files.
        :param all: Bool: if True, saves all opened PEM files instead of only the selected ones.
        :return: None
        """
        if len(self.pem_files) > 0:
            if all is False:
                pem_files, rows = self.get_selected_pem_files()
            else:
                pem_files, rows = self.pem_files, range(self.table.rowCount())

            self.pg.setMaximum(len(pem_files))
            self.pg.show()
            self.window().statusBar().addPermanentWidget(self.pg)

            # Update all the PEM files in memory first.
            for row, pem_file in zip(rows, pem_files):
                pem_file = self.update_pem_file_from_table(pem_file, row)

            # This is split from the above for loop because the table is refreshed when pem_info_widget opens a file, /
            # and it would cause changes in the table to be ignored.
            count = 0
            for row, pem_file in zip(rows, pem_files):
                self.pg.setText(f"Saving {os.path.basename(pem_file.filepath)}")
                self.write_pem_file(pem_file)
                # Block the signals because it only updates the row corresponding to the current stackedWidget.
                self.pem_info_widgets[row].blockSignals(True)
                self.pem_info_widgets[row].open_file(pem_file, parent=self)  # Updates the PEMInfoWidget tables
                self.pem_info_widgets[row].blockSignals(False)
                count += 1
                self.pg.setValue(count)

            self.refresh_table()
            self.pg.hide()
            self.window().statusBar().showMessage(f'Save Complete. {len(pem_files)} file(s) saved.', 2000)

    def save_pem_file_as(self):
        """
        Saves a single PEM file to a selected location.
        :return: None
        """
        row = self.table.currentRow()
        default_path = os.path.split(self.pem_files[-1].filepath)[0]
        self.dialog.setFileMode(QFileDialog.ExistingFiles)
        self.dialog.setAcceptMode(QFileDialog.AcceptSave)
        self.dialog.setDirectory(default_path)
        self.window().statusBar().showMessage('Saving PEM files...')
        file_path = QFileDialog.getSaveFileName(self, '', default_path, 'PEM Files (*.PEM)')[0]  # Returns full filepath

        if file_path:
            pem_file = copy.deepcopy(self.pem_files[row])
            pem_file.filepath = file_path
            updated_file = self.update_pem_file_from_table(pem_file, row, filepath=file_path)

            self.write_pem_file(updated_file)
            self.window().statusBar().showMessage(
                'Save Complete. PEM file saved as {}'.format(os.path.basename(file_path)), 2000)
        else:
            self.window().statusBar().showMessage('Cancelled.', 2000)

    def save_as_kmz(self):
        """
        Saves all GPS from the opened PEM files as a KMZ file. Utilizes 'simplekml' module. Only works with NAD 83
        or WGS 84.
        :return: None
        """

        if len(self.pem_files) == 0:
            return

        if not any([pem_file.has_any_gps() for pem_file in self.pem_files]):
            self.message.information(self, 'Error', 'No GPS to show')
            return

        if self.datumCBox.currentText() == 'NAD 1927':
            self.message.information(self, 'Error', 'Incompatible datum. Must be either NAD 1983 or WGS 1984')
            return

        if any([self.systemCBox.currentText() == '', self.zoneCBox.currentText() == '',
                self.datumCBox.currentText() == '']):
            self.message.information(self, 'Error', 'GPS coordinate system information is incomplete')
            return

        kml = simplekml.Kml()
        pem_files = [pem_file for pem_file in self.pem_files if pem_file.has_any_gps()]

        zone = self.zoneCBox.currentText()
        zone_num = int(re.search('\d+', zone).group())
        north = True if 'n' in zone.lower() else False

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
            loop_gps = pem_file.get_loop_coords()
            loop_gps.append(loop_gps[0])
            loop_name = pem_file.header.get('Loop')
            if loop_gps and loop_gps not in loops:
                loops.append(loop_gps)
                loop_names.append(loop_name)
            if 'surface' in pem_file.survey_type.lower():
                line_gps = pem_file.get_line_coords()
                line_name = pem_file.header.get('LineHole')
                if line_gps and line_gps not in lines:
                    lines.append(line_gps)
                    line_names.append(line_name)
            else:
                borehole_projection = self.mpm.get_3D_borehole_projection(pem_file.get_collar_coords()[0], pem_file.get_hole_geometry(), 100)
                trace_gps = list(zip(borehole_projection[0], borehole_projection[1]))
                hole_name = pem_file.header.get('LineHole')
                if trace_gps and trace_gps not in traces:
                    traces.append(trace_gps)
                    hole_names.append(hole_name)

        # Creates KMZ objects for the loops.
        for loop_gps, name in zip(loops, loop_names):
            loop_coords = []
            for row in loop_gps:
                easting = int(float(row[0]))
                northing = int(float(row[1]))
                lat, lon = utm.to_latlon(easting, northing, zone_num, northern=north)
                loop_coords.append((lon, lat))

            ls = kml.newlinestring(name=name)
            ls.coords = loop_coords
            ls.extrude = 1
            ls.style = loop_style

        # Creates KMZ objects for the lines.
        for line_gps, name in zip(lines, line_names):
            line_coords = []
            folder = kml.newfolder(name=name)
            for row in line_gps:
                easting = int(float(row[0]))
                northing = int(float(row[1]))
                station = row[-1]
                lat, lon = utm.to_latlon(easting, northing, zone_num, northern=north)
                line_coords.append((lon, lat))
                new_point = folder.newpoint(name=f"{station}", coords=[(lon, lat)])
                new_point.style = station_style

            ls = folder.newlinestring(name=name)
            ls.coords = line_coords
            ls.extrude = 1
            ls.style = trace_style

        # Creates KMZ objects for the boreholes.
        for trace_gps, name in zip(traces, hole_names):
            trace_coords = []
            folder = kml.newfolder(name=name)
            for row in trace_gps:
                easting = int(float(row[0]))
                northing = int(float(row[1]))
                lat, lon = utm.to_latlon(easting, northing, zone_num, northern=north)
                trace_coords.append((lon, lat))

            collar = folder.newpoint(name=name, coords=[trace_coords[0]])
            collar.style = collar_style
            ls = folder.newlinestring(name=name)
            ls.coords = trace_coords
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
            self.window().statusBar().showMessage('Cancelled.', 2000)

    def save_as_xyz(self, selected_files=False):
        """
        Save the selected PEM files as XYZ files. Only for surface PEM files.
        :param selected_files: bool: Save selected files. False means all opened files will be saved.
        :return: None
        """
        xyz_serializer = XYZSerializer()
        if selected_files:
            pem_files, rows = self.get_selected_pem_files()
        else:
            pem_files, rows = self.pem_files, range(0, len(self.pem_files))

        if pem_files:
            default_path = os.path.split(self.pem_files[-1].filepath)[0]
            if __name__ == '__main__':
                file_dir = default_path
            else:
                file_dir = self.dialog.getExistingDirectory(self, '', default_path, QFileDialog.DontUseNativeDialog)

            if file_dir:
                for pem_file in pem_files:
                    if 'surface' in pem_file.survey_type.lower():
                        file_name = os.path.splitext(pem_file.filepath)[0] + '.xyz'
                        xyz_file = xyz_serializer.serialize_pem(pem_file)
                        with open(file_name, 'w+') as file:
                            file.write(xyz_file)
                        os.startfile(file_name)

    def export_pem_files(self, export_final=False, all=True):
        """
        Saves all PEM files to a desired location (keeps them opened) and removes any tags.
        :return: None
        """
        if all is False:
            pem_files, rows = self.get_selected_pem_files()
        else:
            pem_files, rows = self.pem_files, range(self.table.rowCount())

        self.window().statusBar().showMessage(f"Saving PEM {'file' if len(pem_files) == 1 else 'files'}...")
        if any([self.systemCBox.currentText()=='', self.zoneCBox.currentText()=='', self.datumCBox.currentText()=='']):
            response = self.message.question(self, 'No CRS',
                                                     'No CRS has been selected. '
                                                     'Do you wish to proceed with no CRS information?',
                                                     self.message.Yes | self.message.No)
            if response == self.message.No:
                return

        default_path = os.path.split(self.pem_files[-1].filepath)[0]
        self.dialog.setDirectory(default_path)
        file_dir = self.dialog.getExistingDirectory(self, '', default_path, QFileDialog.DontUseNativeDialog)

        if file_dir:
            for pem_file, row in zip(pem_files, rows):
                updated_file = self.update_pem_file_from_table(pem_file, row)
                file_name = os.path.splitext(os.path.basename(pem_file.filepath))[0]
                extension = os.path.splitext(pem_file.filepath)[-1]
                if export_final is True:
                    file_name = re.sub('_\d+', '', re.sub('\[-?\w\]', '', file_name))  # Removes underscore-dates and tags
                    if 'surface' in pem_file.survey_type.lower():
                        file_name = file_name.upper()
                        if file_name[0] == 'C':
                            file_name = file_name[1:]
                        if pem_file.is_averaged() and 'AV' not in file_name:
                            file_name = file_name + 'Av'

                updated_file.filepath = os.path.join(file_dir, file_name + extension)
                self.write_pem_file(updated_file, dir=file_dir, remove_old=False)
            self.refresh_table()
            self.window().statusBar().showMessage(
                f"Save complete. {len(pem_files)} PEM {'file' if len(pem_files) == 1 else 'files'} exported", 2000)
        else:
            self.window().statusBar().showMessage('Cancelled.', 2000)
            pass

    def export_all_gps(self):
        """
        Exports all GPS from all opened PEM files to separate CSV files. Creates folders for each loop.
        Doesn't repeat if a line/hole/loop has been done already.
        :return: None
        """
        if self.pem_files:
            system = self.systemCBox.currentText()
            zone = ' Zone ' + self.zoneCBox.currentText() if self.zoneCBox.isEnabled() else ''
            datum = self.datumCBox.currentText()

            loops = []
            lines = []
            collars = []

            default_path = os.path.dirname(self.pem_files[0].filepath)
            export_folder = self.dialog.getExistingDirectory(self, 'Select Destination Folder', default_path, QFileDialog.DontUseNativeDialog)
            if export_folder != '':
                for loop, pem_files in groupby(self.pem_files, key=lambda x: x.header.get('Loop')):
                    pem_files = list(pem_files)
                    try:
                        # Creates a new folder for each loop, where each CSV will be saved for that loop.
                        os.mkdir(os.path.join(export_folder, loop))
                    except FileExistsError:
                        pass
                    folder = os.path.join(export_folder, loop)
                    for pem_file in pem_files:
                        if pem_file.has_loop_gps():
                            loop = pem_file.get_loop_coords()
                            if loop not in loops:
                                loop_name = pem_file.header.get('Loop')
                                print(f"Creating CSV file for loop {loop_name}")
                                loops.append(loop)
                                csv_filepath = os.path.join(folder, loop_name + '.csv')
                                with open(csv_filepath, 'w') as csvfile:
                                    filewriter = csv.writer(csvfile, delimiter=',', lineterminator = '\n',
                                                            quotechar='"', quoting=csv.QUOTE_MINIMAL)
                                    filewriter.writerow([f"Loop {loop_name} - {system} {zone} {datum}"])
                                    filewriter.writerow(['Easting', 'Northing', 'Elevation'])
                                    for row in loop:
                                        filewriter.writerow([row[0], row[1], row[2]])

                        if pem_file.has_station_gps():
                            line = pem_file.get_station_coords()
                            if line not in lines:
                                line_name = pem_file.header.get('LineHole')
                                print(f"Creating CSV file for line {line_name}")
                                lines.append(line)
                                csv_filepath = os.path.join(folder, f"{line_name}.csv")
                                with open(csv_filepath, 'w') as csvfile:
                                    filewriter = csv.writer(csvfile, delimiter=',', lineterminator = '\n',
                                                            quotechar='"', quoting=csv.QUOTE_MINIMAL)
                                    filewriter.writerow([f"Line {line_name} - {system} {zone} {datum}"])
                                    filewriter.writerow(['Easting', 'Northing', 'Elevation', 'Station Number'])
                                    for row in line:
                                        filewriter.writerow([row[0], row[1], row[2], row[-1]])

                        if pem_file.has_collar_gps():
                            collar_coords = pem_file.get_collar_coords()
                            if collar_coords not in collars:
                                hole_name = pem_file.header.get('LineHole')
                                print(f"Creating CSV file for hole {hole_name}")
                                collars.append(collar_coords)
                                csv_filepath = os.path.join(folder, hole_name + '.csv')
                                with open(csv_filepath, 'w') as csvfile:
                                    filewriter = csv.writer(csvfile, delimiter=',', lineterminator = '\n',
                                                            quotechar='"', quoting=csv.QUOTE_MINIMAL)
                                    filewriter.writerow([f"Hole {hole_name} - {system} {zone} {datum}"])
                                    filewriter.writerow(['Easting', 'Northing', 'Elevation'])
                                    for row in collar_coords:
                                        filewriter.writerow([row[0], row[1], row[2]])
                self.window().statusBar().showMessage("Export complete.", 2000)
            else:
                self.window().statusBar().showMessage("No files to export.", 2000)

    def print_plots(self, selected_files=False):
        """
        Save the final plots as PDFs for the selected PEM files. If no PEM files are selected, it saves it for all open
        PEM files
        :param pem_files: List of PEMFile objects
        :param rows: Corresponding rows of the selected PEM files in order to link the RI file to the correct PEM file
        :return: None
        """

        def get_crs():
            crs = {'System': self.systemCBox.currentText(),
                   'Zone': self.zoneCBox.currentText(),
                   'Datum': self.datumCBox.currentText()}
            return crs

        def get_save_file():
            default_path = os.path.split(self.pem_files[-1].filepath)[0]
            self.dialog.setDirectory(default_path)
            if __name__ == '__main__':
                save_dir = os.path.join(
                    os.path.dirname(
                        os.path.dirname(
                            os.path.dirname(
                                os.path.abspath(__file__)))),
                    'sample_files/test')
            else:
                save_dir = os.path.splitext(QFileDialog.getSaveFileName(self, '', default_path)[0])[0]
                # Returns full filepath. For single PDF file
            print(f"Saving PDFs to {save_dir}")
            return save_dir

        if self.pem_files:

            if selected_files is True:
                input_pem_files, rows = self.get_selected_pem_files()
            else:
                input_pem_files = self.pem_files
                rows = range(0, len(input_pem_files))

            # Needs to be deepcopied or else it changes the pem files in self.pem_files
            pem_files = copy.deepcopy(input_pem_files)
            self.window().statusBar().showMessage('Saving plots...', 2000)

            plot_kwargs = {'ShareRange': self.share_range_checkbox.isChecked(),
                           'HideGaps': self.hide_gaps_checkbox.isChecked(),
                           'LoopAnnotations': self.show_loop_anno_checkbox.isChecked(),
                           'MovingLoop': self.movingLoopCBox.isChecked(),
                           'TitleBox': self.plan_map_options.title_box_cbox.isChecked(),
                           'Grid': self.plan_map_options.grid_cbox.isChecked(),
                           'ScaleBar': self.plan_map_options.scale_bar_cbox.isChecked(),
                           'NorthArrow': self.plan_map_options.north_arrow_cbox.isChecked(),
                           'Legend': self.plan_map_options.legend_cbox.isChecked(),
                           'DrawLoops': self.plan_map_options.draw_loops_cbox.isChecked(),
                           'DrawLines': self.plan_map_options.draw_lines_cbox.isChecked(),
                           'DrawHoleCollars': self.plan_map_options.draw_hole_collars_cbox.isChecked(),
                           'DrawHoleTraces': self.plan_map_options.draw_hole_traces_cbox.isChecked(),
                           'LoopLabels': self.plan_map_options.loop_labels_cbox.isChecked(),
                           'LineLabels': self.plan_map_options.line_labels_cbox.isChecked(),
                           'HoleCollarLabels': self.plan_map_options.hole_collar_labels_cbox.isChecked(),
                           'HoleDepthLabels': self.plan_map_options.hole_depth_labels_cbox.isChecked(),
                           'CRS': get_crs(),
                           'LINPlots': self.output_lin_cbox.isChecked(),
                           'LOGPlots': self.output_log_cbox.isChecked(),
                           'STEPPlots': self.output_step_cbox.isChecked(),
                           'PlanMap': self.output_plan_map_cbox.isChecked(),
                           'SectionPlot': self.output_section_cbox.isChecked(),
                           'LabelSectionTicks': self.label_section_depths_cbox.isChecked(),
                           'SectionDepth': self.section_depth_edit.text()}

            if self.share_range_checkbox.isChecked():
                try:
                    plot_kwargs['XMin'] = int(self.min_range_edit.text())
                except ValueError:
                    plot_kwargs['XMin'] = None
                try:
                    plot_kwargs['XMax'] = int(self.max_range_edit.text())
                except ValueError:
                    plot_kwargs['XMax'] = None
            else:
                plot_kwargs['XMin'] = None
                plot_kwargs['XMax'] = None

            ri_files = []
            for row, pem_file in zip(rows, pem_files):
                ri_files.append(self.pem_info_widgets[row].ri_file)
                self.update_pem_file_from_table(pem_file, row)
                if not pem_file.is_averaged():
                    self.file_editor.average(pem_file)
                if not pem_file.is_split():
                    self.file_editor.split_channels(pem_file)

            if self.output_plan_map_cbox.isChecked():
                if not all([plot_kwargs['CRS'].get('System'), plot_kwargs['CRS'].get('Datum')]):
                    response = self.message.question(self, 'No CRS',
                                                     'No CRS has been selected. '
                                                     'Do you wish to proceed without a plan map?',
                                                     self.message.Yes | self.message.No)
                    if response == self.message.No:
                        return

            save_dir = get_save_file()
            if save_dir:
                # PEM Files and RI files zipped together for when they get sorted
                try:
                    printer = PEMPrinter(save_dir, files=list(zip(pem_files, ri_files)), **plot_kwargs)
                    self.window().statusBar().addPermanentWidget(printer.pb)
                    printer.print_files()
                    printer.pb.hide()
                    self.window().statusBar().showMessage('Plots saved', 2000)
                except FileNotFoundError:
                    self.message.information(self, 'Error', f'{save_dir} does not exist')
                    printer.pb.hide()
                except IOError:
                    self.message.information(self, 'Error', f'{save_dir} is currently opened')
                    printer.pb.hide()
            else:
                self.window().statusBar().showMessage('Cancelled', 2000)

    def average_pem_data(self, all=False):
        """
        Average the data of each PEM File selected
        :param all: Bool: Whether or not to average all opened PEM files.
        :return: PEM File object with the data averaged
        """
        if not all:
            pem_files, rows = self.get_selected_pem_files()
        else:
            pem_files, rows = self.pem_files, range(self.table.rowCount())

        if not pem_files:
            return

        self.start_pg(min=0, max=len(pem_files))
        count = 0
        for pem_file, row in zip(pem_files, rows):
            if not pem_file.is_averaged():
                print(f"Averaging {os.path.basename(pem_file.filepath)}")
                self.pg.setText(f"Averaging {os.path.basename(pem_file.filepath)}")
                # Save a backup of the un-averaged file first
                if self.auto_create_backup_files_cbox.isChecked():
                    self.write_pem_file(copy.deepcopy(pem_file), backup=True, tag='[-A]', remove_old=False)
                pem_file = self.file_editor.average(pem_file)
                self.pem_info_widgets[row].open_file(pem_file, parent=self)
                self.refresh_table_row(pem_file, row)
                count += 1
                self.pg.setValue(count)
        self.pg.hide()

    def split_pem_channels(self, pem_files=[], all=False):
        """
        Removes the on-time channels of each selected PEM File
        :param all: bool: Whether or not to split channels for all opened PEM files or only selected ones.
        :return: None
        """

        if not pem_files:
            if not all:
                pem_files, rows = self.get_selected_pem_files()
            else:
                pem_files, rows = self.pem_files, range(self.table.rowCount())
        else:
            if not isinstance(pem_files, list):
                pem_files = [pem_files]
            pem_files, rows = pem_files, [self.pem_files.index(pem_file) for pem_file in pem_files]

        if not pem_files:
            return

        self.start_pg(min=0, max=len(pem_files))
        count = 0
        for pem_file, row in zip(pem_files, rows):
            if not pem_file.is_split():
                print(f"Splitting channels for {os.path.basename(pem_file.filepath)}")
                self.pg.setText(f"Splitting channels for {os.path.basename(pem_file.filepath)}")
                if self.auto_create_backup_files_cbox.isChecked():
                    self.write_pem_file(copy.deepcopy(pem_file), backup=True, tag='[-S]', remove_old=False)
                pem_file = self.file_editor.split_channels(pem_file)
                self.pem_info_widgets[row].open_file(pem_file, parent=self)
                self.refresh_table_row(pem_file, row)
                count += 1
                self.pg.setValue(count)
        self.pg.hide()

    def scale_pem_coil_area(self, coil_area=None, all=False):
        """
        Scales the data according to the coil area change
        :param coil_area: int:  coil area to scale to
        :param all: bool: Whether or not to scale coil area for all opened PEM files or only selected ones.
        """
        if not coil_area:
            coil_area, okPressed = QInputDialog.getInt(self, "Set Coil Areas", "Coil Area:")
            if not okPressed:
                return

        if not all:
            pem_files, rows = self.get_selected_pem_files()
        else:
            pem_files, rows = self.pem_files, range(self.table.rowCount())

        for pem_file, row in zip(pem_files, rows):
            print(f"Performing coil area change for {pem_file.filename}")
            coil_column = self.table_columns.index('Coil Area')
            pem_file = self.file_editor.scale_coil_area(pem_file, coil_area)
            self.table.item(row, coil_column).setText(str(coil_area))
            self.refresh_table_row(pem_file, row)

    def scale_pem_current(self, all=False):
        """
        Scale the data by current for the selected PEM Files
        :param all: Bool: if True, uses all opened PEM files instead of just the selected ones.
        :return: None
        """
        current, okPressed = QInputDialog.getDouble(self, "Scale Current", "Current:")
        if okPressed:
            if not all:
                pem_files, rows = self.get_selected_pem_files()
            else:
                pem_files, rows = self.pem_files, range(self.table.rowCount())
            for pem_file, row in zip(pem_files, rows):
                coil_column = self.table_columns.index('Current')
                pem_file = self.file_editor.scale_current(pem_file, current)
                self.table.item(row, coil_column).setText(str(current))
                self.refresh_table_row(pem_file, row)

    def reverse_all_data(self, comp):
        """
        Reverse the polarity of all data of a given component for all opened PEM files.
        :param comp: Z, X, or Y component
        :return: None
        """
        if len(self.pem_files) > 0:
            for pem_file, pem_info_widget in zip(self.pem_files, self.pem_info_widgets):
                pem_info_widget.reverse_polarity(component=comp)
                pem_file = pem_info_widget.pem_file

    def merge_pem_files(self, pem_files):
        """
        Action of merging multiple PEM files.
        :param pem_files: List of PEMFile objects
        :return: Single merged PEMFile object
        """

        print(f"Merging {', '.join([os.path.basename(pem_file.filepath) for pem_file in pem_files])}")

        if isinstance(pem_files, list) and len(pem_files) > 1:
            # Data merging section
            currents = [float(pem_file.tags.get('Current')) for pem_file in pem_files]
            coil_areas = [float(pem_file.header.get('CoilArea')) for pem_file in pem_files]

            # If any currents are different
            if not all([current == currents[0] for current in currents]):
                response = self.message.question(self, 'Warning - Unequal Current',
                                                 f"{', '.join([os.path.basename(pem_file.filepath) for pem_file in pem_files])} do not have the same current. Proceed with merging anyway?",
                                                 self.message.Yes | self.message.No)
                if response == self.message.No:
                    self.window().statusBar().showMessage('Aborted.', 2000)
                    return

            # If any coil areas are different
            if not all([coil_area == coil_areas[0] for coil_area in coil_areas]):
                response = self.message.question(self, 'Warning - Unequal Coil Areas',
                                                 f"{', '.join([os.path.basename(pem_file.filepath) for pem_file in pem_files])} do not have the same coil area. Proceed with merging anyway?",
                                                 self.message.Yes | self.message.No)
                if response == self.message.No:
                    self.window().statusBar().showMessage('Aborted.', 2000)
                    return

            # If the files aren't all split or un-split
            if any([pem_file.is_split() for pem_file in pem_files]) and any(
                    [not pem_file.is_split() for pem_file in pem_files]):
                response = self.message.question(self, 'Merge PEM Files',
                                                 'There is a mix of channel splitting in the selected files. '
                                                 'Would you like to split the unsplit file(s) and proceed with merging?',
                                                 self.message.Yes | self.message.No)
                if response == self.message.Yes:
                    for pem_file in pem_files:
                        self.split_pem_channels(pem_file)
                else:
                    return

            merged_pem = copy.deepcopy(pem_files[0])
            merged_pem.data = list(chain.from_iterable([pem_file.data for pem_file in pem_files]))
            merged_pem.header['NumReadings'] = str(sum(
                list(chain([int(pem_file.header.get('NumReadings')) for pem_file in pem_files]))))
            merged_pem.is_merged = True

            dir = os.path.split(merged_pem.filepath)[0]
            extension = os.path.splitext(merged_pem.filepath)[-1]
            file_name = os.path.splitext(os.path.basename(merged_pem.filepath))[0]

            merged_pem.filepath = os.path.join(dir, file_name + extension)
            return merged_pem

    def merge_pem_files_selection(self):
        pem_files, rows = self.get_selected_pem_files()
        if len(pem_files) > 1:
            # First update the PEM Files from the table
            for pem_file, row in zip(pem_files, rows):
                self.update_pem_file_from_table(pem_file, row)
            merged_pem = self.merge_pem_files(pem_files)
            if merged_pem:
                # Backup and remove the old files:
                for row in reversed(rows):
                    pem_file = copy.deepcopy(self.pem_files[row])
                    if self.auto_create_backup_files_cbox.isChecked():
                        self.write_pem_file(pem_file, tag='[-M]', backup=True,
                                            remove_old=self.delete_merged_files_cbox.isChecked())
                    if self.delete_merged_files_cbox.isChecked():
                        self.remove_file(row)
                self.write_pem_file(merged_pem, tag='[M]', remove_old=False)
                self.open_pem_files(merged_pem)
        else:
            self.message.information(None, 'Error', 'Must select multiple PEM Files')

    def auto_merge_pem_files(self):
        """
        Automatically merge PEM files. Groups surface files up by loop name first, then by line name, then does the merge.
        :return: None
        """
        if len(self.pem_files) > 0:
            files_to_open = []
            # self.spinner.start()
            # self.spinner.show()

            # time.sleep(.1)
            # updated_pem_files = [self.update_pem_file_from_table(pem_file, row) for pem_file, row in
            #                      zip(copy.deepcopy(self.pem_files), range(self.table.rowCount()))]
            updated_pem_files = [self.update_pem_file_from_table(pem_file, row) for pem_file, row in
                                                      zip(self.pem_files, range(self.table.rowCount()))]
            bh_files = [pem_file for pem_file in updated_pem_files if 'borehole' in pem_file.survey_type.lower()]
            sf_files = [pem_file for pem_file in updated_pem_files if 'surface' in pem_file.survey_type.lower() or 'squid' in pem_file.survey_type.lower()]

            # Surface lines
            for loop, pem_files in groupby(sf_files, key=lambda x: x.header.get('Loop')):
                print(f"Auto merging loop {loop}")
                pem_files = list(pem_files)
                if any([pem_file.is_split() for pem_file in pem_files]) and any(
                        [not pem_file.is_split() for pem_file in pem_files]):
                    response = self.message.question(self, 'Merge PEM Files',
                                                     'There is a mix of channel splitting in the selected files. '
                                                     'Would you like to split the unsplit file(s) and proceed with merging?',
                                                     self.message.Yes | self.message.No)
                    if response == self.message.Yes:
                        self.split_pem_channels(pem_files, all=False)
                    else:
                        return

                for line, pem_files in groupby(pem_files, key=lambda x: x.header.get('LineHole')):
                    pem_files = list(pem_files)
                    if len(pem_files) > 1:
                        print(f"Auto merging line {line}: {[os.path.basename(pem_file.filepath) for pem_file in pem_files]}")
                        rows = [updated_pem_files.index(pem_file) for pem_file in pem_files]
                        merged_pem = self.merge_pem_files(pem_files)
                        if merged_pem:
                            # Backup and remove the old files:
                            for row in reversed(rows):
                                pem_file = updated_pem_files[row]
                                if self.auto_create_backup_files_cbox.isChecked():
                                    self.write_pem_file(copy.deepcopy(pem_file), tag='[-M]', backup=True,
                                                        remove_old=self.delete_merged_files_cbox.isChecked())
                                if self.delete_merged_files_cbox.isChecked():
                                    self.remove_file(row)
                                    updated_pem_files.pop(row)
                            self.write_pem_file(merged_pem, tag='[M]')
                            # Open the files later to not deal with changes in index when files are opened.
                            files_to_open.append(merged_pem)

            # Boreholes
            for loop, pem_files in groupby(bh_files, key=lambda x: x.header.get('Loop')):
                print(f"Loop {loop}")
                pem_files = list(pem_files)
                if any([pem_file.is_split() for pem_file in pem_files]) and any(
                        [not pem_file.is_split() for pem_file in pem_files]):
                    response = self.message.question(self, 'Merge PEM Files',
                                                     'There is a mix of channel splitting in the selected files. '
                                                     'Would you like to split the unsplit file(s) and proceed with merging?',
                                                     self.message.Yes | self.message.No)
                    if response == self.message.Yes:
                        self.split_pem_channels(pem_files, all=False)
                    else:
                        return

                for hole, pem_files in groupby(pem_files, key=lambda x: x.header.get('LineHole')):
                    print(f"Hole {hole}")
                    pem_files = sorted(list(pem_files), key=lambda x: x.get_components())
                    for components, pem_files in groupby(pem_files, key=lambda x: x.get_components()):
                        print(f"Components {components}")
                        pem_files = list(pem_files)
                        if len(pem_files) > 1:
                            print(f"Auto merging hole {hole}: {[os.path.basename(pem_file.filepath) for pem_file in pem_files]}")
                            rows = [updated_pem_files.index(pem_file) for pem_file in pem_files]
                            merged_pem = self.merge_pem_files(pem_files)
                            if merged_pem:
                                # Backup and remove the old files:
                                for row in reversed(rows):
                                    pem_file = updated_pem_files[row]
                                    if self.auto_create_backup_files_cbox.isChecked():
                                        self.write_pem_file(copy.deepcopy(pem_file), tag='[-M]', backup=True,
                                                            remove_old=self.delete_merged_files_cbox.isChecked())
                                    if self.delete_merged_files_cbox.isChecked():
                                        self.remove_file(row)
                                        updated_pem_files.pop(row)
                                self.write_pem_file(merged_pem, tag='[M]')
                                # Open the files later to not deal with changes in index when files are opened.
                                files_to_open.append(merged_pem)
            self.open_pem_files(files_to_open)
            # self.spinner.stop()

    # def reset_crs(self):
    #     """
    #     Reset all CRS drop-down menus.
    #     :return: None
    #     """
    #     self.systemCBox.setCurrentIndex(0)
    #     self.zoneCBox.setCurrentIndex(0)
    #     self.datumCBox.setCurrentIndex(0)

    # def populate_gps_boxes(self):
    #     """
    #     Adds the drop-down options of each CRS drop-down menu.
    #     :return: None
    #     """
    #     for system in self.gps_systems:
    #         self.systemCBox.addItem(system)
    #     for zone in self.gps_zones:
    #         self.zoneCBox.addItem(zone)
    #     for datum in self.gps_datums:
    #         self.datumCBox.addItem(datum)

    # def create_main_table(self):
    #     """
    #     Creates the table (self.table) when the editor is first opened
    #     :return: None
    #     """
    #     self.table_columns = ['File', 'Date', 'Client', 'Grid', 'Line/Hole', 'Loop', 'Current', 'Coil Area',
    #                           'First\nStation',
    #                           'Last\nStation', 'Averaged', 'Split', 'Suffix\nWarnings', 'Repeat\nStations']
    #     self.table.setColumnCount(len(self.table_columns))
    #     self.table.setHorizontalHeaderLabels(self.table_columns)
    #     self.table.setSizeAdjustPolicy(
    #         QAbstractScrollArea.AdjustToContents)

    def sort_all_station_gps(self):
        """
        Sorts the station GPS (based on positions only) of all opened PEM files.
        :return: None
        """
        if self.pem_files:
            for i in range(self.stackedWidget.count()):
                widget = self.stackedWidget.widget(i)
                if widget.station_gps:
                    widget.fill_station_table(widget.station_gps.get_sorted_gps(widget.get_station_gps()))
                else:
                    pass
            self.window().statusBar().showMessage('All stations have been sorted', 2000)

    def sort_all_loop_gps(self):
        """
        Sorts the loop GPS (counter-clockwise) of all opened PEM files.
        :return: None
        """
        if self.pem_files:
            for i in range(self.stackedWidget.count()):
                widget = self.stackedWidget.widget(i)
                if widget.loop_gps:
                    widget.fill_loop_table(widget.loop_gps.get_sorted_gps(widget.get_loop_gps()))
                else:
                    pass
            self.window().statusBar().showMessage('All loops have been sorted', 2000)

    # def fill_share_header(self):
    #     """
    #     Uses the client, grid, and loop information from the first PEM file opened to be used as the basis
    #     to be used on all opened PEM files if the toggle is on.
    #     :return: None
    #     """
    #     if self.pem_files:
    #         self.client_edit.setText(self.pem_files[0].header['Client'])
    #         self.grid_edit.setText(self.pem_files[0].header['Grid'])
    #         self.loop_edit.setText(self.pem_files[0].header['Loop'])
    #         self.update_table()
    #     else:
    #         self.client_edit.setText('')
    #         self.grid_edit.setText('')
    #         self.loop_edit.setText('')

    def fill_share_range(self):
        """
        Calculates the minimum and maximum station numbers between all opened PEM files, and uses this to fill out the
        shared range values
        :return: None
        """
        if self.pem_files:
            min_stations = [f.data.Station.map(convert_station).min() for f in self.pem_files]
            max_stations = [f.data.Station.map(convert_station).max() for f in self.pem_files]
            min_range, max_range = min(min_stations), max(max_stations)
            self.min_range_edit.setText(str(min_range))
            self.max_range_edit.setText(str(max_range))
        else:
            self.min_range_edit.setText('')
            self.max_range_edit.setText('')

    def share_loop(self):
        """
        Share the loop GPS of one file with all other opened PEM files.
        :return: None
        """
        selected_widget = self.pem_info_widgets[self.table.currentRow()]
        selected_widget_loop = selected_widget.get_loop_gps()
        if selected_widget_loop:
            for widget in self.pem_info_widgets:
                widget.fill_loop_table(selected_widget_loop)

    def share_collar(self):
        """
        Share the collar GPS of one file with all other opened PEM files. Will only do so for borehole files.
        :return: None
        """
        selected_widget = self.pem_info_widgets[self.table.currentRow()]
        selected_widget_collar = [selected_widget.get_collar_gps()]
        if selected_widget_collar:
            for widget in list(filter(lambda x: 'borehole' in x.pem_file.survey_type.lower(), self.pem_info_widgets)):
                widget.fill_collar_gps_table(selected_widget_collar)

    def share_segments(self):
        """
        Share the segments of one file with all other opened PEM files. Will only do so for borehole files.
        :return: None
        """
        selected_widget = self.pem_info_widgets[self.table.currentRow()]
        selected_widget_geometry = selected_widget.get_geometry_segments()
        if selected_widget_geometry:
            for widget in list(filter(lambda x: 'borehole' in x.pem_file.survey_type.lower(), self.pem_info_widgets)):
                widget.fill_geometry_table(selected_widget_geometry)

    def share_station_gps(self):
        """
        Share the station GPS of one file with all other opened PEM files. Will only do so for surface files.
        :return: None
        """
        selected_widget = self.pem_info_widgets[self.table.currentRow()]
        selected_widget_station_gps = selected_widget.get_station_gps()
        if selected_widget_station_gps:
            for widget in list(filter(lambda x: 'surface' in x.pem_file.survey_type.lower()
                                            or 'squid' in x.pem_file.survey_type.lower(), self.pem_info_widgets)):
                widget.fill_station_table(selected_widget_station_gps)

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
                survey_type = pem_file.survey_type.lower()
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

                pem_file.header['LineHole'] = new_name
                name_item = QTableWidgetItem(new_name)
                name_item.setTextAlignment(QtCore.Qt.AlignCenter)
                self.table.setItem(row, line_name_column, name_item)
            self.refresh_table()

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
                self.refresh_table_row(self.pem_files[i], i)
            # self.refresh_table()
            self.window().statusBar().showMessage(f'{num_repeat_stations} repeat station(s) automatically renamed.',
                                                  2000)

    # def toggle_share_client(self):
    #     if self.share_client_cbox.isChecked():
    #         self.client_edit.setEnabled(True)
    #         self.refresh_table()
    #     else:
    #         self.client_edit.setEnabled(False)
    #         self.refresh_table()
    #
    # def toggle_share_grid(self):
    #     if self.share_grid_cbox.isChecked():
    #         self.grid_edit.setEnabled(True)
    #         self.refresh_table()
    #     else:
    #         self.grid_edit.setEnabled(False)
    #         self.refresh_table()
    #
    # def toggle_share_loop(self):
    #     if self.share_loop_cbox.isChecked():
    #         self.loop_edit.setEnabled(True)
    #         self.refresh_table()
    #     else:
    #         self.loop_edit.setEnabled(False)
    #         self.refresh_table()
    #
    # def toggle_share_range(self):
    #     if self.share_range_checkbox.isChecked():
    #         self.min_range_edit.setEnabled(True)
    #         self.max_range_edit.setEnabled(True)
    #         self.refresh_table()
    #     else:
    #         self.min_range_edit.setEnabled(False)
    #         self.max_range_edit.setEnabled(False)
    #         self.refresh_table()
    #
    # def toggle_sort_loop(self, widget):
    #     if self.autoSortLoopsCheckbox.isChecked():
    #         widget.fill_loop_table(widget.loop_gps.get_sorted_gps())
    #     else:
    #         widget.fill_loop_table(widget.loop_gps.get_gps())
    #
    # def toggle_zone_box(self):
    #     if self.systemCBox.currentText() == 'UTM':
    #         self.zoneCBox.setEnabled(True)
    #     else:
    #         self.zoneCBox.setEnabled(False)

    def calc_mag_declination(self, pem_file):
        """
        Pop-up window with the magnetic declination information for a coordinate found in a given PEM File. Converts
        the first coordinates found into lat lon. Must have GPS information in order to conver to lat lon.
        :param pem_file: PEMFile object
        :return: None
        """

        def copy_text(str_value):
            cb = QtGui.QApplication.clipboard()
            cb.clear(mode=cb.Clipboard)
            cb.setText(str_value, mode=cb.Clipboard)
            self.mag_win.statusBar().showMessage(f"{str_value} copied to clipboard", 1000)

        if len(self.pem_files) == 0:
            return

        if self.datumCBox.currentText() == 'NAD 1927':
            self.message.information(self, 'Error', 'Incompatible datum. Must be either NAD 1983 or WGS 1984')
            return

        if any([self.systemCBox.currentText() == '', self.zoneCBox.currentText() == '',
                self.datumCBox.currentText() == '']):
            self.message.information(self, 'Error', 'GPS coordinate system information is incomplete')
            return

        zone = self.zoneCBox.currentText()
        zone_num = int(re.search('\d+', zone).group())
        north = True if 'n' in zone.lower() else False

        if pem_file.has_collar_gps():
            coords = pem_file.get_collar_coords()
        elif pem_file.has_loop_gps():
            coords = pem_file.get_loop_coords()
        elif pem_file.has_line_coords():
            coords = pem_file.get_line_coords()
        else:
            self.message.information(self, 'Error', 'No GPS')
            return

        easting, northing, elevation = int(float(coords[0][0])), int(float(coords[0][1])), int(float(coords[0][2]))
        lat, lon = utm.to_latlon(easting, northing, zone_num, northern=north)

        try:
            gm = geomag.GeoMag()
            mag = gm.GeoMag(lat, lon, elevation)

        except Exception as e:
            self.error.showMessage(f"The following error occured whilst calculating the magnetic declination: {str(e)}")

        else:
            self.mag_win = QMainWindow()
            mag_widget = QWidget()
            self.mag_win.setWindowTitle('Magnetic Declination')
            self.mag_win.setWindowIcon(QtGui.QIcon(os.path.join(icons_path, 'mag_field.png')))
            self.mag_win.setGeometry(600, 300, 300, 200)
            self.mag_win.statusBar().showMessage('', 10)
            layout = QGridLayout()
            layout.setColumnStretch(1, 4)
            layout.setColumnStretch(2, 4)
            mag_widget.setLayout(layout)
            self.mag_win.setCentralWidget(mag_widget)
            layout.addWidget(QLabel(f'Latitude (°)'), 0, 0)
            layout.addWidget(QLabel(f'Longitude (°)'), 1, 0)
            layout.addWidget(QLabel('Declination (°)'), 2, 0)
            layout.addWidget(QLabel('Inclination (°)'), 3, 0)
            layout.addWidget(QLabel('Total Field (nT)'), 4, 0)

            lat_edit = QPushButton(f"{lat:.4f}")
            lat_edit.clicked.connect(lambda: copy_text(lat_edit.text()))
            lon_edit = QPushButton(f"{lon:.4f}")
            lon_edit.clicked.connect(lambda: copy_text(lon_edit.text()))
            dec_edit = QPushButton(f"{mag.dec:.2f}")
            dec_edit.clicked.connect(lambda: copy_text(dec_edit.text()))
            inc_edit = QPushButton(f"{mag.dip:.2f}")
            inc_edit.clicked.connect(lambda: copy_text(inc_edit.text()))
            tf_edit = QPushButton(f"{mag.ti:.2f}")
            tf_edit.clicked.connect(lambda: copy_text(tf_edit.text()))

            layout.addWidget(lat_edit, 0, 2)
            layout.addWidget(lon_edit, 1, 2)
            layout.addWidget(dec_edit, 2, 2)
            layout.addWidget(inc_edit, 3, 2)
            layout.addWidget(tf_edit, 4, 2)

            self.mag_win.show()

            return mag.dec

    def extract_stations(self):
        """
        Opens the PEMFileSplitter window, which will allow selected stations to be saved as a new PEM file.
        :return: None
        """
        pem_file, row = self.get_selected_pem_files()
        self.pem_file_splitter = PEMFileSplitter(pem_file[0], parent=self)

    def show_plan_map(self):
        """
        Opens the interactive plan Map window
        :return: None
        """
        if self.pem_files:
            zone = self.zoneCBox.currentText()
            datum = self.datumCBox.currentText()
            if not zone:
                self.message.information(self, 'UTM Zone Error', f"UTM zone cannot be empty.")
            elif not datum:
                self.message.information(self, 'Datum Error', f"Datum cannot be empty.")
            elif datum == 'NAD 1927':
                self.message.information(self, 'Datum Error', f"Datum cannot be NAD 1927.")
            else:
                self.map = FoliumMap(self.pem_files, zone).get_map()
                self.map.show()
        else:
            self.window().statusBar().showMessage('No PEM files are opened.', 2000)

    def show_map_3d_viewer(self):
        """
        Opens the 3D Map Viewer window
        :return: None
        """
        self.map_viewer_3d = Map3DViewer(self.pem_files, parent=self)
        self.map_viewer_3d.show()

    def show_section_3d_viewer(self):
        """
        Opens the 3D Borehole Section Viewer window
        :return: None
        """
        pem_file, row = self.get_selected_pem_files()
        if 'borehole' in pem_file[0].survey_type.lower():
            self.section_3d_viewer = Section3DViewer(pem_file[0], parent=self)
            self.section_3d_viewer.show()
        else:
            self.statusBar().showMessage('Invalid survey type', 2000)

    def show_contour_map_viewer(self):
        """
        Opens the Contour Map Viewer window
        :return: None
        """
        if len(self.pem_files) > 1:
            pem_files = copy.deepcopy(self.pem_files)
            try:
                self.contour_map_viewer = ContourMapViewer(pem_files, parent=self)
            except TypeError as e:
                self.error.setWindowTitle('Error')
                self.error.showMessage(f"The following error occured while creating the contour map: {str(e)}")
                return
            except ValueError as e:
                self.error.setWindowTitle('Error')
                self.error.showMessage(f"The following error occured while creating the contour map: {str(e)}")
            else:
                self.contour_map_viewer.show()
        else:
            self.window().statusBar().showMessage("Must have more than 1 surface PEM file open", 2000)

    def show_loop_planner(self):
        """
        Opens the Loop Planner window.
        :return: None
        """
        self.loop_planner = LoopPlanner()
        self.loop_planner.show()

    def show_grid_planner(self):
        """
        Opens the Grid Planner window.
        :return: None
        """
        self.grid_planner = GridPlanner()
        self.grid_planner.show()

    def batch_rename(self, type):
        """
        Opens the BatchNameEditor for renaming multiple file names and/or line/hole names.
        :param type: File names or line/hole names
        :return: None
        """

        def rename_pem_files():

            if len(self.batch_name_editor.pem_files) > 0:
                self.batch_name_editor.accept_changes()
                for i, row in enumerate(rows):
                    self.pem_files[row] = self.batch_name_editor.pem_files[i]
                self.refresh_table()

        pem_files, rows = self.get_selected_pem_files()
        if not pem_files:
            pem_files, rows = self.pem_files, range(self.table.rowCount())

        self.batch_name_editor = BatchNameEditor(pem_files, type=type)
        self.batch_name_editor.buttonBox.accepted.connect(rename_pem_files)
        self.batch_name_editor.acceptChangesSignal.connect(rename_pem_files)
        self.batch_name_editor.buttonBox.rejected.connect(self.batch_name_editor.close)
        self.batch_name_editor.show()

    def import_ri_files(self):
        """
        Opens BatchRIImporter for bulk importing RI files.
        :return: None
        """
        def open_ri_files():
            ri_filepaths = self.ri_importer.ri_files
            if len(ri_filepaths) > 0:
                for i, ri_filepath in enumerate(ri_filepaths):
                    self.pem_info_widgets[i].open_ri_file(ri_filepath)
                self.window().statusBar().showMessage(f"Imported {str(len(ri_filepaths))} RI files", 2000)
            else:
                pass

        self.ri_importer.open_pem_files(self.pem_files)
        self.ri_importer.show()
        self.ri_importer.acceptImportSignal.connect(open_ri_files)

    def timebase_freqency_converter(self):
        """
        Converts timebase to frequency and vise-versa.
        :return: None
        """

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

        self.freq_win = QWidget()
        self.freq_win.setWindowTitle('Timebase / Frequency Converter')
        self.freq_win.setWindowIcon(QtGui.QIcon(os.path.join(icons_path, 'freq_timebase_calc.png')))
        layout = QGridLayout()
        self.freq_win.setLayout(layout)

        # def keyPressEvent(self, e):
        #     if e.key() == QtCore.Qt.Key_Escape:
        #         self.close()

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

        self.freq_win.show()


class BatchNameEditor(QWidget, Ui_LineNameEditorWidget):
    """
    Class to bulk rename PEM File line/hole names or file names.
    """
    acceptChangesSignal = QtCore.pyqtSignal()

    def __init__(self, pem_files, type=None, parent=None):
        super().__init__()
        self.parent = parent
        self.setupUi(self)
        self.pem_files = pem_files
        self.type = type

        if self.type == 'Line':
            self.setWindowTitle('Rename lines/holes names')
        else:
            self.setWindowTitle('Rename files names')

        self.table_columns = ['Old Name', 'New Name']
        self.addEdit.setText('[n]')
        self.addEdit.textEdited.connect(self.update_table)
        self.removeEdit.textEdited.connect(self.update_table)
        self.buttonBox.rejected.connect(self.close)
        self.buttonBox.accepted.connect(self.acceptChangesSignal.emit)
        self.create_table()

    def keyPressEvent(self, e):
        if e.key() == QtCore.Qt.Key_Escape:
            self.close()
        elif e.key() == QtCore.Qt.Key_Return:
            self.acceptChangesSignal.emit()

    def create_table(self):
        # Creates and populates the table
        self.table.setColumnCount(len(self.table_columns))
        self.table.setHorizontalHeaderLabels(self.table_columns)
        self.table.setSizeAdjustPolicy(
            QAbstractScrollArea.AdjustToContents)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Stretch)

        for pem_file in self.pem_files:
            self.add_to_table(pem_file)

    def add_to_table(self, pem_file):

        row_pos = self.table.rowCount()
        self.table.insertRow(row_pos)

        if self.type == 'Line':
            item = QTableWidgetItem(pem_file.header.get('LineHole'))
            item2 = QTableWidgetItem(pem_file.header.get('LineHole'))
        elif self.type == 'File':
            item = QTableWidgetItem(os.path.basename(pem_file.filepath))
            item2 = QTableWidgetItem(os.path.basename(pem_file.filepath))
        else:
            raise ValueError

        item.setTextAlignment(QtCore.Qt.AlignCenter)
        item2.setTextAlignment(QtCore.Qt.AlignCenter)

        self.table.setItem(row_pos, 0, item)
        self.table.setItem(row_pos, 1, item2)

        self.table.resizeColumnsToContents()

    def update_table(self):
        # Every time a change is made in the line edits, this function is called and updates the entries in the table
        for row in range(self.table.rowCount()):
            # Split the text based on '[n]'. Anything before it becomes the prefix,
            # and everything after is added as a suffix
            if self.type == 'Line':
                # Immediately replace what's in the removeEdit object with nothing
                input = self.table.item(row, 0).text().replace(self.removeEdit.text(), '')
                suffix = self.addEdit.text().rsplit('[n]')[-1]
                prefix = self.addEdit.text().rsplit('[n]')[0]
                output = prefix + input + suffix
            else:
                input = self.table.item(row, 0).text().split('.')[0].replace(self.removeEdit.text(), '')
                ext = '.' + self.table.item(row, 0).text().split('.')[-1]
                suffix = self.addEdit.text().rsplit('[n]')[-1]
                prefix = self.addEdit.text().rsplit('[n]')[0]
                output = prefix + input + suffix + ext

            item = QTableWidgetItem(output)
            item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.table.setItem(row, 1, item)

    def close(self):
        while self.table.rowCount() > 0:
            self.table.removeRow(0)
        self.addEdit.setText('[n]')
        self.removeEdit.setText('')
        self.hide()

    def accept_changes(self):
        # Makes the proposed changes and updates the table
        if len(self.pem_files) > 0:
            for i, pem_file in enumerate(self.pem_files):
                new_name = self.table.item(i, 1).text()
                if self.type == 'Line':
                    pem_file.header['LineHole'] = new_name
                else:
                    old_path = copy.deepcopy(os.path.abspath(pem_file.filepath))
                    new_path = os.path.join(os.path.dirname(pem_file.filepath), new_name)
                    if pem_file.old_filepath is None:
                        pem_file.old_filepath = old_path
                    pem_file.filepath = new_path

            while self.table.rowCount() > 0:
                self.table.removeRow(0)
            for pem_file in self.pem_files:
                self.add_to_table(pem_file)
            header = self.table.horizontalHeader()
            header.setSectionResizeMode(0, QHeaderView.Stretch)
            header.setSectionResizeMode(1, QHeaderView.Stretch)
            self.addEdit.setText('[n]')
            self.removeEdit.setText('')


class BatchRIImporter(QWidget):
    """
    GUI window that imports multiple RI files. There must be equal number of RI files to PEM Files
    and the line/file name numbers much match up.
    """
    acceptImportSignal = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__()
        self.parent = parent
        self.pem_files = []
        self.ri_files = []
        self.ri_parser = RIFile
        self.message = QMessageBox()
        self.initUi()
        self.initSignals()

    def initUi(self):
        self.setAcceptDrops(True)
        self.setGeometry(500, 300, 400, 500)
        layout = QVBoxLayout()
        self.setLayout(layout)
        self.setWindowTitle("RI File Import")

        self.table = QTableWidget()
        self.initTable()

        self.buttonBox = QDialogButtonBox(QDialogButtonBox.Ok |
                                          QDialogButtonBox.Cancel)

        self.layout().addWidget(self.table)
        self.layout().addWidget(self.buttonBox)

    def initSignals(self):
        self.buttonBox.rejected.connect(self.close)
        self.buttonBox.accepted.connect(self.acceptImportSignal.emit)
        self.buttonBox.accepted.connect(self.close)

    def initTable(self):
        columns = ['PEM File', 'RI File']
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        self.table.setSizeAdjustPolicy(
            QAbstractScrollArea.AdjustIgnored)
        self.table.setAlternatingRowColors(True)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Stretch)

    def dragEnterEvent(self, e):
        urls = [url.toLocalFile() for url in e.mimeData().urls()]

        if all([url.lower().endswith('ri1') or url.lower().endswith('ri2') or url.lower().endswith(
                'ri3') for url in urls]):
            e.accept()
        else:
            e.ignore()

    def dropEvent(self, e):
        urls = [url.toLocalFile() for url in e.mimeData().urls()]
        self.open_ri_files(urls)

    def closeEvent(self, e):
        self.clear_table()
        e.accept()

    def keyPressEvent(self, e):
        if e.key() == QtCore.Qt.Key_Escape:
            self.close()
        elif e.key() == QtCore.Qt.Key_Return:
            self.acceptImportSignal.emit()
            self.close()

    def clear_table(self):
        while self.table.rowCount() > 0:
            self.table.removeRow(0)

    def open_pem_files(self, pem_files):
        self.pem_files = pem_files

        names = [os.path.basename(pem_file.filepath) for pem_file in self.pem_files]

        for i, name in enumerate(names):
            row_pos = self.table.rowCount()
            self.table.insertRow(row_pos)
            item = QTableWidgetItem(name)
            item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.table.setItem(row_pos, 0, item)

    def open_ri_files(self, ri_filepaths):
        ri_filepaths.sort(key=lambda path: natsort.humansorted(os.path.basename(path)), reverse=False)
        self.ri_files = []

        if len(ri_filepaths) == len(self.pem_files):

            # Only for boreholes, match up the RI1 file for Z, and RI2 file for XY
            if all(['borehole' in pem_file.survey_type.lower() for pem_file in self.pem_files]):
                ri_files = [self.ri_parser().open(filepath) for filepath in ri_filepaths]

                for pem_file in self.pem_files:
                    pem_components = sorted(pem_file.get_components())
                    pem_name = re.sub('[^0-9]', '', pem_file.header.get('LineHole'))[-4:]

                    for ri_file in ri_files:
                        ri_components = sorted(ri_file.get_components())
                        ri_name = re.sub('[^0-9]', '', os.path.splitext(os.path.basename(ri_file.filepath))[0])[-4:]

                        if pem_components == ri_components and pem_name == ri_name:
                            self.ri_files.append(ri_file.filepath)
                            ri_files.pop(ri_files.index(ri_file))
                            break

            elif not all([pem_file.is_borehole() for pem_file in self.pem_files]):
                self.message.information(None, "Error", "PEM files must either be all borehole or all surface surveys")

            else:
                [self.ri_files.append(ri_filepath) for ri_filepath in ri_filepaths]

            for i, filepath in enumerate(self.ri_files):  # Add the RI file names to the table
                name = os.path.basename(filepath)
                item = QTableWidgetItem(name)
                item.setTextAlignment(QtCore.Qt.AlignCenter)
                self.table.setItem(i, 1, item)

        else:
            self.message.information(None, "Error", "Length of RI files must be equal to length of PEM files")


class PlanMapOptions(QWidget, Ui_PlanMapOptionsWidget):
    """
    GUI to display checkboxes for display options when creating the final Plan Map PDF. Buttons aren't attached
    to any signals. The state of the checkboxes are read from PEMEditor.
    """

    # acceptImportSignal = QtCore.pyqtSignal()

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


class PEMFileSplitter(QWidget, Ui_PEMFileSplitterWidget):
    """
    Class that will extract selected stations from a PEM File and save them as a new PEM File.
    """

    def __init__(self, pem_file, parent=None):
        super().__init__()
        self.pem_file = pem_file
        self.parent = parent
        self.serializer = PEMSerializer()
        self.setupUi(self)
        self.init_signals()
        self.create_table()
        self.fill_table()

        self.show()

    def init_signals(self):
        self.extract_btn.clicked.connect(self.extract_selection)
        self.cancel_btn.clicked.connect(self.close)

    def closeEvent(self, e):
        e.accept()

    def keyPressEvent(self, e):
        if e.key() == QtCore.Qt.Key_Escape:
            self.close()
        elif e.key() == QtCore.Qt.Key_Return:
            self.close()

    def create_table(self):
        self.table_columns = ['Station']
        self.table.setColumnCount(len(self.table_columns))
        self.table.setHorizontalHeaderLabels(self.table_columns)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)

    def fill_table(self):
        stations = self.pem_file.get_unique_stations()

        for i, station in enumerate(stations):
            row = i
            self.table.insertRow(row)
            item = QTableWidgetItem(station)
            item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.table.setItem(row, 0, item)

    def extract_selection(self):
        selected_rows = [model.row() for model in self.table.selectionModel().selectedRows()]
        selected_stations = []
        for row in selected_rows:
            selected_stations.append(self.table.item(row, 0).text())

        if selected_stations:
            default_path = os.path.split(self.pem_file.filepath)[0]
            save_file = os.path.splitext(QFileDialog.getSaveFileName(self, '', default_path)[0])[0] + '.PEM'
            if save_file:
                new_pem_file = copy.copy(self.pem_file)
                selected_stations_data = list(filter(lambda x: x['Station'] in selected_stations, self.pem_file.data))
                new_pem_file.data = selected_stations_data
                new_pem_file.filepath = save_file
                new_pem_file.header['NumReadings'] = str(len(selected_stations_data))
                file = self.serializer.serialize(new_pem_file)
                print(file, file=open(new_pem_file.filepath, 'w+'))
                self.parent.open_pem_files(new_pem_file)
                self.close()
            else:
                self.close()


class Map3DViewer(QWidget, Ui_Map3DWidget):
    """
    QWidget window that displays a 3D map (plotted from Map3D) of the PEM Files.
    """

    def __init__(self, pem_files, parent=None):
        super().__init__()
        self.setupUi(self)
        self.pem_files = pem_files
        self.parent = parent
        self.setWindowTitle("3D Map Viewer")
        self.setWindowIcon(QtGui.QIcon(os.path.join(icons_path, '3d_map2.png')))

        self.draw_loops = self.draw_loops_cbox.isChecked()
        self.draw_lines = self.draw_lines_cbox.isChecked()
        self.draw_boreholes = self.draw_boreholes_cbox.isChecked()

        self.label_loops = self.label_loops_cbox.isChecked()
        self.label_lines = self.label_lines_cbox.isChecked()
        self.label_stations = self.label_stations_cbox.isChecked()
        self.label_boreholes = self.label_boreholes_cbox.isChecked()

        self.draw_loops_cbox.toggled.connect(self.toggle_loops)
        self.draw_lines_cbox.toggled.connect(self.toggle_lines)
        self.draw_boreholes_cbox.toggled.connect(self.toggle_boreholes)

        self.label_loops_cbox.toggled.connect(self.toggle_loop_labels)
        self.label_loop_anno_cbox.toggled.connect(self.toggle_loop_anno_labels)
        self.label_lines_cbox.toggled.connect(self.toggle_line_labels)
        self.label_stations_cbox.toggled.connect(self.toggle_station_labels)
        self.label_boreholes_cbox.toggled.connect(self.toggle_borehole_labels)
        self.label_segments_cbox.toggled.connect(self.toggle_segment_labels)

        self.figure = Figure()
        self.canvas = FigureCanvas(self.figure)
        self.map_layout.addWidget(self.canvas)
        self.figure.subplots_adjust(left=-0.1, bottom=-0.1, right=1.1, top=1.1)
        self.ax = self.figure.add_subplot(111, projection='3d')

        # self.toolbar = ContourMapToolbar(self.canvas, self)
        # self.toolbar_layout.addWidget(self.toolbar)
        # self.toolbar.setFixedHeight(30)

        self.map_plotter = Map3D(self.ax, self.pem_files, parent=self)
        self.map_plotter.plot_pems()
        self.map_plotter.format_ax()

        # Show/hide features based on the current state of the checkboxes
        self.update_canvas()

    def update_canvas(self):
        self.toggle_loops()
        self.toggle_lines()
        self.toggle_boreholes()
        self.toggle_loop_labels()
        self.toggle_loop_anno_labels()
        self.toggle_line_labels()
        self.toggle_borehole_labels()
        self.toggle_station_labels()
        self.toggle_segment_labels()
        self.canvas.draw()

    def toggle_loops(self):
        if self.draw_loops_cbox.isChecked():
            for artist in self.map_plotter.loop_artists:
                artist.set_visible(True)
        else:
            for artist in self.map_plotter.loop_artists:
                artist.set_visible(False)
        self.canvas.draw()

    def toggle_lines(self):
        if self.draw_lines_cbox.isChecked():
            for artist in self.map_plotter.line_artists:
                artist.set_visible(True)
        else:
            for artist in self.map_plotter.line_artists:
                artist.set_visible(False)
        self.canvas.draw()

    def toggle_boreholes(self):
        if self.draw_boreholes_cbox.isChecked():
            for artist in self.map_plotter.hole_artists:
                artist.set_visible(True)
        else:
            for artist in self.map_plotter.hole_artists:
                artist.set_visible(False)
        self.canvas.draw()

    def toggle_loop_labels(self):
        if self.label_loops_cbox.isChecked():
            for artist in self.map_plotter.loop_label_artists:
                artist.set_visible(True)
        else:
            for artist in self.map_plotter.loop_label_artists:
                artist.set_visible(False)
        self.canvas.draw()

    def toggle_loop_anno_labels(self):
        if self.label_loop_anno_cbox.isChecked():
            for artist in self.map_plotter.loop_anno_artists:
                artist.set_visible(True)
        else:
            for artist in self.map_plotter.loop_anno_artists:
                artist.set_visible(False)
        self.canvas.draw()

    def toggle_line_labels(self):
        if self.label_lines_cbox.isChecked():
            for artist in self.map_plotter.line_label_artists:
                artist.set_visible(True)
        else:
            for artist in self.map_plotter.line_label_artists:
                artist.set_visible(False)
        self.canvas.draw()

    def toggle_station_labels(self):
        if self.label_stations_cbox.isChecked():
            for artist in self.map_plotter.station_label_artists:
                artist.set_visible(True)
        else:
            for artist in self.map_plotter.station_label_artists:
                artist.set_visible(False)
        self.canvas.draw()

    def toggle_borehole_labels(self):
        if self.label_boreholes_cbox.isChecked():
            for artist in self.map_plotter.hole_label_artists:
                artist.set_visible(True)
        else:
            for artist in self.map_plotter.hole_label_artists:
                artist.set_visible(False)
        self.canvas.draw()

    def toggle_segment_labels(self):
        if self.label_segments_cbox.isChecked():
            for artist in self.map_plotter.segment_label_artists:
                artist.set_visible(True)
        else:
            for artist in self.map_plotter.segment_label_artists:
                artist.set_visible(False)
        self.canvas.draw()

    def closeEvent(self, e):
        self.figure.clear()
        e.accept()


class Section3DViewer(QWidget, Ui_Section3DWidget):
    """
    Displays a 3D vector plot of a borehole. Plots the vector plot itself in 2D, on a plane that is automatically
    calculated
    """

    def __init__(self, pem_file, parent=None):
        super().__init__()
        self.setupUi(self)
        self.pem_file = pem_file
        if not self.pem_file.is_borehole():
            raise TypeError(f'{os.path.basename(self.pem_file.filepath)} is not a borehole file.')
        self.parent = parent
        self.list_points = []

        self.setWindowTitle('3D Section Viewer')
        self.setWindowIcon(QtGui.QIcon(os.path.join(icons_path, 'section_3d.png')))

        self.draw_loop = self.draw_loop_cbox.isChecked()
        self.draw_borehole = self.draw_borehole_cbox.isChecked()
        self.draw_mag_field = self.draw_mag_field_cbox.isChecked()

        self.label_loop = self.label_loop_cbox.isChecked()
        self.label_loop_anno = self.label_loop_anno_cbox.isChecked()
        self.label_borehole = self.label_borehole_cbox.isChecked()

        self.draw_loop_cbox.toggled.connect(self.toggle_loop)
        self.draw_borehole_cbox.toggled.connect(self.toggle_borehole)
        self.draw_mag_field_cbox.toggled.connect(self.toggle_mag_field)

        self.label_loop_cbox.toggled.connect(self.toggle_loop_label)
        self.label_loop_anno_cbox.toggled.connect(self.toggle_loop_anno_labels)
        self.label_borehole_cbox.toggled.connect(self.toggle_borehole_label)
        self.label_segments_cbox.toggled.connect(self.toggle_segment_labels)

        self.figure = Figure()
        self.canvas = FigureCanvas(self.figure)
        # self.canvas.setFocusPolicy(QtCore.Qt.ClickFocus)  # Needed for key-press events
        # self.canvas.setFocus()

        self.map_layout.addWidget(self.canvas)
        self.ax = self.figure.add_subplot(111, projection='3d')

        self.section_plotter = Section3D(self.ax, self.pem_file, parent=self)
        self.section_plotter.plot_3d_magnetic_field()
        self.section_plotter.format_ax()
        self.figure.subplots_adjust(left=-0.1, bottom=-0.1, right=1.1, top=1.1)
        self.update_canvas()

    """
    Not used
        # self.cid_press = self.figure.canvas.mpl_connect('key_press_event', self.mpl_onpress)
        # self.cid_release = self.figure.canvas.mpl_connect('key_release_event', self.mpl_onrelease)

    def mpl_onclick(self, event):

        def get_mouse_xyz():
            x = float(self.ax.format_coord(event.xdata, event.ydata).split(',')[0].strip().split('=')[-1])
            y = float(self.ax.format_coord(event.xdata, event.ydata).split(',')[1].strip().split('=')[-1])
            z = float(self.ax.format_coord(event.xdata, event.ydata).split(',')[2].strip().split('=')[-1])
            return x, y, z

        if plt.get_current_fig_manager().toolbar.mode != '' or event.xdata is None:
            return
        if event.button == 3:
            if self.clickp1 is None:
                self.clickp1 = get_mouse_xyz()
                print(f'P1: {self.ax.format_coord(event.xdata, event.ydata)}')
                self.ax.plot([self.clickp1[0]], [self.clickp1[1]], [self.clickp1[2]], 'ro', label='1')
        #     self.plan_lines.append(self.ax.lines[-1])
                self.canvas.draw()
        #
            elif self.clickp2 is None:
                self.clickp2 = get_mouse_xyz()
                print(f'P2: {self.ax.format_coord(event.xdata, event.ydata)}')
                self.ax.plot([self.clickp2[0]], [self.clickp2[1]], [self.clickp2[2]], 'bo', label='2')
                self.canvas.draw()
            else:
                self.clickp1 = None
                self.clickp2 = None
        #     self.clickp2 = [int(event.xdata), int(event.ydata)]
        #
        #     if self.clickp2 == self.clickp1:
        #         self.clickp1, self.clickp2 = None, None
        #         raise NameError('P1 != P2, reset')
        #
        #     print(f'P2: {self.clickp2}')
        #
        #     self.ax.plot([self.clickp1[0], self.clickp2[0]],
        #                        [self.clickp1[1], self.clickp2[1]], 'r', label='L')
        #     self.plan_lines.append(self.ax.lines[-1])
        #
        #     plt.draw()
        #
        #     print('Plotting section...')

    def mpl_onpress(self, event):
        # print('press ', event.key)
        sys.stdout.flush()
        if event.key == 'control':
            self.cid_click = self.figure.canvas.mpl_connect('button_press_event', self.mpl_onclick)
        elif event.key == 'escape':
            self.clickp1 = None
            self.clickp2 = None

    def mpl_onrelease(self, event):
        # print('release ', event.key)
        if event.key == 'control':
            self.figure.canvas.mpl_disconnect(self.cid_click)
    """

    def update_canvas(self):
        self.toggle_loop()
        self.toggle_borehole()
        self.toggle_mag_field()
        self.toggle_loop_label()
        self.toggle_loop_anno_labels()
        self.toggle_borehole_label()
        self.toggle_segment_labels()

    def toggle_loop(self):
        if self.draw_loop_cbox.isChecked():
            for artist in self.section_plotter.loop_artists:
                artist.set_visible(True)
        else:
            for artist in self.section_plotter.loop_artists:
                artist.set_visible(False)
        self.canvas.draw()

    def toggle_borehole(self):
        if self.draw_borehole_cbox.isChecked():
            for artist in self.section_plotter.hole_artists:
                artist.set_visible(True)
        else:
            for artist in self.section_plotter.hole_artists:
                artist.set_visible(False)
        self.canvas.draw()

    def toggle_mag_field(self):
        if self.draw_mag_field_cbox.isChecked():
            for artist in self.section_plotter.mag_field_artists:
                artist.set_visible(True)
        else:
            for artist in self.section_plotter.mag_field_artists:
                artist.set_visible(False)
        self.canvas.draw()

    def toggle_loop_label(self):
        if self.label_loop_cbox.isChecked():
            for artist in self.section_plotter.loop_label_artists:
                artist.set_visible(True)
        else:
            for artist in self.section_plotter.loop_label_artists:
                artist.set_visible(False)
        self.canvas.draw()

    def toggle_loop_anno_labels(self):
        if self.label_loop_anno_cbox.isChecked():
            for artist in self.section_plotter.loop_anno_artists:
                artist.set_visible(True)
        else:
            for artist in self.section_plotter.loop_anno_artists:
                artist.set_visible(False)
        self.canvas.draw()

    def toggle_borehole_label(self):
        if self.label_borehole_cbox.isChecked():
            for artist in self.section_plotter.hole_label_artists:
                artist.set_visible(True)
        else:
            for artist in self.section_plotter.hole_label_artists:
                artist.set_visible(False)
        self.canvas.draw()

    def toggle_segment_labels(self):
        if self.label_segments_cbox.isChecked():
            for artist in self.section_plotter.segment_label_artists:
                artist.set_visible(True)
        else:
            for artist in self.section_plotter.segment_label_artists:
                artist.set_visible(False)
        self.canvas.draw()

    def closeEvent(self, e):
        self.figure.clear()
        e.accept()


class ContourMapViewer(QWidget, Ui_ContourMapCreatorFile):
    """
    Window that hosts the ContourMap. Filters the given PEMFiles to only include surface surveys. Either all files
    can be un-split, or if there are any split files, it will split the rest. Averages all files.
    """

    def __init__(self, pem_files, parent=None):
        super().__init__()
        self.setupUi(self)
        self.setWindowTitle('Contour Map Viewer')
        self.setWindowIcon(QtGui.QIcon(os.path.join(icons_path, 'contour_map3.png')))
        self.error = QErrorMessage()
        self.file_editor = PEMFileEditor()

        self.cmap = ContourMap()
        self.parent = parent
        self.pem_files = [pem_file for pem_file in pem_files if 'surface' in pem_file.survey_type.lower()]
        # Must be at least 2 eligible surface PEM files.
        if len(self.pem_files) < 2:
            raise TypeError("There are fewer than 2 eligible surface PEM files")

        # Averages any file not already averaged.
        for pem_file in self.pem_files:
            if not pem_file.is_averaged():
                print(f"Averaging {os.path.basename(pem_file.filepath)}")
                pem_file = self.file_editor.average(pem_file)

        # Either all files must be split or all un-split
        if not all([pem_file.is_split() for pem_file in pem_files]):
            for pem_file in self.pem_files:
                print(f"Splitting channels for {os.path.basename(pem_file.filepath)}")
                pem_file = self.file_editor.split_channels(pem_file)

        self.components = [pem_file.get_components() for pem_file in self.pem_files]
        self.components = list(set([item for sublist in self.components for item in sublist]))
        self.components.append('TF')

        # Disables the radio buttons of any component for which there is no data.
        if 'Z' not in self.components:
            self.z_rbtn.setEnabled(False)
            self.z_rbtn.setChecked(False)
        elif 'X' not in self.components:
            self.x_rbtn.setEnabled(False)
            self.x_rbtn.setChecked(False)
        elif 'Y' not in self.components:
            self.y_rbtn.setEnabled(False)
            self.y_rbtn.setChecked(False)

        # Checks the number of channels in each PEM file. The largest number becomes the maximum of the channel spinbox.
        pem_file_channels = np.array([int(pem_file.header.get('NumChannels')) for pem_file in self.pem_files])
        max_channels = pem_file_channels.max()
        self.channel_spinbox.setMaximum(max_channels)

        # Channel pairs created for use when finding the center-gate time of the current selected channel.
        self.channel_times = self.pem_files[np.argmax(pem_file_channels)].header.get('ChannelTimes')
        self.channel_pairs = list(map(lambda x, y: (x, y), self.channel_times[:-1], self.channel_times[1:]))

        # If all files are split, removes the gap channel. Only an issue for split files.
        if all([pem_file.is_split() for pem_file in self.pem_files]):
            # Remove the gap channel for split files
            for i, pair in enumerate(self.channel_pairs):
                if float(pair[0]) >= -0.0001 and float(pair[1]) <= 0.000048:
                    print(f"Removing channel {i} from the channel pairs")
                    self.channel_pairs.pop(i)

        # Signals
        self.channel_spinbox.valueChanged.connect(self.draw_map)
        self.z_rbtn.clicked.connect(self.draw_map)
        self.x_rbtn.clicked.connect(self.draw_map)
        self.y_rbtn.clicked.connect(self.draw_map)
        self.tf_rbtn.clicked.connect(self.draw_map)
        self.plot_loops_cbox.toggled.connect(self.draw_map)
        self.plot_lines_cbox.toggled.connect(self.draw_map)
        self.plot_stations_cbox.toggled.connect(self.draw_map)
        self.label_loops_cbox.toggled.connect(self.draw_map)
        self.label_lines_cbox.toggled.connect(self.draw_map)
        self.label_stations_cbox.toggled.connect(self.draw_map)
        self.plot_elevation_cbox.toggled.connect(self.draw_map)
        self.grid_cbox.toggled.connect(self.draw_map)
        self.title_box_cbox.toggled.connect(self.draw_map)
        self.channel_list_rbtn.toggled.connect(
            lambda: self.channel_list_edit.setEnabled(self.channel_list_rbtn.isChecked()))
        self.save_figure_btn.clicked.connect(self.save_figure)

        self.figure = Figure(figsize=(11, 8.5))
        self.canvas = FigureCanvas(self.figure)
        self.toolbar = ContourMapToolbar(self.canvas, self)
        self.toolbar_layout.addWidget(self.toolbar)
        self.toolbar.setFixedHeight(30)
        self.map_layout.addWidget(self.canvas)
        self.draw_map()

        self.channel_list_edit.setEnabled(False)

    def get_channel_time(self, channel):
        """
        Retrieve the gate-center time of a channel based on the channel times table.
        :param channel: int: channel number
        :return: float: channel center time.
        """
        current_pair = self.channel_pairs[channel]
        channel_center = (float(current_pair[1]) - float(current_pair[0])) / 2 + float(current_pair[0])
        channel_time = channel_center
        return channel_time

    def draw_map(self):

        component = self.get_selected_component().upper()
        if component not in self.components:
            return

        channel = self.channel_spinbox.value()
        channel_time = self.get_channel_time(channel)
        self.time_label.setText(f"{channel_time * 1000:.3f}ms")

        try:
            self.cmap.plot_contour(self.figure, self.pem_files, component, channel,
                                   draw_grid=self.grid_cbox.isChecked(),
                                   channel_time=channel_time,
                                   plot_loops=self.plot_loops_cbox.isChecked(),
                                   plot_lines=self.plot_lines_cbox.isChecked(),
                                   plot_stations=bool(
                                       self.plot_stations_cbox.isChecked() and self.plot_stations_cbox.isEnabled()),
                                   label_lines=bool(
                                       self.label_lines_cbox.isChecked() and self.label_lines_cbox.isEnabled()),
                                   label_loops=bool(
                                       self.label_loops_cbox.isChecked() and self.label_loops_cbox.isEnabled()),
                                   label_stations=bool(
                                       self.label_stations_cbox.isChecked() and self.label_stations_cbox.isEnabled()),
                                   elevation_contours=self.plot_elevation_cbox.isChecked(),
                                   title_box=self.title_box_cbox.isChecked())
        except Exception as e:
            self.error.showMessage(f"The following error occured while creating the contour plot:\n{str(e)}")
        else:
            self.canvas.draw()

    def get_selected_component(self):
        if self.z_rbtn.isChecked():
            return 'Z'
        elif self.x_rbtn.isChecked():
            return 'X'
        elif self.y_rbtn.isChecked():
            return 'Y'
        elif self.tf_rbtn.isChecked():
            return 'TF'

    def save_figure(self):
        """
        Create a PDF with the current selected channel or a list of channels.
        :return: None
        """
        if self.pem_files:
            if __name__ == '__main__':
                path = r"C:\Users\Eric\PycharmProjects\Crone\sample_files\PEMGetter files\test.pdf"
            else:
                default_path = os.path.abspath(self.pem_files[0].filepath)
                path, ext = QFileDialog.getSaveFileName(self, 'Save Figure', default_path,
                                                        'PDF Files (*.PDF);;PNG Files (*.PNG);;JPG Files (*.JPG')
            if path:
                print(f"Saving PDF to {path}")
                with PdfPages(path) as pdf:
                    # Create a figure just for saving, which is cleared after every save and closed at the end
                    save_fig = plt.figure(figsize=(11, 8.5))

                    # Print plots from the list of channels if it's enabled
                    if self.channel_list_edit.isEnabled():
                        text = self.channel_list_edit.text()
                        try:
                            channels = [int(re.match('\d+', text)[0]) for text in re.split(',| ', text)]
                            print(f"Saving contour map plots for channels {channels}")
                        except IndexError:
                            self.error.showMessage(f"No numbers found in the list of channels")
                            return
                    else:
                        channels = [self.channel_spinbox.value()]

                    for channel in channels:
                        channel_time = self.get_channel_time(channel)
                        fig = self.cmap.plot_contour(save_fig, self.pem_files, self.get_selected_component(),
                                                     channel,
                                                     draw_grid=self.grid_cbox.isChecked(),
                                                     channel_time=channel_time,
                                                     plot_loops=self.plot_loops_cbox.isChecked(),
                                                     plot_lines=self.plot_lines_cbox.isChecked(),
                                                     plot_stations=bool(
                                                         self.plot_stations_cbox.isChecked() and self.plot_stations_cbox.isEnabled()),
                                                     label_lines=bool(
                                                         self.label_lines_cbox.isChecked() and self.label_lines_cbox.isEnabled()),
                                                     label_loops=bool(
                                                         self.label_loops_cbox.isChecked() and self.label_loops_cbox.isEnabled()),
                                                     label_stations=bool(
                                                         self.label_stations_cbox.isChecked() and self.label_stations_cbox.isEnabled()),
                                                     elevation_contours=self.plot_elevation_cbox.isChecked(),
                                                     title_box=self.title_box_cbox.isChecked())

                        pdf.savefig(fig, orientation='landscape')
                        save_fig.clear()
                    plt.close(save_fig)
                os.startfile(path)


class ContourMapToolbar(NavigationToolbar):
    """
    Custom Matplotlib toolbar for ContourMap.
    """
    # only display the buttons we need
    toolitems = [t for t in NavigationToolbar.toolitems if
                 t[0] in ('Home', 'Back', 'Forward', 'Pan', 'Zoom')]


class GPSAdder(QWidget):
    """
    Class to help add station GPS to a PEM file. Helps with files that have missing stations numbers or other
    formatting errors.
    """
    # matplotlib.style.use('ggplot')

    def __init__(self):
        super().__init__()
        self.resize(1000, 800)

        self.df = None
        self.write_table = None  # QTableWidget, one of the ones in the write_widget
        self.write_widget = None  # PEMInfoWidget object
        self.error = False  # For pending errors

        # Highlighting
        self.plan_highlight = None
        self.plan_lx = None
        self.plan_ly = None
        self.section_highlight = None
        self.section_lx = None
        self.section_ly = None
        self.selection = []

        self.layout = QGridLayout()
        self.table = QTableWidget()
        self.table.setFixedWidth(400)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)

        self.message = QMessageBox()
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.setCenterButtons(True)

        self.figure = plt.figure()
        self.figure.subplots_adjust(left=0.17, bottom=0.05, right=0.97, top=0.95)
        self.plan_ax = plt.subplot2grid((30, 1), (0, 0), rowspan=19, colspan=1, fig=self.figure)
        self.plan_ax.set_aspect('equal')
        self.plan_ax.use_sticky_edges = False
        self.section_ax = plt.subplot2grid((30, 1), (22, 0), rowspan=7, colspan=1, fig=self.figure)
        self.section_ax.use_sticky_edges = False
        self.canvas = FigureCanvas(self.figure)

        self.zp = ZoomPan()
        self.plan_zoom = self.zp.zoom_factory(self.plan_ax)
        self.plan_pan = self.zp.pan_factory(self.plan_ax)
        self.section_zoom = self.zp.zoom_factory(self.section_ax)
        self.section_pan = self.zp.pan_factory(self.section_ax)

        self.setLayout(self.layout)
        self.layout.addWidget(self.table, 0, 0)
        self.layout.addWidget(self.button_box, 1, 0, 1, 2)
        self.layout.addWidget(self.canvas, 0, 1)

        self.canvas.mpl_connect('pick_event', self.onpick)

        self.button_box.rejected.connect(self.close)
        self.table.cellChanged.connect(self.plot_table)
        self.table.cellChanged.connect(self.check_table)
        self.table.itemSelectionChanged.connect(self.highlight_point)

        self.del_action = QShortcut(QtGui.QKeySequence("Del"), self)
        self.del_action.activated.connect(self.del_row)

        self.reset_action = QShortcut(QtGui.QKeySequence(" "), self)
        self.reset_action.activated.connect(self.plot_table)
        self.reset_action.activated.connect(self.highlight_point)

        # self.popMenu = QMenu(self)
        # self.popMenu.addAction(self.move_up_action)
        # self.popMenu.addAction(self.move_down_action)

    def del_row(self):
        if self.table.selectionModel().hasSelection():
            row = self.table.selectionModel().selectedRows()[0].row()
            self.table.removeRow(row)
            self.plot_table()
            self.highlight_point(row)

    def close(self):
        self.write_widget = None
        self.write_table = None
        self.clear_table()
        self.hide()

    def clear_table(self):
        self.table.blockSignals(True)
        self.table.clear()
        while self.table.rowCount() > 0:
            self.table.removeRow(0)
        self.table.blockSignals(True)

    def add_df(self, df):
        """
        Add the data frame to GPSAdder. Adds the data to the table and plots it.
        :param df: pandas DataFrame
        :return: None
        """
        self.show()
        self.clear_table()
        self.df = df
        self.df_to_table(self.df)
        self.plot_table()
        self.check_table()

    def df_to_table(self, df):
        """
        Add the contents of the data frame to the table
        :param df: pandas DataFrame of the GPS
        :return: None
        """
        self.table.blockSignals(True)

        def write_row(series):
            """
             Add items from a pandas data frame row to a QTableWidget row
             :param series: pandas Series object
             :return: None
             """
            row_pos = self.table.rowCount()
            # Add a new row to the table
            self.table.insertRow(row_pos)

            items = series.map(lambda x: QTableWidgetItem(str(x))).to_list()
            # Format each item of the table to be centered
            for m, item in enumerate(items):
                item.setTextAlignment(QtCore.Qt.AlignCenter)
                self.table.setItem(row_pos, m, item)

        if df.empty:
            self.message.warning(self, 'Warning', 'No GPS was found')
        else:
            self.clear_table()
            columns = df.columns.to_list()
            self.table.setColumnCount(len(columns))
            self.table.setHorizontalHeaderLabels(columns)
            df.apply(write_row, axis=1)
        self.table.blockSignals(False)

    def table_to_df(self):
        """
        Return a data frame from the information in the table
        :return: pandas DataFrame
        """
        df = pd.DataFrame(columns=self.df.columns)
        for col in range(len(df.columns)):
            l = []
            for row in range(self.table.rowCount()):
                l.append(self.table.item(row, col).text())
            try:
                df.iloc[:, col] = pd.Series(l, dtype=self.df.dtypes.iloc[col])
            except ValueError:
                self.message.information(self, 'Error', 'Invalid data type')
                self.error = True
                return None
        self.error = False
        return df

    def plot_table(self):
        pass

    def onpick(self, event):
        """
        Signal slot: When a point in the plots is clicked, highlights the associated row in the table.
        :param event: Mouse click event
        :return: None
        """
        # Ignore mouse wheel events
        if event.mouseevent.button == 'up' or event.mouseevent.button == 'down' or event.mouseevent.button == 2:
            return

        ind = event.ind[0]
        print(f"Point {ind} clicked")

        self.table.selectRow(ind)
        self.highlight_point(row=ind)

    def highlight_point(self, row=None):
        pass
    #     """
    #     Highlight a scatter point when it's row is selected in the table
    #     :param row: Int: table row to highlight
    #     :return: None
    #     """
    #     def reset_highlight():
    #         self.plan_highlight.remove()
    #         self.plan_lx.remove()
    #         self.plan_ly.remove()
    #         self.section_highlight.remove()
    #         self.section_lx.remove()
    #         self.section_ly.remove()
    #
    #         self.plan_highlight = None
    #         self.plan_lx = None
    #         self.plan_ly = None
    #         self.section_highlight = None
    #         self.section_lx = None
    #         self.section_ly = None
    #
    #     print(f"Row {row} selected")
    #     # Remove previously plotted selection
    #     if self.plan_highlight:
    #         reset_highlight()
    #
    #     # Don't do anything if there is a pending error
    #     if self.error is True:
    #         return
    #
    #     df = self.table_to_df()
    #     # Plot on the plan map
    #     plan_x, plan_y = df.loc[row, 'Easting'], df.loc[row, 'Northing']
    #     self.plan_highlight = self.plan_ax.scatter([plan_x], [plan_y],
    #                                                color='lightsteelblue',
    #                                                edgecolors='blue',
    #                                                zorder=3
    #                                                )
    #     self.plan_lx = self.plan_ax.axhline(plan_y, color='blue')
    #     self.plan_ly = self.plan_ax.axvline(plan_x, color='blue')
    #
    #     # Plot on the section map
    #     section_x, section_y = df.loc[row, 'Station'], df.loc[row, 'Elevation']
    #     self.section_highlight = self.section_ax.scatter([section_x], [section_y],
    #                                                      color='lightsteelblue',
    #                                                      edgecolors='blue',
    #                                                      zorder=3
    #                                                      )
    #     self.section_lx = self.section_ax.axhline(section_y, color='blue')
    #     self.section_ly = self.section_ax.axvline(section_x, color='blue')
    #     self.canvas.draw()

    def check_table(self):
        """
        Look for any incorrect data types and create an error if found
        :return: None
        """

        def color_row(row, color):
            """
            Color the background of each cell of a row in the table
            :param row: Int: Row to color
            :param color: str
            :return: None
            """
            for col in range(self.table.columnCount()):
                self.table.item(row, col).setBackground(QtGui.QColor(color))

        def has_na(row):
            """
            Return True if any cell in the row can't be converted to a float
            :param row: Int: table row to check
            :return: bool
            """
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col).text()
                try:
                    float(item)
                except ValueError:
                    return True
                finally:
                    if item == 'nan':
                        return True
            return False

        self.table.blockSignals(True)
        for row in range(self.table.rowCount()):
            if has_na(row):
                color_row(row, 'pink')
            else:
                color_row(row, 'white')
        self.table.blockSignals(False)


class LineAdder(GPSAdder):

    def __init__(self):
        super().__init__()
        self.setWindowTitle('Line Adder')
        self.button_box.accepted.connect(self.accept)

    def accept(self):
        """
        Signal slot: Adds the data from the table to the write_widget's (pem_info_widget object) table.
        :return: None
        """
        self.write_widget.fill_gps_table(self.table_to_df().dropna(), self.write_widget.stationGPSTable)
        self.close()

    def plot_table(self):
        """
        Plot the data from the table to the axes. Ignores any rows that have NaN somewhere in the row.
        :return: None
        """
        self.plan_ax.clear()
        self.section_ax.clear()

        df = self.table_to_df()

        # Redraw the empty canvas if there is a pending error
        if self.error is True:
            self.canvas.draw()
            return

        # Plot the plan map
        df.plot(x='Easting', y='Northing',
                ax=self.plan_ax,
                color='dimgray',
                zorder=0,
                legend=False
                )
        # Plot the stations on the plan map
        df.plot.scatter(x='Easting', y='Northing',
                        ax=self.plan_ax,
                        color='w',
                        edgecolors='dimgray',
                        zorder=1,
                        legend=False,
                        picker=True
                        )
        # Plot the sections
        df.plot(x='Station', y='Elevation',
                ax=self.section_ax,
                color='dimgray',
                zorder=0,
                legend=False
                )
        # self.section_ax.xaxis.grid(True, which='minor')
        self.section_ax.xaxis.set_minor_locator(FixedLocator(df.Station.to_list()))

        # Plot the stations on the section map
        df.plot.scatter(x='Station', y='Elevation',
                        ax=self.section_ax,
                        color='w',
                        edgecolors='dimgray',
                        zorder=1,
                        legend=False,
                        picker=True
                        )

        # Add flat elevation for the section plot limits
        self.section_ax.set_ylim(self.section_ax.get_ylim()[0] - 5,
                                 self.section_ax.get_ylim()[1] + 5)
        # self.plan_ax.set_yticklabels(self.plan_ax.get_yticklabels(), rotation=0, ha='center')
        self.canvas.draw()

    def highlight_point(self, row=None):
        """
        Highlight a scatter point when it's row is selected in the table
        :param row: Int: table row to highlight
        :return: None
        """

        def reset_highlight():
            self.plan_highlight.remove()
            self.plan_lx.remove()
            self.plan_ly.remove()
            self.section_highlight.remove()
            self.section_lx.remove()
            self.section_ly.remove()

            self.plan_highlight = None
            self.plan_lx = None
            self.plan_ly = None
            self.section_highlight = None
            self.section_lx = None
            self.section_ly = None

        if row is None:
            row = self.table.selectionModel().selectedRows()[0].row()

        print(f"Row {row} selected")
        # Remove previously plotted selection
        if self.plan_highlight:
            reset_highlight()

        # Don't do anything if there is a pending error
        if self.error is True:
            return

        df = self.table_to_df()
        # Plot on the plan map
        plan_x, plan_y = df.loc[row, 'Easting'], df.loc[row, 'Northing']
        self.plan_highlight = self.plan_ax.scatter([plan_x], [plan_y],
                                                   color='lightsteelblue',
                                                   edgecolors='blue',
                                                   zorder=3
                                                   )
        self.plan_lx = self.plan_ax.axhline(plan_y, color='blue')
        self.plan_ly = self.plan_ax.axvline(plan_x, color='blue')

        # Plot on the section map
        section_x, section_y = df.loc[row, 'Station'], df.loc[row, 'Elevation']
        self.section_highlight = self.section_ax.scatter([section_x], [section_y],
                                                         color='lightsteelblue',
                                                         edgecolors='blue',
                                                         zorder=3
                                                         )
        self.section_lx = self.section_ax.axhline(section_y, color='blue')
        self.section_ly = self.section_ax.axvline(section_x, color='blue')
        self.canvas.draw()


class LoopAdder(GPSAdder):

    def __init__(self):
        super().__init__()
        self.setWindowTitle('Loop Adder')
        self.button_box.accepted.connect(self.accept)

    def onpick(self, event):
        """
        Signal slot: When a point in the plots is clicked, highlights the associated row in the table.
        :param event: Mouse click event
        :return: None
        """
        def swap_points():
            """
            Swaps the position of two points on either axes. Creates a data frame from the table, then swaps the
            corresponding rows in the data frame, then re-creates the table and plots the data.
            :return: None
            """
            points = self.selection
            # Create the data frame
            df = self.table_to_df()
            # Create a copy of the two rows.
            a, b = df.iloc[points[0]].copy(), df.iloc[points[1]].copy()
            # Allocate the two rows in reverse order
            df.iloc[points[0]], df.iloc[points[1]] = b, a
            self.df_to_table(df)
            self.plot_table(preserve_limits=True)
            self.highlight_point(points[1])

        # Ignore mouse wheel events
        if event.mouseevent.button == 'up' or event.mouseevent.button == 'down' or event.mouseevent.button == 2:
            return
        ind = event.ind[0]
        print(f"Point {ind} clicked")

        # Swap two points when CTRL is pressed when selecting two points
        if keyboard.is_pressed('ctrl'):
            # Reset the selection if two were already selected
            if len(self.selection) == 2:
                self.selection = []
            self.selection.append(ind)
            print(f'Selected points: {self.selection}')

            if len(self.selection) == 2:
                print(f"Two points are selected, swapping them...")
                swap_points()
        else:
            # Reset the selection if CTRL isn't pressed
            self.selection = []

        self.table.selectRow(ind)
        self.highlight_point(row=ind)

        # # Open the context menu if the right mouse button was clicked
        # if event.mouseevent.button == 3:
        #     cursor = QtGui.QCursor()
        #     self.popMenu.popup(cursor.pos())

    def add_df(self, df):
        """
        Add the data frame to GPSAdder. Adds the data to the table and plots it.
        :param df: pandas DataFrame
        :return: None
        """
        self.show()
        self.clear_table()
        self.df = df
        self.df_to_table(self.df)
        self.plot_table()
        self.check_table()

    def accept(self):
        """
        Signal slot: Adds the data from the table to the write_widget's (pem_info_widget object) table.
        :return: None
        """
        self.write_widget.fill_gps_table(self.table_to_df().dropna(), self.write_widget.loopGPSTable)
        self.close()

    def plot_table(self, preserve_limits=False):
        """
        Plot the data from the table to the axes. Ignores any rows that have NaN somewhere in the row.
        :return: None
        """
        if preserve_limits is True:
            plan_xlim, plan_ylim = self.plan_ax.get_xlim(), self.plan_ax.get_ylim()
            section_xlim, section_ylim = self.section_ax.get_xlim(), self.section_ax.get_ylim()
        self.plan_ax.clear()
        self.section_ax.clear()

        df = self.table_to_df()

        # Redraw the empty canvas if there is a pending error
        if self.error is True:
            self.canvas.draw()
            return

        df = df.append(df.iloc[0], ignore_index=True)
        # Plot the plan map
        df.plot(x='Easting', y='Northing',
                ax=self.plan_ax,
                color='dimgray',
                zorder=0,
                legend=False
                )
        # Plot the stations on the plan map
        df.plot.scatter(x='Easting', y='Northing',
                        ax=self.plan_ax,
                        color='w',
                        edgecolors='dimgray',
                        zorder=1,
                        legend=False,
                        picker=True
                        )
        # Plot the sections
        df.plot(y='Elevation',
                ax=self.section_ax,
                color='dimgray',
                zorder=0,
                legend=False
                )

        # Plot the stations on the section map
        df.reset_index().plot.scatter(x='index', y='Elevation',
                                      ax=self.section_ax,
                                      color='w',
                                      edgecolors='dimgray',
                                      zorder=1,
                                      legend=False,
                                      picker=True
                                      )

        if preserve_limits is True:
            self.plan_ax.set_xlim(plan_xlim)
            self.plan_ax.set_ylim(plan_ylim)
            self.section_ax.set_xlim(section_xlim)
            self.section_ax.set_ylim(section_ylim)
        else:
            # Add flat elevation for the section plot limits
            self.section_ax.set_ylim(self.section_ax.get_ylim()[0] - 5,
                                     self.section_ax.get_ylim()[1] + 5)

        # ticks = self.plan_ax.get_yticklabels()
        # self.plan_ax.set_yticklabels(ticks, rotation=45)
        self.canvas.draw()

    def highlight_point(self, row=None):
        """
        Highlight a scatter point when it's row is selected in the table
        :param row: Int: table row to highlight
        :return: None
        """

        def reset_highlight():
            self.plan_highlight.remove()
            self.plan_lx.remove()
            self.plan_ly.remove()
            self.section_highlight.remove()
            self.section_lx.remove()
            self.section_ly.remove()

            self.plan_highlight = None
            self.plan_lx = None
            self.plan_ly = None
            self.section_highlight = None
            self.section_lx = None
            self.section_ly = None

        if row is None:
            row = self.table.selectionModel().selectedRows()[0].row()
        print(f"Row {row} selected")
        # Remove previously plotted selection
        if self.plan_highlight:
            reset_highlight()

        # Don't do anything if there is a pending error
        if self.error is True:
            return

        color, light_color = ('blue', 'lightsteelblue') if keyboard.is_pressed('ctrl') is False else ('red', 'pink')

        df = self.table_to_df()
        # Plot on the plan map
        plan_x, plan_y = df.loc[row, 'Easting'], df.loc[row, 'Northing']
        self.plan_highlight = self.plan_ax.scatter([plan_x], [plan_y],
                                                   color=light_color,
                                                   edgecolors=color,
                                                   zorder=3
                                                   )
        self.plan_lx = self.plan_ax.axhline(plan_y, color=color)
        self.plan_ly = self.plan_ax.axvline(plan_x, color=color)

        # Plot on the section map
        section_x, section_y = row, df.loc[row, 'Elevation']
        self.section_highlight = self.section_ax.scatter([section_x], [section_y],
                                                         color=light_color,
                                                         edgecolors=color,
                                                         zorder=3
                                                         )
        self.section_lx = self.section_ax.axhline(section_y, color=color)
        self.section_ly = self.section_ax.axvline(section_x, color=color)
        self.canvas.draw()


class ZoomPan:
    """
    Add mouse wheel zoom and pan to matplotlib axes
    from https://stackoverflow.com/questions/11551049/matplotlib-plot-zooming-with-scroll-wheel
    """
    def __init__(self):
        self.press = None
        self.cur_xlim = None
        self.cur_ylim = None
        self.x0 = None
        self.y0 = None
        self.x1 = None
        self.y1 = None
        self.xpress = None
        self.ypress = None

    def zoom_factory(self, ax, base_scale=1.5):
        def zoom(event):
            if event.inaxes != ax: return
            cur_xlim = ax.get_xlim()
            cur_ylim = ax.get_ylim()

            xdata = event.xdata  # get event x location
            ydata = event.ydata  # get event y location

            if event.button == 'up':
                # deal with zoom in
                scale_factor = 1 / base_scale
            elif event.button == 'down':
                # deal with zoom out
                scale_factor = base_scale
            else:
                # deal with something that should never happen
                scale_factor = 1
                print(event.button)

            new_width = (cur_xlim[1] - cur_xlim[0]) * scale_factor
            new_height = (cur_ylim[1] - cur_ylim[0]) * scale_factor

            relx = (cur_xlim[1] - xdata)/(cur_xlim[1] - cur_xlim[0])
            rely = (cur_ylim[1] - ydata)/(cur_ylim[1] - cur_ylim[0])

            ax.set_xlim([xdata - new_width * (1-relx), xdata + new_width * (relx)])
            ax.set_ylim([ydata - new_height * (1-rely), ydata + new_height * (rely)])
            ax.figure.canvas.draw()

        fig = ax.get_figure()  # get the figure of interest
        fig.canvas.mpl_connect('scroll_event', zoom)

        return zoom

    def pan_factory(self, ax):
        def onPress(event):
            if event.inaxes != ax: return
            if event.button != 2: return
            self.cur_xlim = ax.get_xlim()
            self.cur_ylim = ax.get_ylim()
            self.press = self.x0, self.y0, event.xdata, event.ydata
            self.x0, self.y0, self.xpress, self.ypress = self.press

        def onRelease(event):
            self.press = None
            ax.figure.canvas.draw()

        def onMotion(event):
            if self.press is None: return
            if event.inaxes != ax: return
            dx = event.xdata - self.xpress
            dy = event.ydata - self.ypress
            self.cur_xlim -= dx
            self.cur_ylim -= dy
            ax.set_xlim(self.cur_xlim)
            ax.set_ylim(self.cur_ylim)

            ax.figure.canvas.draw()

        fig = ax.get_figure()  # get the figure of interest

        # attach the call back
        fig.canvas.mpl_connect('button_press_event', onPress)
        fig.canvas.mpl_connect('button_release_event', onRelease)
        fig.canvas.mpl_connect('motion_notify_event', onMotion)

        # return the function
        return onMotion


def main():
    from src.pem.pem_getter import PEMGetter
    app = QApplication(sys.argv)
    mw = PEMEditorWindow()

    pg = PEMGetter()
    pem_files = pg.get_pems(client='Kazzinc', number=1)
    mw.open_pem_files(pem_files)
    mw.show()
    mw.open_gps_files([r'C:\Users\Mortulo\PycharmProjects\PEMPro\sample_files\Loop GPS\LOOP4.txt'])
    # import pyqtgraph.examples
    # pyqtgraph.examples.run()

    # mw.open_gps_files([r'C:\Users\Mortulo\PycharmProjects\PEMPro\sample_files\Line GPS\LINE 300S.txt'])
    # mw.import_ri_files()
    # mw.show_map()
    # mw.timebase_freqency_converter()
    # mw.calc_mag_declination(pem_files[0])
    # mw.save_as_xyz(selected_files=False)
    # mw.show_contour_map_viewer()
    # mw.contour_map_viewer.save_figure()
    # mw.auto_merge_pem_files()
    # mw.save_as_kmz()
    # spinner = WaitingSpinner(mw.table)
    # spinner.start()
    # spinner.show()

    # mw.auto_merge_pem_files()
    # mw.sort_files()
    # section = Section3DViewer(pem_files[0])
    # section.show()

    # mw.share_loop_cbox.setChecked(False)
    # mw.output_lin_cbox.setChecked(False)
    # mw.output_log_cbox.setChecked(False)
    # mw.output_step_cbox.setChecked(False)
    # mw.output_section_cbox.setChecked(False)
    # mw.output_plan_map_cbox.setChecked(False)
    # mw.print_plots()

    # map = Map3DViewer(pem_files)
    # map.show()

    # mw.open_pem_files(r'C:\_Data\2019\_Mowgli Testing\DC6200E-LP124.PEM')
    # mw.open_gpx_files(r'C:\_Data\2019\_Mowgli Testing\loop_13_transmitters.GPX')

    # mw.open_pem_files(r'C:\_Data\2019\_Mowgli Testing\1200NAv.PEM')
    # mw.open_ri_file([r'C:\_Data\2019\_Mowgli Testing\1200N.RI3'])
    # mw.print_plots()
    # mw.print_plots(final=True)

    app.exec_()


if __name__ == '__main__':
    main()
    # cProfile.run('main()', 'restats')
    # p = pstats.Stats('restats')
    # p.strip_dirs().sort_stats(-1).print_stats()
    #
    # p.sort_stats('cumulative').print_stats(.5)

    # p.sort_stats('time', 'cumulative').print_stats()
