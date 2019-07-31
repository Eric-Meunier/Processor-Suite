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

