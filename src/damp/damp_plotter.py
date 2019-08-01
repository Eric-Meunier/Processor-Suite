import re
import os
import sys
import time
import datetime
import statistics as stats
import pyqtgraph as pg
from time_axis import AxisTime
# from pyqtgraph.Qt import QtGui, QtCore
import logging
from PyQt5.QtWidgets import (QWidget, QMainWindow, QApplication, QGridLayout, QDesktopWidget)
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
        self.setGeometry(-1000, 300, 800, 600)
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
        # TODO re-set Y range
        # TODO add height with added plots
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
        # TODO make window bigger when other files are brought in
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
                self.open_widgets.append(damp_plot)

                mw_height, mw_width = self.frameGeometry().height(), self.frameGeometry().width()
                dp_height, dp_width = damp_plot.frameGeometry().height(), damp_plot.frameGeometry().width()
                if mw_height < dp_height*len(self.open_widgets):
                    self.resize(mw_width, mw_height+dp_height)
                    # QDesktopWidget().availableGemetry()
                    # self.move(self.pos().x(), self.pos().y()-dp_height)

                self.add_plot(damp_plot)

    def clear_files(self):
        try:
            for widget in self.open_widgets:
                self.gridLayout.removeWidget(widget)
                widget.deleteLater()
            self.open_widgets.clear()
            self.x = 0
            self.y = 0
        except Exception as e:
            logging.info(str(e))
            QtGui.QMessageBox.information(None, 'Error', str(e))
            raise

    def add_plot(self, plot_widget):
        self.gridLayout.addWidget(plot_widget, self.x, self.y)
        self.x += 1
        old_y = self.y
        self.y = int(self.x / 3) + old_y

        if old_y != self.y:
            self.x = 0


class DampParser:
    def __init__(self):
        self.re_split_ramp = re.compile(
            r'read\s+\d{8}([\r\n].*$)*',re.MULTILINE
        )

        self.re_data = re.compile(
            r'(?:\s|^)(?P<Hours>\d{1,2})\s'
            r'(?P<Minutes>\d{1,2})\s'
            r'(?P<Seconds>\d{1,2})\s'
            r'(?P<Num_Samples>\d{1,3})\s'
            r'(?P<Avg_Current>\d+)\s',
            re.MULTILINE)

        self.re_date = re.compile(
            r'\d{4}\/\d{2}\/\d{2}'
        )

        self.re_split_file = re.compile(
            r'Hours.*'
        )

    def format_data(self, raw_data):
        times = []
        currents = []

        if raw_data:
            for item in raw_data:
                timestamp = datetime.time(int(item[0]), int(item[1]), int(item[2]))
                ts_seconds = int(datetime.timedelta(hours=timestamp.hour, minutes=timestamp.minute, seconds=timestamp.second).total_seconds())
                current = item[-1]

                times.append(ts_seconds)
                currents.append(float(int(current)/1000))

            return times, currents
        else:
            return None

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
        self.damp_data = []
        self.survey_date = None

        with open(filename, "rt") as in_file:
            file = in_file.read()
            file_no_ramp = re.split(self.re_split_ramp, file)[0]
            split_file = re.split(self.re_split_file, file_no_ramp)

        for section in split_file:
            damp_data = self.format_data(self.re_data.findall(section))
            if damp_data is not None:
                times = damp_data[0]
                currents = damp_data[1]
                self.damp_data.append({'times': times, 'currents': currents})
            # else:
            #     times = None
            #     currents = None

        self.survey_date = self.get_date(set(self.re_date.findall(file)))

        for item in self.damp_data:
            item['date'] = self.survey_date

        return self.damp_data


class DampPlot(QWidget, Ui_DampPlotWidget):

    def __init__(self, file, grid=True, parent=None):
        super(DampPlot, self).__init__(parent=parent)
        QWidget.__init__(self, parent=parent)
        Ui_DampPlotWidget.__init__(self)
        self.setupUi(self)

        self.pw = None
        self.__axisTime = AxisTime(orientation='bottom')
        self.file = file
        self.grid = grid

        self.create_plot()

    def create_plot(self):
        tick_label_font = QtGui.QFont()
        tick_label_font.setPixelSize(11)
        tick_label_font.setBold(False)

        labelStyle = {'color':'black', 'font-size':'10pt', 'bold':True, 'font-family': 'Nimbus Roman No9 L', 'italic':True}

        self.pw = pg.PlotWidget(axisItems={'bottom': self.__axisTime})
        self.gridLayout.addWidget(self.pw)

        self.pw.showGrid(x=self.grid, y=self.grid, alpha=0.15)

        self.pw.showAxis('right', show=True)
        self.pw.showAxis('top', show=True)
        self.pw.showLabel('right', show=False)
        self.pw.showLabel('top', show=False)

        self.pw.getAxis("bottom").tickFont = tick_label_font
        self.pw.getAxis("left").tickFont = tick_label_font
        self.pw.getAxis("bottom").setStyle(tickTextOffset=10)
        self.pw.getAxis("left").setStyle(tickTextOffset=10)
        self.pw.getAxis("right").setStyle(showValues=False)
        self.pw.getAxis("top").setStyle(showValues=False)

        self.pw.setLabel('left', "Current", units='A', **labelStyle)
        self.pw.setLabel('bottom', "Time", units='', **labelStyle)

        # Plotting section
        for i, file in enumerate(self.file):
            self.times = file['times']
            self.currents = file['currents']
            self.date = file['date']

            try:
                self.pw.plot(x=self.times, y=self.currents, pen=pg.mkPen(color=pg.intColor(i+9), width=2))
                min, max = (stats.median(self.currents) - 1, stats.median(self.currents) + 1)
                self.pw.setYRange(min, max)
            except Exception as e:
                logging.info(str(e))
                QtGui.QMessageBox.information(None, 'Error', str(e))
            finally:
                self.pw.plot()

            if self.date:
                self.pw.setTitle('Damping Box Current ' + self.date.strftime("%B %d, %Y"))
            else:
                self.pw.setTitle('Damping Box Current ')


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
    # damp_parser = DampParser()
    # damp_data = damp_parser.parse(file)
    # damp_plot = DampPlot(damp_data)
    # damp_plot.show()

    app.exec_()

    # if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
    #     QtGui.QApplication.instance().exec_()


if __name__ == '__main__':
    main()
