import re
from decimal import Decimal
from src.pem.pem_file import PEMFile


class PEMParser:
    """
    Class for parsing PEM files into PEM_File objects
    """

    # Constructor
    def __init__(self):
        # Compile necessary Regex objects once

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

        ## Tx loop coordinates section
        self.re_loop_coords = re.compile(
            r'(?P<LoopCoord><L.*>.*)')

        #  Line/Hole coordinates section
        self.re_line_coords = re.compile(
            r'(?P<LineCoord><P.*>.*)')

        # Notes i.e. GEN and HE tags
        self.re_notes = re.compile(  # Parsing the notes i.e. GEN tags and HE tags
            r'(?P<Notes><GEN>.*|<HE\d>.*)',
            re.MULTILINE
        )

        # Header starting from 'Client' to the channel start-end times
        self.re_header = re.compile(  # Parsing the header
            r'(^(<|~).*[\r\n]+)'
            r'(?P<Client>\w.*)[\r\n]'
            r'(?P<Grid>.*)[\r\n]'
            r'(?P<LineHole>.*)[\r\n]'
            r'(?P<Loop>.*)[\r\n]'
            r'(?P<Date>.*)[\r\n]'
            r'^(?P<SurveyType>.*)\s(?P<Convension>Metric|Imperial)\s(?P<Sync>Crystal-Master|Crystal-Slave|Cable)\s(?P<Timebase>\d+\.?\d+)\s(?P<Ramp>\d+)\s(?P<NumChannels>\d+)\s(?P<NumReadings>\d+)[\r\n]'
            r'^(?P<Receiver>#\d+)\s(?P<RxSoftwareVer>[\d.]+)\s(?P<RxSoftwareVerDate>[\w]+,[\w]+)\s(?P<RxFileName>[^\s]+)\s(?P<IsNormalized>[\w]+)\s(?P<PrimeFieldValue>\d+)\s(?P<CoilArea>-?\d+)\s(?P<LoopPolarity>-|\+)?[\n\r]+'
            r'(?P<ChannelTimes>[\W\w]+)[\r\n]\$',
            re.MULTILINE)

        # Data section
        self.re_data = re.compile(  # Parsing the EM data information
            r'^(?P<Station>^\d+[NSEW]?)\s(?P<Component>[XYZ])R(?P<ReadingIndex>\d+)\s(?P<Gain>\d)\s(?P<RxType>[AM\?])\s(?P<ZTS>\d+\.\d+)\s(?P<CoilDelay>\d+)\s(?P<NumStacks>\d+)\s(?P<ReadingsPerSet>\d+)\s(?P<ReadingNumber>\d+).*[\r\n]'
            r'^(?P<RADTool>D\d.*)[\r\n]'
            r'(?P<Data>[\W\de]+[\n\r])',
            re.MULTILINE)

    def parse_tags(self, file):
        tags = {}
        for match in self.re_tags.finditer(file):
            # Iterate through each group name such as 'Format' or 'Unit' in the regex
            for group, index in self.re_tags.groupindex.items():
                tags[group] = match.group(index).strip()

        return tags

    def parse_loop(self, file):
        loop_gps = re.findall(self.re_loop_coords, file)
        return loop_gps

    def parse_line(self, file):
        line_gps = re.findall(self.re_line_coords, file)
        return line_gps

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
                if group is not 'ChannelTimes':
                    header[group] = match.group(index)
            header['ChannelTimes'] = ([Decimal(x) for x in match.group('ChannelTimes').split()])

        return header

    def parse_data(self, file):
        survey_data = []

        for match in self.re_data.finditer(file):  # Each reading is a dictionary
            reading = {}

            for group, index in self.re_data.groupindex.items():
                if group == 'Data':
                    reading[group] = ([Decimal(x) for x in match.group(index).split()])

                else:
                    reading[group] = match.group(index)

            survey_data.append(reading)

        return survey_data

    def get_components(self, data):
        unique_components = []

        for reading in data:
            component = reading['Component']

            if component not in unique_components:
                unique_components.append(component)

        if 'Z' in unique_components:
            unique_components.insert(0, unique_components.pop(unique_components.index('Z')))

        return unique_components

    def survey_type(self, header):
        survey_type = header['SurveyType']

        if survey_type.casefold() == 's-coil':
            survey_type = 'Surface Induction'
        elif survey_type.casefold() == 'borehole':
            survey_type = 'Borehole Induction'
        elif survey_type.casefold() == 'b-rad':
            survey_type = 'Borehole Induction'
        elif survey_type.casefold() == 's-flux':
            survey_type = 'Surface Fluxgate'
        elif survey_type.casefold() == 'bh-flux':
            survey_type = 'Borehole Fluxgate'
        elif survey_type.casefold() == 's-squid':
            survey_type = 'SQUID'
        else:
            survey_type = 'UNDEF_SURV'

        return survey_type

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
        components = self.get_components(data)
        survey_type = self.survey_type(header)
        filepath = filename

        return PEMFile(tags, loop_coords, line_coords, notes, header, data, components, survey_type, filepath)
