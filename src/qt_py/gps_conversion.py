from PySide2 import QtCore, QtGui
from PySide2.QtWidgets import (QWidget, QMessageBox)
from pyproj import CRS

from src.qt_py import icons_path
from src.logger import logger
from src.ui.gps_conversion import Ui_GPSConversion


class GPSConversionWidget(QWidget, Ui_GPSConversion):
    accept_signal = QtCore.Signal(int)

    def __init__(self, parent=None):
        super().__init__()
        self.setupUi(self)
        self.setWindowIcon(QtGui.QIcon(str(icons_path.joinpath("gpx_creator.png"))))
        self.parent = parent
        self.message = QMessageBox()

        self.convert_to_label.setText('')
        self.current_crs_label.setText('')

        self.init_signals()

    def init_signals(self):

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
                    zones = [''] + [f"{num} North" for num in range(1, 61)] + [f"{num} South" for num in range(1, 61)]

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
                    logger.critical(str(e))
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
                self.convert_to_label.setText(f"{crs.name} ({crs.type_name})")
            else:
                self.convert_to_label.setText('')

        # Add the GPS system and datum drop box options
        gps_systems = ['', 'Lat/Lon', 'UTM']
        for system in gps_systems:
            self.gps_system_cbox.addItem(system)

        datums = ['', 'WGS 1984', 'NAD 1927', 'NAD 1983']
        for datum in datums:
            self.gps_datum_cbox.addItem(datum)

        int_valid = QtGui.QIntValidator()
        self.epsg_edit.setValidator(int_valid)

        self.gps_system_cbox.currentIndexChanged.connect(toggle_gps_system)
        self.gps_system_cbox.currentIndexChanged.connect(set_epsg_label)
        self.gps_datum_cbox.currentIndexChanged.connect(toggle_gps_system)
        self.gps_datum_cbox.currentIndexChanged.connect(set_epsg_label)
        self.gps_zone_cbox.currentIndexChanged.connect(set_epsg_label)

        self.crs_rbtn.clicked.connect(toggle_crs_rbtn)
        self.crs_rbtn.clicked.connect(set_epsg_label)
        self.epsg_rbtn.clicked.connect(toggle_crs_rbtn)
        self.epsg_rbtn.clicked.connect(set_epsg_label)

        self.epsg_edit.editingFinished.connect(check_epsg)

        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.close)

    def closeEvent(self, e):
        self.deleteLater()
        e.accept()

    def accept(self):
        """
        Signal slot, emit the EPSG code.
        :return: int
        """
        epsg_code = self.get_epsg()
        if epsg_code:
            self.accept_signal.emit(int(epsg_code))
            self.close()
        else:
            logger.error(f"{epsg_code} is not a valid EPSG code.")
            self.message.information(self, 'Invalid CRS', 'The selected CRS is invalid.')

    def open(self, current_crs):
        self.current_crs_label.setText(f"{current_crs.name} ({current_crs.type_name})")
        self.show()

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
                    logger.error(f"{datum} to EPSG code has not been implemented.")
                    return None

                return epsg_code

        if self.epsg_rbtn.isChecked():
            epsg_code = self.epsg_edit.text()
        else:
            epsg_code = convert_to_epsg()

        return epsg_code