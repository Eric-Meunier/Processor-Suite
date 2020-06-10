from src.pem._legacy.pem_parser import PEMParser
import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from matplotlib import patches
import numpy as np
import math
import re
import os
from scipy import interpolate
from scipy import stats
import logging
import cProfile

# plt.style.use('seaborn-white')
# plt.style.use('bmh')
# plt.style.use('ggplot')

mpl.rcParams['path.simplify'] = True
mpl.rcParams['path.simplify_threshold'] = 1.0
mpl.rcParams['agg.path.chunksize'] = 10000
mpl.rcParams["figure.autolayout"] = False
mpl.rcParams['lines.linewidth'] = 0.5
mpl.rcParams['lines.color'] = '#1B2631'
mpl.rcParams['font.size'] = 9
mpl.rcParams['font.sans-serif'] = 'Tahoma'
# mplstyle.use(['seaborn-paper', 'fast'])  #Enabling this will override some of the above settings.

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s', datefmt='%d-%b-%y %H:%M:%S')


class PEMFileEditor:
    """
    Class for making edits to PEM_Files
    """

    def __init__(self):
        self.active_file = None
        self.parser = PEMParser()

    def open_file(self, file_path):
        """
        Sets the active file. All subsequent operations will be done on the file contained at file_path.
        :param file_path: string containing path to a PEM file
        """
        self.active_file = self.parser.parse(file_path)

    # File plotting functions
    def generate_plots(self, **kwargs):
        """
        :return: A list of matplotlib.figure objects representing the data found inside of the active file
        """
        logging.info("Generating plots...")

        lin_figs, log_figs = self.make_plots(**kwargs)
        logging.info("Finished generating plots")
        return lin_figs, log_figs

    def get_stations(self):
        """
        Converts all the station names in the data into a number, negative if the stations was S or W
        :param data: Dictionary of data from a PEM file
        :return: Dictionary of data for a PEM file with the station numbers now integers
        """
        data = self.active_file.get_data()
        stations = [d['Station'] for d in data]

        return [self.convert_station(station) for station in stations]

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

    def get_profile_data(self, component_data):
        """
        Transforms the data so it is ready to be plotted for LIN and LOG plots
        :param component_data: Data (dict) for a single component (i.e. Z, X, or Y)
        :return: Dictionary where each key is a channel, and the values of those keys are a list of
        dictionaries which contain the stations and readings of all readings of that channel
        """
        profile_data = {}
        num_channels = len(component_data[0]['Data'])

        for channel in range(0, num_channels):
            # profile_data[channel] = {}
            channel_data = []

            for i, station in enumerate(component_data):
                reading = station['Data'][channel]
                station_number = int(self.convert_station(station['Station']))
                channel_data.append({'Station': station_number, 'Reading': reading})

            profile_data[channel] = channel_data

        return profile_data

    def get_channel_data(self, channel, profile_data):
        """
        Get the profile-mode data for a given channel
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

    def calc_gaps(self, survey_type, stations, gap):
        # survey_type = self.active_file.survey_type

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

    def get_interp_data(self, survey_type, profile_data, stations, segments, hide_gaps, gap, interp_method='linear'):
        """
        Interpolates the data using 1-D piecewise linear interpolation. The data is segmented
        into 100 segments.
        :param profile_data: The EM data in profile mode
        :param stations: The stations of the EM data
        :return: The interpolated data and stations
        """
        survey_type = survey_type
        stations = np.array(stations, dtype='float64')
        readings = np.array(profile_data, dtype='float64')
        x_intervals = np.linspace(stations[0], stations[-1], segments)
        f = interpolate.interp1d(stations, readings, kind='linear')

        interpolated_y = f(x_intervals)

        if hide_gaps:
            gap_intervals = self.calc_gaps(survey_type, stations, gap)

            # Masks the intervals that are between gap[0] and gap[1]
            for gap in gap_intervals:
                interpolated_y = np.ma.masked_where((x_intervals > gap[0]) & (x_intervals < gap[1]),
                                                    interpolated_y)

        return interpolated_y, x_intervals

    def make_LINLOG_plots(self, **kwargs):
        def get_kwargs():
            try:
                kwargs['Client']
            except KeyError:
                kwargs['Client'] = header['Client']
            else:
                if kwargs['Client'] is None:
                    kwargs['Client'] = header['Client']

            try:
                kwargs['Grid']
            except KeyError:
                kwargs['Grid'] = header['Grid']
            else:
                if kwargs['Grid'] is None:
                    kwargs['Grid'] = header['Grid']

            try:
                kwargs['Loop']
            except KeyError:
                kwargs['Loop'] = header['Loop']
            else:
                if kwargs['Loop'] is None:
                    kwargs['Loop'] = header['Loop']

            try:
                kwargs['lbound']
            except KeyError:
                kwargs['lbound'] = None

            try:
                kwargs['rbound']
            except KeyError:
                kwargs['rbound'] = None

            try:
                kwargs['HideGaps']
            except KeyError:
                kwargs['HideGaps'] = True

            try:
                kwargs['Gap']
            except KeyError:
                kwargs['Gap'] = None

            try:
                kwargs['Interp']
            except KeyError:
                kwargs['Interp'] = 'linear'

        file = self.active_file
        header = file.get_header()
        tags = file.get_tags()
        components = file.components

        kwargs['Units'] = 'nT/s' if tags['Units'].casefold() == 'nanotesla/sec' else 'pT'
        kwargs['SurveyType'] = file.survey_type
        kwargs['Current'] = tags['Current']

        get_kwargs()

        lin_figs = []
        log_figs = []

        for component in components:
            component_data = list(filter(lambda d: d['Component'] == component, self.active_file.get_data()))
            lin_fig = CroneFigure(component_data, component, header, **kwargs).plot_lin()
            log_fig = CroneFigure(component_data, component, header, **kwargs).plot_log()
            lin_figs.append(lin_fig)
            log_figs.append(log_fig)
        return lin_figs, log_figs


class CroneFigure:
    """
    Class for creating Crone LIN and LOG figures.
    Probably for STP figures in the future too.
    """
    def __init__(self, component_data, component, header, **kwargs):
        super().__init__()
        self.editor = PEMFileEditor()
        self.kwargs = kwargs
        self.data = component_data
        self.profile_data = self.editor.get_profile_data(self.data)
        self.header = header
        self.component = component
        self.stations = [self.editor.convert_station(station['Station']) for station in self.data]
        self.x_limit = min(self.stations) if kwargs['lbound'] is None else kwargs['lbound'], max(self.stations) if \
            kwargs['rbound'] is None else kwargs['rbound']
        self.num_channels = int(self.header['NumChannels']) + 1
        self.units = self.kwargs['Units']
        self.line_colour = '#1B2631'
        self.lin_fig = None
        self.log_fig = None

    def format_figure(self, figure):
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
                plt.setp(ax.get_xticklabels(), visible=True, size=12)

        plt.subplots_adjust(left=0.135, bottom=0.07, right=0.958, top=0.885)
        self.add_rectangle()

        for ax in axes:
            format_spines(ax)

    def format_xaxis(self, figure):
        """
        Formats the X axis of a figure
        :param figure: LIN or LOG figure objects
        """
        x_label_locator = ticker.AutoLocator()
        major_locator = ticker.FixedLocator(self.stations)
        plt.xlim(self.x_limit)
        figure.axes[0].xaxis.set_major_locator(major_locator) # for some reason this seems to apply to all axes
        figure.axes[-1].xaxis.set_major_locator(x_label_locator)

    def create_lin_figure(self):
        """
        Creates the blank LIN figure
        """
        lin_fig, (ax1, ax2, ax3, ax4, ax5) = plt.subplots(5, 1, figsize=(8.5, 11), sharex=True)
        ax6 = ax5.twiny()
        ax6.get_shared_x_axes().join(ax5, ax6)

        self.lin_fig = lin_fig
        self.format_figure(self.lin_fig)

    def plot_lin(self):
        """
        Plots the data into the LIN figure
        """
        def calc_channel_bounds():
            # channel_bounds is a list of tuples showing the inclusive bounds of each data plot
            channel_bounds = [None] * 4
            num_channels_per_plot = int((self.num_channels - 1) // 4)
            remainder_channels = int((self.num_channels - 1) % 4)

            for k in range(0, len(channel_bounds)):
                channel_bounds[k] = (k * num_channels_per_plot + 1, num_channels_per_plot * (k + 1))

            for i in range(0, remainder_channels):
                channel_bounds[i] = (channel_bounds[i][0], (channel_bounds[i][1] + 1))
                for k in range(i + 1, len(channel_bounds)):
                    channel_bounds[k] = (channel_bounds[k][0] + 1, channel_bounds[k][1] + 1)

            channel_bounds.insert(0, (0, 0))
            return channel_bounds

        def add_ylabels():
            for i in range(len(self.lin_fig.axes)-1):
                ax = self.lin_fig.axes[i]
                if i == 0:
                    ax.set_ylabel('Primary Pulse' + "\n(" + self.units + ")")
                else:
                    ax.set_ylabel("Channel " + str(channel_bounds[i][0]) + " - " +
                                   str(channel_bounds[i][1]) + "\n(" + self.units + ")")

        if not self.lin_fig:
            self.create_lin_figure()

        channel_bounds = calc_channel_bounds()

        for i, group in enumerate(channel_bounds):
            ax = self.lin_fig.axes[i]
            self.draw_lines(ax, group[0], group[1])

        self.add_title()
        add_ylabels()
        self.format_yaxis(self.lin_fig)
        self.format_xaxis(self.lin_fig)

        return self.lin_fig

    def create_log_figure(self):
        """
        Creates an empty but formatted LOG figure
        """
        log_fig, ax = plt.subplots(1, 1, figsize=(8.5, 11))
        ax2 = ax.twiny()
        ax2.get_shared_x_axes().join(ax, ax2)
        plt.yscale('symlog', linthreshy=10, linscaley=1. / math.log(10), subsy=list(np.arange(2, 10, 1)))

        self.log_fig = log_fig
        self.format_figure(self.log_fig)

    def plot_log(self):
        """
        Plots the data into the LOG figure
        :return:
        """
        def add_ylabel():
            ax = self.log_fig.axes[0]
            ax.set_ylabel('Primary Pulse to Channel ' + str(self.num_channels-1) + "\n(" + self.units + ")")

        if not self.log_fig:
            self.create_log_figure()

        ax = self.log_fig.axes[0]

        self.draw_lines(ax, 0, self.num_channels-1)
        self.add_title()
        add_ylabel()
        self.format_yaxis(self.log_fig)
        self.format_xaxis(self.log_fig)

        return self.log_fig

    def draw_lines(self, ax, channel_low, channel_high):
        """
        Plots the lines into an axes of a figure
        :param ax: Axes of a figure, either LIN or LOG figure objects
        :param channel_low: The first channel to be plotted
        :param channel_high: The last channel to be plotted
        """
        segments = 1000  # The data will be broken in this number of segments
        offset = segments * 0.1  # Used for spacing the annotations

        for k in range(channel_low, (channel_high + 1)):
            # Gets the profile data for a single channel, along with the stations
            channel_data, stations = self.editor.get_channel_data(k, self.profile_data)

            # Interpolates the channel data, also returns the corresponding x intervals
            interp_data, x_intervals = self.editor.get_interp_data(self.kwargs['SurveyType'],channel_data, stations, segments,
                                                            self.kwargs['HideGaps'], self.kwargs['Gap'],
                                                            self.kwargs['Interp'])

            ax.plot(x_intervals, interp_data, color=self.line_colour)

            # Mask is used to hide data within gaps
            mask = np.isclose(interp_data, interp_data.astype('float64'))
            x_intervals = x_intervals[mask]
            interp_data = interp_data[mask]

            # Annotating the lines
            for i, x_position in enumerate(x_intervals[int(offset)::int(len(x_intervals) * 0.4)]):
                y = interp_data[list(x_intervals).index(x_position)]

                if k == 0:
                    ax.annotate('PP', xy=(x_position, y), xycoords="data", size=7.5, color=self.line_colour,
                                va='center_baseline', ha='center')

                else:
                    ax.annotate(str(k), xy=(x_position, y), xycoords="data", size=7.5, color=self.line_colour,
                                va='center_baseline', ha='center')

            offset += len(x_intervals) * 0.15

            if offset >= len(x_intervals) * 0.85:
                offset = len(x_intervals) * 0.10

    def format_yaxis(self, figure):
        """
        Formats the Y axis of a figure
        :param figure: LIN or LOG figure object
        """
        axes = figure.axes

        for ax in axes:
            ax.get_yaxis().set_label_coords(-0.08, 0.5)

            if ax.get_yscale() != 'symlog':
                y_limits = ax.get_ylim()

                if (y_limits[1] - y_limits[0]) < 3:
                    new_high = math.ceil(((y_limits[1] - y_limits[0]) / 2) + 1)
                    new_low = new_high * -1
                    ax.set_ylim(new_low, new_high)
                    ax.set_yticks(ax.get_yticks())

                elif ax != axes[-1]:
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

            ax.yaxis.set_major_formatter(ticker.FormatStrFormatter('%d'))

    def add_title(self):
        """
        Adds the title header to a figure
        """

        timebase_freq = ((1 / (float(self.header['Timebase']) / 1000)) / 4)

        if 'borehole' in self.kwargs['SurveyType'].casefold():
            s_title = 'Hole'
        else:
            s_title = 'Line'

        plt.figtext(0.550, 0.960, 'Crone Geophysics & Exploration Ltd.',
                    fontname='Century Gothic', fontsize=11, ha='center')

        plt.figtext(0.550, 0.945, self.kwargs['SurveyType'] + ' Pulse EM Survey', family='cursive', style='italic',
                    fontname='Century Gothic', fontsize=10, ha='center')

        plt.figtext(0.145, 0.935, 'Timebase: ' + str(self.header['Timebase']) + ' ms\n' +
                    'Base Frequency: ' + str(round(timebase_freq, 2)) + ' Hz\n' +
                    'Current: ' + str(round(float(self.kwargs['Current']), 1)) + ' A',
                    fontname='Century Gothic', fontsize=10, va='top')

        plt.figtext(0.550, 0.935, s_title + ': ' + self.header['LineHole'] + '\n'
                    + self.component + ' Component' + '\n'
                    + 'Loop: ' + self.kwargs['Loop'],
                    fontname='Century Gothic', fontsize=10, va='top', ha='center')

        plt.figtext(0.955, 0.935,
                    self.kwargs['Client'] + '\n' + self.kwargs['Grid'] + '\n' + self.header['Date'] + '\n',
                    fontname='Century Gothic', fontsize=10, va='top', ha='right')

    def add_rectangle(self):
        """
        Draws a rectangle around a figure object
        """
        fig = plt.gcf()
        rect = patches.Rectangle(xy=(0.02, 0.02), width=0.96, height=0.96, linewidth=0.7, edgecolor='black',
                                 facecolor='none', transform=fig.transFigure)
        fig.patches.append(rect)

    # def mk_qt_plot(self):
    #     import pyqtgraph as pg
    #     pg.setConfigOption('background', 'w')
    #
    #     file = self.active_file
    #     # Header info mostly just for the title of the plots
    #     # TODO Negative coil area in PEM file breaks the parsing
    #     header = file.get_header()
    #     tags = file.get_tags()
    #     client = header['Client']
    #     loop = header['Loop']
    #     linehole = header['LineHole']
    #     date = header['Date']
    #     grid = header['Grid']
    #     current = float(tags['Current'])
    #     timebase = float(header['Timebase'])
    #     timebase_freq = ((1 / (timebase / 1000)) / 4)
    #     survey_type = self.get_survey_type()
    #     num_channels = int(header['NumChannels']) + 1  # +1 because the header channel number is only offtime
    #     units = file.get_tags()['Units']
    #
    #     if 'borehole' in survey_type.casefold():
    #         s_title = 'Hole'
    #     else:
    #         s_title = 'Line'
    #
    #     if units.casefold() == 'nanotesla/sec':
    #         units = 'nT/s'
    #     elif 'picotesla' in units.casefold():
    #         units = 'pT'
    #     else:
    #         units = "UNDEF_UNIT"
    #
    #     data = sorted(self.convert_stations(file.get_data()), key=lambda k: k['Station'])
    #     components = self.get_components(data)
    #
    #     for component in components:
    #         component_data = list(filter(lambda d: d['Component'] == component, data))
    #         profile_data = self.get_profile_data(component_data)
    #         stations = [station['Station'] for station in component_data]
    #         x_limit = min(stations), max(stations)

    # Legacy function, leave as reference
    # def generate_placeholder_plots(self):
    #     """
    #     :return: A list of matplotlib.figure objects representing the data found inside of the active file
    #     """
    #     # Temporary placeholder plots
    #     # Use as guide for creating generate_plots
    #     plots_dict = OrderedDict()
    #
    #     for reading in self.active_file.get_data():
    #         station_number = reading['Station']
    #
    #         if station_number not in plots_dict:
    #             fig = Figure()
    #             ax = fig.add_subplot(111)
    #             ax.set_title('Station ' + str(station_number))
    #             ax.set_xlabel('Channel Number (By Index)')
    #             ax.set_ylabel('Amplitude (' + self.active_file.get_tags()['Units'] + ')')
    #             fig.subplots_adjust(bottom=0.15)
    #
    #             plots_dict[station_number] = {'fig': fig}
    #             plots_dict[station_number]['ax'] = ax
    #
    #         ax = plots_dict[station_number]['ax']
    #         y = reading['Data']
    #         ax.plot(range(len(y)), y, '-', linewidth=0.8)
    #
    #     plots = [plot_data['fig'] for station_number, plot_data in plots_dict.items()]
    #     return plots


if __name__ == "__main__":
    # Code to test PEMFileEditor
    editor = PEMFileEditor()
    testing_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), "../../sample_files/9600NAv LP-100.PEM")
    editor.open_file(testing_file)
    # editor.make_plots()
    # editor.generate_plots()
    cProfile.run('editor.make_plots()', sort='cumtime')
    # plt.show()

