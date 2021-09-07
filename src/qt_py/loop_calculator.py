import logging
import math
import os
import sys

import numpy as np
import pyqtgraph as pg
from scipy.spatial.transform import Rotation as R
from PySide2.QtCore import Qt
from PySide2.QtGui import QKeySequence
from PySide2.QtWidgets import (QMainWindow, QFileDialog, QApplication, QShortcut, QComboBox)

from src.mag_field.mag_field_calculator import MagneticFieldCalculator
from src.qt_py import NonScientific, get_icon, get_line_color
from src.ui.loop_calculator import Ui_LoopCalculator

logger = logging.getLogger(__name__)


class LoopCalculator(QMainWindow, Ui_LoopCalculator):

    def __init__(self, parent=None, darkmode=False):
        def format_plots():
            # Plot widget
            self.plot_widget.setAxisItems({'left': NonScientific(orientation='left'),
                                           'bottom': NonScientific(orientation='bottom')})

            self.plot_widget.hideButtons()
            self.plot_widget.setMenuEnabled(False)
            # Y label is changed during plotting
            self.plot_widget.setLabel('bottom', 'Distance From Loop Center (m)')
            self.plot_widget.getAxis("bottom").nudge -= 10  # Move the label so it doesn't get clipped

            self.plot_widget.getAxis('left').setWidth(60)
            self.plot_widget.getAxis('right').setWidth(15)  # Move the right edge of the plot away from the window edge
            self.plot_widget.showAxis('right', show=True)  # Show the axis edge line
            self.plot_widget.showAxis('top', show=True)  # Show the axis edge line
            self.plot_widget.getAxis("right").setStyle(showValues=False)  # Disable showing the values of axis
            self.plot_widget.getAxis("top").setStyle(showValues=False)  # Disable showing the values of axis
            self.plot_widget.showLabel('right', show=False)
            self.plot_widget.showLabel('top', show=False)
            self.plot_widget.getAxis('left').enableAutoSIPrefix(enable=False)
            self.plot_widget.setLimits(xMin=-1000, xMax=1000, yMin=-500000, yMax=500000)
            self.plot_widget.setXRange(-200, 200)

            # Plan widget
            self.plan_widget.setAxisItems({'left': NonScientific(orientation='left'),
                                           'bottom': NonScientific(orientation='bottom')})
            self.plan_widget.hideButtons()
            self.plan_widget.setMenuEnabled(False)
            """Y label is changed during plotting"""
            self.plan_widget.setLabel('left', 'Northing (m)')
            self.plan_widget.setLabel('bottom', 'Easting (m)')
            self.plan_widget.getAxis("bottom").nudge -= 10  # Move the label so it doesn't get clipped

            self.plan_widget.getAxis('left').setWidth(60)
            self.plan_widget.getAxis('right').setWidth(15)  # Move the right edge of the plot away from the window edge
            self.plan_widget.showAxis('right', show=True)  # Show the axis edge line
            self.plan_widget.showAxis('top', show=True)  # Show the axis edge line
            self.plan_widget.getAxis("right").setStyle(showValues=False)  # Disable showing the values of axis
            self.plan_widget.getAxis("top").setStyle(showValues=False)  # Disable showing the values of axis
            self.plan_widget.showLabel('right', show=False)
            self.plan_widget.showLabel('top', show=False)
            self.plan_widget.getAxis('left').enableAutoSIPrefix(enable=False)
            self.plan_widget.setAspectLocked()

            # Link the X axis of the mag plot and plan map
            # self.plan_widget.setXLink(self.plot_widget)

        def init_signals():
            self.tx_setup_combo.currentIndexChanged.connect(self.calculate_current)
            self.num_tx_turns_sbox.valueChanged.connect(self.calculate_current)
            self.loop_h_sbox.valueChanged.connect(self.calculate_current)
            self.loop_w_sbox.valueChanged.connect(self.calculate_current)
            self.loop_gauge_sbox.valueChanged.connect(self.calculate_current)
            self.loop_quality_sbox.valueChanged.connect(self.calculate_current)
            self.num_parallel_sbox.valueChanged.connect(self.calculate_current)
            self.ramp_sbox.valueChanged.connect(self.calculate_current)
            self.voltage_sbox.valueChanged.connect(self.calculate_current)

            self.loop_h_sbox.valueChanged.connect(self.calculate_mag)  # Update the plot when the loop size is changed
            self.loop_w_sbox.valueChanged.connect(self.calculate_mag)  # Update the plot when the loop size is changed

            self.units_combo.currentIndexChanged.connect(self.calculate_current)
            self.units_combo.currentIndexChanged.connect(self.calculate_mag)

            self.current_sbox.valueChanged.connect(self.calculate_mag)
            self.distance_sbox.valueChanged.connect(self.calculate_mag)

        super().__init__()
        self.parent = parent
        self.darkmode = darkmode
        pg.setConfigOption('background', (66, 66, 66) if self.darkmode else 'w')
        pg.setConfigOption('foreground', "w" if self.darkmode else (53, 53, 53))

        self.setupUi(self)
        self.setWindowTitle(f"Loop Current Calculator")
        self.setWindowIcon(get_icon('voltmeter.png'))

        self.save_shortcut = QShortcut(QKeySequence("Ctrl+S"), self)
        self.copy_shortcut = QShortcut(QKeySequence("Ctrl+C"), self)
        self.save_shortcut.activated.connect(self.save_img)
        self.copy_shortcut.activated.connect(self.copy_img)

        # Add the units option to the status bar
        self.units_combo = QComboBox()
        self.units_combo.addItem("nT/s")
        # self.units_combo.addItem("nT")
        self.units_combo.addItem("pT")
        self.units_combo.setCurrentIndex(0)
        self.statusBar().addPermanentWidget(self.units_combo)

        self.current = None
        self.foreground_color = get_line_color("foreground", "pyqt", self.darkmode)
        self.background_color = get_line_color("background", "pyqt", self.darkmode)
        self.teal_color = get_line_color("teal", "pyqt", self.darkmode)
        self.blue_color = get_line_color("blue", "pyqt", self.darkmode)
        self.purple_color = get_line_color("purple", "pyqt", self.darkmode)
        self.aquamarine_color = get_line_color("aquamarine", "pyqt", self.darkmode)
        self.green_color = get_line_color("green", "pyqt", self.darkmode)
        self.pink_color = get_line_color("pink", "pyqt", self.darkmode)
        self.gray_color = get_line_color("gray", "pyqt", self.darkmode)

        # Legend must be added before thecurves
        self.plot_widget_legend = self.plot_widget.addLegend(pen=pg.mkPen(self.foreground_color),
                                                   brush=pg.mkBrush(self.background_color),
                                                   labelTextSize="8pt",
                                                   verSpacing=-1)
        self.plot_widget_legend.setParent(self.plot_widget)

        self.plan_widget_legend = self.plan_widget.addLegend(pen=pg.mkPen(self.foreground_color),
                                                   brush=pg.mkBrush(self.background_color),
                                                   labelTextSize="8pt",
                                                   verSpacing=-1)
        self.plan_widget_legend.setParent(self.plan_widget)

        # Format the mag response plot
        self.mag_z = pg.PlotDataItem(pen=pg.mkPen(self.teal_color),
                                     symbol=None,
                                     symbolPen=pg.mkPen(self.teal_color),
                                     symbolBrush=pg.mkBrush(self.background_color),
                                     symbolSize=8,
                                     name="Z Component")
        self.mag_x = pg.PlotDataItem(pen=pg.mkPen(self.green_color),
                                     symbol=None,
                                     symbolPen=pg.mkPen(self.green_color),
                                     symbolBrush=pg.mkBrush(self.background_color),
                                     symbolSize=8,
                                     name="X Component")
        self.plot_widget.addItem(self.mag_z)
        self.plot_widget.addItem(self.mag_x)

        self.station_line = pg.InfiniteLine(pos=0, pen=pg.mkPen(self.gray_color, style=Qt.DotLine, width=1.25))
        h_line = pg.InfiniteLine(pos=200000, angle=0, pen=pg.mkPen(self.pink_color, style=Qt.DashLine, width=1.25))
        h_line2 = pg.InfiniteLine(pos=-200000, angle=0, pen=pg.mkPen(self.pink_color, style=Qt.DashLine, width=1.25))
        # Add a legend entry for these lines
        h_line_legend_item = pg.PlotDataItem(pen=pg.mkPen(self.pink_color, style=Qt.DotLine, width=1.25),
                                              name="Overload Limit")
        self.plot_widget.addItem(self.station_line, ignoreBounds=True)
        self.plot_widget.addItem(h_line, ignoreBounds=True)
        self.plot_widget.addItem(h_line2, ignoreBounds=True)
        self.plot_widget.addItem(h_line_legend_item)

        # Format the plan map
        self.loop_item = pg.PlotCurveItem(pen=pg.mkPen(self.blue_color), name="Tx Loop")
        self.station_item = pg.ScatterPlotItem(pen=pg.mkPen(self.gray_color),
                                               brush=pg.mkBrush(self.background_color),
                                               symbol='+',
                                               size=13,
                                               name="Station")
        self.plan_widget.addItem(self.loop_item)
        self.plan_widget.addItem(self.station_item)

        format_plots()
        init_signals()

        self.calculate_current()
        self.calculate_mag()

    def keyPressEvent(self, evt):
        if evt.key() == Qt.Key_Space:
            self.plot_widget.autoRange()
            self.plan_widget.autoRange()

    def closeEvent(self, e):
        self.deleteLater()
        e.accept()

    def save_img(self):
        """Save a screenshot of the window """
        save_name, save_type = QFileDialog.getSaveFileName(self, 'Save Image', 'map.png', 'PNG file (*.PNG)')
        if save_name:
            self.grab().save(save_name)

    def copy_img(self):
        """Take a screenshot of the window and save it to the clipboard"""
        QApplication.clipboard().setPixmap(self.grab())

    def get_loop(self):
        """Create a loop (list of coordinates) for the magnetic field calculator"""
        h, w = self.loop_h_sbox.value(), self.loop_w_sbox.value()
        loop = np.array([(0, 0, 0),
                         (w, 0, 0),
                         (w, h, 0),
                         (0, h, 0)])
        return loop

    def get_loop_wire_diameter(self):
        """Return the loop wire gauge in inches"""
        gauge = self.loop_gauge_sbox.value()

        if gauge == 8:
            return 0.1285  # 3.2636 mm
        elif gauge == 10:
            return 0.1019  # 2.5882 mm
        elif gauge == 12:
            return 0.0808  # 2.0525 mm
        elif gauge == 14:
            return 0.0641  # 1.6277 mm
        else:
            raise NotImplemented(f"Wire gauge of {gauge} is not implemented.")

    def get_r_1000(self):
        """Return the resistance per 1000 ft in Ohms for the given loop quality"""
        gauge = self.loop_gauge_sbox.value()
        loop_quality = self.loop_quality_sbox.value()

        if gauge == 8:
            return 0.614 * (1 + (loop_quality/100))
        elif gauge == 10:
            return 0.9989 * (1 + (loop_quality/100))
        elif gauge == 12:
            return 1.588 * (1 + (loop_quality/100))
        elif gauge == 14:
            return 2.525 * (1 + (loop_quality/100))
        else:
            raise NotImplemented(f"Wire gauge of {gauge} is not implemented.")

    def get_loop_length(self):
        """Return the length of the loop in inches"""
        return (self.loop_h_sbox.value() + self.loop_w_sbox.value()) * 2 * 3.268 * 12  # in inches

    def get_loop_resistance(self):
        """Return the resistance of the loop in ohms. Formula: loop_turns * loop_resistance * loop_length / 12000"""
        loop_turns = self.num_tx_turns_sbox.value()
        loop_resistivity = self.get_r_1000()  # in Ohms / 1000 ft
        loop_length = self.get_loop_length()
        return loop_turns * loop_resistivity * loop_length / 12000

    def get_loop_inductance(self):
        """Return the inductance of the loop in mH"""
        loop_turns = self.num_tx_turns_sbox.value()
        loop_length = self.get_loop_length()
        loop_diameter = self.get_loop_wire_diameter()
        return (loop_turns ** 2) * (
                    0.00508 * loop_length * (2.303 * math.log(4 * loop_length / loop_diameter, 10) - 2.853)) / 1000

    def calculate_current(self):
        """
        Calculate and display the current values
        """
        def get_current_by_voltage():
            """
            I = V / R
            """
            return ((454 if tx_setup == 'Series' else 227) / (
                    loop_resistance / (num_loops * num_butterfly))) / num_butterfly

        def get_current_by_inductance():
            return (voltage * ramp / (loop_inductance / num_butterfly)) / num_butterfly

        def get_current_by_power():
            """
            I = √(P / R)  P is electric power
            """
            return math.sqrt((9600 if tx_setup == 'Series' else 4800) / (
                    loop_resistance / (num_loops * num_butterfly))) / num_butterfly

        tx_setup = self.tx_setup_combo.currentText()
        loop_resistance = self.get_loop_resistance()
        loop_inductance = self.get_loop_inductance()
        num_loops = self.num_parallel_sbox.value()
        num_butterfly = 1  # Don't understand what this does in the Excel sheets
        ramp = self.ramp_sbox.value()
        voltage = self.voltage_sbox.value()

        max_voltage = '320V' if tx_setup == 'Series' else '160V'
        current_by_voltage = get_current_by_voltage()
        current_by_inductance = get_current_by_inductance()
        current_by_power = get_current_by_power()
        max_current = min([current_by_voltage, current_by_inductance, current_by_power, 30])

        self.max_voltage_label.setText(f"(Maximum induced voltage: {max_voltage})")
        self.max_current_voltage_label.setText(f"{current_by_voltage:.1f}V")
        self.max_current_inductance_label.setText(f"{current_by_inductance:.1f}V")
        self.max_current_power_label.setText(f"{current_by_power:.1f}V")
        self.max_current_label.setText(f"{max_current:.1f}V")

    def calculate_mag(self):
        """
        Calculate and plot the magnetic field strength value of the Z component for a range of distances from the
        loop edge.
        """
        loop_coords = self.get_loop()
        em_calculator = MagneticFieldCalculator(loop_coords, closed_loop=True)

        # Create a list of positions that range from 5m from the loop edge (at the loop length half-way point) to 100m
        h, w = self.loop_h_sbox.value(), self.loop_w_sbox.value()
        distances = np.arange(-1005, 1005, 5)
        elevation = 1.
        positions = [(d + (w / 2), h / 2, elevation) for d in distances]

        # Calculate the magnetic field strength at each position
        units = self.units_combo.currentText()
        ramp = self.ramp_sbox.value() / 1000
        mag_z_values = []
        mag_x_values = []
        for dist, pos in zip(distances, positions):
            mx, my, mz = em_calculator.calc_total_field(pos[0], pos[1], pos[2], self.current_sbox.value(),
                                                     out_units=units,
                                                     ramp=ramp)

            # # Rotate the theoretical values into the same frame of reference used with boreholes/surface lines
            # rTx, rTy, rTz = R.from_euler('Z', -90, degrees=True).apply([mx, my, mz])
            #
            # # Rotate the theoretical values by the azimuth/dip
            # r = R.from_euler('YZ', [0, 90], degrees=True)
            # rT = r.apply([rTx, rTy, rTz])  # The rotated theoretical values

            mag_z_values.append(mz)
            mag_x_values.append(mx)

        # Plot only the Z component as it will always encompass the largest value
        self.mag_z.setData(y=mag_z_values, x=distances)
        self.mag_x.setData(y=mag_x_values, x=distances)

        # Update the plot label in case of units change
        self.plot_widget.setLabel('left', 'Magnetic Field Strength', units=units)
        self.plot_widget.autoRange()

        # Update the EM response label
        dist = self.distance_sbox.value()
        pos = (dist, h / 2, elevation)
        mx, my, mz = em_calculator.calc_total_field(pos[0], pos[1], pos[2], self.current_sbox.value(),
                                                 out_units=units,
                                                 ramp=ramp)

        self.z_response_label.setText(f"{mz:,.0f} {units}")
        self.x_response_label.setText(f"{mx:,.0f} {units}")
        if abs(mz) >= 200000:
            self.z_response_label.setStyleSheet(f"color: rgb{str(tuple(get_line_color('pink', 'pyqt', self.darkmode)))}")
        else:
            self.z_response_label.setStyleSheet(f"color: rgb{str(tuple(get_line_color('foreground', 'pyqt', self.darkmode)))}")

        if abs(mx) >= 200000:
            self.x_response_label.setStyleSheet(f"color: rgb{str(tuple(get_line_color('pink', 'pyqt', self.darkmode)))}")
        else:
            self.x_response_label.setStyleSheet(f"color: rgb{str(tuple(get_line_color('foreground', 'pyqt', self.darkmode)))}")

        # Plot the plan map
        loop_coords = np.vstack((loop_coords, loop_coords[0]))
        self.loop_item.setData(loop_coords[:, 0], loop_coords[:, 1])
        x, y = dist, h / 2
        self.station_item.setData([x], [y])
        self.station_line.setPos(pos[0] - (w / 2))


if __name__ == '__main__':
    from src.qt_py import dark_palette
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    darkmode = True
    if darkmode:
        app.setPalette(dark_palette)
    pg.setConfigOptions(antialias=True)
    pg.setConfigOption('crashWarning', True)
    pg.setConfigOption('background', (66, 66, 66) if darkmode else 'w')
    pg.setConfigOption('foreground', "w" if darkmode else (53, 53, 53))

    lc = LoopCalculator(darkmode=darkmode)
    lc.show()

    app.exec_()
