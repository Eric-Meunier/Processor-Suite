import itertools
from colorama import Fore, Back
import os
import re
import sys
from copy import copy
from decimal import Decimal

import numpy as np

from src.pem._legacy.pem_parser import PEMParser


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
                        stack_weights = np.array(stack_weights, dtype=object) / total_stacks
                        averaged_reading = np.average(np.array(unique_station_readings, dtype=float), axis=0,
                                                      weights=stack_weights)

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
            num_ontime_channels = len(ontime_channels) - 1

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
                        return [(pp_times, i - 1)]  # i offset by 1 because length difference with channel_times
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

            pem_file.header['NumChannels'] = str(len(kept_channels_indexes) - 1)
            pem_file.header['ChannelTimes'] = [item[0] for item in kept_channels]
            pem_file.header['ChannelTimes'] = list(dict.fromkeys(list(sum(pem_file.header['ChannelTimes'], ()))))

            return pem_file

    def scale_coil_area(self, pem_file, new_coil_area):
        new_coil_area = int(new_coil_area)
        old_coil_area = int(pem_file.header.get('CoilArea'))

        scale_factor = Decimal(old_coil_area / new_coil_area)

        for i, station in enumerate(pem_file.data):
            for j, reading in enumerate(station['Data']):
                pem_file.data[i]['Data'][j] = reading * scale_factor
        pem_file.header['CoilArea'] = str(new_coil_area)
        pem_file.notes.append(
            '<HE3> Data scaled by coil area change from {0} to {1}'.format(str(old_coil_area), str(new_coil_area)))

        return pem_file

    def scale_current(self, pem_file, new_current):
        new_current = float(new_current)
        old_current = float(pem_file.tags.get('Current'))

        scale_factor = Decimal(new_current / old_current)

        for i, station in enumerate(pem_file.data):
            for j, reading in enumerate(station['Data']):
                pem_file.data[i]['Data'][j] = reading * scale_factor
        pem_file.tags['Current'] = str(new_current)
        pem_file.notes.append(
            '<HE3> Data scaled by current change from {0}A to {1}A'.format(str(old_current), str(new_current)))

        return pem_file

    def shift_stations(self, pem_file, shift_amt, rows=None):
        """
        Shift station number
        :param shift_amt: Amount to shift the station number by
        :param rows: Corresponding row (reading) of the PEMFile in the dataTable
        :return: Updated PEMFile
        """
        if not rows:
            data = pem_file.get_data()
        else:
            data = [pem_file.data[row] for row in rows]
        for reading in data:
            station_num = int(re.findall('-?\d+', reading['Station'])[0])
            new_station_num = station_num + shift_amt
            new_station = re.sub(str(station_num), str(new_station_num), reading['Station'])
            reading['Station'] = new_station
        return pem_file

    def rename_repeats(self, pem_file):
        """
        Rename any stations that end with 1, 4, 6, or 9, numbers usually used to indicate that the station is a
        repeat from a previous section, to the nearest number 0 or 5.
        :param pem_file: PEMFile object
        :return: PEMFile object with stations renamed
        """
        data = pem_file.get_data()
        for reading in data:
            station_num = int(re.findall('-?\d+', reading['Station'])[0])
            station_suffix = re.findall('[nsewNSEW]', reading['Station'])
            if str(station_num)[-1] == '1' or str(station_num)[-1] == '6':
                print(f"station {station_num} changed to {station_num-1}")
                station_num -= 1
                reading['Station'] = str(station_num) + station_suffix[0] if station_suffix else str(station_num)
            elif str(station_num)[-1] == '4' or str(station_num)[-1] == '9':
                print(f"station {station_num} changed to {station_num + 1}")
                station_num += 1
                reading['Station'] = str(station_num)+station_suffix[0] if station_suffix else str(station_num)
        return pem_file

    def reverse_polarity(self, pem_file, rows=None, component=None):
        """
        Flip the data for given readings
        :param pem_file: PEMFile object
        :param rows: Corresponding row (reading) of the PEMFile in the dataTable
        :return: Updated PEMFile
        """
        if component is None:
            data = [pem_file.data[row] for row in rows]
        else:
            data = filter(lambda x: x['Component'] == component, pem_file.data)
        for reading in data:
            decay = np.array(reading['Data'])
            reading['Data'] = decay * -1
        return pem_file

    def auto_clean(self, pem_file):

        def same_decay_lengths(decays):
            length = len(decays[0])
            for decay in decays:
                if len(decay) != length:
                    return False
            return True

        def within_SE(std, mean, value):
            upper_lim, lower_lim = mean + (2 * std), mean - (2 * std)
            print(Fore.BLACK + f"Upper limit: {upper_lim}  Value: {value}  Lower limit: {lower_lim}")
            if value > upper_lim or value < lower_lim:
                return False
            else:
                return True

        if not pem_file.is_averaged():
            pem_data = pem_file.data
            cleaned_data = []
            # components = pem_file.get_components()
            components = 'Z'

            for component in components:
                component_data = [station for station in pem_data if station['Component'] == component]

                # Group the decays from the same stations together
                for station, readings in itertools.groupby(component_data, key=lambda x: x['Station']):
                    readings = list(readings)
                    decays = [reading['Data'] for reading in list(readings)]
                    if same_decay_lengths(decays):
                        for channel in range(len(decays[0])):
                            print(Fore.BLACK + Back.LIGHTMAGENTA_EX + f"Station: {station}  Channel: {channel}")
                            channel_values = np.array([decay[channel] for decay in decays])

                            if len(channel_values) > 2:
                                std = channel_values.std()
                                mean = channel_values.mean()
                                print(Fore.BLACK + f"STD: {std}  Mean: {mean}")

                                for index, value in enumerate(channel_values):
                                    if not within_SE(std, mean, value):
                                        print(Fore.RED + f"Station: {station}  Channel: {channel}  Component: {component}")
                                        print(Fore.RED + f"STD: {std}  Mean: {mean}")
                                        print(Fore.RED + f"Value: {value}  Within SE: {within_SE(std, mean, value)}")
                                        print(Fore.MAGENTA + f"Removing reading index {index} of station {station}, component {component}")
                                        decays.pop(index)
                                        readings.pop(index)
                                        component_data.remove(readings[index])
                                        break
                    else:
                        raise ValueError('Not all decay lengths are the same')

            pem_data = component_data


if __name__ == '__main__':
    from src.pem.pem_getter import PEMGetter
    editor = PEMFileEditor()
    parser = PEMParser()
    getter = PEMGetter()

    pem_files = getter.get_pems()

    editor.auto_clean(pem_files[0])
