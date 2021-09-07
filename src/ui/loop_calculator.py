# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'loop_calculator.ui'
##
## Created by: Qt User Interface Compiler version 5.15.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide2.QtCore import *
from PySide2.QtGui import *
from PySide2.QtWidgets import *

from pyqtgraph import PlotWidget


class Ui_LoopCalculator(object):
    def setupUi(self, LoopCalculator):
        if not LoopCalculator.objectName():
            LoopCalculator.setObjectName(u"LoopCalculator")
        LoopCalculator.resize(773, 606)
        sizePolicy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(LoopCalculator.sizePolicy().hasHeightForWidth())
        LoopCalculator.setSizePolicy(sizePolicy)
        self.centralwidget = QWidget(LoopCalculator)
        self.centralwidget.setObjectName(u"centralwidget")
        sizePolicy.setHeightForWidth(self.centralwidget.sizePolicy().hasHeightForWidth())
        self.centralwidget.setSizePolicy(sizePolicy)
        self.gridLayout = QGridLayout(self.centralwidget)
        self.gridLayout.setObjectName(u"gridLayout")
        self.gridLayout.setContentsMargins(0, 0, 0, 0)
        self.frame_3 = QFrame(self.centralwidget)
        self.frame_3.setObjectName(u"frame_3")
        self.frame_3.setMinimumSize(QSize(100, 0))
        self.frame_3.setFrameShape(QFrame.StyledPanel)
        self.frame_3.setFrameShadow(QFrame.Raised)
        self.horizontalLayout_2 = QGridLayout(self.frame_3)
        self.horizontalLayout_2.setObjectName(u"horizontalLayout_2")
        self.horizontalLayout_2.setContentsMargins(0, 0, 0, 0)
        self.splitter = QSplitter(self.frame_3)
        self.splitter.setObjectName(u"splitter")
        self.splitter.setOrientation(Qt.Horizontal)
        self.splitter.setHandleWidth(2)
        self.frame_2 = QFrame(self.splitter)
        self.frame_2.setObjectName(u"frame_2")
        self.frame_2.setFrameShape(QFrame.StyledPanel)
        self.frame_2.setFrameShadow(QFrame.Plain)
        self.verticalLayout_2 = QVBoxLayout(self.frame_2)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.verticalLayout_2.setContentsMargins(6, 6, 6, 6)
        self.groupBox_5 = QGroupBox(self.frame_2)
        self.groupBox_5.setObjectName(u"groupBox_5")
        self.verticalLayout = QVBoxLayout(self.groupBox_5)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.groupBox_3 = QGroupBox(self.groupBox_5)
        self.groupBox_3.setObjectName(u"groupBox_3")
        sizePolicy1 = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.groupBox_3.sizePolicy().hasHeightForWidth())
        self.groupBox_3.setSizePolicy(sizePolicy1)
        self.groupBox_3.setAlignment(Qt.AlignCenter)
        self.groupBox_3.setFlat(True)
        self.formLayout_4 = QFormLayout(self.groupBox_3)
        self.formLayout_4.setObjectName(u"formLayout_4")
        self.label = QLabel(self.groupBox_3)
        self.label.setObjectName(u"label")

        self.formLayout_4.setWidget(0, QFormLayout.LabelRole, self.label)

        self.tx_setup_combo = QComboBox(self.groupBox_3)
        self.tx_setup_combo.addItem("")
        self.tx_setup_combo.addItem("")
        self.tx_setup_combo.setObjectName(u"tx_setup_combo")

        self.formLayout_4.setWidget(0, QFormLayout.FieldRole, self.tx_setup_combo)

        self.label_7 = QLabel(self.groupBox_3)
        self.label_7.setObjectName(u"label_7")

        self.formLayout_4.setWidget(1, QFormLayout.LabelRole, self.label_7)

        self.ramp_sbox = QDoubleSpinBox(self.groupBox_3)
        self.ramp_sbox.setObjectName(u"ramp_sbox")
        self.ramp_sbox.setDecimals(1)
        self.ramp_sbox.setMinimum(0.500000000000000)
        self.ramp_sbox.setMaximum(1.500000000000000)
        self.ramp_sbox.setSingleStep(0.500000000000000)
        self.ramp_sbox.setValue(1.500000000000000)

        self.formLayout_4.setWidget(1, QFormLayout.FieldRole, self.ramp_sbox)

        self.label_13 = QLabel(self.groupBox_3)
        self.label_13.setObjectName(u"label_13")

        self.formLayout_4.setWidget(2, QFormLayout.LabelRole, self.label_13)

        self.voltage_sbox = QSpinBox(self.groupBox_3)
        self.voltage_sbox.setObjectName(u"voltage_sbox")
        self.voltage_sbox.setMinimum(1)
        self.voltage_sbox.setMaximum(10000)
        self.voltage_sbox.setSingleStep(10)
        self.voltage_sbox.setValue(160)

        self.formLayout_4.setWidget(2, QFormLayout.FieldRole, self.voltage_sbox)

        self.max_voltage_label = QLabel(self.groupBox_3)
        self.max_voltage_label.setObjectName(u"max_voltage_label")
        self.max_voltage_label.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.formLayout_4.setWidget(3, QFormLayout.SpanningRole, self.max_voltage_label)


        self.verticalLayout.addWidget(self.groupBox_3)

        self.groupBox = QGroupBox(self.groupBox_5)
        self.groupBox.setObjectName(u"groupBox")
        sizePolicy1.setHeightForWidth(self.groupBox.sizePolicy().hasHeightForWidth())
        self.groupBox.setSizePolicy(sizePolicy1)
        self.groupBox.setAlignment(Qt.AlignCenter)
        self.groupBox.setFlat(True)
        self.formLayout_3 = QFormLayout(self.groupBox)
        self.formLayout_3.setObjectName(u"formLayout_3")
        self.label_2 = QLabel(self.groupBox)
        self.label_2.setObjectName(u"label_2")

        self.formLayout_3.setWidget(0, QFormLayout.LabelRole, self.label_2)

        self.num_tx_turns_sbox = QSpinBox(self.groupBox)
        self.num_tx_turns_sbox.setObjectName(u"num_tx_turns_sbox")
        self.num_tx_turns_sbox.setMinimumSize(QSize(0, 20))
        self.num_tx_turns_sbox.setMinimum(1)

        self.formLayout_3.setWidget(0, QFormLayout.FieldRole, self.num_tx_turns_sbox)

        self.label_3 = QLabel(self.groupBox)
        self.label_3.setObjectName(u"label_3")

        self.formLayout_3.setWidget(1, QFormLayout.LabelRole, self.label_3)

        self.frame = QFrame(self.groupBox)
        self.frame.setObjectName(u"frame")
        self.frame.setMinimumSize(QSize(0, 0))
        self.frame.setAutoFillBackground(False)
        self.frame.setFrameShape(QFrame.NoFrame)
        self.frame.setFrameShadow(QFrame.Plain)
        self.horizontalLayout = QHBoxLayout(self.frame)
        self.horizontalLayout.setSpacing(6)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.horizontalLayout.setContentsMargins(0, 0, 0, 0)
        self.loop_w_sbox = QSpinBox(self.frame)
        self.loop_w_sbox.setObjectName(u"loop_w_sbox")
        self.loop_w_sbox.setMinimumSize(QSize(0, 0))
        self.loop_w_sbox.setMinimum(1)
        self.loop_w_sbox.setMaximum(10000)
        self.loop_w_sbox.setSingleStep(10)
        self.loop_w_sbox.setValue(400)

        self.horizontalLayout.addWidget(self.loop_w_sbox)

        self.label_4 = QLabel(self.frame)
        self.label_4.setObjectName(u"label_4")
        sizePolicy2 = QSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
        sizePolicy2.setHorizontalStretch(0)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(self.label_4.sizePolicy().hasHeightForWidth())
        self.label_4.setSizePolicy(sizePolicy2)

        self.horizontalLayout.addWidget(self.label_4)

        self.loop_h_sbox = QSpinBox(self.frame)
        self.loop_h_sbox.setObjectName(u"loop_h_sbox")
        self.loop_h_sbox.setMinimumSize(QSize(0, 0))
        self.loop_h_sbox.setFrame(True)
        self.loop_h_sbox.setMinimum(1)
        self.loop_h_sbox.setMaximum(10000)
        self.loop_h_sbox.setSingleStep(10)
        self.loop_h_sbox.setValue(400)

        self.horizontalLayout.addWidget(self.loop_h_sbox)


        self.formLayout_3.setWidget(1, QFormLayout.FieldRole, self.frame)

        self.label_5 = QLabel(self.groupBox)
        self.label_5.setObjectName(u"label_5")

        self.formLayout_3.setWidget(2, QFormLayout.LabelRole, self.label_5)

        self.loop_gauge_sbox = QSpinBox(self.groupBox)
        self.loop_gauge_sbox.setObjectName(u"loop_gauge_sbox")
        self.loop_gauge_sbox.setMinimumSize(QSize(0, 20))
        self.loop_gauge_sbox.setMinimum(8)
        self.loop_gauge_sbox.setMaximum(14)
        self.loop_gauge_sbox.setSingleStep(2)
        self.loop_gauge_sbox.setValue(10)

        self.formLayout_3.setWidget(2, QFormLayout.FieldRole, self.loop_gauge_sbox)

        self.label_6 = QLabel(self.groupBox)
        self.label_6.setObjectName(u"label_6")

        self.formLayout_3.setWidget(3, QFormLayout.LabelRole, self.label_6)

        self.loop_quality_sbox = QSpinBox(self.groupBox)
        self.loop_quality_sbox.setObjectName(u"loop_quality_sbox")
        self.loop_quality_sbox.setMinimumSize(QSize(0, 20))
        self.loop_quality_sbox.setMaximum(100)
        self.loop_quality_sbox.setValue(10)

        self.formLayout_3.setWidget(3, QFormLayout.FieldRole, self.loop_quality_sbox)

        self.line = QFrame(self.groupBox)
        self.line.setObjectName(u"line")
        self.line.setFrameShape(QFrame.HLine)
        self.line.setFrameShadow(QFrame.Sunken)

        self.formLayout_3.setWidget(4, QFormLayout.SpanningRole, self.line)

        self.label_14 = QLabel(self.groupBox)
        self.label_14.setObjectName(u"label_14")

        self.formLayout_3.setWidget(5, QFormLayout.LabelRole, self.label_14)

        self.num_parallel_sbox = QSpinBox(self.groupBox)
        self.num_parallel_sbox.setObjectName(u"num_parallel_sbox")
        self.num_parallel_sbox.setMinimumSize(QSize(0, 20))
        self.num_parallel_sbox.setMinimum(1)

        self.formLayout_3.setWidget(5, QFormLayout.FieldRole, self.num_parallel_sbox)


        self.verticalLayout.addWidget(self.groupBox)


        self.verticalLayout_2.addWidget(self.groupBox_5)

        self.groupBox_2 = QGroupBox(self.frame_2)
        self.groupBox_2.setObjectName(u"groupBox_2")
        sizePolicy1.setHeightForWidth(self.groupBox_2.sizePolicy().hasHeightForWidth())
        self.groupBox_2.setSizePolicy(sizePolicy1)
        self.groupBox_2.setMinimumSize(QSize(100, 100))
        self.groupBox_2.setFlat(False)
        self.formLayout_2 = QFormLayout(self.groupBox_2)
        self.formLayout_2.setObjectName(u"formLayout_2")
        self.label_9 = QLabel(self.groupBox_2)
        self.label_9.setObjectName(u"label_9")

        self.formLayout_2.setWidget(0, QFormLayout.LabelRole, self.label_9)

        self.max_current_voltage_label = QLabel(self.groupBox_2)
        self.max_current_voltage_label.setObjectName(u"max_current_voltage_label")
        self.max_current_voltage_label.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.formLayout_2.setWidget(0, QFormLayout.FieldRole, self.max_current_voltage_label)

        self.label_10 = QLabel(self.groupBox_2)
        self.label_10.setObjectName(u"label_10")

        self.formLayout_2.setWidget(1, QFormLayout.LabelRole, self.label_10)

        self.max_current_inductance_label = QLabel(self.groupBox_2)
        self.max_current_inductance_label.setObjectName(u"max_current_inductance_label")
        self.max_current_inductance_label.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.formLayout_2.setWidget(1, QFormLayout.FieldRole, self.max_current_inductance_label)

        self.label_11 = QLabel(self.groupBox_2)
        self.label_11.setObjectName(u"label_11")

        self.formLayout_2.setWidget(2, QFormLayout.LabelRole, self.label_11)

        self.max_current_power_label = QLabel(self.groupBox_2)
        self.max_current_power_label.setObjectName(u"max_current_power_label")
        self.max_current_power_label.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.formLayout_2.setWidget(2, QFormLayout.FieldRole, self.max_current_power_label)

        self.label_12 = QLabel(self.groupBox_2)
        self.label_12.setObjectName(u"label_12")
        font = QFont()
        font.setBold(True)
        font.setWeight(75)
        self.label_12.setFont(font)

        self.formLayout_2.setWidget(3, QFormLayout.LabelRole, self.label_12)

        self.max_current_label = QLabel(self.groupBox_2)
        self.max_current_label.setObjectName(u"max_current_label")
        self.max_current_label.setFont(font)
        self.max_current_label.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.formLayout_2.setWidget(3, QFormLayout.FieldRole, self.max_current_label)


        self.verticalLayout_2.addWidget(self.groupBox_2)

        self.groupBox_4 = QGroupBox(self.frame_2)
        self.groupBox_4.setObjectName(u"groupBox_4")
        self.formLayout = QFormLayout(self.groupBox_4)
        self.formLayout.setObjectName(u"formLayout")
        self.label_8 = QLabel(self.groupBox_4)
        self.label_8.setObjectName(u"label_8")
        self.label_8.setLayoutDirection(Qt.LeftToRight)
        self.label_8.setAlignment(Qt.AlignLeading|Qt.AlignLeft|Qt.AlignVCenter)

        self.formLayout.setWidget(0, QFormLayout.LabelRole, self.label_8)

        self.current_sbox = QDoubleSpinBox(self.groupBox_4)
        self.current_sbox.setObjectName(u"current_sbox")
        self.current_sbox.setMinimum(1.000000000000000)
        self.current_sbox.setMaximum(100.000000000000000)
        self.current_sbox.setValue(20.000000000000000)

        self.formLayout.setWidget(0, QFormLayout.FieldRole, self.current_sbox)

        self.label_17 = QLabel(self.groupBox_4)
        self.label_17.setObjectName(u"label_17")
        self.label_17.setAlignment(Qt.AlignLeading|Qt.AlignLeft|Qt.AlignVCenter)

        self.formLayout.setWidget(1, QFormLayout.LabelRole, self.label_17)

        self.distance_sbox = QSpinBox(self.groupBox_4)
        self.distance_sbox.setObjectName(u"distance_sbox")
        self.distance_sbox.setMinimum(-1000)
        self.distance_sbox.setMaximum(1000)
        self.distance_sbox.setSingleStep(5)
        self.distance_sbox.setValue(50)

        self.formLayout.setWidget(1, QFormLayout.FieldRole, self.distance_sbox)

        self.label_15 = QLabel(self.groupBox_4)
        self.label_15.setObjectName(u"label_15")
        self.label_15.setFont(font)
        self.label_15.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.formLayout.setWidget(2, QFormLayout.LabelRole, self.label_15)

        self.z_response_label = QLabel(self.groupBox_4)
        self.z_response_label.setObjectName(u"z_response_label")
        self.z_response_label.setFont(font)
        self.z_response_label.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.formLayout.setWidget(2, QFormLayout.FieldRole, self.z_response_label)

        self.label_16 = QLabel(self.groupBox_4)
        self.label_16.setObjectName(u"label_16")
        self.label_16.setFont(font)

        self.formLayout.setWidget(3, QFormLayout.LabelRole, self.label_16)

        self.x_response_label = QLabel(self.groupBox_4)
        self.x_response_label.setObjectName(u"x_response_label")
        self.x_response_label.setFont(font)
        self.x_response_label.setLayoutDirection(Qt.LeftToRight)
        self.x_response_label.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.formLayout.setWidget(3, QFormLayout.FieldRole, self.x_response_label)


        self.verticalLayout_2.addWidget(self.groupBox_4)

        self.verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.verticalLayout_2.addItem(self.verticalSpacer)

        self.splitter.addWidget(self.frame_2)
        self.frame_4 = QFrame(self.splitter)
        self.frame_4.setObjectName(u"frame_4")
        sizePolicy3 = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        sizePolicy3.setHorizontalStretch(1)
        sizePolicy3.setVerticalStretch(0)
        sizePolicy3.setHeightForWidth(self.frame_4.sizePolicy().hasHeightForWidth())
        self.frame_4.setSizePolicy(sizePolicy3)
        self.frame_4.setFrameShape(QFrame.StyledPanel)
        self.frame_4.setFrameShadow(QFrame.Raised)
        self.verticalLayout_3 = QVBoxLayout(self.frame_4)
        self.verticalLayout_3.setSpacing(2)
        self.verticalLayout_3.setObjectName(u"verticalLayout_3")
        self.verticalLayout_3.setContentsMargins(0, 0, 0, 0)
        self.plot_widget = PlotWidget(self.frame_4)
        self.plot_widget.setObjectName(u"plot_widget")
        sizePolicy4 = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        sizePolicy4.setHorizontalStretch(1)
        sizePolicy4.setVerticalStretch(0)
        sizePolicy4.setHeightForWidth(self.plot_widget.sizePolicy().hasHeightForWidth())
        self.plot_widget.setSizePolicy(sizePolicy4)
        self.plot_widget.setFrameShape(QFrame.StyledPanel)
        self.plot_widget.setFrameShadow(QFrame.Plain)

        self.verticalLayout_3.addWidget(self.plot_widget)

        self.plan_widget = PlotWidget(self.frame_4)
        self.plan_widget.setObjectName(u"plan_widget")
        self.plan_widget.setFrameShape(QFrame.StyledPanel)
        self.plan_widget.setFrameShadow(QFrame.Plain)

        self.verticalLayout_3.addWidget(self.plan_widget)

        self.splitter.addWidget(self.frame_4)

        self.horizontalLayout_2.addWidget(self.splitter, 0, 0, 1, 1)


        self.gridLayout.addWidget(self.frame_3, 0, 0, 1, 1)

        LoopCalculator.setCentralWidget(self.centralwidget)
        self.menubar = QMenuBar(LoopCalculator)
        self.menubar.setObjectName(u"menubar")
        self.menubar.setGeometry(QRect(0, 0, 773, 21))
        LoopCalculator.setMenuBar(self.menubar)
        self.statusbar = QStatusBar(LoopCalculator)
        self.statusbar.setObjectName(u"statusbar")
        LoopCalculator.setStatusBar(self.statusbar)

        self.retranslateUi(LoopCalculator)

        QMetaObject.connectSlotsByName(LoopCalculator)
    # setupUi

    def retranslateUi(self, LoopCalculator):
        LoopCalculator.setWindowTitle(QCoreApplication.translate("LoopCalculator", u"MainWindow", None))
        self.groupBox_5.setTitle(QCoreApplication.translate("LoopCalculator", u"Set-up", None))
        self.groupBox_3.setTitle(QCoreApplication.translate("LoopCalculator", u"Transmitter", None))
        self.label.setText(QCoreApplication.translate("LoopCalculator", u"Setup:", None))
        self.tx_setup_combo.setItemText(0, QCoreApplication.translate("LoopCalculator", u"Single", None))
        self.tx_setup_combo.setItemText(1, QCoreApplication.translate("LoopCalculator", u"Series", None))

        self.label_7.setText(QCoreApplication.translate("LoopCalculator", u"Ramp Length:", None))
        self.ramp_sbox.setSuffix(QCoreApplication.translate("LoopCalculator", u"ms", None))
        self.label_13.setText(QCoreApplication.translate("LoopCalculator", u"Voltage:", None))
        self.voltage_sbox.setSuffix(QCoreApplication.translate("LoopCalculator", u"V", None))
        self.max_voltage_label.setText(QCoreApplication.translate("LoopCalculator", u"(Maximum induced voltage: 160V)", None))
        self.groupBox.setTitle(QCoreApplication.translate("LoopCalculator", u"Loop", None))
        self.label_2.setText(QCoreApplication.translate("LoopCalculator", u"Turns:", None))
        self.label_3.setText(QCoreApplication.translate("LoopCalculator", u"Size:", None))
        self.loop_w_sbox.setSuffix(QCoreApplication.translate("LoopCalculator", u"m", None))
        self.label_4.setText(QCoreApplication.translate("LoopCalculator", u"x", None))
        self.loop_h_sbox.setSuffix(QCoreApplication.translate("LoopCalculator", u"m", None))
        self.label_5.setText(QCoreApplication.translate("LoopCalculator", u"Wire Gauge:", None))
        self.label_6.setText(QCoreApplication.translate("LoopCalculator", u"Wire Degradation:", None))
        self.loop_quality_sbox.setSuffix(QCoreApplication.translate("LoopCalculator", u"%", None))
        self.label_14.setText(QCoreApplication.translate("LoopCalculator", u"Number of Loops:", None))
        self.groupBox_2.setTitle(QCoreApplication.translate("LoopCalculator", u"Current Calculations", None))
        self.label_9.setText(QCoreApplication.translate("LoopCalculator", u"Current As Limited By Voltage:", None))
        self.max_current_voltage_label.setText(QCoreApplication.translate("LoopCalculator", u"TextLabel", None))
        self.label_10.setText(QCoreApplication.translate("LoopCalculator", u"Current As Limited By Inductance:", None))
        self.max_current_inductance_label.setText(QCoreApplication.translate("LoopCalculator", u"TextLabel", None))
        self.label_11.setText(QCoreApplication.translate("LoopCalculator", u"Current As Limited By Power:", None))
        self.max_current_power_label.setText(QCoreApplication.translate("LoopCalculator", u"TextLabel", None))
        self.label_12.setText(QCoreApplication.translate("LoopCalculator", u"Maximum Current:", None))
        self.max_current_label.setText(QCoreApplication.translate("LoopCalculator", u"TextLabel", None))
        self.groupBox_4.setTitle(QCoreApplication.translate("LoopCalculator", u"EM Response", None))
        self.label_8.setText(QCoreApplication.translate("LoopCalculator", u"Current:", None))
        self.current_sbox.setSuffix(QCoreApplication.translate("LoopCalculator", u"A", None))
        self.label_17.setText(QCoreApplication.translate("LoopCalculator", u"Easting Position:", None))
        self.distance_sbox.setSuffix(QCoreApplication.translate("LoopCalculator", u"m", None))
        self.label_15.setText(QCoreApplication.translate("LoopCalculator", u"Response (Z-Component):", None))
        self.z_response_label.setText(QCoreApplication.translate("LoopCalculator", u"TextLabel", None))
        self.label_16.setText(QCoreApplication.translate("LoopCalculator", u"Response (X-Component):", None))
        self.x_response_label.setText(QCoreApplication.translate("LoopCalculator", u"TextLabel", None))
    # retranslateUi

