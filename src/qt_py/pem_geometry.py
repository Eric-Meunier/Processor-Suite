import logging
import math
import os
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import mplcursors
import numpy as np
from PySide2.QtCore import Qt, Signal
from PySide2.QtGui import QIcon, QKeySequence
from PySide2.QtWidgets import (QMainWindow, QMessageBox, QWidget, QErrorMessage,
                               QFileDialog, QVBoxLayout, QApplication, QShortcut)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from pandas import DataFrame, Series, read_csv, concat

from src.gps.gps_editor import BoreholeSegments
from src.mpl.interactive_spline import InteractiveSpline
from src.mpl.zoom_pan import ZoomPan
from src.qt_py import icons_path
from src.qt_py.gps_adder import DADSelector
from src.ui.pem_geometry import Ui_PEMGeometry

logger = logging.getLogger(__name__)


def dad_to_seg(df, units='m'):
    """
    Create a segment data frame from a DAD data frame. DAD data is split into 1m intervals.
    :param df: pandas DataFrame with Depth, Azimuth, Dip columns
    :param units: str, units of the segments, either 'm' or 'ft'
    :return: pandas DataFrame with Azimuth, Dip, segment length, unit, and depth columns
    """
    if units == 'm' or units is None:
        units = 2
    elif units == 'ft':
        units = 0
    else:
        raise NotImplementedError(f"{units} is not implemented as a unit for segments.")

    # Interpolate the DAD to 1m segments
    depth = df.Depth.to_numpy()
    azimuth = df.Azimuth.to_numpy()
    dip = df.Dip.to_numpy()

    i_depth = np.arange(depth[0], depth[-1] + 1)
    i_azimuth = np.interp(i_depth, depth, azimuth)
    i_dip = np.interp(i_depth, depth, dip)
    df = DataFrame(zip(i_depth, i_azimuth, i_dip), columns=df.columns)

    # Create the segment data frame
    seg = df.head(0).copy()
    depth_count, az_count, dip_count = 0, 0, 0

    # Calculate the iterative differences in depth, azimuth, and dip going down the hole
    depth_diff = df.Depth.diff().dropna()
    az_diff = df.Azimuth.diff().dropna()
    dip_diff = df.Dip.diff().dropna()

    # Start a counter for each attribute. When the threshold for any attribute is met, append current df row
    for i, (depth, az, dip) in enumerate(list(zip(depth_diff, az_diff, dip_diff))):
        depth_count += abs(depth)
        az_count += abs(az)
        dip_count += abs(dip)
        if any([depth_count >= 10, az_count >= 1., dip_count >= 1.]):
            seg = seg.append(df.iloc[i + 1])
            # Reset the counters
            depth_count, az_count, dip_count = 0, 0, 0

    # Add the last segment if it isn't there from the iterative calculations
    if seg.tail(1).Depth.iloc[0] != df.tail(1).Depth.iloc[0]:
        seg = seg.append(df.iloc[-1])

    seg_length = seg.Depth.diff()
    seg_length.iloc[0] = seg.Depth.iloc[0]
    seg['Segment_length'] = seg_length
    seg['Unit'] = units

    # Re-arrange the columns
    depths = seg.pop('Depth')
    seg.insert(4, 'Depth', depths)
    seg.reset_index(inplace=True, drop=True)
    seg = seg.round(2)

    return BoreholeSegments(seg)


class PEMGeometry(QMainWindow, Ui_PEMGeometry):
    # plt.style.use('seaborn-white')
    accepted_sig = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)

        self.setWindowTitle('PEM Geometry')
        self.setWindowIcon(QIcon(os.path.join(icons_path, 'pem_geometry.png')))
        self.resize(1100, 800)
        # self.status_bar.setStyleSheet("border-top :0.5px solid gray;")

        self.message = QMessageBox()
        self.error = QErrorMessage()
        self.error.setWindowTitle('Error')

        self.parent = parent
        self.pem_file = None
        self.dialog = QFileDialog()

        # Initialize the plot lines
        self.tool_az_line = None
        self.tool_mag_line = None
        self.tool_dip_line = None
        self.az_spline = None
        self.existing_az_line = None
        self.existing_dip_line = None
        self.imported_az_line = None
        self.imported_dip_line = None
        self.collar_az_line = None
        self.collar_dip_line = None
        self.dip_spline = None

        # Polar lines
        self.tool_az_line_p = None
        self.tool_dip_line_p = None
        self.existing_az_line_p = None
        self.existing_dip_line_p = None
        self.imported_az_line_p = None
        self.imported_dip_line_p = None
        self.collar_az_line_p = None
        self.collar_dip_line_p = None

        self.background = None
        self.df = None

        self.az_output_combo.addItem('')
        self.dip_output_combo.addItem('')

        self.az_lines = []
        self.dip_lines = []
        self.roll_lines = []
        self.polar_lines = []

        # Create the main plots
        self.figure, (self.mag_ax, self.dip_ax, self.roll_ax) = plt.subplots(1, 3, sharey=True)
        self.figure.subplots_adjust(left=0.07, bottom=0.08, right=0.94, top=0.92)
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setFocusPolicy(Qt.StrongFocus)
        self.plots_layout.addWidget(self.canvas)

        # Create the polar plot
        self.polar_widget = QWidget()
        self.polar_widget.setLayout(QVBoxLayout())
        self.polar_widget.layout().setContentsMargins(0, 0, 0, 0)
        self.polar_figure = plt.figure()
        self.polar_figure.subplots_adjust(left=0.03, bottom=0.08, right=0.82, top=0.92)
        self.polar_ax = self.polar_figure.add_subplot(projection="polar")
        self.polar_ax.set_theta_zero_location("N")
        self.polar_ax.set_theta_direction(-1)
        self.polar_ax.set_rlabel_position(0)
        self.polar_ax.grid(linestyle='dashed', linewidth=0.5)
        self.polar_ax.grid(True, linestyle='-', linewidth=1, which='minor')
        self.polar_ax.set_xticks(np.pi / 180. * np.linspace(0, 360, 24, endpoint=False))

        self.polar_canvas = FigureCanvas(self.polar_figure)
        self.polar_canvas.setFocusPolicy(Qt.StrongFocus)
        self.polar_widget.layout().addWidget(self.polar_canvas)
        self.polar_plot_layout.addWidget(self.polar_canvas)

        # Format the axes
        self.mag_ax.invert_yaxis()
        self.az_ax = self.mag_ax.twiny()
        self.axes = [self.az_ax, self.mag_ax, self.dip_ax, self.roll_ax]

        self.az_ax.set_xlabel('Azimuth (°)', color='r')
        self.dip_ax.set_xlabel('Dip (°)', color='b')
        self.mag_ax.set_xlabel('Magnetic Field Strength (nT)', color='g')
        self.roll_ax.set_xlabel('Roll Angle (°)', color='k')

        tkw = dict(size=4, width=1.5)
        self.az_ax.tick_params(axis='x', colors='r', **tkw)
        self.dip_ax.tick_params(axis='x', colors='b', **tkw)
        self.dip_ax.tick_params(axis='y', which='major', right=True, direction='out')
        self.mag_ax.tick_params(axis='x', colors='g', **tkw)
        self.roll_ax.yaxis.set_label_position('right')
        self.roll_ax.yaxis.set_ticks_position('right')

        self.zp = ZoomPan()
        self.az_zoom = self.zp.zoom_factory(self.az_ax)
        self.az_pan = self.zp.pan_factory(self.az_ax)
        self.dip_zoom = self.zp.zoom_factory(self.dip_ax)
        self.dip_pan = self.zp.pan_factory(self.dip_ax)
        self.mag_zoom = self.zp.zoom_factory(self.mag_ax)
        self.mag_pan = self.zp.pan_factory(self.mag_ax)
        self.roll_zoom = self.zp.zoom_factory(self.roll_ax)
        self.roll_pan = self.zp.pan_factory(self.roll_ax)

        # Signals
        self.actionOpen_Geometry_File.triggered.connect(self.open_file_dialog)
        self.actionOpen_Geometry_File.setIcon(QIcon(str(icons_path.joinpath("open.png"))))
        self.actionAllow_Negative_Azimuth.triggered.connect(lambda: self.plot_tool_values(update=True))

        self.actionSave_Screenshot.setShortcut("Ctrl+S")
        self.actionSave_Screenshot.triggered.connect(self.save_img)
        self.actionSave_Screenshot.setIcon(QIcon(str(icons_path.joinpath("save_as.png"))))
        self.actionCopy_Screenshot.setShortcut("Ctrl+C")
        self.actionCopy_Screenshot.triggered.connect(self.copy_img)
        self.actionCopy_Screenshot.setIcon(QIcon(str(icons_path.joinpath("copy.png"))))

        self.reset_range_shortcut = QShortcut(QKeySequence(' '), self)
        self.reset_range_shortcut.activated.connect(self.update_plots)

        self.mag_dec_sbox.valueChanged.connect(self.redraw_az_line)
        self.collar_az_sbox.valueChanged.connect(self.redraw_collar_az_line)
        self.collar_dip_sbox.valueChanged.connect(self.redraw_collar_dip_line)

        self.az_spline_cbox.toggled.connect(self.toggle_az_spline)
        self.dip_spline_cbox.toggled.connect(self.toggle_dip_spline)
        self.show_tool_geom_cbox.toggled.connect(self.toggle_tool_geom)
        self.show_existing_geom_cbox.toggled.connect(self.toggle_existing_geom)
        self.show_imported_geom_cbox.toggled.connect(self.toggle_imported_geom)
        self.collar_az_cbox.toggled.connect(self.toggle_collar_az)
        self.collar_dip_cbox.toggled.connect(self.toggle_collar_dip)
        self.show_mag_cbox.toggled.connect(self.toggle_mag)

        self.az_output_combo.currentTextChanged.connect(self.az_combo_changed)
        self.az_output_combo.currentTextChanged.connect(self.toggle_accept)
        self.dip_output_combo.currentTextChanged.connect(self.dip_combo_changed)
        self.dip_output_combo.currentTextChanged.connect(self.toggle_accept)
        self.accept_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.close)

    def dragEnterEvent(self, e):
        urls = [url.toLocalFile() for url in e.mimeData().urls()]

        if len(urls) > 1:
            e.ignore()
        else:
            file = urls[0]
            if any([file.endswith('seg'), file.endswith('txt'), file.endswith('dad'), file.endswith('csv'),
                    file.endswith('xlsx'), file.endswith('xls')]):
                e.accept()
            else:
                e.ignore()

    def dropEvent(self, e):
        file = [url.toLocalFile() for url in e.mimeData().urls()][0]

        if file.endswith('seg'):
            self.open_seg_file(file)
        else:
            self.open_dad_file(file)

    def save_img(self):
        """Save an image of the window """
        save_name, save_type = QFileDialog.getSaveFileName(self, 'Save Image', 'map.png', 'PNG file (*.PNG)')
        if save_name:
            self.grab().save(save_name)
            self.status_bar.showMessage(f"Image saved.", 1500)

    def copy_img(self):
        """Take an image of the window and copy it to the clipboard"""
        QApplication.clipboard().setPixmap(self.grab())
        self.status_bar.showMessage(f"Image saved to clipboard.", 1500)

    def open_file_dialog(self):
        """
        Open files through the file dialog
        """
        default_path = self.pem_file.filepath.parent
        files, ext = self.dialog.getOpenFileNames(self, 'Open File', str(default_path),
                                                  filter='DAD files (*.dad; *.csv; *.xlsx; *.xls; *.txt);; '
                                                         'SEG files (*.seg; *.txt)')
        if files != '':
            for file in files:
                if 'dad' in ext.lower():
                    self.open_dad_file(file)
                else:
                    self.open_seg_file(file)
        else:
            pass

    def open(self, pem_files):
        if not isinstance(pem_files, list):
            pem_files = [pem_files]

        # Try to use a file which has the geometry required to calculate the magnetic declination. Otherwise use the
        # last file.
        for file in pem_files:
            if file == pem_files[-1] or file.get_mag_dec():
                self.pem_file = file.copy()
                break

        if not all([f.is_borehole for f in pem_files]):
            logger.error(f"PEM files must be borehole surveys.")
            return

        # Merge the data of the pem files
        if len(pem_files) > 1:
            self.pem_file.data = concat([pem_file.data for pem_file in pem_files], axis=0, ignore_index=True)

            # # Use the first geometry where the segments aren't empty (if any)
            # for file in pem_files:
            #     if not file.segments.df.empty:
            #         pem_file.geometry = file.get_geometry()

        if not all([f.has_d7() for f in pem_files]) and not self.pem_file.has_geometry():
            logger.error(f"PEM files must have D7 RAD tool objects or P tag geometry.")
            return

        if not self.pem_file.is_averaged():
            self.pem_file = self.pem_file.average()

        self.status_bar.showMessage(f"Opened file(s): {', '.join([f.filepath.name for f in pem_files])}")
        self.plot_pem()
        self.show()

    def accept(self):
        """
        Signal slot, when the accept button is pressed. Create a segment object from the coordinates of the lines
        selected for output.
        :return: BoreholeSegments object
        """
        az_line = self.get_output_az_line()
        if az_line == self.az_spline:
            az_line = self.az_spline.spline

        dip_line = self.get_output_dip_line()
        if dip_line == self.dip_spline:
            dip_line = self.dip_spline.spline

        # Get the line coordinates
        az, az_depth = az_line.get_xdata(), az_line.get_ydata()
        dip, dip_depth = np.array(dip_line.get_xdata()) * -1, dip_line.get_ydata()

        # Interpolate the data to 1m segment lengths and starting from depth 0
        xi = np.arange(0, max(az_depth.max(), dip_depth.max() + 1), 1)
        i_az = np.interp(xi, az_depth, az)
        i_dip = np.interp(xi, dip_depth, dip)
        dad_df = DataFrame({'Depth': xi, 'Azimuth': i_az, 'Dip': i_dip})

        seg = dad_to_seg(dad_df, units=self.pem_file.get_gps_units())
        self.accepted_sig.emit(seg)
        plt.close(self.figure)
        plt.close(self.polar_figure)
        self.close()

    def plot_pem(self):
        """
        Plot the pem file tool values and segment information. One of the two must be present.
        """

        def add_az_spline(az, depth):
            """
            Add the azimuth spline line
            """
            spline_stations = np.linspace(0, depth.iloc[-1], 6)
            spline_az = np.interp(spline_stations, depth, az + self.mag_dec_sbox.value())
            self.az_spline = InteractiveSpline(self.az_ax, zip(spline_stations, spline_az),
                                               line_color='darkred',
                                               method="cubic")

            self.toggle_az_spline()
            self.az_output_combo.addItem('Spline')
            self.az_spline_cbox.setEnabled(True)

        def add_dip_spline(dip, depth):
            """
            Add the dip spline line
            """
            spline_stations = np.linspace(0, depth.iloc[-1], 6)
            spline_dip = np.interp(spline_stations, depth, dip)

            self.dip_spline = InteractiveSpline(self.dip_ax, zip(spline_stations, spline_dip),
                                                line_color='darkblue',
                                                method="cubic")

            self.toggle_dip_spline()
            self.dip_output_combo.addItem('Spline')
            self.dip_spline_cbox.setEnabled(True)

        def add_collar_az(az, depth):
            """
            Add the fixed azimuth line
            :param az: list, azimuths from either the tool values or seg file to use as a starting point
            :param depth: list, corresponding depths of the az
            """
            if self.collar_az_line is None:
                global collar_az, collar_depths
                avg_az = int(np.average(az))
                self.collar_az_sbox.blockSignals(True)
                self.collar_az_sbox.setValue(avg_az)
                self.collar_az_sbox.blockSignals(False)

                collar_depths = np.array([0, depth.iloc[-1]])
                collar_az = np.array([avg_az] * 2)

                # Plot the lines
                self.collar_az_line, = self.az_ax.plot(collar_az, collar_depths,
                                                       color='crimson',
                                                       linestyle=(0, (5, 10)),
                                                       label='Fixed Azimuth',
                                                       lw=0.8,
                                                       zorder=1)

                # Plot the line in the polar plot
                self.collar_az_line_p, = self.polar_ax.plot([math.radians(az) for az in collar_az], collar_depths,
                                                            color='crimson',
                                                            linestyle=(0, (5, 10)),
                                                            label='Fixed Azimuth',
                                                            lw=0.8,
                                                            zorder=1)

                # Add the lines to the legend
                self.az_lines.append(self.collar_az_line)
                self.polar_lines.append(self.collar_az_line_p)
                self.az_output_combo.addItem('Fixed')

                # Ensure the visibility of the lines are correct
                self.toggle_collar_az()

        def add_collar_dip(dip, depth):
            """
            Add the fixed dip line
            :param dip: list, dips from either the tool values or seg file to use as a starting point
            :param depth: list, corresponding depths of the dip
            """
            if self.collar_dip_line is None:
                global collar_dip, collar_depths
                avg_dip = int(np.average(dip))
                self.collar_dip_sbox.blockSignals(True)
                self.collar_dip_sbox.setValue(avg_dip)
                self.collar_dip_sbox.blockSignals(False)

                collar_depths = np.array([0, depth.iloc[-1]])
                collar_dip = np.array([avg_dip] * 2)

                # Plot the lines
                self.collar_dip_line, = self.dip_ax.plot(collar_dip, collar_depths,
                                                         color='blue',
                                                         linestyle=(0, (5, 10)),
                                                         label='Fixed Dip',
                                                         lw=0.8,
                                                         zorder=1)

                # Plot in the polar plot
                self.collar_dip_line_p, = self.polar_ax.plot([-math.radians(dip) for dip in collar_dip], collar_depths,
                                                             color='blue',
                                                             linestyle=(0, (5, 10)),
                                                             label='Fixed Dip',
                                                             lw=0.8,
                                                             zorder=1)

                # Add the lines to the legend
                self.dip_lines.append(self.collar_dip_line)
                self.polar_lines.append(self.collar_dip_line_p)
                self.dip_output_combo.addItem('Fixed')

                # Ensure the visibility of the lines are correct
                self.toggle_collar_dip()

        def plot_seg_values():
            """
            Plot the azimuth and dip from the P tags section of the pem_file
            """
            global seg_az, seg_dip, seg_depth
            seg = self.pem_file.get_segments()
            seg_depth = seg.Depth
            seg_az = seg.Azimuth
            seg_dip = seg.Dip * -1

            if self.existing_az_line is None:
                # Enable the show existing geometry check box
                self.show_existing_geom_cbox.setEnabled(True)
                # Plot the lines
                self.existing_az_line, = self.az_ax.plot(seg_az, seg_depth,
                                                         color='crimson',
                                                         linestyle='-.',
                                                         label='Existing Azimuth',
                                                         lw=0.8,
                                                         zorder=1)

                self.existing_dip_line, = self.dip_ax.plot(seg_dip, seg_depth,
                                                           color='dodgerblue',
                                                           linestyle='-.',
                                                           label='Existing Dip',
                                                           lw=0.8,
                                                           zorder=1)

                # Plot the lines in the polar plot
                self.existing_az_line_p, = self.polar_ax.plot([math.radians(az) for az in seg_az], seg_depth,
                                                              color='crimson',
                                                              linestyle='-.',
                                                              label='Existing Azimuth',
                                                              lw=0.8,
                                                              zorder=1)

                self.existing_dip_line_p, = self.polar_ax.plot([-math.radians(dip) for dip in seg_dip], seg_depth,
                                                               color='dodgerblue',
                                                               linestyle='-.',
                                                               label='Existing Dip',
                                                               lw=0.8,
                                                               zorder=1)

                # Add the lines to the legend
                self.az_lines.append(self.existing_az_line)
                self.dip_lines.append(self.existing_dip_line)
                self.polar_lines.append(self.existing_az_line_p)
                self.polar_lines.append(self.existing_dip_line_p)

                self.az_output_combo.addItem('Existing')
                self.dip_output_combo.addItem('Existing')

                # Ensure the visibility of the lines are correct
                self.toggle_existing_geom()

                self.show_existing_geom_cbox.setEnabled(True)

        def set_cursor():
            """
            Create the mplcursor object and set some custom properties
            """

            def show_annotation(sel):
                """
                Change the properties of the annotation box
                :param sel: selected matplotlib artist
                """
                x, y = sel.target
                # label = sel.artist.get_label()
                sel.annotation.set_text(f"x = {x:.1f}\ny = {y:.1f}")
                sel.annotation.get_bbox_patch().set(boxstyle='square', fc="white", ec='k')
                sel.annotation.arrow_patch.set(arrowstyle="-|>", ec="k", alpha=.5)

            c = mplcursors.cursor(multiple=False, hover=False, bindings={'select': 3, 'deselect': 1})
            c.connect('add', show_annotation)
            # c.enabled = False

        filt = (self.pem_file.data.Component == 'X') | (self.pem_file.data.Component == 'Y')
        data = self.pem_file.data[filt]

        self.df = DataFrame({'Station': data.Station.astype(int),
                                'RAD_tool': data.RAD_tool,
                                'RAD_ID': data.RAD_ID})
        # Only keep unique RAD IDs and unique stations
        self.df.drop_duplicates(subset=['RAD_ID'], inplace=True)
        self.df.drop_duplicates(subset=['Station'], inplace=True)
        self.df.sort_values(by='Station', inplace=True)

        az, dip, depth = Series(dtype=float), Series(dtype=float), Series(dtype=float)
        if self.pem_file.has_d7() and self.pem_file.has_xy():
            self.plot_tool_values(update=False)

            # Only add the roll axes legend since it won't change
            self.roll_ax.legend(self.roll_lines, [l.get_label() for l in self.roll_lines])

            az, dip, depth = tool_az, tool_dip, stations

        if self.pem_file.has_geometry():
            plot_seg_values()

            if not az.any():
                az, dip, depth = seg_az, seg_dip, seg_depth

        if az.any() and depth.any():
            add_az_spline(az, depth)
            add_dip_spline(dip, depth)

            add_collar_az(az, depth)
            add_collar_dip(dip, depth)

        # Adds the annotations when a point on a line is clicked
        set_cursor()

        self.update_plots()

    def plot_tool_values(self, update=False):
        """
        Plot all the tool values (azimuth, dip, map and roll angles). Moved out of "plot_pem" so it can be updated alone
        :param update: Bool, whether to update the plot afterwards
        """
        # Clear the tool azimuth line if it's an update
        if update:
            self.az_ax.lines.remove(self.tool_az_line)

        global tool_az, tool_dip, stations
        # tool_az = self.df.RAD_tool.map(lambda x: x.get_azimuth(
        #     allow_negative=self.actionAllow_Negative_Azimuth.isChecked()))
        tool_az = self.pem_file.get_azimuth(average=True).Angle
        tool_az = tool_az + self.mag_dec_sbox.value()  # Add the magnetic declination

        # If all azimuth values are negative, make them positive.
        if all(tool_az < 0):
            tool_az = tool_az + 360

        tool_dip = self.df.RAD_tool.map(lambda x: x.get_dip())
        mag = self.df.RAD_tool.map(lambda x: x.get_mag())
        acc_roll = self.df.RAD_tool.map(lambda x: x.get_acc_roll())
        mag_roll = self.df.RAD_tool.map(lambda x: x.get_mag_roll())
        stations = self.df.Station.astype(int)

        # Plot the tool information
        self.tool_az_line, = self.az_ax.plot(tool_az, stations, '-r',
                                             label='Tool Azimuth',
                                             lw=0.9,
                                             zorder=2)

        self.tool_mag_line, = self.mag_ax.plot(mag, stations,
                                               color='green',
                                               label='Total Magnetic Field',
                                               lw=0.3,
                                               zorder=1)

        self.tool_dip_line, = self.dip_ax.plot(tool_dip, stations, '-b',
                                               label='Tool Dip',
                                               lw=0.9,
                                               zorder=1)

        acc_roll_line, = self.roll_ax.plot(acc_roll, stations, '-b',
                                           label='Accelerometer',
                                           lw=0.9,
                                           zorder=1)

        mag_roll_line, = self.roll_ax.plot(mag_roll, stations, '-r',
                                           label='Magnetometer',
                                           lw=0.9,
                                           zorder=1)

        # Plot the information in the polar plot
        self.tool_az_line_p, = self.polar_ax.plot([math.radians(az) for az in tool_az], stations, '-r',
                                                  label='Tool Azimuth',
                                                  lw=0.9,
                                                  zorder=2)

        self.tool_dip_line_p, = self.polar_ax.plot([-math.radians(dip) for dip in tool_dip], stations, '-b',
                                                   label='Tool Dip',
                                                   lw=0.9,
                                                   zorder=1)

        self.az_lines = [self.tool_az_line, self.tool_mag_line]
        self.dip_lines = [self.tool_dip_line]
        self.roll_lines = [acc_roll_line, mag_roll_line]
        self.polar_lines = [self.tool_az_line_p, self.tool_dip_line_p]

        self.az_output_combo.addItem('Tool')
        self.dip_output_combo.addItem('Tool')

        self.mag_dec_sbox.setEnabled(True)
        self.show_tool_geom_cbox.setEnabled(True)
        self.show_mag_cbox.setEnabled(True)

        mag = self.pem_file.get_mag_dec()
        if mag:
            self.mag_dec_sbox.setValue(mag.dec)

        if update:
            self.canvas.draw_idle()
            self.polar_canvas.draw()

    def plot_df(self, df, source):
        """
        Plot a dataframe from a .seg or .dad file.
        :param df: DataFrame object with an Azimuth, Dip, and Depth column
        :param source: str, file source of the df, either 'seg' or 'dad'
        """
        if df.empty:
            return

        depths = df.Depth
        az = df.Azimuth
        dip = df.Dip
        # Flip the dip if it's coming from a .seg file
        if source == 'seg':
            dip = dip * -1

        if self.imported_az_line is None:
            # Enable the check box
            self.show_imported_geom_cbox.setEnabled(True)
            # Plot the lines
            self.imported_az_line, = self.az_ax.plot(az, depths,
                                                     color='crimson',
                                                     ls='dashed',
                                                     label='Imported Azimuth',
                                                     lw=0.8,
                                                     zorder=1)

            self.imported_dip_line, = self.dip_ax.plot(dip, depths,
                                                       color='dodgerblue',
                                                       ls='dashed',
                                                       label='Imported Dip',
                                                       lw=0.8,
                                                       zorder=1)

            # Add the lines to the polar plot
            self.imported_az_line_p, = self.polar_ax.plot([math.radians(z) for z in az], depths,
                                                          color='crimson',
                                                          ls='dashed',
                                                          label='Imported Azimuth',
                                                          lw=0.8,
                                                          zorder=1)

            self.imported_dip_line_p, = self.polar_ax.plot([-math.radians(z) for z in dip], depths,
                                                           color='dodgerblue',
                                                           ls='dashed',
                                                           label='Imported Dip',
                                                           lw=0.8,
                                                           zorder=1)
            # Add the lines to the legend
            self.az_lines.append(self.imported_az_line)
            self.dip_lines.append(self.imported_dip_line)
            self.polar_lines.append(self.imported_az_line_p)
            self.polar_lines.append(self.imported_dip_line_p)

            self.az_output_combo.addItem('Imported')
            self.dip_output_combo.addItem('Imported')
        else:
            # Update the data
            self.imported_az_line.set_data(az, depths)
            self.imported_dip_line.set_data(dip, depths)
            self.imported_az_line_p.set_data([math.radians(z) for z in az], depths)
            self.imported_dip_line_p.set_data([-math.radians(z) for z in dip], depths)

        self.toggle_imported_geom()
        self.update_plots()

    def open_seg_file(self, filepath):
        """
        Import and plot a .seg file
        :param filepath: str, filepath of the file to plot
        """
        df = read_csv(filepath,
                      delim_whitespace=True,
                      usecols=[1, 2, 5],
                      names=['Azimuth', 'Dip', 'Depth'],
                      dtype=float)
        self.plot_df(df, source='seg')

    def open_dad_file(self, filepath):
        """
        Import and plot a depth-azimuth-dip format file. Can be extentions xlsx, xls, csv, txt, dad.
        :param filepath: str or Path, filepath of the file to plot
        """
        def accept_file(data_df):
            try:
                self.plot_df(data_df, source='dad')
            except Exception as e:
                logger.error(f'Error plotting {filepath.name}. {str(e)}.')
                self.message.critical(self, 'Error',
                                         f'The following error occurred attempting to plot {filepath.name}: '
                                         f'\n{str(e)}.')

        filepath = Path(filepath)
        global selector
        selector = DADSelector()
        selector.accept_sig.connect(accept_file)

        try:
            selector.open(filepath)
        except Exception as e:
            logger.critical(f"The following error occurred trying to open {filepath.name}:{str(e)}")
            self.error.showMessage(f"The following error occurred trying to open {filepath.name}:{str(e)}")

    def redraw_az_line(self):
        """
        Signal slot, move the tool azimuth line when the magnetic declination value is changed.
        """
        v = self.mag_dec_sbox.value()
        self.tool_az_line.set_data(tool_az + v, stations)
        self.tool_az_line_p.set_data([math.radians(x + v) for x in tool_az], stations)
        self.update_plots(self.az_ax)

    def redraw_collar_az_line(self):
        """
        Signal slot, move the tool azimuth line when the magnetic declination value is changed.
        """
        v = [self.collar_az_sbox.value()] * 2
        self.collar_az_line.set_data(v, collar_depths)
        self.collar_az_line_p.set_data([math.radians(x) for x in v], collar_depths)
        self.update_plots(self.az_ax)

    def redraw_collar_dip_line(self):
        """
        Signal slot, move the tool azimuth line when the magnetic declination value is changed.
        """
        v = [self.collar_dip_sbox.value()] * 2
        self.collar_dip_line.set_data(v, collar_depths)
        self.collar_dip_line_p.set_data([-math.radians(x) for x in v], collar_depths)
        self.update_plots(self.dip_ax)

    def toggle_az_spline(self):
        """
        Signal slot, toggle the azimuth line on and off
        """
        if self.az_spline_cbox.isChecked():
            self.az_spline.line.set_visible(True)
            self.az_spline.spline.set_visible(True)
        else:
            self.az_spline.line.set_visible(False)
            self.az_spline.spline.set_visible(False)
        self.canvas.draw_idle()

    def toggle_dip_spline(self):
        """
        Signal slot, toggle the azimuth line on and off
        """
        if self.dip_spline_cbox.isChecked():
            self.dip_spline.line.set_visible(True)
            self.dip_spline.spline.set_visible(True)
        else:
            self.dip_spline.line.set_visible(False)
            self.dip_spline.spline.set_visible(False)
        self.canvas.draw_idle()

    def toggle_tool_geom(self):
        """
        Signal slot, toggle the tool dip and azimuth lines on and off
        :return:
        """
        if self.show_tool_geom_cbox.isChecked():
            self.tool_az_line.set_visible(True)
            self.tool_dip_line.set_visible(True)
            self.tool_az_line_p.set_visible(True)
            self.tool_dip_line_p.set_visible(True)
            if self.tool_az_line not in self.az_lines:
                # Add the lines back for the legend
                self.az_lines.append(self.tool_az_line)
                self.dip_lines.append(self.tool_dip_line)
                self.polar_lines.append(self.tool_az_line_p)
                self.polar_lines.append(self.tool_dip_line_p)
        else:
            self.tool_az_line.set_visible(False)
            self.tool_dip_line.set_visible(False)
            self.tool_az_line_p.set_visible(False)
            self.tool_dip_line_p.set_visible(False)
            # Remove the lines from the legend
            self.az_lines.remove(self.tool_az_line)
            self.dip_lines.remove(self.tool_dip_line)
            self.polar_lines.remove(self.tool_az_line_p)
            self.polar_lines.remove(self.tool_dip_line_p)

        # Update the legends
        self.az_ax.legend(self.az_lines, [l.get_label() for l in self.az_lines])
        self.dip_ax.legend(self.dip_lines, [l.get_label() for l in self.dip_lines])
        self.update_polar_legend()

        self.canvas.draw_idle()
        self.polar_canvas.draw_idle()

    def toggle_existing_geom(self):
        """
        Signal slot, toggle the segment dip and azimuth lines on and off
        :return:
        """
        if not self.existing_az_line:
            return

        if self.show_existing_geom_cbox.isChecked():
            self.existing_az_line.set_visible(True)
            self.existing_dip_line.set_visible(True)
            self.existing_az_line_p.set_visible(True)
            self.existing_dip_line_p.set_visible(True)
            if self.existing_az_line not in self.az_lines:
                # Add the lines back for the legend
                self.az_lines.append(self.existing_az_line)
                self.dip_lines.append(self.existing_dip_line)
                self.polar_lines.append(self.existing_az_line_p)
                self.polar_lines.append(self.existing_dip_line_p)
        else:
            self.existing_az_line.set_visible(False)
            self.existing_dip_line.set_visible(False)
            self.existing_az_line_p.set_visible(False)
            self.existing_dip_line_p.set_visible(False)
            # Remove the lines from the legend
            self.az_lines.remove(self.existing_az_line)
            self.dip_lines.remove(self.existing_dip_line)
            self.polar_lines.remove(self.existing_az_line_p)
            self.polar_lines.remove(self.existing_dip_line_p)

        # Update the legends
        self.az_ax.legend(self.az_lines, [l.get_label() for l in self.az_lines])
        self.dip_ax.legend(self.dip_lines, [l.get_label() for l in self.dip_lines])
        self.update_polar_legend()

        self.canvas.draw_idle()
        self.polar_canvas.draw_idle()

    def toggle_imported_geom(self):
        """
        Signal slot, toggle the imported dip and azimuth lines on and off
        """
        if not self.imported_az_line:
            return

        if self.show_imported_geom_cbox.isChecked():
            self.imported_az_line.set_visible(True)
            self.imported_dip_line.set_visible(True)
            self.imported_az_line_p.set_visible(True)
            self.imported_dip_line_p.set_visible(True)
            if self.imported_az_line not in self.az_lines:
                # Add the lines back for the legend
                self.az_lines.append(self.imported_az_line)
                self.dip_lines.append(self.imported_dip_line)
                self.polar_lines.append(self.imported_az_line_p)
                self.polar_lines.append(self.imported_dip_line_p)
        else:
            self.imported_az_line.set_visible(False)
            self.imported_dip_line.set_visible(False)
            self.imported_az_line_p.set_visible(False)
            self.imported_dip_line_p.set_visible(False)
            # Remove the lines from the legend
            self.az_lines.remove(self.imported_az_line)
            self.dip_lines.remove(self.imported_dip_line)
            self.polar_lines.remove(self.imported_az_line_p)
            self.polar_lines.remove(self.imported_dip_line_p)

        # Update the legends
        self.az_ax.legend(self.az_lines, [l.get_label() for l in self.az_lines])
        self.dip_ax.legend(self.dip_lines, [l.get_label() for l in self.dip_lines])
        self.update_polar_legend()

        self.canvas.draw_idle()
        self.polar_canvas.draw_idle()

    def toggle_collar_az(self):
        """
        Signal slot, toggle the Fixed azimuth line on and off
        """
        if self.collar_az_cbox.isChecked():
            self.collar_az_line.set_visible(True)
            self.collar_az_line_p.set_visible(True)
            if self.collar_az_line not in self.az_lines:
                # Add the lines back for the legend
                self.az_lines.append(self.collar_az_line)
                self.polar_lines.append(self.collar_az_line_p)
        else:
            self.collar_az_line.set_visible(False)
            self.collar_az_line_p.set_visible(False)
            self.az_lines.remove(self.collar_az_line)
            self.polar_lines.remove(self.collar_az_line_p)

        # Update the legends
        self.az_ax.legend(self.az_lines, [l.get_label() for l in self.az_lines])
        self.update_polar_legend()

        self.canvas.draw_idle()
        self.polar_canvas.draw_idle()

    def toggle_collar_dip(self):
        """
        Signal slot, toggle the Fixed azimuth line on and off
        """
        if self.collar_dip_cbox.isChecked():
            self.collar_dip_line.set_visible(True)
            self.collar_dip_line_p.set_visible(True)
            if self.collar_dip_line not in self.dip_lines:
                # Add the lines back for the legend
                self.dip_lines.append(self.collar_dip_line)
                self.polar_lines.append(self.collar_dip_line_p)
        else:
            self.collar_dip_line.set_visible(False)
            self.collar_dip_line_p.set_visible(False)
            self.dip_lines.remove(self.collar_dip_line)
            self.polar_lines.remove(self.collar_dip_line_p)

        # Update the legends
        self.dip_ax.legend(self.dip_lines, [l.get_label() for l in self.dip_lines])
        self.update_polar_legend()

        self.canvas.draw_idle()
        self.polar_canvas.draw_idle()

    def toggle_mag(self):
        """
        Signal slot, toggle the magnetic field strength line on and off
        """
        if not self.tool_mag_line:
            return

        if self.show_mag_cbox.isChecked():
            self.tool_mag_line.set_visible(True)
            if self.tool_mag_line not in self.az_lines:
                # Add the lines back for the legend
                self.az_lines.append(self.tool_mag_line)
        else:
            self.tool_mag_line.set_visible(False)
            # Remove the lines from the legend
            self.az_lines.remove(self.tool_mag_line)

        # Update the legends
        self.az_ax.legend(self.az_lines, [l.get_label() for l in self.az_lines])

        self.canvas.draw_idle()

    def toggle_accept(self):
        if self.az_output_combo.currentText() == '' or self.dip_output_combo.currentText() == '':
            self.accept_btn.setEnabled(False)
        else:
            self.accept_btn.setEnabled(True)

    def az_combo_changed(self):
        """
        Make the line selected for export stick out compared to the other lines
        """
        # Find which line is selected
        exempt_line = self.get_output_az_line()

        # Change the alpha for the lines accordingly
        for line in self.az_lines:
            if exempt_line is None:
                line.set_alpha(1.)
            else:
                if line is exempt_line:
                    line.set_alpha(1.)
                else:
                    line.set_alpha(0.1)

        if self.az_spline:
            # Make the alpha change separately for the InteractiveSpline object since there are two lines to change
            if exempt_line == self.az_spline or exempt_line is None:
                self.az_spline.change_alpha(1.)
            else:
                self.az_spline.change_alpha(0.1)

        self.canvas.draw_idle()

    def dip_combo_changed(self):
        """
         Make the line selected for export stick out compared to the other lines
         """
        # Find which line is selected
        exempt_line = self.get_output_dip_line()

        # Change the alpha for the lines accordingly
        for line in self.dip_lines:
            if exempt_line is None:
                line.set_alpha(1.)
            else:
                if line is exempt_line:
                    line.set_alpha(1.)
                else:
                    line.set_alpha(0.1)

        if self.dip_spline:
            # Make the alpha change separately for the InteractiveSpline object since there are two lines to change
            if exempt_line == self.dip_spline or exempt_line is None:
                self.dip_spline.change_alpha(1.)
            else:
                self.dip_spline.change_alpha(0.1)

        self.canvas.draw_idle()

    def get_output_az_line(self):
        """
        Find the corresponding line object for the text selected in the combo box
        :return: Line2D object
        """
        combo_text = self.az_output_combo.currentText()
        if combo_text == 'Imported':
            selected_line = self.imported_az_line
        elif combo_text == 'Existing':
            selected_line = self.existing_az_line
        elif combo_text == 'Tool':
            selected_line = self.tool_az_line
        elif combo_text == 'Spline':
            selected_line = self.az_spline
        elif combo_text == 'Fixed':
            selected_line = self.collar_az_line
        else:
            selected_line = None
        return selected_line

    def get_output_dip_line(self):
        """
        Find the corresponding line object for the text selected in the combo box
        :return: Line2D object
        """
        combo_text = self.dip_output_combo.currentText()
        if combo_text == 'Imported':
            selected_line = self.imported_dip_line
        elif combo_text == 'Existing':
            selected_line = self.existing_dip_line
        elif combo_text == 'Tool':
            selected_line = self.tool_dip_line
        elif combo_text == 'Spline':
            selected_line = self.dip_spline
        elif combo_text == 'Fixed':
            selected_line = self.collar_dip_line
        else:
            selected_line = None
        return selected_line

    def update_plots(self, ax=None):
        """
        Update/redraw and rescale the plots
        :param ax: Matplotlib Axes object, if given only this axes will be rescaled
        """
        if ax:
            axes = [ax]
        else:
            axes = self.axes

        for ax in axes:
            # Update the legends
            if ax == self.az_ax:
                self.az_ax.legend(self.az_lines, [l.get_label() for l in self.az_lines])
            elif ax == self.dip_ax:
                self.dip_ax.legend(self.dip_lines, [l.get_label() for l in self.dip_lines])

            ax.relim()
            ax.autoscale_view()

        self.update_polar_legend()
        self.canvas.draw_idle()
        self.polar_canvas.draw()

    def update_polar_legend(self):
        # Update the legend of the polar plot
        angle = np.deg2rad(0)
        self.polar_ax.legend(self.polar_lines, [l.get_label() for l in self.polar_lines],
                             loc="lower left",
                             bbox_to_anchor=(0.5 + np.cos(angle) / 2, 0.8 + np.sin(angle) / 2)
                             )


if __name__ == '__main__':
    from src.pem.pem_getter import PEMGetter
    from src.pem.pem_file import PEMParser
    app = QApplication(sys.argv)

    pg = PEMGetter()
    parser = PEMParser()
    # files = pg.get_pems(folder='PEM Rotation', file='_PU-340 XY.PEM')
    # files = pg.get_pems(folder='Raw Boreholes', number=1, random=True, incl='xy')
    files = pg.get_pems(file=r"Raw Boreholes\HOLE STE-21-02\RAW\ste-21-02 xy.pem")
    # files = pg.get_pems(folder='Raw Boreholes', file='XY_0410.PEM')
    # files = pg.get_pems(client='Minera', subfolder='CPA-5057', file='XY.PEM')

    win = PEMGeometry()
    win.open(files)
    # dad = r'C:\_Data\2020\Iscaycruz\Borehole\SE-20-02A\RAW\gyro.csv'
    # win.open_dad_file(dad)

    # win.az_output_combo.setCurrentIndex(1)
    # win.dip_output_combo.setCurrentIndex(1)
    # win.add_dad(r'C:\Users\Mortulo\PycharmProjects\PEMPro\sample_files\Segments\BR01.dad')
    app.exec_()
