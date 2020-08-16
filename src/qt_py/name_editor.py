import copy
import os
import sys

from PyQt5 import (QtCore, uic)
from PyQt5.QtWidgets import (QWidget, QAbstractScrollArea, QTableWidgetItem, QHeaderView)

# Modify the paths for when the script is being run in a frozen state (i.e. as an EXE)
if getattr(sys, 'frozen', False):
    application_path = sys._MEIPASS
    lineNameEditorCreatorFile = 'qt_ui\\line_name_editor.ui'
    icons_path = 'icons'
else:
    application_path = os.path.dirname(os.path.abspath(__file__))
    lineNameEditorCreatorFile = os.path.join(os.path.dirname(application_path), 'qt_ui\\line_name_editor.ui')
    icons_path = os.path.join(os.path.dirname(application_path), "qt_ui\\icons")

# Load Qt ui file into a class
Ui_LineNameEditorWidget, QtBaseClass = uic.loadUiType(lineNameEditorCreatorFile)


class BatchNameEditor(QWidget, Ui_LineNameEditorWidget):
    """
    Class to bulk rename PEM File line/hole names or file names.
    """
    acceptChangesSignal = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        """
        :param pem_files: list, PEMFile objects
        :param type: str, the type of name to change, either 'File' or 'Line'
        :param parent: Qt Widget object
        """
        super().__init__()
        self.parent = parent
        self.setupUi(self)
        self.pem_files = []
        self.type = None

        self.table_columns = ['Old Name', 'New Name']
        self.table.setColumnCount(len(self.table_columns))
        self.table.setHorizontalHeaderLabels(self.table_columns)
        self.table.setSizeAdjustPolicy(
            QAbstractScrollArea.AdjustToContents)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Stretch)

        self.addEdit.setText('[n]')
        self.addEdit.textEdited.connect(self.update_table)
        self.removeEdit.textEdited.connect(self.update_table)
        self.buttonBox.rejected.connect(self.close)
        self.buttonBox.accepted.connect(self.acceptChangesSignal.emit)

    def open(self, pem_files, type=None):
        """
        Open the pem_files
        :param pem_files: list, PEMFile objects
        :param type: str, either 'Line' to change the line names or 'File' to change file names
        :return: None
        """
        self.pem_files = pem_files
        self.type = type

        if self.type == 'Line':
            self.setWindowTitle('Rename lines/holes names')
        else:
            self.setWindowTitle('Rename files names')

        for pem_file in self.pem_files:
            self.add_to_table(pem_file)

        self.show()

    def add_to_table(self, pem_file):
        """
        Add the PEM files to the table.
        :param pem_file: PEMFile object
        """
        row_pos = self.table.rowCount()
        self.table.insertRow(row_pos)

        if self.type == 'Line':
            item = QTableWidgetItem(pem_file.line_name)
            item2 = QTableWidgetItem(pem_file.line_name)
        elif self.type == 'File':
            item = QTableWidgetItem(pem_file.filename)
            item2 = QTableWidgetItem(pem_file.filename)
        else:
            raise ValueError('Invalid type in BatchNameEditor')

        item.setTextAlignment(QtCore.Qt.AlignCenter)
        item2.setTextAlignment(QtCore.Qt.AlignCenter)

        self.table.setItem(row_pos, 0, item)
        self.table.setItem(row_pos, 1, item2)

        self.table.resizeColumnsToContents()

    def keyPressEvent(self, e):
        if e.key() == QtCore.Qt.Key_Escape:
            self.close()
        elif e.key() == QtCore.Qt.Key_Return:
            self.acceptChangesSignal.emit()

    def update_table(self):
        """
        Every time a change is made in the line edits, this function is called and updates the entries in the table
        """
        for row in range(self.table.rowCount()):
            # Split the text based on '[n]'. Anything before it becomes the prefix,
            # and everything after is added as a suffix
            if self.type == 'Line':
                # Immediately replace what's in the removeEdit object with nothing
                input = self.table.item(row, 0).text().replace(self.removeEdit.text(), '')
                suffix = self.addEdit.text().rsplit('[n]')[-1]
                prefix = self.addEdit.text().rsplit('[n]')[0]
                output = prefix + input + suffix
            else:
                input = self.table.item(row, 0).text().split('.')[0].replace(self.removeEdit.text(), '')
                ext = '.' + self.table.item(row, 0).text().split('.')[-1]
                suffix = self.addEdit.text().rsplit('[n]')[-1]
                prefix = self.addEdit.text().rsplit('[n]')[0]
                output = prefix + input + suffix + ext

            item = QTableWidgetItem(output)
            item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.table.setItem(row, 1, item)

    # def close(self):
    #     while self.table.rowCount() > 0:
    #         self.table.removeRow(0)
    #     self.addEdit.setText('[n]')
    #     self.removeEdit.setText('')
    #     self.hide()

    def accept_changes(self):
        """
        Makes the proposed changes and updates the table
        """

        def refresh_table():
            while self.table.rowCount() > 0:
                self.table.removeRow(0)

            for pem_file in self.pem_files:
                self.add_to_table(pem_file)

            header = self.table.horizontalHeader()
            header.setSectionResizeMode(0, QHeaderView.Stretch)
            header.setSectionResizeMode(1, QHeaderView.Stretch)
            self.addEdit.setText('[n]')
            self.removeEdit.setText('')

        if self.pem_files:
            for i, pem_file in enumerate(self.pem_files):
                new_name = self.table.item(i, 1).text()
                if self.type == 'Line':
                    pem_file.line_name = new_name
                else:
                    old_path = copy.deepcopy(os.path.abspath(pem_file.filepath))
                    new_path = os.path.join(os.path.dirname(pem_file.filepath), new_name)
                    if pem_file.old_filepath is None:
                        pem_file.old_filepath = old_path
                    pem_file.filepath = new_path
                    pem_file.filename = os.path.basename(new_path)

            refresh_table()

