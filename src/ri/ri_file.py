import logging
import re
import sys

from PyQt5.QtWidgets import (QMainWindow, QApplication)

__version__ = '0.0.0'

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s', datefmt='%d-%b-%y %H:%M:%S')

sys._excepthook = sys.excepthook


def exception_hook(exctype, value, traceback):
    print(exctype, value, traceback)
    sys._excepthook(exctype, value, traceback)
    sys.exit(1)


sys.excepthook = exception_hook


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUi()
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
        except Exception as e:
            logging.warning(str(e))
            pass

    def open_files(self, files):
        if not isinstance(files, list) and isinstance(files, str):
            files = [files]
        for file in files:
            ri_file = self.ri_file.open(file)


class RIFile:
    def __init__(self):
        # self.file = {}
        self.header = {}
        self.data = []
        self.columns = ['Station', 'Component', 'Gain', 'Theoretical PP', 'Measured PP', 'S1', 'Last Step',
                       '(M-T)*100/Tot', '(S1-T)*100/Tot', '(LS-T)*100/Tot', '(S2-S1)*100/Tot', 'S3%', 'S4%',
                       'S5%', 'S6%', 'S7%', 'S8%', 'S9%', 'S10%']
        self.survey_type = None

    def open(self, filepath):

        self.data = []

        with open(filepath, 'rt') as in_file:
            step_info = re.split('\$\$', in_file.read())[-1]
            raw_file = step_info.splitlines()
            raw_file = [line.split() for line in raw_file[1:]]  # Removing the header row
            # Creating the remaining off-time channel columns for the header
            [self.columns.append('Ch' + str(num + 11)) for num in range(len(raw_file[0]) - len(self.columns))]

            for row in raw_file:
                station = {}
                for i, column in enumerate(self.columns):
                    station[column] = row[i]
                self.data.append(station)
        return self

    def get_components(self):
        components = []
        for row in self.data:
            component = row['Component']
            if component not in components:
                components.append(row['Component'])
        return components


def main():
    app = QApplication(sys.argv)
    # file = r'C:\_Data\2019\BMSC\Surface\MO-254\STP\254-01N.RI2'
    file = r'C:\_Data\2019\Nantou BF\Surface\Semtoun 100-114\STP\50N_100.RI3'
    mw = MainWindow()
    # mw.ri_file.open(file)
    mw.show()
    app.exec_()


if __name__ == '__main__':
    main()