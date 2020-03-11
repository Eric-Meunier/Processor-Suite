import math, os, sys, itertools
import matplotlib.backends.backend_tkagg  # Needed for pyinstaller, or receive  ImportError
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas, NavigationToolbar2QT as NavigationToolbar
import numpy as np
import pyqtgraph as pg
from numpy import linspace, meshgrid
from PyQt5.QtWidgets import (QErrorMessage, QApplication, QWidget, QMainWindow)
from PyQt5 import QtGui, QtCore, uic
from matplotlib import patches
from matplotlib.figure import Figure
import matplotlib.transforms as mtransforms
from src.pem.pem_plotter import MagneticFieldCalculator as MagCalc
from matplotlib import patheffects
from timeit import default_timer as timer
from matplotlib.backends.backend_pdf import PdfPages
from mpl_toolkits.mplot3d import Axes3D  # Needed for 3D plots
import mpl_toolkits.mplot3d.art3d as art3d
from scipy import interpolate as interp
from scipy import stats
from statistics import mean


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

        self.ax.plot(0, 0, 'ro')

    def plot_hole(self, easting=0, northing=0, az=0, dip=60, length=400):
        mfc = MagCalc()

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
        self.loop_roi = LoopROI([0, 0], [500, 500], pen=pg.mkPen('m', width=1.5))
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
        self.plan_region_changed()

    def setup_section_view(self):
        self.section_figure = Figure()
        self.ax = self.section_figure.add_subplot()
        self.section_canvas = FigureCanvas(self.section_figure)
        self.section_view_layout.addWidget(self.section_canvas)

    def change_loop_width(self):
        height = self.loop_roi.size()[1]
        width = self.loop_width_edit.text()
        try:
            width = float(width)
        except ValueError:
            print('Value is not a number')
        else:
            print(f"Loop width changed to {width}")
            self.loop_roi.setSize((width, height))

    def change_loop_height(self):
        height = self.loop_height_edit.text()
        width = self.loop_roi.size()[0]
        try:
            height = float(height)
        except ValueError:
            print('Value is not a number')
        else:
            print(f"Loop height changed to {height}")
            self.loop_roi.setSize((width, height))

    def change_loop_angle(self):
        angle = self.loop_angle_edit.text()
        try:
            angle = float(angle)
        except ValueError:
            print('Value is not a number')
        else:
            print(f"Loop angle changed to {angle}")
            self.loop_roi.setAngle(angle)

    def plan_region_changed(self):
        self.loop_width_edit.blockSignals(True)
        self.loop_height_edit.blockSignals(True)
        self.loop_angle_edit.blockSignals(True)
        x, y = self.loop_roi.pos()
        w, h = self.loop_roi.size()
        angle = self.loop_roi.angle()
        self.loop_width_edit.setText(f"{w:.1f}")
        self.loop_height_edit.setText(f"{h:.1f}")
        self.loop_angle_edit.setText(f"{angle:.1f}")
        print(f"Lower left corner: {x}, {y}")
        print(f"Upper left corner: {x}, {y + h}")
        print(f"Upper Right corner: {x + w}, {y + h}")
        print(f"Lower left corner: {x + w}, {y}")
        self.loop_width_edit.blockSignals(False)
        self.loop_height_edit.blockSignals(False)
        self.loop_angle_edit.blockSignals(False)


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