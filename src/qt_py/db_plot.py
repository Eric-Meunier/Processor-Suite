import datetime
import logging
import re
import sys
import numpy as np
from pathlib import Path
from threading import Timer

import math
import pandas as pd
import pyqtgraph as pg
from PySide2.QtCore import Qt
from PySide2.QtWidgets import (QMainWindow, QMessageBox, QGridLayout, QWidget, QMenu, QAction,
                               QFileDialog, QVBoxLayout, QLabel, QApplication)
from src.qt_py import read_file, get_icon, get_line_color

logger = logging.getLogger(__name__)
logger.setLevel("DEBUG")


class DBPlotter(QMainWindow):

    def __init__(self, parent=None, darkmode=False):
        super().__init__()
        self.parent = parent
        self.darkmode = darkmode
        self.db_files = []
        self.db_widgets = []
        self.message = QMessageBox()
        self.default_path = None

        self.x = 0
        self.y = 0

        # Format the window
        self.setWindowTitle("DB Plot")
        self.setWindowIcon(get_icon('db_plot.png'))
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

        self.openFile_Action = QAction('Open File', self.file_menu)
        self.openFile_Action.triggered.connect(self.open_file_dialog)
        self.openFile_Action.setIcon(get_icon("open.png"))
        self.actionSave_Screenshot = QAction("Save Screenshot")
        self.actionSave_Screenshot.setShortcut("Ctrl+S")
        self.actionSave_Screenshot.triggered.connect(self.save_img)
        self.actionSave_Screenshot.setIcon(get_icon("save2.png"))
        self.actionCopy_Screenshot = QAction("Copy Screenshot")
        self.actionCopy_Screenshot.setShortcut("Ctrl+C")
        self.actionCopy_Screenshot.triggered.connect(self.copy_img)
        self.actionCopy_Screenshot.setIcon(get_icon("copy.png"))

        self.show_lr_action = QAction('Show Sliding Window', self.view_menu, checkable=True)
        self.show_lr_action.setChecked(True)
        self.show_lr_action.setShortcut('r')
        self.show_lr_action.triggered.connect(toggle_lrs)

        self.show_symbols_action = QAction('Show Symbols', self.view_menu, checkable=True)
        self.show_symbols_action.setChecked(True)
        self.show_symbols_action.setShortcut('s')
        self.show_symbols_action.triggered.connect(toggle_symbols)

        self.file_menu.addAction(self.openFile_Action)
        self.file_menu.addSeparator()
        self.file_menu.addActions([self.actionCopy_Screenshot, self.actionSave_Screenshot])
        self.view_menu.addAction(self.show_lr_action)
        self.view_menu.addAction(self.show_symbols_action)

        self.menuBar().addMenu(self.file_menu)
        self.menuBar().addMenu(self.view_menu)

    def closeEvent(self, e):
        self.clear()
        e.accept()

    def keyPressEvent(self, event):
        # Remove the widget
        if event.key() == Qt.Key_Delete:
            self.remove_file()

        # Reset the range of the plots
        elif event.key() == Qt.Key_Space:
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
        default_path = None
        if self.parent:
            default_path = self.parent.project_dir_edit.text()
        files = QFileDialog().getOpenFileNames(self, 'Open Files',
                                               default_path,
                                               filter='Damp files (*.log *.txt *.rtf)')[0]
        if files:
            for file in files:
                if file.lower().endswith('log') or file.lower().endswith('txt') or file.lower().endswith('rtf'):
                    self.open(file)
                else:
                    logger.error(f"{file} is an invalid file type.")
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
        Parse the data and create the DBPlot
        """
        def to_timestamp(row):
            """
            Return a timestamp from the hours, minutes, seconds of the row.
            :param row: pd.Series
            :return: int, datetime timestamp
            """
            return (row.Hours * 3600) + (row.Minutes * 60) + row.Seconds

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
            date = parse_date(data_str)
            if not date:
                logger.info(f"No date found.")
                date_str = "[No Date]"
            else:
                global year, month, day
                year, month, day = date.group(1).split('/')
                date_str = datetime.date(int(year), int(month), int(day)).strftime('%B %d, %Y')

            # Find the data based on the regex pattern
            data = re.findall(r'\d{1,2}\s\d{1,2}\s\d{1,2}\s\d+\s\d+', data_str)
            data = [d.split() for d in data]

            # Create a data frame
            df = pd.DataFrame(data,
                              columns=['Hours', 'Minutes', 'Seconds', 'Num_samples', 'Current']).dropna().astype(int)

            if df.empty:
                logger.info(f"No data found in {name}")
                return df, date_str

            # Create a timestamp column to be used as the X axis
            df['Time'] = df.apply(to_timestamp, axis=1)

            # Convert the milliamps to amps
            df.Current = df.Current / 1000

            return df, date_str

        data_found = False
        for file in db_files:
            name = Path(file).name
            logger.info(f"Parsing file {name}.")
            str_contents = read_file(file, as_list=False)
            # For files with extra spaces. Doesn't work.
            # str_contents = re.sub(r" {2,}", "\|", str_contents)
            # str_contents = re.sub(r" ", "", str_contents)
            # str_contents = re.sub(r"\|", " ", str_contents)

            # Try to create a DBPlot for each 'read' command found
            reads = re.split(r'read ', str_contents)

            if not reads:
                logger.warning(f"No data found.")
                raise ValueError(f"No data found in {name}.")

            if len(reads) < 2:
                # No read command found
                logger.warning(f"No 'read' command found.")
                command = 'None'
                data_str = str_contents

                df, date_str = parse_data(data_str)
                if df.empty:
                    raise ValueError(f"No data found in {name}.\nEnsure that the file's encoding is UTF-8.")

                db_widget = DBPlotWidget(df, command, name, date_str, parent=self, darkmode=self.darkmode)
                self.db_widgets.append(db_widget)
                self.add_widget(db_widget)

            else:
                # Each read command found
                for i, read in enumerate(reads[1:]):
                    logger.info(F"Parsing read command #{i}.")
                    read = read.strip()
                    lines = read.split('\n')

                    if len(lines[0].strip()) == 8:
                        logger.info(f"Ramp read found.")
                        continue

                    command = 'read ' + lines[0]  # The "read" command input

                    if len(lines) < 3:  # Meaning it is only the command and no data following
                        logger.info(f"No data found.")
                        continue

                    if len(lines[0].strip()) != 4:  # Meaning it is a ramp reading
                        logger.info(f"No data found. Possible ramp reading.")
                        continue

                    data_str = '\n'.join(lines)
                    df, date_str = parse_data(data_str)
                    if df.empty:
                        logger.info(f"No data found.")
                        continue
                    else:
                        data_found = True
                        db_widget = DBPlotWidget(df, command, name, date_str, parent=self, darkmode=self.darkmode)
                        self.db_widgets.append(db_widget)
                        self.add_widget(db_widget)

                if data_found is False:
                    logger.warning(f"No data found in file.")
                    raise ValueError(f"No data found in file {name}.")

    def add_widget(self, plot_widget):
        """
        Add and position a plot widget in the grid layout.
        :param plot_widget: DBPlot object
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

    def clear(self):
        """
        Clear of all widgets/files.
        :return: None
        """
        for widget in self.db_widgets:
            self.widget_layout.removeWidget(widget)
            widget.deleteLater()
            self.db_widgets.remove(widget)
        self.x, self.y = 0, 0

    def save_img(self):
        """
        Save a screenshot of the window.
        """
        if not self.default_path:
            return

        save_path = QFileDialog().getSaveFileName(self, 'Save File Name',
                                                  str(self.default_path.with_suffix('.png')),
                                                  'PNG Files (*.PNG)')[0]

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
    def __init__(self, db_data, command, filepath, date, parent=None, darkmode=False):
        """
        :param db_data: DataFrame of damping box data.
        :param command: str, the command that was used in the damping box. Uses it for the legend name.
        :param filepath: str, filename of the damping box file,
        :param date: str, date parsed after the command
        :param parent: Qt parent object
        """
        super().__init__()
        self.parent = parent
        self.darkmode = darkmode
        self.color = get_line_color("teal", "pyqt", self.darkmode)
        self.foreground_color = get_line_color("foreground", "pyqt", self.darkmode)
        self.background_color = get_line_color("background", "pyqt", self.darkmode)
        self.data = db_data
        self.date = date
        self.curve = None
        self.symbols = None

        # Format widget
        self.setLayout(QVBoxLayout())
        self.setMinimumHeight(200)
        self.statusBar().show()

        # Create the plot
        time_axis = pg.DateAxisItem(orientation='bottom')
        self.plot_widget = pg.PlotWidget(axisItems={'bottom': time_axis})
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
            brush=pg.mkBrush(color=get_line_color("gray", "pyqt", darkmode, alpha=20)),
            hoverBrush=pg.mkBrush(color=get_line_color("gray", "pyqt", darkmode, alpha=40)),
            pen=pg.mkPen(color=get_line_color("foreground", "pyqt", darkmode, alpha=100)),
            hoverPen=pg.mkPen(color=get_line_color("foreground", "pyqt", darkmode, alpha=200)),
        )

        self.lr.sigRegionChanged.connect(self.lr_moved)
        self.lr.setZValue(-10)

        self.plot_df()

    def plot_df(self):
        """
        Plot the damping box data
        """
        self.curve = pg.PlotCurveItem(self.data.Time.to_numpy(), self.data.Current.to_numpy(),
                                      pen=pg.mkPen(color=self.color, width=2.5),
                                      )
        self.symbols = pg.ScatterPlotItem(self.data.Time, self.data.Current,
                                          symbol='+',
                                          size=6,
                                          pen=pg.mkPen(color=self.color, width=0.1),
                                          )
        self.plot_widget.addItem(self.curve)
        self.plot_widget.addItem(self.symbols)
        self.plot_widget.addItem(self.lr)

        range = self.curve.xData.max() - self.curve.xData.min()
        self.lr.setRegion([self.curve.xData.min() + (range * .05), self.curve.xData.max() - (range * .05)])
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
        self.delta_current_label.setText(f"??: {current_delta:.1f} ")
        self.median_current_label.setText(f"Median: {data.Current.median():.1f} ")

        if current_delta > 0.5:
            self.delta_current_label.setStyleSheet(f'color: {get_line_color("red", "mpl", self.darkmode)}')
        else:
            self.delta_current_label.setStyleSheet(f'color: {get_line_color("foreground", "mpl", self.darkmode)}')

        time_d = data.Time.max() - data.Time.min()
        if math.isnan(time_d) or time_d == 0.:
            self.duration_label.setText(f"Duration: nan ")
            self.rate_of_change_label.setText(f"Rate: nan ")
        else:
            hours = int(time_d / 3600)
            minutes = int(time_d % 3600 / 60)
            seconds = int(time_d % 60)
            self.duration_label.setText(f"Duration: {hours:02d}:{minutes:02d}:{seconds:02d} ")
            self.rate_of_change_label.setText(f"Rate: {current_delta / (time_d / 3600):.1f} A/h ")


if __name__ == '__main__':
    from src.qt_py import dark_palette
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    darkmode = True
    if darkmode:
        app.setPalette(dark_palette)
    pg.setConfigOptions(antialias=True)
    pg.setConfigOption('crashWarning', True)
    pg.setConfigOption('background', (66, 66, 66) if darkmode else 'w')
    pg.setConfigOption('foreground', "w" if darkmode else (53, 53, 53))
    mw = DBPlotter(darkmode=darkmode)

    samples_folder = str(Path(Path(__file__).absolute().parents[2]).joinpath(r'sample_files\Damping box files'))

    # files = str(Path(samples_folder).joinpath('CM 252.txt'))
    # files = str(Path(samples_folder).joinpath('Date error/0511_May11Dampingbox232Voltage.txt'))
    files = str(Path(samples_folder).joinpath('Date error/1113_DX233-20211113.log'))
    # files = str(Path(samples_folder).joinpath('0724_238-20210724 (no data error).log'))
    # files = str(Path(samples_folder).joinpath('1110_Nov10DB228Current.txt'))
    # files = str(Path(samples_folder).joinpath(r'Extra spaces\1108_CM 252 11,08.txt'))
    mw.open(files)
    mw.show()

    app.exec_()
