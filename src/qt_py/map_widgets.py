import io
import os
import re
import sys
import time

import folium
# import matplotlib.backends.backend_tkagg  # Needed for pyinstaller, or receive  ImportError
import matplotlib.pyplot as plt
import numpy as np
import plotly
import plotly.graph_objects as go
from PyQt5 import (QtGui)
from PyQt5 import uic
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtWidgets import (QErrorMessage, QApplication, QWidget, QShortcut, QFileDialog, QMessageBox, QGridLayout,
                             QAction, QMainWindow)
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas, \
    NavigationToolbar2QT as NavigationToolbar

from src.pem.pem_plotter import ContourMap


# Modify the paths for when the script is being run in a frozen state (i.e. as an EXE)
if getattr(sys, 'frozen', False):
    application_path = sys._MEIPASS
    section3DCreatorFile = 'qt_ui\\3D_section.ui'
    contourMapCreatorFile = 'qt_ui\\contour_map.ui'
    icons_path = 'icons'
else:
    application_path = os.path.dirname(os.path.abspath(__file__))
    section3DCreatorFile = os.path.join(os.path.dirname(application_path), 'qt_ui\\3D_section.ui')
    contourMapCreatorFile = os.path.join(os.path.dirname(application_path), 'qt_ui\\contour_map.ui')
    icons_path = os.path.join(os.path.dirname(application_path), "qt_ui\\icons")

# Load Qt ui file into a class
Ui_Section3DWidget, QtBaseClass = uic.loadUiType(section3DCreatorFile)
Ui_ContourMapCreatorFile, QtBaseClass = uic.loadUiType(contourMapCreatorFile)


sys._excepthook = sys.excepthook


def exception_hook(exctype, value, traceback):
    print(exctype, value, traceback)
    sys._excepthook(exctype, value, traceback)
    sys.exit(1)


sys.excepthook = exception_hook


class Map3DViewer(QMainWindow):

    def __init__(self, parent=None):
        super().__init__()
        self.pem_files = None
        self.parent = parent

        self.loops = []
        self.lines = []
        self.collars = []
        self.holes = []
        self.annotations = []

        self.setWindowTitle("3D Map Viewer")
        self.setWindowIcon(QtGui.QIcon(os.path.join(icons_path, '3d_map2.png')))
        self.resize(1000, 800)
        layout = QGridLayout()
        self.setLayout(layout)

        self.save_img_action = QAction('Save Image')
        self.save_img_action.setShortcut("Ctrl+S")
        self.save_img_action.triggered.connect(self.save_img)
        self.copy_image_action = QAction('Copy Image')
        self.copy_image_action.setShortcut("Ctrl+C")
        self.copy_image_action.triggered.connect(self.copy_img)

        self.file_menu = self.menuBar().addMenu('&File')
        self.file_menu.addAction(self.save_img_action)
        self.file_menu.addAction(self.copy_image_action)

        self.figure = go.Figure()
        self.figure.update_layout(scene=dict(
            xaxis_title='EASTING',
            yaxis_title='NORTHING',
            zaxis_title='ELEVATION',
            aspectmode='data'),
            margin=dict(r=0, b=0, l=0, t=0),
        )

        # create an instance of QWebEngineView and set the html code
        self.plot_widget = QWebEngineView()
        self.setCentralWidget(self.plot_widget)

    def open(self, pem_files):
        if not isinstance(pem_files, list):
            pem_files = [pem_files]
        self.pem_files = pem_files
        self.plot_pems()
        self.show()

    def plot_pems(self):
        if not self.pem_files:
            return

        def reset_figure():
            self.figure.data = []
            self.loops = []
            self.lines = []
            self.collars = []
            self.holes = []

        def plot_loop(pem_file):
            t = time.time()

            loop = pem_file.get_loop(closed=True)
            if loop.to_string() not in self.loops:
                self.loops.append(loop.to_string())

                # Plot the loop in the figure
                self.figure.add_trace(go.Scatter3d(x=loop.Easting,
                                                   y=loop.Northing,
                                                   z=loop.Elevation,
                                                   legendgroup='loop',
                                                   mode='lines',
                                                   name=f"Loop {pem_file.loop_name}",
                                                   text=loop.index))

            print(f"Time to add loop trace: {time.time() - t}")

        def plot_line(pem_file):
            t = time.time()
            line = pem_file.get_line()

            if line.to_string() not in self.lines:
                self.lines.append(line.to_string())
                # Plot the line in the figure
                self.figure.add_trace(go.Scatter3d(x=line.Easting,
                                                   y=line.Northing,
                                                   z=line.Elevation,
                                                   legendgroup='line',
                                                   mode='lines+markers',
                                                   name=pem_file.line_name,
                                                   text=line.Station
                                                   ))

                # if self.label_stations_cbox.isChecked():
                #     for row in line.itertuples():
                #         self.annotations.append(dict(x=row.Easting,
                #                                      y=row.Northing,
                #                                      z=row.Elevation,
                #                                      ax=0,
                #                                      ay=0,
                #                                      text=row.Station,
                #                                      showarrow=False,
                #                                      xanchor="center",
                #                                      yanchor="bottom"))

                print(f"Time to add line trace: {time.time() - t}")

        def plot_hole(pem_file):
            t = time.time()
            collar = pem_file.get_collar().dropna()
            geometry = pem_file.get_geometry()
            proj = geometry.get_projection()

            if not proj.empty:
                if proj.to_string() not in self.holes:
                    self.holes.append(proj.to_string())
                    # Plot the line in the figure
                    self.figure.add_trace(go.Scatter3d(x=proj.Easting,
                                                       y=proj.Northing,
                                                       z=proj.Elevation,
                                                       mode='lines+markers',
                                                       legendgroup='hole',
                                                       name=pem_file.line_name,
                                                       text=proj['Relative_depth']
                                                       ))

                else:
                    return

            elif not collar.empty and collar.to_string() not in self.collars:
                self.collars.append(collar.to_string())
                self.figure.add_trace(go.Scatter3d(x=collar.Easting,
                                                   y=collar.Northing,
                                                   z=collar.Elevation,
                                                   # legendgroup='hole',
                                                   name=pem_file.line_name,
                                                   text=pem_file.line_name
                                                   ))

            print(f"Time to add line trace: {time.time() - t}")

        reset_figure()

        # Plot the PEMs
        for pem_file in self.pem_files:
            plot_loop(pem_file)

            if not pem_file.is_borehole():
                plot_line(pem_file)

            else:
                plot_hole(pem_file)

        # Set the style of the markers and lines
        self.figure.update_traces(marker=dict(size=6,
                                              line=dict(width=2,
                                                        color='DarkSlateGrey')),
                                  line=dict(width=4)
                                  )
        # TODO Format the axis ticks
        self.figure.update_layout(yaxis_tickformat='%')

        # Create the HTML
        html = '<html><body>'
        html += plotly.offline.plot(self.figure,
                                    output_type='div',
                                    include_plotlyjs='cdn',
                                    config={'displayModeBar': False}
                                    )
        html += '</body></html>'

        t2 = time.time()
        # Add the plot HTML to be shown in the plot widget
        self.plot_widget.setHtml(html)
        print(f'Time to set HTML: {time.time() - t2}')

    def save_img(self):
        save_file = QFileDialog.getSaveFileName(self, 'Save Image', 'map.png', 'PNG Files (*.PNG);; All files(*.*)')[0]

        if save_file:
            size = self.contentsRect()
            img = QtGui.QPixmap(size.width(), size.height())
            self.render(img)
            img.save(save_file)
        else:
            pass

    def copy_img(self):
        size = self.contentsRect()
        img = QtGui.QPixmap(size.width(), size.height())
        self.render(img)
        img.copy(size)
        QApplication.clipboard().setPixmap(img)


# class Section3DViewer(QWidget, Ui_Section3DWidget):
#     """
#     Displays a 3D vector plot of a borehole. Plots the vector plot itself in 2D, on a plane that is automatically
#     calculated
#     """
#
#     def __init__(self, pem_file, parent=None):
#         super().__init__()
#         self.setupUi(self)
#         self.pem_file = pem_file
#         if not self.pem_file.is_borehole():
#             raise TypeError(f'{os.path.basename(self.pem_file.filepath)} is not a borehole file.')
#         self.parent = parent
#         self.list_points = []
#
#         self.setWindowTitle('3D Section Viewer')
#         self.setWindowIcon(QtGui.QIcon(os.path.join(icons_path, 'section_3d.png')))
#
#         self.draw_loop = self.draw_loop_cbox.isChecked()
#         self.draw_borehole = self.draw_borehole_cbox.isChecked()
#         self.draw_mag_field = self.draw_mag_field_cbox.isChecked()
#
#         self.label_loop = self.label_loop_cbox.isChecked()
#         self.label_loop_anno = self.label_loop_anno_cbox.isChecked()
#         self.label_borehole = self.label_borehole_cbox.isChecked()
#
#         self.draw_loop_cbox.toggled.connect(self.toggle_loop)
#         self.draw_borehole_cbox.toggled.connect(self.toggle_borehole)
#         self.draw_mag_field_cbox.toggled.connect(self.toggle_mag_field)
#
#         self.label_loop_cbox.toggled.connect(self.toggle_loop_label)
#         self.label_loop_anno_cbox.toggled.connect(self.toggle_loop_anno_labels)
#         self.label_borehole_cbox.toggled.connect(self.toggle_borehole_label)
#         self.label_segments_cbox.toggled.connect(self.toggle_segment_labels)
#
#         self.figure = Figure()
#         self.canvas = FigureCanvas(self.figure)
#         # self.canvas.setFocusPolicy(QtCore.Qt.ClickFocus)  # Needed for key-press events
#         # self.canvas.setFocus()
#
#         self.map_layout.addWidget(self.canvas)
#         self.ax = self.figure.add_subplot(111, projection='3d')
#
#         self.section_plotter = Section3D(self.ax, self.pem_file, parent=self)
#         self.section_plotter.plot_3d_magnetic_field()
#         self.section_plotter.format_ax()
#         self.figure.subplots_adjust(left=-0.1, bottom=-0.1, right=1.1, top=1.1)
#         self.update_canvas()

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

    # def update_canvas(self):
    #     self.toggle_loop()
    #     self.toggle_borehole()
    #     self.toggle_mag_field()
    #     self.toggle_loop_label()
    #     self.toggle_loop_anno_labels()
    #     self.toggle_borehole_label()
    #     self.toggle_segment_labels()
    #
    # def toggle_loop(self):
    #     if self.draw_loop_cbox.isChecked():
    #         for artist in self.section_plotter.loop_artists:
    #             artist.set_visible(True)
    #     else:
    #         for artist in self.section_plotter.loop_artists:
    #             artist.set_visible(False)
    #     self.canvas.draw()
    #
    # def toggle_borehole(self):
    #     if self.draw_borehole_cbox.isChecked():
    #         for artist in self.section_plotter.hole_artists:
    #             artist.set_visible(True)
    #     else:
    #         for artist in self.section_plotter.hole_artists:
    #             artist.set_visible(False)
    #     self.canvas.draw()
    #
    # def toggle_mag_field(self):
    #     if self.draw_mag_field_cbox.isChecked():
    #         for artist in self.section_plotter.mag_field_artists:
    #             artist.set_visible(True)
    #     else:
    #         for artist in self.section_plotter.mag_field_artists:
    #             artist.set_visible(False)
    #     self.canvas.draw()
    #
    # def toggle_loop_label(self):
    #     if self.label_loop_cbox.isChecked():
    #         for artist in self.section_plotter.loop_label_artists:
    #             artist.set_visible(True)
    #     else:
    #         for artist in self.section_plotter.loop_label_artists:
    #             artist.set_visible(False)
    #     self.canvas.draw()
    #
    # def toggle_loop_anno_labels(self):
    #     if self.label_loop_anno_cbox.isChecked():
    #         for artist in self.section_plotter.loop_anno_artists:
    #             artist.set_visible(True)
    #     else:
    #         for artist in self.section_plotter.loop_anno_artists:
    #             artist.set_visible(False)
    #     self.canvas.draw()
    #
    # def toggle_borehole_label(self):
    #     if self.label_borehole_cbox.isChecked():
    #         for artist in self.section_plotter.hole_label_artists:
    #             artist.set_visible(True)
    #     else:
    #         for artist in self.section_plotter.hole_label_artists:
    #             artist.set_visible(False)
    #     self.canvas.draw()
    #
    # def toggle_segment_labels(self):
    #     if self.label_segments_cbox.isChecked():
    #         for artist in self.section_plotter.segment_label_artists:
    #             artist.set_visible(True)
    #     else:
    #         for artist in self.section_plotter.segment_label_artists:
    #             artist.set_visible(False)
    #     self.canvas.draw()
    #
    # def closeEvent(self, e):
    #     self.figure.clear()
    #     e.accept()


class ContourMapViewer(QWidget, Ui_ContourMapCreatorFile):
    """
    Widget to display contour maps. Filters the given PEMFiles to only include surface surveys. Either all files
    can be un-split, or if there are any split files, it will split the rest. Averages all files.
    """

    def __init__(self, parent=None):
        super().__init__()
        self.setupUi(self)
        self.setWindowTitle('Contour Map Viewer')
        self.setWindowIcon(QtGui.QIcon(os.path.join(icons_path, 'contour_map3.png')))
        self.channel_list_edit.setEnabled(False)

        self.parent = parent
        self.pem_files = None
        self.components = None
        self.channel_times = None
        self.channel_pairs = None

        self.error = QErrorMessage()
        self.message = QMessageBox()
        self.cmap = ContourMap()

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

        # Figure and canvas
        self.canvas = FigureCanvas(self.cmap.figure)
        self.toolbar = ContourMapToolbar(self.canvas, self)
        self.toolbar_layout.addWidget(self.toolbar)
        self.toolbar.setFixedHeight(30)
        self.map_layout.addWidget(self.canvas)

    def open(self, pem_files):
        """
        Open the PEMFiles and plot the map
        :param pem_files: list, PEMFile objects to plot
        :return: None
        """
        survey_type = pem_files[0].get_survey_type()
        self.pem_files = [file for file in pem_files if not file.is_borehole() and file.get_survey_type() == survey_type]

        # Must be at least 2 eligible surface PEM files.
        if len(self.pem_files) < 2:
            self.message.information(self, 'Insufficient PEM Files', 'Must have at least 2 surface PEM files to plot')
            return

        # Averages any file not already averaged.
        for pem_file in self.pem_files:
            if not pem_file.is_averaged():
                print(f"Averaging {pem_file.filepath.name}")
                pem_file = pem_file.average()

        # Either all files must be split or all un-split
        if not all([pem_file.is_split() for pem_file in self.pem_files]):
            for pem_file in self.pem_files:
                print(f"Splitting channels for {pem_file.filepath.name}")
                pem_file = pem_file.split()

        self.components = np.append(np.unique(np.array([file.get_components() for file in self.pem_files])), 'TF')

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
        pem_file_channels = np.array([file.number_of_channels for file in self.pem_files])
        max_channels = pem_file_channels.max()
        self.channel_spinbox.setMaximum(max_channels)
        self.channel_times = self.pem_files[np.argmax(pem_file_channels)].channel_times

        self.draw_map()
        self.show()

    def draw_map(self):
        """
        Plot the map on the canvas
        """
        component = self.get_selected_component().upper()
        if component not in self.components:
            return

        channel = self.channel_spinbox.value()
        channel_time = self.channel_times.loc[channel]['Center']
        self.time_label.setText(f"{channel_time * 1000:.3f}ms")

        try:
            self.cmap.plot_contour(self.pem_files, component, channel,
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
        Svae to PDF the current selected channel or a list of channels.
        :return: None
        """
        if self.pem_files:
            default_path = self.pem_files[0].filepath.absolute()
            path, ext = QFileDialog.getSaveFileName(self, 'Save Figure', default_path,
                                                    'PDF Files (*.PDF);;PNG Files (*.PNG);;JPG Files (*.JPG')
            if path:
                # Create a new instance of ContourMap
                cmap_save = ContourMap()
                print(f"Saving PDF to {path}")
                with PdfPages(path) as pdf:
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
                        channel_time = self.channel_times.loc[channel]['Center']
                        fig = cmap_save.plot_contour(self.pem_files, self.get_selected_component(),
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
                        fig.clear()
                    plt.close(fig)
                os.startfile(path)


class FoliumMap(QMainWindow):

    def __init__(self):
        super().__init__()
        self.pem_files = None
        self.crs = None
        self.map = None
        self.win = None
        # start_location is used as the zoom-point when the map is opened
        self.start_location = None

        self.error = QErrorMessage()
        layout = QGridLayout()
        self.setLayout(layout)
        self.setWindowTitle('Map')
        self.setWindowIcon(QtGui.QIcon(os.path.join(icons_path, 'folium.png')))

        self.save_img_action = QAction('Save Image')
        self.save_img_action.setShortcut("Ctrl+S")
        self.save_img_action.triggered.connect(self.save_img)
        self.copy_image_action = QAction('Copy Image')
        self.copy_image_action.setShortcut("Ctrl+C")
        self.copy_image_action.triggered.connect(self.copy_img)

        self.file_menu = self.menuBar().addMenu('&File')
        self.file_menu.addAction(self.save_img_action)
        self.file_menu.addAction(self.copy_image_action)

        # create an instance of QWebEngineView and set the html code
        self.web_engine_widget = QWebEngineView()
        self.setCentralWidget(self.web_engine_widget)

    def open(self, pem_files, crs):
        self.pem_files = pem_files
        self.crs = crs
        self.error = QErrorMessage()

        if self.crs.is_valid():
            self.plot_pems()

            # Add the map to a QWebEngineView
            data = io.BytesIO()
            self.map.save(data, close_file=False)
            self.web_engine_widget.setHtml(data.getvalue().decode())

            self.show()

    def plot_pems(self):

        def plot_borehole(pem_file):
            if pem_file.has_collar_gps():
                # Add the CRS to the collar and retrieve the lat lon coordinates
                pem_file.geometry.collar.crs = self.crs
                collar = pem_file.geometry.collar.to_latlon().df

                if collar.to_string() not in collars:
                    collars.append(collar.to_string())
                    if self.start_location is None:
                        self.start_location = collar.loc[0, ['Northing', 'Easting']]

                    # Plot the collar
                    folium.Marker(collar.loc[0, ['Northing', 'Easting']],
                                  popup=pem_file.line_name,
                                  tooltip=pem_file.line_name
                                  ).add_to(collar_group)

        def plot_line(pem_file):
            if pem_file.has_station_gps():
                # Add the CRS to the line and retrieve the lat lon coordinates
                pem_file.line.crs = self.crs
                line = pem_file.line.to_latlon().df

                if line.to_string() not in lines:
                    lines.append(line.to_string())
                    if self.start_location is None:
                        self.start_location = line.loc[0, ['Northing', 'Easting']]

                    # Plot the line
                    folium.PolyLine(locations=line.loc[:, ['Northing', 'Easting']],
                                    popup=pem_file.line_name,
                                    tooltip=pem_file.line_name,
                                    line_opacity=0.5,
                                    color='blue'
                                    ).add_to(line_group)

                    # Plot the stations markers
                    for row in line.itertuples():
                        folium.Marker((row.Northing, row.Easting),
                                      popup=row.Station,
                                      tooltip=row.Station,
                                      size=10
                                      ).add_to(station_group)

        def plot_loop(pem_file):
            if pem_file.has_loop_gps():
                # Add the CRS to the loop and retrieve the lat lon coordinates
                pem_file.loop.crs = self.crs
                loop = pem_file.loop.to_latlon().get_loop(closed=True)

                if loop.to_string() not in loops:
                    loops.append(loop.to_string())
                    if self.start_location is None:
                        self.start_location = loop.loc[0, ['Northing', 'Easting']]
                    # Plot loop
                    folium.PolyLine(locations=loop.loc[:, ['Northing', 'Easting']],
                                    popup=pem_file.loop_name,
                                    tooltip=pem_file.loop_name,
                                    line_opacity=0.5,
                                    color='magenta'
                                    ).add_to(loop_group)

        station_group = folium.FeatureGroup(name='Stations')
        line_group = folium.FeatureGroup(name='Lines')
        loop_group = folium.FeatureGroup(name='Loop')
        collar_group = folium.FeatureGroup(name='Collars')
        loops = []
        collars = []
        lines = []

        for pem_file in self.pem_files:
            if pem_file.is_borehole():
                plot_borehole(pem_file)
            else:
                plot_line(pem_file)

            plot_loop(pem_file)

        self.map = folium.Map(location=self.start_location,
                              zoom_start=15,
                              zoom_control=False,
                              control_scale=True,
                              tiles='OpenStreetMap',
                              attr='testing attr'
                              )

        folium.raster_layers.TileLayer('OpenStreetMap').add_to(self.map)
        folium.raster_layers.TileLayer('Stamen Toner').add_to(self.map)
        folium.raster_layers.TileLayer('Stamen Terrain').add_to(self.map)
        folium.raster_layers.TileLayer('Cartodb positron').add_to(self.map)
        station_group.add_to(self.map)
        line_group.add_to(self.map)
        loop_group.add_to(self.map)
        collar_group.add_to(self.map)
        folium.LayerControl().add_to(self.map)

    def save_img(self):
        save_file = QFileDialog.getSaveFileName(self, 'Save Image', 'map.png', 'PNG Files (*.PNG);; All files(*.*)')[0]

        if save_file:
            size = self.contentsRect()
            img = QtGui.QPixmap(size.width(), size.height())
            self.render(img)
            img.save(save_file)
        else:
            pass

    def copy_img(self):
        size = self.contentsRect()
        img = QtGui.QPixmap(size.width(), size.height())
        self.render(img)
        img.copy(size)
        QApplication.clipboard().setPixmap(img)


class ContourMapToolbar(NavigationToolbar):
    """
    Custom Matplotlib toolbar for ContourMap.
    """
    # only display the buttons we need
    toolitems = [t for t in NavigationToolbar.toolitems if
                 t[0] in ('Home', 'Back', 'Forward', 'Pan', 'Zoom')]


if __name__ == '__main__':
    from src.pem.pem_getter import PEMGetter
    app = QApplication(sys.argv)

    pg = PEMGetter()
    files = pg.get_pems(client='Kazzinc', number=5)

    # map = Map3DViewer()
    # map.show()
    # map.open(files)

    fmap = FoliumMap()
    fmap.open(files, files[0].get_crs())

    # cmap = ContourMapViewer()
    # cmap.open(files)
    # cmap.show()


    app.exec_()