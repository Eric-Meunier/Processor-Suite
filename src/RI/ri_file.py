import re
import os
import sys
from os.path import isfile, join
import logging
from PyQt5 import (QtCore, QtGui, uic)
from PyQt5.QtWidgets import (QMainWindow, QAction, QApplication, QGridLayout, QFileDialog, QDesktopWidget,
                             QTableWidgetItem, QHeaderView, QAbstractScrollArea, QMessageBox)

__version__ = '0.0.0'

if getattr(sys, 'frozen', False):
    # If the application is run as a bundle, the pyInstaller bootloader
    # extends the sys module by a flag frozen=True and sets the app
    # path into variable _MEIPASS'.
    application_path = sys._MEIPASS
    ConderWindow_qtCreatorFile = 'qt_ui\\con_file_window.ui'
    icons_path = 'icons'
else:
    application_path = os.path.dirname(os.path.abspath(__file__))
    ConderWindow_qtCreatorFile = os.path.join(os.path.dirname(application_path), 'qt_ui\\con_file_window.ui')
    icons_path = os.path.join(os.path.dirname(application_path), "qt_ui\\icons")

samples_path = os.path.join(application_path, "sample_files")
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s', datefmt='%d-%b-%y %H:%M:%S')

# ConderWindow_qtCreatorFile = os.path.join(os.path.dirname(application_path), 'qt_ui\\con_file_window.ui')
Ui_Conder_Window, QtBaseClass = uic.loadUiType(ConderWindow_qtCreatorFile)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUi()
        self.ri_parser = RIFileParser()
        self.ri_file = RIFile()

    def initUi(self):
        self.setAcceptDrops(True)

    def dragEnterEvent(self, e):
        urls = [url.toLocalFile() for url in e.mimeData().urls()]

        def check_extension(urls):
            for url in urls:
                if url.lower().endswith('ri1') or url.lower().endswith('ri2') or url.lower().endswith('ri3'):
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
            ri_file = self.ri_file(file)
            self.files.append(ri_file)
            self.add_to_table(ri_file)


class RIFileParser:
    def __init__(self):
        self.re_ri = re.compile('')


class RIFile:
    pass

def main():
    app = QApplication(sys.argv)

    mw = MainWindow()
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