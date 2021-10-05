# importing the pyqtgraph.examples module
import pyqtgraph.examples
import pyqtgraph as pg
from pyqtgraph.Qt import QtGui, QtCore
import numpy as np


# run this examples
# pyqtgraph.examples.run()

app = QtGui.QApplication([])

widget = pg.PlotWidget()
roi = pg.PolyLineROI(zip(np.arange(0, 10, 1), np.arange(0, 10, 1)))
roi.sigRegionChanged.connect(lambda: print("Region changed"))
widget.addItem(roi)
widget.show()

app.exec_()