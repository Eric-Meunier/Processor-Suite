from src.pem.pem_parser import PEMParser, PEMFile
from matplotlib.figure import Figure
from matplotlib.ticker import (IndexLocator, AutoLocator, AutoMinorLocator, MaxNLocator, Locator,
                               FixedLocator)
import matplotlib.ticker as ticker
from collections import OrderedDict
import matplotlib.pyplot as plt
from matplotlib import patches
import numpy as np
import math
# from PIL import ImageDraw
import re
from log import Logger
from math import atan2, degrees
import warnings
from matplotlib.dates import date2num, DateConverter, num2date
from matplotlib.container import ErrorbarContainer
from datetime import datetime

logger = Logger(__name__)
# plt.style.use('seaborn-whitegrid')
# plt.style.use('seaborn-white')
# plt.style.use('bmh')
# plt.style.use('ggplot')
plt.style.use('seaborn-paper')

# import matplotlib.style as mplstyle
# mplstyle.use('fast')

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

    def generate_plots(self):
        """
        :return: A list of matplotlib.figure objects representing the data found inside of the active file
        """
        logger.info("Generating plots...")
        lin_fig, log_fig = self.mk_plots()
        logger.info("Finished generating plots")
        return lin_fig, log_fig

    def convert_stations(self, data):
        """
        Converts all the station names in the data into a number, negative if the stations was S or W
        :param data: Dictionary of data from a PEM file
        :return: Dictionary of data for a PEM file with the station numbers now integers
        """

        stations = [d['Station'] for d in data]

        for index, station in enumerate(stations):

            if re.match(r"\d+(S|W)", station):
                data[index]['Station'] = (-int(re.sub(r"\D", "", station)))

            else:
                data[index]['Station'] = (int(re.sub(r"\D", "", station)))

        return data

    def get_components(self, data):
        """
        Retrieve the unique components of the survey file (i.e. Z, X, or Y)
        :param data: EM data dictionary of a PEM file
        :return: List of components in str format
        """
        unique_components = []

        for reading in data:
            component = reading['Component']

            if component not in unique_components:
                unique_components.append(component)

        if 'Z' in unique_components:
            unique_components.insert(0, unique_components.pop(unique_components.index('Z')))

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
        data = []
        stations = []
        for station in profile_data[channel]:
            data.append(station['Reading'])
            stations.append(station['Station'])

        return data, stations

    def mk_plots(self):
        """
        Plot the LIN and LOG plots.
        :return: LIN plot figure and LOG plot figure
        """

        def get_interp_data(profile_data, stations):
            """
            Interpolates the data using 1-D piecewise linear interpolation. The data is segmented
            into 100 segments.
            :param profile_data: The EM data in profile mode
            :param stations: The stations of the EM data
            :return: The interpolated data and stations, in 100 segments
            TODO What if the survey has more than 100 stations already?
            """
            readings = np.array(profile_data, dtype='float64')
            step = abs((max(stations) - min(stations)) / 1000)
            x_intervals = np.arange(min(stations), max(stations) + 1, step)

            interp_data = np.interp(x_intervals, stations, readings)

            return interp_data, x_intervals

        def mk_subplot(ax, channel_low, channel_high, profile_data):
            """
            Plots and annotates the data in the LIN and LOG plots
            :param ax: Axes object
            :param channel_low: The smallest channel being plotted in the axes
            :param channel_high: The largest channel being plotted in the axes
            :param profile_data: The data in profile mode. Gets interpolated.
            """
            offset = 100

            # rect = plt.Rectangle((0.2, 0.75), 0.4, 0.15, color='k', alpha=0.3, transform=ax.transAxes)
            # ax.add_patch(rect)

            for k in range(channel_low, (channel_high + 1)):
                # Gets the profile data for a single channel, along with the stations
                channel_data, stations = self.get_channel_data(k, profile_data)

                # Interpolates the channel data, also returns the corresponding x intervals
                interp_data, x_intervals = get_interp_data(channel_data, stations)

                ax.plot(stations, channel_data, color=line_colour, linewidth=line_width, alpha=alpha)

                for i, x_position in enumerate(x_intervals[offset::400]):
                    y = interp_data[list(x_intervals).index(x_position)]

                    if k == 0:
                        ax.annotate('PP', xy=(x_position, y), xycoords="data", size=7,
                                    va='center_baseline', ha='center', alpha=alpha)

                    else:
                        ax.annotate(str(k), xy=(x_position, y), xycoords="data", size=7,
                                    va='center_baseline', ha='center', alpha=alpha)
                offset += 150

                if offset >= 850:
                    offset = 100

        # def calc_y(x_position_percent, stations_percent, array):
        #     """
        #     Calculate the Y value at a given position
        #     :param x_position_percent: Percentage along the x-axis
        #     :param array: Profile data for a given channel
        #     :return: The Y axis value at the x_position_percent
        #     """
        #     # x_index = x_position_percent * len(array)
        #     # xp = np.arange(0, len(array), 1, dtype='float64')
        #
        #     fp = np.asarray(array, dtype='float64')
        #     # if ax.get_yscale()=='symlog':
        #     #     y_value = np.interp(x_position_percent, stations_percent, fp)
        #     y_value = np.interp(x_position_percent, stations_percent, fp)
        #
        #     return y_value

        # def annotate_plot(str_annotation, obj_plt, channel, offset):
        #     # TODO Make plotting interp based, and also probably make annotations not interp based.
        #     # List of stations but using a percent to represent their position
        #     stations_percent = [(abs(stations[x] - stations[0]) / abs(stations[0] - stations[-1])) for x in
        #                         range(len(stations))]
        #
        #     for i in range(0, 100, 40):
        #         x_percent = i / 100 + offset
        #         y = calc_y(x_percent, stations_percent, profile_data[channel])
        #
        #         obj_plt.annotate(str_annotation, xy=(x_percent, y), xycoords=("axes fraction", "data"), size=7,
        #                          va='center_baseline', ha='center', alpha=alpha)

        def add_titles():
            """
            Adds the titles to the plots
            """

            plt.figtext(0.555, 0.97, 'Crone Geophysics & Exploration Ltd.',
                        fontname='Century Gothic', alpha=alpha, fontsize=10, ha='center')

            plt.figtext(0.555, 0.955, survey_type + ' Pulse EM Survey', family='cursive', style='italic',
                        fontname='Century Gothic', alpha=alpha, fontsize=9, ha='center')

            plt.figtext(0.125, 0.945, 'Timebase: ' + str(timebase) + ' ms\n' +
                        'Frequency: ' + str(round(timebase_freq, 2)) + ' Hz',
                        fontname='Century Gothic', alpha=alpha, fontsize=9, va='top')

            plt.figtext(0.555, 0.945, s_title + ': ' + linehole + '\n'
                        + component + ' Component' + '\n'
                        + 'Loop: ' + loop,
                        fontname='Century Gothic', alpha=alpha, fontsize=9, va='top', ha='center')

            plt.figtext(0.975, 0.945, client + '\n' + grid + '\n' + date + '\n',
                        fontname='Century Gothic', alpha=alpha, fontsize=9, va='top', ha='right')

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
            ax.tick_params(axis='x', which='major', direction='inout', length=3)
            # ax.tick_params(axis='x', which='minor', direction='inout', length=3)
            plt.setp(ax.get_yticklabels(), alpha=alpha, fontname=font)
            plt.setp(ax.get_xticklabels(), visible=False)

        def format_xlabel_spine():
            ax.spines['right'].set_visible(False)
            ax.spines['bottom'].set_visible(False)
            plt.setp(ax.spines['left'], alpha=alpha)
            plt.setp(ax.spines['top'], alpha=alpha)
            ax.spines['top'].set_visible(False)
            ax.spines["top"].set_position(("axes", -0.1))
            ax.xaxis.set_major_locator(x_label_locator)
            ax.xaxis.set_ticks_position('bottom')
            ax.xaxis.set_label_position('bottom')
            ax.set_yticks(ax.get_yticks())
            ax.tick_params(axis='x', which='major', direction='out', length=6)
            plt.setp(ax.get_xticklabels(), visible=True, size=12, alpha=alpha, fontname="Century Gothic")

        def add_rectangle():
            fig = plt.gcf()
            rect = patches.Rectangle(xy=(0.01, 0.01), width=0.98, height=0.98, linewidth=0.7, edgecolor='black',
                                     facecolor='none', transform=fig.transFigure)
            # box = patches.FancyBboxPatch(xy=(0.01, 0.01), width=0.98, height=0.98, linewidth=0.8, edgecolor='black',
            #                              facecolor='none', transform=fig.transFigure, boxstyle="round,pad=0.1")
            fig.patches.append(rect)

        file = self.active_file
        # Header info mostly just for the title of the plots
        header = file.get_header()
        client = header['Client']
        loop = header['Loop']
        linehole = header['LineHole']
        date = header['Date']
        grid = header['Grid']
        timebase = float(header['Timebase'])
        timebase_freq = ((1 / (timebase / 1000)) / 4)
        survey_type = header['SurveyType']
        num_channels = int(header['NumChannels']) + 1  # +1 because the header channel number is only offtime
        units = file.get_tags()['Units']

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
        # if units == 'nT/s':
        #     first_channel_label = "Primary Pulse"
        # elif units == 'pT':
        #     first_channel_label = 'On-time'
        # else:
        #     first_channel_label = 'UNDEF_CHAN'

        # sort the data by station. Station names must first be converted into a number
        data = sorted(self.convert_stations(file.get_data()), key=lambda k: k['Station'])
        components = self.get_components(data)

        log_figs = []
        lin_figs = []

        line_width = 0.5
        line_colour = 'black'
        alpha = 1
        font = "Tahoma"

        # Each component has their own figure
        for component in components:
            logger.info("Plotting component " + component)

            # t1 = time.time()

            # The LIN plot always has 5 axes. LOG only ever has one.
            lin_fig, (ax1, ax2, ax3, ax4, ax5) = plt.subplots(5, 1, figsize=(8.5, 11), sharex=True)
            # Using subplots_adjust instead of tight_layout since it's significantly faster (3 secs -> 0.3 secs)
            # NOTE: Subplots y-axis' are now always at the same distance from the left edge. As a result, the y-axis
            #       labels may get cutoff if the y-axis numbers are too long. With tight_layout the y-axis distance from
            #       the left edge is changed to ensure the y-axis labels are always the same distance away.
            lin_fig.subplots_adjust(left=0.14, bottom=0.05, right=0.960, top=0.9)
            add_rectangle()
            ax6 = ax5.twiny()
            ax6.get_shared_x_axes().join(ax5, ax6)

            component_data = list(filter(lambda d: d['Component'] == component, data))

            profile_data = self.get_profile_data(component_data)

            stations = [station['Station'] for station in component_data]
            x_limit = min(stations), max(stations)
            plt.xlim(x_limit)

            # minor_locator = AutoMinorLocator(5)
            major_locator = FixedLocator(stations)
            x_label_locator = AutoLocator()

            # Much of the slow loading time comes from the following block up to the End of block comment.
            # This is mostly due to matplotlib being oriented towards publication-quality graphics, and not being very
            # well optimized for speed.  If speed is desired in the future we will need to switch to a faster plotting
            # library such as pyqtgraph or vispy.

            # channel_bounds is a list of tuples showing the inclusive bounds of each data plot
            channel_bounds = [None] * 4
            num_channels_per_plot = int(num_channels // 4)
            remainder_channels = int(num_channels % 4)

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
            lin_fig.align_ylabels()

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

                if (y_limits[1] - y_limits[0]) < 2:
                    new_high = math.ceil((y_limits[1] - y_limits[0]) / 2 + 2)
                    new_low = math.floor((y_limits[1] - y_limits[0]) / 2 - 2)
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
            log_fig, ax = plt.subplots(1, 1, figsize=(8.5, 11))
            log_fig.subplots_adjust(left=0.1225, bottom=0.05, right=0.960, top=0.9)
            add_rectangle()
            axlog2 = ax.twiny()
            axlog2.get_shared_x_axes().join(ax, axlog2)
            plt.yscale('symlog', linthreshy=10)
            plt.xlim(x_limit)

            add_titles()

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
