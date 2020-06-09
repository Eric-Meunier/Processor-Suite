import natsort


class PEMSerializer:
    """
    Class for serializing PEM files to be saved
    """

    # Constructor
    def __init__(self):
        pass

    def serialize_tags(self, pem_file):
        result = ""
        xyp = ' '.join([pem_file.probes.get('XY probe number'),
                        pem_file.probes.get('SOA'),
                        pem_file.probes.get('Tool number'),
                        pem_file.probes.get('Tool ID')])
        result += f"<FMT> {pem_file.format}\n"
        result += f"<UNI> {'nanoTesla/sec' if pem_file.units == 'nT/s' else 'picoTesla'}\n"
        result += f"<OPR> {pem_file.operator}\n"
        result += f"<XYP> {xyp}\n"
        result += f"<CUR> {pem_file.current}\n"
        result += f"<TXS> {pem_file.loop_dimensions}"

        return result

    def serialize_loop_coords(self, pem_file):
        result = '~ Transmitter Loop Co-ordinates:\n'
        loop = pem_file.get_loop()
        if loop.empty:
            result += '<L00>\n''<L01>\n''<L02>\n''<L03>\n'
        else:
            loop.reset_index(inplace=True)
            for row in loop.itertuples():
                tag = f"<L{row.Index:02d}>"
                row = f"{tag} {row.Easting:.2f} {row.Northing:.2f} {row.Elevation:.2f} {row.Unit}"
                result += row + '\n'
        return result

    def serialize_line_coords(self, pem_file):

        def serialize_station_coords():
            result = '~ Hole/Profile Co-ordinates:\n'
            line = pem_file.get_line()
            if line.empty:
                result += '<P00>\n''<P01>\n''<P02>\n''<P03>\n''<P04>\n''<P05>\n'
            else:
                line.reset_index(inplace=True)
                for row in line.itertuples():
                    tag = f"<P{row.Index:02d}>"
                    row = f"{tag} {row.Easting:.2f} {row.Northing:.2f} {row.Elevation:.2f} {row.Unit} {row.Station}"
                    result += row + '\n'
            return result

        def serialize_collar_coords():
            result = '~ Hole/Profile Co-ordinates:\n'
            collar = pem_file.get_collar()
            if collar.empty:
                result += '<P00>\n'
            else:
                for row in collar.itertuples():
                    tag = f"<P{row.Index:02d}>"
                    row = f"{tag} {row.Easting:.2f} {row.Northing:.2f} {row.Elevation:.2f} {row.Unit}"
                    result += row + '\n'
            return result

        def serialize_segments():
            result = ''
            segs = pem_file.get_segments()
            if segs.empty:
                result += '<P01>\n''<P02>\n''<P03>\n''<P04>\n''<P05>\n'
            else:
                for row in segs.itertuples():
                    tag = f"<P{row.Index:02d}>"
                    row = f"{tag} {row.Azimuth:.2f} {row.Dip:.2f} {row[3]:.2f} {row.Unit} {row.Depth:.2f}"
                    result += row + '\n'
            return result

        if pem_file.is_borehole():
            return serialize_collar_coords() + \
                   serialize_segments()
        else:
            return serialize_station_coords()

    def serialize_notes(self, pem_file):
        results = []
        if not pem_file.notes:
            return ''
        else:
            for line in pem_file.notes:
                if line not in results:
                    results.append(line)
        return '\n'.join(results) + '\n'

    def serialize_header(self, pem_file):

        def get_channel_times(table):
            times = []
            # Add all the start times
            table.Start.map(times.append)
            # Add the first 'End' since it's the only value not repeated as a start
            times.insert(1, table.iloc[0].End)
            # Add the last end-time
            times.append(table.iloc[-1].End)
            return times

        result_list = [str(pem_file.client),
                       str(pem_file.grid),
                       str(pem_file.line_name),
                       str(pem_file.loop_name),
                       str(pem_file.date),
                       ' '.join([str(pem_file.survey_type),
                                 str(pem_file.convention),
                                 str(pem_file.sync),
                                 str(pem_file.timebase),
                                 str(int(pem_file.ramp)),
                                 str(pem_file.number_of_channels),
                                 str(pem_file.number_of_readings)]),
                       ' '.join([str(pem_file.rx_number),
                                 str(pem_file.rx_software_version),
                                 str(pem_file.rx_software_version_date),
                                 str(pem_file.rx_file_name),
                                 str(pem_file.normalized),
                                 str(pem_file.primary_field_value),
                                 str(pem_file.coil_area)])]

        if pem_file.loop_polarity is not None:
            result_list[-1] += ' ' + pem_file.loop_polarity

        result = '\n'.join(result_list) + '\n\n'

        times_per_line = 7
        cnt = 0

        times = get_channel_times(pem_file.channel_times)
        channel_times = [f'{time:9.6f}' for time in times]

        for i in range(0, len(channel_times), times_per_line):
            line_times = channel_times[i:i+times_per_line]
            result += ' '.join([str(time) for time in line_times]) + '\n'
            cnt += 1

        result += '$\n'
        return result

    def serialize_data(self, pem_file):
        df = pem_file.get_data(sorted=True)

        def serialize_reading(reading):
            result = ' '.join([reading['Station'],
                               reading['Component'] + 'R' + str(reading['Reading index']),
                               str(reading['Gain']),
                               reading['Rx type'],
                               str(reading['ZTS']),
                               str(reading['Coil delay']),
                               str(reading['Number of stacks']),
                               str(reading['Readings per set']),
                               str(reading['Reading number'])]) + '\n'
            rad = []
            for r in reading['RAD tool'].to_list()[:-1]:
                if isinstance(r, float):
                    rad.append(f"{r:g}")
                else:
                    rad.append(r)
            result += ' '.join(rad) + '\n'

            readings_per_line = 7
            reading_spacing = 12
            count = 0

            channel_readings = [f'{r:<8g}' for r in reading['Reading']]

            for i in range(0, len(channel_readings), readings_per_line):
                readings = channel_readings[i:i + readings_per_line]
                result += ' '.join([str(r) + max(0, reading_spacing - len(r))*' ' for r in readings]) + '\n'
                count += 1

            return result + '\n'

        return ''.join(df.apply(serialize_reading, axis=1))

    def serialize(self, pem_file):
        """
        Create a string of a PEM file to be printed to a text file.
        :param pem_file: PEM_File object
        :return: A string in PEM file format containing the data found inside of pem_file
        """
        result = self.serialize_tags(pem_file) + \
                 self.serialize_loop_coords(pem_file) + \
                 self.serialize_line_coords(pem_file) + \
                 self.serialize_notes(pem_file) + '~\n' + \
                 self.serialize_header(pem_file) + \
                 self.serialize_data(pem_file)

        return result
