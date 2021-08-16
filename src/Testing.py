from PySide2 import QtCore, QtGui, QtWidgets, QtWebEngineWidgets

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

viewer = QtWebEngineWidgets.QWebEngineView()
viewer.load(QtCore.QUrl("http://gmail.com"))
viewer.show()

app.exec_()