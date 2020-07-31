import re
import pandas as pd
import numpy as np
from src.gps.gps_editor import BoreholeSegments


class Segmenter:
    def __init__(self):
        pass

    @staticmethod
    def dad_to_seg(df, units='m'):
        """
        Create a segment data frame from a DAD data frame
        :param df: pandas DataFrame with Depth, Azimuth, Dip columns
        :return: pandas DataFrame with Azimuth, Dip, segment length, unit, and depth columns
        """
        units = 2 if units == 'm' else 0

        # Create the segment data frame
        seg = df.head(0).copy()
        depth_count, az_count, dip_count = 0, 0, 0

        # Calculate the iterative differences in depth, azimuth, and dip going down the hole
        depth_diff = df.Depth.diff().dropna()
        az_diff = df.Azimuth.diff().dropna()
        dip_diff = df.Dip.diff().dropna()

        # Start a counter for each attribute. When the threshold for any attribute is met, append current df row
        for i, (depth, az, dip) in enumerate(list(zip(depth_diff, az_diff, dip_diff))):
            depth_count += abs(depth)
            az_count += abs(az)
            dip_count += abs(dip)
            if any([depth_count >= 10, az_count >= 1., dip_count >= 1.]):
                seg = seg.append(df.iloc[i + 1])
                # Reset the counters
                depth_count, az_count, dip_count = 0, 0, 0

        # Add the last segment if it isn't there from the iterative calculations
        if seg.tail(1).Depth.iloc[0] != df.tail(1).Depth.iloc[0]:
            seg = seg.append(df.iloc[-1])

        seg_length = seg.Depth.diff()
        seg_length.iloc[0] = seg.Depth.iloc[0]
        seg['Segment_length'] = seg_length
        seg['Unit'] = units

        # Re-arrange the columns
        depths = seg.pop('Depth')
        seg.insert(4, 'Depth', depths)
        seg.reset_index(inplace=True, drop=True)

        return BoreholeSegments(seg)

# class SegmentCalculator:
#     """
#     Create a segment file out of a DAD file. The file must have the first three columns be Depth, then Azimuth, then Dip.
#     File can be Excel, CSV, or Text
#     """
#
#     def parse_file(self, filepath=None):
#
#         def open_text(filepath=None):
#
#             depths = []
#             azimuths = []
#             dips = []
#
#             with open(filepath, 'r', encoding='utf-8-sig') as file:
#                 data = file.readlines()
#
#             for row in data:
#                 s_row = re.split('[\s\t,]+', row)
#                 depths.append(float(s_row[0]))
#                 azimuths.append(float(s_row[1]))
#                 dips.append(float(s_row[2]))
#
#             return depths, azimuths, dips
#
#         def open_spreadsheet(filepath=None, excel=False):
#             if excel is True:
#                 data = pd.read_excel(filepath)
#             else:
#                 data = pd.read_csv(filepath)
#             depths = data.iloc[:, 0]
#             azimuths = data.iloc[:, 1]
#             dips = data.iloc[:, 2]
#
#             return depths, azimuths, dips
#
#         if filepath.endswith('xlsx') or filepath.endswith('xls'):
#             depths, azimuths, dips = open_spreadsheet(filepath, excel=True)
#         elif filepath.endswith('csv'):
#             depths, azimuths, dips = open_spreadsheet(filepath, excel=False)
#         elif filepath.endswith('dad'):
#             depths, azimuths, dips = open_text(filepath)
#
#         return depths, azimuths, dips
#
#     def get_segments(self, filepath, seg_interval=10):
#         """
#         Create a segments file from a DAD file.
#         :param filepath: Filepath of the DAD file in either text, excel, or CSV format.
#         :return: Segments data
#         """
#         depths, azimuths, dips = self.parse_file(filepath)
#         if all([depths, azimuths, dips]):
#             seg_len = 1
#             # Segment everything into 1m long pieces and interpolate.
#             interp_depths = np.arange(0, depths[-1], seg_len)
#             interp_az = np.interp(interp_depths, depths, azimuths)
#             interp_dips = np.interp(interp_depths, depths, dips)
#
#             seg_depths = np.arange(interp_depths[0], interp_depths[-1]+1, seg_interval)
#             indexes = [list(interp_depths).index(depth) for depth in seg_depths]
#             seg_az = [interp_az[index] for index in indexes]
#             seg_dips = [interp_dips[index] for index in indexes]
#             seg_lengths = [seg_depths[1]-seg_depths[0]]+list(map(lambda x,y: y-x, seg_depths[0:-1], seg_depths[1:]))
#
#             self.save_seg_file(seg_depths, seg_az, seg_dips, seg_lengths)
#             return seg_depths, seg_az, seg_dips, seg_lengths
#
#     def save_seg_file(self, depths, azimuths, dips, seg_lengths):
#         segments = ""
#
#         for depth, az, dip, seg_len in zip(depths, azimuths, dips, seg_lengths):
#             row = f"{az:.2f} {-dip:.2f} {seg_len:.1f} 2 {depth}\n"
#             segments += row
#
#         print(segments, file=open(r'C:\Users\Eric\PycharmProjects\Crone\sample_files\PEMGetter files\_TEST SEG.SEG', 'w+'))


if __name__ == '__main__':
    # filepath = r'C:\_Data\2019\Eastern\Osisko\Planning\OM19-7443-01\gyro.xlsx'
    filepath = r'C:\Users\Eric\PycharmProjects\Crone\sample_files\PEMGetter files\tool.dad'
    # c = SegmentCalculator()
    # c.get_segments(filepath)
