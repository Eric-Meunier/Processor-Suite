import copy
import os
import sys
import time
import keyboard

import numpy as np
import pandas as pd
import pyqtgraph as pg
import pylineclip as lc
from PyQt5 import uic, QtCore, QtGui
from PyQt5.QtWidgets import (QApplication, QMainWindow)
from pyqtgraph.Point import Point

# from matplotlib.figure import Figure
from src.pem.pem_file import StationConverter

if getattr(sys, 'frozen', False):
    application_path = sys._MEIPASS
    plotEditorCreatorFile = 'qt_ui\\pem_plot_editor.ui'
else:
    application_path = os.path.dirname(os.path.abspath(__file__))
    plotEditorCreatorFile = os.path.join(os.path.dirname(application_path), 'qt_ui\\pem_plot_editor.ui')

# Load Qt ui file into a class
Ui_PlotEditorWindow, QtBaseClass = uic.loadUiType(plotEditorCreatorFile)

pg.setConfigOptions(antialias=True)
pg.setConfigOption('background', 'w')
pg.setConfigOption('foreground', 'k')
pg.setConfigOption('crashWarning', True)
pd.options.mode.chained_assignment = None  # default='warn'


class PEMPlotEditor(QMainWindow, Ui_PlotEditorWindow):

    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.pem_file = None
        self.units = None
        self.stations = []

        self.line_selected = False
        self.selected_station = None
        self.selected_data = pd.DataFrame()
        self.selected_lines = []
        self.deleted_lines = []

        self.active_ax = None
        self.active_ax_ind = None
        self.plotted_decay_lines = []
        self.plotted_decay_data = pd.DataFrame()

        self.x_decay_plot = self.decay_layout.addPlot(0, 0, title='X Component', viewBox=DecayViewBox())
        self.y_decay_plot = self.decay_layout.addPlot(1, 0, title='Y Component', viewBox=DecayViewBox())
        self.z_decay_plot = self.decay_layout.addPlot(2, 0, title='Z Component', viewBox=DecayViewBox())
        self.decay_layout.ci.layout.setSpacing(1)  # Spacing between plots
        self.decay_axes = np.array([self.x_decay_plot, self.y_decay_plot, self.z_decay_plot])
        self.active_decay_axes = []

        def link_decay_y():
            if len(self.active_decay_axes) > 1:
                for ax in self.active_decay_axes[1:]:
                    if self.link_y_cbox.isChecked():
                        ax.setYLink(self.active_decay_axes[0])
                    else:
                        ax.setYLink(None)

        def link_decay_x():
            if len(self.active_decay_axes) > 1:
                for ax in self.active_decay_axes[1:]:
                    if self.link_x_cbox.isChecked():
                        ax.setXLink(self.active_decay_axes[0])
                    else:
                        ax.setXLink(None)

        # Link the X and Y axis of each axes
        link_decay_x()
        link_decay_y()

        for ax in self.decay_axes:
            ax.vb.box_select_signal.connect(self.box_select_decay_lines)
            ax.hideButtons()
            ax.setMenuEnabled(False)
            ax.getAxis('left').enableAutoSIPrefix(enable=False)
            ax.scene().sigMouseMoved.connect(self.decay_mouse_moved)
            ax.scene().sigMouseClicked.connect(self.decay_plot_clicked)

        # Configure the plots
        self.x_profile_layout.ci.layout.setSpacing(5)  # Spacing between plots
        self.x_ax0 = self.x_profile_layout.addPlot(0, 0)
        self.x_ax1 = self.x_profile_layout.addPlot(1, 0)
        self.x_ax2 = self.x_profile_layout.addPlot(2, 0)
        self.x_ax3 = self.x_profile_layout.addPlot(3, 0)
        self.x_ax4 = self.x_profile_layout.addPlot(4, 0)

        self.y_profile_layout.ci.layout.setSpacing(5)  # Spacing between plots
        self.y_ax0 = self.y_profile_layout.addPlot(0, 0)
        self.y_ax1 = self.y_profile_layout.addPlot(1, 0)
        self.y_ax2 = self.y_profile_layout.addPlot(2, 0)
        self.y_ax3 = self.y_profile_layout.addPlot(3, 0)
        self.y_ax4 = self.y_profile_layout.addPlot(4, 0)

        self.z_profile_layout.ci.layout.setSpacing(5)  # Spacing between plots
        self.z_ax0 = self.z_profile_layout.addPlot(0, 0)
        self.z_ax1 = self.z_profile_layout.addPlot(1, 0)
        self.z_ax2 = self.z_profile_layout.addPlot(2, 0)
        self.z_ax3 = self.z_profile_layout.addPlot(3, 0)
        self.z_ax4 = self.z_profile_layout.addPlot(4, 0)

        self.x_layout_axes = [self.x_ax0, self.x_ax1, self.x_ax2, self.x_ax3, self.x_ax4]
        self.y_layout_axes = [self.y_ax0, self.y_ax1, self.y_ax2, self.y_ax3, self.y_ax4]
        self.z_layout_axes = [self.z_ax0, self.z_ax1, self.z_ax2, self.z_ax3, self.z_ax4]

        self.profile_axes = np.concatenate([self.x_layout_axes, self.y_layout_axes, self.z_layout_axes])
        self.active_profile_axes = []

        # Configure each axes
        for ax in self.profile_axes:
            ax.hideButtons()
            ax.setMenuEnabled(False)
            ax.getAxis('left').enableAutoSIPrefix(enable=False)

            # Add the vertical selection line
            hover_v_line = pg.InfiniteLine(angle=90, movable=False)
            hover_v_line.setPen((102, 178, 255, 100), width=2.)
            selected_v_line = pg.InfiniteLine(angle=90, movable=False)
            selected_v_line.setPen((51, 51, 255, 100), width=2.)

            hover_v_line_text = pg.TextItem("hover v line", anchor=(0, 0))
            hover_v_line_text.setParentItem(ax.vb)
            hover_v_line_text.setPos(0, 0)
            hover_v_line_text.setColor((102, 178, 255, 100))
            selected_v_line_text = pg.TextItem("selected v line", anchor=(0, 0))
            selected_v_line_text.setParentItem(ax.vb)
            selected_v_line_text.setPos(0, 0)
            selected_v_line_text.setColor((51, 51, 255, 100))

            ax.addItem(hover_v_line, ignoreBounds=True)
            ax.addItem(selected_v_line, ignoreBounds=True)
            ax.addItem(hover_v_line_text, ignoreBounds=True)
            ax.addItem(selected_v_line_text, ignoreBounds=True)

            # Connect the mouse moved signal
            ax.scene().sigMouseMoved.connect(self.profile_mouse_moved)
            ax.scene().sigMouseClicked.connect(self.profile_plot_clicked)

        # Signals
        self.link_y_cbox.toggled.connect(link_decay_y)
        self.link_x_cbox.toggled.connect(link_decay_x)

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Delete:
            self.delete_lines()

        elif event.key() == QtCore.Qt.Key_Space:
            # Only need to auto range the first axes of each group, since they are all linked.
            if self.active_profile_axes:
                for ax in self.active_profile_axes:
                    ax.autoRange()
            if self.active_decay_axes:
                for ax in self.active_decay_axes:
                    ax.autoRange()

        elif event.key() == QtCore.Qt.Key_Escape:
            self.clear_selection()

    def open(self, pem_file):
        """
        Open a PEMFile object and plot the data.
        :param pem_file: PEMFile object.
        """
        self.pem_file = copy.deepcopy(pem_file)
        # Add the deletion flag column
        self.pem_file.data.insert(13, 'del_flag', False)
        self.stations = self.pem_file.get_stations(converted=True)

        # Convert the stations in the data
        converter = StationConverter()
        self.pem_file.data.Station = self.pem_file.data.Station.map(converter.convert_station)

        # Set the units of the decay plots
        self.units = self.pem_file.units
        for ax in self.decay_axes:
            ax.setLabel('left', f"Response", units=self.units)

        # Plot the LIN profiles
        self.plot_profiles()
        self.toggle_plot_visibility()
        self.show()

    def plot_profiles(self):
        """
        Plot the PEM file in a LIN plot style, with both components in separate plots
        """

        def clear_plots():
            pass

        def link_profile_axes():
            if len(self.active_profile_axes) > 1:
                for ax in self.active_profile_axes[1:]:
                    ax.setXLink(self.active_profile_axes[0])

        def plot_lin(component):

            def plot_lines(df, ax, channel):
                """
                Plot the lines on the pyqtgraph ax for a given channel
                :param df: DataFrame of filtered data
                :param ax: pyqtgraph PlotItem
                :param channel: int, channel to plot
                """
                x, y = df['Station'], df[channel]
                interp_x = np.linspace(x.min(), x.max() + 1, num=1000)
                interp_y = np.interp(interp_x, x, y)

                profile_line = pg.PlotCurveItem(x=interp_x, y=interp_y,
                                                pen=pg.mkPen('k', width=1.),
                                                # clickable=True,
                                                )
                # profile_line.sigClicked.connect(self.profile_line_clicked)
                ax.addItem(profile_line)
                # self.profile_lines.append(profile_line)

            def calc_channel_bounds():
                """
                Create tuples of start and end channels to be plotted per axes
                :return: list of tuples, first item of tuple is the axes, second is the start and end channel for that axes
                """
                channel_bounds = [None] * 4
                num_channels_per_plot = int((file.number_of_channels - 1) // 4)
                remainder_channels = int((file.number_of_channels - 1) % 4)

                for k in range(0, len(channel_bounds)):
                    channel_bounds[k] = (k * num_channels_per_plot + 1, num_channels_per_plot * (k + 1))

                for i in range(0, remainder_channels):
                    channel_bounds[i] = (channel_bounds[i][0], (channel_bounds[i][1] + 1))
                    for k in range(i + 1, len(channel_bounds)):
                        channel_bounds[k] = (channel_bounds[k][0] + 1, channel_bounds[k][1] + 1)

                channel_bounds.insert(0, (0, 0))
                return channel_bounds

            filt = profile_data['Component'] == component.upper()
            channel_bounds = calc_channel_bounds()
            for i, bounds in enumerate(channel_bounds):
                # Select the correct axes based on the component
                if component == 'X':
                    ax = self.x_layout_axes[i]
                elif component == 'Y':
                    ax = self.y_layout_axes[i]
                else:
                    ax = self.z_layout_axes[i]

                # Set the Y-axis labels
                if i == 0:
                    ax.setLabel('left', f"PP channel", units=self.units)
                else:
                    ax.setLabel('left', f"Channel {bounds[0]} to {bounds[1]}", units=self.units)

                # Plot the data
                for ch in range(bounds[0], bounds[1] + 1):
                    data = profile_data[filt].loc[:, ['Station', ch]]
                    plot_lines(data, ax, ch)

        clear_plots()
        global file
        file = copy.deepcopy(self.pem_file)

        if not file.is_averaged():
            file = file.average()

        if not file.is_split():
            file = file.split()

        profile_data = file.get_profile_data()
        if profile_data.empty:
            return

        t = time.time()
        for component in file.get_components():
            plot_lin(component)

            # Add the profile axes to the list of active profile axes
            if component == 'X':
                if self.x_layout_axes not in self.active_profile_axes:
                    self.active_profile_axes.extend(self.x_layout_axes)
            elif component == 'Y':
                if self.y_layout_axes not in self.active_profile_axes:
                    self.active_profile_axes.extend(self.y_layout_axes)
            elif component == 'Z':
                if self.z_layout_axes not in self.active_profile_axes:
                    self.active_profile_axes.extend(self.z_layout_axes)

            link_profile_axes()

        print(f"Time to make plots: {time.time() - t}")

    def plot_station(self, station, preserve_selection=False):
        """
        Plot the decay lines for each component of the given station
        :param station: int, station number
        :param preserve_selection: bool, re-select the selected lines after plotting
        """

        def plot_decay(row):
            """
            Plot the decay line (Reading) of the row
            :param row: pandas Series
            """
            # Select which axes to plot on
            if row.Component == 'X':
                ax = self.x_decay_plot
            elif row.Component == 'Y':
                ax = self.y_decay_plot
            else:
                ax = self.z_decay_plot

            # Add the ax to the list of active decay axes
            if ax not in self.active_decay_axes:
                self.active_decay_axes.append(ax)

            # Change the pen if the data is flagged for deletion
            if row.del_flag is False:
                pen = pg.mkPen((96, 96, 96), width=1.)
            else:
                pen = pg.mkPen('r', width=1.)

            # Create and configure the line item
            decay_line = pg.PlotCurveItem(y=row.Reading,
                                          pen=pen,
                                          )
            decay_line.setClickable(True, width=5)
            decay_line.sigClicked.connect(self.decay_line_clicked)

            # Add the line at y=0
            ax.addLine(y=0, pen=pg.mkPen('k', width=0.1))
            # Plot the decay
            ax.addItem(decay_line)
            # Add the plot item to the list of plotted items
            self.plotted_decay_lines.append(decay_line)

        # Move the selected vertical line
        for ax in self.profile_axes:
            selected_v_line = ax.items[1]
            selected_v_line.setPos(station)

        index_of_selected = []
        # Keep the same lines highlighted after data modification
        if preserve_selection is False:
            self.selected_lines = []
        else:
            index_of_selected = [self.plotted_decay_lines.index(line) for line in self.selected_lines]

        # Clear the plots
        for ax in self.decay_axes:
            ax.clear()
        self.plotted_decay_lines = []
        self.plotted_decay_data = None  # Not actually necessary

        # Filter the data
        filt = self.pem_file.data['Station'] == station
        self.plotted_decay_data = self.pem_file.data[filt]

        # Plot the decays
        self.plotted_decay_data.apply(plot_decay, axis=1)

        if preserve_selection is True:
            self.selected_lines = [self.plotted_decay_lines[i] for i in index_of_selected]
            self.highlight_lines()

        self.toggle_plot_visibility()

    def toggle_plot_visibility(self):
        """
        Signal slot, show/hide decay plots and profile plot tabs
        """

        components = self.pem_file.get_components()

        x_ax = self.x_decay_plot
        y_ax = self.y_decay_plot
        z_ax = self.z_decay_plot

        if 'X' in components:
            x_ax.show()
            self.profile_tab_widget.setTabEnabled(0, True)
        else:
            x_ax.hide()
            self.profile_tab_widget.setTabEnabled(0, False)

        if 'Y' in components:
            y_ax.show()
            self.profile_tab_widget.setTabEnabled(1, True)
        else:
            y_ax.hide()
            self.profile_tab_widget.setTabEnabled(1, False)

        if 'Z' in components:
            z_ax.show()
            self.profile_tab_widget.setTabEnabled(2, True)
        else:
            z_ax.hide()
            self.profile_tab_widget.setTabEnabled(2, False)

    def profile_mouse_moved(self, evt):
        """
        Signal slot, when the mouse is moved in one of the axes. Calculates and plots a light blue vertical line at the
        nearest station where the mouse is.
        :param evt: pyqtgraph MouseClickEvent
        """
        def find_nearest_station(x):
            """
            Calculate the nearest station from the position x
            :param x: int, mouse x location
            :return: int, station number
            """
            idx = (np.abs(self.stations - x)).argmin()
            return self.stations[idx]

        # def set_station_text():
        #     text.setPos(mouse_point.x(), 0)

        global nearest_station
        pos = evt
        mouse_point = self.active_profile_axes[0].vb.mapSceneToView(pos)
        nearest_station = find_nearest_station(int(mouse_point.x()))

        for ax in self.active_profile_axes:
            ax.items[0].setPos(nearest_station)
            ax.items[2].setPos(nearest_station, ax.viewRange()[1][1])
            ax.items[2].setText(str(nearest_station))

        # set_station_text()

    def profile_plot_clicked(self, evt):
        """
        Signal slot, when the profile plot is clicked. Plots a darker blue vertical line at the nearest station where
        the click was made and plots that station's decays in the decay plot.
        Uses the nearest station calculated in self.profile_mouse_moved.
        :param evt: pyqtgraph MouseClickEvent (not used)
        """
        self.selected_station = nearest_station
        for ax in self.active_profile_axes:
            ax.items[3].setPos(nearest_station, ax.viewRange()[1][1])
            ax.items[3].setText(str(nearest_station))

        self.plot_station(nearest_station)

    def decay_line_clicked(self, line):
        """
        Signal slot, select the decay line that was clicked. If control is held, it extends the current selection.
        :param line: clicked PlotItem line
        """
        self.line_selected = True
        if keyboard.is_pressed('ctrl'):
            self.selected_lines.append(line)
            self.highlight_lines()
        else:
            self.selected_data = None
            self.selected_lines = [line]
            self.highlight_lines()

    def decay_plot_clicked(self, evt):
        """
        Signal slot, change the profile tab to the same component as the clicked decay plot
        :param evt: MouseClick event
        """
        # print(f"Decay plot clicked")
        self.profile_tab_widget.setCurrentIndex(self.active_ax_ind)
        # if self.line_selected is False:
        #     self.clear_selection()
        # else:
        #     self.line_selected = False

    def decay_mouse_moved(self, evt):
        """
        Signal slot, find the decay_axes plot under the mouse when the mouse is moved to determine which plot is active.
        :param evt: MouseMovement event
        """
        self.active_ax = None
        for ax in self.decay_axes:
            if ax.sceneBoundingRect().contains(evt):
                self.active_ax = ax
                self.active_ax_ind = np.where(self.decay_axes == self.active_ax)[0][0]
                break

    def highlight_lines(self):
        """
        Highlight the line selected and un-highlight any previously highlighted line.
        :param lines: list, PlotItem lines
        """
        if self.plotted_decay_lines:

            # Enable decay editing buttons
            if len(self.selected_lines) > 0:
                self.change_component_btn.setEnabled(True)
                self.flip_decay_btn.setEnabled(True)
            else:
                self.change_component_btn.setEnabled(False)
                self.flip_decay_btn.setEnabled(False)

            for line, del_flag in zip(self.plotted_decay_lines, self.plotted_decay_data.del_flag):
                if del_flag is True:
                    pen_color = 'r'
                else:
                    pen_color = (96, 96, 96)

                if line in self.selected_lines:
                    if del_flag is False:
                        # pen_color = (102, 102, 255)
                        pen_color = (70, 70, 255)
                        # pen_color = (127, 0, 255)

                    print(f"Line {self.plotted_decay_lines.index(line)} selected")
                    line.setPen(pen_color, width=2)
                    if len(self.selected_lines) == 1:
                        line.setShadowPen(pg.mkPen('w', width=2.5, cosmetic=True))
                else:
                    line.setPen(pen_color, width=1)
                    line.setShadowPen(None)

    def clear_selection(self):
        self.selected_data = None
        self.selected_lines = []
        self.highlight_lines()

    def box_select_decay_lines(self, rect):
        """
        Signal slot, select all lines that intersect the drawn rectangle.
        :param rect: QRectF object
        """

        def intersects_rect(line):
            """
            Uses cohens-utherland algorithm to find if a line intersects the rectangle at any point.
            :param line: PlotCurveItem
            :return: bool
            """
            xi, yi = line.xData, line.yData

            # Line is broken down into segments for the algorithm
            for i, (x, y) in enumerate(zip(xi[:-1], yi[:-1])):
                x1, y1 = float(x), y
                x2, y2 = float(xi[i + 1]), yi[i + 1]
                x3, y3, x4, y4 = lc.cohensutherland(left, top, right, bottom, x1, y1, x2, y2)

                if any([x3, y3, x4, y4]):
                    print()
                    return True

        # Create the clip window for the line clipping algorithm.
        left, top, right, bottom = min(rect.left(), rect.right()), max(rect.top(), rect.bottom()), \
                                   max(rect.left(), rect.right()), min(rect.top(), rect.bottom())
        lines = [line for line in self.active_ax.curves if intersects_rect(line)]

        if keyboard.is_pressed('ctrl'):
            self.selected_lines.extend(lines)
        else:
            self.selected_lines = lines
        self.selected_data = None

        self.highlight_lines()
        self.get_selected_data()

    def get_selected_data(self):
        """
        Return the corresponding data of the decay lines that are currently selected
        :return: pandas DataFrame
        """
        ind = [self.plotted_decay_lines.index(line) for line in self.selected_lines]
        data = self.plotted_decay_data.iloc[ind]
        return data

    def delete_lines(self):
        """
        Delete the selected lines. The data corresponding to the selected lines have their deletion flags flipped
        (i.e. from True > False or False > True). The station is then re-plotted. Line highlight is preserved.
        """
        selected_data = self.get_selected_data()
        if not selected_data.empty:
            # Change the deletion flag
            selected_data.loc[:, 'del_flag'] = selected_data.loc[:, 'del_flag'].map(lambda x: not x)

            # Update the data in the pem file object
            self.pem_file.data.iloc[selected_data.index] = selected_data
            self.plot_station(self.selected_station, preserve_selection=True)

    def change_component(self):
        pass

    def change_station(self):
        pass

    def flip_lines(self):
        pass


class DecayViewBox(pg.ViewBox):
    box_select_signal = QtCore.pyqtSignal(object)

    def __init__(self, *args, **kwds):
        pg.ViewBox.__init__(self, *args, **kwds)
        # self.setMouseMode(self.RectMode)
        brush = QtGui.QBrush(QtGui.QColor('blue'))
        pen = QtGui.QPen(brush, 1)
        # self.rbScaleBox.setPen(pen)
        self.rbScaleBox.setBrush(brush)
        self.rbScaleBox.setOpacity(0.2)

    def mouseDragEvent(self, ev, axis=None):
        pos = ev.pos()
        if ev.button() == QtCore.Qt.LeftButton:
            ev.accept()
            if ev.isFinish():  # This is the final move in the drag
                # Hide the rectangle
                self.rbScaleBox.hide()
                # Create a rectangle object from the click-and-drag rectangle
                rect = QtCore.QRectF(Point(ev.buttonDownPos(ev.button())), Point(pos))
                # Convert the coordinates to the same as the data
                rect = self.childGroup.mapRectFromParent(rect)
                # Emit the signal to select the lines that intersect the rect
                self.box_select_signal.emit(rect)
            else:
                # update shape of scale box
                self.updateScaleBox(ev.buttonDownPos(), ev.pos())
        else:
            pg.ViewBox.mouseDragEvent(self, ev)

    def wheelEvent(self, ev, axis=None):

        def invertQTransform(tr):
            """Return a QTransform that is the inverse of *tr*.
            Rasises an exception if tr is not invertible.

            Note that this function is preferred over QTransform.inverted() due to
            bugs in that method. (specifically, Qt has floating-point precision issues
            when determining whether a matrix is invertible)
            """
            try:
                import numpy.linalg
                arr = np.array(
                    [[tr.m11(), tr.m12(), tr.m13()], [tr.m21(), tr.m22(), tr.m23()], [tr.m31(), tr.m32(), tr.m33()]])
                inv = numpy.linalg.inv(arr)
                return QtGui.QTransform(inv[0, 0], inv[0, 1], inv[0, 2], inv[1, 0], inv[1, 1], inv[1, 2], inv[2, 0],
                                        inv[2, 1])
            except ImportError:
                inv = tr.inverted()
                if inv[1] is False:
                    raise Exception("Transform is not invertible.")
                return inv[0]

        if axis in (0, 1):
            mask = [False, False]
            mask[axis] = self.state['mouseEnabled'][axis]
        else:
            mask = self.state['mouseEnabled'][:]
        s = 1.02 ** (ev.delta() * self.state['wheelScaleFactor'])  # actual scaling factor
        s = [(None if m is False else s) for m in mask]
        center = Point(invertQTransform(self.childGroup.transform()).map(ev.pos()))

        self._resetTarget()
        self.scaleBy(s, center)
        ev.accept()
        self.sigRangeChangedManually.emit(mask)


    # class PEMPlotEditor(QWidget, Ui_PlotEditorWindow):


#
#     def __init__(self, pem_file):
#         super().__init__()
#         self.setupUi(self)
#         self.pem_file = pem_file
#         self.decay_cleaner = PEMDecayCleaner(self.pem_file)
#         # self.canvas = FigureCanvas(self.decay_cleaner.fig)
#         self.toolbar = NavigationToolbar(self.decay_cleaner.canvas, self)
#         self.toolbar_layout.addWidget(self.toolbar)
#         self.toolbar.setFixedHeight(30)
#         self.decay_layout.addWidget(self.decay_cleaner.canvas)
#     # def plot(self):
#     #     roi = pg.PolyLineROI(zip(np.arange(100), np.random.normal(size=100)), pen=(5,9), closed=False, removable=True,
#     #                          movable=False)
#     #     p2 = self.win.addItem(roi)
#     #     p3 = None
#
#
# class PEMDecayCleaner:
#
#     def __init__(self, pem_file):#, component, station):
#         self.pem_file = pem_file
#         # self.
#         self.selected_line_color = 'magenta'
#         self.x = np.linspace(0, 10, 100)
#
#         self.fig, self.ax = plt.subplots()
#         self.canvas = FigureCanvas(self.fig)
#         self.lines = []
#
#         for i in range(1, 10):
#             self.lines.append(self.ax.plot(self.x, i * self.x + self.x, picker=5, color='dimgray', alpha=0.75))
#         self.lines = [line[0] for line in self.lines]  # Because appending ax.plot appends a list
#
#         rectprops = dict(facecolor='magenta', edgecolor='black',
#                          alpha=0.2, fill=True)
#         self.rs = RectangleSelector(self.ax, self.on_rect_select,
#                                     drawtype='box', useblit=False,
#                                     button=[1],  # don't use middle button or right-click
#                                     minspanx=5, minspany=5,
#                                     spancoords='pixels',
#                                     interactive=False,
#                                     rectprops=rectprops)
#
#         self.fig.canvas.callbacks.connect('pick_event', self.on_pick)
#         self.fig.canvas.callbacks.connect('button_press_event', self.on_btn_press)
#         self.fig.canvas.callbacks.connect('key_press_event', self.on_key_press)
#         # plt.show()
#
#     # def plot_decay(self, component, station):
#     def get_plot(self):
#         return self.fig
#
#     def select_line(self, line):
#         line._color = self.selected_line_color
#         line._alpha = 1.
#         # self.selected_lines.append(line)
#         print(f"Selected line {self.lines.index(line)}")
#         self.fig.canvas.draw()
#
#     def deselect_line(self, line):
#         line._color = 'dimgray'
#         line._alpha = 0.75
#         # self.selected_lines.remove(line)
#         print(f"De-selected line {self.lines.index(line)}")
#         self.fig.canvas.draw()
#
#     def delete_line(self, line):
#         """
#         Delete a line
#         :param line: Line2D object
#         :return: None
#         """
#         # line.remove()  # Remvoes the line from the plot, but not from the list
#         # self.selected_lines.remove(line)  # Removes the object from the selected lines list
#         # self.lines.remove(line)  # Removes the object from the selected lines list
#
#         def is_deleted():
#             if line._color == 'red':
#                 return True
#             else:
#                 return False
#
#         if is_deleted():
#             line._color = self.selected_line_color
#             line._alpha = 1
#         else:
#             line._color = 'red'
#             line._alpha = 0.5
#
#         self.fig.canvas.draw()
#
#     def on_rect_select(self, eclick, erelease):
#         """
#         What happens when a rectangle is drawn
#         :param eclick: event mouse click
#         :param erelease: event mouse click release
#         :return: None
#         """
#         x1, y1 = eclick.xdata, eclick.ydata
#         x2, y2 = erelease.xdata, erelease.ydata
#         bbox = Bbox.from_bounds(x1, y1, x2-x1, y2-y1)
#
#         # Reset all lines
#         for line in self.lines:
#             self.deselect_line(line)
#         self.fig.canvas.draw()
#
#         for line in self.lines:
#             if line._path.intersects_bbox(bbox):
#                 self.select_line(line)
#
#     def on_pick(self, event):
#         # When a plotted line is clicked
#
#         def is_selected(line):
#             if line._color == self.selected_line_color:
#                 return True
#             else:
#                 return False
#
#         line = event.artist
#         index = self.lines.index(line)
#
#         if is_selected(line):
#             self.deselect_line(line)
#         else:
#             self.select_line(line)
#
#     def on_key_press(self, event):
#         # What happens when a key is pressed
#         if event.key == 'delete':
#             if self.selected_lines:
#                 for line in reversed(self.selected_lines):
#                     self.delete_line(line)
#                 # self.fig.canvas.draw()
#
#     def on_btn_press(self, event):
#         if not event.inaxes:
#             for line in self.lines:
#                 self.deselect_line(line)


if __name__ == '__main__':
    from src.pem.pem_getter import PEMGetter

    app = QApplication(sys.argv)
    pem_getter = PEMGetter()
    pem_files = pem_getter.get_pems(client='PEM Splitting', selection=1)

    editor = PEMPlotEditor()
    editor.open(pem_files[0])

    app.exec_()