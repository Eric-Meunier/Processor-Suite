import logging
import logging
import os
import sys

import cartopy
import cartopy.crs as ccrs
from PyQt5 import (QtGui)
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (QWidget, QFrame, QMainWindow, QLabel, QPushButton, QFormLayout, QVBoxLayout)
from matplotlib import pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

logger = logging.getLogger(__name__)

# Modify the paths for when the script is being run in a frozen state (i.e. as an EXE)
if getattr(sys, 'frozen', False):
    application_path = os.path.dirname(sys.executable)
    icons_path = 'qt_ui\\icons'
else:
    application_path = os.path.dirname(os.path.abspath(__file__))
    icons_path = os.path.join(os.path.dirname(application_path), "qt_ui\\icons")


class MagDeclinationCalculator(QMainWindow):
    """
    Converts the first coordinates found into lat lon. Must have GPS information in order to convert to lat lon.
    """

    def __init__(self, parent=None):
        super().__init__()
        self.parent = parent
        self.setWindowTitle('Magnetic Declination')
        self.setWindowIcon(QIcon(os.path.join(icons_path, 'mag_field.png')))
        # self.setLayout(QVBoxLayout())
        self.resize(400, 400)
        self.status_bar = self.statusBar()

        self.pos_label = QLabel()
        self.status_bar.addPermanentWidget(self.pos_label)

        main_widget = QWidget()
        main_widget.setLayout(QVBoxLayout())
        main_widget.layout().setContentsMargins(0, 0, 0, 0)
        self.setCentralWidget(main_widget)

        frame = QFrame()
        frame.setLayout(QFormLayout())

        self.dec_edit = QPushButton()
        self.dec_edit.clicked.connect(lambda: self.copy_text(self.dec_edit.text()))
        self.inc_edit = QPushButton()
        self.inc_edit.clicked.connect(lambda: self.copy_text(self.inc_edit.text()))
        self.tf_edit = QPushButton()
        self.tf_edit.clicked.connect(lambda: self.copy_text(self.tf_edit.text()))

        frame.layout().addRow(QLabel('Declination (°)'), self.dec_edit)
        frame.layout().addRow(QLabel('Inclination (°)'), self.inc_edit)
        frame.layout().addRow(QLabel('Total Field (nT)'), self.tf_edit)
        main_widget.layout().addWidget(frame)

        self.figure = Figure()
        self.ax = None
        plt.subplots_adjust(left=0, right=100, top=100, bottom=0)
        canvas = FigureCanvas(self.figure)
        main_widget.layout().addWidget(canvas)

    def copy_text(self, str_value):
        """
        Copy the str_value to the clipboard
        :param str_value: str
        :return None
        """
        cb = QtGui.QApplication.clipboard()
        cb.clear(mode=cb.Clipboard)
        cb.setText(str_value, mode=cb.Clipboard)
        self.status_bar.showMessage(f"{str_value} copied to clipboard", 1000)

    def calc_mag_dec(self, pem_file):
        """
        Calculate the magnetic declination for the PEM file.
        :param pem_file: PEMFile object
        :return: None
        """

        if not pem_file:
            logger.warning(f"No PEM files passed.")
            return

        if not pem_file.get_crs():
            logger.warning(f"No CRS.")
            self.message.information(self, 'Error', 'GPS coordinate system information is invalid')
            return

        mag = pem_file.get_mag_dec()

        self.dec_edit.setText(f"{mag.dec:.2f}")
        self.inc_edit.setText(f"{mag.dip:.2f}")
        self.tf_edit.setText(f"{mag.ti:.2f}")
        self.pos_label.setText(f"Latitude: {mag.lat:5f}°  Longitude: {mag.lon:.5f}°")

        # Draw the globe map
        ax = self.figure.add_subplot(projection=ccrs.Orthographic(mag.lon, mag.lat))
        ax.plot(mag.lon, mag.lat, 'o', color='red', markeredgecolor='black', transform=ccrs.Geodetic())
        ax.add_feature(cartopy.feature.OCEAN, zorder=0)
        # ax.add_feature(cartopy.feature.COASTLINE, zorder=0, edgecolor='black', linewidth=0.8)
        ax.add_feature(cartopy.feature.LAND, zorder=0, edgecolor='black')
        ax.add_feature(cartopy.feature.BORDERS, zorder=0, edgecolor='gray', linewidth=0.5)

        ax.set_global()
        ax.gridlines(color='black', linewidth=0.4)
