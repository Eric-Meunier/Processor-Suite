import re
import os
import sys
import datetime
import statistics as stats
import logging
import itertools
from src.pem.pem_parser import PEMParser
from src.pem.pem_file import PEMFile
from PyQt5.QtWidgets import (QWidget, QMainWindow, QApplication, QGridLayout, QDesktopWidget, QMessageBox,
                             QFileDialog, QAbstractScrollArea, QTableWidgetItem)
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


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUi()
        layout = QGridLayout(self)
        self.setLayout(layout)
        self.editor = PEMEditor()
        self.message = QMessageBox()
        self.layout().addWidget(self.editor)

    def initUi(self):
        def center_window(self):
            qtRectangle = self.frameGeometry()
            centerPoint = QDesktopWidget().availableGeometry().center()
            qtRectangle.moveCenter(centerPoint)
            self.move(qtRectangle.topLeft())
            self.show()

        self.setAcceptDrops(True)
        self.dialog = QFileDialog()
        self.statusBar().showMessage('Ready')
        self.setWindowTitle("PEM Editor  v" + str(__version__))
        self.setWindowIcon(
            QtGui.QIcon(os.path.join(application_path, "crone_logo.ico")))
        # TODO Program where the window opens
        self.setGeometry(500, 300, 800, 600)
        center_window(self)

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
            for url in urls:
                self.editor.open_file(url)
            # Resize the window
            # if self.gridLayout.sizeHint().height()+25>self.size().height():
            #     self.resize(self.gridLayout.sizeHint().width()+25, self.gridLayout.sizeHint().height()+25)
        except Exception as e:
            logging.warning(str(e))
            self.message.information(None, 'Error', str(e))
            pass


class PEMEditor(QWidget, Ui_PEMEditorWidget):
    def __init__(self):
        super(PEMEditor, self).__init__()
        self.setupUi(self)

        self.message = QMessageBox()
        self.pem_files = []
        self.parser = PEMParser
        self.create_table()

    def open_file(self, file):
        try:
            pem_file = self.parser().parse(file)
            self.pem_files.append(pem_file)
            self.add_to_table(pem_file)
        except Exception as e:
            logging.info(str(e))
            self.message.information(None, 'Error', str(e))

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
        client = header.get('Client')
        grid = header.get('Grid')
        line = header.get('LineHole')
        loop = header.get('Loop')
        start_stn = str(min(pem_file.get_unique_stations()))
        end_stn = str(max(pem_file.get_unique_stations()))

        new_row = [file, client, grid, line, loop, start_stn, end_stn]

        # if self.shareRangeCheckBox.isChecked():
        #     new_start_stn, new_end_stn = self.get_shared_range()
        # else:
        #     new_start_stn, new_end_stn = old_start_stn, old_end_stn

        row_pos = self.table.rowCount()
        self.table.insertRow(row_pos)

        for i, column in enumerate(self.columns):
            self.table.setItem(row_pos, i, QTableWidgetItem(new_row[i]))

        self.table.resizeColumnsToContents()

        # if self.table.item(row_pos, 1).text() != self.table.item(row_pos, 2).text():
        #     for column in range (1, 3):
        #         self.table.item(row_pos, column).setForeground(QtGui.QColor('red'))
        #
        # if self.table.item(row_pos, 3).text() != self.table.item(row_pos, 4).text():
        #     for column in range (3, 5):
        #         self.table.item(row_pos, column).setForeground(QtGui.QColor('red'))

    def clear_files(self):
        while self.table.rowCount() > 0:
            self.table.removeRow(0)
        self.pem_files.clear()

    def save_pem(self, pem_file):
        try:
            save_file = pem_file.save_file()
            print(save_file)
            # print(save_file, file=open(pem_file.filepath, 'w'))
        except Exception as e:
            self.message.information(None, 'Error', str(e))
            logging.info(str(e))

    def save_all_pems(self):
        # TODO Add suffix to file names, and choose location
        if len(self.pem_files)>0:
            for pem_file in self.pem_files:
                try:
                    file = pem_file.save_file()
                    print(file)
                    # print(file, file=open(file.filepath, 'w'))
                except Exception as e:
                    self.message.information(None, 'Error', str(e))
                    logging.info(str(e))
        else:
            pass

if __name__ == '__main__':
    app = QApplication(sys.argv)
    mw = MainWindow()
    sample_files = os.path.join(os.path.dirname(os.path.dirname(application_path)), "sample_files")
    file_names = [f for f in os.listdir(sample_files) if os.path.isfile(os.path.join(sample_files, f)) and f.lower().endswith('.pem')]
    file_paths = []

    for file in file_names:
        # file_paths.append(os.path.join(sample_files, file))
        mw.editor.open_file(os.path.join(sample_files, file))
    # editor = PEMEditor()
    app.exec_()
