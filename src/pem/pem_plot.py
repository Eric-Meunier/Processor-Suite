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
        stations = [d['Station'] for d in data]
        for station in stations:
            if re.match("\d+(E|N)", station):
                return int(re.findall("(\d+)\w",station))
            # elif re.match("\d+(S|W)", station):
            #     return int(-(station))
        # return station


    # def remove_ontime(self):
    #     """
    #     Removes the on-time channels from the data.
    #     :return:
    #     """
    #     pprint(self.open_file(path))

pem = PEMFileEditor()
path = r'C:/Users/Eric/PycharmProjects/Crone/sample_files/2400NAv.PEM'

file = pem.open_file(path)
header = file.get_header()
units = file.get_tags()['Units']
channels = header['NumChannels']
data = file.get_data()

x_data = list(filter(lambda d: d['Component'] == 'X', data))
z_data = list(filter(lambda d: d['Component'] == 'Z', data))
z_stations = []
# pprint(pem.convert_stations(z_data))
station  = '10E'
result = station.replace()
pprint(result.group())
pprint(type(result.group()))

# pprint(z_stations)
# stations = np.array(stations)
# pprint(sorted(stations))
# pprint(type(stations))


# for station in stations:
#     # if re.match(r'W|S',station):
#     pprint(station)





#
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
# ax1.plot(stations, data_set,'k',linewidth=0.6)
# plt.yscale('symlog')
#
# # plt.show()

