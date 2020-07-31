import keyboard
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.artist import Artist
from matplotlib.lines import Line2D
from matplotlib.patches import Polygon
from PyQt5.QtCore import Qt
from scipy import spatial
from scipy.interpolate import interp1d, splrep, BSpline, splev


# def dist(x, y):
#     """
#     Return the distance between two points.
#     """
#     d = x - y
#     return np.sqrt(np.dot(d, d))
#
#
# def dist_point_to_segment(p, s0, s1):
#     """
#     Get the distance of a point to a segment.
#       *p*, *s0*, *s1* are *xy* sequences
#     This algorithm from
#     http://geomalgorithms.com/a02-_lines.html
#     """
#     v = s1 - s0
#     w = p - s0
#     c1 = np.dot(w, v)
#     if c1 <= 0:
#         return dist(p, s0)
#     c2 = np.dot(v, v)
#     if c2 <= c1:
#         return dist(p, s1)
#     b = c1 / c2
#     pb = s0 + b * v
#     return dist(p, pb)


class InteractiveSpline:

    """
    A polygon editor.
    https://matplotlib.org/gallery/event_handling/poly_editor.html

    Key-bindings

      't' toggle vertex markers on and off.  When vertex markers are on,
          you can move them, delete them

      'd' delete the vertex under point

      'i' insert a vertex at point.  You must be within epsilon of the
          line connecting two existing vertices

    """

    showverts = True
    epsilon = 10  # max pixel distance to count as a vertex hit

    def __init__(self, ax, spline_coords, line_color='red', vertical_plot=True):
        """
        :param ax: Matplotlib Axes object
        :param spline_coords: list of tuple, x and y coordinates of the spline to create
        :param line_color: str, color of the line
        :param vertical_plot: bool, if the target axes is being plotted vertically
        """
        self.ax = ax
        self.vp = vertical_plot

        # Create a Polygon object from the coordinates
        coords = np.array(list(spline_coords))
        if self.vp:
            coords = np.flip(coords, axis=1)
        poly = Polygon(coords, closed=False, animated=True)
        ax.add_patch(poly)
        if poly.figure is None:
            raise RuntimeError('You must first add the polygon to a figure '
                               'or canvas before defining the interactor')
        canvas = poly.figure.canvas
        self.poly = poly
        self.poly.set_visible(False)
        self.background = None
        self._ind = None  # the active vert
        self.method = 'quadratic'

        x, y = zip(*self.poly.xy)
        self.line = Line2D(x, y,
                           ls="",
                           marker='o',
                           markerfacecolor=line_color,
                           markeredgecolor='dimgray',
                           animated=True,
                           zorder=1)
        self.ax.add_line(self.line)

        xi, yi = self.interpolate(self.method)
        self.spline = Line2D(xi, yi,
                             color=line_color,
                             animated=True,
                             zorder=5)

        self.ax.add_line(self.spline)

        # self.cid = self.poly.add_callback(self.poly_changed)
        canvas.mpl_connect('draw_event', self.draw_callback)
        canvas.mpl_connect('button_press_event', self.button_press_callback)
        canvas.mpl_connect('key_press_event', self.key_press_callback)
        canvas.mpl_connect('button_release_event', self.button_release_callback)
        canvas.mpl_connect('motion_notify_event', self.motion_notify_callback)
        self.canvas = canvas

    def change_alpha(self, alpha):
        self.line.set_alpha(alpha)
        self.spline.set_alpha(alpha)

    def get_spline_coords(self):
        spline_coords = self.spline.get_transform().transform(self.spline._xy)
        return spline_coords

    def interpolate(self, method):
        """
        Interpolates the spline based on the coordinates of self.poly
        :param method: str, either 'cubic' or 'bspline'
        :return: tuple of arrays, x and y coordinates of spline
        """
        if self.vp:
            y, x = self.poly.xy.T
        else:
            x, y = self.poly.xy.T

        xmin, xmax = x.min(), x.max()
        xi = np.linspace(xmin, xmax, 1000)

        # tck = splrep(x, y, s=0)
        # yi = splev(xi, tck, der=0)

        f = interp1d(x, y, kind=method)
        yi = f(xi)

        if self.vp:
            return yi, xi
        else:
            return xi, yi

    def draw_callback(self, event):
        self.background = self.canvas.copy_from_bbox(self.ax.bbox)
        self.ax.draw_artist(self.poly)
        self.ax.draw_artist(self.line)
        self.ax.draw_artist(self.spline)
        # do not need to blit here, this will fire before the screen is
        # updated

    def poly_changed(self, poly):
        """
        this method is called whenever the polygon object is called
        """
        # only copy the artist props to the line (except visibility)
        vis = self.line.get_visible()
        Artist.update_from(self.line, poly)
        self.line.set_visible(vis)  # don't use the poly visibility state

    def get_ind_under_point(self, event):
        """
        get the index of the vertex under point if within epsilon tolerance
        """
        # display coords
        xy = np.asarray(self.poly.xy)
        xyt = self.poly.get_transform().transform(xy)
        xt, yt = xyt[:, 0], xyt[:, 1]
        d = np.hypot(xt - event.x, yt - event.y)
        indseq, = np.nonzero(d == d.min())
        ind = indseq[0]
        print(f"Index clicked: {ind} ({self.poly.xy[ind]})")
        if d[ind] >= self.epsilon:
            ind = None

        return ind

    def button_press_callback(self, event):
        """
        whenever a mouse button is pressed
        """

        if not self.showverts:
            return
        if event.inaxes is None:
            return
        if event.button != 1:
            return
        self._ind = self.get_ind_under_point(event)

        # Add a knot if the point clicked is close enough to the spline
        if keyboard.is_pressed('left ctrl'):
            print(f"Mouse button clicked with left ctrl held.")
            xys = self.poly.get_transform().transform(self.poly.xy)
            p = event.x, event.y  # display coords

            # Find the distance of the point clicked to the nearest spline coordinate
            spline_coords = self.get_spline_coords()
            distance, spline_index = spatial.KDTree(spline_coords).query(p)

            # Find which poly segment the value falls within
            if self.vp:
                poly_ys = np.sort(xys[:, 1])
                i = np.where(poly_ys >= p[1])[0][0]
                print(f"Poly segment index: {i}")
            else:
                poly_xs = np.sort(xys[:, 0])
                i = np.where(poly_xs >= p[0])[0][0]
                print(f"Poly segment index: {i}")

            if distance <= self.epsilon * 2:
                self.poly.xy = np.insert(
                    self.poly.xy, i,
                    [event.xdata, event.ydata],
                    axis=0)

                self.line.set_data(zip(*self.poly.xy))

                xi, yi = self.interpolate(self.method)
                self.spline.set_data(xi, yi)

        # Remove a knot
        elif keyboard.is_pressed('alt'):
        # elif event.button == Qt.RightButton:
            ind = self.get_ind_under_point(event)

            if all([ind is not None, ind != 0, ind != len(self.poly.xy), len(self.poly.xy) > 4]):
                print(f"Deleting index {ind} ({self.poly.xy[ind]})")
                print(f"Poly XY before delete: \n{self.poly.xy}")
                self.poly.xy = np.delete(self.poly.xy, ind, axis=0)
                print(f"Poly XY after delete: \n{self.poly.xy}")

                self.line.set_data(zip(*self.poly.xy))

                xi, yi = self.interpolate(self.method)
                self.spline.set_data(xi, yi)
            else:
                print(f"Cannot delete that knot.")

        if self.line.stale:
            self.canvas.draw_idle()

    def button_release_callback(self, event):
        """
        whenever a mouse button is released
        """

        if not self.showverts:
            return
        if event.button != 1:
            return
        self._ind = None

    def key_press_callback(self, event):
        """
        whenever a key is pressed
        """

        if not event.inaxes:
            return

        if event.key == 't':
            self.showverts = not self.showverts
            self.line.set_visible(self.showverts)
            if not self.showverts:
                self._ind = None

        if self.line.stale:
            self.canvas.draw_idle()

    def motion_notify_callback(self, event):
        """
        on mouse movement
        """

        if not self.showverts:
            return
        if self._ind is None:
            return
        if event.inaxes is None:
            return
        if event.button != 1:
            return

        x, y = event.xdata, event.ydata

        # Lock the x component movement if it's the first or last knot
        if self._ind == 0 or self._ind == len(self.poly.xy) - 1:
            self.poly.xy[self._ind] = x, self.poly.xy[self._ind][1]
        else:
            self.poly.xy[self._ind] = x, y

        # if self.vp:
        #     self.line.set_data(zip(*np.flip(self.poly.xy, axis=1)))
        # else:
        self.line.set_data(zip(*self.poly.xy))

        xi, yi = self.interpolate(self.method)
        self.spline.set_data(xi, yi)

        self.canvas.restore_region(self.background)
        self.ax.draw_artist(self.poly)
        self.ax.draw_artist(self.line)
        self.ax.draw_artist(self.spline)
        self.canvas.blit(self.ax.bbox)


if __name__ == '__main__':
    fig, ax = plt.subplots()
    xs = (921, 951, 993, 1035, 1200)
    ys = (1181, 1230, 1243, 1230, 1181)

    ax.set_ylim((800, 1300))
    ax.set_xlim((1000, 1300))

    p = InteractiveSpline(ax, zip(xs, ys))

    plt.show()