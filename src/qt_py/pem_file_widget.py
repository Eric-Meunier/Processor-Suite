from PyQt5.QtWidgets import *
from PyQt5 import uic
from pem.pem_editor import PEMFileEditor
from qt_py.plot_viewer_widget import PlotViewerWidget
from qt_py.plot_widget import PlotWidget
from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt4agg import NavigationToolbar2QT as NavigationToolbar
from PyQt5.QtCore import Qt, pyqtSignal, QEvent
from PyQt5 import QtGui
from PyQt5.QtPrintSupport import QPrinter
import os
from matplotlib.backends.backend_pdf import PdfPages


class PEMFileWidget(QWidget):

    def __init__(self, parent=None, editor=None):
        QWidget.__init__(self, parent=parent)

        if not editor:
            self.editor = PEMFileEditor()
        else:
            self.editor = editor

        self.layout = QVBoxLayout(self)
        self.label = QLabel()
        self.label.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.label)

    def open_file(self, file_name):
        # Display loading text
        self.label.show()
        self.label.setText('Loading ' + os.path.basename(file_name) + '...')
        QApplication.processEvents()
        # TODO Find alternative to calling processEvents()?

        self.editor.open_file(file_name)

        lin_figs, log_figs = self.editor.generate_plots()

        self.tab_widget = QTabWidget(self)
        self.layout.addWidget(self.tab_widget)

        self.lin_view_widget = PlotViewerWidget(editor=self.editor, figures=lin_figs, plot_heights=900)
        self.log_view_widget = PlotViewerWidget(editor=self.editor, figures=log_figs, plot_heights=900)

        self.tab_widget.tabBar().setExpanding(True)
        # new_file_widget.setTabPosition(QTabWidget.West)
        self.tab_widget.addTab(self.lin_view_widget, 'Linear Plots')
        self.tab_widget.addTab(self.log_view_widget, 'Log Plots')

        # Hide loading screen and show results
        self.label.hide()

        # print(str(self.width()) + ", " + str(self.height()))

    def print(self, dir_name):

        # Code for making pdf by printing widgets
        # Conclusion: This rasterizes the plots, making them blurry.

        # printer = QPrinter(QPrinter.HighResolution)
        # printer.setOutputFileName("print.ps");
        #
        # painter = QtGui.QPainter()
        # painter.begin(printer)
        #
        # # TODO Make canvas return function
        # lin_figs = [x.canvas for x in self.lin_view_widget.plot_widgets()]
        #
        # page_cnt = len(lin_figs)
        #
        # # self.lin_view_widget.update()
        #
        # self.lin_view_widget.scroll_content_widget.show()
        # self.lin_view_widget.scroll_content_widget.repaint()
        # self.lin_view_widget.scroll_content_widget.update()
        #
        #
        # for page in range(page_cnt):
        #
        #     # myWidget = QLabel()
        #     # myWidget.setText('test')
        #     myWidget = lin_figs[page_cnt - 1 - page]
        #
        #     xscale = 0.9 * printer.pageRect().width() / myWidget.width()
        #     yscale = 0.9 * printer.pageRect().height() / myWidget.height()
        #     scale = min(xscale, yscale)
        #     # painter.translate(printer.paperRect().x() + printer.pageRect().width() / 2,
        #     #                   printer.paperRect().y() + printer.pageRect().height() / 2)
        #     painter.scale(scale, scale)
        #     # painter.translate(0, -printer.pageRect().height()*page);
        #
        #     myWidget.show()
        #     myWidget.repaint(0,0,1,1)
        #
        #     myWidget.render(painter)
        #
        #     painter.resetTransform()
        #     if page != page_cnt - 1:
        #         print(printer.newPage())
        #
        # painter.end()
        #
        # pass

        # ------------------------------------------------------------------

        # Code for turning .svg plots into pdfs, will be useful if we switch to pyqtgraph

        # from svglib.svglib import svg2rlg
        # from reportlab.graphics import renderPDF
        # from reportlab.pdfgen import canvas
        # #
        # lin_figs = [x.figure for x in self.lin_view_widget.plot_widgets()]
        #
        # canvas = canvas.Canvas('result.pdf')
        # page_size = canvas._pagesize
        #
        # #
        # lin_figs[0].savefig('temp.svg', format='svg')
        # drawing = svg2rlg('temp.svg')
        #
        # xscale = page_size[0] / drawing.width
        # yscale = page_size[1] / drawing.height
        # scale = min(xscale, yscale)
        #
        # print(xscale)
        # print(yscale)
        #
        # drawing.width = drawing.width*scale
        # drawing.height = drawing.height*scale
        # drawing.scale(scale, scale)
        #
        # # renderPDF.drawToFile(drawing, "file.pdf")
        # renderPDF.draw(drawing, canvas, 0, page_size[1] - drawing.height)
        # canvas.save()

        # ------------------------------------------------------------------

        if not os.path.exists(dir_name):
            os.makedirs(dir_name)

        lin_figs = [x.figure for x in self.lin_view_widget.plot_widgets()]
        log_figs = [x.figure for x in self.log_view_widget.plot_widgets()]

        with PdfPages(os.path.join(dir_name, "lin.pdf")) as pdf:
            for fig in lin_figs:
                pdf.savefig(fig)

        with PdfPages(os.path.join(dir_name, "log.pdf")) as pdf:
            for fig in log_figs:
                pdf.savefig(fig)
