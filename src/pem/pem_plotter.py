import logging
import math
import os
import re
import sys
from itertools import chain
import matplotlib.backends.backend_tkagg  # Needed for pyinstaller, or receive  ImportError
import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
from PyQt5.QtWidgets import (QProgressBar)
from matplotlib import patches
from matplotlib.backends.backend_pdf import PdfPages
from scipy import interpolate
from scipy import stats

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
# mpl.rcParams['lines.color'] = '#1B2631'
mpl.rcParams['font.size'] = 9
# mpl.rcParams['font.sans-serif'] = 'Tahoma'


class PEMPlotter:
    """
    Class for creating Crone LIN and LOG figures.
    PEMFile must be averaged and split.
    """

    def __init__(self, pem_file, **kwargs):#hide_gaps=True, gap=None, x_min=None, x_max=None):
        super().__init__()
        self.pem_file = pem_file
        self.hide_gaps = kwargs.get('HideGaps')
        self.gap = kwargs.get('Gap')
        self.data = self.pem_file.data
        self.header = self.pem_file.header
        self.stations = self.pem_file.get_converted_unique_stations()
        self.survey_type = self.pem_file.get_survey_type()
        self.x_min = int(min(chain(self.stations))) if kwargs.get('XMin') is None else kwargs.get('XMin')
        self.x_max = int(max(chain(self.stations))) if kwargs.get('XMax') is None else kwargs.get('XMax')
        self.num_channels = int(self.header['NumChannels']) + 1
        self.units = 'nT/s' if self.pem_file.tags['Units'].casefold() == 'nanotesla/sec' else 'pT'
        self.channel_bounds = self.calc_channel_bounds()
        self.line_colour = 'k'
        # self.line_colour = 'red'

    def calc_channel_bounds(self):
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
                plt.setp(ax.get_xticklabels(), visible=True, size=12,  fontname='Century Gothic')

        plt.subplots_adjust(left=0.135, bottom=0.07, right=0.958, top=0.885)
        self.add_rectangle(figure)

        for ax in axes:
            format_spines(ax)

    def format_xaxis(self, figure):
        """
        Formats the X axis of a figure
        :param figure: LIN or LOG figure objects
        """
        x_label_locator = ticker.AutoLocator()
        major_locator = ticker.FixedLocator(sorted(self.stations))
        plt.xlim(self.x_min, self.x_max)
        figure.axes[0].xaxis.set_major_locator(major_locator)  # for some reason this seems to apply to all axes
        figure.axes[-1].xaxis.set_major_locator(x_label_locator)

    def make_lin_fig(self, component, lin_fig):
        """
        Plots the data into the LIN figure
        :return: Matplotlib Figure object
        """
        def add_ylabels():
            for i in range(len(lin_fig.axes) - 1):
                ax = lin_fig.axes[i]
                if i == 0:
                    ax.set_ylabel('Primary Pulse' + "\n(" + self.units + ")")
                else:
                    ax.set_ylabel("Channel " + str(channel_bounds[i][0]) + " - " +
                                  str(channel_bounds[i][1]) + "\n(" + self.units + ")")

        self.format_figure(lin_fig)
        channel_bounds = self.channel_bounds

        for i, group in enumerate(channel_bounds):
            ax = lin_fig.axes[i]
            self.draw_lines(ax, group[0], group[1], component)

        self.add_title(component)
        add_ylabels()
        self.format_yaxis(lin_fig)
        self.format_xaxis(lin_fig)
        return lin_fig

    def make_log_fig(self, component, log_fig):
        """
        Plots the data into the LOG figure
        :return: Matplotlib Figure object
        """

        def add_ylabel():
            ax = log_fig.axes[0]
            ax.set_ylabel('Primary Pulse to Channel ' + str(self.num_channels - 1) + "\n(" + self.units + ")")

        self.format_figure(log_fig)
        ax = log_fig.axes[0]

        self.draw_lines(ax, 0, self.num_channels - 1, component)
        self.add_title(component)
        add_ylabel()
        self.format_yaxis(log_fig)
        self.format_xaxis(log_fig)
        return log_fig

    def convert_station(self, station):
        """
        Converts a single station name into a number, negative if the stations was S or W
        :return: Integer station number
        """
        if re.match(r"\d+(S|W)", station):
            station = (-int(re.sub(r"\D", "", station)))

        else:
            station = (int(re.sub(r"\D", "", station)))

        return station

    def get_profile_data(self, component):
        """
        Transforms the data so it is ready to be plotted for LIN and LOG plots
        :param component: A single component (i.e. Z, X, or Y)
        :return: Dictionary where each key is a channel, and the values of those keys are a list of
        dictionaries which contain the stations and readings of all readings of that channel
        """
        profile_data = {}
        component_data = list(filter(lambda d: d['Component'] == component, self.data))
        num_channels = len(component_data[0]['Data'])
        for channel in range(0, num_channels):
            channel_data = []

            for i, station in enumerate(component_data):
                reading = station['Data'][channel]
                station_number = int(self.convert_station(station['Station']))
                channel_data.append({'Station': station_number, 'Reading': reading})

            profile_data[channel] = channel_data

        return profile_data

    def get_channel_data(self, channel, profile_data):
        """
        Get the profile-mode data for a given channel
        :param channel: int, channel number
        :param profile_data: dict, data in profile-mode
        :return: data in list form and corresponding stations as a list
        """
        data = []
        stations = []

        for station in profile_data[channel]:
            data.append(station['Reading'])
            stations.append(station['Station'])

        return data, stations

    def draw_lines(self, ax, channel_low, channel_high, component):
        """
        Plots the lines into an axes of a figure
        :param ax: Axes of a figure, either LIN or LOG figure objects
        :param channel_low: The first channel to be plotted
        :param channel_high: The last channel to be plotted
        :param component: String letter representing the component to plot (X, Y, or Z)
        """

        def calc_gaps(stations):
            survey_type = self.survey_type

            if 'borehole' in survey_type.casefold():
                min_gap = 50
            elif 'surface' in survey_type.casefold():
                min_gap = 200
            station_gaps = np.diff(stations)

            if self.gap is None:
                self.gap = max(int(stats.mode(station_gaps)[0] * 2), min_gap)

            gap_intervals = [(stations[i], stations[i + 1]) for i in range(len(stations) - 1) if
                             station_gaps[i] > self.gap]

            return gap_intervals

        def get_interp_data(profile_data, stations, interp_method='linear'):
            """
            Interpolates the data using 1-D piecewise linear interpolation. The data is segmented
            into 100 segments.
            :param profile_data: The EM data in profile mode
            :param segments: Number of segments to interpolate
            :param hide_gaps: Bool: Whether or not to hide gaps
            :param gap: The minimum length threshold above which is considered a gap
            :return: The interpolated data and stations
            """
            stations = np.array(stations, dtype='float64')
            readings = np.array(profile_data, dtype='float64')
            x_intervals = np.linspace(stations[0], stations[-1], segments)
            f = interpolate.interp1d(stations, readings, kind=interp_method)

            interpolated_y = f(x_intervals)

            if self.hide_gaps:
                gap_intervals = calc_gaps(stations)

                # Masks the intervals that are between gap[0] and gap[1]
                for gap in gap_intervals:
                    interpolated_y = np.ma.masked_where((x_intervals > gap[0]) & (x_intervals < gap[1]),
                                                        interpolated_y)

            return interpolated_y, x_intervals

        segments = 1000  # The data will be broken in this number of segments
        offset = segments * 0.1  # Used for spacing the annotations
        profile_channel_data = self.get_profile_data(component)

        for k in range(channel_low, (channel_high + 1)):
            # Gets the profile data for a single channel, along with the stations
            channel_data, stations = self.get_channel_data(k, profile_channel_data)

            # Interpolates the channel data, also returns the corresponding x intervals
            interp_data, x_intervals = get_interp_data(channel_data, stations)

            ax.plot(x_intervals, interp_data, color=self.line_colour)

            # Mask is used to hide data within gaps
            mask = np.isclose(interp_data, interp_data.astype('float64'))
            x_intervals = x_intervals[mask]
            interp_data = interp_data[mask]

            # Annotating the lines
            for i, x_position in enumerate(x_intervals[int(offset)::int(len(x_intervals) * 0.4)]):
                y = interp_data[list(x_intervals).index(x_position)]

                if k == 0:
                    ax.annotate('PP', xy=(x_position, y), xycoords="data", size=7.5, va='center_baseline', ha='center',
                                color=self.line_colour)

                else:
                    ax.annotate(str(k), xy=(x_position, y), xycoords="data", size=7.5, va='center_baseline', ha='center',
                                color=self.line_colour)

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

    def add_title(self, component):
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
                    'Current: ' + str(round(float(self.pem_file.tags.get('Current')), 1)) + ' A',
                    fontname='Century Gothic', fontsize=10, va='top')

        plt.figtext(0.550, 0.935, s_title + ': ' + self.header.get('LineHole') + '\n' +
                    'Loop: ' + self.header.get('Loop') + '\n' +
                    component + ' Component',
                    fontname='Century Gothic', fontsize=10, va='top', ha='center')

        plt.figtext(0.955, 0.935,
                    self.header.get('Client') + '\n' + self.header.get('Grid') + '\n' + self.header['Date'] + '\n',
                    fontname='Century Gothic', fontsize=10, va='top', ha='right')

    def add_rectangle(self, figure):
        """
        Draws a rectangle around a figure object
        """
        rect = patches.Rectangle(xy=(0.02, 0.02), width=0.96, height=0.96, linewidth=0.7, edgecolor='black',
                                 facecolor='none', transform=figure.transFigure)
        figure.patches.append(rect)

    # def get_lin_figs(self):
    #     components = self.pem_file.get_components()
    #     file_dir = r'C:\_Data\2019\BMSC\Surface\MO-254'
    #     with PdfPages(os.path.join(file_dir, "lin test.pdf")) as pdf:
    #         for component in components:
    #             pdf.savefig(self.make_lin_fig(component))
    #             plt.clf()
    #
    # def get_log_figs(self):
    #     components = self.pem_file.get_components()
    #     log_figs = []
    #
    #     for component in components:
    #         log_figs.append(self.make_log_fig(component))
    #
    #     return log_figs


class PEMPrinter:
    """
    Class for printing PEMPLotter plots to PDF.
    Creates the figures for PEMPlotter so they may be closed after they are saved.
    :param pem_files: List of PEMFile objects
    :param save_dir: Desired save location for the PDFs
    :param kwargs: Plotting kwargs such as hide_gaps, gaps, and x limits used in PEMPlotter.
    """

    def __init__(self, pem_files, save_dir, **kwargs):
        self.pem_files = pem_files
        self.plotter = PEMPlotter
        self.save_dir = save_dir
        self.kwargs = kwargs
        self.pg = QProgressBar()
        self.pg_count = 0
        self.pg_end = sum([len(pem_file.get_components()) for pem_file in self.pem_files])
        self.pg.setValue(0)

    def create_lin_figure(self):
        """
        Creates the blank LIN figure
        """
        lin_fig, (ax1, ax2, ax3, ax4, ax5) = plt.subplots(5, 1, figsize=(8.5, 11), sharex=True)
        ax6 = ax5.twiny()
        ax6.get_shared_x_axes().join(ax5, ax6)

        return lin_fig

    def create_log_figure(self):
        """
        Creates an empty but formatted LOG figure
        """
        log_fig, ax = plt.subplots(1, 1, figsize=(8.5, 11))
        ax2 = ax.twiny()
        ax2.get_shared_x_axes().join(ax, ax2)
        plt.yscale('symlog', linthreshy=10, linscaley=1. / math.log(10), subsy=list(np.arange(2, 10, 1)))

        return log_fig

    def print_lin_figs(self):

        with PdfPages(os.path.join(self.save_dir, "lin.pdf")) as pdf:

            for pem_file in self.pem_files:
                components = pem_file.get_components()
                for component in components:
                    lin_figure = self.create_lin_figure()
                    lin_plot = self.plotter(pem_file, **self.kwargs).make_lin_fig(component, lin_figure)
                    pdf.savefig(lin_plot)
                    self.pg_count += 1
                    self.pg.setValue((self.pg_count/self.pg_end) * 100)
                    plt.close(lin_figure)

    def print_log_figs(self):

        with PdfPages(os.path.join(self.save_dir, "log.pdf")) as pdf:

            for pem_file in self.pem_files:
                components = pem_file.get_components()
                for component in components:
                    log_figure = self.create_log_figure()
                    log_plot = self.plotter(pem_file, **self.kwargs).make_log_fig(component, log_figure)
                    pdf.savefig(log_plot)
                    self.pg_count += 1
                    self.pg.setValue((self.pg_count / self.pg_end) * 100)
                    plt.close(log_figure)

# class CronePYQTFigure:
#     """
#     Class creating graphs using pyqtgraph.
#     # TODO Straight to Widget or make figures?
#     # TODO Only needs data, should the class do the rest of the work?
#     """


# if __name__ == "__main__":
#     # app = QtGui.QApplication(sys.argv)
#     # mw = MainWindow()
#     # app.exec_()
#
#     # cProfile.run('editor.make_plots()', sort='cumtime')
#     testing_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), "../../sample_files/9600NAv LP-100.PEM")
#     plots = CronePYQTFigure()
#     plots.plot(testing_file)
#     # plt.show()
