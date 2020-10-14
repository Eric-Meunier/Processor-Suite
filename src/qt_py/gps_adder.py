import logging
import os
import re
import sys
from pathlib import Path

import keyboard
import numpy as np
import pandas as pd
import pyqtgraph as pg
from PyQt5 import (QtCore, QtGui, uic)
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (QMainWindow, QApplication, QMessageBox, QTableWidgetItem, QCheckBox,
                             QHeaderView, QLabel)

from src.gps.gps_editor import TransmitterLoop, SurveyLine
from src.pem.pem_file import StationConverter

logger = logging.getLogger(__name__)

# Modify the paths for when the script is being run in a frozen state (i.e. as an EXE)
if getattr(sys, 'frozen', False):
    application_path = os.path.dirname(sys.executable)
    lineAdderCreator = 'qt_ui\\line_adder.ui'
    loopAdderCreator = 'qt_ui\\loop_adder.ui'
    icons_path = 'qt_ui\\icons'
else:
    application_path = os.path.dirname(os.path.abspath(__file__))
    lineAdderCreator = os.path.join(os.path.dirname(application_path), 'qt_ui\\line_adder.ui')
    loopAdderCreator = os.path.join(os.path.dirname(application_path), 'qt_ui\\loop_adder.ui')
    icons_path = os.path.join(os.path.dirname(application_path), "qt_ui\\icons")


# Load Qt ui file into a class
Ui_LineAdder, _ = uic.loadUiType(lineAdderCreator)
Ui_LoopAdder, _ = uic.loadUiType(loopAdderCreator)

pg.setConfigOptions(antialias=True)
pg.setConfigOption('background', 'w')
pg.setConfigOption('foreground', 'k')
pg.setConfigOption('crashWarning', True)


class GPSAdder(QMainWindow):
    """
    Class to help add station GPS to a PEM file. Helps with files that have missing stations numbers or other
    formatting errors.
    """
    accept_sig = QtCore.pyqtSignal(object)

    def __init__(self):
        super().__init__()
        self.resize(1000, 800)
        self.setWindowIcon(QIcon(os.path.join(icons_path, 'gps_adder.png')))

        self.df = None
        self.error = False  # For pending errors

        # Highlighting
        self.plan_highlight = pg.PlotDataItem(clickable=True)
        self.plan_highlight.sigPointsClicked.connect(self.point_clicked)
        self.plan_highlight.setZValue(2)
        self.plan_lx = pg.InfiniteLine(movable=False, angle=0, pen=pg.mkPen('b', width=2.))
        self.plan_lx.setZValue(0)
        self.plan_ly = pg.InfiniteLine(movable=False, angle=90, pen=pg.mkPen('b', width=2.))
        self.plan_ly.setZValue(0)
        self.section_highlight = pg.PlotDataItem(clickable=True)
        self.section_highlight.sigPointsClicked.connect(self.point_clicked)
        self.section_highlight.setZValue(2)
        self.section_lx = pg.InfiniteLine(movable=False, angle=0, pen=pg.mkPen('b', width=2.))
        self.section_lx.setZValue(0)
        self.section_ly = pg.InfiniteLine(movable=False, angle=90, pen=pg.mkPen('b', width=2.))
        self.section_ly.setZValue(0)
        self.selection = []
        self.selected_row_info = None

        self.message = QMessageBox()

    def keyPressEvent(self, e):
        if e.key() == QtCore.Qt.Key_Delete:
            self.del_row()

        elif e.key() == QtCore.Qt.Key_Space:  # Reset the plot ranges
            self.plan_view.autoRange()
            self.section_view.autoRange()

        elif e.key() == QtCore.Qt.Key_Escape:  # Clear the selection
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
        self.accept_sig.emit(self.table_to_df().dropna())
        self.hide()

    def close(self):
        self.clear_table()
        self.hide()

    def clear_table(self):
        self.table.blockSignals(True)
        self.table.clear()
        while self.table.rowCount() > 0:
            self.table.removeRow(0)
        self.table.blockSignals(True)

    def open(self, o, name=''):
        pass

    def df_to_table(self, df):
        """
        Add the contents of the data frame to the table
        :param df: pandas DataFrame of the GPS
        :return: None
        """
        self.table.blockSignals(True)

        def write_row(series):
            """
             Add items from a pandas data frame row to a QTableWidget row
             :param series: pandas Series object
             :return: None
             """
            def series_to_items(x):
                if isinstance(x, float):
                    return QTableWidgetItem(f"{x}")
                    # return QTableWidgetItem(f"{x:.2f}")
                else:
                    return QTableWidgetItem(str(x))

            row_pos = self.table.rowCount()
            # Add a new row to the table
            self.table.insertRow(row_pos)

            items = series.map(series_to_items).to_list()
            # Format each item of the table to be centered
            for m, item in enumerate(items):
                item.setTextAlignment(QtCore.Qt.AlignCenter)
                self.table.setItem(row_pos, m, item)

        if df.empty:
            logger.warning(f"No GPS found.")
            self.message.warning(self, 'Warning', 'No GPS was found')
        else:
            self.clear_table()
            columns = df.columns.to_list()
            self.table.setColumnCount(len(columns))
            self.table.setHorizontalHeaderLabels(columns)
            df.apply(write_row, axis=1)
        self.table.blockSignals(False)

    def table_to_df(self):
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

        df = pd.DataFrame(gps, columns=self.df.columns).astype(dtype=self.df.dtypes)
        return df

    def plot_table(self, preserve_limits=False):
        pass

    def highlight_point(self, row=None):
        pass

    def point_clicked(self, obj, points):
        """
        Signal slot: When a point in the plots is clicked
        :param event: Mouse click event
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
            df = self.table_to_df()
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
            lx = np.argwhere(self.plan_plot.xData == x)
            ly = np.argwhere(self.plan_plot.yData == y)
        else:
            lx = np.argwhere(self.section_plot.xData == x)
            ly = np.argwhere(self.section_plot.yData == y)
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
            self.table.blockSignals(True)
            logger.critical(f"{self.table.item(row, col).text()} is not a number.")
            self.message.critical(self, 'Error', f"{self.table.item(row, col).text()} cannot be converted to a number.")

            self.table.setItem(row, col, self.selected_row_info[col])
            self.table.blockSignals(False)
        else:
            self.plot_table()
            self.highlight_point(row=row)

        # Color the table if it's LineAdder running
        if 'color_table' in dir(self):
            self.color_table()


class LineAdder(GPSAdder, Ui_LineAdder):

    def __init__(self, parent=None):
        super().__init__()
        self.setupUi(self)
        self.parent = parent
        self.line = None
        self.selected_row_info = None
        self.converter = StationConverter()
        self.setWindowTitle('Line Adder')

        # Status bar widgets
        self.auto_sort_cbox = QCheckBox("Automatically Sort Line by Position", self)
        self.auto_sort_cbox.setChecked(True)

        self.errors_label = QLabel('')
        self.errors_label.setIndent(5)

        self.status_bar.addPermanentWidget(self.auto_sort_cbox, 0)
        self.status_bar.addPermanentWidget(QLabel(), 1)
        self.status_bar.addPermanentWidget(self.errors_label, 0)

        # Table
        self.table.setFixedWidth(400)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        # Create the plan and section plots
        self.plan_plot = pg.PlotDataItem(clickable=True)
        self.plan_plot.sigPointsClicked.connect(self.point_clicked)
        self.plan_view.addItem(self.plan_plot)

        self.section_plot = pg.PlotDataItem(clickable=True)
        self.section_plot.sigPointsClicked.connect(self.point_clicked)
        self.section_view.addItem(self.section_plot)

        self.plan_view.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.section_view.setFocusPolicy(QtCore.Qt.StrongFocus)

        # Format the plots
        self.plan_view.setTitle('Plan View')
        self.plan_view.setAxisItems({'left': NonScientific(orientation='left'),
                                     'bottom': NonScientific(orientation='bottom')})
        self.section_view.setTitle('Elevation View')

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

        # self.plan_view.setLabel('left', f"Northing", units='m')
        # self.plan_view.setLabel('bottom', f"Easting", units='m')
        # self.section_view.setLabel('left', f"Elevation", units='m')
        # self.section_view.setLabel('bottom', f"Station", units=None)

        # Signals
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.close)

        self.table.cellChanged.connect(self.cell_changed)
        self.table.itemSelectionChanged.connect(self.highlight_point)
        self.auto_sort_cbox.toggled.connect(lambda: self.open(self.line))

    def keyPressEvent(self, e):
        if e.key() == QtCore.Qt.Key_Delete:
            self.del_row()

        elif e.key() == QtCore.Qt.Key_Space:  # Reset the plot ranges
            self.plan_view.autoRange()
            self.section_view.autoRange()

        elif e.key() == QtCore.Qt.Key_Escape:  # Clear the selection
            self.table.clearSelection()
            if self.plan_lx in self.plan_view.items():
                self.plan_view.removeItem(self.plan_highlight)
                self.plan_view.removeItem(self.plan_lx)
                self.plan_view.removeItem(self.plan_ly)
                self.section_view.removeItem(self.section_highlight)
                self.section_view.removeItem(self.section_lx)
                self.section_view.removeItem(self.section_ly)

    def open(self, o, name=''):
        """
        Add the data frame to GPSAdder. Adds the data to the table and plots it.
        :param o: Union [filepath; GPS object; DataFrame], Loop to open
        :param name: str, name of the line
        """
        errors = pd.DataFrame()
        if isinstance(o, str):
            if Path(o).is_file():
                self.line = SurveyLine(o)
                errors = self.line.get_errors()
            else:
                raise ValueError(f"{o} is not a valid file.")
        elif isinstance(o, SurveyLine):
            self.line = o

        if self.line.df.empty:
            logger.critical(f"No GPS found: {self.line.error_msg}.")
            self.message.critical(self, 'No GPS', f"{self.line.error_msg}.")
            return

        self.setWindowTitle(f'Line Adder - {name}')

        self.clear_table()
        self.df = self.line.get_line(sorted=self.auto_sort_cbox.isChecked())
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
        df = self.table_to_df()
        if df.empty:
            return

        df['Station'] = df['Station'].astype(int)

        # Plot the plan map
        self.plan_plot.setData(df.Easting.to_numpy(), df.Northing.to_numpy(),
                               symbol='o',
                               symbolSize=8,
                               symbolPen=pg.mkPen('k', width=1.),
                               symbolBrush=pg.mkBrush('w'),
                               pen=pg.mkPen('k', width=1.5)
                               )
        # Plot the sections
        self.section_plot.setData(df.Station.to_numpy(), df.Elevation.to_numpy(),
                                  symbol='o',
                                  symbolSize=8,
                                  symbolPen=pg.mkPen('k', width=1.),
                                  symbolBrush=pg.mkBrush('w'),
                                  pen=pg.mkPen('k', width=1.5)
                                  )

        # Set the X and Y labels
        if df.Unit.all() == '0':
            self.plan_view.getAxis('left').setLabel('Northing', units='m')
            self.plan_view.getAxis('bottom').setLabel('Easting', units='m')

            self.section_view.setLabel('left', f"Elevation", units='m')
            self.section_view.setLabel('bottom', f"Station", units='m')

        elif df.Unit.all() == '1':
            self.plan_view.getAxis('left').setLabel('Northing', units='ft')
            self.plan_view.getAxis('bottom').setLabel('Easting', units='ft')

            self.section_view.setLabel('left', f"Elevation", units='ft')
            self.section_view.setLabel('bottom', f"Station", units='ft')
        else:
            self.plan_view.getAxis('left').setLabel('Northing', units=None)
            self.plan_view.getAxis('bottom').setLabel('Easting', units=None)

            self.section_view.setLabel('left', f"Elevation", units=None)
            self.section_view.setLabel('bottom', f"Station", units=None)

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

        color = (255, 0, 0, 150) if keyboard.is_pressed('ctrl') else (0, 0, 255, 150)

        df = self.table_to_df()
        df['Station'] = df['Station'].astype(int)

        # Plot on the plan map
        plan_x, plan_y = df.loc[row, 'Easting'], df.loc[row, 'Northing']

        # Add the over-lying scatter point
        self.plan_highlight.setData([plan_x], [plan_y],
                                    symbol='o',
                                    symbolSize=10,
                                    symbolPen=pg.mkPen(color, width=1.5),
                                    symbolBrush=pg.mkBrush('w'),
                                    )
        # Move the cross hairs and set their color
        self.plan_lx.setPos(plan_y)
        self.plan_lx.setPen(pg.mkPen(color, width=2.))
        self.plan_ly.setPos(plan_x)
        self.plan_ly.setPen(pg.mkPen(color, width=2.))

        # Plot on the section map
        section_x, section_y = df.loc[row, 'Station'], df.loc[row, 'Elevation']

        # Add the over-lying scatter point
        self.section_highlight.setData([section_x], [section_y],
                                       symbol='o',
                                       symbolSize=10,
                                       symbolPen=pg.mkPen(color, width=1.5),
                                       symbolBrush=pg.mkBrush('w'),
                                       )
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
                        self.table.item(row, stations_column).setForeground(QtGui.QColor('red'))
                        self.table.item(other_station_index, stations_column).setForeground(QtGui.QColor('red'))
                        errors += 1
                    else:
                        self.table.item(row, stations_column).setForeground(QtGui.QColor('black'))
                    stations.append(station)

        def color_order():
            """
            Color the background of the station cells if the station number is out of order
            """
            global errors
            df_stations = self.table_to_df().Station.map(lambda x: re.search(r'-?\d+', str(x)).group())

            table_stations = df_stations.astype(int).to_list()

            sorted_stations = df_stations.dropna().astype(int).to_list()
            reverse = True if (table_stations[0] > table_stations[-1]) else False
            sorted_stations = sorted(sorted_stations, reverse=reverse)

            blue_color, red_color = QtGui.QColor('blue'), QtGui.QColor('red')
            blue_color.setAlpha(50)
            red_color.setAlpha(50)

            for row in range(self.table.rowCount()):
                station_item = self.table.item(row, stations_column)
                station_num = table_stations[row]
                # station_num = re.search('-?\d+', table_stations[row]).group()
                if not station_num and station_num != 0:
                    station_item.setBackground(QtGui.QColor('dimgray'))
                else:
                    if int(station_num) > sorted_stations[row]:
                        station_item.setBackground(blue_color)
                        errors += 1
                    elif int(station_num) < sorted_stations[row]:
                        station_item.setBackground(red_color)
                        errors += 1
                    else:
                        station_item.setBackground(QtGui.QColor('white'))

        self.table.blockSignals(True)
        global errors
        errors = 0
        stations_column = self.df.columns.to_list().index('Station')
        color_duplicates()
        color_order()
        self.errors_label.setText(f"{str(errors)} error(s) ")
        self.table.blockSignals(False)


class LoopAdder(GPSAdder, Ui_LoopAdder):

    def __init__(self, parent=None):
        super().__init__()
        self.setupUi(self)
        self.parent = parent
        self.loop = None
        self.selected_row_info = None
        self.setWindowTitle('Loop Adder')

        # Status bar widgets
        self.auto_sort_cbox = QCheckBox("Automatically Sort Loop", self)
        self.auto_sort_cbox.setChecked(True)

        self.status_bar.addPermanentWidget(self.auto_sort_cbox, 0)
        self.status_bar.addPermanentWidget(QLabel(), 1)

        self.table.setFixedWidth(400)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        # Create the plan and section plots
        self.plan_plot = pg.PlotDataItem(clickable=True)
        self.plan_plot.sigPointsClicked.connect(self.point_clicked)
        self.plan_view.addItem(self.plan_plot)

        self.section_plot = pg.PlotDataItem(clickable=True)
        self.section_plot.sigPointsClicked.connect(self.point_clicked)
        self.section_view.addItem(self.section_plot)

        self.plan_view.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.section_view.setFocusPolicy(QtCore.Qt.StrongFocus)

        # Format the plots
        self.plan_view.setTitle('Plan View')
        self.plan_view.setAxisItems({'left': NonScientific(orientation='left'),
                                     'bottom': NonScientific(orientation='bottom')})
        self.section_view.setTitle('Elevation View')

        self.plan_view.setAspectLocked()

        self.plan_view.hideButtons()
        self.section_view.hideButtons()

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

        # Signals
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.close)

        self.table.cellChanged.connect(self.cell_changed)
        self.table.itemSelectionChanged.connect(self.highlight_point)
        self.auto_sort_cbox.toggled.connect(lambda: self.open(self.loop))

    def open(self, o, name=''):
        """
        Add the data frame to GPSAdder. Adds the data to the table and plots it.
        :param o: Union (filepath, dataframe), Loop to open
        :param name: str, name of the loop
        """
        errors = pd.DataFrame()
        if isinstance(o, str):
            if Path(o).is_file():
                self.loop = TransmitterLoop(o)
                errors = self.loop.get_errors()
            else:
                raise ValueError(f"{o} is not a valid file.")
        elif isinstance(o, TransmitterLoop):
            self.loop = o
        else:
            raise ValueError(f"{o} is not a valid input.")

        if self.loop.df.empty:
            logger.critical(f"No GPS found: {self.loop.error_msg}")
            self.message.critical(self, 'No GPS', f"{self.loop.error_msg}")
            return

        self.setWindowTitle(f'Loop Adder - {name}')

        self.clear_table()
        self.df = self.loop.get_loop(closed=True, sorted=self.auto_sort_cbox.isChecked())
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
        df = self.table_to_df()

        if df.empty:
            return

        # Close the loop
        df = df.append(df.iloc[0], ignore_index=True)

        # Plot the plan map
        self.plan_plot.setData(df.Easting.to_numpy(), df.Northing.to_numpy(),
                               symbol='o',
                               symbolSize=8,
                               symbolPen=pg.mkPen('k', width=1.),
                               symbolBrush=pg.mkBrush('w'),
                               pen=pg.mkPen('k', width=1.5)
                               )
        # Plot the sections
        self.section_plot.setData(df.Elevation.to_numpy(),
                                  symbol='o',
                                  symbolSize=8,
                                  symbolPen=pg.mkPen('k', width=1.),
                                  symbolBrush=pg.mkBrush('w'),
                                  pen=pg.mkPen('k', width=1.5)
                                  )

        # Set the X and Y labels
        if df.Unit.all() == '0':
            self.plan_view.getAxis('left').setLabel('Northing', units='m')
            self.plan_view.getAxis('bottom').setLabel('Easting', units='m')

            self.section_view.setLabel('left', f"Elevation", units='m')

        elif df.Unit.all() == '1':
            self.plan_view.getAxis('left').setLabel('Northing', units='ft')
            self.plan_view.getAxis('bottom').setLabel('Easting', units='ft')

            self.section_view.setLabel('left', f"Elevation", units='ft')
        else:
            self.plan_view.getAxis('left').setLabel('Northing', units=None)
            self.plan_view.getAxis('bottom').setLabel('Easting', units=None)

            self.section_view.setLabel('left', f"Elevation", units=None)

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

        color = (255, 0, 0, 150) if keyboard.is_pressed('ctrl') else (0, 0, 255, 150)

        df = self.table_to_df()

        # Plot on the plan map
        plan_x, plan_y = df.loc[row, 'Easting'], df.loc[row, 'Northing']

        # Add the over-lying scatter point
        self.plan_highlight.setData([plan_x], [plan_y],
                                    symbol='o',
                                    symbolSize=10,
                                    symbolPen=pg.mkPen(color, width=1.5),
                                    symbolBrush=pg.mkBrush('w'),
                                    )
        # Move the cross hairs and set their color
        self.plan_lx.setPos(plan_y)
        self.plan_lx.setPen(pg.mkPen(color, width=2.))
        self.plan_ly.setPos(plan_x)
        self.plan_ly.setPen(pg.mkPen(color, width=2.))

        # Plot on the section map
        section_x, section_y = row, df.loc[row, 'Elevation']

        # Add the over-lying scatter point
        self.section_highlight.setData([section_x], [section_y],
                                       symbol='o',
                                       symbolSize=10,
                                       symbolPen=pg.mkPen(color, width=1.5),
                                       symbolBrush=pg.mkBrush('w'),
                                       )
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


class NonScientific(pg.AxisItem):
    def __init__(self, *args, **kwargs):
        super(NonScientific, self).__init__(*args, **kwargs)

    def tickStrings(self, values, scale, spacing):
        return [int(value*1) for value in values]  # This line return the NonScientific notation value

    def logTickStrings(self, values, scale, spacing):
        return [int(value*1) for value in values]  # This line return the NonScientific notation value


def main():
    from src.pem.pem_getter import PEMGetter
    app = QApplication(sys.argv)
    line_samples_folder = str(Path(Path(__file__).absolute().parents[2]).joinpath(r'sample_files/Line GPS'))
    loop_samples_folder = str(Path(Path(__file__).absolute().parents[2]).joinpath(r'sample_files/Loop GPS'))

    mw = LoopAdder()
    # mw = LineAdder()
    mw.show()

    pg = PEMGetter()
    # file = str(Path(line_samples_folder).joinpath('PRK-LOOP11-LINE9.txt'))
    file = str(Path(loop_samples_folder).joinpath('LOOP225Gold.txt'))

    # loop = TransmitterLoop(file)
    # line = SurveyLine(file)

    mw.open(file)

    app.exec_()


if __name__ == '__main__':
    main()