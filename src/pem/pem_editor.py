from src.pem.pem_parser import PEMParser, PEMFile
from matplotlib.figure import Figure
from matplotlib.ticker import (FormatStrFormatter, AutoMinorLocator, MaxNLocator)
from collections import OrderedDict
import matplotlib.pyplot as plt
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

        # raise NotImplementedError

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

        if units.casefold() == 'nanotesla/sec':
            units = 'nT/s'
        elif units.casefold() == 'picoteslas':
            units = 'pT'

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

        def annotate_plot(self, str_annotation, obj_plt, channel, offset):

            # This is eventually used for free floating annotations not tied to data points
            # uniquestations = self.active_file.get_unique_stations()
            # xspacing = (abs(max(stations)) - abs(min(stations))) / num_stns
            # yaxes = obj_plt.axes.get_ylim()
            # yspacing = yaxes[1] - yaxes[0]
            # stations = list(sorted(uniquestations))
            num_stns = len(stations)
            spacing = 16
            if num_stns < 6:
                spacing = 3
            elif num_stns < 16:
                spacing = 8
            elif num_stns < 32:
                spacing = 16
            elif num_stns < 50:
                spacing = 20
            i = offset % len(stations)
            while i < len(stations):
                xy = (stations[i], profile_data[channel][i])
                obj_plt.annotate(str_annotation, xy=xy, textcoords='data', size=7, alpha=alpha)
                i += spacing

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

            # TODO channel rules are incorrect
            # remaining channels are plotted evenly on the remaining subplots
            num_channels_per_plot = int((num_channels) / 4)

            # TODO 'Primary Pulse' must become 'On-time' for Fluxgate data
            ax1.set_ylabel("Primary Pulse\n(" + units + ")", fontname=font, alpha=alpha)
            ax2.set_ylabel("Channel 1 - " + str(num_channels_per_plot) + "\n(" + units + ")", fontname=font,
                           alpha=alpha)
            ax3.set_ylabel("Channel " + str(num_channels_per_plot + 1) + " - " + str(
                num_channels_per_plot * 2) + "\n(" + units + ")", fontname=font, alpha=alpha)
            ax4.set_ylabel(
                "Channel " + str(num_channels_per_plot * 2 + 1) + " - " + str(
                    num_channels_per_plot * 3) + "\n(" + units + ")", fontname=font, alpha=alpha)
            ax5.set_ylabel(
                "Channel " + str(num_channels_per_plot * 3 + 1) + " - " + str(
                    num_channels_per_plot * 4) + "\n(" + units + ")", fontname=font, alpha=alpha)
            lin_fig.align_ylabels()

            # First channel always has its own plot
            ax1.plot(stations, profile_data[0], 'k', linewidth=line_width, alpha=alpha)
            annotate_plot(self, "PP", ax1, 0,0)

            ax1.set_title('Crone Geophysics & Exploration Ltd.\n'
                          + survey_type + ' Pulse EM Survey      ' + client + '      ' + grid + '\n'
                          + 'Line: ' + linehole + '      Loop: ' + loop + '      Component: ' + component + '\n'
                          + date, fontname=font, alpha=alpha, fontsize=10)

            # Plotting section
            offset_slant = 0

            # For longer profiles you can add a switch case to this
            offset_adjust = 4
            if len(stations) > 24:
                offset_adjust = 6
            elif len(stations) > 40:
                offset_adjust = 10

            for i in range(0, num_channels_per_plot):
                ax2.plot(stations, profile_data[i + 1], color=line_colour, linewidth=0.6, alpha=alpha)
                annotate_plot(self, str(i + 1), ax2, i + 1,offset_slant)

                ax3.plot(stations, profile_data[i + 1 + (num_channels_per_plot * 1)],
                         color=line_colour, linewidth=line_width, alpha=alpha)
                annotate_plot(self, str(i + 1 + (num_channels_per_plot * 1)), ax3, i + 1 + (num_channels_per_plot * 1),offset_slant)

                ax4.plot(stations, profile_data[i + 1 + (num_channels_per_plot * 2)],
                         color=line_colour, linewidth=line_width, alpha=alpha)
                annotate_plot(self, str(i + 1 + (num_channels_per_plot * 2)), ax4, i + 1 + (num_channels_per_plot * 2),offset_slant)

                ax5.plot(stations, profile_data[i + 1 + (num_channels_per_plot * 3)],
                         color=line_colour, linewidth=line_width, alpha=alpha)
                annotate_plot(self, str(i + 1 + (num_channels_per_plot * 3)), ax5, i + 1 + (num_channels_per_plot * 3),offset_slant)
                offset_slant += offset_adjust
            # Formatting the styling of the subplots
            for index, ax in enumerate(lin_fig.axes):
                ax.spines['right'].set_visible(False)
                ax.spines['bottom'].set_visible(False)
                ax.locator_params(axis='y', nbins=5)
                plt.setp(ax.get_yticklabels(), alpha=alpha, fontname=font)
                plt.setp(ax.spines['left'], alpha=alpha)
                plt.setp(ax.spines['top'], alpha=alpha)
                plt.setp(ax.spines['bottom'], alpha=alpha)

                # Creates a minimum Y axis tick range
                ylimits = ax.get_ylim()
                if (ylimits[1] - ylimits[0]) < 4:
                    new_high = int(((ylimits[1]) - ylimits[0]) / 2) + 2
                    new_low = int(((ylimits[1]) - ylimits[0]) / 2) - 2
                    ax.set_ylim(new_low, new_high)

                ax.set_yticks(ax.get_yticks()[::])
                plt.setp(ax.spines['top'], alpha=alpha)
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

                    plt.setp(ax.get_xticklabels(), visible=True, size=12, alpha=alpha, fontname=font)
                    # plt.setp(ax.get_xtick(), alpha=alpha)

            # lin_fig.subplots_adjust(hspace=0.25)
            # lin_fig.tight_layout(rect=[0.015, 0.025, 1, 0.9])
            # try:
            #     plt.gca().add_patch(Rectangle((50,100),40,30,linewidth=1,edgecolor='r',facecolor='none'))
            # except:
            #     print('problem with add_patch')
            #     pass

            lin_fig.tight_layout(pad=1.5)
            try:
                lin_fig.savefig(r'C:\Users\Eric\Desktop\lin.pdf', dpi=lin_fig.dpi)
            except:
                print('lin.pdf open, cannot be saved.')
                pass

            log_fig, ax1 = plt.subplots(1, 1, figsize=(8.5, 11))

            # Creating the LOG plot
            offset_slant = 0
            offset_adjust = 2
            if len(stations) > 24:
                offset_adjust = 4
            elif len(stations) > 40:
                offset_adjust = 6
            k = 0

            for i in range(0, num_channels):
                ax1.plot(stations, profile_data[i], color=line_colour, linewidth=line_width, alpha=alpha)
                if k == 0:  # Plot the PP
                    annotate_plot(self, "PP", ax1, 0, 0)
                else:
                    annotate_plot(self, str(k), ax1, k, offset_slant)
                k += 1
                offset_slant += offset_adjust
            plt.yscale('symlog', linthreshy=10)
            plt.xlim(x_limit)

            ax1.set_title('Crone Geophysics & Exploration Ltd.\n'
                          + survey_type + ' Pulse EM Survey      ' + client + '      ' + grid + '\n'
                          + 'Line: ' + linehole + '      Loop: ' + loop + '      Component: ' + component + '\n'
                          + date, fontname=font, alpha=alpha, fontsize=10)
            ax1.set_ylabel('Primary Pulse to Channel ' + str(num_channels) + '\n(' + str(units) + ')', fontname=font,
                           alpha=alpha)

            for index, ax in enumerate(log_fig.axes):
                ax.spines['right'].set_visible(False)
                ax.spines['bottom'].set_visible(False)
                ax.spines['top'].set_visible(False)
                # ax.locator_params(axis='y', nbins=5)
                plt.setp(ax.get_yticklabels(), alpha=alpha, fontname=font)
                # plt.setp(ax.spines['left'], alpha=alpha)
                # plt.setp(ax.spines['top'], alpha=alpha)
                # plt.setp(ax.spines['bottom'], alpha=alpha)
            # log_fig.tight_layout(rect=[0, 0, 1, 0.825])
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


if __name__ == "__main__":
    # Code to test PEMFileEditor
    editor = PEMFileEditor()
    editor.open_file('CH934ZM.PEM')
    editor.generate_placeholder_plots()
