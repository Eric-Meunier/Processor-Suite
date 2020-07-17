import math
import numpy as np
import pandas as pd
import time
from copy import deepcopy
from timeit import default_timer as timer


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
                print(f"Loop has {self.wire.shape[1]} columns in row. Removing the last column...")
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
    def get_angle_2V(v1, v2):
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


# calculate magnetic fields arising from electrical current through wires of arbitrary shape
# with the law of Biot-Savart

# written by Michael Wack
# wack@geophysik.uni-muenchen.de

# tested with python 3.4.3


class Wire:
    """
    represents an arbitrary 3D wire geometry
    """

    def __init__(self, current=1, path=None, discretization_length=0.01):
        """

        :param current: electrical current in Ampere used for field calculations
        :param path: geometry of the wire specified as path of n 3D (x,y,z) points in a numpy array with dimension n x 3
                     length unit is meter
        :param discretization_length: length of dL after discretization
        """
        self.current = current
        self.path = path
        self.discretization_length = discretization_length

    @property
    def discretized_path(self):
        """
        calculate end points of segments of discretized path
        approximate discretization lenghth is given by self.discretization_length
        elements will never be combined
        elements longer that self.dicretization_length will be divided into pieces
        :return: discretized path as m x 3 numpy array
        """

        try:
            return self.dpath
        except AttributeError:
            pass

        self.dpath = deepcopy(self.path)
        for c in range(len(self.dpath) - 2, -1, -1):
            # go backwards through all elements
            # length of element
            element = self.dpath[c + 1] - self.dpath[c]
            el_len = np.linalg.norm(element)
            npts = int(np.ceil(
                el_len / self.discretization_length))  # number of parts that this element should be split up into
            if npts > 1:
                # element too long -> create points between
                # length of new sub elements
                sel = el_len / float(npts)
                for d in range(npts - 1, 0, -1):
                    self.dpath = np.insert(self.dpath, c + 1, self.dpath[c] + element / el_len * sel * d, axis=0)

        return self.dpath

    @property
    def IdL_r1(self):
        """
        calculate discretized path elements dL and their center point r1
        :return: numpy array with I * dL vectors, numpy array of r1 vectors (center point of element dL)
        """
        npts = len(self.discretized_path)
        if npts < 2:
            print("discretized path must have at least two points")
            return

        IdL = np.array(
            [self.discretized_path[c + 1] - self.discretized_path[c] for c in range(npts - 1)]) * self.current
        r1 = np.array([(self.discretized_path[c + 1] + self.discretized_path[c]) * 0.5 for c in range(npts - 1)])

        return IdL, r1

    def ExtendPath(self, path):
        """
        extends existing path by another one
        :param path: path to append
        """
        if self.path is None:
            self.path = path
        else:
            # check if last point is identical to avoid zero length segments
            if self.path[-1] == path[0]:
                self.path = np.append(self.path, path[1:], axis=1)
            else:
                self.path = np.append(self.path, path, axis=1)

    def Translate(self, xyz):
        """
        move the wire in space
        :param xyz: 3 component vector that describes translation in x,y and z direction
        """
        if self.path is not None:
            self.path += np.array(xyz)

        return self

    def Rotate(self, axis=(1, 0, 0), deg=0):
        """
        rotate wire around given axis by deg degrees
        :param axis: axis of rotation
        :param deg: angle
        """
        if self.path is not None:
            n = axis
            ca = np.cos(np.radians(deg))
            sa = np.sin(np.radians(deg))
            R = np.array(
                [[n[0] ** 2 * (1 - ca) + ca, n[0] * n[1] * (1 - ca) - n[2] * sa, n[0] * n[2] * (1 - ca) + n[1] * sa],
                 [n[1] * n[0] * (1 - ca) + n[2] * sa, n[1] ** 2 * (1 - ca) + ca, n[1] * n[2] * (1 - ca) - n[0] * sa],
                 [n[2] * n[0] * (1 - ca) - n[1] * sa, n[2] * n[1] * (1 - ca) + n[0] * sa, n[2] ** 2 * (1 - ca) + ca]])
            self.path = np.dot(self.path, R.T)

        return self


class BiotSavart:
    """
    calculates the magnetic field generated by currents flowing through wires
    """

    def __init__(self, wire=None):
        self.wires = []
        if wire is not None:
            self.wires.append(wire)

    def AddWire(self, wire):
        self.wires.append(wire)

    def CalculateB(self, points):
        """
        calculate magnetic field B at given points
        :param points: numpy array of n points (xyz)
        :return: numpy array of n vectors representing the B field at given points
        """

        print("found {} wire(s).".format(len(self.wires)))
        c = 0
        # generate list of IdL and r1 vectors from all wires
        for w in self.wires:
            c += 1
            _IdL, _r1 = w.IdL_r1
            print("wire {} has {} segments".format(c, len(_IdL)))
            if c == 1:
                IdL = _IdL
                r1 = _r1
            else:
                IdL = np.vstack((IdL, _IdL))
                r1 = np.vstack((r1, _r1))
        print("total number of segments: {}".format(len(IdL)))
        print("number of field points: {}".format(len(points)))
        print("total number of calculations: {}".format(len(points)*len(IdL)))

        # now we have
        # all segment vectors multiplied by the flowing current in IdL
        # and all vectors to the central points of the segments in r1

        # calculate vector B*1e7 for each point in space
        t1 = time.process_time()
        # simple list comprehension to calculate B at each point r
        B = np.array([BiotSavart._CalculateB1(r, IdL, r1) * 1e-7 for r in points])

        # multi processing
        # slower than single processing?
        #pool = mp.Pool(processes=16)
        #B = np.array([pool.apply(_CalculateB1, args=(r, IdL, r1)) for r in points])

        t2 = time.process_time()
        print("time needed for calculation: {} s".format(t2-t1))

        return B

    def vv_PlotWires(self):
        for w in self.wires:
            w.vv_plot_path()

    def mpl3d_PlotWires(self, ax):
        for w in self.wires:
            w.mpl3d_plot_path(show=False, ax=ax)

    @staticmethod
    def _CalculateB1(r, IdL, r1):
        """
        calculate magnetic field B for one point r in space
        :param r: 3 component numpy array representing the location where B will be calculated
        :param IdL:  all segment vectors multiplied by the flowing current
        :param r1: all vectors to the central points of the segments
        :return: numpy array of 3 component vector of B multiplied by 1e7
        """

        # calculate law of biot savart for all current elements at given point r
        r2 = r - r1
        r25 = np.linalg.norm(r2, axis=1)**3
        r3 = r2 / r25[:, np.newaxis]

        cr = np.cross(IdL, r3)

        # claculate sum of contributions from all current elements
        s = np.sum(cr, axis=0)

        return s