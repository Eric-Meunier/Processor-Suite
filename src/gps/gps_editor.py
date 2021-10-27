import copy
import logging
import math
import re
from math import hypot
from pathlib import Path

import chardet
import geopandas as gpd
import numpy as np
import pandas as pd
from pyproj import CRS
from scipy import spatial
from shapely.geometry import asMultiPoint, Point, Polygon, MultiLineString, LineString
from zipfile import ZipFile

from src import app_temp_dir
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

    def get_gps(file):
        """
        Create a dataframe from the contents of the input. Accepts many different input formats.
        :param file: can be list, dict, str, dataframe, or GPSObject.
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
                gps, gdf, crs = read_gpx(file)
                gps.rename(columns={"Name": "Station"}, inplace=True)
                return gps
            else:
                contents = read_file(file, as_list=True)
            gps = pd.DataFrame.from_records(contents)
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
        gps = get_gps(file)

    gps, error_gps = cull_gps(gps)  # Remove tags, units, extra columns and empty/NaN rows
    if gps.empty:
        return gps, units, gps, error_msg

    gps.columns = range(gps.shape[1])  # Reset the columns
    gps.rename(columns=cols, inplace=True)  # Add the column names to the two data frames
    error_gps.rename(columns=cols, inplace=True)

    # Remove the NaNs from the good data frame
    gps = gps.dropna(axis=0).drop_duplicates()

    gps[['Easting', 'Northing', 'Elevation']] = gps[['Easting', 'Northing', 'Elevation']].astype(float)
    if survey_line:
        # Replace empty station numbers with 0
        gps["Station"].replace("None", "0", inplace=True)
        gps['Station'] = gps['Station'].map(convert_station)

    return gps, units, error_gps, error_msg


def read_kmz(file):
    """
    Parse a KMZ file, and create a DataFrame with the coordinates in UTM. Only keeps coordinates and name and description.
    Includes polygons and multilines.
    :param file: str
    :return: DataFrame
    """
    pd.set_option("display.precision", 2)
    gpd.io.file.fiona.drvsupport.supported_drivers["KML"] = "rw"

    # KMZs are just zipped KML, so extract the KMZ and the KML is the only object in there, so extract that.
    kmz = ZipFile(file, 'r')
    kmz.extract(kmz.filelist[0], app_temp_dir)

    gdf = gpd.read_file(app_temp_dir.joinpath('doc.kml'), driver="KML")
    crs = gdf.estimate_utm_crs()
    logger.info(f"Reading KMZ file {Path(file).name}. Estimated CRS: {crs.name}.")
    gdf = gdf.to_crs(crs)

    utm_df = pd.DataFrame(columns=["geometry", "Type", "Name", "Description"])

    # For multilines, ignore the last coordinate as it is a repeat of the first to close the shape.
    multilines = gdf.iloc[0:-1][gdf.iloc[0:-1].geometry.apply(lambda x: isinstance(x, MultiLineString))]
    linestrings = gdf[gdf.geometry.apply(lambda x: isinstance(x, LineString))]
    points = gdf[gdf.geometry.apply(lambda x: isinstance(x, Point))]
    polygons = gdf[gdf.geometry.apply(lambda x: isinstance(x, Polygon))]

    for name, multiline in multilines.iterrows():
        multiline_geometry = [Point(x) for x in [line.coords for line in multiline.geometry.geoms]]
        multiline_df = pd.DataFrame(multiline_geometry, columns=["geometry"])
        multiline_df["Type"] = ["Multiline"]  * len(multiline_geometry)
        multiline_df["Name"] = multiline.Name * len(multiline_geometry)
        multiline_df["Description"] = [""] * len(multiline_geometry)  # Ignore Multiline descriptions, they are gibberish.

        utm_df = pd.concat([utm_df, multiline_df])

    for name, linestring in linestrings.iterrows():
        linestring_geometry = [Point(x) for x in linestring.geometry.coords]
        linestring_df = pd.DataFrame(linestring_geometry, columns=["geometry"])
        linestring_df["Type"] = ["Linestring"]  * len(linestring_geometry)
        linestring_df["Name"] = linestring.Name * len(linestring_geometry)
        linestring_df["Description"] = linestring.Description

        utm_df = pd.concat([utm_df, linestring_df])

    for name, polygon in polygons.iterrows():
        polygon_geometry = [Point(x) for x in polygon.geometry.boundary.coords]
        polygon_df = pd.DataFrame(polygon_geometry, columns=["geometry"])
        polygon_df["Type"] = ["Polygon"]  * len(polygon_geometry)
        polygon_df["Name"] = polygon.Name
        polygon_df["Description"] = polygon.Description

        utm_df = pd.concat([utm_df, polygon_df])

    point_df = points.copy()
    point_df["Type"] = ["Point"] * len(point_df)
    utm_df = pd.concat([utm_df, point_df])

    utm_df["Easting"] = utm_df.geometry.map(lambda p: p.x).round(decimals=2)
    utm_df["Northing"] = utm_df.geometry.map(lambda p: p.y).round(decimals=2)
    # Re-arrange the columns and get rid of Geometry column
    utm_df = utm_df[["Easting", "Northing", "Type", "Name", "Description", "geometry"]]
    return utm_df, gdf, crs


def read_gpx(file, for_pemfile=False):
    """
    Parse a GPX file, and create a DataFrame with the coordinates in UTM. Only keeps coordinates and name and description.
    :param file: str
    :param for_pemfile: Bool, automatically rename invalid station names and elevation values for PEM files.
    :return: UTM DataFrame, GeoDataFrame, CRS
    """
    def rename_station(name):
        # Rename a name so it is a valid station name. i.e. numbers only except for the cardinal suffix.
        station_name = re.sub(r'\W', '', name)
        station_name = re.sub(r"[^nsewNSEW\d]", "", station_name)
        return station_name

    gdf = gpd.read_file(file)
    crs = gdf.estimate_utm_crs()
    logger.info(f"Reading GPX file {Path(file).name}. Estimated CRS: {crs.name}.")
    gdf = gdf.to_crs(crs)
    
    utm_df = pd.DataFrame()
    utm_df["Easting"] = gdf.geometry.map(lambda p: p.x).round(decimals=2)
    utm_df["Northing"] = gdf.geometry.map(lambda p: p.y).round(decimals=2)
    utm_df["Elevation"] = gdf.ele
    utm_df["Name"] = gdf.name
    utm_df["Description"] = gdf.desc
    utm_df["geometry"] = gdf.geometry

    if for_pemfile is True:
        utm_df["Name"] = utm_df["Name"].map(rename_station)

    return utm_df, gdf, crs


def read_gps(file, for_pemfile=False):
    """
    Helper function, parse a file which contains GPS information. Will read .txt, .xlsx, .xls, .csv, .kmz, .gpx.
    :param file: str or Path, a file with extention [.txt, .xlsx, .xls, .csv, .kmz, .gpx.]
    :param for_pemfile: Bool, if True, only keeps characters which are valid for station name conversion. Currently
    only applicable to GPX files.
    :return: tuple, UTM dataframe, GeoDataframe, CRS
    """
    if isinstance(file, str) or isinstance(file, Path):
        file = Path(file)
        if file.suffix.lower() == ".kmz":
            return read_kmz(file)
        elif file.suffix.lower() == ".gpx":
            return read_gpx(file, for_pemfile=for_pemfile)
        elif file.suffix.lower() == '.csv':
            contents = pd.read_csv(file, delim_whitespace=False, header=None)
            return contents, None, None
        elif file.suffix.lower() == '.txt':
            contents = pd.read_csv(file, delim_whitespace=True, header=None)
            return contents, None, None
        elif file.suffix.lower() in ['.xlsx', '.xls']:
            contents = pd.read_excel(file, header=None, sheet_name=None, dtype=str)
            return contents, None, None
        else:
            raise NotImplementedError(f"'{file.suffix}' files not supported."
                                      f" Must be one of .txt, .xlsx, .xls, .csv, .kmz, .gpx,")
    elif isinstance(file, list):
        contents = pd.DataFrame.from_records(file)
        return contents, None, None
    elif isinstance(file, pd.DataFrame):
        return file, None, None
    else:
        raise NotImplementedError(f"{file} is not supported. Must be a filepath, list, or dataframe.")


class BaseGPS:
    def __init__(self):
        """
        A basic GPS object (Transmitter loop, survey line, etc...).
        """
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

    def get_gdf(self):
        """
        Convert the Dataframe to a GeoDataframe. Must have a valid CRS.
        :return: GeoDataframe object.
        """
        df = self.df.copy().iloc[0:0]  # Copy and clear the data frame
        if not self.crs:
            logger.info('No CRS.')
            self.df = df
            return None
        elif self.df.empty:
            logger.info('GPS pd.DataFrame is empty.')
            self.df = df
            return None

        # Create point objects for each coordinate
        mpoints = asMultiPoint(self.df.loc[:, ['Easting', 'Northing']].to_numpy())
        gdf = gpd.GeoSeries(list(mpoints), crs=self.crs)
        return gdf

    def to_string(self, header=False):
        return self.df.to_string(index=False, header=header)

    def to_csv(self, header=False):
        return self.df.to_csv(index=False, header=header)

    def to_latlon(self):
        """
        Convert the data frame coordinates to Lat Lon in decimal format
        :return: GPS object
        """
        gdf = self.get_gdf()
        if gdf is None:
            return

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
        gdf = self.get_gdf()
        if gdf is None:
            return

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
        gdf = self.get_gdf()
        if gdf is None:
            return

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
        gdf = self.get_gdf()
        if gdf is None:
            return

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
        gdf = self.get_gdf()
        if gdf is None:
            return

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

    def get_loop_corners(self):
        """
        from https://www.pyimagesearch.com/2016/03/21/ordering-coordinates-clockwise-with-python-and-opencv/
        Get the loop corners. Hasn't been tested.
        :return: array
        """
        pts = self.df.to_numpy()
        # sort the points based on their x-coordinates
        xSorted = pts[np.argsort(pts[:, 0]), :]
        # grab the left-most and right-most points from the sorted
        # x-roodinate points
        leftMost = xSorted[:2, :]
        rightMost = xSorted[2:, :]
        # now, sort the left-most coordinates according to their
        # y-coordinates so we can grab the top-left and bottom-left
        # points, respectively
        leftMost = leftMost[np.argsort(leftMost[:, 1]), :]
        (tl, bl) = leftMost
        # now that we have the top-left coordinate, use it as an
        # anchor to calculate the Euclidean distance between the
        # top-left and right-most points; by the Pythagorean
        # theorem, the point with the largest distance will be
        # our bottom-right point
        D = spatial.distance.cdist(tl[np.newaxis], rightMost, "euclidean")[0]
        (br, tr) = rightMost[np.argsort(D)[::-1], :]
        # return the coordinates in top-left, top-right,
        # bottom-right, and bottom-left order
        return np.array([tl, tr, br, bl], dtype="float32")


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
        :param segments: Union (str filepath, pd.DataFrame, list, BoreholeSegments), GPS data
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

    def to_string(self, header=False):
        units = self.collar.get_units()
        if units is None:
            logger.warning(f"No units passed. Assuming 'm'.")
        self.collar.df.insert(len(self.collar.df.columns) - 1, "Units", ["0" if units == "m" else "1"])
        self.segments.df.insert(len(self.segments.df.columns) - 1, "Units", ["2" if units == "m" else "1"] * len(self.segments.df))
        return self.collar.df.to_string() + '\n' + self.segments.df.to_string()

    def to_csv(self, header=False):
        units = self.collar.get_units()
        if units is None:
            logger.warning(f"No units passed. Assuming 'm'.")
        self.collar.df.insert(len(self.collar.df.columns) - 1, "Units", ["0" if units == "m" else "1"])
        self.segments.df.insert(len(self.segments.df.columns) - 1, "Units", ["2" if units == "m" else "1"] * len(self.segments.df))
        return self.collar.df.to_csv() + '\n' + self.segments.df.to_csv()


if __name__ == '__main__':
    # from src.pem.pem_getter import PEMGetter
    # pg = PEMGetter()
    # pem_files = pg.get_pems(client='Raglan', number=1)
    samples_folder = Path(__file__).parents[2].joinpath('sample_files')

    # gps_parser = GPSParser()
    # crs = CRS().from_dict({'System': 'UTM', 'Zone': '16 North', 'Datum': 'NAD 1983'})

    # txt_file = r"C:\_Data\2021\Managem\Surface\Kokiak Aicha\GPS\KA1000N_1025.txt"
    # gpx_file = r'C:\_Data\2021\Eastern\L5N.gpx'
    # gpx_file = samples_folder.joinpath(r'GPX files\L3100E_0814 (elevation error).gpx')
    # gpx_file = samples_folder.joinpath(r'GPX files\Loop-32.gpx')

    kml_file = r"C:\Users\Eric\PycharmProjects\PEMPro\sample_files\KML Files\BHP Arizona OCLT-1801D.kmz"
    # kml_file = r"C:\Users\Eric\PycharmProjects\PEMPro\sample_files\KML Files\CAPA_A_stations.kmz"
    # read_kmz(kml_file)
    utm_df, gdf, crs = read_gps(kml_file, for_pemfile=True)
    print(utm_df)
    # utm_gps, zone, hemisphere, crs, errors = gpx_editor.get_utm(gpx_file)
    # df = pd.DataFrame(utm_gps)
    # df.to_csv(r"C:\_Data\2021\Eastern\L5N.CSV")
    # print(df)
    # file, errors = gpx_editor.parse_gpx(gpx_file)

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
    # line = SurveyLine(utm_gps)
    # print(line.df)
    # print(loop.get_sorted_loop(), '\n', loop.get_loop())
    # collar = BoreholeCollar(file)
    # seg = BoreholeSegments(file)
    # gps_parser.parse_collar_gps(file)
