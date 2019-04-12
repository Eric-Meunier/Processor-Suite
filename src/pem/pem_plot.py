from src.pem.pem_parser import PEMParser
from pprint import pprint
from collections import OrderedDict
import matplotlib.pyplot as plt
import numpy as np
import re


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
        :param data: Data from a PEM file
        :return: Data for a PEM file
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
        Retrieve the unique components of the survey file
        :param data: EM data section of a PEM file
        :return: List of components in str format
        """
        unique_components = []

        for reading in data:
            component = reading['Component']

            if component not in unique_components:
                unique_components.append(component)

        return unique_components

    def get_profile_data(self, component_data, num_channels):

        profile_data = {}

        for channel in range(0, num_channels):
            profile_data[channel] = []

            for station in component_data:
                reading = station['Data']
                station_number = station['Station']

                # thing = {station_number: reading[channel]}
                # profile_data[channel].append(thing)

                profile_data[channel].append(reading[channel])


        return profile_data

    # def remove_ontime(self):
    #     """
    #     Removes the on-time channels from the data.
    #     :return:
    #     """
    #     pprint(self.open_file(path))

    def mk_plots(self, path):

        # pem = PEMFileEditor()
        # path = r'C:/Users/Mortulo/PycharmProjects/Crone/sample_files/2400NAv.PEM'

        file = pem.open_file(path)
        header = file.get_header()
        units = file.get_tags()['Units']
        if units == 'nanoTesla/sec':
            units = 'nT/s'
        else:
            units = 'pT'

        num_channels = int(header['NumChannels'])

        data = sorted(pem.convert_stations(file.get_data()), key=lambda k: k['Station'])

        components = pem.get_components(data)


        # Each component has their own figure
        for component in components:
            fig, (ax1, ax2, ax3, ax4, ax5) = plt.subplots(5, 1, figsize=(8.5, 11), sharex=True)
            line_width = 0.7

            component_data = list(filter(lambda d: d['Component'] == component, data))

            profile_data = pem.get_profile_data(component_data, num_channels)

            stations = [reading['Station'] for reading in component_data]

            ax1.plot(stations, profile_data[0], 'k', linewidth=line_width) # First channel has its own plot
            ax1.set_ylabel("Primary Pulse\n("+units+")")
            num_channels_per_plot = int((num_channels-1)/4) # remaining channels are plotted evenly on the remaining subplots

            for i in range(0, num_channels_per_plot):

                ax2.plot(stations, profile_data[i], 'k', linewidth=0.6)
                # ax2.x_axis('off')
                ax2.set_ylabel("Channel 1 - "+ str(num_channels_per_plot)+"\n("+units+")")

                ax3.plot(stations, profile_data[i + (num_channels_per_plot * 1)], 'k', linewidth=line_width)
                ax3.set_ylabel("Channel " + str(num_channels_per_plot+1)+" - "+str(num_channels_per_plot*2)+"\n("+units+")")
                ax4.plot(stations, profile_data[i + (num_channels_per_plot * 2)], 'k', linewidth=line_width)
                ax4.set_ylabel("Channel " + str(num_channels_per_plot*2 + 1) + " - " + str(num_channels_per_plot * 3)+"\n("+units+")")
                ax5.plot(stations, profile_data[i + (num_channels_per_plot * 3)], 'k', linewidth=line_width)
                ax5.set_ylabel("Channel " + str(num_channels_per_plot*3 + 1) + " - " + str(num_channels_per_plot * 4)+"\n("+units+")")

            fig.align_ylabels()
            fig.suptitle('Crone Geophysics & Exploration\n'
                         +header['Client']+' Line: '+header['LineHole'])
            fig.subplots_adjust(hspace=0.25)
            # fig2, ax1 = plt.subplots(1, 1, figsize=(8.5, 11))
            #
            # for i in range(0, num_channels):
            #
            #     ax1.plot(stations, profile_data[i], 'k', linewidth=0.6)
            #     plt.yscale('symlog')

        return fig

pem = PEMFileEditor()
path = r'C:/Users/Mortulo/PycharmProjects/Crone/sample_files/2400NAv.PEM'
pem.mk_plots(path)
plt.show()

