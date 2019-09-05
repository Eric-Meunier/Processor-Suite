import os
import sys
import logging
import numpy as np
import math
import matplotlib as mpl
from scipy import interpolate
from scipy import stats
import matplotlib.ticker as ticker
from matplotlib import patches
from itertools import chain
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
from PyQt5 import (QtCore, QtGui, uic)
from PyQt5.QtWidgets import (QMainWindow, QAction, QApplication, QGridLayout, QFileDialog, QDesktopWidget,
                             QTableWidgetItem, QHeaderView, QAbstractScrollArea, QMessageBox)

__version__ = '0.0.0'
logging.info('PEMPlotter')

if getattr(sys, 'frozen', False):
    # If the application is run as a bundle, the pyInstaller bootloader
    # extends the sys module by a flag frozen=True and sets the app
    # path into variable _MEIPASS'.
    application_path = sys._MEIPASS
else:
    application_path = os.path.dirname(os.path.abspath(__file__))


mpl.rcParams['path.simplify'] = True
mpl.rcParams['path.simplify_threshold'] = 1.0
mpl.rcParams['agg.path.chunksize'] = 10000
mpl.rcParams["figure.autolayout"] = False
mpl.rcParams['lines.linewidth'] = 0.5
mpl.rcParams['lines.color'] = '#1B2631'
mpl.rcParams['font.size'] = 9
mpl.rcParams['font.sans-serif'] = 'Tahoma'


# class MainWindow(QMainWindow):
#     def __init__(self):
#         super().__init__()
#         self.initUi()
#
#     def initUi(self):
#         def center_window(self):
#             qtRectangle = self.frameGeometry()
#             centerPoint = QDesktopWidget().availableGeometry().center()
#             qtRectangle.moveCenter(centerPoint)
#             self.move(qtRectangle.topLeft())
#             self.show()
#
#         self.dialog = QtGui.QFileDialog()
#         self.statusBar().showMessage('Ready')
#         self.setWindowTitle("Damping Box Current Plot  v"+str(__version__))
#         self.setWindowIcon(
#             QtGui.QIcon(os.path.join(application_path, "crone_logo.ico")))
#         # TODO Program where the window opens
#         self.setGeometry(500, 300, 800, 600)
#         self.center_window()

class PEMPlotter:
    """
    Class for creating Crone LIN figure
    """

    def __init__(self, pem_file, parent=None, x_limit = None):
        super().__init__()
        self.parent = parent
        self.pem_file = pem_file
        self.data = self.pem_file.data
        self.header = self.pem_file.header
        self.stations = self.pem_file.get_converted_unique_stations()
        self.survey_type = self.pem_file.get_survey_type()
        if x_limit is None:
            self.x_limit = (str(min(chain(self.stations))), str(max(chain(self.stations))))
        else:
            self.x_limit = x_limit
        self.num_channels = int(self.header['NumChannels']) + 1
        self.units = 'nT/s' if self.pem_file.tags['Units'].casefold() == 'nanotesla/sec' else 'pT'
        self.line_colour = '#1B2631'
        self.lin_fig = None
        self.log_fig = None

    def format_figure(self, figure):
        """
        Formats a figure, mainly the spines, adjusting the padding, and adding the rectangle.
        :param figure: LIN or LOG figure object
        """
        axes = figure.axes

        def format_spines(ax):
            ax.spines['right'].set_visible(False)
            ax.spines['top'].set_visible(False)

            if ax != axes[-1]:
                ax.spines['bottom'].set_position(('data', 0))
                ax.tick_params(axis='x', which='major', direction='inout', length=4)
                plt.setp(ax.get_xticklabels(), visible=False)
            else:
                ax.spines['bottom'].set_visible(False)
                ax.xaxis.set_ticks_position('bottom')
                ax.tick_params(axis='x', which='major', direction='out', length=6)
                plt.setp(ax.get_xticklabels(), visible=True, size=12)

        plt.subplots_adjust(left=0.135, bottom=0.07, right=0.958, top=0.885)
        self.add_rectangle()

        for ax in axes:
            format_spines(ax)

    def format_xaxis(self, figure):
        """
        Formats the X axis of a figure
        :param figure: LIN or LOG figure objects
        """
        x_label_locator = ticker.AutoLocator()
        major_locator = ticker.FixedLocator(self.stations)
        plt.xlim(self.x_limit)
        figure.axes[0].xaxis.set_major_locator(major_locator)  # for some reason this seems to apply to all axes
        figure.axes[-1].xaxis.set_major_locator(x_label_locator)

    def create_lin_figure(self):
        """
        Creates the blank LIN figure
        """
        lin_fig, (ax1, ax2, ax3, ax4, ax5) = plt.subplots(5, 1, figsize=(8.5, 11), sharex=True)
        ax6 = ax5.twiny()
        ax6.get_shared_x_axes().join(ax5, ax6)

        self.lin_fig = lin_fig
        self.format_figure(self.lin_fig)

    def plot_lin_fig(self):
        """
        Plots the data into the LIN figure
        """

        def calc_channel_bounds():
            # channel_bounds is a list of tuples showing the inclusive bounds of each data plot
            channel_bounds = [None] * 4
            num_channels_per_plot = int((self.num_channels - 1) // 4)
            remainder_channels = int((self.num_channels - 1) % 4)

            for k in range(0, len(channel_bounds)):
                channel_bounds[k] = (k * num_channels_per_plot + 1, num_channels_per_plot * (k + 1))

            for i in range(0, remainder_channels):
                channel_bounds[i] = (channel_bounds[i][0], (channel_bounds[i][1] + 1))
                for k in range(i + 1, len(channel_bounds)):
                    channel_bounds[k] = (channel_bounds[k][0] + 1, channel_bounds[k][1] + 1)

            channel_bounds.insert(0, (0, 0))
            return channel_bounds

        def add_ylabels():
            for i in range(len(self.lin_fig.axes) - 1):
                ax = self.lin_fig.axes[i]
                if i == 0:
                    ax.set_ylabel('Primary Pulse' + "\n(" + self.units + ")")
                else:
                    ax.set_ylabel("Channel " + str(channel_bounds[i][0]) + " - " +
                                  str(channel_bounds[i][1]) + "\n(" + self.units + ")")

        if not self.lin_fig:
            self.create_lin_figure()

        channel_bounds = calc_channel_bounds()

        profile_data = self.pem_file.get_profile_data(self.data)

        for i, group in enumerate(channel_bounds):
            ax = self.lin_fig.axes[i]
            self.draw_lines(ax, group[0], group[1])

        self.add_title()
        add_ylabels()
        self.format_yaxis(self.lin_fig)
        self.format_xaxis(self.lin_fig)

        return self.lin_fig

    def create_log_figure(self):
        """
        Creates an empty but formatted LOG figure
        """
        log_fig, ax = plt.subplots(1, 1, figsize=(8.5, 11))
        ax2 = ax.twiny()
        ax2.get_shared_x_axes().join(ax, ax2)
        plt.yscale('symlog', linthreshy=10, linscaley=1. / math.log(10), subsy=list(np.arange(2, 10, 1)))

        self.log_fig = log_fig
        self.format_figure(self.log_fig)

    def plot_log_fig(self):
        """
        Plots the data into the LOG figure
        :return:
        """

        def add_ylabel():
            ax = self.log_fig.axes[0]
            ax.set_ylabel('Primary Pulse to Channel ' + str(self.num_channels - 1) + "\n(" + self.units + ")")

        if not self.log_fig:
            self.create_log_figure()

        ax = self.log_fig.axes[0]

        self.draw_lines(ax, 0, self.num_channels - 1)
        self.add_title()
        add_ylabel()
        self.format_yaxis(self.log_fig)
        self.format_xaxis(self.log_fig)

        return self.log_fig

    def draw_lines(self, ax, channel_low, channel_high):
        """
        Plots the lines into an axes of a figure
        :param ax: Axes of a figure, either LIN or LOG figure objects
        :param channel_low: The first channel to be plotted
        :param channel_high: The last channel to be plotted
        """
        segments = 1000  # The data will be broken in this number of segments
        offset = segments * 0.1  # Used for spacing the annotations

        for k in range(channel_low, (channel_high + 1)):
            # Gets the profile data for a single channel, along with the stations
            channel_data, stations = self.editor.get_channel_data(k, self.profile_data)

            # Interpolates the channel data, also returns the corresponding x intervals
            interp_data, x_intervals = self.editor.get_interp_data(self.kwargs['SurveyType'], channel_data, stations,
                                                                   segments,
                                                                   self.kwargs['HideGaps'], self.kwargs['Gap'],
                                                                   self.kwargs['Interp'])

            ax.plot(x_intervals, interp_data, color=self.line_colour)

            # Mask is used to hide data within gaps
            mask = np.isclose(interp_data, interp_data.astype('float64'))
            x_intervals = x_intervals[mask]
            interp_data = interp_data[mask]

            # Annotating the lines
            for i, x_position in enumerate(x_intervals[int(offset)::int(len(x_intervals) * 0.4)]):
                y = interp_data[list(x_intervals).index(x_position)]

                if k == 0:
                    ax.annotate('PP', xy=(x_position, y), xycoords="data", size=7.5, color=self.line_colour,
                                va='center_baseline', ha='center')

                else:
                    ax.annotate(str(k), xy=(x_position, y), xycoords="data", size=7.5, color=self.line_colour,
                                va='center_baseline', ha='center')

            offset += len(x_intervals) * 0.15

            if offset >= len(x_intervals) * 0.85:
                offset = len(x_intervals) * 0.10

    def format_yaxis(self, figure):
        """
        Formats the Y axis of a figure
        :param figure: LIN or LOG figure object
        """
        axes = figure.axes

        for ax in axes:
            ax.get_yaxis().set_label_coords(-0.08, 0.5)

            if ax.get_yscale() != 'symlog':
                y_limits = ax.get_ylim()

                if (y_limits[1] - y_limits[0]) < 3:
                    new_high = math.ceil(((y_limits[1] - y_limits[0]) / 2) + 1)
                    new_low = new_high * -1
                    ax.set_ylim(new_low, new_high)
                    ax.set_yticks(ax.get_yticks())

                elif ax != axes[-1]:
                    new_high = math.ceil(max(y_limits[1], 0))
                    new_low = math.floor(min(y_limits[0], 0))
                    ax.set_ylim(new_low, new_high)
                    ax.set_yticks(ax.get_yticks())

            elif ax.get_yscale() == 'symlog':
                y_limits = ax.get_ylim()
                new_high = 10.0 ** math.ceil(math.log(max(y_limits[1], 11), 10))
                new_low = -1 * 10.0 ** math.ceil(math.log(max(abs(y_limits[0]), 11), 10))
                ax.set_ylim(new_low, new_high)

                ax.tick_params(axis='y', which='major', labelrotation=90)
                plt.setp(ax.get_yticklabels(), va='center')

            ax.yaxis.set_major_formatter(ticker.FormatStrFormatter('%d'))

    def add_title(self):
        """
        Adds the title header to a figure
        """

        timebase_freq = ((1 / (float(self.header['Timebase']) / 1000)) / 4)

        if 'borehole' in self.survey_type.casefold():
            s_title = 'Hole'
        else:
            s_title = 'Line'

        plt.figtext(0.550, 0.960, 'Crone Geophysics & Exploration Ltd.',
                    fontname='Century Gothic', fontsize=11, ha='center')

        plt.figtext(0.550, 0.945, self.survey_type + ' Pulse EM Survey', family='cursive', style='italic',
                    fontname='Century Gothic', fontsize=10, ha='center')

        plt.figtext(0.145, 0.935, 'Timebase: ' + str(self.header['Timebase']) + ' ms\n' +
                    'Base Frequency: ' + str(round(timebase_freq, 2)) + ' Hz\n' +
                    'Current: ' + str(round(float(self.kwargs['Current']), 1)) + ' A',
                    fontname='Century Gothic', fontsize=10, va='top')

        plt.figtext(0.550, 0.935, s_title + ': ' + self.header['LineHole'] + '\n'
                    + self.component + ' Component' + '\n'
                    + 'Loop: ' + self.kwargs['Loop'],
                    fontname='Century Gothic', fontsize=10, va='top', ha='center')

        plt.figtext(0.955, 0.935,
                    self.kwargs['Client'] + '\n' + self.kwargs['Grid'] + '\n' + self.header['Date'] + '\n',
                    fontname='Century Gothic', fontsize=10, va='top', ha='right')

    def add_rectangle(self):
        """
        Draws a rectangle around a figure object
        """
        fig = plt.gcf()
        rect = patches.Rectangle(xy=(0.02, 0.02), width=0.96, height=0.96, linewidth=0.7, edgecolor='black',
                                 facecolor='none', transform=fig.transFigure)
        fig.patches.append(rect)


# class CronePYQTFigure:
#     """
#     Class creating graphs using pyqtgraph.
#     # TODO Straight to Widget or make figures?
#     # TODO Only needs data, should the class do the rest of the work?
#     """


if __name__ == "__main__":
    # app = QtGui.QApplication(sys.argv)
    # mw = MainWindow()
    # app.exec_()

    # cProfile.run('editor.make_plots()', sort='cumtime')
    testing_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), "../../sample_files/9600NAv LP-100.PEM")
    plots = CronePYQTFigure()
    plots.plot(testing_file)
    # plt.show()
