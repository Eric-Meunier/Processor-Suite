import pyqtgraph as pg
import time

class AxisTime(pg.AxisItem):
    ## Formats axis label to human readable time.
    # @param[in] values List of \c time_t.
    # @param[in] scale Not used.
    # @param[in] spacing Not used.
    def tickStrings(self, values, scale, spacing):
        strns = []
        for x in values:
            try:
                strns.append(time.strftime("%H:%M:%S", time.gmtime(x)))    # time_t --> time.struct_time
            except ValueError:  # Windows can't handle dates before 1970
                strns.append('')
        return strns
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
# # -*- coding: utf-8 -*-
# """
# This example demonstrates the creation of a plot with a customized
# AxisItem and ViewBox.
# """
#
# # import initExample  ## Add path to library (just for examples; you do not need this)
#
# import pyqtgraph as pg
# from pyqtgraph.Qt import QtCore, QtGui
# import numpy as np
# import time
#
#
# class DateAxis(pg.AxisItem):
#     def tickStrings(self, values, scale, spacing):
#         strns = []
#         rng = max(values) - min(values)
#         # if rng < 120:
#         #    return pg.AxisItem.tickStrings(self, values, scale, spacing)
#         if rng < 3600 * 24:
#             string = '%H:%M:%S'
#             label1 = '%b %d -'
#             label2 = ' %b %d, %Y'
#         elif rng >= 3600 * 24 and rng < 3600 * 24 * 30:
#             string = '%d'
#             label1 = '%b - '
#             label2 = '%b, %Y'
#         elif rng >= 3600 * 24 * 30 and rng < 3600 * 24 * 30 * 24:
#             string = '%b'
#             label1 = '%Y -'
#             label2 = ' %Y'
#         elif rng >= 3600 * 24 * 30 * 24:
#             string = '%Y'
#             label1 = ''
#             label2 = ''
#         for x in values:
#             try:
#                 strns.append(time.strftime(string, time.localtime(x)))
#             except ValueError:  ## Windows can't handle dates before 1970
#                 strns.append('')
#         try:
#             label = time.strftime(label1, time.localtime(min(values))) + time.strftime(label2,
#                                                                                        time.localtime(max(values)))
#         except ValueError:
#             label = ''
#         # self.setLabel(text=label)
#         return strns
#
#
# class CustomViewBox(pg.ViewBox):
#     def __init__(self, *args, **kwds):
#         pg.ViewBox.__init__(self, *args, **kwds)
#         self.setMouseMode(self.RectMode)
#
#     ## reimplement right-click to zoom out
#     def mouseClickEvent(self, ev):
#         if ev.button() == QtCore.Qt.RightButton:
#             self.autoRange()
#
#     def mouseDragEvent(self, ev):
#         if ev.button() == QtCore.Qt.RightButton:
#             ev.ignore()
#         else:
#             pg.ViewBox.mouseDragEvent(self, ev)
#
#
# app = pg.mkQApp()
#
# axis = DateAxis(orientation='bottom')
# vb = CustomViewBox()
#
# pw = pg.PlotWidget(viewBox=vb, axisItems={'bottom': axis}, enableMenu=False,
#                    title="PlotItem with custom axis and ViewBox<br>Menu disabled, mouse behavior changed: left-drag to zoom, right-click to reset zoom")
# dates = np.arange(8) * (3600 * 24 * 356)
# pw.plot(x=dates, y=[1, 6, 2, 4, 3, 5, 6, 8], symbol='o')
# pw.show()
# pw.setWindowTitle('pyqtgraph example: customPlot')
#
# r = pg.PolyLineROI([(0, 0), (10, 10)])
# pw.addItem(r)
#
# ## Start Qt event loop unless running in interactive mode or using pyside.
# if __name__ == '__main__':
#     import sys
#
#     if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
#         QtGui.QApplication.instance().exec_()
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
# #!/usr/bin/env python
#
# #############################################################################
# #
# # This file was adapted from Taurus TEP17, but all taurus dependencies were
# # removed so that it works with just pyqtgraph
# #
# # Just run it and play with the zoom to see how the labels and tick positions
# # automatically adapt to the shown range
# #
# #############################################################################
# # http://taurus-scada.org
# #
# # Copyright 2011 CELLS / ALBA Synchrotron, Bellaterra, Spain
# #
# # Taurus is free software: you can redistribute it and/or modify
# # it under the terms of the GNU Lesser General Public License as published by
# # the Free Software Foundation, either version 3 of the License, or
# # (at your option) any later version.
# #
# # Taurus is distributed in the hope that it will be useful,
# # but WITHOUT ANY WARRANTY; without even the implied warranty of
# # MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# # GNU Lesser General Public License for more details.
# #
# # You should have received a copy of the GNU Lesser General Public License
# # along with Taurus.  If not, see <http://www.gnu.org/licenses/>.
# #
# #############################################################################
#
# """
# This module provides date-time aware axis
# """
#
# __all__ = ["DateAxisItem"]
#
# import numpy
# from pyqtgraph import AxisItem
# from datetime import datetime, timedelta
# from time import mktime
#
#
# class DateAxisItem(AxisItem):
#     """
#     A tool that provides a date-time aware axis. It is implemented as an
#     AxisItem that interpretes positions as unix timestamps (i.e. seconds
#     since 1970).
#     The labels and the tick positions are dynamically adjusted depending
#     on the range.
#     It provides a  :meth:`attachToPlotItem` method to add it to a given
#     PlotItem
#     """
#
#     # Max width in pixels reserved for each label in axis
#     _pxLabelWidth = 80
#
#     def __init__(self, *args, **kwargs):
#         AxisItem.__init__(self, *args, **kwargs)
#         self._oldAxis = None
#
#     def tickValues(self, minVal, maxVal, size):
#         """
#         Reimplemented from PlotItem to adjust to the range and to force
#         the ticks at "round" positions in the context of time units instead of
#         rounding in a decimal base
#         """
#
#         maxMajSteps = int(size / self._pxLabelWidth)
#
#         dt1 = datetime.fromtimestamp(minVal)
#         dt2 = datetime.fromtimestamp(maxVal)
#
#         dx = maxVal - minVal
#         majticks = []
#
#         if dx > 63072001:  # 3600s*24*(365+366) = 2 years (count leap year)
#             d = timedelta(days=366)
#             for y in range(dt1.year + 1, dt2.year):
#                 dt = datetime(year=y, month=1, day=1)
#                 majticks.append(mktime(dt.timetuple()))
#
#         elif dx > 5270400:  # 3600s*24*61 = 61 days
#             d = timedelta(days=31)
#             dt = dt1.replace(day=1, hour=0, minute=0,
#                              second=0, microsecond=0) + d
#             while dt < dt2:
#                 # make sure that we are on day 1 (even if always sum 31 days)
#                 dt = dt.replace(day=1)
#                 majticks.append(mktime(dt.timetuple()))
#                 dt += d
#
#         elif dx > 172800:  # 3600s24*2 = 2 days
#             d = timedelta(days=1)
#             dt = dt1.replace(hour=0, minute=0, second=0, microsecond=0) + d
#             while dt < dt2:
#                 majticks.append(mktime(dt.timetuple()))
#                 dt += d
#
#         elif dx > 7200:  # 3600s*2 = 2hours
#             d = timedelta(hours=1)
#             dt = dt1.replace(minute=0, second=0, microsecond=0) + d
#             while dt < dt2:
#                 majticks.append(mktime(dt.timetuple()))
#                 dt += d
#
#         elif dx > 1200:  # 60s*20 = 20 minutes
#             d = timedelta(minutes=10)
#             dt = dt1.replace(minute=(dt1.minute // 10) * 10,
#                              second=0, microsecond=0) + d
#             while dt < dt2:
#                 majticks.append(mktime(dt.timetuple()))
#                 dt += d
#
#         elif dx > 120:  # 60s*2 = 2 minutes
#             d = timedelta(minutes=1)
#             dt = dt1.replace(second=0, microsecond=0) + d
#             while dt < dt2:
#                 majticks.append(mktime(dt.timetuple()))
#                 dt += d
#
#         elif dx > 20:  # 20s
#             d = timedelta(seconds=10)
#             dt = dt1.replace(second=(dt1.second // 10) * 10, microsecond=0) + d
#             while dt < dt2:
#                 majticks.append(mktime(dt.timetuple()))
#                 dt += d
#
#         elif dx > 2:  # 2s
#             d = timedelta(seconds=1)
#             majticks = range(int(minVal), int(maxVal))
#
#         else:  # <2s , use standard implementation from parent
#             return AxisItem.tickValues(self, minVal, maxVal, size)
#
#         L = len(majticks)
#         if L > maxMajSteps:
#             majticks = majticks[::int(numpy.ceil(float(L) / maxMajSteps))]
#
#         return [(d.total_seconds(), majticks)]
#
#     def tickStrings(self, values, scale, spacing):
#         """Reimplemented from PlotItem to adjust to the range"""
#         ret = []
#         if not values:
#             return []
#
#         if spacing >= 31622400:  # 366 days
#             fmt = "%Y"
#
#         elif spacing >= 2678400:  # 31 days
#             fmt = "%Y %b"
#
#         elif spacing >= 86400:  # = 1 day
#             fmt = "%b/%d"
#
#         elif spacing >= 3600:  # 1 h
#             fmt = "%b/%d-%Hh"
#
#         elif spacing >= 60:  # 1 m
#             fmt = "%H:%M"
#
#         elif spacing >= 1:  # 1s
#             fmt = "%H:%M:%S"
#
#         else:
#             # less than 2s (show microseconds)
#             # fmt = '%S.%f"'
#             fmt = '[+%fms]'  # explicitly relative to last second
#
#         for x in values:
#             try:
#                 t = datetime.fromtimestamp(x)
#                 ret.append(t.strftime(fmt))
#             except ValueError:  # Windows can't handle dates before 1970
#                 ret.append('')
#
#         return ret
#
#     def attachToPlotItem(self, plotItem):
#         """Add this axis to the given PlotItem
#         :param plotItem: (PlotItem)
#         """
#         self.setParentItem(plotItem)
#         viewBox = plotItem.getViewBox()
#         self.linkToView(viewBox)
#         self._oldAxis = plotItem.axes[self.orientation]['item']
#         self._oldAxis.hide()
#         plotItem.axes[self.orientation]['item'] = self
#         pos = plotItem.axes[self.orientation]['pos']
#         plotItem.layout.addItem(self, *pos)
#         self.setZValue(-1000)
#
#     def detachFromPlotItem(self):
#         """Remove this axis from its attached PlotItem
#         (not yet implemented)
#         """
#         raise NotImplementedError()  # TODO
#
#
# if __name__ == '__main__':
#     import time
#     import sys
#     import pyqtgraph as pg
#     from PyQt4 import QtGui
#
#     app = QtGui.QApplication([])
#
#     w = pg.PlotWidget()
#
#     # Add the Date-time axis
#     axis = DateAxisItem(orientation='bottom')
#     axis.attachToPlotItem(w.getPlotItem())
#
#     # plot some random data with timestamps in the last hour
#     now = time.time()
#     timestamps = numpy.linspace(now - 3600, now, 100)
#     w.plot(x=timestamps, y=numpy.random.rand(100), symbol='o')
#
#     w.show()
#
#     sys.exit(app.exec_())
#
#
#
#
#
#
# # import pyqtgraph as pg
# # import datetime
# # import time
# #
# #
# # def timestamp():
# #     return int(time.mktime(datetime.datetime.now().timetuple()))
# #
# #
# # class TimeAxisItem(pg.AxisItem):
# #     def __init__(self, *args, **kwargs):
# #         super().__init__(*args, **kwargs)
# #         self.setLabel(text='Time', units=None)
# #         self.enableAutoSIPrefix(False)
# #
# #     def tickStrings(self, values, scale, spacing):
# #         return [datetime.datetime.fromtimestamp(value).strftime("%H:%M:%S") for value in values]
#
#
#
#
#
# # __all__ = ["DateAxisItem"]
# #
# # import numpy
# # from pyqtgraph import AxisItem
# # from datetime import datetime, timedelta
# # from time import mktime
# #
# # class DateAxisItem(AxisItem):
# #     """
# #     A tool that provides a date-time aware axis. It is implemented as an
# #     AxisItem that interpretes positions as unix timestamps (i.e. seconds
# #     since 1970).
# #     The labels and the tick positions are dynamically adjusted depending
# #     on the range.
# #     It provides a  :meth:`attachToPlotItem` method to add it to a given
# #     PlotItem
# #     """
# #
# #     # Max width in pixels reserved for each label in axis
# #     _pxLabelWidth = 80
# #
# #     def __init__(self, *args, **kwargs):
# #         AxisItem.__init__(self, *args, **kwargs)
# #         self._oldAxis = None
# #
# #     def tickValues(self, minVal, maxVal, size):
# #         """
# #         Reimplemented from PlotItem to adjust to the range and to force
# #         the ticks at "round" positions in the context of time units instead of
# #         rounding in a decimal base
# #         """
# #
# #         maxMajSteps = int(size / self._pxLabelWidth)
# #
# #         dt1 = datetime.fromtimestamp(minVal)
# #         dt2 = datetime.fromtimestamp(maxVal)
# #
# #         dx = maxVal - minVal
# #         majticks = []
# #
# #         if dx > 63072001:  # 3600s*24*(365+366) = 2 years (count leap year)
# #             d = timedelta(days=366)
# #             for y in range(dt1.year + 1, dt2.year):
# #                 dt = datetime(year=y, month=1, day=1)
# #                 majticks.append(mktime(dt.timetuple()))
# #
# #         elif dx > 5270400:  # 3600s*24*61 = 61 days
# #             d = timedelta(days=31)
# #             dt = dt1.replace(day=1, hour=0, minute=0,
# #                              second=0, microsecond=0) + d
# #             while dt < dt2:
# #                 # make sure that we are on day 1 (even if always sum 31 days)
# #                 dt = dt.replace(day=1)
# #                 majticks.append(mktime(dt.timetuple()))
# #                 dt += d
# #
# #         elif dx > 172800:  # 3600s24*2 = 2 days
# #             d = timedelta(days=1)
# #             dt = dt1.replace(hour=0, minute=0, second=0, microsecond=0) + d
# #             while dt < dt2:
# #                 majticks.append(mktime(dt.timetuple()))
# #                 dt += d
# #
# #         elif dx > 7200:  # 3600s*2 = 2hours
# #             d = timedelta(hours=1)
# #             dt = dt1.replace(minute=0, second=0, microsecond=0) + d
# #             while dt < dt2:
# #                 majticks.append(mktime(dt.timetuple()))
# #                 dt += d
# #
# #         elif dx > 1200:  # 60s*20 = 20 minutes
# #             d = timedelta(minutes=10)
# #             dt = dt1.replace(minute=(dt1.minute // 10) * 10,
# #                              second=0, microsecond=0) + d
# #             while dt < dt2:
# #                 majticks.append(mktime(dt.timetuple()))
# #                 dt += d
# #
# #         elif dx > 120:  # 60s*2 = 2 minutes
# #             d = timedelta(minutes=1)
# #             dt = dt1.replace(second=0, microsecond=0) + d
# #             while dt < dt2:
# #                 majticks.append(mktime(dt.timetuple()))
# #                 dt += d
# #
# #         elif dx > 20:  # 20s
# #             d = timedelta(seconds=10)
# #             dt = dt1.replace(second=(dt1.second // 10) * 10, microsecond=0) + d
# #             while dt < dt2:
# #                 majticks.append(mktime(dt.timetuple()))
# #                 dt += d
# #
# #         elif dx > 2:  # 2s
# #             d = timedelta(seconds=1)
# #             majticks = range(int(minVal), int(maxVal))
# #
# #         else:  # <2s , use standard implementation from parent
# #             return AxisItem.tickValues(self, minVal, maxVal, size)
# #
# #         L = len(majticks)
# #         if L > maxMajSteps:
# #             majticks = majticks[::int(numpy.ceil(float(L) / maxMajSteps))]
# #
# #         return [(d.total_seconds(), majticks)]
# #
# #     def tickStrings(self, values, scale, spacing):
# #         """Reimplemented from PlotItem to adjust to the range"""
# #         ret = []
# #         if not values:
# #             return []
# #
# #         if spacing >= 31622400:  # 366 days
# #             fmt = "%Y"
# #
# #         elif spacing >= 2678400:  # 31 days
# #             fmt = "%Y %b"
# #
# #         elif spacing >= 86400:  # = 1 day
# #             fmt = "%b/%d"
# #
# #         elif spacing >= 3600:  # 1 h
# #             fmt = "%b/%d-%Hh"
# #
# #         elif spacing >= 60:  # 1 m
# #             fmt = "%H:%M"
# #
# #         elif spacing >= 1:  # 1s
# #             fmt = "%H:%M:%S"
# #
# #         else:
# #             # less than 2s (show microseconds)
# #             # fmt = '%S.%f"'
# #             fmt = '[+%fms]'  # explicitly relative to last second
# #
# #         for x in values:
# #             try:
# #                 t = datetime.fromtimestamp(x)
# #                 ret.append(t.strftime(fmt))
# #             except ValueError:  # Windows can't handle dates before 1970
# #                 ret.append('')
# #
# #         return ret
# #
# #     def attachToPlotItem(self, plotItem):
# #         """Add this axis to the given PlotItem
# #         :param plotItem: (PlotItem)
# #         """
# #         self.setParentItem(plotItem)
# #         viewBox = plotItem.getViewBox()
# #         self.linkToView(viewBox)
# #         self._oldAxis = plotItem.axes[self.orientation]['item']
# #         self._oldAxis.hide()
# #         plotItem.axes[self.orientation]['item'] = self
# #         pos = plotItem.axes[self.orientation]['pos']
# #         plotItem.layout.addItem(self, *pos)
# #         self.setZValue(-1000)
# #
# #     def detachFromPlotItem(self):
# #         """Remove this axis from its attached PlotItem
# #         (not yet implemented)
# #         """
# #         raise NotImplementedError()  # TODO