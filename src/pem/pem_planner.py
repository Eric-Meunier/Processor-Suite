import math
import os
import sys
import numpy as np

import matplotlib.backends.backend_tkagg  # Needed for pyinstaller, or receive  ImportError
import matplotlib.ticker as ticker
import pyqtgraph as pg
from PyQt5 import QtGui, uic
from PyQt5.QtWidgets import (QApplication, QMainWindow)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib import pyplot as plt
from src.mag_field import wire, biotsavart

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
else:
    application_path = os.path.dirname(os.path.abspath(__file__))
    loopPlannerCreatorFile = os.path.join(os.path.dirname(application_path), 'qt_ui\\loop_planner.ui')

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
        self.setup_plan_view()
        self.setup_section_view()
        self.setup_gps_boxes()

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

        self.hole_trace = pg.PlotDataItem()
        self.hole_collar = pg.ScatterPlotItem()
        self.cs = None

        self.plot_hole()
        self.plot_mag()

    def plot_hole(self):

        def get_hole_trace():
            delta_surf = length * math.cos(math.radians(dip))
            dx = delta_surf * math.sin(math.radians(az))
            dy = delta_surf * math.cos(math.radians(az))
            x = [0, dx]
            y = [0, dy]
            return x, y

        def get_hole_section():
            x, y = 0, 0
            dx = length * math.cos(math.radians(-dip))
            dy = length * math.sin(math.radians(-dip))
            x = [x, x + dx]
            y = [y, y + dy]
            return x, y

        self.hole_trace.clear()
        self.hole_collar.clear()
        self.ax.clear()

        # For plotting purposes, easting and northing are always 0 and 0.
        az = int(self.hole_az_edit.text())
        dip = int(self.hole_dip_edit.text())
        length = int(self.hole_length_edit.text())
        tx, ty = get_hole_trace()

        self.hole_trace = pg.PlotDataItem(tx, ty, pen=pg.mkPen(width=2, color=0.5))
        self.hole_collar = pg.ScatterPlotItem([0], [0], pen=pg.mkPen(width=3, color=0.5))
        self.plan_view_vb.addItem(self.hole_trace)
        self.plan_view_vb.addItem(self.hole_collar)

        sx, sy = get_hole_section()
        self.ax.plot(sx, sy, '-')
        self.ax.plot(0, 0, 'o')

        x_lim = self.ax.get_xlim()
        mid_point = (abs(x_lim[1] - x_lim[0]) / 2) + x_lim[0]
        # self.ax.set_xlim(right=, left = )
        self.ax.set_xlim(right=mid_point + length * 1.5, left = mid_point - length * 1.5)
        self.ax.set_ylim(top=0,  bottom=-length * 1.2)
        # self.plot_mag()

    def plot_mag(self):
        xmin, xmax = self.ax.get_xlim()
        ymin, ymax = self.ax.get_ylim()
        x, y = self.loop_roi.pos()
        w, h = self.loop_roi.size()
        loop_coords = np.array([(x, y, 0), (x + w, y, 0), (x + w, y + h, 0), (x, y + h, 0), (x, y, 0)])
        loop_wire = wire.Wire(path=loop_coords, discretization_length=1)
        sol = biotsavart.BiotSavart(wire=loop_wire)

        dip = int(self.hole_dip_edit.text())
        length = int(self.hole_length_edit.text())
        x, y = 0, 0
        dx = length * math.cos(math.radians(-dip))
        dy = length * math.sin(math.radians(-dip))
        xs = np.linspace(x, x + dx, 50)
        ys = np.linspace(y, y + dy, 50)
        zs = np.linspace(0, -length, 50)
        xys = list(zip(xs, ys))
        # xx, yy, zz = np.meshgrid(xs, ys, zs)
        # points = [[(xy, z) for xy in xys] for z in zs]
        points = []
        for z in zs:
            for (x, y) in zip(xs, ys):
                points.append([x, y, z])
        # points = [[[item in tuple for tuple in xy] for xy in xys] for z in zs]
        points = np.array(points)

        # resolution = 50
        # volume_corner1 = (xmin, ymin, 0)
        # volume_corner2 = (xmax, ymax, 0)
        #
        # # matplotlib plot 2D
        # # create list of xy coordinates
        # grid = np.mgrid[volume_corner1[0]:volume_corner2[0]:resolution, volume_corner1[1]:volume_corner2[1]:resolution]
        #
        # # create list of grid points
        # points = np.vstack(map(np.ravel, grid)).T
        # points = np.hstack([points, np.zeros([len(points), 1])])  # Adds a third column with 0 as its entry
        #
        # # calculate B field at given points
        B = sol.CalculateB(points=points)
        #
        Babs = np.linalg.norm(B, axis=1)

        # remove big values close to the wire
        cutoff = 0.005

        B[Babs > cutoff] = [np.nan, np.nan, np.nan]
        # Babs[Babs > cutoff] = np.nan

        for ba in B:
            print(ba)

        self.ax.clear()
        self.plot_hole()
        # self.ax.quiver(points[:, 0], points[:, 1], B[:, 0], B[:, 1], scale=0.01)
        X = np.unique(points[:, 0])
        Y = np.unique(points[:, 2])
        self.ax.contour(X, Y, Babs.reshape([len(X), len(Y)]).T, 10)
        self.section_canvas.draw()
        # ax.clabel(cs)

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
        self.plan_view_vb.autoRange()
        self.loop_roi.sigRegionChangeFinished.connect(self.plan_region_changed)
        # self.plan_region_changed()

    def setup_section_view(self):
        self.section_figure = Figure()
        self.ax = self.section_figure.add_subplot()
        self.section_canvas = FigureCanvas(self.section_figure)
        self.section_view_layout.addWidget(self.section_canvas)

        # self.ax.set_xlim(right=0, left=10)
        self.ax.set_aspect('equal')
        self.ax.use_sticky_edges = False  # So the plot doesn't re-size after the first time it's plotted
        # self.ax.yaxis.tick_left()
        # self.ax.yaxis.set_major_formatter(ticker.StrMethodFormatter('{x:.0f}'))
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

        self.plot_mag()


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