import os
import sys
import copy
import time
# import matplotlib.backends.backend_tkagg  # Needed for pyinstaller, or receive  ImportError
import matplotlib.pyplot as plt
import numpy as np
import pyqtgraph as pg
from PyQt5 import uic
from PyQt5.QtWidgets import (QApplication, QWidget)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas, \
    NavigationToolbar2QT as NavigationToolbar
from matplotlib.transforms import Bbox
# from matplotlib.figure import Figure
from matplotlib.widgets import RectangleSelector

if getattr(sys, 'frozen', False):
    application_path = sys._MEIPASS
    plotEditorCreatorFile = 'qt_ui\\pem_plot_editor.ui'
else:
    application_path = os.path.dirname(os.path.abspath(__file__))
    plotEditorCreatorFile = os.path.join(os.path.dirname(application_path), 'qt_ui\\pem_plot_editor.ui')

# Load Qt ui file into a class
Ui_PlotEditorWindow, QtBaseClass = uic.loadUiType(plotEditorCreatorFile)


class PEMPlotEditor(QWidget, Ui_PlotEditorWindow):

    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.pem_file = None
        self.lines = []

        self.decay_plot = self.decay_view.addPlot(0, 0)

        # Configure the plots
        self.x_profile_view.ci.layout.setSpacing(10)  # Spacing between plots
        self.x_ax0 = self.x_profile_view.addPlot(0, 0)
        self.x_ax1 = self.x_profile_view.addPlot(1, 0)
        self.x_ax2 = self.x_profile_view.addPlot(2, 0)
        self.x_ax3 = self.x_profile_view.addPlot(3, 0)
        self.x_ax4 = self.x_profile_view.addPlot(4, 0)

        self.y_profile_view.ci.layout.setSpacing(10)  # Spacing between plots
        self.y_ax0 = self.y_profile_view.addPlot(0, 0)
        self.y_ax1 = self.y_profile_view.addPlot(1, 0)
        self.y_ax2 = self.y_profile_view.addPlot(2, 0)
        self.y_ax3 = self.y_profile_view.addPlot(3, 0)
        self.y_ax4 = self.y_profile_view.addPlot(4, 0)

        self.z_profile_view.ci.layout.setSpacing(10)  # Spacing between plots
        self.z_ax0 = self.z_profile_view.addPlot(0, 0)
        self.z_ax1 = self.z_profile_view.addPlot(1, 0)
        self.z_ax2 = self.z_profile_view.addPlot(2, 0)
        self.z_ax3 = self.z_profile_view.addPlot(3, 0)
        self.z_ax4 = self.z_profile_view.addPlot(4, 0)

        self.x_view_axes = [self.x_ax0, self.x_ax1, self.x_ax2, self.x_ax3, self.x_ax4]
        self.y_view_axes = [self.y_ax0, self.y_ax1, self.y_ax2, self.y_ax3, self.y_ax4]
        self.z_view_axes = [self.z_ax0, self.z_ax1, self.z_ax2, self.z_ax3, self.z_ax4]

        self.axes = np.concatenate([self.x_view_axes, self.y_view_axes, self.z_view_axes])

        for ax in self.axes[1:]:
            ax.setXLink(self.x_ax0)

        for ax in self.axes:
            ax.hideButtons()
            ax.getAxis('left').enableAutoSIPrefix(enable=False)
            # ax.getAxis('top').enableAutoSIPrefix(enable=False)

    def open(self, pem_file):
        self.pem_file = pem_file
        self.plot_profiles()

    def plot(self):
        # TODO Use this for spline
        roi = pg.PolyLineROI(zip(np.arange(100), np.random.normal(size=100)), pen=(5,9), closed=False, removable=True,
                             movable=False)
        p2 = self.decay_plot.addItem(roi)
        p3 = None

    def plot_profiles(self):
        """
        Plot the PEM file in a LIN plot style, with both components in separate plots
        """

        def clear_plots():
            pass
            # for ax in self.axes:
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

                line = ax.plot(x=interp_x, y=interp_y,
                               pen=pg.mkPen((54, 55, 55), width=1.),
                               clickable=True,
                               symbol='o')
                line.sigPointsClicked.connect(self.line_clicked)
                self.lines.append(line)

            def calc_channel_bounds():
                """
                Create tuples of start and end channels to be plotted per axes
                :return: list of tuples, first item of tuple is the axes, second is the start and end channel for that axes
                """
                channel_bounds = [None] * 4
                num_channels_per_plot = int((self.pem_file.number_of_channels - 1) // 4)
                remainder_channels = int((self.pem_file.number_of_channels - 1) % 4)

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
                    ax.setLabel('left', f"PP channel", units=self.pem_file.units)
                else:
                    ax.setLabel('left', f"Channel {bounds[0]} to {bounds[1]}", units=self.pem_file.units)

                # Plot the data
                for ch in range(bounds[0], bounds[1] + 1):
                    data = profile_data[filt].loc[:, ['Station', ch]]
                    plot_lines(data, ax, ch)

        clear_plots()

        # Get the profile data
        profile_data = self.pem_file.get_profile_data()
        if profile_data.empty:
            return

        t = time.time()
        plot_lin('X')
        plot_lin('Y')
        print(f"Time to make plots: {time.time() - t}")

    def line_clicked(self, item, points):
        print(f'Point clicked {points}')
        # for i, c in enumerate(self.lines):
        #     if c is curve:
        #         c.setPen('rgb'[i], width=3)
        #     else:
        #         c.setPen('rgb'[i], width=1)


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
    pem_files = pem_getter.get_pems(client='Raglan', number=5)

    editor = PEMPlotEditor()
    editor.open(pem_files[0])
    editor.show()

    app.exec_()