import cProfile
import copy
import datetime
import logging
import os
import re
import pstats
import sys
import time
import utm
import numpy as np
import simplekml
from shutil import copyfile
from decimal import getcontext
from itertools import chain, groupby
from collections import defaultdict
from PyQt5 import (QtCore, QtGui, uic)
from PyQt5.QtWidgets import (QWidget, QMainWindow, QApplication, QDesktopWidget, QMessageBox, QFileDialog,
                             QAbstractScrollArea, QTableWidgetItem, QAction, QMenu, QProgressBar, QCheckBox,
                             QInputDialog, QHeaderView, QTableWidget, QErrorMessage, QDialogButtonBox, QVBoxLayout)
import matplotlib as mpl
import matplotlib.pyplot as plt
# from pyqtspinner.spinner import WaitingSpinner
import colorcet as cc
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas, NavigationToolbar2QT as NavigationToolbar
from mpl_toolkits.mplot3d import Axes3D  # Needed for 3D plots
from matplotlib.figure import Figure
from src.pem.pem_file import PEMFile
from src.gps.gps_editor import GPSParser, INFParser, GPXEditor
from src.pem.pem_file_editor import PEMFileEditor
from src.pem.pem_parser import PEMParser
from src.pem.pem_plotter import PEMPrinter, Map3D, Section3D, CustomProgressBar, MapPlotMethods, ContourMap
from src.pem.pem_serializer import PEMSerializer
from src.pem.xyz_serializer import XYZSerializer
from src.qt_py.pem_info_widget import PEMFileInfoWidget
from src.ri.ri_file import RIFile

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s', datefmt='%d-%b-%y %H:%M:%S')

getcontext().prec = 6

if getattr(sys, 'frozen', False):
    # If the application is run as a bundle, the pyInstaller bootloader
    # extends the sys module by a flag frozen=True and sets the app
    # path into variable _MEIPASS'.
    application_path = sys._MEIPASS
    editorWindowCreatorFile = 'qt_ui\\pem_editor_window.ui'
    lineNameEditorCreatorFile = 'qt_ui\\line_name_editor.ui'
    planMapOptionsCreatorFile = 'qt_ui\\plan_map_options.ui'
    pemFileSplitterCreatorFile = 'qt_ui\\pem_file_splitter.ui'
    map3DCreatorFile = 'qt_ui\\3D_map.ui'
    section3DCreatorFile = 'qt_ui\\3D_section.ui'
    contourMapCreatorFile = 'qt_ui\\contour_map.ui'
    icons_path = 'icons'
else:
    application_path = os.path.dirname(os.path.abspath(__file__))
    editorWindowCreatorFile = os.path.join(os.path.dirname(application_path), 'qt_ui\\pem_editor_window.ui')
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

sys._excepthook = sys.excepthook


def exception_hook(exctype, value, traceback):
    print(exctype, value, traceback)
    sys._excepthook(exctype, value, traceback)
    sys.exit(1)


sys.excepthook = exception_hook


def alpha_num_sort(string):
    """ Returns all numbers on 5 digits to let sort the string with numeric order.
    Ex: alphaNumOrder("a6b12.125")  ==> "a00006b00012.00125"
    """
    return ''.join([format(int(x), '05d') if x.isdigit()
                    else x for x in re.split(r'(\d+)', string)])


class PEMEditorWindow(QMainWindow, Ui_PEMEditorWindow):
    # logging.info('PEMEditor')

    def __init__(self, parent=None):
        super().__init__()
        self.parent = parent
        self.initUi()

        self.pem_files = []
        self.pem_info_widgets = []
        self.tab_num = 2

        self.dialog = QFileDialog()
        self.parser = PEMParser()
        self.file_editor = PEMFileEditor()
        self.message = QMessageBox()
        self.error = QErrorMessage()
        self.gps_parser = GPSParser()
        self.gpx_editor = GPXEditor()
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

        self.initMenus()
        self.initSignals()
        self.allow_signals = True

        self.stackedWidget.hide()
        self.pemInfoDockWidget.hide()
        self.plotsDockWidget.hide()
        # self.plotsDockWidget.setWidget(self.tabWidget)
        # self.addDockWidget(QtCore.Qt.RightDockWidgetArea, self.stackedWidget)

        self.gps_systems = ['', 'UTM']
        self.gps_zones = [''] + [f"{num} North" for num in range(1, 61)] + [f"{num} South" for num in range(1, 61)]
        self.gps_datums = ['', 'NAD 1927', 'NAD 1983', 'WGS 1984']

        self.create_table()
        self.populate_gps_boxes()

    def initUi(self):
        """
        Initializing the UI.
        :return: None
        """
        # logging.info('PEMEditor - Initializing UI')
        def center_window(self):
            qtRectangle = self.frameGeometry()
            centerPoint = QDesktopWidget().availableGeometry().center()
            qtRectangle.moveCenter(centerPoint)
            self.move(qtRectangle.topLeft())

        self.setupUi(self)

        self.setWindowTitle("PEMEditor")
        self.setWindowIcon(
            QtGui.QIcon(os.path.join(icons_path, 'pem_editor_3.png')))
        self.setGeometry(500, 300, 1700, 900)
        center_window(self)

    def initMenus(self):
        """
        Initializing all actions.
        :return: None
        """
        # logging.info('PEMEditor - Initializing Actions')
        self.setAcceptDrops(True)

        # 'File' menu
        self.openFile = QAction("&Open...", self)
        self.openFile.setShortcut("Ctrl+O")
        self.openFile.setStatusTip('Open file')
        self.openFile.triggered.connect(self.open_file_dialog)

        self.saveFiles = QAction("&Save Files", self)
        self.saveFiles.setShortcut("Ctrl+S")
        self.saveFiles.setStatusTip("Save all files")
        self.saveFiles.triggered.connect(lambda: self.save_pem_files(all=True))

        self.save_files_as_xyz_action = QAction("&Save Files As XYZ", self)
        self.save_files_as_xyz_action.setStatusTip("Save all files as XYZ files. Only for surface surveys.")
        self.save_files_as_xyz_action.triggered.connect(lambda: self.save_as_xyz(selected_files=False))

        self.export_pems_action = QAction("&Export Files...", self)
        self.export_pems_action.setShortcut("F11")
        self.export_pems_action.setStatusTip("Export all files to a specified location.")
        self.export_pems_action.triggered.connect(lambda: self.export_pem_files(all=True))

        self.export_pem_files_action = QAction("&Export Final PEM Files...", self)
        self.export_pem_files_action.setShortcut("F9")
        self.export_pem_files_action.setStatusTip("Export the final PEM files")
        self.export_pem_files_action.triggered.connect(lambda: self.export_pem_files(export_final=True))

        self.print_plots_action = QAction("&Print Plots to PDF...", self)
        self.print_plots_action.setShortcut("F12")
        self.print_plots_action.setStatusTip("Print plots to a PDF file")
        self.print_plots_action.triggered.connect(self.print_plots)

        self.del_file = QAction("&Remove File", self)
        self.del_file.setShortcut("Del")
        self.del_file.triggered.connect(self.remove_file_selection)
        self.addAction(self.del_file)
        self.del_file.setEnabled(False)

        self.clearFiles = QAction("&Clear All Files", self)
        self.clearFiles.setShortcut("Shift+Del")
        self.clearFiles.setStatusTip("Clear all files")
        self.clearFiles.triggered.connect(self.clear_files)

        # self.sort_files_action = QAction("&Sort Table", self)
        # self.sort_files_action.setStatusTip("Sort all files in the table.")
        # self.sort_files_action.triggered.connect(self.sort_files)

        self.backup_files_action = QAction("&Backup Files", self)
        # self.sortFiles.setShortcut("Shift+Del")
        self.backup_files_action.setStatusTip("Backup all files in the table.")
        self.backup_files_action.triggered.connect(self.backup_files)

        self.import_ri_files_action = QAction("&Import RI Files", self)
        self.import_ri_files_action.setShortcut("Ctrl+I")
        self.import_ri_files_action.setStatusTip("Import multiple RI files")
        self.import_ri_files_action.triggered.connect(self.import_ri_files)

        self.fileMenu = self.menubar.addMenu('&File')
        self.fileMenu.addAction(self.openFile)
        self.fileMenu.addAction(self.saveFiles)
        self.fileMenu.addAction(self.save_files_as_xyz_action)
        self.fileMenu.addAction(self.export_pems_action)
        self.fileMenu.addAction(self.export_pem_files_action)
        self.fileMenu.addAction(self.backup_files_action)
        # self.fileMenu.addAction(self.sort_files_action)
        self.fileMenu.addSeparator()
        self.fileMenu.addAction(self.clearFiles)
        self.fileMenu.addSeparator()
        self.fileMenu.addAction(self.import_ri_files_action)
        self.fileMenu.addAction(self.print_plots_action)

        # PEM menu
        self.averageAllPems = QAction("&Average All PEM Files", self)
        self.averageAllPems.setStatusTip("Average all PEM files")
        self.averageAllPems.setShortcut("F5")
        self.averageAllPems.triggered.connect(lambda: self.average_pem_data(all=True))

        self.splitAllPems = QAction("&Split All PEM Files", self)
        self.splitAllPems.setStatusTip("Remove on-time channels for all PEM files")
        self.splitAllPems.setShortcut("F6")
        self.splitAllPems.triggered.connect(lambda: self.split_pem_channels(all=True))

        self.merge_action = QAction("&Merge", self)
        self.merge_action.triggered.connect(self.merge_pem_files_selection)
        self.merge_action.setShortcut("Shift+M")

        self.scaleAllCurrents = QAction("&Scale All Current", self)
        self.scaleAllCurrents.setStatusTip("Scale the current of all PEM Files to the same value")
        self.scaleAllCurrents.setShortcut("F7")
        self.scaleAllCurrents.triggered.connect(lambda: self.scale_pem_current(all=True))

        self.scaleAllCoilAreas = QAction("&Change All Coil Areas", self)
        self.scaleAllCoilAreas.setStatusTip("Scale all coil areas to the same value")
        self.scaleAllCoilAreas.setShortcut("F8")
        self.scaleAllCoilAreas.triggered.connect(lambda: self.scale_coil_area_selection(all=True))

        self.editLineNames = QAction("&Rename All Lines/Holes", self)
        self.editLineNames.setStatusTip("Rename all line/hole names")
        # self.editLineNames.setShortcut("F2")
        self.editLineNames.triggered.connect(lambda: self.batch_rename(type='Line'))

        self.editFileNames = QAction("&Rename All Files", self)
        self.editFileNames.setStatusTip("Rename all file names")
        # self.editFileNames.setShortcut("F3")
        self.editFileNames.triggered.connect(lambda: self.batch_rename(type='File'))

        self.PEMMenu = self.menubar.addMenu('&PEM')
        self.PEMMenu.addAction(self.editLineNames)
        self.PEMMenu.addAction(self.editFileNames)
        self.PEMMenu.addSeparator()
        self.PEMMenu.addAction(self.averageAllPems)
        self.PEMMenu.addAction(self.splitAllPems)
        self.PEMMenu.addSeparator()
        self.PEMMenu.addAction(self.scaleAllCurrents)
        self.PEMMenu.addAction(self.scaleAllCoilAreas)

        # GPS menu
        self.saveAsKMZFile = QAction("&Save as KMZ", self)
        self.saveAsKMZFile.setStatusTip("Create a KMZ file using all GPS in the opened PEM file(s)")
        self.saveAsKMZFile.setIcon(QtGui.QIcon(os.path.join(icons_path, 'google_earth.png')))
        self.saveAsKMZFile.triggered.connect(self.save_as_kmz)

        self.sortAllStationGps = QAction("&Sort All Station GPS", self)
        self.sortAllStationGps.setStatusTip("Sort the station GPS for every file")
        self.sortAllStationGps.triggered.connect(self.sort_all_station_gps)

        self.sortAllLoopGps = QAction("&Sort All Loop GPS", self)
        self.sortAllLoopGps.setStatusTip("Sort the loop GPS for every file")
        self.sortAllLoopGps.triggered.connect(self.sort_all_loop_gps)

        self.GPSMenu = self.menubar.addMenu('&GPS')
        self.GPSMenu.addAction(self.saveAsKMZFile)
        self.GPSMenu.addSeparator()
        self.GPSMenu.addAction(self.sortAllStationGps)
        self.GPSMenu.addAction(self.sortAllLoopGps)

        # Map menu
        self.show3DMap = QAction("&3D Map", self)
        self.show3DMap.setStatusTip("Show 3D map of all PEM files")
        self.show3DMap.setShortcut('Ctrl+M')
        self.show3DMap.setIcon(QtGui.QIcon(os.path.join(icons_path, '3d_map2.png')))
        self.show3DMap.triggered.connect(self.show_map_3d_viewer)

        self.showContourMap = QAction("&Contour Map", self)
        self.showContourMap.setIcon(QtGui.QIcon(os.path.join(icons_path, 'contour_map3.png')))
        self.showContourMap.setStatusTip("Show a contour map of surface PEM files")
        self.showContourMap.triggered.connect(self.show_contour_map_viewer)

        self.MapMenu = self.menubar.addMenu('&Map')
        self.MapMenu.addAction(self.show3DMap)
        self.MapMenu.addAction(self.showContourMap)

    def initSignals(self):
        """
        Initializing all signals.
        :return: None
        """
        # logging.info('PEMEditor - Initializing Signals')
        self.table.viewport().installEventFilter(self)

        self.table.installEventFilter(self)
        self.table.setFocusPolicy(QtCore.Qt.StrongFocus)

        self.table.itemSelectionChanged.connect(self.display_pem_info_widget)
        self.table.cellChanged.connect(self.table_value_changed)

        self.plan_map_options_btn.clicked.connect(self.plan_map_options.show)
        self.print_plots_btn.clicked.connect(self.print_plots)

        self.share_client_cbox.stateChanged.connect(self.toggle_share_client)
        self.share_grid_cbox.stateChanged.connect(self.toggle_share_grid)
        self.share_loop_cbox.stateChanged.connect(self.toggle_share_loop)
        # self.reset_header_btn.clicked.connect(self.fill_share_header)
        self.client_edit.textChanged.connect(lambda: self.refresh_table(single_row=False))
        self.grid_edit.textChanged.connect(lambda: self.refresh_table(single_row=False))
        self.loop_edit.textChanged.connect(lambda: self.refresh_table(single_row=False))

        self.share_range_checkbox.stateChanged.connect(self.toggle_share_range)
        self.reset_range_btn.clicked.connect(self.fill_share_range)
        self.hide_gaps_checkbox.stateChanged.connect(self.toggle_hide_gaps)
        self.min_range_edit.textChanged.connect(lambda: self.refresh_table(single_row=False))
        self.max_range_edit.textChanged.connect(lambda: self.refresh_table(single_row=False))
        self.auto_name_line_btn.clicked.connect(self.auto_name_lines)
        self.auto_merge_files_btn.clicked.connect(self.auto_merge_pem_files)

        self.reverseAllZButton.clicked.connect(lambda: self.reverse_all_data(comp='Z'))
        self.reverseAllXButton.clicked.connect(lambda: self.reverse_all_data(comp='X'))
        self.reverseAllYButton.clicked.connect(lambda: self.reverse_all_data(comp='Y'))
        self.rename_all_repeat_stations_btn.clicked.connect(self.rename_all_repeat_stations)

        self.systemCBox.currentIndexChanged.connect(self.toggle_zone_box)
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
                survey_type = selected_pems[0].survey_type.lower()

                self.table.menu = QMenu(self.table)
                self.table.remove_file_action = QAction("&Remove", self)
                self.table.remove_file_action.triggered.connect(self.remove_file_selection)

                self.table.open_file_action = QAction("&Open", self)
                self.table.open_file_action.triggered.connect(self.open_in_text_editor)

                self.table.save_file_action = QAction("&Save", self)
                self.table.save_file_action.triggered.connect(self.save_pem_files)

                self.table.export_pem_action = QAction("&Export...", self)
                self.table.export_pem_action.triggered.connect(self.export_pem_files)

                self.table.save_file_as_action = QAction("&Save As...", self)
                self.table.save_file_as_action.triggered.connect(self.save_pem_file_as)

                self.table.save_as_xyz_action = QAction("&Save As XYZ...", self)
                self.table.save_as_xyz_action.triggered.connect(lambda: self.save_as_xyz(selected_files=True))

                self.table.print_plots_action = QAction("&Print Plots", self)
                self.table.print_plots_action.triggered.connect(lambda: self.print_plots(selected_files=True))

                self.table.extract_stations_action = QAction("&Extract Stations", self)
                self.table.extract_stations_action.triggered.connect(self.extract_stations)

                self.table.view_3d_section_action = QAction("&View 3D Section", self)
                self.table.view_3d_section_action.setIcon(QtGui.QIcon(os.path.join(icons_path, 'section_3d.png')))
                self.table.view_3d_section_action.triggered.connect(self.show_section_3d_viewer)

                self.table.average_action = QAction("&Average", self)
                self.table.average_action.triggered.connect(self.average_pem_data)

                self.table.split_action = QAction("&Split Channels", self)
                self.table.split_action.triggered.connect(self.split_pem_channels)

                self.table.scale_current_action = QAction("&Scale Current", self)
                self.table.scale_current_action.triggered.connect(self.scale_pem_current)

                self.table.scale_ca_action = QAction("&Scale Coil Area", self)
                self.table.scale_ca_action.triggered.connect(self.scale_coil_area_selection)

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
            self.del_file.setEnabled(True)  # Makes the 'Del' shortcut work when the table is in focus
        elif source == self.table and event.type() == QtCore.QEvent.FocusOut:
            self.del_file.setEnabled(False)
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

    def open_in_text_editor(self):
        """
        Open the selected PEM File in a text editor
        """
        # logging.info('Opening PEM File in text editor')
        pem_files, rows = self.get_selected_pem_files()
        for pem_file in pem_files:
            os.startfile(pem_file.filepath)

    def open_file_dialog(self):
        """
        Open files through the file dialog
        """
        try:
            files = self.dialog.getOpenFileNames(self, 'Open File', filter='PEM files (*.pem);; All files(*.*)')
            if files[0] != '':
                for file in files[0]:
                    if file.lower().endswith('.pem'):
                        self.open_files(file)
                    else:
                        pass
            else:
                pass
        except Exception as e:
            logging.warning(str(e))
            self.message.information(None, 'PEMEditorWindow: open_file_dialog error', str(e))
            pass

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
        elif all([url.lower().endswith('inf') for url in urls]):
            inf_files = True
        elif all([url.lower().endswith('gpx') for url in urls]):
            gpx_files = True

        pem_conditions = bool(all([
            bool(e.answerRect().intersects(self.table.geometry())),
            pem_files,
        ]))

        if len(self.pem_files) == 0:
            if pem_conditions is True:
                e.acceptProposedAction()
            else:
                e.ignore()

        else:
            eligible_tabs = [self.stackedWidget.currentWidget().Station_GPS_Tab,
                             self.stackedWidget.currentWidget().Loop_GPS_Tab,
                             self.stackedWidget.currentWidget().Geometry_Tab,
                             ]
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
        self.open_files(urls)

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

    def open_files(self, files):
        """
        First step of opening a PEM, GPS, RI, GPX, or INF file.
        :param files: Any filetype that the program can open.
        """
        # logging.info('PEMEditor - Opening Files')
        if not isinstance(files, list) and isinstance(files, str):
            files = [files]
        pem_files = [file for file in files if file.lower().endswith('pem')]
        gps_files = [file for file in files if
                     file.lower().endswith('txt') or file.lower().endswith('csv') or file.lower().endswith(
                         'seg') or file.lower().endswith('xyz')]
        ri_files = [file for file in files if
                    file.lower().endswith('ri1') or file.lower().endswith('ri2') or file.lower().endswith('ri3')]
        inf_files = [file for file in files if file.lower().endswith('inf')]
        gpx_files = [file for file in files if file.lower().endswith('gpx')]

        start_time = time.time()
        if len(pem_files) > 0:
            self.open_pem_files(pem_files)
            print('open_pem_files time: {} seconds'.format(time.time() - start_time))

        if len(gps_files) > 0:
            self.open_gps_files(gps_files)
            print('open_gps_files time: {} seconds'.format(time.time() - start_time))

        if len(ri_files) > 0:
            self.open_ri_file(ri_files)

        if len(inf_files) > 0:
            self.open_inf_file(inf_files)

        if len(gpx_files) > 0:
            self.open_gpx_files(gpx_files)

    def open_pem_files(self, pem_files):
        """
        Action of opening a PEM file. Will not open a PEM file if it is already opened.
        :param pem_files: list: Filepaths for the PEM Files
        """

        def is_opened(pem_file):
            # pem_file is the pem_file filepath, not the PEMFile object.
            if len(self.pem_files) > 0:
                existing_filepaths = [os.path.abspath(file.filepath) for file in self.pem_files]
                if os.path.abspath(pem_file) in existing_filepaths:
                    self.window().statusBar().showMessage(f"{pem_file} is already opened", 2000)
                    return True
                else:
                    return False
            else:
                return False

        if not isinstance(pem_files, list):
            pem_files = [pem_files]

        self.block_signals()
        self.allow_signals = False
        self.stackedWidget.show()
        self.pemInfoDockWidget.show()
        files_to_add = []
        self.start_pg(min=0, max=len(pem_files))
        count = 0

        for pem_file in pem_files:
            if isinstance(pem_file, PEMFile):
                pem_file = pem_file.filepath

            if not is_opened(pem_file):
                pemInfoWidget = PEMFileInfoWidget()
                pemInfoWidget.refresh_tables_signal.connect(lambda: self.refresh_table(single_row=True))

                if not isinstance(pem_file, PEMFile):
                    try:
                        pem_file = self.parser.parse(pem_file)
                    except ValueError as e:
                        self.error.setWindowTitle(f"Open PEM File Error")
                        self.error.showMessage(f"The following error occurred while opening PEM File {os.path.basename(pem_file)}:"
                                               f"\n{str(e)}")
                        self.pg.hide()
                        continue

                    print(f'Opening {os.path.basename(pem_file.filepath)}')
                self.pg.setText(f"Opening {os.path.basename(pem_file.filepath)}")
                try:
                    pemInfoWidget.blockSignals(True)
                    pem_widget = pemInfoWidget.open_file(pem_file, parent=self)
                    pem_widget.tabs.setCurrentIndex(self.tab_num)
                    pem_widget.tabs.currentChanged.connect(self.change_pem_info_tab)
                    self.pem_files.append(pem_file)
                    self.pem_info_widgets.append(pem_widget)
                    self.stackedWidget.addWidget(pem_widget)

                    files_to_add.append(pem_file)
                    pemInfoWidget.blockSignals(False)

                    # Fill in the GPS System information based on the existing GEN tag if it's not yet filled.
                    for note in pem_file.notes:
                        if '<GEN> CRS:' in note:
                            if self.systemCBox.currentText() == '' and self.datumCBox.currentText() == '':
                                info = re.split(': ', note)[-1]
                                matches = re.search(r'(?P<System>UTM|Latitude/Longitude)(?P<Zone>\sZone \d+)?\s?'
                                                    r'(?P<Hemisphere>North|South)?\,\s(?P<Datum>.*)', info)
                                system = matches.group('System')
                                zone = matches.group('Zone')
                                hemis = matches.group('Hemisphere')
                                datum = matches.group('Datum')

                                self.systemCBox.setCurrentIndex(self.gps_systems.index(system))
                                if zone:
                                    zone = zone.split('Zone ')[-1]
                                    self.zoneCBox.setCurrentIndex(self.gps_zones.index(f"{zone} {hemis.title()}"))
                                self.datumCBox.setCurrentIndex(self.gps_datums.index(datum))

                    # Fill the shared header and station info if it's the first PEM File opened
                    if len(self.pem_files) == 1:
                        if self.client_edit.text() == '':
                            self.client_edit.setText(self.pem_files[0].header['Client'])
                        if self.grid_edit.text() == '':
                            self.grid_edit.setText(self.pem_files[0].header['Grid'])
                        if self.loop_edit.text() == '':
                            self.loop_edit.setText(self.pem_files[0].header['Loop'])

                        all_stations = [file.get_converted_unique_stations() for file in self.pem_files]

                        if self.min_range_edit.text() == '':
                            min_range = str(min(chain.from_iterable(all_stations)))
                            self.min_range_edit.setText(min_range)
                        if self.max_range_edit.text() == '':
                            max_range = str(max(chain.from_iterable(all_stations)))
                            self.max_range_edit.setText(max_range)

                    count += 1
                    self.pg.setValue(count)
                except Exception as e:
                    self.error.setWindowTitle('Open PEM File Error')
                    self.error.showMessage(str(e))

        if len(self.pem_files) > 0:
            self.fill_share_range()

        if not self.autoSortLoopsCheckbox.isChecked():
            self.message.warning(self, 'Warning', 'Loops aren\'t being sorted.')

        # Add all files to the table at once for aesthetics.
        [self.add_pem_to_table(pem_file) for pem_file in files_to_add]
        self.sort_files()
        self.allow_signals = True
        self.enable_signals()
        self.pg.hide()
        # self.update_table_row_colors()
        # self.update_repeat_stations_cells()
        # self.update_suffix_warnings_cells()

    def open_gps_files(self, gps_files):
        """
        Adds GPS information from the gps_files to the PEMFile object
        :param gps_files: Text or gpx file(s) with GPS information in them
        """
        # logging.info('PEMEditor - Opening GPS Files')
        def read_gps_files(gps_files):  # Merges files together if there are multiple files
            if len(gps_files) > 1:
                merged_file = ''
                for file in gps_files:
                    with open(file, mode='rt') as in_file:
                        contents = in_file.read()
                        merged_file += contents
                return merged_file
            else:
                with open(gps_files[0], mode='rt') as in_file:
                    file = in_file.read()
                return file

        if len(gps_files) > 0:
            file = read_gps_files(gps_files)
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

    def open_ri_file(self, ri_files):
        """
        Adds RI file information to the associated PEMFile object. Only accepts 1 file.
        :param ri_file: Text file with step plot information in them
        """
        # logging.info('PEMEditor - Opening RI Files')
        ri_file = ri_files[0]  # Filepath
        pem_info_widget = self.stackedWidget.currentWidget()
        pem_info_widget.open_ri_file(ri_file)

    def open_inf_file(self, inf_files):
        """
        Parses a .INF file to extract the CRS information in ti and set the CRS drop-down values.
        :param inf_files: List of .INF files. Will only use the first file.
        :return: None
        """
        # logging.info('PEMEditor - Opening INF File')
        inf_file = inf_files[0]  # Filepath, only accept the first one
        inf_parser = INFParser()
        crs = inf_parser.get_crs(inf_file)
        coord_sys = crs.get('Coordinate System')
        coord_zone = crs.get('Coordinate Zone')
        datum = crs.get('Datum')
        if 'NAD 1983' in datum:
            datum = 'NAD 1983'
        elif 'NAD 1927' in datum:
            datum = 'NAD 1927'
        self.systemCBox.setCurrentIndex(self.gps_systems.index(coord_sys))
        self.zoneCBox.setCurrentIndex(self.gps_zones.index(coord_zone))
        self.datumCBox.setCurrentIndex(self.gps_datums.index(datum))

    def open_gpx_files(self, gpx_files):
        # logging.info('PEMEditor - Opening GPX Files')
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

    def clear_files(self):
        """
        Remove all files
        """
        # logging.info('PEMEditor - Clearing All Files')
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

    def sort_files(self):
        """
        Sort the PEM files (and their associated files/widget) in the main table.
        :return: None
        """
        if len(self.pem_files) > 0:
            print('Sorting the table')
            # Cannot simply sort the widgets in stackedWidget so they are removed and re-added.
            [self.stackedWidget.removeWidget(widget) for widget in self.pem_info_widgets]

            # Sorting the pem_files and pem_file_widgets using the pem_file basename as key.
            sorted_files = [(pem_file, piw) for pem_file, piw in
                            sorted(zip(self.pem_files, self.pem_info_widgets),
                                   key=lambda pair: alpha_num_sort(os.path.basename(pair[0].filepath)),
                                   reverse=False)]

            self.pem_files = [pair[0] for pair in sorted_files]
            self.pem_info_widgets = [pair[1] for pair in sorted_files]
            # Re-adding the pem_info_widgets
            [self.stackedWidget.addWidget(widget) for widget in self.pem_info_widgets]
            self.refresh_table()

    def backup_files(self):
        """
        Create a backup (.bak) file for each opened PEM file, saved in a backup folder.
        :return: None
        """
        logging.info('PEMEditor - Backing Up All Files')
        if len(self.pem_files) > 0:
            for pem_file in self.pem_files:
                print(f"Backing up {os.path.basename(pem_file.filepath)}")
                pem_file = copy.deepcopy(pem_file)
                self.save_pem_file_to_file(pem_file, backup=True, tag='[B]', remove_old=False)
            self.window().statusBar().showMessage(f'Backup complete. Backed up {len(self.pem_files)} PEM files.', 2000)

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

    def display_pem_info_widget(self):
        """
        Slot: Changes which pemInfoWidget is displayed when a table row is clicked
        """
        self.stackedWidget.setCurrentIndex(self.table.currentRow())

    def change_pem_info_tab(self, tab_num):
        """
        Slot: Change the tab for each pemInfoWidget to the same
        :param tab_num: tab index number to change to
        """
        # logging.info(f"PEMEditor - Changing PEMInfo Tab to {tab_num}")
        self.tab_num = tab_num
        if len(self.pem_info_widgets) > 0:
            for widget in self.pem_info_widgets:
                widget.tabs.setCurrentIndex(self.tab_num)

    def extract_stations(self):
        """
        Opens the PEMFileSplitter window, which will allow selected stations to be saved as a new PEM file.
        :return: None
        """
        logging.info('PEMEditor - Extract stations')
        pem_file, row = self.get_selected_pem_files()
        self.pem_file_splitter = PEMFileSplitter(pem_file[0], parent=self)

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
                    self.save_pem_file_to_file(copy.deepcopy(pem_file), backup=True, tag='[-A]')
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
                    self.save_pem_file_to_file(copy.deepcopy(pem_file), backup=True, tag='[-S]')
                pem_file = self.file_editor.split_channels(pem_file)
                self.pem_info_widgets[row].open_file(pem_file, parent=self)
                self.refresh_table_row(pem_file, row)
                count += 1
                self.pg.setValue(count)
        self.pg.hide()

    def scale_coil_area_selection(self, coil_area=None, all=False):
        """
        Scales the data according to the coil area change
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
            print(f"Performing coil area change for {os.path.basename(pem_file.filepath)}")
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
        # logging.info(f'PEMEditor - Reversing data polarity for {comp} component')
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
                        self.save_pem_file_to_file(pem_file, tag='[-M]', backup=True,
                                                   remove_old=self.delete_merged_files_cbox.isChecked())
                    if self.delete_merged_files_cbox.isChecked():
                        self.remove_file(row)
                self.save_pem_file_to_file(merged_pem, tag='[M]')
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
                                    self.save_pem_file_to_file(copy.deepcopy(pem_file), tag='[-M]', backup=True,
                                                               remove_old=self.delete_merged_files_cbox.isChecked())
                                if self.delete_merged_files_cbox.isChecked():
                                    self.remove_file(row)
                                    updated_pem_files.pop(row)
                            self.save_pem_file_to_file(merged_pem, tag='[M]')
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
                                        self.save_pem_file_to_file(copy.deepcopy(pem_file), tag='[-M]', backup=True,
                                                                   remove_old=self.delete_merged_files_cbox.isChecked())
                                    if self.delete_merged_files_cbox.isChecked():
                                        self.remove_file(row)
                                        updated_pem_files.pop(row)
                                self.save_pem_file_to_file(merged_pem, tag='[M]')
                                # Open the files later to not deal with changes in index when files are opened.
                                files_to_open.append(merged_pem)
            self.open_pem_files(files_to_open)
            # self.spinner.stop()

    def save_pem_file_to_file(self, pem_file, dir=None, tag=None, backup=False, remove_old=False):
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
                self.save_pem_file_to_file(pem_file)
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

            self.save_pem_file_to_file(updated_file)
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
            self.message.information(self, 'Error', 'GPS system information is incomplete')
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
        save_dir = QFileDialog.getSaveFileName(self, 'Save KMZ File', default_path, 'KMZ Files (*.KMZ)')[0]
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
                file_dir = QFileDialog.getExistingDirectory(self, '', default_path, QFileDialog.DontUseNativeDialog)

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
        file_dir = QFileDialog.getExistingDirectory(self, '', default_path, QFileDialog.DontUseNativeDialog)

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
                self.save_pem_file_to_file(updated_file, dir=file_dir)
            self.refresh_table()
            self.window().statusBar().showMessage(
                f"Save complete. {len(pem_files)} PEM {'file' if len(pem_files) == 1 else 'files'} exported", 2000)
        else:
            self.window().statusBar().showMessage('Cancelled.', 2000)
            pass

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

    def print_plots(self, selected_files=False):
        """
        Save the final plots as PDFs for the selected PEM files. If no PEM files are selected, it saves it for all open
        PEM files
        :param pem_files: List of PEMFile objects
        :param rows: Corresponding rows of the selected PEM files in order to link the RI file to the correct PEM file
        :return: None
        """

        # logging.info('PEMEditor - Printing plots')

        def get_crs():
            crs = {'Coordinate System': self.systemCBox.currentText(),
                   'Zone': self.zoneCBox.currentText(),
                   'Datum': self.datumCBox.currentText()}
            return crs

        def get_save_file():
            default_path = os.path.split(self.pem_files[-1].filepath)[0]
            self.dialog.setDirectory(default_path)
            if __name__ == '__main__':
                save_dir = r'C:\Users\Eric\PycharmProjects\Crone\sample_files\PEMGetter files\test'  # For testing purposes
            else:
                save_dir = os.path.splitext(QFileDialog.getSaveFileName(self, '', default_path)[0])[0]
                # Returns full filepath. For single PDF file
            return save_dir

        if len(self.pem_files) > 0:

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
                if not all([plot_kwargs['CRS'].get('Coordinate System'), plot_kwargs['CRS'].get('Datum')]):
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
                except IOError:
                    self.message.information(self, 'Error', 'File is currently opened')
                    printer.pb.hide()
            else:
                self.window().statusBar().showMessage('Cancelled', 2000)

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

    def reset_crs(self):
        """
        Reset all CRS drop-down menus.
        :return: None
        """
        # logging.info('PEMEditor - Reset CRS')
        self.systemCBox.setCurrentIndex(0)
        self.zoneCBox.setCurrentIndex(0)
        self.datumCBox.setCurrentIndex(0)

    def populate_gps_boxes(self):
        """
        Adds the drop-down options of each CRS drop-down menu.
        :return: None
        """
        # logging.info('PEMEditor - Filling CRS information')
        for system in self.gps_systems:
            self.systemCBox.addItem(system)
        for zone in self.gps_zones:
            self.zoneCBox.addItem(zone)
        for datum in self.gps_datums:
            self.datumCBox.addItem(datum)

    def create_table(self):
        """
        Creates the table (self.table) when the editor is first opened
        :return: None
        """
        self.table_columns = ['File', 'Date', 'Client', 'Grid', 'Line/Hole', 'Loop', 'Current', 'Coil Area',
                              'First\nStation',
                              'Last\nStation', 'Averaged', 'Split', 'Suffix\nWarnings', 'Repeat\nStations']
        self.table.setColumnCount(len(self.table_columns))
        self.table.setHorizontalHeaderLabels(self.table_columns)
        self.table.setSizeAdjustPolicy(
            QAbstractScrollArea.AdjustToContents)
        # self.table.resizeColumnsToContents()
        # header = self.table.horizontalHeader()
        # header.setSectionResizeMode(0, QHeaderView.Stretch)
        # header.setSectionResizeMode(1, QHeaderView.Stretch)
        # header.setSectionResizeMode(2, QHeaderView.Stretch)
        # header.setSectionResizeMode(3, QHeaderView.Stretch)

    def add_pem_to_table(self, pem_file):
        """
        Add a new row to the table and fill in the row with the PEM file's information.
        :param pem_file: PEMFile object
        :return: None
        """
        print(f"Adding a new row to table for PEM file {os.path.basename(pem_file.filepath)}")
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.fill_pem_row(pem_file, row)

    def refresh_table(self, single_row=False):
        """
        Deletes and re-populates the table rows with the new information. Blocks table signals while doing so.
        :return: None
        """
        # logging.info('PEMEditor - Refreshing PEMEditor table')
        if len(self.pem_files) > 0:
            self.table.blockSignals(True)
            if single_row:
                index = self.stackedWidget.currentIndex()
                print(f'Refreshing table row {index}')
                self.refresh_table_row(self.pem_files[index], index)
            else:
                print('Refreshing entire table')
                while self.table.rowCount() > 0:
                    self.table.removeRow(0)
                for row, pem_file in enumerate(self.pem_files):
                    self.add_pem_to_table(pem_file)
                # self.update_table_row_colors()
                # self.update_repeat_stations_cells()
                # self.update_suffix_warnings_cells()
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

    def color_table_row_text(self, row):
        """
        Color cells of the main table based on conditions. Ex: Red text if the PEM file isn't averaged.
        :param row: Row of the main table to check and color
        :return: None
        """
        self.table.blockSignals(True)
        average_col = self.table_columns.index('Averaged')
        split_col = self.table_columns.index('Split')
        suffix_col = self.table_columns.index('Suffix\nWarnings')
        repeat_col = self.table_columns.index('Repeat\nStations')
        pem_has_gps = self.pem_files[row].has_all_gps()

        for i, column in enumerate(self.table_columns):
            item = self.table.item(row, i)
            if item:
                value = item.text()
                if i == average_col:
                    if value.lower() == 'no':
                        item.setForeground(QtGui.QColor('red'))
                    else:
                        item.setForeground(QtGui.QColor('black'))
                elif i == split_col:
                    if value.lower() == 'no':
                        item.setForeground(QtGui.QColor('red'))
                    else:
                        item.setForeground(QtGui.QColor('black'))
                elif i == suffix_col:
                    if int(value) > 0:
                        item.setForeground(QtGui.QColor('red'))
                    else:
                        item.setForeground(QtGui.QColor('black'))
                elif i == repeat_col:
                    if int(value) > 0:
                        item.setForeground(QtGui.QColor('red'))
                    else:
                        item.setForeground(QtGui.QColor('black'))

        if not pem_has_gps:
            self.color_row(self.table, row, 'magenta')

        if self.allow_signals:
            self.table.blockSignals(False)

    def fill_pem_row(self, pem_file, row, special_cols_only=False):
        """
        Adds the information from a PEM file to the main table. Blocks the table signals while doing so.
        :param pem_file: PEMFile object
        :param row: int: row of the PEM file in the table
        :param special_cols_only: bool: Whether to only fill in the information from the non-editable columns (i.e.
        from the 'First Station' column to the end.
        :return: None
        """
        print(f"Filling info from PEM File {os.path.basename(pem_file.filepath)} to table")
        self.table.blockSignals(True)

        # pem_file_index = self.pem_files.index(pem_file)
        info_widget = self.pem_info_widgets[row]

        boldFont = QtGui.QFont()
        boldFont.setBold(True)
        normalFont = QtGui.QFont()
        normalFont.setBold(False)

        header = pem_file.header
        tags = pem_file.tags
        file = os.path.basename(pem_file.filepath)
        date = header.get('Date')
        client = self.client_edit.text() if self.share_client_cbox.isChecked() else header.get('Client')
        grid = self.grid_edit.text() if self.share_grid_cbox.isChecked() else header.get('Grid')
        loop = self.loop_edit.text() if self.share_loop_cbox.isChecked() else header.get('Loop')
        current = f"{float(tags.get('Current')):.1f}"
        coil_area = pem_file.header.get('CoilArea')
        averaged = 'Yes' if pem_file.is_averaged() else 'No'
        split = 'Yes' if pem_file.is_split() else 'No'
        suffix_warnings = str(info_widget.suffix_warnings)
        repeat_stations = str(info_widget.num_repeat_stations)
        line = header.get('LineHole')
        start_stn = self.min_range_edit.text() if self.share_range_checkbox.isChecked() else str(
            min(pem_file.get_converted_unique_stations()))
        end_stn = self.max_range_edit.text() if self.share_range_checkbox.isChecked() else str(
            max(pem_file.get_converted_unique_stations()))

        new_row = [file, date, client, grid, line, loop, current, coil_area, start_stn, end_stn, averaged, split,
                   suffix_warnings, repeat_stations]

        columns = self.table_columns
        col_nums = range(0, len(self.table_columns))

        # Only write the columns that shouldn't be edited in the table directly
        if special_cols_only:
            columns = columns[self.table_columns.index('First\nStation'):]
            col_nums = [self.table_columns.index(col) for col in columns]

        for col_num, column in zip(col_nums, columns):
            entry = new_row[col_num]
            item = QTableWidgetItem(entry)
            item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.table.setItem(row, col_num, item)

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

        if col == self.table_columns.index('Coil Area'):
            pem_file = self.pem_files[row]
            old_value = int(pem_file.header.get('CoilArea'))
            try:
                new_value = int(self.table.item(row, col).text())
                print(f"Coil area changed to {new_value}")
            except ValueError:
                print("Value is not an integer.")
                pass
            else:
                if int(old_value) != int(new_value):
                    self.scale_coil_area_selection(coil_area=int(new_value))
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
                os.remove(old_path)

                self.window().statusBar().showMessage(f"File renamed to {str(new_value)}", 2000)

        # Spec cols are columns that shouldn't be edited manually, thus this re-fills the cells based on the
        # information from the PEM file
        spec_cols = self.table_columns[self.table_columns.index('First\nStation'):]
        spec_col_nums = [self.table_columns.index(col) for col in spec_cols]
        if col in spec_col_nums:
            self.fill_pem_row(pem_file, row, special_cols_only=True)

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
        # logging.info('PEMEditor - Checking for table anomalies')
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
        # logging.info('PEMEditor - Checking for table changes')
        self.table.blockSignals(True)
        boldFont = QtGui.QFont()
        boldFont.setBold(True)
        normalFont = QtGui.QFont()
        normalFont.setBold(False)

        info_widget = self.pem_info_widgets[self.pem_files.index(pem_file)]

        pem_file_info_list = [
            os.path.basename(pem_file.filepath),
            pem_file.header.get('Date'),
            pem_file.header.get('Client'),
            pem_file.header.get('Grid'),
            pem_file.header.get('LineHole'),
            pem_file.header.get('Loop'),
            pem_file.tags.get('Current'),
            pem_file.header.get('CoilArea'),
            str(min(pem_file.get_converted_unique_stations())),
            str(max(pem_file.get_converted_unique_stations())),
            str('Yes' if pem_file.is_averaged() else 'No'),
            str('Yes' if pem_file.is_split() else 'No'),
            str(info_widget.suffix_warnings),
            str(info_widget.num_repeat_stations)
        ]
        for column in range(self.table.columnCount()):
            if self.table.item(row, column):
                original_value = pem_file_info_list[column]
                if self.table.item(row, column).text() != original_value:
                    self.table.item(row, column).setFont(boldFont)
                else:
                    self.table.item(row, column).setFont(normalFont)
        self.table.resizeColumnsToContents()

        if self.allow_signals:
            self.table.blockSignals(False)

    def update_pem_file_from_table(self, pem_file, table_row, filepath=None):
        """
        Saves the pem file in memory using the information in the table.
        :param pem_file: PEM file object to save.
        :param table_row: Corresponding row of the PEM file in the main table.
        :param filepath: New filepath to be given to the PEM file. If None is given, it will use the filename in the
        table.
        :return: None
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

    def color_row(self, table, rowIndex, color, alpha=50):
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

    #
    # def update_table_row_colors(self):
    #     """
    #     Signal slot: Colors the row of the table whose PEM file doesn't have all the GPS it should
    #     :return: None
    #     """
    #     self.table.blockSignals(True)
    #     for row in range(self.table.rowCount()):
    #         pem_file = self.pem_files[row]
    #         if not all([pem_file.has_collar_gps(), pem_file.has_geometry(), pem_file.has_loop_gps()]) or not all(
    #             [pem_file.has_station_gps(), pem_file.has_loop_gps()]):
    #             print(f'Coloring row {row} magenta')
    #             self.color_table_row(self.table, row, 'magenta', alpha=50)
    #         else:
    #             print(f'Coloring row {row} white')
    #             self.color_table_row(self.table, row, 'white', alpha=50)
    #     self.table.blockSignals(False)

    # def update_repeat_stations_cells(self):
    #     """
    #     Adds the number of potential repeat stations in the PEM file in the Repeat Stations column of the table.
    #     :return: None
    #     """
    #     print('Updating repeat stations column')
    #     self.table.blockSignals(True)
    #     boldFont = QtGui.QFont()
    #     boldFont.setBold(True)
    #     normalFont = QtGui.QFont()
    #     normalFont.setBold(False)
    #     column = self.table_columns.index('Repeat\nStations')
    #     for row in range(self.table.rowCount()):
    #         num_repeat_stations = self.pem_info_widgets[row].num_repeat_stations
    #         item = QTableWidgetItem(str(num_repeat_stations))
    #         item.setTextAlignment(QtCore.Qt.AlignCenter)
    #         if num_repeat_stations > 0:
    #             item.setForeground(QtGui.QColor('red'))
    #             item.setFont(boldFont)
    #         else:
    #             item.setForeground(QtGui.QColor('black'))
    #             item.setFont(normalFont)
    #         self.table.setItem(row, column, item)
    #     self.table.blockSignals(False)

    # def update_suffix_warnings_cells(self):
    #     """
    #     Adds the number of potential suffix errors in the data of the PEM file in the Suffix Warnings column of the table.
    #     :return: None
    #     """
    #     print('Updating suffix warnings column')
    #     self.table.blockSignals(True)
    #     boldFont = QtGui.QFont()
    #     boldFont.setBold(True)
    #     normalFont = QtGui.QFont()
    #     normalFont.setBold(False)
    #     column = self.table_columns.index('Suffix\nWarnings')
    #     for row in range(self.table.rowCount()):
    #         num_suffix_warnings = self.pem_info_widgets[row].suffix_warnings
    #         item = QTableWidgetItem(str(num_suffix_warnings))
    #         item.setTextAlignment(QtCore.Qt.AlignCenter)
    #         if num_suffix_warnings > 0:
    #             item.setForeground(QtGui.QColor('red'))
    #             item.setFont(boldFont)
    #         else:
    #             item.setForeground(QtGui.QColor('black'))
    #             item.setFont(normalFont)
    #         self.table.setItem(row, column, item)
    #     self.table.blockSignals(False)

    def sort_all_station_gps(self):
        """
        Sorts the station GPS (based on positions only) of all opened PEM files.
        :return: None
        """
        if len(self.pem_files) > 0:
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
        if len(self.pem_files) > 0:
            for i in range(self.stackedWidget.count()):
                widget = self.stackedWidget.widget(i)
                if widget.loop_gps:
                    widget.fill_loop_table(widget.loop_gps.get_sorted_gps(widget.get_loop_gps()))
                else:
                    pass
            self.window().statusBar().showMessage('All loops have been sorted', 2000)

    def fill_share_header(self):
        """
        Uses the client, grid, and loop information from the first PEM file opened to be used as the basis
        to be used on all opened PEM files if the toggle is on.
        :return: None
        """
        # logging.info('PEMEditor - Filling share header information')
        if len(self.pem_files) > 0:
            self.client_edit.setText(self.pem_files[0].header['Client'])
            self.grid_edit.setText(self.pem_files[0].header['Grid'])
            self.loop_edit.setText(self.pem_files[0].header['Loop'])
            self.update_table()
        else:
            self.client_edit.setText('')
            self.grid_edit.setText('')
            self.loop_edit.setText('')

    def fill_share_range(self):
        """
        Calculates the minimum and maximum station numbers between all opened PEM files, and uses this to fill out the
        shared range values
        :return: None
        """
        # logging.info('PEMEditor - Filling share range information')
        if len(self.pem_files) > 0:
            all_stations = [file.get_converted_unique_stations() for file in self.pem_files]
            min_range, max_range = str(min(chain.from_iterable(all_stations))), str(
                max(chain.from_iterable(all_stations)))
            self.min_range_edit.setText(min_range)
            self.max_range_edit.setText(max_range)
        else:
            self.min_range_edit.setText('')
            self.max_range_edit.setText('')

    def share_loop(self):
        """
        Share the loop GPS of one file with all other opened PEM files.
        :return: None
        """
        # logging.info('PEMEditor - Sharing loop GPS')
        selected_widget = self.pem_info_widgets[self.table.currentRow()]
        try:
            selected_widget_loop = selected_widget.get_loop_gps()
        except:
            return
        else:
            for widget in self.pem_info_widgets:
                widget.fill_loop_table(selected_widget_loop)

    def share_collar(self):
        """
        Share the collar GPS of one file with all other opened PEM files. Will only do so for borehole files.
        :return: None
        """
        # logging.info('PEMEditor - Sharing collar GPS')
        selected_widget = self.pem_info_widgets[self.table.currentRow()]
        try:
            selected_widget_collar = [selected_widget.get_collar_gps()]
        except:
            return
        else:
            for widget in list(filter(lambda x: 'borehole' in x.pem_file.survey_type.lower(), self.pem_info_widgets)):
                widget.fill_collar_gps_table(selected_widget_collar)

    def share_segments(self):
        """
        Share the segments of one file with all other opened PEM files. Will only do so for borehole files.
        :return: None
        """
        # logging.info('PEMEditor - Sharing borehole segments')
        selected_widget = self.pem_info_widgets[self.table.currentRow()]
        try:
            selected_widget_geometry = selected_widget.get_geometry_segments()
        except:
            return
        else:
            for widget in list(filter(lambda x: 'borehole' in x.pem_file.survey_type.lower(), self.pem_info_widgets)):
                widget.fill_geometry_table(selected_widget_geometry)

    def share_station_gps(self):
        """
        Share the station GPS of one file with all other opened PEM files. Will only do so for surface files.
        :return: None
        """
        # logging.info('PEMEditor - Sharing line GPS')
        selected_widget = self.pem_info_widgets[self.table.currentRow()]
        try:
            selected_widget_station_gps = selected_widget.get_station_gps()
        except:
            return
        else:
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
        # TODO Should only be for surface lines
        if any(self.pem_files):
            file_name_column = self.table_columns.index('File')
            line_name_column = self.table_columns.index('Line/Hole')
            new_name = ''
            for row in range(self.table.rowCount()):
                pem_file = self.pem_files[row]
                survey_type = pem_file.survey_type.lower()
                file_name = self.table.item(row, file_name_column).text()
                if 'borehole' in survey_type:
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

    def toggle_share_client(self):
        if self.share_client_cbox.isChecked():
            self.client_edit.setEnabled(True)
            self.refresh_table()
        else:
            self.client_edit.setEnabled(False)
            self.refresh_table()

    def toggle_share_grid(self):
        if self.share_grid_cbox.isChecked():
            self.grid_edit.setEnabled(True)
            self.refresh_table()
        else:
            self.grid_edit.setEnabled(False)
            self.refresh_table()

    def toggle_share_loop(self):
        if self.share_loop_cbox.isChecked():
            self.loop_edit.setEnabled(True)
            self.refresh_table()
        else:
            self.loop_edit.setEnabled(False)
            self.refresh_table()

    def toggle_share_range(self):
        if self.share_range_checkbox.isChecked():
            self.min_range_edit.setEnabled(True)
            self.max_range_edit.setEnabled(True)
            self.refresh_table()
        else:
            self.min_range_edit.setEnabled(False)
            self.max_range_edit.setEnabled(False)
            self.refresh_table()

    def toggle_sort_loop(self, widget):
        if self.autoSortLoopsCheckbox.isChecked():
            widget.fill_loop_table(widget.loop_gps.get_sorted_gps())
        else:
            widget.fill_loop_table(widget.loop_gps.get_gps())

    def toggle_hide_gaps(self):
        pass  # To be implemented when pyqtplots are in

    def toggle_zone_box(self):
        if self.systemCBox.currentText() == 'UTM':
            self.zoneCBox.setEnabled(True)
        else:
            self.zoneCBox.setEnabled(False)

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
                    # Create a copy and delete the old one.
                    copyfile(self.pem_files[row].old_filepath, self.pem_files[row].filepath)
                    self.window().statusBar().showMessage(
                        f"{os.path.basename(self.pem_files[row].old_filepath)} renamed to {os.path.basename(self.pem_files[row].filepath)}",
                        2000)
                    os.remove(self.pem_files[row].old_filepath)
                # self.refresh_table()

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

        # logging.info('PEMEditor - Importing RI Files')

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


class BatchNameEditor(QWidget, Ui_LineNameEditorWidget):
    """
    Class to bulk rename PEM File line/hole names or file names.
    """
    # logging.info('BatchNameEditor')
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
            # Split the text based on '[n]'. Anything before it becomes the prefix, and everything after is added as a suffix
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
    # logging.info('BatchRIImporter')
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
        ri_filepaths.sort(key=lambda path: alpha_num_sort(os.path.basename(path)), reverse=False)
        self.ri_files = []

        if len(ri_filepaths) == len(self.pem_files):

            # Only for boreholes, match up the RI1 file for Z, and RI2 file for XY
            if all(['borehole' in pem_file.survey_type.lower() for pem_file in self.pem_files]):
                ri_files = [self.ri_parser().open(filepath) for filepath in ri_filepaths]

                for pem_file in self.pem_files:
                    pem_components = pem_file.get_components()
                    pem_name = re.sub('[^0-9]', '', pem_file.header.get('LineHole'))[-4:]

                    for ri_file in ri_files:
                        ri_components = ri_file.get_components()
                        ri_name = re.sub('[^0-9]', '', os.path.splitext(os.path.basename(ri_file.filepath))[0])[-4:]

                        if pem_components == ri_components and pem_name == ri_name:
                            self.ri_files.append(ri_file.filepath)
                            ri_files.pop(ri_files.index(ri_file))

            elif not all(['surface' in pem_file.survey_type.lower() for pem_file in self.pem_files]):
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
        # logging.info('PlanMapOptions')
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
        # logging.info('PEMFileSplitter')
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
        # logging.info('Map3DViewer')
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
        self.section_plotter.plot_2d_magnetic_field()
        self.section_plotter.format_ax()
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
        self.save_figure_btn.clicked.connect(self.save_figure)

        self.figure = Figure(figsize=(11, 8.5))
        self.canvas = FigureCanvas(self.figure)
        self.toolbar = ContourMapToolbar(self.canvas, self)
        self.toolbar_layout.addWidget(self.toolbar)
        self.toolbar.setFixedHeight(30)
        self.map_layout.addWidget(self.canvas)
        self.draw_map()

    def draw_map(self):

        def get_channel_time(channel):
            """
            Retrieve the gate-center time of a channel based on the channel times table.
            :param channel: int: channel number
            :return: float: channel center time.
            """
            current_pair = self.channel_pairs[channel]
            channel_center = (float(current_pair[1]) - float(current_pair[0])) / 2 + float(current_pair[0])
            channel_time = channel_center
            return channel_time

        component = self.get_selected_component().upper()
        if component not in self.components:
            return

        channel = self.channel_spinbox.value()
        channel_time = get_channel_time(channel)
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
        if len(self.pem_files) > 0:
            default_path = os.path.abspath(self.pem_files[0].filepath)
            path, ext = QFileDialog.getSaveFileName(self, 'Save Figure', default_path,
                                                    'PDF Files (*.PDF);;PNG Files (*.PNG);;JPG Files (*.JPG')
            if path:
                # resize the figure to 8.5 x 11, then back to the original size after it's been printed
                size = self.figure.get_size_inches()
                self.figure.set_size_inches(11, 8.5)
                self.figure.savefig(path, orientation='landscape')
                self.figure.set_size_inches(size)
                self.canvas.draw()
                os.startfile(path)


class ContourMapToolbar(NavigationToolbar):
    """
    Custom Matplotlib toolbar for ContourMap.
    """
    # only display the buttons we need
    toolitems = [t for t in NavigationToolbar.toolitems if
                 t[0] in ('Home', 'Back', 'Forward', 'Pan', 'Zoom')]


def main():
    from src.pem.pem_getter import PEMGetter
    app = QApplication(sys.argv)
    mw = PEMEditorWindow()
    mw.show()
    pg = PEMGetter()
    pem_files = pg.get_pems()
    mw.open_pem_files(pem_files)

    # mw.save_as_xyz(selected_files=False)
    # mw.show_contour_map_viewer()
    # mw.auto_merge_pem_files()
    # mw.show_contour_map_viewer()
    # mw.save_as_kmz()
    # spinner = WaitingSpinner(mw.table)
    # spinner.start()
    # spinner.show()

    # mw.auto_merge_pem_files()
    # mw.sort_files()
    # section = Section3DViewer(pem_files)
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
