import copy
import logging
import math
import os
import re
import sys
from datetime import datetime

import cartopy.crs as ccrs  # import projections
import matplotlib
import matplotlib as mpl
import matplotlib.backends.backend_tkagg  # Needed for pyinstaller, or receive  ImportError
import matplotlib.lines as mlines
import matplotlib.offsetbox
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import matplotlib.text as mtext
import matplotlib.transforms as mtransforms
from matplotlib.text import OffsetFrom
import numpy as np
from PyQt5.QtWidgets import (QProgressBar)
from matplotlib import patches
from matplotlib import patheffects
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.lines import Line2D
from scipy import interpolate
from scipy import stats

from src.gps.gps_editor import GPSEditor
from src.pem.pem_parser import PEMParser

__version__ = '0.0.1'
logging.info('PEMPlotter')

if getattr(sys, 'frozen', False):
    # If the application is run as a bundle, the pyInstaller bootloader
    # extends the sys module by a flag frozen=True and sets the app
    # path into variable _MEIPASS'.
    application_path = sys._MEIPASS
else:
    application_path = os.path.dirname(os.path.abspath(__file__))

mpl.rcParams['path.simplify'] = True
mpl.rcParams['path.simplify_threshold'] = 1.0
mpl.rcParams['agg.path.chunksize'] = 10000
mpl.rcParams["figure.autolayout"] = False
mpl.rcParams['lines.linewidth'] = 0.5
# mpl.rcParams['lines.color'] = '#1B2631'
mpl.rcParams['font.size'] = 9

line_color = 'black'


def add_rectangle(figure):
    """
    Draws a rectangle around a figure object
    """
    rect = patches.Rectangle(xy=(0.02, 0.02), width=0.96, height=0.96, linewidth=0.7, edgecolor='black',
                             facecolor='none', transform=figure.transFigure)
    figure.patches.append(rect)


def format_figure(figure, step=False):
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

    plt.subplots_adjust(left=0.135 if step is False else 0.170, bottom=0.07, right=0.958, top=0.885)
    add_rectangle(figure)

    for ax in axes:
        format_spines(ax)


def format_xaxis(pem_file, figure, x_min, x_max):
    """
    Formats the X axis of a figure
    :param figure: LIN or LOG figure objects
    """
    stations = [convert_station(station) for station in pem_file.get_unique_stations()]
    if x_min is None:
        x_min = min(stations)
    if x_max is None:
        x_max = max(stations)
    x_label_locator = ticker.AutoLocator()
    major_locator = ticker.FixedLocator(sorted(stations))
    plt.xlim(x_min, x_max)
    figure.axes[0].xaxis.set_major_locator(major_locator)  # for some reason this seems to apply to all axes
    figure.axes[-1].xaxis.set_major_locator(x_label_locator)


def convert_station(station):
    """
    Converts a single station name into a number, negative if the stations was S or W
    :return: Integer station number
    """
    if re.match(r"\d+(S|W)", station):
        station = (-int(re.sub(r"\D", "", station)))

    else:
        station = (int(re.sub(r"\D", "", station)))

    return station


def get_profile_data(pem_file, component):
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
            station_number = int(convert_station(station['Station']))
            channel_data.append({'Station': station_number, 'Reading': reading})

        profile_data[channel] = channel_data

    return profile_data


def get_channel_data(channel, profile_data):
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


def get_interp_data(profile_data, stations, survey_type, hide_gaps=True, gap=None, segments=1000,
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
    f = interpolate.interp1d(stations, readings, kind=interp_method)

    interpolated_y = f(x_intervals)

    if hide_gaps:
        gap_intervals = calc_gaps(stations, gap)

        # Masks the intervals that are between gap[0] and gap[1]
        for gap in gap_intervals:
            interpolated_y = np.ma.masked_where((x_intervals > gap[0]) & (x_intervals < gap[1]),
                                                interpolated_y)

    return interpolated_y, x_intervals


def draw_lines(pem_file, component, ax, channel_low, channel_high, hide_gaps=True):
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
    profile_channel_data = get_profile_data(pem_file, component)

    for k in range(channel_low, (channel_high + 1)):
        # Gets the profile data for a single channel, along with the stations
        channel_data, stations = get_channel_data(k, profile_channel_data)

        # Interpolates the channel data, also returns the corresponding x intervals
        interp_data, x_intervals = get_interp_data(channel_data, stations, pem_file.survey_type,
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


def format_yaxis(pem_file, figure, step=False):
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

        elif ax.get_yscale() == 'symlog':
            y_limits = ax.get_ylim()
            new_high = 10.0 ** math.ceil(math.log(max(y_limits[1], 11), 10))
            new_low = -1 * 10.0 ** math.ceil(math.log(max(abs(y_limits[0]), 11), 10))
            ax.set_ylim(new_low, new_high)

            ax.tick_params(axis='y', which='major', labelrotation=90)
            plt.setp(ax.get_yticklabels(), va='center')

        ax.yaxis.set_major_formatter(ticker.FormatStrFormatter('%d'))  # Prevent scientific notation


def add_title(pem_file, component, step=False):
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

    plt.figtext(0.550, 0.935, f"{s_title} : {header.get('LineHole')}\n" +
                f"Loop: {header.get('Loop')}\n" +
                f"{component} Component",
                fontname='Century Gothic', fontsize=10, va='top', ha='center')

    plt.figtext(0.955, 0.935, f"{header.get('Client')}\n" +
                f"{header.get('Grid')}\n" +
                f"{header['Date']}\n",
                fontname='Century Gothic', fontsize=10, va='top', ha='right')


class LINPlotter:
    """
     Plots the data into the LIN figure
     :return: Matplotlib Figure object
     """

    def plot(self, pem_file, component, figure, x_min=None, x_max=None, hide_gaps=True):

        def add_ylabels():
            units = 'nT/s' if 'induction' in pem_file.survey_type.lower() else 'pT'
            for i in range(len(figure.axes) - 1):
                ax = figure.axes[i]
                if i == 0:
                    ax.set_ylabel(f"Primary Pulse\n({units}")
                else:
                    ax.set_ylabel(f"Channel {str(channel_bounds[i][0])} - {str(channel_bounds[i][1])}\n({units})")

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
            draw_lines(pem_file, component, ax, group[0], group[1], hide_gaps=hide_gaps)

        add_title(pem_file, component)
        add_ylabels()
        format_figure(figure)
        format_yaxis(pem_file, figure, step=False)
        format_xaxis(pem_file, figure, x_min, x_max)
        return figure


class LOGPlotter:
    """
     Plots the data into the LOG figure
     :return: Matplotlib Figure object
     """

    def plot(self, pem_file, component, figure, x_min=None, x_max=None, hide_gaps=True):
        def add_ylabels():
            units = 'nT/s' if 'induction' in pem_file.survey_type.lower() else 'pT'
            ax = figure.axes[0]
            ax.set_ylabel(f"Primary Pulse to Channel {str(num_channels - 1)}\n({units})")

        num_channels = int(pem_file.header['NumChannels']) + 1

        # Plotting section
        ax = figure.axes[0]
        draw_lines(pem_file, component, ax, 0, num_channels - 1, hide_gaps=hide_gaps)

        add_title(pem_file, component)
        add_ylabels()
        format_figure(figure)
        format_yaxis(pem_file, figure, step=False)
        format_xaxis(pem_file, figure, x_min, x_max)
        return figure


class STEPPlotter:
    """
     Plots the data from an RI file into the STEP figure
     :return: Matplotlib Figure object
     """

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
                interp_data, x_intervals = get_interp_data(profile_data[key], stations, survey_type,
                                                           hide_gaps=hide_gaps)
                mask = np.isclose(interp_data, interp_data.astype('float64'))
                x_intervals = x_intervals[mask]
                interp_data = interp_data[mask]

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
                interp_data, x_intervals = get_interp_data(channel, stations, survey_type, hide_gaps=hide_gaps)
                mask = np.isclose(interp_data, interp_data.astype('float64'))
                x_intervals = x_intervals[mask]
                interp_data = interp_data[mask]
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
                        profile_data[key] = [convert_station(station['Station']) for station in component_data]
                    else:
                        profile_data[key] = [float(station[key]) for station in component_data]
            return profile_data

        survey_type = pem_file.survey_type
        profile_data = get_profile_step_data(component)
        off_time_channel_data = [profile_data[key] for key in profile_data if re.match('Ch', key)]
        num_off_time_channels = len(off_time_channel_data) + 10
        num_channels_to_plot = round(num_off_time_channels / 4)

        draw_step_lines(figure, profile_data, hide_gaps=hide_gaps)

        add_title(pem_file, component, step=True)
        add_ylabel(profile_data, num_channels_to_plot)
        format_figure(figure, step=True)
        format_yaxis(pem_file, figure, step=True)
        format_xaxis(pem_file, figure, x_min, x_max)
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
        if not pa:
            self.pa = label_xy
        self.calc_angle_data()
        kwargs.update(rotation_mode=kwargs.get("rotation_mode", "anchor"), xytext=(0, 0), textcoords='offset points')
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
        else:
            if deg > 90 or deg < -90:
                deg = deg - 180
        self.angle_data = deg

    def calc_xy_offset(self):

        pass

    def _get_rotation(self):
        return self.ax.transData.transform_angles(np.array((self.angle_data,)),
                                                  np.array([self.pa[0], self.pa[1]]).reshape((1, 2)))[0]

    def _set_rotation(self, rotation):
        pass

    _rotation = property(_get_rotation, _set_rotation)


class PlanMap:
    def __init__(self, pem_files, figure, projection, draw_loops=True, draw_lines=True, draw_hole_collar=True,
                 draw_hole_trace=True):
        self.color = 'black'
        self.fig = figure
        if not isinstance(pem_files, list):
            pem_files = [pem_files]
        self.pem_files = pem_files
        self.loops = []
        self.lines = []
        self.collars = []
        self.holes = []
        self.loop_handle = None
        self.station_handle = None
        self.collar_handle = None
        self.trace_handle = None
        self.map_scale = None
        self.draw_loops = draw_loops
        self.draw_lines = draw_lines
        self.draw_hole_collar = draw_hole_collar
        self.draw_hole_trace = draw_hole_trace
        self.gps_editor = GPSEditor
        self.crs = projection
        self.ax = self.fig.add_subplot(projection=self.crs)
        # self.inset_ax = self.fig.add_axes([0.1, 0.5, 0.5, 0.3], projection=self.crs)

        self.plot_pems()
        self.format_figure()
        plt.show()

    # def get_rotation(self, xs, ys):
    #     """
    #     Get the real axes rotation value between two points
    #     :param xs: list of X coordinates of the two points
    #     :param ys: list of Y coordinates of the two points
    #     :return: Rotation value that aligns properly between p1 and p2
    #     """
    #     p1 = self.ax.transData.transform_point((xs[0], ys[0]))
    #     p2 = self.ax.transData.transform_point((xs[1], ys[1]))
    #     dy = (p2[1] - p1[1])
    #     dx = (p2[0] - p1[0])
    #     rotn = np.degrees(np.arctan2(dy, dx))
    #     if rotn > 90 or rotn < -90:
    #         return rotn - 180
    #     else:
    #         return rotn

    def plot_pems(self):

        def add_loop_to_map(pem_file):
            loop_gps = pem_file.get_loop_coords()
            if loop_gps and loop_gps not in self.loops:
                self.loops.append(loop_gps)
                loop_center = self.gps_editor().get_loop_center(copy.copy(loop_gps))
                eastings, northings = [float(coord[0]) for coord in loop_gps], [float(coord[1]) for coord in loop_gps]
                eastings.insert(0, eastings[-1])  # To close up the loop
                northings.insert(0, northings[-1])

                self.ax.text(loop_center[0], loop_center[1], f"Tx Loop {pem_file.header.get('Loop')}", ha='center',
                             color=self.color, zorder=3)  # Add the loop name
                self.loop_handle, = self.ax.plot(eastings, northings, color=self.color, label='Transmitter Loop',
                                                 transform=self.crs, zorder=2)  # Plot the loop

        def add_line_to_map(pem_file):
            line_gps = pem_file.get_station_coords()
            if line_gps and line_gps not in self.lines:
                self.lines.append(line_gps)
                eastings, northings = [float(coord[0]) for coord in line_gps], [float(coord[1]) for coord in line_gps]
                line_label = RotnAnnotation(f"{pem_file.header.get('LineHole')}",
                                            label_xy=(float(line_gps[0][0]), float(line_gps[0][1])),
                                            p=(eastings[0], northings[0]), pa=(eastings[-1], northings[-1]),
                                            va='bottom', ha='center', color=self.color, zorder=4,
                                            path_effects=label_buffer)
                self.station_handle, = self.ax.plot(eastings, northings, '-|', markersize=5, color=self.color,
                                                    label='Surface Line', transform=self.crs, zorder=2)  # Plot the line

        def add_hole_to_map(pem_file):

            def get_borehole_projection(segments):
                if not collar:
                    return None
                else:
                    trace = [(col_x, col_y)]  # Easting and Northing tuples
                    azimuth = None
                    for segment in segments:
                        azimuth = math.radians(float(segment[0]))
                        dip = math.radians(float(segment[1]))
                        seg_l = float(segment[2])
                        delta_seg_l = seg_l * math.cos(dip)
                        delta_elev = seg_l * math.sin(dip)
                        dx = delta_seg_l * math.sin(azimuth)
                        dy = delta_seg_l * math.cos(azimuth)
                        trace.append((float(trace[-1][0]) + dx, float(trace[-1][1]) + dy))
                    return [segment[0] for segment in trace], [segment[1] for segment in trace]

            if self.draw_hole_collar is True:
                collar = pem_file.get_collar_coords()
                col_x, col_y = float(collar[0][0]), float(collar[0][1])
                segments = pem_file.get_hole_geometry()
                if segments:
                    seg_x, seg_y = get_borehole_projection(segments)
                else:
                    seg_x, seg_y = None, None

                if collar and collar not in self.collars:
                    self.collars.append(collar)
                    self.collar_handle, = self.ax.plot(col_x, col_y, 'o', color=self.color,
                                                       fillstyle='none', label='Borehole Collar', zorder=2)
                    # Add the hole label at the collar
                    collar_label = RotnAnnotation(f"{pem_file.header.get('LineHole')}",
                                                  label_xy=(col_x, col_y),
                                                  p=(seg_x[0], seg_y[0]), pa=(seg_x[-1], seg_y[-1]), ax=self.ax, hole_collar=True,
                                                  va='bottom', ha='center', color=self.color, zorder=4,
                                                  path_effects=label_buffer)

                    # Add buffer around the label for readability
                    # collar_label.set_path_effects([patheffects.Stroke(linewidth=3, foreground='white'),
                    #                               patheffects.Normal()])
                    if seg_x and seg_y and self.draw_hole_trace is True:
                        self.trace_handle, = self.ax.plot(seg_x, seg_y, '-.', color=self.color, label='Borehole Trace', zorder=2)
                        # Add the end tick for the borehole trace
                        end_tick = RotnAnnotation("|",
                                                  label_xy=(seg_x[-1], seg_y[-1]),
                                                  p=(seg_x[0], seg_y[0]), pa=(seg_x[-1], seg_y[-1]), ax=self.ax, hole_collar=False,
                                                  va='center', ha='center', rotation_mode='anchor', fontsize=14,
                                                  color=self.color)
                        # Label the depth of the hole
                        bh_depth = RotnAnnotation(f" {float(segments[-1][-1]):.0f} m",
                                                  label_xy=(seg_x[-1], seg_y[-1]),
                                                  p=(seg_x[0], seg_y[0]), pa=(seg_x[-1], seg_y[-1]), ax=self.ax, hole_collar=True,
                                                  va='bottom', ha='left', fontsize=8, color=self.color,
                                                  path_effects=label_buffer, zorder=3)
                else:
                    pass

        for pem_file in self.pem_files:
            label_buffer = [patheffects.Stroke(linewidth=3, foreground='white'), patheffects.Normal()]

            if self.draw_loops is True:
                add_loop_to_map(pem_file)

            if 'surface' in pem_file.survey_type.lower() and self.draw_lines is True:
                add_line_to_map(pem_file)

            if 'borehole' in pem_file.survey_type.lower() and self.draw_hole_collar is True:
                add_hole_to_map(pem_file)

    def format_figure(self):

        def scale_bar(ax, proj, length=None, location=(0.5, 0.05), linewidth=3,
                      units='m', m_per_unit=1000):
            """
            http://stackoverflow.com/a/35705477/1072212
            ax is the axes to draw the scalebar on.
            proj is the projection the axes are in
            location is center of the scalebar in axis coordinates ie. 0.5 is the middle of the plot
            length is the length of the scalebar in km.
            linewidth is the thickness of the scalebar.
            units is the name of the unit
            m_per_unit is the number of meters in a unit
            """
            # find lat/lon center to find best UTM zone
            x0, x1, y0, y1 = ax.get_extent(proj.as_geodetic())
            # Projection in metres
            tm = ccrs.TransverseMercator((x0 + x1) / 2)
            # Get the extent of the plotted area in coordinates in metres
            x0, x1, y0, y1 = ax.get_extent(tm)
            # Turn the specified scalebar location into coordinates in metres
            sbcx, sbcy = x0 + (x1 - x0) * location[0], y0 + (y1 - y0) * location[1]

            if not length:
                def myround(x, base=5):
                    return base * math.ceil(x / base)

                length = (ax.get_extent()[1] - ax.get_extent()[0])
                num_digit = int(np.floor(np.log10(length)))  # number of digits in number
                length = round(length, -num_digit)  # round to 1sf
                length = myround(length / 8, base=0.5 * 10 ** num_digit)  # Rounds to the nearest 1,2,5...

            # Generate the x coordinate for the ends of the scalebar
            bar_xs = [sbcx - length * m_per_unit / 2, sbcx + length * m_per_unit / 2]
            # buffer for scalebar
            buffer = [patheffects.withStroke(linewidth=5, foreground="w")]
            # Plot the scalebar with buffer
            ax.plot(bar_xs, [sbcy, sbcy], transform=tm, color='dimgray',
                    linewidth=linewidth, path_effects=buffer)
            # buffer for text
            buffer = [patheffects.withStroke(linewidth=3, foreground="w")]
            # Plot the scalebar label
            t0 = ax.text(sbcx, sbcy, f"{length:.0f} {units}", transform=tm,
                         horizontalalignment='center', verticalalignment='bottom',
                         path_effects=buffer, zorder=2, color='dimgray')
            # Plot the scalebar without buffer, in case covered by text buffer
            ax.plot(bar_xs, [sbcy, sbcy], transform=tm, color='dimgray',
                    linewidth=linewidth, zorder=3)

        def set_size(ax=None):
            """
            Re-size the extents to make the axes 11" by 8.5"
            :param ax: GeoAxes object
            :return: None
            """

            def myround(x, base=5):
                return base * math.ceil(x / base)

            def get_scale_factor():
                # num_digit = len(str(int(current_scale)))  # number of digits in number
                num_digit = int(np.floor(np.log10(current_scale)))   # number of digits in number
                new_scale = round(current_scale, -num_digit)  # round to 1sf
                new_scale = myround(new_scale, base=5 * 10 ** num_digit)  # Rounds to the nearest 1,2,5...
                self.map_scale = new_scale
                scale_factor = new_scale / current_scale
                return scale_factor

            if not ax: ax = plt.gca()

            xmin, xmax, ymin, ymax = ax.get_extent()
            width, height = xmax - xmin, ymax - ymin
            current_scale = width / 0.2794  # 11 inches in meters
            scale_factor = get_scale_factor()
            offset = (ymax - ymin) * .25

            ratio = width / height
            if ratio < (11 / 8.5):
                new_height = height*1.2  # Add padding
                new_height = new_height * scale_factor  # Increase the height based on the increase in scale
                new_width = new_height * (11 / 8.5)  # Set the new width to be the correct ratio larger than height

            else:
                new_width = width*1.2
                new_width = new_width * scale_factor
                new_height = new_width * (8.5 / 11)

            new_xmin = xmin - ((new_width - width) / 2)
            new_xmax = xmax + ((new_width - width) / 2)
            new_ymin = ymin - ((new_height - height) / 2)
            new_ymax = ymax + ((new_height - height) / 2)

            ax.set_extent(
                (new_xmin - (offset * 11 / 8.5), new_xmax + (offset * 11 / 8.5), new_ymin - offset, new_ymax + offset),
                crs=self.crs)

        def add_title():
            b_xmin = 0.02
            b_width = 0.30
            b_ymin = 0.82
            b_height = 0.15
            center_pos = b_xmin + (b_width / 2)
            right_pos = b_xmin + b_width - .02
            left_pos = b_xmin + .02
            top_pos = b_ymin + b_height - 0.020

            line_1 = mlines.Line2D([b_xmin, b_xmin + b_width], [top_pos - .030, top_pos - .030],
                                   linewidth=1, color='gray', transform=self.ax.transAxes, zorder=4)

            line_2 = mlines.Line2D([b_xmin, b_xmin + b_width], [top_pos - .105, top_pos - .105],
                                   linewidth=.5, color='gray', transform=self.ax.transAxes, zorder=4)

            client = self.pem_files[0].header.get("Client")
            grid = self.pem_files[0].header.get("Grid")
            survey_type = self.pem_files[0].get_survey_type()

            survey_dates = [pem_file.header.get('Date') for pem_file in self.pem_files]
            min_date = datetime.strftime(min([datetime.strptime(date, '%B %d, %Y') for date in survey_dates]), '%B %d')
            max_date = datetime.strftime(max([datetime.strptime(date, '%B %d, %Y') for date in survey_dates]),
                                         '%B %d, %Y')

            # timebases = []
            # [timebases.append(timebase) for timebase in [pem_file.header.get('Timebase') for pem_file in self.pem_files] if timebase not in timebases]
            # [str(timebase) for timebase in timebases]
            #
            # timebase_freqs = [str(round(((1 / (float(timebase) / 1000)) / 4),2)) for timebase in timebases]

            coord_sys = "UTM Zone 31N, WGS 84"
            scale = f"1:{self.map_scale:,.0f}"

            rect = patches.FancyBboxPatch(xy=(b_xmin, b_ymin), width=b_width, height=b_height, edgecolor='gray',
                                          boxstyle="round,pad=0.005", facecolor='white', zorder=4,
                                          transform=self.ax.transAxes)
            self.ax.add_patch(rect)
            shadow = patches.Shadow(rect, 0.002, -0.002)
            self.ax.add_patch(shadow)
            self.ax.add_line(line_1)
            self.ax.add_line(line_2)

            self.ax.text(center_pos, top_pos, 'Crone Geophysics & Exploration Ltd.',
                         fontname='Century Gothic', fontsize=11, ha='center', zorder=5, transform=self.ax.transAxes)

            self.ax.text(center_pos, top_pos - 0.020, f"{survey_type} Pulse EM Survey", family='cursive',
                         style='italic',
                         fontname='Century Gothic', fontsize=10, ha='center', zorder=5, transform=self.ax.transAxes)

            self.ax.text(center_pos, top_pos - 0.040, f"{client}\n" + f"{grid}",
                         fontname='Century Gothic', fontsize=10, va='top', ha='center', zorder=5,
                         transform=self.ax.transAxes)

            self.ax.text(center_pos, top_pos - 0.085, f"Survey Date: {min_date} - {max_date}",
                         fontname='Century Gothic', fontsize=9, va='top', ha='center', zorder=5,
                         transform=self.ax.transAxes)

            self.ax.text(left_pos, top_pos - 0.113, f"{coord_sys}", family='cursive', style='italic', color='dimgray',
                         fontname='Century Gothic', fontsize=9, va='top', ha='left', zorder=5,
                         transform=self.ax.transAxes)

            self.ax.text(right_pos, top_pos - 0.113, f"Scale {scale}", family='cursive', style='italic',
                         color='dimgray',
                         fontname='Century Gothic', fontsize=9, va='top', ha='right', zorder=5,
                         transform=self.ax.transAxes)

        set_size(self.ax)
        plt.grid(linestyle='dotted')
        self.ax.xaxis.set_visible(True)  # Required to actually get the labels to show in UTM
        self.ax.yaxis.set_visible(True)
        self.ax.set_yticklabels(self.ax.get_yticklabels(), rotation=90, ha='center')
        self.ax.yaxis.set_major_formatter(ticker.StrMethodFormatter('{x:,.0f}m N'))
        self.ax.xaxis.set_major_formatter(ticker.StrMethodFormatter('{x:,.0f}m E'))
        self.ax.xaxis.set_ticks_position('top')
        plt.setp(self.ax.get_xticklabels(), fontname='Century Gothic')
        plt.setp(self.ax.get_yticklabels(), fontname='Century Gothic', va='center')
        plt.subplots_adjust(left=0.03, bottom=0.02, right=0.97, top=0.96)
        # self.ax.add_wms(wms='http://vmap0.tiles.osgeo.org/wms/vmap0',
        #                 layers=['basic'])

        scale_bar(self.ax, self.crs, m_per_unit=1, units='m')

        arrow = plt.arrow(0.96, 0.86, 0., 0.1, shape='right', width=0.008, facecolor='white', edgecolor='dimgray',
                          length_includes_head=True,
                          transform=self.ax.transAxes, zorder=10)
        arrow_shadow = patches.Shadow(arrow, 0.002, -0.002)
        self.ax.add_patch(arrow_shadow)

        add_title()
        legend_handles = [handle for handle in
                          [self.loop_handle, self.station_handle, self.collar_handle, self.trace_handle] if
                          handle is not None]
        self.ax.legend(handles=legend_handles, title='Legend', loc='lower left',
                       framealpha=1, shadow=True)

    def get_map(self):
        return self.fig


# class PEMPlotter:
#     """
#     Class for creating Crone LIN, LOG and STEP figures.
#     PEMFile must be averaged and split.
#     """
#
#     def __init__(self, pem_file=None, ri_file=None, **kwargs):  # hide_gaps=True, gap=None, x_min=None, x_max=None):
#         super().__init__()
#         self.pem_file = pem_file
#         self.ri_file = ri_file
#         self.hide_gaps = kwargs.get('HideGaps')
#         self.gap = kwargs.get('Gap')
#         self.data = self.pem_file.data
#         self.header = self.pem_file.header
#         self.stations = self.pem_file.get_converted_unique_stations()
#         self.survey_type = self.pem_file.survey_type
#         self.x_min = int(min(chain(self.stations))) if kwargs.get('XMin') is None else kwargs.get('XMin')
#         self.x_max = int(max(chain(self.stations))) if kwargs.get('XMax') is None else kwargs.get('XMax')
#         self.num_channels = int(self.header['NumChannels']) + 1
#         self.units = 'nT/s' if self.pem_file.tags['Units'].casefold() == 'nanotesla/sec' else 'pT'
#         # self.channel_bounds = self.calc_channel_bounds()
#         self.line_color = 'k'
#
#     #
#     # def calc_channel_bounds(self):
#     #     # channel_bounds is a list of tuples showing the inclusive bounds of each data plot
#     #     channel_bounds = [None] * 4
#     #     num_channels_per_plot = int((self.num_channels - 1) // 4)
#     #     remainder_channels = int((self.num_channels - 1) % 4)
#     #
#     #     for k in range(0, len(channel_bounds)):
#     #         channel_bounds[k] = (k * num_channels_per_plot + 1, num_channels_per_plot * (k + 1))
#     #
#     #     for i in range(0, remainder_channels):
#     #         channel_bounds[i] = (channel_bounds[i][0], (channel_bounds[i][1] + 1))
#     #         for k in range(i + 1, len(channel_bounds)):
#     #             channel_bounds[k] = (channel_bounds[k][0] + 1, channel_bounds[k][1] + 1)
#     #
#     #     channel_bounds.insert(0, (0, 0))
#     #     return channel_bounds
#
#     # def format_figure(self, figure, step=False):
#     #     """
#     #     Formats a figure, mainly the spines, adjusting the padding, and adding the rectangle.
#     #     :param figure: LIN or LOG figure object
#     #     """
#     #     axes = figure.axes
#     #
#     #     def format_spines(ax):
#     #         ax.spines['right'].set_visible(False)
#     #         ax.spines['top'].set_visible(False)
#     #
#     #         if ax != axes[-1]:
#     #             ax.spines['bottom'].set_position(('data', 0))
#     #             ax.tick_params(axis='x', which='major', direction='inout', length=4)
#     #             plt.setp(ax.get_xticklabels(), visible=False)
#     #         else:
#     #             ax.spines['bottom'].set_visible(False)
#     #             ax.xaxis.set_ticks_position('bottom')
#     #             ax.tick_params(axis='x', which='major', direction='out', length=6)
#     #             plt.setp(ax.get_xticklabels(), visible=True, size=12, fontname='Century Gothic')
#     #
#     #     plt.subplots_adjust(left=0.135 if step is False else 0.170, bottom=0.07, right=0.958, top=0.885)
#     #     add_rectangle(figure)
#     #
#     #     for ax in axes:
#     #         format_spines(ax)
#     #
#     # def format_xaxis(self, figure):
#     #     """
#     #     Formats the X axis of a figure
#     #     :param figure: LIN or LOG figure objects
#     #     """
#     #     x_label_locator = ticker.AutoLocator()
#     #     major_locator = ticker.FixedLocator(sorted(self.stations))
#     #     plt.xlim(self.x_min, self.x_max)
#     #     figure.axes[0].xaxis.set_major_locator(major_locator)  # for some reason this seems to apply to all axes
#     #     figure.axes[-1].xaxis.set_major_locator(x_label_locator)
#     #
#     # def make_lin_fig(self, component, lin_fig):
#     #     """
#     #     Plots the data into the LIN figure
#     #     :return: Matplotlib Figure object
#     #     """
#     #
#     #     def add_ylabels():
#     #         for i in range(len(lin_fig.axes) - 1):
#     #             ax = lin_fig.axes[i]
#     #             if i == 0:
#     #                 ax.set_ylabel('Primary Pulse' + "\n(" + self.units + ")")
#     #             else:
#     #                 ax.set_ylabel("Channel " + str(channel_bounds[i][0]) + " - " +
#     #                               str(channel_bounds[i][1]) + "\n(" + self.units + ")")
#     #
#     #     def calc_channel_bounds():
#     #         # channel_bounds is a list of tuples showing the inclusive bounds of each data plot
#     #         channel_bounds = [None] * 4
#     #         num_channels_per_plot = int((self.num_channels - 1) // 4)
#     #         remainder_channels = int((self.num_channels - 1) % 4)
#     #
#     #         for k in range(0, len(channel_bounds)):
#     #             channel_bounds[k] = (k * num_channels_per_plot + 1, num_channels_per_plot * (k + 1))
#     #
#     #         for i in range(0, remainder_channels):
#     #             channel_bounds[i] = (channel_bounds[i][0], (channel_bounds[i][1] + 1))
#     #             for k in range(i + 1, len(channel_bounds)):
#     #                 channel_bounds[k] = (channel_bounds[k][0] + 1, channel_bounds[k][1] + 1)
#     #
#     #         channel_bounds.insert(0, (0, 0))
#     #         return channel_bounds
#     #
#     #     self.format_figure(lin_fig)
#     #     channel_bounds = calc_channel_bounds()
#     #
#     #     for i, group in enumerate(channel_bounds):
#     #         ax = lin_fig.axes[i]
#     #         self.draw_lines(ax, group[0], group[1], component)
#     #
#     #     self.add_title(component)
#     #     add_ylabels()
#     #     self.format_yaxis(lin_fig)
#     #     self.format_xaxis(lin_fig)
#     #     return lin_fig
#
#     def make_log_fig(self, component, log_fig):
#         """
#         Plots the data into the LOG figure
#         :return: Matplotlib Figure object
#         """
#
#         def add_ylabel():
#             ax = log_fig.axes[0]
#             ax.set_ylabel('Primary Pulse to Channel ' + str(self.num_channels - 1) + "\n(" + self.units + ")")
#
#         self.format_figure(log_fig)
#         ax = log_fig.axes[0]
#
#         self.draw_lines(ax, 0, self.num_channels - 1, component)
#         self.add_title(component)
#         add_ylabel()
#         self.format_yaxis(log_fig)
#         self.format_xaxis(log_fig)
#         return log_fig
#
#     def make_step_fig(self, component, step_fig):
#         """
#         Plots the step data (from ri_file) into the step_fig.
#         :param component: Component i.e. X, Y, or Z
#         :param step_fig: Figure object
#         :return: Figure object
#         """
#
#         def add_ylabel(profile_data, num_channels_to_plot):
#             fluxgate = True if 'fluxgate' in self.survey_type.lower() else False
#             units = 'pT' if fluxgate is True else 'nT/s'
#             channels = [re.findall('\d+', key)[0] for key in profile_data if re.match('Ch', key)]
#
#             step_fig.axes[0].set_ylabel("TP = Theoretical Primary\n"
#                                         f"{'PP = Calculated PP x Ramp' if fluxgate is True else 'PP = Last Ramp Channel'}\n"
#                                         f"S1 = Calculated Step Ch.1\n({units})")
#             step_fig.axes[1].set_ylabel("Deviation from TP\n"
#                                         "(% Total Theoretical)")
#             step_fig.axes[2].set_ylabel("Step Channels 2 - 4\n"
#                                         "Deviation from S1\n"
#                                         "(% Total Theoretical)")
#             step_fig.axes[3].set_ylabel("Pulse EM Off-time\n"
#                                         f"Channels {str(min(channels[-num_channels_to_plot:]))} - "
#                                         f"{str(max(channels[-num_channels_to_plot:]))}\n"
#                                         f"({units})")
#
#         def annotate_line(ax, annotation, interp_data, x_intervals, offset):
#
#             for i, x_position in enumerate(x_intervals[int(offset)::int(len(x_intervals) * 0.4)]):
#                 y = interp_data[list(x_intervals).index(x_position)]
#
#                 ax.annotate(str(annotation), xy=(x_position, y), xycoords="data", size=7.5, va='center_baseline',
#                             ha='center',
#                             color=self.line_color)
#
#         def draw_step_lines(fig, profile_data):
#             """
#             Plotting the lines for step plots made from RI files.
#             :param fig: step_fig Figure object
#             :param profile_data: RI file data tranposed to profile mode
#             :return: step_fig object with lines plotted
#             """
#
#             segments = 1000  # The data will be broken in this number of segments
#             offset = segments * 0.1  # Used for spacing the annotations
#
#             keys = ['Theoretical PP', 'Measured PP', 'S1', '(M-T)*100/Tot', '(S1-T)*100/Tot', '(S2-S1)*100/Tot', 'S3%',
#                     'S4%']
#             annotations = ['TP', 'PP', 'S1', 'PP', 'S1', 'S2', 'S3', 'S4']
#             stations = profile_data['Stations']
#             for i, key in enumerate(keys):
#                 interp_data, x_intervals = self.get_interp_data(profile_data[key], stations)
#                 mask = np.isclose(interp_data, interp_data.astype('float64'))
#                 x_intervals = x_intervals[mask]
#                 interp_data = interp_data[mask]
#
#                 if i < 3:  # Plotting TP, PP, and S1 to the first axes
#                     ax = fig.axes[0]
#                     ax.plot(x_intervals, interp_data, color=self.line_color)
#                     annotate_line(ax, annotations[i], interp_data, x_intervals, offset)
#                     offset += len(x_intervals) * 0.15
#                 elif i < 5:  # Plotting the PP and S1% to the second axes
#                     if i == 3:  # Resetting the annotation positions
#                         offset = segments * 0.1
#                     ax = fig.axes[1]
#                     ax.plot(x_intervals, interp_data, color=self.line_color)
#                     annotate_line(ax, annotations[i], interp_data, x_intervals, offset)
#                     offset += len(x_intervals) * 0.15
#                 else:  # Plotting S2% to S4% to the third axes
#                     if i == 5:
#                         offset = segments * 0.1
#                     ax = fig.axes[2]
#                     ax.plot(x_intervals, interp_data, color=self.line_color)
#                     annotate_line(ax, annotations[i], interp_data, x_intervals, offset)
#                     offset += len(x_intervals) * 0.15
#                 if offset >= len(x_intervals) * 0.85:
#                     offset = len(x_intervals) * 0.10
#
#             offset = segments * 0.1
#             # Plotting the off-time channels to the fourth axes
#             for i, channel in enumerate(off_time_channel_data[-num_channels_to_plot:]):
#                 interp_data, x_intervals = self.get_interp_data(channel, stations)
#                 mask = np.isclose(interp_data, interp_data.astype('float64'))
#                 x_intervals = x_intervals[mask]
#                 interp_data = interp_data[mask]
#                 ax = fig.axes[3]
#                 ax.plot(x_intervals, interp_data, color=self.line_color)
#                 annotate_line(ax, str(num_off_time_channels - i), interp_data, x_intervals, offset)
#                 offset += len(x_intervals) * 0.15
#                 if offset >= len(x_intervals) * 0.85:
#                     offset = len(x_intervals) * 0.10
#
#         self.format_figure(step_fig, step=True)
#         profile_data = self.get_profile_step_data(component)
#         off_time_channel_data = [profile_data[key] for key in profile_data if re.match('Ch', key)]
#         num_off_time_channels = len(off_time_channel_data) + 10
#         num_channels_to_plot = round(num_off_time_channels / 4)
#
#         draw_step_lines(step_fig, profile_data)
#
#         self.add_title(component)
#         add_ylabel(profile_data, num_channels_to_plot)
#         self.format_yaxis(step_fig, step=True)
#         self.format_xaxis(step_fig)
#         return step_fig
#
#     def make_plan_map(self, pem_files):
#         pass
#
#     # def convert_station(self, station):
#     #     """
#     #     Converts a single station name into a number, negative if the stations was S or W
#     #     :return: Integer station number
#     #     """
#     #     if re.match(r"\d+(S|W)", station):
#     #         station = (-int(re.sub(r"\D", "", station)))
#     #
#     #     else:
#     #         station = (int(re.sub(r"\D", "", station)))
#     #
#     #     return station
#     #
#     # def get_profile_data(self, component):
#     #     """
#     #     Transforms the data so it is ready to be plotted for LIN and LOG plots. Only for PEM data.
#     #     :param component: A single component (i.e. Z, X, or Y)
#     #     :return: Dictionary where each key is a channel, and the values of those keys are a list of
#     #     dictionaries which contain the stations and readings of all readings of that channel
#     #     """
#     #     profile_data = {}
#     #     component_data = list(filter(lambda d: d['Component'] == component, self.data))
#     #     num_channels = len(component_data[0]['Data'])
#     #     for channel in range(0, num_channels):
#     #         channel_data = []
#     #
#     #         for i, station in enumerate(component_data):
#     #             reading = station['Data'][channel]
#     #             station_number = int(self.convert_station(station['Station']))
#     #             channel_data.append({'Station': station_number, 'Reading': reading})
#     #
#     #         profile_data[channel] = channel_data
#     #
#     #     return profile_data
#
#     def get_profile_step_data(self, component):
#         """
#         Transforms the RI data as a profile to be plotted.
#         :param component: The component that is being plotted (i.e. X, Y, Z)
#         :return: The data in profile mode
#         """
#         profile_data = {}
#         keys = self.ri_file.columns
#         component_data = list(filter(lambda d: d['Component'] == component, self.ri_file.data))
#
#         for key in keys:
#             if key is not 'Gain' and key is not 'Component':
#                 if key is 'Station':
#                     key = 'Stations'
#                     profile_data[key] = [self.convert_station(station['Station']) for station in component_data]
#                 else:
#                     profile_data[key] = [float(station[key]) for station in component_data]
#         return profile_data
#
#     #
#     # def get_channel_data(self, channel, profile_data):
#     #     """
#     #     Get the profile-mode data for a given channel. Only for PEM data.
#     #     :param channel: int, channel number
#     #     :param profile_data: dict, data in profile-mode
#     #     :return: data in list form and corresponding stations as a list
#     #     """
#     #     data = []
#     #     stations = []
#     #
#     #     for station in profile_data[channel]:
#     #         data.append(station['Reading'])
#     #         stations.append(station['Station'])
#     #
#     #     return data, stations
#
#     # def get_interp_data(self, profile_data, stations, segments=1000, interp_method='linear'):
#     #     """
#     #     Interpolates the data using 1-D piecewise linear interpolation. The data is segmented
#     #     into 1000 segments.
#     #     :param profile_data: The EM data in profile mode
#     #     :param segments: Number of segments to interpolate
#     #     :param hide_gaps: Bool: Whether or not to hide gaps
#     #     :param gap: The minimum length threshold above which is considered a gap
#     #     :return: The interpolated data and stations
#     #     """
#     #
#     #     def calc_gaps(stations):
#     #         survey_type = self.survey_type
#     #
#     #         if 'borehole' in survey_type.casefold():
#     #             min_gap = 50
#     #         elif 'surface' in survey_type.casefold():
#     #             min_gap = 200
#     #         station_gaps = np.diff(stations)
#     #
#     #         if self.gap is None:
#     #             self.gap = max(int(stats.mode(station_gaps)[0] * 2), min_gap)
#     #
#     #         gap_intervals = [(stations[i], stations[i + 1]) for i in range(len(stations) - 1) if
#     #                          station_gaps[i] > self.gap]
#     #
#     #         return gap_intervals
#     #
#     #     stations = np.array(stations, dtype='float64')
#     #     readings = np.array(profile_data, dtype='float64')
#     #     x_intervals = np.linspace(stations[0], stations[-1], segments)
#     #     f = interpolate.interp1d(stations, readings, kind=interp_method)
#     #
#     #     interpolated_y = f(x_intervals)
#     #
#     #     if self.hide_gaps:
#     #         gap_intervals = calc_gaps(stations)
#     #
#     #         # Masks the intervals that are between gap[0] and gap[1]
#     #         for gap in gap_intervals:
#     #             interpolated_y = np.ma.masked_where((x_intervals > gap[0]) & (x_intervals < gap[1]),
#     #                                                 interpolated_y)
#     #
#     #     return interpolated_y, x_intervals
#     #
#     # def draw_lines(self, ax, channel_low, channel_high, component):
#     #     """
#     #     Plots the lines into an axes of a figure. Not for step figures.
#     #     :param ax: Axes of a figure, either LIN or LOG figure objects
#     #     :param channel_low: The first channel to be plotted
#     #     :param channel_high: The last channel to be plotted
#     #     :param component: String letter representing the component to plot (X, Y, or Z)
#     #     """
#     #
#     #     segments = 1000  # The data will be broken in this number of segments
#     #     offset = segments * 0.1  # Used for spacing the annotations
#     #     profile_channel_data = self.get_profile_data(component)
#     #
#     #     for k in range(channel_low, (channel_high + 1)):
#     #         # Gets the profile data for a single channel, along with the stations
#     #         channel_data, stations = self.get_channel_data(k, profile_channel_data)
#     #
#     #         # Interpolates the channel data, also returns the corresponding x intervals
#     #         interp_data, x_intervals = self.get_interp_data(channel_data, stations, segments)
#     #
#     #         ax.plot(x_intervals, interp_data, color=self.line_color)
#     #
#     #         # Mask is used to hide data within gaps
#     #         mask = np.isclose(interp_data, interp_data.astype('float64'))
#     #         x_intervals = x_intervals[mask]
#     #         interp_data = interp_data[mask]
#     #
#     #         # Annotating the lines
#     #         for i, x_position in enumerate(x_intervals[int(offset)::int(len(x_intervals) * 0.4)]):
#     #             y = interp_data[list(x_intervals).index(x_position)]
#     #
#     #             if k == 0:
#     #                 ax.annotate('PP', xy=(x_position, y), xycoords="data", size=7.5, va='center_baseline', ha='center',
#     #                             color=self.line_color)
#     #
#     #             else:
#     #                 ax.annotate(str(k), xy=(x_position, y), xycoords="data", size=7.5, va='center_baseline',
#     #                             ha='center',
#     #                             color=self.line_color)
#     #
#     #         offset += len(x_intervals) * 0.15
#     #
#     #         if offset >= len(x_intervals) * 0.85:
#     #             offset = len(x_intervals) * 0.10
#     #
#     # def format_yaxis(self, figure, step=False):
#     #     """
#     #     Formats the Y axis of a figure. Will increase the limits of the scale if depending on the limits of the data.
#     #     :param figure: LIN, LOG or Step figure objects
#     #     """
#     #     axes = figure.axes[:-1]
#     #
#     #     for ax in axes:
#     #         ax.get_yaxis().set_label_coords(-0.08 if step is False else -0.095, 0.5)
#     #
#     #         if ax.get_yscale() != 'symlog':
#     #             y_limits = ax.get_ylim()
#     #
#     #             if 'induction' in self.survey_type.lower():
#     #                 if step is True:
#     #                     if ax == axes[1] and (y_limits[1] - y_limits[0]) < 20:
#     #                         new_high = math.ceil(((y_limits[1] - y_limits[0]) / 2) + 10)
#     #                         new_low = new_high * -1
#     #                     elif ax in axes[2:4] and (y_limits[1] - y_limits[0]) < 3:
#     #                         new_high = math.ceil(((y_limits[1] - y_limits[0]) / 2) + 1)
#     #                         new_low = new_high * -1
#     #                     else:
#     #                         new_high = math.ceil(max(y_limits[1], 0))
#     #                         new_low = math.floor(min(y_limits[0], 0))
#     #                 else:
#     #                     if (y_limits[1] - y_limits[0]) < 3:
#     #                         new_high = math.ceil(((y_limits[1] - y_limits[0]) / 2) + 1)
#     #                         new_low = new_high * -1
#     #                     else:
#     #                         new_high = math.ceil(max(y_limits[1], 0))
#     #                         new_low = math.floor(min(y_limits[0], 0))
#     #
#     #             elif 'fluxgate' in self.survey_type.lower():
#     #                 if step is True:
#     #                     if ax == axes[1] and (y_limits[1] - y_limits[0]) < 20:
#     #                         new_high = math.ceil(((y_limits[1] - y_limits[0]) / 2) + 10)
#     #                         new_low = new_high * -1
#     #                     elif ax == axes[2] and (y_limits[1] - y_limits[0]) < 3:
#     #                         new_high = math.ceil(((y_limits[1] - y_limits[0]) / 2) + 1)
#     #                         new_low = new_high * -1
#     #                     elif ax == axes[3] and (y_limits[1] - y_limits[0]) < 30:
#     #                         new_high = math.ceil(((y_limits[1] - y_limits[0]) / 2) + 10)
#     #                         new_low = new_high * -1
#     #                     else:
#     #                         new_high = math.ceil(max(y_limits[1], 0))
#     #                         new_low = math.floor(min(y_limits[0], 0))
#     #                 else:
#     #                     if (y_limits[1] - y_limits[0]) < 30:
#     #                         new_high = math.ceil(((y_limits[1] - y_limits[0]) / 2) + 10)
#     #                         new_low = new_high * -1
#     #                     else:
#     #                         new_high = math.ceil(max(y_limits[1], 0))
#     #                         new_low = math.floor(min(y_limits[0], 0))
#     #
#     #             ax.set_ylim(new_low, new_high)
#     #             ax.set_yticks(ax.get_yticks())
#     #
#     #         elif ax.get_yscale() == 'symlog':
#     #             y_limits = ax.get_ylim()
#     #             new_high = 10.0 ** math.ceil(math.log(max(y_limits[1], 11), 10))
#     #             new_low = -1 * 10.0 ** math.ceil(math.log(max(abs(y_limits[0]), 11), 10))
#     #             ax.set_ylim(new_low, new_high)
#     #
#     #             ax.tick_params(axis='y', which='major', labelrotation=90)
#     #             plt.setp(ax.get_yticklabels(), va='center')
#     #
#     #         ax.yaxis.set_major_formatter(ticker.FormatStrFormatter('%d'))  # Prevent scientific notation
#     #
#     # def add_title(self, component):
#     #     """
#     #     Adds the title header to a figure
#     #     """
#     #
#     #     timebase_freq = ((1 / (float(self.header['Timebase']) / 1000)) / 4)
#     #
#     #     if 'borehole' in self.survey_type.casefold():
#     #         s_title = 'Hole'
#     #     else:
#     #         s_title = 'Line'
#     #
#     #     plt.figtext(0.550, 0.960, 'Crone Geophysics & Exploration Ltd.',
#     #                 fontname='Century Gothic', fontsize=11, ha='center')
#     #
#     #     plt.figtext(0.550, 0.945, self.survey_type + ' Pulse EM Survey', family='cursive', style='italic',
#     #                 fontname='Century Gothic', fontsize=10, ha='center')
#     #
#     #     plt.figtext(0.145, 0.935, 'Timebase: ' + str(self.header['Timebase']) + ' ms\n' +
#     #                 'Base Frequency: ' + str(round(timebase_freq, 2)) + ' Hz\n' +
#     #                 'Current: ' + str(round(float(self.pem_file.tags.get('Current')), 1)) + ' A',
#     #                 fontname='Century Gothic', fontsize=10, va='top')
#     #
#     #     plt.figtext(0.550, 0.935, s_title + ': ' + self.header.get('LineHole') + '\n' +
#     #                 'Loop: ' + self.header.get('Loop') + '\n' +
#     #                 component + ' Component',
#     #                 fontname='Century Gothic', fontsize=10, va='top', ha='center')
#     #
#     #     plt.figtext(0.955, 0.935,
#     #                 self.header.get('Client') + '\n' + self.header.get('Grid') + '\n' + self.header['Date'] + '\n',
#     #                 fontname='Century Gothic', fontsize=10, va='top', ha='right')


# class PlanMap:
#     def __init__(self):
#         self.figure = None
#         self.pem_files = None
#         self.gps_editor = GPSEditor
#
#     def make_plan_map(self, pem_files, figure):
#         self.figure = figure
#         self.pem_files = pem_files
#
#         if all(['surface' in pem_file.survey_type.lower() for pem_file in self.pem_files]):
#             self.surface_plan()
#         elif all(['borehole' in pem_file.survey_type.lower() for pem_file in self.pem_files]):
#             self.borehole_plan()
#         else:
#             return None
#
#     def plot_loops(self):
#
#         def draw_loop(pem_file):
#             loop_coords = pem_file.loop_coords
#             loop_center = self.gps_editor().get_loop_center(copy.copy(loop_coords))
#             eastings, northings = [float(coord[1]) for coord in loop_coords], [float(coord[2]) for coord in loop_coords]
#             eastings.insert(0, eastings[-1])  # To close up the loop
#             northings.insert(0, northings[-1])
#
#             self.figure.axes[0].text(loop_center[0], loop_center[1], pem_file.header.get('Loop'),
#                                      multialignment='center')
#             self.figure.axes[0].plot(eastings, northings, color='b')
#
#         loops = []
#         for pem_file in self.pem_files:
#             if pem_file.loop_coords not in loops:  # plot the loop if the loop hasn't been plotted yet
#                 draw_loop(pem_file)
#
#     def format_figure(self):
#         ax = self.figure.axes[0]
#         ax.set_aspect('equal', adjustable='box')
#         [ax.spines[spine].set_color('none') for spine in ax.spines]
#         ax.tick_params(axis='y', which='major', labelrotation=90)
#         ax.tick_params(which='major', width=1.00, length=5, labelsize=10)
#         ax.yaxis.set_major_formatter(ticker.FormatStrFormatter('%dN'))
#         ax.xaxis.set_major_formatter(ticker.FormatStrFormatter('%dE'))
#         ax.xaxis.set_ticks_position('top')
#         plt.setp(ax.get_xticklabels(), fontname='Century Gothic')
#         plt.setp(ax.get_yticklabels(), fontname='Century Gothic', va='center')
#         plt.grid(linestyle='dotted')
#         plt.subplots_adjust(left=0.092, bottom=0.07, right=0.908, top=0.685)
#         add_rectangle(self.figure)
#
#         xmin, xmax = ax.get_xlim()
#         ymin, ymax = ax.get_ylim()
#         xwidth, ywidth = xmax - xmin, ymax - ymin
#
#         if xwidth < 1000:
#             scalesize = 250
#         elif xwidth < 2000:
#             scalesize = 500
#         elif xwidth < 3000:
#             scalesize = 750
#         elif xwidth < 4000:
#             scalesize = 1000
#
#         # SCALE BAR
#         scalebar = AnchoredHScaleBar(size=scalesize, label=str(scalesize) + 'm', loc=4, frameon=False,
#                                      pad=0.3, sep=2, color="black", ax=ax)
#         ax.add_artist(scalebar)
#         # NORTH ARROW
#         # ax.annotate('N', (1.01, 1), xytext=(1.01, 0.9), xycoords='axes fraction',
#         #             ha='center', fontsize=12, fontweight='bold',
#         #             arrowprops=dict(arrowstyle='->', color='k'), transform=ax.transAxes)
#
#         plt.arrow(0.5, 0.5, 0., 0.5, shape='right', width=0.007, color='gray', length_includes_head=True,
#                   transform=self.figure.transFigure, zorder=10)
#
#     def surface_plan(self):
#
#         def plot_lines():
#             pass
#
#         self.plot_loops()
#         plot_lines()
#         self.format_figure()
#         return self.figure
#
#     def borehole_plan(self):
#         borehole_names = []
#         # TODO Can have same hole with two loops
#         unique_boreholes = []
#         for pem_file in self.pem_files:
#             borehole_names.append(pem_file.header.get('LineHole'))
#             if pem_file.header.get('LineHole') not in borehole_names:
#                 unique_boreholes.append(pem_file)
#         self.pem_files = unique_boreholes
#
#         return self.figure


# Draws a pretty scale bar
class AnchoredHScaleBar(matplotlib.offsetbox.AnchoredOffsetbox):
    """ size: length of bar in data units
        extent : height of bar ends in axes units
    """

    def __init__(self, size=1, extent=0.03, label="", loc=1, ax=None,
                 pad=0.4, borderpad=0.5, ppad=-25, sep=2, prop=None,
                 frameon=True, **kwargs):
        if not ax:
            ax = plt.gca()
        trans = ax.get_xaxis_transform()
        size_bar = matplotlib.offsetbox.AuxTransformBox(trans)
        line = Line2D([0, size], [0, 0], **kwargs)
        vline1 = Line2D([0, 0], [-extent / 2., extent / 2.], **kwargs)
        vline2 = Line2D([size, size], [-extent / 2., extent / 2.], **kwargs)
        size_bar.add_artist(line)
        size_bar.add_artist(vline1)
        size_bar.add_artist(vline2)
        txt = matplotlib.offsetbox.TextArea(label, minimumdescent=False)
        self.vpac = matplotlib.offsetbox.VPacker(children=[size_bar, txt],
                                                 align="center", pad=ppad, sep=sep)
        matplotlib.offsetbox.AnchoredOffsetbox.__init__(self, loc, pad=pad,
                                                        borderpad=borderpad, child=self.vpac, prop=prop,
                                                        frameon=frameon)


class PEMPrinter:
    """
    Class for printing PEMPLotter plots to PDF.
    Creates the figures for PEMPlotter so they may be closed after they are saved.
    :param pem_files: List of PEMFile objects
    :param save_path: Desired save location for the PDFs
    :param kwargs: Plotting kwargs such as hide_gaps, gaps, and x limits used in PEMPlotter.
    """

    def __init__(self, save_path, files, **kwargs):
        self.files = files  # Zipped PEM and RI files
        self.pem_files = []
        self.ri_files = []
        self.sort_files()

        self.save_path = save_path
        self.x_min = kwargs.get('XMin')
        self.x_max = kwargs.get('XMax')
        self.hide_gaps = kwargs.get('HideGaps')
        # self.projection = kwargs.get('Projection')
        self.projection = ccrs.UTM(31)
        self.pb = QProgressBar()
        self.pb_count = 0
        self.pb_end = sum([len(pair[0].get_components()) for pair in self.files])
        self.pb.setValue(0)

    def sort_files(self):
        self.files.sort(key=lambda x: x[0].get_components(), reverse=True)
        self.files.sort(key=lambda x: x[0].header['LineHole'])

        self.pem_files = [pair[0] for pair in self.files]
        self.ri_files = [pair[1] for pair in self.files]

    def create_plan_figure(self):
        """
        Creates an empty but formatted Plan figure
        :return: Figure object
        """
        plan_fig, ax = plt.subplots(1, 1, figsize=(11, 8.5))
        return plan_fig

    def create_lin_figure(self):
        """
        Creates the blank LIN figure
        :return: Figure object
        """
        lin_fig, (ax1, ax2, ax3, ax4, ax5) = plt.subplots(5, 1, figsize=(8.5, 11), sharex=True)
        ax6 = ax5.twiny()
        ax6.get_shared_x_axes().join(ax5, ax6)

        return lin_fig

    def create_log_figure(self):
        """
        Creates an empty but formatted LOG figure
        :return: Figure object
        """
        log_fig, ax = plt.subplots(1, 1, figsize=(8.5, 11))
        ax2 = ax.twiny()
        ax2.get_shared_x_axes().join(ax, ax2)
        plt.yscale('symlog', linthreshy=10, linscaley=1. / math.log(10), subsy=list(np.arange(2, 10, 1)))

        return log_fig

    def create_step_figure(self):
        """
        Creates the blank Step figure
        :return: Figure object
        """
        stp_fig, (ax1, ax2, ax3, ax4) = plt.subplots(4, 1, figsize=(8.5, 11), sharex=True)
        ax5 = ax4.twiny()
        ax5.get_shared_x_axes().join(ax4, ax5)
        return stp_fig

    # To save LIN and LOG pdfs separately. Requires a save_dir instead of a save_path.
    # def print_lin_figs(self):
    #     with PdfPages(os.path.join(self.save_dir, "lin.pdf")) as pdf:
    #         for pem_file in self.pem_files:
    #             components = pem_file.get_components()
    #             for component in components:
    #                 lin_figure = self.create_lin_figure()
    #                 lin_plot = self.plotter(pem_file, **self.kwargs).make_lin_fig(component, lin_figure)
    #                 pdf.savefig(lin_plot)
    #                 self.pb_count += 1
    #                 self.pb.setValue((self.pb_count/self.pb_end) * 100)
    #                 plt.close(lin_figure)
    #
    # def print_log_figs(self):
    #     with PdfPages(os.path.join(self.save_dir, "log.pdf")) as pdf:
    #         for pem_file in self.pem_files:
    #             components = pem_file.get_components()
    #             for component in components:
    #                 log_figure = self.create_log_figure()
    #                 log_plot = self.plotter(pem_file, **self.kwargs).make_log_fig(component, log_figure)
    #                 pdf.savefig(log_plot)
    #                 self.pb_count += 1
    #                 self.pb.setValue((self.pb_count / self.pb_end) * 100)
    #                 plt.close(log_figure)

    def print_plan_map(self):
        with PdfPages(self.save_path + '.PDF') as pdf:
            plan_figure = self.create_plan_figure()
            plan_map = PlanMap(self.pem_files, plan_figure, self.projection)
            pdf.savefig(plan_map.get_map(), orientation='landscape')
            self.pb_count += 1
            self.pb.setValue(int((self.pb_count / self.pb_end) * 100))
            plt.close(plan_figure)
        os.startfile(self.save_path + '.PDF')

    def print_step_plots(self):
        with PdfPages(self.save_path + '.PDF') as pdf:
            for file in self.files:
                pem_file = file[0]
                ri_file = file[1]
                if ri_file:
                    components = pem_file.get_components()
                    for component in components:
                        step_figure = self.create_step_figure()
                        step_plotter = STEPPlotter()
                        plotted_fig = step_plotter.plot(pem_file, ri_file, component, step_figure, x_min=self.x_min,
                                                        x_max=self.x_max,
                                                        hide_gaps=self.hide_gaps)
                        pdf.savefig(plotted_fig)
                        self.pb_count += 1
                        self.pb.setValue(int((self.pb_count / self.pb_end) * 100))
                        plt.close(step_figure)
        os.startfile(self.save_path + '.PDF')

    def print_final_plots(self):
        # file_name = self.pem_files[-1].header.get('LineHole')+'.PDF'
        # path = os.path.join(self.save_dir, file_name)
        with PdfPages(self.save_path + '.PDF') as pdf:
            for pem_file in self.pem_files:
                components = pem_file.get_components()
                for component in components:
                    lin_figure = self.create_lin_figure()
                    lin_plotter = LINPlotter()
                    plotted_fig = lin_plotter.plot(pem_file, component, lin_figure, x_min=self.x_min, x_max=self.x_max,
                                                   hide_gaps=self.hide_gaps)
                    pdf.savefig(plotted_fig)
                    self.pb_count += 1
                    self.pb.setValue(int((self.pb_count / self.pb_end) * 100))
                    plt.close(lin_figure)
            for pem_file in self.pem_files:
                components = pem_file.get_components()
                for component in components:
                    log_figure = self.create_log_figure()
                    log_plotter = LOGPlotter()
                    plotted_fig = log_plotter.plot(pem_file, component, log_figure, x_min=self.x_min, x_max=self.x_max,
                                                   hide_gaps=self.hide_gaps)
                    pdf.savefig(plotted_fig)
                    self.pb_count += 1
                    self.pb.setValue(int((self.pb_count / self.pb_end) * 100))
                    plt.close(log_figure)
            for file in self.files:
                pem_file = file[0]
                ri_file = file[1]
                if ri_file:
                    components = pem_file.get_components()
                    for component in components:
                        step_figure = self.create_step_figure()
                        step_plotter = STEPPlotter()
                        plotted_fig = step_plotter.plot(pem_file, ri_file, component, step_figure, x_min=self.x_min,
                                                        x_max=self.x_max,
                                                        hide_gaps=self.hide_gaps)
                        pdf.savefig(plotted_fig)
                        self.pb_count += 1
                        self.pb.setValue(int((self.pb_count / self.pb_end) * 100))
                        plt.close(step_figure)
        os.startfile(self.save_path + '.PDF')


# class CronePYQTFigure:
#     """
#     Class creating graphs using pyqtgraph.
#     # TODO Straight to Widget or make figures?
#     # TODO Only needs data, should the class do the rest of the work?
#     """

if __name__ == '__main__':
    parser = PEMParser
    # # sample_files = os.path.join(os.path.dirname(os.path.dirname(application_path)), "sample_files")
    sample_files_dir = r'C:\_Data\2019\_Mowgli Testing'
    file_names = [f for f in os.listdir(sample_files_dir) if
                  os.path.isfile(os.path.join(sample_files_dir, f)) and f.lower().endswith('.pem')]
    pem_files = []

    # file = os.path.join(sample_files, file_names[0])
    for file in file_names:
        filepath = os.path.join(sample_files_dir, file)
        pem_file = parser().parse(filepath)
        print('File: ' + filepath)
        # pem_files.append((pem_file, None))  # Empty second item for ri_files
        pem_files.append(pem_file)
    # file = r'C:\_Data\2019\BMSC\Surface\MO-254\PEM\254-01NAv.PEM'
    # file = r'C:\_Data\2019\Eastern\Maritime Resources\WV-19-06\PEM\WV-19-06\WV-19-06 XYT.PEM'
    # pem_file = parser.parse(file)
    fig = plt.figure(figsize=(11, 8.5))
    pm = PlanMap(pem_files, fig, ccrs.UTM(21))
    # pm.make_plan_map(pem_files)
    # printer = PEMPrinter(sample_files_dir, pem_files)
    # printer.print_final_plots()
