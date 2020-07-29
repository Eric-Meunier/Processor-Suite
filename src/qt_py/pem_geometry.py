from PyQt5 import (uic)
from PyQt5.QtWidgets import (QMainWindow)

import copy
import sys
import os
import math
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from PyQt5.QtWidgets import (QApplication)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.lines import Line2D
from src.mpl.interactive_spline import InteractiveSpline
from src.mpl.zoom_pan import ZoomPan

if getattr(sys, 'frozen', False):
    application_path = sys._MEIPASS
    pemGeometryCreatorFile = 'qt_ui\\pem_geometry.ui'
    icons_path = 'icons'
else:
    application_path = os.path.dirname(os.path.abspath(__file__))
    pemGeometryCreatorFile = os.path.join(os.path.dirname(application_path), 'qt_ui\\pem_geometry.ui')
    icons_path = os.path.join(os.path.dirname(application_path), "qt_ui\\icons")

# Load Qt ui file into a class
Ui_PemGeometry, QtBaseClass = uic.loadUiType(pemGeometryCreatorFile)


class PEMGeometry(QMainWindow, Ui_PemGeometry):

    def __init__(self, parent=None):
        super().__init__()
        self.setupUi(self)
        self.setWindowTitle('PEM Geometry')
        self.resize(1100, 800)

        self.parent = parent
        self.pem_file = None
        self.az_line = None
        self.az_spline = None
        self.background = None
        self.df = None

        self.figure, (self.mag_ax, self.dip_ax, self.roll_ax) = plt.subplots(1, 3, sharey=True)
        # self.figure.subplots_adjust(left=0.10, bottom=0.15, right=0.97, top=0.92)
        self.canvas = FigureCanvas(self.figure)
        self.plots_layout.addWidget(self.canvas)

        self.mag_ax.use_sticky_edges = False
        self.dip_ax.use_sticky_edges = False
        self.roll_ax.use_sticky_edges = False
        self.mag_ax.invert_yaxis()

        self.az_ax = self.mag_ax.twiny()
        # self.roll_ax.spines["bottom"].set_position(("axes", -0.09))

        self.az_ax.set_xlabel('Azimuth (°)', color='r')
        self.dip_ax.set_xlabel('Dip (°)', color='b')
        self.mag_ax.set_xlabel('Magnetic Field Strength (nT)', color='g')
        self.roll_ax.set_xlabel('Roll Angle (°)', color='k')

        tkw = dict(size=4, width=1.5)
        self.az_ax.tick_params(axis='x', colors='r', **tkw)
        self.dip_ax.tick_params(axis='x', colors='b', **tkw)
        self.dip_ax.tick_params(axis='y', which='major', right=True, direction='out')
        self.mag_ax.tick_params(axis='x', colors='g', **tkw)
        self.roll_ax.yaxis.set_label_position('right')
        self.roll_ax.yaxis.set_ticks_position('right')

        self.zp = ZoomPan()
        self.az_zoom = self.zp.zoom_factory(self.az_ax)
        self.az_pan = self.zp.pan_factory(self.az_ax)
        self.dip_zoom = self.zp.zoom_factory(self.dip_ax)
        self.dip_pan = self.zp.pan_factory(self.dip_ax)
        self.mag_zoom = self.zp.zoom_factory(self.mag_ax)
        self.mag_pan = self.zp.pan_factory(self.mag_ax)
        self.roll_zoom = self.zp.zoom_factory(self.roll_ax)
        self.roll_pan = self.zp.pan_factory(self.roll_ax)

        self.mag_dec_sbox.valueChanged.connect(self.redraw_az_line)

    def redraw_az_line(self):
        v = self.mag_dec_sbox.value()
        self.az_line.set_data(az + v, stations)
        self.canvas.draw()

    def open(self, pem_file):
        if not pem_file.is_borehole():
            print(f"{pem_file.filepath.name} is not a borehole file.")
            return
        elif not pem_file.has_d7() and not pem_file.has_geometry():
            print(f"{pem_file.filepath.name} does not have D7 RAD tool objects nor P tag geometry.")
            return
        # elif not 'X'in pem_file.data.Component.unique() or not 'Y'in pem_file.data.Component.unique():
        #     return

        self.pem_file = copy.deepcopy(pem_file)
        if not self.pem_file.is_averaged():
            self.pem_file = self.pem_file.average()
        self.plot_pem()
        self.show()

    def plot_pem(self):

        if self.pem_file.has_d7():
            self.df = pd.DataFrame({'Station': self.pem_file.data.Station,
                                    'RAD_tool': self.pem_file.data.RAD_tool,
                                    'RAD_ID': self.pem_file.data.RAD_ID})
            # Only keep unique RAD IDs
            self.df.drop_duplicates(subset='RAD_ID', inplace=True)

            global az, stations
            az = self.df.RAD_tool.map(lambda x: x.get_azimuth() + self.mag_dec_sbox.value())
            dip = self.df.RAD_tool.map(lambda x: x.get_dip())
            mag = self.df.RAD_tool.map(lambda x: x.get_mag_strength())
            acc_roll = self.df.RAD_tool.map(lambda x: x.get_acc_roll())
            mag_roll = self.df.RAD_tool.map(lambda x: x.get_mag_roll())
            stations = self.df.Station.astype(int)

            self.az_line, = self.az_ax.plot(az, stations, '-r',
                                            label='Tool Azimuth',
                                            lw=0.6,
                                            zorder=2)

            spline_stations = np.linspace(stations.iloc[0], stations.iloc[-1], 5)
            spline_az = np.interp(spline_stations, stations, az)

            # self.az_spline, = self.az_ax.plot(spline_az, spline_stations, '-m',
            #                                   label='Spline Azimuth',
            #                                   lw=0.6,
            #                                   zorder=2)

            self.az_spline = InteractiveSpline(self.az_ax, zip(spline_az, spline_stations),
                                               line_color='magenta')

            tool_mag, = self.mag_ax.plot(mag, stations, '-g',
                                         label='Total Magnetic Field',
                                         lw=0.6,
                                         alpha=0.4,
                                         zorder=1)
            tool_dip, = self.dip_ax.plot(dip, stations, '-b',
                                         label='Tool Dip',
                                         lw=0.6,
                                         zorder=1)

            acc_roll_plot, = self.roll_ax.plot(acc_roll, stations, '-b',
                                               label='Accelerometer',
                                               lw=0.6,
                                               zorder=1)

            mag_roll_plot, = self.roll_ax.plot(mag_roll, stations, '-r',
                                               label='Magnetometer',
                                               lw=0.6,
                                               zorder=1)

            az_lines = [self.az_line, tool_mag]
            dip_lines = [tool_dip]
            roll_lines = [acc_roll_plot, mag_roll_plot]
            self.az_ax.legend(az_lines, [l.get_label() for l in az_lines])
            self.dip_ax.legend(dip_lines, [l.get_label() for l in dip_lines])
            self.roll_ax.legend(roll_lines, [l.get_label() for l in roll_lines])


if __name__ == '__main__':
    from src.pem.pem_getter import PEMGetter
    app = QApplication(sys.argv)

    pg = PEMGetter()
    files = pg.get_pems(client='PEM Rotation', file='BR01.PEM')

    win = PEMGeometry()
    win.open(files[0])

    app.exec_()