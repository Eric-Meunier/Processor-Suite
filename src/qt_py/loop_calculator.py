import logging
import os
import sys
import math

from PyQt5 import (uic)
from PyQt5.QtWidgets import (QMainWindow, QApplication)

from src.logger import Log
from src.mag_field.mag_field_calculator import MagneticFieldCalculator

logger = logging.getLogger(__name__)

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
        self.calculate_current()

        # Connect all the signals
        self.tx_setup_combo.currentIndexChanged.connect(self.calculate_current)
        self.num_tx_turns_sbox.valueChanged.connect(self.calculate_current)
        self.loop_h_sbox.valueChanged.connect(self.calculate_current)
        self.loop_w_sbox.valueChanged.connect(self.calculate_current)
        self.loop_gauge_sbox.valueChanged.connect(self.calculate_current)
        self.loop_quality_sbox.valueChanged.connect(self.calculate_current)
        self.ramp_sbox.valueChanged.connect(self.calculate_current)
        self.voltage_sbox.valueChanged.connect(self.calculate_current)

    @Log()
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

    @Log()
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

    @Log()
    def get_loop_length(self):
        """Return the length of the loop in inches"""
        return (self.loop_h_sbox.value() + self.loop_w_sbox.value()) * 2 * 3.268 * 12  # in inches

    @Log()
    def get_loop_resistance(self):
        """Return the resistance of the loop in ohms. Formula: loop_turns * loop_resistance * loop_length / 12000"""
        loop_turns = self.num_tx_turns_sbox.value()
        loop_resistance = self.get_r_1000()  # in Ohms / 1000 ft
        loop_length = self.get_loop_length()
        return loop_turns * loop_resistance * loop_length / 12000

    @Log()
    def get_loop_inductance(self):
        """Return the inductance of the loop in mH"""
        loop_turns = self.num_tx_turns_sbox.value()
        loop_length = self.get_loop_length()
        loop_diameter = self.get_loop_wire_diameter()
        return (loop_turns ** 2) * (
                    0.00508 * loop_length * (2.303 * math.log(4 * loop_length / loop_diameter, 10) - 2.853)) / 1000

    def calculate_current(self):

        @Log()
        def get_current_by_voltage():
            return (454 if tx_setup == 'Series' else 227 / (loop_resistance / loop_turns)) / loop_turns

        @Log()
        def get_current_by_inductance():
            return (voltage * ramp / (loop_inductance / loop_turns)) / loop_turns

        @Log()
        def get_current_by_power():
            return math.sqrt(9600 if tx_setup == 'Series' else 4800 / (loop_resistance / loop_turns)) / loop_turns

        tx_setup = self.tx_setup_combo.currentText()
        loop_turns = self.num_tx_turns_sbox.value()
        loop_resistance = self.get_loop_resistance()
        loop_inductance = self.get_loop_inductance()
        ramp = self.ramp_sbox.value()
        voltage = self.voltage_sbox.value()

        max_voltage = '320V' if tx_setup == 'Series' else '160V'
        current_by_voltage = get_current_by_voltage()
        current_by_inductance = get_current_by_inductance()
        current_by_power = get_current_by_power()

        self.max_voltage_label.setText(max_voltage)
        self.max_current_voltage_label.setText(f"{current_by_voltage:.1f}V")
        self.max_current_inductance_label.setText(f"{current_by_inductance:.1f}V")
        self.max_current_power_label.setText(f"{current_by_power:.1f}V")
        self.max_current_label.setText(f"{min([current_by_voltage, current_by_inductance, current_by_power]):.1f}V")


if __name__ == '__main__':
    app = QApplication(sys.argv)

    lc = LoopCalculator()
    lc.show()

    app.exec_()
