import logging
import os
import re
import sys
import keyboard
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import math
import natsort
import numpy as np
import pandas as pd
import pyqtgraph as pg
from pyqtgraph.graphicsItems.ROI import Handle
import plotly
import plotly.graph_objects as go
from PySide2.QtCore import Qt, QTimer, QPointF, QRect
from PySide2.QtGui import QFont
from PySide2.QtWebEngineWidgets import QWebEngineView
from PySide2.QtWidgets import (QMainWindow, QMessageBox, QGridLayout, QWidget, QAction, QErrorMessage,
                               QFileDialog, QApplication, QHBoxLayout, QShortcut, QActionGroup)
from matplotlib import patheffects
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from scipy import interpolate as interp

from src import app_data_dir, profile, timeit
from src.qt_py import get_icon, CustomProgressDialog, NonScientific, get_line_color, MapToolbar, ScreenshotWindow
from src.gps.gps_editor import BoreholeGeometry
from src.pem.pem_plotter import plot_line, plot_loop
from src.ui.contour_map import Ui_ContourMap

logger = logging.getLogger(__name__)


class TileMapViewer(ScreenshotWindow):

    def __init__(self, parent=None):
        super().__init__()
        self.pem_files = None
        self.parent = parent

        self.loops = []
        self.lines = []
        self.collars = []
        self.holes = []
        self.lons = []  # List of all coordinates for the purpose of centering the map
        self.lats = []  # List of all coordinates for the purpose of centering the map

        self.setWindowTitle("Tile Map")
        self.setWindowIcon(get_icon('folium.png'))
        self.resize(1000, 800)
        self.statusBar().show()

        layout = QHBoxLayout()
        self.setLayout(layout)
        self.layout().setContentsMargins(0, 0, 0, 0)

        self.mapbox_token = self.get_mapbox_token()

        self.map_styles = ["open-street-map",
                          "carto-positron",
                          "carto-darkmatter",
                          "stamen-terrain",
                          "stamen-toner",
                          "stamen-watercolor"]
        if self.mapbox_token:
            self.map_styles.extend(
                ["basic",
                          "streets",
                          "outdoors",
                          "light",
                          "dark",
                          "satellite",
                          "satellite-streets"]
            )

        self.view_menu = self.menuBar().addMenu('&Map Style')
        # self.map_style_menu = self.view_menu.addMenu("Map Style")
        self.map_style_group = QActionGroup(self, exclusive=True)
        for style in self.map_styles:
            action = self.map_style_group.addAction(QAction(style.title(), self, checkable=True))
            self.view_menu.addAction(action)

        if self.mapbox_token:
            self.map_style_group.actions()[self.map_styles.index("satellite")].setChecked(True)
        else:
            self.map_style_group.actions()[self.map_styles.index("open-street-map")].setChecked(True)
        self.map_style_group.triggered.connect(self.refresh_map_style)

        self.map_figure = go.Figure(go.Scattermapbox(mode="markers+lines"))

        # create an instance of QWebEngineView and set the html code
        self.map_widget = QWebEngineView()
        self.map_widget.setContentsMargins(0, 0, 0, 0)
        self.layout().addWidget(self.map_widget)
        self.setCentralWidget(self.map_widget)

    @staticmethod
    def get_mapbox_token():
        if app_data_dir.joinpath(".mapbox").is_file():
            return open(str(app_data_dir.joinpath(".mapbox")), 'r').read()
        else:
            return None

    def get_map_style(self):
        ind = self.map_style_group.actions().index(self.map_style_group.checkedAction())
        style = self.map_styles[ind]
        return style

    def refresh_map_style(self):
        self.map_figure.update_layout(
            mapbox_style=self.get_map_style(),
            mapbox_accesstoken=self.mapbox_token)
        self.load_page()

    def open(self, pem_files):
        if not isinstance(pem_files, list):
            pem_files = [pem_files]
        assert pem_files, "No files to plot."
        assert any([f.has_any_gps() for f in pem_files]), "No GPS to plot."

        self.show()
        self.pem_files = pem_files
        self.plot_pems()

    def plot_pems(self):
        def plot_loop():
            if pem_file.get_loop_gps().empty:
                return
            loop = pem_file.loop.to_latlon().get_loop_gps(closed=True).dropna()

            if loop.to_string() not in self.loops:
                self.loops.append(loop.to_string())

                self.lons.extend(loop.Easting.values)
                self.lats.extend(loop.Northing.values)

                # Plot the loop in the figure
                self.map_figure.add_trace(go.Scattermapbox(lon=loop.Easting,
                                                           lat=loop.Northing,
                                                           legendgroup=pem_file.loop_name,
                                                           mode='lines',
                                                           name=f"Loop {pem_file.loop_name}",
                                                           text=loop.index))

        def plot_line():
            if pem_file.get_line_gps().empty:
                return
            line = pem_file.line.to_latlon().get_line_gps().dropna()

            if line.to_string() not in self.lines:
                self.lines.append(line.to_string())
                self.lons.extend(line.Easting.values)
                self.lats.extend(line.Northing.values)

                # Plot the line in the figure
                self.map_figure.add_trace(go.Scattermapbox(lon=line.Easting,
                                                           lat=line.Northing,
                                                           legendgroup=pem_file.loop_name,
                                                           mode='lines+markers',
                                                           name=pem_file.line_name,
                                                           text=line.Station
                                                           ))

        def plot_hole():
            geometry = BoreholeGeometry(pem_file.collar, pem_file.segments)
            proj = geometry.get_projection(latlon=True)
            if proj.empty or pem_file.get_collar_gps().empty:
                return
            collar = pem_file.collar.to_latlon().get_collar_gps().dropna()

            if not proj.empty and proj.to_string() not in self.holes:
                logger.info(f"Plotting hole trace for {pem_file.filepath.name}")
                self.holes.append(proj.to_string())
                self.collars.append(collar.to_string())
                self.lons.extend(proj.Easting.values)
                self.lats.extend(proj.Northing.values)

                # Plot the line in the figure
                self.map_figure.add_trace(go.Scattermapbox(lon=proj.Easting,
                                                           lat=proj.Northing,
                                                           mode='lines+markers',
                                                           legendgroup=pem_file.loop_name,
                                                           name=pem_file.line_name,
                                                           text=proj['Relative_depth']
                                                           ))

            elif not collar.empty and collar.to_string() not in self.collars:
                self.collars.append(collar.to_string())
                self.lons.extend(collar.Easting.values)
                self.lats.extend(collar.Northing.values)

                self.map_figure.add_trace(go.Scattermapbox(lon=collar.Easting,
                                                           lat=collar.Northing,
                                                           mode='markers',
                                                           marker=go.scattermapbox.Marker(
                                                               size=10
                                                           ),
                                                           legendgroup=pem_file.loop_name,
                                                           name=pem_file.line_name,
                                                           text=pem_file.line_name
                                                           ))

                # self.map_figure.add_trace(go.Scattermapbox(
                #     lat=['45.5017'],
                #     lon=['-73.5673'],
                #     mode='markers',
                #     marker=go.scattermapbox.Marker(
                #         size=14
                #     ),
                #     text=['Montreal'],
                # ))

        with CustomProgressDialog("Plotting PEM Files", 0, len(self.pem_files)) as dlg:
            # Plot the PEMs
            for pem_file in self.pem_files:
                pem_file = pem_file.copy()  # Copy the PEM file so GPS conversions don't affect the original file
                if dlg.wasCanceled():
                    break
                dlg.setLabelText(f"Plotting {pem_file.filepath.name}")

                crs = pem_file.get_crs()
                if not crs:
                    logger.warning(f"Skipping {pem_file.filepath.name} because it doesn't have a valid CRS.")
                    continue

                # Plot the GPS objects
                plot_loop()
                if not pem_file.is_borehole():
                    plot_line()
                else:
                    plot_hole()
                dlg += 1

        assert all([self.lons, self.lats]), f"No Lat/Lon GPS found."

        self.map_figure.update_layout(
            margin={"r": 0,
                    "t": 0,
                    "l": 0,
                    "b": 0},
            legend=dict(yanchor="top",
                        xanchor="left",
                        x=0.01,
                        y=0.99,
                        bordercolor="Black",
                        borderwidth=1),
            mapbox={'center': {'lon': np.mean(self.lons), 'lat': np.mean(self.lats)},
                    'zoom': 13},
            # autosize=True,
            mapbox_style=self.get_map_style(),
            mapbox_accesstoken=self.mapbox_token
        )

        self.load_page() # Add the plot HTML to be shown in the plot widget

    def load_page(self):
        """
        Plots the data by creating the HTML from the plot and setting it in the WebEngine.
        """
        # Create the HTML
        html = '<html><body>'
        html += plotly.offline.plot(self.map_figure,
                                    output_type='div',
                                    include_plotlyjs='cdn',
                                    config={'displayModeBar': False}
                                    )
        html += '</body></html>'

        # Add the plot HTML to be shown in the plot widget
        self.map_widget.setHtml(html)


class Map3DViewer(ScreenshotWindow):

    def __init__(self, parent=None, darkmode=False):
        super().__init__()
        self.pem_files = None
        self.parent = parent
        self.darkmode = darkmode

        self.loops = []
        self.lines = []
        self.collars = []
        self.holes = []
        self.annotations = []

        self.setWindowTitle("3D Map Viewer")
        self.setWindowIcon(get_icon('3d_map.png'))
        self.resize(1000, 800)
        self.setLayout(QGridLayout())

        # create an instance of QWebEngineView and set the html code
        self.map_widget = QWebEngineView()
        self.setCentralWidget(self.map_widget)

        self.map_figure = go.Figure()
        self.map_figure.update_layout(scene=dict(
            xaxis_title='EASTING',
            yaxis_title='NORTHING',
            zaxis_title='ELEVATION',
            aspectmode='data'),
            margin={"r": 0,
                    "t": 0,
                    "l": 0,
                    "b": 0},
            template="plotly_dark" if self.darkmode else "plotly"
        )

    def open(self, pem_files):
        if not isinstance(pem_files, list):
            pem_files = [pem_files]

        assert pem_files, "No files to plot."

        if any([f.has_any_gps() for f in pem_files]):
            self.pem_files = pem_files
            self.plot_pems()
            self.show()
        else:
            raise Exception(f"No GPS to plot.")

    def plot_pems(self):
        def plot_loop(pem_file):
            loop = pem_file.get_loop_gps(closed=True)

            if not loop.empty and loop.to_string() not in self.loops:
                self.loops.append(loop.to_string())

                # Plot the loop in the figure
                self.map_figure.add_trace(go.Scatter3d(x=loop.Easting,
                                                       y=loop.Northing,
                                                       z=loop.Elevation,
                                                       # legendgroup=pem_file.loop_name,
                                                       mode='lines',
                                                       name=f"Loop {pem_file.loop_name}",
                                                       text=loop.index))

        def plot_line(pem_file):
            line = pem_file.get_line_gps()

            if not line.empty and line.to_string() not in self.lines:
                self.lines.append(line.to_string())
                # Plot the line in the figure
                self.map_figure.add_trace(go.Scatter3d(x=line.Easting,
                                                       y=line.Northing,
                                                       z=line.Elevation,
                                                       # legendgroup=pem_file.loop_name,
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

        def plot_hole(pem_file):
            collar = pem_file.get_collar_gps().dropna()
            geometry = BoreholeGeometry(pem_file.collar, pem_file.segments)
            proj = geometry.get_projection(latlon=False)

            if not proj.empty and proj.to_string() not in self.holes:
                self.holes.append(proj.to_string())
                self.collars.append(collar.to_string())
                # Plot the line in the figure
                self.map_figure.add_trace(go.Scatter3d(x=proj.Easting,
                                                       y=proj.Northing,
                                                       z=proj.Elevation,
                                                       mode='lines+markers',
                                                       # legendgroup=pem_file.loop_name,
                                                       name=pem_file.line_name,
                                                       text=proj['Relative_depth']
                                                       ))

            elif not collar.empty and collar.to_string() not in self.collars:
                self.collars.append(collar.to_string())
                self.map_figure.add_trace(go.Scatter3d(x=collar.Easting,
                                                       y=collar.Northing,
                                                       z=collar.Elevation,
                                                       # legendgroup=pem_file.loop_name,
                                                       name=pem_file.line_name,
                                                       text=pem_file.line_name
                                                       ))

        def load_page():
            """
            Plots the data by creating the HTML from the plot and setting it in the WebEngine.
            """
            # Create the HTML
            html = '<html><body>'
            html += plotly.offline.plot(self.map_figure,
                                        output_type='div',
                                        include_plotlyjs='cdn',
                                        config={'displayModeBar': False}
                                        )
            # html += "body {margin: 0;}"  # Attempting to remove white border with darkmode
            html += '</body></html>'

            # Add the plot HTML to be shown in the plot widget
            self.map_widget.setHtml(html)

        # Plot the PEMs
        for pem_file in self.pem_files:
            plot_loop(pem_file)

            if not pem_file.is_borehole():
                plot_line(pem_file)

            else:
                plot_hole(pem_file)

        # Set the style of the markers and lines
        self.map_figure.update_traces(marker=dict(size=6,
                                                  line=dict(width=2,
                                                            color=get_line_color("gray", "mpl", self.darkmode))),
                                      line=dict(width=4)
                                      )

        self.map_figure.update_layout(yaxis_tickformat='%',
                                      legend=dict(
                                          yanchor="top",
                                          y=0.99,
                                          xanchor="left",
                                          x=0.01,
                                      )
                                      )

        # Add the plot HTML to be shown in the plot widget
        load_page()

    def save_img(self):
        save_name, save_type = QFileDialog.getSaveFileName(self, 'Save Image',
                                                           'map.png',
                                                           'PNG file (*.PNG);; PDF file (*.PDF)'
                                                           )
        if save_name:
            if 'PDF' in save_type:
                self.map_widget.page().printToPdf(save_name)
            else:
                self.grab().save(save_name)

    def copy_img(self):
        QApplication.clipboard().setPixmap(self.grab())
        self.statusBar().show()
        self.statusBar().showMessage('Image copied to clipboard.', 1000)
        QTimer.singleShot(1000, lambda: self.statusBar().hide())


# TODO Make ContourMapViewer a MainWindow and inherit ScreenshotWindow
class ContourMapViewer(QWidget, Ui_ContourMap):
    """
    Widget to display contour maps. Filters the given PEMFiles to only include surface surveys. Either all files
    can be un-split, or if there are any split files, it will split the rest. Averages all files.
    """
    def __init__(self, parent=None, darkmode=False):
        super().__init__()
        self.setupUi(self)
        self.setWindowTitle('Contour Map Viewer')
        self.setWindowIcon(get_icon('contour_map.png'))
        self.channel_list_edit.setEnabled(False)

        self.error = QErrorMessage()
        self.message = QMessageBox()
        self.parent = parent
        self.darkmode = darkmode

        plt.style.use('dark_background' if self.darkmode else 'default')
        plt.rcParams['axes.facecolor'] = get_line_color("background", "mpl", self.darkmode)
        plt.rcParams['figure.facecolor'] = get_line_color("background", "mpl", self.darkmode)
        self.acc_color = get_line_color("blue", "mpl", self.darkmode)
        self.mag_color = get_line_color("green", "mpl", self.darkmode)
        self.foreground_color = get_line_color("foreground", "mpl", self.darkmode)
        self.background_color = get_line_color("background", "mpl", self.darkmode)

        self.pem_files = None
        self.data = pd.DataFrame()
        self.components = None
        self.channel_times = None
        self.channel_pairs = None

        self.figure, self.ax, self.cbar_ax = self.get_figure()
        self.canvas = FigureCanvas(self.figure)
        self.toolbar = MapToolbar(self.canvas, self)
        self.toolbar_layout.addWidget(self.toolbar)
        self.toolbar.setFixedHeight(30)
        self.map_layout.addWidget(self.canvas)
        self.ax.spines['right'].set_visible(False)
        self.ax.spines['bottom'].set_visible(False)

        # Creating a custom colormap that imitates the Geosoft colors
        # Blue > Teal > Green > Yellow > Red > Orange > Magenta > Light pink
        custom_colors = [(0, 0, 1), (0, 1, 1), (0, 1, 0), (1, 1, 0), (1, 0.5, 0), (1, 0, 0), (1, 0, 1), (1, .8, 1)]
        custom_cmap = mpl.colors.LinearSegmentedColormap.from_list('custom', custom_colors)
        custom_cmap.set_under('blue')
        custom_cmap.set_over('magenta')
        self.colormap = custom_cmap

        """Signals"""
        self.save_img_action = QAction('Save Image')
        self.save_img_action.setShortcut("Ctrl+S")
        self.save_img_action.triggered.connect(self.save_img)
        self.save_img_action.setIcon(get_icon("save_as.png"))
        self.copy_image_action = QAction('Copy Image')
        self.copy_image_action.setShortcut("Ctrl+C")
        self.copy_image_action.triggered.connect(self.copy_img)
        self.copy_image_action.setIcon(get_icon("copy.png"))

        self.channel_spinbox.valueChanged.connect(lambda: self.draw_map(self.figure))
        self.z_rbtn.clicked.connect(lambda: self.draw_map(self.figure))
        self.x_rbtn.clicked.connect(lambda: self.draw_map(self.figure))
        self.y_rbtn.clicked.connect(lambda: self.draw_map(self.figure))
        self.tf_rbtn.clicked.connect(lambda: self.draw_map(self.figure))
        self.plot_loops_cbox.toggled.connect(lambda: self.draw_map(self.figure))
        self.plot_lines_cbox.toggled.connect(lambda: self.draw_map(self.figure))
        self.plot_stations_cbox.toggled.connect(lambda: self.draw_map(self.figure))
        self.label_loops_cbox.toggled.connect(lambda: self.draw_map(self.figure))
        self.label_lines_cbox.toggled.connect(lambda: self.draw_map(self.figure))
        self.label_stations_cbox.toggled.connect(lambda: self.draw_map(self.figure))
        self.plot_elevation_cbox.toggled.connect(lambda: self.draw_map(self.figure))
        self.grid_cbox.toggled.connect(self.toggle_grid)
        self.title_box_cbox.toggled.connect(lambda: self.draw_map(self.figure))
        self.channel_list_rbtn.toggled.connect(
            lambda: self.channel_list_edit.setEnabled(self.channel_list_rbtn.isChecked()))
        self.save_figure_btn.clicked.connect(self.save_figure)

    def closeEvent(self, e):
        e.accept()
        self.deleteLater()

    def save_img(self):
        save_name, save_type = QFileDialog.getSaveFileName(self, 'Save Image',
                                                           'map.png',
                                                           'PNG file (*.PNG);; PDF file (*.PDF)'
                                                           )
        if save_name:
            if 'PDF' in save_type:
                self.map_widget.page().printToPdf(save_name)
            else:
                self.grab().save(save_name)

    def copy_img(self):
        QApplication.clipboard().setPixmap(self.grab())
        # self.status_bar.show()
        self.status_bar.showMessage('Image copied to clipboard.', 1000)
        # QTimer.singleShot(1000, lambda: self.status_bar.hide())

    @staticmethod
    def get_figure():
        """
        Create the figure and axes for plotting. Required for saving the plots.
        """
        figure = Figure(figsize=(11, 8.5))

        # Create a large grid in order to specify the placement of the colorbar
        ax = plt.subplot2grid((90, 110), (0, 0),
                              rowspan=90,
                              colspan=90,
                              fig=figure)
        ax.spines['top'].set_visible(False)
        ax.spines['left'].set_visible(False)
        ax.set_aspect('equal')
        ax.use_sticky_edges = False  # So the plot doesn't re-size after the first time it's plotted
        ax.yaxis.tick_right()

        cbar_ax = plt.subplot2grid((90, 110), (0, 108),
                                   rowspan=90,
                                   colspan=2,
                                   fig=figure)

        return figure, ax, cbar_ax

    def open(self, pem_files):
        """
        Open the PEMFiles and plot the map
        :param pem_files: list, PEMFile objects to plot
        :return: None
        """
        survey_type = pem_files[0].get_survey_type()
        self.pem_files = [file for file in pem_files if not file.is_borehole() and file.get_survey_type() == survey_type]

        if len(self.pem_files) < 2:
            self.message.information(self, 'Insufficient PEM Files', 'Must have at least 2 surface PEM files to plot')
            return
        elif not all([file.is_fluxgate() == self.pem_files[0].is_fluxgate() for file in self.pem_files]):
            self.message.information(self, 'Mixed Survey Types', 'Not all survey types are the same.')
            return

        self.show()
        self.get_contour_data()
        if self.data.empty:
            self.message.information(self, "No Data Found", f"No valid contour data was found.")
            return

        # Averages any file not already averaged.
        if not all([pem_file.is_averaged() for pem_file in self.pem_files]):
            for pem_file in self.pem_files:
                pem_file.average()

        # Either all files must be split or all un-split
        if not all([pem_file.is_split() for pem_file in self.pem_files]):
            for pem_file in self.pem_files:
                pem_file.split()

        self.components = np.append(np.unique(np.hstack(np.array([file.get_components() for file in self.pem_files],
                                                        dtype=object))), 'TF')

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
        self.channel_spinbox.setMaximum(max_channels - 1)
        self.channel_times = self.pem_files[np.argmax(pem_file_channels)].channel_times

        self.draw_map(self.figure)

    @timeit
    def get_contour_data(self):
        """
        Create contour data (GPS + channel reading) for all PEMFiles.
        :return: pandas DataFrame
        """
        self.data = pd.DataFrame()
        with CustomProgressDialog("Gathering PEM Data", 0, len(self.pem_files)) as dlg:
            # app.processEvents()
            for pem_file in self.pem_files:
                if dlg.wasCanceled():
                    break
                pem_data = pem_file.get_contour_data()
                self.data = pd.concat([self.data, pem_data])
                dlg += 1

    def toggle_grid(self):
        # Draw the grid
        if self.grid_cbox.isChecked():
            self.ax.grid()
        else:
            self.ax.grid(False)
        self.canvas.draw_idle()


    @profile()
    @timeit
    def draw_map(self, figure, channel=None):
        """
        Plot the map on the canvas
        """
        def plot_pem_gps():
            """
            Plots the GPS information (lines, stations, loops) from the PEM files
            """
            loops = []
            lines = []

            for pem_file in self.pem_files:
                # Plot the line
                line = pem_file.line
                if all([pem_file.has_station_gps(),
                        self.plot_lines_cbox.isChecked(),
                        line not in lines]):
                    lines.append(line)
                    plot_line(pem_file, figure,
                              annotate=bool(
                                  self.label_stations_cbox.isChecked() and
                                  self.label_stations_cbox.isEnabled()),
                              label=bool(
                                  self.label_lines_cbox.isChecked() and
                                  self.label_lines_cbox.isEnabled()),
                              plot_ticks=bool(
                                  self.plot_stations_cbox.isChecked() and
                                  self.plot_stations_cbox.isEnabled()),
                              color=self.foreground_color,
                              buffer_color=self.background_color)

                # Plot the loop
                loop = pem_file.loop
                if all([pem_file.has_loop_gps(),
                        self.plot_loops_cbox.isChecked(),
                        loop not in loops]):
                    loops.append(loop)
                    plot_loop(pem_file, figure,
                              annotate=False,
                              label=bool(
                                  self.label_loops_cbox.isChecked() and
                                  self.label_loops_cbox.isEnabled()),
                              color=self.foreground_color,
                              buffer_color=self.background_color)

        def add_title():
            """
            Adds the title box to the plot. Removes any existing text first.
            """
            # Remove any previous title texts
            for text in reversed(figure.texts):
                text.remove()

            # Draw the title
            if self.title_box_cbox.isChecked():
                center_pos = 0.5
                top_pos = 0.95

                client = self.pem_files[0].client
                grid = self.pem_files[0].grid
                loops = natsort.os_sorted(np.unique(np.array([f.loop_name for f in self.pem_files])))
                if len(loops) > 3:
                    loop_text = f"Loop: {loops[0]} to {loops[-1]}"
                else:
                    loop_text = f"Loop: {', '.join(loops)}"

                # coord_sys = f"{system}{' Zone ' + zone.title() if zone else ''}, {datum.upper()}"
                # scale = f"1:{map_scale:,.0f}"

                crone_text = figure.text(center_pos, top_pos, 'Crone Geophysics & Exploration Ltd.',
                                         fontname='Century Gothic',
                                         fontsize=11,
                                         ha='center',
                                         zorder=10)

                survey_type = self.pem_files[0].get_survey_type()
                survey_text = figure.text(center_pos, top_pos - 0.036, f"Cubic-Interpolation Contour Map"
                                                                       f"\n{survey_type} Pulse EM "
                                                                       f"Survey",
                                          family='cursive',
                                          style='italic',
                                          fontname='Century Gothic',
                                          fontsize=9,
                                          ha='center',
                                          zorder=10)

                header_text = figure.text(center_pos, top_pos - 0.046, f"{client}\n{grid}\n{loop_text}",
                                          fontname='Century Gothic',
                                          fontsize=9.5,
                                          va='top',
                                          ha='center',
                                          zorder=10)

        ax = figure.axes[0]
        cbar_ax = figure.axes[1]
        ax.cla()
        cbar_ax.cla()

        component = self.get_selected_component().upper()
        if component not in self.components:
            self.message.information(self, "Missing Component",
                                     f"'{component}' component is not in the available components.")
            return

        if channel is None:
            channel = self.channel_spinbox.value()
        channel_time = self.channel_times.iloc[channel]['Center']
        self.time_label.setText(f"{channel_time * 1000:.3f}ms")

        add_title()
        plot_pem_gps()

        # Creating a 2D grid for the interpolation
        numcols, numrows = 100, 100
        xi = np.linspace(self.data.Easting.min(), self.data.Easting.max(), numcols)
        yi = np.linspace(self.data.Northing.min(), self.data.Northing.max(), numrows)
        xx, yy = np.meshgrid(xi, yi)

        # Interpolating the 2D grid data
        comp_data = self.data.loc[self.data.Component == component]
        ch_data = comp_data.loc[:, channel]
        di = interp.griddata((comp_data.Easting, comp_data.Northing), ch_data, (xx, yy), method='cubic')

        # Add elevation contour lines
        if self.plot_elevation_cbox.isChecked():
            zi = interp.griddata((comp_data.Easting, comp_data.Northing), comp_data.Elevation, (xx, yy),
                                 method='cubic')
            contour = ax.contour(xi, yi, zi,
                                 colors=self.foreground_color,
                                 alpha=0.8)
            # contourf = ax.contourf(xi, yi, zi, cmap=colormap)
            ax.clabel(contour,
                      fontsize=6,
                      inline=True,
                      inline_spacing=0.5,
                      fmt='%d')

        # Add the filled contour plot
        contourf = ax.contourf(xi, yi, di,
                               cmap=self.colormap,
                               levels=50)

        # Add colorbar for the data contours
        cbar = figure.colorbar(contourf, cax=cbar_ax)
        cbar_ax.set_xlabel(f"{'pT' if self.pem_files[0].is_fluxgate() else 'nT/s'}")
        cbar.ax.get_xaxis().labelpad = 10

        # Add component and channel text at the top right of the figure
        component_text = f"{component.upper()} Component" if component != 'TF' else 'Total Field'
        info_text = figure.text(0, 1.02, f"{component_text}\nChannel {channel}\n{channel_time * 1000:.3f}ms",
                                transform=cbar_ax.transAxes,
                                color=self.foreground_color,
                                fontname='Century Gothic',
                                fontsize=9,
                                va='bottom',
                                ha='center',
                                zorder=10)

        ax.yaxis.get_major_formatter().set_scientific(False)
        self.toggle_grid()

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
        Save to PDF the current selected channel or a list of channels.
        :return: None
        """
        if self.pem_files:
            # plt.style.use('default')
            default_path = self.pem_files[0].filepath.parent.with_suffix(".PDF")
            path, ext = QFileDialog.getSaveFileName(self, 'Save Figure', str(default_path),
                                                    'PDF Files (*.PDF);;PNG Files (*.PNG);;JPG Files (*.JPG')
            if path:
                # Create a new instance of ContourMap
                logger.info(f"Saving PDF to {path}.")
                with PdfPages(path) as pdf:
                    # Print plots from the list of channels if it's enabled
                    if self.channel_list_edit.isEnabled():
                        text = self.channel_list_edit.text()
                        try:
                            channels = []
                            for split_text in re.split(r",| ", text):
                                if split_text == '':
                                    continue
                                ch_match = re.match(r"\d+", split_text)
                                if not ch_match:
                                    self.message.information(self, "Invalid Channel",
                                                             f"No integer value found in '{split_text}'.")
                                    continue
                                try:
                                    ch = int(ch_match[0])
                                except ValueError:
                                    self.message.information(self, "Invalid Channel",
                                                             f"{ch_match[0]} is not an integer value.")
                                else:
                                    channels.append(ch)
                            logger.info(f"Saving contour map plots for channels {channels}.")
                        except IndexError:
                            logger.critical(f"No numbers found in the list of channels.")
                            self.error.showMessage(f"No numbers found in the list of channels.")
                            return
                    else:
                        channels = [self.channel_spinbox.value()]

                    # Use a separate figure just for saving
                    save_fig, ax, cbar_ax = self.get_figure()

                    for channel in channels:
                        if channel not in self.data.columns:
                            self.message.information(self, "Invalid Channel", f"Channel {channel} is not in the data.")
                            continue
                        self.draw_map(save_fig, channel)
                        pdf.savefig(save_fig, orientation='landscape')

                    plt.close(save_fig)
                # plt.style.use('dark_background' if self.darkmode else 'default')
                os.startfile(path)


class GPSViewer(QMainWindow):

    def __init__(self, parent=None, darkmode=False):
        super().__init__()
        # Format the window
        self.setWindowTitle(f"GPS Viewer")
        self.setWindowIcon(get_icon('gps_viewer.png'))
        self.setFocusPolicy(Qt.StrongFocus)
        self.installEventFilter(self)

        pg.setConfigOption('background', (66, 66, 66) if darkmode else 'w')
        pg.setConfigOption('foreground', 'w' if darkmode else (53, 53, 53))

        layout = QHBoxLayout()
        self.plan_view = pg.PlotWidget()
        self.setCentralWidget(self.plan_view)
        self.setLayout(layout)
        self.setContentsMargins(0, 0, 0, 0)

        self.parent = parent
        self.darkmode = darkmode
        self.pem_files = None
        self.contour_data = pd.DataFrame()
        self.status_bar = self.statusBar()
        self.status_bar.hide()

        self.loops = []
        self.lines = []
        self.collars = []
        self.traces = []
        self.foreground_color = get_line_color("foreground", "mpl", self.darkmode)
        self.background_color = get_line_color("background", "mpl", self.darkmode)
        self.line_color = get_line_color("teal", "mpl", self.darkmode)
        self.loop_color = get_line_color("foreground", "mpl", self.darkmode)
        self.hole_color = get_line_color("blue", "mpl", self.darkmode)
        self.green_color = get_line_color("green", "mpl", self.darkmode)

        # Format the plots
        self.plan_view.setAxisItems({'left': NonScientific(orientation='left'),
                                     'bottom': NonScientific(orientation='bottom')})

        self.plan_view.setAspectLocked()
        self.plan_view.setMenuEnabled(False)
        self.plan_view.showGrid(x=True, y=True, alpha=0.1)
        self.plan_view.hideButtons()  # Hide the little 'A' button at the bottom left

        self.plan_view.getAxis('left').setLabel('Northing', units='m')
        self.plan_view.getAxis('bottom').setLabel('Easting', units='m')

        self.plan_view.getAxis('left').enableAutoSIPrefix(enable=False)  # Disables automatic scaling of labels
        self.plan_view.getAxis('bottom').enableAutoSIPrefix(enable=False)  # Disables automatic scaling of labels
        self.plan_view.getAxis("right").setStyle(showValues=False)  # Disable showing the values of axis
        self.plan_view.getAxis("top").setStyle(showValues=False)  # Disable showing the values of axis

        # self.plan_view.getAxis('right').setWidth(10)  # Move the right edge of the plot away from the window edge
        self.plan_view.showAxis('right', show=True)  # Show the axis edge line
        self.plan_view.showAxis('top', show=True)  # Show the axis edge line
        self.plan_view.showLabel('right', show=False)
        self.plan_view.showLabel('top', show=False)

        self.ruler = None
        self.ruler_text = None
        self.measuring_pos = None
        self.measuring_state = 0

        # Actions
        self.save_img_action = QShortcut("Ctrl+S", self)
        self.save_img_action.activated.connect(self.save_img)
        self.copy_image_action = QShortcut("Ctrl+C", self)
        self.copy_image_action.activated.connect(self.copy_img)
        self.auto_range_action = QShortcut(" ", self)
        self.auto_range_action.activated.connect(lambda: self.plan_view.autoRange())
        self.plan_view.scene().sigMouseClicked.connect(self.mouse_clicked)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape or event.key() == Qt.Key_Delete:
            # Remove the ruler when Escape or Delete is pressed
            if self.ruler in self.plan_view.items():
                self.plan_view.removeItem(self.ruler)  # On second click, remove the tool entirely.
                self.plan_view.removeItem(self.ruler_text)  # On second click, remove the tool entirely.
                self.measuring_state = 0

    def mouse_clicked(self, e):
        """
        When the plot is clicked. Add the measuring tool if CTRL is held. Otherwise, the first normal click
        will stop moving the measuring tool end, and the second normal click will remove the tool all together.
        :param e: MouseClickEvent object.
        """
        if keyboard.is_pressed("CTRL"):
            """Add the measuring tool"""
            self.plan_view.removeItem(self.ruler)
            self.plan_view.removeItem(self.ruler_text)

            pos = self.plan_view.getPlotItem().vb.mapSceneToView(e.scenePos())
            self.measuring_pos = pos
            self.ruler = Ruler(positions=[pos, pos],
                               pen=pg.mkPen(self.green_color,
                                            style=Qt.DashLine,
                                            width=1.5))
            self.ruler.setZValue(10)
            self.ruler.sigRegionChanged.connect(self.update_ruler)
            self.ruler_text = pg.TextItem("length",
                                          color=pg.mkColor(self.green_color),
                                          anchor=(0.5, 0.5),
                                          fill=pg.mkBrush(self.background_color))
            self.ruler_text.setParentItem(self.ruler)
            # self.ruler_text.setFont(QFont("Helvetica", 9, QFont.Normal))
            self.ruler_text.setZValue(10)
            self.plan_view.addItem(self.ruler, ignoreBounds=True)
            self.plan_view.addItem(self.ruler_text, ignoreBounds=True)
            self.plan_view.scene().sigMouseMoved.connect(self.move_measuring_tool)
            self.update_ruler()
        else:
            if self.ruler in self.plan_view.items():
                if self.measuring_state % 2 == 0:  # On first click, stop moving the second handle, but keep the tool.
                    self.plan_view.scene().sigMouseMoved.disconnect()
                else:
                    self.plan_view.removeItem(self.ruler)  # On second click, remove the tool entirely.
                    self.plan_view.removeItem(self.ruler_text)  # On second click, remove the tool entirely.
                self.measuring_state += 1

    def move_measuring_tool(self, e):
        """
        Move the second measuring tool handle when the measuring tool is out.
        :param e: QPointF, position of the mouse.
        """
        pos = self.plan_view.getPlotItem().vb.mapSceneToView(e)
        self.ruler.movePoint(self.ruler.getHandles()[-1], pos)

    def update_ruler(self):
        """
        Move the distance text and position when the ruler is moved or changed.
        :return: None
        """
        def get_ruler_info():
            handles = self.ruler.getHandles()
            handle_positions = np.array([vb.mapSceneToView(h.scenePos()) for h in handles])

            distance = math.sqrt((handle_positions[0].x() - handle_positions[1].x()) ** 2 +
                                 (handle_positions[0].y() - handle_positions[1].y()) ** 2)

            new_pos = QPointF(np.mean([h.x() for h in handle_positions]), np.mean([h.y() for h in handle_positions]))
            return new_pos, distance

        vb = self.plan_view.getPlotItem().vb
        new_pos, distance = get_ruler_info()
        self.ruler_text.setText(f"{distance:.2f} m")
        self.ruler_text.setPos(new_pos)

    def save_img(self):
        save_name, save_type = QFileDialog.getSaveFileName(self, 'Save Image', 'gps.png', 'PNG file (*.PNG)')
        if save_name:
            self.grab().save(save_name)

    def copy_img(self):
        QApplication.clipboard().setPixmap(self.grab())
        self.status_bar.show()
        self.status_bar.showMessage('Image copied to clipboard.', 1000)
        QTimer.singleShot(1000, lambda: self.status_bar.hide())

    def open(self, pem_files):
        if not isinstance(pem_files, list):
            pem_files = [pem_files]

        assert pem_files, f"No PEM files to plot."
        self.pem_files = pem_files
        self.plot_pems()
        self.show()

    def plot_pems(self):
        def plot_loop():
            def add_loop_annotation(row):
                """Add the loop number annotation"""
                text_item = pg.TextItem(str(row.name), color=self.loop_color, border=None, fill=None, anchor=(0.5, 0.5))
                self.plan_view.addItem(text_item, ignoreBounds=True)
                text_item.setPos(row.Easting, row.Northing)
                text_item.setParentItem(loop_item)
                # text_item.setFont(QFont("Helvetica", 7, QFont.Normal))
                text_item.setZValue(0)

            loop = pem_file.get_loop_gps(sorted=False, closed=True).dropna()
            if loop.empty:
                logger.warning(f"No loop GPS in {pem_file.filepath.name}.")
                return
            loop_str = loop.to_string()

            if not loop.empty and loop_str not in self.loops:
                self.loops.append(loop_str)

                # Plot the loop line
                loop_item = pg.PlotDataItem(clickable=True,
                                            name=pem_file.loop_name,
                                            pen=pg.mkPen(self.loop_color, width=1.)
                                            )
                loop_item.setZValue(-1)
                loop_item.setData(loop.Easting, loop.Northing)

                self.plan_view.addItem(loop_item)

                # Plot the annotations
                loop.apply(add_loop_annotation, axis=1)

                # Plot the loop name annotation
                center = pem_file.loop.get_center()
                text_item = pg.TextItem(str(pem_file.loop_name),
                                        color=self.loop_color,
                                        anchor=(0.5, 0.5),
                                        )
                self.plan_view.addItem(text_item, ignoreBounds=True)
                text_item.setPos(center[0], center[1])
                text_item.setParentItem(loop_item)
                # text_item.setFont(QFont("Helvetica", 8, QFont.Normal))
                text_item.setZValue(0)

        def plot_line():
            # Removed, creates too much lag
            def add_station_annotation(row):
                """Add the station name annotation"""
                text_item = pg.TextItem(str(row.Station),
                                        color=self.line_color,
                                        anchor=(0, 0.5),
                                        rotateAxis=(row.Easting, row.Northing),
                                        # angle=90
                )
                self.plan_view.addItem(text_item, ignoreBounds=True)
                text_item.setPos(row.Easting, row.Northing)
                text_item.setParentItem(line_item)
                # text_item.setFont(QFont("Helvetica", 8, QFont.Normal))
                text_item.setZValue(2)

            line = pem_file.get_line_gps().dropna()
            if line.empty:
                logger.warning(f"No line GPS in {pem_file.filepath.name}.")
                return

            line_str = line.to_string()

            if not line.empty and line_str not in self.lines:
                self.lines.append(line_str)

                line_item = pg.PlotDataItem(clickable=True,
                                            name=pem_file.line_name,
                                            symbol='o',
                                            symbolSize=5,
                                            symbolPen=pg.mkPen(self.line_color, width=1.),
                                            symbolBrush=pg.mkBrush(self.background_color),
                                            pen=pg.mkPen(self.line_color, width=1.)
                                            )
                line_item.setData(line.Easting, line.Northing)
                line_item.setZValue(1)

                self.plan_view.addItem(line_item)

                # # Add the station annotations
                # line.apply(add_station_annotation, axis=1)

                # Add the line name annotation
                text_item = pg.TextItem(str(pem_file.line_name),
                                        color=self.line_color,
                                        anchor=(1, 0.5),
                                        )
                self.plan_view.addItem(text_item, ignoreBounds=True)
                text_item.setPos(line.iloc[line.Station.argmin()].Easting,
                                 line.iloc[line.Station.argmin()].Northing)
                text_item.setParentItem(line_item)
                text_item.setFont(QFont("Helvetica", 8, QFont.Normal))
                text_item.setZValue(2)

        def plot_hole():
            def plot_collar():
                if collar.to_string() not in self.collars:
                    self.collars.append(collar.to_string())

                    collar_item = pg.PlotDataItem(clickable=True,
                                                  name=pem_file.line_name,
                                                  symbol='o',
                                                  symbolSize=10,
                                                  symbolPen=pg.mkPen(self.hole_color, width=1.),
                                                  symbolBrush=pg.mkBrush(self.background_color),
                                                  pen=pg.mkPen(self.hole_color, width=1.5)
                                                  )
                    collar_item.setZValue(2)
                    # Don't plot the collar here
                    collar_item.setData(collar.Easting, collar.Northing)
                    self.plan_view.addItem(collar_item)

                    # Add the hole name annotation
                    text_item = pg.TextItem(f"{pem_file.line_name}",
                                            color=self.hole_color,
                                            anchor=name_anchor,
                                            # anchor=anchor,
                                            )
                    self.plan_view.addItem(text_item, ignoreBounds=True)
                    text_item.setPos(collar.iloc[0].Easting,
                                     collar.iloc[0].Northing)
                    text_item.setParentItem(collar_item)
                    text_item.setFont(QFont("Helvetica", 8, QFont.Normal))
                    text_item.setZValue(2)

            def plot_geometry():
                if proj.to_string() not in self.traces:
                    self.traces.append(proj.to_string())

                    trace_item = pg.PlotDataItem(clickable=True,
                                                 name=pem_file.line_name,
                                                 symbol='o',
                                                 symbolSize=2.5,
                                                 symbolPen=pg.mkPen(self.hole_color, width=1.),
                                                 symbolBrush=pg.mkBrush(self.background_color),
                                                 pen=pg.mkPen(self.hole_color, width=1.1)
                                                 )

                    trace_item.setData(proj.Easting, proj.Northing)
                    trace_item.setZValue(1)
                    self.plan_view.addItem(trace_item)

                    # Add the depth annotation
                    # Add the line name annotation
                    text_item = pg.TextItem(f"{proj.iloc[-1].Relative_depth:g} m",
                                            color=self.hole_color,
                                            anchor=depth_anchor,
                                            # angle=angle
                                            )
                    self.plan_view.addItem(text_item, ignoreBounds=True)
                    text_item.setPos(proj.iloc[-1].Easting,
                                     proj.iloc[-1].Northing)
                    text_item.setParentItem(trace_item)
                    text_item.setFont(QFont("Helvetica", 8, QFont.Normal))
                    text_item.setZValue(2)

            collar = pem_file.get_collar_gps().dropna()
            if collar.empty:
                logger.info(f"No collar GPS in {pem_file.filepath.name}.")
                return

            geometry = BoreholeGeometry(pem_file.collar, pem_file.segments)
            proj = geometry.get_projection(latlon=False)
            if proj.empty:
                logger.info(f"No hole segments in {pem_file.filepath.name}.")
                # Annotation anchor for hole name and depth. Use the azimuth near the collar for the collar name,
                # and the azimuth at the end of the hole for the depth.
                name_anchor = (0.5, 1)
            else:
                name_az = pem_file.segments.df.iloc[0].Azimuth if not pem_file.segments.df.empty else 180
                name_anchor = (0.5, 1) if 90 < name_az < 270 else (0.5, 0)
                depth_az = pem_file.segments.df.iloc[-1].Azimuth if not pem_file.segments.df.empty else 180
                depth_anchor = (0.5, 0) if 90 < depth_az < 270 else (0.5, 1)

                plot_geometry()

            plot_collar()

        # self.line_color = '#2DA8D8FF'
        # self.loop_color = '#2A2B2DFF'
        # self.hole_color = '#D9514EFF'

        with CustomProgressDialog("Plotting PEM files", 0, len(self.pem_files)) as dlg:
            for pem_file in self.pem_files:
                if dlg.wasCanceled():
                    break

                dlg.setLabelText(f"Plotting {pem_file.filepath.name}")
                logger.info(f"Plotting {pem_file.filepath.name}")

                plot_loop()
                if pem_file.is_borehole():
                    plot_hole()
                else:
                    plot_line()
                dlg += 1


class Ruler(pg.LineSegmentROI):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.handlePen = pg.mkPen(self.pen.color())

    def _makePen(self):
        # Generate the pen color for this ROI based on its current state.
        if self.mouseHovering:
            return pg.mkPen(self.pen.color(), width=self.pen.width() + 0.5)
        else:
            return self.pen

    def addHandle(self, info, index=None):
        class CustomHandle(Handle):
            """
            Re-implementing Handle to change the size and color (especially when hovering) of the handles.
            """
            def __init__(self, *args, **kwds):
                Handle.__init__(self, *args, **kwds)

            def hoverEvent(self, ev):
                hover = False
                if not ev.isExit():
                    if ev.acceptDrags(Qt.LeftButton):
                        hover = True
                    for btn in [Qt.LeftButton, Qt.RightButton, Qt.MidButton]:
                        if int(self.acceptedMouseButtons() & btn) > 0 and ev.acceptClicks(btn):
                            hover = True

                if hover:
                    self.currentPen = pg.mkPen(self.pen.color(), width=self.pen.width() + 1.5)
                else:
                    self.currentPen = self.pen
                self.update()

        # Reimplement so a signal can be emitted
        h = CustomHandle(5, typ="r", pen=self.pen, parent=self)
        h.setPos(info['pos'] * self.state['size'])
        info['item'] = h

        h.connectROI(self)
        if index is None:
            self.handles.append(info)
        else:
            self.handles.insert(index, info)

        h.setZValue(self.zValue() + 1)
        h.sigRemoveRequested.connect(self.removeHandle)
        self.stateChanged(finish=True)
        return h


if __name__ == '__main__':
    from src.qt_py import dark_palette
    from src.pem.pem_file import PEMGetter

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    darkmode = True
    if darkmode:
        app.setPalette(dark_palette)
    pg.setConfigOptions(antialias=True)
    pg.setConfigOption('crashWarning', True)
    pg.setConfigOption('background', (66, 66, 66) if darkmode else 'w')
    pg.setConfigOption('foreground', "w" if darkmode else (53, 53, 53))

    getter = PEMGetter()
    files = getter.get_pems(folder=r'Iscaycruz\Loop 1')
    # files = getter.get_pems(folder='Iscaycruz', subfolder='Loop 1')
    # files = getter.get_pems(folder=r'Final folders\PX20002-W01\Final', file='XY.PEM')
    # files = getter.get_pems(client="Iscaycruz", number=10, random=True)

    # m = TileMapViewer()
    m = ContourMapViewer(darkmode=darkmode)
    # m = GPSViewer(darkmode=darkmode)
    # m = Map3DViewer(darkmode=darkmode)
    m.open(files)
    m.show()
    app.processEvents()
    # m.save_img()

    # app.processEvents()
    # cmap.open(files)
    # cmap.channel_list_edit.setText("1, 3, 100, 4")
    # cmap.channel_list_rbtn.setChecked(True)
    # cmap.save_figure()

    app.exec_()
