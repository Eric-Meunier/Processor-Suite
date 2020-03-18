import math
import os
import sys
import numpy as np

import matplotlib.backends.backend_tkagg  # Needed for pyinstaller, or receive  ImportError
import matplotlib.ticker as ticker
import pyqtgraph as pg
from PyQt5 import QtGui, QtCore, uic
from PyQt5.QtWidgets import (QApplication, QMainWindow)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib import pyplot as plt
import matplotlib.transforms as mtransforms
from src.mag_field import wire, biotsavart
from src.mag_field.mag_field_calculator import MagneticFieldCalculator

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
    icons_path = 'icons'
else:
    application_path = os.path.dirname(os.path.abspath(__file__))
    loopPlannerCreatorFile = os.path.join(os.path.dirname(application_path), 'qt_ui\\loop_planner.ui')
    icons_path = os.path.join(os.path.dirname(application_path), "qt_ui\\icons")

# Load Qt ui file into a class
Ui_LoopPlannerWindow, QtBaseClass = uic.loadUiType(loopPlannerCreatorFile)


pg.setConfigOptions(antialias=True)
pg.setConfigOption('background', 'w')
pg.setConfigOption('foreground', 'k')
pg.setConfigOption('crashWarning', True)
# Ensure using PyQt5 backend
matplotlib.use('QT5Agg')


class LoopPlanner(QMainWindow, Ui_LoopPlannerWindow):

    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.setWindowTitle('Loop Planner')
        self.setWindowIcon(QtGui.QIcon(os.path.join(icons_path, 'loop_planner.png')))
        self.setGeometry(200, 200, 1400, 700)
        self.setup_plan_view()
        self.setup_section_view()
        self.setup_gps_boxes()

        self.hole_easting = int(self.hole_easting_edit.text())
        self.hole_northing = int(self.hole_northing_edit.text())
        self.hole_az = int(self.hole_az_edit.text())
        self.hole_dip = -int(self.hole_dip_edit.text())
        self.hole_length = int(self.hole_length_edit.text())
        self.hole_elevation = 0

        self.loop_height_edit.returnPressed.connect(self.change_loop_height)
        self.loop_width_edit.returnPressed.connect(self.change_loop_width)
        self.loop_angle_edit.returnPressed.connect(self.change_loop_angle)

        # self.hole_easting_edit.returnPressed.connect(self.plot_hole)
        # self.hole_northing_edit.returnPressed.connect(self.plot_hole)
        self.hole_az_edit.returnPressed.connect(self.plot_hole)
        self.hole_dip_edit.returnPressed.connect(self.plot_hole)
        self.hole_length_edit.returnPressed.connect(self.plot_hole)

        size_validator = QtGui.QIntValidator()
        size_validator.setBottom(0)
        az_validator = QtGui.QIntValidator()
        az_validator.setRange(0, 360)
        dip_validator = QtGui.QIntValidator()
        dip_validator.setRange(0, 90)

        self.loop_height_edit.setValidator(size_validator)
        self.loop_width_edit.setValidator(size_validator)
        self.loop_angle_edit.setValidator(size_validator)

        self.hole_easting_edit.setValidator(size_validator)
        self.hole_northing_edit.setValidator(size_validator)
        self.hole_az_edit.setValidator(az_validator)
        self.hole_dip_edit.setValidator(dip_validator)
        self.hole_length_edit.setValidator(size_validator)

        self.hole_trace_plot = pg.PlotDataItem()
        self.hole_collar_plot = pg.ScatterPlotItem()
        self.section_center = pg.ScatterPlotItem()
        self.section_line = pg.PlotDataItem()
        self.cs = None

        self.plot_hole()
        self.plan_view_vb.autoRange()

    def plot_hole(self):

        def get_hole_projection():
            x, y, z = self.hole_easting, self.hole_northing, self.hole_elevation
            delta_surf = self.hole_length * math.cos(math.radians(self.hole_dip))
            dx = delta_surf * math.sin(math.radians(self.hole_az))
            dy = delta_surf * math.cos(math.radians(self.hole_az))
            dz = self.hole_length * math.sin(math.radians(self.hole_dip))
            x = [x, dx]
            y = [y, dy]
            z = [z, dz]
            return x, y, z

        def get_section_extents():
            # Remove the previously plotted center and section line
            self.section_center.clear()
            self.section_line.clear()

            x, y, z = get_hole_projection()
            # Line center is based on the 80th percentile down the hole
            line_center_x = np.percentile(x, 80)
            line_center_y = np.percentile(y, 80)

            # Calculate the length of the cross-section
            line_len = math.ceil(self.hole_length / 400) * 400
            dx = math.sin(math.radians(self.hole_az)) * (line_len / 2)
            dy = math.cos(math.radians(self.hole_az)) * (line_len / 2)

            p1 = (line_center_x - dx, line_center_y - dy)
            p2 = (line_center_x + dx, line_center_y + dy)

            # Plot the center point and section line
            self.section_center = pg.ScatterPlotItem([line_center_x], [line_center_y], width=3, pen='r')
            self.section_line = pg.PlotDataItem([line_center_x - dx, line_center_x + dx],
                                                [line_center_y - dy, line_center_y + dy], width=1,
                                                pen=pg.mkPen(color=0.5, style=QtCore.Qt.DashLine))
            self.plan_view_vb.addItem(self.section_center)
            self.plan_view_vb.addItem(self.section_line)
            return p1, p2

        def plot_hole_section(p1, p2, hole_projection):

            def get_magnitude(vector):
                return math.sqrt(sum(i ** 2 for i in vector))

            # hole_projection as [(x0, y0, z0), (x1, y1, z1)...]
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
                # print(f"Azimuth = {self.hole_az}")
                # print(f"p1, p2 = {p1}, {p2}")
                # print(f"p ([p1[0], p1[1], 0]) = {p}")
                # print(f"vec ([p2[0] - p1[0], p2[1] - p1[1], 0]) = {vec}")
                # print(f"planeNormal (np.cross(vec, [0, 0, -1])) = {planeNormal}")
                # print(f"coords = {q}")
                # print(f"q_proj (q - np.dot(q - p, planeNormal) * planeNormal) = {q_proj}")
                # print(f"distvec (np.array([q_proj[0] - p[0], q_proj[1] - p[1]])) = {distvec}")
                # print(f"x (np.sqrt(distvec.dot(distvec))) = {dist}")
                # print(f"z (q_proj[2]) = {q_proj[2]}\n")

            # Plot the collar
            self.ax.plot(plotx[0], plotz[0], 'o', markerfacecolor='w', markeredgecolor='k')
            # Plot the hole section line
            self.ax.plot(plotx, plotz, color='dimgray', lw=1)

        def plot_mag(c1, c2):

            wire_coords = self.get_loop_coords()
            mag_calculator = MagneticFieldCalculator(wire_coords)
            xx, yy, zz, uproj, vproj, wproj,  plotx, plotz, arrow_len = mag_calculator.get_2d_magnetic_field(c1, c2)
            self.ax.quiver(xx, zz, plotx, plotz, color='dimgray', label='Field', pivot='middle', zorder=0,
                       units='dots', scale=.050, width=.8, headlength=11, headwidth=6)

        self.hole_easting = 0
        # self.hole_easting = int(self.hole_easting_edit.text())
        self.hole_northing = 0
        # self.hole_northing = int(self.hole_northing_edit.text())
        self.hole_az = int(self.hole_az_edit.text())
        self.hole_dip = -int(self.hole_dip_edit.text())
        self.hole_length = int(self.hole_length_edit.text())

        self.hole_trace_plot.clear()
        self.hole_collar_plot.clear()
        self.ax.clear()

        xs, ys, zs = get_hole_projection()

        self.hole_trace_plot = pg.PlotDataItem(xs, ys, pen=pg.mkPen(width=2, color=0.5))
        self.hole_collar_plot = pg.ScatterPlotItem([0], [0], pen=pg.mkPen(width=3, color=0.5))
        self.plan_view_vb.addItem(self.hole_trace_plot)
        self.plan_view_vb.addItem(self.hole_collar_plot)

        p1, p2 = get_section_extents()
        plot_hole_section(p1, p2, list(zip(xs, ys, zs)))
        c1, c2 = list(p1), list(p2)
        c1.append(self.ax.get_ylim()[1])
        c2.append(self.ax.get_ylim()[0])
        plot_mag(c1, c2)

        self.section_canvas.draw()

    def setup_gps_boxes(self):
        self.gps_systems = ['', 'UTM']
        self.gps_zones = [''] + [f"{num} North" for num in range(1, 61)] + [f"{num} South" for num in range(1, 61)]
        self.gps_datums = ['', 'NAD 1927', 'NAD 1983', 'WGS 1984']

        for system in self.gps_systems:
            self.systemCBox.addItem(system)
        for zone in self.gps_zones:
            self.zoneCBox.addItem(zone)
        for datum in self.gps_datums:
            self.datumCBox.addItem(datum)

    def setup_plan_view(self):
        self.plan_view_vb = self.plan_view_widget.addViewBox(row=1, col=0, lockAspect=True)
        # self.plan_view_vb.disableAutoRange('xy')

        # loop_roi is the loop.
        self.loop_roi = LoopROI([-250, -250], [500, 500], pen=pg.mkPen('m', width=1.5))
        self.plan_view_vb.addItem(self.loop_roi)
        self.loop_roi.setZValue(10)
        self.loop_roi.addScaleHandle([1, 0.5], [0.5, 0.5])
        self.loop_roi.addScaleHandle([0.5, 0], [0.5, 0.5])
        self.loop_roi.addScaleHandle([0.5, 1], [0.5, 0.5])
        self.loop_roi.addScaleHandle([0, 0.5], [0.5, 0.5])
        self.loop_roi.addRotateHandle([1, 1], [0.5, 0.5])
        self.loop_roi.addRotateHandle([0, 0], [0.5, 0.5])
        self.loop_roi.addRotateHandle([1, 0], [0.5, 0.5])
        self.loop_roi.addRotateHandle([0, 1], [0.5, 0.5])
        # self.plan_view_vb.autoRange()
        self.loop_roi.sigRegionChangeFinished.connect(self.plan_region_changed)

    def setup_section_view(self):
        self.section_figure = Figure()
        self.ax = self.section_figure.add_subplot()
        self.section_canvas = FigureCanvas(self.section_figure)
        self.section_view_layout.addWidget(self.section_canvas)

        # self.ax.set_xlim(right=0, left=10)
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
        self.loop_width_edit.blockSignals(True)
        self.loop_height_edit.blockSignals(True)
        self.loop_angle_edit.blockSignals(True)
        x, y = self.loop_roi.pos()
        w, h = self.loop_roi.size()
        angle = self.loop_roi.angle()
        self.loop_width_edit.setText(f"{w:.0f}")
        self.loop_height_edit.setText(f"{h:.0f}")
        self.loop_angle_edit.setText(f"{angle:.0f}")
        print(f"Lower left corner: {x}, {y}")
        print(f"Lower right corner: {x + w}, {y}")
        print(f"Upper Right corner: {x + w}, {y + h}")
        print(f"Upper left corner: {x}, {y + h}")
        self.loop_width_edit.blockSignals(False)
        self.loop_height_edit.blockSignals(False)
        self.loop_angle_edit.blockSignals(False)

        self.plot_hole()

    def get_loop_coords(self):
        """
        Return the coordinates of the loop corners
        :return: list of (x, y, z)
        """
        x, y = self.loop_roi.pos()
        w, h = self.loop_roi.size()
        return [(x, y, self.hole_elevation), (x + w, y, self.hole_elevation), (x + w, y + h, self.hole_elevation), (x, y+h, self.hole_elevation)]


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


if __name__ == '__main__':
    from src.pem.pem_getter import PEMGetter

    app = QApplication(sys.argv)
    pem_getter = PEMGetter()
    pem_files = pem_getter.get_pems()
    # editor = PEMPlotEditor(pem_files[0])
    # editor.show()
    planner = LoopPlanner()
    planner.show()

    app.exec_()