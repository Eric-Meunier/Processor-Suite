import re
import os
import pandas as pd
import numpy as np
from decimal import Decimal
from src.pem.pem_file import PEMFile


class PEMParser:
    """
    Class for parsing PEM files into PEM_File objects
    """

    # Constructor
    def __init__(self):

        #  'Tags' section
        self.re_tags = re.compile(  # Parsing the 'Tags' i.e. the information above the loop coordinates
            r'<FMT>\s(?P<Format>\d+)\s*~?.*[\r\n]'
            r'<UNI>\s(?P<Units>nanoTesla\/sec|picoTesla)\s*~?.*[\r\n]'
            r'<OPR>\s(?P<Operator>.*)~?.*[\r\n]'
            r'<XYP>\s(?P<Probes>[\d\w\s-]*).*[\r\n]'
            r'<CUR>\s(?P<Current>\d+\.?\d?)\s*~?.*[\r\n]'
            r'<TXS>\s(?P<LoopSize>[\d\.\s]*).*[\r\n]',
            re.MULTILINE
        )

        # Tx loop coordinates section
        self.re_loop_coords = re.compile(
            r'(?P<LoopCoord><L.*>.*)')

        #  Line/Hole coordinates section
        self.re_line_coords = re.compile(
            r'(?P<LineCoord><P.*>.*)')

        # Notes i.e. GEN and HE tags
        self.re_notes = re.compile(  # Parsing the notes i.e. GEN tags and HE tags
            r'^(?P<Notes><GEN>.*|<HE\d>.*)',
            re.MULTILINE
        )

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
                    elif match == 'picoTesla':
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
            # Split the matches up into individual items of a list, ignoring the tags.
            loop_gps = '\n'.join([' '.join(match.split()[1:5]) for match in matches])
            if any(loop_gps):
                return loop_gps
            else:
                print(f"No loop coordinates found in {os.path.basename(filepath)}")
                return None

        def parse_line(file):
            # Find all re matches
            matches = re.findall(self.re_line_coords, file)
            # Split the matches up into individual items of a list
            line_gps = '\n'.join([' '.join(match.split()[1:6]) for match in matches])
            if any(line_gps):
                return line_gps
            else:
                print(f"No line coordinates found in {os.path.basename(filepath)}")
                return None

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
                    table.loc[last_off_time_channel:, 'Remove'] = table.loc[52:, 'Remove'].map(lambda x: True)
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
    file.rotate(type='mag', soa=-5)
    file.average()
    out = r'C:\Users\Mortulo\PycharmProjects\PEMPro\sample_files\PEM Rotation\test.PEM'
    print(file.get_serialized_file(), file=open(out, 'w'))