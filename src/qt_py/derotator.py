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

    def __init__(self, parent=None):
        super().__init__()
        self.setupUi(self)
        self.parent = parent
        self.pem_file = None

        self.setWindowTitle('XY De-rotation')
        self.setWindowIcon(QtGui.QIcon(os.path.join(icons_path, 'derotate.png')))

        self.message = QMessageBox()

        self.button_box.accepted.connect(self.rotate)
        self.button_box.rejected.connect(self.close)

        self.acc_btn.clicked.connect(self.rotate)
        self.mag_btn.clicked.connect(self.rotate)
        self.pp_btn.clicked.connect(self.rotate)
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
                                             f"{pem_file.filename} is already de-rotated. " +
                                             'Do you wish to de-rotate again?',
                                             self.message.Yes | self.message.No)
            if response == self.message.No:
                return

        self.setWindowTitle(f"XY De-rotation - {pem_file.filename}")
        self.rotate()
        self.show()

    def plot_pem(self, pem_file):
        """
        Plot the PEM file in a LIN plot style, with both components in separate plots
        :param pem_file: PEMFile object
        """

        def clear_plots():
            for ax in self.axes:
                ax.clear()

        def plot_lin(component):

            def plot_lines(df, ax, channel):
                """
                Plot the lines on the pyqtgraph ax for a given channel
                :param df: DataFrame of filtered data
                :param ax: pyqtgraph PlotItem
                :param channel: int, channel to plot
                """
                ax.plot(x=df['Station'], y=df[channel], pen='k')

            def calc_channel_bounds():
                """
                Create tuples of start and end channels to be plotted per axes
                :return: list of tuples, first item of tuple is the axes, second is the start and end channel for that axes
                """
                channel_bounds = [None] * 4
                num_channels_per_plot = int((pem_file.number_of_channels - 1) // 4)
                remainder_channels = int((pem_file.number_of_channels - 1) % 4)

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
                    ax.setLabel('left', f"PP channel", units=pem_file.units)
                else:
                    ax.setLabel('left', f"Channel {bounds[0]} to {bounds[1]}", units=pem_file.units)

                # Plot the data
                for ch in range(bounds[0], bounds[1] + 1):
                    data = profile_data[filt].loc[:, ['Station', ch]]
                    plot_lines(data, ax, ch)

        if not pem_file:
            return

        # Split the data if it isn't already split
        if not pem_file.is_split():
            pem_file = pem_file.split()

        # Average the data if it isn't averaged
        if not pem_file.is_averaged():
            pem_file = pem_file.average()

        clear_plots()

        # Get the profile data
        profile_data = pem_file.get_profile_data()
        if profile_data.empty:
            return

        t = time.time()
        plot_lin('X')
        plot_lin('Y')
        print(f"Time to make lin plots: {time.time() - t}")

    def rotate(self):
        """
        Rotate and plot the data, always using the original PEMFile
        """

        def fill_table(stations):
            self.list.clear()
            for s in stations.itertuples():
                result = f"{s.Station} {s.Component} - reading # {s.Reading_number} (index {s.Reading_index})"
                self.list.addItem(result)

        if self.acc_btn.isChecked():
            method = 'acc'
        elif self.mag_btn.isChecked():
            method = 'mag'
        else:
            method = 'pp'

        soa = self.soa_sbox.value()

        # Create a copy of the pem_file so it is never changed
        pem_file = copy.deepcopy(self.pem_file)
        rotated_file, ineligible_stations = pem_file.rotate(method=method, soa=soa)
        # Fill the table with the ineligible stations
        if not ineligible_stations.empty:
            fill_table(ineligible_stations)
            self.bad_stations_label.show()
            self.list.show()

        else:
            self.bad_stations_label.hide()
            self.list.hide()

        self.plot_pem(rotated_file)


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
#                                              f"{pem_file.filename} is already de-rotated. " +
#                                              'Do you wish to de-rotate again?',
#                                              self.message.Yes | self.message.No)
#             if response == self.message.No:
#                 return
#
#         self.setWindowTitle(f"XY De-rotation - {pem_file.filename}")
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
    pem_files = pg.get_pems(client='PEM Rotation', selection=3)
    mw.open(pem_files)

    app.exec_()


if __name__ == '__main__':
    main()