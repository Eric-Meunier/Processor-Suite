import logging
import math
import os
import re
import sys
from pprint import pprint
from itertools import chain
from operator import itemgetter, attrgetter
import matplotlib.backends.backend_tkagg  # Needed for pyinstaller, or receive  ImportError
import matplotlib as mpl
from src.pem.pem_parser import PEMParser
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
from matplotlib.lines import Line2D
import matplotlib.offsetbox
from mpl_toolkits.axes_grid1.anchored_artists import AnchoredSizeBar
from PyQt5.QtWidgets import (QProgressBar)
from matplotlib import patches
from matplotlib.backends.backend_pdf import PdfPages
from scipy import interpolate
from scipy import stats
import copy
from src.gps.gps_editor import GPSEditor, GPSParser

__version__ = '0.0.1'
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


def add_rectangle(figure):
    """
    Draws a rectangle around a figure object
    """
    rect = patches.Rectangle(xy=(0.02, 0.02), width=0.96, height=0.96, linewidth=0.7, edgecolor='black',
                             facecolor='none', transform=figure.transFigure)
    figure.patches.append(rect)


class PEMPlotter:
    """
    Class for creating Crone LIN, LOG and STEP figures.
    PEMFile must be averaged and split.
    """

    def __init__(self, pem_file=None, ri_file=None, **kwargs):  # hide_gaps=True, gap=None, x_min=None, x_max=None):
        super().__init__()
        self.pem_file = pem_file
        self.ri_file = ri_file
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
        # self.channel_bounds = self.calc_channel_bounds()
        self.line_colour = 'k'
        # self.line_colour = 'red'

    #
    # def calc_channel_bounds(self):
    #     # channel_bounds is a list of tuples showing the inclusive bounds of each data plot
    #     channel_bounds = [None] * 4
    #     num_channels_per_plot = int((self.num_channels - 1) // 4)
    #     remainder_channels = int((self.num_channels - 1) % 4)
    #
    #     for k in range(0, len(channel_bounds)):
    #         channel_bounds[k] = (k * num_channels_per_plot + 1, num_channels_per_plot * (k + 1))
    #
    #     for i in range(0, remainder_channels):
    #         channel_bounds[i] = (channel_bounds[i][0], (channel_bounds[i][1] + 1))
    #         for k in range(i + 1, len(channel_bounds)):
    #             channel_bounds[k] = (channel_bounds[k][0] + 1, channel_bounds[k][1] + 1)
    #
    #     channel_bounds.insert(0, (0, 0))
    #     return channel_bounds

    def format_figure(self, figure, step=False):
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
                plt.setp(ax.get_xticklabels(), visible=True, size=12, fontname='Century Gothic')

        plt.subplots_adjust(left=0.135 if step is False else 0.170, bottom=0.07, right=0.958, top=0.885)
        add_rectangle(figure)

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

        self.format_figure(lin_fig)
        channel_bounds = calc_channel_bounds()

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

    def make_step_fig(self, component, step_fig):
        """
        Plots the step data (from ri_file) into the step_fig.
        :param component: Component i.e. X, Y, or Z
        :param step_fig: Figure object
        :return: Figure object
        """

        def add_ylabel(profile_data, num_channels_to_plot):
            fluxgate = True if 'fluxgate' in self.survey_type.lower() else False
            units = 'pT' if fluxgate is True else 'nT/s'
            channels = [re.findall('\d+', key)[0] for key in profile_data if re.match('Ch', key)]

            step_fig.axes[0].set_ylabel("TP = Theoretical Primary\n"
                                        f"{'PP = Calculated PP x Ramp' if fluxgate is True else 'PP = Last Ramp Channel'}\n"
                                        f"S1 = Calculated Step Ch.1\n({units})")
            step_fig.axes[1].set_ylabel("Deviation from TP\n"
                                        "(% Total Theoretical)")
            step_fig.axes[2].set_ylabel("Step Channels 2 - 4\n"
                                        "Deviation from S1\n"
                                        "(% Total Theoretical)")
            step_fig.axes[3].set_ylabel("Pulse EM Off-time\n"
                                        f"Channels {str(min(channels[-num_channels_to_plot:]))} - {str(max(channels[-num_channels_to_plot:]))}\n"
                                        f"({units})")

        def annotate_line(ax, annotation, interp_data, x_intervals, offset):

            for i, x_position in enumerate(x_intervals[int(offset)::int(len(x_intervals) * 0.4)]):
                y = interp_data[list(x_intervals).index(x_position)]

                ax.annotate(str(annotation), xy=(x_position, y), xycoords="data", size=7.5, va='center_baseline',
                            ha='center',
                            color=self.line_colour)

        def draw_step_lines(fig, profile_data):
            """
            Plotting the lines for step plots made from RI files.
            :param fig: step_fig Figure object
            :param profile_data: RI file data tranposed to profile mode
            :return: step_fig object with lines plotted
            """

            segments = 1000  # The data will be broken in this number of segments
            offset = segments * 0.1  # Used for spacing the annotations

            keys = ['Theoretical PP', 'Measured PP', 'S1', '(M-T)*100/Tot', '(S1-T)*100/Tot', '(S2-S1)*100/Tot', 'S3%',
                    'S4%']
            annotations = ['TP', 'PP', 'S1', 'PP', 'S1', 'S2', 'S3', 'S4']
            stations = profile_data['Stations']
            for i, key in enumerate(keys):
                interp_data, x_intervals = self.get_interp_data(profile_data[key], stations)
                mask = np.isclose(interp_data, interp_data.astype('float64'))
                x_intervals = x_intervals[mask]
                interp_data = interp_data[mask]

                if i < 3:  # Plotting TP, PP, and S1 to the first axes
                    ax = fig.axes[0]
                    ax.plot(x_intervals, interp_data, color=self.line_colour)
                    annotate_line(ax, annotations[i], interp_data, x_intervals, offset)
                    offset += len(x_intervals) * 0.15
                elif i < 5:  # Plotting the PP and S1% to the second axes
                    if i == 3:  # Resetting the annotation positions
                        offset = segments * 0.1
                    ax = fig.axes[1]
                    ax.plot(x_intervals, interp_data, color=self.line_colour)
                    annotate_line(ax, annotations[i], interp_data, x_intervals, offset)
                    offset += len(x_intervals) * 0.15
                else:  # Plotting S2% to S4% to the third axes
                    if i == 5:
                        offset = segments * 0.1
                    ax = fig.axes[2]
                    ax.plot(x_intervals, interp_data, color=self.line_colour)
                    annotate_line(ax, annotations[i], interp_data, x_intervals, offset)
                    offset += len(x_intervals) * 0.15
                if offset >= len(x_intervals) * 0.85:
                    offset = len(x_intervals) * 0.10

            offset = segments * 0.1
            # Plotting the off-time channels to the fourth axes
            for i, channel in enumerate(off_time_channel_data[-num_channels_to_plot:]):
                interp_data, x_intervals = self.get_interp_data(channel, stations)
                mask = np.isclose(interp_data, interp_data.astype('float64'))
                x_intervals = x_intervals[mask]
                interp_data = interp_data[mask]
                ax = fig.axes[3]
                ax.plot(x_intervals, interp_data, color=self.line_colour)
                annotate_line(ax, str(num_off_time_channels - i), interp_data, x_intervals, offset)
                offset += len(x_intervals) * 0.15
                if offset >= len(x_intervals) * 0.85:
                    offset = len(x_intervals) * 0.10

        self.format_figure(step_fig, step=True)
        profile_data = self.get_profile_step_data(component)
        off_time_channel_data = [profile_data[key] for key in profile_data if re.match('Ch', key)]
        num_off_time_channels = len(off_time_channel_data) + 10
        num_channels_to_plot = round(num_off_time_channels / 4)

        draw_step_lines(step_fig, profile_data)

        self.add_title(component)
        add_ylabel(profile_data, num_channels_to_plot)
        self.format_yaxis(step_fig, step=True)
        self.format_xaxis(step_fig)
        return step_fig

    def make_plan_map(self, pem_files):
        pass

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
        Transforms the data so it is ready to be plotted for LIN and LOG plots. Only for PEM data.
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

    def get_profile_step_data(self, component):
        """
        Transforms the RI data as a profile to be plotted.
        :param component: The component that is being plotted (i.e. X, Y, Z)
        :return: The data in profile mode
        """
        profile_data = {}
        keys = self.ri_file.columns
        component_data = list(filter(lambda d: d['Component'] == component, self.ri_file.data))

        for key in keys:
            if key is not 'Gain' and key is not 'Component':
                if key is 'Station':
                    key = 'Stations'
                    profile_data[key] = [self.convert_station(station['Station']) for station in component_data]
                else:
                    profile_data[key] = [float(station[key]) for station in component_data]
        return profile_data

    def get_channel_data(self, channel, profile_data):
        """
        Get the profile-mode data for a given channel. Only for PEM data.
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

    def get_interp_data(self, profile_data, stations, segments=1000, interp_method='linear'):
        """
        Interpolates the data using 1-D piecewise linear interpolation. The data is segmented
        into 1000 segments.
        :param profile_data: The EM data in profile mode
        :param segments: Number of segments to interpolate
        :param hide_gaps: Bool: Whether or not to hide gaps
        :param gap: The minimum length threshold above which is considered a gap
        :return: The interpolated data and stations
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

    def draw_lines(self, ax, channel_low, channel_high, component):
        """
        Plots the lines into an axes of a figure
        :param ax: Axes of a figure, either LIN or LOG figure objects
        :param channel_low: The first channel to be plotted
        :param channel_high: The last channel to be plotted
        :param component: String letter representing the component to plot (X, Y, or Z)
        """

        segments = 1000  # The data will be broken in this number of segments
        offset = segments * 0.1  # Used for spacing the annotations
        profile_channel_data = self.get_profile_data(component)

        for k in range(channel_low, (channel_high + 1)):
            # Gets the profile data for a single channel, along with the stations
            channel_data, stations = self.get_channel_data(k, profile_channel_data)

            # Interpolates the channel data, also returns the corresponding x intervals
            interp_data, x_intervals = self.get_interp_data(channel_data, stations, segments)

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
                    ax.annotate(str(k), xy=(x_position, y), xycoords="data", size=7.5, va='center_baseline',
                                ha='center',
                                color=self.line_colour)

            offset += len(x_intervals) * 0.15

            if offset >= len(x_intervals) * 0.85:
                offset = len(x_intervals) * 0.10

    def format_yaxis(self, figure, step=False):
        """
        Formats the Y axis of a figure
        :param figure: LIN or LOG figure object
        """
        axes = figure.axes[:-1]

        for ax in axes:
            ax.get_yaxis().set_label_coords(-0.08 if step is False else -0.095, 0.5)

            if ax.get_yscale() != 'symlog':
                y_limits = ax.get_ylim()

                if 'induction' in self.survey_type.lower():
                    if step is True:
                        if ax == axes[1] and (y_limits[1] - y_limits[0]) < 20:
                            new_high = math.ceil(((y_limits[1] - y_limits[0]) / 2) + 10)
                            new_low = new_high * -1
                        elif ax in axes[2:4] and (y_limits[1] - y_limits[0]) < 3:
                            new_high = math.ceil(((y_limits[1] - y_limits[0]) / 2) + 1)
                            new_low = new_high * -1
                        else:
                            new_high = math.ceil(max(y_limits[1], 0))
                            new_low = math.floor(min(y_limits[0], 0))
                    else:
                        if (y_limits[1] - y_limits[0]) < 3:
                            new_high = math.ceil(((y_limits[1] - y_limits[0]) / 2) + 1)
                            new_low = new_high * -1
                        else:
                            new_high = math.ceil(max(y_limits[1], 0))
                            new_low = math.floor(min(y_limits[0], 0))

                elif 'fluxgate' in self.survey_type.lower():
                    if step is True:
                        if ax == axes[1] and (y_limits[1] - y_limits[0]) < 20:
                            new_high = math.ceil(((y_limits[1] - y_limits[0]) / 2) + 10)
                            new_low = new_high * -1
                        elif ax == axes[2] and (y_limits[1] - y_limits[0]) < 3:
                            new_high = math.ceil(((y_limits[1] - y_limits[0]) / 2) + 1)
                            new_low = new_high * -1
                        elif ax == axes[3] and (y_limits[1] - y_limits[0]) < 30:
                            new_high = math.ceil(((y_limits[1] - y_limits[0]) / 2) + 10)
                            new_low = new_high * -1
                        else:
                            new_high = math.ceil(max(y_limits[1], 0))
                            new_low = math.floor(min(y_limits[0], 0))
                    else:
                        if (y_limits[1] - y_limits[0]) < 30:
                            new_high = math.ceil(((y_limits[1] - y_limits[0]) / 2) + 10)
                            new_low = new_high * -1
                        else:
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

            # ax.yaxis.set_major_formatter(ticker.FormatStrFormatter('%d'))

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


class PlanMap:
    def __init__(self):
        self.figure = None
        self.pem_files = None
        self.gps_editor = GPSEditor

    def make_plan_map(self, pem_files, figure):
        self.figure = figure
        self.pem_files = pem_files

        if all(['surface' in pem_file.survey_type.lower() for pem_file in self.pem_files]):
            self.surface_plan()
        elif all(['borehole' in pem_file.survey_type.lower() for pem_file in self.pem_files]):
            self.borehole_plan()
        else:
            return None

    def plot_loops(self):

        def draw_loop(pem_file):
            loop_coords = pem_file.loop_coords
            loop_center = self.gps_editor().get_loop_center(copy.copy(loop_coords))
            eastings, northings = [float(coord[1]) for coord in loop_coords], [float(coord[2]) for coord in loop_coords]
            eastings.insert(0, eastings[-1])  # To close up the loop
            northings.insert(0, northings[-1])

            self.figure.axes[0].text(loop_center[0], loop_center[1], pem_file.header.get('Loop'),
                                     multialignment='center')
            self.figure.axes[0].plot(eastings, northings, color='b')

        loops = []
        for pem_file in self.pem_files:
            if pem_file.loop_coords not in loops:  # plot the loop if the loop hasn't been plotted yet
                draw_loop(pem_file)

    def format_figure(self):
        ax = self.figure.axes[0]
        ax.set_aspect('equal', adjustable='box')
        [ax.spines[spine].set_color('none') for spine in ax.spines]
        ax.tick_params(axis='y', which='major', labelrotation=90)
        ax.tick_params(which='major', width=1.00, length=5, labelsize=10)
        ax.yaxis.set_major_formatter(ticker.FormatStrFormatter('%dN'))
        ax.xaxis.set_major_formatter(ticker.FormatStrFormatter('%dE'))
        ax.xaxis.set_ticks_position('top')
        plt.setp(ax.get_xticklabels(), fontname='Century Gothic')
        plt.setp(ax.get_yticklabels(), fontname='Century Gothic', va='center')

        plt.subplots_adjust(left=0.135, bottom=0.07, right=0.958, top=0.785)
        add_rectangle(self.figure)

        xmin, xmax = ax.get_xlim()
        ymin, ymax = ax.get_ylim()
        xwidth, ywidth = xmax - xmin, ymax - ymin

        if xwidth < 1000:
            scalesize = 250
        elif xwidth < 2000:
            scalesize = 500
        elif xwidth < 3000:
            scalesize = 750
        elif xwidth < 4000:
            scalesize = 1000

        # SCALE BAR
        scalebar = AnchoredScaleBar(ax.transData, sizey=0)#, sizex=scalesize, label=str(scalesize) + 'm', loc=8, frameon=False,
        #                        pad=0.3, sep=2, color="black", ax=ax)
        # ax.add_artist(scalebar)
        add_scalebar(ax, matchy=False)
        # NORTH ARROW
        ax.annotate('N', (1, 0.1), xytext=(1,0.0), xycoords='axes fraction',
                        ha='center', fontsize=12, fontweight='bold',
                        arrowprops=dict(arrowstyle='fancy', color='k'), transform=ax.transAxes)

    def surface_plan(self):

        def plot_lines():
            pass

        self.plot_loops()
        plot_lines()
        self.format_figure()
        return self.figure

    def borehole_plan(self):
        borehole_names = []
        # TODO Can have same hole with two loops
        unique_boreholes = []
        for pem_file in self.pem_files:
            borehole_names.append(pem_file.header.get('LineHole'))
            if pem_file.header.get('LineHole') not in borehole_names:
                unique_boreholes.append(pem_file)
        self.pem_files = unique_boreholes

        return self.figure


from matplotlib.offsetbox import AnchoredOffsetbox


class AnchoredScaleBar(AnchoredOffsetbox):
    def __init__(self, transform, sizex=0, sizey=0, labelx=None, labely=None, loc=4,
                 pad=0.1, borderpad=0.1, sep=2, prop=None, barcolor="black", barwidth=None,
                 **kwargs):
        """
        Draw a horizontal and/or vertical  bar with the size in data coordinate
        of the give axes. A label will be drawn underneath (center-aligned).
        - transform : the coordinate frame (typically axes.transData)
        - sizex,sizey : width of x,y bar, in data units. 0 to omit
        - labelx,labely : labels for x,y bars; None to omit
        - loc : position in containing axes
        - pad, borderpad : padding, in fraction of the legend font size (or prop)
        - sep : separation between labels and bars in points.
        - **kwargs : additional arguments passed to base class constructor
        """
        from matplotlib.patches import Rectangle
        from matplotlib.offsetbox import AuxTransformBox, VPacker, HPacker, TextArea, DrawingArea
        bars = AuxTransformBox(transform)
        if sizex:
            bars.add_artist(Rectangle((0, 0), sizex, 0, ec=barcolor, lw=barwidth, fc="none"))
        if sizey:
            bars.add_artist(Rectangle((0, 0), 0, sizey, ec=barcolor, lw=barwidth, fc="none"))

        if sizex and labelx:
            self.xlabel = TextArea(labelx, minimumdescent=False)
            bars = VPacker(children=[bars, self.xlabel], align="center", pad=0, sep=sep)
        if sizey and labely:
            self.ylabel = TextArea(labely)
            bars = HPacker(children=[self.ylabel, bars], align="center", pad=0, sep=sep)

        AnchoredOffsetbox.__init__(self, loc, pad=pad, borderpad=borderpad,
                                   child=bars, prop=prop, frameon=False, **kwargs)


def add_scalebar(ax, matchx=True, matchy=True, hidex=True, hidey=True, **kwargs):
    """ Add scalebars to axes
    Adds a set of scale bars to *ax*, matching the size to the ticks of the plot
    and optionally hiding the x and y axes
    - ax : the axis to attach ticks to
    - matchx,matchy : if True, set size of scale bars to spacing between ticks
                    if False, size should be set using sizex and sizey params
    - hidex,hidey : if True, hide x-axis and y-axis of parent
    - **kwargs : additional arguments passed to AnchoredScaleBars
    Returns created scalebar object
    """

    def f(axis):
        l = axis.get_majorticklocs()
        return len(l) > 1 and (l[1] - l[0])

    if matchx:
        kwargs['sizex'] = f(ax.xaxis)
        kwargs['labelx'] = str(kwargs['sizex'])
    if matchy:
        kwargs['sizey'] = f(ax.yaxis)
        kwargs['labely'] = str(kwargs['sizey'])

    sb = AnchoredScaleBar(ax.transData, **kwargs)
    ax.add_artist(sb)

    if hidex: ax.xaxis.set_visible(False)
    if hidey: ax.yaxis.set_visible(False)
    if hidex and hidey: ax.set_frame_on(False)

    return sb

# # Draws a pretty scale bar
# class AnchoredHScaleBar(matplotlib.offsetbox.AnchoredOffsetbox):
#     """ size: length of bar in data units
#         extent : height of bar ends in axes units
#     """
#     def __init__(self, size=1, extent = 0.03, label="", loc=1, ax=None,
#                  pad=0.4, borderpad=0.5, ppad = -25, sep=2, prop=None,
#                  frameon=True, **kwargs):
#         if not ax:
#             ax = plt.gca()
#         trans = ax.get_xaxis_transform()
#         size_bar = matplotlib.offsetbox.AuxTransformBox(trans)
#         line = Line2D([0,size],[0,0], **kwargs)
#         vline1 = Line2D([0,0],[-extent/2.,extent/2.], **kwargs)
#         vline2 = Line2D([size,size],[-extent/2.,extent/2.], **kwargs)
#         size_bar.add_artist(line)
#         size_bar.add_artist(vline1)
#         size_bar.add_artist(vline2)
#         txt = matplotlib.offsetbox.TextArea(label, minimumdescent=False)
#         self.vpac = matplotlib.offsetbox.VPacker(children=[size_bar,txt],
#                                  align="center", pad=ppad, sep=sep)
#         matplotlib.offsetbox.AnchoredOffsetbox.__init__(self, loc, pad=pad,
#                  borderpad=borderpad, child=self.vpac, prop=prop, frameon=frameon)


class PEMPrinter:
    """
    Class for printing PEMPLotter plots to PDF.
    Creates the figures for PEMPlotter so they may be closed after they are saved.
    :param pem_files: List of PEMFile objects
    :param save_path: Desired save location for the PDFs
    :param kwargs: Plotting kwargs such as hide_gaps, gaps, and x limits used in PEMPlotter.
    """

    def __init__(self, save_path, files, **kwargs):
        self.files = files  # Zipped PEM and RI files
        self.pem_files = []
        self.ri_files = []
        self.sort_files()
        self.plotter = PEMPlotter
        self.mapper = PlanMap
        self.save_path = save_path
        self.kwargs = kwargs
        self.pb = QProgressBar()
        self.pb_count = 0
        self.pb_end = sum([len(pair[0].get_components()) for pair in self.files])
        self.pb.setValue(0)

    def sort_files(self):
        self.files.sort(key=lambda x: x[0].get_components(), reverse=True)
        self.files.sort(key=lambda x: x[0].header['LineHole'])

        self.pem_files = [pair[0] for pair in self.files]
        self.ri_files = [pair[1] for pair in self.files]

    def create_plan_figure(self):
        """
        Creates an empty but formatted Plan figure
        :return: Figure object
        """
        plan_fig, ax = plt.subplots(1, 1, figsize=(8.5, 11))
        return plan_fig

    def create_lin_figure(self):
        """
        Creates the blank LIN figure
        :return: Figure object
        """
        lin_fig, (ax1, ax2, ax3, ax4, ax5) = plt.subplots(5, 1, figsize=(8.5, 11), sharex=True)
        ax6 = ax5.twiny()
        ax6.get_shared_x_axes().join(ax5, ax6)

        return lin_fig

    def create_log_figure(self):
        """
        Creates an empty but formatted LOG figure
        :return: Figure object
        """
        log_fig, ax = plt.subplots(1, 1, figsize=(8.5, 11))
        ax2 = ax.twiny()
        ax2.get_shared_x_axes().join(ax, ax2)
        plt.yscale('symlog', linthreshy=10, linscaley=1. / math.log(10), subsy=list(np.arange(2, 10, 1)))

        return log_fig

    def create_step_figure(self):
        """
        Creates the blank Step figure
        :return: Figure object
        """
        stp_fig, (ax1, ax2, ax3, ax4) = plt.subplots(4, 1, figsize=(8.5, 11), sharex=True)
        ax5 = ax4.twiny()
        ax5.get_shared_x_axes().join(ax4, ax5)

        return stp_fig

    # To save LIN and LOG pdfs separately. Requires a save_dir instead of a save_path.
    # def print_lin_figs(self):
    #     with PdfPages(os.path.join(self.save_dir, "lin.pdf")) as pdf:
    #         for pem_file in self.pem_files:
    #             components = pem_file.get_components()
    #             for component in components:
    #                 lin_figure = self.create_lin_figure()
    #                 lin_plot = self.plotter(pem_file, **self.kwargs).make_lin_fig(component, lin_figure)
    #                 pdf.savefig(lin_plot)
    #                 self.pb_count += 1
    #                 self.pb.setValue((self.pb_count/self.pb_end) * 100)
    #                 plt.close(lin_figure)
    #
    # def print_log_figs(self):
    #     with PdfPages(os.path.join(self.save_dir, "log.pdf")) as pdf:
    #         for pem_file in self.pem_files:
    #             components = pem_file.get_components()
    #             for component in components:
    #                 log_figure = self.create_log_figure()
    #                 log_plot = self.plotter(pem_file, **self.kwargs).make_log_fig(component, log_figure)
    #                 pdf.savefig(log_plot)
    #                 self.pb_count += 1
    #                 self.pb.setValue((self.pb_count / self.pb_end) * 100)
    #                 plt.close(log_figure)

    def print_plan_map(self):
        with PdfPages(self.save_path + '.PDF') as pdf:
            plan_figure = self.create_plan_figure()
            plan_map = self.mapper().make_plan_map(self.pem_files, plan_figure)
            pdf.savefig(plan_map)
            self.pb_count += 1
            self.pb.setValue((self.pb_count / self.pb_end) * 100)
            plt.close(plan_figure)
        os.startfile(self.save_path + '.PDF')

    def print_step_plots(self):
        with PdfPages(self.save_path + '.PDF') as pdf:
            for file in self.files:
                pem_file = file[0]
                ri_file = file[1]
                if ri_file:
                    components = pem_file.get_components()
                    for component in components:
                        step_figure = self.create_step_figure()
                        step_plot = self.plotter(pem_file=pem_file, ri_file=ri_file, **self.kwargs).make_step_fig(
                            component,
                            step_figure)
                        pdf.savefig(step_plot)
                        self.pb_count += 1
                        self.pb.setValue((self.pb_count / self.pb_end) * 100)
                        plt.close(step_figure)
        os.startfile(self.save_path + '.PDF')

    def print_final_plots(self):
        # file_name = self.pem_files[-1].header.get('LineHole')+'.PDF'
        # path = os.path.join(self.save_dir, file_name)
        with PdfPages(self.save_path + '.PDF') as pdf:
            for pem_file in self.pem_files:
                components = pem_file.get_components()
                for component in components:
                    lin_figure = self.create_lin_figure()
                    lin_plot = self.plotter(pem_file=pem_file, **self.kwargs).make_lin_fig(component, lin_figure)
                    pdf.savefig(lin_plot)
                    self.pb_count += 1
                    self.pb.setValue((self.pb_count / self.pb_end) * 100)
                    plt.close(lin_figure)
            for pem_file in self.pem_files:
                components = pem_file.get_components()
                for component in components:
                    log_figure = self.create_log_figure()
                    log_plot = self.plotter(pem_file=pem_file, **self.kwargs).make_log_fig(component, log_figure)
                    pdf.savefig(log_plot)
                    self.pb_count += 1
                    self.pb.setValue((self.pb_count / self.pb_end) * 100)
                    plt.close(log_figure)
            for file in self.files:
                pem_file = file[0]
                ri_file = file[1]
                if ri_file:
                    components = pem_file.get_components()
                    for component in components:
                        step_figure = self.create_step_figure()
                        step_plot = self.plotter(pem_file=pem_file, ri_file=ri_file, **self.kwargs).make_step_fig(
                            component,
                            step_figure)
                        pdf.savefig(step_plot)
                        self.pb_count += 1
                        self.pb.setValue((self.pb_count / self.pb_end) * 100)
                        plt.close(step_figure)
        os.startfile(self.save_path + '.PDF')


# class CronePYQTFigure:
#     """
#     Class creating graphs using pyqtgraph.
#     # TODO Straight to Widget or make figures?
#     # TODO Only needs data, should the class do the rest of the work?
#     """

if __name__ == '__main__':
    parser = PEMParser()
    # sample_files = os.path.join(os.path.dirname(os.path.dirname(application_path)), "sample_files")
    sample_files_dir = r'C:\_Data\2019\BMSC\Surface\MO-254\PEM'
    file_names = [f for f in os.listdir(sample_files_dir) if
                  os.path.isfile(os.path.join(sample_files_dir, f)) and f.lower().endswith('.pem')]
    pem_files = []

    # file = os.path.join(sample_files, file_names[0])
    for file in file_names:
        filepath = os.path.join(sample_files_dir, file)
        pem_file = parser.parse(filepath)
        print('File: ' + filepath)
        pem_files.append((pem_file, None))  # Empty second item for ri_files

    printer = PEMPrinter(sample_files_dir, pem_files)
    printer.print_final_plots()
