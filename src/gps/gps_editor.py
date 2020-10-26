import copy
import logging
import re
from src.logger import Log
from pathlib import Path

import geopandas as gpd
import gpxpy
import math
import numpy as np
import pandas as pd
import utm
from math import hypot
from pyproj import CRS
from scipy import spatial
from shapely.geometry import asMultiPoint

logger = logging.getLogger(__name__)


class BaseGPS:

    def __init__(self):
        self.pem_file = None
        self.df = gpd.GeoDataFrame()
        self.crs = None
        self.errors = pd.DataFrame()
        self.error_msg = ''

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

    def get_errors(self):
        return self.errors

    def to_latlon(self):
        """
        Convert the data frame coordinates to Lat Lon in decimal format
        :return: GPS object
        """
        df = self.df.copy().iloc[0:0]  # Copy and clear the data frame
        if not self.crs:
            logger.warning('No CRS')
            self.df = df
            return self
        elif self.df.empty:
            logger.info('GPS dataframe is empty.')
            self.df = df
            return self

        # Create point objects for each coordinate
        mpoints = asMultiPoint(self.df.loc[:, ['Easting', 'Northing']].to_numpy())
        gdf = gpd.GeoSeries(list(mpoints), crs=self.crs)

        # Convert the point objects to WGS 1984 Lat/Lon
        epsg_code = f'4326'  # Geographic

        converted_gdf = gdf.to_crs(f"EPSG:{epsg_code}")

        # Assign the converted UTM columns to the data frame
        self.df['Easting'], self.df['Northing'] = converted_gdf.map(lambda p: p.x), converted_gdf.map(lambda p: p.y)
        self.df.dropna(inplace=True)
        self.crs = CRS.from_epsg(epsg_code)
        return self

    def to_nad27(self):
        """
        Convert the data frame coordinates to NAD 1927.
        :return: GPS object
        """
        df = self.df.copy().iloc[0:0]  # Copy and clear the data frame
        if not self.crs:
            logger.warning('No CRS')
            self.df = df
            return self
        elif self.df.empty:
            logger.warning('GPS dataframe is empty.')
            self.df = df
            return self

        # Create point objects for each coordinate
        mpoints = asMultiPoint(self.df.loc[:, ['Easting', 'Northing']].to_numpy())
        gdf = gpd.GeoSeries(list(mpoints), crs=self.crs)

        # Convert the point objects to NAD 1927
        if self.crs.utm_zone:
            zone_number = int(self.crs.utm_zone[:-1])
            epsg_code = f'267{zone_number:02d}'  # Projected
        else:
            epsg_code = f'4267'  # Geographic

        converted_gdf = gdf.to_crs(f"EPSG:{epsg_code}")

        # Assign the converted UTM columns to the data frame
        self.df['Easting'], self.df['Northing'] = converted_gdf.map(lambda p: p.x), converted_gdf.map(lambda p: p.y)
        self.df.dropna(inplace=True)
        self.crs = CRS.from_epsg(epsg_code)
        return self

    def to_nad83(self):
        """
        Convert the data frame coordinates to NAD 1983.
        :return: GPS object
        """
        df = self.df.copy().iloc[0:0]  # Copy and clear the data frame
        if not self.crs:
            logger.warning('No CRS.')
            self.df = df
            return self
        elif self.df.empty:
            logger.warning('GPS dataframe is empty.')
            self.df = df
            return self

        # Create point objects for each coordinate
        mpoints = asMultiPoint(self.df.loc[:, ['Easting', 'Northing']].to_numpy())
        gdf = gpd.GeoSeries(list(mpoints), crs=self.crs)

        # Convert the point objects to NAD 1983
        if self.crs.utm_zone:
            zone_number = int(self.crs.utm_zone[:-1])
            epsg_code = f'269{zone_number:02d}'  # Projected
        else:
            epsg_code = f'4269'  # Geographic

        converted_gdf = gdf.to_crs(f"EPSG:{epsg_code}")

        # Assign the converted UTM columns to the data frame
        self.df['Easting'], self.df['Northing'] = converted_gdf.map(lambda p: p.x), converted_gdf.map(lambda p: p.y)
        self.df.dropna(inplace=True)
        self.crs = CRS.from_epsg(epsg_code)
        return self

    def to_wgs84(self):
        """
        Convert the data frame coordinates to WGS 1984.
        :return: GPS object
        """
        df = self.df.copy().iloc[0:0]  # Copy and clear the data frame
        if not self.crs:
            logger.warning('No CRS.')
            self.df = df
            return self
        elif self.df.empty:
            logger.warning('GPS dataframe is empty.')
            self.df = df
            return self

        # Create point objects for each coordinate
        mpoints = asMultiPoint(self.df.loc[:, ['Easting', 'Northing']].to_numpy())
        gdf = gpd.GeoSeries(list(mpoints), crs=self.crs)

        # Convert the point objects to WGS 1984
        if self.crs.utm_zone:
            zone_number = int(self.crs.utm_zone[:-1])
            if self.crs.utm_zone[-1] == 'N':
                prefix = '326'
            else:
                prefix = '327'

            epsg_code = f'{prefix}{zone_number:02d}'  # Projected
        else:
            epsg_code = f'4326'  # Geographic

        converted_gdf = gdf.to_crs(f"EPSG:{epsg_code}")

        # Assign the converted UTM columns to the data frame
        self.df['Easting'], self.df['Northing'] = converted_gdf.map(lambda p: p.x), converted_gdf.map(lambda p: p.y)
        self.df.dropna(inplace=True)
        self.crs = CRS.from_epsg(epsg_code)
        return self

    def to_epsg(self, epsg_code):
        """
        Convert the data frame coordinates to WGS 1984.
        :return: GPS object
        """
        df = self.df.copy().iloc[0:0]  # Copy and clear the data frame
        if not self.crs:
            logger.warning('No CRS.')
            self.df = df
            return self
        elif self.df.empty:
            logger.warning('GPS dataframe is empty.')
            self.df = df
            return self

        # Create point objects for each coordinate
        mpoints = asMultiPoint(self.df.loc[:, ['Easting', 'Northing']].to_numpy())
        gdf = gpd.GeoSeries(list(mpoints), crs=self.crs)

        try:
            converted_gdf = gdf.to_crs(f"EPSG:{epsg_code}")
        except Exception as e:
            logger.error(f"Could not convert to {epsg_code}: {str(e)}.")
            return None
        else:
            # Assign the converted UTM columns to the data frame
            self.df['Easting'], self.df['Northing'] = converted_gdf.map(lambda p: p.x), converted_gdf.map(lambda p: p.y)
            self.df.dropna(inplace=True)
            self.crs = CRS.from_epsg(epsg_code)
            return self


class TransmitterLoop(BaseGPS):
    """
    Transmitter loop GPS class
    """

    def __init__(self, loop, cull_loop=True, crs=None):
        """
        :param loop: Union (str, dataframe, list) filepath of a text file OR a data frame/list containing loop GPS
        """
        super().__init__()
        self.crs = crs
        self.df, self.errors, self.error_msg = self.parse_loop_gps(loop)

        # if cull_loop:
        #     self.cull_loop()

    @staticmethod
    # @Log()
    def parse_loop_gps(file):
        """
        Parse a text file or data frame for loop GPS.
        :param file: Union (str filepath, dataframe, list), text containing GPS data
        :return: DataFrame of the GPS.
        """

        def has_na(series):
            """
            Return True if the row has any NaN, else return False.
            :param series: pandas Series
            :return: bool
            """
            if series.isnull().values.any():
                return True
            else:
                return False

        empty_gps = pd.DataFrame(columns=[
            'Easting',
            'Northing',
            'Elevation',
            'Unit',
        ])

        error_msg = ''

        if isinstance(file, list):
            # split_file = [r.strip().split() for r in file]
            gps = pd.DataFrame(file)
        elif isinstance(file, pd.DataFrame):
            gps = file
        elif Path(str(file)).is_file():
            file = open(file, 'rt').readlines()
            split_file = [r.strip().split() for r in file]
            gps = pd.DataFrame(split_file)
        elif file is None:
            logger.warning(f"Empty file passed.")
            return empty_gps, pd.DataFrame(), 'Empty file passed.'
        else:
            logger.error(f"Invalid input: {file}.")
            raise TypeError(f'{file} is not a valid input for loop GPS parsing.')

        gps = gps.astype(str)
        # Remove P tags and units columns
        cols_to_drop = []
        for i, col in gps.dropna(axis=0).iteritems():
            # Remove P tag column
            if col.map(lambda x: x.startswith('<')).all():
                cols_to_drop.append(i)
            # Remove units column
            elif col.map(lambda x: x == '0').all():
                cols_to_drop.append(i)

        gps = gps.drop(cols_to_drop, axis=1)

        if len(gps.columns) < 3:
            error_msg = f"{len(gps.columns)} column(s) of values were found instead of 3."
            logger.warning(error_msg)
            # print("Fewer than 3 columns were found.")
            return empty_gps, gps, error_msg
        elif len(gps.columns) > 3:
            gps = gps.drop(gps.columns[3:], axis=1)

        gps.columns = range(gps.shape[1])  # Reset the columns

        # Find any rows where there is a NaN
        bad_rows = gps.apply(has_na, axis=1)
        error_gps = gps.loc[bad_rows].copy()

        # Add the units column
        gps.insert(3, 'Unit', '0')

        cols = {
            0: 'Easting',
            1: 'Northing',
            2: 'Elevation',
        }
        # Add the column names to the two data frames
        gps.rename(columns=cols, inplace=True)
        error_gps.rename(columns=cols, inplace=True)

        # Remove the NaNs from the good data frame
        gps = gps.dropna(axis=0).drop_duplicates()
        gps[['Easting', 'Northing', 'Elevation']] = gps[['Easting', 'Northing', 'Elevation']].astype(float)
        gps['Unit'] = gps['Unit'].astype(str)

        return gps, error_gps, error_msg

    def cull_loop(self):
        """
        Delete evenly-spaced entries to reduce the number to less than 100.
        :param gps: list: rows of loop GPS
        :return: list: Loop GPS with less than 100 items.
        """
        if self.df.shape[0] > 100:
            # Cutting down the loop size to being no more than 100 points
            num_to_cull = self.df.shape[0] - 99
            logger.info(f"Culling {num_to_cull} coordinates from loop")
            factor = num_to_cull / self.df.shape[0]
            n = int(1/factor)
            self.df = self.df[self.df.index % n != 0]
            self.df.reset_index(drop=True, inplace=True)

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

    def get_loop(self, sorted=False, closed=False):
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
        :param line: Union (str, dataframe, list) filepath of a text file OR a data frame/list containing line GPS
        """
        super().__init__()
        self.crs = crs
        self.df, self.errors, self.error_msg = self.parse_station_gps(line)

    @staticmethod
    # @Log()
    def parse_station_gps(file):
        """
        Parse a text file or data frame for station GPS.
        :param file: Union (str filepath, dataframe, list), text containing GPS data
        :return: DataFrame of the GPS.
        """

        def convert_station(station):
            """
            Converts a single station name into a number, negative if the stations was S or W
            :return: Integer station number
            """
            # Ensure station is a string
            station = str(station).upper()
            if re.match(r"-?\d+(S|W)", station):
                station = (-int(re.sub(r"[SW]", "", station)))
            else:
                station = (int(re.sub(r"[EN]", "", station)))
            return station

        def has_na(series):
            """
            Return True if the row has any NaN, else return False.
            :param series: pandas Series
            :return: bool
            """
            if series.isnull().values.any():
                return True
            else:
                return False

        empty_gps = pd.DataFrame(columns=[
            'Easting',
            'Northing',
            'Elevation',
            'Unit',
            'Station'
        ])

        error_msg = ''

        if isinstance(file, list):
            # split_file = [r.strip().split() for r in file]
            gps = pd.DataFrame(file)
        elif isinstance(file, pd.DataFrame):
            gps = file
        elif Path(str(file)).is_file():
            file = open(file, 'rt').readlines()
            split_file = [r.strip().split() for r in file]
            gps = pd.DataFrame(split_file)
        elif file is None:
            logger.warning("Empty file passed.")
            return empty_gps, pd.DataFrame(), 'Empty file passed.'
        else:
            logger.error(f"Invalid input: {file}.")
            raise TypeError(f'{file} is not a valid input for station GPS parsing.')

        gps = gps.astype(str)
        # Remove P tags and units columns
        cols_to_drop = []
        for i, col in gps.dropna(axis=0).iteritems():
            # Remove P tag column
            if col.map(lambda x: x.startswith('<')).all():
                cols_to_drop.append(i)
            # Remove units column
            elif col.map(lambda x: x == '0').all():
                cols_to_drop.append(i)

        gps = gps.drop(cols_to_drop, axis=1)

        if len(gps.columns) < 4:
            error_msg = f"{len(gps.columns)} column(s) of values were found instead of 4."
            logger.warning(error_msg)
            return empty_gps, gps, error_msg
        elif len(gps.columns) > 4:
            gps = gps.drop(gps.columns[4:], axis=1)
        gps.columns = range(gps.shape[1])  # Reset the columns

        # Find any rows where there is a NaN
        bad_rows = gps.apply(has_na, axis=1)
        error_gps = gps.loc[bad_rows].copy()

        # Add the units column
        gps.insert(3, 'Unit', '0')

        cols = {
            0: 'Easting',
            1: 'Northing',
            2: 'Elevation',
            3: 'Station'
        }
        # Add the column names to the two data frames
        gps.rename(columns=cols, inplace=True)
        error_gps.rename(columns=cols, inplace=True)

        # Remove the NaNs from the good data frame
        gps = gps.dropna(axis=0).drop_duplicates()
        gps[['Easting', 'Northing', 'Elevation']] = gps[['Easting', 'Northing', 'Elevation']].astype(float)
        gps['Unit'] = gps['Unit'].astype(str)
        gps['Station'] = gps['Station'].map(convert_station)

        return gps, error_gps, error_msg

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
        :param hole: Union (str filepath, dataframe, list), GPS data
        """
        super().__init__()
        self.crs = crs
        self.df, self.errors, self.error_msg = self.parse_collar(hole)

    @staticmethod
    # @Log()
    def parse_collar(file):
        """
        Parse a text file for collar GPS. Returns the first match found.
        :param file: Union (str filepath, dataframe, list), GPS data. If list is passed, should be a nested list.
        :return: Pandas DataFrame of the GPS.
        """
        def has_na(series):
            """
            Return True if the row has any NaN, else return False.
            :param series: pandas Series
            :return: bool
            """
            if series.isnull().values.any():
                return True
            else:
                return False

        empty_gps = pd.DataFrame(columns=[
            'Easting',
            'Northing',
            'Elevation',
            'Unit',
        ])
        error_msg = ''

        if isinstance(file, list):
            if file:
                gps = pd.DataFrame(file)
            else:
                logger.warning(f"Empty file passed.")
                return empty_gps, pd.DataFrame(), 'Empty file passed.'

        elif isinstance(file, pd.DataFrame):
            gps = file

        elif Path(str(file)).is_file():
            file = open(file, 'rt').readlines()
            split_file = [r.strip().split() for r in file]
            gps = pd.DataFrame(split_file)

        elif file is None:
            logger.warning(f"No GPS passed.")
            return empty_gps, pd.DataFrame(), 'Empty file passed.'

        else:
            logger.error(f"Invalid input: {file}.")
            raise TypeError('Invalid input for collar GPS parsing')

        # If more than 1 collar GPS is found, only keep the first row and all other rows are errors
        if len(gps) > 1:
            logger.warning(f"{len(gps)} row(s) found instead of 1. Removing the extra rows.")
            gps = gps.drop(gps.iloc[1:].index)

        gps = gps.astype(str)
        # Remove P tags and units columns
        cols_to_drop = []
        for i, col in gps.dropna(axis=0).iteritems():
            if col.empty:
                continue
            # Remove P tag column
            if col.map(lambda x: str(x).startswith('<')).all():
                logger.info(f"Removing P-tag column.")
                cols_to_drop.append(i)
            # Remove units column
            elif col.map(lambda x: str(x) == '0').all():
                logger.info(f"Removing column of 0s.")
                cols_to_drop.append(i)

        gps = gps.drop(cols_to_drop, axis=1)

        if len(gps.columns) < 3:
            error_msg = f"{len(gps.columns)} column(s) of values were found instead of 3."
            logger.warning(error_msg)
            return empty_gps, gps, error_msg
        elif len(gps.columns) > 3:
            gps = gps.drop(gps.columns[3:], axis=1)  # Remove extra columns

        gps.columns = range(gps.shape[1])  # Reset the columns

        # Find any rows where there is a NaN
        bad_rows = gps.apply(has_na, axis=1)
        error_gps = gps.loc[bad_rows].copy()

        # Add the units column
        gps.insert(3, 'Unit', '0')

        cols = {
            0: 'Easting',
            1: 'Northing',
            2: 'Elevation',
        }
        # Add the column names to the two data frames
        gps.rename(columns=cols, inplace=True)
        error_gps.rename(columns=cols, inplace=True)

        # Remove the NaNs from the good data frame
        gps = gps.dropna(axis=0).drop_duplicates()

        gps[['Easting', 'Northing', 'Elevation']] = gps[['Easting', 'Northing', 'Elevation']].astype(float)
        gps['Unit'] = gps['Unit'].astype(str)

        return gps, error_gps, error_msg

    def get_collar(self):
        return self.df


class BoreholeSegments(BaseGPS):
    """
    Class representing the segments section of a borehole in a PEM file
    """

    def __init__(self, segments):
        """
        :param segments: Union (str filepath, dataframe, list), GPS data
        """
        super().__init__()
        self.df, self.errors, self.error_msg = self.parse_segments(segments)

    @staticmethod
    # @Log()
    def parse_segments(file):
        """
        Parse a text file for geometry segments.
        :param file: Union (str filepath, dataframe, list), GPS data
        :return: Pandas DataFrame of the segments.
        """

        def has_na(series):
            """
            Return True if the row has any NaN, else return False.
            :param series: pandas Series
            :return: bool
            """
            if series.isnull().values.any():
                return True
            else:
                return False

        empty_gps = pd.DataFrame(columns=[
            'Azimuth',
            'Dip',
            'Segment_length',
            'Unit',
            'Depth'
        ])
        error_msg = ''

        if isinstance(file, list):
            # split_file = [r.strip().split() for r in file]
            gps = pd.DataFrame(file)
        elif isinstance(file, pd.DataFrame):
            gps = file
        elif Path(str(file)).is_file():
            file = open(file, 'rt').readlines()
            split_file = [r.strip().split() for r in file]
            gps = pd.DataFrame(split_file)
        elif file is None:
            logger.warning(f"Empty file passed.")
            return empty_gps, pd.DataFrame(), 'Empty file passed.'
        else:
            logger.warning(f"Invalid input: {file}.")
            raise TypeError(f'{file} is not a valid input for segments parsing')

        gps = gps.astype(str)
        # Remove P tags and units columns
        cols_to_drop = []
        for i, col in gps.dropna(axis=0).iteritems():
            # Remove P tag column
            if col.map(lambda x: str(x).startswith('<')).all():
                cols_to_drop.append(i)

        gps = gps.drop(cols_to_drop, axis=1)

        if len(gps.columns) < 5:
            error_msg = f"{len(gps.columns)} column(s) of values were found instead of 5."
            logger.warning(error_msg)
            return empty_gps, gps, error_msg
        elif len(gps.columns) > 5:
            gps = gps.drop(gps.columns[5:], axis=1)

        gps.columns = range(gps.shape[1])  # Reset the columns

        # Find any rows where there is a NaN
        bad_rows = gps.apply(has_na, axis=1)
        error_gps = gps.loc[bad_rows].copy()

        cols = {
            0: 'Azimuth',
            1: 'Dip',
            2: 'Segment_length',
            3: 'Unit',
            4: 'Depth'
        }
        # Add the column names to the two data frames
        gps.rename(columns=cols, inplace=True)
        error_gps.rename(columns=cols, inplace=True)

        # Remove the NaNs from the good data frame
        gps = gps.dropna(axis=0).drop_duplicates()
        gps[['Azimuth',
             'Dip',
             'Segment_length',
             'Depth']] = gps[['Azimuth',
                              'Dip',
                              'Segment_length',
                              'Depth']].astype(float)
        gps['Unit'] = gps['Unit'].astype(str)

        return gps, error_gps, error_msg

    def get_segments(self):
        return self.df


class BoreholeGeometry(BaseGPS):
    """
    Class that represents the geometry of a hole, with collar and segments.
    """
    def __init__(self, collar, segments):
        super().__init__()
        self.collar = collar
        self.segments = segments

    def get_projection(self, num_segments=None, stations=None, latlon=False):
        """
        Uses the segments to create a 3D projection of a borehole trace. Can be broken up into segments and interpolated.
        :param num_segments: Desired number of segments to be output
        :param stations: list, stations to use for interpolation to ensure they are in the segments
        :param latlon: bool, whether to return the projection as latlon
        :return: pandas DataFrame: Projected easting, northing, elevation, and relative depth from collar
        """
        self.crs = self.collar.crs

        # Create the data frame
        projection = gpd.GeoDataFrame(columns=['Easting', 'Northing', 'Elevation', 'Relative_depth'])
        collar = self.collar.get_collar().dropna()
        segments = self.segments.get_segments().dropna()

        if collar.empty:
            logger.warning(f"Collar GPS is empty.")
            return projection
        elif segments.empty:
            logger.warning(f"Hole segments is empty.")
            return projection

        # Interpolate the segments
        if num_segments is not None or stations is not None:
            azimuths = segments.Azimuth.to_list()
            dips = segments.Dip.to_list()
            depths = segments.Depth.to_list()

            # Create the interpolated lists
            if stations is not None:
                interp_depths = sorted(np.unique(np.concatenate((depths, stations))))
                num_segments = len(interp_depths)
            else:
                interp_depths = np.linspace(depths[0], depths[-1], num_segments)
            interp_az = np.interp(interp_depths, depths, azimuths)
            interp_dip = np.interp(interp_depths, depths, dips)
            interp_lens = np.subtract(interp_depths[1:], interp_depths[:-1])
            interp_lens = np.insert(interp_lens, 0, segments.iloc[0]['Segment_length'])  # Add the first seg length
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
        projection['Relative_depth'] = pd.Series(relative_depth, dtype=float)
        self.df = projection

        if latlon and not self.df.empty:
            self.df = self.to_latlon().df

        return self.df

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


class GPXEditor:

    @staticmethod
    def parse_gpx(filepath):
        gpx_file = open(filepath, 'r')
        gpx = gpxpy.parse(gpx_file)
        gps = []
        for waypoint in gpx.waypoints:
            gps.append([waypoint.latitude, waypoint.longitude, waypoint.elevation, '0', waypoint.name])
        return gps

    def get_utm(self, gpx_file, as_string=False):
        """
        Retrieve the GPS from the GPS file in UTM coordinates
        :param gpx_file: str or Path, filepath
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
    # from src.pem.pem_getter import PEMGetter
    # pg = PEMGetter()
    # pem_files = pg.get_pems(client='Raglan', number=1)

    # gps_parser = GPSParser()
    # gpx_editor = GPXEditor()
    crs = CRS().from_dict({'System': 'UTM', 'Zone': '16 North', 'Datum': 'NAD 1983'})
    # file = r'C:\Users\Mortulo\PycharmProjects\PEMPro\src\gps\sample_files\45-1.csv'
    # file = r'C:\Users\Mortulo\PycharmProjects\PEMPro\sample_files\Collar GPS\AF19003 loop and collar.txt'
    file = r'C:\Users\Mortulo\PycharmProjects\PEMPro\sample_files\Segments\92-21A~1.SEG'
    # file = r'C:\Users\Mortulo\PycharmProjects\PEMPro\sample_files\Line GPS\LINE 0S.txt'
    # file = r'C:\Users\Mortulo\PycharmProjects\PEMPro\sample_files\Collar GPS\LT19003_collar.txt'
    # file = r'C:\Users\Mortulo\PycharmProjects\PEMPro\sample_files\Loop GPS\PERKOA SW LOOP 1.txt'
    # collar = BoreholeCollar(r'C:\Users\Mortulo\PycharmProjects\PEMPro\sample_files\Collar GPS\LT19003_collar.txt')
    # segments = BoreholeSegments(r'C:\Users\Mortulo\PycharmProjects\PEMPro\sample_files\Segments\718-3759gyro.seg')
    # geometry = BoreholeGeometry(collar, segments)
    # geometry.get_projection(num_segments=1000)
    # loop = TransmitterLoop(pem_files[0].loop.df, crs=crs)
    # loop.to_nad83()
    # line = SurveyLine(file, name=os.path.basename(file))
    # print(loop.get_sorted_loop(), '\n', loop.get_loop())
    # collar = BoreholeCollar(file)
    seg = BoreholeSegments(file)
    # gps_parser.parse_collar_gps(file)
