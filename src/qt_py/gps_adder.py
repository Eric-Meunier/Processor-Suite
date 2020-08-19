import sys
import os
import keyboard
import matplotlib.pyplot as plt
import pandas as pd
import matplotlib
from pathlib import Path
from PyQt5 import (QtCore, QtGui)
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (QWidget, QApplication, QMessageBox, QTableWidgetItem, QGridLayout, QCheckBox,
                             QHeaderView, QTableWidget, QDialogButtonBox, QAbstractItemView, QShortcut)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.ticker import FixedLocator, FormatStrFormatter
from src.gps.gps_editor import TransmitterLoop, SurveyLine
from src.mpl.zoom_pan import ZoomPan


# Modify the paths for when the script is being run in a frozen state (i.e. as an EXE)
if getattr(sys, 'frozen', False):
    application_path = sys._MEIPASS
    icons_path = 'icons'
else:
    application_path = os.path.dirname(os.path.abspath(__file__))
    icons_path = os.path.join(os.path.dirname(application_path), "qt_ui\\icons")


class GPSAdder(QWidget):
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

        self.layout = QGridLayout()
        self.table = QTableWidget()
        self.table.setFixedWidth(400)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)

        self.message = QMessageBox()
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.setCenterButtons(True)
        self.button_box.accepted.connect(self.accept)

        self.figure = plt.figure()
        self.figure.subplots_adjust(left=0.17, bottom=0.05, right=0.97, top=0.95)
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

        self.auto_sort_cbox = QCheckBox("Sort Automatically", self)
        self.auto_sort_cbox.setChecked(True)

        self.setLayout(self.layout)
        self.layout.addWidget(self.auto_sort_cbox, 0, 0)
        self.layout.addWidget(self.table, 1, 0)
        self.layout.addWidget(self.button_box, 2, 0, 1, 2)
        self.layout.addWidget(self.canvas, 1, 1)

        self.canvas.mpl_connect('pick_event', self.onpick)

        self.button_box.rejected.connect(self.close)
        self.table.cellChanged.connect(self.plot_table)
        self.table.cellChanged.connect(self.check_table)
        self.table.itemSelectionChanged.connect(self.highlight_point)

        self.del_action = QShortcut(QtGui.QKeySequence("Del"), self)
        self.del_action.activated.connect(self.del_row)

        self.reset_action = QShortcut(QtGui.QKeySequence(" "), self)
        self.reset_action.activated.connect(self.plot_table)
        self.reset_action.activated.connect(self.highlight_point)

        # self.popMenu = QMenu(self)
        # self.popMenu.addAction(self.move_up_action)
        # self.popMenu.addAction(self.move_down_action)

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
        df = pd.DataFrame(columns=self.df.columns)
        for col in range(len(df.columns)):
            l = []
            for row in range(self.table.rowCount()):
                l.append(self.table.item(row, col).text())
            try:
                df.iloc[:, col] = pd.Series(l, dtype=self.df.dtypes.iloc[col])
            except ValueError:
                self.message.information(self, 'Error', 'Invalid data type')
                self.error = True
                return None
        self.error = False
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
        # print(f"Point {index} clicked")

        # Swap two points when CTRL is pressed when selecting two points
        if keyboard.is_pressed('ctrl'):
            # print('CTRL is pressed')
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

    def check_table(self):
        """
        Look for any incorrect data types and create an error if found
        :return: None
        """

        def color_row(row, color):
            """
            Color the background of each cell of a row in the table
            :param row: Int: Row to color
            :param color: str
            :return: None
            """
            for col in range(self.table.columnCount()):
                self.table.item(row, col).setBackground(QtGui.QColor(color))

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

        self.table.blockSignals(True)
        for row in range(self.table.rowCount()):
            if has_na(row):
                color_row(row, 'pink')
            else:
                color_row(row, 'white')
        self.table.blockSignals(False)


class LineAdder(GPSAdder):

    def __init__(self, parent=None):
        super().__init__()
        self.parent = parent
        self.line = None
        self.setWindowTitle('Line Adder')
        self.auto_sort_cbox.toggled.connect(lambda: self.open(self.line))

    def open(self, o):
        """
        Add the data frame to GPSAdder. Adds the data to the table and plots it.
        :param o: Union, filepath; GPS object; DataFrame; Loop to open
        """
        if isinstance(o, str):
            if Path(o).is_file():
                self.line = SurveyLine(o)
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
        self.check_table()
        self.show()

    def accept(self):
        """
        Signal slot: Adds the data from the table to the write_widget's (pem_info_widget object) table.
        :return: None
        """
        self.write_widget.fill_gps_table(self.table_to_df().dropna(), self.write_widget.line_table)
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
            row = self.table.selectionModel().selectedRows()[0].row()

        # print(f"Row {row} selected")
        # Remove previously plotted selection
        if self.plan_highlight:
            reset_highlight()

        # Don't do anything if there is a pending error
        if self.error is True:
            return

        color, light_color = ('blue', 'lightsteelblue') if keyboard.is_pressed('ctrl') is False else ('red', 'pink')

        df = self.table_to_df()
        df['Station'] = df['Station'].astype(int)

        # Plot on the plan map
        plan_x, plan_y = df.loc[row, 'Easting'], df.loc[row, 'Northing']
        self.plan_highlight = self.plan_ax.scatter([plan_x], [plan_y],
                                                   color=light_color,
                                                   edgecolors=color,
                                                   zorder=3
                                                   )
        self.plan_lx = self.plan_ax.axhline(plan_y, color=color)
        self.plan_ly = self.plan_ax.axvline(plan_x, color=color)

        # Plot on the section map
        section_x, section_y = df.loc[row, 'Station'], df.loc[row, 'Elevation']
        self.section_highlight = self.section_ax.scatter([section_x], [section_y],
                                                         color=light_color,
                                                         edgecolors=color,
                                                         zorder=3
                                                         )
        self.section_lx = self.section_ax.axhline(section_y, color=color)
        self.section_ly = self.section_ax.axvline(section_x, color=color)
        self.canvas.draw()


class LoopAdder(GPSAdder):

    def __init__(self, parent=None):
        super().__init__()
        self.parent = parent
        self.loop = None
        self.setWindowTitle('Loop Adder')
        self.auto_sort_cbox.toggled.connect(lambda: self.open(self.loop))

    def open(self, o):
        """
        Add the data frame to GPSAdder. Adds the data to the table and plots it.
        :param o: Union, filepath; GPS object; Loop to open
        """
        if isinstance(o, str):
            if Path(o).is_file():
                self.loop = TransmitterLoop(o)
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
        self.check_table()
        self.show()

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
            row = self.table.selectionModel().selectedRows()[0].row()
        # print(f"Row {row} selected")

        # Remove previously plotted selection
        if self.plan_highlight:
            reset_highlight()

        # Don't do anything if there is a pending error
        if self.error is True:
            return

        color, light_color = ('blue', 'lightsteelblue') if keyboard.is_pressed('ctrl') is False else ('red', 'pink')

        df = self.table_to_df()
        # Plot on the plan map
        plan_x, plan_y = df.loc[row, 'Easting'], df.loc[row, 'Northing']
        self.plan_highlight = self.plan_ax.scatter([plan_x], [plan_y],
                                                   color=light_color,
                                                   edgecolors=color,
                                                   zorder=3
                                                   )
        self.plan_lx = self.plan_ax.axhline(plan_y, color=color)
        self.plan_ly = self.plan_ax.axvline(plan_x, color=color)

        # Plot on the section map
        section_x, section_y = row, df.loc[row, 'Elevation']
        self.section_highlight = self.section_ax.scatter([section_x], [section_y],
                                                         color=light_color,
                                                         edgecolors=color,
                                                         zorder=3
                                                         )
        self.section_lx = self.section_ax.axhline(section_y, color=color)
        self.section_ly = self.section_ax.axvline(section_x, color=color)
        self.canvas.draw()


def main():
    from src.pem.pem_getter import PEMGetter
    app = QApplication(sys.argv)
    # mw = LoopAdder()
    mw = LineAdder()

    pg = PEMGetter()
    # file = r'C:\Users\kajth\PycharmProjects\Crone\sample_files\Loop GPS\LOOP 3.txt'
    file = r'C:\Users\Mortulo\PycharmProjects\PEMPro\sample_files\Line GPS\LINE 0S.txt'
    loop = TransmitterLoop(file)
    line = SurveyLine(file)
    mw.open(file)

    app.exec_()


if __name__ == '__main__':
    main()