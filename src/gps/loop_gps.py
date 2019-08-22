import re
import os
import sys
import operator
import math
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
    def __init__(self, gps_data, filepath=None):
        self.filepath = filepath
        if self.filepath:
            self.filename = os.path.basename(self.filepath)  # With extension
            self.file_dir = os.path.dirname(self.filepath)

        self.gps_data = gps_data
        self.sorted_gps_data = self.sort_loop()

    def sort_loop(self):

        loop_coords_tuples = []  # Used to find the center point
        loop_coords = []  # The actual full coordinates

        # Splitting up the coordinates from a string to something usable
        for coord in self.gps_data:
            coord_tuple = (float(coord[0]), float(coord[1]))
            coord_item = [float(coord[0]), float(coord[1]), float(coord[2]), coord[3]]
            loop_coords_tuples.append(coord_tuple)
            loop_coords.append(coord_item)

        # Finds the center point using the tuples.
        center = list(map(operator.truediv, reduce(lambda x, y: map(operator.add, x, y), loop_coords_tuples), [len(loop_coords_tuples)] * 2))

        # The function used in 'sorted' to figure out how to sort it
        def lambda_func(coord_item):
            coord = (coord_item[0], coord_item[1])
            return (-135 - math.degrees(math.atan2(*tuple(map(operator.sub, coord, center))[::-1]))) % 360

        sorted_coords = sorted(loop_coords, key=lambda_func, reverse=True)
        formatted_gps = self.format_gps_data(sorted_coords)
        pprint(formatted_gps)

        return formatted_gps

    def format_gps_data(self, gps_data):

        def format_row(row):
            for i, item in enumerate(row):
                if i < 3:
                    row[i] = '{:0.2f}'.format(float(item))
                else:
                    row[i] = str(item)
            return row

        count = 0
        formatted_gps = []

        if len(gps_data) > 0:
            for row in gps_data:
                if row[-1] == '':
                    row[-1] = 0
                formatted_row = format_row(row)
                formatted_gps.append("<L" + '{num:02d}'.format(num=count) + "> " + ' '.join(formatted_row))
                count += 1

        return formatted_gps

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
            r'(?P<Easting>\d{3,}\.?\d*)\W+(?P<Northing>\d{3,}\.?\d*)\W+(?P<Elevation>\d{1,4}\.?\d*)\W*(?P<Units>0|1)?\W?')

    def parse(self, filepath):
        self.filepath = filepath

        with open(self.filepath, 'rt') as in_file:
            self.file = in_file.read()

        self.raw_gps = re.findall(self.re_gps, self.file)
        self.raw_gps = list(map(lambda x: list(x), self.raw_gps))

        if self.raw_gps:
            return self.gps_file(self.raw_gps, filepath=self.filepath)
        else:
            return ''

    def parse_text(self, gps):
        if isinstance(gps, list):
            ' '.join(gps)
        gps_str = '\n'.join(gps)
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
    gps_file().parse(file)


if __name__ == '__main__':
    main()
