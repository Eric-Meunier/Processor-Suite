# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'plan_map_options.ui'
##
## Created by: Qt User Interface Compiler version 5.15.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide2.QtCore import *
from PySide2.QtGui import *
from PySide2.QtWidgets import *


class Ui_PlanMapOptions(object):
    def setupUi(self, PlanMapOptions):
        if not PlanMapOptions.objectName():
            PlanMapOptions.setObjectName(u"PlanMapOptions")
        PlanMapOptions.resize(269, 336)
        self.gridLayout_4 = QGridLayout(PlanMapOptions)
        self.gridLayout_4.setObjectName(u"gridLayout_4")
        self.verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.gridLayout_4.addItem(self.verticalSpacer, 11, 1, 1, 2)

        self.buttonBox = QDialogButtonBox(PlanMapOptions)
        self.buttonBox.setObjectName(u"buttonBox")
        self.buttonBox.setMinimumSize(QSize(150, 0))
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Ok)
        self.buttonBox.setCenterButtons(True)

        self.gridLayout_4.addWidget(self.buttonBox, 12, 1, 1, 2)

        self.groupBox_2 = QGroupBox(PlanMapOptions)
        self.groupBox_2.setObjectName(u"groupBox_2")
        self.gridLayout = QGridLayout(self.groupBox_2)
        self.gridLayout.setObjectName(u"gridLayout")
        self.loop_labels_cbox = QCheckBox(self.groupBox_2)
        self.loop_labels_cbox.setObjectName(u"loop_labels_cbox")
        self.loop_labels_cbox.setChecked(True)

        self.gridLayout.addWidget(self.loop_labels_cbox, 0, 0, 1, 1)

        self.line_labels_cbox = QCheckBox(self.groupBox_2)
        self.line_labels_cbox.setObjectName(u"line_labels_cbox")
        self.line_labels_cbox.setChecked(True)

        self.gridLayout.addWidget(self.line_labels_cbox, 2, 0, 1, 1)

        self.hole_collar_labels_cbox = QCheckBox(self.groupBox_2)
        self.hole_collar_labels_cbox.setObjectName(u"hole_collar_labels_cbox")
        self.hole_collar_labels_cbox.setChecked(True)

        self.gridLayout.addWidget(self.hole_collar_labels_cbox, 0, 1, 1, 1)

        self.hole_depth_labels_cbox = QCheckBox(self.groupBox_2)
        self.hole_depth_labels_cbox.setObjectName(u"hole_depth_labels_cbox")
        self.hole_depth_labels_cbox.setChecked(True)

        self.gridLayout.addWidget(self.hole_depth_labels_cbox, 2, 1, 1, 1)


        self.gridLayout_4.addWidget(self.groupBox_2, 2, 0, 1, 4)

        self.groupBox_3 = QGroupBox(PlanMapOptions)
        self.groupBox_3.setObjectName(u"groupBox_3")
        self.gridLayout_3 = QGridLayout(self.groupBox_3)
        self.gridLayout_3.setObjectName(u"gridLayout_3")
        self.draw_loops_cbox = QCheckBox(self.groupBox_3)
        self.draw_loops_cbox.setObjectName(u"draw_loops_cbox")
        self.draw_loops_cbox.setChecked(True)

        self.gridLayout_3.addWidget(self.draw_loops_cbox, 0, 0, 1, 1)

        self.draw_hole_collars_cbox = QCheckBox(self.groupBox_3)
        self.draw_hole_collars_cbox.setObjectName(u"draw_hole_collars_cbox")
        self.draw_hole_collars_cbox.setChecked(True)

        self.gridLayout_3.addWidget(self.draw_hole_collars_cbox, 0, 1, 1, 1)

        self.draw_lines_cbox = QCheckBox(self.groupBox_3)
        self.draw_lines_cbox.setObjectName(u"draw_lines_cbox")
        self.draw_lines_cbox.setChecked(True)

        self.gridLayout_3.addWidget(self.draw_lines_cbox, 1, 0, 1, 1)

        self.draw_hole_traces_cbox = QCheckBox(self.groupBox_3)
        self.draw_hole_traces_cbox.setObjectName(u"draw_hole_traces_cbox")
        self.draw_hole_traces_cbox.setChecked(True)

        self.gridLayout_3.addWidget(self.draw_hole_traces_cbox, 1, 1, 1, 1)


        self.gridLayout_4.addWidget(self.groupBox_3, 1, 0, 1, 4)

        self.groupBox = QGroupBox(PlanMapOptions)
        self.groupBox.setObjectName(u"groupBox")
        self.gridLayout_2 = QGridLayout(self.groupBox)
        self.gridLayout_2.setObjectName(u"gridLayout_2")
        self.title_box_cbox = QCheckBox(self.groupBox)
        self.title_box_cbox.setObjectName(u"title_box_cbox")
        self.title_box_cbox.setChecked(True)

        self.gridLayout_2.addWidget(self.title_box_cbox, 0, 0, 1, 1)

        self.grid_cbox = QCheckBox(self.groupBox)
        self.grid_cbox.setObjectName(u"grid_cbox")
        self.grid_cbox.setChecked(True)

        self.gridLayout_2.addWidget(self.grid_cbox, 0, 1, 1, 1)

        self.scale_bar_cbox = QCheckBox(self.groupBox)
        self.scale_bar_cbox.setObjectName(u"scale_bar_cbox")
        self.scale_bar_cbox.setChecked(True)

        self.gridLayout_2.addWidget(self.scale_bar_cbox, 4, 0, 1, 1)

        self.north_arrow_cbox = QCheckBox(self.groupBox)
        self.north_arrow_cbox.setObjectName(u"north_arrow_cbox")
        self.north_arrow_cbox.setChecked(True)

        self.gridLayout_2.addWidget(self.north_arrow_cbox, 4, 1, 1, 1)

        self.legend_cbox = QCheckBox(self.groupBox)
        self.legend_cbox.setObjectName(u"legend_cbox")
        self.legend_cbox.setChecked(True)

        self.gridLayout_2.addWidget(self.legend_cbox, 5, 0, 1, 1)


        self.gridLayout_4.addWidget(self.groupBox, 0, 0, 1, 4)

        self.all_btn = QPushButton(PlanMapOptions)
        self.all_btn.setObjectName(u"all_btn")
        self.all_btn.setMaximumSize(QSize(16777215, 16777215))

        self.gridLayout_4.addWidget(self.all_btn, 4, 0, 1, 2)

        self.none_btn = QPushButton(PlanMapOptions)
        self.none_btn.setObjectName(u"none_btn")
        self.none_btn.setMaximumSize(QSize(16777215, 16777215))

        self.gridLayout_4.addWidget(self.none_btn, 4, 2, 1, 2)

        QWidget.setTabOrder(self.title_box_cbox, self.grid_cbox)
        QWidget.setTabOrder(self.grid_cbox, self.scale_bar_cbox)
        QWidget.setTabOrder(self.scale_bar_cbox, self.north_arrow_cbox)
        QWidget.setTabOrder(self.north_arrow_cbox, self.legend_cbox)
        QWidget.setTabOrder(self.legend_cbox, self.draw_loops_cbox)
        QWidget.setTabOrder(self.draw_loops_cbox, self.draw_hole_collars_cbox)
        QWidget.setTabOrder(self.draw_hole_collars_cbox, self.draw_lines_cbox)
        QWidget.setTabOrder(self.draw_lines_cbox, self.draw_hole_traces_cbox)
        QWidget.setTabOrder(self.draw_hole_traces_cbox, self.loop_labels_cbox)
        QWidget.setTabOrder(self.loop_labels_cbox, self.hole_collar_labels_cbox)
        QWidget.setTabOrder(self.hole_collar_labels_cbox, self.line_labels_cbox)
        QWidget.setTabOrder(self.line_labels_cbox, self.hole_depth_labels_cbox)
        QWidget.setTabOrder(self.hole_depth_labels_cbox, self.all_btn)
        QWidget.setTabOrder(self.all_btn, self.none_btn)

        self.retranslateUi(PlanMapOptions)

        QMetaObject.connectSlotsByName(PlanMapOptions)
    # setupUi

    def retranslateUi(self, PlanMapOptions):
        PlanMapOptions.setWindowTitle(QCoreApplication.translate("PlanMapOptions", u"Form", None))
        self.groupBox_2.setTitle(QCoreApplication.translate("PlanMapOptions", u"Labels", None))
        self.loop_labels_cbox.setText(QCoreApplication.translate("PlanMapOptions", u"Loops", None))
        self.line_labels_cbox.setText(QCoreApplication.translate("PlanMapOptions", u"Lines", None))
        self.hole_collar_labels_cbox.setText(QCoreApplication.translate("PlanMapOptions", u"Hole Collars", None))
        self.hole_depth_labels_cbox.setText(QCoreApplication.translate("PlanMapOptions", u"Hole Depth", None))
        self.groupBox_3.setTitle(QCoreApplication.translate("PlanMapOptions", u"Draw", None))
        self.draw_loops_cbox.setText(QCoreApplication.translate("PlanMapOptions", u"Loops", None))
        self.draw_hole_collars_cbox.setText(QCoreApplication.translate("PlanMapOptions", u"Hole Collars", None))
        self.draw_lines_cbox.setText(QCoreApplication.translate("PlanMapOptions", u"Lines", None))
        self.draw_hole_traces_cbox.setText(QCoreApplication.translate("PlanMapOptions", u"Hole Traces", None))
        self.groupBox.setTitle(QCoreApplication.translate("PlanMapOptions", u"General", None))
        self.title_box_cbox.setText(QCoreApplication.translate("PlanMapOptions", u"Title Box", None))
        self.grid_cbox.setText(QCoreApplication.translate("PlanMapOptions", u"Grid", None))
        self.scale_bar_cbox.setText(QCoreApplication.translate("PlanMapOptions", u"Scale Bar", None))
        self.north_arrow_cbox.setText(QCoreApplication.translate("PlanMapOptions", u"North Arrow", None))
        self.legend_cbox.setText(QCoreApplication.translate("PlanMapOptions", u"Legend", None))
        self.all_btn.setText(QCoreApplication.translate("PlanMapOptions", u"All", None))
        self.none_btn.setText(QCoreApplication.translate("PlanMapOptions", u"None", None))
    # retranslateUi

