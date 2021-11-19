import copy
import logging
import math
import re
import os
from datetime import datetime
from pathlib import Path
from random import randrange, choices

import geomag
import natsort
import numpy as np
import pandas as pd
from pyproj import CRS
from scipy.spatial.transform import Rotation as R

from src.pem import convert_station
from src.gps.gps_editor import TransmitterLoop, SurveyLine, BoreholeCollar, BoreholeSegments, BoreholeGeometry
# from src.logger import Log
from src.mag_field.mag_field_calculator import MagneticFieldCalculator

logger = logging.getLogger(__name__)

pd.options.mode.chained_assignment = None  # default='warn'


def sort_data(data):
    # Sort the data frame
    df = data.reindex(index=natsort.order_by_index(
        data.index, natsort.index_humansorted(zip(data.Component,
                                                  data.Station,
                                                  data['Reading_index'],
                                                  data['Reading_number']))))
    # Reset the index
    df.reset_index(drop=True, inplace=True)
    return df


def get_split_table(table, units, ramp):
    """
    Return the channel table with Delete column filled out appropriately.
    :param table: DataFrame
    :param units: str, 'pT' or 'nT/s'
    :param ramp: float, ramp in microseconds
    :return: DataFrame
    """
    ramp = ramp * 1e-6
    for ind, row in table.iterrows():

        if row.Start > 0:
            remove = False
        else:
            if units == 'nT/s':
                if row.Start == -0.0002:
                    remove = False
                else:
                    remove = True
            # Keep the first channel that is before the start of the ramp for fluxgate surveys
            elif units == 'pT':
                if row.Start < -ramp and ind == 0:
                    remove = False
                else:
                    remove = True
            else:
                remove = True

        table.loc[ind, "Remove"] = remove
    return table


def process_angle(average_angle, angle):
    """
    Find the angle angle closest (by multiples of 360) to the average angle angle.
    :param average_angle: float
    :param angle: float
    :return: float
    """
    # print(f"Processing angle {angle:.2f} (avg. {average_angle:.2f}).")
    roll_minus = angle - 360
    roll_plus = angle + 360
    diff = abs(angle - average_angle)
    diff_minus = abs(roll_minus - average_angle)
    diff_plus = abs(roll_plus - average_angle)
    # print(f"Diff, diff_minus, diff_plus: {', '.join([str(round(diff, 2)), str(round(diff_minus, 2)), str(round(diff_plus, 2))])}.")
    if all(diff_minus < [diff, diff_plus]):
        if diff_minus > 300:
            roll_minus = roll_minus - 360
        # print(f"Going with {diff_minus:.2f}")
        # print(F"Returning new angle {roll_minus:.2f}\n")
        return roll_minus
    elif all(diff_plus < [diff, diff_minus]):
        if diff_plus > 300:
            roll_plus = roll_plus + 360
        # print(f"Going with {diff_plus:.2f}")
        # print(F"Returning new angle {roll_plus:.2f}\n")
        return roll_plus
    else:
        # print(f"Going with {diff:.2f}")
        # print(f"Returning angle {angle:.2f}\n")
        return angle


class StepFile:
    """
    Step file class
    """
    def __init__(self):
        self.format = None
        self.units = None
        self.operator = None
        self.probes = None
        self.current = None
        self.loop_dimensions = None
        self.client = None
        self.grid = None
        self.line_name = None
        self.loop_name = None
        self.date = None
        self.survey_type = None
        self.convention = None
        self.sync = None
        self.timebase = None
        self.ramp = None
        self.number_of_channels = None
        self.number_of_readings = None
        self.rx_number = None
        self.rx_software_version = None
        self.rx_software_version_date = None
        self.rx_file_name = None
        self.normalized = None
        self.primary_field_value = None
        self.coil_area = None
        self.loop_polarity = None
        self.channel_times = None

        self.notes = None
        self.data = None
        self.filepath = None

        self.loop = None
        self.collar = None
        self.segments = None
        # self.geometry = None
        self.line = None
        self.crs = None

        self.total_scale_factor = 0.
        self.soa = 0  # For XY SOA rotation
        self.pp_table = None  # PP de-rotation information
        self.prepped_for_rotation = False
        self.legacy = False

    def from_step(self, tags, loop_coords, line_coords, notes, header, channel_table, data, filepath=None):
        """
        Fill the information of the Step file object from a parsed .stp file.
        :param tags: dict, tags section of the Step file
        :param loop_coords: list, loop coordinates
        :param line_coords: list, line/hole geometry coordinates
        :param notes: list, notes section
        :param header: dict, header section
        :param channel_table: DataFrame of the channel times
        :param data: DataFrame of the data
        :param filepath: str, filepath of the file
        :return: StepFile object
        """
        self.format = tags.get('Format')
        self.units = tags.get('Units')
        self.operator = tags.get('Operator')
        self.probes = tags.get('Probes')
        self.soa = float(self.probes.get("SOA"))
        self.current = tags.get('Current')
        self.loop_dimensions = tags.get('Loop dimensions')

        self.client = header.get('Client')
        self.grid = header.get('Grid')
        self.line_name = header.get('Line_name')
        self.loop_name = header.get('Loop_name')
        self.date = header.get('Date')
        self.survey_type = header.get('Survey type')
        self.convention = header.get('Convention')
        self.sync = header.get('Sync')
        self.timebase = header.get('Timebase')
        self.ramp = header.get('Ramp')
        # self.number_of_channels = header.get('Number of channels')
        self.number_of_readings = header.get('Number of readings')
        self.rx_number = header.get('Receiver number')
        self.rx_software_version = header.get('Rx software version')
        self.rx_software_version_date = header.get('Rx software version date')
        self.rx_file_name = header.get('Rx file name')
        self.normalized = header.get('Normalized')
        self.primary_field_value = header.get('Primary field value')
        self.coil_area = header.get('Coil area')
        self.loop_polarity = header.get('Loop polarity')
        self.channel_times = channel_table
        self.number_of_channels = len(channel_table)

        self.notes = notes

        self.data = sort_data(data)
        # Add the deletion flag column
        if 'Deleted' not in self.data.columns:
            self.data.insert(13, 'Deleted', False)
            self.legacy = True

        # Add the overload column
        if 'Overload' not in self.data.columns:
            self.data.insert(14, 'Overload', False)

        # Add the Timestamp column
        if 'Timestamp' not in self.data.columns:
            self.data.insert(15, 'Timestamp', None)

        self.filepath = Path(filepath)

        self.crs = self.get_crs()
        self.loop = TransmitterLoop(loop_coords, crs=self.crs)
        if self.is_borehole():
            self.collar = BoreholeCollar([line_coords[0]], crs=self.crs)
            self.segments = BoreholeSegments(line_coords[1:])
            # self.geometry = BoreholeGeometry(self.collar, self.segments)
        else:
            self.line = SurveyLine(line_coords, crs=self.crs)

        return self

    def is_borehole(self):
        if 'borehole' in self.get_survey_type().lower():
            return True
        else:
            return False

    def is_fluxgate(self):
        if 'fluxgate' in self.get_survey_type().lower() or 'squid' in self.get_survey_type().lower():
            return True
        else:
            return False

    def is_xy(self):
        """
        If the survey is an induction XY probe survey
        :return: bool
        """
        if not self.is_borehole or self.is_fluxgate():
            return False
        else:
            components = self.data.Component.unique()
            if len(components) == 2:
                if 'X' in components and 'Y' in components:
                    return True
                else:
                    return False
            else:
                return False

    def is_z(self):
        """
        If the survey is an induction Z probe survey
        :return: bool
        """
        if not self.is_borehole or self.is_fluxgate():
            return False
        else:
            components = self.data.Component.unique()
            if len(components) == 1:
                if 'Z' in components:
                    return True
                else:
                    return False
            else:
                return False

    def is_derotated(self):
        if self.is_borehole():
            filt = (self.data.Component == 'X') | (self.data.Component == 'Y')
            xy_data = self.data[filt]
            return xy_data['RAD_tool'].map(lambda x: x.derotated).all()
        else:
            return False

    def is_averaged(self):
        data = self.data[['Station', 'Component']]
        if any(data.duplicated()):
            return False
        else:
            return True

    def is_split(self):
        if self.channel_times.Remove.any():
            return False
        else:
            return True

    def is_pp(self):
        if self.channel_times.Width.max() < 10 ** -4:
            return True
        else:
            return False

    def is_mmr(self):
        # This is hacky as hell but currently our RX dumps the BH files as type BH-Flux so we just hope the
        # operator puts mmr or dipole somewhere in the loop name
        # TODO We need a fileheader survey type for MMR
        return 'mmr' in self.loop_name.casefold() or 'dipole' in self.loop_name.casefold()

    def has_collar_gps(self):
        if self.is_borehole():
            if not self.collar.df.dropna().empty and all(self.collar.df):
                return True
            else:
                return False
        else:
            return False

    def has_geometry(self):
        if self.is_borehole():
            if not self.segments.df.dropna().empty and all(self.segments.df):
                return True
            else:
                return False
        else:
            return False

    def has_loop_gps(self):
        if not self.loop.df.dropna().empty and all(self.loop.df):
            return True
        else:
            return False

    def has_station_gps(self):
        if not self.is_borehole():
            if not self.line.df.dropna().empty and all(self.line.df):
                return True
            else:
                return False
        else:
            return False

    def has_any_gps(self):
        if any([self.has_collar_gps(), self.has_geometry(), self.has_station_gps(), self.has_loop_gps()]):
            return True
        else:
            return False

    def has_all_gps(self):
        if self.is_borehole():
            if not all([self.has_loop_gps(), self.has_collar_gps(), self.has_geometry()]):
                return False
            else:
                return True
        else:
            if not all([self.has_loop_gps(), self.has_station_gps()]):
                return False
            else:
                return True

    def has_d7(self):
        return self.data.RAD_tool.map(lambda x: x.D == 'D7').all()

    def has_xy(self):
        components = self.get_components()
        if 'X' in components and 'Y' in components:
            return True
        else:
            return False

    def get_gps_units(self):
        """
        Return the type of units being used for GPS ('m' or 'ft')
        :return: str
        """
        unit = None
        if self.has_loop_gps():
            unit = self.loop.get_units()
        elif self.has_collar_gps():
            unit = self.collar.get_units()
        elif self.has_station_gps():
            unit = self.line.get_units()

        return unit

    def get_gps_warnings(self):
        """
        Return all the GPS warnings from the SurveyLine (if applicable) and TansmitterLoop objects.
        :return: Dict
        """
        if self.is_borehole():
            line_warnings = {}
        else:
            line_warnings = self.line.get_warnings(stations=self.get_stations(converted=True))
        loop_warnings = self.loop.get_warnings()
        return {"Line Warnings": line_warnings, "Loop Warnings": loop_warnings}

    def get_number_gps_warnings(self):
        """
        Return the number of GPS warnings in the SurveyLine (if applicable) and TansmitterLoop objects.
        :return: int
        """
        count = 0
        for gps_object, object_warnings in self.get_gps_warnings().items():
            for type, warnings in object_warnings.items():
                count += len(warnings)

        return count

    def get_crs(self):
        """
        Return the StepFile's CRS, or create one from the note in the Step file if it exists.
        :return: Proj CRS object
        """

        if self.crs:
            return self.crs

        else:
            for note in self.notes:
                if 'EPSG' in note:
                    epsg_code = re.search(r"EPSG:(\d+)", note.strip()).group(1)
                    crs = CRS.from_epsg(epsg_code)
                    logger.info(f"{self.filepath.name} CRS is {crs.name}.")
                    return crs
                elif '<CRS>' in note:
                    crs_str = re.split('<CRS>', note)[-1].strip()
                    crs = CRS.from_string(crs_str)
                    logger.info(f"{self.filepath.name} CRS is {crs.name}.")
                    return crs
                # For older Step files that used the <GEN> tag
                elif 'CRS:' in note:
                    crs_str = re.split('CRS: ', note)[-1]
                    s = crs_str.split()

                    system = s[0]
                    if system == 'Lat/Lon':
                        epsg_code = '4326'
                    else:
                        zone_number = s[2]
                        north = True if s[3].strip(',') == 'North' else False
                        datum = f"{s[4]} {s[5]}"

                        if datum == 'WGS 1984':
                            if north:
                                epsg_code = f'326{zone_number}'
                            else:
                                epsg_code = f'327{zone_number}'
                        elif datum == 'NAD 1927':
                            epsg_code = f'267{zone_number}'
                        elif datum == 'NAD 1983':
                            epsg_code = f'269{zone_number}'
                        else:
                            logger.error(f"{datum} CRS string not implemented.")
                            return None

                    crs = CRS.from_epsg(epsg_code)
                    logger.info(f"{self.filepath.name} CRS is {crs.name}")
                    return crs

    def get_loop_gps(self, sorted=False, closed=False):
        return self.loop.get_loop_gps(sorted=sorted, closed=closed)

    def get_line_gps(self, sorted=False):
        return self.line.get_line_gps(sorted=sorted)

    def get_collar_gps(self):
        return self.collar.get_collar_gps()

    def get_segments(self):
        return self.segments.get_segments()

    def get_geometry(self):
        return BoreholeGeometry(self.collar, self.segments)

    def get_notes(self):
        return self.notes

    def get_data(self, sorted=False):
        if sorted:
            data = sort_data(self.data)
        else:
            data = self.data
        return data

    def get_dad(self):
        """
        Return the DAD of a borehole file. Will use the segments if available, other will use the RAD for XY files.
        :return: Dataframe
        """
        assert self.is_borehole(), f"Can only get DAD from borehole surveys."
        assert any([self.has_xy(), self.has_geometry()]), f"File must either have geometry or be an XY file."

        if self.has_geometry():
            # Create the DAD from the geometry
            seg = self.segments.df

            # Interpolate the data to 1m segment lengths and starting from depth 0
            xi = np.arange(0, seg.Depth.max() + 1, 1)
            i_az = np.interp(xi, seg.Depth, seg.Azimuth)
            i_dip = np.interp(xi, seg.Depth, seg.Dip)
        else:
            # Create the DAD from the RAD Tool data
            data = self.data.drop_duplicates(subset='Station')
            depths = data.loc[:, "Station"].astype(int)
            azimuths = data.RAD_tool.apply(lambda x: x.get_azimuth()).astype(float)
            dips = data.RAD_tool.apply(lambda x: x.get_dip()).astype(float)

            xi = np.arange(0, depths.max() + 1, 1)
            i_az = np.interp(xi, depths, azimuths)
            i_dip = np.interp(xi, depths, dips)

        return pd.DataFrame({'Depth': xi, 'Azimuth': i_az, 'Dip': i_dip})

    def get_date(self):
        return datetime.strptime(self.date, (r'%B %d, %Y'))

    def get_mag(self, average=False):
        """
        Return the magnetic field strength profile of a borehole file.
        :return: Dataframe
        :param average: Bool, return the average per each station
        """
        assert self.is_borehole(), f"Can only get magnetic field strength data from borehole surveys."
        assert any([self.has_xy(), self.has_geometry()]), f"File must either have geometry or be an XY file."

        df = self.data.drop_duplicates(subset="RAD_ID").loc[:, ["Station", "RAD_tool"]]
        df.Station = df.Station.astype(float)
        mag = df.RAD_tool.apply(lambda x: x.get_mag())
        df = df.assign(Mag=mag)
        if average is True:
            df = df.groupby('Station', as_index=False).mean()

        df = df.sort_values("Station")
        return df.dropna()

    def get_azimuth(self, average=False):
        """
        Return the measured azimuth values of a borehole file.
        :return: DataFrame
        :param average: Bool, return the average per each station
        """
        assert all([self.has_xy(), self.is_borehole()]), f"Can only get azimuth data from borehole XY surveys."

        data = self.data[(self.data.Component == "X") | (self.data.Component == "Y")]
        data = data.drop_duplicates(subset="RAD_ID")
        data.Station = data.Station.astype(float)
        data.sort_values("Station", inplace=True)
        azimuth_data = data.RAD_tool.map(lambda x: x.get_azimuth())

        # The first azimuth is used as the first "average"
        processed_azimuth_data = np.array([azimuth_data[0]])
        for azimuth in azimuth_data[1:]:
            processed_azimuth = process_angle(np.mean(processed_azimuth_data), azimuth)
            processed_azimuth_data = np.append(processed_azimuth_data, processed_azimuth)

        while all([r < 0 for r in processed_azimuth_data]):
            processed_azimuth_data = np.array(processed_azimuth_data) + 360

        df = pd.DataFrame.from_dict({"Angle": processed_azimuth_data, "Station": data.Station})
        if average is True:
            df = df.groupby("Station", as_index=False).mean()

        return df

    def get_dip(self, average=False):
        """
        Return the measured dip values of a borehole file.
        :return: DataFrame
        :param average: Bool, return the average per each station
        """
        assert all(
            [self.has_xy(), self.is_borehole()]), f"Can only get dip data from borehole surveys with XY components."

        df = self.data.drop_duplicates(subset="RAD_ID").loc[:, ["Station", "RAD_tool"]]
        df.Station = df.Station.astype(float)
        dip = df.RAD_tool.apply(lambda x: x.get_dip())
        df = df.assign(Dip=dip)
        if average is True:
            df = df.groupby('Station', as_index=False).mean()

        df = df.sort_values("Station")
        return df.dropna()

    def get_roll_data(self, roll_type, soa=0):

        if not self.prepped_for_rotation:
            raise ValueError(F"StepFile must be prepped for de-rotation.")

        if not all([self.has_xy(), self.is_borehole()]):
            raise ValueError(F"StepFile must be a borehole file with X and Y component readings.")

        data = self.data[(self.data.Component == "X") | (self.data.Component == "Y")]
        data = data.drop_duplicates(subset="RAD_ID")
        data.Station = data.Station.astype(float)
        data.sort_values("Station", inplace=True)

        if roll_type == "Acc":
            roll_data = data.RAD_tool.map(lambda x: x.acc_roll_angle + soa).to_numpy()
        elif roll_type == "Mag":
            roll_data = data.RAD_tool.map(lambda x: x.mag_roll_angle + soa).to_numpy()
        elif roll_type == "Tool":
            roll_data = data.RAD_tool.map(lambda x: x.angle_used + soa).to_numpy()
        elif roll_type == "Measured_PP":
            if not self.has_all_gps():
                raise ValueError(f"StepFile must have all GPS for {roll_type} de-rotation.")
            roll_data = data.RAD_tool.map(lambda x: x.measured_pp_roll_angle).to_numpy()
        elif roll_type == "Cleaned_PP":
            if not self.has_all_gps():
                raise ValueError(f"StepFile must have all GPS for {roll_type} de-rotation.")
            roll_data = data.RAD_tool.map(lambda x: x.cleaned_pp_roll_angle).to_numpy()
        else:
            raise ValueError(f"{roll_type} is not a valid de-rotation method.")

        # The first roll angle is used as the first "average"
        processed_roll_data = np.array([roll_data[0]])
        for roll in roll_data[1:]:
            processed_roll = process_angle(processed_roll_data[-1], roll)  # Works better than using average
            # processed_roll = process_angle(np.mean(processed_roll_data), roll)
            processed_roll_data = np.append(processed_roll_data, processed_roll)

        while all([r < 0 for r in processed_roll_data]):
            processed_roll_data = np.array(processed_roll_data) + 360

        df = pd.DataFrame.from_dict({"Angle": processed_roll_data, "Station": data.Station})
        return df

    def get_soa(self):
        return self.probes.get("SOA")

    def get_channel_bounds(self):
        """
        Create tuples of start and end channels to be plotted per axes for LIN plots
        :return: list of tuples, first item of tuple is the axes, second is the start and end channel for that axes
        """
        channel_bounds = [None] * 4

        # Only plot off-time channels
        number_of_channels = len(self.channel_times[~self.channel_times.Remove.astype(bool)])

        num_channels_per_plot = int((number_of_channels - 1) // 4)
        remainder_channels = int((number_of_channels - 1) % 4)

        for k in range(0, len(channel_bounds)):
            channel_bounds[k] = (k * num_channels_per_plot + 1, num_channels_per_plot * (k + 1))

        for i in range(0, remainder_channels):
            channel_bounds[i] = (channel_bounds[i][0], (channel_bounds[i][1] + 1))
            for k in range(i + 1, len(channel_bounds)):
                channel_bounds[k] = (channel_bounds[k][0] + 1, channel_bounds[k][1] + 1)

        channel_bounds.insert(0, (0, 0))
        logger.debug(f"{self.filepath.name} has {number_of_channels} channels. LIN plots binned as {channel_bounds}.")

        return channel_bounds

    def get_number_of_channels(self, incl_ontime=True):
        if incl_ontime is True:
            return len(self.channel_times)
        else:
            return len(self.channel_times[~self.channel_times.Remove.astype(bool)])

    def get_profile_data(self, component, averaged=False, converted=False, ontime=True, incl_deleted=False):
        """
        Transform the readings in the data in a manner to be plotted as a profile
        :param component: str, used to filter the profile data and only keep the given component
        :param averaged: bool, average the readings of the profile
        :param converted: bool, convert the station names to int
        :param ontime: bool, keep the on-time channels
        :param incl_deleted: bool, include readings that are flagged as deleted
        :return: pandas DataFrame object with Station as the index, and channels as columns.
        """
        comp_filt = self.data['Component'] == component.upper()
        data = self.data[comp_filt]

        if not incl_deleted:
            data = data[~data.Deleted.astype(bool)]

        if ontime is False:
            data.Reading = data.Reading.map(lambda x: x[~self.channel_times.Remove.astype(bool)])

        profile = pd.DataFrame.from_dict(dict(zip(data.Reading.index, data.Reading.values))).T

        if converted is True:
            stations = data.Station.map(convert_station)
        else:
            stations = data.Station

        profile.insert(0, 'Station', stations)
        profile.set_index('Station', drop=True, inplace=True)

        if averaged is True:
            profile = profile.groupby('Station').mean()

        # Sort the data frame to prevent issues with plotting
        profile.sort_index(inplace=True)
        return profile

    def get_contour_data(self):
        """
        Create a data frame which includes GPS position and columns for each channel.
        :return: DataFrame object
        """
        logger.debug(F"Retrieving contour data for {self.filepath.name}.")

        def add_gps(row):
            """Add the GPS for a given station"""
            gps = line_gps[line_gps.Station == row.Station]
            if not gps.empty:
                row.Easting = gps.Easting.values[0]
                row.Northing = gps.Northing.values[0]
                row.Elevation = gps.Elevation.values[0]
            return row

        def get_tf(row):

            def calculate_tf(col):
                return math.sqrt(sum(col ** 2))

            channels = range(0, self.number_of_channels)
            tf = row.loc[:, channels].apply(calculate_tf).to_numpy()
            tf_row = row.iloc[0].copy().to_frame().T
            tf_row.Component = 'TF'
            tf_row.loc[:, channels] = tf
            return tf_row

        line_gps = self.get_line_gps()
        # Filter the GPS to only keep those that are in the data
        line_gps = line_gps[line_gps.Station.isin(self.get_stations(converted=True))]

        if line_gps.empty:
            logger.warning(f"Skipping {self.filepath.name} because it has no line GPS.")
            return pd.DataFrame()

        readings = pd.DataFrame.from_dict(
            dict(zip(self.data.loc[:, "Reading"].index, self.data.loc[:, "Reading"].values))).T
        data = pd.concat([self.data.loc[:, ["Station", "Component"]], readings], axis=1)
        data.Station = data.Station.map(convert_station)
        data["Line"] = self.line_name
        data["Easting"] = None
        data["Northing"] = None
        data["Elevation"] = None

        data = data.apply(add_gps, axis=1)
        tf = data.groupby("Station").apply(get_tf)
        data = data.append(tf).dropna().reset_index(drop=True)
        return data

    def get_file_name(self, suffix=True):
        """
        Return the name of the StepFile's file.
        :param suffix: Bool, include the extension or not.
        :return: str
        """
        if suffix is True:
            return self.filepath.name
        else:
            return self.filepath.stem

    def get_components(self):
        components = list(self.data['Component'].unique())
        return components

    def get_stations(self, component=None, converted=False, incl_deleted=True):
        """
        Return a list of unique stations in the Step file.
        :param component: str, only count stations for the given component. 'None' will consider all components.
        :param converted: bool, whether to convert the stations to Int.
        :param incl_deleted: bool, whether include readings which are flagged for deletion.
        :return: list
        """
        if incl_deleted:
            data = self.data.copy()
        else:
            data = self.data[~self.data.Deleted.astype(bool)].copy()

        if component is not None:
            data = data[data.Component == component.upper()]

        stations = data.Station.unique()
        if converted:
            stations = [convert_station(station) for station in stations]

        return np.array(natsort.os_sorted(stations))

    def get_gps_extents(self):
        """
        Return the minimum and maximum of each dimension of the GPS in the file
        :return: tuple of float, xmin, xmax, ymin, ymax, zmin, zmax
        """
        loop = self.get_loop_gps()

        if self.is_borehole() and self.has_collar_gps():
            collar = self.get_collar_gps()
            segments = self.get_segments()

            if not segments.empty:
                line = BoreholeGeometry(collar, segments).get_projection()
            else:
                line = collar
        else:
            line = self.get_line_gps()

        east = pd.concat([loop.Easting, line.Easting])
        north = pd.concat([loop.Northing, line.Northing])
        elev = pd.concat([loop.Elevation, line.Elevation])

        xmin, xmax, ymin, ymax, zmin, zmax = east.min(), east.max(), north.min(), north.max(), elev.min(), elev.max()
        return xmin, xmax, ymin, ymax, zmin, zmax

    def get_mag_dec(self):
        """
        Calculate the magnetic declination for the Step file.
        """
        crs = self.get_crs()
        if not crs:
            logger.info(f'{self.filepath.name} No CRS.')
            return

        if self.has_collar_gps():
            coords = self.collar
        elif self.has_loop_gps():
            coords = self.loop
        elif self.has_station_gps():
            coords = self.line
        else:
            logger.error(f'No GPS in {self.filepath.name}')
            return

        assert not coords.df.empty, f"GPS data frame of {self.filepath.name} is empty."
        coords = copy.deepcopy(coords)

        coords.crs = crs
        coords = coords.to_latlon().df
        lat, lon, elevation = coords.iloc[0]['Northing'], coords.iloc[0]['Easting'], coords.iloc[0]['Elevation']

        gm = geomag.geomag.GeoMag()
        mag = gm.GeoMag(lat, lon, elevation)
        return mag

    def get_survey_type(self):
        """
        Return the survey type in title format
        :return: str
        """
        file_survey_type = re.sub(r'\s+', '_', self.survey_type.casefold())

        if any(['s-coil' in file_survey_type,
                'surface' in file_survey_type,
                'sf_coil' in file_survey_type]):
            survey_type = 'Surface Induction'

        elif any(['borehole' in file_survey_type,
                  'b-rad' in file_survey_type,
                  'b_rad' in file_survey_type,
                  'bh_rad' in file_survey_type,
                  'bh_xy_rad' in file_survey_type,
                  'bh_xy_fast_rad' in file_survey_type,
                  'otool' in file_survey_type,
                  'bh_z' in file_survey_type,
                  'bh_fast_rad' in file_survey_type,
                  'bh_z_probe' in file_survey_type,
                  'xy_magnum' in file_survey_type,
                  'radtool' in file_survey_type]):
            survey_type = 'Borehole Induction'

        elif any(['s-flux' in file_survey_type,
                  'sf_fluxgate' in file_survey_type]):
            survey_type = 'Surface Fluxgate'

        elif any(['bh-flux' in file_survey_type,
                  'bh_fast_fluxgate' in file_survey_type,
                  'bh_fluxgate' in file_survey_type]):
            survey_type = 'Borehole Fluxgate'

        elif any(['s-squid' in file_survey_type,
                  'sf_squid_3c' in file_survey_type,
                  'sf_squid' in file_survey_type]):
            survey_type = 'SQUID'

        else:
            raise ValueError(f"Invalid survey type: {file_survey_type}")

        return survey_type

    def get_repeats(self):
        """
        Return a mask of which stations may be repeat stations.
        :return: dataframe
        """

        def find_repeats(station):
            station_num = re.search('\d+', station).group()
            if station_num[-1] == '1' or station_num[-1] == '4' or station_num[-1] == '6' or station_num[-1] == '9':
                return True
            else:
                return False

        # Set the number of repeat stations
        repeat_mask = self.data.Station.map(find_repeats)
        repeat_data = self.data[repeat_mask]
        return repeat_data

    def get_suffix_mode(self):
        """
        Return the most common station suffix.
        :return: str
        """
        if self.is_borehole():
            return None

        matches = self.data.Station.map(lambda x: re.search(r'[NSEWnsew]', x))
        suffixes = matches.map(lambda x: x.group() if x else x)
        if not suffixes.any():
            logger.info(f"No suffixes found in {self.filepath.name}")
            return None

        mode = suffixes.mode()[0]
        return mode

    def get_suffix_warnings(self):
        """
        Return a data frame of the data whose station suffix is not the mode.
        :return: DataFrame
        """

        df = self.data.iloc[0:0].copy()

        if self.is_borehole():
            return df

        matches = self.data.Station.map(lambda x: re.search(r'[NSEWnsew]', x))
        suffixes = matches.map(lambda x: x.group() if x else x)
        if not suffixes.any():
            logger.info(f"No suffixes found in {self.filepath.name}")
            return df

        mode = suffixes.mode()[0]
        mask = suffixes != mode
        df = self.data[mask]
        return df

    def get_eligible_derotation_data(self):
        """
        Filter the data to only keep readings that have a matching X and Y pair for the same RAD_tool ID.
        :return: tuple, dataframe of eligible and dataframe of ineligible data.
        """
        def filter_data(group):
            """
            Flag the readings to be removed if the group doesn't have an X and Y pair.
            :param group: DataFrame, readings of the same station and same RAD tool ID
            :return: DataFrame
            """
            if group.Component.nunique() < 2:
                # Flag the readings to be removed
                group.Remove = True
            return group

        data = self.data.copy()

        # Add a 'Remove' column, which will be removed later. This way a data frame of ineligible data can be kept.
        data['Remove'] = False

        # Create a filter for X and Y data only
        xy_filt = (data.Component == 'X') | (data.Component == 'Y')

        # Remove groups that don't have X and Y pairs. For some reason couldn't make it work within rotate_data
        xy_data = data[xy_filt].groupby(['Station', 'RAD_ID'],
                                        group_keys=False,
                                        as_index=False).apply(lambda k: filter_data(k))

        eligible_data = xy_data[~xy_data.Remove.astype(bool)].drop(['Remove'], axis=1)
        ineligible_stations = xy_data[xy_data.Remove].drop(['Remove'], axis=1)
        logger.info(f"Data ineligible for de-rotation:\n"
                    f"{ineligible_stations.loc[:, ['Station', 'Reading_number', 'Reading_index']]}")
        return eligible_data, ineligible_stations

    def get_clipboard_info(self):
        """
        Copies the information of the StepFile to the clipboard for the purposes of filling out the geophysicssheet.
        """
        stations = self.get_stations(converted=True)
        survey_type = f"{self.get_survey_type()} {''.join(self.get_components())}"  # Differentiates Z and XY surveys
        info = [self.operator,  # Operator
                self.date,  # Date
                self.client,  # Client
                '',  # Helpers
                'Survey',  # Type of day
                '',  # Per diem
                '',  # Total hours worked
                self.grid,  # Grid
                self.loop_name,  # Loop name
                self.line_name,  # Line/Hole name
                stations.min(),  # Start
                stations.max(),  # End
                '',  # Complete?
                survey_type,  # Survey type
                '',  # Start time on drill
                '',  # Time leaving drill
                ', '.join(self.data.ZTS.astype(int).astype(str).unique()),  # ZTS
                self.timebase,  # Timebase
                '',  # Channel config.
                self.ramp,  # Ramp
                self.current,  # Current
                '',  # Damping box setting
                '',  # Tx config.
                self.rx_number,  # Receiver
                '',  # Clock
                self.probes["Probe number"] if self.is_z() else '',  # Z probe
                self.probes["Probe number"] if self.is_xy() else '',  # XY probe
                self.probes["Tool number"] if self.is_xy() else '',  # RAD tool
                '',  # RAD battery pack
                self.probes["Probe number"] if self.is_fluxgate() and self.is_borehole() else '',  # Fluxgate probe
                '',  # Fluxgate battery pack
                '',  # Borehole cable
                self.probes["Probe number"] if not self.is_borehole() and not self.is_fluxgate() else '',
                # Surface coil
                self.probes["Probe number"] if not self.is_borehole() and self.is_fluxgate() else '',
                # Surface fluxgate
                self.probes["Probe number"] if "squid" in self.survey_type.lower() else '',
                '',  # Slip ring
                '',  # Transmitter
                '',  # VRs
                '',  # Damping boxes
                ]

        return info

    def get_theory_pp(self):
        """
        Calculate the theoretical PP value for each station
        :return: DataFrame
        """
        if not self.has_all_gps():
            return pd.DataFrame()

        stations = list(self.get_stations(converted=True))
        pps = []
        borehole = self.is_borehole()
        loop = self.get_loop_gps(sorted=False, closed=False)
        mag_calc = MagneticFieldCalculator(loop, closed_loop=not self.is_mmr())
        # columns = ["Station"]
        # columns.extend(self.get_components())

        if borehole:
            segments = self.get_segments()
            dips = segments.Dip
            depths = segments.Depth
            azimuths = segments.Azimuth
            geometry = BoreholeGeometry(self.collar, self.segments)
            proj = geometry.get_projection(stations=stations)

            # Use the segment azimuth and dip of the next segment (as per Bill's cross)
            # Find the next station. If it's the last station, re-use the last station.
            for station in stations:
                station_ind = stations.index(station)
                convert_station(station)

                # Re-use the last station if it's the current index
                if stations.index(station) == len(stations) - 1:
                    next_station = station
                else:
                    next_station = stations[station_ind + 1]

                dip = np.interp(int(next_station), depths, dips)
                azimuth = np.interp(int(next_station), depths, azimuths)
                # Find the location in 3D space of the station
                filt = proj.loc[:, 'Relative_depth'] == float(station)
                x_pos, y_pos, z_pos = proj[filt].iloc[0]['Easting'], \
                                      proj[filt].iloc[0]['Northing'], \
                                      proj[filt].iloc[0]['Elevation']

                # Calculate the theoretical magnetic field strength of each component at that point (in nT/s)
                Tx, Ty, Tz = mag_calc.calc_total_field(x_pos, y_pos, z_pos,
                                                       amps=self.current,
                                                       out_units='nT/s',
                                                       ramp=self.ramp / 10 ** 6)
                # Rotate the theoretical values into the same frame of reference used with boreholes/surface lines
                rTx, rTy, rTz = R.from_euler('Z', -90, degrees=True).apply([Tx, Ty, Tz])

                # Rotate the theoretical values by the azimuth/dip
                r = R.from_euler('YZ', [90 - dip, azimuth], degrees=True)
                rT = r.apply([rTx, rTy, rTz])  # The rotated theoretical values
                pps.append([station, rT[0], rT[1], rT[2]])

        else:  # Surface survey
            azimuths = self.line.get_azimuths()

            for station in stations:
                station = convert_station(station)

                dip = 0
                azimuth = azimuths[azimuths.Station == station]
                if azimuth.empty:
                    logger.warning(f"{station} not in list of GPS stations")
                    continue
                azimuth = azimuth.iloc[0].Azimuth

                filt = self.line.df.loc[:, 'Station'] == float(station)
                x_pos, y_pos, z_pos = self.line.df[filt].iloc[0]['Easting'], \
                                      self.line.df[filt].iloc[0]['Northing'], \
                                      self.line.df[filt].iloc[0]['Elevation']

                # Calculate the theoretical magnetic field strength of each component at that point (in nT/s)
                Tx, Ty, Tz = mag_calc.calc_total_field(x_pos, y_pos, z_pos,
                                                       amps=self.current,
                                                       out_units='nT/s',
                                                       ramp=self.ramp / 10 ** 6)
                # Rotate the theoretical values into the same frame of reference used with boreholes/surface lines
                rTx, rTy, rTz = R.from_euler('Z', -90, degrees=True).apply([Tx, Ty, Tz])

                # Rotate the theoretical values by the azimuth/dip
                r = R.from_euler('YZ', [dip, azimuth], degrees=True)
                rT = r.apply([rTx, rTy, rTz])  # The rotated theoretical values
                pps.append([station, rT[0], rT[1], rT[2]])

        df = pd.DataFrame.from_records(pps, columns=["Station", "X", "Y", "Z"])
        return df

    def get_theory_data(self):
        """
        Calculate the theoretical value for each station at each channel time. Not currently used.
        :return: DataFrame
        """
        if not self.has_all_gps():
            return pd.DataFrame()

        stations = list(self.get_stations(converted=True))
        pps = []
        borehole = self.is_borehole()
        loop = self.get_loop_gps(sorted=False, closed=False)
        mag_calc = MagneticFieldCalculator(loop, closed_loop=not self.is_mmr())

        if borehole:
            segments = self.get_segments()
            dips = segments.Dip
            depths = segments.Depth
            azimuths = segments.Azimuth
            geometry = BoreholeGeometry(self.collar, self.segments)
            proj = geometry.get_projection(stations=stations)

            # Use the segment azimuth and dip of the next segment (as per Bill's cross)
            # Find the next station. If it's the last station, re-use the last station.
            for station in stations:
                station_ind = stations.index(station)
                convert_station(station)

                # Re-use the last station if it's the current index
                if stations.index(station) == len(stations) - 1:
                    next_station = station
                else:
                    next_station = stations[station_ind + 1]

                dip = np.interp(int(next_station), depths, dips)
                azimuth = np.interp(int(next_station), depths, azimuths)
                # Find the location in 3D space of the station
                filt = proj.loc[:, 'Relative_depth'] == float(station)
                x_pos, y_pos, z_pos = proj[filt].iloc[0]['Easting'], \
                                      proj[filt].iloc[0]['Northing'], \
                                      proj[filt].iloc[0]['Elevation']

                # Calculate the theoretical magnetic field strength of each component at that point (in nT/s)
                Tx, Ty, Tz = mag_calc.calc_total_field(x_pos, y_pos, z_pos,
                                                       amps=self.current,
                                                       out_units='nT/s',
                                                       ramp=self.ramp / 10 ** 6)
                # Rotate the theoretical values into the same frame of reference used with boreholes/surface lines
                rTx, rTy, rTz = R.from_euler('Z', -90, degrees=True).apply([Tx, Ty, Tz])

                # Rotate the theoretical values by the azimuth/dip
                r = R.from_euler('YZ', [90 - dip, azimuth], degrees=True)
                rT = r.apply([rTx, rTy, rTz])  # The rotated theoretical values
                pps.append([station, rT[0], rT[1], rT[2]])

                """
                # Theory calculations
                x_decay, y_decay, z_decay = mag_calc.get_decay(rT[0], rT[1], rT[2], self.channel_times.Center.to_numpy(),
                                                               tau=(self.timebase / 1000) * 1e-3)
                plt.yscale("symlog")
                plt.xscale("log")

                measured_decay = self.data.loc[(self.data.Station == f"{station}") & (self.data.Component == "Z")].Reading.mean()[1:]

                x = self.channel_times.Center.to_numpy()[1:]
                plt.plot(x, x_decay, "b--")
                plt.plot(x, measured_decay, "k")
                plt.show()
                """
        else:  # Surface survey
            azimuths = self.line.get_azimuths()

            for station in stations:
                station = convert_station(station)

                dip = 0
                azimuth = azimuths[azimuths.Station == station]
                if azimuth.empty:
                    logger.warning(f"{station} not in list of GPS stations")
                    continue
                azimuth = azimuth.iloc[0].Azimuth

                filt = self.line.df.loc[:, 'Station'] == float(station)
                x_pos, y_pos, z_pos = self.line.df[filt].iloc[0]['Easting'], \
                                      self.line.df[filt].iloc[0]['Northing'], \
                                      self.line.df[filt].iloc[0]['Elevation']

                # Calculate the theoretical magnetic field strength of each component at that point (in nT/s)
                Tx, Ty, Tz = mag_calc.calc_total_field(x_pos, y_pos, z_pos,
                                                       amps=self.current,
                                                       out_units='nT/s',
                                                       ramp=self.ramp / 10 ** 6)

                # Rotate the theoretical values into the same frame of reference used with boreholes/surface lines
                rTx, rTy, rTz = R.from_euler('Z', -90, degrees=True).apply([Tx, Ty, Tz])

                # Rotate the theoretical values by the azimuth/dip
                r = R.from_euler('YZ', [dip, azimuth], degrees=True)
                rT = r.apply([rTx, rTy, rTz])  # The rotated theoretical values
                pps.append([station, rT[0], rT[1], rT[2]])

                """
                # Theoretical decay calculations
                x_decay, y_decay, z_decay = mag_calc.get_decay(rT[0], rT[1], rT[2], self.channel_times.Center.to_numpy(),
                                                               tau=(self.timebase / 100) * 1e-3)
                # plt.yscale("symlog")
                # plt.xscale("log")

                measured_decay = self.data.loc[(self.data.Station == f"{station}N") & (self.data.Component == "X")].Reading.mean()[1:]

                x = self.channel_times.Center.to_numpy()[1:]
                plt.plot(x, x_decay, "b--")
                plt.plot(x, measured_decay, "k")
                plt.show()
                """

        df = pd.DataFrame.from_records(pps, columns=["Station", "X", "Y", "Z"])
        return df

    def get_reversed_components(self):
        """
        Return which components may have the polarity reserved. File must have all GPS information.
        :return: list of components
        """
        reversed_components = []
        theory_pp_data = self.get_theory_pp().set_index("Station", drop=True)
        # Find the PP channel
        pp_ch_num = self.channel_times[self.channel_times.Remove == False].iloc[0].name

        if not theory_pp_data.empty:
            for component in self.get_components():
                pp_data = self.get_profile_data(component,
                                                averaged=True,
                                                converted=True,
                                                ontime=True,
                                                incl_deleted=True).loc[:, pp_ch_num]

                # Only include common stations. PP represents the measured data, XYZ are theoretical.
                df = pd.concat([pp_data, theory_pp_data], axis=1).rename({pp_ch_num: 'PP'}, axis=1).dropna(axis=0)
                theory_pp = df.loc[:, component].to_numpy()
                pp = df.loc[:, 'PP'].to_numpy()

                diff = sum(np.abs(theory_pp - pp))
                reversed_diff = sum(np.abs(theory_pp - (pp * -1)))
                # print(f"Component: {component}\nDiff: {diff}\nReversed Diff: {reversed_diff}\n")
                if abs(reversed_diff) < abs(diff):
                    logger.info(f"{self.filepath.name} {component} component may be reversed.")
                    reversed_components.append(component)
        return reversed_components

    def auto_name_file(self):
        """
        Automatically rename file names.
        For boreholes, applies the hole name (with upper()) with components appened.
        For surface, applies line name (with upper()), removes "L".
        :return: None
        """
        if self.is_borehole():
            new_name = f"{self.line_name.upper()} {''.join(self.get_components())}"
        else:
            new_name = re.sub(r"L", "", self.line_name.upper()).strip()
        new_path = self.filepath.with_name(new_name).with_suffix(".stp")
        os.rename(str(self.filepath), str(new_path))
        self.filepath = new_path
        return self.filepath

    def auto_name_line(self):
        """
        Automatically rename hole and line names.
        For boreholes, applies upper() and removes "z" or "xy" since many operators tend to add that.
        For surface, applies upper() and removes "L".
        :return: None
        """
        if self.is_borehole():
            new_name = re.sub(r"xy|XY|z|Z", "", self.line_name.upper()).strip()
        else:
            new_name = re.sub(r"L", "", self.line_name.upper()).strip()
        self.line_name = new_name
        return self.line_name

    def set_crs(self, crs):
        """
        Set the CRS of all GPS objects
        :param crs: CRS object
        """
        logger.info(f"Setting CRS of {self.filepath.name} to {crs.name if crs else 'None'}.")

        self.crs = crs
        self.loop.crs = crs
        if self.is_borehole():
            self.collar.crs = crs
        else:
            self.line.crs = crs

        # Add the note, removing any existing ones.
        for note in reversed(self.notes):
            if '<GEN> CRS' in note or '<CRS>' in note:
                del self.notes[self.notes.index(note)]
        if self.crs is not None:
            self.notes.append(f"<GEN>/<CRS> {crs.name} (EPSG:{crs.to_epsg()})")

    def convert_crs(self, crs):
        if crs is not None:
            logger.log(f"Converting GPS of {self.filepath.name} to {crs.name}.")
            epsg_code = crs.to_epsg()
            if not self.loop.df.empty:
                self.loop = self.loop.to_epsg(epsg_code)

            if self.is_borehole():
                if not self.collar.df.empty:
                    self.collar = self.collar.to_epsg(epsg_code)

            else:
                if not self.line.df.empty:
                    self.line = self.line.to_epsg(epsg_code)

    def to_string(self, legacy=False):
        """
        Return the text format of the Step file
        :param legacy: bool, if True will strip newer features so it is compatible with Step (such as D5 RAD tool
        lines and remove Timestamp and Deleted values.
        :return: str, Full text of the Step file
        """
        ps = StepSerializer()
        text = ps.serialize(self.copy(), legacy=legacy)
        return text

    def to_headerdf(self):
        # We have to use deepcopy to avoid mutating the object
        d = {}
        kd = self.__dict__
        for k in kd.keys():
            if kd[k] is None or \
                    isinstance(kd[k], str) or \
                    isinstance(kd[k], bool) or \
                    isinstance(kd[k], float) or \
                    isinstance(kd[k], int):
                d[k] = self.__dict__[k]

        if self.is_borehole() and not self.collar.df.empty:
            d['Easting'], d['Northing'], d['Elevation'] = self.collar.df.Easting[0], \
                                                          self.collar.df.Northing[0], \
                                                          self.collar.df.Elevation[0]
        else:
            d['Easting'], d['Northing'], d['Elevation'] = None, None, None
        # Hope to god the last station is the last station in the survey
        d['Start'], d['End'] = self.data.Station[0], self.data.Station[len(self.data.Station) - 1]
        df = pd.DataFrame(d, index=[0])
        return df

    def to_xyz(self):
        """
        Create a str in XYZ format of the step file's data
        :return: str
        """

        def get_station_gps(row):
            """
            Add the GPS information for each station
            :param row: pandas DataFrame row
            :return: pandas DataFrame row
            """
            value = row.c_Station
            filt = gps['Station'] == value

            if filt.any():
                row['Easting'] = gps[filt]['Easting'].iloc[0]
                row['Northing'] = gps[filt]['Northing'].iloc[0]
                row['Elevation'] = gps[filt]['Elevation'].iloc[0]
            return row

        df = pd.DataFrame(columns=['Easting', 'Northing', 'Elevation', 'Component', 'Station', 'c_Station'])
        step_data = self.get_data(sorted=True).dropna(subset=['Station'])

        if self.is_borehole():
            gps = self.get_geometry().get_projection(stations=self.get_stations(converted=True))
            # Rename 'Relative_depth' to 'Station' for get_station_gps, so it matches with
            gps.rename(columns={'Relative_depth': 'Station'}, inplace=True)
        else:
            gps = self.get_line_gps(sorted=True).drop_duplicates('Station')

        # assert not self.is_borehole(), 'Can only create XYZ file with surface Step files.'
        if gps.empty:
            raise Exception(f"Cannot create XYZ file with {self.filepath.name} because it has no GPS.")

        logger.info(f'Converting {self.filepath.name} to XYZ')

        df['Component'] = step_data.Component.copy()
        df['Station'] = step_data.Station.copy()
        df['c_Station'] = df.Station.map(convert_station)  # Used to find corresponding GPS

        # Add the GPS
        df = df.apply(get_station_gps, axis=1)

        # Create a dataframe of the readings with channel number as columns
        channel_data = pd.DataFrame(step_data.Reading.to_dict()).transpose()

        # Merge the two data frames
        df = pd.concat([df, channel_data], axis=1).drop('c_Station', axis=1)
        str_df = df.to_string(index=False)
        return str_df

    def copy(self):
        """
        Create a copy of the StepFile object
        :return: StepFile object
        """
        copy_step = copy.deepcopy(self)
        # Create a copy of the RAD Tool objects, otherwise a deepcopy of a StepFile object still references the same
        # RADTool objects.
        copy_step.data.RAD_tool = copy_step.data.RAD_tool.map(lambda x: copy.deepcopy(x))
        return copy_step

    def save(self, processed=False, legacy=False, backup=False, rename=False, tag=''):
        """
        Save the Step file to a .stp file with the same filepath it currently has.
        :param processed: bool, Average, split and de-rotate (if applicable) and save in a legacy format.
        :param legacy: bool, will save a legacy version which is compatible with Step.
        :param backup: bool, if the save is for a backup. If so, it will save the Step file in a [Backup] folder,
        and create the folder if it doesn't exist. The [Backup] folder will be located in the parent directory of the
        StepFile.
        :param tag: str, tag to be append to the file name. Used for pre-averaging and pre-splitting saves.
        """

        logger.info(f"Saving {self.filepath.name}. (Legacy: {legacy}. Processed: {processed}. Backup: {backup}. "
                    f"Rename: {rename}, Tag: {tag})")

        # Once legacy is saved once, it will always save as legacy.
        if legacy is True or processed is True:
            self.legacy = True

        if processed is True:
            # Make sure the file is averaged and split and de-rotated
            if not self.is_split():
                self.split()
            if not self.is_averaged():
                self.average()
            if self.is_borehole():
                if self.has_xy() and not self.is_derotated():
                    if not self.prepped_for_rotation:
                        self.prep_rotation()
                    self.rotate('acc')

            if rename is True:
                # Remove underscore-dates and tags
                file_name = re.sub(r'_\d{4}', '', re.sub(r'\[-?\w\]', '', self.filepath.name))
                if not self.is_borehole():
                    file_name = file_name.upper()
                    if file_name.lower()[0] == 'c':
                        file_name = file_name[1:]

                self.filepath = self.filepath.with_name(file_name)

        text = self.to_string(legacy=any([processed, legacy, self.legacy]))

        if backup:
            backup_path = self.filepath.parent.joinpath('[Backup]').joinpath(
                self.filepath.stem + tag + self.filepath.suffix)

            # Create a [Backup] folder if it doesn't exist
            if not backup_path.parent.is_dir():
                Path.mkdir(backup_path.parent)

            print(text, file=open(str(backup_path), 'w+'))

        else:
            print(text, file=open(str(self.filepath), 'w+'))

    def average(self):
        """
        Averages the data of the Step file object. Uses a weighted average.
        :return: Step file object
        """
        if self.is_averaged():
            logger.info(f"{self.filepath.name} is already averaged.")
            return
        logger.info(f"Averaging {self.filepath.name}.")

        def weighted_average(group):
            """
            Function to calculate the weighted average reading of a station-component group.
            :param group: pandas DataFrame of Step data for a station-component
            :return: pandas DataFrame of the averaged station-component.
            """
            # Take the first row as a new data frame
            new_data_df = group.iloc[0]
            # Sum the number of stacks column
            new_data_df['Number_of_stacks'] = group['Number_of_stacks'].sum()
            # Add the weighted average of the readings to the reading column
            new_data_df['Reading'] = np.average(group.Reading.to_list(),
                                                axis=0,
                                                weights=group['Number_of_stacks'].to_list())
            return new_data_df

        # Don't use deleted data
        filt = ~self.data.Deleted.astype(bool)

        if not filt.any():
            raise Exception(f"No remaining non-deleted data to average in {self.filepath.name}.")

        # Create a data frame with all data averaged
        df = self.data[filt].groupby(['Station', 'Component']).apply(weighted_average)
        # Sort the data frame
        df = sort_data(df)
        self.data = df
        self.number_of_readings = len(self.data)
        return self

    def split(self):
        """
        Remove the on-time channels of the Step file object
        :return: Step file object with split data
        """
        logger.info(f"Splitting channels for {self.filepath.name}.")
        if self.is_split():
            logger.info(f"{self.filepath.name} is already split.")
            return

        # Only keep the select channels from each reading
        self.data.Reading = self.data.Reading.map(lambda x: x[~self.channel_times.Remove.astype(bool)])
        # Create a filter and update the channels table
        filt = ~self.channel_times.Remove.astype(bool)
        self.channel_times = self.channel_times[filt].reset_index(drop=True)
        # Update the Step file's number of channels attribute
        self.number_of_channels = len(self.channel_times)

        return self

    # def remove_channels(self, n: [int]):
    #     """
    #     Remove n channels from the StepFile
    #     :return: Step file object
    #     """
    #     logger.info(f"Removing channel(s) {n} for {self.filepath.name}.")
    #
    #     # Delete the channels from each reading
    #     for i, r in enumerate(self.data.Reading):
    #         self.data.Reading[i] = np.delete(r, n)
    #
    #     # Create a filter and update the channels table
    #     self.channel_times.drop(n, inplace=True)
    #     self.channel_times.reset_index(drop=True, inplace=True)
    #     # Update the Step file's number of channels attribute
    #     self.number_of_channels = len(self.channel_times)
    #
    #     return self

    def scale_coil_area(self, coil_area):
        """
        Scale the data by a change in coil area
        :param coil_area: int: new coil area
        :return: StepFile object: self with data scaled
        """
        logger.info(f"Scaling coil area of {self.filepath.name} to {coil_area}.")

        new_coil_area = coil_area
        assert isinstance(new_coil_area, int), "New coil area is not type int"
        old_coil_area = float(self.coil_area)

        scale_factor = float(old_coil_area / new_coil_area)

        self.data.Reading = self.data.Reading * scale_factor  # Vectorized
        logger.info(f"{self.filepath.name} coil area scaled to {new_coil_area} from {old_coil_area}.")

        self.coil_area = new_coil_area
        self.notes.append(f'<HE3> Data scaled by coil area change of {old_coil_area}/{new_coil_area}')
        return self

    def scale_current(self, current):
        """
        Scale the data by a change in current
        :param current: float, new current
        :return: StepFile object, self with data scaled
        """
        new_current = current
        assert isinstance(new_current, float), "New current is not type float"
        logger.info(f"Performing current change for {self.filepath.name} to {current}.")

        old_current = float(self.current)

        scale_factor = float(new_current / old_current)

        self.data.Reading = self.data.Reading * scale_factor  # Vectorized

        self.current = new_current
        self.notes.append(f'<HE3> Data scaled by current change of {new_current}A/{old_current}A')
        return self

    def scale_by_factor(self, factor):
        """
        Scale the data by a change in coil area
        :param factor: float
        :return: StepFile object, self with data scaled
        """
        assert isinstance(factor, float), "New coil area is not type float"
        # Scale the scale factor to account for compounding
        scaled_factor = factor / (1 + self.total_scale_factor)

        self.data.Reading = self.data.Reading * (1 + scaled_factor)  # Vectorized
        logger.info(f"{self.filepath.name} data scaled by factor of {(1 + scaled_factor)}.")

        self.total_scale_factor += factor

        self.notes.append(f'<HE3> Data scaled by factor of {1 + factor}')
        return self

    def mag_offset(self):
        """
        Subtract the last channel from the entire decay
        This will remove all amplitude information from the Step!
        :return: StepFile object, self with data scaled
        """
        def substract_mag(reading):
            off_time_data = np.delete(reading, self.channel_times.Remove)
            mag = np.average(off_time_data[-3:])
            offset_data = reading - mag
            return offset_data

        self.data.Reading = self.data.Reading.map(substract_mag)
        # for i in range(len(self.data.Reading)):
        #     self.data.Reading[i] -= self.data.Reading[i][-1]
        #     self.data.Reading[i][-1] = np.average(self.data.Reading[i][-7:])
        logger.info(f"Data in {self.filepath.name} offset by last reading - Amplitude information lost")

        self.notes.append('<HE3> Data shifted to force last chn to zero.')
        return self

    def change_suffix(self, new_suffix):
        """
        Change the station suffix of all data in the StepFile to new_suffix. Only applies to surface surveys.
        :param new_suffix: str, either N, S, E, W
        :return: StepFile object
        """
        assert new_suffix.upper() in ['N', 'E', 'S', 'W'], f"{new_suffix} is not a valid suffix."
        assert not self.is_borehole(), f"Suffixes only apply to surface surveys."

        self.data.loc[:, 'Station'] = self.data.loc[:, 'Station'].map(
            lambda x: re.sub(r'[NESW]', new_suffix.upper(), x))

        return self

    def reverse_component(self, component):
        logger.info(f"Reversing {component} data of {self.filepath.name}.")
        filt = self.data.Component == component.upper()

        if filt.any():
            data = self.data[filt]
            data.loc[:, 'Reading'] = data.loc[:, 'Reading'] * -1
            self.data[filt] = data

            note = f"<HE3> {component.upper()} component polarity reversed."
            if note in self.notes:
                self.notes.remove(note)
            else:
                self.notes.append(note)
        else:
            logger.warning(f"{self.filepath.name} has no {component} component data.")
        return self

    def reverse_station_numbers(self):
        """
        Reverse the order of all station numbers.
        """
        def get_new_station_num(station):
            old_number = re.search(r"\d+", station).group(0)
            new_number = new_order.get(old_number)
            new_station = re.sub(r"\d+", new_number, station)
            return new_station

        logger.info(f"Reversing station numbers of {self.filepath.name}.")
        new_order = dict(zip(self.get_stations(converted=True).astype(str),
                             reversed(self.get_stations(converted=True).astype(str))))
        reversed_stations = self.data.Station.map(get_new_station_num)
        self.data.Station = reversed_stations

        note = f"<HE3> Station numbers reversed."
        if note in self.notes:
            self.notes.remove(note)
        else:
            self.notes.append(note)
        return self

    def rotate(self, method='acc', soa=0):
        """
        Rotate the XY data of the Step file.
        Formula: X' = Xcos(roll) - Ysin(roll), Y' = Xsin(roll) + Ycos(roll)
        :param method: str, Method of rotation, either 'acc' for accelerometer or 'mag' for magnetic, or 'unrotate' if
        the file has been de-rotated.
        :param soa: int, Sensor offset angle
        :return: Step file object with rotated data
        """
        assert self.is_borehole(), f"{self.filepath.name} is not a borehole file."

        if not self.prepped_for_rotation:
            logger.info(f"{self.filepath.name} has not been prepped for rotation.")
            self.prep_rotation()

        if method == "unrotate":
            assert self.is_derotated(), f"{self.filepath.name} has not been de-rotated."
            assert self.has_d7(), f"{self.filepath.name} RAD tool values must be D7."
        # else:
        #     if method is not None:
        #         # assert self.prepped_for_rotation, f"{self.filepath.name} has not been prepped for rotation."
        #         if not self.prepped_for_rotation:
        #             logger.info(f"{self.filepath.name} has not been prepped for rotation.")
        #             self.prep_rotation()
        self.soa += soa
        logger.info(f"De-rotating data of {self.filepath.name} using {method} with SOA {self.soa}.")

        def rotate_group(group, method, soa):
            """
            Rotate the data for a given reading.
            :param group: pandas DataFrame: data frame of the readings to rotate. Must contain at least one
            reading from X and Y components, and the RAD tool values for all readings must all be the same.
            :param method: str: type of rotation to apply. Either 'acc' for accelerometer or 'mag' for magnetic
            :return: pandas DataFrame: data frame of the readings with the data rotated.
            """
            def get_new_rad(method):
                """
                Create a new RADTool object ready for XY de-rotation based on the rotation method
                :param method: str, either 'acc', 'mag', or 'pp'
                :return: RADTool object
                """
                # PP rotation using cleaned PP
                if method == 'pp':
                    if self.is_fluxgate():
                        roll_angle = rad.measured_pp_roll_angle
                        rot_type = 'pp_raw'
                    else:
                        roll_angle = rad.cleaned_pp_roll_angle
                        rot_type = 'pp_cleaned'

                    new_info = {'roll_angle': roll_angle,
                                'dip': rad.pp_dip,
                                'R': 'R2',
                                'angle_used': roll_angle,
                                'derotated': True,
                                'rotation_type': rot_type}

                # Accelerometer rotation
                elif method == 'acc':
                    new_info = {'roll_angle': rad.acc_roll_angle,
                                'dip': rad.acc_dip,
                                'R': 'R3',
                                'angle_used': rad.acc_roll_angle + soa,
                                'derotated': True,
                                'rotation_type': 'acc'}

                # Magnetometer rotation
                elif method == 'mag':
                    new_info = {'roll_angle': rad.mag_roll_angle,
                                'dip': rad.mag_dip,
                                'R': 'R3',
                                'angle_used': rad.mag_roll_angle + soa,
                                'derotated': True,
                                'rotation_type': 'mag'}

                # SOA rotation
                elif method is None:
                    if self.is_derotated():
                        roll_angle = rad.angle_used
                        r = "R3"
                        dip = rad.dip
                        derotated = True
                    else:
                        roll_angle = soa
                        r = None
                        dip = None
                        derotated = False

                    new_info = {'roll_angle': roll_angle,
                                'dip': dip,
                                'R': r,
                                'angle_used': soa,
                                'derotated': derotated,
                                'rotation_type': 'soa'}

                elif method == 'unrotate':
                    new_info = {'roll_angle': None,
                                'dip': None,
                                'R': None,
                                'angle_used': rad.angle_used,
                                'derotated': False,
                                'rotation_type': None}

                else:
                    raise ValueError(f"{method} is not a valid de-rotation method.")

                # Set the new attributes to the RAD object
                for key, value in new_info.items():
                    setattr(rad, key, value)
                return rad

            def weighted_average(group):
                """
                Function to calculate the weighted average reading of a station-component group.
                :param group: pandas DataFrame of Step data for a station-component
                :return: np array, averaged reading
                """
                # Sum the number of stacks column
                weights = group['Number_of_stacks'].to_list()
                # Add the weighted average of the readings to the reading column
                averaged_reading = np.average(group.Reading.to_list(),
                                              axis=0,
                                              weights=weights)
                return averaged_reading

            # print(f"Rotating station {group.iloc[0].Station}")
            # if group.iloc[0].Station == "400" or group.iloc[0].Station == "220":
            #     print("Stopping here")
            # Create a new RADTool object ready for de-rotating
            rad = group.iloc[0]['RAD_tool']  # Why do some RADs have no acc angle value?
            new_rad = get_new_rad(method)
            if method == "unrotate":
                roll_angle = rad.angle_used
                roll = -math.radians(roll_angle)
                new_rad.angle_used = None
            else:
                roll_angle = new_rad.angle_used  # Roll angle used for de-rotation
                roll = math.radians(roll_angle)

            x_rows = group[group['Component'] == 'X']
            y_rows = group[group['Component'] == 'Y']

            rotated_x = []
            rotated_y = []

            if len(x_rows) == len(y_rows):
                # print(f"Length of X and Y are the same, using indexed pairing.")
                for i, (x_data, y_data) in enumerate(
                        zip(x_rows.itertuples(index=False), y_rows.itertuples(index=False))):
                    x = [x * math.cos(roll) - y * math.sin(roll) for (x, y) in zip(x_data.Reading, y_data.Reading)]
                    y = [x * math.sin(roll) + y * math.cos(roll) for (x, y) in zip(x_data.Reading, y_data.Reading)]
                    rotated_x.append(np.array(x))
                    rotated_y.append(np.array(y))
            else:
                x_pair = weighted_average(x_rows)
                y_pair = weighted_average(y_rows)

                for x_data in x_rows.itertuples(index=False):
                    x = [x * math.cos(roll) - y * math.sin(roll) for (x, y) in zip(x_data.Reading, y_pair)]
                    rotated_x.append(np.array(x))
                for y_data in y_rows.itertuples(index=False):
                    y = [x * math.sin(roll) + y * math.cos(roll) for (x, y) in zip(x_pair, y_data.Reading)]
                    rotated_y.append(np.array(y))

            x_rows.Reading = rotated_x
            y_rows.Reading = rotated_y

            row = x_rows.append(y_rows)
            row['RAD_tool'] = row['RAD_tool'].map(lambda p: new_rad)
            return row

        global include_pp
        if all([self.has_all_gps(), self.ramp > 0]):
            include_pp = True
        else:
            include_pp = False
            if method == 'PP':
                raise ValueError("Cannot perform PP rotation on a Step file that doesn't have the necessary geometry.")

        # Create a filter for X and Y data only
        xy_filt = (self.data.Component == 'X') | (self.data.Component == 'Y')
        xy_data = self.data[xy_filt]

        if xy_data.empty:
            raise Exception(f"{self.filepath.name} has no eligible XY data for de-rotation.")

        # Rotate the data
        rotated_data = xy_data.groupby(['Station', 'RAD_ID'],
                                       group_keys=False,
                                       as_index=False).apply(lambda l: rotate_group(l, method, soa))

        self.data.update(rotated_data)  # Fixes KeyError "... value not in index"

        # Remove the rows that were filtered out in filtered_data
        if method == "unrotate":
            self.soa = 0
        self.probes['SOA'] = str(self.soa)

        # Remove any previous de-rotation notes
        for note in reversed(self.notes):
            if "<GEN> XY data" in note and "rotated" in note:
                self.notes.remove(note)

        # Add the rotation note
        if method == 'acc':
            self.notes.append('<GEN> XY data de-rotated using accelerometer.')
        elif method == 'mag':
            self.notes.append('<GEN> XY data de-rotated using magnetometer.')
        elif method == 'PP':
            self.notes.append('<GEN> XY data de-rotated using PP.')
        elif method == 'unrotate':
            self.notes.append('<GEN> XY data un-rotated.')

        if float(soa) != 0.0:
            self.notes.append(f"<GEN> XY data rotated using an SOA offset of {self.soa}°.")
        return self

    def prep_rotation(self):
        """
        Prepare the Step file for probe de-rotation by updating the RAD tool objects with all calculations needed for
        any eligible de-rotation method.
        :return: tuple, updated StepFile object and data frame of ineligible stations.
        """
        assert self.is_borehole(), f"{self.filepath.name} is not a borehole file."
        logger.info(f"Preparing for XY de-rotation for {self.filepath.name}.")

        def setup_pp():
            """
            Set up the necessary variables used for cleaned PP rotation.
            """
            assert self.has_loop_gps(), f"{self.filepath.name} has no loop GPS."
            assert self.has_geometry(), f"{self.filepath.name} has incomplete geometry."
            assert self.has_collar_gps(), f"{self.filepath.name} has no collar GPS."
            assert self.ramp > 0, f"Ramp must be larger than 0. {self.ramp} was passed for {self.filepath.name}."

            global proj, loop, ramp, mag_calc, ch_times, ch_numbers

            self.pp_table = pd.DataFrame(columns=['Station',
                                                  'Azimuth',
                                                  'Dip',
                                                  'Easting',
                                                  'Northing',
                                                  'Elevation',
                                                  'TPPx',
                                                  'TPPy',
                                                  'TPPz',
                                                  'CPPx',
                                                  'CPPy',
                                                  'CPPz'])
            geometry = BoreholeGeometry(self.collar, self.segments)
            proj = geometry.get_projection(stations=self.get_stations(converted=True))
            loop = self.get_loop_gps(sorted=False, closed=False)
            # Get the ramp in seconds
            ramp = self.ramp / 10 ** 6
            mag_calc = MagneticFieldCalculator(loop, closed_loop=not self.is_mmr())

            # Only keep off-time channels with PP
            ch_times = self.channel_times[~self.channel_times.Remove.astype(bool)]
            # Normalize the channel times so they start from turn off. Look at MRC-067 for proof
            ch_times.loc[:, 'Start':'Center'] = ch_times.loc[:, 'Start':'Center'].applymap(lambda x: x + ramp)

            pp_ch = ch_times.iloc[0]
            # Make sure the PP channel is within the ramp
            assert pp_ch.End < ramp, 'PP channel does not fall within the ramp'
            pp_center = pp_ch['Center']

            # Get the special channel numbers
            ch_numbers = []
            total_time = pp_center
            last_time = ch_times.iloc[-1].End
            while (total_time + ramp) < last_time:
                # Add the ramp time iteratively to the PP center time until reaching the end of the off-time
                total_time += ramp

                # Create a filter to find in which channel the time falls in
                filt = (ch_times['Start'] <= total_time) & (ch_times['End'] > total_time)
                if filt.any():
                    ch_index = ch_times[filt].index.values[0]
                    ch_numbers.append(ch_index)
            # print(ch_numbers)

        def prepare_rad(group):
            """
            Update the RAD Tool object with all calculated angles for rotation.
            :param group: pandas DataFrame: data frame of the readings to rotate. Must contain at least one
            reading from X and Y components, and the RAD tool values for all readings must all be the same.
            :return: pandas DataFrame: group with the RAD_tool objects updated and ready for rotation.
            """

            def calculate_angles(rad):
                """
                Calculate the roll angle for each available method and add it to the RAD tool object.
                :param rad: RADTool object
                """

                def calculate_pp_angles():
                    def get_cleaned_pp(row):
                        """
                        Calculate the cleaned PP value of a station
                        :param row: Step data DataFrame row
                        :return: float, cleaned PP value
                        """
                        # Get the list of ch_times indexes so the cleaned_pp can be selected by index.
                        # Needed for when channels are split before hand.
                        cleaned_pp_channels = ch_times.index.to_list()

                        cleaned_pp = row.Reading[0]
                        for num in ch_numbers:
                            ind = cleaned_pp_channels.index(num)
                            cleaned_pp += row.Reading[ind]
                        return cleaned_pp

                    # Add the PP information (theoretical PP, cleaned PP, roll angle) to the new RAD Tool object
                    if include_pp is True:
                        segments = self.get_segments()
                        pp_rad_info = dict()

                        # Calculate the raw PP value for each component
                        pp_ch_index = self.channel_times[~self.channel_times.Remove.astype(bool)].index.values[0]
                        measured_ppx = group[group.Component == 'X'].apply(lambda x: x.Reading[pp_ch_index],
                                                                           axis=1).mean()
                        measured_ppy = group[group.Component == 'Y'].apply(lambda x: x.Reading[pp_ch_index],
                                                                           axis=1).mean()
                        ppxy_measured = math.sqrt(sum([measured_ppx ** 2, measured_ppy ** 2]))

                        # Use the segment azimuth and dip of the next segment (as per Bill's cross)
                        # Find the next station. If it's the last station, re-use the last station.
                        stations = list(self.data.Station.unique())
                        current_station = group.Station.unique()[0]
                        current_station_ind = stations.index(current_station)

                        # Re-use the last station if it's the current index
                        if current_station_ind == len(stations) - 1:
                            next_station = current_station
                        else:
                            next_station = stations[current_station_ind + 1]

                        # Calculate the dip and azimuth at the next station, interpolating in case the station
                        # is not in the segments.
                        seg_dip = np.interp(int(next_station), segments.Depth, segments.Dip)
                        seg_azimuth = np.interp(int(next_station), segments.Depth, segments.Azimuth)

                        # Find the location in 3D space of the station
                        filt = proj.loc[:, 'Relative_depth'] == float(group.Station.iloc[0])
                        x_pos, y_pos, z_pos = proj[filt].iloc[0]['Easting'], \
                                              proj[filt].iloc[0]['Northing'], \
                                              proj[filt].iloc[0]['Elevation']

                        # Calculate the theoretical magnetic field strength of each component at that point (in nT/s)
                        Tx, Ty, Tz = mag_calc.calc_total_field(x_pos, y_pos, z_pos,
                                                               amps=self.current,
                                                               out_units='nT/s',
                                                               ramp=ramp)

                        # Rotate the theoretical values into the same frame of reference used with boreholes
                        rTx, rTy, rTz = R.from_euler('Z', -90, degrees=True).apply([Tx, Ty, Tz])

                        # Rotate the theoretical values into the hole coordinate system
                        r = R.from_euler('YZ', [90 - seg_dip, seg_azimuth], degrees=True)
                        rT = r.apply([rTx, rTy, rTz])  # The rotated theoretical values
                        ppxy_theory = math.sqrt(sum([rT[0] ** 2, rT[1] ** 2]))

                        if not self.is_fluxgate():
                            # Calculate the cleaned PP value for each component for non-fluxgate surveys
                            cleaned_PPx = group[group.Component == 'X'].apply(get_cleaned_pp, axis=1).mean()
                            cleaned_PPy = group[group.Component == 'Y'].apply(get_cleaned_pp, axis=1).mean()
                            ppxy_cleaned = math.sqrt(sum([cleaned_PPx ** 2, cleaned_PPy ** 2]))

                            # Calculate the required rotation angle
                            cleaned_pp_roll_angle = math.degrees(
                                math.atan2(rT[1], rT[0]) - math.atan2(cleaned_PPy, cleaned_PPx)
                            )

                            # if allow_negative_angles is False:
                            if cleaned_pp_roll_angle < 0:
                                cleaned_pp_roll_angle = cleaned_pp_roll_angle + 360

                            pp_rad_info['ppx_cleaned'] = cleaned_PPx
                            pp_rad_info['ppy_cleaned'] = cleaned_PPy
                        else:
                            cleaned_pp_roll_angle = None
                            ppxy_cleaned = None

                        measured_pp_roll_angle = math.degrees(math.atan2(rT[1], rT[0]) -
                                                              math.atan2(measured_ppy, measured_ppx))

                        # if allow_negative_angles is False:
                        if measured_pp_roll_angle < 0:
                            measured_pp_roll_angle = measured_pp_roll_angle + 360

                        # Update the RAD Tool object with the new information
                        pp_rad_info['azimuth'] = seg_azimuth
                        pp_rad_info['dip'] = seg_dip

                        pp_rad_info['x_pos'] = x_pos
                        pp_rad_info['y_pos'] = y_pos
                        pp_rad_info['z_pos'] = z_pos

                        pp_rad_info['ppx_theory'] = rT[0]
                        pp_rad_info['ppy_theory'] = rT[1]
                        pp_rad_info['ppz_theory'] = rT[2]
                        pp_rad_info['ppx_raw'] = measured_ppx
                        pp_rad_info['ppy_raw'] = measured_ppy
                        pp_rad_info['ppxy_theory'] = ppxy_theory
                        pp_rad_info['ppxy_cleaned'] = ppxy_cleaned
                        pp_rad_info['ppxy_measured'] = ppxy_measured
                        pp_rad_info['cleaned_pp_roll_angle'] = cleaned_pp_roll_angle
                        pp_rad_info['measured_pp_roll_angle'] = measured_pp_roll_angle
                        pp_rad_info['pp_dip'] = -seg_dip

                        for key, value in pp_rad_info.items():
                            setattr(rad, key, value)

                def calculate_acc_angles():
                    if rad.D == 'D5':
                        x, y, z = rad.x, rad.y, rad.z
                    else:
                        x, y, z = rad.gx, rad.gy, rad.gz

                    theta = math.atan2(y, z)
                    cc_roll_angle = 360 - math.degrees(theta) if y < 0 else math.degrees(theta)
                    roll_angle = 360 - cc_roll_angle if y > 0 else cc_roll_angle
                    if roll_angle >= 360:
                        roll_angle = roll_angle - 360
                    elif roll_angle < 0:
                        roll_angle = roll_angle + 360

                    # Calculate the dip
                    dip = math.degrees(math.acos(x / math.sqrt((x ** 2) + (y ** 2) + (z ** 2)))) - 90

                    # Update the new_rad with the de-rotation information
                    new_info = {'acc_roll_angle': roll_angle,
                                'acc_dip': dip}

                    for key, value in new_info.items():
                        setattr(rad, key, value)

                def calculate_mag_angles():
                    if rad.D == 'D5':
                        x, y, z = rad.x, rad.y, rad.z
                    else:
                        x, y, z = rad.Hx, rad.Hy, rad.Hz

                    theta = math.atan2(-y, -z)
                    cc_roll_angle = math.degrees(theta)
                    roll_angle = 360 - cc_roll_angle if y < 0 else cc_roll_angle
                    if roll_angle > 360:
                        roll_angle = roll_angle - 360
                    elif roll_angle < 0:
                        roll_angle = -roll_angle

                    # Calculate the dip
                    dip = -90.  # The dip is assumed to be 90°

                    # Update the new_rad with the de-rotation information
                    new_info = {'mag_roll_angle': roll_angle,
                                'mag_dip': dip}

                    for key, value in new_info.items():
                        setattr(rad, key, value)

                calculate_pp_angles()
                calculate_acc_angles()
                calculate_mag_angles()
                return rad

            rad = group.iloc[0]['RAD_tool']
            # Calculate all the roll angles available and add it to the RAD tool object
            rad = calculate_angles(rad)
            group.RAD_tool = rad
            return group

        if all([self.has_all_gps(), self.ramp > 0]):
            setup_pp()
            include_pp = True
        else:
            include_pp = False

        # Remove groups that don't have X and Y pairs. For some reason couldn't make it work within rotate_data
        eligible_data, ineligible_data = self.get_eligible_derotation_data()

        if eligible_data.empty:
            raise Exception(f"No eligible data found for probe de-rotation in {self.filepath.name}")

        # Calculate the RAD tool angles
        prepped_data = eligible_data.groupby(['Station', 'RAD_ID'],
                                             group_keys=False,
                                             as_index=False).apply(lambda l: prepare_rad(l))

        # Don't use .update as the ineligible data will be kept in.
        xy_filt = (self.data.Component == 'X') | (self.data.Component == 'Y')
        self.data[xy_filt] = prepped_data

        # Remove the rows that were filtered out in filtered_data
        # Resetting the index prevents the error IndexError: single positional indexer is out-of-bounds
        self.data = self.data.dropna(subset=['Station']).reset_index(drop=True)
        self.prepped_for_rotation = True
        return self, ineligible_data


class StepParser:
    """
    Class for parsing Step files into StepFile objects
    """
    def __init__(self):
        self.filepath = None

    def parse(self, filepath):
        """
        Parses a Step file to extract all information and creates a StepFile object out of it.
        :param filepath: string containing path to a Step file
        :return: A Step_File object representing the data found inside of filename
        """
        def parse_tags(text):
            cols = [
                'Format',
                'Units',
                'Operator',
                'Probes',
                'Current',
                'Loop dimensions'
            ]
            tags = {}
            text = text.strip().split('\n')

            assert text, f'Error parsing the tags. No matches were found in {self.filepath.name}.'
            assert len(text) == 6, f"{len(text)} tags were found instead of 6 in {self.filepath.name}."

            tags['Format'] = text[0].split('>')[1].strip()
            tags['Units'] = text[1].split('>')[1].strip()
            tags['Operator'] = text[2].split('>')[1].strip().title()
            tags['Probes'] = text[3].split('>')[1].strip()
            tags['Current'] = float(text[4].split('>')[1].strip())
            tags['Loop dimensions'] = text[5].split('>')[1].strip()

            # Format the units
            if tags['Units'] == 'nanoTesla/sec':
                tags['Units'] = 'nT/s'
            elif tags['Units'] == 'picoTesla' or tags['Units'] == 'picoTeslas':
                tags['Units'] = 'pT'

            # Format the operator name, removing the '~'
            if '~' in tags['Operator']:
                tags['Operator'] = tags['Operator'].split('~')[0].strip()

            # Format the probe numbers
            probe_cols = ['Probe number', 'SOA', 'Tool number', 'Tool ID']
            tags['Probes'] = dict(zip(probe_cols, tags['Probes'].split()))

            return tags

        def parse_loop(text):
            """
            Parse the loop section (<L> tags) of the Step File
            :param text: str, raw loop string from the Step file
            :return: list of everything in the <L> tag section
            """
            assert text, f'Error parsing the loop coordinates. No matches were found in {self.filepath.name}.'

            text = text.strip().split('\n')
            loop_text = [t.strip().split() for t in text if t.startswith('<L')]
            return loop_text

        def parse_line(text):
            """
            Parse the line section (<P> tags) of the Step File
            :param text: str, raw line string from the Step file
            :return: list of everything in the <P> tag section
            """
            assert text, f'Error parsing the line coordinates. No matches were found in {self.filepath.name}.'

            text = text.strip().split('\n')
            line_text = [t.strip().split() for t in text if t.startswith('<P')]
            return line_text

        def parse_notes(file):
            """
            Parse the notes of the Step File, which are any lines with <GEN> or <HE> tags.
            :param file: str of the .stp file
            :return: list of notes
            """
            notes = re.findall(r'<GEN>.*|<HE\d>.*|<CRS>.*', file)
            # Remove the 'xxxxxxxxxxxxxxxx' notes
            for note in reversed(notes):
                if 'xxx' in note.lower() or re.match('<GEN> NOTES', note):
                    notes.remove(note)

            return notes

        def parse_header(text):
            """
            Parse the header section of the Step File, which is the client name down to the channel table.
            :param text: str, raw header string from the Step file
            :return: dictionary of the header items
            """
            assert text, f'Error parsing the tags. No matches were found in {self.filepath.name}.'

            text = text.strip().split('\n')
            # Remove any Note tags
            for t in reversed(text):
                if t.startswith('<'):
                    text.remove(t)

            assert len(text) == 7, f"{len(text)} header lines were found instead of 7 in {self.filepath.name}."

            header = dict()

            header['Client'] = text[0]
            header['Grid'] = text[1]
            header['Line_name'] = text[2]
            header['Loop_name'] = text[3]
            header['Date'] = text[4]

            survey_param = text[5].split()
            receiver_param = text[6].split()

            assert len(survey_param) == 7, \
                f"{len(survey_param)} survey parameters were found instead of 7 in {self.filepath.name}."

            assert len(receiver_param) >= 7, \
                f"{len(receiver_param)} receiver parameters were found instead of 7 or 8 in {self.filepath.name}."

            header['Survey type'] = survey_param[0]
            header['Convention'] = survey_param[1]
            header['Sync'] = survey_param[2]
            header['Timebase'] = float(survey_param[3])
            header['Ramp'] = float(survey_param[4])
            header['Number of channels'] = int(survey_param[5])
            header['Number of readings'] = int(survey_param[6])

            header['Receiver number'] = receiver_param[0]
            header['Rx software version'] = receiver_param[1]
            header['Rx software version date'] = receiver_param[2]
            header['Rx file name'] = receiver_param[3]
            header['Normalized'] = receiver_param[4]
            header['Primary field value'] = receiver_param[5]
            header['Coil area'] = float(receiver_param[6])
            if len(receiver_param) > 7:
                header['Loop polarity'] = receiver_param[7]

            return header

        def parse_channel_times(text, units=None, num_channels=None, ramp=None):
            """
            Create a DataFrame of the channel times from the Step file.
            :param text: str, channel times section in the Step file, above the data section.
            :param units: str, nT/s or pT, used to know which channel is the ramp channel.
            :param num_channels: int, number of channels indicated in the Step file header. Used to make sure all
            channels are accounted for.
            :return: DataFrame
            """
            def channel_table(channel_times, units, ramp):
                """
                Channel times table data frame with channel start, end, center, width, and whether the channel is
                to be removed when the file is split
                :param channel_times: pandas Series, float of each channel time read from a Step file header.
                :return: pandas DataFrame
                """
                def find_last_off_time():
                    """
                    Find where the next channel width is less than half the previous channel width, which indicates
                    the start of the next on-time.
                    :return: int: Row index of the last off-time channel
                    """
                    filt = ~table['Remove'].astype(bool)
                    for index, row in table[filt][1:-1].iterrows():
                        next_row = table.loc[index + 1]
                        if row.Width > (next_row.Width * 2):
                            return index + 1

                # Create the channel times table
                table = pd.DataFrame(columns=['Start', 'End', 'Center', 'Width', 'Remove'])
                # Convert the times to miliseconds
                times = channel_times

                # The first number to the second last number are the start times
                table['Start'] = list(times[:-1])
                # The second number to the last number are the end times
                table['End'] = list(times[1:])
                table['Width'] = table['End'] - table['Start']
                table['Center'] = (table['Width'] / 2) + table['Start']

                # Step files seem to always have a repeating channel time as the third number, so the second row
                # must be removed.
                table.drop(1, inplace=True)
                table.reset_index(drop=True, inplace=True)
                table['Remove'] = False

                # If the file isn't a PP file
                if table.Width.max() > 1.1e-5:  # 1.1 because of python floats are imprecise
                    # Configure which channels to remove
                    table = get_split_table(table, units, ramp)

                    # Configure each channel after the last off-time channel (only for full waveform)
                    last_off_time_channel = find_last_off_time()
                    if last_off_time_channel:
                        table.loc[last_off_time_channel:, 'Remove'] = table.loc[last_off_time_channel:, 'Remove'].map(
                            lambda x: True)
                return table

            assert text, f'Error parsing the channel times. No matches were found in {self.filepath.name}.'

            table = channel_table(np.array(text.split(), dtype=float), units, ramp)
            assert len(table) == num_channels or len(table) == num_channels + 1, \
                f"{len(table)} channels found in channel times section instead of {num_channels} found in header of {self.filepath.name}"
            return table

        def parse_data(text):
            """
            Parse the data section of the Step file.
            :param text: str, data section after the '$' in the Step file
            :return: DataFrame of the data
            """
            cols = [
                'Station',
                'Component',
                'Reading_index',
                'Gain',
                'Rx_type',
                'ZTS',
                'Coil_delay',
                'Number_of_stacks',
                'Readings_per_set',
                'Reading_number',
                'RAD_tool',
                'Reading',
                'Deleted',
                'Overload',
                'Timestamp',
            ]

            def format_data(reading):
                """
                Format the data row so it is ready to be added to the data frame
                :param reading: str of a reading in a Step file
                :return: list
                """
                data = reading.strip().split('\n')  # Strip because readings can have more than 1 new line between them.
                head = data[0].split()

                station = head[0]
                comp = head[1][0]
                reading_index = re.search(r'\d+', head[1]).group()
                gain = head[2]
                rx_type = head[3]
                zts = head[4]
                coil_delay = head[5]
                num_stacks = head[6]
                readings_per_set = head[7]
                reading_number = head[8]

                rad_tool = data[1]
                decay = ''.join(data[2:])

                result = [station, comp, reading_index, gain, rx_type, zts, coil_delay, num_stacks, readings_per_set,
                          reading_number, rad_tool, decay]

                # Add the new columns from DMP2 files
                if len(head) > 9:
                    deleted = True if head[9] == 'True' else False
                    overload = True if head[10] == 'True' else False
                    timestamp = head[11]
                    result.extend([deleted, overload, timestamp])

                return result

            assert text, f'No data found in {self.filepath.name}.'

            # Each reading is separated by two return characters usually, but sometimes there are spaces too.
            text = re.split(r"\n\s*\n", text.strip())

            data = []
            # Format each reading to be added to the data frame. Faster than creating Series object per row.
            for read_num, reading in enumerate(text):
                if not reading.strip():
                    continue
                data.append(format_data(reading))

            # Create the data frame
            df = pd.DataFrame(data, columns=cols[:np.array(data).shape[1]])

            # Format the columns of the data frame
            # Create a RAD tool ID number to be used for grouping up readings for probe rotation, since the CDR2
            # and CDR3 don't count reading numbers the same way.
            df['RAD_tool'] = df['RAD_tool'].map(lambda x: RADTool().from_match(x))
            # Create and add the RAD ID column
            df.insert(list(df.columns).index('RAD_tool') + 1, 'RAD_ID', df['RAD_tool'].map(lambda x: x.id))
            df.drop_duplicates(subset="Reading", inplace=True)
            df['Reading'] = df['Reading'].map(lambda x: np.array(x.split(), dtype=float))
            df[['Reading_index',
                'Gain',
                'Coil_delay',
                'Number_of_stacks',
                'Readings_per_set',
                'Reading_number']] = df[['Reading_index',
                                         'Gain',
                                         'Coil_delay',
                                         'Number_of_stacks',
                                         'Readings_per_set',
                                         'Reading_number']].astype(int)
            df['ZTS'] = df['ZTS'].astype(float)

            # Format the extra DMP2 columns
            if len(df.columns) == 16:

                def get_time(timestamp):
                    if timestamp != 'None':
                        if 'AM' in timestamp or 'PM' in timestamp:
                            fmt = '%Y-%m-%d_%I:%M:%S_%p'
                        else:
                            fmt = '%Y-%m-%d_%H:%M:%S'
                        obj = datetime.strptime(timestamp, fmt)
                        return obj
                    else:
                        return None

                df[['Deleted', 'Overload']] = df[['Deleted', 'Overload']].astype(bool)
                df['Timestamp'] = df['Timestamp'].map(get_time)
            return df

        assert Path(filepath).exists(), f"{Path(filepath)} does not exist."
        self.filepath = Path(filepath)
        logger.info(f"Parsing {self.filepath.name}.")

        with open(filepath, "rt") as file:
            contents = file.readlines()

        # Remove the ~ comments from files converted with Bill's software, makes breaking up the file for parsing easier
        for i, line in enumerate(contents):
            if '~' in line:
                # Don't remove the transmitter and hole tag lines
                if re.match('~ Transmitter.*', line) or re.match('~ Hole.*', line) or re.match('~\n', line):
                    continue
                # Keep one last ~ for sectioning the header
                elif re.match('~Tags for headings.*', line):
                    contents[i] = re.sub('(~.*)', '~', line)
                else:
                    contents[i] = re.sub('(~.*)', '', line)

        contents = ''.join(contents)
        # Break the file up into sections
        scontents = contents.split('~')
        raw_tags = scontents[0]
        raw_loop = scontents[1]
        raw_line = scontents[2]
        raw_header = scontents[3].split('\n\n')[0]
        raw_channel_times = scontents[3].split('\n\n')[1].split('$')[0]
        raw_data = scontents[3].split('$')[1].strip()

        tags = parse_tags(raw_tags)
        loop_coords = parse_loop(raw_loop)
        line_coords = parse_line(raw_line)
        notes = parse_notes(contents)
        header = parse_header(raw_header)
        channel_table = parse_channel_times(raw_channel_times,
                                            units=tags.get('Units'),
                                            num_channels=header.get('Number of channels'),
                                            ramp=header.get("Ramp"))
        data = parse_data(raw_data)

        step_file = StepFile().from_step(tags, loop_coords, line_coords, notes, header, channel_table, data,
                                         filepath=filepath)
        return step_file


class StepSerializer:
    """
    Class for serializing Step files to be saved
    """
    def __init__(self):
        self.step_file = None

    def serialize_tags(self):
        result = ""
        xyp = ' '.join([self.step_file.probes.get('Probe number'),
                        self.step_file.probes.get('SOA'),
                        self.step_file.probes.get('Tool number'),
                        self.step_file.probes.get('Tool ID')])
        result += f"<FMT> {self.step_file.format}\n"
        result += f"<UNI> {'nanoTesla/sec' if self.step_file.units == 'nT/s' else 'picoTesla'}\n"
        result += f"<OPR> {self.step_file.operator}\n"
        result += f"<XYP> {xyp}\n"
        result += f"<CUR> {self.step_file.current}\n"
        result += f"<TXS> {self.step_file.loop_dimensions}"

        return result

    def serialize_loop_coords(self):
        result = '~ Transmitter Loop Co-ordinates:'
        loop = self.step_file.get_loop_gps()
        units_code = self.step_file.loop.get_units_code()
        assert units_code, f"No units code for the loop of {self.step_file.get_file_name()}."
        if loop.empty:
            result += '\n<L00>\n''<L01>\n''<L02>\n''<L03>'
        else:
            loop.reset_index(inplace=True)
            for row in loop.itertuples():
                tag = f"<L{row.Index:02d}>"
                row = f"{tag} {row.Easting:.2f} {row.Northing:.2f} {row.Elevation:.2f} {units_code}"
                result += '\n' + row
        return result

    def serialize_line_coords(self):
        def serialize_station_coords():
            result = '~ Hole/Profile Co-ordinates:'
            line = self.step_file.get_line_gps()
            units_code = self.step_file.line.get_units_code()
            assert units_code, f"No units code for the line of {self.step_file.get_file_name()}."
            if line.empty:
                result += '\n<P00>\n''<P01>\n''<P02>\n''<P03>\n''<P04>\n''<P05>'
            else:
                line.reset_index(inplace=True)
                for row in line.itertuples():
                    tag = f"<P{row.Index:02d}>"
                    row = f"{tag} {row.Easting:.2f} {row.Northing:.2f} {row.Elevation:.2f} {units_code} {row.Station}"
                    result += '\n' + row
            return result

        def serialize_collar_coords():
            result = '~ Hole/Profile Co-ordinates:'
            collar = self.step_file.get_collar_gps()
            collar.reset_index(drop=True, inplace=True)
            units_code = self.step_file.collar.get_units_code()
            assert units_code, f"No units code for the collar of {self.step_file.get_file_name()}."
            if collar.empty:
                result += '\n<P00>'
            else:
                for row in collar.itertuples():
                    tag = f"<P{row.Index:02d}>"
                    row = f"{tag} {row.Easting:.2f} {row.Northing:.2f} {row.Elevation:.2f} {units_code}"
                    result += '\n' + row
            return result

        def serialize_segments():
            result = ''
            segs = self.step_file.get_segments()
            segs.reset_index(drop=True, inplace=True)
            units_code = self.step_file.segments.get_units_code()
            assert units_code, f"No units code for the segments of {self.step_file.get_file_name()}."
            if segs.empty:
                result += '\n<P01>\n''<P02>\n''<P03>\n''<P04>\n''<P05>'
            else:
                for row in segs.itertuples():
                    tag = f"<P{row.Index + 1:02d}>"
                    row = f"{tag} {row.Azimuth:.2f} {row.Dip:.2f} {row[3]:.2f} {units_code} {row.Depth:.2f}"
                    result += '\n' + row
            return result

        if self.step_file.is_borehole():
            return serialize_collar_coords() + \
                   serialize_segments()
        else:
            return serialize_station_coords()

    def serialize_notes(self):
        results = []
        if not self.step_file.notes:
            return ''
        else:
            for line in self.step_file.notes:
                if line not in results:
                    results.append(line)
        return '\n'.join(results) + '\n'

    def serialize_header(self):
        def get_channel_times(table):
            times = []
            # Add all the start times
            table.Start.map(times.append)
            # Add the first 'End' since it's the only value not repeated as a start
            times.insert(1, table.iloc[0].End)
            # Add the last end-time
            times.append(table.iloc[-1].End)
            return times

        survey_type = self.step_file.get_survey_type()
        if survey_type == 'Surface Induction':
            survey_str = 'Surface'
        elif survey_type == 'Borehole Induction':
            survey_str = 'Borehole'
        elif survey_type == 'Surface Fluxgate':
            survey_str = 'S-Flux'
        elif survey_type == 'Borehole Fluxgate':
            survey_str = 'BH-Flux'
        elif survey_type == 'SQUID':
            survey_str = 'S-SQUID'
        else:
            raise ValueError(f"{survey_type} is not a valid survey type.")

        result_list = [str(self.step_file.client),
                       str(self.step_file.grid),
                       str(self.step_file.line_name),
                       str(self.step_file.loop_name),
                       str(self.step_file.date),
                       ' '.join([survey_str,
                                 str(self.step_file.convention),
                                 str(self.step_file.sync),
                                 str(self.step_file.timebase),
                                 str(int(self.step_file.ramp)),
                                 str(self.step_file.number_of_channels - 1),
                                 str(int(self.step_file.number_of_readings))]),
                       ' '.join([str(self.step_file.rx_number),
                                 str(self.step_file.rx_software_version),
                                 str(self.step_file.rx_software_version_date),
                                 str(self.step_file.rx_file_name),
                                 str(self.step_file.normalized),
                                 str(self.step_file.primary_field_value),
                                 str(int(self.step_file.coil_area))])]

        if self.step_file.loop_polarity is not None:
            result_list[-1] += ' ' + self.step_file.loop_polarity

        result = '\n'.join(result_list) + '\n\n'

        times_per_line = 7
        cnt = 0

        times = get_channel_times(self.step_file.channel_times)
        channel_times = [f'{time:9.6f}' for time in times]

        for i in range(0, len(channel_times), times_per_line):
            line_times = channel_times[i:i + times_per_line]
            result += ' '.join([str(time) for time in line_times]) + '\n'
            cnt += 1

        result += '$'
        return result

    def serialize_data(self, legacy=False):
        """
        Print the data to text for a Step file format.
        :param legacy: bool, will remove the timestamp and deleted status if True.
        :return: string
        """
        def serialize_reading(reading):
            reading_header = [reading['Station'],
                              reading['Component'] + 'R' + f"{reading['Reading_index']:g}",
                              f"{reading['Gain']:g}",
                              reading['Rx_type'],
                              f"{reading['ZTS']:g}",
                              f"{reading['Coil_delay']:g}",
                              f"{reading['Number_of_stacks']:g}",
                              f"{reading['Readings_per_set']:g}",
                              f"{reading['Reading_number']:g}",
                              ]
            # Add the DMP2 information if not saving a processed version of the file
            if not legacy:
                reading_header.extend([f"{reading['Deleted']}",
                                       f"{reading['Overload']}",
                                       re.sub(r'\s', '_', f"{reading['Timestamp']}")  # Replace the spaces
                                       ])

            result = ' '.join(reading_header) + '\n'
            rad = reading['RAD_tool'].to_string(legacy=legacy)
            result += rad + '\n'

            readings_per_line = 7
            reading_spacing = 12
            count = 0

            # channel_readings = [f'{r:<8g}' for r in reading['Reading']]
            channel_readings = [f'{r:10.3f}' for r in reading['Reading']]

            for i in range(0, len(channel_readings), readings_per_line):
                readings = channel_readings[i:i + readings_per_line]
                result += ' '.join([str(r) + max(0, reading_spacing - len(r)) * ' ' for r in readings]) + '\n'
                count += 1

            return result + '\n'

        df = self.step_file.get_data(sorted=True)

        # Remove deleted readings
        filt = ~df.Deleted.astype(bool)
        df = df[filt]
        if df.empty:
            logger.warning(f"No valid data found to print in {self.step_file.filepath.name}.")
            return ""
        else:
            return ''.join(df.apply(serialize_reading, axis=1))

    def serialize(self, step_file, legacy=False):
        """
        Create a string of a Step file to be printed to a text file.
        :param step_file: Step_File object
        :param legacy: bool, if True will strip newer features so it is compatible with Step (such as D5 RAD tool
        lines and remove Timestamp and Deleted values.
        :return: A string in Step file format containing the data found inside of step_file
        """
        self.step_file = step_file

        result = self.serialize_tags() + '\n'
        result += self.serialize_loop_coords() + '\n'
        result += self.serialize_line_coords() + '\n'
        result += self.serialize_notes()
        result += '~\n'
        result += self.serialize_header() + '\n'
        result += self.serialize_data(legacy=legacy)
        return result


class RADTool:
    """
    Class that represents the RAD Tool reading in a Step fiel.
    """
    def __init__(self):
        self.D = None
        self.x = None
        self.y = None
        self.z = None
        self.total_field = None

        self.id = None

    def from_match(self, match):
        """
        Create the RADTool object using the string parsed from StepParser.
        :param match: str, Full string parsed from StepParser
        :return RADTool object
        """
        match = match.split()
        self.D = match[0]  # Always D4
        match[1:] = np.array(match[1:])

        self.x = float(match[1])
        self.y = float(match[2])
        self.z = float(match[3])
        self.total_field = float(match[4])

        return self

    def from_dict(self, dict):
        """
        Use the keys and values of a dictionary to create the RADTool object.
        :param dict: dictionary with keys being the RADTool object's attributes.
        :return: RADTool object
        """
        self.id = ''

        for key, value in dict.items():
            self.__setattr__(key, value)
            self.id += str(value)

        return self

    def to_string(self, legacy=False):
        """
        Create a string for Step serialization
        :param legacy: bool, if True, return D5 values instead of D7 for compatibility with Step.
        :return: str
        """
        # If the input D value is already D5
        result = list(self.D)
        result.append(f"{self.x:g}")
        result.append(f"{self.y:g}")
        result.append(f"{self.z:g}")
        result.append(f"{self.total_field:g}")

        return ' '.join(result)


class StepGetter:
    """
    Class to get a list of Step files from a testing directory. Used for testing.
    """
    def __init__(self):
        self.step_parser = StepParser()

    def get_steps(self, folder=None, number=None, selection=None, file=None, random=False,
                 incl=None):
        """
        Retrieve a list of StepFiles
        :param folder: str, folder from which to retrieve files
        :param number: int, number of files to selected
        :param selection: int, index of file to select
        :param file: str, name the specific to open
        :param random: bool, select random files. If no number is passed, randomly selects the number too.
        :param incl: str, text to include in the file name.
        :return: list of StepFile objects.
        """

        def add_step(filepath):
            """
            Parse and add the StepFile to the list of step_files.
            :param filepath: Path object of the StepFile
            """
            if not filepath.exists():
                raise ValueError(f"File {filepath} does not exists.")

            logger.info(f'Getting File {filepath}.')
            try:
                step_file = self.step_parser.parse(filepath)
            except Exception:
                return
            else:
                step_files.append(step_file)

        sample_files_dir = Path(__file__).parents[2].joinpath('sample_files')

        if folder:
            sample_files_dir = sample_files_dir.joinpath(folder)
            if not sample_files_dir.exists():
                raise ValueError(f"Folder {folder} does not exist.")

        step_files = []

        # Pool of available files is all StepFiles in StepGetter files directory.
        if incl is not None:
            available_files = list(sample_files_dir.rglob(f'*{incl}*.stp'))
        else:
            available_files = list(sample_files_dir.rglob(f'*.stp'))
        # print(f"Available files: {', '.join([str(a) for a in available_files])}")

        if random:
            if not number:
                # Generate a random number of files to choose from
                number = randrange(5, min(len(available_files), 15))
            elif number > len(available_files):
                number = len(available_files)

            random_selection = choices(available_files, k=number)

            for file in random_selection:
                add_step(file)

        else:
            if number:
                for file in available_files[:number]:
                    filepath = sample_files_dir.joinpath(file)
                    add_step(filepath)
                    # step_files.append((step_file, None))  # Empty second item for ri_files

            elif selection is not None and not selection > len(available_files):
                filepath = sample_files_dir.joinpath(available_files[selection])
                add_step(filepath)
                # step_files.append((step_file, None))  # Empty second item for ri_files

            elif file is not None:
                filepath = sample_files_dir.joinpath(file)
                add_step(filepath)

            else:
                for file in available_files:
                    filepath = sample_files_dir.joinpath(file)
                    add_step(filepath)
                    # step_files.append((step_file, None))  # Empty second item for ri_files

        step_list = '\n'.join([str(f.filepath) for f in step_files])
        if not step_list:
            raise ValueError(f"No Step files found in {sample_files_dir}.")
        return step_files

    def parse(self, filepath):
        if not Path(filepath).is_file():
            raise FileNotFoundError(f"{filepath} does not exist.")

        step_file = StepParser.parse(filepath)
        return step_file


if __name__ == '__main__':
    sample_folder = Path(__file__).parents[2].joinpath("sample_files")

    file = sample_folder.joinpath(r"Step files\XY.STP")
    step_file = StepParser().parse(file)

    print(step_file.get_components())
    print(step_file.auto_name_file())
    print(step_file.get_file_name())
    # print(step_file.to_string(legacy=True))

