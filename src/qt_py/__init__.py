import sys
import re
from pathlib import Path

import chardet
import numpy as np
import pandas as pd
import pyqtgraph as pg
from PySide2.QtCore import QSizeF, Qt, Signal, QPointF
from PySide2.QtGui import QKeySequence, QColor, QCursor, QPixmap, QIcon, QPalette, QIntValidator
from PySide2.QtWidgets import (QMessageBox, QWidget, QLabel, QFrame, QHBoxLayout, QVBoxLayout, QTabWidget, QMenu,
                               QAction, QComboBox, QLineEdit, QGroupBox, QGridLayout, QRadioButton,
                               QTableWidgetItem, QShortcut, QPushButton, QSizePolicy, QItemDelegate)
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from pyproj import CRS
from src.logger import logger, Log

# Modify the paths for when the script is being run in a frozen state (i.e. as an EXE)
if getattr(sys, 'frozen', False):
    application_path = Path(sys.executable).parent
else:
    application_path = Path(__file__).absolute().parents[1]  # src folder path

icons_path = application_path.joinpath("ui\\icons")

light_palette = QPalette()
dark_palette = QPalette()
dark_palette.setColor(QPalette.Window, QColor(53, 53, 53))
dark_palette.setColor(QPalette.WindowText, Qt.white)
dark_palette.setColor(QPalette.Disabled, QPalette.WindowText, Qt.gray)  # QColor(127, 127, 127))
dark_palette.setColor(QPalette.Base, QColor(42, 42, 42))
dark_palette.setColor(QPalette.AlternateBase, QColor(66, 66, 66))
dark_palette.setColor(QPalette.ToolTipBase, Qt.white)
dark_palette.setColor(QPalette.ToolTipText, Qt.white)
dark_palette.setColor(QPalette.Text, Qt.white)
dark_palette.setColor(QPalette.Disabled, QPalette.Text, QColor(200, 200, 200))
dark_palette.setColor(QPalette.Dark, QColor(35, 35, 35))
dark_palette.setColor(QPalette.Shadow, QColor(20, 20, 20))
dark_palette.setColor(QPalette.Button, QColor(53, 53, 53))
dark_palette.setColor(QPalette.ButtonText, Qt.white)
dark_palette.setColor(QPalette.Disabled, QPalette.ButtonText, Qt.gray)  # QColor(127, 127, 127))
dark_palette.setColor(QPalette.BrightText, Qt.red)
dark_palette.setColor(QPalette.Link, QColor(42, 130, 218))
dark_palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
dark_palette.setColor(QPalette.Disabled, QPalette.Highlight, QColor(80, 80, 80))
dark_palette.setColor(QPalette.HighlightedText, Qt.white)
dark_palette.setColor(QPalette.Disabled, QPalette.HighlightedText, Qt.gray)  # QColor(127, 127, 127))


def get_line_color(color, style, darkmode, alpha=255):
    """
    Return line colors for an object and for a given style.
    :param color: str, any of ['pink', 'blue', 'red', 'purple', 'aquamarine', 'green', 'teal', 'foreground',
    'background', 'gray']
    :param style: str, "mpl" or "pyqt"
    :param darkmode: bool
    :param alpha: int, between 0 and 255
    :return: str or list, depending on style.
    """
    pink_color = [255, 153, 204, alpha] if darkmode else [255, 0, 127, alpha]
    teal_color = [102, 255, 255, alpha] if darkmode else [0, 204, 204, alpha]
    yellow_color = [255, 255, 153, alpha] if darkmode else [255, 255, 0, alpha]
    blue_color = [153, 204, 255, alpha] if darkmode else [46, 151, 255, alpha]
    single_blue_color = [42, 130, 218, alpha]
    red_color = [255, 153, 153, alpha] if darkmode else [255, 0, 0, alpha]
    purple_color = [204, 153, 255, alpha] if darkmode else [127, 0, 255, alpha]
    aquamarine_color = [153, 255, 204, alpha] if darkmode else [0, 255, 128, alpha]
    green_color = [102, 255, 102, alpha] if darkmode else [0, 204, 0, alpha]
    foreground_color = [255, 255, 255, alpha] if darkmode else [0, 0, 0, alpha]
    background_color = [66, 66, 66, alpha] if darkmode else [255, 255, 255, alpha]
    gray_color = [178, 178, 178, alpha] if darkmode else [128, 128, 128, alpha]

    if color == "pink":
        if style == "mpl" or style == "hex":
            return rgb2hex(*pink_color[:-1])
        else:
            return pink_color
    elif color == "teal":
        if style == "mpl" or style == "hex":
            return rgb2hex(*teal_color[:-1])
        else:
            return teal_color
    elif color == "yellow":
        if style == "mpl" or style == "hex":
            return rgb2hex(*yellow_color[:-1])
        else:
            return yellow_color
    elif color == "blue":
        if style == "mpl" or style == "hex":
            return rgb2hex(*blue_color[:-1])
        else:
            return blue_color
    elif color == "single_blue":
        if style == "mpl" or style == "hex":
            return rgb2hex(*single_blue_color[:-1])
        else:
            return single_blue_color
    elif color == "red":
        if style == "mpl" or style == "hex":
            return rgb2hex(*red_color[:-1])
        else:
            return red_color
    elif color == "purple":
        if style == "mpl" or style == "hex":
            return rgb2hex(*purple_color[:-1])
        else:
            return purple_color
    elif color == "aquamarine":
        if style == "mpl" or style == "hex":
            return rgb2hex(*aquamarine_color[:-1])
        else:
            return aquamarine_color
    elif color == "green":
        if style == "mpl" or style == "hex":
            return rgb2hex(*green_color[:-1])
        else:
            return green_color
    elif color == "foreground":
        if style == "mpl" or style == "hex":
            return rgb2hex(*foreground_color[:-1])
        else:
            return foreground_color
    elif color == "background":
        if style == "mpl" or style == "hex":
            return rgb2hex(*background_color[:-1])
        else:
            return background_color
    elif color == "gray":
        if style == "mpl" or style == "hex":
            return rgb2hex(*gray_color[:-1])
        else:
            return gray_color
    else:
        raise NotImplementedError(f"{color} is not implemented.")


def rgb2hex(r,g,b):
    return "#{:02x}{:02x}{:02x}".format(r,g,b)


def hex2rgb(hexcode):
    return tuple(map(ord,hexcode[1:].decode('hex')))


def get_icon(filename):
    return QIcon(str(icons_path.joinpath(filename)))


def get_extension_icon(filepath):
    ext = filepath.suffix.lower()
    if ext in ['.xls', '.xlsx', '.csv']:
        icon_pix = QPixmap(str(icons_path.joinpath('excel_file.png')))
        if not (icons_path.joinpath('excel_file.png').exists()):
            print(f"{icons_path.joinpath('excel_file.png')} does not exist.")
        icon = QIcon(icon_pix)
    elif ext in ['.rtf', '.docx', '.doc']:
        icon_pix = QPixmap(str(icons_path.joinpath('word_file.png')))
        if not (icons_path.joinpath('word_file.png').exists()):
            print(f"{icons_path.joinpath('word_file.png')} does not exist.")
        icon = QIcon(icon_pix)
    elif ext in ['.log', '.txt', '.xyz', '.seg', '.dad']:
        icon_pix = QPixmap(str(icons_path.joinpath('txt_file.png')))
        if not (icons_path.joinpath('txt_file.png').exists()):
            print(f"{icons_path.joinpath('txt_file.png')} does not exist.")
        icon = QIcon(icon_pix)
    elif ext in ['.pem']:
        icon_pix = QPixmap(str(icons_path.joinpath('crone_logo.png')))
        if not (icons_path.joinpath('crone_logo.png').exists()):
            print(f"{icons_path.joinpath('crone_logo.png')} does not exist.")
        icon = QIcon(icon_pix)
    elif ext in ['.dmp', '.dmp2', '.dmp3', '.dmp4']:
        icon_pix = QPixmap(str(icons_path.joinpath('dmp.png')))
        if not (icons_path.joinpath('dmp.png').exists()):
            print(f"{icons_path.joinpath('dmp.png')} does not exist.")
        icon = QIcon(icon_pix)
    elif ext in ['.gpx', '.gdb']:
        icon_pix = QPixmap(str(icons_path.joinpath('garmin_file.png')))
        if not (icons_path.joinpath('garmin_file.png').exists()):
            print(f"{icons_path.joinpath('garmin_file.png')} does not exist.")
        icon = QIcon(icon_pix)
    elif ext in ['.ssf']:
        icon_pix = QPixmap(str(icons_path.joinpath('ssf_file.png')))
        if not (icons_path.joinpath('ssf_file.png').exists()):
            print(f"{icons_path.joinpath('ssf_file.png')} does not exist.")
        icon = QIcon(icon_pix)
    elif ext in ['.cor']:
        icon_pix = QPixmap(str(icons_path.joinpath('cor_file.png')))
        if not (icons_path.joinpath('cor_file.png').exists()):
            print(f"{icons_path.joinpath('cor_file.png')} does not exist.")
        icon = QIcon(icon_pix)
    else:
        icon_pix = QPixmap(str(icons_path.joinpath('none_file.png')))
        if not (icons_path.joinpath('none_file.png').exists()):
            print(f"{icons_path.joinpath('none_file.png')} does not exist.")
        icon = QIcon(icon_pix)
    return icon


def read_file(file, as_list=False):
    """
    Read an ascii file with automatic decoding.
    :param file: str
    :param as_list: Bool, return the contents as a single list (True) or str (False)
    :return: list or str
    """
    with open(file, 'rb') as byte_file:
        byte_content = byte_file.read()
        encoding = chardet.detect(byte_content).get('encoding')
        logger.info(f"Using {encoding} encoding for {Path(str(file)).name}.")
        contents = byte_content.decode(encoding=encoding)
    if as_list is True:
        contents = [c.strip().split() for c in contents.splitlines()]
    return contents


def df_to_table(df, table):
    """
    Add the contents of the data frame to the table
    :param df: pandas pd.DataFrame of the GPS
    :param table: QTableWidget
    :return: None
    """
    def write_row(series):
        """
         Add items from a pandas data frame row to a Qpg.TableWidget row
         :param series: pandas Series object
         :return: None
         """
        def series_to_items(x):
            # if isinstance(x, float):
            #     return QTableWidgetItem(f"{x}")
            #     # return QTableWidgetItem(f"{x:.2f}")
            # else:
            return QTableWidgetItem(str(x))

        row_pos = table.rowCount()
        table.insertRow(row_pos)

        items = series.map(series_to_items).to_list()
        # Format each item of the table to be centered
        for m, item in enumerate(items):
            item.setTextAlignment(Qt.AlignCenter)
            table.setItem(row_pos, m, item)

    if df.empty:
        logger.error(f"Empty data frame passed.")
        raise ValueError("Empty data frame passed.")
    else:
        columns = df.columns.to_list()
        table.setColumnCount(len(columns))
        table.setHorizontalHeaderLabels(columns)
        # Cast as type "object" to prevent ints being upcasted as floats
        df.astype("O").apply(write_row, axis=1)


def table_to_df(table, dtypes=None, nan_replacement=False):
    """
    Create a DataFrame from the information in the table.
    :param table: QTableWidget
    :param dtypes: list, data types of the data frame columns.
    :param nan_replacement: str, convert NaNs to this value.
    :return: pandas pd.DataFrame
    """
    header = [table.horizontalHeaderItem(i).text() for i in range(table.columnCount())]
    gps = []
    for row in range(table.rowCount()):
        gps_row = list()
        for col in range(table.columnCount()):
            gps_row.append(table.item(row, col).text())
        gps.append(gps_row)

    df = pd.DataFrame(gps, columns=header)

    if nan_replacement is not False:
        # In some data frames, the NaN is just a "nan" string
        df = df.replace(to_replace=np.nan, value=nan_replacement)
        df = df.replace(to_replace="nan", value=nan_replacement)
    if dtypes is not None:
        df = df.astype(dtypes)
    else:
        df = df.apply(pd.to_numeric, errors='coerce')
    return df


def auto_size_ax(ax, figure, buffer=0):
    """
    Change the limits of the axes so the axes fills the full size of the figure.
    :param ax: Matplotlib Axes object
    :param figure: Matplotlib Figure object
    :param buffer: int, marging (as a percentage) to add to the X and Y.
    :return: None
    """
    xmin, xmax = ax.get_xlim()
    ymin, ymax = ax.get_ylim()
    map_width, map_height = xmax - xmin, ymax - ymin

    current_ratio = map_width / map_height
    figure_ratio = figure.bbox.width / figure.bbox.height

    if current_ratio < figure_ratio:
        new_height = map_height
        new_width = new_height * figure_ratio
    else:
        new_width = map_width
        new_height = new_width * (1 / figure_ratio)

    x_offset = buffer * new_width
    # y_offset = 0.06 * new_height  # Causes large margins on the right and left
    y_offset = buffer * new_height
    new_xmin = (xmin - x_offset) - ((new_width - map_width) / 2)
    new_xmax = (xmax + x_offset) + ((new_width - map_width) / 2)
    new_ymin = (ymin - y_offset) - ((new_height - map_height) / 2)
    new_ymax = (ymax + y_offset) + ((new_height - map_height) / 2)

    ax.set_xlim(new_xmin, new_xmax)
    ax.set_ylim(new_ymin, new_ymax)


def clear_table(table):
    """
    Clear a given table
    """
    table.blockSignals(True)
    while table.rowCount() > 0:
        table.removeRow(0)
    table.blockSignals(False)


class CustomProgressDialog(pg.ProgressDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # self.setWindowFlags(Qt.CustomizeWindowHint | Qt.WindowStaysOnTopHint)
        self.setWindowFlags(Qt.CustomizeWindowHint)

        # parent = kwargs.get("parent")
        # if parent:
        #     self.setWindowTitle(parent.windowTitle())
        #     self.setWindowIcon(parent.windowIcon())

        # self.setStyleSheet("background-color: rgb(255, 255, 255);")


# class CustomProgressBar(QtWidgets.QProgressBar):
#     """No longer used"""
#
#     def __init__(self):
#         super().__init__()
#         # self.setFixedHeight(40)
#         # self.setFixedWidth(120)
#
#         COMPLETED_STYLE = """
#         QProgressBar {
#             border: 2px solid grey;
#             border-radius: 5px;
#             text-align: center;
#         }
#
#         QProgressBar::chunk {
#             background-color: #88B0EB;
#             width: 20px;
#         }
#         """
#
#         # '#37DA7E' for green
#         self.setStyleSheet(COMPLETED_STYLE)  # Old style


class NonScientific(pg.AxisItem):
    def __init__(self, *args, **kwargs):
        super(NonScientific, self).__init__(*args, **kwargs)

    def tickStrings(self, values, scale, spacing):
        return [int(value*1) for value in values]  # This line return the NonScientific notation value

    def logTickStrings(self, values, scale, spacing):
        return [int(value*1) for value in values]  # This line return the NonScientific notation value

    @property
    def nudge(self):
        if not hasattr(self, "_nudge"):
            self._nudge = 5
        return self._nudge

    @nudge.setter
    def nudge(self, nudge):
        self._nudge = nudge
        s = self.size()
        # call resizeEvent indirectly
        self.resize(s + QSizeF(1, 1))
        self.resize(s)

    def resizeEvent(self, ev=None):
        # s = self.size()

        # Set the position of the label
        nudge = self.nudge
        br = self.label.boundingRect()
        p = QPointF(0, 0)
        if self.orientation == "left":
            p.setY(int(self.size().height() / 2 + br.width() / 2))
            p.setX(-nudge)
        elif self.orientation == "right":
            p.setY(int(self.size().height() / 2 + br.width() / 2))
            p.setX(int(self.size().width() - br.height() + nudge))
        elif self.orientation == "top":
            p.setY(-nudge)
            p.setX(int(self.size().width() / 2.0 - br.width() / 2.0))
        elif self.orientation == "bottom":
            p.setX(int(self.size().width() / 2.0 - br.width() / 2.0))
            p.setY(int(self.size().height() - br.height() + nudge))
        self.label.setPos(p)
        self.picture = None


class PlanMapAxis(NonScientific):
    """
    Custom pyqtgraph axis used for Loop Planner plan view
    """
    def __init__(self, *args, **kwargs):
        NonScientific.__init__(self, *args, **kwargs)
        self.enableAutoSIPrefix(False)

    def tickStrings(self, values, scale, spacing):
        """Return the strings that should be placed next to ticks. This method is called
        when redrawing the axis and is a good method to override in subclasses.
        The method is called with a list of tick values, a scaling factor (see below), and the
        spacing between ticks (this is required since, in some instances, there may be only
        one tick and thus no other way to determine the tick spacing)

        The scale argument is used when the axis label is displaying units which may have an SI scaling prefix.
        When determining the text to display, use value*scale to correctly account for this prefix.
        For example, if the axis label's units are set to 'V', then a tick value of 0.001 might
        be accompanied by a scale value of 1000. This indicates that the label is displaying 'mV', and
        thus the tick should display 0.001 * 1000 = 1.
        """
        if self.logMode:
            return self.logTickStrings(values, scale, spacing)

        values = [float(value) for value in values]
        letter = 'N' if self.orientation == 'left' else 'E'
        strings = []
        for v in values:
            vstr = f"{v:.0f}{letter}"
            strings.append(vstr)
        return strings


class FloatDelegate(QItemDelegate):
    def __init__(self, decimals, parent=None):
        QItemDelegate.__init__(self, parent=parent)
        self.nDecimals = decimals

    def paint(self, painter, option, index):
        value = index.model().data(index, Qt.EditRole)
        try:
            number = float(value)
            painter.drawText(option.rect, Qt.AlignLeft, "{:.{}f}".format(number, self.nDecimals))
        except Exception:
            QItemDelegate.paint(self, painter, option, index)


class MapToolbar(NavigationToolbar):
    """
    Custom Matplotlib toolbar for maps. Only has the Home, Back, Forward, Pan, and Zoom buttons.
    """
    # only display the buttons we need
    toolitems = [t for t in NavigationToolbar.toolitems if
                 t[0] in ('Home', 'Back', 'Forward', 'Pan', 'Zoom')]


class TableSelector(QWidget):
    """
    Window to help facilitate selecting information from Excel or CSV files.
    Information is plotted into tables, and the table cells can be double-clicked to select all information below it,
    until the next empty cell.
    """
    accept_sig = Signal(object)

    def __init__(self, selection_labels, single_click=False, parent=None, darkmode=False):
        super().__init__()
        self.parent = parent
        self.single_click = single_click
        self.darkmode = darkmode
        self.setWindowIcon(get_icon("table.png"))
        self.setLayout(QVBoxLayout())
        self.message = QMessageBox()

        self.foreground_color = get_line_color("foreground", "mpl", True)
        self.selection_color = get_line_color("single_blue", "mpl", True)
        self.empty_background = QColor(255, 255, 255, 0)

        self.selection_labels = []
        self.selection_label_names = selection_labels
        self.selection_limit = len(selection_labels)  # Maximum number of selected columns before resetting
        self.selection_count = 0
        self.selection_values = {}
        self.selected_ranges = []  # Only used when self.single_click is False
        self.selected_cells = []  # Only used when self.single_click is True
        self.instruction_label = QLabel()

        self.tables = []
        self.tabs = QTabWidget()
        self.layout().addWidget(self.instruction_label)
        self.layout().addWidget(self.tabs)

        self.selection_label_frame = QFrame()
        self.selection_label_frame.setLayout(QHBoxLayout())
        self.selection_label_frame.layout().setContentsMargins(3, 3, 3, 3)
        self.selection_label_frame.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
        for name in self.selection_label_names:
            label = QLabel(name)
            self.selection_labels.append(label)
            self.selection_label_frame.layout().addWidget(label)
        self.highlight_label(0)
        self.layout().addWidget(self.selection_label_frame)

        self.accept_btn = QPushButton("Accept")
        self.reset_btn = QPushButton("Reset")
        self.close_btn = QPushButton("Close")
        btn_frame = QFrame()
        btn_frame.setLayout(QHBoxLayout())
        btn_frame.layout().addWidget(self.accept_btn)
        btn_frame.layout().addWidget(self.reset_btn)
        btn_frame.layout().addWidget(self.close_btn)
        self.layout().addWidget(btn_frame)

        self.reset_shortcut = QShortcut(QKeySequence("Escape"), self, self.reset)
        self.accept_btn.clicked.connect(self.accept)
        self.reset_btn.clicked.connect(self.reset)
        self.close_btn.clicked.connect(self.close)

    def reset(self):
        for range in self.selected_ranges:
            for item in range:
                item.setBackground(self.empty_background)

        for table in self.tables:
            table.clearSelection()

        self.selected_ranges = []
        self.selection_count = 0
        self.highlight_label(0)

    def accept(self):
        num_values = [len(values) for keys, values in self.selection_values.items()]
        if not all([v == num_values[0] for v in num_values]):
            logger.error(f"All selected information must have the same number of entries.\nNumber sele")
            raise ValueError(f"All selected information must have the same number of entries.\nNumber sele")

        df = pd.DataFrame(self.selection_values)
        self.accept_sig.emit(df)
        self.close()

    def cell_clicked(self, row, col):
        """
        Signal slot, color the cell and register it's contents when clicked.
        :param row: Int
        :param col: Int
        :return: None
        """
        table = self.tables[self.tabs.currentIndex()]

        # Cycle the selection back to the first item when going past the last selection
        if len(self.selected_cells) == self.selection_limit:
            self.selected_cells[0].setBackground(self.empty_background)
            self.selected_cells.pop(0)

        values = []
        item = table.item(row, col)
        item.setBackground(QColor(self.selection_color))
        values.append(item.text())

        if self.selection_count == self.selection_limit:
            self.selection_count = 0

        self.selection_values[self.selection_label_names[self.selection_count]] = values

        self.selection_count += 1
        self.highlight_label(self.selection_count)
        self.selected_cells.append(item)

    def cell_double_clicked(self, row, col):
        """
        Signal slot, range-select all cells below the clicked cell. Stops at the first empty cell.
        :return: None
        """
        table = self.tables[self.tabs.currentIndex()]

        # Remove the last selection range when going over the limit
        if len(self.selected_ranges) == 6:
            for item in self.selected_ranges[0]:
                item.setBackground(self.empty_background)
            self.selected_ranges.pop(0)

        values = []
        selected_range = []
        for selected_row in range(row, table.rowCount()):
            item = table.item(selected_row, col)
            if item is None or not item.text():
                break

            item.setBackground(QColor(self.selection_color))
            selected_range.append(item)
            values.append(item.text())

        if self.selection_count == self.selection_limit:
            self.selection_count = 0

        self.selection_values[self.selection_label_names[self.selection_count]] = values

        self.selection_count += 1
        self.highlight_label(self.selection_count)
        self.selected_ranges.append(selected_range)

    def highlight_label(self, ind):
        """
        Highlight the text of the selected index and un-highlight the rest.
        :param ind: int
        :return: None
        """
        for i, label in enumerate(self.selection_labels):
            if i < ind:
                label.setStyleSheet(f"color: {get_line_color('gray', 'hex', self.darkmode)}")
            elif i == ind:
                label.setStyleSheet(f"color: {self.selection_color}")
            else:
                label.setStyleSheet(f"color: {self.foreground_color}")

    def table_context_menu(self, event):
        """
        Right-click context menu for tables, in order to add an empty row to the table.
        :param event: QEvent object
        :return:None
        """
        def add_row(y_coord, direction):
            table = self.tabs.currentWidget()
            row = table.rowAt(y_coord)
            if direction == "up":
                print(f"Inserting row at {row}.")
                table.insertRow(row)
            else:
                print(f"Inserting row at {row + 1}.")
                table.insertRow(row + 1)

        y_coord = event.pos().y()
        menu = QMenu(self)
        add_row_above_action = QAction('Add Row Above', self)
        add_row_above_action.triggered.connect(lambda: add_row(y_coord, direction="up"))
        add_row_below_action = QAction('Add Row Below', self)
        add_row_below_action.triggered.connect(lambda: add_row(y_coord, direction="down"))
        menu.addAction(add_row_above_action)
        menu.addAction(add_row_below_action)
        menu.popup(QCursor.pos())

    def open(self, filepath):
        """
        :param filepath: str or Path, can be an Excel file, CSV, or txt file.
        :return: None
        """
        filepath = Path(filepath)

        if filepath.suffix == '.xlsx' or filepath.suffix == '.xls':
            content = pd.read_excel(filepath,
                                    header=None,
                                    sheet_name=None)

            for i, (sheet, info) in enumerate(content.items()):
                table = pg.TableWidget()
                table.setData(info.replace(np.nan, '', regex=True).to_numpy())
                self.tables.append(table)
                self.tabs.addTab(table, str(sheet))
        else:
            if filepath.suffix == '.txt' or filepath.suffix == '.dad':
                content = pd.read_csv(filepath,
                                      delim_whitespace=True,
                                      header=None)
            else:
                content = pd.read_csv(filepath,
                                      header=None)

            table = pg.TableWidget()
            table.setData(content.replace(np.nan, '', regex=True).to_numpy())
            self.tables.append(table)
            self.tabs.addTab(table, filepath.name)

        for table in self.tables:
            table.setStyleSheet(f"selection-background-color: #{self.selection_color};")
            if self.single_click is True:
                table.cellClicked.connect(self.cell_clicked)
            else:
                table.cellDoubleClicked.connect(self.cell_double_clicked)
                table.contextMenuEvent = self.table_context_menu
                table.setMouseTracking(True)
                table.viewport().installEventFilter(self)

        self.show()


class SeparatorLine(QFrame):
    def __init__(self):
        super().__init__()
        self.setFrameShape(QFrame.HLine)
        self.setFrameShadow(QFrame.Plain)


class CRSSelector(QGroupBox):
    def __init__(self, title=""):
        """
        Group box with combo boxes with the commonly used GPS systems, datums and UTM zones, along with a EPSG line.
        """
        super().__init__()
        self.crs = None
        self.setLayout(QGridLayout())
        self.setTitle(title)

        self.message = QMessageBox()
        self.epsg_label = QLabel()
        self.epsg_label.setIndent(5)

        self.crs_rbtn = QRadioButton()
        self.epsg_rbtn = QRadioButton()

        self.gps_system_cbox = QComboBox()
        self.gps_datum_cbox = QComboBox()
        self.gps_zone_cbox = QComboBox()
        separator_line = SeparatorLine()
        self.epsg_edit = QLineEdit()
        self.epsg_edit.setValidator(QIntValidator())

        gps_systems = ['', 'Lat/Lon', 'UTM']
        for system in gps_systems:
            self.gps_system_cbox.addItem(system)

        datums = ['', 'WGS 1984', 'NAD 1927', 'NAD 1983']
        for datum in datums:
            self.gps_datum_cbox.addItem(datum)

        self.layout().addWidget(self.crs_rbtn, 0, 0, 3, 1)
        self.layout().addWidget(self.epsg_rbtn, 4, 0, 1, 1)

        self.layout().addWidget(self.gps_system_cbox, 0, 1, 1, 1)
        self.layout().addWidget(self.gps_datum_cbox, 1, 1, 1, 1)
        self.layout().addWidget(self.gps_zone_cbox, 2, 1, 1, 1)
        self.layout().addWidget(separator_line, 3, 0, 1, 2)
        self.layout().addWidget(self.epsg_edit, 4, 1, 1, 1)

        # Signals
        self.gps_system_cbox.currentIndexChanged.connect(self.combo_boxes_changed)
        self.gps_datum_cbox.currentIndexChanged.connect(self.combo_boxes_changed)
        self.gps_zone_cbox.currentIndexChanged.connect(self.combo_boxes_changed)
        self.crs_rbtn.clicked.connect(self.toggle_radio_buttons)
        self.crs_rbtn.clicked.connect(self.set_epsg_label)
        self.epsg_rbtn.clicked.connect(self.toggle_radio_buttons)
        self.epsg_rbtn.clicked.connect(self.set_epsg_label)
        self.epsg_edit.editingFinished.connect(lambda: self.set_epsg(self.epsg_edit.text()))

        self.crs_rbtn.click()

    def reset(self):
        self.gps_system_cbox.setCurrentText('')
        self.gps_zone_cbox.setCurrentText('')
        self.gps_datum_cbox.setCurrentText('')
        self.epsg_label.setText("")
        self.epsg_edit.setText("")
        self.set_crs(None)

    def combo_boxes_changed(self):
        self.populate_combo_boxes()
        self.set_epsg(self.combo_box_to_epsg())

    def toggle_radio_buttons(self):
        """
        Toggle the radio buttons for the project CRS box, switching between the CRS drop boxes and the EPSG edit.
        """
        if self.crs_rbtn.isChecked():
            # Re-enables the appropriate combo boxes
            self.enable_combo_boxes()
            epsg_code = self.combo_box_to_epsg()
            self.epsg_edit.setEnabled(False)
        else:
            # Disable the CRS drop boxes and enable the EPSG line edit
            self.gps_system_cbox.setEnabled(False)
            self.gps_datum_cbox.setEnabled(False)
            self.gps_zone_cbox.setEnabled(False)

            epsg_code = self.epsg_edit.text()

            self.epsg_edit.setEnabled(True)

        try:
            crs = CRS.from_epsg(epsg_code)
        except Exception:
            crs = None
        self.set_crs(crs)

    def populate_combo_boxes(self):
        self.gps_system_cbox.blockSignals(True)
        self.gps_datum_cbox.blockSignals(True)
        self.gps_zone_cbox.blockSignals(True)

        current_zone = self.gps_zone_cbox.currentText()
        datum = self.gps_datum_cbox.currentText()
        system = self.gps_system_cbox.currentText()

        if system == 'Lat/Lon':
            self.gps_datum_cbox.setCurrentText('WGS 1984')
            self.gps_zone_cbox.setCurrentText('')

        elif "UTM" in system:
            # if datum != "":
            self.gps_zone_cbox.clear()

            zones = []
            # NAD 27 and 83 only have zones from 1N to 22N/23N
            if "1927" in datum:
                zones = [''] + [f"{num} North" for num in range(1, 23)] + ['59 North', '60 North']
            elif "1983" in datum:
                zones = [''] + [f"{num} North" for num in range(1, 24)] + ['59 North', '60 North']
            # WGS 84 has zones from 1N and 1S to 60N and 60S
            elif "1984" in datum:
                zones = [''] + [f"{num} North" for num in range(1, 61)] + [f"{num} South" for num in range(1, 61)]

            for zone in zones:
                self.gps_zone_cbox.addItem(zone)

            # Keep the same zone number if possible
            self.gps_zone_cbox.setCurrentText(current_zone)

        self.enable_combo_boxes()

        self.gps_system_cbox.blockSignals(False)
        self.gps_datum_cbox.blockSignals(False)
        self.gps_zone_cbox.blockSignals(False)

    def enable_combo_boxes(self):
        datum = self.gps_datum_cbox.currentText()
        system = self.gps_system_cbox.currentText()

        if self.crs_rbtn.isChecked():
            self.gps_system_cbox.setEnabled(True)

        if system == '':
            self.gps_zone_cbox.setEnabled(False)
            self.gps_datum_cbox.setEnabled(False)

        elif system == 'Lat/Lon':
            self.gps_datum_cbox.setEnabled(False)
            self.gps_zone_cbox.setEnabled(False)

        elif "UTM" in system:
            self.gps_datum_cbox.setEnabled(True)

            if datum == '':
                self.gps_zone_cbox.setEnabled(False)
            else:
                self.gps_zone_cbox.setEnabled(True)

    def combo_box_to_epsg(self):
        """
        Convert and return the EPSG code of the project CRS combo boxes
        :return: str
        """
        system = self.gps_system_cbox.currentText()
        zone = self.gps_zone_cbox.currentText()
        datum = self.gps_datum_cbox.currentText()

        if system == '':
            return None

        elif system == 'Lat/Lon':
            return '4326'

        else:
            if not zone or not datum:
                return None

            s = zone.split()
            zone_number = int(s[0])
            north = True if s[1] == 'North' else False

            if datum == "WGS 1984":
                if north:
                    epsg_code = f'326{zone_number:02d}'
                else:
                    epsg_code = f'327{zone_number:02d}'
            elif datum == 'NAD 1927':
                epsg_code = f'267{zone_number:02d}'
            elif datum == 'NAD 1983':
                epsg_code = f'269{zone_number:02d}'
            else:
                logger.info(f"CRS string not implemented.")
                return None

            logger.info(f"EPSG code from combo boxes: {epsg_code}.")
            return epsg_code

    def set_epsg(self, epsg_code):
        """
        Set the CRS using an EPSG code.
        :param epsg_code: str or int.
        :return: None
        """
        self.epsg_edit.blockSignals(True)
        logger.info(f"Setting CRS using EPSG code {epsg_code}.")
        try:
            crs = CRS.from_epsg(epsg_code)
        except:
            logger.info(f"Invalid EPSG code: {epsg_code}.")
            self.set_crs(None)
            # self.epsg_edit.setText('')
        else:
            self.set_crs(crs)

        self.epsg_edit.blockSignals(False)

    def set_epsg_label(self):
        """
        Convert the current project CRS combo box values into the EPSG code and set the status bar label.
        """
        if self.crs:
            self.epsg_label.setText(f"{self.crs.name} ({self.crs.type_name})")
        else:
            # self.epsg_edit.setText("")
            self.epsg_label.setText("")

    def set_crs(self, crs):
        """
        Fill the combo boxes (if the CRS is supported) and fill the EPSG line.
        :param crs: pyproj CRS object
        """
        self.crs = crs
        self.set_epsg_label()
        if self.crs is None:
            logger.info("Invalid CRS passed")
            return

        name = self.crs.name
        # self.populate_combo_boxes(self.crs.coordinate_operation, self.crs.datum)
        logger.info(F"Setting project CRS to {name} (EPSG {self.crs.to_epsg()}).")
        self.epsg_edit.setText(str(self.crs.to_epsg()))

        # If the combo box information is invalid, use EPSG lineEdit.
        if not self.combo_box_to_epsg():
            self.epsg_rbtn.setChecked(True)
            self.epsg_rbtn.setEnabled(True)
            self.gps_system_cbox.setEnabled(False)
            self.gps_datum_cbox.setEnabled(False)
            self.gps_zone_cbox.setEnabled(False)

    def get_epsg(self):
        """
        Return the EPSG code currently selected. Will convert the drop boxes to EPSG code.
        :return: str, EPSG code
        """
        if self.crs:
            return self.crs.to_epsg()
        else:
            return None

    def get_crs(self):
        return self.crs
