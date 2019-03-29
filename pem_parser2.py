import re
from decimal import Decimal


class PEMFile:
    """
    Class for storing PEM file data for easy access
    """

    # Constructor
    def __init__(self, tags, loop_coords, line_coords, notes, header, data):
        self.tags = tags
        self.loop_coords = loop_coords
        self.line_coords = line_coords
        self.notes = notes
        self.header = header
        self.data = data

    def get_tags(self):
        return self.tags

    def get_loop_coords(self):
        return self.loop_coords

    def get_line_coords(self):
        return self.line_coords()

    def get_notes(self):
        return self.notes

    def get_header(self):
        return self.header

    def get_data(self):
        return self.data


class PEMParser:
    """
    Class for parsing PEM files into PEM_File objects
    """

    # Constructor
    def __init__(self):
        # Compile necessary Regex objects once

        #  'Tags' section
        self.re_tags = re.compile(  # Parsing the 'Tags' i.e. the information above the loop coordinates
            r'<FMT>\s(?P<Format>.*)[\r\n]'
            r'<UNI>\s(?P<Units>.*)[\r\n]'
            r'<OPR>\s(?P<Operator>.*)[\r\n]'
            r'<XYP>\s(?P<XYProbe>\d*)\s(?P<SOA>\d*)\s(?P<Tool>\d*)\s(?P<ToolID>\d*)[\r\n]'
            r'<CUR>\s(?P<Current>.*)[\r\n]'
            r'<TXS>\s(?P<LoopSize>.*)',
            re.MULTILINE
        )

        #  Tx loop coordinates section
        self.re_loop_coords = re.compile(  # Parsing the loop coordinates
            r'(?P<LoopCoordinates><L\d*>.*[\r\n])',
            re.MULTILINE
        )

        #  Line/Hole coordinates section
        self.re_line_coords = re.compile(  # Parsing the line/hole coordinates
            r'(?P<LineCoordinates><P\d*>.*[\r\n])',
            re.MULTILINE
        )

        self.re_notes = re.compile(  # Parsing the notes i.e. GEN tags and HE tags
            r'(?P<Notes><GEN>.*|<HE\d>.*)',
            re.MULTILINE
        )

        self.re_header = re.compile(  # Parsing the header
            r'(^(<|~).*[\r\n])'
            r'(?P<Client>\w.*)[\r\n]'
            r'(?P<Grid>.*)[\r\n]'
            r'(?P<LineHole>.*)[\r\n]'
            r'(?P<Loop>.*)[\r\n]'
            r'(?P<Date>.*)[\r\n]'
            r'^(?P<SurveyType>.*)\s(Metric|Imperial)\s(Crystal-(Master|Slave)|(Cable))\s(?P<Timebase>\d+\.?\d+)\s(?P<Ramp>\d+)\s(?P<NumChannels>\d+)\s(?P<NumReadings>\d+)[\r\n]'
            r'^(?P<Receiver>#\d+)\s(?P<RxSoftwareVer>\d+\.?\d?\d?)\s(?P<RxSoftwareVerDate>.*,\d+.*)\s(?P<RxFileName>.*)\s(N|Y)\s(?P<PrimeFieldValue>\d+)\s(?P<CoilArea>\d+).*[\n\r]'
            r'[\r\n](?P<ChannelTimes>[\W\d]+)[\r\n]\$',
            re.MULTILINE)


        self.re_data = re.compile(  # Parsing the EM data information
            r'^(?P<Station>^\d+[NSEW]?)\s(?P<Component>[XYZ])R(?P<ReadingIndex>\d+)\s(?P<Gain>\d)\s(?P<RxType>[AM\?])\s(?P<ZTS>\d+\.\d+)\s(?P<CoilDelay>\d+)\s(?P<NumStacks>\d+)\s(?P<ReadingsPerSet>\d)\s(?P<ReadingNumber>\d+)[\r\n]'
            r'^(?P<RADTool>D\d.*)[\r\n]'
            r'(?P<Data>[\W\d]+[\n\r])',
            re.MULTILINE)

    def parse_tags(self, file):
        tags = {}
        for match in self.re_tags.finditer(file):
            # Iterate through each group name such as 'Format' or 'Unit' in the regex
            for group, index in self.re_tags.groupindex.items():
                tags[group] = match.group(index).strip()

        return tags

    def parse_loop(self, file):
        loop_coords = []
        for match in self.re_loop_coords.finditer(file):
            for group, index in self.re_loop_coords.groupindex.items():
                loop_coords.append(match.group(index))
        return loop_coords

    def parse_line(self, file):
        line_coords = []
        for match in self.re_loop_coords.finditer(file):
            for group, index in self.re_loop_coords.groupindex.items():
                line_coords.append(match.group(index))
        return line_coords

    def parse_notes(self, file):
        notes = []
        for match in self.re_notes.finditer(file):
                for group, index in self.re_notes.groupindex.items():
                    notes.append(match.group(index))
        return notes

    def parse_header(self, file):
        header = {}
        for match in self.re_header.finditer(file):
            for group, index in self.re_header.groupindex.items():
                # pprint.pprint(group)
                if group is not 'ChannelTimes':
                    header[group] = match.group(index)
            header['ChannelTimes']=([Decimal(x) for x in match.group('ChannelTimes').split()])
        return header

    def parse_data(self, file):
        survey_data = []
        data = {}
        for match in self.re_data.finditer(file):
            for group, index in self.re_data.groupindex.items():
                if group is not 'Data':
                    data[group] = match.group(index)
            data['Data'] = ([Decimal(x) for x in match.group('Data').split()])
            survey_data.append(data)
            # pprint.pprint(data)
    # pprint.pprint(survey_data)
        return survey_data

    def parse(self, filename):
        """
        :param filename: string containing path to a PEM file
        :return: A PEM_File object representing the data found inside of filename
        """
        file = None
        with open(filename, "rt") as in_file:
            file = in_file.read()

        tags = self.parse_tags(file)
        loop_coords = self.parse_loop(file)
        line_coords = self.parse_line(file)
        notes = self.parse_notes(file)
        header = self.parse_header(file)
        data = self.parse_data(file)

        return PEMFile(tags, loop_coords, line_coords, notes, header, data)
