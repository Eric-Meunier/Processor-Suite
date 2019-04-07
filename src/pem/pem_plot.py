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

    def lin_plotter(self, ax, x, y):
        """
        LIN plots for final PEM data
        :return:
        """
        out = ax.plot(x, y)
        ax.set(xlabel='Station', ylabel='Response (nT/s)')
        ax.grid()
        # plt.grid(True)
        return out

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

    def get_profile_data(self, component_data):
        profile_data = {}

        for channel in range(0, num_channels):
            profile_data[channel] = []

            for station in component_data:
                reading = station['Data']
                # station_number = station['Station']
                # profile_data[channel].append({reading[channel]:station_number})
                profile_data[channel].append(reading)


        return profile_data

    # def remove_ontime(self):
    #     """
    #     Removes the on-time channels from the data.
    #     :return:
    #     """
    #     pprint(self.open_file(path))

pem = PEMFileEditor()
path = r'C:/Users/Mortulo/PycharmProjects/Crone/sample_files/2400NAv.PEM'

file = pem.open_file(path)
header = file.get_header()
units = file.get_tags()['Units']
num_channels = int(header['NumChannels'])

data = sorted(pem.convert_stations(file.get_data()), key=lambda k: k['Station'])
components = pem.get_components(data)

# Each component has their own plot
for component in components:
    fig, (ax1, ax2, ax3, ax4, ax5) = plt.subplots(5, 1, figsize=(8.5, 8))
    component_data = list(filter(lambda d: d['Component'] == component, data))
    channel_data = pem.get_profile_data(component_data)
    pprint(channel_data)

    ax1.plot(channel_data[0]) # First channel has its own plot
    num_channels_per_plot = int((num_channels-1)/4) # remaining channels are plotted evenly on the remaining subplots

    for i in range(0, num_channels_per_plot):
        ax2.plot(channel_data[i])
        ax3.plot(channel_data[i + (num_channels_per_plot * 1)])
        ax4.plot(channel_data[i + (num_channels_per_plot * 2)])
        ax5.plot(channel_data[i + (num_channels_per_plot * 3)])



# fig2, ax1 = plt.subplots(1,1, figsize=(8.5, 11))
#
# ax1.plot(z_stations, data_set,'k',linewidth=0.6)
# plt.yscale('symlog')
#
plt.show()

