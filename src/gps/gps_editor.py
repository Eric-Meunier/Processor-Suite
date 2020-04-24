import logging
import math
import operator
import os
import re
import sys
import copy
import pandas as pd
from functools import reduce
from math import hypot
from os.path import isfile, join
from src.gps.gpx_module import gpxpy
import utm

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


class GPSEditor:
    """
    Class for editing Station, Loop, and Collar gps, and hole geometry segments
    :param gps_data: List of lists. Format of the items in the lists doesn't matter
    """

    def __init__(self):
        self.parser = GPSParser()

    def sort_loop(self, gps):
        loop_gps = self.format_gps(self.parser.parse_loop_gps(copy.copy(gps)))
        if not loop_gps:
            return None
        loop_coords_tuples = []  # Used to find the center point
        loop_coords = []  # The actual full coordinates

        # Splitting up the coordinates from a string to something usable
        for coord in loop_gps:
            coord_tuple = coord[0], coord[1]
            # coord_item = [float(coord[0]), float(coord[1]), float(coord[2]), coord[3]]
            if coord_tuple not in loop_coords_tuples:
                loop_coords_tuples.append(coord_tuple)
            if coord not in loop_coords:
                loop_coords.append(coord)

        # Finds the center point using the tuples.
        center = list(map(operator.truediv, reduce(lambda x, y: map(operator.add, x, y), loop_coords_tuples), [len(loop_coords_tuples)] * 2))

        # The function used in 'sorted' to figure out how to sort it
        def lambda_func(coord_item):
            coord = (coord_item[0], coord_item[1])
            return (math.degrees(math.atan2(*tuple(map(operator.sub, coord, center))[::-1]))) % 360

        sorted_coords = sorted(loop_coords, key=lambda_func)
        if len(sorted_coords) > 100:
            sorted_coords = self.cull_loop(sorted_coords)
        return sorted_coords

    def get_loop_center(self, gps):
        loop_gps = self.format_gps(self.parser.parse_loop_gps(copy.copy(gps)))
        if not loop_gps:
            return None
        loop_coords_tuples = []  # Easting and Northing

        # Splitting up the coordinates from a string to something usable
        for coord in loop_gps:
            coord_tuple = coord[0], coord[1]
            if coord_tuple not in loop_coords_tuples:
                loop_coords_tuples.append(coord_tuple)

        # Finds the center point using the tuples.
        center = list(map(operator.truediv, reduce(lambda x, y: map(operator.add, x, y), loop_coords_tuples),
                          [len(loop_coords_tuples)] * 2))
        return tuple(center)

    def sort_line(self, gps):
        station_gps = self.format_gps(self.parser.parse_station_gps(copy.copy(gps)))
        if not station_gps:
            return None
        line_coords = []
        line_coords_tuples = []

        # Splitting up the coordinates from a string to something usable
        for coord in station_gps:
            coord_tuple = [float(coord[0]), float(coord[1])]
            if coord not in line_coords:
                line_coords.append(coord)
                line_coords_tuples.append(coord_tuple)

        distances = spatial.distance.cdist(line_coords_tuples, line_coords_tuples, 'euclidean')
        index_of_max = np.argmax(distances, axis=0)[0]  # Will return the indexes of both ends of the line
        end_point = line_coords[index_of_max]

        def distance(q):
            # Return the Euclidean distance between points p and q.
            p = end_point
            return hypot(p[0] - q[0], p[1] - q[1])

        sorted_coords = sorted(line_coords, key=distance, reverse=True)
        return sorted_coords

    def format_gps(self, gps):
        """
        Formats the numbers in station and loop gps
        :param gps_data: List without tags
        :return: List of strings
        """
        def format_row(row):
            for i, item in enumerate(row):
                if i <= 2:
                    row[i] = float(item)
                else:
                    row[i] = int(item)
            return row

        if not gps:
            return None

        formatted_gps = []
        for row in gps:
            formatted_gps.append(format_row(row))
        return formatted_gps

    def cull_loop(self, gps):
        """
        Delete evenly-spaced entries to reduce the number to less than 100.
        :param gps: list: rows of loop GPS
        :return: list: Loop GPS with less than 100 items.
        """
        loop_gps = self.parser.parse_loop_gps(copy.copy(gps))
        if loop_gps:
            # Cutting down the loop size to being no more than 100 points
            num_to_cull = len(loop_gps) - 99
            factor = num_to_cull / len(loop_gps)
            n = int(1/factor)
            del loop_gps[n-1::n]
        return loop_gps

    def get_station_gps(self, gps, sorted=True):
        # Doesn't check if it's actually surface line GPS. Can return hole collar inadvertently
        gps = self.format_gps(self.parser.parse_station_gps(gps))
        if sorted:
            return self.sort_line(gps)
        else:
            return gps

    def get_loop_gps(self, gps, sorted=True):
        gps = self.format_gps(self.parser.parse_loop_gps(gps))
        if sorted:
            return self.sort_loop(gps)
        else:
            return self.format_gps(gps)

    def get_geometry(self, file):
        segments = self.parser.parse_segments(file)
        if not segments:
            return []
        return segments

    def get_collar_gps(self, file):
        gps = self.parser.parse_collar_gps(file)
        if not gps:
            return []
        return self.format_gps(gps)


class GPSParser:
    """
    Class for parsing loop gps, station gps, and hole geometry
    """

    def __init__(self):
        # self.re_station_gps = re.compile(
        #     r'(?P<Easting>\d{4,}\.?\d*)\W{1,3}(?P<Northing>\d{4,}\.?\d*)\W{1,3}(?P<Elevation>\d{1,4}\.?\d*)\W+(?P<Units>0|1)\W+?(?P<Station>-?\d+[NESWnesw]?)')
        self.re_station_gps = re.compile(
            r'(?P<Easting>-?\d{4,}\.?\d*)\W{1,3}(?P<Northing>-?\d{4,}\.?\d*)\W{1,3}(?P<Elevation>-?\d{1,4}\.?\d*)\W+(?P<Units>0|1)[\s\t,]*(?P<Station>-?\w+)?')
        self.re_loop_gps = re.compile(
            r'(?P<Easting>-?\d{4,}\.?\d*)\W+(?P<Northing>-?\d{4,}\.?\d*)\W+(?P<Elevation>-?\d{1,4}\.?\d*)\W*(?P<Units>0|1)?.*')
        self.re_collar_gps = re.compile(
            r'(?P<Easting>-?\d{4,}\.?\d*)[\s\t,]+(?P<Northing>-?\d{4,}\.?\d*)[\s\t,]+(?P<Elevation>-?\d{1,4}\.?\d*)[\s\t,]+(?P<Units>0|1)?\s*?')
        self.re_segment = re.compile(
            r'(?P<Azimuth>-?\d{0,3}\.?\d*)[\s\t,]+(?P<Dip>-?\d{1,3}\.?\d*)[\s\t,]+(?P<SegLength>\d{1,3}\.?\d*)[\s\t,]+(?P<Units>0|1|2)[\s\t,]+(?P<Depth>-?\d{1,4}\.?\d*)')

    def open(self, filepath):
        """
        Read and return the contents of a text file
        :param filepath: str: filepath of the file to be read
        :return: str: contents of the text file
        """
        with open(filepath, 'rt') as in_file:
            file = in_file.read()
        return file

    def convert_to_str(self, file):
        if isinstance(file, list):
            for i, row in enumerate(file):
                if isinstance(row, list):
                    row = list(map(lambda x: str(x), row))
                    row_str = ' '.join(row)
                    file[i] = row_str
                else:
                    pass
            gps_str = '\n'.join(file)
        elif file is None or file is '':
            return None
        else:
            gps_str = file
        return gps_str

    def parse_station_gps(self, filepath):
        """
        Parse a text file for station GPS. Station is returned as 0 if no station is found.
        :param filepath: str: filepath of the text file containing GPS data
        :return: Pandas DataFrame of the GPS.
        """

        def convert_station(station):
            """
            Convert station to integer (-ve for S, W, +ve for E, N)
            :param station: str: station str
            :return: str: converted station str
            """
            if station:
                station = re.findall('-?\d+[NSEWnsew]?', station)[0]
                if re.search('[swSW]', station):
                    return int(re.sub('[swSW]', '', station)) * -1
                elif re.search('[neNE]', station):
                    return int(re.sub('[neNE]', '', station))
                else:
                    return int(station)
            else:
                return 0

        cols = [
            'Easting',
            'Northing',
            'Elevation',
            'Unit',
            'Station'
        ]
        contents = self.open(filepath)
        gps_str = self.convert_to_str(contents)
        raw_gps = re.findall(self.re_station_gps, gps_str)
        gps = pd.DataFrame(raw_gps, columns=cols)
        gps.loc[:, 'Easting':'Elevation'] = gps.loc[:, 'Easting':'Elevation'].astype(float)
        gps['Station'] = gps['Station'].map(convert_station)
        return gps

    def parse_loop_gps(self, filepath):
        """
        Parse a text file for loop GPS.
        :param filepath: str: filepath of the text file containing GPS data
        :return: Pandas DataFrame of the GPS.
        """
        cols = [
            'Easting',
            'Northing',
            'Elevation',
            'Unit'
        ]
        contents = self.open(filepath)
        gps_str = self.convert_to_str(contents)
        raw_gps = re.findall(self.re_loop_gps, gps_str)
        gps = pd.DataFrame(raw_gps, columns=cols)
        gps.loc[:, 'Easting':'Elevation'] = gps.loc[:, 'Easting':'Elevation'].astype(float)
        return gps

    def parse_segments(self, file):
        cols = [
            'Azimuth',
            'Dip',
            'Unit',
            'Segment Length',
            'Depth'
        ]
        seg_file_str = self.convert_to_str(file)
        raw_seg_file = re.findall(self.re_segment, seg_file_str)
        raw_seg_file = list(map(lambda x: list(x), raw_seg_file))
        if raw_seg_file:
            return raw_seg_file
        else:
            return []

    def parse_collar_gps(self, file):
        cols = [
            'Easting',
            'Northing',
            'Elevation',
            'Unit'
        ]
        collar_str = self.convert_to_str(file)
        raw_collar_gps = re.findall(self.re_collar_gps, collar_str)
        raw_collar_gps = list(map(lambda x: list(x), raw_collar_gps))
        if raw_collar_gps:
            return [raw_collar_gps[0]]  # Returns the first find
        else:
            return []


class INFParser:

    def get_crs(self, filepath):
        crs = {}
        with open(filepath, 'r') as in_file:
            file = in_file.read()

        crs['Coordinate System'] = re.findall('Coordinate System:\W+(?P<System>.*)', file)[0]
        crs['Coordinate Zone'] = re.findall('Coordinate Zone:\W+(?P<Zone>.*)', file)[0]
        crs['Datum'] = re.findall('Datum:\W+(?P<Datum>.*)', file)[0]

        return crs


class GPXEditor:

    def parse_gpx(self, filepath):
        gpx_file = open(filepath, 'r')
        gpx = gpxpy.parse(gpx_file)
        gps = []
        for waypoint in gpx.waypoints:
            gps.append([waypoint.latitude, waypoint.longitude, waypoint.elevation, '0', waypoint.name])
        return gps

    def get_utm(self, gpx_filepath):
        """
        Retrieve the GPS from the GPS file in UTM coordinates
        :param gpx_filepath: filepath of a GPX file
        :return: List of rows of UTM gps with elevation, units (0 or 1) and comment/name from the GPX waypoint
        """
        gps = self.parse_gpx(gpx_filepath)
        zone = None
        hemisphere = None
        utm_gps = []
        for row in gps:
            lat = row[0]
            lon = row[1]
            elevation = row[2]
            units = row[3]
            name = row[4]
            stn = re.findall('\d+', re.split('-', name)[-1])
            stn = stn[0] if stn else ''
            u = utm.from_latlon(lat, lon)
            zone = u[2]
            letter = u[3]
            hemisphere = 'north' if lat >= 0 else 'south'  # Used in PEMEditor
            utm_gps.append([u[0], u[1], elevation, units, stn])
        return utm_gps, zone, hemisphere

    def get_lat_long(self, gpx_filepath):
        gps = self.parse_gpx(gpx_filepath)
        return gps

    def save_gpx(self, coordinates):
        pass


if __name__ == '__main__':
    from src.pem.pem_getter import PEMGetter
    pg = PEMGetter()
    pem_files = pg.get_pems()
    gps_editor = GPSEditor()
    gps_parser = GPSParser()
    gpx_editor = GPXEditor()
    file = r'C:\Users\Mortulo\PycharmProjects\PEMPro\src\gps\sample_files\45-1.csv'
    # gpx_editor.get_utm(pem_files[0].filepath)
    gps_parser.parse_station_gps(file)
