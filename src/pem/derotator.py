import os
import sys
from pathlib import Path
from src.pem.pem_file import PEMFile

import numpy as np
import pandas as pd
import pyqtgraph as pg
from src.logger import Log
from src.qt_py.custom_qt_widgets import NonScientific
from PyQt5 import (QtCore, QtGui, uic)
from PyQt5.QtWidgets import (QMainWindow, QApplication, QMessageBox, QShortcut, QFileDialog)

import logging
import sys

logger = logging.getLogger(__name__)

# Modify the paths for when the script is being run in a frozen state (i.e. as an EXE)
if getattr(sys, 'frozen', False):
    application_path = os.path.dirname(sys.executable)
    icons_path = 'ui\\icons'
    derotatorCreatorFile = 'ui\\derotator.ui'
else:
    application_path = os.path.dirname(os.path.abspath(__file__))
    icons_path = os.path.join(os.path.dirname(application_path), "ui\\icons")
    derotatorCreatorFile = os.path.join(os.path.dirname(application_path), 'ui\\derotator.ui')

# Load Qt ui file into a class
Ui_Derotator, QtBaseClass = uic.loadUiType(derotatorCreatorFile)

pg.setConfigOptions(antialias=True)
pg.setConfigOption('background', 'w')
pg.setConfigOption('foreground', 'k')
pg.setConfigOption('crashWarning', True)

# TODO Add tool that shows difference in tool rotation value and PP
# TODO add mag to profiles, or to PP values tab.
# TODO Add tab for deviation from cleaned PP


class Derotator(QMainWindow, Ui_Derotator):
    """
    Class that de-rotates XY data of a PEMFile
    """
    accept_sig = QtCore.pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.installEventFilter(self)
        self.parent = parent
        self.pem_file = None
        self.rotated_file = None
        self.pp_plotted = False
        self.rotation_note = None
        self.mag_curves = []
        self.soa = self.soa_sbox.value()

        self.setWindowTitle('XY De-rotation')
        self.setWindowIcon(QtGui.QIcon(os.path.join(icons_path, 'derotate.png')))

        self.message = QMessageBox()

        self.bad_stations_label.hide()
        self.list.hide()
        self.statusBar().hide()

        def update_profile_views(mag_axes, axes):
            for mag_ax, ax in zip(mag_axes, axes):
                mag_ax.setGeometry(ax.vb.sceneBoundingRect())
                mag_ax.linkedViewChanged(ax.vb, mag_ax.XAxis)

        def update_tab_plot_views(mag_axes, axes):
            for mag_ax, ax in zip(mag_axes, axes):
                mag_ax.setGeometry(ax.vb.sceneBoundingRect())
                mag_ax.linkedViewChanged(ax.vb, mag_ax.YAxis)

        def toggle_mag_plots():
            if self.plot_mag_cbox.isChecked():
                for curve in np.concatenate([self.mag_curves, [self.dev_mag_curve]]):
                    curve.show()
                for ax in self.profile_axes:
                    ax.getAxis("right").show()
                self.dev_ax.getAxis("bottom").setLabel("Total Magnetic Field", color='1DD219', units="pT")
                self.dev_ax.getAxis("bottom").setPen(pg.mkPen(color='1DD219'))
                self.dev_ax.getAxis("bottom").setTextPen(pg.mkPen(color='1DD219'))
                self.dev_ax.getAxis("bottom").setStyle(showValues=True)
            else:
                for curve in np.concatenate([self.mag_curves, [self.dev_mag_curve]]):
                    curve.hide()
                for ax in self.profile_axes:
                    ax.getAxis("right").hide()
                self.dev_ax.getAxis("bottom").setLabel("")
                self.dev_ax.getAxis("bottom").setPen(pg.mkPen(color='k'))
                self.dev_ax.getAxis("bottom").setTextPen(pg.mkPen(color='k'))
                self.dev_ax.getAxis("bottom").setStyle(showValues=False)

        # Configure the plots
        self.x_view.ci.layout.setSpacing(10)  # Spacing between plots
        self.x_ax0 = self.x_view.addPlot(0, 0)
        self.x_ax1 = self.x_view.addPlot(1, 0)
        self.x_ax2 = self.x_view.addPlot(2, 0)
        self.x_ax3 = self.x_view.addPlot(3, 0)
        self.x_ax4 = self.x_view.addPlot(4, 0)

        self.mag_x_ax0 = pg.ViewBox()
        self.mag_x_ax1 = pg.ViewBox()
        self.mag_x_ax2 = pg.ViewBox()
        self.mag_x_ax3 = pg.ViewBox()
        self.mag_x_ax4 = pg.ViewBox()

        self.x_view_axes = [self.x_ax0, self.x_ax1, self.x_ax2, self.x_ax3, self.x_ax4]
        self.mag_x_view_axes = [self.mag_x_ax0, self.mag_x_ax1, self.mag_x_ax2, self.mag_x_ax3, self.mag_x_ax4]

        # Configure the lin plot
        self.y_view.ci.layout.setSpacing(10)  # Spacing between plots
        self.y_ax0 = self.y_view.addPlot(0, 0)
        self.y_ax1 = self.y_view.addPlot(1, 0)
        self.y_ax2 = self.y_view.addPlot(2, 0)
        self.y_ax3 = self.y_view.addPlot(3, 0)
        self.y_ax4 = self.y_view.addPlot(4, 0)

        self.mag_y_ax0 = pg.ViewBox()
        self.mag_y_ax1 = pg.ViewBox()
        self.mag_y_ax2 = pg.ViewBox()
        self.mag_y_ax3 = pg.ViewBox()
        self.mag_y_ax4 = pg.ViewBox()

        self.y_view_axes = [self.y_ax0, self.y_ax1, self.y_ax2, self.y_ax3, self.y_ax4]
        self.mag_y_view_axes = [self.mag_y_ax0, self.mag_y_ax1, self.mag_y_ax2, self.mag_y_ax3, self.mag_y_ax4]

        for mag_ax, ax in zip(np.concatenate([self.mag_x_view_axes, self.mag_y_view_axes]),
                              np.concatenate([self.x_view_axes, self.y_view_axes])):
            ax.hideButtons()
            ax.setMenuEnabled(False)
            ax.setXLink(self.x_ax0)
            ax.getAxis('left').setWidth(60)
            ax.getAxis('right').setWidth(60)
            ax.getAxis('left').enableAutoSIPrefix(enable=False)
            ax.getAxis('right').enableAutoSIPrefix(enable=False)

            # Add the mag plot into the profile plot
            ax.showAxis("right")
            ax.scene().addItem(mag_ax)
            mag_ax.setXLink(ax)
            ax.getAxis("right").linkToView(mag_ax)
            ax.getAxis("right").setLabel("Total Magnetic Field", color='1DD219', units="pT")
            ax.getAxis("right").setPen(pg.mkPen(color='1DD219'))
            ax.getAxis("right").setTextPen(pg.mkPen(color='1DD219'))

        # Create the deviation plot
        self.dev_ax = self.deviation_view.addPlot(0, 0, axisItems={'top': NonScientific(orientation="top"),
                                                                   'bottom': NonScientific(orientation="bottom")})
        self.dev_ax_legend = self.dev_ax.addLegend(pen='k', brush='w')
        self.dev_ax_legend.setParent(self.deviation_view)
        self.dev_ax.setLabel('top', 'Acc - PP Rotation (Degrees)')
        self.dev_ax.setLabel('left', 'Station', units=None)
        v_line = pg.InfiniteLine(pos=0, angle=90, pen=pg.mkPen("k", width=0.5))
        self.dev_ax.addItem(v_line)

        # Create the rotation angle plot
        self.rot_ax = self.rotation_view.addPlot(0, 0, axisItems={'top': NonScientific(orientation="top")})
        self.rot_ax_legend = self.rot_ax.addLegend(pen='k', brush='w')
        self.rot_ax_legend.setParent(self.rotation_view)
        self.rot_ax.setLimits(xMin=0, xMax=360)
        self.rot_ax.setLabel('top', 'Rotation Angle', units='Degrees')
        self.rot_ax.setLabel('left', 'Station', units=None)

        # Create the pp values plot
        self.pp_ax = self.pp_view.addPlot(0, 0, axisItems={'top': NonScientific(orientation="top")})
        self.pp_ax_legend = self.pp_ax.addLegend(pen='k', brush='w')
        self.pp_ax_legend.setParent(self.pp_view)
        self.pp_ax.setLabel('top', 'Magnetic Field Strength', units='nT/s')
        self.pp_ax.setLabel('left', 'Station', units=None)

        # Disable the 'A' button and auto-scaling SI units
        for ax in [self.dev_ax, self.rot_ax, self.pp_ax]:
            ax.hideButtons()
            ax.invertY(True)
            ax.showGrid(x=False, y=True, alpha=0.3)
            ax.showAxis('top')
            ax.showAxis('right')
            ax.getAxis("right").setStyle(showValues=False)
            if ax is not self.dev_ax:
                ax.getAxis("bottom").setStyle(showValues=False)

            # ax.getAxis('left').enableAutoSIPrefix(enable=False)
            ax.getAxis('top').enableAutoSIPrefix(enable=False)
            ax.getAxis('bottom').enableAutoSIPrefix(enable=False)

        self.x_dev_curve = pg.PlotCurveItem(pen=pg.mkPen('b', width=1), name="X Component")
        self.y_dev_curve = pg.PlotCurveItem(pen=pg.mkPen('r', width=1), name="Y Component")
        self.x_dev_scatter = pg.ScatterPlotItem(pen=pg.mkPen('b', width=1), brush=pg.mkBrush("w"))
        self.y_dev_scatter = pg.ScatterPlotItem(pen=pg.mkPen('r', width=1), brush=pg.mkBrush("w"))
        self.dev_ax.addItem(self.x_dev_curve)
        self.dev_ax.addItem(self.y_dev_curve)
        self.dev_ax.addItem(self.x_dev_scatter)
        self.dev_ax.addItem(self.y_dev_scatter)

        self.dev_ax_mag = pg.ViewBox()
        self.dev_ax_mag.invertY(True)
        self.dev_ax.scene().addItem(self.dev_ax_mag)
        self.dev_ax.getAxis("bottom").linkToView(self.dev_ax_mag)
        self.dev_ax.getAxis("bottom").setLabel("Total Magnetic Field", color='1DD219', units="pT")
        self.dev_ax.getAxis("bottom").setPen(pg.mkPen(color='1DD219'))
        self.dev_ax.getAxis("bottom").setTextPen(pg.mkPen(color='1DD219'))
        self.dev_ax_mag.setYLink(self.dev_ax)
        self.dev_mag_curve = pg.PlotCurveItem(pen=pg.mkPen('1DD219', width=1), name="Magnetic Field Strength")
        self.dev_ax_mag.addItem(self.dev_mag_curve)

        self.profile_axes = np.concatenate([self.x_view_axes, self.y_view_axes])
        self.axes = np.concatenate([self.x_view_axes, self.y_view_axes, [self.rot_ax], [self.pp_ax], [self.dev_ax]])

        self.x_ax0.vb.sigResized.connect(lambda: update_profile_views(self.mag_x_view_axes, self.x_view_axes))
        self.y_ax0.vb.sigResized.connect(lambda: update_profile_views(self.mag_y_view_axes, self.y_view_axes))
        self.dev_ax.vb.sigResized.connect(lambda: update_tab_plot_views([self.dev_ax_mag], [self.dev_ax]))

        # Signals
        self.actionPEM_File.triggered.connect(self.export_pem_file)
        self.actionStats.triggered.connect(self.export_stats)
        self.plot_mag_cbox.triggered.connect(toggle_mag_plots)

        self.button_box.accepted.connect(lambda: self.accept_sig.emit(self.rotated_file))
        self.button_box.rejected.connect(self.close)

        self.acc_btn.clicked.connect(self.rotate)
        self.mag_btn.clicked.connect(self.rotate)
        self.pp_btn.clicked.connect(self.rotate)
        self.none_btn.clicked.connect(self.rotate)
        self.soa_sbox.valueChanged.connect(self.rotate)

        self.reset_range_shortcut = QShortcut(QtGui.QKeySequence(' '), self)
        self.reset_range_shortcut.activated.connect(self.reset_range)

        self.change_component_shortcut = QShortcut(QtGui.QKeySequence('c'), self)
        self.change_component_shortcut.activated.connect(self.change_tab)

    def eventFilter(self, watched, event):
        if event.type() == QtCore.QEvent.Close:  # Close the viewboxes when the window is closed
            self.deleteLater()
        return super().eventFilter(watched, event)

    def export_stats(self):
        """
        Save the stats data frame to a CSV file.
        """
        save_file = QFileDialog().getSaveFileName(self, 'Save CSV File',
                                                  str(self.pem_file.filepath.with_suffix('.CSV')),
                                                  'CSV Files (*.CSV)')[0]
        if save_file:
            df = self.get_stats()
            df.to_csv(save_file,
                      header=True,
                      index=False,
                      float_format='%.2f',
                      na_rep='')
            os.startfile(save_file)

    def export_pem_file(self):
        """
        Export the rotated PEMFile.
        """
        save_file = QFileDialog().getSaveFileName(self, 'Save PEM File',
                                                  str(self.pem_file.filepath),
                                                  'PEM Files (*.PEM)')[0]
        if save_file:
            pem = self.rotated_file.copy()
            pem.filepath = Path(save_file)
            pem.save()
            os.startfile(save_file)

    def get_stats(self):
        """
        Create a data frame with relevant information about de-rotation.
        :return: pandas DataFrame object
        """

        def get_stats(reading):
            """
            Return the relevant information in the reading, mostly in the RAD_Tool object.
            :param reading: PEMFile reading
            :return: list
            """
            rad = reading.RAD_tool
            station = reading.Station
            stats.append([station, rad.azimuth, rad.dip,
                          rad.x_pos, rad.y_pos, rad.z_pos,
                          rad.ppx_theory, rad.ppy_theory, rad.ppz_theory,
                          rad.ppxy_theory, rad.ppxy_measured, rad.ppxy_cleaned,
                          rad.get_azimuth(), rad.get_dip(),
                          rad.acc_roll_angle, rad.mag_roll_angle, rad.measured_pp_roll_angle, rad.cleaned_pp_roll_angle]
                         )

        stats = []
        self.pem_file.data.apply(get_stats, axis=1)
        df = pd.DataFrame(stats,
                          columns=['Station', 'Segment Azimuth', 'Segment Dip',
                                   'X Position', 'Y Position', 'Z Position',
                                   'PPx Theory', 'PPy Theory', 'PPz Theory',
                                   'PPxy Theory', 'PPxy Measured', 'PPxy Cleaned',
                                   'Calculated Azimuth', 'Calculated Dip',
                                   'Accelerometer Roll Angle', 'Magnetometer Roll Angle', 'Measured PP Roll Angle',
                                   'Cleaned PP Roll Angle'])
        df.drop_duplicates(inplace=True, subset='Station')
        return df

    def reset_range(self):
        """
        Reset the range of each plot
        """
        for ax in self.axes:
            ax.enableAutoRange(enable=True)
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

        def fill_table(stations):
            """
            Fill the stations list with the ineligible readings
            :param stations: DataFrame of ineligible readings
            """
            self.list.clear()
            for s in stations.itertuples():
                result = f"{s.Station} {s.Component} - reading # {s.Reading_number} (index {s.Reading_index})"
                self.list.addItem(result)

        def plot_mag():

            # if self.actionPlot_Mag.isChecked():
            mag_df = self.pem_file.get_mag()
            mag_x, mag_y = mag_df.Station.to_numpy(), mag_df.Mag.to_numpy()

            self.dev_mag_curve.setData(x=mag_y, y=mag_x)

            for mag_ax in np.concatenate([self.mag_x_view_axes, self.mag_y_view_axes]):
                # Plot the mag
                mag_curve = pg.PlotCurveItem(x=mag_x, y=mag_y, pen=pg.mkPen('1DD219', width=1))
                mag_ax.addItem(mag_curve)
                self.mag_curves.append(mag_curve)

        while isinstance(pem_file, list):
            pem_file = pem_file[0]

        assert isinstance(pem_file, PEMFile), f"{pem_file} is not a PEMFile object."

        if not pem_file:
            logger.error("No PEM file passed.")
            self.message.critical(self, 'Error', 'PEM file is invalid')
            return
        elif pem_file.data.empty:
            logger.error(f"No data found in {pem_file.filepath.name}.")
            self.message.critical(self, 'Error', f"No EM data in {pem_file.filepath.name}")
            return

        # Ensure the file is a borehole and it has both X and Y component data
        if all([pem_file.is_borehole(), 'X' in pem_file.get_components(), 'Y' in pem_file.get_components()]):
            self.pem_file = pem_file
        else:
            if not pem_file.is_borehole():
                logger.error(f"{pem_file.filepath.name} is not a borehole file.")
            else:
                logger.error(f"No X and/or Y data found in {pem_file.filepath.name}.")

            self.message.critical(self, 'Ineligible File',
                                  'File must be a borehole survey with X and Y component data.')
            return

        # Check that the file hasn't already been de-rotated.
        if self.pem_file.is_derotated():
            response = self.message.question(self, 'File already de-rotated',
                                             f"{pem_file.filepath.name} is already de-rotated. " +
                                             'Do you wish to de-rotate again?',
                                             self.message.Yes | self.message.No)
            if response == self.message.No:
                return

        # Disable PP de-rotation if it's lacking all necessary GPS
        if self.pem_file.has_all_gps():
            self.pp_btn.setEnabled(True)
        else:
            self.pp_btn.setEnabled(False)

        try:
            self.pem_file, ineligible_stations = self.pem_file.prep_rotation()
        except Exception as e:
            # Common exception will be that there is no eligible data
            logger.error(str(e))
            self.message.information(self, 'Error', str(e))
        else:
            self.setWindowTitle(f"XY De-rotation - {pem_file.filepath.name}")

            # Disable the PP values tab if there's no PP information
            if all([self.pem_file.has_all_gps(), self.pem_file.ramp > 0]):
                self.tabWidget.setTabEnabled(0, True)
                self.tabWidget.setTabEnabled(2, True)
            else:
                self.tabWidget.setTabEnabled(0, False)
                self.tabWidget.setTabEnabled(2, False)

            # Fill the table with the ineligible stations
            if not ineligible_stations.empty:
                fill_table(ineligible_stations)
                self.bad_stations_label.show()
                self.list.show()
            else:
                self.bad_stations_label.hide()
                self.list.hide()

            self.rotate()
            plot_mag()

            # Limit the profile plots to only show the station range
            stations = self.pem_file.get_stations(converted=True)
            for ax in np.concatenate([self.x_view_axes, self.y_view_axes]):
                ax.setLimits(xMin=stations.min(), xMax=stations.max())
            for ax in [self.rot_ax, self.pp_ax, self.dev_ax]:
                ax.setLimits(yMin=stations.min() - 1, yMax=stations.max() + 1)

            self.reset_range()
            self.show()

    def plot_pem(self, pem_file):
        """
        Plot the PEM file in a LIN plot style, with both components in separate plots
        :param pem_file: PEMFile object
        """

        def clear_plots():
            for ax in np.concatenate([self.x_view_axes, self.y_view_axes]):
                ax.clear()

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

            profile_data = processed_pem.get_profile_data(component, converted=True, incl_deleted=False)
            if profile_data.empty:
                raise ValueError(f'Profile data for {self.pem_file.filepath.name} is empty.')

            for i, bounds in enumerate(channel_bounds):
                # Select the correct axes based on the component
                if component == 'X':
                    ax = self.x_view_axes[i]
                    mag_ax = self.mag_x_view_axes[i]
                else:
                    ax = self.y_view_axes[i]
                    mag_ax = self.mag_y_view_axes[i]

                # Set the Y-axis labels
                if i == 0:
                    ax.setLabel('left', f"PP channel", units=processed_pem.units)
                else:
                    ax.setLabel('left', f"Channel {bounds[0]} to {bounds[1]}", units=processed_pem.units)

                # Plot the data
                for ch in range(bounds[0], bounds[1] + 1):
                    data = profile_data.iloc[:, ch]
                    plot_lines(data, ax)

        def plot_deviation():
            """
            Plot the difference between PP rotation value and Acc rotation value. Useful for SOA.
            """
            x_filt = raw_pem.data['Component'] == 'X'
            y_filt = raw_pem.data['Component'] == 'Y'
            x_stations = raw_pem.data[x_filt].Station.astype(int)
            y_stations = raw_pem.data[y_filt].Station.astype(int)
            x_acc_angles = raw_pem.data[x_filt].RAD_tool.map(lambda x: x.acc_roll_angle - self.soa)
            y_acc_angles = raw_pem.data[y_filt].RAD_tool.map(lambda x: x.acc_roll_angle - self.soa)

            x_pp_angle_measured = raw_pem.data[x_filt].RAD_tool.map(lambda x: x.measured_pp_roll_angle)
            y_pp_angle_measured = raw_pem.data[y_filt].RAD_tool.map(lambda x: x.measured_pp_roll_angle)
            x_deviation = x_acc_angles - x_pp_angle_measured
            y_deviation = y_acc_angles - y_pp_angle_measured

            # Calculate the average deviation for the curve line
            x_df = pd.DataFrame([x_deviation, x_stations]).T
            x_df.rename(columns={"RAD_tool": "Deviation"}, inplace=True)
            x_avg_df = x_df.groupby("Station", as_index=False).mean()

            y_df = pd.DataFrame([y_deviation, y_stations]).T
            y_df.rename(columns={"RAD_tool": "Deviation"}, inplace=True)
            y_avg_df = y_df.groupby("Station", as_index=False).mean()

            self.x_dev_scatter.setData(x=x_deviation.to_numpy(), y=x_stations.to_numpy())
            self.y_dev_scatter.setData(x=y_deviation.to_numpy(), y=y_stations.to_numpy())
            self.x_dev_curve.setData(x=x_avg_df.Deviation.to_numpy(), y=x_avg_df.Station.to_numpy())
            self.y_dev_curve.setData(x=y_avg_df.Deviation.to_numpy(), y=y_avg_df.Station.to_numpy())

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

        raw_pem = pem_file.copy()  # Needed otherwise the returned PEMFile will be averaged and split
        processed_pem = pem_file.copy()

        # Split the data if it isn't already split
        if not processed_pem.is_split():
            processed_pem = processed_pem.split()

        # Average the data if it isn't averaged
        if not processed_pem.is_averaged():
            processed_pem = processed_pem.average()

        clear_plots()
        channel_bounds = self.pem_file.get_channel_bounds()

        plot_lin('X')
        plot_lin('Y')
        plot_rotation()

        if self.pp_plotted is False and self.pp_btn.isEnabled():
            plot_deviation()
            plot_pp_values()

    def rotate(self):
        """
        Rotate and plot the data, always using the original PEMFile
        """

        method = self.get_method()
        self.soa = self.soa_sbox.value()
        # Create a copy of the pem_file so it is never changed
        copy_file = self.pem_file.copy()

        if method is not None:
            self.rotated_file = copy_file.rotate(method=method, soa=self.soa)
        else:
            self.rotated_file = copy_file

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
    from src.pem.pem_file import PEMParser, DMPParser
    app = QApplication(sys.argv)
    mw = Derotator()

    pg = PEMGetter()
    parser = PEMParser()
    # parser = DMPParser()
    pem_files = parser.parse(r"C:\_Data\2021\TMC\EM17-107\RAW\XYEM17-107_0330.PEM")
    # pem_files = pg.get_pems(client='PEM Rotation', file='_BX-081 XY.PEM')
    # pem_files, errors = parser.parse(r'C:\_Data\2021\Eastern\Corazan Mining\FLC-2020-23 (LP-26A)\RAW\XYZ_0329.DMP')
    mw.open(pem_files)

    # mw.export_stats()

    app.exec_()


if __name__ == '__main__':

    main()
