import sys
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from pem.pem_editor import PEMFileEditor
from qt_py.pem_file_widget import PEMFileWidget


class FileBrowser(QTabWidget):
    def __init__(self, parent=None):
        super(FileBrowser, self).__init__(parent)
        # self.setWindowTitle("tab demo")

        # TODO Make model to deal with these together
        self.editors = []
        self.widgets = []
        self.active_editor = None
        self.original_indices = []

        # TODO Make custom TabBar Widget to make detachable
        self.setTabsClosable(True)
        self.setMovable(True)

        self.tabCloseRequested.connect(self.on_tab_close)
        self.tabBar().tabMoved.connect(self.on_tab_move)

    def open_file(self, file_name):
        # TODO Logic for different file types

        new_editor = PEMFileEditor()
        new_file_widget = PEMFileWidget(editor=new_editor)

        self.editors.append(new_editor)
        self.widgets.append(new_file_widget)
        self.original_indices.append(len(self.widgets))

        self.addTab(new_file_widget, file_name)
        self.setCurrentWidget(new_file_widget)

        new_file_widget.open_file(file_name)
        self.active_editor = new_editor

    def on_tab_close(self, index):
        print(index)
        self.removeTab(index)
        self.editors.pop(index)
        self.widgets.pop(index)
        self.original_indices.pop(index)

    def on_tab_move(self, from_index, to_index):
        self.editors.insert(to_index, self.editors.pop(from_index))
        self.widgets.insert(to_index, self.widgets.pop(from_index))
        self.original_indices.insert(to_index, self.original_indices.pop(from_index))

        print('moved ' + str(from_index) + ' ' + str(to_index) + ' to new order ' + str(self.original_indices))


def main():
    app = QApplication(sys.argv)
    ex = FileBrowser()
    ex.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()