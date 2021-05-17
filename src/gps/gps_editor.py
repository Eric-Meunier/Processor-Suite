import copy
import logging
import os
import re
import sys
from pathlib import Path
from shapely.geometry import asMultiPoint

import geopandas as gpd
import gpxpy
import math
import numpy as np
import pandas as pd
import utm
from PySide2 import QtCore, QtGui
from PySide2.QtUiTools import loadUiType
from PySide2.QtWidgets import (QWidget, QMessageBox)
from math import hypot
from pyproj import CRS
from scipy import spatial

logger = logging.getLogger(__name__)

if getattr(sys, 'frozen', False):
    application_path = Path(sys.executable).parent
else:
    application_path = Path(__file__).absolute().parents[1]
icons_path = application_path.joinpath('ui\\icons')

# Load Qt ui file into a class
Ui_GPSConversionWidget, _ = loadUiType(str(application_path.joinpath('ui\\gps_conversion.ui')))


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
            logger.info('No CRS')
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
            logger.infoinfoinfoinfo('No CRS')
            self.df = df
            return self
        elif self.df.empty:
            logger.info('GPS dataframe is empty.')
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
            logger.infoinfoinfo('No CRS.')
            self.df = df
            return self
        elif self.df.empty:
            logger.info('GPS dataframe is empty.')
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
            logger.infoinfo('No CRS.')
            self.df = df
            return self
        elif self.df.empty:
            logger.info('GPS dataframe is empty.')
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
        :param epsg_code: int, EPSG code to convert to.
        :return: GPS object
        """
        df = self.df.copy().iloc[0:0]  # Copy and clear the data frame
        if not self.crs:
            logger.info('No CRS.')
            self.df = df
            return self
        elif self.df.empty:
            logger.info('GPS dataframe is empty.')
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

        if isinstance(file, TransmitterLoop):
            logger.info(f"TransmitterLoop passed.")
            return file.df, file.errors, ''
        elif isinstance(file, list):
            # split_file = [r.strip().split() for r in file]
            gps = pd.DataFrame(file)
        elif isinstance(file, pd.DataFrame):
            gps = file
        elif Path(str(file)).is_file():
            file = open(file, 'rt').readlines()
            split_file = [r.strip().split() for r in file]
            gps = pd.DataFrame(split_file)
        elif file is None:
            logger.warning(f"No GPS passed.")
            return empty_gps, pd.DataFrame(), 'No GPS passed.'
        else:
            logger.error(f"Invalid input: {file}.")
            raise TypeError(f'{file} is not a valid input for loop GPS parsing.')

        # Capture rows with NaN in the first three columns
        nan_rows = gps.iloc[:, 0: 2].apply(has_na, axis=1)
        error_gps = gps.loc[nan_rows].copy()

        # Remove NaN before converting to str
        gps = gps[~nan_rows]

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

        if gps.empty:
            error_msg = f"No loop GPS found."
            logger.info(error_msg)
            return empty_gps, gps, error_msg
        elif len(gps.columns) < 3:
            error_msg = f"{len(gps.columns)} column(s) of values were found instead of 3."
            logger.info(error_msg)
            # print("Fewer than 3 columns were found.")
            return empty_gps, gps, error_msg
        elif len(gps.columns) > 3:
            gps = gps.drop(gps.columns[3:], axis=1)

        gps.columns = range(gps.shape[1])  # Reset the columns

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
        :param file: Union (str filepath, dataframe, list), raw GPS data
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
                station = (-float(re.sub(r"[SW]", "", station)))
            else:
                station = (float(re.sub(r"[EN]", "", station)))
            return int(station)

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

        if isinstance(file, SurveyLine):
            logger.info(f"SurveyLine passed.")
            return file.df, file.errors, ''
        elif isinstance(file, list):
            # split_file = [r.strip().split() for r in file]
            gps = pd.DataFrame(file)
        elif isinstance(file, pd.DataFrame):
            gps = file
        elif Path(str(file)).is_file():
            file = open(file, 'rt').readlines()
            split_file = [r.strip().split() for r in file]
            gps = pd.DataFrame(split_file)
        elif file is None:
            logger.warning("No GPS passed.")
            return empty_gps, pd.DataFrame(), 'No GPS passed.'
        else:
            logger.error(f"Invalid input: {file}.")
            raise TypeError(f'{file} is not a valid input for station GPS parsing.')

        # Capture rows with NaN in the first three columns
        nan_rows = gps.iloc[:, 0: 2].apply(has_na, axis=1)
        error_gps = gps.loc[nan_rows].copy()

        # Remove NaN before converting to str
        gps = gps[~nan_rows]

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

        if gps.empty:
            error_msg = f"No station GPS found."
            logger.info(error_msg)
            return empty_gps, gps, error_msg
        elif len(gps.columns) < 4:
            error_msg = f"{len(gps.columns)} column(s) of values were found instead of 4."
            logger.info(error_msg)
            return empty_gps, gps, error_msg
        elif len(gps.columns) > 4:
            gps = gps.drop(gps.columns[4:], axis=1)
        gps.columns = range(gps.shape[1])  # Reset the columns

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
                logger.warning(f"No GPS passed.")
                return empty_gps, pd.DataFrame(), 'No GPS passed.'

        elif isinstance(file, pd.DataFrame):
            gps = file

        elif Path(str(file)).is_file():
            file = open(file, 'rt').readlines()
            split_file = [r.strip().split() for r in file]
            gps = pd.DataFrame(split_file)

        elif file is None:
            logger.warning(f"No GPS passed.")
            return empty_gps, pd.DataFrame(), 'No GPS passed.'

        else:
            logger.error(f"Invalid input: {file}.")
            raise TypeError('Invalid input for collar GPS parsing')

        # If more than 1 collar GPS is found, only keep the first row and all other rows are errors
        if len(gps) > 1:
            logger.info(f"{len(gps)} row(s) found instead of 1. Removing the extra rows.")
            gps = gps.drop(gps.iloc[1:].index)

        # Capture rows with NaN in the first three columns
        nan_rows = gps.iloc[:, 0: 2].apply(has_na, axis=1)
        error_gps = gps.loc[nan_rows].copy()

        # Remove NaN before converting to str
        gps = gps[~nan_rows]

        gps = gps.astype(str)
        # Remove P tags and units columns
        cols_to_drop = []
        for i, col in gps.dropna(axis=0).iteritems():
            if col.empty:
                continue
            # Remove P tag column
            if col.map(lambda x: str(x).startswith('<')).all():
                # logger.info(f"Removing P-tag column.")
                cols_to_drop.append(i)
            # Remove units column
            # TODO A collar GPS with east, north, and 0 for elevation will fail because of this.
            elif col.map(lambda x: str(x) == '0').all():
                # logger.info(f"Removing column of 0s.")
                cols_to_drop.append(i)

        gps = gps.drop(cols_to_drop, axis=1)

        if gps.empty:
            error_msg = f"No collar GPS found."
            logger.info(error_msg)
            return empty_gps, gps, error_msg
        elif len(gps.columns) < 3:
            error_msg = f"{len(gps.columns)} column(s) of values were found instead of 3."
            logger.info(error_msg)
            return empty_gps, gps, error_msg
        elif len(gps.columns) > 3:
            gps = gps.drop(gps.columns[3:], axis=1)  # Remove extra columns

        gps.columns = range(gps.shape[1])  # Reset the columns

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
            logger.warning(f"No GPS passed.")
            return empty_gps, pd.DataFrame(), 'No GPS passed.'
        else:
            logger.warning(f"Invalid input: {file}.")
            raise TypeError(f'{file} is not a valid input for segments parsing')

        # Capture rows with NaN in the first three columns
        nan_rows = gps.iloc[:, 0: 2].apply(has_na, axis=1)
        error_gps = gps.loc[nan_rows].copy()

        # Remove NaN before converting to str
        gps = gps[~nan_rows]

        gps = gps.astype(str)
        # Remove P tags and units columns
        cols_to_drop = []
        for i, col in gps.dropna(axis=0).iteritems():
            # Remove P tag column
            if col.map(lambda x: str(x).startswith('<')).all():
                cols_to_drop.append(i)

        gps = gps.drop(cols_to_drop, axis=1)

        if gps.empty:
            error_msg = f"No segments found."
            logger.info(error_msg)
            return empty_gps, gps, error_msg
        elif len(gps.columns) < 5:
            error_msg = f"{len(gps.columns)} column(s) of values were found instead of 5."
            logger.info(error_msg)
            return empty_gps, gps, error_msg
        elif len(gps.columns) > 5:
            gps = gps.drop(gps.columns[5:], axis=1)

        gps.columns = range(gps.shape[1])  # Reset the columns

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
        # Create the data frame
        projection = gpd.GeoDataFrame(columns=['Easting', 'Northing', 'Elevation', 'Relative_depth'])

        self.crs = self.collar.crs
        if not self.crs:
            logger.info(f"No CRS passed.")
            if latlon:
                logger.error(f"Cannot project as latlon without CRS.")
                return projection
        elif self.crs.is_geographic:
            logger.error(f"CRS must be projected, not geographic.")
            return projection

        collar = self.collar.get_collar().dropna()
        segments = self.segments.get_segments().dropna()

        if collar.empty:
            logger.info(f"Collar GPS is empty.")
            return projection
        elif segments.empty:
            logger.info(f"Hole segments is empty.")
            return projection

        # Interpolate the segments
        if num_segments is not None or stations is not None:
            seg_azimuths = segments.Azimuth.to_list()
            seg_dips = segments.Dip.to_list()
            seg_depths = segments.Depth.to_list()

            # Create the interpolated lists. Make sure the first depth is 0 (collar)
            if stations is not None:
                interp_depths = sorted(np.unique(np.concatenate((seg_depths, stations))))
                if interp_depths[0] != 0:
                    interp_depths = np.insert(interp_depths, 0, 0.)
            else:
                interp_depths = np.linspace(seg_depths[0], seg_depths[-1], num_segments)
                if interp_depths[0] != 0:
                    interp_depths = np.insert(interp_depths, 0, 0.)

            num_segments = len(interp_depths)
            # Num segments is length of points - 1
            interp_az = np.interp(interp_depths[1:], seg_depths, seg_azimuths)
            interp_dip = np.interp(interp_depths[1:], seg_depths, seg_dips)
            interp_lens = np.diff(interp_depths)
            inter_units = np.full(num_segments - 1, segments.Unit.unique()[0])

            # Stack up the arrays and transpose it
            segments = np.vstack(
                (interp_az,
                 interp_dip,
                 interp_lens,
                 inter_units,
                 interp_depths[1:])
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
            # relative_depth = np.append(relative_depth, relative_depth[-1] + seg_l)
            relative_depth = np.append(relative_depth, segment[4])

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

        # Use Route points if no waypoints exist
        if gpx.waypoints:
            for waypoint in gpx.waypoints:
                # name = re.sub(r'\s', '_', waypoint.name)
                name = re.sub(r'\W', '', waypoint.name)
                if not all([waypoint.latitude, waypoint.longitude, waypoint.elevation]):
                    logger.warning(F"Skipping point {name} as the GPS is incomplete.")
                else:
                    gps.append([waypoint.latitude, waypoint.longitude, waypoint.elevation, '0', name])
        elif gpx.routes:
            route = gpx.routes[0]
            for point in route.points:
                # name = re.sub(r'\s', '_', point.name)
                name = re.sub(r'\W', '', point.name)
                if not all([point.latitude, point.longitude, point.elevation]):
                    logger.warning(F"Skipping point {name} as the GPS is incomplete.")
                else:
                    gps.append([point.latitude, point.longitude, 0., '0', name])  # Routes have no elevation data, thus 0.
        else:
            raise ValueError(F"No waypoints or routes found in {Path(filepath).name}.")
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
            name = row[4]  # Station name usually
            # stn = re.findall('\d+', re.split('-', name)[-1])
            # stn = stn[0] if stn else ''
            u = utm.from_latlon(lat, lon)
            zone = u[2]
            letter = u[3]
            hemisphere = 'north' if lat >= 0 else 'south'  # Used in PEMEditor
            crs = self.get_crs(zone, hemisphere)
            if as_string is True:
                utm_gps.append(' '.join([str(u[0]), str(u[1]), str(elevation), units, name]))
            else:
                utm_gps.append([u[0], u[1], elevation, units, name])

        return utm_gps, zone, hemisphere, crs

    def get_lat_long(self, gpx_filepath):
        gps = self.parse_gpx(gpx_filepath)
        return gps

    def get_crs(self, zone_number, hemis):
        if hemis == "north":
            north = True
        else:
            north = False

        # Assumes datum is WGS1984
        if north:
            epsg_code = f'326{zone_number:02d}'
        else:
            epsg_code = f'327{zone_number:02d}'
        logger.debug(f"EPSG for zone {zone_number}, hemisphese {hemis}: {epsg_code}.")

        try:
            crs = CRS.from_epsg(epsg_code)
        except Exception as e:
            logger.error(f"{e}.")
            return None
        else:
            logger.debug(f"Project CRS: {crs.name}")
            return crs

    def save_gpx(self, coordinates):
        pass


class GPSConversionWidget(QWidget, Ui_GPSConversionWidget):
    accept_signal = QtCore.Signal(int)

    def __init__(self, parent=None):
        super().__init__()
        self.setupUi(self)

        self.parent = parent
        self.message = QMessageBox()

        self.convert_to_label.setText('')
        self.current_crs_label.setText('')

        self.init_signals()

    def init_signals(self):

        def toggle_gps_system():
            """
            Toggle the datum and zone combo boxes and change their options based on the selected CRS system.
            """
            current_zone = self.gps_zone_cbox.currentText()
            datum = self.gps_datum_cbox.currentText()
            system = self.gps_system_cbox.currentText()

            if system == '':
                self.gps_zone_cbox.setEnabled(False)
                self.gps_datum_cbox.setEnabled(False)

            elif system == 'Lat/Lon':
                self.gps_datum_cbox.setCurrentText('WGS 1984')
                self.gps_zone_cbox.setCurrentText('')
                self.gps_datum_cbox.setEnabled(False)
                self.gps_zone_cbox.setEnabled(False)

            elif system == 'UTM':
                self.gps_datum_cbox.setEnabled(True)

                if datum == '':
                    self.gps_zone_cbox.setEnabled(False)
                    return
                else:
                    self.gps_zone_cbox.clear()
                    self.gps_zone_cbox.setEnabled(True)

                # NAD 27 and 83 only have zones from 1N to 22N/23N
                if datum == 'NAD 1927':
                    zones = [''] + [f"{num} North" for num in range(1, 23)] + ['59 North', '60 North']
                elif datum == 'NAD 1983':
                    zones = [''] + [f"{num} North" for num in range(1, 24)] + ['59 North', '60 North']
                # WGS 84 has zones from 1N and 1S to 60N and 60S
                else:
                    zones = [''] + [f"{num} North" for num in range(1, 61)] + [f"{num} South" for num in range(1, 61)]

                for zone in zones:
                    self.gps_zone_cbox.addItem(zone)

                # Keep the same zone number if possible
                self.gps_zone_cbox.setCurrentText(current_zone)

        def toggle_crs_rbtn():
            """
            Toggle the radio buttons for the project CRS box, switching between the CRS drop boxes and the EPSG edit.
            """
            if self.crs_rbtn.isChecked():
                # Enable the CRS drop boxes and disable the EPSG line edit
                self.gps_system_cbox.setEnabled(True)
                toggle_gps_system()

                self.epsg_edit.setEnabled(False)
            else:
                # Disable the CRS drop boxes and enable the EPSG line edit
                self.gps_system_cbox.setEnabled(False)
                self.gps_datum_cbox.setEnabled(False)
                self.gps_zone_cbox.setEnabled(False)

                self.epsg_edit.setEnabled(True)

        def check_epsg():
            """
            Try to convert the EPSG code to a Proj CRS object, reject the input if it doesn't work.
            """
            epsg_code = self.epsg_edit.text()
            self.epsg_edit.blockSignals(True)

            if epsg_code:
                try:
                    crs = CRS.from_epsg(epsg_code)
                except Exception as e:
                    logger.critical(str(e))
                    self.message.critical(self, 'Invalid EPSG Code', f"{epsg_code} is not a valid EPSG code.")
                    self.epsg_edit.setText('')
                finally:
                    set_epsg_label()

            self.epsg_edit.blockSignals(False)

        def set_epsg_label():
            """
            Convert the current project CRS combo box values into the EPSG code and set the status bar label.
            """
            epsg_code = self.get_epsg()
            if epsg_code:
                crs = CRS.from_epsg(epsg_code)
                self.convert_to_label.setText(f"{crs.name} ({crs.type_name})")
            else:
                self.convert_to_label.setText('')

        # Add the GPS system and datum drop box options
        gps_systems = ['', 'Lat/Lon', 'UTM']
        for system in gps_systems:
            self.gps_system_cbox.addItem(system)

        datums = ['', 'WGS 1984', 'NAD 1927', 'NAD 1983']
        for datum in datums:
            self.gps_datum_cbox.addItem(datum)

        int_valid = QtGui.QIntValidator()
        self.epsg_edit.setValidator(int_valid)

        self.gps_system_cbox.currentIndexChanged.connect(toggle_gps_system)
        self.gps_system_cbox.currentIndexChanged.connect(set_epsg_label)
        self.gps_datum_cbox.currentIndexChanged.connect(toggle_gps_system)
        self.gps_datum_cbox.currentIndexChanged.connect(set_epsg_label)
        self.gps_zone_cbox.currentIndexChanged.connect(set_epsg_label)

        self.crs_rbtn.clicked.connect(toggle_crs_rbtn)
        self.crs_rbtn.clicked.connect(set_epsg_label)
        self.epsg_rbtn.clicked.connect(toggle_crs_rbtn)
        self.epsg_rbtn.clicked.connect(set_epsg_label)

        self.epsg_edit.editingFinished.connect(check_epsg)

        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.close)

    def closeEvent(self, e):
        self.deleteLater()
        e.accept()

    def accept(self):
        """
        Signal slot, emit the EPSG code.
        :return: int
        """
        epsg_code = self.get_epsg()
        if epsg_code:
            self.accept_signal.emit(int(epsg_code))
            self.close()
        else:
            logger.error(f"{epsg_code} is not a valid EPSG code.")
            self.message.information(self, 'Invalid CRS', 'The selected CRS is invalid.')

    def open(self, current_crs):
        self.current_crs_label.setText(f"{current_crs.name} ({current_crs.type_name})")
        self.show()

    def get_epsg(self):
        """
        Return the EPSG code currently selected. Will convert the drop boxes to EPSG code.
        :return: str, EPSG code
        """

        def convert_to_epsg():
            """
            Convert and return the EPSG code of the project CRS combo boxes
            :return: str
            """
            system = self.gps_system_cbox.currentText()
            zone = self.gps_zone_cbox.currentText()
            datum = self.gps_datum_cbox.currentText()

            if system == '':
                return None

            elif system == 'Lat/Lon':
                return '4326'

            else:
                if not zone or not datum:
                    return None

                s = zone.split()
                zone_number = int(s[0])
                north = True if s[1] == 'North' else False

                if datum == 'WGS 1984':
                    if north:
                        epsg_code = f'326{zone_number:02d}'
                    else:
                        epsg_code = f'327{zone_number:02d}'
                elif datum == 'NAD 1927':
                    epsg_code = f'267{zone_number:02d}'
                elif datum == 'NAD 1983':
                    epsg_code = f'269{zone_number:02d}'
                else:
                    logger.error(f"{datum} to EPSG code has not been implemented.")
                    return None

                return epsg_code

        if self.epsg_rbtn.isChecked():
            epsg_code = self.epsg_edit.text()
        else:
            epsg_code = convert_to_epsg()

        return epsg_code


if __name__ == '__main__':
    # from src.pem.pem_getter import PEMGetter
    # pg = PEMGetter()
    # pem_files = pg.get_pems(client='Raglan', number=1)
    samples_folder = Path(__file__).parents[2].joinpath('sample_files')

    # gps_parser = GPSParser()
    gpx_editor = GPXEditor()
    # crs = CRS().from_dict({'System': 'UTM', 'Zone': '16 North', 'Datum': 'NAD 1983'})
    gpx_file = samples_folder.joinpath(r'GPX files\L77+25_0515.gpx')

    result = gpx_editor.get_utm(gpx_file)

    # file = r'C:\Users\Mortulo\PycharmProjects\PEMPro\sample_files\Line GPS\LINE 0S.txt'
    # file = r'C:\Users\Mortulo\PycharmProjects\PEMPro\sample_files\Collar GPS\LT19003_collar.txt'
    # file = r'C:\Users\Mortulo\PycharmProjects\PEMPro\sample_files\Loop GPS\PERKOA SW LOOP 1.txt'
    # collar = BoreholeCollar(r'C:\Users\Mortulo\PycharmProjects\PEMPro\sample_files\Collar GPS\LT19003_collar.txt')
    # segments = BoreholeSegments(r'C:\Users\Mortulo\PycharmProjects\PEMPro\sample_files\Segments\718-3759gyro.seg')
    # geometry = BoreholeGeometry(collar, segments)
    # geometry.get_projection(num_segments=1000)
    # loop = TransmitterLoop(file)
    # loop.to_nad83()
    # line = SurveyLine(file, name=os.path.basename(file))
    # print(loop.get_sorted_loop(), '\n', loop.get_loop())
    # collar = BoreholeCollar(file)
    # seg = BoreholeSegments(file)
    # gps_parser.parse_collar_gps(file)
