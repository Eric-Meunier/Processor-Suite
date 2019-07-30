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
qtCreatorFile = os.path.join(os.path.dirname(os.path.realpath(__file__)), "./damp_plot_widget.ui")
Ui_DampPlotWidget, QtBaseClass = uic.loadUiType(qtCreatorFile)


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.damp_parser = DampParser()
        self.init_ui()
        self.setAcceptDrops(True)

    def init_ui(self):
        logging.info("Setting up MainWindow ui")
        centralwidget = QtWidgets.QWidget(self)
        centralwidget.setObjectName("centralwidget")
        self.setCentralWidget(centralwidget)

        self.statusBar().showMessage('Ready')
        self.setWindowTitle("Damping Box Current Plot")
        self.setGeometry(-1000, 300, 800, 600)

        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)

        self.show()

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
        times, currents = self.damp_parser.parse(files)
        damp_plot = DampPlot(times, currents)
        self.add_plot(damp_plot)

    def add_plot(self, widget):
        self.layout().addWidget(widget)


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

    def parse(self, files):
        file = None

        # TODO Opening multiple files
        for filename in files:
            with open(filename, "rt") as in_file:
                file = in_file.read()

        damp_data = self.re_data.findall(file)

        return self.format_data(damp_data)


class DampPlot(QWidget):

    def __init__(self, times, currents, parent = None):
        super(DampPlot, self).__init__(parent=parent)
        self.ui = Ui_DampPlotWidget()
        self.ui.setupUi(self)
        self.times = times
        self.currents = currents
        self.ui.plotWidget.plot(self.times, y=self.currents)


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
    #
    # damp_plot = DampPlot(times, currents)
    # damp_plot.show()

    app.exec_()

    if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
        QtGui.QApplication.instance().exec_()


if __name__== '__main__':
    main()
