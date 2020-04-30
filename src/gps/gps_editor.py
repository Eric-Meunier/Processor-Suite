import math
import os
import re
import copy
import pandas as pd
from math import hypot
from src.gps.gpx_module import gpxpy
import utm
import numpy as np
from scipy import spatial


class TransmitterLoop:
    """
    Transmitter loop GPS class
    """

    def __init__(self, loop, name=None, cull_loop=True):
        """
        :param loop: either a str filepath of a text file or a pandas data frame containing loop GPS
        """
        self.parser = GPSParser()
        if isinstance(loop, str):
            loop = self.parser.parse_loop_gps(loop)

        self.df = loop.drop_duplicates()
        self.name = name
        if cull_loop:
            self.cull_loop()

    def cull_loop(self):
        """
        Delete evenly-spaced entries to reduce the number to less than 100.
        :param gps: list: rows of loop GPS
        :return: list: Loop GPS with less than 100 items.
        """
        if self.df.shape[0] > 100:
            # Cutting down the loop size to being no more than 100 points
            num_to_cull = self.df.shape[0] - 99
            print(f"Culling {num_to_cull} coordinates from loop {self.name}")
            factor = num_to_cull / self.df.shape[0]
            n = int(1/factor)
            self.df = self.df[self.df.index % n != 0]
            self.df.reset_index(drop=True, inplace=True)
        return self.df

    def get_sorted_loop(self):
        """
        Sorts the loop to be counter-clockwise.
        :return: pandas DataFrame of sorted loop coordinates
        """
        def get_angle(dx, dy):
            return (math.atan2(dy, dx) + 2.0 * math.pi) % (2.0 * math.pi)

        df = copy.deepcopy(self.df)
        cx, cy = self.get_center()
        df['dx'] = pd.Series(df['Easting'] - cx).astype(float)
        df['dy'] = pd.Series(df['Northing'] - cy).astype(float)
        df['angle'] = df.apply(lambda x: get_angle(x['dx'], x['dy']), axis=1)
        df.sort_values(by='angle', inplace=True)
        df.drop(labels=['dx', 'dy', 'angle'], axis=1, inplace=True)
        return df

    def get_center(self):
        """
        Return the centroid of the loop by taking the average of the easting and the northing.
        :return: tuple: easting centroid and northing centroid
        """
        return self.df['Easting'].sum() / self.df.shape[0], self.df['Northing'].sum() / self.df.shape[0]

    def get_loop(self):
        return self.df


class SurveyLine:
    """
    Survey Line class object representing the survey line GPS information
    """

    def __init__(self, line, name=None):
        """
        :param line: str filepath of a text file OR a pandas data frame containing line GPS
        """
        self.parser = GPSParser()
        if isinstance(line, str):
            line = self.parser.parse_station_gps(line)

        self.df = line.drop_duplicates()
        self.name = name

    def get_sorted_line(self):
        """
        Sorts the points in the survey line by distance. Chooses one end of the line, and uses that point to
        calculate the distance of each other point from that point, then sorts.
        :return: pandas DataFrame of the sorted line GPS
        """

        def calc_distance(point, end_point):
            # Return the Euclidean distance between points p and q.
            p = end_point
            q = point
            return hypot(p[0] - q[0], p[1] - q[1])

        df = copy.deepcopy(self.df)

        # Create a 2D grid of calculated distances between each point
        distances = spatial.distance.cdist(df.loc[:, 'Easting':'Northing'], df.loc[:, 'Easting':'Northing'],
                                           metric='euclidean')
        # Take the index of the largest distance
        index_of_max = np.argmax(distances, axis=0)[0]  # Will return the indexes of both ends of the line
        end_point = df.iloc[index_of_max]

        # Calculate the distance from each point to the chosen end_point and add it as a column
        df['Distance'] = df.apply(
            lambda x: calc_distance((x.Easting, x.Northing), end_point),
            axis=1).astype(float)

        # Sort by the distance column, then remove it
        df.sort_values(by='Distance', inplace=True, ascending=False)
        df.drop('Distance', axis=1, inplace=True)
        return df

    def get_line(self):
        return self.df


class BoreholeCollar:
    """
    Borehole collar class object representing the collar GPS
    """

    def __init__(self, hole, name=None):
        """
        :param line: str filepath of a text file OR a pandas data frame containing collar GPS
        """
        self.parser = GPSParser()
        if isinstance(hole, str):
            hole = self.parser.parse_collar_gps(hole)

        self.df = hole.drop_duplicates()
        self.name = name

    def get_collar(self):
        return self.df


class BoreholeGeometry:
    """
    Borehole geometry class object representing the segments section of a borehole in a PEM file
    """

    def __init__(self, hole, name=None):
        """
        :param line: str filepath of a text file OR a pandas data frame containing hole geometry
        """
        self.parser = GPSParser()
        if isinstance(hole, str):
            hole = self.parser.parse_segments(hole)

        self.df = hole.drop_duplicates()
        self.name = name

    def get_segments(self):
        return self.df


# class GPSEditor:
#     """
#     Class for editing Station, Loop, and Collar gps, and hole geometry segments
#     :param gps_data: List of lists. Format of the items in the lists doesn't matter
#     """
#
#     def __init__(self):
#         self.parser = GPSParser()
#
#     def sort_loop(self, gps):
#         loop_gps = self.format_gps(self.parser.parse_loop_gps(copy.copy(gps)))
#         if not loop_gps:
#             return None
#         loop_coords_tuples = []  # Used to find the center point
#         loop_coords = []  # The actual full coordinates
#
#         # Splitting up the coordinates from a string to something usable
#         for coord in loop_gps:
#             coord_tuple = coord[0], coord[1]
#             # coord_item = [float(coord[0]), float(coord[1]), float(coord[2]), coord[3]]
#             if coord_tuple not in loop_coords_tuples:
#                 loop_coords_tuples.append(coord_tuple)
#             if coord not in loop_coords:
#                 loop_coords.append(coord)
#
#         # Finds the center point using the tuples.
#         center = list(map(operator.truediv, reduce(lambda x, y: map(operator.add, x, y), loop_coords_tuples), [len(loop_coords_tuples)] * 2))
#
#         # The function used in 'sorted' to figure out how to sort it
#         def lambda_func(coord_item):
#             coord = (coord_item[0], coord_item[1])
#             return (math.degrees(math.atan2(*tuple(map(operator.sub, coord, center))[::-1]))) % 360
#
#         sorted_coords = sorted(loop_coords, key=lambda_func)
#         if len(sorted_coords) > 100:
#             sorted_coords = self.cull_loop(sorted_coords)
#         return sorted_coords
#
#     def get_loop_center(self, gps):
#         loop_gps = self.format_gps(self.parser.parse_loop_gps(copy.copy(gps)))
#         if not loop_gps:
#             return None
#         loop_coords_tuples = []  # Easting and Northing
#
#         # Splitting up the coordinates from a string to something usable
#         for coord in loop_gps:
#             coord_tuple = coord[0], coord[1]
#             if coord_tuple not in loop_coords_tuples:
#                 loop_coords_tuples.append(coord_tuple)
#
#         # Finds the center point using the tuples.
#         center = list(map(operator.truediv, reduce(lambda x, y: map(operator.add, x, y), loop_coords_tuples),
#                           [len(loop_coords_tuples)] * 2))
#         return tuple(center)
#
#     def sort_line(self, gps):
#         station_gps = self.format_gps(self.parser.parse_station_gps(copy.copy(gps)))
#         if not station_gps:
#             return None
#         line_coords = []
#         line_coords_tuples = []
#
#         # Splitting up the coordinates from a string to something usable
#         for coord in station_gps:
#             coord_tuple = [float(coord[0]), float(coord[1])]
#             if coord not in line_coords:
#                 line_coords.append(coord)
#                 line_coords_tuples.append(coord_tuple)
#
#         distances = spatial.distance.cdist(line_coords_tuples, line_coords_tuples, 'euclidean')
#         index_of_max = np.argmax(distances, axis=0)[0]  # Will return the indexes of both ends of the line
#         end_point = line_coords[index_of_max]
#
#         def distance(q):
#             # Return the Euclidean distance between points p and q.
#             p = end_point
#             return hypot(p[0] - q[0], p[1] - q[1])
#
#         sorted_coords = sorted(line_coords, key=distance, reverse=True)
#         return sorted_coords
#
#     def format_gps(self, gps):
#         """
#         Formats the numbers in station and loop gps
#         :param gps_data: List without tags
#         :return: List of strings
#         """
#         def format_row(row):
#             for i, item in enumerate(row):
#                 if i <= 2:
#                     row[i] = float(item)
#                 else:
#                     row[i] = int(item)
#             return row
#
#         if not gps:
#             return None
#
#         formatted_gps = []
#         for row in gps:
#             formatted_gps.append(format_row(row))
#         return formatted_gps
#
#     def cull_loop(self, gps):
#         """
#         Delete evenly-spaced entries to reduce the number to less than 100.
#         :param gps: list: rows of loop GPS
#         :return: list: Loop GPS with less than 100 items.
#         """
#         loop_gps = self.parser.parse_loop_gps(copy.copy(gps))
#         if loop_gps:
#             # Cutting down the loop size to being no more than 100 points
#             num_to_cull = len(loop_gps) - 99
#             factor = num_to_cull / len(loop_gps)
#             n = int(1/factor)
#             del loop_gps[n-1::n]
#         return loop_gps
#
#     def get_station_gps(self, gps, sorted=True):
#         # Doesn't check if it's actually surface line GPS. Can return hole collar inadvertently
#         gps = self.format_gps(self.parser.parse_station_gps(gps))
#         if sorted:
#             return self.sort_line(gps)
#         else:
#             return gps
#
#     def get_loop_gps(self, gps, sorted=True):
#         gps = self.format_gps(self.parser.parse_loop_gps(gps))
#         if sorted:
#             return self.sort_loop(gps)
#         else:
#             return self.format_gps(gps)
#
#     def get_geometry(self, file):
#         segments = self.parser.parse_segments(file)
#         if not segments:
#             return []
#         return segments
#
#     def get_collar_gps(self, file):
#         gps = self.parser.parse_collar_gps(file)
#         if not gps:
#             return []
#         return self.format_gps(gps)


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

    def parse_station_gps(self, file):
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
                return np.nan

        cols = [
            'Easting',
            'Northing',
            'Elevation',
            'Unit',
            'Station'
        ]
        if os.path.isfile(file):
            contents = self.open(file)
        else:
            contents = file
        matched_gps = re.findall(self.re_station_gps, contents)
        gps = pd.DataFrame(matched_gps, columns=cols)
        gps[['Easting', 'Northing', 'Elevation']] = gps[['Easting', 'Northing', 'Elevation']].astype(float)
        gps['Unit'] = gps['Unit'].astype(str)
        gps['Station'] = gps['Station'].map(convert_station)
        return gps

    def parse_loop_gps(self, file):
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
        if os.path.isfile(file):
            contents = self.open(file)
        else:
            contents = file
        matched_gps = re.findall(self.re_loop_gps, contents)
        gps = pd.DataFrame(matched_gps, columns=cols)
        gps[['Easting', 'Northing', 'Elevation']] = gps[['Easting', 'Northing', 'Elevation']].astype(float)
        gps['Unit'] = gps['Unit'].astype(str)
        return gps

    def parse_segments(self, file):
        """
        Parse a text file for geometry segments.
        :param filepath: str: filepath of the text file containing segments data
        :return: Pandas DataFrame of the segments.
        """
        cols = [
            'Azimuth',
            'Dip',
            'Segment Length',
            'Unit',
            'Depth'
        ]
        if os.path.isfile(file):
            contents = self.open(file)
        else:
            contents = file
        matched_seg = re.findall(self.re_segment, contents)
        seg = pd.DataFrame(matched_seg, columns=cols)
        seg[['Azimuth',
                 'Dip',
                 'Segment Length',
                 'Depth']] = seg[['Azimuth',
                                      'Dip',
                                      'Segment Length',
                                      'Depth']].astype(float)
        seg['Unit'] = seg['Unit'].astype(str)
        return seg

    def parse_collar_gps(self, file):
        """
        Parse a text file for collar GPS. Returns the first match found.
        :param filepath: str: filepath of the text file containing GPS data
        :return: Pandas DataFrame of the GPS.
        """
        cols = [
            'Easting',
            'Northing',
            'Elevation',
            'Unit'
        ]
        if os.path.isfile(file):
            contents = self.open(file)
        else:
            contents = file
        matched_gps = re.search(self.re_collar_gps, contents).group(0).split()
        gps = pd.DataFrame([matched_gps], columns=cols)
        gps[['Easting', 'Northing', 'Elevation']] = gps[['Easting', 'Northing', 'Elevation']].astype(float)
        gps['Unit'] = gps['Unit'].astype(str)
        return gps


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
    # from src.pem.pem_getter import PEMGetter
    # pg = PEMGetter()
    # pem_files = pg.get_pems()
    # gps_parser = GPSParser()
    # gpx_editor = GPXEditor()

    file = r'C:\Users\Mortulo\PycharmProjects\PEMPro\src\gps\sample_files\45-1.csv'
    # file = r'C:\Users\Mortulo\PycharmProjects\PEMPro\sample_files\Collar GPS\AF19003 loop and collar.txt'
    # file = r'C:\Users\Mortulo\PycharmProjects\PEMPro\sample_files\Line GPS\LINE 0S.txt'
    # file = r'C:\Users\Mortulo\PycharmProjects\PEMPro\sample_files\Collar GPS\LT19003_collar.txt'
    loop = TransmitterLoop(file, name=os.path.basename(file))
    # line = SurveyLine(file, name=os.path.basename(file))
    # print(loop.get_sorted_loop(), '\n', loop.get_loop())
    # gps_parser.parse_collar_gps(file)
