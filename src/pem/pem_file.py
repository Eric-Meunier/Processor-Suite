import math
import os
import re
import time

import natsort
import numpy as np
import pandas as pd

from src.gps.gps_editor import TransmitterLoop, SurveyLine, BoreholeCollar, BoreholeSegments, BoreholeGeometry
from src.pem.pem_serializer import PEMSerializer


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
    def __init__(self, tags, loop_coords, line_coords, notes, header, data, filepath=None):
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
        self.channel_times = header.get('Channel times')

        self.loop = TransmitterLoop(loop_coords, name=self.loop_name)
        if self.is_borehole():
            collar = BoreholeCollar(line_coords, name=self.line_name)
            segments = BoreholeSegments(line_coords, name=self.line_name)
            self.geometry = BoreholeGeometry(collar, segments, name=self.line_name)
        else:
            self.line = SurveyLine(line_coords, name=self.line_name)
        self.notes = notes
        self.data = data
        self.filepath = filepath
        self.filename = os.path.basename(filepath)

        self.unsplit_data = None
        self.unaveraged_data = None
        self.old_filepath = None

    def is_borehole(self):
        if 'borehole' in self.get_survey_type().lower():
            return True
        else:
            return False

    def is_rotated(self):
        return self.data['RAD tool'].map(lambda x: x.Rotated).all()

    def is_averaged(self):
        data = self.data[['Station', 'Component']]
        if any(data.duplicated()):
            return False
        else:
            return True

    def is_split(self):
        ct = self.channel_times
        if len(ct[ct < 0]) == 2:
            return True
        else:
            return False

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
                zone = int(s[2])
                north = True if s[3][:-1] == 'North' else False
                datum = f"{s[4]} {s[5]}"
                print(f"CRS is {system} Zone {zone} {'North' if north else 'South'}, {datum}")
                return {'System': system, 'Zone': zone, 'North': north, 'Datum': datum}
        return None

    def get_loop(self, sorted=True, closed=False, crs=None):
        return self.loop.get_loop(sorted=sorted, closed=closed, crs=crs)

    def get_line(self, sorted=True, crs=None):
        return self.line.get_line(sorted=sorted, crs=crs)

    def get_collar(self, crs=None):
        return self.geometry.get_collar(crs=crs)

    def get_segments(self):
        return self.geometry.get_segments()

    def get_notes(self):
        return self.notes

    def get_data(self, sorted=True):
        if sorted:
            data = sort_data(self.data)
        else:
            data = self.data
        return data

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

    def get_profile_data(self):
        """
        Transforms the data from the PEM file in profile
        :return: Dictionary where each key is a channel, and the values of those keys are a list of
        dictionaries which contain the stations and readings of all readings of that channel. Each component has
        such a dictionary.
        """

        components = self.get_components()
        profile_data = {}

        for component in components:
            component_profile_data = {}
            component_data = [station for station in self.data if station['Component'] == component]
            num_channels = len(component_data[0]['Data'])

            for channel in range(0, num_channels):
                channel_data = []

                for i, station in enumerate(component_data):
                    reading = station['Data'][channel]
                    station_number = int(convert_station(station['Station']))
                    channel_data.append({'Station': station_number, 'Reading': reading})

                component_profile_data[channel] = channel_data

            profile_data[component] = component_profile_data

        return profile_data

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

    def get_serialized_file(self):
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
            # Create a new data frame
            new_data_df = pd.DataFrame(columns=group.columns)
            # Fill the new data frame with the last row of the group
            new_data_df = new_data_df.append(group.iloc[-1])
            # Sum the number of stacks column
            new_data_df['Number of stacks'] = group['Number of stacks'].sum()
            # Add the weighted average of the readings to the reading column
            new_data_df['Reading'] = [np.average(group.Reading.to_list(),
                                                 axis=0,
                                                 weights=group['Number of stacks'].to_list())]
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

        def remove_on_time(readings, channel_times):
            """
            Remove the on-time channels using the channel times table from the PEM file
            :param readings: np.array of values for a given reading
            :param channel_times: pandas DataFrame from the PEM file
            :return: np.array with only select channels remaining
            """
            return readings[~channel_times.Remove]  # Only keep the "True" values from the mask

        # Only keep the select channels from each reading
        self.data.Reading = self.data.Reading.map(lambda x: remove_on_time(x, self.channel_times))
        # Create a filter and update the channels table
        filt = self.channel_times.Remove == False
        self.channel_times = self.channel_times[filt]
        # Update the PEM file's number of channels attribute
        self.number_of_channels = len(self.channel_times.index)
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

    def rotate(self, type='acc', soa=0):
        """
        Rotate the XY data of the PEM file.
        Formula: X' = Xcos(roll) - Ysin(roll), Y' = Xsin(roll) + Ycos(roll)
        :param type: str: Method of rotation, either 'acc' for accelerometer or 'mag' for magnetic
        :param soa: int: Sensor offset angle
        :return: PEM file object with rotated data
        """
        if self.is_rotated():
            print(f"{self.filename} is already rotated.")
            return
        elif not self.is_borehole():
            print(f"{self.filename} is not a borehole file.")
            return
        elif self.data['RAD tool'].map(lambda x: x.D == 'D5').any():
            print(f"{self.filename} appears to be a file that has been run through Otool, thus it will not be rotated.")
            return
        else:
            def rotate_data(row, type):
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

                assert len(np.unique(row['RAD tool'].map(lambda x: x.to_list()))) == 1, 'More than 1 unique RAD tool set'
                print(f"Number of unique RAD tool sets: {len(np.unique(row['RAD tool'].map(lambda x: x.to_list())))}")

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
                if type == 'acc':
                    theta = math.atan2(rad.gy, rad.gz)
                    cc_roll_angle = 360 - math.degrees(theta) if rad.gy < 0 else math.degrees(theta)
                    roll_angle = 360 - cc_roll_angle if rad.gy > 0 else cc_roll_angle
                    if roll_angle >= 360:
                        roll_angle = roll_angle - 360
                    # Calculate the dip
                    dip = math.degrees(math.acos(rad.gx/math.sqrt((rad.gx ** 2) + (rad.gy ** 2) + (rad.gz ** 2)))) - 90
                    # Create the new rad tool series
                    new_rad_tool = pd.Series({'D': 'D5',
                                              'gz': rad.gz,
                                              'gx': rad.gx,
                                              'gy': rad.gy,
                                              'Roll angle': roll_angle,
                                              'Dip': dip,
                                              'R': 'R3',
                                              'Roll angle SOA': roll_angle - soa,
                                              'Rotated': True})
                    print(f"Station {row.iloc[0].Station} roll angle: {roll_angle:.2f}")

                # Magnetometer rotation
                elif type == 'mag':
                    theta = math.atan2(-rad.Hy, -rad.Hz)
                    cc_roll_angle = math.degrees(theta)
                    roll_angle = 360 - cc_roll_angle if rad.Hy < 0 else cc_roll_angle
                    if roll_angle > 360:
                        roll_angle = roll_angle - 360
                    dip = -90.  # The dip is assumed to be 90°
                    new_rad_tool = pd.Series({'D': 'D5',
                                              'Hz': rad.Hz,
                                              'Hx': rad.Hx,
                                              'Hy': rad.Hy,
                                              'Roll angle': roll_angle,
                                              'Dip': dip,
                                              'R': 'R3',
                                              'Roll angle SOA': roll_angle - soa,
                                              'Rotated': True})
                else:
                    raise ValueError(f'"{type}" is an invalid rotation method')

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
                                                   group_keys=False).apply(lambda i: rotate_data(i, type))
            print(time.time() - st)
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
            r'<UNI>\s(?P<Units>nanoTesla/sec|picoTeslas)\s*~?.*[\r\n]'
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

        # Header starting from 'Client' to the channel start-end times
        self.re_header = re.compile(  # Parsing the header
            r'^(?:(<|~).*[\r\n]+)'
            r'(?P<Client>\w.*)[\r\n]'
            r'(?P<Grid>.*)[\r\n]'
            r'(?P<LineHole>.*)[\r\n]'
            r'(?P<Loop>.*)[\r\n]'
            r'(?P<Date>.*)[\r\n]'
            r'(?P<SurveyType>.*)\s(?P<Convention>Metric|Imperial)\s(?P<Sync>Crystal-Master|Crystal-Slave|Cable)\s(?P<Timebase>\d+\.?\d+)\s(?P<Ramp>\d+)\s(?P<NumChannels>\d+)\s(?P<NumReadings>\d+)[\r\n]'
            r'(?P<Receiver>#\d+)\s(?P<RxSoftwareVer>[\d.]+)\s(?P<RxSoftwareVerDate>[\w]+,[\w]+)\s(?P<RxFileName>[^\s]+)\s(?P<IsNormalized>[\w]+)\s(?P<PrimeFieldValue>\d+)\s(?P<CoilArea>-?\d+)\s(?P<LoopPolarity>-|\+)?[\n\r]+'
            r'(?P<ChannelTimes>[\W\w]+)[\r\n]\$',
            re.MULTILINE)

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
                    match.split('~')[0].split()[0]
                elif cols[i] == 'Units':
                    if match == 'nanoTesla/sec':
                        match = 'nT/s'
                    elif match == 'picoTeslas':
                        match = 'pT'
                elif cols[i] == 'Probes':
                    probe_cols = ['XY probe number', 'SOA', 'Tool number', 'Tool ID']
                    match = dict(zip(probe_cols, match.split()))
                elif cols[i] == 'Current':
                    match = float(match)
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

        def parse_header(file, units=None):

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

            cols = [
                'Client',
                'Grid',
                'Line',
                'Loop',
                'Date',
                'Survey type',
                'Convention',
                'Sync',
                'Timebase',
                'Ramp',
                'Number of channels',
                'Number of readings',
                'Receiver number',
                'Rx software version',
                'Rx software version date',
                'Rx file name',
                'Normalized',
                'Primary field value',
                'Coil area',
                'Loop polarity',
                'Channel times'
            ]
            header = {}
            matches = self.re_header.findall(file)

            if not matches:
                raise ValueError('Error parsing header. No matches were found.')

            matches = matches[0]

            if len(matches) - 1 != len(cols):
                raise ValueError('Error parsing header. Not all matches were found')

            # Starting from index 1 to ignore the '~' match
            for i, match in enumerate(matches[1:]):
                if cols[i] in ['Timebase', 'Ramp']:
                    match = float(match)
                elif cols[i] in ['Number of channels', 'Number of readings', 'Primary field value', 'Coil area']:
                    match = int(match)
                elif cols[i] == 'Channel times':
                    match = channel_table(pd.Series(match.split(), dtype=float))

                header[cols[i]] = match

            return header

        def parse_data(file):

            def rad_to_series(match):
                """
                Create a pandas Series from the RAD tool data
                :param match: str: re match of the rad tool section
                :return: pandas Series
                """
                match = match.split()
                if match[0] == 'D7':
                    index = [
                        'D',
                        'Hx',
                        'gx',
                        'Hy',
                        'gy',
                        'Hz',
                        'gz',
                        'T'
                    ]
                    series = pd.Series(match, index=index)
                    series[1:] = series[1:].astype(float)
                    series['Rotated'] = False
                    return series

                elif match[0] == 'D5':
                    if len(match) == 6:
                        index = [
                            'D',
                            'x',
                            'y',
                            'z',
                            'roll angle',
                            'dip',
                        ]
                        series = pd.Series(match, index=index)
                        series[1:] = series[1:].astype(float)
                        series['Rotated'] = False
                        return series

                    elif len(match) == 8:
                        index = [
                            'D',
                            'x',
                            'y',
                            'z',
                            'roll angle',
                            'dip',
                            'R',
                            'roll angle used'
                        ]
                        series = pd.Series(match, index=index)
                        series[1:5] = series[1:5].astype(float)
                        series[-1:] = series[-1:].astype(float)
                        series['Rotated'] = True
                        return series

                    else:
                        raise ValueError('Error in the number of the RAD tool values')
                else:
                    raise ValueError('Error in D value of RAD tool line. D value is neither D5 nor D7.')

            def get_rad_id(match):
                return ''.join(match.split())

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
            df['RAD ID'] = df['RAD tool'].map(get_rad_id)
            df['RAD tool'] = df['RAD tool'].map(rad_to_series)
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

        file = None
        with open(filepath, "rt") as in_file:
            file = in_file.read()

        tags = parse_tags(file)
        loop_coords = parse_loop(file)
        line_coords = parse_line(file)
        notes = parse_notes(file)
        header = parse_header(file, units=tags.get('Units'))
        data = parse_data(file)

        return PEMFile(tags, loop_coords, line_coords, notes, header, data, filepath)


if __name__ == '__main__':
    # file = r'C:\Users\Mortulo\PycharmProjects\PEMPro\sample_files\7600N.PEM'
    # file = r'C:\Users\Mortulo\PycharmProjects\PEMPro\sample_files\PEMGetter files\Nantou\PUX-021 ZAv.PEM'
    # file = r'C:\Users\Mortulo\PycharmProjects\PEMPro\sample_files\L1000N_29.PEM'
    # file = r'C:\Users\Mortulo\PycharmProjects\PEMPro\sample_files\PEM Rotation\BX-081 XY.PEM'
    # file = r'C:\Users\Mortulo\PycharmProjects\PEMPro\sample_files\PEM Rotation\MRC-067 XY.PEM'
    # file = r'C:\Users\Mortulo\PycharmProjects\PEMPro\sample_files\PEM Rotation\BX-081 XYT.PEM'
    # file = r'C:\Users\Mortulo\PycharmProjects\PEMPro\sample_files\PEM Rotation\MX-198 XY.PEM'
    # file = r'C:\Users\Mortulo\PycharmProjects\PEMPro\sample_files\PEM Rotation\SAN-225G-18 CXYZ (flux).PEM'
    file = r'C:\Users\Mortulo\PycharmProjects\PEMPro\sample_files\PEM Rotation\PU-340 XY.PEM'
    # file = r'C:\Users\Mortulo\PycharmProjects\PEMPro\sample_files\PEM Rotation\SAN-237-19 XYZ (flux).PEM'
    p = PEMParser()
    file = p.parse(file)
    file.split()
    file.rotate(type='acc', soa=0)
    # file.average()
    file.scale_current(10)
    out = r'C:\Users\Mortulo\PycharmProjects\PEMPro\sample_files\PEM Rotation\test.PEM'
    print(file.get_serialized_file(), file=open(out, 'w'))
    os.startfile(out)