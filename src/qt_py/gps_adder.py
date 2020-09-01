import sys
import os
import re
import time
import keyboard
import matplotlib.pyplot as plt
import pandas as pd
import matplotlib
from pathlib import Path
from PyQt5 import (QtCore, QtGui, uic)
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (QMainWindow, QApplication, QMessageBox, QTableWidgetItem, QGridLayout, QCheckBox,
                             QHeaderView, QLabel, QDialogButtonBox, QAbstractItemView, QShortcut)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.ticker import FixedLocator, FormatStrFormatter
from src.gps.gps_editor import TransmitterLoop, SurveyLine
from src.pem.pem_file import StationConverter
from src.mpl.zoom_pan import ZoomPan


# Modify the paths for when the script is being run in a frozen state (i.e. as an EXE)
if getattr(sys, 'frozen', False):
    application_path = sys._MEIPASS
    lineAdderCreator = 'qt_ui\\line_adder.ui'
    loopAdderCreator = 'qt_ui\\loop_adder.ui'
    icons_path = 'icons'
else:
    application_path = os.path.dirname(os.path.abspath(__file__))
    lineAdderCreator = os.path.join(os.path.dirname(application_path), 'qt_ui\\line_adder.ui')
    loopAdderCreator = os.path.join(os.path.dirname(application_path), 'qt_ui\\loop_adder.ui')
    icons_path = os.path.join(os.path.dirname(application_path), "qt_ui\\icons")


# Load Qt ui file into a class
Ui_LineAdder, _ = uic.loadUiType(lineAdderCreator)
Ui_LoopAdder, _ = uic.loadUiType(loopAdderCreator)


class GPSAdder(QMainWindow):
    """
    Class to help add station GPS to a PEM file. Helps with files that have missing stations numbers or other
    formatting errors.
    """
    # matplotlib.style.use('ggplot')
    # matplotlib.style.use('seaborn')
    matplotlib.style.use('fast')

    def __init__(self):
        super().__init__()
        self.resize(1000, 800)
        self.setWindowIcon(QIcon(os.path.join(icons_path, 'gps_adder.png')))

        self.df = None
        self.write_table = None  # QTableWidget, one of the ones in the write_widget
        self.write_widget = None  # PEMInfoWidget object
        self.error = False  # For pending errors

        # Highlighting
        self.plan_highlight = None
        self.plan_lx = None
        self.plan_ly = None
        self.section_highlight = None
        self.section_lx = None
        self.section_ly = None
        self.selection = []

        # self.layout = QGridLayout()
        # self.table = QTableWidget()
        # self.table.setFixedWidth(400)
        # self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        # self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        # self.table.setSelectionMode(QAbstractItemView.SingleSelection)

        self.message = QMessageBox()
        # self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        # self.button_box.setCenterButtons(True)
        # self.button_box.accepted.connect(self.accept)
        # self.button_box.rejected.connect(self.close)

        self.figure = plt.figure()
        self.figure.subplots_adjust(left=0.20, bottom=0.05, right=0.97, top=0.95)
        self.plan_ax = plt.subplot2grid((30, 1), (0, 0), rowspan=19, colspan=1, fig=self.figure)
        self.plan_ax.set_aspect('equal', adjustable='datalim')
        self.plan_ax.use_sticky_edges = False
        self.section_ax = plt.subplot2grid((30, 1), (22, 0), rowspan=7, colspan=1, fig=self.figure)
        self.section_ax.use_sticky_edges = False
        self.canvas = FigureCanvas(self.figure)

        self.zp = ZoomPan()
        self.plan_zoom = self.zp.zoom_factory(self.plan_ax)
        self.plan_pan = self.zp.pan_factory(self.plan_ax)
        self.section_zoom = self.zp.zoom_factory(self.section_ax)
        self.section_pan = self.zp.pan_factory(self.section_ax)

        # self.auto_sort_cbox = QCheckBox("Automatically Sort Line by Position", self)
        # self.auto_sort_cbox.setChecked(True)

        # self.setLayout(self.layout)
        # self.layout.addWidget(self.auto_sort_cbox, 0, 0)
        # self.layout.addWidget(self.table, 1, 0)
        # self.layout.addWidget(self.button_box, 2, 0, 1, 2)
        # self.layout.addWidget(self.canvas, 1, 1)
        # self.canvas_frame.layout().addWidget(self.canvas)
        #
        # self.canvas.mpl_connect('pick_event', self.onpick)
        #
        # self.button_box.rejected.connect(self.close)
        # self.table.cellChanged.connect(self.plot_table)
        # self.table.cellChanged.connect(self.check_table)
        # self.table.itemSelectionChanged.connect(self.highlight_point)

        # self.del_action = QShortcut(QtGui.QKeySequence("Del"), self)
        # self.del_action.activated.connect(self.del_row)

        # self.reset_action = QShortcut(QtGui.QKeySequence(" "), self)
        # self.reset_action.activated.connect(self.plot_table)
        # self.reset_action.activated.connect(self.highlight_point)

        # self.popMenu = QMenu(self)
        # self.popMenu.addAction(self.move_up_action)
        # self.popMenu.addAction(self.move_down_action)

    def keyPressEvent(self, e):
        if e.key() == QtCore.Qt.Key_Delete:
            self.del_row()
        elif e.key() == QtCore.Qt.Key_Space:
            self.plot_table()
            self.highlight_point()

    def del_row(self):
        if self.table.selectionModel().hasSelection():
            row = self.table.selectionModel().selectedRows()[0].row()
            self.table.removeRow(row)
            self.plot_table()
            self.highlight_point(row)

    def close(self):
        # self.write_widget = None
        # self.write_table = None
        self.clear_table()
        self.hide()

    def clear_table(self):
        self.table.blockSignals(True)
        self.table.clear()
        while self.table.rowCount() > 0:
            self.table.removeRow(0)
        self.table.blockSignals(True)

    def reset_range(self):
        """
        Reset the plot limits automatically
        """
        self.plan_ax.relim()
        self.plan_ax.autoscale()

        self.section_ax.relim()
        self.section_ax.autoscale()
        self.canvas.draw()

    def open(self, o):
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
                    return QTableWidgetItem(f"{x:.2f}")
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

    # def onpick(self, event):
    #     """
    #     Signal slot: When a point in the plots is clicked, highlights the associated row in the table.
    #     :param event: Mouse click event
    #     :return: None
    #     """
    #     # Ignore mouse wheel events
    #     if event.mouseevent.button == 'up' or event.mouseevent.button == 'down' or event.mouseevent.button == 2:
    #         return
    #
    #     ind = event.ind[0]
    #     print(f"Point {ind} clicked")
    #
    #     self.table.selectRow(ind)
    #     self.highlight_point(row=ind)

    def onpick(self, event):
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
            points = self.selection
            # Create the data frame
            df = self.table_to_df()
            # Create a copy of the two rows.
            a, b = df.iloc[points[0]].copy(), df.iloc[points[1]].copy()
            # Allocate the two rows in reverse order
            df.iloc[points[0]], df.iloc[points[1]] = b, a
            self.df_to_table(df)
            self.plot_table(preserve_limits=True)

        # Ignore mouse wheel events
        if event.mouseevent.button == 'up' or event.mouseevent.button == 'down' or event.mouseevent.button == 2:
            return
        index = event.ind[0]

        # Swap two points when CTRL is pressed when selecting two points
        if keyboard.is_pressed('ctrl'):
            # Reset the selection if two were already selected
            if len(self.selection) == 2:
                self.selection = []
            self.selection.append(index)
            # print(f'Selected points: {self.selection}')

            if len(self.selection) == 2:
                # print(f"Two points are selected, swapping them...")
                swap_points()
                index = self.selection[0]
        else:
            # Reset the selection if CTRL isn't pressed
            self.selection = []

        self.table.selectRow(index)
        self.highlight_point(row=index)

        self.table.blockSignals(False)

    def highlight_point(self, row=None):
        pass

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

            # Cound how many rows have entries that can't be forced into a float
            error_count = 0
            if has_na(row):
                error_count += 1
            return error_count

        errors = get_errors()

        # Reject the change if it causes an error.
        if errors > 0:
            self.table.blockSignals(True)
            self.message.critical(self, 'Error', "Value cannot be converted to a number")

            item = QTableWidgetItem(self.selected_row_info[col])
            item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.table.setItem(row, col, item)
            self.table.blockSignals(False)
        else:
            self.plot_table()
            self.highlight_point(row=row)

        # Color the table if it's LineAdder running
        if 'color_table' in dir(self):
            self.color_table()
        # self.highlight_point(row=row)

    # def check_table(self):
    #     """
    #     Look for any incorrect data types and create an error if found
    #     :return: None
    #     """
    #
    #     def color_row(row, color):
    #         """
    #         Color the background of each cell of a row in the table
    #         :param row: Int: Row to color
    #         :param color: str
    #         :return: None
    #         """
    #         for col in range(self.table.columnCount()):
    #             self.table.item(row, col).setBackground(QtGui.QColor(color))
    #
    #     def has_na(row):
    #         """
    #         Return True if any cell in the row can't be converted to a float
    #         :param row: Int: table row to check
    #         :return: bool
    #         """
    #         for col in range(self.table.columnCount()):
    #             item = self.table.item(row, col).text()
    #             try:
    #                 float(item)
    #             except ValueError:
    #                 return True
    #             finally:
    #                 if item == 'nan':
    #                     return True
    #         return False
    #
    #     error_count = 0
    #     self.table.blockSignals(True)
    #     for row in range(self.table.rowCount()):
    #         if has_na(row):
    #             color_row(row, 'pink')
    #             error_count += 1
    #         else:
    #             color_row(row, 'white')
    #     self.table.blockSignals(False)
    #     return error_count


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
        self.spacer_label = QLabel('')

        # Format the borders of the items in the status bar
        self.setStyleSheet("QStatusBar::item {border-left: 1px solid gray; border-top: 1px solid gray}")
        self.status_bar.setStyleSheet("border-top: 1px solid gray; border-top: None")

        self.status_bar.addPermanentWidget(self.auto_sort_cbox, 0)
        self.status_bar.addPermanentWidget(self.spacer_label, 1)
        self.status_bar.addPermanentWidget(self.errors_label, 0)

        self.table.setFixedWidth(400)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)

        self.canvas_frame.layout().addWidget(self.canvas)
        self.canvas.mpl_connect('pick_event', self.onpick)
        self.canvas.setFocusPolicy(QtCore.Qt.StrongFocus)

        # Signals
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.close)

        self.table.cellChanged.connect(self.cell_changed)
        self.table.itemSelectionChanged.connect(self.highlight_point)
        self.auto_sort_cbox.toggled.connect(lambda: self.open(self.line))

        self.reset_action = QShortcut(QtGui.QKeySequence(" "), self)
        self.reset_action.activated.connect(self.reset_range)
        # self.reset_action.activated.connect(self.highlight_point)

        # self.status_bar.hide()
        # self.status_bar.addWidget(self.button_box)

    def keyPressEvent(self, e):
        if e.key() == QtCore.Qt.Key_Delete:
            self.del_row()
        # elif e.key() == QtCore.Qt.Key_Space:
        #     print(f"Space key pressed")
        #     self.reset_range()
        #     self.plot_table()
        #     self.highlight_point()

    def del_row(self):
        if self.table.selectionModel().hasSelection():
            row = self.table.selectionModel().selectedRows()[0].row()
            self.table.removeRow(row)
            self.plot_table()
            self.color_table()
            self.highlight_point(row)

    def open(self, o):
        """
        Add the data frame to GPSAdder. Adds the data to the table and plots it.
        :param o: Union, filepath; GPS object; DataFrame; Loop to open
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

        if not self.line:
            return

        if self.line.df.empty:
            return

        self.clear_table()
        self.df = self.line.get_line(sorted=self.auto_sort_cbox.isChecked())
        self.df_to_table(self.df)
        self.plot_table()
        self.color_table()
        self.show()

        if not errors.empty:
            self.message.warning(self, 'Parsing Error',
                                 f"The following rows could not be parsed:\n\n{errors.to_string()}")

    def accept(self):
        """
        Signal slot: Adds the data from the table to the write_widget's (pem_info_widget object) table.
        :return: None
        """
        self.write_widget.fill_gps_table(self.table_to_df().dropna(), self.write_widget.table)
        self.hide()

    def plot_table(self, preserve_limits=False):
        """
        Plot the data from the table to the axes. Ignores any rows that have NaN somewhere in the row.
        :return: None
        """
        if preserve_limits is True:
            plan_xlim, plan_ylim = self.plan_ax.get_xlim(), self.plan_ax.get_ylim()
            section_xlim, section_ylim = self.section_ax.get_xlim(), self.section_ax.get_ylim()

        self.plan_ax.clear()
        self.section_ax.clear()

        df = self.table_to_df()
        df['Station'] = df['Station'].astype(int)

        # Redraw the empty canvas if there is a pending error
        if self.error is True:
            self.canvas.draw()
            return

        # Plot the plan map
        df.plot(x='Easting', y='Northing',
                ax=self.plan_ax,
                color='dimgray',
                zorder=0,
                legend=False
                )
        # Plot the stations on the plan map
        df.plot.scatter(x='Easting', y='Northing',
                        ax=self.plan_ax,
                        color='w',
                        edgecolors='dimgray',
                        zorder=1,
                        legend=False,
                        picker=True
                        )
        # Plot the sections
        df.plot(x='Station', y='Elevation',
                ax=self.section_ax,
                color='dimgray',
                zorder=0,
                legend=False
                )

        self.plan_ax.ticklabel_format(axis='both', style='plain', useOffset=False)
        # self.section_ax.xaxis.grid(True, which='minor')
        self.section_ax.xaxis.set_minor_locator(FixedLocator(df.Station.to_list()))

        # Plot the stations on the section map
        df.plot.scatter(x='Station', y='Elevation',
                        ax=self.section_ax,
                        color='w',
                        edgecolors='dimgray',
                        zorder=1,
                        legend=False,
                        picker=True
                        )

        if preserve_limits is True:
            self.plan_ax.set_xlim(plan_xlim)
            self.plan_ax.set_ylim(plan_ylim)
            self.section_ax.set_xlim(section_xlim)
            self.section_ax.set_ylim(section_ylim)
        else:
            # Add flat elevation for the section plot limits
            self.section_ax.set_ylim(self.section_ax.get_ylim()[0] - 5,
                                     self.section_ax.get_ylim()[1] + 5)
        # self.plan_ax.set_yticklabels(self.plan_ax.get_yticklabels(), rotation=0, ha='center')
        self.canvas.draw()

    def highlight_point(self, row=None):
        """
        Highlight a scatter point when it's row is selected in the table
        :param row: Int: table row to highlight
        :return: None
        """

        def reset_highlight():
            """
            Remove the crosshairs
            """
            self.plan_highlight.remove()
            self.plan_lx.remove()
            self.plan_ly.remove()
            self.section_highlight.remove()
            self.section_lx.remove()
            self.section_ly.remove()

            self.plan_highlight = None
            self.plan_lx = None
            self.plan_ly = None
            self.section_highlight = None
            self.section_lx = None
            self.section_ly = None

        if row is None:
            selected_row = self.table.selectionModel().selectedRows()
            if selected_row:
                row = self.table.selectionModel().selectedRows()[0].row()
            else:
                print(f"No row selected")
                return

        # Save the information of the row for backup purposes
        self.selected_row_info = [self.table.item(row, j).text() for j in range(len(self.df.columns))]

        # Remove previously plotted selection
        if self.plan_highlight:
            reset_highlight()

        color, light_color = ('blue', 'lightsteelblue') if keyboard.is_pressed('ctrl') is False else ('red', 'pink')

        df = self.table_to_df()
        df['Station'] = df['Station'].astype(int)

        # Plot on the plan map
        plan_x, plan_y = df.loc[row, 'Easting'], df.loc[row, 'Northing']
        self.plan_highlight = self.plan_ax.scatter([plan_x], [plan_y],
                                                   color=light_color,
                                                   edgecolors=color,
                                                   zorder=3,
                                                   )
        self.plan_lx = self.plan_ax.axhline(plan_y, color=color, alpha=0.5)
        self.plan_ly = self.plan_ax.axvline(plan_x, color=color, alpha=0.5)

        # Plot on the section map
        section_x, section_y = df.loc[row, 'Station'], df.loc[row, 'Elevation']
        self.section_highlight = self.section_ax.scatter([section_x], [section_y],
                                                         color=light_color,
                                                         edgecolors=color,
                                                         zorder=3,
                                                         )
        self.section_lx = self.section_ax.axhline(section_y, color=color, alpha=0.5)
        self.section_ly = self.section_ax.axvline(section_x, color=color, alpha=0.5)
        self.canvas.draw()

    # def cell_changed(self, row, col):
    #     """
    #     Signal slot, when a cell is changed, check if it creates any errors. If it does, replace the changed value
    #     with the value saved in "cell_activate".
    #     :param row: int
    #     :param col: int
    #     """
    #
    #     def get_errors():
    #         """
    #         Count any incorrect data types
    #         :return: int, number of errors found
    #         """
    #
    #         def has_na(row):
    #             """
    #             Return True if any cell in the row can't be converted to a float
    #             :param row: Int: table row to check
    #             :return: bool
    #             """
    #             for col in range(self.table.columnCount()):
    #                 item = self.table.item(row, col).text()
    #                 try:
    #                     float(item)
    #                 except ValueError:
    #                     return True
    #                 finally:
    #                     if item == 'nan':
    #                         return True
    #             return False
    #
    #         # Cound how many rows have entries that can't be forced into a float
    #         error_count = 0
    #         for row in range(self.table.rowCount()):
    #             if has_na(row):
    #                 error_count += 1
    #         return error_count
    #
    #     errors = get_errors()
    #
    #     # Reject the change if it causes an error.
    #     if errors > 0:
    #         self.table.blockSignals(True)
    #         self.message.critical(self, 'Error', "Value cannot be converted to a number")
    #
    #         item = QTableWidgetItem(self.selected_row_info[col])
    #         item.setTextAlignment(QtCore.Qt.AlignCenter)
    #         self.table.setItem(row, col, item)
    #         self.table.blockSignals(False)
    #     else:
    #         self.plot_table()
    #         self.highlight_point(row=row)
    #
    #     self.color_table()
    #     # self.highlight_point(row=row)

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
            df_stations = self.table_to_df().Station.map(lambda x: re.search('-?\d+', str(x)).group())

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
                if not station_num:
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
        # super().__init__()
        # self.setupUi(self)
        # self.parent = parent
        # self.loop = None
        # self.setWindowTitle('Loop Adder')
        #
        # # self.table = QTableWidget()
        # self.table.setFixedWidth(400)
        # self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        # self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        # self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        #
        # self.canvas_frame.layout().addWidget(self.canvas)
        # self.canvas.mpl_connect('pick_event', self.onpick)
        #
        # self.button_box.rejected.connect(self.close)
        # self.table.cellChanged.connect(self.plot_table)
        # self.table.cellChanged.connect(self.check_table)
        # self.table.itemSelectionChanged.connect(self.highlight_point)
        # self.auto_sort_cbox.toggled.connect(lambda: self.open(self.loop))
        # self.status_bar.hide()
        #

        super().__init__()
        self.setupUi(self)
        self.parent = parent
        self.loop = None
        self.selected_row_info = None
        self.setWindowTitle('Loop Adder')

        # Status bar widgets
        self.auto_sort_cbox = QCheckBox("Automatically Sort Loop", self)
        self.auto_sort_cbox.setChecked(True)

        self.spacer_label = QLabel('')

        # Format the borders of the items in the status bar
        self.setStyleSheet("QStatusBar::item {border-left: 1px solid gray; border-top: 1px solid gray}")
        self.status_bar.setStyleSheet("border-top: 1px solid gray; border-top: None")

        self.status_bar.addPermanentWidget(self.auto_sort_cbox, 0)
        self.status_bar.addPermanentWidget(self.spacer_label, 1)

        self.table.setFixedWidth(400)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)

        self.canvas_frame.layout().addWidget(self.canvas)
        self.canvas.mpl_connect('pick_event', self.onpick)
        self.canvas.setFocusPolicy(QtCore.Qt.StrongFocus)

        # Signals
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.close)

        self.table.cellChanged.connect(self.cell_changed)
        self.table.itemSelectionChanged.connect(self.highlight_point)
        self.auto_sort_cbox.toggled.connect(lambda: self.open(self.loop))

        self.reset_action = QShortcut(QtGui.QKeySequence(" "), self)
        self.reset_action.activated.connect(self.reset_range)

    def open(self, o):
        """
        Add the data frame to GPSAdder. Adds the data to the table and plots it.
        :param o: Union (filepath, dataframe), Loop to open
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

        if not self.loop:
            return

        if self.loop.df.empty:
            return

        self.clear_table()
        self.df = self.loop.get_loop(closed=True, sorted=self.auto_sort_cbox.isChecked())
        self.df_to_table(self.df)
        self.plot_table()
        self.show()

        if not errors.empty:
            self.message.warning(self, 'Parsing Error',
                                 f"The following rows could not be parsed:\n\n{errors.to_string()}")

    def accept(self):
        """
        Signal slot: Adds the data from the table to the write_widget's (pem_info_widget object) table.
        :return: None
        """
        self.write_widget.fill_gps_table(self.table_to_df().dropna(), self.write_widget.loop_table)
        self.hide()

    def plot_table(self, preserve_limits=False):
        """
        Plot the data from the table to the axes.
        :return: None
        """
        if preserve_limits is True:
            plan_xlim, plan_ylim = self.plan_ax.get_xlim(), self.plan_ax.get_ylim()
            section_xlim, section_ylim = self.section_ax.get_xlim(), self.section_ax.get_ylim()
        self.plan_ax.clear()
        self.section_ax.clear()

        df = self.table_to_df()

        # Redraw the empty canvas if there is a pending error
        if self.error is True:
            self.canvas.draw()
            return

        df = df.append(df.iloc[0], ignore_index=True)
        # Plot the plan map
        df.plot(x='Easting', y='Northing',
                ax=self.plan_ax,
                color='dimgray',
                zorder=0,
                legend=False
                )
        # Plot the stations on the plan map
        df.plot.scatter(x='Easting', y='Northing',
                        ax=self.plan_ax,
                        color='w',
                        edgecolors='dimgray',
                        zorder=1,
                        legend=False,
                        picker=True
                        )
        # Plot the sections
        df.plot(y='Elevation',
                ax=self.section_ax,
                color='dimgray',
                zorder=0,
                legend=False
                )

        # Plot the stations on the section map
        df.reset_index().plot.scatter(x='index', y='Elevation',
                                      ax=self.section_ax,
                                      color='w',
                                      edgecolors='dimgray',
                                      zorder=1,
                                      legend=False,
                                      picker=True
                                      )

        if preserve_limits is True:
            self.plan_ax.set_xlim(plan_xlim)
            self.plan_ax.set_ylim(plan_ylim)
            self.section_ax.set_xlim(section_xlim)
            self.section_ax.set_ylim(section_ylim)
        else:
            # Add flat elevation for the section plot limits
            self.section_ax.set_ylim(self.section_ax.get_ylim()[0] - 5,
                                     self.section_ax.get_ylim()[1] + 5)

        self.plan_ax.ticklabel_format(axis='both', style='plain', useOffset=False)
        # ticks = self.plan_ax.get_yticklabels()
        # self.plan_ax.set_yticklabels(ticks, rotation=45)
        self.canvas.draw()

    def highlight_point(self, row=None):
        """
        Highlight a scatter point when it's row is selected in the table.
        :param row: Int: table row to highlight
        :return: None
        """
        def reset_highlight():
            """
            Remove the crosshairs
            """
            self.plan_highlight.remove()
            self.plan_lx.remove()
            self.plan_ly.remove()
            self.section_highlight.remove()
            self.section_lx.remove()
            self.section_ly.remove()

            self.plan_highlight = None
            self.plan_lx = None
            self.plan_ly = None
            self.section_highlight = None
            self.section_lx = None
            self.section_ly = None

        if row is None:
            selected_row = self.table.selectionModel().selectedRows()
            if selected_row:
                row = self.table.selectionModel().selectedRows()[0].row()
            else:
                print(f"No row selected")
                return

        # Save the information of the row for backup purposes
        self.selected_row_info = [self.table.item(row, j).text() for j in range(len(self.df.columns))]

        # Remove previously plotted selection
        if self.plan_highlight:
            reset_highlight()

        color, light_color = ('blue', 'lightsteelblue') if keyboard.is_pressed('ctrl') is False else ('red', 'pink')

        df = self.table_to_df()
        # Plot on the plan map
        plan_x, plan_y = df.loc[row, 'Easting'], df.loc[row, 'Northing']
        self.plan_highlight = self.plan_ax.scatter([plan_x], [plan_y],
                                                   color=light_color,
                                                   edgecolors=color,
                                                   zorder=3
                                                   )
        self.plan_lx = self.plan_ax.axhline(plan_y, color=color, alpha=0.5)
        self.plan_ly = self.plan_ax.axvline(plan_x, color=color, alpha=0.5)

        # Plot on the section map
        section_x, section_y = row, df.loc[row, 'Elevation']
        self.section_highlight = self.section_ax.scatter([section_x], [section_y],
                                                         color=light_color,
                                                         edgecolors=color,
                                                         zorder=3
                                                         )
        self.section_lx = self.section_ax.axhline(section_y, color=color, alpha=0.5)
        self.section_ly = self.section_ax.axvline(section_x, color=color, alpha=0.5)
        self.canvas.draw()


def main():
    from src.pem.pem_getter import PEMGetter
    app = QApplication(sys.argv)
    line_samples_folder = str(Path(Path(__file__).absolute().parents[2]).joinpath('sample_files\Line GPS'))
    loop_samples_folder = str(Path(Path(__file__).absolute().parents[2]).joinpath('sample_files\Loop GPS'))
    # mw = LoopAdder()
    mw = LineAdder()

    pg = PEMGetter()
    file = str(Path(line_samples_folder).joinpath('PRK-LOOP11-LINE9.txt'))
    # file = str(Path(loop_samples_folder).joinpath('LOOP225Gold.txt'))

    # loop = TransmitterLoop(file)
    # line = SurveyLine(file)

    mw.open(file)

    app.exec_()


if __name__ == '__main__':
    main()