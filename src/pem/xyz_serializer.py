import re

def alpha_num_sort(string):
    """ Returns all numbers on 5 digits to let sort the string with numeric order.
    Ex: alphaNumOrder("a6b12.125")  ==> "a00006b00012.00125"
    """
    return ''.join([format(int(x), '05d') if x.isdigit()
                    else x for x in re.split(r'(\d+)', string)])

class XYZSerializer:
    """
    Arrange a PEM file into an XYZ file format
    """

    def serialize_pem(self, pem_file):

        def get_station_gps(station_num, line_gps):
            # Return the easting, northing, elevation of a station number
            gps_list = [int(line[-1]) for line in line_gps]
            try:
                index = gps_list.index(station_num)
                easting, northing, elevation = line_gps[index][0], line_gps[index][1], line_gps[index][2]
                return easting, northing, elevation
            except ValueError:
                print(f"Station {station_num} not in line GPS")
                return None, None, None

        result = ''
        components = pem_file.get_components()
        num_channels = int(pem_file.header.get('NumChannels'))
        pem_gps = pem_file.get_line_coords()
        pem_data = pem_file.data
        pem_data.sort(key=lambda x: alpha_num_sort(x['Station']))
        pem_data.sort(key=lambda x: x['Component'])

        header = ['Easting', 'Northing', 'Elevation', 'Component', 'Station']
        for ch in range(0, num_channels+1):
            header.append(f"ch{ch}")

        header_row = ' '.join(header)
        result += header_row + '\n'

        for station in pem_data:
            station_num = pem_file.convert_station(station['Station'])
            easting, northing, elevation = get_station_gps(station_num, pem_gps)
            if all([easting, northing, elevation]):
                component = station['Component'].upper()
                result += ' '.join([easting, northing, elevation, component, str(station_num)])
                for channel in range(0, num_channels+1):
                    result += ' ' + str(station['Data'][channel])
                result += '\n'

        return result
