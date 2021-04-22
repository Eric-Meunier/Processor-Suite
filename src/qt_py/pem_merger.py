import logging
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyqtgraph as pg
from PyQt5 import uic, QtCore, QtGui
from PyQt5.QtWidgets import (QApplication, QMainWindow, QFrame, QLineEdit, QLabel, QMessageBox, QFileDialog,
                             QPushButton, QAction, QHBoxLayout)

from src.pem.pem_file import StationConverter

logger = logging.getLogger(__name__)

if getattr(sys, 'frozen', False):
    application_path = os.path.dirname(sys.executable)
    mergerCreatorFile = 'ui\\pem_merger.ui'
    icons_path = 'ui\\icons'
else:
    application_path = os.path.dirname(os.path.abspath(__file__))
    mergerCreatorFile = os.path.join(os.path.dirname(application_path), 'ui\\pem_merger.ui')
    icons_path = os.path.join(os.path.dirname(application_path), "ui\\icons")

# Load Qt ui file into a class
Ui_PlotMergerWindow, QtBaseClass = uic.loadUiType(mergerCreatorFile)

pg.setConfigOptions(antialias=True)
pg.setConfigOption('background', 'w')
pg.setConfigOption('foreground', 'k')
pg.setConfigOption('crashWarning', True)
pd.options.mode.chained_assignment = None  # default='warn'


class PEMMerger(QMainWindow, Ui_PlotMergerWindow):
    accept_sig = QtCore.pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__()
        self.parent = parent
        self.setupUi(self)
        self.installEventFilter(self)
        self.message = QMessageBox()

        # Format window
        self.setWindowTitle('PEM Merger')
        self.setWindowIcon(QtGui.QIcon(os.path.join(icons_path, 'pem_merger.png')))

        self.converter = StationConverter()
        self.pf1 = None
        self.pf2 = None
        self.units = None
        self.components = []
        self.channel_bounds = None
        self.last_scale_factor_1 = 0.
        self.last_scale_factor_2 = 0.
        self.last_soa_1 = 0.
        self.last_soa_2 = 0.

        self.menuView.addSeparator()
        self.view_x_action = QAction('X Component')
        self.view_y_action = QAction('Y Component')
        self.view_z_action = QAction('Z Component')

        # Status bar
        self.save_frame = QFrame()
        self.save_frame.setLayout(QHBoxLayout())
        self.save_frame.layout().setContentsMargins(0, 0, 0, 0)

        self.save_path_label = QLabel('Save Path:')
        self.save_path_edit = QLineEdit()
        self.accept_btn = QPushButton('Accept')

        self.save_frame.layout().addWidget(self.save_path_label)
        self.save_frame.layout().addWidget(self.save_path_edit)
        self.save_frame.layout().addWidget(self.accept_btn)
        # self.accept_btn.setFlat(True)

        self.status_bar.addPermanentWidget(self.save_frame)
        # self.status_bar.addPermanentWidget(self.save_path_label)
        # self.status_bar.addPermanentWidget(self.save_path_edit)
        # self.status_bar.addPermanentWidget(self.accept_btn)

        # Configure the plots
        # X axis lin plots
        self.x_profile_layout.ci.layout.setSpacing(3)  # Spacing between plots
        self.x_ax0 = self.x_profile_layout.addPlot(0, 0)
        self.x_ax1 = self.x_profile_layout.addPlot(1, 0)
        self.x_ax2 = self.x_profile_layout.addPlot(2, 0)
        self.x_ax3 = self.x_profile_layout.addPlot(3, 0)
        self.x_ax4 = self.x_profile_layout.addPlot(4, 0)
        self.pf1_x_curves = []
        self.pf2_x_curves = []

        # Y axis lin plots
        self.y_profile_layout.ci.layout.setSpacing(3)  # Spacing between plots
        self.y_ax0 = self.y_profile_layout.addPlot(0, 0)
        self.y_ax1 = self.y_profile_layout.addPlot(1, 0)
        self.y_ax2 = self.y_profile_layout.addPlot(2, 0)
        self.y_ax3 = self.y_profile_layout.addPlot(3, 0)
        self.y_ax4 = self.y_profile_layout.addPlot(4, 0)
        self.pf1_y_curves = []
        self.pf2_y_curves = []

        # Z axis lin plots
        self.z_profile_layout.ci.layout.setSpacing(3)  # Spacing between plots
        self.z_ax0 = self.z_profile_layout.addPlot(0, 0)
        self.z_ax1 = self.z_profile_layout.addPlot(1, 0)
        self.z_ax2 = self.z_profile_layout.addPlot(2, 0)
        self.z_ax3 = self.z_profile_layout.addPlot(3, 0)
        self.z_ax4 = self.z_profile_layout.addPlot(4, 0)
        self.pf1_z_curves = []
        self.pf2_z_curves = []

        self.x_layout_axes = [self.x_ax0, self.x_ax1, self.x_ax2, self.x_ax3, self.x_ax4]
        self.y_layout_axes = [self.y_ax0, self.y_ax1, self.y_ax2, self.y_ax3, self.y_ax4]
        self.z_layout_axes = [self.z_ax0, self.z_ax1, self.z_ax2, self.z_ax3, self.z_ax4]

        self.profile_axes = np.concatenate([self.x_layout_axes, self.y_layout_axes, self.z_layout_axes])

        # Configure each axes
        for ax in self.profile_axes:
            ax.setXLink(self.x_ax0)
            ax.hideButtons()
            ax.setMenuEnabled(False)
            ax.getAxis('left').setWidth(60)
            ax.getAxis('left').enableAutoSIPrefix(enable=False)

        self.init_signals()

    def init_signals(self):

        def toggle_symbols():
            self.plot_profiles(self.pf1, components='all')
            self.plot_profiles(self.pf2, components='all')

        def coil_area_1_changed(coil_area):
            self.pf1 = self.pf1.scale_coil_area(coil_area)
            self.plot_profiles(self.pf1, components='all')

        def coil_area_2_changed(coil_area):
            self.pf2 = self.pf2.scale_coil_area(coil_area)
            self.plot_profiles(self.pf2, components='all')

        def current_1_changed(current):
            self.pf1 = self.pf1.scale_current(current)
            self.plot_profiles(self.pf1, components='all')

        def current_2_changed(current):
            self.pf2 = self.pf2.scale_current(current)
            self.plot_profiles(self.pf2, components='all')

        def factor_1_changed(factor):
            scale_factor = factor - self.last_scale_factor_1

            self.pf1 = self.pf1.scale_by_factor(scale_factor)
            self.plot_profiles(self.pf1, components='all')

            self.last_scale_factor_1 = factor

        def factor_2_changed(factor):
            scale_factor = factor - self.last_scale_factor_2

            self.pf2 = self.pf2.scale_by_factor(scale_factor)
            self.plot_profiles(self.pf2, components='all')

            self.last_scale_factor_2 = factor

        def soa_1_changed(soa):
            soa_delta = soa - self.last_soa_1

            self.pf1 = self.pf1.rotate_soa(soa_delta)
            self.plot_profiles(self.pf1, components='all')

            self.last_soa_1 = soa

        def soa_2_changed(soa):
            soa_delta = soa - self.last_soa_2

            self.pf2 = self.pf2.rotate_soa(soa_delta)
            self.plot_profiles(self.pf2, components='all')

            self.last_soa_2 = soa

        def flip_component(pem_file):
            ind = self.profile_tab_widget.currentIndex()
            if ind == 0:
                component = 'X'
            elif ind == 1:
                component = 'Y'
            else:
                component = 'Z'

            filt = pem_file.data.Component == component

            if filt.any():
                data = pem_file.data[filt]

                data.loc[:, 'Reading'] = data.loc[:, 'Reading'] * -1

                pem_file.data[filt] = data

                self.plot_profiles(pem_file, component)

        def accept_merge():
            merged_pem = self.get_merged_pem()
            save_path = Path(self.save_path_edit.text())

            merged_pem.filepath = save_path
            merged_pem.save()
            self.status_bar.showMessage(f"File saved.", 1000)
            self.accept_sig.emit(str(save_path))
            self.close()

        # Menu
        self.actionSave_As.triggered.connect(self.save_pem_file)
        self.actionSave_Screenshot.triggered.connect(self.save_img)
        self.actionCopy_Screenshot.triggered.connect(self.copy_img)

        self.actionSymbols.triggered.connect(toggle_symbols)

        self.view_x_action.triggered.connect(lambda: self.profile_tab_widget.setCurrentIndex(0))
        self.view_y_action.triggered.connect(lambda: self.profile_tab_widget.setCurrentIndex(1))
        self.view_z_action.triggered.connect(lambda: self.profile_tab_widget.setCurrentIndex(2))

        # Spin boxes
        self.coil_area_sbox_1.valueChanged.connect(coil_area_1_changed)
        self.coil_area_sbox_2.valueChanged.connect(coil_area_2_changed)

        self.current_sbox_1.valueChanged.connect(current_1_changed)
        self.current_sbox_2.valueChanged.connect(current_2_changed)

        self.factor_sbox_1.valueChanged.connect(factor_1_changed)
        self.factor_sbox_2.valueChanged.connect(factor_2_changed)

        self.soa_sbox_1.valueChanged.connect(soa_1_changed)
        self.soa_sbox_2.valueChanged.connect(soa_2_changed)

        # Buttons
        self.flip_data_btn_1.clicked.connect(lambda: flip_component(self.pf1))
        self.flip_data_btn_2.clicked.connect(lambda: flip_component(self.pf2))

        self.accept_btn.clicked.connect(accept_merge)

    def keyPressEvent(self, event):
        # Delete a decay when the delete key is pressed
        if event.key() == QtCore.Qt.Key_C:
            self.cycle_profile_component()

        elif event.key() == QtCore.Qt.Key_Space:
            self.reset_range()

    def eventFilter(self, watched, event):
        if event.type() == QtCore.QEvent.Close:
            self.deleteLater()
        return super().eventFilter(watched, event)

    def reset_range(self):
        for ax in self.profile_axes:
            ax.autoRange()

    def open(self, pem_files):
        """
        Open a PEMFile object and plot the data.
        :param pem_files: list, 2 PEMFile objects.
        """

        def format_plots():
            """
            Creates plot curves for each channel of each component. Adds plot labels for the Y axis and title of
            the profile plots, and sets the X axis limits of each plot.
            """

            def set_plot_labels(axes):
                """
                Plot the Y axis label for the plot.
                :param axes: list of PlotItem plots for a component.
                """

                # Set the plot labels
                for i, bounds in enumerate(self.channel_bounds):
                    ax = axes[i]
                    # Set the Y-axis labels
                    if i == 0:
                        ax.setLabel('left', f"PP channel", units=self.units)
                    else:
                        ax.setLabel('left', f"Channel {bounds[0]} to {bounds[1]}", units=self.units)

            def add_plot_curves(axes, *item_lists):
                """
                Create and add the PlotCurveItems to the correct PlotItem.
                :param axes: list of plot axes for a component
                :param item_lists: list of PlotCurveItems for each PEMFile.
                """
                for item_list in item_lists:
                    for channel in range(self.channel_bounds[0][0], self.channel_bounds[-1][-1] + 1):
                        curve = pg.PlotDataItem()
                        item_list.append(curve)

                        # Add the curve to the correct plot
                        ax = self.get_ax(channel, axes)
                        ax.addItem(curve)

            profile_page_set = False
            stations = np.concatenate([self.pf1.get_stations(converted=True), self.pf2.get_stations(converted=True)])
            mn, mx = stations.min(), stations.max()

            if 'X' in self.components:
                # Add the line name and loop name as the title for the profile plots
                self.x_ax0.setTitle(f"X Component")
                # Add the PlotCurveItems
                add_plot_curves(self.x_layout_axes, *[self.pf1_x_curves, self.pf2_x_curves])

                # Add the plot XY labels
                for ax in self.x_layout_axes:
                    ax.setLimits(xMin=mn, xMax=mx)

                set_plot_labels(self.x_layout_axes)

                self.profile_tab_widget.setCurrentIndex(0)
                profile_page_set = True
            else:
                self.profile_tab_widget.setCurrentIndex(1)

            if 'Y' in self.components:
                # Add the line name and loop name as the title for the profile plots
                self.y_ax0.setTitle(f"Y Component")
                # Add the PlotCurveItems
                add_plot_curves(self.y_layout_axes, *[self.pf1_y_curves, self.pf2_y_curves])

                # Add the plot XY labels
                for ax in self.y_layout_axes:
                    ax.setLimits(xMin=mn, xMax=mx)

                set_plot_labels(self.y_layout_axes)

                if not profile_page_set:
                    self.profile_tab_widget.setCurrentIndex(1)
                    profile_page_set = True
            else:
                self.profile_tab_widget.setCurrentIndex(2)

            if 'Z' in self.components:
                # Add the line name and loop name as the title for the profile plots
                self.z_ax0.setTitle(f"Z Component")
                # Add the PlotCurveItems
                add_plot_curves(self.z_layout_axes, *[self.pf1_z_curves, self.pf2_z_curves])

                # Add the plot XY labels
                for ax in self.z_layout_axes:
                    ax.setLimits(xMin=mn, xMax=mx)

                set_plot_labels(self.z_layout_axes)

                if not profile_page_set:
                    self.profile_tab_widget.setCurrentIndex(2)

        def set_file_information():
            """
            Set the information labels for both PEMFiles.
            """

            def check_label_differences():
                for l1, l2 in zip([self.client_label_1,
                                   self.grid_label_1,
                                   self.line_label_1,
                                   self.loop_label_1,
                                   self.operator_label_1,
                                   self.tools_label_1,
                                   self.date_label_1,
                                   self.ramp_label_1,
                                   self.rx_num_label_1,
                                   self.sync_label_1,
                                   self.zts_label_1,
                                   ],
                                  [self.client_label_1,
                                   self.grid_label_2,
                                   self.line_label_2,
                                   self.loop_label_2,
                                   self.operator_label_2,
                                   self.tools_label_2,
                                   self.date_label_2,
                                   self.ramp_label_2,
                                   self.rx_num_label_2,
                                   self.sync_label_2,
                                   self.zts_label_2,
                                   ]
                                  ):
                    if l1.text() != l2.text():
                        l1_font = l1.font()
                        l2_font = l2.font()

                        # l1_font.setUnderline(True)
                        # l2_font.setUnderline(True)
                        l1_font.setBold(True)
                        l2_font.setBold(True)

                        l1.setFont(l1_font)
                        l2.setFont(l2_font)

            self.coil_area_sbox_1.blockSignals(True)
            self.coil_area_sbox_2.blockSignals(True)
            self.soa_sbox_1.blockSignals(True)
            self.current_sbox_1.blockSignals(True)
            self.current_sbox_2.blockSignals(True)
            self.soa_sbox_2.blockSignals(True)

            self.file_label_1.setText(self.pf1.filepath.name)
            self.client_label_1.setText(self.pf1.client)
            self.grid_label_1.setText(self.pf1.grid)
            self.line_label_1.setText(self.pf1.line_name)
            self.loop_label_1.setText(self.pf1.loop_name)
            self.operator_label_1.setText(self.pf1.operator)
            self.tools_label_1.setText(' '.join(self.pf1.probes.values()))

            self.date_label_1.setText(self.pf1.date)
            self.ramp_label_1.setText(str(self.pf1.ramp))
            self.rx_num_label_1.setText(self.pf1.rx_number)
            self.sync_label_1.setText(self.pf1.sync)
            self.zts_label_1.setText(', '.join(self.pf1.data.ZTS.astype(str).unique()))

            self.coil_area_sbox_1.setValue(float(self.pf1.coil_area))
            self.current_sbox_1.setValue(float(self.pf1.current))
            self.soa_sbox_1.setValue(float(self.pf1.get_soa()))

            self.file_label_2.setText(self.pf2.filepath.name)
            self.client_label_2.setText(self.pf2.client)
            self.grid_label_2.setText(self.pf2.grid)
            self.line_label_2.setText(self.pf2.line_name)
            self.loop_label_2.setText(self.pf2.loop_name)
            self.operator_label_2.setText(self.pf2.operator)
            self.tools_label_2.setText(' '.join(self.pf2.probes.values()))

            self.date_label_2.setText(self.pf2.date)
            self.ramp_label_2.setText(str(self.pf2.ramp))
            self.rx_num_label_2.setText(self.pf2.rx_number)
            self.sync_label_2.setText(self.pf2.sync)
            self.zts_label_2.setText(', '.join(self.pf1.data.ZTS.astype(str).unique()))

            self.coil_area_sbox_2.setValue(float(self.pf2.coil_area))
            self.current_sbox_2.setValue(float(self.pf2.current))
            self.soa_sbox_2.setValue(float(self.pf2.get_soa()))

            self.coil_area_sbox_1.blockSignals(False)
            self.coil_area_sbox_2.blockSignals(False)
            self.soa_sbox_1.blockSignals(False)
            self.current_sbox_1.blockSignals(False)
            self.current_sbox_2.blockSignals(False)
            self.soa_sbox_2.blockSignals(False)

            check_label_differences()

        def set_buttons():
            """
            Enable the Flip Component buttons
            """
            for pem_file in [self.pf1, self.pf2]:
                components = pem_file.get_components()

                if 'X' in components:
                    self.menuView.addAction(self.view_x_action)

                if 'Y' in components:
                    self.menuView.addAction(self.view_y_action)

                if 'Z' in components:
                    self.menuView.addAction(self.view_z_action)

        assert len(pem_files) == 2, f"PEMMerger exclusively accepts two PEM files."
        f1, f2 = pem_files[0], pem_files[1]
        assert f1.is_borehole() == f2.is_borehole(), f"Cannot merge a borehole survey with a surface survey."
        assert f1.is_fluxgate() == f2.is_fluxgate(), f"Cannot merge a fluxgate survey with an induction survey."
        assert f1.timebase == f2.timebase, f"Both files must have the same timebase."
        assert f1.number_of_channels == f2.number_of_channels, f"Both files must have the same number of channels."

        # Enable the SOA spin boxes if the file is a borehole file and has XY component data
        if all([f1.is_borehole(), f1.has_xy()]):
            self.soa_sbox_1.setEnabled(True)
        if all([f2.is_borehole(), f2.has_xy()]):
            self.soa_sbox_2.setEnabled(True)

        # Try and ensure the files are plotted in the correct order
        f1_min, f2_min = f1.get_stations(converted=True).min(), f2.get_stations(converted=True).min()
        if f1_min < f2_min:
            self.pf1 = f1
            self.pf2 = f2
        else:
            self.pf1 = f2
            self.pf2 = f1

        if self.pf1.is_fluxgate():
            self.units = 'pT'
        else:
            self.units = 'nT/s'

        self.components = np.unique(np.hstack(np.array([self.pf1.get_components(), self.pf2.get_components()],
                                                       dtype=object)))
        self.channel_bounds = self.pf1.get_channel_bounds()

        format_plots()
        set_file_information()
        set_buttons()
        self.save_path_edit.setText(str(self.pf1.filepath.with_name(f"{self.pf1.line_name}.PEM")))

        # Plot the LIN profiles
        self.plot_profiles(self.pf1, components='all')
        self.plot_profiles(self.pf2, components='all')
        self.reset_range()
        self.show()

    def plot_profiles(self, pem_file, components=None):
        """
        Plot the PEM file in a LIN plot style, with both components in separate plots
        :param pem_file: PEMFile object to plot.
        :param components: list of str, components to plot. If None it will plot every component in the file.
        """

        def plot_lines(channel):
            """
            Average and plot the data of the channel.
            :param channel: int, channel number
            """
            channel_number = channel.name
            df_avg = channel.groupby('Station').mean()
            x, y = df_avg.index.to_numpy(), df_avg.to_numpy()

            curve = self.get_curve(channel_number, component, pem_file)

            if self.actionSymbols.isChecked():
                symbols = {'symbol': 'o',
                           'symbolSize': 5,
                           'symbolPen': pg.mkPen(color, width=1.1),
                           'symbolBrush': pg.mkBrush('w')}
            else:
                symbols = {'symbol': None}

            curve.setData(x, y, pen=pg.mkPen(color), **symbols)

        if not isinstance(components, np.ndarray):
            # Get the components
            if components is None or components == 'all':
                components = self.components

        if pem_file == self.pf1:
            # color = 'r'
            color = (28, 28, 27)
        else:
            # color = 'b'
            color = (206, 74, 126)

        for component in components:
            profile_data = pem_file.get_profile_data(component,
                                                     averaged=False,
                                                     converted=True,
                                                     ontime=False,
                                                     incl_deleted=False)

            if profile_data.empty:
                continue

            profile_data.apply(plot_lines)

    def get_ax(self, channel, axes):
        """
        Find which plot the channel should be plotted in.
        :param channel: int, channel number
        :param axes: list, pg PlotItems
        :return: pg PlotItem
        """
        for i, bound in enumerate(self.channel_bounds):
            if channel in range(bound[0], bound[1] + 1):
                return axes[i]

    def get_curve(self, channel, component, pem_file):
        """
        Find the PlotCurveItem for a given channel, component and PEMFile
        :param channel: int
        :param component: str
        :param pem_file: PEMFile object
        """
        if component == 'X':
            if pem_file == self.pf1:
                return self.pf1_x_curves[channel]
            else:
                return self.pf2_x_curves[channel]
        if component == 'Y':
            if pem_file == self.pf1:
                return self.pf1_y_curves[channel]
            else:
                return self.pf2_y_curves[channel]
        else:
            if pem_file == self.pf1:
                return self.pf1_z_curves[channel]
            else:
                return self.pf2_z_curves[channel]

    def get_merged_pem(self):
        """
        Merge the two PEM files into a single PEM file.
        :return: single PEMFile object
        """
        pems = [self.pf1, self.pf2]
        merged_pem = pems[0].copy()
        merged_pem.data = pd.concat([pem_file.data for pem_file in pems], axis=0, ignore_index=True)
        merged_pem.number_of_readings = sum([f.number_of_readings for f in pems])
        merged_pem.is_merged = True

        return merged_pem

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
            if 'X' in self.components:
                indexes.append(0)
            if 'Y' in self.components:
                indexes.append(1)
            if 'Z' in self.components:
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

        self.profile_tab_widget.setCurrentIndex(new_ind)

    def save_pem_file(self):
        default_name = str(self.pf1.filepath.with_name(f"{self.pf1.line_name}.PEM"))
        save_path = QFileDialog.getSaveFileName(self, 'Save PEM File',
                                                default_name,
                                                'PEM Files (*.PEM)')[0]
        if save_path:
            merged_pem = self.get_merged_pem()
            merged_pem.filepath = Path(save_path)
            merged_pem.save()

    def save_img(self):
        default = self.pf1.filepath.parent.joinpath(f"{self.pf1.filepath.stem} & {self.pf2.filepath.stem}")
        save_file = QFileDialog.getSaveFileName(self, 'Save Image',
                                                str(default),
                                                'PNG Files (*.PNG)')[0]
        if save_file:
            self.grab().save(save_file)

    def copy_img(self):
        QApplication.clipboard().setPixmap(self.grab())
        self.status_bar.showMessage('Image copied to clipboard.', 1000)


if __name__ == '__main__':
    from src.pem.pem_getter import PEMGetter
    app = QApplication(sys.argv)

    pem_getter = PEMGetter()
    # pem_files = pem_getter.get_pems(client='Minera', number=2)
    pf1 = pem_getter.get_pems(folder='Raw Boreholes', file='em10-10xy_0403.PEM')[0]
    pf2 = pem_getter.get_pems(folder='Raw Boreholes', file='em10-10-2xy_0403.PEM')[0]
    # pf1 = pem_getter.get_pems(client='Kazzinc', file='MANO-19-004 XYT.PEM')[0]
    # pf2 = pem_getter.get_pems(client='Kazzinc', file='MANO-19-004 ZAv.PEM')[0]
    # pf1 = pem_getter.get_pems(client='Iscaycruz', subfolder='PZ-19-05', file='CXY_02.PEM')[0]
    # pf2 = pem_getter.get_pems(client='Iscaycruz', subfolder='PZ-19-05', file='CXY_03.PEM')[0]
    w = PEMMerger()
    w.open([pf1, pf2])

    w.show()

    app.exec_()
