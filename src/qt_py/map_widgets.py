import logging
import os
import re
import sys

import matplotlib.pyplot as plt
import numpy as np
import plotly
import plotly.graph_objects as go
import pyqtgraph as pg
from PyQt5 import (QtGui, QtCore, uic)
from PyQt5.QtCore import QTimer
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtWidgets import (QErrorMessage, QApplication, QWidget, QFileDialog, QMessageBox, QGridLayout,
                             QAction, QMainWindow, QHBoxLayout, QShortcut)
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas, \
    NavigationToolbar2QT as NavigationToolbar

from src.logger import Log
from src.qt_py.custom_qt_widgets import CustomProgressBar
from src.gps.gps_editor import BoreholeGeometry
from src.pem.pem_plotter import ContourMap

logger = logging.getLogger(__name__)

# Modify the paths for when the script is being run in a frozen state (i.e. as an EXE)
if getattr(sys, 'frozen', False):
    application_path = os.path.dirname(sys.executable)
    section3DCreatorFile = 'ui\\3D_section.ui'
    contourMapCreatorFile = 'ui\\contour_map.ui'
    icons_path = 'ui\\icons'
else:
    application_path = os.path.dirname(os.path.abspath(__file__))
    section3DCreatorFile = os.path.join(os.path.dirname(application_path), 'ui\\3D_section.ui')
    contourMapCreatorFile = os.path.join(os.path.dirname(application_path), 'ui\\contour_map.ui')
    icons_path = os.path.join(os.path.dirname(application_path), "ui\\icons")

# Load Qt ui file into a class
Ui_Section3DWidget, _ = uic.loadUiType(section3DCreatorFile)
Ui_ContourMapCreatorFile, _ = uic.loadUiType(contourMapCreatorFile)

pg.setConfigOptions(antialias=True)
pg.setConfigOption('background', 'w')
pg.setConfigOption('foreground', 'k')
pg.setConfigOption('crashWarning', True)


# class Map3DViewer2(QMainWindow):
#
#     def __init__(self, parent=None):
#         super().__init__()
#         self.pem_files = None
#         self.parent = parent
#
#         self.loops = []
#         self.lines = []
#         self.collars = []
#         self.holes = []
#         self.annotations = []
#
#         self.view = pg.opengl.GLViewWidget()
#
#         # self.setWindowTitle("3D Map Viewer")
#         # self.setWindowIcon(QtGui.QIcon(os.path.join(icons_path, '3d_map2.png')))
#         # self.resize(1000, 800)
#         # layout = QGridLayout()
#         # self.setLayout(layout)
#         #
#         # self.save_img_action = QAction('Save Image')
#         # self.save_img_action.setShortcut("Ctrl+S")
#         # self.save_img_action.triggered.connect(self.save_img)
#         # self.copy_image_action = QAction('Copy Image')
#         # self.copy_image_action.setShortcut("Ctrl+C")
#         # self.copy_image_action.triggered.connect(self.copy_img)
#         #
#         # self.file_menu = self.menuBar().addMenu('&File')
#         # self.file_menu.addAction(self.save_img_action)
#         # self.file_menu.addAction(self.copy_image_action)
#         #
#         # self.figure = go.Figure()
#         # self.figure.update_layout(scene=dict(
#         #     xaxis_title='EASTING',
#         #     yaxis_title='NORTHING',
#         #     zaxis_title='ELEVATION',
#         #     aspectmode='data'),
#         #     margin=dict(r=0, b=0, l=0, t=0),
#         # )
#         #
#         # # create an instance of QWebEngineView and set the html code
#         # self.plot_widget = QWebEngineView()
#         # self.setCentralWidget(self.plot_widget)
#
#     def open(self, pem_files):
#         if not isinstance(pem_files, list):
#             pem_files = [pem_files]
#
#         if not pem_files:
#             raise Exception("No files to plot.")
#
#         if any([f.has_any_gps() for f in pem_files]):
#             self.pem_files = pem_files
#             self.plot_pems()
#             self.show()
#         else:
#             raise Exception(f"No GPS to plot.")
#
#     def plot_pems(self):
#
#         def reset_figure():
#             self.figure.data = []
#             self.loops = []
#             self.lines = []
#             self.collars = []
#             self.holes = []
#
#         def plot_loop(pem_file):
#             loop = pem_file.get_loop(closed=True)
#             if loop.to_string() not in self.loops:
#                 self.loops.append(loop.to_string())
#
#                 # Plot the loop in the figure
#                 self.figure.add_trace(go.Scatter3d(x=loop.Easting,
#                                                    y=loop.Northing,
#                                                    z=loop.Elevation,
#                                                    legendgroup='loop',
#                                                    mode='lines',
#                                                    name=f"Loop {pem_file.loop_name}",
#                                                    text=loop.index))
#
#         def plot_line(pem_file):
#             line = pem_file.get_line()
#
#             if line.to_string() not in self.lines:
#                 self.lines.append(line.to_string())
#                 # Plot the line in the figure
#                 self.figure.add_trace(go.Scatter3d(x=line.Easting,
#                                                    y=line.Northing,
#                                                    z=line.Elevation,
#                                                    legendgroup='line',
#                                                    mode='lines+markers',
#                                                    name=pem_file.line_name,
#                                                    text=line.Station
#                                                    ))
#
#                 # if self.label_stations_cbox.isChecked():
#                 #     for row in line.itertuples():
#                 #         self.annotations.append(dict(x=row.Easting,
#                 #                                      y=row.Northing,
#                 #                                      z=row.Elevation,
#                 #                                      ax=0,
#                 #                                      ay=0,
#                 #                                      text=row.Station,
#                 #                                      showarrow=False,
#                 #                                      xanchor="center",
#                 #                                      yanchor="bottom"))
#
#         def plot_hole(pem_file):
#             collar = pem_file.get_collar().dropna()
#             geometry = BoreholeGeometry(pem_file.collar, pem_file.segments)
#             proj = geometry.get_projection(latlon=False)
#
#             if not proj.empty:
#                 if proj.to_string() not in self.holes:
#                     self.holes.append(proj.to_string())
#                     # Plot the line in the figure
#                     self.figure.add_trace(go.Scatter3d(x=proj.Easting,
#                                                        y=proj.Northing,
#                                                        z=proj.Elevation,
#                                                        mode='lines+markers',
#                                                        legendgroup='hole',
#                                                        name=pem_file.line_name,
#                                                        text=proj['Relative_depth']
#                                                        ))
#
#                 else:
#                     return
#
#             elif not collar.empty and collar.to_string() not in self.collars:
#                 self.collars.append(collar.to_string())
#                 self.figure.add_trace(go.Scatter3d(x=collar.Easting,
#                                                    y=collar.Northing,
#                                                    z=collar.Elevation,
#                                                    # legendgroup='hole',
#                                                    name=pem_file.line_name,
#                                                    text=pem_file.line_name
#                                                    ))
#
#         reset_figure()
#
#         # Plot the PEMs
#         for pem_file in self.pem_files:
#             plot_loop(pem_file)
#
#             if not pem_file.is_borehole():
#                 plot_line(pem_file)
#
#             else:
#                 plot_hole(pem_file)
#
#         # Set the style of the markers and lines
#         self.figure.update_traces(marker=dict(size=6,
#                                               line=dict(width=2,
#                                                         color='DarkSlateGrey')),
#                                   line=dict(width=4)
#                                   )
#         # TODO Format the axis ticks
#         self.figure.update_layout(yaxis_tickformat='%')
#
#         # Create the HTML
#         html = '<html><body>'
#         html += plotly.offline.plot(self.figure,
#                                     output_type='div',
#                                     include_plotlyjs='cdn',
#                                     config={'displayModeBar': False}
#                                     )
#         html += '</body></html>'
#
#         t2 = time.time()
#         # Add the plot HTML to be shown in the plot widget
#         self.plot_widget.setHtml(html)
#         print(f'Time to set HTML: {time.time() - t2:.3f}')
#
#     def save_img(self):
#         save_file = QFileDialog.getSaveFileName(self, 'Save Image', 'map.png', 'PNG Files (*.PNG);; All files(*.*)')[0]
#
#         if save_file:
#             size = self.contentsRect()
#             img = QtGui.QPixmap(size.width(), size.height())
#             self.render(img)
#             img.save(save_file)
#         else:
#             pass
#
#     def copy_img(self):
#         size = self.contentsRect()
#         img = QtGui.QPixmap(size.width(), size.height())
#         self.render(img)
#         img.copy(size)
#         QApplication.clipboard().setPixmap(img)


class MapboxViewer(QMainWindow):

    def __init__(self, parent=None):
        """
        Base widget to plot Plotly Mapbox maps in.
        :param parent: Qt parent object
        """
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
        self.setWindowIcon(QtGui.QIcon(os.path.join(icons_path, 'folium.png')))
        self.status_bar = self.statusBar()
        self.status_bar.show()
        # self.resize(1000, 800)

        layout = QHBoxLayout()
        self.setLayout(layout)
        self.layout().setContentsMargins(0, 0, 0, 0)

        self.save_img_action = QAction('Save Image')
        self.save_img_action.setShortcut("Ctrl+S")
        self.save_img_action.triggered.connect(self.save_img)
        self.copy_image_action = QAction('Copy Image')
        self.copy_image_action.setShortcut("Ctrl+C")
        self.copy_image_action.triggered.connect(self.copy_img)

        self.file_menu = self.menuBar().addMenu('&File')
        self.file_menu.addAction(self.save_img_action)
        self.file_menu.addAction(self.copy_image_action)

        self.map_figure = go.Figure(go.Scattermapbox(mode="markers+lines"))

        # create an instance of QWebEngineView and set the html code
        self.map_widget = QWebEngineView()
        self.map_widget.setContentsMargins(0, 0, 0, 0)
        self.layout().addWidget(self.map_widget)
        self.setCentralWidget(self.map_widget)

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


class TileMapViewer(MapboxViewer):

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

        self.resize(1000, 800)

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

        def plot_loop():
            loop = pem_file.loop.to_latlon().get_loop(closed=True).dropna()
            if loop.empty:
                logger.warning(f"No loop GPS in {pem_file.filepath.name}")
                return

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
            line = pem_file.line.to_latlon().get_line().dropna()
            if line.empty:
                logger.warning(f"No line GPS in {pem_file.filepath.name}")
                return

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
            if proj.empty:
                logger.warning(f"Hole projection is empty for {pem_file.filepath.name}")
            collar = pem_file.collar.to_latlon().get_collar().dropna()

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

        bar = CustomProgressBar()
        bar.setMaximum(len(self.pem_files))

        with pg.ProgressDialog("Plotting PEM Files", 0, len(self.pem_files)) as dlg:
            dlg.setBar(bar)
            dlg.setWindowTitle("Plotting PEM Files")

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

        if not all([self.lons, self.lats]):
            logger.error(f"No Lat/Lon GPS after plotting all PEM files.")
            raise Exception(f"No Lat/Lon GPS after plotting all PEM files.")

        # Pass the mapbox token, for access to better map tiles. If none is passed, it uses the free open street map.
        token = open(".mapbox", 'r').read()
        if not token:
            logger.warning(f"No Mapbox token passed.")
            map_style = "open-street-map"
        else:
            map_style = "outdoors"

        # TODO Decide what to do with tokens
        # Format the figure margins and legend
        self.map_figure.update_layout(
            margin={"r": 0,
                    "t": 0,
                    "l": 0,
                    "b": 0},
            legend=dict(
                yanchor="top",
                y=0.99,
                xanchor="left",
                x=0.01,
                bordercolor="Black",
                borderwidth=1
            ),
        )
        # Add the map style and center/zoom the map
        self.map_figure.update_layout(
            mapbox={
                'center': {'lon': np.mean(self.lons), 'lat': np.mean(self.lats)},
                # 'center': {'lon': -73.5673, 'lat': 45.5017},
                'zoom': 13
                },
            autosize=True,
            mapbox_style=map_style,
            mapbox_accesstoken=token)

        # Add the plot HTML to be shown in the plot widget
        self.load_page()


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
        )

        # create an instance of QWebEngineView and set the html code
        self.map_widget = QWebEngineView()
        self.setCentralWidget(self.map_widget)

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
            loop = pem_file.get_loop(closed=True)

            if not loop.empty and loop.to_string() not in self.loops:
                self.loops.append(loop.to_string())

                # Plot the loop in the figure
                self.map_figure.add_trace(go.Scatter3d(x=loop.Easting,
                                                       y=loop.Northing,
                                                       z=loop.Elevation,
                                                       legendgroup=pem_file.loop_name,
                                                       mode='lines',
                                                       name=f"Loop {pem_file.loop_name}",
                                                       text=loop.index))

        def plot_line(pem_file):
            line = pem_file.get_line()

            if not line.empty and line.to_string() not in self.lines:
                self.lines.append(line.to_string())
                # Plot the line in the figure
                self.map_figure.add_trace(go.Scatter3d(x=line.Easting,
                                                       y=line.Northing,
                                                       z=line.Elevation,
                                                       legendgroup=pem_file.loop_name,
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
            collar = pem_file.get_collar().dropna()
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
                                                       legendgroup=pem_file.loop_name,
                                                       name=pem_file.line_name,
                                                       text=proj['Relative_depth']
                                                       ))

            elif not collar.empty and collar.to_string() not in self.collars:
                self.collars.append(collar.to_string())
                self.map_figure.add_trace(go.Scatter3d(x=collar.Easting,
                                                       y=collar.Northing,
                                                       z=collar.Elevation,
                                                       legendgroup=pem_file.loop_name,
                                                       name=pem_file.line_name,
                                                       text=pem_file.line_name
                                                       ))

        # reset_figure()

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
                                                            color='DarkSlateGrey')),
                                      line=dict(width=4)
                                      )
        # TODO Format the axis ticks
        self.map_figure.update_layout(yaxis_tickformat='%',
                                      legend=dict(
                                          yanchor="top",
                                          y=0.99,
                                          xanchor="left",
                                          x=0.01,
                                      )
                                      )

        # Add the plot HTML to be shown in the plot widget
        self.load_page()

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
        self.status_bar.show()
        self.status_bar.showMessage('Image copied to clipboard.', 1000)
        QTimer.singleShot(1000, lambda: self.status_bar.hide())


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
                pem_file = pem_file.average()

        # Either all files must be split or all un-split
        if not all([pem_file.is_split() for pem_file in self.pem_files]):
            for pem_file in self.pem_files:
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
            logger.critical(str(e))
            self.error.showMessage(f"The following error occurred while creating the contour plot:\n{str(e)}")
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
        Save to PDF the current selected channel or a list of channels.
        :return: None
        """
        if self.pem_files:
            default_path = self.pem_files[0].filepath.absolute()
            path, ext = QFileDialog.getSaveFileName(self, 'Save Figure', default_path,
                                                    'PDF Files (*.PDF);;PNG Files (*.PNG);;JPG Files (*.JPG')
            if path:
                # Create a new instance of ContourMap
                cmap_save = ContourMap()
                logger.info(f"Saving PDF to {path}.")
                with PdfPages(path) as pdf:
                    # Print plots from the list of channels if it's enabled
                    if self.channel_list_edit.isEnabled():
                        text = self.channel_list_edit.text()
                        try:
                            channels = [int(re.match('\d+', text)[0]) for text in re.split(',| ', text)]
                            logger.info(f"Saving contour map plots for channels {channels}.")
                        except IndexError:
                            logger.critical(f"No numbers found in the list of channels.")
                            self.error.showMessage(f"No numbers found in the list of channels.")
                            return
                    else:
                        channels = [self.channel_spinbox.value()]

                    # TODO instead of re-plotting, create a copy of the figure with...
                    # # Create a copy of the figure
                    # buf = io.BytesIO()
                    # pickle.dump(self.fem_figure, buf)
                    # buf.seek(0)
                    # save_figure = pickle.load(buf)

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


class GPSViewer(QMainWindow):

    def __init__(self, parent=None):
        super().__init__()

        # Format the window
        self.setWindowTitle(f"GPS Viewer")
        self.setWindowIcon(QtGui.QIcon(os.path.join(icons_path, 'gps_viewer.png')))
        self.setFocusPolicy(QtCore.Qt.StrongFocus)

        layout = QHBoxLayout()
        self.plan_view = pg.PlotWidget()
        self.setCentralWidget(self.plan_view)
        self.setLayout(layout)
        self.layout().setContentsMargins(0, 0, 0, 0)

        self.parent = parent
        self.pem_files = None
        self.status_bar = self.statusBar()
        self.status_bar.hide()

        self.loops = []
        self.lines = []
        self.collars = []
        self.traces = []

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

        self.plan_view.getAxis('right').setWidth(10)  # Move the right edge of the plot away from the window edge
        self.plan_view.showAxis('right', show=True)  # Show the axis edge line
        self.plan_view.showAxis('top', show=True)  # Show the axis edge line
        self.plan_view.showLabel('right', show=False)
        self.plan_view.showLabel('top', show=False)

        # Actions
        self.save_img_action = QShortcut("Ctrl+S", self)
        self.save_img_action.activated.connect(self.save_img)
        self.copy_image_action = QShortcut("Ctrl+C", self)
        self.copy_image_action.activated.connect(self.copy_img)
        self.auto_range_action = QShortcut(" ", self)
        self.auto_range_action.activated.connect(lambda: self.plan_view.autoRange())

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
                text_item = pg.TextItem(str(row.name), color=loop_color, border=None, fill=None, anchor=(0.5, 0.5))
                self.plan_view.addItem(text_item, ignoreBounds=True)
                text_item.setPos(row.Easting, row.Northing)
                text_item.setParentItem(loop_item)
                # text_item.setFont(QtGui.QFont("Helvetica", 8, QtGui.QFont.Normal))
                text_item.setZValue(0)

            loop = pem_file.get_loop(sorted=False, closed=True).dropna()
            if loop.empty:
                logger.warning(f"No loop GPS in {pem_file.filepath.name}.")
                return
            loop_str = loop.to_string()

            if not loop.empty and loop_str not in self.loops:
                self.loops.append(loop_str)

                # Plot the loop line
                loop_item = pg.PlotDataItem(clickable=True,
                                            name=pem_file.loop_name,
                                            pen=pg.mkPen(loop_color, width=1.)
                                            )
                loop_item.setZValue(-1)
                loop_item.setData(loop.Easting, loop.Northing)

                self.plan_view.addItem(loop_item)

                # Plot the annotations
                loop.apply(add_loop_annotation, axis=1)

                # Plot the loop name annotation
                center = pem_file.loop.get_center()
                text_item = pg.TextItem(str(pem_file.loop_name),
                                        color=loop_color,
                                        anchor=(0.5, 0.5),
                                        )
                self.plan_view.addItem(text_item, ignoreBounds=True)
                text_item.setPos(center[0], center[1])
                text_item.setParentItem(loop_item)
                text_item.setFont(QtGui.QFont("Helvetica", 8, QtGui.QFont.Normal))
                text_item.setZValue(0)

        def plot_line():

            # Removed, creates too much lag
            def add_station_annotation(row):
                """Add the station name annotation"""
                text_item = pg.TextItem(str(row.Station),
                                        color=line_color,
                                        anchor=(0, 0.5),
                                        rotateAxis=(row.Easting, row.Northing),
                                        # angle=90
                )
                self.plan_view.addItem(text_item, ignoreBounds=True)
                text_item.setPos(row.Easting, row.Northing)
                text_item.setParentItem(line_item)
                # text_item.setFont(QtGui.QFont("Helvetica", 8, QtGui.QFont.Normal))
                text_item.setZValue(2)

            line = pem_file.get_line().dropna()
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
                                            symbolPen=pg.mkPen(line_color, width=1.),
                                            symbolBrush=pg.mkBrush('w'),
                                            pen=pg.mkPen(line_color, width=1.)
                                            )
                line_item.setData(line.Easting, line.Northing)
                line_item.setZValue(1)

                self.plan_view.addItem(line_item)

                # # Add the station annotations
                # line.apply(add_station_annotation, axis=1)

                # Add the line name annotation
                text_item = pg.TextItem(str(pem_file.line_name),
                                        color=line_color,
                                        anchor=(1, 0.5),
                                        )
                self.plan_view.addItem(text_item, ignoreBounds=True)
                text_item.setPos(line.iloc[line.Station.argmin()].Easting,
                                 line.iloc[line.Station.argmin()].Northing)
                text_item.setParentItem(line_item)
                text_item.setFont(QtGui.QFont("Helvetica", 8, QtGui.QFont.Normal))
                text_item.setZValue(2)

        def plot_hole():

            collar = pem_file.get_collar().dropna()
            if collar.empty:
                logger.warning(f"No collar GPS in {pem_file.filepath.name}.")
                return

            geometry = BoreholeGeometry(pem_file.collar, pem_file.segments)
            proj = geometry.get_projection(latlon=False)
            if proj.empty:
                logger.warning(f"No hole segments in {pem_file.filepath.name}.")
                return

            # Annotation anchor for hole name and depth. Use the azimuth near the collar for the collar name, and the
            # azimuth at the end of the hole for the depth.
            name_az = pem_file.segments.df.iloc[0].Azimuth if not pem_file.segments.df.empty else 180
            name_anchor = (0.5, 1) if 90 < name_az < 270 else (0.5, 0)
            depth_az = pem_file.segments.df.iloc[-1].Azimuth if not pem_file.segments.df.empty else 180
            depth_anchor = (0.5, 0) if 90 < depth_az < 270 else (0.5, 1)

            if collar.to_string() not in self.collars:
                self.collars.append(collar.to_string())

                collar_item = pg.PlotDataItem(clickable=True,
                                              name=pem_file.line_name,
                                              symbol='o',
                                              symbolSize=10,
                                              symbolPen=pg.mkPen(hole_color, width=1.),
                                              symbolBrush=pg.mkBrush('w'),
                                              pen=pg.mkPen(hole_color, width=1.5)
                                              )
                collar_item.setZValue(2)
                # Don't plot the collar here
                collar_item.setData(collar.Easting, collar.Northing)
                self.plan_view.addItem(collar_item)

                # Add the hole name annotation
                text_item = pg.TextItem(f"{pem_file.line_name}",
                                        color=hole_color,
                                        anchor=name_anchor,
                                        # anchor=anchor,
                                        )
                self.plan_view.addItem(text_item, ignoreBounds=True)
                text_item.setPos(collar.iloc[0].Easting,
                                 collar.iloc[0].Northing)
                text_item.setParentItem(collar_item)
                text_item.setFont(QtGui.QFont("Helvetica", 8, QtGui.QFont.Normal))
                text_item.setZValue(2)

            if proj.to_string() not in self.traces:
                self.traces.append(proj.to_string())

                trace_item = pg.PlotDataItem(clickable=True,
                                             name=pem_file.line_name,
                                             symbol='o',
                                             symbolSize=2.5,
                                             symbolPen=pg.mkPen(hole_color, width=1.),
                                             symbolBrush=pg.mkBrush(hole_color),
                                             pen=pg.mkPen(hole_color, width=1.1)
                                             )

                trace_item.setData(proj.Easting, proj.Northing)
                trace_item.setZValue(1)
                self.plan_view.addItem(trace_item)

                # Add the depth annotation
                # Add the line name annotation
                text_item = pg.TextItem(f"{proj.iloc[-1].Relative_depth:g} m",
                                        color=hole_color,
                                        anchor=depth_anchor,
                                        # angle=angle
                                        )
                self.plan_view.addItem(text_item, ignoreBounds=True)
                text_item.setPos(proj.iloc[-1].Easting,
                                 proj.iloc[-1].Northing)
                text_item.setParentItem(trace_item)
                text_item.setFont(QtGui.QFont("Helvetica", 8, QtGui.QFont.Normal))
                text_item.setZValue(2)

        line_color = '#2DA8D8FF'
        loop_color = '#2A2B2DFF'
        hole_color = '#D9514EFF'

        bar = CustomProgressBar()
        bar.setMaximum(len(self.pem_files))

        with pg.ProgressDialog("Plotting PEM files", 0, len(self.pem_files)) as dlg:
            dlg.setWindowTitle("Plotting PEM files")
            dlg.setBar(bar)

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


# class FoliumMap(QMainWindow):
#
#     def __init__(self):
#         super().__init__()
#         self.pem_files = None
#         self.crs = None
#         self.map = None
#         self.win = None
#         # start_location is used as the zoom-point when the map is opened
#         self.start_location = None
#
#         self.error = QErrorMessage()
#         layout = QGridLayout()
#         self.setLayout(layout)
#         self.setWindowTitle('Map')
#         self.setWindowIcon(QtGui.QIcon(os.path.join(icons_path, 'folium.png')))
#
#         self.save_img_action = QAction('Save Image')
#         self.save_img_action.setShortcut("Ctrl+S")
#         self.save_img_action.triggered.connect(self.save_img)
#         self.copy_image_action = QAction('Copy Image')
#         self.copy_image_action.setShortcut("Ctrl+C")
#         self.copy_image_action.triggered.connect(self.copy_img)
#
#         self.file_menu = self.menuBar().addMenu('&File')
#         self.file_menu.addAction(self.save_img_action)
#         self.file_menu.addAction(self.copy_image_action)
#
#         # create an instance of QWebEngineView and set the html code
#         self.web_engine_widget = QWebEngineView()
#         self.setCentralWidget(self.web_engine_widget)
#
#     def open(self, pem_files, crs):
#         self.pem_files = pem_files
#         self.crs = crs
#         self.error = QErrorMessage()
#
#         if self.crs.is_valid():
#             self.plot_pems()
#
#             # Add the map to a QWebEngineView
#             data = io.BytesIO()
#             self.map.save(data, close_file=False)
#             self.web_engine_widget.setHtml(data.getvalue().decode())
#
#             self.show()
#
#     def plot_pems(self):
#
#         def plot_borehole(pem_file):
#             if pem_file.has_collar_gps():
#                 # Add the CRS to the collar and retrieve the lat lon coordinates
#                 pem_file.collar.crs = self.crs
#                 collar = pem_file.collar.to_latlon().df
#
#                 if collar.to_string() not in collars:
#                     collars.append(collar.to_string())
#                     if self.start_location is None:
#                         self.start_location = collar.loc[0, ['Northing', 'Easting']]
#
#                     # Plot the collar
#                     folium.Marker(collar.loc[0, ['Northing', 'Easting']],
#                                   popup=pem_file.line_name,
#                                   tooltip=pem_file.line_name
#                                   ).add_to(collar_group)
#
#         def plot_line(pem_file):
#             if pem_file.has_station_gps():
#                 # Add the CRS to the line and retrieve the lat lon coordinates
#                 pem_file.line.crs = self.crs
#                 line = pem_file.line.to_latlon().df
#
#                 if line.to_string() not in lines:
#                     lines.append(line.to_string())
#                     if self.start_location is None:
#                         self.start_location = line.loc[0, ['Northing', 'Easting']]
#
#                     # Plot the line
#                     folium.PolyLine(locations=line.loc[:, ['Northing', 'Easting']],
#                                     popup=pem_file.line_name,
#                                     tooltip=pem_file.line_name,
#                                     line_opacity=0.5,
#                                     color='blue'
#                                     ).add_to(line_group)
#
#                     # Plot the stations markers
#                     for row in line.itertuples():
#                         folium.Marker((row.Northing, row.Easting),
#                                       popup=row.Station,
#                                       tooltip=row.Station,
#                                       size=10
#                                       ).add_to(station_group)
#
#         def plot_loop(pem_file):
#             if pem_file.has_loop_gps():
#                 # Add the CRS to the loop and retrieve the lat lon coordinates
#                 pem_file.loop.crs = self.crs
#                 loop = pem_file.loop.to_latlon().get_loop(closed=True)
#
#                 if loop.to_string() not in loops:
#                     loops.append(loop.to_string())
#                     if self.start_location is None:
#                         self.start_location = loop.loc[0, ['Northing', 'Easting']]
#                     # Plot loop
#                     folium.PolyLine(locations=loop.loc[:, ['Northing', 'Easting']],
#                                     popup=pem_file.loop_name,
#                                     tooltip=pem_file.loop_name,
#                                     line_opacity=0.5,
#                                     color='magenta'
#                                     ).add_to(loop_group)
#
#         station_group = folium.FeatureGroup(name='Stations')
#         line_group = folium.FeatureGroup(name='Lines')
#         loop_group = folium.FeatureGroup(name='Loop')
#         collar_group = folium.FeatureGroup(name='Collars')
#         loops = []
#         collars = []
#         lines = []
#
#         for pem_file in self.pem_files:
#             if pem_file.is_borehole():
#                 plot_borehole(pem_file)
#             else:
#                 plot_line(pem_file)
#
#             plot_loop(pem_file)
#
#         self.map = folium.Map(location=self.start_location,
#                               zoom_start=15,
#                               zoom_control=False,
#                               control_scale=True,
#                               tiles='OpenStreetMap',
#                               attr='testing attr'
#                               )
#
#         folium.raster_layers.TileLayer('OpenStreetMap').add_to(self.map)
#         folium.raster_layers.TileLayer('Stamen Toner').add_to(self.map)
#         folium.raster_layers.TileLayer('Stamen Terrain').add_to(self.map)
#         folium.raster_layers.TileLayer('Cartodb positron').add_to(self.map)
#         station_group.add_to(self.map)
#         line_group.add_to(self.map)
#         loop_group.add_to(self.map)
#         collar_group.add_to(self.map)
#         folium.LayerControl().add_to(self.map)
#
#     def save_img(self):
#         save_file = QFileDialog.getSaveFileName(self, 'Save Image', 'map.png', 'PNG Files (*.PNG);; All files(*.*)')[0]
#
#         if save_file:
#             size = self.contentsRect()
#             img = QtGui.QPixmap(size.width(), size.height())
#             self.render(img)
#             img.save(save_file)
#         else:
#             pass
#
#     def copy_img(self):
#         size = self.contentsRect()
#         img = QtGui.QPixmap(size.width(), size.height())
#         self.render(img)
#         img.copy(size)
#         QApplication.clipboard().setPixmap(img)


class ContourMapToolbar(NavigationToolbar):
    """
    Custom Matplotlib toolbar for ContourMap.
    """
    # only display the buttons we need
    toolitems = [t for t in NavigationToolbar.toolitems if
                 t[0] in ('Home', 'Back', 'Forward', 'Pan', 'Zoom')]


class NonScientific(pg.AxisItem):
    def __init__(self, *args, **kwargs):
        super(NonScientific, self).__init__(*args, **kwargs)

    def tickStrings(self, values, scale, spacing):
        return [int(value*1) for value in values]  # This line return the NonScientific notation value

    def logTickStrings(self, values, scale, spacing):
        return [int(value*1) for value in values]  # This line return the NonScientific notation value


if __name__ == '__main__':
    from src.pem.pem_getter import PEMGetter

    app = QApplication(sys.argv)

    getter = PEMGetter()
    files = getter.get_pems(client='Kazzinc', number=5)
    # files = getter.get_pems(client='Iscaycruz', subfolder='Sante Est')
    # files = getter.get_pems(client="Iscaycruz", number=10, random=True)

    m = TileMapViewer()
    # m = GPSViewer()
    # m = Map3DViewer()
    m.open(files)
    m.show()

    # map = Map3DViewer()
    # map.show()
    # map.open(files)

    # cmap = ContourMapViewer()
    # cmap.open(files)
    # cmap.show()

    app.exec_()
