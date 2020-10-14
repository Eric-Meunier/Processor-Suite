import math
import numpy as np
import pandas as pd
from timeit import default_timer as timer
import logging

logger = logging.getLogger(__name__)


class MagneticFieldCalculator:
    """
    Class that calculates magnetic field for a given transmitter loop.
    :param: wire: list or DataFrame of wire (loop) coordinates
    """

    def __init__(self, wire):
        if isinstance(wire, pd.DataFrame):
            # Ensure the loop is not closed
            wire.drop_duplicates(inplace=True)
            self.wire = wire.loc[:, ['Easting', 'Northing', 'Elevation']].to_numpy()
        else:
            self.wire = np.array(wire, dtype='float')
            # Remove any unwanted columns. Only easting, northing, elevation is required.
            while self.wire.shape[1] > 3:
                logger.info(f"Loop has {self.wire.shape[1]} columns in row. Removing the last column.")
                self.wire = np.delete(self.wire, 3, axis=1)

    @staticmethod
    def scale_vector(vector, factor):
        """
        :param vector: list or tuple
        :param factor: float or int
        """
        newvector = list(map(lambda x: x * factor, vector))
        return newvector

    @staticmethod
    def get_magnitude(vector):
        return math.sqrt(sum(i ** 2 for i in vector))

    @staticmethod
    def project(normal_plane, vector):
        length = np.linalg.norm(normal_plane)
        calc = np.dot(normal_plane, vector) / length ** 2
        scaled = normal_plane * calc
        newvector = vector - scaled
        return newvector[0], newvector[1], newvector[2]

    @staticmethod
    def get_angle_2v(v1, v2):
        len1 = math.sqrt(sum(i ** 2 for i in v1))
        len2 = math.sqrt(sum(i ** 2 for i in v2))
        angle = math.acos(np.dot(v1, v2) / (len1 * len2))
        return angle

    def calc_total_field(self, x, y, z, amps=1, out_units='pT', ramp=None):
        """
        Calculate the magnetic field at position (x, y, z) with current I using Biot-Savart Law.
        Uses equation: dB = (u0 * I * dL * r) / (4 * pi * r^2)
        :param x, y, z: Position at which the magnetic field is calculated
        :param amps: float, Current (Amps)
        :param out_units: str, desired output units. Can be either nT, pT, or nT/s (ramp required)
        :param ramp: float, ramp length (in seconds), used only for nT/s units
        :return: tuple, (x, y, z) Magnetic field strength (in Teslas by default)
        """

        # Permeability of free space
        u0 = 1.25663706e-6

        # Break the wire into segments (differential elements)
        loop_diff = np.append(np.diff(self.wire, axis=0), [self.wire[0] - self.wire[-1]], axis=0)

        # Calculate the displacement vector for each segment
        AP = np.array([x, y, z]) - self.wire
        # Create a shifted copy of AP
        BP = np.append(AP[1:], [AP[0]], axis=0)

        # Calculate the square root of the sum of the elements in each row of AP and BP.
        r_AP = np.sqrt((AP ** 2).sum(axis=-1))
        r_BP = np.sqrt((BP ** 2).sum(axis=-1))

        # Multiply AP and BP with loop_diff element-wise, then summing each row
        dot1 = np.multiply(AP, loop_diff).sum(axis=1)
        dot2 = np.multiply(BP, loop_diff).sum(axis=1)

        # Calculate the cross product of loop_diff and AP -> dl X r^ in Biot Savart's eq.
        cross = np.cross(loop_diff, AP)

        # Square the displacement vector -> |r'|^2 in Biot Savart's eq.
        cross_sqrt = np.sqrt((cross ** 2).sum(axis=-1)) ** 2

        # Calculate the Biot Savart equation
        top = (dot1 / r_AP - dot2 / r_BP) * u0 * amps
        bottom = cross_sqrt * 4 * np.pi
        factor = top / bottom
        factor = factor[..., np.newaxis]

        # Calculate the field magnetic from each segment
        field = cross * factor
        # Sum the contribution of each segment
        field = field.sum(axis=0)

        if out_units:
            if out_units == 'nT':
                field = field * (10 ** 9)
            elif out_units == 'pT':
                field = field * (10 ** 12)
            elif out_units == 'nT/s':
                if ramp is None:
                    raise ValueError('For units of nT/s, a ramp time (in seconds) must be given')
                else:
                    field = (field * (10 ** 9)) / ramp
            else:
                raise ValueError('Invalid output unit')

        return field[0], field[1], field[2]
        # return field[1], -field[0], field[2]

    # def calc_total_field(self, x, y, z, amps=1, out_units='pT', ramp=None):
    #     """
    #     Calculate the magnetic field at position (x, y, z) with current I using Biot-Savart Law. Uses the geometry of
    #     wire_coords for the wire.
    #     :param x, y, z: Position at which the magnetic field is calculated
    #     :param amps: float, Current (Amps)
    #     :param out_units: str, desired output units. Can be either nT, pT, or nT/s (ramp required)
    #     :param ramp: float, ramp length (in seconds), used only for nT/s units
    #     :return: tuple, (x, y, z) Magnetic field strength (in Teslas by default)
    #     """
    #
    #     def loop_difference():
    #         """
    #         Returns an array of segment lengths for each component of self.wire
    #         :return: np.array
    #         """
    #         loop_diff = np.append(np.diff(self.wire, axis=0), [self.wire[0] - self.wire[-1]], axis=0)
    #         return loop_diff
    #
    #     def array_shift(arr, shift_num):
    #         result = np.empty_like(arr)
    #         if shift_num > 0:
    #             result[:shift_num] = arr[-shift_num:]
    #             result[shift_num:] = arr[:-shift_num]
    #         elif shift_num < 0:
    #             result[shift_num:] = arr[:-shift_num]
    #             result[:shift_num] = arr[-shift_num:]
    #         else:
    #             result[:] = arr
    #         return result
    #
    #     u0 = 1.25663706e-6  # Constant
    #     loop_diff = np.diff(self.wire, axis=0)
    #
    #     AP = np.array([x, y, z]) - self.wire
    #     BP = array_shift(AP, -1)
    #
    #     r1 = np.sqrt((AP ** 2).sum(-1))[..., np.newaxis].T.squeeze()
    #     r2 = np.sqrt((BP ** 2).sum(-1))[..., np.newaxis].T.squeeze()
    #     Dot1 = np.multiply(AP, loop_diff).sum(1)
    #     Dot2 = np.multiply(BP, loop_diff).sum(1)
    #     cross = np.cross(loop_diff, AP)
    #
    #     CrossSqrd = (np.sqrt((cross ** 2).sum(-1))[..., np.newaxis]).squeeze() ** 2
    #     top = (Dot1 / r1 - Dot2 / r2) * u0 * amps
    #     bottom = (CrossSqrd * 4 * np.pi)
    #     factor = (top / bottom)
    #
    #     cross = cross[~np.isnan(factor)]  # filter out any NaN
    #     factor = factor[~np.isnan(factor)]  # filter out any NaN
    #     factor = factor[..., np.newaxis]
    #
    #     field = cross * factor
    #     field = np.sum(field, axis=0)
    #
    #     if out_units:
    #         if out_units == 'nT':
    #             field = field * (10 ** 9)
    #         elif out_units == 'pT':
    #             field = field * (10 ** 12)
    #         elif out_units == 'nT/s':
    #             if ramp is None:
    #                 raise ValueError('For units of nT/s, a ramp time (in seconds) must be given')
    #             else:
    #                 field = (field * (10 ** 9)) / ramp
    #         else:
    #             raise ValueError('Invalid output unit')
    #
    #     return field[0], field[1], field[2]

    def get_3d_magnetic_field(self, c1, c2, spacing=None, arrow_len=None, num_rows=12):
        """

        :param c1: corner 1: [x, y, z] coordinate
        :param c2: corner 2: [x, y, z] coordinate
        :param spacing: int: Spacing of arrows along the section-line.
        :param arrow_len: float: Length of arrows
        :param num_rows:
        :return: tuple: mesh X, Y, Z coordinates, projected X, Y, Z of the arrows, X and Z normalized vectors, arrow length
        """

        def wrapper_proj(i, j, k, normal_plane):
            return self.project(normal_plane, [i, j, k])

        v_proj = np.vectorize(wrapper_proj, excluded=[3])
        v_field = np.vectorize(self.calc_total_field)

        # Vector to point and normal of cross section
        vec = [c2[0] - c1[0], c2[1] - c1[1], 0]
        planeNormal = np.cross(vec, [0, 0, -1])

        # Angle between the plane and j_hat
        theta = self.get_angle_2v(planeNormal, [0, 1, 0])

        # Fixes angles where p2.y is less than p1.y
        if c2[1] < c1[1]:
            theta = -theta

        # Creating the grid
        # min_x, max_x, min_y, max_y, min_z, max_z = self.get_extents(self.pem_file)
        max_z = max([c1[2], c2[2]]) + 10
        min_z = min([c1[2], c2[2]]) - 10

        line_len = round(math.sqrt((c1[0] - c2[0]) ** 2 + (c1[1] - c2[1]) ** 2))
        if arrow_len is None:
            arrow_len = float(line_len // 30)
        # Spacing between the arrows
        if spacing is None:
            # spacing = (abs(min_x - max_x) + abs(min_y - max_y)) // 30
            spacing = line_len // 20

        a = np.arange(-10, line_len, spacing)
        b = np.zeros(1)
        c = np.arange(min_z, max_z, line_len // 20)

        xx, yy, zz = np.meshgrid(a, b, c)

        xx_rot = xx * math.cos(theta) - yy * math.sin(theta)
        yy_rot = xx * math.sin(theta) + yy * math.cos(theta)

        xx = xx_rot + c1[0]
        yy = yy_rot + c1[1]

        start = timer()

        # Calculate the magnetic field at each grid point
        u, v, w = v_field(xx, yy, zz)
        # Project the arrows
        uproj, vproj, wproj = v_proj(u, v, w, planeNormal)

        return xx, yy, zz, uproj, vproj, wproj, arrow_len

    def get_2d_magnetic_field(self, c1, c2, spacing=None, arrow_len=None, num_rows=12):
        """

        :param c1: corner 1: [x, y, z] coordinate
        :param c2: corner 2: [x, y, z] coordinate
        :param spacing:
        :param arrow_len:
        :param num_rows:
        :return: tuple: mesh X, Y, Z coordinates, projected X, Y, Z of the arrows, X and Z normalized vectors, arrow length
        """

        def wrapper_proj(i, j, k, normal_plane):
            return self.project(normal_plane, [i, j, k])

        v_proj = np.vectorize(wrapper_proj, excluded=[3])
        v_field = np.vectorize(self.calc_total_field)

        # Vector to point and normal of cross section
        vec = [c2[0] - c1[0], c2[1] - c1[1], 0]
        planeNormal = np.cross(vec, [0, 0, -1])

        # Angle between the plane and j_hat
        theta = self.get_angle_2v(planeNormal, [0, 1, 0])

        # Fixes angles where p2.y is less than p1.y
        if c2[1] < c1[1]:
            theta = -theta

        # Creating the grid
        # min_x, max_x, min_y, max_y, min_z, max_z = self.get_extents(self.pem_file)
        max_z = max([c1[2], c2[2]]) + 10
        min_z = min([c1[2], c2[2]]) - 10

        line_len = round(math.sqrt((c1[0] - c2[0]) ** 2 + (c1[1] - c2[1]) ** 2))
        if arrow_len is None:
            arrow_len = float(line_len // 30)
        # Spacing between the arrows
        if spacing is None:
            # spacing = (abs(min_x - max_x) + abs(min_y - max_y)) // 30
            spacing = line_len // 20

        a = np.arange(-10, line_len, spacing)
        b = np.zeros(1)
        c = np.arange(min_z, max_z, line_len // 20)

        xx, yy, zz = np.meshgrid(a, b, c)

        xx_rot = xx * math.cos(theta) - yy * math.sin(theta)
        yy_rot = xx * math.sin(theta) + yy * math.cos(theta)

        xx = xx_rot + c1[0]
        yy = yy_rot + c1[1]

        # Calculate the magnetic field at each grid point
        u, v, w = v_field(xx, yy, zz)
        # Project the arrows
        uproj, vproj, wproj = v_proj(u, v, w, planeNormal)

        mag = np.sqrt(u * u + v * v + w * w)  # Magnitude for colormap
        uprot = np.cos(theta) * uproj + np.sin(theta) * vproj  # Rotate the vectors back to the X-Z Plane

        uprot2d = np.squeeze(uprot).T  # Get rid of the extra dimension, transpose to fudge the arrangement
        wproj2d = np.squeeze(wproj).T
        magsqueeze = np.squeeze(mag).T

        plotx = uprot2d / np.sqrt(uprot2d ** 2 + wproj2d ** 2) * 0.7  # Normalize vector lengths
        plotz = wproj2d / np.sqrt(uprot2d ** 2 + wproj2d ** 2) * 0.7

        xx, zz = np.meshgrid(a, c)

        return xx, yy, zz, uproj, vproj, wproj, plotx, plotz, arrow_len

