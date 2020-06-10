import sys

import keyboard
import matplotlib.pyplot as plt
import pandas as pd
from PyQt5 import (QtCore, QtGui)
from PyQt5.QtWidgets import (QWidget, QApplication, QMessageBox, QTableWidgetItem, QGridLayout,
                             QHeaderView, QTableWidget, QDialogButtonBox, QAbstractItemView, QShortcut)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.ticker import FixedLocator


class GPSAdder(QWidget):
    """
    Class to help add station GPS to a PEM file. Helps with files that have missing stations numbers or other
    formatting errors.
    """
    # matplotlib.style.use('ggplot')

    def __init__(self):
        super().__init__()
        self.resize(1000, 800)

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

        self.figure = plt.figure()
        self.figure.subplots_adjust(left=0.17, bottom=0.05, right=0.97, top=0.95)
        self.plan_ax = plt.subplot2grid((30, 1), (0, 0), rowspan=19, colspan=1, fig=self.figure)
        self.plan_ax.set_aspect('equal')
        self.plan_ax.use_sticky_edges = False
        self.section_ax = plt.subplot2grid((30, 1), (22, 0), rowspan=7, colspan=1, fig=self.figure)
        self.section_ax.use_sticky_edges = False
        self.canvas = FigureCanvas(self.figure)

        self.zp = ZoomPan()
        self.plan_zoom = self.zp.zoom_factory(self.plan_ax)
        self.plan_pan = self.zp.pan_factory(self.plan_ax)
        self.section_zoom = self.zp.zoom_factory(self.section_ax)
        self.section_pan = self.zp.pan_factory(self.section_ax)

        self.setLayout(self.layout)
        self.layout.addWidget(self.table, 0, 0)
        self.layout.addWidget(self.button_box, 1, 0, 1, 2)
        self.layout.addWidget(self.canvas, 0, 1)

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
        self.write_widget = None
        self.write_table = None
        self.clear_table()
        self.hide()

    def clear_table(self):
        self.table.blockSignals(True)
        self.table.clear()
        while self.table.rowCount() > 0:
            self.table.removeRow(0)
        self.table.blockSignals(True)

    def add_df(self, df):
        """
        Add the data frame to GPSAdder. Adds the data to the table and plots it.
        :param df: pandas DataFrame
        :return: None
        """
        self.show()
        self.clear_table()
        self.df = df
        self.df_to_table(self.df)
        self.plot_table()
        self.check_table()

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
            row_pos = self.table.rowCount()
            # Add a new row to the table
            self.table.insertRow(row_pos)

            items = series.map(lambda x: QTableWidgetItem(str(x))).to_list()
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

    def plot_table(self):
        pass

    def onpick(self, event):
        """
        Signal slot: When a point in the plots is clicked, highlights the associated row in the table.
        :param event: Mouse click event
        :return: None
        """
        # Ignore mouse wheel events
        if event.mouseevent.button == 'up' or event.mouseevent.button == 'down' or event.mouseevent.button == 2:
            return

        ind = event.ind[0]
        print(f"Point {ind} clicked")

        self.table.selectRow(ind)
        self.highlight_point(row=ind)

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

    def __init__(self):
        super().__init__()
        self.setWindowTitle('Line Adder')
        self.button_box.accepted.connect(self.accept)

    def accept(self):
        """
        Signal slot: Adds the data from the table to the write_widget's (pem_info_widget object) table.
        :return: None
        """
        self.write_widget.fill_gps_table(self.table_to_df().dropna(), self.write_widget.stationGPSTable)
        self.close()

    def plot_table(self):
        """
        Plot the data from the table to the axes. Ignores any rows that have NaN somewhere in the row.
        :return: None
        """
        self.plan_ax.clear()
        self.section_ax.clear()

        df = self.table_to_df()

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

        print(f"Row {row} selected")
        # Remove previously plotted selection
        if self.plan_highlight:
            reset_highlight()

        # Don't do anything if there is a pending error
        if self.error is True:
            return

        df = self.table_to_df()
        # Plot on the plan map
        plan_x, plan_y = df.loc[row, 'Easting'], df.loc[row, 'Northing']
        self.plan_highlight = self.plan_ax.scatter([plan_x], [plan_y],
                                                   color='lightsteelblue',
                                                   edgecolors='blue',
                                                   zorder=3
                                                   )
        self.plan_lx = self.plan_ax.axhline(plan_y, color='blue')
        self.plan_ly = self.plan_ax.axvline(plan_x, color='blue')

        # Plot on the section map
        section_x, section_y = df.loc[row, 'Station'], df.loc[row, 'Elevation']
        self.section_highlight = self.section_ax.scatter([section_x], [section_y],
                                                         color='lightsteelblue',
                                                         edgecolors='blue',
                                                         zorder=3
                                                         )
        self.section_lx = self.section_ax.axhline(section_y, color='blue')
        self.section_ly = self.section_ax.axvline(section_x, color='blue')
        self.canvas.draw()


class LoopAdder(GPSAdder):

    def __init__(self):
        super().__init__()
        self.setWindowTitle('Loop Adder')
        self.button_box.accepted.connect(self.accept)

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
        print(f"Point {index} clicked")

        # Swap two points when CTRL is pressed when selecting two points
        if keyboard.is_pressed('ctrl'):
            print('CTRL is pressed')
            # Reset the selection if two were already selected
            if len(self.selection) == 2:
                self.selection = []
            self.selection.append(index)
            print(f'Selected points: {self.selection}')

            if len(self.selection) == 2:
                print(f"Two points are selected, swapping them...")
                swap_points()
                index = self.selection[0]
        else:
            # Reset the selection if CTRL isn't pressed
            self.selection = []

        self.table.selectRow(index)
        self.highlight_point(row=index)

        self.table.blockSignals(False)

    def add_df(self, df):
        """
        Add the data frame to GPSAdder. Adds the data to the table and plots it.
        :param df: pandas DataFrame
        :return: None
        """
        self.show()
        self.clear_table()
        self.df = df
        self.df_to_table(self.df)
        self.plot_table()
        self.check_table()

    def accept(self):
        """
        Signal slot: Adds the data from the table to the write_widget's (pem_info_widget object) table.
        :return: None
        """
        self.write_widget.fill_gps_table(self.table_to_df().dropna(), self.write_widget.loopGPSTable)
        self.close()

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

        # ticks = self.plan_ax.get_yticklabels()
        # self.plan_ax.set_yticklabels(ticks, rotation=45)
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
        print(f"Row {row} selected")

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


class ZoomPan:
    """
    Add mouse wheel zoom and pan to matplotlib axes
    from https://stackoverflow.com/questions/11551049/matplotlib-plot-zooming-with-scroll-wheel
    """
    def __init__(self):
        self.press = None
        self.cur_xlim = None
        self.cur_ylim = None
        self.x0 = None
        self.y0 = None
        self.x1 = None
        self.y1 = None
        self.xpress = None
        self.ypress = None

    def zoom_factory(self, ax, base_scale=1.5):
        def zoom(event):
            if event.inaxes != ax: return
            cur_xlim = ax.get_xlim()
            cur_ylim = ax.get_ylim()

            xdata = event.xdata  # get event x location
            ydata = event.ydata  # get event y location

            if event.button == 'up':
                # deal with zoom in
                scale_factor = 1 / base_scale
            elif event.button == 'down':
                # deal with zoom out
                scale_factor = base_scale
            else:
                # deal with something that should never happen
                scale_factor = 1
                print(event.button)

            new_width = (cur_xlim[1] - cur_xlim[0]) * scale_factor
            new_height = (cur_ylim[1] - cur_ylim[0]) * scale_factor

            relx = (cur_xlim[1] - xdata)/(cur_xlim[1] - cur_xlim[0])
            rely = (cur_ylim[1] - ydata)/(cur_ylim[1] - cur_ylim[0])

            ax.set_xlim([xdata - new_width * (1-relx), xdata + new_width * (relx)])
            ax.set_ylim([ydata - new_height * (1-rely), ydata + new_height * (rely)])
            ax.figure.canvas.draw()

        fig = ax.get_figure()  # get the figure of interest
        fig.canvas.mpl_connect('scroll_event', zoom)

        return zoom

    def pan_factory(self, ax):
        def onPress(event):
            if event.inaxes != ax: return
            if event.button != 2: return
            self.cur_xlim = ax.get_xlim()
            self.cur_ylim = ax.get_ylim()
            self.press = self.x0, self.y0, event.xdata, event.ydata
            self.x0, self.y0, self.xpress, self.ypress = self.press

        def onRelease(event):
            self.press = None
            ax.figure.canvas.draw()

        def onMotion(event):
            if self.press is None: return
            if event.inaxes != ax: return
            dx = event.xdata - self.xpress
            dy = event.ydata - self.ypress
            self.cur_xlim -= dx
            self.cur_ylim -= dy
            ax.set_xlim(self.cur_xlim)
            ax.set_ylim(self.cur_ylim)

            ax.figure.canvas.draw()

        fig = ax.get_figure()  # get the figure of interest

        # attach the call back
        fig.canvas.mpl_connect('button_press_event', onPress)
        fig.canvas.mpl_connect('button_release_event', onRelease)
        fig.canvas.mpl_connect('motion_notify_event', onMotion)

        # return the function
        return onMotion


def main():
    from src.pem.pem_getter import PEMGetter
    app = QApplication(sys.argv)
    mw = LoopAdder()

    pg = PEMGetter()
    pem_files = pg.get_pems(client='Trevali Peru', number=5)
    mw.show()
    # mw.open_gps_files([r'C:\Users\Mortulo\PycharmProjects\PEMPro\sample_files\Loop GPS\LOOP 240.txt'])

    app.exec_()


if __name__ == '__main__':
    main()