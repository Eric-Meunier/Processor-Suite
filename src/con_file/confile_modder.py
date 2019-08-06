import re
import os
import sys
from os.path import isfile, join
import logging
from PyQt5.QtWidgets import (QWidget, QMainWindow, QApplication, QGridLayout, QDesktopWidget)
from PyQt5 import (QtCore, QtGui, QtWidgets, uic)

samples_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "sample_files")
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s', datefmt='%d-%b-%y %H:%M:%S')


class ConFile:
    def __init__(self, filepath):
        self.filepath = filepath

        self.re_line = re.compile(r'(?:Line|Hole)\s(?P<Line>.*?)\s+[ZXY]\s+Component',)
        self.re_section = re.compile(r'RPLS Section,\s+(?P<Section>\d)\s+.*',)
        self.re_start_stn = re.compile(r'RPLS StartStn,\s+(?P<StartStn>\d+)\s+.*',)
        self.re_end_stn = re.compile(r'RPLS EndStn,\s+(?P<EndStn>\d+)\s+.*',)
        self.name = os.path.splitext(os.path.basename(self.filepath))[0]
        self.end_stn = None
        self.start_stn = None

        with open(self.filepath, 'rt') as in_file:
            self.file = in_file.read()

        self.get_station_range()
        self.set_station_range(500, 10)
        self.rename_line()
        self.save_file()

    def get_station_range(self):
        self.start_stn = int(self.re_start_stn.search(self.file).group(1))
        self.end_stn = int(self.re_end_stn.search(self.file).group(1))

        return self.start_stn, self.end_stn

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

        old_name = self.re_line.search(self.file).group(0)
        new_name = old_name.replace(self.re_line.search(self.file).group(1), self.name[0:-1])
        self.file = re.sub(old_name, new_name, self.file)

    def save_file(self):
        print(self.file, file=open(self.filepath, 'w'))






class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):

        self.statusBar().showMessage('Ready')
        self.setGeometry(500, 300, 800, 600)
        self.setWindowTitle('Con File Modder')
        self.show()

    def dragEnterEvent(self, e):
        # TODO check file type, only accept CON files
        e.accept()
        # if e.mimeData().hasFormat('text/plain'):
        #     e.accept()
        # else:
        #     e.ignore()

    def dropEvent(self, e):
        logging.info("File dropped into main window")
        urls = [url.toLocalFile() for url in e.mimeData().urls()]
        self.file_open(urls)


def main():

    # app = QtGui.QApplication(sys.argv)
    # mw = MainWindow()

    file_names = [f for f in os.listdir(samples_path) if isfile(join(samples_path, f)) and f.lower().endswith('.con')]
    file_paths = []

    for file in file_names:
        file_paths.append(join(samples_path, file))

    confile = ConFile

    for file in file_paths:
        confile(file)

    # app.exec_()

if __name__ == '__main__':
    main()