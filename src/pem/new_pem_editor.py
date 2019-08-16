import os
import sys
import logging
import copy
from itertools import chain
from src.pem.pem_serializer import PEMSerializer
from src.pem.pem_parser import PEMParser
from PyQt5.QtWidgets import (QWidget, QMainWindow, QApplication, QGridLayout, QDesktopWidget, QMessageBox, QTabWidget,
                             QFileDialog, QAbstractScrollArea, QTableWidgetItem, QMenuBar, QAction, QMenu, QDockWidget,
                             QHeaderView)
from PyQt5 import (QtCore, QtGui, uic)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s', datefmt='%d-%b-%y %H:%M:%S')

__version__ = '0.1.0'

if getattr(sys, 'frozen', False):
    # If the application is run as a bundle, the pyInstaller bootloader
    # extends the sys module by a flag frozen=True and sets the app
    # path into variable _MEIPASS'.
    application_path = sys._MEIPASS
    editorCreatorFile = 'qt_ui\\pem_editor_widget.ui'
    editorWindowCreatorFile = 'qt_ui\\pem_editor_window.ui'
    icons_path = 'icons'
else:
    application_path = os.path.dirname(os.path.abspath(__file__))
    editorCreatorFile = os.path.join(os.path.dirname(application_path), 'qt_ui\\pem_editor_widget.ui')
    editorWindowCreatorFile = os.path.join(os.path.dirname(application_path), 'qt_ui\\pem_editor_window.ui')
    icons_path = os.path.join(os.path.dirname(application_path), "qt_ui\\icons")

# Load Qt ui file into a class
# editorCreatorFile = os.path.join(os.path.dirname(application_path), 'qt_ui\\pem_editor_widget.ui')
# editorWindowCreatorFile = os.path.join(os.path.dirname(application_path), 'qt_ui\\pem_editor_window.ui')
Ui_PEMEditorWidget, QtBaseClass = uic.loadUiType(editorCreatorFile)
Ui_PEMEditorWindow, QtBaseClass = uic.loadUiType(editorWindowCreatorFile)


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
        # self.setGeometry(500, 300, 1000, 800)
        center_window(self)

    def initApps(self):
        self.message = QMessageBox()
        self.dialog = QFileDialog()

        self.editor = PEMEditor(self)
        self.layout.addWidget(self.editor)
        self.setCentralWidget(self.editor)
        self.dockWidget.hide()
        # self.dockWidget.setWidget(self.tabWidget)
        # self.addDockWidget(QtCore.Qt.RightDockWidgetArea, self.dockWidget)

        self.parser = PEMParser()
        self.serializer = PEMSerializer()

    def initActions(self):
        self.setAcceptDrops(True)
        self.parent.statusBar().showMessage('Ready')

        self.openFile = QAction("&Open...", self)
        self.openFile.setShortcut("Ctrl+O")
        self.openFile.setStatusTip('Open file')
        self.openFile.triggered.connect(self.open_file_dialog)

        self.saveFiles = QAction("&Save Files", self)
        self.saveFiles.setShortcut("Ctrl+S")
        self.saveFiles.setStatusTip("Save all files")
        self.saveFiles.triggered.connect(self.save_all)

        self.saveFilesAs = QAction("&Save Files As...", self)
        self.saveFilesAs.setShortcut("F12")
        self.saveFilesAs.setStatusTip("Save all files as...")
        self.saveFilesAs.triggered.connect(self.save_all_as)

        self.clearFiles = QAction("&Clear Files", self)
        self.clearFiles.setShortcut("Shift+Del")
        self.clearFiles.setStatusTip("Clear all files")
        self.clearFiles.triggered.connect(self.clear_files)

        self.fileMenu = self.menubar.addMenu('&File')
        self.fileMenu.addAction(self.openFile)
        self.fileMenu.addAction(self.saveFiles)
        self.fileMenu.addAction(self.saveFilesAs)
        self.fileMenu.addAction(self.clearFiles)

    def open_file_dialog(self):
        try:
            files = self.dialog.getOpenFileNames(self, 'Open File', filter='PEM files (*.pem);; All files(*.*)')
            if files[0]!='':
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
        urls = [url.toLocalFile() for url in e.mimeData().urls()]

        def check_extension(urls):
            for url in urls:
                if url.lower().endswith('pem'):
                    continue
                else:
                    return False
            return True

        if check_extension(urls):
            e.accept()
        else:
            self.parent.statusBar().showMessage('Invalid file type', 1000)
            e.ignore()

    def dropEvent(self, e):
        try:
            urls = [url.toLocalFile() for url in e.mimeData().urls()]
            self.open_files(urls)
        except Exception as e:
            logging.warning(str(e))
            self.message.information(None, 'Error - Could not open selected PEM files', str(e))
            pass

    def open_files(self, files):
        if not isinstance(files, list) and isinstance(files, str):
            files = [files]
        for file in files:
            try:
                pem_file = self.parser.parse(file)
                self.editor.pem_files.append(pem_file)

                if len(self.editor.pem_files) == 1:  # The initial fill of the header and station info
                    if self.editor.client_edit.text() == '':
                        self.editor.client_edit.setText(self.editor.pem_files[0].header['Client'])
                    if self.editor.grid_edit.text() == '':
                        self.editor.grid_edit.setText(self.editor.pem_files[0].header['Grid'])
                    if self.editor.loop_edit.text() == '':
                        self.editor.loop_edit.setText(self.editor.pem_files[0].header['Loop'])

                    all_stations = [file.get_unique_stations() for file in self.editor.pem_files]

                    if self.editor.min_range_edit.text() == '':
                        min_range = str(min(chain.from_iterable(all_stations)))
                        self.editor.min_range_edit.setText(min_range)
                    if self.editor.max_range_edit.text() == '':
                        max_range = str(max(chain.from_iterable(all_stations)))
                        self.editor.max_range_edit.setText(max_range)

            except Exception as e:
                logging.info(str(e))
                self.message.information(None, 'Error', str(e))

        if len(self.editor.pem_files) > 0:
            # self.parent.statusBar().showMessage('Opened {0} PEM Files'.format(len(files)), 2000)
            self.editor.fill_share_range()
        # self.update_table()

    def clear_files(self):
        while self.editor.table.rowCount() > 0:
            self.editor.table.removeRow(0)
        self.editor.pem_files.clear()
        self.editor.min_range_edit.setText('')
        self.editor.max_range_edit.setText('')
        self.editor.client_edit.setText('')
        self.editor.grid_edit.setText('')
        self.editor.loop_edit.setText('')
        self.parent.statusBar().showMessage('All files removed', 2000)

    def save_all(self):
        if len(self.editor.pem_files) > 0:
            for row in range(self.editor.table.rowCount()):
                file = copy.copy(self.editor.pem_files[row])
                updated_file = self.editor.update_pem_file(self.editor.pem_files[row], row)
                save_file = self.serializer.serialize(updated_file)
                self.parent.statusBar().showMessage('Save complete. {0} PEM files saved'.format(len(self.editor.pem_files)), 2000)
                print(save_file, file=open(updated_file.filepath, 'w+'))
                if os.path.basename(file.filepath) != os.path.basename(updated_file.filepath):
                    os.remove(file.filepath)
            self.editor.update_table()
        else:
            self.parent.statusBar().showMessage('No PEM files to save', 2000)

    def save_all_as(self):
        if len(self.editor.pem_files) > 0:
            default_path = os.path.split(self.editor.pem_files[-1].filepath)[0]
            self.dialog.setFileMode(QFileDialog.Directory)
            self.dialog.setDirectory(default_path)
            self.parent.statusBar().showMessage('Saving PEM files...')
            file_dir = QFileDialog.getExistingDirectory(self, '', default_path)
            suffix = 'Av'
            if file_dir:
                for row in range(self.editor.table.rowCount()):
                    pem_file = self.editor.pem_files[row]
                    updated_file = self.editor.update_pem_file(self.editor.pem_files[row], row)
                    file_name = os.path.splitext(os.path.basename(pem_file.filepath))[0]
                    extension = os.path.splitext(pem_file.filepath)[-1]
                    updated_file.filepath = os.path.join(file_dir, file_name + suffix + extension)
                    save_file = self.serializer.serialize(updated_file)

                    print(save_file, file=open(updated_file.filepath, 'w+'))
                    self.parent.statusBar().showMessage('Save complete. {0} PEM files saved'.format(len(self.editor.pem_files)), 2000)
                self.editor.update_table()
            else:
                self.parent.statusBar().showMessage('No directory chosen', 2000)
                logging.info("No directory chosen, aborted save")
                pass


class PEMEditor(QWidget, Ui_PEMEditorWidget):
    def __init__(self, parent):
        super(PEMEditor, self).__init__(parent)
        self.setupUi(self)

        self.parent = parent
        self.message = QMessageBox()
        self.pem_files = []
        self.create_table()
        self.table.viewport().installEventFilter(self)

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

    # Creates the right-click context menu on the table
    def contextMenuEvent(self, event):
        if self.table.underMouse():
            if self.table.selectionModel().selectedIndexes():
                self.table.menu = QMenu(self.table)
                self.table.remove_file_action = QAction("&Remove", self)
                self.table.remove_file_action.triggered.connect(self.remove_file)

                self.table.save_file_file_action = QAction("&Save", self)
                self.table.save_file_file_action.triggered.connect(self.save_file)

                self.table.menu.addAction(self.table.save_file_file_action)
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
        return super(QWidget, self).eventFilter(source, event)

    # Remove a single file
    def remove_file(self):
        row = self.table.currentRow()
        if row != -1:
            self.table.removeRow(row)
            self.parent.window().statusBar().showMessage('{0} removed'.format(self.pem_files[row].filepath), 2000)
            del self.pem_files[row]
            self.update_table()
        else:
            pass

    def update_pem_file(self, pem_file, table_row):
        updated_file = None
        pem_file.filepath = os.path.join(os.path.split(pem_file.filepath)[0], self.table.item(table_row, 0).text())
        pem_file.header['Client'] = self.table.item(table_row, 1).text()
        pem_file.header['Grid'] = self.table.item(table_row, 2).text()
        pem_file.header['LineHole'] = self.table.item(table_row, 3).text()
        pem_file.header['Loop'] = self.table.item(table_row, 4).text()
        pem_file.tags['Current'] = self.table.item(table_row, 5).text()
        return pem_file

    def save_file(self):
        row = self.table.currentRow()

        if row != -1 and len(self.pem_files) > 0:
            file = copy.copy(self.pem_files[row])
            updated_file = self.update_pem_file(self.pem_files[row], row)
            save_file = self.parent.serializer.serialize(updated_file)
            self.parent.window().statusBar().showMessage(
                'File {} saved.'.format(os.path.basename(updated_file.filepath)), 2000)
            print(save_file, file=open(updated_file.filepath, 'w+'))
            self.update_table()

            if os.path.basename(file.filepath) != os.path.basename(updated_file.filepath):
                os.remove(file.filepath)
        else:
            pass

    # Creates the table when the editor is first opened
    def create_table(self):
        self.columns = ['File', 'Client', 'Grid', 'Line/Hole', 'Loop', 'Current', 'First Station', 'Last Station']
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

        line = header.get('LineHole')
        start_stn = self.min_range_edit.text() if self.share_range_checkbox.isChecked() else str(
            min(pem_file.get_unique_stations()))
        end_stn = self.max_range_edit.text() if self.share_range_checkbox.isChecked() else str(
            max(pem_file.get_unique_stations()))

        new_row = [file, client, grid, line, loop, current, start_stn, end_stn]

        row_pos = self.table.rowCount()
        self.table.insertRow(row_pos)

        for i, column in enumerate(self.columns):
            self.table.setItem(row_pos, i, QTableWidgetItem(new_row[i]))

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
            str(min(pem_file.get_unique_stations())),
            str(max(pem_file.get_unique_stations()))
        ]
        for column in range(self.table.columnCount()):
            if self.table.item(row_pos, column).text() != pem_file_info_list[column]:
                self.table.item(row_pos, column).setFont(boldFont)
        #
        # if self.table.item(row_pos, 3).text() != self.table.item(row_pos, 4).text():
        #     for column in range (3, 5):
        #         self.table.item(row_pos, column).setForeground(QtGui.QColor('red'))

    # Deletes and re-creates the table with the new information
    def update_table(self):
        # self.update_header()
        if len(self.pem_files) > 0:
            while self.table.rowCount() > 0:
                self.table.removeRow(0)
            for pem_file in self.pem_files:
                self.add_to_table(pem_file)
        else:
            pass

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
