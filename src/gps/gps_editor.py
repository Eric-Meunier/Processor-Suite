import logging
import math
import operator
import os
import re
import sys
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
        # # logging.info('GPSEditor')
        self.parser = GPSParser()

    def sort_loop(self, gps_data):
        # logging.info('GPSEditor - Sorting loop GPS')
        loop_gps = self.parser.parse_loop_gps(gps_data)
        if not loop_gps:
            return None
        loop_coords_tuples = []  # Used to find the center point
        loop_coords = []  # The actual full coordinates

        # Splitting up the coordinates from a string to something usable
        for coord in loop_gps:
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
        if len(sorted_coords) > 100:
            sorted_coords = self.cull_loop(sorted_coords)
        formatted_gps = self.format_gps(sorted_coords)
        return formatted_gps

    def get_loop_center(self, gps):
        loop_gps = self.parser.parse_loop_gps(gps)
        if not loop_gps:
            return None
        # logging.info('GPSEditor - Retrieving loop GPS center point')
        loop_coords_tuples = []  # Easting and Northing

        # Splitting up the coordinates from a string to something usable
        for coord in loop_gps:
            coord_tuple = (float(coord[0]), float(coord[1]))
            if coord_tuple not in loop_coords_tuples:
                loop_coords_tuples.append(coord_tuple)

        # Finds the center point using the tuples.
        center = list(map(operator.truediv, reduce(lambda x, y: map(operator.add, x, y), loop_coords_tuples),
                          [len(loop_coords_tuples)] * 2))
        return center

    def sort_line(self, gps):
        # logging.info('GPSEditor - Sorting line GPS')
        station_gps = self.parser.parse_station_gps(gps)
        if not station_gps:
            return None
        line_coords = []
        line_coords_tuples = []
        duplicates = []

        # Splitting up the coordinates from a string to something usable
        for coord in station_gps:
            coord_item = [float(coord[0]), float(coord[1]), float(coord[2]), str(coord[3]), str(coord[4])]
            coord_tuple = [float(coord[0]), float(coord[1])]
            if coord_item not in line_coords:
                line_coords.append(coord_item)
                line_coords_tuples.append(coord_tuple)
            else:
                duplicates.append(coord_item)

        distances = spatial.distance.cdist(line_coords_tuples, line_coords_tuples, 'euclidean')
        index_of_max = np.argmax(distances, axis=0)[0]  # Will return the indexes of both ends of the line
        end_point = line_coords[index_of_max]

        def distance(q):
            # Return the Euclidean distance between points p and q.
            p = end_point
            return hypot(p[0] - q[0], p[1] - q[1])

        sorted_coords = sorted(line_coords, key=distance, reverse=True)
        formatted_gps = self.format_gps(sorted_coords)
        return formatted_gps

    # def sort_stations(self, gps):
    #     stations = [int(point[-1]) for point in gps]
    #     order = 'asc' if stations[-1] > stations[0] else 'desc'
    #     if order is 'asc':
    #         stations.sort()
    #     else:
    #         stations.sort(reverse=True)
    #
    #     sorted_stations_gps = []
    #     for i, number in enumerate(stations):
    #         gps[i][:-1].append(str(number))
    #         sorted_stations_gps.append(gps[i])
    #     return sorted_stations_gps

    def format_gps(self, gps):
        """
        Formats the numbers in station and loop gps
        :param gps_data: List without tags
        :return: List of strings
        """
        # logging.info('GPSEditor - Formatting GPS')

        def format_row(row):
            for i, item in enumerate(row):
                if i <= 2:
                    row[i] = '{:0.2f}'.format(float(item))
                else:
                    row[i] = str(int(item))
            return row

        if not gps:
            return None

        formatted_gps = []
        for row in gps:
            formatted_gps.append(format_row(row))
        return formatted_gps

    def cull_loop(self, gps):
        # logging.info('GPSEditor - Culling loop GPS')

        loop_gps = self.parser.parse_loop_gps(gps)
        if loop_gps:
            # Cutting down the loop size to being no more than 100 points
            num_to_cull = len(loop_gps) - 99
            factor = num_to_cull / len(loop_gps)
            n = int(1/factor)
            del loop_gps[n-1::n]
        return loop_gps

    def get_station_gps(self, gps):
        # lDoesn't check if it's actually surface line GPS. Can return hole collar inadvertently
        return self.format_gps(self.parser.parse_station_gps(gps))

    def get_loop_gps(self, gps):
        return self.format_gps(self.parser.parse_loop_gps(gps))

    def get_sorted_station_gps(self, gps):
        return self.sort_line(gps)

    def get_sorted_loop_gps(self, gps):
        return self.sort_loop(gps)

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
        # # logging.info('GPSParser')
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

    def open(self, filepath):  # Not needed, done in PEMEditor.
        self.filepath = filepath

        with open(self.filepath, 'rt') as in_file:
            self.file = in_file.read()

        return self.file

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

    def parse_station_gps(self, gps):
        gps_str = self.convert_to_str(gps)
        raw_gps = re.findall(self.re_station_gps, gps_str)
        raw_gps = list(map(lambda x: list(x), raw_gps))

        if raw_gps:
            for i, row in enumerate(raw_gps):
                station = row.pop(4)
                if station:
                    station = re.findall('-?\d+[NSEWnsew]?', station)[0]
                    if re.search('[swSW]', station):
                        raw_gps[i].append('-' + str(re.sub('[swSW]', '', station)))
                    elif re.search('[neNE]', station):
                        raw_gps[i].append(str(re.sub('[neNE]', '', station)))
                    else:
                        raw_gps[i].append(station)
                else:
                    raw_gps[i].append(9999)
            return raw_gps
        else:
            return []

    def parse_loop_gps(self, gps):
        gps_str = self.convert_to_str(gps)
        raw_gps = re.findall(self.re_loop_gps, gps_str)
        raw_gps = list(map(lambda x: list(x), raw_gps))

        if raw_gps:
            return raw_gps
        else:
            return []

    def parse_segments(self, file):
        seg_file_str = self.convert_to_str(file)
        raw_seg_file = re.findall(self.re_segment, seg_file_str)
        raw_seg_file = list(map(lambda x: list(x), raw_seg_file))
        if raw_seg_file:
            return raw_seg_file
        else:
            return []

    def parse_collar_gps(self, file):
        collar_str = self.convert_to_str(file)
        raw_collar_gps = re.findall(self.re_collar_gps, collar_str)
        raw_collar_gps = list(map(lambda x: list(x), raw_collar_gps))
        if raw_collar_gps:
            return [raw_collar_gps[0]]  # Returns the first find
        else:
            return []


class INFParser:

    def get_crs(self, filepath):
        # logging.info('INFParser')
        crs = {}
        with open(filepath, 'r') as in_file:
            file = in_file.read()

        crs['Coordinate System'] = re.findall('Coordinate System:\W+(?P<System>.*)', file)[0]
        crs['Coordinate Zone'] = re.findall('Coordinate Zone:\W+(?P<Zone>.*)', file)[0]
        crs['Datum'] = re.findall('Datum:\W+(?P<Datum>.*)', file)[0]

        return crs


class GPXEditor:

    def parse_gpx(self, filepath):
        # logging.info('GPXEditor')
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
        # logging.info('GPXEditor - Converting GPX file coordinates to UTM')
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
            # zone = math.floor((lon+180)/6) + 1  # Calculate the zone number
            # myProj = Proj(f"+proj=utm +zone={zone},\+{hemisphere} +ellps=WGS84 +datum=WGS84 +units=m +no_defs")  # north for north hemisphere
            # UTMx, UTMy = myProj(lon, lat)
            utm_gps.append([u[0], u[1], elevation, units, stn])
        return utm_gps, zone, hemisphere

    def get_lat_long(self, gpx_filepath):
        gps = self.parse_gpx(gpx_filepath)
        return gps

    def save_gpx(self, coordinates):
        pass


def main():
    from src.pem.pem_getter import PEMGetter
    pg = PEMGetter()
    pem_files = pg.get_pems()
    gps_editor = GPSEditor()
    gps_parser = GPSParser()
    gpx_editor = GPXEditor()

    gpx_editor.get_utm(pem_files[0].filepath)

if __name__ == '__main__':
    main()
