import re
import os
import sys
from os.path import isfile, join
import logging
from PyQt5 import (QtCore, QtGui, uic)
from PyQt5.QtWidgets import (QMainWindow, QTextEdit, QAction, QApplication, QGridLayout, QListWidget, QFileDialog,
                             QTableWidgetItem, QHeaderView, QAbstractScrollArea)

samples_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "sample_files")
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s', datefmt='%d-%b-%y %H:%M:%S')

MW_qtCreatorFile = os.path.join(os.path.dirname(os.path.realpath(__file__)), "con_file_mw.ui")
Ui_MainWindow, QtBaseClass = uic.loadUiType(MW_qtCreatorFile)


class ConFile:
    def __init__(self, filepath):
        self.filepath = filepath

        self.re_line = re.compile(r'(?:Line|Hole)\s(?P<Line>.*?)\s+[ZXY]\s+Component', )
        self.re_section = re.compile(r'RPLS Section,\s+(?P<Section>\d)\s+.*', )
        self.re_start_stn = re.compile(r'RPLS StartStn,\s+(?P<StartStn>\d+)\s+.*', )
        self.re_end_stn = re.compile(r'RPLS EndStn,\s+(?P<EndStn>\d+)\s+.*', )
        self.filename = os.path.basename(self.filepath)  # With extension
        self.name = os.path.splitext(os.path.basename(self.filepath))[0]

        with open(self.filepath, 'rt') as in_file:
            self.file = in_file.read()

        self.original_name = self.re_line.search(self.file).group(1)
        self.new_name = self.name[0:-1]
        self.end_stn = int(self.re_start_stn.search(self.file).group(1))
        self.start_stn = int(self.re_end_stn.search(self.file).group(1))

    def set_station_range(self, start_stn, end_stn):
        old_start_stn = self.re_start_stn.search(self.file).group(0)
        new_start_stn = old_start_stn.replace(self.re_start_stn.search(self.file).group(1), str(start_stn), 1)
        self.file = re.sub(old_start_stn, new_start_stn, self.file)

        old_end_stn = self.re_end_stn.search(self.file).group(0)
        new_end_stn = old_end_stn.replace(self.re_end_stn.search(self.file).group(1), str(end_stn), 1)
        self.file = re.sub(old_end_stn, new_end_stn, self.file)

        old_section = self.re_section.search(self.file).group(0)
        new_section = old_section.replace(self.re_section.search(self.file).group(1), str(1), 1)
        self.file = re.sub(old_section, new_section, self.file)

    def rename_line(self):
        old = self.re_line.search(self.file).group(0)
        new = old.replace(self.re_line.search(self.file).group(1), self.new_name)
        self.file = re.sub(old, new, self.file)

    def save_file(self):
        print(self.file, file=open(self.filepath, 'w'))


class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super().__init__()
        # Ui_MainWindow.__init__(self)
        self.setupUi(self)

        self.initUI()
        self.dialog = QFileDialog()
        self.setLayout = None
        self.files = []

    def initUI(self):

        self.setGeometry(500, 300, 600, 400)
        self.setWindowTitle('Con File Modder')
        self.setWindowIcon(
            QtGui.QIcon(os.path.join(os.path.dirname(os.path.realpath(__file__)), "../qt_ui/icons/crone_logo.ico")))
        self.setAcceptDrops(True)

        self.setCentralWidget(self.centralWidget)
        self.gridLayout.addWidget(self.tableWidget)

        self.statusBar.showMessage('Ready')

        self.openFile = QAction("&Open File", self)
        self.openFile.setShortcut("Ctrl+O")
        self.openFile.setStatusTip('Open file')
        self.openFile.triggered.connect(self.open_file_dialog)

        self.saveFiles = QAction("&Save Files", self)
        self.saveFiles.setShortcut("Ctrl+S")
        self.saveFiles.setStatusTip("Save all files")
        self.saveFiles.triggered.connect(self.save_files)

        self.clearFiles = QAction("&Clear Files", self)
        self.clearFiles.setShortcut("C")
        self.clearFiles.setStatusTip("Clear all files")
        self.clearFiles.triggered.connect(self.clear_files)


        self.fileMenu = self.mainMenu.addMenu('&File')
        self.fileMenu.addAction(self.openFile)
        self.fileMenu.addAction(self.saveFiles)
        self.fileMenu.addAction(self.clearFiles)

        self.create_table()

        self.show()

    def dragEnterEvent(self, e):
        # TODO check file type, only accept CON files
        e.accept()

    def dropEvent(self, e):
        logging.info("File dropped into main window")
        urls = [url.toLocalFile() for url in e.mimeData().urls()]  # if url.lower().endswith('.con')]
        if len(urls) > 0:
            for url in urls:
                self.file_open(url)
        else:
            pass

    def file_open(self, file):
        confile = ConFile
        self.files.append(confile(file))
        self.add_to_table(confile(file))

    def open_file_dialog(self):
        try:
            file = self.dialog.getOpenFileName(self, 'Open File')
            self.file_open(file[0])
        except Exception as e:
            logging.warning(str(e))
            QtGui.QMessageBox.information(None, 'Error', str(e))
            raise

    def save_files(self):
        pass

    def create_table(self):
        self.tableWidget.setColumnCount(5)
        self.tableWidget.setHorizontalHeaderLabels(
            ['File', 'Original Line Name', 'New Line Name', 'Start Station', 'End Station'])
        self.tableWidget.setSizeAdjustPolicy(
            QAbstractScrollArea.AdjustToContents)
        self.tableWidget.resizeColumnsToContents()

    def add_to_table(self, confile):
        name = confile.filename
        current_name = confile.original_name
        new_line_name = confile.new_name
        start_stn = str(confile.start_stn)
        end_stn = str(confile.end_stn)

        row_pos = self.tableWidget.rowCount()
        self.tableWidget.insertRow(row_pos)
        self.tableWidget.setItem(row_pos, 0, QTableWidgetItem(name))
        self.tableWidget.setItem(row_pos, 1, QTableWidgetItem(current_name))
        self.tableWidget.setItem(row_pos, 2, QTableWidgetItem(new_line_name))
        self.tableWidget.setItem(row_pos, 3, QTableWidgetItem(start_stn))
        self.tableWidget.setItem(row_pos, 4, QTableWidgetItem(end_stn))

        self.tableWidget.resizeColumnsToContents()

        if self.tableWidget.itemAt(row_pos,1).text() == self.tableWidget.itemAt(row_pos, 2).text():
            for column in range(self.tableWidget.columnCount()):
                self.tableWidget.item(row_pos, column).setForeground(QtGui.QColor('magenta'))

    def clear_files(self):
        while self.tableWidget.rowCount() > 0:
                self.tableWidget.removeRow(0)
        self.files.clear()


def main():
    app = QApplication(sys.argv)
    mw = MainWindow()

    # file_names = [f for f in os.listdir(samples_path) if isfile(join(samples_path, f)) and f.lower().endswith('.con')]
    # file_paths = []
    #
    # for file in file_names:
    #     file_paths.append(join(samples_path, file))
    #
    # confile = ConFile
    #
    # for file in file_paths:
    #     confile(file)

    app.exec_()


if __name__ == '__main__':
    main()
