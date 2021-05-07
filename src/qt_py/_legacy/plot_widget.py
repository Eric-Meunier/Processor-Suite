import PySide2
from PySide2.QtWidgets import *
from PySide2 import uic
from pem.pem_editor import PEMFileEditor
from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt4agg import NavigationToolbar2QT as NavigationToolbar
from PySide2.QtCore import Qt, pyqtSignal, QEvent
import os

# # Load Qt ui file into a class
# qtCreatorFile = os.path.join(os.path.dirname(os.path.realpath(__file__)), "../ui/pem_file_form.ui")
# Ui_PEMFileWidget, QtBaseClass = loadUiType(qtCreatorFile)


class PlotWidget(QWidget):

    def __init__(self, parent=None, editor=None, figure=None, plot_height=1100, plot_width=850):
        QWidget.__init__(self, parent=parent)

        # TODO Store file or editor?
        if not editor:
            raise ValueError
        self.editor = editor

        if not figure:
            raise ValueError
        self.figure = figure

        # For debug
        # p = self.palette()
        # p.setColor(self.backgroundRole(), Qt.red)
        # self.setPalette(p)

        self.nav_bar_visible = False
        self.plot_height = plot_height
        self.plot_width = plot_width

        # TODO Ensure these are checked for None in following code
        self.canvas = None
        self.toolbar = None

        self.configure_canvas(figure)

    def configure_canvas(self, figure):
        self.canvas = FigureCanvas(figure)
        layout = QVBoxLayout(self)
        self.setLayout(layout)
        self.layout().addWidget(self.canvas)
        self.layout().setContentsMargins(0, 0, 0, 0)

        self.canvas.setFixedHeight(self.plot_height)
        self.canvas.setFixedWidth(self.plot_width)
        self.canvas.draw()

        self.toolbar = NavigationToolbar(self.layout().itemAt(0).widget(), self)
        self.layout().addWidget(self.toolbar)
        self.toolbar.hide()

    def toggle_nav_bar(self):
        # TODO Make sure this is working and integrate
        if self.nav_bar_visible:
            self.toolbar.hide()
        else:
            self.toolbar.show()

        self.nav_bar_visible = not self.nav_bar_visible



