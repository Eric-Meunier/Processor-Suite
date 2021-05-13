import os
import logging
import sys
import numpy as np
import pandas as pd
from pathlib import Path
# from src.logger import Log
from PySide2 import QtCore, QtGui, QtUiTools
from PySide2.QtWidgets import (QMainWindow, QApplication, QMessageBox, QShortcut, QFileDialog)
import pyqtgraph as pg
from src.pem.pem_file import PEMFile
from src.qt_py.custom_qt_widgets import NonScientific

logger = logging.getLogger(__name__)

if getattr(sys, 'frozen', False):
    application_path = Path(sys.executable).parent
else:
    application_path = Path(__file__).absolute().parents[1]
icons_path = application_path.joinpath("ui\\icons")

# Load Qt ui file into a class
Ui_Derotator, QtBaseClass = QtUiTools.loadUiType(str(application_path.joinpath('ui\\derotator.ui')))

pg.setConfigOptions(antialias=True)
pg.setConfigOption('background', 'w')
pg.setConfigOption('foreground', 'k')
pg.setConfigOption('crashWarning', True)

symbol_size = 9


class Derotator(QMainWindow, Ui_Derotator):
    """
    Class that de-rotates XY data of a PEMFile
    """
    accept_sig = QtCore.Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.installEventFilter(self)
        self.parent = parent
        self.pem_file = None
        self.rotated_file = None
        self.pp_plotted = False
        self.rotation_note = None
        self.soa = self.soa_sbox.value()

        self.setWindowTitle('XY De-rotation')
        self.setWindowIcon(QtGui.QIcon(os.path.join(icons_path, 'derotate.png')))

        self.message = QMessageBox()

        self.bad_stations_label.hide()
        self.list.setText('')
        self.statusBar().hide()

        # Configure the plots
        self.x_view.ci.layout.setSpacing(5)  # Spacing between plots
        self.x_ax0 = self.x_view.addPlot(0, 0)
        self.x_ax1 = self.x_view.addPlot(0, 1)
        self.x_ax2 = self.x_view.addPlot(0, 2)
        self.x_ax3 = self.x_view.addPlot(0, 3)
        self.x_ax4 = self.x_view.addPlot(0, 4)

        self.x_view_axes = [self.x_ax0, self.x_ax1, self.x_ax2, self.x_ax3, self.x_ax4]

        # Configure the lin plot
        self.y_view.ci.layout.setSpacing(5)  # Spacing between plots
        self.y_ax0 = self.y_view.addPlot(0, 0)
        self.y_ax1 = self.y_view.addPlot(0, 1)
        self.y_ax2 = self.y_view.addPlot(0, 2)
        self.y_ax3 = self.y_view.addPlot(0, 3)
        self.y_ax4 = self.y_view.addPlot(0, 4)

        self.y_view_axes = [self.y_ax0, self.y_ax1, self.y_ax2, self.y_ax3, self.y_ax4]

        # Create the deviation plot
        self.dev_ax = self.deviation_view.addPlot(0, 0, axisItems={'top': NonScientific(orientation="top")})
        self.dev_ax_legend = self.dev_ax.addLegend(pen='k', brush='w', labelTextSize="8pt", verSpacing=-1)
        self.dev_ax_legend.setParent(self.deviation_view)
        self.dev_ax.setLabel('top', 'PP Rotation Angle - Accelerometer Rotation Angle (Degrees)')
        self.dev_ax.setLabel('left', 'Station', units=None)
        v_line = pg.InfiniteLine(pos=0, angle=90, pen=pg.mkPen("k", width=0.5))
        self.dev_ax.addItem(v_line)

        self.x_dev_curve = pg.PlotCurveItem(pen=pg.mkPen((255, 0, 0, 100), width=2), name="X Component")
        self.y_dev_curve = pg.PlotCurveItem(pen=pg.mkPen((0, 0, 255, 100), width=2), name="Y Component")
        self.x_dev_scatter = pg.ScatterPlotItem(pen=pg.mkPen((255, 0, 0, 100), width=2, symbolSize=symbol_size),
                                                brush=pg.mkBrush("w"))
        self.y_dev_scatter = pg.ScatterPlotItem(pen=pg.mkPen((0, 0, 255, 100), width=2, symbolSize=symbol_size),
                                                brush=pg.mkBrush("w"))
        self.dev_ax.addItem(self.x_dev_curve)
        self.dev_ax.addItem(self.y_dev_curve)
        self.dev_ax.addItem(self.x_dev_scatter)
        self.dev_ax.addItem(self.y_dev_scatter)

        # Create the dip plot
        self.dip_ax = self.tool_view.addPlot(0, 0, axisItems={'top': NonScientific(orientation="top")})
        # self.dip_ax_legend = self.dip_ax.addLegend(pen='k', brush='w', labelTextSize="8pt", verSpacing=-1)
        # self.dip_ax_legend.setParent(self.tool_view)
        self.dip_curve = pg.PlotCurveItem(pen=pg.mkPen((0, 0, 255, 100), width=2), name="Dip")
        self.dip_ax.addItem(self.dip_curve)
        self.dip_ax.setLabel('top', 'Dip Angle (Degrees)')
        self.dip_ax.setLabel('left', 'Station', units=None)
        v_line = pg.InfiniteLine(pos=0, angle=90, pen=pg.mkPen("k", width=0.5))
        self.dip_ax.addItem(v_line)
        self.dip_ax.setLimits(xMin=-90, xMax=0)
        self.dip_ax.setXRange(-90, 0)

        # Mag plot
        self.mag_ax = self.tool_view.addPlot(0, 1, axisItems={'top': NonScientific(orientation="top")})
        self.mag_curve = pg.PlotCurveItem(pen=pg.mkPen((0, 255, 0, 100), width=2), name="Magnetic Field Strength")
        self.mag_ax.setLabel("top", "Total Magnetic Field (pT)")
        self.mag_ax.setLabel('left', 'Station', units=None)
        self.mag_ax.addItem(self.mag_curve)
        self.mag_ax.getAxis("left").setWidth(30)
        self.mag_ax.getAxis("right").setWidth(10)

        # Create the rotation angle plot
        self.rot_ax = self.rotation_view.addPlot(0, 0, axisItems={'top': NonScientific(orientation="top")})
        self.rot_ax_legend = self.rot_ax.addLegend(pen='k', brush='w', labelTextSize="8pt", verSpacing=-1)
        self.rot_ax_legend.setParent(self.rotation_view)
        self.rot_ax.setLimits(xMin=0, xMax=360)
        self.rot_ax.setXRange(0, 360)
        self.rot_ax.setLabel('top', 'Rotation Angle', units='Degrees')
        self.rot_ax.setLabel('left', 'Station', units=None)

        # Create the pp values plot
        self.pp_ax = self.pp_view.addPlot(0, 0, axisItems={'top': NonScientific(orientation="top")})
        self.pp_ax_legend = self.pp_ax.addLegend(pen='k', brush='w', labelTextSize="8pt", verSpacing=-1)
        self.pp_ax_legend.setParent(self.pp_view)
        self.pp_ax.setLabel('top', 'Magnetic Field Strength', units='nT/s')
        self.pp_ax.setLabel('left', 'Station', units=None)

        for ax in np.concatenate([self.x_view_axes, self.y_view_axes]):
            ax.hideButtons()
            ax.setMenuEnabled(False)
            ax.invertY(True)
            ax.setYLink(self.x_ax0)

            # Add the mag plot into the profile plot
            ax.showAxis("top")
            ax.showAxis("right")
            ax.getAxis("top").setStyle(showValues=True)
            ax.getAxis("right").setStyle(showValues=False)
            ax.getAxis("left").setStyle(showValues=False)
            ax.getAxis('top').enableAutoSIPrefix(enable=False)
            # ax.hideAxis("left")
            ax.hideAxis("bottom")

        # Use the first axes to set the label and tick labels
        for ax in [self.x_ax0, self.y_ax0]:
            ax.getAxis("left").setStyle(showValues=True)
            ax.getAxis("left").setLabel("Station", color='1DD219')
        #
        # for ax in [self.x_ax4, self.y_ax4]:
        #     ax.showAxis("right")
        #     ax.getAxis("right").setStyle(showValues=False)

        # Disable the 'A' button and auto-scaling SI units
        for ax in [self.dev_ax, self.dip_ax, self.mag_ax, self.rot_ax, self.pp_ax]:
            # ax.showGrid(x=False, y=True, alpha=0.3)
            ax.hideButtons()
            ax.setMenuEnabled(False)
            ax.invertY(True)
            ax.setYLink(self.x_ax0)

            # Add the mag plot into the profile plot
            ax.showAxis("top")
            ax.showAxis("right")
            ax.getAxis("top").setStyle(showValues=True)
            ax.getAxis("right").setStyle(showValues=False)
            ax.getAxis("left").setStyle(showValues=True)
            ax.getAxis("left").setLabel("Station", color='1DD219')
            ax.getAxis('top').enableAutoSIPrefix(enable=False)
            ax.hideAxis("bottom")

        self.mag_ax.getAxis("left").setStyle(showValues=False)
        self.mag_ax.getAxis("left").setLabel("")

        self.profile_axes = np.concatenate([self.x_view_axes, self.y_view_axes])
        self.axes = np.concatenate([self.x_view_axes, self.y_view_axes, [self.dev_ax], [self.dip_ax], [self.mag_ax],
                                    [self.rot_ax], [self.pp_ax]])

        # Signals
        self.actionPEM_File.triggered.connect(self.export_pem_file)
        self.actionStats.triggered.connect(self.export_stats)

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
            list = []
            for s in stations.itertuples():
                result = f"{s.Station} {s.Component} - reading # {s.Reading_number} (index {s.Reading_index})"
                list.append(result)
            self.list.setText("\n".join(list))

        def plot_mag():
            mag_df = self.pem_file.get_mag()
            mag_df = mag_df.drop_duplicates(subset='Station')
            stations = mag_df.Station.astype(int).to_numpy()
            if mag_df.Mag.any():
                self.mag_curve.setData(x=mag_df.Mag.to_numpy(), y=stations)
            else:
                logger.warning(f"No mag data found in {self.pem_file.filepath.name}")

        def plot_dip():
            """
            Plot the dip of the hole.
            """
            dip_df = self.pem_file.get_dip()
            dip_df = dip_df.drop_duplicates(subset='Station')
            stations = dip_df.Station.astype(int).to_numpy()
            if not dip_df.empty:
                self.dip_curve.setData(x=dip_df.Dip.to_numpy(), y=stations)
            else:
                logger.warning(f"No dip data found in {self.pem_file.filepath.name}")

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
            else:
                self.bad_stations_label.hide()

            # Limit the profile plots to only show the station range
            stations = self.pem_file.get_stations(converted=True)
            for ax in np.concatenate([self.x_view_axes, self.y_view_axes]):
                ax.setLimits(yMin=stations.min(), yMax=stations.max())
            for ax in [self.dev_ax, self.dip_ax, self.mag_ax, self.rot_ax, self.pp_ax]:
                ax.setLimits(yMin=stations.min() - 1, yMax=stations.max() + 1)

            self.rotate()
            if self.pem_file.has_d7():
                plot_mag()
                plot_dip()
            else:
                self.tabWidget.setTabEnabled(1, False)

            self.show()
            self.reset_range()

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
                x, y = df.to_numpy(), df.index.to_numpy()

                ax.plot(x=x, y=y,
                        pen=pg.mkPen('k', width=1.1),
                        )

            profile_data = processed_pem.get_profile_data(component, converted=True, incl_deleted=False)
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
                    ax.setLabel('top', f"PP channel", units=processed_pem.units)
                else:
                    ax.setLabel('top', f"Ch {bounds[0]} to {bounds[1]}", units=processed_pem.units)

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
            x_acc_angles = raw_pem.data[x_filt].RAD_tool.map(lambda x: x.acc_roll_angle + self.soa)
            y_acc_angles = raw_pem.data[y_filt].RAD_tool.map(lambda x: x.acc_roll_angle + self.soa)

            x_pp_angle_measured = raw_pem.data[x_filt].RAD_tool.map(lambda x: x.measured_pp_roll_angle)
            y_pp_angle_measured = raw_pem.data[y_filt].RAD_tool.map(lambda x: x.measured_pp_roll_angle)
            x_deviation = x_pp_angle_measured - x_acc_angles
            y_deviation = y_pp_angle_measured - y_acc_angles

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
                stations = raw_pem.data[x_filt].Station.astype(int).to_numpy()

                if self.pp_btn.isEnabled():
                    # Add the cleaned PP information for non-fluxgate surveys
                    if not pem_file.is_fluxgate():
                        x_pp_angle_cleaned = raw_pem.data[x_filt].RAD_tool.map(lambda x: x.cleaned_pp_roll_angle)
                        cpp_item = pg.PlotDataItem()
                        cpp_item.setData(x_pp_angle_cleaned.to_numpy(), stations,
                                         pen=pg.mkPen((255, 0, 0, 200), width=2.),
                                         symbolPen=pg.mkPen((255, 0, 0, 200), width=2.),
                                         # symbolPen='r',
                                         symbolBrush=pg.mkBrush('w'),
                                         symbol='t',
                                         symbolSize=symbol_size)
                        ax.addItem(cpp_item)
                        self.rot_ax_legend.addItem(cpp_item, 'Cleaned PP')

                    x_pp_angle_measured = raw_pem.data[x_filt].RAD_tool.map(lambda x: x.measured_pp_roll_angle)

                    # Create and plot the scatter plot items
                    mpp_item = pg.PlotDataItem()
                    mpp_item.setData(x_pp_angle_measured.to_numpy(), stations,
                                     pen=pg.mkPen((0, 0, 255, 200), width=2.),
                                     symbolPen=pg.mkPen((0, 0, 255, 200), width=2.),
                                     # symbolPen='b',
                                     symbolBrush=pg.mkBrush('w'),
                                     symbol='t1',
                                     symbolSize=symbol_size)

                    # Add the scatter plot items to the scatter plot
                    ax.addItem(mpp_item)
                    # Add the items to the legend
                    self.rot_ax_legend.addItem(mpp_item, 'Measured PP')

                acc_angles = raw_pem.data[x_filt].RAD_tool.map(lambda x: x.acc_roll_angle - self.soa)
                mag_angles = raw_pem.data[x_filt].RAD_tool.map(lambda x: x.mag_roll_angle - self.soa)

                acc_item = pg.PlotDataItem()
                mag_item = pg.PlotDataItem()
                acc_item.setData(acc_angles.to_numpy(), stations,
                                 pen=pg.mkPen((0, 255, 0, 200), width=2.),
                                 symbolPen=pg.mkPen((0, 255, 0, 200), width=2.),
                                 # symbolPen='g',
                                 symbolBrush=pg.mkBrush('w'),
                                 symbol='o',
                                 symbolSize=symbol_size)
                mag_item.setData(mag_angles.to_numpy(), stations,
                                 pen=pg.mkPen((100, 100, 100, 200), width=2.),
                                 symbolPen=pg.mkPen((100, 100, 100, 200), width=2.),
                                 # symbolPen='m',
                                 symbolBrush=pg.mkBrush('w'),
                                 symbol='s',
                                 symbolSize=symbol_size)
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
            stations = raw_pem.data[x_filt].Station.astype(int).to_numpy()

            if not pem_file.is_fluxgate():
                ppxy_cleaned = raw_pem.data[x_filt].RAD_tool.map(lambda x: x.ppxy_cleaned)
                cleaned_item = pg.PlotDataItem(ppxy_cleaned.to_numpy(), stations,
                                               pen=pg.mkPen((255, 0, 0, 200), width=2),
                                               brush=None,
                                               symbol='t',
                                               symbolPen=pg.mkPen((255, 0, 0, 200), width=2),
                                               symbolBrush='w',
                                               symbolSize=symbol_size)
                ax.addItem(cleaned_item)
                self.pp_ax_legend.addItem(cleaned_item, 'Cleaned PP')

            ppxy_theory = raw_pem.data[x_filt].RAD_tool.map(lambda x: x.ppxy_theory)
            ppxy_measured = raw_pem.data[x_filt].RAD_tool.map(lambda x: x.ppxy_measured)

            theory_item = pg.PlotDataItem(ppxy_theory.to_numpy(), stations,
                                          pen=pg.mkPen((0, 255, 0, 200), width=2),
                                          brush=None,
                                          symbol='o',
                                          symbolPen=pg.mkPen((0, 255, 0, 200), width=2),
                                          symbolBrush='w',
                                          symbolSize=symbol_size)

            measured_item = pg.PlotDataItem(ppxy_measured.to_numpy(), stations,
                                            pen=pg.mkPen((0, 0, 255, 200), width=2),
                                            brush=None,
                                            symbol='t1',
                                            symbolPen=pg.mkPen((0, 0, 255, 200), width=2),
                                            symbolBrush='w',
                                            symbolSize=symbol_size)

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

        if pem_file.has_all_gps() and pem_file.ramp > 0:
            plot_deviation()

        if self.pp_plotted is False and self.pp_btn.isEnabled():
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
        self.reset_range()

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
    pem_files = pg.get_pems(folder="PEM Rotation", file="_SAN-225G-18 XYZ.PEM")
    # pem_files = pg.get_pems(folder="PEM Rotation", random=True, number=5)
    # for pem_file in pem_files:
    #     d = Derotator()
    #     d.open(pem_file)
    mw.open(pem_files)

    # mw.export_stats()

    app.exec_()


if __name__ == '__main__':

    main()
