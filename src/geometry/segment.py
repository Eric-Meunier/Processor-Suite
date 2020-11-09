from src.gps.gps_editor import BoreholeSegments
import logging
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class Segmenter:

    def __init__(self):
        pass

    @staticmethod
    def dad_to_seg(df, units='m'):
        """
        Create a segment data frame from a DAD data frame. DAD data is split into 1m intervals.
        :param df: pandas DataFrame with Depth, Azimuth, Dip columns
        :param units: str, units of the segments, either 'm' or 'ft'
        :return: pandas DataFrame with Azimuth, Dip, segment length, unit, and depth columns
        """
        if units == 'm':
            units = 2
        elif units == 'ft':
            units = 0
        else:
            raise NotImplemented(f"{units} is not implemented as a unit for segments.")

        # Interpolate the DAD to 1m segments
        depth = df.Depth.to_numpy()
        azimuth = df.Azimuth.to_numpy()
        dip = df.Dip.to_numpy()

        i_depth = np.arange(depth[0], depth[-1] + 1)
        i_azimuth = np.interp(i_depth, depth, azimuth)
        i_dip = np.interp(i_depth, depth, dip)
        df = pd.DataFrame(zip(i_depth, i_azimuth, i_dip), columns=df.columns)

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
        seg = seg.round(2)

        return BoreholeSegments(seg)


if __name__ == '__main__':
    # filepath = r'C:\_Data\2019\Eastern\Osisko\Planning\OM19-7443-01\gyro.xlsx'
    filepath = r'C:\Users\Eric\PycharmProjects\Crone\sample_files\PEMGetter files\tool.dad'
    # c = SegmentCalculator()
    # c.get_segments(filepath)
