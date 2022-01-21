import copy
import logging
import math
import re
import time
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
from src import timeit

logger = logging.getLogger(__name__)

pd.options.mode.chained_assignment = None  # default='warn'

# TODO Auto-name DMP files and PP files. For PP files, name should just be Date + Receiver + 'PP'


def parse_file(filepath):
    """
    Helper function to simplify parsing either DMP, DMP2, or PEM files.
    :param filepath: str or Path
    :return: PEMFile object.
    """
    filepath = Path(filepath)
    ext = filepath.suffix.lower()
    if ext == ".dmp" or ext == ".dmp2":
        dmp_parser = DMPParser()
        pem_file, errors = dmp_parser.parse(filepath)
    elif ext == ".pem":
        pem_parser = PEMParser()
        pem_file = pem_parser.parse(filepath)
    else:
        raise NotImplementedError(F"{ext.upper()} parsing not implemented.")

    return pem_file


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


def get_processed_angles(roll_data):
    """
    Correct roll angles so they are generally between 0-360 and don't flip back and forth between 360 and 0.
    :param roll_data: list, series or numpy array.
    :return: numpy array
    """
    def process_angle(reference_angle, angle):
        """
        Find the angle angle closest (by multiples of 360) to the base reference angle.
        :param reference_angle: float, angle to use as the base reference.
        :param angle: float
        :return: float
        """
        # print(f"Processing angle {angle:.2f} (avg. {average_angle:.2f}).")
        roll_minus = angle - 360
        roll_plus = angle + 360
        diff = abs(angle - reference_angle)
        diff_minus = abs(roll_minus - reference_angle)
        diff_plus = abs(roll_plus - reference_angle)
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

    if not roll_data.all():
        return roll_data
    # The first roll angle is used as the first "average"
    processed_roll_data = np.array([roll_data[0]])
    for roll in roll_data[1:]:
        processed_roll = process_angle(processed_roll_data[-1], roll)  # Works better than using average
        processed_roll_data = np.append(processed_roll_data, processed_roll)

    while all([r < 0 for r in processed_roll_data]):
        processed_roll_data = np.array(processed_roll_data) + 360
    while all([r >= 360 for r in processed_roll_data]):
        processed_roll_data = np.array(processed_roll_data) - 360

    return processed_roll_data


class PEMFile:
    """
    PEM file class
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

        self.original_coil_area = None  # For notes.
        self.original_current = None  # For notes.

        self.notes = None
        self.data = None
        self.filepath = None

        self.loop = TransmitterLoop(None)
        self.collar = BoreholeCollar(None)
        self.segments = BoreholeSegments(None)
        # self.geometry = None
        self.line = SurveyLine(None)
        self.crs = None

        self.total_scale_factor = 0.
        self.soa = 0  # For XY SOA rotation
        self.pp_table = None  # PP de-rotation information
        self.prepped_for_rotation = False
        self.legacy = False

    def from_pem(self, tags, loop_coords, line_coords, notes, header, channel_table, data, filepath=None):
        """
        Fill the information of the PEM file object from a parsed .PEM file.
        :param tags: dict, tags section of the PEM file
        :param loop_coords: list, loop coordinates
        :param line_coords: list, line/hole geometry coordinates
        :param notes: list, notes section
        :param header: dict, header section
        :param channel_table: DataFrame of the channel times
        :param data: DataFrame of the data
        :param filepath: str, filepath of the file
        :return: PEMFile object
        """
        self.format = tags.get('Format')
        self.units = tags.get('Units')
        self.operator = tags.get('Operator')
        self.probes = tags.get('Probes')
        self.soa = float(self.probes.get("SOA"))
        self.current = tags.get('Current')
        self.original_current = self.current
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
        self.original_coil_area = self.coil_area
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

    def from_dmp(self, header, channel_table, data, filepath, notes=None):
        """
        Create a PEMFile object from the contents of a parsed .DMP file.
        :param header: parsed dictionary of DMP header information
        :param channel_table: parsed DataFrame of the channel table in the DMP file
        :param data: parsed DataFrame of the data in the DMP file
        :param filepath: Path object of the DMP file.
        :param notes: parsed list of notes in the DMP file
        :return: PEMFile object
        """
        self.format = header.get('Format')
        self.units = header.get('Units')
        self.operator = header.get('Operator')
        self.probes = header.get('Probes')
        self.current = header.get('Current')
        self.original_current = header.get('Current')
        self.loop_dimensions = header.get('Loop dimensions')

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
        self.original_coil_area = header.get('Coil area')
        self.loop_polarity = header.get('Loop polarity')
        self.channel_times = channel_table
        self.number_of_channels = len(channel_table)

        if notes:
            self.notes = notes
        else:
            self.notes = []

        self.data = sort_data(data)
        # Add the deletion flag column
        if 'Deleted' not in self.data.columns:
            self.data.insert(13, 'Deleted', False)

        # Add the overload column
        if 'Overload' not in self.data.columns:
            self.data.insert(14, 'Overload', False)

        # Add the Timestamp column
        if 'Timestamp' not in self.data.columns:
            self.data.insert(15, 'Timestamp', None)

        self.filepath = filepath.with_suffix('.PEM')

        self.crs = self.get_crs()
        self.loop = TransmitterLoop(None, crs=self.crs)
        if self.is_borehole():
            self.collar = BoreholeCollar(None, crs=self.crs)
            self.segments = BoreholeSegments(None)
            # self.geometry = BoreholeGeometry(self.collar, self.segments)
        else:
            self.line = SurveyLine(None, crs=self.crs)

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
        Return the PEMFile's CRS, or create one from the note in the PEM file if it exists.
        :return: Proj CRS object
        """

        if self.crs:
            return self.crs

        else:
            for note in self.notes:
                if 'EPSG' in note:
                    epsg_code = re.search(r"EPSG:(\d+)", note.strip()).group(1)
                    crs = CRS.from_epsg(epsg_code)
                    logger.debug(f"{self.filepath.name} CRS is {crs.name}.")
                    return crs
                elif '<CRS>' in note:
                    crs_str = re.split('<CRS>', note)[-1].strip()
                    crs = CRS.from_string(crs_str)
                    logger.debug(f"{self.filepath.name} CRS is {crs.name}.")
                    return crs
                # For older PEM files that used the <GEN> tag
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
                    logger.debug(f"{self.filepath.name} CRS is {crs.name}")
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

        processed_azimuth_data = get_processed_angles(azimuth_data)

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
        assert all([self.has_xy(), self.is_borehole()]), \
            f"Can only get dip data from borehole surveys with XY components."

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
            raise ValueError(F"PEMFile must be prepped for de-rotation.")

        if not all([self.has_xy(), self.is_borehole()]):
            raise ValueError(F"PEMFile must be a borehole file with X and Y component readings.")

        data = self.data[(self.data.Component == "X") | (self.data.Component == "Y")]
        data = data.drop_duplicates(subset="RAD_ID")
        data.Station = data.Station.astype(float)
        data.sort_values("Station", inplace=True)

        if roll_type == "Acc":
            roll_data = get_processed_angles(data.RAD_tool.map(lambda x: x.acc_roll_angle + soa).to_numpy())
        elif roll_type == "Mag":
            roll_data = get_processed_angles(data.RAD_tool.map(lambda x: x.mag_roll_angle + soa).to_numpy())
        elif roll_type == "Tool":
            roll_data = get_processed_angles(data.RAD_tool.map(lambda x: x.angle_used + soa).to_numpy())
        elif roll_type == "Measured_PP":
            if not self.has_all_gps():
                raise ValueError(f"PEMFile must have all GPS for {roll_type} de-rotation.")
            roll_data = get_processed_angles(data.RAD_tool.map(lambda x: x.measured_pp_roll_angle).to_numpy())
        elif roll_type == "Cleaned_PP":
            if not self.has_all_gps():
                raise ValueError(f"PEMFile must have all GPS for {roll_type} de-rotation.")
            roll_data = get_processed_angles(data.RAD_tool.map(lambda x: x.cleaned_pp_roll_angle).to_numpy())
        elif roll_type == "All":
            mpp_roll_data = get_processed_angles(data.RAD_tool.map(lambda x: x.measured_pp_roll_angle).to_numpy())
            cpp_roll_data = get_processed_angles(data.RAD_tool.map(lambda x: x.cleaned_pp_roll_angle).to_numpy())
            acc_roll_data = get_processed_angles(data.RAD_tool.map(lambda x: x.acc_roll_angle + soa).to_numpy())
            mag_roll_data = get_processed_angles(data.RAD_tool.map(lambda x: x.mag_roll_angle + soa).to_numpy())
            df = pd.DataFrame.from_dict({"Station": data.Station.astype(int),
                                         "Acc": acc_roll_data,
                                         "Mag": mag_roll_data,
                                         "Measured PP": mpp_roll_data,
                                         "Cleaned PP": cpp_roll_data})
            return df
        else:
            raise ValueError(f"{roll_type} is not a valid de-rotation method.")

        df = pd.DataFrame.from_dict({"Station": data.Station, "Angle": roll_data})
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

    def get_offtime_channels(self):
        return self.channel_times[~self.channel_times.Remove.astype(bool)]

    def get_profile_data(self, averaged=False, converted=False, ontime=True, incl_deleted=False):
        """
        Transform the readings in the data in a manner to be plotted as a profile
        :param averaged: bool, average the readings of the profile
        :param converted: bool, convert the station names to int
        :param ontime: bool, keep the on-time channels
        :param incl_deleted: bool, include readings that are flagged as deleted
        :return: pandas DataFrame object with Station as the index, and channels as columns.
        """
        data = self.data

        if not incl_deleted:
            data = data[~data.Deleted.astype(bool)]

        if ontime is False:
            data.Reading = data.Reading.map(lambda x: x[~self.channel_times.Remove.astype(bool)])

        # Transform the data to profile format
        profile = pd.DataFrame.from_dict(dict(zip(data.Reading.index, data.Reading.values))).T

        if converted is True:
            stations = data.Station.map(convert_station)
        else:
            stations = data.Station

        profile.insert(0, 'Station', stations)
        # Insert the Component and Deleted columns
        profile.insert(1, 'Component', data.Component)
        profile.insert(2, 'Deleted', data.Deleted)
        # profile.set_index('Station', drop=True, inplace=True)

        if averaged is True:
            profile.drop(columns=["Deleted"], inplace=True)  # No need to keep the Deleted column for averaged data.
            profile = profile.groupby(['Station', 'Component'],
                                      group_keys=False,
                                      as_index=False).mean()

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
        Return the name of the PEMFile's file.
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
        Return a list of unique stations in the PEM file.
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

    def get_min_station(self):
        stations = self.get_stations(converted=True, incl_deleted=True)
        return stations.min()

    def get_max_station(self):
        stations = self.get_stations(converted=True, incl_deleted=True)
        return stations.max()

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
        Calculate the magnetic declination for the PEM file.
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
        # logger.info(f"Data ineligible for de-rotation:\n"
        #             f"{ineligible_stations.loc[:, ['Station', 'Reading_number', 'Reading_index']]}")
        return eligible_data, ineligible_stations

    def get_clipboard_info(self):
        """
        Copies the information of the PEMFile to the clipboard for the purposes of filling out the geophysicssheet.
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
            profile_data = self.get_profile_data(averaged=True,
                                                 converted=True,
                                                 ontime=True,
                                                 incl_deleted=True)
            for component in self.get_components():
                pp_data = profile_data[profile_data.Component == component].set_index(
                    'Station', drop=True).loc[:, pp_ch_num]

                # Only include common stations. PP represents the measured data, XYZ are theoretical.
                df = pd.concat([pp_data, theory_pp_data.loc[:, component]], axis=1).rename(
                    {pp_ch_num: 'Measured', component: "Theory"}, axis=1).dropna(axis=0)
                theory_pp = df.Theory.to_numpy()
                measured_pp = df.Measured.to_numpy()

                diff = np.abs(theory_pp - measured_pp)
                reversed_diff = np.abs(theory_pp - (measured_pp * -1))

                # Find how many diff values are greater in the flipped array than in the original. If more than half the
                # array is larger in the original, than it is probably incorrect.
                if len(np.where(diff > reversed_diff)[0]) > len(diff) * 0.5:
                    logger.info(f"{self.filepath.name} {component} component may be reversed.")
                    reversed_components.append(component)

                # print(f"Component: {component}\nDiff: {diff}\nReversed Diff: {reversed_diff}\n")
                # if abs(reversed_diff) < abs(diff):
                #     logger.info(f"{self.filepath.name} {component} component may be reversed.")
                #     reversed_components.append(component)
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
        new_path = self.filepath.with_name(new_name.upper()).with_suffix(".PEM")
        if new_path == self.filepath:
            return self.filepath

        if new_path.is_file():
            os.remove(str(new_path))
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
            new_name = re.sub(r"L|LINE", "", self.line_name.upper()).strip()
        self.line_name = new_name.upper()
        return self.line_name

    def set_crs(self, crs):
        """
        Set the CRS of all GPS objects
        :param crs: CRS object
        """
        logger.debug(f"Setting CRS of {self.filepath.name} to {crs.name if crs else 'None'}.")

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
            logger.debug(f"Converting GPS of {self.filepath.name} to {crs.name}.")
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
        Return the text format of the PEM file
        :param legacy: bool, if True will strip newer features so it is compatible with Step (such as D5 RAD tool
        lines and remove Timestamp and Deleted values.
        :return: str, Full text of the PEM file
        """
        ps = PEMSerializer()
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
        Create a str in XYZ format of the pem file's data
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
        pem_data = self.get_data(sorted=True).dropna(subset=['Station'])

        if self.is_borehole():
            gps = self.get_geometry().get_projection(stations=self.get_stations(converted=True))
            # Rename 'Relative_depth' to 'Station' for get_station_gps, so it matches with
            gps.rename(columns={'Relative_depth': 'Station'}, inplace=True)
        else:
            gps = self.get_line_gps(sorted=True).drop_duplicates('Station')

        # assert not self.is_borehole(), 'Can only create XYZ file with surface PEM files.'
        if gps.empty:
            raise Exception(f"Cannot create XYZ file with {self.filepath.name} because it has no GPS.")

        logger.info(f'Converting {self.filepath.name} to XYZ')

        df['Component'] = pem_data.Component.copy()
        df['Station'] = pem_data.Station.copy()
        df['c_Station'] = df.Station.map(convert_station)  # Used to find corresponding GPS

        # Add the GPS
        df = df.apply(get_station_gps, axis=1)

        # Create a dataframe of the readings with channel number as columns
        channel_data = pd.DataFrame(pem_data.Reading.to_dict()).transpose()

        # Merge the two data frames
        df = pd.concat([df, channel_data], axis=1).drop('c_Station', axis=1)
        str_df = df.to_string(index=False)
        return str_df

    def copy(self):
        """
        Create a copy of the PEMFile object
        :return: PEMFile object
        """
        copy_pem = copy.deepcopy(self)
        # Create a copy of the RAD Tool objects, otherwise a deepcopy of a PEMFile object still references the same
        # RADTool objects.
        copy_pem.data.RAD_tool = copy_pem.data.RAD_tool.map(lambda x: copy.deepcopy(x))
        return copy_pem

    def save(self, processed=False, legacy=False, backup=False, rename=False, tag=''):
        """
        Save the PEM file to a .PEM file with the same filepath it currently has.
        :param processed: bool, Average, split and de-rotate (if applicable) and save in a legacy format.
        :param legacy: bool, will save a legacy version which is compatible with Step.
        :param backup: bool, if the save is for a backup. If so, it will save the PEM file in a [Backup] folder,
        and create the folder if it doesn't exist. The [Backup] folder will be located in the parent directory of the
        PEMFile.
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
        Averages the data of the PEM file object. Uses a weighted average.
        :return: PEM file object
        """
        if self.is_averaged():
            logger.info(f"{self.filepath.name} is already averaged.")
            return
        logger.info(f"Averaging {self.filepath.name}.")

        def weighted_average(group):
            """
            Function to calculate the weighted average reading of a station-component group.
            :param group: pandas DataFrame of PEM data for a station-component
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
        Remove the on-time channels of the PEM file object
        :return: PEM file object with split data
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
        # Update the PEM file's number of channels attribute
        self.number_of_channels = len(self.channel_times)

        return self

    # def remove_channels(self, n: [int]):
    #     """
    #     Remove n channels from the PEMFile
    #     :return: PEM file object
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
    #     # Update the PEM file's number of channels attribute
    #     self.number_of_channels = len(self.channel_times)
    #
    #     return self

    def scale_coil_area(self, coil_area):
        """
        Scale the data by a change in coil area
        :param coil_area: float, new coil area
        :return: PEMFile object: self with data scaled
        """
        logger.info(f"Scaling coil area of {self.filepath.name} to {coil_area}.")

        new_coil_area = coil_area
        old_coil_area = float(self.coil_area)

        scale_factor = float(old_coil_area / new_coil_area)

        self.data.Reading = self.data.Reading * scale_factor  # Vectorized
        logger.info(f"{self.filepath.name} coil area scaled to {new_coil_area:.1f} from {old_coil_area:.1f}.")

        self.coil_area = new_coil_area

        for note in self.notes:
            if "Data scaled by coil area change of" in note:
                self.notes.remove(note)
        self.notes.append(f'<HE3> Data scaled by coil area change of {self.original_coil_area:.1f}/{new_coil_area:.1f}')
        return self

    def scale_current(self, current):
        """
        Scale the data by a change in current
        :param current: float, new current
        :return: PEMFile object, self with data scaled
        """
        new_current = current
        assert isinstance(new_current, float), "New current is not type float"
        logger.info(f"Performing current change for {self.filepath.name} to {current:.2f}.")

        old_current = float(self.current)

        scale_factor = float(new_current / old_current)

        self.data.Reading = self.data.Reading * scale_factor  # Vectorized
        self.current = new_current

        for note in self.notes:
            if "Data scaled by current change of" in note:
                self.notes.remove(note)
        self.notes.append(f'<HE3> Data scaled by current change of {new_current:.2f}A/{self.original_current:.2f}A')
        return self

    def scale_by_factor(self, factor):
        """
        Scale the data by a change in coil area
        :param factor: float
        :return: PEMFile object, self with data scaled
        """
        assert isinstance(factor, float), "New coil area is not type float"
        # Scale the scale factor to account for compounding
        scaled_factor = factor / (1 + self.total_scale_factor)

        self.data.Reading = self.data.Reading * (1 + scaled_factor)  # Vectorized
        logger.info(f"{self.filepath.name} data scaled by factor of {(1 + scaled_factor):.2f}.")

        self.total_scale_factor += factor

        self.notes.append(f'<HE3> Data scaled by factor of {1 + factor:.2f}')
        return self

    def mag_offset(self):
        """
        Subtract the last channel from the entire decay
        This will remove all amplitude information from the PEM!
        :return: PEMFile object, self with data scaled
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
        Change the station suffix of all data in the PEMFile to new_suffix. Only applies to surface surveys.
        :param new_suffix: str, either N, S, E, W
        :return: PEMFile object
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

    @timeit
    def rotate(self, method='acc', soa=0):
        """
        Rotate the XY data of the PEM file.
        Formula: X' = Xcos(roll) - Ysin(roll), Y' = Xsin(roll) + Ycos(roll)
        :param method: str, Method of rotation, either 'acc' for accelerometer or 'mag' for magnetic, or 'unrotate' if
        the file has been de-rotated.
        :param soa: int, Sensor offset angle
        :return: PEM file object with rotated data
        """
        assert self.is_borehole(), f"{self.filepath.name} is not a borehole file."

        if not self.prepped_for_rotation:
            logger.info(f"{self.filepath.name} has not been prepped for rotation.")
            self.prep_rotation()

        if method == "unrotate":
            assert self.is_derotated(), f"{self.filepath.name} has not been de-rotated."
            assert self.has_d7(), f"{self.filepath.name} RAD tool values must be D7."
        self.soa += soa
        logger.info(f"De-rotating data of {self.filepath.name} using {method} with SOA {self.soa}.")

        # @timeit
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
                        roll_angle = 0
                        r = None
                        dip = None
                        derotated = False

                    new_info = {'roll_angle': roll_angle,
                                'dip': dip,
                                'R': r,
                                'angle_used': roll_angle + self.soa,  # For derotated files, same as angle_used + soa
                                'derotated': derotated,
                                'rotation_type': 'soa'}
                    # print(new_info)

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
                :param group: pandas DataFrame of PEM data for a station-component
                :return: np array, averaged reading
                """
                # Sum the number of stacks column
                weights = group['Number_of_stacks'].to_list()
                # Add the weighted average of the readings to the reading column
                averaged_reading = np.average(group.Reading.to_list(),
                                              axis=0,
                                              weights=weights)
                return averaged_reading

            # Create a new RADTool object ready for de-rotating
            rad = group.iloc[0]['RAD_tool']  # Why do some RADs have no acc angle value?
            new_rad = get_new_rad(method)
            if method == "unrotate":
                roll_angle = rad.angle_used
                roll = -math.radians(roll_angle)
                new_rad.angle_used = None
            elif method is None:
                roll = math.radians(soa)
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
                raise ValueError("Cannot perform PP rotation on a PEM file that doesn't have the necessary geometry.")

        # Create a filter for X and Y data only
        xy_filt = (self.data.Component == 'X') | (self.data.Component == 'Y')
        xy_data = self.data[xy_filt]

        if xy_data.empty:
            raise Exception(f"{self.filepath.name} has no eligible XY data for de-rotation.")

        @timeit
        def apply_rotation():
            # Rotate the data
            rotated_data = xy_data.groupby(['Station', 'RAD_ID'],
                                           group_keys=False,
                                           as_index=False).apply(lambda l: rotate_group(l, method, soa))
            return rotated_data

        rotated_data = apply_rotation()

        @timeit
        def update_data():
            self.data.update(rotated_data)  # Fixes KeyError "... value not in index"

        update_data()
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

    @timeit
    def prep_rotation(self):
        """
        Prepare the PEM file for probe de-rotation by updating the RAD tool objects with all calculations needed for
        any eligible de-rotation method.
        :return: tuple, updated PEMFile object and data frame of ineligible stations.
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

            # global proj, loop, ramp, mag_calc, ch_times, ch_numbers

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

            return {"proj": proj,
                    "loop": loop,
                    "ramp": ramp,
                    "mag_calc": mag_calc,
                    "ch_times": ch_times,
                    "ch_numbers": ch_numbers}

        def prepare_rad(group, pp_info):
            """
            Update the RAD Tool object with all calculated angles for rotation.
            :param group: pandas DataFrame: data frame of the readings to rotate. Must contain at least one
            reading from X and Y components, and the RAD tool values for all readings must all be the same.
            :param pp_info: Dict, information needed to calculate PP angles.
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
                        :param row: PEM data DataFrame row
                        :return: float, cleaned PP value
                        """
                        # Get the list of ch_times indexes so the cleaned_pp can be selected by index.
                        # Needed for when channels are split before hand.
                        cleaned_pp_channels = pp_info.get("ch_times").index.to_list()

                        cleaned_pp = row.Reading[0]
                        for num in pp_info.get("ch_numbers"):
                            ind = cleaned_pp_channels.index(num)
                            cleaned_pp += row.Reading[ind]
                        return cleaned_pp

                    # Add the PP information (theoretical PP, cleaned PP, roll angle) to the new RAD Tool object
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
                    proj = pp_info.get("proj")
                    filt = proj.loc[:, 'Relative_depth'] == float(group.Station.iloc[0])
                    x_pos, y_pos, z_pos = proj[filt].iloc[0]['Easting'], \
                                          proj[filt].iloc[0]['Northing'], \
                                          proj[filt].iloc[0]['Elevation']

                    # Calculate the theoretical magnetic field strength of each component at that point (in nT/s)
                    mag_calc = pp_info.get("mag_calc")
                    Tx, Ty, Tz = mag_calc.calc_total_field(x_pos, y_pos, z_pos,
                                                           amps=self.current,
                                                           out_units='nT/s',
                                                           ramp=pp_info.get("ramp"))

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
                    # print(new_info)
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

                if include_pp is True:
                    calculate_pp_angles()
                calculate_acc_angles()
                calculate_mag_angles()
                return rad

            rad = group.iloc[0]['RAD_tool']
            # Calculate all the roll angles available and add it to the RAD tool object
            rad = calculate_angles(rad)
            group.RAD_tool = rad
            return group

        pp_info = {}
        if all([self.has_all_gps(), self.ramp > 0]):
            pp_info = setup_pp()
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
                                             as_index=False).apply(lambda l: prepare_rad(l, pp_info))

        # Don't use .update as the ineligible data will be kept in.
        xy_filt = (self.data.Component == 'X') | (self.data.Component == 'Y')
        self.data[xy_filt] = prepped_data

        # Remove the rows that were filtered out in filtered_data
        # Resetting the index prevents the error IndexError: single positional indexer is out-of-bounds
        self.data = self.data.dropna(subset=['Station']).reset_index(drop=True)
        self.prepped_for_rotation = True
        return self, ineligible_data


class PEMParser:
    """
    Class for parsing PEM files into PEMFile objects
    """
    def __init__(self):
        self.filepath = None

    def parse(self, filepath):
        """
        Parses a PEM file to extract all information and creates a PEMFile object out of it.
        :param filepath: string containing path to a PEM file
        :return: A PEM_File object representing the data found inside of filename
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
            Parse the loop section (<L> tags) of the PEM File
            :param text: str, raw loop string from the PEM file
            :return: list of everything in the <L> tag section
            """
            assert text, f'Error parsing the loop coordinates. No matches were found in {self.filepath.name}.'

            text = text.strip().split('\n')
            loop_text = [t.strip().split() for t in text if t.startswith('<L')]
            return loop_text

        def parse_line(text):
            """
            Parse the line section (<P> tags) of the PEM File
            :param text: str, raw line string from the PEM file
            :return: list of everything in the <P> tag section
            """
            assert text, f'Error parsing the line coordinates. No matches were found in {self.filepath.name}.'

            text = text.strip().split('\n')
            line_text = [t.strip().split() for t in text if t.startswith('<P')]
            return line_text

        def parse_notes(file):
            """
            Parse the notes of the PEM File, which are any lines with <GEN> or <HE> tags.
            :param file: str of the .PEM file
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
            Parse the header section of the PEM File, which is the client name down to the channel table.
            :param text: str, raw header string from the PEM file
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
            Create a DataFrame of the channel times from the PEM file.
            :param text: str, channel times section in the PEM file, above the data section.
            :param units: str, nT/s or pT, used to know which channel is the ramp channel.
            :param num_channels: int, number of channels indicated in the PEM file header. Used to make sure all
            channels are accounted for.
            :param ramp: float, ramp length.
            :return: DataFrame
            """
            def channel_table(channel_times, units, ramp):
                """
                Channel times table data frame with channel start, end, center, width, and whether the channel is
                to be removed when the file is split
                :param channel_times: pandas Series, float of each channel time read from a PEM file header.
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

                # PEM files seem to always have a repeating channel time as the third number, so the second row
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
            Parse the data section of the PEM file.
            :param text: str, data section after the '$' in the PEM file
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
                :param reading: str of a reading in a PEM file
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

        pem_file = PEMFile().from_pem(tags, loop_coords, line_coords, notes, header, channel_table, data,
                                      filepath=filepath)
        return pem_file


class DMPParser:
    def __init__(self):
        """
        Class that parses .DMP and .DMP2 files into PEMFile objects.
        """
        self.filepath = None
        self.pp_file = False

        self.data_columns = [
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
            'Reading'
        ]

    def parse_dmp(self, filepath):
        """
        Create a PEMFile object by parsing a .DMP file.
        :param filepath: str, filepath of the .DMP file
        :return: PEMFile object
        """

        def parse_header(text, old_dmp=False):
            """
            Create the header dictionary that is found in PEM files from the contents of the .DMP file.
            :param text: str or list, header section of the .DMP file.
            :param old_dmp: bool, if the file is an old version of the DMP file which lacks two lines.
            :return: dict
            """
            assert text, f'No header found in {self.filepath.name}.'

            if isinstance(text, str):
                text = text.strip().split('\n')
            text = [t.strip() for t in text]

            if old_dmp is True:
                assert len(text) == 27, f'Incorrect number of lines found in the header of {self.filepath.name}'
            else:
                assert len(text) == 29, f'Incorrect number of lines found in the header of {self.filepath.name}'

            if text[-1] == 'ZTS - Narrow':
                self.pp_file = True
            else:
                self.pp_file = False

            header = dict()
            header['Format'] = str(210)
            header['Units'] = 'pT' if 'flux' in text[6].lower() or 'squid' in text[6].lower() else 'nT/s'
            header['Operator'] = text[11]
            header['Probes'] = {'Probe number': '0', 'SOA': '0', 'Tool number': '0', 'Tool ID': '0'}
            header['Current'] = float(text[12])
            header['Loop dimensions'] = ' '.join(re.split(r'\D', text[13])) + ' 0'

            header['Client'] = text[8]
            header['Grid'] = text[9]
            header['Line_name'] = text[7]
            header['Loop_name'] = text[10]
            header['Date'] = datetime.strptime(re.sub(r'\s+', '', text[14]), '%m/%d/%y').strftime('%B %d, %Y')
            header['Survey type'] = re.sub('\s+', '_', text[6].casefold())
            header['Convention'] = text[15]
            header['Sync'] = text[18]
            header['Timebase'] = float(text[16].split('ms')[0]) if 'ms' in text[16] else float(text[16].split()[0])
            header['Ramp'] = float(text[17])
            header['Number of channels'] = int(text[25])
            header['Number of readings'] = int(text[24])
            header['Receiver number'] = text[1].split()[-1]
            header['Rx software version'] = text[2].split()[-1]
            header['Rx software version date'] = re.sub(r'\s', '',
                                                        re.sub('Released: ', '', text[3])) + f"s{text[26]}"
            header['Rx file name'] = text[5]
            header['Normalized'] = 'N' if text[19] == 'Norm.' else 'Normalized??'
            header['Primary field value'] = text[23]
            header['Coil area'] = float(text[20])
            header['Coil delay'] = int(text[21])
            header['Loop polarity'] = '+'

            return header

        def parse_channel_times(text, units=None, ramp=None):
            """
            Convert the channel table in the .DMP file to a PEM channel times table DataFrame
            :param text: str or list, raw channel table information in the .DMP file
            :param units: str, 'nT/s' or 'pT'
            :return: DataFrame
            """

            def channel_table(channel_times, units, ramp):
                """
                Channel times table data frame with channel start, end, center, width, and whether the channel is
                to be removed when the file is split
                :param channel_times: numpy array with shape (, 2), float of each channel start and end time.
                :param units: str
                :param ramp: float, used for fluxgate survey's on-time channel selection.
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
                times = channel_times

                # The first number to the second last number are the start times
                table['Start'] = times[:, 0] / 10 ** 6  # Convert to seconds
                # The second number to the last number are the end times
                table['End'] = times[:, 1] / 10 ** 6  # Convert to seconds
                table['Width'] = table['End'] - table['Start']
                table['Center'] = (table['Width'] / 2) + table['Start']
                table['Remove'] = False

                if self.pp_file is False:
                    # Configure which channels to remove for the first on-time
                    table = get_split_table(table, units, ramp)

                    # Configure each channel after the last off-time channel (only for full waveform)
                    last_off_time_channel = find_last_off_time()
                    if last_off_time_channel:
                        table.loc[last_off_time_channel:, 'Remove'] = table.loc[last_off_time_channel:, 'Remove'].map(
                            lambda x: True)
                    # else:
                    #     table['Remove'] = False
                return table

            assert text, f'No channel times found in {self.filepath.name}.'

            text = text.strip().split('\n')
            # text = np.array([t.strip().split() for t in text], dtype=float)
            text = np.array(' '.join([t.strip() for t in text]).split(), dtype=float)

            # elif isinstance(text, list):
            #     text = np.array(text)

            # Reshape the channel times to be 3 columns (channel number, start-time, end-time)
            times = text.reshape((int(len(text) / 3), 3))

            # Used to add the gap channel, but not sure if needed.
            if self.pp_file is False:
                # Find the index of the gap 0 channel
                global ind_of_0  # global index since the 0 value must be inserted into the decays
                ind_of_0 = list(times[:, 0]).index(1)
                # Add the gap channel
                times = np.insert(times, ind_of_0, [0., times[ind_of_0 - 1][2], 0.], axis=0)

            # Remove the channel number column
            times = np.delete(times, 0, axis=1)

            table = channel_table(times, units, ramp)
            return table

        def parse_notes(text):
            """
            Return a list of notes from the .DMP file, excluding 'xxxxxxxxxxxxxxxx' entries.
            :param text: str or list, raw test from the notes section of the .DMP file.
            :return: list of notes
            """
            if isinstance(text, str):
                text = text.split()

            notes = []
            for item in text:
                # Get rid of the 'xxxxxxxxxxxxxxxx' notes
                if 'xxx' not in item.lower():
                    notes.append(item)
            return notes

        def parse_data(text, header):
            """
            Create the PEM file DataFrame of the data in the .DMP file
            :param text: str, raw string of the data section of the .DMP file
            :param header: dict, the parsed header section of the .DMP file
            :return: DataFrame
            """

            def format_data(reading):
                """
                Format the data row so it is ready to be added to the data frame
                :param reading: str of a reading in a PEM file
                :return: list
                """
                contents = reading.split('\n')

                head = contents[0].split()
                station = head[0]
                comp = head[1][0]
                reading_index = re.search(r'\d+', head[1]).group()
                zts = float(head[2]) + ramp
                number_of_stacks = head[3]
                readings_per_set = head[4]
                reading_number = head[5]
                rad_tool = contents[1]

                # Used to add the gap channel, but not sure if needed.
                # if self.pp_file is True:
                #     decay = np.array(''.join(contents[2:]).split(), dtype=float) * 10 ** 9
                # else:

                # Add the 0 gap
                if self.pp_file is False:
                    decay = ' '.join(
                        np.insert(np.array(''.join(contents[2:]).split(), dtype=float), ind_of_0, 0.0).astype(str)
                    )
                else:
                    decay = ''.join(contents[2:])

                return [station, comp, reading_index, gain, rx_type, zts, coil_delay, number_of_stacks,
                        readings_per_set, reading_number, rad_tool, decay]

            assert text, f'No data found in {self.filepath.name}.'

            if isinstance(text, list):
                text = '\n'.join(text)

            # Reading variables that are sourced from outside the data section of the .DMP file
            global rx_type, gain, coil_delay, ramp
            rx_type = 'A'
            gain = 0
            coil_delay = header.get('Coil delay')
            ramp = header.get('Ramp')

            # Replace the spaces infront of station names with a tab character, to more easily split after
            text = re.sub(r'\s{3,}(?P<station>[\w]{1,}\s[XYZ])', r'\t\g<station>', text.strip())
            text = text.split('\t')

            data = []
            for reading in text:
                # Parse the data row and create a Series object to be inserted in the data frame
                # series = parse_row(reading)
                data.append(format_data(reading))

            df = pd.DataFrame(data, columns=self.data_columns)

            # Convert the columns to their correct data types
            df['RAD_tool'] = df['RAD_tool'].map(lambda x: RADTool().from_dmp(x))
            df['RAD_ID'] = df['RAD_tool'].map(lambda x: x.id)

            # Convert the decay units to nT/s or pT
            factor = 1e9  # Always 1e9 for DMP files?
            df.drop_duplicates(subset="Reading", inplace=True)
            df['Reading'] = df['Reading'].map(lambda x: np.array(x.split(), dtype=float) * factor)
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
            return df

        if isinstance(filepath, str):
            filepath = Path(filepath)

        assert filepath.is_file(), f"{filepath.name} is not a file"
        self.filepath = filepath
        logger.info(f"Parsing {self.filepath.name}.")

        # Read the contents of the file
        with open(filepath, 'rt') as file:
            contents = file.read()

        # Split the content up into sections
        # Splitting new .DMP files
        if '&&' in contents:
            logger.info(f"{self.filepath.name} is a new style DMP file.")
            old_dmp = False
            raw_header = re.split('&&', contents)[0].strip()
            raw_channel_table = re.split('<<', re.split(r'\$\$', contents)[0])[1].strip()
            raw_notes = re.split('<<', re.split('&&', contents)[1])[0].strip()  # The content between '&&' and '<<'
            raw_data = re.split(r'\$\$', contents)[1].strip()

            # Don't see any notes in old .DMP files so only included here
            notes = parse_notes(raw_notes)

        # Splitting old .DMP files
        else:
            logger.info(f"{self.filepath.name} is an old style DMP file.")
            old_dmp = True
            scontents = contents.split('\n')
            num_ch = int(scontents[25].strip())

            raw_header = scontents[:27]
            raw_channel_table = '\n'.join(scontents[27:27 + math.ceil(num_ch / 2)]).strip()
            raw_data = '\n'.join(scontents[27 + math.ceil(num_ch / 2):]).strip()

            notes = []

        if not raw_header:
            raise ValueError(f'No header found in {self.filepath.name}.')
        elif not raw_data:
            raise ValueError(f'No data found in {self.filepath.name}.')

        # Parse the sections into nearly what they should be in the PEM file
        header = parse_header(raw_header, old_dmp=old_dmp)
        channel_table = parse_channel_times(raw_channel_table, units=header.get('Units'), ramp=header.get("Ramp"))
        data = parse_data(raw_data, header)

        header_readings = int(header.get('Number of readings'))
        if len(data) != header_readings:
            logger.warning(f"{self.filepath.name}: Header claims {header_readings} readings but {len(data)} was found.")

        pem_file = PEMFile().from_dmp(header, channel_table, data, self.filepath, notes=notes)
        return pem_file, pd.DataFrame()  # Empty data_error data frame. Errors not implemented yet for .DMP files.

    def parse_dmp2(self, filepath):
        """
        Create a PEMFile object by parsing a .DMP2 file.
        :param filepath: str, filepath of the .DMP2 file
        :return: PEMFile object
        """
        def parse_channel_times(units, ramp):
            """
            Convert the channel table in the .DMP file to a PEM channel times table DataFrame
            :param units: str, 'nT/s' or 'pT'
            :return: DataFrame
            """
            def channel_table(channel_times):
                """
                Channel times table data frame with channel start, end, center, width, and whether the channel is
                to be removed when the file is split
                :param channel_times: pandas Series, float of each channel time read from a PEM file header.
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
                table['Remove'] = False

                # If the file isn't a PP file
                if not table.Width.max() < 1e-4:
                    # Configure which channels to remove
                    table = get_split_table(table, units, ramp)

                    # Configure each channel after the last off-time channel (only for full waveform)
                    last_off_time_channel = find_last_off_time()
                    if last_off_time_channel:
                        table.loc[last_off_time_channel:, 'Remove'] = table.loc[last_off_time_channel:, 'Remove'].map(
                            lambda x: True)
                return table

            table = channel_table(header['Channel_times'] / 10 ** 6)  # Convert to seconds
            header_channels = int(header['Number of channels'])
            assert len(table) == header_channels or len(table) == header_channels + 1, \
                f"{self.filepath.name}: Header claims {header_channels} channels but {len(table)} found."
            return table

        def parse_header(header_content):
            """
            Parse the header section of the DMP File
            :param header_content: list of str of the header section of the .DMP2 file
            :return: dict
            """
            header_content = header_content.split('\n')
            # Remove blank lines
            [header_content.remove(h) for h in reversed(header_content) if h == '']
            ind, val = [h.split(':')[0].strip() for h in header_content], [h.split(':')[1].strip() for h in
                                                                           header_content]

            # Create a Series object
            s = pd.Series(val, index=ind)

            s['Channel_Number'] = np.array(s['Channel_Number'].split(), dtype=int)
            s['Channel_Time'] = np.array(s['Channel_Time'].split(), dtype=float)

            # Create the header dictionary
            header = dict()
            header['Format'] = '210'
            header['Units'] = 'pT' if 'flux' in s['Survey_Type'].lower() or 'squid' in s[
                'Survey_Type'].lower() else 'nT/s'
            header['Operator'] = s['Operator_Name'].title()
            header['Probes'] = {'Probe number': s['Sensor_Number'],
                                'SOA': '0',
                                'Tool number': s['Tool_Number'],
                                'Tool ID': '0'}
            header['Current'] = float(s['Current'])

            header['Channel_times'] = s['Channel_Time']
            header['Channel_numbers'] = s['Channel_Number']
            header['Loop dimensions'] = f"{s['Loop_Length']} {s['Loop_Width']} 0"

            header['Client'] = s['Client_Name']
            header['Grid'] = s['Grid_Name']
            header['Line_name'] = s['name']
            header['Loop_name'] = s['Loop_Name']
            header['Date'] = date_str

            header['Survey type'] = re.sub(r'\s+', '_', s['Survey_Type'])
            header['Convention'] = 'Metric'
            header['Sync'] = re.sub(r'\s+', '-', s['Sync_Type'])
            # Some DMP2 files can have just "Crystal" as sync type, which causes issues with Step.
            if header['Sync'] == "Crystal":
                header['Sync'] = "Crystal-Master"
            header['Timebase'] = float(s['Time_Base'].split()[0])
            header['Ramp'] = float(s['Ramp_Length'])
            header['Number of channels'] = len(s['Channel_Time']) - 1
            header['Number of readings'] = int(s['Total_Readings'])

            header['Receiver number'] = s['Crone_Digital_PEM_Receiver']
            header['Rx software version'] = s['Software_Version']
            header['Rx software version date'] = re.sub(r'\s+', '', s['Software_Release_Date'])
            header['Rx file name'] = re.sub(r'\s+', '_', s['File_Name'])
            header['Normalized'] = 'N'
            header['Primary field value'] = '1000'

            coil_area = float(s['Coil_Area'])
            if coil_area > 50000:
                coil_area = coil_area / 10 ** 3  # For fluxgate files
            header['Coil area'] = coil_area
            header['Loop polarity'] = '+'
            # TODO Find how notes are saved in .DMP2 files
            # header['Notes'] = [note for note in s['File_Notes'].split('\n')]

            return header

        def parse_data(data_content, units=None):
            """
            Create a PEM file data frame from the contents of the .DMP2 file
            :param data_content: list of str of the data section of the .DMP2 file
            :param units: str, 'nT/s' or 'pT'
            :return: DataFrame
            """
            def str_to_datetime(date_string):
                """
                Convert the timestamp string to a datetime object
                :param date_string: str of the timestamp from the .DMP2 file.
                :return: datetime object
                """
                if '-' in date_string:
                    if 'AM' in date_string or 'PM' in date_string:
                        fmt = '%Y-%m-%d,%I:%M:%S %p'
                    else:
                        fmt = '%Y-%m-%d,%H:%M:%S'
                else:
                    year = re.search(r'(\d+\W\d+\W)(\d+)', date_string).group(2)
                    if len(year) == 2:
                        year_fmt = 'y'
                    else:
                        year_fmt = 'Y'

                    if 'AM' in date_string or 'PM' in date_string:
                        fmt = f'%m/%d/%{year_fmt},%I:%M:%S %p'
                    else:
                        fmt = f'%m/%d/%{year_fmt},%H:%M:%S'
                date_object = datetime.strptime(date_string, fmt)
                return date_object

            assert data_content, f'No data found in {self.filepath.name}.'

            data_section = data_content.strip()
            split_data = data_section.split('\n\n')

            # Create a data frame out of the readings
            df_data = []
            for reading in split_data:
                split_reading = reading.split('\n')

                # Header information
                arr = [re.split(r':\s?', d, maxsplit=1) for d in split_reading if
                       not d.lower().startswith('data') and
                       not d.lower().startswith('overload') and
                       not d.lower().startswith('deleted')]

                # Separate the decay reading, overload and deleted status that should be their own readings
                decays = [x for x in split_reading if x.startswith('data')]
                overloads = [x for x in split_reading if x.lower().startswith('overload')]
                deletes = list(filter(lambda x: x.startswith('Deleted'), split_reading))[0].split(': ')[1].split(',')

                # Iterate over each actual decay readings and create their own dictionary to be added to the df
                for decay, overload, deleted in zip(decays, overloads, deletes):
                    entry = dict(arr)  # The base information that is true for each reading
                    decay_values = decay.split(': ')[1]
                    if not decay_values:
                        logger.warning(f"Empty decay found for {entry['name']}, reading number {entry['Reading_Number']}")
                        continue
                    entry['data'] = decay_values
                    entry['Component'] = decay[4].upper()  # The component is the 4th character in the 'data' title

                    entry['Overload'] = overload.split(': ')[1]
                    entry['Deleted'] = deleted.strip()

                    df_data.append(entry)

            df = pd.DataFrame(df_data)
            df.drop_duplicates(subset="data", inplace=True)
            # Convert the columns to the correct data type
            df[['Number_of_Readings',
                'Number_of_Stacks',
                'Reading_Number',
                'ZTS_Offset']] = df[['Number_of_Readings',
                                     'Number_of_Stacks',
                                     'Reading_Number',
                                     'ZTS_Offset']].astype(int)

            # Convert the decays from Teslas to either nT or pT, depending on the survey type
            factor = 10 ** 12 if units == 'pT' else 10 ** 9
            df['data'] = df['data'].map(lambda x: np.array(x.split(), dtype=float) * factor)
            if 'RAD' in df.columns.values:
                df['RAD'] = df['RAD'].map(lambda x: RADTool().from_dmp(x))
            else:
                logger.warning(f"No RAD tool data found in {self.filepath.name}. Creating 0s instead.")
                df['RAD'] = RADTool().from_dmp('0. 0. 0. 0. 0. 0. 0.')

            pem_df = pd.DataFrame(columns=self.data_columns)
            pem_df['Station'] = df['name'].map(lambda x: x.split(',')[0])
            pem_df['Component'] = df['Component']
            pem_df['Reading_index'] = df['name'].map(lambda x: x.split(',')[-1][1:]).astype(int)
            pem_df['Gain'] = 0
            pem_df['Rx_type'] = 'A'
            pem_df['ZTS'] = df['ZTS_Offset']
            pem_df['Coil_delay'] = 0
            pem_df['Number_of_stacks'] = df['Number_of_Stacks']
            pem_df['Readings_per_set'] = df['Number_of_Readings']
            pem_df['Reading_number'] = df['Reading_Number']
            pem_df['RAD_tool'] = df['RAD']
            pem_df['Reading'] = df['data']
            pem_df['RAD_ID'] = pem_df['RAD_tool'].map(lambda x: x.id)
            pem_df['Deleted'] = df['Deleted'].map(lambda x: False if x.strip() == 'F' else True)
            pem_df['Overload'] = df['Overload'].map(lambda x: False if x.strip() == 'F' else True)

            # Set the overload readings to be deleted
            overload_filt = pem_df.loc[:, 'Overload']
            pem_df.loc[overload_filt, 'Deleted'] = True

            pem_df['Timestamp'] = df['Date_Time'].map(str_to_datetime)

            # Remove Inf readings
            inf_filt = pem_df.Reading.map(lambda x: np.isinf(x).any())
            inf_readings = pem_df[inf_filt]
            if not inf_readings.empty:
                logger.error(f"Following stations had Inf readings: "
                             f"\n{inf_readings.loc[:, ['Station', 'Component', 'Reading_number']].to_string()}")

            pem_df = pem_df[~inf_filt]
            return pem_df, inf_readings

        if isinstance(filepath, str):
            filepath = Path(filepath)

        assert filepath.is_file(), f"{filepath.name} does not exist."
        self.filepath = filepath
        logger.info(f"Parsing {self.filepath.name}.")

        # Read the contents of the file
        with open(filepath, 'rt') as file:
            contents = file.read()
            # Change the different occurences of header titles between DMP2 file versions so they are the same.
            contents = re.sub('isDeleted', 'Deleted', contents)
            if not re.search('Loop_Length', contents):
                contents = re.sub('Loop_Height', 'Loop_Length', contents)
            contents = re.sub('Released', 'Software_Release_Date', contents)

            # Find the year of the date of the file, and if necessary convert the year format to %Y instead of %y
            date = re.search(r'Date: (\d+\W\d+\W\d+)', contents).group(1)

            # If date is separated with hyphens, the date format is Y-m-d instead of m-d-y
            if '-' in date:
                date_str = datetime.strptime(date, '%Y-%m-%d').strftime('%B %d, %Y')
            else:
                year = re.search(r'(\d+\W\d+\W)(\d+)', date).group(2)

                # Replace the year to be 20xx
                if len(year) < 4:
                    Y = int(year) + 2000
                    date = re.sub(r'(\d+\W\d+\W)(\d+)', f'\g<1>{Y}', date)

                date_str = datetime.strptime(date, '%m/%d/%Y').strftime('%B %d, %Y')

        # Split the file up into the header and data sections
        scontents = contents.split('$$')
        if not scontents[0].strip():
            raise ValueError(f'No header found in {self.filepath.name}.')
        elif not scontents[1].strip():
            raise ValueError(f'No data found in {self.filepath.name}.')

        header = parse_header(scontents[0])
        data, data_errors = parse_data(scontents[1], units=header.get('Units'))
        channel_table = parse_channel_times(header.get('Units'), header.get("Ramp"))
        # notes = header['Notes']

        pem_file = PEMFile().from_dmp(header, channel_table, data, self.filepath)
        return pem_file, data_errors

    def parse(self, filepath):
        """
        Parse a .DMP file, including .DMP2+.
        :param filepath: str or Path object of the DMP file
        :return: PEMFile object
        """
        if isinstance(filepath, str):
            filepath = Path(filepath)
        assert filepath.is_file(), f"{filepath} does not exist."

        if filepath.suffix.lower() == '.dmp':
            pem_file, inf_errors = self.parse_dmp(filepath)
        elif filepath.suffix.lower() == '.dmp2':
            pem_file, inf_errors = self.parse_dmp2(filepath)
        else:
            raise NotImplementedError(f"Parsing {filepath.suffix} files not implemented yet.")

        return pem_file, inf_errors


class PEMSerializer:
    """
    Class for serializing PEM files to be saved
    """
    def __init__(self):
        self.pem_file = None

    def serialize_tags(self):
        format_boilerplate = "~ data format"
        units_boilerplate = "~ data units"
        operator_boilerplate = "~ operator's name"
        probe_boilerplate = "~ probe #, SOA, tool or RAD #, tool id"
        current_boilerplate = "~ peak current in loop"
        loop_size_boilerplate = "~ loop size (x y units) (units: 0 = m, 1 = ft)"

        result = ""
        xyp = ' '.join([self.pem_file.probes.get('Probe number'),
                        self.pem_file.probes.get('SOA'),
                        self.pem_file.probes.get('Tool number'),
                        self.pem_file.probes.get('Tool ID')])
        # Force 230, as sometimes 210 is entered and causes issues with Maxwell
        result += f"<FMT> {self.pem_file.format:<37}{format_boilerplate}\n"
        result += f"<UNI> {'nanoTesla/sec' if self.pem_file.units == 'nT/s' else 'picoTesla':<37}{units_boilerplate}\n"
        result += f"<OPR> {self.pem_file.operator:<37}{operator_boilerplate}\n"
        result += f"<XYP> {xyp:<37}{probe_boilerplate}\n"
        result += f"<CUR> {self.pem_file.current:<37}{current_boilerplate}\n"
        result += f"<TXS> {self.pem_file.loop_dimensions:<37}{loop_size_boilerplate}"

        return result

    def serialize_loop_coords(self):
        loop_boilerplate = ["~ x y z units", "~ units=0: m", "~ units=1: ft"]
        result = '~ Transmitter Loop Co-ordinates:'
        loop = self.pem_file.get_loop_gps()
        units_code = self.pem_file.loop.get_units_code()
        assert units_code, f"No units code for the loop of {self.pem_file.get_file_name()}."
        if loop.empty:
            result += '\n<L00>\n''<L01>\n''<L02>\n''<L03>'
        else:
            loop.reset_index(inplace=True)
            for i, row in enumerate(loop.itertuples()):
                tag = f"<L{row.Index:02d}>"
                row = f"{tag} {row.Easting:.2f} {row.Northing:.2f} {row.Elevation:.2f} {units_code}"
                if i < len(loop_boilerplate):
                    row = f"{row:<43}{loop_boilerplate[i]}"
                result += '\n' + row
        return result

    def serialize_line_coords(self):
        def serialize_station_coords():
            result = '~ Hole/Profile Co-ordinates:'
            line = self.pem_file.get_line_gps()
            units_code = self.pem_file.line.get_units_code()
            assert units_code, f"No units code for the line of {self.pem_file.get_file_name()}."
            if line.empty:
                rows = ['<P01>',
                        '<P02>',
                        '<P03>',
                        '<P04>',
                        '<P05>']
                for i, row in enumerate(rows):
                    if i < len(profile_boilerplate):
                        row = f"{row:<43}{profile_boilerplate[i]}"
                    result += '\n' + row
            else:
                line.reset_index(inplace=True)
                for i, row in enumerate(line.itertuples()):
                    tag = f"<P{row.Index:02d}>"
                    row = f"{tag} {row.Easting:.2f} {row.Northing:.2f} {row.Elevation:.2f} {units_code} {row.Station}"
                    if i < len(profile_boilerplate):
                        row = f"{row:<43}{profile_boilerplate[i]}"
                    result += '\n' + row
            return result

        def serialize_collar_coords():
            result = '~ Hole/Profile Co-ordinates:'
            collar = self.pem_file.get_collar_gps()
            collar.reset_index(drop=True, inplace=True)
            units_code = self.pem_file.collar.get_units_code()
            assert units_code, f"No units code for the collar of {self.pem_file.get_file_name()}."
            if collar.empty:
                result += '\n' + f"{'<P00>:<43'}{profile_boilerplate[0]}"
            else:
                for row in collar.itertuples():
                    tag = f"<P{row.Index:02d}>"
                    row = f"{tag} {row.Easting:.2f} {row.Northing:.2f} {row.Elevation:.2f} {units_code}"
                    row = f"{row:<43}{profile_boilerplate[0]}"
                    result += '\n' + row
            return result

        def serialize_segments():
            result = ''
            segs = self.pem_file.get_segments()
            segs.reset_index(drop=True, inplace=True)
            units_code = self.pem_file.segments.get_units_code()
            assert units_code, f"No units code for the segments of {self.pem_file.get_file_name()}."
            if segs.empty:
                rows = ['<P01>',
                        '<P02>',
                        '<P03>',
                        '<P04>',
                        '<P05>']
                for i, row in enumerate(rows):
                    if i < len(profile_boilerplate) - 1:
                        row = f"{row:<43}{profile_boilerplate[i - 1]}"  # -1 since the first item is added to collar
                    result += '\n' + row
            else:
                for i, row in enumerate(segs.itertuples()):
                    tag = f"<P{row.Index + 1:02d}>"
                    row = f"{tag} {row.Azimuth:.2f} {row.Dip:.2f} {row[3]:.2f} {units_code} {row.Depth:.2f}"
                    if i < len(profile_boilerplate) - 1:
                        row = f"{row:<43}{profile_boilerplate[i - 1]}"  # -1 since the first item is added to collar
                    result += '\n' + row
            return result

        profile_boilerplate = ["~ 4 or 5 numbers:  X Y Z Units Stn",
                               "~  Units=0 (m) or 1 (ft).",
                               "~ Surface: Stn -ve for West & South.",
                               "~ BH: after <P00> for collar coords,",
                               "~  can define hole segments with:",
                               "~  Az Dip Length Units Depth",
                               "~  Dip +ve down. Units =2(m) =3(ft).",
                               "~  Depth: Length sum to segment end.",
                               "~ BH: Stn and Depth are optional."]

        if self.pem_file.is_borehole():
            return serialize_collar_coords() + \
                   serialize_segments()
        else:
            return serialize_station_coords()

    def serialize_notes(self):
        results = []
        if not self.pem_file.notes:
            return ''
        else:
            for line in self.pem_file.notes:
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

        survey_type = self.pem_file.get_survey_type()
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

        result_list = [str(self.pem_file.client),
                       str(self.pem_file.grid),
                       str(self.pem_file.line_name),
                       str(self.pem_file.loop_name),
                       str(self.pem_file.date),
                       ' '.join([survey_str,
                                 str(self.pem_file.convention),
                                 str(self.pem_file.sync),
                                 str(self.pem_file.timebase),
                                 str(int(self.pem_file.ramp)),
                                 str(self.pem_file.number_of_channels - 1),
                                 str(int(self.pem_file.number_of_readings))]),
                       ' '.join([str(self.pem_file.rx_number),
                                 str(self.pem_file.rx_software_version),
                                 str(self.pem_file.rx_software_version_date),
                                 str(self.pem_file.rx_file_name),
                                 str(self.pem_file.normalized),
                                 str(self.pem_file.primary_field_value),
                                 str(int(self.pem_file.coil_area))])]

        if self.pem_file.loop_polarity is not None:
            result_list[-1] += ' ' + self.pem_file.loop_polarity

        result = '\n'.join(result_list) + '\n\n'

        times_per_line = 7
        cnt = 0

        times = get_channel_times(self.pem_file.channel_times)
        channel_times = [f'{time:9.6f}' for time in times]

        for i in range(0, len(channel_times), times_per_line):
            line_times = channel_times[i:i + times_per_line]
            result += ' '.join([str(time) for time in line_times]) + '\n'
            cnt += 1

        result += '$'
        return result

    def serialize_data(self, legacy=False):
        """
        Print the data to text for a PEM file format.
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

            channel_readings = [f'{r:10.3f}' for r in reading['Reading']]

            for i in range(0, len(channel_readings), readings_per_line):
                readings = channel_readings[i:i + readings_per_line]
                result += ' '.join([str(r) + max(0, reading_spacing - len(r)) * ' ' for r in readings]) + '\n'
                count += 1

            return result + '\n'

        df = self.pem_file.get_data(sorted=True)

        # Remove deleted readings
        filt = ~df.Deleted.astype(bool)
        df = df[filt]
        if df.empty:
            logger.warning(f"No valid data found to print in {self.pem_file.filepath.name}.")
            return ""
        else:
            return ''.join(df.apply(serialize_reading, axis=1))

    def serialize(self, pem_file, legacy=False):
        """
        Create a string of a PEM file to be printed to a text file.
        :param pem_file: PEM_File object
        :param legacy: bool, if True will strip newer features so it is compatible with Step (such as D5 RAD tool
        lines and remove Timestamp and Deleted values.
        :return: A string in PEM file format containing the data found inside of pem_file
        """
        self.pem_file = pem_file
        is_fluxgate = self.pem_file.is_fluxgate()

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
    Class that represents the RAD Tool reading in a PEM survey
    """
    def __init__(self):
        self.D = None
        self.Hx = None
        self.gx = None
        self.Hy = None
        self.gy = None
        self.Hz = None
        self.gz = None
        self.T = None

        self.x = None
        self.y = None
        self.z = None
        self.roll_angle = None
        self.dip = None
        self.R = None
        self.angle_used = None  # Roll angle - SOA

        self.derotated = False
        self.rotation_type = None
        self.id = None

        # PP rotation stats
        self.azimuth = None
        self.dip = None
        self.x_pos = None
        self.y_pos = None
        self.z_pos = None
        self.ppx_theory = None
        self.ppy_theory = None
        self.ppz_theory = None
        self.ppx_raw = None
        self.ppy_raw = None
        self.ppx_cleaned = None
        self.ppy_cleaned = None
        self.ppxy_theory = None
        self.ppxy_cleaned = None
        self.ppxy_measured = None
        self.cleaned_pp_roll_angle = None
        self.measured_pp_roll_angle = None

        self.acc_dip = None
        self.mag_dip = None
        self.pp_dip = None

        self.acc_roll_angle = None
        self.mag_roll_angle = None

    def from_match(self, match):
        """
        Create the RADTool object using the string parsed from PEMParser
        :param match: str, Full string parsed from PEMParser
        :return RADTool object
        """
        match = match.split()
        self.D = match[0]
        match[1:] = np.array(match[1:])

        if self.D == 'D7':
            if len(match) == 8:
                self.derotated = False
                self.Hx = float(match[1])
                self.gx = float(match[2])
                self.Hy = float(match[3])
                self.gy = float(match[4])
                self.Hz = float(match[5])
                self.gz = float(match[6])
                self.T = float(match[7])

                self.id = ''.join([
                    str(self.Hx),
                    str(self.gx),
                    str(self.Hy),
                    str(self.gy),
                    str(self.Hz),
                    str(self.gz),
                    str(self.T)
                ])

            elif len(match) == 11:
                self.derotated = True
                self.Hx = float(match[1])
                self.gx = float(match[2])
                self.Hy = float(match[3])
                self.gy = float(match[4])
                self.Hz = float(match[5])
                self.gz = float(match[6])
                self.roll_angle = float(match[7])
                self.dip = float(match[8])
                self.R = match[9]
                self.angle_used = float(match[10])

                self.id = ''.join([
                    str(self.Hx),
                    str(self.gx),
                    str(self.Hy),
                    str(self.gy),
                    str(self.Hz),
                    str(self.gz),
                    str(self.roll_angle),
                    str(self.dip),
                    self.R,
                    str(self.angle_used),
                ])
            else:
                raise Exception(f"D7 RAD tool had {len(match)} items (should have 8 or 11).")

        elif self.D == 'D5':
            self.x = float(match[1])
            self.y = float(match[2])
            self.z = float(match[3])
            self.roll_angle = float(match[4])
            self.dip = float(match[5])
            if len(match) == 6:
                self.derotated = False

                self.id = ''.join([
                    str(self.x),
                    str(self.y),
                    str(self.z),
                    str(self.roll_angle),
                    str(self.dip)
                ])

            elif len(match) == 8:
                self.R = match[6]
                self.angle_used = float(match[7])
                self.derotated = True

                self.id = ''.join([
                    str(self.x),
                    str(self.y),
                    str(self.z),
                    str(self.roll_angle),
                    str(self.dip),
                    str(self.R),
                    str(self.angle_used)
                ])

            else:
                raise ValueError(f'{len(match)} long D5 RAD tool match passed. Should be length of 6 or 8.')

        else:
            raise ValueError(f'{self.D} is an invalid RAD tool D value. D value must be D5 or D7.')

        return self

    def from_dict(self, dict):
        """
        Use the keys and values of a dictionary to create the RADTool object
        :param dict: dictionary with keys being the RADTool object's attributes.
        :return: RADTool object
        """
        self.id = ''

        for key, value in dict.items():
            self.__setattr__(key, value)
            self.id += str(value)
        self.derotated = True if self.angle_used is not None else False

        return self

    def from_dmp(self, text):
        """
        Create the RADTool object from the RAD line in a .DMP file.
        :param text: str or list of RAD tool line items in the .DMP file
        :return: RADTool object
        """
        if not isinstance(text, list):
            text = text.split()

        self.D = 'D7'
        self.Hx = float(text[0])
        self.gx = float(text[1])
        self.Hy = float(text[2])
        self.gy = float(text[3])
        self.Hz = float(text[4])
        self.gz = float(text[5])
        if len(text) > 6:
            self.T = float(text[6])
        else:
            self.T = 0.0

        self.id = ''.join([
            str(self.Hx),
            str(self.gx),
            str(self.Hy),
            str(self.gy),
            str(self.Hz),
            str(self.gz),
            str(self.T),
        ])

        return self

    def get_azimuth(self, allow_negative=False):
        """
        Calculate the azimuth of the RAD tool object. Must be D7.
        :param allow_negative: bool, allow negative azimuth values or only allow values within 0 - 360.
        :return: float, azimuth
        """
        if not self.has_tool_values():
            return None

        g = math.sqrt(sum([self.gx ** 2, self.gy ** 2, self.gz ** 2]))
        numer = ((self.Hz * self.gy) - (self.Hy * self.gz)) * g
        denumer = self.Hx * (self.gy ** 2 + self.gz ** 2) - (self.Hy * self.gx * self.gy) - (
                    self.Hz * self.gx * self.gz)

        azimuth = math.degrees(math.atan2(numer, denumer))
        if not allow_negative:
            if azimuth < 0:
                azimuth = 360 + azimuth
        return azimuth

    def get_dip(self):
        """
        Calculate the dip of the RAD tool object. Must be D7.
        :return: float, dip
        """
        if not self.has_tool_values():
            return None

        try:
            dip = math.degrees(math.acos(self.gx / math.sqrt((self.gx ** 2) + (self.gy ** 2) + (self.gz ** 2)))) - 90
        except ZeroDivisionError:
            logger.error(f"Attempted division by 0.")
            dip = None
        return dip

    def get_acc_roll(self, allow_negative=False):
        """
        Calculate the roll angle as measured by the accelerometer. Must be D7.
        :param allow_negative: bool, allow negative roll values or only allow values within 0 - 360.
        :return: float, roll angle
        """
        if not self.has_tool_values():
            return None

        x, y, z = self.gx, self.gy, self.gz

        theta = math.atan2(y, z)
        cc_roll_angle = 360 - math.degrees(theta) if y < 0 else math.degrees(theta)
        roll_angle = 360 - cc_roll_angle if y > 0 else cc_roll_angle
        if roll_angle >= 360:
            roll_angle = roll_angle - 360
        if allow_negative:
            if roll_angle < 0:
                roll_angle = roll_angle + 360

        return roll_angle

    def get_mag_roll(self, allow_negative=False):
        """
        Calculate the roll angle as measured by the magnetometer. Must be D7.
        :param allow_negative: bool, allow negative roll values or only allow values within 0 - 360.
        :return: float, roll angle
        """
        if not self.has_tool_values():
            return None

        x, y, z = self.Hx, self.Hy, self.Hz

        theta = math.atan2(-y, -z)
        cc_roll_angle = math.degrees(theta)
        roll_angle = 360 - cc_roll_angle if y < 0 else cc_roll_angle
        if roll_angle > 360:
            roll_angle = roll_angle - 360
        if allow_negative:
            if roll_angle < 0:
                roll_angle = -roll_angle

        return roll_angle

    def get_mag(self):
        """
        Calculate and return the magnetic field strength (total field) in units of nT
        :return: float
        """
        if not self.has_tool_values():
            return None

        x, y, z = self.Hx, self.Hy, self.Hz
        mag_strength = math.sqrt(sum([x ** 2, y ** 2, z ** 2])) * (10 ** 5)
        return mag_strength

    def has_tool_values(self):
        if all([self.Hx, self.gx, self.Hy, self.gy, self.Hz, self.gz]):
            return True
        else:
            return False

    def is_derotated(self):
        return True if self.angle_used is not None else False

    def to_string(self, legacy=False):
        """
        Create a string for PEM serialization
        :param legacy: bool, if True, return D5 values instead of D7 for compatibility with Step.
        :return: str
        """
        # If the input D value is already D5
        if self.D == 'D5':
            result = [self.D]
            if self.rotation_type is None:
                result.append(f"{self.x:g}")
                result.append(f"{self.y:g}")
                result.append(f"{self.z:g}")

            elif self.rotation_type == 'acc' or self.rotation_type.lower() == 'pp':
                result.append(f"{self.gx:g}")
                result.append(f"{self.gy:g}")
                result.append(f"{self.gz:g}")

            elif self.rotation_type == 'mag':
                result.append(f"{self.Hx:g}")
                result.append(f"{self.Hy:g}")
                result.append(f"{self.Hz:g}")

            result.append(f"{self.roll_angle:g}")
            result.append(f"{self.dip:g}")

            # Files output with otool don't have an "R" or angle used value.
            if self.R is not None and self.angle_used is not None:
                result.append(self.R)
                result.append(f"{self.angle_used:g}")

        else:
            # Create the D5 RAD tool line that is compatible with Step (just for borehole XY).
            if legacy:
                if self.is_derotated():
                    if self.rotation_type == 'mag':  # Only mag de-rotation uses the mag values. Everything is acc.
                        x, y, z = f"{self.Hx:g}", f"{self.Hy:g}", f"{self.Hz:g}"
                    else:
                        x, y, z = f"{self.gx:g}", f"{self.gy:g}", f"{self.gz:g}"

                    # For de-rotated XY RADs
                    if all([att is not None for att in [self.roll_angle, self.dip, self.angle_used, self.R]]):
                        result = [
                            'D5',
                            x,
                            y,
                            z,
                            f"{self.roll_angle:g}",
                            f"{self.dip:g}",
                            self.R,
                            f"{self.angle_used:g}"
                        ]

                # For rotated and Z RADs
                else:
                    result = [
                        'D7',
                        f"{self.Hx:g}",
                        f"{self.gx:g}",
                        f"{self.Hy:g}",
                        f"{self.gy:g}",
                        f"{self.Hz:g}",
                        f"{self.gz:g}",
                        f"{self.T:g}" if self.T is not None else '0'
                    ]

            # Non legacy
            else:
                if self.D == 'D7' or self.D == 'D6':
                    result = [
                        self.D,
                        f"{self.Hx:g}",
                        f"{self.gx:g}",
                        f"{self.Hy:g}",
                        f"{self.gy:g}",
                        f"{self.Hz:g}",
                        f"{self.gz:g}",
                    ]

                    if self.R is not None and self.angle_used is not None:
                        if self.rotation_type == 'acc':
                            result.append(f"{self.acc_roll_angle:g}")
                        elif self.rotation_type == 'mag':
                            result.append(f"{self.mag_roll_angle:g}")
                        elif self.rotation_type == 'pp_raw':
                            result.append(f"{self.measured_pp_roll_angle:g}")
                        elif self.rotation_type == 'pp_cleaned':
                            result.append(f"{self.cleaned_pp_roll_angle:g}")
                        elif self.rotation_type == "soa":
                            result.append(f"{self.angle_used:g}")
                        else:
                            if self.roll_angle is None:
                                raise Exception(f"The RAD tool object has been de-rotated, yet no roll_angle exists.")

                            result.append(f"{self.roll_angle:g}")

                        result.append(f"{self.get_dip():g}")
                        result.append(self.R)
                        result.append(f"{self.angle_used:g}")
                    else:
                        if self.T is not None:
                            result.append(f"{self.T:g}")
                        else:
                            result.append(f"0")

                else:
                    raise ValueError('RADTool D value is neither "D5" nor "D7"')

        # print(result)
        return ' '.join(result)


class PEMGetter:
    """
    Class to get a list of PEM files from a testing directory. Used for testing.
    """
    def __init__(self):
        self.pem_parser = PEMParser()

    def get_pems(self, folder=None, number=None, selection=None, file=None, random=False,
                 incl=None):
        """
        Retrieve a list of PEMFiles
        :param folder: str, folder from which to retrieve files
        :param number: int, number of files to selected
        :param selection: int, index of file to select
        :param file: str, name the specific to open
        :param random: bool, select random files. If no number is passed, randomly selects the number too.
        :param incl: str, text to include in the file name.
        :return: list of PEMFile objects.
        """

        def add_pem(filepath):
            """
            Parse and add the PEMFile to the list of pem_files.
            :param filepath: Path object of the PEMFile
            """
            if not filepath.exists():
                raise ValueError(f"File {filepath} does not exists.")

            logger.info(f'Getting File {filepath}.')
            try:
                pem_file = self.pem_parser.parse(filepath)
            except Exception:
                return
            else:
                pem_files.append(pem_file)

        sample_files_dir = Path(__file__).parents[2].joinpath('sample_files')

        if folder:
            sample_files_dir = sample_files_dir.joinpath(folder)
            if not sample_files_dir.exists():
                raise ValueError(f"Folder {folder} does not exist.")

        pem_files = []

        # Pool of available files is all PEMFiles in PEMGetter files directory.
        if incl is not None:
            available_files = list(sample_files_dir.rglob(f'*{incl}*.PEM'))
        else:
            available_files = list(sample_files_dir.rglob(f'*.PEM'))
        # print(f"Available files: {', '.join([str(a) for a in available_files])}")

        if random:
            if not number:
                # Generate a random number of files to choose from
                number = randrange(5, min(len(available_files), 15))
            elif number > len(available_files):
                number = len(available_files)

            random_selection = choices(available_files, k=number)

            for file in random_selection:
                add_pem(file)

        else:
            if number:
                for file in available_files[:number]:
                    filepath = sample_files_dir.joinpath(file)
                    add_pem(filepath)
                    # pem_files.append((pem_file, None))  # Empty second item for ri_files

            elif selection is not None and not selection > len(available_files):
                filepath = sample_files_dir.joinpath(available_files[selection])
                add_pem(filepath)
                # pem_files.append((pem_file, None))  # Empty second item for ri_files

            elif file is not None:
                filepath = sample_files_dir.joinpath(file)
                add_pem(filepath)

            else:
                for file in available_files:
                    filepath = sample_files_dir.joinpath(file)
                    add_pem(filepath)
                    # pem_files.append((pem_file, None))  # Empty second item for ri_files

        pem_list = '\n'.join([str(f.filepath) for f in pem_files])
        if not pem_list:
            raise ValueError(f"No PEM files found in {sample_files_dir}.")
        logger.info(f"Collected PEM files: {pem_list}")
        return pem_files

    def parse(self, filepath):
        if not Path(filepath).is_file():
            raise FileNotFoundError(f"{filepath} does not exist.")

        pem_file = parse_file(filepath)
        return pem_file


def import_files():
    data_dir = Path(r"Z:\_Data")
    filt = r"RAW\*xy*.pem"
    pem_files = list(data_dir.rglob(filt))
    pem_files = [f for f in pem_files if "XYG" not in str(f).upper() and "XYT" not in str(f).upper() and "XYZT" not in str(f).upper()]
    output_folder = Path(r"C:\Users\Eric\PycharmProjects\PEMPro\sample_files\Rotation Testing\Vertical Holes")
    parser = PEMParser()
    print(f"XY files found: {len(pem_files)}.")
    count = 0
    for i, filepath in enumerate(pem_files):
        print(f"{i + 1} / {len(pem_files)}")
        # if filepath.suffix.lower() not in [".dmp", ".dmp2"]:
        #     print(f"{filepath} is not .DMP or .DMP2.")
        #     continue

        try:
            pem_file = parser.parse(filepath)
        except:
            print(f"Error parsing {filepath}.")
            continue

        if not pem_file.is_borehole():
            print(f"{pem_file.filepath} is not a borehole file.")
            continue
        if not pem_file.has_xy():
            print(f"{pem_file.filepath} doesn't have XY data.")
            continue

        try:
            mean_dip = pem_file.get_dip(average=True).Dip.mean()
        except:
            print(f"Error calculating dip.")
            continue

        print(f"Mean dip: {mean_dip:.2f}")
        if mean_dip <= -85.:
            # print(f"{pem_file.filepath.name} is near vertical. Moving to sample folder.")
            new_path = output_folder.joinpath(pem_file.filepath.stem + pem_file.line_name + ".PEM")
            pem_file.filepath = new_path
            pem_file.save()
            # print(f"New filepath: {new_path}.")
            count += 1

    print(f"Vertical files found: {count}.")


def compare_rolls():
    folder = Path(r"C:\Users\Eric\PycharmProjects\PEMPro\sample_files\Rotation Testing\Vertical Holes")
    output_folder = Path(r"C:\Users\Eric\PycharmProjects\PEMPro\sample_files\Rotation Testing\Vertical Holes\Roll Comparisons")
    pems = list(folder.glob("*.pem"))
    parser = PEMParser()
    for i, filepath in enumerate(pems):
        print(f"{i + 1} / {len(pems)}")
        pem_file = parser.parse(filepath)
        try:
            pem_file.prep_rotation()
        except:
            print(f"Cannot prep for de-rotation")
            continue

        roll_data = pem_file.get_roll_data("All").groupby("Station", as_index=False).mean()
        roll_data.to_csv(output_folder.joinpath(pem_file.filepath.stem).with_suffix(".csv"),
                         index=False,
                         float_format="%.1f")


def analyze_rolls():
    def process_angle(angle):
        while angle > 180:
            angle -= 360
        while angle < -180:
            angle += 360

        return angle
    vertical_hole_folder = Path(r"C:\Users\Eric\PycharmProjects\PEMPro\sample_files\Rotation Testing\Vertical Holes\Roll Comparisons")
    normal_folder = Path(r"C:\Users\Eric\PycharmProjects\PEMPro\sample_files\Rotation Testing\Roll Comparisons")
    output_names = ["Vertical Holes", "Normal Holes"]
    folders = [vertical_hole_folder, normal_folder]

    for output_name, folder in zip(output_names, folders):
        files = list(folder.glob("*.csv"))

        file_names = []
        acc_mag_mean = []
        acc_mpp_mean = []
        acc_cpp_mean = []
        mag_mpp_mean = []
        mag_cpp_mean = []
        mpp_cpp_mean = []

        for file in files:
            df = pd.read_csv(file)
            if "Measured PP" in df.columns and "Cleaned PP" in df.columns:
                print(f"Processing file {file.name}.")
                file_names.append(file.name)

                acc_mag_diff = get_processed_angles(df.Acc) - get_processed_angles(df.Mag)
                acc_mag_mean.append(process_angle(acc_mag_diff.mean()))
                # print(f"Acc - Mag:\n{acc_mag_diff}\n")

                acc_mpp_diff = get_processed_angles(df.Acc) - get_processed_angles(df.loc[:, "Measured PP"])
                acc_mpp_mean.append(process_angle(acc_mpp_diff.mean()))
                # print(f"Acc - Measured PP:\n{acc_mpp_diff}\n")

                acc_cpp_diff = get_processed_angles(df.Acc) - get_processed_angles(df.loc[:, "Cleaned PP"])
                acc_cpp_mean.append(process_angle(acc_cpp_diff.mean()))
                # print(f"Acc - Measured PP:\n{acc_mpp_diff}\n")

                mag_mpp_diff = get_processed_angles(df.Mag) - get_processed_angles(df.loc[:, "Measured PP"])
                mag_mpp_mean.append(process_angle(mag_mpp_diff.mean()))
                # print(f"Mag - Measured PP:\n{mag_mpp_diff}\n")

                mag_cpp_diff = get_processed_angles(df.Mag) - get_processed_angles(df.loc[:, "Cleaned PP"])
                mag_cpp_mean.append(process_angle(mag_cpp_diff.mean()))
                # print(f"Mag - Cleaned PP:\n{mag_cpp_diff}\n")

                mpp_cpp_diff = get_processed_angles(df.loc[:, "Measured PP"]) - get_processed_angles(df.loc[:, "Cleaned PP"])
                mpp_cpp_mean.append(process_angle(mpp_cpp_diff.mean()))
                # print(f"Measured PP - Cleaned PP:\n{mpp_cpp_diff}\n")

        columns = ["File",
                   "Acc - Mag",
                   "Acc - Measured PP",
                   "Acc - Cleaned PP",
                   "Mag - Measured PP",
                   "Mag - Cleaned PP",
                   "Measured PP - Cleaned PP"]
        analysis_df = pd.DataFrame(data=[file_names,
                                         acc_mag_mean,
                                         acc_mpp_mean,
                                         acc_cpp_mean,
                                         mag_mpp_mean,
                                         mag_cpp_mean,
                                         mpp_cpp_mean]).T
        analysis_df.columns = columns
        analysis_df.set_index("File", inplace=True)

        # analysis_df = analysis_df.append(analysis_df.mean(), ignore_index=True)
        analysis_df.loc["Mean"] = analysis_df.mean()
        analysis_df.to_csv(folder.joinpath(output_name + ".CSV"), float_format="%.1f", index=True)
        os.startfile(str(folder.joinpath(output_name + ".CSV")))


if __name__ == '__main__':
    # import_files()
    # compare_rolls()
    # analyze_rolls()

    sample_folder = Path(__file__).parents[2].joinpath("sample_files")
    #
    pg = PEMGetter()
    # pem_file = pg.get_pems("Rotation Testing", number=1)[0]
    pem_file = pg.parse(r"C:\_Data\2021\Trevali Peru\Surface\Off Loop Puajanca\RAW\1280.PEM")
    # pem_file.prep_rotation()
    # pem_file.rotate(method="mag")
    # print(pem_file.get_roll_data(roll_type="Mag"))
    # pem_file = pg.parse(r"C:\_Data\2021\TMC\Senc Resources\Loop 11\RAW\700e_1210.PEM")
    # # txt_file = sample_folder.joinpath(r"Line GPS\KA800N_1027.txt")
    # # line = SurveyLine(txt_file)
    # # line.get_warnings(stations=pem_file.get_stations(converted=True, incl_deleted=False))
    #
    # # file = sample_folder.joinpath(r"C:\_Data\2021\Eastern\Corazan Mining\FLC-2021-26 (LP-26B)\RAW\_0327_PP.DMP")
    # # file = r"C:\_Data\2021\TMC\Laurentia\STE-21-50-W3\RAW\ste-21-50w3xy_0819.dmp2"
    # # pem_files = pg.parse(r"C:\_Data\2021\TMC\Laurentia\STE-21-70\Final\STE-21-70 XYT.PEM")
    # # pem_files = pg.parse(r"C:\_Data\2021\Trevali Peru\Borehole\_SAN-264-21\RAW\xy_1002.PEM")
    # # pem_file = pg.parse(r"C:\_Data\2021\Trevali Peru\Borehole\SAN-0251-21\RAW\xy_1019.PEM")
    # # file = r"C:\_Data\2021\TMC\Murchison\Barraute B\RAW\l35eb2_0.PEM817.dmp2"
    # # pem_file, errors = dmpparser.parse(file)
    # # print(pem_file.to_string())
    #
    # # pem_files = pg.get_pems(random=True, number=1)
    # # pem_files = pg.get_pems(folder="Raw Boreholes", file=r"EB-21-52\Final\z.PEM")
    # # pem_files = pg.get_pems(folder="Raw Surface", file=r"Loop L\Final\100E.PEM")
    # # pem_files = pg.get_pems(folder="Raw Surface", subfolder=r"Loop 1\Final\Perkoa South", file="11200E.PEM")
    # # pem_files = pg.get_pems(folder="Raw Boreholes", file="em21-155 z_0415.PEM")
    #
    # # pem_file = pem_files[0]
    # # pem_file, _ = pem_file.prep_rotation()
    # # pem_file.get_theory_pp()
    # # pem_file.get_theory_data()
    print(pem_file.get_reversed_components())
    # # pem_file.rotate(method="unrotate")
    # # pem_file.rotate(method="unrotate")
    # # pem_file.filepath = pem_file.filepath.with_name(pem_file.filepath.stem + "(unrotated)" + ".PEM")
    # # pem_file.save()
