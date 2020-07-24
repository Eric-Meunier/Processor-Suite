import sys
import os
import copy
import math
import numpy as np
import time
from PyQt5 import (QtCore, QtGui, uic)
from PyQt5.QtWidgets import (QMainWindow, QApplication, QMessageBox, QRadioButton, QGridLayout,
                             QLabel, QLineEdit, QShortcut, QTableWidgetItem)
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from src.pem.pem_plotter import LINPlotter, LOGPlotter
import pyqtgraph as pg

sys._excepthook = sys.excepthook


def exception_hook(exctype, value, traceback):
    print(exctype, value, traceback)
    sys._excepthook(exctype, value, traceback)
    sys.exit(1)


sys.excepthook = exception_hook

# Modify the paths for when the script is being run in a frozen state (i.e. as an EXE)
if getattr(sys, 'frozen', False):
    application_path = sys._MEIPASS
    icons_path = 'icons'
    derotatorCreatorFile = 'qt_ui\\derotator.ui'
else:
    application_path = os.path.dirname(os.path.abspath(__file__))
    icons_path = os.path.join(os.path.dirname(application_path), "qt_ui\\icons")
    derotatorCreatorFile = os.path.join(os.path.dirname(application_path), 'qt_ui\\derotator.ui')

# Load Qt ui file into a class
Ui_Derotator, QtBaseClass = uic.loadUiType(derotatorCreatorFile)

pg.setConfigOptions(antialias=True)
pg.setConfigOption('background', 'w')
pg.setConfigOption('foreground', 'k')
pg.setConfigOption('crashWarning', True)


class Derotator(QMainWindow, Ui_Derotator):
    """
    Class that de-rotates XY data of a PEMFile
    """
    accept_sig = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__()
        self.setupUi(self)
        self.parent = parent
        self.pem_file = None
        self.rotated_file = None
        self.pp_plotted = False
        self.rotation_note = None

        self.acc_rotated_file = None
        self.mag_rotated_file = None
        self.pp_rotated_file = None

        self.setWindowTitle('XY De-rotation')
        self.setWindowIcon(QtGui.QIcon(os.path.join(icons_path, 'derotate.png')))

        self.message = QMessageBox()

        self.button_box.accepted.connect(lambda: self.accept_sig.emit())
        self.button_box.rejected.connect(self.close)

        self.acc_btn.clicked.connect(self.rotate)
        self.mag_btn.clicked.connect(self.rotate)
        self.pp_btn.clicked.connect(self.rotate)
        self.none_btn.clicked.connect(self.rotate)
        self.soa_sbox.editingFinished.connect(self.rotate)

        self.reset_range_shortcut = QShortcut(QtGui.QKeySequence(' '), self)
        self.reset_range_shortcut.activated.connect(self.reset_range)

        self.change_component_shortcut = QShortcut(QtGui.QKeySequence('c'), self)
        self.change_component_shortcut.activated.connect(self.change_tab)

        self.bad_stations_label.hide()
        self.list.hide()

        self.statusBar().hide()

        # Configure the plots
        self.x_view.ci.layout.setSpacing(10)  # Spacing between plots
        self.x_ax0 = self.x_view.addPlot(0, 0)
        self.x_ax1 = self.x_view.addPlot(1, 0)
        self.x_ax2 = self.x_view.addPlot(2, 0)
        self.x_ax3 = self.x_view.addPlot(3, 0)
        self.x_ax4 = self.x_view.addPlot(4, 0)

        self.x_view_axes = [self.x_ax0, self.x_ax1, self.x_ax2, self.x_ax3, self.x_ax4]

        for ax in self.x_view_axes[1:]:
            ax.setXLink(self.x_ax0)

        # Configure the lin plot
        self.y_view.ci.layout.setSpacing(10)  # Spacing between plots
        self.y_ax0 = self.y_view.addPlot(0, 0)
        self.y_ax1 = self.y_view.addPlot(1, 0)
        self.y_ax2 = self.y_view.addPlot(2, 0)
        self.y_ax3 = self.y_view.addPlot(3, 0)
        self.y_ax4 = self.y_view.addPlot(4, 0)

        self.y_view_axes = [self.y_ax0, self.y_ax1, self.y_ax2, self.y_ax3, self.y_ax4]

        for ax in self.y_view_axes[1:]:
            ax.setXLink(self.y_ax0)

        self.axes = np.concatenate([self.x_view_axes, self.y_view_axes])
        # Disable the 'A' button and auto-scaling SI units
        for ax in self.axes:
            ax.hideButtons()
            ax.getAxis('left').enableAutoSIPrefix(enable=False)

        # Create the rotation angle plot
        self.rot_ax = self.rotation_view.addPlot(0, 0)
        self.rot_ax.invertY(True)
        self.rot_ax.showGrid(x=False, y=True, alpha=0.3)
        self.rot_ax_legend = self.rot_ax.addLegend(pen='k', brush='w')
        self.rot_ax_legend.setParent(self.rotation_view)
        # legend.anchor((0, 0), (0.6, 0.01))
        self.rot_ax.hideAxis('bottom')
        self.rot_ax.showAxis('top')
        self.rot_ax.setLabel('top', 'Rotation Angle', units='Degrees')
        self.rot_ax.setLabel('left', 'Station', units=None)
        self.rot_ax.getAxis('top').enableAutoSIPrefix(enable=False)

        # Create the pp values plot
        self.pp_ax = self.pp_view.addPlot(0, 0)
        self.pp_ax.invertY(True)
        self.pp_ax.showGrid(x=False, y=True, alpha=0.3)
        self.pp_ax_legend = self.pp_ax.addLegend(pen='k', brush='w')
        self.pp_ax_legend.setParent(self.pp_view)
        # self.pp_ax_legend.anchor((0, 0), (0.6, 0.01))
        self.pp_ax.hideAxis('bottom')
        self.pp_ax.showAxis('top')
        self.pp_ax.setLabel('top', 'Magnetic Field Strength', units='nT/s')
        self.pp_ax.setLabel('left', 'Station', units=None)
        self.pp_ax.getAxis('top').enableAutoSIPrefix(enable=False)

    def reset_range(self):
        """
        Reset the range of each plot
        """
        for ax in self.axes:
            ax.autoRange()

    def change_tab(self):
        """
        Alternate between component plots
        """
        if self.tab_widget.currentIndex() == 0:
            self.tab_widget.setCurrentIndex(1)
        else:
            self.tab_widget.setCurrentIndex(0)

    def open(self, pem_file):
        """
        Open, rotate, and plot the PEMFile.
        :param pem_file: borehole PEMFile object
        """
        assert pem_file, 'Invalid PEM file'

        while isinstance(pem_file, list):
            pem_file = pem_file[0]

        if all([pem_file.is_borehole(), 'X' in pem_file.get_components(), 'Y' in pem_file.get_components()]):
            self.pem_file = pem_file
        else:
            self.message.information(self, 'Ineligible File',
                                     'File must be a borehole survey with X and Y component data.')
            return

        if self.pem_file.is_rotated():
            response = self.message.question(self, 'File already de-rotated',
                                             f"{pem_file.filepath.name} is already de-rotated. " +
                                             'Do you wish to de-rotate again?',
                                             self.message.Yes | self.message.No)
            if response == self.message.No:
                return

        if self.pem_file.has_loop_gps() and self.pem_file.has_geometry():
            self.pp_btn.setEnabled(True)
        else:
            self.pp_btn.setEnabled(False)

        self.setWindowTitle(f"XY De-rotation - {pem_file.filepath.name}")
        self.show()
        self.rotate()

    def plot_pem(self, pem_file):
        """
        Plot the PEM file in a LIN plot style, with both components in separate plots
        :param pem_file: PEMFile object
        """

        def clear_plots():
            for ax in self.axes:
                ax.clear()
            self.rot_ax.clear()
            # self.pp_ax.clear()

        def plot_lin(component):

            def plot_lines(df, ax, channel):
                """
                Plot the lines on the pyqtgraph ax for a given channel
                :param df: DataFrame of filtered data
                :param ax: pyqtgraph PlotItem
                :param channel: int, channel to plot
                """
                ax.plot(x=df['Station'], y=df[channel], pen=pg.mkPen('k', width=1.25))

            def calc_channel_bounds():
                """
                Create tuples of start and end channels to be plotted per axes
                :return: list of tuples, first item of tuple is the axes, second is the start and end channel for that axes
                """
                channel_bounds = [None] * 4
                num_channels_per_plot = int((processed_pem.number_of_channels - 1) // 4)
                remainder_channels = int((processed_pem.number_of_channels - 1) % 4)

                for k in range(0, len(channel_bounds)):
                    channel_bounds[k] = (k * num_channels_per_plot + 1, num_channels_per_plot * (k + 1))

                for i in range(0, remainder_channels):
                    channel_bounds[i] = (channel_bounds[i][0], (channel_bounds[i][1] + 1))
                    for k in range(i + 1, len(channel_bounds)):
                        channel_bounds[k] = (channel_bounds[k][0] + 1, channel_bounds[k][1] + 1)

                channel_bounds.insert(0, (0, 0))
                return channel_bounds

            filt = profile_data['Component'] == component.upper()
            channel_bounds = calc_channel_bounds()
            for i, bounds in enumerate(channel_bounds):
                # Select the correct axes based on the component
                if component == 'X':
                    ax = self.x_view_axes[i]
                else:
                    ax = self.y_view_axes[i]

                # Set the Y-axis labels
                if i == 0:
                    ax.setLabel('left', f"PP channel", units=processed_pem.units)
                else:
                    ax.setLabel('left', f"Channel {bounds[0]} to {bounds[1]}", units=processed_pem.units)

                # Plot the data
                for ch in range(bounds[0], bounds[1] + 1):
                    data = profile_data[filt].loc[:, ['Station', ch]]
                    plot_lines(data, ax, ch)

        def plot_rotation():
            """
            Plot the rotation angle of the tool (if selected) and the PP rotation angles for comparison.
            """
            method = self.get_method()

            if method is not None:
                ax = self.rot_ax
                x_filt = raw_pem.data['Component'] == 'X'
                stations = raw_pem.data[x_filt].Station.astype(int)

                if self.pp_btn.isEnabled():
                    x_pp_angle_cleaned = raw_pem.data[x_filt].RAD_tool.map(lambda x: x.pp_rotation_angle_cleaned)
                    x_pp_angle_raw = raw_pem.data[x_filt].RAD_tool.map(lambda x: x.pp_rotation_angle_raw)

                    # Create and plot the scatter plot items
                    cpp_item = pg.ScatterPlotItem()
                    cpp_item.setData(x_pp_angle_cleaned, stations,
                                     pen='m',
                                     brush=None,
                                     symbol='o',
                                     size=18)
                    rpp_item = pg.ScatterPlotItem()
                    rpp_item.setData(x_pp_angle_raw, stations,
                                     pen='b',
                                     brush=None,
                                     symbol='t',
                                     size=18)

                    # Add the scatter plot items to the scatter plot
                    ax.addItem(cpp_item)
                    ax.addItem(rpp_item)
                    # Add the items to the legend
                    self.rot_ax_legend.addItem(cpp_item, 'Cleaned PP')
                    self.rot_ax_legend.addItem(rpp_item, 'Raw PP')

                x_angle_used = raw_pem.data[x_filt].RAD_tool.map(lambda x: x.angle_used)

                if method != 'pp':
                    tool_item = pg.ScatterPlotItem()
                    tool_item.setData(x_angle_used, stations,
                                      pen='k',
                                      brush=None,
                                      symbol='s',
                                      size=18)
                    ax.addItem(tool_item)
                    self.rot_ax_legend.addItem(tool_item, 'Tool')

        def plot_pp_values():
            """
            Plot the theoretical PP values with the measured (raw) and cleaned PP
            """
            ax = self.pp_ax
            # Used for PP values and rotation angle plots, not lin plots
            x_filt = raw_pem.data['Component'] == 'X'
            stations = raw_pem.data[x_filt].Station.astype(int)

            ppxy_theory = raw_pem.data[x_filt].RAD_tool.map(lambda x: x.ppxy_theory)
            ppxy_cleaned = raw_pem.data[x_filt].RAD_tool.map(lambda x: x.ppxy_cleaned)
            ppxy_raw = raw_pem.data[x_filt].RAD_tool.map(lambda x: x.ppxy_raw)

            theory_item = pg.ScatterPlotItem()
            theory_item.setData(ppxy_theory, stations,
                                pen='k',
                                brush=None,
                                symbol='o',
                                size=14)
            cleaned_item = pg.ScatterPlotItem()
            cleaned_item.setData(ppxy_cleaned, stations,
                                 pen='m',
                                 brush=None,
                                 symbol='s',
                                 size=14)
            raw_item = pg.ScatterPlotItem()
            raw_item.setData(ppxy_raw, stations,
                             pen='b',
                             brush=None,
                             symbol='t',
                             size=14)

            ax.addItem(theory_item)
            ax.addItem(cleaned_item)
            ax.addItem(raw_item)

            self.pp_ax_legend.addItem(theory_item, 'Theory')
            self.pp_ax_legend.addItem(cleaned_item, 'Cleaned PP')
            self.pp_ax_legend.addItem(raw_item, 'Raw PP')
            self.pp_plotted = True

        if not pem_file:
            return

        raw_pem = copy.deepcopy(pem_file)  # Needed otherwise the returned PEMFile will be averaged and split
        processed_pem = copy.deepcopy(pem_file)

        # Split the data if it isn't already split
        if not processed_pem.is_split():
            processed_pem = processed_pem.split()

        # Average the data if it isn't averaged
        if not processed_pem.is_averaged():
            processed_pem = processed_pem.average()

        clear_plots()

        # Get the profile data
        profile_data = processed_pem.get_profile_data()
        if profile_data.empty:
            return

        t = time.time()
        plot_lin('X')
        plot_lin('Y')
        plot_rotation()
        if self.pp_plotted is False and self.pp_btn.isEnabled():
            plot_pp_values()
        print(f"Time to make plots: {time.time() - t}")

    def rotate(self):
        """
        Rotate and plot the data, always using the original PEMFile
        """

        def fill_table(stations):
            self.list.clear()
            for s in stations.itertuples():
                result = f"{s.Station} {s.Component} - reading # {s.Reading_number} (index {s.Reading_index})"
                self.list.addItem(result)

        method = self.get_method()
        ineligible_stations = None
        soa = self.soa_sbox.value()
        # Create a copy of the pem_file so it is never changed
        pem_file = copy.deepcopy(self.pem_file)

        if method is not None:
            self.rotated_file, ineligible_stations = pem_file.rotate(method=method, soa=soa)
        else:
            self.rotated_file = pem_file

        # Fill the table with the ineligible stations
        if ineligible_stations is not None and not ineligible_stations.empty:
            fill_table(ineligible_stations)
            self.bad_stations_label.show()
            self.list.show()

        else:
            self.bad_stations_label.hide()
            self.list.hide()

        self.plot_pem(self.rotated_file)

    def get_method(self):
        if self.acc_btn.isChecked():
            method = 'acc'
            self.rotation_note = '<GEN> XY data de-rotated using accelerometer'
        elif self.mag_btn.isChecked():
            method = 'mag'
            self.rotation_note = '<GEN> XY data de-rotated using magnetometer'
        elif self.pp_btn.isChecked():
            method = 'pp'
            self.rotation_note = '<GEN> XY data de-rotated using cleaned PP.'
        else:
            method = None
            self.rotation_note = None
        return method


# # Works with Maptlotlib
# class Derotator(QMainWindow, Ui_Derotator):
#
#     def __init__(self, parent=None):
#         super().__init__()
#         self.setupUi(self)
#         self.parent = parent
#         self.pem_file = None
#
#         self.setWindowTitle('XY De-rotation')
#         self.setWindowIcon(QtGui.QIcon(os.path.join(icons_path, 'derotate.png')))
#
#         self.message = QMessageBox()
#
#         self.lin_fig, (ax1, ax2, ax3, ax4, ax5) = plt.subplots(5, 1, num=1, sharex=True, clear=True)
#         ax6 = ax5.twiny()
#         ax6.get_shared_x_axes().join(ax5, ax6)
#
#         self.log_fig, ax = plt.subplots(1, 1, num=2, clear=True)
#
#         self.lin_canvas = FigureCanvas(self.lin_fig)
#         self.log_canvas = FigureCanvas(self.log_fig)
#         self.lin_canvas.setMinimumSize(816, 1056)
#         self.log_canvas.setMinimumSize(816, 1056)
#
#         self.lin_scroll_area.setWidget(self.lin_canvas)
#         self.log_scroll_area.setWidget(self.log_canvas)
#
#         self.button_box.accepted.connect(self.rotate)
#         self.button_box.rejected.connect(self.close)
#
#         self.acc_btn.clicked.connect(self.rotate)
#         self.mag_btn.clicked.connect(self.rotate)
#         self.pp_btn.clicked.connect(self.rotate)
#         self.soa_sbox.editingFinished.connect(self.rotate)
#
#         self.bad_stations_label.hide()
#         self.bad_stations_list.hide()
#
#         # int_validator = QtGui.QIntValidator()
#         # self.soa_edit.setValidator(int_validator)
#
#     def open(self, pem_file):
#         while isinstance(pem_file, list):
#             pem_file = pem_file[0]
#
#         if all([pem_file.is_borehole(), 'X' in pem_file.get_components(), 'Y' in pem_file.get_components()]):
#             self.pem_file = pem_file
#         else:
#             self.message.information(self, 'Ineligible File',
#                                      'File must be a borehole survey with X and Y component data.')
#             return
#
#         if self.pem_file.is_rotated():
#             response = self.message.question(self, 'File already de-rotated',
#                                              f"{pem_file.filepath.name} is already de-rotated. " +
#                                              'Do you wish to de-rotate again?',
#                                              self.message.Yes | self.message.No)
#             if response == self.message.No:
#                 return
#
#         self.setWindowTitle(f"XY De-rotation - {pem_file.filepath.name}")
#         self.plot_pem(self.pem_file)
#         self.show()
#
#     def plot_pem(self, pem_file):
#
#         def configure_lin_fig():
#             """
#             Add the subplots for a lin plot
#             """
#             t = time.time()
#             self.portrait_fig, (ax1, ax2, ax3, ax4, ax5) = plt.subplots(5, 1, num=1, sharex=True, clear=True)
#             ax6 = ax5.twiny()
#             ax6.get_shared_x_axes().join(ax5, ax6)
#             print(f"Time to configure lin plot: {time.time() - t}")
#
#         def configure_log_fig():
#             """
#             Configure the log plot axes
#             """
#             t = time.time()
#             self.portrait_fig, ax = plt.subplots(1, 1, num=2, clear=True)
#             ax2 = ax.twiny()
#             ax2.get_shared_x_axes().join(ax, ax2)
#             plt.yscale('symlog', linthreshy=10, linscaley=1. / math.log(10), subsy=list(np.arange(2, 10, 1)))
#             print(f"Time to configure log plot: {time.time() - t}")
#
#         t = time.time()
#         self.lin_fig.clear()
#         self.log_fig.clear()
#         configure_lin_fig()
#         configure_log_fig()
#
#         # LIN plot
#         lin_plotter = LINPlotter(pem_file, self.lin_fig)
#         self.lin_fig = lin_plotter.plot('X')
#         self.lin_canvas.draw()
#
#         # LOG plot
#         log_plotter = LOGPlotter(pem_file, self.log_fig)
#         self.log_fig = log_plotter.plot('X')
#         self.log_canvas.draw()
#         print(f"Time to make plots: {time.time() - t}")
#
#     def rotate(self):
#         if self.acc_btn.isChecked():
#             method = 'acc'
#         elif self.mag_btn.isChecked():
#             method = 'mag'
#         else:
#             method = 'pp'
#
#         soa = self.soa_sbox.value()
#
#         # Create a copy of the pem_file so it is never changed
#         pem_file = copy.deepcopy(self.pem_file)
#         rotated_file = pem_file.rotate(method=method, soa=soa)
#         self.plot_pem(rotated_file)


def main():
    from src.pem.pem_getter import PEMGetter
    app = QApplication(sys.argv)
    mw = Derotator()

    pg = PEMGetter()
    pem_files = pg.get_pems(client='PEM Rotation', file='131-20-32xy.PEM')
    mw.open(pem_files)

    app.exec_()


if __name__ == '__main__':
    main()