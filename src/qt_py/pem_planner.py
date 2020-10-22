import logging
import os
import sys
from pathlib import Path

import geopandas as gpd
import gpxpy
import math
import matplotlib.ticker as ticker
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import pyqtgraph as pg
import simplekml
from PyQt5 import QtGui, QtCore, uic
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import (QApplication, QMainWindow, QFileDialog, QShortcut, QLabel, QMessageBox, QInputDialog,
                             QLineEdit, QFormLayout, QWidget, QFrame)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from pyproj import CRS
from shapely.geometry import asMultiPoint

from src.qt_py.custom_qt_widgets import NonScientific
from src.mag_field.mag_field_calculator import MagneticFieldCalculator
from src.qt_py.map_widgets import MapboxViewer

logger = logging.getLogger(__name__)

# Modify the paths for when the script is being run in a frozen state (i.e. as an EXE)
if getattr(sys, 'frozen', False):
    application_path = os.path.dirname(sys.executable)
    loopPlannerCreatorFile = 'qt_ui\\loop_planner.ui'
    loopPlannerCreatorFile2 = 'qt_ui\\loop_planner2.ui'
    gridPlannerCreatorFile = 'qt_ui\\grid_planner.ui'
    icons_path = 'qt_ui\\icons'
else:
    application_path = os.path.dirname(os.path.abspath(__file__))
    loopPlannerCreatorFile = os.path.join(os.path.dirname(application_path), 'qt_ui\\loop_planner.ui')
    loopPlannerCreatorFile2 = os.path.join(os.path.dirname(application_path), 'qt_ui\\loop_planner2.ui')
    gridPlannerCreatorFile = os.path.join(os.path.dirname(application_path), 'qt_ui\\grid_planner.ui')
    icons_path = os.path.join(os.path.dirname(application_path), "qt_ui\\icons")

# Load Qt ui file into a class
Ui_LoopPlannerWindow, _ = uic.loadUiType(loopPlannerCreatorFile)
Ui_LoopPlannerWindow2, _ = uic.loadUiType(loopPlannerCreatorFile2)
Ui_GridPlannerWindow, _ = uic.loadUiType(gridPlannerCreatorFile)

pg.setConfigOptions(antialias=True)
pg.setConfigOption('background', 'w')
pg.setConfigOption('foreground', 'k')
pg.setConfigOption('crashWarning', True)


class SurveyPlanner(QMainWindow):
    """
    Base class for the LoopPlanner and GridPlanner
    """

    def __init__(self, parent=None):
        super().__init__()
        self.parent = parent

        self.setGeometry(200, 200, 1400, 700)
        self.dialog = QFileDialog()
        self.message = QMessageBox()

        self.save_shortcut = QShortcut(QtGui.QKeySequence("Ctrl+S"), self)
        self.copy_shortcut = QShortcut(QtGui.QKeySequence("Ctrl+C"), self)
        self.save_shortcut.activated.connect(self.save_img)
        self.copy_shortcut.activated.connect(self.copy_img)

        # Status bar
        self.spacer_label = QLabel()
        self.epsg_label = QLabel()
        self.epsg_label.setIndent(5)

        # Map viewer
        self.map_viewer = MapboxViewer(parent=self)

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
                    print(f"CRS string not implemented.")
                    return None

                return epsg_code

        if self.epsg_rbtn.isChecked():
            epsg_code = self.epsg_edit.text()
        else:
            epsg_code = convert_to_epsg()

        return epsg_code

    def copy_loop_to_clipboard(self):
        """
        Copy the loop corner coordinates to the clipboard.
        """

        epsg = self.get_epsg()
        if epsg:
            crs_str = CRS.from_epsg(self.get_epsg()).name
        else:
            crs_str = 'No CRS selected'

        result = crs_str + '\n'
        corners = self.get_loop_coords()
        for point in corners:
            easting = f"{point[0]:.0f} E"
            northing = f"{point[1]:.0f} N"
            result += easting + ', ' + northing + '\n'
        cb = QtGui.QApplication.clipboard()
        cb.clear(mode=cb.Clipboard)
        cb.setText(result, mode=cb.Clipboard)

        self.status_bar.show()
        self.status_bar.showMessage('Loop corner coordinates copied to clipboard.', 1000)
        QTimer.singleShot(1000, lambda: self.status_bar.hide())

    def save_img(self):
        save_name, save_type = QFileDialog.getSaveFileName(self, 'Save Image',
                                                           'map.png',
                                                           'PNG file (*.PNG)'
                                                           )
        if save_name:
            self.grab().save(save_name)

    def copy_img(self):
        QApplication.clipboard().setPixmap(self.grab())


class HoleWidget(QWidget):
    name_changed_sig = QtCore.pyqtSignal()

    def __init__(self, info, name=''):
        """
        Widget representing a hole as tab in Loop Planner.
        :param info: dict, properties of a previous hole to be used as a starting point.
        """
        super().__init__()

        layout = QFormLayout()
        self.setLayout(layout)

        if not info:
            info = {
                'easting': 599709,
                'northing': 4829107,
                'elevation': 0,
                'azimuth': 0,
                'dip': 60,
                'length': 400,
            }

        # Create all the inner widget items
        self.hole_easting_edit = QLineEdit(str(int(info.get('easting'))))
        self.hole_northing_edit = QLineEdit(str(int(info.get('northing'))))
        self.hole_elevation_edit = QLineEdit(str(int(info.get('elevation'))))
        self.hole_azimuth_edit = QLineEdit(str(int(info.get('azimuth'))))
        self.hole_dip_edit = QLineEdit(str(int(info.get('dip'))))
        self.hole_length_edit = QLineEdit(str(int(info.get('length'))))
        self.hole_name_edit = QLineEdit(name)
        self.hole_name_edit.setPlaceholderText('(Optional)')

        # Add the widgets to the layout
        self.layout().addRow('Easting', self.hole_easting_edit)
        self.layout().addRow('Northing', self.hole_northing_edit)
        self.layout().addRow('Elevation\nFrom Loop', self.hole_elevation_edit)
        self.layout().addRow('Azimuth', self.hole_azimuth_edit)
        self.layout().addRow('Dip', self.hole_dip_edit)
        self.layout().addRow('Length', self.hole_length_edit)

        # Create the horizontal line for the header
        h_line = QFrame()
        h_line.setFrameShape(QFrame().HLine)
        h_line.setFrameShadow(QFrame().Sunken)
        self.layout().addRow(h_line)

        self.layout().addRow('Name', self.hole_name_edit)

        # Validators
        self.int_validator = QtGui.QIntValidator()
        self.size_validator = QtGui.QIntValidator()
        self.size_validator.setBottom(1)
        self.az_validator = QtGui.QIntValidator()
        self.az_validator.setRange(0, 360)
        self.dip_validator = QtGui.QIntValidator()
        self.dip_validator.setRange(0, 90)

        # Set all validators
        self.hole_easting_edit.setValidator(self.size_validator)
        self.hole_northing_edit.setValidator(self.size_validator)
        self.hole_elevation_edit.setValidator(self.int_validator)
        self.hole_azimuth_edit.setValidator(self.az_validator)
        self.hole_dip_edit.setValidator(self.dip_validator)
        self.hole_length_edit.setValidator(self.size_validator)

        # Plotting
        self.select_pen = pg.mkPen('b', width=2.)
        self.deselect_pen = pg.mkPen('k', width=1.)

        self.hole_collar = pg.ScatterPlotItem(clickable=True,
                                              symbol='o',
                                              brush=pg.mkBrush('w')
                                              )
        self.hole_collar.setZValue(10)
        self.hole_collar.sigClicked.connect(self.select)
        self.hole_trace = pg.PlotCurveItem()

        self.draw_hole()

        # Signals
        self.hole_name_edit.textChanged.connect(self.name_changed_sig.emit)
        self.hole_easting_edit.editingFinished.connect(self.draw_hole)
        self.hole_northing_edit.editingFinished.connect(self.draw_hole)
        self.hole_elevation_edit.editingFinished.connect(self.draw_hole)
        self.hole_azimuth_edit.editingFinished.connect(self.draw_hole)
        self.hole_dip_edit.editingFinished.connect(self.draw_hole)
        self.hole_length_edit.editingFinished.connect(self.draw_hole)

    def draw_hole(self):
        """
        Draw the hole in the plan view.
        """
        self.hole_collar.setData([int(self.hole_easting_edit.text())], [int(self.hole_northing_edit.text())])

    def select(self):
        print(f'Hole collar clicked.')
        self.hole_collar.setPen(self.select_pen)
        self.hole_collar.setSize(14)

    def deselect(self):
        print(f'Hole collar deselect.')
        self.hole_collar.setPen(self.deselect_pen)
        self.hole_collar.setSize(12)

    def get_info(self):
        """Return a dictionary of hole properties"""
        return {
            'easting': self.hole_easting_edit.text(),
            'northing': self.hole_northing_edit.text(),
            'elevation': self.hole_elevation_edit.text(),
            'azimuth': self.hole_azimuth_edit.text(),
            'dip': self.hole_dip_edit.text(),
            'length': self.hole_length_edit.text(),
        }


class LoopWidget(QWidget):
    name_changed_sig = QtCore.pyqtSignal()
    plot_hole_sig = QtCore.pyqtSignal()

    def __init__(self, info, pos, name=''):
        """
        Widget representing a loop as tab in Loop Planner.
        :param info: dict, properties of a previous loop to be used as a starting point.
        :param pos: tuple of int, centre position of the loop ROI.
        :param name: str, name of the loop.
        """
        super().__init__()

        layout = QFormLayout()
        self.setLayout(layout)

        if not info:
            info = {
                'height': 500,
                'width': 500,
                'angle': 0,
            }

        # Create all the inner widget items
        self.loop_height_edit = QLineEdit(str(int(info.get('height'))))
        self.loop_width_edit = QLineEdit(str(int(info.get('width'))))
        self.loop_angle_edit = QLineEdit(str(int(info.get('angle'))))

        self.loop_name_edit = QLineEdit(name)
        self.loop_name_edit.setPlaceholderText('(Optional)')

        # Add the widgets to the layout
        self.layout().addRow('Height', self.loop_height_edit)
        self.layout().addRow('Width', self.loop_width_edit)
        self.layout().addRow('Angle', self.loop_angle_edit)

        # Create the horizontal line for the header
        h_line = QFrame()
        h_line.setFrameShape(QFrame().HLine)
        h_line.setFrameShadow(QFrame().Sunken)
        self.layout().addRow(h_line)

        self.layout().addRow('Name', self.loop_name_edit)

        # Validators
        self.int_validator = QtGui.QIntValidator()
        self.size_validator = QtGui.QIntValidator()
        self.size_validator.setBottom(1)
        self.loop_angle_validator = QtGui.QIntValidator()
        self.loop_angle_validator.setRange(0, 360)

        # Set all validators
        self.loop_height_edit.setValidator(self.size_validator)
        self.loop_width_edit.setValidator(self.size_validator)
        self.loop_angle_edit.setValidator(self.int_validator)

        # Loop ROI
        #TODO PolyLineROI
        self.selected_pen = pg.mkPen('b', width=2.)
        self.unselected_pen = pg.mkPen('k', width=1.)

        self.loop_roi = LoopROI(pos,
                                size=(int(info.get('height')), int(info.get('height'))),
                                scaleSnap=True,
                                pen=self.unselected_pen,
                                centered=True)

        self.loop_roi.setZValue(-10)
        self.loop_roi.addScaleHandle([0, 0], [0.5, 0.5], lockAspect=True)
        self.loop_roi.addScaleHandle([1, 0], [0.5, 0.5], lockAspect=True)
        self.loop_roi.addScaleHandle([1, 1], [0.5, 0.5], lockAspect=True)
        self.loop_roi.addScaleHandle([0, 1], [0.5, 0.5], lockAspect=True)
        self.loop_roi.addRotateHandle([1, 0.5], [0.5, 0.5])
        self.loop_roi.addRotateHandle([0.5, 0], [0.5, 0.5])
        self.loop_roi.addRotateHandle([0.5, 1], [0.5, 0.5])
        self.loop_roi.addRotateHandle([0, 0.5], [0.5, 0.5])
        self.loop_roi.setAcceptedMouseButtons(QtCore.Qt.LeftButton)

        # Signals
        self.loop_name_edit.textChanged.connect(self.name_changed_sig.emit)
        self.loop_roi.sigRegionChangeStarted.connect(self.update_loop_values)
        self.loop_roi.sigClicked.connect(self.select)

    def select(self):
        """When the loop is selected"""
        self.loop_roi.setPen(self.selected_pen)

    def deselect(self):
        self.loop_roi.setPen(self.unselected_pen)

    def update_loop_values(self):
        """
        Signal slot: Updates the values of the loop width, height and angle when the loop ROI is changed, then
        replots the section plot.
        :return: None
        """
        self.select()
        self.loop_width_edit.blockSignals(True)
        self.loop_height_edit.blockSignals(True)
        self.loop_angle_edit.blockSignals(True)
        x, y = self.loop_roi.pos()
        w, h = self.loop_roi.size()
        angle = self.loop_roi.angle()
        self.loop_width_edit.setText(f"{w:.0f}")
        self.loop_height_edit.setText(f"{h:.0f}")
        self.loop_angle_edit.setText(f"{angle:.0f}")
        self.loop_width_edit.blockSignals(False)
        self.loop_height_edit.blockSignals(False)
        self.loop_angle_edit.blockSignals(False)

        self.plot_hole_sig.emit()

    def get_info(self):
        """Return a dictionary of loop properties"""
        return {
            'height': self.loop_height_edit.text(),
            'width': self.loop_width_edit.text(),
            'angle': self.loop_angle_edit.text(),
        }


class LoopPlanner2(SurveyPlanner, Ui_LoopPlannerWindow2):
    """
    Program that plots the magnetic field projected to a plane perpendicular to a borehole for a interactive loop.
    Loop and borehole collar can be exported as KMZ or GPX files.
    """

    def __init__(self, parent=None):
        super().__init__()
        self.setupUi(self)
        self.parent = parent

        self.setWindowTitle('Loop Planner')
        self.setWindowIcon(QtGui.QIcon(os.path.join(icons_path, 'loop_planner.png')))
        self.setGeometry(200, 200, 1400, 700)

        # Status bar
        self.status_bar.addPermanentWidget(self.spacer_label, 1)
        self.status_bar.addPermanentWidget(self.epsg_label, 0)

        # Plotting
        self.loop_widgets = []
        self.hole_widgets = []

        self.loop_plot_items = []
        self.hole_plot_items = []

        self.hole_traces = []  #pg.PlotDataItem()
        self.hole_collars = []  #pg.ScatterPlotItem()
        self.section_extent_lines = []  #pg.PlotDataItem()

        self.section_figure = Figure()
        self.ax = self.section_figure.add_subplot()
        self.section_canvas = FigureCanvas(self.section_figure)
        self.section_view_layout.addWidget(self.section_canvas)

        self.selected_hole = None
        self.selected_loop = None

        self.add_hole('Hole')
        self.add_loop('Loop')

        self.add_hole_btn.clicked.connect(self.add_hole)
        self.add_loop_btn.clicked.connect(self.add_loop)

        def hole_tab_changed(ind):
            print(f"Hole tab {ind} selected")
            self.selected_hole = self.hole_widgets[ind]
            self.selected_hole.select()

        def loop_tab_changed(ind):
            print(f"Loop tab {ind} selected")
            self.selected_loop = self.hole_widgets[ind]
            self.selected_loop.select()

        self.hole_tab_widget.currentChanged.connect(hole_tab_changed)
        self.loop_tab_widget.currentChanged.connect(loop_tab_changed)

        self.init_plan_view()
        # self.init_section_view()
        #
        # self.plot_hole()
        # self.plan_view.autoRange()

        # self.init_signals()
        self.init_crs()

    def add_hole(self, name=None):
        """
        Create tab for a new hole
        :param name: str, name of the hole
        """

        def name_changed(widget):
            """
            Rename the tab name when the hole name is changed.
            :param widget: Hole widget
            """
            ind = self.hole_widgets.index(widget)
            self.hole_tab_widget.setTabText(ind, widget.hole_name_edit.text())

        def hole_clicked(widget):
            """
            De-select all other holes.
            :param widget: The hole widget that was clicked
            """
            for w in self.hole_widgets:
                if w != widget:
                    w.deselect()

        if not name:
            name, ok_pressed = QInputDialog.getText(self, "Add Hole", "Hole name:", QLineEdit.Normal, "")
            if not ok_pressed:
                return

        if name != '':
            # Copy the information from the currently selected hole widget to be used in the new widget
            if self.hole_widgets:
                info = self.hole_widgets[self.hole_tab_widget.currentIndex()].get_info()
            else:
                info = None

            # Create the hole widget for the tab
            hole_widget = HoleWidget(info, name=name)
            self.hole_widgets.append(hole_widget)
            hole_widget.name_changed_sig.connect(lambda: name_changed(hole_widget))
            hole_widget.hole_collar.sigClicked.connect(lambda: hole_clicked(hole_widget))
            self.hole_tab_widget.addTab(hole_widget, name)

            self.plan_view.addItem(hole_widget.hole_collar)
            self.plan_view.addItem(hole_widget.hole_trace)

    def add_loop(self, name=None):
        """
        Create tab for a new loop
        :param name: str, name of the loop
        """

        def name_changed(widget):
            """
            Rename the tab name when the loop name is changed.
            :param widget: Loop widget
            """
            ind = self.hole_widgets.index(widget)
            self.hole_tab_widget.setTabText(ind, widget.hole_name_edit.text())

        def loop_clicked(widget):
            """
            De-select all other loops.
            :param widget: The loop widget that was clicked
            """
            for w in self.loop_widgets:
                if w != widget:
                    w.deselect()

        if not name:
            name, ok_pressed = QInputDialog.getText(self, "Add Loop", "Loop name:", QLineEdit.Normal, "")
            if not ok_pressed:
                return

        if name != '':
            # Copy the information from the currently selected hole widget to be used in the new widget
            if self.loop_widgets:
                info = self.loop_widgets[self.loop_tab_widget.currentIndex()].get_info()
            else:
                info = None

            # Create the loop widget for the tab
            pos = self.plan_view.viewRect().center()
            loop_widget = LoopWidget(info, pos, name=name)
            self.loop_widgets.append(loop_widget)

            # Connect signals
            loop_widget.name_changed_sig.connect(lambda: name_changed(loop_widget))
            loop_widget.plot_hole_sig.connect(self.plot_hole)
            loop_widget.loop_roi.sigClicked.connect(lambda: loop_clicked(loop_widget))
            loop_widget.loop_roi.sigRegionChangeStarted.connect(lambda: loop_clicked(loop_widget))

            self.loop_tab_widget.addTab(loop_widget, name)

            # Add the loop ROI to the plan view
            self.plan_view.addItem(loop_widget.loop_roi)

    def init_signals(self):

        def change_loop_width():
            """
            Signal slot: Change the loop ROI dimensions from user input
            :return: None
            """
            height = self.loop_roi.size()[1]
            width = self.loop_width_edit.text()
            width = float(width)
            logger.info(f"Loop width changed to {width}.")
            self.loop_roi.setSize((width, height))

        def change_loop_height():
            """
            Signal slot: Change the loop ROI dimensions from user input
            :return: None
            """
            height = self.loop_height_edit.text()
            width = self.loop_roi.size()[0]
            height = float(height)
            logger.info(f"Loop height changed to {height}.")
            self.loop_roi.setSize((width, height))

        def change_loop_angle():
            """
            Signal slot: Change the loop ROI angle from user input
            :return: None
            """
            angle = self.loop_angle_edit.text()
            angle = float(angle)
            logger.info(f"Loop angle changed to {angle}.")
            self.loop_roi.setAngle(angle)

        # Menu
        self.actionSave_as_KMZ.triggered.connect(self.save_kmz)
        self.actionSave_as_KMZ.setIcon(QtGui.QIcon(os.path.join(icons_path, 'google_earth.png')))
        self.actionSave_as_GPX.triggered.connect(self.save_gpx)
        self.actionSave_as_GPX.setIcon(QtGui.QIcon(os.path.join(icons_path, 'garmin_file.png')))
        # self.view_map_action.setDisabled(True)
        self.view_map_action.triggered.connect(self.view_map)
        self.view_map_action.setIcon(QtGui.QIcon(os.path.join(icons_path, 'folium.png')))
        self.actionCopy_Loop_to_Clipboard.triggered.connect(self.copy_loop_to_clipboard)

        # Line edits
        self.loop_height_edit.editingFinished.connect(change_loop_height)
        self.loop_width_edit.editingFinished.connect(change_loop_width)
        self.loop_angle_edit.editingFinished.connect(change_loop_angle)

        self.hole_easting_edit.editingFinished.connect(self.plot_hole)
        self.hole_northing_edit.editingFinished.connect(self.plot_hole)
        self.hole_elevation_edit.editingFinished.connect(self.plot_hole)
        self.hole_az_edit.editingFinished.connect(self.plot_hole)
        self.hole_dip_edit.editingFinished.connect(self.plot_hole)
        self.hole_length_edit.editingFinished.connect(self.plot_hole)

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
                    logger.error(f"Invalid EPSG code: {epsg_code}.")
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

        self.gps_system_cbox.setCurrentIndex(2)
        self.gps_datum_cbox.setCurrentIndex(1)
        self.gps_zone_cbox.setCurrentIndex(17)

    def init_plan_view(self):
        """
        Initial set-up of the plan view. Creates the plot widget, custom axes for the Y and X axes, and adds the loop ROI.
        :return: None
        """
        self.plan_view.setAxisItems({'left': NonScientific(orientation='left'),
                                     'bottom': NonScientific(orientation='bottom')})
        self.plan_view.showGrid(x=True, y=True, alpha=0.2)
        self.plan_view.getViewBox().disableAutoRange('xy')
        self.plan_view.setAspectLocked()
        self.plan_view.hideButtons()
        self.plan_view.setLabel('left', 'Northing', units='m')
        self.plan_view.setLabel('bottom', 'Easting', units='m')
        self.plan_view.getAxis('left').enableAutoSIPrefix(enable=False)
        self.plan_view.getAxis('bottom').enableAutoSIPrefix(enable=False)
        self.plan_view.getAxis('right').setWidth(15)
        self.plan_view.getAxis('bottom').setHeight(45)
        self.plan_view.getAxis('top').setHeight(15)
        self.plan_view.getAxis('right').setStyle(showValues=False)  # Disable showing the values of axis
        self.plan_view.getAxis('top').setStyle(showValues=False)  # Disable showing the values of axis
        self.plan_view.showAxis('right', show=True)  # Show the axis edge line
        self.plan_view.showAxis('top', show=True)  # Show the axis edge line
        self.plan_view.showLabel('right', show=False)
        self.plan_view.showLabel('top', show=False)

    def init_section_view(self):
        """
        Initial set-up of the section plot. Sets the axes to have equal aspect ratios.
        :return: None
        """
        self.ax.set_aspect('equal')
        self.ax.use_sticky_edges = False  # So the plot doesn't re-size after the first time it's plotted
        self.ax.spines['top'].set_visible(False)
        self.ax.spines['left'].set_visible(False)
        self.ax.spines['right'].set_visible(False)
        self.ax.spines['bottom'].set_visible(False)
        self.ax.get_xaxis().set_visible(False)
        self.ax.yaxis.set_major_formatter(ticker.StrMethodFormatter('{x:.0f}'))
        self.ax.figure.subplots_adjust(left=0.1, bottom=0.1, right=1., top=1.)

    def plot_hole(self):
        """
        Plots the hole on the plan plot and section plot, and plots the vector magnetic field on the section plot.
        :return: None
        """

        def get_hole_projection():
            """
            Calculates the 3D projection of the hole.
            :return: list of (x, y, z) tuples of the 3D hole trace.
            """
            x, y, z = self.hole_easting, self.hole_northing, self.hole_elevation
            delta_surf = self.hole_length * math.cos(math.radians(self.hole_dip))
            dx = delta_surf * math.sin(math.radians(self.hole_az))
            dy = delta_surf * math.cos(math.radians(self.hole_az))
            dz = self.hole_length * math.sin(math.radians(self.hole_dip))
            x = [x, self.hole_easting + dx]
            y = [y, self.hole_northing + dy]
            z = [z, self.hole_elevation + dz]
            return x, y, z

        def get_section_extents(x, y, z):
            """
            Calculates the two coordinates to be used for the section plot.
            :param x: list, hole projection x values
            :param y: list, hole projection y values
            :param z: list, hole projection z values
            :return: (x, y) tuples of the two end-points.
            """
            # Remove the previously plotted section line
            self.section_extent_line.clear()

            # Calculate the length of the cross-section
            line_len = math.ceil(self.hole_length / 400) * 400

            # Find the coordinate that is 80% down the hole
            if 90 < self.hole_az < 180:
                line_center_x = np.percentile(x, 80)
                line_center_y = np.percentile(y, 20)
            elif 180 < self.hole_az < 270:
                line_center_x = np.percentile(x, 20)
                line_center_y = np.percentile(y, 20)
            elif 270 < self.hole_az < 360:
                line_center_x = np.percentile(x, 20)
                line_center_y = np.percentile(y, 80)
            else:
                line_center_x = np.percentile(x, 80)
                line_center_y = np.percentile(y, 80)

            # # Plot the center point to see if it's working properly
            # self.hole_line_center.setData([line_center_x], [line_center_y], pen=pg.mkPen(width=2, color=0.4))
            # self.plan_view.addItem(self.hole_line_center)

            # Calculate the end point coordinates of the section line
            dx = math.sin(math.radians(self.hole_az)) * (line_len / 2)
            dy = math.cos(math.radians(self.hole_az)) * (line_len / 2)
            p1 = (line_center_x - dx, line_center_y - dy)
            p2 = (line_center_x + dx, line_center_y + dy)

            # Plot the section line
            self.section_extent_line.setData([line_center_x - dx, line_center_x + dx],
                                             [line_center_y - dy, line_center_y + dy],
                                             width=1,
                                             pen=pg.mkPen(color=0.5,
                                                          style=QtCore.Qt.DashLine))
            self.plan_view.addItem(self.section_extent_line)

            return p1, p2

        def plot_hole_section(p1, p2, hole_projection):
            """
            Plot the hole trace in the section plot.
            :param p1: (x, y) tuple: Coordinate of one end of the section's extent.
            :param p2: (x, y) tuple: Coordinate of the other end of the section's extent.
            :param hole_projection: list of (x, y, z) tuples: 3D projection of the borehole geometry.
            :return: None
            """

            def get_magnitude(vector):
                return math.sqrt(sum(i ** 2 for i in vector))

            p = np.array([p1[0], p1[1], 0])
            vec = [p2[0] - p1[0], p2[1] - p1[1], 0]
            planeNormal = np.cross(vec, [0, 0, -1])
            planeNormal = planeNormal / get_magnitude(planeNormal)

            plotx = []
            plotz = []

            # Projecting the 3D trace to a 2D plane
            for coordinate in hole_projection:
                q = np.array(coordinate)
                q_proj = q - np.dot(q - p, planeNormal) * planeNormal
                distvec = np.array([q_proj[0] - p[0], q_proj[1] - p[1]])
                dist = np.sqrt(distvec.dot(distvec))

                plotx.append(dist)
                plotz.append(q_proj[2])

            # Plot the collar
            self.ax.plot(plotx[0], plotz[0], 'o',
                         mfc='w',
                         markeredgecolor='dimgray',
                         zorder=10)
            # Plot the hole section line
            self.ax.plot(plotx, plotz,
                         color='dimgray',
                         lw=1,
                         zorder=1)
            self.ax.axhline(y=0,
                            color='dimgray', lw=0.6,
                            zorder=9)

        def plot_mag(c1, c2):
            """
            Plots the magnetic vector quiver plot in the section plot.
            :param c1: (x, y, z) tuple: Corner of the 2D section to plot the mag on.
            :param c2: (x, y, z) tuple: Opposite corner of the 2D section to plot the mag on.
            :return: None
            """
            wire_coords = self.get_loop_coords()
            mag_calculator = MagneticFieldCalculator(wire_coords)
            xx, yy, zz, uproj, vproj, wproj, plotx, plotz, arrow_len = mag_calculator.get_2d_magnetic_field(c1, c2)
            self.ax.quiver(xx, zz, plotx, plotz,
                           color='dimgray',
                           label='Field',
                           pivot='middle',
                           zorder=0,
                           units='dots',
                           scale=.050,
                           width=.8,
                           headlength=11,
                           headwidth=6)

        def plot_trace(xs, ys):
            """
            Plot the hole trace on the plan view plot.
            :param xs: list: X values to plot
            :param ys: list: Y values to plot
            :return: None
            """
            self.hole_trace.setData(xs, ys, pen=pg.mkPen(width=2, color=0.5))
            self.hole_collar.setData([self.hole_easting], [self.hole_northing],
                                     pen=pg.mkPen(width=3, color=0.5))
            self.plan_view.addItem(self.hole_trace)
            self.plan_view.addItem(self.hole_collar)

        def shift_loop(dx, dy):
            """
            Moves the loop ROI so it is in the same position relative to the grid.
            :param dx: Shift amount in x axis
            :param dy: Shift amount in y axis
            :return: None
            """
            self.loop_roi.blockSignals(True)
            x, y = self.loop_roi.pos()
            self.loop_roi.setPos(x + dx, y + dy)
            self.loop_roi.blockSignals(False)

        self.hole_easting = int(self.hole_easting_edit.text())
        self.hole_northing = int(self.hole_northing_edit.text())
        self.hole_elevation = int(self.hole_elevation_edit.text())
        self.hole_az = int(self.hole_az_edit.text())
        self.hole_dip = -int(self.hole_dip_edit.text())
        self.hole_length = int(self.hole_length_edit.text())

        self.hole_trace.clear()
        self.hole_collar.clear()
        self.ax.clear()

        xs, ys, zs = get_hole_projection()
        p1, p2 = get_section_extents(xs, ys, zs)

        plot_trace(xs, ys)
        plot_hole_section(p1, p2, list(zip(xs, ys, zs)))

        # Get the corners of the 2D section to plot the mag on
        c1, c2 = list(p1), list(p2)
        c1.append(max(self.ax.get_ylim()[1], 0))  # Add the max Z
        c2.append(self.ax.get_ylim()[0])  # Add the min Z
        plot_mag(c1, c2)

        self.section_canvas.draw()

    def get_loop_coords(self):
        """
        Return the coordinates of the loop corners
        :return: list of (x, y, z)
        """
        x, y = self.loop_roi.pos()
        w, h = self.loop_roi.size()
        angle = self.loop_roi.angle()
        c1 = (x, y, 0)
        c2 = (c1[0] + w * (math.cos(math.radians(angle))), c1[1] + w * (math.sin(math.radians(angle))), 0)
        c3 = (c2[0] - h * (math.sin(math.radians(angle))), c2[1] + h * (math.sin(math.radians(90-angle))), 0)
        c4 = (c3[0] + w * (math.cos(math.radians(180-angle))), c3[1] - w * (math.sin(math.radians(180-angle))), 0)
        corners = [c1, c2, c3, c4]

        return corners

    def get_loop_lonlat(self):
        """
        Return the lat lon data frame of the loop corners
        :return: dataframe
        """
        epsg = self.get_epsg()

        if not epsg:
            self.message.critical(self, 'Invalid CRS', 'Input CRS is invalid.')
            return pd.DataFrame()
        else:
            crs = CRS.from_epsg(epsg)

        # Get the loop data
        loop = pd.DataFrame(self.get_loop_coords(), columns=['Easting', 'Northing', 'Elevation'])
        loop = loop.append(loop.iloc[0])  # Close the loop

        # Create point objects for each coordinate
        mpoints = asMultiPoint(loop.loc[:, ['Easting', 'Northing']].to_numpy())
        gdf = gpd.GeoSeries(list(mpoints), crs=crs)

        # Convert to lat lon
        converted_gdf = gdf.to_crs(epsg=4326)
        loop['Easting'], loop['Northing'] = converted_gdf.map(lambda p: p.x), converted_gdf.map(lambda p: p.y)

        return loop

    def get_collar_lonlat(self):
        """
        Return the lat lon data frame of the hole collar
        :return: dataframe
        """
        epsg = self.get_epsg()

        if not epsg:
            self.message.critical(self, 'Invalid CRS', 'Input CRS is invalid.')
            return pd.DataFrame()
        else:
            crs = CRS.from_epsg(epsg)

        # Add the collar coordinates to the GPX as a waypoint.
        hole = pd.DataFrame(columns=['Easting', 'Northing'])
        hole.loc[0] = [self.hole_easting, self.hole_northing]

        # Create point objects for each coordinate
        mpoints = asMultiPoint(hole.loc[:, ['Easting', 'Northing']].to_numpy())
        gdf = gpd.GeoSeries(list(mpoints), crs=crs)

        # Convert to lat lon
        converted_gdf = gdf.to_crs(epsg=4326)
        hole['Easting'], hole['Northing'] = converted_gdf.map(lambda p: p.x), converted_gdf.map(lambda p: p.y)
        return hole

    def view_map(self):
        """
        View the hole and loop in a Plotly mapbox interactive map. A screen capture of the map can be
        saved with 'Ctrl+S' or copied to the clipboard with 'Ctrl+C'
        """
        global terrain_map
        terrain_map = MapboxViewer()

        loop_coords = self.get_loop_lonlat()
        collar = self.get_collar_lonlat()

        if loop_coords.empty and collar.empty:
            logger.error(f"No GPS to plot.")
            return

        hole_name = 'Hole' if self.hole_name_edit.text() == '' else self.hole_name_edit.text()
        loop_name = 'Loop' if self.loop_name_edit.text() == '' else self.loop_name_edit.text()

        terrain_map.map_figure.add_trace(go.Scattermapbox(lon=collar.Easting,
                                                          lat=collar.Northing,
                                                          mode='markers',
                                                          name=hole_name,
                                                          text=hole_name
                                                          ))

        terrain_map.map_figure.add_trace(go.Scattermapbox(lon=loop_coords.Easting,
                                                          lat=loop_coords.Northing,
                                                          mode='lines+markers',
                                                          name=loop_name,
                                                          text=loop_coords.index
                                                          ))

        # Pass the mapbox token, for access to better map tiles. If none is passed, it uses the free open street map.
        token = open(".mapbox", 'r').read()
        if not token:
            logger.warning(f"No Mapbox token passed.")
            map_style = "open-street-map"
        else:
            map_style = "outdoors"

        # Format the figure margins and legend
        terrain_map.map_figure.update_layout(
            margin={"r": 0,
                    "t": 0,
                    "l": 0,
                    "b": 0},
            legend=dict(
                yanchor="top",
                y=0.99,
                xanchor="left",
                x=0.01,
                bordercolor="Black",
                borderwidth=1
            ),
        )
        # Add the map style and center/zoom the map
        terrain_map.map_figure.update_layout(
            mapbox={
                'center': {'lon': loop_coords.Easting.mean(), 'lat': loop_coords.Northing.mean()},
                'zoom': 13},
            mapbox_style=map_style,
            mapbox_accesstoken=token)

        terrain_map.load_page()
        terrain_map.show()

    def save_kmz(self):
        """
        Save the loop and hole collar to a KMZ file.
        :return: None
        """

        kml = simplekml.Kml()

        loop_style = simplekml.Style()
        loop_style.linestyle.width = 4
        loop_style.linestyle.color = simplekml.Color.yellow

        trace_style = simplekml.Style()
        trace_style.linestyle.width = 2
        trace_style.linestyle.color = simplekml.Color.magenta

        collar_style = simplekml.Style()
        collar_style.iconstyle.icon.href = 'http://maps.google.com/mapfiles/kml/paddle/wht-stars.png'
        collar_style.iconstyle.color = simplekml.Color.magenta

        hole_name = self.hole_name_edit.text()
        if not hole_name:
            hole_name = 'Hole'
        folder = kml.newfolder(name=hole_name)
        loop_name = self.loop_name_edit.text()
        if not loop_name:
            loop_name = 'Loop'

        # Creates KMZ objects for the loop.
        loop = self.get_loop_lonlat()
        if loop.empty:
            return
        ls = folder.newlinestring(name=loop_name)
        ls.coords = loop.to_numpy()
        ls.extrude = 1
        ls.style = loop_style

        # Creates KMZ object for the collar
        collar = self.get_collar_lonlat()
        if collar.empty:
            return
        collar = folder.newpoint(name=hole_name, coords=collar.to_numpy())
        collar.style = collar_style

        save_dir = self.dialog.getSaveFileName(self, 'Save KMZ File', hole_name, 'KMZ Files (*.KMZ)')[0]
        if save_dir:
            kmz_save_dir = os.path.splitext(save_dir)[0] + '.kmz'
            kml.savekmz(kmz_save_dir, format=False)
            try:
                logger.info(f"Saving {Path(kmz_save_dir).name}.")
                os.startfile(kmz_save_dir)
            except OSError:
                logger.error(f'No application to open {kmz_save_dir}.')
                pass

    def save_gpx(self):
        """
        Save the loop and collar coordinates to a GPX file.
        :return: None
        """
        gpx = gpxpy.gpx.GPX()

        hole_name = self.hole_name_edit.text()
        if not hole_name:
            hole_name = 'Hole'
        loop_name = self.loop_name_edit.text()
        if not loop_name:
            loop_name = 'Loop'

        def loop_to_gpx(row):
            """
            Create a gpx waypoint object for each data row
            :param row: series, converted data row
            """
            waypoint = gpxpy.gpx.GPXWaypoint(latitude=row.Northing,
                                             longitude=row.Easting,
                                             name=loop_name)
            gpx.waypoints.append(waypoint)
            route.points.append(waypoint)

        print('Exporting GPX...')
        self.status_bar.showMessage(f"Saving GPX file...")

        loop = self.get_loop_lonlat()
        if loop.empty:
            return
        # Create the GPX waypoints
        route = gpxpy.gpx.GPXRoute()
        loop.apply(loop_to_gpx, axis=1)
        gpx.routes.append(route)

        collar = self.get_collar_lonlat()
        if collar.empty:
            return
        waypoint = gpxpy.gpx.GPXWaypoint(latitude=collar.loc[0, 'Northing'],
                                         longitude=collar.loc[0, 'Easting'],
                                         name=hole_name)
        gpx.waypoints.append(waypoint)

        # Save the file
        save_path = self.dialog.getSaveFileName(self, 'Save GPX File', hole_name, 'GPX Files (*.GPX)')[0]
        if save_path:
            with open(save_path, 'w') as f:
                f.write(gpx.to_xml())
            self.status_bar.showMessage('Save complete.', 2000)
            try:
                logger.info(f"Saving {Path(save_path).name}.")
                os.startfile(save_path)
            except OSError:
                logger.error(f'No application to open {save_path}.')
                pass
        else:
            self.status_bar.showMessage('Cancelled.', 2000)


class LoopPlanner(SurveyPlanner, Ui_LoopPlannerWindow):
    """
    Program that plots the magnetic field projected to a plane perpendicular to a borehole for a interactive loop.
    Loop and borehole collar can be exported as KMZ or GPX files.
    """

    def __init__(self, parent=None):
        super().__init__()
        self.setupUi(self)
        self.parent = parent

        self.setWindowTitle('Loop Planner')
        self.setWindowIcon(QtGui.QIcon(os.path.join(icons_path, 'loop_planner.png')))
        self.setGeometry(200, 200, 1400, 700)

        self.loop_roi = None

        self.hole_easting = int(self.hole_easting_edit.text())
        self.hole_northing = int(self.hole_northing_edit.text())
        self.hole_elevation = int(self.hole_elevation_edit.text())
        self.hole_az = int(self.hole_az_edit.text())
        self.hole_dip = -int(self.hole_dip_edit.text())
        self.hole_length = int(self.hole_length_edit.text())
        self.hole_elevation = 0

        self.section_figure = Figure()
        self.ax = self.section_figure.add_subplot()
        self.section_canvas = FigureCanvas(self.section_figure)
        self.section_view_layout.addWidget(self.section_canvas)

        # Status bar
        self.status_bar.addPermanentWidget(self.spacer_label, 1)
        self.status_bar.addPermanentWidget(self.epsg_label, 0)

        # Set up plots
        self.hole_trace = pg.PlotDataItem()
        self.hole_collar = pg.ScatterPlotItem()
        self.section_extent_line = pg.PlotDataItem()
        self.loop_plot = pg.ScatterPlotItem()

        self.init_plan_view()
        self.init_section_view()

        self.plot_hole()
        self.plan_view.autoRange()

        # Validators
        int_validator = QtGui.QIntValidator()
        size_validator = QtGui.QIntValidator()
        size_validator.setBottom(1)
        loop_angle_validator = QtGui.QIntValidator()
        loop_angle_validator.setRange(0, 360)
        az_validator = QtGui.QIntValidator()
        az_validator.setRange(0, 360)
        dip_validator = QtGui.QIntValidator()
        dip_validator.setRange(0, 90)

        self.loop_height_edit.setValidator(size_validator)
        self.loop_width_edit.setValidator(size_validator)
        self.loop_angle_edit.setValidator(int_validator)

        self.hole_easting_edit.setValidator(size_validator)
        self.hole_northing_edit.setValidator(size_validator)
        self.hole_elevation_edit.setValidator(int_validator)
        self.hole_az_edit.setValidator(az_validator)
        self.hole_dip_edit.setValidator(dip_validator)
        self.hole_length_edit.setValidator(size_validator)

        self.init_signals()
        self.init_crs()

    def init_signals(self):

        def change_loop_width():
            """
            Signal slot: Change the loop ROI dimensions from user input
            :return: None
            """
            height = self.loop_roi.size()[1]
            width = self.loop_width_edit.text()
            width = float(width)
            logger.info(f"Loop width changed to {width}.")
            self.loop_roi.setSize((width, height))

        def change_loop_height():
            """
            Signal slot: Change the loop ROI dimensions from user input
            :return: None
            """
            height = self.loop_height_edit.text()
            width = self.loop_roi.size()[0]
            height = float(height)
            logger.info(f"Loop height changed to {height}.")
            self.loop_roi.setSize((width, height))

        def change_loop_angle():
            """
            Signal slot: Change the loop ROI angle from user input
            :return: None
            """
            angle = self.loop_angle_edit.text()
            angle = float(angle)
            logger.info(f"Loop angle changed to {angle}.")
            self.loop_roi.setAngle(angle)

        # Menu
        self.actionSave_as_KMZ.triggered.connect(self.save_kmz)
        self.actionSave_as_KMZ.setIcon(QtGui.QIcon(os.path.join(icons_path, 'google_earth.png')))
        self.actionSave_as_GPX.triggered.connect(self.save_gpx)
        self.actionSave_as_GPX.setIcon(QtGui.QIcon(os.path.join(icons_path, 'garmin_file.png')))
        # self.view_map_action.setDisabled(True)
        self.view_map_action.triggered.connect(self.view_map)
        self.view_map_action.setIcon(QtGui.QIcon(os.path.join(icons_path, 'folium.png')))
        self.actionCopy_Loop_to_Clipboard.triggered.connect(self.copy_loop_to_clipboard)

        # Line edits
        self.loop_height_edit.editingFinished.connect(change_loop_height)
        self.loop_width_edit.editingFinished.connect(change_loop_width)
        self.loop_angle_edit.editingFinished.connect(change_loop_angle)

        self.hole_easting_edit.editingFinished.connect(self.plot_hole)
        self.hole_northing_edit.editingFinished.connect(self.plot_hole)
        self.hole_elevation_edit.editingFinished.connect(self.plot_hole)
        self.hole_az_edit.editingFinished.connect(self.plot_hole)
        self.hole_dip_edit.editingFinished.connect(self.plot_hole)
        self.hole_length_edit.editingFinished.connect(self.plot_hole)

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
                    logger.error(f"Invalid EPSG code: {epsg_code}.")
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

        self.gps_system_cbox.setCurrentIndex(2)
        self.gps_datum_cbox.setCurrentIndex(1)
        self.gps_zone_cbox.setCurrentIndex(17)

    def init_plan_view(self):
        """
        Initial set-up of the plan view. Creates the plot widget, custom axes for the Y and X axes, and adds the loop ROI.
        :return: None
        """

        def plan_region_changed():
            """
            Signal slot: Updates the values of the loop width, height and angle when the loop ROI is changed, then
            replots the section plot.
            :return: None
            """
            self.loop_width_edit.blockSignals(True)
            self.loop_height_edit.blockSignals(True)
            self.loop_angle_edit.blockSignals(True)
            x, y = self.loop_roi.pos()
            w, h = self.loop_roi.size()
            angle = self.loop_roi.angle()
            self.loop_width_edit.setText(f"{w:.0f}")
            self.loop_height_edit.setText(f"{h:.0f}")
            self.loop_angle_edit.setText(f"{angle:.0f}")
            self.loop_width_edit.blockSignals(False)
            self.loop_height_edit.blockSignals(False)
            self.loop_angle_edit.blockSignals(False)

            self.plot_hole()

        yaxis = CustomAxis(orientation='left')
        xaxis = CustomAxis(orientation='bottom')
        self.plan_view.setAxisItems({'bottom': xaxis, 'left': yaxis})
        self.plan_view.showGrid(x=True, y=True, alpha=0.2)
        # self.plan_view_vb.disableAutoRange('xy')
        self.plan_view.setAspectLocked()
        self.plan_view.hideButtons()
        self.plan_view.getAxis('right').setWidth(15)
        self.plan_view.getAxis("right").setStyle(showValues=False)  # Disable showing the values of axis
        self.plan_view.getAxis("top").setStyle(showValues=False)  # Disable showing the values of axis
        self.plan_view.showAxis('right', show=True)  # Show the axis edge line
        self.plan_view.showAxis('top', show=True)  # Show the axis edge line
        self.plan_view.showLabel('right', show=False)
        self.plan_view.showLabel('top', show=False)

        # loop_roi is the loop.
        self.loop_roi = LoopROI([self.hole_easting-250, self.hole_northing-250], [500, 500],
                                scaleSnap=True,
                                pen=pg.mkPen('m', width=1.5))
        self.plan_view.addItem(self.loop_roi)
        self.loop_roi.setZValue(10)
        self.loop_roi.addScaleHandle([0, 0], [0.5, 0.5], lockAspect=True)
        self.loop_roi.addScaleHandle([1, 0], [0.5, 0.5], lockAspect=True)
        self.loop_roi.addScaleHandle([1, 1], [0.5, 0.5], lockAspect=True)
        self.loop_roi.addScaleHandle([0, 1], [0.5, 0.5], lockAspect=True)
        self.loop_roi.addRotateHandle([1, 0.5], [0.5, 0.5])
        self.loop_roi.addRotateHandle([0.5, 0], [0.5, 0.5])
        self.loop_roi.addRotateHandle([0.5, 1], [0.5, 0.5])
        self.loop_roi.addRotateHandle([0, 0.5], [0.5, 0.5])
        self.loop_roi.sigRegionChangeFinished.connect(plan_region_changed)

    def init_section_view(self):
        """
        Initial set-up of the section plot. Sets the axes to have equal aspect ratios.
        :return: None
        """
        self.ax.set_aspect('equal')
        self.ax.use_sticky_edges = False  # So the plot doesn't re-size after the first time it's plotted
        self.ax.spines['top'].set_visible(False)
        self.ax.spines['left'].set_visible(False)
        self.ax.spines['right'].set_visible(False)
        self.ax.spines['bottom'].set_visible(False)
        self.ax.get_xaxis().set_visible(False)
        self.ax.yaxis.set_major_formatter(ticker.StrMethodFormatter('{x:.0f}'))
        self.ax.figure.subplots_adjust(left=0.1, bottom=0.1, right=1., top=1.)

    def plot_hole(self):
        """
        Plots the hole on the plan plot and section plot, and plots the vector magnetic field on the section plot.
        :return: None
        """

        def get_hole_projection():
            """
            Calculates the 3D projection of the hole.
            :return: list of (x, y, z) tuples of the 3D hole trace.
            """
            x, y, z = self.hole_easting, self.hole_northing, self.hole_elevation
            delta_surf = self.hole_length * math.cos(math.radians(self.hole_dip))
            dx = delta_surf * math.sin(math.radians(self.hole_az))
            dy = delta_surf * math.cos(math.radians(self.hole_az))
            dz = self.hole_length * math.sin(math.radians(self.hole_dip))
            x = [x, self.hole_easting + dx]
            y = [y, self.hole_northing + dy]
            z = [z, self.hole_elevation + dz]
            return x, y, z

        def get_section_extents(x, y, z):
            """
            Calculates the two coordinates to be used for the section plot.
            :param x: list, hole projection x values
            :param y: list, hole projection y values
            :param z: list, hole projection z values
            :return: (x, y) tuples of the two end-points.
            """
            # Remove the previously plotted section line
            self.section_extent_line.clear()

            # Calculate the length of the cross-section
            line_len = math.ceil(self.hole_length / 400) * 400

            # Find the coordinate that is 80% down the hole
            if 90 < self.hole_az < 180:
                line_center_x = np.percentile(x, 80)
                line_center_y = np.percentile(y, 20)
            elif 180 < self.hole_az < 270:
                line_center_x = np.percentile(x, 20)
                line_center_y = np.percentile(y, 20)
            elif 270 < self.hole_az < 360:
                line_center_x = np.percentile(x, 20)
                line_center_y = np.percentile(y, 80)
            else:
                line_center_x = np.percentile(x, 80)
                line_center_y = np.percentile(y, 80)

            # # Plot the center point to see if it's working properly
            # self.hole_line_center.setData([line_center_x], [line_center_y], pen=pg.mkPen(width=2, color=0.4))
            # self.plan_view.addItem(self.hole_line_center)

            # Calculate the end point coordinates of the section line
            dx = math.sin(math.radians(self.hole_az)) * (line_len / 2)
            dy = math.cos(math.radians(self.hole_az)) * (line_len / 2)
            p1 = (line_center_x - dx, line_center_y - dy)
            p2 = (line_center_x + dx, line_center_y + dy)

            # Plot the section line
            self.section_extent_line.setData([line_center_x - dx, line_center_x + dx],
                                             [line_center_y - dy, line_center_y + dy],
                                             width=1,
                                             pen=pg.mkPen(color=0.5,
                                                          style=QtCore.Qt.DashLine))
            self.plan_view.addItem(self.section_extent_line)

            return p1, p2

        def plot_hole_section(p1, p2, hole_projection):
            """
            Plot the hole trace in the section plot.
            :param p1: (x, y) tuple: Coordinate of one end of the section's extent.
            :param p2: (x, y) tuple: Coordinate of the other end of the section's extent.
            :param hole_projection: list of (x, y, z) tuples: 3D projection of the borehole geometry.
            :return: None
            """

            def get_magnitude(vector):
                return math.sqrt(sum(i ** 2 for i in vector))

            p = np.array([p1[0], p1[1], 0])
            vec = [p2[0] - p1[0], p2[1] - p1[1], 0]
            planeNormal = np.cross(vec, [0, 0, -1])
            planeNormal = planeNormal / get_magnitude(planeNormal)

            plotx = []
            plotz = []

            # Projecting the 3D trace to a 2D plane
            for coordinate in hole_projection:
                q = np.array(coordinate)
                q_proj = q - np.dot(q - p, planeNormal) * planeNormal
                distvec = np.array([q_proj[0] - p[0], q_proj[1] - p[1]])
                dist = np.sqrt(distvec.dot(distvec))

                plotx.append(dist)
                plotz.append(q_proj[2])

            # Plot the collar
            self.ax.plot(plotx[0], plotz[0], 'o',
                         mfc='w',
                         markeredgecolor='dimgray',
                         zorder=10)
            # Plot the hole section line
            self.ax.plot(plotx, plotz,
                         color='dimgray',
                         lw=1,
                         zorder=1)
            self.ax.axhline(y=0,
                            color='dimgray', lw=0.6,
                            zorder=9)

        def plot_mag(c1, c2):
            """
            Plots the magnetic vector quiver plot in the section plot.
            :param c1: (x, y, z) tuple: Corner of the 2D section to plot the mag on.
            :param c2: (x, y, z) tuple: Opposite corner of the 2D section to plot the mag on.
            :return: None
            """
            wire_coords = self.get_loop_coords()
            mag_calculator = MagneticFieldCalculator(wire_coords)
            xx, yy, zz, uproj, vproj, wproj, plotx, plotz, arrow_len = mag_calculator.get_2d_magnetic_field(c1, c2)
            self.ax.quiver(xx, zz, plotx, plotz,
                           color='dimgray',
                           label='Field',
                           pivot='middle',
                           zorder=0,
                           units='dots',
                           scale=.050,
                           width=.8,
                           headlength=11,
                           headwidth=6)

        def plot_trace(xs, ys):
            """
            Plot the hole trace on the plan view plot.
            :param xs: list: X values to plot
            :param ys: list: Y values to plot
            :return: None
            """
            self.hole_trace.setData(xs, ys, pen=pg.mkPen(width=2, color=0.5))
            self.hole_collar.setData([self.hole_easting], [self.hole_northing],
                                     pen=pg.mkPen(width=3, color=0.5))
            self.plan_view.addItem(self.hole_trace)
            self.plan_view.addItem(self.hole_collar)

        def shift_loop(dx, dy):
            """
            Moves the loop ROI so it is in the same position relative to the grid.
            :param dx: Shift amount in x axis
            :param dy: Shift amount in y axis
            :return: None
            """
            self.loop_roi.blockSignals(True)
            x, y = self.loop_roi.pos()
            self.loop_roi.setPos(x + dx, y + dy)
            self.loop_roi.blockSignals(False)

        # Shift the loop position relative to the hole position when the hole is moved
        if self.move_loop_cbox.isChecked():
            if int(self.hole_easting_edit.text()) != self.hole_easting:
                shift_amt = int(self.hole_easting_edit.text()) - self.hole_easting
                shift_loop(shift_amt, 0)
            if int(self.hole_northing_edit.text()) != self.hole_northing:
                shift_amt = int(self.hole_northing_edit.text()) - self.hole_northing
                shift_loop(0, shift_amt)

        self.hole_easting = int(self.hole_easting_edit.text())
        self.hole_northing = int(self.hole_northing_edit.text())
        self.hole_elevation = int(self.hole_elevation_edit.text())
        self.hole_az = int(self.hole_az_edit.text())
        self.hole_dip = -int(self.hole_dip_edit.text())
        self.hole_length = int(self.hole_length_edit.text())

        self.hole_trace.clear()
        self.hole_collar.clear()
        self.ax.clear()

        xs, ys, zs = get_hole_projection()
        p1, p2 = get_section_extents(xs, ys, zs)

        plot_trace(xs, ys)
        plot_hole_section(p1, p2, list(zip(xs, ys, zs)))

        # Get the corners of the 2D section to plot the mag on
        c1, c2 = list(p1), list(p2)
        c1.append(max(self.ax.get_ylim()[1], 0))  # Add the max Z
        c2.append(self.ax.get_ylim()[0])  # Add the min Z
        plot_mag(c1, c2)

        self.section_canvas.draw()

    def shift_loop(self, dx, dy):
        """
        Moves the loop ROI so it is in the same position relative to the hole.
        :param dx: Shift amount in x axis
        :param dy: Shift amount in y axis
        :return: None
        """
        self.loop_roi.blockSignals(True)
        x, y = self.loop_roi.pos()
        self.loop_roi.setPos(x + dx, y + dy)
        self.plan_view.autoRange(items=[self.loop_roi])
        self.loop_roi.blockSignals(False)

    def get_loop_coords(self):
        """
        Return the coordinates of the loop corners
        :return: list of (x, y, z)
        """
        x, y = self.loop_roi.pos()
        w, h = self.loop_roi.size()
        angle = self.loop_roi.angle()
        c1 = (x, y, 0)
        c2 = (c1[0] + w * (math.cos(math.radians(angle))), c1[1] + w * (math.sin(math.radians(angle))), 0)
        c3 = (c2[0] - h * (math.sin(math.radians(angle))), c2[1] + h * (math.sin(math.radians(90-angle))), 0)
        c4 = (c3[0] + w * (math.cos(math.radians(180-angle))), c3[1] - w * (math.sin(math.radians(180-angle))), 0)
        corners = [c1, c2, c3, c4]

        return corners

    def get_loop_lonlat(self):
        """
        Return the lat lon data frame of the loop corners
        :return: dataframe
        """
        epsg = self.get_epsg()

        if not epsg:
            self.message.critical(self, 'Invalid CRS', 'Input CRS is invalid.')
            return pd.DataFrame()
        else:
            crs = CRS.from_epsg(epsg)

        # Get the loop data
        loop = pd.DataFrame(self.get_loop_coords(), columns=['Easting', 'Northing', 'Elevation'])
        loop = loop.append(loop.iloc[0])  # Close the loop

        # Create point objects for each coordinate
        mpoints = asMultiPoint(loop.loc[:, ['Easting', 'Northing']].to_numpy())
        gdf = gpd.GeoSeries(list(mpoints), crs=crs)

        # Convert to lat lon
        converted_gdf = gdf.to_crs(epsg=4326)
        loop['Easting'], loop['Northing'] = converted_gdf.map(lambda p: p.x), converted_gdf.map(lambda p: p.y)

        return loop

    def get_collar_lonlat(self):
        """
        Return the lat lon data frame of the hole collar
        :return: dataframe
        """
        epsg = self.get_epsg()

        if not epsg:
            self.message.critical(self, 'Invalid CRS', 'Input CRS is invalid.')
            return pd.DataFrame()
        else:
            crs = CRS.from_epsg(epsg)

        # Add the collar coordinates to the GPX as a waypoint.
        hole = pd.DataFrame(columns=['Easting', 'Northing'])
        hole.loc[0] = [self.hole_easting, self.hole_northing]

        # Create point objects for each coordinate
        mpoints = asMultiPoint(hole.loc[:, ['Easting', 'Northing']].to_numpy())
        gdf = gpd.GeoSeries(list(mpoints), crs=crs)

        # Convert to lat lon
        converted_gdf = gdf.to_crs(epsg=4326)
        hole['Easting'], hole['Northing'] = converted_gdf.map(lambda p: p.x), converted_gdf.map(lambda p: p.y)
        return hole

    def view_map(self):
        """
        View the hole and loop in a Plotly mapbox interactive map. A screen capture of the map can be
        saved with 'Ctrl+S' or copied to the clipboard with 'Ctrl+C'
        """
        global terrain_map
        terrain_map = MapboxViewer()

        loop_coords = self.get_loop_lonlat()
        collar = self.get_collar_lonlat()

        if loop_coords.empty and collar.empty:
            logger.error(f"No GPS to plot.")
            return

        hole_name = 'Hole' if self.hole_name_edit.text() == '' else self.hole_name_edit.text()
        loop_name = 'Loop' if self.loop_name_edit.text() == '' else self.loop_name_edit.text()

        terrain_map.map_figure.add_trace(go.Scattermapbox(lon=collar.Easting,
                                                          lat=collar.Northing,
                                                          mode='markers',
                                                          name=hole_name,
                                                          text=hole_name
                                                          ))

        terrain_map.map_figure.add_trace(go.Scattermapbox(lon=loop_coords.Easting,
                                                          lat=loop_coords.Northing,
                                                          mode='lines+markers',
                                                          name=loop_name,
                                                          text=loop_coords.index
                                                          ))

        # Pass the mapbox token, for access to better map tiles. If none is passed, it uses the free open street map.
        token = open(".mapbox", 'r').read()
        if not token:
            logger.warning(f"No Mapbox token passed.")
            map_style = "open-street-map"
        else:
            map_style = "outdoors"

        # Format the figure margins and legend
        terrain_map.map_figure.update_layout(
            margin={"r": 0,
                    "t": 0,
                    "l": 0,
                    "b": 0},
            legend=dict(
                yanchor="top",
                y=0.99,
                xanchor="left",
                x=0.01,
                bordercolor="Black",
                borderwidth=1
            ),
        )
        # Add the map style and center/zoom the map
        terrain_map.map_figure.update_layout(
            mapbox={
                'center': {'lon': loop_coords.Easting.mean(), 'lat': loop_coords.Northing.mean()},
                'zoom': 13},
            mapbox_style=map_style,
            mapbox_accesstoken=token)

        terrain_map.load_page()
        terrain_map.show()

    def save_kmz(self):
        """
        Save the loop and hole collar to a KMZ file.
        :return: None
        """

        kml = simplekml.Kml()

        loop_style = simplekml.Style()
        loop_style.linestyle.width = 4
        loop_style.linestyle.color = simplekml.Color.yellow

        trace_style = simplekml.Style()
        trace_style.linestyle.width = 2
        trace_style.linestyle.color = simplekml.Color.magenta

        collar_style = simplekml.Style()
        collar_style.iconstyle.icon.href = 'http://maps.google.com/mapfiles/kml/paddle/wht-stars.png'
        collar_style.iconstyle.color = simplekml.Color.magenta

        hole_name = self.hole_name_edit.text()
        if not hole_name:
            hole_name = 'Hole'
        folder = kml.newfolder(name=hole_name)
        loop_name = self.loop_name_edit.text()
        if not loop_name:
            loop_name = 'Loop'

        # Creates KMZ objects for the loop.
        loop = self.get_loop_lonlat()
        if loop.empty:
            return
        ls = folder.newlinestring(name=loop_name)
        ls.coords = loop.to_numpy()
        ls.extrude = 1
        ls.style = loop_style

        # Creates KMZ object for the collar
        collar = self.get_collar_lonlat()
        if collar.empty:
            return
        collar = folder.newpoint(name=hole_name, coords=collar.to_numpy())
        collar.style = collar_style

        save_dir = self.dialog.getSaveFileName(self, 'Save KMZ File', hole_name, 'KMZ Files (*.KMZ)')[0]
        if save_dir:
            kmz_save_dir = os.path.splitext(save_dir)[0] + '.kmz'
            kml.savekmz(kmz_save_dir, format=False)
            try:
                logger.info(f"Saving {Path(kmz_save_dir).name}.")
                os.startfile(kmz_save_dir)
            except OSError:
                logger.error(f'No application to open {kmz_save_dir}.')
                pass

    def save_gpx(self):
        """
        Save the loop and collar coordinates to a GPX file.
        :return: None
        """
        gpx = gpxpy.gpx.GPX()

        hole_name = self.hole_name_edit.text()
        if not hole_name:
            hole_name = 'Hole'
        loop_name = self.loop_name_edit.text()
        if not loop_name:
            loop_name = 'Loop'

        def loop_to_gpx(row):
            """
            Create a gpx waypoint object for each data row
            :param row: series, converted data row
            """
            waypoint = gpxpy.gpx.GPXWaypoint(latitude=row.Northing,
                                             longitude=row.Easting,
                                             name=loop_name)
            gpx.waypoints.append(waypoint)
            route.points.append(waypoint)

        print('Exporting GPX...')
        self.status_bar.showMessage(f"Saving GPX file...")

        loop = self.get_loop_lonlat()
        if loop.empty:
            return
        # Create the GPX waypoints
        route = gpxpy.gpx.GPXRoute()
        loop.apply(loop_to_gpx, axis=1)
        gpx.routes.append(route)

        collar = self.get_collar_lonlat()
        if collar.empty:
            return
        waypoint = gpxpy.gpx.GPXWaypoint(latitude=collar.loc[0, 'Northing'],
                                         longitude=collar.loc[0, 'Easting'],
                                         name=hole_name)
        gpx.waypoints.append(waypoint)

        # Save the file
        save_path = self.dialog.getSaveFileName(self, 'Save GPX File', hole_name, 'GPX Files (*.GPX)')[0]
        if save_path:
            with open(save_path, 'w') as f:
                f.write(gpx.to_xml())
            self.status_bar.showMessage('Save complete.', 2000)
            try:
                logger.info(f"Saving {Path(save_path).name}.")
                os.startfile(save_path)
            except OSError:
                logger.error(f'No application to open {save_path}.')
                pass
        else:
            self.status_bar.showMessage('Cancelled.', 2000)


class GridPlanner(SurveyPlanner, Ui_GridPlannerWindow):
    """
    Program to plan a surface grid.
    """

    def __init__(self, parent=None):
        super().__init__()
        self.setupUi(self)
        self.parent = parent

        self.setWindowTitle('Grid Planner')
        self.setWindowIcon(QtGui.QIcon(os.path.join(icons_path, 'grid_planner.png')))
        self.setGeometry(200, 200, 1100, 700)

        self.loop_height = int(self.loop_height_edit.text())
        self.loop_width = int(self.loop_width_edit.text())
        self.loop_angle = int(self.loop_angle_edit.text())

        self.grid_easting = int(self.grid_easting_edit.text())
        self.grid_northing = int(self.grid_northing_edit.text())
        self.grid_az = int(self.grid_az_edit.text())
        self.line_number = int(self.line_number_edit.text())
        self.line_length = int(self.line_length_edit.text())
        self.station_spacing = int(self.station_spacing_edit.text())
        self.line_spacing = int(self.line_spacing_edit.text())

        self.grid_east_center, self.grid_north_center = 0, 0
        self.lines = []

        # Status bar
        self.status_bar.addPermanentWidget(self.spacer_label, 1)
        self.status_bar.addPermanentWidget(self.epsg_label, 0)

        # Plots
        self.grid_lines_plot = pg.MultiPlotItem()
        self.grid_lines_plot.setZValue(1)
        self.init_plan_view()

        self.plan_view.autoRange()
        self.plot_grid()

        # Validators
        int_validator = QtGui.QIntValidator()
        size_validator = QtGui.QIntValidator()
        size_validator.setBottom(1)
        loop_angle_validator = QtGui.QIntValidator()
        loop_angle_validator.setRange(0, 360)
        az_validator = QtGui.QIntValidator()
        az_validator.setRange(0, 360)
        dip_validator = QtGui.QIntValidator()
        dip_validator.setRange(0, 90)

        self.loop_height_edit.setValidator(size_validator)
        self.loop_width_edit.setValidator(size_validator)
        self.loop_angle_edit.setValidator(int_validator)

        self.grid_easting_edit.setValidator(int_validator)
        self.grid_northing_edit.setValidator(int_validator)
        self.grid_az_edit.setValidator(az_validator)
        self.line_number_edit.setValidator(size_validator)
        self.line_length_edit.setValidator(size_validator)
        self.station_spacing_edit.setValidator(size_validator)
        self.line_spacing_edit.setValidator(size_validator)

        self.init_signals()
        self.init_crs()

    def init_signals(self):

        def change_loop_width():
            """
            Signal slot: Change the loop ROI dimensions from user input
            :return: None
            """
            height = self.loop_roi.size()[1]
            width = self.loop_width_edit.text()
            width = float(width)
            logger.info(f"Loop width changed to {width}")
            self.loop_roi.setSize((width, height))

        def change_loop_height():
            """
            Signal slot: Change the loop ROI dimensions from user input
            :return: None
            """
            height = self.loop_height_edit.text()
            width = self.loop_roi.size()[0]
            height = float(height)
            logger.info(f"Loop height changed to {height}")
            self.loop_roi.setSize((width, height))

        def change_loop_angle():
            """
            Signal slot: Change the loop ROI angle from user input
            :return: None
            """
            angle = self.loop_angle_edit.text()
            angle = float(angle)
            logger.info(f"Loop angle changed to {angle}")
            self.loop_roi.setAngle(angle)

        def change_grid_angle():
            """
            Signal slot: Change the grid ROI angle from user input. Converts from azimuth to angle
            :return: None
            """
            az = int(self.grid_az_edit.text())
            angle = 90 - az
            logger.info(f"Grid angle changed to {az}")
            self.grid_roi.setAngle(angle)

        def change_grid_size():
            """
            Signal slot: Change the grid ROI dimensions from user input
            :return: None
            """
            self.line_length = int(self.line_length_edit.text())
            self.line_number = int(self.line_number_edit.text())
            self.line_spacing = int(self.line_spacing_edit.text())
            self.grid_roi.setSize((self.line_length, max((self.line_number - 1) * self.line_spacing, 10)))
            logger.info(f"Grid size changed to {self.line_length} x {max((self.line_number - 1) * self.line_spacing, 10)}")

        def change_grid_pos():
            """
            Change the position of the grid ROI based on the input from the grid easting and northing text edits.
            :return: None
            """

            def get_corner(x, y):
                """
                Find the bottom-right corner given the center of the grid.
                :param x: X coordinate of the center point
                :param y: Y coordinate of the center point
                :return: X, Y coordinate of the bottom-right corner.
                """
                a = 90 - self.grid_roi.angle()
                w = max((self.line_number - 1) * self.line_spacing, 10)
                h = self.line_length

                hypo = math.sqrt(w ** 2 + h ** 2)
                angle = math.degrees(math.atan(h / w)) + a
                theta = math.radians(angle)
                dx = (hypo / 2) * math.cos(theta)
                dy = (hypo / 2) * math.sin(theta)
                center = pg.ScatterPlotItem([x + dx], [y - dy], pen='y')
                self.plan_view.addItem(center)
                logger.info(f"Corner is at {x + dx}, {y - dy}")
                return x + dx, y - dy

            x, y = get_corner(int(self.grid_easting_edit.text()), int(self.grid_northing_edit.text()))
            easting_shift = x - self.grid_easting
            northing_shift = y - self.grid_northing
            self.shift_loop(easting_shift, northing_shift)
            self.grid_easting, self.grid_northing = x, y
            self.grid_roi.setPos(x, y)

            self.grid_east_center, self.grid_north_center = int(self.grid_easting_edit.text()), int(
                self.grid_northing_edit.text())
            logger.info(f"Grid position changed to {self.grid_east_center, self.grid_north_center}")

            self.plot_grid()
            self.plan_view.autoRange(items=[self.loop_roi, self.grid_roi])

        # Menu
        self.actionSave_as_KMZ.triggered.connect(self.save_kmz)
        self.actionSave_as_KMZ.setIcon(QtGui.QIcon(os.path.join(icons_path, 'google_earth.png')))
        self.actionSave_as_GPX.triggered.connect(self.save_gpx)
        self.actionSave_as_GPX.setIcon(QtGui.QIcon(os.path.join(icons_path, 'garmin_file.png')))
        # self.view_map_action.setDisabled(True)
        self.view_map_action.triggered.connect(self.view_map)
        self.view_map_action.setIcon(QtGui.QIcon(os.path.join(icons_path, 'folium.png')))
        self.actionCopy_Loop_to_Clipboard.triggered.connect(self.copy_loop_to_clipboard)
        self.actionCopy_Grid_to_Clipboard.triggered.connect(self.copy_grid_to_clipboard)

        self.loop_height_edit.editingFinished.connect(change_loop_height)
        self.loop_width_edit.editingFinished.connect(change_loop_width)
        self.loop_angle_edit.editingFinished.connect(change_loop_angle)
        self.grid_az_edit.editingFinished.connect(change_grid_angle)

        self.grid_easting_edit.editingFinished.connect(self.plot_grid)
        self.grid_easting_edit.editingFinished.connect(change_grid_pos)
        self.grid_northing_edit.editingFinished.connect(self.plot_grid)
        self.grid_northing_edit.editingFinished.connect(change_grid_pos)
        self.grid_az_edit.editingFinished.connect(self.plot_grid)
        self.line_number_edit.editingFinished.connect(self.plot_grid)
        self.line_number_edit.editingFinished.connect(change_grid_size)
        self.line_length_edit.editingFinished.connect(self.plot_grid)
        self.line_length_edit.editingFinished.connect(change_grid_size)
        self.station_spacing_edit.editingFinished.connect(self.plot_grid)
        self.line_spacing_edit.editingFinished.connect(self.plot_grid)
        self.line_spacing_edit.editingFinished.connect(change_grid_size)

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
                    logger.error(f"Invalid EPSG code: {epsg_code}.")
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

        self.gps_system_cbox.setCurrentIndex(2)
        self.gps_datum_cbox.setCurrentIndex(1)
        self.gps_zone_cbox.setCurrentIndex(17)
        set_epsg_label()

    def init_plan_view(self):
        """
        Initial set-up of the plan view. Creates the plot widget, custom axes for the Y and X axes, and adds the loop ROI.
        :return: None
        """

        def set_loop():

            def loop_moved():
                """
                Signal slot: Updates the values of the loop width, height and angle when the loop ROI is changed, then
                replots the section plot.
                :return: None
                """
                self.loop_width_edit.blockSignals(True)
                self.loop_height_edit.blockSignals(True)
                self.loop_angle_edit.blockSignals(True)
                x, y = self.loop_roi.pos()
                w, h = self.loop_roi.size()
                angle = self.loop_roi.angle()
                self.loop_width_edit.setText(f"{w:.0f}")
                self.loop_height_edit.setText(f"{h:.0f}")
                self.loop_angle_edit.setText(f"{angle:.0f}")
                self.loop_width_edit.blockSignals(False)
                self.loop_height_edit.blockSignals(False)
                self.loop_angle_edit.blockSignals(False)
                self.plot_grid()

            # Create the loop ROI
            center_x, center_y = self.get_grid_center(self.grid_easting, self.grid_northing)
            self.loop_roi = LoopROI([center_x - (self.loop_width / 2),
                                     center_y - (self.loop_height / 2)],
                                    [self.loop_width, self.loop_height], scaleSnap=True,
                                    pen=pg.mkPen('m', width=1.5))
            self.plan_view.addItem(self.loop_roi)
            self.loop_roi.setZValue(0)
            self.loop_roi.addScaleHandle([0, 0], [0.5, 0.5], lockAspect=True)
            self.loop_roi.addScaleHandle([1, 0], [0.5, 0.5], lockAspect=True)
            self.loop_roi.addScaleHandle([1, 1], [0.5, 0.5], lockAspect=True)
            self.loop_roi.addScaleHandle([0, 1], [0.5, 0.5], lockAspect=True)
            self.loop_roi.addRotateHandle([1, 0.5], [0.5, 0.5])
            self.loop_roi.addRotateHandle([0.5, 0], [0.5, 0.5])
            self.loop_roi.addRotateHandle([0.5, 1], [0.5, 0.5])
            self.loop_roi.addRotateHandle([0, 0.5], [0.5, 0.5])
            self.loop_roi.sigRegionChangeFinished.connect(loop_moved)

        def set_grid():

            def grid_moved():
                """
                Signal slot: Update the grid easting and northing text based on the new position of the grid when the ROI
                is moved.
                :return: None
                """
                self.grid_easting_edit.blockSignals(True)
                self.grid_northing_edit.blockSignals(True)

                x, y = self.grid_roi.pos()
                self.grid_easting, self.grid_northing = x, y
                self.grid_east_center, self.grid_north_center = self.get_grid_center(x, y)
                self.grid_easting_edit.setText(f"{self.grid_east_center:.0f}")
                self.grid_northing_edit.setText(f"{self.grid_north_center:.0f}")

                self.grid_easting_edit.blockSignals(False)
                self.grid_northing_edit.blockSignals(False)
                self.plot_grid()

            # Create the grid
            self.grid_roi = LoopROI([self.grid_easting, self.grid_northing],
                                    [self.line_length, (self.line_number - 1) * self.line_spacing], scaleSnap=True,
                                    pen=pg.mkPen(None, width=1.5))
            self.grid_roi.setAngle(90)
            self.plan_view.addItem(self.grid_roi)
            self.grid_roi.sigRegionChangeStarted.connect(lambda: self.grid_roi.setPen('b'))
            self.grid_roi.sigRegionChangeFinished.connect(lambda: self.grid_roi.setPen(None))
            self.grid_roi.sigRegionChangeFinished.connect(grid_moved)

        yaxis = CustomAxis(orientation='left')
        xaxis = CustomAxis(orientation='bottom')
        self.plan_view.setAxisItems({'bottom': xaxis, 'left': yaxis})
        self.plan_view.showGrid(x=True, y=True, alpha=0.2)
        self.plan_view.setAspectLocked()
        self.plan_view.hideButtons()
        self.plan_view.getAxis('right').setWidth(15)
        self.plan_view.getAxis("right").setStyle(showValues=False)  # Disable showing the values of axis
        self.plan_view.getAxis("top").setStyle(showValues=False)  # Disable showing the values of axis
        self.plan_view.showAxis('right', show=True)  # Show the axis edge line
        self.plan_view.showAxis('top', show=True)  # Show the axis edge line
        self.plan_view.showLabel('right', show=False)
        self.plan_view.showLabel('top', show=False)
        set_grid()
        set_loop()

    def plot_grid(self):
        """
        Plots the stations and lines on the plan map.
        :return: None
        """

        def transform_station(x, y, l):
            """
            Calculate the position of a station based on the distance away from the start station for that line.
            :param x: X coordinate of the starting station
            :param y: Y coordinate of the starting station
            :param l: distance away from the starting station
            :return: X, Y coordinate of the station
            """
            angle = 90 - self.grid_roi.angle()
            dx = l * math.sin(math.radians(angle))
            dy = l * math.cos(math.radians(angle))

            return x + dx, y + dy

        def transform_line_start(x, y, l):
            """
            Calculate the position of the starting station of a line based on the distance away from the corner of the
            grid.
            :param x: X coordinate of the grid corner
            :param y: Y coordinate of the grid corner
            :param l: Distance from the grid corner
            :return: X, Y coordinate of the starting station
            """
            angle = 90 - self.grid_roi.angle()
            dx = l * math.cos(math.radians(angle))
            dy = l * math.sin(math.radians(angle))

            return x - dx, y + dy

        def clear_plots():
            for item in reversed(self.plan_view.items()):
                if not isinstance(item, LoopROI):
                    self.plan_view.removeItem(item)

        clear_plots()

        x, y = self.grid_roi.pos()
        center_x, center_y = self.get_grid_center(x, y)
        self.get_grid_corner_coords()

        self.grid_az = int(self.grid_az_edit.text())
        self.line_length = int(self.line_length_edit.text())
        self.station_spacing = int(self.station_spacing_edit.text())
        self.line_spacing = int(self.line_spacing_edit.text())
        self.line_number = int(self.line_number_edit.text())

        self.lines = []
        # Plotting the stations and lines
        for i, line in enumerate(range(self.line_number)):
            a = 90 - self.grid_roi.angle()
            if 45 <= a < 135:
                line_number = i + 1
                line_suffix = 'N'
                station_suffix = 'E'
                text_angle = self.grid_roi.angle() - 90
                text_anchor = (1, 0.5)
            elif 135 <= a < 225:
                line_number = i + 1
                line_suffix = 'E'
                station_suffix = 'S'
                text_angle = self.grid_roi.angle()
                text_anchor = (0.5, 1)
            elif 225 <= a < 315:
                line_number = self.line_number - i
                line_suffix = 'N'
                station_suffix = 'W'
                text_angle = self.grid_roi.angle() +90
                text_anchor = (0, 0.5)
            else:
                line_number = self.line_number - i
                line_suffix = 'E'
                station_suffix = 'N'
                text_angle = self.grid_roi.angle() - 180
                text_anchor = (0.5, 0)

            line_name = f" {line_number}{line_suffix} "
            self.lines.append({'line_name': line_name})
            station_xs, station_ys, station_names = [], [], []

            x_start, y_start = transform_line_start(x, y, i * self.line_spacing)
            station_text = pg.TextItem(text=line_name, color='b', angle=text_angle,
                                       rotateAxis=(0, 1),
                                       anchor=text_anchor)
            station_text.setPos(x_start, y_start)
            self.plan_view.addItem(station_text)

            # Add station labels
            for j, station in enumerate(range(int(self.line_length / self.station_spacing) + 1)):
                station_x, station_y = transform_station(x_start, y_start, j * self.station_spacing)
                station_name = f"{self.station_spacing*(j+1)}{station_suffix}"
                station_names.append(station_name)
                station_xs.append(station_x)
                station_ys.append(station_y)
            self.lines[i]['station_coords'] = list(zip(station_xs, station_ys, station_names))

            line_plot = pg.PlotDataItem(station_xs, station_ys, pen='b')
            line_plot.setZValue(1)
            stations_plot = pg.ScatterPlotItem(station_xs, station_ys, pen='b', brush='w')
            stations_plot.setZValue(2)

            self.plan_view.addItem(line_plot)
            self.plan_view.addItem(stations_plot)

        # Plot a symbol at the center of the grid
        grid_center = pg.ScatterPlotItem([center_x],[center_y], pen='b', symbol='+')
        grid_center.setZValue(1)
        self.plan_view.addItem(grid_center)

    def grid_to_df(self):
        """
        Convert the grid lines to a data frame
        :return: pd.DataFrame
        """
        line_list = []
        for line in self.lines:
            name = line['line_name']

            for station in line['station_coords']:
                easting = station[0]
                northing = station[1]
                station = station[2]
                line_list.append([name, easting, northing, station])

        df = pd.DataFrame(line_list, columns=['Line_name', 'Easting', 'Northing', 'Station'])
        return df

    def get_grid_corner_coords(self):
        """
        Return the coordinates of the grid corners.
        :return: list of (x, y)
        """
        x, y = self.grid_roi.pos()
        w, h = self.grid_roi.size()
        angle = self.grid_roi.angle()
        c1 = (x, y)
        c2 = (c1[0] + w * (math.cos(math.radians(angle))), c1[1] + w * (math.sin(math.radians(angle))))
        c3 = (c2[0] - h * (math.sin(math.radians(angle))), c2[1] + h * (math.sin(math.radians(90 - angle))))
        c4 = (c3[0] + w * (math.cos(math.radians(180 - angle))), c3[1] - w * (math.sin(math.radians(180 - angle))))
        corners = [c1, c2, c3, c4]

        # self.grid_stations_plot.addPoints([coord[0] for coord in corners],
        #                        [coord[1] for coord in corners], pen=pg.mkPen(width=3, color='r'))
        return corners

    def get_grid_center(self, x, y):
        """
        Find the center of the grid given the bottom-right coordinate of the grid.
        :param x: X coordinate of the bottom-right corner
        :param y: Y coordinate of the bottom-right corner
        :return: X, Y coordinate of the center of the grid.
        """
        a = 90 - self.grid_roi.angle()
        w = max((self.line_number - 1) * self.line_spacing, 10)
        h = self.line_length

        hypo = math.sqrt(w ** 2 + h ** 2)
        angle = math.degrees(math.atan(h / w)) + a
        theta = math.radians(angle)
        dx = (hypo / 2) * math.cos(theta)
        dy = (hypo / 2) * math.sin(theta)
        # print(f"Center is at {x - dx}, {y + dy}")
        return x - dx, y + dy

    def get_grid_lonlat(self):
        """
        Convert the coordinates of all stations in the grid to lon lat.
        :return: List of dicts with lonlat coordinates.
        """
        epsg = self.get_epsg()

        if not epsg:
            self.message.critical(self, 'Invalid CRS', 'Input CRS is invalid.')
            return pd.DataFrame()
        else:
            crs = CRS.from_epsg(epsg)

        # Get the grid data
        grid = self.grid_to_df()

        # Create point objects for each coordinate
        mpoints = asMultiPoint(grid.loc[:, ['Easting', 'Northing']].to_numpy())
        gdf = gpd.GeoSeries(list(mpoints), crs=crs)

        # Convert to lat lon
        converted_gdf = gdf.to_crs(epsg=4326)
        grid['Easting'], grid['Northing'] = converted_gdf.map(lambda p: p.x), converted_gdf.map(lambda p: p.y)

        return grid

    def get_loop_corners(self):
        """
        Return the coordinates of the loop corners
        :return: list of (x, y)
        """
        x, y = self.loop_roi.pos()
        w, h = self.loop_roi.size()
        angle = self.loop_roi.angle()
        c1 = (x, y)
        c2 = (c1[0] + w * (math.cos(math.radians(angle))), c1[1] + w * (math.sin(math.radians(angle))))
        c3 = (c2[0] - h * (math.sin(math.radians(angle))), c2[1] + h * (math.sin(math.radians(90-angle))))
        c4 = (c3[0] + w * (math.cos(math.radians(180-angle))), c3[1] - w * (math.sin(math.radians(180-angle))))
        corners = [c1, c2, c3, c4]

        return corners

    def get_loop_lonlat(self):
        """
        Return the lat lon data frame of the loop corners
        :return: dataframe
        """
        epsg = self.get_epsg()

        if not epsg:
            self.message.critical(self, 'Invalid CRS', 'Input CRS is invalid.')
            return pd.DataFrame()
        else:
            crs = CRS.from_epsg(epsg)

        # Get the loop data
        loop = pd.DataFrame(self.get_loop_corners(), columns=['Easting', 'Northing'])
        loop = loop.append(loop.iloc[0])  # Close the loop

        # Create point objects for each coordinate
        mpoints = asMultiPoint(loop.loc[:, ['Easting', 'Northing']].to_numpy())
        gdf = gpd.GeoSeries(list(mpoints), crs=crs)

        # Convert to lat lon
        converted_gdf = gdf.to_crs(epsg=4326)
        loop['Easting'], loop['Northing'] = converted_gdf.map(lambda p: p.x), converted_gdf.map(lambda p: p.y)

        return loop

    def view_map(self):
        """
        View the hole and loop in a Plotly mapbox interactive map. A screen capture of the map can be
        saved with 'Ctrl+S' or copied to the clipboard with 'Ctrl+C'
        """

        def plot_line(line):
            line_name = line.Line_name.unique()[0].strip()
            terrain_map.map_figure.add_trace(go.Scattermapbox(lon=line.Easting,
                                                              lat=line.Northing,
                                                              mode='lines+markers',
                                                              name=line_name,
                                                              text=line.Station
                                                              ))

        global terrain_map
        terrain_map = MapboxViewer()

        loop_coords = self.get_loop_lonlat()
        grid = self.get_grid_lonlat()

        if loop_coords.empty and grid.empty:
            logger.error(f"No GPS to plot.")
            return

        loop_name = 'Loop' if self.loop_name_edit.text() == '' else self.loop_name_edit.text()

        # Plot the lines
        grid.groupby('Line_name').apply(plot_line)
        # Plot the loop
        terrain_map.map_figure.add_trace(go.Scattermapbox(lon=loop_coords.Easting,
                                                          lat=loop_coords.Northing,
                                                          mode='lines+markers',
                                                          name=loop_name,
                                                          text=loop_coords.index
                                                          ))

        # Pass the mapbox token, for access to better map tiles. If none is passed, it uses the free open street map.
        token = open(".mapbox", 'r').read()
        if not token:
            logger.warning(f"No Mapbox token passed.")
            map_style = "open-street-map"
        else:
            map_style = "outdoors"

        # Format the figure margins and legend
        terrain_map.map_figure.update_layout(
            margin={"r": 0,
                    "t": 0,
                    "l": 0,
                    "b": 0},
            legend=dict(
                yanchor="top",
                y=0.99,
                xanchor="left",
                x=0.01,
                bordercolor="Black",
                borderwidth=1
            ),
        )
        # Add the map style and center/zoom the map
        terrain_map.map_figure.update_layout(
            mapbox={
                'center': {'lon': loop_coords.Easting.mean(), 'lat': loop_coords.Northing.mean()},
                'zoom': 13},
            mapbox_style=map_style,
            mapbox_accesstoken=token)

        terrain_map.load_page()
        terrain_map.show()

    def save_kmz(self):
        """
        Save the loop and grid lines/stations to a KMZ file.
        :return: None
        """
        kml = simplekml.Kml()

        loop_style = simplekml.Style()
        loop_style.linestyle.width = 4
        loop_style.linestyle.color = simplekml.Color.yellow

        trace_style = simplekml.Style()
        trace_style.linestyle.width = 2
        trace_style.linestyle.color = simplekml.Color.magenta

        station_style = simplekml.Style()
        station_style.iconstyle.icon.href = 'http://maps.google.com/mapfiles/kml/shapes/placemark_circle.png'
        station_style.iconstyle.color = simplekml.Color.magenta

        grid_name = self.grid_name_edit.text()
        if not grid_name:
            grid_name = 'Grid'
        grid_folder = kml.newfolder(name=grid_name)

        # Save the loop if the checkbox is checked
        if self.include_loop_cbox.isChecked():
            loop_name = self.loop_name_edit.text()
            if not loop_name:
                loop_name = 'Loop'

            # Creates KMZ objects for the loop.
            loop = self.get_loop_lonlat()
            if not loop.empty:
                ls = grid_folder.newlinestring(name=loop_name)
                ls.coords = loop.to_numpy()
                ls.extrude = 1
                ls.style = loop_style

        def grid_to_kmz(group):
            """
            Plot a line to KMZ
            :param group: data frame of a single line.
            """
            line_name = group.Line_name.unique()[0]
            line_coords = group.loc[:, ['Easting', 'Northing', 'Station']].to_numpy()
            line_folder = grid_folder.newfolder(name=line_name)
            kmz_line_coords = []

            # Plot the stations
            for lon, lat, station_name in line_coords:
                new_point = line_folder.newpoint(name=f"{station_name}", coords=[(lon, lat)])
                new_point.style = station_style
                kmz_line_coords.append((lon, lat))

            # Plot the line
            ls = line_folder.newlinestring(name=line_name)
            ls.coords = line_coords
            ls.extrude = 1
            ls.style = trace_style

        # Creates KMZ object for the lines and stations
        grid = self.get_grid_lonlat()
        grid.groupby('Line_name').apply(grid_to_kmz)

        save_dir = self.dialog.getSaveFileName(self, 'Save KMZ File', grid_name, 'KMZ Files (*.KMZ)')[0]
        if save_dir:
            kmz_save_dir = os.path.splitext(save_dir)[0] + '.kmz'
            kml.savekmz(kmz_save_dir, format=False)
            self.status_bar.showMessage('Save complete.', 1000)
            try:
                logger.info(f"Saving {Path(save_dir).name}.")
                os.startfile(save_dir)
            except OSError:
                logger.error(f'No application to open {save_dir}.')
                pass

    def save_gpx(self):
        """
        Save the loop and collar coordinates to a GPX file.
        :return: None
        """
        gpx = gpxpy.gpx.GPX()

        grid_name = self.grid_name_edit.text()
        if not grid_name:
            grid_name = 'Grid'

        # Save the loop if the checkbox is checked
        if self.include_loop_cbox.isChecked():
            loop_name = self.loop_name_edit.text()
            if not loop_name:
                loop_name = 'Loop'

            # Add the loop coordinates to the GPX. Creates a route for the loop and adds the corners as waypoints.
            def loop_to_gpx(row):
                """
                Create a gpx waypoint object for each data row
                :param row: series, converted data row
                """
                waypoint = gpxpy.gpx.GPXWaypoint(latitude=row.Northing,
                                                 longitude=row.Easting,
                                                 name=loop_name)
                gpx.waypoints.append(waypoint)
                route.points.append(waypoint)

            loop = self.get_loop_lonlat()
            if loop.empty:
                return
            # Create the GPX waypoints
            route = gpxpy.gpx.GPXRoute()
            loop.apply(loop_to_gpx, axis=1)
            gpx.routes.append(route)

        def grid_to_gpx(row):
            """
            Create a gpx waypoint object for each station
            :param row: series, line station
            """
            waypoint = gpxpy.gpx.GPXWaypoint(latitude=row.Northing,
                                             longitude=row.Easting,
                                             name=f"L{row.Line_name}-{row.Station}",
                                             description=row.Station)
            gpx.waypoints.append(waypoint)

        # Add the line coordinates to the GPX as a waypoint.
        grid = self.get_grid_lonlat()
        grid.apply(grid_to_gpx, axis=1)

        save_path = self.dialog.getSaveFileName(self, 'Save GPX File', grid_name, 'GPX Files (*.GPX)')[0]
        if save_path:
            with open(save_path, 'w') as f:
                f.write(gpx.to_xml())
            self.status_bar.showMessage('Save complete.', 1000)
            try:
                logger.info(f"Saving {Path(save_path).name}.")
                os.startfile(save_path)
            except OSError:
                logger.error(f'No application to open {save_path}.')
                pass

    def copy_grid_to_clipboard(self):
        """
        Copy the grid station coordinates to the clipboard.
        :return: None
        """
        crs_str = f"{self.gps_system_cbox.currentText()} Zone {self.gps_zone_cbox.currentText()}, {self.gps_datum_cbox.currentText()}"
        result = crs_str + '\n'
        for line in self.lines:
            line_name = line['line_name']
            coords = line['station_coords']
            result += f"Line {line_name.strip()}" + '\n'
            for point in coords:
                result += f"{point[0]:.0f} E, {point[1]:.0f} N, {point[2]}" + '\n'
            result += '\n'
        cb = QtGui.QApplication.clipboard()
        cb.clear(mode=cb.Clipboard)
        cb.setText(result, mode=cb.Clipboard)
        self.status_bar.showMessage('Grid coordinates copied to clipboard', 1000)


class LoopROI(pg.RectROI):
    """
    Custom ROI for transmitter loops. Created in order to change the color of the ROI lines when highlighted.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _makePen(self):
        # Generate the pen color for this ROI based on its current state.
        if self.mouseHovering:
            # style=QtCore.Qt.DashLine,
            return pg.mkPen(self.pen.color(), width=2)
        else:
            return self.pen


class CustomAxis(pg.AxisItem):
    """
    Custom pyqtgraph axis used for Loop Planner plan view
    """

    def __init__(self, *args, **kwargs):
        pg.AxisItem.__init__(self, *args, **kwargs)

    def tickStrings(self, values, scale, spacing):
        """Return the strings that should be placed next to ticks. This method is called
        when redrawing the axis and is a good method to override in subclasses.
        The method is called with a list of tick values, a scaling factor (see below), and the
        spacing between ticks (this is required since, in some instances, there may be only
        one tick and thus no other way to determine the tick spacing)

        The scale argument is used when the axis label is displaying units which may have an SI scaling prefix.
        When determining the text to display, use value*scale to correctly account for this prefix.
        For example, if the axis label's units are set to 'V', then a tick value of 0.001 might
        be accompanied by a scale value of 1000. This indicates that the label is displaying 'mV', and
        thus the tick should display 0.001 * 1000 = 1.
        """
        if self.logMode:
            return self.logTickStrings(values, scale, spacing)

        letter = 'N' if self.orientation == 'left' else 'E'
        places = max(0, np.ceil(-np.log10(spacing * scale)))
        strings = []
        for v in values:
            vs = v * scale
            if abs(vs) < .001 or abs(vs) >= 10000:
                vstr = f"{vs:.0f}{letter}"
            else:
                vstr = ("%%0.%df" % places) % vs
            strings.append(vstr)
        return strings


def main():
    app = QApplication(sys.argv)
    planner = LoopPlanner2()
    # planner = GridPlanner()

    # planner.gps_system_cbox.setCurrentIndex(2)
    # planner.gps_datum_cbox.setCurrentIndex(1)
    # planner.gps_zone_cbox.setCurrentIndex(16)
    planner.show()
    # planner.hole_az_edit.setText('174')
    # planner.view_map()
    # planner.save_gpx()

    app.exec_()


if __name__ == '__main__':
    main()


