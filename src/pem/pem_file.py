from src.pem.pem_serializer import PEMSerializer
import re
import os
from src.gps.gps_editor import TransmitterLoop, SurveyLine, BoreholeCollar, BoreholeGeometry


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
        self.receiver_number = header.get('Receiver number')
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
            self.collar = BoreholeCollar(line_coords, name=self.line_name)
            self.geometry = BoreholeGeometry(line_coords)
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
            if not self.collar.df.empty and all(self.collar.df):
                return True
            else:
                return False
        else:
            return False

    def has_geometry(self):
        if self.is_borehole():
            if not self.geometry.df.empty and all(self.geometry.df):
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
        raise ValueError(f'No CRS found in {self.filename}')

    def get_loop_coords(self, sorted=True):
        if sorted:
            return self.loop.get_sorted_loop()
        else:
            return self.loop.get_loop()

    def get_station_coords(self, sorted=True):
        if sorted:
            return self.line.get_sorted_line()
        else:
            return self.line.get_line()

    def get_collar_coords(self):
        return self.collar.get_collar()

    def get_hole_geometry(self):
        return self.geometry.get_segments()

    # def get_line_coords(self):  # All P tags
    #     if self.is_borehole():
    #         return self.get_collar_coords()+self.get_hole_geometry()
    #     else:
    #         return self.get_station_coords()

    def get_notes(self):
        return self.notes

    def get_data(self):
        return self.data

    def get_components(self):
        components = list(self.data['Component'].unique())
        return components

    def get_unique_stations(self, converted=False):
        if converted:
            [self.convert_station(station) for station in self.data['Station'].unique()]
        else:
            return self.data['Station'].unique()

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
                    station_number = int(self.convert_station(station['Station']))
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
        ps = PEMSerializer()
        pem_file = ps.serialize(self)
        return pem_file

