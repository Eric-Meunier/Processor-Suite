import math
import numpy as np
import pandas as pd
from timeit import default_timer as timer


class MagneticFieldCalculator:
    """
    Class that calculates magnetic field for a given transmitter loop.
    :param: wire: list or DataFrame of wire (loop) coordinates
    """

    def __init__(self, wire):
        if isinstance(wire, pd.DataFrame):
            self.wire = wire.loc[:, ['Easting', 'Northing', 'Elevation']].to_numpy()
        else:
            self.wire = np.array(wire, dtype='float')
            # Remove any unwanted columns. Only easting, northing, elevation is required.
            while self.wire.shape[1] > 3:
                print(f"Loop has {self.wire.shape[1]} columns in row. Removing the last column...")
                self.wire = np.delete(self.wire, 3, axis=1)

    def scale_vector(self, vector, factor):
        """
        :param vector: list or tuple
        :param factor: float or int
        """
        newvector = list(map(lambda x: x * factor, vector))
        return newvector

    def get_magnitude(self, vector):
        return math.sqrt(sum(i ** 2 for i in vector))

    def project(self, normal_plane, vector):
        length = np.linalg.norm(normal_plane)
        calc = np.dot(normal_plane, vector) / length ** 2
        scaled = normal_plane * calc
        newvector = vector - scaled
        return newvector[0], newvector[1], newvector[2]

    def get_angle_2V(self, v1, v2):
        len1 = math.sqrt(sum(i ** 2 for i in v1))
        len2 = math.sqrt(sum(i ** 2 for i in v2))
        angle = math.acos(np.dot(v1, v2) / (len1 * len2))
        return angle

    def calc_total_field(self, x, y, z, I=1):
        """
        Calculate the magnetic field at position (x, y, z) with current I using Biot-Savart Law. Uses the geometry of
        wire_coords for the wire.
        :param x, y, z: Position at which the magnetic field is calculated
        :param I: float: Current (Amps)
        :return: Magnetic field strength (in Teslas) for each component
        """

        def loop_difference(loop_listorarray):
            loop_array = np.array(loop_listorarray)
            loop_diff = np.append(np.diff(loop_array, axis=0),
                                  [loop_array[0] - loop_array[-1]], axis=0)
            return loop_diff

        def array_shift(arr, shift_num):
            result = np.empty_like(arr)
            if shift_num > 0:
                result[:shift_num] = arr[-shift_num:]
                result[shift_num:] = arr[:-shift_num]
            elif shift_num < 0:
                result[shift_num:] = arr[:-shift_num]
                result[:shift_num] = arr[-shift_num:]
            else:
                result[:] = arr
            return result

        u0 = 1.25663706e-6  # Constant
        loop_array = np.array(self.wire)
        # point = np.array([pos[0], pos[1], pos[2]])
        point = np.array([x, y, z])
        loop_diff = loop_difference(loop_array)

        AP = point - loop_array
        BP = array_shift(AP, -1)

        r1 = np.sqrt((AP ** 2).sum(-1))[..., np.newaxis].T.squeeze()
        r2 = np.sqrt((BP ** 2).sum(-1))[..., np.newaxis].T.squeeze()
        Dot1 = np.multiply(AP, loop_diff).sum(1)
        Dot2 = np.multiply(BP, loop_diff).sum(1)
        cross = np.cross(loop_diff, AP)

        CrossSqrd = (np.sqrt((cross ** 2).sum(-1))[..., np.newaxis]).squeeze() ** 2
        top = (Dot1 / r1 - Dot2 / r2) * u0 * I
        bottom = (CrossSqrd * 4 * np.pi)
        factor = (top / bottom)
        factor = factor[..., np.newaxis]

        field = cross * factor
        field = np.sum(field, axis=0)

        return field[0], field[1], field[2]

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
        theta = self.get_angle_2V(planeNormal, [0, 1, 0])

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

        print('Computing Field at {} points.....'.format(xx.size))
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
        theta = self.get_angle_2V(planeNormal, [0, 1, 0])

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

        print('Computing Field at {} points.....'.format(xx.size))
        start = timer()

        # Calculate the magnetic field at each grid point
        u, v, w = v_field(xx, yy, zz)
        # Project the arrows
        uproj, vproj, wproj = v_proj(u, v, w, planeNormal)

        end = timer()
        time = round(end - start, 2)
        print('Calculated in {} seconds'.format(str(time)))

        mag = np.sqrt(u * u + v * v + w * w)  # Magnitude for colormap
        uprot = np.cos(theta) * uproj + np.sin(theta) * vproj  # Rotate the vectors back to the X-Z Plane

        uprot2d = np.squeeze(uprot).T  # Get rid of the extra dimension, transpose to fudge the arrangement
        wproj2d = np.squeeze(wproj).T
        magsqueeze = np.squeeze(mag).T

        plotx = uprot2d / np.sqrt(uprot2d ** 2 + wproj2d ** 2) * 0.7  # Normalize vector lengths
        plotz = wproj2d / np.sqrt(uprot2d ** 2 + wproj2d ** 2) * 0.7

        xx, zz = np.meshgrid(a, c)

        return xx, yy, zz, uproj, vproj, wproj, plotx, plotz, arrow_len