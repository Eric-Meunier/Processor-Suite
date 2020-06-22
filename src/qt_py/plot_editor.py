import os
import sys

# import matplotlib.backends.backend_tkagg  # Needed for pyinstaller, or receive  ImportError
import matplotlib.pyplot as plt
import numpy as np
from PyQt5 import uic
from PyQt5.QtWidgets import (QApplication, QWidget)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas, \
    NavigationToolbar2QT as NavigationToolbar
from matplotlib.transforms import Bbox
# from matplotlib.figure import Figure
from matplotlib.widgets import RectangleSelector

if getattr(sys, 'frozen', False):
    application_path = sys._MEIPASS
    plotEditorCreatorFile = 'qt_ui\\pem_plot_editor.ui'
else:
    application_path = os.path.dirname(os.path.abspath(__file__))
    plotEditorCreatorFile = os.path.join(os.path.dirname(application_path), 'qt_ui\\pem_plot_editor.ui')

# Load Qt ui file into a class
Ui_PlotEditorWindow, QtBaseClass = uic.loadUiType(plotEditorCreatorFile)


class PEMPlotEditor(QWidget, Ui_PlotEditorWindow):

    def __init__(self, pem_file):
        super().__init__()
        self.setupUi(self)
        self.pem_file = pem_file
        self.decay_cleaner = PEMDecayCleaner(self.pem_file)
        # self.canvas = FigureCanvas(self.decay_cleaner.fig)
        self.toolbar = NavigationToolbar(self.decay_cleaner.canvas, self)
        self.toolbar_layout.addWidget(self.toolbar)
        self.toolbar.setFixedHeight(30)
        self.decay_layout.addWidget(self.decay_cleaner.canvas)
    # def plot(self):
    #     roi = pg.PolyLineROI(zip(np.arange(100), np.random.normal(size=100)), pen=(5,9), closed=False, removable=True,
    #                          movable=False)
    #     p2 = self.win.addItem(roi)
    #     p3 = None


class PEMDecayCleaner:

    def __init__(self, pem_file):#, component, station):
        self.pem_file = pem_file
        # self.
        self.selected_line_color = 'magenta'
        self.x = np.linspace(0, 10, 100)

        self.fig, self.ax = plt.subplots()
        self.canvas = FigureCanvas(self.fig)
        self.lines = []

        for i in range(1, 10):
            self.lines.append(self.ax.plot(self.x, i * self.x + self.x, picker=5, color='dimgray', alpha=0.75))
        self.lines = [line[0] for line in self.lines]  # Because appending ax.plot appends a list

        rectprops = dict(facecolor='magenta', edgecolor='black',
                         alpha=0.2, fill=True)
        self.rs = RectangleSelector(self.ax, self.on_rect_select,
                                    drawtype='box', useblit=False,
                                    button=[1],  # don't use middle button or right-click
                                    minspanx=5, minspany=5,
                                    spancoords='pixels',
                                    interactive=False,
                                    rectprops=rectprops)

        self.fig.canvas.callbacks.connect('pick_event', self.on_pick)
        self.fig.canvas.callbacks.connect('button_press_event', self.on_btn_press)
        self.fig.canvas.callbacks.connect('key_press_event', self.on_key_press)
        # plt.show()

    # def plot_decay(self, component, station):
    def get_plot(self):
        return self.fig

    def select_line(self, line):
        line._color = self.selected_line_color
        line._alpha = 1.
        # self.selected_lines.append(line)
        print(f"Selected line {self.lines.index(line)}")
        self.fig.canvas.draw()

    def deselect_line(self, line):
        line._color = 'dimgray'
        line._alpha = 0.75
        # self.selected_lines.remove(line)
        print(f"De-selected line {self.lines.index(line)}")
        self.fig.canvas.draw()

    def delete_line(self, line):
        """
        Delete a line
        :param line: Line2D object
        :return: None
        """
        # line.remove()  # Remvoes the line from the plot, but not from the list
        # self.selected_lines.remove(line)  # Removes the object from the selected lines list
        # self.lines.remove(line)  # Removes the object from the selected lines list

        def is_deleted():
            if line._color == 'red':
                return True
            else:
                return False

        if is_deleted():
            line._color = self.selected_line_color
            line._alpha = 1
        else:
            line._color = 'red'
            line._alpha = 0.5

        self.fig.canvas.draw()

    def on_rect_select(self, eclick, erelease):
        """
        What happens when a rectangle is drawn
        :param eclick: event mouse click
        :param erelease: event mouse click release
        :return: None
        """
        x1, y1 = eclick.xdata, eclick.ydata
        x2, y2 = erelease.xdata, erelease.ydata
        bbox = Bbox.from_bounds(x1, y1, x2-x1, y2-y1)

        # Reset all lines
        for line in self.lines:
            self.deselect_line(line)
        self.fig.canvas.draw()

        for line in self.lines:
            if line._path.intersects_bbox(bbox):
                self.select_line(line)

    def on_pick(self, event):
        # When a plotted line is clicked

        def is_selected(line):
            if line._color == self.selected_line_color:
                return True
            else:
                return False

        line = event.artist
        index = self.lines.index(line)

        if is_selected(line):
            self.deselect_line(line)
        else:
            self.select_line(line)

    def on_key_press(self, event):
        # What happens when a key is pressed
        if event.key == 'delete':
            if self.selected_lines:
                for line in reversed(self.selected_lines):
                    self.delete_line(line)
                # self.fig.canvas.draw()

    def on_btn_press(self, event):
        if not event.inaxes:
            for line in self.lines:
                self.deselect_line(line)


if __name__ == '__main__':
    from src.pem.pem_getter import PEMGetter

    app = QApplication(sys.argv)
    pem_getter = PEMGetter()
    pem_files = pem_getter.get_pems(client='Raglan', number=5)
    # map = FoliumMap(pem_files, '17N')
    # editor = PEMPlotEditor(pem_files[0])
    # editor.show()
    # planner = LoopPlanner()

    # pem_files = list(filter(lambda x: 'borehole' in x.survey_type.lower(), pem_files))
    fig = plt.figure(figsize=(11, 8.5), dpi=100)
    # ax = fig.add_subplot()
    # component = 'z'
    # channel = 15
    # contour = ContourMap()
    # contour.plot_contour(ax, pem_files, component, channel)
    # plt.show()
    # printer = PEMPrinter(sample_files_dir, pem_files)
    # printer.print_final_plots()
    app.exec_()