import src.sdxf as sdxf
from src.pem.pem_file import PEMParser, PEMFile


class DXFDrawing:
    def __init__(self):
        self.drawing = sdxf.Drawing()
        self.features = 0

    def add_df(self, df, closed_poly: bool, **kwargs):
        # Pandas series don't like the datatypes so we recast
        xs, ys = df.Easting.to_numpy(), df.Northing.to_numpy()
        self.drawing.layers.append(sdxf.Layer(color=7))
        i = 1
        while i < len(xs):
            self.drawing.append(sdxf.Line(points=[(xs[i], ys[i]), (xs[i-1], ys[i-1])], **kwargs))
            i += 1

        if closed_poly:
            self.drawing.append(sdxf.Line(points=[(xs[0], ys[0]), (xs[-1], ys[-1])], **kwargs))

    def save_dxf(self, out_path: str):
        assert out_path.endswith(".dxf")
        self.drawing.saveas(out_path)


class PEMDXFDrawing(DXFDrawing):
    def __init__(self):
        super().__init__()

    def add_loop(self, pem: PEMFile):
        self.drawing.layers.append(sdxf.Layer(name=f'{pem.loop_name}', color=7))
        if pem.is_mmr():
            self.add_df(pem.loop.df, closed_poly=False, layer=f'{pem.loop_name}')
        else:
            self.add_df(pem.loop.df, closed_poly=True, layer=f'{pem.loop_name}')

    def add_surveyline(self, pem: PEMFile):
        self.drawing.layers.append(sdxf.Layer(name=f'{pem.line_name}', color=7))
        if pem.is_borehole():
            self.add_df(pem.segments.df, closed_poly=False, layer=f'{pem.loop_name}')
        else:
            self.add_df(pem.line.df, closed_poly=False, layer=f'{pem.loop_name}')


if __name__ == "__main__":
    from src.pem.pem_file import PEMParser, PEMFile
    path = r'C:\Users\Norm\Downloads\PEMs for Map\WLF-04-12 ZAv.PEM'
    apem = PEMParser().parse(path)
    dxfdraw = DXFDrawing()
    dxfdraw.add_df(apem.loop.df, True)
    dxfdraw.save_dxf(r'C:\Users\Norm\Downloads\PEMs for Map\test.dxf')

    pass