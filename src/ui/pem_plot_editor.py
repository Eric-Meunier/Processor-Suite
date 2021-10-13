# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'pem_plot_editor.ui'
##
## Created by: Qt User Interface Compiler version 5.15.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide2.QtCore import *
from PySide2.QtGui import *
from PySide2.QtWidgets import *

from pyqtgraph import GraphicsLayoutWidget


class Ui_PEMPlotEditor(object):
    def setupUi(self, PEMPlotEditor):
        if not PEMPlotEditor.objectName():
            PEMPlotEditor.setObjectName(u"PEMPlotEditor")
        PEMPlotEditor.resize(1126, 867)
        PEMPlotEditor.setDocumentMode(False)
        self.actionSave = QAction(PEMPlotEditor)
        self.actionSave.setObjectName(u"actionSave")
        self.actionSave_As = QAction(PEMPlotEditor)
        self.actionSave_As.setObjectName(u"actionSave_As")
        self.actionOpen = QAction(PEMPlotEditor)
        self.actionOpen.setObjectName(u"actionOpen")
        self.actionReset_File = QAction(PEMPlotEditor)
        self.actionReset_File.setObjectName(u"actionReset_File")
        self.actionCopy_Screenshot = QAction(PEMPlotEditor)
        self.actionCopy_Screenshot.setObjectName(u"actionCopy_Screenshot")
        self.actionSave_Screenshot = QAction(PEMPlotEditor)
        self.actionSave_Screenshot.setObjectName(u"actionSave_Screenshot")
        self.actionUn_Delete_All = QAction(PEMPlotEditor)
        self.actionUn_Delete_All.setObjectName(u"actionUn_Delete_All")
        self.centralwidget = QWidget(PEMPlotEditor)
        self.centralwidget.setObjectName(u"centralwidget")
        self.horizontalLayout_3 = QHBoxLayout(self.centralwidget)
        self.horizontalLayout_3.setSpacing(0)
        self.horizontalLayout_3.setObjectName(u"horizontalLayout_3")
        self.horizontalLayout_3.setContentsMargins(0, 0, 0, 0)
        self.frame_7 = QFrame(self.centralwidget)
        self.frame_7.setObjectName(u"frame_7")
        self.frame_7.setFrameShape(QFrame.StyledPanel)
        self.frame_7.setFrameShadow(QFrame.Plain)
        self.verticalLayout_4 = QVBoxLayout(self.frame_7)
        self.verticalLayout_4.setObjectName(u"verticalLayout_4")
        self.verticalLayout_4.setContentsMargins(6, 6, 6, 6)
        self.label = QLabel(self.frame_7)
        self.label.setObjectName(u"label")
        font = QFont()
        font.setPointSize(8)
        font.setBold(True)
        font.setWeight(75)
        self.label.setFont(font)

        self.verticalLayout_4.addWidget(self.label, 0, Qt.AlignHCenter)

        self.groupBox_5 = QGroupBox(self.frame_7)
        self.groupBox_5.setObjectName(u"groupBox_5")
        self.groupBox_5.setMinimumSize(QSize(0, 24))
        self.groupBox_5.setAlignment(Qt.AlignCenter)
        self.groupBox_5.setFlat(False)
        self.verticalLayout_7 = QVBoxLayout(self.groupBox_5)
        self.verticalLayout_7.setObjectName(u"verticalLayout_7")
        self.verticalLayout_7.setContentsMargins(9, 9, 9, 9)
        self.plot_ontime_decays_cbox = QCheckBox(self.groupBox_5)
        self.plot_ontime_decays_cbox.setObjectName(u"plot_ontime_decays_cbox")
        self.plot_ontime_decays_cbox.setFocusPolicy(Qt.NoFocus)
        self.plot_ontime_decays_cbox.setChecked(True)

        self.verticalLayout_7.addWidget(self.plot_ontime_decays_cbox)

        self.plot_auto_clean_lines_cbox = QCheckBox(self.groupBox_5)
        self.plot_auto_clean_lines_cbox.setObjectName(u"plot_auto_clean_lines_cbox")
        self.plot_auto_clean_lines_cbox.setChecked(True)

        self.verticalLayout_7.addWidget(self.plot_auto_clean_lines_cbox)

        self.line_2 = QFrame(self.groupBox_5)
        self.line_2.setObjectName(u"line_2")
        self.line_2.setFrameShape(QFrame.HLine)
        self.line_2.setFrameShadow(QFrame.Sunken)

        self.verticalLayout_7.addWidget(self.line_2)

        self.link_x_cbox = QCheckBox(self.groupBox_5)
        self.link_x_cbox.setObjectName(u"link_x_cbox")
        self.link_x_cbox.setFocusPolicy(Qt.NoFocus)
        self.link_x_cbox.setChecked(True)

        self.verticalLayout_7.addWidget(self.link_x_cbox)

        self.link_y_cbox = QCheckBox(self.groupBox_5)
        self.link_y_cbox.setObjectName(u"link_y_cbox")
        self.link_y_cbox.setFocusPolicy(Qt.NoFocus)
        self.link_y_cbox.setChecked(True)

        self.verticalLayout_7.addWidget(self.link_y_cbox)

        self.auto_range_cbox = QCheckBox(self.groupBox_5)
        self.auto_range_cbox.setObjectName(u"auto_range_cbox")
        self.auto_range_cbox.setFocusPolicy(Qt.NoFocus)
        self.auto_range_cbox.setChecked(False)

        self.verticalLayout_7.addWidget(self.auto_range_cbox)

        self.zoom_to_offtime_btn = QPushButton(self.groupBox_5)
        self.zoom_to_offtime_btn.setObjectName(u"zoom_to_offtime_btn")
        self.zoom_to_offtime_btn.setFocusPolicy(Qt.NoFocus)
        self.zoom_to_offtime_btn.setFlat(False)

        self.verticalLayout_7.addWidget(self.zoom_to_offtime_btn)


        self.verticalLayout_4.addWidget(self.groupBox_5)

        self.groupBox_6 = QGroupBox(self.frame_7)
        self.groupBox_6.setObjectName(u"groupBox_6")
        self.groupBox_6.setAlignment(Qt.AlignCenter)
        self.verticalLayout_8 = QVBoxLayout(self.groupBox_6)
        self.verticalLayout_8.setObjectName(u"verticalLayout_8")
        self.verticalLayout_8.setContentsMargins(9, 9, 9, 9)
        self.change_comp_decay_btn = QPushButton(self.groupBox_6)
        self.change_comp_decay_btn.setObjectName(u"change_comp_decay_btn")
        self.change_comp_decay_btn.setEnabled(False)
        self.change_comp_decay_btn.setFocusPolicy(Qt.NoFocus)

        self.verticalLayout_8.addWidget(self.change_comp_decay_btn)

        self.change_decay_suffix_btn = QPushButton(self.groupBox_6)
        self.change_decay_suffix_btn.setObjectName(u"change_decay_suffix_btn")
        self.change_decay_suffix_btn.setEnabled(False)
        self.change_decay_suffix_btn.setFocusPolicy(Qt.NoFocus)

        self.verticalLayout_8.addWidget(self.change_decay_suffix_btn)

        self.change_station_decay_btn = QPushButton(self.groupBox_6)
        self.change_station_decay_btn.setObjectName(u"change_station_decay_btn")
        self.change_station_decay_btn.setEnabled(False)
        self.change_station_decay_btn.setFocusPolicy(Qt.NoFocus)

        self.verticalLayout_8.addWidget(self.change_station_decay_btn)

        self.flip_decay_btn = QPushButton(self.groupBox_6)
        self.flip_decay_btn.setObjectName(u"flip_decay_btn")
        self.flip_decay_btn.setEnabled(False)
        self.flip_decay_btn.setFocusPolicy(Qt.NoFocus)

        self.verticalLayout_8.addWidget(self.flip_decay_btn)


        self.verticalLayout_4.addWidget(self.groupBox_6)

        self.verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.verticalLayout_4.addItem(self.verticalSpacer)


        self.horizontalLayout_3.addWidget(self.frame_7)

        self.frame_4 = QFrame(self.centralwidget)
        self.frame_4.setObjectName(u"frame_4")
        self.frame_4.setFrameShape(QFrame.NoFrame)
        self.frame_4.setFrameShadow(QFrame.Plain)
        self.verticalLayout_5 = QVBoxLayout(self.frame_4)
        self.verticalLayout_5.setObjectName(u"verticalLayout_5")
        self.verticalLayout_5.setContentsMargins(0, 0, 0, 0)

        self.horizontalLayout_3.addWidget(self.frame_4)

        self.frame_2 = QFrame(self.centralwidget)
        self.frame_2.setObjectName(u"frame_2")
        self.frame_2.setFrameShape(QFrame.NoFrame)
        self.frame_2.setFrameShadow(QFrame.Plain)
        self.verticalLayout_6 = QVBoxLayout(self.frame_2)
        self.verticalLayout_6.setObjectName(u"verticalLayout_6")
        self.verticalLayout_6.setContentsMargins(0, 0, 0, 0)

        self.horizontalLayout_3.addWidget(self.frame_2)

        self.frame_3 = QFrame(self.centralwidget)
        self.frame_3.setObjectName(u"frame_3")
        self.frame_3.setFrameShape(QFrame.StyledPanel)
        self.frame_3.setFrameShadow(QFrame.Plain)
        self.horizontalLayout = QHBoxLayout(self.frame_3)
        self.horizontalLayout.setSpacing(0)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.horizontalLayout.setContentsMargins(0, 0, 0, 0)
        self.decay_layout = GraphicsLayoutWidget(self.frame_3)
        self.decay_layout.setObjectName(u"decay_layout")
        self.decay_layout.setFrameShape(QFrame.NoFrame)
        self.decay_layout.setFrameShadow(QFrame.Plain)
        self.decay_layout.setLineWidth(1)

        self.horizontalLayout.addWidget(self.decay_layout)

        self.profile_tab_widget = QStackedWidget(self.frame_3)
        self.profile_tab_widget.setObjectName(u"profile_tab_widget")
        self.x_profile_widget = QWidget()
        self.x_profile_widget.setObjectName(u"x_profile_widget")
        self.verticalLayout = QVBoxLayout(self.x_profile_widget)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.x_profile_layout = GraphicsLayoutWidget(self.x_profile_widget)
        self.x_profile_layout.setObjectName(u"x_profile_layout")
        self.x_profile_layout.setFrameShape(QFrame.NoFrame)
        self.x_profile_layout.setFrameShadow(QFrame.Plain)

        self.verticalLayout.addWidget(self.x_profile_layout)

        self.profile_tab_widget.addWidget(self.x_profile_widget)
        self.y_profile_widget = QWidget()
        self.y_profile_widget.setObjectName(u"y_profile_widget")
        self.verticalLayout_2 = QVBoxLayout(self.y_profile_widget)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.verticalLayout_2.setContentsMargins(0, 0, 0, 0)
        self.y_profile_layout = GraphicsLayoutWidget(self.y_profile_widget)
        self.y_profile_layout.setObjectName(u"y_profile_layout")
        self.y_profile_layout.setFrameShape(QFrame.NoFrame)

        self.verticalLayout_2.addWidget(self.y_profile_layout)

        self.profile_tab_widget.addWidget(self.y_profile_widget)
        self.z_profile_widget = QWidget()
        self.z_profile_widget.setObjectName(u"z_profile_widget")
        self.verticalLayout_3 = QVBoxLayout(self.z_profile_widget)
        self.verticalLayout_3.setObjectName(u"verticalLayout_3")
        self.verticalLayout_3.setContentsMargins(0, 0, 0, 0)
        self.z_profile_layout = GraphicsLayoutWidget(self.z_profile_widget)
        self.z_profile_layout.setObjectName(u"z_profile_layout")
        self.z_profile_layout.setFrameShape(QFrame.NoFrame)

        self.verticalLayout_3.addWidget(self.z_profile_layout)

        self.profile_tab_widget.addWidget(self.z_profile_widget)

        self.horizontalLayout.addWidget(self.profile_tab_widget)


        self.horizontalLayout_3.addWidget(self.frame_3)

        self.frame = QFrame(self.centralwidget)
        self.frame.setObjectName(u"frame")
        self.frame.setFrameShape(QFrame.StyledPanel)
        self.frame.setFrameShadow(QFrame.Plain)
        self.frame.setMidLineWidth(0)
        self.verticalLayout_11 = QVBoxLayout(self.frame)
        self.verticalLayout_11.setObjectName(u"verticalLayout_11")
        self.verticalLayout_11.setContentsMargins(6, 6, 6, 6)
        self.label_2 = QLabel(self.frame)
        self.label_2.setObjectName(u"label_2")
        self.label_2.setFont(font)

        self.verticalLayout_11.addWidget(self.label_2, 0, Qt.AlignHCenter)

        self.groupBox = QGroupBox(self.frame)
        self.groupBox.setObjectName(u"groupBox")
        self.groupBox.setMaximumSize(QSize(16777215, 16777215))
        self.groupBox.setAlignment(Qt.AlignCenter)
        self.verticalLayout_10 = QVBoxLayout(self.groupBox)
        self.verticalLayout_10.setObjectName(u"verticalLayout_10")
        self.verticalLayout_10.setContentsMargins(9, 9, 9, 9)
        self.plot_mag_cbox = QCheckBox(self.groupBox)
        self.plot_mag_cbox.setObjectName(u"plot_mag_cbox")
        self.plot_mag_cbox.setChecked(True)

        self.verticalLayout_10.addWidget(self.plot_mag_cbox)

        self.line_3 = QFrame(self.groupBox)
        self.line_3.setObjectName(u"line_3")
        self.line_3.setFrameShape(QFrame.HLine)
        self.line_3.setFrameShadow(QFrame.Sunken)

        self.verticalLayout_10.addWidget(self.line_3)

        self.show_scatter_cbox = QCheckBox(self.groupBox)
        self.show_scatter_cbox.setObjectName(u"show_scatter_cbox")
        self.show_scatter_cbox.setFocusPolicy(Qt.NoFocus)
        self.show_scatter_cbox.setChecked(True)

        self.verticalLayout_10.addWidget(self.show_scatter_cbox)


        self.verticalLayout_11.addWidget(self.groupBox)

        self.groupBox_3 = QGroupBox(self.frame)
        self.groupBox_3.setObjectName(u"groupBox_3")
        self.groupBox_3.setAlignment(Qt.AlignCenter)
        self.verticalLayout_9 = QVBoxLayout(self.groupBox_3)
        self.verticalLayout_9.setObjectName(u"verticalLayout_9")
        self.verticalLayout_9.setContentsMargins(9, 9, 9, 9)
        self.change_comp_profile_btn = QPushButton(self.groupBox_3)
        self.change_comp_profile_btn.setObjectName(u"change_comp_profile_btn")
        self.change_comp_profile_btn.setEnabled(False)
        self.change_comp_profile_btn.setFocusPolicy(Qt.NoFocus)

        self.verticalLayout_9.addWidget(self.change_comp_profile_btn)

        self.change_profile_suffix_btn = QPushButton(self.groupBox_3)
        self.change_profile_suffix_btn.setObjectName(u"change_profile_suffix_btn")
        self.change_profile_suffix_btn.setEnabled(False)
        self.change_profile_suffix_btn.setFocusPolicy(Qt.NoFocus)

        self.verticalLayout_9.addWidget(self.change_profile_suffix_btn)

        self.shift_station_profile_btn = QPushButton(self.groupBox_3)
        self.shift_station_profile_btn.setObjectName(u"shift_station_profile_btn")
        self.shift_station_profile_btn.setEnabled(False)
        self.shift_station_profile_btn.setFocusPolicy(Qt.NoFocus)

        self.verticalLayout_9.addWidget(self.shift_station_profile_btn)

        self.flip_profile_btn = QPushButton(self.groupBox_3)
        self.flip_profile_btn.setObjectName(u"flip_profile_btn")
        self.flip_profile_btn.setEnabled(False)
        self.flip_profile_btn.setFocusPolicy(Qt.NoFocus)

        self.verticalLayout_9.addWidget(self.flip_profile_btn)

        self.line = QFrame(self.groupBox_3)
        self.line.setObjectName(u"line")
        self.line.setFrameShape(QFrame.HLine)
        self.line.setFrameShadow(QFrame.Sunken)

        self.verticalLayout_9.addWidget(self.line)

        self.remove_profile_btn = QPushButton(self.groupBox_3)
        self.remove_profile_btn.setObjectName(u"remove_profile_btn")
        self.remove_profile_btn.setEnabled(False)
        self.remove_profile_btn.setFocusPolicy(Qt.NoFocus)

        self.verticalLayout_9.addWidget(self.remove_profile_btn)


        self.verticalLayout_11.addWidget(self.groupBox_3)

        self.groupBox_2 = QGroupBox(self.frame)
        self.groupBox_2.setObjectName(u"groupBox_2")
        self.groupBox_2.setAlignment(Qt.AlignCenter)
        self.verticalLayout_12 = QVBoxLayout(self.groupBox_2)
        self.verticalLayout_12.setObjectName(u"verticalLayout_12")
        self.label_3 = QLabel(self.groupBox_2)
        self.label_3.setObjectName(u"label_3")

        self.verticalLayout_12.addWidget(self.label_3)

        self.auto_clean_std_sbox = QDoubleSpinBox(self.groupBox_2)
        self.auto_clean_std_sbox.setObjectName(u"auto_clean_std_sbox")
        self.auto_clean_std_sbox.setDecimals(1)
        self.auto_clean_std_sbox.setMinimum(0.100000000000000)
        self.auto_clean_std_sbox.setSingleStep(1.000000000000000)

        self.verticalLayout_12.addWidget(self.auto_clean_std_sbox)

        self.label_4 = QLabel(self.groupBox_2)
        self.label_4.setObjectName(u"label_4")

        self.verticalLayout_12.addWidget(self.label_4)

        self.auto_clean_window_sbox = QSpinBox(self.groupBox_2)
        self.auto_clean_window_sbox.setObjectName(u"auto_clean_window_sbox")
        self.auto_clean_window_sbox.setMinimum(2)
        self.auto_clean_window_sbox.setValue(5)

        self.verticalLayout_12.addWidget(self.auto_clean_window_sbox)

        self.auto_clean_btn = QPushButton(self.groupBox_2)
        self.auto_clean_btn.setObjectName(u"auto_clean_btn")
        self.auto_clean_btn.setFocusPolicy(Qt.NoFocus)

        self.verticalLayout_12.addWidget(self.auto_clean_btn)


        self.verticalLayout_11.addWidget(self.groupBox_2)

        self.verticalSpacer_2 = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.verticalLayout_11.addItem(self.verticalSpacer_2)


        self.horizontalLayout_3.addWidget(self.frame)

        PEMPlotEditor.setCentralWidget(self.centralwidget)
        self.menubar = QMenuBar(PEMPlotEditor)
        self.menubar.setObjectName(u"menubar")
        self.menubar.setGeometry(QRect(0, 0, 1126, 21))
        self.menuFile = QMenu(self.menubar)
        self.menuFile.setObjectName(u"menuFile")
        PEMPlotEditor.setMenuBar(self.menubar)
        self.status_bar = QStatusBar(PEMPlotEditor)
        self.status_bar.setObjectName(u"status_bar")
        self.status_bar.setStyleSheet(u"QStatusBar::item{border:None}")
        self.status_bar.setSizeGripEnabled(False)
        PEMPlotEditor.setStatusBar(self.status_bar)
        QWidget.setTabOrder(self.y_profile_layout, self.decay_layout)
        QWidget.setTabOrder(self.decay_layout, self.zoom_to_offtime_btn)
        QWidget.setTabOrder(self.zoom_to_offtime_btn, self.change_comp_decay_btn)
        QWidget.setTabOrder(self.change_comp_decay_btn, self.change_decay_suffix_btn)
        QWidget.setTabOrder(self.change_decay_suffix_btn, self.change_station_decay_btn)
        QWidget.setTabOrder(self.change_station_decay_btn, self.flip_decay_btn)
        QWidget.setTabOrder(self.flip_decay_btn, self.change_comp_profile_btn)
        QWidget.setTabOrder(self.change_comp_profile_btn, self.change_profile_suffix_btn)
        QWidget.setTabOrder(self.change_profile_suffix_btn, self.shift_station_profile_btn)
        QWidget.setTabOrder(self.shift_station_profile_btn, self.flip_profile_btn)
        QWidget.setTabOrder(self.flip_profile_btn, self.remove_profile_btn)
        QWidget.setTabOrder(self.remove_profile_btn, self.z_profile_layout)
        QWidget.setTabOrder(self.z_profile_layout, self.x_profile_layout)

        self.menubar.addAction(self.menuFile.menuAction())
        self.menuFile.addAction(self.actionSave)
        self.menuFile.addAction(self.actionSave_As)
        self.menuFile.addSeparator()
        self.menuFile.addAction(self.actionCopy_Screenshot)
        self.menuFile.addAction(self.actionSave_Screenshot)
        self.menuFile.addSeparator()
        self.menuFile.addAction(self.actionUn_Delete_All)
        self.menuFile.addAction(self.actionReset_File)

        self.retranslateUi(PEMPlotEditor)

        self.zoom_to_offtime_btn.setDefault(False)
        self.profile_tab_widget.setCurrentIndex(0)


        QMetaObject.connectSlotsByName(PEMPlotEditor)
    # setupUi

    def retranslateUi(self, PEMPlotEditor):
        PEMPlotEditor.setWindowTitle(QCoreApplication.translate("PEMPlotEditor", u"MainWindow", None))
        self.actionSave.setText(QCoreApplication.translate("PEMPlotEditor", u"Save PEM File", None))
#if QT_CONFIG(shortcut)
        self.actionSave.setShortcut(QCoreApplication.translate("PEMPlotEditor", u"Ctrl+S", None))
#endif // QT_CONFIG(shortcut)
        self.actionSave_As.setText(QCoreApplication.translate("PEMPlotEditor", u"Save PEM File As...", None))
#if QT_CONFIG(shortcut)
        self.actionSave_As.setShortcut(QCoreApplication.translate("PEMPlotEditor", u"Ctrl+Alt+S", None))
#endif // QT_CONFIG(shortcut)
        self.actionOpen.setText(QCoreApplication.translate("PEMPlotEditor", u"Open", None))
        self.actionReset_File.setText(QCoreApplication.translate("PEMPlotEditor", u"Reset File", None))
#if QT_CONFIG(tooltip)
        self.actionReset_File.setToolTip(QCoreApplication.translate("PEMPlotEditor", u"Revert all changes made to the PEM file", None))
#endif // QT_CONFIG(tooltip)
        self.actionCopy_Screenshot.setText(QCoreApplication.translate("PEMPlotEditor", u"Copy Screenshot", None))
#if QT_CONFIG(shortcut)
        self.actionCopy_Screenshot.setShortcut(QCoreApplication.translate("PEMPlotEditor", u"Ctrl+C", None))
#endif // QT_CONFIG(shortcut)
        self.actionSave_Screenshot.setText(QCoreApplication.translate("PEMPlotEditor", u"Save Screenshot", None))
#if QT_CONFIG(shortcut)
        self.actionSave_Screenshot.setShortcut(QCoreApplication.translate("PEMPlotEditor", u"Ctrl+Alt+C", None))
#endif // QT_CONFIG(shortcut)
        self.actionUn_Delete_All.setText(QCoreApplication.translate("PEMPlotEditor", u"Un-Delete All", None))
        self.label.setText(QCoreApplication.translate("PEMPlotEditor", u"Decay Options", None))
        self.groupBox_5.setTitle(QCoreApplication.translate("PEMPlotEditor", u"View", None))
        self.plot_ontime_decays_cbox.setText(QCoreApplication.translate("PEMPlotEditor", u"Plot On-Time", None))
        self.plot_auto_clean_lines_cbox.setText(QCoreApplication.translate("PEMPlotEditor", u"Plot Auto-Clean Lines", None))
        self.link_x_cbox.setText(QCoreApplication.translate("PEMPlotEditor", u"Link X-axes", None))
        self.link_y_cbox.setText(QCoreApplication.translate("PEMPlotEditor", u"Link Y-axes", None))
        self.auto_range_cbox.setText(QCoreApplication.translate("PEMPlotEditor", u"Auto-Range", None))
#if QT_CONFIG(tooltip)
        self.zoom_to_offtime_btn.setToolTip(QCoreApplication.translate("PEMPlotEditor", u"Zoom to the late off-time channels", None))
#endif // QT_CONFIG(tooltip)
        self.zoom_to_offtime_btn.setText(QCoreApplication.translate("PEMPlotEditor", u"Zoom to Off-time", None))
#if QT_CONFIG(shortcut)
        self.zoom_to_offtime_btn.setShortcut(QCoreApplication.translate("PEMPlotEditor", u"Shift+Space", None))
#endif // QT_CONFIG(shortcut)
        self.groupBox_6.setTitle(QCoreApplication.translate("PEMPlotEditor", u"Edit", None))
        self.change_comp_decay_btn.setText(QCoreApplication.translate("PEMPlotEditor", u"Component", None))
        self.change_decay_suffix_btn.setText(QCoreApplication.translate("PEMPlotEditor", u"Suffix", None))
        self.change_station_decay_btn.setText(QCoreApplication.translate("PEMPlotEditor", u"Station", None))
        self.flip_decay_btn.setText(QCoreApplication.translate("PEMPlotEditor", u"+/-", None))
        self.label_2.setText(QCoreApplication.translate("PEMPlotEditor", u"Profile Options", None))
        self.groupBox.setTitle(QCoreApplication.translate("PEMPlotEditor", u"View", None))
        self.plot_mag_cbox.setText(QCoreApplication.translate("PEMPlotEditor", u"Plot Mag", None))
        self.show_scatter_cbox.setText(QCoreApplication.translate("PEMPlotEditor", u"Show Scatter", None))
        self.groupBox_3.setTitle(QCoreApplication.translate("PEMPlotEditor", u"Edit", None))
        self.change_comp_profile_btn.setText(QCoreApplication.translate("PEMPlotEditor", u"Components", None))
        self.change_profile_suffix_btn.setText(QCoreApplication.translate("PEMPlotEditor", u"Suffixes", None))
        self.shift_station_profile_btn.setText(QCoreApplication.translate("PEMPlotEditor", u"Stations", None))
        self.flip_profile_btn.setText(QCoreApplication.translate("PEMPlotEditor", u"+/-", None))
        self.remove_profile_btn.setText(QCoreApplication.translate("PEMPlotEditor", u"Del", None))
        self.groupBox_2.setTitle(QCoreApplication.translate("PEMPlotEditor", u"Cleaning", None))
        self.label_3.setText(QCoreApplication.translate("PEMPlotEditor", u"Threshold Value", None))
        self.label_4.setText(QCoreApplication.translate("PEMPlotEditor", u"Window Size", None))
        self.auto_clean_btn.setText(QCoreApplication.translate("PEMPlotEditor", u"Auto-Clean", None))
        self.menuFile.setTitle(QCoreApplication.translate("PEMPlotEditor", u"File", None))
    # retranslateUi

