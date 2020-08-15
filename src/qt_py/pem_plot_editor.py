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
from PyQt5.QtWidgets import (QApplication, QMainWindow, QInputDialog, QLineEdit, QLabel, QMessageBox, QFileDialog,
                             QFrame)
from pyqtgraph.Point import Point
# from pyod.models.abod import ABOD
# from pyod.models.knn import KNN
# from pyod.utils.data import get_outliers_inliers

from src.pem.pem_file import StationConverter, PEMParser

if getattr(sys, 'frozen', False):
    application_path = sys._MEIPASS
    plotEditorCreatorFile = 'qt_ui\\pem_plot_editor.ui'
    icons_path = 'icons'
else:
    application_path = os.path.dirname(os.path.abspath(__file__))
    plotEditorCreatorFile = os.path.join(os.path.dirname(application_path), 'qt_ui\\pem_plot_editor.ui')
    icons_path = os.path.join(os.path.dirname(application_path), "qt_ui\\icons")

# Load Qt ui file into a class
Ui_PlotEditorWindow, QtBaseClass = uic.loadUiType(plotEditorCreatorFile)

pg.setConfigOptions(antialias=True)
pg.setConfigOption('background', 'w')
pg.setConfigOption('foreground', 'k')
pg.setConfigOption('crashWarning', True)
pd.options.mode.chained_assignment = None  # default='warn'


class PEMPlotEditor(QMainWindow, Ui_PlotEditorWindow):
    save_sig = QtCore.pyqtSignal(object)
    close_sig = QtCore.pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__()
        self.parent = parent
        self.setupUi(self)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.setWindowTitle('PEM Plot Editor')
        self.setWindowIcon(QtGui.QIcon(os.path.join(icons_path, 'cleaner.png')))
        self.resize(1300, 850)
        self.setAcceptDrops(True)
        self.message = QMessageBox()

        # Status bar formatting
        self.station_text = QLabel()
        self.station_text.setIndent(5)
        self.selection_text = QLabel()
        self.selection_text.setIndent(5)
        self.selection_text.setStyleSheet('color: blue')
        self.file_info_label = QLabel()
        self.file_info_label.setIndent(5)
        self.number_of_readings = QLabel()
        self.number_of_readings.setIndent(5)

        self.setStyleSheet("QStatusBar::item {border-left: 1px solid gray;}")
        self.status_bar.setStyleSheet("border-top: 1px solid gray;")

        self.status_bar.addWidget(self.station_text, 0)
        self.status_bar.addWidget(self.selection_text, 1)
        self.status_bar.addPermanentWidget(self.file_info_label, 0)
        self.status_bar.addPermanentWidget(self.number_of_readings, 0)

        self.converter = StationConverter()
        self.pem_file = None
        self.units = None
        self.stations = np.array([])

        self.line_selected = False
        self.selected_station = None
        self.selected_data = pd.DataFrame()
        self.selected_lines = []
        self.deleted_lines = []
        self.selected_profile_stations = np.array([])

        self.active_ax = None
        self.active_ax_ind = None
        self.last_active_ax = None  # last_active_ax is always a plotitem object, and never None after the init.
        self.last_active_ax_ind = None  # last_active_ax is always a plotitem object, and never None after the init.
        self.plotted_decay_lines = []
        self.plotted_decay_data = pd.DataFrame()

        self.x_decay_plot = self.decay_layout.addPlot(0, 0, title='X Component', viewBox=DecayViewBox())
        self.y_decay_plot = self.decay_layout.addPlot(1, 0, title='Y Component', viewBox=DecayViewBox())
        self.z_decay_plot = self.decay_layout.addPlot(2, 0, title='Z Component', viewBox=DecayViewBox())
        self.decay_layout.ci.layout.setSpacing(2)  # Spacing between plots
        # self.decay_layout.ci.layout.setRowStretchFactor(1, 1)
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
        self.x_ax0 = self.x_profile_layout.addPlot(0, 0, viewBox=ProfileViewBox())
        self.x_ax1 = self.x_profile_layout.addPlot(1, 0, viewBox=ProfileViewBox())
        self.x_ax2 = self.x_profile_layout.addPlot(2, 0, viewBox=ProfileViewBox())
        self.x_ax3 = self.x_profile_layout.addPlot(3, 0, viewBox=ProfileViewBox())
        self.x_ax4 = self.x_profile_layout.addPlot(4, 0, viewBox=ProfileViewBox())

        # Y axis lin plots
        self.y_profile_layout.ci.layout.setSpacing(5)  # Spacing between plots
        self.y_ax0 = self.y_profile_layout.addPlot(0, 0, viewBox=ProfileViewBox())
        self.y_ax1 = self.y_profile_layout.addPlot(1, 0, viewBox=ProfileViewBox())
        self.y_ax2 = self.y_profile_layout.addPlot(2, 0, viewBox=ProfileViewBox())
        self.y_ax3 = self.y_profile_layout.addPlot(3, 0, viewBox=ProfileViewBox())
        self.y_ax4 = self.y_profile_layout.addPlot(4, 0, viewBox=ProfileViewBox())

        # Z axis lin plots
        self.z_profile_layout.ci.layout.setSpacing(5)  # Spacing between plots
        self.z_ax0 = self.z_profile_layout.addPlot(0, 0, viewBox=ProfileViewBox())
        self.z_ax1 = self.z_profile_layout.addPlot(1, 0, viewBox=ProfileViewBox())
        self.z_ax2 = self.z_profile_layout.addPlot(2, 0, viewBox=ProfileViewBox())
        self.z_ax3 = self.z_profile_layout.addPlot(3, 0, viewBox=ProfileViewBox())
        self.z_ax4 = self.z_profile_layout.addPlot(4, 0, viewBox=ProfileViewBox())

        self.x_layout_axes = [self.x_ax0, self.x_ax1, self.x_ax2, self.x_ax3, self.x_ax4]
        self.y_layout_axes = [self.y_ax0, self.y_ax1, self.y_ax2, self.y_ax3, self.y_ax4]
        self.z_layout_axes = [self.z_ax0, self.z_ax1, self.z_ax2, self.z_ax3, self.z_ax4]

        self.profile_axes = np.concatenate([self.x_layout_axes, self.y_layout_axes, self.z_layout_axes])
        self.active_profile_axes = []

        # Configure each axes
        for ax in self.profile_axes:
            ax.vb.box_select_signal.connect(self.box_select_profile_plot)
            ax.hideButtons()
            ax.setMenuEnabled(False)
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
            # selected_v_line_text = pg.TextItem("", anchor=(0, 0))
            # selected_v_line_text.setParentItem(ax.vb)
            # selected_v_line_text.setPos(0, 0)
            # selected_v_line_text.setColor((51, 51, 255, 100))

            ax.addItem(hover_v_line, ignoreBounds=True)
            ax.addItem(selected_v_line, ignoreBounds=True)
            ax.addItem(hover_v_line_text, ignoreBounds=True)
            # ax.addItem(selected_v_line_text, ignoreBounds=True)

            # Connect the mouse moved signal
            ax.scene().sigMouseMoved.connect(self.profile_mouse_moved)
            ax.scene().sigMouseClicked.connect(self.profile_plot_clicked)

        # Signals
        self.profile_tab_widget.currentChanged.connect(self.profile_tab_changed)
        self.show_average_cbox.toggled.connect(lambda: self.plot_profiles('all'))
        self.show_scatter_cbox.toggled.connect(lambda: self.plot_profiles('all'))
        self.plot_ontime_decays_cbox.toggled.connect(lambda: self.plot_station(self.selected_station,
                                                                               preserve_selection=True))
        self.plot_ontime_decays_cbox.toggled.connect(lambda: self.active_decay_axes[0].autoRange())

        self.link_y_cbox.toggled.connect(self.link_decay_y)
        self.link_x_cbox.toggled.connect(self.link_decay_x)

        self.change_station_btn.clicked.connect(self.change_station)
        self.auto_clean_btn.clicked.connect(self.auto_clean)
        self.actionOpen.triggered.connect(self.open_file_dialog)
        self.actionSave.triggered.connect(self.save)
        self.actionSave_As.triggered.connect(self.save_as)

    def keyPressEvent(self, event):
        # Delete a decay when the delete key is pressed
        if event.key() == QtCore.Qt.Key_Delete or event.key() == QtCore.Qt.Key_C:
            t = time.time()
            self.delete_lines()
            print(f"Time to delete and replot: {time.time() - t}")

        # Cycle through highlighted decays forwards
        elif event.key() == QtCore.Qt.Key_D or event.key() == QtCore.Qt.RightArrow:
            self.cycle_selection('up')

        # Cycle through highlighted decays backwards
        elif event.key() == QtCore.Qt.Key_A or event.key() == QtCore.Qt.LeftArrow:
            self.cycle_selection('down')

        # Cycle through the selection station forwards
        elif event.key() == QtCore.Qt.Key_W:
            self.cycle_station('up')

        # Cycle through the selection station backwards
        elif event.key() == QtCore.Qt.Key_S:
            self.cycle_station('down')

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
            self.reset_range()

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

    def dragEnterEvent(self, e):
        urls = [url.toLocalFile() for url in e.mimeData().urls()]
        if all([url.lower().endswith('pem') for url in urls]):
            e.accept()

    def dropEvent(self, e):
        urls = [url.toLocalFile() for url in e.mimeData().urls()]
        self.open(urls[0])

    def open(self, pem_file):
        """
        Open a PEMFile object and plot the data.
        :param pem_file: PEMFile object.
        """
        if isinstance(pem_file, str):
            parser = PEMParser()
            pem_file = parser.parse(pem_file)

        self.pem_file = pem_file
        self.file_info_label.setText(f"Timebase {self.pem_file.timebase:.2f}ms    {self.pem_file.get_survey_type()} Survey")

        # Add the deletion flag column
        if 'del_flag' not in self.pem_file.data.columns:
            self.pem_file.data.insert(13, 'del_flag', False)

        if self.pem_file.is_split():
            # self.plot_ontime_decays_cbox.setChecked(False)  # Triggers the signal
            self.plot_ontime_decays_cbox.setEnabled(False)
        else:
            self.plot_ontime_decays_cbox.setEnabled(True)

        # Set the units of the decay plots
        self.units = self.pem_file.units

        # Add the line name and loop name as the title for the profile plots
        for ax in [self.x_ax0, self.y_ax0, self.z_ax0]:
            ax.setTitle(f"{self.pem_file.line_name}\t\tLoop {self.pem_file.loop_name}")

        # Set the X and Y axis labels for the decay axes
        for ax in self.decay_axes:
            ax.setLabel('left', f"Response", units=self.units)
            ax.setLabel('bottom', 'Channel number')

        # Plot the LIN profiles
        self.plot_profiles()
        # Plot the first station. This also helps with the linking of the X and Y axes for the decay plots.
        self.plot_station(self.stations.min())

        # Link the X and Y axis of each axes
        self.link_decay_x()
        self.link_decay_y()
        self.reset_range()

        self.show()

    def open_file_dialog(self):
        """
        Open files through the file dialog
        """
        files = QFileDialog.getOpenFileNames(self, 'Open File', filter='PEM files (*.pem)')
        if files[0] != '':
            file = files[0][0]
            if file.lower().endswith('.pem'):
                self.open(file)

    def closeEvent(self, e):
        self.close_sig.emit(self)
        # for ax in np.concatenate([self.decay_axes, self.profile_axes]):
        #     ax.vb.close()
        e.accept()

    def save(self):
        """
        Save the PEM file
        """
        self.status_bar.showMessage('Saving file...')
        self.pem_file.data = self.pem_file.data[self.pem_file.data.del_flag == False]
        self.pem_file.save()
        self.plot_profiles('all')
        self.plot_station(self.selected_station, preserve_selection=False)

        self.status_bar.showMessage('File saved.', 2000)
        QtCore.QTimer.singleShot(2000, lambda: self.station_text.setText(station_text))
        self.save_sig.emit(self.pem_file)

    def save_as(self):
        """
        Save the PEM file to a new file name
        """
        file_path = QFileDialog.getSaveFileName(self, '', str(self.pem_file.filepath), 'PEM Files (*.PEM)')[0]
        if file_path:
            text = self.pem_file.to_string()
            print(text, file=open(str(file_path), 'w+'))

            self.status_bar.showMessage(f'File saved to {file_path}', 2000)
            QtCore.QTimer.singleShot(2000, lambda: self.station_text.setText(station_text))

    def update_file(self):

        def toggle_decay_plots():
            """
            Show/hide decay plots and profile plot tabs based on the components in the pem file
            """
            x_ax = self.x_decay_plot
            y_ax = self.y_decay_plot
            z_ax = self.z_decay_plot

            if 'X' in components:
                x_ax.show()
                self.profile_tab_widget.setTabEnabled(0, True)

                if x_ax not in self.active_decay_axes:
                    self.active_decay_axes.append(x_ax)
            else:
                x_ax.hide()
                self.profile_tab_widget.setTabEnabled(0, False)

                if x_ax in self.active_decay_axes:
                    self.active_decay_axes.remove(x_ax)

            if 'Y' in components:
                y_ax.show()
                self.profile_tab_widget.setTabEnabled(1, True)

                if y_ax not in self.active_decay_axes:
                    self.active_decay_axes.append(y_ax)
            else:
                y_ax.hide()
                self.profile_tab_widget.setTabEnabled(1, False)

                if y_ax in self.active_decay_axes:
                    self.active_decay_axes.remove(y_ax)

            if 'Z' in components:
                z_ax.show()
                self.profile_tab_widget.setTabEnabled(2, True)

                if z_ax not in self.active_decay_axes:
                    self.active_decay_axes.append(z_ax)
            else:
                z_ax.hide()
                self.profile_tab_widget.setTabEnabled(2, False)

                if z_ax in self.active_decay_axes:
                    self.active_decay_axes.remove(z_ax)

            self.link_decay_x()
            self.link_decay_y()

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
            # Add or remove axes from the list of active profile axes
            if 'X' in components:
                if all([ax not in self.active_profile_axes for ax in self.x_layout_axes]):
                    self.active_profile_axes.extend(self.x_layout_axes)
            else:
                for ax in self.x_layout_axes:
                    if ax in self.active_profile_axes:
                        self.active_profile_axes.remove(ax)

            if 'Y' in components:
                if all([ax not in self.active_profile_axes for ax in self.y_layout_axes]):
                    self.active_profile_axes.extend(self.y_layout_axes)
            else:
                for ax in self.y_layout_axes:
                    if ax in self.active_profile_axes:
                        self.active_profile_axes.remove(ax)

            if 'Z' in components:
                if all([ax not in self.active_profile_axes for ax in self.z_layout_axes]):
                    self.active_profile_axes.extend(self.z_layout_axes)
            else:
                for ax in self.z_layout_axes:
                    if ax in self.active_profile_axes:
                        self.active_profile_axes.remove(ax)

            link_profile_axes()
            print(f"Number of active profile axes: {len(self.active_profile_axes)}")

        # Update the list of stations
        self.stations = np.sort(self.pem_file.get_stations(converted=True))

        # Select a new selected station if it no longer exists
        if self.selected_station not in self.stations:
            self.selected_station = self.stations[0]

        # Re-calculate the converted station numbers
        self.pem_file.data['cStation'] = self.pem_file.data.Station.map(self.converter.convert_station)

        components = self.pem_file.get_components()
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

            # Only plot off-time channels
            number_of_channels = len(file.channel_times[file.channel_times.Remove == False]) - 1

            num_channels_per_plot = int((number_of_channels - 1) // 4)
            remainder_channels = int((number_of_channels - 1) % 4)

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
                Plot the lines on the pyqtgraph ax
                :param df: DataFrame of filtered data
                :param ax: pyqtgraph PlotItem
                """
                global lin_plotting_time, averaging_time

                t = time.time()
                df_avg = df.groupby('Station').mean()
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
                """
                Plot the scatter plot markers
                :param df: DataFrame of filtered data
                :param ax: pyqtgraph PlotItem
                :return:
                """
                global scatter_plotting_time
                t = time.time()
                x, y = df.index, df

                scatter = pg.ScatterPlotItem(x=x, y=y,
                                             pen=pg.mkPen('k', width=1.),
                                             symbol='o',
                                             size=2,
                                             brush='w',
                                             )

                # Color the scatters of the highlighted stations a different color
                if self.selected_profile_stations.any():
                    selected_df = df.where((df.index >= self.selected_profile_stations.min()) &
                                           (df.index <= self.selected_profile_stations.max())).dropna()
                    sx, sy = selected_df.index, selected_df

                    selected_scatter = pg.ScatterPlotItem(x=sx, y=sy,
                                                          pen=pg.mkPen('b', width=1.5),
                                                          symbol='o',
                                                          size=2.5,
                                                          brush='w',
                                                          )
                    selected_scatter.setZValue(10)
                    ax.addItem(selected_scatter)

                ax.addItem(scatter)
                scatter_plotting_time += time.time() - t

            # Plotting
            for i, bounds in enumerate(channel_bounds):
                ax = axes[i]

                # Set the Y-axis labels
                if i == 0:
                    ax.setLabel('left', f"PP channel", units=self.units)
                else:
                    ax.setLabel('left', f"Channel {bounds[0]} to {bounds[1]}", units=self.units)

                # Plot the data
                for channel in range(bounds[0], bounds[1] + 1):
                    data = profile_data.iloc[:, channel]

                    if self.show_average_cbox.isChecked():
                        plot_lines(data, ax)
                    if self.show_scatter_cbox.isChecked():
                        plot_scatters(data, ax)

        t = time.time()
        self.update_file()
        print(f"Time to update file: {time.time() - t}")

        file = copy.deepcopy(self.pem_file)
        file.data = file.data.loc[file.data.del_flag == False]

        self.number_of_readings.setText(f"{len(file.data)} readings ")

        # Get the components
        if components is None or components == 'all':
            components = file.get_components()

        # Clear the plots of the components that are to be plotted only
        clear_plots(components)

        t = time.time()
        global averaging_time, lin_plotting_time, scatter_plotting_time
        averaging_time = 0
        lin_plotting_time = 0
        scatter_plotting_time = 0

        # Calculate the lin plot axes channel bounds
        channel_bounds = calc_channel_bounds()

        for component in components:
            tp = time.time()
            profile_data = file.get_profile_data(component, averaged=False, converted=True, ontime=False)
            print(f"Time getting profile data: {time.time() - tp}")
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

        print(f"Time to make lin plots: {lin_plotting_time}")
        print(f"Time to make scatter plots: {scatter_plotting_time}")
        print(f"Averaging time: {averaging_time}")
        print(f"Total plotting time for profile plots: {time.time() - t}")

    def plot_station(self, station, preserve_selection=False):
        """
        Plot the decay lines for each component of the given station
        :param station: int, station number
        :param preserve_selection: bool, re-select the selected lines after plotting
        """

        def set_status_text(data):
            """
            Set the status bar text with information about the station
            :param data: dataFrame of plotted decays
            """
            global station_text
            stn = data.Station.unique()
            if stn:
                station_number_text = f"Station {stn[0]}"
                reading_numbers = data.Reading_number.unique()
                if len(reading_numbers) > 1:
                    r_numbers_range = f"Reading numbers {reading_numbers.min()} - {reading_numbers.max()}"
                else:
                    r_numbers_range = f"Reading number {reading_numbers.min()}"

                station_readings = f"{len(data.index)} {'Reading' if len(data.index) == 1 else 'Readings'}"

                station_text = '    '.join([station_number_text, station_readings, r_numbers_range])
            else:
                station_text = ''
            self.station_text.setText(station_text)

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
                z_value = 1
                pen = pg.mkPen((96, 96, 96), width=1.)
            else:
                z_value = 2
                pen = pg.mkPen('r', width=1.)

            # Remove the on-time channels if the checkbox is checked
            if self.plot_ontime_decays_cbox.isChecked():
                y = row.Reading
            else:
                y = row.Reading[~self.pem_file.channel_times.Remove]

            # Create and configure the line item
            decay_line = pg.PlotCurveItem(y=y,
                                          pen=pen,
                                          )
            decay_line.setClickable(True, width=5)
            decay_line.setZValue(z_value)
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

        # Update the status bar text
        set_status_text(self.plotted_decay_data)

        # Update the titles of each decay axes
        station = self.plotted_decay_data.Station.unique()[0]
        self.x_decay_plot.setTitle(f"Station {station} - X Component")
        self.y_decay_plot.setTitle(f"Station {station} - Y Component")
        self.z_decay_plot.setTitle(f"Station {station} - Z Component")

        # Plot the decays
        self.plotted_decay_data.apply(plot_decay, axis=1)

        # Update the plot limits
        for ax in self.decay_axes:
            if self.plot_ontime_decays_cbox.isChecked():
                y = len(self.pem_file.channel_times)
            else:
                y = len(self.pem_file.channel_times[self.pem_file.channel_times.Remove == False])

            ax.setLimits(minXRange=0, maxXRange=y - 1,
                         xMin=0, xMax=y - 1)

        # Re-select lines that were selected
        if preserve_selection is True:
            self.selected_lines = [self.plotted_decay_lines[i] for i in index_of_selected]
            self.highlight_lines()
        else:
            self.selection_text.setText('')

        if self.auto_range_cbox.isChecked() and preserve_selection is False:
            for ax in self.active_decay_axes:
                ax.autoRange()

    def reset_range(self):
        """
        Auto range all axes
        """
        if self.link_y_cbox.isChecked():
            filt = self.pem_file.data.cStation == self.selected_station
            min_y = self.pem_file.data.loc[filt].Reading.map(lambda x: x.min()).min()
            max_y = self.pem_file.data.loc[filt].Reading.map(lambda x: x.max()).max()
            self.active_decay_axes[0].setYRange(min_y, max_y)
        else:
            for ax in self.decay_axes:
                ax.autoRange()

        self.active_profile_axes[0].autoRange()

    def highlight_lines(self):
        """
        Highlight the line selected and un-highlight any previously highlighted line.
        :param lines: list, PlotItem lines
        """

        def set_selection_text(selected_data):
            """
            Update the status bar with information about the selected lines
            """
            if self.selected_lines:

                # Show the range of reading numbers and reading indexes if multiple decays are selected
                if len(selected_data) > 1:
                    r_numbers = selected_data.Reading_number.unique()
                    r_indexes = selected_data.Reading_index.unique()
                    if len(r_numbers) > 1:
                        r_number_text = f"Reading numbers: {r_numbers.min()} - {r_numbers.max()}"
                    else:
                        r_number_text = f"Reading number: {r_numbers.min()}"

                    if len(r_indexes) > 1:
                        r_index_text = f"Reading indexes: {r_indexes.min()} - {r_indexes.max()}"
                    else:
                        r_index_text = f"Reading index: {r_indexes.min()}"

                    selection_text = f"{len(selected_data)} selected    {r_number_text}    {r_index_text}"

                # Show the reading number, reading index for the selected decay, plus azimuth, dip, and roll for bh
                else:
                    selected_decay = selected_data.iloc[0]
                    r_number_text = f"Reading Number {selected_decay.Reading_number}"
                    r_index_text = f"Reading Index {selected_decay.Reading_index}"

                    if self.pem_file.is_borehole() and selected_decay.RAD_tool.has_tool_values():
                        azimuth = f"Azimuth {selected_decay.RAD_tool.get_azimuth():.2f}"
                        dip = f"Dip {selected_decay.RAD_tool.get_dip():.2f}"
                        roll = f"Roll angle {selected_decay.RAD_tool.get_acc_roll():.2f}"
                        selection_text = f"{'    '.join([r_number_text, r_index_text, azimuth, dip, roll])}"
                    else:
                        selection_text = f"{'    '.join([r_number_text, r_index_text])}"

                self.selection_text.setText(selection_text)

            # Reset the selection text if nothing is selected
            else:
                self.selection_text.setText('')

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
                    z_value = 4
                else:
                    pen_color = (96, 96, 96)
                    z_value = 3

                if line in self.selected_lines:
                    if del_flag is False:
                        pen_color = (85, 85, 255)  # Blue
                        # pen_color = (204, 0, 204)  # Magenta ish
                        # pen_color = (153, 51, 255)  # Puple

                    print(f"Line {self.plotted_decay_lines.index(line)} selected")
                    line.setPen(pen_color, width=2)
                    line.setZValue(z_value)
                    if len(self.selected_lines) == 1:
                        line.setShadowPen(pg.mkPen('w', width=2.5, cosmetic=True))
                else:
                    line.setPen(pen_color, width=1)
                    line.setShadowPen(None)

            set_selection_text(self.get_selected_data())

    def clear_selection(self):
        self.selected_data = None
        self.selected_lines = []
        self.highlight_lines()
        self.selected_profile_stations = np.array([])
        # Hide the LinearRegionItem in each axes
        for ax in self.profile_axes:
            ax.vb.lr.hide()

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
        mouse_point = self.active_profile_axes[0].vb.mapSceneToView(pos)
        nearest_station = find_nearest_station(int(mouse_point.x()))

        for ax in self.active_profile_axes:
            ax.items[0].setPos(nearest_station)  # Move the click vertical line
            ax.items[2].setPos(nearest_station, ax.viewRange()[1][1])  # Move the hover vertical like
            ax.items[2].setText(str(nearest_station))

    def profile_plot_clicked(self, evt):
        """
        Signal slot, when the profile plot is clicked. Plots a darker blue vertical line at the nearest station where
        the click was made and plots that station's decays in the decay plot.
        Uses the nearest station calculated in self.profile_mouse_moved.
        :param evt: pyqtgraph MouseClickEvent (not used)
        """
        self.selected_station = nearest_station
        # for ax in self.active_profile_axes:
        #     ax.items[3].setPos(nearest_station, ax.viewRange()[1][1])
        #     ax.items[3].setText(str(nearest_station))

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

    def box_select_profile_plot(self, range):
        """
        Signal slot, select stations from the profile plot when click-and-dragged
        :param range: tuple, range of the linearRegionItem
        """
        # Update the LinearRegionItem for each axes
        for ax in self.profile_axes:
            ax.vb.lr.setRegion((range[0], range[1]))
            ax.vb.lr.show()

            # Find the stations that fall within the selection range
            self.selected_profile_stations = self.stations[
                np.where((self.stations < range[0]) & (self.stations > range[1]))]

    def profile_tab_changed(self, ind):
        pass

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
            self.pem_file.data.loc[selected_data.index] = selected_data
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

    def cycle_station(self, direction):
        """
        Change the selected station
        :param direction: str, direction to cycle stations. Either 'up' or 'down'.
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

    def cycle_selection(self, direction):
        """
        Change the selected decay
        :param direction: str, direction to cycle decays. Either 'up' or 'down'.
        """
        if not self.selected_lines:
            return

        # Cycle through highlighted decays backwards
        if direction == 'down':
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
        elif direction == 'up':
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

    def auto_clean(self):
        """
        Automatically detect and delete readings with outlier values.
        """

        def clean_group(group):

            def eval_decay(reading, min_cutoff, max_cutoff):
                if any(reading[mask] < min_cutoff) or any(reading[mask] > max_cutoff):
                    global count
                    count += 1
                    return True
                else:
                    return False

            readings = np.array(group.Reading.to_list())
            data_std = np.std(readings, axis=0)[mask]
            data_median = np.median(readings, axis=0)[mask]
            min_cutoff = data_median - data_std * 3
            max_cutoff = data_median + data_std * 3

            if len(group.loc[group.del_flag == False]) > 3:
                group.del_flag = group.Reading.map(lambda x: eval_decay(x, min_cutoff, max_cutoff))

            return group

        if self.pem_file.is_averaged():
            return

        global count, mask
        count = 0

        # Filter the data to only see readings that aren't already flagged for deletion
        data = self.pem_file.data[self.pem_file.data.del_flag == False]
        # Filter the readings to only consider off-time channels
        mask = np.asarray(self.pem_file.channel_times.Remove == False)
        # Clean the data
        cleaned_data = data.groupby(['Station', 'Component']).apply(clean_group)
        # Update the data
        self.pem_file.data[self.pem_file.data.del_flag == False] = cleaned_data

        # Plot the new data
        self.plot_profiles()
        self.plot_station(self.selected_station)

        self.message.information(self, 'Auto-clean results', f"{count} reading(s) automatically deleted.")


class DecayViewBox(pg.ViewBox):
    """
    Custom ViewBox for the decay plots. Allows box selecting, box-zoom when shift is held, and mouse wheel when shift
    is held does mouse wheel zoom
    """
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


class ProfileViewBox(pg.ViewBox):
    """
    Custom ViewBox for profile plots. Click and drag creates a linear region selector.
    """
    box_select_signal = QtCore.pyqtSignal(object)

    def __init__(self, *args, **kwds):
        pg.ViewBox.__init__(self, *args, **kwds)
        brush = QtGui.QBrush(QtGui.QColor('blue'))
        pen = QtGui.QPen(brush, 1)

        self.lr = pg.LinearRegionItem([-100, 100], movable=False)
        self.lr.setZValue(-10)
        self.lr.hide()
        self.addItem(self.lr)

        # self.lr.setBrush(brush)
        # self.lr.setOpacity(0.2)

    def mouseDragEvent(self, ev, axis=None):
        if ev.button() == QtCore.Qt.LeftButton:
            ev.accept()
            range = [self.mapToView(ev.buttonDownPos()).x(), self.mapToView(ev.pos()).x()]

            if ev.isFinish():  # This is the final move in the drag
                # self.lr.hide()
                self.box_select_signal.emit(range)
            else:
                # update region of the LinearRegionItem
                self.lr.show()
                # self.lr.setRegion([self.mapToView(ev.buttonDownPos()).x(), self.mapToView(ev.pos()).x()])
                self.box_select_signal.emit(range)
                ev.accept()
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
    pem_files = pem_getter.get_pems(file='7600N.PEM')

    editor = PEMPlotEditor()
    editor.open(pem_files[0])
    # editor.auto_clean()

    app.exec_()