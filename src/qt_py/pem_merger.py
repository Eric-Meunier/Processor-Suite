import copy
import os
import re
import sys
import time
import keyboard

import numpy as np
import pandas as pd
import pyqtgraph as pg
import pylineclip as lc
from scipy import spatial
from PyQt5 import uic, QtCore, QtGui
from PyQt5.QtWidgets import (QApplication, QMainWindow, QInputDialog, QLineEdit, QLabel, QMessageBox, QFileDialog,
                             QPushButton, QTableWidget, QTableWidgetItem, QWidget, QHBoxLayout, QAbstractItemView)
from pyqtgraph.Point import Point

from src.pem.pem_file import StationConverter, PEMParser

if getattr(sys, 'frozen', False):
    application_path = sys._MEIPASS
    mergerCreatorFile = 'qt_ui\\pem_merger.ui'
    icons_path = 'icons'
else:
    application_path = os.path.dirname(os.path.abspath(__file__))
    mergerCreatorFile = os.path.join(os.path.dirname(application_path), 'qt_ui\\pem_merger.ui')
    icons_path = os.path.join(os.path.dirname(application_path), "qt_ui\\icons")

# Load Qt ui file into a class
Ui_PlotMergerWindow, QtBaseClass = uic.loadUiType(mergerCreatorFile)

pg.setConfigOptions(antialias=True)
pg.setConfigOption('background', 'w')
pg.setConfigOption('foreground', 'k')
pg.setConfigOption('crashWarning', True)
pd.options.mode.chained_assignment = None  # default='warn'


class PEMMerger(QMainWindow, Ui_PlotMergerWindow):

    def __init__(self, parent=None):
        super().__init__()
        self.parent = parent
        self.setupUi(self)
        self.message = QMessageBox()

        # Format window
        self.setWindowTitle('PEM Plot Editor')
        self.setWindowIcon(QtGui.QIcon(os.path.join(icons_path, 'plot_editor.png')))

        self.converter = StationConverter()
        self.pf_1 = None
        self.pf_2 = None
        self.units = None
        self.stations = np.array([])
        self.components = []
        self.channel_bounds = None

        # Configure the plots
        # X axis lin plots
        self.x_profile_layout.ci.layout.setSpacing(5)  # Spacing between plots
        self.x_ax0 = self.x_profile_layout.addPlot(0, 0)
        self.x_ax1 = self.x_profile_layout.addPlot(1, 0)
        self.x_ax2 = self.x_profile_layout.addPlot(2, 0)
        self.x_ax3 = self.x_profile_layout.addPlot(3, 0)
        self.x_ax4 = self.x_profile_layout.addPlot(4, 0)
        self.pf1_x_curves = []
        self.pf2_x_curves = []

        # Y axis lin plots
        self.y_profile_layout.ci.layout.setSpacing(5)  # Spacing between plots
        self.y_ax0 = self.y_profile_layout.addPlot(0, 0)
        self.y_ax1 = self.y_profile_layout.addPlot(1, 0)
        self.y_ax2 = self.y_profile_layout.addPlot(2, 0)
        self.y_ax3 = self.y_profile_layout.addPlot(3, 0)
        self.y_ax4 = self.y_profile_layout.addPlot(4, 0)
        self.pf1_y_curves = []
        self.pf2_y_curves = []

        # Z axis lin plots
        self.z_profile_layout.ci.layout.setSpacing(5)  # Spacing between plots
        self.z_ax0 = self.z_profile_layout.addPlot(0, 0)
        self.z_ax1 = self.z_profile_layout.addPlot(1, 0)
        self.z_ax2 = self.z_profile_layout.addPlot(2, 0)
        self.z_ax3 = self.z_profile_layout.addPlot(3, 0)
        self.z_ax4 = self.z_profile_layout.addPlot(4, 0)
        self.pf1_z_curves = []
        self.pf2_z_curves = []

        self.x_layout_axes = [self.x_ax0, self.x_ax1, self.x_ax2, self.x_ax3, self.x_ax4]
        self.y_layout_axes = [self.y_ax0, self.y_ax1, self.y_ax2, self.y_ax3, self.y_ax4]
        self.z_layout_axes = [self.z_ax0, self.z_ax1, self.z_ax2, self.z_ax3, self.z_ax4]

        self.profile_axes = np.concatenate([self.x_layout_axes, self.y_layout_axes, self.z_layout_axes])

        # Configure each axes
        for ax in self.profile_axes:
            ax.hideButtons()
            ax.setMenuEnabled(False)
            ax.getAxis('left').enableAutoSIPrefix(enable=False)

        # Signals

    def open(self, pem_files):
        """
        Open a PEMFile object and plot the data.
        :param pem_files: list, 2 PEMFile objects.
        """

        def format_plots():

            def set_plot_labels(ax):

                # Set the plot labels
                for i, bounds in enumerate(self.channel_bounds):
                    # Set the Y-axis labels
                    if i == 0:
                        ax.setLabel('left', f"PP channel", units=self.units)
                    else:
                        ax.setLabel('left', f"Channel {bounds[0]} to {bounds[1]}", units=self.units)

            if 'X' in self.components:
                # Add the line name and loop name as the title for the profile plots
                self.x_ax0.setTitle(f"X Component")

                for ax in self.x_layout_axes:
                    set_plot_labels(ax)

            if 'Y' in self.components:
                # Add the line name and loop name as the title for the profile plots
                self.y_ax0.setTitle(f"Y Component")

                for ax in self.y_layout_axes:
                    set_plot_labels(ax)

            if 'Z' in self.components:
                # Add the line name and loop name as the title for the profile plots
                self.z_ax0.setTitle(f"Z Component")

                for ax in self.z_layout_axes:
                    set_plot_labels(ax)

        if len(pem_files) != 2:
            raise Exception(f"PEMMerger exclusively accepts two PEM files")

        f1, f2 = pem_files[0], pem_files[1]

        assert f1.is_borehole() == f2.is_borehole(), f"Cannot merge a borehole survey with a surface survey."
        assert f1.is_fluxgate() == f2.is_fluxgate(), f"Cannot merge a fluxgate survey with an induction survey."
        assert f1.timebase == f2.timebase, f"Both files must have the same timebase."
        assert f1.number_of_channels == f2.number_of_channels, f"Both files must have the same number of channels."

        if f1.ramp != f2.ramp:
            response = self.message.question(self, 'Warning', 'The two files have different ramps. Continue with'
                                                              'merging?', self.message.Yes, self.message.No)

            if response == self.message.No:
                return

        self.pf_1 = f1
        self.pf_2 = f2

        if self.pf_1.is_split():
            self.actionOn_time.blockSignals(True)
            self.actionOn_time.setChecked(False)
            self.actionOn_time.blockSignals(False)

            self.actionOn_time.setEnabled(False)
        else:
            self.actionOn_time.setEnabled(True)

        self.components = set(np.array([self.pf_1.get_components(), self.pf_2.get_components()]).flatten())
        self.channel_bounds = self.pf_1.get_channel_bounds()

        format_plots()

        # Plot the LIN profiles
        self.plot_profiles(self.pf_1, components='all')

        self.show()

    def plot_profiles(self, pem_file, components=None):
        """
        Plot the PEM file in a LIN plot style, with both components in separate plots
        :param pem_file: PEMFile object to plot.
        :param color: Union, line color to use for the plots.
        :param components: list of str, components to plot. If None it will plot every component in the file.
        """

        def clear_plots(components):
            """
            Clear the plots of the given components
            :param components: list of str
            """
            axes = []

            if 'X' in components:
                axes.extend(self.x_layout_axes)
            if 'Y' in components:
                axes.extend(self.y_layout_axes)
            if 'Z' in components:
                axes.extend(self.z_layout_axes)

            for ax in axes:
                ax.clearPlots()

        def plot_lin(profile_data, axes):

            # def plot_lines(df, ax):
            #     """
            #     Plot the lines on the pyqtgraph ax
            #     :param df: DataFrame of filtered data
            #     :param ax: pyqtgraph PlotItem
            #     """
            #     df_avg = df.groupby('Station').mean()
            #     x, y = df_avg.index, df_avg
            #
            #     curve = pg.PlotCurveItem(
            #         x.to_numpy(), y.to_numpy(),
            #         pen=pg.mkPen(color, width=1.),
            #         symbol='o',
            #         symbolSize=2,
            #         symbolBrush='k',
            #         symbolPen='k',
            #     )
            #     ax.addItem(curve)

            def get_ax(channel):
                pass

            def plot_lines_2(channel):
                channel_number = channel.name
                df_avg = channel.groupby('Station').mean()
                x, y = df_avg.index, df_avg
                print(channel)


            # def plot_scatters(df, ax):
            #     """
            #     Plot the scatter plot markers
            #     :param df: DataFrame of filtered data
            #     :param ax: pyqtgraph PlotItem
            #     :return:
            #     """
            #     global scatter_plotting_time
            #     t = time.time()
            #     x, y = df.index, df
            #
            #     scatter = pg.ScatterPlotItem(x=x, y=y,
            #                                  pen=pg.mkPen('k', width=1.),
            #                                  symbol='o',
            #                                  size=2,
            #                                  brush='w',
            #                                  )
            #
            #     ax.addItem(scatter)
            #     scatter_plotting_time += time.time() - t

            # Plotting

            profile_data.apply(plot_lines_2)

            # for i, bounds in enumerate(self.channel_bounds):
            #     ax = axes[i]
            #
            #     # Plot the data
            #     for channel in range(bounds[0], bounds[1] + 1):
            #         data = profile_data.iloc[:, channel]
            #
            #         plot_lines(data, ax)
            #         # if self.show_scatter_cbox.isChecked():
            #         #     plot_scatters(data, ax)

        if not isinstance(components, np.ndarray):
            # Get the components
            if components is None or components == 'all':
                components = self.components

        # clear_plots(components)

        if pem_file == self.pf_1:
            color = 'b'
            
        file = pem_file.copy()

        for component in components:
            profile_data = file.get_profile_data(component,
                                                 averaged=False,
                                                 converted=True,
                                                 ontime=self.actionOn_time.isChecked())

            if profile_data.empty:
                continue

            print(f"Plotting profile for {component} component")
            # Select the correct axes based on the component
            if component == 'X':
                axes = self.x_layout_axes
            elif component == 'Y':
                axes = self.y_layout_axes
            else:
                axes = self.z_layout_axes

            plot_lin(profile_data, axes)

    def cycle_profile_component(self):
        """
        Signal slot, cycle through the profile plots
        """

        def get_comp_indexes():
            """
            Return the index of the stacked widget of each component present in the PEM file
            :return: list of int
            """
            indexes = []
            if 'X' in self.components:
                indexes.append(0)
            if 'Y' in self.components:
                indexes.append(1)
            if 'Z' in self.components:
                indexes.append(2)
            return indexes

        comp_indexes = get_comp_indexes()
        current_ind = self.profile_tab_widget.currentIndex()
        if len(comp_indexes) > 1:
            if current_ind + 1 > max(comp_indexes):
                new_ind = min(comp_indexes)
            else:
                new_ind = comp_indexes[comp_indexes.index(current_ind) + 1]
        elif comp_indexes[0] != current_ind:
            new_ind = comp_indexes[0]
        else:
            return

        print(f"Cycling profile tab to {new_ind}")
        self.profile_tab_widget.setCurrentIndex(new_ind)


if __name__ == '__main__':
    from src.pem.pem_getter import PEMGetter
    app = QApplication(sys.argv)

    pem_getter = PEMGetter()
    pem_files = pem_getter.get_pems(client='Minera', number=2)

    w = PEMMerger()
    w.open(pem_files)

    w.show()

    app.exec_()