from src.pem.pem_file import PEMParser, PEMFile
from src.gps.gps_adder import TransmitterLoop
from src.mag_field.mag_field_calculator import MagneticFieldCalculator

class MMRFile(PEMFile):
    def __init__(self):
        super(MMRFile, self).__init__()

    def __repr__(self):
        s = f"File: {self.filepath} \n" \
            f"Loaded Loop: {self.loop} \n" \
            f"Loaded BH: {self.segments} "
        return s

    @classmethod
    def from_pemlike(cls, filepath):
        pemfile = PEMParser.parse(cls, filepath)
        mmrfile = MMRFile()
        mmrfile.__dict__ = pemfile.__dict__.copy()
        return mmrfile

    def add_loop(self, filepath: str):
        try:
            self.loop = TransmitterLoop(filepath)
        except AssertionError:
            print("Unable to add loop!!!")

    def add_BH(self, ):
        pass

    def BField(self):
        mag = MagneticFieldCalculator(self.loop.df)

        pass

    def calc_harmonics(self):
        pass

    def ontime_channels(self):
        pass

    def offtime_channels(self):
        pass


if __name__ == "__main__":
    lp = "src\\mmr\\MMR LOOP SEPT 23.csv"
    a = MMRFile.from_pemlike("src\\mmr\\STACK\\Working\\SL12-64FLUXGATE.PEM")
    a.add_loop(lp)

    pass