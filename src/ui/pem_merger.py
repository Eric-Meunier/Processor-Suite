# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'pem_merger.ui'
##
## Created by: Qt User Interface Compiler version 5.15.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide2.QtCore import *
from PySide2.QtGui import *
from PySide2.QtWidgets import *

from pyqtgraph import GraphicsLayoutWidget


class Ui_PEMMerger(object):
    def setupUi(self, PEMMerger):
        if not PEMMerger.objectName():
            PEMMerger.setObjectName(u"PEMMerger")
        PEMMerger.resize(894, 730)
        self.actionSymbols = QAction(PEMMerger)
        self.actionSymbols.setObjectName(u"actionSymbols")
        self.actionSymbols.setCheckable(True)
        self.actionSymbols.setChecked(True)
        self.actionSave_As = QAction(PEMMerger)
        self.actionSave_As.setObjectName(u"actionSave_As")
        self.actionSave_Screenshot = QAction(PEMMerger)
        self.actionSave_Screenshot.setObjectName(u"actionSave_Screenshot")
        self.actionCopy_Screenshot = QAction(PEMMerger)
        self.actionCopy_Screenshot.setObjectName(u"actionCopy_Screenshot")
        self.centralwidget = QWidget(PEMMerger)
        self.centralwidget.setObjectName(u"centralwidget")
        self.horizontalLayout = QHBoxLayout(self.centralwidget)
        self.horizontalLayout.setSpacing(3)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.horizontalLayout.setContentsMargins(0, 0, 0, 0)
        self.frame = QFrame(self.centralwidget)
        self.frame.setObjectName(u"frame")
        sizePolicy = QSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.frame.sizePolicy().hasHeightForWidth())
        self.frame.setSizePolicy(sizePolicy)
        self.frame.setStyleSheet(u"color:rgb(28, 28, 27)")
        self.frame.setFrameShape(QFrame.StyledPanel)
        self.frame.setFrameShadow(QFrame.Plain)
        self.formLayout = QFormLayout(self.frame)
        self.formLayout.setObjectName(u"formLayout")
        self.file_label_1 = QLabel(self.frame)
        self.file_label_1.setObjectName(u"file_label_1")
        font = QFont()
        font.setBold(True)
        font.setWeight(75)
        self.file_label_1.setFont(font)
        self.file_label_1.setStyleSheet(u"color:rgb(28, 28, 27)")
        self.file_label_1.setAlignment(Qt.AlignCenter)

        self.formLayout.setWidget(0, QFormLayout.SpanningRole, self.file_label_1)

        self.groupBox_5 = QGroupBox(self.frame)
        self.groupBox_5.setObjectName(u"groupBox_5")
        font1 = QFont()
        font1.setBold(False)
        font1.setItalic(False)
        font1.setWeight(50)
        self.groupBox_5.setFont(font1)
        self.groupBox_5.setAlignment(Qt.AlignCenter)
        self.groupBox_5.setFlat(True)
        self.formLayout_7 = QFormLayout(self.groupBox_5)
        self.formLayout_7.setObjectName(u"formLayout_7")
        self.label_24 = QLabel(self.groupBox_5)
        self.label_24.setObjectName(u"label_24")
        self.label_24.setFont(font1)

        self.formLayout_7.setWidget(0, QFormLayout.LabelRole, self.label_24)

        self.client_label_1 = QLabel(self.groupBox_5)
        self.client_label_1.setObjectName(u"client_label_1")
        self.client_label_1.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.formLayout_7.setWidget(0, QFormLayout.FieldRole, self.client_label_1)

        self.label_25 = QLabel(self.groupBox_5)
        self.label_25.setObjectName(u"label_25")
        self.label_25.setFont(font1)

        self.formLayout_7.setWidget(1, QFormLayout.LabelRole, self.label_25)

        self.grid_label_1 = QLabel(self.groupBox_5)
        self.grid_label_1.setObjectName(u"grid_label_1")
        self.grid_label_1.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.formLayout_7.setWidget(1, QFormLayout.FieldRole, self.grid_label_1)

        self.label_9 = QLabel(self.groupBox_5)
        self.label_9.setObjectName(u"label_9")
        self.label_9.setFont(font1)

        self.formLayout_7.setWidget(2, QFormLayout.LabelRole, self.label_9)

        self.line_label_1 = QLabel(self.groupBox_5)
        self.line_label_1.setObjectName(u"line_label_1")
        self.line_label_1.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.formLayout_7.setWidget(2, QFormLayout.FieldRole, self.line_label_1)

        self.label_12 = QLabel(self.groupBox_5)
        self.label_12.setObjectName(u"label_12")
        self.label_12.setFont(font1)

        self.formLayout_7.setWidget(3, QFormLayout.LabelRole, self.label_12)

        self.loop_label_1 = QLabel(self.groupBox_5)
        self.loop_label_1.setObjectName(u"loop_label_1")
        self.loop_label_1.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.formLayout_7.setWidget(3, QFormLayout.FieldRole, self.loop_label_1)

        self.label_13 = QLabel(self.groupBox_5)
        self.label_13.setObjectName(u"label_13")
        self.label_13.setFont(font1)

        self.formLayout_7.setWidget(4, QFormLayout.LabelRole, self.label_13)

        self.operator_label_1 = QLabel(self.groupBox_5)
        self.operator_label_1.setObjectName(u"operator_label_1")
        self.operator_label_1.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.formLayout_7.setWidget(4, QFormLayout.FieldRole, self.operator_label_1)

        self.label_27 = QLabel(self.groupBox_5)
        self.label_27.setObjectName(u"label_27")
        font2 = QFont()
        font2.setBold(False)
        font2.setWeight(50)
        self.label_27.setFont(font2)

        self.formLayout_7.setWidget(5, QFormLayout.LabelRole, self.label_27)

        self.tools_label_1 = QLabel(self.groupBox_5)
        self.tools_label_1.setObjectName(u"tools_label_1")
        self.tools_label_1.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.formLayout_7.setWidget(5, QFormLayout.FieldRole, self.tools_label_1)


        self.formLayout.setWidget(1, QFormLayout.SpanningRole, self.groupBox_5)

        self.groupBox_3 = QGroupBox(self.frame)
        self.groupBox_3.setObjectName(u"groupBox_3")
        self.groupBox_3.setAlignment(Qt.AlignCenter)
        self.groupBox_3.setFlat(True)
        self.formLayout_5 = QFormLayout(self.groupBox_3)
        self.formLayout_5.setObjectName(u"formLayout_5")
        self.label_15 = QLabel(self.groupBox_3)
        self.label_15.setObjectName(u"label_15")
        self.label_15.setFont(font1)

        self.formLayout_5.setWidget(2, QFormLayout.LabelRole, self.label_15)

        self.rx_num_label_1 = QLabel(self.groupBox_3)
        self.rx_num_label_1.setObjectName(u"rx_num_label_1")
        self.rx_num_label_1.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.formLayout_5.setWidget(2, QFormLayout.FieldRole, self.rx_num_label_1)

        self.label_11 = QLabel(self.groupBox_3)
        self.label_11.setObjectName(u"label_11")
        self.label_11.setFont(font1)

        self.formLayout_5.setWidget(0, QFormLayout.LabelRole, self.label_11)

        self.date_label_1 = QLabel(self.groupBox_3)
        self.date_label_1.setObjectName(u"date_label_1")
        self.date_label_1.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.formLayout_5.setWidget(0, QFormLayout.FieldRole, self.date_label_1)

        self.label_19 = QLabel(self.groupBox_3)
        self.label_19.setObjectName(u"label_19")
        self.label_19.setFont(font1)

        self.formLayout_5.setWidget(1, QFormLayout.LabelRole, self.label_19)

        self.ramp_label_1 = QLabel(self.groupBox_3)
        self.ramp_label_1.setObjectName(u"ramp_label_1")
        self.ramp_label_1.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.formLayout_5.setWidget(1, QFormLayout.FieldRole, self.ramp_label_1)

        self.label_21 = QLabel(self.groupBox_3)
        self.label_21.setObjectName(u"label_21")
        self.label_21.setFont(font1)

        self.formLayout_5.setWidget(3, QFormLayout.LabelRole, self.label_21)

        self.sync_label_1 = QLabel(self.groupBox_3)
        self.sync_label_1.setObjectName(u"sync_label_1")
        self.sync_label_1.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.formLayout_5.setWidget(3, QFormLayout.FieldRole, self.sync_label_1)

        self.label_14 = QLabel(self.groupBox_3)
        self.label_14.setObjectName(u"label_14")
        self.label_14.setFont(font2)

        self.formLayout_5.setWidget(4, QFormLayout.LabelRole, self.label_14)

        self.zts_label_1 = QLabel(self.groupBox_3)
        self.zts_label_1.setObjectName(u"zts_label_1")
        self.zts_label_1.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.formLayout_5.setWidget(4, QFormLayout.FieldRole, self.zts_label_1)


        self.formLayout.setWidget(2, QFormLayout.SpanningRole, self.groupBox_3)

        self.groupBox = QGroupBox(self.frame)
        self.groupBox.setObjectName(u"groupBox")
        sizePolicy1 = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.groupBox.sizePolicy().hasHeightForWidth())
        self.groupBox.setSizePolicy(sizePolicy1)
        self.groupBox.setAlignment(Qt.AlignCenter)
        self.groupBox.setFlat(True)
        self.formLayout_3 = QFormLayout(self.groupBox)
        self.formLayout_3.setObjectName(u"formLayout_3")
        self.label = QLabel(self.groupBox)
        self.label.setObjectName(u"label")
        self.label.setFont(font1)

        self.formLayout_3.setWidget(0, QFormLayout.LabelRole, self.label)

        self.coil_area_sbox_1 = QSpinBox(self.groupBox)
        self.coil_area_sbox_1.setObjectName(u"coil_area_sbox_1")
        sizePolicy2 = QSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        sizePolicy2.setHorizontalStretch(0)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(self.coil_area_sbox_1.sizePolicy().hasHeightForWidth())
        self.coil_area_sbox_1.setSizePolicy(sizePolicy2)
        self.coil_area_sbox_1.setFrame(True)
        self.coil_area_sbox_1.setButtonSymbols(QAbstractSpinBox.UpDownArrows)
        self.coil_area_sbox_1.setProperty("showGroupSeparator", False)
        self.coil_area_sbox_1.setMinimum(1)
        self.coil_area_sbox_1.setMaximum(99999)
        self.coil_area_sbox_1.setSingleStep(50)

        self.formLayout_3.setWidget(0, QFormLayout.FieldRole, self.coil_area_sbox_1)

        self.label_3 = QLabel(self.groupBox)
        self.label_3.setObjectName(u"label_3")
        self.label_3.setFont(font1)

        self.formLayout_3.setWidget(1, QFormLayout.LabelRole, self.label_3)

        self.current_sbox_1 = QDoubleSpinBox(self.groupBox)
        self.current_sbox_1.setObjectName(u"current_sbox_1")
        self.current_sbox_1.setDecimals(1)
        self.current_sbox_1.setMinimum(0.100000000000000)
        self.current_sbox_1.setMaximum(99.900000000000006)
        self.current_sbox_1.setSingleStep(0.500000000000000)
        self.current_sbox_1.setValue(20.000000000000000)

        self.formLayout_3.setWidget(1, QFormLayout.FieldRole, self.current_sbox_1)

        self.label_2 = QLabel(self.groupBox)
        self.label_2.setObjectName(u"label_2")
        self.label_2.setFont(font2)

        self.formLayout_3.setWidget(2, QFormLayout.LabelRole, self.label_2)

        self.factor_sbox_1 = QDoubleSpinBox(self.groupBox)
        self.factor_sbox_1.setObjectName(u"factor_sbox_1")
        self.factor_sbox_1.setMinimum(-99.989999999999995)
        self.factor_sbox_1.setSingleStep(0.050000000000000)
        self.factor_sbox_1.setValue(0.000000000000000)

        self.formLayout_3.setWidget(2, QFormLayout.FieldRole, self.factor_sbox_1)

        self.soa_sbox_1 = QDoubleSpinBox(self.groupBox)
        self.soa_sbox_1.setObjectName(u"soa_sbox_1")
        self.soa_sbox_1.setEnabled(False)
        self.soa_sbox_1.setMinimum(-99.000000000000000)
        self.soa_sbox_1.setMaximum(99.000000000000000)

        self.formLayout_3.setWidget(3, QFormLayout.FieldRole, self.soa_sbox_1)

        self.flip_data_btn_1 = QPushButton(self.groupBox)
        self.flip_data_btn_1.setObjectName(u"flip_data_btn_1")
        self.flip_data_btn_1.setEnabled(True)
        sizePolicy2.setHeightForWidth(self.flip_data_btn_1.sizePolicy().hasHeightForWidth())
        self.flip_data_btn_1.setSizePolicy(sizePolicy2)
        self.flip_data_btn_1.setMaximumSize(QSize(16777215, 16777215))

        self.formLayout_3.setWidget(4, QFormLayout.SpanningRole, self.flip_data_btn_1)

        self.label_28 = QLabel(self.groupBox)
        self.label_28.setObjectName(u"label_28")
        self.label_28.setEnabled(True)

        self.formLayout_3.setWidget(3, QFormLayout.LabelRole, self.label_28)


        self.formLayout.setWidget(3, QFormLayout.SpanningRole, self.groupBox)


        self.horizontalLayout.addWidget(self.frame)

        self.profile_tab_widget = QStackedWidget(self.centralwidget)
        self.profile_tab_widget.setObjectName(u"profile_tab_widget")
        self.profile_tab_widget.setFrameShape(QFrame.StyledPanel)
        self.profile_tab_widget.setFrameShadow(QFrame.Plain)
        self.stackedWidgetPage1 = QWidget()
        self.stackedWidgetPage1.setObjectName(u"stackedWidgetPage1")
        self.stackedWidgetPage1.setEnabled(True)
        self.verticalLayout = QVBoxLayout(self.stackedWidgetPage1)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.x_profile_layout = GraphicsLayoutWidget(self.stackedWidgetPage1)
        self.x_profile_layout.setObjectName(u"x_profile_layout")
        self.x_profile_layout.setEnabled(True)
        self.x_profile_layout.setFrameShape(QFrame.NoFrame)

        self.verticalLayout.addWidget(self.x_profile_layout)

        self.profile_tab_widget.addWidget(self.stackedWidgetPage1)
        self.stackedWidgetPage2 = QWidget()
        self.stackedWidgetPage2.setObjectName(u"stackedWidgetPage2")
        self.stackedWidgetPage2.setEnabled(True)
        self.verticalLayout_2 = QVBoxLayout(self.stackedWidgetPage2)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.verticalLayout_2.setContentsMargins(0, 0, 0, 0)
        self.y_profile_layout = GraphicsLayoutWidget(self.stackedWidgetPage2)
        self.y_profile_layout.setObjectName(u"y_profile_layout")
        self.y_profile_layout.setEnabled(True)
        self.y_profile_layout.setFrameShape(QFrame.NoFrame)

        self.verticalLayout_2.addWidget(self.y_profile_layout)

        self.profile_tab_widget.addWidget(self.stackedWidgetPage2)
        self.stackedWidgetPage3 = QWidget()
        self.stackedWidgetPage3.setObjectName(u"stackedWidgetPage3")
        self.stackedWidgetPage3.setEnabled(True)
        self.verticalLayout_3 = QVBoxLayout(self.stackedWidgetPage3)
        self.verticalLayout_3.setObjectName(u"verticalLayout_3")
        self.verticalLayout_3.setContentsMargins(0, 0, 0, 0)
        self.z_profile_layout = GraphicsLayoutWidget(self.stackedWidgetPage3)
        self.z_profile_layout.setObjectName(u"z_profile_layout")
        self.z_profile_layout.setEnabled(True)
        self.z_profile_layout.setFrameShape(QFrame.NoFrame)

        self.verticalLayout_3.addWidget(self.z_profile_layout)

        self.profile_tab_widget.addWidget(self.stackedWidgetPage3)

        self.horizontalLayout.addWidget(self.profile_tab_widget)

        self.frame_2 = QFrame(self.centralwidget)
        self.frame_2.setObjectName(u"frame_2")
        sizePolicy.setHeightForWidth(self.frame_2.sizePolicy().hasHeightForWidth())
        self.frame_2.setSizePolicy(sizePolicy)
        self.frame_2.setStyleSheet(u";color:rgb(206, 74, 126) ")
        self.frame_2.setFrameShape(QFrame.StyledPanel)
        self.frame_2.setFrameShadow(QFrame.Plain)
        self.formLayout_2 = QFormLayout(self.frame_2)
        self.formLayout_2.setObjectName(u"formLayout_2")
        self.file_label_2 = QLabel(self.frame_2)
        self.file_label_2.setObjectName(u"file_label_2")
        self.file_label_2.setFont(font)
        self.file_label_2.setStyleSheet(u"color:	rgb(206, 74, 126)")
        self.file_label_2.setAlignment(Qt.AlignCenter)

        self.formLayout_2.setWidget(0, QFormLayout.SpanningRole, self.file_label_2)

        self.groupBox_2 = QGroupBox(self.frame_2)
        self.groupBox_2.setObjectName(u"groupBox_2")
        self.groupBox_2.setAlignment(Qt.AlignCenter)
        self.groupBox_2.setFlat(True)
        self.formLayout_4 = QFormLayout(self.groupBox_2)
        self.formLayout_4.setObjectName(u"formLayout_4")
        self.label_17 = QLabel(self.groupBox_2)
        self.label_17.setObjectName(u"label_17")
        self.label_17.setFont(font2)

        self.formLayout_4.setWidget(0, QFormLayout.LabelRole, self.label_17)

        self.client_label_2 = QLabel(self.groupBox_2)
        self.client_label_2.setObjectName(u"client_label_2")
        self.client_label_2.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.formLayout_4.setWidget(0, QFormLayout.FieldRole, self.client_label_2)

        self.label_18 = QLabel(self.groupBox_2)
        self.label_18.setObjectName(u"label_18")
        self.label_18.setFont(font2)

        self.formLayout_4.setWidget(1, QFormLayout.LabelRole, self.label_18)

        self.grid_label_2 = QLabel(self.groupBox_2)
        self.grid_label_2.setObjectName(u"grid_label_2")
        self.grid_label_2.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.formLayout_4.setWidget(1, QFormLayout.FieldRole, self.grid_label_2)

        self.label_7 = QLabel(self.groupBox_2)
        self.label_7.setObjectName(u"label_7")
        self.label_7.setFont(font2)

        self.formLayout_4.setWidget(2, QFormLayout.LabelRole, self.label_7)

        self.line_label_2 = QLabel(self.groupBox_2)
        self.line_label_2.setObjectName(u"line_label_2")
        self.line_label_2.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.formLayout_4.setWidget(2, QFormLayout.FieldRole, self.line_label_2)

        self.label_10 = QLabel(self.groupBox_2)
        self.label_10.setObjectName(u"label_10")
        self.label_10.setFont(font2)

        self.formLayout_4.setWidget(3, QFormLayout.LabelRole, self.label_10)

        self.loop_label_2 = QLabel(self.groupBox_2)
        self.loop_label_2.setObjectName(u"loop_label_2")
        self.loop_label_2.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.formLayout_4.setWidget(3, QFormLayout.FieldRole, self.loop_label_2)

        self.label_8 = QLabel(self.groupBox_2)
        self.label_8.setObjectName(u"label_8")
        self.label_8.setFont(font2)

        self.formLayout_4.setWidget(4, QFormLayout.LabelRole, self.label_8)

        self.operator_label_2 = QLabel(self.groupBox_2)
        self.operator_label_2.setObjectName(u"operator_label_2")
        self.operator_label_2.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.formLayout_4.setWidget(4, QFormLayout.FieldRole, self.operator_label_2)

        self.label_29 = QLabel(self.groupBox_2)
        self.label_29.setObjectName(u"label_29")
        self.label_29.setFont(font2)

        self.formLayout_4.setWidget(5, QFormLayout.LabelRole, self.label_29)

        self.tools_label_2 = QLabel(self.groupBox_2)
        self.tools_label_2.setObjectName(u"tools_label_2")
        self.tools_label_2.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.formLayout_4.setWidget(5, QFormLayout.FieldRole, self.tools_label_2)


        self.formLayout_2.setWidget(1, QFormLayout.SpanningRole, self.groupBox_2)

        self.groupBox_4 = QGroupBox(self.frame_2)
        self.groupBox_4.setObjectName(u"groupBox_4")
        self.groupBox_4.setAlignment(Qt.AlignCenter)
        self.groupBox_4.setFlat(True)
        self.formLayout_6 = QFormLayout(self.groupBox_4)
        self.formLayout_6.setObjectName(u"formLayout_6")
        self.label_20 = QLabel(self.groupBox_4)
        self.label_20.setObjectName(u"label_20")
        self.label_20.setFont(font2)

        self.formLayout_6.setWidget(0, QFormLayout.LabelRole, self.label_20)

        self.date_label_2 = QLabel(self.groupBox_4)
        self.date_label_2.setObjectName(u"date_label_2")
        self.date_label_2.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.formLayout_6.setWidget(0, QFormLayout.FieldRole, self.date_label_2)

        self.label_22 = QLabel(self.groupBox_4)
        self.label_22.setObjectName(u"label_22")
        self.label_22.setFont(font2)

        self.formLayout_6.setWidget(1, QFormLayout.LabelRole, self.label_22)

        self.ramp_label_2 = QLabel(self.groupBox_4)
        self.ramp_label_2.setObjectName(u"ramp_label_2")
        self.ramp_label_2.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.formLayout_6.setWidget(1, QFormLayout.FieldRole, self.ramp_label_2)

        self.label_16 = QLabel(self.groupBox_4)
        self.label_16.setObjectName(u"label_16")
        self.label_16.setFont(font2)

        self.formLayout_6.setWidget(2, QFormLayout.LabelRole, self.label_16)

        self.rx_num_label_2 = QLabel(self.groupBox_4)
        self.rx_num_label_2.setObjectName(u"rx_num_label_2")
        self.rx_num_label_2.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.formLayout_6.setWidget(2, QFormLayout.FieldRole, self.rx_num_label_2)

        self.label_23 = QLabel(self.groupBox_4)
        self.label_23.setObjectName(u"label_23")
        self.label_23.setFont(font2)

        self.formLayout_6.setWidget(3, QFormLayout.LabelRole, self.label_23)

        self.sync_label_2 = QLabel(self.groupBox_4)
        self.sync_label_2.setObjectName(u"sync_label_2")
        self.sync_label_2.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.formLayout_6.setWidget(3, QFormLayout.FieldRole, self.sync_label_2)

        self.label_26 = QLabel(self.groupBox_4)
        self.label_26.setObjectName(u"label_26")
        self.label_26.setFont(font2)

        self.formLayout_6.setWidget(4, QFormLayout.LabelRole, self.label_26)

        self.zts_label_2 = QLabel(self.groupBox_4)
        self.zts_label_2.setObjectName(u"zts_label_2")
        self.zts_label_2.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.formLayout_6.setWidget(4, QFormLayout.FieldRole, self.zts_label_2)


        self.formLayout_2.setWidget(2, QFormLayout.SpanningRole, self.groupBox_4)

        self.groupBox_6 = QGroupBox(self.frame_2)
        self.groupBox_6.setObjectName(u"groupBox_6")
        self.groupBox_6.setAlignment(Qt.AlignCenter)
        self.groupBox_6.setFlat(True)
        self.formLayout_8 = QFormLayout(self.groupBox_6)
        self.formLayout_8.setObjectName(u"formLayout_8")
        self.label_5 = QLabel(self.groupBox_6)
        self.label_5.setObjectName(u"label_5")
        self.label_5.setFont(font1)

        self.formLayout_8.setWidget(0, QFormLayout.LabelRole, self.label_5)

        self.coil_area_sbox_2 = QSpinBox(self.groupBox_6)
        self.coil_area_sbox_2.setObjectName(u"coil_area_sbox_2")
        sizePolicy2.setHeightForWidth(self.coil_area_sbox_2.sizePolicy().hasHeightForWidth())
        self.coil_area_sbox_2.setSizePolicy(sizePolicy2)
        self.coil_area_sbox_2.setMinimum(1)
        self.coil_area_sbox_2.setMaximum(99999)
        self.coil_area_sbox_2.setSingleStep(50)

        self.formLayout_8.setWidget(0, QFormLayout.FieldRole, self.coil_area_sbox_2)

        self.label_6 = QLabel(self.groupBox_6)
        self.label_6.setObjectName(u"label_6")
        self.label_6.setFont(font1)

        self.formLayout_8.setWidget(1, QFormLayout.LabelRole, self.label_6)

        self.current_sbox_2 = QDoubleSpinBox(self.groupBox_6)
        self.current_sbox_2.setObjectName(u"current_sbox_2")
        self.current_sbox_2.setFont(font2)
        self.current_sbox_2.setDecimals(1)
        self.current_sbox_2.setMinimum(0.100000000000000)
        self.current_sbox_2.setMaximum(99.900000000000006)
        self.current_sbox_2.setSingleStep(0.500000000000000)
        self.current_sbox_2.setValue(20.000000000000000)

        self.formLayout_8.setWidget(1, QFormLayout.FieldRole, self.current_sbox_2)

        self.label_4 = QLabel(self.groupBox_6)
        self.label_4.setObjectName(u"label_4")
        self.label_4.setFont(font2)

        self.formLayout_8.setWidget(2, QFormLayout.LabelRole, self.label_4)

        self.factor_sbox_2 = QDoubleSpinBox(self.groupBox_6)
        self.factor_sbox_2.setObjectName(u"factor_sbox_2")
        self.factor_sbox_2.setMinimum(-99.989999999999995)
        self.factor_sbox_2.setSingleStep(0.050000000000000)
        self.factor_sbox_2.setValue(0.000000000000000)

        self.formLayout_8.setWidget(2, QFormLayout.FieldRole, self.factor_sbox_2)

        self.flip_data_btn_2 = QPushButton(self.groupBox_6)
        self.flip_data_btn_2.setObjectName(u"flip_data_btn_2")
        self.flip_data_btn_2.setEnabled(True)

        self.formLayout_8.setWidget(4, QFormLayout.SpanningRole, self.flip_data_btn_2)

        self.soa_sbox_2 = QDoubleSpinBox(self.groupBox_6)
        self.soa_sbox_2.setObjectName(u"soa_sbox_2")
        self.soa_sbox_2.setEnabled(False)
        self.soa_sbox_2.setMinimum(-99.000000000000000)
        self.soa_sbox_2.setMaximum(99.000000000000000)

        self.formLayout_8.setWidget(3, QFormLayout.FieldRole, self.soa_sbox_2)

        self.label_30 = QLabel(self.groupBox_6)
        self.label_30.setObjectName(u"label_30")
        self.label_30.setEnabled(True)

        self.formLayout_8.setWidget(3, QFormLayout.LabelRole, self.label_30)


        self.formLayout_2.setWidget(3, QFormLayout.FieldRole, self.groupBox_6)


        self.horizontalLayout.addWidget(self.frame_2)

        PEMMerger.setCentralWidget(self.centralwidget)
        self.menubar = QMenuBar(PEMMerger)
        self.menubar.setObjectName(u"menubar")
        self.menubar.setGeometry(QRect(0, 0, 894, 21))
        self.menuFile = QMenu(self.menubar)
        self.menuFile.setObjectName(u"menuFile")
        self.menuView = QMenu(self.menubar)
        self.menuView.setObjectName(u"menuView")
        PEMMerger.setMenuBar(self.menubar)
        self.status_bar = QStatusBar(PEMMerger)
        self.status_bar.setObjectName(u"status_bar")
        PEMMerger.setStatusBar(self.status_bar)
        QWidget.setTabOrder(self.x_profile_layout, self.coil_area_sbox_1)
        QWidget.setTabOrder(self.coil_area_sbox_1, self.current_sbox_1)
        QWidget.setTabOrder(self.current_sbox_1, self.factor_sbox_1)
        QWidget.setTabOrder(self.factor_sbox_1, self.coil_area_sbox_2)
        QWidget.setTabOrder(self.coil_area_sbox_2, self.current_sbox_2)
        QWidget.setTabOrder(self.current_sbox_2, self.factor_sbox_2)
        QWidget.setTabOrder(self.factor_sbox_2, self.flip_data_btn_2)
        QWidget.setTabOrder(self.flip_data_btn_2, self.y_profile_layout)
        QWidget.setTabOrder(self.y_profile_layout, self.z_profile_layout)

        self.menubar.addAction(self.menuFile.menuAction())
        self.menubar.addAction(self.menuView.menuAction())
        self.menuFile.addAction(self.actionSave_As)
        self.menuFile.addSeparator()
        self.menuFile.addAction(self.actionSave_Screenshot)
        self.menuFile.addAction(self.actionCopy_Screenshot)
        self.menuView.addAction(self.actionSymbols)

        self.retranslateUi(PEMMerger)

        self.profile_tab_widget.setCurrentIndex(0)


        QMetaObject.connectSlotsByName(PEMMerger)
    # setupUi

    def retranslateUi(self, PEMMerger):
        PEMMerger.setWindowTitle(QCoreApplication.translate("PEMMerger", u"MainWindow", None))
        self.actionSymbols.setText(QCoreApplication.translate("PEMMerger", u"Symbols", None))
        self.actionSave_As.setText(QCoreApplication.translate("PEMMerger", u"Save PEM File...", None))
#if QT_CONFIG(shortcut)
        self.actionSave_As.setShortcut(QCoreApplication.translate("PEMMerger", u"Ctrl+S", None))
#endif // QT_CONFIG(shortcut)
        self.actionSave_Screenshot.setText(QCoreApplication.translate("PEMMerger", u"Save Image", None))
#if QT_CONFIG(shortcut)
        self.actionSave_Screenshot.setShortcut("")
#endif // QT_CONFIG(shortcut)
        self.actionCopy_Screenshot.setText(QCoreApplication.translate("PEMMerger", u"Copy Image", None))
#if QT_CONFIG(shortcut)
        self.actionCopy_Screenshot.setShortcut(QCoreApplication.translate("PEMMerger", u"Ctrl+C", None))
#endif // QT_CONFIG(shortcut)
        self.file_label_1.setText(QCoreApplication.translate("PEMMerger", u"FileLabel", None))
        self.groupBox_5.setTitle(QCoreApplication.translate("PEMMerger", u"Header Information", None))
        self.label_24.setText(QCoreApplication.translate("PEMMerger", u"Client:", None))
        self.client_label_1.setText(QCoreApplication.translate("PEMMerger", u"TextLabel", None))
        self.label_25.setText(QCoreApplication.translate("PEMMerger", u"Grid:", None))
        self.grid_label_1.setText(QCoreApplication.translate("PEMMerger", u"TextLabel", None))
        self.label_9.setText(QCoreApplication.translate("PEMMerger", u"Line:", None))
        self.line_label_1.setText(QCoreApplication.translate("PEMMerger", u"TextLabel", None))
        self.label_12.setText(QCoreApplication.translate("PEMMerger", u"Loop:", None))
        self.loop_label_1.setText(QCoreApplication.translate("PEMMerger", u"TextLabel", None))
        self.label_13.setText(QCoreApplication.translate("PEMMerger", u"Operator:", None))
        self.operator_label_1.setText(QCoreApplication.translate("PEMMerger", u"TextLabel", None))
        self.label_27.setText(QCoreApplication.translate("PEMMerger", u"Sensors:", None))
        self.tools_label_1.setText(QCoreApplication.translate("PEMMerger", u"TextLabel", None))
        self.groupBox_3.setTitle(QCoreApplication.translate("PEMMerger", u"File Information", None))
        self.label_15.setText(QCoreApplication.translate("PEMMerger", u"Rx Number:", None))
        self.rx_num_label_1.setText(QCoreApplication.translate("PEMMerger", u"TextLabel", None))
        self.label_11.setText(QCoreApplication.translate("PEMMerger", u"Date:", None))
        self.date_label_1.setText(QCoreApplication.translate("PEMMerger", u"TextLabel", None))
        self.label_19.setText(QCoreApplication.translate("PEMMerger", u"Ramp:", None))
        self.ramp_label_1.setText(QCoreApplication.translate("PEMMerger", u"TextLabel", None))
        self.label_21.setText(QCoreApplication.translate("PEMMerger", u"Sync Type:", None))
        self.sync_label_1.setText(QCoreApplication.translate("PEMMerger", u"TextLabel", None))
        self.label_14.setText(QCoreApplication.translate("PEMMerger", u"ZTS:", None))
        self.zts_label_1.setText(QCoreApplication.translate("PEMMerger", u"TextLabel", None))
        self.groupBox.setTitle(QCoreApplication.translate("PEMMerger", u"Editing", None))
        self.label.setText(QCoreApplication.translate("PEMMerger", u"Coil Area:", None))
        self.label_3.setText(QCoreApplication.translate("PEMMerger", u"Current:", None))
        self.current_sbox_1.setSuffix(QCoreApplication.translate("PEMMerger", u"A", None))
        self.label_2.setText(QCoreApplication.translate("PEMMerger", u"Factor:", None))
        self.flip_data_btn_1.setText(QCoreApplication.translate("PEMMerger", u"Flip Data", None))
        self.label_28.setText(QCoreApplication.translate("PEMMerger", u"SOA:", None))
        self.file_label_2.setText(QCoreApplication.translate("PEMMerger", u"FileLabel2", None))
        self.groupBox_2.setTitle(QCoreApplication.translate("PEMMerger", u"Header Information", None))
        self.label_17.setText(QCoreApplication.translate("PEMMerger", u"Client:", None))
        self.client_label_2.setText(QCoreApplication.translate("PEMMerger", u"TextLabel", None))
        self.label_18.setText(QCoreApplication.translate("PEMMerger", u"Grid:", None))
        self.grid_label_2.setText(QCoreApplication.translate("PEMMerger", u"TextLabel", None))
        self.label_7.setText(QCoreApplication.translate("PEMMerger", u"Line:", None))
        self.line_label_2.setText(QCoreApplication.translate("PEMMerger", u"TextLabel", None))
        self.label_10.setText(QCoreApplication.translate("PEMMerger", u"Loop:", None))
        self.loop_label_2.setText(QCoreApplication.translate("PEMMerger", u"TextLabel", None))
        self.label_8.setText(QCoreApplication.translate("PEMMerger", u"Operator:", None))
        self.operator_label_2.setText(QCoreApplication.translate("PEMMerger", u"TextLabel", None))
        self.label_29.setText(QCoreApplication.translate("PEMMerger", u"Sensors:", None))
        self.tools_label_2.setText(QCoreApplication.translate("PEMMerger", u"TextLabel", None))
        self.groupBox_4.setTitle(QCoreApplication.translate("PEMMerger", u"File Information", None))
        self.label_20.setText(QCoreApplication.translate("PEMMerger", u"Date:", None))
        self.date_label_2.setText(QCoreApplication.translate("PEMMerger", u"TextLabel", None))
        self.label_22.setText(QCoreApplication.translate("PEMMerger", u"Ramp:", None))
        self.ramp_label_2.setText(QCoreApplication.translate("PEMMerger", u"TextLabel", None))
        self.label_16.setText(QCoreApplication.translate("PEMMerger", u"Rx Number:", None))
        self.rx_num_label_2.setText(QCoreApplication.translate("PEMMerger", u"TextLabel", None))
        self.label_23.setText(QCoreApplication.translate("PEMMerger", u"Sync Type:", None))
        self.sync_label_2.setText(QCoreApplication.translate("PEMMerger", u"TextLabel", None))
        self.label_26.setText(QCoreApplication.translate("PEMMerger", u"ZTS:", None))
        self.zts_label_2.setText(QCoreApplication.translate("PEMMerger", u"TextLabel", None))
        self.groupBox_6.setTitle(QCoreApplication.translate("PEMMerger", u"Editing", None))
        self.label_5.setText(QCoreApplication.translate("PEMMerger", u"Coil Area:", None))
        self.label_6.setText(QCoreApplication.translate("PEMMerger", u"Current:", None))
        self.current_sbox_2.setSuffix(QCoreApplication.translate("PEMMerger", u"A", None))
        self.label_4.setText(QCoreApplication.translate("PEMMerger", u"Factor:", None))
        self.flip_data_btn_2.setText(QCoreApplication.translate("PEMMerger", u"Flip Data", None))
        self.label_30.setText(QCoreApplication.translate("PEMMerger", u"SOA:", None))
        self.menuFile.setTitle(QCoreApplication.translate("PEMMerger", u"File", None))
        self.menuView.setTitle(QCoreApplication.translate("PEMMerger", u"View", None))
    # retranslateUi

