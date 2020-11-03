import copy
import csv
import datetime
import logging
import os
import re
import subprocess
import sys
from itertools import groupby
from pathlib import Path

import keyboard
import natsort
import numpy as np
import pandas as pd
import pyqtgraph as pg
import simplekml
import stopit
from PyQt5 import (QtCore, QtGui, uic)
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtWidgets import (QWidget, QMainWindow, QApplication, QDesktopWidget, QMessageBox, QFileDialog, QHeaderView,
                             QTableWidgetItem, QAction, QMenu, QGridLayout, QTextBrowser, QFileSystemModel, QHBoxLayout,
                             QInputDialog, QErrorMessage, QLabel, QLineEdit, QPushButton, QAbstractItemView,
                             QVBoxLayout, QCalendarWidget, QFormLayout, QCheckBox, QSizePolicy, QFrame, QGroupBox,
                             QComboBox, QListWidgetItem)
from matplotlib import pyplot as plt
from matplotlib.colors import LinearSegmentedColormap as LCMap
from pyproj import CRS

from src.mag_field.mag_dec_widget import MagDeclinationCalculator
from src.damp.db_plot import DBPlotter
from src.gps.gps_editor import (SurveyLine, TransmitterLoop, BoreholeCollar, BoreholeSegments, BoreholeGeometry,
                                GPSConversionWidget)
from src.gps.gpx_creator import GPXCreator
from src.pem.pem_file import PEMFile, PEMParser, DMPParser, StationConverter
from src.pem.pem_plotter import PEMPrinter
from src.qt_py.custom_qt_widgets import CustomProgressBar
from src.pem.derotator import Derotator
from src.qt_py.map_widgets import Map3DViewer, ContourMapViewer, TileMapViewer, GPSViewer
from src.qt_py.name_editor import BatchNameEditor
from src.geometry.pem_geometry import PEMGeometry
from src.qt_py.pem_info_widget import PEMFileInfoWidget
from src.pem.pem_merger import PEMMerger
from src.qt_py.pem_planner import LoopPlanner, GridPlanner
from src.pem.pem_plot_editor import PEMPlotEditor
from src.qt_py.ri_importer import BatchRIImporter
from src.pem.station_splitter import StationSplitter
from src.qt_py.unpacker import Unpacker

logger = logging.getLogger(__name__)

# Modify the paths for when the script is being run in a frozen state (i.e. as an EXE)
if getattr(sys, 'frozen', False):
    application_path = os.path.dirname(sys.executable)
    loopCalcUIFile = 'qt_ui\\loop_calculator.ui'
    icons_path = 'qt_ui\\icons'
else:
    application_path = os.path.dirname(os.path.abspath(__file__))
    loopCalcUIFile = os.path.join(os.path.dirname(application_path), 'qt_ui\\loop_calculator.ui')
    icons_path = os.path.join(os.path.dirname(application_path), "qt_ui\\icons")

# Load Qt ui file into a class
loopCalcUi, _ = uic.loadUiType(loopCalcUIFile)


class LoopCalculator(QMainWindow, loopCalcUi):

    def __init__(self):
        super().__init__()
        self.setupUi(self)

        self.show()


if __name__ == '__main__':
    lc = LoopCalculator()
