import copy
import logging
import os
import re
import sys
import math

import keyboard
import numpy as np
import pandas as pd
import pylineclip as lc
import pyqtgraph as pg
from pathlib import Path
from PySide2 import QtCore, QtGui
from PySide2.QtUiTools import loadUiType
from PySide2.QtCore import QPointF
from PySide2.QtWidgets import (QApplication, QMainWindow, QInputDialog, QLineEdit, QLabel, QMessageBox, QFileDialog,
                             QPushButton, QShortcut)
from pyqtgraph.Point import Point
from scipy import spatial

from src.pem.pem_file import StationConverter, PEMParser
from src.logger import Log

# from pyod.models.abod import ABOD
# from pyod.models.knn import KNN
# from pyod.utils.data import get_outliers_inliers
logger = logging.getLogger(__name__)

if getattr(sys, 'frozen', False):
    application_path = Path(sys.executable).parent
else:
    application_path = Path(__file__).absolute().parents[1]
icons_path = application_path.joinpath("ui\\icons")

# Load Qt ui file into a class
Ui_PlotEditorWindow, QtBaseClass = loadUiType(str(application_path.joinpath('ui\\pem_plot_editor.ui')))

pg.setConfigOptions(antialias=True)
pg.setConfigOption('background', 'w')
pg.setConfigOption('foreground', 'k')
pg.setConfigOption('crashWarning', True)
pd.options.mode.chained_assignment = None  # default='warn'


class PEMPlotEditor(QMainWindow, Ui_PlotEditorWindow):
    save_sig = QtCore.Signal(object)
    close_sig = QtCore.Signal(object)
    reset_file_sig = QtCore.Signal(object)

    def __init__(self, parent=None):
        super().__init__()
        self.parent = parent
        self.setupUi(self)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.installEventFilter(self)
        self.activateWindow()
        self.setWindowTitle('PEM Plot Editor')
        self.setWindowIcon(QtGui.QIcon(os.path.join(icons_path, 'plot_editor.png')))

        self.resize(1300, 900)

        self.setAcceptDrops(True)
        self.message = QMessageBox()

        # Status bar formatting
        self.station_text = QLabel()
        self.decay_selection_text = QLabel()
        self.decay_selection_text.setIndent(20)
        self.decay_selection_text.setStyleSheet('color: blue')
        self.decay_selection_text.hide()
        self.profile_selection_text = QLabel()
        self.profile_selection_text.setIndent(20)
        self.profile_selection_text.setStyleSheet('color: #ce4a7e')
        # self.profile_selection_text.setStyleSheet('color: purple')
        self.profile_selection_text.hide()
        self.file_info_label = QLabel()
        self.file_info_label.setIndent(20)
        self.file_info_label.setStyleSheet('color: gray')
        self.number_of_readings = QLabel()
        self.number_of_readings.setIndent(20)
        self.number_of_repeats = QPushButton('')
        self.number_of_repeats.setFlat(True)

        # self.setStyleSheet("QStatusBar::item {border-left: 1px solid gray;}")
        # self.status_bar.setStyleSheet("border-top: 1px solid gray;")

        self.status_bar.addWidget(self.station_text, 0)
        self.status_bar.addWidget(self.decay_selection_text, 0)
        self.status_bar.addWidget(QLabel(), 1)  # Spacer
        self.status_bar.addWidget(self.profile_selection_text, 0)
        self.status_bar.addPermanentWidget(self.file_info_label, 0)
        self.status_bar.addPermanentWidget(self.number_of_readings, 0)
        self.status_bar.addPermanentWidget(self.number_of_repeats, 0)

        self.converter = StationConverter()
        self.pem_file = None
        self.fallback_file = None
        self.units = None
        self.stations = np.array([])
        self.mag_df = pd.DataFrame()

        self.line_selected = False
        self.selected_station = None
        self.selected_data = pd.DataFrame()
        self.selected_lines = []
        self.deleted_lines = []
        self.selected_profile_stations = np.array([])
        self.nearest_decay = None
        self.mag_curves = []

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
            ax.vb.installEventFilter(self)
            ax.vb.box_select_signal.connect(self.box_select_decay_lines)
            ax.hideButtons()
            ax.setMenuEnabled(False)
            ax.getAxis('left').enableAutoSIPrefix(enable=False)

            ax.scene().sigMouseMoved.connect(self.decay_mouse_moved)
            ax.scene().sigMouseClicked.connect(self.decay_plot_clicked)

        # Create mag plots
        self.x_profile_layout.ci.layout.setSpacing(5)  # Spacing between plots
        self.mag_x_ax0 = pg.ViewBox()
        self.mag_x_ax1 = pg.ViewBox()
        self.mag_x_ax2 = pg.ViewBox()
        self.mag_x_ax3 = pg.ViewBox()
        self.mag_x_ax4 = pg.ViewBox()

        # Y axis lin plots
        self.y_profile_layout.ci.layout.setSpacing(5)  # Spacing between plots
        self.mag_y_ax0 = pg.ViewBox()
        self.mag_y_ax1 = pg.ViewBox()
        self.mag_y_ax2 = pg.ViewBox()
        self.mag_y_ax3 = pg.ViewBox()
        self.mag_y_ax4 = pg.ViewBox()

        # Z axis lin plots
        self.z_profile_layout.ci.layout.setSpacing(5)  # Spacing between plots
        self.mag_z_ax0 = pg.ViewBox()
        self.mag_z_ax1 = pg.ViewBox()
        self.mag_z_ax2 = pg.ViewBox()
        self.mag_z_ax3 = pg.ViewBox()
        self.mag_z_ax4 = pg.ViewBox()

        self.mag_x_layout_axes = [self.mag_x_ax0, self.mag_x_ax1, self.mag_x_ax2, self.mag_x_ax3, self.mag_x_ax4]
        self.mag_y_layout_axes = [self.mag_y_ax0, self.mag_y_ax1, self.mag_y_ax2, self.mag_y_ax3, self.mag_y_ax4]
        self.mag_z_layout_axes = [self.mag_z_ax0, self.mag_z_ax1, self.mag_z_ax2, self.mag_z_ax3, self.mag_z_ax4]
        self.mag_profile_axes = np.concatenate([self.mag_x_layout_axes, self.mag_y_layout_axes, self.mag_z_layout_axes])

        # Configure the plots
        # X axis lin plots
        self.x_ax0 = self.x_profile_layout.addPlot(0, 0, viewBox=ProfileViewBox())
        self.x_ax1 = self.x_profile_layout.addPlot(1, 0, viewBox=ProfileViewBox())
        self.x_ax2 = self.x_profile_layout.addPlot(2, 0, viewBox=ProfileViewBox())
        self.x_ax3 = self.x_profile_layout.addPlot(3, 0, viewBox=ProfileViewBox())
        self.x_ax4 = self.x_profile_layout.addPlot(4, 0, viewBox=ProfileViewBox())

        # Y axis lin plots
        self.y_ax0 = self.y_profile_layout.addPlot(0, 0, viewBox=ProfileViewBox())
        self.y_ax1 = self.y_profile_layout.addPlot(1, 0, viewBox=ProfileViewBox())
        self.y_ax2 = self.y_profile_layout.addPlot(2, 0, viewBox=ProfileViewBox())
        self.y_ax3 = self.y_profile_layout.addPlot(3, 0, viewBox=ProfileViewBox())
        self.y_ax4 = self.y_profile_layout.addPlot(4, 0, viewBox=ProfileViewBox())

        # Z axis lin plots
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

        def update_views(mag_axes, axes):
            for mag_ax, ax in zip(mag_axes, axes):
                mag_ax.setGeometry(ax.vb.sceneBoundingRect())
                mag_ax.linkedViewChanged(ax.vb, mag_ax.XAxis)

        # Configure each axes, including the mag plots
        for mag_ax, ax in zip(self.mag_profile_axes, self.profile_axes):
            ax.vb.installEventFilter(self)
            ax.vb.box_select_signal.connect(self.box_select_profile_plot)
            ax.hideButtons()
            ax.setMenuEnabled(False)
            ax.getAxis('left').setWidth(60)
            ax.getAxis('left').enableAutoSIPrefix(enable=False)
            ax.getAxis('right').enableAutoSIPrefix(enable=False)

            # Add the vertical selection line
            color = (23, 23, 23, 100)
            font = QtGui.QFont("Helvetica", 10)
            # hover_color = (102, 178, 255, 100)
            # select_color = (51, 51, 255, 100)
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
            # hover_v_line_text.setColor((102, 178, 255, 100))

            ax.addItem(hover_v_line, ignoreBounds=True)
            ax.addItem(hover_v_line_text, ignoreBounds=True)
            ax.addItem(selected_v_line, ignoreBounds=True)

            # Connect the mouse moved signal
            ax.scene().sigMouseMoved.connect(self.profile_mouse_moved)
            ax.scene().sigMouseClicked.connect(self.profile_plot_clicked)

            # Add the mag plot into the profile plot
            ax.showAxis("right")
            ax.scene().addItem(mag_ax)
            mag_ax.setXLink(self.x_ax0)
            ax.getAxis("right").linkToView(mag_ax)
            ax.getAxis("right").setLabel("Total Magnetic Field", color='1DD219', units="pT")
            ax.getAxis("right").setPen(pg.mkPen(color='1DD219'))
            ax.getAxis("right").setTextPen(pg.mkPen(color='1DD219'))

        # Signal for when the view is updated. Required, or else the mag plots aren't placed correctly.
        self.x_ax0.vb.sigResized.connect(lambda: update_views(self.mag_x_layout_axes, self.x_layout_axes))
        self.y_ax0.vb.sigResized.connect(lambda: update_views(self.mag_y_layout_axes, self.y_layout_axes))
        self.z_ax0.vb.sigResized.connect(lambda: update_views(self.mag_z_layout_axes, self.z_layout_axes))

        """Signals"""

        def toggle_mag_plots():
            if self.plot_mag_cbox.isChecked():
                for curve in self.mag_curves:
                    curve.show()
                for ax in self.profile_axes:
                    ax.getAxis("right").show()
            else:
                for curve in self.mag_curves:
                    curve.hide()
                for ax in self.profile_axes:
                    ax.getAxis("right").hide()

        # Shortcuts
        self.actionSave_Screenshot.triggered.connect(self.save_img)
        self.actionCopy_Screenshot.triggered.connect(self.copy_img)

        # Checkboxes
        self.show_average_cbox.toggled.connect(lambda: self.plot_profiles('all'))
        self.show_scatter_cbox.toggled.connect(lambda: self.plot_profiles('all'))
        self.plot_mag_cbox.toggled.connect(toggle_mag_plots)
        self.auto_range_cbox.toggled.connect(self.reset_range)
        self.plot_ontime_decays_cbox.toggled.connect(lambda: self.plot_station(self.selected_station,
                                                                               preserve_selection=True))
        self.plot_ontime_decays_cbox.toggled.connect(lambda: self.active_decay_axes[0].autoRange())

        self.link_y_cbox.toggled.connect(self.link_decay_y)
        self.link_x_cbox.toggled.connect(self.link_decay_x)

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

        # Menu
        self.actionOpen.triggered.connect(self.open_file_dialog)
        self.actionSave.triggered.connect(self.save)
        self.actionSave_As.triggered.connect(self.save_as)

    def keyPressEvent(self, event):
        # Delete a decay when the delete key is pressed
        if event.key() == QtCore.Qt.Key_Delete or event.key() == QtCore.Qt.Key_R:
            if keyboard.is_pressed("shift"):
                self.undelete_lines()
            else:
                self.delete_lines()

        elif event.key() == QtCore.Qt.Key_C:
            self.cycle_profile_component()

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
                self.flip_decays(source='decay')

        # Change the component of the readings to X
        elif event.key() == QtCore.Qt.Key_X:
            if self.selected_lines:
                self.change_component('X', source='decay')

        # Change the component of the readings to Y
        elif event.key() == QtCore.Qt.Key_Y:
            if self.selected_lines:
                self.change_component('Y', source='decay')

        # Change the component of the readings to Z
        elif event.key() == QtCore.Qt.Key_Z:
            if self.selected_lines:
                self.change_component('Z', source='decay')

        # Reset the ranges of the plots when the space bar is pressed
        elif event.key() == QtCore.Qt.Key_Space:
            if keyboard.is_pressed('Shift'):
                self.zoom_to_offtime()
            else:
                self.reset_range()

        # Clear the selected decays when the Escape key is pressed
        elif event.key() == QtCore.Qt.Key_Escape:
            self.clear_selection()

    def eventFilter(self, watched, event):
        if event.type() == QtCore.QEvent.GraphicsSceneWheel:
            # print(f"Wheel event")
            self.pyqtgraphWheelEvent(event)
            return True
        elif event.type() == QtCore.QEvent.Close:
            event.accept()
            self.deleteLater()
        return super().eventFilter(watched, event)

    def pyqtgraphWheelEvent(self, evt):
        y = evt.delta()
        if y < 0:
            self.cycle_station('down')
        else:
            self.cycle_station('up')

    def wheelEvent(self, evt):
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

        self.fallback_file = pem_file.copy()
        self.pem_file = pem_file
        self.setWindowTitle(f"PEM Plot Editor' - {pem_file.filepath.name}")

        file_info = ' | '.join([f"Timebase: {self.pem_file.timebase:.2f}ms",
                                f"{self.pem_file.get_survey_type()} Survey",
                                f"Operator: {self.pem_file.operator.title()}"
                                ])
        self.file_info_label.setText(file_info)
        # self.timebase_label.setText(f"Timebase: {self.pem_file.timebase:.2f}ms")
        # self.survey_type_label.setText(f"{self.pem_file.get_survey_type()} Survey")
        # self.operator_label.setText(f"Operator: {self.pem_file.operator.title()}")

        if self.pem_file.is_split():
            # self.plot_ontime_decays_cbox.setChecked(False)  # Triggers the signal
            self.plot_ontime_decays_cbox.setEnabled(False)
        else:
            self.plot_ontime_decays_cbox.setEnabled(True)

        # Plot the mag profile if available. Disable the plot mag button if it's not applicable.
        if self.pem_file.is_borehole() and self.pem_file.has_xy():
            self.mag_df = self.pem_file.get_mag()
            if self.mag_df.Mag.any():
                self.plot_mag_cbox.setEnabled(True)
                # Save the mag curves so they can be toggled easily.
                self.mag_curves = []
                x, y = self.mag_df.Station.to_numpy(), self.mag_df.Mag.to_numpy()
                for ax in self.mag_profile_axes:
                    mag_plot_item = pg.PlotCurveItem(x=x, y=y, pen=pg.mkPen('1DD219', width=2.))
                    ax.addItem(mag_plot_item)
                    self.mag_curves.append(mag_plot_item)
            else:
                self.plot_mag_cbox.setChecked(False)
                self.plot_mag_cbox.setEnabled(False)
        else:
            self.plot_mag_cbox.setChecked(False)
            self.plot_mag_cbox.setEnabled(False)

        # Set the units of the decay plots
        self.units = self.pem_file.units
        if self.units == 'pT':
            self.auto_clean_std_sbox.setValue(50)
        else:
            self.auto_clean_std_sbox.setValue(10)

        # Add the line name and loop name as the title for the profile plots
        self.x_ax0.setTitle(f"{self.pem_file.line_name} - Loop {self.pem_file.loop_name}\n[X Component]")
        self.y_ax0.setTitle(f"{self.pem_file.line_name} - Loop {self.pem_file.loop_name}\n[Y Component]")
        self.z_ax0.setTitle(f"{self.pem_file.line_name} - Loop {self.pem_file.loop_name}\n[Z Component]")

        # Set the X and Y axis labels for the decay axes
        for ax in self.decay_axes:
            ax.setLabel('left', f"Response", units=self.units)
            ax.setLabel('bottom', 'Channel number')

        # Plot the LIN profiles
        self.plot_profiles(components='all')
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
        self.pem_file.data = self.pem_file.data[~self.pem_file.data.Deleted.astype(bool)]
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
                if x_ax not in self.active_decay_axes:
                    self.active_decay_axes.append(x_ax)
            else:
                x_ax.hide()
                if x_ax in self.active_decay_axes:
                    self.active_decay_axes.remove(x_ax)

            if 'Y' in components:
                y_ax.show()
                # self.profile_tab_widget.setTabEnabled(1, True)
                if y_ax not in self.active_decay_axes:
                    self.active_decay_axes.append(y_ax)
            else:
                y_ax.hide()
                if y_ax in self.active_decay_axes:
                    self.active_decay_axes.remove(y_ax)

            if 'Z' in components:
                z_ax.show()
                if z_ax not in self.active_decay_axes:
                    self.active_decay_axes.append(z_ax)
            else:
                z_ax.hide()
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

            # Add or remove axes from the list of active profile axes
            if 'X' in components:
                if all([ax not in self.active_profile_axes for ax in self.x_layout_axes]):
                    self.active_profile_axes.extend(self.x_layout_axes)
            else:
                for ax in self.x_layout_axes:
                    if ax in self.active_profile_axes:
                        self.active_profile_axes.remove(ax)

                # Cycle to the next profile plot component if this component is no longer in the data but it's
                # the current profile selected
                if self.profile_tab_widget.currentIndex() == 0:
                    print(f"X profile selected but there's no X data, cycling to the next component")
                    self.cycle_profile_component()

            if 'Y' in components:
                if all([ax not in self.active_profile_axes for ax in self.y_layout_axes]):
                    self.active_profile_axes.extend(self.y_layout_axes)
            else:
                for ax in self.y_layout_axes:
                    if ax in self.active_profile_axes:
                        self.active_profile_axes.remove(ax)

                if self.profile_tab_widget.currentIndex() == 1:
                    print(f"Y profile selected but there's no Y data, cycling to the next component")
                    self.cycle_profile_component()

            if 'Z' in components:
                if all([ax not in self.active_profile_axes for ax in self.z_layout_axes]):
                    self.active_profile_axes.extend(self.z_layout_axes)
            else:
                for ax in self.z_layout_axes:
                    if ax in self.active_profile_axes:
                        self.active_profile_axes.remove(ax)

                if self.profile_tab_widget.currentIndex() == 2:
                    print(f"Z profile selected but there's no Z data, cycling to the next component")
                    self.cycle_profile_component()

            link_profile_axes()

        # Update the list of stations
        self.stations = np.sort(self.pem_file.get_stations(converted=True))

        # Select a new selected station if it no longer exists
        if self.selected_station not in self.stations:
            self.selected_station = self.stations[0]

        # Re-calculate the converted station numbers
        self.pem_file.data['cStation'] = self.pem_file.data.Station.map(self.converter.convert_station)

        # Re-set the limits of the profile plots
        for ax in self.profile_axes:
            ax.setLimits(xMin=self.pem_file.data.cStation.min() - 1, xMax=self.pem_file.data.cStation.max() + 1)

        repeats = self.pem_file.get_repeats()
        self.number_of_repeats.setText(f'{len(repeats)} repeat(s)')
        if len(repeats) > 0:
            self.number_of_repeats.setStyleSheet('color: red')
        else:
            self.number_of_repeats.setStyleSheet('color: black')

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

    def reset_range(self):
        """
        Auto range all axes
        """
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

        stations = self.pem_file.get_stations(converted=True)
        for ax in self.profile_axes:
            ax.autoRange()
            ax.setXRange(stations.min(), stations.max())

        # self.active_profile_axes[0].autoRange()

    def zoom_to_offtime(self):
        """
        Change the Y limits of the decay plots to be zoomed on the late off-time channels.
        """
        filt = self.pem_file.data.cStation == self.selected_station
        channel_mask = ~self.pem_file.channel_times.Remove
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

        def plot_lin(profile_data, axes):

            def plot_lines(df, ax):
                """
                Plot the lines on the pyqtgraph ax
                :param df: DataFrame of filtered data
                :param ax: pyqtgraph PlotItem
                """
                df_avg = df.groupby('Station').mean()
                x, y = df_avg.index, df_avg

                ax.plot(x=x, y=y,
                        pen=pg.mkPen('k', width=1.),
                        symbol='o',
                        symbolSize=2,
                        symbolBrush='k',
                        symbolPen='k',
                        )

            def plot_scatters(df, ax):
                """
                Plot the scatter plot markers
                :param df: DataFrame of filtered data
                :param ax: pyqtgraph PlotItem
                :return:
                """
                x, y = df.index, df

                scatter = pg.ScatterPlotItem(x=x, y=y,
                                             pen=pg.mkPen('k', width=1.),
                                             symbol='o',
                                             size=2,
                                             brush='w',
                                             )

                ax.addItem(scatter)

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

        self.update_file()

        file = copy.deepcopy(self.pem_file)
        file.data = file.data.loc[~file.data.Deleted.astype(bool)]

        self.number_of_readings.setText(f"{len(file.data)} reading(s)")

        if not isinstance(components, np.ndarray):
            # Get the components
            if components is None or components == 'all':
                components = file.get_components()

        # Clear the plots of the components that are to be plotted only
        clear_plots(components)

        # Calculate the lin plot axes channel bounds
        channel_bounds = file.get_channel_bounds()

        for component in components:
            profile_data = file.get_profile_data(component,
                                                 averaged=False,
                                                 converted=True,
                                                 ontime=False,
                                                 incl_deleted=True).dropna()
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
                color = (96, 96, 96, 150)
                z_value = 2
            else:
                color = (255, 0, 0, 50)
                z_value = 1

            if row.Overload is True:
                style = QtCore.Qt.DashDotDotLine
            else:
                style = QtCore.Qt.SolidLine

            pen = pg.mkPen(color, width=1., style=style)

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
            selected_v_line = ax.items[2]  # Clicked vertical station line
            selected_v_line.setPos(station)

        index_of_selected = []
        # Keep the same lines highlighted after data modification
        if preserve_selection is False:
            self.selected_lines.clear()
        else:
            index_of_selected = [self.plotted_decay_lines.index(line) for line in self.selected_lines]

        # Clear the plots
        for ax in self.decay_axes:
            ax.clear()

        self.plotted_decay_lines.clear()
        self.plotted_decay_data = None  # Not actually necessary
        self.nearest_decay = None

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
                y = len(self.pem_file.channel_times[~self.pem_file.channel_times.Remove])

            ax.setLimits(minXRange=0, maxXRange=y - 1,
                         xMin=0, xMax=y - 1)

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

    def toggle_mag(self):
        if self.plot_mag_cbox.isEnabled():
            mag_df = self.pem_file.get_mag()
            if mag_df.Mag.any():
                self.mag_x_ax0.plot(x=mag_df.Station, y=mag_df.Mag, pen=pg.mkPen('g', width=3.))
            else:
                logger.info(f"{self.pem_file.name} RAD tool cannot calculate magnetic field strength.")

    def highlight_lines(self):
        """
        Highlight the line selected and un-highlight any previously highlighted line.
        :param lines: list, PlotItem lines
        """

        def set_decay_selection_text(selected_data):
            """
            Update the status bar with information about the selected lines
            """
            if self.selected_lines:
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
                    timestamp = selected_decay.Timestamp
                    if timestamp is not None:
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
            self.change_decay_suffix_btn.setEnabled(True)
            self.change_station_decay_btn.setEnabled(True)
            self.flip_decay_btn.setEnabled(True)
        else:
            self.change_comp_decay_btn.setEnabled(False)
            self.change_decay_suffix_btn.setEnabled(False)
            self.change_station_decay_btn.setEnabled(False)
            self.flip_decay_btn.setEnabled(False)

        # Change the color of the plotted lines
        for line, Deleted, overload in zip(self.plotted_decay_lines, self.plotted_decay_data.Deleted,
                                           self.plotted_decay_data.Overload):

            # Change the pen if the data is flagged for deletion
            if Deleted is False:
                color = (96, 96, 96, 150)
                z_value = 2
            else:
                color = (255, 0, 0, 100)
                z_value = 1

            # Change the line style if the reading is overloaded
            if overload is True:
                style = QtCore.Qt.DashDotDotLine
            else:
                style = QtCore.Qt.SolidLine

            # Colors for the lines if they selected
            if line in self.selected_lines:
                if Deleted is False:
                    color = (85, 85, 255, 200)  # Blue
                    # color = (153, 85, 204, 200)  # Purple
                    z_value = 4
                else:
                    color = (255, 0, 0, 150)
                    z_value = 3
                    # pen_color = (204, 0, 204)  # Magenta ish
                    # pen_color = (153, 51, 255)  # Puple

                line.setPen(color, width=2, style=style)
                line.setZValue(z_value)
            # Color the lines that aren't selected
            else:
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

        # Hide the LinearRegionItem in each profile axes
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

    # @Log()
    def find_nearest_station(self, x):
        """
        Calculate the nearest station from the position x
        :param x: int, mouse x location
        :return: int, station number
        """
        idx = (np.abs(self.stations - x)).argmin()
        return self.stations[idx]

    def profile_mouse_moved(self, evt):
        """
        Signal slot, when the mouse is moved in one of the axes. Calculates and plots a light blue vertical line at the
        nearest station where the mouse is.
        :param evt: pyqtgraph MouseClickEvent
        """

        global nearest_station
        pos = evt
        mouse_point = self.active_profile_axes[0].vb.mapSceneToView(pos)
        nearest_station = self.find_nearest_station(int(mouse_point.x()))

        for ax in self.active_profile_axes:
            ax.items[0].setPos(nearest_station)  # Move the hover line
            ax.items[1].setPos(nearest_station, ax.viewRange()[1][1])  # Move the hover text
            # Change the anchor of the text for the later stations so they don't get clipped
            if len(self.stations) > 1 and nearest_station in self.stations[-math.floor(len(self.stations) / 2):]:
                ax.items[1].setAnchor((1, 0))
            else:
                ax.items[1].setAnchor((0, 0))
            ax.items[1].setText(str(nearest_station))  # Chang text to the be the station number

    def profile_plot_clicked(self, evt):
        """
        Signal slot, when the profile plot is clicked. Plots a darker blue vertical line at the nearest station where
        the click was made and plots that station's decays in the decay plot, and remove any selection.
        Uses the nearest station calculated in self.profile_mouse_moved.
        :param evt: pyqtgraph MouseClickEvent (not used)
        """
        self.selected_station = nearest_station
        self.plot_station(nearest_station)

        # Hide any profile box-selection
        for ax in self.profile_axes:
            ax.vb.lr.hide()

    def decay_line_clicked(self, line):
        """
        Signal slot, select the decay line that was clicked. If control is held, it extends the current selection.
        :param line: clicked PlotItem line
        """
        pass
        # self.line_selected = True
        # if keyboard.is_pressed('ctrl'):
        #     self.selected_lines.append(line)
        #     self.highlight_lines()
        # else:
        #     self.selected_data = None
        #     self.selected_lines = [line]
        #     self.highlight_lines()

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

    def decay_mouse_moved(self, evt):
        """
        Signal slot, find the decay_axes plot under the mouse when the mouse is moved to determine which plot is active.
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

        # Find which axes is beneath the mouse
        for ax in self.decay_axes:
            if ax.vb.childGroup.sceneBoundingRect().contains(evt):
                self.active_ax = ax
                self.last_active_ax = ax
                self.active_ax_ind = np.where(self.decay_axes == self.active_ax)[0][0]
                self.last_active_ax_ind = self.active_ax_ind
                break

        if self.active_ax is not None:
            line_distances = []
            ax_lines = self.active_ax.curves
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
        self.get_selected_decay_data()

    def box_select_profile_plot(self, range, start):
        """
        Signal slot, select stations from the profile plot when click-and-dragged
        :param range: tuple, range of the linearRegionItem
        :param start: bool, if box select has just been started
        """
        """
        Using the range given by the signal doesn't always work properly when the click begins off-plot. 
        """
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

        ind, comp = self.get_active_component()
        comp_profile_axes = self.get_component_profile(comp)
        comp_stations = self.pem_file.data[self.pem_file.data.Component == comp].Station
        comp_stations = np.array([self.converter.convert_station(s) for s in comp_stations])

        # Update the LinearRegionItem for each axes of the current component
        for ax in comp_profile_axes:
            ax.vb.lr.setRegion((x0, x1))
            ax.vb.lr.show()

        # Find the stations that fall within the selection range
        self.selected_profile_stations = comp_stations[
            np.where((comp_stations <= x1) & (comp_stations >= x0))]

        # Enable the edit buttons and set the profile selection text
        if self.selected_profile_stations.any():
            self.change_comp_profile_btn.setEnabled(True)
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

    def get_component_profile(self, comp):
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
        ind = [self.plotted_decay_lines.index(line) for line in self.selected_lines]
        data = self.plotted_decay_data.iloc[ind]
        return data

    def get_selected_profile_data(self):
        """
        Return the corresponding data of the currently selected stations from the profile plots
        :return: pandas DataFrame
        """
        ind, comp = self.get_active_component()

        df = self.pem_file.data
        filt = ((df.Component == comp) &
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

    def delete_lines(self):
        """
        Delete the selected lines. The data corresponding to the selected lines have their deletion flags flipped
        (i.e. from True > False or False > True). The station is then re-plotted. Line highlight is preserved.
        """
        selected_data = self.get_selected_decay_data()
        if not selected_data.empty:
            # Change the deletion flag
            selected_data.loc[:, 'Deleted'] = selected_data.loc[:, 'Deleted'].map(lambda x: not x)

            # Update the data in the pem file object
            self.pem_file.data.loc[selected_data.index] = selected_data
            self.plot_profiles(components=selected_data.Component.unique())
            self.plot_station(self.selected_station, preserve_selection=True)

    def undelete_lines(self):
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
            self.plot_profiles(components=selected_data.Component.unique())
            self.plot_station(self.selected_station, preserve_selection=True)

    def change_decay_component_dialog(self, source=None):
        """
        Open a user input window to select the new component to change to.
        :param source: str, either 'decay' or 'profile' to signify which data to modify
        """
        if not source:
            logger.warning(f"No source selected.")
            return

        new_comp, ok_pressed = QInputDialog.getText(self, "Change Component", "New Component:", QLineEdit.Normal)
        if ok_pressed:
            new_comp = new_comp.upper()
            if new_comp not in ['X', 'Y', 'Z']:
                self.message.information(self, 'Invalid Component', 'The component must be one of X, Y, Z.')
                return
            else:
                self.change_component(new_comp, source=source)

    def change_component(self, new_component, source=None):
        """
        Change the component of the selected data
        :param new_component: str
        :param source: str, either 'decay' or 'profile' to know which selected data to modify
        """
        if source == 'decay':
            selected_data = self.get_selected_decay_data()
        else:
            selected_data = self.get_selected_profile_data()

        old_comp = selected_data.Component.unique()[0]

        if not selected_data.empty and new_component != old_comp:
            # Change the deletion flag
            selected_data.loc[:, 'Component'] = selected_data.loc[:, 'Component'].map(lambda x: new_component.upper())

            # Update the data in the pem file object
            self.pem_file.data.iloc[selected_data.index] = selected_data
            self.plot_profiles(components=[old_comp, new_component])
            self.plot_station(self.selected_station, preserve_selection=True)

    def change_suffix_dialog(self, source=None):
        """
        Open a user input window to select the new station suffix to change to.
        :param source: str, must be in ['N', 'E', 'S', 'W']
        """
        if not source:
            logger.warning(f"No source selected.")
            return

        new_suffix, ok_pressed = QInputDialog.getText(self, "Change Suffix", "New Suffix:")
        if ok_pressed:
            new_suffix = new_suffix.upper()
            if new_suffix not in ['N', 'E', 'S', 'W']:
                self.message.information(self, 'Invalid Suffix', 'The suffix must be one of N, E, S, W.')
                return
            else:
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
        self.plot_profiles(components='all')
        self.plot_station(self.selected_station, preserve_selection=True)

    def change_station(self):
        """
        Opens a input dialog to change the station name of the selected data.
        """
        if self.selected_lines:
            selected_data = self.get_selected_decay_data()
            selected_station = selected_data.Station.unique()[0]

            new_station, ok_pressed = QInputDialog.getText(self, "Change Station", "New Station:", QLineEdit.Normal,
                                                           selected_station)
            if ok_pressed:
                new_station = new_station.upper()
                if re.match(r'-?\d+', new_station):
                    # Update the station number in the selected data
                    selected_data.loc[:, 'Station'] = new_station
                    # Update the data in the pem file object
                    self.pem_file.data.iloc[selected_data.index] = selected_data

                    # Update the plots
                    self.plot_profiles(components=selected_data.Component.unique())
                    self.plot_station(self.selected_station)

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
        shift_amount, ok_pressed = QInputDialog.getInt(self, "Shift Stations", "Shift Amount:",
                                                       value=0,
                                                       min=-9999,
                                                       max=9999,
                                                       )
        if ok_pressed and shift_amount != 0:
            # Update the station number in the selected data
            selected_data.loc[:, 'Station'] = selected_data.loc[:, 'Station'].map(shift)
            # Update the data in the pem file object
            self.pem_file.data.iloc[selected_data.index] = selected_data

            # Update the plots
            self.plot_profiles(components=selected_data.Component.unique())
            self.plot_station(self.selected_station)

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
            self.plot_profiles(components=selected_data.Component.unique())
            self.plot_station(self.selected_station, preserve_selection=True)

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
            self.plot_profiles(components=selected_data.Component.unique())
            self.plot_station(self.selected_station, preserve_selection=True)

    def cycle_profile_component(self):
        """
        Signal slot, cycle through the profile plots
        """

        def get_comp_indexes():
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

        comp_indexes = get_comp_indexes()
        current_ind = self.profile_tab_widget.currentIndex()
        if len(comp_indexes) > 1:
            if current_ind + 1 > max(comp_indexes):
                new_ind = min(comp_indexes)
            else:
                new_ind = comp_indexes[comp_indexes.index(current_ind) + 1]
        elif comp_indexes[0] != current_ind:
            new_ind = comp_indexes[0]
        else:
            return
        print(f"Cycling profile tab to {new_ind}")
        self.profile_tab_widget.setCurrentIndex(new_ind)

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
                self.plot_station(self.stations[new_ind], preserve_selection=False)
        elif direction == 'up':
            if station_index == 0:
                return
            else:
                # Force the new index to be a different station then the one selected
                new_ind = station_index
                while self.stations[new_ind] == self.selected_station and new_ind > 0:
                    new_ind -= 1
                self.plot_station(self.stations[new_ind], preserve_selection=False)

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
                if local_count < max_removable:
                    # First pass, using 96% confidence interval
                    min_cutoff = median[mask] - std[mask] * 2
                    max_cutoff = median[mask] + std[mask] * 2
                    if any(reading[mask] < min_cutoff) or any(reading[mask] > max_cutoff):
                        count += 1
                        local_count += 1
                        return True
                else:
                    logger.info(f"Max removable limit reached.")
                if local_count < max_removable:
                    # Second pass, looking at the last 3 off-time channels, and using 68% confidence interval
                    min_cutoff = median[mask][-3:] - std[mask][-3:]
                    max_cutoff = median[mask][-3:] + std[mask][-3:]
                    if any(reading[mask][-3:] < min_cutoff) or any(reading[mask][-3:] > max_cutoff):
                        count += 1
                        local_count += 1
                        return True
                else:
                    logger.info(f"Max removable limit reached.")

                return False

            readings = np.array(group.Reading.to_list())
            data_std = np.array([threshold_value] * len(readings[0]))
            data_median = np.median(readings, axis=0)

            if len(group.loc[~group.Deleted.astype(bool)]) > 2:
                global local_count
                local_count = 0  # The number of readings that have been deleted so far for this group.
                max_removable = len(group) - 2  # Maximum number of readings that are allowed to be deleted.
                group.Deleted = group.Reading.map(lambda x: eval_decay(x, data_std, data_median, max_removable))

            return group

        if self.pem_file.is_averaged():
            return

        global count, mask, threshold_value
        count = 0

        # Use a fixed standard deviation value for cleaning across all channels
        threshold_value = self.auto_clean_std_sbox.value()

        # Filter the data to only see readings that aren't already flagged for deletion
        data = self.pem_file.data[~self.pem_file.data.Deleted.astype(bool)]
        # Filter the readings to only consider off-time channels
        mask = np.asarray(~self.pem_file.channel_times.Remove)
        # Clean the data
        cleaned_data = data.groupby(['Station', 'Component']).apply(clean_group)
        # Update the data
        self.pem_file.data[~self.pem_file.data.Deleted.astype(bool)] = cleaned_data

        # Plot the new data
        self.plot_profiles(components='all')
        self.plot_station(self.selected_station)

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
            station_num = re.search('\d+', station).group()
            if station_num[-1] == '1' or station_num[-1] == '6':
                station_num = str(int(station_num) - 1)
            elif station_num[-1] == '4' or station_num[-1] == '9':
                station_num = str(int(station_num) + 1)

            new_station = re.sub('\d+', station_num, station)
            return new_station

        repeats = self.pem_file.get_repeats()
        if repeats.empty:
            return

        # Rename the stations
        repeats.Station = repeats.Station.map(auto_rename_repeats)
        self.pem_file.data.loc[repeats.index] = repeats

        # Plot the new data
        self.plot_profiles(components='all')
        self.plot_station(self.selected_station, preserve_selection=False)

        self.message.information(self, 'Auto-rename results', f"{len(repeats)} reading(s) automatically renamed.")

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


class DecayViewBox(pg.ViewBox):
    """
    Custom ViewBox for the decay plots. Allows box selecting, box-zoom when shift is held, and mouse wheel when shift
    is held does mouse wheel zoom
    """
    box_select_signal = QtCore.Signal(object)

    def __init__(self, *args, **kwds):
        pg.ViewBox.__init__(self, *args, **kwds)
        self.setFocusPolicy(QtCore.Qt.NoFocus)
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
    box_select_signal = QtCore.Signal(object, object)
    box_select_started_signal = QtCore.Signal()

    def __init__(self, *args, **kwds):
        pg.ViewBox.__init__(self, *args, **kwds)
        color = r'#ce4a7e'
        brush = QtGui.QBrush(QtGui.QColor(color))
        pen = QtGui.QPen(brush, 1)

        self.lr = pg.LinearRegionItem([-100, 100], movable=False, pen=pg.mkPen('k'))
        self.lr.setZValue(-10)
        self.lr.setBrush(brush)
        self.lr.setOpacity(0.5)
        self.lr.hide()
        self.addItem(self.lr)

    def mouseDragEvent(self, ev, axis=None):
        if ev.button() == QtCore.Qt.LeftButton:
            ev.accept()
            range = [self.mapToView(ev.buttonDownPos()).x(), self.mapToView(ev.pos()).x()]

            # update region of the LinearRegionItem
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
    # from pyqtgraph.Qt import QtGui, QtCore

    from src.pem.pem_getter import PEMGetter
    from src.pem.pem_file import PEMParser, DMPParser
    from pathlib import Path

    samples_folder = Path(__file__).parents[2].joinpath('sample_files')

    app = QApplication(sys.argv)
    pem_getter = PEMGetter()
    parser = PEMParser()
    dmp_parser = DMPParser()
    # pem_files = pem_getter.get_pems(random=True, number=1)

    # pem_files = [parser.parse(r'C:\Users\Mortulo\Downloads\Data\Dump\September 16, 2020\DMP\pp-coil.PEM')]
    # pem_files, errors = dmp_parser.parse_dmp2(r'C:\_Data\2020\Raglan\Surface\West Boundary\RAW\xyz_25.DMP2')
    # pem_file = parser.parse(samples_folder.joinpath(r'TMC holes\1338-18-19\RAW\XY_16.PEM'))
    # pem_file = pem_getter.get_pems(client="PEM Rotation", random=True, number=1)[0]
    pem_file = pem_getter.get_pems(client="TMC", random=True, number=1)[0]

    editor = PEMPlotEditor()
    # editor.move(0, 0)
    editor.open(pem_file)
    # editor.auto_clean()

    app.exec_()

