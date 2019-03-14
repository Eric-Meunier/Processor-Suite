import re
import pprint
from decimal import Decimal


# File format constants
FILE_HEADERS = ['Client', 'Grid', 'LineHole', 'Loop', 'Date', 'TypeOfSurvey', 'Timebase', 'Ramp', 'NumChannels',
                'Receiver', 'ChannelTimes']


class PEM_File:
    """
    Class for storing PEM file data for easy access
    """

    # Constructor
    def __init__(self, header_results, survey):
        # TODO Organize header_results into separate fields like survey?
        self.header_results = header_results
        self.survey = survey

    def get_headers(self):
        return self.header_results

    def get_survey(self):
        return self.survey

    def get_unique_stations(self):
        # Create a set out of all the stations, which automatically removes duplicates.
        unique_stations = {int(n) for n in
                           [reading['station_number'] for reading in self.survey]}
        return sorted(unique_stations)


class PEM_Parser:
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
            r'(?P<TypeOfSurvey>\w+\s\w+).+\s(?P<Timebase>\d+\.\d+)\s(?P<Ramp>\d+)\s'
            r'(?P<NumChannels>\d+).*[\r\n]'
            r'(?P<Receiver>#\d+).*[\n\r]+'
            r'(?P<ChannelTimes>(.*[\n\r])+)\$',
            re.MULTILINE)

        self.re_data = re.compile(  # Parsing the EM data information
            r'(?P<Station>^\d+)\s(?P<Component>[a-zA-Z])R(?P<ReadingIndex>\d+).*[\r\n]'
            r'(?:D\d.+[\n\r])'
            r'(?P<Data>[\W\d]+[\n\r])',
            re.MULTILINE)

    def parse(self, filename):
        """
        :param filename: string containing path to a PEM file
        :return: A PEM_File object representing the data found inside of filename
        """
        file = None
        with open(filename, "rt") as in_file:
            file = in_file.read()

        # Parse header section
        header_results = {}
        header_matches = re.match(self.re_header, file)
        for i in range(len(FILE_HEADERS)):  # Compiles the header information from the PEM file into a dictionary
            header_results[FILE_HEADERS[i]] = header_matches.group(FILE_HEADERS[i])

        # Extract numbers from strings
        header_results['ChannelTimes'] = [Decimal(x) for x in header_results['ChannelTimes'].split()]

        # TODO units is unused, perhaps make units a field in PEM_file
        units = re.search(r"<UNI> (\w.+)", file, re.MULTILINE)

        # Parse the EM data in the PEM files
        station_number = []
        reading_index = []
        decay = []
        component = []

        for match in self.re_data.finditer(file):  # Compiles the EM data section
            # TODO Abstract out names like 'Station' and 'ReadingIndex' to constants
            station_number.append(match.group('Station'))
            reading_index.append(match.group('ReadingIndex'))
            decay.append([float(x) for x in match.group('Data').split()])
            component.append(match.group('Component'))
            # print('\n\nStation: ',station_number,'\nReading Index :',reading_index,'\nDecay: ',decay,'\nComponent: ',component)

        survey = []
        for i in range(len(station_number)):
            survey.append({'station_number': int(station_number[i]),
                           'reading_index': reading_index[i],
                           'decay': decay[i],
                           'component': component[i]})

        # for station in ([x for i, x in enumerate(station_number) if station_number.index(x) == i]):
        #     print (station_number.index(station))

        return PEM_File(header_results, survey)
