import re
import pprint
# from decimal import Decimal


class PEMParser:
    """
    Class for parsing PEM files into PEM_File objects
    """

    # Constructor
    def __init__(self):
        # Compile necessary Regex objects once

        #  'Tags' section
        self.re_tags = re.compile(
            r'<FMT>\s(?P<Format>.*)[\r\n]'
            r'<UNI>\s(?P<Units>.*)[\r\n]'
            r'<OPR>\s(?P<Operator>.*)[\r\n]'
            r'<XYP>\s(?P<XYProbe>\d*)\s(?P<SOA>\d*)\s(?P<Tool>\d*)\s(?P<ToolID>\d*)[\r\n]'
            r'<CUR>\s(?P<Current>.*)[\r\n]'
            r'<TXS>\s(?P<LoopSize>.*)',
            re.MULTILINE
        )

        #  Tx loop coordinates section
        self.re_loop_coords = re.compile(
            r'(?P<LoopCoordinates><L\d*>.*[\r\n])',
            re.MULTILINE
        )

        #  Line/Hole coordinates section
        self.re_line_coords = re.compile(
            r'(?P<line_coordinates><P\d*>.*[\r\n])',
            re.MULTILINE
        )

        self.re_notes = re.compile(
            r'(?P<Notes><GEN>.*|<HE\d>.*)',
            re.MULTILINE
        )

        self.re_header = re.compile(
            r'(^(<|~).*[\r\n])+'
            r'(?P<Client>\w.*)[\r\n]'
            r'(?P<Grid>.*)[\r\n]'
            r'(?P<LineHole>.*)[\r\n]'
            r'(?P<Loop>.*)[\r\n]'
            r'(?P<Date>.*)[\r\n]'
            r'^(?P<SurveyType>.*)\s(Metric|Imperial)\sCrystal-(Master|Slave)\s(?P<Timebase>\d+\.?\d+)\s(?P<Ramp>\d+)\s(?P<NumChannels>\d+)\s(?P<NumReadings>\d+)[\r\n]'
            r'^(?P<Receiver>#\d+)\s(?P<RxSoftwareVer>\d+\.?\d?\d?)\s(?P<RxSoftwareVerDate>.*,\d+.*)\s(?P<RxFileName>.*)\s(N|Y)\s(?P<PrimeFieldValue>\d+)\s(?P<CoilArea>\d+).*[\n\r]'
            r'[\r\n](?P<ChannelTimes>[\W\d]+)[\r\n]\$',
            re.MULTILINE)

        # # TODO Add RAD Tool group
        # self.re_data = re.compile(  # Parsing the EM data information
        #     r'(?P<Station>^\d+)\s(?P<Component>[a-zA-Z])R(?P<ReadingIndex>\d+).*[\r\n]'
        #     r'(?:D\d.+[\n\r])'
        #     r'(?P<Data>[\W\d]+[\n\r])',
        #     re.MULTILINE)

    def parse_tags(self, file):
        with open(file) as f:
            file=f.read()
            result = {}
            loop_coords = []
            line_coords = []
            notes=[]
            header = {}

            for match in self.re_tags.finditer(file):
                # Iterate through each group name such as 'Format' or 'Unit' in the regex
                for group, index in self.re_tags.groupindex.items():
                    result[group] = match.group(index).strip()

            for match in self.re_loop_coords.finditer(file):
                    for group, index in self.re_loop_coords.groupindex.items():
                        loop_coords.append(match.group(index))
                    result[group]=loop_coords

            for match in self.re_line_coords.finditer(file):
                    for group, index in self.re_line_coords.groupindex.items():
                        line_coords.append(match.group(index))
                    result[group]=line_coords

            for match in self.re_notes.finditer(file):
                    for group, index in self.re_notes.groupindex.items():
                        notes.append(match.group(index))
                    result[group]=notes

            for match in self.re_header.finditer(file):
                for group, index in self.re_header.groupindex.items():
                    # notes.append(match.group(index))
                    header[group] = match.group(index)
                pprint.pprint(header)

            return result


z = PEMParser().parse_tags("OC-5109-19 XYT.PEM")

pprint.pprint(z)