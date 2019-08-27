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
                             QInputDialog, QHeaderView)

from src.gps.loop_gps import LoopGPSParser
from src.gps.station_gps import StationGPSParser
from src.pem.pem_file_editor import PEMFileEditor
from src.pem.pem_parser import PEMParser
from src.pem.pem_serializer import PEMSerializer
from src.qt_py.pem_info_widget import PEMFileInfoWidget

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s', datefmt='%d-%b-%y %H:%M:%S')

__version__ = '0.1.0'

_station_gps_tab = 1
_loop_gps_tab = 2
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
# editorCreatorFile = os.path.join(os.path.dirname(application_path), 'qt_ui\\pem_editor_widget.ui')
# editorWindowCreatorFile = os.path.join(os.path.dirname(application_path), 'qt_ui\\pem_editor_window.ui')
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
    def __init__(self, parent=None):
        super().__init__()
        self.parent = parent
        self.initUi()
        self.initApps()
        self.initActions()

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
        self.setGeometry(500, 300, 1000, 800)
        center_window(self)

    def initApps(self):
        self.message = QMessageBox()
        self.dialog = QFileDialog()

        self.editor = PEMEditorWidget(self)
        self.layout.addWidget(self.editor)
        self.setCentralWidget(self.editor)

        self.dockWidget.hide()
        # self.dockWidget.setWidget(self.tabWidget)
        # self.addDockWidget(QtCore.Qt.RightDockWidgetArea, self.dockWidget)

        self.parser = PEMParser()
        self.serializer = PEMSerializer()

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
        self.averageAllPems.setShortcut("Ctrl + Shift + A")
        self.averageAllPems.triggered.connect(self.editor.average_all_pem_files)

        self.splitAllPems = QAction("&Split All PEM Files", self)
        self.splitAllPems.setStatusTip("Split all PEM files")
        self.splitAllPems.setShortcut("Ctrl + Shift + S")
        self.splitAllPems.triggered.connect(self.editor.split_all_pem_files)

        self.coilAreaAllPems = QAction("&Change All Coil Areas", self)
        self.coilAreaAllPems.setStatusTip("Change all coil areas to the same value")
        self.coilAreaAllPems.triggered.connect(self.editor.scale_all_coil_area)

        self.editLineNames = QAction("&Bulk Rename Lines/Holes", self)
        self.editLineNames.setStatusTip("Rename all line/hole names")
        self.editLineNames.setShortcut("F2")
        self.editLineNames.triggered.connect(self.editor.edit_linenames)

        self.editFileNames = QAction("&Bulk Rename Files", self)
        self.editFileNames.setStatusTip("Rename all file names")
        self.editFileNames.setShortcut("F3")
        self.editFileNames.triggered.connect(self.editor.edit_filenames)

        self.sortAllStationGps = QAction("&Sort All Station GPS", self)
        self.sortAllStationGps.setStatusTip("Sort the station GPS for every file")
        self.sortAllStationGps.triggered.connect(self.editor.sort_all_station_gps)

        self.sortAllLoopGps = QAction("&Sort All Loop GPS", self)
        self.sortAllLoopGps.setStatusTip("Sort the loop GPS for every file")
        self.sortAllLoopGps.triggered.connect(self.editor.sort_all_loop_gps)

        self.PEMMenu = self.menubar.addMenu('&PEM')
        self.PEMMenu.addAction(self.averageAllPems)
        self.PEMMenu.addAction(self.splitAllPems)
        self.PEMMenu.addAction(self.coilAreaAllPems)
        self.PEMMenu.addAction(self.editLineNames)
        self.PEMMenu.addAction(self.editFileNames)

        self.GPSMenu = self.menubar.addMenu('&GPS')
        self.GPSMenu.addAction(self.sortAllStationGps)
        self.GPSMenu.addAction(self.sortAllLoopGps)

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
            self.message.information(None, 'Error', str(e))
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
            bool(e.answerRect().intersects(self.editor.table.geometry())),
            pem_files,
        ]))

        if len(self.editor.pem_files) == 0:
            if pem_conditions is True:
                e.acceptProposedAction()
            else:
                e.ignore()

        else:
            eligible_tabs = [_station_gps_tab, _loop_gps_tab]

            gps_conditions = bool(all([
                e.answerRect().intersects(self.editor.stackedWidget.geometry()),
                text_files,
                # len(urls) == 1,
                self.editor.stackedWidget.currentWidget().tabs.currentIndex() in eligible_tabs,
                self.editor.share_loop_gps_checkbox.isChecked() is True and
                self.editor.stackedWidget.currentWidget().tabs.currentIndex() is not _loop_gps_tab or
                len(self.editor.pem_files) == 1,
                len(self.editor.pem_files) > 0
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
            self.editor.open_pem_files(pem_files)

        if len(gps_files) > 0:
            self.editor.open_gps_files(gps_files)

    def clear_files(self):
        while self.editor.table.rowCount() > 0:
            self.editor.table.removeRow(0)
        for i in reversed(range(self.editor.stackedWidget.count())):
            widget = self.editor.stackedWidget.widget(i)
            self.editor.stackedWidget.removeWidget(widget)
        self.editor.pem_files.clear()
        self.editor.min_range_edit.setText('')
        self.editor.max_range_edit.setText('')
        self.editor.client_edit.setText('')
        self.editor.grid_edit.setText('')
        self.editor.loop_edit.setText('')
        self.window().statusBar().showMessage('All files removed', 2000)

    def save_all(self):
        if len(self.editor.pem_files) > 0:
            for row in range(self.editor.table.rowCount()):
                updated_file = self.editor.update_pem_file_from_table(self.editor.pem_files[row], row)
                self.editor.save_pem_file(updated_file)
                self.window().statusBar().showMessage(
                    'Save complete. {0} PEM files saved'.format(len(self.editor.pem_files)), 2000)
            self.editor.update_table()
        else:
            self.window().statusBar().showMessage('No PEM files to save', 2000)

    def save_all_to(self):

        # def find_suffix()

        if len(self.editor.pem_files) > 0:
            default_path = os.path.split(self.editor.pem_files[-1].filepath)[0]
            # self.dialog.setFileMode(QFileDialog.ExistingFiles)
            # self.dialog.setOption(QFileDialog.ShowDirsOnly, on=False)
            self.dialog.setNameFilter('PEM Files (*.PEM)')
            self.dialog.setAcceptMode(QFileDialog.AcceptSave)
            self.dialog.setDirectory(default_path)
            self.window().statusBar().showMessage('Saving PEM files...')
            file_dir = QFileDialog.getExistingDirectory(self, '', default_path, QFileDialog.DontUseNativeDialog)

            if file_dir:
                for row in range(self.editor.table.rowCount()):
                    pem_file = self.editor.pem_files[row]
                    updated_file = self.editor.update_pem_file_from_table(self.editor.pem_files[row], row)
                    file_name = os.path.splitext(os.path.basename(pem_file.filepath))[0]
                    extension = os.path.splitext(pem_file.filepath)[-1]
                    updated_file.filepath = os.path.join(file_dir, file_name + extension)

                    self.editor.save_pem_file(updated_file)
                    self.window().statusBar().showMessage(
                        'Save complete. {0} PEM files saved'.format(len(self.editor.pem_files)), 2000)
                self.editor.update_table()
            else:
                self.window().statusBar().showMessage('No directory chosen', 2000)
                logging.info("No directory chosen, aborted save")
                pass


class PEMEditorWidget(QWidget, Ui_PEMEditorWidget):
    def __init__(self, parent):
        super(PEMEditorWidget, self).__init__(parent)
        self.parent = parent

        self.setupUi(self)
        self.initActions()
        self.initApps()

        self.pem_files = []
        self.gps_files = []
        self.pem_info_widgets = []

        self.create_table()

    def initApps(self):
        self.parser = PEMParser()
        self.file_editor = PEMFileEditor()
        self.message = QMessageBox()
        self.pem_info_widget = PEMFileInfoWidget
        self.station_gps_parser = StationGPSParser()
        self.serializer = PEMSerializer()

        self.stackedWidget.hide()

    def initActions(self):
        self.table.viewport().installEventFilter(self)
        self.table.itemSelectionChanged.connect(self.display_pem_info_widget)
        self.table.itemChanged.connect(self.table_value_changed)

        self.share_loop_gps_checkbox.toggled.connect(self.toggle_share_loop)
        self.sort_loop_button.toggled.connect(self.toggle_sort_loops)

        self.del_file = QAction("&Remove File", self)
        self.del_file.setShortcut("Del")
        self.del_file.triggered.connect(self.remove_file)
        self.addAction(self.del_file)

        self.share_header_checkbox.stateChanged.connect(self.toggle_share_header)
        self.reset_header_btn.clicked.connect(self.fill_share_header)
        self.client_edit.returnPressed.connect(self.update_table)
        self.grid_edit.returnPressed.connect(self.update_table)
        self.loop_edit.returnPressed.connect(self.update_table)

        self.share_range_checkbox.stateChanged.connect(self.toggle_share_range)
        self.reset_range_btn.clicked.connect(self.fill_share_range)
        self.min_range_edit.returnPressed.connect(self.update_table)
        self.max_range_edit.returnPressed.connect(self.update_table)

    def open_pem_files(self, pem_files):
        self.stackedWidget.show()
        for file in pem_files:
            try:
                pem_file = self.parser.parse(file)
                pem_info_widget = self.pem_info_widget(pem_file, parent=self)
                self.pem_files.append(pem_file)
                self.pem_info_widgets.append(pem_info_widget)
                self.stackedWidget.addWidget(pem_info_widget)

                if len(self.pem_files) == 1:  # The initial fill of the header and station info
                    if self.client_edit.text() == '':
                        self.client_edit.setText(self.pem_files[0].header['Client'])
                    if self.grid_edit.text() == '':
                        self.grid_edit.setText(self.pem_files[0].header['Grid'])
                    if self.loop_edit.text() == '':
                        self.loop_edit.setText(self.pem_files[0].header['Loop'])

                    all_stations = [file.get_unique_stations() for file in self.pem_files]

                    if self.min_range_edit.text() == '':
                        min_range = str(min(chain.from_iterable(all_stations)))
                        self.min_range_edit.setText(min_range)
                    if self.max_range_edit.text() == '':
                        max_range = str(max(chain.from_iterable(all_stations)))
                        self.max_range_edit.setText(max_range)

            except Exception as e:
                logging.info(str(e))
                self.message.information(None, 'Error', str(e))

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
                    gps_file = station_gps_parser.parse_text(file)
                    pem_info_widget.station_gps = gps_file

                    if station_gps_tab.findChild(QToolButton, 'sort_stations_button').isChecked():
                        gps_data = '\n'.join(gps_file.get_sorted_gps())
                    else:
                        gps_data = '\n'.join(gps_file.get_gps())
                    station_gps_tab.findChild(QTextEdit, 'station_gps_text').setPlainText(gps_data)

                elif loop_gps_tab == current_tab:
                    gps_file = loop_gps_parser.parse_text(file)
                    pem_info_widget.loop_gps = gps_file

                    if self.share_loop_gps_checkbox.isChecked():
                        if len(self.pem_files) == 1:
                            if self.sort_loop_button.isChecked():
                                gps_data = '\n'.join(gps_file.get_sorted_gps())
                            else:
                                gps_data = '\n'.join(gps_file.get_gps())
                        else:
                            gps_data = self.stackedWidget.widget(0).tabs.widget(_loop_gps_tab).findChild \
                                (QTextEdit, 'loop_gps_text').toPlainText()
                            pem_info_widget.sort_loop_button.setEnabled(False)
                    else:
                        if loop_gps_tab.findChild(QToolButton, 'sort_loop_button').isChecked():
                            gps_data = '\n'.join(gps_file.get_sorted_gps())
                        else:
                            gps_data = '\n'.join(gps_file.get_gps())
                    loop_gps_tab.findChild(QTextEdit, 'loop_gps_text').setPlainText(gps_data)
                else:
                    pass

            except Exception as e:
                logging.info(str(e))
                self.message.information(None, 'Error', str(e))
                pass
        else:
            self.message.information(None, 'Too many files', 'Only one GPS file can be opened at once')
            pass

    # Creates the right-click context menu on the table
    def contextMenuEvent(self, event):
        if self.table.underMouse():
            if self.table.selectionModel().selectedIndexes():
                self.table.menu = QMenu(self.table)
                self.table.remove_file_action = QAction("&Remove", self)
                self.table.remove_file_action.triggered.connect(self.remove_file)

                self.table.save_file_file_action = QAction("&Save", self)
                self.table.save_file_file_action.triggered.connect(self.save_pem_file_selection)

                self.table.average_action = QAction("&Average", self)
                self.table.average_action.triggered.connect(self.average_select_pem)

                self.table.split_action = QAction("&Split", self)
                self.table.split_action.triggered.connect(self.split_select_pem)

                self.table.scale_ca_action = QAction("&Coil Area", self)
                self.table.scale_ca_action.triggered.connect(self.scale_coil_area_selection)

                self.table.menu.addAction(self.table.save_file_file_action)
                self.table.menu.addSeparator()
                self.table.menu.addAction(self.table.average_action)
                self.table.menu.addAction(self.table.split_action)
                self.table.menu.addAction(self.table.scale_ca_action)
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
            # self.stackedWidget.hide()
        return super(QWidget, self).eventFilter(source, event)

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
            rows = []
            for i in self.table.selectedIndexes():
                if i.row() not in rows:
                    rows.append(i.row())

            for row in rows:
                pem_file = self.pem_files[row]
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
            rows = []
            for i in self.table.selectedIndexes():
                if i.row() not in rows:
                    rows.append(i.row())

            for row in rows:
                pem_file = self.pem_files[row]
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

    def table_value_changed(self, e):
        if e.column() == self.columns.index('Coil Area'):
            pem_file = self.pem_files[e.row()]
            old_value = int(pem_file.header.get('CoilArea'))
            new_value = int(self.table.item(e.row(), e.column()).text())
            if int(old_value) != int(new_value):
                self.scale_coil_area(pem_file, int(new_value))
                self.window().statusBar().showMessage(
                    'Coil area changed from {0} to {1}'.format(str(old_value), str(new_value)), 2000)

        if e.column() == self.columns.index('File'):
            pem_file = self.pem_files[e.row()]
            old_path = copy.copy(pem_file.filepath)
            new_value = self.table.item(e.row(), e.column()).text()

            if new_value != os.path.basename(pem_file.filepath):
                if pem_file.old_filepath is None:
                    pem_file.old_filepath = old_path

                new_name = self.table.item(e.row(), e.column()).text()
                new_path = '/'.join(old_path.split('/')[:-1]) + '/' + new_name

                pem_file.filepath = new_path
                self.window().statusBar().showMessage(
                    'File renamed to {}'.format(str(new_name)), 2000)

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

    # Saves the pem file in memory using the information in the table
    def update_pem_file_from_table(self, pem_file, table_row):
        pem_file.filepath = os.path.join(os.path.split(pem_file.filepath)[0], self.table.item(table_row, 0).text())
        pem_file.header['Client'] = self.table.item(table_row, 1).text()
        pem_file.header['Grid'] = self.table.item(table_row, 2).text()
        pem_file.header['LineHole'] = self.table.item(table_row, 3).text()
        pem_file.header['Loop'] = self.table.item(table_row, 4).text()
        pem_file.tags['Current'] = self.table.item(table_row, 5).text()
        pem_file.loop_coords = self.stackedWidget.widget(table_row).tabs.findChild(QTextEdit,
                                                                                   'loop_gps_text').toPlainText()
        pem_file.line_coords = self.stackedWidget.widget(table_row).tabs.findChild(QTextEdit,
                                                                                   'station_gps_text').toPlainText()
        return pem_file

    def save_pem_file(self, pem_file):
        file_dir = os.path.split(pem_file.filepath)[0]
        file_name = os.path.splitext(os.path.basename(pem_file.filepath))[0]
        extension = os.path.splitext(pem_file.filepath)[-1]
        overwrite = True

        if pem_file.unaveraged_data:
            # Means the data has been averaged, therefore append '[A]'
            if '[A]' not in file_name:
                file_name += '[A]'
                overwrite = False
        if pem_file.unsplit_data:
            if '[S]' not in file_name:
                file_name += '[S]'
                overwrite = False

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

    # Remove selected files
    def remove_file(self):
        rows = []
        for i in reversed(self.table.selectedIndexes()):
            if i.row() not in rows:
                rows.append(i.row())

        for row in rows:
            self.table.removeRow(row)
            self.stackedWidget.removeWidget(self.stackedWidget.widget(row))
            self.window().statusBar().showMessage('{0} removed'.format(self.pem_files[row].filepath), 2000)
            del self.pem_files[row]
            if len(self.pem_files) == 0:
                self.stackedWidget.hide()
                self.client_edit.setText('')
                self.grid_edit.setText('')
                self.loop_edit.setText('')
                self.min_range_edit.setText('')
                self.max_range_edit.setText('')
        self.update_table()

    # Creates the table when the editor is first opened
    def create_table(self):
        self.columns = ['File', 'Client', 'Grid', 'Line/Hole', 'Loop', 'Current', 'Coil Area', 'First Station',
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

        header = pem_file.header
        tags = pem_file.tags
        file = os.path.basename(pem_file.filepath)
        client = self.client_edit.text() if self.share_header_checkbox.isChecked() else header.get('Client')
        grid = self.grid_edit.text() if self.share_header_checkbox.isChecked() else header.get('Grid')
        loop = self.loop_edit.text() if self.share_header_checkbox.isChecked() else header.get('Loop')
        current = tags.get('Current')
        coil_area = pem_file.header.get('CoilArea')
        averaged = 'Yes' if pem_file.is_averaged() else 'No'
        split = 'Yes' if pem_file.is_split() else 'No'
        line = header.get('LineHole')
        start_stn = self.min_range_edit.text() if self.share_range_checkbox.isChecked() else str(
            min(pem_file.get_unique_stations()))
        end_stn = self.max_range_edit.text() if self.share_range_checkbox.isChecked() else str(
            max(pem_file.get_unique_stations()))

        new_row = [file, client, grid, line, loop, current, coil_area, start_stn, end_stn, averaged, split]

        row_pos = self.table.rowCount()
        self.table.insertRow(row_pos)

        for i, column in enumerate(self.columns):
            item = QTableWidgetItem(new_row[i])
            item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.table.setItem(row_pos, i, item)

        self.table.resizeColumnsToContents()

        boldFont = QtGui.QFont()
        boldFont.setBold(True)
        # Only used for table comparisons. Makes bold entries that have changed
        pem_file_info_list = [
            file,
            header.get('Client'),
            header.get('Grid'),
            header.get('LineHole'),
            header.get('Loop'),
            tags.get('Current'),
            header.get('CoilArea'),
            str(min(pem_file.get_unique_stations())),
            str(max(pem_file.get_unique_stations())),
            str(averaged),
            str(split)
        ]
        for column in range(self.table.columnCount()):
            if self.table.item(row_pos, column).text() != pem_file_info_list[column]:
                self.table.item(row_pos, column).setFont(boldFont)

        if self.table.item(row_pos, self.columns.index('Averaged')).text().lower() == 'no':
            self.table.item(row_pos, self.columns.index('Averaged')).setForeground(QtGui.QColor('red'))

        if self.table.item(row_pos, self.columns.index('Split')).text().lower() == 'no':
            self.table.item(row_pos, self.columns.index('Split')).setForeground(QtGui.QColor('red'))
        #
        # if self.table.item(row_pos, 3).text() != self.table.item(row_pos, 4).text():
        #     for column in range (3, 5):
        #         self.table.item(row_pos, column).setForeground(QtGui.QColor('red'))

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
                widget.sort_stations_button.setChecked(True)
                widget_station_text = widget.tabs.widget(_station_gps_tab).findChild(QTextEdit, 'station_gps_text')
                widget_station_text.setPlainText('\n'.join(self.stackedWidget.widget(i).station_gps.get_sorted_gps()))
            self.window().statusBar().showMessage('All stations have been sorted', 2000)

    def sort_all_loop_gps(self):
        if len(self.pem_files) > 0:
            if self.share_loop_gps_checkbox.isChecked() is False:
                self.toggle_sort_loops()
            else:
                for i in range(self.stackedWidget.count()):
                    widget = self.stackedWidget.widget(i)
                    widget.sort_loop_button.setChecked(True)
                    widget_loop_text = widget.tabs.widget(_loop_gps_tab).findChild(QTextEdit, 'loop_gps_text')
                    widget_loop_text.setPlainText('\n'.join(self.stackedWidget.widget(0).loop_gps.get_sorted_gps()))
                self.sort_loop_button.setChecked(True)
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
            all_stations = [file.get_unique_stations() for file in self.pem_files]
            min_range, max_range = str(min(chain.from_iterable(all_stations))), str(
                max(chain.from_iterable(all_stations)))
            self.min_range_edit.setText(min_range)
            self.max_range_edit.setText(max_range)
            self.update_table()
        else:
            self.min_range_edit.setText('')
            self.max_range_edit.setText('')

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

    def toggle_share_loop(self):
        if self.share_loop_gps_checkbox.isChecked():
            self.sort_loop_button.setEnabled(True)
            if len(self.pem_files) > 0:
                first_widget = self.stackedWidget.widget(0)
                if first_widget.loop_gps:
                    if self.sort_loop_button.isChecked():
                        loop = '\n'.join(first_widget.loop_gps.get_sorted_gps())
                    else:
                        loop = '\n'.join(first_widget.loop_gps.get_gps())
                else:
                    loop = ''
                for i in range(self.stackedWidget.count()):
                    widget = self.stackedWidget.widget(i)
                    widget.sort_loop_button.setEnabled(False)
                    widget.format_loop_gps_button.setEnabled(False)
                    if i != 0:
                        widget_loop_text = widget.tabs.widget(_loop_gps_tab).findChild(QTextEdit, 'loop_gps_text')
                        widget_loop_text.setPlainText(loop)
        else:
            self.sort_loop_button.setEnabled(False)
            if len(self.pem_files) > 0:
                for i in range(self.stackedWidget.count()):
                    widget = self.stackedWidget.widget(i)
                    widget_loop_text = widget.tabs.widget(_loop_gps_tab).findChild(QTextEdit, 'loop_gps_text')
                    widget.sort_loop_button.setEnabled(True)
                    widget.format_loop_gps_button.setEnabled(True)
                    if widget.loop_gps:
                        if widget.sort_loop_button.isChecked():
                            widget_loop_text.setPlainText('\n'.join(widget.loop_gps.get_sorted_gps()))
                        else:
                            widget_loop_text.setPlainText('\n'.join(widget.loop_gps.get_gps()))
                    else:
                        widget_loop_text.setPlainText('')

    def toggle_sort_loop(self, widget):
        widget_loop_text = widget.tabs.widget(_loop_gps_tab).findChild(QTextEdit, 'loop_gps_text')
        if self.sort_loop_button.isChecked():
            widget_loop_text.setPlainText('\n'.join(self.stackedWidget.widget(0).loop_gps.get_sorted_gps()))
        else:
            widget_loop_text.setPlainText('\n'.join(self.stackedWidget.widget(0).loop_gps.get_gps()))

    def toggle_sort_loops(self):
        if len(self.pem_files) > 0:
            for i in range(self.stackedWidget.count()):
                widget = self.stackedWidget.widget(i)
                self.toggle_sort_loop(widget)

    def edit_linenames(self):

        def rename_pem_files():
            if len(self.linename_editor.pem_files) > 0:
                self.linename_editor.accept_changes()
                for i, pem_file in enumerate(self.linename_editor.pem_files):
                    self.pem_files[i].header['LineHole'] = pem_file
                self.update_table()

        self.linename_editor = LineNameEditor(self.pem_files, field='Line name')
        self.linename_editor.buttonBox.accepted.connect(rename_pem_files)
        self.linename_editor.acceptChangesSignal.connect(rename_pem_files)
        self.linename_editor.buttonBox.rejected.connect(self.linename_editor.close)

        self.linename_editor.show()

    def edit_filenames(self):

        def rename_pem_files():
            if len(self.linename_editor.pem_files) > 0:
                self.linename_editor.accept_changes()
                for i, pem_file in enumerate(self.linename_editor.pem_files):
                    self.pem_files[i] = pem_file
                self.update_table()

        self.linename_editor = LineNameEditor(self.pem_files, field='File name')
        self.linename_editor.acceptChangesSignal.connect(rename_pem_files)
        self.linename_editor.buttonBox.rejected.connect(self.linename_editor.close)

        self.linename_editor.show()


class LineNameEditor(QWidget, Ui_LineNameEditorWidget):
    """
    Class to bulk rename PEM File line/hole names or file names.
    """
    acceptChangesSignal = QtCore.pyqtSignal()

    def __init__(self, pem_files, field=None, parent=None):
        super().__init__()
        self.parent = parent
        self.setupUi(self)
        self.pem_files = pem_files
        self.field = field

        if self.field == 'Line name':
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

        if self.field == 'Line name':
            item = QTableWidgetItem(pem_file.header.get('LineHole'))
            item2 = QTableWidgetItem(pem_file.header.get('LineHole'))
        elif self.field == 'File name':
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
            if self.field == 'Line name':
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
                output = prefix+input+suffix+ext

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
                if self.field == 'Line name':
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
