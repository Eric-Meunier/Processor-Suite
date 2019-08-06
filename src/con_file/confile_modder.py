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

        self.re_line = re.compile(r'((?:Line|Hole)\s)(?P<Line>.*?)(\s+[ZXY]\s+Component)')
        self.re_section = re.compile(r'(RPLS Section,\s+)(?P<Section>\d)(\s+.*)')
        self.re_start_stn = re.compile(r'(RPLS StartStn,\s+)(?P<StartStn>[\W\d]+?)(\s+.*)')
        self.re_end_stn = re.compile(r'(RPLS EndStn,\s+)(?P<EndStn>[\W\d]+?)(\s+.*)')
        self.re_win2_max = re.compile(r'(RPLS MaxWin2,\s+)(?P<Max>[\W\d]+?)(\s+.*)')
        self.re_win2_min = re.compile(r'(RPLS MinWin2,\s+)(?P<Min>[\W\d]+?)(\s+.*)')
        self.re_win2_step = re.compile(r'(RPLS TickWin2,\s+)(?P<Step>\d+)(\s+.*)')

        self.filename = os.path.basename(self.filepath)  # With extension
        self.name = os.path.splitext(os.path.basename(self.filepath))[0]

        with open(self.filepath, 'rt') as in_file:
            self.file = in_file.read()

        self.original_name = self.re_line.search(self.file).group('Line')
        self.new_name = self.name[0:-1]
        self.start_stn = int(self.re_start_stn.search(self.file).group('StartStn'))
        self.end_stn = int(self.re_end_stn.search(self.file).group('EndStn'))

        self.set_win2()

    def set_station_range(self, start_stn, end_stn):
        self.file = re.sub(self.re_start_stn, r"\g<1>"+str(start_stn)+"\g<3>", self.file)
        self.file = re.sub(self.re_end_stn, r"\g<1>"+str(end_stn)+"\g<3>", self.file)
        self.file = re.sub(self.re_section, r"\g<1>"+str(1)+"\g<3>", self.file)

    def set_win2(self):
        win2_max = self.re_win2_max.search(self.file).group('Max')
        win2_min = self.re_win2_min.search(self.file).group('Min')

        if int(win2_max) - int(win2_min) < 25:
            new_win2_step = 5

            if abs(int(win2_max)) > abs(int(win2_min)):
                new_win2_max = 15
                new_win2_min = -10
            else:
                new_win2_max = 10
                new_win2_min = -15

            self.file = re.sub(self.re_win2_max, r"\g<1>"+str(new_win2_max)+"\g<3>", self.file)
            self.file = re.sub(self.re_win2_min, r"\g<1>"+str(new_win2_min)+"\g<3>", self.file)
            self.file = re.sub(self.re_win2_step, r"\g<1>"+str(new_win2_step)+"\g<3>", self.file)

        else:
            pass

    def rename_line(self):
        self.file = re.sub(self.re_line, r"\g<1>" + str(self.new_name) + "\g<3>", self.file)

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
        if len(self.files) > 0:
            temp_filepaths = []
            new_range = self.get_range()

            for file in self.files:
                temp_filepaths.append(file.filepath)
                file.rename_line()
                file.set_station_range(new_range[0], new_range[1])
                file.set_win2()
                file.save_file()

            self.clear_files()

            for filepath in temp_filepaths:
                self.file_open(filepath)

    def get_range(self):
        if len(self.files) > 0:
            mins, maxs = [], []
            for file in self.files:
                mins.append(file.start_stn)
                maxs.append(file.end_stn)

            min_stn = min(mins)
            max_stn = max(maxs)
        return min_stn, max_stn

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

        if self.tableWidget.item(row_pos, 1).text() != self.tableWidget.item(row_pos, 2).text():
            for column in range(self.tableWidget.columnCount()):
                self.tableWidget.item(row_pos, column).setForeground(QtGui.QColor('red'))

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
