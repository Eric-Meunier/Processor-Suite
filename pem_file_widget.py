from PyQt5.QtWidgets import *
from PyQt5 import uic
from pem_editor import PEMFileEditor
from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt4agg import NavigationToolbar2QT as NavigationToolbar
from PyQt5.QtCore import Qt

qtCreatorFile = "pem_file_form.ui"  # Enter file here.
Ui_PEMFileWidget, QtBaseClass = uic.loadUiType(qtCreatorFile)


class PEMFileWidget(QWidget, Ui_PEMFileWidget):

    def __init__(self, parent=None):
        QWidget.__init__(self, parent=parent)
        Ui_PEMFileWidget.__init__(self)
        self.setupUi(self)
        self.editor = PEMFileEditor()

        # For debug
        # p = self.palette()
        # p.setColor(self.backgroundRole(), Qt.red)
        # self.setPalette(p)

        # Container Widget
        self.scroll_content_widget = QWidget()

        # Layout of Container Widget
        self.scroll_content_layout = QVBoxLayout(self.scroll_content_widget)
        self.scroll_content_widget.setLayout(self.scroll_content_layout)

        self.scroll = QScrollArea()
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(self.scroll_content_widget)

        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.verticalLayout.addWidget(self.scroll)

        # Connect signals to slots
        self.show_nav_bars.clicked.connect(self.on_show_nav_bars)

        self.nav_bars_visible = False

    def open_file(self, file_name):
        self.editor.open_file(file_name)
        self.label.setText(file_name)
        self.label.setParent(None)

        figures = self.editor.generate_placeholder_plots()

        for fig in figures:
            canvas = FigureCanvas(fig)

            canvas_widget = QWidget()
            canvas_widget_layout = QVBoxLayout(canvas_widget)
            canvas_widget.setLayout(canvas_widget_layout)
            canvas_widget.layout().addWidget(canvas)

            layout = self.scroll_content_layout
            # layout.insertWidget(layout.count() - 1, canvas)
            layout.addWidget(canvas_widget)

            canvas.setFixedHeight(350)
            canvas.draw()

        # print(str(self.width()) + ", " + str(self.height()))

    def on_show_nav_bars(self):
        def layout_widgets(layout):
            return (layout.itemAt(i).widget() for i in range(layout.count()))

        if not self.nav_bars_visible:
            for widget in layout_widgets(self.scroll_content_layout):
                # TODO store list of widgets and their canvases
                toolbar = NavigationToolbar(widget.layout().itemAt(0).widget(), widget)
                widget.layout().addWidget(toolbar)
            self.nav_bars_visible = True

        else:
            for widget in layout_widgets(self.scroll_content_layout):
                # TODO store list of widgets and their canvases
                widget.layout().itemAt(1).widget().setParent(None)
            self.nav_bars_visible = False

        print("Toggled navigation bars " + ('on' if self.nav_bars_visible else 'off'))
