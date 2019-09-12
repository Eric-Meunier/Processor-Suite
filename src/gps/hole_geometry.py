import logging
import os
import re
import sys
from math import hypot
from os.path import isfile, join

import numpy as np
from scipy import spatial

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


# class GeometryFile:  # Not a thing
#     """
#     Borehole segment object.
#     # :param gps_data: List of lists. Format of the items in the lists doesn't matter
#     # :param filepath: Filepath of the original text file with the GPS data in it
#     """
#
#     def __init__(self, gps_data):
#         self.gps_data = gps_data
#         self.sorted_gps_data = self.sort_line()
#
#     def sort_line(self):
#         logging.info('Sorting line GPS')
#         line_coords = []
#         duplicates = []
#
#         if self.gps_data:
#             # Splitting up the coordinates from a string to something usable
#             for coord in self.gps_data:
#                 coord_item = [float(coord[0]), float(coord[1]), float(coord[2]), str(coord[3]), str(coord[4])]
#                 if coord_item not in line_coords:
#                     line_coords.append(coord_item)
#                 else:
#                     duplicates.append(coord_item)
#
#             distances = spatial.distance.cdist(line_coords, line_coords, 'euclidean')
#             index_of_max = np.argmax(distances, axis=0)[0]  # Will return the indexes of both ends of the line
#             end_point = line_coords[index_of_max]
#
#             def distance(q):
#                 # Return the Euclidean distance between points p and q.
#                 p = end_point
#                 return hypot(p[0] - q[0], p[1] - q[1])
#
#             sorted_coords = sorted(line_coords, key=distance, reverse=True)
#             # sorted_stations = self.sort_stations(sorted_coords)
#             formatted_gps = self.format_gps_data(sorted_coords)
#
#             return formatted_gps
#         else:
#             return ''
#
#     def sort_stations(self, gps):
#         stations = [int(point[-1]) for point in gps]
#         order = 'asc' if stations[-1] > stations[0] else 'desc'
#         if order is 'asc':
#             stations.sort()
#         else:
#             stations.sort(reverse=True)
#
#         sorted_stations_gps = []
#         for i, number in enumerate(stations):
#             gps[i][:-1].append(str(number))
#             sorted_stations_gps.append(gps[i])
#         return sorted_stations_gps
#
#     def format_gps_data(self, gps_data):
#         """
#         Adds the P tags and formats the numbers
#         :param gps_data: List without tags
#         :return: List of strings
#         """
#
#         def format_row(row):
#             for i, item in enumerate(row):
#                 if i <= 2:
#                     row[i] = '{:0.2f}'.format(float(item))
#                 else:
#                     row[i] = str(item)
#             return row
#
#         formatted_gps = []
#         if len(gps_data) > 0:
#             for row in gps_data:
#                 formatted_gps.append(format_row(row))
#
#         return formatted_gps
#
#     def get_sorted_gps(self):
#         return self.sorted_gps_data
#
#     def get_gps(self):
#         return self.format_gps_data(self.gps_data)


class GeometryParser:
    """
    Class to parse borehole segment files.
    """

    def __init__(self):
        self.formatted_file = []
        # self.geometry_file = GeometryFile
        self.re_collar_gps = re.compile(
            r'(?P<Easting>\d{4,}\.?\d*)[\s\t,]+(?P<Northing>\d{4,}\.?\d*)[\s\t,]+(?P<Elevation>\d{1,4}\.?\d*)[\s\t,]+(?P<Units>0|1)?\s*?')
        self.re_segment = re.compile(
            r'(?P<Azimuth>\d{1,3}\.?\d*)[\s\t,]+(?P<Dip>\d{1,3}\.?\d*)[\s\t,]+(?P<SegLength>\d{1,3}\.?\d*)[\s\t,]+(?P<Units>0|1|2)[\s\t,]+(?P<Depth>\d{1,4}\.?\d*)')

    def open(self, filepath):  # Not really needed as PEMEditor open_gps does this anyway
        with open(filepath, 'rt') as in_file:
            file = in_file.read()
        return file

    def parse_segments(self, file):
        if isinstance(file, list):
            for i, row in enumerate(file):  # Convert to str for re purposes
                if isinstance(row, list):
                    row_str = ' '.join(row)
                    file[i] = row_str
                else:
                    pass
            seg_file_str = '\n'.join(file)
        elif file is None or file is '':
            return None
        else:
            seg_file_str = file
        raw_seg_file = re.findall(self.re_segment, seg_file_str)
        raw_seg_file = list(map(lambda x: list(x), raw_seg_file))
        if raw_seg_file:
            return raw_seg_file
        else:
            return None

    def parse_collar_gps(self, file):
        if isinstance(file, list):
            for i, row in enumerate(file):  # Convert to str for re purposes
                if isinstance(row, list):
                    row_str = ' '.join(row)
                    file[i] = row_str
                else:
                    pass
            collar_str = '\n'.join(file)
        elif file is None or file is '':
            return None
        else:
            collar_str = file
        raw_collar_gps = re.findall(self.re_collar_gps, collar_str)
        raw_collar_gps = list(map(lambda x: list(x), raw_collar_gps))
        if raw_collar_gps:
            return raw_collar_gps[0]  # Returns the first find
        else:
            return None


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

    # gps_file = SegmentParser
    #
    # file = r'C:\Users\Eric\Desktop\7600N.PEM'
    # gps_file().open(file)


if __name__ == '__main__':
    main()
