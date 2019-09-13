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



class GeometryEditor:
    """
    Class for editing hole geometry
    """
    def __init__(self):
        self.parser = GeometryParser()

    def get_geometry(self, file):
        segments = self.parser.parse_segments(file)
        if not segments:
            return ''

        return segments

    def get_collar_gps(self, file):
        gps = self.parser.parse_collar_gps(file)

        if not gps:
            return ''

        return gps


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
