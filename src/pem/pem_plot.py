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

    def convert_stations(self, data):
        """
        Converts station names into numbers, producing a negative number of the station is S or W
        :param data: EM data section of a PEM file
        :return: List of integer station numbers
        """
        # TODO This probably belongs in pem_parser
        stations = np.array([d['Station'] for d in data])
        # stations = np.unique(stations)

        converted_stations = []

        for station in stations:

            if re.match(r"\d+(S|W)", station):
                converted_stations.append(-int(re.sub(r"\D","",station)))

            else:
                converted_stations.append(int(re.sub(r"\D","",station)))

        return converted_stations

    def get_components(self, data):
        """
        Retrieve the unique components of the survey file
        :param data: EM data section of a PEM file
        :return: List of string components
        """
        unique_components = []

        for reading in data:
            component = reading['Component']

            if component not in unique_components:
                unique_components.append(component)

        return unique_components


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
number_channels = header['NumChannels']
data = file.get_data()
components = pem.get_components(data)
profile_data = {}


for component in components[0]:
    filtered_data = list(filter(lambda d: d['Component'] == component, data))
    # pprint(filtered_data)

    for station in filtered_data:
        # pprint(station['Data'])
        pp = list(map(lambda x: x, station['Data']))
        pprint(pp)




# def profile_data(data):
#     components =
#     profiled_data = []
#     for station in stations:
#         for channel in data:





# fig, (ax1, ax2, ax3, ax4, ax5) = plt.subplots(5, 1, figsize=(8.5, 8))
# pp = []
# data_set = []
#
# for reading in z_data:
#     pp.append(reading['Data'][0])
#     data_set.append(reading['Data'])
#
# ax1.plot(pp)
#
# fig2, ax1 = plt.subplots(1,1, figsize=(8.5, 11))
#
# ax1.plot(z_stations, data_set,'k',linewidth=0.6)
# plt.yscale('symlog')
#
# plt.show()

