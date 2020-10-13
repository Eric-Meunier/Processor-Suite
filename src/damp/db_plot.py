import datetime
import logging
import os
import re
import sys
from pathlib import Path
from threading import Timer

import pandas as pd
import pyqtgraph as pg
from PyQt5 import (QtCore, QtGui)
from PyQt5.QtWidgets import (QWidget, QMainWindow, QShortcut, QVBoxLayout, QGridLayout, QMessageBox, QFileDialog,
                             QLabel, QAction, QMenu, QApplication)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

file_format = logging.Formatter('\n%(asctime)s - %(filename)s (%(funcName)s)\n%(levelname)s: %(message)s',
                                datefmt='%m/%d/%Y %I:%M:%S %p')
stream_format = logging.Formatter('%(filename)s (%(funcName)s)\n%(levelname)s: %(message)s')

stream_handler = logging.StreamHandler(stream=sys.stdout)
stream_handler.setLevel(logging.INFO)
stream_handler.setFormatter(stream_format)

file_handler = logging.FileHandler(filename='err.log', mode='w')
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(file_format)

logger.addHandler(stream_handler)
logger.addHandler(file_handler)


pg.setConfigOptions(antialias=True)
pg.setConfigOption('background', 'w')
pg.setConfigOption('foreground', 'k')
pg.setConfigOption('crashWarning', True)

__version__ = '0.5'

if getattr(sys, 'frozen', False):
    # If the application is run as a bundle, the pyInstaller bootloader
    # extends the sys module by a flag frozen=True and sets the app
    # path into variable _MEIPASS'.
    application_path = os.path.dirname(sys.executable)
    icons_path = 'qt_ui\\icons'
else:
    application_path = os.path.dirname(os.path.abspath(__file__))
    icons_path = os.path.join(os.path.dirname(application_path), "qt_ui\\icons")


class DBPlotter(QMainWindow):

    def __init__(self, parent=None):
        super().__init__()
        self.parent = parent
        self.db_files = []
        self.db_widgets = []
        self.message = QMessageBox()
        self.default_path = None

        self.x = 0
        self.y = 0

        # Format the window
        self.setWindowTitle("DB Plot v" + str(__version__))
        self.setWindowIcon(QtGui.QIcon(os.path.join(icons_path, 'db_plot 32.png')))
        self.resize(800, 700)
        self.setAcceptDrops(True)

        self.setLayout(QVBoxLayout())

        # Create and format a central widget
        self.widget_layout = QGridLayout()
        self.widget_layout.setContentsMargins(0, 0, 0, 0)
        self.widget = QWidget()
        self.widget.setLayout(self.widget_layout)
        self.setCentralWidget(self.widget)

        # Menu
        def toggle_lrs():
            """
            Toggle the visibility of the linear region item in all the plots.
            """
            if self.show_lr_action.isChecked():
                for widget in self.db_widgets:
                    widget.plot_widget.addItem(widget.lr)
            else:
                for widget in self.db_widgets:
                    widget.plot_widget.removeItem(widget.lr)

        def toggle_symbols():
            """
            Toggle the visibility of the scatter points in all the plots.
            """
            if self.show_symbols_action.isChecked():
                for widget in self.db_widgets:
                    widget.plot_widget.addItem(widget.symbols)
            else:
                for widget in self.db_widgets:
                    widget.plot_widget.removeItem(widget.symbols)

        self.file_menu = QMenu("File", self)
        self.view_menu = QMenu("View", self)

        self.open_file_action = QAction('Open', self.file_menu)
        self.open_file_action.triggered.connect(self.open_file_dialog)

        self.show_lr_action = QtGui.QAction('Show Sliding Window', self.view_menu, checkable=True)
        self.show_lr_action.setChecked(True)
        self.show_lr_action.setShortcut('r')
        self.show_lr_action.triggered.connect(toggle_lrs)

        self.show_symbols_action = QtGui.QAction('Show Symbols', self.view_menu, checkable=True)
        self.show_symbols_action.setChecked(True)
        self.show_symbols_action.setShortcut('s')
        self.show_symbols_action.triggered.connect(toggle_symbols)

        self.file_menu.addAction(self.open_file_action)
        self.view_menu.addAction(self.show_lr_action)
        self.view_menu.addAction(self.show_symbols_action)

        self.menuBar().addMenu(self.file_menu)
        self.menuBar().addMenu(self.view_menu)

        # Actions
        self.save_shortcut = QShortcut(QtGui.QKeySequence("Ctrl+S"), self)
        self.copy_shortcut = QShortcut(QtGui.QKeySequence("Ctrl+C"), self)
        self.save_shortcut.activated.connect(self.save_img)
        self.copy_shortcut.activated.connect(self.copy_img)

        # self.scroll_area = QScrollArea()
        # self.scroll_area.setLayout(QVBoxLayout())
        # self.scroll_area.layout().setContentsMargins(0, 0, 0, 0)
        # # self.scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOn)
        # self.scroll_area.setWidgetResizable(True)
        # # self.scroll_area.setGeometry(10, 10, 200, 200)
        # self.layout().addWidget(self.scroll_area)
        # self.setCentralWidget(self.scroll_area)
        #
        # self.scroll_area_widget = QWidget()
        # self.vbox = QVBoxLayout()
        # self.scroll_area_widget.setLayout(self.vbox)
        # self.scroll_area.setWidget(self.scroll_area_widget)

    def keyPressEvent(self, event):
        # Remove the widget
        if event.key() == QtCore.Qt.Key_Delete:
            self.remove_file()

        # Reset the range of the plots
        elif event.key() == QtCore.Qt.Key_Space:
            if self.db_widgets:
                for w in self.db_widgets:
                    w.reset_range()

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
            self.window().statusBar().showMessage('Invalid file type', 1000)

    def dropEvent(self, e):
        urls = [url.toLocalFile() for url in e.mimeData().urls()]
        self.open(urls)

    def open_file_dialog(self):
        files = QFileDialog().getOpenFileNames(self, 'Open Files',
                                               filter='Damp files (*.log *.txt *.rtf)')[0]
        if files:
            for file in files:
                if file.lower().endswith('log') or file.lower().endswith('txt') or file.lower().endswith('rtf'):
                    self.open(file)
                else:
                    nt(f"Invalid file type")
        else:
            pass

    def open(self, db_files):
        if not isinstance(db_files, list):
            db_files = [db_files]

        # Use the first opened file's filepath to be used as the default path for save_img.
        if not self.default_path:
            self.default_path = Path(db_files[0])

        try:
            self.create_db_widget(db_files)
        except Exception as e:
            self.message.critical(self, 'Error', str(e))
            pass

    def create_db_widget(self, db_files):
        """
        Parse the data and create the DBPlotWidget
        """

        def to_timestamp(row):
            """
            Return a timestamp from the hours, minutes, seconds of the row and the year, month, day from the read
            command.
            :param row: pd.Series
            :return: int, datetime timestamp
            """
            date_time = datetime.datetime(year=int(year),
                                          month=int(month),
                                          day=int(day),
                                          hour=row.Hours,
                                          minute=row.Minutes,
                                          second=row.Seconds)

            return date_time.timestamp()

        def parse_date(string):
            date = re.search(r'<CR>Time:(\d+\/\d+\/\d+)', string)
            return date

        def parse_data(data_str):
            """
            Create a data frame of the damping box data. The <CR> with date must be in the string, or else no timestamp
            can be created.
            :param data_str: string, raw data of a single read command.
            :return: pd DataFrame
            """

            # Date is required because the X-axis AxisItem requires a datetime timestamp
            date = parse_date(data_str)
            if not date:
                logger.error(f"Skipped data in {name} as no date can be found")
                raise Exception(f"No date found in {name}")
            else:
                global year, month, day, date_str
                year, month, day = date.group(1).split('/')
                date_str = datetime.date(int(year), int(month), int(day)).strftime('%B %d, %Y')

            # Find the data based on the regex pattern
            data = re.findall(r'\d{1,2}\s\d{1,2}\s\d{1,2}\s\d+\s\d+', data_str)
            data = [d.split() for d in data]

            # Create a data frame
            df = pd.DataFrame(data,
                              columns=['Hours', 'Minutes', 'Seconds', 'Num_samples', 'Current']
                              ).dropna().astype(int)

            if df.empty:
                raise Exception(f"Data error in {name}")

            # Create a timestamp column to be used as the X axis
            df['Time'] = df.apply(to_timestamp, axis=1)

            # Convert the miliamps to amps
            df.Current = df.Current / 1000

            return df

        for file in db_files:
            name = Path(file).name
            with open(file) as f:
                contents = f.read()

            # Try to create a DBPlotWidget for each 'read' command found
            reads = re.split(r'read ', contents)

            if not reads:
                logger.info(f"No data found in {name}")
                raise Exception(f"No data found in {name}")

            if len(reads) < 2:
                # No read command found
                logger.info(f"No 'read' command found in {name}")
                command = 'None'
                data_str = contents

                df = parse_data(data_str)

                db_widget = DBPlotWidget(df, command, name, date_str, parent=self)
                self.db_widgets.append(db_widget)
                self.add_widget(db_widget)
                # self.layout().addWidget(db_widget)

            else:
                # Each read command found
                for i, read in enumerate(reads[1:]):
                    lines = read.split('\n')
                    command = 'read ' + lines[0]  # The "read" command input

                    if len(lines) < 3:  # Meaning it is only the command and no data following
                        continue

                    if len(lines[0]) != 4:  # Meaning it is a ramp reading
                        continue

                    data_str = '\n'.join(lines)

                    df = parse_data(data_str)
                    if df.empty:
                        raise Exception(f"Data error in {name}")

                    db_widget = DBPlotWidget(df, command, name, date_str, parent=self)
                    self.db_widgets.append(db_widget)
                    self.add_widget(db_widget)
                    # self.layout().addWidget(db_widget)

    def add_widget(self, plot_widget):
        """
        Add and position a plot widget in the grid layout.
        :param plot_widget: DBPlotWidget object
        """
        # Adding the plot object to the layout
        self.widget_layout.addWidget(plot_widget, self.x, self.y)
        self.x += 1
        old_y = self.y
        self.y = int(self.x / 3) + old_y

        if old_y != self.y:
            self.x = 0

    def arrange_plots(self):
        """
        Re-arranges the layout of the plots for when a file is removed.
        """
        self.setUpdatesEnabled(False)

        for widget in self.db_widgets:
            self.widget_layout.removeWidget(widget)

        self.x, self.y = 0, 0
        for widget in self.db_widgets:
            self.add_widget(widget)

        self.setUpdatesEnabled(True)

    def remove_file(self):
        """
        Signal slot, Remove the widget beneath the mouse.
        """
        for widget in self.db_widgets:
            if widget.underMouse():
                self.widget_layout.removeWidget(widget)
                widget.deleteLater()
                self.db_widgets.remove(widget)
                break
        self.arrange_plots()

    def save_img(self):
        """
        Save a screenshot of the window.
        """
        if not self.default_path:
            return

        save_path = QFileDialog().getSaveFileName(self, 'Save File Name',
                                                  str(self.default_path.with_suffix('.png')),
                                                  'PNG Files (*.PNG);; All files(*.*)')[0]

        if save_path:
            self.grab().save(save_path)

    def copy_img(self):
        """
        Copy the image of the window to the clipboard
        """

        def hide_status_bar():
            self.statusBar().hide()

        QApplication.clipboard().setPixmap(self.grab())

        self.statusBar().show()
        t = Timer(1., hide_status_bar)  # Runs 'hide_status_bar' after 1 second
        t.start()
        self.statusBar().showMessage(f"Screen shot copied to clipboard.", 1000)


class DBPlotWidget(QMainWindow):
    """
    A widget that plots damping box data, with a linear region item that, when moved, updates
    the status bar with information within the region.
    """

    def __init__(self, db_data, command, filepath, date, parent=None):
        """
        :param db_data: DataFrame of damping box data.
        :param command: str, the command that was used in the damping box. Uses it for the legend name.
        :param filepath: str, filename of the damping box file,
        :param date: str, date parsed after the command
        :param parent: Qt parent object
        """
        super().__init__()
        self.parent = parent
        self.data = db_data
        self.date = date
        self.curve = None
        self.symbols = None

        # Format widget
        self.setLayout(QVBoxLayout())
        self.setMinimumHeight(200)
        self.statusBar().show()

        # Create the plot
        axis = pg.DateAxisItem(orientation='bottom')
        self.plot_widget = pg.PlotWidget(axisItems={'bottom': axis})
        self.setCentralWidget(self.plot_widget)

        # Format the plot
        self.plot_widget.addLegend()
        self.plot_widget.hideButtons()
        self.plot_widget.setTitle(f"{self.date} (Command: {command})")
        self.plot_widget.setLabel('left', f"Current", units='A')

        self.plot_widget.getAxis('left').enableAutoSIPrefix(enable=False)
        self.plot_widget.getAxis('right').setWidth(15)  # Move the right edge of the plot away from the window edge
        self.plot_widget.showAxis('right', show=True)
        self.plot_widget.showAxis('top', show=True)
        self.plot_widget.showLabel('right', show=False)
        self.plot_widget.showLabel('top', show=False)

        # self.plot_widget.getAxis("bottom").setStyle(tickTextOffset=10)
        # self.plot_widget.getAxis("left").setStyle(tickTextOffset=10)
        self.plot_widget.getAxis("right").setStyle(showValues=False)
        self.plot_widget.getAxis("top").setStyle(showValues=False)

        # Status bar
        self.min_current_label = QLabel()
        self.min_current_label.setIndent(4)
        self.max_current_label = QLabel()
        self.max_current_label.setIndent(4)
        self.delta_current_label = QLabel()
        self.delta_current_label.setIndent(4)
        self.median_current_label = QLabel()
        self.median_current_label.setIndent(4)
        self.duration_label = QLabel()
        self.duration_label.setIndent(4)
        self.rate_of_change_label = QLabel()
        self.rate_of_change_label.setIndent(4)
        self.file_label = QLabel(f"File: {filepath}")

        self.statusBar().addWidget(self.min_current_label)
        self.statusBar().addWidget(self.max_current_label)
        self.statusBar().addWidget(self.median_current_label)
        self.statusBar().addWidget(self.delta_current_label)
        self.statusBar().addWidget(self.duration_label)
        self.statusBar().addWidget(self.rate_of_change_label)
        self.statusBar().addPermanentWidget(self.file_label)

        # Create the linear region item
        self.lr = pg.LinearRegionItem(
            brush=pg.mkBrush(color=(51, 153, 255, 20)),
            hoverBrush=pg.mkBrush(color=(51, 153, 255, 30)),
            pen=pg.mkPen(color=(0, 25, 51, 100)),
            hoverPen=pg.mkPen(color=(0, 25, 51, 200)),
        )
        self.lr.sigRegionChanged.connect(self.lr_moved)
        self.lr.setZValue(-10)

        self.plot_df()

    def plot_df(self):
        """
        Plot the damping box data
        :param command: str, the command that was used in the damping box. Uses it for the legend name.
        """
        # color = (51, 153, 255)
        color = (153, 51, 255)
        self.curve = pg.PlotCurveItem(self.data.Time.to_numpy(), self.data.Current.to_numpy(),
                                      pen=pg.mkPen(color=color, width=2.5),
                                      )
        self.symbols = pg.ScatterPlotItem(self.data.Time, self.data.Current,
                                          symbol='+',
                                          size=6,
                                          pen=pg.mkPen(color='w', width=0.1),
                                          brush=pg.mkBrush(color=color),
                                          )
        self.plot_widget.addItem(self.curve)
        self.plot_widget.addItem(self.symbols)
        self.plot_widget.addItem(self.lr)

        self.lr.setRegion([self.curve.xData.min(), self.curve.xData.max()])
        self.lr.setBounds([self.curve.xData.min(), self.curve.xData.max()])
        self.lr_moved()  # Manually trigger to update status bar information

        self.reset_range()  # Manually set the range

    def reset_range(self):
        """
        Set the range to zoom into the median current
        """
        self.plot_widget.autoRange()
        self.plot_widget.setYRange(self.data.Current.median() - 1, self.data.Current.median() + 1)

    def lr_moved(self):
        """
        Signal slot, when the linear region item is moved or changed, update the status bar information
        """
        mn, mx = self.lr.getRegion()

        # Create a filter to only include data that is within the region
        filt = (self.data.Time >= mn) & (self.data.Time <= mx)
        data = self.data[filt]

        self.min_current_label.setText(f"Min: {data.Current.min():.1f} ")
        self.max_current_label.setText(f"Max: {data.Current.max():.1f} ")
        current_delta = data.Current.max() - data.Current.min()
        self.delta_current_label.setText(f"Δ: {current_delta:.1f} ")
        self.median_current_label.setText(f"Median: {data.Current.median():.1f} ")

        if current_delta > 0.5:
            self.delta_current_label.setStyleSheet('color: red')
        else:
            self.delta_current_label.setStyleSheet('color: black')

        time_d = data.Time.max() - data.Time.min()
        hours = int(time_d / 3600)
        minutes = int(time_d % 3600 / 60)
        seconds = int(time_d % 60)
        self.duration_label.setText(f"Duration: {hours:02d}:{minutes:02d}:{seconds:02d} ")
        self.rate_of_change_label.setText(f"Rate: {current_delta / (time_d / 3600):.1f} A/h ")


if __name__ == '__main__':
    app = QtGui.QApplication(sys.argv)
    mw = DBPlotter()

    samples_folder = str(Path(Path(__file__).absolute().parents[2]).joinpath('sample_files\Damping box files'))

    files = str(Path(samples_folder).joinpath('08_247-20200914-200332.log'))
    mw.open(files)
    mw.show()

    app.exec_()
