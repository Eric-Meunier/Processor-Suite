# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'map_generator.ui'
##
## Created by: Qt User Interface Compiler version 5.15.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide2.QtCore import *
from PySide2.QtGui import *
from PySide2.QtWidgets import *


class Ui_MapGenerator(object):
    def setupUi(self, MapGenerator):
        if not MapGenerator.objectName():
            MapGenerator.setObjectName(u"MapGenerator")
        MapGenerator.resize(800, 600)
        self.action_save_pdf = QAction(MapGenerator)
        self.action_save_pdf.setObjectName(u"action_save_pdf")
        self.centralwidget = QWidget(MapGenerator)
        self.centralwidget.setObjectName(u"centralwidget")
        self.horizontalLayout = QHBoxLayout(self.centralwidget)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.frame = QFrame(self.centralwidget)
        self.frame.setObjectName(u"frame")
        sizePolicy = QSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.frame.sizePolicy().hasHeightForWidth())
        self.frame.setSizePolicy(sizePolicy)
        self.frame.setFrameShape(QFrame.StyledPanel)
        self.frame.setFrameShadow(QFrame.Raised)
        self.verticalLayout_4 = QVBoxLayout(self.frame)
        self.verticalLayout_4.setSpacing(6)
        self.verticalLayout_4.setObjectName(u"verticalLayout_4")
        self.verticalLayout_4.setContentsMargins(2, 2, 2, 2)
        self.groupBox = QGroupBox(self.frame)
        self.groupBox.setObjectName(u"groupBox")
        sizePolicy1 = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.groupBox.sizePolicy().hasHeightForWidth())
        self.groupBox.setSizePolicy(sizePolicy1)
        self.groupBox.setCheckable(True)
        self.verticalLayout_2 = QVBoxLayout(self.groupBox)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.label_holes_cbox = QCheckBox(self.groupBox)
        self.label_holes_cbox.setObjectName(u"label_holes_cbox")

        self.verticalLayout_2.addWidget(self.label_holes_cbox)

        self.draw_hole_trace_cbox = QCheckBox(self.groupBox)
        self.draw_hole_trace_cbox.setObjectName(u"draw_hole_trace_cbox")

        self.verticalLayout_2.addWidget(self.draw_hole_trace_cbox)


        self.verticalLayout_4.addWidget(self.groupBox)

        self.draw_loops_cbox = QGroupBox(self.frame)
        self.draw_loops_cbox.setObjectName(u"draw_loops_cbox")
        sizePolicy1.setHeightForWidth(self.draw_loops_cbox.sizePolicy().hasHeightForWidth())
        self.draw_loops_cbox.setSizePolicy(sizePolicy1)
        self.draw_loops_cbox.setCheckable(True)
        self.verticalLayout = QVBoxLayout(self.draw_loops_cbox)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.label_loops_cbox = QCheckBox(self.draw_loops_cbox)
        self.label_loops_cbox.setObjectName(u"label_loops_cbox")

        self.verticalLayout.addWidget(self.label_loops_cbox)


        self.verticalLayout_4.addWidget(self.draw_loops_cbox)

        self.inset_map_box = QGroupBox(self.frame)
        self.inset_map_box.setObjectName(u"inset_map_box")
        self.inset_map_box.setCheckable(True)
        self.verticalLayout_5 = QVBoxLayout(self.inset_map_box)
        self.verticalLayout_5.setObjectName(u"verticalLayout_5")
        self.label_inset_gridlines_cbox = QCheckBox(self.inset_map_box)
        self.label_inset_gridlines_cbox.setObjectName(u"label_inset_gridlines_cbox")

        self.verticalLayout_5.addWidget(self.label_inset_gridlines_cbox)

        self.label_inset_countries_cbox = QCheckBox(self.inset_map_box)
        self.label_inset_countries_cbox.setObjectName(u"label_inset_countries_cbox")

        self.verticalLayout_5.addWidget(self.label_inset_countries_cbox)


        self.verticalLayout_4.addWidget(self.inset_map_box)

        self.verticalSpacer_2 = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.verticalLayout_4.addItem(self.verticalSpacer_2)

        self.groupBox_2 = QGroupBox(self.frame)
        self.groupBox_2.setObjectName(u"groupBox_2")
        sizePolicy1.setHeightForWidth(self.groupBox_2.sizePolicy().hasHeightForWidth())
        self.groupBox_2.setSizePolicy(sizePolicy1)
        self.verticalLayout_3 = QVBoxLayout(self.groupBox_2)
        self.verticalLayout_3.setObjectName(u"verticalLayout_3")
        self.sep_by_survey = QRadioButton(self.groupBox_2)
        self.sep_by_survey.setObjectName(u"sep_by_survey")

        self.verticalLayout_3.addWidget(self.sep_by_survey)

        self.sep_by_property = QRadioButton(self.groupBox_2)
        self.sep_by_property.setObjectName(u"sep_by_property")

        self.verticalLayout_3.addWidget(self.sep_by_property)

        self.sep_by_none = QRadioButton(self.groupBox_2)
        self.sep_by_none.setObjectName(u"sep_by_none")
        self.sep_by_none.setChecked(True)

        self.verticalLayout_3.addWidget(self.sep_by_none)


        self.verticalLayout_4.addWidget(self.groupBox_2)

        self.verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.verticalLayout_4.addItem(self.verticalSpacer)

        self.label = QLabel(self.frame)
        self.label.setObjectName(u"label")
        sizePolicy1.setHeightForWidth(self.label.sizePolicy().hasHeightForWidth())
        self.label.setSizePolicy(sizePolicy1)

        self.verticalLayout_4.addWidget(self.label)

        self.page_size_combo = QComboBox(self.frame)
        self.page_size_combo.addItem("")
        self.page_size_combo.addItem("")
        self.page_size_combo.setObjectName(u"page_size_combo")

        self.verticalLayout_4.addWidget(self.page_size_combo)


        self.horizontalLayout.addWidget(self.frame)

        self.scrollArea = QScrollArea(self.centralwidget)
        self.scrollArea.setObjectName(u"scrollArea")
        self.scrollArea.setWidgetResizable(True)
        self.scrollAreaWidgetContents = QWidget()
        self.scrollAreaWidgetContents.setObjectName(u"scrollAreaWidgetContents")
        self.scrollAreaWidgetContents.setGeometry(QRect(0, 0, 651, 539))
        self.scrollArea.setWidget(self.scrollAreaWidgetContents)

        self.horizontalLayout.addWidget(self.scrollArea)

        MapGenerator.setCentralWidget(self.centralwidget)
        self.menubar = QMenuBar(MapGenerator)
        self.menubar.setObjectName(u"menubar")
        self.menubar.setGeometry(QRect(0, 0, 800, 21))
        self.menu_file = QMenu(self.menubar)
        self.menu_file.setObjectName(u"menu_file")
        MapGenerator.setMenuBar(self.menubar)
        self.statusbar = QStatusBar(MapGenerator)
        self.statusbar.setObjectName(u"statusbar")
        MapGenerator.setStatusBar(self.statusbar)

        self.menubar.addAction(self.menu_file.menuAction())
        self.menu_file.addAction(self.action_save_pdf)

        self.retranslateUi(MapGenerator)

        QMetaObject.connectSlotsByName(MapGenerator)
    # setupUi

    def retranslateUi(self, MapGenerator):
        MapGenerator.setWindowTitle(QCoreApplication.translate("MapGenerator", u"MainWindow", None))
        self.action_save_pdf.setText(QCoreApplication.translate("MapGenerator", u"Save PDF", None))
        self.groupBox.setTitle(QCoreApplication.translate("MapGenerator", u"Holes", None))
        self.label_holes_cbox.setText(QCoreApplication.translate("MapGenerator", u"Labels", None))
        self.draw_hole_trace_cbox.setText(QCoreApplication.translate("MapGenerator", u"Hole Trace", None))
        self.draw_loops_cbox.setTitle(QCoreApplication.translate("MapGenerator", u"Loops", None))
        self.label_loops_cbox.setText(QCoreApplication.translate("MapGenerator", u"Labels", None))
        self.inset_map_box.setTitle(QCoreApplication.translate("MapGenerator", u"Inset Map", None))
        self.label_inset_gridlines_cbox.setText(QCoreApplication.translate("MapGenerator", u"Label Gridlines", None))
        self.label_inset_countries_cbox.setText(QCoreApplication.translate("MapGenerator", u"Label Countries", None))
        self.groupBox_2.setTitle(QCoreApplication.translate("MapGenerator", u"Separate Maps By:", None))
        self.sep_by_survey.setText(QCoreApplication.translate("MapGenerator", u"Survey Type", None))
        self.sep_by_property.setText(QCoreApplication.translate("MapGenerator", u"Property", None))
        self.sep_by_none.setText(QCoreApplication.translate("MapGenerator", u"None", None))
        self.label.setText(QCoreApplication.translate("MapGenerator", u"Page Size:", None))
        self.page_size_combo.setItemText(0, QCoreApplication.translate("MapGenerator", u"11 x 8.5\"", None))
        self.page_size_combo.setItemText(1, QCoreApplication.translate("MapGenerator", u"18 x 11\"", None))

        self.menu_file.setTitle(QCoreApplication.translate("MapGenerator", u"File", None))
    # retranslateUi

