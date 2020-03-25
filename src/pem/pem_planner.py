import math
import os
import sys
import re
import numpy as np
import utm
import simplekml

import matplotlib.backends.backend_tkagg  # Needed for pyinstaller, or receive  ImportError
import matplotlib.ticker as ticker
import pyqtgraph as pg
from PyQt5 import QtGui, QtCore, uic
from PyQt5.QtWidgets import (QApplication, QMainWindow, QFileDialog)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from src.mag_field.mag_field_calculator import MagneticFieldCalculator
from src.gps.gpx_module import gpxpy
from src.gps.gpx_module.gpxpy import gpx

sys._excepthook = sys.excepthook


def exception_hook(exctype, value, traceback):
    print(exctype, value, traceback)
    sys._excepthook(exctype, value, traceback)
    sys.exit(1)


sys.excepthook = exception_hook

if getattr(sys, 'frozen', False):
    # If the application is run as a bundle, the pyInstaller
    # extends the sys module by a flag frozen=True and sets t
    # path into variable _MEIPASS'.
    application_path = sys._MEIPASS
    loopPlannerCreatorFile = 'qt_ui\\loop_planner.ui'
    gridPlannerCreatorFile = 'qt_ui\\grid_planner.ui'
    icons_path = 'icons'
else:
    application_path = os.path.dirname(os.path.abspath(__file__))
    loopPlannerCreatorFile = os.path.join(os.path.dirname(application_path), 'qt_ui\\loop_planner.ui')
    gridPlannerCreatorFile = os.path.join(os.path.dirname(application_path), 'qt_ui\\grid_planner.ui')
    icons_path = os.path.join(os.path.dirname(application_path), "qt_ui\\icons")

# Load Qt ui file into a class
Ui_LoopPlannerWindow, QtBaseClass = uic.loadUiType(loopPlannerCreatorFile)
Ui_GridPlannerWindow, QtBaseClass = uic.loadUiType(gridPlannerCreatorFile)

pg.setConfigOptions(antialias=True)
pg.setConfigOption('background', 'w')
pg.setConfigOption('foreground', 'k')
pg.setConfigOption('crashWarning', True)
# Ensure using PyQt5 backend
matplotlib.use('QT5Agg')


class LoopPlanner(QMainWindow, Ui_LoopPlannerWindow):
    """
    Program that plots the magnetic field projected to a plane perpendicular to a borehole for a interactive loop.
    Loop and borehole collar can be exported as KMZ or GPX files.
    """

    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.setWindowTitle('Loop Planner')
        self.setWindowIcon(QtGui.QIcon(os.path.join(icons_path, 'loop_planner.png')))
        self.setGeometry(200, 200, 1400, 700)
        self.dialog = QFileDialog()

        self.hole_easting = int(self.hole_easting_edit.text())
        self.hole_northing = int(self.hole_northing_edit.text())
        self.hole_az = int(self.hole_az_edit.text())
        self.hole_dip = -int(self.hole_dip_edit.text())
        self.hole_length = int(self.hole_length_edit.text())
        self.hole_elevation = 0

        self.section_figure = Figure()
        self.ax = self.section_figure.add_subplot()
        self.section_canvas = FigureCanvas(self.section_figure)
        self.section_view_layout.addWidget(self.section_canvas)

        # Signals
        self.actionSave_as_KMZ.triggered.connect(self.save_kmz)
        self.actionSave_as_GPX.triggered.connect(self.save_gpx)

        self.loop_height_edit.returnPressed.connect(self.change_loop_height)
        self.loop_width_edit.returnPressed.connect(self.change_loop_width)
        self.loop_angle_edit.returnPressed.connect(self.change_loop_angle)

        self.hole_easting_edit.returnPressed.connect(self.plot_hole)
        self.hole_northing_edit.returnPressed.connect(self.plot_hole)
        self.hole_az_edit.returnPressed.connect(self.plot_hole)
        self.hole_dip_edit.returnPressed.connect(self.plot_hole)
        self.hole_length_edit.returnPressed.connect(self.plot_hole)

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
        self.hole_az_edit.setValidator(az_validator)
        self.hole_dip_edit.setValidator(dip_validator)
        self.hole_length_edit.setValidator(size_validator)

        # Plots
        self.hole_trace_plot = pg.PlotDataItem()
        # self.hole_trace_plot.showGrid()
        self.hole_collar_plot = pg.ScatterPlotItem()
        self.section_extent_line = pg.PlotDataItem()
        self.loop_plot = pg.ScatterPlotItem()

        self.setup_plan_view()
        self.setup_section_view()
        self.setup_gps_boxes()

        self.plot_hole()
        self.plan_view_plot.autoRange()

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

        def get_section_extents():
            """
            Calculates the two coordinates to be used for the section plot.
            :return: (x, y) tuples of the two end-points.
            """
            # Remove the previously plotted section line
            self.section_extent_line.clear()

            x, y, z = get_hole_projection()

            # Calculate the length of the cross-section
            line_len = math.ceil(self.hole_length / 400) * 400
            if 90 < self.hole_az < 180 or 270 < self.hole_az < 360:
                # Line center is based on the 80th percentile down the hole
                line_center_x = np.percentile(x, 80)
                line_center_y = np.percentile(y, 80)
            else:
                # Line center is based on the 80th percentile down the hole
                line_center_x = np.percentile(x, 80)
                line_center_y = np.percentile(y, 80)

            dx = math.sin(math.radians(self.hole_az)) * (line_len / 2)
            dy = math.cos(math.radians(self.hole_az)) * (line_len / 2)

            p1 = (line_center_x - dx, line_center_y - dy)
            p2 = (line_center_x + dx, line_center_y + dy)

            # Plot the section line
            self.section_extent_line.setData([line_center_x - dx, line_center_x + dx],
                                                       [line_center_y - dy, line_center_y + dy], width=1,
                                                       pen=pg.mkPen(color=0.5, style=QtCore.Qt.DashLine))
            self.plan_view_plot.addItem(self.section_extent_line)
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
            self.ax.plot(plotx[0], plotz[0], 'o', mfc='w', markeredgecolor='dimgray', zorder=10)
            # Plot the hole section line
            self.ax.plot(plotx, plotz, color='dimgray', lw=1, zorder=1)
            self.ax.axhline(y=0, color='dimgray', lw=0.6, zorder=9)

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
            self.ax.quiver(xx, zz, plotx, plotz, color='dimgray', label='Field', pivot='middle', zorder=0,
                           units='dots', scale=.050, width=.8, headlength=11, headwidth=6)

        def plot_trace(xs, ys):
            """
            Plot the hole trace on the plan view plot.
            :param xs: list: X values to plot
            :param ys: list: Y values to plot
            :return: None
            """
            self.hole_trace_plot.setData(xs, ys, pen=pg.mkPen(width=2, color=0.5))
            self.hole_collar_plot.setData([self.hole_easting], [self.hole_northing],
                                                       pen=pg.mkPen(width=3, color=0.5))
            self.plan_view_plot.addItem(self.hole_trace_plot)
            self.plan_view_plot.addItem(self.hole_collar_plot)

        if int(self.hole_easting_edit.text()) != self.hole_easting:
            shift_amt = int(self.hole_easting_edit.text()) - self.hole_easting
            self.shift_loop(shift_amt, 0)
            self.hole_easting = int(self.hole_easting_edit.text())
        if int(self.hole_northing_edit.text()) != self.hole_northing:
            shift_amt = int(self.hole_northing_edit.text()) - self.hole_northing
            self.shift_loop(0, shift_amt)
            self.hole_northing = int(self.hole_northing_edit.text())
        self.hole_az = int(self.hole_az_edit.text())
        self.hole_dip = -int(self.hole_dip_edit.text())
        self.hole_length = int(self.hole_length_edit.text())

        self.hole_trace_plot.clear()
        self.hole_collar_plot.clear()
        self.ax.clear()

        xs, ys, zs = get_hole_projection()
        p1, p2 = get_section_extents()

        plot_trace(xs, ys)
        plot_hole_section(p1, p2, list(zip(xs, ys, zs)))

        # Get the corners of the 2D section to plot the mag on
        c1, c2 = list(p1), list(p2)
        c1.append(self.ax.get_ylim()[1])  # Add the max Z
        c2.append(self.ax.get_ylim()[0])  # Add the min Z
        plot_mag(c1, c2)

        self.section_canvas.draw()

    def setup_gps_boxes(self):
        """
        Adds the items in the drop down menus for the GPS information.
        :return: None
        """
        self.gps_systems = ['UTM']
        self.gps_zones = [f"{num} North" for num in range(1, 61)] + [f"{num} South" for num in range(1, 61)]
        self.gps_datums = ['NAD 1983', 'WGS 1984']

        for system in self.gps_systems:
            self.systemCBox.addItem(system)
        for zone in self.gps_zones:
            self.zoneCBox.addItem(zone)
        for datum in self.gps_datums:
            self.datumCBox.addItem(datum)

        self.systemCBox.setCurrentIndex(0)
        self.zoneCBox.setCurrentIndex(16)
        self.datumCBox.setCurrentIndex(1)

    def setup_plan_view(self):
        """
        Initial set-up of the plan view. Creates the plot widget, custom axes for the Y and X axes, and adds the loop ROI.
        :return: None
        """
        yaxis = CustomAxis(orientation='left')
        xaxis = CustomAxis(orientation='bottom')
        self.plan_view_plot = self.plan_view_widget.addPlot(row=1, col=0, axisItems={'bottom': xaxis, 'left': yaxis})
        self.plan_view_plot.showGrid(x=True, y=True, alpha=0.2)
        # self.plan_view_vb.disableAutoRange('xy')
        self.plan_view_plot.setAspectLocked()

        # loop_roi is the loop.
        self.loop_roi = LoopROI([self.hole_easting-250, self.hole_northing-250], [500, 500], scaleSnap=True, pen=pg.mkPen('m', width=1.5))
        self.plan_view_plot.addItem(self.loop_roi)
        self.loop_roi.setZValue(10)
        self.loop_roi.addScaleHandle([0, 0], [0.5, 0.5], lockAspect=True)
        self.loop_roi.addScaleHandle([1, 0], [0.5, 0.5], lockAspect=True)
        self.loop_roi.addScaleHandle([1, 1], [0.5, 0.5], lockAspect=True)
        self.loop_roi.addScaleHandle([0, 1], [0.5, 0.5], lockAspect=True)
        self.loop_roi.addRotateHandle([1, 0.5], [0.5, 0.5])
        self.loop_roi.addRotateHandle([0.5, 0], [0.5, 0.5])
        self.loop_roi.addRotateHandle([0.5, 1], [0.5, 0.5])
        self.loop_roi.addRotateHandle([0, 0.5], [0.5, 0.5])
        self.loop_roi.sigRegionChangeFinished.connect(self.plan_region_changed)

    def setup_section_view(self):
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

    def change_loop_width(self):
        height = self.loop_roi.size()[1]
        width = self.loop_width_edit.text()
        width = float(width)
        print(f"Loop width changed to {width}")
        self.loop_roi.setSize((width, height))

    def change_loop_height(self):
        height = self.loop_height_edit.text()
        width = self.loop_roi.size()[0]
        height = float(height)
        print(f"Loop height changed to {height}")
        self.loop_roi.setSize((width, height))

    def change_loop_angle(self):
        angle = self.loop_angle_edit.text()
        angle = float(angle)
        print(f"Loop angle changed to {angle}")
        self.loop_roi.setAngle(angle)

    def plan_region_changed(self):
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
        self.plan_view_plot.autoRange(items=[self.loop_roi])
        self.loop_roi.blockSignals(False)

    def get_loop_coords(self):
        """
        Return the coordinates of the loop corners
        :return: list of (x, y, z)
        """
        x, y = self.loop_roi.pos()
        w, h = self.loop_roi.size()
        angle = self.loop_roi.angle()
        c1 = (x, y, self.hole_elevation)
        c2 = (c1[0] + w * (math.cos(math.radians(angle))), c1[1] + w * (math.sin(math.radians(angle))), self.hole_elevation)
        c3 = (c2[0] - h * (math.sin(math.radians(angle))), c2[1] + h * (math.sin(math.radians(90-angle))), self.hole_elevation)
        c4 = (c3[0] + w * (math.cos(math.radians(180-angle))), c3[1] - w * (math.sin(math.radians(180-angle))), self.hole_elevation)
        corners = [c1, c2, c3, c4]

        # self.loop_plot.clear()
        # self.loop_plot.setData([coord[0] for coord in corners],
        #                        [coord[1] for coord in corners], pen=pg.mkPen(width=3, color='r'))
        # self.plan_view_vb.addItem(self.loop_plot)

        return corners

    def get_loop_lonlat(self):
        zone = self.zoneCBox.currentText()
        zone_num = int(re.search('\d+', zone).group())
        north = True if 'n' in zone.lower() else False

        loop_gps = self.get_loop_coords()
        loop_lonlat = []
        for row in loop_gps:
            easting = int(float(row[0]))
            northing = int(float(row[1]))
            lat, lon = utm.to_latlon(easting, northing, zone_num, northern=north)
            loop_lonlat.append((lon, lat))

        return loop_lonlat

    def get_collar_lonlat(self):
        zone = self.zoneCBox.currentText()
        zone_num = int(re.search('\d+', zone).group())
        north = True if 'n' in zone.lower() else False

        easting = self.hole_easting
        northing = self.hole_northing
        lat, lon = utm.to_latlon(easting, northing, zone_num, northern=north)
        return lon, lat

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
        loop_lonlat = self.get_loop_lonlat()
        loop_lonlat.append(loop_lonlat[0])
        ls = folder.newlinestring(name=loop_name)
        ls.coords = loop_lonlat
        ls.extrude = 1
        ls.style = loop_style

        # Creates KMZ object for the collar
        lon, lat = self.get_collar_lonlat()
        collar = folder.newpoint(name=hole_name, coords=[(lon, lat)])
        collar.style = collar_style

        save_dir = self.dialog.getSaveFileName(self, 'Save KMZ File', None, 'KMZ Files (*.KMZ);; All files(*.*)')[0]
        if save_dir:
            kmz_save_dir = os.path.splitext(save_dir)[0] + '.kmz'
            kml.savekmz(kmz_save_dir, format=False)
            os.startfile(kmz_save_dir)
        else:
            self.window().statusBar().showMessage('Cancelled.', 2000)

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

        # Add the loop coordinates to the GPX. Creates a route for the loop and adds the corners as waypoints.
        loop_lonlat = self.get_loop_lonlat()
        loop_lonlat.append(loop_lonlat[0])
        route = gpxpy.gpx.GPXRoute()
        for i, coord in enumerate(loop_lonlat):
            lon = coord[0]
            lat = coord[1]
            waypoint = gpxpy.gpx.GPXWaypoint(latitude=lat, longitude=lon, name=loop_name, description=f"{loop_name}-{i}")
            gpx.waypoints.append(waypoint)
            route.points.append(waypoint)
        gpx.routes.append(route)

        # Add the collar coordinates to the GPX as a waypoint.
        hole_lonlat= self.get_collar_lonlat()
        waypoint = gpxpy.gpx.GPXWaypoint(latitude=hole_lonlat[1], longitude=hole_lonlat[0], name=hole_name, description=hole_name)
        gpx.waypoints.append(waypoint)

        save_path = self.dialog.getSaveFileName(self, 'Save GPX File', None, 'GPX Files (*.GPX);; All files(*.*)')[0]
        if save_path:
            with open(save_path, 'w') as f:
                f.write(gpx.to_xml())
            self.statusBar().showMessage('Save complete.', 2000)
            os.startfile(save_path)
        else:
            self.window().statusBar().showMessage('Cancelled.', 2000)


class GridPlanner(QMainWindow, Ui_GridPlannerWindow):
    """
    Program to plan a surface grid.
    """

    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.setWindowTitle('Grid Planner')
        self.setWindowIcon(QtGui.QIcon(os.path.join(icons_path, 'grid_planner.png')))
        self.setGeometry(200, 200, 1100, 700)
        self.dialog = QFileDialog()

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
        self.lines =[]

        # Signals
        self.actionSave_as_KMZ.triggered.connect(self.save_kmz)
        self.actionSave_as_GPX.triggered.connect(self.save_gpx)

        self.loop_height_edit.returnPressed.connect(self.change_loop_height)
        self.loop_width_edit.returnPressed.connect(self.change_loop_width)
        self.loop_angle_edit.returnPressed.connect(self.change_loop_angle)
        self.grid_az_edit.returnPressed.connect(self.change_grid_angle)

        self.grid_easting_edit.returnPressed.connect(self.plot_grid)
        self.grid_easting_edit.returnPressed.connect(self.change_grid_pos)
        self.grid_northing_edit.returnPressed.connect(self.plot_grid)
        self.grid_northing_edit.returnPressed.connect(self.change_grid_pos)
        self.grid_az_edit.returnPressed.connect(self.plot_grid)
        self.line_number_edit.returnPressed.connect(self.plot_grid)
        self.line_number_edit.returnPressed.connect(self.change_grid_size)
        self.line_length_edit.returnPressed.connect(self.plot_grid)
        self.line_length_edit.returnPressed.connect(self.change_grid_size)
        self.station_spacing_edit.returnPressed.connect(self.plot_grid)
        self.line_spacing_edit.returnPressed.connect(self.plot_grid)
        self.line_spacing_edit.returnPressed.connect(self.change_grid_size)

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

        # Plots
        self.grid_lines_plot = pg.MultiPlotItem()
        self.grid_lines_plot.setZValue(1)

        self.setup_plan_view()
        self.setup_gps_boxes()

        self.plot_grid()
        self.plan_view_plot.autoRange()

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
            for item in reversed(self.plan_view_plot.items):
                if not isinstance(item, LoopROI):
                    self.plan_view_plot.removeItem(item)

        clear_plots()

        x, y = self.grid_roi.pos()
        center_x, center_y = self.get_grid_center(x, y)
        self.get_grid_coords()

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
            self.plan_view_plot.addItem(station_text)

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

            self.plan_view_plot.addItem(line_plot)
            self.plan_view_plot.addItem(stations_plot)

        grid_center = pg.ScatterPlotItem([center_x],[center_y], pen='b', symbol='+')
        grid_center.setZValue(1)
        self.plan_view_plot.addItem(grid_center)

    def setup_gps_boxes(self):
        """
        Adds the items in the drop down menus for the GPS information.
        :return: None
        """
        self.gps_systems = ['UTM']
        self.gps_zones = [f"{num} North" for num in range(1, 61)] + [f"{num} South" for num in range(1, 61)]
        self.gps_datums = ['NAD 1983', 'WGS 1984']

        for system in self.gps_systems:
            self.systemCBox.addItem(system)
        for zone in self.gps_zones:
            self.zoneCBox.addItem(zone)
        for datum in self.gps_datums:
            self.datumCBox.addItem(datum)

        self.systemCBox.setCurrentIndex(0)
        self.zoneCBox.setCurrentIndex(16)
        self.datumCBox.setCurrentIndex(1)

    def setup_plan_view(self):
        """
        Initial set-up of the plan view. Creates the plot widget, custom axes for the Y and X axes, and adds the loop ROI.
        :return: None
        """

        def set_loop():
            center_x, center_y = self.get_grid_center(self.grid_easting, self.grid_northing)
            self.loop_roi = LoopROI([center_x - (self.loop_width / 2),
                                     center_y - (self.loop_height / 2)],
                                    [self.loop_width, self.loop_height], scaleSnap=True,
                                    pen=pg.mkPen('m', width=1.5))
            self.plan_view_plot.addItem(self.loop_roi)
            self.loop_roi.setZValue(0)
            self.loop_roi.addScaleHandle([0, 0], [0.5, 0.5], lockAspect=True)
            self.loop_roi.addScaleHandle([1, 0], [0.5, 0.5], lockAspect=True)
            self.loop_roi.addScaleHandle([1, 1], [0.5, 0.5], lockAspect=True)
            self.loop_roi.addScaleHandle([0, 1], [0.5, 0.5], lockAspect=True)
            self.loop_roi.addRotateHandle([1, 0.5], [0.5, 0.5])
            self.loop_roi.addRotateHandle([0.5, 0], [0.5, 0.5])
            self.loop_roi.addRotateHandle([0.5, 1], [0.5, 0.5])
            self.loop_roi.addRotateHandle([0, 0.5], [0.5, 0.5])
            self.loop_roi.sigRegionChangeFinished.connect(self.loop_moved)

        def set_grid():
            self.grid_roi = LoopROI([self.grid_easting, self.grid_northing],
                                    [self.line_length, (self.line_number - 1) * self.line_spacing], scaleSnap=True,
                                    pen=pg.mkPen(None, width=1.5))
            self.grid_roi.setAngle(90)
            self.plan_view_plot.addItem(self.grid_roi)
            self.grid_roi.sigRegionChangeStarted.connect(lambda: self.grid_roi.setPen('b'))
            self.grid_roi.sigRegionChangeFinished.connect(lambda: self.grid_roi.setPen(None))
            self.grid_roi.sigRegionChangeFinished.connect(self.grid_moved)

        yaxis = CustomAxis(orientation='left')
        xaxis = CustomAxis(orientation='bottom')
        self.plan_view_plot = self.plan_view_widget.addPlot(row=1, col=0, axisItems={'bottom': xaxis, 'left': yaxis})
        self.plan_view_plot.showGrid(x=True, y=True, alpha=0.2)
        self.plan_view_plot.setAspectLocked()
        set_grid()
        set_loop()

    def change_loop_width(self):
        height = self.loop_roi.size()[1]
        width = self.loop_width_edit.text()
        width = float(width)
        print(f"Loop width changed to {width}")
        self.loop_roi.setSize((width, height))

    def change_loop_height(self):
        height = self.loop_height_edit.text()
        width = self.loop_roi.size()[0]
        height = float(height)
        print(f"Loop height changed to {height}")
        self.loop_roi.setSize((width, height))

    def change_loop_angle(self):
        angle = self.loop_angle_edit.text()
        angle = float(angle)
        print(f"Loop angle changed to {angle}")
        self.loop_roi.setAngle(angle)

    def change_grid_angle(self):
        az = int(self.grid_az_edit.text())
        angle = 90 - az
        print(f"Grid angle changed to {az}")
        self.grid_roi.setAngle(angle)

    def change_grid_size(self):
        self.line_length = int(self.line_length_edit.text())
        self.line_number = int(self.line_number_edit.text())
        self.line_spacing = int(self.line_spacing_edit.text())
        self.grid_roi.setSize((self.line_length, (self.line_number - 1) * self.line_spacing))
        print(f"Grid size changed to {self.line_length} x {(self.line_number - 1) * self.line_spacing}")

    def change_grid_pos(self):
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
            w = (self.line_number - 1) * self.line_spacing
            h = self.line_length

            hypo = math.sqrt(w ** 2 + h ** 2)
            angle = math.degrees(math.atan(h / w)) + a
            theta = math.radians(angle)
            dx = (hypo / 2) * math.cos(theta)
            dy = (hypo / 2) * math.sin(theta)
            center = pg.ScatterPlotItem([x + dx], [y - dy], pen='y')
            self.plan_view_plot.addItem(center)
            print(f"Corner is at {x + dx}, {y - dy}")
            return x + dx, y - dy

        x, y = get_corner(int(self.grid_easting_edit.text()), int(self.grid_northing_edit.text()))
        easting_shift = x - self.grid_easting
        northing_shift = y - self.grid_northing
        self.shift_loop(easting_shift, northing_shift)
        self.grid_easting, self.grid_northing = x, y
        self.grid_roi.setPos(x, y)

        self.grid_east_center, self.grid_north_center = int(self.grid_easting_edit.text()), int(self.grid_northing_edit.text())
        print(f"Grid position changed to {self.grid_east_center, self.grid_north_center}")

        self.plot_grid()
        self.plan_view_plot.autoRange(items=[self.loop_roi, self.grid_roi])

    def grid_moved(self):
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

    def loop_moved(self):
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

    def shift_loop(self, dx, dy):
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

    def get_grid_coords(self):
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
        w = (self.line_number - 1) * self.line_spacing
        h = self.line_length

        hypo = math.sqrt(w ** 2 + h ** 2)
        angle = math.degrees(math.atan(h / w)) + a
        theta = math.radians(angle)
        dx = (hypo / 2) * math.cos(theta)
        dy = (hypo / 2) * math.sin(theta)
        # print(f"Center is at {x - dx}, {y + dy}")
        return x - dx, y + dy

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
        c3 = (c2[0] - h * (math.sin(math.radians(angle))), c2[1] + h * (math.sin(math.radians(90-angle))))
        c4 = (c3[0] + w * (math.cos(math.radians(180-angle))), c3[1] - w * (math.sin(math.radians(180-angle))))
        corners = [c1, c2, c3, c4]

        return corners

    def get_loop_lonlat(self):
        zone = self.zoneCBox.currentText()
        zone_num = int(re.search('\d+', zone).group())
        north = True if 'n' in zone.lower() else False

        loop_gps = self.get_loop_coords()
        loop_lonlat = []
        for row in loop_gps:
            easting = int(float(row[0]))
            northing = int(float(row[1]))
            lat, lon = utm.to_latlon(easting, northing, zone_num, northern=north)
            loop_lonlat.append((lon, lat))

        return loop_lonlat

    def get_grid_lonlat(self):
        """
        Convert the coordinates of all stations in the grid to lon lat.
        :return: List of dicts with lonlat coordinates.
        """
        zone = self.zoneCBox.currentText()
        zone_num = int(re.search('\d+', zone).group())
        north = True if 'n' in zone.lower() else False

        lonlat_lines = []

        for line in self.lines:
            line_name = line['line_name']
            coords = line['station_coords']
            lonlat_coords = []

            for easting, northing, station_name in coords:
                lat, lon = utm.to_latlon(easting, northing, zone_num, northern=north)
                lonlat_coords.append((lon, lat, station_name))

            lonlat_lines.append({'line_name': line_name, 'station_coords': lonlat_coords})

        return lonlat_lines

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
        loop_name = self.loop_name_edit.text()
        if not loop_name:
            loop_name = 'Loop'

        # Creates KMZ objects for the loop.
        loop_lonlat = self.get_loop_lonlat()
        loop_lonlat.append(loop_lonlat[0])
        ls = grid_folder.newlinestring(name=loop_name)
        ls.coords = loop_lonlat
        ls.extrude = 1
        ls.style = loop_style

        # Creates KMZ object for the lines and stations
        for line in self.get_grid_lonlat():
            line_coords = line['station_coords']
            line_name = line['line_name']
            kmz_line_coords = []
            line_folder = grid_folder.newfolder(name=line_name)
            for lon, lat, station_name in line_coords:
                new_point = line_folder.newpoint(name=f"{station_name}", coords=[(lon, lat)])
                new_point.style = station_style
                kmz_line_coords.append((lon, lat))

            ls = line_folder.newlinestring(name=line_name)
            ls.coords = line_coords
            ls.extrude = 1
            ls.style = trace_style

        save_dir = self.dialog.getSaveFileName(self, 'Save KMZ File', None, 'KMZ Files (*.KMZ);; All files(*.*)')[0]
        if save_dir:
            kmz_save_dir = os.path.splitext(save_dir)[0] + '.kmz'
            kml.savekmz(kmz_save_dir, format=False)
            os.startfile(kmz_save_dir)
        else:
            self.window().statusBar().showMessage('Cancelled.', 2000)

    def save_gpx(self):
        """
        Save the loop and collar coordinates to a GPX file.
        :return: None
        """
        gpx = gpxpy.gpx.GPX()

        grid_name = self.grid_name_edit.text()
        if not grid_name:
            grid_name = 'Grid'
        loop_name = self.loop_name_edit.text()
        if not loop_name:
            loop_name = 'Loop'

        # Add the loop coordinates to the GPX. Creates a route for the loop and adds the corners as waypoints.
        loop_lonlat = self.get_loop_lonlat()
        loop_lonlat.append(loop_lonlat[0])
        route = gpxpy.gpx.GPXRoute()
        for i, coord in enumerate(loop_lonlat):
            lon = coord[0]
            lat = coord[1]
            waypoint = gpxpy.gpx.GPXWaypoint(latitude=lat, longitude=lon, name=loop_name, description=f"{loop_name}-{i}")
            gpx.waypoints.append(waypoint)
            route.points.append(waypoint)
        gpx.routes.append(route)

        # Add the collar coordinates to the GPX as a waypoint.
        grid_lonlat = self.get_grid_lonlat()
        for line in grid_lonlat:
            line_name = line['line_name']
            coords = line['station_coords']

            for coord in coords:
                station = coord[2]
                waypoint = gpxpy.gpx.GPXWaypoint(latitude=coord[1], longitude=coord[0],
                                                 name=f"L{line_name.strip()}-{station}", description=station)
                gpx.waypoints.append(waypoint)

        save_path = self.dialog.getSaveFileName(self, 'Save GPX File', grid_name, 'GPX Files (*.GPX);; All files(*.*)')[0]
        if save_path:
            with open(save_path, 'w') as f:
                f.write(gpx.to_xml())
            self.statusBar().showMessage('Save complete.', 2000)
            os.startfile(save_path)
        else:
            self.window().statusBar().showMessage('Cancelled.', 2000)


class LoopROI(pg.ROI):
    """
    Custom ROI for transmitter loops. Created in order to change the color of the ROI lines when highlighted.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _makePen(self):
        # Generate the pen color for this ROI based on its current state.
        if self.mouseHovering:
            # style=QtCore.Qt.DashLine,
            return pg.mkPen(self.pen.color(), width=3)
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


if __name__ == '__main__':
    app = QApplication(sys.argv)
    # planner = LoopPlanner()
    planner = GridPlanner()
    planner.show()
    planner.save_gpx()

    app.exec_()
