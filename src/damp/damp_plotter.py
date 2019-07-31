import re
import os
import sys
import datetime
import statistics as stats
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
        self.setWindowIcon(
            QtGui.QIcon(os.path.join(os.path.dirname(os.path.realpath(__file__)), "../qt_ui/icons/crone_logo.ico")))
        self.move(-1000, 300)
        self.setAcceptDrops(True)

        mainMenu = self.menuBar()

        openFile = QtGui.QAction("&Open File", self)
        openFile.setShortcut("Ctrl+O")
        openFile.setStatusTip('Open File')
        openFile.triggered.connect(self.open_file_dialog)

        clearFiles = QtGui.QAction("&Clear Files", self)
        clearFiles.setShortcut("C")
        clearFiles.setStatusTip('Clear All Open Files')
        clearFiles.triggered.connect(self.clear_files)

        fileMenu = mainMenu.addMenu('&File')
        fileMenu.addAction(openFile)
        fileMenu.addAction(clearFiles)

        self.x = 0
        self.y = 0
        self.damp_parser = DampParser()

        self.open_widgets = []

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
        self.file_open(urls)

    def open_file_dialog(self):
        try:
            file = QtGui.QFileDialog.getOpenFileName(self, 'Open File')
            # file = open(name, 'r')
            self.file_open(file[0])
        except Exception as e:
            logging.warning(str(e))
            QtGui.QMessageBox.information(None, 'Error', str(e))
            raise

    def file_open(self, files):
        # Only work with lists, so if input isn't a list, makes it one
        if not isinstance(files, list) and isinstance(files, str):
            files = [files]

        for file in files:
            try:
                damp_data = self.damp_parser.parse(file)
            except Exception as e:
                logging.warning(str(e))
                QtGui.QMessageBox.information(None, 'Error', str(e))
                raise
            else:
                damp_plot = DampPlot(damp_data)
                self.add_plot(damp_plot)

    def clear_files(self):
        logging.info('All files deleted')
        try:
            for widget in self.open_widgets:
                self.gridLayout.removeWidget(widget)
                widget.deleteLater()
            self.open_widgets.clear()
        except Exception as e:
            logging.info(str(e))
            QtGui.QMessageBox.information(None, 'Error', str(e))
            raise

    def add_plot(self, plot_widget):
        self.open_widgets.append(plot_widget)
        self.gridLayout.addWidget(plot_widget, self.x, self.y)
        self.x += 1
        old_y = self.y
        self.y = int(self.x / 3) + old_y

        if old_y != self.y:
            self.x = 0


class DampParser:
    def __init__(self):
        self.re_data = re.compile(
            r'(?P<Hours>\d{1,2})\s'
            r'(?P<Minutes>\d{1,2})\s'
            r'(?P<Seconds>\d{1,2})\s'
            r'(?P<Num_Samples>\d{1,3})\s'
            r'(?P<Avg_Current>\d+)\s',
            re.MULTILINE)

        self.re_date = re.compile(
            r'\d{4}\/\d{2}\/\d{2}'
        )

        self.damp_data = None
        self.survey_date = None

    def format_data(self, raw_data):
        times = []
        currents = []

        for item in raw_data:
            # time = datetime.time(int(item[0]), int(item[1]), int(item[2]), int(item[3]))
            time = float(item[0]) + float(item[1]) / 60 + float(item[2]) / 60 / 60 + float(item[3]) / 60 / 60 / 1000
            current = item[-1]

            times.append(time)
            currents.append(float(int(current)/1000))

        return times, currents

    def get_date(self, dates):
        if dates:
            formatted_dates = []

            for date in dates:
                split_date = date.split('/')
                date_obj = datetime.date(int(split_date[0]), int(split_date[1]), int(split_date[2]))
                formatted_dates.append(date_obj)

            return max(formatted_dates)
        else:
            return None

    def parse(self, filename):
        file = None

        with open(filename, "rt") as in_file:
            file = in_file.read()

        self.damp_data = self.format_data(self.re_data.findall(file))
        times = self.damp_data[0]
        currents = self.damp_data[1]

        self.survey_date = self.get_date(set(self.re_date.findall(file)))

        return {'times': times, 'currents': currents, 'date': self.survey_date}


class DampPlot(QWidget, Ui_DampPlotWidget):

    def __init__(self, file, grid=True, parent=None):
        super(DampPlot, self).__init__(parent=parent)
        QWidget.__init__(self, parent=parent)
        Ui_DampPlotWidget.__init__(self)
        self.setupUi(self)

        self.times = file['times']
        self.currents = file['currents']
        self.date = file['date']
        self.grid = grid

        self.create_plot()

    def create_plot(self):
        tick_label_font = QtGui.QFont()
        tick_label_font.setPixelSize(11)
        tick_label_font.setBold(False)

        labelStyle = {'color':'black', 'font-size':'10pt', 'bold':True, 'font-family': 'Nimbus Roman No9 L', 'italic':True}

        pw = self.plotWidget
        pw.plot(self.times, y=self.currents, pen=pg.mkPen('m', width=2))

        min, max = (stats.median(self.currents)-1, stats.median(self.currents)+1)
        pw.setYRange(min, max)

        if self.date:
            pw.setTitle('Damping Box Current '+self.date.strftime("%B %d, %Y"))
        else:
            pw.setTitle('Damping Box Current ')

        pw.showGrid(x=self.grid, y=self.grid, alpha=0.15)

        pw.showAxis('right', show=True)
        pw.showAxis('top', show=True)
        pw.showLabel('right', show=False)
        pw.showLabel('top', show=False)

        pw.getAxis("bottom").tickFont = tick_label_font
        pw.getAxis("left").tickFont = tick_label_font
        pw.getAxis("bottom").setStyle(tickTextOffset=10)
        pw.getAxis("left").setStyle(tickTextOffset=10)
        pw.getAxis("right").setStyle(showValues=False)
        pw.getAxis("top").setStyle(showValues=False)

        pw.setLabel('left', "Current", units='A', **labelStyle)
        pw.setLabel('bottom', "Time", units='', **labelStyle)


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

    # file = 'df.log'
    #     # damp_parser = DampParser()
    #     # damp_data = damp_parser.parse(file)
    #     # damp_plot = DampPlot(damp_data)
    #     # damp_plot.show()

    app.exec_()

    # if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
    #     QtGui.QApplication.instance().exec_()


if __name__ == '__main__':
    main()
