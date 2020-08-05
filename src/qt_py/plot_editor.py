import os
import sys
import copy
import time
# import matplotlib.backends.backend_tkagg  # Needed for pyinstaller, or receive  ImportError
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pyqtgraph as pg
from PyQt5 import uic, QtCore, QtGui
from PyQt5.QtWidgets import (QApplication, QWidget)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas, \
    NavigationToolbar2QT as NavigationToolbar
from matplotlib.transforms import Bbox
# from matplotlib.figure import Figure
from matplotlib.widgets import RectangleSelector
from src.pem.pem_file import StationConverter

if getattr(sys, 'frozen', False):
    application_path = sys._MEIPASS
    plotEditorCreatorFile = 'qt_ui\\pem_plot_editor.ui'
else:
    application_path = os.path.dirname(os.path.abspath(__file__))
    plotEditorCreatorFile = os.path.join(os.path.dirname(application_path), 'qt_ui\\pem_plot_editor.ui')

# Load Qt ui file into a class
Ui_PlotEditorWindow, QtBaseClass = uic.loadUiType(plotEditorCreatorFile)

pg.setConfigOptions(antialias=True)
pg.setConfigOption('background', 'w')
pg.setConfigOption('foreground', 'k')
pg.setConfigOption('crashWarning', True)


class PEMPlotEditor(QWidget, Ui_PlotEditorWindow):

    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.pem_file = None
        self.units = None
        self.stations = []

        self.selected_station = None
        self.selected_data = None
        self.selected_decay_line = None
        self.decay_lines = []
        self.plotted_decay_data = None

        # lr = pg.LinearRegionItem()
        # lr.hide()
        self.x_decay_plot = self.decay_layout.addPlot(0, 0)
        self.y_decay_plot = self.decay_layout.addPlot(1, 0)
        self.z_decay_plot = self.decay_layout.addPlot(2, 0)
        self.decay_layout.ci.layout.setSpacing(10)  # Spacing between plots
        self.decay_axes = [self.x_decay_plot, self.y_decay_plot, self.z_decay_plot]

        # Link the X axis of each axes
        for ax in self.decay_axes[1:]:
            ax.setXLink(self.x_decay_plot)

        for ax in self.decay_axes:
            ax.hideButtons()
            ax.getAxis('left').enableAutoSIPrefix(enable=False)

        # def drag(ev):
        #     global vb, lr
        #     if (ev.button() == QtCore.Qt.LeftButton) and (ev.modifiers() & QtCore.Qt.ControlModifier):
        #         lr.show()
        #         lr.setRegion([self.x_decay_plot.vb.mapToView(ev.buttonDownPos()).x(),
        #         self.x_decay_plot.vb.mapToView(ev.pos()).x()])
        #         ev.accept()
        #     else:
        #         pg.ViewBox.mouseDragEvent(self.x_decay_plot.vb, ev)
        # 
        # self.x_decay_plot.vb.mouseDragEvent = drag

        # Configure the plots
        self.x_profile_layout.ci.layout.setSpacing(10)  # Spacing between plots
        self.x_ax0 = self.x_profile_layout.addPlot(0, 0)
        self.x_ax1 = self.x_profile_layout.addPlot(1, 0)
        self.x_ax2 = self.x_profile_layout.addPlot(2, 0)
        self.x_ax3 = self.x_profile_layout.addPlot(3, 0)
        self.x_ax4 = self.x_profile_layout.addPlot(4, 0)

        self.y_profile_layout.ci.layout.setSpacing(10)  # Spacing between plots
        self.y_ax0 = self.y_profile_layout.addPlot(0, 0)
        self.y_ax1 = self.y_profile_layout.addPlot(1, 0)
        self.y_ax2 = self.y_profile_layout.addPlot(2, 0)
        self.y_ax3 = self.y_profile_layout.addPlot(3, 0)
        self.y_ax4 = self.y_profile_layout.addPlot(4, 0)

        self.z_profile_layout.ci.layout.setSpacing(10)  # Spacing between plots
        self.z_ax0 = self.z_profile_layout.addPlot(0, 0)
        self.z_ax1 = self.z_profile_layout.addPlot(1, 0)
        self.z_ax2 = self.z_profile_layout.addPlot(2, 0)
        self.z_ax3 = self.z_profile_layout.addPlot(3, 0)
        self.z_ax4 = self.z_profile_layout.addPlot(4, 0)

        self.x_view_axes = [self.x_ax0, self.x_ax1, self.x_ax2, self.x_ax3, self.x_ax4]
        self.y_view_axes = [self.y_ax0, self.y_ax1, self.y_ax2, self.y_ax3, self.y_ax4]
        self.z_view_axes = [self.z_ax0, self.z_ax1, self.z_ax2, self.z_ax3, self.z_ax4]

        self.profile_axes = np.concatenate([self.x_view_axes, self.y_view_axes, self.z_view_axes])

        # Link the X axis of each axes
        for ax in self.profile_axes[1:]:
            ax.setXLink(self.x_ax0)

        # Configure each axes
        for ax in self.profile_axes:
            ax.hideButtons()
            ax.getAxis('left').enableAutoSIPrefix(enable=False)

            # Add the vertical selection line
            hover_v_line = pg.InfiniteLine(angle=90, movable=False)
            hover_v_line.setPen((102, 178, 255, 100), width=2.)
            selected_v_line = pg.InfiniteLine(angle=90, movable=False)
            selected_v_line.setPen((51, 51, 255, 100), width=2.)
            ax.addItem(hover_v_line, ignoreBounds=True)
            ax.addItem(selected_v_line, ignoreBounds=True)

            # Connect the mouse moved signal
            ax.scene().sigMouseMoved.connect(self.profile_mouse_moved)
            ax.scene().sigMouseClicked.connect(self.profile_plot_clicked)

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Delete:
            if self.selected_decay_line:
                self.decay_lines[self.selected_decay_line].setPen('r')

    def open(self, pem_file):
        self.pem_file = copy.deepcopy(pem_file)
        self.stations = self.pem_file.get_stations(converted=True)

        # Convert the stations in the data
        converter = StationConverter()
        self.pem_file.data.Station = self.pem_file.data.Station.map(converter.convert_station)

        # Set the units of the decay plots
        self.units = self.pem_file.units
        for ax in self.decay_axes:
            ax.setLabel('left', f"Response", units=self.units)

        # Plot the LIN profiles
        self.plot_profiles()
        self.show()

    def plot_profiles(self):
        """
        Plot the PEM file in a LIN plot style, with both components in separate plots
        """

        def clear_plots():
            pass
            # for ax in self.profile_axes:
            #     if ax not in [self.pp_ax, self.rot_ax]:
            #         ax.clear()

        def plot_lin(component):

            def plot_lines(df, ax, channel):
                """
                Plot the lines on the pyqtgraph ax for a given channel
                :param df: DataFrame of filtered data
                :param ax: pyqtgraph PlotItem
                :param channel: int, channel to plot
                """
                x, y = df['Station'], df[channel]
                interp_x = np.linspace(x.min(), x.max() + 1, num=1000)
                interp_y = np.interp(interp_x, x, y)

                profile_line = pg.PlotCurveItem(x=interp_x, y=interp_y,
                                                pen=pg.mkPen('k', width=1.),
                                                # clickable=True,
                                                )
                # profile_line.sigClicked.connect(self.profile_line_clicked)
                ax.addItem(profile_line)
                # self.profile_lines.append(profile_line)

            def calc_channel_bounds():
                """
                Create tuples of start and end channels to be plotted per axes
                :return: list of tuples, first item of tuple is the axes, second is the start and end channel for that axes
                """
                channel_bounds = [None] * 4
                num_channels_per_plot = int((file.number_of_channels - 1) // 4)
                remainder_channels = int((file.number_of_channels - 1) % 4)

                for k in range(0, len(channel_bounds)):
                    channel_bounds[k] = (k * num_channels_per_plot + 1, num_channels_per_plot * (k + 1))

                for i in range(0, remainder_channels):
                    channel_bounds[i] = (channel_bounds[i][0], (channel_bounds[i][1] + 1))
                    for k in range(i + 1, len(channel_bounds)):
                        channel_bounds[k] = (channel_bounds[k][0] + 1, channel_bounds[k][1] + 1)

                channel_bounds.insert(0, (0, 0))
                return channel_bounds

            filt = profile_data['Component'] == component.upper()
            channel_bounds = calc_channel_bounds()
            for i, bounds in enumerate(channel_bounds):
                # Select the correct axes based on the component
                if component == 'X':
                    ax = self.x_view_axes[i]
                else:
                    ax = self.y_view_axes[i]

                # Set the Y-axis labels
                if i == 0:
                    ax.setLabel('left', f"PP channel", units=self.units)
                else:
                    ax.setLabel('left', f"Channel {bounds[0]} to {bounds[1]}", units=self.units)

                # Plot the data
                for ch in range(bounds[0], bounds[1] + 1):
                    data = profile_data[filt].loc[:, ['Station', ch]]
                    plot_lines(data, ax, ch)

        clear_plots()
        global file
        file = copy.deepcopy(self.pem_file)

        if not file.is_averaged():
            file = file.average()

        if not file.is_split():
            file = file.split()

        profile_data = file.get_profile_data()
        if profile_data.empty:
            return

        t = time.time()
        for component in file.get_components():
            plot_lin(component)
        print(f"Time to make plots: {time.time() - t}")

    def select_station(self, station):

        def plot_decay(row):
            if row.Component == 'X':
                ax = self.x_decay_plot
            elif row.Component == 'Y':
                ax = self.y_decay_plot
            else:
                ax = self.z_decay_plot

            decay_line = pg.PlotCurveItem(y=row.Reading,
                                          pen=pg.mkPen('k', width=1.),
                                          )
            decay_line.setClickable(True, width=3)
            decay_line.sigClicked.connect(self.decay_line_clicked)

            ax.addItem(decay_line)
            self.decay_lines.append(decay_line)

        # Move the selected vertical line
        for ax in self.profile_axes:
            selected_v_line = ax.items[1]
            selected_v_line.setPos(station)

        # Clear the plots
        for ax in self.decay_axes:
            ax.clear()
        self.decay_lines = []

        # Filter the data
        filt = self.pem_file.data['Station'] == station
        self.plotted_decay_data = self.pem_file.data[filt]

        # Plot the decays
        self.plotted_decay_data.apply(plot_decay, axis=1)

    def profile_mouse_moved(self, evt):
        """
        Signal slot, when the mouse is moved in one of the axes. Calculates and plots a light blue vertical line at the
        nearest station where the mouse is.
        :param evt: pyqtgraph MouseClickEvent
        """
        def find_nearest_station(x):
            """
            Calculate the nearest station from the position x
            :param x: int, mouse x location
            :return: int, station number
            """
            idx = (np.abs(self.stations - x)).argmin()
            return self.stations[idx]

        global nearest_station
        pos = evt
        mouse_point = self.x_ax0.vb.mapSceneToView(pos)
        nearest_station = find_nearest_station(int(mouse_point.x()))

        for ax in self.profile_axes:
            ax.items[0].setPos(nearest_station)

    def profile_plot_clicked(self, evt):
        """
        Signal slot, when the profile plot is clicked. Plots a darker blue vertical line at the nearest station where
        the click was made and plots that station's decays in the decay plot.
        Uses the nearest station calculated in self.profile_mouse_moved.
        :param evt: pyqtgraph MouseClickEvent (not used)
        """
        self.select_station(nearest_station)

    def decay_line_clicked(self, item):
        curve = item
        self.selected_data = self.plotted_decay_data.iloc[self.decay_lines.index(curve)]
        self.selected_decay_line = self.decay_lines.index(curve)
        print(f"Line {self.selected_decay_line} selected")
        for i, c in enumerate(self.decay_lines):
            if c is curve:
                c.setPen('b', width=2)
                c.setShadowPen(pg.mkPen('w', width=6, cosmetic=True))
            else:
                c.setPen('k', width=1)
                c.setShadowPen(None)


# class PEMPlotEditor(QWidget, Ui_PlotEditorWindow):
#
#     def __init__(self, pem_file):
#         super().__init__()
#         self.setupUi(self)
#         self.pem_file = pem_file
#         self.decay_cleaner = PEMDecayCleaner(self.pem_file)
#         # self.canvas = FigureCanvas(self.decay_cleaner.fig)
#         self.toolbar = NavigationToolbar(self.decay_cleaner.canvas, self)
#         self.toolbar_layout.addWidget(self.toolbar)
#         self.toolbar.setFixedHeight(30)
#         self.decay_layout.addWidget(self.decay_cleaner.canvas)
#     # def plot(self):
#     #     roi = pg.PolyLineROI(zip(np.arange(100), np.random.normal(size=100)), pen=(5,9), closed=False, removable=True,
#     #                          movable=False)
#     #     p2 = self.win.addItem(roi)
#     #     p3 = None
#
#
# class PEMDecayCleaner:
#
#     def __init__(self, pem_file):#, component, station):
#         self.pem_file = pem_file
#         # self.
#         self.selected_line_color = 'magenta'
#         self.x = np.linspace(0, 10, 100)
#
#         self.fig, self.ax = plt.subplots()
#         self.canvas = FigureCanvas(self.fig)
#         self.lines = []
#
#         for i in range(1, 10):
#             self.lines.append(self.ax.plot(self.x, i * self.x + self.x, picker=5, color='dimgray', alpha=0.75))
#         self.lines = [line[0] for line in self.lines]  # Because appending ax.plot appends a list
#
#         rectprops = dict(facecolor='magenta', edgecolor='black',
#                          alpha=0.2, fill=True)
#         self.rs = RectangleSelector(self.ax, self.on_rect_select,
#                                     drawtype='box', useblit=False,
#                                     button=[1],  # don't use middle button or right-click
#                                     minspanx=5, minspany=5,
#                                     spancoords='pixels',
#                                     interactive=False,
#                                     rectprops=rectprops)
#
#         self.fig.canvas.callbacks.connect('pick_event', self.on_pick)
#         self.fig.canvas.callbacks.connect('button_press_event', self.on_btn_press)
#         self.fig.canvas.callbacks.connect('key_press_event', self.on_key_press)
#         # plt.show()
#
#     # def plot_decay(self, component, station):
#     def get_plot(self):
#         return self.fig
#
#     def select_line(self, line):
#         line._color = self.selected_line_color
#         line._alpha = 1.
#         # self.selected_lines.append(line)
#         print(f"Selected line {self.lines.index(line)}")
#         self.fig.canvas.draw()
#
#     def deselect_line(self, line):
#         line._color = 'dimgray'
#         line._alpha = 0.75
#         # self.selected_lines.remove(line)
#         print(f"De-selected line {self.lines.index(line)}")
#         self.fig.canvas.draw()
#
#     def delete_line(self, line):
#         """
#         Delete a line
#         :param line: Line2D object
#         :return: None
#         """
#         # line.remove()  # Remvoes the line from the plot, but not from the list
#         # self.selected_lines.remove(line)  # Removes the object from the selected lines list
#         # self.lines.remove(line)  # Removes the object from the selected lines list
#
#         def is_deleted():
#             if line._color == 'red':
#                 return True
#             else:
#                 return False
#
#         if is_deleted():
#             line._color = self.selected_line_color
#             line._alpha = 1
#         else:
#             line._color = 'red'
#             line._alpha = 0.5
#
#         self.fig.canvas.draw()
#
#     def on_rect_select(self, eclick, erelease):
#         """
#         What happens when a rectangle is drawn
#         :param eclick: event mouse click
#         :param erelease: event mouse click release
#         :return: None
#         """
#         x1, y1 = eclick.xdata, eclick.ydata
#         x2, y2 = erelease.xdata, erelease.ydata
#         bbox = Bbox.from_bounds(x1, y1, x2-x1, y2-y1)
#
#         # Reset all lines
#         for line in self.lines:
#             self.deselect_line(line)
#         self.fig.canvas.draw()
#
#         for line in self.lines:
#             if line._path.intersects_bbox(bbox):
#                 self.select_line(line)
#
#     def on_pick(self, event):
#         # When a plotted line is clicked
#
#         def is_selected(line):
#             if line._color == self.selected_line_color:
#                 return True
#             else:
#                 return False
#
#         line = event.artist
#         index = self.lines.index(line)
#
#         if is_selected(line):
#             self.deselect_line(line)
#         else:
#             self.select_line(line)
#
#     def on_key_press(self, event):
#         # What happens when a key is pressed
#         if event.key == 'delete':
#             if self.selected_lines:
#                 for line in reversed(self.selected_lines):
#                     self.delete_line(line)
#                 # self.fig.canvas.draw()
#
#     def on_btn_press(self, event):
#         if not event.inaxes:
#             for line in self.lines:
#                 self.deselect_line(line)


if __name__ == '__main__':
    from src.pem.pem_getter import PEMGetter

    app = QApplication(sys.argv)
    pem_getter = PEMGetter()
    pem_files = pem_getter.get_pems(client='PEM Splitting', number=1)

    editor = PEMPlotEditor()
    editor.open(pem_files[0])

    app.exec_()