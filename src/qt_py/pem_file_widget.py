from PyQt5.QtWidgets import *
from PyQt5 import uic
from pem.pem_editor import PEMFileEditor
from qt_py.plot_viewer_widget import PlotViewerWidget
from qt_py.plot_widget import PlotWidget
from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt4agg import NavigationToolbar2QT as NavigationToolbar
from PyQt5.QtCore import Qt, pyqtSignal, QEvent
import os


class PEMFileWidget(QWidget):

    def __init__(self, parent=None, editor=None):
        QWidget.__init__(self, parent=parent)

        if not editor:
            self.editor = PEMFileEditor()
        else:
            self.editor = editor

        self.layout = QVBoxLayout(self)
        self.label = QLabel()
        self.label.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.label)

    def open_file(self, file_name):
        # Display loading text
        self.label.show()
        self.label.setText('Loading ' + os.path.basename(file_name) + '...')
        QApplication.processEvents()
        # TODO Find alternative to calling processEvents()?

        self.editor.open_file(file_name)

        lin_figs, log_figs = self.editor.generate_plots()

        self.tab_widget = QTabWidget(self)
        self.layout.addWidget(self.tab_widget)

        self.lin_view_widget = PlotViewerWidget(editor=self.editor, figures=lin_figs, plot_heights=900)
        self.log_view_widget = PlotViewerWidget(editor=self.editor, figures=log_figs, plot_heights=900)

        self.tab_widget.tabBar().setExpanding(True)
        # new_file_widget.setTabPosition(QTabWidget.West)
        self.tab_widget.addTab(self.lin_view_widget, 'Linear Plots')
        self.tab_widget.addTab(self.log_view_widget, 'Log Plots')

        # Hide loading screen and show results
        self.label.hide()

        # print(str(self.width()) + ", " + str(self.height()))
