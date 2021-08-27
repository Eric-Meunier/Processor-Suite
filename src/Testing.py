# from PySide2 import QtCore, QtGui, QtWidgets, QtWebEngineWidgets
# #
# # app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
# #
# # viewer = QtWebEngineWidgets.QWebEngineView()
# # viewer.load(QtCore.QUrl("http://gmail.com"))
# # viewer.show()
# #
# # app.exec_()

from PySide2 import QtGui
from PySide2.QtWidgets import *
from PySide2.QtCharts import QtCharts
from PySide2.QtGui import QPainter
from random import randint
app = QApplication([])
window = QWidget()
layout = QVBoxLayout()
# Initialize chart
chart = QtCharts.QChart()
lineSeries = QtCharts.QLineSeries()
# Make some random data points
dataSeries = [(i+1, randint(0, 99999)) for i in range(200)]
# load data into chart:
for point in dataSeries:
    lineSeries.append(point[0],point[1])
# Add Some Chart Options
chart.addSeries(lineSeries)
chart.setTitle("Random Numbers from 0-9000")
chart.createDefaultAxes()
# Create a container (similar to a widget)
chartView = QtCharts.QChartView(chart)
chartView.setRenderHint(QPainter.Antialiasing)
# Some Chart Styling
lineSeries.setColor(QtGui.QColor("darkgray"))
# chartView.chart().setBackgroundBrush(QtGui.QColor("ivory"))
layout.addWidget(chartView)
window.setLayout(layout)
window.show()
window.resize(600, 400)
app.exec_()