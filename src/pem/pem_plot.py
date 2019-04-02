from src.pem.pem_parser import PEMParser
from pprint import pprint
from collections import OrderedDict
import matplotlib.pyplot as plt
import matplotlib as mpl
import numpy as np


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
channels = header['NumChannels']
data = file.get_data()
# data_keys = [keys for keys, vals in data.items()]
x_data = list(filter(lambda d: d['Component'] == 'X', data))
# pprint(x_data)

for i in x_data:
    pprint(i['Component'])
# for reading in data:
#
#     if reading['Component'] == 'X':
#         x_data.append(reading['Data'])
#
# x_data = np.array(x_data)
# pprint(data[0]['Component'])
# pprint(x_data)
#
#
# x = range(len(pp))
# fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(8.5, 11))
# pem.lin_plotter(ax1, x, pp)
# pem.lin_plotter(ax2, x, ch1)
# pem.lin_plotter(ax3, x, ch2)
#
#
# plt.tight_layout()
# plt.show()
#
# plt.close('all')

