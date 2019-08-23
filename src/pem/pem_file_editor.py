import os
import sys
from copy import copy
from decimal import Decimal
from pprint import pprint
from functools import reduce
from src.pem.pem_parser import PEMParser
from src.pem.pem_file import PEMFile

import numpy as np

if getattr(sys, 'frozen', False):
    # If the application is run as a bundle, the pyInstaller bootloader
    # extends the sys module by a flag frozen=True and sets the app
    # path into variable _MEIPASS'.
    application_path = sys._MEIPASS
else:
    application_path = os.path.dirname(os.path.abspath(__file__))


class PEMFileEditor:
    """
    Class to make edits to PEMFiles
    """

    def average(self, pem_file):
        """
        Average the EM data
        :param pem_file: PEMFile object
        :return: PEMFile object with the data (*.get_data()) averaged. Also adds a 'raw_data' attribute which
        is the old un-averaged data
        """
        if pem_file.is_averaged():
            print('File is averaged')
            return
        else:
            pem_file.raw_data = copy(pem_file.get_data())
            new_data = []
            unwanted_keys = ['Data', 'NumStacks']
            num_channels = pem_file.header.get('NumChannels')
            pem_data = pem_file.get_data()
            unique_stations = pem_file.get_unique_stations()
            components = pem_file.get_components()

            for station in unique_stations:
                station_data = list(filter(lambda x: x['Station'] == station, pem_data))

                for component in components:
                    component_data = list(filter(lambda x: x['Component'] == component, station_data))
                    if component_data:
                        new_unique_station = {}
                        unique_station_readings = []
                        total_stacks = 0

                        for reading in component_data:
                            reading_data = reading['Data']
                            total_stacks += int(reading['NumStacks'])
                            unique_station_readings.append(reading_data)

                        averaged_reading = np.mean(np.array(unique_station_readings), axis=0)

                        for k, v in component_data[0].items():
                            if k not in unwanted_keys:
                                new_unique_station[k] = v

                        new_unique_station['Data'] = [Decimal(x) for x in averaged_reading]
                        new_unique_station['NumStacks'] = str(total_stacks)

                        new_data.append(new_unique_station)

            pem_file.header['NumReadings'] = str(len(new_data))
            pem_file.data = new_data

        return pem_file

    def split_channels(self, pem_file):

        def get_offtime_channels(channel_times):
            ontime_channels = list(filter(lambda x: x <= 0, channel_times))
            num_ontime_channels = len(ontime_channels)-1

            remaining_channels = list(filter(lambda x: x > 0, channel_times))
            paired_channel_times = list(map(lambda x, y: (x, y), remaining_channels[:-1], remaining_channels[1:]))
            differences = list(map(lambda x, y: y - x, remaining_channels[:-1], remaining_channels[1:]))

            offtime_channels = [(paired_channel_times[0], num_ontime_channels)]

            for i, channel in enumerate(differences[1:]):
                # Divided by 2 because there are small drops in CDDR3 borehole fluxgate times
                if differences[i + 1] >= (differences[i] / 2):
                    offtime_channels.append((paired_channel_times[i + 1], i + 1 + num_ontime_channels))
                else:
                    break
            return offtime_channels

        def get_pp_channel():
            survey_type = pem_file.survey_type
            if 'induction' in survey_type.lower():
                pp_times = (-0.0002, -0.0001)
                for i, pair in enumerate(channel_pairs):
                    if float(pair[0]) == pp_times[0]:
                        return [(pp_times, i)]
            if 'fluxgate' or 'squid' in survey_type.lower():
                return [(channel_pairs[0], 0)]

        if pem_file.is_split():
            print('Stop, already split')
        else:
            pem_file.unsplit_data = copy(pem_file.data)
            channel_times = pem_file.header.get('ChannelTimes')
            channel_pairs = list(map(lambda x, y: (x, y), channel_times[:-1], channel_times[1:]))

            offtime_channels = get_offtime_channels(channel_times)
            pp_channel = get_pp_channel()
            kept_channels = pp_channel + offtime_channels
            kept_channels_indeces = [item[1] for item in kept_channels]

            # Modifying the EM data
            for station in pem_file.get_data():
                off_time_readings = []
                for i, reading in enumerate(station['Data']):
                    if i in kept_channels_indeces:
                        off_time_readings.append(reading)
                    else:
                        pass
                station['Data'] = off_time_readings

            pem_file.header['NumChannels'] = str(len(kept_channels_indeces))
            pem_file.header['ChannelTimes'] = [item[0] for item in kept_channels]
            pem_file.header['ChannelTimes'] = list(dict.fromkeys(list(sum(pem_file.header['ChannelTimes'], ()))))

            return pem_file


if __name__ == '__main__':
    editor = PEMFileEditor()
    parser = PEMParser()

    # sample_files = os.path.join(os.path.dirname(os.path.dirname(application_path)), "sample_files")
    sample_files = r'C:\Users\Eric\Desktop\All survey types'
    file_names = [f for f in os.listdir(sample_files) if
                  os.path.isfile(os.path.join(sample_files, f)) and f.lower().endswith('.pem')]
    file_paths = []

    # file = os.path.join(sample_files, file_names[0])
    for file in file_names:
        filepath = os.path.join(sample_files, file)
        print('File: ' + filepath)

        pem_file = parser.parse(filepath)
        editor.split_channels(pem_file)
    # file = r'C:\Users\Eric\Desktop\600N.PEM'
    # file = r'C:\Users\Eric\Desktop\CDR3 Surface Induction.PEM'
    # file = r'C:\Users\Eric\Desktop\2400NAv.PEM'
    #
    # print('File: '+file)
    # pem_file = parser.parse(file)
    # editor.split_channels(pem_file)
