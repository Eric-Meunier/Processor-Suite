import logging
import os
import sys
import math
import numpy as np
import pyqtgraph as pg

from PyQt5 import (QtGui, QtCore, uic)
from PyQt5.QtWidgets import (QMainWindow, QApplication, QComboBox, QShortcut, QFileDialog)

from src.logger import Log
from src.qt_py.custom_qt_widgets import NonScientific
from src.mag_field.mag_field_calculator import MagneticFieldCalculator

logger = logging.getLogger(__name__)

pg.setConfigOptions(antialias=True)
pg.setConfigOption('background', 'w')
pg.setConfigOption('foreground', 'k')
pg.setConfigOption('crashWarning', True)

# Modify the paths for when the script is being run in a frozen state (i.e. as an EXE)
if getattr(sys, 'frozen', False):
    application_path = os.path.dirname(sys.executable)
    loopCalcUIFile = 'qt_ui\\loop_calculator.ui'
    icons_path = 'qt_ui\\icons'
else:
    application_path = os.path.dirname(os.path.abspath(__file__))
    loopCalcUIFile = os.path.join(os.path.dirname(application_path), 'qt_ui\\loop_calculator.ui')
    icons_path = os.path.join(os.path.dirname(application_path), "qt_ui\\icons")

# Load Qt ui file into a class
loopCalcUi, _ = uic.loadUiType(loopCalcUIFile)


class LoopCalculator(QMainWindow, loopCalcUi):

    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.setWindowTitle(f"Loop Current Calculator")
        self.setWindowIcon(QtGui.QIcon(os.path.join(icons_path, 'voltmeter.png')))

        # Add the units option to the status bar
        self.units_combo = QComboBox()
        self.units_combo.addItem("nT/s")
        # self.units_combo.addItem("nT")
        self.units_combo.addItem("pT")
        self.units_combo.setCurrentIndex(0)
        self.statusBar().addPermanentWidget(self.units_combo)

        self.current = None

        # Format the plot
        self.mag_z = pg.PlotDataItem(pen=pg.mkPen('k'),
                                     symbol=None,
                                     symbolPen=pg.mkPen('k'),
                                     symbolBrush=pg.mkBrush('w'),
                                     symbolSize=8)
        self.plot_widget.setAxisItems({'left': NonScientific(orientation='left'),
                                       'bottom': NonScientific(orientation='bottom')})
        self.plot_widget.addItem(self.mag_z)
        self.plot_widget.hideButtons()
        self.plot_widget.setMenuEnabled(False)
        """Y label is changed during plotting"""
        self.plot_widget.setLabel('bottom', 'Distance From Loop Edge', units='m')
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
        self.plot_widget.setLimits(xMin=5, xMax=100, yMin=0)
        h_line = pg.InfiniteLine(pos=200000, angle=0, pen=pg.mkPen('r'))
        self.plot_widget.addItem(h_line, ignoreBounds=True)

        # Connect all the signals
        self.tx_setup_combo.currentIndexChanged.connect(self.calculate_current)
        self.num_tx_turns_sbox.valueChanged.connect(self.calculate_current)
        self.loop_h_sbox.valueChanged.connect(self.calculate_current)
        self.loop_w_sbox.valueChanged.connect(self.calculate_current)
        self.loop_gauge_sbox.valueChanged.connect(self.calculate_current)
        self.loop_quality_sbox.valueChanged.connect(self.calculate_current)
        self.num_parallel_sbox.valueChanged.connect(self.calculate_current)
        self.ramp_sbox.valueChanged.connect(self.calculate_current)
        self.voltage_sbox.valueChanged.connect(self.calculate_current)

        self.units_combo.currentIndexChanged.connect(self.calculate_current)
        self.units_combo.currentIndexChanged.connect(self.calculate_mag)

        self.current_sbox.valueChanged.connect(self.calculate_mag)
        self.distance_sbox.valueChanged.connect(self.calculate_mag)

        self.save_shortcut = QShortcut(QtGui.QKeySequence("Ctrl+S"), self)
        self.copy_shortcut = QShortcut(QtGui.QKeySequence("Ctrl+C"), self)
        self.save_shortcut.activated.connect(self.save_img)
        self.copy_shortcut.activated.connect(self.copy_img)

        self.calculate_current()
        self.calculate_mag()

    def keyPressEvent(self, evt):
        if evt.key() == QtCore.Qt.Key_Space:
            self.plot_widget.autoRange()

    def save_img(self):
        save_name, save_type = QFileDialog.getSaveFileName(self, 'Save Image',
                                                           'map.png',
                                                           'PNG file (*.PNG)'
                                                           )
        if save_name:
            self.grab().save(save_name)

    def copy_img(self):
        QApplication.clipboard().setPixmap(self.grab())

    def get_loop(self):
        """Create a loop (list of coordinates) for the magnetic field calculator"""
        h, w = self.loop_h_sbox.value(), self.loop_w_sbox.value()
        loop = np.array([(0, 0, 0),
                         (0, h, 0),
                         (-w, h, 0),
                         (-w, 0, 0)])
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
        calculator = MagneticFieldCalculator(self.get_loop())

        # Create a list of positions that range from 5m from the loop edge (at the loop length half-way point) to 100m
        h = self.loop_h_sbox.value()
        distances = np.arange(5, 105, 5)
        positions = [(d, h / 2, 0.1) for d in distances]

        # Calculate the magnetic field strength at each position
        units = self.units_combo.currentText()
        ramp = self.ramp_sbox.value() / 1000
        mag_values = []
        for dist, pos in zip(distances, positions):
            mx, my, mz = calculator.calc_total_field(pos[0], pos[1], pos[2], self.current_sbox.value(),
                                                     out_units=units,
                                                     ramp=ramp)
            mag_values.append(mz)

        # Plot only the Z component as it will always encompass the largest value
        self.mag_z.setData(y=np.abs(mag_values), x=distances)

        # Update the label in case of units change
        self.plot_widget.setLabel('left', 'Z-Component Magnetic Field Strength', units=units)
        self.plot_widget.autoRange()

        # Update the EM response label
        pos = (self.distance_sbox.value(), h / 2, 0.1)
        mx, my, mz = calculator.calc_total_field(pos[0], pos[1], pos[2], self.current_sbox.value(),
                                                 out_units=units,
                                                 ramp=ramp)
        self.response_label.setText(f"{abs(mz):,.0f} {units}")
        if abs(mz) >= 200000:
            self.response_label.setStyleSheet("color: red")
        else:
            self.response_label.setStyleSheet("color: black")


if __name__ == '__main__':
    app = QApplication(sys.argv)

    lc = LoopCalculator()
    lc.show()

    app.exec_()
