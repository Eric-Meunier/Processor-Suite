from PyQt5.QtWidgets import *
from PyQt5 import uic
from pem.pem_editor import PEMFileEditor
from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt4agg import NavigationToolbar2QT as NavigationToolbar
from PyQt5.QtCore import Qt, pyqtSignal, QEvent
import os

# Load Qt ui file into a class
qtCreatorFile = os.path.join(os.path.dirname(os.path.realpath(__file__)), "../qt_ui/pem_file_form.ui")
Ui_PEMFileWidget, QtBaseClass = uic.loadUiType(qtCreatorFile)


class PEMFileWidget(QWidget, Ui_PEMFileWidget):

    def __init__(self, parent=None, editor=None):
        QWidget.__init__(self, parent=parent)
        Ui_PEMFileWidget.__init__(self)
        self.setupUi(self)
        if not editor:
            self.editor = PEMFileEditor()
        else:
            self.editor = editor

        # For debug
        # p = self.palette()
        # p.setColor(self.backgroundRole(), Qt.red)
        # self.setPalette(p)

        # Container Widget to hold scrollable content
        self.scroll_content_widget = QWidget()

        # Layout of Container Widget
        self.scroll_content_layout = QVBoxLayout(self.scroll_content_widget)
        self.scroll_content_widget.setLayout(self.scroll_content_layout)

        # Create scroll area to allow for scrolling of scroll_content_widget
        self.scroll = PlotScrollArea()
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(self.scroll_content_widget)

        # Add the scroll area to the forms highest level layout
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.verticalLayout.addWidget(self.scroll)

        # Connect signals to slots
        self.show_nav_bars.clicked.connect(self.on_show_nav_bars)

        self.nav_bars_visible = False

        # Hide widgets by default since no file has been loaded
        self.show_nav_bars_button.hide()
        self.scroll.hide()

        #self.keyPressed.connect(self.on_key)
        self.scroll.arrowKeyPressed.connect(self.on_arrow_key)
        self.scroll.verticalScrollBar().valueChanged.connect(self.on_scroll_change)

        self.PLOT_FIXED_HEIGHT = 350

    def scroll_page(self, direction):

        def layout_widgets(layout):
            return (layout.itemAt(i).widget() for i in range(layout.count()))

        page_distance = self.scroll.verticalScrollBar().value()
        page = 0

        heights = [widget.y() for widget in layout_widgets(self.scroll_content_layout)]

        for height in heights:
            if height > page_distance:
                break
            page += 1

        if direction < 0:
            page -= 1

        new_page = page + direction

        if new_page < 0:
            new_page = 0

        elif new_page >= len(heights):
            new_page = len(heights) - 1

        page_distance = heights[new_page]

        self.scroll.verticalScrollBar().setValue(page_distance)

    def open_file(self, file_name):
        # Hide widgets and display loading text
        self.show_nav_bars_button.hide()
        self.scroll.hide()
        self.label.show()
        self.label.setText('Loading ' + os.path.basename(file_name) + '...')
        QApplication.processEvents()
        # TODO Find alternative to calling processEvents()?

        self.editor.open_file(file_name)

        figures = self.editor.generate_placeholder_plots()

        # Create a FigureCanvas for each figure to display plots in Qt
        for fig in figures:
            canvas = FigureCanvas(fig)

            canvas_widget = QWidget()
            canvas_widget_layout = QVBoxLayout(canvas_widget)
            canvas_widget.setLayout(canvas_widget_layout)
            canvas_widget.layout().addWidget(canvas)

            layout = self.scroll_content_layout
            layout.insertWidget(layout.count(), canvas_widget)

            canvas.setFixedHeight(self.PLOT_FIXED_HEIGHT)
            canvas.draw()

        # Hide loading screen and show results
        self.show_nav_bars_button.show()
        self.scroll.show()
        self.label.hide()

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

    def on_arrow_key(self, event):
        if event.key() == Qt.Key_Left:
            self.scroll_page(-1)
        if event.key() == Qt.Key_Right:
            self.scroll_page(1)

    def on_scroll_change(self, x):
        pass

    # def keyPressEvent(self, event):
    #     super(PEMFileWidget, self).keyPressEvent(event)
    #     self.keyPressed.emit(event)


class PlotScrollArea(QScrollArea):
    arrowKeyPressed = pyqtSignal(QEvent)

    def __init__(self, *args):
        QScrollBar.__init__(self, *args)

    def event(self, event):
        if (event.type() == QEvent.KeyPress) and (event.key() == Qt.Key_Left or
                                                  event.key() == Qt.Key_Right):
            self.arrowKeyPressed.emit(event)
            return True

        return QScrollArea.event(self, event)
