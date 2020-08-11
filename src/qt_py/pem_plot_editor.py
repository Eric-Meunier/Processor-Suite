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
from PyQt5 import uic, QtCore, QtGui
from PyQt5.QtWidgets import (QApplication, QMainWindow, QInputDialog, QLineEdit)
from pyqtgraph.Point import Point

# from matplotlib.figure import Figure
from src.pem.pem_file import StationConverter

if getattr(sys, 'frozen', False):
    application_path = sys._MEIPASS
    plotEditorCreatorFile = 'qt_ui\\pem_plot_editor.ui'
else:
    application_path = os.path.dirname(os.path.abspath(__file__))
    plotEditorCreatorFile = os.path.join(os.path.dirname(application_path), 'qt_ui\\pem_plot_editor.ui')

# Load Qt ui file into a class
Ui_PlotEditorWindow, QtBaseClass = uic.loadUiType(plotEditorCreatorFile)

pg.setConfigOptions(antialias=True)
pg.setConfigOption('background', 'w')
pg.setConfigOption('foreground', 'k')
pg.setConfigOption('crashWarning', True)
pd.options.mode.chained_assignment = None  # default='warn'


class PEMPlotEditor(QMainWindow, Ui_PlotEditorWindow):

    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.pem_file = None
        self.units = None
        self.stations = np.array([])

        self.line_selected = False
        self.selected_station = None
        self.selected_data = pd.DataFrame()
        self.selected_lines = []
        self.deleted_lines = []

        self.active_ax = None
        self.active_ax_ind = None
        self.last_active_ax = None  # last_active_ax is always a plotitem object, and never None after the init.
        self.last_active_ax_ind = None  # last_active_ax is always a plotitem object, and never None after the init.
        self.plotted_decay_lines = []
        self.plotted_decay_data = pd.DataFrame()

        self.x_decay_plot = self.decay_layout.addPlot(0, 0, title='X Component', viewBox=DecayViewBox())
        self.y_decay_plot = self.decay_layout.addPlot(1, 0, title='Y Component', viewBox=DecayViewBox())
        self.z_decay_plot = self.decay_layout.addPlot(2, 0, title='Z Component', viewBox=DecayViewBox())
        self.decay_layout.ci.layout.setSpacing(1)  # Spacing between plots
        self.decay_axes = np.array([self.x_decay_plot, self.y_decay_plot, self.z_decay_plot])
        self.active_decay_axes = []

        for ax in self.decay_axes:
            ax.vb.box_select_signal.connect(self.box_select_decay_lines)
            ax.hideButtons()
            ax.setMenuEnabled(False)
            ax.getAxis('left').enableAutoSIPrefix(enable=False)

            ax.scene().sigMouseMoved.connect(self.decay_mouse_moved)
            ax.scene().sigMouseClicked.connect(self.decay_plot_clicked)

        # Configure the plots
        # X axis lin plots
        self.x_profile_layout.ci.layout.setSpacing(5)  # Spacing between plots
        self.x_ax0 = self.x_profile_layout.addPlot(0, 0)
        self.x_ax1 = self.x_profile_layout.addPlot(1, 0)
        self.x_ax2 = self.x_profile_layout.addPlot(2, 0)
        self.x_ax3 = self.x_profile_layout.addPlot(3, 0)
        self.x_ax4 = self.x_profile_layout.addPlot(4, 0)

        # Y axis lin plots
        self.y_profile_layout.ci.layout.setSpacing(5)  # Spacing between plots
        self.y_ax0 = self.y_profile_layout.addPlot(0, 0)
        self.y_ax1 = self.y_profile_layout.addPlot(1, 0)
        self.y_ax2 = self.y_profile_layout.addPlot(2, 0)
        self.y_ax3 = self.y_profile_layout.addPlot(3, 0)
        self.y_ax4 = self.y_profile_layout.addPlot(4, 0)

        # Z axis lin plots
        self.z_profile_layout.ci.layout.setSpacing(5)  # Spacing between plots
        self.z_ax0 = self.z_profile_layout.addPlot(0, 0)
        self.z_ax1 = self.z_profile_layout.addPlot(1, 0)
        self.z_ax2 = self.z_profile_layout.addPlot(2, 0)
        self.z_ax3 = self.z_profile_layout.addPlot(3, 0)
        self.z_ax4 = self.z_profile_layout.addPlot(4, 0)

        self.x_layout_axes = [self.x_ax0, self.x_ax1, self.x_ax2, self.x_ax3, self.x_ax4]
        self.y_layout_axes = [self.y_ax0, self.y_ax1, self.y_ax2, self.y_ax3, self.y_ax4]
        self.z_layout_axes = [self.z_ax0, self.z_ax1, self.z_ax2, self.z_ax3, self.z_ax4]

        self.profile_axes = np.concatenate([self.x_layout_axes, self.y_layout_axes, self.z_layout_axes])
        self.active_profile_axes = []

        # Configure each axes
        for ax in self.profile_axes:
            ax.hideButtons()
            # ax.setMenuEnabled(False)
            ax.getAxis('left').enableAutoSIPrefix(enable=False)

            # Add the vertical selection line
            hover_v_line = pg.InfiniteLine(angle=90, movable=False)
            hover_v_line.setPen((102, 178, 255, 100), width=2.)
            selected_v_line = pg.InfiniteLine(angle=90, movable=False)
            selected_v_line.setPen((51, 51, 255, 100), width=2.)

            # Add the text annotations for the vertical lines
            hover_v_line_text = pg.TextItem("", anchor=(0, 0))
            hover_v_line_text.setParentItem(ax.vb)
            hover_v_line_text.setPos(0, 0)
            hover_v_line_text.setColor((102, 178, 255, 100))
            selected_v_line_text = pg.TextItem("", anchor=(0, 0))
            selected_v_line_text.setParentItem(ax.vb)
            selected_v_line_text.setPos(0, 0)
            selected_v_line_text.setColor((51, 51, 255, 100))

            ax.addItem(hover_v_line, ignoreBounds=True)
            ax.addItem(selected_v_line, ignoreBounds=True)
            ax.addItem(hover_v_line_text, ignoreBounds=True)
            ax.addItem(selected_v_line_text, ignoreBounds=True)

            # Connect the mouse moved signal
            ax.scene().sigMouseMoved.connect(self.profile_mouse_moved)
            ax.scene().sigMouseClicked.connect(self.profile_plot_clicked)

        # Signals
        self.link_y_cbox.toggled.connect(self.link_decay_y)
        self.link_x_cbox.toggled.connect(self.link_decay_x)

        self.change_station_btn.clicked.connect(self.change_station)

    def keyPressEvent(self, event):
        # Delete a decay when the delete key is pressed
        if event.key() == QtCore.Qt.Key_Delete or event.key() == QtCore.Qt.Key_C:
            t = time.time()
            self.delete_lines()
            # self.plot_profiles()
            print(f"Time to delete and replot: {time.time() - t}")

        # Cycle through highlighted decays backwards
        elif event.key() == QtCore.Qt.Key_A or event.key() == QtCore.Qt.LeftArrow:
            if self.selected_lines:
                new_selection = []
                # For each decay axes, find any selected lines and cycle to the next line in that axes
                for ax in self.active_decay_axes:
                    num_plotted = len(ax.curves)
                    # Find the index of any lines in the current ax that is selected
                    index_of_selected = [ax.curves.index(line) for line in self.selected_lines if line in ax.curves]
                    if index_of_selected:
                        old_index = index_of_selected[0]  # Only take the first selected decay
                        if old_index == 0:
                            new_index = num_plotted - 1
                        else:
                            new_index = old_index - 1
                        new_selection.append(ax.curves[new_index])
                self.selected_lines = new_selection
                self.highlight_lines()

        # Cycle through highlighted decays forwards
        elif event.key() == QtCore.Qt.Key_D or event.key() == QtCore.Qt.RightArrow:
            if self.selected_lines:
                new_selection = []
                # For each decay axes, find any selected lines and cycle to the next line in that axes
                for ax in self.active_decay_axes:
                    num_plotted = len(ax.curves)
                    # Find the index of any lines in the current ax that is selected
                    index_of_selected = [ax.curves.index(line) for line in self.selected_lines if line in ax.curves]
                    if index_of_selected:
                        old_index = index_of_selected[0]  # Only take the first selected decay
                        if old_index < num_plotted - 1:
                            new_index = old_index + 1
                        else:
                            new_index = 0
                        new_selection.append(ax.curves[new_index])
                self.selected_lines = new_selection
                self.highlight_lines()

        # Flip the decay when the F key is pressed
        elif event.key() == QtCore.Qt.Key_F:
            if self.selected_lines:
                self.flip_decays()

        # Change the component of the readings to X
        elif event.key() == QtCore.Qt.Key_X:
            if self.selected_lines:
                self.change_component('X')

        # Change the component of the readings to Y
        elif event.key() == QtCore.Qt.Key_Y:
            if self.selected_lines:
                self.change_component('Y')

        # Change the component of the readings to Z
        elif event.key() == QtCore.Qt.Key_Z:
            if self.selected_lines:
                self.change_component('Z')

        # Reset the ranges of the plots when the space bar is pressed
        elif event.key() == QtCore.Qt.Key_Space:
            # Only need to auto range the first axes, since they are all linked.
            if self.active_profile_axes:
                self.active_profile_axes[0].autoRange()

            if self.active_decay_axes:
                for ax in self.active_decay_axes:
                    ax.autoRange()

        # Clear the selected decays when the Escape key is pressed
        elif event.key() == QtCore.Qt.Key_Escape:
            self.clear_selection()

    def wheelEvent(self, evt):
        if not keyboard.is_pressed('shift'):
            y = evt.angleDelta().y()
            if y < 0:
                self.cycle_station('down')
            else:
                self.cycle_station('up')

    def cycle_station(self, direction):
        """
        Change the selected station
        :param direction: str, direction to cycle stations. either 'up' or 'down'.
        """
        station_index = list(self.stations).index(self.selected_station)
        if direction == 'down':
            if station_index == len(self.stations) - 1:
                return
            else:
                self.plot_station(self.stations[station_index + 1])
        elif direction == 'up':
            if station_index == 0:
                return
            else:
                self.plot_station(self.stations[station_index - 1])

    def open(self, pem_file):
        """
        Open a PEMFile object and plot the data.
        :param pem_file: PEMFile object.
        """
        self.pem_file = copy.deepcopy(pem_file)
        # Add the deletion flag column
        self.pem_file.data.insert(13, 'del_flag', False)

        # Set the units of the decay plots
        self.units = self.pem_file.units

        for ax in self.decay_axes:
            ax.setLabel('left', f"Response", units=self.units)
            ax.setLimits(minXRange=0, maxXRange=self.pem_file.number_of_channels,
                         xMin=0, xMax=self.pem_file.number_of_channels)

        # Plot the LIN profiles
        self.plot_profiles()
        # Plot the first station. This also helps with the linking of the X and Y axes for the decay plots.
        self.plot_station(self.stations.min())

        # Link the X and Y axis of each axes
        self.link_decay_x()
        self.link_decay_y()

        self.show()

    def update_file(self):

        def toggle_decay_plots():
            """
            Show/hide decay plots and profile plot tabs based on the components in the pem file
            """

            components = self.pem_file.get_components()

            x_ax = self.x_decay_plot
            y_ax = self.y_decay_plot
            z_ax = self.z_decay_plot

            if 'X' in components:
                x_ax.show()
                self.profile_tab_widget.setTabEnabled(0, True)
            else:
                x_ax.hide()
                self.profile_tab_widget.setTabEnabled(0, False)

            if 'Y' in components:
                y_ax.show()
                self.profile_tab_widget.setTabEnabled(1, True)
            else:
                y_ax.hide()
                self.profile_tab_widget.setTabEnabled(1, False)

            if 'Z' in components:
                z_ax.show()
                self.profile_tab_widget.setTabEnabled(2, True)
            else:
                z_ax.hide()
                self.profile_tab_widget.setTabEnabled(2, False)

        def toggle_profile_plots():
            """
            Update which profile axes are active based on what components are present and update the axis links.
            """

            def link_profile_axes():
                if len(self.active_profile_axes) > 1:
                    for ax in self.active_profile_axes[1:]:
                        ax.setXLink(self.active_profile_axes[0])

            # Update the profile axes
            tt = time.time()
            self.active_profile_axes = []
            for component in self.pem_file.get_components():
                # Add the profile axes to the list of active profile axes
                if component == 'X':
                    if self.x_layout_axes not in self.active_profile_axes:
                        self.active_profile_axes.extend(self.x_layout_axes)
                elif component == 'Y':
                    if self.y_layout_axes not in self.active_profile_axes:
                        self.active_profile_axes.extend(self.y_layout_axes)
                elif component == 'Z':
                    if self.z_layout_axes not in self.active_profile_axes:
                        self.active_profile_axes.extend(self.z_layout_axes)

                link_profile_axes()
            print(f"Time linking profile axes: {time.time() - tt}")

        self.stations = np.sort(self.pem_file.get_stations(converted=True))

        # Convert the stations in the data
        converter = StationConverter()
        self.pem_file.data['cStation'] = self.pem_file.data.Station.map(converter.convert_station)

        toggle_profile_plots()
        toggle_decay_plots()

    def link_decay_x(self):
        """
        Link or unlink the X axis of all decay plots
        """
        if len(self.active_decay_axes) > 1:
            for ax in self.active_decay_axes[1:]:
                if self.link_x_cbox.isChecked():
                    ax.setXLink(self.active_decay_axes[0])
                else:
                    ax.setXLink(None)

    def link_decay_y(self):
        """
        Link or unlink the Y axis of all decay plots
        """
        if len(self.active_decay_axes) > 1:
            for ax in self.active_decay_axes[1:]:
                if self.link_y_cbox.isChecked():
                    ax.setYLink(self.active_decay_axes[0])
                else:
                    ax.setYLink(None)

    def plot_profiles(self, components=None):
        """
        Plot the PEM file in a LIN plot style, with both components in separate plots
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

        def calc_channel_bounds():
            """
            Create tuples of start and end channels to be plotted per axes
            :return: list of tuples, first item of tuple is the axes, second is the start and end channel for that axes
            """
            channel_bounds = [None] * 4
            num_channels_per_plot = int((file.number_of_channels - 1) // 4)
            remainder_channels = int((file.number_of_channels - 1) % 4)

            for k in range(0, len(channel_bounds)):
                channel_bounds[k] = (k * num_channels_per_plot + 1, num_channels_per_plot * (k + 1))

            for i in range(0, remainder_channels):
                channel_bounds[i] = (channel_bounds[i][0], (channel_bounds[i][1] + 1))
                for k in range(i + 1, len(channel_bounds)):
                    channel_bounds[k] = (channel_bounds[k][0] + 1, channel_bounds[k][1] + 1)

            channel_bounds.insert(0, (0, 0))
            return channel_bounds

        def plot_lin(profile_data, axes):

            def plot_lines(df, ax):
                """
                Plot the lines on the pyqtgraph ax for a given channel
                :param df: DataFrame of filtered data
                :param ax: pyqtgraph PlotItem
                :param channel: int, channel to plot
                """
                global lin_plotting_time, averaging_time

                t = time.time()
                df_avg = df.groupby('Station').apply(lambda x: np.average(x, axis=0))
                averaging_time += time.time() - t

                x, y = df_avg.index, df_avg

                t2 = time.time()
                ax.plot(x=x, y=y,
                        pen=pg.mkPen('k', width=1.),
                        symbol='o',
                        symbolSize=2,
                        symbolBrush='k',
                        symbolPen='k',
                        )
                lin_plotting_time += time.time() - t2

            def plot_scatters(df, ax):
                global scatter_plotting_time
                t = time.time()
                x, y = df.index, df

                scatter = pg.ScatterPlotItem(x=x, y=y,
                                             # pen=pg.mkPen('k', width=1.),
                                             symbol='o',
                                             size=2,
                                             brush='k',
                                             pen='k',
                                             )
                ax.addItem(scatter)
                scatter_plotting_time += time.time() - t

            for i, bounds in enumerate(channel_bounds):
                ax = axes[i]

                # Set the Y-axis labels
                if i == 0:
                    ax.setLabel('left', f"PP channel", units=self.units)
                else:
                    ax.setLabel('left', f"Channel {bounds[0]} to {bounds[1]}", units=self.units)

                # Plot the data
                for ch in range(bounds[0], bounds[1] + 1):
                    data = profile_data.iloc[:, ch]

                    plot_lines(data, ax)
                    plot_scatters(data, ax)

        self.update_file()

        file = copy.deepcopy(self.pem_file)
        file.data = file.data.loc[file.data.del_flag == False]

        if components is None:
            components = file.get_components()

        clear_plots(components)

        t = time.time()
        global averaging_time, lin_plotting_time, scatter_plotting_time
        averaging_time = 0
        lin_plotting_time = 0
        scatter_plotting_time = 0

        ts = time.time()
        if not file.is_split():
            file = file.split()
        print(f"Time to deal with splitting: {time.time() - ts}")

        # Calculate the lin plot axes channel bounds
        channel_bounds = calc_channel_bounds()

        for component in components:
            print(f"Plotting profile for {component} component")
            # Select the correct axes based on the component
            if component == 'X':
                axes = self.x_layout_axes
            elif component == 'Y':
                axes = self.y_layout_axes
            else:
                axes = self.z_layout_axes

            tp = time.time()
            profile_data = file.get_profile_data2(component, averaged=False, converted=True)
            if profile_data.empty:
                return
            print(f"Time getting profile data: {time.time() - tp}")

            plot_lin(profile_data, axes)

        print(f"Time to make lin plots: {lin_plotting_time}")
        print(f"Time to make scatter plots: {scatter_plotting_time}")
        print(f"Averaging time: {averaging_time}")
        print(f"Time to make profile plots: {time.time() - t}")

    def plot_station(self, station, preserve_selection=False):
        """
        Plot the decay lines for each component of the given station
        :param station: int, station number
        :param preserve_selection: bool, re-select the selected lines after plotting
        """

        def plot_decay(row):
            """
            Plot the decay line (Reading) of the row
            :param row: pandas Series
            """
            # Select which axes to plot on
            if row.Component == 'X':
                ax = self.x_decay_plot
            elif row.Component == 'Y':
                ax = self.y_decay_plot
            else:
                ax = self.z_decay_plot

            # Add the ax to the list of active decay axes
            if ax not in self.active_decay_axes:
                self.active_decay_axes.append(ax)

            # Change the pen if the data is flagged for deletion
            if row.del_flag is False:
                pen = pg.mkPen((96, 96, 96), width=1.)
            else:
                pen = pg.mkPen('r', width=1.)

            # Create and configure the line item
            decay_line = pg.PlotCurveItem(y=row.Reading,
                                          pen=pen,
                                          )
            decay_line.setClickable(True, width=6)
            decay_line.sigClicked.connect(self.decay_line_clicked)

            # Add the line at y=0
            ax.addLine(y=0, pen=pg.mkPen('k', width=0.15))
            # Plot the decay
            ax.addItem(decay_line)
            # Add the plot item to the list of plotted items
            self.plotted_decay_lines.append(decay_line)

        self.selected_station = station

        # Move the selected vertical line
        for ax in self.profile_axes:
            selected_v_line = ax.items[1]
            selected_v_line.setPos(station)

        index_of_selected = []
        # Keep the same lines highlighted after data modification
        if preserve_selection is False:
            self.selected_lines = []
        else:
            index_of_selected = [self.plotted_decay_lines.index(line) for line in self.selected_lines]

        # Clear the plots
        for ax in self.decay_axes:
            ax.clear()
        self.plotted_decay_lines = []
        self.plotted_decay_data = None  # Not actually necessary

        # Filter the data
        filt = self.pem_file.data['cStation'] == station
        self.plotted_decay_data = self.pem_file.data[filt]

        # Plot the decays
        self.plotted_decay_data.apply(plot_decay, axis=1)

        # Re-select lines that were selected
        if preserve_selection is True:
            self.selected_lines = [self.plotted_decay_lines[i] for i in index_of_selected]
            self.highlight_lines()

        if self.auto_range_cbox.isChecked() and preserve_selection is False:
            for ax in self.active_decay_axes:
                ax.autoRange()

    def profile_mouse_moved(self, evt):
        """
        Signal slot, when the mouse is moved in one of the axes. Calculates and plots a light blue vertical line at the
        nearest station where the mouse is.
        :param evt: pyqtgraph MouseClickEvent
        """
        def find_nearest_station(x):
            """
            Calculate the nearest station from the position x
            :param x: int, mouse x location
            :return: int, station number
            """
            idx = (np.abs(self.stations - x)).argmin()
            return self.stations[idx]

        global nearest_station
        pos = evt
        try:
            mouse_point = self.active_profile_axes[0].vb.mapSceneToView(pos)
        except np.linalg.LinAlgError:
            self.profile_tab_widget.setCurrentIndex(0)
        else:
            nearest_station = find_nearest_station(int(mouse_point.x()))

            for ax in self.active_profile_axes:
                ax.items[0].setPos(nearest_station)
                ax.items[2].setPos(nearest_station, ax.viewRange()[1][1])
                ax.items[2].setText(str(nearest_station))

    def profile_plot_clicked(self, evt):
        """
        Signal slot, when the profile plot is clicked. Plots a darker blue vertical line at the nearest station where
        the click was made and plots that station's decays in the decay plot.
        Uses the nearest station calculated in self.profile_mouse_moved.
        :param evt: pyqtgraph MouseClickEvent (not used)
        """
        self.selected_station = nearest_station
        for ax in self.active_profile_axes:
            ax.items[3].setPos(nearest_station, ax.viewRange()[1][1])
            ax.items[3].setText(str(nearest_station))

        self.plot_station(nearest_station)

    def decay_line_clicked(self, line):
        """
        Signal slot, select the decay line that was clicked. If control is held, it extends the current selection.
        :param line: clicked PlotItem line
        """
        self.line_selected = True
        if keyboard.is_pressed('ctrl'):
            self.selected_lines.append(line)
            self.highlight_lines()
        else:
            self.selected_data = None
            self.selected_lines = [line]
            self.highlight_lines()

    def decay_plot_clicked(self, evt):
        """
        Signal slot, change the profile tab to the same component as the clicked decay plot
        :param evt: MouseClick event
        """
        self.profile_tab_widget.setCurrentIndex(self.active_ax_ind)

    def decay_mouse_moved(self, evt):
        """
        Signal slot, find the decay_axes plot under the mouse when the mouse is moved to determine which plot is active.
        :param evt: MouseMovement event
        """
        self.active_ax = None
        for ax in self.decay_axes:
            if ax.sceneBoundingRect().contains(evt):
                self.active_ax = ax
                self.last_active_ax = ax
                self.active_ax_ind = np.where(self.decay_axes == self.active_ax)[0][0]
                self.last_active_ax_ind = self.active_ax_ind
                break

    def highlight_lines(self):
        """
        Highlight the line selected and un-highlight any previously highlighted line.
        :param lines: list, PlotItem lines
        """
        if self.plotted_decay_lines:

            # Enable decay editing buttons
            if len(self.selected_lines) > 0:
                self.change_component_btn.setEnabled(True)
                self.change_station_btn.setEnabled(True)
                self.flip_decay_btn.setEnabled(True)
            else:
                self.change_component_btn.setEnabled(False)
                self.change_station_btn.setEnabled(False)
                self.flip_decay_btn.setEnabled(False)

            # Change the color and width of the plotted lines
            for line, del_flag in zip(self.plotted_decay_lines, self.plotted_decay_data.del_flag):
                # Make the line red if it is flagged for deletion
                if del_flag is True:
                    pen_color = 'r'
                else:
                    pen_color = (96, 96, 96)

                if line in self.selected_lines:
                    if del_flag is False:
                        # pen_color = (102, 102, 255)
                        pen_color = (80, 80, 255)
                        # pen_color = (127, 0, 255)

                    print(f"Line {self.plotted_decay_lines.index(line)} selected")
                    line.setPen(pen_color, width=2)
                    if len(self.selected_lines) == 1:
                        line.setShadowPen(pg.mkPen('w', width=2.5, cosmetic=True))
                else:
                    line.setPen(pen_color, width=1)
                    line.setShadowPen(None)

    def clear_selection(self):
        self.selected_data = None
        self.selected_lines = []
        self.highlight_lines()

    def box_select_decay_lines(self, rect):
        """
        Signal slot, select all lines that intersect the drawn rectangle.
        :param rect: QRectF object
        """

        def change_profile_tab():
            self.profile_tab_widget.setCurrentIndex(self.last_active_ax_ind)

        def intersects_rect(line):
            """
            Uses cohen-sutherland algorithm to find if a line intersects the rectangle at any point.
            :param line: PlotCurveItem
            :return: bool
            """
            xi, yi = line.xData, line.yData

            # Line is broken down into segments for the algorithm
            for i, (x, y) in enumerate(zip(xi[:-1], yi[:-1])):
                x1, y1 = float(x), y
                x2, y2 = float(xi[i + 1]), yi[i + 1]
                x3, y3, x4, y4 = lc.cohensutherland(left, top, right, bottom, x1, y1, x2, y2)

                if any([x3, y3, x4, y4]):
                    return True

        # Change the profile tab to the same component as the decay plot that was clicked
        change_profile_tab()

        # Create the clip window for the line clipping algorithm.
        left, top, right, bottom = min(rect.left(), rect.right()), max(rect.top(), rect.bottom()), \
                                   max(rect.left(), rect.right()), min(rect.top(), rect.bottom())
        lines = [line for line in self.last_active_ax.curves if intersects_rect(line)]

        if keyboard.is_pressed('ctrl'):
            self.selected_lines.extend(lines)
        else:
            self.selected_lines = lines
        self.selected_data = None

        self.highlight_lines()
        self.get_selected_data()

    def get_selected_data(self):
        """
        Return the corresponding data of the decay lines that are currently selected
        :return: pandas DataFrame
        """
        ind = [self.plotted_decay_lines.index(line) for line in self.selected_lines]
        data = self.plotted_decay_data.iloc[ind]
        return data

    def delete_lines(self):
        """
        Delete the selected lines. The data corresponding to the selected lines have their deletion flags flipped
        (i.e. from True > False or False > True). The station is then re-plotted. Line highlight is preserved.
        """
        selected_data = self.get_selected_data()
        if not selected_data.empty:
            # Change the deletion flag
            selected_data.loc[:, 'del_flag'] = selected_data.loc[:, 'del_flag'].map(lambda x: not x)

            # Update the data in the pem file object
            self.pem_file.data.iloc[selected_data.index] = selected_data
            self.plot_profiles(components=selected_data.Component.unique())
            self.plot_station(self.selected_station, preserve_selection=True)

    def change_component(self, component):
        """
        Change the component of the selected data
        :param component: str
        """
        selected_data = self.get_selected_data()
        old_comp = selected_data.Component.unique()[0]

        if not selected_data.empty and component != old_comp:
            # Change the deletion flag
            selected_data.loc[:, 'Component'] = selected_data.loc[:, 'Component'].map(lambda x: component.upper())

            # Update the data in the pem file object
            self.pem_file.data.iloc[selected_data.index] = selected_data
            self.plot_profiles(components=[old_comp, component])
            self.plot_station(self.selected_station, preserve_selection=True)

    def change_station(self):
        """
        Opens a input dialog to change the station name of the selected data
        """
        if self.selected_lines:
            selected_data = self.get_selected_data()
            selected_station = selected_data.Station.unique()[0]

            new_station, ok_pressed = QInputDialog.getText(self, "Change Station", "New Station:", QLineEdit.Normal,
                                                           selected_station)
            if ok_pressed:
                new_station = new_station.upper()
                if re.match('-?\d+', new_station):
                    # Update the station number in the selected data
                    selected_data.loc[:, 'Station'] = new_station
                    # Update the data in the pem file object
                    self.pem_file.data.iloc[selected_data.index] = selected_data

                    # Update the plots
                    self.plot_profiles(components=selected_data.Component.unique())
                    self.plot_station(self.selected_station)

    def flip_decays(self):
        """
        Flip the polarity of the decays of the selected data.
        """
        selected_data = self.get_selected_data()
        if not selected_data.empty:
            # Change the deletion flag
            selected_data.loc[:, 'Reading'] = selected_data.loc[:, 'Reading'].map(lambda x: x * -1)

            # Update the data in the pem file object
            self.pem_file.data.iloc[selected_data.index] = selected_data
            self.plot_profiles(components=selected_data.Component.unique())
            self.plot_station(self.selected_station, preserve_selection=True)


class DecayViewBox(pg.ViewBox):
    box_select_signal = QtCore.pyqtSignal(object)

    def __init__(self, *args, **kwds):
        pg.ViewBox.__init__(self, *args, **kwds)
        # self.setMouseMode(self.RectMode)
        brush = QtGui.QBrush(QtGui.QColor('blue'))
        pen = QtGui.QPen(brush, 1)
        # self.rbScaleBox.setPen(pen)
        self.rbScaleBox.setBrush(brush)
        self.rbScaleBox.setOpacity(0.2)

    def mouseDragEvent(self, ev, axis=None):
        pos = ev.pos()

        if keyboard.is_pressed('shift'):
            ev.accept()  # we accept all buttons

            lastPos = ev.lastPos()
            dif = pos - lastPos
            dif = dif * -1

            if ev.isFinish():  # This is the final move in the drag; change the view scale now
                # print "finish"
                self.rbScaleBox.hide()
                ax = QtCore.QRectF(Point(ev.buttonDownPos(ev.button())), Point(pos))
                ax = self.childGroup.mapRectFromParent(ax)
                self.showAxRect(ax)
                self.axHistoryPointer += 1
                self.axHistory = self.axHistory[:self.axHistoryPointer] + [ax]
            else:
                # update shape of scale box
                self.updateScaleBox(ev.buttonDownPos(), ev.pos())

        else:

            if ev.button() == QtCore.Qt.LeftButton:
                ev.accept()
                if ev.isFinish():  # This is the final move in the drag
                    # Hide the rectangle
                    self.rbScaleBox.hide()
                    # Create a rectangle object from the click-and-drag rectangle
                    rect = QtCore.QRectF(Point(ev.buttonDownPos(ev.button())), Point(pos))
                    # Convert the coordinates to the same as the data
                    rect = self.childGroup.mapRectFromParent(rect)
                    # Emit the signal to select the lines that intersect the rect
                    self.box_select_signal.emit(rect)
                else:
                    # update shape of scale box
                    self.updateScaleBox(ev.buttonDownPos(), ev.pos())
            else:
                pg.ViewBox.mouseDragEvent(self, ev)

    def wheelEvent(self, ev, axis=None):

        def invertQTransform(tr):
            """Return a QTransform that is the inverse of *tr*.
            Rasises an exception if tr is not invertible.

            Note that this function is preferred over QTransform.inverted() due to
            bugs in that method. (specifically, Qt has floating-point precision issues
            when determining whether a matrix is invertible)
            """
            try:
                import numpy.linalg
                arr = np.array(
                    [[tr.m11(), tr.m12(), tr.m13()], [tr.m21(), tr.m22(), tr.m23()], [tr.m31(), tr.m32(), tr.m33()]])
                inv = numpy.linalg.inv(arr)
                return QtGui.QTransform(inv[0, 0], inv[0, 1], inv[0, 2], inv[1, 0], inv[1, 1], inv[1, 2], inv[2, 0],
                                        inv[2, 1])
            except ImportError:
                inv = tr.inverted()
                if inv[1] is False:
                    raise Exception("Transform is not invertible.")
                return inv[0]

        if keyboard.is_pressed('shift'):
            if axis in (0, 1):
                mask = [False, False]
                mask[axis] = self.state['mouseEnabled'][axis]
            else:
                mask = self.state['mouseEnabled'][:]
            s = 1.02 ** (ev.delta() * self.state['wheelScaleFactor'])  # actual scaling factor
            s = [(None if m is False else s) for m in mask]
            center = Point(invertQTransform(self.childGroup.transform()).map(ev.pos()))

            self._resetTarget()
            self.scaleBy(s, center)
            ev.accept()
            self.sigRangeChangedManually.emit(mask)


if __name__ == '__main__':
    from src.pem.pem_getter import PEMGetter

    app = QApplication(sys.argv)
    pem_getter = PEMGetter()
    pem_files = pem_getter.get_pems(client='PEM Splitting', selection=0)

    editor = PEMPlotEditor()
    editor.open(pem_files[0])

    app.exec_()