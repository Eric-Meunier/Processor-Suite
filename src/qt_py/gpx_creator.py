import csv
import logging
import os
import sys
from pathlib import Path

import geopandas as gpd
import gpxpy
import pandas as pd
from PySide2 import QtGui, QtWidgets
from pyproj import CRS
from shapely.geometry import asMultiPoint
from src.ui.gpx_creator import Ui_GPXCreator

logger = logging.getLogger(__name__)

if getattr(sys, 'frozen', False):
    application_path = Path(sys.executable).parent
else:
    application_path = Path(__file__).absolute().parents[1]
icons_path = application_path.joinpath('ui\\icons')


class GPXCreator(QtWidgets.QMainWindow, Ui_GPXCreator):
    """
    Program to convert a CSV file into a GPX file. The datum of the intput GPS must be NAD 83 or WGS 84.
    Columns of the CSV must be 'Name', 'Comment', 'Easting', 'Northing'.
    """
    def __init__(self, parent=None):
        super().__init__()
        self.parent = parent
        self.setupUi(self)
        self.setWindowTitle("GPX Creator")
        self.setWindowIcon(
            QtGui.QIcon(os.path.join(icons_path, 'gpx_creator_4.svg')))

        self.dialog = QtWidgets.QFileDialog()
        self.message = QtWidgets.QMessageBox()
        self.setAcceptDrops(True)

        self.filepath = None

        # Status bar
        self.spacer_label = QtWidgets.QLabel()
        self.epsg_label = QtWidgets.QLabel()
        self.epsg_label.setIndent(5)

        # # Format the borders of the items in the status bar
        # self.setStyleSheet("QStatusBar::item {border-left: 1px solid gray; border-top: 1px solid gray}")
        # self.status_bar.setStyleSheet("border-top: 1px solid gray; border-top: None")

        self.status_bar.addPermanentWidget(self.spacer_label, 1)
        self.status_bar.addPermanentWidget(self.epsg_label, 0)

        # Actions
        self.del_file = QtWidgets.QAction("&Remove Row", self)
        self.del_file.setShortcut("Del")
        self.del_file.triggered.connect(self.remove_row)
        self.addAction(self.del_file)

        # Signals
        # Buttons
        self.openAction.triggered.connect(self.open_file_dialog)
        self.exportGPX.triggered.connect(self.export_gpx)
        self.create_csv_template_action.triggered.connect(self.create_csv_template)
        self.export_gpx_btn.clicked.connect(self.export_gpx)
        # self.auto_name_btn.clicked.connect(self.auto_name)

        self.init_crs()

    def init_crs(self):
        """
        Populate the CRS drop boxes and connect all their signals
        """

        def toggle_gps_system():
            """
            Toggle the datum and zone combo boxes and change their options based on the selected CRS system.
            """
            current_zone = self.gps_zone_cbox.currentText()
            datum = self.gps_datum_cbox.currentText()
            system = self.gps_system_cbox.currentText()

            if system == '':
                self.gps_zone_cbox.setEnabled(False)
                self.gps_datum_cbox.setEnabled(False)

            elif system == 'Lat/Lon':
                self.gps_datum_cbox.setCurrentText('WGS 1984')
                self.gps_zone_cbox.setCurrentText('')
                self.gps_datum_cbox.setEnabled(False)
                self.gps_zone_cbox.setEnabled(False)

            elif system == 'UTM':
                self.gps_datum_cbox.setEnabled(True)

                if datum == '':
                    self.gps_zone_cbox.setEnabled(False)
                    return
                else:
                    self.gps_zone_cbox.clear()
                    self.gps_zone_cbox.setEnabled(True)

                # NAD 27 and 83 only have zones from 1N to 22N/23N
                if datum == 'NAD 1927':
                    zones = [''] + [f"{num} North" for num in range(1, 23)] + ['59 North', '60 North']
                elif datum == 'NAD 1983':
                    zones = [''] + [f"{num} North" for num in range(1, 24)] + ['59 North', '60 North']
                # WGS 84 has zones from 1N and 1S to 60N and 60S
                else:
                    zones = [''] + [f"{num} North" for num in range(1, 61)] + [f"{num} South" for num in
                                                                               range(1, 61)]

                for zone in zones:
                    self.gps_zone_cbox.addItem(zone)

                # Keep the same zone number if possible
                self.gps_zone_cbox.setCurrentText(current_zone)

        def toggle_crs_rbtn():
            """
            Toggle the radio buttons for the project CRS box, switching between the CRS drop boxes and the EPSG edit.
            """
            if self.crs_rbtn.isChecked():
                # Enable the CRS drop boxes and disable the EPSG line edit
                self.gps_system_cbox.setEnabled(True)
                toggle_gps_system()

                self.epsg_edit.setEnabled(False)
            else:
                # Disable the CRS drop boxes and enable the EPSG line edit
                self.gps_system_cbox.setEnabled(False)
                self.gps_datum_cbox.setEnabled(False)
                self.gps_zone_cbox.setEnabled(False)

                self.epsg_edit.setEnabled(True)

        def check_epsg():
            """
            Try to convert the EPSG code to a Proj CRS object, reject the input if it doesn't work.
            """
            epsg_code = self.epsg_edit.text()
            self.epsg_edit.blockSignals(True)

            if epsg_code:
                try:
                    crs = CRS.from_epsg(epsg_code)
                except Exception as e:
                    self.message.critical(self, 'Invalid EPSG Code', f"{epsg_code} is not a valid EPSG code.")
                    self.epsg_edit.setText('')
                finally:
                    set_epsg_label()

            self.epsg_edit.blockSignals(False)

        def set_epsg_label():
            """
            Convert the current project CRS combo box values into the EPSG code and set the status bar label.
            """
            epsg_code = self.get_epsg()
            if epsg_code:
                crs = CRS.from_epsg(epsg_code)
                self.epsg_label.setText(f"{crs.name} ({crs.type_name})")
            else:
                self.epsg_label.setText('')

        # Add the GPS system and datum drop box options
        gps_systems = ['', 'Lat/Lon', 'UTM']
        for system in gps_systems:
            self.gps_system_cbox.addItem(system)

        datums = ['', 'WGS 1984', 'NAD 1927', 'NAD 1983']
        for datum in datums:
            self.gps_datum_cbox.addItem(datum)

        int_valid = QtGui.QIntValidator()
        self.epsg_edit.setValidator(int_valid)

        # Signals
        # Combo boxes
        self.gps_system_cbox.currentIndexChanged.connect(toggle_gps_system)
        self.gps_system_cbox.currentIndexChanged.connect(set_epsg_label)
        self.gps_datum_cbox.currentIndexChanged.connect(toggle_gps_system)
        self.gps_datum_cbox.currentIndexChanged.connect(set_epsg_label)
        self.gps_zone_cbox.currentIndexChanged.connect(set_epsg_label)

        # Radio buttons
        self.crs_rbtn.clicked.connect(toggle_crs_rbtn)
        self.crs_rbtn.clicked.connect(set_epsg_label)
        self.epsg_rbtn.clicked.connect(toggle_crs_rbtn)
        self.epsg_rbtn.clicked.connect(set_epsg_label)

        self.epsg_edit.editingFinished.connect(check_epsg)

    def closeEvent(self, e):
        self.deleteLater()
        e.accept()

    def dragEnterEvent(self, e):
        e.accept()

    def dropEvent(self, e):
        urls = [url.toLocalFile() for url in e.mimeData().urls()]
        self.open(urls[0])

    def dragMoveEvent(self, e):
        urls = [url.toLocalFile() for url in e.mimeData().urls()]
        if len(urls) == 1 and Path(urls[0]).suffix.lower() in ['.csv', '.xlsx']:
            e.accept()
        else:
            e.ignore()

    def open_file_dialog(self):
        """
        Open files through the file dialog
        """
        file = self.dialog.getOpenFileNames(self, 'Open File',
                                            filter='CSV files (*.csv);;'
                                                   'Excel files (*.xlsx)')[0]
        if file:
            self.open(file)
        else:
            pass

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
                filewriter.writerow(['Easting', 'Northing', 'Comment'])
                os.startfile(file)
        else:
            pass

    def get_epsg(self):
        """
        Return the EPSG code currently selected. Will convert the drop boxes to EPSG code.
        :return: str, EPSG code
        """

        def convert_to_epsg():
            """
            Convert and return the EPSG code of the project CRS combo boxes
            :return: str
            """
            system = self.gps_system_cbox.currentText()
            zone = self.gps_zone_cbox.currentText()
            datum = self.gps_datum_cbox.currentText()

            if system == '':
                return None

            elif system == 'Lat/Lon':
                return '4326'

            else:
                if not zone or not datum:
                    return None

                s = zone.split()
                zone_number = int(s[0])
                north = True if s[1] == 'North' else False

                if datum == 'WGS 1984':
                    if north:
                        epsg_code = f'326{zone_number:02d}'
                    else:
                        epsg_code = f'327{zone_number:02d}'
                elif datum == 'NAD 1927':
                    epsg_code = f'267{zone_number:02d}'
                elif datum == 'NAD 1983':
                    epsg_code = f'269{zone_number:02d}'
                else:
                    logger.info(f"CRS string not implemented.")
                    return None

                return epsg_code

        if self.epsg_rbtn.isChecked():
            epsg_code = self.epsg_edit.text()
        else:
            epsg_code = convert_to_epsg()

        return epsg_code

    def auto_name(self):
        """
        Append the Comment to the Name to create unique names
        """
        if self.table.rowCount() > 0:
            for row in range(self.table.rowCount()):
                name = self.table.item(row, 0).text()
                comment = self.table.item(row, 1).text()

                new_name = f"{name} - {comment}"
                item = QtWidgets.QTableWidgetItem(new_name)
                self.table.setItem(row, 0, item)

    def open(self, filepath):
        """
        Add the information from the CSV to the table.
        :param filepath: str, filepath of the CSV or text file to convert to GPX
        :return: None
        """

        def df_to_table(df):
            """
            Write the values in the data frame to the table.
            :param df: dataframe
            """
            self.table.setRowCount(df.shape[0])

            # getting data from df is computationally costly so convert it to array first
            df_array = df.values
            for row in range(df.shape[0]):
                for col in range(df.shape[1]):
                    value = df_array[row, col]
                    item = QtWidgets.QTableWidgetItem(str(value))

                    self.table.setItem(row, col, item)

        self.filepath = Path(filepath)

        if str(self.filepath).endswith('csv'):
            data = pd.read_csv(filepath)
        elif str(self.filepath).endswith('xlsx'):
            data = pd.read_excel(filepath)
        else:
            self.message.critical(self, 'Invalid file type', f"{self.filepath.name} is not a valid file.")
            return

        if not all([header in data.columns for header in ['Easting', 'Northing', 'Comment']]):
            self.message.information(self, f"Error parsing {filepath.name}",
                                     "The CSV data columns must have headers 'Easting', 'Northing', and 'Comment'")
            return

        data.loc[:, ['Easting', 'Northing']] = data.loc[:, ['Easting', 'Northing']].astype(float)
        data.loc[:, 'Comment'] = data.loc[:, 'Comment'].astype(str)
        df_to_table(data)

        logger.info(f'Opening {self.filepath.name}')
        self.status_bar.showMessage(f'Opened {self.filepath.name}', 2000)

    def export_gpx(self):
        """
        Save a GPX file from the information in the table.
        :return: None
        """

        def table_to_df():
            """
            Return a data frame from the information in the table
            :return: pandas DataFrame
            """
            gps = []
            for row in range(self.table.rowCount()):
                gps_row = list()
                for col in range(self.table.columnCount()):
                    gps_row.append(self.table.item(row, col).text())
                gps.append(gps_row)

            df = gpd.GeoDataFrame(gps, columns=['Easting', 'Northing', 'Comment'])
            df.loc[:, ['Easting', 'Northing']] = df.loc[:, ['Easting', 'Northing']].astype(float)
            return df

        def row_to_gpx(row):
            """
            Create a gpx waypoint object for each data row
            :param row: series, converted data row
            """
            waypoint = gpxpy.gpx.GPXWaypoint(latitude=row.Northing,
                                             longitude=row.Easting,
                                             name=f"{name}-{row.Comment}",
                                             comment=row.Comment)
            gpx.waypoints.append(waypoint)

        if not self.table.rowCount() > 0:
            return

        name = self.name_edit.text()
        if not name:
            self.message.critical(self, 'Empty name', 'A name must be given.')
            return

        epsg = self.get_epsg()
        if not epsg:
            self.message.critical(self, 'Invalid CRS', 'Input CRS is invalid.')
            return
        else:
            crs = CRS.from_epsg(epsg)

        self.status_bar.showMessage(f"Saving GPX file...")

        default_path = str(self.filepath.parent)
        file = self.dialog.getSaveFileName(self, 'Save File', default_path, filter='GPX file (*.gpx);;')[0]

        if not file:
            self.status_bar.showMessage('Cancelled', 2000)
            return

        logger.info(f"Saving {file}")

        gpx = gpxpy.gpx.GPX()

        # Create a data frame from the table
        data = table_to_df()

        # Create point objects for each coordinate
        mpoints = asMultiPoint(data.loc[:, ['Easting', 'Northing']].to_numpy())
        gdf = gpd.GeoSeries(list(mpoints), crs=crs)

        # Convert to lat lon
        converted_gdf = gdf.to_crs(epsg=4326)
        data['Easting'], data['Northing'] = converted_gdf.map(lambda p: p.x), converted_gdf.map(lambda p: p.y)

        # Create the GPX waypoints
        data.apply(row_to_gpx, axis=1)

        # Save the file
        with open(file, 'w') as f:
            f.write(gpx.to_xml())
        self.status_bar.showMessage('Save complete.', 2000)

        # Open the file
        if self.open_file_cbox.isChecked():
            try:
                os.startfile(file)
            except OSError:
                logger.error(f'No application to open {file}')
                pass


def main():
    app = QtWidgets.QApplication(sys.argv)

    gpx_creator = GPXCreator()
    gpx_creator.show()
    file = str(Path(__file__).parents[2].joinpath(r'sample_files\GPX files\testing file.csv'))
    gpx_creator.open(file)
    gpx_creator.name_edit.setText('Testing line')
    gpx_creator.gps_system_cbox.setCurrentText('UTM')
    gpx_creator.gps_datum_cbox.setCurrentText('WGS 1984')
    gpx_creator.gps_zone_cbox.setCurrentText('37 North')
    gpx_creator.export_gpx()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
