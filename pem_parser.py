import re
import pprint
from decimal import Decimal


# File format constants
FILE_HEADERS = ['Client', 'Grid', 'LineHole', 'Loop', 'Date', 'TypeOfSurvey', 'Timebase', 'Ramp', 'NumChannels',
                'Receiver', 'ReceiverInfo', 'ChannelTimes', 'NumReadings']


class PEMFile:
    """
    Class for storing PEM file data for easy access
    """

    # Constructor
    def __init__(self, tags, header_results, survey):
        self.header_results = header_results
        self.survey = survey
        self.tags = tags

    # TODO Make individual getters for each field
    def get_tags(self):
        return self.tags

    def get_headers(self):
        return self.header_results

    def get_survey(self):
        return self.survey

    def get_unique_stations(self):
        # Create a set out of all the stations, which automatically removes duplicates.
        unique_stations = {int(n) for n in
                           [reading['station_number'] for reading in self.survey]}
        return sorted(unique_stations)


class PEMParser:
    """
    Class for parsing PEM files into PEM_File objects
    """

    # Constructor
    def __init__(self):
        # Compile necessary Regex objects once
        self.re_header = re.compile(  # Parsing the header information
            r'(^(<|~).*[\r\n])+'
            r'(?P<Client>\w.*)[\r\n]'
            r'(?P<Grid>.*)[\r\n]'
            r'(?P<LineHole>.*)[\r\n]'
            r'(?P<Loop>.*)[\r\n]'
            r'(?P<Date>.*)[\r\n]'
            r'(?P<TypeOfSurvey>\w+\s\w+).+\s(?P<Timebase>.+)\s(?P<Ramp>\d+)\s(?P<NumChannels>\d+)\s(?P<NumReadings>\d+)[\r\n]'
            r'(?P<Receiver>#\d+)(?P<ReceiverInfo>.*)[\n\r]+'
            r'(?P<ChannelTimes>(.*[\n\r])+)\$',
            re.MULTILINE)

        self.re_data = re.compile(  # Parsing the EM data information
            r'(?P<Station>^\d+)\s(?P<Component>[a-zA-Z])R(?P<ReadingIndex>\d+).*[\r\n]'
            r'(?:D\d.+[\n\r])'
            r'(?P<Data>[\W\d]+[\n\r])',
            re.MULTILINE)

        self.re_tags = re.compile( # Parsing the tags at beginning of file
            r'^<((?P<Format>FMT)|'
            r'(?P<Unit>UNI)|'
            r'(?P<Operator>OPR)|'
            r'(?P<XYProbe>XYP)|'
            r'(?P<PeakLoopCurrent>CUR)|'
            r'(?P<LoopSize>TXS)|'
            r'((?P<LoopCoords>L)(?P<LoopNumber>\d\d))|'
            r'((?P<HoleCoords>P)(?P<HoleNumber>\d\d))'
            r')>(?P<Content>[^~\r\n]*)(~|$)', re.MULTILINE)

    def parse_tags(self, file):
        result = {}

        for match in self.re_tags.finditer(file):
            # Iterate through each group name such as 'Format' or 'Unit' in the regex
            for group, index in self.re_tags.groupindex.items():
                # Skip Content group so that only the groups representing tag names get turned into keys in result
                if group == 'Content':
                    continue
                group_match = match.group(index)
                # If the group was matched with in this particular match
                if group_match:
                    if group not in ['LoopNumber', 'HoleNumber']:
                        content = match.group('Content')
                    else:
                        content = match.group(group)
                    content = content.strip()

                    if group not in result:
                        # Group has not yet been added to in result
                        result[group] = content
                    elif isinstance(result[group], list):
                        # Multiple values for group exist in result
                        result[group].append(content)
                    else:
                        # A value for group already exists in result so make
                        # the value a list instead and have it include both its
                        # prior self and the new value
                        result[group] = [result[group], content]

        # Collapse Coords and Numbers into single lists
        def collapse(coords, numbers):
            result = ['']*len(coords)
            numbers = [x for x in numbers if not x == ''] # Remove empty strings

            for i in range(len(numbers)):
                result[int(numbers[i])] = coords[i]

            return result

        if 'HoleCoords' in result:
            result['HoleCoords'] = collapse(result['HoleCoords'], result['HoleNumber'])
            del result['HoleNumber']
        if 'LoopCoords' in result:
            result['LoopCoords'] = collapse(result['LoopCoords'], result['LoopNumber'])
            del result['LoopNumber']

        # Convert necessary types to numbers
        # TODO Split XYProbe into X-Y probe #, SOA, tool #, tool id?
        result['XYProbe'] = [int(x) for x in result['XYProbe'].split()]
        result['PeakLoopCurrent'] = Decimal(result['PeakLoopCurrent'])
        loop_size = result['LoopSize'].split()
        result['LoopSize'] = [Decimal(loop_size[0]),
                              Decimal(loop_size[1]),
                              int(loop_size[2])]

        for i in range(len(result['LoopCoords'])):
            loop_coords = result['LoopCoords'][i].split()
            if result['LoopCoords'][i]:
                result['LoopCoords'][i] = [Decimal(x) for x in loop_coords[0:3]]+[int(loop_coords[3])]

        for i in range(len(result['HoleCoords'])):
            hole_coords = result['HoleCoords'][i].split()
            if result['HoleCoords'][i]:
                result['HoleCoords'][i] = [Decimal(x) for x in hole_coords[0:3]] + [int(hole_coords[3])]

        return result

    def parse_header(self, file):
        header_results = {}
        header_matches = re.match(self.re_header, file)
        for i in range(len(FILE_HEADERS)):  # Compiles the header information from the PEM file into a dictionary
            header_results[FILE_HEADERS[i]] = header_matches.group(FILE_HEADERS[i])

        # Extract numbers from strings
        header_results['ChannelTimes'] = [Decimal(x) for x in header_results['ChannelTimes'].split()]
        return header_results

    def parse_data(self, file):
        station_number = []
        reading_index = []
        decay = []
        component = []

        for match in self.re_data.finditer(file):  # Compiles the EM data section
            # TODO Abstract out names like 'Station' and 'ReadingIndex' to constants
            station_number.append(match.group('Station'))
            reading_index.append(match.group('ReadingIndex'))
            decay.append([Decimal(x) for x in match.group('Data').split()])
            component.append(match.group('Component'))
            # print('\n\nStation: ',station_number,'\nReading Index :',reading_index,'\nDecay: ',decay,'\nComponent: ',component)

        survey = []
        for i in range(len(station_number)):
            survey.append({'StationNumber': int(station_number[i]),
                           'ReadingIndex': reading_index[i],
                           'Decay': decay[i],
                           'Component': component[i]})

        # for station in ([x for i, x in enumerate(station_number) if station_number.index(x) == i]):
        #     print (station_number.index(station))
        return survey

    def parse(self, filename):
        """
        :param filename: string containing path to a PEM file
        :return: A PEM_File object representing the data found inside of filename
        """
        file = None
        with open(filename, "rt") as in_file:
            file = in_file.read()

        # Parse tags section
        tags = self.parse_tags(file)

        # Parse header section
        header_results = self.parse_header(file)

        # Parse the EM data in the PEM files
        survey = self.parse_data(file)

        return PEMFile(tags, header_results, survey)
