import re
import os
import sys
import datetime
import pyqtgraph as pg
from time_axis import TimeAxisItem, timestamp
# from pyqtgraph.Qt import QtGui, QtCore
import logging
from PyQt5.QtWidgets import (QWidget, QMainWindow, QApplication)
from PyQt5 import (QtCore, QtGui, QtWidgets, uic)

pg.setConfigOption('background', 'w')
pg.setConfigOption('foreground', 'k')
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s', datefmt='%d-%b-%y %H:%M:%S')

# Load Qt ui file into a class
MW_qtCreatorFile = os.path.join(os.path.dirname(os.path.realpath(__file__)), "./main_window.ui")
DP_qtCreatorFile = os.path.join(os.path.dirname(os.path.realpath(__file__)), "./damp_plot_widget.ui")
Ui_MainWindow, QtBaseClass = uic.loadUiType(MW_qtCreatorFile)
Ui_DampPlotWidget, QtBaseClass = uic.loadUiType(DP_qtCreatorFile)


class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super().__init__()
        QMainWindow.__init__(self)
        Ui_MainWindow.__init__(self)
        self.setupUi(self)
        self.statusBar().showMessage('Ready')
        self.setWindowTitle("Damping Box Current Plot")
        self.move(-1000,300)
        self.x = 0
        self.y = 0
        self.damp_parser = DampParser()
        # self.init_ui()
        self.setAcceptDrops(True)

        self.show()

    # def init_ui(self):
    #     # self.ui =
    #     logging.info("Setting up MainWindow ui")
    #     centralwidget = QtWidgets.QWidget(self)
    #     centralwidget.setObjectName("centralwidget")
    #     self.setCentralWidget(centralwidget)
    #
    #     self.statusBar().showMessage('Ready')
    #     self.setWindowTitle("Damping Box Current Plot")
    #     self.setGeometry(-1000, 300, 800, 600)
    #
    #     layout = QtWidgets.QVBoxLayout()
    #     self.setLayout(layout)
    #
    #     self.show()

    def dragEnterEvent(self, e):
        e.accept()
        # if e.mimeData().hasFormat('text/plain'):
        #     e.accept()
        # else:
        #     e.ignore()

    def dropEvent(self, e):
        logging.info("File dropped into main window")
        urls = [url.toLocalFile() for url in e.mimeData().urls()]
        self.open_files(urls)

    def open_files(self, files):
        # Only work with lists, so if input isn't a list, makes it one
        if not isinstance(files, list) and isinstance(files, str):
            files = [files]

        for file in files:
            times, currents = self.damp_parser.parse(file)
            damp_plot = DampPlot(times, currents)
            self.add_plot(damp_plot)

    def add_plot(self, plot_widget):
        self.gridLayout.addWidget(plot_widget, self.x, self.y)
        self.x += 1
        old_y = self.y
        self.y = int((self.x)/3)+old_y

        if old_y != self.y:
            self.x = 0


class DampParser:

    def __init__(self):
        self.re_data = re.compile(
            r'^(?P<Hours>\d\d?)\s'
            r'(?P<Minutes>\d\d?)\s'
            r'(?P<Seconds>\d\d?)\s'
            r'(?P<Num_Samples>\d\d?)\s'
            r'(?P<Avg_Current>\d+)\s',
          re.MULTILINE)

    def format_data(self, raw_data):
        times = []
        currents = []

        for item in raw_data:
            # time = datetime.time(int(item[0]), int(item[1]), int(item[2]), int(item[3]))
            time = float(item[0]) + float(item[1])/60 + float(item[2])/60/60 + float(item[3])/60/60/1000
            current = item[-1]

            times.append(time)
            currents.append(int(current))

        return times, currents

    def parse(self, filename):
        file = None

        with open(filename, "rt") as in_file:
            file = in_file.read()

        damp_data = self.re_data.findall(file)

        return self.format_data(damp_data)


class DampPlot(QWidget, Ui_DampPlotWidget):

    def __init__(self, times, currents, parent = None):
        super(DampPlot, self).__init__(parent=parent)
        QWidget.__init__(self, parent=parent)
        Ui_DampPlotWidget.__init__(self)
        # self.ui = Ui_DampPlotWidget()
        # self.ui.setupUi(self)
        self.setupUi(self)
        self.times = times
        self.currents = currents
        self.plotWidget.plot(self.times, y=self.currents)


# class Ui_DampPlotWidget(object):
#     def setupUi(self, CustomWidget):
#         CustomWidget.setObjectName("CustomWidget")
#         CustomWidget.resize(800, 600)
#         self.gridLayout = QtWidgets.QGridLayout(CustomWidget)
#         self.gridLayout.setObjectName("gridLayout")
#         self.plotWidget = pg.PlotWidget(CustomWidget)
#         self.plotWidget.setObjectName("plotWidget")
#         self.gridLayout.addWidget(self.plotWidget, 0, 0, 1, 1)
#
#         self.retranslateUi(CustomWidget)
#         QtCore.QMetaObject.connectSlotsByName(CustomWidget)
#
#     def retranslateUi(self, CustomWidget):
#         _translate = QtCore.QCoreApplication.translate
#         CustomWidget.setWindowTitle(_translate("CustomWidget", "Damping Box Plot"))
#         # self.checkBox.setText(_translate("CustomWidget", "Mouse Enabled"))


def main():
    app = QtGui.QApplication(sys.argv)
    mw = MainWindow()

    # cw = QtGui.QWidget()
    # mw.setCentralWidget(cw)
    # layout = QtGui.QVBoxLayout(cw)

    # file = ['df.log']
    # damp_parser = DampParser()
    # times, currents = damp_parser.parse(file)
    # damp_plot = DampPlot(times, currents)
    # damp_plot.show()

    app.exec_()

    # if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
    #     QtGui.QApplication.instance().exec_()


if __name__== '__main__':
    main()
