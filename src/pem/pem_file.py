import re

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
        unique_stations = {self.convert_station(n) for n in
                           [reading['Station'] for reading in self.data]}
        return unique_stations

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
