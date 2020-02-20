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

        def get_station_gps(station_num):
            # Return the easting, northing, elevation of a station number
            pass

        result = ''
        components = pem_file.get_components()
        num_channels = int(pem_file.header.get('NumChannels'))
        pem_gps = pem_file.get_line_gps()
        pem_data = pem_file.data
        pem_data.sort(key=lambda x: x['Component'])
        pem_data.sort(key=lambda x: alpha_num_sort(x['Station']))

        header = ['Easting', 'Northing', 'Elevation', 'Component', 'Station']
        for ch in range(0, num_channels+1):
            header.append(f"ch{ch}")

        for station in pem_data:
            station_num = pem_file.convert_station(station['Station'])
            easting, northing, elevation = None, None, None

        header_row = '\t'.join(header)
        result += header_row
        return result
