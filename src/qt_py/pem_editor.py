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
from shutil import copyfile
from itertools import chain, groupby
from PyQt5 import (QtCore, QtGui, uic)
from PyQt5.QtWidgets import (QWidget, QMainWindow, QApplication, QDesktopWidget, QMessageBox, QFileDialog,
                             QTableWidgetItem, QAction, QMenu, QGridLayout, QTextBrowser,
                             QInputDialog, QErrorMessage, QLabel, QLineEdit, QPushButton)
# from pyqtspinner.spinner import WaitingSpinner
import geomag

from src.gps.gps_editor import SurveyLine, TransmitterLoop, BoreholeCollar, BoreholeGeometry, GPXEditor, CRS
from src.gps.gpx_creator import GPXCreator

from src.pem.pem_file import PEMFile, PEMParser
from src.pem.pem_plotter import PEMPrinter, CustomProgressBar, FoliumMap
from src.pem.pem_planner import LoopPlanner, GridPlanner

from src.qt_py.pem_info_widget import PEMFileInfoWidget
from src.qt_py.unpacker import Unpacker
from src.qt_py.ri_importer import BatchRIImporter
from src.qt_py.gps_adder import LineAdder, LoopAdder
from src.qt_py.name_editor import BatchNameEditor
from src.qt_py.station_splitter import StationSplitter
from src.qt_py.map_widgets import Map3DViewer, Section3DViewer, ContourMapViewer

from src.damp.db_plot import DBPlot

__version__ = '0.11.0'

# Modify the paths for when the script is being run in a frozen state (i.e. as an EXE)
if getattr(sys, 'frozen', False):
    application_path = sys._MEIPASS
    editorWindowCreatorFile = 'qt_ui\\pem_editor.ui'
    planMapOptionsCreatorFile = 'qt_ui\\plan_map_options.ui'
    icons_path = 'icons'
else:
    application_path = os.path.dirname(os.path.abspath(__file__))
    editorWindowCreatorFile = os.path.join(os.path.dirname(application_path), 'qt_ui\\pem_editor.ui')
    planMapOptionsCreatorFile = os.path.join(os.path.dirname(application_path), 'qt_ui\\plan_map_options.ui')
    icons_path = os.path.join(os.path.dirname(application_path), "qt_ui\\icons")

# Load Qt ui file into a class
Ui_PEMEditorWindow, QtBaseClass = uic.loadUiType(editorWindowCreatorFile)
Ui_PlanMapOptionsWidget, QtBaseClass = uic.loadUiType(planMapOptionsCreatorFile)


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


class PEMEditor(QMainWindow, Ui_PEMEditorWindow):

    def __init__(self, parent=None):
        super().__init__()
        self.parent = parent
        self.initUi()

        self.pem_files = []
        self.pem_info_widgets = []
        self.tab_num = 1
        self.allow_signals = True

        self.dialog = QFileDialog()
        self.message = QMessageBox()
        self.error = QErrorMessage()
        self.pg = CustomProgressBar()
        self.text_browsers = []

        # Widgets
        self.line_adder = LineAdder()
        self.loop_adder = LoopAdder()
        self.gpx_editor = GPXEditor()
        self.station_splitter = StationSplitter(parent=self)
        self.grid_planner = GridPlanner()
        self.loop_planner = LoopPlanner()
        self.db_plot = DBPlot()
        self.unpacker = Unpacker()
        self.gpx_creator = GPXCreator()
        self.ri_importer = BatchRIImporter(parent=self)
        self.plan_map_options = PlanMapOptions(parent=self)
        self.batch_name_editor = BatchNameEditor()
        self.map_viewer_3d = Map3DViewer()
        self.freq_con = FrequencyConverter(parent=self)
        self.section_viewer_3d = None
        self.contour_viewer = None

        self.initMenus()
        self.initSignals()

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
        def center_window(win):
            qtRectangle = win.frameGeometry()
            centerPoint = QDesktopWidget().availableGeometry().center()
            qtRectangle.moveCenter(centerPoint)
            win.move(qtRectangle.topLeft())

        self.setupUi(self)
        self.setAcceptDrops(True)
        self.setWindowTitle("PEMPro  v" + str(__version__))
        self.setWindowIcon(
            QtGui.QIcon(os.path.join(icons_path, 'conder.png')))
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
        self.actionImport_RI_Files.triggered.connect(self.show_ri_importer)

        # PEM menu
        self.actionRename_All_Lines_Holes.setStatusTip("Rename all line/hole names")
        self.actionRename_All_Lines_Holes.setToolTip("Rename all line/hole names")
        self.actionRename_All_Lines_Holes.triggered.connect(lambda: self.show_batch_renamer(type='Line'))

        self.actionRename_All_Files.setStatusTip("Rename all file names")
        self.actionRename_All_Files.setToolTip("Rename all file names")
        self.actionRename_All_Files.triggered.connect(lambda: self.show_batch_renamer(type='File'))

        self.actionAverage_All_PEM_Files.setStatusTip("Average all PEM files")
        self.actionAverage_All_PEM_Files.setToolTip("Average all PEM files")
        self.actionAverage_All_PEM_Files.setIcon(QtGui.QIcon(os.path.join(icons_path, 'average.png')))
        self.actionAverage_All_PEM_Files.setShortcut("F5")
        self.actionAverage_All_PEM_Files.triggered.connect(lambda: self.average_pem_data(selected=False))
        # self.actionAverage_All_PEM_Files.triggered.connect(self.refresh_table)

        self.actionSplit_All_PEM_Files.setStatusTip("Remove on-time channels for all PEM files")
        self.actionSplit_All_PEM_Files.setToolTip("Remove on-time channels for all PEM files")
        self.actionSplit_All_PEM_Files.setIcon(QtGui.QIcon(os.path.join(icons_path, 'split.png')))
        self.actionSplit_All_PEM_Files.setShortcut("F6")
        self.actionSplit_All_PEM_Files.triggered.connect(lambda: self.split_pem_channels(selected=False))
        # self.actionSplit_All_PEM_Files.triggered.connect(self.refresh_table)

        self.actionScale_All_Currents.setStatusTip("Scale the current of all PEM Files to the same value")
        self.actionScale_All_Currents.setToolTip("Scale the current of all PEM Files to the same value")
        self.actionScale_All_Currents.setIcon(QtGui.QIcon(os.path.join(icons_path, 'current.png')))
        self.actionScale_All_Currents.setShortcut("F7")
        self.actionScale_All_Currents.triggered.connect(lambda: self.scale_pem_current(selected=False))

        self.actionChange_All_Coil_Areas.setStatusTip("Scale all coil areas to the same value")
        self.actionChange_All_Coil_Areas.setToolTip("Scale all coil areas to the same value")
        self.actionChange_All_Coil_Areas.setIcon(QtGui.QIcon(os.path.join(icons_path, 'coil.png')))
        self.actionChange_All_Coil_Areas.setShortcut("F8")
        self.actionChange_All_Coil_Areas.triggered.connect(lambda: self.scale_pem_coil_area(selected=False))

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
        self.actionLoop_Planner.triggered.connect(lambda: self.loop_planner.show())

        self.actionGrid_Planner.setStatusTip("Grid planner")
        self.actionGrid_Planner.setToolTip("Grid planner")
        self.actionGrid_Planner.setIcon(
            QtGui.QIcon(os.path.join(icons_path, 'grid_planner.png')))
        self.actionGrid_Planner.triggered.connect(lambda: self.grid_planner.show())

        self.actionConvert_Timebase_Frequency.setStatusTip("Two way conversion between timebase and frequency")
        self.actionConvert_Timebase_Frequency.setToolTip("Two way conversion between timebase and frequency")
        self.actionConvert_Timebase_Frequency.setIcon(QtGui.QIcon(os.path.join(icons_path, 'freq_timebase_calc.png')))
        self.actionConvert_Timebase_Frequency.triggered.connect(lambda: self.freq_con.show())

        self.actionDamping_Box_Plotter.setStatusTip("Plot damping box data")
        self.actionDamping_Box_Plotter.setToolTip("Plot damping box data")
        self.actionDamping_Box_Plotter.setIcon(QtGui.QIcon(os.path.join(icons_path, 'db_plot 32.png')))
        self.actionDamping_Box_Plotter.triggered.connect(lambda: self.db_plot.show())

        self.actionUnpacker.setStatusTip("Unpack and organize a raw folder")
        self.actionUnpacker.setToolTip("Unpack and organize a raw folder")
        self.actionUnpacker.setIcon(QtGui.QIcon(os.path.join(icons_path, 'unpacker_1.png')))
        self.actionUnpacker.triggered.connect(lambda: self.unpacker.show())

        self.actionGPX_Creator.setStatusTip("GPX file creator")
        self.actionGPX_Creator.setToolTip("GPX file creator")
        self.actionGPX_Creator.setIcon(QtGui.QIcon(os.path.join(icons_path, 'gpx_creator_4.png')))
        self.actionGPX_Creator.triggered.connect(lambda: self.gpx_creator.show())

        # Actions
        self.actionDel_File = QAction("&Remove File", self)
        self.actionDel_File.setShortcut("Del")
        self.actionDel_File.triggered.connect(self.remove_file)
        self.addAction(self.actionDel_File)
        self.actionDel_File.setEnabled(False)

        self.actionClear_Files = QAction("&Clear All Files", self)
        self.actionClear_Files.setShortcut("Shift+Del")
        self.actionClear_Files.setStatusTip("Clear all files")
        self.actionClear_Files.setToolTip("Clear all files")
        self.actionClear_Files.triggered.connect(lambda: self.remove_file(rows=np.arange(self.table.rowCount())))

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
        self.share_client_cbox.stateChanged.connect(lambda: self.refresh_rows(rows='all'))
        self.share_grid_cbox.stateChanged.connect(lambda: self.refresh_rows(rows='all'))
        self.share_loop_cbox.stateChanged.connect(lambda: self.refresh_rows(rows='all'))

        self.client_edit.textChanged.connect(lambda: self.refresh_rows(rows='all'))
        self.grid_edit.textChanged.connect(lambda: self.refresh_rows(rows='all'))
        self.loop_edit.textChanged.connect(lambda: self.refresh_rows(rows='all'))

        self.share_range_cbox.stateChanged.connect(
            lambda: self.min_range_edit.setEnabled(self.share_range_cbox.isChecked()))
        self.share_range_cbox.stateChanged.connect(
            lambda: self.max_range_edit.setEnabled(self.share_range_cbox.isChecked()))
        # self.share_range_cbox.stateChanged.connect(self.refresh_table)

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

        self.reset_crs_btn.clicked.connect(self.reset_crs)

    def contextMenuEvent(self, event):
        """
        Right-click context menu items.
        :param event: Right-click event.
        :return: None
        """
        if self.table.underMouse():
            if self.table.selectionModel().selectedIndexes():
                selected_pems, rows = self.get_selected_pem_files()

                self.table.menu = QMenu(self.table)
                self.table.remove_file_action = QAction("&Remove", self)
                self.table.remove_file_action.triggered.connect(self.remove_file)
                self.table.remove_file_action.setIcon(QtGui.QIcon(os.path.join(icons_path, 'remove.png')))

                self.table.open_file_action = QAction("&Open", self)
                self.table.open_file_action.triggered.connect(self.open_in_text_editor)
                self.table.open_file_action.setIcon(QtGui.QIcon(os.path.join(icons_path, 'txt_file.png')))

                self.table.save_file_action = QAction("&Save", self)
                self.table.save_file_action.setIcon(QtGui.QIcon(os.path.join(icons_path, 'save.png')))
                self.table.save_file_action.triggered.connect(self.save_pem_files)

                self.table.export_pem_action = QAction("&Export...", self)
                self.table.export_pem_action.triggered.connect(lambda: self.export_pem_files(selected=True))

                self.table.save_file_as_action = QAction("&Save As...", self)
                self.table.save_file_as_action.triggered.connect(self.save_pem_file_as)

                self.table.save_as_xyz_action = QAction("&Save As XYZ...", self)
                self.table.save_as_xyz_action.triggered.connect(lambda: self.save_as_xyz(selected=True))

                self.table.print_plots_action = QAction("&Print Plots", self)
                self.table.print_plots_action.setIcon(QtGui.QIcon(os.path.join(icons_path, 'pdf.png')))
                self.table.print_plots_action.triggered.connect(lambda: self.print_plots(selected_files=True))

                self.table.extract_stations_action = QAction("&Extract Stations", self)
                self.table.extract_stations_action.triggered.connect(self.show_station_splitter)

                self.table.calc_mag_dec = QAction("&Magnetic Declination", self)
                self.table.calc_mag_dec.setIcon(QtGui.QIcon(os.path.join(icons_path, 'mag_field.png')))
                self.table.calc_mag_dec.triggered.connect(lambda: self.show_mag_dec(selected_pems[0]))

                self.table.view_3d_section_action = QAction("&View 3D Section", self)
                self.table.view_3d_section_action.setIcon(QtGui.QIcon(os.path.join(icons_path, 'section_3d.png')))
                self.table.view_3d_section_action.triggered.connect(self.show_section_3d_viewer)

                self.table.average_action = QAction("&Average", self)
                self.table.average_action.triggered.connect(lambda: self.average_pem_data(selected=True))
                self.table.average_action.setIcon(QtGui.QIcon(os.path.join(icons_path, 'average.png')))

                self.table.split_action = QAction("&Split Channels", self)
                self.table.split_action.triggered.connect(lambda: self.split_pem_channels(selected=True))
                self.table.split_action.setIcon(QtGui.QIcon(os.path.join(icons_path, 'split.png')))

                self.table.scale_current_action = QAction("&Scale Current", self)
                self.table.scale_current_action.triggered.connect(lambda: self.scale_pem_current(selected=True))
                self.table.scale_current_action.setIcon(QtGui.QIcon(os.path.join(icons_path, 'current.png')))

                self.table.scale_ca_action = QAction("&Scale Coil Area", self)
                self.table.scale_ca_action.triggered.connect(lambda: self.scale_pem_coil_area(selected=True))
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
                self.table.rename_lines_action.triggered.connect(lambda: self.show_batch_renamer(type='Line'))

                self.table.rename_files_action = QAction("&Rename Files", self)
                self.table.rename_files_action.triggered.connect(lambda: self.show_batch_renamer(type='File'))

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
                if len(self.table.selectionModel().selectedRows()) == 1:
                    self.table.menu.addSeparator()
                    self.table.menu.addAction(self.table.share_loop_action)
                    if all([f.is_borehole() for f in selected_pems]):
                        self.table.menu.addAction(self.table.share_collar_action)
                        self.table.menu.addAction(self.table.share_segments_action)
                    elif all([not f.is_borehole() for f in selected_pems]):
                        self.table.menu.addAction(self.table.share_station_gps_action)
                if len(self.table.selectionModel().selectedRows()) > 1:
                    self.table.menu.addSeparator()
                    self.table.menu.addAction(self.table.rename_lines_action)
                    self.table.menu.addAction(self.table.rename_files_action)
                self.table.menu.addSeparator()
                if all([f.is_borehole() for f in selected_pems]):
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
        """
        Controls which files can be drag-and-dropped into the program. Conditions are based on the file type of each
        file being dragged, and which widget they are being dragged onto.
        :param e: PyQT event
        """
        urls = [url.toLocalFile() for url in e.mimeData().urls()]
        pem_files = False
        text_files = False
        ri_files = False
        inf_files = False
        gpx_files = False

        # Files must all be the same extension
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

    def change_pem_info_tab(self, tab_num):
        """
        Slot: Change the tab for each pemInfoWidget to the same
        :param tab_num: tab index number to change to
        """
        self.tab_num = tab_num
        if len(self.pem_info_widgets) > 0:
            for widget in self.pem_info_widgets:
                widget.tabs.setCurrentIndex(self.tab_num)

    def block_signals(self, bool):
        print(f'Blocking all signals {bool}')
        for thing in [self.table, self.client_edit, self.grid_edit, self.loop_edit, self.min_range_edit,
                      self.max_range_edit]:
            thing.blockSignals(bool)

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

    def reset_crs(self):
        self.systemCBox.setCurrentIndex(0)
        self.zoneCBox.setCurrentIndex(0)
        self.datumCBox.setCurrentIndex(0)

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
            t2 = time.time()
            self.pg.setText(f"Opening {pem_file.filename}")

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
            print(f"Time to open PIW: {time.time() - t2}")
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
                pems = natsort.humansorted(pems, key=lambda x: x.filename)
                i = pems.index(pem_file)
            return i

        def fill_crs(pem_file):
            """
            Fill CRS from the file to the main table's CRS drop down menus
            :param pem_file: PEMFile object
            """
            crs = pem_file.get_crs()
            if crs:
                self.systemCBox.setCurrentIndex(self.gps_systems.index(crs.System))
                if crs.system == 'UTM':
                    hemis = 'North' if crs.north is True else 'South'
                    self.zoneCBox.setCurrentIndex(self.gps_zones.index(f"{crs.zone} {hemis}"))
                self.datumCBox.setCurrentIndex(self.gps_datums.index(crs.datum))

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

        t1 = time.time()
        parser = PEMParser()
        self.table.setUpdatesEnabled(False)
        self.stackedWidget.show()
        self.pemInfoDockWidget.show()

        # Start the progress bar
        self.start_pg(min=0, max=len(pem_files))
        count = 0

        if not self.autoSortLoopsCheckbox.isChecked():
            self.message.warning(self, 'Warning', "Loops aren't being sorted.")

        for pem_file in pem_files:
            t3 = time.time()
            # Create a PEMFile object if a filepath was passed
            if not isinstance(pem_file, PEMFile):
                print(f'Parsing {os.path.basename(pem_file)}')
                pem_file = parser.parse(pem_file)

            # Check if the file is already opened in the table. Won't open if it is.
            if is_opened(pem_file):
                self.statusBar().showMessage(f"{pem_file.filename} is already opened", 2000)
            else:
                # Create the PEMInfoWidget
                pem_widget = add_info_widget(pem_file)
                # Fill the shared header text boxes for the first file opened
                if not self.pem_files:
                    share_header(pem_file)
                # Fill CRS from the file if project CRS currently empty
                if self.systemCBox.currentText() == '' and self.datumCBox.currentText() == '':
                    fill_crs(pem_file)

                t5 = time.time()
                i = get_insertion_point(pem_file)
                print(f"Time to calculate insertion point: {time.time() - t5}")
                self.pem_files.insert(i, pem_file)
                self.pem_info_widgets.insert(i, pem_widget)
                self.stackedWidget.insertWidget(i, pem_widget)
                self.table.insertRow(i)
                t4 = time.time()
                self.fill_pem_row(pem_file, i)
                print(f"Time to fill row: {time.time() - t4}")

                # Progress the progress bar
                count += 1
                self.pg.setValue(count)
                print(f"Time to open PEM file: {time.time() - t3}")

        # Set the shared range boxes
        self.fill_share_range()

        self.table.setUpdatesEnabled(True)
        self.pg.hide()
        self.table.resizeColumnsToContents()
        print(f"Time to open all PEM files: {time.time() - t1}")

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
                self.line_adder.add_df(line.get_line(sorted=self.autoSortStationsCheckbox.isChecked()))
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
                self.loop_adder.add_df(loop.get_loop(sorted=self.autoSortLoopsCheckbox.isChecked()))
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
        def get_crs(filepath):
            crs = {}
            with open(filepath, 'r') as in_file:
                file = in_file.read()

            crs['Coordinate System'] = re.findall('Coordinate System:\W+(?P<System>.*)', file)[0]
            crs['Coordinate Zone'] = re.findall('Coordinate Zone:\W+(?P<Zone>.*)', file)[0]
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
            current_tab = pem_info_widget.tabs.currentWidget()
            # TODO this
            if current_tab == pem_info_widget.Station_GPS_Tab:
                pem_info_widget.add_station_gps(file)
            elif current_tab == pem_info_widget.Geometry_Tab:
                pem_info_widget.add_geometry(file)
            elif current_tab == pem_info_widget.Loop_GPS_Tab:
                pem_info_widget.add_loop_gps(file)
            else:
                pass

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
            browser.setWindowIcon(QtGui.QIcon(os.path.join(icons_path, 'txt_file.png')))
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
                else:
                    pass
        else:
            pass

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
        save_file = pem_file.to_string()
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

    def save_pem_files(self, selected=False):
        """
        Save all selected PEM files.
        :param selected: Bool: if True, saves all opened PEM files instead of only the selected ones.
        :return: None
        """
        if self.pem_files:
            if selected is True:
                pem_files, rows = self.get_selected_pem_files()
            else:
                pem_files, rows = self.pem_files, np.arange(self.table.rowCount())

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
        if __name__ == '__main__':
            file_path = r'C:\Users\Mortulo\PycharmProjects\PEMPro\sample_files\test.PEM'
            row = 0
        else:
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
                bh_projection = pem_file.geometry.get_projection(num_segments=100, crs=crs)
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
            self.window().statusBar().showMessage('Cancelled.', 2000)

    def save_as_xyz(self, selected=False):
        """
        Save the selected PEM files as XYZ files. Only for surface PEM files.
        :param selected: bool: Save selected files. False means all opened files will be saved.
        :return: None
        """

        def serialize_pem(pem_file):
            """
            Create a str in XYZ format of the pem file's data
            :param pem_file: PEMFile object
            :return: str
            """

            def get_station_gps(row):
                """
                Add the GPS information for each station
                :param row: pandas DataFrame row
                :return: pandas DataFrame row
                """
                value = row.c_Station
                filt = gps['Station'] == value

                if filt.any() or filt.all():
                    row['Easting'] = gps[filt]['Easting'].iloc[0]
                    row['Northing'] = gps[filt]['Northing'].iloc[0]
                    row['Elevation'] = gps[filt]['Elevation'].iloc[0]
                return row

            df = pd.DataFrame(columns=['Easting', 'Northing', 'Elevation', 'Component', 'Station', 'c_Station'])
            pem_data = pem_file.get_data(sorted=True).dropna()
            gps = pem_file.line.get_line(sorted=True).drop_duplicates('Station')

            assert not pem_file.is_borehole(), 'Can only create XYZ file with surface PEM files.'
            assert not gps.empty, 'No GPS found.'
            print(f'Saving XYZ file...')

            df['Component'] = pem_data.Component.copy()
            df['Station'] = pem_data.Station.copy()
            df['c_Station'] = df.Station.map(convert_station)
            # Add the GPS
            df = df.apply(get_station_gps, axis=1)

            # Create a dataframe of the readings with channel number as columns
            channel_data = pd.DataFrame(columns=range(int(pem_file.number_of_channels)))
            channel_data = pem_data.apply(lambda x: pd.Series(x.Reading), axis=1)
            # Merge the two data frames
            df = pd.concat([df, channel_data], axis=1).drop('c_Station', axis=1)
            str_df = df.apply(lambda x: x.astype(str).str.cat(sep=' '), axis=1)
            str_df = '\n'.join(str_df.to_list())
            return str_df

        if selected:
            pem_files, rows = self.get_selected_pem_files()
        else:
            pem_files, rows = self.pem_files, np.arange(self.table.rowCount())

        if pem_files:
            default_path = os.path.split(self.pem_files[-1].filepath)[0]
            if __name__ == '__main__':
                file_dir = default_path
            else:
                file_dir = self.dialog.getExistingDirectory(self, '', default_path, QFileDialog.DontUseNativeDialog)

            if file_dir:
                for pem_file in pem_files:
                    if not pem_file.is_borehole():
                        file_name = os.path.splitext(pem_file.filepath)[0] + '.xyz'
                        xyz_file = serialize_pem(pem_file)
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

        self.window().statusBar().showMessage(f"Saving PEM {'file' if len(pem_files) == 1 else 'files'}...")
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
                updated_file = self.update_pem_file_from_table(pem_file, row)
                file_name = os.path.splitext(os.path.basename(pem_file.filepath))[0]
                extension = os.path.splitext(pem_file.filepath)[-1]
                if export_final is True:
                    # Remove underscore-dates and tags
                    file_name = re.sub('_\d+', '', re.sub('\[-?\w\]', '', file_name))
                    if not pem_file.is_borehole():
                        file_name = file_name.upper()
                        if file_name.lower()[0] == 'c':
                            file_name = file_name[1:]
                        if pem_file.is_averaged() and 'av' not in file_name.lower():
                            file_name = file_name + 'Av'

                updated_file.filepath = os.path.join(file_dir, file_name + extension)
                updated_file.filename = os.path.basename(updated_file.filepath)
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
            crs = self.get_crs()

            if not crs.is_valid():
                self.message.information(self, 'Invalid CRS', 'CRS is incomplete and/or invalid.')
                return

            system = crs.system
            # zone = ' Zone ' + self.zoneCBox.currentText() if self.zoneCBox.isEnabled() else ''
            zone = ' Zone ' + crs.zone if self.zoneCBox.isEnabled() else ''
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
                            loop = pem_file.get_loop(sorted=self.autoSortLoopsCheckbox.isChecked(), closed=False)
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
                self.window().statusBar().showMessage("Export complete.", 2000)
            else:
                self.window().statusBar().showMessage("No files to export.", 2000)

    def fill_pem_row(self, pem_file, row):
        """
        Adds the information from a PEM file to the main table. Blocks the table signals while doing so.
        :param pem_file: PEMFile object
        :param row: int, row of the PEM file in the table
        :return: None
        """
        print(f"Filling {pem_file.filename}'s information to the table")
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

    def color_table_row_text(self, row):
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

    # def refresh_table(self, single_row=False):
    #     """
    #     Deletes and re-populates the table rows with the new information. Blocks table signals while doing so.
    #     :return: None
    #     """
    #     if self.pem_files:
    #         self.table.blockSignals(True)
    #         if single_row:
    #             index = self.stackedWidget.currentIndex()
    #             print(f'Refreshing table row {index}')
    #             self.refresh_table_row(self.pem_files[index], index)
    #         else:
    #             print('Refreshing entire table')
    #             while self.table.rowCount() > 0:
    #                 self.table.removeRow(0)
    #             for pem_file in self.pem_files:
    #                 self.add_pem_to_table(pem_file)
    #         if self.allow_signals:
    #             self.table.blockSignals(False)
    #     else:
    #         pass

    def refresh_rows(self, rows=None, current_index=False):
        """
        Clear the row and fill in the PEM file's information
        :param rows: Corresponding row of the PEM file in the main table
        :param current_index: bool, whether to refresh the row corresponding to the currently opened PEMInfoWidget
        :return: None
        """
        if current_index:
            rows = list(self.stackedWidget.currentIndex())
        else:
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
            """
            Add the CRS from the table as a note to the PEM file.
            :return: None
            """
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
        pem_file.filename = os.path.basename(pem_file.filepath)
        pem_file.date = self.table.item(table_row, self.table_columns.index('Date')).text()
        pem_file.client = self.table.item(table_row, self.table_columns.index('Client')).text()
        pem_file.grid = self.table.item(table_row, self.table_columns.index('Grid')).text()
        pem_file.line_name = self.table.item(table_row, self.table_columns.index('Line/Hole')).text()
        pem_file.loop_name = self.table.item(table_row, self.table_columns.index('Loop')).text()
        pem_file.current = self.table.item(table_row, self.table_columns.index('Current')).text()
        pem_file.loop = self.stackedWidget.widget(table_row).get_loop()

        if pem_file.is_borehole():
            pem_file.geometry = self.stackedWidget.widget(table_row).get_geometry()
        else:
            pem_file.line = self.stackedWidget.widget(table_row).get_line()

        return pem_file

    def backup_files(self):
        """
        Create a backup (.bak) file for each opened PEM file, saved in a backup folder.
        :return: None
        """
        for pem_file in self.pem_files:
            print(f"Backing up {os.path.basename(pem_file.filepath)}")
            pem_file = copy.deepcopy(pem_file)
            self.write_pem_file(pem_file, backup=True, tag='[B]', remove_old=False)
        self.window().statusBar().showMessage(f'Backup complete. Backed up {len(self.pem_files)} PEM files.', 2000)

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

        for row in rows:
            self.table.removeRow(row)
            self.stackedWidget.removeWidget(self.stackedWidget.widget(row))
            del self.pem_files[row]
            del self.pem_info_widgets[row]

        if len(self.pem_files) == 0:
            self.stackedWidget.hide()
            self.pemInfoDockWidget.hide()
            self.client_edit.setText('')
            self.grid_edit.setText('')
            self.loop_edit.setText('')
            self.min_range_edit.setText('')
            self.max_range_edit.setText('')
            self.reset_crs()

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

    def get_crs(self):
        """
        Return a CRS object based on the CRS information in the PEM Editor window
        :return: CRS object
        """
        system = self.systemCBox.currentText()
        zone = self.zoneCBox.currentText()
        datum = self.datumCBox.currentText()

        crs_dict = {'System': system, 'Zone': zone, 'Datum': datum}
        crs = CRS(crs_dict)
        return crs

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

        self.start_pg(min=0, max=len(pem_files))
        count = 0
        for pem_file, row in zip(pem_files, rows):
            if not pem_file.is_averaged():
                print(f"Averaging {pem_file.filename}")
                self.pg.setText(f"Averaging {pem_file.filename}")
                # Save a backup of the un-averaged file first
                if self.auto_create_backup_files_cbox.isChecked():
                    self.write_pem_file(copy.deepcopy(pem_file), backup=True, tag='[-A]', remove_old=False)
                t = time.time()
                pem_file = pem_file.average()
                print(f"Time to average file: {time.time() - t}")
                t2 = time.time()
                self.pem_info_widgets[row].open_file(pem_file, parent=self)
                print(f"Time to open PEM info widget: {time.time() - t2}")
                # self.refresh_table_row(pem_file, row)
                count += 1
                self.pg.setValue(count)
        self.refresh_rows(rows=rows)
        self.pg.hide()

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

        self.start_pg(min=0, max=len(pem_files))
        count = 0
        for pem_file, row in zip(pem_files, rows):
            if not pem_file.is_split():
                print(f"Splitting channels for {os.path.basename(pem_file.filepath)}")
                self.pg.setText(f"Splitting channels for {pem_file.filename}")
                if self.auto_create_backup_files_cbox.isChecked():
                    self.write_pem_file(copy.deepcopy(pem_file), backup=True, tag='[-S]', remove_old=False)
                t = time.time()
                pem_file = pem_file.split()
                print(f"Time to split file: {time.time() - t}")
                t2 = time.time()
                self.pem_info_widgets[row].open_file(pem_file, parent=self)  # Emits a signal to refresh the table row
                print(f"Time to open PEM info widget: {time.time() - t2}")
                count += 1
                self.pg.setValue(count)
        self.pg.hide()

    def scale_pem_coil_area(self, coil_area=None, selected=False):
        """
        Scales the data according to the coil area change
        :param coil_area: int:  coil area to scale to
        :param selected: bool, True will only export selected rows.
        """
        if not coil_area:
            coil_area, okPressed = QInputDialog.getInt(self, "Set Coil Areas", "Coil Area:")
            if not okPressed:
                return

        if selected is True:
            pem_files, rows = self.get_selected_pem_files()
        else:
            pem_files, rows = self.pem_files, np.arange(self.table.rowCount())

        for pem_file, row in zip(pem_files, rows):
            print(f"Performing coil area change for {pem_file.filename}")
            pem_file = pem_file.scale_coil_area(coil_area)
            self.refresh_rows(rows=row)

    def scale_pem_current(self, selected=False):
        """
        Scale the data by current for the selected PEM Files
        :param selected: bool, True will only export selected rows.
        :return: None
        """
        current, okPressed = QInputDialog.getDouble(self, "Scale Current", "Current:")
        if okPressed:
            if selected is True:
                pem_files, rows = self.get_selected_pem_files()
            else:
                pem_files, rows = self.pem_files, np.arange(self.table.rowCount())

            for pem_file, row in zip(pem_files, rows):
                print(f"Performing current change for {pem_file.filename}")
                pem_file = pem_file.scale_current(current)
                self.refresh_rows(rows=row)

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
                    self.split_pem_channels(pem_files=pem_files)
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
                        self.split_pem_channels(pem_files=pem_files)
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
                        self.split_pem_channels(pem_files=pem_files)
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

    # def sort_all_station_gps(self):
    #     """
    #     Sorts the station GPS (based on positions only) of all opened PEM files.
    #     :return: None
    #     """
    #     if self.pem_files:
    #         for i in range(self.stackedWidget.count()):
    #             widget = self.stackedWidget.widget(i)
    #             if widget.station_gps:
    #                 widget.fill_station_table(widget.station_gps.get_sorted_gps(widget.get_line()))
    #             else:
    #                 pass
    #         self.window().statusBar().showMessage('All stations have been sorted', 2000)
    #
    # def sort_all_loop_gps(self):
    #     """
    #     Sorts the loop GPS (counter-clockwise) of all opened PEM files.
    #     :return: None
    #     """
    #     if self.pem_files:
    #         for i in range(self.stackedWidget.count()):
    #             widget = self.stackedWidget.widget(i)
    #             if widget.loop_gps:
    #                 widget.fill_loop_table(widget.loop_gps.get_sorted_gps(widget.get_loop()))
    #             else:
    #                 pass
    #         self.window().statusBar().showMessage('All loops have been sorted', 2000)

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
        widget = self.pem_info_widgets[self.table.currentRow()]
        widget_loop = widget.get_loop().df
        if not widget_loop.empty:
            for widget in self.pem_info_widgets:
                widget.fill_gps_table(widget_loop, widget.loopGPSTable)

    def share_collar(self):
        """
        Share the collar GPS of one file with all other opened PEM files. Will only do so for borehole files.
        :return: None
        """
        widget = self.pem_info_widgets[self.table.currentRow()]
        widget_collar = widget.get_collar().df
        if not widget_collar.empty:
            for widget in list(filter(lambda x: x.pem_file.is_borehole(), self.pem_info_widgets)):
                widget.fill_gps_table(widget_collar, widget.collarGPSTable)

    def share_segments(self):
        """
        Share the segments of one file with all other opened PEM files. Will only do so for borehole files.
        :return: None
        """
        widget = self.pem_info_widgets[self.table.currentRow()]
        wigdet_segments = widget.get_segments().df
        if not wigdet_segments.empty:
            for widget in list(filter(lambda x: x.pem_file.is_borehole(), self.pem_info_widgets)):
                widget.fill_gps_table(wigdet_segments, widget.geometryTable)

    def share_station_gps(self):
        """
        Share the station GPS of one file with all other opened PEM files. Will only do so for surface files.
        :return: None
        """
        widget = self.pem_info_widgets[self.table.currentRow()]
        widget_line = widget.get_line().df
        if not widget_line.empty:
            for widget in list(filter(lambda x: not x.pem_file.is_borehole(), self.pem_info_widgets)):
                widget.fill_gps_table(widget_line, widget.stationGPSTable)

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
            self.window().statusBar().showMessage(f'{num_repeat_stations} repeat station(s) automatically renamed.',
                                                  2000)

    def show_mag_dec(self, pem_file):
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
        m.calc_mag_dec(pem_file, crs)
        m.show()

    def show_station_splitter(self):
        """
        Opens the PEMFileSplitter window, which will allow selected stations to be saved as a new PEM file.
        :return: None
        """
        pem_file, row = self.get_selected_pem_files()
        self.station_splitter.open(pem_file[0])
        self.station_splitter.show()

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

    def show_batch_renamer(self, type):
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
            if len(self.batch_name_editor.pem_files) > 0:
                self.batch_name_editor.accept_changes()
                for i, row in enumerate(rows):
                    self.pem_files[row] = self.batch_name_editor.pem_files[i]
                self.refresh_table()

        pem_files, rows = self.get_selected_pem_files()
        if not pem_files:
            pem_files, rows = self.pem_files, range(self.table.rowCount())

        self.batch_name_editor.open(pem_files, type=type)
        self.batch_name_editor.buttonBox.accepted.connect(rename_pem_files)
        self.batch_name_editor.acceptChangesSignal.connect(rename_pem_files)
        self.batch_name_editor.buttonBox.rejected.connect(self.batch_name_editor.close)
        self.batch_name_editor.show()

    def show_ri_importer(self):
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
        self.ri_importer.acceptImportSignal.connect(open_ri_files)
        self.ri_importer.show()


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
        self.setWindowIcon(QtGui.QIcon(os.path.join(icons_path, 'freq_timebase_calc.png')))
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


class MagDeclinationCalculator(QMainWindow):
    """
    Converts the first coordinates found into lat lon. Must have GPS information in order to convert to lat lon.
    """
    def __init__(self, parent=None):
        super().__init__()
        self.parent = parent
        self.setWindowTitle('Magnetic Declination')
        self.setWindowIcon(QtGui.QIcon(os.path.join(icons_path, 'mag_field.png')))
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

        assert not crs.is_nad27, 'Incompatible datum. Must be either NAD 1983 or WGS 1984'
        assert crs.is_valid(), 'GPS coordinate system information is incomplete'

        if pem_file.has_collar_gps():
            coords = pem_file.get_collar(crs=crs)
        elif pem_file.has_loop_gps():
            coords = pem_file.get_loop(crs=crs)
        elif pem_file.has_line_coords():
            coords = pem_file.get_line(crs=crs)
        else:
            self.message.information(self, 'Error', 'No GPS')
            return

        lat, lon, elevation = coords.iloc[0]['Latitude'], coords.iloc[0]['Longitude'], coords.iloc[0]['Elevation']

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
    mw = PEMEditor()
    # mw.show()

    # pg = PEMGetter()
    # pem_files = pg.get_pems(client='PEM Splitting', number=5)
    pem_files = r'C:\Users\Mortulo\PycharmProjects\PEMPro\sample_files\PEMGetter files\PEM Splitting\1410S (flux).PEM'
    mw.open_pem_files(pem_files)
    # mw.average_pem_data()
    # mw.split_pem_channels(pem_files[0])
    mw.show()
    # mw.reverse_all_data('X')

    # mw.open_gps_files([r'C:\Users\Mortulo\PycharmProjects\PEMPro\sample_files\Loop GPS\LOOP 240.txt'])
    # mw.save_as_xyz()
    # mw.open_gps_files([r'C:\Users\Mortulo\PycharmProjects\PEMPro\sample_files\Loop GPS\LOOP4.txt'])
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
    import cProfile
    import pstats
    main()
    # cProfile.run('main()', 'restats')
    # p = pstats.Stats('restats')
    # p.sort_stats('cumulative').print_stats(.5)

    # p.sort_stats('time', 'cumulative').print_stats()
    # p.strip_dirs().sort_stats(-1).print_stats()
