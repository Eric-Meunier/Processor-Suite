import re
import os
import sys
from os.path import isfile, join
import logging
from src.pem.pem_parser import PEMParser

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


class GPSFile:
    def __init__(self, filepath, gps_data):
        self.filepath = filepath
        self.filename = os.path.basename(self.filepath)  # With extension
        self.file_dir = os.path.dirname(self.filepath)

        self.gps_data = gps_data

    def sort_stations(self):
        pass

    def save_file(self):
        pass


class StationGPSParser:
    """
    Class to parse station GPS text files.
    """

    def __init__(self):
        self.formatted_GPS = []
        self.filepath = None

        self.re_gps = re.compile(
            r'(?P<Easting>\d{3,}\.?\d+)\s+(?P<Northing>\d{3,}\.\d+)\s+(?P<Elevation>\d{3,}\.\d+)\s+(?P<Units>0|1)\s+(?P<Station>\d+)')

        # self.parse()

    def parse(self, filepath):
        self.filepath = filepath

        with open(self.filepath, 'rt') as in_file:
            self.file = in_file.read()

        self.raw_gps = re.findall(self.re_gps, self.file)

        count = 0

        if self.raw_gps:
            gps_file = GPSFile
            for row in self.raw_gps:
                self.formatted_GPS.append("<P"+'{num:02d}'.format(num=count)+"> "+' '.join(row))
                count += 1
            return gps_file(filepath, self.formatted_GPS)
        else:
            return None


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

    for file in file_paths:
        gps_file(file)


if __name__ == '__main__':
    main()
