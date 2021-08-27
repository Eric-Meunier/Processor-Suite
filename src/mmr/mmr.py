from src.pem.pem_file import PEMParser, PEMFile
from src.gps.gps_editor import TransmitterLoop, BoreholeSegments, BoreholeCollar, BoreholeGeometry
from src.mag_field.mag_field_calculator import MagneticFieldCalculator


def mutate_attr_catch(ufunc):
    def wrapper(*args, **kwargs):
        try:
            ufunc(*args, **kwargs)
            print("Added successfully")
        except AssertionError as e:
            print(f"AssertionError at {e}")
        except TypeError as e:
            print(f"TypeError at {e}")
        return None
    return wrapper


class MMRFile(PEMFile):
    def __init__(self):
        super(MMRFile, self).__init__()
        self.loop = TransmitterLoop(None)
        self.bhcollar = BoreholeCollar(None)
        self.bhseg = BoreholeSegments(None)

    def is_fluxgate(self):
        return True

    def __repr__(self):
        s = f"File: {self.filepath} \n" \
            f"Loaded Loop: {self.loop} \n" \
            f"Loaded BH: {self.segments} "
        return s

    @classmethod
    def from_pemlike(cls, filepath):
        pemfile = PEMParser.parse(PEMParser(), filepath)
        mmrfile = MMRFile()
        mmrfile.__dict__ = pemfile.__dict__.copy()
        return mmrfile

    def add_BH_collar_manual(self):
        easting = float(input("Enter easting: "))
        northing = float(input("Enter northing: "))
        elevation = float(input("Enter elevation: "))
        coord = [[easting, northing, elevation]]
        self.add_BH_collar(coord)

    @mutate_attr_catch
    def add_BH_collar(self, filepath):
        self.loop = BoreholeCollar(filepath)

    @mutate_attr_catch
    def add_BH_segments(self, filepath: str):
        """
        Add the survey borehole segment or dad file
        :param filepath: path to dip azimuth depth file
        """
        self.bhseg = BoreholeSegments(filepath)

    @mutate_attr_catch
    def add_loop(self, filepath: str):
        """
        Add a CLoop/Electrode cable hybrid coordinate set
        :param filepath: path to file with the electrode and loop coordinates in realspace
        """
        self.loop = TransmitterLoop(filepath)

    @mutate_attr_catch
    def compile_bh(self):
        assert self.bhcollar is not None and self.bhseg is not None
        self.bh = BoreholeGeometry(self.bhcollar, self.bhseg)

    def BField(self, x, y, z):
        mag = MagneticFieldCalculator(self.loop.df, closed_loop=False)
        return mag.calc_total_field(x, y, z)

    @mutate_attr_catch
    def ontime_channels(self):
        pass

    def offtime_channels(self):
        pass


if __name__ == "__main__":
    import numpy as np
    a = MMRFile.from_pemlike(r"C:\Users\Norm\Documents\GitHub\Crone\sample_files\MMR\64TOT.PEM")
    print(a.BField(1, 1, 1))
