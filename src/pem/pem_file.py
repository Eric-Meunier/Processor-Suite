import math
import os
import re
import time
import copy
import natsort
import geomag
from datetime import datetime
from pyproj import CRS
import numpy as np
import pandas as pd
from scipy.spatial.transform import Rotation as R

from pathlib import Path
from src.gps.gps_editor import TransmitterLoop, SurveyLine, BoreholeCollar, BoreholeSegments, BoreholeGeometry  #, CRS
from src.mag_field.mag_field_calculator import MagneticFieldCalculator


def sort_data(data):
    # Sort the data frame
    df = data.reindex(index=natsort.order_by_index(
        data.index, natsort.index_humansorted(zip(data.Component, data.Station, data['Reading_index'], data['Reading_number']))))
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
        self.geometry = None
        self.line = None
        self.crs = None

        self.total_scale_factor = 0.
        self.pp_table = None
        self.prepped_for_rotation = False

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
        self.number_of_channels = header.get('Number of channels')
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

        self.notes = notes

        self.data = sort_data(data)
        # Add the deletion flag column
        if 'del_flag' not in self.data.columns:
            self.data.insert(13, 'del_flag', False)

        # Add the overload column
        if 'Overload' not in self.data.columns:
            self.data.insert(14, 'Overload', False)

        # Add the datetime column
        if 'datetime' not in self.data.columns:
            self.data.insert(15, 'datetime', None)

        self.filepath = Path(filepath)

        crs = self.get_crs()
        self.loop = TransmitterLoop(loop_coords, crs=crs)
        if self.is_borehole():
            self.collar = BoreholeCollar([line_coords[0]], crs=crs)
            self.segments = BoreholeSegments(line_coords[1:])
            self.geometry = BoreholeGeometry(self.collar, self.segments)
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
        self.number_of_channels = header.get('Number of channels')
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

        if notes:
            self.notes = notes
        else:
            self.notes = []

        self.data = sort_data(data)
        # Add the deletion flag column
        if 'del_flag' not in self.data.columns:
            self.data.insert(13, 'del_flag', False)

        # Add the overload column
        if 'Overload' not in self.data.columns:
            self.data.insert(14, 'Overload', False)

        # Add the datetime column
        if 'datetime' not in self.data.columns:
            self.data.insert(15, 'datetime', None)

        self.filepath = filepath.with_suffix('.PEM')

        crs = self.get_crs()
        self.loop = TransmitterLoop(None, crs=crs)
        if self.is_borehole():
            self.collar = BoreholeCollar(None, crs=crs)
            self.segments = BoreholeSegments(None)
            self.geometry = BoreholeGeometry(self.collar, self.segments)
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

    def is_rotated(self):
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
            if not self.geometry.collar.df.dropna().empty and all(self.geometry.collar.df):
                return True
            else:
                return False
        else:
            return False

    def has_geometry(self):
        if self.is_borehole():
            if not self.geometry.segments.df.dropna().empty and all(self.geometry.segments.df):
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
                    print(f"CRS is {crs.name}")
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
                            print(f"CRS string not implemented.")
                            return None

                    crs = CRS.from_epsg(epsg_code)
                    print(f"CRS is {crs.name}")
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
        return self.geometry

    def get_notes(self):
        return self.notes

    def get_data(self, sorted=False):
        if sorted:
            data = sort_data(self.data)
        else:
            data = self.data
        return data

    def get_channel_bounds(self):
        """
        Create tuples of start and end channels to be plotted per axes for LIN plots
        :return: list of tuples, first item of tuple is the axes, second is the start and end channel for that axes
        """
        channel_bounds = [None] * 4

        # Only plot off-time channels
        number_of_channels = len(self.channel_times[self.channel_times.Remove == False])

        num_channels_per_plot = int((number_of_channels - 1) // 4)
        remainder_channels = int((number_of_channels - 1) % 4)

        for k in range(0, len(channel_bounds)):
            channel_bounds[k] = (k * num_channels_per_plot + 1, num_channels_per_plot * (k + 1))

        for i in range(0, remainder_channels):
            channel_bounds[i] = (channel_bounds[i][0], (channel_bounds[i][1] + 1))
            for k in range(i + 1, len(channel_bounds)):
                channel_bounds[k] = (channel_bounds[k][0] + 1, channel_bounds[k][1] + 1)

        channel_bounds.insert(0, (0, 0))
        return channel_bounds

    def get_profile_data(self, component, averaged=False, converted=False, ontime=True):
        """
        Transform the readings in the data in a manner to be plotted as a profile
        :param component: str, used to filter the profile data and only keep the given component
        :param averaged: bool, average the readings of the profile
        :param converted: bool, convert the station names to int
        :param ontime: bool, keep the on-time channels
        :return: pandas DataFrame object with Station as the index, and channels as columns.
        """
        t = time.time()
        comp_filt = self.data['Component'] == component.upper()
        data = self.data[comp_filt]

        if ontime is False:
            data.Reading = data.Reading.map(lambda x: x[~self.channel_times.Remove])

        profile = pd.DataFrame.from_dict(dict(zip(data.Reading.index, data.Reading.values))).T

        if converted is True:
            stations = data.Station.map(self.converter.convert_station)
        else:
            stations = data.Station

        profile.insert(0, 'Station', stations)
        profile.set_index('Station', drop=True, inplace=True)

        if averaged is True:
            profile = profile.groupby('Station').mean()

        # print(f"PEMFile - Time to get profile data: {time.time() - t}")
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
                line = self.geometry.get_projection()
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
            print('GPS coordinate system information is invalid')
            return

        if self.has_collar_gps():
            coords = self.geometry.collar
        elif self.has_loop_gps():
            coords = self.loop
        elif self.has_station_gps():
            coords = self.line
        else:
            print('Error - No GPS')
            return

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
                  'otool' in file_survey_type,
                  'bh_z' in file_survey_type,
                  'bh_fast_rad' in file_survey_type,
                  'bh_z_probe' in file_survey_type,
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

    def to_string(self):
        """
        Return the text format of the PEM file
        :return: str, Full text of the PEM file
        """
        ps = PEMSerializer()
        text = ps.serialize(copy.deepcopy(self))
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

            if filt.any() or filt.all():
                row['Easting'] = gps[filt]['Easting'].iloc[0]
                row['Northing'] = gps[filt]['Northing'].iloc[0]
                row['Elevation'] = gps[filt]['Elevation'].iloc[0]
            return row

        df = pd.DataFrame(columns=['Easting', 'Northing', 'Elevation', 'Component', 'Station', 'c_Station'])
        pem_data = self.get_data(sorted=True).dropna()
        gps = self.line.get_line(sorted=True).drop_duplicates('Station')

        assert not self.is_borehole(), 'Can only create XYZ file with surface PEM files.'
        assert not gps.empty, 'No GPS found.'
        print(f'Converting {self.filepath.name} to XYZ')
        # t = time.time()

        df['Component'] = pem_data.Component.copy()
        df['Station'] = pem_data.Station.copy()
        df['c_Station'] = df.Station.map(self.converter.convert_station)
        # Add the GPS
        df = df.apply(get_station_gps, axis=1)

        # Create a dataframe of the readings with channel number as columns
        channel_data = pd.DataFrame(columns=range(int(self.number_of_channels)))
        channel_data = pem_data.apply(lambda x: pd.Series(x.Reading), axis=1)
        # Merge the two data frames
        df = pd.concat([df, channel_data], axis=1).drop('c_Station', axis=1)
        str_df = df.apply(lambda x: x.astype(str).str.cat(sep=' '), axis=1)
        str_df = '\n'.join(str_df.to_list())
        # print(f"PEMFile - Time to convert {self.filepath.name} to XYZ: {time.time() - t}")
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

    def save(self, backup=False, tag=''):
        """
        Save the PEM file to a .PEM file with the same filepath it currently has.
        :param backup: bool, if the save is for a backup. If so, it will save the PEM file in a [Backup] folder,
        and create the folder if it doesn't exist. The [Backup] folder will be located in the parent directory of the
        PEMFile.
        :param tag: str, tag to be appened to the file name. Used for pre-averaging and pre-splitting saves.
        """
        text = self.to_string()

        if backup:
            print(f"Saving backup for {self.filepath.name}")

            backup_path = self.filepath.parent.joinpath('[Backup]').joinpath(
                self.filepath.stem + tag + self.filepath.suffix)

            # Create a [Backup] folder if it doesn't exist
            if not backup_path.parent.is_dir():
                Path.mkdir(backup_path.parent)

            print(text, file=open(str(backup_path), 'w+'))
        else:
            print(f"Saving {self.filepath.name}.")
            print(text, file=open(str(self.filepath), 'w+'))

    def average(self):
        """
        Averages the data of the PEM file object. Uses a weighted average.
        :return: PEM file object
        """
        print(f"Averaging {self.filepath.name}")
        # t = time.time()
        if self.is_averaged():
            print(f"{self.filepath.name} is already averaged")
            return

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
        filt = self.data.del_flag == False
        # Create a data frame with all data averaged
        df = self.data[filt].groupby(['Station', 'Component']).apply(weighted_average)
        # Sort the data frame
        df = sort_data(df)
        self.data = df
        # print(f"PEMFile - Time to average {self.filepath.name}: {time.time() - t}")
        return self

    def split(self):
        """
        Remove the on-time channels of the PEM file object
        :return: PEM file object with split data
        """
        print(f"Splitting channels for {self.filepath.name}")
        # t = time.time()
        if self.is_split():
            print(f"{self.filepath.name} is already split.")
            return

        # Only keep the select channels from each reading
        self.data.Reading = self.data.Reading.map(lambda x: x[~self.channel_times.Remove])
        # Create a filter and update the channels table
        filt = self.channel_times.Remove == False
        self.channel_times = self.channel_times[filt]
        # Update the PEM file's number of channels attribute
        self.number_of_channels = len(self.channel_times.index) - 1

        # print(f"PEMFile - Time to split PEM file: {time.time() - t}")
        return self

    def scale_coil_area(self, coil_area):
        """
        Scale the data by a change in coil area
        :param coil_area: int: new coil area
        :return: PEMFile object: self with data scaled
        """
        # t = time.time()
        print(f"Scaling coil area of {self.filepath.name}")

        new_coil_area = coil_area
        assert isinstance(new_coil_area, int), "New coil area is not type int"
        old_coil_area = self.coil_area

        scale_factor = float(old_coil_area / new_coil_area)

        self.data.Reading = self.data.Reading * scale_factor  # Vectorized
        print(f"{self.filepath.name} coil area scaled to {new_coil_area} from {old_coil_area}")

        self.coil_area = new_coil_area
        self.notes.append(f'<HE3> Data scaled by coil area change of {old_coil_area}/{new_coil_area}')
        # print(f"PEMFile - Time to scale by coil area: {time.time() - t}")
        return self

    def scale_current(self, current):
        """
        Scale the data by a change in current
        :param current: float, new current
        :return: PEMFile object, self with data scaled
        """
        new_current = current
        assert isinstance(new_current, float), "New current is not type float"
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
        print(f"{self.filepath.name} data scaled by factor of {(1 + scaled_factor)}")

        self.total_scale_factor += factor

        self.notes.append(f'<HE3> Data scaled by factor of {1 + factor}')
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
        print(f"De-rotating data of {self.filepath.name}")

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
                :param x: list: list of x readings to rotated
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
                Y' = Xsin(roll) + Ycos(roll)
                :param y: list: list of y readings to rotated
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
                                'angle_used': rad.acc_roll_angle - soa,
                                'rotated': True,
                                'rotation_type': 'acc'}

                # Magnetometer rotation
                elif method == 'mag':
                    # Update the new_rad with the de-rotation information
                    new_info = {'roll_angle': rad.mag_roll_angle,
                                'dip': rad.mag_dip,
                                'R': 'R3',
                                'angle_used': rad.mag_roll_angle - soa,
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

        # Create a filter for X and Y data only
        filt = (self.data.Component == 'X') | (self.data.Component == 'Y')
        filtered_data = self.data[filt]

        st = time.time()
        # Rotate the data
        rotated_data = filtered_data.groupby(['Station', 'RAD_ID'],
                                             group_keys=False,
                                             as_index=False).apply(lambda l: rotate_data(l, method, soa))
        print(f"PEMFile - Time to rotate data: {time.time() - st}")

        self.data[filt] = rotated_data
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
        print(f"Preparing for XY-derotation for {self.filepath.name}")

        def filter_data(df):
            """
            Remove reading groups that don't have and X and Y pair. Such readings have their station name changed
            to NaN and are added to a 'ineligible_stations' data frame.
            :param df: group pd DataFrame, readings of the same station and same RAD tool ID
            :return: pd DataFrame
            """
            if df.Component.nunique() < 2:
                # Capture to the ineligible stations
                global ineligible_stations
                ineligible_stations = pd.concat([df, ineligible_stations])
                # Make the station NaN so it can be easily removed after
                df.Station = np.nan
            return df

        def setup_pp():
            """
            Set up the necessary variables used for cleaned PP rotation.
            """
            assert self.has_loop_gps(), f"{self.filepath.name} has no loop GPS."
            assert self.has_geometry(), f"{self.filepath.name} has incomplete geometry."
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
            proj = self.geometry.get_projection(stations=self.get_stations(converted=True))
            loop = self.get_loop(sorted=False, closed=False)
            # Get the ramp in seconds
            ramp = self.ramp / 10 ** 6
            mag_calc = MagneticFieldCalculator(loop)

            # TODO Remove the last channel of fluxgates
            # Only keep off-time channels with PP
            ch_times = self.channel_times[self.channel_times.loc[:, 'Remove'] == False]
            # Normalize the channel times so they start from turn off
            # ch_times.loc[:, 'Start':'Center'] = ch_times.loc[:, 'Start':'Center'].applymap(lambda x: x + ramp)

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
                        cleaned_pp = row.Reading[0]
                        for num in ch_numbers:
                            cleaned_pp += row.Reading[num]
                        return cleaned_pp

                    # Add the PP information (theoretical PP, cleaned PP, roll angle) to the new RAD Tool object
                    if include_pp is True:
                        pp_rad_info = dict()

                        # Calculate the raw PP value for each component
                        pp_ch_index = self.channel_times[self.channel_times.Remove == False].index.values[0]
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

                        # rTx_new, rTy_new, rTz_new = R.from_euler(
                        #     'ZY', [90 - seg_azimuth, 90 - seg_dip], degrees=True).apply([Tx, Ty, Tz]
                        #                                                                 )

                        # Rotate the theoretical values into the hole coordinate system
                        r = R.from_euler('YZ', [90 - seg_dip, seg_azimuth], degrees=True)
                        rT = r.apply([rTx, rTy, rTz])  # The rotated theoretical values
                        ppxy_theory = math.sqrt(sum([rT[0] ** 2, rT[1] ** 2]))

                        # ppxy_theory_new = math.sqrt(sum([rTx_new ** 2, rTy_new ** 2]))

                        # print(f"Calculated PP at {group.Station.unique()[0]}: {rT[0]:.2f}, {rT[1]:.2f}, {rT[2]:.2f}")

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
                            # print(f"Cleaned PP roll angle at {group.Station.unique()[0]}: {clean_pp_roll_angle:.2f}")
                        else:
                            cleaned_pp_roll_angle = None
                            ppxy_cleaned = None

                        measured_pp_roll_angle = math.degrees(
                            math.atan2(rT[1], rT[0]) - math.atan2(measured_ppy, measured_ppx)
                        )
                        if measured_pp_roll_angle < 0:
                            measured_pp_roll_angle = measured_pp_roll_angle + 360
                        # print(f"Raw PP roll angle at {group.Station.unique()[0]}: {measured_pp_roll_angle:.2f}")

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

                    # print(f"Acc roll angle at {group.Station.unique()[0]}: {roll_angle}")
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

                    # print(f"Mag roll angle at {group.Station.unique()[0]}: {roll_angle}")
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

        global ineligible_stations, include_pp
        ineligible_stations = pd.DataFrame()
        segments = self.get_segments()

        if all([self.has_loop_gps(), self.has_geometry(), self.ramp > 0]):
            setup_pp()
            include_pp = True
        else:
            include_pp = False

        # Create a filter for X and Y data only
        filt = (self.data.Component == 'X') | (self.data.Component == 'Y')
        # st = time.time()
        # Remove groups that don't have X and Y pairs. For some reason couldn't make it work within rotate_data
        filtered_data = self.data[filt].groupby(['Station', 'RAD_ID'],
                                                group_keys=False,
                                                as_index=False).apply(lambda k: filter_data(k))
        if filtered_data.dropna(subset=['Station']).empty:
            raise Exception(f"No eligible data found for probe de-rotation in {self.filepath.name}")

        # print(f"PEMFile - Time to filter data for rotation preparation: {time.time() - st}")

        # Calculate the RAD tool angles
        prepped_data = filtered_data.groupby(['Station', 'RAD_ID'],
                                             group_keys=False,
                                             as_index=False).apply(lambda l: prepare_rad(l))
        # print(f"PEMFile - Time to prepare RAD tools: {time.time() - st}")

        self.data[filt] = prepped_data
        # Remove the rows that were filtered out in filtered_data
        self.data.dropna(subset=['Station'], inplace=True)
        self.prepped_for_rotation = True
        return self, ineligible_stations


class PEMParser:
    """
    Class for parsing PEM files into PEMFile objects
    """

    def __init__(self):
        self.filepath = None

        # Used with the old method of parsing
        # #  'Tags' section
        # self.re_tags = re.compile(  # Parsing the 'Tags' i.e. the information above the loop coordinates
        #     r'<FMT>\s(?P<Format>\d+)\s*~?.*[\r\n]'
        #     r'<UNI>\s(?P<Units>nanoTesla/sec|picoTesla)\s*~?.*[\r\n]'
        #     r'<OPR>\s(?P<Operator>.*)~?.*[\r\n]'
        #     r'<XYP>\s(?P<Probes>[\d\w\s-]*).*[\r\n]'
        #     r'<CUR>\s(?P<Current>\d+\.?\d?)\s*~?.*[\r\n]'
        #     r'<TXS>\s(?P<LoopSize>[\d\.\s]*).*[\r\n]',
        #     re.MULTILINE)
        #
        # # Tx loop coordinates section
        # self.re_loop_coords = re.compile(
        #     r'(?P<LoopCoord><L.*>.*)')
        #
        # #  Line/Hole coordinates section
        # self.re_line_coords = re.compile(
        #     r'(?P<LineCoord><P.*>.*)')
        #
        # # Notes i.e. GEN and HE tags
        # self.re_notes = re.compile(  # Parsing the notes i.e. GEN tags and HE tags
        #     r'^(?P<Notes><GEN>.*|<HE\d>.*)',
        #     re.MULTILINE)
        # #
        # # # Header starting from 'Client' to before the channel times
        # # self.re_header = re.compile(  # Parsing the header
        # #     r'^(?:(<|~).*[\r\n]+)'
        # #     r'(?P<Client>\w.*)[\r\n]'
        # #     r'(?P<Grid>.*)[\r\n]'
        # #     r'(?P<LineHole>.*)[\r\n]'
        # #     r'(?P<Loop>.*)[\r\n]'
        # #     r'(?P<Date>.*)[\r\n]'
        # #     r'(?P<SurveyType>.*)\s(?P<Convention>Metric|Imperial)\s(?P<Sync>Crystal-Master|Crystal-Slave|Cable)\s(?P<Timebase>\d+\.?\d+)\s(?P<Ramp>\d+)\s(?P<NumChannels>\d+)\s(?P<NumReadings>\d+)[\r\n]'
        # #     r'(?P<Receiver>#\d+)\s(?P<RxSoftwareVer>[\d.]+)\s(?P<RxSoftwareVerDate>[\w]+,[\w]+)\s(?P<RxFileName>[^\s]+)\s(?P<IsNormalized>[\w]+)\s(?P<PrimeFieldValue>\d+)\s(?P<CoilArea>-?\d+)\s(?P<LoopPolarity>-|\+)?[\n\r]+',
        # #     re.MULTILINE)
        #
        # # Header starting from 'Client' to before the channel times
        # self.re_header = re.compile(  # Parsing the header
        #     r'^(?:(<|~).*[\r\n]+)'
        #     r'(?P<Client>\w.*)[\r\n]'
        #     r'(?P<Grid>.*)[\r\n]'
        #     r'(?P<LineHole>.*)[\r\n]'
        #     r'(?P<Loop>.*)[\r\n]'
        #     r'(?P<Date>.*)[\r\n]'
        #     r'(?P<SurveyParameters>.+)[\r\n]'
        #     r'(?P<ReceiverParameters>.+)[\r\n]',
        #     re.MULTILINE)
        #
        # # Channel times
        # self.re_channel_times = re.compile(
        #     r'[\r\n]{2}(?P<ChannelTimes>.*?)\$',
        #     re.DOTALL)
        #
        # # Data section
        # self.re_data = re.compile(  # Parsing the EM data information
        #     r'^(?P<Station>^\d+[NSEW]?)\s(?P<Component>[XYZ])R(?P<ReadingIndex>\d+)(?:R.*?)?\s(?P<Gain>\d+)\s(?P<RxType>[AM\?])\s(?P<ZTS>\d+\.\d+)\s(?P<CoilDelay>\d+)\s(?P<NumStacks>\d+)\s(?P<ReadingsPerSet>\d+)\s(?P<ReadingNumber>\d+).*[\r\n]'
        #     r'^(?P<RADTool>D\d.*)[\r\n]'
        #     r'(?P<Data>[\W\deE]+[\n\r])',
        #     re.MULTILINE)

    # Old method
    # def parse(self, filepath):
    #     """
    #     Parses a PEM file to extract all information and creates a PEMFile object out of it.
    #     :param filepath: string containing path to a PEM file
    #     :return: A PEM_File object representing the data found inside of filename
    #     """
    #
    #     def parse_tags(file):
    #         t = time.time()
    #         cols = [
    #             'Format',
    #             'Units',
    #             'Operator',
    #             'Probes',
    #             'Current',
    #             'Loop dimensions'
    #         ]
    #         tags = {}
    #         matches = self.re_tags.findall(file)
    #
    #         if not matches:
    #             raise ValueError(f'Error parsing the tags. No matches were found in {self.filepath.name}.')
    #
    #         matches = matches[0]
    #         if len(cols) != len(matches):
    #             raise ValueError('Error in number of tags parsed')
    #         # XY probe  # , SOA, tool #, tool id
    #         for i, match in enumerate(matches):
    #             if cols[i] == 'Operator':
    #                 # Remove ~ from the operator name if it exists
    #                 match = match.split('~')[0].strip()
    #             elif cols[i] == 'Units':
    #                 if match == 'nanoTesla/sec' or match == 'nT/s':
    #                     match = 'nT/s'
    #                 elif match == 'picoTesla' or match == 'pT':
    #                     match = 'pT'
    #             elif cols[i] == 'Probes':
    #                 probe_cols = ['XY probe number', 'SOA', 'Tool number', 'Tool ID']
    #                 match = dict(zip(probe_cols, match.split()))
    #             elif cols[i] == 'Current':
    #                 match = float(match)
    #             elif cols[i] == 'Loop dimensions':
    #                 match = match.strip()
    #             tags[cols[i]] = match
    #         print(f"PEMParser - Time to parse tags of {self.filepath.name}: {time.time() - t}")
    #         return tags
    #
    #     def parse_loop(file):
    #         # Find all re matches
    #         t = time.time()
    #         matches = re.findall(self.re_loop_coords, file)
    #         if matches:
    #             return matches
    #         else:
    #             print(f"No loop coordinates found in {os.path.basename(filepath)}")
    #         print(f"PEMParser - Time to parse loop of {self.filepath.name}: {time.time() - t}")
    #
    #     def parse_line(file):
    #         t = time.time()
    #         # Find all re matches
    #         matches = re.findall(self.re_line_coords, file)
    #         if matches:
    #             return matches
    #         else:
    #             print(f"No line coordinates found in {os.path.basename(filepath)}")
    #         print(f"PEMParser - Time to parse line of {self.filepath.name}: {time.time() - t}")
    #
    #     def parse_notes(file):
    #         t = time.time()
    #         notes = []
    #         for match in self.re_notes.finditer(file):
    #             for group, index in self.re_notes.groupindex.items():
    #                 notes.append(match.group(index))
    #         print(f"PEMParser - Time to parse notes of {self.filepath.name}: {time.time() - t}")
    #         return notes
    #
    #     def parse_header(file):
    #         t = time.time()
    #
    #         header_cols = [
    #             'Client',
    #             'Grid',
    #             'Line',
    #             'Loop',
    #             'Date'
    #         ]
    #
    #         survey_param_cols = [
    #             'Survey type',
    #             'Convention',
    #             'Sync',
    #             'Timebase',
    #             'Ramp',
    #             'Number of channels',
    #             'Number of readings'
    #         ]
    #
    #         receiver_param_cols = [
    #             'Receiver number',
    #             'Rx software version',
    #             'Rx software version date',
    #             'Rx file name',
    #             'Normalized',
    #             'Primary field value',
    #             'Coil area',
    #             'Loop polarity'
    #         ]
    #
    #         header = {}
    #         matches = self.re_header.search(file)
    #
    #         if not matches:
    #             raise ValueError(f'Error parsing header. No matches were found in {self.filepath.name}.')
    #
    #         matches = matches.groups()
    #
    #         if len(matches) != 8:
    #             raise ValueError(f'Error parsing header. Not all matches were found in {self.filepath.name}.')
    #
    #         # Starting from index 1 to ignore the '~' match
    #         for i, match in enumerate(matches[1:6]):
    #             header[header_cols[i]] = match
    #
    #         # Survey parameters
    #         survey_params = matches[6].split(' ')
    #         if not survey_params:
    #             raise ValueError(f'Error parsing survey parameters in {self.filepath.name}.')
    #
    #         for j, match in enumerate(survey_params):
    #             if survey_param_cols[j] in ['Timebase', 'Ramp']:
    #                 match = float(match)
    #             elif survey_param_cols[j] in ['Number of channels', 'Number of readings']:
    #                 match = int(match)
    #             header[survey_param_cols[j]] = match
    #
    #         # Receiver parameters
    #         receiver_params = matches[7].split(' ')
    #         if not receiver_params:
    #             raise ValueError(f'Error parsing receiver parameters in {self.filepath.name}.')
    #
    #         for k, match in enumerate(receiver_params):
    #             if receiver_param_cols[k] in ['Primary field value', 'Coil area']:
    #                 match = int(match)
    #             header[receiver_param_cols[k]] = match
    #
    #         print(f"PEMParser - Time to parse header of {self.filepath.name}: {time.time() - t}")
    #         return header
    #
    #     def parse_channel_times(file, units=None):
    #
    #         def channel_table(channel_times):
    #             """
    #             Channel times table data frame with channel start, end, center, width, and whether the channel is
    #             to be removed when the file is split
    #             :param channel_times: pandas Series: float of each channel time read from a PEM file header.
    #             :return: pandas DataFrame
    #             """
    #
    #             def check_removable(row):
    #                 """
    #                 Return True if the passed channel times is a channel that should be removed when the file is split.
    #                 :param row: pandas row from the channel table
    #                 :return: bool: True if the channel should be removed, else False.
    #                 """
    #                 if units == 'nT/s':
    #                     if row.Start == -0.0002:
    #                         return False
    #                     elif row.Start > 0:
    #                         return False
    #                     else:
    #                         return True
    #
    #                 elif units == 'pT':
    #                     if row.Start == -0.002:
    #                         return False
    #                     elif row.Start > 0:
    #                         return False
    #                     else:
    #                         return True
    #                 else:
    #                     raise ValueError('Units parsed from tags is invalid')
    #
    #             def find_last_off_time():
    #                 """
    #                 Find where the next channel width is less than half the previous channel width, which indicates
    #                 the start of the next on-time.
    #                 :return: int: Row index of the last off-time channel
    #                 """
    #                 filt = table['Remove'] == False
    #                 for index, row in table[filt][1:-1].iterrows():
    #                     next_row = table.loc[index + 1]
    #                     if row.Width > (next_row.Width * 2):
    #                         return index + 1
    #
    #             # Create the channel times table
    #             table = pd.DataFrame(columns=['Start', 'End', 'Center', 'Width', 'Remove'])
    #             # Convert the times to miliseconds
    #             times = channel_times
    #
    #             # The first number to the second last number are the start times
    #             table['Start'] = list(times[:-1])
    #             # The second number to the last number are the end times
    #             table['End'] = list(times[1:])
    #             table['Width'] = table['End'] - table['Start']
    #             table['Center'] = (table['Width'] / 2) + table['Start']
    #
    #             # PEM files seem to always have a repeating channel time as the third number, so the second row
    #             # must be removed.
    #             table.drop(1, inplace=True)
    #             table.reset_index(drop=True, inplace=True)
    #
    #             # If the file is a PP file
    #             if table.Width.max() < 10 ** -5:
    #                 table['Remove'] = False
    #             else:
    #                 # Configure which channels to remove for the first on-time
    #                 table['Remove'] = table.apply(check_removable, axis=1)
    #
    #                 # Configure each channel after the last off-time channel (only for full waveform)
    #                 last_off_time_channel = find_last_off_time()
    #                 if last_off_time_channel:
    #                     table.loc[last_off_time_channel:, 'Remove'] = table.loc[last_off_time_channel:, 'Remove'].map(lambda x: True)
    #             return table
    #
    #         t = time.time()
    #         matches = self.re_channel_times.search(file)
    #         if not matches:
    #             raise ValueError(f'Error parsing channel times. No matches were found in {self.filepath.name}.')
    #
    #         table = channel_table(np.array(matches.group(1).split(), dtype=float))
    #         print(f"PEMParser - Time to parse channel table of {self.filepath.name}: {time.time() - t}")
    #         return table
    #
    #     def parse_data(file):
    #         t = time.time()
    #
    #         cols = [
    #             'Station',
    #             'Component',
    #             'Reading_index',
    #             'Gain',
    #             'Rx_type',
    #             'ZTS',
    #             'Coil_delay',
    #             'Number_of_stacks',
    #             'Readings_per_set',
    #             'Reading_number',
    #             'RAD_tool',
    #             'Reading'
    #         ]
    #
    #         matches = self.re_data.findall(file)
    #         if not matches:
    #             raise ValueError(f'Error parsing data. No matches were found in {self.filepath.name}.')
    #
    #         df = pd.DataFrame(matches, columns=cols)
    #         # Create a RAD tool ID number to be used for grouping up readings for probe rotation, since the CDR2
    #         # and CDR3 don't count reading numbers the same way.
    #         df['RAD_tool'] = df['RAD_tool'].map(lambda x: RADTool().from_match(x))
    #         df['RAD_ID'] = df['RAD_tool'].map(lambda x: x.id)
    #         df['Reading'] = df['Reading'].map(lambda x: np.array(x.split(), dtype=float))
    #         df[['Reading_index',
    #             'Gain',
    #             'Coil_delay',
    #             'Number_of_stacks',
    #             'Readings_per_set',
    #             'Reading_number']] = df[['Reading_index',
    #                                      'Gain',
    #                                      'Coil_delay',
    #                                      'Number_of_stacks',
    #                                      'Readings_per_set',
    #                                      'Reading_number']].astype(int)
    #         df['ZTS'] = df['ZTS'].astype(float)
    #         print(f"PEMParser - Time to parse data of {self.filepath.name}: {time.time() - t}")
    #         return df
    #
    #     assert Path(filepath).is_file(), f"{filepath.name} is not a file"
    #     self.filepath = Path(filepath)
    #     print(f"Parsing {self.filepath.name}")
    #
    #     t = time.time()
    #     file = None
    #     with open(filepath, "rt") as in_file:
    #         file = in_file.read()
    #
    #     tags = parse_tags(file)
    #     loop_coords = parse_loop(file)
    #     line_coords = parse_line(file)
    #     notes = parse_notes(file)
    #     header = parse_header(file)
    #     channel_table = parse_channel_times(file, units=tags.get('Units'))
    #     data = parse_data(file)
    #
    #     print(f"PEMParser - Time to parse {self.filepath.name}: {time.time() - t}")
    #
    #     return PEMFile().from_pem(tags, loop_coords, line_coords, notes, header, channel_table, data, filepath=filepath)

    def parse(self, filepath):
        """
        Parses a PEM file to extract all information and creates a PEMFile object out of it.
        :param filepath: string containing path to a PEM file
        :return: A PEM_File object representing the data found inside of filename
        """

        def parse_tags(text):
            # t = time.time()
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

            # print(f"PEMParser - Time to parse tags of {self.filepath.name}: {time.time() - t}")
            return tags

        def parse_loop(text):
            """
            Parse the loop section (<L> tags) of the PEM File
            :param text: str, raw loop string from the PEM file
            :return: list of everything in the <L> tag section
            """
            assert text, f'Error parsing the loop coordinates. No matches were found in {self.filepath.name}.'

            # t = time.time()
            text = text.strip().split('\n')
            loop_text = [t.strip().split() for t in text if t.startswith('<L')]
            # print(f"PEMParser - Time to parse loop of {self.filepath.name}: {time.time() - t}")
            return loop_text

        def parse_line(text):
            """
            Parse the line section (<P> tags) of the PEM File
            :param text: str, raw line string from the PEM file
            :return: list of everything in the <P> tag section
            """
            assert text, f'Error parsing the line coordinates. No matches were found in {self.filepath.name}.'

            # t = time.time()
            text = text.strip().split('\n')
            line_text = [t.strip().split() for t in text if t.startswith('<P')]
            # print(f"PEMParser - Time to parse line of {self.filepath.name}: {time.time() - t}")
            return line_text

        def parse_notes(file):
            """
            Parse the notes of the PEM File, which are any lines with <GEN> or <HE> tags.
            :param file: str of the .PEM file
            :return: list of notes
            """
            # t = time.time()
            notes = re.findall(r'<GEN>.*|<HE\d>.*|<CRS>.*', file)
            # Remove the 'xxxxxxxxxxxxxxxx' notes
            for note in reversed(notes):
                if 'xxx' in note.lower() or re.match('<GEN> NOTES', note):
                    notes.remove(note)

            # print(f"PEMParser - Time to parse notes of {self.filepath.name}: {time.time() - t}")
            return notes

        def parse_header(text):
            """
            Parse the header section of the PEM File, which is the client name down to the channel table.
            :param text: str, raw header string from the PEM file
            :return: dictionary of the header items
            """

            assert text, f'Error parsing the tags. No matches were found in {self.filepath.name}.'
            # t1 = time.time()

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

            # print(f"PEMParser - Time to parse header of {self.filepath.name}: {time.time() - t1}")
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
                    filt = table['Remove'] == False
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
            # t = time.time()

            table = channel_table(np.array(text.split(), dtype=float))
            assert len(table) == num_channels or len(table) == num_channels + 1, \
                f"{len(table)} channels found in channel times section instead of {num_channels} found in header of {self.filepath.name}"
            # print(f"PEMParser - Time to parse channel table of {self.filepath.name}: {time.time() - t}")
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
                'Reading'
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
                reading_index = re.search('\d+', head[1]).group()
                gain = head[2]
                rx_type = head[3]
                zts = head[4]
                coil_delay = head[5]
                num_stakcs = head[6]
                readings_per_set = head[7]
                reading_number = head[8]
                rad_tool = data[1]
                decay = ''.join(data[2:])
                return [station, comp, reading_index, gain, rx_type, zts, coil_delay, num_stakcs, readings_per_set,
                        reading_number, rad_tool, decay]

            assert text, f'No data found in {self.filepath.name}.'
            # t = time.time()

            # Each reading is separated by two return characters
            text = text.strip().split('\n\n')

            data = []
            # Format each reading to be added to the data frame. Faster than creating Series object per row.
            for reading in text:
                data.append(format_data(reading))

            # Create the data frame
            df = pd.DataFrame(data, columns=cols)

            # Format the columns of the data frame
            # Create a RAD tool ID number to be used for grouping up readings for probe rotation, since the CDR2
            # and CDR3 don't count reading numbers the same way.
            df['RAD_tool'] = df['RAD_tool'].map(lambda x: RADTool().from_match(x))
            df['RAD_ID'] = df['RAD_tool'].map(lambda x: x.id)
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
            # print(f"PEMParser - Time to parse data of {self.filepath.name}: {time.time() - t}")
            return df

        assert Path(filepath).is_file(), f"{filepath.name} is not a file"
        self.filepath = Path(filepath)
        print(f"Parsing {self.filepath.name}")

        # t = time.time()
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

        # print(f"PEMParser - Time to parse {self.filepath.name}: {time.time() - t}")

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

            # t = time.time()

            if text[-1] == 'ZTS - Narrow':
                self.pp_file = True

            header = dict()
            header['Format'] = str(210)
            header['Units'] = 'pT' if 'flux' in text[6].lower() or 'squid' in text[6].lower() else 'nT/s'
            header['Operator'] = text[11]
            header['Probes'] = {'XY probe number': '0', 'SOA': '0', 'Tool number': '0', 'Tool ID': '0'}
            header['Current'] = float(text[12])
            header['Loop dimensions'] = ' '.join(re.split('\D', text[13])) + ' 0'

            header['Client'] = text[8]
            header['Grid'] = text[9]
            header['Line_name'] = text[7]
            header['Loop_name'] = text[10]
            header['Date'] = datetime.strptime(re.sub('\s+', '', text[14]), '%m/%d/%y').strftime('%B %d, %Y')
            header['Survey type'] = text[6]
            header['Convention'] = text[15]
            header['Sync'] = text[18]
            header['Timebase'] = float(text[16].split('ms')[0]) if 'ms' in text[16] else float(text[16].split()[0])
            header['Ramp'] = float(text[17])
            header['Number of channels'] = int(text[25])
            header['Number of readings'] = int(text[24])
            header['Receiver number'] = text[1].split()[-1]
            header['Rx software version'] = text[2].split()[-1]
            header['Rx software version date'] = re.sub('\s', '',
                                                        re.sub('Released: ', '', text[3])) + f"s{text[26]}"
            header['Rx file name'] = text[5]
            header['Normalized'] = 'N' if text[19] == 'Norm.' else 'Normalized??'
            header['Primary field value'] = text[23]
            header['Coil area'] = float(text[20])
            header['Coil delay'] = int(text[21])
            header['Loop polarity'] = '+'
            # print(f"DMPParser - Time to parse header of {self.filepath.name}: {time.time() - t}")

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
                    filt = table['Remove'] == False
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

            # t1 = time.time()
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
            # print(f"DMPParser - Time to parse channel times of {self.filepath.name}: {time.time() - t1}")
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
                reading_index = re.search('\d+', head[1]).group()
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

            # t1 = time.time()
            # df = pd.DataFrame(columns=cols)

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
            # print(f"DMPParser - Time to parse data of {self.filepath.name} file: {time.time() - t1}")
            return df

        assert Path(filepath).is_file(), f"{filepath.name} is not a file"
        self.filepath = Path(filepath)
        print(f"Parsing {self.filepath.name}")

        # t = time.time()
        # Read the contents of the file
        with open(filepath, 'rt') as file:
            contents = file.read()

        # Split the content up into sections
        # Splitting new .DMP files
        if '&&' in contents:
            old_dmp = False
            raw_header = re.split('&&', contents)[0].strip()
            raw_channel_table = re.split('<<', re.split('\$\$', contents)[0])[1].strip()
            raw_notes = re.split('<<', re.split('&&', contents)[1])[0].strip()  # The content between '&&' and '<<'
            raw_data = re.split('\$\$', contents)[1].strip()

            # Don't see any notes in old .DMP files so only included here
            notes = parse_notes(raw_notes)

        # Splitting old .DMP files
        else:
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

        assert len(data) == header.get('Number of readings'), \
            f"Not all readings found in {self.filepath.name}"

        pem_file = PEMFile().from_dmp(header, channel_table, data, self.filepath, notes=notes)
        # print(f"DMPParser - Time to convert PEMFile: {time.time() - t}")
        return pem_file

    def parse_dmp2(self, filepath):
        """
        Create a PEMFile object by parsing a .DMP2 file.
        :param filepath: str, filepath of the .DMP2 file
        :return: PEMFile object
        """
        def parse_channel_times(header_dict, units=None):
            """
            Convert the channel table in the .DMP file to a PEM channel times table DataFrame
            :param header_dict: dict, parsed header section of the .DMP file
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
                    filt = table['Remove'] == False
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

            # t = time.time()

            table = channel_table(header['Channel_times'] / 10 ** 6)  # Convert to seconds
            assert len(table) == int(header['Number of channels']) or len(table) == int(header['Number of channels']) + 1, \
                f"{len(table)} channels found in channel times section instead of {int(header['Number of channels'])} found in header of {self.filepath.name}"
            # print(f"PEMParser - Time to parse channel table of {self.filepath.name}: {time.time() - t}")
            return table

        def parse_header(header_content):
            """
            Parse the header section of the DMP File
            :param header_content: list of str of the header section of the .DMP2 file
            :return: dict
            """
            # t1 = time.time()
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

            header['Survey type'] = re.sub('\s+', '_', s['Survey_Type'])
            header['Convention'] = 'Metric'
            header['Sync'] = re.sub('\s+', '-', s['Sync_Type'])
            header['Timebase'] = float(s['Time_Base'].split()[0])
            header['Ramp'] = float(s['Ramp_Length'])
            header['Number of channels'] = len(s['Channel_Time']) - 1
            header['Number of readings'] = int(s['Total_Readings'])

            header['Receiver number'] = s['Crone_Digital_PEM_Receiver']
            header['Rx software version'] = s['Software_Version']
            header['Rx software version date'] = re.sub('\s+', '', s['Software_Release_Date'])
            header['Rx file name'] = s['File_Name']
            header['Normalized'] = 'N'
            header['Primary field value'] = '1000'
            header['Coil area'] = float(s['Coil_Area'])  # / 10 ** 3  # Doesn't work with dB/dt
            header['Loop polarity'] = '+'
            # header['Notes'] = [note for note in s['File_Notes'].split('\n')]

            # print(f"PEMParser - Time to parse header of {self.filepath.name}: {time.time() - t1}")
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
                    year = re.search('(\d+\W\d+\W)(\d+)', date_string).group(2)
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
                arr = [re.split(':\s?', d, maxsplit=1) for d in split_reading if
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
            pem_df['del_flag'] = df['Deleted'].map(lambda x: False if x.strip() == 'F' else True)
            pem_df['Overload'] = df['Overload'].map(lambda x: False if x.strip() == 'F' else True)

            # Find the overload readings and set them to be deleted
            overload_filt = pem_df.loc[:, 'Overload'] == True
            pem_df.loc[overload_filt, 'del_flag'] = True

            pem_df['datetime'] = df['Date_Time'].map(str_to_datetime)
            print(f"DMPParser - Time to parse data of {self.filepath.name}: {time.time() - t1}")
            return pem_df

        assert Path(filepath).is_file(), f"{filepath.name} is not a file"
        self.filepath = Path(filepath)
        print(f"Parsing {self.filepath.name}")

        # t1 = time.time()
        # Read the contents of the file
        with open(filepath, 'rt') as file:
            contents = file.read()
            # Change the different occurences of header titles between DMP2 file versions so they are the same.
            contents = re.sub('isDeleted', 'Deleted', contents)
            contents = re.sub('Loop_Height', 'Loop_Length', contents)
            contents = re.sub('Released', 'Software_Release_Date', contents)

            # Find the year of the date of the file, and if necessary convert the year format to %Y instead of %y
            date = re.search('Date: (\d+\W\d+\W\d+)', contents).group(1)

            # If date is separated with hyphens, the date format is Y-m-d instead of m-d-y
            if '-' in date:
                date_str = datetime.strptime(date, '%Y-%m-%d').strftime('%B %d, %Y')
            else:
                year = re.search('(\d+\W\d+\W)(\d+)', date).group(2)

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
        data = parse_data(scontents[1], units=header.get('Units'))
        channel_table = parse_channel_times(header, units=header.get('Units'))
        # notes = header['Notes']

        # print(f'DMPParser - Time to parse {self.filepath.name} file: {time.time() - t1}')
        pem_file = PEMFile().from_dmp(header, channel_table, data, self.filepath)
        return pem_file


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

        result_list = [str(self.pem_file.client),
                       str(self.pem_file.grid),
                       str(self.pem_file.line_name),
                       str(self.pem_file.loop_name),
                       str(self.pem_file.date),
                       ' '.join([str(self.pem_file.survey_type),
                                 str(self.pem_file.convention),
                                 str(self.pem_file.sync),
                                 str(self.pem_file.timebase),
                                 str(int(self.pem_file.ramp)),
                                 str(self.pem_file.number_of_channels),
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

    def serialize_data(self):
        df = self.pem_file.get_data(sorted=True)

        # Remove deleted readings
        filt = df.del_flag == False
        df = df[filt]

        def serialize_reading(reading):
            result = ' '.join([reading['Station'],
                               reading['Component'] + 'R' + f"{reading['Reading_index']:g}",
                               f"{reading['Gain']:g}",
                               reading['Rx_type'],
                               f"{reading['ZTS']:g}",
                               f"{reading['Coil_delay']:g}",
                               f"{reading['Number_of_stacks']:g}",
                               f"{reading['Readings_per_set']:g}",
                               f"{reading['Reading_number']:g}",
                               # f"{reading['del_flag']:g}",
                               # f"{reading['Overload']:g}",
                               # f"{reading['datetime']:g}",
                               ]) + '\n'
            rad = reading['RAD_tool'].to_string()
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

    def serialize(self, pem_file):
        """
        Create a string of a PEM file to be printed to a text file.
        :param pem_file: PEM_File object
        :return: A string in PEM file format containing the data found inside of pem_file
        """
        self.pem_file = pem_file

        # t = time.time()
        result = self.serialize_tags() + '\n'
        result += self.serialize_loop_coords() + '\n'
        result += self.serialize_line_coords() + '\n'
        result += self.serialize_notes()
        result += '~\n'
        result += self.serialize_header() + '\n'
        result += self.serialize_data()
        # print(f"Time to seralize {pem_file.filepath.name}: {time.time() - t}")
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
                raise ValueError('Error in the number of the RAD tool values')

        else:
            raise ValueError('Error in D value of RAD tool line. D value is neither D5 nor D7.')

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

        self.D = f"D{len(text)}"
        self.Hx = float(text[0])
        self.gx = float(text[1])
        self.Hy = float(text[2])
        self.gy = float(text[3])
        self.Hz = float(text[4])
        self.gz = float(text[5])
        if len(text) > 6:
            self.T = float(text[6])

        self.id = ''.join([
            str(self.Hx),
            str(self.gx),
            str(self.Hy),
            str(self.gy),
            str(self.Hz),
            str(self.gz),
        ])

        return self

    def get_azimuth(self):
        """
        Calculate the azimuth of the RAD tool object. Must be D7.
        :return: float, azimuth
        """
        if not self.has_tool_values():
            return None

        g = math.sqrt(sum([self.gx ** 2, self.gy ** 2, self.gz ** 2]))
        numer = ((self.Hz * self.gy) - (self.Hy * self.gz)) * g
        denumer = self.Hx * (self.gy ** 2 + self.gz ** 2) - (self.Hy * self.gx * self.gy) - (self.Hz * self.gx * self.gz)
        # TODO check that the azimuth is correct
        azimuth = math.degrees(math.atan2(numer, denumer))
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

    def is_rotated(self):
        return True if self.angle_used is not None else False

    def to_string(self):
        """
        Create a string for PEM serialization
        :return: str
        """
        if self.D == 'D5':
            result = [self.D]
            if self.rotation_type is None:
                result.append(f"{self.x:g}")
                result.append(f"{self.y:g}")
                result.append(f"{self.z:g}")

            elif self.rotation_type == 'acc':
                result.append(f"{self.gx:g}")
                result.append(f"{self.gy:g}")
                result.append(f"{self.gz:g}")

            elif self.rotation_type == 'mag':
                result.append(f"{self.Hx:g}")
                result.append(f"{self.Hy:g}")
                result.append(f"{self.Hz:g}")

            result.append(f"{self.roll_angle:g}")
            result.append(f"{self.dip:g}")

        # elif self.D == 'D6':
        #     result = [
        #         self.D,
        #         f"{self.Hx:g}",
        #         f"{self.gx:g}",
        #         f"{self.Hy:g}",
        #         f"{self.gy:g}",
        #         f"{self.Hz:g}",
        #         f"{self.gz:g}",
        #     ]

        elif self.D == 'D7' or self.D == 'D6':
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
                # else:
                #     result.append(f"{self.roll_angle:g}")

                result.append(f"{self.get_dip():g}")
                result.append(self.R)
                result.append(f"{self.angle_used:g}")
            else:
                if self.T is not None:
                    result.append(f"{self.T:g}")
                else:
                    result.append('0')

        else:
            raise ValueError('RADTool D value is neither "D5", "D6", nor "D7"')

        return ' '.join(result)


if __name__ == '__main__':
    from src.pem.pem_getter import PEMGetter

    dparse = DMPParser()
    pemparse = PEMParser()
    pg = PEMGetter()
    # pem_file = pg.get_pems(client='PEM Rotation', file='BX-081.PEM')[0]
    # prep_pem, _ = pem_file.prep_rotation()
    # rotated_pem = prep_pem.rotate('pp')

    # pem_file = pemparse.parse(r'C:\Users\Mortulo\PycharmProjects\PEMPro\sample_files\PEMGetter files\Kazzinc\7400NAv.PEM')
    # pem_file = pemparse.parse(r'N:\GeophysicsShare\Dave\Eric\Norman\Kevin\M-20-539 (new dec)\RAW\Eric\XY-Collar.PEM')

    file = r'C:\_Data\2018\BHP\SPEM\OCLT01\DMP\May 22, 2018\Dump\L1E.DMP'
    # file = str(Path(__file__).parents[2].joinpath('sample_files/PEMGetter files/PEM Rotation/BX-081.PEM'))
    file = dparse.parse_dmp(file)

    # out = str(Path(__file__).parents[2] / 'sample_files' / 'test results'/f'{file.filepath.stem} - test conversion.pem')
    # print(file.to_string(), file=open(out, 'w'))
    # os.startfile(out)