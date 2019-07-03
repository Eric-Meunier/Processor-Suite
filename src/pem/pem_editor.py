from src.pem.pem_parser import PEMParser, PEMFile
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from matplotlib.figure import Figure
from matplotlib import patches
from collections import OrderedDict
import numpy as np
import math
import re
from scipy import interpolate
from scipy import stats
from log import Logger
import warnings
from matplotlib.dates import date2num, DateConverter, num2date
from matplotlib.container import ErrorbarContainer
from datetime import datetime

# plt.style.use('seaborn-white')
# plt.style.use('bmh')
# plt.style.use('ggplot')

plt.style.use('seaborn-paper')
logger = Logger(__name__)

import time


class PEMFileEditor:
    """
    Class for making edits to and generating plots from PEM_Files
    """

    def __init__(self):
        self.active_file = None
        self.parser = PEMParser()

    def open_file(self, file_path):
        """
        Sets the active file. All subsequent operations will be done on the file contained at file_path.
        :param file_path: string containing path to a PEM file
        """
        self.active_file = self.parser.parse(file_path)

    # File plotting functions

    def generate_plots(self, **kwargs):
        """
        :return: A list of matplotlib.figure objects representing the data found inside of the active file
        """
        logger.info("Generating plots...")

        lin_fig, log_fig = self.mk_linlog_plots(**kwargs)
        logger.info("Finished generating plots")
        return lin_fig, log_fig

    def get_survey_type(self):
        survey_type = self.active_file.get_header()['SurveyType']

        if survey_type.casefold() == 's-coil':
            survey_type = 'Surface Induction'
        elif survey_type.casefold() == 'borehole':
            survey_type = 'Borehole Induction'
        elif survey_type.casefold() == 'b-rad':
            survey_type = 'Borehole Induction'
        elif survey_type.casefold() == 's-flux':
            survey_type = 'Surface Fluxgate'
        elif survey_type.casefold() == 'bh-flux':
            survey_type = 'Borehole Fluxgate'
        elif survey_type.casefold() == 's-squid':
            survey_type = 'SQUID'
        else:
            survey_type = 'UNDEF_SURV'

        return survey_type

    def convert_stations(self):
        """
        Converts all the station names in the data into a number, negative if the stations was S or W
        :param data: Dictionary of data from a PEM file
        :return: Dictionary of data for a PEM file with the station numbers now integers
        """
        data = self.active_file.get_data()
        stations = [d['Station'] for d in data]

        for index, station in enumerate(stations):

            if re.match(r"\d+(S|W)", station):
                data[index]['Station'] = (-int(re.sub(r"\D", "", station)))

            else:
                data[index]['Station'] = (int(re.sub(r"\D", "", station)))

        return data

    def get_components(self):
        """
        Retrieve the unique components of the survey file (i.e. Z, X, or Y)
        :param data: EM data dictionary of a PEM file
        :return: List of components in str format
        """
        # sort the data by station. Station names must first be converted into a number
        data = sorted(self.convert_stations(), key=lambda k: k['Station'])
        unique_components = []

        for reading in data:
            component = reading['Component']

            if component not in unique_components:
                unique_components.append(component)

        if 'Z' in unique_components:
            unique_components.insert(0, unique_components.pop(unique_components.index('Z')))

        self.components = unique_components
        return unique_components

    def get_profile_data(self, component_data):
        """
        Transforms the data so it is ready to be plotted for LIN and LOG plots
        :param component_data: Data (dict) for a single component (i.e. Z, X, or Y)
        :return: Dictionary where each key is a channel, and the values of those keys are a list of
        dictionaries which contain the stations and readings of all readings of that channel
        """
        profile_data = {}
        num_channels = len(component_data[0]['Data'])

        for channel in range(0, num_channels):
            # profile_data[channel] = {}
            channel_data = []

            for i, station in enumerate(component_data):
                reading = station['Data'][channel]
                station_number = station['Station']
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

    def calc_gaps(self, stations, gap):
        survey_type = self.get_survey_type()

        if 'borehole' in survey_type.casefold():
            min_gap = 50
        elif 'surface' in survey_type.casefold():
            min_gap = 200
        station_gaps = np.diff(stations)

        if gap is None:
            gap = max(int(stats.mode(station_gaps)[0] * 2), min_gap)

        gap_intervals = [(stations[i], stations[i + 1]) for i in range(len(stations) - 1) if
                         station_gaps[i] > gap]

        return gap_intervals

    def get_interp_data(self, profile_data, stations, segments, hide_gaps, gap, interp_method='linear'):
        """
        Interpolates the data using 1-D piecewise linear interpolation. The data is segmented
        into 100 segments.
        :param profile_data: The EM data in profile mode
        :param stations: The stations of the EM data
        :return: The interpolated data and stations
        """
        stations = np.array(stations, dtype='float64')
        readings = np.array(profile_data, dtype='float64')
        x_intervals = np.linspace(stations[0], stations[-1], segments)
        f = interpolate.interp1d(stations, readings, kind=interp_method)

        interpolated_y = f(x_intervals)

        if hide_gaps:
            gap_intervals = self.calc_gaps(stations, gap)

            # Masks the intervals that are between gap[0] and gap[1]
            for gap in gap_intervals:
                interpolated_y = np.ma.masked_where((x_intervals > gap[0]) & (x_intervals < gap[1]),
                                                    interpolated_y)

        return interpolated_y, x_intervals

    def mk_linlog_plots(self, **kwargs):
        """
        Plot the LIN and LOG plots.
        :return: LIN plot figure and LOG plot figure
        """

        file = self.active_file
        # Header info mostly just for the title of the plots
        # TODO Negative coil area in PEM file breaks the parsing
        header = file.get_header()
        tags = file.get_tags()

        if kwargs['Client']:
            client = kwargs['Client']
        else:
            client = header['Client']

        if kwargs['Loop']:
            loop = kwargs['Loop']
        else:
            loop = header['Loop']

        if kwargs['Grid']:
            grid = kwargs['Grid']
        else:
            grid = header['Grid']

        interp_method = kwargs['Interp'].split()[0].lower()

        linehole = header['LineHole']
        date = header['Date']
        current = float(tags['Current'])
        timebase = float(header['Timebase'])
        timebase_freq = ((1 / (timebase / 1000)) / 4)
        survey_type = self.get_survey_type()
        num_channels = int(header['NumChannels']) + 1  # +1 because the header channel number is only offtime
        units = file.get_tags()['Units']

        if 'borehole' in survey_type.casefold():
            s_title = 'Hole'
        else:
            s_title = 'Line'

        if units.casefold() == 'nanotesla/sec':
            units = 'nT/s'
        elif 'picotesla' in units.casefold():
            units = 'pT'
        else:
            units = "UNDEF_UNIT"

        first_channel_label = "Primary Pulse"

        components = self.get_components()

        log_figs = []
        lin_figs = []

        line_width = 0.5
        line_colour = '#1B2631'
        alpha = 1
        font = "Tahoma"

        def mk_subplot(ax, channel_low, channel_high, profile_data, segments=1000):
            """
            Plots and annotates the data in the LIN and LOG plots
            :param ax: Axes object
            :param channel_low: The smallest channel being plotted in the axes
            :param channel_high: The largest channel being plotted in the axes
            :param profile_data: The data in profile mode. Gets interpolated.
            """
            offset = segments * 0.1

            leftbound = kwargs['lbound']
            rightbound = kwargs['rbound']
            hide_gaps = kwargs['hide_gaps']
            gap = kwargs['gap']

            for k in range(channel_low, (channel_high + 1)):
                # Gets the profile data for a single channel, along with the stations
                channel_data, stations = self.get_channel_data(k, profile_data)

                # Interpolates the channel data, also returns the corresponding x intervals
                interp_data, x_intervals = self.get_interp_data(channel_data, stations, segments, hide_gaps, gap,
                                                                interp_method)
                ax.plot(x_intervals, interp_data, color=line_colour, linewidth=line_width, alpha=alpha)

                if leftbound is not None and rightbound is not None:
                    ax.set_xlim(leftbound, rightbound)
                elif leftbound is not None:
                    ax.set_xlim(left=leftbound)
                elif rightbound is not None:
                    ax.set_xlim(right=rightbound)

                ax.plot(x_intervals, interp_data, color=line_colour, linewidth=line_width, alpha=alpha)

                mask = np.isclose(interp_data, interp_data.astype('float64'))
                x_intervals = x_intervals[mask]
                interp_data = interp_data[mask]

                for i, x_position in enumerate(x_intervals[int(offset)::int(len(x_intervals) * 0.4)]):
                    y = interp_data[list(x_intervals).index(x_position)]

                    if k == 0:
                        ax.annotate('PP', xy=(x_position, y), xycoords="data", size=7.5, color=line_colour,
                                    va='center_baseline', ha='center', alpha=alpha)

                    else:
                        ax.annotate(str(k), xy=(x_position, y), xycoords="data", size=7.5, color=line_colour,
                                    va='center_baseline', ha='center', alpha=alpha)

                offset += len(x_intervals) * 0.15

                if offset >= len(x_intervals) * 0.85:
                    offset = len(x_intervals) * 0.10

        def add_titles():
            """
            Adds the titles to the plots
            """

            plt.figtext(0.555, 0.955, 'Crone Geophysics & Exploration Ltd.',
                        fontname='Century Gothic', alpha=alpha, fontsize=11, ha='center')

            plt.figtext(0.555, 0.940, survey_type + ' Pulse EM Survey', family='cursive', style='italic',
                        fontname='Century Gothic', alpha=alpha, fontsize=10, ha='center')

            plt.figtext(0.14, 0.930, 'Timebase: ' + str(timebase) + ' ms\n' +
                        'Base Frequency: ' + str(round(timebase_freq, 2)) + ' Hz\n' +
                        'Current: ' + str(round(current, 1)) + ' A',
                        fontname='Century Gothic', alpha=alpha, fontsize=10, va='top')

            plt.figtext(0.555, 0.930, s_title + ': ' + linehole + '\n'
                        + component + ' Component' + '\n'
                        + 'Loop: ' + loop,
                        fontname='Century Gothic', alpha=alpha, fontsize=10, va='top', ha='center')

            plt.figtext(0.955, 0.930, client + '\n' + grid + '\n' + date + '\n',
                        fontname='Century Gothic', alpha=alpha, fontsize=10, va='top', ha='right')

        def format_spine():
            ax.spines['right'].set_visible(False)
            ax.spines['top'].set_visible(False)
            plt.setp(ax.spines['left'], alpha=alpha)
            plt.setp(ax.spines['bottom'], alpha=alpha)
            ax.spines['bottom'].set_position(('data', 0))
            ax.xaxis.set_ticks_position('bottom')
            # ax.xaxis.set_minor_locator(minor_locator)
            ax.xaxis.set_major_locator(major_locator)
            ax.set_yticks(ax.get_yticks())
            ax.get_yaxis().set_label_coords(-0.08, 0.5)
            ax.tick_params(axis='x', which='major', direction='inout', length=4)
            # ax.tick_params(axis='x', which='minor', direction='inout', length=3)
            plt.setp(ax.get_yticklabels(), alpha=alpha, fontname=font)
            plt.setp(ax.get_xticklabels(), visible=False)
            ax.yaxis.set_major_formatter(ticker.FormatStrFormatter('%d'))
            if ax.get_yscale() == 'symlog':
                ax.tick_params(axis='y', which='major', labelrotation=90)
                plt.setp(ax.get_yticklabels(), va='center')

        def format_xlabel_spine():
            ax.spines['right'].set_visible(False)
            ax.spines['top'].set_visible(False)
            plt.setp(ax.spines['left'], alpha=alpha)
            plt.setp(ax.spines['bottom'], alpha=alpha)
            ax.spines['bottom'].set_visible(False)
            ax.spines["bottom"].set_position(("outward", 0.1))
            ax.xaxis.set_major_locator(x_label_locator)
            ax.xaxis.set_ticks_position('bottom')
            ax.xaxis.set_label_position('bottom')
            ax.set_yticks(ax.get_yticks())
            ax.tick_params(axis='x', which='major', direction='out', length=6)
            plt.setp(ax.get_xticklabels(), visible=True, size=12, alpha=alpha, fontname="Century Gothic")

        def add_rectangle():
            fig = plt.gcf()
            rect = patches.Rectangle(xy=(0.02, 0.02), width=0.96, height=0.96, linewidth=0.7, edgecolor='black',
                                     facecolor='none', transform=fig.transFigure)
            fig.patches.append(rect)

        # Each component has their own figure
        for component in components:
            logger.info("Plotting component " + component)
            # t1 = time.time()

            # The LIN plot always has 5 axes. LOG only ever has one.
            lin_fig, (ax1, ax2, ax3, ax4, ax5) = plt.subplots(5, 1, figsize=(8.5, 11), dpi=100, sharex=True)

            # Using subplots_adjust instead of tight_layout since it's significantly faster (3 secs -> 0.3 secs)
            # NOTE: Subplots y-axis' are now always at the same distance from the left edge. As a result, the y-axis
            #       labels may get cutoff if the y-axis numbers are too long. With tight_layout the y-axis distance from
            #       the left edge is changed to ensure the y-axis labels are always the same distance away.

            lin_fig.subplots_adjust(left=0.135, bottom=0.07, right=0.958, top=0.885)
            add_rectangle()
            ax6 = ax5.twiny()
            ax6.get_shared_x_axes().join(ax5, ax6)

            component_data = list(filter(lambda d: d['Component'] == component, self.active_file.get_data()))

            profile_data = self.get_profile_data(component_data)

            stations = [station['Station'] for station in component_data]
            x_limit = min(stations), max(stations)
            plt.xlim(x_limit)

            # minor_locator = AutoMinorLocator(5)
            major_locator = ticker.FixedLocator(stations)
            x_label_locator = ticker.AutoLocator()

            # Much of the slow loading time comes from the following block up to the End of block comment.
            # This is mostly due to matplotlib being oriented towards publication-quality graphics, and not being very
            # well optimized for speed.  If speed is desired in the future we will need to switch to a faster plotting
            # library such as pyqtgraph or vispy.

            # channel_bounds is a list of tuples showing the inclusive bounds of each data plot
            channel_bounds = [None] * 4
            num_channels_per_plot = int((num_channels - 1) // 4)
            remainder_channels = int((num_channels - 1) % 4)

            for k in range(0, len(channel_bounds)):
                channel_bounds[k] = (k * num_channels_per_plot + 1, num_channels_per_plot * (k + 1))

            for i in range(0, remainder_channels):
                channel_bounds[i] = (channel_bounds[i][0], (channel_bounds[i][1] + 1))
                for k in range(i + 1, len(channel_bounds)):
                    channel_bounds[k] = (channel_bounds[k][0] + 1, channel_bounds[k][1] + 1)
            # SUBTRACTS THE ON-TIME/PP CHANNEL
            channel_bounds[3] = (channel_bounds[3][0], num_channels - 1)

            # Set the Y-axis labels
            ax1.set_ylabel(first_channel_label + "\n(" + units + ")", fontname=font, alpha=alpha)
            ax2.set_ylabel("Channel 1 - " + str(channel_bounds[0][1]) +
                           "\n(" + units + ")", fontname=font, alpha=alpha)
            ax3.set_ylabel("Channel " + str(channel_bounds[1][0]) + " - " +
                           str(channel_bounds[1][1]) + "\n(" + units + ")", fontname=font, alpha=alpha)
            ax4.set_ylabel("Channel " + str(channel_bounds[2][0]) + " - " +
                           str(channel_bounds[2][1]) + "\n(" + units + ")", fontname=font, alpha=alpha)
            ax5.set_ylabel("Channel " + str(channel_bounds[3][0]) + " - " +
                           str(channel_bounds[3][1]) + "\n(" + units + ")", fontname=font, alpha=alpha)
            # lin_fig.align_ylabels()

            add_titles()

            # PLOT PP
            mk_subplot(ax1, 0, 0, profile_data)
            # Plotting each subplot
            mk_subplot(ax2, channel_bounds[0][0], channel_bounds[0][1], profile_data)
            mk_subplot(ax3, channel_bounds[1][0], channel_bounds[1][1], profile_data)
            mk_subplot(ax4, channel_bounds[2][0], channel_bounds[2][1], profile_data)
            mk_subplot(ax5, channel_bounds[3][0], channel_bounds[3][1], profile_data)

            # Formatting the styling of the subplots
            for index, ax in enumerate(lin_fig.axes):
                # Creates a minimum Y axis tick range
                y_limits = ax.get_ylim()

                if (y_limits[1] - y_limits[0]) < 3:
                    new_high = math.ceil(((y_limits[1] - y_limits[0]) / 2) + 1)
                    # new_low = math.floor(((y_limits[1] - y_limits[0]) / 2) - 2)
                    new_low = new_high * -1
                    ax.set_ylim(new_low, new_high)
                    ax.set_yticks(ax.get_yticks())

                elif index != 5:
                    new_high = math.ceil(max(y_limits[1], 0))
                    new_low = math.floor(min(y_limits[0], 0))
                    ax.set_ylim(new_low, new_high)
                    ax.set_yticks(ax.get_yticks())

                if index != 5:
                    format_spine()

                # The 6th subplot, only used for station tick labelling
                elif index == 5:
                    format_xlabel_spine()

            # Creating the LOG plot
            log_fig, ax = plt.subplots(1, 1, figsize=(8.5, 11), dpi=100)
            log_fig.subplots_adjust(left=0.135, bottom=0.07, right=0.958, top=0.885)

            axlog2 = ax.twiny()
            axlog2.get_shared_x_axes().join(ax, axlog2)
            plt.yscale('symlog', linthreshy=10, linscaley=1. / math.log(10), subsy=list(np.arange(2, 10, 1)))
            plt.xlim(x_limit)

            add_titles()
            add_rectangle()

            ax.set_ylabel(first_channel_label + ' to Channel ' + str(num_channels - 1) + '\n(' + str(units) + ')',
                          fontname=font,
                          alpha=alpha)

            mk_subplot(ax, 0, channel_bounds[3][1], profile_data)

            # SET LOG PLOT LIMITS
            y_limits = ax.get_ylim()
            new_high = 10.0 ** math.ceil(math.log(max(y_limits[1], 11), 10))
            new_low = -1 * 10.0 ** math.ceil(math.log(max(abs(y_limits[0]), 11), 10))
            ax.set_ylim(new_low, new_high)

            # Modify the axes spines
            for index, ax in enumerate(log_fig.axes):
                if index == 0:
                    format_spine()

                elif index == 1:
                    format_xlabel_spine()

            lin_figs.append(lin_fig)
            log_figs.append(log_fig)

        return lin_figs, log_figs

    # def mk_qt_plot(self):
    #     import pyqtgraph as pg
    #     pg.setConfigOption('background', 'w')
    #
    #     file = self.active_file
    #     # Header info mostly just for the title of the plots
    #     # TODO Negative coil area in PEM file breaks the parsing
    #     header = file.get_header()
    #     tags = file.get_tags()
    #     client = header['Client']
    #     loop = header['Loop']
    #     linehole = header['LineHole']
    #     date = header['Date']
    #     grid = header['Grid']
    #     current = float(tags['Current'])
    #     timebase = float(header['Timebase'])
    #     timebase_freq = ((1 / (timebase / 1000)) / 4)
    #     survey_type = self.get_survey_type()
    #     num_channels = int(header['NumChannels']) + 1  # +1 because the header channel number is only offtime
    #     units = file.get_tags()['Units']
    #
    #     if 'borehole' in survey_type.casefold():
    #         s_title = 'Hole'
    #     else:
    #         s_title = 'Line'
    #
    #     if units.casefold() == 'nanotesla/sec':
    #         units = 'nT/s'
    #     elif 'picotesla' in units.casefold():
    #         units = 'pT'
    #     else:
    #         units = "UNDEF_UNIT"
    #
    #     data = sorted(self.convert_stations(file.get_data()), key=lambda k: k['Station'])
    #     components = self.get_components(data)
    #
    #     for component in components:
    #         component_data = list(filter(lambda d: d['Component'] == component, data))
    #         profile_data = self.get_profile_data(component_data)
    #         stations = [station['Station'] for station in component_data]
    #         x_limit = min(stations), max(stations)

    # Legacy function, leave as reference
    def generate_placeholder_plots(self):
        """
        :return: A list of matplotlib.figure objects representing the data found inside of the active file
        """
        # Temporary placeholder plots
        # Use as guide for creating generate_plots
        plots_dict = OrderedDict()

        for reading in self.active_file.get_data():
            station_number = reading['Station']

            if station_number not in plots_dict:
                fig = Figure()
                ax = fig.add_subplot(111)
                ax.set_title('Station ' + str(station_number))
                ax.set_xlabel('Channel Number (By Index)')
                ax.set_ylabel('Amplitude (' + self.active_file.get_tags()['Units'] + ')')
                fig.subplots_adjust(bottom=0.15)

                plots_dict[station_number] = {'fig': fig}
                plots_dict[station_number]['ax'] = ax

            ax = plots_dict[station_number]['ax']
            y = reading['Data']
            ax.plot(range(len(y)), y, '-', linewidth=0.8)

        plots = [plot_data['fig'] for station_number, plot_data in plots_dict.items()]
        return plots


if __name__ == "__main__":
    # Code to test PEMFileEditor
    editor = PEMFileEditor()
    editor.open_file('CH934ZM.PEM')
    editor.generate_placeholder_plots()
