import re
import os
import sys
import numpy as np
from scipy import spatial
from math import hypot, sqrt
from os.path import isfile, join
import logging
from PyQt5 import QtCore

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


class StationGPSFile:
    # duplicate_signal = QtCore.pyqtSignal(int)
    # TODO Add signal for duplicates message?
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
        self.sorted_gps_data = self.sort_line()

    def sort_line(self):
        logging.info('Sorting line GPS')
        line_coords = []  # The actual full coordinates
        duplicates = []

        if self.gps_data:
            # Splitting up the coordinates from a string to something usable
            for coord in self.gps_data:
                coord_item = [float(coord[0]), float(coord[1]), float(coord[2]), int(coord[3]), int(coord[4])]
                if coord_item not in line_coords:
                    line_coords.append(coord_item)
                else:
                    duplicates.append(coord_item)

            # if len(duplicates) > 0:
            #     self.duplicate_signal.emit(len(duplicates))

            distances = spatial.distance.cdist(line_coords, line_coords, 'euclidean')
            index_of_max = np.argmax(distances, axis=0)[0]  # Will return the indexes of both ends of the line
            end_point = line_coords[index_of_max]

            def distance(q):
                # Return the Euclidean distance between points p and q.
                p = end_point
                return hypot(p[0] - q[0], p[1] - q[1])

            sorted_coords = sorted(line_coords, key=distance, reverse=True)
            sorted_stations = self.sort_stations(sorted_coords)
            formatted_gps = self.format_gps_data(sorted_stations)

            return formatted_gps
        else:
            return ''

    def sort_stations(self, gps):
        stations = [int(point[-1]) for point in gps]
        order = 'asc' if stations[-1] > stations[0] else 'desc'
        if order is 'asc':
            stations.sort()
        else:
            stations.sort(reverse=True)

        sorted_stations_gps=[]
        for i, number in enumerate(stations):
            gps[i][:-1].append(str(number))
            sorted_stations_gps.append(gps[i])
        return sorted_stations_gps

    def format_gps_data(self, gps_data):
        """
        Adds the P tags and formats the numbers
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
            for row in gps_data:
                formatted_gps.append(format_row(row))

        return formatted_gps

    def get_sorted_gps(self):
        return self.sorted_gps_data

    def get_gps(self):
        return self.format_gps_data(self.gps_data)


class StationGPSParser:
    """
    Class to parse station GPS text files.
    """

    def __init__(self):
        self.formatted_GPS = []
        self.filepath = None
        self.gps_file = StationGPSFile
        self.re_gps = re.compile(
            r'(?P<Easting>\d{4,}\.?\d*)\W{1,3}(?P<Northing>\d{4,}\.?\d*)\W{1,3}(?P<Elevation>\d{1,4}\.?\d*)\W+(?P<Units>0|1)\W+?(?P<Station>-?\d+)')

    def parse(self, filepath):
        # For .txt or .csv files with GPS in them
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
        # For data coming in from PEMInfoWidget/PEMEditor
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
            # return self.gps_file('')
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

    file_names = [f for f in os.listdir(samples_path) if isfile(join(samples_path, f)) and f.lower().endswith('.txt') or f.lower().endswith('.csv')]
    file_paths = []

    for file in file_names:
        file_paths.append(join(samples_path, file))

    gps_file = StationGPSParser

    file = r'C:\Users\Eric\Desktop\7600N.PEM'
    gps_file().parse(file)


if __name__ == '__main__':
    main()
