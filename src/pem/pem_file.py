import copy
import logging
import math
import re
import time
from datetime import datetime
from pathlib import Path

import geomag
import natsort
import numpy as np
import pandas as pd
from pyproj import CRS
from scipy.spatial.transform import Rotation as R

from src.gps.gps_editor import TransmitterLoop, SurveyLine, BoreholeCollar, BoreholeSegments, BoreholeGeometry  # , CRS
from src.logger import Log
from src.mag_field.mag_field_calculator import MagneticFieldCalculator

logger = logging.getLogger(__name__)


def sort_data(data):
    # Sort the data frame
    df = data.reindex(index=natsort.order_by_index(
        data.index, natsort.index_humansorted(zip(data.Component,
                                                  data.Station,
                                                  data['Reading_index'],
                                                  data['Reading_number']))))
    # Reset the index
    df.reset_index(drop=True, inplace=True)
    return df


class StationConverter:

    @staticmethod
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

    def convert_stations(self, stations):
        converted_stations = stations.map(self.convert_station)
        return converted_stations


class PEMFile:
    """
    PEM file class
    """
    def __init__(self):
        self.converter = StationConverter()
        self.format = None
        self.units = None
        self.operator = None
        self.probes = None
        self.current = None
        self.loop_dimensions = None
        self.client = None
        self.grid = None
        self.line_name = None
        self.loop_name = None
        self.date = None
        self.survey_type = None
        self.convention = None
        self.sync = None
        self.timebase = None
        self.ramp = None
        self.number_of_channels = None
        self.number_of_readings = None
        self.rx_number = None
        self.rx_software_version = None
        self.rx_software_version_date = None
        self.rx_file_name = None
        self.normalized = None
        self.primary_field_value = None
        self.coil_area = None
        self.loop_polarity = None
        self.channel_times = None

        self.notes = None
        self.data = None
        self.filepath = None

        self.loop = None
        self.collar = None
        self.segments = None
        # self.geometry = None
        self.line = None
        self.crs = None

        self.total_scale_factor = 0.
        self.pp_table = None
        self.prepped_for_rotation = False
        self.legacy = False

    def from_pem(self, tags, loop_coords, line_coords, notes, header, channel_table, data, filepath=None):
        """
        Fill the information of the PEM file object from a parsed .PEM file.
        :param tags: dict, tags section of the PEM file
        :param loop_coords: list, loop coordinates
        :param line_coords: list, line/hole geometry coordinates
        :param notes: list, notes section
        :param header: dict, header section
        :param channel_table: DataFrame of the channel times
        :param data: DataFrame of the data
        :param filepath: str, filepath of the file
        :return: PEMFile object
        """
        self.format = tags.get('Format')
        self.units = tags.get('Units')
        self.operator = tags.get('Operator')
        self.probes = tags.get('Probes')
        self.current = tags.get('Current')
        self.loop_dimensions = tags.get('Loop dimensions')

        self.client = header.get('Client')
        self.grid = header.get('Grid')
        self.line_name = header.get('Line_name')
        self.loop_name = header.get('Loop_name')
        self.date = header.get('Date')
        self.survey_type = header.get('Survey type')
        self.convention = header.get('Convention')
        self.sync = header.get('Sync')
        self.timebase = header.get('Timebase')
        self.ramp = header.get('Ramp')
        # self.number_of_channels = header.get('Number of channels')
        self.number_of_readings = header.get('Number of readings')
        self.rx_number = header.get('Receiver number')
        self.rx_software_version = header.get('Rx software version')
        self.rx_software_version_date = header.get('Rx software version date')
        self.rx_file_name = header.get('Rx file name')
        self.normalized = header.get('Normalized')
        self.primary_field_value = header.get('Primary field value')
        self.coil_area = header.get('Coil area')
        self.loop_polarity = header.get('Loop polarity')
        self.channel_times = channel_table
        self.number_of_channels = len(channel_table)

        self.notes = notes

        self.data = sort_data(data)
        # Add the deletion flag column
        if 'Deleted' not in self.data.columns:
            self.data.insert(13, 'Deleted', False)

        # Add the overload column
        if 'Overload' not in self.data.columns:
            self.data.insert(14, 'Overload', False)

        # Add the Timestamp column
        if 'Timestamp' not in self.data.columns:
            self.data.insert(15, 'Timestamp', None)

        self.filepath = Path(filepath)

        crs = self.get_crs()
        self.loop = TransmitterLoop(loop_coords, crs=crs)
        if self.is_borehole():
            self.collar = BoreholeCollar([line_coords[0]], crs=crs)
            self.segments = BoreholeSegments(line_coords[1:])
            # self.geometry = BoreholeGeometry(self.collar, self.segments)
        else:
            self.line = SurveyLine(line_coords, crs=crs)

        return self

    def from_dmp(self, header, channel_table, data, filepath, notes=None):
        """
        Create a PEMFile object from the contents of a parsed .DMP file.
        :param header: parsed dictionary of DMP header information
        :param channel_table: parsed DataFrame of the channel table in the DMP file
        :param data: parsed DataFrame of the data in the DMP file
        :param filepath: Path object of the DMP file.
        :param notes: parsed list of notes in the DMP file
        :return: PEMFile object
        """
        self.format = header.get('Format')
        self.units = header.get('Units')
        self.operator = header.get('Operator')
        self.probes = header.get('Probes')
        self.current = header.get('Current')
        self.loop_dimensions = header.get('Loop dimensions')

        self.client = header.get('Client')
        self.grid = header.get('Grid')
        self.line_name = header.get('Line_name')
        self.loop_name = header.get('Loop_name')
        self.date = header.get('Date')
        self.survey_type = header.get('Survey type')
        self.convention = header.get('Convention')
        self.sync = header.get('Sync')
        self.timebase = header.get('Timebase')
        self.ramp = header.get('Ramp')
        # self.number_of_channels = header.get('Number of channels')
        self.number_of_readings = header.get('Number of readings')
        self.rx_number = header.get('Receiver number')
        self.rx_software_version = header.get('Rx software version')
        self.rx_software_version_date = header.get('Rx software version date')
        self.rx_file_name = header.get('Rx file name')
        self.normalized = header.get('Normalized')
        self.primary_field_value = header.get('Primary field value')
        self.coil_area = header.get('Coil area')
        self.loop_polarity = header.get('Loop polarity')
        self.channel_times = channel_table
        self.number_of_channels = len(channel_table)

        if notes:
            self.notes = notes
        else:
            self.notes = []

        self.data = sort_data(data)
        # Add the deletion flag column
        if 'Deleted' not in self.data.columns:
            self.data.insert(13, 'Deleted', False)

        # Add the overload column
        if 'Overload' not in self.data.columns:
            self.data.insert(14, 'Overload', False)

        # Add the Timestamp column
        if 'Timestamp' not in self.data.columns:
            self.data.insert(15, 'Timestamp', None)

        self.filepath = filepath.with_suffix('.PEM')

        crs = self.get_crs()
        self.loop = TransmitterLoop(None, crs=crs)
        if self.is_borehole():
            self.collar = BoreholeCollar(None, crs=crs)
            self.segments = BoreholeSegments(None)
            # self.geometry = BoreholeGeometry(self.collar, self.segments)
        else:
            self.line = SurveyLine(None, crs=crs)

        return self

    def is_borehole(self):
        if 'borehole' in self.get_survey_type().lower():
            return True
        else:
            return False

    def is_fluxgate(self):
        if 'fluxgate' in self.get_survey_type().lower() or 'squid' in self.get_survey_type().lower():
            return True
        else:
            return False

    def is_derotated(self):
        if self.is_borehole():
            filt = (self.data.Component == 'X') | (self.data.Component == 'Y')
            xy_data = self.data[filt]
            return xy_data['RAD_tool'].map(lambda x: x.rotated).all()
        else:
            return False

    def is_averaged(self):
        data = self.data[['Station', 'Component']]
        if any(data.duplicated()):
            return False
        else:
            return True

    def is_split(self):
        t = time.time()
        if self.channel_times.Remove.any():
            return False
        else:
            return True

    def is_pp(self):
        if self.channel_times.Width.max() < 10 ** -4:
            return True
        else:
            return False

    def has_collar_gps(self):
        if self.is_borehole():
            if not self.collar.df.dropna().empty and all(self.collar.df):
                return True
            else:
                return False
        else:
            return False

    def has_geometry(self):
        if self.is_borehole():
            if not self.segments.df.dropna().empty and all(self.segments.df):
                return True
            else:
                return False
        else:
            return False

    def has_loop_gps(self):
        if not self.loop.df.dropna().empty and all(self.loop.df):
            return True
        else:
            return False

    def has_station_gps(self):
        if not self.is_borehole():
            if not self.line.df.dropna().empty and all(self.line.df):
                return True
            else:
                return False
        else:
            return False

    def has_any_gps(self):
        if any([self.has_collar_gps(), self.has_geometry(), self.has_station_gps(), self.has_loop_gps()]):
            return True
        else:
            return False

    def has_all_gps(self):
        if self.is_borehole():
            if not all([self.has_loop_gps(), self.has_collar_gps(), self.has_geometry()]):
                return False
            else:
                return True
        else:
            if not all([self.has_loop_gps(), self.has_station_gps()]):
                return False
            else:
                return True

    def has_d7(self):
        return self.data.RAD_tool.map(lambda x: x.D == 'D7').all()

    def has_xy(self):
        components = self.get_components()
        if 'X' in components and 'Y' in components:
            return True
        else:
            return False

    def get_gps_units(self):
        """
        Return the type of units being used for GPS ('m' or 'ft')
        :return: str
        """
        if self.has_loop_gps():
            unit = self.loop.df.get('Unit').all()
        elif self.has_collar_gps():
            unit = self.collar.df.get('Unit').all()
        elif self.has_station_gps():
            unit = self.line.df.get('Unit').all()
        else:
            return None

        if unit == '0':
            return 'm'
        elif unit == '1':
            return 'ft'
        else:
            raise ValueError(f"{unit} is not 0 or 1")

    def get_crs(self):
        """
        Return the PEMFile's CRS, or create one from the note in the PEM file if it exists.
        :return: Proj CRS object
        """

        if self.crs:
            return self.crs

        else:
            for note in self.notes:
                if '<CRS>' in note:
                    crs_str = re.split('<CRS>', note)[-1].strip()
                    crs = CRS.from_string(crs_str)
                    logger.info(f"{self.filepath.name} CRS is {crs.name}.")
                    return crs

                # For older PEM files that used the <GEN> tag
                elif 'CRS:' in note:
                    crs_str = re.split('CRS: ', note)[-1]
                    s = crs_str.split()

                    system = s[0]
                    if system == 'Lat/Lon':
                        epsg_code = '4326'
                    else:
                        zone_number = s[2]
                        north = True if s[3].strip(',') == 'North' else False
                        datum = f"{s[4]} {s[5]}"

                        if datum == 'WGS 1984':
                            if north:
                                epsg_code = f'326{zone_number}'
                            else:
                                epsg_code = f'327{zone_number}'
                        elif datum == 'NAD 1927':
                            epsg_code = f'267{zone_number}'
                        elif datum == 'NAD 1983':
                            epsg_code = f'269{zone_number}'
                        else:
                            logger.error(f"{datum} CRS string not implemented.")
                            return None

                    crs = CRS.from_epsg(epsg_code)
                    logger.info(f"{self.filepath.name} CRS is {crs.name}")
                    return crs

    def get_loop(self, sorted=False, closed=False):
        return self.loop.get_loop(sorted=sorted, closed=closed)

    def get_line(self, sorted=False):
        return self.line.get_line(sorted=sorted)

    def get_collar(self):
        return self.collar.get_collar()

    def get_segments(self):
        return self.segments.get_segments()

    def get_geometry(self):
        return BoreholeGeometry(self.collar, self.segments)

    def get_notes(self):
        return self.notes

    def get_data(self, sorted=False):
        if sorted:
            data = sort_data(self.data)
        else:
            data = self.data
        return data

    def get_dad(self):
        """
        Return the DAD of a borehole file. Will use the segments if available, other will use the RAD for XY files.
        :return: Dataframe
        """
        assert self.is_borehole(), f"Can only get DAD from borehole surveys."
        assert any([self.has_xy(), self.has_geometry()]), f"File must either have geometry or be an XY file."

        if self.has_geometry():
            # Create the DAD from the geometry
            seg = self.segments.df

            # Interpolate the data to 1m segment lengths and starting from depth 0
            xi = np.arange(0, seg.Depth.max() + 1, 1)
            i_az = np.interp(xi, seg.Depth, seg.Azimuth)
            i_dip = np.interp(xi, seg.Depth, seg.Dip)
        else:
            # Create the DAD from the RAD Tool data
            data = self.data.drop_duplicates(subset='Station')
            depths = data.loc[:, "Station"].astype(int)
            azimuths = data.RAD_tool.apply(lambda x: x.get_azimuth()).astype(float)
            dips = data.RAD_tool.apply(lambda x: x.get_dip()).astype(float)

            xi = np.arange(0, depths.max() + 1, 1)
            i_az = np.interp(xi, depths, azimuths)
            i_dip = np.interp(xi, depths, dips)

        return pd.DataFrame({'Depth': xi, 'Azimuth': i_az, 'Dip': i_dip})

    def get_channel_bounds(self):
        """
        Create tuples of start and end channels to be plotted per axes for LIN plots
        :return: list of tuples, first item of tuple is the axes, second is the start and end channel for that axes
        """
        channel_bounds = [None] * 4

        # Only plot off-time channels
        number_of_channels = len(self.channel_times[~self.channel_times.Remove.astype(bool)])

        num_channels_per_plot = int((number_of_channels - 1) // 4)
        remainder_channels = int((number_of_channels - 1) % 4)

        for k in range(0, len(channel_bounds)):
            channel_bounds[k] = (k * num_channels_per_plot + 1, num_channels_per_plot * (k + 1))

        for i in range(0, remainder_channels):
            channel_bounds[i] = (channel_bounds[i][0], (channel_bounds[i][1] + 1))
            for k in range(i + 1, len(channel_bounds)):
                channel_bounds[k] = (channel_bounds[k][0] + 1, channel_bounds[k][1] + 1)

        channel_bounds.insert(0, (0, 0))
        logger.debug(f"{self.filepath.name} has {number_of_channels} channels. LIN plots binned as {channel_bounds}.")

        return channel_bounds

    def get_profile_data(self, component, averaged=False, converted=False, ontime=True, incl_deleted=False):
        """
        Transform the readings in the data in a manner to be plotted as a profile
        :param component: str, used to filter the profile data and only keep the given component
        :param averaged: bool, average the readings of the profile
        :param converted: bool, convert the station names to int
        :param ontime: bool, keep the on-time channels
        :param incl_deleted: bool, include readings that are flagged as deleted
        :return: pandas DataFrame object with Station as the index, and channels as columns.
        """
        comp_filt = self.data['Component'] == component.upper()
        data = self.data[comp_filt]

        if not incl_deleted:
            data = data[~data.Deleted.astype(bool)]

        if ontime is False:
            data.Reading = data.Reading.map(lambda x: x[~self.channel_times.Remove.astype(bool)])

        profile = pd.DataFrame.from_dict(dict(zip(data.Reading.index, data.Reading.values))).T

        if converted is True:
            stations = data.Station.map(self.converter.convert_station)
        else:
            stations = data.Station

        profile.insert(0, 'Station', stations)
        profile.set_index('Station', drop=True, inplace=True)

        if averaged is True:
            profile = profile.groupby('Station').mean()

        return profile

    def get_components(self):
        components = list(self.data['Component'].unique())
        return components

    def get_stations(self, converted=False):
        """
        Return a list of unique stations in the PEM file.
        :param converted: Bool, whether to convert the stations to Int
        :return: list
        """
        stations = self.data.Station.unique()
        if converted:
            stations = [self.converter.convert_station(station) for station in stations]
        return np.array(stations)

    def get_gps_extents(self):
        """
        Return the minimum and maximum of each dimension of the GPS in the file
        :return: tuple of float, xmin, xmax, ymin, ymax, zmin, zmax
        """
        loop = self.get_loop()

        if self.is_borehole() and self.has_collar_gps():
            collar = self.get_collar()
            segments = self.get_segments()

            if not segments.empty:
                line = BoreholeGeometry(collar, segments).get_projection()
            else:
                line = collar
        else:
            line = self.get_line()

        east = pd.concat([loop.Easting, line.Easting])
        north = pd.concat([loop.Northing, line.Northing])
        elev = pd.concat([loop.Elevation, line.Elevation])

        xmin, xmax, ymin, ymax, zmin, zmax = east.min(), east.max(), north.min(), north.max(), elev.min(), elev.max()
        return xmin, xmax, ymin, ymax, zmin, zmax

    def get_mag_dec(self):
        """
        Calculate the magnetic declination for the PEM file.
        """
        crs = self.get_crs()
        if not crs:
            logger.info(f'{self.filepath.name} No CRS.')
            return

        if self.has_collar_gps():
            coords = self.collar
        elif self.has_loop_gps():
            coords = self.loop
        elif self.has_station_gps():
            coords = self.line
        else:
            logger.error(f'No GPS in {self.filepath.name}')
            return

        assert not coords.df.empty, f"GPS data frame of {self.filepath.name} is empty."
        coords = copy.deepcopy(coords)

        coords.crs = crs
        coords = coords.to_latlon().df
        lat, lon, elevation = coords.iloc[0]['Northing'], coords.iloc[0]['Easting'], coords.iloc[0]['Elevation']

        gm = geomag.geomag.GeoMag()
        mag = gm.GeoMag(lat, lon, elevation)
        return mag

    def get_survey_type(self):
        """
        Return the survey type in title format
        :return: str
        """
        file_survey_type = re.sub('\s+', '_', self.survey_type.casefold())

        if any(['s-coil' in file_survey_type,
                'surface' in file_survey_type,
                'sf_coil' in file_survey_type]):
            survey_type = 'Surface Induction'

        elif any(['borehole' in file_survey_type,
                  'b-rad' in file_survey_type,
                  'b_rad' in file_survey_type,
                  'bh_rad' in file_survey_type,
                  'bh_xy_rad' in file_survey_type,
                  'bh_xy_fast_rad' in file_survey_type,
                  'otool' in file_survey_type,
                  'bh_z' in file_survey_type,
                  'bh_fast_rad' in file_survey_type,
                  'bh_z_probe' in file_survey_type,
                  'xy_magnum' in file_survey_type,
                  'radtool' in file_survey_type]):
            survey_type = 'Borehole Induction'

        elif any(['s-flux' in file_survey_type,
                  'sf_fluxgate' in file_survey_type]):
            survey_type = 'Surface Fluxgate'

        elif any(['bh-flux' in file_survey_type,
                  'bh_fast_fluxgate' in file_survey_type,
                  'bh_fluxgate' in file_survey_type]):
            survey_type = 'Borehole Fluxgate'

        elif 's-squid' in file_survey_type:
            survey_type = 'SQUID'

        else:
            raise ValueError(f"Invalid survey type: {file_survey_type}")

        return survey_type

    def get_repeats(self):
        """
        Return a mask of which stations may be repeat stations.
        :return: dataframe
        """

        def find_repeats(station):
            station_num = re.search('\d+', station).group()
            if station_num[-1] == '1' or station_num[-1] == '4' or station_num[-1] == '6' or station_num[-1] == '9':
                return True
            else:
                return False

        # Set the number of repeat stations
        repeat_mask = self.data.Station.map(find_repeats)
        repeat_data = self.data[repeat_mask]
        return repeat_data

    def get_suffix_mode(self):
        """
        Return the most common station suffix.
        :return: str
        """
        if self.is_borehole():
            return None

        matches = self.data.Station.map(lambda x: re.search(r'[NSEWnsew]', x))
        suffixes = matches.map(lambda x: x.group() if x else x)
        if not suffixes.any():
            logger.info(f"No suffixes found in {self.filepath.name}")
            return None

        mode = suffixes.mode()[0]
        return mode

    def get_suffix_warnings(self):
        """
        Return a data frame of the data whose station suffix is not the mode.
        :return: DataFrame
        """

        df = self.data.iloc[0:0].copy()

        if self.is_borehole():
            return df

        matches = self.data.Station.map(lambda x: re.search(r'[NSEWnsew]', x))
        suffixes = matches.map(lambda x: x.group() if x else x)
        if not suffixes.any():
            logger.info(f"No suffixes found in {self.filepath.name}")
            return df

        mode = suffixes.mode()[0]
        mask = suffixes != mode
        df = self.data[mask]
        return df

    def get_rotation_filtered_data(self):
        """
        Filter the data to only keep readings that have a matching X and Y pair for the same RAD_tool ID.
        :return: tuple, data frame of eligible and ineligible data.
        """

        def filter_data(group):
            """
            Flag the readings to be removed if the group doesn't have a X and Y pair.
            :param group: DataFrame, readings of the same station and same RAD tool ID
            :return: DataFrame
            """
            if group.Component.nunique() < 2:
                # Flag the readings to be removed
                group.Remove = True
            return group

        data = self.data.copy()

        # Add a 'Remove' column, which will be removed later.
        data['Remove'] = False

        # Create a filter for X and Y data only
        xy_filt = (data.Component == 'X') | (data.Component == 'Y')

        # Remove groups that don't have X and Y pairs. For some reason couldn't make it work within rotate_data
        data = data[xy_filt].groupby(['Station', 'RAD_ID'],
                                     group_keys=False,
                                     as_index=False).apply(lambda k: filter_data(k))

        eligible_data = data[~data.Remove.astype(bool)].drop(['Remove'], axis=1)
        ineligible_stations = data[data.Remove].drop(['Remove'], axis=1)
        return eligible_data, ineligible_stations

    def set_crs(self, crs):
        """
        Set the CRS of all GPS objects
        :param crs: CRS object
        """
        logger.info(f"Setting CRS of {self.filepath.name} to {crs.name if crs else 'None'}.")

        self.crs = crs
        self.loop.crs = crs
        if self.is_borehole():
            self.collar.crs = crs
        else:
            self.line.crs = crs

    def to_string(self, legacy=False):
        """
        Return the text format of the PEM file
        :param legacy: bool, if True will strip newer features so it is compatible with Step (such as D5 RAD tool
        lines and remove Timestamp and Deleted values.
        :return: str, Full text of the PEM file
        """
        ps = PEMSerializer()
        text = ps.serialize(self.copy(), legacy=legacy)
        return text

    def to_xyz(self):
        """
        Create a str in XYZ format of the pem file's data
        :return: str
        """

        def get_station_gps(row):
            """
            Add the GPS information for each station
            :param row: pandas DataFrame row
            :return: pandas DataFrame row
            """
            value = row.c_Station
            filt = gps['Station'] == value

            if filt.any():
                row['Easting'] = gps[filt]['Easting'].iloc[0]
                row['Northing'] = gps[filt]['Northing'].iloc[0]
                row['Elevation'] = gps[filt]['Elevation'].iloc[0]
            return row

        df = pd.DataFrame(columns=['Easting', 'Northing', 'Elevation', 'Component', 'Station', 'c_Station'])
        pem_data = self.get_data(sorted=True).dropna(subset=['Station'])

        if self.is_borehole():
            gps = self.get_geometry().get_projection(stations=self.get_stations(converted=True))
            # Rename 'Relative_depth' to 'Station' for get_station_gps, so it matches with
            gps.rename(columns={'Relative_depth': 'Station'}, inplace=True)
        else:
            gps = self.get_line(sorted=True).drop_duplicates('Station')

        # assert not self.is_borehole(), 'Can only create XYZ file with surface PEM files.'
        if gps.empty:
            raise Exception(f"Cannot create XYZ file with {self.filepath.name} because it has no GPS.")

        logger.info(f'Converting {self.filepath.name} to XYZ')

        df['Component'] = pem_data.Component.copy()
        df['Station'] = pem_data.Station.copy()
        df['c_Station'] = df.Station.map(self.converter.convert_station)  # Used to find corresponding GPS

        # Add the GPS
        df = df.apply(get_station_gps, axis=1)

        # Create a dataframe of the readings with channel number as columns
        channel_data = pd.DataFrame(pem_data.Reading.to_dict()).transpose()

        # Merge the two data frames
        df = pd.concat([df, channel_data], axis=1).drop('c_Station', axis=1)
        str_df = df.to_string(index=False)
        return str_df

    def copy(self):
        """
        Create a copy of the PEMFile object
        :return: PEMFile object
        """
        copy_pem = copy.deepcopy(self)
        # Create a copy of the RAD Tool objects, otherwise a deepcopy of a PEMFile object still references the same
        # RADTool objects.
        copy_pem.data.RAD_tool = copy_pem.data.RAD_tool.map(lambda x: copy.deepcopy(x))
        return copy_pem

    def save(self, processed=False, legacy=False, backup=False, tag=''):
        """
        Save the PEM file to a .PEM file with the same filepath it currently has.
        :param processed: bool, Average, split and de-rotate (if applicable) and save in a legacy format.
        :param legacy: bool, will save a legacy version which is compatible with Step.
        :param backup: bool, if the save is for a backup. If so, it will save the PEM file in a [Backup] folder,
        and create the folder if it doesn't exist. The [Backup] folder will be located in the parent directory of the
        PEMFile.
        :param tag: str, tag to be append to the file name. Used for pre-averaging and pre-splitting saves.
        """

        logger.info(f"Saving {self.filepath.name}. (Legacy: {legacy}. Processed: {processed}. Backup: {backup}. "
                    f"Tag: {tag})")

        # Once legacy is saved once, it will always save as legacy.
        if legacy is True:
            self.legacy = True

        if processed is True:
            # Make sure the file is averaged and split and de-rotated
            if not self.is_split():
                self.split()
            if not self.is_averaged():
                self.average()
            if self.is_borehole():
                if self.has_xy() and not self.is_derotated():
                    if not self.prepped_for_rotation:
                        self.prep_rotation()
                    self.rotate('acc')

            # Remove underscore-dates and tags
            file_name = re.sub(r'_\d+', '', re.sub(r'\[-?\w\]', '', self.filepath.name))
            if not self.is_borehole():
                file_name = file_name.upper()
                if file_name.lower()[0] == 'c':
                    file_name = file_name[1:]

            self.filepath = self.filepath.with_name(file_name)

        print(f"self.legacy: {self.legacy}")
        text = self.to_string(legacy=any([processed, legacy, self.legacy]))

        if backup:
            backup_path = self.filepath.parent.joinpath('[Backup]').joinpath(
                self.filepath.stem + tag + self.filepath.suffix)

            # Create a [Backup] folder if it doesn't exist
            if not backup_path.parent.is_dir():
                Path.mkdir(backup_path.parent)

            print(text, file=open(str(backup_path), 'w+'))

        else:
            print(text, file=open(str(self.filepath), 'w+'))

    def average(self):
        """
        Averages the data of the PEM file object. Uses a weighted average.
        :return: PEM file object
        """
        if self.is_averaged():
            logger.info(f"{self.filepath.name} is already averaged.")
            return
        logger.info(f"Averaging {self.filepath.name}.")

        def weighted_average(group):
            """
            Function to calculate the weighted average reading of a station-component group.
            :param group: pandas DataFrame of PEM data for a station-component
            :return: pandas DataFrame of the averaged station-component.
            """
            # Take the first row as a new data frame
            new_data_df = group.iloc[0]
            # Sum the number of stacks column
            new_data_df['Number_of_stacks'] = group['Number_of_stacks'].sum()
            # Add the weighted average of the readings to the reading column
            new_data_df['Reading'] = np.average(group.Reading.to_list(),
                                                axis=0,
                                                weights=group['Number_of_stacks'].to_list())
            return new_data_df

        # Don't use deleted data
        filt = ~self.data.Deleted.astype(bool)

        if not filt.any():
            raise Exception(f"No remaining non-deleted data to average in {self.filepath.name}.")

        # Create a data frame with all data averaged
        df = self.data[filt].groupby(['Station', 'Component']).apply(weighted_average)
        # Sort the data frame
        df = sort_data(df)
        self.data = df
        return self

    def split(self):
        """
        Remove the on-time channels of the PEM file object
        :return: PEM file object with split data
        """
        logger.info(f"Splitting channels for {self.filepath.name}.")
        if self.is_split():
            logger.info(f"{self.filepath.name} is already split.")
            return

        # Only keep the select channels from each reading
        self.data.Reading = self.data.Reading.map(lambda x: x[~self.channel_times.Remove.astype(bool)])
        # Create a filter and update the channels table
        filt = ~self.channel_times.Remove.astype(bool)
        self.channel_times = self.channel_times[filt]
        # Update the PEM file's number of channels attribute
        self.number_of_channels = len(self.channel_times)

        return self

    def scale_coil_area(self, coil_area):
        """
        Scale the data by a change in coil area
        :param coil_area: int: new coil area
        :return: PEMFile object: self with data scaled
        """
        logger.info(f"Scaling coil area of {self.filepath.name} to {coil_area}.")

        new_coil_area = coil_area
        assert isinstance(new_coil_area, int), "New coil area is not type int"
        old_coil_area = self.coil_area

        scale_factor = float(old_coil_area / new_coil_area)

        self.data.Reading = self.data.Reading * scale_factor  # Vectorized
        logger.info(f"{self.filepath.name} coil area scaled to {new_coil_area} from {old_coil_area}.")

        self.coil_area = new_coil_area
        self.notes.append(f'<HE3> Data scaled by coil area change of {old_coil_area}/{new_coil_area}')
        return self

    def scale_current(self, current):
        """
        Scale the data by a change in current
        :param current: float, new current
        :return: PEMFile object, self with data scaled
        """
        new_current = current
        assert isinstance(new_current, float), "New current is not type float"
        logger.info(f"Performing current change for {self.filepath.name} to {current}.")

        old_current = self.current

        scale_factor = float(new_current / old_current)

        self.data.Reading = self.data.Reading * scale_factor  # Vectorized

        self.current = new_current
        self.notes.append(f'<HE3> Data scaled by current change of {new_current}A/{old_current}A')
        return self

    def scale_by_factor(self, factor):
        """
        Scale the data by a change in coil area
        :param factor: float
        :return: PEMFile object, self with data scaled
        """
        assert isinstance(factor, float), "New coil area is not type float"
        # Scale the scale factor to account for compounding
        scaled_factor = factor / (1 + self.total_scale_factor)

        self.data.Reading = self.data.Reading * (1 + scaled_factor)  # Vectorized
        logger.info(f"{self.filepath.name} data scaled by factor of {(1 + scaled_factor)}.")

        self.total_scale_factor += factor

        self.notes.append(f'<HE3> Data scaled by factor of {1 + factor}')
        return self

    def rotate_soa(self, soa):
        """
        Rotate the X and Y by an SOA value.
        :param soa: int
        :return: PEMFile object
        """

        def rotate_data(group, soa):
            """
            Rotate the data for a given reading
            :param group: pandas DataFrame: data frame of the readings to rotate. Must contain at least one
            reading from X and Y components, and the RAD tool values for all readings must all be the same.
            :param soa: int, value to rotate by.
            :return: pandas DataFrame: data frame of the readings with the data rotated.
            """

            def rotate_x(x_values, y_pair, roll_angle):
                """
                Rotate the X data of a reading
                Formula: X' = Xcos(roll) - Ysin(roll)
                :param x_values: list: list of x readings to rotated
                :param y_pair: list: list of paired y reading
                :param roll_angle: float: calculated roll angle
                :return: list: rotated x values
                """
                rotated_x = [x * math.cos(math.radians(roll_angle)) - y * math.sin(math.radians(roll_angle)) for (x, y) in
                             zip(x_values, y_pair)]
                return np.array(rotated_x, dtype=float)

            def rotate_y(y_values, x_pair, roll_angle):
                """
                Rotate the Y data of a reading
                Formula: Y' = Xsin(roll) + Ycos(roll)
                :param y_values: list: list of y readings to rotated
                :param x_pair: list: list of paired x reading
                :param roll_angle: float: calculated roll angle
                :return: list: rotated y values
                """
                rotated_y = [x * math.sin(math.radians(roll_angle)) + y * math.cos(math.radians(roll_angle)) for (x, y) in
                             zip(x_pair, y_values)]
                return np.array(rotated_y, dtype=float)

            def weighted_average(group):
                """
                Function to calculate the weighted average reading of a station-component group.
                :param group: pandas DataFrame of PEM data for a station-component
                :return: np array, averaged reading
                """
                # Sum the number of stacks column
                weights = group['Number_of_stacks'].to_list()
                # Add the weighted average of the readings to the reading column
                averaged_reading = np.average(group.Reading.to_list(),
                                              axis=0,
                                              weights=weights)
                return averaged_reading

            x_data = group[group['Component'] == 'X']
            y_data = group[group['Component'] == 'Y']
            # Save the first reading of each component to be used a the 'pair' reading for rotation
            x_pair = weighted_average(x_data)
            y_pair = weighted_average(y_data)

            x_data.loc[:, 'Reading'] = x_data.loc[:, 'Reading'].map(lambda i: rotate_x(i, y_pair, soa))
            y_data.loc[:, 'Reading'] = y_data.loc[:, 'Reading'].map(lambda i: rotate_y(i, x_pair, soa))
            row = x_data.append(y_data)
            return row

        filtered_data, _ = self.get_rotation_filtered_data()
        logger.info(f"Rotating {self.filepath.name} by SOA of {soa}.")

        # Rotate the data
        rotated_data = filtered_data.groupby(['Station', 'RAD_ID'],
                                             group_keys=False,
                                             as_index=False).apply(lambda l: rotate_data(l, soa))

        xy_filt = (self.data.Component == 'X') | (self.data.Component == 'Y')
        self.data[xy_filt] = rotated_data
        return self

    def rotate(self, method='acc', soa=0):
        """
        Rotate the XY data of the PEM file.
        Formula: X' = Xcos(roll) - Ysin(roll), Y' = Xsin(roll) + Ycos(roll)
        :param method: str: Method of rotation, either 'acc' for accelerometer or 'mag' for magnetic
        :param soa: int: Sensor offset angle
        :return: PEM file object with rotated data
        """
        assert self.is_borehole(), f"{self.filepath.name} is not a borehole file."
        assert self.prepped_for_rotation, f"{self.filepath.name} has not been prepped for rotation."
        logger.info(f"De-rotating data of {self.filepath.name} using {method} with SOA {soa}.")

        def rotate_data(group, method, soa):
            """
            Rotate the data for a given reading
            :param group: pandas DataFrame: data frame of the readings to rotate. Must contain at least one
            reading from X and Y components, and the RAD tool values for all readings must all be the same.
            :param method: str: type of rotation to apply. Either 'acc' for accelerometer or 'mag' for magnetic
            :return: pandas DataFrame: data frame of the readings with the data rotated.
            """

            def rotate_x(x_values, y_pair, roll_angle):
                """
                Rotate the X data of a reading
                Formula: X' = Xcos(roll) - Ysin(roll)
                :param x_values: list: list of x readings to rotated
                :param y_pair: list: list of paired y reading
                :param roll_angle: float: calculated roll angle
                :return: list: rotated x values
                """
                rotated_x = [x * math.cos(math.radians(roll_angle)) - y * math.sin(math.radians(roll_angle)) for (x, y) in
                             zip(x_values, y_pair)]
                return np.array(rotated_x, dtype=float)

            def rotate_y(y_values, x_pair, roll_angle):
                """
                Rotate the Y data of a reading
                Formula: Y' = Xsin(roll) + Ycos(roll)
                :param y_values: list: list of y readings to rotated
                :param x_pair: list: list of paired x reading
                :param roll_angle: float: calculated roll angle
                :return: list: rotated y values
                """
                rotated_y = [x * math.sin(math.radians(roll_angle)) + y * math.cos(math.radians(roll_angle)) for (x, y) in
                             zip(x_pair, y_values)]
                return np.array(rotated_y, dtype=float)

            def get_new_rad(method):
                """
                Create a new RADTool object ready for XY de-rotation based on the rotation method
                :param method: str, either 'acc', 'mag', or 'pp'
                :return: RADTool object
                """

                # PP rotation using cleaned PP
                if method == 'pp':
                    if self.is_fluxgate():
                        roll_angle = rad.measured_pp_roll_angle
                        rot_type = 'pp_raw'
                    else:
                        roll_angle = rad.cleaned_pp_roll_angle
                        rot_type = 'pp_cleaned'

                    # Update the new_rad with the de-rotation information
                    new_info = {'roll_angle': roll_angle,
                                'dip': rad.pp_dip,
                                'R': 'R1',
                                'angle_used': roll_angle,
                                'rotated': True,
                                'rotation_type': rot_type}

                # Accelerometer rotation
                elif method == 'acc':
                    # Update the new_rad with the de-rotation information
                    new_info = {'roll_angle': rad.acc_roll_angle,
                                'dip': rad.acc_dip,
                                'R': 'R3',
                                'angle_used': rad.acc_roll_angle + soa,
                                'rotated': True,
                                'rotation_type': 'acc'}

                # Magnetometer rotation
                elif method == 'mag':
                    # Update the new_rad with the de-rotation information
                    new_info = {'roll_angle': rad.mag_roll_angle,
                                'dip': rad.mag_dip,
                                'R': 'R3',
                                'angle_used': rad.mag_roll_angle + soa,
                                'rotated': True,
                                'rotation_type': 'mag'}

                else:
                    raise ValueError(f"{method} is not a valid de-rotation method.")

                # Set the new attributes to the RAD object
                for key, value in new_info.items():
                    setattr(rad, key, value)
                return rad

            def weighted_average(group):
                """
                Function to calculate the weighted average reading of a station-component group.
                :param group: pandas DataFrame of PEM data for a station-component
                :return: np array, averaged reading
                """
                # Sum the number of stacks column
                weights = group['Number_of_stacks'].to_list()
                # Add the weighted average of the readings to the reading column
                averaged_reading = np.average(group.Reading.to_list(),
                                              axis=0,
                                              weights=weights)
                return averaged_reading

            x_data = group[group['Component'] == 'X']
            y_data = group[group['Component'] == 'Y']
            # Save the first reading of each component to be used a the 'pair' reading for rotation
            x_pair = weighted_average(x_data)
            y_pair = weighted_average(y_data)

            rad = group.iloc[0]['RAD_tool']

            # Create a new RADTool object ready for de-rotating
            new_rad = get_new_rad(method)
            roll_angle = new_rad.angle_used  # Roll angle used for de-rotation

            x_data.loc[:, 'Reading'] = x_data.loc[:, 'Reading'].map(lambda i: rotate_x(i, y_pair, roll_angle))
            y_data.loc[:, 'Reading'] = y_data.loc[:, 'Reading'].map(lambda i: rotate_y(i, x_pair, roll_angle))
            row = x_data.append(y_data)
            # Add the new rad tool series to the row
            row['RAD_tool'] = row['RAD_tool'].map(lambda p: new_rad)
            return row

        global include_pp
        if all([self.has_loop_gps(), self.has_geometry(), self.ramp > 0]):
            include_pp = True
        else:
            include_pp = False
            if method.upper() == 'PP':
                raise ValueError("Cannot perform PP rotation on a PEM file that doesn't have the necessary geometry.")

        logger.info(f"Include PP for {self.filepath.name}: {include_pp}.")
        # Create a filter for X and Y data only
        xy_filt = (self.data.Component == 'X') | (self.data.Component == 'Y')
        filtered_data = self.data[xy_filt]  # Data should have already been filtered by prep_rotation.

        if filtered_data.empty:
            raise Exception(f"{self.filepath.name} has no eligible XY data for de-rotation.")

        # Rotate the data
        rotated_data = filtered_data.groupby(['Station', 'RAD_ID'],
                                             group_keys=False,
                                             as_index=False).apply(lambda l: rotate_data(l, method, soa))

        self.data[xy_filt] = rotated_data
        # Remove the rows that were filtered out in filtered_data
        # self.data.dropna(inplace=True)
        self.probes['SOA'] = str(soa)
        return self

    def prep_rotation(self):
        """
        Prepare the PEM file for probe de-rotation by updating the RAD tool objects with all calculations needed for
        any eligible de-rotation method.
        :return: tuple, updated PEMFile object and data frame of ineligible stations.
        """

        assert self.is_borehole(), f"{self.filepath.name} is not a borehole file."
        logger.info(f"Preparing for XY de-rotation for {self.filepath.name}.")

        def setup_pp():
            """
            Set up the necessary variables used for cleaned PP rotation.
            """
            assert self.has_loop_gps(), f"{self.filepath.name} has no loop GPS."
            assert self.has_geometry(), f"{self.filepath.name} has incomplete geometry."
            assert self.has_collar_gps(), f"{self.filepath.name} has no collar GPS."
            assert self.ramp > 0, f"Ramp must be larger than 0. {self.ramp} was passed for {self.filepath.name}."

            global proj, loop, ramp, mag_calc, ch_times, ch_numbers

            self.pp_table = pd.DataFrame(columns=['Station',
                                                  'Azimuth',
                                                  'Dip',
                                                  'Easting',
                                                  'Northing',
                                                  'Elevation',
                                                  'TPPx',
                                                  'TPPy',
                                                  'TPPz',
                                                  'CPPx',
                                                  'CPPy',
                                                  'CPPz'])
            geometry = BoreholeGeometry(self.collar, self.segments)
            proj = geometry.get_projection(stations=self.get_stations(converted=True))
            loop = self.get_loop(sorted=False, closed=False)
            # Get the ramp in seconds
            ramp = self.ramp / 10 ** 6
            mag_calc = MagneticFieldCalculator(loop)

            # Only keep off-time channels with PP
            ch_times = self.channel_times[~self.channel_times.Remove.astype(bool)]
            # Normalize the channel times so they start from turn off. Look at MRC-067 for proof
            ch_times.loc[:, 'Start':'Center'] = ch_times.loc[:, 'Start':'Center'].applymap(lambda x: x + ramp)

            pp_ch = ch_times.iloc[0]
            # Make sure the PP channel is within the ramp
            assert pp_ch.End < ramp, 'PP channel does not fall within the ramp'
            pp_center = pp_ch['Center']

            # Get the special channel numbers
            ch_numbers = []
            total_time = pp_center
            last_time = ch_times.iloc[-1].End
            # TODO Double check this is done correctly
            while (total_time + ramp) < last_time:
                # Add the ramp time iteratively to the PP center time until reaching the end of the off-time
                total_time += ramp

                # Create a filter to find in which channel the time falls in
                filt = (ch_times['Start'] <= total_time) & (ch_times['End'] > total_time)
                if filt.any():
                    ch_index = ch_times[filt].index.values[0]
                    ch_numbers.append(ch_index)

        def prepare_rad(group):
            """
            Update the RAD Tool object with all calculated angles for rotation.
            :param group: pandas DataFrame: data frame of the readings to rotate. Must contain at least one
            reading from X and Y components, and the RAD tool values for all readings must all be the same.
            :return: pandas DataFrame: group with the RAD_tool objects updated and ready for rotation.
            """

            def calculate_angles(rad):
                """
                Calculate the roll angle for each available method and add it to the RAD tool object.
                :param rad: RADTool object
                """

                def calculate_pp_angles():

                    def get_cleaned_pp(row):
                        """
                        Calculate the cleaned PP value of a station
                        :param row: PEM data DataFrame row
                        :return: float, cleaned PP value
                        """
                        # Get the list of ch_times indexes so the cleaned_pp can be selected by index.
                        # Needed for when channels are split before hand.
                        cleaned_pp_channels = ch_times.index.to_list()

                        cleaned_pp = row.Reading[0]
                        for num in ch_numbers:
                            ind = cleaned_pp_channels.index(num)
                            cleaned_pp += row.Reading[ind]
                        return cleaned_pp

                    # Add the PP information (theoretical PP, cleaned PP, roll angle) to the new RAD Tool object
                    if include_pp is True:
                        segments = self.get_segments()
                        pp_rad_info = dict()

                        # Calculate the raw PP value for each component
                        pp_ch_index = self.channel_times[~self.channel_times.Remove.astype(bool)].index.values[0]
                        measured_ppx = group[group.Component == 'X'].apply(lambda x: x.Reading[pp_ch_index],
                                                                           axis=1).mean()
                        measured_ppy = group[group.Component == 'Y'].apply(lambda x: x.Reading[pp_ch_index],
                                                                           axis=1).mean()
                        ppxy_measured = math.sqrt(sum([measured_ppx ** 2, measured_ppy ** 2]))

                        # Use the segment azimuth and dip of the next segment (as per Bill's cross)
                        # Find the next station. If it's the last station, re-use the last station.
                        stations = list(self.data.Station.unique())
                        current_station = group.Station.unique()[0]
                        current_station_ind = stations.index(current_station)

                        # Re-use the last station if it's the current index
                        if current_station_ind == len(stations) - 1:
                            next_station = current_station
                        else:
                            next_station = stations[current_station_ind + 1]

                        # Calculate the dip and azimuth at the next station, interpolating in case the station
                        # is not in the segments.
                        seg_dip = np.interp(int(next_station), segments.Depth, segments.Dip)
                        seg_azimuth = np.interp(int(next_station), segments.Depth, segments.Azimuth)

                        # Find the location in 3D space of the station
                        filt = proj.loc[:, 'Relative_depth'] == float(group.Station.iloc[0])
                        x_pos, y_pos, z_pos = proj[filt].iloc[0]['Easting'], \
                                              proj[filt].iloc[0]['Northing'], \
                                              proj[filt].iloc[0]['Elevation']

                        # Calculate the theoretical magnetic field strength of each component at that point (in nT/s)
                        Tx, Ty, Tz = mag_calc.calc_total_field(x_pos, y_pos, z_pos,
                                                               amps=self.current,
                                                               out_units='nT/s',
                                                               ramp=ramp)

                        # Rotate the theoretical values into the same frame of reference used with boreholes
                        rTx, rTy, rTz = R.from_euler('Z', -90, degrees=True).apply([Tx, Ty, Tz])

                        # Rotate the theoretical values into the hole coordinate system
                        r = R.from_euler('YZ', [90 - seg_dip, seg_azimuth], degrees=True)
                        rT = r.apply([rTx, rTy, rTz])  # The rotated theoretical values
                        ppxy_theory = math.sqrt(sum([rT[0] ** 2, rT[1] ** 2]))

                        if not self.is_fluxgate():
                            # Calculate the cleaned PP value for each component for non-fluxgate surveys
                            cleaned_PPx = group[group.Component == 'X'].apply(get_cleaned_pp, axis=1).mean()
                            cleaned_PPy = group[group.Component == 'Y'].apply(get_cleaned_pp, axis=1).mean()
                            ppxy_cleaned = math.sqrt(sum([cleaned_PPx ** 2, cleaned_PPy ** 2]))

                            # Calculate the required rotation angle
                            cleaned_pp_roll_angle = math.degrees(
                                math.atan2(rT[1], rT[0]) - math.atan2(cleaned_PPy, cleaned_PPx)
                            )
                            if cleaned_pp_roll_angle < 0:
                                cleaned_pp_roll_angle = cleaned_pp_roll_angle + 360

                            pp_rad_info['ppx_cleaned'] = cleaned_PPx
                            pp_rad_info['ppy_cleaned'] = cleaned_PPy
                        else:
                            cleaned_pp_roll_angle = None
                            ppxy_cleaned = None

                        measured_pp_roll_angle = math.degrees(
                            math.atan2(rT[1], rT[0]) - math.atan2(measured_ppy, measured_ppx))

                        if measured_pp_roll_angle < 0:
                            measured_pp_roll_angle = measured_pp_roll_angle + 360

                        # Update the RAD Tool object with the new information
                        pp_rad_info['azimuth'] = seg_azimuth
                        pp_rad_info['dip'] = seg_dip

                        pp_rad_info['x_pos'] = x_pos
                        pp_rad_info['y_pos'] = y_pos
                        pp_rad_info['z_pos'] = z_pos

                        pp_rad_info['ppx_theory'] = rT[0]
                        pp_rad_info['ppy_theory'] = rT[1]
                        pp_rad_info['ppz_theory'] = rT[2]
                        pp_rad_info['ppx_raw'] = measured_ppx
                        pp_rad_info['ppy_raw'] = measured_ppy
                        pp_rad_info['ppxy_theory'] = ppxy_theory
                        pp_rad_info['ppxy_cleaned'] = ppxy_cleaned
                        pp_rad_info['ppxy_measured'] = ppxy_measured
                        pp_rad_info['cleaned_pp_roll_angle'] = cleaned_pp_roll_angle
                        pp_rad_info['measured_pp_roll_angle'] = measured_pp_roll_angle
                        pp_rad_info['pp_dip'] = -seg_dip

                        for key, value in pp_rad_info.items():
                            setattr(rad, key, value)

                def calculate_acc_angles():
                    if rad.D == 'D5':
                        x, y, z = rad.x, rad.y, rad.z
                    else:
                        x, y, z = rad.gx, rad.gy, rad.gz

                    theta = math.atan2(y, z)
                    cc_roll_angle = 360 - math.degrees(theta) if y < 0 else math.degrees(theta)
                    roll_angle = 360 - cc_roll_angle if y > 0 else cc_roll_angle
                    if roll_angle >= 360:
                        roll_angle = roll_angle - 360
                    elif roll_angle < 0:
                        roll_angle = roll_angle + 360

                    # Calculate the dip
                    dip = math.degrees(math.acos(x / math.sqrt((x ** 2) + (y ** 2) + (z ** 2)))) - 90

                    # Update the new_rad with the de-rotation information
                    new_info = {'acc_roll_angle': roll_angle,
                                'acc_dip': dip}

                    for key, value in new_info.items():
                        setattr(rad, key, value)

                def calculate_mag_angles():
                    if rad.D == 'D5':
                        x, y, z = rad.x, rad.y, rad.z
                    else:
                        x, y, z = rad.Hx, rad.Hy, rad.Hz

                    theta = math.atan2(-y, -z)
                    cc_roll_angle = math.degrees(theta)
                    roll_angle = 360 - cc_roll_angle if y < 0 else cc_roll_angle
                    if roll_angle > 360:
                        roll_angle = roll_angle - 360
                    elif roll_angle < 0:
                        roll_angle = -roll_angle

                    # Calculate the dip
                    dip = -90.  # The dip is assumed to be 90°

                    # Update the new_rad with the de-rotation information
                    new_info = {'mag_roll_angle': roll_angle,
                                'mag_dip': dip}

                    for key, value in new_info.items():
                        setattr(rad, key, value)

                calculate_pp_angles()
                calculate_acc_angles()
                calculate_mag_angles()
                return rad

            rad = group.iloc[0]['RAD_tool']
            # Calculate all the roll angles available and add it to the RAD tool object
            rad = calculate_angles(rad)
            group.RAD_tool = rad
            return group

        if all([self.has_loop_gps(), self.has_geometry(), self.ramp > 0]):
            setup_pp()
            include_pp = True
        else:
            include_pp = False

        # Remove groups that don't have X and Y pairs. For some reason couldn't make it work within rotate_data
        eligible_data, ineligible_data = self.get_rotation_filtered_data()

        if eligible_data.empty:
            raise Exception(f"No eligible data found for probe de-rotation in {self.filepath.name}")

        # Calculate the RAD tool angles
        prepped_data = eligible_data.groupby(['Station', 'RAD_ID'],
                                             group_keys=False,
                                             as_index=False).apply(lambda l: prepare_rad(l))

        xy_filt = (self.data.Component == 'X') | (self.data.Component == 'Y')
        self.data[xy_filt] = prepped_data
        # Remove the rows that were filtered out in filtered_data
        self.data.dropna(subset=['Station'], inplace=True)
        self.prepped_for_rotation = True
        return self, ineligible_data


class PEMParser:
    """
    Class for parsing PEM files into PEMFile objects
    """

    def __init__(self):
        self.filepath = None

    def parse(self, filepath):
        """
        Parses a PEM file to extract all information and creates a PEMFile object out of it.
        :param filepath: string containing path to a PEM file
        :return: A PEM_File object representing the data found inside of filename
        """

        def parse_tags(text):
            cols = [
                'Format',
                'Units',
                'Operator',
                'Probes',
                'Current',
                'Loop dimensions'
            ]
            tags = {}
            text = text.strip().split('\n')

            assert text, f'Error parsing the tags. No matches were found in {self.filepath.name}.'
            assert len(text) == 6, f"{len(text)} tags were found instead of 6 in {self.filepath.name}"

            tags['Format'] = text[0].split('>')[1].strip()
            tags['Units'] = text[1].split('>')[1].strip()
            tags['Operator'] = text[2].split('>')[1].strip().title()
            tags['Probes'] = text[3].split('>')[1].strip()
            tags['Current'] = float(text[4].split('>')[1].strip())
            tags['Loop dimensions'] = text[5].split('>')[1].strip()

            # Format the units
            if tags['Units'] == 'nanoTesla/sec':
                tags['Units'] = 'nT/s'
            elif tags['Units'] == 'picoTesla' or tags['Units'] == 'picoTeslas':
                tags['Units'] = 'pT'

            # Format the operator name, removing the '~'
            if '~' in tags['Operator']:
                tags['Operator'] = tags['Operator'].split('~')[0].strip()

            # Format the probe numbers
            probe_cols = ['XY probe number', 'SOA', 'Tool number', 'Tool ID']
            tags['Probes'] = dict(zip(probe_cols, tags['Probes'].split()))

            return tags

        def parse_loop(text):
            """
            Parse the loop section (<L> tags) of the PEM File
            :param text: str, raw loop string from the PEM file
            :return: list of everything in the <L> tag section
            """
            assert text, f'Error parsing the loop coordinates. No matches were found in {self.filepath.name}.'

            text = text.strip().split('\n')
            loop_text = [t.strip().split() for t in text if t.startswith('<L')]
            return loop_text

        def parse_line(text):
            """
            Parse the line section (<P> tags) of the PEM File
            :param text: str, raw line string from the PEM file
            :return: list of everything in the <P> tag section
            """
            assert text, f'Error parsing the line coordinates. No matches were found in {self.filepath.name}.'

            text = text.strip().split('\n')
            line_text = [t.strip().split() for t in text if t.startswith('<P')]
            return line_text

        def parse_notes(file):
            """
            Parse the notes of the PEM File, which are any lines with <GEN> or <HE> tags.
            :param file: str of the .PEM file
            :return: list of notes
            """
            notes = re.findall(r'<GEN>.*|<HE\d>.*|<CRS>.*', file)
            # Remove the 'xxxxxxxxxxxxxxxx' notes
            for note in reversed(notes):
                if 'xxx' in note.lower() or re.match('<GEN> NOTES', note):
                    notes.remove(note)

            return notes

        def parse_header(text):
            """
            Parse the header section of the PEM File, which is the client name down to the channel table.
            :param text: str, raw header string from the PEM file
            :return: dictionary of the header items
            """

            assert text, f'Error parsing the tags. No matches were found in {self.filepath.name}.'

            text = text.strip().split('\n')
            # Remove any Note tags
            for t in reversed(text):
                if t.startswith('<'):
                    text.remove(t)

            assert len(text) == 7, f"{len(text)} header lines were found instead of 7 in {self.filepath.name}"

            header = dict()

            header['Client'] = text[0]
            header['Grid'] = text[1]
            header['Line_name'] = text[2]
            header['Loop_name'] = text[3]
            header['Date'] = text[4]

            survey_param = text[5].split()
            receiver_param = text[6].split()

            assert len(survey_param) == 7, \
                f"{len(survey_param)} survey parameters were found instead of 7 in {self.filepath.name}"

            assert len(receiver_param) >= 7, \
                f"{len(receiver_param)} receiver parameters were found instead of 7 or 8 in {self.filepath.name}"

            header['Survey type'] = survey_param[0]
            header['Convention'] = survey_param[1]
            header['Sync'] = survey_param[2]
            header['Timebase'] = float(survey_param[3])
            header['Ramp'] = float(survey_param[4])
            header['Number of channels'] = int(survey_param[5])
            header['Number of readings'] = int(survey_param[6])

            header['Receiver number'] = receiver_param[0]
            header['Rx software version'] = receiver_param[1]
            header['Rx software version date'] = receiver_param[2]
            header['Rx file name'] = receiver_param[3]
            header['Normalized'] = receiver_param[4]
            header['Primary field value'] = receiver_param[5]
            header['Coil area'] = float(receiver_param[6])
            if len(receiver_param) > 7:
                header['Loop polarity'] = receiver_param[7]

            return header

        def parse_channel_times(text, units=None, num_channels=None):
            """
            Create a DataFrame of the channel times from the PEM file.
            :param text: str, channel times section in the PEM file, above the data section.
            :param units: str, nT/s or pT, used to know which channel is the ramp channel.
            :param num_channels: int, number of channels indicated in the PEM file header. Used to make sure all
            channels are accounted for.
            :return: DataFrame
            """

            def channel_table(channel_times):
                """
                Channel times table data frame with channel start, end, center, width, and whether the channel is
                to be removed when the file is split
                :param channel_times: pandas Series, float of each channel time read from a PEM file header.
                :return: pandas DataFrame
                """

                def check_removable(row):
                    """
                    Return True if the passed channel times is a channel that should be removed when the file is split.
                    :param row: pandas row from the channel table
                    :return: bool: True if the channel should be removed, else False.
                    """
                    if units == 'nT/s':
                        if row.Start == -0.0002:
                            return False
                        elif row.Start > 0:
                            return False
                        else:
                            return True

                    elif units == 'pT':
                        if row.Start == -0.002:
                            return False
                        elif row.Start > 0:
                            return False
                        else:
                            return True
                    else:
                        raise ValueError('Units parsed from tags is invalid')

                def find_last_off_time():
                    """
                    Find where the next channel width is less than half the previous channel width, which indicates
                    the start of the next on-time.
                    :return: int: Row index of the last off-time channel
                    """
                    filt = ~table['Remove'].astype(bool)
                    for index, row in table[filt][1:-1].iterrows():
                        next_row = table.loc[index + 1]
                        if row.Width > (next_row.Width * 2):
                            return index + 1

                # Create the channel times table
                table = pd.DataFrame(columns=['Start', 'End', 'Center', 'Width', 'Remove'])
                # Convert the times to miliseconds
                times = channel_times

                # The first number to the second last number are the start times
                table['Start'] = list(times[:-1])
                # The second number to the last number are the end times
                table['End'] = list(times[1:])
                table['Width'] = table['End'] - table['Start']
                table['Center'] = (table['Width'] / 2) + table['Start']

                # PEM files seem to always have a repeating channel time as the third number, so the second row
                # must be removed.
                table.drop(1, inplace=True)
                table.reset_index(drop=True, inplace=True)

                # If the file is a PP file
                if table.Width.max() < 10 ** -5:
                    table['Remove'] = False
                else:
                    # Configure which channels to remove for the first on-time
                    table['Remove'] = table.apply(check_removable, axis=1)

                    # Configure each channel after the last off-time channel (only for full waveform)
                    last_off_time_channel = find_last_off_time()
                    if last_off_time_channel:
                        table.loc[last_off_time_channel:, 'Remove'] = table.loc[last_off_time_channel:, 'Remove'].map(
                            lambda x: True)
                return table

            assert text, f'Error parsing the channel times. No matches were found in {self.filepath.name}.'

            table = channel_table(np.array(text.split(), dtype=float))
            assert len(table) == num_channels or len(table) == num_channels + 1, \
                f"{len(table)} channels found in channel times section instead of {num_channels} found in header of {self.filepath.name}"
            return table

        def parse_data(text):
            """
            Parse the data section of the PEM file.
            :param text: str, data section after the '$' in the PEM file
            :return: DataFrame of the data
            """

            cols = [
                'Station',
                'Component',
                'Reading_index',
                'Gain',
                'Rx_type',
                'ZTS',
                'Coil_delay',
                'Number_of_stacks',
                'Readings_per_set',
                'Reading_number',
                'RAD_tool',
                'Reading',
                'Deleted',
                'Overload',
                'Timestamp',
            ]

            def format_data(reading):
                """
                Format the data row so it is ready to be added to the data frame
                :param reading: str of a reading in a PEM file
                :return: list
                """
                data = reading.split('\n')
                head = data[0].split()

                station = head[0]
                comp = head[1][0]
                reading_index = re.search(r'\d+', head[1]).group()
                gain = head[2]
                rx_type = head[3]
                zts = head[4]
                coil_delay = head[5]
                num_stacks = head[6]
                readings_per_set = head[7]
                reading_number = head[8]

                rad_tool = data[1]
                decay = ''.join(data[2:])

                result = [station, comp, reading_index, gain, rx_type, zts, coil_delay, num_stacks, readings_per_set,
                          reading_number, rad_tool, decay]

                # Add the new columns from DMP2 files
                if len(head) > 9:
                    Deleted = True if head[9] == 'True' else False
                    overload = True if head[10] == 'True' else False
                    timestamp = head[11]
                    result.extend([Deleted, overload, timestamp])

                return result

            assert text, f'No data found in {self.filepath.name}.'

            # Each reading is separated by two return characters
            text = text.strip().split('\n\n')

            data = []
            # Format each reading to be added to the data frame. Faster than creating Series object per row.
            for reading in text:
                data.append(format_data(reading))

            # Create the data frame
            df = pd.DataFrame(data, columns=cols[:np.array(data).shape[1]])

            # Format the columns of the data frame
            # Create a RAD tool ID number to be used for grouping up readings for probe rotation, since the CDR2
            # and CDR3 don't count reading numbers the same way.
            df['RAD_tool'] = df['RAD_tool'].map(lambda x: RADTool().from_match(x))
            df.insert(list(df.columns).index('RAD_tool') + 1, 'RAD_ID', df['RAD_tool'].map(lambda x: x.id))
            df['Reading'] = df['Reading'].map(lambda x: np.array(x.split(), dtype=float))
            df[['Reading_index',
                'Gain',
                'Coil_delay',
                'Number_of_stacks',
                'Readings_per_set',
                'Reading_number']] = df[['Reading_index',
                                         'Gain',
                                         'Coil_delay',
                                         'Number_of_stacks',
                                         'Readings_per_set',
                                         'Reading_number']].astype(int)
            df['ZTS'] = df['ZTS'].astype(float)

            # Format the extra DMP2 columns
            if len(df.columns) == 16:

                def get_time(timestamp):
                    if timestamp != 'None':
                        if 'AM' in timestamp or 'PM' in timestamp:
                            fmt = '%Y-%m-%d_%I:%M:%S_%p'
                        else:
                            fmt = '%Y-%m-%d_%H:%M:%S'
                        obj = datetime.strptime(timestamp, fmt)
                        return obj
                    else:
                        return None

                df[['Deleted', 'Overload']] = df[['Deleted', 'Overload']].astype(bool)
                df['Timestamp'] = df['Timestamp'].map(get_time)
            return df

        assert Path(filepath).exists(), f"{Path(filepath)} does not exist."
        self.filepath = Path(filepath)
        logger.info(f"Parsing {self.filepath.name}")

        with open(filepath, "rt") as file:
            contents = file.readlines()

        # Remove the ~ comments from files converted with Bill's software, makes breaking up the file for parsing easier
        for i, line in enumerate(contents):
            if '~' in line:
                # Don't remove the transmitter and hole tag lines
                if re.match('~ Transmitter.*', line) or re.match('~ Hole.*', line) or re.match('~\n', line):
                    continue
                # Keep one last ~ for sectioning the header
                elif re.match('~Tags for headings.*', line):
                    contents[i] = re.sub('(~.*)', '~', line)
                else:
                    contents[i] = re.sub('(~.*)', '', line)

        contents = ''.join(contents)
        # Break the file up into sections
        scontents = contents.split('~')
        raw_tags = scontents[0]
        raw_loop = scontents[1]
        raw_line = scontents[2]
        raw_header = scontents[3].split('\n\n')[0]
        raw_channel_times = scontents[3].split('\n\n')[1].split('$')[0]
        raw_data = scontents[3].split('$')[1].strip()

        tags = parse_tags(raw_tags)
        loop_coords = parse_loop(raw_loop)
        line_coords = parse_line(raw_line)
        notes = parse_notes(contents)
        header = parse_header(raw_header)
        channel_table = parse_channel_times(raw_channel_times,
                                            units=tags.get('Units'),
                                            num_channels=header.get('Number of channels'))
        data = parse_data(raw_data)

        pem_file = PEMFile().from_pem(tags, loop_coords, line_coords, notes, header, channel_table, data,
                                      filepath=filepath)
        return pem_file


class DMPParser:

    def __init__(self):
        """
        Class that parses .DMP and .DMP2 files into PEMFile objects.
        """
        self.filepath = None
        self.pp_file = False

        self.data_columns = [
            'Station',
            'Component',
            'Reading_index',
            'Gain',
            'Rx_type',
            'ZTS',
            'Coil_delay',
            'Number_of_stacks',
            'Readings_per_set',
            'Reading_number',
            'RAD_tool',
            'Reading'
        ]

    def parse_dmp(self, filepath):
        """
        Create a PEMFile object by parsing a .DMP file.
        :param filepath: str, filepath of the .DMP file
        :return: PEMFile object
        """

        def parse_header(text, old_dmp=False):
            """
            Create the header dictionary that is found in PEM files from the contents of the .DMP file.
            :param text: str or list, header section of the .DMP file.
            :param old_dmp: bool, if the file is an old version of the DMP file which lacks two lines.
            :return: dict
            """
            assert text, f'No header found in {self.filepath.name}.'

            if isinstance(text, str):
                text = text.strip().split('\n')
            text = [t.strip() for t in text]

            if old_dmp is True:
                assert len(text) == 27, f'Incorrect number of lines found in the header of {self.filepath.name}'
            else:
                assert len(text) == 29, f'Incorrect number of lines found in the header of {self.filepath.name}'

            if text[-1] == 'ZTS - Narrow':
                self.pp_file = True

            header = dict()
            header['Format'] = str(210)
            header['Units'] = 'pT' if 'flux' in text[6].lower() or 'squid' in text[6].lower() else 'nT/s'
            header['Operator'] = text[11]
            header['Probes'] = {'XY probe number': '0', 'SOA': '0', 'Tool number': '0', 'Tool ID': '0'}
            header['Current'] = float(text[12])
            header['Loop dimensions'] = ' '.join(re.split(r'\D', text[13])) + ' 0'

            header['Client'] = text[8]
            header['Grid'] = text[9]
            header['Line_name'] = text[7]
            header['Loop_name'] = text[10]
            header['Date'] = datetime.strptime(re.sub(r'\s+', '', text[14]), '%m/%d/%y').strftime('%B %d, %Y')
            header['Survey type'] = re.sub('\s+', '_', text[6].casefold())
            header['Convention'] = text[15]
            header['Sync'] = text[18]
            header['Timebase'] = float(text[16].split('ms')[0]) if 'ms' in text[16] else float(text[16].split()[0])
            header['Ramp'] = float(text[17])
            header['Number of channels'] = int(text[25])
            header['Number of readings'] = int(text[24])
            header['Receiver number'] = text[1].split()[-1]
            header['Rx software version'] = text[2].split()[-1]
            header['Rx software version date'] = re.sub(r'\s', '',
                                                        re.sub('Released: ', '', text[3])) + f"s{text[26]}"
            header['Rx file name'] = text[5]
            header['Normalized'] = 'N' if text[19] == 'Norm.' else 'Normalized??'
            header['Primary field value'] = text[23]
            header['Coil area'] = float(text[20])
            header['Coil delay'] = int(text[21])
            header['Loop polarity'] = '+'

            return header

        def parse_channel_times(text, units=None):
            """
            Convert the channel table in the .DMP file to a PEM channel times table DataFrame
            :param text: str or list, raw channel table information in the .DMP file
            :param units: str, 'nT/s' or 'pT'
            :return: DataFrame
            """

            def channel_table(channel_times):
                """
                Channel times table data frame with channel start, end, center, width, and whether the channel is
                to be removed when the file is split
                :param channel_times: numpy array with shape (, 2), float of each channel start and end time.
                :return: pandas DataFrame
                """

                def check_removable(row):
                    """
                    Return True if the passed channel times is a channel that should be removed when the file is split.
                    :param row: pandas row from the channel table
                    :return: bool: True if the channel should be removed, else False.
                    """
                    if units == 'nT/s':
                        if row.Start == -0.0002:
                            return False
                        elif row.Start > 0:
                            return False
                        else:
                            return True

                    elif units == 'pT':
                        if row.Start == -0.002:
                            return False
                        elif row.Start > 0:
                            return False
                        else:
                            return True
                    else:
                        raise ValueError('Units parsed from tags is invalid')

                def find_last_off_time():
                    """
                    Find where the next channel width is less than half the previous channel width, which indicates
                    the start of the next on-time.
                    :return: int: Row index of the last off-time channel
                    """
                    filt = ~table['Remove'].astype(bool)
                    for index, row in table[filt][1:-1].iterrows():
                        next_row = table.loc[index + 1]
                        if row.Width > (next_row.Width * 2):
                            return index + 1

                # Create the channel times table
                table = pd.DataFrame(columns=['Start', 'End', 'Center', 'Width', 'Remove'])
                times = channel_times

                # The first number to the second last number are the start times
                table['Start'] = times[:, 0] / 10 ** 6  # Convert to seconds
                # The second number to the last number are the end times
                table['End'] = times[:, 1] / 10 ** 6  # Convert to seconds
                table['Width'] = table['End'] - table['Start']
                table['Center'] = (table['Width'] / 2) + table['Start']

                if self.pp_file is False:
                    # Configure which channels to remove for the first on-time
                    table['Remove'] = table.apply(check_removable, axis=1)

                    # Configure each channel after the last off-time channel (only for full waveform)
                    last_off_time_channel = find_last_off_time()
                    if last_off_time_channel:
                        table.loc[last_off_time_channel:, 'Remove'] = table.loc[last_off_time_channel:, 'Remove'].map(lambda x: True)
                else:
                    table['Remove'] = False
                return table

            assert text, f'No channel times found in {self.filepath.name}.'

            text = text.strip().split('\n')
            # text = np.array([t.strip().split() for t in text], dtype=float)
            text = np.array(' '.join([t.strip() for t in text]).split(), dtype=float)

            # elif isinstance(text, list):
            #     text = np.array(text)

            # Reshape the channel times to be 3 columns (channel number, start-time, end-time)
            times = text.reshape((int(len(text) / 3), 3))

            # Used to add the gap channel, but not sure if needed.
            if self.pp_file is False:
                # Find the index of the gap 0 channel
                global ind_of_0  # global index since the 0 value must be inserted into the decays
                ind_of_0 = list(times[:, 0]).index(1)
                # Add the gap channel
                times = np.insert(times, ind_of_0, [0., times[ind_of_0-1][2], 0.], axis=0)

            # Remove the channel number column
            times = np.delete(times, 0, axis=1)

            table = channel_table(times)
            return table

        def parse_notes(text):
            """
            Return a list of notes from the .DMP file, excluding 'xxxxxxxxxxxxxxxx' entries.
            :param text: str or list, raw test from the notes section of the .DMP file.
            :return: list of notes
            """
            if isinstance(text, str):
                text = text.split()

            notes = []
            for item in text:
                # Get rid of the 'xxxxxxxxxxxxxxxx' notes
                if 'xxx' not in item.lower():
                    notes.append(item)
            return notes

        def parse_data(text, header):
            """
            Create the PEM file DataFrame of the data in the .DMP file
            :param text: str, raw string of the data section of the .DMP file
            :param header: dict, the parsed header section of the .DMP file
            :return: DataFrame
            """

            def format_data(reading):
                """
                Format the data row so it is ready to be added to the data frame
                :param reading: str of a reading in a PEM file
                :return: list
                """
                contents = reading.split('\n')

                head = contents[0].split()
                station = head[0]
                comp = head[1][0]
                reading_index = re.search(r'\d+', head[1]).group()
                zts = float(head[2]) + ramp
                number_of_stacks = head[3]
                readings_per_set = head[4]
                reading_number = head[5]
                rad_tool = contents[1]

                # Used to add the gap channel, but not sure if needed.
                # if self.pp_file is True:
                #     decay = np.array(''.join(contents[2:]).split(), dtype=float) * 10 ** 9
                # else:

                # Add the 0 gap
                if self.pp_file is False:
                    decay = ' '.join(
                        np.insert(np.array(''.join(contents[2:]).split(), dtype=float), ind_of_0, 0.0).astype(str)
                    )
                else:
                    decay = ''.join(contents[2:])

                return [station, comp, reading_index, gain, rx_type, zts, coil_delay, number_of_stacks,
                        readings_per_set, reading_number, rad_tool, decay]

            assert text, f'No data found in {self.filepath.name}.'

            if isinstance(text, list):
                text = '\n'.join(text)

            # Reading variables that are sourced from outside the data section of the .DMP file
            global rx_type, gain, coil_delay, ramp
            rx_type = 'A'
            gain = 0
            coil_delay = header.get('Coil delay')
            ramp = header.get('Ramp')

            # Replace the spaces infront of station names with a tab character, to more easily split after
            text = re.sub(r'\s{3,}(?P<station>[\w]{1,}\s[XYZ])', r'\t\g<station>', text.strip())
            text = text.split('\t')

            data = []
            for reading in text:
                # Parse the data row and create a Series object to be inserted in the data frame
                # series = parse_row(reading)
                data.append(format_data(reading))

            df = pd.DataFrame(data, columns=self.data_columns)

            # Convert the columns to their correct data types
            df['RAD_tool'] = df['RAD_tool'].map(lambda x: RADTool().from_dmp(x))
            df['RAD_ID'] = df['RAD_tool'].map(lambda x: x.id)

            # Convert the decay units to nT/s or pT
            factor = 10 ** 12 if header.get('Units') == 'pT' else 10 ** 9
            df['Reading'] = df['Reading'].map(lambda x: np.array(x.split(), dtype=float) * factor)
            df[['Reading_index',
                'Gain',
                'Coil_delay',
                'Number_of_stacks',
                'Readings_per_set',
                'Reading_number']] = df[['Reading_index',
                                         'Gain',
                                         'Coil_delay',
                                         'Number_of_stacks',
                                         'Readings_per_set',
                                         'Reading_number']].astype(int)
            df['ZTS'] = df['ZTS'].astype(float)
            return df

        if isinstance(filepath, str):
            filepath = Path(filepath)

        assert filepath.is_file(), f"{filepath.name} is not a file"
        self.filepath = filepath
        logger.info(f"Parsing {self.filepath.name}.")

        # Read the contents of the file
        with open(filepath, 'rt') as file:
            contents = file.read()

        # Split the content up into sections
        # Splitting new .DMP files
        if '&&' in contents:
            logger.info(f"{self.filepath.name} is a new style DMP file.")
            old_dmp = False
            raw_header = re.split('&&', contents)[0].strip()
            raw_channel_table = re.split('<<', re.split(r'\$\$', contents)[0])[1].strip()
            raw_notes = re.split('<<', re.split('&&', contents)[1])[0].strip()  # The content between '&&' and '<<'
            raw_data = re.split(r'\$\$', contents)[1].strip()

            # Don't see any notes in old .DMP files so only included here
            notes = parse_notes(raw_notes)

        # Splitting old .DMP files
        else:
            logger.info(f"{self.filepath.name} is an old style DMP file.")
            old_dmp = True
            scontents = contents.split('\n')
            num_ch = int(scontents[25].strip())

            raw_header = scontents[:27]
            raw_channel_table = '\n'.join(scontents[27:27 + math.ceil(num_ch / 2)]).strip()
            raw_data = '\n'.join(scontents[27 + math.ceil(num_ch / 2):]).strip()

            notes = []

        if not raw_header:
            raise ValueError(f'No header found in {self.filepath.name}.')
        elif not raw_data:
            raise ValueError(f'No data found in {self.filepath.name}.')

        # Parse the sections into nearly what they should be in the PEM file
        header = parse_header(raw_header, old_dmp=old_dmp)
        channel_table = parse_channel_times(raw_channel_table, units=header.get('Units'))
        data = parse_data(raw_data, header)

        header_readings = int(header.get('Number of readings'))
        assert len(data) == header_readings, \
            f"{self.filepath.name}: Header claims {header_readings} readings but {len(data)} was found."

        pem_file = PEMFile().from_dmp(header, channel_table, data, self.filepath, notes=notes)
        return pem_file, pd.DataFrame()  # Empty data_error data frame. Errors not implemented yet for .DMP files.

    def parse_dmp2(self, filepath):
        """
        Create a PEMFile object by parsing a .DMP2 file.
        :param filepath: str, filepath of the .DMP2 file
        :return: PEMFile object
        """
        def parse_channel_times(units=None):
            """
            Convert the channel table in the .DMP file to a PEM channel times table DataFrame
            :param units: str, 'nT/s' or 'pT'
            :return: DataFrame
            """

            def channel_table(channel_times):
                """
                Channel times table data frame with channel start, end, center, width, and whether the channel is
                to be removed when the file is split
                :param channel_times: pandas Series, float of each channel time read from a PEM file header.
                :return: pandas DataFrame
                """

                def check_removable(row):
                    """
                    Return True if the passed channel times is a channel that should be removed when the file is split.
                    :param row: pandas row from the channel table
                    :return: bool: True if the channel should be removed, else False.
                    """
                    if units == 'nT/s':
                        if row.Start == -0.0002:
                            return False
                        elif row.Start > 0:
                            return False
                        else:
                            return True

                    elif units == 'pT':
                        if row.Start == -0.002:
                            return False
                        elif row.Start > 0:
                            return False
                        else:
                            return True
                    else:
                        raise ValueError('Units parsed from tags is invalid')

                def find_last_off_time():
                    """
                    Find where the next channel width is less than half the previous channel width, which indicates
                    the start of the next on-time.
                    :return: int: Row index of the last off-time channel
                    """
                    filt = ~table['Remove'].astype(bool)
                    for index, row in table[filt][1:-1].iterrows():
                        next_row = table.loc[index + 1]
                        if row.Width > (next_row.Width * 2):
                            return index + 1

                # Create the channel times table
                table = pd.DataFrame(columns=['Start', 'End', 'Center', 'Width', 'Remove'])
                # Convert the times to miliseconds
                times = channel_times

                # The first number to the second last number are the start times
                table['Start'] = list(times[:-1])
                # The second number to the last number are the end times
                table['End'] = list(times[1:])
                table['Width'] = table['End'] - table['Start']
                table['Center'] = (table['Width'] / 2) + table['Start']

                # If the file is a PP file
                if table.Width.max() < 10 ** -4:
                    table['Remove'] = False
                else:
                    # Configure which channels to remove for the first on-time
                    table['Remove'] = table.apply(check_removable, axis=1)

                    # Configure each channel after the last off-time channel (only for full waveform)
                    last_off_time_channel = find_last_off_time()
                    if last_off_time_channel:
                        table.loc[last_off_time_channel:, 'Remove'] = table.loc[last_off_time_channel:, 'Remove'].map(
                            lambda x: True)
                return table

            table = channel_table(header['Channel_times'] / 10 ** 6)  # Convert to seconds
            header_channels = int(header['Number of channels'])
            assert len(table) == header_channels or len(table) == header_channels + 1, \
                f"{self.filepath.name}: Header claims {header_channels} channels but {len(table)} found."
            return table

        def parse_header(header_content):
            """
            Parse the header section of the DMP File
            :param header_content: list of str of the header section of the .DMP2 file
            :return: dict
            """
            header_content = header_content.split('\n')
            # Remove blank lines
            [header_content.remove(h) for h in reversed(header_content) if h == '']
            ind, val = [h.split(':')[0].strip() for h in header_content], [h.split(':')[1].strip() for h in header_content]

            # Create a Series object
            s = pd.Series(val, index=ind)

            s['Channel_Number'] = np.array(s['Channel_Number'].split(), dtype=int)
            s['Channel_Time'] = np.array(s['Channel_Time'].split(), dtype=float)

            # Create the header dictionary
            header = dict()
            header['Format'] = '210'
            header['Units'] = 'pT' if 'flux' in s['Survey_Type'].lower() or 'squid' in s['Survey_Type'].lower() else 'nT/s'
            header['Operator'] = s['Operator_Name'].title()
            header['Probes'] = {'XY probe number': s['Sensor_Number'],
                                'SOA': '0',
                                'Tool number': s['Tool_Number'],
                                'Tool ID': '0'}
            header['Current'] = float(s['Current'])

            header['Channel_times'] = s['Channel_Time']
            header['Channel_numbers'] = s['Channel_Number']
            header['Loop dimensions'] = f"{s['Loop_Length']} {s['Loop_Width']} 0"

            header['Client'] = s['Client_Name']
            header['Grid'] = s['Grid_Name']
            header['Line_name'] = s['name']
            header['Loop_name'] = s['Loop_Name']
            header['Date'] = date_str

            header['Survey type'] = re.sub(r'\s+', '_', s['Survey_Type'])
            header['Convention'] = 'Metric'
            header['Sync'] = re.sub(r'\s+', '-', s['Sync_Type'])
            header['Timebase'] = float(s['Time_Base'].split()[0])
            header['Ramp'] = float(s['Ramp_Length'])
            header['Number of channels'] = len(s['Channel_Time']) - 1
            header['Number of readings'] = int(s['Total_Readings'])

            header['Receiver number'] = s['Crone_Digital_PEM_Receiver']
            header['Rx software version'] = s['Software_Version']
            header['Rx software version date'] = re.sub(r'\s+', '', s['Software_Release_Date'])
            header['Rx file name'] = re.sub(r'\s+', '_', s['File_Name'])
            header['Normalized'] = 'N'
            header['Primary field value'] = '1000'

            coil_area = float(s['Coil_Area'])
            if coil_area > 50000:
                coil_area = coil_area / 10 ** 3  # For fluxgate files
            header['Coil area'] = coil_area
            header['Loop polarity'] = '+'
            # TODO Find how notes are saved in .DMP2 files
            # header['Notes'] = [note for note in s['File_Notes'].split('\n')]

            return header

        def parse_data(data_content, units=None):
            """
            Create a PEM file data frame from the contents of the .DMP2 file
            :param data_content: list of str of the data section of the .DMP2 file
            :param units: str, 'nT/s' or 'pT'
            :return: DataFrame
            """

            def str_to_datetime(date_string):
                """
                Convert the timestamp string to a datetime object
                :param date_string: str of the timestamp from the .DMP2 file.
                :return: datetime object
                """
                if '-' in date_string:
                    if 'AM' in date_string or 'PM' in date_string:
                        fmt = '%Y-%m-%d,%I:%M:%S %p'
                    else:
                        fmt = '%Y-%m-%d,%H:%M:%S'
                else:
                    year = re.search(r'(\d+\W\d+\W)(\d+)', date_string).group(2)
                    if len(year) == 2:
                        year_fmt = 'y'
                    else:
                        year_fmt = 'Y'

                    if 'AM' in date_string or 'PM' in date_string:
                        fmt = f'%m/%d/%{year_fmt},%I:%M:%S %p'
                    else:
                        fmt = f'%m/%d/%{year_fmt},%H:%M:%S'
                date_object = datetime.strptime(date_string, fmt)
                return date_object

            assert data_content, f'No data found in {self.filepath.name}.'

            data_section = data_content.strip()
            sdata = data_section.split('\n\n')

            # Create a data frame out of the readings
            df_data = []
            for reading in sdata:
                split_reading = reading.split('\n')

                # Take the array that doesn't change per reading
                arr = [re.split(r':\s?', d, maxsplit=1) for d in split_reading if
                       not d.lower().startswith('data') and
                       not d.lower().startswith('overload') and
                       not d.lower().startswith('deleted')]

                # Separate the decay reading, overload and deleted status that should be their own readings
                datas = [x for x in split_reading if x.startswith('data')]
                overloads = [x for x in split_reading if x.lower().startswith('overload')]
                deletes = list(filter(lambda x: x.startswith('Deleted'), split_reading))[0].split(': ')[1].split(',')

                # Iterate over each actual decay reading and create their own dictionary to be added to the df
                for data, overload, deleted in zip(datas, overloads, deletes):
                    entry = dict(arr)  # The base information that is true for each reading
                    entry['Component'] = data[4].upper()  # The component is the 4th character in the 'data' title
                    entry['data'] = data.split(': ')[1]
                    entry['Overload'] = overload.split(': ')[1]
                    entry['Deleted'] = deleted.strip()

                    df_data.append(entry)

            # Create a data frame from the DMP file
            df = pd.DataFrame(df_data)
            # Convert the columns to the correct data type
            df[['Number_of_Readings',
                'Number_of_Stacks',
                'Reading_Number',
                'ZTS_Offset']] = df[['Number_of_Readings',
                                     'Number_of_Stacks',
                                     'Reading_Number',
                                     'ZTS_Offset']].astype(int)

            # Convert the decays from Teslas to either nT or pT
            factor = 10 ** 12 if units == 'pT' else 10 ** 9
            df['data'] = df['data'].map(lambda x: np.array(x.split(), dtype=float) * factor)
            if 'RAD' in df.columns.values:
                df['RAD'] = df['RAD'].map(lambda x: RADTool().from_dmp(x))
            else:
                logger.warning(f"No RAD tool data found in {self.filepath.name}. Creating 0s instead.")
                df['RAD'] = RADTool().from_dmp('0. 0. 0. 0. 0. 0. 0.')

            # Create the PEM file data frame
            pem_df = pd.DataFrame(columns=self.data_columns)
            pem_df['Station'] = df['name'].map(lambda x: x.split(',')[0])
            pem_df['Component'] = df['Component']
            pem_df['Reading_index'] = df['name'].map(lambda x: x.split(',')[-1][1:]).astype(int)
            pem_df['Gain'] = 0
            pem_df['Rx_type'] = 'A'
            pem_df['ZTS'] = df['ZTS_Offset']
            pem_df['Coil_delay'] = 0
            pem_df['Number_of_stacks'] = df['Number_of_Stacks']
            pem_df['Readings_per_set'] = df['Number_of_Readings']
            pem_df['Reading_number'] = df['Reading_Number']
            pem_df['RAD_tool'] = df['RAD']
            pem_df['Reading'] = df['data']
            pem_df['RAD_ID'] = pem_df['RAD_tool'].map(lambda x: x.id)
            pem_df['Deleted'] = df['Deleted'].map(lambda x: False if x.strip() == 'F' else True)
            pem_df['Overload'] = df['Overload'].map(lambda x: False if x.strip() == 'F' else True)

            # Find the overload readings and set them to be deleted
            overload_filt = pem_df.loc[:, 'Overload']
            pem_df.loc[overload_filt, 'Deleted'] = True

            pem_df['Timestamp'] = df['Date_Time'].map(str_to_datetime)

            # Remove Inf readings
            inf_filt = pem_df.Reading.map(lambda x: np.isinf(x).any())
            inf_readings = pem_df[inf_filt]
            if not inf_readings.empty:
                logger.error(f"Following stations had Inf readings: "
                             f"\n{inf_readings.loc[:, ['Station', 'Component', 'Reading_number']].to_string()}")

            pem_df = pem_df[~inf_filt]
            return pem_df, inf_readings

        if isinstance(filepath, str):
            filepath = Path(filepath)

        assert filepath.is_file(), f"{filepath.name} does not exist."
        self.filepath = filepath
        logger.info(f"Parsing {self.filepath.name}.")

        # Read the contents of the file
        with open(filepath, 'rt') as file:
            contents = file.read()
            # Change the different occurences of header titles between DMP2 file versions so they are the same.
            contents = re.sub('isDeleted', 'Deleted', contents)
            if not re.search('Loop_Length', contents):
                contents = re.sub('Loop_Height', 'Loop_Length', contents)
            contents = re.sub('Released', 'Software_Release_Date', contents)

            # Find the year of the date of the file, and if necessary convert the year format to %Y instead of %y
            date = re.search(r'Date: (\d+\W\d+\W\d+)', contents).group(1)

            # If date is separated with hyphens, the date format is Y-m-d instead of m-d-y
            if '-' in date:
                date_str = datetime.strptime(date, '%Y-%m-%d').strftime('%B %d, %Y')
            else:
                year = re.search(r'(\d+\W\d+\W)(\d+)', date).group(2)

                # Replace the year to be 20xx
                if len(year) < 4:
                    Y = int(year) + 2000
                    date = re.sub(r'(\d+\W\d+\W)(\d+)', f'\g<1>{Y}', date)

                date_str = datetime.strptime(date, '%m/%d/%Y').strftime('%B %d, %Y')

        # Split the file up into the header and data sections
        scontents = contents.split('$$')
        if not scontents[0].strip():
            raise ValueError(f'No header found in {self.filepath.name}.')
        elif not scontents[1].strip():
            raise ValueError(f'No data found in {self.filepath.name}.')

        header = parse_header(scontents[0])
        data, data_errors = parse_data(scontents[1], units=header.get('Units'))
        channel_table = parse_channel_times(units=header.get('Units'))
        # notes = header['Notes']

        pem_file = PEMFile().from_dmp(header, channel_table, data, self.filepath)
        return pem_file, data_errors

    def parse(self, filepath):
        """
        Parse a .DMP file, including .DMP2+.
        :param filepath: str or Path object of the DMP file
        :return: PEMFile object
        """

        if isinstance(filepath, str):
            filepath = Path(filepath)
        assert filepath.is_file(), f"{filepath.name} does not exist."

        if filepath.suffix.lower() == '.dmp':
            pem_file, inf_errors = self.parse_dmp(filepath)
        elif filepath.suffix.lower() == '.dmp2':
            pem_file, inf_errors = self.parse_dmp2(filepath)
        else:
            raise NotImplementedError(f"Parsing {filepath.suffix} files not implemented yet.")

        return pem_file, inf_errors


class PEMSerializer:
    """
    Class for serializing PEM files to be saved
    """

    def __init__(self):
        self.pem_file = None

    def serialize_tags(self):
        result = ""
        xyp = ' '.join([self.pem_file.probes.get('XY probe number'),
                        self.pem_file.probes.get('SOA'),
                        self.pem_file.probes.get('Tool number'),
                        self.pem_file.probes.get('Tool ID')])
        result += f"<FMT> {self.pem_file.format}\n"
        result += f"<UNI> {'nanoTesla/sec' if self.pem_file.units == 'nT/s' else 'picoTesla'}\n"
        result += f"<OPR> {self.pem_file.operator}\n"
        result += f"<XYP> {xyp}\n"
        result += f"<CUR> {self.pem_file.current}\n"
        result += f"<TXS> {self.pem_file.loop_dimensions}"

        return result

    def serialize_loop_coords(self):
        result = '~ Transmitter Loop Co-ordinates:'
        loop = self.pem_file.get_loop()
        if loop.empty:
            result += '\n<L00>\n''<L01>\n''<L02>\n''<L03>'
        else:
            loop.reset_index(inplace=True)
            for row in loop.itertuples():
                tag = f"<L{row.Index:02d}>"
                row = f"{tag} {row.Easting:.2f} {row.Northing:.2f} {row.Elevation:.2f} {row.Unit}"
                result += '\n' + row
        return result

    def serialize_line_coords(self):

        def serialize_station_coords():
            result = '~ Hole/Profile Co-ordinates:'
            line = self.pem_file.get_line()
            if line.empty:
                result += '\n<P00>\n''<P01>\n''<P02>\n''<P03>\n''<P04>\n''<P05>'
            else:
                line.reset_index(inplace=True)
                for row in line.itertuples():
                    tag = f"<P{row.Index:02d}>"
                    row = f"{tag} {row.Easting:.2f} {row.Northing:.2f} {row.Elevation:.2f} {row.Unit} {row.Station}"
                    result += '\n' + row
            return result

        def serialize_collar_coords():
            result = '~ Hole/Profile Co-ordinates:'
            collar = self.pem_file.get_collar()
            collar.reset_index(drop=True, inplace=True)
            if collar.empty:
                result += '\n<P00>'
            else:
                for row in collar.itertuples():
                    tag = f"<P{row.Index:02d}>"
                    row = f"{tag} {row.Easting:.2f} {row.Northing:.2f} {row.Elevation:.2f} {row.Unit}"
                    result += '\n' + row
            return result

        def serialize_segments():
            result = ''
            segs = self.pem_file.get_segments()
            segs.reset_index(drop=True, inplace=True)
            if segs.empty:
                result += '\n<P01>\n''<P02>\n''<P03>\n''<P04>\n''<P05>'
            else:
                for row in segs.itertuples():
                    tag = f"<P{row.Index + 1:02d}>"
                    row = f"{tag} {row.Azimuth:.2f} {row.Dip:.2f} {row[3]:.2f} {row.Unit} {row.Depth:.2f}"
                    result += '\n' + row
            return result

        if self.pem_file.is_borehole():
            return serialize_collar_coords() + \
                   serialize_segments()
        else:
            return serialize_station_coords()

    def serialize_notes(self):
        results = []
        if not self.pem_file.notes:
            return ''
        else:
            for line in self.pem_file.notes:
                if line not in results:
                    results.append(line)
        return '\n'.join(results) + '\n'

    def serialize_header(self):

        def get_channel_times(table):
            times = []
            # Add all the start times
            table.Start.map(times.append)
            # Add the first 'End' since it's the only value not repeated as a start
            times.insert(1, table.iloc[0].End)
            # Add the last end-time
            times.append(table.iloc[-1].End)
            return times

        survey_type = self.pem_file.get_survey_type()
        if survey_type == 'Surface Induction':
            survey_str = 'Surface'
        elif survey_type == 'Borehole Induction':
            survey_str = 'Borehole'
        elif survey_type == 'Surface Fluxgate':
            survey_str = 'S-Flux'
        elif survey_type == 'Borehole Fluxgate':
            survey_str = 'BH-Flux'
        elif survey_type == 'SQUID':
            survey_str = 'SQUID'
        else:
            raise ValueError(f"{survey_type} is not a valid survey type.")

        result_list = [str(self.pem_file.client),
                       str(self.pem_file.grid),
                       str(self.pem_file.line_name),
                       str(self.pem_file.loop_name),
                       str(self.pem_file.date),
                       ' '.join([survey_str,
                                 str(self.pem_file.convention),
                                 str(self.pem_file.sync),
                                 str(self.pem_file.timebase),
                                 str(int(self.pem_file.ramp)),
                                 str(self.pem_file.number_of_channels - 1),
                                 str(self.pem_file.number_of_readings)]),
                       ' '.join([str(self.pem_file.rx_number),
                                 str(self.pem_file.rx_software_version),
                                 str(self.pem_file.rx_software_version_date),
                                 str(self.pem_file.rx_file_name),
                                 str(self.pem_file.normalized),
                                 str(self.pem_file.primary_field_value),
                                 str(int(self.pem_file.coil_area))])]

        if self.pem_file.loop_polarity is not None:
            result_list[-1] += ' ' + self.pem_file.loop_polarity

        result = '\n'.join(result_list) + '\n\n'

        times_per_line = 7
        cnt = 0

        times = get_channel_times(self.pem_file.channel_times)
        channel_times = [f'{time:9.6f}' for time in times]

        for i in range(0, len(channel_times), times_per_line):
            line_times = channel_times[i:i+times_per_line]
            result += ' '.join([str(time) for time in line_times]) + '\n'
            cnt += 1

        result += '$'
        return result

    def serialize_data(self, legacy=False):
        df = self.pem_file.get_data(sorted=True)

        # Remove deleted readings
        filt = ~df.Deleted.astype(bool)
        df = df[filt]

        def serialize_reading(reading):
            reading_header = [reading['Station'],
                              reading['Component'] + 'R' + f"{reading['Reading_index']:g}",
                              f"{reading['Gain']:g}",
                              reading['Rx_type'],
                              f"{reading['ZTS']:g}",
                              f"{reading['Coil_delay']:g}",
                              f"{reading['Number_of_stacks']:g}",
                              f"{reading['Readings_per_set']:g}",
                              f"{reading['Reading_number']:g}",
                              ]
            # Add the DMP2 information if not saving a processed version of the file
            if not legacy:
                reading_header.extend([f"{reading['Deleted']}",
                                       f"{reading['Overload']}",
                                       re.sub(r'\s', '_', f"{reading['Timestamp']}")  # Replace the spaces
                                       ])

            result = ' '.join(reading_header) + '\n'
            rad = reading['RAD_tool'].to_string(legacy=legacy)
            result += rad + '\n'

            readings_per_line = 7
            reading_spacing = 12
            count = 0

            # channel_readings = [f'{r:<8g}' for r in reading['Reading']]
            channel_readings = [f'{r:10.3f}' for r in reading['Reading']]

            for i in range(0, len(channel_readings), readings_per_line):
                readings = channel_readings[i:i + readings_per_line]
                result += ' '.join([str(r) + max(0, reading_spacing - len(r))*' ' for r in readings]) + '\n'
                count += 1

            return result + '\n'

        return ''.join(df.apply(serialize_reading, axis=1))

    def serialize(self, pem_file, legacy=False):
        """
        Create a string of a PEM file to be printed to a text file.
        :param pem_file: PEM_File object
        :param legacy: bool, if True will strip newer features so it is compatible with Step (such as D5 RAD tool
        lines and remove Timestamp and Deleted values.
        :return: A string in PEM file format containing the data found inside of pem_file
        """
        self.pem_file = pem_file

        result = self.serialize_tags() + '\n'
        result += self.serialize_loop_coords() + '\n'
        result += self.serialize_line_coords() + '\n'
        result += self.serialize_notes()
        result += '~\n'
        result += self.serialize_header() + '\n'
        result += self.serialize_data(legacy=legacy)
        return result


class RADTool:
    """
    Class that represents the RAD Tool reading in a PEM survey
    """

    def __init__(self):
        self.D = None
        self.Hx = None
        self.gx = None
        self.Hy = None
        self.gy = None
        self.Hz = None
        self.gz = None
        self.T = None

        self.x = None
        self.y = None
        self.z = None
        self.roll_angle = None
        self.dip = None
        self.R = None
        self.angle_used = None  # Roll angle - SOA

        self.rotated = False
        self.rotation_type = None
        self.id = None

        # PP rotation stats
        self.azimuth = None
        self.dip = None
        self.x_pos = None
        self.y_pos = None
        self.z_pos = None
        self.ppx_theory = None
        self.ppy_theory = None
        self.ppz_theory = None
        self.ppx_raw = None
        self.ppy_raw = None
        self.ppx_cleaned = None
        self.ppy_cleaned = None
        self.ppxy_theory = None
        self.ppxy_cleaned = None
        self.ppxy_measured = None
        self.cleaned_pp_roll_angle = None
        self.measured_pp_roll_angle = None
        self.pp_dip = None

        self.acc_roll_angle = None
        self.mag_roll_angle = None

    def from_match(self, match):
        """
        Create the RADTool object using the string parsed from PEMParser
        :param match: str, Full string parsed from PEMParser
        :return RADTool object
        """
        match = match.split()
        self.D = match[0]
        match[1:] = np.array(match[1:])

        if self.D == 'D7':
            if len(match) == 8:
                self.rotated = False
                self.Hx = float(match[1])
                self.gx = float(match[2])
                self.Hy = float(match[3])
                self.gy = float(match[4])
                self.Hz = float(match[5])
                self.gz = float(match[6])
                self.T = float(match[7])

                self.id = ''.join([
                    str(self.Hx),
                    str(self.gx),
                    str(self.Hy),
                    str(self.gy),
                    str(self.Hz),
                    str(self.gz),
                    str(self.T)
                ])

            elif len(match) == 11:
                self.rotated = True
                self.Hx = float(match[1])
                self.gx = float(match[2])
                self.Hy = float(match[3])
                self.gy = float(match[4])
                self.Hz = float(match[5])
                self.gz = float(match[6])
                self.roll_angle = float(match[7])
                self.dip = float(match[8])
                self.R = match[9]
                self.angle_used = float(match[10])

                self.id = ''.join([
                    str(self.Hx),
                    str(self.gx),
                    str(self.Hy),
                    str(self.gy),
                    str(self.Hz),
                    str(self.gz),
                    str(self.roll_angle),
                    str(self.dip),
                    self.R,
                    str(self.angle_used),
                ])
            else:
                raise Exception(f"{len(match)} long D7 RAD tool match passed. Should be length of 8 or 11.")

        elif self.D == 'D5':
            self.x = float(match[1])
            self.y = float(match[2])
            self.z = float(match[3])
            self.roll_angle = float(match[4])
            self.dip = float(match[5])
            if len(match) == 6:
                self.rotated = False

                self.id = ''.join([
                    str(self.x),
                    str(self.y),
                    str(self.z),
                    str(self.roll_angle),
                    str(self.dip)
                ])

            elif len(match) == 8:
                self.R = match[6]
                self.angle_used = float(match[7])
                self.rotated = True

                self.id = ''.join([
                    str(self.x),
                    str(self.y),
                    str(self.z),
                    str(self.roll_angle),
                    str(self.dip),
                    str(self.R),
                    str(self.angle_used)
                ])

            else:
                raise ValueError(f'{len(match)} long D5 RAD tool match passed. Should be length of 6 or 8.')

        else:
            raise ValueError(f'{self.D} is an invalid RAD tool D value. D value must be D5 or D7.')

        return self

    def from_dict(self, dict):
        """
        Use the keys and values of a dictionary to create the RADTool object
        :param dict: dictionary with keys being the RADTool object's attributes.
        :return: RADTool object
        """
        self.id = ''

        for key, value in dict.items():
            self.__setattr__(key, value)
            self.id += str(value)
        self.rotated = True if self.angle_used is not None else False

        return self

    def from_dmp(self, text):
        """
        Create the RADTool object from the RAD line in a .DMP file.
        :param text: str or list of RAD tool line items in the .DMP file
        :return: RADTool object
        """
        if not isinstance(text, list):
            text = text.split()

        self.D = 'D7'
        self.Hx = float(text[0])
        self.gx = float(text[1])
        self.Hy = float(text[2])
        self.gy = float(text[3])
        self.Hz = float(text[4])
        self.gz = float(text[5])
        if len(text) > 6:
            self.T = float(text[6])
        else:
            self.T = 0.0

        self.id = ''.join([
            str(self.Hx),
            str(self.gx),
            str(self.Hy),
            str(self.gy),
            str(self.Hz),
            str(self.gz),
            str(self.T),
        ])

        return self

    # @Log()
    def get_azimuth(self, allow_negative=False):
        """
        Calculate the azimuth of the RAD tool object. Must be D7.
        :param allow_negative: bool, allow negative azimuth values or only allow values within 0 - 360.
        :return: float, azimuth
        """
        if not self.has_tool_values():
            return None

        g = math.sqrt(sum([self.gx ** 2, self.gy ** 2, self.gz ** 2]))
        numer = ((self.Hz * self.gy) - (self.Hy * self.gz)) * g
        denumer = self.Hx * (self.gy ** 2 + self.gz ** 2) - (self.Hy * self.gx * self.gy) - (self.Hz * self.gx * self.gz)

        azimuth = math.degrees(math.atan2(numer, denumer))
        if not allow_negative:
            if azimuth < 0:
                azimuth = 360 + azimuth
        return azimuth

    def get_dip(self):
        """
        Calculate the dip of the RAD tool object. Must be D7.
        :return: float, dip
        """
        if not self.has_tool_values():
            return None

        try:
            dip = math.degrees(math.acos(self.gx / math.sqrt((self.gx ** 2) + (self.gy ** 2) + (self.gz ** 2)))) - 90
        except ZeroDivisionError:
            logger.error(f"Attempted division by 0.")
            dip = None
        return dip

    def get_acc_roll(self):
        """
        Calculate the roll angle as measured by the accelerometer. Must be D7.
        :return: float, roll angle
        """
        if not self.has_tool_values():
            return None

        x, y, z = self.gx, self.gy, self.gz

        theta = math.atan2(y, z)
        cc_roll_angle = 360 - math.degrees(theta) if y < 0 else math.degrees(theta)
        roll_angle = 360 - cc_roll_angle if y > 0 else cc_roll_angle
        if roll_angle >= 360:
            roll_angle = roll_angle - 360
        elif roll_angle < 0:
            roll_angle = roll_angle + 360

        return roll_angle

    def get_mag_roll(self):
        """
        Calculate the roll angle as measured by the magnetometer. Must be D7.
        :return: float, roll angle
        """
        if not self.has_tool_values():
            return None

        x, y, z = self.Hx, self.Hy, self.Hz

        theta = math.atan2(-y, -z)
        cc_roll_angle = math.degrees(theta)
        roll_angle = 360 - cc_roll_angle if y < 0 else cc_roll_angle
        if roll_angle > 360:
            roll_angle = roll_angle - 360
        elif roll_angle < 0:
            roll_angle = -roll_angle

        return roll_angle

    def get_mag_strength(self):
        """
        Calculate and return the magnetic field strength (total field) in units of nT
        :return: float
        """
        if not self.has_tool_values():
            return None

        x, y, z = self.Hx, self.Hy, self.Hz
        mag_strength = math.sqrt(sum([x ** 2, y ** 2, z ** 2])) * (10 ** 5)
        return mag_strength

    def has_tool_values(self):
        if all([self.Hx, self.gx, self.Hy, self.gy, self.Hz, self.gz]):
            return True
        else:
            return False

    def is_derotated(self):
        return True if self.angle_used is not None else False

    def to_string(self, legacy=False):
        """
        Create a string for PEM serialization
        :param legacy: bool, if True, return D5 values instead of D7 for compatibility with Step.
        :return: str
        """
        # If the input D value is already D5
        if self.D == 'D5':
            result = [self.D]
            if self.rotation_type is None:
                result.append(f"{self.x:g}")
                result.append(f"{self.y:g}")
                result.append(f"{self.z:g}")

            elif self.rotation_type == 'acc' or self.rotation_type.lower() == 'pp':
                result.append(f"{self.gx:g}")
                result.append(f"{self.gy:g}")
                result.append(f"{self.gz:g}")

            elif self.rotation_type == 'mag':
                result.append(f"{self.Hx:g}")
                result.append(f"{self.Hy:g}")
                result.append(f"{self.Hz:g}")

            result.append(f"{self.roll_angle:g}")
            result.append(f"{self.dip:g}")
            result.append(self.R)
            result.append(f"{self.angle_used:g}")

        else:

            # Create the D5 RAD tool line that is compatible with Step (just for borehole XY).
            if legacy:

                if self.is_derotated():
                    if self.rotation_type == 'mag':  # Only mag de-rotation uses the mag values. Everything is acc.
                        x, y, z = f"{self.Hx:g}", f"{self.Hy:g}", f"{self.Hz:g}"
                    else:
                        x, y, z = f"{self.gx:g}", f"{self.gy:g}", f"{self.gz:g}"

                    # For de-rotated XY RADs
                    if all([self.roll_angle, self.dip, self.angle_used, self.R]):
                        result = [
                            'D5',
                            x,
                            y,
                            z,
                            f"{self.roll_angle:g}",
                            f"{self.dip:g}",
                            self.R,
                            f"{self.angle_used:g}"
                        ]

                # For rotated and Z RADs
                else:
                    result = [
                        'D7',
                        f"{self.Hx:g}",
                        f"{self.gx:g}",
                        f"{self.Hy:g}",
                        f"{self.gy:g}",
                        f"{self.Hz:g}",
                        f"{self.gz:g}",
                        f"{self.T:g}" if self.T is not None else '0'
                    ]

            # Non legacy
            else:
                if self.D == 'D7' or self.D == 'D6':
                    result = [
                        self.D,
                        f"{self.Hx:g}",
                        f"{self.gx:g}",
                        f"{self.Hy:g}",
                        f"{self.gy:g}",
                        f"{self.Hz:g}",
                        f"{self.gz:g}",
                    ]

                    if self.R is not None and self.angle_used is not None:
                        if self.rotation_type == 'acc':
                            result.append(f"{self.acc_roll_angle:g}")
                        elif self.rotation_type == 'mag':
                            result.append(f"{self.mag_roll_angle:g}")
                        elif self.rotation_type == 'pp_raw':
                            result.append(f"{self.measured_pp_roll_angle:g}")
                        elif self.rotation_type == 'pp_cleaned':
                            result.append(f"{self.cleaned_pp_roll_angle:g}")
                        else:
                            if self.roll_angle is None:
                                raise Exception(f"The RAD tool object has been de-rotated, yet no roll_angle exists.")

                            logger.warning(f"No rotation type passed. Using existing roll angle of {self.roll_angle:g}.")
                            result.append(f"{self.roll_angle:g}")

                        result.append(f"{self.get_dip():g}")
                        result.append(self.R)
                        result.append(f"{self.angle_used:g}")
                    else:
                        result.append(f"{self.T:g}")

                else:
                    raise ValueError('RADTool D value is neither "D5" nor "D7"')

        return ' '.join(result)


if __name__ == '__main__':
    from src.pem.pem_getter import PEMGetter
    import os

    dparser = DMPParser()
    pemparser = PEMParser()
    pem_g = PEMGetter()
    pem_file = pem_g.get_pems(client='PEM Rotation', file='_BX-081 XY.PEM')[0]
    pem_file.get_dad()
    # pem_file = pem_g.get_pems(client='Kazzinc', number=1)[0]
    # pem_file.to_xyz()
    # prep_pem, _ = pem_file.prep_rotation()
    # pem = pem_file.rotate_soa(10)
    # rotated_pem = prep_pem.rotate('pp')

    # pem_file = pemparser.parse(r'C:\_Data\2020\Eastern\Egypt Road\__ER-19-02\RAW\XY29_29.PEM')
    # pem_file = dparser.parse(r'C:\_Data\2020\Eastern\Dominique\_DOM-91-1\RAW\xy03_03.DMP')
    # pem_file = dparser.parse_dmp2(r'C:\_Data\2020\Juno\Surface\Europa\Loop 3\RAW\line 850_16.dmp2')
    # pem_file.save(legacy=True)

    # file = str(Path(__file__).parents[2].joinpath('sample_files/DMP files/DMP2 New/BR-32 Surface/l4200e.dmp2'))
    # pem_file = dparser.parse_dmp2(file)
    # pem_file.get_suffix_warnings()
    # pem_file.save(processed=False)
    # pem_file2 = pemparser.parse(file.filepath)
    # pem_file2.save(processed=True)

    # out = str(Path(__file__).parents[2].joinpath(
    # 'sample_files/test results/f'{file.filepath.stem} - test conversion.pem')
    # print(file.to_string(), file=open(out, 'w'))
    # os.startfile(pem_file.filepath)
