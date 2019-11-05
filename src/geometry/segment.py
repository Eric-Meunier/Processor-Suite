import re
import pandas as pd
import numpy as np

class SegmentCalculator:
    """
    Create a segment file out of a DAD file. The file must have the first three columns be Depth, then Azimuth, then Dip.
    File can be Excel, CSV, or Text
    """

    def parse_file(self, filepath=None):

        def open_text(filepath=None):

            depths = []
            azimuths = []
            dips = []

            with open(filepath, 'r', encoding='utf-8-sig') as file:
                data = file.readlines()

            for row in data:
                s_row = re.split('[\s\t,]+', row)
                depths.append(float(s_row[0]))
                azimuths.append(float(s_row[1]))
                dips.append(float(s_row[2]))

            return depths, azimuths, dips

        def open_spreadsheet(filepath=None, excel=False):
            if excel is True:
                data = pd.read_excel(filepath)
            else:
                data = pd.read_csv(filepath)
            depths = data.iloc[:, 0]
            azimuths = data.iloc[:, 1]
            dips = data.iloc[:, 2]

            return depths, azimuths, dips

        if filepath.endswith('xlsx') or filepath.endswith('xls'):
            depths, azimuths, dips = open_spreadsheet(filepath, excel=True)
        elif filepath.endswith('csv'):
            depths, azimuths, dips = open_spreadsheet(filepath, excel=False)
        elif filepath.endswith('dad'):
            depths, azimuths, dips = open_text(filepath)

        return depths, azimuths, dips

    def get_segments(self, filepath):
        """
        Create a segments file from a DAD file.
        :param filepath: Filepath of the DAD file in either text, excel, or CSV format.
        :return: Segments data
        """
        depths, azimuths, dips = self.parse_file(filepath)
        if all([depths, azimuths, dips]):
            seg_len = 1
            interp_depths = np.arange(0, depths[-1], seg_len)
            interp_az = np.interp(interp_depths, depths, azimuths)
            interp_dips = np.interp(interp_depths, depths, dips)

        self.save_seg_file(interp_depths, interp_az, interp_dips)
        return interp_depths, interp_az, interp_dips

    def save_seg_file(self, depths, azimuths, dips):
        segments = ""

        # for depth, az, dip in zip(interp_depths, interp_az, interp_dips):
        #     row = f"{az:.2f} {-dip:.2f} {seg_len:.1f} 2 {depth}\n"
        #     segments += row
        #
        # print(segments, file=open(r'N:\GeophysicsShare\Temp\_TEST SEG.SEG', 'w+'))
            # segments = []
            # for i, (depth, azimuth, dip) in enumerate(zip(depths, azimuths, dips)):
            #     depth = depth + sum(depths[0:i])
            #     azimuth = azimuth + sum(azimuths[0:i])
            #     dip = dip + sum(dips[0:i])
            #     segments.append([depth, azimuth, dip])


if __name__ == '__main__':
    # filepath = r'C:\_Data\2019\Eastern\Osisko\Planning\OM19-7443-01\gyro.xlsx'
    filepath = r'N:\GeophysicsShare\Temp\tool.dad'
    c = SegmentCalculator()
    c.get_segments(filepath)
