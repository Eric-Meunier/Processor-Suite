from pem.pem_file import PEMFile
from log import Logger
logger = Logger(__name__)


class PEMSerializer:
    """
    Class for serializing PEM files to be saved
    """

    # Constructor
    def __init__(self):
        pass

    def serialize_tags(self, tags):
        def tag(id, content):
            return '<' + id + '> ' + str(content) + '\n'

        result = ""

        result += tag('FMT', tags['Format'])
        result += tag('UNI', tags['Units'])
        result += tag('OPR', tags['Operator'])
        result += tag('XYP', ' '.join([tags['XYProbe'],
                                       tags['SOA'],
                                       tags['Tool'],
                                       tags['ToolID']]))
        result += tag('CUR', tags['Current'])
        result += tag('TXS', tags['LoopSize'])

        return result

    def serialize_loop_coords(self, coords):
        result = '~ Transmitter Loop Co-ordinates:\n'
        cnt = 0
        for loop_coord in coords:
            result += loop_coord['Tag'] + ' ' + ' '.join(loop_coord['LoopCoordinates']) + '\n'
            cnt += 1
        return result

    def serialize_line_coords(self, coords):
        result = '~ Hole/Profile Co-ordinates:\n'
        cnt = 0
        for hole_coord in coords:
            result += hole_coord['Tag'] + ' ' + ' '.join(hole_coord['LineCoordinates']) + '\n'
            cnt += 1
        return result

    def serialize_notes(self, notes):
        if not notes:
            return ''
        return '\n'.join(notes) + '\n'

    def serialize_header(self, header):
        result_list = [header['Client'],
                       header['Grid'],
                       header['LineHole'],
                       header['Loop'],
                       header['Date'],
                       ' '.join([header['SurveyType'],
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

        result = '\n'.join(result_list) + '\n\n'

        times_per_line = 7
        cnt = 0

        channel_times = [str(time) for time in header['ChannelTimes']]

        for i in range(0, len(channel_times), times_per_line):
            line_times = channel_times[i:i+times_per_line]

            result += ' '.join([str(time) for time in line_times]) + '\n'

            cnt += 1

        return result

    def serialize_data(self, data):
        def serialize_reading(reading):
            # r'^(?P<Station>^\d+[NSEW]?)\s(?P<Component>[XYZ])R(?P<ReadingIndex>\d+)\s(?P<Gain>\d)\s(?P<RxType>[AM\?])\s(?P<ZTS>\d+\.\d+)\s(?P<CoilDelay>\d+)\s(?P<NumStacks>\d+)\s(?P<ReadingsPerSet>\d)\s(?P<ReadingNumber>\
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

            channel_readings = [str(r) for r in reading['Data']]

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

        logger.info("Serializing file...")

        result = self.serialize_tags(pem_file.get_tags()) + \
                 self.serialize_loop_coords(pem_file.get_loop_coords()) + \
                 self.serialize_line_coords(pem_file.get_line_coords()) + '~\n' + \
                 self.serialize_notes(pem_file.get_notes()) + \
                 self.serialize_header(pem_file.get_header()) + \
                 self.serialize_data(pem_file.get_data())

        logger.info("Finished serializing")

        return result
