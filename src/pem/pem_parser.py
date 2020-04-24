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
                elif cols[i] == 'Probes':
                    probe_cols = ['XY probe number', 'SOA', 'Tool number', 'Tool ID']
                    match = dict(zip(probe_cols, match.split()))
                elif cols[i] == 'Current':
                    match = float(match)
                tags[cols[i]] = match
            return tags

        def parse_loop(file):
            # Columns for the data frame
            cols = ['Easting', 'Northing', 'Elevation', 'Unit']
            # Find all re matches
            matches = re.findall(self.re_loop_coords, file)
            # Split the matches up into individual items of a list, ignoring the tags.
            loop_gps = [match.split()[1:5] for match in matches]
            # Create a pandas data frame from the split matches if any are found. Otherwise return None
            if any(loop_gps):
                loop_df = pd.DataFrame(loop_gps, columns=cols, dtype=float)
                loop_df = loop_df.astype({'Unit': str})
                return loop_df
            else:
                print(f"No loop coordinates found in {os.path.basename(filepath)}")
                return None

        def parse_line(file):
            # Columns for the data frame
            cols = ['Easting', 'Northing', 'Elevation', 'Unit', 'Station']
            # Find all re matches
            matches = re.findall(self.re_line_coords, file)
            # Split the matches up into individual items of a list
            line_gps = [match.split()[1:6] for match in matches]
            if any(line_gps):
                # Create a pandas data frame from the split matches
                line_df = pd.DataFrame(line_gps, columns=cols)
                line_df.loc[:, 'Easting':'Northing'] = line_df.loc[:, 'Easting':'Northing'].astype(float)
                line_df[['Unit', 'Station']] = line_df[['Unit', 'Station']].astype(str)
                return line_df
            else:
                print(f"No line coordinates found in {os.path.basename(filepath)}")
                return None

        def parse_notes(file):
            notes = []
            for match in self.re_notes.finditer(file):
                for group, index in self.re_notes.groupindex.items():
                    notes.append(match.group(index))

            return notes

        def parse_header(file):
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
                'Channel times table'
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
                elif cols[i] == 'Channel times table':
                    match = pd.Series(match.split(), dtype=float)

                header[cols[i]] = match

            return header

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

            # Split the values in the RAD tool and Reading columns to lists
            for i, match in enumerate(matches):
                match = list(match)
                rad_tool = match[-2].split()
                reading = match[-1].split()
                match[-2] = np.array(rad_tool)
                # match[-1] = np.array(reading, dtype=float)
                match[-1] = pd.DataFrame(reading, columns=['Value'], dtype=float)
                matches[i] = match

            df = pd.DataFrame(matches, columns=cols)
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
            df = pd.DataFrame(matches, columns=cols)
            return df

        file = None
        with open(filepath, "rt") as in_file:
            file = in_file.read()

        tags = parse_tags(file)
        loop_coords = parse_loop(file)
        line_coords = parse_line(file)
        notes = parse_notes(file)
        header = parse_header(file)
        data = parse_data(file)

        return PEMFile(tags, loop_coords, line_coords, notes, header, data, filepath)


if __name__ == '__main__':
    file = r'C:\Users\Mortulo\PycharmProjects\PEMPro\sample_files\7600N.PEM'
    p = PEMParser()
    file = p.parse(file)
    print(file.get_crs())