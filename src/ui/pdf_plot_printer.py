# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'pdf_plot_printer.ui'
##
## Created by: Qt User Interface Compiler version 5.15.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide2.QtCore import *
from PySide2.QtGui import *
from PySide2.QtWidgets import *


class Ui_PDFPlotPrinter(object):
    def setupUi(self, PDFPlotPrinter):
        if not PDFPlotPrinter.objectName():
            PDFPlotPrinter.setObjectName(u"PDFPlotPrinter")
        PDFPlotPrinter.resize(283, 449)
        self.gridLayout_2 = QGridLayout(PDFPlotPrinter)
        self.gridLayout_2.setObjectName(u"gridLayout_2")
        self.make_plan_maps_gbox = QGroupBox(PDFPlotPrinter)
        self.make_plan_maps_gbox.setObjectName(u"make_plan_maps_gbox")
        sizePolicy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.make_plan_maps_gbox.sizePolicy().hasHeightForWidth())
        self.make_plan_maps_gbox.setSizePolicy(sizePolicy)
        self.make_plan_maps_gbox.setAlignment(Qt.AlignLeading|Qt.AlignLeft|Qt.AlignVCenter)
        self.make_plan_maps_gbox.setCheckable(True)
        self.gridLayout = QGridLayout(self.make_plan_maps_gbox)
        self.gridLayout.setObjectName(u"gridLayout")
        self.moving_loop_cbox = QCheckBox(self.make_plan_maps_gbox)
        self.moving_loop_cbox.setObjectName(u"moving_loop_cbox")

        self.gridLayout.addWidget(self.moving_loop_cbox, 0, 0, 1, 1)

        self.plan_map_options_btn = QPushButton(self.make_plan_maps_gbox)
        self.plan_map_options_btn.setObjectName(u"plan_map_options_btn")
        sizePolicy1 = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.plan_map_options_btn.sizePolicy().hasHeightForWidth())
        self.plan_map_options_btn.setSizePolicy(sizePolicy1)

        self.gridLayout.addWidget(self.plan_map_options_btn, 3, 0, 1, 2)

        self.show_loop_anno_cbox = QCheckBox(self.make_plan_maps_gbox)
        self.show_loop_anno_cbox.setObjectName(u"show_loop_anno_cbox")

        self.gridLayout.addWidget(self.show_loop_anno_cbox, 0, 1, 1, 1)


        self.gridLayout_2.addWidget(self.make_plan_maps_gbox, 1, 0, 1, 2)

        self.make_profile_plots_gbox = QGroupBox(PDFPlotPrinter)
        self.make_profile_plots_gbox.setObjectName(u"make_profile_plots_gbox")
        sizePolicy.setHeightForWidth(self.make_profile_plots_gbox.sizePolicy().hasHeightForWidth())
        self.make_profile_plots_gbox.setSizePolicy(sizePolicy)
        self.make_profile_plots_gbox.setAlignment(Qt.AlignLeading|Qt.AlignLeft|Qt.AlignVCenter)
        self.make_profile_plots_gbox.setFlat(False)
        self.make_profile_plots_gbox.setCheckable(True)
        self.make_profile_plots_gbox.setChecked(True)
        self.gridLayout_5 = QGridLayout(self.make_profile_plots_gbox)
        self.gridLayout_5.setObjectName(u"gridLayout_5")
        self.share_range_cbox = QGroupBox(self.make_profile_plots_gbox)
        self.share_range_cbox.setObjectName(u"share_range_cbox")
        self.share_range_cbox.setAlignment(Qt.AlignLeading|Qt.AlignLeft|Qt.AlignVCenter)
        self.share_range_cbox.setFlat(True)
        self.share_range_cbox.setCheckable(True)
        self.gridLayout_3 = QGridLayout(self.share_range_cbox)
        self.gridLayout_3.setObjectName(u"gridLayout_3")
        self.max_range_edit = QLineEdit(self.share_range_cbox)
        self.max_range_edit.setObjectName(u"max_range_edit")
        sizePolicy1.setHeightForWidth(self.max_range_edit.sizePolicy().hasHeightForWidth())
        self.max_range_edit.setSizePolicy(sizePolicy1)
        self.max_range_edit.setMinimumSize(QSize(0, 0))
        self.max_range_edit.setMaximumSize(QSize(16777215, 16777215))

        self.gridLayout_3.addWidget(self.max_range_edit, 0, 1, 1, 1)

        self.min_range_label = QLabel(self.share_range_cbox)
        self.min_range_label.setObjectName(u"min_range_label")

        self.gridLayout_3.addWidget(self.min_range_label, 1, 0, 1, 1)

        self.max_range_label = QLabel(self.share_range_cbox)
        self.max_range_label.setObjectName(u"max_range_label")

        self.gridLayout_3.addWidget(self.max_range_label, 0, 0, 1, 1)

        self.min_range_edit = QLineEdit(self.share_range_cbox)
        self.min_range_edit.setObjectName(u"min_range_edit")
        sizePolicy1.setHeightForWidth(self.min_range_edit.sizePolicy().hasHeightForWidth())
        self.min_range_edit.setSizePolicy(sizePolicy1)
        self.min_range_edit.setMinimumSize(QSize(0, 0))
        self.min_range_edit.setMaximumSize(QSize(16777215, 16777215))

        self.gridLayout_3.addWidget(self.min_range_edit, 1, 1, 1, 1)


        self.gridLayout_5.addWidget(self.share_range_cbox, 2, 0, 1, 4)

        self.line = QFrame(self.make_profile_plots_gbox)
        self.line.setObjectName(u"line")
        sizePolicy1.setHeightForWidth(self.line.sizePolicy().hasHeightForWidth())
        self.line.setSizePolicy(sizePolicy1)
        self.line.setFrameShape(QFrame.HLine)
        self.line.setFrameShadow(QFrame.Sunken)

        self.gridLayout_5.addWidget(self.line, 3, 0, 1, 4)

        self.hide_gaps_cbox = QCheckBox(self.make_profile_plots_gbox)
        self.hide_gaps_cbox.setObjectName(u"hide_gaps_cbox")
        sizePolicy1.setHeightForWidth(self.hide_gaps_cbox.sizePolicy().hasHeightForWidth())
        self.hide_gaps_cbox.setSizePolicy(sizePolicy1)
        self.hide_gaps_cbox.setChecked(True)

        self.gridLayout_5.addWidget(self.hide_gaps_cbox, 4, 0, 1, 4)

        self.frame = QFrame(self.make_profile_plots_gbox)
        self.frame.setObjectName(u"frame")
        self.frame.setFrameShape(QFrame.StyledPanel)
        self.frame.setFrameShadow(QFrame.Raised)
        self.horizontalLayout = QHBoxLayout(self.frame)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.horizontalLayout.setContentsMargins(0, 0, 0, 0)
        self.output_lin_cbox = QCheckBox(self.frame)
        self.output_lin_cbox.setObjectName(u"output_lin_cbox")
        self.output_lin_cbox.setChecked(True)

        self.horizontalLayout.addWidget(self.output_lin_cbox)

        self.output_log_cbox = QCheckBox(self.frame)
        self.output_log_cbox.setObjectName(u"output_log_cbox")
        self.output_log_cbox.setChecked(True)
        self.output_log_cbox.setTristate(False)

        self.horizontalLayout.addWidget(self.output_log_cbox)

        self.output_step_cbox = QCheckBox(self.frame)
        self.output_step_cbox.setObjectName(u"output_step_cbox")
        self.output_step_cbox.setChecked(True)

        self.horizontalLayout.addWidget(self.output_step_cbox)


        self.gridLayout_5.addWidget(self.frame, 0, 0, 1, 4)


        self.gridLayout_2.addWidget(self.make_profile_plots_gbox, 0, 0, 1, 2)

        self.make_section_plots_gbox = QGroupBox(PDFPlotPrinter)
        self.make_section_plots_gbox.setObjectName(u"make_section_plots_gbox")
        sizePolicy.setHeightForWidth(self.make_section_plots_gbox.sizePolicy().hasHeightForWidth())
        self.make_section_plots_gbox.setSizePolicy(sizePolicy)
        self.make_section_plots_gbox.setAlignment(Qt.AlignLeading|Qt.AlignLeft|Qt.AlignVCenter)
        self.make_section_plots_gbox.setFlat(False)
        self.make_section_plots_gbox.setCheckable(True)
        self.formLayout = QFormLayout(self.make_section_plots_gbox)
        self.formLayout.setObjectName(u"formLayout")
        self.label_4 = QLabel(self.make_section_plots_gbox)
        self.label_4.setObjectName(u"label_4")

        self.formLayout.setWidget(2, QFormLayout.LabelRole, self.label_4)

        self.label_section_depths_cbox = QCheckBox(self.make_section_plots_gbox)
        self.label_section_depths_cbox.setObjectName(u"label_section_depths_cbox")

        self.formLayout.setWidget(1, QFormLayout.SpanningRole, self.label_section_depths_cbox)

        self.section_depth_edit = QLineEdit(self.make_section_plots_gbox)
        self.section_depth_edit.setObjectName(u"section_depth_edit")

        self.formLayout.setWidget(2, QFormLayout.FieldRole, self.section_depth_edit)


        self.gridLayout_2.addWidget(self.make_section_plots_gbox, 2, 0, 1, 2)

        self.print_btn = QPushButton(PDFPlotPrinter)
        self.print_btn.setObjectName(u"print_btn")

        self.gridLayout_2.addWidget(self.print_btn, 4, 0, 1, 1)

        self.cancel_btn = QPushButton(PDFPlotPrinter)
        self.cancel_btn.setObjectName(u"cancel_btn")

        self.gridLayout_2.addWidget(self.cancel_btn, 4, 1, 1, 1)

        self.groupBox = QGroupBox(PDFPlotPrinter)
        self.groupBox.setObjectName(u"groupBox")
        self.gridLayout_4 = QGridLayout(self.groupBox)
        self.gridLayout_4.setObjectName(u"gridLayout_4")
        self.save_path_edit = QLineEdit(self.groupBox)
        self.save_path_edit.setObjectName(u"save_path_edit")

        self.gridLayout_4.addWidget(self.save_path_edit, 0, 0, 1, 1)

        self.change_save_path_btn = QPushButton(self.groupBox)
        self.change_save_path_btn.setObjectName(u"change_save_path_btn")
        sizePolicy2 = QSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        sizePolicy2.setHorizontalStretch(0)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(self.change_save_path_btn.sizePolicy().hasHeightForWidth())
        self.change_save_path_btn.setSizePolicy(sizePolicy2)
        self.change_save_path_btn.setMaximumSize(QSize(50, 16777215))

        self.gridLayout_4.addWidget(self.change_save_path_btn, 0, 1, 1, 1)


        self.gridLayout_2.addWidget(self.groupBox, 3, 0, 1, 2)

        QWidget.setTabOrder(self.print_btn, self.cancel_btn)
        QWidget.setTabOrder(self.cancel_btn, self.make_profile_plots_gbox)
        QWidget.setTabOrder(self.make_profile_plots_gbox, self.output_lin_cbox)
        QWidget.setTabOrder(self.output_lin_cbox, self.output_log_cbox)
        QWidget.setTabOrder(self.output_log_cbox, self.output_step_cbox)
        QWidget.setTabOrder(self.output_step_cbox, self.share_range_cbox)
        QWidget.setTabOrder(self.share_range_cbox, self.max_range_edit)
        QWidget.setTabOrder(self.max_range_edit, self.min_range_edit)
        QWidget.setTabOrder(self.min_range_edit, self.hide_gaps_cbox)
        QWidget.setTabOrder(self.hide_gaps_cbox, self.make_plan_maps_gbox)
        QWidget.setTabOrder(self.make_plan_maps_gbox, self.moving_loop_cbox)
        QWidget.setTabOrder(self.moving_loop_cbox, self.show_loop_anno_cbox)
        QWidget.setTabOrder(self.show_loop_anno_cbox, self.plan_map_options_btn)
        QWidget.setTabOrder(self.plan_map_options_btn, self.make_section_plots_gbox)
        QWidget.setTabOrder(self.make_section_plots_gbox, self.label_section_depths_cbox)
        QWidget.setTabOrder(self.label_section_depths_cbox, self.section_depth_edit)
        QWidget.setTabOrder(self.section_depth_edit, self.save_path_edit)
        QWidget.setTabOrder(self.save_path_edit, self.change_save_path_btn)

        self.retranslateUi(PDFPlotPrinter)

        QMetaObject.connectSlotsByName(PDFPlotPrinter)
    # setupUi

    def retranslateUi(self, PDFPlotPrinter):
        PDFPlotPrinter.setWindowTitle(QCoreApplication.translate("PDFPlotPrinter", u"Form", None))
#if QT_CONFIG(statustip)
        self.make_plan_maps_gbox.setStatusTip(QCoreApplication.translate("PDFPlotPrinter", u"Create plan maps", None))
#endif // QT_CONFIG(statustip)
        self.make_plan_maps_gbox.setTitle(QCoreApplication.translate("PDFPlotPrinter", u"Plan Map", None))
#if QT_CONFIG(statustip)
        self.moving_loop_cbox.setStatusTip(QCoreApplication.translate("PDFPlotPrinter", u"If the survey is a moving-loop survey", None))
#endif // QT_CONFIG(statustip)
        self.moving_loop_cbox.setText(QCoreApplication.translate("PDFPlotPrinter", u"Moving Loop", None))
        self.plan_map_options_btn.setText(QCoreApplication.translate("PDFPlotPrinter", u"More Options", None))
#if QT_CONFIG(statustip)
        self.show_loop_anno_cbox.setStatusTip(QCoreApplication.translate("PDFPlotPrinter", u"Show loop annotation numbers", None))
#endif // QT_CONFIG(statustip)
        self.show_loop_anno_cbox.setText(QCoreApplication.translate("PDFPlotPrinter", u"Loop Annotations", None))
#if QT_CONFIG(statustip)
        self.make_profile_plots_gbox.setStatusTip(QCoreApplication.translate("PDFPlotPrinter", u"Create profile (LIN, LOG, STEP) plots", None))
#endif // QT_CONFIG(statustip)
        self.make_profile_plots_gbox.setTitle(QCoreApplication.translate("PDFPlotPrinter", u"Profile Plots", None))
#if QT_CONFIG(statustip)
        self.share_range_cbox.setStatusTip(QCoreApplication.translate("PDFPlotPrinter", u"All profile plots will have the same X-axis range", None))
#endif // QT_CONFIG(statustip)
        self.share_range_cbox.setTitle(QCoreApplication.translate("PDFPlotPrinter", u"Share Range", None))
        self.min_range_label.setText(QCoreApplication.translate("PDFPlotPrinter", u"Min", None))
        self.max_range_label.setText(QCoreApplication.translate("PDFPlotPrinter", u"Max", None))
#if QT_CONFIG(statustip)
        self.hide_gaps_cbox.setStatusTip(QCoreApplication.translate("PDFPlotPrinter", u"Don't plot anything where there are large gaps in data", None))
#endif // QT_CONFIG(statustip)
        self.hide_gaps_cbox.setText(QCoreApplication.translate("PDFPlotPrinter", u"Hide Data Gaps", None))
#if QT_CONFIG(statustip)
        self.output_lin_cbox.setStatusTip(QCoreApplication.translate("PDFPlotPrinter", u"Create LIN plots", None))
#endif // QT_CONFIG(statustip)
        self.output_lin_cbox.setText(QCoreApplication.translate("PDFPlotPrinter", u"LIN Plot", None))
#if QT_CONFIG(statustip)
        self.output_log_cbox.setStatusTip(QCoreApplication.translate("PDFPlotPrinter", u"Create LOG plots", None))
#endif // QT_CONFIG(statustip)
        self.output_log_cbox.setText(QCoreApplication.translate("PDFPlotPrinter", u"LOG Plot", None))
#if QT_CONFIG(statustip)
        self.output_step_cbox.setStatusTip(QCoreApplication.translate("PDFPlotPrinter", u"Create STEP plots (only if RI files are included)", None))
#endif // QT_CONFIG(statustip)
        self.output_step_cbox.setText(QCoreApplication.translate("PDFPlotPrinter", u"STEP Plot", None))
#if QT_CONFIG(statustip)
        self.make_section_plots_gbox.setStatusTip(QCoreApplication.translate("PDFPlotPrinter", u"Create section plots", None))
#endif // QT_CONFIG(statustip)
        self.make_section_plots_gbox.setTitle(QCoreApplication.translate("PDFPlotPrinter", u"Section Plots", None))
#if QT_CONFIG(tooltip)
        self.label_4.setToolTip(QCoreApplication.translate("PDFPlotPrinter", u"<html><head/><body><p>The azimuth of the section plot will be the azimuth at this hole depth.</p></body></html>", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(statustip)
        self.label_4.setStatusTip(QCoreApplication.translate("PDFPlotPrinter", u"The depth of the hole to use as the intersection of the section plot", None))
#endif // QT_CONFIG(statustip)
        self.label_4.setText(QCoreApplication.translate("PDFPlotPrinter", u"Hole Depth (Optional):", None))
#if QT_CONFIG(statustip)
        self.label_section_depths_cbox.setStatusTip(QCoreApplication.translate("PDFPlotPrinter", u"Add depth labels down the hole", None))
#endif // QT_CONFIG(statustip)
        self.label_section_depths_cbox.setText(QCoreApplication.translate("PDFPlotPrinter", u"Label Ticks", None))
#if QT_CONFIG(tooltip)
        self.section_depth_edit.setToolTip(QCoreApplication.translate("PDFPlotPrinter", u"<html><head/><body><p>The azimuth of the section plot will be the azimuth at this hole depth.</p></body></html>", None))
#endif // QT_CONFIG(tooltip)
        self.print_btn.setText(QCoreApplication.translate("PDFPlotPrinter", u"Print", None))
        self.cancel_btn.setText(QCoreApplication.translate("PDFPlotPrinter", u"Cancel", None))
        self.groupBox.setTitle(QCoreApplication.translate("PDFPlotPrinter", u"Save File", None))
        self.change_save_path_btn.setText(QCoreApplication.translate("PDFPlotPrinter", u"...", None))
    # retranslateUi

