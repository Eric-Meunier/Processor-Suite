import math
import os
import re
import time

import natsort
import numpy as np
import pandas as pd

from pathlib import Path
from src.gps.gps_editor import TransmitterLoop, SurveyLine, BoreholeCollar, BoreholeSegments, BoreholeGeometry, CRS
from src.mag_field.mag_field_calculator import MagneticFieldCalculator


def sort_data(data):
    # Sort the data frame
    df = data.reindex(index=natsort.order_by_index(
        data.index, natsort.index_natsorted(zip(data.Component, data.Station, data['Reading number']))))
    # Reset the index
    df.reset_index(drop=True, inplace=True)
    return df


def convert_station(station):
    """
    Converts a single station name into a number, negative if the stations was S or W
    :return: Integer station number
    """
    if re.match(r"\d+(S|W)", station):
        station = (-int(re.sub(r"\D", "", station)))
    else:
        station = (int(re.sub(r"\D", "", station)))
    return station


class PEMFile:
    """
    PEM file class
    """
    def __init__(self, tags, loop_coords, line_coords, notes, header, channel_table, data, filepath=None):
        self.format = tags.get('Format')
        self.units = tags.get('Units')
        self.operator = tags.get('Operator')
        self.probes = tags.get('Probes')
        self.current = tags.get('Current')
        self.loop_dimensions = tags.get('Loop dimensions')

        self.client = header.get('Client')
        self.grid = header.get('Grid')
        self.line_name = header.get('Line')
        self.loop_name = header.get('Loop')
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
        self.data = data
        self.filepath = filepath
        self.filename = os.path.basename(filepath)

        crs = self.get_crs()
        self.loop = TransmitterLoop(loop_coords, crs=crs)
        if self.is_borehole():
            collar = BoreholeCollar(line_coords, crs=crs)
            segments = BoreholeSegments(line_coords)
            self.geometry = BoreholeGeometry(collar, segments)
        else:
            self.line = SurveyLine(line_coords, crs=crs)

        self.unsplit_data = None
        self.unaveraged_data = None
        self.old_filepath = None

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
        return self.data['RAD tool'].map(lambda x: x.rotated).all()

    def is_averaged(self):
        data = self.data[['Station', 'Component']]
        if any(data.duplicated()):
            return False
        else:
            return True

    def is_split(self):
        if self.channel_times.Remove.any():
            return False
        else:
            return True

    def has_collar_gps(self):
        if self.is_borehole():
            if not self.geometry.collar.df.empty and all(self.geometry.collar.df):
                return True
            else:
                return False
        else:
            return False

    def has_geometry(self):
        if self.is_borehole():
            if not self.geometry.segments.df.empty and all(self.geometry.segments.df):
                return True
            else:
                return False
        else:
            return False

    def has_loop_gps(self):
        if not self.loop.df.empty and all(self.loop.df):
            return True
        else:
            return False

    def has_station_gps(self):
        if not self.is_borehole():
            if not self.line.df.empty and all(self.line.df):
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
        for note in self.notes:
            if 'CRS:' in note:
                crs = re.split('CRS: ', note)[-1]
                s = crs.split()
                system = s[0]
                zone = f"{s[2]} {s[3]}"
                datum = f"{s[4]} {s[5]}"
                # print(f"CRS is {system} Zone {zone} {'North' if north else 'South'}, {datum}")
                return CRS().from_dict({'System': system, 'Zone': zone, 'Datum': datum})
            else:
                return CRS()
        return None

    def get_loop(self, sorted=True, closed=False):
        return self.loop.get_loop(sorted=sorted, closed=closed)

    def get_line(self, sorted=True):
        return self.line.get_line(sorted=sorted)

    def get_collar(self):
        return self.geometry.get_collar()

    def get_segments(self):
        return self.geometry.get_segments()

    def get_geometry(self):
        return self.geometry

    def get_notes(self):
        return self.notes

    def get_data(self, sorted=True):
        if sorted:
            data = sort_data(self.data)
        else:
            data = self.data
        return data

    def get_profile_data(self, component=None):
        """
        Transform the readings in the data in a manner to be plotted as a profile
        :param component: str, used to filter the profile data and only keep the given component
        :return: pandas DataFrame object with Station, Component and all channels as columns.
        """
        profile = pd.DataFrame.from_dict(dict(zip(self.data.Reading.index, self.data.Reading.values))).T
        profile.insert(0, 'Station', self.data.Station.map(convert_station))
        profile.insert(1, 'Component', self.data.Component)

        if component:
            filt = profile['Component'] == component.upper()
            profile = profile[filt]

        profile.sort_values(by=['Component', 'Station'], inplace=True)
        return profile

    def get_components(self):
        components = list(self.data['Component'].unique())
        return components

    def get_unique_stations(self, converted=False):
        """
        Return a list of unique stations in the PEM file.
        :param converted: Bool, whether to convert the stations to Int
        :return: list
        """
        stations = self.data.Station.unique()
        if converted:
            stations = [convert_station(station) for station in stations]
        return stations

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

    def get_survey_type(self):

        if self.survey_type.casefold() == 's-coil' or self.survey_type.casefold() == 'surface':
            survey_type = 'Surface Induction'
        elif self.survey_type.casefold() == 'borehole':
            survey_type = 'Borehole Induction'
        elif self.survey_type.casefold() == 'b-rad':
            survey_type = 'Borehole Induction'
        elif self.survey_type.casefold() == 'b-otool':
            survey_type = 'Borehole Induction'
        elif self.survey_type.casefold() == 's-flux':
            survey_type = 'Surface Fluxgate'
        elif self.survey_type.casefold() == 'bh-flux':
            survey_type = 'Borehole Fluxgate'
        elif self.survey_type.casefold() == 's-squid':
            survey_type = 'SQUID'
        else:
            raise ValueError(f"Invalid survey type: {self.survey_type}")

        return survey_type

    def to_string(self):
        """
        Return the text format of the PEM file
        :return: str: Full text of the PEM file
        """
        ps = PEMSerializer()
        text = ps.serialize(self)
        return text

    def average(self):
        """
        Averages the data of the PEM file object. Uses a weighted average.
        :return: PEM file object
        """
        if self.is_averaged():
            print(f"{self.filename} is already averaged")
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
            new_data_df['Number of stacks'] = group['Number of stacks'].sum()
            # Add the weighted average of the readings to the reading column
            new_data_df['Reading'] = np.average(group.Reading.to_list(),
                                                axis=0,
                                                weights=group['Number of stacks'].to_list())
            return new_data_df

        # Create a data frame with all data averaged
        df = self.data.groupby(['Station', 'Component']).apply(weighted_average)
        # Sort the data frame
        df = sort_data(df)
        self.data = df
        return self

    def split(self):
        """
        Remove the on-time channels of the PEM file object
        :return: PEM file object with split data
        """
        if self.is_split():
            print(f"{self.filename} is already split.")
            return

        # Only keep the select channels from each reading
        self.data.Reading = self.data.Reading.map(lambda x: x[~self.channel_times.Remove])
        # Create a filter and update the channels table
        filt = self.channel_times.Remove == False
        self.channel_times = self.channel_times[filt]
        # Update the PEM file's number of channels attribute
        self.number_of_channels = len(self.channel_times.index) - 1
        return self

    def scale_coil_area(self, coil_area):
        """
        Scale the data by a change in coil area
        :param coil_area: int: new coil area
        :return: PEMFile object: self with data scaled
        """
        new_coil_area = coil_area
        assert isinstance(new_coil_area, int), "New coil area is not type int"
        old_coil_area = self.coil_area

        scale_factor = float(old_coil_area / new_coil_area)
        self.data.Reading = self.data.Reading.map(lambda x: x * scale_factor)
        print(f"{self.filename} coil area scaled to {new_coil_area} from {old_coil_area}")

        self.coil_area = new_coil_area
        self.notes.append(f'<HE3> Data scaled by coil area change of {old_coil_area}/{new_coil_area}')
        return self

    def scale_current(self, current):
        """
        Scale the data by a change in current
        :param current: int: new current
        :return: PEMFile object: self with data scaled
        """
        new_current = current
        assert isinstance(new_current, float), "New current is not type float"
        old_current = self.current

        scale_factor = float(new_current / old_current)
        self.data.Reading = self.data.Reading.map(lambda x: x * scale_factor)
        print(f"{self.filename} current scaled to {new_current}A from {old_current}A")

        self.current = new_current
        self.notes.append(f'<HE3> Data scaled by current change of {new_current}A/{old_current}A')
        return self

    def rotate(self, method='acc', soa=0):
        """
        Rotate the XY data of the PEM file.
        Formula: X' = Xcos(roll) - Ysin(roll), Y' = Xsin(roll) + Ycos(roll)
        :param method: str: Method of rotation, either 'acc' for accelerometer or 'mag' for magnetic
        :param soa: int: Sensor offset angle
        :return: PEM file object with rotated data
        """
        assert self.is_borehole(), f"{self.filename} is not a borehole file."

        # if self.data['RAD tool'].map(lambda x: x.D == 'D5').any():
        #     print(f"{self.filename} appears to be a file that has been run through Otool, thus it will not be rotated.")
        #     return self
        # else:

        def rotate_data(row, method):
            """
            Rotate the data for a given reading
            :param row: pandas DataFrame: data frame of the readings to rotate. Must contain at least one
            reading from X and Y components, and the RAD tool values for all readings must all be the same.
            :param type: str: type of rotation to apply. Either 'acc' for accelerometer or 'mag' for magnetic
            :return: pandas DataFrame: data frame of the readings with the data rotated.
            """
            if row.Component.nunique() < 2:
                r = row.iloc[0]
                print(f"Removing {r.Station} - {r.Component}, reading {r['Reading number']}, index {r['Reading index']} since it has no pairing X/Y reading")
                # Set the station name as NaN so it can be easily removed later.
                row['Station'] = np.nan
                return row

            assert len(row['RAD ID'].unique()) == 1, 'More than 1 unique RAD tool set'
            print(f"Number of unique RAD tool sets: {len(row['RAD ID'].unique())}")

            def rotate_x(x_values, y_pair, roll_angle):
                """
                Rotate the X data of a reading
                Formula: X' = Xcos(roll) - Ysin(roll)
                :param x: list: list of x readings to rotated
                :param y_pair: list: list of paired y reading
                :param roll_angle: float: calculated roll angle
                :return: list: rotated x values
                """
                rotated_x = [x * math.cos(math.radians(roll_angle)) - y * math.sin(math.radians(roll_angle)) for (x, y) in zip(x_values, y_pair)]
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
                rotated_y = [x * math.sin(math.radians(roll_angle)) + y * math.cos(math.radians(roll_angle)) for (x, y) in zip(x_pair, y_values)]
                return np.array(rotated_y, dtype=float)

            x_data = row[row['Component'] == 'X']
            y_data = row[row['Component'] == 'Y']
            # Save the first reading of each component to be used a the 'pair' reading for rotation
            x_pair = x_data.iloc[0].Reading
            y_pair = y_data.iloc[0].Reading

            rad = row.iloc[0]['RAD tool']
            # Accelerometer rotation
            if method == 'acc':
                if rad.D == 'D5':
                    x, y, z = rad.x, rad.y, rad.z
                else:
                    x, y, z = rad.gx, rad.gy, rad.gz

                theta = math.atan2(y, z)
                cc_roll_angle = 360 - math.degrees(theta) if y < 0 else math.degrees(theta)
                roll_angle = 360 - cc_roll_angle if y > 0 else cc_roll_angle
                if roll_angle >= 360:
                    roll_angle = roll_angle - 360
                # Calculate the dip
                dip = math.degrees(math.acos(x / math.sqrt((x ** 2) + (y ** 2) + (z ** 2)))) - 90
                # Create the new rad tool series
                new_rad_tool = RADTool().from_dict({'D': 'D5',
                                                    'gz': z,
                                                    'gx': x,
                                                    'gy': y,
                                                    'roll_angle': roll_angle,
                                                    'dip': dip,
                                                    'R': 'R3',
                                                    'angle_used': roll_angle - soa,
                                                    'rotated': True,
                                                    'rotation_type': 'acc'})
                print(f"Station {row.iloc[0].Station} roll angle: {roll_angle:.2f}")

            # Magnetometer rotation
            elif method == 'mag':
                if rad.D == 'D5':
                    x, y, z = rad.x, rad.y, rad.z
                else:
                    x, y, z = rad.Hx, rad.Hy, rad.Hz

                theta = math.atan2(-y, -z)
                cc_roll_angle = math.degrees(theta)
                roll_angle = 360 - cc_roll_angle if y < 0 else cc_roll_angle
                if roll_angle > 360:
                    roll_angle = roll_angle - 360
                dip = -90.  # The dip is assumed to be 90°
                new_rad_tool = RADTool().from_dict({'D': 'D5',
                                                    'Hz': z,
                                                    'Hx': x,
                                                    'Hy': y,
                                                    'roll_angle': roll_angle,
                                                    'dip': dip,
                                                    'R': 'R3',
                                                    'angle_used': roll_angle - soa,
                                                    'rotated': True,
                                                    'rotation_type': 'mag'})

            elif method == 'pp':
                assert self.has_loop_gps(), f"{self.filename} has no loop GPS."
                assert self.has_geometry(), f"{self.filename} has incomplete geometry."
                assert self.ramp > 0

                geometry = self.get_geometry()
                loop = self.get_loop(sorted=True, closed=True)
                mag_calc = MagneticFieldCalculator(loop)

            else:
                raise ValueError(f'"{method}" is an invalid rotation method')

            x_data.loc[:, 'Reading'] = x_data.loc[:, 'Reading'].map(lambda i: rotate_x(i, y_pair, roll_angle + soa))
            y_data.loc[:, 'Reading'] = y_data.loc[:, 'Reading'].map(lambda i: rotate_y(i, x_pair, roll_angle + soa))
            row = x_data.append(y_data)
            # Add the new rad tool series to the row
            row['RAD tool'] = row['RAD tool'].map(lambda p: new_rad_tool)
            return row

        # Create a filter for X and Y data only
        filt = (self.data.Component == 'X') | (self.data.Component == 'Y')
        st = time.time()
        rotated_data = self.data[filt].groupby(['Station', 'RAD ID'],
                                               as_index=False,
                                               group_keys=False).apply(lambda i: rotate_data(i, method))
        print(f"Time to rotate data: {time.time() - st}")
        self.data[filt] = rotated_data
        # Sort the data and remove unrotated readings
        self.data = sort_data(self.data.dropna(axis=0))
        self.probes['SOA'] = str(soa)
        return self


class PEMParser:
    """
    Class for parsing PEM files into PEM_File objects
    """

    # Constructor
    def __init__(self):

        #  'Tags' section
        self.re_tags = re.compile(  # Parsing the 'Tags' i.e. the information above the loop coordinates
            r'<FMT>\s(?P<Format>\d+)\s*~?.*[\r\n]'
            r'<UNI>\s(?P<Units>nanoTesla/sec|picoTesla)\s*~?.*[\r\n]'
            r'<OPR>\s(?P<Operator>.*)~?.*[\r\n]'
            r'<XYP>\s(?P<Probes>[\d\w\s-]*).*[\r\n]'
            r'<CUR>\s(?P<Current>\d+\.?\d?)\s*~?.*[\r\n]'
            r'<TXS>\s(?P<LoopSize>[\d\.\s]*).*[\r\n]',
            re.MULTILINE)

        # Tx loop coordinates section
        self.re_loop_coords = re.compile(
            r'(?P<LoopCoord><L.*>.*)')

        #  Line/Hole coordinates section
        self.re_line_coords = re.compile(
            r'(?P<LineCoord><P.*>.*)')

        # Notes i.e. GEN and HE tags
        self.re_notes = re.compile(  # Parsing the notes i.e. GEN tags and HE tags
            r'^(?P<Notes><GEN>.*|<HE\d>.*)',
            re.MULTILINE)
        #
        # # Header starting from 'Client' to before the channel times
        # self.re_header = re.compile(  # Parsing the header
        #     r'^(?:(<|~).*[\r\n]+)'
        #     r'(?P<Client>\w.*)[\r\n]'
        #     r'(?P<Grid>.*)[\r\n]'
        #     r'(?P<LineHole>.*)[\r\n]'
        #     r'(?P<Loop>.*)[\r\n]'
        #     r'(?P<Date>.*)[\r\n]'
        #     r'(?P<SurveyType>.*)\s(?P<Convention>Metric|Imperial)\s(?P<Sync>Crystal-Master|Crystal-Slave|Cable)\s(?P<Timebase>\d+\.?\d+)\s(?P<Ramp>\d+)\s(?P<NumChannels>\d+)\s(?P<NumReadings>\d+)[\r\n]'
        #     r'(?P<Receiver>#\d+)\s(?P<RxSoftwareVer>[\d.]+)\s(?P<RxSoftwareVerDate>[\w]+,[\w]+)\s(?P<RxFileName>[^\s]+)\s(?P<IsNormalized>[\w]+)\s(?P<PrimeFieldValue>\d+)\s(?P<CoilArea>-?\d+)\s(?P<LoopPolarity>-|\+)?[\n\r]+',
        #     re.MULTILINE)

        # Header starting from 'Client' to before the channel times
        self.re_header = re.compile(  # Parsing the header
            r'^(?:(<|~).*[\r\n]+)'
            r'(?P<Client>\w.*)[\r\n]'
            r'(?P<Grid>.*)[\r\n]'
            r'(?P<LineHole>.*)[\r\n]'
            r'(?P<Loop>.*)[\r\n]'
            r'(?P<Date>.*)[\r\n]'
            r'(?P<SurveyParameters>.+)[\r\n]'
            r'(?P<ReceiverParameters>.+)[\r\n]',
            re.MULTILINE)

        # Channel times
        self.re_channel_times = re.compile(
            r'[\r\n]{2}(?P<ChannelTimes>.*?)\$',
            re.DOTALL)

        # Data section
        self.re_data = re.compile(  # Parsing the EM data information
            r'^(?P<Station>^\d+[NSEW]?)\s(?P<Component>[XYZ])R(?P<ReadingIndex>\d+)(?:R.*?)?\s(?P<Gain>\d+)\s(?P<RxType>[AM\?])\s(?P<ZTS>\d+\.\d+)\s(?P<CoilDelay>\d+)\s(?P<NumStacks>\d+)\s(?P<ReadingsPerSet>\d+)\s(?P<ReadingNumber>\d+).*[\r\n]'
            r'^(?P<RADTool>D\d.*)[\r\n]'
            r'(?P<Data>[\W\deE]+[\n\r])',
            re.MULTILINE)

    def parse(self, filepath):
        """
        Parses a PEM file to extract all information and creates a PEMFile object out of it.
        :param filepath: string containing path to a PEM file
        :return: A PEM_File object representing the data found inside of filename
        """

        def parse_tags(file):
            cols = [
                'Format',
                'Units',
                'Operator',
                'Probes',
                'Current',
                'Loop dimensions'
            ]
            tags = {}
            matches = self.re_tags.findall(file)

            if not matches:
                raise ValueError('Error parsing the tags. No matches were found.')

            matches = matches[0]
            if len(cols) != len(matches):
                raise ValueError('Error in number of tags parsed')
            # XY probe  # , SOA, tool #, tool id
            for i, match in enumerate(matches):
                if cols[i] == 'Operator':
                    # Remove ~ from the operator name if it exists
                    match = match.split('~')[0].strip()
                elif cols[i] == 'Units':
                    if match == 'nanoTesla/sec':
                        match = 'nT/s'
                    elif match == 'picoTesla':
                        match = 'pT'
                elif cols[i] == 'Probes':
                    probe_cols = ['XY probe number', 'SOA', 'Tool number', 'Tool ID']
                    match = dict(zip(probe_cols, match.split()))
                elif cols[i] == 'Current':
                    match = float(match)
                elif cols[i] == 'Loop dimensions':
                    match = match.strip()
                tags[cols[i]] = match
            return tags

        def parse_loop(file):
            # Find all re matches
            matches = re.findall(self.re_loop_coords, file)
            if matches:
                return matches
            else:
                print(f"No loop coordinates found in {os.path.basename(filepath)}")

        def parse_line(file):
            # Find all re matches
            matches = re.findall(self.re_line_coords, file)
            if matches:
                return matches
            else:
                print(f"No line coordinates found in {os.path.basename(filepath)}")

        def parse_notes(file):
            notes = []
            for match in self.re_notes.finditer(file):
                for group, index in self.re_notes.groupindex.items():
                    notes.append(match.group(index))

            return notes

        def parse_header(file):

            header_cols = [
                'Client',
                'Grid',
                'Line',
                'Loop',
                'Date'
            ]

            survey_param_cols = [
                'Survey type',
                'Convention',
                'Sync',
                'Timebase',
                'Ramp',
                'Number of channels',
                'Number of readings'
            ]

            receiver_param_cols = [
                'Receiver number',
                'Rx software version',
                'Rx software version date',
                'Rx file name',
                'Normalized',
                'Primary field value',
                'Coil area',
                'Loop polarity'
            ]

            header = {}
            matches = self.re_header.search(file)

            if not matches:
                raise ValueError('Error parsing header. No matches were found.')

            matches = matches.groups()

            if len(matches) != 8:
                raise ValueError('Error parsing header. Not all matches were found')

            # Starting from index 1 to ignore the '~' match
            for i, match in enumerate(matches[1:6]):
                header[header_cols[i]] = match

            # Survey parameters
            survey_params = matches[6].split(' ')
            if not survey_params:
                raise ValueError('Error parsing survey parameters')

            for j, match in enumerate(survey_params):
                if survey_param_cols[j] in ['Timebase', 'Ramp']:
                    match = float(match)
                elif survey_param_cols[j] in ['Number of channels', 'Number of readings']:
                    match = int(match)
                header[survey_param_cols[j]] = match

            # Receiver parameters
            receiver_params = matches[7].split(' ')
            if not receiver_params:
                raise ValueError('Error parsing receiver parameters')

            for k, match in enumerate(receiver_params):
                if receiver_param_cols[k] in ['Primary field value', 'Coil area']:
                    match = int(match)
                header[receiver_param_cols[k]] = match

            return header

        def parse_channel_times(file, units=None):

            def channel_table(channel_times):
                """
                Channel times table data frame with channel start, end, center, width, and whether the channel is
                to be removed when the file is split
                :param channel_times: pandas Series: float of each channel time read from a PEM file header.
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

                # Configure which channels to remove for the first on-time
                table['Remove'] = table.apply(check_removable, axis=1)

                # Configure each channel after the last off-time channel (only for full waveform)
                last_off_time_channel = find_last_off_time()
                if last_off_time_channel:
                    table.loc[last_off_time_channel:, 'Remove'] = table.loc[last_off_time_channel:, 'Remove'].map(lambda x: True)
                return table

            t = time.time()
            matches = self.re_channel_times.search(file)
            print(f"Time to find channel time matches: {time.time() - t}")
            if not matches:
                raise ValueError('Error parsing channel times. No matches were found.')

            table = channel_table(np.array(matches.group(1).split(), dtype=float))
            return table

        def parse_data(file):

            cols = [
                'Station',
                'Component',
                'Reading index',
                'Gain',
                'Rx type',
                'ZTS',
                'Coil delay',
                'Number of stacks',
                'Readings per set',
                'Reading number',
                'RAD tool',
                'Reading'
            ]

            matches = self.re_data.findall(file)
            if not matches:
                raise ValueError('Error parsing header. No matches were found.')

            df = pd.DataFrame(matches, columns=cols)
            # Create a RAD tool ID number to be used for grouping up readings for probe rotation, since the CDR2
            # and CDR3 don't count reading numbers the same way.
            df['RAD tool'] = df['RAD tool'].map(lambda x: RADTool().from_match(x))
            df['RAD ID'] = df['RAD tool'].map(lambda x: x.id)
            df['Reading'] = df['Reading'].map(lambda x: np.array(x.split(), dtype=float))
            df[['Reading index',
                'Gain',
                'Coil delay',
                'Number of stacks',
                'Readings per set',
                'Reading number']] = df[['Reading index',
                                         'Gain',
                                         'Coil delay',
                                         'Number of stacks',
                                         'Readings per set',
                                         'Reading number']].astype(int)
            df['ZTS'] = df['ZTS'].astype(float)
            return df

        t = time.time()
        file = None
        with open(filepath, "rt") as in_file:
            file = in_file.read()

        t1 = time.time()
        tags = parse_tags(file)
        print(f"Time to parse tags: {time.time() - t1}")
        t2 = time.time()
        loop_coords = parse_loop(file)
        print(f"Time to parse loop: {time.time() - t2}")
        t3 = time.time()
        line_coords = parse_line(file)
        print(f"Time to parse line: {time.time() - t3}")
        t4 = time.time()
        notes = parse_notes(file)
        print(f"Time to parse notes: {time.time() - t4}")
        t5 = time.time()
        header = parse_header(file)
        print(f"Time to parse header: {time.time() - t5}")
        t6 = time.time()
        channel_table = parse_channel_times(file, units=tags.get('Units'))
        print(f"Time to parse channel table: {time.time() - t5}")
        t7 = time.time()
        data = parse_data(file)
        print(f"Time to parse data: {time.time() - t7}")

        print(f"Time to parse PEM file: {time.time() - t}")

        return PEMFile(tags, loop_coords, line_coords, notes, header, channel_table, data, filepath)


class PEMSerializer:
    """
    Class for serializing PEM files to be saved
    """

    def __init__(self):
        pass

    def serialize_tags(self, pem_file):
        result = ""
        xyp = ' '.join([pem_file.probes.get('XY probe number'),
                        pem_file.probes.get('SOA'),
                        pem_file.probes.get('Tool number'),
                        pem_file.probes.get('Tool ID')])
        result += f"<FMT> {pem_file.format}\n"
        result += f"<UNI> {'nanoTesla/sec' if pem_file.units == 'nT/s' else 'picoTesla'}\n"
        result += f"<OPR> {pem_file.operator}\n"
        result += f"<XYP> {xyp}\n"
        result += f"<CUR> {pem_file.current}\n"
        result += f"<TXS> {pem_file.loop_dimensions}"

        return result

    def serialize_loop_coords(self, pem_file):
        result = '~ Transmitter Loop Co-ordinates:'
        loop = pem_file.get_loop()
        if loop.empty:
            result += '\n<L00>\n''<L01>\n''<L02>\n''<L03>'
        else:
            loop.reset_index(inplace=True)
            for row in loop.itertuples():
                tag = f"<L{row.Index:02d}>"
                row = f"{tag} {row.Easting:.2f} {row.Northing:.2f} {row.Elevation:.2f} {row.Unit}"
                result += '\n' + row
        return result

    def serialize_line_coords(self, pem_file):

        def serialize_station_coords():
            result = '~ Hole/Profile Co-ordinates:'
            line = pem_file.get_line()
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
            collar = pem_file.get_collar()
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
            segs = pem_file.get_segments()
            if segs.empty:
                result += '\n<P01>\n''<P02>\n''<P03>\n''<P04>\n''<P05>'
            else:
                for row in segs.itertuples():
                    tag = f"<P{row.Index:02d}>"
                    row = f"{tag} {row.Azimuth:.2f} {row.Dip:.2f} {row[3]:.2f} {row.Unit} {row.Depth:.2f}"
                    result += '\n' + row
            return result

        if pem_file.is_borehole():
            return serialize_collar_coords() + \
                   serialize_segments()
        else:
            return serialize_station_coords()

    def serialize_notes(self, pem_file):
        results = []
        if not pem_file.notes:
            return ''
        else:
            for line in pem_file.notes:
                if line not in results:
                    results.append(line)
        return '\n'.join(results) + '\n'

    def serialize_header(self, pem_file):

        def get_channel_times(table):
            times = []
            # Add all the start times
            table.Start.map(times.append)
            # Add the first 'End' since it's the only value not repeated as a start
            times.insert(1, table.iloc[0].End)
            # Add the last end-time
            times.append(table.iloc[-1].End)
            return times

        result_list = [str(pem_file.client),
                       str(pem_file.grid),
                       str(pem_file.line_name),
                       str(pem_file.loop_name),
                       str(pem_file.date),
                       ' '.join([str(pem_file.survey_type),
                                 str(pem_file.convention),
                                 str(pem_file.sync),
                                 str(pem_file.timebase),
                                 str(int(pem_file.ramp)),
                                 str(pem_file.number_of_channels),
                                 str(pem_file.number_of_readings)]),
                       ' '.join([str(pem_file.rx_number),
                                 str(pem_file.rx_software_version),
                                 str(pem_file.rx_software_version_date),
                                 str(pem_file.rx_file_name),
                                 str(pem_file.normalized),
                                 str(pem_file.primary_field_value),
                                 str(pem_file.coil_area)])]

        if pem_file.loop_polarity is not None:
            result_list[-1] += ' ' + pem_file.loop_polarity

        result = '\n'.join(result_list) + '\n\n'

        times_per_line = 7
        cnt = 0

        times = get_channel_times(pem_file.channel_times)
        channel_times = [f'{time:9.6f}' for time in times]

        for i in range(0, len(channel_times), times_per_line):
            line_times = channel_times[i:i+times_per_line]
            result += ' '.join([str(time) for time in line_times]) + '\n'
            cnt += 1

        result += '$'
        return result

    def serialize_data(self, pem_file):
        df = pem_file.get_data(sorted=True)

        def serialize_reading(reading):
            result = ' '.join([reading['Station'],
                               reading['Component'] + 'R' + str(reading['Reading index']),
                               str(reading['Gain']),
                               reading['Rx type'],
                               str(reading['ZTS']),
                               str(reading['Coil delay']),
                               str(reading['Number of stacks']),
                               str(reading['Readings per set']),
                               str(reading['Reading number'])]) + '\n'
            rad = reading['RAD tool'].to_string()
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
        result = self.serialize_tags(pem_file) + '\n'
        result += self.serialize_loop_coords(pem_file) + '\n'
        result += self.serialize_line_coords(pem_file) + '\n'
        result += self.serialize_notes(pem_file)
        result += '~\n'
        result += self.serialize_header(pem_file) + '\n'
        result += self.serialize_data(pem_file)

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

            if self.R is not None and self.angle_used is not None:
                result.append(self.R)
                result.append(f"{self.angle_used:g}")

        elif self.D == 'D7':
            result = [
                self.D,
                f"{self.Hx:g}",
                f"{self.gx:g}",
                f"{self.Hy:g}",
                f"{self.gy:g}",
                f"{self.Hz:g}",
                f"{self.gz:g}",
                f"{self.T:g}"
            ]
        else:
            raise ValueError('RADTool D value is neither "D5" nor "D7"')

        return ' '.join(result)


if __name__ == '__main__':
    from src.pem.pem_getter import PEMGetter

    pg = PEMGetter()
    files = pg.get_pems(client='PEM Rotation', number=1)
    # files = pg.get_pems(client='Raglan', number=1)
    file = files[0]
    # p = PEMParser()
    # file = p.parse(file)
    # file.get_profile_data()

    # file.split()

    file.rotate(method='pp', soa=0)

    # file.average()
    # file.scale_current(10)
    out = str(Path(__file__).parent.parent.parent / 'sample_files' / 'test results'/f'{file.filename} - test rotation.pem')
    print(file.to_string(), file=open(out, 'w'))
    os.startfile(out)