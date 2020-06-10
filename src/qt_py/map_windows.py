import os
import re
import sys

import matplotlib.pyplot as plt
import numpy as np
from PyQt5 import (QtGui, uic)
from PyQt5.QtWidgets import (QWidget, QFileDialog,
                             QErrorMessage)
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas, \
    NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

from src.pem.pem_file_editor import PEMFileEditor
from src.pem.pem_plotter import Map3D, Section3D, ContourMap

# Modify the paths for when the script is being run in a frozen state (i.e. as an EXE)
if getattr(sys, 'frozen', False):
    application_path = sys._MEIPASS
    map3DCreatorFile = 'qt_ui\\3D_map.ui'
    section3DCreatorFile = 'qt_ui\\3D_section.ui'
    contourMapCreatorFile = 'qt_ui\\contour_map.ui'
    icons_path = 'icons'
else:
    application_path = os.path.dirname(os.path.abspath(__file__))
    map3DCreatorFile = os.path.join(os.path.dirname(application_path), 'qt_ui\\3D_map.ui')
    section3DCreatorFile = os.path.join(os.path.dirname(application_path), 'qt_ui\\3D_section.ui')
    contourMapCreatorFile = os.path.join(os.path.dirname(application_path), 'qt_ui\\contour_map.ui')
    icons_path = os.path.join(os.path.dirname(application_path), "qt_ui\\icons")

# Load Qt ui file into a class
Ui_Map3DWidget, QtBaseClass = uic.loadUiType(map3DCreatorFile)
Ui_Section3DWidget, QtBaseClass = uic.loadUiType(section3DCreatorFile)
Ui_ContourMapCreatorFile, QtBaseClass = uic.loadUiType(contourMapCreatorFile)


class Map3DViewer(QWidget, Ui_Map3DWidget):
    """
    QWidget window that displays a 3D map (plotted from Map3D) of the PEM Files.
    """

    def __init__(self, pem_files, parent=None):
        super().__init__()
        self.setupUi(self)
        self.pem_files = pem_files
        self.parent = parent
        self.setWindowTitle("3D Map Viewer")
        self.setWindowIcon(QtGui.QIcon(os.path.join(icons_path, '3d_map2.png')))

        self.draw_loops = self.draw_loops_cbox.isChecked()
        self.draw_lines = self.draw_lines_cbox.isChecked()
        self.draw_boreholes = self.draw_boreholes_cbox.isChecked()

        self.label_loops = self.label_loops_cbox.isChecked()
        self.label_lines = self.label_lines_cbox.isChecked()
        self.label_stations = self.label_stations_cbox.isChecked()
        self.label_boreholes = self.label_boreholes_cbox.isChecked()

        self.draw_loops_cbox.toggled.connect(self.toggle_loops)
        self.draw_lines_cbox.toggled.connect(self.toggle_lines)
        self.draw_boreholes_cbox.toggled.connect(self.toggle_boreholes)

        self.label_loops_cbox.toggled.connect(self.toggle_loop_labels)
        self.label_loop_anno_cbox.toggled.connect(self.toggle_loop_anno_labels)
        self.label_lines_cbox.toggled.connect(self.toggle_line_labels)
        self.label_stations_cbox.toggled.connect(self.toggle_station_labels)
        self.label_boreholes_cbox.toggled.connect(self.toggle_borehole_labels)
        self.label_segments_cbox.toggled.connect(self.toggle_segment_labels)

        self.figure = Figure()
        self.canvas = FigureCanvas(self.figure)
        self.map_layout.addWidget(self.canvas)
        self.figure.subplots_adjust(left=-0.1, bottom=-0.1, right=1.1, top=1.1)
        self.ax = self.figure.add_subplot(111, projection='3d')

        # self.toolbar = ContourMapToolbar(self.canvas, self)
        # self.toolbar_layout.addWidget(self.toolbar)
        # self.toolbar.setFixedHeight(30)

        self.map_plotter = Map3D(self.ax, self.pem_files, parent=self)
        self.map_plotter.plot_pems()
        self.map_plotter.format_ax()

        # Show/hide features based on the current state of the checkboxes
        self.update_canvas()

    def update_canvas(self):
        self.toggle_loops()
        self.toggle_lines()
        self.toggle_boreholes()
        self.toggle_loop_labels()
        self.toggle_loop_anno_labels()
        self.toggle_line_labels()
        self.toggle_borehole_labels()
        self.toggle_station_labels()
        self.toggle_segment_labels()
        self.canvas.draw()

    def toggle_loops(self):
        if self.draw_loops_cbox.isChecked():
            for artist in self.map_plotter.loop_artists:
                artist.set_visible(True)
        else:
            for artist in self.map_plotter.loop_artists:
                artist.set_visible(False)
        self.canvas.draw()

    def toggle_lines(self):
        if self.draw_lines_cbox.isChecked():
            for artist in self.map_plotter.line_artists:
                artist.set_visible(True)
        else:
            for artist in self.map_plotter.line_artists:
                artist.set_visible(False)
        self.canvas.draw()

    def toggle_boreholes(self):
        if self.draw_boreholes_cbox.isChecked():
            for artist in self.map_plotter.hole_artists:
                artist.set_visible(True)
        else:
            for artist in self.map_plotter.hole_artists:
                artist.set_visible(False)
        self.canvas.draw()

    def toggle_loop_labels(self):
        if self.label_loops_cbox.isChecked():
            for artist in self.map_plotter.loop_label_artists:
                artist.set_visible(True)
        else:
            for artist in self.map_plotter.loop_label_artists:
                artist.set_visible(False)
        self.canvas.draw()

    def toggle_loop_anno_labels(self):
        if self.label_loop_anno_cbox.isChecked():
            for artist in self.map_plotter.loop_anno_artists:
                artist.set_visible(True)
        else:
            for artist in self.map_plotter.loop_anno_artists:
                artist.set_visible(False)
        self.canvas.draw()

    def toggle_line_labels(self):
        if self.label_lines_cbox.isChecked():
            for artist in self.map_plotter.line_label_artists:
                artist.set_visible(True)
        else:
            for artist in self.map_plotter.line_label_artists:
                artist.set_visible(False)
        self.canvas.draw()

    def toggle_station_labels(self):
        if self.label_stations_cbox.isChecked():
            for artist in self.map_plotter.station_label_artists:
                artist.set_visible(True)
        else:
            for artist in self.map_plotter.station_label_artists:
                artist.set_visible(False)
        self.canvas.draw()

    def toggle_borehole_labels(self):
        if self.label_boreholes_cbox.isChecked():
            for artist in self.map_plotter.hole_label_artists:
                artist.set_visible(True)
        else:
            for artist in self.map_plotter.hole_label_artists:
                artist.set_visible(False)
        self.canvas.draw()

    def toggle_segment_labels(self):
        if self.label_segments_cbox.isChecked():
            for artist in self.map_plotter.segment_label_artists:
                artist.set_visible(True)
        else:
            for artist in self.map_plotter.segment_label_artists:
                artist.set_visible(False)
        self.canvas.draw()

    def closeEvent(self, e):
        self.figure.clear()
        e.accept()


class Section3DViewer(QWidget, Ui_Section3DWidget):
    """
    Displays a 3D vector plot of a borehole. Plots the vector plot itself in 2D, on a plane that is automatically
    calculated
    """

    def __init__(self, pem_file, parent=None):
        super().__init__()
        self.setupUi(self)
        self.pem_file = pem_file
        if not self.pem_file.is_borehole():
            raise TypeError(f'{os.path.basename(self.pem_file.filepath)} is not a borehole file.')
        self.parent = parent
        self.list_points = []

        self.setWindowTitle('3D Section Viewer')
        self.setWindowIcon(QtGui.QIcon(os.path.join(icons_path, 'section_3d.png')))

        self.draw_loop = self.draw_loop_cbox.isChecked()
        self.draw_borehole = self.draw_borehole_cbox.isChecked()
        self.draw_mag_field = self.draw_mag_field_cbox.isChecked()

        self.label_loop = self.label_loop_cbox.isChecked()
        self.label_loop_anno = self.label_loop_anno_cbox.isChecked()
        self.label_borehole = self.label_borehole_cbox.isChecked()

        self.draw_loop_cbox.toggled.connect(self.toggle_loop)
        self.draw_borehole_cbox.toggled.connect(self.toggle_borehole)
        self.draw_mag_field_cbox.toggled.connect(self.toggle_mag_field)

        self.label_loop_cbox.toggled.connect(self.toggle_loop_label)
        self.label_loop_anno_cbox.toggled.connect(self.toggle_loop_anno_labels)
        self.label_borehole_cbox.toggled.connect(self.toggle_borehole_label)
        self.label_segments_cbox.toggled.connect(self.toggle_segment_labels)

        self.figure = Figure()
        self.canvas = FigureCanvas(self.figure)
        # self.canvas.setFocusPolicy(QtCore.Qt.ClickFocus)  # Needed for key-press events
        # self.canvas.setFocus()

        self.map_layout.addWidget(self.canvas)
        self.ax = self.figure.add_subplot(111, projection='3d')

        self.section_plotter = Section3D(self.ax, self.pem_file, parent=self)
        self.section_plotter.plot_3d_magnetic_field()
        self.section_plotter.format_ax()
        self.figure.subplots_adjust(left=-0.1, bottom=-0.1, right=1.1, top=1.1)
        self.update_canvas()

    """
    Not used
        # self.cid_press = self.figure.canvas.mpl_connect('key_press_event', self.mpl_onpress)
        # self.cid_release = self.figure.canvas.mpl_connect('key_release_event', self.mpl_onrelease)

    def mpl_onclick(self, event):

        def get_mouse_xyz():
            x = float(self.ax.format_coord(event.xdata, event.ydata).split(',')[0].strip().split('=')[-1])
            y = float(self.ax.format_coord(event.xdata, event.ydata).split(',')[1].strip().split('=')[-1])
            z = float(self.ax.format_coord(event.xdata, event.ydata).split(',')[2].strip().split('=')[-1])
            return x, y, z

        if plt.get_current_fig_manager().toolbar.mode != '' or event.xdata is None:
            return
        if event.button == 3:
            if self.clickp1 is None:
                self.clickp1 = get_mouse_xyz()
                print(f'P1: {self.ax.format_coord(event.xdata, event.ydata)}')
                self.ax.plot([self.clickp1[0]], [self.clickp1[1]], [self.clickp1[2]], 'ro', label='1')
        #     self.plan_lines.append(self.ax.lines[-1])
                self.canvas.draw()
        #
            elif self.clickp2 is None:
                self.clickp2 = get_mouse_xyz()
                print(f'P2: {self.ax.format_coord(event.xdata, event.ydata)}')
                self.ax.plot([self.clickp2[0]], [self.clickp2[1]], [self.clickp2[2]], 'bo', label='2')
                self.canvas.draw()
            else:
                self.clickp1 = None
                self.clickp2 = None
        #     self.clickp2 = [int(event.xdata), int(event.ydata)]
        #
        #     if self.clickp2 == self.clickp1:
        #         self.clickp1, self.clickp2 = None, None
        #         raise NameError('P1 != P2, reset')
        #
        #     print(f'P2: {self.clickp2}')
        #
        #     self.ax.plot([self.clickp1[0], self.clickp2[0]],
        #                        [self.clickp1[1], self.clickp2[1]], 'r', label='L')
        #     self.plan_lines.append(self.ax.lines[-1])
        #
        #     plt.draw()
        #
        #     print('Plotting section...')

    def mpl_onpress(self, event):
        # print('press ', event.key)
        sys.stdout.flush()
        if event.key == 'control':
            self.cid_click = self.figure.canvas.mpl_connect('button_press_event', self.mpl_onclick)
        elif event.key == 'escape':
            self.clickp1 = None
            self.clickp2 = None

    def mpl_onrelease(self, event):
        # print('release ', event.key)
        if event.key == 'control':
            self.figure.canvas.mpl_disconnect(self.cid_click)
    """

    def update_canvas(self):
        self.toggle_loop()
        self.toggle_borehole()
        self.toggle_mag_field()
        self.toggle_loop_label()
        self.toggle_loop_anno_labels()
        self.toggle_borehole_label()
        self.toggle_segment_labels()

    def toggle_loop(self):
        if self.draw_loop_cbox.isChecked():
            for artist in self.section_plotter.loop_artists:
                artist.set_visible(True)
        else:
            for artist in self.section_plotter.loop_artists:
                artist.set_visible(False)
        self.canvas.draw()

    def toggle_borehole(self):
        if self.draw_borehole_cbox.isChecked():
            for artist in self.section_plotter.hole_artists:
                artist.set_visible(True)
        else:
            for artist in self.section_plotter.hole_artists:
                artist.set_visible(False)
        self.canvas.draw()

    def toggle_mag_field(self):
        if self.draw_mag_field_cbox.isChecked():
            for artist in self.section_plotter.mag_field_artists:
                artist.set_visible(True)
        else:
            for artist in self.section_plotter.mag_field_artists:
                artist.set_visible(False)
        self.canvas.draw()

    def toggle_loop_label(self):
        if self.label_loop_cbox.isChecked():
            for artist in self.section_plotter.loop_label_artists:
                artist.set_visible(True)
        else:
            for artist in self.section_plotter.loop_label_artists:
                artist.set_visible(False)
        self.canvas.draw()

    def toggle_loop_anno_labels(self):
        if self.label_loop_anno_cbox.isChecked():
            for artist in self.section_plotter.loop_anno_artists:
                artist.set_visible(True)
        else:
            for artist in self.section_plotter.loop_anno_artists:
                artist.set_visible(False)
        self.canvas.draw()

    def toggle_borehole_label(self):
        if self.label_borehole_cbox.isChecked():
            for artist in self.section_plotter.hole_label_artists:
                artist.set_visible(True)
        else:
            for artist in self.section_plotter.hole_label_artists:
                artist.set_visible(False)
        self.canvas.draw()

    def toggle_segment_labels(self):
        if self.label_segments_cbox.isChecked():
            for artist in self.section_plotter.segment_label_artists:
                artist.set_visible(True)
        else:
            for artist in self.section_plotter.segment_label_artists:
                artist.set_visible(False)
        self.canvas.draw()

    def closeEvent(self, e):
        self.figure.clear()
        e.accept()


class ContourMapViewer(QWidget, Ui_ContourMapCreatorFile):
    """
    Window that hosts the ContourMap. Filters the given PEMFiles to only include surface surveys. Either all files
    can be un-split, or if there are any split files, it will split the rest. Averages all files.
    """

    def __init__(self, pem_files, parent=None):
        super().__init__()
        self.setupUi(self)
        self.setWindowTitle('Contour Map Viewer')
        self.setWindowIcon(QtGui.QIcon(os.path.join(icons_path, 'contour_map3.png')))
        self.error = QErrorMessage()
        self.file_editor = PEMFileEditor()

        self.cmap = ContourMap()
        self.parent = parent
        self.pem_files = [pem_file for pem_file in pem_files if 'surface' in pem_file.survey_type.lower()]
        # Must be at least 2 eligible surface PEM files.
        if len(self.pem_files) < 2:
            raise TypeError("There are fewer than 2 eligible surface PEM files")

        # Averages any file not already averaged.
        for pem_file in self.pem_files:
            if not pem_file.is_averaged():
                print(f"Averaging {os.path.basename(pem_file.filepath)}")
                pem_file = self.file_editor.average(pem_file)

        # Either all files must be split or all un-split
        if not all([pem_file.is_split() for pem_file in pem_files]):
            for pem_file in self.pem_files:
                print(f"Splitting channels for {os.path.basename(pem_file.filepath)}")
                pem_file = self.file_editor.split_channels(pem_file)

        self.components = [pem_file.get_components() for pem_file in self.pem_files]
        self.components = list(set([item for sublist in self.components for item in sublist]))
        self.components.append('TF')

        # Disables the radio buttons of any component for which there is no data.
        if 'Z' not in self.components:
            self.z_rbtn.setEnabled(False)
            self.z_rbtn.setChecked(False)
        elif 'X' not in self.components:
            self.x_rbtn.setEnabled(False)
            self.x_rbtn.setChecked(False)
        elif 'Y' not in self.components:
            self.y_rbtn.setEnabled(False)
            self.y_rbtn.setChecked(False)

        # Checks the number of channels in each PEM file. The largest number becomes the maximum of the channel spinbox.
        pem_file_channels = np.array([int(pem_file.header.get('NumChannels')) for pem_file in self.pem_files])
        max_channels = pem_file_channels.max()
        self.channel_spinbox.setMaximum(max_channels)

        # Channel pairs created for use when finding the center-gate time of the current selected channel.
        self.channel_times = self.pem_files[np.argmax(pem_file_channels)].header.get('ChannelTimes')
        self.channel_pairs = list(map(lambda x, y: (x, y), self.channel_times[:-1], self.channel_times[1:]))

        # If all files are split, removes the gap channel. Only an issue for split files.
        if all([pem_file.is_split() for pem_file in self.pem_files]):
            # Remove the gap channel for split files
            for i, pair in enumerate(self.channel_pairs):
                if float(pair[0]) >= -0.0001 and float(pair[1]) <= 0.000048:
                    print(f"Removing channel {i} from the channel pairs")
                    self.channel_pairs.pop(i)

        # Signals
        self.channel_spinbox.valueChanged.connect(self.draw_map)
        self.z_rbtn.clicked.connect(self.draw_map)
        self.x_rbtn.clicked.connect(self.draw_map)
        self.y_rbtn.clicked.connect(self.draw_map)
        self.tf_rbtn.clicked.connect(self.draw_map)
        self.plot_loops_cbox.toggled.connect(self.draw_map)
        self.plot_lines_cbox.toggled.connect(self.draw_map)
        self.plot_stations_cbox.toggled.connect(self.draw_map)
        self.label_loops_cbox.toggled.connect(self.draw_map)
        self.label_lines_cbox.toggled.connect(self.draw_map)
        self.label_stations_cbox.toggled.connect(self.draw_map)
        self.plot_elevation_cbox.toggled.connect(self.draw_map)
        self.grid_cbox.toggled.connect(self.draw_map)
        self.title_box_cbox.toggled.connect(self.draw_map)
        self.channel_list_rbtn.toggled.connect(
            lambda: self.channel_list_edit.setEnabled(self.channel_list_rbtn.isChecked()))
        self.save_figure_btn.clicked.connect(self.save_figure)

        self.figure = Figure(figsize=(11, 8.5))
        self.canvas = FigureCanvas(self.figure)
        self.toolbar = ContourMapToolbar(self.canvas, self)
        self.toolbar_layout.addWidget(self.toolbar)
        self.toolbar.setFixedHeight(30)
        self.map_layout.addWidget(self.canvas)
        self.draw_map()

        self.channel_list_edit.setEnabled(False)

    def get_channel_time(self, channel):
        """
        Retrieve the gate-center time of a channel based on the channel times table.
        :param channel: int: channel number
        :return: float: channel center time.
        """
        current_pair = self.channel_pairs[channel]
        channel_center = (float(current_pair[1]) - float(current_pair[0])) / 2 + float(current_pair[0])
        channel_time = channel_center
        return channel_time

    def draw_map(self):

        component = self.get_selected_component().upper()
        if component not in self.components:
            return

        channel = self.channel_spinbox.value()
        channel_time = self.get_channel_time(channel)
        self.time_label.setText(f"{channel_time * 1000:.3f}ms")

        try:
            self.cmap.plot_contour(self.figure, self.pem_files, component, channel,
                                   draw_grid=self.grid_cbox.isChecked(),
                                   channel_time=channel_time,
                                   plot_loops=self.plot_loops_cbox.isChecked(),
                                   plot_lines=self.plot_lines_cbox.isChecked(),
                                   plot_stations=bool(
                                       self.plot_stations_cbox.isChecked() and self.plot_stations_cbox.isEnabled()),
                                   label_lines=bool(
                                       self.label_lines_cbox.isChecked() and self.label_lines_cbox.isEnabled()),
                                   label_loops=bool(
                                       self.label_loops_cbox.isChecked() and self.label_loops_cbox.isEnabled()),
                                   label_stations=bool(
                                       self.label_stations_cbox.isChecked() and self.label_stations_cbox.isEnabled()),
                                   elevation_contours=self.plot_elevation_cbox.isChecked(),
                                   title_box=self.title_box_cbox.isChecked())
        except Exception as e:
            self.error.showMessage(f"The following error occured while creating the contour plot:\n{str(e)}")
        else:
            self.canvas.draw()

    def get_selected_component(self):
        if self.z_rbtn.isChecked():
            return 'Z'
        elif self.x_rbtn.isChecked():
            return 'X'
        elif self.y_rbtn.isChecked():
            return 'Y'
        elif self.tf_rbtn.isChecked():
            return 'TF'

    def save_figure(self):
        """
        Create a PDF with the current selected channel or a list of channels.
        :return: None
        """
        if self.pem_files:
            if __name__ == '__main__':
                path = r"C:\Users\Eric\PycharmProjects\Crone\sample_files\PEMGetter files\test.pdf"
            else:
                default_path = os.path.abspath(self.pem_files[0].filepath)
                path, ext = QFileDialog.getSaveFileName(self, 'Save Figure', default_path,
                                                        'PDF Files (*.PDF);;PNG Files (*.PNG);;JPG Files (*.JPG')
            if path:
                print(f"Saving PDF to {path}")
                with PdfPages(path) as pdf:
                    # Create a figure just for saving, which is cleared after every save and closed at the end
                    save_fig = plt.figure(figsize=(11, 8.5))

                    # Print plots from the list of channels if it's enabled
                    if self.channel_list_edit.isEnabled():
                        text = self.channel_list_edit.text()
                        try:
                            channels = [int(re.match('\d+', text)[0]) for text in re.split(',| ', text)]
                            print(f"Saving contour map plots for channels {channels}")
                        except IndexError:
                            self.error.showMessage(f"No numbers found in the list of channels")
                            return
                    else:
                        channels = [self.channel_spinbox.value()]

                    for channel in channels:
                        channel_time = self.get_channel_time(channel)
                        fig = self.cmap.plot_contour(save_fig, self.pem_files, self.get_selected_component(),
                                                     channel,
                                                     draw_grid=self.grid_cbox.isChecked(),
                                                     channel_time=channel_time,
                                                     plot_loops=self.plot_loops_cbox.isChecked(),
                                                     plot_lines=self.plot_lines_cbox.isChecked(),
                                                     plot_stations=bool(
                                                         self.plot_stations_cbox.isChecked() and self.plot_stations_cbox.isEnabled()),
                                                     label_lines=bool(
                                                         self.label_lines_cbox.isChecked() and self.label_lines_cbox.isEnabled()),
                                                     label_loops=bool(
                                                         self.label_loops_cbox.isChecked() and self.label_loops_cbox.isEnabled()),
                                                     label_stations=bool(
                                                         self.label_stations_cbox.isChecked() and self.label_stations_cbox.isEnabled()),
                                                     elevation_contours=self.plot_elevation_cbox.isChecked(),
                                                     title_box=self.title_box_cbox.isChecked())

                        pdf.savefig(fig, orientation='landscape')
                        save_fig.clear()
                    plt.close(save_fig)
                os.startfile(path)


class ContourMapToolbar(NavigationToolbar):
    """
    Custom Matplotlib toolbar for ContourMap.
    """
    # only display the buttons we need
    toolitems = [t for t in NavigationToolbar.toolitems if
                 t[0] in ('Home', 'Back', 'Forward', 'Pan', 'Zoom')]
