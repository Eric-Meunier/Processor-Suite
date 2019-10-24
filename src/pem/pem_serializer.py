# from log import Logger
# logger = Logger(__name__)
import logging
import re

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s', datefmt='%d-%b-%y %H:%M:%S')


class PEMSerializer:
    """
    Class for serializing PEM files to be saved
    """

    # Constructor
    def __init__(self):
        logging.info('PEMSerializer')

    def serialize_tags(self, tags):
        def tag(id, content):
            return '<' + id + '> ' + str(content) + '\n'

        result = ""

        result += tag('FMT', tags['Format'])
        result += tag('UNI', tags['Units'])
        result += tag('OPR', tags['Operator'])
        # TODO Probes line are currently a single line, not individual
        # result += tag('XYP', ' '.join([tags['XYProbe'],
        #                                tags['SOA'],
        #                                tags['Tool'],
        #                                tags['ToolID']]))
        result += tag('XYP', tags['Probes'])
        result += tag('CUR', tags['Current'])
        result += tag('TXS', tags['LoopSize'])

        return result

    def serialize_loop_coords(self, coords):
        # Coords are a list of lists
        result = '~ Transmitter Loop Co-ordinates:\n'
        if not coords:
            result += '<L00>\n''<L01>\n''<L02>\n''<L03>\n'
        else:
            for i, position in enumerate(coords):
                tag = f"<L{i:02d}> "
                row = ' '.join(position)
                result += tag + row + '\n'
        return result

    def serialize_line_coords(self, pem_file):

        def serialize_station_coords(coords):
            # Coords are a list of lists
            result = '~ Hole/Profile Co-ordinates:\n'
            if not coords or not any(coords):
                result += '<P00>\n''<P01>\n''<P02>\n''<P03>\n''<P04>\n''<P05>\n'
            else:
                for i, position in enumerate(coords):
                    tag = f"<P{i:02d}> "
                    row = ' '.join(position)
                    result += tag + row + '\n'
            return result

        def serialize_collar_coords(coords):
            # Coords are a list of lists
            result = '~ Hole/Profile Co-ordinates:\n'
            if not coords or not any(coords):
                result += '<P00>\n'
            else:
                for i, position in enumerate(coords):
                    tag = f"<P00> "
                    row = ' '.join(position)
                    result += tag + row + '\n'
            return result

        def serialize_segments(segments):
            # segments are a list of lists
            result = ''
            if not segments or not any(segments):
                result += '<P01>\n''<P02>\n''<P03>\n''<P04>\n''<P05>\n'
            else:
                for i, position in enumerate(segments):
                    tag = f"<P{i + 1:02d}> "
                    row = ' '.join(position)
                    result += tag + row + '\n'
            return result

        if 'surface' in pem_file.survey_type.lower() or 'squid' in pem_file.survey_type.lower():
            return serialize_station_coords(pem_file.get_line_coords())
        else:
            return serialize_collar_coords(pem_file.get_collar_coords()) + \
                   serialize_segments(pem_file.get_hole_geometry())

    def serialize_notes(self, notes):
        results = []
        if not notes:
            return ''
        else:
            for line in notes:
                if line not in results:
                    results.append(line)
        return '\n'.join(results) + '\n'

    def serialize_header(self, header):
        result_list = [header['Client'],
                       header['Grid'],
                       header['LineHole'],
                       header['Loop'],
                       header['Date'],
                       ' '.join([header['SurveyType'],
                                 header['Convension'],
                                 header['Sync'],
                                 header['Timebase'],
                                 header['Ramp'],
                                 header['NumChannels'],
                                 header['NumReadings']]),
                       ' '.join([header['Receiver'],
                                 header['RxSoftwareVer'],
                                 header['RxSoftwareVerDate'],
                                 header['RxFileName'],
                                 header['IsNormalized'],
                                 header['PrimeFieldValue'],
                                 header['CoilArea']])]

        if header['LoopPolarity'] is not None:
            result_list[-1] += ' ' + header['LoopPolarity']

        result = '\n'.join(result_list) + '\n\n'

        times_per_line = 7
        cnt = 0

        channel_times = [f'{time:.6f}' for time in header['ChannelTimes']]
        channel_times = list(map(lambda x: ' ' + x if not x.startswith('-') else x, channel_times))

        for i in range(0, len(channel_times), times_per_line):
            line_times = channel_times[i:i+times_per_line]

            result += ' '.join([str(time) for time in line_times]) + '\n'

            cnt += 1

        result += '$\n'

        return result

    def serialize_data(self, data):

        def atoi(text):
            return int(text) if text.isdigit() else text

        def natural_keys(text):
            '''
            alist.sort(key=natural_keys) sorts in human order
            http://nedbatchelder.com/blog/200712/human_sorting.html
            '''
            return [atoi(c) for c in re.split(r'(\d+)', text)]

        data.sort(key=lambda i: (i['Component'], natural_keys(i['Station']), i['ReadingNumber']))

        def serialize_reading(reading):
            result = ' '.join([reading['Station'],
                               reading['Component'] + 'R' + reading['ReadingIndex'],
                               reading['Gain'],
                               reading['RxType'],
                               reading['ZTS'],
                               reading['CoilDelay'],
                               reading['NumStacks'],
                               reading['ReadingsPerSet'],
                               reading['ReadingNumber']]) + '\n'
            result += reading['RADTool'] + '\n'

            readings_per_line = 7
            reading_spacing = 15
            cnt = 0

            channel_readings = [f'{r:0.6g}' for r in reading['Data']]
            channel_readings = list(map(lambda x: ' ' + x if not x.startswith('-') else x, channel_readings))

            for i in range(0, len(channel_readings), readings_per_line):
                readings = channel_readings[i:i + readings_per_line]
                result += ' '.join([str(r) + max(0, reading_spacing - len(r))*' ' for r in readings]) + '\n'
                cnt += 1

            return result + '\n'

        return ''.join([serialize_reading(reading) for reading in data])

    def serialize(self, pem_file):
        """
        :param pem_file: PEM_File object
        :return: A string in PEM file format containing the data found inside of pem_file
        """

        result = self.serialize_tags(pem_file.get_tags()) + \
                 self.serialize_loop_coords(pem_file.get_loop_coords()) + \
                 self.serialize_line_coords(pem_file) + \
                 self.serialize_notes(pem_file.get_notes()) + '~\n' + \
                 self.serialize_header(pem_file.get_header()) + \
                 self.serialize_data(pem_file.get_data())

        return result
