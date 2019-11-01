import cProfile
import copy
import datetime
import logging
import os
import re
import pstats
import sys
import time
from decimal import getcontext
from itertools import chain

from PyQt5 import (QtCore, QtGui, uic)
from PyQt5.QtWidgets import (QWidget, QMainWindow, QApplication, QDesktopWidget, QMessageBox, QFileDialog,
                             QAbstractScrollArea, QTableWidgetItem, QAction, QMenu, QToolButton, QCheckBox,
                             QInputDialog, QHeaderView, QTableWidget, QGridLayout, QDialogButtonBox, QVBoxLayout)
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from mpl_toolkits.mplot3d import Axes3D  # Needed for 3D plots
from matplotlib.figure import Figure
from src.pem.pem_file import PEMFile
from src.gps.gps_editor import GPSParser, INFParser, GPXEditor
from src.pem.pem_file_editor import PEMFileEditor
from src.pem.pem_parser import PEMParser
from src.pem.pem_plotter import PEMPrinter, Map3D, Section3D
from src.pem.pem_serializer import PEMSerializer
from src.pem.pem_getter import PEMGetter
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
    icons_path = 'icons'
else:
    application_path = os.path.dirname(os.path.abspath(__file__))
    editorWindowCreatorFile = os.path.join(os.path.dirname(application_path), 'qt_ui\\pem_editor_window.ui')
    lineNameEditorCreatorFile = os.path.join(os.path.dirname(application_path), 'qt_ui\\line_name_editor.ui')
    planMapOptionsCreatorFile = os.path.join(os.path.dirname(application_path), 'qt_ui\\plan_map_options.ui')
    pemFileSplitterCreatorFile = os.path.join(os.path.dirname(application_path), 'qt_ui\\pem_file_splitter.ui')
    map3DCreatorFile = os.path.join(os.path.dirname(application_path), 'qt_ui\\3D_map.ui')
    section3DCreatorFile = os.path.join(os.path.dirname(application_path), 'qt_ui\\3D_section.ui')
    icons_path = os.path.join(os.path.dirname(application_path), "qt_ui\\icons")

# Load Qt ui file into a class
Ui_PEMEditorWindow, QtBaseClass = uic.loadUiType(editorWindowCreatorFile)
Ui_LineNameEditorWidget, QtBaseClass = uic.loadUiType(lineNameEditorCreatorFile)
Ui_PlanMapOptionsWidget, QtBaseClass = uic.loadUiType(planMapOptionsCreatorFile)
Ui_PEMFileSplitterWidget, QtBaseClass = uic.loadUiType(pemFileSplitterCreatorFile)
Ui_Map3DWidget, QtBaseClass = uic.loadUiType(map3DCreatorFile)
Ui_Section3DWidget, QtBaseClass = uic.loadUiType(section3DCreatorFile)

sys._excepthook = sys.excepthook


def exception_hook(exctype, value, traceback):
    print(exctype, value, traceback)
    sys._excepthook(exctype, value, traceback)
    sys.exit(1)


sys.excepthook = exception_hook


class PEMEditorWindow(QMainWindow, Ui_PEMEditorWindow):
    logging.info('PEMEditor')

    def __init__(self, parent=None):
        super().__init__()
        self.parent = parent
        self.initUi()

        self.pem_files = []
        self.gps_files = []
        self.pem_info_widgets = []
        self.tab_num = 2

        self.message = QMessageBox()
        self.dialog = QFileDialog()
        self.parser = PEMParser()
        self.file_editor = PEMFileEditor()
        self.message = QMessageBox()
        self.dialog = QFileDialog()
        self.gps_parser = GPSParser()
        self.gpx_editor = GPXEditor()
        self.serializer = PEMSerializer()
        self.ri_importer = BatchRIImporter(parent=self)
        self.plan_map_options = PlanMapOptions(parent=self)
        self.map_viewer_3d = None
        self.section_viewer_3d = None
        self.pem_file_splitter = None

        self.initActions()
        self.initSignals()

        self.stackedWidget.hide()
        self.pemInfoDockWidget.hide()
        self.plotsDockWidget.hide()
        # self.plotsDockWidget.setWidget(self.tabWidget)
        # self.addDockWidget(QtCore.Qt.RightDockWidgetArea, self.stackedWidget)

        self.gps_systems = ['', 'UTM', 'Latitude/Longitude']
        self.gps_zones = [''] + [f"{num} North" for num in range(1, 61)] + [f"{num} South" for num in range(1, 61)]
        self.gps_datums = ['', 'NAD 1927', 'NAD 1983', 'WGS 1984']

        self.create_table()
        self.populate_gps_boxes()

    def initUi(self):
        logging.info('PEMEditor - Initializing UI')
        def center_window(self):
            qtRectangle = self.frameGeometry()
            centerPoint = QDesktopWidget().availableGeometry().center()
            qtRectangle.moveCenter(centerPoint)
            self.move(qtRectangle.topLeft())

        self.setupUi(self)

        self.setWindowTitle("PEMEditor")
        self.setWindowIcon(
            QtGui.QIcon(os.path.join(icons_path, 'crone_logo.ico')))
        self.setGeometry(500, 300, 1500, 800)
        center_window(self)

    def initActions(self):
        logging.info('PEMEditor - Initializing Actions')
        self.setAcceptDrops(True)

        # 'File' menu
        self.openFile = QAction("&Open...", self)
        self.openFile.setShortcut("Ctrl+O")
        self.openFile.setStatusTip('Open file')
        self.openFile.triggered.connect(self.open_file_dialog)

        self.saveFiles = QAction("&Save Files", self)
        self.saveFiles.setShortcut("Ctrl+S")
        self.saveFiles.setStatusTip("Save all files")
        self.saveFiles.triggered.connect(lambda: self.save_pem_file_selection(all=True))

        self.saveFilesTo = QAction("&Save Files To...", self)
        self.saveFilesTo.setShortcut("F11")
        self.saveFilesTo.setStatusTip("Save all files at specified location.")
        self.saveFilesTo.triggered.connect(lambda: self.save_pem_file_to(all=True))

        self.export_final_pems_action = QAction("&Export Final PEM Files", self)
        self.export_final_pems_action.setShortcut("F9")
        self.export_final_pems_action.setStatusTip("Export the final PEM files")
        self.export_final_pems_action.triggered.connect(self.export_final_pems)

        self.print_plan_map_action = QAction("&Print Plan Map PDF", self)
        self.print_plan_map_action.setShortcut("F10")
        self.print_plan_map_action.setStatusTip("Print a plan map to PDF")
        self.print_plan_map_action.triggered.connect(lambda: self.print_plots(plan=True))

        self.print_step_plots_action = QAction("&Print Step Plots PDF", self)
        self.print_step_plots_action.setShortcut("F11")
        self.print_step_plots_action.setStatusTip("Print the step plots to PDF")
        self.print_step_plots_action.triggered.connect(lambda: self.print_plots(step=True))

        self.print_final_plots_action = QAction("&Print Final Plots PDF", self)
        self.print_final_plots_action.setShortcut("F12")
        self.print_final_plots_action.setStatusTip("Print the final plots to PDF")
        self.print_final_plots_action.triggered.connect(lambda: self.print_plots(final=True))

        self.del_file = QAction("&Remove File", self)
        self.del_file.setShortcut("Del")
        self.del_file.triggered.connect(self.remove_file_selection)
        self.addAction(self.del_file)
        self.del_file.setEnabled(False)

        self.clearFiles = QAction("&Clear All Files", self)
        self.clearFiles.setShortcut("Shift+Del")
        self.clearFiles.setStatusTip("Clear all files")
        self.clearFiles.triggered.connect(self.clear_files)

        self.import_ri_files_action = QAction("&Import RI Files", self)
        self.import_ri_files_action.setShortcut("Ctrl+I")
        self.import_ri_files_action.setStatusTip("Import multiple RI files")
        self.import_ri_files_action.triggered.connect(self.import_ri_files)

        self.fileMenu = self.menubar.addMenu('&File')
        self.fileMenu.addAction(self.openFile)
        self.fileMenu.addAction(self.saveFiles)
        self.fileMenu.addAction(self.saveFilesTo)
        self.fileMenu.addAction(self.clearFiles)
        self.fileMenu.addSeparator()
        self.fileMenu.addAction(self.import_ri_files_action)
        self.fileMenu.addSeparator()
        self.fileMenu.addAction(self.export_final_pems_action)
        self.fileMenu.addAction(self.print_plan_map_action)
        self.fileMenu.addAction(self.print_step_plots_action)
        self.fileMenu.addAction(self.print_final_plots_action)

        # PEM menu
        self.averageAllPems = QAction("&Average All PEM Files", self)
        self.averageAllPems.setStatusTip("Average all PEM files")
        self.averageAllPems.setShortcut("F5")
        self.averageAllPems.triggered.connect(lambda: self.average_select_pem(all=True))

        self.splitAllPems = QAction("&Split All PEM Files", self)
        self.splitAllPems.setStatusTip("Remove on-time channels for all PEM files")
        self.splitAllPems.setShortcut("F6")
        self.splitAllPems.triggered.connect(lambda: self.split_channels_select_pem(all=True))

        self.merge_action = QAction("&Merge", self)
        self.merge_action.triggered.connect(self.merge_pem_files_selection)
        self.merge_action.setShortcut("Shift+M")

        self.scaleAllCurrents = QAction("&Scale All Current", self)
        self.scaleAllCurrents.setStatusTip("Scale the current of all PEM Files to the same value")
        self.scaleAllCurrents.setShortcut("F7")
        self.scaleAllCurrents.triggered.connect(lambda: self.scale_current_selection(all=True))

        self.scaleAllCoilAreas = QAction("&Change All Coil Areas", self)
        self.scaleAllCoilAreas.setStatusTip("Scale all coil areas to the same value")
        self.scaleAllCoilAreas.setShortcut("F8")
        self.scaleAllCoilAreas.triggered.connect(lambda: self.scale_coil_area_selection(all=True))

        self.editLineNames = QAction("&Rename All Lines/Holes", self)
        self.editLineNames.setStatusTip("Rename all line/hole names")
        self.editLineNames.setShortcut("F2")
        self.editLineNames.triggered.connect(lambda: self.batch_rename(type='Line'))

        self.editFileNames = QAction("&Rename All Files", self)
        self.editFileNames.setStatusTip("Rename all file names")
        self.editFileNames.setShortcut("F3")
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
        self.sortAllStationGps = QAction("&Sort All Station GPS", self)
        self.sortAllStationGps.setStatusTip("Sort the station GPS for every file")
        self.sortAllStationGps.triggered.connect(self.sort_all_station_gps)

        self.sortAllLoopGps = QAction("&Sort All Loop GPS", self)
        self.sortAllLoopGps.setStatusTip("Sort the loop GPS for every file")
        self.sortAllLoopGps.triggered.connect(self.sort_all_loop_gps)

        self.GPSMenu = self.menubar.addMenu('&GPS')
        self.GPSMenu.addAction(self.sortAllStationGps)
        self.GPSMenu.addAction(self.sortAllLoopGps)

        # Map menu
        self.show3DMap = QAction("&3D Map", self)
        self.show3DMap.setStatusTip("Show 3D map of all PEM files")
        self.show3DMap.setShortcut('Ctrl+M')
        self.show3DMap.triggered.connect(self.show_map_3d_viewer)

        self.MapMenu = self.menubar.addMenu('&Map')
        self.MapMenu.addAction(self.show3DMap)

    def initSignals(self):
        logging.info('PEMEditor - Initializing Signals')
        self.table.viewport().installEventFilter(self)

        self.table.installEventFilter(self)
        self.table.setFocusPolicy(QtCore.Qt.StrongFocus)

        self.table.itemSelectionChanged.connect(self.display_pem_info_widget)
        self.table.cellChanged.connect(self.table_value_changed)

        self.plan_map_options_btn.clicked.connect(self.plan_map_options.show)

        self.share_client_cbox.stateChanged.connect(self.toggle_share_client)
        self.share_grid_cbox.stateChanged.connect(self.toggle_share_grid)
        self.share_loop_cbox.stateChanged.connect(self.toggle_share_loop)
        self.reset_header_btn.clicked.connect(self.fill_share_header)
        self.client_edit.textChanged.connect(self.update_table)
        self.grid_edit.textChanged.connect(self.update_table)
        self.loop_edit.textChanged.connect(self.update_table)

        self.share_range_checkbox.stateChanged.connect(self.toggle_share_range)
        self.reset_range_btn.clicked.connect(self.fill_share_range)
        self.hide_gaps_checkbox.stateChanged.connect(self.toggle_hide_gaps)
        self.min_range_edit.textChanged.connect(self.update_table)
        self.max_range_edit.textChanged.connect(self.update_table)

        self.reverseAllZButton.clicked.connect(lambda: self.reverse_all_data(comp='Z'))
        self.reverseAllXButton.clicked.connect(lambda: self.reverse_all_data(comp='X'))
        self.reverseAllYButton.clicked.connect(lambda: self.reverse_all_data(comp='Y'))

        self.systemCBox.currentIndexChanged.connect(self.toggle_zone_box)
        self.reset_crs_btn.clicked.connect(self.reset_crs)

    def contextMenuEvent(self, event):
        if self.table.underMouse():
            if self.table.selectionModel().selectedIndexes():
                selected_pem, row = self.get_selected_pem_files()
                survey_type = selected_pem[0].survey_type.lower()

                self.table.menu = QMenu(self.table)
                self.table.remove_file_action = QAction("&Remove", self)
                self.table.remove_file_action.triggered.connect(self.remove_file_selection)

                self.table.open_file_action = QAction("&Open", self)
                self.table.open_file_action.triggered.connect(self.open_in_text_editor)

                self.table.save_file_action = QAction("&Save", self)
                self.table.save_file_action.triggered.connect(self.save_pem_file_selection)

                self.table.save_file_to_action = QAction("&Save To...", self)
                self.table.save_file_to_action.triggered.connect(self.save_pem_file_to)

                self.table.save_file_as_action = QAction("&Save As...", self)
                self.table.save_file_as_action.triggered.connect(self.save_pem_file_as)

                self.table.extract_stations_action = QAction("&Extract Stations", self)
                self.table.extract_stations_action.triggered.connect(self.extract_stations)

                self.table.view_3d_section_action = QAction("&View 3D Section", self)
                self.table.view_3d_section_action.triggered.connect(self.show_section_3d_viewer)

                self.table.average_action = QAction("&Average", self)
                self.table.average_action.triggered.connect(self.average_select_pem)

                self.table.split_action = QAction("&Split Channels", self)
                self.table.split_action.triggered.connect(self.split_channels_select_pem)

                self.table.scale_current_action = QAction("&Scale Current", self)
                self.table.scale_current_action.triggered.connect(self.scale_current_selection)

                self.table.scale_ca_action = QAction("&Scale Coil Area", self)
                self.table.scale_ca_action.triggered.connect(self.scale_coil_area_selection)

                self.table.share_loop_action = QAction("&Share Loop", self)
                self.table.share_loop_action.triggered.connect(self.share_loop)

                self.table.share_collar_action = QAction("&Share Collar", self)
                self.table.share_collar_action.triggered.connect(self.share_collar)

                self.table.share_segments_action = QAction("&Share Geometry", self)
                self.table.share_segments_action.triggered.connect(self.share_segments)

                self.table.rename_lines_action = QAction("&Rename Lines/Holes", self)
                self.table.rename_lines_action.triggered.connect(lambda: self.batch_rename(type='Line'))

                self.table.rename_files_action = QAction("&Rename Files", self)
                self.table.rename_files_action.triggered.connect(lambda: self.batch_rename(type='File'))

                self.table.menu.addAction(self.table.open_file_action)
                self.table.menu.addAction(self.table.save_file_action)
                if len(self.table.selectionModel().selectedRows()) == 1:
                    self.table.menu.addAction(self.table.save_file_as_action)
                    self.table.menu.addAction(self.table.extract_stations_action)
                else:
                    self.table.menu.addAction(self.table.save_file_to_action)
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
                if len(self.table.selectionModel().selectedRows()) > 1:
                    self.table.menu.addSeparator()
                    self.table.menu.addAction(self.table.rename_lines_action)
                    self.table.menu.addAction(self.table.rename_files_action)
                self.table.menu.addSeparator()
                # if 'borehole' in survey_type:
                #     self.table.menu.addAction(self.table.view_3d_section_action)
                self.table.menu.addAction(self.print_plan_map_action)
                self.table.menu.addAction(self.print_step_plots_action)
                self.table.menu.addAction(self.print_final_plots_action)
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
        logging.info('Opening PEM File in text editor')
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
                e.answerRect().intersects(self.gps_box.geometry()),
                inf_files is True or gpx_files is True,
            ]))

            if pem_conditions is True or gps_conditions is True or ri_conditions is True or inf_conditions is True:
                e.acceptProposedAction()
            else:
                e.ignore()

    def dropEvent(self, e):
        urls = [url.toLocalFile() for url in e.mimeData().urls()]
        self.open_files(urls)

    def open_files(self, files):
        """
        Open GPS or PEM Files
        :param files: GPS or PEM filepaths
        """
        logging.info('PEMEditor - Opening Files')
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
        Opens the PEM Files when dragged in
        :param pem_files: Filepaths for the PEM Files
        """
        logging.info('PEMEditor - Opening PEM Files')

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

        self.stackedWidget.show()
        self.pemInfoDockWidget.show()

        for pem_file in pem_files:
            if isinstance(pem_file, PEMFile):
                pem_file = pem_file.filepath
            # Check that the PEM File isn't already opened
            if not is_opened(pem_file):
                pemInfoWidget = PEMFileInfoWidget()

                if not isinstance(pem_file, PEMFile):
                    pem_file = self.parser.parse(pem_file)
                    print(f'Opening {os.path.basename(pem_file.filepath)}')
                try:
                    pem_widget = pemInfoWidget.open_file(pem_file, parent=self)
                    pem_widget.tabs.setCurrentIndex(self.tab_num)
                    pem_widget.tabs.currentChanged.connect(self.change_pem_info_tab)
                    self.pem_files.append(pem_file)
                    self.pem_info_widgets.append(pem_widget)
                    self.stackedWidget.addWidget(pem_widget)
                    self.add_to_table(pem_file)
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
                        # TODO This section refreshes the table after each setText. Because of signals?
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
                except Exception as e:
                    logging.info(str(e))
                    self.message.information(None, 'PEMEditor: open_pem_files error', str(e))

            if len(self.pem_files) > 0:
                # self.window().statusBar().showMessage('Opened {0} PEM Files'.format(len(files)), 2000)
                self.fill_share_range()

    def open_gps_files(self, gps_files):
        """
        Adds GPS information from the gps_files to the PEMFile object
        :param gps_files: Text or gpx file(s) with GPS information in them
        """
        logging.info('PEMEditor - Opening GPS Files')
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
        logging.info('PEMEditor - Opening RI Files')
        ri_file = ri_files[0]  # Filepath
        pem_info_widget = self.stackedWidget.currentWidget()
        pem_info_widget.open_ri_file(ri_file)

    def open_inf_file(self, inf_files):
        logging.info('PEMEditor - Opening INF File')
        inf_file = inf_files[0]  # Filepath, only accept the first one
        inf_parser = INFParser()
        crs = inf_parser.get_crs(inf_file)
        coord_sys = crs.get('Coordinate System')
        coord_zone = crs.get('Coordinate Zone')
        datum = crs.get('Datum')
        self.systemCBox.setCurrentIndex(self.gps_systems.index(coord_sys))
        self.zoneCBox.setCurrentIndex(self.gps_zones.index(coord_zone))
        self.datumCBox.setCurrentIndex(self.gps_datums.index(datum))

    def open_gpx_files(self, gpx_files):
        logging.info('PEMEditor - Opening GPX Files')
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
        Remove all files from the widget
        """
        logging.info('PEMEditor - Clearing All Files')
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

    def get_selected_pem_files(self):
        """
        Return the corresponding pem_files and rows which are currently selected in the table
        :return: pem_file objects and corresponding row indexes
        """
        selected_pem_files = []
        rows = [model.row() for model in self.table.selectionModel().selectedRows()]
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
        logging.info(f"PEMEditor - Changing PEMInfo Tab to {tab_num}")
        self.tab_num = tab_num
        if len(self.pem_info_widgets) > 0:
            for widget in self.pem_info_widgets:
                widget.tabs.setCurrentIndex(self.tab_num)

    def extract_stations(self):
        logging.info('PEMEditor - Extract stations')
        pem_file, row = self.get_selected_pem_files()
        self.pem_file_splitter = PEMFileSplitter(pem_file[0], parent=self)

    def average_pem_data(self, pem_file):
        """
        Average the data PEM File
        :param pem_file: PEM File object
        :return: PEM File object with the data averaged
        """
        logging.info('PEMEditor - Averaging PEM File data')
        if pem_file.is_averaged():
            self.window().statusBar().showMessage('File is already averaged.', 2000)
            return
        else:
            pem_file = self.file_editor.average(pem_file)
            self.window().statusBar().showMessage('File averaged.', 2000)

    def average_select_pem(self, all=False):
        """
        Average the data of each PEM File selected
        :param pem_file: PEM File object
        :return: PEM File object with the data averaged
        """
        if not all:
            pem_files, rows = self.get_selected_pem_files()
        else:
            pem_files, rows = self.pem_files, range(self.table.rowCount())
        for pem_file in pem_files:
            self.average_pem_data(pem_file)
        self.update_table()

    def split_pem_channels(self, pem_file):
        """
        Removes the on-time channels of the PEM File
        :param pem_file: PEM File object
        :return: PEM File object with the on-time channels removed from the data
        """
        logging.info('PEMEditor - Splitting PEM File channels')
        if pem_file.is_split():
            self.window().statusBar().showMessage('File is already split.', 2000)
            return
        else:
            pem_file = self.file_editor.split_channels(pem_file)
            self.window().statusBar().showMessage('File split.', 2000)

    def split_channels_select_pem(self, all=False):
        """
        Removes the on-time channels of each selected PEM File
        :param pem_file: PEM File object
        :return: PEM File object with the on-time channels removed from the data
        """
        if not all:
            pem_files, rows = self.get_selected_pem_files()
        else:
            pem_files, rows = self.pem_files, range(self.table.rowCount())
        for pem_file in pem_files:
            self.split_pem_channels(pem_file)
        self.update_table()

    def scale_coil_area(self, pem_file, new_coil_area):
        """
        Scales the data according to the coil area change
        :param pem_file: PEM File object
        :param new_coil_area: Desired coil area
        :return: PEM File with the data scaled  by the coil area change
        """
        logging.info('PEMEditor - Scaling PEM File data by coil area')
        pem_file = self.file_editor.scale_coil_area(pem_file, new_coil_area)
        self.update_table()

    def scale_coil_area_selection(self, all=False):
        """
        Scales the data according to the user-input coil area
        :return: PEM File with the data scaled  by the coil area change
        """
        coil_area, okPressed = QInputDialog.getInt(self, "Set Coil Areas", "Coil Area:")
        if okPressed:
            if not all:
                pem_files, rows = self.get_selected_pem_files()
            else:
                pem_files, rows = self.pem_files, range(self.table.rowCount())
            for pem_file, row in zip(pem_files, rows):
                coil_column = self.columns.index('Coil Area')
                self.scale_coil_area(pem_file, coil_area)
                self.table.item(row, coil_column).setText(str(coil_area))

    def scale_current(self, pem_file, new_current):
        """
        Scale the data according to the change in current
        :param pem_file: PEM File object
        :param new_current: Desired current to scale the data to
        :return: PEM File object with the data scaled
        """
        logging.info('PEMEditor - Scaling PEM File data by current')
        pem_file = self.file_editor.scale_current(pem_file, new_current)
        self.update_table()

    def scale_current_selection(self, all=False):
        """
        Scale the data by current for the selected PEM Files
        """
        current, okPressed = QInputDialog.getDouble(self, "Scale Current", "Current:")
        if okPressed:
            if not all:
                pem_files, rows = self.get_selected_pem_files()
            else:
                pem_files, rows = self.pem_files, range(self.table.rowCount())
            for pem_file, row in zip(pem_files, rows):
                coil_column = self.columns.index('Current')
                self.scale_current(pem_file, current)
                self.table.item(row, coil_column).setText(str(current))

    def reverse_all_data(self, comp):
        logging.info(f'PEMEditor - Reversing data polarity for {comp} component')
        if len(self.pem_files) > 0:
            for pem_file, pem_info_widget in zip(self.pem_files, self.pem_info_widgets):
                pem_info_widget.reverse_polarity(component=comp)
                pem_file = pem_info_widget.pem_file

    def merge_pem_files(self, pem_files):
        logging.info('PEMEditor - Merging PEM Files')
        # Check that all selected files are the same in terms of being averaged and being split
        def pem_files_eligible():
            # if all([pem_file.is_averaged() for pem_file in pem_files]) or all(
            #         [not pem_file.is_averaged() for pem_file in pem_files]):
            if all([pem_file.is_split() for pem_file in pem_files]) or all(
                    [not pem_file.is_split() for pem_file in pem_files]):
                return True
            else:
                return False

        if isinstance(pem_files, list) and len(pem_files) > 1:
            # Data merging section
            if not pem_files_eligible():
                response = self.message.question(self, 'Merge PEM Files',
                                                 'Both files have not been split. Would you like to split the unsplit file(s) and proceed with merging?',
                                                 self.message.Yes | self.message.No)
                if response == self.message.Yes:
                    for pem_file in pem_files:
                        self.split_pem_channels(pem_file)
                else:
                    return

            merged_pem = copy.copy(pem_files[0])
            merged_pem.data = list(chain.from_iterable([pem_file.data for pem_file in pem_files]))
            merged_pem.header['NumReadings'] = str(sum(
                list(chain([int(pem_file.header.get('NumReadings')) for pem_file in pem_files]))))
            merged_pem.is_merged = True
            # Add the '[M]'
            dir = os.path.split(merged_pem.filepath)[0]
            file_name = '[M]' + os.path.split(merged_pem.filepath)[-1]

            merged_pem.filepath = os.path.join(dir, file_name)
            self.save_pem_file(merged_pem)
            return merged_pem
            # else:
            #     self.message.information(None, 'Error',
            #                              'Selected PEM Files not eligible for merging.')
            #     return

    def merge_pem_files_selection(self):
        pem_files, rows = self.get_selected_pem_files()

        if len(pem_files) > 1:
            # First update the PEM Files from the table
            for pem_file, row in zip(pem_files, rows):
                self.update_pem_file_from_table(pem_file, row)
            merged_pem = self.merge_pem_files(pem_files)
            if merged_pem:
                # Remove the old files:
                for row in reversed(rows):
                    self.remove_file(row)
                self.open_pem_files(merged_pem)
        else:
            self.message.information(None, 'Error', 'Must select multiple PEM Files')

    def table_value_changed(self, row, col):
        logging.info(f'PEMEditor - Table value changed at row {row} and column {col}')
        if col == self.columns.index('Coil Area'):
            pem_file = self.pem_files[row]
            old_value = int(pem_file.header.get('CoilArea'))
            try:
                new_value = int(self.table.item(row, col).text())
            except ValueError:
                pass
            else:
                if int(old_value) != int(new_value):
                    self.scale_coil_area(pem_file, int(new_value))
                    self.window().statusBar().showMessage(
                        f"Coil area changed from {str(old_value)} to {str(new_value)}", 2000)

        if col == self.columns.index('File'):
            pem_file = self.pem_files[row]
            old_path = copy.copy(pem_file.filepath)
            new_value = self.table.item(row, col).text()

            if new_value != os.path.basename(pem_file.filepath):
                # if pem_file.old_filepath is None:
                pem_file.old_filepath = old_path
                new_path = '/'.join(old_path.split('/')[:-1]) + '/' + new_value
                pem_file.filepath = new_path
                self.window().statusBar().showMessage(
                    f"File renamed to {str(new_value)}", 2000)

        pem_file = self.pem_files[row]
        # self.update_pem_file_from_table(pem_file, row)
        self.check_for_table_changes(pem_file, row)
        self.check_for_table_anomalies()

    def check_for_table_anomalies(self):
        logging.info('PEMEditor - Checking for table anomalies')
        self.table.blockSignals(True)
        date_column = self.columns.index('Date')
        current_year = str(datetime.datetime.now().year)

        for row in range(self.table.rowCount()):
            if self.table.item(row, date_column):
                date = self.table.item(row, date_column).text()
                year = str(date.split(' ')[-1])
                if year != current_year:
                    self.table.item(row, date_column).setForeground(QtGui.QColor('red'))
                else:
                    self.table.item(row, date_column).setForeground(QtGui.QColor('black'))
        self.table.blockSignals(False)

    def check_for_table_changes(self, pem_file, row):
        logging.info('PEMEditor - Checking for table changes')
        boldFont = QtGui.QFont()
        boldFont.setBold(True)
        normalFont = QtGui.QFont()
        normalFont.setBold(False)

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
            str('Yes' if pem_file.is_split() else 'No')
        ]
        for column in range(self.table.columnCount()):
            if self.table.item(row, column):
                original_value = pem_file_info_list[column]
                if self.table.item(row, column).text() != original_value:
                    self.table.item(row, column).setFont(boldFont)
                else:
                    self.table.item(row, column).setFont(normalFont)
        self.table.resizeColumnsToContents()

    # Saves the pem file in memory using the information in the table
    def update_pem_file_from_table(self, pem_file, table_row, filepath=None):
        logging.info('PEMEditor - Updating PEM File from Table info')

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
                                             self.table.item(table_row, self.columns.index('File')).text())
        else:
            pem_file.filepath = filepath

        add_crs_tag()
        pem_file.header['Date'] = self.table.item(table_row, self.columns.index('Date')).text()
        pem_file.header['Client'] = self.table.item(table_row, self.columns.index('Client')).text()
        pem_file.header['Grid'] = self.table.item(table_row, self.columns.index('Grid')).text()
        pem_file.header['LineHole'] = self.table.item(table_row, self.columns.index('Line/Hole')).text()
        pem_file.header['Loop'] = self.table.item(table_row, self.columns.index('Loop')).text()
        pem_file.tags['Current'] = self.table.item(table_row, self.columns.index('Current')).text()
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

    def save_pem_file(self, pem_file, dir=None, export=False):
        logging.info('PEMEditor - Saving PEM File')
        # The action of saving a PEM file
        if dir is None:
            file_dir = os.path.split(pem_file.filepath)[0]
        else:
            file_dir = dir
        file_name = os.path.splitext(os.path.basename(pem_file.filepath))[0]
        extension = os.path.splitext(pem_file.filepath)[-1]
        overwrite = True

        if not export:
            if pem_file.is_merged:
                if '[M]' in file_name:
                    file_name = re.sub('\[M\]', '', file_name)
                    file_name = '[M]' + file_name
                    # pem_file.is_merged = False
                    overwrite = False

        pem_file.filepath = os.path.join(file_dir + '/' + file_name + extension)
        save_file = self.serializer.serialize(pem_file)
        print(save_file, file=open(pem_file.filepath, 'w+'))

        if overwrite is True and pem_file.old_filepath:
            os.remove(pem_file.old_filepath)
            pem_file.old_filepath = None

    def save_pem_file_to(self, all=False):
        # Saving PEM files to new directory
        if all is False:
            pem_files, rows = self.get_selected_pem_files()
        else:
            pem_files, rows = self.pem_files, range(self.table.rowCount())
        default_path = os.path.split(self.pem_files[-1].filepath)[0]
        self.dialog.setFileMode(QFileDialog.ExistingFiles)
        self.dialog.setAcceptMode(QFileDialog.AcceptSave)
        self.dialog.setDirectory(default_path)
        self.window().statusBar().showMessage(f"Saving PEM {'file' if len(pem_files) == 1 else 'files'}...")
        file_dir = QFileDialog.getExistingDirectory(self, '', default_path, QFileDialog.DontUseNativeDialog)

        if file_dir:
            for pem_file, row in zip(pem_files, rows):
                pem_file = copy.copy(pem_file)
                updated_file = self.update_pem_file_from_table(pem_file, row)

                self.save_pem_file(updated_file, dir=file_dir)
            self.window().statusBar().showMessage(
                f"Save Complete. PEM {'file' if len(pem_files) == 1 else 'files'} saved to {os.path.basename(file_dir)}", 2000)
        else:
            self.window().statusBar().showMessage('Cancelled.', 2000)

    # Save selected PEM files
    def save_pem_file_selection(self, all=False):
        # Saving PEM files to same directory
        if all is False:
            pem_files, rows = self.get_selected_pem_files()
        else:
            pem_files, rows = self.pem_files, range(self.table.rowCount())

        for row, pem_file in zip(rows, pem_files):
            updated_file = self.update_pem_file_from_table(pem_file, row)
            self.save_pem_file(updated_file)
            self.pem_info_widgets[row].open_file(updated_file, parent=self)  # Updates the PEMInfoWidget tables
        if len(pem_files) == 1:
            self.parent.window().statusBar().showMessage(
                'Save Complete. PEM file {} saved.'.format(os.path.basename(pem_files[0].filepath)), 2000)
        else:
            self.parent.window().statusBar().showMessage(
                'Save Complete. {} files saved.'.format(str(len(pem_files))), 2000)
        self.update_table()

    def save_pem_file_as(self):  # Only saves a single file
        row = self.table.currentRow()
        default_path = os.path.split(self.pem_files[-1].filepath)[0]
        self.dialog.setFileMode(QFileDialog.ExistingFiles)
        self.dialog.setAcceptMode(QFileDialog.AcceptSave)
        self.dialog.setDirectory(default_path)
        self.window().statusBar().showMessage('Saving PEM files...')
        file_path = QFileDialog.getSaveFileName(self, '', default_path, 'PEM Files (*.PEM)')[0]  # Returns full filepath

        if file_path:
            pem_file = copy.copy(self.pem_files[row])
            pem_file.filepath = file_path
            updated_file = self.update_pem_file_from_table(pem_file, row, filepath=file_path)

            self.save_pem_file(updated_file)
            self.window().statusBar().showMessage(
                'Save Complete. PEM file saved as {}'.format(os.path.basename(file_path)), 2000)
        else:
            self.window().statusBar().showMessage('Cancelled.', 2000)

    def export_final_pems(self):
        # Saves the files and removes any tags

        pem_files, rows = self.get_selected_pem_files()
        if not pem_files:
            pem_files, rows = copy.copy(self.pem_files), range(self.table.rowCount())

        self.window().statusBar().showMessage(f"Saving PEM {'file' if len(pem_files) == 1 else 'files'}...")
        default_path = os.path.split(self.pem_files[-1].filepath)[0]
        self.dialog.setDirectory(default_path)
        file_dir = QFileDialog.getExistingDirectory(self, '', default_path, QFileDialog.DontUseNativeDialog)

        if file_dir:
            for pem_file, row in zip(pem_files, rows):
                updated_file = self.update_pem_file_from_table(pem_file, row)
                file_name = os.path.splitext(os.path.basename(pem_file.filepath))[0]
                extension = os.path.splitext(pem_file.filepath)[-1]
                new_file_name = re.sub('_\d+', '', re.sub('\[\w\]', '', file_name))
                updated_file.filepath = os.path.join(file_dir, new_file_name + extension)
                self.save_pem_file(updated_file, dir=file_dir, export=True)

            self.window().statusBar().showMessage(
                'Save complete. {0} PEM {1} exported'.format(len(pem_files),
                                                             'file' if len(pem_files) == 1 else 'files'), 2000)
            # self.update_table()
        else:
            self.window().statusBar().showMessage('Cancelled.', 2000)
            pass

    def show_map_3d_viewer(self):
        self.map_viewer_3d = Map3DViewer(self.pem_files, parent=self)
        self.map_viewer_3d.show()

    def show_section_3d_viewer(self):
        pem_file, row = self.get_selected_pem_files()
        if 'borehole' in pem_file[0].survey_type.lower():
            self.section_3d_viewer = Section3DViewer(pem_file[0], parent=self)
            self.section_3d_viewer.show()
        else:
            self.statusBar().showMessage('Invalid survey type', 2000)

    def print_plots(self, final=False, step=False, plan=False):
        logging.info('PEMEditor - Printing plots')

        def get_crs():
            crs = {'Coordinate System': self.systemCBox.currentText(),
                   'Zone': self.zoneCBox.currentText(),
                   'Datum': self.datumCBox.currentText()}
            return crs

        def get_save_file():
            default_path = os.path.split(self.pem_files[-1].filepath)[0]
            self.dialog.setDirectory(default_path)
            if __name__ == '__main__':
                save_dir = r'C:\_Data\2019\_Mowgli Testing\test'  # For testing purposes
            else:
                save_dir = os.path.splitext(QFileDialog.getSaveFileName(self, '', default_path)[0])[0]
                # Returns full filepath. For single PDF file
            return save_dir

        if len(self.pem_files) > 0:
            self.window().statusBar().showMessage('Saving plots...')

            plot_kwargs = {'HideGaps': self.hide_gaps_checkbox.isChecked(),
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
                           'CRS': get_crs()}

            pem_files_selection, rows = self.get_selected_pem_files()
            if pem_files_selection:
                pem_files = copy.copy(pem_files_selection)
            else:
                pem_files = copy.copy(self.pem_files)
                rows = range(self.table.rowCount())
            ri_files = []
            for row, pem_file in zip(rows, pem_files):
                ri_files.append(self.pem_info_widgets[row].ri_file)
                self.update_pem_file_from_table(pem_file, row)
                if not pem_file.is_averaged():
                    self.file_editor.average(pem_file)
                if not pem_file.is_split():
                    self.file_editor.split_channels(pem_file)

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

            # Save all plots
            if final is True:
                if not all([plot_kwargs['CRS'].get('Coordinate System'), plot_kwargs['CRS'].get('Datum')]):
                    response = self.message.question(self, 'No CRS',
                                                     'No CRS has been selected. '
                                                     'Do you wish to processed without a plan map?',
                                                     self.message.Yes | self.message.No)
                    if response == self.message.No:
                        return
                save_dir = get_save_file()
                if save_dir:
                    # PEM Files and RI files zipped together for when they get sorted
                    printer = PEMPrinter(save_dir, files=list(zip(pem_files, ri_files)), **plot_kwargs)
                    self.window().statusBar().addPermanentWidget(printer.pb)
                    printer.print_final_plots()
                    printer.pb.hide()
                else:
                    self.window().statusBar().showMessage('Cancelled', 2000)

            # Only save step plots
            elif step is True:
                save_dir = get_save_file()
                if save_dir:
                    # PEM Files and RI files zipped together for when they get sorted
                    printer = PEMPrinter(save_dir, files=list(zip(pem_files, ri_files)), **plot_kwargs)
                    self.window().statusBar().addPermanentWidget(printer.pb)
                    printer.print_step_plots()
                    printer.pb.hide()
                else:
                    self.window().statusBar().showMessage('Cancelled', 2000)
            # Only save plan map
            elif plan is True:
                if not all([plot_kwargs['CRS'].get('Coordinate System'), plot_kwargs['CRS'].get('Datum')]):
                    self.message.information(self, 'No CRS',
                                             'No CRS has been selected. '
                                             'Please selected a CRS to proceed.')
                else:
                    save_dir = get_save_file()
                    if save_dir:
                        # PEM Files and RI files zipped together for when they get sorted
                        printer = PEMPrinter(save_dir, files=list(zip(pem_files, ri_files)), **plot_kwargs)
                        self.window().statusBar().addPermanentWidget(printer.pb)
                        printer.print_plan_map()
                        printer.pb.hide()
                    else:
                        self.window().statusBar().showMessage('Cancelled', 2000)
            else:
                raise ValueError
            self.window().statusBar().showMessage('Plots saved', 2000)

    def remove_file(self, table_row):
        logging.info(f'PEMEditor - Removing file at row {table_row}')
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

    # Remove selected files
    def remove_file_selection(self):
        pem_files, rows = self.get_selected_pem_files()
        for row in reversed(rows):
            self.window().statusBar().showMessage('{0} removed'.format(self.pem_files[row].filepath), 2000)
            self.remove_file(row)

    def reset_crs(self):
        logging.info('PEMEditor - Reset CRS')
        self.systemCBox.setCurrentIndex(0)
        self.zoneCBox.setCurrentIndex(0)
        self.datumCBox.setCurrentIndex(0)

    def populate_gps_boxes(self):
        logging.info('PEMEditor - Filling CRS information')
        for system in self.gps_systems:
            self.systemCBox.addItem(system)
        for zone in self.gps_zones:
            self.zoneCBox.addItem(zone)
        for datum in self.gps_datums:
            self.datumCBox.addItem(datum)

    # Creates the table when the editor is first opened
    def create_table(self):
        self.columns = ['File', 'Date', 'Client', 'Grid', 'Line/Hole', 'Loop', 'Current', 'Coil Area', 'First Station',
                        'Last Station', 'Averaged', 'Split']
        self.table.setColumnCount(len(self.columns))
        self.table.setHorizontalHeaderLabels(self.columns)
        self.table.setSizeAdjustPolicy(
            QAbstractScrollArea.AdjustToContents)
        # self.table.resizeColumnsToContents()
        # header = self.table.horizontalHeader()
        # header.setSectionResizeMode(0, QHeaderView.Stretch)
        # header.setSectionResizeMode(1, QHeaderView.Stretch)
        # header.setSectionResizeMode(2, QHeaderView.Stretch)
        # header.setSectionResizeMode(3, QHeaderView.Stretch)

    def add_to_table(self, pem_file):
        logging.info(f'PEMEditor - Adding PEM File {os.path.basename(pem_file.filepath)} to table')
        self.table.blockSignals(True)
        header = pem_file.header
        tags = pem_file.tags
        file = os.path.basename(pem_file.filepath)
        date = header.get('Date')
        client = self.client_edit.text() if self.share_client_cbox.isChecked() else header.get('Client')
        grid = self.grid_edit.text() if self.share_grid_cbox.isChecked() else header.get('Grid')
        loop = self.loop_edit.text() if self.share_loop_cbox.isChecked() else header.get('Loop')
        current = tags.get('Current')
        coil_area = pem_file.header.get('CoilArea')
        averaged = 'Yes' if pem_file.is_averaged() else 'No'
        split = 'Yes' if pem_file.is_split() else 'No'
        line = header.get('LineHole')
        start_stn = self.min_range_edit.text() if self.share_range_checkbox.isChecked() else str(
            min(pem_file.get_converted_unique_stations()))
        end_stn = self.max_range_edit.text() if self.share_range_checkbox.isChecked() else str(
            max(pem_file.get_converted_unique_stations()))

        new_row = [file, date, client, grid, line, loop, current, coil_area, start_stn, end_stn, averaged, split]

        row_pos = self.table.rowCount()
        self.table.insertRow(row_pos)

        for i, column in enumerate(self.columns):
            item = QTableWidgetItem(new_row[i])
            if i == self.columns.index('Averaged') or i == self.columns.index('Split'):
                item.setFlags(QtCore.Qt.ItemIsSelectable)
            item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.table.setItem(row_pos, i, item)

        if self.table.item(row_pos, self.columns.index('Averaged')).text().lower() == 'no':
            self.table.item(row_pos, self.columns.index('Averaged')).setForeground(QtGui.QColor('red'))

        if self.table.item(row_pos, self.columns.index('Split')).text().lower() == 'no':
            self.table.item(row_pos, self.columns.index('Split')).setForeground(QtGui.QColor('red'))

        self.check_for_table_changes(pem_file, row_pos)
        self.check_for_table_anomalies()
        self.table.blockSignals(False)

    # Deletes and re-populates the table rows with the new information
    def update_table(self):
        logging.info('PEMEditor - Refreshing PEMEditor table')
        if len(self.pem_files) > 0:
            self.table.blockSignals(True)
            while self.table.rowCount() > 0:
                self.table.removeRow(0)
            for pem_file in self.pem_files:
                self.add_to_table(pem_file)
            self.table.blockSignals(False)
        else:
            pass

    def sort_all_station_gps(self):
        if len(self.pem_files) > 0:
            for i in range(self.stackedWidget.count()):
                widget = self.stackedWidget.widget(i)
                if widget.station_gps:
                    widget.fill_station_table(widget.station_gps.get_sorted_gps(widget.get_station_gps()))
                else:
                    pass
            self.window().statusBar().showMessage('All stations have been sorted', 2000)

    def sort_all_loop_gps(self):
        if len(self.pem_files) > 0:
            for i in range(self.stackedWidget.count()):
                widget = self.stackedWidget.widget(i)
                if widget.loop_gps:
                    widget.fill_loop_table(widget.loop_gps.get_sorted_gps(widget.get_loop_gps()))
                else:
                    pass
            self.window().statusBar().showMessage('All loops have been sorted', 2000)

    def fill_share_header(self):
        logging.info('PEMEditor - Filling share header information')
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
        logging.info('PEMEditor - Filling share range information')
        if len(self.pem_files) > 0:
            all_stations = [file.get_converted_unique_stations() for file in self.pem_files]
            min_range, max_range = str(min(chain.from_iterable(all_stations))), str(
                max(chain.from_iterable(all_stations)))
            self.min_range_edit.setText(min_range)
            self.max_range_edit.setText(max_range)
            # self.update_table()
        else:
            self.min_range_edit.setText('')
            self.max_range_edit.setText('')

    def share_loop(self):
        logging.info('PEMEditor - Sharing loop GPS')
        selected_widget = self.pem_info_widgets[self.table.currentRow()]
        try:
            selected_widget_loop = selected_widget.get_loop_gps()
        except:
            return
        else:
            for widget in self.pem_info_widgets:
                widget.fill_loop_table(selected_widget_loop)

    def share_collar(self):
        logging.info('PEMEditor - Sharing collar GPS')
        selected_widget = self.pem_info_widgets[self.table.currentRow()]
        try:
            selected_widget_collar = [selected_widget.get_collar_gps()]
        except:
            return
        else:
            for widget in list(filter(lambda x: 'borehole' in x.pem_file.survey_type.lower(), self.pem_info_widgets)):
                widget.fill_collar_gps_table(selected_widget_collar)

    def share_segments(self):
        logging.info('PEMEditor - Sharing borehole segments')
        selected_widget = self.pem_info_widgets[self.table.currentRow()]
        try:
            selected_widget_geometry = selected_widget.get_geometry_segments()
        except:
            return
        else:
            for widget in list(filter(lambda x: 'borehole' in x.pem_file.survey_type.lower(), self.pem_info_widgets)):
                widget.fill_geometry_table(selected_widget_geometry)

    def toggle_share_client(self):
        if self.share_client_cbox.isChecked():
            self.client_edit.setEnabled(True)
            self.update_table()
        else:
            self.client_edit.setEnabled(False)
            self.update_table()

    def toggle_share_grid(self):
        if self.share_grid_cbox.isChecked():
            self.grid_edit.setEnabled(True)
            self.update_table()
        else:
            self.grid_edit.setEnabled(False)
            self.update_table()

    def toggle_share_loop(self):
        if self.share_loop_cbox.isChecked():
            self.loop_edit.setEnabled(True)
            self.update_table()
        else:
            self.loop_edit.setEnabled(False)
            self.update_table()

    def toggle_share_range(self):
        if self.share_range_checkbox.isChecked():
            self.min_range_edit.setEnabled(True)
            self.max_range_edit.setEnabled(True)
            self.update_table()
        else:
            self.min_range_edit.setEnabled(False)
            self.max_range_edit.setEnabled(False)
            self.update_table()

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
        logging.info('PEMEditor - Batch renaming')

        def rename_pem_files():
            if len(self.batch_name_editor.pem_files) > 0:
                self.batch_name_editor.accept_changes()
                for i, row in enumerate(rows):
                    self.pem_files[row] = self.batch_name_editor.pem_files[i]
                self.update_table()

        pem_files, rows = self.get_selected_pem_files()
        if not pem_files:
            pem_files, rows = self.pem_files, range(self.table.rowCount())

        self.batch_name_editor = BatchNameEditor(pem_files, type=type)
        self.batch_name_editor.buttonBox.accepted.connect(rename_pem_files)
        self.batch_name_editor.acceptChangesSignal.connect(rename_pem_files)
        self.batch_name_editor.buttonBox.rejected.connect(self.batch_name_editor.close)

        self.batch_name_editor.show()

    def import_ri_files(self):
        logging.info('PEMEditor - Importing RI Files')

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
    logging.info('BatchNameEditor')
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

        self.columns = ['Old Name', 'New Name']
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
        self.table.setColumnCount(len(self.columns))
        self.table.setHorizontalHeaderLabels(self.columns)
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
                    old_path = copy.copy(pem_file.filepath)
                    new_path = '/'.join(old_path.split('/')[:-1]) + '/' + new_name
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
    logging.info('BatchRIImporter')
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
        self.ri_files = []

        if len(ri_filepaths) == len(self.pem_files):

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
        logging.info('PlanMapOptions')
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
        logging.info('PEMFileSplitter')
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
        self.columns = ['Station']
        self.table.setColumnCount(len(self.columns))
        self.table.setHorizontalHeaderLabels(self.columns)
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
        logging.info('Map3DViewer')
        super().__init__()
        self.setupUi(self)
        self.pem_files = pem_files
        self.parent = parent
        self.setWindowTitle("3D Map Viewer")

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
        self.ax = self.figure.add_subplot(111, projection='3d')

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

    def __init__(self, pem_file, parent=None):
        super().__init__()
        self.setupUi(self)
        self.pem_file = pem_file
        self.parent = parent
        self.list_points = []

        self.setWindowTitle('3D Section Viewer')

        self.draw_loop = self.draw_loop_cbox.isChecked()
        self.draw_borehole = self.draw_borehole_cbox.isChecked()
        self.draw_mag_field = self.draw_mag_field_cbox.isChecked()

        self.label_loop = self.label_loop_cbox.isChecked()
        self.label_loop_anno = self.label_loop_anno_cbox.isChecked()
        self.label_borehole = self.label_borehole_cbox.isChecked()

        self.draw_loop_cbox.toggled.connect(self.toggle_loop)
        self.draw_borehole_cbox.toggled.connect(self.toggle_borehole)
        self.draw_mag_field_cbox.toggled.connect(self.toggle_mag_field)

        self.draw_grid = self.draw_grid_cbox.isChecked()

        self.label_loop_cbox.toggled.connect(self.toggle_loop_label)
        self.label_loop_anno_cbox.toggled.connect(self.toggle_loop_anno_labels)
        self.label_borehole_cbox.toggled.connect(self.toggle_borehole_label)
        self.label_segments_cbox.toggled.connect(self.toggle_segment_labels)

        self.draw_grid_cbox.toggled.connect(self.toggle_grid)

        self.figure = Figure()
        self.canvas = FigureCanvas(self.figure)
        # self.canvas.setFocusPolicy(QtCore.Qt.ClickFocus)  # Needed for key-press events
        # self.canvas.setFocus()

        self.map_layout.addWidget(self.canvas)
        self.ax = self.figure.add_subplot(111, projection='3d')

        self.section_plotter = Section3D(self.ax, self.pem_file, parent=self)
        self.section_plotter.format_ax()
        self.update_canvas()

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

    def update_canvas(self):
        self.toggle_loop()
        self.toggle_borehole()
        self.toggle_mag_field()
        self.toggle_loop_label()
        self.toggle_loop_anno_labels()
        self.toggle_borehole_label()
        self.toggle_segment_labels()
        self.toggle_grid()

    def toggle_grid(self):
        if self.draw_grid:
            self.ax.grid(b=True)
        else:
            self.ax.grid(b=False)
        self.canvas.draw()

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


def main():
    app = QApplication(sys.argv)
    mw = PEMEditorWindow()
    mw.show()
    pg = PEMGetter()
    pem_files = pg.get_pems()
    mw.open_pem_files(pem_files)

    # section = Section3DViewer(pem_files)
    # section.show()

    map = Map3DViewer(pem_files)
    map.show()

    # mw.open_pem_files(r'C:\_Data\2019\_Mowgli Testing\DC6200E-LP124.PEM')
    # mw.open_gpx_files(r'C:\_Data\2019\_Mowgli Testing\loop_13_transmitters.GPX')

    # mw.open_pem_files(r'C:\_Data\2019\_Mowgli Testing\1200NAv.PEM')
    # mw.open_ri_file([r'C:\_Data\2019\_Mowgli Testing\1200N.RI3'])
    # mw.print_plots(step=True)
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
