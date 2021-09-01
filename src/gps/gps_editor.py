import copy
import logging
import math
import re
from math import hypot
from pathlib import Path

import chardet
import geopandas as gpd
import gpxpy
import numpy as np
import pandas as pd
import utm
from pyproj import CRS
from scipy import spatial
from shapely.geometry import asMultiPoint

from src.pem import convert_station
from src.qt_py import read_file

logger = logging.getLogger(__name__)


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


def parse_gps(file, gps_object):
    def get_init_gps():
        """
        Create the empty dataframe, and initialize the units, columns and error message.
        :return: tuple, (dataframe, units, columns, error message)
        """
        units = "m"
        error_msg = ''

        if survey_line:
            empty_gps = pd.DataFrame(columns=[
                'Easting',
                'Northing',
                'Elevation',
                'Station'
            ])
            cols = {
                0: 'Easting',
                1: 'Northing',
                2: 'Elevation',
                3: 'Station'
            }
        else:
            empty_gps = pd.DataFrame(columns=[
                'Easting',
                'Northing',
                'Elevation',
            ])
            cols = {
                0: 'Easting',
                1: 'Northing',
                2: 'Elevation',
            }
        return empty_gps, units, cols, error_msg

    def read_file(file):
        """
        Create a dataframe from the contents of the input. Accepts many different input formats.
        :param file: input, can be list, dict, str, dataframe, or GPSObject.
        :return: dataframe
        """
        global error_msg

        if isinstance(file, list):
            gps = pd.DataFrame(file)
        elif isinstance(file, dict):
            gps = pd.DataFrame(file, index=[0])
        elif isinstance(file, pd.DataFrame):
            gps = file
        elif isinstance(file, str) or isinstance(file, Path):
            if not Path(file).is_file():
                raise ValueError(f"File {file} does not exist.")

            if Path(file).suffix.lower() == '.gpx':
                # Convert the GPX file to string
                gps, zone, hemisphere, crs, gpx_errors = GPXParser().get_utm(file, as_string=True)
                if gpx_errors:
                    error_msg += '\n'.join(gpx_errors)
                contents = [c.strip().split() for c in gps]
            else:
                contents = read_file(file, as_list=True)
            gps = pd.DataFrame(contents)
        else:
            logger.error(f"Invalid input: {file}.")
            raise TypeError(f'Invalid input for collar GPS parsing: {file}')

        return gps

    def cull_gps(gps):
        """
        Remove empty rows or rows in NaNs, remove <P> and <L> tags, units column, and any extra columns.
        :param gps: dataframe
        :return: tuple, (dataframe, dataframe of error rows)
        """
        global units, error_msg

        nan_rows = gps.iloc[:, 0: 3].apply(has_na, axis=1)
        error_gps = gps.loc[nan_rows].copy()
        gps = gps[~nan_rows]  # Remove NaN before converting to str
        if gps.empty:
            logger.debug("No GPS found after removing NaNs.")
            error_msg = f"No GPS found after removing NaNs."
            return gps, error_gps

        gps = gps.astype(str)
        # Remove P tags and units columns
        cols_to_drop = []
        for i, col in gps.dropna(axis=0).iteritems():
            if col.empty:
                continue
            # Remove P tag column
            if col.map(lambda x: str(x).startswith('<')).all():
                logger.debug(f"Removing <P> or <L> tag column.")
                cols_to_drop.append(i)
            # Remove units column (except borehole collars, and when number of columns would be less than 3,
            # in which case it is assumed it's the elevation value)
            elif col.map(lambda x: str(x) == '0').all() and len(gps.columns) - len(cols_to_drop) > 3:
                if gps_object == BoreholeCollar and len(gps.columns) == 3:
                    pass
                else:
                    units = 'm'
                    logger.debug(f"Removing column of 0s.")
                    cols_to_drop.append(i)
            elif col.map(lambda x: str(x) == '1').all() and len(gps.columns) - len(cols_to_drop) > 3:
                if gps_object == BoreholeCollar and len(gps.columns) == 3:
                    pass
                else:
                    units = 'ft'
                    logger.debug(f"Removing column of 1s.")
                    cols_to_drop.append(i)
        gps = gps.drop(cols_to_drop, axis=1)

        if survey_line:
            if len(gps.columns) < 4:
                error_msg = f"{len(gps.columns)} column(s) of values were found instead of 4."
                logger.info(error_msg)
                error_gps = gps.copy()
                gps = empty_gps.copy()
            elif len(gps.columns) > 4:
                gps = gps.drop(gps.columns[4:], axis=1)
        else:
            if len(gps.columns) < 3:
                error_msg = f"{len(gps.columns)} column(s) of values were found instead of 3."
                logger.info(error_msg)
                error_gps = gps.copy()
                gps = empty_gps.copy()
            elif len(gps.columns) > 3:
                logger.debug(F"Removing extra column.")
                gps = gps.drop(gps.columns[3:], axis=1)  # Remove extra columns

        return gps, error_gps

    global survey_line, units, error_msg
    survey_line = bool(gps_object == SurveyLine)
    empty_gps, units, cols, error_msg = get_init_gps()

    if file is None:
        logger.debug(f"No GPS passed.")
        return empty_gps, units, pd.DataFrame(), 'No GPS passed.'
    else:
        gps = read_file(file)

    gps, error_gps = cull_gps(gps)  # Remove tags, units, extra columns and empty/NaN rows
    if gps.empty:
        return gps, units, gps, error_msg

    gps.columns = range(gps.shape[1])  # Reset the columns
    gps.rename(columns=cols, inplace=True) # Add the column names to the two data frames
    error_gps.rename(columns=cols, inplace=True)

    # Remove the NaNs from the good data frame
    gps = gps.dropna(axis=0).drop_duplicates()
    gps[['Easting', 'Northing', 'Elevation']] = gps[['Easting', 'Northing', 'Elevation']].astype(float)
    if survey_line:
        gps['Station'] = gps['Station'].map(convert_station)

    return gps, units, error_gps, error_msg


class BaseGPS:

    def __init__(self):
        self.pem_file = None
        self.df = gpd.GeoDataFrame()
        self.units = None
        self.crs = None
        self.errors = pd.DataFrame()
        self.error_msg = ''

    def get_extents(self):
        """
        Return the min and max of each dimension of the GPS
        :return: xmin, xmax, ymin, ymax, zmin, zmax
        """
        return self.df['Easting'].min(), self.df['Easting'].max(), \
               self.df['Northing'].min(), self.df['Northing'].max(), \
               self.df['Elevation'].min(), self.df['Elevation'].max()

    def get_units(self):
        return self.units

        # units = self.df['Unit'].unique()
        # if units == '0' or '2':
        #     return 'm'
        # elif units == '1':
        #     return 'ft'
        # else:
        #     raise ValueError(f"'{units}'' is not a valid unit code. Must either be '0', '1', or '2'.")

    def get_units_code(self):
        if self.units == "m":
            return "0"
        elif self.units == "ft":
            return "1"
        elif self.units is None:
            return
        else:
            raise ValueError(f"{self.units} does not have an associated units code.")

    def get_errors(self):
        return self.errors

    def to_string(self, header=False):
        return self.df.to_string(index=False, header=header)

    def to_csv(self, header=False):
        return self.df.to_csv(index=False, header=header)

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
            logger.info('GPS pd.DataFrame is empty.')
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
            logger.info('GPS pd.DataFrame is empty.')
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
            logger.info('GPS pd.DataFrame is empty.')
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
            logger.info('GPS pd.DataFrame is empty.')
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
            logger.info('GPS pd.DataFrame is empty.')
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
        :param loop: Union (str, pd.DataFrame, list) filepath of a text file OR a data frame/list containing loop GPS
        """
        super().__init__()
        self.crs = crs
        self.df, self.units, self.errors, self.error_msg = self.parse_loop_gps(loop)

        # if cull_loop:
        #     self.cull_loop()

    @staticmethod
    def parse_loop_gps(file):
        """
        Parse a text file or data frame for loop GPS.
        :param file: Union (str filepath, pd.DataFrame, list), text containing GPS data
        :return: pd.DataFrame of the GPS.
        """
        if isinstance(file, TransmitterLoop):
            logger.info(f"SurveyLine passed.")
            return file.df, file.units, file.errors, ''
        else:
            gps, units, error_gps, error_msg = parse_gps(file, TransmitterLoop)
            return gps, units, error_gps, error_msg

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
        :return: pandas pd.DataFrame of sorted loop coordinates
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
        :param line: Union (str, pd.DataFrame, list) filepath of a text file OR a data frame/list containing line GPS
        """
        super().__init__()
        self.crs = crs
        self.df, self.units, self.errors, self.error_msg = self.parse_station_gps(line)

    @staticmethod
    def parse_station_gps(file):
        """
        Parse a text file or data frame for station GPS.
        :param file: Union (str filepath, pd.DataFrame, list), raw GPS data
        :return: pd.DataFrame of the GPS.
        """

        if isinstance(file, SurveyLine):
            logger.info(f"SurveyLine passed.")
            return file.df, file.units, file.errors, ''
        else:
            gps, units, error_gps, error_msg = parse_gps(file, SurveyLine)
            return gps, units, error_gps, error_msg

    def get_sorted_line(self):
        """
        Sorts the points in the survey line by distance. Chooses one end of the line, and uses that point to
        calculate the distance of each other point from that point, then sorts.
        :return: pandas pd.DataFrame of the sorted line GPS
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

    def get_azimuths(self):
        """
        Return the azimuth angle between each GPS point.
        :return: DataFrame
        """
        assert not self.df.empty, f"Line GPS is empty."

        gps = sorted(self.df.to_numpy(), key=lambda x: x[-1])  # Sorted by station number
        azimuths = []
        for ind, point in enumerate(gps):
            station = point[-1]
            # Repeat the last azimuth for the last point
            if ind == len(gps) - 1:
                azimuths.append((station, azimuths[-1][-1]))
                break

            next_point = gps[ind + 1]
            angle = math.degrees(math.atan2(next_point[1] - point[1], next_point[0] - point[0]))
            azimuth = 90 - angle
            azimuths.append((station, azimuth))

        return pd.DataFrame.from_records(azimuths, columns=["Station", "Azimuth"])


class BoreholeCollar(BaseGPS):
    """
    Class object representing the collar GPS
    """

    def __init__(self, hole, crs=None):
        """
        :param hole: Union (str filepath, pd.DataFrame, list), GPS data
        """
        super().__init__()
        self.crs = crs
        self.df, self.units, self.errors, self.error_msg = self.parse_collar(hole)

    @staticmethod
    # @Log()
    def parse_collar(file):
        """
        Parse a text file for collar GPS. Returns the first match found.
        :param file: Union (str filepath, pd.DataFrame, list), GPS data. If list is passed, should be a nested list.
        :return: Pandas pd.DataFrame of the GPS.
        """
        if isinstance(file, BoreholeCollar):
            logger.info(f"SurveyLine passed.")
            return file.df, file.units, file.errors, ''
        else:
            gps, units, error_gps, error_msg = parse_gps(file, BoreholeCollar)

        # If more than 1 collar GPS is found, only keep the first row and all other rows are errors
        if len(gps) > 1:
            logger.debug(f"{len(gps)} row(s) found instead of 1. Removing the extra rows.")
            gps = gps.drop(gps.iloc[1:].index)

        return gps, units, error_gps, error_msg

    def get_collar(self):
        return self.df


class BoreholeSegments(BaseGPS):
    """
    Class representing the segments section of a borehole in a PEM file
    """

    def __init__(self, segments):
        """
        :param segments: Union (str filepath, pd.DataFrame, list), GPS data
        """
        super().__init__()
        self.df, self.units, self.errors, self.error_msg = self.parse_segments(segments)

    @staticmethod
    # @Log()
    def parse_segments(file):
        """
        Parse a text file for geometry segments.
        :param file: Union (str filepath, pd.DataFrame, list), GPS data
        :return: Pandas pd.DataFrame of the segments.
        """
        empty_gps = pd.DataFrame(columns=[
            'Azimuth',
            'Dip',
            'Segment_length',
            'Depth'
        ])
        error_msg = ''
        units = "m"

        if isinstance(file, list):
            # split_file = [r.strip().split() for r in file]
            gps = pd.DataFrame(file)
        elif isinstance(file, pd.DataFrame):
            gps = file
        elif Path(str(file)).is_file():
            with open(file, 'rb') as byte_file:
                byte_content = byte_file.read()
                encoding = chardet.detect(byte_content).get('encoding')
                logger.info(f"Using {encoding} encoding for {Path(str(file)).name}.")
                str_contents = byte_content.decode(encoding=encoding)
            contents = [c.strip().split() for c in str_contents.splitlines()]
            gps = pd.DataFrame(contents)
        elif file is None:
            logger.debug(f"No GPS passed.")
            return empty_gps, units, pd.DataFrame(), 'No GPS passed.'
        else:
            logger.debug(f"Invalid input: {file}.")
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
            # Remove units column (except borehole collars if it's the elevation value)
            elif col.map(lambda x: str(x) == '2').all():
                units = 'm'
                logger.debug(f"Removing column of 0s.")
                cols_to_drop.append(i)

        gps = gps.drop(cols_to_drop, axis=1)

        if gps.empty:
            error_msg = f"No segments found."
            logger.info(error_msg)
            return empty_gps, units, gps, error_msg
        elif len(gps.columns) < 4:
            error_msg = f"{len(gps.columns)} column(s) of values were found instead of 4."
            logger.info(error_msg)
            return empty_gps, units, gps, error_msg
        elif len(gps.columns) > 4:
            gps = gps.drop(gps.columns[4:], axis=1)

        gps.columns = range(gps.shape[1])  # Reset the columns

        cols = {
            0: 'Azimuth',
            1: 'Dip',
            2: 'Segment_length',
            3: 'Depth'
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

        return gps, units, error_gps, error_msg

    def get_segments(self):
        return self.df

    def get_units_code(self):
        if self.units == "m":
            return "2"
        elif self.units == "ft":
            return "1"
        elif self.units is None:
            return
        else:
            raise ValueError(f"{self.units} does not have an associated units code.")

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
        :return: pandas pd.DataFrame: Projected easting, northing, elevation, and relative depth from collar
        """
        # Create the data frame
        projection = gpd.GeoDataFrame(columns=['Easting', 'Northing', 'Elevation', 'Relative_depth'])

        self.crs = self.collar.crs
        if not self.crs:
            logger.debug(f"No CRS passed.")
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

            # Stack up the arrays and transpose it
            segments = np.vstack(
                (interp_az,
                 interp_dip,
                 interp_lens,
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
            relative_depth = np.append(relative_depth, segment[3])

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
        units = self.collar.get_units()
        if units is None:
            logger.warning(f"No units passed. Assuming 'm'.")
        self.collar.df.insert(len(self.collar.df.columns) - 1, "Units", ["0" if units == "m" else "1"])
        self.segments.df.insert(len(self.segments.df.columns) - 1, "Units", ["2" if units == "m" else "1"] * len(self.segments.df))
        return self.collar.df.to_string() + '\n' + self.segments.df.to_string()

    def to_csv(self):
        units = self.collar.get_units()
        if units is None:
            logger.warning(f"No units passed. Assuming 'm'.")
        self.collar.df.insert(len(self.collar.df.columns) - 1, "Units", ["0" if units == "m" else "1"])
        self.segments.df.insert(len(self.segments.df.columns) - 1, "Units", ["2" if units == "m" else "1"] * len(self.segments.df))
        return self.collar.df.to_csv() + '\n' + self.segments.df.to_csv()


class GPXParser:

    @staticmethod
    def parse_gpx(filepath):
        with open(filepath, 'rb') as byte_file:
            byte_content = byte_file.read()
            encoding = chardet.detect(byte_content).get('encoding')
            logger.info(f"Using {encoding} encoding.")
            str_contents = byte_content.decode(encoding=encoding)
        gpx = gpxpy.parse(str_contents)
        gps = []
        errors = []

        # Use Route points if no waypoints exist
        if gpx.waypoints:
            for waypoint in gpx.waypoints:
                # name = re.sub(r'\s', '_', waypoint.name)
                name = re.sub(r'\W', '', waypoint.name)
                name = re.sub(r"[^nsewNSEW\d]", "", name)
                if not waypoint.elevation:
                    logger.warning(F"{name} has no elevation value. Using '0.0' instead.")
                    errors.append(F"{name} has no elevation value. Using '0.0' instead.")
                    waypoint.elevation = 0.
                gps.append([waypoint.latitude, waypoint.longitude, waypoint.elevation, '0', name])
            if len(gpx.waypoints) != len(gps):
                logger.warning(f"{len(gpx.waypoints)} waypoints found in GPX file but {len(gps)} points parsed.")
        elif gpx.routes:
            route = gpx.routes[0]
            for point in route.points:
                # name = re.sub(r'\s', '_', point.name)
                name = re.sub(r'\W', '', point.name)
                if not point.elevation:
                    logger.warning(F"{name} has no elevation value. Using '0.0' instead.")
                    errors.append(F"{name} has no elevation value. Using '0.0' instead.")
                    point.elevation = 0.
                gps.append([point.latitude, point.longitude, 0., '0', name])  # Routes have no elevation data, thus 0.
            if len(route.points) != len(gps):
                logger.warning(f"{len(route.points)} points found in GPX file but {len(gps)} points parsed.")
        else:
            raise ValueError(F"No waypoints or routes found in {Path(filepath).name}.")

        return gps, errors

    def get_utm(self, gpx_file, as_string=False):
        """
        Retrieve the GPS from the GPS file in UTM coordinates
        :param gpx_file: str or Path, filepath
        :param as_string: bool, return a string instead of tuple if True
        :return: latitude, longitude, elevation, unit, stn
        """
        try:
            gps, errors = self.parse_gpx(gpx_file)
        except Exception as e:
            raise Exception(str(e))
        zone = None
        hemisphere = None
        crs = None
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
            if crs is None:
                crs = self.get_crs(zone, hemisphere)
            if as_string is True:
                utm_gps.append(' '.join([str(u[0]), str(u[1]), str(elevation), units, name]))
            else:
                utm_gps.append([u[0], u[1], elevation, units, name])

        return utm_gps, zone, hemisphere, crs, errors

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


if __name__ == '__main__':
    # from src.pem.pem_getter import PEMGetter
    # pg = PEMGetter()
    # pem_files = pg.get_pems(client='Raglan', number=1)
    samples_folder = Path(__file__).parents[2].joinpath('sample_files')

    # gps_parser = GPSParser()
    gpx_editor = GPXParser()
    # crs = CRS().from_dict({'System': 'UTM', 'Zone': '16 North', 'Datum': 'NAD 1983'})
    gpx_file = samples_folder.joinpath(r'GPX files\L3100E_0814 (elevation error).gpx')
    # gpx_file = samples_folder.joinpath(r'GPX files\2000E_0524.gpx')

    print(gpx_editor.get_utm(gpx_file))
    file, errors = gpx_editor.parse_gpx(gpx_file)

    # file = samples_folder.joinpath(r'Line GPS\LINE 0S.txt')
    # file = r'C:\Users\Mortulo\PycharmProjects\PEMPro\sample_files\Collar GPS\LT19003_collar.txt'
    # file = r'C:\Users\Mortulo\PycharmProjects\PEMPro\sample_files\Loop GPS\PERKOA SW LOOP 1.txt'
    # collar = BoreholeCollar(samples_folder.joinpath(r'Collar GPS\LT19003_collar.txt'))
    # segments = BoreholeSegments(samples_folder.joinpath(r'Segments\718-3759gyro.seg'))
    # geometry = BoreholeGeometry(collar, segments)
    # print(geometry.to_string())
    # geometry.get_projection(num_segments=1000)
    # loop = TransmitterLoop(file)
    # loop.to_nad83()
    line = SurveyLine(file)
    # print(loop.get_sorted_loop(), '\n', loop.get_loop())
    # collar = BoreholeCollar(file)
    # seg = BoreholeSegments(file)
    # gps_parser.parse_collar_gps(file)
