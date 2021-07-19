import pandas as pd

import src.dxf.sdxf as sdxf
from src.pem.pem_file import PEMFile


class DXFDrawing:
    def __init__(self):
        self.drawing = sdxf.Drawing()
        self.features = 0

    def add_df(self, df: pd.DataFrame, closed_poly: bool, **kwargs):
        """
        Add a dataframe type object to a DXF
        :param df: dataframe with .Easting and .Northing
        :param closed_poly: whether or not to join the first and last points
        :param kwargs: passthrough to sdxf calls
        """
        # sdxf doesn't like the Series datatypes so we recast
        xs, ys = df.Easting.to_numpy(), df.Northing.to_numpy()

        self.drawing.layers.append(sdxf.Layer(color=7))
        i = 1
        while i < len(xs):
            self.drawing.append(sdxf.Line(points=[(xs[i], ys[i]), (xs[i - 1], ys[i - 1])], **kwargs))
            i += 1

        if closed_poly:
            self.drawing.append(sdxf.Line(points=[(xs[0], ys[0]), (xs[-1], ys[-1])], **kwargs))
        self.features += 1

    def save_dxf(self, out_path: str):
        """
        Save the dxfs to out_path, does some error catching
        """
        assert out_path.lower().endswith(".dxf")
        # We don't want to save an empty file
        if self.features > 0:
            self.drawing.saveas(out_path)


class PEMDXFDrawing(DXFDrawing):
    def __init__(self):
        super().__init__()

    def add_loop(self, pem: PEMFile, **kw):
        """
        Add the loop from a PEMFile classed object
        :param pem: PEMFile to plot
        :param kw: passthrough for the dxf calls
        """
        self.drawing.layers.append(sdxf.Layer(name=f'{pem.loop_name}', color=7))
        if pem.is_mmr():
            self.add_df(pem.loop.df, closed_poly=False, layer=f'{pem.loop_name}', **kw)
        else:
            self.add_df(pem.loop.df, closed_poly=True, layer=f'{pem.loop_name}', **kw)

    def add_surveyline(self, pem: PEMFile, **kw):
        """
        Add the survey borehole or surface line from a PEMFile classed object
        :param pem: PEMFile to plot
        :param kw: passthrough for the dxf calls
        """
        self.drawing.layers.append(sdxf.Layer(name=f'{pem.line_name}', color=7))
        if pem.is_borehole():
            self.add_df(pem.segments.df, closed_poly=False, layer=f'{pem.loop_name}', **kw)
        else:
            self.add_df(pem.line.df, closed_poly=False, layer=f'{pem.loop_name}', **kw)
