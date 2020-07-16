import copy
import os
import sys

from PyQt5 import (QtCore,  QtGui)
from PyQt5.QtWidgets import (QWidget, QFileDialog, QApplication, QTableWidgetItem, QHeaderView, QTableWidget,
                             QPushButton, QGridLayout)


class StationSplitter(QWidget):
    """
    Class that will extract selected stations from a PEM File and save them as a new PEM File.
    """
    def __init__(self, parent=None):
        super().__init__()
        self.pem_file = None
        self.parent = parent

        self.setWindowTitle('Station Splitter')
        self.resize(300, 500)
        if getattr(sys, 'frozen', False):
            icon_path = os.path.join(os.path.dirname(sys._MEIPASS), "qt_ui\\icons\\station_splitter2.png")
        else:
            icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                     "qt_ui\\icons\\station_splitter2.png")
        self.setWindowIcon(QtGui.QIcon(icon_path))

        self.extract_btn = QPushButton('Extract')
        self.cancel_btn = QPushButton('Cancel')
        self.extract_btn.clicked.connect(self.extract_selection)
        self.cancel_btn.clicked.connect(self.close)

        self.table = QTableWidget()
        self.table_columns = ['Station']
        self.table.setColumnCount(len(self.table_columns))
        self.table.setHorizontalHeaderLabels(self.table_columns)
        self.table.setAlternatingRowColors(True)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)

        self.layout = QGridLayout()
        self.setLayout(self.layout)
        self.layout.addWidget(self.table, 0, 0, 1, 2)
        self.layout.addWidget(self.extract_btn, 1, 0)
        self.layout.addWidget(self.cancel_btn, 1, 1)

    def open(self, pem_file):
        self.pem_file = pem_file
        self.fill_table()
        self.show()

    def closeEvent(self, e):
        # self.table.clear()
        e.accept()

    def keyPressEvent(self, e):
        if e.key() == QtCore.Qt.Key_Escape:
            self.close()
        elif e.key() == QtCore.Qt.Key_Return:
            self.close()

    def fill_table(self):
        """
        Add each station in the PEM file as a row in the table.
        :return: None
        """
        stations = self.pem_file.get_unique_stations()

        for i, station in enumerate(stations):
            row = i
            self.table.insertRow(row)
            item = QTableWidgetItem(station)
            item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.table.setItem(row, 0, item)

    def extract_selection(self):
        selected_rows = [model.row() for model in self.table.selectionModel().selectedRows()]
        selected_stations = []
        for row in selected_rows:
            selected_stations.append(self.table.item(row, 0).text())

        if selected_stations:
            default_path = os.path.split(self.pem_file.filepath)[0]
            save_file = os.path.splitext(QFileDialog.getSaveFileName(self, '', default_path)[0])[0] + '.PEM'
            if save_file:
                new_pem_file = copy.deepcopy(self.pem_file)
                filt = self.pem_file.data.Station.isin(selected_stations)
                new_data = self.pem_file.data.loc[filt]
                new_pem_file.data = new_data
                new_pem_file.filepath = save_file
                new_pem_file.number_of_readings = len(new_data.index)
                file = new_pem_file.to_string()
                print(file, file=open(new_pem_file.filepath, 'w+'))
                self.parent.open_pem_files(new_pem_file)
                self.close()
            else:
                pass


if __name__ == '__main__':
    from src.pem.pem_getter import PEMGetter

    app = QApplication(sys.argv)
    pg = PEMGetter()
    files = pg.get_pems(number=1)
    ss = StationSplitter()
    ss.open(files[0])
    ss.show()

    sys.exit(app.exec())