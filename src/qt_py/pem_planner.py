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
import simplekml
from PySide2 import QtGui, QtCore, QtUiTools
from PySide2.QtWidgets import (QApplication, QMainWindow, QFileDialog, QShortcut, QLabel, QMessageBox, QInputDialog,
                               QLineEdit, QFormLayout, QWidget, QFrame, QPushButton, QGroupBox, QHBoxLayout,
                               QRadioButton,
                               QGridLayout)
import pyqtgraph as pg
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib import patheffects
import matplotlib.transforms as mtransforms
from pyproj import CRS
from shapely.geometry import asMultiPoint

from src.logger import Log
from src.gps.gps_editor import BoreholeCollar, BoreholeGeometry
from src.geometry.segment import Segmenter
from src.qt_py.custom_qt_widgets import NonScientific, PlanMapAxis
from src.mag_field.mag_field_calculator import MagneticFieldCalculator
from src.qt_py.map_widgets import TileMapViewer

logger = logging.getLogger(__name__)

if getattr(sys, 'frozen', False):
    application_path = Path(sys.executable).parent
else:
    application_path = Path(__file__).absolute().parents[1]
icons_path = application_path.joinpath("ui\\icons")

# Load Qt ui file into a class
Ui_LoopPlannerWindow, _ = QtUiTools.loadUiType(str(application_path.joinpath('ui\\loop_planner.ui')))
Ui_GridPlannerWindow, _ = QtUiTools.loadUiType(str(application_path.joinpath('ui\\grid_planner.ui')))

pg.setConfigOptions(antialias=True)
pg.setConfigOption('background', 'w')
pg.setConfigOption('foreground', 'k')
pg.setConfigOption('crashWarning', True)

default_color = (0, 0, 0, 150)
selection_color = '#1976D2'

# TODO add feature to import loop with corner coordinates (and disable width and height).


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
        self.map_viewer = TileMapViewer(parent=self)

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
    name_changed_sig = QtCore.Signal(str)
    plot_hole_sig = QtCore.Signal()

    def __init__(self, properties, plot_widget, name=''):
        """
        Widget representing a hole as tab in Loop Planner.
        :param properties: dict, properties of a previous hole to be used as a starting point.
        :param plot_widget: pyqtgraph plot widget to plot on.
        :param name: str, name of the hole.
        """
        super().__init__()
        self.segmenter = Segmenter()

        layout = QFormLayout()
        self.setLayout(layout)
        self.plan_view = plot_widget
        self.projection = pd.DataFrame()
        self.segments = None
        self.section_length = None

        if not properties:
            properties = {
                'easting': 599709,
                'northing': 4829107,
                'elevation': 0,
                'azimuth': 0,
                'dip': 60,
                'length': 400,
            }

        # Create all the inner widget items
        # Position
        position_gbox = QGroupBox('Position')
        position_gbox.setLayout(QFormLayout())
        position_gbox.setFlat(True)
        self.hole_easting_edit = QLineEdit(str(int(properties.get('easting'))))
        self.hole_northing_edit = QLineEdit(str(int(properties.get('northing'))))
        self.hole_elevation_edit = QLineEdit(str(int(properties.get('elevation'))))
        position_gbox.layout().addRow('Easting', self.hole_easting_edit)
        position_gbox.layout().addRow('Northing', self.hole_northing_edit)
        position_gbox.layout().addRow('Elevation\nFrom Loop', self.hole_elevation_edit)
        self.layout().addRow(position_gbox)

        # Geometry
        geometry_gbox = QGroupBox('Geometry')
        geometry_gbox.setFlat(True)
        geometry_gbox.setLayout(QGridLayout())
        geometry_gbox.layout().setContentsMargins(0, 0, 0, 0)
        geometry_gbox.layout().setVerticalSpacing(0)

        self.manual_geometry_rbtn = QRadioButton()
        self.manual_geometry_rbtn.setChecked(True)
        self.dad_geometry_rbtn = QRadioButton()

        # Manual geometry frame
        manual_geometry_frame = QFrame()
        manual_geometry_frame.setLayout(QFormLayout())
        manual_geometry_frame.setContentsMargins(0, 0, 0, 0)
        self.hole_azimuth_edit = QLineEdit(str(int(properties.get('azimuth'))))
        self.hole_dip_edit = QLineEdit(str(int(properties.get('dip'))))
        self.hole_length_edit = QLineEdit(str(int(properties.get('length'))))
        manual_geometry_frame.layout().addRow('Azimuth', self.hole_azimuth_edit)
        manual_geometry_frame.layout().addRow('Dip', self.hole_dip_edit)
        manual_geometry_frame.layout().addRow('Length', self.hole_length_edit)

        # DAD file frame
        dad_geometry_frame = QFrame()
        dad_geometry_frame.setLayout(QHBoxLayout())
        dad_geometry_frame.setContentsMargins(0, 0, 0, 0)
        self.dad_file_edit = QLineEdit()
        self.dad_file_edit.setEnabled(False)
        self.dad_file_edit.setReadOnly(True)
        self.add_dad_file_btn = QPushButton('...')
        # self.add_dad_file_btn.setEnabled(False)
        self.add_dad_file_btn.setMaximumWidth(23)
        dad_geometry_frame.layout().addWidget(QLabel('DAD File'))
        dad_geometry_frame.layout().addWidget(self.dad_file_edit)
        dad_geometry_frame.layout().addWidget(self.add_dad_file_btn)

        geometry_gbox.layout().addWidget(self.manual_geometry_rbtn, 0, 0)
        geometry_gbox.layout().addWidget(manual_geometry_frame, 0, 1)
        geometry_gbox.layout().addWidget(self.dad_geometry_rbtn, 1, 0)
        geometry_gbox.layout().addWidget(dad_geometry_frame, 1, 1)
        self.layout().addRow(geometry_gbox)

        # Hole name
        self.hole_name_edit = QLineEdit(name)
        self.hole_name_edit.setPlaceholderText('(Optional)')

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
        # Hole collar
        self.hole_collar = pg.ScatterPlotItem(clickable=True,
                                              pen=pg.mkPen(default_color, width=1.),
                                              symbol='o',
                                              brush=pg.mkBrush('w'),
                                              )
        self.hole_collar.setZValue(5)

        # Hole trace
        self.hole_trace = pg.PlotCurveItem(clickable=True, pen=pg.mkPen(default_color, width=1.))
        self.hole_trace.setZValue(4)

        # The end bar
        self.hole_end = pg.ArrowItem(headLen=0,
                                     tailLen=0,
                                     tailWidth=15,
                                     pen=pg.mkPen(default_color, width=1.),
                                     )
        self.hole_end.setZValue(5)

        # Hole name
        self.hole_name = pg.TextItem(name, anchor=(-0.15, 0.5), color=(0, 0, 0, 150))
        self.hole_name.setZValue(100)

        # Add a single section line to be used by all holes
        self.section_extent_line = pg.PlotDataItem(width=1,
                                                   pen=pg.mkPen(color=0.5,
                                                                style=QtCore.Qt.DashLine))
        self.hole_end.setZValue(1)

        self.plan_view.addItem(self.hole_collar)
        self.plan_view.addItem(self.hole_trace)
        self.plan_view.addItem(self.hole_end, ignoreBounds=True)
        self.plan_view.addItem(self.hole_name, ignoreBounds=True)
        self.plan_view.addItem(self.section_extent_line)

        self.calc_hole_projection()
        self.draw_hole()

        # Signals
        def toggle_geometry():
            self.hole_azimuth_edit.setEnabled(self.manual_geometry_rbtn.isChecked())
            self.hole_dip_edit.setEnabled(self.manual_geometry_rbtn.isChecked())
            self.hole_length_edit.setEnabled(self.manual_geometry_rbtn.isChecked())

            self.dad_file_edit.setEnabled(self.dad_geometry_rbtn.isChecked())

            # Update the plots
            self.calc_hole_projection()
            self.draw_hole()
            self.plot_hole_sig.emit()

        # Radio buttons
        self.manual_geometry_rbtn.toggled.connect(toggle_geometry)
        self.dad_geometry_rbtn.toggled.connect(toggle_geometry)

        # Buttons
        self.add_dad_file_btn.clicked.connect(self.get_dad_file)

        # Editing
        self.hole_name_edit.textChanged.connect(self.name_changed_sig.emit)
        self.hole_name_edit.textChanged.connect(lambda: self.hole_name.setText(self.hole_name_edit.text()))

        self.hole_easting_edit.editingFinished.connect(self.calc_hole_projection)
        self.hole_easting_edit.editingFinished.connect(self.draw_hole)
        self.hole_northing_edit.editingFinished.connect(self.calc_hole_projection)
        self.hole_northing_edit.editingFinished.connect(self.draw_hole)
        self.hole_elevation_edit.editingFinished.connect(self.calc_hole_projection)
        self.hole_elevation_edit.editingFinished.connect(self.draw_hole)
        self.hole_azimuth_edit.editingFinished.connect(self.calc_hole_projection)
        self.hole_azimuth_edit.editingFinished.connect(self.draw_hole)
        self.hole_dip_edit.editingFinished.connect(self.calc_hole_projection)
        self.hole_dip_edit.editingFinished.connect(self.draw_hole)
        self.hole_length_edit.editingFinished.connect(self.calc_hole_projection)
        self.hole_length_edit.editingFinished.connect(self.draw_hole)

    def select(self):
        self.hole_collar.setPen(pg.mkPen(selection_color, width=1.5))
        self.hole_collar.setSize(12)
        self.hole_collar.setZValue(10)

        self.hole_trace.setPen(pg.mkPen(selection_color, width=1.5))
        self.hole_trace.setShadowPen(pg.mkPen('w', width=3.))
        self.hole_trace.setZValue(9)

        self.hole_end.setPen(pg.mkPen(selection_color, width=1.5))

        self.hole_name.setColor(selection_color)

    def deselect(self):
        self.hole_collar.setPen(pg.mkPen(default_color, width=1.))
        self.hole_collar.setSize(11)
        self.hole_collar.setZValue(5)

        self.hole_trace.setPen(pg.mkPen(default_color, width=1.))
        self.hole_trace.setShadowPen(None)
        self.hole_trace.setZValue(4)

        self.hole_end.setPen(pg.mkPen(default_color, width=1.))

        self.hole_name.setColor(default_color)

    def remove(self):
        self.plan_view.removeItem(self.hole_collar)
        self.plan_view.removeItem(self.hole_trace)
        self.plan_view.removeItem(self.hole_end)
        self.plan_view.removeItem(self.hole_name)
        self.plan_view.removeItem(self.section_extent_line)
        self.deleteLater()

    def get_properties(self):
        """Return a dictionary of hole properties"""
        return {
            'easting': self.hole_easting_edit.text(),
            'northing': self.hole_northing_edit.text(),
            'elevation': self.hole_elevation_edit.text(),
            'azimuth': self.hole_azimuth_edit.text(),
            'dip': self.hole_dip_edit.text(),
            'length': self.hole_length_edit.text(),
        }

    def calc_hole_projection(self):
        """
        Calculate and update the 3D projection of the hole.
        """
        # Reset the current projection, so there isn't a length error later
        self.projection = self.projection.iloc[0:0]

        x = float(self.hole_easting_edit.text())
        y = float(self.hole_northing_edit.text())
        z = float(self.hole_elevation_edit.text())
        collar = BoreholeCollar([[x, y, z, '0']])  # Float so it doesn't get removed when parsing collar

        # Using the manual user-input settings
        if self.manual_geometry_rbtn.isChecked():
            length = float(self.hole_length_edit.text())
            azimuth = float(self.hole_azimuth_edit.text())
            dip = float(self.hole_dip_edit.text())
            df = pd.DataFrame({'Depth': [z, length],
                               'Azimuth': [azimuth] * 2,
                               'Dip': [dip] * 2})
            segments = self.segmenter.dad_to_seg(df)
        # Using a DAD file
        else:
            if not self.segments:
                logger.warning(f"Cannot calculate hole project without segments.")
                self.projection = self.projection.iloc[0:0]
                return

            segments = self.segments

        # Get projection of DAD file by creating a BoreholeGeometry object
        geometry = BoreholeGeometry(collar, segments)
        self.projection = geometry.get_projection()

    def get_section_extents(self):
        """
        Calculates the two coordinates to be used for the section plot.
        :return: (x, y) tuples of the two end-points.
        """

        if self.projection.empty:
            return None, None

        azimuth = self.get_azimuth()

        # Calculate the length of the cross-section
        if self.manual_geometry_rbtn.isChecked():
            hole_length = int(self.hole_length_edit.text())
        else:
            hole_length = int(self.segments.df.Depth.iloc[-1])
        self.section_length = math.ceil(hole_length / 100) * 100  # Nearest 100

        # Distance of the hole collar to the bottom of the hole as projected on the surface
        dist = math.hypot(self.projection.Easting.iloc[-1] - self.projection.Easting.iloc[0],
                          self.projection.Northing.iloc[-1] - self.projection.Northing.iloc[0])

        # Ensure the section length is at least twice the length of dist to make sure the collar is within the section
        while not self.section_length >= 2 * dist:
            self.section_length *= 2

        # Find the coordinate that is 80% down the hole
        if 90 < azimuth < 180:
            line_center_x = np.percentile(self.projection.Easting, 80)
            line_center_y = np.percentile(self.projection.Northing, 20)
        elif 180 < azimuth < 270:
            line_center_x = np.percentile(self.projection.Easting, 20)
            line_center_y = np.percentile(self.projection.Northing, 20)
        elif 270 < azimuth < 360:
            line_center_x = np.percentile(self.projection.Easting, 20)
            line_center_y = np.percentile(self.projection.Northing, 80)
        else:
            line_center_x = np.percentile(self.projection.Easting, 80)
            line_center_y = np.percentile(self.projection.Northing, 80)

        # Calculate the end point coordinates of the section line
        dx = math.sin(math.radians(azimuth)) * (self.section_length / 2)
        dy = math.cos(math.radians(azimuth)) * (self.section_length / 2)
        p1 = np.array([line_center_x - dx, line_center_y - dy])
        p2 = np.array([line_center_x + dx, line_center_y + dy])

        # Plot the section line
        self.section_extent_line.setData([line_center_x - dx, line_center_x + dx],
                                         [line_center_y - dy, line_center_y + dy])

        return p1, p2

    def get_azimuth(self):
        xs, ys = self.projection.Easting.to_numpy(), self.projection.Northing.to_numpy()
        azimuth = math.degrees(math.atan2((xs[-1] - xs[-2]), (ys[-1] - ys[-2])))
        if azimuth < 0:
            azimuth = azimuth + 360
        return azimuth

    def get_proj_latlon(self, crs):
        """
        Return the lat lon data frame of the hole projection
        :param crs: User selected CRS
        :return: dataframe
        """
        proj = self.projection

        # Create point objects for each coordinate
        mpoints = asMultiPoint(proj.loc[:, ['Easting', 'Northing']].to_numpy())
        gdf = gpd.GeoSeries(list(mpoints), crs=crs)

        # Convert to lat lon
        converted_gdf = gdf.to_crs(epsg=4326)
        proj['Easting'], proj['Northing'] = converted_gdf.map(lambda p: p.x), converted_gdf.map(lambda p: p.y)
        return proj

    def get_dad_file(self):
        """
        Open a DAD file through the file dialog
        """

        def open_dad_file(filepath):
            """
            Parse a depth-azimuth-dip file. Can be extentions xlsx, xls, csv, txt, dad.
            :param filepath: str, filepath of the DAD file
            """
            try:
                if filepath.endswith('xlsx') or filepath.endswith('xls'):
                    df = pd.read_excel(filepath,
                                       # delim_whitespace=True,
                                       usecols=[0, 1, 2],
                                       names=['Depth', 'Azimuth', 'Dip'],
                                       header=None,
                                       dtype=float)
                else:
                    df = pd.read_csv(filepath,
                                     delim_whitespace=True,
                                     usecols=[0, 1, 2],
                                     names=['Depth', 'Azimuth', 'Dip'],
                                     header=None,
                                     dtype=float)
            except Exception as e:
                logger.error(f"The following error occurred trying to read {Path(filepath).name}:{str(e)}")
                self.message.critical(self, 'Import Error',
                                      f"The following error occurred trying to read {Path(filepath).name}:{str(e)}")

            else:
                if all([d == float for d in df.dtypes]):
                    # Update the dad file path
                    self.dad_file_edit.setText(filepath)
                    # Flip the dip so down is positive
                    df.Dip = df.Dip * -1
                    # Create a BoreholeSegment object from the DAD file, to more easily calculate the projection
                    self.segments = self.segmenter.dad_to_seg(df.dropna())
                    # Update the hole projection
                    self.calc_hole_projection()
                    # Draw the hole and update the section plot
                    self.draw_hole()
                    self.plot_hole_sig.emit()

                    self.window().status_bar.showMessage(f"DAD file imported successfully.", 1000)

                else:
                    logger.error(f'Data in {Path(filepath).name} is not float. Make sure there is no header row.')
                    self.message.information(self, 'Error',
                                             'Data returned is not float. Make sure there is no header row.')

        file_name, file_type = QFileDialog.getOpenFileName(self, 'Open File',
                                                           filter='Depth-azimuth-dip file (*.dad);; '
                                                                  'Comma-separated file (*.csv);; '
                                                                  'Text file (*.txt);; '
                                                                  'Excel file (*.xlsx);; '
                                                                  'Excel file (*.xls)'
                                                           )
        if file_name != '':
            open_dad_file(file_name)

    def draw_hole(self):
        """
        Draw the hole in the plan view.
        """
        # Plot the collar
        self.hole_collar.setData([int(self.hole_easting_edit.text())], [int(self.hole_northing_edit.text())])

        # Plot the name
        self.hole_name.setPos(int(self.hole_easting_edit.text()), int(self.hole_northing_edit.text()))

        if not self.projection.empty:
            # Plot the trace
            self.hole_trace.setData(self.projection.Easting.to_numpy(), self.projection.Northing.to_numpy())
            self.hole_trace.show()

            # Plot the end of the hole
            self.hole_end.setPos(self.projection.Easting.iloc[-1], self.projection.Northing.iloc[-1])
            angle = self.get_azimuth()
            self.hole_end.show()
            self.hole_end.setStyle(angle=angle + 90,
                                   pen=self.hole_trace.opts['pen'])
        else:
            self.hole_trace.hide()
            self.hole_end.hide()

        self.plot_hole_sig.emit()


class LoopWidget(QWidget):
    name_changed_sig = QtCore.Signal(str)
    plot_hole_sig = QtCore.Signal()

    def __init__(self, properties, center, plot_widget, name=''):
        """
        Widget representing a loop as tab in Loop Planner.
        :param properties: dict, properties of a previous loop to be used as a starting point.
        :param center: tuple of int, centre position of the loop ROI.
        :param plot_widget: pyqtgraph plot widget to plot on.
        :param name: str, name of the loop.
        """
        super().__init__()

        layout = QFormLayout()
        self.setLayout(layout)
        self.plan_view = plot_widget

        if not properties:
            properties = {
                'height': 500,
                'width': 500,
                'angle': 0,
            }

        # Create all the inner widget items
        self.loop_height_edit = QLineEdit(str(int(properties.get('height'))))
        self.loop_width_edit = QLineEdit(str(int(properties.get('width'))))
        self.loop_angle_edit = QLineEdit(str(int(properties.get('angle'))))

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

        self.copy_loop_btn = QPushButton(QtGui.QIcon(str(Path(icons_path, 'copy.png'))), "Copy Corners")
        self.layout().addRow(self.copy_loop_btn)

        # Validators
        self.size_validator = QtGui.QIntValidator()
        self.size_validator.setBottom(1)
        self.loop_angle_validator = QtGui.QIntValidator()
        self.loop_angle_validator.setRange(0, 360)

        # Set all validators
        self.loop_height_edit.setValidator(self.size_validator)
        self.loop_width_edit.setValidator(self.size_validator)
        self.loop_angle_edit.setValidator(self.loop_angle_validator)

        # Set the position of the loop by the center (and not the bottom-left corner)
        h = int(properties.get('height'))
        w = int(properties.get('width'))
        pos = QtCore.QPointF(center.x() - (w / 2), center.y() - (h / 2))  # Adjusted position for the center

        self.loop_roi = LoopROI(pos,
                                size=(h, w),
                                scaleSnap=True,
                                snapSize=5,
                                centered=True,
                                pen=pg.mkPen(default_color, width=1.),
                                handlePen=pg.mkPen(50, 50, 50, 100),
                                handleHoverPen=pg.mkPen(50, 50, 50, 255),
                                )

        self.loop_roi.setZValue(15)
        self.loop_roi.addRotateHandle(pos=[1, 0.5], center=[0.5, 0.5])
        self.loop_roi.setAcceptedMouseButtons(QtCore.Qt.LeftButton)

        # Add loop name
        self.loop_name = pg.TextItem(name, anchor=(0.5, 0.5), color=(0, 0, 0, 100))
        self.loop_name.setZValue(0)

        # Add the items to the plot
        self.plan_view.addItem(self.loop_roi)
        self.plan_view.addItem(self.loop_name, ignoreBounds=True)
        self.plot_loop_name()

        # Signals
        self.loop_height_edit.editingFinished.connect(self.update_loop_roi)
        self.loop_width_edit.editingFinished.connect(self.update_loop_roi)
        self.loop_angle_edit.editingFinished.connect(self.update_loop_roi)

        self.loop_name_edit.textChanged.connect(self.name_changed_sig.emit)
        self.loop_name_edit.textChanged.connect(lambda: self.loop_name.setText(self.loop_name_edit.text()))
        self.loop_roi.sigRegionChanged.connect(self.update_loop_values)
        self.loop_roi.sigRegionChanged.connect(self.plot_loop_name)
        self.loop_roi.sigRegionChangeFinished.connect(lambda: self.plot_hole_sig.emit())

    def select(self):
        """When the loop is selected"""
        self.loop_roi.setPen(selection_color, width=1.5)
        self.loop_name.setColor(selection_color)

    def deselect(self):
        self.loop_roi.setPen(pg.mkPen(default_color), width=1.)
        self.loop_name.setColor(default_color)

    def remove(self):
        self.plan_view.removeItem(self.loop_roi)
        self.plan_view.removeItem(self.loop_name)
        self.deleteLater()

    def get_loop_coords(self):
        """
        Return the coordinates of the corners of the loop.
        :return: list of QtCore.QPointF objects.
        """
        x, y = self.loop_roi.pos()
        w, h = self.loop_roi.size()
        angle = self.loop_roi.angle()

        c1 = QtCore.QPointF(x, y)
        c2 = QtCore.QPointF(c1.x() + w * (math.cos(math.radians(angle))), c1.y() + w * (math.sin(math.radians(angle))))
        c3 = QtCore.QPointF(c2.x() - h * (math.sin(math.radians(angle))), c2.y() + h * (math.sin(math.radians(90-angle))))
        c4 = QtCore.QPointF(c3.x() + w * (math.cos(math.radians(180-angle))), c3.y() - w * (math.sin(math.radians(180-angle))))
        corners = [c1, c2, c3, c4]
        return corners

    def get_loop_coords_latlon(self, crs):
        """
        Return the coordinates of the loop as lat lon.
        :param crs: User selected CRS object
        :return: dataframe
        """
        # Get the loop data
        loop = pd.DataFrame([[c.x(), c.y(), 0] for c in self.get_loop_coords()],
                            columns=['Easting', 'Northing', 'Elevation'])
        loop = loop.append(loop.iloc[0])  # Close the loop

        # Create point objects for each coordinate
        mpoints = asMultiPoint(loop.loc[:, ['Easting', 'Northing']].to_numpy())
        gdf = gpd.GeoSeries(list(mpoints), crs=crs)

        # Convert to lat lon
        converted_gdf = gdf.to_crs(epsg=4326)
        loop['Easting'], loop['Northing'] = converted_gdf.map(lambda p: p.x), converted_gdf.map(lambda p: p.y)
        return loop

    def get_loop_center(self):
        """
        Return the coordinates of the center of the loop.
        :return: QtCore.QPointF
        """
        corners = self.get_loop_coords()
        xs = np.array([c.x() for c in corners])
        ys = np.array([c.y() for c in corners])

        center = QtCore.QPointF(xs.mean(), ys.mean())
        return center

    def get_properties(self):
        """Return a dictionary of loop properties"""
        return {
            'height': self.loop_height_edit.text(),
            'width': self.loop_width_edit.text(),
            'angle': self.loop_angle_edit.text(),
        }

    def plot_loop_name(self):
        center = self.get_loop_center()
        # self.loop_center.setData([center.x()], [center.y()])
        self.loop_name.setPos(center.x(), center.y())

    def update_loop_roi(self):
        """
        Signal slot, change the loop ROI object based on the user input values.
        """
        self.loop_roi.blockSignals(True)

        # Change the loop ROI
        h = int(self.loop_height_edit.text())
        w = int(self.loop_width_edit.text())
        a = int(self.loop_angle_edit.text())

        self.loop_roi.setSize((w, h))
        self.loop_roi.setAngle(a)

        # Update the loop name position
        self.plot_loop_name()

        self.loop_roi.blockSignals(False)

        # Update the section plot
        self.plot_hole_sig.emit()

    def update_loop_values(self):
        """
        Signal slot: Updates the values of the loop width, height and angle when the loop ROI is changed, then
        replots the section plot.
        """
        self.loop_width_edit.blockSignals(True)
        self.loop_height_edit.blockSignals(True)
        self.loop_angle_edit.blockSignals(True)
        w, h = self.loop_roi.size()
        angle = self.loop_roi.angle()
        self.loop_width_edit.setText(f"{w:.0f}")
        self.loop_height_edit.setText(f"{h:.0f}")
        self.loop_angle_edit.setText(f"{angle:.0f}")
        self.loop_width_edit.blockSignals(False)
        self.loop_height_edit.blockSignals(False)
        self.loop_angle_edit.blockSignals(False)


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
        self.resize(1500, 800)
        # self.installEventFilter(self)
        self.status_bar.show()

        # Status bar
        self.status_bar.addPermanentWidget(self.epsg_label, 0)

        self.plan_view.setMenuEnabled(False)
        self.hole_tab_widget.setTabsClosable(True)
        self.loop_tab_widget.setTabsClosable(True)

        # Plotting
        self.selected_hole = None
        self.selected_loop = None

        self.loop_widgets = []
        self.hole_widgets = []

        self.section_figure = Figure()
        self.ax = self.section_figure.add_subplot()
        self.section_canvas = FigureCanvas(self.section_figure)
        self.section_view_layout.addWidget(self.section_canvas)

        self.add_hole('Hole')
        # self.add_loop('Loop')

        # Signals
        # Tabs
        self.hole_tab_widget.tabCloseRequested.connect(self.remove_hole)
        self.loop_tab_widget.tabCloseRequested.connect(self.remove_loop)
        self.hole_tab_widget.currentChanged.connect(self.select_hole)
        self.loop_tab_widget.currentChanged.connect(self.select_loop)

        # Menu
        self.actionSave_as_KMZ.triggered.connect(self.save_kmz)
        self.actionSave_as_GPX.triggered.connect(self.save_gpx)
        self.view_map_action.triggered.connect(self.view_map)

        # Checkbox
        def toggle_annotations():
            for hole in self.hole_widgets:
                if self.show_annotations_cbox.isChecked():
                    hole.hole_name.show()
                else:
                    hole.hole_name.hide()

            for loop in self.loop_widgets:
                if self.show_annotations_cbox.isChecked():
                    loop.loop_name.show()
                else:
                    loop.loop_name.hide()

        self.show_annotations_cbox.toggled.connect(toggle_annotations)
        self.show_grid_cbox.toggled.connect(lambda: self.plan_view.showGrid(x=self.show_grid_cbox.isChecked(),
                                                                            y=self.show_grid_cbox.isChecked()))

        # Buttons
        self.add_hole_btn.clicked.connect(self.add_hole)
        self.add_loop_btn.clicked.connect(self.add_loop)

        # Qt size change
        # self.section_frame.resizeEvent = self.event

        self.init_crs()
        self.init_plan_view()
        self.init_section_view()

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
        self.plan_view.showGrid(x=self.show_grid_cbox.isChecked(), y=self.show_grid_cbox.isChecked(), alpha=0.2)
        self.plan_view.getViewBox().disableAutoRange('xy')
        self.plan_view.setAspectLocked()
        self.plan_view.hideButtons()
        self.plan_view.setLabel('left', 'Northing')
        self.plan_view.setLabel('bottom', 'Easting')
        self.plan_view.getAxis('left').enableAutoSIPrefix(enable=False)
        self.plan_view.getAxis('bottom').enableAutoSIPrefix(enable=False)
        self.plan_view.getAxis('right').setWidth(15)
        self.plan_view.getAxis('top').setHeight(15)
        self.plan_view.getAxis("bottom").nudge -= 10  # Move the label so it doesn't get clipped

        # Add the right and top borders
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
        self.ax.figure.subplots_adjust(left=0.1, bottom=0.02, right=0.98, top=0.98)
        self.ax.get_yaxis().set_visible(False)  # Hide the section plot until a loop is added.

    def event(self, e):
        if e.type() in [QtCore.QEvent.Show]:  # , QtCore.QEvent.Resize):
            self.plot_hole()

        return QMainWindow.event(self, e)

    def closeEvent(self, e):
        self.deleteLater()
        e.accept()

    def select_hole(self, ind):
        """
        Select a hole, ensuring the hole widget is highlighted and the tab is set to the correct page.
        :param ind: int, index of the hole
        """
        if ind == -1:
            print(f"No hole selected")
            self.selected_hole = None
        else:
            print(f"Hole {ind} selected")
            self.selected_hole = self.hole_widgets[ind]

            for i, widget in enumerate(self.hole_widgets):
                if i == ind:
                    widget.select()
                else:
                    widget.deselect()

        self.plot_hole()

    def select_loop(self, ind):
        """
        Select a loop, ensuring the loop widget is highlighted and the tab is set to the correct page.
        :param ind: int, index of the hole
        """
        if ind == -1:
            print(f"No loop selected")
            self.selected_loop = None
        else:
            print(f"loop {ind} selected")
            self.selected_loop = self.loop_widgets[ind]

            for i, widget in enumerate(self.loop_widgets):
                if i == ind:
                    widget.select()
                else:
                    widget.deselect()

        self.plot_hole()

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
            # Change the tab
            ind = self.hole_widgets.index(widget)
            self.hole_tab_widget.setCurrentIndex(ind)

            # Select the object
            for w in self.hole_widgets:
                if w == widget:
                    w.select()
                else:
                    w.deselect()

        if not name:
            name, ok_pressed = QInputDialog.getText(self, "Add Hole", "Hole name:", QLineEdit.Normal, "")
            if not ok_pressed:
                return

        if name != '':
            # Copy the information from the currently selected hole widget to be used in the new widget
            if self.hole_widgets:
                properties = self.hole_widgets[self.hole_tab_widget.currentIndex()].get_properties()
            else:
                properties = None

            # Create the hole widget for the tab
            hole_widget = HoleWidget(properties, self.plan_view, name=name)
            self.hole_widgets.append(hole_widget)
            hole_widget.name_changed_sig.connect(lambda: name_changed(hole_widget))
            hole_widget.hole_collar.sigClicked.connect(lambda: hole_clicked(hole_widget))
            hole_widget.plot_hole_sig.connect(self.plot_hole)
            self.hole_tab_widget.addTab(hole_widget, name)
            self.hole_tab_widget.setCurrentIndex(len(self.hole_widgets) - 1)

            # Select the hole if it is the only one open
            if self.hole_tab_widget.count() == 1:
                self.select_hole(0)

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
            ind = self.loop_widgets.index(widget)
            self.loop_tab_widget.setTabText(ind, widget.loop_name_edit.text())

        def loop_clicked(widget):
            """
            De-select all other loops.
            :param widget: The loop widget that was clicked
            """
            # Change the tab
            ind = self.loop_widgets.index(widget)
            self.loop_tab_widget.setCurrentIndex(ind)

            # Select the object
            for w in self.loop_widgets:
                if w == widget:
                    widget.select()
                else:
                    w.deselect()

        def loop_copied(widget):
            """
            Copy the loop coordinates to the clipboard.
            :param widget: Loop widget object
            """
            epsg = self.get_epsg()
            if epsg:
                crs_str = CRS.from_epsg(self.get_epsg()).name
            else:
                crs_str = 'No CRS selected'

            # Create a string from the loop corners
            result = crs_str + '\n'
            corners = widget.get_loop_coords()
            for point in corners:
                easting = f"{point.x():.0f} E"
                northing = f"{point.y():.0f} N"
                result += easting + ', ' + northing + '\n'

            # Add the string to the clipboard
            cb = QtGui.QApplication.clipboard()
            cb.clear(mode=cb.Clipboard)
            cb.setText(result, mode=cb.Clipboard)

            self.status_bar.showMessage('Loop corner coordinates copied to clipboard.', 1000)

        if not name:
            name, ok_pressed = QInputDialog.getText(self, "Add Loop", "Loop name:", QLineEdit.Normal, "")
            if not ok_pressed:
                return

        if name != '':
            # Copy the information from the currently selected hole widget to be used in the new widget
            if self.loop_widgets:
                properties = self.loop_widgets[self.loop_tab_widget.currentIndex()].get_properties()
            else:
                properties = None

            # Create the loop widget for the tab
            pos = self.plan_view.viewRect().center()
            loop_widget = LoopWidget(properties, pos, self.plan_view, name=name)
            self.loop_widgets.append(loop_widget)

            # Connect signals
            loop_widget.name_changed_sig.connect(lambda: name_changed(loop_widget))
            loop_widget.plot_hole_sig.connect(self.plot_hole)
            loop_widget.loop_roi.sigClicked.connect(lambda: loop_clicked(loop_widget))
            loop_widget.loop_roi.sigRegionChangeStarted.connect(lambda: loop_clicked(loop_widget))
            loop_widget.copy_loop_btn.clicked.connect(lambda: loop_copied(loop_widget))

            self.loop_tab_widget.addTab(loop_widget, name)
            self.loop_tab_widget.setCurrentIndex(len(self.loop_widgets) - 1)

            # Select the loop if it is the only one open
            if self.loop_tab_widget.count() == 1:
                self.select_loop(0)
                self.ax.get_yaxis().set_visible(True)

    def remove_hole(self, ind):
        response = QMessageBox.question(self, "Remove Hole", "Are you sure you want to remove this hole?",
                                        QMessageBox.Yes, QMessageBox.No)
        if response == QMessageBox.Yes:
            widget = self.hole_widgets[ind]
            widget.remove()
            del self.hole_widgets[ind]
            self.hole_tab_widget.removeTab(ind)

    def remove_loop(self, ind):
        response = QMessageBox.question(self, "Remove Loop", "Are you sure you want to remove this loop?",
                                        QMessageBox.Yes, QMessageBox.No)
        if response == QMessageBox.Yes:
            widget = self.loop_widgets[ind]
            widget.remove()
            del self.loop_widgets[ind]
            self.loop_tab_widget.removeTab(ind)

    def plot_hole(self):
        """
        Plots the hole on the plan plot and section plot, and plots the vector magnetic field on the section plot.
        :return: None
        """

        def plot_hole_section(proj):
            """
            Plot the hole trace
            :param proj: pd DataFrame, 3D projected hole trace of the geometry
            """

            def get_plane_projection(p1, p2, proj):
                """
                Projects each 3D point in proj to the plane defined by p1 and p2.
                :param p1: tuple, (x, y) point
                :param p2: tuple, (x, y) point
                :param proj: dataframe, 3D projected borehole trace
                :return: list of x, z tuples
                """

                def project(row):
                    """
                    Project the 3D point to a 2D plane
                    :param row: proj DataFrame row
                    :return: projected x, z coordinate tuple
                    """
                    q = row.loc[['Easting', 'Northing', 'Relative_depth']].to_numpy()  # The point being projected
                    q_proj = q - np.dot(q - p, plane_normal) * plane_normal
                    distvec = np.array(q_proj - p)[:-1]
                    dist = np.sqrt(distvec.dot(distvec))
                    return dist, q_proj[2]

                p = np.append(p1, 0)
                vec = np.append(p2 - p1, 0)  # Calculate the vector
                plane_normal = np.cross(vec, [0, 0, -1])  # Find the orthogonal plane to the vector
                plane_normal = plane_normal / math.sqrt(sum(i ** 2 for i in plane_normal))

                plane_proj = proj.apply(project, axis=1).to_numpy()
                return plane_proj

            # Get the 2D projected coordinates onto the plane defined by points p1 and p2
            plane_projection = get_plane_projection(p1, p2, proj)

            buffer = [patheffects.Stroke(linewidth=3, foreground='white'), patheffects.Normal()]
            hole_len = self.selected_hole.projection.Relative_depth.iloc[-1]
            collar_elevation = 0.

            # Plotz is the collar elevation minus the relative depth
            plotx, plotz = [p[0] for p in plane_projection], [collar_elevation - p[1] for p in plane_projection]

            # Plot the hole section line
            self.ax.plot(plotx, plotz,
                         color=selection_color,
                         lw=1,
                         # path_effects=buffer,
                         zorder=10)

            # Circle at top of hole
            self.ax.plot([plotx[0]], collar_elevation, 'o',
                         markerfacecolor='w',
                         markeredgecolor=selection_color,
                         markersize=8,
                         zorder=11)

            # Label hole name
            hole_name = self.selected_hole.hole_name_edit.text()
            trans = mtransforms.blended_transform_factory(self.ax.transData, self.ax.transAxes)
            self.ax.annotate(f"{hole_name}", (plotx[0], collar_elevation),
                             xytext=(0, 12),
                             textcoords='offset pixels',
                             color=selection_color,
                             ha='center',
                             size=9,
                             transform=trans,
                             path_effects=buffer,
                             zorder=10)

            # Label end-of-hole depth
            angle = math.degrees(math.atan2(plotz[-1] - plotz[-2], plotx[-1] - plotx[-2])) + 90
            self.ax.text(plotx[-1] + self.selected_hole.section_length * .01, plotz[-1], f" {hole_len:.0f} m ",
                         color=selection_color,
                         ha='left',
                         size=8,
                         rotation=angle,
                         path_effects=buffer,
                         zorder=10,
                         rotation_mode='anchor')

            # Plot the end of hole tick
            self.ax.scatter(plotx[-1], plotz[-1],
                            marker=(2, 0, angle + 90),
                            color=selection_color,
                            s=100,  # Size
                            zorder=12)

            # Add the horizontal line
            self.ax.axhline(y=0,
                            color='dimgray',
                            lw=0.6,
                            path_effects=buffer,
                            zorder=0
                            )

        def plot_mag(c1, c2):
            """
            Plots the magnetic vector quiver plot in the section plot.
            :param c1: (x, y, z) tuple: Corner of the 2D section to plot the mag on.
            :param c2: (x, y, z) tuple: Opposite corner of the 2D section to plot the mag on.
            :return: None
            """
            corners = self.selected_loop.get_loop_coords()
            wire_coords = [(c.x(), c.y(), 0) for c in corners]
            mag_calculator = MagneticFieldCalculator(wire_coords)
            xx, yy, zz, uproj, vproj, wproj, plotx, plotz, arrow_len = mag_calculator.get_2d_magnetic_field(c1, c2)
            self.ax.quiver(xx, zz, plotx, plotz,
                           color='dimgray',
                           label='Field',
                           pivot='middle',
                           zorder=1,
                           units='dots',
                           scale=.050,
                           width=.8,
                           headlength=11,
                           headwidth=6)

        self.ax.clear()

        if not self.selected_loop:
            logger.warning(f"Cannot plot hole without a loop.")
            self.ax.get_yaxis().set_visible(False)
            self.section_canvas.draw()
            return
        elif not self.selected_hole:
            logger.warning(f"No hole is opened.")
            self.ax.get_yaxis().set_visible(False)
            self.section_canvas.draw()
            return
        elif self.selected_hole.projection.empty:
            logger.warning(f"Cannot plot hole without hole geometry.")
            self.ax.get_yaxis().set_visible(False)
            self.section_canvas.draw()
            return

        proj = self.selected_hole.projection
        p1, p2 = self.selected_hole.get_section_extents()
        # plot_hole_section(p1, p2, list(zip(xs, ys, zs)))
        plot_hole_section(proj)

        # Get the corners of the 2D section to plot the mag on
        max_z = max(self.ax.get_ylim()[1], 0)
        ratio = self.section_frame.height() / (self.section_frame.width() * 0.9)
        min_z = max_z - (self.selected_hole.section_length * ratio)  # Try to fill the entire plot
        c1 = np.append(p1, max_z)  # Add the max Z
        c2 = np.append(p2, min_z)  # Add the min Z
        plot_mag(c1, c2)

        self.ax.get_yaxis().set_visible(True)
        self.section_canvas.draw()

    def get_crs(self):
        try:
            crs = CRS.from_epsg(self.get_epsg())
        except Exception as e:
            self.message.critical(self, 'Error', f"Error creating CRS: {e}.")
            return
        return crs

    def view_map(self):
        """
        View the hole and loop in a Plotly mapbox interactive map. A screen capture of the map can be
        saved with 'Ctrl+S' or copied to the clipboard with 'Ctrl+C'
        """
        if not any([self.hole_widgets, self.loop_widgets]):
            self.status_bar.showMessage(f"Nothing to show.", 1000)
            return

        global tile_map
        tile_map = TileMapViewer()

        # Format the figure margins and legend
        tile_map.map_figure.update_layout(
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

        lats, lons = [], []  # For centering the map when it's opened.

        def plot_loops():

            for widget in self.loop_widgets:
                loop_name = widget.loop_name_edit.text()

                loop_coords = widget.get_loop_coords_latlon(crs)
                if loop_coords.empty:
                    logger.error(f"Loop {loop_name} GPS is empty.")
                    return

                tile_map.map_figure.add_trace(go.Scattermapbox(lon=loop_coords.Easting,
                                                               lat=loop_coords.Northing,
                                                               mode='lines+markers',
                                                               name=loop_name,
                                                               text=loop_coords.index
                                                               )
                                              )

                lons.extend(loop_coords.Easting.to_numpy())
                lats.extend(loop_coords.Northing.to_numpy())

        def plot_holes():

            for widget in self.hole_widgets:
                hole_coords = widget.get_proj_latlon(crs)

                if hole_coords.empty:
                    logger.error(f"{hole_name} projection is empty.")
                    return

                hole_name = widget.hole_name_edit.text()

                tile_map.map_figure.add_trace(go.Scattermapbox(lon=hole_coords.Easting,
                                                               lat=hole_coords.Northing,
                                                               mode='lines+markers',
                                                               name=hole_name,
                                                               text=hole_coords.Relative_depth
                                                               )
                                              )

                lons.extend(hole_coords.Easting.to_numpy())
                lats.extend(hole_coords.Northing.to_numpy())

        crs = self.get_crs()

        plot_loops()
        plot_holes()

        # Pass the mapbox token, for access to better map tiles.
        # If none is passed, it uses the free open street map.
        token = open(".mapbox", 'r').read()
        if not token:
            logger.warning(f"No Mapbox token passed.")
            map_style = "open-street-map"
        else:
            map_style = "outdoors"

        # Add the map style and center/zoom the map
        tile_map.map_figure.update_layout(
            mapbox={
                'center': {'lon': np.array(lons).mean(), 'lat': np.array(lats).mean()},
                'zoom': 13},
            mapbox_style=map_style,
            mapbox_accesstoken=token)

        tile_map.load_page()
        tile_map.show()

    def save_kmz(self):
        """
        Save the loop and hole collar to a KMZ file.
        """
        if not any([self.hole_widgets, self.loop_widgets]):
            self.status_bar.showMessage(f"No GPS to save.", 1000)
            return

        crs = self.get_crs()

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

        for hole_widget in self.hole_widgets:
            hole_name = hole_widget.hole_name_edit.text()
            folder = kml.newfolder(name=hole_name)

            # Add the collar
            proj = hole_widget.get_proj_latlon(crs)
            if proj.empty:
                logger.warning(f"{hole_name} projection is empty.")
                continue

            collar = proj.iloc[0]

            collar = folder.newpoint(name=hole_name, coords=[collar.to_numpy()])
            collar.style = collar_style

            # Add the hole trace
            trace = folder.newlinestring(name=hole_name)
            trace.coords = proj.to_numpy()
            trace.extrude = 1
            trace.style = trace_style

        for loop_widget in self.loop_widgets:
            loop_name = loop_widget.loop_name_edit.text()

            # Add the loop
            loop = loop_widget.get_loop_coords_latlon(crs)

            if loop.empty:
                logger.error(f"Loop {loop_name} GPS is empty.")
                return

            ls = kml.newlinestring(name=loop_name)
            ls.coords = loop.to_numpy()
            ls.extrude = 1
            ls.style = loop_style

        save_dir = self.dialog.getSaveFileName(self, 'Save KMZ File', '', 'KMZ Files (*.KMZ)')[0]
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
        """
        if not any([self.hole_widgets, self.loop_widgets]):
            self.status_bar.showMessage(f"No GPS to save.", 1000)
            return

        crs = self.get_crs()

        gpx = gpxpy.gpx.GPX()

        # Add the collars
        for hole_widget in self.hole_widgets:
            hole_name = hole_widget.hole_name_edit.text()

            # Add the collar
            proj = hole_widget.get_proj_latlon(crs)
            if proj.empty:
                logger.warning(f"{hole_name} projection is empty.")
                continue

            collar = proj.iloc[0]

            waypoint = gpxpy.gpx.GPXWaypoint(latitude=collar.Northing,
                                             longitude=collar.Easting,
                                             name=hole_name)
            gpx.waypoints.append(waypoint)

        # Add the loops
        for loop_widget in self.loop_widgets:
            loop_name = loop_widget.loop_name_edit.text()

            # Add the loop
            loop = loop_widget.get_loop_coords_latlon(crs)

            if loop.empty:
                logger.error(f"Loop {loop_name} GPS is empty.")
                return

            # Create the GPX waypoints
            route = gpxpy.gpx.GPXRoute()
            for i, coord in loop.iterrows():
                waypoint = gpxpy.gpx.GPXWaypoint(latitude=coord.Northing,
                                                 longitude=coord.Easting,
                                                 name=loop_name)
                gpx.waypoints.append(waypoint)
                route.points.append(waypoint)
            gpx.routes.append(route)

        # Save the file
        save_path = self.dialog.getSaveFileName(self, 'Save GPX File', '', 'GPX Files (*.GPX)')[0]
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
        # self.installEventFilter(self)

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

        yaxis = PlanMapAxis(orientation='left')
        xaxis = PlanMapAxis(orientation='bottom')
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

    def closeEvent(self, e):
        self.deleteLater()
        e.accept()

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
            tile_map.map_figure.add_trace(go.Scattermapbox(lon=line.Easting,
                                                           lat=line.Northing,
                                                           mode='lines+markers',
                                                           name=line_name,
                                                           text=line.Station
                                                           ))

        global tile_map
        tile_map = TileMapViewer()

        loop_coords = self.get_loop_lonlat()
        grid = self.get_grid_lonlat()

        if loop_coords.empty and grid.empty:
            logger.error(f"No GPS to plot.")
            return

        loop_name = 'Loop' if self.loop_name_edit.text() == '' else self.loop_name_edit.text()

        # Plot the lines
        grid.groupby('Line_name').apply(plot_line)
        # Plot the loop
        tile_map.map_figure.add_trace(go.Scattermapbox(lon=loop_coords.Easting,
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
        tile_map.map_figure.update_layout(
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
        tile_map.map_figure.update_layout(
            mapbox={
                'center': {'lon': loop_coords.Easting.mean(), 'lat': loop_coords.Northing.mean()},
                'zoom': 13},
            mapbox_style=map_style,
            mapbox_accesstoken=token)

        tile_map.load_page()
        tile_map.show()

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

        self.status_bar.showMessage('Loop corner coordinates copied to clipboard.', 1000)

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
            return pg.mkPen(self.pen.color(), width=self.pen.width() + 0.5)
        else:
            return self.pen


def main():
    app = QApplication(sys.argv)
    # planner = LoopPlanner()
    planner = GridPlanner()

    # planner.gps_system_cbox.setCurrentIndex(2)
    # planner.gps_datum_cbox.setCurrentIndex(1)
    # planner.gps_zone_cbox.setCurrentIndex(16)
    planner.show()
    # planner.hole_widgets[0].get_dad_file()
    # planner.hole_az_edit.setText('174')
    # planner.view_map()
    # planner.save_gpx()

    app.exec_()


if __name__ == '__main__':
    main()


