import pandas as pd
import utm
import sys
import os
import re
import csv
from PyQt5 import (QtGui, uic)
from PyQt5.QtWidgets import (QApplication, QMainWindow, QFileDialog, QMessageBox, QTableWidgetItem, QAction)

if getattr(sys, 'frozen', False):
    application_path = sys._MEIPASS
    gpxCreatorFile = 'qt_ui\\gpx_creator.ui'
    icons_path = 'icons'
else:
    application_path = os.path.dirname(os.path.abspath(__file__))
    gpxCreatorFile = os.path.join(os.path.dirname(application_path), 'qt_ui\\gpx_creator.ui')
    icons_path = os.path.join(os.path.dirname(application_path), "qt_ui\\icons")

# Load Qt ui file into a class
Ui_GPXCreator, QtBaseClass = uic.loadUiType(gpxCreatorFile)

sys._excepthook = sys.excepthook


def exception_hook(exctype, value, traceback):
    print(exctype, value, traceback)
    sys._excepthook(exctype, value, traceback)
    sys.exit(1)


sys.excepthook = exception_hook


class GPXCreator(QMainWindow, Ui_GPXCreator):
    """
    Program to convert a CSV file into a GPX file. The datum of the intput GPS must be NAD 83 or WGS 84.
    Columns of the CSV must be 'Name', 'Comment', 'Easting', 'Northing'.
    """
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.setWindowTitle("GPX Creator")
        self.setWindowIcon(
            QtGui.QIcon(os.path.join(icons_path, 'gpx_creator_4.svg')))
        self.dialog = QFileDialog()
        self.message = QMessageBox()
        self.setAcceptDrops(True)

        self.filepath = None
        self.gps_zones = [''] + [f"{num} North" for num in range(1, 61)] + [f"{num} South" for num in range(1, 61)]
        for zone in self.gps_zones:
            self.zone_number_box.addItem(zone)

        # Actions
        self.del_file = QAction("&Remove Row", self)
        self.del_file.setShortcut("Del")
        self.del_file.triggered.connect(self.remove_row)
        self.addAction(self.del_file)

        # Signals
        self.importCSV.triggered.connect(self.open_file_dialog)
        self.exportGPX.triggered.connect(self.export_gpx)
        self.create_csv_template_action.triggered.connect(self.create_csv_template)
        self.export_gpx_btn.clicked.connect(self.export_gpx)
        self.auto_name_btn.clicked.connect(self.auto_name)
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

    def remove_row(self):
        rows = [model.row() for model in self.table.selectionModel().selectedRows()]
        if rows:
            for row in reversed(rows):
                self.table.removeRow(row)

    def create_csv_template(self):
        """
        Create an empty CSV file with the correct columns.
        :return: None
        """
        file = self.dialog.getSaveFileName(self, 'Save File', filter='CSV file (*.csv);; All files(*.*)')[0]
        if file != '':
            with open(file, 'w') as csvfile:
                filewriter = csv.writer(csvfile, delimiter=',',
                                        quotechar='|', quoting=csv.QUOTE_MINIMAL)
                filewriter.writerow(['Name', 'Comment', 'Easting', 'Northing'])
                os.startfile(file)
        else:
            pass

    def auto_name(self):
        """
        Append the Comment to the Name to create unique names
        :return: None
        """
        if self.table.rowCount() > 0:
            for row in range(self.table.rowCount()):
                name = self.table.item(row, 0).text()
                comment = self.table.item(row, 1).text()

                new_name = f"{name} - {comment}"
                item = QTableWidgetItem(new_name)
                self.table.setItem(row, 0, item)

    def import_csv(self, filepath):
        """
        Add the information from the CSV to the table.
        :param filepath: str: filepath of the CSV file to convert to GPX
        :return: None
        """

        def write_df_to_table(df):
            # headers = list(df)
            self.table.setRowCount(df.shape[0])
            # self.table.setColumnCount(df.shape[1])
            # self.table.setHorizontalHeaderLabels(headers)

            # getting data from df is computationally costly so convert it to array first
            df_array = df.values
            for row in range(df.shape[0]):
                for col in range(df.shape[1]):
                    value = df_array[row, col]
                    if col in [0, 1]:
                        item = QTableWidgetItem(str(value))
                    else:
                        try:
                            value = float(value)
                        except ValueError:
                            item = QTableWidgetItem('Error')
                        else:
                            item = QTableWidgetItem(f"{value:.4f}")

                    self.table.setItem(row, col, item)

        self.filepath = filepath
        data = pd.read_csv(filepath)
        write_df_to_table(data)
        print(f'Opening file {os.path.basename(self.filepath)}')
        self.statusBar().showMessage(f'Opened file {os.path.basename(self.filepath)}', 2000)

    def export_gpx(self):
        """
        Save a GPX file from the information in the table.
        :return: None
        """

        if not self.table.rowCount() > 0:
            return

        print('Exporting GPX...')
        self.statusBar().showMessage(f"Saving GPX file...")

        default_path = os.path.dirname(self.filepath)
        file = self.dialog.getSaveFileName(self, 'Save File', default_path, filter='GPX file (*.gpx);; All files(*.*)')
        if file[0] == '':
            return

        savepath = file[0]
        gpx = src._legacy.gpx_module.gpxpy.gpx.GPX()

        if not self.system_box.currentText():
            self.message.information(self, 'Error', 'Coordinate system cannot be empty.')
            return

        if self.system_box.currentText() == 'UTM':
            zone_text = self.zone_number_box.currentText()

            if not zone_text:
                self.message.information(self, 'Error', 'Zone number cannot be empty.')
                return

            zone_number = int(re.findall('\d+', zone_text)[0])
            north = True if 'n' in zone_text.lower() else False

            for row in range(self.table.rowCount()):
                name = self.table.item(row, 0).text()
                desc = self.table.item(row, 1).text()
                try:
                    easting = int(float(self.table.item(row, 2).text()))
                    northing = int(float(self.table.item(row, 3).text()))
                except ValueError:
                    pass
                else:
                    # UTM converted to lat lon
                    lat, lon = utm.to_latlon(easting, northing, zone_number=zone_number, northern=north)
                    waypoint = src._legacy.gpx_module.gpxpy.gpx.GPXWaypoint(latitude=lat, longitude=lon, name=name, comment=desc)
                    gpx.waypoints.append(waypoint)

        elif self.system_box.currentText() == 'Lat/Lon':
            for row in range(self.table.rowCount()):
                name = self.table.item(row, 0).text()
                desc = self.table.item(row, 1).text()
                try:
                    lat = float(self.table.item(row, 2).text())
                    lon = float(self.table.item(row, 3).text())
                except ValueError:
                    pass
                else:
                    waypoint = src._legacy.gpx_module.gpxpy.gpx.GPXWaypoint(latitude=lat, longitude=lon, name=name, comment=desc)
                    gpx.waypoints.append(waypoint)

        with open(savepath, 'w') as f:
            f.write(gpx.to_xml())
        self.statusBar().showMessage('Save complete.', 2000)

        if self.open_file_cbox.isChecked():
            os.startfile(savepath)

    def toggle_utm_boxes(self):
        if self.system_box.currentText() == 'UTM':
            self.zone_number_box.setEnabled(True)
            self.zone_number_label.setEnabled(True)
        else:
            self.zone_number_box.setEnabled(False)
            self.zone_number_label.setEnabled(False)

    def reset(self):
        while self.table.rowCount() > 0:
            self.table.removeRow(0)
        self.system_box.setCurrentText('')
        self.zone_number_box.setCurrentText('')


def main():
    app = QApplication(sys.argv)

    gpx_creator = GPXCreator()
    gpx_creator.show()
    file = r'C:\Users\Eric\PycharmProjects\Crone\sample_files\PEMGetter files\gps.csv'
    gpx_creator.import_csv(file)
    gpx_creator.system_box.setCurrentText('UTM')
    # gpx_creator.datum_box.setCurrentText('WGS 1983')
    gpx_creator.zone_number_box.setCurrentText('37 North')
    # gpx_creator.export_gpx('sdfs')

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
