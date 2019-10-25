import copy
import logging
import math
import os
import re
import sys
from datetime import datetime
from timeit import default_timer as timer
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
from matplotlib import patches
from matplotlib import patheffects
from matplotlib.backends.backend_pdf import PdfPages
from mpl_toolkits.mplot3d import Axes3D  # Needed for 3D plots
from scipy import interpolate as interp
from scipy import stats
from statistics import mean
from itertools import chain

from src.gps.gps_editor import GPSEditor
from src.pem.pem_getter import PEMGetter

__version__ = '0.1.0'
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


def natural_sort(list):
    convert = lambda text: int(text) if text.isdigit() else text.lower()
    alphanum_key = lambda key: [convert(c) for c in re.split('([0-9]+)', key)]
    return sorted(list, key=alphanum_key)


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


def format_xaxis(pem_file, component, figure, x_min, x_max):
    """
    Formats the X axis of a figure
    :param figure: LIN or LOG figure objects
    """
    component_data = list(filter(lambda d: d['Component'] == component, pem_file.data))
    component_stations = [convert_station(station['Station']) for station in component_data]
    if x_min is None:
        x_min = min(component_stations)
    if x_max is None:
        x_max = max(component_stations)
    x_label_locator = ticker.AutoLocator()
    major_locator = ticker.FixedLocator(sorted(component_stations))
    plt.xlim(x_min, x_max)
    figure.axes[0].xaxis.set_major_locator(major_locator)  # for some reason this seems to apply to all axes
    figure.axes[-1].xaxis.set_major_locator(x_label_locator)


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

        profile_data[channel] = sorted(channel_data, key=lambda x: x['Station'])

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
    f = interp.interp1d(stations, readings, kind=interp_method)

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

    plt.figtext(0.550, 0.935, f"{s_title}: {header.get('LineHole')}\n" +
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
                    ax.set_ylabel(f"Primary Pulse\n({units})")
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
        format_xaxis(pem_file, component, figure, x_min, x_max)
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
        format_xaxis(pem_file, component, figure, x_min, x_max)
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
        format_xaxis(pem_file, component, figure, x_min, x_max)
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


class PlanMap:
    def __init__(self, pem_files, figure, **kwargs):
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
        self.crs = self.get_crs(kwargs.get('CRS')) if kwargs else None #self.get_crs({'Coordinate System': 'UTM', 'Zone': '10 North', 'Datum': 'WGS 1984'})

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
                        plt.annotate(i, xy=(x, y), va='center', ha='center', fontsize=7, path_effects=label_buffer,
                                     zorder=3, color=self.color, transform=self.ax.transData)

        def add_line_to_map(pem_file):

            def get_rotation(eastings, northings):
                ang = np.arctan2(eastings[0] - eastings[-1], northings[0] - northings[-1])
                deg = np.rad2deg(ang)
                return deg

            line_gps = pem_file.get_station_coords()
            if line_gps and line_gps not in self.lines:
                self.lines.append(line_gps)
                eastings, northings = [float(coord[0]) for coord in line_gps], [float(coord[1]) for coord in line_gps]
                if self.line_labels:
                    line_label = RotnAnnotation(f"{pem_file.header.get('LineHole')}",
                                                label_xy=(float(line_gps[0][0]), float(line_gps[0][1])),
                                                p=(eastings[0], northings[0]), pa=(eastings[-1], northings[-1]),
                                                va='bottom', ha='center', color=self.color, zorder=5,
                                                path_effects=label_buffer)
                    self.labels.append(line_label)
                # marker_rotation = get_rotation(eastings, northings)
                self.station_handle, = self.ax.plot(eastings, northings, '-o', markersize=3, color=self.color,
                                                    markerfacecolor='w', markeredgewidth=0.3,
                                                    label='Surface Line', transform=self.crs, zorder=2)  # Plot the line

        def add_hole_to_map(pem_file):

            def get_borehole_projection(segments):
                if not collar:
                    return None
                else:
                    trace = [(collar_x, collar_y)]  # Easting and Northing tuples
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

            if self.draw_hole_collars is True:
                try:
                    collar = pem_file.get_collar_coords()[0]
                except IndexError:
                    return
                else:
                    collar_x, collar_y = float(collar[0]), float(collar[1])
                segments = pem_file.get_hole_geometry()
                if segments:
                    seg_x, seg_y = get_borehole_projection(segments)
                else:
                    seg_x, seg_y = None, None

                if collar and collar not in self.collars:
                    self.collars.append(collar)
                    marker_style = dict(marker='o', color='white', markeredgecolor=self.color, markersize=8)
                    self.collar_handle, = self.ax.plot(collar_x, collar_y, fillstyle='full',
                                                       label='Borehole Collar', zorder=3, **marker_style)
                    # Add the hole label at the collar
                    if self.hole_collar_labels:
                        collar_label = RotnAnnotation(f"{pem_file.header.get('LineHole')}",
                                                      label_xy=(collar_x, collar_y),
                                                      p=(seg_x[0], seg_y[0]), pa=(seg_x[1], seg_y[1]), ax=self.ax,
                                                      hole_collar=True,
                                                      va='bottom', ha='center', color=self.color, zorder=4,
                                                      path_effects=label_buffer)
                        self.labels.append(collar_label)

                    if seg_x and seg_y and self.draw_hole_traces is True:

                        # Adding the ticks on the hole trace. Both X and Y segments are interpolated first
                        f_new_x = interp.interp1d(np.linspace(0, len(seg_x), num=len(seg_x)), seg_x)
                        xx = np.linspace(0, len(seg_x), num=1000)
                        new_x = f_new_x(xx)

                        f_new_y = interp.interp1d(np.linspace(0, len(seg_y), num=len(seg_y)), seg_y)
                        yy = np.linspace(0, len(seg_y), num=1000)
                        new_y = f_new_y(yy)

                        # Plotting the actual trace
                        self.trace_handle, = self.ax.plot(new_x, new_y, '--', color=self.color, label='Borehole Trace',
                                                          zorder=2, markersize=1)

                        # Plotting the ticks
                        for x, y in zip(new_x[100::100], new_y[100::100]):
                            p = (x, y)
                            index = list(new_x).index(x)
                            pa = (new_x[index - 1], new_y[index - 1])
                            self.ax.annotate('', xy=pa, xycoords='data', xytext=p,
                                         arrowprops=dict(arrowstyle='|-|', mutation_scale=3, connectionstyle='arc3',
                                                         lw=.5))

                        # Add the end tick for the borehole trace
                        self.ax.annotate('', xy=(new_x[-1], new_y[-1]), xycoords='data', xytext=(new_x[-2], new_y[-2]),
                                     arrowprops=dict(arrowstyle='|-|', mutation_scale=5, connectionstyle='arc3',
                                                     lw=.5))

                        # Label the depth of the hole
                        if self.hole_depth_labels:
                            bh_depth = RotnAnnotation(f" {float(segments[-1][-1]):.0f} m",
                                                      label_xy=(seg_x[-1], seg_y[-1]),
                                                      p=(seg_x[-2], seg_y[-2]), pa=(seg_x[-1], seg_y[-1]), ax=self.ax,
                                                      hole_collar=True,
                                                      va='bottom', ha='left', fontsize=8, color=self.color,
                                                      path_effects=label_buffer, zorder=4)
                else:
                    pass

        for pem_file in self.pem_files:
            label_buffer = [patheffects.Stroke(linewidth=2, foreground='white'), patheffects.Normal()]

            if 'surface' in pem_file.survey_type.lower() and self.draw_lines is True:
                add_line_to_map(pem_file)

            if 'borehole' in pem_file.survey_type.lower() and self.draw_hole_collars is True:
                add_hole_to_map(pem_file)

            if self.draw_loops is True:
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

            def get_scale_factor():
                # num_digit = len(str(int(current_scale)))  # number of digits in number
                num_digit = int(np.floor(np.log10(current_scale)))  # number of digits in number
                scale_nums = [1., 1.25, 1.5, 2., 5.]
                possible_scales = [num * 10 ** num_digit for num in scale_nums+list(map(lambda x: x*10, scale_nums))]
                new_scale = min(filter(lambda x: x > current_scale * 1.30, possible_scales),
                                key=lambda x: x - current_scale * 1.30)
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
            if self.moving_loop and len(loops) > 1:
                loop_text = f"Loop: {loops[0]} to {loops[-1]}"
            else:
                loop_text = f"Loop: {', '.join(loops)}"

            hole = f"Hole: {self.pem_files[0].header.get('LineHole')}"

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
            f"{loop_text if 'surface' in self.survey_type else hole}",
                         fontname='Century Gothic', fontsize=10, va='top', ha='center', zorder=10,
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

        plt.subplots_adjust(left=0.03, bottom=0.03, right=0.97, top=0.95)
        set_size()
        set_scale()

        if self.map_grid:
            plt.grid(linestyle='dotted', zorder=0)
        self.ax.xaxis.set_visible(True)  # Required to actually get the labels to show in UTM
        self.ax.yaxis.set_visible(True)
        self.ax.set_yticklabels(self.ax.get_yticklabels(), rotation=90, ha='center')
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
        if any([self.loops, self.lines, self.collars, self.holes]):
            self.format_figure()
            return self.fig
        else:
            return None


class SectionPlot:
    def __init__(self, pem_file, figure, **kwargs):
        self.color = 'black'
        self.fig = figure
        self.pem_file = pem_file
        self.gps_editor = GPSEditor()

        self.loop_coords = [[float(num) for num in row] for row in self.pem_file.get_loop_coords()]
        self.collar = self.pem_file.get_collar_coords()[0]
        self.segments = self.pem_file.get_hole_geometry()
        self.current = float(self.pem_file.tags.get('Current'))
        self.survey_type = pem_files[0].survey_type.lower()
        self.timebase = [pem_files[0].header.get('Timebase')]

        self.ax = self.fig.add_subplot(111, projection='3d')
        self.plot_trace()
        self.plot_loop()
        self.plot_magnetic_field()

    def get_extents(self):
        min_x = min([float(row[0]) for row in self.loop_coords] + [float(self.collar[0])])
        max_x = max([float(row[0]) for row in self.loop_coords] + [float(self.collar[0])])
        min_y = min([float(row[1]) for row in self.loop_coords] + [float(self.collar[1])])
        max_y = max([float(row[1]) for row in self.loop_coords] + [float(self.collar[1])])
        min_z = min([float(row[2]) for row in self.loop_coords] + [float(self.collar[2])] + [float(self.segments[-1][4])])
        max_z = max([float(row[2]) for row in self.loop_coords] + [float(self.collar[2])] + [float(self.segments[-1][4])])
        return min_x, max_x, min_y, max_y, min_z, max_z

    def calc_total_field(self, Px, Py, Pz, I):
        """
        Calculate the magnetic field at position P with current I using Biot-Savart Law. Geometry used is the loop.
        :param P: Position at which the magnetic field is calculated
        :param I: Current used
        :return: Magnetic field strength
        """

        def get_magnitude(vector):
            return math.sqrt(sum(i ** 2 for i in vector))

        def scale_vectors(vector, factor):
            """
            :param vector: List or Tuple
            :param factor: Float or Int
            :return: Scaled vector
            """
            newvector = list(map(lambda x: x * factor, vector))
            return newvector

        mag_const = 4 * math.pi * 10 ** -7
        integral_sum = [0, 0, 0]

        for i, point in enumerate(self.loop_coords):
            l = [point[0] - self.loop_coords[i - 1][0],
                 point[1] - self.loop_coords[i - 1][1],
                 point[2] - self.loop_coords[i - 1][2]]
            AP = [Px - self.loop_coords[i - 1][0], Py - self.loop_coords[i - 1][1],
                  Pz - self.loop_coords[i - 1][2]]
            BP = [Px - self.loop_coords[i][0], Py - self.loop_coords[i][1], Pz - self.loop_coords[i][2]]
            r1 = get_magnitude(AP)
            r2 = get_magnitude(BP)
            Dot1 = np.dot(l, AP)
            Dot2 = np.dot(l, BP)
            cross = np.cross(l, AP).tolist()
            CrossSqrd = get_magnitude(cross) ** 2
            factor = (Dot1 / r1 - Dot2 / r2) * mag_const * I / (CrossSqrd * 4 * math.pi)
            term = scale_vectors(cross, factor)
            integral_sum = [integral_sum[0] + term[0],
                            integral_sum[1] + term[1],
                            integral_sum[2] + term[2]]
        unit = 'nT' if 'induction' in self.pem_file.survey_type.lower() else 'pT'
        if unit == 'pT':
            field = scale_vectors(integral_sum, 1e12)
        elif unit == 'nT':
            field = scale_vectors(integral_sum, 1e9)
        return field[0], field[1], field[2]

    def plot_loop(self):
        xs = [row[0] for row in self.loop_coords] + [self.loop_coords[0][0]]
        ys = [row[1] for row in self.loop_coords] + [self.loop_coords[0][1]]
        zs = [row[2] for row in self.loop_coords] + [self.loop_coords[0][2]]

        self.ax.plot(xs, ys, zs, color='black')

    def plot_trace(self):

        def get_3D_borehole_projection(segments):
            if not self.collar:
                return None
            else:
                collar_x, collar_y, collar_z = float(self.collar[0]), float(self.collar[1]), float(self.collar[2])
                trace = [(collar_x, collar_y, collar_z)]  # Easting and Northing tuples
                azimuth = None
                for segment in segments:
                    azimuth = math.radians(float(segment[0]))
                    dip = math.radians(float(segment[1]))
                    seg_l = float(segment[2])
                    delta_seg_l = seg_l * math.cos(dip)
                    delta_elev = seg_l * math.sin(dip)
                    dx = delta_seg_l * math.sin(azimuth)
                    dy = delta_seg_l * math.cos(azimuth)
                    trace.append((float(trace[-1][0]) + dx, float(trace[-1][1]) + dy, float(trace[-1][2]) - delta_elev))
                return [segment[0] for segment in trace], \
                       [segment[1] for segment in trace], \
                       [segment[2] for segment in trace]

        def get_section_extents(trace):
            seg_center = None

        seg_x, seg_y, seg_z = get_3D_borehole_projection(self.segments)
        # x, y = get_section_extents(trace)
        self.ax.plot(seg_x, seg_y, seg_z, linewidth=1)

        # plt.plot(trace_x, trace_y)

    def plot_magnetic_field(self, buffer=0):

        min_x, max_x, min_y, max_y, min_z, max_z = self.get_extents()
        rows = 8.
        x = np.arange(min_x - buffer, max_x + buffer, (max_x - min_x) * 1/rows)
        y = np.arange(min_y - buffer, max_y + buffer, (max_y - min_y) * 1/rows)
        z = np.arange(min_z/1.25 - buffer, max_z + buffer, (max_z - min_z) * 1/rows)

        arrowlength = (16.)

        xx, yy, zz = np.meshgrid(x, y, z)

        vField = np.vectorize(self.calc_total_field)

        print('Computing Field at {} points.....'.format(xx.size))
        start = timer()

        u, v, w = vField(xx, yy, zz, self.current)

        end = timer()
        time = round(end - start, 2)
        print('Calculated in {} seconds'.format(str(time)))

        self.ax.quiver(xx, yy, zz, u, v, w, length=arrowlength, normalize=True,
                      color='magenta', label='Field', linewidth=.5, alpha=1,
                      arrow_length_ratio=.6, pivot='middle', zorder=3)

    def get_map(self):
        plt.show()


class Map3D:
    """
    Class that plots all GPS from PEM Files in 3D. Draws on a given Axes3D object.
    """
    def __init__(self, ax, pem_files, parent=None):
        self.parent = parent
        self.pem_files = pem_files
        self.ax = ax
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
        self.segments = []
        self.hole_artists = []
        self.hole_label_artists = []
        self.buffer = [patheffects.Stroke(linewidth=2, foreground='white'), patheffects.Normal()]

        self.plot_pems()

    def plot_pems(self):

        def plot_loop(pem_file):
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

        def plot_line(pem_file):
            line_coords = pem_file.get_line_coords()
            if line_coords:
                line = [[float(num) for num in row] for row in line_coords]
                if line not in self.lines:
                    self.lines.append(line_coords)
                    x, y, z = [r[0] for r in line], \
                              [r[1] for r in line], \
                              [r[2] for r in line]
                    line_artist, = self.ax.plot(x, y, z, '-o', lw=1,
                                 markersize=3, color='black', markerfacecolor = 'w', markeredgewidth = 0.3)
                    self.line_artists.append(line_artist)
                    line_name = pem_file.header.get('LineHole')
                    line_end = line[-1]
                    line_label_artist = self.ax.text(line_end[0], line_end[1], line_end[2], line_name, ha='center',
                                                     va='bottom')
                    self.line_label_artists.append(line_label_artist)

                    for station in line:
                        station_label_artist = self.ax.text(station[0], station[1], station[2], f"{station[-1]:.0f}",
                                     path_effects=self.buffer, ha='center', va='bottom')
                        self.station_label_artists.append(station_label_artist)

        def plot_hole(pem_file):

            def get_3D_borehole_projection(collar_gps, segments):
                if not collar_gps:
                    return None
                else:
                    collar_x, collar_y, collar_z = collar_gps[0], collar_gps[1], collar_gps[2]
                    trace = [(collar_x, collar_y, collar_z)]  # Easting and Northing tuples
                    azimuth = None
                    for segment in segments:
                        azimuth = math.radians(float(segment[0]))
                        dip = math.radians(float(segment[1]))
                        seg_l = float(segment[2])
                        delta_seg_l = seg_l * math.cos(dip)
                        delta_elev = seg_l * math.sin(dip)
                        dx = delta_seg_l * math.sin(azimuth)
                        dy = delta_seg_l * math.cos(azimuth)
                        trace.append(
                            (float(trace[-1][0]) + dx, float(trace[-1][1]) + dy, float(trace[-1][2]) - delta_elev))
                    return [segment[0] for segment in trace], \
                           [segment[1] for segment in trace], \
                           [segment[2] for segment in trace]

            collar_gps = pem_file.get_collar_coords()
            segments = pem_file.get_hole_geometry()
            if collar_gps and segments and segments not in self.segments:
                self.segments.append(segments)

                collar_gps = [[float(num) for num in row] for row in collar_gps]
                segments = [[float(num) for num in row] for row in segments]

                xx, yy, zz = get_3D_borehole_projection(collar_gps[0], segments)
                hole_artist, = self.ax.plot(xx, yy, zz, '--', lw=1, color='darkred')
                self.hole_artists.append(hole_artist)

                name = pem_file.header.get('LineHole')
                hole_label_artist = self.ax.text(collar_gps[0][0], collar_gps[0][1], collar_gps[0][2], str(name),
                                                 path_effects=self.buffer, ha='center', va='bottom', color='darkred')
                self.hole_label_artists.append(hole_label_artist)

        for pem_file in self.pem_files:
            survey_type = pem_file.survey_type.lower()

            plot_loop(pem_file)
            if 'surface' in survey_type:
                plot_line(pem_file)
            if 'borehole' in survey_type:
                plot_hole(pem_file)

        self.format_ax()

    def format_ax(self):

        def set_z_limits():
            min_x, max_x = self.ax.get_xlim()
            min_y, max_y = self.ax.get_ylim()
            min_z, max_z = self.ax.get_zlim()

            x_extent, y_extent, z_extent = max_x-min_x,  max_y-min_y,  max_z-min_z
            new_z_extent = max(x_extent, y_extent, z_extent)
            mid_z = min_z + (abs(max_z - min_z) / 2)
            new_z_min, new_z_max = mid_z - (new_z_extent/2), mid_z + (new_z_extent/2)
            self.ax.set_zlim([new_z_min, new_z_max])

        set_z_limits()
        self.ax.set_xlabel('Easting')
        self.ax.set_ylabel('Northing')
        self.ax.set_zlabel('Elevation')


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
        self.kwargs = kwargs
        self.save_path = save_path
        self.x_min = kwargs.get('XMin')
        self.x_max = kwargs.get('XMax')
        self.hide_gaps = kwargs.get('HideGaps')
        self.crs = kwargs.get('CRS')
        self.pb = QProgressBar()
        self.pb_count = 0
        self.pb_end = sum([len(pair[0].get_components()) for pair in self.files])
        self.pb.setValue(0)

    def sort_files(self):

        def atoi(text):
            return int(text) if text.isdigit() else text

        def natural_keys(text):
            '''
            alist.sort(key=natural_keys) sorts in human order
            http://nedbatchelder.com/blog/200712/human_sorting.html
            '''
            return [atoi(c) for c in re.split(r'(\d+)', text)]

        self.files.sort(key=lambda x: x[0].get_components(), reverse=True)
        self.files.sort(key=lambda x: natural_keys(x[0].header['LineHole']))

        self.pem_files = [pair[0] for pair in self.files]
        self.ri_files = [pair[1] for pair in self.files]

    def create_plan_figure(self):
        """
        Creates an empty but formatted Plan figure
        :return: Figure object
        """
        fig = plt.figure(figsize=(11, 8.5))
        return fig

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
        if all([self.crs.get('Coordinate System'), self.crs.get('Datum')]):
            with PdfPages(self.save_path + '.PDF') as pdf:
                plan_figure = self.create_plan_figure()
                plan_map = PlanMap(self.pem_files, plan_figure, **self.kwargs)
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
            if all([self.crs.get('Coordinate System'), self.crs.get('Datum')]):
                # Saving the Plan Map
                map_figure = self.create_plan_figure()
                plan_map = PlanMap(self.pem_files, map_figure, **self.kwargs)
                pdf.savefig(plan_map.get_map(), orientation='landscape')
                self.pb_count += 1
                self.pb.setValue(int((self.pb_count / self.pb_end) * 100))
                plt.close(map_figure)

            # Saving the LIN plots
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

            # Saving the LOG plots
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

            # Saving the STEP plots
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
    pem_getter = PEMGetter()
    pem_files = pem_getter.get_pems()
    fig = plt.figure(figsize=(11, 8.5))
    # sm = SectionPlot(pem_files[0], fig)
    # map = sm.get_map()
    map = Map3D(fig)
    map.plot_pems(pem_files)
    plt.show()
    # printer = PEMPrinter(sample_files_dir, pem_files)
    # printer.print_final_plots()
