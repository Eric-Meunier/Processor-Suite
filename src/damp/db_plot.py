import re
import os
import sys
import datetime
import codecs
import statistics as stats
import pyqtgraph as pg
from src.damp.time_axis import AxisTime
import logging
from PyQt5.QtWidgets import (QWidget, QMainWindow, QApplication, QGridLayout, QDesktopWidget, QMessageBox)
from PyQt5 import (QtCore, QtGui, uic)

pg.setConfigOption('background', 'w')
pg.setConfigOption('foreground', 'k')
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s', datefmt='%d-%b-%y %H:%M:%S')

__version__ = '0.0.2'

if getattr(sys, 'frozen', False):
    # If the application is run as a bundle, the pyInstaller bootloader
    # extends the sys module by a flag frozen=True and sets the app
    # path into variable _MEIPASS'.
    application_path = sys._MEIPASS
else:
    application_path = os.path.dirname(os.path.abspath(__file__))

# Load Qt ui file into a class
DB_Window_qtCreatorFile = os.path.join(os.path.dirname(application_path), 'qt_ui\\db_plot_window.ui')
DB_Widget_qtCreatorFile = os.path.join(os.path.dirname(application_path), 'qt_ui\\db_plot_widget.ui')
Ui_DB_Window, QtBaseClass = uic.loadUiType(DB_Window_qtCreatorFile)
Ui_DB_Widget, QtBaseClass = uic.loadUiType(DB_Widget_qtCreatorFile)


class DBPlot(QMainWindow, Ui_DB_Window):
    def __init__(self):
        super().__init__()
        self.initUi()
        self.initActions()

        self.filename = None
        self.show_coords = False
        self.show_grids = True
        self.show_symbols = False

        self.x = 0
        self.y = 0

        self.damp_parser = DampParser()
        self.message = QMessageBox()

        self.open_widgets = []

    def initUi(self):
        def center_window(self):
            qtRectangle = self.frameGeometry()
            centerPoint = QDesktopWidget().availableGeometry().center()
            qtRectangle.moveCenter(centerPoint)
            self.move(qtRectangle.topLeft())
            # self.show()
        self.setupUi(self)
        self.dialog = QtGui.QFileDialog()
        self.statusBar().showMessage('Ready')
        self.setWindowTitle("DB Plot  v"+str(__version__))
        self.setWindowIcon(
            QtGui.QIcon(os.path.join(application_path, "crone_logo.ico")))
        # self.setGeometry(500, 300, 800, 600)
        center_window(self)

    def initActions(self):
        self.setAcceptDrops(True)
        self.mainMenu = self.menuBar()

        self.openFile = QtGui.QAction("&Open File", self)
        self.openFile.setShortcut("Ctrl+O")
        self.openFile.setStatusTip('Open file')
        self.openFile.triggered.connect(self.open_file_dialog)

        self.clearFiles = QtGui.QAction("&Clear Files", self)
        self.clearFiles.setShortcut("Del")
        self.clearFiles.setStatusTip('Clear all open files')
        self.clearFiles.triggered.connect(self.clear_files)

        self.resetRange = QtGui.QAction("&Reset Ranges", self)
        self.resetRange.setShortcut(" ")
        self.resetRange.setStatusTip("Reset the X and Y axes ranges of all plots")
        self.resetRange.triggered.connect(self.reset_range)

        self.savePlots = QtGui.QAction("&Save Plots", self)
        self.savePlots.setShortcut("Ctrl+S")
        self.savePlots.setStatusTip("Save all plots as PNG")
        self.savePlots.triggered.connect(self.save_plots)

        self.showCoords = QtGui.QAction("&Show Mouse Values", self)
        self.showCoords.setShortcut("V")
        self.showCoords.setStatusTip("Show the plots values where the mouse is positioned")
        self.showCoords.triggered.connect(self.toggle_coords)

        self.showGrids = QtGui.QAction("&Show Grid Lines", self)
        self.showGrids.setShortcut("G")
        self.showGrids.setStatusTip("Show grid lines on the plots")
        self.showGrids.triggered.connect(self.toggle_grid)

        self.showSymbols = QtGui.QAction("&Show Symbols", self)
        self.showSymbols.setShortcut("t")
        self.showSymbols.setStatusTip("Show data points symbols on plots")
        self.showSymbols.triggered.connect(self.toggle_symbols)

        self.fileMenu = self.mainMenu.addMenu('&File')
        self.fileMenu.addAction(self.openFile)
        self.fileMenu.addAction(self.savePlots)

        self.viewMenu = self.mainMenu.addMenu('&View')
        self.viewMenu.addAction(self.showCoords)
        self.viewMenu.addAction(self.showGrids)
        self.viewMenu.addAction(self.clearFiles)
        self.viewMenu.addAction(self.resetRange)
        self.viewMenu.addAction(self.showSymbols)

    def dragEnterEvent(self, e):
        urls = [url.toLocalFile() for url in e.mimeData().urls()]

        def check_extension(urls):
            for url in urls:
                if url.lower().endswith('log') or url.lower().endswith('txt') or url.lower().endswith('rtf'):
                    continue
                else:
                    return False
            return True

        if check_extension(urls):
            e.accept()
        else:
            e.ignore()

    def dropEvent(self, e):
        try:
            urls = [url.toLocalFile() for url in e.mimeData().urls()]
            self.open_files(urls)
            # Resize the window
            if self.gridLayout.sizeHint().height() > self.size().height() or self.gridLayout.sizeHint().width() > self.size().width():
                self.resize(self.gridLayout.sizeHint().width(), self.gridLayout.sizeHint().height())
        except Exception as e:
            logging.warning(str(e))
            self.message.information(None, 'Error', str(e))
            pass

    def open_file_dialog(self):
        try:
            file = QtGui.QFileDialog.getOpenFileName(self, 'Open File')
            if file[0].endswith('log') or file[0].endswith('txt') or file[0].endswith('rtf'):
                self.open_files(file[0])
            else:
                self.message.information(None, 'Error', 'Invalid File Format')
                return
        except Exception as e:
            logging.warning(str(e))
            self.message.information(None, 'Error', str(e))
            return

    def open_files(self, files):
        # Only work with lists (to accomodate files with multiple logs, so if input isn't a list, makes it one
        if not isinstance(files, list) and isinstance(files, str):
            files = [files]
        for file in files:
            try:
                damp_data = self.damp_parser.parse(file)
            except Exception as e:
                logging.warning(str(e))
                self.message.information(None, 'Error', str(e))
                return
            else:
                damp_plot = DampPlot(damp_data, grid=self.show_grids, show_coords=self.show_coords,
                                     show_symbols=self.show_symbols)
                self.open_widgets.append(damp_plot)
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
            self.message.information(None, 'Error', str(e))
            raise

    def reset_range(self):
        if len(self.open_widgets)>0:
            try:
                for widget in self.open_widgets:
                    widget.set_ranges()

            except Exception as e:
                self.message.information(None, 'Error',str(e))
                logging.info(str(e))
                pass

    def save_plots(self):
        # Save all plots on the window into a PNG image, basically a screen shot
        default_path = self.open_widgets[-1].folderpath
        dates = [widget.date for widget in self.open_widgets if widget.date is not None]

        if dates:
            min_date, max_date = min(dates), max(dates)
            min_str_date = min_date.strftime("%B %d, %Y") if min_date else None
            max_str_date = max_date.strftime("%B %d, %Y") if max_date else None

            if min_str_date != max_str_date:
                file_name = '/' + min_str_date + '-' + max_str_date + ' Current Logs.png'
            else:
                file_name = '/' + min_str_date + ' Current Logs.png' if min_str_date else '/' + max_str_date + ' Current Logs.png'
        else:
            file_name = '/Current Logs.png'

        self.mainMenu.hide()
        self.statusBar().hide()

        self.dialog.setFileMode(QtGui.QFileDialog.Directory)
        self.dialog.setDirectory(default_path)
        # file_dialog.setOption(QFileDialog.ShowDirsOnly)
        file_dir = QtGui.QFileDialog.getExistingDirectory(self, '', default_path)

        if file_dir:
            self.grab().save(file_dir + file_name)
        else:
            logging.info("No directory chosen, aborted save")
            pass

        self.mainMenu.show()
        self.statusBar().showMessage('Ready')

    def toggle_coords(self):
        # Toggle displaying the plot values at the location of the mouse
        self.show_coords = not self.show_coords
        if len(self.open_widgets) > 0:
            for widget in self.open_widgets:
                widget.show_coords = self.show_coords
                if self.show_coords:
                    widget.text.setText('')
                    widget.text.show()
                else:
                    widget.text.hide()

    def toggle_grid(self):
        self.show_grids = not self.show_grids
        if len(self.open_widgets) > 0:
            for widget in self.open_widgets:
                widget.pw.showGrid(x=self.show_grids, y=self.show_grids)

    def toggle_symbols(self):
        self.show_symbols = not self.show_symbols
        if len(self.open_widgets) > 0:
            for widget in self.open_widgets:
                if self.show_symbols:
                    for symbols in widget.symbols:
                        widget.pw.addItem(symbols)
                else:
                    for symbols in widget.symbols:
                        widget.pw.removeItem(symbols)
        else:
            pass

    def add_plot(self, plot_widget):
        # Adding the plot object to the layout
        self.gridLayout.addWidget(plot_widget, self.x, self.y)
        self.x += 1
        old_y = self.y
        self.y = int(self.x / 3) + old_y

        if old_y != self.y:
            self.x = 0


class DampParser:
    def __init__(self):
        self.re_split_ramp = re.compile(
            r'read\s+\d{8}([\r\n].*$)*', re.MULTILINE
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
                ts_seconds = int(datetime.timedelta(hours=timestamp.hour, minutes=timestamp.minute,
                                                    seconds=timestamp.second).total_seconds())
                current = item[-1]

                times.append(ts_seconds)
                currents.append(float(int(current) / 1000))

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

    def parse(self, filepath):
        file = None
        damp_data = []
        survey_date = None
        filename = filepath.split('/')[-1].split('.')[0]
        folderpath = '/'.join(filepath.split('/')[0:-1])

        raw = open(filepath, 'rb').read()  # Read the file as bytes first...

        # This try is only needed because some files are encoded in utf-16le (no bom) for some reason
        # If a BOM is present, we know what to use to decode
        if raw.startswith(codecs.BOM_UTF16_LE):
            file = raw.decode('utf-16le')
        elif raw.startswith(codecs.BOM_UTF16_BE):
            file = raw.decode('utf-16be')
        elif raw.startswith(codecs.BOM_UTF8):
            file = raw.decode('utf-8')
        else:
            # If no BOM is present, becomes trial and error
            try:
                decoded = raw.decode('utf-16le').encode('ascii')
                file = raw.decode('utf-16le')
            except UnicodeEncodeError:
                try:
                    decoded = raw.decode('utf-16be').encode('ascii')
                    file = raw.decode('utf-16be')
                except UnicodeEncodeError:
                    file = raw.decode('utf-8')

        file_no_ramp = re.split(self.re_split_ramp, file)[0]
        split_file = re.split(self.re_split_file, file_no_ramp)

        for section in split_file:
            data = self.format_data(self.re_data.findall(section))
            if data is not None:
                times = data[0]
                currents = data[1]
                damp_data.append({'times': times, 'currents': currents})

        survey_date = self.get_date(set(self.re_date.findall(file)))

        for item in damp_data:
            item['date'] = survey_date
            item['filename'] = filename
            item['folderpath'] = folderpath

        return damp_data


class DampPlot(QWidget, Ui_DB_Widget):

    def __init__(self, file, show_coords=False, grid=True, show_symbols=True, parent=None):
        super(DampPlot, self).__init__(parent=parent)
        QWidget.__init__(self, parent=parent)
        Ui_DB_Widget.__init__(self)
        self.setupUi(self)

        self.pw = None
        self.__axisTime = AxisTime(orientation='bottom')
        self.file = file
        self.filename = file[0]['filename']
        self.folderpath = file[0]['folderpath']
        self.grid = grid
        self.times = []
        self.currents = []
        self.date = None
        self.curves = []
        self.symbols = []
        self.mouse_x_txt = 0
        self.mouse_y_txt = 0
        self.text = pg.TextItem(text='', color=(0, 0, 0), border='w', fill=(255, 255, 255), anchor=(1, 1.1))
        self.text.setZValue(4)
        self.setMouseTracking(True)
        self.show_coords = show_coords
        self.show_symbols = show_symbols
        self.create_plot()

    def leaveEvent(self, e):
        self.text.hide()

    def create_plot(self):
        tick_label_font = QtGui.QFont()
        tick_label_font.setPixelSize(11)
        tick_label_font.setBold(False)

        labelStyle = {'color': 'black', 'font-size': '10pt', 'bold': True, 'font-family': 'Nimbus Roman No9 L',
                      'italic': True}

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
        # self.pw.setLabel('bottom', "Time", units='', **labelStyle)

        self.pw.plot()

        # Plotting section
        try:
            for i, file in enumerate(self.file):
                times = file['times']
                currents = file['currents']
                self.date = file['date']

                self.times.append(times)
                self.currents.append(currents)

                color = pg.intColor(i)
                custom_pen = pg.mkPen(color=color, width=3)
                # self.pw.plot(x=self.times, y=self.currents, pen=custom_pen)#, symbol='+', symbolSize=8, symbolPen='r')
                curve = pg.PlotCurveItem(times, currents, pen=custom_pen)
                symbols = pg.PlotDataItem(times, currents, symbol='d', symbolSize=8,
                                               symbolPen=color, symbolBrush=color)
                self.curves.append(curve)
                self.symbols.append(symbols)

                self.pw.addItem(curve)
                if self.show_symbols:
                    self.pw.addItem(symbols)

            self.pw.disableAutoRange()
            self.pw.addItem(self.text)
            self.set_ranges()

            if self.date:
                self.pw.setTitle('Damping Box Current ' + self.date.strftime("%B %d, %Y"))
            else:
                self.pw.setTitle('Damping Box Current ')

        except Exception as e:
            logging.info(str(e))
            self.message.information(None, 'Error', str(e))

        def mouseMoved(e):
            # Retrieves the coordinates of the mouse coordinates of the event
            self.mouse_y_txt = str(round(self.pw.plotItem.vb.mapSceneToView(e).y(), 4))
            self.mouse_x_txt = str(datetime.timedelta(seconds=self.pw.plotItem.vb.mapSceneToView(e).x())).split('.')[0]
            if self.show_coords:
                self.text.show()
                self.text.setText(text='Time: ' + str(self.mouse_x_txt) + '\nCurrent: ' + str(self.mouse_y_txt))
                self.text.setPos(self.pw.plotItem.vb.mapSceneToView(e))
            else:
                pass

        # Connects the action of moving the mouse to mouseMoved function
        self.pw.scene().sigMouseMoved.connect(mouseMoved)

    def set_ranges(self):

        offset = 0.5*(max([stats.median(currents) for currents in self.currents]) - min([stats.median(currents) for currents in self.currents]))
        median = stats.median([stats.median(currents) for currents in self.currents])
        min_y, max_y = median - max(offset, 1), median + max(offset, 1)
        min_x, max_x = min([item for sublist in self.times for item in sublist]), max([item for sublist in self.times for item in sublist])

        self.pw.setYRange(min_y, max_y)
        self.pw.setXRange(min_x, max_x)


def main():
    app = QtGui.QApplication(sys.argv)
    mw = DBPlot()
    mw.show()
    app.exec_()

    # file = 'df.log'
    # damp_parser = DampParser()
    # damp_data = damp_parser.parse(file)
    # damp_plot = DampPlot(damp_data)
    # damp_plot.show()

    # if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
    #     QtGui.QApplication.instance().exec_()


if __name__ == '__main__':
    main()
