from src.pem.pem_parser import PEMParser
from pprint import pprint
from collections import OrderedDict
import matplotlib.pyplot as plt
import numpy as np
import re
# plt.style.use('seaborn-whitegrid')
# plt.style.use('bmh')
# plt.style.use('ggplot')
# plt.style.use('seaborn-white')
# plt.style.use('grayscale')

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
        pprint(self.active_file)

        return self.active_file

    # def convert_stations(self, data):
    #     """
    #     Converts station names into numbers, producing a negative number of the station is S or W
    #     :param data: EM data section of a PEM file
    #     :return: List of integer station numbers
    #     """
    #     # TODO Probably isn't needed, the dictionary based converter below is probably better
    #     stations = np.array([d['Station'] for d in data])
    #     # stations = np.unique(stations)
    #
    #     converted_stations = []
    #
    #     for station in stations:
    #
    #         if re.match(r"\d+(S|W)", station):
    #             converted_stations.append(-int(re.sub(r"\D","",station)))
    #
    #         else:
    #             converted_stations.append(int(re.sub(r"\D","",station)))
    #
    #     return converted_stations

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
        """
        Plot the LIN and LOG plots.
        :return: LIN plot figure and LOG plot figure
        """

        file = self.active_file
        # Header info mostly just for the title of the plots
        header = file.get_header()
        pprint(file.get_header())
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
        data = sorted(editor.convert_stations(file.get_data()), key=lambda k: k['Station'])
        components = editor.get_components(data)

        # Each component has their own figure
        for component in components:
            # The LIN plot always has 5 axes. LOG only ever has one.
            lin_fig, (ax1, ax2, ax3, ax4, ax5) = plt.subplots(5, 1, figsize=(8.5, 11), sharex=True)
            line_width = 0.7

            component_data = list(filter(lambda d: d['Component'] == component, data))

            profile_data = editor.get_profile_data(component_data, num_channels)

            stations = [reading['Station'] for reading in component_data]

            # First channel always has its own plot
            ax1.plot(stations, profile_data[0], 'k', linewidth=line_width)
            # TODO 'Primary Pulse' must become 'On-time' for Fluxgate data
            ax1.set_ylabel("Primary Pulse\n("+units+")")

            # remaining channels are plotted evenly on the remaining subplots
            num_channels_per_plot = int((num_channels-1)/4)

            # Creating the LIN plot
            for i in range(0, num_channels_per_plot):

                ax2.plot(stations, profile_data[i], linewidth=0.6)
                ax2.set_ylabel("Channel 1 - " + str(num_channels_per_plot)+"\n("+units+")")
                ax2.locator_params(axis='y', tight=True, nbins=4)
                # ax2.ticklabel_format(scilimits=(-3,3))

                ax3.plot(stations, profile_data[i + (num_channels_per_plot * 1)], linewidth=line_width)
                ax3.set_ylabel("Channel " + str(num_channels_per_plot+1)+" - "+str(num_channels_per_plot*2)+"\n("+units+")")
                ax4.plot(stations, profile_data[i + (num_channels_per_plot * 2)], linewidth=line_width)
                ax4.set_ylabel("Channel " + str(num_channels_per_plot*2 + 1) + " - " + str(num_channels_per_plot * 3)+"\n("+units+")")
                ax5.plot(stations, profile_data[i + (num_channels_per_plot * 3)], linewidth=line_width)
                ax5.set_ylabel("Channel " + str(num_channels_per_plot*3 + 1) + " - " + str(num_channels_per_plot * 4)+"\n("+units+")")

            lin_fig.align_ylabels()
            lin_fig.suptitle('Crone Geophysics & Exploration Ltd.\n'
                         + survey_type + ' Pulse EM Survey      ' + client + '      ' + grid + '\n'
                         + 'Line: ' + linehole + '      Loop: ' + loop + '      Component: ' + component + '\n'
                         + date)
            lin_fig.subplots_adjust(hspace=0.25)
            lin_fig.tight_layout(rect=[0, 0, 1, 0.915])

            log_fig, ax1 = plt.subplots(1, 1, figsize=(8.5, 11))

            # Creating the LOG plot
            for i in range(0, num_channels):

                ax1.plot(stations, profile_data[i], linewidth=0.6)

            plt.yscale('symlog')
            log_fig.suptitle('Crone Geophysics & Exploration Ltd.\n'
                 + survey_type + ' Pulse EM Survey      ' + client + '      ' + grid + '\n'
                 + 'Line: ' + linehole + '      Loop: ' + loop + '      Component: ' + component + '\n'
                 + date)
            ax1.set_ylabel('Primary Pulse to Channel ' + str(num_channels-1) + '\n(' + str(units) + ')')
            ax1.set_xlabel('Station')
            log_fig.tight_layout(rect=[0, 0, 1, 0.915])

        return lin_fig, log_fig


if __name__ == "__main__":

    # Code to test PEMFileEditor
    path = r'C:/Users/Eric/PycharmProjects/Crone/sample_files/7600N.PEM'
    editor = PEMFileEditor()
    editor.open_file(path)
    editor.mk_plots()

    plt.show()



