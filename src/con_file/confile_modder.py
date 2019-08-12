import re
import os
import sys
from os.path import isfile, join
import logging
from PyQt5 import (QtCore, QtGui, uic)
from PyQt5.QtWidgets import (QMainWindow, QAction, QApplication, QGridLayout, QFileDialog, QDesktopWidget,
                             QTableWidgetItem, QHeaderView, QAbstractScrollArea, QMessageBox)
from src.pem.pem_parser import PEMParser

__version__ = '0.0.1'

if getattr(sys, 'frozen', False):
    # If the application is run as a bundle, the pyInstaller bootloader
    # extends the sys module by a flag frozen=True and sets the app
    # path into variable _MEIPASS'.
    application_path = sys._MEIPASS
else:
    application_path = os.path.dirname(os.path.abspath(__file__))

samples_path = os.path.join(application_path, "sample_files")
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s', datefmt='%d-%b-%y %H:%M:%S')

MW_qtCreatorFile = os.path.join(application_path, "con_file_window.ui")
Ui_MainWindow, QtBaseClass = uic.loadUiType(MW_qtCreatorFile)


class ConFile:
    """
    Con file object is based on the .CON text-based files. It reads the .CON file, and
    renames the current line name in the .CON file to that of the .CON file's filename. It
    can also populate the client, grid, and loop names if they haven't been set by
    pembat, and it can change the station ranges.
    """
    def __init__(self, filepath):
        self.pem_file = None

        self.filepath = filepath
        self.filename = os.path.basename(self.filepath)  # With extension
        self.file_dir = os.path.dirname(self.filepath)

        # Only used if pembat hasn't been run
        self.re_client = re.compile(r'(RPLS .t1.,\s\")(?P<Client>.*)(\")')
        self.re_holehole = re.compile(r'(RPLS .t2., \")(?P<Loop>.*\s?)(\s{4}[XYZ]\sComponent\")')

        # Unused groups must be made for re.sub
        self.re_line = re.compile(r'((?:Line|Hole)\s)(?P<Line>.*?)(\s+[ZXY]\s+Component)')
        self.re_section = re.compile(r'(RPLS Section,\s+)(?P<Section>\d)(\s+.*)')
        self.re_start_stn = re.compile(r'(RPLS StartStn,\s+)(?P<StartStn>[\W\d]+?)(\s+.*)')
        self.re_end_stn = re.compile(r'(RPLS EndStn,\s+)(?P<EndStn>[\W\d]+?)(\s+.*)')
        self.re_win2_max = re.compile(r'(RPLS MaxWin2,\s+)(?P<Max>[\W\d]+?)(\s+.*)')
        self.re_win2_min = re.compile(r'(RPLS MinWin2,\s+)(?P<Min>[\W\d]+?)(\s+.*)')
        self.re_win2_step = re.compile(r'(RPLS TickWin2,\s+)(?P<Step>\d+)(\s+.*)')

        with open(self.filepath, 'rt') as in_file:
            self.file = in_file.read()

        self.original_name = self.re_line.search(self.file).group('Line')
        self.name = re.split('[XYZ]\.CON',os.path.basename(self.filepath))[0]
        self.start_stn = int(self.re_start_stn.search(self.file).group('StartStn'))
        self.end_stn = int(self.re_end_stn.search(self.file).group('EndStn'))

        self.check_header()
        self.set_win2()

    def check_header(self):
        """
        Checks if pembat.exe has been run. If not, it will fill in the header in its place.
        """
        def get_pem_file():
            pem_file_names = [f for f in os.listdir(self.file_dir) if
                              isfile(join(self.file_dir, f)) and f.lower().endswith('.pem')]
            pem_file_paths = []

            if len(pem_file_names) > 0:
                for file in pem_file_names:
                    pem_file_paths.append(join(self.file_dir, file))
                pem_file = PEMParser().parse(pem_file_paths[0])

                self.pem_file = pem_file
            else:
                pass

        if self.re_client.search(self.file).group('Client').lower() == 'client':
            if self.pem_file is None:
                get_pem_file()

            header = self.pem_file.get_header()
            client = header['Client']
            grid = header['Grid']

            new_client_str = client+'   '+grid
            self.file = re.sub(self.re_client, r"\g<1>"+str(new_client_str)+"\g<3>", self.file)
        else:
            pass

        if self.re_holehole.search(self.file).group('Loop').lower() == 'hole hole ':
            if self.pem_file is None:
                get_pem_file()

            header = self.pem_file.get_header()
            loop = header['Loop']
            survey_type = self.pem_file.get_survey_type()
            line_type = 'Line' if 'surface' in survey_type.lower() else 'Hole'
            new_loop_str = "Loop {0}, {1} {2}".format(loop, line_type, self.name)
            self.file = re.sub(self.re_holehole, r"\g<1>"+str(new_loop_str)+"\g<3>", self.file)
        else:
            pass

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
        self.file = re.sub(self.re_line, r"\g<1>" + str(self.name) + "\g<3>", self.file)

    def save_file(self):
        print(self.file, file=open(self.filepath, 'w+'))


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
        def center_window(self):
            qtRectangle = self.frameGeometry()
            centerPoint = QDesktopWidget().availableGeometry().center()
            qtRectangle.moveCenter(centerPoint)
            self.move(qtRectangle.topLeft())
            self.show()

        self.setGeometry(500, 300, 800, 600)
        self.setWindowTitle('Con File Modder  v'+__version__)
        self.setWindowIcon(
            QtGui.QIcon(os.path.join(application_path, "crone_logo.ico")))
        self.setAcceptDrops(True)

        self.setCentralWidget(self.centralWidget)

        self.statusBar.showMessage('Ready')
        self.message = QMessageBox()

        self.mkdxfButton.clicked.connect(self.run_mkdxf)
        self.mkdxfButton.setShortcut("\r")

        self.shareRangeCheckBox.stateChanged.connect(self.set_ranges)

        self.openFile = QAction("&Open File", self)
        self.openFile.setShortcut("Ctrl+O")
        self.openFile.setStatusTip('Open file')
        self.openFile.triggered.connect(self.open_file_dialog)

        self.saveFiles = QAction("&Save Files", self)
        self.saveFiles.setShortcut("Ctrl+S")
        self.saveFiles.setStatusTip("Save all files")
        self.saveFiles.triggered.connect(self.save_files)

        self.clearFiles = QAction("&Clear Files", self)
        self.clearFiles.setShortcut("Del")
        self.clearFiles.setStatusTip("Clear all files")
        self.clearFiles.triggered.connect(self.clear_files)

        self.fileMenu = self.mainMenu.addMenu('&File')
        self.fileMenu.addAction(self.openFile)
        self.fileMenu.addAction(self.saveFiles)
        self.fileMenu.addAction(self.clearFiles)

        self.create_table()

        center_window(self)

    def dragEnterEvent(self, e):
        urls = [url.toLocalFile() for url in e.mimeData().urls()]
        def check_extension(urls):
            for url in urls:
                if url.lower().endswith('con'):
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
                self.file_open(url)
            # Resize the window
            if self.gridLayout.sizeHint().height()+25>self.size().height():
                self.resize(self.gridLayout.sizeHint().width()+25, self.gridLayout.sizeHint().height()+25)
        except Exception as e:
            logging.warning(str(e))
            self.message.information(None, 'Error', str(e))
            pass

    def file_open(self, file):
        try:
            confile = ConFile(file)
        except Exception as e:
            logging.warning(str(e))
            self.message.information(None, 'Error', str(e))
        else:
            self.files.append(confile)
            self.add_to_table(confile)

    def open_file_dialog(self):
        try:
            file = self.dialog.getOpenFileName(self, 'Open File')
            if file[0].lower().endswith('.con'):
                self.file_open(file[0])
            else:
                self.message.information(None, 'Error', 'Invalid File Format')
                return
        except Exception as e:
            logging.warning(str(e))
            self.message.information(None, 'Error', str(e))
            pass

    def save_files(self):
        if len(self.files) > 0:
            temp_filepaths = []

            for file in self.files:
                temp_filepaths.append(file.filepath)
                file.rename_line()

                if self.shareRangeCheckBox.isChecked():
                    new_min, new_max = self.get_shared_range()
                    file.set_station_range(new_min, new_max)
                else:
                    file.set_station_range(file.start_stn, file.end_stn)

                file.save_file()

            self.clear_files()

            for filepath in temp_filepaths:
                self.file_open(filepath)

    def run_mkdxf(self):
        if len(self.files)>0:
            working_dir = os.path.split(self.files[0].filepath)[0]
            os.chdir(working_dir)
            os.system("start /wait cmd /c mkdxf")
        else:
            pass

    def get_shared_range(self):
        if len(self.files) > 0:
            mins, maxs = [], []
            for file in self.files:
                mins.append(file.start_stn)
                maxs.append(file.end_stn)

            min_stn = min(mins)
            max_stn = max(maxs)
        return min_stn, max_stn

    def set_ranges(self):
        if len(self.files)>0:
            if self.shareRangeCheckBox.isChecked():
                min_range, max_range = self.get_shared_range()
                for file in self.files:
                    file.set_station_range(min_range, max_range)
                self.update_table()
            else:
                for file in self.files:
                    min_range = int(file.start_stn)
                    max_range = int(file.end_stn)
                    file.set_station_range(min_range, max_range)
                self.update_table()
        else:
            pass

    def update_table(self):
        while self.tableWidget.rowCount() > 0:
            self.tableWidget.removeRow(0)
        for file in self.files:
            self.add_to_table(file)

    def create_table(self):
        self.tableWidget.setColumnCount(5)
        self.tableWidget.setHorizontalHeaderLabels(
            ['File', 'Original Line Name', 'New Line Name', 'Original Station Range', 'New Station Range'])
        self.tableWidget.setSizeAdjustPolicy(
            QAbstractScrollArea.AdjustToContents)
        self.tableWidget.resizeColumnsToContents()

    def add_to_table(self, confile):
        name = confile.filename
        current_name = confile.original_name
        new_line_name = confile.name
        old_start_stn = str(confile.start_stn)
        old_end_stn = str(confile.end_stn)

        if self.shareRangeCheckBox.isChecked():
            new_start_stn, new_end_stn = self.get_shared_range()
        else:
            new_start_stn, new_end_stn = old_start_stn, old_end_stn

        row_pos = self.tableWidget.rowCount()
        self.tableWidget.insertRow(row_pos)
        self.tableWidget.setItem(row_pos, 0, QTableWidgetItem(name))
        self.tableWidget.setItem(row_pos, 1, QTableWidgetItem(current_name))
        self.tableWidget.setItem(row_pos, 2, QTableWidgetItem(new_line_name))
        self.tableWidget.setItem(row_pos, 3, QTableWidgetItem(old_start_stn+' to '+old_end_stn))
        self.tableWidget.setItem(row_pos, 4, QTableWidgetItem(str(new_start_stn) + ' to ' + str(new_end_stn)))

        self.tableWidget.resizeColumnsToContents()

        # if self.tableWidget.item(row_pos, 1).text() != self.tableWidget.item(row_pos, 2).text():
        #     for column in range(self.tableWidget.columnCount()):
        #         self.tableWidget.item(row_pos, column).setForeground(QtGui.QColor('red'))
        if self.tableWidget.item(row_pos, 1).text() != self.tableWidget.item(row_pos, 2).text():
            for column in range (1, 3):
                self.tableWidget.item(row_pos, column).setForeground(QtGui.QColor('red'))

        if self.tableWidget.item(row_pos, 3).text() != self.tableWidget.item(row_pos, 4).text():
            for column in range (3, 5):
                self.tableWidget.item(row_pos, column).setForeground(QtGui.QColor('red'))

    def clear_files(self):
        while self.tableWidget.rowCount() > 0:
            self.tableWidget.removeRow(0)
        self.files.clear()


def main():

    app = QApplication(sys.argv)
    mw = MainWindow()
    app.exec_()

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


if __name__ == '__main__':
    main()
