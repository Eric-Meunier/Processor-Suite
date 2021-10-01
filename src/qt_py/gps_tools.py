import csv
import logging
import os
import sys
from pathlib import Path

import geopandas as gpd
import gpxpy
import pandas as pd
import pyqtgraph as pg
import matplotlib.pyplot as plt
from matplotlib import ticker
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas, \
    NavigationToolbar2QT as NavigationToolbar
from PySide2.QtCore import Qt, Signal, QEvent
from PySide2.QtGui import QColor, QKeySequence, QIntValidator
from PySide2.QtWidgets import (QMainWindow, QMessageBox, QWidget, QFileDialog, QVBoxLayout, QLabel, QApplication,
                               QFrame, QHBoxLayout, QHeaderView, QInputDialog, QPushButton, QTabWidget, QAction,
                               QTableWidgetItem, QShortcut, QMenu, QSizePolicy, QTableWidget, QItemDelegate,
                               QErrorMessage, QSplitter)
from pyproj import CRS
from shapely.geometry import asMultiPoint

from src.gps.gps_editor import TransmitterLoop, SurveyLine, GPXParser, read_gpx, read_kmz
from src.logger import logger
from src.qt_py import (get_icon, NonScientific, read_file, table_to_df, df_to_table, get_line_color, FloatDelegate,
                       clear_table, MapToolbar)
from src.ui.gps_conversion import Ui_GPSConversion
from src.ui.gpx_creator import Ui_GPXCreator
from src.ui.line_adder import Ui_LineAdder
from src.ui.loop_adder import Ui_LoopAdder

logger = logging.getLogger(__name__)
empty_background = QColor(255, 255, 255, 0)


class GPSAdder(QMainWindow):
    """
    Class to help add station GPS to a PEM file. Helps with files that have missing stations numbers or other
    formatting errors.
    """
    accept_sig = Signal(object)

    def __init__(self, darkmode=False):
        super().__init__()
        self.resize(1000, 800)
        self.setWindowIcon(get_icon('gps_adder.png'))

        self.parent = None
        self.darkmode = darkmode
        self.df = None
        self.error = False  # For pending errors
        self.units = None
        self.selection = []
        self.selected_row_info = None
        self.message = QMessageBox()

        self.foreground_color = get_line_color("foreground", "pyqt", self.darkmode)
        self.background_color = get_line_color("background", "pyqt", self.darkmode)

        # Create the plan and section plots
        self.plan_plot = pg.PlotDataItem(clickable=True,
                                         pen=pg.mkPen(self.foreground_color, width=1.),
                                         symbolPen=pg.mkPen(self.foreground_color, width=1.),
                                         symbol='o',
                                         symbolSize=8,
                                         symbolBrush=pg.mkBrush(self.background_color))
        self.plan_plot.sigPointsClicked.connect(self.point_clicked)

        self.section_plot = pg.PlotDataItem(clickable=True,
                                            pen=pg.mkPen(self.foreground_color, width=1.),
                                            symbolPen=pg.mkPen(self.foreground_color, width=1.),
                                            symbol='o',
                                            symbolSize=8,
                                            symbolBrush=pg.mkBrush(self.background_color))
        self.section_plot.sigPointsClicked.connect(self.point_clicked)

        # Highlighting
        highlight_color = get_line_color("single_blue", "pyqt", self.darkmode)
        self.plan_highlight = pg.PlotDataItem(clickable=True,
                                              pen=pg.mkPen(highlight_color, width=2.),
                                              symbolPen=pg.mkPen(highlight_color, width=2.),
                                              symbol='o',
                                              symbolSize=10,
                                              symbolBrush=pg.mkBrush(self.background_color))
        self.plan_highlight.sigPointsClicked.connect(self.point_clicked)
        self.plan_highlight.setZValue(2)
        self.plan_lx = pg.InfiniteLine(movable=False, angle=0, pen=pg.mkPen(highlight_color, width=2.))
        self.plan_lx.setZValue(0)
        self.plan_ly = pg.InfiniteLine(movable=False, angle=90, pen=pg.mkPen(highlight_color, width=2.))
        self.plan_ly.setZValue(0)
        self.section_highlight = pg.PlotDataItem(clickable=True,
                                                 pen=pg.mkPen(highlight_color, width=2.),
                                                 symbolPen=pg.mkPen(highlight_color, width=2.),
                                                 symbol='o',
                                                 symbolSize=10,
                                                 symbolBrush=pg.mkBrush(self.background_color))
        self.section_highlight.sigPointsClicked.connect(self.point_clicked)
        self.section_highlight.setZValue(2)
        self.section_lx = pg.InfiniteLine(movable=False, angle=0, pen=pg.mkPen(highlight_color, width=2.))
        self.section_lx.setZValue(0)
        self.section_ly = pg.InfiniteLine(movable=False, angle=90, pen=pg.mkPen(highlight_color, width=2.))
        self.section_ly.setZValue(0)

    def closeEvent(self, e):
        e.accept()
        self.deleteLater()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Delete:
            self.del_row()

        elif e.key() == Qt.Key_Space:  # Reset the plot ranges
            self.plan_view.autoRange()
            self.section_view.autoRange()

        elif e.key() == Qt.Key_Escape:  # Clear the selection
            self.table.clearSelection()
            if self.plan_lx in self.plan_view.items():
                self.plan_view.removeItem(self.plan_highlight)
                self.plan_view.removeItem(self.plan_lx)
                self.plan_view.removeItem(self.plan_ly)
                self.section_view.removeItem(self.section_highlight)
                self.section_view.removeItem(self.section_lx)
                self.section_view.removeItem(self.section_ly)

    def del_row(self):
        if self.table.selectionModel().hasSelection():
            row = self.table.selectionModel().selectedRows()[0].row()
            self.table.removeRow(row)
            self.plot_table()

            # Select the next row
            if self.table.rowCount() == 0:
                return
            elif row == self.table.rowCount():
                next_row = row - 1
            else:
                next_row = row

            # Highlight the next row
            self.highlight_point(next_row)

            # Color the table if it's LineAdder running
            if 'color_table' in dir(self):
                self.color_table()

    def accept(self):
        """
        Signal slot: Adds the data from the table to the write_widget's (pem_info_widget object) table.
        :return: None
        """
        self.accept_sig.emit(table_to_df(self.table).dropna())
        # self.hide()

        self.close()
        self.deleteLater()

    def clear_table(self):
        self.table.blockSignals(True)
        self.table.clear()
        while self.table.rowCount() > 0:
            self.table.removeRow(0)
        self.table.blockSignals(True)

    def clear_selection(self):
        self.table.clearSelection()
        if self.plan_lx in self.plan_view.items():
            self.plan_view.removeItem(self.plan_highlight)
            self.plan_view.removeItem(self.plan_lx)
            self.plan_view.removeItem(self.plan_ly)
            self.section_view.removeItem(self.section_highlight)
            self.section_view.removeItem(self.section_lx)
            self.section_view.removeItem(self.section_ly)

    def open(self, o, name=''):
        pass

    def open_file_dialog(self):
        default_path = None
        if self.parent:
            default_path = self.parent.project_dir_edit.text()
        file, extension = QFileDialog().getOpenFileName(self, "Open GPS File", default_path, "Text Files (*.TXT);;"
                                                                                             "CSV Files (*.CSV);;"
                                                                                             "GPX Files (*.GPX)")
        if file:
            self.open(file)

    def df_to_table(self, df):
        """
        Add the contents of the data frame to the table
        :param df: pandas pd.DataFrame of the GPS
        :return: None
        """
        self.table.blockSignals(True)

        if df.empty:
            logger.error(f"No GPS found.")
            self.message.error(self, 'Error', 'No GPS was found.')
        else:
            self.clear_table()
            df_to_table(df, self.table)

        self.table.blockSignals(False)

    # def table_to_df(self):
    #     """
    #     Return a data frame from the information in the table
    #     :return: pandas pd.DataFrame
    #     """
    #     # gps = []
    #     # for row in range(self.table.rowCount()):
    #     #     gps_row = list()
    #     #     for col in range(self.table.columnCount()):
    #     #         gps_row.append(self.table.item(row, col).text())
    #     #     gps.append(gps_row)
    #     #
    #     # df = pd.DataFrame(gps, columns=self.df.columns).astype(dtype=self.df.dtypes)
    #     return df

    def refresh_table(self):
        """
        Re-draw the table, resetting all coloring and keeping the vertical scroll bar position the same.
        :return: None
        """
        self.table.blockSignals(True)

        df = table_to_df(self.table)

        # Store vertical scroll bar position to be restored after
        slider_position = self.table.verticalScrollBar().sliderPosition()

        self.df_to_table(df)  # Clears previous contents

        # Restore scroll bar position
        self.table.verticalScrollBar().setSliderPosition(slider_position)

        # Color the table if it's LineAdder running
        if 'color_table' in dir(self):
            self.color_table()

        self.table.blockSignals(False)

    def plot_table(self, preserve_limits=False):
        pass

    def highlight_point(self, row=None):
        pass

    def point_clicked(self, obj, points):
        """
        Signal slot: When a point in the plots is clicked
        :param obj: PlotDataItem, the source object
        :param points: list.
        :return: None
        """
        self.table.blockSignals(True)

        def swap_points():
            """
            Swaps the position of two points on either axes. Creates a data frame from the table, then swaps the
            corresponding rows in the data frame, then re-creates the table and plots the data.
            :return: None
            """
            indexes = self.selection
            # Create the data frame
            df = table_to_df(self.table)
            # Create a copy of the two rows.
            a, b = df.iloc[indexes[0]].copy(), df.iloc[indexes[1]].copy()
            # Allocate the two rows in reverse order
            df.iloc[indexes[0]], df.iloc[indexes[1]] = b, a
            self.df_to_table(df)
            self.plot_table(preserve_limits=True)

        point = points[0]
        # Get the index of the point clicked
        p = point.pos()
        x, y = p.x(), p.y()
        if obj == self.plan_highlight or obj == self.plan_plot:
            lx = np.argwhere(self.plan_plot.getData()[0] == x)
            ly = np.argwhere(self.plan_plot.getData()[1] == y)
        else:
            lx = np.argwhere(self.section_plot.getData()[0] == x)
            ly = np.argwhere(self.section_plot.getData()[1] == y)
        ind = np.intersect1d(lx, ly).tolist()[0]

        # Swap two points when CTRL is pressed when selecting two points
        if keyboard.is_pressed('ctrl'):
            # Reset the selection if two were already selected
            if len(self.selection) == 2:
                self.selection = []
            self.selection.append(ind)
            # print(f'Selected points: {self.selection}')

            if len(self.selection) == 2:
                # print(f"Two points are selected, swapping them...")
                swap_points()
                ind = self.selection[0]
        else:
            # Reset the selection if CTRL isn't pressed
            self.selection = []

        self.table.selectRow(ind)
        self.highlight_point(row=ind)

        self.table.blockSignals(False)

    def cell_changed(self, row, col):
        """
        Signal slot, when a cell is changed, check if it creates any errors. If it does, replace the changed value
        with the value saved in "cell_activate".
        :param row: int
        :param col: int
        """
        def get_errors():
            """
            Count any incorrect data types
            :return: int, number of errors found
            """
            def has_na(row):
                """
                Return True if any cell in the row can't be converted to a float
                :param row: Int: table row to check
                :return: bool
                """
                for col in range(self.table.columnCount()):
                    item = self.table.item(row, col).text()
                    try:
                        float(item)
                    except ValueError:
                        return True
                    finally:
                        if item == 'nan':
                            return True
                return False

            # Count how many rows have entries that can't be forced into a float
            error_count = 0
            if has_na(row):
                error_count += 1
            return error_count

        errors = get_errors()

        # Reject the change if it causes an error.
        if errors > 0:
            logger.info(f"{self.table.item(row, col).text()} is not a number.")
            self.message.critical(self, 'Error', f"{self.table.item(row, col).text()} cannot be converted to a number.")

            self.table.blockSignals(True)
            self.table.setItem(row, col, self.selected_row_info[col])
            self.table.blockSignals(False)
        else:
            self.plot_table()
            self.highlight_point(row=row)

        # Refresh the table if it's LineAdder running
        if 'color_table' in dir(self):
            self.refresh_table()


class LineAdder(GPSAdder, Ui_LineAdder):

    def __init__(self, parent=None, darkmode=False):
        def format_plots():
            self.plan_view.setTitle('Plan View')
            self.plan_view.setAxisItems({'left': NonScientific(orientation='left'),
                                         'bottom': NonScientific(orientation='bottom')})
            self.section_view.setTitle('Elevation View')
            self.section_view.setAxisItems({'left': NonScientific(orientation='left'),
                                            'bottom': NonScientific(orientation='bottom')})
            self.plan_view.setAspectLocked()
            self.section_view.setAspectLocked()

            self.plan_view.hideButtons()  # Hide the little 'A' button at the bottom left
            self.section_view.hideButtons()  # Hide the little 'A' button at the bottom left

            self.plan_view.getAxis('left').enableAutoSIPrefix(enable=False)  # Disables automatic scaling of labels
            self.plan_view.getAxis('bottom').enableAutoSIPrefix(enable=False)  # Disables automatic scaling of labels
            self.section_view.getAxis('left').enableAutoSIPrefix(enable=False)  # Disables automatic scaling of labels
            self.section_view.getAxis('bottom').enableAutoSIPrefix(enable=False)  # Disables automatic scaling of labels
            self.plan_view.getAxis("right").setStyle(showValues=False)  # Disable showing the values of axis
            self.plan_view.getAxis("top").setStyle(showValues=False)  # Disable showing the values of axis
            self.section_view.getAxis("right").setStyle(showValues=False)  # Disable showing the values of axis
            self.section_view.getAxis("top").setStyle(showValues=False)  # Disable showing the values of axis

            self.plan_view.getAxis('right').setWidth(15)  # Move the right edge of the plot away from the window edge
            self.plan_view.showAxis('right', show=True)  # Show the axis edge line
            self.plan_view.showAxis('top', show=True)  # Show the axis edge line
            self.plan_view.showLabel('right', show=False)
            self.plan_view.showLabel('top', show=False)
            self.section_view.getAxis('right').setWidth(15)  # Move the right edge of the plot away from the window edge
            self.section_view.showAxis('right', show=True)  # Show the axis edge line
            self.section_view.showAxis('top', show=True)  # Show the axis edge line
            self.section_view.showLabel('right', show=False)
            self.section_view.showLabel('top', show=False)

        def init_signals():
            self.actionOpen.triggered.connect(self.open_file_dialog)
            self.actionEdit_Names.triggered.connect(self.edit_names)
            self.actionInterp_Null_Elevation.triggered.connect(self.interp_elevation)

            self.button_box.accepted.connect(self.accept)
            self.button_box.rejected.connect(self.close)

            self.table.cellChanged.connect(self.cell_changed)
            self.table.itemSelectionChanged.connect(self.highlight_point)
            self.auto_sort_cbox.toggled.connect(lambda: self.open(self.line))

        super().__init__(darkmode)
        self.setupUi(self)
        self.setWindowTitle('Line Adder')
        self.actionOpen.setIcon(get_icon("open.png"))
        self.actionEdit_Names.setIcon(get_icon("edit.png"))
        self.actionInterp_Null_Elevation.setIcon(get_icon("grid_planner.png"))
        self.status_bar.hide()

        self.parent = parent
        self.line = None
        self.selected_row_info = None
        self.name_edit = None

        # Table
        self.table.setFixedWidth(400)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        self.plan_view.addItem(self.plan_plot)
        self.section_view.addItem(self.section_plot)

        self.plan_view.setFocusPolicy(Qt.StrongFocus)
        self.section_view.setFocusPolicy(Qt.StrongFocus)

        format_plots()
        init_signals()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Delete:
            self.del_row()

        elif e.key() == Qt.Key_Space:  # Reset the plot ranges
            self.plan_view.autoRange()
            self.section_view.autoRange()

        elif e.key() == Qt.Key_Escape:  # Clear the selection
            self.clear_selection()

    def edit_names(self):
        """
        Remove text from station names. Useful for GPX files.
        """
        trunc_amt, _ = QInputDialog().getInt(self, "Edit Station Names", "Amount to truncate:", 1)
        if trunc_amt:
            # Remove any selections/highlights
            self.clear_selection()
            print(f"Truncating {trunc_amt}")
            self.df.Station.loc[:] = self.df.Station.loc[:].map(lambda x: str(x)[trunc_amt:]).astype(int)
            self.df_to_table(self.df)
            self.plot_table(preserve_limits=True)

    def interp_elevation(self):
        """
        Interpolate missing ("0.0") elevation values.
        :return: None
        """
        df = table_to_df(self.table)
        elevation = df.Elevation
        filt = elevation == 0
        interp_elevation = np.interp(df.index, df[~filt.astype(bool)].index, df[~filt.astype(bool)].Elevation)
        df.Elevation = interp_elevation
        self.df_to_table(df)
        self.plot_table(preserve_limits=False)

    def open(self, gps, name=''):
        """
        Add the data frame to GPSAdder. Adds the data to the table and plots it.
        :param gps: Union [filepath; GPS object; pd.DataFrame], Loop to open
        :param name: str, name of the line
        """
        errors = pd.DataFrame()
        if isinstance(gps, str) or isinstance(gps, Path):
            if Path(gps).is_file():
                self.line = SurveyLine(gps)
                errors = self.line.get_errors()
            else:
                raise ValueError(f"{gps} is not a valid file.")
        elif isinstance(gps, SurveyLine):
            self.line = gps
        else:
            raise ValueError(F"{gps} is not a valid input type.")

        if self.line.df.empty:
            logger.critical(f"No GPS found: {self.line.error_msg}.")
            self.message.critical(self, 'Error', f"No GPS found. {self.line.error_msg}.")
            return

        self.setWindowTitle(f'Line Adder - {name}')

        self.clear_table()
        self.units = self.line.get_units()
        self.df = self.line.get_line(sorted=self.auto_sort_cbox.isChecked())
        self.df.loc[:, "Easting":"Elevation"] = self.df.loc[:, "Easting":"Elevation"].astype(float).applymap(
            lambda x: f"{x:.2f}")
        # Convert the column dtypes for when the data is created from the table values
        self.df["Easting"] = pd.to_numeric(self.df["Easting"])
        self.df["Northing"] = pd.to_numeric(self.df["Northing"])
        self.df["Elevation"] = pd.to_numeric(self.df["Elevation"])
        self.df_to_table(self.df)
        self.plot_table()
        self.color_table()
        self.show()

        if not errors.empty:
            logger.warning(f"The following rows could not be parsed:\n\n{errors.to_string()}.")
            self.message.warning(self, 'Parsing Error',
                                 f"The following rows could not be parsed:\n\n{errors.to_string()}")

    def plot_table(self, preserve_limits=False):
        """
        Plot the data from the table to the axes.
        :return: None
        """
        df = table_to_df(self.table)
        if df.empty:
            return
        df['Station'] = df['Station'].astype(int)

        self.plan_plot.setData(df.Easting.to_numpy(), df.Northing.to_numpy())
        self.section_plot.setData(df.Station.to_numpy(), df.Elevation.to_numpy())

    def highlight_point(self, row=None):
        """
        Highlight a scatter point when its row is selected in the table.
        :param row: Int: table row to highlight
        :return: None
        """
        if row is None:
            selected_row = self.table.selectionModel().selectedRows()
            if selected_row:
                row = self.table.selectionModel().selectedRows()[0].row()
            else:
                logger.info(f"No row selected.")
                return

        # Save the information of the row for backup purposes
        self.selected_row_info = [self.table.item(row, j).clone() for j in range(len(self.df.columns))]

        color = get_line_color("red", "pyqt", self.darkmode) if keyboard.is_pressed(
            'ctrl') else get_line_color("single_blue", "pyqt", self.darkmode)

        df = table_to_df(self.table)
        df['Station'] = df['Station'].astype(int)

        # Plot on the plan map
        plan_x, plan_y = df.loc[row, 'Easting'], df.loc[row, 'Northing']

        # Add the over-lying scatter point
        self.plan_highlight.setData([plan_x], [plan_y], symbolPen=pg.mkPen(color, width=1.5))

        # Move the cross hairs and set their color
        self.plan_lx.setPos(plan_y)
        self.plan_lx.setPen(pg.mkPen(color, width=2.))
        self.plan_ly.setPos(plan_x)
        self.plan_ly.setPen(pg.mkPen(color, width=2.))

        # Plot on the section map
        section_x, section_y = df.loc[row, 'Station'], df.loc[row, 'Elevation']

        # Add the over-lying scatter point
        self.section_highlight.setData([section_x], [section_y], symbolPen=pg.mkPen(color, width=1.5))

        # Move the cross hairs and set their color
        self.section_lx.setPos(section_y)
        self.section_lx.setPen(pg.mkPen(color, width=1.5))
        self.section_ly.setPos(section_x)
        self.section_ly.setPen(pg.mkPen(color, width=1.5))

        # Add the infinite lines if they haven't been added yet
        if self.plan_lx not in self.plan_view.items():
            self.plan_view.addItem(self.plan_highlight)
            self.plan_view.addItem(self.plan_lx)
            self.plan_view.addItem(self.plan_ly)
            self.section_view.addItem(self.section_highlight)
            self.section_view.addItem(self.section_lx)
            self.section_view.addItem(self.section_ly)

    def color_table(self):
        """
        Color the foreground of station numbers if they are duplicated, and the background if they are out of order.
        """
        def color_duplicates():
            """
            Color the table rows to indicate duplicate station numbers in the GPS.
            """
            global errors
            stations = []
            for row in range(self.table.rowCount()):
                if self.table.item(row, stations_column):
                    station = self.table.item(row, stations_column).text()
                    if station in stations:
                        other_station_index = stations.index(station)
                        self.table.item(row, stations_column).setForeground(QColor('red'))
                        self.table.item(other_station_index, stations_column).setForeground(QColor('red'))
                        errors += 1
                    # else:
                    #     self.table.item(row, stations_column).setForeground(QColor('lightGray'))
                    stations.append(station)

        def color_order():
            """
            Color the background of the station cells if the station number is out of order
            """
            global errors
            df_stations = table_to_df(self.table).Station.map(
                lambda x: re.search(r'-?\d+', str(x)).group())

            table_stations = df_stations.astype(int).to_list()

            sorted_stations = df_stations.dropna().astype(int).to_list()
            reverse = True if (table_stations[0] > table_stations[-1]) else False
            sorted_stations = sorted(sorted_stations, reverse=reverse)

            purple_color = QColor(get_line_color("purple", "mpl", self.darkmode, alpha=50))
            pink_color = QColor(get_line_color("pink", "mpl", self.darkmode, alpha=50))
            gray_color = QColor(get_line_color("gray", "mpl", self.darkmode, alpha=50))

            for row in range(self.table.rowCount()):
                station_item = self.table.item(row, stations_column)
                station_num = table_stations[row]
                # station_num = re.search('-?\d+', table_stations[row]).group()
                if not station_num and station_num != 0:
                    station_item.setBackground(gray_color)
                else:
                    if int(station_num) > sorted_stations[row]:
                        station_item.setBackground(purple_color)
                        errors += 1
                    elif int(station_num) < sorted_stations[row]:
                        station_item.setBackground(pink_color)
                        errors += 1
                    else:
                        station_item.setBackground(empty_background)

        self.table.blockSignals(True)
        global errors
        errors = 0
        stations_column = self.df.columns.to_list().index('Station')
        color_duplicates()
        color_order()
        if errors > 0:
            self.message.warning(self, "Parsing Errors Found", f"{str(errors)} error(s) found parsing the GPS.")
        # self.errors_label.setText(f"{str(errors)} error(s) ")
        self.table.blockSignals(False)


class LoopAdder(GPSAdder, Ui_LoopAdder):

    def __init__(self, parent=None, darkmode=False):

        def format_plots():
            # Format the plots
            self.plan_view.setTitle('Plan View')
            self.plan_view.setAxisItems({'left': NonScientific(orientation='left'),
                                         'bottom': NonScientific(orientation='bottom')})
            self.section_view.setTitle('Elevation View')

            self.plan_view.hideButtons()
            self.section_view.hideButtons()

            self.plan_view.setAspectLocked()
            self.section_view.getAxis('bottom').setLabel('Index')  # Set the label only for the section X axis

            self.plan_view.getAxis('left').enableAutoSIPrefix(enable=False)  # Disables automatic scaling of labels
            self.plan_view.getAxis('bottom').enableAutoSIPrefix(enable=False)  # Disables automatic scaling of labels
            self.section_view.getAxis('left').enableAutoSIPrefix(enable=False)  # Disables automatic scaling of labels
            self.section_view.getAxis('bottom').enableAutoSIPrefix(enable=False)  # Disables automatic scaling of labels
            self.plan_view.getAxis("right").setStyle(showValues=False)  # Disable showing the values of axis
            self.plan_view.getAxis("top").setStyle(showValues=False)  # Disable showing the values of axis
            self.section_view.getAxis("right").setStyle(showValues=False)  # Disable showing the values of axis
            self.section_view.getAxis("top").setStyle(showValues=False)  # Disable showing the values of axis

            self.plan_view.getAxis('right').setWidth(15)  # Move the right edge of the plot away from the window edge
            self.plan_view.showAxis('right', show=True)  # Show the axis edge line
            self.plan_view.showAxis('top', show=True)  # Show the axis edge line
            self.plan_view.showLabel('right', show=False)
            self.plan_view.showLabel('top', show=False)
            self.section_view.getAxis('right').setWidth(15)  # Move the right edge of the plot away from the window edge
            self.section_view.showAxis('right', show=True)  # Show the axis edge line
            self.section_view.showAxis('top', show=True)  # Show the axis edge line
            self.section_view.showLabel('right', show=False)
            self.section_view.showLabel('top', show=False)

        def init_signals():
            self.actionOpen.triggered.connect(self.open_file_dialog)

            self.button_box.accepted.connect(self.accept)
            self.button_box.rejected.connect(self.close)

            self.table.cellChanged.connect(self.cell_changed)
            self.table.itemSelectionChanged.connect(self.highlight_point)
            self.auto_sort_cbox.toggled.connect(lambda: self.open(self.loop))

        super().__init__(darkmode)
        self.setupUi(self)
        self.parent = parent
        self.darkmode = darkmode

        self.loop = None
        self.selected_row_info = None
        self.setWindowTitle('Loop Adder')
        self.actionOpen.setIcon(get_icon("open.png"))
        self.status_bar.hide()

        self.table.setFixedWidth(400)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        self.plan_view.addItem(self.plan_plot)
        self.section_view.addItem(self.section_plot)
        self.plan_view.setFocusPolicy(Qt.StrongFocus)
        self.section_view.setFocusPolicy(Qt.StrongFocus)

        format_plots()
        init_signals()

    def open(self, gps, name=''):
        """
        Add the data frame to GPSAdder. Adds the data to the table and plots it.
        :param gps: Union (filepath, dataframe), Loop to open
        :param name: str, name of the loop
        """
        errors = pd.DataFrame()
        if isinstance(gps, str):
            if Path(gps).is_file():
                self.loop = TransmitterLoop(gps)
                errors = self.loop.get_errors()
            else:
                raise ValueError(f"{gps} is not a valid file.")
        elif isinstance(gps, TransmitterLoop):
            self.loop = gps
        else:
            raise ValueError(f"{gps} is not a valid input.")

        if self.loop.df.empty:
            logger.critical(f"No GPS found: {self.loop.error_msg}")
            self.message.critical(self, 'Error', f"No GPS found. {self.loop.error_msg}")
            return

        self.setWindowTitle(f'Loop Adder - {name}')

        self.clear_table()
        self.units = self.loop.get_units()
        self.df = self.loop.get_loop(closed=True, sorted=self.auto_sort_cbox.isChecked())
        self.df.loc[:, "Easting":"Elevation"] = self.df.loc[:, "Easting":"Elevation"].astype(float).applymap(
            lambda x: f"{x:.2f}")
        # Convert the column dtypes for when the data is created from the table values
        self.df["Easting"] = pd.to_numeric(self.df["Easting"])
        self.df["Northing"] = pd.to_numeric(self.df["Northing"])
        self.df["Elevation"] = pd.to_numeric(self.df["Elevation"])
        self.df_to_table(self.df)
        self.plot_table()
        self.show()

        if not errors.empty:
            logger.warning(f"The following rows could not be parsed:\n\n{errors.to_string()}")
            self.message.warning(self, 'Parsing Error',
                                 f"The following rows could not be parsed:\n\n{errors.to_string()}")

    def plot_table(self, preserve_limits=False):
        """
        Plot the data from the table to the axes.
        :return: None
        """
        df = table_to_df(self.table)

        if df.empty:
            return

        # Close the loop
        df = df.append(df.iloc[0], ignore_index=True)

        # Plot the plan map
        self.plan_plot.setData(df.Easting.to_numpy(), df.Northing.to_numpy())

        # Plot the sections
        self.section_plot.setData(df.Elevation.to_numpy())

    def highlight_point(self, row=None):
        """
        Highlight a scatter point when its row is selected in the table.
        :param row: Int: table row to highlight
        :return: None
        """
        if row is None:
            selected_row = self.table.selectionModel().selectedRows()
            if selected_row:
                row = self.table.selectionModel().selectedRows()[0].row()
            else:
                logger.info(f"No row selected.")
                return

        # Save the information of the row for backup purposes
        self.selected_row_info = [self.table.item(row, j).clone() for j in range(len(self.df.columns))]

        color = get_line_color("red", "pyqt", self.darkmode) if keyboard.is_pressed(
            'ctrl') else get_line_color("single_blue", "pyqt", self.darkmode)

        df = table_to_df(self.table)

        # Plot on the plan map
        plan_x, plan_y = df.loc[row, 'Easting'], df.loc[row, 'Northing']

        # Add the over-lying scatter point
        self.plan_highlight.setData([plan_x], [plan_y], symbolPen=pg.mkPen(color, width=1.5))

        # Move the cross hairs and set their color
        self.plan_lx.setPos(plan_y)
        self.plan_lx.setPen(pg.mkPen(color, width=2.))
        self.plan_ly.setPos(plan_x)
        self.plan_ly.setPen(pg.mkPen(color, width=2.))

        # Plot on the section map
        section_x, section_y = row, df.loc[row, 'Elevation']

        # Add the over-lying scatter point
        self.section_highlight.setData([section_x], [section_y], symbolPen=pg.mkPen(color, width=1.5))

        # Move the cross hairs and set their color
        self.section_lx.setPos(section_y)
        self.section_lx.setPen(pg.mkPen(color, width=1.5))
        self.section_ly.setPos(section_x)
        self.section_ly.setPen(pg.mkPen(color, width=1.5))

        # Add the infinite lines if they haven't been added yet
        if self.plan_lx not in self.plan_view.items():
            self.plan_view.addItem(self.plan_highlight)
            self.plan_view.addItem(self.plan_lx)
            self.plan_view.addItem(self.plan_ly)
            self.section_view.addItem(self.section_highlight)
            self.section_view.addItem(self.section_lx)
            self.section_view.addItem(self.section_ly)


class CollarPicker(GPSAdder, Ui_LoopAdder):
    accept_sig = Signal(object)

    def __init__(self, parent=None, darkmode=False):
        super().__init__(darkmode)
        self.setupUi(self)
        self.parent = parent

        def format_plots():
                self.plan_view.setTitle('Plan View')
                self.plan_view.setAxisItems({'left': NonScientific(orientation='left'),
                                             'bottom': NonScientific(orientation='bottom')})
                self.section_view.setTitle('Elevation View')

                self.plan_view.setAspectLocked()

                self.plan_view.hideButtons()
                self.section_view.hideButtons()

                self.section_view.getAxis('bottom').setLabel('Index')  # Set the label only for the section X axis

                self.plan_view.getAxis('left').enableAutoSIPrefix(enable=False)  # Disables automatic scaling of labels
                self.plan_view.getAxis('bottom').enableAutoSIPrefix(
                    enable=False)  # Disables automatic scaling of labels
                self.section_view.getAxis('left').enableAutoSIPrefix(
                    enable=False)  # Disables automatic scaling of labels
                self.section_view.getAxis('bottom').enableAutoSIPrefix(
                    enable=False)  # Disables automatic scaling of labels
                self.plan_view.getAxis("right").setStyle(showValues=False)  # Disable showing the values of axis
                self.plan_view.getAxis("top").setStyle(showValues=False)  # Disable showing the values of axis
                self.section_view.getAxis("right").setStyle(showValues=False)  # Disable showing the values of axis
                self.section_view.getAxis("top").setStyle(showValues=False)  # Disable showing the values of axis

                self.plan_view.getAxis('right').setWidth(
                    15)  # Move the right edge of the plot away from the window edge
                self.plan_view.showAxis('right', show=True)  # Show the axis edge line
                self.plan_view.showAxis('top', show=True)  # Show the axis edge line
                self.plan_view.showLabel('right', show=False)
                self.plan_view.showLabel('top', show=False)
                self.section_view.getAxis('right').setWidth(
                    15)  # Move the right edge of the plot away from the window edge
                self.section_view.showAxis('right', show=True)  # Show the axis edge line
                self.section_view.showAxis('top', show=True)  # Show the axis edge line
                self.section_view.showLabel('right', show=False)
                self.section_view.showLabel('top', show=False)

                self.plan_view.getAxis('left').setLabel('Northing', units=None)
                self.plan_view.getAxis('bottom').setLabel('Easting', units=None)

                self.section_view.setLabel('left', f"Elevation", units=None)

        def init_signals():
            self.actionOpen.triggered.connect(self.open_file_dialog)

            self.button_box.accepted.connect(self.accept)
            self.button_box.rejected.connect(self.close)

            self.table.cellChanged.connect(self.cell_changed)
            self.table.itemSelectionChanged.connect(self.highlight_point)

        self.setWindowTitle('Collar Picker')
        self.actionOpen.setIcon(get_icon("open.png"))
        self.status_bar.hide()
        self.menuSettings.deleteLater()

        self.gps_content = None
        self.selected_row_info = None

        self.table.setFixedWidth(400)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().hide()

        # Create the plan and section plots
        self.plan_plot = pg.ScatterPlotItem(clickable=True,
                                            symbol='o',
                                            size=8,
                                            pen=pg.mkPen(self.foreground_color,
                                                         width=1.),
                                            brush=pg.mkBrush(self.background_color))
        self.plan_plot.sigClicked.connect(self.point_clicked)
        self.plan_view.addItem(self.plan_plot)

        self.section_plot = pg.ScatterPlotItem(clickable=True,
                                               symbol='o',
                                               size=8,
                                               pen=pg.mkPen(self.foreground_color,
                                                            width=1.),
                                               brush=pg.mkBrush(self.background_color))
        self.section_plot.sigClicked.connect(self.point_clicked)
        self.section_view.addItem(self.section_plot)

        self.plan_view.setFocusPolicy(Qt.StrongFocus)
        self.section_view.setFocusPolicy(Qt.StrongFocus)

        format_plots()
        init_signals()

    def accept(self):
        selected_row = self.table.currentRow()
        gps = [[self.table.item(selected_row, col).text() for col in range(self.table.columnCount())]]
        print(f"Collar GPS: {gps}")
        self.accept_sig.emit(gps)
        self.close()

    def keyPressEvent(self, e):
        """Re-implement so deselecting cannot be done"""
        if e.key() == Qt.Key_Delete:
            self.del_row()

        elif e.key() == Qt.Key_Space:  # Reset the plot ranges
            self.plan_view.autoRange()
            self.section_view.autoRange()

    def cell_changed(self, row, col):
        # Don't check for errors for CollarPicker.
        pass

    def open(self, gps, name=''):
        """
        Add the data frame to GPSAdder. Adds the data to the table and plots it.
        :param gps: Union (filepath, dataframe), file to open
        :param name: str, name of the loop
        """
        def get_df(gps):
            df = pd.DataFrame()
            if isinstance(gps, str) or isinstance(gps, Path):
                if Path(str(gps)).is_file():
                    if Path(gps).suffix.lower() == '.gpx':
                        # Convert the GPX file to string
                        gps, zone, hemisphere, crs, gpx_errors = GPXParser().get_utm(gps, as_string=True)
                        contents = [c.strip().split() for c in gps]
                    else:
                        contents = read_file(gps, as_list=True)
                    try:
                        df = pd.DataFrame.from_records(contents)
                    except ValueError as e:
                        self.show()
                        self.message.critical(self, f"Parsing Error", str(e))
                        return df
            elif isinstance(gps, list):
                try:
                    df = pd.DataFrame.from_records(gps)
                except ValueError as e:
                    self.show()
                    self.message.critical(self, f"Parsing Error", str(e))
                    return df
            else:
                df = gps

            return df

        self.setWindowTitle(f'Collar Picker - {name}')
        gpx_errors = []
        remove_cols = []
        self.df = get_df(gps)

        if self.df.empty:
            logger.critical(f"No GPS found to Collar Picker.")
            self.message.critical(self, 'Error', f"No GPS found.")
            return
        else:
            self.df = self.df.apply(pd.to_numeric, errors='ignore')

        # self.clear_table()
        self.df_to_table(self.df)
        self.table.selectRow(0)
        self.plot_table()
        self.show()
        if gpx_errors:
            error_str = '\n'.join(gpx_errors)
            self.message.warning(self, "Parsing Errors", f"The following errors occurred parsing the GPS file: "
                                                         f"{error_str}")

    def plot_table(self, preserve_limits=False):
        """
        Plot the data from the table to the axes.
        :return: None
        """
        df = table_to_df(self.table)
        if df.empty:
            return

        self.plan_plot.setData(df.iloc[:, 0].to_numpy(), df.iloc[:, 1].to_numpy())
        self.section_plot.setData(df.index, df.iloc[:, 2].to_numpy())

    def highlight_point(self, row=None):
        """
        Highlight a scatter point when its row is selected in the table.
        :param row: Int: table row to highlight
        :return: None
        """
        if row is None:
            selected_row = self.table.selectionModel().selectedRows()
            if selected_row:
                row = self.table.selectionModel().selectedRows()[0].row()
            else:
                logger.info(f"No row selected.")
                return

        # Save the information of the row for backup purposes
        self.selected_row_info = [self.table.item(row, j).clone() for j in range(len(self.df.columns))]

        df = table_to_df(self.table)

        # Plot on the plan map
        plan_x, plan_y = df.iloc[row, 0], df.iloc[row, 1]

        # Add the over-lying scatter point
        self.plan_highlight.setData([plan_x], [plan_y])

        # Move the cross hairs and set their color
        self.plan_lx.setPos(plan_y)
        self.plan_ly.setPos(plan_x)

        # Plot on the section map
        section_x, section_y = row, df.iloc[row, 2]

        # Add the over-lying scatter point
        self.section_highlight.setData([section_x], [section_y])

        # Move the cross hairs and set their color
        self.section_lx.setPos(section_y)
        self.section_ly.setPos(section_x)

        # Add the infinite lines if they haven't been added yet
        if self.plan_lx not in self.plan_view.items():
            self.plan_view.addItem(self.plan_highlight)
            self.plan_view.addItem(self.plan_lx)
            self.plan_view.addItem(self.plan_ly)
            self.section_view.addItem(self.section_highlight)
            self.section_view.addItem(self.section_lx)
            self.section_view.addItem(self.section_ly)


class ExcelTablePicker(QWidget):
    accept_sig = Signal(object)

    def __init__(self, parent=None):
        super().__init__()
        self.parent = parent
        self.setWindowTitle("Excel Table Picker")
        self.setWindowIcon(get_icon("excel_file.png"))
        self.setLayout(QVBoxLayout())

        self.content = None
        self.easting = None
        self.northing = None
        self.elevation = None
        self.click_count = 0
        self.selected_cells = []
        self.selection_color = QColor(get_line_color("single_blue", "mpl", True))

        self.tables = []
        self.tabs = QTabWidget()
        self.layout().addWidget(QLabel("Sequentially click the Easting, Northing, and Elevation cells."))
        self.layout().addWidget(self.tabs)

        self.selection_text = QLabel("Easting: \nNorthing: \nElevation: ")
        self.layout().addWidget(self.selection_text)

        self.accept_btn = QPushButton("Accept")
        self.reset_btn = QPushButton("Reset")
        self.close_btn = QPushButton("Close")
        btn_frame = QFrame()
        btn_frame.setLayout(QHBoxLayout())
        btn_frame.layout().addWidget(self.accept_btn)
        btn_frame.layout().addWidget(self.reset_btn)
        btn_frame.layout().addWidget(self.close_btn)
        self.layout().addWidget(btn_frame)

        self.accept_btn.clicked.connect(self.accept)
        self.reset_btn.clicked.connect(self.reset)
        self.close_btn.clicked.connect(self.close)

    def reset(self):
        for item in self.selected_cells:
            item.setBackground(empty_background)

        for table in self.tables:
            table.clearSelection()

        self.easting = None
        self.northing = None
        self.elevation = None
        self.selected_cells = []
        self.click_count = 0
        self.selection_text.setText("Easting: \nNorthing: \nElevation: ")

    def accept(self):
        self.accept_sig.emit({"Easting":self.easting, "Northing": self.northing, "Elevation": self.elevation})
        self.close()

    def cell_clicked(self, row, col):
        """
        Signal slot, color the cell and register it's contents when clicked.
        :param row: Int
        :param col: Int
        :return: None
        """
        table = self.tables[self.tabs.currentIndex()]
        item = table.item(row, col)
        value = item.text()
        table.item(row, col).setBackground(self.selection_color)

        if self.click_count == 3:
            self.click_count = 0

        if self.click_count == 0:
            self.easting = value
        elif self.click_count == 1:
            self.northing = value
        else:
            self.elevation = value

        self.selection_text.setText(f"Easting: {self.easting or ''}\nNorthing: {self.northing or ''}\n"
                                    f"Elevation: {self.elevation or ''}")
        self.click_count += 1

        self.selected_cells.append(item)
        if len(self.selected_cells) > 3:
            self.selected_cells[0].setBackground(empty_background)
            self.selected_cells.pop(0)

    def open(self, content):
        """
        :param content: dict or filepath, content of the Excel file (all sheets).
        :return: None
        """
        if not isinstance(content, dict):
            if isinstance(content, Path) or isinstance(content, str):
                content = Path(content)
                if not content.suffix.lower() in [".xls", ".xlsx"]:
                    raise ValueError(f"{content.name} must be an excel file.")
                if not content.is_file():
                    raise ValueError(f"{content} does not exist.")

                content = pd.read_excel(content,
                                        header=None,
                                        sheet_name=None)
        self.content = content

        for i, (sheet, info) in enumerate(self.content.items()):
            table = pg.TableWidget()
            table.setStyleSheet(f"selection-background-color: {self.selection_color};")
            table.setData(info.replace(np.nan, '', regex=True).to_numpy())
            table.cellClicked.connect(self.cell_clicked)
            self.tables.append(table)
            self.tabs.addTab(table, sheet)

        self.show()


class DADSelector(QWidget):
    accept_sig = Signal(object)

    def __init__(self, parent=None):
        super().__init__()
        self.parent = parent
        self.setWindowTitle("DAD Selector")
        self.setWindowIcon(get_icon("excel_file.png"))
        self.setLayout(QVBoxLayout())
        self.message = QMessageBox()

        self.depths = None
        self.azimuths = None
        self.dips = None
        self.selection_count = 0
        self.selected_ranges = []
        self.selection_color = QColor(get_line_color("single_blue", "mpl", True))
        # self.selection_color = QColor('#50C878')

        self.tables = []
        self.tabs = QTabWidget()
        self.layout().addWidget(QLabel(
            "Sequentially double-click the top cell of the Depth, Azimuth, and Dip cell ranges."))
        self.layout().addWidget(self.tabs)

        self.selection_text = QLabel("Depth: \nAzimuth: \nDip: ")
        self.selection_text.setWordWrap(True)
        self.layout().addWidget(self.selection_text)

        self.accept_btn = QPushButton("Accept")
        self.reset_btn = QPushButton("Reset")
        self.close_btn = QPushButton("Close")
        btn_frame = QFrame()
        btn_frame.setLayout(QHBoxLayout())
        btn_frame.layout().addWidget(self.accept_btn)
        btn_frame.layout().addWidget(self.reset_btn)
        btn_frame.layout().addWidget(self.close_btn)
        self.layout().addWidget(btn_frame)

        self.reset_shortcut = QShortcut(QKeySequence("Escape"), self, self.reset)
        self.accept_btn.clicked.connect(self.accept)
        self.reset_btn.clicked.connect(self.reset)
        self.close_btn.clicked.connect(self.close)

    def eventFilter(self, source, event):
        if event.type() == QEvent.MouseButtonRelease:
            table = self.tables[self.tabs.currentIndex()]
            selected_items = table.selectedItems()

            # Remove the 3rd last selected range
            if len(self.selected_ranges) == 3:
                for item in self.selected_ranges[0]:
                    item.setBackground(empty_background)
                self.selected_ranges.pop(0)

            values = []
            for item in selected_items:
                item.setBackground(self.selection_color)
                values.append(item.text())

            if self.selection_count == 3:
                self.selection_count = 0

            if self.selection_count == 0:
                self.depths = values
            elif self.selection_count == 1:
                self.azimuths = values
            else:
                self.dips = values

            self.selection_text.setText(f"Depth: {self.depths or ''}\nAzimuth: {self.azimuths or ''}\n"
                                        f"Dip: {self.dips or ''}")
            self.selection_count += 1
            self.selected_ranges.append(selected_items)

        # return QObject.eventFilter(source, event)
        return QWidget.eventFilter(self, source, event)

    def reset(self):
        for range in self.selected_ranges:
            for item in range:
                item.setBackground(empty_background)

        for table in self.tables:
            table.clearSelection()

        self.depths = None
        self.azimuths = None
        self.dips = None
        self.selected_ranges = []
        self.selection_count = 0
        self.selection_text.setText("Depth: \nAzimuth: \nDip: ")

    def accept(self):
        data = {"Depth": self.depths, "Azimuth": self.azimuths, "Dip": self.dips}
        df = pd.DataFrame(data, dtype=float)
        if not all([d == float for d in df.dtypes]):
            logger.error(f'Data selected are not all numerical values.')
            self.message.information(self, 'Error', f'The data selected are not all numerical values.')
        else:
            self.accept_sig.emit(df)
            self.close()

    def cell_double_clicked(self, row, col):
        """
        Signal slot, range-select all cells below the clicked cell.
        Doesn't work with the selection method, so it is not used. Could be a toggle though.
        :return: None
        """
        table = self.tables[self.tabs.currentIndex()]

        # Remove the 3rd last selected range
        if len(self.selected_ranges) == 3:
            for item in self.selected_ranges[0]:
                item.setBackground(empty_background)
            self.selected_ranges.pop(0)

        values = []
        selected_range = []
        for s_row in range(row, table.rowCount()):
            item = table.item(s_row, col)
            item.setBackground(self.selection_color)
            selected_range.append(item)
            values.append(item.text())

        if self.selection_count == 3:
            self.selection_count = 0

        if self.selection_count == 0:
            self.depths = values
        elif self.selection_count == 1:
            self.azimuths = values
        else:
            self.dips = values

        self.selection_text.setText(f"Depth: {self.depths or ''}\nAzimuth: {self.azimuths or ''}\n"
                                    f"Dip: {self.dips or ''}")
        self.selection_count += 1
        self.selected_ranges.append(selected_range)

    def open(self, filepath):
        """
        :param filepath: str or Path, can be an Excel file, CSV, or txt file.
        :return: None
        """
        filepath = Path(filepath)

        if filepath.suffix == '.xlsx' or filepath.suffix == '.xls':
            content = pd.read_excel(filepath,
                                 header=None,
                                 sheet_name=None)

            for i, (sheet, info) in enumerate(content.items()):
                table = pg.TableWidget()
                table.setData(info.replace(np.nan, '', regex=True).to_numpy())
                self.tables.append(table)
                self.tabs.addTab(table, str(sheet))
        else:
            if filepath.suffix == '.txt' or filepath.suffix == '.dad':
                content = pd.read_csv(filepath,
                                   delim_whitespace=True,
                                   header=None)
            else:
                content = pd.read_csv(filepath,
                                   header=None)

            table = pg.TableWidget()
            table.setData(content.replace(np.nan, '', regex=True).to_numpy())
            self.tables.append(table)
            self.tabs.addTab(table, filepath.name)

        for table in self.tables:
            table.setStyleSheet(f"selection-background-color: {self.selection_color};")
            # table.cellDoubleClicked.connect(self.cell_double_clicked)
            table.setMouseTracking(True)
            table.viewport().installEventFilter(self)

        self.show()


class GPSConversionWidget(QWidget, Ui_GPSConversion):
    accept_signal = Signal(int)

    def __init__(self, parent=None):
        """
        Window for selecting a new CRS (either by drop-down or by EPSG code).
        """
        super().__init__()
        self.setupUi(self)
        self.setWindowIcon(get_icon("gpx_creator.png"))
        self.parent = parent
        self.message = QMessageBox()

        self.convert_to_label.setText('')
        self.current_crs_label.setText('')

        self.init_signals()

    def init_signals(self):
        def toggle_gps_system():
            """
            Toggle the datum and zone combo boxes and change their options based on the selected CRS system.
            """
            current_zone = self.gps_zone_cbox.currentText()
            datum = self.gps_datum_cbox.currentText()
            system = self.gps_system_cbox.currentText()

            if system == '':
                self.gps_zone_cbox.setEnabled(False)
                self.gps_datum_cbox.setEnabled(False)

            elif system == 'Lat/Lon':
                self.gps_datum_cbox.setCurrentText('WGS 1984')
                self.gps_zone_cbox.setCurrentText('')
                self.gps_datum_cbox.setEnabled(False)
                self.gps_zone_cbox.setEnabled(False)

            elif system == 'UTM':
                self.gps_datum_cbox.setEnabled(True)

                if datum == '':
                    self.gps_zone_cbox.setEnabled(False)
                    return
                else:
                    self.gps_zone_cbox.clear()
                    self.gps_zone_cbox.setEnabled(True)

                # NAD 27 and 83 only have zones from 1N to 22N/23N
                if datum == 'NAD 1927':
                    zones = [''] + [f"{num} North" for num in range(1, 23)] + ['59 North', '60 North']
                elif datum == 'NAD 1983':
                    zones = [''] + [f"{num} North" for num in range(1, 24)] + ['59 North', '60 North']
                # WGS 84 has zones from 1N and 1S to 60N and 60S
                else:
                    zones = [''] + [f"{num} North" for num in range(1, 61)] + [f"{num} South" for num in range(1, 61)]

                for zone in zones:
                    self.gps_zone_cbox.addItem(zone)

                # Keep the same zone number if possible
                self.gps_zone_cbox.setCurrentText(current_zone)

        def toggle_crs_rbtn():
            """
            Toggle the radio buttons for the project CRS box, switching between the CRS drop boxes and the EPSG edit.
            """
            if self.crs_rbtn.isChecked():
                # Enable the CRS drop boxes and disable the EPSG line edit
                self.gps_system_cbox.setEnabled(True)
                toggle_gps_system()

                self.epsg_edit.setEnabled(False)
            else:
                # Disable the CRS drop boxes and enable the EPSG line edit
                self.gps_system_cbox.setEnabled(False)
                self.gps_datum_cbox.setEnabled(False)
                self.gps_zone_cbox.setEnabled(False)

                self.epsg_edit.setEnabled(True)

        def check_epsg():
            """
            Try to convert the EPSG code to a Proj CRS object, reject the input if it doesn't work.
            """
            epsg_code = self.epsg_edit.text()
            self.epsg_edit.blockSignals(True)

            if epsg_code:
                try:
                    crs = CRS.from_epsg(epsg_code)
                except Exception as e:
                    logger.critical(str(e))
                    self.message.critical(self, 'Invalid EPSG Code', f"{epsg_code} is not a valid EPSG code.")
                    self.epsg_edit.setText('')
                finally:
                    set_epsg_label()

            self.epsg_edit.blockSignals(False)

        def set_epsg_label():
            """
            Convert the current project CRS combo box values into the EPSG code and set the status bar label.
            """
            epsg_code = self.get_epsg()
            if epsg_code:
                crs = CRS.from_epsg(epsg_code)
                self.convert_to_label.setText(f"{crs.name} ({crs.type_name})")
            else:
                self.convert_to_label.setText('')

        # Add the GPS system and datum drop box options
        gps_systems = ['', 'Lat/Lon', 'UTM']
        for system in gps_systems:
            self.gps_system_cbox.addItem(system)

        datums = ['', 'WGS 1984', 'NAD 1927', 'NAD 1983']
        for datum in datums:
            self.gps_datum_cbox.addItem(datum)

        int_valid = QIntValidator()
        self.epsg_edit.setValidator(int_valid)

        self.gps_system_cbox.currentIndexChanged.connect(toggle_gps_system)
        self.gps_system_cbox.currentIndexChanged.connect(set_epsg_label)
        self.gps_datum_cbox.currentIndexChanged.connect(toggle_gps_system)
        self.gps_datum_cbox.currentIndexChanged.connect(set_epsg_label)
        self.gps_zone_cbox.currentIndexChanged.connect(set_epsg_label)

        self.crs_rbtn.clicked.connect(toggle_crs_rbtn)
        self.crs_rbtn.clicked.connect(set_epsg_label)
        self.epsg_rbtn.clicked.connect(toggle_crs_rbtn)
        self.epsg_rbtn.clicked.connect(set_epsg_label)

        self.epsg_edit.editingFinished.connect(check_epsg)

        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.close)

    def closeEvent(self, e):
        self.deleteLater()
        e.accept()

    def accept(self):
        """
        Signal slot, emit the EPSG code.
        :return: int
        """
        epsg_code = self.get_epsg()
        if epsg_code:
            self.accept_signal.emit(int(epsg_code))
            self.close()
        else:
            logger.error(f"{epsg_code} is not a valid EPSG code.")
            self.message.information(self, 'Invalid CRS', 'The selected CRS is invalid.')

    def open(self, current_crs):
        self.current_crs_label.setText(f"{current_crs.name} ({current_crs.type_name})")
        self.show()

    def get_epsg(self):
        """
        Return the EPSG code currently selected. Will convert the drop boxes to EPSG code.
        :return: str, EPSG code
        """

        def convert_to_epsg():
            """
            Convert and return the EPSG code of the project CRS combo boxes
            :return: str
            """
            system = self.gps_system_cbox.currentText()
            zone = self.gps_zone_cbox.currentText()
            datum = self.gps_datum_cbox.currentText()

            if system == '':
                return None

            elif system == 'Lat/Lon':
                return '4326'

            else:
                if not zone or not datum:
                    return None

                s = zone.split()
                zone_number = int(s[0])
                north = True if s[1] == 'North' else False

                if datum == 'WGS 1984':
                    if north:
                        epsg_code = f'326{zone_number:02d}'
                    else:
                        epsg_code = f'327{zone_number:02d}'
                elif datum == 'NAD 1927':
                    epsg_code = f'267{zone_number:02d}'
                elif datum == 'NAD 1983':
                    epsg_code = f'269{zone_number:02d}'
                else:
                    logger.error(f"{datum} to EPSG code has not been implemented.")
                    return None

                return epsg_code

        if self.epsg_rbtn.isChecked():
            epsg_code = self.epsg_edit.text()
        else:
            epsg_code = convert_to_epsg()

        return epsg_code


class GPXCreator(QMainWindow, Ui_GPXCreator):
    """
    Program to convert a CSV file into a GPX file. The datum of the intput GPS must be NAD 83 or WGS 84.
    Columns of the CSV must be 'Name', 'Comment', 'Easting', 'Northing'.
    """
    def __init__(self, parent=None):
        def init_crs():
            """
            Populate the CRS drop boxes and connect all their signals
            """
            def toggle_gps_system():
                """
                Toggle the datum and zone combo boxes and change their options based on the selected CRS system.
                """
                current_zone = self.gps_zone_cbox.currentText()
                datum = self.gps_datum_cbox.currentText()
                system = self.gps_system_cbox.currentText()

                if system == '':
                    self.gps_zone_cbox.setEnabled(False)
                    self.gps_datum_cbox.setEnabled(False)

                elif system == 'Lat/Lon':
                    self.gps_datum_cbox.setCurrentText('WGS 1984')
                    self.gps_zone_cbox.setCurrentText('')
                    self.gps_datum_cbox.setEnabled(False)
                    self.gps_zone_cbox.setEnabled(False)

                elif system == 'UTM':
                    self.gps_datum_cbox.setEnabled(True)

                    if datum == '':
                        self.gps_zone_cbox.setEnabled(False)
                        return
                    else:
                        self.gps_zone_cbox.clear()
                        self.gps_zone_cbox.setEnabled(True)

                    # NAD 27 and 83 only have zones from 1N to 22N/23N
                    if datum == 'NAD 1927':
                        zones = [''] + [f"{num} North" for num in range(1, 23)] + ['59 North', '60 North']
                    elif datum == 'NAD 1983':
                        zones = [''] + [f"{num} North" for num in range(1, 24)] + ['59 North', '60 North']
                    # WGS 84 has zones from 1N and 1S to 60N and 60S
                    else:
                        zones = [''] + [f"{num} North" for num in range(1, 61)] + [f"{num} South" for num in
                                                                                   range(1, 61)]

                    for zone in zones:
                        self.gps_zone_cbox.addItem(zone)

                    # Keep the same zone number if possible
                    self.gps_zone_cbox.setCurrentText(current_zone)

            def toggle_crs_rbtn():
                """
                Toggle the radio buttons for the project CRS box, switching between the CRS drop boxes and the EPSG edit.
                """
                if self.crs_rbtn.isChecked():
                    # Enable the CRS drop boxes and disable the EPSG line edit
                    self.gps_system_cbox.setEnabled(True)
                    toggle_gps_system()

                    self.epsg_edit.setEnabled(False)
                else:
                    # Disable the CRS drop boxes and enable the EPSG line edit
                    self.gps_system_cbox.setEnabled(False)
                    self.gps_datum_cbox.setEnabled(False)
                    self.gps_zone_cbox.setEnabled(False)

                    self.epsg_edit.setEnabled(True)

            def check_epsg():
                """
                Try to convert the EPSG code to a Proj CRS object, reject the input if it doesn't work.
                """
                epsg_code = self.epsg_edit.text()
                self.epsg_edit.blockSignals(True)

                if epsg_code:
                    try:
                        crs = CRS.from_epsg(epsg_code)
                    except Exception as e:
                        self.message.critical(self, 'Invalid EPSG Code', f"{epsg_code} is not a valid EPSG code.")
                        self.epsg_edit.setText('')
                    finally:
                        set_epsg_label()

                self.epsg_edit.blockSignals(False)

            def set_epsg_label():
                """
                Convert the current project CRS combo box values into the EPSG code and set the status bar label.
                """
                epsg_code = self.get_epsg()
                if epsg_code:
                    crs = CRS.from_epsg(epsg_code)
                    self.epsg_label.setText(f"{crs.name} ({crs.type_name})")
                else:
                    self.epsg_label.setText('')

            # Add the GPS system and datum drop box options
            gps_systems = ['', 'Lat/Lon', 'UTM']
            for system in gps_systems:
                self.gps_system_cbox.addItem(system)

            datums = ['', 'WGS 1984', 'NAD 1927', 'NAD 1983']
            for datum in datums:
                self.gps_datum_cbox.addItem(datum)

            int_valid = QIntValidator()
            self.epsg_edit.setValidator(int_valid)

            # Signals
            # Combo boxes
            self.gps_system_cbox.currentIndexChanged.connect(toggle_gps_system)
            self.gps_system_cbox.currentIndexChanged.connect(set_epsg_label)
            self.gps_datum_cbox.currentIndexChanged.connect(toggle_gps_system)
            self.gps_datum_cbox.currentIndexChanged.connect(set_epsg_label)
            self.gps_zone_cbox.currentIndexChanged.connect(set_epsg_label)

            # Radio buttons
            self.crs_rbtn.clicked.connect(toggle_crs_rbtn)
            self.crs_rbtn.clicked.connect(set_epsg_label)
            self.epsg_rbtn.clicked.connect(toggle_crs_rbtn)
            self.epsg_rbtn.clicked.connect(set_epsg_label)

            self.epsg_edit.editingFinished.connect(check_epsg)

        super().__init__()
        self.parent = parent
        self.setupUi(self)
        self.setWindowTitle("GPX Creator")
        self.setWindowIcon(get_icon('gpx_file.png'))

        self.dialog = QFileDialog()
        self.message = QMessageBox()
        self.setAcceptDrops(True)

        self.filepath = None

        # Status bar
        self.spacer_label = QLabel()
        self.epsg_label = QLabel()
        self.epsg_label.setIndent(5)

        self.status_bar.addPermanentWidget(self.spacer_label, 1)
        self.status_bar.addPermanentWidget(self.epsg_label, 0)

        # Actions
        self.del_file = QAction("&Remove Row", self)
        self.del_file.setShortcut("Del")
        self.del_file.triggered.connect(self.remove_row)
        self.addAction(self.del_file)

        # Buttons
        self.openAction.triggered.connect(self.open_file_dialog)
        self.openAction.setIcon(get_icon("open.png"))
        self.create_csv_template_action.triggered.connect(self.create_csv_template)
        self.create_csv_template_action.setIcon(get_icon("excel_file.png"))
        self.export_gpx_btn.clicked.connect(self.export_gpx)
        # self.auto_name_btn.clicked.connect(self.auto_name)

        init_crs()

    def closeEvent(self, e):
        self.deleteLater()
        e.accept()

    def dragEnterEvent(self, e):
        e.accept()

    def dropEvent(self, e):
        urls = [url.toLocalFile() for url in e.mimeData().urls()]
        self.open(urls[0])

    def dragMoveEvent(self, e):
        urls = [url.toLocalFile() for url in e.mimeData().urls()]
        if len(urls) == 1 and Path(urls[0]).suffix.lower() in ['.csv', '.xlsx']:
            e.accept()
        else:
            e.ignore()

    def open_file_dialog(self):
        """
        Open files through the file dialog
        """
        default_path = None
        if self.parent:
            default_path = self.parent.project_dir_edit.text()

        file = self.dialog.getOpenFileNames(self, 'Open File',
                                            default_path,
                                            filter='CSV files (*.csv);;'
                                                   'Excel files (*.xlsx)')[0]
        if file:
            self.open(file)
        else:
            pass

    def remove_row(self):
        rows = [model.row() for model in self.table.selectionModel().selectedRows()]
        if rows:
            for row in reversed(rows):
                self.table.removeRow(row)

    def create_csv_template(self):
        """
        Create an empty CSV file with the correct columns.
        :return: None
        """
        file = self.dialog.getSaveFileName(self, 'Save File', filter='CSV file (*.csv);; All files(*.*)')[0]
        if file != '':
            with open(file, 'w') as csvfile:
                filewriter = csv.writer(csvfile, delimiter=',',
                                        quotechar='|', quoting=csv.QUOTE_MINIMAL)
                filewriter.writerow(['Easting', 'Northing', 'Comment'])
                os.startfile(file)
        else:
            pass

    def get_epsg(self):
        """
        Return the EPSG code currently selected. Will convert the drop boxes to EPSG code.
        :return: str, EPSG code
        """
        def convert_to_epsg():
            """
            Convert and return the EPSG code of the project CRS combo boxes
            :return: str
            """
            system = self.gps_system_cbox.currentText()
            zone = self.gps_zone_cbox.currentText()
            datum = self.gps_datum_cbox.currentText()

            if system == '':
                return None

            elif system == 'Lat/Lon':
                return '4326'

            else:
                if not zone or not datum:
                    return None

                s = zone.split()
                zone_number = int(s[0])
                north = True if s[1] == 'North' else False

                if datum == 'WGS 1984':
                    if north:
                        epsg_code = f'326{zone_number:02d}'
                    else:
                        epsg_code = f'327{zone_number:02d}'
                elif datum == 'NAD 1927':
                    epsg_code = f'267{zone_number:02d}'
                elif datum == 'NAD 1983':
                    epsg_code = f'269{zone_number:02d}'
                else:
                    logger.info(f"CRS string not implemented.")
                    return None

                return epsg_code

        if self.epsg_rbtn.isChecked():
            epsg_code = self.epsg_edit.text()
        else:
            epsg_code = convert_to_epsg()

        return epsg_code

    def auto_name(self):
        """
        Append the Comment to the Name to create unique names
        """
        if self.table.rowCount() > 0:
            for row in range(self.table.rowCount()):
                name = self.table.item(row, 0).text()
                comment = self.table.item(row, 1).text()

                new_name = f"{name} - {comment}"
                item = QTableWidgetItem(new_name)
                self.table.setItem(row, 0, item)

    def open(self, filepath):
        """
        Add the information from the CSV to the table.
        :param filepath: str, filepath of the CSV or text file to convert to GPX
        :return: None
        """
        def df_to_table(df):
            """
            Write the values in the data frame to the table.
            :param df: dataframe
            """
            self.table.setRowCount(df.shape[0])

            # getting data from df is computationally costly so convert it to array first
            df_array = df.values
            for row in range(df.shape[0]):
                for col in range(df.shape[1]):
                    value = df_array[row, col]
                    item = QTableWidgetItem(str(value))

                    self.table.setItem(row, col, item)

        self.filepath = Path(filepath)

        if str(self.filepath).endswith('csv'):
            data = pd.read_csv(filepath)
        elif str(self.filepath).endswith('xlsx'):
            data = pd.read_excel(filepath)
        else:
            self.message.critical(self, 'Invalid file type', f"{self.filepath.name} is not a valid file.")
            return

        if not all([header in data.columns for header in ['Easting', 'Northing', 'Comment']]):
            self.message.information(self, f"Error parsing {filepath.name}",
                                     "The CSV data columns must have headers 'Easting', 'Northing', and 'Comment'")
            return

        data.loc[:, ['Easting', 'Northing']] = data.loc[:, ['Easting', 'Northing']].astype(float)
        data.loc[:, 'Comment'] = data.loc[:, 'Comment'].astype(str)
        df_to_table(data)

        logger.info(f'Opening {self.filepath.name}')
        self.status_bar.showMessage(f'Opened {self.filepath.name}', 2000)

    def export_gpx(self):
        """
        Save a GPX file from the information in the table.
        :return: None
        """
        def table_to_df():
            """
            Return a data frame from the information in the table
            :return: pandas DataFrame
            """
            gps = []
            for row in range(self.table.rowCount()):
                gps_row = list()
                for col in range(self.table.columnCount()):
                    gps_row.append(self.table.item(row, col).text())
                gps.append(gps_row)

            df = gpd.GeoDataFrame(gps, columns=['Easting', 'Northing', 'Comment'])
            df.loc[:, ['Easting', 'Northing']] = df.loc[:, ['Easting', 'Northing']].astype(float)
            return df

        def row_to_gpx(row):
            """
            Create a gpx waypoint object for each data row
            :param row: series, converted data row
            """
            waypoint = gpxpy.gpx.GPXWaypoint(latitude=row.Northing,
                                             longitude=row.Easting,
                                             name=f"{name}-{row.Comment}",
                                             comment=row.Comment)
            gpx.waypoints.append(waypoint)

        if not self.table.rowCount() > 0:
            return

        name = self.name_edit.text()
        if not name:
            self.message.critical(self, 'Empty name', 'A name must be given.')
            return

        epsg = self.get_epsg()
        if not epsg:
            self.message.critical(self, 'Invalid CRS', 'Input CRS is invalid.')
            return
        else:
            crs = CRS.from_epsg(epsg)

        self.status_bar.showMessage(f"Saving GPX file...")

        default_path = str(self.filepath.parent)
        file = self.dialog.getSaveFileName(self, 'Save File', default_path, filter='GPX file (*.gpx);;')[0]

        if not file:
            self.status_bar.showMessage('Cancelled', 2000)
            return

        logger.info(f"Saving {file}")

        gpx = gpxpy.gpx.GPX()

        # Create a data frame from the table
        data = table_to_df()

        # Create point objects for each coordinate
        mpoints = asMultiPoint(data.loc[:, ['Easting', 'Northing']].to_numpy())
        gdf = gpd.GeoSeries(list(mpoints), crs=crs)

        # Convert to lat lon
        converted_gdf = gdf.to_crs(epsg=4326)
        data['Easting'], data['Northing'] = converted_gdf.map(lambda p: p.x), converted_gdf.map(lambda p: p.y)

        # Create the GPX waypoints
        data.apply(row_to_gpx, axis=1)

        # Save the file
        with open(file, 'w') as f:
            f.write(gpx.to_xml())
        self.status_bar.showMessage('Save complete.', 2000)

        # Open the file
        if self.open_file_cbox.isChecked():
            try:
                os.startfile(file)
            except OSError:
                logger.error(f'No application to open {file}')
                pass


class GPSExtractor(QMainWindow):
    def __init__(self, parent=None, darkmode=False):
        super().__init__()
        self.parent = parent
        self.darkmode = darkmode
        self.setAcceptDrops(True)
        self.setWindowTitle("GPS Extractor")
        self.setWindowIcon(get_icon('gps_extractor.png'))
        self.resize(1200, 600)
        self.statusBar().show()

        self.background_color = get_line_color("background", "mpl", self.darkmode)
        self.foreground_color = get_line_color("foreground", "mpl", self.darkmode)
        self.line_color = get_line_color("green", "mpl", self.darkmode)

        plt.style.use('dark_background' if self.darkmode else 'default')
        plt.rcParams['axes.facecolor'] = self.background_color
        plt.rcParams['figure.facecolor'] = self.background_color

        self.error_msg = QErrorMessage()
        self.central_widget = QWidget()
        splitter = QSplitter()
        self.layout = QHBoxLayout()
        self.layout.addWidget(splitter)
        self.central_widget.setLayout(self.layout)
        self.setCentralWidget(self.central_widget)

        self.open_file_action = QAction("Open File...")
        self.open_file_action.setIcon(get_icon("open.png"))
        self.open_file_action.triggered.connect(self.open_file_dialog)

        self.file_menu = QMenu("File")
        self.file_menu.addAction(self.open_file_action)

        self.menuBar().addMenu(self.file_menu)

        self.figure, self.ax = plt.subplots()
        # self.figure.subplots_adjust(right=0.80)
        self.canvas = FigureCanvas(self.figure)
        self.toolbar = MapToolbar(self.canvas, self)
        self.toolbar.setFixedHeight(30)

        frame = QFrame()
        frame.setLayout(QVBoxLayout())
        frame.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
        frame.layout().setContentsMargins(0, 0, 0, 0)
        frame.setStyleSheet("border: 1px solid black")
        frame.layout().addWidget(self.canvas)
        frame.layout().addWidget(self.toolbar)

        self.crs_label = QLabel()
        self.statusBar().addPermanentWidget(self.crs_label)

        float_delegate = FloatDelegate(2)  # Must keep this reference or else it is garbage collected
        self.table = QTableWidget()
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        # self.table.setItemDelegateForColumn(0, float_delegate)
        # self.table.setItemDelegateForColumn(1, float_delegate)

        splitter.addWidget(frame)
        splitter.addWidget(self.table)

    def dragEnterEvent(self, e):
        e.acceptProposedAction()

    def dragMoveEvent(self, e):
        urls = [Path(url.toLocalFile()) for url in e.mimeData().urls()]
        filepath = Path(urls[0])
        if len(urls) == 1 and filepath.suffix.lower() in [".kmz", ".gpx"]:
            e.accept()
        else:
            e.ignore()

    def dropEvent(self, e):
        filepath = e.mimeData().urls()[0].toLocalFile()
        self.open_file(filepath)

    def open_file_dialog(self):
        if self.parent is not None:
            default = self.parent.project_dir
        else:
            default = ""
        file, ext = QFileDialog.getOpenFileName(self, "Select GPS File", default, "GPX Files (*.GPX);;"
                                                                                  "KMZ Files (*.KMZ);;")
        if file:
            pass

    def open_file(self, filepath):
        filepath = Path(filepath)
        self.setWindowTitle(f"GPS Extractor - {filepath.name}")
        suffix = filepath.suffix.lower()
        if suffix == ".kmz":
            try:
                df, geo_df, crs = read_kmz(filepath)
            except Exception as e:
                self.error_msg.showMessage(str(e))
                return
        elif suffix == ".gpx":
            try:
                df, geo_df, crs = read_gpx(filepath)
            except Exception as e:
                self.error_msg.showMessage(str(e))
                return
        else:
            raise ValueError(f"'{suffix}'' is not a valid filetype.")

        clear_table(self.table)

        self.plot_data(geo_df)
        df_to_table(df.drop(columns=["geometry"]), self.table)
        self.crs_label.setText(f"CRS: {crs.name} ({crs.to_string()})")

    def plot_data(self, geo_df):
        self.ax.clear()
        self.ax.xaxis.set_major_formatter(ticker.StrMethodFormatter('{x:.0f}'))
        self.ax.yaxis.set_major_formatter(ticker.StrMethodFormatter('{x:.0f}'))
        self.ax.set_xlabel("Easting (m)")
        self.ax.set_ylabel("Northing (m)")
        self.ax.xaxis.set_visible(True)  # Required to actually get the labels to show in UTM
        self.ax.yaxis.set_visible(True)
        for tick in self.ax.get_yticklabels():
            tick.set_rotation(45)

        # self.ax.xaxis.set_ticks_position('top')
        # plt.setp(self.ax.get_xticklabels())
        plt.setp(self.ax.get_yticklabels(), va='center')

        # geo_df.plot(column="Name", ax=self.ax, legend=True)
        geo_df:gpd.GeoDataFrame
        geo_df.plot(ax=self.ax, color=self.line_color)
        # Move the legend outside the plot
        # self.ax.get_legend()._loc = 2  # upper left
        # self.ax.get_legend().set_bbox_to_anchor((1, 1))


if __name__ == '__main__':
    from src.qt_py import dark_palette

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    darkmode = False
    if darkmode:
        app.setPalette(dark_palette)

    samples_folder = Path(__file__).parents[2].joinpath('sample_files')

    """ GPS Extractor """
    mw = GPSExtractor(darkmode=darkmode)
    # mw.open_file(samples_folder.joinpath(r"KML Files\BHP Arizona OCLT-1801D.kmz"))
    # mw.open_file(samples_folder.joinpath(r"KML Files\BHP Ocelot 2018.kmz"))
    # mw.open_file(samples_folder.joinpath(r"KML Files\Bonita_Property.kmz"))
    mw.open_file(samples_folder.joinpath(r"KML Files\Prelim Loops from Michel\LOOP_B06.kmz"))
    mw.show()

    """GPS Conversion"""
    # mw = GPSConversionWidget()
    # mw.show()

    """GPX Creator"""
    # gpx_creator = GPXCreator()
    # gpx_creator.show()
    # file = str(Path(__file__).parents[2].joinpath(r'sample_files\GPX files\testing file.csv'))
    # gpx_creator.open(file)
    # gpx_creator.name_edit.setText('Testing line')
    # gpx_creator.gps_system_cbox.setCurrentText('UTM')
    # gpx_creator.gps_datum_cbox.setCurrentText('WGS 1984')
    # gpx_creator.gps_zone_cbox.setCurrentText('37 North')
    # # gpx_creator.export_gpx()

    """Adders"""
    # line_samples_folder = str(Path(Path(__file__).absolute().parents[2]).joinpath(r'sample_files/Line GPS'))
    # loop_samples_folder = str(Path(Path(__file__).absolute().parents[2]).joinpath(r'sample_files/Loop GPS'))
    #
    # # mw = CollarPicker(darkmode=darkmode)
    # # file = r"C:\_Data\2021\TMC\Laurentia\GEN-21-09\GPS\Loop 09_0823.gpx"
    # # mw = LoopAdder(darkmode=darkmode)
    # # file = str(Path(line_samples_folder).joinpath('PRK-LOOP11-LINE9.txt'))
    # # loop = TransmitterLoop(file)
    # mw = LineAdder(darkmode=darkmode)
    # # mw = ExcelTablePicker()
    # # mw = DADSelector()
    # # file = samples_folder.joinpath(r"Segments\BHEM-Belvais-2021-07-22.xlsx")
    # # file = samples_folder.joinpath(r'GPX files\L3100E_0814 (elevation error).gpx')
    # file = r"C:\_Data\2021\Eastern\Maritime Resources\Birchy 2\GPS\L5N.GPX"
    # # file = samples_folder.joinpath(r'Raw Boreholes\OBS-88-027\RAW\Obalski.xlsx')
    # # file = samples_folder.joinpath(r'Raw Boreholes\GEN-21-02\RAW\GEN-21-01_02_04.xlsx')
    # # line = SurveyLine(str(file))
    # mw.open(file)
    # mw.show()

    app.exec_()
