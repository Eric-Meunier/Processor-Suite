import os
import re

import natsort
from PyQt5 import (QtCore)
from PyQt5.QtWidgets import (QWidget, QMessageBox, QAbstractScrollArea, QTableWidgetItem, QHeaderView, QTableWidget,
                             QDialogButtonBox, QVBoxLayout)

__version__ = '0.0.0'


def convert_station(station):
    """
    Converts a single station name into a number, negative if the stations was S or W
    :return: Integer station number
    """
    if re.match(r"\d+(S|W)", station):
        station = (-int(re.sub(r"\D", "", station)))
    else:
        station = (int(re.sub(r"\D", "", station)))
    return station


class RIFile:
    """
    Class that represents a Step response RI file
    """
    def __init__(self):
        self.filepath = None
        self.header = {}
        self.data = []
        self.columns = ['Station', 'Component', 'Gain', 'Theoretical PP', 'Measured PP', 'S1', 'Last Step',
                       '(M-T)*100/Tot', '(S1-T)*100/Tot', '(LS-T)*100/Tot', '(S2-S1)*100/Tot', 'S3%', 'S4%',
                       'S5%', 'S6%', 'S7%', 'S8%', 'S9%', 'S10%']
        self.survey_type = None

    def open(self, filepath):
        self.filepath = filepath
        self.data = []

        with open(filepath, 'rt') as in_file:
            step_info = re.split('\$\$', in_file.read())[-1]
            raw_file = step_info.splitlines()
            raw_file = [line.split() for line in raw_file[1:]]  # Removing the header row
            # Creating the remaining off-time channel columns for the header
            [self.columns.append('Ch' + str(num + 11)) for num in range(len(raw_file[0]) - len(self.columns))]

            for row in raw_file:
                station = {}
                for i, column in enumerate(self.columns):
                    station[column] = row[i]
                self.data.append(station)
        return self

    def get_components(self):
        components = []
        for row in self.data:
            component = row['Component']
            if component not in components:
                components.append(row['Component'])
        return components

    def get_ri_profile(self, component):
        """
        Transforms the RI data as a profile to be plotted.
        :param component: The component that is being plotted (i.e. X, Y, Z)
        :return: The data in profile mode
        """
        profile_data = {}
        keys = self.columns
        component_data = list(filter(lambda d: d['Component'] == component, self.data))

        for key in keys:
            if key is not 'Gain' and key is not 'Component':
                if key is 'Station':
                    key = 'Stations'
                    profile_data[key] = [convert_station(station['Station']) for station in component_data]
                else:
                    profile_data[key] = [float(station[key]) for station in component_data]
        return profile_data

#
# class RIParser:
#     """
#     Class that represents a Step response RI file
#     """
#     def __init__(self):
#         self.filepath = None
#         self.header = {}
#         self.data = []
#         self.columns = ['Station', 'Component', 'Gain', 'Theoretical PP', 'Measured PP', 'S1', 'Last Step',
#                        '(M-T)*100/Tot', '(S1-T)*100/Tot', '(LS-T)*100/Tot', '(S2-S1)*100/Tot', 'S3%', 'S4%',
#                        'S5%', 'S6%', 'S7%', 'S8%', 'S9%', 'S10%']
#         self.survey_type = None
#
#     def open(self, filepath):
#         self.filepath = filepath
#         self.data = []
#
#         with open(filepath, 'rt') as in_file:
#             step_info = re.split('\$\$', in_file.read())[-1]
#             raw_file = step_info.splitlines()
#             raw_file = [line.split() for line in raw_file[1:]]  # Removing the header row
#             # Creating the remaining off-time channel columns for the header
#             [self.columns.append('Ch' + str(num + 11)) for num in range(len(raw_file[0]) - len(self.columns))]
#
#             for row in raw_file:
#                 station = {}
#                 for i, column in enumerate(self.columns):
#                     station[column] = row[i]
#                 self.data.append(station)
#         return self
#
#     def get_components(self):
#         components = []
#         for row in self.data:
#             component = row['Component']
#             if component not in components:
#                 components.append(row['Component'])
#         return components


class BatchRIImporter(QWidget):
    """
    Widget that imports multiple RI files. There must be equal number of RI files to PEM Files
    and the line/file name numbers much match up.
    """
    acceptImportSignal = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__()
        self.parent = parent
        self.pem_files = []
        self.ri_files = []

        self.setAcceptDrops(True)
        self.setGeometry(500, 300, 400, 500)
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.setWindowTitle("RI File Import")
        # self.ri_parser = RIFile()
        self.message = QMessageBox()

        self.table = QTableWidget()
        columns = ['PEM File', 'RI File']
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        self.table.setSizeAdjustPolicy(
            QAbstractScrollArea.AdjustIgnored)
        self.table.setAlternatingRowColors(True)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Stretch)

        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok |
                                           QDialogButtonBox.Cancel)
        self.button_box.setCenterButtons(True)
        self.button_box.rejected.connect(self.close)
        self.button_box.accepted.connect(self.acceptImportSignal.emit)
        self.button_box.accepted.connect(self.close)

        self.layout.addWidget(self.table)
        self.layout.addWidget(self.button_box)

    def dragEnterEvent(self, e):
        urls = [url.toLocalFile() for url in e.mimeData().urls()]

        if all([url.lower().endswith('ri1') or url.lower().endswith('ri2') or url.lower().endswith(
                'ri3') for url in urls]):
            e.accept()
        else:
            e.ignore()

    def dropEvent(self, e):
        urls = [url.toLocalFile() for url in e.mimeData().urls()]
        self.open_ri_files(urls)

    def closeEvent(self, e):
        self.clear_table()
        e.accept()

    def keyPressEvent(self, e):
        if e.key() == QtCore.Qt.Key_Escape:
            self.close()
        elif e.key() == QtCore.Qt.Key_Return:
            self.acceptImportSignal.emit()
            self.close()

    def clear_table(self):
        while self.table.rowCount() > 0:
            self.table.removeRow(0)

    def open_pem_files(self, pem_files):
        self.pem_files = pem_files

        names = [pem_file.filepath.name for pem_file in self.pem_files]

        for i, name in enumerate(names):
            row_pos = self.table.rowCount()
            self.table.insertRow(row_pos)
            item = QTableWidgetItem(name)
            item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.table.setItem(row_pos, 0, item)

    def open_ri_files(self, ri_filepaths):
        ri_filepaths.sort(key=lambda path: natsort.humansorted(os.path.basename(path)), reverse=False)
        self.ri_files = []

        if len(ri_filepaths) == len(self.pem_files):

            # Only for boreholes, match up the RI1 file for Z, and RI2 file for XY
            if all([pem_file.is_borehole() for pem_file in self.pem_files]):
                ri_files = [RIFile().open(filepath) for filepath in ri_filepaths]

                for pem_file in self.pem_files:
                    pem_components = sorted(pem_file.get_components())
                    pem_name = re.sub('[^0-9]', '', pem_file.line_name)[-4:]

                    for ri_file in ri_files:
                        ri_components = sorted(ri_file.get_components())
                        ri_name = re.sub('[^0-9]', '', os.path.splitext(os.path.basename(ri_file.filepath))[0])[-4:]

                        if pem_components == ri_components and pem_name == ri_name:
                            self.ri_files.append(ri_file.filepath)
                            ri_files.pop(ri_files.index(ri_file))
                            break

            elif any([pem_file.is_borehole() for pem_file in self.pem_files]):
                self.message.information(None, "Error", "PEM files must either be all borehole or all surface surveys")

            else:
                [self.ri_files.append(ri_filepath) for ri_filepath in ri_filepaths]

            for i, filepath in enumerate(self.ri_files):  # Add the RI file names to the table
                name = os.path.basename(filepath)
                item = QTableWidgetItem(name)
                item.setTextAlignment(QtCore.Qt.AlignCenter)
                self.table.setItem(i, 1, item)

        else:
            self.message.information(None, "Error", "Length of RI files must be equal to length of PEM files")


if __name__ == '__main__':
    pass
    # file = r'C:\_Data\2019\Nantou BF\Surface\Semtoun 100-114\STP\50N_100.RI3'
    # main()
