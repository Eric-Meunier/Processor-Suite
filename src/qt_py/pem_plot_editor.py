import copy
import logging
import math
import os
import re
import sys

import keyboard
import pyqtgraph as pg
import numpy as np
import pandas as pd
import pylineclip as lc
from PySide2.QtCore import Qt, Signal, QEvent, QTimer, QPointF, QRectF, QSettings
from PySide2.QtGui import QColor, QFont, QTransform, QBrush, QPen, QKeySequence, QCursor
from PySide2.QtWidgets import (QMainWindow, QMessageBox, QFileDialog, QLabel, QApplication, QWidget,
                               QInputDialog, QPushButton, QShortcut, QVBoxLayout)
from scipy import spatial, signal

from src.pem import convert_station
from src.pem.pem_file import PEMParser, PEMGetter
from src.qt_py import get_icon, get_line_color
from src.ui.pem_plot_editor import Ui_PEMPlotEditor
# from src.logger import Log

"""
NOTE: pyqtgraph 0.12.0 creates a bug with QRectF, specifically with decay_mouse_moved, where the event pointer
will not intersect the area of the QRectF.
"""

logger = logging.getLogger(__name__)
pd.options.mode.chained_assignment = None  # default='warn'

# TODO Toggle decay plots (double click?)
# TODO Disable auto cleaning and auto-cleaning lines for PP files (shouldn't be needed with new PP viewer)
# TODO update profile channel numbers to reflect actual channel number for non-split files
# TODO Calculate PP theoretical fit?


class PEMPlotEditor(QMainWindow, Ui_PEMPlotEditor):
    save_sig = Signal(object)
    close_sig = Signal(object)
    reset_file_sig = Signal(object)

    def __init__(self, parent=None, darkmode=False):
        super().__init__()
        self.parent = parent
        self.darkmode = darkmode

        self.foreground_color = get_line_color("foreground", "pyqt", self.darkmode)
        self.selection_color = get_line_color("teal", "pyqt", self.darkmode)
        self.deletion_color = get_line_color("red", "pyqt", self.darkmode)
        self.autoclean_color = get_line_color("green", "pyqt", self.darkmode)
        pg.setConfigOption('background', get_line_color("background", "pyqt", self.darkmode))
        pg.setConfigOption('foreground', self.foreground_color)

        self.setupUi(self)
        self.setFocusPolicy(Qt.StrongFocus)
        self.installEventFilter(self)
        self.activateWindow()
        self.setWindowTitle('PEM Plot Editor')
        self.setWindowIcon(get_icon('plot_editor.png'))
        self.actionSave.setIcon(get_icon('save.png'))
        self.actionSave_As.setIcon(get_icon('save_as.png'))
        self.actionCopy_Screenshot.setIcon(get_icon('copy.png'))
        self.actionSave_Screenshot.setIcon(get_icon('save2.png'))
        self.actionUn_Delete_All.setIcon(get_icon('cleaner.png'))
        self.actionReset_File.setIcon(get_icon('undo.png'))
        self.resize(1300, 900)
        self.setAcceptDrops(True)

        self.message = QMessageBox()
        self.pem_file = None
        self.fallback_file = None
        self.units = None

        self.profile_data = pd.DataFrame()
        self.channel_bounds = None
        self.theory_data = pd.DataFrame()
        self.stations = np.array([])
        self.mag_df = None
        self.current_component = "X"
        self.nearest_station = None
        self.line_selected = False
        self.selected_station = None
        self.selected_data = pd.DataFrame()
        self.selected_lines = []
        self.deleted_lines = []
        self.selected_profile_stations = np.array([])
        self.selected_profile_component = None
        self.component_profile_plot_items = {}
        self.component_stations = {}
        self.nearest_decay = None
        self.mag_curves = []
        self.last_offtime_channel = None  # For auto-clean lines

        self.active_ax = None
        self.active_ax_ind = None
        self.last_active_ax = None  # last_active_ax is always a plotitem object, and never None after the init.
        self.last_active_ax_ind = None  # last_active_ax is always a plotitem object, and never None after the init.
        self.plotted_decay_lines = []
        self.decay_data = pd.DataFrame()

        # Status bar formatting
        self.station_text = QLabel()
        self.decay_selection_text = QLabel()
        self.decay_selection_text.setIndent(20)
        self.decay_selection_text.setStyleSheet(f'color: rgb{tuple(self.selection_color)}')
        self.decay_selection_text.hide()
        self.profile_selection_text = QLabel()
        self.profile_selection_text.setIndent(20)
        self.profile_selection_text.setStyleSheet(f'color: #ce4a7e')
        self.profile_selection_text.hide()
        self.file_info_label = QLabel()
        self.file_info_label.setIndent(20)
        self.number_of_readings = QLabel()
        self.number_of_readings.setIndent(20)
        self.number_of_repeats = QPushButton('')
        self.number_of_repeats.setFlat(True)

        self.status_bar.addWidget(self.station_text, 0)
        self.status_bar.addWidget(self.decay_selection_text, 0)
        self.status_bar.addWidget(QLabel(), 1)  # Spacer
        self.status_bar.addWidget(self.profile_selection_text, 0)
        self.status_bar.addPermanentWidget(self.file_info_label, 0)
        self.status_bar.addPermanentWidget(self.number_of_readings, 0)
        self.status_bar.addPermanentWidget(self.number_of_repeats, 0)

        """ Plots """
        self.x_decay_plot = self.decay_layout.addPlot(0, 0, title='X Component', viewBox=DecayViewBox())
        self.y_decay_plot = self.decay_layout.addPlot(1, 0, title='Y Component', viewBox=DecayViewBox())
        self.z_decay_plot = self.decay_layout.addPlot(2, 0, title='Z Component', viewBox=DecayViewBox())
        self.decay_layout.ci.layout.setSpacing(2)  # Spacing between plots
        # self.decay_layout.ci.layout.setRowStretchFactor(1, 1)
        self.decay_axes = np.array([self.x_decay_plot, self.y_decay_plot, self.z_decay_plot])
        self.active_decay_axes = []

        # Lines for auto cleaning thresholds.
        self.x_decay_lower_threshold_line = pg.PlotCurveItem(pen=pg.mkPen(self.autoclean_color,
                                                                          width=1.5,
                                                                          style=Qt.DashLine),
                                                             setClickable=False,
                                                             name='median limit')
        self.x_decay_upper_threshold_line = pg.PlotCurveItem(pen=pg.mkPen(self.autoclean_color,
                                                                          width=1.5,
                                                                          style=Qt.DashLine),
                                                             setClickable=False,
                                                             name='median limit')
        self.y_decay_lower_threshold_line = pg.PlotCurveItem(pen=pg.mkPen(self.autoclean_color,
                                                                          width=1.5,
                                                                          style=Qt.DashLine),
                                                             setClickable=False,
                                                             name='median limit')
        self.y_decay_upper_threshold_line = pg.PlotCurveItem(pen=pg.mkPen(self.autoclean_color,
                                                                          width=1.5,
                                                                          style=Qt.DashLine),
                                                             setClickable=False,
                                                             name='median limit')
        self.z_decay_lower_threshold_line = pg.PlotCurveItem(pen=pg.mkPen(self.autoclean_color,
                                                                          width=1.5,
                                                                          style=Qt.DashLine),
                                                             setClickable=False,
                                                             name='median limit')
        self.z_decay_upper_threshold_line = pg.PlotCurveItem(pen=pg.mkPen(self.autoclean_color,
                                                                          width=1.5,
                                                                          style=Qt.DashLine),
                                                             setClickable=False,
                                                             name='median limit')

        self.auto_clean_lines = [self.x_decay_lower_threshold_line,
                                 self.x_decay_upper_threshold_line,
                                 self.y_decay_lower_threshold_line,
                                 self.y_decay_upper_threshold_line,
                                 self.z_decay_lower_threshold_line,
                                 self.z_decay_upper_threshold_line]

        self.select_all_action = QShortcut(QKeySequence("Ctrl+A"), self)

        for ax in self.decay_axes:
            ax.vb.installEventFilter(self)
            ax.vb.box_select_signal.connect(self.box_select_decay_lines)
            ax.hideButtons()
            ax.setMenuEnabled(False)
            ax.getAxis('left').enableAutoSIPrefix(enable=False)

            ax.scene().sigMouseMoved.connect(self.decay_mouse_moved)
            ax.scene().sigMouseClicked.connect(self.decay_plot_clicked)

        self.x_profile_layout.ci.layout.setSpacing(5)  # Spacing between plots
        self.y_profile_layout.ci.layout.setSpacing(5)  # Spacing between plots
        self.z_profile_layout.ci.layout.setSpacing(5)  # Spacing between plots

        # Configure the profile plots
        # X axis lin plots
        self.x_ax = self.x_profile_layout.addPlot(row=0, col=0, rowspan=5, viewBox=ProfileViewBox())
        self.x_ax0 = self.x_profile_layout.addPlot(row=1, col=0, rowspan=1, viewBox=ProfileViewBox())
        self.x_ax1 = self.x_profile_layout.addPlot(row=2, col=0, rowspan=1, viewBox=ProfileViewBox())
        self.x_ax2 = self.x_profile_layout.addPlot(row=3, col=0, rowspan=1, viewBox=ProfileViewBox())
        self.x_ax3 = self.x_profile_layout.addPlot(row=4, col=0, rowspan=1, viewBox=ProfileViewBox())
        self.x_ax4 = self.x_profile_layout.addPlot(row=5, col=0, rowspan=1, viewBox=ProfileViewBox())
        self.mag_x_ax = self.x_profile_layout.addPlot(row=6, col=0, rowspan=1, viewBox=ProfileViewBox())

        # Y axis lin plots
        self.y_ax = self.y_profile_layout.addPlot(row=0, col=0, rowspan=5, viewBox=ProfileViewBox())
        self.y_ax0 = self.y_profile_layout.addPlot(row=1, col=0, rowspan=1, viewBox=ProfileViewBox())
        self.y_ax1 = self.y_profile_layout.addPlot(row=2, col=0, rowspan=1, viewBox=ProfileViewBox())
        self.y_ax2 = self.y_profile_layout.addPlot(row=3, col=0, rowspan=1, viewBox=ProfileViewBox())
        self.y_ax3 = self.y_profile_layout.addPlot(row=4, col=0, rowspan=1, viewBox=ProfileViewBox())
        self.y_ax4 = self.y_profile_layout.addPlot(row=5, col=0, rowspan=1, viewBox=ProfileViewBox())
        self.mag_y_ax = self.y_profile_layout.addPlot(row=6, col=0, rowspan=1, viewBox=ProfileViewBox())

        # Z axis lin plots
        self.z_ax = self.z_profile_layout.addPlot(row=0, col=0, rowspan=5, viewBox=ProfileViewBox())
        self.z_ax0 = self.z_profile_layout.addPlot(row=1, col=0, rowspan=1, viewBox=ProfileViewBox())
        self.z_ax1 = self.z_profile_layout.addPlot(row=2, col=0, rowspan=1, viewBox=ProfileViewBox())
        self.z_ax2 = self.z_profile_layout.addPlot(row=3, col=0, rowspan=1, viewBox=ProfileViewBox())
        self.z_ax3 = self.z_profile_layout.addPlot(row=4, col=0, rowspan=1, viewBox=ProfileViewBox())
        self.z_ax4 = self.z_profile_layout.addPlot(row=5, col=0, rowspan=1, viewBox=ProfileViewBox())
        self.mag_z_ax = self.z_profile_layout.addPlot(row=6, col=0, rowspan=1, viewBox=ProfileViewBox())

        self.x_layout_axes = [self.x_ax, self.x_ax0, self.x_ax1, self.x_ax2, self.x_ax3, self.x_ax4, self.mag_x_ax]
        self.y_layout_axes = [self.y_ax, self.y_ax0, self.y_ax1, self.y_ax2, self.y_ax3, self.y_ax4, self.mag_y_ax]
        self.z_layout_axes = [self.z_ax, self.z_ax0, self.z_ax1, self.z_ax2, self.z_ax3, self.z_ax4, self.mag_z_ax]

        self.profile_axes = np.concatenate([self.x_layout_axes, self.y_layout_axes, self.z_layout_axes])
        self.mag_profile_axes = [self.mag_x_ax, self.mag_y_ax, self.mag_z_ax]

        self.station_cursors = []  # For easy toggling of the station cursors lines/text
        self.active_profile_axes = []

        # Configure each axes, including the mag plots. Axes linking is done during update_()
        for ax in self.profile_axes:
            ax.vb.installEventFilter(self)
            ax.vb.box_select_signal.connect(self.box_select_profile_plot)
            ax.hideButtons()
            ax.setMenuEnabled(False)
            ax.getAxis('left').setWidth(60)
            ax.getAxis('left').enableAutoSIPrefix(enable=False)

            # Add the vertical selection line
            color = get_line_color("teal", "pyqt", self.darkmode, alpha=200 if self.darkmode else 150)
            font = QFont("Helvetica", 10)
            hover_v_line = pg.InfiniteLine(angle=90, movable=False)
            hover_v_line.setPen(color, width=2.)
            selected_v_line = pg.InfiniteLine(angle=90, movable=False)
            selected_v_line.setPen(color, width=2.)

            # Add the text annotations for the vertical lines
            hover_v_line_text = pg.TextItem("")
            hover_v_line_text.setParentItem(ax.vb)
            hover_v_line_text.setAnchor((0, 0))
            hover_v_line_text.setPos(0, 0)
            hover_v_line_text.setColor(color)
            hover_v_line_text.setFont(font)

            ax.addItem(hover_v_line, ignoreBounds=True)
            ax.addItem(hover_v_line_text, ignoreBounds=True)
            ax.addItem(selected_v_line, ignoreBounds=True)

            self.station_cursors.append(hover_v_line)
            self.station_cursors.append(hover_v_line_text)
            self.station_cursors.append(selected_v_line)

            # Connect the mouse moved signal
            ax.scene().sigMouseMoved.connect(self.profile_mouse_moved)

            if ax != self.profile_axes[0]:
                ax.setXLink(self.profile_axes[0])

        # Mouse click signal will be emitted for each axes per click if connected to each profile axes.
        for ax in [self.x_ax, self.y_ax, self.z_ax]:
            ax.scene().sigMouseClicked.connect(self.profile_plot_clicked)

        self.load_settings()  # Checking the checkboxes emits the signals, so load settings before connecting signals.
        self.init_signals()
        self.toggle_profile_plots()

    def init_signals(self):
        def toggle_auto_clean_lines():
            for line in self.auto_clean_lines:
                if self.plot_auto_clean_lines_cbox.isChecked():
                    line.show()
                else:
                    line.hide()

        def select_all_stations():
            stations = self.pem_file.get_stations(converted=True)
            self.box_select_profile_plot((stations.min(), stations.max()), start=False)

        def toggle_station_cursor():
            for item in self.station_cursors:
                item.show() if self.actionShow_Station_Cursor.isChecked() else item.hide()

        def coil_area_changed():
            self.pem_file.scale_coil_area(self.coil_area_sbox.value())
            self.refresh_plots(components="all", preserve_selection=True)

        def soa_changed():
            soa_delta = self.soa_sbox.value() - self.pem_file.soa

            self.pem_file.rotate(method=None, soa=soa_delta)
            self.refresh_plots(components="all", preserve_selection=True)

        # Actions
        self.select_all_action.activated.connect(select_all_stations)

        # Menu
        self.actionSave.triggered.connect(self.save)
        self.actionSave_As.triggered.connect(self.save_as)
        self.actionUn_Delete_All.triggered.connect(self.undelete_all)
        self.actionSplit_Profile.triggered.connect(self.toggle_profile_plots)
        # Required or else the plots don't align correctly.
        self.actionSplit_Profile.triggered.connect(lambda: self.plot_profiles())
        self.actionSplit_Profile.triggered.connect(lambda: self.reset_range(decays=False, profiles=True))
        self.actionShow_Station_Cursor.triggered.connect(toggle_station_cursor)

        # Shortcuts
        self.actionSave_Screenshot.triggered.connect(self.save_img)
        self.actionCopy_Screenshot.triggered.connect(self.copy_img)

        # Checkboxes
        self.show_scatter_cbox.toggled.connect(lambda: self.plot_profiles(components='all'))
        self.plot_mag_cbox.toggled.connect(self.toggle_mag_plots)
        self.auto_range_cbox.toggled.connect(lambda: self.reset_range(decays=True, profiles=False))

        self.plot_auto_clean_lines_cbox.toggled.connect(toggle_auto_clean_lines)
        self.plot_ontime_decays_cbox.toggled.connect(lambda: self.plot_decays(self.selected_station,
                                                                              preserve_selection=True))
        self.plot_ontime_decays_cbox.toggled.connect(lambda: self.active_decay_axes[0].autoRange())

        self.link_y_cbox.toggled.connect(self.link_decay_y)
        self.link_x_cbox.toggled.connect(self.link_decay_x)

        # Spinboxes
        self.min_ch_sbox.valueChanged.connect(self.profile_channel_selection_changed)
        self.min_ch_sbox.valueChanged.connect(lambda: self.plot_profiles("all"))
        self.max_ch_sbox.valueChanged.connect(self.profile_channel_selection_changed)
        self.max_ch_sbox.valueChanged.connect(lambda: self.plot_profiles("all"))
        self.coil_area_sbox.valueChanged.connect(coil_area_changed)
        self.soa_sbox.valueChanged.connect(soa_changed)
        self.auto_clean_std_sbox.valueChanged.connect(self.update_auto_clean_lines)
        self.auto_clean_window_sbox.valueChanged.connect(self.update_auto_clean_lines)

        # Buttons
        self.change_comp_decay_btn.clicked.connect(lambda: self.change_decay_component_dialog(source='decay'))
        self.change_decay_suffix_btn.clicked.connect(lambda: self.change_suffix_dialog(source='decay'))
        self.change_station_decay_btn.clicked.connect(self.change_station)
        self.flip_decay_btn.clicked.connect(lambda: self.flip_decays(source='decay'))
        self.zoom_to_offtime_btn.clicked.connect(self.zoom_to_offtime)

        self.change_comp_profile_btn.clicked.connect(lambda: self.change_decay_component_dialog(source='profile'))
        self.change_profile_suffix_btn.clicked.connect(lambda: self.change_suffix_dialog(source='profile'))
        self.flip_profile_btn.clicked.connect(lambda: self.flip_decays(source='profile'))
        self.shift_station_profile_btn.clicked.connect(self.shift_stations)
        self.remove_profile_btn.clicked.connect(self.remove_stations)

        self.auto_clean_btn.clicked.connect(self.auto_clean)
        self.actionReset_File.triggered.connect(self.reset_file)
        self.number_of_repeats.clicked.connect(self.rename_repeats)

        # Manually toggle since its checkboxe may be set when loading settings, which doesn't occurs before the signals
        # are connected. Toggling mag plots is done during open().
        toggle_auto_clean_lines()

    def toggle_mag_plots(self):
        if self.plot_mag_cbox.isChecked() and self.plot_mag_cbox.isEnabled():
            for ax in self.mag_profile_axes:
                ax.show()
        else:
            for ax in self.mag_profile_axes:
                ax.hide()

    def toggle_profile_plots(self):
        """
        Toggle between the split 5-axis profile plots or the single. Ignores the mag axes.
        :return: None
        """
        for ax in self.profile_axes:
            if ax in [self.mag_x_ax, self.mag_y_ax, self.mag_z_ax]:
                continue

            if ax in [self.x_ax, self.y_ax, self.z_ax]:
                ax.hide() if self.actionSplit_Profile.isChecked() else ax.show()
            else:
                ax.show() if self.actionSplit_Profile.isChecked() else ax.hide()

        if self.actionSplit_Profile.isChecked():
            self.x_profile_layout.ci.layout.setRowStretchFactor(0, 0)
            self.y_profile_layout.ci.layout.setRowStretchFactor(0, 0)
            self.z_profile_layout.ci.layout.setRowStretchFactor(0, 0)
            self.min_ch_sbox.setEnabled(False)
            self.max_ch_sbox.setEnabled(False)
        else:
            # Set the stretch factor to allow the single profile ax to take up 5 spaces.
            self.x_profile_layout.ci.layout.setRowStretchFactor(0, 5)
            self.y_profile_layout.ci.layout.setRowStretchFactor(0, 5)
            self.z_profile_layout.ci.layout.setRowStretchFactor(0, 5)
            self.min_ch_sbox.setEnabled(True)
            self.max_ch_sbox.setEnabled(True)

    def save_settings(self):
        settings = QSettings("Crone Geophysics", "PEMPro")
        settings.beginGroup("pem_plot_editor")

        # Geometry
        settings.setValue("windowGeometry", self.saveGeometry())

        # Setting options
        settings.setValue("actionSplit_Profile", self.actionSplit_Profile.isChecked())
        settings.setValue("actionShow_Station_Cursor", self.actionShow_Station_Cursor.isChecked())
        settings.setValue("plot_ontime_decays_cbox", self.plot_ontime_decays_cbox.isChecked())
        settings.setValue("plot_auto_clean_lines_cbox", self.plot_auto_clean_lines_cbox.isChecked())
        settings.setValue("link_x_cbox", self.link_x_cbox.isChecked())
        settings.setValue("link_y_cbox", self.link_y_cbox.isChecked())
        settings.setValue("auto_range_cbox", self.auto_range_cbox.isChecked())
        settings.setValue("plot_mag_cbox", self.plot_mag_cbox.isChecked())
        settings.setValue("show_scatter_cbox", self.show_scatter_cbox.isChecked())

        settings.endGroup()

    def load_settings(self):
        settings = QSettings("Crone Geophysics", "PEMPro")
        settings.beginGroup("pem_plot_editor")

        # Geometry
        if settings.value("windowGeometry"):
            self.restoreGeometry(settings.value("windowGeometry"))

        # Setting options
        self.actionSplit_Profile.setChecked(
            settings.value("actionSplit_Profile", defaultValue=True, type=bool))
        self.actionShow_Station_Cursor.setChecked(
            settings.value("actionShow_Station_Cursor", defaultValue=True, type=bool))
        self.plot_ontime_decays_cbox.setChecked(
            settings.value("plot_ontime_decays_cbox", defaultValue=True, type=bool))
        self.plot_auto_clean_lines_cbox.setChecked(
            settings.value("plot_auto_clean_lines_cbox", defaultValue=True, type=bool))
        self.link_x_cbox.setChecked(
            settings.value("link_x_cbox", defaultValue=True, type=bool))
        self.link_y_cbox.setChecked(
            settings.value("link_y_cbox", defaultValue=True, type=bool))
        self.auto_range_cbox.setChecked(
            settings.value("auto_range_cbox", defaultValue=False, type=bool))
        self.plot_mag_cbox.setChecked(
            settings.value("plot_mag_cbox", defaultValue=True, type=bool))
        self.show_scatter_cbox.setChecked(
            settings.value("show_scatter_cbox", defaultValue=True, type=bool))

    def keyPressEvent(self, event):
        # Delete a decay when the delete key is pressed
        if event.key() == Qt.Key_Delete or event.key() == Qt.Key_R:
            if keyboard.is_pressed("shift"):
                self.undelete_selected_lines()
            else:
                self.delete_lines()

        elif event.key() == Qt.Key_C:
            self.cycle_profile_component()

        # Cycle through highlighted decays forwards
        elif event.key() == Qt.Key_D or event.key() == Qt.RightArrow:
            self.cycle_selection('up')

        # Cycle through highlighted decays backwards
        elif event.key() == Qt.Key_A or event.key() == Qt.LeftArrow:
            self.cycle_selection('down')

        # Cycle through the selection station forwards
        elif event.key() == Qt.Key_W:
            self.cycle_station('up')

        # Cycle through the selection station backwards
        elif event.key() == Qt.Key_S:
            self.cycle_station('down')

        # Flip the decay when the F key is pressed
        elif event.key() == Qt.Key_F:
            if self.selected_lines:
                self.flip_decays(source='decay')

        # Change the component of the readings to X
        elif event.key() == Qt.Key_X:
            if self.selected_lines:
                self.change_component('X', source='decay')

        # Change the component of the readings to Y
        elif event.key() == Qt.Key_Y:
            if self.selected_lines:
                self.change_component('Y', source='decay')

        # Change the component of the readings to Z
        elif event.key() == Qt.Key_Z:
            if self.selected_lines:
                self.change_component('Z', source='decay')

        # Reset the ranges of the plots when the space bar is pressed
        elif event.key() == Qt.Key_Space:
            if keyboard.is_pressed('Shift'):
                self.zoom_to_offtime()
            else:
                self.reset_range()

        # Clear the selected decays when the Escape key is pressed
        elif event.key() == Qt.Key_Escape:
            self.clear_selection()

    def eventFilter(self, source, event):
        # Scroll through channels in the single profile plot
        if event.type() == QEvent.GraphicsSceneWheel:
            if keyboard.is_pressed("CTRL"):
                self.min_ch_sbox.blockSignals(True)  # Prevent plotting to occur multiple times
                self.max_ch_sbox.blockSignals(True)  # Prevent plotting to occur multiple times

                y = event.delta()
                if y < 0:
                    # Increase channel numbers
                    self.max_ch_sbox.setValue(self.max_ch_sbox.value() + 1)
                    self.min_ch_sbox.setValue(self.min_ch_sbox.value() + 1)
                else:
                    # Decrease channel numbers
                    self.min_ch_sbox.setValue(self.min_ch_sbox.value() - 1)
                    self.max_ch_sbox.setValue(self.max_ch_sbox.value() - 1)
                self.plot_profiles("all")
                # Manually trigger this signal slot, so plotting doesn't occur again
                self.profile_channel_selection_changed(None)

                self.min_ch_sbox.blockSignals(False)
                self.max_ch_sbox.blockSignals(False)
            else:
                self.pyqtgraphWheelEvent(event)  # Change currently selected station
            return True
        elif event.type() == QEvent.Close:
            event.accept()
            self.deleteLater()
        return super().eventFilter(source, event)

    def closeEvent(self, e):
        self.save_settings()
        self.close_sig.emit(self)

        self.deleteLater()
        e.accept()

    def pyqtgraphWheelEvent(self, event):
        y = event.delta()
        if y < 0:
            self.cycle_station('down')
        else:
            self.cycle_station('up')

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

    def open(self, pem_file):
        """
        Open a PEMFile object and plot the data.
        :param pem_file: PEMFile object.
        """
        if isinstance(pem_file, str):
            parser = PEMParser()
            pem_file = parser.parse(pem_file)
        # assert not pem_file.is_pp(), f"PEMFile cannot be a PP file."

        self.setWindowTitle(f"PEM Plot Editor - {pem_file.filepath.name}")

        self.fallback_file = pem_file.copy()
        self.pem_file = pem_file
        self.data_edited()  # Update the profile and theory data

        file_info = ' | '.join([f"Timebase: {self.pem_file.timebase:.2f}ms",
                                f"{self.pem_file.get_survey_type()} Survey",
                                f"Operator: {self.pem_file.operator.title()}"])
        self.file_info_label.setText(file_info)

        if self.pem_file.is_split():  # Takes care of PP files too
            self.plot_ontime_decays_cbox.setEnabled(False)
        else:
            self.plot_ontime_decays_cbox.setEnabled(True)

        # Plot the mag profile if available. Disable the plot mag button if it's not applicable.
        if all([self.pem_file.is_borehole(), self.pem_file.has_xy(), self.pem_file.has_d7()]):
            self.mag_df = self.pem_file.get_mag(average=True)
            self.soa_sbox.blockSignals(True)
            self.soa_sbox.setEnabled(True)
            self.soa_sbox.setValue(self.pem_file.soa)
            self.soa_sbox.blockSignals(False)
            if self.mag_df.Mag.any():
                self.plot_mag_cbox.setEnabled(True)
                self.plot_mag()
            else:
                self.plot_mag_cbox.setEnabled(False)
        else:
            self.plot_mag_cbox.setEnabled(False)
            self.soa_sbox.setEnabled(False)
        # Manually toggle mag plots incase they may have been disabled in the previous step.
        self.toggle_mag_plots()

        # Disable suffix changes if the file is a borehole
        if self.pem_file.is_borehole():
            self.change_profile_suffix_btn.setEnabled(False)
            self.change_decay_suffix_btn.setEnabled(False)

        self.max_ch_sbox.blockSignals(True)
        self.min_ch_sbox.blockSignals(True)
        self.coil_area_sbox.blockSignals(True)
        self.auto_clean_std_sbox.blockSignals(True)
        self.auto_clean_window_sbox.blockSignals(True)

        # Set the units of the decay plots
        self.units = self.pem_file.units
        if self.units == 'pT':
            if "SQUID" in self.pem_file.get_survey_type():
                self.auto_clean_std_sbox.setValue(7)
            else:
                self.auto_clean_std_sbox.setValue(20)
        else:
            if self.pem_file.is_borehole():
                self.auto_clean_std_sbox.setValue(2)
            else:
                self.auto_clean_std_sbox.setValue(1.5)

        # Set the channel max for the single profile plot and auto clean box
        self.last_offtime_channel = self.pem_file.get_offtime_channels().index[-1]
        self.auto_clean_window_sbox.setMaximum(self.last_offtime_channel + 1)
        self.auto_clean_window_sbox.setValue(int(self.last_offtime_channel / 4))
        # self.min_ch_sbox.setMaximum(1)
        self.max_ch_sbox.setMaximum(self.last_offtime_channel)
        self.max_ch_sbox.setValue(self.last_offtime_channel)
        self.min_ch_sbox.setValue(self.last_offtime_channel - 5)
        self.coil_area_sbox.setValue(self.pem_file.coil_area)

        self.max_ch_sbox.blockSignals(False)
        self.min_ch_sbox.blockSignals(False)
        self.coil_area_sbox.blockSignals(False)
        self.auto_clean_std_sbox.blockSignals(False)
        self.auto_clean_window_sbox.blockSignals(False)

        # Add the line name and loop name as the title for the profile plots
        self.x_ax.setTitle(f"{self.pem_file.line_name} - Loop {self.pem_file.loop_name}\n[X Component]")
        self.x_ax0.setTitle(f"{self.pem_file.line_name} - Loop {self.pem_file.loop_name}\n[X Component]")
        self.y_ax.setTitle(f"{self.pem_file.line_name} - Loop {self.pem_file.loop_name}\n[Y Component]")
        self.y_ax0.setTitle(f"{self.pem_file.line_name} - Loop {self.pem_file.loop_name}\n[Y Component]")
        self.z_ax.setTitle(f"{self.pem_file.line_name} - Loop {self.pem_file.loop_name}\n[Z Component]")
        self.z_ax0.setTitle(f"{self.pem_file.line_name} - Loop {self.pem_file.loop_name}\n[Z Component]")

        # Set the X and Y axis labels for the decay axes
        for ax in self.decay_axes:
            ax.setLabel('left', f"Response", units=self.units)
            ax.setLabel('bottom', 'Channel number')

        # Plot the LIN profiles
        self.plot_profiles(components='all')

        # Plot the first station. This also helps with the linking of the X and Y axes for the decay plots.
        self.plot_decays(self.stations.min())

        # Link the X and Y axis of each axes
        self.link_decay_x()
        self.link_decay_y()
        self.reset_range()

        self.show()

    def save(self):
        """
        Save the PEM file.
        """
        self.status_bar.showMessage('Saving file...')
        self.pem_file.data = self.pem_file.data[~self.pem_file.data.Deleted.astype(bool)]
        self.pem_file.save()
        self.refresh_plots(components='all', preserve_selection=False)

        self.status_bar.showMessage('File saved.', 2000)
        QTimer.singleShot(2000, lambda: self.station_text.setText(station_text))
        self.save_sig.emit(self.pem_file)

    def save_as(self):
        """
        Save the PEM file to a new file name.
        """
        file_path = QFileDialog.getSaveFileName(self, '', str(self.pem_file.filepath), 'PEM Files (*.PEM)')[0]
        if file_path:
            text = self.pem_file.to_string()
            print(text, file=open(str(file_path), 'w+'))

            self.status_bar.showMessage(f'File saved to {file_path}', 2000)
            QTimer.singleShot(2000, lambda: self.station_text.setText(station_text))

    def update_(self):
        """
        Updates all the plots, hide/show components as needed, reset the limits of the plots, re-calculate the stations
        in the PEMFile.
        :return: None
        """
        def update_active_decay_plots(available_components):
            """
            Show/hide decay plots and profile plot tabs based on the components in the pem file
            """
            def toggle_decay_ax(component):
                if component == "X":
                    ax = self.x_decay_plot
                elif component == "Y":
                    ax = self.y_decay_plot
                else:
                    ax = self.z_decay_plot

                if component in available_components:
                    ax.show()
                    if ax not in self.active_decay_axes:
                        self.active_decay_axes.append(ax)
                else:
                    ax.hide()
                    if ax in self.active_decay_axes:
                        self.active_decay_axes.remove(ax)

            toggle_decay_ax("X")
            toggle_decay_ax("Y")
            toggle_decay_ax("Z")

            self.link_decay_x()
            self.link_decay_y()

        def update_active_profile_plots(avaiable_components):
            """
            Update which profile axes are active based on what components are present and update the axis links.
            Resets and re-adds all axes in order to keep the sorting of self.active_profile_axes consistent.
            """
            def link_profile_axes():  # is this necessary?
                if len(self.active_profile_axes) > 1:
                    for ax in self.active_profile_axes[1:]:
                        ax.setXLink(self.active_profile_axes[0])

            def update_active_axes(component):
                if component == "X":
                    layout_axes = self.x_layout_axes
                elif component == "Y":
                    layout_axes = self.y_layout_axes
                else:
                    layout_axes = self.z_layout_axes

                single_profile_ax = layout_axes[0]
                split_profile_axes = layout_axes[1:-1]
                mag_profile_ax = layout_axes[-1]

                if component in avaiable_components:
                    if self.actionSplit_Profile.isChecked():
                        # Add the split profile axes
                        self.active_profile_axes.extend(split_profile_axes)
                    else:
                        # Add the single profile ax
                        self.active_profile_axes.append(single_profile_ax)
                    # Add the mag ax last to keep the order consistent
                    self.active_profile_axes.append(mag_profile_ax)
                else:
                    # Cycle to the next component if there's no EM data for that component
                    if self.current_component not in avaiable_components:
                        print(f"'{component}' is not in the list of available components ({avaiable_components})")
                        self.cycle_profile_component()

                # if self.profile_tab_widget.currentIndex() == 0:
                #     self.cycle_profile_component()

            # Reset in order to keep the sorting of the self.active_profile_axes list consistent.
            self.active_profile_axes = []

            update_active_axes("X")
            update_active_axes("Y")
            update_active_axes("Z")

            # link_profile_axes()  # Is this necessary?

        # Update the list of stations
        self.stations = np.sort(self.pem_file.get_stations(converted=True))

        # Re-calculate the converted station numbers
        self.pem_file.data['cStation'] = self.pem_file.data.Station.map(convert_station)

        # Select a new selected station if it no longer exists
        if self.selected_station not in self.stations:
            self.selected_station = self.stations[0]

        # Re-set the limits of the profile plots
        for ax in np.concatenate([self.profile_axes, self.mag_profile_axes]):
            ax.setLimits(xMin=self.pem_file.data.cStation.min() - 1, xMax=self.pem_file.data.cStation.max() + 1)

        repeats = self.pem_file.get_repeats()
        self.number_of_repeats.setText(f'{len(repeats)} repeat(s)')
        if len(repeats) > 0:
            self.number_of_repeats.setStyleSheet(f'color: {get_line_color("red", "mpl", self.darkmode)}')
        else:
            self.number_of_repeats.setStyleSheet('')  # Reset the color automatically

        avaiable_components = self.pem_file.get_components()
        update_active_profile_plots(avaiable_components)
        update_active_decay_plots(avaiable_components)

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

    def reset_range(self, decays=True, profiles=True):
        """
        Auto range all axes.
        :param decays: bool, auto-range the decay plots.
        :param profiles: bool, auto-range the profile plots.
        """
        if decays is True:
            # If the y axes are linked, manually set the Y limit
            if self.link_y_cbox.isChecked():
                # Auto range the X, then manually set the Y.
                self.active_decay_axes[0].autoRange()
                filt = self.pem_file.data.cStation == self.selected_station
                min_y = self.pem_file.data.loc[filt].Reading.map(lambda x: x.min()).min()
                max_y = self.pem_file.data.loc[filt].Reading.map(lambda x: x.max()).max()
                self.active_decay_axes[0].setYRange(min_y, max_y)
            else:
                for ax in self.decay_axes:
                    ax.autoRange()

        if profiles is True:
            stations = self.pem_file.get_stations(converted=True, incl_deleted=True)
            for ax in self.profile_axes:
                ax.autoRange()
                ax.setXRange(stations.min(), stations.max())

    def zoom_to_offtime(self):
        """
        Change the Y limits of the decay plots to be zoomed on the late off-time channels.
        """
        filt = self.pem_file.data.cStation == self.selected_station
        channel_mask = ~self.pem_file.channel_times.Remove.astype(bool)
        min_y = self.pem_file.data.loc[filt].Reading.map(lambda x: x[channel_mask][-3:].min()).min() - 1
        max_y = self.pem_file.data.loc[filt].Reading.map(lambda x: x[channel_mask][-3:].max()).max() + 1

        # If the y axes are linked, manually set the Y limit
        if self.link_y_cbox.isChecked():
            # Auto range the X, then manually set the Y.
            self.active_decay_axes[0].autoRange()

            self.active_decay_axes[0].setYRange(min_y, max_y)
        else:
            for ax in self.decay_axes:
                ax.setYRange(min_y, max_y)

    def plot_profiles(self, components=None):
        """
        Plot the PEM file in a LIN plot style, with both components in separate plots
        :param components: list of str, components to plot. If None it will plot every component in the file.
        """
        def clear_plots(components):
            """
            Clear the plots of the given components. Does not clear the mag plots.
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
                # Don't clear the mag plots. They only need to be plotted once.
                if ax in [self.mag_x_ax, self.mag_y_ax, self.mag_z_ax]:
                    continue
                ax.clearPlots()

        def plot_lin(profile_data, axes):
            def plot_lines(df, ax):
                """
                Plot the lines on the pyqtgraph ax
                :param df: DataFrame of filtered data
                :param ax: pyqtgraph PlotItem
                """
                df_avg = df.groupby('Station').mean()
                x, y = df_avg.index.to_numpy(), df_avg.to_numpy()

                ax.plot(x=x, y=y, pen=pg.mkPen(self.foreground_color, width=1.))

            def plot_scatters(df, ax):
                """
                Plot the scatter plot markers
                :param df: DataFrame of filtered data
                :param ax: pyqtgraph PlotItem
                :return:
                """
                x, y = df.index.to_numpy(), df.to_numpy()

                scatter = pg.ScatterPlotItem(x=x, y=y,
                                             pen=pg.mkPen(self.foreground_color, width=1.),
                                             symbol='o',
                                             size=1.,
                                             brush='w')

                ax.addItem(scatter)

            def plot_theory_pp(df, ax):
                """
                Plot the theoretical PP values
                :param df: DataFrame, calculated theoretical total magnetic field strength.
                :param ax: pyqtgraph PlotItem for the PP frame
                :return: None
                """
                if not df.empty:
                    pp_plot_item = pg.PlotCurveItem(x=df.Station.to_numpy(), y=df[component].to_numpy(),
                                                    pen=pg.mkPen(self.selection_color, width=1.5, style=Qt.DotLine),
                                                    name="PP Theory")
                    ax.addItem(pp_plot_item)

            # Use the actual channel numbers for the Y axis of the profile plots so it matches with decay plots
            ch_offset = self.pem_file.channel_times[~self.pem_file.channel_times.Remove.astype(bool)].index[1] - 1

            # Since toggling the self.actionSplit_Profiles needs to call plot_profiles(), there's no point in plotting
            # both the split profiles and single profile.
            if self.actionSplit_Profile.isChecked():
                # Plot the split profile axes
                for i, bounds in enumerate(self.channel_bounds):
                    ax = axes[i + 1]  # axes[0] is the single profile ax

                    # Set the Y-axis labels
                    if i == 0:
                        ax.setLabel('left', f"PP channel", units=self.units)
                    else:
                        ax.setLabel('left', f"Channel {bounds[0]} to {bounds[1]}",
                                    units=self.units)

                    # Plot the data
                    for channel in range(bounds[0], bounds[1] + 1):
                        data = profile_data.loc[:, channel]
                        plot_lines(data, ax)
                        if self.show_scatter_cbox.isChecked():
                            plot_scatters(data, ax)

                    ax.autoRange()  # Is there ever a reason not to auto range the profile axes?
                plot_theory_pp(self.theory_data, axes[1])
                axes[1].autoRange()  # Auto range again after the PP line is added
            else:
                # Plot the single profile ax
                min_ch, max_ch = self.min_ch_sbox.value(), self.max_ch_sbox.value()
                ax = axes[0]
                for channel in range(min_ch, max_ch + 1):
                    ax.setLabel('left', f"Channel {'PP' if min_ch == 0 else min_ch} to {max_ch}", units=self.units)
                    data = profile_data.loc[:, channel]
                    plot_lines(data, ax)
                    if self.show_scatter_cbox.isChecked():
                        plot_scatters(data, ax)

                ax.autoRange()  # Is there ever a reason not to auto range the profile axes?
                # Only plot the theoretical value if the PP is plotted.
                if min_ch == 0:
                    plot_theory_pp(self.theory_data, ax)

        file = copy.deepcopy(self.pem_file)
        file.data = file.data.loc[~file.data.Deleted.astype(bool)]  # Remove deleted data for the profile plots.
        self.update_()
        self.number_of_readings.setText(f"{len(file.data)} reading(s)")

        if not isinstance(components, np.ndarray):
            # Get the components
            if components is None or components == 'all':
                components = file.get_components()

        clear_plots(components)

        for component in components:
            filt = (self.profile_data.Component == component) & (self.profile_data.Deleted == False)
            profile_data = self.profile_data[filt].set_index("Station", drop=True)

            # For nearest station calculation
            self.component_stations[component] = self.pem_file.get_stations(component=component, converted=True)

            if profile_data.empty:
                continue

            # Select the correct axes based on the component
            if component == 'X':
                axes = self.x_layout_axes
            elif component == 'Y':
                axes = self.y_layout_axes
            else:
                axes = self.z_layout_axes

            plot_lin(profile_data, axes)

    def plot_decays(self, station, preserve_selection=False):
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
            if stn.any():
                station_number_text = f" Station: {stn[0]}"
                reading_numbers = data.Reading_number.unique()
                if len(reading_numbers) > 1:
                    r_numbers_range = f"R-numbers: {reading_numbers.min()} - {reading_numbers.max()}"
                else:
                    r_numbers_range = f"R-number: {reading_numbers.min()}"

                station_readings = f"{len(data.index)} {'Reading' if len(data.index) == 1 else 'Readings'}"

                station_text = ' | '.join([station_number_text, station_readings, r_numbers_range])
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

            # Change the pen if the data is flagged for deletion or overload
            if row.Deleted is False:
                color = get_line_color("foreground", "pyqt", self.darkmode, alpha=255)
                z_value = 2
            else:
                color = get_line_color("red", "pyqt", self.darkmode, alpha=200)
                z_value = 1

            # Use a dotted line for readings that are flagged as Overloads
            if row.Overload is True:
                style = Qt.DashDotDotLine
            else:
                style = Qt.SolidLine

            # For all other lines
            pen = pg.mkPen(color, width=1., style=style)

            # Remove the on-time channels if the checkbox is checked
            if self.plot_ontime_decays_cbox.isChecked():
                y = row.Reading
            else:
                y = row.Reading[~self.pem_file.channel_times.Remove.astype(bool)]

            # Create and configure the line item
            decay_line = pg.PlotCurveItem(y=y, pen=pen)
            decay_line.setClickable(True, width=5)
            decay_line.setZValue(z_value)

            # Add the line at y=0
            ax.addLine(y=0, pen=pg.mkPen(self.foreground_color, width=0.15))
            # Plot the decay
            ax.addItem(decay_line)
            # Add the plot item to the list of plotted items
            self.plotted_decay_lines.append(decay_line)

        self.selected_station = station

        # Move the selected vertical line
        for ax in self.profile_axes:
            selected_v_line = ax.items[2]  # Clicked vertical station line
            selected_v_line.setPos(station)

        index_of_selected = []
        # Keep the same lines highlighted after data modification
        if preserve_selection is False:
            self.selected_lines.clear()
        else:
            ax_lines = [line for line in self.selected_lines if line.name() is None]  # Ignore median lines
            index_of_selected = [self.plotted_decay_lines.index(line) for line in ax_lines]

        for ax in self.decay_axes:
            ax.clear()

        self.plotted_decay_lines.clear()
        self.nearest_decay = None

        # Filter the data
        filt = self.pem_file.data['cStation'] == station
        self.decay_data = self.pem_file.data[filt]

        # Update the status bar text
        set_status_text(self.decay_data)

        # Re-add the auto clean lines, since clearing all items except the auto clean lines isn't working correctly.
        # Only add them if there's data for that component, otherwise there's just the auto clean lines with no decays.
        components = self.decay_data.Component.unique()
        if "X" in components:
            self.x_decay_plot.addItem(self.x_decay_lower_threshold_line)
            self.x_decay_plot.addItem(self.x_decay_upper_threshold_line)
        if "Y" in components:
            self.y_decay_plot.addItem(self.y_decay_lower_threshold_line)
            self.y_decay_plot.addItem(self.y_decay_upper_threshold_line)
        if "Z" in components:
            self.z_decay_plot.addItem(self.z_decay_lower_threshold_line)
            self.z_decay_plot.addItem(self.z_decay_upper_threshold_line)

        # Update the titles of each decay axes
        station = self.decay_data.Station.unique()[0]
        self.x_decay_plot.setTitle(f"Station {station} - X Component")
        self.y_decay_plot.setTitle(f"Station {station} - Y Component")
        self.z_decay_plot.setTitle(f"Station {station} - Z Component")

        # Plot the decays
        self.decay_data.apply(plot_decay, axis=1)

        self.update_auto_clean_lines()

        # Update the plot limits
        for ax in self.decay_axes:
            if self.plot_ontime_decays_cbox.isChecked():
                y = len(self.pem_file.channel_times)
            else:
                y = len(self.pem_file.channel_times[~self.pem_file.channel_times.Remove.astype(bool)])

            ax.setLimits(minXRange=0, maxXRange=y - 1, xMin=0, xMax=y - 1)

        # Re-select lines that were selected
        if preserve_selection is True:
            self.selected_lines = [self.plotted_decay_lines[i] for i in index_of_selected]
            self.highlight_lines()
        else:
            self.decay_selection_text.hide()
            self.change_comp_decay_btn.setEnabled(False)
            self.change_decay_suffix_btn.setEnabled(False)
            self.change_station_decay_btn.setEnabled(False)
            self.flip_decay_btn.setEnabled(False)

        if self.auto_range_cbox.isChecked() and preserve_selection is False:
            for ax in self.active_decay_axes:
                ax.autoRange()

    def plot_mag(self):
        # Only plot the mag once. It doesn't need to be cleared.
        x, y = self.mag_df.Station.to_numpy(), self.mag_df.Mag.to_numpy()
        for ax in self.mag_profile_axes:
            mag_plot_item = pg.PlotCurveItem(x=x, y=y, pen=pg.mkPen('1DD219', width=2.))
            ax.getAxis("left").setLabel("Total Magnetic Field", units="pT")
            ax.addItem(mag_plot_item)

    def update_auto_clean_lines(self):
        """
        Update the position and length of the auto-clean threshold lines.
        :return: None
        """
        window_size = self.auto_clean_window_sbox.value()
        for ax in self.decay_axes:
            if ax == self.x_decay_plot:
                comp_filt = self.decay_data.Component == "X"
                thresh_line_1, thresh_line_2 = self.x_decay_lower_threshold_line, self.x_decay_upper_threshold_line
            elif ax == self.y_decay_plot:
                comp_filt = self.decay_data.Component == "Y"
                thresh_line_1, thresh_line_2 = self.y_decay_lower_threshold_line, self.y_decay_upper_threshold_line
            else:
                comp_filt = self.decay_data.Component == "Z"
                thresh_line_1, thresh_line_2 = self.z_decay_lower_threshold_line, self.z_decay_upper_threshold_line

            # Ignore deleted data when calculating median
            existing_data = self.decay_data[comp_filt][~self.decay_data[comp_filt].Deleted.astype(bool)]
            if existing_data.empty:
                thresh_line_1.hide()
                thresh_line_2.hide()
                continue
            else:
                thresh_line_1.show()
                thresh_line_2.show()

            # Excludes next on-time data
            median_data = pd.DataFrame.from_records(
                existing_data.Reading.reset_index(drop=True)).iloc[:, :self.last_offtime_channel + 1]

            median = median_data.median(axis=0).to_numpy()
            if self.pem_file.number_of_channels > 10:
                median = signal.savgol_filter(median, 5, 3)
            if not self.plot_ontime_decays_cbox.isChecked():
                median = median[~self.pem_file.channel_times.Remove.astype(bool)]

            std = np.array([self.auto_clean_std_sbox.value()] * window_size)

            # Doesn't include next on-time data, if applicable.
            # median_data = median_data.loc[:,
            #                        ~self.pem_file.channel_times.Remove.reset_index(drop=True).astype(bool)]
            if not self.plot_ontime_decays_cbox.isChecked():
                median_data.rename(dict(zip(median_data.columns,
                                            range(len(median_data.columns)))),
                                   inplace=True,
                                   axis=1)  # Resets for the X axis values when not plotting on-time
            off_time_median = median_data.median().to_numpy()
            if self.pem_file.number_of_channels > 10:
                # off_time_median = signal.savgol_filter(off_time_median, 5, 3)
                off_time_median = signal.medfilt(off_time_median, 3)

            x = list(range(self.last_offtime_channel - window_size + 1, self.last_offtime_channel + 1))
            thresh_line_1.setData(x=x, y=off_time_median[-window_size:] + std)
            thresh_line_2.setData(x=x, y=off_time_median[-window_size:] - std)

    def highlight_lines(self):
        """
        Highlight the line selected and un-highlight any previously highlighted line.
        """
        def set_decay_selection_text(selected_data):
            """
            Update the status bar with information about the selected lines
            """
            if self.selected_lines and selected_data is not None:
                decay_selection_text = []
                # Show the range of reading numbers and reading indexes if multiple decays are selected
                if len(selected_data) > 1:
                    num_deleted = len(selected_data[selected_data.Deleted])
                    num_selected = f"{len(selected_data)} readings selected ({num_deleted} deleted)"
                    r_numbers = selected_data.Reading_number.unique()
                    r_indexes = selected_data.Reading_index.unique()
                    ztses = selected_data.ZTS.unique()

                    if len(r_numbers) > 1:
                        r_number_text = f"R-numbers: {r_numbers.min()}-{r_numbers.max()}"
                    else:
                        r_number_text = f"R-number: {r_numbers.min()}"

                    if len(r_indexes) > 1:
                        r_index_text = f"R-indexes: {r_indexes.min()}-{r_indexes.max()}"
                    else:
                        r_index_text = f"R-index: {r_indexes.min()}"

                    if len(ztses) > 1:
                        ztses_text = f"ZTS: {ztses.min():g}-{ztses.max():g}"
                    else:
                        ztses_text = f"ZTS: {ztses.min():g}"

                    # decay_selection_text = f"{len(selected_data)} selected    {r_number_text}    {r_index_text}"
                    decay_selection_text.extend([num_selected, r_number_text, r_index_text, ztses_text])

                # Show the reading number, reading index for the selected decay, plus azimuth, dip, and roll for bh
                else:
                    selected_decay = selected_data.iloc[0]

                    r_number_text = f"R-number: {selected_decay.Reading_number}"
                    r_index_text = f"R-index: {selected_decay.Reading_index}"
                    zts = f"ZTS: {selected_decay.ZTS:g}"
                    stack_number = f"Stacks: {selected_decay.Number_of_stacks}"

                    decay_selection_text.append(r_number_text)
                    decay_selection_text.append(r_index_text)
                    decay_selection_text.append(zts)
                    decay_selection_text.append(stack_number)

                    # Add the time stamp if it exists
                    if not pd.isna(selected_decay.Timestamp):
                        date_time = f"Timestamp: {selected_decay.Timestamp.strftime('%b %d - %H:%M:%S')}"
                        decay_selection_text.append(date_time)

                    # Add the RAD tool information if the PEM file is a borehole with all tool values present
                    if self.pem_file.is_borehole() and selected_decay.RAD_tool.has_tool_values():
                        azimuth = f"Azimuth: {selected_decay.RAD_tool.get_azimuth():.2f}"
                        dip = f"Dip: {selected_decay.RAD_tool.get_dip():.2f}"
                        roll = f"Roll: {selected_decay.RAD_tool.get_acc_roll():.2f}"

                        decay_selection_text.append(f"<{'  '.join([azimuth, dip, roll])}>")

                self.decay_selection_text.setText(' | '.join(decay_selection_text))
                self.decay_selection_text.show()

            # Reset the selection text if nothing is selected
            else:
                self.decay_selection_text.hide()

        if not self.plotted_decay_lines:
            return

        # Enable decay editing buttons
        if len(self.selected_lines) > 0:
            self.change_comp_decay_btn.setEnabled(True)
            if not self.pem_file.is_borehole():
                self.change_decay_suffix_btn.setEnabled(True)
            self.change_station_decay_btn.setEnabled(True)
            self.flip_decay_btn.setEnabled(True)
        else:
            self.change_comp_decay_btn.setEnabled(False)
            if not self.pem_file.is_borehole():
                self.change_decay_suffix_btn.setEnabled(False)
            self.change_station_decay_btn.setEnabled(False)
            self.flip_decay_btn.setEnabled(False)

        # Change the color of the plotted lines
        for line, Deleted, overload in zip(self.plotted_decay_lines,
                                           self.decay_data.Deleted,
                                           self.decay_data.Overload):

            # Change the pen if the data is flagged for deletion
            if Deleted is False:
                color = get_line_color("foreground", "pyqt", self.darkmode, alpha=200)
                z_value = 2
            else:
                color = get_line_color("red", "pyqt", self.darkmode, alpha=150)
                z_value = 1

            # Change the line style if the reading is overloaded
            if overload is True:
                style = Qt.DashDotDotLine
            else:
                style = Qt.SolidLine

            # Colors for the lines if they selected
            if line in self.selected_lines:
                if Deleted is False:
                    color = get_line_color("teal", "pyqt", self.darkmode, alpha=250)
                    z_value = 4
                else:
                    color = get_line_color("red", "pyqt", self.darkmode, alpha=200)
                    z_value = 3

                line.setPen(color, width=2, style=style)
                line.setZValue(z_value)
            else:
                # Color the lines that aren't selected
                line.setPen(color, width=1, style=style)
                line.setZValue(z_value)

        set_decay_selection_text(self.get_selected_decay_data())

    def clear_selection(self):
        """
        Signal slot, clear all selections (decay and profile plots)
        """
        self.selected_data = None
        self.selected_lines = []
        self.highlight_lines()
        self.selected_profile_stations = np.array([])

        # Hide the pg.LinearRegionItem in each profile axes
        for ax in self.profile_axes:
            ax.vb.lr.hide()

        # Disable the profile editing buttons
        self.change_comp_profile_btn.setEnabled(False)
        self.change_profile_suffix_btn.setEnabled(False)
        self.shift_station_profile_btn.setEnabled(False)
        self.flip_profile_btn.setEnabled(False)
        self.remove_profile_btn.setEnabled(False)

        # Hide the profile selection text. Decay selection text is taken care of in self.highlight_lines
        self.profile_selection_text.hide()

    def find_nearest_station(self, x):
        """
        Calculate the nearest station (for the current component) from the position x
        :param x: int, mouse x location
        :return: int, station number
        """
        stations = self.component_stations.get(self.current_component)
        idx = (np.abs(stations - x)).argmin()
        return stations[idx]

    def profile_mouse_moved(self, evt):
        """
        Signal slot, when the mouse is moved in one of the axes. Calculates and plots a light blue vertical line at the
        nearest station where the mouse is.
        :param evt: pyqtgraph MouseClickEvent
        """
        assert len(self.active_profile_axes) > 0, "There are no active profile axes."
        pos = evt

        profile_axes = self.get_component_profile_axes(self.current_component)
        mouse_point = profile_axes[0].vb.mapSceneToView(pos)
        self.nearest_station = self.find_nearest_station(int(mouse_point.x()))

        for ax in self.active_profile_axes:
            ax.items[0].setPos(self.nearest_station)  # Move the hover line
            ax.items[1].setPos(self.nearest_station, ax.viewRange()[1][1])  # Move the hover text
            # Change the anchor of the text for the later stations so they don't get clipped
            if len(self.stations) > 1 and self.nearest_station in self.stations[-math.floor(len(self.stations) / 2):]:
                ax.items[1].setAnchor((1, 0))
            else:
                ax.items[1].setAnchor((0, 0))
            ax.items[1].setText(str(self.nearest_station))  # Chang text to the be the station number

    def profile_plot_clicked(self, evt):
        """
        Signal slot, when the profile plot is clicked. Plots a darker blue vertical line at the nearest station where
        the click was made and plots that station's decays in the decay plot, and remove any selection.
        Uses the nearest station calculated in self.profile_mouse_moved.
        :param evt: pyqtgraph MouseClickEvent (not used)
        """
        self.selected_station = self.nearest_station
        self.plot_decays(self.nearest_station)

        # Hide any profile box-selection
        for ax in self.profile_axes:
            ax.vb.lr.hide()

        self.profile_selection_text.setText("")

    def decay_mouse_moved(self, evt):
        """
        Signal slot, find the decay_axes plot under the mouse when the mouse is moved to determine which plot is active.
        Highlights the decay line closest to the mouse.
        :param evt: MouseMovement event
        """
        def normalize(point):
            """
            Normalize a point so it works as a percentage of the view box data coordinates.
            :param point: QPoint object
            :return: normalized QPointF object
            """
            view = vb.viewRect()
            nx = (point.x() + view.x()) / view.width()
            ny = (point.y() + view.y()) / view.height()
            return QPointF(nx, ny)

        self.active_ax = None

        # print(f"\nEvt: {evt}")
        # Find which axes is beneath the mouse
        for ax in self.decay_axes:
            # print(f"Rect: {ax.vb.childGroup.sceneBoundingRect()}")
            if ax.vb.childGroup.sceneBoundingRect().contains(evt):
                self.active_ax = ax
                self.last_active_ax = ax
                self.active_ax_ind = np.where(self.decay_axes == self.active_ax)[0][0]
                self.last_active_ax_ind = self.active_ax_ind
                break

        if self.active_ax is not None:
            line_distances = []
            ax_lines = [line for line in self.active_ax.curves if line.name() is None]  # Ignore median lines
            vb = self.active_ax.vb

            if not ax_lines:
                return

            # Change the mouse coordinates to be in the plot's native coordinates (not data coordinates)
            m_pos = vb.mapSceneToView(evt)
            m_pos = normalize(m_pos)
            mouse_point = (m_pos.x(), m_pos.y())
            # logger.info(f"Mouse pos: {mouse_point[0]:.2f}, {mouse_point[1]:.2f}")

            for line in ax_lines:
                xi, yi = line.xData, line.yData
                interp_xi = np.linspace(xi.min(), xi.max(), 100)
                interp_yi = np.interp(interp_xi, xi, yi)  # Interp for when the mouse in between two points
                line_qpoints = [normalize(QPointF(x, y)) for x, y in zip(interp_xi, interp_yi)]
                line_points = np.array([(p.x(), p.y()) for p in line_qpoints])

                # logger.info(f"Line data pos: {np.average([p[0] for p in line_points]):.2f}, "
                #             f"{np.average([p[1] for p in line_points]):.2f}")

                # Calculate the distance between each point of the line and the mouse position
                distances = spatial.distance.cdist(np.array([mouse_point]), line_points, metric='euclidean')
                line_distances.append(distances)

            # Find the index of the smallest overall distance
            ind_of_min = np.array([l.min() for l in line_distances]).argmin()
            # logger.info(f"Line {ind_of_min} is nearest the mouse.")

            self.nearest_decay = ax_lines[ind_of_min]
            for line in ax_lines:
                if line == self.nearest_decay:
                    line_color = line.opts.get('pen').color()
                    line.setShadowPen(pg.mkPen(line_color, width=2.5, cosmetic=True))
                else:
                    line.setShadowPen(None)

        # Reset everything when the mouse is moved outside of an axes
        else:
            self.nearest_decay = None
            for line in self.plotted_decay_lines:
                line.setShadowPen(None)

    def decay_plot_clicked(self, evt):
        """
        Signal slot, change the profile tab to the same component as the clicked decay plot, and select the neareset
        decay line. If control is held, it extends the current selection.
        :param evt: MouseClick event
        """
        if self.active_ax_ind is not None:

            self.profile_tab_widget.setCurrentIndex(self.active_ax_ind)

            if self.nearest_decay:

                self.line_selected = True
                if keyboard.is_pressed('ctrl'):
                    self.selected_lines.append(self.nearest_decay)
                    self.highlight_lines()
                else:
                    self.selected_data = None
                    self.selected_lines = [self.nearest_decay]
                    self.highlight_lines()
        else:
            logger.warning(f"No nearest decay.")

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
            :param line: pg.PlotCurveItem
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
        self.get_selected_decay_data()

    def box_select_profile_plot(self, range, start):
        """
        Signal slot, select stations from the profile plot when click-and-dragged
        :param range: tuple, range of the linearRegionItem
        :param start: bool, if box select has just been started
        """
        # Using the range given by the signal doesn't always work properly when the click begins off-plot.
        if start:
            # If it's the start of the select, use the hover station since it seems to work better
            hover_station = self.profile_axes[0].items[1].x()  # The station hover line
            range = np.hstack([range, [hover_station]]).min(), np.hstack([range, [hover_station]]).max()
        else:
            range = (min(range), max(range))

        # Force the range to use existing stations
        x0 = self.find_nearest_station(range[0])
        x1 = self.find_nearest_station(range[1])
        # logger.info(f"Selecting stations from {x0} to {x1}")

        comp_profile_axes = self.get_component_profile_axes(self.current_component)
        comp_stations = self.pem_file.data[self.pem_file.data.Component == self.current_component].Station
        comp_stations = np.array([convert_station(s) for s in comp_stations])

        # Update the pg.LinearRegionItem for each axes of the current component
        for ax in comp_profile_axes:
            ax.vb.lr.setRegion((x0, x1))
            ax.vb.lr.show()

        # Find the stations that fall within the selection range
        self.selected_profile_stations = comp_stations[np.where((comp_stations <= x1) & (comp_stations >= x0))]
        # Copy so the selected component doesn't change when cycling components
        self.selected_profile_component = copy.deepcopy(self.current_component)

        # Enable the edit buttons and set the profile selection text
        if self.selected_profile_stations.any():
            self.change_comp_profile_btn.setEnabled(True)
            if not self.pem_file.is_borehole():
                self.change_profile_suffix_btn.setEnabled(True)
            self.shift_station_profile_btn.setEnabled(True)
            self.flip_profile_btn.setEnabled(True)
            self.remove_profile_btn.setEnabled(True)
            self.profile_selection_text.show()
            self.profile_selection_text.setText(
                f"Station {self.selected_profile_stations.min()} - {self.selected_profile_stations.max()}")
        else:
            self.change_comp_profile_btn.setEnabled(False)
            self.change_profile_suffix_btn.setEnabled(False)
            self.shift_station_profile_btn.setEnabled(False)
            self.flip_profile_btn.setEnabled(False)
            self.remove_profile_btn.setEnabled(False)
            self.profile_selection_text.hide()

    def get_component_profile_axes(self, comp):
        """
        Return the layout which contains the axes for the given component.
        :param comp: Str
        :return: list of axes
        """
        if comp == 'X':
            return self.x_layout_axes
        elif comp == 'Y':
            return self.y_layout_axes
        else:
            return self.z_layout_axes

    def get_selected_decay_data(self):
        """
        Return the corresponding data of the decay lines that are currently selected
        :return: pandas DataFrame
        """
        ind = []
        for line in self.selected_lines:
            if line in self.plotted_decay_lines:
                ind.append(self.plotted_decay_lines.index(line))
        if not ind:
            # print(f"Line is not in the list of decay lines.")
            return
        else:
            data = self.decay_data.iloc[ind]
            return data

    def get_selected_profile_data(self):
        """
        Return the corresponding data of the currently selected stations from the profile plots
        :return: pandas DataFrame
        """
        df = self.pem_file.data
        filt = ((df.Component == self.selected_profile_component) &
                (df.cStation >= self.selected_profile_stations.min()) &
                (df.cStation <= self.selected_profile_stations.max()))
        data = self.pem_file.data[filt]
        return data

    def get_active_component(self):
        """
        Return the active profile index and component
        :return: tuple, int index and str component
        """
        tab_ind = self.profile_tab_widget.currentIndex()
        if tab_ind == 0:
            comp = 'X'
        elif tab_ind == 1:
            comp = 'Y'
        else:
            comp = 'Z'
        return tab_ind, comp

    def get_comp_indexes(self):
        """
        Return the index of the stacked widget of each component present in the PEM file
        :return: list of int
        """
        indexes = []
        components = self.pem_file.get_components()
        if 'X' in components:
            indexes.append(0)
        if 'Y' in components:
            indexes.append(1)
        if 'Z' in components:
            indexes.append(2)
        return indexes

    def delete_lines(self):
        """
        Delete the selected lines. The data corresponding to the selected lines have their deletion flags flipped
        (i.e. from True > False or False > True). The station is then re-plotted. Line highlight is preserved.
        """
        selected_data = self.get_selected_decay_data()
        if selected_data is None:
            return

        if not selected_data.empty:
            # Change the deletion flag
            selected_data.loc[:, 'Deleted'] = selected_data.loc[:, 'Deleted'].map(lambda x: not x)

            # Update the data in the pem file object
            self.pem_file.data.loc[selected_data.index] = selected_data
            self.refresh_plots(components=selected_data.Component.unique(), preserve_selection=True)

    def undelete_selected_lines(self):
        """
        Undelete the selected lines. The data corresponding to the selected lines have their deletion flags changed to
        False. The station is then re-plotted. Line highlight is preserved.
        """
        selected_data = self.get_selected_decay_data()
        if not selected_data.empty:
            # Change the deletion flag
            selected_data.loc[:, 'Deleted'] = selected_data.loc[:, 'Deleted'].map(lambda x: False)

            # Update the data in the pem file object
            self.pem_file.data.loc[selected_data.index] = selected_data
            self.refresh_plots(components=selected_data.Component.unique(), preserve_selection=True)

    def undelete_all(self):
        """
        Un-delete all deleted readings in the file.
        :return: None
        """
        self.pem_file.data.loc[:, 'Deleted'] = self.pem_file.data.loc[:, 'Deleted'].map(lambda x: False)
        self.refresh_plots()

    def change_decay_component_dialog(self, source=None):
        """
        Open a user input window to select the new component to change to.
        :param source: str, either 'decay' or 'profile' to signify which data to modify
        """
        assert source is not None, f"No source selected."

        new_comp, ok_pressed = QInputDialog.getItem(self, "Change Component", "New Component:", ["X", "Y", "Z"],
                                                    current=0)

        if ok_pressed:
            self.change_component(new_comp, source=source)

    def change_component(self, new_component, source=None):
        """
        Change the component of the selected data
        :param new_component: str
        :param source: str, either 'decay' or 'profile' to know which selected data to modify
        """
        assert new_component in ["X", "Y", "Z"], f"Component must be either X, Y, or Z ({new_component} passed.)"
        if source == 'decay':
            selected_data = self.get_selected_decay_data()
        else:
            selected_data = self.get_selected_profile_data()

        old_comp = selected_data.Component.unique()[0]

        if not selected_data.empty and new_component != old_comp:
            # Change the deletion flag
            selected_data.loc[:, 'Component'] = selected_data.loc[:, 'Component'].map(lambda x: new_component)

            # Update the data in the pem file object
            self.pem_file.data.iloc[selected_data.index] = selected_data
            self.refresh_plots(components=[old_comp, new_component], preserve_selection=True)

    def change_suffix_dialog(self, source=None):
        """
        Open a user input window to select the new station suffix to change to.
        :param source: str, 'decay' or 'profile'
        """
        assert source is not None, f"No source selected."

        new_suffix, ok_pressed = QInputDialog.getItem(self, "Change Suffix", "New Suffix:", ['N', 'E', 'S', 'W'],
                                                      current=0)
        if ok_pressed:
            self.change_suffix(new_suffix, source=source)

    def change_suffix(self, new_suffix, source=None):
        """
        Change the station's suffix of the selected data
        :param new_suffix: str, must be in ['N', 'E', 'S', 'W']
        :param source: str, either 'decay' or 'profile' based on which data is to be changed
        """
        assert new_suffix.upper() in ['N', 'E', 'S', 'W'], f"{new_suffix} is not a valid suffix."
        if source == 'decay':
            selected_data = self.get_selected_decay_data()
        else:
            selected_data = self.get_selected_profile_data()

        selected_data.loc[:, 'Station'] = selected_data.loc[:, 'Station'].map(
            lambda x: re.sub(r'[NESW]', new_suffix.upper(), x))

        # Update the data in the pem file object
        self.pem_file.data.iloc[selected_data.index] = selected_data
        self.refresh_plots()

    def change_station(self):
        """
        Opens a input dialog to change the station number of the selected data.
        """
        if self.selected_lines:
            selected_data = self.get_selected_decay_data()
            selected_station = selected_data.Station.unique()[0]
            original_number = re.match(r"-?\d+", selected_station).group()

            new_station, ok_pressed = QInputDialog.getInt(self, "Change Station", "New Station:",
                                                          value=int(original_number),
                                                          step=5)

            if ok_pressed:
                # Update the station number in the selected data
                selected_data.loc[:, 'Station'] = re.sub(r"-?\d+", str(new_station), original_number)
                # Update the data in the pem file object
                self.pem_file.data.iloc[selected_data.index] = selected_data
                self.refresh_plots(components=selected_data.Component.unique())

    def profile_channel_selection_changed(self, value):
        """
        When the channel selection spin boxes for the single profile plot are changed.
        Prevents the maximum channel to be smaller than the minimum, and vise-versa.
        :param value: Int
        :return: None
        """
        self.min_ch_sbox.setMaximum(self.max_ch_sbox.value())
        self.max_ch_sbox.setMinimum(self.min_ch_sbox.value())

    def data_edited(self):
        """
        Signal slot, when PEM data is modified, update the data used for profile plotting.
        Removing the calculation of the profile data out of plot_profiles() helps speed up plotting when cycling thorugh
        channels in the single profile plot.
        :return: None
        """
        pem_file = self.pem_file.copy()
        # Calculate the lin plot axes channel bounds (for split profile plots only)
        self.channel_bounds = pem_file.get_channel_bounds()
        self.theory_data = pem_file.get_theory_pp()

        self.profile_data = pem_file.get_profile_data(averaged=False,
                                                      converted=True,
                                                      ontime=False,
                                                      incl_deleted=True).dropna()

    def shift_stations(self):
        """
        Shift the station numbers of the selected profile data
        """
        def shift(station):
            # Find the numbers in the station name
            station_num = re.match(r'-?\d+', station).group()
            if station_num:
                new_num = int(station_num) + shift_amount
                new_station = re.sub(r'-?\d+', str(new_num), station)
                return new_station

        selected_data = self.get_selected_profile_data()
        if selected_data.empty:
            return

        global shift_amount
        shift_amount, ok_pressed = QInputDialog.getInt(self, "Shift Stations", "Shift Amount:", value=0, step=5)

        if ok_pressed and shift_amount != 0:
            # Update the station number in the selected data
            selected_data.loc[:, 'Station'] = selected_data.loc[:, 'Station'].map(shift)
            # Update the data in the pem file object
            self.pem_file.data.iloc[selected_data.index] = selected_data
            self.refresh_plots(components=selected_data.Component.unique())

    def flip_decays(self, source=None):
        """
        Flip the polarity of the decays of the selected data.
        :param source: str, either 'decay' or 'profile' to know which selected data to modify
        """
        if source == 'decay':
            selected_data = self.get_selected_decay_data()
        else:
            selected_data = self.get_selected_profile_data()

        if not selected_data.empty:
            # Reverse the reading
            selected_data.loc[:, 'Reading'] = selected_data.loc[:, 'Reading'] * -1

            # Update the data in the pem file object
            self.pem_file.data.iloc[selected_data.index] = selected_data
            self.refresh_plots(components=selected_data.Component.unique(), preserve_selection=True)

    def remove_stations(self):
        """
        Set each reading in the selected stations to be flagged for deletion.
        """
        selected_data = self.get_selected_profile_data()
        if not selected_data.empty:
            # Change the deletion flag
            selected_data.loc[:, 'Deleted'] = True

            # Update the data in the pem file object
            self.pem_file.data.iloc[selected_data.index] = selected_data
            self.refresh_plots(components=selected_data.Component.unique(), preserve_selection=True)

    def cycle_profile_component(self):
        """
        Signal slot, cycle the profile plots to the next component
        """
        comp_indexes = self.get_comp_indexes()
        current_ind = self.profile_tab_widget.currentIndex()
        if len(comp_indexes) > 1:
            # Reset the cycle
            if current_ind + 1 > max(comp_indexes):
                new_ind = min(comp_indexes)
            else:
                # If the last of the current component was just changed to another component
                if current_ind not in comp_indexes:
                    new_ind = min(comp_indexes)
                else:
                    new_ind = comp_indexes[comp_indexes.index(current_ind) + 1]
        elif comp_indexes[0] != current_ind:
            new_ind = comp_indexes[0]
        else:
            new_ind = current_ind  # Component wasn't changed

        self.profile_tab_widget.setCurrentIndex(new_ind)
        self.current_component = ["X", "Y", "Z"][new_ind]

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
                # Force the new index to be a different station then the one selected
                new_ind = station_index
                while self.stations[new_ind] == self.selected_station and new_ind < len(self.stations) - 1:
                    new_ind += 1
                self.plot_decays(self.stations[new_ind], preserve_selection=False)
        elif direction == 'up':
            if station_index == 0:
                return
            else:
                # Force the new index to be a different station then the one selected
                new_ind = station_index
                while self.stations[new_ind] == self.selected_station and new_ind > 0:
                    new_ind -= 1
                self.plot_decays(self.stations[new_ind], preserve_selection=False)

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
        def eval_decay(reading, std, median, max_removable):
            """
            Evaluate the reading and calculate if it should be flagged for deletion. Will stop deleting when
            only 2 readings are left. Evaluates in two passes, the first pass is a large sweep of every channel
            using a high confidence interval, and the second only looks at the last 3 channels and uses a low
            confidence interval.
            :param reading: list, decay values for each channel
            :param std: int, a fixed standard deviation number to be used as a basis for calculating the data cutoff
            limits
            :param median: list, the median value of each channel decay value for the given group.
            :param max_removable: int, the maximum number of readings that can be removed before reaching the
            limit
            :return: bool, True if the reading should be deleted.
            """
            global count, local_count
            # TODO count not working, sometimes one reading remains
            if local_count < max_removable:
                # 68, 96, 99
                # Second pass, looking at the last 5 off-time channels, and using 68% confidence interval
                min_cutoff = median[mask][-window_size:] - std[mask][-window_size:]
                max_cutoff = median[mask][-window_size:] + std[mask][-window_size:]
                if any(reading[mask][-window_size:] < min_cutoff) or any(reading[mask][-window_size:] > max_cutoff):
                    count += 1
                    local_count += 1
                    return True
            else:
                logger.info(f"Max removable limit reached.")

            return False

        if self.pem_file.is_averaged():
            return

        global count, mask, threshold_value, window_size
        count = 0

        # Use a fixed standard deviation value for cleaning across all channels
        threshold_value = self.auto_clean_std_sbox.value()
        window_size = self.auto_clean_window_sbox.value()

        # Filter the data to only see readings that aren't already flagged for deletion
        data = self.pem_file.data[~self.pem_file.data.Deleted.astype(bool)]
        # Filter the readings to only consider off-time channels
        mask = np.asarray(~self.pem_file.channel_times.Remove.astype(bool))

        # Clean the data
        cleaned_data = pd.DataFrame()
        for id, group in data.groupby(['Station', 'Component'], as_index=False, group_keys=False):
            readings = np.array(group[~group.Deleted.astype(bool)].Reading.to_list())
            data_std = np.array([threshold_value] * len(readings[0]))
            data_median = np.median(group[~group.Deleted.astype(bool)].Reading.to_list(), axis=0)

            if len(group.loc[~group.Deleted.astype(bool)]) > 2:
                global local_count
                local_count = 0  # The number of readings that have been deleted so far for this group.
                max_removable = len(group) - 2  # Maximum number of readings that are allowed to be deleted.
                # Order the group by degree of deviation from the median
                group["Deviation"] = group.Reading.map(lambda y: abs(y - data_median).sum())
                group = group.sort_values(by="Deviation", ascending=False).drop("Deviation", axis=1)
                group.Deleted = group.Reading.map(lambda x: eval_decay(x, data_std, data_median, max_removable))

            cleaned_data = cleaned_data.append(group)

        # Update the data
        self.pem_file.data.update(cleaned_data)
        self.refresh_plots(components="all")

        # Reset the range for only the profile axes.
        self.reset_range(decays=False, profiles=True)

        self.message.information(self, 'Auto-clean results', f"{count} reading(s) automatically deleted.")

    def rename_repeats(self):
        """
        Automatically renames the repeat stations in the data.
        """
        def auto_rename_repeats(station):
            """
            Automatically rename a repeat station
            :param station: str, station number
            :return: str
            """
            station_num = re.search(r'\d+', station).group()
            if station_num[-1] == '1' or station_num[-1] == '6':
                station_num = str(int(station_num) - 1)
            elif station_num[-1] == '4' or station_num[-1] == '9':
                station_num = str(int(station_num) + 1)

            new_station = re.sub(r'\d+', station_num, station)
            return new_station

        repeats = self.pem_file.get_repeats()
        if repeats.empty:
            return

        # Rename the stations
        repeats.Station = repeats.Station.map(auto_rename_repeats)
        self.pem_file.data.loc[repeats.index] = repeats
        self.refresh_plots(components='all', preserve_selection=False)

        self.message.information(self, 'Auto-rename results', f"{len(repeats)} reading(s) automatically renamed.")

    def refresh_plots(self, components='all', preserve_selection=False):
        self.data_edited()
        self.plot_profiles(components=components)
        self.plot_decays(self.selected_station, preserve_selection=preserve_selection)

    def reset_file(self):
        """
        Revert all changes made to the PEM file.
        """
        response = self.message.question(self, 'Reset File',
                                         'Resetting the file will revert all changes made. '
                                         'Are you sure you wish to continue?',
                                         self.message.Yes | self.message.No)
        if response == self.message.Yes:
            self.reset_file_sig.emit((self.pem_file, self.fallback_file))
            self.open(self.fallback_file)
            self.status_bar.showMessage('File reset.', 1000)


class PPViewer(QMainWindow):
    def __init__(self, parent=None, darkmode=False):
        super().__init__()
        self.parent = parent
        self.darkmode = darkmode
        self.message = QMessageBox()
        self.pem_file = None

        self.foreground_color = get_line_color("foreground", "pyqt", self.darkmode)
        self.selection_color = get_line_color("teal", "pyqt", self.darkmode)
        self.deletion_color = get_line_color("red", "pyqt", self.darkmode)
        self.autoclean_color = get_line_color("green", "pyqt", self.darkmode)
        pg.setConfigOption('background', get_line_color("background", "pyqt", self.darkmode))
        pg.setConfigOption('foreground', self.foreground_color)

        self.setFocusPolicy(Qt.StrongFocus)
        self.installEventFilter(self)
        self.activateWindow()
        self.setWindowTitle('PEM Plot Editor')
        self.setWindowIcon(get_icon('plot_editor.png'))

        self.layout = QVBoxLayout()
        self.widget = pg.GraphicsLayoutWidget()
        self.widget.setLayout(self.layout)
        self.setCentralWidget(self.widget)

        self.decay_selection_text = QLabel()
        self.decay_selection_text.setIndent(20)
        self.decay_selection_text.setStyleSheet(f'color: rgb{tuple(self.selection_color)}')
        self.decay_selection_text.hide()
        self.number_of_readings = QLabel()
        self.number_of_readings.setIndent(20)
        self.file_info_label = QLabel()
        self.file_info_label.setIndent(20)

        self.statusBar().addWidget(self.decay_selection_text, 0)
        self.statusBar().addPermanentWidget(self.file_info_label, 0)
        self.statusBar().addPermanentWidget(self.number_of_readings, 0)

        self.selected_data = pd.DataFrame()
        self.selected_lines = []
        self.line_selected = False
        self.deleted_lines = []
        self.nearest_decay = None
        self.plotted_decay_lines = []
        self.decay_data = pd.DataFrame()

        # self.decay_layout = pg.GraphicsLayout()
        # self.layout.addWidget(self.decay_layout)
        self.decay_plot = self.widget.addPlot(0, 0, title='Z Component', viewBox=DecayViewBox())
        self.decay_plot.setTitle(f"PP Decays")
        self.decay_plot.setLabel('left', f"Response", units="nT/s")
        self.decay_plot.setLabel('bottom', 'Time (μs)')

        self.decay_plot.vb.installEventFilter(self)
        self.decay_plot.vb.box_select_signal.connect(self.box_select_decay_lines)
        self.decay_plot.hideButtons()
        self.decay_plot.setMenuEnabled(False)
        self.decay_plot.getAxis('left').enableAutoSIPrefix(enable=False)

        self.decay_plot.scene().sigMouseMoved.connect(self.decay_mouse_moved)
        self.decay_plot.scene().sigMouseClicked.connect(self.decay_plot_clicked)

    def keyPressEvent(self, event):
        # Delete a decay when the delete key is pressed
        if event.key() == Qt.Key_Delete or event.key() == Qt.Key_R:
            if keyboard.is_pressed("shift"):
                self.undelete_selected_lines()
            else:
                self.delete_lines()

        # Cycle through highlighted decays forwards
        elif event.key() == Qt.Key_D or event.key() == Qt.RightArrow:
            self.cycle_selection('up')

        # Cycle through highlighted decays backwards
        elif event.key() == Qt.Key_A or event.key() == Qt.LeftArrow:
            self.cycle_selection('down')

        # Flip the decay when the F key is pressed
        elif event.key() == Qt.Key_F:
            if self.selected_lines:
                self.flip_decays()

        # Reset the ranges of the plots when the space bar is pressed
        elif event.key() == Qt.Key_Space:
            self.reset_range()

        # Clear the selected decays when the Escape key is pressed
        elif event.key() == Qt.Key_Escape:
            self.clear_selection()

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

    def reset_range(self):
        self.decay_plot.autoRange()

    def reset_file(self):
        """
        Revert all changes made to the PEM file.
        """
        response = self.message.question(self, 'Reset File',
                                         'Resetting the file will revert all changes made. '
                                         'Are you sure you wish to continue?',
                                         self.message.Yes | self.message.No)
        if response == self.message.Yes:
            self.reset_file_sig.emit((self.pem_file, self.fallback_file))
            self.open(self.fallback_file)
            self.status_bar.showMessage('File reset.', 1000)

    def open(self, pem_file):
        """
        Open a PP PEMFile object and plot the data.
        :param pem_file: PEMFile object.
        """
        if isinstance(pem_file, str):
            parser = PEMParser()
            pem_file = parser.parse(pem_file)
        assert pem_file.is_pp(), f"PEMFile must be a PP file."

        self.setWindowTitle(f"PP Viewer - {pem_file.filepath.name}")

        self.pem_file = pem_file.copy()
        # Change all stations to be '0', and all components to be 'Z'.
        self.pem_file.data.Station = 0
        self.pem_file.data.Component = "Z"

        file_info = ' | '.join([f"Timebase: {self.pem_file.timebase:.2f}ms",
                                f"{self.pem_file.survey_type}",
                                f"Operator: {self.pem_file.operator.title()}"])
        self.file_info_label.setText(file_info)

        self.plot_decays()
        self.reset_range()

    def plot_decays(self, preserve_selection=False):
        """
        Plot the decay lines for each component of the given station
        :param preserve_selection: bool, re-select the selected lines after plotting
        """
        def set_status_text(data):
            """
            Set the status bar text with information about the station
            :param data: dataFrame of plotted decays
            """
            global station_text
            stn = data.Station.unique()
            if stn.any():
                station_number_text = f" Station: {stn[0]}"
                reading_numbers = data.Reading_number.unique()
                if len(reading_numbers) > 1:
                    r_numbers_range = f"R-numbers: {reading_numbers.min()} - {reading_numbers.max()}"
                else:
                    r_numbers_range = f"R-number: {reading_numbers.min()}"

                station_readings = f"{len(data.index)} {'Reading' if len(data.index) == 1 else 'Readings'}"

                station_text = ' | '.join([station_number_text, station_readings, r_numbers_range])
            else:
                station_text = ''
            self.station_text.setText(station_text)

        def plot_decay(row):
            """
            Plot the decay line (Reading) of the row
            :param row: pandas Series
            """
            # Change the pen if the data is flagged for deletion or overload
            if row.Deleted is False:
                color = get_line_color("foreground", "pyqt", self.darkmode, alpha=255)
                z_value = 2
            else:
                color = get_line_color("red", "pyqt", self.darkmode, alpha=200)
                z_value = 1

            # Use a dotted line for readings that are flagged as Overloads
            if row.Overload is True:
                style = Qt.DashDotDotLine
            else:
                style = Qt.SolidLine

            # For all other lines
            pen = pg.mkPen(color, width=1., style=style)

            y = row.Reading

            # Create and configure the line item
            decay_line = pg.PlotCurveItem(x=x, y=y, pen=pen, name="Testing line name")
            decay_line.setClickable(True, width=5)
            decay_line.setZValue(z_value)

            # Add the line at y=0
            self.decay_plot.addLine(y=0, pen=pg.mkPen(self.foreground_color, width=0.15))
            # Plot the decay
            self.decay_plot.addItem(decay_line)
            # Add the plot item to the list of plotted items
            self.plotted_decay_lines.append(decay_line)

        # TODO also plot where ideal should location would be, and calculate that difference with what was used.
        def plot_shoulder():
            data = self.pem_file.data.sort_values(by="Reading_number", ascending=False)
            channel_centers = self.pem_file.channel_times.Center.to_numpy() * 1e6
            # Sort the data so the last two readings have shoulders plotted.
            if len(data) < 2:
                logger.info(f"{self.pem_file.filepath.name} doesn't have 2 PP readings.")
                return

            readings = data.iloc[0:2].Reading
            for decay in readings:
                y = np.percentile(decay, 90)
                x_ind = list(decay).index(min(decay, key=lambda x: abs(x-y)))

                scatter = pg.ScatterPlotItem(x=[channel_centers[x_ind]], y=[y],
                                             name="Shoulder",
                                             pen=pg.mkPen(self.foreground_color, width=0.15))
                self.decay_plot.addItem(scatter)

                for value in [100, 90, 50, 10, 0]:
                    p = np.percentile(decay, value)
                    line = pg.InfiniteLine(pos=p, angle=0, pen=pg.mkPen(get_line_color("blue", "pyqtgraph", self.darkmode)),
                                           label=str(value), name=str(value))
                    self.decay_plot.addItem(line)

        index_of_selected = []
        # Keep the same lines highlighted after data modification
        if preserve_selection is False:
            self.selected_lines.clear()
        else:
            ax_lines = [line for line in self.selected_lines if line.name() is None]  # Ignore median lines
            index_of_selected = [self.plotted_decay_lines.index(line) for line in ax_lines]

        self.decay_plot.clear()
        self.plotted_decay_lines.clear()
        self.nearest_decay = None

        # Filter the data
        self.decay_data = self.pem_file.data

        # # Update the status bar text
        # set_status_text(self.decay_data)

        # Plot the decays
        x = self.pem_file.channel_times.Center.to_numpy() * 1e6
        self.decay_data.apply(plot_decay, axis=1)
        plot_shoulder()

        self.decay_plot.setLimits(xMin=x.min(), xMax=x.max())

        # Re-select lines that were selected
        if preserve_selection is True:
            self.selected_lines = [self.plotted_decay_lines[i] for i in index_of_selected]
            self.highlight_lines()
        else:
            self.decay_selection_text.hide()

        if preserve_selection is False:
            self.reset_range()

    def clear_selection(self):
        """
        Signal slot, clear all selections (decay and profile plots)
        """
        self.selected_data = None
        self.selected_lines = []
        self.highlight_lines()

    def highlight_lines(self):
        """
        Highlight the line selected and un-highlight any previously highlighted line.
        """
        def set_decay_selection_text(selected_data):
            """
            Update the status bar with information about the selected lines
            """
            if self.selected_lines and selected_data is not None:
                decay_selection_text = []
                # Show the range of reading numbers and reading indexes if multiple decays are selected
                if len(selected_data) > 1:
                    num_deleted = len(selected_data[selected_data.Deleted])
                    num_selected = f"{len(selected_data)} readings selected ({num_deleted} deleted)"
                    r_numbers = selected_data.Reading_number.unique()
                    r_indexes = selected_data.Reading_index.unique()
                    ztses = selected_data.ZTS.unique()

                    if len(r_numbers) > 1:
                        r_number_text = f"R-numbers: {r_numbers.min()}-{r_numbers.max()}"
                    else:
                        r_number_text = f"R-number: {r_numbers.min()}"

                    if len(r_indexes) > 1:
                        r_index_text = f"R-indexes: {r_indexes.min()}-{r_indexes.max()}"
                    else:
                        r_index_text = f"R-index: {r_indexes.min()}"

                    if len(ztses) > 1:
                        ztses_text = f"ZTS: {ztses.min():g}-{ztses.max():g}"
                    else:
                        ztses_text = f"ZTS: {ztses.min():g}"

                    # decay_selection_text = f"{len(selected_data)} selected    {r_number_text}    {r_index_text}"
                    decay_selection_text.extend([num_selected, r_number_text, r_index_text, ztses_text])

                # Show the reading number, reading index for the selected decay, plus azimuth, dip, and roll for bh
                else:
                    selected_decay = selected_data.iloc[0]

                    r_number_text = f"R-number: {selected_decay.Reading_number}"
                    r_index_text = f"R-index: {selected_decay.Reading_index}"
                    zts = f"ZTS: {selected_decay.ZTS:g}"

                    decay_selection_text.append(r_number_text)
                    decay_selection_text.append(r_index_text)
                    decay_selection_text.append(zts)

                    # Add the time stamp if it exists
                    if not pd.isna(selected_decay.Timestamp):
                        date_time = f"Timestamp: {selected_decay.Timestamp.strftime('%b %d - %H:%M:%S')}"
                        decay_selection_text.append(date_time)

                self.decay_selection_text.setText(' | '.join(decay_selection_text))
                self.decay_selection_text.show()

            # Reset the selection text if nothing is selected
            else:
                self.decay_selection_text.hide()

        if not self.plotted_decay_lines:  # if nothing is plotted in the decay plot
            return

        # Change the color of the plotted lines
        for line, Deleted, overload in zip(self.plotted_decay_lines,
                                           self.decay_data.Deleted,
                                           self.decay_data.Overload):

            # Change the pen if the data is flagged for deletion
            if Deleted is False:
                color = get_line_color("foreground", "pyqt", self.darkmode, alpha=200)
                z_value = 2
            else:
                color = get_line_color("red", "pyqt", self.darkmode, alpha=150)
                z_value = 1

            # Change the line style if the reading is overloaded
            if overload is True:
                style = Qt.DashDotDotLine
            else:
                style = Qt.SolidLine

            # Colors for the lines if they selected
            if line in self.selected_lines:
                if Deleted is False:
                    color = get_line_color("teal", "pyqt", self.darkmode, alpha=250)
                    z_value = 4
                else:
                    color = get_line_color("red", "pyqt", self.darkmode, alpha=200)
                    z_value = 3

                line.setPen(color, width=2, style=style)
                line.setZValue(z_value)
            else:
                # Color the lines that aren't selected
                line.setPen(color, width=1, style=style)
                line.setZValue(z_value)

        set_decay_selection_text(self.get_selected_decay_data())

    def get_selected_decay_data(self):
        """
        Return the corresponding data of the decay lines that are currently selected
        :return: pandas DataFrame
        """
        ind = []
        for line in self.selected_lines:
            if line in self.plotted_decay_lines:
                ind.append(self.plotted_decay_lines.index(line))
        if not ind:
            # print(f"Line is not in the list of decay lines.")
            return
        else:
            data = self.decay_data.iloc[ind]
            return data

    def decay_mouse_moved(self, evt):
        """
        Signal slot, find the decay_axes plot under the mouse when the mouse is moved to determine which plot is active.
        Highlights the decay line closest to the mouse.
        :param evt: MouseMovement event
        """
        def normalize(point):
            """
            Normalize a point so it works as a percentage of the view box data coordinates.
            :param point: QPoint object
            :return: normalized QPointF object
            """
            view = vb.viewRect()
            nx = (point.x() + view.x()) / view.width()
            ny = (point.y() + view.y()) / view.height()
            return QPointF(nx, ny)

        line_distances = []
        ax_lines = [line for line in self.decay_plot.curves if isinstance(line, pg.PlotCurveItem)]
        vb = self.decay_plot.vb

        if not ax_lines:
            return

        # Change the mouse coordinates to be in the plot's native coordinates (not data coordinates)
        m_pos = vb.mapSceneToView(evt)
        m_pos = normalize(m_pos)
        mouse_point = (m_pos.x(), m_pos.y())
        # logger.info(f"Mouse pos: {mouse_point[0]:.2f}, {mouse_point[1]:.2f}")

        for line in ax_lines:
            xi, yi = line.xData, line.yData
            interp_xi = np.linspace(xi.min(), xi.max(), 100)
            interp_yi = np.interp(interp_xi, xi, yi)  # Interp for when the mouse in between two points
            line_qpoints = [normalize(QPointF(x, y)) for x, y in zip(interp_xi, interp_yi)]
            line_points = np.array([(p.x(), p.y()) for p in line_qpoints])

            # logger.info(f"Line data pos: {np.average([p[0] for p in line_points]):.2f}, "
            #             f"{np.average([p[1] for p in line_points]):.2f}")

            # Calculate the distance between each point of the line and the mouse position
            distances = spatial.distance.cdist(np.array([mouse_point]), line_points, metric='euclidean')
            line_distances.append(distances)

        # Find the index of the smallest overall distance
        ind_of_min = np.array([l.min() for l in line_distances]).argmin()
        # logger.info(f"Line {ind_of_min} is nearest the mouse.")

        self.nearest_decay = ax_lines[ind_of_min]
        for line in ax_lines:
            if line == self.nearest_decay:
                line_color = line.opts.get('pen').color()
                line.setShadowPen(pg.mkPen(line_color, width=2.5, cosmetic=True))
            else:
                line.setShadowPen(None)

    def decay_plot_clicked(self, evt):
        """
        Signal slot, change the profile tab to the same component as the clicked decay plot, and select the neareset
        decay line. If control is held, it extends the current selection.
        :param evt: MouseClick event
        """
        if self.nearest_decay:
            self.line_selected = True
            if keyboard.is_pressed('ctrl'):
                self.selected_lines.append(self.nearest_decay)
                self.highlight_lines()
            else:
                self.selected_data = None
                self.selected_lines = [self.nearest_decay]
                self.highlight_lines()
        else:
            logger.warning(f"No nearest decay.")

    def box_select_decay_lines(self, rect):
        """
        Signal slot, select all lines that intersect the drawn rectangle.
        :param rect: QRectF object
        """
        def intersects_rect(line):
            """
            Uses cohen-sutherland algorithm to find if a line intersects the rectangle at any point.
            :param line: pg.PlotCurveItem
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

        # Create the clip window for the line clipping algorithm.
        left, top, right, bottom = min(rect.left(), rect.right()), max(rect.top(), rect.bottom()), \
                                   max(rect.left(), rect.right()), min(rect.top(), rect.bottom())
        curves = [line for line in self.decay_plot.curves if isinstance(line, pg.PlotCurveItem)]
        lines = [line for line in curves if intersects_rect(line)]

        if keyboard.is_pressed('ctrl'):
            self.selected_lines.extend(lines)
        else:
            self.selected_lines = lines
        self.selected_data = None

        self.highlight_lines()
        self.get_selected_decay_data()

    def flip_decays(self):
        """
        Flip the polarity of the decays of the selected data.
        """
        selected_data = self.get_selected_decay_data()

        if not selected_data.empty:
            # Reverse the reading
            selected_data.loc[:, 'Reading'] = selected_data.loc[:, 'Reading'] * -1

            # Update the data in the pem file object
            self.pem_file.data.iloc[selected_data.index] = selected_data
            self.plot_decays(preserve_selection=True)

    def delete_lines(self):
        """
        Delete the selected lines. The data corresponding to the selected lines have their deletion flags flipped
        (i.e. from True > False or False > True). The station is then re-plotted. Line highlight is preserved.
        """
        selected_data = self.get_selected_decay_data()
        if selected_data is None:
            return

        if not selected_data.empty:
            # Change the deletion flag
            selected_data.loc[:, 'Deleted'] = selected_data.loc[:, 'Deleted'].map(lambda x: not x)

            # Update the data in the pem file object
            self.pem_file.data.loc[selected_data.index] = selected_data
            self.plot_decays(preserve_selection=True)

    def undelete_selected_lines(self):
        """
        Undelete the selected lines. The data corresponding to the selected lines have their deletion flags changed to
        False. The station is then re-plotted. Line highlight is preserved.
        """
        selected_data = self.get_selected_decay_data()
        if not selected_data.empty:
            # Change the deletion flag
            selected_data.loc[:, 'Deleted'] = selected_data.loc[:, 'Deleted'].map(lambda x: False)

            # Update the data in the pem file object
            self.pem_file.data.loc[selected_data.index] = selected_data
            self.plot_decays(preserve_selection=True)

    def undelete_all(self):
        """
        Un-delete all deleted readings in the file.
        :return: None
        """
        self.pem_file.data.loc[:, 'Deleted'] = self.pem_file.data.loc[:, 'Deleted'].map(lambda x: False)
        self.plot_decays()

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
            num_plotted = len(self.decay_plot.curves)
            # Find the index of any lines in the current ax that is selected
            index_of_selected = [self.decay_plot.curves.index(line)
                                 for line in self.selected_lines if line in self.decay_plot.curves]
            if index_of_selected:
                old_index = index_of_selected[0]  # Only take the first selected decay
                if old_index == 0:
                    new_index = num_plotted - 1
                else:
                    new_index = old_index - 1
                new_selection.append(self.decay_plot.curves[new_index])
            self.selected_lines = new_selection
            self.highlight_lines()

        # Cycle through highlighted decays forwards
        elif direction == 'up':
            new_selection = []
            # For each decay axes, find any selected lines and cycle to the next line in that axes
            num_plotted = len(self.decay_plot.curves)
            # Find the index of any lines in the current ax that is selected
            index_of_selected = [self.decay_plot.curves.index(line)
                                 for line in self.selected_lines if line in self.decay_plot.curves]
            if index_of_selected:
                old_index = index_of_selected[0]  # Only take the first selected decay
                if old_index < num_plotted - 1:
                    new_index = old_index + 1
                else:
                    new_index = 0
                new_selection.append(self.decay_plot.curves[new_index])
            self.selected_lines = new_selection
            self.highlight_lines()


class DecayViewBox(pg.ViewBox):
    """
    Custom pg.ViewBox for the decay plots. Allows box selecting, box-zoom when shift is held, and mouse wheel when shift
    is held does mouse wheel zoom
    """
    box_select_signal = Signal(object)

    def __init__(self, *args, **kwds):
        pg.ViewBox.__init__(self, *args, **kwds)
        self.setFocusPolicy(Qt.NoFocus)
        # self.setMouseMode(self.RectMode)
        brush = QBrush(QColor('blue'))
        pen = QPen(brush, 1)
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
                self.rbScaleBox.hide()
                ax = QRectF(pg.Point(ev.buttonDownPos(ev.button())), pg.Point(pos))
                ax = self.childGroup.mapRectFromParent(ax)
                self.showAxRect(ax)
                self.axHistoryPointer += 1
                self.axHistory = self.axHistory[:self.axHistoryPointer] + [ax]
            else:
                # update shape of scale box
                self.updateScaleBox(ev.buttonDownPos(), ev.pos())

        else:
            if ev.button() == Qt.LeftButton:
                ev.accept()
                if ev.isFinish():  # This is the final move in the drag
                    # Hide the rectangle
                    self.rbScaleBox.hide()
                    # Create a rectangle object from the click-and-drag rectangle
                    rect = QRectF(pg.Point(ev.buttonDownPos(ev.button())), pg.Point(pos))
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
                return QTransform(inv[0, 0], inv[0, 1], inv[0, 2], inv[1, 0], inv[1, 1], inv[1, 2], inv[2, 0],
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
            center = pg.Point(invertQTransform(self.childGroup.transform()).map(ev.pos()))

            self._resetTarget()
            self.scaleBy(s, center)
            ev.accept()
            self.sigRangeChangedManually.emit(mask)


class ProfileViewBox(pg.ViewBox):
    """
    Custom pg.ViewBox for profile plots. Click and drag creates a linear region selector.
    """
    box_select_signal = Signal(object, object)
    box_select_started_signal = Signal()

    def __init__(self, *args, **kwds):
        pg.ViewBox.__init__(self, *args, **kwds)
        color = '#ce4a7e'
        brush = QBrush(QColor(color))
        pen = QPen(brush, 1)

        self.lr = pg.LinearRegionItem([-100, 100], movable=False, pen=pg.mkPen('k'))
        self.lr.setZValue(-10)
        self.lr.setBrush(brush)
        self.lr.setOpacity(0.5)
        self.lr.hide()
        self.addItem(self.lr)

    def mouseDragEvent(self, ev, axis=None):
        if ev.button() == Qt.LeftButton:
            ev.accept()
            range = [self.mapToView(ev.buttonDownPos()).x(), self.mapToView(ev.pos()).x()]

            # update region of the pg.LinearRegionItem
            self.lr.show()
            # self.lr.setRegion(range)  # Doesn't seem to be required.
            self.box_select_signal.emit(range, ev.start)
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
                return QTransform(inv[0, 0], inv[0, 1], inv[0, 2], inv[1, 0], inv[1, 1], inv[1, 2], inv[2, 0],
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
            center = pg.Point(invertQTransform(self.childGroup.transform()).map(ev.pos()))

            self._resetTarget()
            self.scaleBy(s, center)
            ev.accept()
            self.sigRangeChangedManually.emit(mask)


if __name__ == '__main__':
    from pathlib import Path
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

    samples_folder = Path(__file__).parents[2].joinpath('sample_files')
    pem_g = PEMGetter()

    # file = r"C:\_Data\2021\TMC\Murchison\Barraute B\3000E.PEM"  # Error
    # file = r"C:\_Data\2021\TMC\Murchison\Barraute B\RAW\3000E.PEM"  # No error

    # PP drift testing
    # pem_file = pem_g.parse(samples_folder.joinpath(r"Test PEMS\pp (40 us drift).dmp"))

    # pp_viewer = PPViewer(darkmode=darkmode)
    # # pp_viewer.setWindowState(pp_viewer.windowState() & ~Qt.WindowMinimized | Qt.WindowActive)
    # # pp_viewer.setWindowFlags(Qt.WindowStaysOnTopHint)
    # pp_viewer.show()
    # pp_files = samples_folder.joinpath("PP files").glob("*.*")
    # for pp_file in list(pp_files)[:1]:
    #     print(F"PP file: {pp_file}")
    #     pem_file = pem_g.parse(pp_file)
    #     pp_viewer.open(pem_file)
        # pp_viewer.activateWindow()
        # app.processEvents()
        # input("Press Enter to continue...")

    # pem_file = pem_g.parse(samples_folder.joinpath(r"Test PEMS\pp (eastern drift).dmp2"))

    # pem_file = pem_g.get_pems(folder="Raw Boreholes", file=r"SR-15-04 Z.PEM")[0]
    # pem_file = pem_g.get_pems(folder="Raw Boreholes", file="em21-155 z_0415.PEM")[0]
    # pem_file = pem_g.get_pems(folder="Raw Boreholes", file="XY.PEM")[0]
    # pem_file = pem_g.get_pems(folder="Raw Surface", file=r"Loop L\Final\100E.PEM")[0]
    # pem_file = pem_g.get_pems(folder="Raw Surface", file=r"Loop L\RAW\800E.PEM")[0]
    # pem_file = pem_g.get_pems(folder="Raw Surface", file=r"Loop L\RAW\1200E.PEM")[0]
    pem_file = pem_g.get_pems(folder="Raw Surface", file=r"JHadid\RAW\400n.PEM")[0]
    # pem_file = pem_g.get_pems(folder="Minera", file="L11000N_6.PEM")[0]

    editor = PEMPlotEditor(darkmode=darkmode)
    editor.open(pem_file)
    # editor.actionSplit_Profile.trigger()
    # editor.auto_clean()

    app.exec_()

