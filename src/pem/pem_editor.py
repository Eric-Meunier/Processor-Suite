from src.pem.pem_parser import PEMParser, PEMFile
from matplotlib.figure import Figure
from matplotlib.ticker import (FormatStrFormatter, AutoMinorLocator, MaxNLocator, Locator)
import matplotlib.ticker as ticker
from collections import OrderedDict
import matplotlib.pyplot as plt
import numpy as np
import math
# from PIL import ImageDraw
import re
from log import Logger

logger = Logger(__name__)
# plt.style.use('seaborn-whitegrid')
# plt.style.use('seaborn-white')
# plt.style.use('bmh')
# plt.style.use('ggplot')
plt.style.use('seaborn-paper')


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

    def get_profile_data(self, component_data, num_channels):
        """
        Transforms the data so it is ready to be plotted for LIN and LOG plots
        :param component_data: Data (dict) for a single component (i.e. Z, X, or Y)
        :param num_channels: Int number of channels
        :return: Dictionary where each key is a channel, and the
        values are a list of the EM responses of that channel at each station
        """

        profile_data = {}

        for channel in range(0, num_channels):
            profile_data[channel] = []

            for station in component_data:
                reading = station['Data']
                # TODO Station number should probably be in this dictionary, and will be the X axis of the plots
                station_number = station['Station']

                profile_data[channel].append(reading[channel])

        return profile_data

    def mk_plots(self):

        def mkSubplot(ax, channel_low, channel_high, stations, profile_data):

            offset_slant = 0
            offset_adjust = 1

            if len(stations) > 24:
                offset_adjust = 3
            elif len(stations) > 40:
                offset_adjust = 5

            for k in range(channel_low, (channel_high + 1)):
                ax.plot(stations, profile_data[k], color=line_colour, linewidth=line_width, alpha=alpha)
                if k == 0:
                    annotate_plot("PP", ax, 0, 0)
                else:
                    annotate_plot(str(k), ax, k, offset_slant)
                offset_slant += offset_adjust

        def annotate_plot(str_annotation, obj_plt, channel, offset):

            # This is eventually used for free floating annotations not tied to data points
            # uniquestations = self.active_file.get_unique_stations()
            # xspacing = (abs(max(stations)) - abs(min(stations))) / num_stns
            # yaxes = obj_plt.axes.get_ylim()
            # yspacing = yaxes[1] - yaxes[0]
            # stations = list(sorted(uniquestations))
            num_stns = len(stations)
            spacing = 12
            if num_stns < 12:
                spacing = 8
            elif num_stns < 24:
                spacing = 12
            elif num_stns < 36:
                spacing = 16
            elif num_stns < 48:
                spacing = 24
            elif num_stns < 60:
                spacing = 32
            elif num_stns < 80:
                spacing = 40
            i = offset % len(stations)
            while i < len(stations):
                xy = (stations[i], profile_data[channel][i])
                obj_plt.annotate(str_annotation, xy=xy, textcoords='data', size=7, alpha=alpha)
                i += spacing

        """
        Plot the LIN and LOG plots.
        :return: LIN plot figure and LOG plot figure
        """

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
        elif survey_type.casefold() == 'borehole' or survey_type == 'b-rad':
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

        if units == 'nT/s':
            first_channel_label = "Primary Pulse"
        elif units == 'pT':
            first_channel_label = 'On-time'
        else:
            first_channel_label = 'UNDEF_CHAN'

        # sort the data by station. Station names must first be converted into a number
        data = sorted(self.convert_stations(file.get_data()), key=lambda k: k['Station'])
        components = self.get_components(data)

        log_figs = []
        lin_figs = []

        line_width = 0.5
        line_colour = 'black'
        alpha = 0.8
        # font = "Century Gothic"
        font = "Tahoma"

        # Each component has their own figure
        for component in components:
            logger.info("Plotting component " + component)

            # The LIN plot always has 5 axes. LOG only ever has one.
            lin_fig, (ax1, ax2, ax3, ax4, ax5) = plt.subplots(5, 1, figsize=(8.5, 11), sharex=True)
            ax6 = ax5.twiny()
            ax6.get_shared_x_axes().join(ax5, ax6)

            component_data = list(filter(lambda d: d['Component'] == component, data))

            profile_data = self.get_profile_data(component_data, num_channels)

            stations = [reading['Station'] for reading in component_data]
            x_limit = min(stations), max(stations)
            plt.xlim(x_limit)

            minor_locator = AutoMinorLocator(5)
            # major_formatter = FormatStrFormatter('%d')

            # TODO Much of the slow loading time comes from the following block up to the End of block comment.
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

            # Setting the titles
            plt.figtext(0.555, 0.97, 'Crone Geophysics & Exploration Ltd.',
                        fontname='Century Gothic', alpha=alpha, fontsize=10, ha='center')

            plt.figtext(0.555, 0.955,  survey_type + ' Pulse EM Survey', family='cursive', style='italic',
                        fontname='Century Gothic', alpha=alpha, fontsize=9, ha='center')

            plt.figtext(0.125, 0.945, 'Timebase: ' + str(timebase) + ' ms\n' +
                        'Frequency: ' + str(round(timebase_freq, 2)) + ' Hz',
                        fontname='Century Gothic', alpha=alpha, fontsize=9, va='top')

            plt.figtext(0.555, 0.945, 'Loop: ' + loop + '\n'
                        + s_title + ': ' + linehole + '\n'
                        + component + ' Component',
                        fontname='Century Gothic', alpha=alpha, fontsize=9, va='top', ha='center')

            plt.figtext(0.975, 0.945, client + '\n' + grid + '\n' + date + '\n',
                        fontname='Century Gothic', alpha=alpha, fontsize=9, va='top', ha='right')

            # PLOT PP
            mkSubplot(ax1, 0, 0, stations, profile_data)
            # Plotting each subplot
            mkSubplot(ax2, channel_bounds[0][0], channel_bounds[0][1], stations, profile_data)
            mkSubplot(ax3, channel_bounds[1][0], channel_bounds[1][1], stations, profile_data)
            mkSubplot(ax4, channel_bounds[2][0], channel_bounds[2][1], stations, profile_data)
            mkSubplot(ax5, channel_bounds[3][0], channel_bounds[3][1], stations, profile_data)

            # Formatting the styling of the subplots
            for index, ax in enumerate(lin_fig.axes):

                ax.spines['right'].set_visible(False)
                ax.spines['bottom'].set_visible(False)
                # if index != 5: ax.locator_params(axis='y', nbins=5)
                plt.setp(ax.get_yticklabels(), alpha=alpha, fontname=font)
                plt.setp(ax.spines['left'], alpha=alpha)
                plt.setp(ax.spines['top'], alpha=alpha)
                plt.setp(ax.spines['bottom'], alpha=alpha)

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
                    ax.spines['top'].set_position(('data', 0))
                    ax.xaxis.set_ticks_position('top')
                    ax.xaxis.set_minor_locator(minor_locator)
                    ax.tick_params(axis='x', which='major', direction='inout', length=6)
                    ax.tick_params(axis='x', which='minor', direction='inout', length=3)
                    plt.setp(ax.get_xticklabels(), visible=False)
                # The 6th subplot, only used for station tick labelling
                elif index == 5:
                    ax.spines['top'].set_visible(False)
                    ax.spines["top"].set_position(("axes", -0.1))
                    ax.xaxis.set_ticks_position('bottom')
                    ax.xaxis.set_label_position('bottom')
                    ax.tick_params(axis='x', which='major', direction='out', length=6)
                    plt.setp(ax.get_xticklabels(), visible=True, size=12, alpha=alpha, fontname="Century Gothic")

            # lin_fig.subplots_adjust(hspace=0.25)
            lin_fig.tight_layout(rect=[0.015, 0.025, 1, 0.92])
            # lin_fig.tight_layout(pad=1.5)

            log_fig, axlog1 = plt.subplots(1, 1, figsize=(8.5, 11))
            axlog2 = axlog1.twiny()
            axlog2.get_shared_x_axes().join(axlog1, axlog2)
            # Creating the LOG plot
            mkSubplot(axlog1, 0, channel_bounds[3][1], stations, profile_data)
            # Creating the LOG plot
            plt.yscale('symlog', linthreshy=10)
            plt.xlim(x_limit)

            # Setting the titles
            plt.figtext(0.555, 0.97, 'Crone Geophysics & Exploration Ltd.',
                        fontname='Century Gothic', alpha=alpha, fontsize=10, ha='center')

            plt.figtext(0.555, 0.955,  survey_type + ' Pulse EM Survey', family='cursive', style='italic',
                        fontname='Century Gothic', alpha=alpha, fontsize=9, ha='center')

            plt.figtext(0.125, 0.945, 'Timebase: ' + str(timebase) + ' ms\n' +
                        'Frequency: ' + str(round(timebase_freq, 2)) + ' Hz',
                        fontname='Century Gothic', alpha=alpha, fontsize=9, va='top')

            plt.figtext(0.555, 0.945, 'Loop: ' + loop + '\n'
                        + s_title + ': ' + linehole + '\n'
                        + component + ' Component',
                        fontname='Century Gothic', alpha=alpha, fontsize=9, va='top', ha='center')

            plt.figtext(0.975, 0.945, client + '\n' + grid + '\n' + date + '\n',
                        fontname='Century Gothic', alpha=alpha, fontsize=9, va='top', ha='right')

            axlog1.set_ylabel(first_channel_label + ' to Channel ' + str(num_channels - 1) + '\n(' + str(units) + ')',
                              fontname=font,
                              alpha=alpha)

            # SET LOG PLOT LIMITS
            y_limits = axlog1.get_ylim()
            new_high = 10.0 ** math.ceil(math.log(max(y_limits[1], 11), 10))
            new_low = -1 * 10.0 ** math.ceil(math.log(max(abs(y_limits[0]), 11), 10))
            axlog1.set_ylim(new_low, new_high)
            # SET LOG PLOT LIMITS

            for index, ax in enumerate(log_fig.axes):
                ax.spines['right'].set_visible(False)
                ax.spines['bottom'].set_visible(False)

                if index == 0:
                    ax.spines['top'].set_position(('data', 0))
                    ax.xaxis.set_ticks_position('top')
                    ax.xaxis.set_minor_locator(minor_locator)
                    # ax.yaxis.set_minor_locator(ticker.SymmetricalLogLocator(base=9, linthresh=10))
                    # ax.yaxis.set_minor_locator(AutoMinorLocator())
                    ax.tick_params(axis='x', which='major', direction='inout', length=6)
                    ax.tick_params(axis='x', which='minor', direction='inout', length=3)
                    plt.setp(ax.get_yticklabels(), alpha=alpha, fontname=font)
                    plt.setp(ax.get_xticklabels(), visible=False)
                    ax.set_yticks(ax.get_yticks())

                elif index == 1:
                    ax.spines['top'].set_visible(False)
                    ax.spines["top"].set_position(("axes", -0.1))
                    ax.xaxis.set_ticks_position('bottom')
                    ax.xaxis.set_label_position('bottom')
                    ax.tick_params(axis='x', which='major', direction='out', length=6)
                    plt.setp(ax.get_xticklabels(), visible=True, size=12, alpha=alpha, fontname="Century Gothic")
                    ax.set_yticks(ax.get_yticks())
                # plt.setp(ax.spines['left'], alpha=alpha)
                # plt.setp(ax.spines['top'], alpha=alpha)
                # plt.setp(ax.spines['bottom'], alpha=alpha)

            log_fig.tight_layout(rect=[0.015, 0.025, 1, 0.92])
            # log_fig.tight_layout()
            # TODO End of block

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


# class MinorSymLogLocator(Locator):
#     """
#     Dynamically find minor tick positions based on the positions of
#     major ticks for a symlog scaling.
#     """
#     def __init__(self, linthresh):
#         """
#         Ticks will be placed between the major ticks.
#         The placement is linear for x between -linthresh and linthresh,
#         otherwise its logarithmically
#         """
#         self.linthresh = linthresh
#
#     def __call__(self):
#         'Return the locations of the ticks'
#         majorlocs = self.axis.get_majorticklocs()
#
#         # iterate through minor locs
#         minorlocs = []
#
#         # handle the lowest part
#         for i in xrange(1, len(majorlocs)):
#             majorstep = majorlocs[i] - majorlocs[i-1]
#             if abs(majorlocs[i-1] + majorstep/2) < self.linthresh:
#                 ndivs = 10
#             else:
#                 ndivs = 9
#             minorstep = majorstep / ndivs
#             locs = np.arange(majorlocs[i-1], majorlocs[i], minorstep)[1:]
#             minorlocs.extend(locs)
#
#         return self.raise_if_exceeds(np.array(minorlocs))
#
#     def tick_values(self, vmin, vmax):
#         raise NotImplementedError('Cannot get tick locations for a '
#                                   '%s type.' % type(self))


if __name__ == "__main__":
    # Code to test PEMFileEditor
    editor = PEMFileEditor()
    editor.open_file('CH934ZM.PEM')
    editor.generate_placeholder_plots()
