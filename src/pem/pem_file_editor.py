import os
import sys
import re
from copy import copy
from decimal import Decimal, getcontext

import numpy as np

from src.pem.pem_parser import PEMParser

getcontext().prec = 6

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
            pem_file.unaveraged_data = copy(pem_file.get_data())
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
                        stack_weights = []
                        total_stacks = 0

                        for reading in component_data:
                            stack_weights.append(int(reading['NumStacks']))
                            total_stacks += int(reading['NumStacks'])
                            unique_station_readings.append(reading['Data'])
                        # if station == '900S':
                        stack_weights = np.array(stack_weights, dtype=object)/total_stacks
                        averaged_reading = np.average(np.array(unique_station_readings, dtype=float), axis=0, weights=stack_weights)

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
                    if float(pair[0]) == pp_times[0] and float(pair[1]) == pp_times[1]:
                        return [(pp_times, i-1)]  # i offset by 1 because length difference with channel_times
            if 'fluxgate' or 'squid' in survey_type.lower():
                return [(channel_pairs[0], 0)]

        if pem_file.is_split():
            return
        else:
            pem_file.unsplit_data = copy(pem_file.data)
            channel_times = pem_file.header.get('ChannelTimes')
            channel_pairs = list(map(lambda x, y: (x, y), channel_times[:-1], channel_times[1:]))

            offtime_channels = get_offtime_channels(channel_times)
            pp_channel = get_pp_channel()
            kept_channels = pp_channel + offtime_channels
            kept_channels_indexes = [item[1] for item in kept_channels]

            # Modifying the EM data
            for station in pem_file.get_data():
                off_time_readings = []
                for i, reading in enumerate(station['Data']):
                    if i in kept_channels_indexes:
                        off_time_readings.append(reading)
                    else:
                        pass
                station['Data'] = off_time_readings

            pem_file.header['NumChannels'] = str(len(kept_channels_indexes)-1)
            pem_file.header['ChannelTimes'] = [item[0] for item in kept_channels]
            pem_file.header['ChannelTimes'] = list(dict.fromkeys(list(sum(pem_file.header['ChannelTimes'], ()))))

            return pem_file

    def scale_coil_area(self, pem_file, new_coil_area):
        new_coil_area = int(new_coil_area)
        old_coil_area = int(pem_file.header.get('CoilArea'))

        scale_factor = Decimal(old_coil_area/new_coil_area)

        for i, station in enumerate(pem_file.data):
            for j, reading in enumerate(station['Data']):
                pem_file.data[i]['Data'][j] = reading * scale_factor
        pem_file.header['CoilArea'] = str(new_coil_area)
        pem_file.notes.append('<HE3> Data scaled by coil area change from {0} to {1}'.format(str(old_coil_area), str(new_coil_area)))

        return pem_file

    def shift_stations(self, pem_file, shift_amt):
        data = pem_file.get_data()
        for reading in data:
            old_num = int(re.findall('\d+', reading['Station'])[0])
            suffix = str(re.search('[NSEW]', reading['Station']))
            new_num = str(old_num + shift_amt)
            reading['Station'] = str(new_num+suffix)
        return pem_file


if __name__ == '__main__':
    editor = PEMFileEditor()
    parser = PEMParser()

    # sample_files = os.path.join(os.path.dirname(os.path.dirname(application_path)), "sample_files")
    sample_files = r'C:\Users\Eric\Desktop\All survey types'
    file_names = [f for f in os.listdir(sample_files) if
                  os.path.isfile(os.path.join(sample_files, f)) and f.lower().endswith('.pem')]
    file_paths = []

    file = os.path.join(sample_files, file_names[0])
    for file in file_names:
        filepath = os.path.join(sample_files, file)
        print('File: ' + filepath)

        pem_file = parser.parse(filepath)
        editor.shift_stations(pem_file, 1000)
    # file = r'C:\Users\Eric\Desktop\600N.PEM'
    # file = r'C:\Users\Eric\Desktop\All survey types\CDR2 SQUID.PEM'
    # file = r'C:\Users\Eric\Desktop\2400NAv.PEM'
    #
    # pem_file = parser.parse(file)
    # editor.shift_stations(pem_file, 1000)
