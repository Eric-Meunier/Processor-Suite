import sys
import chardet
from pathlib import Path

import numpy as np
import pandas as pd
import pyqtgraph as pg
from PySide2 import QtWidgets
from PySide2.QtCore import Qt, QSizeF, QPointF
from PySide2.QtGui import QPixmap, QIcon, QPalette, QColor
from PySide2.QtWidgets import QTableWidgetItem, QItemDelegate
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from src.logger import logger

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
        if style == "mpl":
            return rgb2hex(*pink_color[:-1])
        else:
            return pink_color
    elif color == "teal":
        if style == "mpl":
            return rgb2hex(*teal_color[:-1])
        else:
            return teal_color
    elif color == "yellow":
        if style == "mpl":
            return rgb2hex(*yellow_color[:-1])
        else:
            return yellow_color
    elif color == "blue":
        if style == "mpl":
            return rgb2hex(*blue_color[:-1])
        else:
            return blue_color
    elif color == "single_blue":
        if style == "mpl":
            return rgb2hex(*single_blue_color[:-1])
        else:
            return single_blue_color
    elif color == "red":
        if style == "mpl":
            return rgb2hex(*red_color[:-1])
        else:
            return red_color
    elif color == "purple":
        if style == "mpl":
            return rgb2hex(*purple_color[:-1])
        else:
            return purple_color
    elif color == "aquamarine":
        if style == "mpl":
            return rgb2hex(*aquamarine_color[:-1])
        else:
            return aquamarine_color
    elif color == "green":
        if style == "mpl":
            return rgb2hex(*green_color[:-1])
        else:
            return green_color
    elif color == "foreground":
        if style == "mpl":
            return rgb2hex(*foreground_color[:-1])
        else:
            return foreground_color
    elif color == "background":
        if style == "mpl":
            return rgb2hex(*background_color[:-1])
        else:
            return background_color
    elif color == "gray":
        if style == "mpl":
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


def table_to_df(table, dtypes=None):
    """
    Return a data frame from the information in the table.
    :param table: QTableWidget
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
    if dtypes is not None:
        df = df.astype(dtypes)
    else:
        df = df.apply(pd.to_numeric, errors='ignore')
    return df


# TODO Create function which will re-limit axes to match a given (or the widget's) size.
def set_ax_size(size, ax, figure):
    """
    Re-size the extents to make the axes 11" by 8.5"
    :param size: tuple, desired size of the plot in inches
    :param ax: Matplotlib Axes object
    :param figure: Matplotlib Figure object
    """
    bbox = ax.get_window_extent().transformed(figure.dpi_scale_trans.inverted())
    xmin, xmax = ax.get_xlim()
    ymin, ymax = ax.get_ylim()
    # xmin, xmax, ymin, ymax = ax.get_extent()
    map_width, map_height = xmax - xmin, ymax - ymin

    current_ratio = map_width / map_height

    if current_ratio < (bbox.width / bbox.height):
        new_height = map_height
        # Set the new width to be the correct ratio larger than height
        new_width = new_height * (bbox.width / bbox.height)
    else:
        new_width = map_width
        new_height = new_width * (bbox.height / bbox.width)

    x_offset = 0
    y_offset = 0.06 * new_height
    new_xmin = (xmin - x_offset) - ((new_width - map_width) / 2)
    new_xmax = (xmax - x_offset) + ((new_width - map_width) / 2)
    new_ymin = (ymin + y_offset) - ((new_height - map_height) / 2)
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
        self.setWindowFlags(Qt.CustomizeWindowHint | Qt.WindowStaysOnTopHint)
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
        except :
            QItemDelegate.paint(self, painter, option, index)


class MapToolbar(NavigationToolbar):
    """
    Custom Matplotlib toolbar for maps. Only has the Home, Back, Forward, Pan, and Zoom buttons.
    """
    # only display the buttons we need
    toolitems = [t for t in NavigationToolbar.toolitems if
                 t[0] in ('Home', 'Back', 'Forward', 'Pan', 'Zoom')]
