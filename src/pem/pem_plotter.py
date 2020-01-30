import copy
import logging
import math
import os
import re
import sys
from datetime import datetime
from timeit import default_timer as timer
from collections import defaultdict
import cartopy
import cartopy.crs as ccrs  # import projections
import matplotlib.backends.backend_tkagg  # Needed for pyinstaller, or receive  ImportError
import matplotlib as mpl
import matplotlib.lines as mlines
import matplotlib.pyplot as plt
import matplotlib.text as mtext
import matplotlib.ticker as ticker
import matplotlib.transforms as mtransforms
import numpy as np
from PyQt5.QtWidgets import (QProgressBar)
from PyQt5 import QtGui, QtCore
from matplotlib import patches
from matplotlib import patheffects
from matplotlib.backends.backend_pdf import PdfPages
from mpl_toolkits.mplot3d import Axes3D  # Needed for 3D plots
import mpl_toolkits.mplot3d.art3d as art3d
from scipy import interpolate as interp
from scipy import stats
from statistics import mean
import itertools

from src.gps.gps_editor import GPSEditor

__version__ = '0.1.0'
logging.info('PEMPlotter')

if getattr(sys, 'frozen', False):
    # If the application is run as a bundle, the pyInstaller bootloader
    # extends the sys module by a flag frozen=True and sets the app
    # path into variable _MEIPASS'.
    application_path = sys._MEIPASS
else:
    application_path = os.path.dirname(os.path.abspath(__file__))

sys._excepthook = sys.excepthook


def exception_hook(exctype, value, traceback):
    print(exctype, value, traceback)
    sys._excepthook(exctype, value, traceback)
    sys.exit(1)


sys.excepthook = exception_hook

mpl.rcParams['path.simplify'] = True
mpl.rcParams['path.simplify_threshold'] = 1.0
mpl.rcParams['agg.path.chunksize'] = 10000
mpl.rcParams["figure.autolayout"] = False
mpl.rcParams['lines.linewidth'] = 0.5
# mpl.rcParams['lines.color'] = '#1B2631'
mpl.rcParams['font.size'] = 9

line_color = 'black'


def natural_sort(list):
    convert = lambda text: int(text) if text.isdigit() else text.lower()
    alphanum_key = lambda key: [convert(c) for c in re.split('([0-9]+)', key)]
    return sorted(list, key=alphanum_key)


class PlotMethods:
    """
    Collection of methods for plotting LIN, LOG, and STEP plots
    """
    @staticmethod
    def add_rectangle(figure):
        """
        Draws a rectangle around a figure object
        """
        rect = patches.Rectangle(xy=(0.02, 0.02), width=0.96, height=0.96, linewidth=0.7, edgecolor='black',
                                 facecolor='none', transform=figure.transFigure)
        figure.patches.append(rect)

    def format_figure(self, figure, step=False):
        """
        Formats a figure, mainly the spines, adjusting the padding, and adding the rectangle.
        :param figure: LIN or LOG figure object
        """
        axes = figure.axes

        def format_spines(ax):
            ax.spines['right'].set_visible(False)
            ax.spines['top'].set_visible(False)

            if ax != axes[-1]:
                ax.spines['bottom'].set_position(('data', 0))
                ax.tick_params(axis='x', which='major', direction='inout', length=4)
                plt.setp(ax.get_xticklabels(), visible=False)
            else:
                ax.spines['bottom'].set_visible(False)
                ax.xaxis.set_ticks_position('bottom')
                ax.tick_params(axis='x', which='major', direction='out', length=6)
                plt.setp(ax.get_xticklabels(), visible=True, size=12, fontname='Century Gothic')

        figure.subplots_adjust(left=0.135 if step is False else 0.170, bottom=0.07, right=0.958, top=0.885)
        self.add_rectangle(figure)

        for ax in axes:
            format_spines(ax)

    def format_xaxis(self, pem_file, component, figure, x_min, x_max):
        """
        Formats the X axis of a figure
        :param figure: LIN or LOG figure objects
        """
        component_data = list(filter(lambda d: d['Component'] == component, pem_file.data))
        component_stations = [self.convert_station(station['Station']) for station in component_data]
        if x_min is None:
            x_min = min(component_stations)
        if x_max is None:
            x_max = max(component_stations)
        x_label_locator = ticker.AutoLocator()
        major_locator = ticker.FixedLocator(sorted(component_stations))
        plt.xlim(x_min, x_max)
        figure.axes[0].xaxis.set_major_locator(major_locator)  # for some reason this seems to apply to all axes
        figure.axes[-1].xaxis.set_major_locator(x_label_locator)

    def format_yaxis(self, pem_file, figure, step=False):
        """
        Formats the Y axis of a figure. Will increase the limits of the scale if depending on the limits of the data.
        :param figure: LIN, LOG or Step figure objects
        """
        axes = figure.axes[:-1]
        survey_type = pem_file.survey_type

        for ax in axes:
            ax.get_yaxis().set_label_coords(-0.08 if step is False else -0.095, 0.5)

            if ax.get_yscale() != 'symlog':
                y_limits = ax.get_ylim()

                if 'induction' in survey_type.lower():
                    if step is True:
                        if ax == axes[1] and (y_limits[1] - y_limits[0]) < 20:
                            new_high = math.ceil(((y_limits[1] - y_limits[0]) / 2) + 10)
                            new_low = new_high * -1
                        elif ax in axes[2:4] and (y_limits[1] - y_limits[0]) < 3:
                            new_high = math.ceil(((y_limits[1] - y_limits[0]) / 2) + 1)
                            new_low = new_high * -1
                        else:
                            new_high = math.ceil(max(y_limits[1], 0))
                            new_low = math.floor(min(y_limits[0], 0))
                    else:
                        if (y_limits[1] - y_limits[0]) < 3:
                            new_high = math.ceil(((y_limits[1] - y_limits[0]) / 2) + 1)
                            new_low = new_high * -1
                        else:
                            new_high = math.ceil(max(y_limits[1], 0))
                            new_low = math.floor(min(y_limits[0], 0))

                elif 'fluxgate' in survey_type.lower():
                    if step is True:
                        if ax == axes[1] and (y_limits[1] - y_limits[0]) < 20:
                            new_high = math.ceil(((y_limits[1] - y_limits[0]) / 2) + 10)
                            new_low = new_high * -1
                        elif ax == axes[2] and (y_limits[1] - y_limits[0]) < 3:
                            new_high = math.ceil(((y_limits[1] - y_limits[0]) / 2) + 1)
                            new_low = new_high * -1
                        elif ax == axes[3] and (y_limits[1] - y_limits[0]) < 30:
                            new_high = math.ceil(((y_limits[1] - y_limits[0]) / 2) + 10)
                            new_low = new_high * -1
                        else:
                            new_high = math.ceil(max(y_limits[1], 0))
                            new_low = math.floor(min(y_limits[0], 0))
                    else:
                        if (y_limits[1] - y_limits[0]) < 30:
                            new_high = math.ceil(((y_limits[1] - y_limits[0]) / 2) + 10)
                            new_low = new_high * -1
                        else:
                            new_high = math.ceil(max(y_limits[1], 0))
                            new_low = math.floor(min(y_limits[0], 0))

                ax.set_ylim(new_low, new_high)
                ax.set_yticks(ax.get_yticks())
                ax.yaxis.set_major_locator(ticker.AutoLocator())
                ax.set_yticks(ax.get_yticks())  # This is used twice to avoid half-integer tick values

            elif ax.get_yscale() == 'symlog':
                y_limits = ax.get_ylim()
                new_high = 10.0 ** math.ceil(math.log(max(y_limits[1], 11), 10))
                new_low = -1 * 10.0 ** math.ceil(math.log(max(abs(y_limits[0]), 11), 10))
                ax.set_ylim(new_low, new_high)

                ax.tick_params(axis='y', which='major', labelrotation=90)
                plt.setp(ax.get_yticklabels(), va='center')

            ax.yaxis.set_major_formatter(ticker.FormatStrFormatter('%d'))  # Prevent scientific notation

    def convert_station(self, station):
        """
        Converts a single station name into a number, negative if the stations was S or W
        :return: Integer station number
        """
        if re.match(r"\d+(S|W)", station):
            station = (-int(re.sub(r"\D", "", station)))

        else:
            station = (int(re.sub(r"\D", "", station)))

        return station

    def get_profile_data(self, pem_file, component):
        """
        Transforms the data of a single component so it is ready to be plotted for LIN and LOG plots. Only for PEM data.
        :param component: A single component (i.e. Z, X, or Y)
        :return: Dictionary where each key is a channel, and the values of those keys are a list of
        dictionaries which contain the stations and readings of all readings of that channel
        """
        profile_data = {}
        component_data = list(filter(lambda d: d['Component'] == component, pem_file.data))
        num_channels = len(component_data[0]['Data'])

        for channel in range(0, num_channels):
            channel_data = []

            for i, station in enumerate(component_data):
                reading = station['Data'][channel]
                station_number = int(self.convert_station(station['Station']))
                channel_data.append({'Station': station_number, 'Reading': reading})

            profile_data[channel] = sorted(channel_data, key=lambda x: x['Station'])

        return profile_data

    def get_channel_data(self, channel, profile_data):
        """
        Get the profile-mode data for a given channel. Only for PEM data.
        :param channel: int, channel number
        :param profile_data: dict, data in profile-mode
        :return: data in list form and corresponding stations as a list
        """
        data = []
        stations = []

        for station in profile_data[channel]:
            data.append(station['Reading'])
            stations.append(station['Station'])

        return data, stations

    def get_interp_data(self, profile_data, stations, survey_type, hide_gaps=True, gap=None, segments=1000,
                        interp_method='linear'):
        """
        Interpolates the data using 1-D piecewise linear interpolation. The data is segmented
        into 1000 segments.
        :param profile_data: The EM data of a single channel in profile mode
        :param segments: Number of segments to interpolate
        :param hide_gaps: Bool: Whether or not to hide gaps
        :param gap: The minimum length threshold above which is considered a gap
        :return: The interpolated data and stations
        """

        def calc_gaps(stations, gap):

            if 'borehole' in survey_type.casefold():
                min_gap = 50
            elif 'surface' in survey_type.casefold():
                min_gap = 200
            station_gaps = np.diff(stations)

            if gap is None:
                gap = max(int(stats.mode(station_gaps)[0] * 2), min_gap)

            gap_intervals = [(stations[i], stations[i + 1]) for i in range(len(stations) - 1) if
                             station_gaps[i] > gap]

            return gap_intervals

        stations = np.array(stations, dtype='float64')
        readings = np.array(profile_data, dtype='float64')
        x_intervals = np.linspace(stations[0], stations[-1], segments)
        f = interp.interp1d(stations, readings, kind=interp_method)

        interpolated_y = f(x_intervals)

        if hide_gaps:
            gap_intervals = calc_gaps(stations, gap)

            # Masks the intervals that are between gap[0] and gap[1]
            for gap in gap_intervals:
                interpolated_y = np.ma.masked_where((x_intervals > gap[0]) & (x_intervals < gap[1]),
                                                    interpolated_y)

        return interpolated_y, x_intervals

    def draw_lines(self, pem_file, component, ax, channel_low, channel_high, hide_gaps=True):
        """
        Plots the lines into an axes of a figure. Not for step figures.
        :param ax: Axes of a figure, either LIN or LOG figure objects
        :param channel_low: The first channel to be plotted
        :param channel_high: The last channel to be plotted
        :param component: String letter representing the component to plot (X, Y, or Z)
        """

        line_color = 'k'
        segments = 1000  # The data will be broken in this number of segments
        offset = segments * 0.1  # Used for spacing the annotations
        profile_channel_data = self.get_profile_data(pem_file, component)

        for k in range(channel_low, (channel_high + 1)):
            # Gets the profile data for a single channel, along with the stations
            channel_data, stations = self.get_channel_data(k, profile_channel_data)

            # Interpolates the channel data, also returns the corresponding x intervals
            interp_data, x_intervals = self.get_interp_data(channel_data, stations, pem_file.survey_type,
                                                       segments=segments, hide_gaps=hide_gaps)

            ax.plot(x_intervals, interp_data, color=line_color)

            # Mask is used to hide data within gaps
            mask = np.isclose(interp_data, interp_data.astype('float64'))
            x_intervals = x_intervals[mask]
            interp_data = interp_data[mask]

            # Annotating the lines
            for i, x_position in enumerate(x_intervals[int(offset)::int(len(x_intervals) * 0.4)]):
                y = interp_data[list(x_intervals).index(x_position)]

                if k == 0:
                    ax.annotate('PP', xy=(x_position, y), xycoords="data", size=7.5, va='center_baseline', ha='center',
                                color=line_color)

                else:
                    ax.annotate(str(k), xy=(x_position, y), xycoords="data", size=7.5, va='center_baseline',
                                ha='center',
                                color=line_color)

            offset += len(x_intervals) * 0.15

            if offset >= len(x_intervals) * 0.85:
                offset = len(x_intervals) * 0.10

    def add_title(self, pem_file, component, step=False):
        """
        Adds the title header to a figure
        """
        header = pem_file.header
        survey_type = pem_file.survey_type
        timebase = float(header['Timebase'])
        timebase_freq = ((1 / (timebase / 1000)) / 4)
        step_flux_timebase = f"({timebase * 2:.2f} ms Step)" if step is True and 'fluxgate' in survey_type.lower() else ''

        if 'borehole' in survey_type.casefold():
            s_title = 'Hole'
        else:
            s_title = 'Line'

        plt.figtext(0.550, 0.960, 'Crone Geophysics & Exploration Ltd.',
                    fontname='Century Gothic', fontsize=11, ha='center')

        plt.figtext(0.550, 0.945, f"{survey_type} Pulse EM Survey", family='cursive', style='italic',
                    fontname='Century Gothic', fontsize=10, ha='center')

        plt.figtext(0.145, 0.935, f"Timebase: {timebase:.2f} ms {step_flux_timebase}\n" +
                    f"Base Frequency: {str(round(timebase_freq, 2))} Hz\n" +
                    f"Current: {float(pem_file.tags.get('Current')):.1f} A",
                    fontname='Century Gothic', fontsize=10, va='top')

        plt.figtext(0.550, 0.935, f"{s_title}: {header.get('LineHole')}\n" +
                    f"Loop: {header.get('Loop')}\n" +
                    f"{component} Component",
                    fontname='Century Gothic', fontsize=10, va='top', ha='center')

        plt.figtext(0.955, 0.935, f"{header.get('Client')}\n" +
                    f"{header.get('Grid')}\n" +
                    f"{header['Date']}\n",
                    fontname='Century Gothic', fontsize=10, va='top', ha='right')


class LINPlotter(PlotMethods):
    """
     Plots the data into the LIN figure
     :return: Matplotlib Figure object
     """

    def __init__(self):
        super().__init__()

    def plot(self, pem_file, component, figure, x_min=None, x_max=None, hide_gaps=True):

        def add_ylabels():
            units = 'nT/s' if 'induction' in pem_file.survey_type.lower() else 'pT'
            for i in range(len(figure.axes) - 1):
                ax = figure.axes[i]
                if i == 0:
                    ax.set_ylabel(f"Primary Pulse\n({units})")
                else:
                    ax.set_ylabel(f"Channel {channel_bounds[i][0]} - {channel_bounds[i][1]}\n({units})")

        def calc_channel_bounds():
            # channel_bounds is a list of tuples showing the inclusive bounds of each data plot
            channel_bounds = [None] * 4
            num_channels_per_plot = int((num_channels - 1) // 4)
            remainder_channels = int((num_channels - 1) % 4)

            for k in range(0, len(channel_bounds)):
                channel_bounds[k] = (k * num_channels_per_plot + 1, num_channels_per_plot * (k + 1))

            for i in range(0, remainder_channels):
                channel_bounds[i] = (channel_bounds[i][0], (channel_bounds[i][1] + 1))
                for k in range(i + 1, len(channel_bounds)):
                    channel_bounds[k] = (channel_bounds[k][0] + 1, channel_bounds[k][1] + 1)

            channel_bounds.insert(0, (0, 0))
            return channel_bounds

        num_channels = int(pem_file.header['NumChannels']) + 1
        channel_bounds = calc_channel_bounds()

        # Plotting section
        for i, group in enumerate(channel_bounds):
            ax = figure.axes[i]
            self.draw_lines(pem_file, component, ax, group[0], group[1], hide_gaps=hide_gaps)

        self.add_title(pem_file, component, figure)
        add_ylabels()
        self.format_figure(figure)
        self.format_yaxis(pem_file, figure, step=False)
        self.format_xaxis(pem_file, component, figure, x_min, x_max)
        return figure


class LOGPlotter(PlotMethods):
    """
     Plots the data into the LOG figure
     :return: Matplotlib Figure object
     """

    def __init__(self):
        super().__init__()

    def plot(self, pem_file, component, figure, x_min=None, x_max=None, hide_gaps=True):
        def add_ylabels():
            units = 'nT/s' if 'induction' in pem_file.survey_type.lower() else 'pT'
            ax = figure.axes[0]
            ax.set_ylabel(f"Primary Pulse to Channel {str(num_channels - 1)}\n({units})")

        num_channels = int(pem_file.header['NumChannels']) + 1

        # Plotting section
        ax = figure.axes[0]
        self.draw_lines(pem_file, component, ax, 0, num_channels - 1, hide_gaps=hide_gaps)

        self.add_title(pem_file, component, figure)
        add_ylabels()
        self.format_figure(figure)
        self.format_yaxis(pem_file, figure, step=False)
        self.format_xaxis(pem_file, component, figure, x_min, x_max)
        return figure


class STEPPlotter(PlotMethods):
    """
     Plots the data from an RI file into the STEP figure
     :return: Matplotlib Figure object
     """

    def __init__(self):
        super().__init__()

    def plot(self, pem_file, ri_file, component, figure, x_min=None, x_max=None, hide_gaps=True):

        def add_ylabel(profile_data, num_channels_to_plot):
            fluxgate = True if 'fluxgate' in survey_type.lower() else False
            units = 'pT' if fluxgate is True else 'nT/s'
            channels = [re.findall('\d+', key)[0] for key in profile_data if re.match('Ch', key)]

            figure.axes[0].set_ylabel("TP = Theoretical Primary\n"
                                      f"{'PP = Calculated PP x Ramp' if fluxgate is True else 'PP = Last Ramp Channel'}\n"
                                      f"S1 = Calculated Step Ch.1\n({units})")
            figure.axes[1].set_ylabel("Deviation from TP\n"
                                      "(% Total Theoretical)")
            figure.axes[2].set_ylabel("Step Channels 2 - 4\n"
                                      "Deviation from S1\n"
                                      "(% Total Theoretical)")
            figure.axes[3].set_ylabel("Pulse EM Off-time\n"
                                      f"Channels {str(min(channels[-num_channels_to_plot:]))} - "
                                      f"{str(max(channels[-num_channels_to_plot:]))}\n"
                                      f"({units})")

        def annotate_line(ax, annotation, interp_data, x_intervals, offset):

            for i, x_position in enumerate(x_intervals[int(offset)::int(len(x_intervals) * 0.4)]):
                y = interp_data[list(x_intervals).index(x_position)]

                ax.annotate(str(annotation), xy=(x_position, y), xycoords="data", size=7.5, va='center_baseline',
                            ha='center',
                            color=line_color)

        def draw_step_lines(fig, profile_data, hide_gaps=True):
            """
            Plotting the lines for step plots made from RI files.
            :param fig: step_fig Figure object
            :param profile_data: RI file data tranposed to profile mode
            :return: step_fig object with lines plotted
            """

            segments = 1000  # The data will be broken in this number of segments
            offset = segments * 0.1  # Used for spacing the annotations

            keys = ['Theoretical PP', 'Measured PP', 'S1', '(M-T)*100/Tot', '(S1-T)*100/Tot', '(S2-S1)*100/Tot', 'S3%',
                    'S4%']
            annotations = ['TP', 'PP', 'S1', 'PP', 'S1', 'S2', 'S3', 'S4']
            stations = profile_data['Stations']

            for i, key in enumerate(keys):
                interp_data, x_intervals = self.get_interp_data(profile_data[key], stations, survey_type,
                                                                hide_gaps=hide_gaps)

                if i < 3:  # Plotting TP, PP, and S1 to the first axes
                    ax = fig.axes[0]
                    ax.plot(x_intervals, interp_data, color=line_color)
                    annotate_line(ax, annotations[i], interp_data, x_intervals, offset)
                    offset += len(x_intervals) * 0.15
                elif i < 5:  # Plotting the PP and S1% to the second axes
                    if i == 3:  # Resetting the annotation positions
                        offset = segments * 0.1
                    ax = fig.axes[1]
                    ax.plot(x_intervals, interp_data, color=line_color)
                    annotate_line(ax, annotations[i], interp_data, x_intervals, offset)
                    offset += len(x_intervals) * 0.15
                else:  # Plotting S2% to S4% to the third axes
                    if i == 5:
                        offset = segments * 0.1
                    ax = fig.axes[2]
                    ax.plot(x_intervals, interp_data, color=line_color)
                    annotate_line(ax, annotations[i], interp_data, x_intervals, offset)
                    offset += len(x_intervals) * 0.15
                if offset >= len(x_intervals) * 0.85:
                    offset = len(x_intervals) * 0.10

            offset = segments * 0.1
            # Plotting the off-time channels to the fourth axes
            for i, channel in enumerate(off_time_channel_data[-num_channels_to_plot:]):
                interp_data, x_intervals = self.get_interp_data(channel, stations, survey_type, hide_gaps=hide_gaps)
                ax = fig.axes[3]
                ax.plot(x_intervals, interp_data, color=line_color)
                annotate_line(ax, str(num_off_time_channels - i), interp_data, x_intervals, offset)
                offset += len(x_intervals) * 0.15
                if offset >= len(x_intervals) * 0.85:
                    offset = len(x_intervals) * 0.10

        def get_profile_step_data(component):
            """
            Transforms the RI data as a profile to be plotted.
            :param component: The component that is being plotted (i.e. X, Y, Z)
            :return: The data in profile mode
            """
            profile_data = {}
            keys = ri_file.columns
            component_data = list(filter(lambda d: d['Component'] == component, ri_file.data))

            for key in keys:
                if key is not 'Gain' and key is not 'Component':
                    if key is 'Station':
                        key = 'Stations'
                        profile_data[key] = [self.convert_station(station['Station']) for station in component_data]
                    else:
                        profile_data[key] = [float(station[key]) for station in component_data]
            return profile_data

        survey_type = pem_file.survey_type
        profile_data = get_profile_step_data(component)
        off_time_channel_data = [profile_data[key] for key in profile_data if re.match('Ch', key)]
        num_off_time_channels = len(off_time_channel_data) + 10
        num_channels_to_plot = round(num_off_time_channels / 4)

        draw_step_lines(figure, profile_data, hide_gaps=hide_gaps)

        self.add_title(pem_file, component, step=True)
        add_ylabel(profile_data, num_channels_to_plot)
        self.format_figure(figure, step=True)
        self.format_yaxis(pem_file, figure, step=True)
        self.format_xaxis(pem_file, component, figure, x_min, x_max)
        return figure


class RotnAnnotation(mtext.Annotation):
    """
    Text label object that rotates relative to the plot data based on the angle between the points given
    :param label_str: label str
    :param label_xy label position
    :param p: Point 1
    :param pa: Point 2
    :param ax: Axes object
    :param kwargs: text object kwargs
    """

    def __init__(self, label_str, label_xy, p, pa=None, ax=None, hole_collar=False, **kwargs):
        self.ax = ax or plt.gca()
        self.p = p
        self.pa = pa
        self.hole_collar = hole_collar
        self.kwargs = kwargs
        if not pa:
            self.pa = label_xy
        self.calc_angle_data()
        self.kwargs.update(rotation_mode=kwargs.get("rotation_mode", "anchor"))

        mtext.Annotation.__init__(self, label_str, label_xy, **kwargs)
        self.set_transform(mtransforms.IdentityTransform())
        if 'clip_on' in kwargs:
            self.set_clip_path(self.ax.patch)
        self.ax._add_text(self)

    def calc_angle_data(self):
        ang = np.arctan2(self.p[1] - self.pa[1], self.p[0] - self.pa[0])
        deg = np.rad2deg(ang)
        if self.hole_collar is True:
            deg = deg - 90
            self.kwargs.update(xytext=(0, 2), textcoords='offset points')
        # else:
        if deg > 90 or deg < -90:
            deg = deg - 180
            if self.hole_collar:
                self.kwargs.update(va='top')
                self.kwargs.update(xytext=(0, -4), textcoords='offset points')
        self.angle_data = deg

    def calc_xy_offset(self):
        pass

    def _get_rotation(self):
        return self.ax.transData.transform_angles(np.array((self.angle_data,)),
                                                  np.array([self.pa[0], self.pa[1]]).reshape((1, 2)))[0]

    def _set_rotation(self, rotation):
        pass

    _rotation = property(_get_rotation, _set_rotation)


class MapPlotMethods:
    """
    Collection of methods for plotting maps.
    """

    def get_extents(self, pem_file):
        """
        Calculate the GPS extents of each dimension of the PEM file.
        :param pem_file: PEMFile object
        :return: Range of GPS in all 3 components
        """
        logging.info('MapPlotMethods - Retrieving extents')
        loop_coords = pem_file.get_loop_coords()
        collar = pem_file.get_collar_coords()[0]
        segments = pem_file.get_hole_geometry()
        min_x = min([float(row[0]) for row in loop_coords] + [float(collar[0])])
        max_x = max([float(row[0]) for row in loop_coords] + [float(collar[0])])
        min_y = min([float(row[1]) for row in loop_coords] + [float(collar[1])])
        max_y = max([float(row[1]) for row in loop_coords] + [float(collar[1])])
        min_z = min(
            [float(row[2]) for row in loop_coords] + [float(collar[2])] + [float(collar[2]) - float(segments[-1][4])])
        max_z = max(
            [float(row[2]) for row in loop_coords] + [float(collar[2])] + [float(collar[2]) - float(segments[-1][4])])
        return min_x, max_x, min_y, max_y, min_z, max_z

    def get_3D_borehole_projection(self, collar_gps, segments, interp_segments=None):
        """
        Uses the segments to create a 3D projection of a borehole trace. Can be broken up into segments and interpolated.
        :param collar_gps: Collar GPS of the borehole (easting, northing, elevation)
        :param segments: Segments of a borehole trace (Azimuth, dip, segment length, units, depth)
        :param interp_segments: Desired number of segments to be output
        :return: list of hole trace tuples (easting, northing, elevation)
        """
        logging.info('MapPlotMethods - Retrieving 3D borehole projection')
        if not collar_gps:
            return None
        else:
            collar_x, collar_y, collar_z = collar_gps[0], collar_gps[1], collar_gps[2]

            if interp_segments:
                azimuths = [float(row[0]) for row in segments]
                dips = [float(row[1]) for row in segments]
                depths = [float(row[-1]) for row in segments]
                units = segments[0][-2]

                interp_depths = np.linspace(depths[0], depths[-1], interp_segments)
                interp_az = np.interp(interp_depths, depths, azimuths)
                interp_dip = np.interp(interp_depths, depths, dips)
                interp_lens = [float(segments[0][-1])]

                for depth, next_depth in zip(interp_depths[:-1], interp_depths[1:]):
                    interp_lens.append(next_depth - depth)

                segments = list(
                    zip(interp_az, interp_dip, interp_lens, [units] * len(interp_depths), interp_depths))

            eastings = [float(collar_x)]
            northings = [float(collar_y)]
            depths = [float(collar_z)]
            azimuth = None

            for segment in segments:
                azimuth = math.radians(float(segment[0]))
                dip = math.radians(float(segment[1]))
                seg_l = float(segment[2])
                delta_seg_l = seg_l * math.cos(dip)
                dz = seg_l * math.sin(dip)
                dx = delta_seg_l * math.sin(azimuth)
                dy = delta_seg_l * math.cos(azimuth)

                eastings.append(float(eastings[-1] + dx))
                northings.append(float(northings[-1] + dy))
                depths.append(float(depths[-1] - dz))

            return eastings, northings, depths

    def get_section_extents(self, pem_file, hole_depth=None, section_plot=False, plot_width=None):
        """
        Find the 50th percentile down the hole, use that as the center of the section, and find the
        X and Y extents of that section line. Default azimuth used is from the 80th percentile if no hole_depth is given.
        :param pem_file: PEMFile object
        :param hole_depth: Desired hole depth to use to find the azimuth of the section
        :param section_plot: Bool: If True, will scale the plot such that the scale is of an acceptable value. Used
        for 2D section plots.
        :param plot_width: Physical width of the plot in meters.
        :return: XY coordinates of each end of the section line, and the azimuth of that line.
        """
        def calc_scale_factor(p1, p2, plot_width):
            """
            Modifies the two cross-section points so they will create a map with an appropriate scale
            :param p1: xy tuple of one of the current extent points
            :param p2: xy tuple of the other extent point
            :return: A factor by which to multiply the change in X and change in Y
            """

            def get_scale_factor():
                # num_digit = len(str(int(current_scale)))  # number of digits in number
                num_digit = int(np.floor(np.log10(current_scale)))  # number of digits in number
                scale_nums = [1., 1.25, 1.5, 2., 5.]
                possible_scales = [num * 10 ** num_digit for num in
                                   scale_nums + list(map(lambda x: x * 10, scale_nums))]
                new_scale = min(filter(lambda x: x > current_scale, possible_scales),
                                key=lambda x: x - current_scale)
                self.map_scale = new_scale
                scale_factor = new_scale / current_scale
                return scale_factor

            xmin, xmax, ymin, ymax = min([p1[0], p2[0]]), max([p1[0], p2[0]]), min([p1[1], p2[1]]), max([p1[1], p2[1]])
            dist = math.sqrt((xmax - xmin) ** 2 + (ymax - ymin) ** 2)
            bbox_width = plot_width  # Section plot width in m (after subplot adjustment)
            current_scale = dist / bbox_width
            scale_factor = get_scale_factor()
            return scale_factor

        collar = pem_file.get_collar_coords()[0]
        segments = pem_file.get_hole_geometry()
        azimuths = [float(row[0]) for row in segments]
        dips = [float(row[1]) for row in segments]
        depths = [float(row[-1]) for row in segments]
        units = segments[0][-2]

        # Splitting the segments into 1000 pieces
        interp_depths = np.linspace(depths[0], depths[-1], 1000)
        interp_az = np.interp(interp_depths, depths, azimuths)
        interp_dip = np.interp(interp_depths, depths, dips)
        interp_lens = [float(segments[0][-1])]
        for depth, next_depth in zip(interp_depths[:-1], interp_depths[1:]):
            interp_lens.append(next_depth - depth)

        # Recreating the segments with the interpreted data
        interp_segments = list(zip(interp_az, interp_dip, interp_lens, [units] * len(interp_depths), interp_depths))

        interp_x, interp_y, interp_z = self.get_3D_borehole_projection(collar, interp_segments)

        # Find the depths that are 50% and var percentile% down the hole
        perc_50_depth = np.percentile(interp_depths, 50)
        if not hole_depth:
            hole_depth = np.percentile(interp_depths, 80)

        # Nearest index of the 50th and var percentile% depths
        i_perc_50_depth = min(range(len(interp_depths)), key=lambda i: abs(interp_depths[i] - perc_50_depth))
        i_perc_depth = min(range(len(interp_depths)), key=lambda i: abs(interp_depths[i] - hole_depth))

        line_center_x, line_center_y = interp_x[i_perc_50_depth], interp_y[i_perc_50_depth]
        line_az = interp_az[i_perc_depth]
        print(f"Line azimuth: {line_az:.0f}°")
        line_len = math.ceil(depths[-1] / 400) * 300
        dx = math.cos(math.radians(90 - line_az)) * (line_len / 2)
        dy = math.sin(math.radians(90 - line_az)) * (line_len / 2)

        line_xy_1 = (line_center_x - dx, line_center_y - dy)
        line_xy_2 = (line_center_x + dx, line_center_y + dy)

        if section_plot:
            plot_width = plot_width
            scale_factor = calc_scale_factor(line_xy_1, line_xy_2, plot_width)
            dx = dx * scale_factor
            dy = dy * scale_factor

            line_xy_1 = (line_center_x - dx, line_center_y - dy)
            line_xy_2 = (line_center_x + dx, line_center_y + dy)

        return line_xy_1, line_xy_2, line_az


class PlanMap(MapPlotMethods):
    """
    Draws a plan map on a given Matplotlib figure object. Only makes a plan map for one survey type and timebase.
    :param: pem_Files: list of pem_files
    :param: figure: Matplotlib landscape-oriented figure object
    """

    def __init__(self, pem_files, figure, **kwargs):
        super().__init__()
        self.color = 'black'
        self.fig = figure
        self.pem_files = []

        if not isinstance(pem_files, list):
            pem_files = [pem_files]

        self.survey_type = pem_files[0].survey_type.lower()
        self.timebase = [pem_files[0].header.get('Timebase')]

        for pem_file in pem_files:  # Only allow one kind of survey type per map
            if pem_file.survey_type.lower() == self.survey_type:
                self.pem_files.append(pem_file)
                if pem_file.header.get('Timebase') not in self.timebase:
                    self.timebase.append(pem_file.header.get('Timebase'))

        self.loops = []
        self.loop_names = []
        self.lines = []
        self.collars = []
        self.holes = []
        self.labels = []

        self.loop_handle = None
        self.station_handle = None
        self.collar_handle = None
        self.trace_handle = None
        self.map_scale = None
        self.system = None
        self.zone = None
        self.datum = None

        self.draw_loop_annotations = kwargs.get('LoopAnnotations') if kwargs else False
        self.moving_loop = kwargs.get('MovingLoop') if kwargs else True
        self.title_box = kwargs.get('TitleBox') if kwargs else True
        self.map_grid = kwargs.get('Grid') if kwargs else True
        self.scale_bar = kwargs.get('ScaleBar') if kwargs else True
        self.north_arrow = kwargs.get('NorthArrow') if kwargs else True
        self.show_legend = kwargs.get('Legend') if kwargs else True
        self.draw_loops = kwargs.get('DrawLoops') if kwargs else True
        self.draw_lines = kwargs.get('DrawLines') if kwargs else True
        self.draw_hole_collars = kwargs.get('DrawHoleCollars') if kwargs else True
        self.draw_hole_traces = kwargs.get('DrawHoleTraces') if kwargs else True
        self.loop_labels = kwargs.get('LoopLabels') if kwargs else True
        self.line_labels = kwargs.get('LineLabels') if kwargs else True
        self.hole_collar_labels = kwargs.get('HoleCollarLabels') if kwargs else True
        self.hole_depth_labels = kwargs.get('HoleDepthLabels') if kwargs else True
        self.crs = self.get_crs(kwargs.get(
            'CRS')) if kwargs else None  # self.get_crs({'Coordinate System': 'UTM', 'Zone': '10 North', 'Datum': 'WGS 1984'})

        self.gps_editor = GPSEditor
        if self.crs:
            self.ax = self.fig.add_subplot(projection=self.crs)
            # self.inset_ax = self.fig.add_axes([0.1, 0.5, 0.5, 0.3], projection=self.crs)
            self.plot_pems()

    def get_crs(self, crs):
        if crs is None:
            return None
        else:
            self.system = crs.get('Coordinate System')
            self.zone = crs.get('Zone')
            self.datum = crs.get('Datum')

            if self.system == 'UTM':
                zone_num = int(re.findall('\d+', self.zone)[0])
                south_hemis = True if 'South' in self.zone else False
                globe = ccrs.Globe(datum=re.sub(' 19', '', self.datum))
                return ccrs.UTM(zone_num, southern_hemisphere=south_hemis, globe=globe)
            elif self.system == 'Latitude/Longitude':
                return ccrs.Geodetic()

    def plot_pems(self):

        def add_loop_to_map(pem_file):
            loop_gps = pem_file.get_loop_coords()
            if loop_gps and loop_gps not in self.loops:
                self.loops.append(loop_gps)
                self.loop_names.append(pem_file.header.get('Loop'))
                loop_center = self.gps_editor().get_loop_center(copy.copy(loop_gps))
                eastings, northings = [float(coord[0]) for coord in loop_gps], [float(coord[1]) for coord in loop_gps]
                eastings.insert(0, eastings[-1])  # To close up the loop
                northings.insert(0, northings[-1])
                zorder = 4 if not self.moving_loop else 6
                if self.loop_labels:
                    loop_label = self.ax.text(loop_center[0], loop_center[1], f"Tx Loop {pem_file.header.get('Loop')}",
                                              ha='center',
                                              color=self.color, zorder=zorder,
                                              path_effects=label_buffer)  # Add the loop name

                self.loop_handle, = self.ax.plot(eastings, northings, color=self.color, label='Transmitter Loop',
                                                 transform=self.crs, zorder=2)  # Plot the loop

                # Moves the loop label away from other labels
                # adjust_text([loop_label], add_objects=self.labels, ax=self.ax, avoid_text=True, avoid_points=False,
                #             autoalign=True)

                if self.draw_loop_annotations:
                    for i, (x, y) in enumerate(list(zip(eastings, northings))):
                        self.fig.annotate(i, xy=(x, y), va='center', ha='center', fontsize=7, path_effects=label_buffer,
                                     zorder=3, color=self.color, transform=self.ax.transData)

        def add_line_to_map(pem_file):

            line_gps = pem_file.get_station_coords()
            # Plotting the line and adding the line label
            if line_gps and line_gps not in self.lines:
                self.lines.append(line_gps)
                eastings, northings = [float(coord[0]) for coord in line_gps], [float(coord[1]) for coord in line_gps]
                angle = math.degrees(math.atan2(northings[-1]-northings[0], eastings[-1] - eastings[0]))

                if abs(angle) > 90:
                    x, y = eastings[-1], northings[-1]
                    # Flip the label if it's upside-down
                    angle = angle - 180
                else:
                    x, y = eastings[0], northings[0]

                line_label = self.ax.text(x, y, f" {pem_file.header.get('LineHole')} ",
                                          rotation=angle, rotation_mode='anchor', ha='right', va='center', zorder=5, color=self.color,
                                          path_effects=label_buffer)
                self.labels.append(line_label)
                self.station_handle, = self.ax.plot(eastings, northings, '-o', markersize=3, color=self.color,
                                                    markerfacecolor='w', markeredgewidth=0.3,
                                                    label='Surface Line', transform=self.crs, zorder=2)  # Plot the line

        def add_hole_to_map(pem_file):

            if self.draw_hole_collars is True:
                try:
                    collar = pem_file.get_collar_coords()[0]
                except IndexError:
                    return
                else:
                    collar_x, collar_y, collar_z = float(collar[0]), float(collar[1]), float(collar[2])
                segments = pem_file.get_hole_geometry()
                if segments and collar:
                    seg_x, seg_y, seg_z = self.get_3D_borehole_projection(collar, segments, interp_segments=1000)
                else:
                    seg_x, seg_y = None, None

                if collar and collar not in self.collars:
                    self.collars.append(collar)
                    marker_style = dict(marker='o', color='white', markeredgecolor=self.color, markersize=8)
                    self.collar_handle, = self.ax.plot(collar_x, collar_y, fillstyle='full',
                                                       label='Borehole Collar', zorder=4, **marker_style)
                    # Add the hole label at the collar
                    if self.hole_collar_labels:
                        angle = math.degrees(math.atan2(seg_y[-1] - seg_y[0], seg_x[-1] - seg_x[0]))
                        align = 'left' if angle > 90 or angle < -90 else 'right'
                        collar_label = self.ax.text(collar_x, collar_y, f"  {pem_file.header.get('LineHole')}  ",
                                                    va='center', ha=align, color=self.color, zorder=5,
                                                    path_effects=label_buffer)
                        self.labels.append(collar_label)

                    if seg_x and seg_y and self.draw_hole_traces is True:

                        # Calculating tick indexes. Ticks are placed at evenly spaced depths.
                        # depths = np.linspace(min(seg_z), collar_z, 10)  # Spaced such that there are 10 segments
                        depths = np.arange(collar_z, min(seg_z)-51, -50)  # Spaced every 50m, starting from the top

                        # Find the index of the seg_z depth nearest each depths value.
                        indexes = [min(range(len(seg_z)), key=lambda i: abs(seg_z[i] - depth)) for depth in depths]

                        # Hole trace is plotted using marker positions so that they match perfectly.
                        index_x = [seg_x[index] for index in indexes]  # Marker positions
                        index_y = [seg_y[index] for index in indexes]

                        # Plotting the hole trace
                        self.trace_handle, = self.ax.plot(index_x, index_y, '--', color=self.color)

                        # Plotting the markers
                        for index in indexes[1:-1]:
                            angle = math.degrees(math.atan2(seg_y[index+1] - seg_y[index], seg_x[index+1] - seg_x[index]))
                            self.ax.plot(seg_x[index], seg_y[index], markersize=5, marker=(2, 0, angle),
                                         mew=.5, color=self.color)

                        # Add the end tick for the borehole trace and the label
                        angle = math.degrees(math.atan2(seg_y[-1] - seg_y[-2], seg_x[-1] - seg_x[-2]))
                        self.ax.text(seg_x[-1], seg_y[-1], '|', rotation=angle, color=self.color, va='center',
                                     ha='center', fontsize=9)

                        if self.hole_depth_labels:
                            bh_depth = self.ax.text(seg_x[-1], seg_y[-1], f"  {float(segments[-1][-1]):.0f} m",
                                                    rotation=angle+90, fontsize=8, color=self.color,
                                                    path_effects=label_buffer, zorder=3, rotation_mode='anchor')
                else:
                    pass

        for pem_file in self.pem_files:
            label_buffer = [patheffects.Stroke(linewidth=1.5, foreground='white'), patheffects.Normal()]

            if 'surface' in pem_file.survey_type.lower() and self.draw_lines is True:
                add_line_to_map(pem_file)

            if 'borehole' in pem_file.survey_type.lower() and self.draw_hole_collars is True:
                add_hole_to_map(pem_file)

            if self.draw_loops is True:
                if len(self.loops) == 0:
                    add_loop_to_map(pem_file)

    def format_figure(self):

        def add_scale_bar():
            """
            Adds scale bar to the axes.
            Gets the width of the map in meters, find the best bar length number, and converts the bar length to
            equivalent axes percentage, then plots using axes transform so it is static on the axes.
            :return: None
            """

            def myround(x, base=5):
                return base * math.ceil(x / base)

            def add_rectangles(left_bar_pos, bar_center, right_bar_pos, y):
                rect_height = 0.005
                line_width = 0.4
                sm_rect_width = (bar_center - left_bar_pos) / 5
                sm_rect_xs = np.arange(left_bar_pos, bar_center, sm_rect_width)
                big_rect_x = bar_center
                big_rect_width = right_bar_pos - bar_center

                # Adding the small rectangles
                for i, rect_x in enumerate(sm_rect_xs):  # Top set of small rectangles
                    fill = 'w' if i % 2 == 0 else 'k'
                    patch = patches.Rectangle((rect_x, y), sm_rect_width, rect_height, ec='k', linewidth=line_width,
                                              facecolor=fill, transform=self.ax.transAxes, zorder=9)
                    self.ax.add_patch(patch)
                for i, rect_x in enumerate(sm_rect_xs):  # Bottom set of small rectangles
                    fill = 'k' if i % 2 == 0 else 'w'
                    patch = patches.Rectangle((rect_x, y - rect_height), sm_rect_width, rect_height, ec='k', zorder=9,
                                              linewidth=line_width, facecolor=fill, transform=self.ax.transAxes)
                    self.ax.add_patch(patch)

                # Adding the big rectangles
                patch1 = patches.Rectangle((big_rect_x, y), big_rect_width, rect_height, ec='k', facecolor='k',
                                           linewidth=line_width, transform=self.ax.transAxes, zorder=9)
                patch2 = patches.Rectangle((big_rect_x, y - rect_height), big_rect_width, rect_height, ec='k',
                                           facecolor='w', linewidth=line_width, transform=self.ax.transAxes, zorder=9)
                self.ax.add_patch(patch1)
                self.ax.add_patch(patch2)

            bar_center = 0.5  # Half way across the axes
            bar_height_pos = 0.05
            map_width = self.ax.get_extent()[1] - self.ax.get_extent()[0]
            num_digit = int(np.floor(np.log10(map_width)))  # number of digits in number
            bar_map_length = round(map_width, -num_digit)  # round to 1sf
            bar_map_length = myround(bar_map_length / 8, base=0.5 * 10 ** num_digit)  # Rounds to the nearest 1,2,5...
            if bar_map_length > 10000:
                units = 'kilometers'
                bar_map_length = bar_map_length / 1000
            else:
                units = 'meters'
            buffer = [patheffects.Stroke(linewidth=1, foreground='white'), patheffects.Normal()]
            bar_ax_length = bar_map_length / map_width
            left_bar_pos = bar_center - (bar_ax_length / 2)
            right_bar_pos = bar_center + (bar_ax_length / 2)

            # Simple tick scale
            # self.ax.plot([left_bar_pos, bar_center, right_bar_pos], [bar_height_pos]*3, color='k',
            #              linewidth=1, transform=self.ax.transAxes, path_effects=buffer)
            # self.ax.plot([left_bar_pos], [bar_height_pos], marker=3, color='k', lw=5,transform=self.ax.transAxes,
            #              path_effects=buffer)
            # self.ax.plot([right_bar_pos], [bar_height_pos], marker=3, color='k', transform=self.ax.transAxes,
            #              path_effects=buffer)
            # self.ax.text(bar_center, bar_height_pos+.005, f"{bar_map_length:.0f} {units}", ha='center',
            #              transform=self.ax.transAxes, path_effects=buffer)

            add_rectangles(left_bar_pos, bar_center, right_bar_pos, bar_height_pos)
            self.ax.text(left_bar_pos, bar_height_pos + .009, f"{bar_map_length / 2:.0f}", ha='center',
                         transform=self.ax.transAxes, path_effects=buffer, fontsize=7, zorder=9)
            self.ax.text(bar_center, bar_height_pos + .009, f"0", ha='center',
                         transform=self.ax.transAxes, path_effects=buffer, fontsize=7, zorder=9)
            self.ax.text(right_bar_pos, bar_height_pos + .009, f"{bar_map_length / 2:.0f}", ha='center',
                         transform=self.ax.transAxes, path_effects=buffer, fontsize=7, zorder=9)
            self.ax.text(bar_center, bar_height_pos - .018, f"({units})", ha='center',
                         transform=self.ax.transAxes, path_effects=buffer, fontsize=7, zorder=9)

        def set_size():
            """
            Re-size the extents to make the axes 11" by 8.5"
            :param ax: GeoAxes object
            :return: None
            """
            bbox = self.ax.get_window_extent().transformed(self.fig.dpi_scale_trans.inverted())
            xmin, xmax, ymin, ymax = self.ax.get_extent()
            map_width, map_height = xmax - xmin, ymax - ymin

            current_ratio = map_width / map_height

            if current_ratio < (bbox.width / bbox.height):
                new_height = map_height
                new_width = new_height * (
                        bbox.width / bbox.height)  # Set the new width to be the correct ratio larger than height

            else:
                new_width = map_width
                new_height = new_width * (bbox.height / bbox.width)
            x_offset = 0
            y_offset = 0.06 * new_height
            new_xmin = (xmin - x_offset) - ((new_width - map_width) / 2)
            new_xmax = (xmax - x_offset) + ((new_width - map_width) / 2)
            new_ymin = (ymin + y_offset) - ((new_height - map_height) / 2)
            new_ymax = (ymax + y_offset) + ((new_height - map_height) / 2)

            self.ax.set_extent((new_xmin, new_xmax, new_ymin, new_ymax), crs=self.crs)

        def set_scale():
            """
            Changes the extent of the plot such that the scale is an acceptable value.
            :return: None
            """

            def get_scale_factor():
                # num_digit = len(str(int(current_scale)))  # number of digits in number
                num_digit = int(np.floor(np.log10(current_scale)))  # number of digits in number
                scale_nums = [1., 1.25, 1.5, 2., 2.5, 5.]
                possible_scales = [num * 10 ** num_digit for num in
                                   scale_nums + list(map(lambda x: x * 10, scale_nums))]
                new_scale = min(filter(lambda x: x > current_scale * 1.30, possible_scales),
                                key=lambda x: x - current_scale * 1.30)
                if new_scale == 1500:
                    new_scale = 2000
                self.map_scale = new_scale
                scale_factor = new_scale / current_scale
                return scale_factor

            xmin, xmax, ymin, ymax = self.ax.get_extent()
            map_width, map_height = xmax - xmin, ymax - ymin
            bbox = self.ax.get_window_extent().transformed(self.fig.dpi_scale_trans.inverted())
            current_scale = map_width / (bbox.width * .0254)
            scale_factor = get_scale_factor()
            new_map_height = map_height * scale_factor
            new_map_width = map_width * scale_factor

            new_xmin = xmin - ((new_map_width - map_width) / 2)
            new_xmax = xmax + ((new_map_width - map_width) / 2)
            new_ymin = ymin - ((new_map_height - map_height) / 2)
            new_ymax = ymax + ((new_map_height - map_height) / 2)

            self.ax.set_extent((new_xmin, new_xmax, new_ymin, new_ymax), crs=self.crs)

        def add_title():
            """
            Adds the title box to the plot.
            :return: None
            """

            def get_survey_dates():
                survey_dates = [pem_file.header.get('Date') for pem_file in self.pem_files]
                min_date = min([datetime.strptime(date, '%B %d, %Y') for date in survey_dates])
                max_date = max([datetime.strptime(date, '%B %d, %Y') for date in survey_dates])
                min_date_text = datetime.strftime(min_date, '%B %d')
                max_date_text = datetime.strftime(max_date, '%B %d, %Y')
                survey_date_text = f"Survey Date: {min_date_text} - {max_date_text}" if min_date != max_date else f"Survey Date: {max_date_text}"
                return survey_date_text

            b_xmin = 0.015  # Title box
            b_width = 0.30
            b_ymin = 0.784
            b_height = 0.200
            center_pos = b_xmin + (b_width / 2)
            right_pos = b_xmin + b_width - .01
            left_pos = b_xmin + .01
            top_pos = b_ymin + b_height - 0.020

            # Separating lines
            line_1 = mlines.Line2D([b_xmin, b_xmin + b_width], [top_pos - .045, top_pos - .045],
                                   linewidth=1, color='gray', transform=self.ax.transAxes, zorder=10)

            line_2 = mlines.Line2D([b_xmin, b_xmin + b_width], [top_pos - .115, top_pos - .115],
                                   linewidth=1, color='gray', transform=self.ax.transAxes, zorder=10)

            line_3 = mlines.Line2D([b_xmin, b_xmin + b_width], [top_pos - .160, top_pos - .160],
                                   linewidth=.5, color='gray', transform=self.ax.transAxes, zorder=10)

            # Title box rectangle
            rect = patches.FancyBboxPatch(xy=(b_xmin, b_ymin), width=b_width, height=b_height, edgecolor='k',
                                          boxstyle="round,pad=0.005", facecolor='white', zorder=9,
                                          transform=self.ax.transAxes)

            client = self.pem_files[0].header.get("Client")
            grid = self.pem_files[0].header.get("Grid")
            loops = natural_sort(self.loop_names)
            hole = self.pem_files[0].header.get('LineHole')

            if 'surface' in self.survey_type:
                if self.moving_loop and len(loops) > 1:
                    survey_text = f"Loop: {loops[0]} to {loops[-1]}"
                else:
                    survey_text = f"Loop: {', '.join(loops)}"
            else:
                survey_text = f"Hole: {hole}    Loop: {', '.join(loops)}"

            coord_sys = f"{self.system}{' Zone ' + self.zone.title() if self.zone else ''}, {self.datum.upper()}"
            scale = f"1:{self.map_scale:,.0f}"

            self.ax.text(center_pos, top_pos, 'Crone Geophysics & Exploration Ltd.',
                         fontname='Century Gothic', fontsize=11, ha='center', zorder=10, transform=self.ax.transAxes)

            self.ax.text(center_pos, top_pos - 0.020, f"{'Line' if 'surface' in self.survey_type else 'Hole'}"
            f" and Loop Location Map", family='cursive',
                         fontname='Century Gothic', fontsize=10, ha='center', zorder=10, transform=self.ax.transAxes)

            self.ax.text(center_pos, top_pos - 0.040, f"{self.survey_type.title()} Pulse EM Survey", family='cursive',
                         style='italic',
                         fontname='Century Gothic', fontsize=9, ha='center', zorder=10, transform=self.ax.transAxes)

            self.ax.text(center_pos, top_pos - 0.054, f"{client}\n" + f"{grid}\n"
                         f"{survey_text}", fontname='Century Gothic', fontsize=10, va='top', ha='center', zorder=10,
                         transform=self.ax.transAxes)

            self.ax.text(center_pos, top_pos - 0.124, f"Timebase: {', '.join(self.timebase)} ms\n{get_survey_dates()}",
                         fontname='Century Gothic', fontsize=9, va='top', ha='center', zorder=10,
                         transform=self.ax.transAxes)

            self.ax.text(left_pos, top_pos - 0.167, f"{coord_sys}", family='cursive', style='italic', color='dimgray',
                         fontname='Century Gothic', fontsize=8, va='top', ha='left', zorder=10,
                         transform=self.ax.transAxes)

            self.ax.text(right_pos, top_pos - 0.167, f"Scale {scale}", family='cursive', style='italic',
                         color='dimgray',
                         fontname='Century Gothic', fontsize=8, va='top', ha='right', zorder=10,
                         transform=self.ax.transAxes)

            self.ax.add_patch(rect)
            shadow = patches.Shadow(rect, 0.002, -0.002)
            self.ax.add_patch(shadow)
            self.ax.add_line(line_1)
            self.ax.add_line(line_2)
            self.ax.add_line(line_3)

        def add_north_arrow():
            """
            Adds the north arrow to the plot. The arrow is manually drawn, and is always fixed in position and size.
            :return: None
            """

            def ax_len(pixel_length):  # Calculate the equivalent axes size for a given pixel length
                return shaft_len * (pixel_length / 300)  # 267 is pixel length of old north arrow

            l_width = .5
            top = 0.97
            bot = 0.81
            mid = bot + (top - bot) / 2  # Mid point position of the arrow
            shaft_len = top - bot
            ca = 0.94  # Alignment of the arrow

            # Drawing full arrow polygon using ax.plot
            xs = [ca, ca, ca + ax_len(11), ca, ca, ca - ax_len(6), ca - ax_len(6), ca]
            ys = [top - ax_len(45) + ax_len(8), top, top - ax_len(45), top - ax_len(45) + ax_len(8), bot,
                  bot - ax_len(12), bot + ax_len((41 - 12)), bot + ax_len(41)]
            self.ax.plot(xs, ys, color='k', lw=l_width, transform=self.ax.transAxes)

            # Drawing the N
            xs = [ca - ax_len(12), ca - ax_len(12), ca + ax_len(12), ca + ax_len(12)]  # First N
            ys = [mid - ax_len(21), mid + ax_len(21), mid - ax_len(30) + ax_len(21), mid + ax_len(21)]  # First N
            x2s = [ca - ax_len(12), ca + ax_len(12), ca + ax_len(12)]  # Second diagonal line
            y2s = [mid + ax_len(30) - ax_len(21), mid - ax_len(21),
                   mid - ax_len(30) + ax_len(21)]  # Second diagonal line
            self.ax.plot(xs, ys, color='k', lw=l_width, transform=self.ax.transAxes)
            self.ax.plot(x2s, y2s, color='k', lw=l_width, transform=self.ax.transAxes)

            # Drawing the two side-lines
            x1 = [ca - ax_len(31) - ax_len(36), ca - ax_len(31)]
            x2 = [ca + ax_len(31) + ax_len(36), ca + ax_len(31)]
            y = [mid] * 2
            tick_line1 = mlines.Line2D(x1, y, color='k', lw=l_width, transform=self.ax.transAxes)
            tick_line2 = mlines.Line2D(x2, y, color='k', lw=l_width, transform=self.ax.transAxes)

            self.ax.add_line(tick_line1)
            self.ax.add_line(tick_line2)

        self.fig.subplots_adjust(left=0.03, bottom=0.03, right=0.97, top=0.95)
        set_size()
        set_scale()

        if self.map_grid:
            self.ax.grid(linestyle='dotted', zorder=0)
        else:
            self.ax.grid(False)
        self.ax.xaxis.set_visible(True)  # Required to actually get the labels to show in UTM
        self.ax.yaxis.set_visible(True)
        self.ax.set_yticklabels(self.ax.get_yticklabels(), rotation=90, ha='center')
        if self.system == 'UTM':
            self.ax.yaxis.set_major_formatter(ticker.StrMethodFormatter('{x:,.0f}m N'))
            self.ax.xaxis.set_major_formatter(ticker.StrMethodFormatter('{x:,.0f}m E'))
        self.ax.xaxis.set_ticks_position('top')
        plt.setp(self.ax.get_xticklabels(), fontname='Century Gothic')
        plt.setp(self.ax.get_yticklabels(), fontname='Century Gothic', va='center')

        # self.ax.add_wms(wms='http://vmap0.tiles.osgeo.org/wms/vmap0',
        #                 layers=['basic'])

        if self.scale_bar:
            add_scale_bar()
        if self.north_arrow:
            add_north_arrow()
        if self.title_box:
            add_title()

        if self.show_legend:
            legend_handles = [handle for handle in
                              [self.loop_handle, self.station_handle, self.collar_handle] if
                              handle is not None]
            # Manually add the hole trace legend handle
            if self.draw_hole_traces and 'borehole' in self.survey_type:
                legend_handles.append(
                    mlines.Line2D([], [], linestyle='--', color=self.color, marker='|', label='Borehole Trace'))

            self.ax.legend(handles=legend_handles, title='Legend', loc='lower right', framealpha=1, shadow=True,
                           edgecolor='k')

    def get_map(self):
        """
        Retuns the figure if anything is plotted in it.
        :return: Matplotlib Figure object.
        """
        if any([self.loops, self.lines, self.collars, self.holes]):
            self.format_figure()
            return self.fig
        else:
            return None


class ContourPlot(MapPlotMethods):
    """
    Plot PEM surface data as a contour plot.
    """

    def __init__(self, ax, pem_files, parent=None):
        MapPlotMethods.__init__(self)



class Map3D(MapPlotMethods):
    """
    Class that plots all GPS from PEM Files in 3D. Draws on a given Axes3D object.
    :param: ax: Matplotlib axes object
    :param: pem_files: List of PEMFile objects to plot
    :param: parent: PyQt parent
    :param: set_z: Set Z axis equal to X and Y (for non-section plots)
    """

    def __init__(self, ax, pem_files, parent=None, set_z=True):
        logging.info('Map3D')
        MapPlotMethods.__init__(self)
        self.parent = parent
        self.pem_files = pem_files
        self.ax = ax
        self.set_z = set_z
        self.gps_editor = GPSEditor()
        self.loops = []
        self.loop_artists = []
        self.loop_label_artists = []
        self.loop_anno_artists = []
        self.lines = []
        self.line_artists = []
        self.line_label_artists = []
        self.station_label_artists = []
        self.collars = []
        self.geometries = []
        self.hole_artists = []
        self.hole_label_artists = []
        self.segment_label_artists = []
        self.buffer = [patheffects.Stroke(linewidth=1, foreground='white'), patheffects.Normal()]

    def plot_pems(self):
        logging.info('Map3D - Plotting all PEM files')
        for pem_file in self.pem_files:
            survey_type = pem_file.survey_type.lower()

            self.plot_loop(pem_file)
            if 'surface' in survey_type:
                self.plot_line(pem_file)
            if 'borehole' in survey_type:
                self.plot_hole(pem_file)

    def plot_loop(self, pem_file):
        logging.info('Map3D - Plotting loop')
        loop_coords = pem_file.get_loop_coords()
        if loop_coords:
            loop = [[float(num) for num in row] for row in loop_coords]
            if loop_coords not in self.loops:
                self.loops.append(loop_coords)
                x, y, z = [r[0] for r in loop] + [loop[0][0]], \
                          [r[1] for r in loop] + [loop[0][1]], \
                          [r[2] for r in loop] + [loop[0][2]]
                loop_artist, = self.ax.plot(x, y, z, lw=1, color='blue')
                self.loop_artists.append(loop_artist)
                loop_name = pem_file.header.get('Loop')
                loop_center = self.gps_editor.get_loop_center(loop)
                avg_z = mean(z)
                loop_label_artist = self.ax.text(loop_center[0], loop_center[1], avg_z, loop_name,
                                                 path_effects=self.buffer, color='blue', ha='center', va='center')
                self.loop_label_artists.append(loop_label_artist)

                for i, (x, y, z) in enumerate(zip(x, y, z)):
                    loop_anno_artist = self.ax.text(x, y, z, str(i), color='blue', path_effects=self.buffer,
                                                    va='bottom', ha='center', fontsize=7)
                    self.loop_anno_artists.append(loop_anno_artist)

    def plot_line(self, pem_file):
        logging.info('Map3D - Plotting surface line')
        line_coords = pem_file.get_line_coords()
        if line_coords:
            line = [[float(num) for num in row] for row in line_coords]
            if line not in self.lines:
                self.lines.append(line_coords)
                x, y, z = [r[0] for r in line], \
                          [r[1] for r in line], \
                          [r[2] for r in line]
                line_artist, = self.ax.plot(x, y, z, '-o', lw=1,
                                            markersize=3, color='black', markerfacecolor='w', markeredgewidth=0.3)
                self.line_artists.append(line_artist)
                line_name = pem_file.header.get('LineHole')
                line_end = line[-1]
                line_label_artist = self.ax.text(line_end[0], line_end[1], line_end[2], line_name, ha='center',
                                                 va='bottom', path_effects=self.buffer, zorder=5)
                self.line_label_artists.append(line_label_artist)

                for station in line:
                    station_label_artist = self.ax.text(station[0], station[1], station[2], f"{station[-1]:.0f}",
                                                        fontsize=7, path_effects=self.buffer, ha='center', va='bottom',
                                                        color='dimgray')
                    self.station_label_artists.append(station_label_artist)

    def plot_hole(self, pem_file):
        logging.info('Map3D - Plotting borehole')

        collar_gps = pem_file.get_collar_coords()
        segments = pem_file.get_hole_geometry()
        if collar_gps and segments and segments not in self.geometries:
            self.geometries.append(segments)

            collar_gps = [[float(num) for num in row] for row in collar_gps]
            segments = [[float(num) for num in row] for row in segments]

            xx, yy, zz = self.get_3D_borehole_projection(collar_gps[0], segments)
            hole_artist, = self.ax.plot(xx, yy, zz, '--', lw=1, color='darkred')
            self.hole_artists.append(hole_artist)

            name = pem_file.header.get('LineHole')
            hole_label_artist = self.ax.text(collar_gps[0][0], collar_gps[0][1], collar_gps[0][2], str(name), zorder=5,
                                             path_effects=self.buffer, ha='center', va='bottom', color='darkred')
            self.hole_label_artists.append(hole_label_artist)

            for i, (x, y, z) in enumerate(list(zip(xx, yy, zz))[1:]):
                segment_label_artist = self.ax.text(x, y, z, f"{segments[i][-1]:.0f}", fontsize=7,
                                                    path_effects=self.buffer, ha='center', va='bottom', color='darkred')
                self.segment_label_artists.append(segment_label_artist)

    def format_ax(self):
        logging.info('Map3D - Formatting axes')

        def set_limits():
            min_x, max_x = self.ax.get_xlim()
            min_y, max_y = self.ax.get_ylim()
            min_z, max_z = self.ax.get_zlim()

            max_range = np.array([max_x - min_x, max_y - min_y, max_z - min_z]).max() / 2.0

            mid_x = (max_x + min_x) * 0.5
            mid_y = (max_y + min_y) * 0.5
            mid_z = (max_z + min_z) * 0.5
            self.ax.set_xlim(mid_x - max_range, mid_x + max_range)
            self.ax.set_ylim(mid_y - max_range, mid_y + max_range)
            if self.set_z:
                self.ax.set_zlim(mid_z - max_range, mid_z + max_range)

        set_limits()

        self.ax.set_xlabel('Easting')
        self.ax.set_ylabel('Northing')
        self.ax.set_zlabel('Elevation')

        self.ax.xaxis.set_major_formatter(ticker.StrMethodFormatter('{x:,.0f}'))
        self.ax.yaxis.set_major_formatter(ticker.StrMethodFormatter('{x:,.0f}'))
        self.ax.zaxis.set_major_formatter(ticker.StrMethodFormatter('{x:,.0f}'))


class MagneticFieldCalculator(MapPlotMethods):
    """
    Class that makes the magnetic field calculations for section vector plots.
    :param: pem_file: PEMFile object
    """

    def __init__(self, pem_file):
        logging.info('MagneticFieldCalculator')
        self.pem_file = pem_file
        MapPlotMethods.__init__(self)
        self.loop_coords = [[float(num) for num in row] for row in self.pem_file.get_loop_coords()]
        self.collar = [float(num) for num in self.pem_file.get_collar_coords()[0]]
        self.segments = [[float(num) for num in row] for row in self.pem_file.get_hole_geometry()]
        self.current = float(self.pem_file.tags.get('Current'))

    def get_magnitude(self, vector):
        return math.sqrt(sum(i ** 2 for i in vector))

    def calc_total_field(self, Px, Py, Pz, I):
        """
        Calculate the magnetic field at position P with current I using Biot-Savart Law. Geometry used is the loop.
        :param P: Position at which the magnetic field is calculated
        :param I: Current used
        :return: Magnetic field strength for each component
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

        u0 = 1.25663706e-6
        loop_array = np.array(self.loop_coords)
        loop_array = np.delete(loop_array, 3, 1)  # Delete the units column
        point = np.array([Px, Py, Pz])
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

        unit = 'nT' if 'induction' in self.pem_file.survey_type.lower() else 'pT'
        if unit == 'pT':
            field *= 1e12
        elif unit == 'nT':
            field *= 1e9
        else:
            raise NotImplemented('Invalid Units')

        return field[0], field[1], field[2]

    def project(self, normal_plane, vector):
        length = np.linalg.norm(normal_plane)
        calc = np.dot(normal_plane, vector) / length ** 2
        scaled = normal_plane * calc
        newvector = vector - scaled
        return newvector[0], newvector[1], newvector[2]

    def get_3d_magnetic_field(self, num_rows, buffer=0):
        logging.info('MagneticFieldCalculator - Creating mesh grid and creating vector field')
        # Create a mesh grid
        min_x, max_x, min_y, max_y, min_z, max_z = self.get_extents(self.pem_file)
        arrow_len = (max_z - min_z) // 16
        rows = float(num_rows)
        x = np.arange(min_x - buffer, max_x + buffer, (max_x - min_x) * 1 / rows)
        y = np.arange(min_y - buffer, max_y + buffer, (max_y - min_y) * 1 / rows)
        z = np.arange(min_z - buffer, max_z + buffer, (max_z - min_z) * 1 / rows)

        xx, yy, zz = np.meshgrid(x, y, z)

        # Vector function that will calculate the magnetic field for each point passed
        vField = np.vectorize(self.calc_total_field)

        print('Computing Field at {} points.....'.format(xx.size))
        start = timer()

        # Calculate the magnetic field at each mesh grid point
        u, v, w = vField(xx, yy, zz, self.current)

        end = timer()
        time = round(end - start, 2)
        print('Calculated in {} seconds'.format(str(time)))

        return xx, yy, zz, u, v, w, arrow_len

    def get_angle_2V(self, v1, v2):
        len1 = math.sqrt(sum(i ** 2 for i in v1))
        len2 = math.sqrt(sum(i ** 2 for i in v2))
        angle = math.acos(np.dot(v1, v2) / (len1 * len2))
        return angle

    def get_2d_magnetic_field(self, p1, p2, spacing=None, arrow_len=None, num_rows=12):

        def wrapper_proj(i, j, k, normal_plane):
            return self.project(normal_plane, [i, j, k])

        v_proj = np.vectorize(wrapper_proj, excluded=[3])
        v_field = np.vectorize(self.calc_total_field)

        # Vector to point and normal of cross section
        vec = [p2[0] - p1[0], p2[1] - p1[1], 0]
        planeNormal = np.cross(vec, [0, 0, -1])

        # Angle between the plane and j_hat
        theta = self.get_angle_2V(planeNormal, [0, 1, 0])

        # Fixes angles where p2.y is less than p1.y
        if p2[1] < p1[1]:
            theta = -theta

        # Creating the grid
        min_x, max_x, min_y, max_y, min_z, max_z = self.get_extents(self.pem_file)
        # Calculate the Z so that it is like a section plot
        min_z = max_z - ((float(math.floor(min_z / 400) + 1) * 400))
        line_len = round(math.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2))
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

        xx = xx_rot + p1[0]
        yy = yy_rot + p1[1]

        print('Computing Field at {} points.....'.format(xx.size))
        start = timer()

        # Calculate the magnetic field at each grid point
        u, v, w = v_field(xx, yy, zz, self.current)
        # Project the arrows
        uproj, vproj, wproj = v_proj(u, v, w, planeNormal)

        end = timer()
        time = round(end - start, 2)
        print('Calculated in {} seconds'.format(str(time)))

        return xx, yy, zz, uproj, vproj, wproj, arrow_len


class Section3D(Map3D, MagneticFieldCalculator):
    def __init__(self, ax, pem_file, **kwargs):
        logging.info('Section3D')
        if isinstance(pem_file, list):
            pem_file = pem_file[0]
        self.pem_file = pem_file
        self.ax = ax
        Map3D.__init__(self, self.ax, self.pem_file, set_z=False)
        MagneticFieldCalculator.__init__(self, self.pem_file)

        self.mag_field_artists = []
        self.buffer = [patheffects.Stroke(linewidth=2, foreground='white'), patheffects.Normal()]

        self.plot_hole(self.pem_file)
        self.plot_loop(self.pem_file)

    def plot_2d_magnetic_field(self):
        logging.info('Section3D - Plotting magnetic field')

        p1, p2, line_az = self.get_section_extents(self.pem_file)
        xx, yy, zz, u, v, w, arrow_len = self.get_2d_magnetic_field(p1, p2)
        mag_field_artist = self.ax.quiver(xx, yy, zz, u, v, w, length=arrow_len, normalize=True,
                                          color='black', label='Field', linewidth=.5, alpha=1.,
                                          arrow_length_ratio=.3, pivot='middle', zorder=0)
        self.mag_field_artists.append(mag_field_artist)

    # Not used
    # def plot_3d_magnetic_field(self, num_rows=8):
    #     logging.info('Section3D - Plotting magnetic field')
    #     xx, yy, zz, u, v, w, arrow_len = self.get_3d_magnetic_field(num_rows, buffer=10)
    #     # 3D Quiver
    #     mag_field_artist = self.ax.quiver(xx, yy, zz, u, v, w, length=arrow_len, normalize=True,
    #                   color='black', label='Field', linewidth=.5, alpha=1,
    #                   arrow_length_ratio=.3, pivot='middle', zorder=0)
    #     self.mag_field_artists.append(mag_field_artist)


class SectionPlot(MagneticFieldCalculator):
    """
    Plots the section plot (magnetic field vector plot) of a single borehole on a given figure object.
    By default the azimuth selected is the 80th percentile down the hole, but this is selected by the user.
    """

    def __init__(self, pem_files, fig, stations=None, hole_depth=None, **kwargs):
        self.color = 'black'
        self.fig = fig
        self.ax = self.fig.add_subplot()
        self.pem_file = pem_files[0]
        self.stations = stations
        try:
            self.hole_depth = int(hole_depth)
        except ValueError:
            self.hole_depth = None
        MagneticFieldCalculator.__init__(self, self.pem_file)
        self.buffer = [patheffects.Stroke(linewidth=3, foreground='white'), patheffects.Normal()]

        self.fig.subplots_adjust(left=0.055, bottom=0.03, right=0.97, top=0.955)
        bbox = self.ax.get_window_extent().transformed(self.fig.dpi_scale_trans.inverted())
        plot_width = bbox.width * .0254
        self.p1, self.p2, self.line_az = self.get_section_extents(self.pem_file, hole_depth=self.hole_depth,
                                                                  section_plot=True, plot_width=plot_width)
        self.line_len = math.sqrt((self.p1[0] - self.p2[0]) ** 2 + (self.p1[1] - self.p2[1]) ** 2)
        self.section_depth = self.line_len * (bbox.height / bbox.width)
        self.units = 'm' if self.segments[0][3] == 2 else 'ft'
        self.label_ticks = kwargs.get('LabelSectionTicks')

        self.plot_hole_section()
        self.plot_mag_section()
        self.format_figure()
        # plt.show()
        # filename = r'C:\Users\Eric\Desktop\Section.PDF'
        # plt.savefig(filename, dpi='figure', orientation='portrait')
        # os.startfile(filename)

    def get_hole_projection(self):
        """
        :returns list[X as Float, Y as Float, Azi as Float, SectionLength as Float, Z(Elevation) as Float]
        """

        trace_list = [self.collar[:2]]
        for counter, segment in enumerate(self.segments):
            azimuth = math.radians(float(segment[0]))
            dip = math.radians(float(segment[1]))
            delta_L = float(segment[2])
            delta_surf = delta_L * math.cos(dip)
            delta_elev = delta_L * math.sin(dip)

            dx = delta_surf * math.sin(azimuth)
            dy = delta_surf * math.cos(azimuth)

            trace_list.append(list(map(lambda x: round(x, 2), [trace_list[counter][0] + dx,
                                                               trace_list[counter][1] + dy])))

        return trace_list

    def format_figure(self):

        def calc_scale():
            (xmin, xmax) = self.ax.get_xlim()
            map_width = xmax - xmin
            bbox = self.ax.get_window_extent().transformed(self.fig.dpi_scale_trans.inverted())
            current_scale = map_width / (bbox.width * .0254)
            return current_scale

        def add_scale_bar():
            """
            Adds scale bar to the axes.
            Gets the width of the map in meters, find the best bar length number, and converts the bar length to
            equivalent axes percentage, then plots using axes transform so it is static on the axes.
            :return: None
            """

            def myround(x, base=5):
                return base * math.ceil(x / base)

            def add_rectangles(left_bar_pos, bar_center, right_bar_pos, y):
                """
                Draw the scale bar itself, using multiple rectangles.
                :param left_bar_pos: Axes position of the left-most part of the scale bar
                :param bar_center: Axes position center scale bar
                :param right_bar_pos: Axes position of the right-most part of the scale bar
                :param y: Axes height of the desired location of the scale bar
                :return: None
                """
                rect_height = 0.005
                line_width = 0.4
                sm_rect_width = (bar_center - left_bar_pos) / 5
                sm_rect_xs = np.arange(left_bar_pos, bar_center, sm_rect_width)
                big_rect_x = bar_center
                big_rect_width = right_bar_pos - bar_center

                # Adding the small rectangles
                for i, rect_x in enumerate(sm_rect_xs):  # Top set of small rectangles
                    fill = 'w' if i % 2 == 0 else 'k'
                    patch = patches.Rectangle((rect_x, y), sm_rect_width, rect_height, ec='k', linewidth=line_width,
                                              facecolor=fill, transform=self.ax.transAxes, zorder=9)
                    self.ax.add_patch(patch)
                for i, rect_x in enumerate(sm_rect_xs):  # Bottom set of small rectangles
                    fill = 'k' if i % 2 == 0 else 'w'
                    patch = patches.Rectangle((rect_x, y - rect_height), sm_rect_width, rect_height, ec='k', zorder=9,
                                              linewidth=line_width, facecolor=fill, transform=self.ax.transAxes)
                    self.ax.add_patch(patch)

                # Adding the big rectangles
                patch1 = patches.Rectangle((big_rect_x, y), big_rect_width, rect_height, ec='k', facecolor='k',
                                           linewidth=line_width, transform=self.ax.transAxes, zorder=9)
                patch2 = patches.Rectangle((big_rect_x, y - rect_height), big_rect_width, rect_height, ec='k',
                                           facecolor='w', linewidth=line_width, transform=self.ax.transAxes, zorder=9)
                # Background rectangle
                patch3 = patches.Rectangle((left_bar_pos, y - rect_height), big_rect_width * 2, rect_height * 2, ec='k',
                                           facecolor='w', linewidth=line_width, transform=self.ax.transAxes, zorder=5,
                                           path_effects=buffer)
                self.ax.add_patch(patch1)
                self.ax.add_patch(patch2)
                self.ax.add_patch(patch3)

            # bar_center = 0.85
            bar_center = 0.015 + (0.38 / 2)
            bar_height_pos = 0.25
            map_width = self.line_len
            num_digit = int(np.floor(np.log10(map_width)))  # number of digits in number
            bar_map_length = round(map_width, -num_digit)  # round to 1sf
            bar_map_length = myround(bar_map_length / 4, base=0.5 * 10 ** num_digit)  # Rounds to the nearest 1,2,5...
            units = 'meters' if self.units == 'm' else 'feet'

            buffer = [patheffects.Stroke(linewidth=5, foreground='white'), patheffects.Normal()]
            bar_ax_length = bar_map_length / map_width
            left_bar_pos = bar_center - (bar_ax_length / 2)
            right_bar_pos = bar_center + (bar_ax_length / 2)

            add_rectangles(left_bar_pos, bar_center, right_bar_pos, bar_height_pos)
            self.ax.text(left_bar_pos, bar_height_pos + .009, f"{bar_map_length / 2:.0f}", ha='center',
                         transform=self.ax.transAxes, path_effects=buffer, fontsize=7, zorder=9)
            self.ax.text(bar_center, bar_height_pos + .009, f"0", ha='center',
                         transform=self.ax.transAxes, path_effects=buffer, fontsize=7, zorder=9)
            self.ax.text(right_bar_pos, bar_height_pos + .009, f"{bar_map_length / 2:.0f}", ha='center',
                         transform=self.ax.transAxes, path_effects=buffer, fontsize=7, zorder=9)
            self.ax.text(bar_center, bar_height_pos - .018, f"({units})", ha='center',
                         transform=self.ax.transAxes, path_effects=buffer, fontsize=7, zorder=9)

        def add_title():

            def get_survey_date():
                survey_date = self.pem_file.header.get('Date')
                date_obj = datetime.strptime(survey_date, '%B %d, %Y')
                max_date_text = datetime.strftime(date_obj, '%B %d, %Y')
                survey_date_text = f"Survey Date: {max_date_text}"
                return survey_date_text

            b_xmin = 0.015  # Title box
            b_width = 0.38
            b_ymin = 0.015
            b_height = 0.165

            center_pos = b_xmin + (b_width / 2)
            right_pos = b_xmin + b_width - .01
            left_pos = b_xmin + .01
            top_pos = b_ymin + b_height - 0.013

            # Separating lines
            line_1 = mlines.Line2D([b_xmin, b_xmin + b_width], [top_pos - .045, top_pos - .045],
                                   linewidth=1, color='gray', transform=self.ax.transAxes, zorder=10)

            line_2 = mlines.Line2D([b_xmin, b_xmin + b_width], [top_pos - .098, top_pos - .098],
                                   linewidth=1, color='gray', transform=self.ax.transAxes, zorder=10)

            line_3 = mlines.Line2D([b_xmin, b_xmin + b_width], [top_pos - .135, top_pos - .135],
                                   linewidth=.5, color='gray', transform=self.ax.transAxes, zorder=10)

            # Title box rectangle
            rect = patches.FancyBboxPatch(xy=(b_xmin, b_ymin), width=b_width, height=b_height, edgecolor='k',
                                          boxstyle="round,pad=0.005", facecolor='white', zorder=9,
                                          transform=self.ax.transAxes)

            client = self.pem_file.header.get("Client")
            grid = self.pem_file.header.get("Grid")
            loop = self.pem_file.header.get('Loop')
            hole = self.pem_file.header.get('LineHole')

            scale = f"1:{calc_scale():,.0f}"

            self.ax.text(center_pos, top_pos, 'Crone Geophysics & Exploration Ltd.',
                         fontname='Century Gothic', fontsize=11, ha='center', zorder=10, transform=self.ax.transAxes)

            self.ax.text(center_pos, top_pos - 0.02, f"Hole Cross-Section with Primary Field", family='cursive',
                         fontname='Century Gothic', fontsize=10, ha='center', zorder=10, transform=self.ax.transAxes)

            self.ax.text(center_pos, top_pos - 0.037, f"{self.pem_file.survey_type.title()} Pulse EM Survey",
                         family='cursive',
                         style='italic',
                         fontname='Century Gothic', fontsize=9, ha='center', zorder=10, transform=self.ax.transAxes)

            self.ax.text(center_pos, top_pos - 0.051, f"{client}\n" + f"{grid}\n"
            f"Hole: {hole}    Loop: {loop}",
                         fontname='Century Gothic', fontsize=10, va='top', ha='center', zorder=10,
                         transform=self.ax.transAxes)

            self.ax.text(center_pos, top_pos - 0.105,
                         f"Timebase: {self.pem_file.header.get('Timebase')} ms\n{get_survey_date()}",
                         fontname='Century Gothic', fontsize=9, va='top', ha='center', zorder=10,
                         transform=self.ax.transAxes)

            self.ax.text(left_pos, top_pos - 0.140, f"Section Azimuth: {self.line_az:.0f}°", family='cursive',
                         style='italic', color='dimgray',
                         fontname='Century Gothic', fontsize=8, va='top', ha='left', zorder=10,
                         transform=self.ax.transAxes)

            self.ax.text(right_pos, top_pos - 0.140, f"Scale {scale}", family='cursive', style='italic',
                         color='dimgray',
                         fontname='Century Gothic', fontsize=8, va='top', ha='right', zorder=10,
                         transform=self.ax.transAxes)

            self.ax.add_patch(rect)
            shadow = patches.Shadow(rect, 0.002, -0.002)
            self.ax.add_patch(shadow)
            self.ax.add_line(line_1)
            self.ax.add_line(line_2)
            self.ax.add_line(line_3)

        self.ax.xaxis.set_visible(False)
        self.ax.yaxis.set_visible(True)
        self.ax.set_yticklabels(self.ax.get_yticklabels(), rotation=90, va='center')

        if self.units == 'm':
            self.ax.yaxis.set_major_formatter(ticker.StrMethodFormatter('{x:,.0f} m'))
        else:
            self.ax.yaxis.set_major_formatter(ticker.StrMethodFormatter('{x:,.0f} ft'))

        add_title()
        add_scale_bar()

    def plot_mag_section(self):
        """
        Plots the vector field cross section. The end-points of the section are automatically calculated.
        :param plt_ax: matplotlib.figure.ax
            Constraints: must be 2D
        :return: None
        """

        def wrapper_proj(i, j, k, normal_plane):
            return self.project(normal_plane, [i, j, k])

        vProj = np.vectorize(wrapper_proj, excluded=[3])
        vField = np.vectorize(self.calc_total_field)

        current = float(self.pem_file.tags.get('Current'))
        vec = [self.p2[0] - self.p1[0],
               self.p2[1] - self.p1[1],
               0]
        planeNormal = np.cross(vec, [0, 0, -1])

        # Angle between the plane and j_hat
        theta = self.get_angle_2V(planeNormal, [0, 1, 0])

        # Fixes angles where p2.y is less than p1.y
        if self.p2[1] < self.p1[1]:
            theta = -theta

        hole_elevation = self.collar[2]
        min_z = hole_elevation - self.section_depth

        try:
            length = np.arange(0, self.line_len + 30, self.line_len // 25)
            y = np.zeros(1)
            z = np.arange(min_z, hole_elevation + 50, (hole_elevation - min_z) // 30)
        except ZeroDivisionError:
            print('SectionLength ZeroDivisionError, expected > 0')
            return
        except:
            raise
        xx, yy, zz = np.meshgrid(length, y, z)
        x_rot = xx * math.cos(theta) - yy * math.sin(theta)
        y_rot = xx * math.sin(theta) + yy * math.cos(theta)

        xx = x_rot + self.p1[0]
        yy = y_rot + self.p1[1]

        print('Computing Field at {} points.....'.format(xx.size))
        start = timer()

        u, v, w = vField(xx, yy, zz, current)  # Calculate the field
        uproj, vproj, wproj = vProj(u, v, w, planeNormal)  # Project it to the plane
        mag = np.sqrt(u * u + v * v + w * w)  # Magnitude for colormap
        uprot = np.cos(theta) * uproj + np.sin(theta) * vproj  # Rotate the vectors back to the X-Z Plane

        uprot2d = np.squeeze(uprot).T  # Get rid of the extra dimension, transpose to fudge the arrangement
        wproj2d = np.squeeze(wproj).T
        magsqueeze = np.squeeze(mag).T

        plotx = uprot2d / np.sqrt(uprot2d ** 2 + wproj2d ** 2) * 0.7  # Normalize vector lengths
        plotz = wproj2d / np.sqrt(uprot2d ** 2 + wproj2d ** 2) * 0.7

        xx, zz = np.meshgrid(length, z)
        end = timer()
        time = round(end - start, 2)
        print('Calculated in {} seconds'.format(str(time)))
        self.ax.set_xlim(0, self.line_len)
        self.ax.set_ylim(min_z, hole_elevation)

        # Plot the vector arrows
        self.ax.quiver(xx, zz, plotx, plotz, color='dimgray', label='Field', pivot='middle', zorder=0,
                       units='dots', scale=.045, width=.6, headlength=9, headwidth=5)

        # Plot Labelling
        lefttext = f'{self.p1[0]:,.0f}m E\n{self.p1[1]:,.0f}m N'
        righttext = f'{self.p2[0]:,.0f}m E\n{self.p2[1]:,.0f}m N'
        self.ax.text(0, 1.01, lefttext, color='k', ha='left', size='small', path_effects=self.buffer,
                     zorder=9, transform=self.ax.transAxes)
        self.ax.text(1, 1.01, righttext, color='k', ha='right', size='small',
                     path_effects=self.buffer, zorder=9, transform=self.ax.transAxes)
        # plt.draw()
        # plt.pause(0.0001)

    def plot_hole_section(self):
        p = np.array([self.p1[0], self.p1[1], 0])
        vec = [self.p2[0] - self.p1[0], self.p2[1] - self.p1[1], 0]
        planeNormal = np.cross(vec, [0, 0, -1])
        planeNormal = planeNormal / self.get_magnitude(planeNormal)

        interp_x, interp_y, interp_z = np.array(self.get_3D_borehole_projection(
            self.collar, self.segments, interp_segments=1000), dtype='float64')

        # Plotting station ticks on the projected hole
        if self.stations is None:
            self.stations = self.pem_file.get_converted_unique_stations()

        # Marker indexes are the station depth as a percentage of the max station depth
        station_indexes = [int(station / self.segments[-1][-1] * 1000) for station in self.stations]

        plotx = []
        plotz = []

        hole_trace = list(zip(interp_x, interp_y, interp_z))

        # Projecting the 3D trace to a 2D plane
        for i, coordinate in enumerate(hole_trace):
            q = np.array(coordinate)
            q_proj = q - np.dot(q - p, planeNormal) * planeNormal
            distvec = np.array([q_proj[0] - p[0], q_proj[1] - p[1]])
            dist = np.sqrt(distvec.dot(distvec))

            plotx.append(dist)
            plotz.append(q_proj[2])

            if i == 0:
                # Circle at top of hole
                self.ax.plot([dist], [q_proj[2]], 'o', markerfacecolor='w', markeredgecolor='k',
                             path_effects=self.buffer, zorder=11)
                # Hole name label
                hole_name = self.pem_file.header.get('LineHole')
                trans = mtransforms.blended_transform_factory(self.ax.transData, self.ax.transAxes)
                self.ax.text(dist, 1.01, hole_name, color='k', ha='center', size=10, transform=trans, zorder=10)
            elif i == len(hole_trace) - 1:
                # Label end-of-hole depth
                hole_len = self.segments[-1][-1]
                angle = math.degrees(math.atan2(plotz[-1]-plotz[-100], plotx[-1]-plotx[-100])) + 90
                self.ax.text(dist + self.line_len * .01, q_proj[2], f"{hole_len:.0f} m", color='k', ha='left',
                             rotation=angle, path_effects=self.buffer, zorder=10, rotation_mode='anchor')

        # Plot the hole section line
        self.ax.plot(plotx, plotz, color='k', lw=1, path_effects=self.buffer, zorder=10)

        # Plotting the ticks
        for i, (x, z) in enumerate(zip(plotx, plotz)):
            if i in station_indexes:
                p = (x, z)
                index = list(plotx).index(x)
                pa = (plotx[index - 1], plotz[index - 1])
                angle = math.degrees(math.atan2(pa[1] - p[1], pa[0] - p[0])) - 90

                self.ax.text(x, z, '|', rotation=angle+90, ha='center', va='center', zorder=12, rotation_mode='anchor')

                # Label the station ticks
                if self.label_ticks:
                    self.ax.text(x, z, f"{self.stations[station_indexes.index(i)]} {self.units}", rotation=angle,
                             color='dimgray', size=8)

        # # Markers are plotted separately so they don't have a buffer around them like the line does
        # self.ax.plot(plotx, plotz, 'o', color='k', lw=1, zorder=11,
        #              markevery=station_indexes, markersize=4, markerfacecolor='w')

    def get_section_plot(self):
        return self.fig


class PEMPrinter:
    """
    Class for printing PEMPLotter plots to PDF.
    Creates a single portrait and a single landscape figure object and re-uses them for all plots.
    :param pem_files: List of PEMFile objects
    :param save_path: Desired save location for the PDFs
    :param kwargs: Plotting kwargs such as hide_gaps, gaps, and x limits used in PEMPlotter.
    """

    def __init__(self, save_path, files, **kwargs):
        self.files = files  # Zipped PEM and RI files
        self.kwargs = kwargs
        self.save_path = save_path
        self.share_range = kwargs.get('ShareRange')
        self.x_min = kwargs.get('XMin')
        self.x_max = kwargs.get('XMax')
        self.hide_gaps = kwargs.get('HideGaps')
        self.print_plan_maps = kwargs.get('PlanMap')
        self.print_section_plot = kwargs.get('SectionPlot')
        self.print_lin_plots = kwargs.get('LINPlots')
        self.print_log_plots = kwargs.get('LOGPlots')
        self.print_step_plots = kwargs.get('STEPPlots')
        self.crs = kwargs.get('CRS')

        self.pb = CustomProgressBar()
        self.pb_count = 0
        self.pb_end = 0
        self.pb.setValue(0)

        self.portrait_fig = plt.figure(figsize=(8.5, 11), num=1, clear=True)
        self.landscape_fig = plt.figure(figsize=(11, 8.5), num=2, clear=True)

    def print_files(self):

        def atoi(text):
            return int(text) if text.isdigit() else text

        def natural_keys(text):
            """
            alist.sort(key=natural_keys) sorts in human order
            http://nedbatchelder.com/blog/200712/human_sorting.html
            """
            return [atoi(c) for c in re.split(r'(\d+)', text)]

        def save_plots(pem_files, ri_files, x_min, x_max):
                # Saving the Plan Map. Must have a CRS.
                if all([self.crs.get('Coordinate System'), self.crs.get('Datum')]) and self.print_plan_maps is True:
                    if any([pem_file.has_any_gps() for pem_file in pem_files]):
                        self.pb.setText(f"Saving plan map for {', '.join([pem_file.header.get('LineHole') for pem_file in pem_files])}")
                        plan_map = PlanMap(pem_files, self.landscape_fig, **self.kwargs)
                        pdf.savefig(plan_map.get_map(), orientation='landscape')
                        self.pb_count += 1
                        self.pb.setValue(self.pb_count)
                        self.landscape_fig.clf()
                    else:
                        print('No PEM file has any GPS to plot on the plan map.')

                # Save the Section plot as long as it is a borehole survey. Must have loop, collar GPS and segments.
                if self.print_section_plot is True and 'borehole' in pem_files[0].survey_type.lower():
                    if pem_files[0].has_collar_gps() and pem_files[0].has_loop_gps() and pem_files[0].has_geometry():
                        self.pb.setText(f"Saving section plot for {pem_files[0].header.get('LineHole')}")
                        section_depth = self.kwargs.get('SectionDepth')
                        stations = sorted(set(itertools.chain.from_iterable(
                            [pem_file.get_converted_unique_stations() for pem_file in pem_files])))

                        section_plotter = SectionPlot(pem_files, self.portrait_fig, stations=stations,
                                                      hole_depth=section_depth, **self.kwargs)
                        section_fig = section_plotter.get_section_plot()
                        pdf.savefig(section_fig)
                        self.pb_count += 1
                        self.pb.setValue(self.pb_count)
                        self.portrait_fig.clear()
                    else:
                        print('No PEM file has the GPS required to make a section plot.')

                # Saving the LIN plots
                if self.print_lin_plots is True:
                    for pem_file in pem_files:
                        components = pem_file.get_components()
                        for component in components:
                            self.configure_lin_fig()
                            lin_plotter = LINPlotter()
                            self.pb.setText(
                                f"Saving LIN plot for {pem_file.header.get('LineHole')}, component {component}")

                            plotted_fig = lin_plotter.plot(pem_file, component, self.portrait_fig, x_min=x_min,
                                                           x_max=x_max, hide_gaps=self.hide_gaps)
                            pdf.savefig(plotted_fig)
                            self.pb_count += 1
                            self.pb.setValue(self.pb_count)
                            self.portrait_fig.clear()

                # Saving the LOG plots
                if self.print_log_plots is True:
                    for pem_file in pem_files:
                        components = pem_file.get_components()
                        for component in components:
                            self.configure_log_fig()
                            log_plotter = LOGPlotter()
                            self.pb.setText(
                                f"Saving LOG plot for {pem_file.header.get('LineHole')}, component {component}")

                            plotted_fig = log_plotter.plot(pem_file, component, self.portrait_fig, x_min=x_min,
                                                           x_max=x_max, hide_gaps=self.hide_gaps)
                            pdf.savefig(plotted_fig)
                            self.pb_count += 1
                            self.pb.setValue(self.pb_count)
                            self.portrait_fig.clear()

                # Saving the STEP plots. Must have RI files associated with the PEM file.
                if self.print_step_plots is True:
                    for pem_file, ri_file in zip(pem_files, ri_files):
                        if ri_file:
                            components = pem_file.get_components()
                            for component in components:
                                self.pb.setText(
                                    f"Saving STEP plot for {pem_file.header.get('LineHole')}, component {component}")
                                self.configure_step_fig()
                                step_plotter = STEPPlotter()
                                plotted_fig = step_plotter.plot(pem_file, ri_file, component, self.portrait_fig,
                                                                x_min=x_min, x_max=x_max, hide_gaps=self.hide_gaps)
                                pdf.savefig(plotted_fig)
                                self.pb_count += 1
                                self.pb.setValue(self.pb_count)
                                self.portrait_fig.clear()

        def set_pb_max(unique_bhs, unique_grids):
            """
            Calculate the progress bar maximum value. I.E. calculates how many PDF pages will be made.
            :param unique_bhs: Dict of unique borehole surveys (different hole name and loop name)
            :param unique_grids: Dict of unique surface grids (different loop names)
            :return: Sets the maximum value of self.pb.
            """
            total_count = 0

            if unique_bhs:
                for survey, files in unique_bhs.items():
                    num_plots = sum([len(file[0].get_components()) for file in files])
                    if self.print_plan_maps:
                        if any([file[0].has_any_gps() for file in files]):
                            total_count += 1
                    if self.print_section_plot:
                        if any([file[0].has_collar_gps() and file[0].has_geometry() and file[0].has_loop_gps() for file in files]):
                            total_count += 1
                    if self.print_lin_plots:
                        total_count += num_plots
                    if self.print_log_plots:
                        total_count += num_plots
                    if self.print_step_plots:
                        if all([file[1] for file in files]):
                            total_count += num_plots

            if unique_grids:
                for loop, lines in unique_grids.items():
                    num_plots = sum([len(file[0].get_components()) for file in lines])
                    if self.print_plan_maps:
                        if any([file[0].has_any_gps() for file in lines]):
                            total_count += 1
                    if self.print_lin_plots:
                        total_count += num_plots
                    if self.print_log_plots:
                        total_count += num_plots
                    if self.print_step_plots:
                        if all([file[1] for file in lines]):
                            total_count += num_plots

            self.pb_end = total_count
            print(f"Number of PDF pages: {total_count}")
            self.pb.setMaximum(total_count)

        unique_bhs = defaultdict()
        unique_grids = defaultdict()

        bh_files = list(filter(lambda x: 'borehole' in x[0].survey_type.lower(), self.files))
        sf_files = list(filter(lambda x: 'surface' in x[0].survey_type.lower(), self.files))

        if any(bh_files):
            bh_files.sort(key=lambda x: x[0].get_components(), reverse=True)
            bh_files.sort(key=lambda x: natural_keys(x[0].header['Loop']))
            bh_files.sort(key=lambda x: natural_keys(x[0].header['LineHole']))

        if any(sf_files):
            sf_files.sort(key=lambda x: x[0].get_components(), reverse=True)
            sf_files.sort(key=lambda x: natural_keys(x[0].header['LineHole']))
            sf_files.sort(key=lambda x: natural_keys(x[0].header['Loop']))

        # Group the files by unique surveys i.e. each entry is the same borehole and same loop
        for survey, files in itertools.groupby(bh_files, key=lambda x: (
                x[0].header.get('LineHole'), x[0].header.get('Loop'))):
            unique_bhs[survey] = list(files)
            print(survey, list(files))

        # Group the files by unique surveys i.e. each entry is the same borehole and same loop
        for loop, files in itertools.groupby(sf_files, key=lambda x: x[0].header.get('Loop')):
            unique_grids[loop] = list(files)
            print(loop, list(files))

        set_pb_max(unique_bhs, unique_grids)  # Set the maximum for the progress bar

        with PdfPages(self.save_path + '.PDF') as pdf:
            for survey, files in unique_bhs.items():
                 pem_files = [pair[0] for pair in files]
                 ri_files = [pair[1] for pair in files]
                 if self.x_min is None and self.share_range is True:
                     x_min = min(itertools.chain.from_iterable([pem_file.get_converted_unique_stations() for
                                                                pem_file in pem_files]))
                 else:
                     x_min = self.x_min
                 if self.x_max is None and self.share_range is True:
                     x_max = max(itertools.chain.from_iterable([pem_file.get_converted_unique_stations() for
                                                                pem_file in pem_files]))
                 else:
                     x_max = self.x_max
                 save_plots(pem_files, ri_files, x_min, x_max)
                 self.pb.setText('Complete')

            for loop, files in unique_grids.items():
                pem_files = [pair[0] for pair in files]
                ri_files = [pair[1] for pair in files]
                if self.x_min is None and self.share_range is True:
                    x_min = min(itertools.chain.from_iterable([pem_file.get_converted_unique_stations() for
                                                               pem_file in pem_files]))
                else:
                    x_min = self.x_min
                if self.x_max is None and self.share_range is True:
                    x_max = max(itertools.chain.from_iterable([pem_file.get_converted_unique_stations() for
                                                               pem_file in pem_files]))
                else:
                    x_max = self.x_max
                save_plots(pem_files, ri_files, x_min, x_max)

        plt.close(self.portrait_fig)
        plt.close(self.landscape_fig)
        os.startfile(self.save_path + '.PDF')

    def configure_lin_fig(self):
        """
        Add the subplots for a lin plot
        """
        self.portrait_fig, (ax1, ax2, ax3, ax4, ax5) = plt.subplots(5, 1, num=1, sharex=True, clear=True)
        ax6 = ax5.twiny()
        ax6.get_shared_x_axes().join(ax5, ax6)

    def configure_log_fig(self):
        """
        Configure the lob plot axes
        """
        self.portrait_fig, ax = plt.subplots(1, 1, num=1, clear=True)
        ax2 = ax.twiny()
        ax2.get_shared_x_axes().join(ax, ax2)
        plt.yscale('symlog', linthreshy=10, linscaley=1. / math.log(10), subsy=list(np.arange(2, 10, 1)))

    def configure_step_fig(self):
        """
        Configure the step plot figure
        """
        self.portrait_fig, (ax1, ax2, ax3, ax4) = plt.subplots(4, 1, num=1, sharex=True, clear=True)
        ax5 = ax4.twiny()
        ax5.get_shared_x_axes().join(ax4, ax5)


class CustomProgressBar(QProgressBar):

    def __init__(self):
        super().__init__()
        self.setMinimum(0)
        self.setAlignment(QtCore.Qt.AlignCenter)
        self._text = None

        COMPLETED_STYLE = """
        QProgressBar {
            border: 2px solid grey;
            border-radius: 5px;
            text-align: center;
        }

        QProgressBar::chunk {
            background-color: #88B0EB;
            width: 20px;
        }
        """
        # '#37DA7E' for green
        self.setStyleSheet(COMPLETED_STYLE)

    def setText(self, text):
        self._text = text

    def text(self):
        return self._text


if __name__ == '__main__':
    from src.pem.pem_getter import PEMGetter

    pem_getter = PEMGetter()
    pem_files = pem_getter.get_pems()
    # for pem_file in pem_files:
    #     pem_file.has_collar_gps()
    # pem_files = list(filter(lambda x: 'borehole' in x.survey_type.lower(), pem_files))
    fig = plt.figure(figsize=(8.5, 11), dpi=100)
    # plan_map = PlanMap(pem_files, fig)
    # ax = fig.add_subplot()
    section = SectionPlot(pem_files, fig)
    plt.show()
    # printer = PEMPrinter(sample_files_dir, pem_files)
    # printer.print_final_plots()
