import logging
import math
import os
import re
import sys
from pathlib import Path

import geopandas as gpd
import gpxpy
import matplotlib.pyplot as plt
import matplotlib as mpl
import matplotlib.ticker as ticker
import numpy as np
import plotly.graph_objects as go
import simplekml
from PySide2.QtCore import Qt, Signal, QEvent, QPoint, QPointF, QSettings, QSize
from PySide2.QtGui import QIntValidator, QKeySequence, QTransform
from PySide2.QtWidgets import (QMainWindow, QMessageBox, QGridLayout, QWidget, QFileDialog, QLabel, QApplication,
                               QFrame, QHBoxLayout, QLineEdit,
                               QHeaderView, QInputDialog, QTableWidgetItem, QGroupBox, QFormLayout, QTableWidget,
                               QShortcut, QPushButton, QCheckBox, QDoubleSpinBox, QProgressDialog, QRadioButton,
                               QItemDelegate, QSpinBox)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from pandas import DataFrame, read_excel, read_csv, read_table
from pyproj import CRS
import pyqtgraph as pg
from pyqtgraph.graphicsItems.ROI import Handle
from scipy import spatial
from shapely.geometry import asMultiPoint

from src import app_data_dir
from src.qt_py import get_icon, get_line_color, NonScientific, PlanMapAxis
from src.qt_py.map_widgets import TileMapViewer
from src.qt_py.pem_geometry import dad_to_seg
# from src.logger import Log
from src.gps.gps_editor import BoreholeCollar, BoreholeGeometry
from src.mag_field.mag_field_calculator import MagneticFieldCalculator
from src.ui.grid_planner import Ui_GridPlanner
from src.ui.loop_planner import Ui_LoopPlanner

logger = logging.getLogger(__name__)
selection_color = get_line_color("single_blue", "mpl", True)


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

        self.save_shortcut = QShortcut(QKeySequence("Ctrl+S"), self)
        self.copy_shortcut = QShortcut(QKeySequence("Ctrl+C"), self)
        self.save_shortcut.activated.connect(self.save_project)
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
        self.statusBar().showMessage(F"Image saved to clipboard.", 1500)

    def copy_loop_coords(self, widget):
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
        cb = QApplication.clipboard()
        cb.clear(mode=cb.Clipboard)
        cb.setText(result, mode=cb.Clipboard)

        self.statusBar().showMessage('Loop corner coordinates copied to clipboard.', 1000)


class HoleWidget(QWidget):
    name_changed_sig = Signal(str)
    plot_hole_sig = Signal()
    remove_sig = Signal()

    def __init__(self, properties, plot_widget, name='', darkmode=False):
        """
        Widget representing a hole as tab in Loop Planner.
        :param properties: dict, properties of a previous hole to be used as a starting point.
        :param plot_widget: pyqtgraph plot widget to plot on.
        :param name: str, name of the hole.
        """
        def init_signals():
            def toggle_geometry():
                self.hole_azimuth_edit.setEnabled(self.manual_geometry_rbtn.isChecked())
                self.hole_dip_edit.setEnabled(self.manual_geometry_rbtn.isChecked())
                self.hole_length_edit.setEnabled(self.manual_geometry_rbtn.isChecked())

                self.dad_file_edit.setEnabled(self.dad_geometry_rbtn.isChecked())

                # Update the plots
                self.get_hole_projection()
                self.draw_hole()
                self.plot_hole_sig.emit()

            def toggle_visibility():
                if self.show_cbox.isChecked():
                    self.hole_collar.show()
                    self.hole_name.show()
                    self.hole_trace.show()
                    self.hole_end.show()
                    self.section_extent_line.show()
                else:
                    self.hole_collar.hide()
                    self.hole_name.hide()
                    self.hole_trace.hide()
                    self.hole_end.hide()
                    self.section_extent_line.hide()

            self.show_cbox.toggled.connect(toggle_visibility)

            # Radio buttons
            self.manual_geometry_rbtn.toggled.connect(toggle_geometry)
            self.dad_geometry_rbtn.toggled.connect(toggle_geometry)

            # Buttons
            self.add_dad_file_btn.clicked.connect(self.get_dad_file)

            # Editing
            self.hole_name_edit.textChanged.connect(self.name_changed_sig.emit)
            self.hole_name_edit.textChanged.connect(lambda: self.hole_name.setText(self.hole_name_edit.text()))
            self.remove_btn.clicked.connect(self.remove_sig.emit)

            self.hole_easting_edit.editingFinished.connect(self.get_hole_projection)
            self.hole_easting_edit.editingFinished.connect(self.draw_hole)
            self.hole_northing_edit.editingFinished.connect(self.get_hole_projection)
            self.hole_northing_edit.editingFinished.connect(self.draw_hole)
            self.hole_elevation_edit.editingFinished.connect(self.get_hole_projection)
            self.hole_elevation_edit.editingFinished.connect(self.draw_hole)
            self.hole_azimuth_edit.editingFinished.connect(self.get_hole_projection)
            self.hole_azimuth_edit.editingFinished.connect(self.draw_hole)
            self.hole_dip_edit.editingFinished.connect(self.get_hole_projection)
            self.hole_dip_edit.editingFinished.connect(self.draw_hole)
            self.hole_length_edit.editingFinished.connect(self.get_hole_projection)
            self.hole_length_edit.editingFinished.connect(self.draw_hole)

        def init_ui():
            self.hole_easting_edit.setMaximum(1e9)
            self.hole_easting_edit.setMinimum(-1e9)
            self.hole_easting_edit.setSuffix("m")
            self.hole_northing_edit.setMaximum(1e9)
            self.hole_northing_edit.setMinimum(-1e9)
            self.hole_northing_edit.setSuffix("m")
            self.hole_elevation_edit.setMaximum(1e9)
            self.hole_elevation_edit.setMinimum(-1e9)
            self.hole_elevation_edit.setSuffix("m")
            self.hole_azimuth_edit.setMaximum(360)
            self.hole_azimuth_edit.setMinimum(0)
            self.hole_azimuth_edit.setSuffix("°")
            self.hole_dip_edit.setMaximum(90)
            self.hole_dip_edit.setMinimum(-90)
            self.hole_dip_edit.setSuffix("°")
            self.hole_length_edit.setMaximum(1e9)
            self.hole_length_edit.setMinimum(0.1)
            self.hole_length_edit.setSuffix("m")

            # Position
            position_gbox = QGroupBox('Position')
            position_gbox.setLayout(QFormLayout())
            position_gbox.setFlat(True)
            self.hole_easting_edit.setValue(float(properties.get('easting')))
            self.hole_northing_edit.setValue(float(properties.get('northing')))
            self.hole_elevation_edit.setValue(float(properties.get('elevation')))
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
            self.show_cbox.setChecked(True)
            self.layout().addRow(self.show_cbox)
            self.manual_geometry_rbtn.setChecked(True)

            # Manual geometry frame
            manual_geometry_frame = QFrame()
            manual_geometry_frame.setLayout(QFormLayout())
            manual_geometry_frame.setContentsMargins(0, 0, 0, 0)
            self.hole_azimuth_edit.setValue(float(properties.get('azimuth')))
            self.hole_dip_edit.setValue(float(properties.get('dip')))
            self.hole_length_edit.setValue(float(properties.get('length')))
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
            name_frame = QFrame()
            name_frame.setLayout(QHBoxLayout())
            name_frame.layout().setContentsMargins(0, 0, 0, 0)
            self.hole_name_edit.setPlaceholderText('(Optional)')

            self.remove_btn.setFlat(True)
            self.remove_btn.setToolTip("Remove")

            name_frame.layout().addWidget(QLabel("Name"))
            name_frame.layout().addWidget(self.hole_name_edit)
            name_frame.layout().addWidget(self.remove_btn)
            self.layout().addRow(name_frame)

        super().__init__()
        self.darkmode = darkmode
        self.setLayout(QFormLayout())
        self.plan_view = plot_widget
        self.projection = DataFrame()
        self.segments = None
        self.section_length = None
        self.loop = None

        self.hole_color = get_line_color("foreground", "pyqt", self.darkmode)
        self.selection_color = get_line_color("teal", "pyqt", self.darkmode) if self.darkmode else selection_color
        self.foreground_color = get_line_color("foreground", "pyqt", self.darkmode)
        self.background_color = get_line_color("background", "pyqt", self.darkmode)

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
        self.show_cbox = QCheckBox("Show in plan map")
        self.hole_easting_edit = QDoubleSpinBox()
        self.hole_northing_edit = QDoubleSpinBox()
        self.hole_elevation_edit = QDoubleSpinBox()
        self.hole_azimuth_edit = QDoubleSpinBox()
        self.hole_dip_edit = QDoubleSpinBox()
        self.hole_length_edit = QDoubleSpinBox()
        self.manual_geometry_rbtn = QRadioButton()
        self.dad_geometry_rbtn = QRadioButton()
        self.hole_name_edit = QLineEdit(name)
        self.remove_btn = QPushButton(get_icon("remove2.png"), "")
        init_ui()

        # Hole collar
        self.hole_collar = pg.ScatterPlotItem(clickable=True,
                                           pen=pg.mkPen(self.hole_color, width=1.),
                                           symbol='o',
                                           brush=pg.mkBrush(self.background_color))
        self.hole_collar.setZValue(5)

        # Hole trace
        self.hole_trace = pg.PlotCurveItem(clickable=True, pen=pg.mkPen(self.hole_color, width=1.))
        self.hole_trace.setZValue(4)

        # The end bar
        self.hole_end = pg.ArrowItem(headLen=0,
                                  tailLen=0,
                                  tailWidth=15,
                                  pen=pg.mkPen(self.hole_color, width=1.))
        self.hole_end.setZValue(5)

        # Hole name
        self.hole_name = pg.TextItem(name, anchor=(-0.15, 0.5), color=self.foreground_color)
        self.hole_name.setZValue(100)

        # Add a single section line to be used by all holes
        self.section_extent_line = pg.PlotDataItem(width=1,
                                                   pen=pg.mkPen(color=get_line_color("gray", "pyqt", self.darkmode),
                                                                style=Qt.DashLine))
        self.hole_end.setZValue(1)

        self.plan_view.addItem(self.hole_collar)
        self.plan_view.addItem(self.hole_trace)
        self.plan_view.addItem(self.hole_end, ignoreBounds=True)
        self.plan_view.addItem(self.hole_name, ignoreBounds=True)
        self.plan_view.addItem(self.section_extent_line)

        self.get_hole_projection()
        self.draw_hole()

        init_signals()

    def select(self):
        self.hole_collar.setPen(pg.mkPen(self.selection_color, width=1.5))
        self.hole_collar.setSize(12)
        self.hole_collar.setZValue(10)

        self.hole_trace.setPen(pg.mkPen(self.selection_color, width=1.5))
        self.hole_trace.setShadowPen(pg.mkPen(self.selection_color, width=3.))
        self.hole_trace.setZValue(9)

        self.hole_end.setPen(pg.mkPen(self.selection_color, width=1.5))

        self.hole_name.setColor(self.selection_color)
        if self.show_cbox.isChecked():
            self.section_extent_line.show()

    def deselect(self):
        self.hole_collar.setPen(pg.mkPen(self.hole_color, width=1.))
        self.hole_collar.setSize(11)
        self.hole_collar.setZValue(5)

        self.hole_trace.setPen(pg.mkPen(self.hole_color, width=1.))
        self.hole_trace.setShadowPen(None)
        self.hole_trace.setZValue(4)

        self.hole_end.setPen(pg.mkPen(self.hole_color, width=1.))

        self.hole_name.setColor(self.hole_color)
        if self.show_cbox.isChecked():
            self.section_extent_line.hide()

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
            'name': self.hole_name_edit.text(),
            'easting': self.hole_easting_edit.value(),
            'northing': self.hole_northing_edit.value(),
            'elevation': self.hole_elevation_edit.value(),
            'azimuth': self.hole_azimuth_edit.value(),
            'dip': self.hole_dip_edit.value(),
            'length': self.hole_length_edit.value(),
        }

    def get_hole_projection(self):
        """
        Calculate and update the 3D projection of the hole.
        """
        # Reset the current projection, so there isn't a length error later
        self.projection = self.projection.iloc[0:0]

        x = float(self.hole_easting_edit.value())
        y = float(self.hole_northing_edit.value())
        z = float(self.hole_elevation_edit.value())
        collar = BoreholeCollar([[x, y, z, '0']])  # Float so it doesn't get removed when parsing collar

        # Using the manual user-input settings
        if self.manual_geometry_rbtn.isChecked():
            length = float(self.hole_length_edit.value())
            azimuth = float(self.hole_azimuth_edit.value())
            dip = float(self.hole_dip_edit.value())
            df = DataFrame({'Depth': [z, length],
                            'Azimuth': [azimuth] * 2,
                            'Dip': [dip] * 2})
            segments = dad_to_seg(df)
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
            hole_length = int(self.hole_length_edit.value())
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
        proj = self.projection.copy()

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
                    df = read_excel(filepath,
                                    # delim_whitespace=True,
                                    usecols=[0, 1, 2],
                                    names=['Depth', 'Azimuth', 'Dip'],
                                    header=None,
                                    dtype=float)
                else:
                    df = read_csv(filepath,
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
                    self.segments = dad_to_seg(df.dropna())
                    self.get_hole_projection()
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
        self.hole_collar.setData([int(self.hole_easting_edit.value())], [int(self.hole_northing_edit.value())])

        # Plot the name
        self.hole_name.setPos(int(self.hole_easting_edit.value()), int(self.hole_northing_edit.value()))

        if not self.projection.empty:
            # Plot the trace
            self.hole_trace.setData(self.projection.Easting.to_numpy(), self.projection.Northing.to_numpy())
            if self.show_cbox.isChecked():
                self.hole_trace.show()

            # Plot the end of the hole
            self.hole_end.setPos(self.projection.Easting.iloc[-1], self.projection.Northing.iloc[-1])
            angle = self.get_azimuth()
            if self.show_cbox.isChecked():
                self.hole_end.show()
            self.hole_end.setStyle(angle=angle + 90,
                                   pen=self.hole_trace.opts['pen'])
        else:
            self.hole_trace.hide()
            self.hole_end.hide()

        self.plot_hole_sig.emit()


class LoopWidget(QWidget):
    name_changed_sig = Signal(str)
    plot_hole_sig = Signal()
    remove_sig = Signal()

    def __init__(self, coords, plot_widget, name='', angle=0., darkmode=False):
        """
        Widget representing a loop as tab in Loop Planner.
        :param coords: list of lists, coordinates of the loop. If one is passed, it will be used as the center and
        the corners will be calculated using a 500m x 500m size.
        :param name: str, name of the loop.
        :param angle: angle of a previous loop to be used as a starting point.
        :param plot_widget: pyqtgraph plot widget to plot on.
        """
        def init_ui():
            self.setLayout(QFormLayout())
            
            self.show_cbox.setChecked(True)
            self.layout().addRow(self.show_cbox)
            
            self.loop_angle_sbox.setRange(-360, 360)
            self.loop_angle_sbox.setValue(int(angle))
            self.loop_name_edit.setPlaceholderText('(Optional)')
            self.layout().addRow('Angle', self.loop_angle_sbox)

            self.coords_table.setColumnCount(2)
            self.coords_table.setHorizontalHeaderLabels(["Easting", "Northing"])
            self.coords_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            float_delegate = QItemDelegate()
            self.coords_table.setItemDelegateForColumn(0, float_delegate)
            self.coords_table.setItemDelegateForColumn(1, float_delegate)
            self.layout().addRow(self.coords_table)

            h_line = QFrame()
            h_line.setFrameShape(QFrame().HLine)
            h_line.setFrameShadow(QFrame().Sunken)
            self.layout().addRow(h_line)
            self.layout().addRow(self.copy_loop_btn)

            name_frame = QFrame()
            name_frame.setLayout(QHBoxLayout())
            name_frame.layout().setContentsMargins(0, 0, 0, 0)
            self.loop_name_edit.setPlaceholderText('(Optional)')

            self.remove_btn.setFlat(True)
            self.remove_btn.setToolTip("Remove")

            name_frame.layout().addWidget(QLabel("Name"))
            name_frame.layout().addWidget(self.loop_name_edit)
            name_frame.layout().addWidget(self.remove_btn)
            self.layout().addRow(name_frame)

        def init_signals():
            def toggle_visibility():
                if self.show_cbox.isChecked():
                    self.loop_roi.show()
                    self.loop_name.show()
                    if self.show_corners:
                        for label in self.corner_labels:
                            label.show()
                    if self.show_segments:
                        for label in self.segment_labels:
                            label.show()
                else:
                    self.loop_roi.hide()
                    self.loop_name.hide()
                    for label in np.concatenate([self.corner_labels, self.segment_labels]):
                        label.hide()

            self.coords_table.cellChanged.connect(self.update_loop_corners)
            self.show_cbox.toggled.connect(toggle_visibility)
            self.remove_btn.clicked.connect(self.remove_sig.emit)
            self.loop_angle_sbox.valueChanged.connect(self.update_loop_roi)

            self.loop_name_edit.textChanged.connect(self.name_changed_sig.emit)
            self.loop_name_edit.textChanged.connect(lambda: self.loop_name.setText(self.loop_name_edit.text()))
            self.loop_roi.setAcceptedMouseButtons(Qt.LeftButton)
            self.loop_roi.sigHandleAdded.connect(self.update_loop_values)
            self.loop_roi.sigHandleAdded.connect(self.label_loop_corners)
            self.loop_roi.sigRegionChanged.connect(self.update_loop_values)
            self.loop_roi.sigRegionChanged.connect(self.plot_loop_name)
            self.loop_roi.sigRegionChangeFinished.connect(lambda: self.plot_hole_sig.emit())

        def get_corners(coords):
            if len(coords) == 1:
                center = coords[0]
                # Set the position of the loop by the center (and not the bottom-left corner)
                h, w = 500, 500
                pos = QPointF(center.x() - (w / 2), center.y() - (h / 2))  # Adjusted position for the center
                # angle = 0

                c1 = QPointF(pos)
                c2 = QPointF(c1.x() + w * (math.cos(math.radians(angle))), c1.y() + w * (math.sin(math.radians(angle))))
                c3 = QPointF(c2.x() - h * (math.sin(math.radians(angle))),
                             c2.y() + h * (math.sin(math.radians(90 - angle))))
                c4 = QPointF(c3.x() + w * (math.cos(math.radians(180 - angle))),
                             c3.y() - w * (math.sin(math.radians(180 - angle))))
                corners = [(c1.x(), c1.y()),
                           (c2.x(), c2.y()),
                           (c3.x(), c3.y()),
                           (c4.x(), c4.y()),
                           ]
            else:
                corners = coords
            
            return corners
        
        super().__init__()
        self.darkmode = darkmode
        self.setAcceptDrops(True)
        self.plan_view = plot_widget
        self.corner_labels = []
        self.segment_labels = []
        self.show_corners = True
        self.show_segments = True
        self.is_selected = True

        self.foreground_color = get_line_color("foreground", "pyqt", self.darkmode)
        self.loop_color = get_line_color("foreground", "pyqt", self.darkmode)
        self.selection_color = get_line_color("teal", "pyqt", self.darkmode) if self.darkmode else selection_color

        # Create all the inner widget items
        self.show_cbox = QCheckBox("Show in plan map")
        self.loop_angle_sbox = QSpinBox()
        self.loop_name_edit = QLineEdit(name)
        self.coords_table = QTableWidget()
        self.copy_loop_btn = QPushButton(get_icon('copy.png'), "Copy Corners")
        self.loop_name_edit = QLineEdit(name)
        self.remove_btn = QPushButton(get_icon("remove2.png"), "")
        init_ui()

        # Plots
        corners = get_corners(coords)
        self.loop_roi = PolyLoop(corners,
                                 scaleSnap=True,
                                 snapSize=5,
                                 closed=True,
                                 pen=pg.mkPen(self.selection_color, width=1.))
        self.loop_roi.hoverPen = pg.mkPen(self.selection_color, width=2.)
        self.loop_roi.setZValue(15)
        self.update_loop_values()

        self.loop_name = pg.TextItem(name, anchor=(0.5, 0.5), color=(0, 0, 0, 100))
        self.loop_name.setZValue(0)

        self.plan_view.addItem(self.loop_roi)
        self.plan_view.addItem(self.loop_name, ignoreBounds=True)

        self.plot_loop_name()

        init_signals()

    def select(self):
        """When the loop is selected"""
        self.loop_roi.setPen(self.selection_color, width=1.5)
        self.loop_name.setColor(self.selection_color)
        if self.show_corners is True:
            for label in self.corner_labels:
                label.show()
        if self.show_segments is True:
            for label in self.segment_labels:
                label.show()
        for handle in self.loop_roi.getHandles():
            handle.show()

        self.is_selected = True

    def deselect(self):
        self.loop_roi.setPen(pg.mkPen(self.loop_color), width=1.)
        self.loop_name.setColor(self.loop_color)
        for label in self.corner_labels:
            label.hide()
        for label in self.segment_labels:
            label.hide()
        for handle in self.loop_roi.getHandles():
            handle.hide()
        self.is_selected = False

    def remove(self):
        """
        Remove and delete the loop ROI object.
        :return: None
        """
        self.plan_view.removeItem(self.loop_roi)
        self.plan_view.removeItem(self.loop_name)
        for label in self.corner_labels:
            self.plan_view.removeItem(label)
        for label in self.segment_labels:
            self.plan_view.removeItem(label)
        self.deleteLater()

    def get_loop_coords(self):
        """
        Return the coordinates of the corners (handles) of the loop.
        :return: list of QPointF objects.
        """
        corners = []
        for scene_p in self.loop_roi.getSceneHandlePositions():
            x = self.loop_roi.mapSceneToParent(scene_p[1]).x()
            y = self.loop_roi.mapSceneToParent(scene_p[1]).y()
            corners.append(QPointF(x, y))
        return corners

    def get_loop_coords_latlon(self, crs):
        """
        Return the coordinates of the loop as lat lon.
        :param crs: User selected CRS object
        :return: dataframe
        """
        # Get the loop data
        loop = DataFrame([[c.x(), c.y(), 0] for c in self.get_loop_coords()],
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
        :return: QPointF
        """
        corners = self.get_loop_coords()
        xs = np.array([c.x() for c in corners])
        ys = np.array([c.y() for c in corners])

        center = QPointF(xs.mean(), ys.mean())
        return center

    def get_angle(self):
        return self.loop_angle_sbox.text()

    def get_properties(self):
        """Return a dictionary of loop properties"""
        return {
            'name': self.loop_name_edit.text(),
            'coordinates': self.get_loop_coords(),
            # 'center': self.get_loop_center(),
        }

    def plot_loop_name(self):
        center = self.get_loop_center()
        self.loop_name.setPos(center.x(), center.y())

    def update_loop_roi(self):
        """
        Signal slot, change the loop ROI object based on the user input values.
        """
        print(f"updating loop roi")
        self.loop_roi.blockSignals(True)

        angle = int(self.loop_angle_sbox.text())
        self.loop_roi.setAngle(angle, center=self.get_loop_center())
        self.plot_loop_name()
        self.label_loop_corners()

        self.loop_roi.blockSignals(False)

        # Update the section plot
        self.plot_hole_sig.emit()

    def update_loop_values(self):
        """
        Signal slot: Updates the values of the loop angle and table values when the loop ROI is changed, then
        replots the section plot.
        """

        def series_to_items(x):
            x = round(x, 0)
            item = QTableWidgetItem()
            item.setData(Qt.EditRole, x)
            return item

        self.coords_table.blockSignals(True)
        self.loop_angle_sbox.blockSignals(True)

        while self.coords_table.rowCount() > 0:
            self.coords_table.removeRow(0)

        corners = self.get_loop_coords()
        for corner in corners:
            # Add a new row to the table
            row_pos = self.coords_table.rowCount()
            self.coords_table.insertRow(row_pos)

            items = [series_to_items(c) for c in [corner.x(), corner.y()]]
            # Format each item of the table to be centered
            for m, item in enumerate(items):
                item.setTextAlignment(Qt.AlignCenter)
                self.coords_table.setItem(row_pos, m, item)

        angle = self.loop_roi.getState().get("angle")
        self.loop_angle_sbox.setValue(int(angle))

        self.coords_table.blockSignals(False)
        self.loop_angle_sbox.blockSignals(False)
        self.label_loop_corners()

    def update_loop_corners(self):
        """
        Move a handle based on the values in the table
        """
        self.loop_roi.blockSignals(True)

        loop_pos = self.loop_roi.state.get("pos")
        for row, handle in zip(range(self.coords_table.rowCount()), self.loop_roi.getHandles()):
            table_x, table_y = self.coords_table.item(row, 0).text(), self.coords_table.item(row, 1).text()
            print(
                f"Moving {handle.pos().x():.0f}, {handle.pos().y():.0f} to {float(table_x) + loop_pos.x():.0f}, "
                f"{float(table_y) + loop_pos.y():.0f}")
            self.loop_roi.movePoint(handle, QPointF(float(table_x), float(table_y)))

        self.loop_roi.blockSignals(False)
        self.label_loop_corners()

    def label_loop_corners(self):
        """
        Label the loop corners and segment lengths
        """

        # Remove previous labels
        for label in self.corner_labels:
            self.plan_view.removeItem(label)
        for label in self.segment_labels:
            self.plan_view.removeItem(label)

        corners = self.get_loop_coords()
        for i, corner in enumerate(corners):
            label = pg.TextItem(str(i + 1), color=pg.mkColor(self.selection_color))
            label.setPos(corner)
            self.corner_labels.append(label)
            self.plan_view.addItem(label, ignoreBounds=True)
            if self.show_corners is False:
                label.hide()

        for segment in self.loop_roi.segments:
            p1, p2 = segment.getSceneHandlePositions()
            p1 = self.loop_roi.mapSceneToParent(p1[1])
            p2 = self.loop_roi.mapSceneToParent(p2[1])
            x, y = ((p2.x() - p1.x()) / 2) + p1.x(), ((p2.y() - p1.y()) / 2) + p1.y()
            dist = spatial.distance.euclidean((p1.x(), p1.y()), (p2.x(), p2.y()))
            label = pg.TextItem(f"{dist:.0f}m", color=pg.mkColor(self.loop_color))
            label.setPos(x, y)
            self.segment_labels.append(label)
            self.plan_view.addItem(label, ignoreBounds=True)
            if self.show_segments is False:
                label.hide()


class LoopPlanner(SurveyPlanner, Ui_LoopPlanner):
    """
    Program that plots the magnetic field projected to a plane perpendicular to a borehole for a interactive loop.
    Loop and borehole collar can be exported as KMZ or GPX files.
    """
    def __init__(self, parent=None, darkmode=False):
        def init_ui():
            self.setAcceptDrops(True)
            self.setWindowTitle('Loop Planner')
            self.setWindowIcon(get_icon('loop_planner.png'))
            self.resize(1500, 800)
            self.status_bar.show()

            # Status bar
            self.status_bar.addPermanentWidget(self.epsg_label, 0)
            self.plan_view.setMenuEnabled(False)

            # Icons
            self.actionOpen_Project.setIcon(get_icon("open.png"))
            self.actionSave_Project.setIcon(get_icon("save.png"))
            self.actionSave_As.setIcon(get_icon("save_as.png"))
            self.actionSave_as_KMZ.setIcon(get_icon("google_earth.png"))
            self.actionSave_as_GPX.setIcon(get_icon("garmin_file.png"))
            self.view_map_action.setIcon(get_icon("folium.png"))
            self.add_hole_btn.setIcon(get_icon("add.png"))
            self.add_loop_btn.setIcon(get_icon("add.png"))

        def init_signals():
            def toggle_annotations():
                for hole in self.hole_widgets:
                    if self.show_names_cbox.isChecked():
                        hole.hole_name.show()
                    else:
                        hole.hole_name.hide()

                for loop in self.loop_widgets:
                    if self.show_names_cbox.isChecked():
                        loop.loop_name.show()
                    else:
                        loop.loop_name.hide()

                    if self.show_corners_cbox.isChecked():
                        loop.show_corners = True
                        if loop.is_selected:
                            for label in loop.corner_labels:
                                label.show()
                    else:
                        loop.show_corners = False
                        for label in loop.corner_labels:
                            label.hide()

                    if self.show_segments_cbox.isChecked():
                        loop.show_segments = True
                        if loop.is_selected:
                            for label in loop.segment_labels:
                                label.show()
                    else:
                        loop.show_segments = False
                        for label in loop.segment_labels:
                            label.hide()

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

            self.hole_cbox.currentIndexChanged.connect(self.select_hole)
            self.loop_cbox.currentIndexChanged.connect(self.select_loop)

            # Menu
            self.actionOpen_Project.triggered.connect(lambda: self.open_project(filepath=None))
            self.actionSave_Project.triggered.connect(lambda: self.save_project(save_as=False))
            self.actionSave_As.triggered.connect(lambda: self.save_project(save_as=True))
            self.actionSave_as_KMZ.triggered.connect(self.save_kmz)
            self.actionSave_as_GPX.triggered.connect(self.save_gpx)
            self.view_map_action.triggered.connect(self.view_map)

            # Checkbox
            self.show_names_cbox.toggled.connect(toggle_annotations)
            self.show_corners_cbox.toggled.connect(toggle_annotations)
            self.show_segments_cbox.toggled.connect(toggle_annotations)
            self.show_grid_cbox.toggled.connect(lambda: self.plan_view.showGrid(x=self.show_grid_cbox.isChecked(),
                                                                                y=self.show_grid_cbox.isChecked()))

            # Buttons
            self.add_hole_btn.clicked.connect(self.add_hole)
            self.add_loop_btn.clicked.connect(self.add_loop)

            # CRS
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

        def init_crs():
            """
            Populate the CRS drop boxes and connect all their signals
            """
            # Add the GPS system and datum drop box options
            gps_systems = ['', 'Lat/Lon', 'UTM']
            for system in gps_systems:
                self.gps_system_cbox.addItem(system)

            datums = ['', 'WGS 1984', 'NAD 1927', 'NAD 1983']
            for datum in datums:
                self.gps_datum_cbox.addItem(datum)

            int_valid = QIntValidator()
            self.epsg_edit.setValidator(int_valid)

            self.gps_system_cbox.setCurrentIndex(2)
            self.gps_datum_cbox.setCurrentIndex(1)
            self.gps_zone_cbox.setCurrentIndex(17)

        def init_plan_view():
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

        def init_section_view():
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

        super().__init__()
        self.setupUi(self)
        self.parent = parent
        self.darkmode = darkmode

        self.background_color = get_line_color("background", "mpl", self.darkmode)
        self.foreground_color = get_line_color("foreground", "mpl", self.darkmode)
        self.hole_color = get_line_color("foreground", "mpl", self.darkmode)
        self.loop_color = get_line_color("purple", "mpl", self.darkmode)
        self.selection_color = get_line_color("teal", "mpl", self.darkmode) if self.darkmode else selection_color

        plt.style.use('dark_background' if self.darkmode else 'default')
        plt.rcParams['axes.facecolor'] = self.background_color
        plt.rcParams['figure.facecolor'] = self.background_color

        self.save_name = None
        self.selected_hole = None
        self.selected_loop = None
        self.loop_widgets = []
        self.hole_widgets = []

        self.section_figure = Figure()
        self.ax = self.section_figure.add_subplot()
        self.section_canvas = FigureCanvas(self.section_figure)
        self.section_view_layout.addWidget(self.section_canvas)

        self.add_hole('Hole')
        self.add_loop('Loop')
        self.loop_tab_widget.hide()

        init_ui()
        init_signals()
        init_crs()
        init_plan_view()
        init_section_view()

        self.load_settings()

    def dragEnterEvent(self, e):
        e.accept()

    def dropEvent(self, e):
        urls = [Path(url.toLocalFile()) for url in e.mimeData().urls()]

        if all([file.suffix.lower() == ".tx" for file in urls]):
            for file in urls:
                # print(f"Opening loop {file.name}")
                # self.add_loop(file.name)
                self.open_tx_file(file)

    def event(self, e):
        if e.type() in [QEvent.Show]:  # , QEvent.Resize):
            self.plot_hole()

        return QMainWindow.event(self, e)

    def closeEvent(self, e):
        self.save_settings()
        self.deleteLater()
        e.accept()

    def save_settings(self):
        settings = QSettings("Crone Geophysics", "PEMPro")
        settings.beginGroup("LoopPlanner")

        # Window geometry
        settings.setValue("size", self.size())
        settings.setValue("pos", self.pos())

        # Project
        settings.setValue("last_opened_project", self.save_name)

        settings.endGroup()

    def load_settings(self):
        settings = QSettings("Crone Geophysics", "PEMPro")
        settings.beginGroup("LoopPlanner")

        # Window geometry
        self.resize(settings.value("size", QSize(1500, 800)))
        self.move(settings.value("pos", QPoint(100, 50)))

        # Project
        project_file = settings.value("last_opened_project")
        if project_file:
            if Path(project_file).is_file():
                response = self.message.question(self, "Open Project", "Continue last project?",
                                                 self.message.Yes, self.message.No)
                if response == self.message.Yes:
                    self.open_project(project_file)

        settings.endGroup()

    def select_hole(self, ind):
        """
        Select a hole, ensuring the hole widget is highlighted and the tab is set to the correct page.
        :param ind: int, index of the hole
        """
        if ind == -1:
            self.selected_hole = None
        else:
            self.selected_hole = self.hole_widgets[ind]
            self.hole_tab_widget.setCurrentIndex(ind)

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
            self.selected_loop = None
        else:
            self.selected_loop = self.loop_widgets[ind]
            self.loop_tab_widget.setCurrentIndex(ind)

            for i, widget in enumerate(self.loop_widgets):
                if i == ind:
                    widget.select()
                else:
                    widget.deselect()

        self.plot_hole()

    def add_hole(self, name=None, easting=None, northing=None, elevation=None, azimuth=None, dip=None, length=None):
        """
        Create tab for a new hole
        :param name: str, name of the hole
        :param easting: str or float
        :param northing: str or float
        :param elevation: str or float
        :param azimuth: str or float
        :param dip: str or float
        :param length: str or float
        :return: None
        """
        def name_changed(widget):
            """
            Rename the tab name when the hole name is changed.
            :param widget: Hole widget
            """
            ind = self.hole_widgets.index(widget)
            self.hole_cbox.setItemText(ind, widget.hole_name_edit.text())

        def hole_clicked(widget):
            """
            De-select all other holes.
            :param widget: The hole widget that was clicked
            """
            # Change the tab
            ind = self.hole_widgets.index(widget)
            self.hole_tab_widget.setCurrentIndex(ind)
            self.hole_cbox.setCurrentIndex(ind)

            # Select the object
            for w in self.hole_widgets:
                if w == widget:
                    w.select()
                else:
                    w.deselect()

        def remove_hole(widget):
            ind = self.hole_widgets.index(widget)
            self.remove_hole(ind)

        if not name:
            name, ok_pressed = QInputDialog.getText(self, "Add Hole", "Hole name:", QLineEdit.Normal, "")
            if not ok_pressed:
                return

        if name != '':
            self.hole_tab_widget.show()

            # Copy the information from the currently selected hole widget to be used in the new widget
            if self.hole_widgets:
                properties = self.hole_widgets[self.hole_tab_widget.currentIndex()].get_properties()
            else:
                properties = dict()

            # Set the property values from the init
            prop_names = ["easting", "northing", "elevation", "azimuth", "dip", "length"]
            for i, value in enumerate([easting, northing, elevation, azimuth, dip, length]):
                if value is not None:
                    properties[prop_names[i]] = float(value)

            # Create the hole widget for the tab
            hole_widget = HoleWidget(properties, self.plan_view, name=name, darkmode=self.darkmode)
            self.hole_widgets.append(hole_widget)
            hole_widget.name_changed_sig.connect(lambda: name_changed(hole_widget))
            hole_widget.hole_collar.sigClicked.connect(lambda: hole_clicked(hole_widget))
            hole_widget.plot_hole_sig.connect(self.plot_hole)
            hole_widget.remove_sig.connect(lambda: remove_hole(hole_widget))
            self.hole_tab_widget.addWidget(hole_widget)
            self.hole_tab_widget.setCurrentIndex(len(self.hole_widgets) - 1)
            self.hole_cbox.addItem(name)
            self.hole_cbox.setCurrentIndex(len(self.hole_widgets) - 1)

            # Select the hole if it is the only one open
            if self.hole_tab_widget.count() == 1:
                self.select_hole(0)

    def add_loop(self, name=None, coords=None):
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
            self.loop_cbox.setItemText(ind, widget.loop_name_edit.text())

        def loop_clicked(widget):
            """
            De-select all other loops.
            :param widget: The loop widget that was clicked
            """
            # Change the tab
            ind = self.loop_widgets.index(widget)
            self.loop_tab_widget.setCurrentIndex(ind)
            self.loop_cbox.setCurrentIndex(ind)

            # Select the object
            for w in self.loop_widgets:
                if w == widget:
                    widget.select()
                else:
                    w.deselect()

        def remove_loop(widget):
            ind = self.loop_widgets.index(widget)
            self.remove_loop(ind)

        if not name:
            name, ok_pressed = QInputDialog.getText(self, "Add Loop", "Loop name:", QLineEdit.Normal, "")
            if not ok_pressed:
                return

        if name != '':
            self.loop_tab_widget.show()

            # Copy the information from the currently selected hole widget to be used in the new widget
            if self.loop_widgets:
                angle = self.loop_widgets[self.loop_tab_widget.currentIndex()].get_angle()
            else:
                angle = 0

            if coords is None:
                # Create the loop widget for the tab
                coords = [self.plan_view.viewRect().center()]

            loop_widget = LoopWidget(coords, self.plan_view, name=name, angle=int(angle), darkmode=self.darkmode)
            self.loop_widgets.append(loop_widget)

            # Connect signals
            loop_widget.name_changed_sig.connect(lambda: name_changed(loop_widget))
            loop_widget.plot_hole_sig.connect(self.plot_hole)
            loop_widget.loop_roi.sigClicked.connect(lambda: loop_clicked(loop_widget))
            loop_widget.loop_roi.sigRegionChangeStarted.connect(lambda: loop_clicked(loop_widget))
            loop_widget.copy_loop_btn.clicked.connect(lambda: self.copy_loop_coords(loop_widget))
            loop_widget.remove_sig.connect(lambda: remove_loop(loop_widget))

            if not self.show_corners_cbox.isChecked():
                loop_widget.show_corners = False

            if not self.show_segments_cbox.isChecked():
                loop_widget.show_segments = False

            self.loop_tab_widget.addWidget(loop_widget)
            self.loop_tab_widget.setCurrentIndex(len(self.loop_widgets) - 1)
            self.loop_cbox.addItem(name)
            self.loop_cbox.setCurrentIndex(len(self.loop_widgets) - 1)

            # Select the loop if it is the only one open
            if self.loop_tab_widget.count() == 1:
                self.select_loop(0)
                self.ax.get_yaxis().set_visible(True)

    def remove_hole(self, ind, prompt=True):
        if prompt is True:
            response = QMessageBox.question(self, "Remove Hole", "Are you sure you want to remove this hole?",
                                            QMessageBox.Yes, QMessageBox.No)
        else:
            response = QMessageBox.Yes

        if response == QMessageBox.Yes:
            widget = self.hole_widgets[ind]
            widget.remove()
            del self.hole_widgets[ind]
            self.hole_tab_widget.removeWidget(widget)
            self.hole_cbox.removeItem(ind)

        if len(self.hole_widgets) == 0:
            self.hole_tab_widget.hide()

    def remove_loop(self, ind, prompt=True):
        if prompt is True:
            response = QMessageBox.question(self, "Remove Loop", "Are you sure you want to remove this loop?",
                                            QMessageBox.Yes, QMessageBox.No)
        else:
            response = QMessageBox.Yes

        if response == QMessageBox.Yes:
            widget = self.loop_widgets[ind]
            widget.remove()
            del self.loop_widgets[ind]
            self.loop_tab_widget.removeWidget(widget)
            self.loop_cbox.removeItem(ind)

        if len(self.loop_widgets) == 0:
            self.loop_tab_widget.hide()

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

            buffer = [mpl.patheffects.Stroke(linewidth=3,
                                             foreground=self.background_color),
                      mpl.patheffects.Normal()]
            hole_len = self.selected_hole.projection.Relative_depth.iloc[-1]
            collar_elevation = 0.

            # Plotz is the collar elevation minus the relative depth
            plotx, plotz = [p[0] for p in plane_projection], [collar_elevation - p[1] for p in plane_projection]

            # Plot the hole section line
            self.ax.plot(plotx, plotz,
                         color=self.selection_color,
                         lw=1,
                         # path_effects=buffer,
                         zorder=10)

            # Circle at top of hole
            self.ax.plot([plotx[0]], collar_elevation, 'o',
                         markerfacecolor=self.background_color,
                         markeredgecolor=self.selection_color,
                         markersize=8,
                         zorder=11)

            # Label hole name
            hole_name = self.selected_hole.hole_name_edit.text()
            trans = mpl.transforms.blended_transform_factory(self.ax.transData, self.ax.transAxes)
            self.ax.annotate(f"{hole_name}", (plotx[0], collar_elevation),
                             xytext=(0, 12),
                             textcoords='offset pixels',
                             color=self.selection_color,
                             ha='center',
                             size=9,
                             transform=trans,
                             path_effects=buffer,
                             zorder=10)

            # Label end-of-hole depth
            angle = math.degrees(math.atan2(plotz[-1] - plotz[-2], plotx[-1] - plotx[-2])) + 90
            self.ax.text(plotx[-1] + self.selected_hole.section_length * .01, plotz[-1], f" {hole_len:.0f} m ",
                         color=self.selection_color,
                         ha='left',
                         size=8,
                         rotation=angle,
                         path_effects=buffer,
                         zorder=10,
                         rotation_mode='anchor')

            # Plot the end of hole tick
            self.ax.scatter(plotx[-1], plotz[-1],
                            marker=(2, 0, angle + 90),
                            color=self.selection_color,
                            s=100,  # Size
                            zorder=12)

            # Add the horizontal line
            self.ax.axhline(y=0,
                            color=get_line_color("gray", "mpl", self.darkmode),
                            lw=0.6,
                            # path_effects=buffer,
                            zorder=0)

        def plot_mag(c1, c2):
            """
            Plots the magnetic vector quiver plot in the section plot.
            :param c1: (x, y, z) tuple: Corner of the 2D section to plot the mag on.
            :param c2: (x, y, z) tuple: Opposite corner of the 2D section to plot the mag on.
            :return: None
            """
            corners = self.selected_loop.get_loop_coords()
            wire_coords = [(c.x(), c.y(), 0) for c in corners]
            # TODO This won't catch MMR C Loops because there is no PEMFile to reference
            mag_calculator = MagneticFieldCalculator(wire_coords)
            xx, yy, zz, uproj, vproj, wproj, plotx, plotz, arrow_len = mag_calculator.get_2d_magnetic_field(c1, c2)
            self.ax.quiver(xx, zz, plotx, plotz,
                           color=get_line_color("gray", "mpl", self.darkmode),
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
            self.ax.get_yaxis().set_visible(False)
            self.section_canvas.draw()
            return
        elif not self.selected_hole:
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
        plot_hole_section(proj)

        # Get the corners of the 2D section to plot the mag on
        max_z = max(self.ax.get_ylim()[1], 0)
        ratio = self.section_frame.height() / (self.section_frame.width() * 0.9)
        min_z = max_z - (self.selected_hole.section_length * ratio)  # Try to fill the entire plot
        c1 = np.append(p1, max_z)
        c2 = np.append(p2, min_z)
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
                bordercolor=self.foreground_color,
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
        token = open(str(app_data_dir.joinpath(".mapbox")), 'r').read()
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

    def open_tx_file(self, file):
        """
        Parse a Maxwell .tx file and add it as a loop.
        :param file: Path or str, filepath.
        :return: None
        """
        if not isinstance(file, Path):
            file = Path(file)
        print(f"Opening {file.name}.")
        content = read_table(file, header=None, delim_whitespace=True)
        if content.empty:
            logger.warning(f"No coordinates found in {file.name}.")
            return
        else:
            coords = []
            for ind, coord in content.iterrows():
                coords.append(QPointF(coord[0], coord[1]))

        self.add_loop(name=file.name, coords=coords)

    def open_project(self, filepath=None):
        """
        Parse a .LFP file and add the holes and loops in the file to the project
        :filepath: str or Path, filepath of project
        :return: None
        """
        if filepath is None:
            default_path = None
            if self.parent:
                default_path = self.parent.project_dir_edit.text()

            filepath, filetype = QFileDialog.getOpenFileName(self, "Loop Planning File",
                                                             default_path,
                                                             "Loop Planning File (*.LPF)")

        if filepath:
            self.save_name = filepath

            # Remove existing holes and loops
            for ind in reversed(range(len(self.hole_widgets))):
                self.remove_hole(ind, prompt=False)
            for ind in reversed(range(len(self.loop_widgets))):
                self.remove_loop(ind, prompt=False)

            file = open(filepath, "r").read()
            epsg = re.search("EPSG: (\d+)", file).group(1)
            holes = re.findall(
                r">> Hole\n(name:.*\neasting:.*\nnorthing:.*\nelevation:.*\nazimuth:.*\ndip:.*\nlength:.*\n)<<", file)
            loops = re.findall(r">> Loop\n(name:.*\n(?:c.*\n)+)<<", file)

            self.epsg_edit.setText(epsg)
            self.epsg_rbtn.click()

            with pg.ProgressDialog("Opening Project...", 0, len(holes) + len(loops)) as dlg:
                for hole in holes:
                    if dlg.wasCanceled():
                        break

                    properties = dict()
                    for line in hole.split():
                        key, value = line.split(":")
                        if key != "name":
                            value = float(value)
                        properties[key] = value

                    self.add_hole(**properties)

                    dlg += 1

                for loop in loops:
                    if dlg.wasCanceled():
                        break

                    name = re.search("name:(.*)\n", loop).group(1)
                    coord_str = [re.sub("c\d+:", "", line).split(",") for line in loop.split("\n")[1:-1]]
                    coords = [QPointF(float(c[0].strip()), float(c[1].strip())) for c in coord_str]

                    self.add_loop(name=name, coords=coords)

                    dlg += 1

            self.plan_view.autoRange()

    def save_project(self, save_as=False):
        """
        Save the project as a .prj file.
        :return: None
        """
        if not self.hole_widgets and not self.loop_widgets:
            print(f"No holes or loops to save.")
            return

        if save_as or not self.save_name:
            save_name, filetype = QFileDialog.getSaveFileName(self, "Project File Name", "", "Loop Planning File (*.LPF)")
            if save_name:
                self.save_name = save_name
            else:
                return

        result = ''
        result += "EPSG: " + self.get_epsg() + "\n"
        for hole in self.hole_widgets:
            string = '>> Hole\n'
            for key, value in hole.get_properties().items():
                string += f"{key}:{value}\n"
            result += string + "<<\n"
        for loop in self.loop_widgets:
            string = '>> Loop\n'
            for key, value in loop.get_properties().items():
                if key == "coordinates":
                    for j, coord in enumerate(value):
                        string += f"c{j}:{coord.x():.2f}, {coord.y():.2f}\n"
                else:
                    string += f"{key}:{value}\n"
            result += string + "<<\n"

        with open(str(self.save_name), "w+") as file:
            file.write(result)

        # os.startfile(save_name)
        self.statusBar().showMessage("Project file saved.", 1500)

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
            proj = hole_widget.get_proj_latlon(crs).loc[:, "Easting":"Northing"]
            if proj.empty:
                logger.warning(f"{hole_name} projection is empty.")
                continue

            collar = proj.iloc[0]

            collar_point = folder.newpoint(name=hole_name, coords=[collar.to_numpy()])
            collar_point.style = collar_style

            # Add the hole trace
            trace = folder.newlinestring(name=hole_name)
            trace.coords = proj.to_numpy()
            trace.extrude = 1
            trace.style = trace_style

        for loop_widget in self.loop_widgets:
            loop_name = loop_widget.loop_name_edit.text()

            # Add the loop
            loop = loop_widget.get_loop_coords_latlon(crs).loc[:, "Easting":"Northing"]

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
            # try:
            #     logger.info(f"Saving {Path(kmz_save_dir).name}.")
            #     os.startfile(kmz_save_dir)
            # except OSError:
            #     logger.error(f'No application to open {kmz_save_dir}.')
            #     pass

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
            proj = hole_widget.get_proj_latlon(crs).loc[:, "Easting":"Northing"]
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
            loop = loop_widget.get_loop_coords_latlon(crs).loc[:, "Easting":"Northing"]

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
            # try:
            #     logger.info(f"Saving {Path(save_path).name}.")
            #     os.startfile(save_path)
            # except OSError:
            #     logger.error(f'No application to open {save_path}.')
            #     pass
        else:
            self.status_bar.showMessage('Cancelled.', 2000)


class GridPlanner(SurveyPlanner, Ui_GridPlanner):
    """
    Program to plan a surface grid.
    """
    def __init__(self, parent=None, darkmode=False):
        def init_ui():
            self.setWindowTitle('Grid Planner')
            self.setWindowIcon(get_icon('grid_planner.png'))
            self.setGeometry(200, 200, 1100, 700)
            self.actionSave_as_KMZ.setIcon(get_icon("google_earth.png"))
            self.actionSave_as_GPX.setIcon(get_icon("garmin_file.png"))
            self.view_map_action.setIcon(get_icon("folium.png"))
            self.status_bar.addPermanentWidget(self.epsg_label, 0)

        def init_signals():
            def change_loop_width():
                """
                Signal slot: Change the loop ROI dimensions from user input
                :return: None
                """
                height = self.loop_roi.size()[1]
                width = self.loop_width_sbox.value()
                logger.debug(f"Loop width changed to {width}")
                self.loop_roi.setSize((width, height))

            def change_loop_height():
                """
                Signal slot: Change the loop ROI dimensions from user input
                :return: None
                """
                height = self.loop_height_sbox.value()
                width = self.loop_roi.size()[0]
                logger.debug(f"Loop height changed to {height}")
                self.loop_roi.setSize((width, height))

            def change_loop_angle():
                """
                Signal slot: Change the loop ROI angle from user input
                :return: None
                """
                angle = self.loop_angle_sbox.value()
                logger.info(f"Loop angle changed to {angle}")
                self.loop_roi.setAngle(angle)

            def change_grid_angle():
                """
                Signal slot: Change the grid ROI angle from user input. Converts from azimuth to angle
                :return: None
                """
                az = self.grid_az_sbox.value()
                angle = 90 - az
                logger.info(f"Grid angle changed to {az}")
                self.grid_roi.setAngle(angle)

            def change_grid_size():
                """
                Signal slot: Change the grid ROI dimensions from user input
                :return: None
                """
                self.line_length = self.line_length_sbox.value()
                self.line_number = self.line_number_sbox.value()
                self.line_spacing = self.line_spacing_sbox.value()
                self.grid_roi.setSize((self.line_length, max((self.line_number - 1) * self.line_spacing, 10)))
                logger.info(
                    f"Grid size changed to {self.line_length} x {max((self.line_number - 1) * self.line_spacing, 10)}")

            def change_grid_pos():
                """
                Change the position of the grid ROI based on the input from the grid easting and northing spin boxes.
                :return: None
                """
                self.grid_roi.blockSignals(True)

                self.grid_east_center, self.grid_north_center = self.grid_easting_sbox.value(), self.grid_northing_sbox.value()
                self.grid_roi.setPos(self.grid_east_center, self.grid_north_center)

                self.plot_grid()
                self.plan_view.autoRange(items=[self.loop_roi, self.grid_roi])

                self.grid_roi.blockSignals(False)

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

            def loop_moved():
                """
                Signal slot: Updates the values of the loop width, height and angle when the loop ROI is changed, then
                replots the section plot.
                :return: None
                """
                self.loop_width_sbox.blockSignals(True)
                self.loop_height_sbox.blockSignals(True)
                self.loop_angle_sbox.blockSignals(True)
                x, y = self.loop_roi.pos()
                w, h = self.loop_roi.size()
                angle = self.loop_roi.angle()
                self.loop_width_sbox.setValue(w)
                self.loop_height_sbox.setValue(h)
                self.loop_angle_sbox.setValue(angle)
                self.loop_width_sbox.blockSignals(False)
                self.loop_height_sbox.blockSignals(False)
                self.loop_angle_sbox.blockSignals(False)
                self.plot_grid()

            def grid_moved():
                """
                Signal slot: Update the grid easting and northing text based on the new position of the grid when the
                ROI is moved.
                :return: None
                """
                self.grid_easting_sbox.blockSignals(True)
                self.grid_northing_sbox.blockSignals(True)

                x, y = self.grid_roi.pos()
                self.grid_easting, self.grid_northing = x, y
                self.grid_east_center, self.grid_north_center = self.get_grid_center(x, y)
                self.grid_easting_sbox.setValue(self.grid_east_center)
                self.grid_northing_sbox.setValue(self.grid_north_center)

                self.grid_easting_sbox.blockSignals(False)
                self.grid_northing_sbox.blockSignals(False)
                self.plot_grid()

            def copy_loop_to_clipboard():
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
                cb = QApplication.clipboard()
                cb.clear(mode=cb.Clipboard)
                cb.setText(result, mode=cb.Clipboard)

                self.status_bar.showMessage('Loop corner coordinates copied to clipboard.', 1000)

            def copy_grid_to_clipboard():
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
                cb = QApplication.clipboard()
                cb.clear(mode=cb.Clipboard)
                cb.setText(result, mode=cb.Clipboard)
                self.status_bar.showMessage('Grid coordinates copied to clipboard', 1000)

            # Menu
            self.actionSave_as_KMZ.triggered.connect(self.save_kmz)
            self.actionSave_as_KMZ.setIcon(get_icon('google_earth.png'))
            self.actionSave_as_GPX.triggered.connect(self.save_gpx)
            self.actionSave_as_GPX.setIcon(get_icon('garmin_file.png'))
            # self.view_map_action.setDisabled(True)
            self.view_map_action.triggered.connect(self.view_map)
            self.view_map_action.setIcon(get_icon('folium.png'))
            self.actionCopy_Loop_to_Clipboard.triggered.connect(copy_loop_to_clipboard)
            self.actionCopy_Grid_to_Clipboard.triggered.connect(copy_grid_to_clipboard)

            self.loop_height_sbox.valueChanged.connect(change_loop_height)
            self.loop_width_sbox.valueChanged.connect(change_loop_width)
            self.loop_angle_sbox.valueChanged.connect(change_loop_angle)
            self.grid_az_sbox.valueChanged.connect(change_grid_angle)

            self.grid_easting_sbox.valueChanged.connect(self.plot_grid)
            self.grid_easting_sbox.valueChanged.connect(change_grid_pos)
            self.grid_northing_sbox.valueChanged.connect(self.plot_grid)
            self.grid_northing_sbox.valueChanged.connect(change_grid_pos)
            self.grid_az_sbox.valueChanged.connect(self.plot_grid)
            self.line_number_sbox.valueChanged.connect(self.plot_grid)
            self.line_number_sbox.valueChanged.connect(change_grid_size)
            self.line_length_sbox.valueChanged.connect(self.plot_grid)
            self.line_length_sbox.valueChanged.connect(change_grid_size)
            self.station_spacing_sbox.valueChanged.connect(self.plot_grid)
            self.line_spacing_sbox.valueChanged.connect(self.plot_grid)
            self.line_spacing_sbox.valueChanged.connect(change_grid_size)

            # CRS
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
            set_epsg_label()

            # Plots
            self.grid_roi.sigRegionChangeStarted.connect(lambda: self.grid_roi.setPen('b'))
            self.grid_roi.sigRegionChangeFinished.connect(lambda: self.grid_roi.setPen(None))
            self.grid_roi.sigRegionChangeFinished.connect(grid_moved)
            self.loop_roi.sigRegionChangeFinished.connect(loop_moved)

        def init_crs():
            """
            Populate the CRS drop boxes and connect all their signals
            """
            # Add the GPS system and datum drop box options
            gps_systems = ['', 'Lat/Lon', 'UTM']
            for system in gps_systems:
                self.gps_system_cbox.addItem(system)

            datums = ['', 'WGS 1984', 'NAD 1927', 'NAD 1983']
            for datum in datums:
                self.gps_datum_cbox.addItem(datum)

            int_valid = QIntValidator()
            self.epsg_edit.setValidator(int_valid)

            self.gps_system_cbox.setCurrentIndex(2)
            self.gps_datum_cbox.setCurrentIndex(1)
            self.gps_zone_cbox.setCurrentIndex(17)

        def format_plots():
            """
            Initial set-up of the plan view. Creates the plot widget, custom axes for the Y and X axes, and adds the loop ROI.
            :return: None
            """
            yaxis = PlanMapAxis(orientation='left')
            xaxis = PlanMapAxis(orientation='bottom')
            # yaxis = NonScientific(orientation='left')
            # xaxis = NonScientific(orientation='bottom')
            self.grid_roi.setAngle(90)
            self.loop_roi.setZValue(0)
            self.loop_roi.addScaleHandle([0, 0], [0.5, 0.5], lockAspect=True)
            self.loop_roi.addScaleHandle([1, 0], [0.5, 0.5], lockAspect=True)
            self.loop_roi.addScaleHandle([1, 1], [0.5, 0.5], lockAspect=True)
            self.loop_roi.addScaleHandle([0, 1], [0.5, 0.5], lockAspect=True)
            self.loop_roi.addRotateHandle([1, 0.5], [0.5, 0.5])
            self.loop_roi.addRotateHandle([0.5, 0], [0.5, 0.5])
            self.loop_roi.addRotateHandle([0.5, 1], [0.5, 0.5])
            self.loop_roi.addRotateHandle([0, 0.5], [0.5, 0.5])
            self.plan_view.setAxisItems({'bottom': xaxis, 'left': yaxis})
            self.plan_view.showGrid(x=True, y=True, alpha=0.2)
            self.plan_view.setAspectLocked()
            self.plan_view.hideButtons()
            self.plan_view.getAxis('right').setWidth(15)
            # self.plan_view.setContentsMargins(150, 150, 150, 150)
            self.plan_view.getAxis("right").setStyle(showValues=False)  # Disable showing the values of axis
            self.plan_view.getAxis("top").setStyle(showValues=False)  # Disable showing the values of axis
            self.plan_view.showAxis('right', show=True)  # Show the axis edge line
            self.plan_view.showAxis('top', show=True)  # Show the axis edge line
            self.plan_view.showLabel('right', show=False)
            self.plan_view.showLabel('top', show=False)
            self.plan_view.setLabel('left', 'Northing (m)')
            self.plan_view.setLabel('bottom', 'Easting (m)')

        super().__init__()
        self.setupUi(self)
        init_ui()

        self.parent = parent
        self.darkmode = darkmode

        self.background_color = get_line_color("background", "mpl", self.darkmode)
        self.foreground_color = get_line_color("foreground", "mpl", self.darkmode)
        self.line_color = get_line_color("blue", "mpl", self.darkmode)
        self.loop_color = get_line_color("purple", "mpl", self.darkmode)
        self.selection_color = get_line_color("teal", "mpl", self.darkmode) if self.darkmode else selection_color

        self.loop_roi = None
        self.grid_roi = None
        self.loop_height = self.loop_height_sbox.value()
        self.loop_width = self.loop_width_sbox.value()
        self.loop_angle = self.loop_angle_sbox.value()
        self.grid_easting = self.grid_easting_sbox.value()
        self.grid_northing = self.grid_northing_sbox.value()
        self.grid_az = self.grid_az_sbox.value()
        self.line_number = self.line_number_sbox.value()
        self.line_length = self.line_length_sbox.value()
        self.station_spacing = self.station_spacing_sbox.value()
        self.line_spacing = self.line_spacing_sbox.value()
        self.grid_east_center = None
        self.grid_north_center = None
        self.lines = []

        # Plots
        # Create the grid
        center_x, center_y = self.get_grid_center(self.grid_easting, self.grid_northing, az=0)
        grid_width, grid_length = (self.line_number - 1) * self.line_spacing, self.line_length
        self.grid_roi = RectLoop([self.grid_easting + (grid_width / 2), self.grid_northing - (grid_length / 2)],
                                 [grid_length, grid_width],
                                 scaleSnap=True,
                                 pen=pg.mkPen(None, width=1.5))
        self.plan_view.addItem(self.grid_roi)

        self.show()

        # Create the loop ROI
        self.loop_roi = RectLoop([self.grid_easting - (grid_length / 2), self.grid_northing - (grid_length / 2)],
                                 [self.loop_width, self.loop_height],
                                 scaleSnap=True,
                                 pen=pg.mkPen(self.loop_color, width=1.5))
        self.plan_view.addItem(self.loop_roi)

        self.grid_lines_plot = pg.MultiPlotItem()
        self.grid_lines_plot.setZValue(1)
        format_plots()

        self.plan_view.autoRange()
        self.plot_grid()

        init_signals()
        init_crs()

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
                if not isinstance(item, RectLoop):
                    self.plan_view.removeItem(item)

        clear_plots()

        x, y = self.grid_roi.pos()
        center_x, center_y = self.get_grid_center(x, y)
        self.get_grid_corner_coords()

        self.grid_az = self.grid_az_sbox.value()
        self.line_length = self.line_length_sbox.value()
        self.station_spacing = self.station_spacing_sbox.value()
        self.line_spacing = self.line_spacing_sbox.value()
        self.line_number = self.line_number_sbox.value()

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
                text_angle = self.grid_roi.angle() + 90
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
            station_text = pg.TextItem(text=line_name, color=self.line_color,
                                       angle=text_angle,
                                       rotateAxis=(0, 1),
                                       anchor=text_anchor)
            station_text.setPos(x_start, y_start)
            self.plan_view.addItem(station_text)

            # Add station labels
            for j, station in enumerate(range(int(self.line_length / self.station_spacing) + 1)):
                station_x, station_y = transform_station(x_start, y_start, j * self.station_spacing)
                station_name = f"{self.station_spacing * (j + 1)}{station_suffix}"
                station_names.append(station_name)
                station_xs.append(station_x)
                station_ys.append(station_y)
            self.lines[i]['station_coords'] = list(zip(station_xs, station_ys, station_names))

            line_plot = pg.PlotDataItem(station_xs, station_ys, pen=self.line_color)
            line_plot.setZValue(1)
            stations_plot = pg.ScatterPlotItem(station_xs, station_ys, pen=self.line_color, brush=self.background_color)
            stations_plot.setZValue(2)

            self.plan_view.addItem(line_plot)
            self.plan_view.addItem(stations_plot)

        # Plot a symbol at the center of the grid
        grid_center = pg.ScatterPlotItem([center_x], [center_y], pen=self.line_color, symbol='+')
        grid_center.setZValue(1)
        self.plan_view.addItem(grid_center)

    def grid_to_df(self):
        """
        Convert the grid lines to a data frame
        :return: DataFrame
        """
        line_list = []
        for line in self.lines:
            name = line['line_name']

            for station in line['station_coords']:
                easting = station[0]
                northing = station[1]
                station = station[2]
                line_list.append([name, easting, northing, station])

        df = DataFrame(line_list, columns=['Line_name', 'Easting', 'Northing', 'Station'])
        return df

    def get_grid_corner_coords(self):
        """
        Return the coordinates of the grid corners.
        :return: list of (x, y)
        """
        x, y = self.grid_roi.pos()
        w, h = self.grid_roi.size()
        angle = self.grid_roi.angle() - 90
        c1 = (x, y)
        c2 = (c1[0] + w * (math.cos(math.radians(angle))), c1[1] + w * (math.sin(math.radians(angle))))
        c3 = (c2[0] - h * (math.sin(math.radians(angle))), c2[1] + h * (math.sin(math.radians(90 - angle))))
        c4 = (c3[0] + w * (math.cos(math.radians(180 - angle))), c3[1] - w * (math.sin(math.radians(180 - angle))))
        corners = [c1, c2, c3, c4]

        # self.grid_stations_plot.addPoints([coord[0] for coord in corners],
        #                        [coord[1] for coord in corners], pen=pg.mkPen(width=3, color='r'))
        return corners

    def get_grid_center(self, x, y, az=None):
        """
        Find the center of the grid given the bottom-right coordinate of the grid.
        :param x: float, X coordinate of the bottom-right corner
        :param y: float, Y coordinate of the bottom-right corner
        :param az: float, azimuth of the grid ROI.
        :return: X, Y coordinate of the center of the grid.
        """
        if az is None:
            az = self.grid_roi.angle() - 90
        w = max((self.line_number - 1) * self.line_spacing, 10)
        h = self.line_length

        hypo = math.sqrt(w ** 2 + h ** 2)
        angle = math.degrees(math.atan(h / w)) + az
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
            return DataFrame()
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

    def get_loop_coords(self):
        """
        Return the coordinates of the loop corners
        :return: list of (x, y)
        """
        x, y = self.loop_roi.pos()
        w, h = self.loop_roi.size()
        angle = self.loop_roi.angle()
        c1 = (x, y)
        c2 = (c1[0] + w * (math.cos(math.radians(angle))), c1[1] + w * (math.sin(math.radians(angle))))
        c3 = (c2[0] - h * (math.sin(math.radians(angle))), c2[1] + h * (math.sin(math.radians(90 - angle))))
        c4 = (c3[0] + w * (math.cos(math.radians(180 - angle))), c3[1] - w * (math.sin(math.radians(180 - angle))))
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
            return DataFrame()
        else:
            crs = CRS.from_epsg(epsg)

        # Get the loop data
        loop = DataFrame(self.get_loop_coords(), columns=['Easting', 'Northing'])
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
        token = open(str(app_data_dir.joinpath(".mapbox")), 'r').read()
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

    def save_project(self):
        pass

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


class PolyLoop(pg.PolyLineROI):
    """
    Custom ROI for transmitter loops. Created in order to change the color of the ROI lines when highlighted.
    """
    sigHandleAdded = Signal(object)
    sigHandleRemoved = Signal(object)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        pass

    def _makePen(self):
        # Generate the pen color for this ROI based on its current state.
        if self.mouseHovering:
            # print(f"Mouse hovering")
            return pg.mkPen(self.pen.color(), width=self.pen.width() + 0.5)
        else:
            return self.pen

    def addSegment(self, h1, h2, index=None):

        class CustomSegment(pg.LineSegmentROI):
            """
            Reimplement in order to set the hover pen to the same color as the current loop pen color, and disable rotating
            the segment.
            """

            # Used internally by pg.PolyLineROI
            def __init__(self, *args, **kwds):
                self._parentHovering = False
                pg.LineSegmentROI.__init__(self, *args, **kwds)

            def setParentHover(self, hover):
                # set independently of own hover state
                if self._parentHovering != hover:
                    self._parentHovering = hover
                    self._updateHoverColor()

            def _makePen(self):
                if self.mouseHovering or self._parentHovering:
                    return pg.mkPen(self.pen.color(), width=self.pen.width() + 0.5)
                else:
                    return self.pen

            def hoverEvent(self, ev):
                # accept drags even though we discard them to prevent competition with parent ROI
                # (unless parent ROI is not movable)
                if self.parentItem().translatable:
                    ev.acceptDrags(Qt.LeftButton)
                return pg.LineSegmentROI.hoverEvent(self, ev)

            def setAngle(self, *args, **kwargs):
                # Disable rotating the line segment
                pass

        seg = CustomSegment(handles=(h1, h2), pen=self.pen, parent=self, movable=False)
        if index is None:
            self.segments.append(seg)
        else:
            self.segments.insert(index, seg)
        seg.sigClicked.connect(self.segmentClicked)
        seg.setAcceptedMouseButtons(Qt.LeftButton)
        seg.setZValue(self.zValue() + 1)
        for h in seg.handles:
            h['item'].setDeletable(True)
            h['item'].setAcceptedMouseButtons(h['item'].acceptedMouseButtons() | Qt.LeftButton)  ## have these handles take left clicks too, so that handles cannot be added on top of other handles

    def addHandle(self, info, index=None):

        class CustomHandle(Handle):
            """
            Re-implementing Handle to change the size and color (especially when hovering) of the handles.
            """
            def __init__(self, *args, **kwds):
                Handle.__init__(self, *args, **kwds)
                # self.pen = pg.mkPen(selection_color, width=1.)

            def hoverEvent(self, ev):
                hover = False
                if not ev.isExit():
                    if ev.acceptDrags(Qt.LeftButton):
                        hover = True
                    for btn in [Qt.LeftButton, Qt.RightButton, Qt.MidButton]:
                        if int(self.acceptedMouseButtons() & btn) > 0 and ev.acceptClicks(btn):
                            hover = True

                if hover:
                    self.currentPen = pg.mkPen(self.pen.color(), width=self.pen.width() + 1.5)
                else:
                    self.currentPen = self.pen
                self.update()

        # Reimplement so a signal can be emitted
        # h = CustomHandle(6, typ="r", pen=pg.mkPen(selection_color, width=1.), parent=self)
        h = CustomHandle(6, typ="r", pen=self.pen, parent=self)
        h.setPos(info['pos'] * self.state['size'])
        info['item'] = h

        h.connectROI(self)
        if index is None:
            self.handles.append(info)
        else:
            self.handles.insert(index, info)

        h.setZValue(self.zValue() + 1)
        h.sigRemoveRequested.connect(self.removeHandle)
        self.stateChanged(finish=True)
        self.sigHandleAdded.emit(h)
        return h

    def removeHandle(self, handle, updateSegments=True):
        self.sigHandleRemoved.emit(handle)
        pg.ROI.removeHandle(self, handle)
        handle.sigRemoveRequested.disconnect(self.removeHandle)

        if not updateSegments:
            return
        segments = handle.rois[:]

        if len(segments) == 1:
            self.removeSegment(segments[0])
        elif len(segments) > 1:
            handles = [h['item'] for h in segments[1].handles]
            handles.remove(handle)
            segments[0].replaceHandle(handle, handles[0])
            self.removeSegment(segments[1])
        self.stateChanged(finish=True)

    def setAngle(self, angle, center=None, centerLocal=None, snap=False, update=True, finish=True):
        """
        Set the ROI's rotation angle.

        =============== ==========================================================================
        **Arguments**
        angle           (float) The final ROI angle in degrees
        center          (None | Point) Optional center point around which the ROI is rotated,
                        expressed as [0-1, 0-1] over the size of the ROI.
        centerLocal     (None | Point) Same as *center*, but the position is expressed in the
                        local coordinate system of the ROI
        snap            (bool) If True, the final ROI angle is snapped to the nearest increment
                        (default is 15 degrees; see ROI.rotateSnapAngle)
        update          (bool) See setPos()
        finish          (bool) See setPos()
        =============== ==========================================================================
        """
        if not -360 < angle < 360:
            return

        if update not in (True, False):
            raise TypeError("update argument must be bool")

        if snap is True:
            angle = round(angle / self.rotateSnapAngle) * self.rotateSnapAngle

        self.state['angle'] = angle
        tr = QTransform()  # note: only rotation is contained in the transform
        tr.rotate(angle)
        if center is not None:
            centerLocal = QPointF(center) * self.state['size']
        if centerLocal is not None:
            centerLocal = QPointF(centerLocal)
            # rotate to new angle, keeping a specific point anchored as the center of rotation
            cc = self.mapToParent(centerLocal) - (tr.map(centerLocal) + self.state['pos'])
            self.translate(cc, update=False)

        self.setTransform(tr)
        if update:
            self.stateChanged(finish=finish)


class RectLoop(pg.RectROI):
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

    def addHandle(self, info, index=None):

        class CustomHandle(Handle):
            """
            Re-implementing Handle to change the size and color (especially when hovering) of the handles.
            """
            def __init__(self, *args, **kwds):
                Handle.__init__(self, *args, **kwds)
                # self.pen = pg.mkPen(selection_color, width=1.)

            def hoverEvent(self, ev):
                hover = False
                if not ev.isExit():
                    if ev.acceptDrags(Qt.LeftButton):
                        hover = True
                    for btn in [Qt.LeftButton, Qt.RightButton, Qt.MidButton]:
                        if int(self.acceptedMouseButtons() & btn) > 0 and ev.acceptClicks(btn):
                            hover = True

                if hover:
                    self.currentPen = pg.mkPen(self.pen.color(), width=self.pen.width() + 1.5)
                else:
                    self.currentPen = self.pen
                self.update()

        # Reimplement so a signal can be emitted
        # h = CustomHandle(6, typ="r", pen=pg.mkPen(selection_color, width=1.), parent=self)
        h = CustomHandle(6, typ="r", pen=self.pen, parent=self)
        h.setPos(info['pos'] * self.state['size'])
        info['item'] = h

        h.connectROI(self)
        if index is None:
            self.handles.append(info)
        else:
            self.handles.insert(index, info)

        h.setZValue(self.zValue() + 1)
        h.sigRemoveRequested.connect(self.removeHandle)
        self.stateChanged(finish=True)
        # self.sigHandleAdded.emit(h)
        return h

def main():
    from src.qt_py import dark_palette
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    darkmode = True
    if darkmode:
        app.setPalette(dark_palette)
    pg.setConfigOptions(antialias=True)
    pg.setConfigOption('crashWarning', True)
    pg.setConfigOption('background', (66, 66, 66) if darkmode else 'w')
    pg.setConfigOption('foreground', "w" if darkmode else (53, 53, 53))

    samples_folder = Path(__file__).parents[2].joinpath('sample_files')
    # planner = LoopPlanner(darkmode=darkmode)
    planner = GridPlanner(darkmode=darkmode)

    # hole_data = read_excel(r"C:\_Data\2021\Canadian Palladium\_Planning\Crone_BHEM_Collars.xlsx").dropna()
    # for ind, hole in hole_data.iterrows():
    #     planner.add_hole(name=hole["HOLE-ID"],
    #                      easting=hole["UTM_E"],
    #                      northing=hole["UTM_N"],
    #                      length=hole.LENGTH,
    #                      azimuth=hole.AZIMUTH,
    #                      dip=hole.DIP
    #                      )
    planner.show()
    # planner.save_project()
    # planner.open_project(filepath=r"C:\_Data\2021\TMC\Galloway Project\_Planning\GA mk2.LPF")
    # planner.gps_system_cbox.setCurrentIndex(2)
    # planner.gps_datum_cbox.setCurrentIndex(3)
    # planner.gps_zone_cbox.setCurrentIndex(18)
    # planner.crs_rbtn.click()
    # planner.view_map()

    # tx_file = samples_folder.joinpath(r"Tx Files/Loop.tx")
    # planner.open_tx_file(tx_file)
    # planner.hole_widgets[0].get_dad_file()
    # planner.hole_az_edit.setText('174')
    # planner.view_map()
    # planner.save_gpx()

    app.exec_()


if __name__ == '__main__':
    main()
