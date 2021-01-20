import re
import os
import sys
from os.path import isfile, join
import logging
from PyQt5 import (QtGui, uic)
from PyQt5.QtWidgets import (QMainWindow, QAction, QApplication, QFileDialog, QDesktopWidget,
                             QTableWidgetItem, QAbstractScrollArea, QMessageBox)
from src.pem._legacy.pem_parser import PEMParser

__version__ = '0.0.2'

if getattr(sys, 'frozen', False):
    # If the application is run as a bundle, the pyInstaller bootloader
    # extends the sys module by a flag frozen=True and sets the app
    # path into variable _MEIPASS'.
    application_path = os.path.dirname(sys.executable)
    ConderWindow_qtCreatorFile = 'ui\\con_file_window.ui'
    icons_path = 'ui\\icons'
else:
    application_path = os.path.dirname(os.path.abspath(__file__))
    ConderWindow_qtCreatorFile = os.path.join(os.path.dirname(application_path), 'ui\\con_file_window.ui')
    icons_path = os.path.join(os.path.dirname(application_path), "ui\\icons")

samples_path = os.path.join(application_path, "sample_files")
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s', datefmt='%d-%b-%y %H:%M:%S')

# ConderWindow_qtCreatorFile = os.path.join(os.path.dirname(application_path), 'ui\\con_file_window.ui')
Ui_Conder_Window, QtBaseClass = uic.loadUiType(ConderWindow_qtCreatorFile)


class Conder(QMainWindow, Ui_Conder_Window):
    def __init__(self, parent=None):
        super().__init__()
        self.parent = parent
        self.initUI()
        self.initActions()

        self.dialog = QFileDialog()
        self.message = QMessageBox()
        self.setCentralWidget(self.centralWidget)
        self.files = []

    def initUI(self):
        def center_window(self):
            qtRectangle = self.frameGeometry()
            centerPoint = QDesktopWidget().availableGeometry().center()
            qtRectangle.moveCenter(centerPoint)
            self.move(qtRectangle.topLeft())

        self.setupUi(self)
        self.setWindowTitle('Conder  v' + __version__)
        self.setWindowIcon(
            QtGui.QIcon(os.path.join(icons_path, 'conder 32.png')))
        center_window(self)

    def initActions(self):
        self.setAcceptDrops(True)
        self.mainMenu = self.menuBar()

        self.mkdxfButton.clicked.connect(self.run_mkdxf)
        self.mkdxfButton.setShortcut("Ctrl+D")

        self.shareRangeCheckBox.stateChanged.connect(self.set_ranges)

        self.openFile = QAction("&Open...", self)
        self.openFile.setShortcut("Ctrl+O")
        self.openFile.setStatusTip('Open file')
        self.openFile.triggered.connect(self.open_file_dialog)

        self.saveFiles = QAction("&Save Files", self)
        self.saveFiles.setShortcut("Ctrl+S")
        self.saveFiles.setStatusTip("Save all files")
        self.saveFiles.triggered.connect(self.save_files)

        self.clearFiles = QAction("&Clear Files", self)
        self.clearFiles.setShortcut("Shift+Del")
        self.clearFiles.setStatusTip("Clear all files")
        self.clearFiles.triggered.connect(self.clear_files)

        self.fileMenu = self.mainMenu.addMenu('&File')
        self.fileMenu.addAction(self.openFile)
        self.fileMenu.addAction(self.saveFiles)
        self.fileMenu.addAction(self.clearFiles)

        self.create_table()

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
            self.open_files(urls)
            # Resize the window
            if self.gridLayout.sizeHint().height() + 25 > self.size().height():
                self.resize(self.gridLayout.sizeHint().width() + 25, self.gridLayout.sizeHint().height() + 25)
        except Exception as e:
            logging.warning(str(e))
            self.message.information(None, 'Error', str(e))
            pass

    def open_files(self, files):
        if not isinstance(files, list) and isinstance(files, str):
            files = [files]
        for file in files:
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
            files = self.dialog.getOpenFileNames(self, 'Open File', filter='Con files (*.con);; All files(*.*)')
            if files[0] != '':
                for file in files[0]:
                    if file.lower().endswith('.con'):
                        self.open_files(file)
                    else:
                        pass
            else:
                pass
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
            if len(self.files) > 1:
                self.window().statusBar().showMessage('{} CON files saved'.format(str(len(self.files))), 2000)
            else:
                self.window().statusBar().showMessage('1 CON file saved')
            self.clear_files()
            self.open_files(temp_filepaths)

    def run_mkdxf(self):
        if len(self.files) > 0:
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
        if len(self.files) > 0:
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
        self.tableWidget.setItem(row_pos, 3, QTableWidgetItem(old_start_stn + ' to ' + old_end_stn))
        self.tableWidget.setItem(row_pos, 4, QTableWidgetItem(str(new_start_stn) + ' to ' + str(new_end_stn)))

        self.tableWidget.resizeColumnsToContents()

        # if self.tableWidget.item(row_pos, 1).text() != self.tableWidget.item(row_pos, 2).text():
        #     for column in range(self.tableWidget.columnCount()):
        #         self.tableWidget.item(row_pos, column).setForeground(QtGui.QColor('red'))
        if self.tableWidget.item(row_pos, 1).text() != self.tableWidget.item(row_pos, 2).text():
            for column in range(1, 3):
                self.tableWidget.item(row_pos, column).setForeground(QtGui.QColor('red'))

        if self.tableWidget.item(row_pos, 3).text() != self.tableWidget.item(row_pos, 4).text():
            for column in range(3, 5):
                self.tableWidget.item(row_pos, column).setForeground(QtGui.QColor('red'))

    def clear_files(self):
        while self.tableWidget.rowCount() > 0:
            self.tableWidget.removeRow(0)
        self.files.clear()


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
        self.re_bfield = re.compile('RPLS .t1.,.*B-Field Step')

        # Unused groups must be made for re.sub
        self.re_line = re.compile(r'((?:Line|Hole)\s)(?P<Line>.*?)(\s+[ZXY]\s+Component)')
        self.re_hole = re.compile(r'((?:Hole)\s)(?P<Hole>.*?)(\s+[ZXY]\s+Component)')
        self.re_bfield_line = re.compile(r'(RPLS .t2.*(Line|Hole):\s)(?P<Line>.*?)(\s+Comp:\s[XYZ]\")')
        self.re_section = re.compile(r'(RPLS Section,\s+)(?P<Section>\d)(\s+.*)')
        self.re_start_stn = re.compile(r'(RPLS StartStn,\s+)(?P<StartStn>[\W\d]+?)(\s+.*)')
        self.re_end_stn = re.compile(r'(RPLS EndStn,\s+)(?P<EndStn>[\W\d]+?)(\s+.*)')
        self.re_win2_max = re.compile(r'(RPLS MaxWin2,\s+)(?P<Max>[\W\d]+?)(\s+.*)')
        self.re_win2_min = re.compile(r'(RPLS MinWin2,\s+)(?P<Min>[\W\d]+?)(\s+.*)')
        self.re_win2_step = re.compile(r'(RPLS TickWin2,\s+)(?P<Step>\d+)(\s+.*)')

        with open(self.filepath, 'rt') as in_file:
            self.file = in_file.read()

        if re.search(self.re_bfield, self.file):  # Check if the file is b-field
            self.original_name = self.name = self.re_bfield_line.search(self.file).group('Line')
        else:
            self.original_name = self.re_line.search(self.file).group('Line')

            # If it is a borehole, use the group 'Hole' as the name (but make sure it doesn't say 'Hole Hole'
            if re.search(self.re_hole, self.file) and not re.search('Hole Hole', self.file):
                self.name = re.search(self.re_hole, self.file).group('Hole')
            else:
                self.name = re.split('[XYZ]\.CON', os.path.basename(self.filepath))[0]

            self.check_header()  # If it's not B-field, check if pembat has been run

        self.start_stn = int(self.re_start_stn.search(self.file).group('StartStn'))
        self.end_stn = int(self.re_end_stn.search(self.file).group('EndStn'))
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

            new_client_str = client + '   ' + grid
            self.file = re.sub(self.re_client, r"\g<1>" + str(new_client_str) + "\g<3>", self.file)
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
            self.file = re.sub(self.re_holehole, r"\g<1>" + str(new_loop_str) + "\g<3>", self.file)
        else:
            pass

    def set_station_range(self, start_stn, end_stn):
        self.file = re.sub(self.re_start_stn, r"\g<1>" + str(start_stn) + "\g<3>", self.file)
        self.file = re.sub(self.re_end_stn, r"\g<1>" + str(end_stn) + "\g<3>", self.file)
        self.file = re.sub(self.re_section, r"\g<1>" + str(1) + "\g<3>", self.file)

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

            self.file = re.sub(self.re_win2_max, r"\g<1>" + str(new_win2_max) + "\g<3>", self.file)
            self.file = re.sub(self.re_win2_min, r"\g<1>" + str(new_win2_min) + "\g<3>", self.file)
            self.file = re.sub(self.re_win2_step, r"\g<1>" + str(new_win2_step) + "\g<3>", self.file)

        else:
            pass

    def rename_line(self):
        self.file = re.sub(self.re_line, r"\g<1>" + str(self.name) + "\g<3>", self.file)

    def save_file(self):
        print(self.file, file=open(self.filepath, 'w+'))


def main():
    app = QApplication(sys.argv)
    mw = Conder()
    mw.show()
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
