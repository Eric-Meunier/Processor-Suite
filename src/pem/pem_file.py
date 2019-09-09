from src.pem.pem_serializer import PEMSerializer
import re
import logging

logging.info('PEMFile')

class PEMFile:
    """
    Class for storing PEM file data for easy access
    """
    # Constructor
    def __init__(self, tags, loop_coords, line_coords, notes, header, data, components, survey_type, filepath=None):
        self.tags = tags
        self.loop_coords = loop_coords
        self.line_coords = line_coords
        self.notes = notes
        self.header = header
        self.data = data
        self.components = components
        self.survey_type = survey_type
        self.filepath = filepath
        self.unsplit_data = None
        self.unaveraged_data = None
        self.old_filepath = None
        self.is_merged = False

    def is_averaged(self):
        unique_identifiers = []
        for reading in self.data:
            identifier = ''.join([reading['Station'], reading['Component']])
            if identifier in unique_identifiers:
                return False
            else:
                unique_identifiers.append(identifier)
        return True

    def is_split(self):
        channel_times = self.header.get('ChannelTimes')
        num_ontime_channels = len(list(filter(lambda x: x < 0, channel_times)))-1

        if num_ontime_channels == 1:
            return True
        else:
            return False

    def get_tags(self):
        return self.tags

    def get_loop_coords(self):
        return self.loop_coords

    def get_line_coords(self):
        return self.line_coords

    def get_notes(self):
        return self.notes

    def get_header(self):
        return self.header

    def get_data(self):
        return self.data

    def get_components(self):
        components = {reading['Component'] for reading in self.data}
        sorted_components = (sorted(components, reverse=False))
        if 'Z' in sorted_components:
            sorted_components.insert(0, sorted_components.pop(sorted_components.index('Z')))
        return sorted_components

    def get_unique_stations(self):
        unique_stations = []
        for reading in self.data:
            if reading['Station'] not in unique_stations:
                unique_stations.append(reading['Station'])
        # unique_stations_list = [station for station in unique_stations]
        return unique_stations

    def get_converted_unique_stations(self):
        return [self.convert_station(station) for station in self.get_unique_stations()]

    def convert_station(self, station):
        """
        Converts a single station name into a number, negative if the stations was S or W
        :return: Integer station number
        """
        if re.match(r"\d+(S|W)", station):
            station = (-int(re.sub(r"\D", "", station)))

        else:
            station = (int(re.sub(r"\D", "", station)))

        return station

    def get_profile_data(self, component_data):
        """
        Transforms the data so it is ready to be plotted for LIN and LOG plots
        :param component_data: Data (dict) for a single component (i.e. Z, X, or Y)
        :return: Dictionary where each key is a channel, and the values of those keys are a list of
        dictionaries which contain the stations and readings of all readings of that channel
        """
        profile_data = {}
        num_channels = len(component_data[0]['Data'])

        for channel in range(0, num_channels):
            # profile_data[channel] = {}
            channel_data = []

            for i, station in enumerate(component_data):
                reading = station['Data'][channel]
                station_number = int(self.convert_station(station['Station']))
                channel_data.append({'Station': station_number, 'Reading': reading})

            profile_data[channel] = channel_data

        return profile_data

    def get_survey_type(self):
        survey_type = self.header['SurveyType']

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

    def save_file(self):
        ps = PEMSerializer()
        pem_file = ps.serialize(self)
        return pem_file
