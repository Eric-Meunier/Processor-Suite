import pandas as pd
import utm
import sys
import os
from PyQt5 import (QtCore, QtGui, uic)
from PyQt5.QtWidgets import (QApplication, QMainWindow, QFileDialog, QAction, QTableWidgetItem)
from src.gps.gpx import gpxpy

if getattr(sys, 'frozen', False):
    application_path = sys._MEIPASS
    gpxCreatorFile = 'qt_ui\\gpx_creator.ui'
else:
    application_path = os.path.dirname(os.path.abspath(__file__))
    gpxCreatorFile = os.path.join(os.path.dirname(application_path), 'qt_ui\\gpx_creator.ui')

# Load Qt ui file into a class
Ui_GPXCreator, QtBaseClass = uic.loadUiType(gpxCreatorFile)

sys._excepthook = sys.excepthook


def exception_hook(exctype, value, traceback):
    print(exctype, value, traceback)
    sys._excepthook(exctype, value, traceback)
    sys.exit(1)


sys.excepthook = exception_hook


class GPXCreator(QMainWindow, Ui_GPXCreator):
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.setWindowTitle("GPX Creator")
        # self.setWindowIcon(
        #     QtGui.QIcon(os.path.join(icons_path, 'crone_logo.ico')))
        self.dialog = QFileDialog()
        self.setAcceptDrops(True)

        self.filepath = None
        self.gps_zones = [''] + [f"{num} North" for num in range(1, 61)] + [f"{num} South" for num in range(1, 61)]
        for zone in self.gps_zones:
            self.zone_number_box.addItem(zone)

        # Signals
        self.importCSV.triggered.connect(self.open_file_dialog)
        self.exportGPX.triggered.connect(self.save_file_dialog)
        self.export_gpx_btn.clicked.connect(self.save_file_dialog)

        self.system_box.currentIndexChanged.connect(self.toggle_utm_boxes)

    def open_file_dialog(self):
        """
        Open files through the file dialog
        """
        files = self.dialog.getOpenFileNames(self, 'Open File', filter='CSV files (*.csv);; All files(*.*)')
        if files[0] != '':
            for file in files[0]:
                if file.lower().endswith('.csv'):
                    self.import_csv(file)
                else:
                    pass
        else:
            pass

    def save_file_dialog(self):
        """
        Open files through the file dialog
        """
        file = self.dialog.getSaveFileName(self, 'Save File', filter='GPX file (*.gpx);; All files(*.*)')
        if file[0] != '':
            self.export_gpx(file[0])
        else:
            pass

    def dragEnterEvent(self, e):
        e.accept()

    def dropEvent(self, e):
        urls = [url.toLocalFile() for url in e.mimeData().urls()]
        self.import_csv(urls[0])

    def dragMoveEvent(self, e):
        urls = [url.toLocalFile() for url in e.mimeData().urls()]
        if len(urls) == 1 and urls[0].lower().endswith('csv'):
            e.accept()
        else:
            e.ignore()

    def import_csv(self, filepath):

        def write_df_to_table(df):
            headers = list(df)
            self.table.setRowCount(df.shape[0])
            self.table.setColumnCount(df.shape[1])
            self.table.setHorizontalHeaderLabels(headers)

            # getting data from df is computationally costly so convert it to array first
            df_array = df.values
            for row in range(df.shape[0]):
                for col in range(df.shape[1]):
                    value = df_array[row, col]
                    if col in [0, 1]:
                        item = QTableWidgetItem(str(value))
                    else:
                        item = QTableWidgetItem(f"{value:.2f}")
                    self.table.setItem(row, col, item)

        self.filepath = filepath
        data = pd.read_csv(filepath)
        write_df_to_table(data)
        print(f'Opening file {os.path.basename(self.filepath)}')
        self.statusBar().showMessage(f'Opened file {os.path.basename(self.filepath)}', 2000)

    def export_gpx(self, savepath):
        gpx = gpxpy.gpx.GPX()
        print('Exporting GPX...')

    def toggle_utm_boxes(self):
        if self.system_box.currentText() == 'UTM':
            self.zone_number_box.setEnabled(True)
            self.zone_letter_box.setEnabled(True)
            self.zone_number_label.setEnabled(True)
            self.zone_letter_label.setEnabled(True)
        else:
            self.zone_number_box.setEnabled(False)
            self.zone_letter_box.setEnabled(False)
            self.zone_number_label.setEnabled(False)
            self.zone_letter_label.setEnabled(False)

def main():
    app = QApplication(sys.argv)

    gpx_creator = GPXCreator()
    gpx_creator.show()
    file = r'C:\Users\Eric\PycharmProjects\Crone\sample_files\PEMGetter files\gps.csv'
    gpx_creator.import_csv(file)
    gpx_creator.export_gpx('sdfs')

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
