import re
import os
import sys
import operator
import math
import numpy as np
from pprint import pprint
from functools import reduce
from os.path import isfile, join
import logging

__version__ = '0.0.0'

if getattr(sys, 'frozen', False):
    # If the application is run as a bundle, the pyInstaller bootloader
    # extends the sys module by a flag frozen=True and sets the app
    # path into variable _MEIPASS'.
    application_path = sys._MEIPASS
else:
    application_path = os.path.dirname(os.path.abspath(__file__))

samples_path = os.path.join(application_path, "sample_files")
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s', datefmt='%d-%b-%y %H:%M:%S')


class LoopGPSFile:
    """
    Loop GPS Object.
    :param gps_data: List of lists. Format of the items in the lists doesn't matter
    :param filepath: Filepath of the original text file with the GPS data in it
    """
    def __init__(self, gps_data):
        self.gps_data = gps_data
        self.sorted_gps_data = self.sort_loop()

    def sort_loop(self):
        logging.info('Sorting loop GPS')

        loop_coords_tuples = []  # Used to find the center point
        loop_coords = []  # The actual full coordinates

        if self.gps_data:
            # Splitting up the coordinates from a string to something usable
            for coord in self.gps_data:
                coord_tuple = (float(coord[0]), float(coord[1]))
                coord_item = [float(coord[0]), float(coord[1]), float(coord[2]), coord[3]]
                if coord_tuple not in loop_coords_tuples:
                    loop_coords_tuples.append(coord_tuple)
                if coord_item not in loop_coords:
                    loop_coords.append(coord_item)

            # Finds the center point using the tuples.
            center = list(map(operator.truediv, reduce(lambda x, y: map(operator.add, x, y), loop_coords_tuples), [len(loop_coords_tuples)] * 2))

            # The function used in 'sorted' to figure out how to sort it
            def lambda_func(coord_item):
                coord = (coord_item[0], coord_item[1])
                return (math.degrees(math.atan2(*tuple(map(operator.sub, coord, center))[::-1]))) % 360

            sorted_coords = sorted(loop_coords, key=lambda_func)
            formatted_gps = self.format_gps_data(sorted_coords)

            return formatted_gps

        else:
            return ''

    def format_gps_data(self, gps_data):
        """
        Adds the L tags and formats the numbers. Will also cull the loop if there are too many points
        :param gps_data: List without tags
        :return: List of strings
        """

        def format_row(row):
            for i, item in enumerate(row):
                if i <= 2:
                    row[i] = '{:0.2f}'.format(float(item))
                else:
                    row[i] = str(item)
            return row

        formatted_gps = []
        if len(gps_data) > 0:
            if len(gps_data) > 100:
                gps_data = self.cull_loop(gps_data)
            for row in gps_data:
                if row[-1] == '':
                    row[-1] = 0
                formatted_gps.append(format_row(row))

        return formatted_gps

    def cull_loop(self, loop_gps):
        # Cutting down the loop size to being no more than 100 points
        num_to_cull = len(loop_gps) - 100
        factor = num_to_cull / len(loop_gps)
        n = int(1/factor)
        culled_loop = loop_gps[::n]
        return culled_loop

    def get_sorted_gps(self):
        return self.sorted_gps_data

    def get_gps(self):
        return self.format_gps_data(self.gps_data)


class LoopGPSParser:
    """
    Class to parse station GPS text files.
    """

    def __init__(self):
        self.formatted_GPS = []
        self.filepath = None
        self.gps_file = LoopGPSFile
        self.re_gps = re.compile(
            r'(?P<Easting>\d{4,}\.?\d*)\W{1,3}(?P<Northing>\d{4,}\.?\d*)\W{1,3}(?P<Elevation>\d{1,4}\.?\d*)\W*(?P<Units>0|1)?\W?')

    def open(self, filepath):
        self.filepath = filepath

        with open(self.filepath, 'rt') as in_file:
            self.file = in_file.read()

        self.parse(self.file)

    def parse(self, gps):
        if isinstance(gps, list):
            for i, row in enumerate(gps):
                if isinstance(row, list):
                    row_str = ' '.join(row)
                    gps[i] = row_str
                else:
                    pass
            gps_str = '\n'.join(gps)
        elif gps is None or gps is '':
            return None
        else:
            gps_str = gps
        raw_gps = re.findall(self.re_gps, gps_str)
        raw_gps = list(map(lambda x: list(x), raw_gps))
        return self.gps_file(raw_gps)


def main():
    # app = QApplication(sys.argv)
    # mw = Conder()
    # mw.show()
    # app.exec_()

    file_names = [f for f in os.listdir(samples_path) if
                  isfile(join(samples_path, f)) and f.lower().endswith('.txt') or f.lower().endswith('.csv')]
    file_paths = []

    for file in file_names:
        file_paths.append(join(samples_path, file))

    gps_file = LoopGPSParser

    # for file in file_paths:
    file = r'C:\Users\Eric\Desktop\testing.txt'
    gps_file().open(file)


if __name__ == '__main__':
    main()
