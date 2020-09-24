import sys
import os
import copy
import math
import numpy as np
import time
import pandas as pd
from PyQt5 import (QtCore, QtGui, uic)
from PyQt5.QtWidgets import (QMainWindow, QApplication, QMessageBox, QRadioButton, QGridLayout,
                             QLabel, QLineEdit, QShortcut, QFileDialog)
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
    accept_sig = QtCore.pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.parent = parent
        self.pem_file = None
        self.rotated_file = None
        self.pp_plotted = False
        self.rotation_note = None
        self.soa = self.soa_sbox.value()

        self.setWindowTitle('XY De-rotation')
        self.setWindowIcon(QtGui.QIcon(os.path.join(icons_path, 'derotate.png')))

        self.message = QMessageBox()

        self.button_box.accepted.connect(lambda: self.accept_sig.emit(self.rotated_file))
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

        self.axes = np.concatenate([self.x_view_axes, self.y_view_axes, [self.rot_ax], [self.pp_ax]])
        # Disable the 'A' button and auto-scaling SI units
        for ax in self.axes:
            ax.hideButtons()
            ax.getAxis('left').enableAutoSIPrefix(enable=False)
            ax.getAxis('top').enableAutoSIPrefix(enable=False)

        # Signals

        self.actionStats.triggered.connect(self.export_stats)

    def export_stats(self):
        """
        Save the stats to a CSV file.
        """
        save_file = QFileDialog().getSaveFileName(self, 'Save CSV File',
                                                  str(self.pem_file.filepath.with_suffix('.CSV')),
                                                  'CSV Files (*.CSV);;')[0]
        if save_file:
            df = self.get_stats()
            df.to_csv(save_file, header=True, index=False)

    def get_stats(self):

        def get_pp_info(reading):
            """
            Return the relevant information in the reading, mostly in the RAD_Tool object.
            :param reading: PEMFile reading
            :return: list
            """
            rad = reading.RAD_tool
            station = reading.Station
            return [station, rad.azimuth, rad.dip,
                    rad.x_pos, rad.y_pos, rad.z_pos,
                    rad.ppx_theory, rad.ppy_theory, rad.ppz_theory]

        if self.pp_btn.isEnabled():
            pp_info = self.pem_file.data.apply(get_pp_info, axis=1)
            df = pd.DataFrame([f for f in pp_info.to_numpy()],
                              columns=['Station', 'Azimuth', 'Dip',
                                       'X Position', 'Y Position', 'Z Position',
                                       'PPx Theory', 'PPy Theory', 'PPz Theory']).drop_duplicates(inplace=False,
                                                                                                  subset='Station')
            return df

    def reset_range(self):
        """
        Reset the range of each plot
        """
        for ax in self.axes:
            ax.autoRange()
            ax.enableAutoRange(enable=True)

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

        def fill_table(stations):
            """
            Fill the stations list with the ineligible readings
            :param stations: DataFrame of ineligible readings
            """
            self.list.clear()
            for s in stations.itertuples():
                result = f"{s.Station} {s.Component} - reading # {s.Reading_number} (index {s.Reading_index})"
                self.list.addItem(result)

        if not pem_file:
            self.message.critical(self, 'Error', 'PEM file is invalid')
            return
        elif pem_file.data.empty:
            self.message.critical(self, 'Error', f"No EM data in {pem_file.filepath.name}")
            return

        while isinstance(pem_file, list):
            pem_file = pem_file[0]

        # Ensure the file is a borehole and it has both X and Y component data
        if all([pem_file.is_borehole(), 'X' in pem_file.get_components(), 'Y' in pem_file.get_components()]):
            self.pem_file = pem_file
        else:
            self.message.information(self, 'Ineligible File',
                                     'File must be a borehole survey with X and Y component data.')
            return

        # # Check that the file hasn't already been de-rotated.
        # if self.pem_file.is_rotated():
        #     response = self.message.question(self, 'File already de-rotated',
        #                                      f"{pem_file.filepath.name} is already de-rotated. " +
        #                                      'Do you wish to de-rotate again?',
        #                                      self.message.Yes | self.message.No)
        #     if response == self.message.No:
        #         return

        if self.pem_file.has_loop_gps() and self.pem_file.has_geometry():
            self.pp_btn.setEnabled(True)
        else:
            self.pp_btn.setEnabled(False)

        try:
            self.pem_file, ineligible_stations = self.pem_file.prep_rotation()
        except Exception as e:
            # Common exception will be that there is no eligible data
            self.message.information(self, 'Error', str(e))
        else:
            self.setWindowTitle(f"XY De-rotation - {pem_file.filepath.name}")

            # Disable the PP values tab if there's no PP information
            if all([self.pem_file.has_loop_gps(), self.pem_file.has_geometry(), self.pem_file.ramp > 0]):
                self.tabWidget.setTabEnabled(1, True)
            else:
                self.tabWidget.setTabEnabled(1, False)

            # Fill the table with the ineligible stations
            if not ineligible_stations.empty:
                fill_table(ineligible_stations)
                self.bad_stations_label.show()
                self.list.show()
            else:
                self.bad_stations_label.hide()
                self.list.hide()

            self.rotate()
            self.show()

    def plot_pem(self, pem_file):
        """
        Plot the PEM file in a LIN plot style, with both components in separate plots
        :param pem_file: PEMFile object
        """

        def clear_plots():
            for ax in self.axes:
                if ax not in [self.pp_ax, self.rot_ax]:
                    ax.clear()

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

        def plot_lin(component):

            def plot_lines(df, ax):
                """
                Plot the lines on the pyqtgraph ax for a given channel
                :param df: DataFrame of filtered data
                :param ax: pyqtgraph PlotItem
                """
                df = df.groupby('Station').mean()
                x, y = df.index, df

                ax.plot(x=x, y=y,
                        pen=pg.mkPen('k', width=1.),
                        symbol='o',
                        symbolSize=2,
                        symbolBrush='k',
                        symbolPen='k',
                        )

            profile_data = processed_pem.get_profile_data(component, converted=True)
            if profile_data.empty:
                raise ValueError(f'Profile data for {self.pem_file.filepath.name} is empty.')

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
                    data = profile_data.iloc[:, ch]
                    plot_lines(data, ax)

        def plot_rotation():
            """
            Plot the rotation angle of the tool (if selected) and the PP rotation angles for comparison.
            """
            method = self.get_method()
            if method is not None:
                self.rot_ax.clear()

                ax = self.rot_ax
                x_filt = raw_pem.data['Component'] == 'X'
                stations = raw_pem.data[x_filt].Station.astype(int)

                if self.pp_btn.isEnabled():
                    # Add the cleaned PP information for non-fluxgate surveys
                    if not pem_file.is_fluxgate():
                        x_pp_angle_cleaned = raw_pem.data[x_filt].RAD_tool.map(lambda x: x.cleaned_pp_roll_angle)
                        cpp_item = pg.ScatterPlotItem()
                        cpp_item.setData(x_pp_angle_cleaned, stations,
                                         pen='r',
                                         brush=None,
                                         symbol='t',
                                         size=14)
                        ax.addItem(cpp_item)
                        self.rot_ax_legend.addItem(cpp_item, 'Cleaned PP')

                    x_pp_angle_measured = raw_pem.data[x_filt].RAD_tool.map(lambda x: x.measured_pp_roll_angle)

                    # Create and plot the scatter plot items
                    mpp_item = pg.ScatterPlotItem()
                    mpp_item.setData(x_pp_angle_measured, stations,
                                     pen='b',
                                     brush=None,
                                     symbol='t1',
                                     size=14)

                    # Add the scatter plot items to the scatter plot
                    ax.addItem(mpp_item)
                    # Add the items to the legend
                    self.rot_ax_legend.addItem(mpp_item, 'Measured PP')

                acc_angles = raw_pem.data[x_filt].RAD_tool.map(lambda x: x.acc_roll_angle - self.soa)
                mag_angles = raw_pem.data[x_filt].RAD_tool.map(lambda x: x.mag_roll_angle - self.soa)

                acc_item = pg.ScatterPlotItem()
                mag_item = pg.ScatterPlotItem()
                acc_item.setData(acc_angles, stations,
                                 pen='g',
                                 brush=None,
                                 symbol='o',
                                 size=14)
                mag_item.setData(mag_angles, stations,
                                 pen='m',
                                 brush=None,
                                 symbol='s',
                                 size=14)
                ax.addItem(acc_item)
                ax.addItem(mag_item)
                self.rot_ax_legend.addItem(acc_item, 'Accelerometer')
                self.rot_ax_legend.addItem(mag_item, 'Magnetometer')

        def plot_pp_values():
            """
            Plot the theoretical PP values with the measured (raw) and cleaned PP
            """
            ax = self.pp_ax
            # Used for PP values and rotation angle plots, not lin plots
            x_filt = raw_pem.data['Component'] == 'X'
            stations = raw_pem.data[x_filt].Station.astype(int)

            if not pem_file.is_fluxgate():
                ppxy_cleaned = raw_pem.data[x_filt].RAD_tool.map(lambda x: x.ppxy_cleaned)
                cleaned_item = pg.ScatterPlotItem()
                cleaned_item.setData(ppxy_cleaned, stations,
                                     pen='r',
                                     brush=None,
                                     symbol='t',
                                     size=14)
                ax.addItem(cleaned_item)
                self.pp_ax_legend.addItem(cleaned_item, 'Cleaned PP')

            ppxy_theory = raw_pem.data[x_filt].RAD_tool.map(lambda x: x.ppxy_theory)
            ppxy_measured = raw_pem.data[x_filt].RAD_tool.map(lambda x: x.ppxy_measured)

            theory_item = pg.ScatterPlotItem()
            theory_item.setData(ppxy_theory, stations,
                                pen='g',
                                brush=None,
                                symbol='o',
                                size=14)

            measured_item = pg.ScatterPlotItem()
            measured_item.setData(ppxy_measured, stations,
                                  pen='b',
                                  brush=None,
                                  symbol='t1',
                                  size=14)

            ax.addItem(measured_item)
            ax.addItem(theory_item)

            self.pp_ax_legend.addItem(measured_item, 'Measured PP')
            self.pp_ax_legend.addItem(theory_item, 'Theory')
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
        channel_bounds = calc_channel_bounds()

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

        method = self.get_method()
        self.soa = self.soa_sbox.value()
        # Create a copy of the pem_file so it is never changed
        pem_file = self.pem_file.copy()

        if pem_file.data.empty:
            raise Exception(f"No EM data in {pem_file.filepath.name}")

        print(id(pem_file.data.iloc[0].RAD_tool), id(self.pem_file.data.iloc[0].RAD_tool))

        if method is not None:
            self.rotated_file = pem_file.rotate(method=method, soa=self.soa)
        else:
            self.rotated_file = pem_file

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
            self.rotation_note = '<GEN> XY data de-rotated using PP.'
        else:
            method = None
            self.rotation_note = None
        return method


def main():
    from src.pem.pem_getter import PEMGetter
    from src.pem.pem_file import PEMParser
    app = QApplication(sys.argv)
    mw = Derotator()

    pg = PEMGetter()
    parser = PEMParser()
    # pem_files = pg.get_pems(client='PEM Rotation', file='PU-340 XY.PEM')
    pem_files = parser.parse(r'N:\GeophysicsShare\Dave\Eric\Norman\TC170199XYT.PEM')
    mw.open(pem_files)
    # mw.export_stats()

    app.exec_()


if __name__ == '__main__':
    main()