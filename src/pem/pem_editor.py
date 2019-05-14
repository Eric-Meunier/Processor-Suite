from src.pem.pem_parser import PEMParser, PEMFile
from matplotlib.figure import Figure
from matplotlib.ticker import (FormatStrFormatter, AutoMinorLocator, MaxNLocator)
from collections import OrderedDict

import matplotlib.pyplot as plt
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
                data[index]['Station'] = (-int(re.sub(r"\D","",station)))

            else:
                data[index]['Station'] = (int(re.sub(r"\D","",station)))

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
        def annotate_plot(self, str_annotation,obj_plt,channel):
            i = 0
            spacing = 6
            while i < len(stations):
                xy = (stations[i],profile_data[channel][i])
                obj_plt.annotate(str_annotation,xy=xy,textcoords='data', size=7)
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
        survey_type = header['SurveyType']

        if survey_type.casefold() == 's-coil':
            survey_type = 'Surface Induction'
        elif survey_type.casefold() == 'borehole' or survey_type == 'b-rad':
            survey_type = 'Borehole Induction'
        elif survey_type.casefold() == 's-flux':
            survey_type = 'Surface Fluxgate'

        num_channels = int(header['NumChannels'])
        units = file.get_tags()['Units']

        if units == 'nanoTesla/sec':
            units = 'nT/s'
        else:
            units = 'pT'

        # sort the data by station. Station names must first be converted into a number
        data = sorted(self.convert_stations(file.get_data()), key=lambda k: k['Station'])
        components = self.get_components(data)

        log_figs = []
        lin_figs = []

        # Each component has their own figure
        for component in components:
            logger.info("Plotting component " + component)
            # The LIN plot always has 5 axes. LOG only ever has one.
            lin_fig, (ax1, ax2, ax3, ax4, ax5, ax6) = plt.subplots(6, 1, figsize=(8.5, 11), sharex=True)
            line_width = 0.5
            line_colour = 'black'

            component_data = list(filter(lambda d: d['Component'] == component, data))

            profile_data = self.get_profile_data(component_data, num_channels)

            stations = [reading['Station'] for reading in component_data]
            plt.xlim(min(stations), max(stations))

            minor_locator = AutoMinorLocator(5)
            major_formatter = FormatStrFormatter('%d')

            # TODO 'Primary Pulse' must become 'On-time' for Fluxgate data
            ax1.set_ylabel("Primary Pulse\n("+units+")")

            # remaining channels are plotted evenly on the remaining subplots
            num_channels_per_plot = int((num_channels-1)/4)

            ax2.set_ylabel("Channel 1 - " + str(num_channels_per_plot) + "\n(" + units + ")")
            ax3.set_ylabel("Channel " + str(num_channels_per_plot + 1) + " - " + str(
                num_channels_per_plot * 2) + "\n(" + units + ")")
            ax4.set_ylabel(
                "Channel " + str(num_channels_per_plot * 2 + 1) + " - " + str(num_channels_per_plot * 3) + "\n(" + units + ")")
            ax5.set_ylabel(
                "Channel " + str(num_channels_per_plot * 3 + 1) + " - " + str(num_channels_per_plot * 4) + "\n(" + units + ")")

            ax5.set_xlabel("Station", size=12)


            for index, ax in enumerate(lin_fig.axes):
                if index != 5:
                    ax.spines['right'].set_visible(False)
                    ax.spines['bottom'].set_visible(False)

                    ax.spines['top'].set_position(('data', 0))
                    ax.xaxis.set_ticks_position('top')
                    ax.xaxis.set_minor_locator(minor_locator)
                    ax.tick_params(axis='x', which='major', direction='inout', length=6)
                    plt.setp(ax.get_xticklabels(), visible=False)


            # ax5.setxticklabels()
            # ax5.xaxis.set_major_formatter(major_formatter)

            # ax5.xaxis.set_ticks_position('top')
            # ax5.tick_params(axis='x', which='major', direction='out', length=5, width=1.5, labelsize=12,
            #                 bottom = True)
            # ax5.set_ticklabels(stations)
            # ax5.xaxis.set_label_coords(0.5,-0.225)
            # ax5.axhline(y=0, xmin=0, xmax=1, color='black', linewidth=0.6)

            lin_fig.align_ylabels()
            lin_fig.suptitle('Crone Geophysics & Exploration Ltd.\n'
                         + survey_type + ' Pulse EM Survey      ' + client + '      ' + grid + '\n'
                         + 'Line: ' + linehole + '      Loop: ' + loop + '      Component: ' + component + '\n'
                         + date)
            # lin_fig.subplots_adjust(hspace=0.25)
            lin_fig.tight_layout(rect=[0, 0.02, 1, 0.9])

            # First channel always has its own plot
            ax1.plot(stations, profile_data[0], 'k', linewidth=line_width)
            annotate_plot(self,"PP",ax1,0)

            # Creating the LIN plot
            j = 2
            for i in range(0, num_channels_per_plot):

                ax2.plot(stations, profile_data[i], color=line_colour, linewidth=0.6)
                annotate_plot(self, str(i+1), ax2, i)
                # ax2.locator_params(axis='y', tight=True, nbins=4)
                # ax2.ticklabel_format(scilimits=(-3,3))
                j += 2

                ax3.plot(stations, profile_data[i + (num_channels_per_plot * 1)], color=line_colour, linewidth=line_width)
                annotate_plot(self,str(i + (num_channels_per_plot * 1)+1),ax3,i + (num_channels_per_plot * 1))
                j += 2

                ax4.plot(stations, profile_data[i + (num_channels_per_plot * 2)], color=line_colour, linewidth=line_width)
                annotate_plot(self,str(i + (num_channels_per_plot * 2)+1),ax4,i + (num_channels_per_plot * 2))
                j += 2

                ax5.plot(stations, profile_data[i + (num_channels_per_plot * 3)], color=line_colour, linewidth=line_width)
                annotate_plot(self,str(i + (num_channels_per_plot * 3)+1),ax5,i + (num_channels_per_plot * 3))

            # TODO Much of the slow loading time comes from the following block up to the End of block comment.
            # This is mostly due to matplotlib being oriented towards publication-quality graphics, and not being very
            # well optimized for speed.  If speed is desired in the future we will need to switch to a faster plotting
            # library such as pyqtgraph or vispy.

            log_fig, ax1 = plt.subplots(1, 1, figsize=(8.5, 11))

            # Creating the LOG plot
            for i in range(0, num_channels):

                ax1.plot(stations, profile_data[i], color=line_colour, linewidth=0.6)
                # annotate_plot(self, str(i + 1), ax1, i + 1)

            plt.yscale('symlog', linthreshy=10)
            log_fig.suptitle('Crone Geophysics & Exploration Ltd.\n'
                 + survey_type + ' Pulse EM Survey      ' + client + '      ' + grid + '\n'
                 + 'Line: ' + linehole + '      Loop: ' + loop + '      Component: ' + component + '\n'
                 + date)
            ax1.set_ylabel('Primary Pulse to Channel ' + str(num_channels-1) + '\n(' + str(units) + ')')
            ax1.set_xlabel('Station')
            log_fig.tight_layout(rect=[0, 0, 1, 0.825])
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