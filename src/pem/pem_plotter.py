import itertools
import logging
# import cartopy.crs as ccrs  # import projections
# import cartopy.io.img_tiles as cimgt
# import cartopy.io.shapereader as shpreader
# from cartopy import feature
# from cartopy.mpl.gridliner import LONGITUDE_FORMATTER, LATITUDE_FORMATTER
import math
import os
import re
import sys
import warnings
from collections import defaultdict
from datetime import datetime

import matplotlib as mpl
import matplotlib.pyplot as plt
import natsort
import numpy as np
import pyqtgraph as pg
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib import patheffects, patches, ticker, text, transforms, lines
from scipy import stats

from src.qt_py import CustomProgressDialog, set_ax_size
from src.mag_field.mag_field_calculator import MagneticFieldCalculator
from src.pem import convert_station
from src.pem.pem_file import PEMParser, PEMGetter
from src.qt_py.ri_importer import RIFile

logger = logging.getLogger(__name__)

mpl.rcParams['path.simplify'] = True
mpl.rcParams['path.simplify_threshold'] = 1.0
mpl.rcParams['agg.path.chunksize'] = 10000
mpl.rcParams["figure.autolayout"] = False
mpl.rcParams['lines.linewidth'] = 0.5
# mpl.rcParams['lines.color'] = '#1B2631'
mpl.rcParams['font.size'] = 9

warnings.filterwarnings("ignore", category=DeprecationWarning)
line_color = 'black'


class ProfilePlotter:
    """
    Base class for plotting LIN, LOG, and STEP plots
    :param pem_file: PEMFile object, file to plot
    :param figure: Matplotlib Figure object to plot on and return
    :param x_min: int, left-side x limit. If none is given it will be calculated from the data.
    :param x_max: int, right-side x limit. If none is given it will be calculated from the data.
    :param hide_gaps: bool, to hide plotted lines where there are gaps in the data
    :return: Matplotlib Figure object
    """
    def __init__(self, pem_file, figure, x_min=None, x_max=None, hide_gaps=True):
        if isinstance(pem_file, str) and os.path.isfile(pem_file):
            pem_file = PEMParser().parse(pem_file)

        if not pem_file.is_averaged():
            pem_file = pem_file.average()
        if not pem_file.is_split():
            pem_file = pem_file.split()

        self.pem_file = pem_file
        self.figure = figure

        self.x_min = x_min
        self.x_max = x_max
        self.hide_gaps = hide_gaps
        self.linewidth = 0.5

    def format_figure(self, component):
        """
        Formats a figure, mainly the spines, adjusting the padding, and adding the rectangle.
        """
        def add_rectangle():
            """
            Add the surrounding rectangle
            """
            rect = patches.Rectangle(xy=(0.02, 0.02),
                                         width=0.96,
                                         height=0.96,
                                         linewidth=0.7,
                                         edgecolor='black',
                                         facecolor='none',
                                         transform=self.figure.transFigure)
            self.figure.patches.append(rect)

        def format_title(component):
            """
            Adds the title header to a figure
            """
            survey_type = self.pem_file.get_survey_type()
            if self.pem_file.timebase == 16.66:
                timebase_freq = 15.00
            elif self.pem_file.timebase == 8.33:
                timebase_freq = 30.00
            else:
                timebase_freq = ((1 / (self.pem_file.timebase / 1000)) / 4)

            s_title = 'Hole' if self.pem_file.is_borehole() else 'Line'

            plt.figtext(0.550, 0.960, 'Crone Geophysics & Exploration Ltd.',
                        fontname='Century Gothic',
                        fontsize=11,
                        ha='center')

            plt.figtext(0.550, 0.945, f"{survey_type} Pulse EM Survey",
                        family='cursive',
                        style='italic',
                        fontname='Century Gothic',
                        fontsize=10,
                        ha='center')

            plt.figtext(0.145, 0.935, f"Timebase: {self.pem_file.timebase:.2f} ms\n" +
                        f"Base Frequency: {str(round(timebase_freq, 2))} Hz\n" +
                        f"Current: {self.pem_file.current:.1f} A",
                        fontname='Century Gothic',
                        fontsize=10,
                        va='top')

            # if borehole is True:
            #     if component == 'Z':
            #         comp_str = 'Z Component (axial; +ve up hole)'
            #     elif component == 'X':
            #         comp_str = 'X Component (crosswise; +ve along azimuth)'
            #     else:
            #         comp_str = 'Y Component (crosswise; +ve left of azimuth)'
            # else:
            #     if component == 'Z':
            #         comp_str = 'Z-Component (+ve up)'
            #     elif component == 'X':
            #         comp_str = 'X-Component (+ve grid north)'
            #     else:
            #         comp_str = 'Y-Component (+ve grid west)'

            plt.figtext(0.550, 0.935, f"{s_title}: {self.pem_file.line_name}\n" +
                        f"Loop: {self.pem_file.loop_name}\n" +
                        f"{component.upper()} Component",
                        fontname='Century Gothic',
                        fontsize=10,
                        va='top',
                        ha='center')

            plt.figtext(0.955, 0.935, f"{self.pem_file.client}\n" +
                        f"{self.pem_file.grid}\n" +
                        f"{self.pem_file.date}\n",
                        fontname='Century Gothic',
                        fontsize=10,
                        va='top',
                        ha='right')

        def format_xaxis(component):
            """
            Formats the X axis of a figure, setting the limits and adding the tick labels
            :param component: str, 'X', 'Y', or 'Z'
            :param x_min: float, manually set the minimum x limit
            :param x_max: float, manually set the maximum x limit
            """
            filt = self.pem_file.data['Component'] == component.upper()
            component_data = self.pem_file.data.loc[filt]
            component_stations = component_data['Station'].map(convert_station).unique()
            if self.x_min is None:
                self.x_min = component_stations.min()
            if self.x_max is None:
                self.x_max = component_stations.max()

            x_label_locator = ticker.AutoLocator()
            major_locator = ticker.FixedLocator(sorted(component_stations))
            plt.xlim(self.x_min, self.x_max)
            # for some reason this seems to apply to all axes
            self.figure.axes[0].xaxis.set_major_locator(major_locator)
            self.figure.axes[-1].xaxis.set_major_locator(x_label_locator)

        def format_yaxis():
            """
            Formats the Y axis of a figure. Will increase the limits of the scale if depending on the limits of the data.
            """
            axes = self.figure.axes[:-1]

            for ax in axes:
                ax.get_yaxis().set_label_coords(-0.08, 0.5)

                if ax.get_yscale() != 'symlog':
                    y_limits = ax.get_ylim()

                    if not self.pem_file.is_fluxgate():
                        if y_limits[1] < 3 or y_limits[0] > -3:
                            new_high = math.ceil(max(y_limits[1] + 1, 0))
                            new_low = math.floor(min(y_limits[0] - 1, 0))
                        else:
                            new_high = math.ceil(max(y_limits[1], 0))
                            new_low = math.floor(min(y_limits[0], 0))
                    else:
                        if y_limits[1] < 6 or y_limits[0] > -6:
                            new_high = math.ceil(max(y_limits[1] + 3, 0))
                            new_low = math.floor(min(y_limits[0] - 3, 0))
                        else:
                            new_high = math.ceil(max(y_limits[1], 0))
                            new_low = math.floor(min(y_limits[0], 0))

                    ax.set_ylim(new_low, new_high)
                    ax.yaxis.set_major_locator(ticker.MaxNLocator(nbins='auto', integer=True, steps=[1, 2, 5, 10]))
                    ax.set_yticks(ax.get_yticks())
                    # ax.yaxis.set_major_locator(ticker.AutoLocator())
                    # ax.set_yticks(ax.get_yticks())  # This is used twice to avoid half-integer tick values

                elif ax.get_yscale() == 'symlog':
                    y_limits = ax.get_ylim()
                    new_high = 10.0 ** math.ceil(math.log(max(y_limits[1], 11), 10))
                    new_low = -1 * 10.0 ** math.ceil(math.log(max(abs(y_limits[0]), 11), 10))
                    ax.set_ylim(new_low, new_high)

                    ax.tick_params(axis='y', which='major', labelrotation=90)
                    plt.setp(ax.get_yticklabels(), va='center')

                ax.yaxis.set_major_formatter(ticker.FormatStrFormatter('%d'))  # Prevent scientific notation

        def format_spines(ax):
            ax.spines['right'].set_visible(False)
            ax.spines['top'].set_visible(False)

            if ax != self.figure.axes[-1]:
                ax.spines['bottom'].set_position(('data', 0))
                ax.tick_params(axis='x', which='major', direction='inout', length=4)
                plt.setp(ax.get_xticklabels(), visible=False)
            else:
                ax.spines['bottom'].set_visible(False)
                ax.xaxis.set_ticks_position('bottom')
                ax.tick_params(axis='x', which='major', direction='out', length=6)
                plt.setp(ax.get_xticklabels(), visible=True, size=12, fontname='Century Gothic')

        add_rectangle()
        format_title(component)
        format_xaxis(component)
        format_yaxis()
        for ax in self.figure.axes:
            format_spines(ax)

    def get_interp_data(self, x, y):
        """
        Interpolate the data into 1000 segments. Can be increasing or decreasing X values.
        :param x: arr, base X values
        :param y: arr, base Y values
        :return: arr tuple, interpolated X and Y arrays with gaps masked if enabled
        """
        def mask_gaps(interp_y, interp_x, stations, gap=None):
            """
            Mask an array in data gaps so it is not plotted by Matplotlib
            :param interp_y: np.array, interpolated Y values
            :param interp_x: np.array, interpolated X values
            :param stations: np.array, stations (converted to ints)
            :param gap: optional int, minimum gap size to trigger the mask
            :return: np.array tuple,  interpolated Y and interpolated X values with data inside of gaps masked
            """
            # min_gap = 50 if self.pem_file.is_borehole() else 200
            min_gap = int(.2 * (stations.max() - stations.min()))
            station_gaps = np.diff(stations)

            if gap is None:
                # Use double the mode of the station spacing as the gap, or the min_gap, whichever is larger
                gap = max(stats.mode(station_gaps)[0] * 2, min_gap)

            gap_intervals = [(stations[i], stations[i + 1]) for i in range(len(stations) - 1) if station_gaps[i] > gap]

            # Masks the intervals that are between gap[0] and gap[1]
            for gap in gap_intervals:
                interp_y = np.ma.masked_where((interp_x > gap[0]) & (interp_x < gap[1]), interp_y)
                interp_x = np.ma.masked_where((interp_x > gap[0]) & (interp_x < gap[1]), interp_x)

            # Causes the mask to still be plotted.
            # Apply the mask
            # mask = np.isclose(interp_y, interp_y.astype('float64'))
            # interp_x = interp_x[mask]
            # interp_y = interp_y[mask]

            return interp_x, interp_y

        # Interpolate the x and y data
        interp_x = np.linspace(x[0], x[-1] + 1, num=1000)

        # Check that the stations are monotonically increasing.
        if np.all(interp_x[1:] >= interp_x[:-1], axis=0):
            interp_y = np.interp(interp_x, x, y)
        else:
            # If it is not increasing, flip the X array
            interp_y = np.interp(np.flip(interp_x), np.flip(x), y)  # Output is the correct orientation

        # Mask the data in gaps
        if self.hide_gaps:
            interp_x, interp_y = mask_gaps(interp_y, interp_x, x)

        return interp_x, interp_y

    @staticmethod
    def annotate_line(ax, annotation, interp_x, interp_y, offset):
        for i, x_position in enumerate(interp_x[int(offset)::int(len(interp_x) * 0.4)]):
            y = interp_y[list(interp_x).index(x_position)]

            ax.annotate(str(annotation),
                        xy=(x_position, y),
                        xycoords="data",
                        size=7.5,
                        va='center_baseline',
                        ha='center',
                        color=line_color)


class LINPlotter(ProfilePlotter):
    """
     Plots the data into the LIN figure
     :param pem_file: PEMFile object, file to plot
     :param figure: Matplotlib Figure object to plot on and return
     :param x_min: int, left-side x limit. If none is given it will be calculated from the data.
     :param x_max: int, right-side x limit. If none is given it will be calculated from the data.
     :param hide_gaps: bool, to hide plotted lines where there are gaps in the data
     :return: Matplotlib Figure object
     """

    def __init__(self, pem_file, figure, x_min=None, x_max=None, hide_gaps=True):
        super().__init__(pem_file, figure, x_min=x_min, x_max=x_max, hide_gaps=hide_gaps)
        self.figure.subplots_adjust(left=0.135, bottom=0.07, right=0.958, top=0.885)

    def plot(self, component):
        def add_ylabels():
            if self.pem_file.is_fluxgate():
                if float(self.pem_file.current) == 1.:
                    units = "pT/A"
                else:
                    units = "pT"
            else:
                units = 'nT/s'
            for i, ax in enumerate(self.figure.axes[:-1]):
                if i == 0:
                    ax.set_ylabel(f"Primary Pulse\n({units})")
                else:
                    ax.set_ylabel(f"Channel {channel_bounds[i][0]} - {channel_bounds[i][1]}\n({units})")

        logger.info(f"Plotting LIN for {self.pem_file.filepath.name}, {component} component.")
        profile = self.pem_file.get_profile_data(component, converted=True)
        channel_bounds = self.pem_file.get_channel_bounds()
        for i, group in enumerate(channel_bounds):
            # Starting offset used for channel annotations
            offset = 100
            ax = self.figure.axes[i]

            for ch in range(group[0], group[1] + 1):
                stations = profile.index.values
                data = profile.loc[:, ch].to_numpy()

                # Interpolate the X and Y data and mask gaps
                interp_stations, interp_data = self.get_interp_data(stations, data)

                # Plot the data
                ax.plot(interp_stations, interp_data, color=line_color, linewidth=self.linewidth)

                # Annotate the lines
                self.annotate_line(ax, 'PP' if ch == 0 else str(ch), interp_stations, interp_data, offset)

                # Increase the offset for the next annotation
                offset += len(interp_stations) * 0.15

                # Reset the offset when it reaches 85%
                if offset >= len(interp_stations) * 0.85:
                    offset = len(interp_stations) * 0.10

        add_ylabels()
        self.format_figure(component)
        return self.figure


class LOGPlotter(ProfilePlotter):
    """
     Plots the data into the LOG figure
     :param pem_file: PEMFile object, file to plot
     :param figure: Matplotlib Figure object to plot on and return
     :param x_min: int, left-side x limit. If none is given it will be calculated from the data.
     :param x_max: int, right-side x limit. If none is given it will be calculated from the data.
     :param hide_gaps: bool, to hide plotted lines where there are gaps in the data
     :return: Matplotlib Figure object
     """

    def __init__(self, pem_file, figure, x_min=None, x_max=None, hide_gaps=True):
        super().__init__(pem_file, figure, x_min=x_min, x_max=x_max, hide_gaps=hide_gaps)
        self.figure.subplots_adjust(left=0.135, bottom=0.07, right=0.958, top=0.885)

    def plot(self, component):

        def add_ylabels():
            if self.pem_file.is_fluxgate():
                if float(self.pem_file.current) == 1.:
                    units = "pT/A"
                else:
                    units = "pT"
            else:
                units = 'nT/s'
            ax.set_ylabel(f"Primary Pulse to Channel {self.pem_file.number_of_channels - 1}\n({units})")

        logger.info(f"Plotting LOG for {self.pem_file.filepath.name}, {component} component.")
        ax = self.figure.axes[0]
        # Starting offset used for channel annotations
        offset = 100
        profile = self.pem_file.get_profile_data(component, converted=True)

        for ch in range(self.pem_file.number_of_channels):
            stations = profile.index.values
            data = profile.loc[:, ch].to_numpy()

            # Interpolate the X and Y data and mask gaps
            interp_stations, interp_data = self.get_interp_data(stations, data)

            # Plot the data
            ax.plot(interp_stations, interp_data, color=line_color, linewidth=self.linewidth)

            # Annotate the lines
            self.annotate_line(ax, 'PP' if ch == 0 else str(ch), interp_stations, interp_data, offset)

            # Increase the offset for the next annotation
            offset += len(interp_stations) * 0.15

            # Reset the offset when it reaches 85%
            if offset >= len(interp_stations) * 0.85:
                offset = len(interp_stations) * 0.10

        add_ylabels()
        self.format_figure(component)
        return self.figure


class STEPPlotter(ProfilePlotter):
    """
     Plots the RI and PEM data into the step figure
     :param pem_file: PEMFile object, file to plot
     :param ri_file: RIFile object, file to plot
     :param figure: Matplotlib Figure object to plot on and return
     :param x_min: int, left-side x limit. If none is given it will be calculated from the data.
     :param x_max: int, right-side x limit. If none is given it will be calculated from the data.
     :param hide_gaps: bool, to hide plotted lines where there are gaps in the data
     :return: Matplotlib Figure object
     """

    def __init__(self, pem_file, ri_file, figure, x_min=None, x_max=None, hide_gaps=True):
        super().__init__(pem_file, figure, x_min=x_min, x_max=x_max, hide_gaps=hide_gaps)
        if isinstance(ri_file, str) and os.path.isfile(ri_file):
            ri_file = RIFile().open(ri_file)
        self.ri_file = ri_file
        self.figure.subplots_adjust(left=0.170, bottom=0.07, right=0.958, top=0.885)

    def format_yaxis(self):
        """
        Formats the Y axis of a figure. Will increase the limits of the scale if depending on the limits of the data.
        """
        axes = self.figure.axes[:-1]

        for ax in axes:
            ax.get_yaxis().set_label_coords(-0.095, 0.5)
            y_limits = ax.get_ylim()

            # Set the limits for fluxgate survey
            if self.pem_file.is_fluxgate():
                if ax == axes[1] and (y_limits[1] < 15 or y_limits[0] > -15):
                    new_high = math.ceil(max(y_limits[1] + 10, 0))
                    new_low = math.floor(min(y_limits[0] - 10, 0))
                elif ax == axes[2] and (y_limits[1] < 3 or y_limits[0] > -3):
                    new_high = math.ceil(max(y_limits[1] + 1, 0))
                    new_low = math.floor(min(y_limits[0] - 1, 0))
                elif ax == axes[3] and (y_limits[1] < 30 or y_limits[0] > -30):
                    new_high = math.ceil(max(y_limits[1] + 10, 0))
                    new_low = math.floor(min(y_limits[0] - 10, 0))
                else:
                    new_high = math.ceil(max(y_limits[1], 0))
                    new_low = math.floor(min(y_limits[0], 0))
            # Set the limits for induction survey
            else:
                if ax == axes[1] and (y_limits[1] < 15 or y_limits[0] > -15):
                    new_high = math.ceil(max(y_limits[1] + 10, 0))
                    new_low = math.floor(min(y_limits[0] - 10, 0))
                elif ax in axes[2:4] and (y_limits[1] < 3 or y_limits[0] > -3):
                    new_high = math.ceil(max(y_limits[1] + 1, 0))
                    new_low = math.floor(min(y_limits[0] - 1, 0))
                else:
                    new_high = math.ceil(max(y_limits[1], 0))
                    new_low = math.floor(min(y_limits[0], 0))

            ax.set_ylim(new_low, new_high)
            ax.yaxis.set_major_locator(ticker.MaxNLocator(nbins='auto', integer=True, steps=[1, 2, 5, 10]))
            ax.set_yticks(ax.get_yticks())
            # ax.yaxis.set_major_locator(ticker.AutoLocator())
            # ax.set_yticks(ax.get_yticks())  # This is used twice to avoid half-integer tick values

            ax.yaxis.set_major_formatter(ticker.FormatStrFormatter('%d'))  # Prevent scientific notation

    def plot(self, component):

        def add_ylabel():
            units = 'pT' if self.pem_file.is_fluxgate() else 'nT/s'
            channels = [re.findall('\d+', key)[0] for key in ri_profile if re.match('Ch', key)]

            self.figure.axes[0].set_ylabel("TP = Theoretical Primary\n"
                                           f"{'PP = Calculated PP x Ramp' if self.pem_file.is_fluxgate() else 'PP = Last Ramp Channel'}\n"
                                           f"S1 = Calculated Step Ch.1\n({units})")
            self.figure.axes[1].set_ylabel("Deviation from TP\n"
                                           "(% Total Theoretical)")
            self.figure.axes[2].set_ylabel("Step Channels 2 - 4\n"
                                           "Deviation from S1\n"
                                           "(% Total Theoretical)")
            self.figure.axes[3].set_ylabel("Pulse EM Off-time\n"
                                           f"Channels {min(channels[-num_channels_to_plot:])} - "
                                           f"{max(channels[-num_channels_to_plot:])}\n"
                                           f"({units})")

        def plot_ri_lines():
            """
            Plot the lines for step plots made from RI files.
            """
            offset = 100  # Used for spacing the annotations
            keys = ['Theoretical PP', 'Measured PP', 'S1', '(M-T)*100/Tot', '(S1-T)*100/Tot', '(S2-S1)*100/Tot', 'S3%',
                    'S4%']
            annotations = ['TP', 'PP', 'S1', 'PP', 'S1', 'S2', 'S3', 'S4']
            # stations = np.array(ri_profile['Stations'], dtype=int)

            for i, key in enumerate(keys):
                interp_stations, interp_data = self.get_interp_data(stations, ri_profile[key])

                if i < 3:  # Plotting TP, PP, and S1 to the first axes
                    ax = self.figure.axes[0]
                    ax.plot(interp_stations, interp_data, color=line_color, linewidth=self.linewidth)
                    self.annotate_line(ax, annotations[i], interp_stations, interp_data, offset)
                    offset += len(interp_stations) * 0.15
                elif i < 5:  # Plotting the PP and S1% to the second axes
                    if i == 3:  # Resetting the annotation positions
                        offset = 100
                    ax = self.figure.axes[1]
                    ax.plot(interp_stations, interp_data, color=line_color, linewidth=self.linewidth)
                    self.annotate_line(ax, annotations[i], interp_stations, interp_data, offset)
                    offset += len(interp_stations) * 0.15
                else:  # Plotting S2% to S4% to the third axes
                    if i == 5:
                        offset = 100
                    ax = self.figure.axes[2]
                    ax.plot(interp_stations, interp_data, color=line_color, linewidth=self.linewidth)
                    self.annotate_line(ax, annotations[i], interp_stations, interp_data, offset)
                    offset += len(interp_stations) * 0.15

                if offset >= len(interp_stations) * 0.85:
                    offset = len(interp_stations) * 0.10

        def plot_offtime_lines():
            """
            Plot the off-time PEM data
            """
            offset = 100
            # Plotting the off-time channels to the fourth axes
            for i, data in enumerate(off_time_channel_data[-num_channels_to_plot:]):
                x_intervals, interp_data = self.get_interp_data(stations, data)
                ax = self.figure.axes[3]
                ax.plot(x_intervals, interp_data, color=line_color, linewidth=self.linewidth)
                self.annotate_line(ax, str(num_off_time_channels - num_channels_to_plot + i + 1),
                                   x_intervals,
                                   interp_data,
                                   offset)
                offset += len(x_intervals) * 0.15
                if offset >= len(x_intervals) * 0.85:
                    offset = len(x_intervals) * 0.10

        logger.info(f"Plotting Step for {self.pem_file.filepath.name}, {component} component.")
        ri_profile = self.ri_file.get_ri_profile(component)
        off_time_channel_data = [ri_profile[key] for key in ri_profile if re.match('Ch', key)]
        num_off_time_channels = len(off_time_channel_data) + 10
        num_channels_to_plot = round(num_off_time_channels / 4)
        stations = np.array(ri_profile['Stations'], dtype=int)

        plot_ri_lines()
        plot_offtime_lines()

        add_ylabel()
        self.format_figure(component)

        # Fix the Y axis scaling for the second plot
        ax = self.figure.axes[1]
        y_limits = ax.get_ylim()
        if y_limits[1] < 10 or y_limits[0] > -10:
            new_high = math.ceil(max(y_limits[1] + 6, 0))
            new_low = math.floor(min(y_limits[0] - 6, 0))
            ax.set_ylim(new_low, new_high)
            ax.yaxis.set_major_locator(ticker.MaxNLocator(nbins='auto', integer=True, steps=[1, 2, 5, 10]))
            ax.set_yticks(ax.get_yticks())

        return self.figure


class RotnAnnotation(text.Annotation):
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

        text.Annotation.__init__(self, label_str, label_xy, **kwargs)
        self.set_transform(transforms.IdentityTransform())
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


class MapPlotter:
    """
    Base class for plotting PEM file GPS on maps
    """
    def __init__(self):
        pass

    def plot_loop(self, pem_file, figure, annotate=True, label=True, color='black', buffer_color="white", zorder=6,
                  is_mmr=False):
        """
        Plot the loop GPS of a pem_file.
        :param pem_file: PEMFile object
        :param figure: Matplotlib Figure object to plot on
        :param annotate: bool, add L-tag annotations
        :param label: bool, add loop label
        :param color: str, line color
        :param zorder: int, order in which to draw the object (higher number draws it on top of lower numbers)
        :param is_mmr: bool, whether or not to join the first and last points of the loop coordinates
        :return: loop_handle for legend
        """
        def get_label_pos(collar, loop):
            """
            Find the best quadrant to place the loop label to avoid the hole labels.
            :param collar: CollarGPS object
            :param loop: TransmitterLoop object
            :return: tuple, x-y coordinates of where the label should be plotted
            """
            def find_quadrant(x, y):
                """
                Return which quadrant coordinates to place the loop label in.
                :param x: float: collar easting
                :param y: float: collar northing
                :return: tuple: x and y coordinate to plot the loop label
                """
                q1 = (xmax - xcenter) * 0.2 + xcenter, (ymax - ycenter) * 0.2 + ycenter
                q2 = (xcenter - xmin) * 0.8 + xmin, (ymax - ycenter) * 0.2 + ycenter
                q3 = (xcenter - xmin) * 0.8 + xmin, (ycenter - ymin) * 0.8 + ymin
                q4 = (xmax - xcenter) * 0.2 + xcenter, (ycenter - ymin) * 0.8 + ymin

                if x > xcenter and y > ycenter:
                    return q3
                elif x > xcenter and y < ycenter:
                    return q2
                elif x < xcenter and y > ycenter:
                    return q4
                else:
                    return q1

            # Loop extents
            xmin, xmax, ymin, ymax, zmin, zmax = loop.get_extents()
            # Loop center
            xcenter, ycenter, zcenter = loop.get_center()

            loop_label_quandrant = find_quadrant(collar.df.iloc[0]['Easting'], collar.df.iloc[0]['Northing'])
            return loop_label_quandrant

        label_buffer = [patheffects.Stroke(linewidth=1.5, foreground=buffer_color), patheffects.Normal()]
        ax = figure.axes[0]
        loop = pem_file.loop
        if not loop.df.empty:
            loop_gps = loop.get_loop(sorted=False, closed=(not is_mmr))
            eastings, northings = loop_gps.Easting.to_numpy(), loop_gps.Northing.to_numpy()

            # Plot the loop
            loop_handle, = ax.plot(eastings, northings,
                                   color=color,
                                   lw=1,
                                   label='Transmitter Loop',
                                   antialiased=True,
                                   zorder=2)

            # Label the loop
            if label:
                if pem_file.is_borehole():
                    collar = pem_file.collar
                    if not collar.df.empty:
                        # Find a more optimal location to plot the label
                        label_x, label_y = get_label_pos(collar, loop)
                    else:
                        # Plot the label in the center
                        label_x, label_y, _ = loop.get_center()
                else:
                    # Plot the label in the center
                    label_x, label_y, _ = loop.get_center()

                loop_label = ax.text(label_x, label_y,
                                     f"Tx Loop {pem_file.loop_name}",
                                     ha='center',
                                     color=color,
                                     zorder=zorder,
                                     path_effects=label_buffer
                                     )

            # Add the loop L-tag annotations
            if annotate:
                for i, (x, y) in enumerate(list(zip(eastings, northings))):
                    plt.annotate(i, xy=(x, y),
                                 va='center',
                                 ha='center',
                                 fontsize=7,
                                 path_effects=label_buffer,
                                 zorder=3,
                                 color=color,
                                 transform=ax.transData)

            return loop_handle

    def plot_line(self, pem_file, figure, annotate=True, label=True, plot_ticks=True, color='black',
                  buffer_color="white", zorder=2):
        """
        Plot the line GPS of a pem_file.
        :param pem_file: PEMFile object
        :param figure: Matplotlib Figure object to plot on
        :param annotate: bool, add L-tag annotations
        :param label: bool, add loop label
        :param plot_ticks: bool, add the tick marks at each station
        :param color: str, line color
        :param zorder: int, order in which to draw the object (higher number draws it on top of lower numbers)
        :return: loop_handle for legend
        """
        lines = []
        line_labels = []
        station_labels = []

        label_buffer = [patheffects.Stroke(linewidth=1.5, foreground=buffer_color), patheffects.Normal()]
        ax = figure.axes[0]
        line = pem_file.line
        # Plotting the line and adding the line label
        if not line.df.empty:
            lines.append(line)
            eastings, northings = line.df['Easting'].to_numpy(), line.df['Northing'].to_numpy()

            # Plot the line
            marker = '-o' if plot_ticks is True else '-'
            station_handle, = ax.plot(eastings, northings,
                                      marker,
                                      lw=1,
                                      antialiased=True,
                                      markersize=3,
                                      color=color,
                                      markerfacecolor=buffer_color,
                                      markeredgewidth=0.3,
                                      label='Surface Line',
                                      zorder=zorder)

            # Add the line label
            if label:
                angle = math.degrees(math.atan2(northings[-1] - northings[0], eastings[-1] - eastings[0]))
                if abs(angle) > 90:
                    x, y = eastings[-1], northings[-1]
                    # Flip the label if it's upside-down
                    angle = angle - 180
                else:
                    x, y = eastings[0], northings[0]

                line_label = ax.text(x, y,
                                     f" {pem_file.line_name} ",
                                     rotation=angle,
                                     rotation_mode='anchor',
                                     ha='right',
                                     va='center',
                                     zorder=zorder + 1,
                                     color=color,
                                     path_effects=label_buffer,
                                     clip_on=True)
                line_labels.append(line_label)

            if annotate:
                for row in line.df.itertuples():
                    station_label = ax.text(row.Easting, row.Northing, row.Station,
                                            fontsize=7,
                                            path_effects=label_buffer,
                                            ha='center',
                                            va='bottom',
                                            color=color,
                                            clip_on=True)
                    station_labels.append(station_label)

            return station_handle

    def plot_hole(self, pem_file, figure, label=True, label_depth=True, plot_ticks=True, plot_trace=True, color='black',
                  buffer_color="white", zorder=6):
        """
        Plot a borehole collar and hole trace.
        :param pem_file: PEMFile object
        :param figure: matplotlib Figure object
        :param label: bool, label the hole name at the hole collar.
        :param label_depth: bool, label the depth of the hole at the end of the hole trace.
        :param plot_ticks: bool, plot ticks going down the hole.
        :param plot_trace: bool, plot the hole trace.
        :param color: str, color of the collar and trace.
        :param zorder: int
        """
        label_buffer = [patheffects.Stroke(linewidth=1.5, foreground=buffer_color), patheffects.Normal()]
        ax = figure.axes[0]
        geometry = pem_file.get_geometry()
        projection = geometry.get_projection(num_segments=1000)

        if not geometry.collar.df.empty:
            collar_x, collar_y = geometry.collar.df.loc[0, ['Easting', 'Northing']].to_numpy()
            marker_style = dict(marker='o',
                                color=buffer_color,
                                markeredgecolor=color,
                                markersize=8)

            # Plot the collar
            collar_handle, = ax.plot(collar_x, collar_y,
                                     fillstyle='full',
                                     label='Borehole Collar',
                                     zorder=4,
                                     **marker_style)
            # Add the hole label at the collar
            if label:
                if pem_file.has_geometry():
                    azimuth = pem_file.get_segments().iloc[0].Azimuth
                else:
                    azimuth = 0

                vo = 0  # Vertical offset for when the label is placed beneath the collar
                ho = 0  # Horizontal offset
                if 0 <= azimuth < 45:
                    ha = 'center'
                    va = 'top'
                elif 45 <= azimuth < 135:
                    ha = 'right'
                    ho = -6
                    va = 'center'
                elif 135 <= azimuth < 225:
                    ha = 'center'
                    va = 'bottom'
                elif 225 < azimuth < 315:
                    ha = 'left'
                    ho = 6
                    va = 'center'
                else:
                    ha = 'center'
                    va = 'top'
                    vo = -6

                if 45 < azimuth < 225:
                   pass

                collar_label = ax.annotate(f"{pem_file.line_name}", (collar_x, collar_y),
                                           xytext=(ho, vo),
                                           textcoords='offset points',
                                           ha=ha,
                                           va=va,
                                           color=color,
                                           zorder=5,
                                           path_effects=label_buffer)

            if not projection.empty and plot_trace:
                seg_x, seg_y = projection['Easting'].to_numpy(), projection['Northing'].to_numpy()
                seg_dist = projection['Relative_depth'].to_numpy()

                # Calculating tick indexes. Ticks are placed at evenly spaced depths.
                # Spaced every 50m, starting from the top
                depths = np.arange(seg_dist.min(), seg_dist.max() + 51, 50)

                # Find the index of the seg_z depth nearest each depths value.
                indexes = [min(range(len(seg_dist)), key=lambda i: abs(seg_dist[i] - depth)) for depth in depths]

                # Hole trace is plotted using marker positions so that they match perfectly.
                index_x = projection.iloc[indexes]['Easting'].to_numpy()
                index_y = projection.iloc[indexes]['Northing'].to_numpy()

                # Plotting the hole trace
                trace_handle, = ax.plot(index_x, index_y, '--', color=color)

                if plot_ticks:
                    # Plotting the markers
                    for index in indexes[1:]:
                        if index != indexes[-1]:
                            angle = math.degrees(
                                math.atan2(seg_y[index + 1] - seg_y[index], seg_x[index + 1] - seg_x[index]))
                            ax.plot(seg_x[index], seg_y[index],
                                    markersize=5,
                                    marker=(2, 0, angle),
                                    mew=.5,
                                    color=color)

                    # Add the end tick for the borehole trace and the label
                    angle = math.degrees(math.atan2(seg_y[-1] - seg_y[-2], seg_x[-1] - seg_x[-2]))

                    ax.plot(seg_x[-1], seg_y[-1],
                            markersize=9,
                            marker=(2, 0, angle),
                            mew=.5,
                            color=color)

                if label_depth:
                    # Label the depth at the bottom of the hole
                    bh_depth = ax.text(seg_x[-1], seg_y[-1], f"  {projection.iloc[-1]['Relative_depth']:.0f} m",
                                       rotation=angle + 90,
                                       fontsize=8,
                                       color=color,
                                       path_effects=label_buffer,
                                       zorder=3,
                                       rotation_mode='anchor')
                    # labels.append(bh_depth)

            return collar_handle

    @staticmethod
    def add_scale_bar(ax, x_pos=0.5, y_pos=0.05, scale_factor=1., units='m', buffer_color="white"):
        """
        Adds scale bar to the axes.
        Gets the width of the map in meters, find the best bar length number, and converts the bar length to
        equivalent axes percentage, then plots using axes transform so it is static on the axes.
        :return: None
        """
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
                patch = patches.Rectangle((rect_x, y), sm_rect_width, rect_height,
                                          ec='k',
                                          linewidth=line_width,
                                          facecolor=fill,
                                          transform=ax.transAxes,
                                          zorder=9)
                ax.add_patch(patch)
            for i, rect_x in enumerate(sm_rect_xs):  # Bottom set of small rectangles
                fill = 'k' if i % 2 == 0 else 'w'
                patch = patches.Rectangle((rect_x, y - rect_height), sm_rect_width, rect_height,
                                          ec='k',
                                          zorder=9,
                                          linewidth=line_width,
                                          facecolor=fill,
                                          transform=ax.transAxes)
                ax.add_patch(patch)

            # Adding the big rectangles
            patch1 = patches.Rectangle((big_rect_x, y), big_rect_width, rect_height,
                                           ec='k',
                                           facecolor='k',
                                           linewidth=line_width,
                                           transform=ax.transAxes,
                                           zorder=9)
            patch2 = patches.Rectangle((big_rect_x, y - rect_height), big_rect_width, rect_height,
                                           ec='k',
                                           facecolor='w',
                                           linewidth=line_width,
                                           transform=ax.transAxes,
                                           zorder=9)
            ax.add_patch(patch1)
            ax.add_patch(patch2)

        label_buffer = [patheffects.Stroke(linewidth=1, foreground=buffer_color), patheffects.Normal()]

        map_width = ax.get_xlim()[1] - ax.get_xlim()[0]
        # map_width = ax.get_extent()[1] - ax.get_extent()[0]
        num_digit = int(np.floor(np.log10(map_width)))  # number of digits in number
        base = 0.5 * 10 ** num_digit
        bar_map_length = round(map_width, -num_digit)  # round to 1sf
        bar_map_length = base * math.ceil(bar_map_length / 8 / base)  # Rounds to the nearest 1,2,5...
        # Multiply by scale factor for Section Plot
        bar_map_length = bar_map_length * scale_factor
        if units == 'm':
            if bar_map_length > 10000:
                units = 'kilometers'
                bar_map_length = bar_map_length / 1000
            else:
                units = 'meters'
        else:
            units = 'feet'

        bar_ax_length = bar_map_length / map_width
        left_pos = x_pos - (bar_ax_length / 2)
        right_pos = x_pos + (bar_ax_length / 2)

        add_rectangles(left_pos, x_pos, right_pos, y_pos)
        ax.text(left_pos, y_pos + .009, f"{bar_map_length / 2:.0f}",
                ha='center',
                transform=ax.transAxes,
                path_effects=label_buffer,
                fontsize=7,
                zorder=9)
        ax.text(x_pos, y_pos + .009, f"0",
                ha='center',
                transform=ax.transAxes,
                path_effects=label_buffer,
                fontsize=7,
                zorder=9)
        ax.text(right_pos, y_pos + .009, f"{bar_map_length / 2:.0f}",
                ha='center',
                transform=ax.transAxes,
                path_effects=label_buffer,
                fontsize=7,
                zorder=9)
        ax.text(x_pos, y_pos - .018, f"({units})",
                ha='center',
                transform=ax.transAxes,
                path_effects=label_buffer,
                fontsize=7,
                zorder=9)

    # @staticmethod
    # def set_size(ax, figure):
    #     """
    #     Re-size the extents to make the axes 11" by 8.5"
    #     :param ax: Matplotlib Axes object
    #     :param figure: Matplotlib Figure object
    #     """
    #     bbox = ax.get_window_extent().transformed(figure.dpi_scale_trans.inverted())
    #     xmin, xmax = ax.get_xlim()
    #     ymin, ymax = ax.get_ylim()
    #     # xmin, xmax, ymin, ymax = ax.get_extent()
    #     map_width, map_height = xmax - xmin, ymax - ymin
    #
    #     current_ratio = map_width / map_height
    #
    #     if current_ratio < (bbox.width / bbox.height):
    #         new_height = map_height
    #         # Set the new width to be the correct ratio larger than height
    #         new_width = new_height * (bbox.width / bbox.height)
    #     else:
    #         new_width = map_width
    #         new_height = new_width * (bbox.height / bbox.width)
    #
    #     x_offset = 0
    #     y_offset = 0.06 * new_height
    #     new_xmin = (xmin - x_offset) - ((new_width - map_width) / 2)
    #     new_xmax = (xmax - x_offset) + ((new_width - map_width) / 2)
    #     new_ymin = (ymin + y_offset) - ((new_height - map_height) / 2)
    #     new_ymax = (ymax + y_offset) + ((new_height - map_height) / 2)
    #
    #     ax.set_xlim(new_xmin, new_xmax)
    #     ax.set_ylim(new_ymin, new_ymax)
    #     # ax.set_extent((new_xmin, new_xmax, new_ymin, new_ymax), crs=crs)

    @staticmethod
    def set_scale(ax, figure):
        """
        Changes the extent of the plot such that the scale is an acceptable value.
        :param ax: Matplotlib Axes object
        :param figure: Matplotlib Figure object
        """
        def get_scale_factor():
            """Return an appropriate scale for the map."""
            # num_digit = len(str(int(current_scale)))  # number of digits in number
            num_digit = int(np.floor(np.log10(current_scale)))  # number of digits in number
            scale_nums = [1., 1.25, 1.5, 2., 2.5, 5.]
            possible_scales = [num * 10 ** num_digit for num in
                               scale_nums + list(map(lambda x: x * 10, scale_nums))]

            # Calculate the new scale using a 40 % buffer
            new_scale = min(filter(lambda x: x > current_scale * 1.40, possible_scales),
                            key=lambda x: x - current_scale * 1.40)
            if new_scale == 1500:
                new_scale = 2000

            scale_factor = new_scale / current_scale
            return scale_factor, new_scale

        xmin, xmax = ax.get_xlim()
        ymin, ymax = ax.get_ylim()
        # xmin, xmax, ymin, ymax = ax.get_extent()
        map_width, map_height = xmax - xmin, ymax - ymin
        bbox = ax.get_window_extent().transformed(figure.dpi_scale_trans.inverted())
        current_scale = map_width / (bbox.width * .0254)
        scale_factor, new_map_scale = get_scale_factor()
        new_map_height = map_height * scale_factor
        new_map_width = map_width * scale_factor

        new_xmin = xmin - ((new_map_width - map_width) / 2)
        new_xmax = xmax + ((new_map_width - map_width) / 2)
        new_ymin = ymin - ((new_map_height - map_height) / 2)
        new_ymax = ymax + ((new_map_height - map_height) / 2)

        ax.set_xlim(new_xmin, new_xmax)
        ax.set_ylim(new_ymin, new_ymax)
        # ax.set_extent((new_xmin, new_xmax, new_ymin, new_ymax), crs=crs)
        return new_map_scale

    @staticmethod
    def add_north_arrow(ax, x_pos=0.94, y_pos=0.89, length=0.16, line_width=0.5):
        """
        Adds the north arrow to the plot. The arrow is manually drawn, and is always fixed in position and size.
        :param ax: Matplotlib Axes object
        :param x_pos: float, horizontal middle position of the arrow
        :param y_pos: float, vertical middle position of the arrow
        :param length: float, length of the arrow
        :param line_width: float, width of the lines
        :return: None
        """
        def ax_len(pixel_length):
            """
            Calculate the equivalent axes size for a given pixel length
            :param pixel_length: float, length of the line in pixel values
            """
            return length * (pixel_length / 300)  # 267 is pixel length of old north arrow

        bot = y_pos - (length / 2)
        top = y_pos + (length / 2)

        # Drawing full arrow polygon using ax.plot
        xs = [x_pos, x_pos, x_pos + ax_len(11), x_pos, x_pos, x_pos - ax_len(6), x_pos - ax_len(6), x_pos]
        ys = [top - ax_len(45) + ax_len(8), top, top - ax_len(45), top - ax_len(45) + ax_len(8), bot,
              bot - ax_len(12), bot + ax_len((41 - 12)), bot + ax_len(41)]
        ax.plot(xs, ys, color='k', lw=line_width, transform=ax.transAxes)

        # Drawing the N
        xs = [x_pos - ax_len(12), x_pos - ax_len(12), x_pos + ax_len(12), x_pos + ax_len(12)]  # First N
        ys = [y_pos - ax_len(21), y_pos + ax_len(21), y_pos - ax_len(30) + ax_len(21), y_pos + ax_len(21)]  # First N
        x2s = [x_pos - ax_len(12), x_pos + ax_len(12), x_pos + ax_len(12)]  # Second diagonal line
        y2s = [y_pos + ax_len(30) - ax_len(21), y_pos - ax_len(21),
               y_pos - ax_len(30) + ax_len(21)]  # Second diagonal line
        ax.plot(xs, ys, color='k', lw=line_width, transform=ax.transAxes)
        ax.plot(x2s, y2s, color='k', lw=line_width, transform=ax.transAxes)

        # Drawing the two side-lines
        x1 = [x_pos - ax_len(31) - ax_len(36), x_pos - ax_len(31)]
        x2 = [x_pos + ax_len(31) + ax_len(36), x_pos + ax_len(31)]
        y = [y_pos] * 2
        tick_line1 = lines.Line2D(x1, y, color='k', lw=line_width, transform=ax.transAxes)
        tick_line2 = lines.Line2D(x2, y, color='k', lw=line_width, transform=ax.transAxes)

        ax.add_line(tick_line1)
        ax.add_line(tick_line2)


class PlanMap(MapPlotter):
    """
    Draws a plan map on a given Matplotlib figure object. Only makes a plan map for one survey type and timebase.
    :param: pem_files: list of pem_files
    :param: figure: Matplotlib landscape-oriented figure object
    """
    def __init__(self, pem_files, figure, crs, annotate_loop=False, is_moving_loop=False, draw_title_box=True,
                 draw_grid=True, draw_scale_bar=True, draw_north_arrow=True, draw_legend=True, draw_loops=True,
                 draw_lines=True, draw_collars=True, draw_hole_traces=True, label_loops=True, label_lines=True,
                 label_collars=True, label_hole_depth=True):
        super().__init__()
        self.figure = figure

        if not isinstance(pem_files, list):
            pem_files = [pem_files]

        self.pem_files = pem_files
        self.crs = crs
        # Get the units of the GPS of each file
        gps_units = np.array([f.get_gps_units() for f in self.pem_files])
        # Remove None values
        gps_units = np.unique(gps_units[gps_units != np.array(None)])
        # Make sure all GPS units are the same
        if len(gps_units) > 1:
            raise ValueError(f"A mix of GPS units was passed.")
        elif not gps_units:
            raise ValueError(f"No GPS units were found.")

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
        self.color = 'black'

        self.annotate_loop = annotate_loop
        self.is_moving_loop = is_moving_loop
        self.draw_title_box = draw_title_box
        self.draw_grid = draw_grid
        self.draw_scale_bar = draw_scale_bar
        self.draw_north_arrow = draw_north_arrow
        self.draw_legend = draw_legend
        self.draw_loops = draw_loops
        self.draw_lines = draw_lines
        self.draw_collars = draw_collars
        self.draw_hole_traces = draw_hole_traces
        self.label_loops = label_loops
        self.label_lines = label_lines
        self.label_collars = label_collars
        self.label_hole_depth = label_hole_depth

        assert self.crs, 'No CRS'

        # When using Cartopy. Disabled for now since it doesn't support North arrows and UTM gridline labels
        # if self.crs.is_projected:
        #     self.map_crs = ccrs.epsg(self.crs.to_epsg())
        # else:
        #     self.map_crs = ccrs.PlateCarree()
        # self.ax = self.figure.add_subplot(projection=self.map_crs)
        self.ax = self.figure.add_subplot()

    def plot(self):
        """
        Plot all the PEM Files and format and return the figure
        :return: Plotted Matplotlib figure
        """
        survey_type = self.pem_files[0].get_survey_type()
        for pem_file in self.pem_files:
            # Remove files that aren't the same survey type
            if pem_file.get_survey_type() != survey_type:
                # User should be suggested that all the files loaded in PEMPro should be the same
                # type of survey
                logger.warning(
                    f"{pem_file.filepath.name} is not the correct survey type: {pem_file.get_survey_type()} vs "
                    f"{survey_type}")
                self.pem_files.remove(pem_file)
                break

            # Plot the surface lines
            if not pem_file.is_borehole() and self.draw_lines is True and pem_file.has_station_gps():
                self.station_handle = self.plot_line(pem_file, self.figure,
                                                     annotate=False)

            # Plot the boreholes
            if pem_file.is_borehole() and self.draw_collars is True and pem_file.has_collar_gps():
                self.plot_hole(pem_file, self.figure,
                               label=self.label_collars,
                               label_depth=self.label_hole_depth)

            # Plot the loops
            if self.draw_loops is True and pem_file.has_loop_gps():
                if pem_file.get_loop().to_string() not in self.loops:
                    self.loops.append(pem_file.get_loop().to_string())
                    self.loop_handle = self.plot_loop(pem_file, self.figure,
                                                      annotate=self.annotate_loop,
                                                      label=self.label_loops,
                                                      is_mmr=pem_file.is_mmr())

        self.format_figure()
        return self.figure

    def format_figure(self):

        def add_title():
            """
            Adds the title box to the plot.
            :return: None
            """
            def get_survey_dates():
                survey_dates = [pem_file.date for pem_file in self.pem_files]
                min_date = min([datetime.strptime(date, '%B %d, %Y') for date in survey_dates])
                max_date = max([datetime.strptime(date, '%B %d, %Y') for date in survey_dates])
                min_date_text = datetime.strftime(min_date, '%B %d')
                max_date_text = datetime.strftime(max_date, '%B %d, %Y')
                survey_date_text = f"Survey Date: {min_date_text} - {max_date_text}" if min_date != max_date else f"Survey Date: {max_date_text}"
                return survey_date_text

            def draw_box():
                # Separating lines
                line_1 = lines.Line2D([b_xmin, b_xmin + b_width], [top_pos - .045, top_pos - .045],
                                       linewidth=1,
                                       color='gray',
                                       transform=self.ax.transAxes,
                                       zorder=10)

                line_2 = lines.Line2D([b_xmin, b_xmin + b_width], [top_pos - .115, top_pos - .115],
                                       linewidth=1,
                                       color='gray',
                                       transform=self.ax.transAxes,
                                       zorder=10)

                line_3 = lines.Line2D([b_xmin, b_xmin + b_width], [top_pos - .160, top_pos - .160],
                                       linewidth=.5,
                                       color='gray',
                                       transform=self.ax.transAxes,
                                       zorder=10)

                # Title box rectangle
                rect = patches.FancyBboxPatch(xy=(b_xmin, b_ymin),
                                              width=b_width,
                                              height=b_height,
                                              edgecolor='k',
                                              boxstyle="round,pad=0.005",
                                              facecolor='white',
                                              zorder=9,
                                              transform=self.ax.transAxes)

                self.ax.add_patch(rect)
                shadow = patches.Shadow(rect, 0.002, -0.002)
                self.ax.add_patch(shadow)
                self.ax.add_line(line_1)
                self.ax.add_line(line_2)
                self.ax.add_line(line_3)

            b_xmin = 0.015
            b_width = 0.30
            b_ymin = 0.784
            b_height = 0.200
            center_pos = b_xmin + (b_width / 2)
            right_pos = b_xmin + b_width - .01
            left_pos = b_xmin + .01
            top_pos = b_ymin + b_height - 0.020

            draw_box()

            client = self.pem_files[0].client
            grid = self.pem_files[0].grid
            loops = natsort.humansorted([file.loop_name for file in self.pem_files])
            loops = list(set(loops))
            hole = self.pem_files[0].line_name
            timebases = np.unique(np.array([file.timebase for file in self.pem_files], dtype=str))

            if not self.pem_files[0].is_borehole():
                if self.is_moving_loop and len(loops) > 1:
                    survey_text = f"Loop: {loops[0]} to {loops[-1]}"
                else:
                    survey_text = f"Loop: {', '.join(loops)}"
            else:
                survey_text = f"Hole: {hole}    Loop: {', '.join(loops)}"

            scale = f"1:{self.map_scale:,.0f}"

            # Head title
            self.ax.text(center_pos, top_pos, 'Crone Geophysics & Exploration Ltd.',
                         fontname='Century Gothic',
                         fontsize=11,
                         ha='center',
                         zorder=10,
                         transform=self.ax.transAxes)

            # Subtitle
            self.ax.text(center_pos, top_pos - 0.020, f"{'Hole' if self.pem_files[0].is_borehole() else 'Line'}"
                                                      f" and Loop Location Map",
                         family='cursive',
                         fontname='Century Gothic',
                         fontsize=10,
                         ha='center',
                         zorder=10,
                         transform=self.ax.transAxes)

            # Survey type
            self.ax.text(center_pos, top_pos - 0.040, f"{self.pem_files[0].get_survey_type().title()} Pulse EM Survey",
                         family='cursive',
                         style='italic',
                         fontname='Century Gothic',
                         fontsize=9,
                         ha='center',
                         zorder=10,
                         transform=self.ax.transAxes)

            # Client and grid names
            self.ax.text(center_pos, top_pos - 0.054, f"{client}\n" + f"{grid}\n"
                                                      f"{survey_text}",
                         fontname='Century Gothic',
                         fontsize=10,
                         va='top',
                         ha='center',
                         zorder=10,
                         transform=self.ax.transAxes)

            # Timebase and survey dates
            self.ax.text(center_pos, top_pos - 0.124, f"Timebase: {', '.join(timebases)} ms\n{get_survey_dates()}",
                         fontname='Century Gothic',
                         fontsize=9,
                         va='top',
                         ha='center',
                         zorder=10,
                         transform=self.ax.transAxes)

            # CRS
            self.ax.text(left_pos, top_pos - 0.167, f"{self.crs.name}",
                         family='cursive',
                         style='italic',
                         color='dimgray',
                         fontname='Century Gothic',
                         fontsize=8,
                         va='top',
                         ha='left',
                         zorder=10,
                         transform=self.ax.transAxes)

            # Map scale
            self.ax.text(right_pos, top_pos - 0.167, f"Scale {scale}",
                         family='cursive',
                         style='italic',
                         color='dimgray',
                         fontname='Century Gothic',
                         fontsize=8,
                         va='top',
                         ha='right',
                         zorder=10,
                         transform=self.ax.transAxes)

        self.figure.subplots_adjust(left=0.03, bottom=0.03, right=0.97, top=0.95)

        # Resize the figure to be 11" x 8.5"
        set_ax_size(self.ax, self.figure)

        # Calculate and set the scale of the map
        self.map_scale = self.set_scale(self.ax, self.figure)

        # Add the grid
        if self.draw_grid:
            self.ax.grid(True, linestyle='dotted', zorder=0)
        else:
            self.ax.grid(False)

        # Add the scale bar
        if self.draw_scale_bar:
            self.add_scale_bar(self.ax)

        # Add the north arrow
        if self.draw_north_arrow:
            self.add_north_arrow(self.ax)

        # Add the title box
        if self.draw_title_box:
            add_title()

        # Add the legend
        if self.draw_legend:
            legend_handles = [handle for handle in
                              [self.loop_handle, self.station_handle, self.collar_handle] if
                              handle is not None]
            # Manually add the hole trace legend handle
            if self.draw_hole_traces and self.pem_files[0].is_borehole():
                legend_handles.append(
                    lines.Line2D([], [],
                                 linestyle='--',
                                 color=self.color,
                                 marker='|',
                                 label='Borehole Trace'))

            self.ax.legend(handles=legend_handles,
                           title='Legend',
                           loc='lower right',
                           framealpha=1,
                           shadow=True,
                           edgecolor='k')

        if 'UTM' in self.crs.name:
            self.ax.yaxis.set_major_formatter(ticker.StrMethodFormatter('{x:,.0f}m N'))
            self.ax.xaxis.set_major_formatter(ticker.StrMethodFormatter('{x:,.0f}m E'))
        else:
            raise NotImplemented(f"{self.crs.name} is not currently supported for map creation.")

        # Add the X and Y axes UTM labels and format the labels
        self.ax.xaxis.set_visible(True)  # Required to actually get the labels to show in UTM
        self.ax.yaxis.set_visible(True)
        for tick in self.ax.get_yticklabels():
            tick.set_rotation(90)
            tick.set_verticalalignment('center')

        self.ax.xaxis.set_ticks_position('top')
        plt.setp(self.ax.get_xticklabels(), fontname='Century Gothic')
        plt.setp(self.ax.get_yticklabels(), fontname='Century Gothic', va='center')


class SectionPlot(MapPlotter):
    """
    Plots the section plot (magnetic field vector plot) of a single borehole on a given figure object.
    By default the azimuth selected is the 80th percentile down the hole, but this is selected by the user.
    """

    def __init__(self):
        super().__init__()
        self.buffer = [patheffects.Stroke(linewidth=3, foreground='white'), patheffects.Normal()]
        self.color = 'black'

        self.figure = None
        self.ax = None
        self.pem_file = None
        self.stations = None
        self.label_ticks = None
        self.line_az = None
        self.line_len = None
        self.p1, self.p2 = None, None
        self.map_scale = None

    def plot(self, pem_file, figure, stations=None, hole_depth=None, label_ticks=False):
        """
        :param pem_file: PEMFile to plot
        :param figure: Matplotlib figure object to plot on
        :param stations: list, stations for tick markers
        :param hole_depth: int, depth of the hole
        :param label_ticks: bool, whether to label the ticks with the depth
        """

        def plot_mag(section_depth):
            """
            Plot the magnetic field lines
            :param section_depth: float, depth to which to plot the lines
            """
            # Corners used to calculate the mag field
            c1, c2 = (self.p1[0], self.p1[1], self.ax.get_ylim()[1]), (
                self.p2[0], self.p2[1], self.ax.get_ylim()[1] - (1.1 * section_depth))

            wire_coords = self.pem_file.get_loop()
            mag_calculator = MagneticFieldCalculator(wire_coords, closed_loop=not self.pem_file.is_mmr())

            xx, yy, zz, uproj, vproj, wproj, plotx, plotz, arrow_len = mag_calculator.get_2d_magnetic_field(c1, c2)

            # Plot the vector arrows
            self.ax.quiver(xx, zz, plotx, plotz,
                           color='dimgray',
                           label='Field',
                           pivot='middle',
                           zorder=0,
                           units='dots',
                           scale=0.036,
                           width=0.6,
                           headlength=10,
                           headwidth=6)

        def plot_hole_section(proj):
            """
            Plot the hole trace
            :param proj: pd DataFrame, 3D projected hole trace of the geometry
            """

            def get_magnitude(vector):
                return math.sqrt(sum(i ** 2 for i in vector))

            def project(row):
                """
                Project the 3D trace to a 2D plane
                :param row: proj DataFrame row
                :return: projected x, y coordinate tuple
                """
                q = np.delete(row.to_numpy(), 2)
                q_proj = q - np.dot(q - p, planeNormal) * planeNormal
                distvec = np.array([q_proj[0] - p[0], q_proj[1] - p[1]])
                dist = np.sqrt(distvec.dot(distvec))
                return dist, q_proj[2]

            p = np.array([self.p1[0], self.p1[1], 0])
            vec = [self.p2[0] - self.p1[0], self.p2[1] - self.p1[1], 0]
            planeNormal = np.cross(vec, [0, 0, -1])
            planeNormal = planeNormal / get_magnitude(planeNormal)

            # Plotting station ticks on the projected hole
            if self.stations is None:
                self.stations = self.pem_file.get_stations(converted=True)

            hole_len = geometry.segments.df.iloc[-1]['Depth']
            collar_elevation = geometry.collar.df.iloc[0]['Elevation']

            # Marker indexes are the station depth as a percentage of the max station depth
            station_indexes = [int(station / hole_len * 1000) for station in self.stations]

            # Get the 2D projected coordinates
            plan_proj = proj.apply(project, axis=1).to_numpy()
            # Plotz is the collar elevation minus the relative depth
            plotx, plotz = [p[0] for p in plan_proj], [collar_elevation - p[1] for p in plan_proj]

            # Plot the hole section line
            self.ax.plot(plotx, plotz,
                         color='k',
                         lw=1,
                         path_effects=self.buffer,
                         zorder=10)

            # Circle at top of hole
            self.ax.plot([plotx[0]], collar_elevation, 'o',
                         markerfacecolor='w',
                         markeredgecolor='k',
                         zorder=11)

            # Label hole name
            hole_name = self.pem_file.line_name
            trans = transforms.blended_transform_factory(self.ax.transData, self.ax.transAxes)
            self.ax.annotate(f"{hole_name}", (plotx[0], collar_elevation),
                             xytext=(0, 12),
                             textcoords='offset pixels',
                             color='k',
                             ha='center',
                             size=10,
                             path_effects=self.buffer,
                             transform=trans,
                             zorder=10)

            # Label end-of-hole depth
            angle = math.degrees(math.atan2(plotz[-1] - plotz[-100], plotx[-1] - plotx[-100])) + 90
            self.ax.text(plotx[-1] + self.line_len * .01, plotz[-1], f" {hole_len:.0f} m ",
                         color='k',
                         ha='left',
                         rotation=angle,
                         path_effects=self.buffer,
                         zorder=10,
                         rotation_mode='anchor')

            # Plotting the ticks
            for i, (x, z) in enumerate(zip(plotx, plotz)):
                if i in station_indexes:
                    index = list(plotx).index(x)
                    # Calculate the angle of the tick
                    pa = (plotx[index - 1], plotz[index - 1])
                    angle = math.degrees(math.atan2(pa[1] - z, pa[0] - x)) - 90

                    # Plot the tick
                    self.ax.scatter(x, z,
                                    marker=(2, 0, angle + 90),
                                    color='k',
                                    zorder=12)

                    # Label the station ticks
                    if self.label_ticks:
                        if i != len(plotx) - 1:
                            self.ax.text(x, z, f" {self.stations[station_indexes.index(i)]}",
                                         rotation=angle,
                                         color='dimgray',
                                         size=8)

            # Format the axes
            ylim = self.ax.get_ylim()
            self.ax.set_xlim(0, self.line_len)
            self.ax.set_ylim(ylim[1] - section_depth, ylim[1] + (0.05 * section_depth))

        while isinstance(pem_file, list):
            pem_file = pem_file[0]
        assert pem_file.has_geometry(), f'{pem_file.filepath.name} does not have hole geometry and/or collar GPS'

        self.pem_file = pem_file
        self.figure = figure
        self.figure.subplots_adjust(left=0.055, bottom=0.03, right=0.97, top=0.955)
        self.ax = self.figure.add_subplot()

        self.stations = stations
        self.label_ticks = label_ticks

        geometry = self.pem_file.get_geometry()
        # Get the 3D projection
        proj = geometry.get_projection(num_segments=1000)

        # Calculate the end-points to be used to plot the cross section on
        bbox = self.ax.get_window_extent().transformed(self.figure.dpi_scale_trans.inverted())
        plot_width = bbox.width * .0254  # Convert to meters
        self.p1, self.p2, self.line_az = self.get_section_end_points(geometry, proj, hole_depth, plot_width)

        # Calculate the length of the cross-section (c = sqrt(a² + b²))
        self.line_len = math.sqrt((self.p1[0] - self.p2[0]) ** 2 + (self.p1[1] - self.p2[1]) ** 2)
        section_depth = self.line_len * (bbox.height / bbox.width)

        plot_hole_section(proj)
        plot_mag(section_depth)
        self.format_figure()

        return self.figure

    def get_section_end_points(self, geometry, proj, hole_depth, plot_width):
        """
        Find the 50th percentile down the hole, use that as the center of the section, and find the
        X and Y extents of that section line. Default azimuth used is from the 80th percentile if no hole_depth is given.
        :param geometry: BoreholeGeometry object
        :param proj: pd DataFrame, 3D projected hole trace of the geometry
        :param hole_depth: Desired hole depth to use to find the azimuth of the section
        :param plot_width: Physical width of the plot in meters.
        :return: tuple: XY coordinates of each corner of the section, the azimuth and the length of the section line.
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

        assert self.pem_file.has_all_gps(), f"PEMFile must have all GPS."
        segments = geometry.segments.df

        # Interpolate the azimuth
        interp_az = np.interp(proj['Relative_depth'], segments['Depth'], segments['Azimuth'])
        interp_depths = proj['Relative_depth'].to_numpy()

        # Find the depths that are 50% to find the center X, Y of the line
        perc_50_depth = np.percentile(interp_depths, 50)
        # If no hole_depth is given, it will take the 80% percentile
        if not hole_depth:
            hole_depth = np.percentile(interp_depths, 80)
        else:
            hole_depth = float(hole_depth)

        # Nearest index of the 50th and hole_depth% depths
        i_perc_50_depth = min(range(len(interp_depths)), key=lambda i: abs(interp_depths[i] - perc_50_depth))
        i_perc_depth = min(range(len(interp_depths)), key=lambda i: abs(interp_depths[i] - hole_depth))

        line_center_x, line_center_y = proj.iloc[i_perc_50_depth]['Easting'], proj.iloc[i_perc_50_depth]['Northing']
        line_az = interp_az[i_perc_depth]
        logger.info(f"Section azimuth for {self.pem_file.filepath.name}: {line_az:.0f}°")

        # Calculate the length of the cross-section. The section length is 3/4 of the hole depth
        line_len = math.ceil(segments.iloc[-1]['Depth'] / 400) * 300

        # Calculate the two end-points of the cross-section, based on the azimuth at hole_depth
        dx = math.cos(math.radians(90 - line_az)) * (line_len / 2)
        dy = math.sin(math.radians(90 - line_az)) * (line_len / 2)
        line_xy_1 = (line_center_x - dx, line_center_y - dy)
        line_xy_2 = (line_center_x + dx, line_center_y + dy)

        # Scale the end-points so they are at an appropriate scale
        scale_factor = calc_scale_factor(line_xy_1, line_xy_2, plot_width)
        dx = dx * scale_factor
        dy = dy * scale_factor

        line_xy_1 = (line_center_x - dx, line_center_y - dy)
        line_xy_2 = (line_center_x + dx, line_center_y + dy)

        return line_xy_1, line_xy_2, line_az

    def format_figure(self):

        def calc_scale():
            xmin, xmax = self.ax.get_xlim()
            map_width = xmax - xmin
            bbox = self.ax.get_window_extent().transformed(self.figure.dpi_scale_trans.inverted())
            current_scale = map_width / (bbox.width * .0254)
            return current_scale

        def add_title():

            def get_survey_date():
                survey_date = self.pem_file.date
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
            line_1 = lines.Line2D([b_xmin, b_xmin + b_width], [top_pos - .045, top_pos - .045],
                                   linewidth=1,
                                   color='gray',
                                   transform=self.ax.transAxes,
                                   zorder=10)

            line_2 = lines.Line2D([b_xmin, b_xmin + b_width], [top_pos - .098, top_pos - .098],
                                   linewidth=1,
                                   color='gray',
                                   transform=self.ax.transAxes,
                                   zorder=10)

            line_3 = lines.Line2D([b_xmin, b_xmin + b_width], [top_pos - .135, top_pos - .135],
                                   linewidth=.5,
                                   color='gray',
                                   transform=self.ax.transAxes,
                                   zorder=10)

            # Title box rectangle
            rect = patches.FancyBboxPatch(xy=(b_xmin, b_ymin),
                                          width=b_width,
                                          height=b_height,
                                          edgecolor='k',
                                          boxstyle="round,pad=0.005",
                                          facecolor='white',
                                          zorder=9,
                                          transform=self.ax.transAxes)

            scale = f"1:{calc_scale():,.0f}"

            self.ax.text(center_pos, top_pos, 'Crone Geophysics & Exploration Ltd.',
                         fontname='Century Gothic',
                         fontsize=11,
                         ha='center',
                         zorder=10,
                         transform=self.ax.transAxes)

            self.ax.text(center_pos, top_pos - 0.02, f"Hole Cross-Section with Primary Field",
                         family='cursive',
                         fontname='Century Gothic',
                         fontsize=10,
                         ha='center',
                         zorder=10,
                         transform=self.ax.transAxes)

            self.ax.text(center_pos, top_pos - 0.037, f"{self.pem_file.get_survey_type()} Pulse EM Survey",
                         family='cursive',
                         style='italic',
                         fontname='Century Gothic',
                         fontsize=9,
                         ha='center',
                         zorder=10,
                         transform=self.ax.transAxes)

            self.ax.text(center_pos, top_pos - 0.051, f"{self.pem_file.client}\n" + f"{self.pem_file.grid}\n"
                                                      f"Hole: {self.pem_file.line_name}    Loop: "
                                                      f"{self.pem_file.loop_name}",
                         fontname='Century Gothic',
                         fontsize=10,
                         va='top',
                         ha='center',
                         zorder=10,
                         transform=self.ax.transAxes)

            self.ax.text(center_pos, top_pos - 0.105,
                         f"Timebase: {self.pem_file.timebase} ms\n{get_survey_date()}",
                         fontname='Century Gothic',
                         fontsize=9,
                         va='top',
                         ha='center',
                         zorder=10,
                         transform=self.ax.transAxes)

            self.ax.text(left_pos, top_pos - 0.140, f"Section Azimuth: {self.line_az:.0f}°",
                         family='cursive',
                         style='italic', color='dimgray',
                         fontname='Century Gothic',
                         fontsize=8,
                         va='top',
                         ha='left',
                         zorder=10,
                         transform=self.ax.transAxes)

            self.ax.text(right_pos, top_pos - 0.140, f"Scale {scale}",
                         family='cursive',
                         style='italic',
                         color='dimgray',
                         fontname='Century Gothic',
                         fontsize=8,
                         va='top',
                         ha='right',
                         zorder=10,
                         transform=self.ax.transAxes)

            self.ax.add_patch(rect)
            shadow = patches.Shadow(rect, 0.002, -0.002)
            self.ax.add_patch(shadow)
            self.ax.add_line(line_1)
            self.ax.add_line(line_2)
            self.ax.add_line(line_3)

        def add_coord_labels():
            # Plot Labelling
            lefttext = f'{self.p1[0]:,.0f}m E\n{self.p1[1]:,.0f}m N'
            righttext = f'{self.p2[0]:,.0f}m E\n{self.p2[1]:,.0f}m N'
            self.ax.text(0, 1.01, lefttext,
                         color='k',
                         ha='left',
                         size='small',
                         path_effects=self.buffer,
                         zorder=9,
                         transform=self.ax.transAxes)
            self.ax.text(1, 1.01, righttext,
                         color='k',
                         ha='right',
                         size='small',
                         path_effects=self.buffer,
                         zorder=9,
                         transform=self.ax.transAxes)

        self.ax.xaxis.set_visible(False)
        self.ax.yaxis.set_visible(True)
        for tick in self.ax.get_yticklabels():
            tick.set_rotation(90)
            tick.set_verticalalignment('center')

        units = self.pem_file.collar.get_units()
        if units == 'm':
            self.ax.yaxis.set_major_formatter(ticker.StrMethodFormatter('{x:,.0f} m'))
        else:
            self.ax.yaxis.set_major_formatter(ticker.StrMethodFormatter('{x:,.0f} ft'))

        add_coord_labels()
        add_title()
        self.add_scale_bar(self.ax, x_pos=0.205, y_pos=0.25, scale_factor=2, units=units)


# class GeneralMap:
#     """
#     Draws a general map for reports on a given Matplotlib figure object. Accepts all holes and surface lines.
#     :param: pem_files: list of pem_files
#     :param: figure: Matplotlib landscape-oriented figure object
#     """
#
#     def __init__(self, pem_files, figure, **kwargs):
#         super().__init__()
#         self.color = 'black'
#         self.fig = figure
#         self.pem_files = pem_files
#
#         if not isinstance(self.pem_files, list):
#             self.pem_files = [self.pem_files]
#
#         self.loops = []
#         self.lines = []
#         self.holes = []
#         self.labels = []
#
#         self.loop_handle = None
#         self.station_handle = None
#         self.collar_handle = None
#         self.trace_handle = None
#         self.map_scale = None
#         self.system = None
#         self.zone = None
#         self.datum = None
#
#         self.draw_loop_annotations = kwargs.get('LoopAnnotations') if kwargs else False
#         self.moving_loop = kwargs.get('MovingLoop') if kwargs else True
#         self.title_box = kwargs.get('TitleBox') if kwargs else True
#         self.map_grid = kwargs.get('Grid') if kwargs else True
#         self.scale_bar = kwargs.get('ScaleBar') if kwargs else True
#         self.north_arrow = kwargs.get('NorthArrow') if kwargs else True
#         self.show_legend = kwargs.get('Legend') if kwargs else True
#         self.draw_loops = kwargs.get('DrawLoops') if kwargs else True
#         self.draw_lines = kwargs.get('DrawLines') if kwargs else True
#         self.draw_collars = kwargs.get('DrawHoleCollars') if kwargs else True
#         self.draw_hole_traces = kwargs.get('DrawHoleTraces') if kwargs else True
#         self.loop_labels = kwargs.get('LoopLabels') if kwargs else True
#         self.line_labels = kwargs.get('LineLabels') if kwargs else True
#         self.hole_collar_labels = kwargs.get('HoleCollarLabels') if kwargs else True
#         self.hole_depth_labels = kwargs.get('HoleDepthLabels') if kwargs else True
#         self.crs = None
#         if __name__ == '__main__':
#             for file in self.pem_files:
#                 try:
#                     self.crs = self.get_crs(file.get_crs())
#                     break
#                 except ValueError:
#                     print(f"{file.filepath.name} has no valid CRS, moving to the next file...")
#                     pass
#         else:
#             self.crs = self.get_crs(kwargs.get('CRS')) if kwargs else None
#
#         if self.crs:
#             self.ax = self.fig.add_subplot(projection=self.crs)
#             self.plot_pems()
#
#     def get_extents(self, pem_file):
#         """
#         Calculate the GPS extents of each dimension of the PEM file.
#         :param pem_file: PEMFile object
#         :return: Range of GPS in all 3 components
#         """
#         loop_coords = pem_file.get_loop_coords()
#         collar = pem_file.get_collar_coords()[0]
#         segments = pem_file.get_hole_geometry()
#         min_x = min([float(row[0]) for row in loop_coords] + [float(collar[0])])
#         max_x = max([float(row[0]) for row in loop_coords] + [float(collar[0])])
#         min_y = min([float(row[1]) for row in loop_coords] + [float(collar[1])])
#         max_y = max([float(row[1]) for row in loop_coords] + [float(collar[1])])
#         min_z = min(
#             [float(row[2]) for row in loop_coords] + [float(collar[2])] + [float(collar[2]) - float(segments[-1][4])])
#         max_z = max(
#             [float(row[2]) for row in loop_coords] + [float(collar[2])] + [float(collar[2]) - float(segments[-1][4])])
#         return min_x, max_x, min_y, max_y, min_z, max_z
#
#     def get_crs(self, crs):
#         self.system = crs.get('System')
#         self.zone = crs.get('Zone')
#         self.north = crs.get('North')
#         self.datum = crs.get('Datum')
#         if not all([self.system, self.zone, self.datum]):
#             raise ValueError('CRS information is invalid.')
#         else:
#             if self.system == 'UTM':
#                 globe = ccrs.Globe(datum=re.sub(' 19', '', self.datum))
#                 return ccrs.UTM(self.zone, southern_hemisphere=not self.north, globe=globe)
#             elif self.system == 'Latitude/Longitude':
#                 return ccrs.Geodetic()
#
#     def get_3D_borehole_projection(self, collar_gps, segments, interp_segments=None):
#         """
#         Uses the segments to create a 3D projection of a borehole trace. Can be broken up into segments and interpolated.
#         :param collar_gps: Collar GPS of the borehole (easting, northing, elevation)
#         :param segments: Segments of a borehole trace (Azimuth, dip, segment length, units, depth)
#         :param interp_segments: Desired number of segments to be output
#         :return: list of hole trace tuples (easting, northing, elevation)
#         """
#         collar_gps = np.array(collar_gps, dtype='float')
#         segments = np.array(segments, dtype='float')
#         if not collar_gps.any():
#             raise ValueError('Collar GPS is invalid.')
#         elif not segments.any():
#             raise ValueError('Segments are invalid.')
#         else:
#             collar_x, collar_y, collar_z = collar_gps[0], collar_gps[1], collar_gps[2]
#
#             if interp_segments:
#                 azimuths = [row[0] for row in segments]
#                 dips = [row[1] for row in segments]
#                 depths = [row[-1] for row in segments]
#                 units = segments[0][-2]
#
#                 interp_depths = np.linspace(depths[0], depths[-1], interp_segments)
#                 interp_az = np.interp(interp_depths, depths, azimuths)
#                 interp_dip = np.interp(interp_depths, depths, dips)
#                 interp_lens = [float(segments[0][-1])]
#
#                 for depth, next_depth in zip(interp_depths[:-1], interp_depths[1:]):
#                     interp_lens.append(next_depth - depth)
#
#                 segments = list(
#                     zip(interp_az, interp_dip, interp_lens, [units] * len(interp_depths), interp_depths))
#
#             eastings = [collar_x]
#             northings = [collar_y]
#             depths = [collar_z]
#             relative_depth = [0.0]
#             azimuth = None
#
#             for segment in segments:
#                 azimuth = math.radians(segment[0])
#                 dip = math.radians(segment[1])
#                 seg_l = segment[2]
#                 delta_seg_l = seg_l * math.cos(dip)
#                 dz = seg_l * math.sin(dip)
#                 dx = delta_seg_l * math.sin(azimuth)
#                 dy = delta_seg_l * math.cos(azimuth)
#
#                 eastings.append(eastings[-1] + dx)
#                 northings.append(northings[-1] + dy)
#                 depths.append(depths[-1] - dz)
#                 relative_depth.append(relative_depth[-1] + seg_l)
#
#             return eastings, northings, depths, relative_depth
#
#     # TODO Should this be removed
#     def get_section_extent(self, pem_file, hole_depth=None, section_plot=False, plot_width=None):
#         """
#         Find the 50th percentile down the hole, use that as the center of the section, and find the
#         X and Y extents of that section line. Default azimuth used is from the 80th percentile if no hole_depth is given.
#         :param pem_file: PEMFile object
#         :param hole_depth: Desired hole depth to use to find the azimuth of the section
#         :param section_plot: Bool: If True, will scale the plot such that the scale is of an acceptable value. Used
#         for 2D section plots.
#         :param plot_width: Physical width of the plot in meters.
#         :return: tuple: XY coordinates of each corner of the section area, and the azimuth of the section.
#         """
#
#         def calc_scale_factor(p1, p2, plot_width):
#             """
#             Modifies the two cross-section points so they will create a map with an appropriate scale
#             :param p1: xy tuple of one of the current extent points
#             :param p2: xy tuple of the other extent point
#             :return: A factor by which to multiply the change in X and change in Y
#             """
#
#             def get_scale_factor():
#                 # num_digit = len(str(int(current_scale)))  # number of digits in number
#                 num_digit = int(np.floor(np.log10(current_scale)))  # number of digits in number
#                 scale_nums = [1., 1.25, 1.5, 2., 5.]
#                 possible_scales = [num * 10 ** num_digit for num in
#                                    scale_nums + list(map(lambda x: x * 10, scale_nums))]
#                 new_scale = min(filter(lambda x: x > current_scale, possible_scales),
#                                 key=lambda x: x - current_scale)
#                 self.map_scale = new_scale
#                 scale_factor = new_scale / current_scale
#                 return scale_factor
#
#             xmin, xmax, ymin, ymax = min([p1[0], p2[0]]), max([p1[0], p2[0]]), min([p1[1], p2[1]]), max([p1[1], p2[1]])
#             dist = math.sqrt((xmax - xmin) ** 2 + (ymax - ymin) ** 2)
#             bbox_width = plot_width  # Section plot width in m (after subplot adjustment)
#             current_scale = dist / bbox_width
#             scale_factor = get_scale_factor()
#             return scale_factor
#
#         if not all([pem_file.has_geometry(), pem_file.has_collar_gps()]):
#             raise ValueError('The PEM file does not have hole geometry and/or collar GPS')
#
#         collar = pem_file.get_collar_coords()[0]
#         segments = pem_file.get_hole_geometry()
#         azimuths = [float(row[0]) for row in segments]
#         dips = [float(row[1]) for row in segments]
#         depths = [float(row[-1]) for row in segments]
#         units = segments[0][-2]
#
#         # Splitting the segments into 1000 pieces
#         interp_depths = np.linspace(depths[0], depths[-1], 1000)
#         interp_az = np.interp(interp_depths, depths, azimuths)
#         interp_dip = np.interp(interp_depths, depths, dips)
#         interp_lens = [float(segments[0][-1])]
#         for depth, next_depth in zip(interp_depths[:-1], interp_depths[1:]):
#             interp_lens.append(next_depth - depth)
#
#         # Recreating the segments with the interpreted data
#         interp_segments = list(zip(interp_az, interp_dip, interp_lens, [units] * len(interp_depths), interp_depths))
#
#         interp_x, interp_y, interp_z, interp_dist = self.get_3D_borehole_projection(collar, interp_segments)
#
#         # Find the depths that are 50% and var percentile% down the holeas
#         perc_50_depth = np.percentile(interp_depths, 50)
#         if not hole_depth:
#             hole_depth = np.percentile(interp_depths, 80)
#
#         # Nearest index of the 50th and var percentile% depths
#         i_perc_50_depth = min(range(len(interp_depths)), key=lambda i: abs(interp_depths[i] - perc_50_depth))
#         i_perc_depth = min(range(len(interp_depths)), key=lambda i: abs(interp_depths[i] - hole_depth))
#
#         line_center_x, line_center_y = interp_x[i_perc_50_depth], interp_y[i_perc_50_depth]
#         line_az = interp_az[i_perc_depth]
#         line_len = math.ceil(depths[-1] / 400) * 300  # Calculating the length of the cross-section
#         dx = math.cos(math.radians(90 - line_az)) * (line_len / 2)
#         dy = math.sin(math.radians(90 - line_az)) * (line_len / 2)
#
#         line_xy_1 = (line_center_x - dx, line_center_y - dy)
#         line_xy_2 = (line_center_x + dx, line_center_y + dy)
#
#         if section_plot:
#             plot_width = plot_width
#             scale_factor = calc_scale_factor(line_xy_1, line_xy_2, plot_width)
#             dx = dx * scale_factor
#             dy = dy * scale_factor
#
#             line_xy_1 = (line_center_x - dx, line_center_y - dy)
#             line_xy_2 = (line_center_x + dx, line_center_y + dy)
#
#         return line_xy_1, line_xy_2, line_az, line_len
#
#     def plot_pems(self):
#
#         def add_loop_to_map(pem_file):
#             loop_gps, loop_name = pem_file.get_loop_coords(), pem_file.header.get('Loop')
#             if (loop_gps, loop_name) not in self.loops:
#                 self.loops.append((loop_gps, loop_name))
#                 loop_center = self.gps_editor().get_loop_center(copy.copy(loop_gps))
#                 eastings, northings = [coord[0] for coord in loop_gps], [coord[1] for coord in loop_gps]
#                 eastings.insert(0, eastings[-1])  # To close up the loop
#                 northings.insert(0, northings[-1])
#                 zorder = 4 if not self.moving_loop else 6
#
#                 if self.loop_labels:
#                     # TODO Probably don't label the loops, but have them all in the legend
#                     loop_label = self.ax.text(loop_center[0], loop_center[1],
#                                               f"Tx Loop {pem_file.header.get('Loop')}",
#                                               ha='center',
#                                               color=self.color,
#                                               zorder=zorder,
#                                               path_effects=label_buffer)  # Add the loop name
#
#                 self.loop_handle, = self.ax.plot(eastings, northings,
#                                                  color=self.color,
#                                                  label='Transmitter Loop',
#                                                  transform=self.crs,
#                                                  zorder=2)  # Plot the loop
#
#                 if self.draw_loop_annotations:
#                     for i, (x, y) in enumerate(list(zip(eastings, northings))):
#                         self.fig.annotate(i,
#                                           xy=(x, y),
#                                           va='center',
#                                           ha='center',
#                                           fontsize=7,
#                                           path_effects=label_buffer,
#                                           zorder=3,
#                                           color=self.color,
#                                           transform=self.ax.transData)
#
#         def add_line_to_map(pem_file):
#
#             line_gps, line_name = pem_file.get_station_coords(), pem_file.header.get('LineHole')
#             # Plotting the line and adding the line label
#             if (line_gps, line_name) not in self.lines:
#                 self.lines.append((line_gps, line_name))
#                 eastings, northings = [float(coord[0]) for coord in line_gps], [float(coord[1]) for coord in line_gps]
#                 angle = math.degrees(math.atan2(northings[-1] - northings[0], eastings[-1] - eastings[0]))
#
#                 if abs(angle) > 90:
#                     x, y = eastings[-1], northings[-1]
#                     # Flip the label if it's upside-down
#                     angle = angle - 180
#                 else:
#                     x, y = eastings[0], northings[0]
#
#                 # Should there be line labels for such a map?
#                 if self.line_labels:
#                     line_label = self.ax.text(x, y,
#                                               f" {pem_file.header.get('LineHole')} ",
#                                               rotation=angle,
#                                               rotation_mode='anchor',
#                                               ha='right',
#                                               va='center',
#                                               zorder=5,
#                                               color=self.color,
#                                               path_effects=label_buffer)
#                     self.labels.append(line_label)
#                 # For legend
#                 self.station_handle, = self.ax.plot(eastings, northings,
#                                                     '-o',
#                                                     markersize=3,
#                                                     color=self.color,
#                                                     markerfacecolor='w',
#                                                     markeredgewidth=0.3,
#                                                     label='Surface Line',
#                                                     transform=self.crs,
#                                                     zorder=2)  # Plot the line
#
#         def add_hole_to_map(pem_file):
#
#             hole_gps, hole_name = pem_file.get_collar_coords()[0], pem_file.header.get('LineHole')
#             collar_x, collar_y, collar_z = float(hole_gps[0]), float(hole_gps[1]), float(hole_gps[2])
#             segments = pem_file.get_hole_geometry()
#             if segments and hole_gps:
#                 seg_x, seg_y, seg_z, seg_dist = self.get_3D_borehole_projection(hole_gps, segments,
#                                                                                 interp_segments=1000)
#             else:
#                 seg_x, seg_y = None, None
#
#             if (hole_gps, hole_name) not in self.holes:
#                 self.holes.append((hole_gps, hole_name))
#                 marker_style = dict(marker='o', color='white', markeredgecolor=self.color, markersize=8)
#                 self.collar_handle, = self.ax.plot(collar_x, collar_y,
#                                                    fillstyle='full',
#                                                    label='Borehole Collar',
#                                                    zorder=4,
#                                                    **marker_style)
#                 # Add the hole label at the collar
#                 if self.hole_collar_labels:
#                     angle = math.degrees(math.atan2(seg_y[-1] - seg_y[0], seg_x[-1] - seg_x[0]))
#                     align = 'left' if angle > 90 or angle < -90 else 'right'
#
#                     if self.hole_collar_labels:
#                         collar_label = self.ax.text(collar_x, collar_y,
#                                                     f"  {pem_file.header.get('LineHole')}  ",
#                                                     va='center',
#                                                     ha=align,
#                                                     color=self.color,
#                                                     zorder=5,
#                                                     path_effects=label_buffer)
#                         self.labels.append(collar_label)
#
#                 if seg_x and seg_y and self.draw_hole_traces is True:
#
#                     # Calculating tick indexes. Ticks are placed at evenly spaced depths.
#                     # depths = np.linspace(min(seg_z), collar_z, 10)  # Spaced such that there are 10 segments
#                     # depths = np.arange(collar_z, min(seg_z)-51, -50)  # Spaced every 50m, starting from the top
#                     depths = np.arange(min(seg_dist), max(seg_dist) + 51, 50)  # Spaced every 50m, starting from the top
#
#                     # Find the index of the seg_z depth nearest each depths value.
#                     # indexes = [min(range(len(seg_z)), key=lambda i: abs(seg_z[i] - depth)) for depth in depths]
#                     indexes = [min(range(len(seg_dist)), key=lambda i: abs(seg_dist[i] - depth)) for depth in depths]
#
#                     # Hole trace is plotted using marker positions so that they match perfectly.
#                     index_x = [seg_x[index] for index in indexes]  # Marker positions
#                     index_y = [seg_y[index] for index in indexes]
#
#                     if self.draw_hole_traces:
#                         # Plotting the hole trace
#                         self.trace_handle, = self.ax.plot(index_x, index_y,
#                                                           '--',
#                                                           label='Hole Trace',
#                                                           color=self.color)
#
#                     # Plotting the markers
#                     for index in indexes[1:]:
#                         if index != indexes[-1]:
#                             angle = math.degrees(
#                                 math.atan2(seg_y[index + 1] - seg_y[index], seg_x[index + 1] - seg_x[index]))
#                             self.ax.plot(seg_x[index], seg_y[index],
#                                          markersize=5,
#                                          marker=(2, 0, angle),
#                                          mew=.5,
#                                          color=self.color)
#
#                     # Add the end tick for the borehole trace and the label
#                     angle = math.degrees(math.atan2(seg_y[-1] - seg_y[-2], seg_x[-1] - seg_x[-2]))
#                     self.ax.scatter(seg_x[-1], seg_y[-1],
#                                     marker=(2, 0, angle),
#                                     color=self.color)
#
#                     # if self.hole_depth_labels:
#                     #     bh_depth = self.ax.text(seg_x[-1], seg_y[-1],
#                     #                             f"  {float(segments[-1][-1]):.0f} m",
#                     #                             rotation=angle+90,
#                     #                             fontsize=8,
#                     #                             color=self.color,
#                     #                             path_effects=label_buffer,
#                     #                             zorder=3,
#                     #                             rotation_mode='anchor')
#
#         for pem_file in self.pem_files:
#             label_buffer = [patheffects.Stroke(linewidth=1.5, foreground='white'), patheffects.Normal()]
#
#             if not pem_file.is_borehole() and self.draw_lines is True and pem_file.has_station_gps():
#                 add_line_to_map(pem_file)
#
#             if pem_file.is_borehole() and self.draw_collars is True and pem_file.has_collar_gps():
#                 add_hole_to_map(pem_file)
#
#             if self.draw_loops is True and pem_file.has_loop_gps():
#                 add_loop_to_map(pem_file)
#
#     def format_figure(self):
#
#         def add_scale_bar():
#             """
#             Adds scale bar to the axes.
#             Gets the width of the map in meters, find the best bar length number, and converts the bar length to
#             equivalent axes percentage, then plots using axes transform so it is static on the axes.
#             :return: None
#             """
#
#             def myround(x, base=5):
#                 return base * math.ceil(x / base)
#
#             def add_rectangles(left_bar_pos, bar_center, right_bar_pos, y):
#                 rect_height = 0.005
#                 line_width = 0.4
#                 sm_rect_width = (bar_center - left_bar_pos) / 5
#                 sm_rect_xs = np.arange(left_bar_pos, bar_center, sm_rect_width)
#                 big_rect_x = bar_center
#                 big_rect_width = right_bar_pos - bar_center
#
#                 # Adding the small rectangles
#                 for i, rect_x in enumerate(sm_rect_xs):  # Top set of small rectangles
#                     fill = 'w' if i % 2 == 0 else 'k'
#                     patch = patches.Rectangle((rect_x, y), sm_rect_width, rect_height,
#                                               ec='k',
#                                               linewidth=line_width,
#                                               facecolor=fill,
#                                               transform=self.ax.transAxes,
#                                               zorder=9)
#                     self.ax.add_patch(patch)
#                 for i, rect_x in enumerate(sm_rect_xs):  # Bottom set of small rectangles
#                     fill = 'k' if i % 2 == 0 else 'w'
#                     patch = patches.Rectangle((rect_x, y - rect_height), sm_rect_width, rect_height,
#                                               ec='k',
#                                               zorder=9,
#                                               linewidth=line_width,
#                                               facecolor=fill,
#                                               transform=self.ax.transAxes)
#                     self.ax.add_patch(patch)
#
#                 # Adding the big rectangles
#                 patch1 = patches.Rectangle((big_rect_x, y), big_rect_width, rect_height,
#                                            ec='k',
#                                            facecolor='k',
#                                            linewidth=line_width,
#                                            transform=self.ax.transAxes,
#                                            zorder=9)
#                 patch2 = patches.Rectangle((big_rect_x, y - rect_height), big_rect_width, rect_height,
#                                            ec='k',
#                                            facecolor='w', linewidth=line_width,
#                                            transform=self.ax.transAxes,
#                                            zorder=9)
#                 self.ax.add_patch(patch1)
#                 self.ax.add_patch(patch2)
#
#             bar_center = 0.5  # Half way across the axes
#             bar_height_pos = 0.05
#             map_width = self.ax.get_extent()[1] - self.ax.get_extent()[0]
#             num_digit = int(np.floor(np.log10(map_width)))  # number of digits in number
#             bar_map_length = round(map_width, -num_digit)  # round to 1sf
#             bar_map_length = myround(bar_map_length / 8, base=0.5 * 10 ** num_digit)  # Rounds to the nearest 1,2,5...
#             if bar_map_length > 10000:
#                 units = 'kilometers'
#                 bar_map_length = bar_map_length / 1000
#             else:
#                 units = 'meters'
#             buffer = [patheffects.Stroke(linewidth=1, foreground='white'), patheffects.Normal()]
#             bar_ax_length = bar_map_length / map_width
#             left_bar_pos = bar_center - (bar_ax_length / 2)
#             right_bar_pos = bar_center + (bar_ax_length / 2)
#
#             add_rectangles(left_bar_pos, bar_center, right_bar_pos, bar_height_pos)
#             self.ax.text(left_bar_pos, bar_height_pos + .009, f"{bar_map_length / 2:.0f}",
#                          ha='center',
#                          transform=self.ax.transAxes,
#                          path_effects=buffer,
#                          fontsize=7,
#                          zorder=9)
#             self.ax.text(bar_center, bar_height_pos + .009, f"0", ha='center',
#                          transform=self.ax.transAxes,
#                          path_effects=buffer,
#                          fontsize=7,
#                          zorder=9)
#             self.ax.text(right_bar_pos, bar_height_pos + .009, f"{bar_map_length / 2:.0f}",
#                          ha='center',
#                          transform=self.ax.transAxes,
#                          path_effects=buffer,
#                          fontsize=7,
#                          zorder=9)
#             self.ax.text(bar_center, bar_height_pos - .018, f"({units})", ha='center',
#                          transform=self.ax.transAxes,
#                          path_effects=buffer,
#                          fontsize=7,
#                          zorder=9)
#
#         def set_size():
#             """
#             Re-size the extents to make the axes 11" by 8.5"
#             :param ax: GeoAxes object
#             :return: None
#             """
#             bbox = self.ax.get_window_extent().transformed(self.fig.dpi_scale_trans.inverted())
#             xmin, xmax, ymin, ymax = self.ax.get_extent()
#             map_width, map_height = xmax - xmin, ymax - ymin
#
#             current_ratio = map_width / map_height
#
#             if current_ratio < (bbox.width / bbox.height):
#                 new_height = map_height
#                 new_width = new_height * (
#                         bbox.width / bbox.height)  # Set the new width to be the correct ratio larger than height
#
#             else:
#                 new_width = map_width
#                 new_height = new_width * (bbox.height / bbox.width)
#             x_offset = 0
#             y_offset = 0.06 * new_height
#             new_xmin = (xmin - x_offset) - ((new_width - map_width) / 2)
#             new_xmax = (xmax - x_offset) + ((new_width - map_width) / 2)
#             new_ymin = (ymin + y_offset) - ((new_height - map_height) / 2)
#             new_ymax = (ymax + y_offset) + ((new_height - map_height) / 2)
#
#             self.ax.set_extent((new_xmin, new_xmax, new_ymin, new_ymax), crs=self.crs)
#
#         def set_scale():
#             """
#             Changes the extent of the plot such that the scale is an acceptable value.
#             :return: None
#             """
#
#             def get_scale_factor():
#                 # num_digit = len(str(int(current_scale)))  # number of digits in number
#                 num_digit = int(np.floor(np.log10(current_scale)))  # number of digits in number
#                 scale_nums = [1., 1.25, 1.5, 2., 2.5, 5.]
#                 possible_scales = [num * 10 ** num_digit for num in
#                                    scale_nums + list(map(lambda x: x * 10, scale_nums))]
#                 new_scale = min(filter(lambda x: x > current_scale * 1.30, possible_scales),
#                                 key=lambda x: x - current_scale * 1.30)
#                 if new_scale == 1500:
#                     new_scale = 2000
#                 self.map_scale = new_scale
#                 scale_factor = new_scale / current_scale
#                 return scale_factor
#
#             xmin, xmax, ymin, ymax = self.ax.get_extent()
#             map_width, map_height = xmax - xmin, ymax - ymin
#             bbox = self.ax.get_window_extent().transformed(self.fig.dpi_scale_trans.inverted())
#             current_scale = map_width / (bbox.width * .0254)
#             scale_factor = get_scale_factor()
#             new_map_height = map_height * scale_factor
#             new_map_width = map_width * scale_factor
#
#             new_xmin = xmin - ((new_map_width - map_width) / 2)
#             new_xmax = xmax + ((new_map_width - map_width) / 2)
#             new_ymin = ymin - ((new_map_height - map_height) / 2)
#             new_ymax = ymax + ((new_map_height - map_height) / 2)
#
#             self.ax.set_extent((new_xmin, new_xmax, new_ymin, new_ymax), crs=self.crs)
#
#         def add_title():
#             """
#             Adds the title box to the plot.
#             :return: None
#             """
#
#             def get_survey_dates():
#                 survey_dates = [pem_file.header.get('Date') for pem_file in self.pem_files]
#                 min_date = min([datetime.strptime(date, '%B %d, %Y') for date in survey_dates])
#                 max_date = max([datetime.strptime(date, '%B %d, %Y') for date in survey_dates])
#                 min_date_text = datetime.strftime(min_date, '%B %d')
#                 max_date_text = datetime.strftime(max_date, '%B %d, %Y')
#                 survey_date_text = f"Survey Date: {min_date_text} - {max_date_text}" if min_date != max_date else f"Survey Date: {max_date_text}"
#                 return survey_date_text
#
#             b_xmin = 0.015  # Title box
#             b_width = 0.30
#             b_ymin = 0.784
#             b_height = 0.200
#             center_pos = b_xmin + (b_width / 2)
#             right_pos = b_xmin + b_width - .01
#             left_pos = b_xmin + .01
#             top_pos = b_ymin + b_height - 0.020
#
#             # Separating lines
#             line_1 = lines.Line2D([b_xmin, b_xmin + b_width], [top_pos - .045, top_pos - .045],
#                                    linewidth=1,
#                                    color='gray',
#                                    transform=self.ax.transAxes,
#                                    zorder=10)
#
#             line_2 = lines.Line2D([b_xmin, b_xmin + b_width], [top_pos - .115, top_pos - .115],
#                                    linewidth=1,
#                                    color='gray',
#                                    transform=self.ax.transAxes,
#                                    zorder=10)
#
#             line_3 = lines.Line2D([b_xmin, b_xmin + b_width], [top_pos - .160, top_pos - .160],
#                                    linewidth=.5,
#                                    color='gray',
#                                    transform=self.ax.transAxes,
#                                    zorder=10)
#
#             # Title box rectangle
#             rect = patches.FancyBboxPatch(xy=(b_xmin, b_ymin),
#                                           width=b_width,
#                                           height=b_height,
#                                           edgecolor='k',
#                                           boxstyle="round,pad=0.005",
#                                           facecolor='white',
#                                           zorder=9,
#                                           transform=self.ax.transAxes)
#
#             client = self.pem_files[0].header.get("Client")
#             grid = self.pem_files[0].header.get("Grid")
#             loops = natsort.humansorted(self.loop_names)
#             hole = self.pem_files[0].header.get('LineHole')
#
#             if 'surface' in self.survey_type:
#                 if self.moving_loop and len(loops) > 1:
#                     survey_text = f"Loop: {loops[0]} to {loops[-1]}"
#                 else:
#                     survey_text = f"Loop: {', '.join(loops)}"
#             else:
#                 survey_text = f"Hole: {hole}    Loop: {', '.join(loops)}"
#
#             coord_sys = f"{self.system}{' Zone ' + self.zone.title() if self.zone else ''}, {self.datum.upper()}"
#             scale = f"1:{self.map_scale:,.0f}"
#
#             self.ax.text(center_pos, top_pos, 'Crone Geophysics & Exploration Ltd.',
#                          fontname='Century Gothic',
#                          fontsize=11,
#                          ha='center',
#                          zorder=10,
#                          transform=self.ax.transAxes)
#
#             self.ax.text(center_pos, top_pos - 0.020, f"{'Line' if 'surface' in self.survey_type else 'Hole'}"
#             f" and Loop Location Map",
#                          family='cursive',
#                          fontname='Century Gothic',
#                          fontsize=10,
#                          ha='center',
#                          zorder=10,
#                          transform=self.ax.transAxes)
#
#             self.ax.text(center_pos, top_pos - 0.040, f"{self.survey_type.title()} Pulse EM Survey",
#                          family='cursive',
#                          style='italic',
#                          fontname='Century Gothic',
#                          fontsize=9,
#                          ha='center',
#                          zorder=10,
#                          transform=self.ax.transAxes)
#
#             self.ax.text(center_pos, top_pos - 0.054, f"{client}\n" + f"{grid}\n"
#             f"{survey_text}",
#                          fontname='Century Gothic',
#                          fontsize=10,
#                          va='top',
#                          ha='center',
#                          zorder=10,
#                          transform=self.ax.transAxes)
#
#             self.ax.text(center_pos, top_pos - 0.124, f"Timebase: {', '.join(self.timebase)} ms\n{get_survey_dates()}",
#                          fontname='Century Gothic',
#                          fontsize=9,
#                          va='top',
#                          ha='center',
#                          zorder=10,
#                          transform=self.ax.transAxes)
#
#             self.ax.text(left_pos, top_pos - 0.167, f"{coord_sys}",
#                          family='cursive',
#                          style='italic',
#                          color='dimgray',
#                          fontname='Century Gothic',
#                          fontsize=8,
#                          va='top',
#                          ha='left',
#                          zorder=10,
#                          transform=self.ax.transAxes)
#
#             self.ax.text(right_pos, top_pos - 0.167, f"Scale {scale}",
#                          family='cursive',
#                          style='italic',
#                          color='dimgray',
#                          fontname='Century Gothic',
#                          fontsize=8,
#                          va='top',
#                          ha='right',
#                          zorder=10,
#                          transform=self.ax.transAxes)
#
#             self.ax.add_patch(rect)
#             shadow = patches.Shadow(rect, 0.002, -0.002)
#             self.ax.add_patch(shadow)
#             self.ax.add_line(line_1)
#             self.ax.add_line(line_2)
#             self.ax.add_line(line_3)
#
#         def add_north_arrow():
#             """
#             Adds the north arrow to the plot. The arrow is manually drawn, and is always fixed in position and size.
#             :return: None
#             """
#
#             def ax_len(pixel_length):  # Calculate the equivalent axes size for a given pixel length
#                 return shaft_len * (pixel_length / 300)  # 267 is pixel length of old north arrow
#
#             l_width = .5
#             top = 0.97
#             bot = 0.81
#             mid = bot + (top - bot) / 2  # Mid point position of the arrow
#             shaft_len = top - bot
#             ca = 0.94  # Alignment of the arrow
#
#             # Drawing full arrow polygon using ax.plot
#             xs = [ca, ca, ca + ax_len(11), ca, ca, ca - ax_len(6), ca - ax_len(6), ca]
#             ys = [top - ax_len(45) + ax_len(8), top, top - ax_len(45), top - ax_len(45) + ax_len(8), bot,
#                   bot - ax_len(12), bot + ax_len((41 - 12)), bot + ax_len(41)]
#             self.ax.plot(xs, ys, color='k', lw=l_width, transform=self.ax.transAxes)
#
#             # Drawing the N
#             xs = [ca - ax_len(12), ca - ax_len(12), ca + ax_len(12), ca + ax_len(12)]  # First N
#             ys = [mid - ax_len(21), mid + ax_len(21), mid - ax_len(30) + ax_len(21), mid + ax_len(21)]  # First N
#             x2s = [ca - ax_len(12), ca + ax_len(12), ca + ax_len(12)]  # Second diagonal line
#             y2s = [mid + ax_len(30) - ax_len(21), mid - ax_len(21),
#                    mid - ax_len(30) + ax_len(21)]  # Second diagonal line
#             self.ax.plot(xs, ys, color='k', lw=l_width, transform=self.ax.transAxes)
#             self.ax.plot(x2s, y2s, color='k', lw=l_width, transform=self.ax.transAxes)
#
#             # Drawing the two side-lines
#             x1 = [ca - ax_len(31) - ax_len(36), ca - ax_len(31)]
#             x2 = [ca + ax_len(31) + ax_len(36), ca + ax_len(31)]
#             y = [mid] * 2
#             tick_line1 = lines.Line2D(x1, y, color='k', lw=l_width, transform=self.ax.transAxes)
#             tick_line2 = lines.Line2D(x2, y, color='k', lw=l_width, transform=self.ax.transAxes)
#
#             self.ax.add_line(tick_line1)
#             self.ax.add_line(tick_line2)
#
#         def add_inset():
#
#             def add_labels():
#                 shpfilename = shpreader.natural_earth(resolution='110m',
#                                                       category='cultural',
#                                                       name='admin_0_countries')
#                 reader = shpreader.Reader(shpfilename)
#                 countries = reader.records()
#
#                 xmin, xmax, ymin, ymax = self.ax_sub.get_extent(crs=ccrs.PlateCarree())
#                 # Try to constrain the text so it doesn't plot outside of ax_sub
#                 xmin = xmin * 1.10 if xmin > 0 else xmin * 0.90
#                 xmax = xmax * 0.90 if xmax > 0 else xmax * 1.10
#                 ymin = ymin * 1.10 if ymin > 0 else ymin * 0.90
#                 ymax = ymax * 0.90 if ymax > 0 else ymax * 1.10
#                 center_x, center_y = ((xmax - xmin) / 2) + xmin, ((ymax - ymin) / 2) + ymin
#                 point = Point(center_x, center_y)
#                 for country in countries:
#                     x = country.geometry.centroid.x
#                     y = country.geometry.centroid.y
#                     if xmin < x < xmax and ymin < y < ymax:
#                         # if country.geometry.contains(point):
#                         name = country.attributes['ABBREV']
#                         # name = country.attributes['POSTAL']
#                         self.ax_sub.text(x, y, name,
#                                          color='k',
#                                          size=7,
#                                          ha='center',
#                                          va='center',
#                                          transform=ccrs.PlateCarree(),
#                                          zorder=2,
#                                          path_effects=[patheffects.withStroke(linewidth=2, foreground="w", alpha=.8)])
#
#             xmin, xmax, ymin, ymax = self.ax.get_extent()
#             center_x, center_y = ((xmax - xmin) / 2) + xmin, ((ymax - ymin) / 2) + ymin
#             lat, lon = utm.to_latlon(center_x, center_y, self.zone, northern=self.north)
#             print(f'Center Easting: {center_x:.0f}, Center Northing: {center_y:.0f}')
#             print(f'Center Lat: {lat:.2f}, Center Lon: {lon:.2f}')
#
#             # self.ax_sub = self.fig.add_axes([0.04, 0.03, 0.24, 0.20],
#             #                                 projection=ccrs.PlateCarree(central_longitude=lon))
#             self.ax_sub = self.fig.add_axes([0.012, 0.04, 0.25, 0.25],
#                                             projection=ccrs.Orthographic(central_longitude=lon, central_latitude=lat))
#             # self.ax_sub = self.fig.add_axes([0.04, 0.03, 0.25, 0.20],
#             #                       projection=ccrs.Mollweide(central_longitude=lon))
#
#             # print(f"Setting inset map extents to : {lat - 30, lat + 30, lon - 20, lon + 20}")
#             # self.ax_sub.set_extent([lon - 35, lon + 35, lat - 20, lat + 20],
#             #                        crs=ccrs.PlateCarree())
#             # self.ax_sub.set_extent([lon - 25, lon + 25, lat - 15, lat + 15],
#             #                        crs=ccrs.PlateCarree())
#
#             self.ax_sub.set_global()
#             self.ax_sub.stock_img()
#             self.ax_sub.coastlines()
#             # self.ax_sub.add_feature(cartopy.feature.OCEAN, zorder=0)
#             # self.ax_sub.add_feature(cartopy.feature.LAND,
#             #                         zorder=0,
#             #                         edgecolor='black',
#             #                         facecolor='gray',
#             #                         alpha=0.2)
#             self.ax_sub.add_feature(feature.BORDERS,
#                                     linewidth=0.4)
#             # other_borders = feature.NaturalEarthFeature(category='cultural',
#             #                                     name='admin_1_states_provinces_lines',
#             #                                     scale='50m',
#             #                                     edgecolors='black',
#             #                                     facecolor='none',
#             #                                     linewidth=0.25)
#             # self.ax_sub.add_feature(other_borders)
#
#             # Plot the X showing the location on the globe
#             self.ax_sub.scatter(lon, lat, s=70,
#                                 marker='X',
#                                 color='pink',
#                                 edgecolors='black',
#                                 zorder=3,
#                                 transform=ccrs.PlateCarree())
#
#             gl = self.ax_sub.gridlines(color='black',
#                                        zorder=1,
#                                        linewidth=0.1,
#                                        draw_labels=False,
#                                        crs=ccrs.PlateCarree())
#             gl.xformatter = LONGITUDE_FORMATTER
#             gl.yformatter = LATITUDE_FORMATTER
#             gl.xlabels_bottom = False
#             gl.ylabels_left = False
#             gl.xlabel_style = {'size': 7, 'color': 'gray'}
#             gl.ylabel_style = {'size': 7, 'color': 'gray'}
#
#             # add_labels()
#
#         def new_get_image(self, tile):
#             """
#             Reimplementation of method in cimgt
#             """
#             if six.PY3:
#                 from urllib.request import urlopen, Request
#             else:
#                 from urllib.request import urlopen
#             url = self._image_url(tile)  # added by H.C. Winsemius
#             req = Request(url)  # added by H.C. Winsemius
#             req.add_header('User-agent', 'your bot 0.1')
#             # fh = urlopen(url)  # removed by H.C. Winsemius
#             fh = urlopen(req)
#             im_data = six.BytesIO(fh.read())
#             fh.close()
#             img = Image.open(im_data)
#
#             img = img.convert(self.desired_tile_form)
#
#             return img, self.tileextent(tile), 'lower'
#
#         self.fig.subplots_adjust(left=0.03, bottom=0.03, right=0.97, top=0.95)
#         set_size()
#         set_scale()
#
#         if self.map_grid:
#             self.ax.grid(linestyle='dotted', zorder=0)
#         else:
#             self.ax.grid(False)
#         self.ax.xaxis.set_visible(True)  # Required to actually get the labels to show in UTM
#         self.ax.yaxis.set_visible(True)
#         self.ax.set_yticklabels(self.ax.get_yticklabels(), rotation=90, ha='center')
#         if self.system == 'UTM':
#             self.ax.yaxis.set_major_formatter(ticker.StrMethodFormatter('{x:,.0f}m N'))
#             self.ax.xaxis.set_major_formatter(ticker.StrMethodFormatter('{x:,.0f}m E'))
#         self.ax.xaxis.set_ticks_position('top')
#         plt.setp(self.ax.get_xticklabels(), fontname='Century Gothic')
#         plt.setp(self.ax.get_yticklabels(), fontname='Century Gothic', va='center')
#
#         if self.scale_bar:
#             add_scale_bar()
#         if self.north_arrow:
#             add_north_arrow()
#         # if self.title_box:
#         #     add_title()
#         add_inset()
#
#         cimgt.OSM.get_image = new_get_image
#         cimgt.Stamen.get_image = new_get_image
#         cimgt.MapQuestOpenAerial.get_image = new_get_image
#         cimgt.GoogleWTS.get_image = new_get_image
#
#         # request = cimgt.Stamen('terrain-background')
#         # request = cimgt.MapQuestOpenAerial()
#         request = cimgt.OSM()
#
#         coastline = feature.NaturalEarthFeature(category='physical',
#                                         name='coastline',
#                                         scale='10m',
#                                         edgecolor='blue',
#                                         facecolor='none')
#         water = feature.NaturalEarthFeature(category='physical',
#                                     name='rivers_lake_centerlines',
#                                     scale='10m',
#                                     edgecolor=feature.COLORS['water'],
#                                     facecolor='none')
#         borders = feature.NaturalEarthFeature(category='cultural',
#                                       name='admin_1_states_provinces_shp',
#                                       scale='10m',
#                                       edgecolor='gray',
#                                       facecolor='none',
#                                       alpha=0.2)
#         # url = 'http://gibs.earthdata.nasa.gov/wmts/epsg4326/best/wmts.cgi'
#         # layer = 'MODIS_Terra_SurfaceReflectance_Bands143'
#         # self.ax.add_feature(cartopy.feature.RIVERS)
#         self.ax.add_feature(coastline)
#         self.ax.add_feature(water)
#         self.ax.add_feature(borders)
#
#         # self.ax.add_image(request, 11, interpolation='spline36')
#         # self.ax.add_wmts(url, layer)
#
#         if self.show_legend:
#             legend_handles = [handle for handle in
#                               [self.loop_handle, self.station_handle, self.collar_handle] if
#                               handle is not None]
#             # Manually add the hole trace legend handle because of the marker angle
#             if self.draw_hole_traces:
#                 legend_handles.append(
#                     lines.Line2D([], [],
#                                   linestyle='--',
#                                   color=self.color,
#                                   marker='|',
#                                   label='Borehole Trace'))
#
#             self.ax.legend(handles=legend_handles,
#                            title='Legend',
#                            loc='lower right',
#                            framealpha=1,
#                            shadow=True,
#                            edgecolor='k')
#
#     def get_map(self):
#         """
#         Retuns the figure if anything is plotted in it.
#         :return: Matplotlib Figure object.
#         """
#         if any([self.loops, self.lines, self.holes]):
#             self.format_figure()
#             return self.fig
#         else:
#             return None


class PEMPrinter:
    """
    Class for printing PEMPLotter plots to PDF.
    Creates a single portrait and a single landscape figure object and re-uses them for all plots.
    :param pem_files: List of PEMFile objects
    :param save_path: Desired save location for the PDFs
    :param kwargs: Plotting kwargs such as hide_gaps, gaps, and x limits used in PEMPlotter.
    """
    def __init__(self, parent=None, **kwargs):
        super().__init__()
        self.parent = parent

        plt.close()  # Close any opened figures. Solves 'Internal C++ object (FigureCanvasQTAgg) already deleted.'
        self.portrait_fig = plt.figure(num=1, clear=True)
        self.portrait_fig.set_size_inches((8.5, 11))
        self.landscape_fig = plt.figure(num=2, clear=True)
        self.landscape_fig.set_size_inches((11, 8.5))

        self.print_plan_maps = kwargs.get('make_plan_map')
        self.print_section_plot = kwargs.get('make_section_plots')
        self.print_lin_plots = kwargs.get('make_lin_plots')
        self.print_log_plots = kwargs.get('make_log_plots')
        self.print_step_plots = kwargs.get('make_step_plots')

        self.crs = kwargs.get('CRS')
        self.share_range = kwargs.get('share_range')
        self.x_min = kwargs.get('x_min')
        self.x_max = kwargs.get('x_max')
        self.hide_gaps = kwargs.get('hide_gaps')
        self.is_moving_loop = kwargs.get('is_moving_loop')
        self.section_depth = kwargs.get('section_depth')

        self.annotate_loop = kwargs.get('annotate_loop')
        self.draw_title_box = kwargs.get('draw_title_box')
        self.draw_grid = kwargs.get('draw_grid')
        self.draw_scale_bar = kwargs.get('draw_scale_bar')
        self.draw_north_arrow = kwargs.get('draw_north_arrow')
        self.draw_legend = kwargs.get('draw_legend')
        self.draw_loops = kwargs.get('draw_loops')
        self.draw_lines = kwargs.get('draw_lines')
        self.draw_collars = kwargs.get('draw_collars')
        self.draw_hole_traces = kwargs.get('draw_hole_traces')
        self.label_loops = kwargs.get('label_loops')
        self.label_lines = kwargs.get('label_lines')
        self.label_collars = kwargs.get('label_collars')
        self.label_hole_depths = kwargs.get('label_hole_depths')
        self.draw_segment_labels = kwargs.get('draw_segment_labels')

    def print_files(self, save_path, files):
        """
        Plot the files to a PDF document
        :param save_path: str, PDF document filepath
        :param files: list of PEMFile and RIFile objects. RI files are optional.
        """
        def save_plots(pem_files, ri_files, x_min, x_max):
            """
            Create the plots and save them as a PDF file
            :param pem_files: list, PEMFile objects to plot
            :param ri_files: optional list, RIFile objects for Step plots
            :param x_min: float, minimum x-axis limit to be shared between all profile plots
            :param x_max: float, maximum x-axis limit to be shared between all profile plots
            """
            global dlg
            if dlg.wasCanceled():
                return

            # Saving the Plan Map. Must have a valid CRS.
            if all([self.crs, self.print_plan_maps is True]):
                if any([pem_file.has_any_gps() for pem_file in pem_files]):
                    dlg.setLabelText(f"Saving plan map for {', '.join([f.line_name for f in pem_files])}")
                    # Plot the plan map
                    plan_map = PlanMap(pem_files, self.landscape_fig, self.crs,
                                       annotate_loop=self.annotate_loop,
                                       is_moving_loop=self.is_moving_loop,
                                       draw_title_box=self.draw_title_box,
                                       draw_grid=self.draw_grid,
                                       draw_scale_bar=self.draw_scale_bar,
                                       draw_north_arrow=self.draw_north_arrow,
                                       draw_legend=self.draw_legend,
                                       draw_loops=self.draw_loops,
                                       draw_lines=self.draw_lines,
                                       draw_collars=self.draw_collars,
                                       draw_hole_traces=self.draw_hole_traces,
                                       label_loops=self.label_loops,
                                       label_lines=self.label_lines,
                                       label_collars=self.label_collars,
                                       label_hole_depth=self.label_hole_depths,
                                       )

                    plan_fig = plan_map.plot()
                    # Save the plot to the PDF file
                    pdf.savefig(plan_fig, orientation='landscape')
                    self.landscape_fig.clf()

                    dlg += 1
                    if dlg.wasCanceled():
                        return
                else:
                    logger.warning('No PEM file has any GPS to plot on the plan map.')

            # Save the Section plot as long as it is a borehole survey. Must have loop, collar GPS and segments.
            if self.print_section_plot is True and pem_files[0].is_borehole():
                if pem_files[0].has_geometry() and pem_files[0].has_collar_gps():
                    dlg.setLabelText(f"Saving section plot for {pem_files[0].line_name}")

                    stations = sorted(set(itertools.chain.from_iterable(
                        [pem_file.get_stations(converted=True) for pem_file in pem_files])))
                    # Plot the section plot
                    section_plotter = SectionPlot()
                    section_fig = section_plotter.plot(pem_files, self.portrait_fig,
                                                       stations=stations,
                                                       hole_depth=self.section_depth,
                                                       label_ticks=self.draw_segment_labels)
                    # Save the plot to the PDF file
                    pdf.savefig(section_fig, orientation='portrait')
                    self.portrait_fig.clear()

                    dlg += 1
                    if dlg.wasCanceled():
                        return
                else:
                    logger.warning('No PEM file has the GPS required to make a section plot.')

            # Saving the LIN plots
            if self.print_lin_plots is True:
                for pem_file in pem_files:
                    # Create the LINPlotter instance
                    lin_plotter = LINPlotter(pem_file, self.portrait_fig,
                                             x_min=x_min,
                                             x_max=x_max,
                                             hide_gaps=self.hide_gaps)
                    components = pem_file.get_components()
                    if 'Z' in components:
                        components.pop(components.index('Z'))
                        components.insert(0, 'Z')

                    for component in components:
                        dlg.setLabelText(f"Saving LIN plot for {pem_file.line_name}, component {component}")

                        # Configure the figure since it gets cleared after each plot
                        self.configure_lin_fig()

                        # Plot the LIN profile
                        plotted_fig = lin_plotter.plot(component)

                        # Save the figure to the PDF
                        pdf.savefig(plotted_fig, orientation='portrait')

                        self.portrait_fig.clear()

                        dlg += 1
                        if dlg.wasCanceled():
                            return

            # Saving the LOG plots
            if self.print_log_plots is True:
                for pem_file in pem_files:
                    # Create the LOGPlotter instance
                    log_plotter = LOGPlotter(pem_file, self.portrait_fig,
                                             x_min=x_min,
                                             x_max=x_max,
                                             hide_gaps=self.hide_gaps)
                    components = pem_file.get_components()
                    if 'Z' in components:
                        components.pop(components.index('Z'))
                        components.insert(0, 'Z')

                    for component in components:
                        dlg.setLabelText(f"Saving LOG plot for {pem_file.line_name}, component {component}")

                        # Configure the figure since it gets cleared after each plot
                        self.configure_log_fig()

                        # Plot the LOG profile
                        plotted_fig = log_plotter.plot(component)

                        # Save the figure to the PDF
                        pdf.savefig(plotted_fig, orientation='portrait')
                        self.portrait_fig.clear()

                        dlg += 1
                        if dlg.wasCanceled():
                            return

            # Saving the STEP plots. Must have RI files associated with the PEM file.
            if self.print_step_plots is True:
                for pem_file, ri_file in zip(pem_files, ri_files):
                    if ri_file:
                        step_plotter = STEPPlotter(pem_file, ri_file, self.portrait_fig,
                                                   x_min=x_min,
                                                   x_max=x_max,
                                                   hide_gaps=self.hide_gaps)
                        components = pem_file.get_components()
                        if 'Z' in components:
                            components.pop(components.index('Z'))
                            components.insert(0, 'Z')

                        for component in components:
                            dlg.setLabelText(f"Saving STEP plot for {pem_file.line_name}, component {component}")

                            self.configure_step_fig()

                            # Plot the step profile
                            plotted_fig = step_plotter.plot(component)

                            # Save the plot to the PDF file
                            pdf.savefig(plotted_fig, orientation='portrait')
                            self.portrait_fig.clear()

                            dlg += 1
                            if dlg.wasCanceled():
                                return
                    else:
                        logger.warning(f"No RI file to go with {pem_file.filepath.name}.")

        def count_pdf_pages(bhs, grids):
            """
            Calculate the progress bar maximum value. I.E. calculates how many PDF pages will be made.
            :param bhs: Dict of unique borehole surveys (different hole name and loop name)
            :param grids: Dict of unique surface grids (different loop names)
            :return: int, number of PDF pages
            """
            total_count = 0

            if bhs:
                for survey, files in bhs.items():
                    num_plots = sum([len(file[0].get_components()) for file in files])
                    if self.print_plan_maps:
                        if any([file[0].has_any_gps() for file in files]):
                            total_count += 1
                    if self.print_section_plot:
                        if any([file[0].has_collar_gps() and file[0].has_geometry() and file[0].has_loop_gps() for file
                                in files]):
                            total_count += 1
                    if self.print_lin_plots:
                        total_count += num_plots
                    if self.print_log_plots:
                        total_count += num_plots
                    if self.print_step_plots:
                        if all([file[1] for file in files]):
                            total_count += num_plots

            if grids:
                for loop, lines in grids.items():
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

            logger.info(f"Number of PDF pages: {total_count}")
            return total_count

        files = files  # Zipped PEM and RI files
        save_path = save_path

        unique_bhs = defaultdict()
        unique_grids = defaultdict()

        bh_files = [(pem, ri) for pem, ri in files if pem.is_borehole()]
        sf_files = [(pem, ri) for pem, ri in files if not pem.is_borehole()]

        if any(bh_files):
            bh_files.sort(key=lambda x: x[0].get_components(), reverse=True)
            bh_files = natsort.humansorted(bh_files, key=lambda x: x[0].loop_name)
            bh_files = natsort.humansorted(bh_files, key=lambda x: x[0].line_name)

        if any(sf_files):
            sf_files.sort(key=lambda x: x[0].get_components(), reverse=True)
            sf_files = natsort.humansorted(sf_files, key=lambda x: x[0].line_name)
            sf_files = natsort.humansorted(sf_files, key=lambda x: x[0].loop_name)

        # Group the files by unique surveys i.e. each entry is the same borehole and same loop
        for survey, files in itertools.groupby(bh_files, key=lambda x: (x[0].line_name, x[0].loop_name)):
            unique_bhs[survey] = list(files)

        # Group the files by unique surveys i.e. each entry is the same borehole and same loop
        for loop, files in itertools.groupby(sf_files, key=lambda x: x[0].loop_name):
            unique_grids[loop] = list(files)

        num_pages = count_pdf_pages(unique_bhs, unique_grids)  # for the progress bar
        with PdfPages(save_path + '.PDF') as pdf:
            global dlg
            with CustomProgressDialog("Printing PDFs..", 0, num_pages, busyCursor=True) as dlg:
                # Save the borehole PDFs
                for survey, files in unique_bhs.items():

                    if dlg.wasCanceled():
                        break

                    pem_files = [pair[0] for pair in files]
                    ri_files = [pair[1] for pair in files]

                    if self.x_min is None and self.share_range is True:
                        x_min = min([min(f.get_stations(converted=True)) for f in pem_files])
                    else:
                        x_min = self.x_min
                    if self.x_max is None and self.share_range is True:
                        x_max = max([max(f.get_stations(converted=True)) for f in pem_files])
                    else:
                        x_max = self.x_max

                    save_plots(pem_files, ri_files, x_min, x_max)

                # Save the surface PDFs
                for loop, files in unique_grids.items():

                    if dlg.wasCanceled():
                        break

                    pem_files = [pair[0] for pair in files]
                    ri_files = [pair[1] for pair in files]
                    if self.x_min is None and self.share_range is True:
                        x_min = min([min(f.get_stations(converted=True)) for f in pem_files])
                    else:
                        x_min = self.x_min
                    if self.x_max is None and self.share_range is True:
                        x_max = max([max(f.get_stations(converted=True)) for f in pem_files])
                    else:
                        x_max = self.x_max

                    save_plots(pem_files, ri_files, x_min, x_max)

        plt.close(self.portrait_fig)
        plt.close(self.landscape_fig)
        # os.startfile(save_path + '.PDF')

    def configure_lin_fig(self):
        """
        Add the subplots for a lin plot
        """
        self.portrait_fig, (ax1, ax2, ax3, ax4, ax5) = plt.subplots(5, 1, num=1, sharex=True, clear=True)
        ax6 = ax5.twiny()
        ax6.get_shared_x_axes().join(ax5, ax6)

    def configure_log_fig(self):
        """
        Configure the log plot axes
        """
        self.portrait_fig, ax = plt.subplots(1, 1, num=1, clear=True)
        ax2 = ax.twiny()
        ax2.get_shared_x_axes().join(ax, ax2)
        plt.yscale('symlog', linthreshy=10, linscaley=1. / math.log(10), subs=list(np.arange(2, 10, 1)))

    def configure_step_fig(self):
        """
        Configure the step plot figure
        """
        self.portrait_fig, (ax1, ax2, ax3, ax4) = plt.subplots(4, 1, num=1, sharex='all', clear=True)
        ax5 = ax4.twiny()
        ax5.get_shared_x_axes().join(ax4, ax5)


if __name__ == '__main__':
    from PySide2.QtWidgets import QApplication
    from src.pem.pem_file import PEMParser

    app = QApplication(sys.argv)
    pem_getter = PEMGetter()
    # pem_files = pem_getter.get_pems(folder='RI files', subfolder=r"PEMPro RI and Suffix Error Files/KBNorth", file="2200EAv KBNorth.PEM")
    # pem_files = [PEMParser().parse(r"C:\_Data\2021\TMC\131-21-38\Final\131-21-38 XYT.PEM")]
    # pem_files = pem_getter.get_pems(folder="Raw Surface", subfolder=r"Loop L\Final", file="100E.PEM")
    pem_files = pem_getter.get_pems(folder="Raw Surface\Barraute B\Final", file="3400E.PEM")
    # editor = PEMPlotEditor(pem_files[0])
    # editor.show()
    # planner = LoopPlanner()

    # map_fig = plt.figure(figsize=(11, 8.5), num=2, clear=True)
    # # map_plot = PlanMap(pem_files, map_fig, CRS.from_epsg(32644)).plot()
    # map_plot = PlanMap(pem_files, map_fig, pem_files[0].get_crs()).plot()
    # plt.show()

    # fig = plt.figure(figsize=(8.5, 11), dpi=100)
    # sp = SectionPlot()
    # sp.plot(pem_files[0], figure=fig)
    # plt.show()

    lin_fig, (ax1, ax2, ax3, ax4, ax5) = plt.subplots(5, 1, num=1, sharex=True, clear=True, figsize=(8.5, 11))
    ax6 = ax5.twiny()
    ax6.get_shared_x_axes().join(ax5, ax6)
    # pem = r'C:\_Data\2021\Eastern\Maritime Resources\Final\0E.PEM'
    lin_plot = LINPlotter(pem_files[0], lin_fig)
    lin_plot.plot('X')
    lin_plot.plot('Y')
    plt.show()

    # log_fig, ax = plt.subplots(1, 1, num=1, clear=True, figsize=(8.5, 11))
    # ax2 = ax.twiny()
    # ax2.get_shared_x_axes().join(ax, ax2)
    # plt.yscale('symlog', linthresh=10, linscale=1. / math.log(10), subs=list(np.arange(2, 10, 1)))
    # log_plot = LOGPlotter(pem_files[0], log_fig)
    # log_plot.plot('X')
    # plt.show()

    # step_fig, (ax1, ax2, ax3, ax4) = plt.subplots(4, 1, num=1, sharex=True, clear=True, figsize=(8.5, 11))
    # ax5 = ax4.twiny()
    # ax5.get_shared_x_axes().join(ax4, ax5)
    # # pem = r'C:\Users\Mortulo\PycharmProjects\PEMPro\sample_files\RI files\246-01NAv.PEM'
    # # ri = r'C:\Users\Mortulo\PycharmProjects\PEMPro\sample_files\RI files\246-01N.RI2'
    # pem = r'C:\_Data\2021\Nantou BF\Surface\Loop 4\Final\16200e.pem'  # Step near 0
    # ri = r'C:\_Data\2021\Nantou BF\Surface\Loop 4\Final\16200E.ri3'
    # step_plot = STEPPlotter(pem, ri, step_fig)
    # step_plot.plot('Z')
    # plt.show()

    # map = GeneralMap(pem_files, fig).get_map()
    # map.show()
    # ax = fig.add_subplot()
    # component = 'z'
    # channel = 15
    # contour = ContourMap()
    # contour.plot_contour(ax, pem_files, component, channel)
    # plt.show()
    # printer = PEMPrinter(sample_files_dir, pem_files)
    # printer.print_final_plots()
    app.exec_()
