import copy
import logging
import os
import re
import sys
from decimal import getcontext
from itertools import chain

from PyQt5 import (QtCore, QtGui, uic)
from PyQt5.QtWidgets import (QWidget, QMainWindow, QApplication, QDesktopWidget, QMessageBox, QFileDialog,
                             QAbstractScrollArea, QTableWidgetItem, QAction, QMenu, QTextEdit, QToolButton,
                             QInputDialog, QHeaderView, QShortcut)

from src.gps.loop_gps import LoopGPSParser
from src.gps.station_gps import StationGPSParser
from src.pem.pem_file_editor import PEMFileEditor
from src.pem.pem_parser import PEMParser
from src.pem.pem_file import PEMFile
from src.pem.pem_serializer import PEMSerializer
from src.qt_py.pem_info_widget import PEMFileInfoWidget

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s', datefmt='%d-%b-%y %H:%M:%S')

__version__ = '0.2.0'

_station_gps_tab = 2
_loop_gps_tab = 1
getcontext().prec = 6

if getattr(sys, 'frozen', False):
    # If the application is run as a bundle, the pyInstaller bootloader
    # extends the sys module by a flag frozen=True and sets the app
    # path into variable _MEIPASS'.
    application_path = sys._MEIPASS
    editorCreatorFile = 'qt_ui\\pem_editor_widget.ui'
    editorWindowCreatorFile = 'qt_ui\\pem_editor_window.ui'
    lineNameEditorCreatorFile = 'qt_ui\\line_name_editor.ui'
    icons_path = 'icons'
else:
    application_path = os.path.dirname(os.path.abspath(__file__))
    editorCreatorFile = os.path.join(os.path.dirname(application_path), 'qt_ui\\pem_editor_widget.ui')
    editorWindowCreatorFile = os.path.join(os.path.dirname(application_path), 'qt_ui\\pem_editor_window.ui')
    lineNameEditorCreatorFile = os.path.join(os.path.dirname(application_path), 'qt_ui\\line_name_editor.ui')
    icons_path = os.path.join(os.path.dirname(application_path), "qt_ui\\icons")

# Load Qt ui file into a class
Ui_PEMEditorWidget, QtBaseClass = uic.loadUiType(editorCreatorFile)
Ui_PEMEditorWindow, QtBaseClass = uic.loadUiType(editorWindowCreatorFile)
Ui_LineNameEditorWidget, QtBaseClass = uic.loadUiType(lineNameEditorCreatorFile)

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
        self.initApps()
        self.initActions()
        self.initSignals()

        self.pem_files = []
        self.gps_files = []
        self.pem_info_widgets = []

        self.create_table()

    def initUi(self):
        def center_window(self):
            qtRectangle = self.frameGeometry()
            centerPoint = QDesktopWidget().availableGeometry().center()
            qtRectangle.moveCenter(centerPoint)
            self.move(qtRectangle.topLeft())

        self.setupUi(self)

        self.setWindowTitle("PEMEditor  v" + str(__version__))
        self.setWindowIcon(
            QtGui.QIcon(os.path.join(icons_path, 'crone_logo.ico')))
        self.setGeometry(500, 300, 1500, 800)
        center_window(self)

    def initApps(self):
        self.message = QMessageBox()
        self.dialog = QFileDialog()
        self.parser = PEMParser()
        self.file_editor = PEMFileEditor()
        self.message = QMessageBox()
        self.dialog = QFileDialog()
        # self.pem_info_widget = PEMFileInfoWidget()
        self.station_gps_parser = StationGPSParser()
        self.serializer = PEMSerializer()

        # self.layout.addWidget(self)
        # self.setCentralWidget(self.table)

        self.stackedWidget.hide()
        self.pemInfoDockWidget.hide()
        self.plotsDockWidget.hide()
        # self.plotsDockWidget.setWidget(self.tabWidget)
        # self.addDockWidget(QtCore.Qt.RightDockWidgetArea, self.dockWidget)

    def initActions(self):
        self.setAcceptDrops(True)
        self.window().statusBar().showMessage('Ready')

        self.openFile = QAction("&Open...", self)
        self.openFile.setShortcut("Ctrl+O")
        self.openFile.setStatusTip('Open file')
        self.openFile.triggered.connect(self.open_file_dialog)

        self.saveFiles = QAction("&Save Files", self)
        self.saveFiles.setShortcut("Ctrl+S")
        self.saveFiles.setStatusTip("Save all files")
        self.saveFiles.triggered.connect(self.save_all)

        self.saveFilesTo = QAction("&Save Files To...", self)
        self.saveFilesTo.setShortcut("F12")
        self.saveFilesTo.setStatusTip("Save all files at specified location.")
        self.saveFilesTo.triggered.connect(self.save_all_to)

        self.del_file = QAction("&Remove File", self)
        self.del_file.setShortcut("Del")
        self.del_file.triggered.connect(self.remove_file_selection)
        self.addAction(self.del_file)
        self.del_file.setEnabled(False)

        self.clearFiles = QAction("&Clear Files", self)
        self.clearFiles.setShortcut("Shift+Del")
        self.clearFiles.setStatusTip("Clear all files")
        self.clearFiles.triggered.connect(self.clear_files)

        self.fileMenu = self.menubar.addMenu('&File')
        self.fileMenu.addAction(self.openFile)
        self.fileMenu.addAction(self.saveFiles)
        self.fileMenu.addAction(self.saveFilesTo)
        self.fileMenu.addAction(self.clearFiles)

        self.averageAllPems = QAction("&Average All PEM Files", self)
        self.averageAllPems.setStatusTip("Average all PEM files")
        self.averageAllPems.setShortcut("F5")
        self.averageAllPems.triggered.connect(self.average_all_pem_files)

        self.splitAllPems = QAction("&Split All PEM Files", self)
        self.splitAllPems.setStatusTip("Split all PEM files")
        self.splitAllPems.setShortcut("F6")
        self.splitAllPems.triggered.connect(self.split_all_pem_files)

        self.coilAreaAllPems = QAction("&Change All Coil Areas", self)
        self.coilAreaAllPems.setStatusTip("Change all coil areas to the same value")
        self.coilAreaAllPems.setShortcut("F7")
        self.coilAreaAllPems.triggered.connect(self.scale_all_coil_area)

        self.editLineNames = QAction("&Rename All Lines/Holes", self)
        self.editLineNames.setStatusTip("Rename all line/hole names")
        self.editLineNames.setShortcut("F2")
        self.editLineNames.triggered.connect(lambda: self.batch_rename(type='Line'))

        self.editFileNames = QAction("&Rename All Files", self)
        self.editFileNames.setStatusTip("Rename all file names")
        self.editFileNames.setShortcut("F3")
        self.editFileNames.triggered.connect(lambda: self.batch_rename(type='File'))

        self.sortAllStationGps = QAction("&Sort All Station GPS", self)
        self.sortAllStationGps.setStatusTip("Sort the station GPS for every file")
        self.sortAllStationGps.triggered.connect(self.sort_all_station_gps)

        self.sortAllLoopGps = QAction("&Sort All Loop GPS", self)
        self.sortAllLoopGps.setStatusTip("Sort the loop GPS for every file")
        self.sortAllLoopGps.triggered.connect(self.sort_all_loop_gps)

        self.PEMMenu = self.menubar.addMenu('&PEM')
        self.PEMMenu.addAction(self.averageAllPems)
        self.PEMMenu.addAction(self.splitAllPems)
        self.PEMMenu.addAction(self.coilAreaAllPems)
        self.PEMMenu.addAction(self.editLineNames)
        self.PEMMenu.addAction(self.editFileNames)

        self.GPSMenu = self.menubar.addMenu('&GPS')
        self.GPSMenu.addAction(self.sortAllStationGps)
        self.GPSMenu.addAction(self.sortAllLoopGps)

    def initSignals(self):

        self.table.viewport().installEventFilter(self)

        self.table.installEventFilter(self)
        self.table.setFocusPolicy(QtCore.Qt.StrongFocus)

        self.table.itemSelectionChanged.connect(self.display_pem_info_widget)
        self.table.cellChanged.connect(self.table_value_changed)

        self.share_header_checkbox.stateChanged.connect(self.toggle_share_header)
        self.reset_header_btn.clicked.connect(self.fill_share_header)
        self.client_edit.textChanged.connect(self.update_table)
        self.grid_edit.textChanged.connect(self.update_table)
        self.loop_edit.textChanged.connect(self.update_table)

        self.share_range_checkbox.stateChanged.connect(self.toggle_share_range)
        self.reset_range_btn.clicked.connect(self.fill_share_range)
        self.min_range_edit.textChanged.connect(self.update_table)
        self.max_range_edit.textChanged.connect(self.update_table)

    def open_file_dialog(self):
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
        if all([url.lower().endswith('pem') for url in urls]):
            pem_files = True
        elif all([url.lower().endswith('txt') or url.lower().endswith('csv') for url in urls]):
            text_files = True

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
            eligible_tabs = [_station_gps_tab, _loop_gps_tab]
            gps_conditions = bool(all([
                e.answerRect().intersects(self.pemInfoDockWidget.geometry()),
                text_files is True,
                self.stackedWidget.currentWidget().tabs.currentIndex() in eligible_tabs,
                len(self.pem_files) > 0
            ]))

            if pem_conditions is True or gps_conditions is True:
                e.acceptProposedAction()
            else:
                e.ignore()

    def dropEvent(self, e):
        urls = [url.toLocalFile() for url in e.mimeData().urls()]
        self.open_files(urls)

    def open_files(self, files):

        if not isinstance(files, list) and isinstance(files, str):
            files = [files]
        pem_files = [file for file in files if file.lower().endswith('pem')]
        gps_files = [file for file in files if file.lower().endswith('txt') or file.lower().endswith('csv')]

        if len(pem_files) > 0:
            self.open_pem_files(pem_files)

        if len(gps_files) > 0:
            self.open_gps_files(gps_files)

    def open_pem_files(self, pem_files):
        logging.info('open_pem_files')
        if not isinstance(pem_files, list):
            pem_files = [pem_files]

        self.stackedWidget.show()
        self.pemInfoDockWidget.show()

        for pem_file in pem_files:
            pemInfoWidget = PEMFileInfoWidget()
            if not isinstance(pem_file, PEMFile):
                pem_file = self.parser.parse(pem_file)
            try:
                pem_widget = pemInfoWidget.open_file(pem_file, parent=self)
                self.pem_files.append(pem_file)
                self.pem_info_widgets.append(pem_widget)
                self.stackedWidget.addWidget(pem_widget)
                self.add_to_table(pem_file)

                if len(self.pem_files) == 1:  # The initial fill of the header and station info
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

        station_gps_parser = StationGPSParser()
        loop_gps_parser = LoopGPSParser()

        if len(gps_files) > 0:
            file = read_gps_files(gps_files)
            try:
                pem_info_widget = self.stackedWidget.currentWidget()
                station_gps_tab = pem_info_widget.tabs.widget(_station_gps_tab)
                loop_gps_tab = pem_info_widget.tabs.widget(_loop_gps_tab)
                current_tab = self.stackedWidget.currentWidget().tabs.currentWidget()

                if station_gps_tab == current_tab:
                    gps_file = station_gps_parser.parse(file)
                    pem_info_widget.station_gps = gps_file

                    if station_gps_tab.findChild(QToolButton, 'sort_station_gps_button').isChecked():
                        gps_data = gps_file.get_sorted_gps()
                    else:
                        gps_data = gps_file.get_gps()
                    pem_info_widget.fill_station_table(gps_data)

                elif loop_gps_tab == current_tab:
                    gps_file = loop_gps_parser.parse(file)
                    pem_info_widget.loop_gps = gps_file

                    if loop_gps_tab.findChild(QToolButton, 'sort_loop_button').isChecked():
                        gps_data = gps_file.get_sorted_gps()
                    else:
                        gps_data = gps_file.get_gps()
                    pem_info_widget.fill_loop_table(gps_data)

                else:
                    pass

            except Exception as e:
                logging.info(str(e))
                self.message.information(None, 'PEMEditorWidget: open_gps_files error', str(e))
                pass

    def clear_files(self):
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

    def save_all(self):
        if len(self.pem_files) > 0:
            for row in range(self.table.rowCount()):
                updated_file = self.update_pem_file_from_table(self.pem_files[row], row)
                self.save_pem_file(updated_file)
                self.window().statusBar().showMessage(
                    'Save complete. {0} PEM files saved'.format(len(self.pem_files)), 2000)
            self.update_table()
        else:
            self.window().statusBar().showMessage('No PEM files to save', 2000)

    def save_all_to(self):
        # Allows the user to select where to save all the files. Save As currently not needed
        # since saving is done smartly

        if len(self.pem_files) > 0:
            default_path = os.path.split(self.pem_files[-1].filepath)[0]
            # self.dialog.setFileMode(QFileDialog.ExistingFiles)
            # self.dialog.setOption(QFileDialog.ShowDirsOnly, on=False)
            self.dialog.setNameFilter('PEM Files (*.PEM)')
            self.dialog.setAcceptMode(QFileDialog.AcceptSave)
            self.dialog.setDirectory(default_path)
            self.window().statusBar().showMessage('Saving PEM files...')
            file_dir = QFileDialog.getExistingDirectory(self, '', default_path, QFileDialog.DontUseNativeDialog)

            if file_dir:
                for row in range(self.table.rowCount()):
                    pem_file = self.pem_files[row]
                    updated_file = self.update_pem_file_from_table(self.pem_files[row], row)
                    # file_name = os.path.splitext(os.path.basename(pem_file.filepath))[0]
                    # extension = os.path.splitext(pem_file.filepath)[-1]
                    # updated_file.filepath = os.path.join(file_dir, file_name + extension)

                    self.save_pem_file(updated_file, dir=file_dir)
                    self.window().statusBar().showMessage(
                        'Save complete. {0} PEM files saved'.format(len(self.pem_files)), 2000)
                self.update_table()
            else:
                self.window().statusBar().showMessage('No directory chosen', 2000)
                logging.info("No directory chosen, aborted save")
                pass

    def contextMenuEvent(self, event):
        if self.table.underMouse():
            if self.table.selectionModel().selectedIndexes():
                self.table.menu = QMenu(self.table)
                self.table.remove_file_action = QAction("&Remove", self)
                self.table.remove_file_action.triggered.connect(self.remove_file_selection)

                self.table.save_file_action = QAction("&Save", self)
                self.table.save_file_action.triggered.connect(self.save_pem_file_selection)

                self.table.save_file_as_action = QAction("&Save As...", self)
                self.table.save_file_as_action.triggered.connect(self.save_as_pem_file_selection)

                self.table.merge_action = QAction("&Merge", self)
                self.table.merge_action.triggered.connect(self.merge_pem_files_selection)

                self.table.average_action = QAction("&Average", self)
                self.table.average_action.triggered.connect(self.average_select_pem)

                self.table.split_action = QAction("&Split", self)
                self.table.split_action.triggered.connect(self.split_select_pem)

                self.table.scale_ca_action = QAction("&Coil Area", self)
                self.table.scale_ca_action.triggered.connect(self.scale_coil_area_selection)

                self.table.share_loop_action = QAction("&Share Loop", self)
                self.table.share_loop_action.triggered.connect(self.share_loop)

                self.table.rename_lines_action = QAction("&Rename Lines/Holes", self)
                self.table.rename_lines_action.triggered.connect(lambda: self.batch_rename(type='Line', selected=True))

                self.table.rename_files_action = QAction("&Rename Files", self)
                self.table.rename_files_action.triggered.connect(lambda: self.batch_rename(type='File', selected=True))

                self.table.menu.addAction(self.table.save_file_action)
                if len(self.table.selectionModel().selectedIndexes()) == len(self.columns):
                    # If only 1 row is selected...
                    self.table.menu.addAction(self.table.save_file_as_action)
                self.table.menu.addSeparator()
                if len(self.table.selectionModel().selectedIndexes()) > len(self.columns):
                    # If more than 2 rows are selected...
                    self.table.menu.addAction(self.table.merge_action)
                self.table.menu.addAction(self.table.average_action)
                self.table.menu.addAction(self.table.split_action)
                self.table.menu.addAction(self.table.scale_ca_action)
                if len(self.pem_files) > 1:
                    self.table.menu.addAction(self.table.share_loop_action)
                if len(self.table.selectionModel().selectedIndexes()) > len(self.columns):
                    self.table.menu.addSeparator()
                    self.table.menu.addAction(self.table.rename_lines_action)
                    self.table.menu.addAction(self.table.rename_files_action)
                self.table.menu.addSeparator()
                self.table.menu.addAction(self.table.remove_file_action)

                self.table.menu.popup(QtGui.QCursor.pos())
            else:
                pass
        else:
            pass

    # Un-selects items from the table when clicking away from the table
    def eventFilter(self, source, event):
        if (event.type() == QtCore.QEvent.MouseButtonPress and
                source is self.table.viewport() and
                self.table.itemAt(event.pos()) is None):
            self.table.clearSelection()
        elif source == self.table and event.type() == QtCore.QEvent.FocusIn:
            self.del_file.setEnabled(True)   # Makes the 'Del' shortcut work when the table is in focus
        elif source == self.table and event.type() == QtCore.QEvent.FocusOut:
            self.del_file.setEnabled(False)
        return super(QWidget, self).eventFilter(source, event)

    def get_selected_pem_files(self):
        rows = []
        selected_pem_files = []

        for i in self.table.selectedIndexes():
            if i.row() not in rows:
                rows.append(i.row())

        for row in rows:
            selected_pem_files.append(self.pem_files[row])

        return selected_pem_files

    def display_pem_info_widget(self):
        # self.stackedWidget.show()
        self.stackedWidget.setCurrentIndex(self.table.currentRow())

    def average_pem_data(self, pem_file):
        if pem_file.is_averaged():
            self.window().statusBar().showMessage('File is already averaged.', 2000)
            return
        else:
            pem_file = self.file_editor.average(pem_file)
            self.window().statusBar().showMessage('File averaged.', 2000)

    def average_select_pem(self, pem_file=None):
        if not pem_file:
            pem_files = self.get_selected_pem_files()
            for pem_file in pem_files:
                self.average_pem_data(pem_file)
        else:
            self.average_pem_data(pem_file)
        self.update_table()

    def average_all_pem_files(self):
        if len(self.pem_files) > 0:
            for pem_file in self.pem_files:
                self.average_pem_data(pem_file)
            self.update_table()
            self.window().statusBar().showMessage('All files averaged.', 2000)
        else:
            pass

    def split_pem_data(self, pem_file):
        if pem_file.is_split():
            self.window().statusBar().showMessage('File is already split.', 2000)
            return
        else:
            pem_file = self.file_editor.split_channels(pem_file)
            self.window().statusBar().showMessage('File split.', 2000)

    def split_select_pem(self, pem_file=None):
        if not pem_file:
            pem_files = self.get_selected_pem_files()
            for pem_file in pem_files:
                self.split_pem_data(pem_file)
        else:
            self.split_pem_data(pem_file)
        self.update_table()

    def split_all_pem_files(self):
        if len(self.pem_files) > 0:
            for pem_file in self.pem_files:
                self.split_pem_data(pem_file)
            self.update_table()
            self.window().statusBar().showMessage('All files split.', 2000)
        else:
            pass

    def scale_coil_area(self, pem_file, new_coil_area):
        pem_file = self.file_editor.scale_coil_area(pem_file, new_coil_area)
        self.update_table()

    def scale_coil_area_selection(self):
        coil_area, okPressed = QInputDialog.getInt(self, "Set Coil Areas", "Coil Area:")
        if okPressed:
            rows = []
            for i in self.table.selectedIndexes():
                if i.row() not in rows:
                    rows.append(i.row())

            for row in rows:
                coil_column = self.columns.index('Coil Area')
                pem_file = self.pem_files[row]
                self.scale_coil_area(pem_file, coil_area)
                self.table.item(row, coil_column).setText(str(coil_area))

    def scale_all_coil_area(self):
        if len(self.pem_files) > 0:
            coil_area, okPressed = QInputDialog.getInt(self, "Set Coil Areas", "Coil Area:")
            if okPressed:
                for i, pem_file in enumerate(self.pem_files):
                    coil_column = self.columns.index('Coil Area')
                    self.table.item(i, coil_column).setText(str(coil_area))

    def merge_pem_files(self, pem_files):

        # Check that all selected files are the same in terms of being averaged and being split
        def pem_files_eligible(pem_files_list):
            if all([pem_file.is_averaged() for pem_file in pem_files]) or all(
                    [not pem_file.is_averaged() for pem_file in pem_files]):
                if all([pem_file.is_split() for pem_file in pem_files]) or all(
                        [not pem_file.is_split() for pem_file in pem_files]):
                    return True
            else:
                return False

        if isinstance(pem_files, list) and len(pem_files) > 1:
            # Data merging section
            if pem_files_eligible(pem_files):
                merged_pem = copy.copy(pem_files[0])
                merged_pem.data = list(chain.from_iterable([pem_file.data for pem_file in pem_files]))
                merged_pem.header['NumReadings'] = str(sum(
                    list(chain([int(pem_file.header.get('NumReadings')) for pem_file in pem_files]))))
                merged_pem.is_merged = True
                # Add the '[M]'
                merged_pem.filepath = os.path.splitext(merged_pem.filepath)[0] + '[M]' + \
                                      os.path.splitext(merged_pem.filepath)[1]

                return merged_pem

            else:
                self.message.information(None, 'Error',
                                         'Must select multiple PEM files')
                return

        else:
            self.message.information(None, 'Error',
                                     'All PEM files must be the same with regards to being averaged and channels being split')
            return

    def merge_pem_files_selection(self):
        pem_files = self.get_selected_pem_files()
        rows = []
        # Find which rows are selected
        for i in self.table.selectedIndexes():
            if i.row() not in rows:
                rows.append(i.row())

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
        print('Table value changed')
        if col == self.columns.index('Coil Area'):
            pem_file = self.pem_files[row]
            old_value = int(pem_file.header.get('CoilArea'))
            new_value = int(self.table.item(row, col).text())
            if int(old_value) != int(new_value):
                self.scale_coil_area(pem_file, int(new_value))
                self.window().statusBar().showMessage(
                    'Coil area changed from {0} to {1}'.format(str(old_value), str(new_value)), 2000)

        if col == self.columns.index('File'):
            pem_file = self.pem_files[row]
            old_path = copy.copy(pem_file.filepath)
            new_value = self.table.item(row, col).text()

            if new_value != os.path.basename(pem_file.filepath):
                if pem_file.old_filepath is None:
                    pem_file.old_filepath = old_path

                new_name = self.table.item(row, col).text()
                new_path = '/'.join(old_path.split('/')[:-1]) + '/' + new_name

                pem_file.filepath = new_path
                self.window().statusBar().showMessage(
                    'File renamed to {}'.format(str(new_name)), 2000)

        pem_file = self.pem_files[row]
        self.check_for_table_changes(pem_file, row)

    def check_for_table_changes(self, pem_file, row):
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
        if filepath is None:
            pem_file.filepath = os.path.join(os.path.split(pem_file.filepath)[0], self.table.item(table_row, 0).text())
        else:
            pem_file.filepath = filepath
        pem_file.header['Date'] = self.table.item(table_row, self.columns.index('Date')).text()
        pem_file.header['Client'] = self.table.item(table_row, self.columns.index('Client')).text()
        pem_file.header['Grid'] = self.table.item(table_row, self.columns.index('Grid')).text()
        pem_file.header['LineHole'] = self.table.item(table_row, self.columns.index('Line/Hole')).text()
        pem_file.header['Loop'] = self.table.item(table_row, self.columns.index('Loop')).text()
        pem_file.tags['Current'] = self.table.item(table_row, self.columns.index('Current')).text()
        pem_file.loop_coords = self.stackedWidget.widget(table_row).get_loop_gps_text()
        pem_file.line_coords = self.stackedWidget.widget(table_row).get_station_gps_text()

        return pem_file

    def save_pem_file(self, pem_file, dir=None):
        if dir is None:
            file_dir = os.path.split(pem_file.filepath)[0]
        else:
            file_dir = dir
        file_name = os.path.splitext(os.path.basename(pem_file.filepath))[0]
        extension = os.path.splitext(pem_file.filepath)[-1]
        overwrite = True
        # tags = []

        if pem_file.is_averaged():
            if '[A]' not in file_name:
                file_name += '[A]'
                overwrite = False
        if pem_file.is_split():
            if '[S]' not in file_name:
                file_name += '[S]'
                overwrite = False
        if pem_file.is_merged:
            if '[M]' in file_name:
                file_name.replace('[M]','')
                file_name += '[M]'
                overwrite = False

        # # Rearranging the tags
        # tags.sort()
        # if '[M]' in tags:
        #     index = tags.index('[M]')
        #     m = tags.pop(index)
        #     tags.append(m)

        # file_name += ''.join(tags)
        pem_file.filepath = os.path.join(file_dir + '/' + file_name + extension)
        save_file = self.serializer.serialize(pem_file)
        print(save_file, file=open(pem_file.filepath, 'w+'))

        if overwrite is True and pem_file.old_filepath:
            os.remove(pem_file.old_filepath)
            pem_file.old_filepath = None

    # Save selected PEM files
    def save_pem_file_selection(self):

        rows = []
        for i in self.table.selectedIndexes():
            if i.row() not in rows:
                rows.append(i.row())

        for row in rows:
            updated_file = self.update_pem_file_from_table(self.pem_files[row], row)
            self.save_pem_file(updated_file)
            self.parent.window().statusBar().showMessage(
                'File {} saved.'.format(os.path.basename(updated_file.filepath)), 2000)
            self.update_table()

    def save_as_pem_file_selection(self):
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
                'Save complete. PEM files saved as {}'.format(os.path.basename(file_path)), 2000)
        else:
            self.window().statusBar().showMessage('No folder selected')

    def remove_file(self, table_row):
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

    # Remove selected files
    def remove_file_selection(self):
        rows = []
        for i in reversed(self.table.selectedIndexes()):
            if i.row() not in rows:
                rows.append(i.row())

        for row in rows:
            self.window().statusBar().showMessage('{0} removed'.format(self.pem_files[row].filepath), 2000)
            self.remove_file(row)

        self.update_table()

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
        self.table.blockSignals(True)
        header = pem_file.header
        tags = pem_file.tags
        file = os.path.basename(pem_file.filepath)
        date = header.get('Date')
        client = self.client_edit.text() if self.share_header_checkbox.isChecked() else header.get('Client')
        grid = self.grid_edit.text() if self.share_header_checkbox.isChecked() else header.get('Grid')
        loop = self.loop_edit.text() if self.share_header_checkbox.isChecked() else header.get('Loop')
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
            item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.table.setItem(row_pos, i, item)

        if self.table.item(row_pos, self.columns.index('Averaged')).text().lower() == 'no':
            self.table.item(row_pos, self.columns.index('Averaged')).setForeground(QtGui.QColor('red'))

        if self.table.item(row_pos, self.columns.index('Split')).text().lower() == 'no':
            self.table.item(row_pos, self.columns.index('Split')).setForeground(QtGui.QColor('red'))

        self.check_for_table_changes(pem_file, row_pos)
        self.table.blockSignals(False)

    # Deletes and re-populates the table rows with the new information
    def update_table(self):
        if len(self.pem_files) > 0:
            while self.table.rowCount() > 0:
                self.table.removeRow(0)
            for pem_file in self.pem_files:
                self.add_to_table(pem_file)
        else:
            pass

    def sort_all_station_gps(self):
        if len(self.pem_files) > 0:
            for i in range(self.stackedWidget.count()):
                widget = self.stackedWidget.widget(i)
                widget.sort_station_gps_button.setChecked(True)
                try:
                    widget.fill_station_table(widget.station_gps.get_sorted_gps())
                except AttributeError:
                    pass
            self.window().statusBar().showMessage('All stations have been sorted', 2000)

    def sort_all_loop_gps(self):
        if len(self.pem_files) > 0:
            for i in range(self.stackedWidget.count()):
                widget = self.stackedWidget.widget(i)
                widget.sort_loop_button.setChecked(True)
                try:
                    widget.fill_loop_table(widget.loop_gps.get_sorted_gps())
                except AttributeError:
                    pass
            self.window().statusBar().showMessage('All loops have been sorted', 2000)

    def fill_share_header(self):
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

        if len(self.pem_files) > 0:
            # all_stations = [file.get_unique_stations() for file in self.pem_files]
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
        selected_widget = self.pem_info_widgets[self.table.currentRow()]
        try:
            selected_widget_loop = selected_widget.get_loop_gps_text()
        except:
            return
        for widget in self.pem_info_widgets:
            widget.fill_loop_table(selected_widget_loop)

    def toggle_share_header(self):
        if self.share_header_checkbox.isChecked():
            self.client_edit.setEnabled(True)
            self.grid_edit.setEnabled(True)
            self.loop_edit.setEnabled(True)
            self.update_table()
        else:
            self.client_edit.setEnabled(False)
            self.grid_edit.setEnabled(False)
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
        if self.sort_loop_button.isChecked():
            widget.fill_loop_table(widget.loop_gps.get_sorted_gps())
        else:
            widget.fill_loop_table(widget.loop_gps.get_gps())

    def toggle_sort_loops(self):
        if len(self.pem_files) > 0:
            for i in range(self.stackedWidget.count()):
                widget = self.stackedWidget.widget(i)
                self.toggle_sort_loop(widget)

    def batch_rename(self, type, selected=False):

        def rename_pem_files():
            if len(self.batch_name_editor.pem_files) > 0:
                self.batch_name_editor.accept_changes()
                if selected is False:
                    for i, pem_file in enumerate(self.batch_name_editor.pem_files):
                        self.pem_files[i] = pem_file
                else:
                    for i, row in enumerate(rows):
                        self.pem_files[row] = self.batch_name_editor.pem_files[i]
                self.update_table()

        if selected is False:
            self.batch_name_editor = BatchNameEditor(self.pem_files, type=type)
        else:
            rows = []
            pem_files = []
            for i in self.table.selectedIndexes():
                if i.row() not in rows:
                    rows.append(i.row())

            for row in rows:
                pem_file = self.pem_files[row]
                pem_files.append(pem_file)

            self.batch_name_editor = BatchNameEditor(pem_files, type=type)

        self.batch_name_editor.buttonBox.accepted.connect(rename_pem_files)
        self.batch_name_editor.acceptChangesSignal.connect(rename_pem_files)
        self.batch_name_editor.buttonBox.rejected.connect(self.batch_name_editor.close)

        self.batch_name_editor.show()


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


if __name__ == '__main__':
    app = QApplication(sys.argv)
    mw = PEMEditorWindow()
    mw.show()
    # sample_files = os.path.join(os.path.dirname(os.path.dirname(application_path)), "sample_files")
    # file_names = [f for f in os.listdir(sample_files) if os.path.isfile(os.path.join(sample_files, f)) and f.lower().endswith('.pem')]
    # file_paths = []
    #
    # for file in file_names:
    #     # file_paths.append(os.path.join(sample_files, file))
    #     mw.editor.open_file(os.path.join(sample_files, file))
    # editor = PEMEditor()
    app.exec_()
