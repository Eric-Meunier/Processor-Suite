# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'gpx_creator.ui'
##
## Created by: Qt User Interface Compiler version 5.15.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide2.QtCore import *
from PySide2.QtGui import *
from PySide2.QtWidgets import *


class Ui_GPXCreator(object):
    def setupUi(self, GPXCreator):
        if not GPXCreator.objectName():
            GPXCreator.setObjectName(u"GPXCreator")
        GPXCreator.resize(822, 595)
        self.openAction = QAction(GPXCreator)
        self.openAction.setObjectName(u"openAction")
        self.exportGPX = QAction(GPXCreator)
        self.exportGPX.setObjectName(u"exportGPX")
        self.create_csv_template_action = QAction(GPXCreator)
        self.create_csv_template_action.setObjectName(u"create_csv_template_action")
        self.centralwidget = QWidget(GPXCreator)
        self.centralwidget.setObjectName(u"centralwidget")
        self.gridLayout = QGridLayout(self.centralwidget)
        self.gridLayout.setSpacing(0)
        self.gridLayout.setObjectName(u"gridLayout")
        self.gridLayout.setContentsMargins(0, 0, 0, 0)
        self.frame = QFrame(self.centralwidget)
        self.frame.setObjectName(u"frame")
        self.frame.setFrameShape(QFrame.Box)
        self.frame.setFrameShadow(QFrame.Sunken)
        self.verticalLayout = QVBoxLayout(self.frame)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(6, 6, 6, 6)
        self.label_4 = QLabel(self.frame)
        self.label_4.setObjectName(u"label_4")

        self.verticalLayout.addWidget(self.label_4)

        self.name_edit = QLineEdit(self.frame)
        self.name_edit.setObjectName(u"name_edit")
        sizePolicy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.name_edit.sizePolicy().hasHeightForWidth())
        self.name_edit.setSizePolicy(sizePolicy)

        self.verticalLayout.addWidget(self.name_edit)

        self.verticalSpacer_2 = QSpacerItem(20, 10, QSizePolicy.Minimum, QSizePolicy.Fixed)

        self.verticalLayout.addItem(self.verticalSpacer_2)

        self.groupBox = QGroupBox(self.frame)
        self.groupBox.setObjectName(u"groupBox")
        self.gridLayout_2 = QGridLayout(self.groupBox)
        self.gridLayout_2.setObjectName(u"gridLayout_2")
        self.gps_system_cbox = QComboBox(self.groupBox)
        self.gps_system_cbox.setObjectName(u"gps_system_cbox")
        self.gps_system_cbox.setMinimumSize(QSize(80, 0))

        self.gridLayout_2.addWidget(self.gps_system_cbox, 1, 2, 1, 1)

        self.gps_zone_cbox = QComboBox(self.groupBox)
        self.gps_zone_cbox.setObjectName(u"gps_zone_cbox")
        self.gps_zone_cbox.setEnabled(False)
        self.gps_zone_cbox.setMinimumSize(QSize(80, 0))

        self.gridLayout_2.addWidget(self.gps_zone_cbox, 3, 2, 1, 1)

        self.gps_datum_cbox = QComboBox(self.groupBox)
        self.gps_datum_cbox.setObjectName(u"gps_datum_cbox")
        self.gps_datum_cbox.setEnabled(False)
        self.gps_datum_cbox.setMinimumSize(QSize(80, 0))

        self.gridLayout_2.addWidget(self.gps_datum_cbox, 4, 2, 1, 1)

        self.label = QLabel(self.groupBox)
        self.label.setObjectName(u"label")
        sizePolicy1 = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.label.sizePolicy().hasHeightForWidth())
        self.label.setSizePolicy(sizePolicy1)

        self.gridLayout_2.addWidget(self.label, 1, 1, 1, 1)

        self.zone_number_label = QLabel(self.groupBox)
        self.zone_number_label.setObjectName(u"zone_number_label")
        self.zone_number_label.setEnabled(True)

        self.gridLayout_2.addWidget(self.zone_number_label, 3, 1, 1, 1)

        self.label_2 = QLabel(self.groupBox)
        self.label_2.setObjectName(u"label_2")

        self.gridLayout_2.addWidget(self.label_2, 4, 1, 1, 1)

        self.epsg_edit = QLineEdit(self.groupBox)
        self.epsg_edit.setObjectName(u"epsg_edit")
        sizePolicy2 = QSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        sizePolicy2.setHorizontalStretch(0)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(self.epsg_edit.sizePolicy().hasHeightForWidth())
        self.epsg_edit.setSizePolicy(sizePolicy2)
        self.epsg_edit.setMaximumSize(QSize(100, 16777215))

        self.gridLayout_2.addWidget(self.epsg_edit, 6, 2, 1, 1)

        self.epsg_rbtn = QRadioButton(self.groupBox)
        self.epsg_rbtn.setObjectName(u"epsg_rbtn")

        self.gridLayout_2.addWidget(self.epsg_rbtn, 6, 0, 1, 1)

        self.label_3 = QLabel(self.groupBox)
        self.label_3.setObjectName(u"label_3")

        self.gridLayout_2.addWidget(self.label_3, 6, 1, 1, 1)

        self.crs_rbtn = QRadioButton(self.groupBox)
        self.crs_rbtn.setObjectName(u"crs_rbtn")
        self.crs_rbtn.setChecked(True)

        self.gridLayout_2.addWidget(self.crs_rbtn, 3, 0, 1, 1)

        self.line = QFrame(self.groupBox)
        self.line.setObjectName(u"line")
        self.line.setFrameShape(QFrame.HLine)
        self.line.setFrameShadow(QFrame.Sunken)

        self.gridLayout_2.addWidget(self.line, 5, 0, 1, 3)


        self.verticalLayout.addWidget(self.groupBox)

        self.verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.verticalLayout.addItem(self.verticalSpacer)

        self.open_file_cbox = QCheckBox(self.frame)
        self.open_file_cbox.setObjectName(u"open_file_cbox")
        self.open_file_cbox.setChecked(True)

        self.verticalLayout.addWidget(self.open_file_cbox)

        self.export_gpx_btn = QPushButton(self.frame)
        self.export_gpx_btn.setObjectName(u"export_gpx_btn")
        self.export_gpx_btn.setCheckable(False)
        self.export_gpx_btn.setChecked(False)

        self.verticalLayout.addWidget(self.export_gpx_btn)


        self.gridLayout.addWidget(self.frame, 0, 0, 1, 1)

        self.table = QTableWidget(self.centralwidget)
        if (self.table.columnCount() < 3):
            self.table.setColumnCount(3)
        __qtablewidgetitem = QTableWidgetItem()
        self.table.setHorizontalHeaderItem(0, __qtablewidgetitem)
        __qtablewidgetitem1 = QTableWidgetItem()
        self.table.setHorizontalHeaderItem(1, __qtablewidgetitem1)
        __qtablewidgetitem2 = QTableWidgetItem()
        self.table.setHorizontalHeaderItem(2, __qtablewidgetitem2)
        self.table.setObjectName(u"table")
        self.table.setFrameShape(QFrame.Box)
        self.table.setAlternatingRowColors(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setGridStyle(Qt.SolidLine)
        self.table.setSortingEnabled(True)

        self.gridLayout.addWidget(self.table, 0, 1, 1, 1)

        GPXCreator.setCentralWidget(self.centralwidget)
        self.menubar = QMenuBar(GPXCreator)
        self.menubar.setObjectName(u"menubar")
        self.menubar.setGeometry(QRect(0, 0, 822, 21))
        self.menuFile = QMenu(self.menubar)
        self.menuFile.setObjectName(u"menuFile")
        GPXCreator.setMenuBar(self.menubar)
        self.status_bar = QStatusBar(GPXCreator)
        self.status_bar.setObjectName(u"status_bar")
        self.status_bar.setSizeGripEnabled(True)
        GPXCreator.setStatusBar(self.status_bar)

        self.menubar.addAction(self.menuFile.menuAction())
        self.menuFile.addAction(self.openAction)
        self.menuFile.addAction(self.exportGPX)
        self.menuFile.addSeparator()
        self.menuFile.addAction(self.create_csv_template_action)

        self.retranslateUi(GPXCreator)

        QMetaObject.connectSlotsByName(GPXCreator)
    # setupUi

    def retranslateUi(self, GPXCreator):
        GPXCreator.setWindowTitle(QCoreApplication.translate("GPXCreator", u"MainWindow", None))
        self.openAction.setText(QCoreApplication.translate("GPXCreator", u"Open File", None))
        self.exportGPX.setText(QCoreApplication.translate("GPXCreator", u"Export GPX", None))
        self.create_csv_template_action.setText(QCoreApplication.translate("GPXCreator", u"Create CSV Template", None))
        self.label_4.setText(QCoreApplication.translate("GPXCreator", u"Name", None))
        self.groupBox.setTitle(QCoreApplication.translate("GPXCreator", u"Input CRS", None))
        self.label.setText(QCoreApplication.translate("GPXCreator", u"System:", None))
        self.zone_number_label.setText(QCoreApplication.translate("GPXCreator", u"Zone:", None))
        self.label_2.setText(QCoreApplication.translate("GPXCreator", u"Datum:", None))
        self.epsg_rbtn.setText("")
        self.label_3.setText(QCoreApplication.translate("GPXCreator", u"EPSG:", None))
        self.crs_rbtn.setText("")
        self.open_file_cbox.setText(QCoreApplication.translate("GPXCreator", u"Open File After Save", None))
        self.export_gpx_btn.setText(QCoreApplication.translate("GPXCreator", u"Create GPX", None))
        ___qtablewidgetitem = self.table.horizontalHeaderItem(0)
        ___qtablewidgetitem.setText(QCoreApplication.translate("GPXCreator", u"Easting", None));
        ___qtablewidgetitem1 = self.table.horizontalHeaderItem(1)
        ___qtablewidgetitem1.setText(QCoreApplication.translate("GPXCreator", u"Northing", None));
        ___qtablewidgetitem2 = self.table.horizontalHeaderItem(2)
        ___qtablewidgetitem2.setText(QCoreApplication.translate("GPXCreator", u"Comment", None));
        self.menuFile.setTitle(QCoreApplication.translate("GPXCreator", u"File", None))
    # retranslateUi

