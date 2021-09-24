import logging
import os
import re
import sys
from pathlib import Path

import keyboard
import numpy as np
import pandas as pd
import pyqtgraph as pg
from PySide2.QtCore import Qt, Signal, QEvent, QObject
from PySide2.QtGui import QColor, QKeySequence, QWidget
from PySide2.QtWidgets import (QMainWindow, QMessageBox, QWidget, QFileDialog, QVBoxLayout, QLabel, QApplication,
                               QFrame, QHBoxLayout, QHeaderView, QInputDialog, QPushButton, QTabWidget,
                               QTableWidgetItem, QShortcut)

from src.gps.gps_editor import TransmitterLoop, SurveyLine, GPXParser
from src.qt_py import get_icon, NonScientific, read_file, table_to_df, df_to_table, get_line_color
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


def main():
    from src.pem.pem_getter import PEMGetter
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

    samples_folder = Path(__file__).absolute().parents[2].joinpath(r'sample_files')
    line_samples_folder = str(Path(Path(__file__).absolute().parents[2]).joinpath(r'sample_files/Line GPS'))
    loop_samples_folder = str(Path(Path(__file__).absolute().parents[2]).joinpath(r'sample_files/Loop GPS'))
    # pg = PEMGetter()

    # mw = CollarPicker(darkmode=darkmode)
    # file = r"C:\_Data\2021\TMC\Laurentia\GEN-21-09\GPS\Loop 09_0823.gpx"

    # mw = LoopAdder(darkmode=darkmode)
    # file = str(Path(line_samples_folder).joinpath('PRK-LOOP11-LINE9.txt'))
    # loop = TransmitterLoop(file)

    mw = LineAdder(darkmode=darkmode)
    # mw = ExcelTablePicker()
    # mw = DADSelector()

    # file = samples_folder.joinpath(r"Segments\BHEM-Belvais-2021-07-22.xlsx")
    # file = samples_folder.joinpath(r'GPX files\L3100E_0814 (elevation error).gpx')
    file = r"C:\_Data\2021\Eastern\Maritime Resources\Birchy 2\GPS\L5N.GPX"
    # file = samples_folder.joinpath(r'Raw Boreholes\OBS-88-027\RAW\Obalski.xlsx')
    # file = samples_folder.joinpath(r'Raw Boreholes\GEN-21-02\RAW\GEN-21-01_02_04.xlsx')
    # line = SurveyLine(str(file))

    mw.open(file)
    mw.show()

    app.exec_()


if __name__ == '__main__':
    main()
