# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'contour_map.ui'
##
## Created by: Qt User Interface Compiler version 5.14.1
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide2.QtCore import (QCoreApplication, QMetaObject, QObject, QPoint,
    QRect, QSize, QUrl, Qt)
from PySide2.QtGui import (QBrush, QColor, QConicalGradient, QCursor, QFont,
    QFontDatabase, QIcon, QLinearGradient, QPalette, QPainter, QPixmap,
    QRadialGradient)
from PySide2.QtWidgets import *


class Ui_ContourMap(object):
    def setupUi(self, ContourMap):
        if ContourMap.objectName():
            ContourMap.setObjectName(u"ContourMap")
        ContourMap.resize(901, 718)
        self.horizontalLayout = QHBoxLayout(ContourMap)
        self.horizontalLayout.setSpacing(1)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.horizontalLayout.setContentsMargins(0, 0, 0, 0)
        self.splitter = QSplitter(ContourMap)
        self.splitter.setObjectName(u"splitter")
        self.splitter.setOrientation(Qt.Horizontal)
        self.splitter.setHandleWidth(2)
        self.frame = QFrame(self.splitter)
        self.frame.setObjectName(u"frame")
        sizePolicy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.frame.sizePolicy().hasHeightForWidth())
        self.frame.setSizePolicy(sizePolicy)
        self.frame.setMaximumSize(QSize(16777215, 16777215))
        self.frame.setFrameShape(QFrame.StyledPanel)
        self.frame.setFrameShadow(QFrame.Plain)
        self.verticalLayout_4 = QVBoxLayout(self.frame)
        self.verticalLayout_4.setObjectName(u"verticalLayout_4")
        self.groupBox_2 = QGroupBox(self.frame)
        self.groupBox_2.setObjectName(u"groupBox_2")
        sizePolicy.setHeightForWidth(self.groupBox_2.sizePolicy().hasHeightForWidth())
        self.groupBox_2.setSizePolicy(sizePolicy)
        self.groupBox_2.setMinimumSize(QSize(0, 0))
        self.groupBox_2.setMaximumSize(QSize(16777215, 16777215))
        self.groupBox_2.setAlignment(Qt.AlignLeading|Qt.AlignLeft|Qt.AlignVCenter)
        self.groupBox_2.setFlat(False)
        self.verticalLayout_2 = QVBoxLayout(self.groupBox_2)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.z_rbtn = QRadioButton(self.groupBox_2)
        self.z_rbtn.setObjectName(u"z_rbtn")
        self.z_rbtn.setChecked(True)

        self.verticalLayout_2.addWidget(self.z_rbtn)

        self.x_rbtn = QRadioButton(self.groupBox_2)
        self.x_rbtn.setObjectName(u"x_rbtn")

        self.verticalLayout_2.addWidget(self.x_rbtn)

        self.y_rbtn = QRadioButton(self.groupBox_2)
        self.y_rbtn.setObjectName(u"y_rbtn")

        self.verticalLayout_2.addWidget(self.y_rbtn)

        self.tf_rbtn = QRadioButton(self.groupBox_2)
        self.tf_rbtn.setObjectName(u"tf_rbtn")

        self.verticalLayout_2.addWidget(self.tf_rbtn)


        self.verticalLayout_4.addWidget(self.groupBox_2)

        self.groupBox = QGroupBox(self.frame)
        self.groupBox.setObjectName(u"groupBox")
        sizePolicy.setHeightForWidth(self.groupBox.sizePolicy().hasHeightForWidth())
        self.groupBox.setSizePolicy(sizePolicy)
        self.groupBox.setMinimumSize(QSize(0, 0))
        self.groupBox.setMaximumSize(QSize(16777215, 16777215))
        self.gridLayout_2 = QGridLayout(self.groupBox)
        self.gridLayout_2.setObjectName(u"gridLayout_2")
        self.plot_lines_cbox = QGroupBox(self.groupBox)
        self.plot_lines_cbox.setObjectName(u"plot_lines_cbox")
        self.plot_lines_cbox.setFlat(True)
        self.plot_lines_cbox.setCheckable(True)
        self.verticalLayout_3 = QVBoxLayout(self.plot_lines_cbox)
        self.verticalLayout_3.setObjectName(u"verticalLayout_3")
        self.label_lines_cbox = QCheckBox(self.plot_lines_cbox)
        self.label_lines_cbox.setObjectName(u"label_lines_cbox")
        self.label_lines_cbox.setChecked(True)

        self.verticalLayout_3.addWidget(self.label_lines_cbox)

        self.label_stations_cbox = QCheckBox(self.plot_lines_cbox)
        self.label_stations_cbox.setObjectName(u"label_stations_cbox")

        self.verticalLayout_3.addWidget(self.label_stations_cbox)

        self.plot_stations_cbox = QCheckBox(self.plot_lines_cbox)
        self.plot_stations_cbox.setObjectName(u"plot_stations_cbox")
        self.plot_stations_cbox.setChecked(False)

        self.verticalLayout_3.addWidget(self.plot_stations_cbox)


        self.gridLayout_2.addWidget(self.plot_lines_cbox, 1, 0, 1, 2)

        self.grid_cbox = QCheckBox(self.groupBox)
        self.grid_cbox.setObjectName(u"grid_cbox")

        self.gridLayout_2.addWidget(self.grid_cbox, 5, 0, 1, 2)

        self.title_box_cbox = QCheckBox(self.groupBox)
        self.title_box_cbox.setObjectName(u"title_box_cbox")
        self.title_box_cbox.setChecked(False)

        self.gridLayout_2.addWidget(self.title_box_cbox, 6, 0, 1, 2)

        self.plot_elevation_cbox = QCheckBox(self.groupBox)
        self.plot_elevation_cbox.setObjectName(u"plot_elevation_cbox")
        self.plot_elevation_cbox.setChecked(True)

        self.gridLayout_2.addWidget(self.plot_elevation_cbox, 4, 0, 1, 2)

        self.plot_loops_cbox = QGroupBox(self.groupBox)
        self.plot_loops_cbox.setObjectName(u"plot_loops_cbox")
        self.plot_loops_cbox.setFlat(True)
        self.plot_loops_cbox.setCheckable(True)
        self.verticalLayout = QVBoxLayout(self.plot_loops_cbox)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.label_loops_cbox = QCheckBox(self.plot_loops_cbox)
        self.label_loops_cbox.setObjectName(u"label_loops_cbox")

        self.verticalLayout.addWidget(self.label_loops_cbox)


        self.gridLayout_2.addWidget(self.plot_loops_cbox, 0, 0, 1, 2)


        self.verticalLayout_4.addWidget(self.groupBox)

        self.label = QLabel(self.frame)
        self.label.setObjectName(u"label")
        sizePolicy1 = QSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.label.sizePolicy().hasHeightForWidth())
        self.label.setSizePolicy(sizePolicy1)
        self.label.setAlignment(Qt.AlignCenter)

        self.verticalLayout_4.addWidget(self.label)

        self.channel_spinbox = QSpinBox(self.frame)
        self.channel_spinbox.setObjectName(u"channel_spinbox")
        sizePolicy.setHeightForWidth(self.channel_spinbox.sizePolicy().hasHeightForWidth())
        self.channel_spinbox.setSizePolicy(sizePolicy)
        self.channel_spinbox.setMinimumSize(QSize(0, 0))
        self.channel_spinbox.setMaximumSize(QSize(16777215, 16777215))

        self.verticalLayout_4.addWidget(self.channel_spinbox)

        self.time_label = QLabel(self.frame)
        self.time_label.setObjectName(u"time_label")
        sizePolicy1.setHeightForWidth(self.time_label.sizePolicy().hasHeightForWidth())
        self.time_label.setSizePolicy(sizePolicy1)

        self.verticalLayout_4.addWidget(self.time_label)

        self.verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.verticalLayout_4.addItem(self.verticalSpacer)

        self.groupBox_3 = QGroupBox(self.frame)
        self.groupBox_3.setObjectName(u"groupBox_3")
        sizePolicy.setHeightForWidth(self.groupBox_3.sizePolicy().hasHeightForWidth())
        self.groupBox_3.setSizePolicy(sizePolicy)
        self.gridLayout_3 = QGridLayout(self.groupBox_3)
        self.gridLayout_3.setObjectName(u"gridLayout_3")
        self.current_channel_rbtn = QRadioButton(self.groupBox_3)
        self.current_channel_rbtn.setObjectName(u"current_channel_rbtn")
        sizePolicy2 = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        sizePolicy2.setHorizontalStretch(0)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(self.current_channel_rbtn.sizePolicy().hasHeightForWidth())
        self.current_channel_rbtn.setSizePolicy(sizePolicy2)
        self.current_channel_rbtn.setChecked(True)

        self.gridLayout_3.addWidget(self.current_channel_rbtn, 0, 0, 1, 1)

        self.channel_list_rbtn = QRadioButton(self.groupBox_3)
        self.channel_list_rbtn.setObjectName(u"channel_list_rbtn")
        sizePolicy2.setHeightForWidth(self.channel_list_rbtn.sizePolicy().hasHeightForWidth())
        self.channel_list_rbtn.setSizePolicy(sizePolicy2)

        self.gridLayout_3.addWidget(self.channel_list_rbtn, 1, 0, 1, 1)

        self.save_figure_btn = QPushButton(self.groupBox_3)
        self.save_figure_btn.setObjectName(u"save_figure_btn")
        sizePolicy2.setHeightForWidth(self.save_figure_btn.sizePolicy().hasHeightForWidth())
        self.save_figure_btn.setSizePolicy(sizePolicy2)

        self.gridLayout_3.addWidget(self.save_figure_btn, 3, 0, 1, 1)

        self.channel_list_edit = QLineEdit(self.groupBox_3)
        self.channel_list_edit.setObjectName(u"channel_list_edit")
        sizePolicy2.setHeightForWidth(self.channel_list_edit.sizePolicy().hasHeightForWidth())
        self.channel_list_edit.setSizePolicy(sizePolicy2)
        self.channel_list_edit.setClearButtonEnabled(False)

        self.gridLayout_3.addWidget(self.channel_list_edit, 2, 0, 1, 1)


        self.verticalLayout_4.addWidget(self.groupBox_3)

        self.splitter.addWidget(self.frame)
        self.frame_2 = QFrame(self.splitter)
        self.frame_2.setObjectName(u"frame_2")
        sizePolicy3 = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        sizePolicy3.setHorizontalStretch(0)
        sizePolicy3.setVerticalStretch(0)
        sizePolicy3.setHeightForWidth(self.frame_2.sizePolicy().hasHeightForWidth())
        self.frame_2.setSizePolicy(sizePolicy3)
        self.frame_2.setFrameShape(QFrame.StyledPanel)
        self.frame_2.setFrameShadow(QFrame.Plain)
        self.gridLayout = QGridLayout(self.frame_2)
        self.gridLayout.setSpacing(0)
        self.gridLayout.setObjectName(u"gridLayout")
        self.gridLayout.setContentsMargins(0, 0, 0, 0)
        self.horizontalSpacer = QSpacerItem(10, 20, QSizePolicy.Fixed, QSizePolicy.Minimum)

        self.gridLayout.addItem(self.horizontalSpacer, 1, 0, 1, 1)

        self.map_layout = QGridLayout()
        self.map_layout.setObjectName(u"map_layout")
        self.map_layout.setSizeConstraint(QLayout.SetDefaultConstraint)

        self.gridLayout.addLayout(self.map_layout, 0, 0, 1, 2)

        self.toolbar_layout = QVBoxLayout()
        self.toolbar_layout.setSpacing(0)
        self.toolbar_layout.setObjectName(u"toolbar_layout")
        self.toolbar_layout.setSizeConstraint(QLayout.SetDefaultConstraint)

        self.gridLayout.addLayout(self.toolbar_layout, 1, 1, 1, 1)

        self.splitter.addWidget(self.frame_2)

        self.horizontalLayout.addWidget(self.splitter)

        QWidget.setTabOrder(self.z_rbtn, self.x_rbtn)
        QWidget.setTabOrder(self.x_rbtn, self.y_rbtn)
        QWidget.setTabOrder(self.y_rbtn, self.tf_rbtn)
        QWidget.setTabOrder(self.tf_rbtn, self.plot_loops_cbox)
        QWidget.setTabOrder(self.plot_loops_cbox, self.label_loops_cbox)
        QWidget.setTabOrder(self.label_loops_cbox, self.plot_lines_cbox)
        QWidget.setTabOrder(self.plot_lines_cbox, self.label_lines_cbox)
        QWidget.setTabOrder(self.label_lines_cbox, self.label_stations_cbox)
        QWidget.setTabOrder(self.label_stations_cbox, self.plot_stations_cbox)
        QWidget.setTabOrder(self.plot_stations_cbox, self.plot_elevation_cbox)
        QWidget.setTabOrder(self.plot_elevation_cbox, self.grid_cbox)
        QWidget.setTabOrder(self.grid_cbox, self.title_box_cbox)
        QWidget.setTabOrder(self.title_box_cbox, self.current_channel_rbtn)
        QWidget.setTabOrder(self.current_channel_rbtn, self.channel_list_rbtn)
        QWidget.setTabOrder(self.channel_list_rbtn, self.channel_list_edit)
        QWidget.setTabOrder(self.channel_list_edit, self.save_figure_btn)

        self.retranslateUi(ContourMap)

        QMetaObject.connectSlotsByName(ContourMap)
    # setupUi

    def retranslateUi(self, ContourMap):
        ContourMap.setWindowTitle(QCoreApplication.translate("ContourMap", u"Form", None))
        self.groupBox_2.setTitle(QCoreApplication.translate("ContourMap", u"Component", None))
        self.z_rbtn.setText(QCoreApplication.translate("ContourMap", u"Z", None))
        self.x_rbtn.setText(QCoreApplication.translate("ContourMap", u"X", None))
        self.y_rbtn.setText(QCoreApplication.translate("ContourMap", u"Y", None))
        self.tf_rbtn.setText(QCoreApplication.translate("ContourMap", u"Total Field", None))
        self.groupBox.setTitle(QCoreApplication.translate("ContourMap", u"Options", None))
        self.plot_lines_cbox.setTitle(QCoreApplication.translate("ContourMap", u"Plot Lines", None))
        self.label_lines_cbox.setText(QCoreApplication.translate("ContourMap", u"Label Lines", None))
        self.label_stations_cbox.setText(QCoreApplication.translate("ContourMap", u"Label Stations", None))
        self.plot_stations_cbox.setText(QCoreApplication.translate("ContourMap", u"Plot Stations", None))
        self.grid_cbox.setText(QCoreApplication.translate("ContourMap", u"Grid", None))
        self.title_box_cbox.setText(QCoreApplication.translate("ContourMap", u"Title Box", None))
        self.plot_elevation_cbox.setText(QCoreApplication.translate("ContourMap", u"Elevation Contour", None))
        self.plot_loops_cbox.setTitle(QCoreApplication.translate("ContourMap", u"Plot Loops", None))
        self.label_loops_cbox.setText(QCoreApplication.translate("ContourMap", u"Label Loops", None))
        self.label.setText(QCoreApplication.translate("ContourMap", u"Channel", None))
        self.time_label.setText(QCoreApplication.translate("ContourMap", u"TextLabel", None))
        self.groupBox_3.setTitle(QCoreApplication.translate("ContourMap", u"Save Figure", None))
        self.current_channel_rbtn.setText(QCoreApplication.translate("ContourMap", u"Selected Channel", None))
        self.channel_list_rbtn.setText(QCoreApplication.translate("ContourMap", u"List of Channels", None))
        self.save_figure_btn.setText(QCoreApplication.translate("ContourMap", u"Save", None))
    # retranslateUi

