import math
import os
import re
import copy
import pandas as pd
# import geopandas as gpd
from math import hypot
import gpxpy
import utm
from shapely.geometry import asMultiPoint
import numpy as np
import cartopy.crs as ccrs
from scipy import spatial


class BaseGPS:

    def __init__(self):
        self.df = None
        self.crs = None

    def to_string(self, header=False):
        return self.df.to_string(index=False, header=header)

    def to_csv(self, header=False):
        return self.df.to_csv(index=False, header=header)

    def get_extents(self):
        """
        Return the min and max of each dimension of the GPS
        :return: xmin, xmax, ymin, ymax, zmin, zmax
        """
        return self.df['Easting'].min(), self.df['Easting'].max(), \
               self.df['Northing'].min(), self.df['Northing'].max(), \
               self.df['Elevation'].min(), self.df['Elevation'].max()

    def get_units(self):
        units = self.df['Unit'].unique()
        if units == '0' or '2':
            return 'm'
        else:
            return 'ft'

    def to_latlon(self):
        """
        Convert the data frame coordinates to Lat Lon in decimal format
        :return: GPS object
        """
        if any([not self.crs, self.df.empty, not self.crs.is_valid()]):
            return
        elif self.crs.is_latlon():
            return self

        zone_num = self.crs.zone_number
        north = self.crs.north
        latlon_df = self.df.apply(lambda x: utm.to_latlon(x.Easting, x.Northing, zone_num, northern=north),
                                  axis=1)
        self.df['Northing'] = latlon_df.map(lambda x: x[0])
        self.df['Easting'] = latlon_df.map(lambda x: x[1])

        # Create a new CRS for Lat Lon
        latlon_crs = CRS().from_dict({'System': 'Lat/Lon',
                                      'Datum': self.crs.datum})
        self.crs = latlon_crs
        return self

    # def to_nad27(self):
    #     """
    #     Convert the data frame coordinates to NAD 27
    #     :return: GPS object
    #     """
    #     if any([not self.crs, self.df.empty, not self.crs.is_valid()]):
    #         return
    #     elif self.crs.is_nad27():
    #         return self
    # 
    #     if self.crs.is_latlon():
    #         df = copy.deepcopy(self.df)
    #     else:
    #         df = copy.deepcopy(self.to_latlon().df)
    # 
    #     # Create point objects for each coordinate
    #     mpoints = asMultiPoint(df.loc[:, ['Easting', 'Northing']].to_numpy())
    #     gdf = gpd.GeoSeries(list(mpoints), crs={'init': self.crs.get_epsg()})
    # 
    #     # Convert the point objects to NAD 27
    #     nad27_gdf = gdf.to_crs({'init': 'EPSG:4267'})
    #     # Convert the point objects back to UTM coordinates
    #     utm_gdf = nad27_gdf.map(lambda p: utm.from_latlon(p.y, p.x))
    # 
    #     # Assign the converted UTM columns to the data frame
    #     self.df['Easting'], self.df['Northing'] = utm_gdf.map(lambda x: x[0]), utm_gdf.map(lambda x: x[1])
    # 
    #     # Create the new CRS object for NAD 27
    #     nad27_crs = CRS().from_dict({'System': 'UTM',
    #                                  'Zone Number': utm_gdf.loc[0][2],
    #                                  'Zone Letter': utm_gdf.loc[0][3],
    #                                  'Datum': 'NAD 27'})
    #     self.crs = nad27_crs
    #     return self
    # 
    # def to_nad83(self):
    #     """
    #     Convert the data frame coordinates to NAD 83
    #     :return: GPS object
    #     """
    #     if any([not self.crs, self.df.empty, not self.crs.is_valid()]):
    #         return
    #     elif self.crs.is_nad83():
    #         return self
    # 
    #     if self.crs.is_latlon():
    #         df = copy.deepcopy(self.df)
    #     else:
    #         df = copy.deepcopy(self.to_latlon().df)
    # 
    #     # Create point objects for each coordinate
    #     mpoints = asMultiPoint(df.loc[:, ['Easting', 'Northing']].to_numpy())
    #     gdf = gpd.GeoSeries(list(mpoints), crs={'init': self.crs.get_epsg()})
    # 
    #     # Convert the point objects to NAD 83
    #     nad83_gdf = gdf.to_crs({'init': 'EPSG:4269'})
    #     # Convert the point objects back to UTM coordinates
    #     utm_gdf = nad83_gdf.map(lambda p: utm.from_latlon(p.y, p.x))
    # 
    #     # Assign the converted UTM columns to the data frame
    #     self.df['Easting'], self.df['Northing'] = utm_gdf.map(lambda x: x[0]), utm_gdf.map(lambda x: x[1])
    # 
    #     # Create the new CRS object for NAD 27
    #     nad83_crs = CRS().from_dict({'System': 'UTM',
    #                                  'Zone Number': utm_gdf.loc[0][2],
    #                                  'Zone Letter': utm_gdf.loc[0][3],
    #                                  'Datum': 'NAD 83'})
    #     self.crs = nad83_crs
    #     return self
    # 
    # def to_wgs84(self):
    #     """
    #     Convert the data frame coordinates to WGS 84
    #     :return: GPS object
    #     """
    #     if any([not self.crs, self.df.empty, not self.crs.is_valid()]):
    #         return
    #     elif self.crs.is_wgs84():
    #         return self
    # 
    #     if self.crs.is_latlon():
    #         df = copy.deepcopy(self.df)
    #     else:
    #         df = copy.deepcopy(self.to_latlon().df)
    # 
    #     # Create point objects for each coordinate
    #     mpoints = asMultiPoint(df.loc[:, ['Easting', 'Northing']].to_numpy())
    #     gdf = gpd.GeoSeries(list(mpoints), crs={'init': self.crs.get_epsg()})
    # 
    #     # Convert the point objects to WGS 84
    #     wgs84_gdf = gdf.to_crs({'init': 'EPSG:4326'})
    #     # Convert the point objects back to UTM coordinates
    #     utm_gdf = wgs84_gdf.map(lambda p: utm.from_latlon(p.y, p.x))
    # 
    #     # Assign the converted UTM columns to the data frame
    #     self.df['Easting'], self.df['Northing'] = utm_gdf.map(lambda x: x[0]), utm_gdf.map(lambda x: x[1])
    # 
    #     # Create the new CRS object for WGS 84
    #     wgs84_crs = CRS().from_dict({'System': 'UTM',
    #                                  'Zone Number': utm_gdf.loc[0][2],
    #                                  'Zone Letter': utm_gdf.loc[0][3],
    #                                  'Datum': 'WGS 84'})
    #     self.crs = wgs84_crs
    #     return self


class TransmitterLoop(BaseGPS):
    """
    Transmitter loop GPS class
    """

    def __init__(self, loop, cull_loop=True, crs=None):
        """
        :param loop: either a str filepath of a text file or a pandas data frame containing loop GPS
        """
        super().__init__()
        self.crs = crs
        self.parser = GPSParser()
        if isinstance(loop, list) or isinstance(loop, str):
            loop = self.parser.parse_loop_gps(loop)

        self.df = loop.drop_duplicates()
        # self.df = self.df.replace(to_replace='', value=np.nan)  #.dropna()
        self.df.Easting = self.df.Easting.astype(float)
        self.df.Northing = self.df.Northing.astype(float)
        self.df.Elevation = self.df.Elevation.astype(float)
        self.df.Unit = self.df.Unit.astype(str)

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
            print(f"Culling {num_to_cull} coordinates from loop")
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

        if self.df.empty:
            return self.df

        df = copy.deepcopy(self.df)
        cx, cy, cz = self.get_center()
        df['dx'] = pd.Series(df['Easting'] - cx).astype(float)
        df['dy'] = pd.Series(df['Northing'] - cy).astype(float)
        df['angle'] = df.apply(lambda x: get_angle(x['dx'], x['dy']), axis=1)
        df.sort_values(by='angle', inplace=True)
        df.drop(labels=['dx', 'dy', 'angle'], axis=1, inplace=True)
        return df

    def get_center(self):
        """
        Return the centroid of the loop by taking the average of the easting, northing, and elevation.
        :return: tuple: easting, northing, and elevation centroid
        """
        return self.df['Easting'].sum() / self.df.shape[0], \
               self.df['Northing'].sum() / self.df.shape[0], \
               self.df['Elevation'].sum() / self.df.shape[0],

    def get_loop(self, sorted=True, closed=False):
        if sorted:
            df = self.get_sorted_loop()
        else:
            df = self.df

        if not df.empty and closed and not df.duplicated().any():
            df = df.append(df.iloc[0], ignore_index=True)

        return df


class SurveyLine(BaseGPS):
    """
    Survey Line class object representing the survey line GPS information
    """

    def __init__(self, line, crs=None):
        """
        :param line: str filepath of a text file OR a pandas data frame containing line GPS
        """
        super().__init__()
        self.crs = crs
        self.parser = GPSParser()
        if isinstance(line, list) or isinstance(line, str):
            line = self.parser.parse_station_gps(line)

        self.df = line.drop_duplicates()
        self.df.Easting = self.df.Easting.astype(float)
        self.df.Northing = self.df.Northing.astype(float)
        self.df.Elevation = self.df.Elevation.astype(float)
        self.df.Unit = self.df.Unit.astype(str)
        self.df.Station = self.df.Station.astype(str)
        # if self.df.Station.hasnans:
        #     raise ValueError('File is missing station numbers.')

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

        if not df.empty:
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

    def get_line(self, sorted=True):
        if sorted:
            df = self.get_sorted_line()
        else:
            df = self.df

        return df


class BoreholeCollar(BaseGPS):
    """
    Class object representing the collar GPS
    """

    def __init__(self, hole, crs=None):
        """
        :param line: str filepath of a text file OR a pandas data frame containing collar GPS
        """
        super().__init__()
        self.crs = crs
        self.parser = GPSParser()
        if isinstance(hole, list) or isinstance(hole, str):
            hole = self.parser.parse_collar_gps(hole)

        self.df = hole.drop_duplicates()
        # Replace empty cells with NaN and then drop any rows with NaNs
        self.df = self.df.replace(to_replace='', value=np.nan)
        self.df.Easting = self.df.Easting.astype(float)
        self.df.Northing = self.df.Northing.astype(float)
        self.df.Elevation = self.df.Elevation.astype(float)
        self.df.Unit = self.df.Unit.astype(str)

    def get_collar(self):
        df = self.df
        return df


class BoreholeSegments(BaseGPS):
    """
    Class representing the segments section of a borehole in a PEM file
    """

    def __init__(self, segments):
        """
        :param hole: str filepath of a text file OR a pandas data frame containing hole geometry
        """
        super().__init__()
        self.parser = GPSParser()
        if isinstance(segments, list) or isinstance(segments, str):
            segments = self.parser.parse_segments(segments)

        self.df = segments.drop_duplicates()
        self.df.Azimuth = self.df.Azimuth.astype(float)
        self.df.Dip = self.df.Dip.astype(float)
        self.df['Segment length'] = self.df['Segment length'].astype(float)
        self.df.Unit = self.df.Unit.astype(str)
        self.df.Depth = self.df.Depth.astype(float)

    def get_segments(self):
        return self.df


class BoreholeGeometry:
    """
    Class that represents the geometry of a hole, with collar and segments.
    """
    def __init__(self, collar, segments):
        self.collar = collar
        self.segments = segments

    def get_projection(self, num_segments=None):
        """
        Uses the segments to create a 3D projection of a borehole trace. Can be broken up into segments and interpolated.
        :param num_segments: Desired number of segments to be output
        :return: pandas DataFrame: Projected easting, northing, elevation, and relative depth from collar
        """
        # Create the data frame
        projection = pd.DataFrame(columns=['Easting', 'Northing', 'Elevation', 'Relative Depth'])

        if self.collar.df.empty or self.segments.df.empty:
            return projection

        collar = self.collar.get_collar().dropna()
        segments = self.segments.get_segments().dropna()

        # Interpolate the segments
        if num_segments:
            azimuths = segments.Azimuth.to_list()
            dips = segments.Dip.to_list()
            depths = segments.Depth.to_list()

            # Create the interpolated lists
            interp_depths = np.linspace(depths[0], depths[-1], num_segments)
            interp_az = np.interp(interp_depths, depths, azimuths)
            interp_dip = np.interp(interp_depths, depths, dips)
            interp_lens = np.subtract(interp_depths[1:], interp_depths[:-1])
            interp_lens = np.insert(interp_lens, 0, segments.iloc[0]['Segment length'])  # Add the first seg length
            inter_units = np.full(num_segments, segments.Unit.unique()[0])

            # Stack up the arrays and transpose it
            segments = np.vstack(
                (interp_az,
                 interp_dip,
                 interp_lens,
                 inter_units,
                 interp_depths)
            ).T
        else:
            segments = segments.to_numpy()

        eastings = collar.Easting.values
        northings = collar.Northing.values
        depths = collar.Elevation.values
        relative_depth = np.array([0.0])

        for segment in segments:
            azimuth = math.radians(float(segment[0]))
            dip = math.radians(float(segment[1]))
            seg_l = float(segment[2])
            delta_seg_l = seg_l * math.cos(dip)
            dz = seg_l * math.sin(dip)
            dx = delta_seg_l * math.sin(azimuth)
            dy = delta_seg_l * math.cos(azimuth)

            eastings = np.append(eastings, eastings[-1] + dx)
            northings = np.append(northings, northings[-1] + dy)
            depths = np.append(depths, depths[-1] - dz)
            relative_depth = np.append(relative_depth, relative_depth[-1] + seg_l)

        projection.Easting = pd.Series(eastings, dtype=float)
        projection.Northing = pd.Series(northings, dtype=float)
        projection.Elevation = pd.Series(depths, dtype=float)
        projection['Relative Depth'] = pd.Series(relative_depth, dtype=float)
        # if crs:
        #     projection = get_latlon(projection, crs)
        return projection

    def get_collar(self):
        return self.collar.get_collar()

    def get_segments(self):
        return self.segments.get_segments()

    def to_string(self):
        collar_str = self.collar.to_string()
        segment_str = self.segments.to_string()
        return collar_str + '\n' + segment_str

    def to_csv(self):
        collar_csv = self.collar.to_csv()
        segment_csv = self.segments.to_csv()
        return collar_csv + '\n' + segment_csv


class GPSParser:
    """
    Class for parsing loop gps, station gps, and hole geometry
    """

    def __init__(self):
        self.re_station_gps = re.compile(
            r'(?P<Easting>-?\d{4,}\.?\d*)[\s,]{1,3}(?P<Northing>-?\d{4,}\.?\d*)[\s,]{1,3}(?P<Elevation>-?\d{1,4}\.?\d*)[\s,]+(?P<Units>0|1)[\s,]*(?P<Station>-?\w+)?')
        self.re_loop_gps = re.compile(
            r'(?P<Easting>-?\d{4,}\.?\d*)[\s,]+(?P<Northing>-?\d{4,}\.?\d*)[\s,]+(?P<Elevation>-?\d{1,4}\.?\d*)[\s,]*(?P<Units>0|1)?')
        self.re_collar_gps = re.compile(
            r'(?P<Easting>-?\d{4,}\.?\d*)[\s,]+(?P<Northing>-?\d{4,}\.?\d*)[\s,]+(?P<Elevation>-?\d{1,4}\.?\d*)[\s,]+(?P<Units>0|1)?\s*?')
        self.re_segment = re.compile(
            r'(?P<Azimuth>-?\d{0,3}\.?\d*)[\s,]+(?P<Dip>-?\d{1,3}\.?\d*)[\s,]+(?P<SegLength>\d{1,3}\.?\d*)[\s,]+(?P<Units>0|1|2)[\s,]+(?P<Depth>-?\d{1,4}\.?\d*)')

    def open(self, filepath):
        """
        Read and return the contents of a text file
        :param filepath: str: filepath of the file to be read
        :return: str: contents of the text file
        """
        with open(filepath, 'rt') as in_file:
            file = in_file.readlines()
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
            :return: int: converted station as integer number
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
        if os.path.isfile(str(file)):
            contents = self.open(file)
        else:
            contents = file

        # Ensure there is no nested-lists
        while isinstance(contents[0], list):
            contents = contents[0]

        matched_gps = []
        for row in contents:
            match = re.search(self.re_station_gps, row)
            if match:
                match = re.split("[\s,]+", match.group(0))
                matched_gps.append(match)

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
        if os.path.isfile(str(file)):
            contents = self.open(file)
        else:
            contents = file

        # Ensure there is no nested-lists
        while any(isinstance(i, list) for i in contents):
            contents = contents[0]

        matched_gps = []
        for row in contents:
            match = re.search(self.re_loop_gps, row)
            if match:
                match = re.split("[\s,]+", match.group(0))
                matched_gps.append(match)

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
            'Segment length',
            'Unit',
            'Depth'
        ]
        if os.path.isfile(str(file)):
            contents = self.open(file)
        else:
            contents = file

        # Ensure there is no nested-lists
        while any(isinstance(i, list) for i in contents):
            contents = contents[0]

        matched_seg = []
        for row in contents:
            match = re.search(self.re_segment, row)
            if match:
                match = re.split("[\s,]+", match.group(0))
                matched_seg.append(match)

        seg = pd.DataFrame(matched_seg, columns=cols)
        seg[['Azimuth',
                 'Dip',
                 'Segment length',
                 'Depth']] = seg[['Azimuth',
                                      'Dip',
                                      'Segment length',
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
        if os.path.isfile(str(file)):
            contents = self.open(file)
        else:
            contents = file

        # Ensure there is no nested-lists
        while any(isinstance(i, list) for i in contents):
            contents = contents[0]

        matched_gps = []
        for row in contents:
            match = re.search(self.re_collar_gps, row)
            if match:
                match = re.split("[\s,]+", match.group(0))
                matched_gps.append(match)
                break

        gps = pd.DataFrame(matched_gps, columns=cols)
        gps[['Easting', 'Northing', 'Elevation']] = gps[['Easting', 'Northing', 'Elevation']].astype(float)
        gps['Unit'] = gps['Unit'].astype(str)
        return gps


class CRS:
    """
    Class to represent Coordinate Reference Systems (CRS) information
    """
    def __init__(self):
        self.system = None
        self.zone = None
        self.zone_number = None
        self.zone_letter = None
        self.north = None
        self.datum = None

    def from_dict(self, crs_dict):
        keys = crs_dict.keys()

        self.system = crs_dict['System']
        if 'Zone' in keys:
            zone = crs_dict['Zone']
            if zone:
                self.zone_number = int(re.search('\d+', zone).group())
                self.north = True if 'N' in zone.upper() else False
        if 'Zone Number' in keys:
            self.zone_number = crs_dict['Zone Number']
        if 'North' in keys:
            self.north = crs_dict['North']
        if 'Zone Letter' in keys:
            self.zone_letter = crs_dict['Zone Letter']
            if self.zone_letter.lower() in ['c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm']:
                self.north = False
            else:
                self.north = True
        self.datum = crs_dict['Datum']
        return self

    def is_valid(self):
        """
        If the CRS object has all information required for coordinate conversions
        :return: bool
        """
        if self.system:
            if self.system == 'Lat/Lon' and self.datum:
                return True
            elif self.system == 'UTM':
                if all([self.system, self.zone_number, self.north is not None, self.datum]):
                    return True
        return False

    def is_nad27(self):
        if self.datum:
            if self.datum == 'NAD 27':
                return True
            else:
                return False
        else:
            return None

    def is_nad83(self):
        if self.datum:
            if self.datum == 'NAD 83':
                return True
            else:
                return False
        else:
            return None

    def is_wgs84(self):
        if self.datum:
            if self.datum == 'WGS 84':
                return True
            else:
                return False
        else:
            return None

    def is_latlon(self):
        if self.system == 'Lat/Lon':
            return True
        else:
            return False

    def to_cartopy_crs(self):
        """
        Return the cartopy ccrs
        :return: ccrs projection
        """
        if self.system == 'UTM':
            return ccrs.UTM(self.zone_number, southern_hemisphere=not self.north)
        elif self.system == 'Latitude/Longitude':
            return ccrs.Geodetic()

    def get_epsg(self):
        """
        Return the EPSG code for the datum
        :return: str
        """

        if self.datum == 'WGS 84':
            return 'EPSG:4326'
        elif self.datum == 'NAD 27':
            return 'EPSG:4267'
        elif self.datum == 'NAD 83':
            return 'EPSG:4269'
        else:
            return None


class GPXEditor:

    def parse_gpx(self, filepath):
        gpx_file = open(filepath, 'r')
        gpx = gpxpy.parse(gpx_file)
        gps = []
        for waypoint in gpx.waypoints:
            gps.append([waypoint.latitude, waypoint.longitude, waypoint.elevation, '0', waypoint.name])
        return gps

    def get_utm(self, gpx_file, as_string=False):
        """
        Retrieve the GPS from the GPS file in UTM coordinates
        :param gpx_file: str, filepath
        :param as_string: bool, return a string instead of tuple if True
        :return: latitude, longitude, elevation, unit, stn
        """
        gps = self.parse_gpx(gpx_file)
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

            if as_string is True:
                utm_gps.append(' '.join([str(u[0]), str(u[1]), str(elevation), units, stn]))
            else:
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
    pem_files = pg.get_pems(client='Raglan', number=1)
    # gps_parser = GPSParser()
    # gpx_editor = GPXEditor()
    crs = CRS().from_dict({'System': 'UTM', 'Zone': '16 North', 'Datum': 'NAD 83'})
    # file = r'C:\Users\Mortulo\PycharmProjects\PEMPro\src\gps\sample_files\45-1.csv'
    # file = r'C:\Users\Mortulo\PycharmProjects\PEMPro\sample_files\Collar GPS\AF19003 loop and collar.txt'
    # file = r'C:\Users\Mortulo\PycharmProjects\PEMPro\sample_files\Line GPS\LINE 0S.txt'
    # file = r'C:\Users\Mortulo\PycharmProjects\PEMPro\sample_files\Collar GPS\LT19003_collar.txt'
    # file = r'C:\Users\Mortulo\PycharmProjects\PEMPro\sample_files\Loop GPS\PERKOA SW LOOP 1.txt'
    # collar = BoreholeCollar(r'C:\Users\Mortulo\PycharmProjects\PEMPro\sample_files\Collar GPS\LT19003_collar.txt')
    # segments = BoreholeSegments(r'C:\Users\Mortulo\PycharmProjects\PEMPro\sample_files\Segments\718-3759gyro.seg')
    # geometry = BoreholeGeometry(collar, segments)
    # geometry.get_projection(num_segments=1000)
    loop = TransmitterLoop(pem_files[0].loop.df, crs=crs)
    loop.to_nad83()
    # line = SurveyLine(file, name=os.path.basename(file))
    # print(loop.get_sorted_loop(), '\n', loop.get_loop())
    # gps_parser.parse_collar_gps(file)
