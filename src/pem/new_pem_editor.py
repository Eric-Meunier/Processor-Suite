import os
import sys
import logging
from itertools import chain
from src.pem.pem_serializer import PEMSerializer
from src.pem.pem_parser import PEMParser
from PyQt5.QtWidgets import (QWidget, QMainWindow, QApplication, QGridLayout, QDesktopWidget, QMessageBox,
                             QFileDialog, QAbstractScrollArea, QTableWidgetItem, QMenuBar, QAction, QMenu)
from PyQt5 import (QtCore, QtGui, uic)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s', datefmt='%d-%b-%y %H:%M:%S')

__version__ = '0.1.0'

if getattr(sys, 'frozen', False):
    # If the application is run as a bundle, the pyInstaller bootloader
    # extends the sys module by a flag frozen=True and sets the app
    # path into variable _MEIPASS'.
    application_path = sys._MEIPASS
else:
    application_path = os.path.dirname(os.path.abspath(__file__))

# Load Qt ui file into a class
editorCreatorFile = os.path.join(os.path.dirname(application_path), 'qt_ui\\pem_editor_widget.ui')
Ui_PEMEditorWidget, QtBaseClass = uic.loadUiType(editorCreatorFile)

# TODO Added filepath to pemparser, will need to go and fix broken code as a result


class PEMEditorWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUi()
        self.initApps()
        self.initActions()

    def initUi(self):
        def center_window(self):
            qtRectangle = self.frameGeometry()
            centerPoint = QDesktopWidget().availableGeometry().center()
            qtRectangle.moveCenter(centerPoint)
            self.move(qtRectangle.topLeft())

        layout = QGridLayout(self)
        self.setLayout(layout)
        self.setAcceptDrops(True)
        self.setWindowTitle("PEMEditor  v" + str(__version__))
        self.setWindowIcon(
            QtGui.QIcon(os.path.join(os.path.dirname(application_path), "qt_ui\\icons\\crone_logo.ico")))
        self.setGeometry(500, 300, 1000, 800)
        center_window(self)

    def initApps(self):
        self.message = QMessageBox()
        self.dialog = QFileDialog()

        self.editor = PEMEditor(self)
        self.parser = PEMParser()
        self.serializer = PEMSerializer()
        self.layout().addWidget(self.editor)
        self.setCentralWidget(self.editor)

    def initActions(self):
        self.statusBar().showMessage('Ready')
        self.mainMenu = self.menuBar()

        self.openFile = QAction("&Open File", self)
        self.openFile.setShortcut("Ctrl+O")
        self.openFile.setStatusTip('Open file')
        self.openFile.triggered.connect(self.open_file_dialog)

        self.saveFiles = QAction("&Save Files", self)
        self.saveFiles.setShortcut("Ctrl+S")
        self.saveFiles.setStatusTip("Save all files")
        self.saveFiles.triggered.connect(self.save_all)

        self.clearFiles = QAction("&Clear Files", self)
        self.clearFiles.setShortcut("Ctrl+Del")
        self.clearFiles.setStatusTip("Clear all files")
        self.clearFiles.triggered.connect(self.clear_files)

        self.fileMenu = self.mainMenu.addMenu('&File')
        self.fileMenu.addAction(self.openFile)
        self.fileMenu.addAction(self.saveFiles)
        self.fileMenu.addAction(self.clearFiles)

    def open_file_dialog(self):
        try:
            file = self.dialog.getOpenFileName(self, 'Open File')
            if file[0].lower().endswith('.pem'):
                self.open_files(file[0])
                # self.setFixedSize(self.layout.sizeHint())
            else:
                self.message.information(None, 'Error', 'Invalid File Format')
                return
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
            e.ignore()

    def dropEvent(self, e):
        try:
            urls = [url.toLocalFile() for url in e.mimeData().urls()]
            self.open_files(urls)
            # #Resize the window
            # if self.gridLayout.sizeHint().height()+25>self.size().height():
            #     self.resize(self.gridLayout.sizeHint().width()+25, self.gridLayout.sizeHint().height()+25)
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
            self.statusBar().showMessage('Opened {0} PEM Files'.format(len(files)), 2000)
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

    def save_all(self):
        if len(self.editor.pem_files) > 0:
            for row in range(self.editor.table.rowCount()):
                self.editor.pem_files[row].header['Client'] = self.editor.table.item(row, 1).text()
                self.editor.pem_files[row].header['Grid'] = self.editor.table.item(row, 2).text()
                self.editor.pem_files[row].header['LineHole'] = self.editor.table.item(row, 3).text()
                self.editor.pem_files[row].header['Loop'] = self.editor.table.item(row, 4).text()
            for pem_file in self.editor.pem_files:
                save_file = self.serializer.serialize(pem_file)
                print(save_file)
                self.statusBar().showMessage('{0} PEM files saved'.format(len(self.editor.pem_files)), 2000)
                # save_name = os.path.splitext(pem_file.filepath)
                # print(save_file, file=open(pem_file.filepath, 'w+'))
            self.editor.update_table()

# class MainWindow(QMainWindow):
#     def __init__(self):
#         super().__init__()
#         self.initUi()
#         layout = QGridLayout(self)
#         self.setLayout(layout)
#         self.editor = PEMEditor(self)
#         self.message = QMessageBox()
#         self.layout().addWidget(self.editor)
#         self.setCentralWidget(self.editor)
#
#         self.mainMenu = self.menuBar()
#
#         self.openFile = QAction("&Open File", self)
#         self.openFile.setShortcut("Ctrl+O")
#         self.openFile.setStatusTip('Open file')
#         self.openFile.triggered.connect(self.open_file_dialog)
#
#         self.saveFiles = QAction("&Save Files", self)
#         self.saveFiles.setShortcut("Ctrl+S")
#         self.saveFiles.setStatusTip("Save all files")
#         self.saveFiles.triggered.connect(self.editor.save_all)
#
#         self.clearFiles = QAction("&Clear Files", self)
#         self.clearFiles.setShortcut("Ctrl+Del")
#         self.clearFiles.setStatusTip("Clear all files")
#         self.clearFiles.triggered.connect(self.editor.clear_files)
#
#         self.fileMenu = self.mainMenu.addMenu('&File')
#         self.fileMenu.addAction(self.openFile)
#         self.fileMenu.addAction(self.saveFiles)
#         self.fileMenu.addAction(self.clearFiles)
#
#     def initUi(self):
#         def center_window(self):
#             qtRectangle = self.frameGeometry()
#             centerPoint = QDesktopWidget().availableGeometry().center()
#             qtRectangle.moveCenter(centerPoint)
#             self.move(qtRectangle.topLeft())
#             # self.show()
#
#         self.setAcceptDrops(True)
#         self.dialog = QFileDialog()
#         self.statusBar().showMessage('Ready')
#         self.setWindowTitle("PEM Editor  v" + str(__version__))
#         self.setWindowIcon(
#             QtGui.QIcon(os.path.join(application_path, "crone_logo.ico")))
#         self.setGeometry(500, 300, 800, 600)
#         center_window(self)
#
#     def open_file_dialog(self):
#         try:
#             file = self.dialog.getOpenFileName(self, 'Open File')
#             if file[0].lower().endswith('.pem'):
#                 self.editor.open_files(file[0])
#                 # self.setFixedSize(self.layout.sizeHint())
#             else:
#                 self.message.information(None, 'Error', 'Invalid File Format')
#                 return
#         except Exception as e:
#             logging.warning(str(e))
#             self.message.information(None, 'Error', str(e))
#             pass
#
#     def dragEnterEvent(self, e):
#         urls = [url.toLocalFile() for url in e.mimeData().urls()]
#
#         def check_extension(urls):
#             for url in urls:
#                 if url.lower().endswith('pem'):
#                     continue
#                 else:
#                     return False
#             return True
#
#         if check_extension(urls):
#             e.accept()
#         else:
#             e.ignore()
#
#     def dropEvent(self, e):
#         try:
#             urls = [url.toLocalFile() for url in e.mimeData().urls()]
#             self.editor.open_files(urls)
#             # #Resize the window
#             # if self.gridLayout.sizeHint().height()+25>self.size().height():
#             #     self.resize(self.gridLayout.sizeHint().width()+25, self.gridLayout.sizeHint().height()+25)
#         except Exception as e:
#             logging.warning(str(e))
#             self.message.information(None, 'Error - Could not open selected PEM files', str(e))
#             pass


class PEMEditor(QWidget, Ui_PEMEditorWidget):
    def __init__(self, parent):
        super(PEMEditor, self).__init__(parent)
        self.setupUi(self)

        self.parent = parent
        self.message = QMessageBox()
        self.pem_files = []
        # self.parser = PEMParser()
        # self.serializer = PEMSerializer()
        self.create_table()
        self.table.viewport().installEventFilter(self)
        self.tabWidget.hide()

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

    # def open_files(self, files):
    #     if not isinstance(files, list) and isinstance(files, str):
    #         files = [files]
    #     for file in files:
    #         try:
    #             pem_file = self.parser.parse(file)
    #             self.pem_files.append(pem_file)
    #
    #             if len(self.pem_files) == 1:  # The initial fill of the header and station info
    #                 if self.client_edit.text() == '':
    #                     self.client_edit.setText(self.pem_files[0].header['Client'])
    #                 if self.grid_edit.text() == '':
    #                     self.grid_edit.setText(self.pem_files[0].header['Grid'])
    #                 if self.loop_edit.text() == '':
    #                     self.loop_edit.setText(self.pem_files[0].header['Loop'])
    #
    #                 all_stations = [file.get_unique_stations() for file in self.pem_files]
    #
    #                 if self.min_range_edit.text() == '':
    #                     min_range = str(min(chain.from_iterable(all_stations)))
    #                     self.min_range_edit.setText(min_range)
    #                 if self.max_range_edit.text() == '':
    #                     max_range = str(max(chain.from_iterable(all_stations)))
    #                     self.max_range_edit.setText(max_range)
    #
    #         except Exception as e:
    #             logging.info(str(e))
    #             self.message.information(None, 'Error', str(e))
    #
    #     if len(self.pem_files) > 0:
    #         self.parent.statusBar().showMessage('Opened {0} PEM Files'.format(len(files)), 2000)
    #         self.fill_share_range()
    #     # self.update_table()

    # Creates the right-click context menu on the table
    def contextMenuEvent(self, event):
        if self.table.underMouse():
            if self.table.selectionModel().selectedIndexes():
                self.table.menu = QMenu(self.table)
                self.table.remove_file_action = QAction("&Remove", self)
                self.table.remove_file_action.triggered.connect(self.remove_file)
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
            self.parent.statusBar().showMessage('{0} removed'.format(self.pem_files[row].filepath), 2000)
            del self.pem_files[row]
            self.update_table()
        else:
            pass

    # Creates the table when the editor is first opened
    def create_table(self):
        self.columns = ['File', 'Client', 'Grid', 'Line/Hole', 'Loop', 'First Station', 'Last Station']
        self.table.setColumnCount(len(self.columns))
        self.table.setHorizontalHeaderLabels(self.columns)
        self.table.setSizeAdjustPolicy(
            QAbstractScrollArea.AdjustToContents)
        self.table.resizeColumnsToContents()

    def add_to_table(self, pem_file):

        header = pem_file.header
        file = os.path.basename(pem_file.filepath)
        client = self.client_edit.text() if self.share_header_checkbox.isChecked() else header.get('Client')
        grid = self.grid_edit.text() if self.share_header_checkbox.isChecked() else header.get('Grid')
        loop = self.loop_edit.text() if self.share_header_checkbox.isChecked() else header.get('Loop')

        line = header.get('LineHole')
        start_stn = self.min_range_edit.text() if self.share_range_checkbox.isChecked() else str(
            min(pem_file.get_unique_stations()))
        end_stn = self.max_range_edit.text() if self.share_range_checkbox.isChecked() else str(
            max(pem_file.get_unique_stations()))

        new_row = [file, client, grid, line, loop, start_stn, end_stn]

        row_pos = self.table.rowCount()
        self.table.insertRow(row_pos)

        for i, column in enumerate(self.columns):
            self.table.setItem(row_pos, i, QTableWidgetItem(new_row[i]))

        self.table.resizeColumnsToContents()

        boldFont = QtGui.QFont()
        boldFont.setBold(True)
        # Only used for table comparisons
        pem_file_info_list = [
            file,
            header.get('Client'),
            header.get('Grid'),
            header.get('LineHole'),
            header.get('Loop'),
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

    # def clear_files(self):
    #     while self.table.rowCount() > 0:
    #         self.table.removeRow(0)
    #     self.pem_files.clear()
    #     self.min_range_edit.setText('')
    #     self.max_range_edit.setText('')
    #     self.client_edit.setText('')
    #     self.grid_edit.setText('')
    #     self.loop_edit.setText('')
    #
    # def save_all(self):
    #     if len(self.pem_files) > 0:
    #         for row in range(self.table.rowCount()):
    #             self.pem_files[row].header['Client'] = self.table.item(row, 1).text()
    #             self.pem_files[row].header['Grid'] = self.table.item(row, 2).text()
    #             self.pem_files[row].header['LineHole'] = self.table.item(row, 3).text()
    #             self.pem_files[row].header['Loop'] = self.table.item(row, 4).text()
    #         for pem_file in self.pem_files:
    #             save_file = self.serializer.serialize(pem_file)
    #             print(save_file)
    #             self.parent.statusBar().showMessage('{0} PEM files saved'.format(len(self.pem_files)), 2000)
    #             # save_name = os.path.splitext(pem_file.filepath)
    #             # print(save_file, file=open(pem_file.filepath, 'w+'))
    #         self.update_table()

    # def save_pem(self, pem_file):
    #     try:
    #         save_file = pem_file.save_file()
    #         print(save_file)
    #         # print(save_file, file=open(pem_file.filepath, 'w'))
    #     except Exception as e:
    #         self.message.information(None, 'Error', str(e))
    #         logging.info(str(e))
    #
    # def save_all_pems(self):
    #     # TODO Add suffix to file names, and choose location
    #     if len(self.pem_files)>0:
    #         for pem_file in self.pem_files:
    #             try:
    #                 file = pem_file.save_file()
    #                 print(file)
    #                 # print(file, file=open(file.filepath, 'w'))
    #             except Exception as e:
    #                 self.message.information(None, 'Error', str(e))
    #                 logging.info(str(e))
    #     else:
    #         pass


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
