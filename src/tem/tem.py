import re
import pandas as pd
from src.pem.pem_file import PEMParser

from pathlib import Path
from src.gps.gps_editor import TransmitterLoop, SurveyLine, BoreholeCollar, BoreholeSegments, BoreholeGeometry

PEMPRO_VER = "0.11.6"
EMPTY_TEM_HEADER = \
    "TEM File Created by Crone PEMPro {ver}\n" \
    "LINE: {linehole} DATATYPE:TEM CONFIG:FIXEDLOOP ELEV:{elev} UNITS:{uni} CURRENT:{cur} " \
    "TXTURNS:{tx_turns} BFREQ:{bfreq} DUTYCYCLE:50.000 ONTIME:{tb_ms} OFFTIME:{tb_ms} &\n" \
    "TURNON:0.000 TURNOFF:{ramp_ms} TIMINGMARK:{tmemark} RXAREAZ:{a_coil} RXAREAX:{a_coil} RXAREAY:{a_coil} RXDIPOLE:YES TXDIPOLE:NO &"


def EMPTY_TEM_LOOP(lst_of_coords):
    s = ""
    for i, coord in enumerate(lst_of_coords):
        s += f"LV{i + 1}X:{coord[0]:.2f} " \
             f"LV{i + 1}Y:{coord[1]:.2f} " \
             f"LV{i + 1}Z:{coord[2]:.2f} & \n"
    return s


EMPTY_TEM_LOOP = \
    "LV1X:50.00 LV1Y:50.00 LV1Z:0.00 & \n" \
    "LV2X:50.00 LV2Y:-50.00 LV2Z:0.00 & \n" \
    "LV3X:-50.00 LV3Y:-50.00 LV3Z:0.00 & \n" \
    "LV4X:-50.00 LV4Y:50.00 LV4Z:0.00 "

TEMPLATE_DEFAULT = {"uni": 'nT/s',
                    "cur": "1000",
                    "lp_l": "100",
                    "lp_w": "100",
                    "client": "NAME_CLIENT",
                    "grid": "NAME_GRID",
                    "linehole": "NAME_SURVEYLINE",
                    "loop": "NAME_LOOP",
                    "date": "January 01, 1900",
                    "m_unit": 'Metric',
                    "survtype": "Surface",
                    "synctype": "Crystal-Master",
                    "tb": "100",
                    "ramp": "1500",
                    "num_chn": "66",
                    "rds": "100",
                    "rx_id": "999",
                    "rx_ver": "9.99",
                    "rx_verd": "Jan01,1990",
                    "ppval": "1000",
                    "a_coil": "500"}

TEMPLATE_BHFLUX = {"uni": 'picoTeslas',
                   "m_unit": 'Metric',
                   "survtype": "BH-FLUX",
                   "ppval": "1000",
                   "a_coil": "500"}

TEMPLATE_BHXY = {"uni": 'nanoTesla/sec',
                 "m_unit": 'Metric',
                 "survtype": "Borehole",
                 "ppval": "1000",
                 "a_coil": "2800"}


def TEM_CHANNELS(ch_times):
    return "/TIMES(ms)=" + ", ".join(ch_times)


class TEMBase:
    # This class will handle all the parsing of the tem file and the base structure
    def __init__(self):
        self.STR_TEM = ""
        self.TEM_SOURCE = ""
        self.TEM_HEADER = ""
        self.TEM_COLUMNS = ""
        self.TEM_META = ""
        self.TEM_DATA = []
        self.filepath = None

    def parse_from_tem(self, filepath):
        with open(filepath, "r+") as f:
            fstr = f.read()
        slashsplit = fstr.split(r'/')
        self.STR_TEM = fstr.split('\n')
        self.TEM_SOURCE = self.STR_TEM[0]
        self.TEM_HEADER = slashsplit[0]
        self.TEM_COLUMNS = slashsplit[-2].split('\n')[-2]
        self.TEM_META = slashsplit[-1].split('\n')[0]
        self.TEM_DATA = slashsplit[-1].split('\n')[1:]

        self.filepath = Path(filepath)


class PEMTEM(TEMBase):
    # This class just extends the init of TEMBase to include the interface from PEMFile
    # and the parsing of the read TEM
    def __init__(self):
        super(PEMTEM, self).__init__()
        self.format = '210'
        self.units = None
        self.operator = "PEMPro"
        self.probes = {'XY probe number': '0',
                       'SOA': '0',
                       'Tool number': '0',
                       'Tool ID': '0'}
        self.current = None
        self.loop_dimensions = "100 100 0"
        self.client = None
        self.grid = None
        self.line_name = None
        self.loop_name = None
        self.date = None
        self.survey_type = None
        self.convention = 'Metric'
        self.sync = 'Crystal-Master'
        self.timebase = None
        self.ramp = None
        self.number_of_channels = None
        self.number_of_readings = None
        self.rx_number = '#999'
        self.rx_software_version = '9.99'
        self.rx_software_version_date = "Jan01,1990"
        self.rx_file_name = 'PEMProTEM'
        self.normalized = 'N'
        self.primary_field_value = '1000'
        self.coil_area = None
        self.loop_polarity = None
        self.channel_times = None

        self.notes = None
        self.data = None

        self.loop = None
        self.collar = None
        self.segments = None

        self.line = None
        self.crs = None

        self.total_scale_factor = 0.
        self.soa = 0  # For XY SOA rotation
        self.pp_table = None  # PP de-rotation information
        self.prepped_for_rotation = False
        self.legacy = False

    @staticmethod
    def _regex_search(re_str, target):
        reg = f'{re_str}:(.*?) '
        found = re.search(reg, target)
        if found:
            return found[1]
        else:
            return None

    def _parse_header(self):
        self.date = self._regex_search('DATE', self.TEM_HEADER)
        if self.date is not None:
            self.date = self.date.replace("_", " ")

        self.coil_area = self._regex_search('RXAREA*', self.TEM_HEADER)

        self.client = self._regex_search('CLIENT', self.TEM_HEADER)
        if self.client is not None:
            self.client = self.client.replace("_", " ")

        self.grid = self._regex_search('PROSPECT', self.TEM_HEADER)
        if self.grid is not None:
            self.grid = self.grid.replace("_", " ")

        self.current = self._regex_search('CURRENT', self.TEM_HEADER)
        if self.current is not None:
            self.current = float(self.current)

        self.line_name = self._regex_search('LINE', self.TEM_HEADER)
        self.loop_name = self._regex_search('LOOP', self.TEM_HEADER)
        self.units = self._regex_search('UNITS', self.TEM_HEADER)[1:-1]
        # Look for timebase
        self.timebase = self._regex_search('OFFTIME', self.TEM_HEADER)
        # If OFFTIME isn't in the header, look for ONTIME
        if self.timebase is None:
            self.timebase = self._regex_search('ONTIME', self.TEM_HEADER)

        if self.timebase is not None:
            self.timebase = float(self.timebase)

        # Infer PEM Survey Type
        self.survey_type = self._PEM_SURVTYPE()

        # Compile a borehole collar if it's there in the header
        collarx = self._regex_search('XCOLLAR', self.TEM_HEADER)
        collary = self._regex_search('YCOLLAR', self.TEM_HEADER)
        collarz = self._regex_search('ZCOLLAR', self.TEM_HEADER)
        if collarz is not None and collary is not None and collarx is not None:
            self.collar = BoreholeCollar([['<P00>', collarx, collary, collarz]])

        self.ramp = self._regex_search('TURNOFF', self.TEM_HEADER)
        if self.ramp is not None:
            self.ramp = float(self.ramp) * 1000

        # Compile a loop since it's in the header
        self.loop = TransmitterLoop(self._parse_loop())

    def _PEM_SURVTYPE(self):
        # Our PEM survey types will not be carried over back and forth
        # so we have to infer them from whats in the TEM

        isborehole = 'CONFIG:DOWNHOLE' in self.TEM_HEADER
        isfluxgate = '/s' in self.units
        # TODO Find a way to infer SQUID data in TEM
        if isborehole and isfluxgate:
            ret = "BH-FLUX"
        elif isborehole and not isfluxgate:
            ret = "Borehole"
        elif not isborehole and isfluxgate:
            ret = "S-FLUX"
        elif not isborehole and not isfluxgate:
            ret = "S-COIL"
        else:
            ret = "S-SQUID"
        return ret

    def _parse_loop(self):
        headersplit = self.TEM_HEADER.split("LOOP:")
        if len(headersplit) > 0:
            loop = headersplit[1].split("&\n")
        else:
            # Escape
            return None
        loop.pop(0)

        regex = re.compile('LV\d+X:([\d+.]+) LV\d+Y:([\d+.]+) LV\d+Z:([\d+.]+)')
        coords = []
        if self.convention == "Metric":
            uflag = '0'
        else:
            uflag = '1'
        for i, l in enumerate(loop):
            c = re.search(regex, l)
            coords.append([f'<L{i:02d}>', c[1], c[2], c[3], uflag])
        return coords

    def _parse_data(self):
        pass

    def parse(self):
        self._parse_header()
        self._PEM_SURVTYPE()

        self._parse_data()

        pass


class TEM(PEMTEM):
    # This class will handle the interface with PEMPro
    def __init__(self, filepath):
        super(TEM, self).__init__()
        super().parse_from_tem(filepath)
        self.parse()

    def is_borehole(self):
        return 'CONFIG:DOWNHOLE' in self.TEM_HEADER

    def is_fluxgate(self):
        if self.units is not None:
            return '/s' in self.units
        else:
            return False

    def is_xy(self):
        """
        If the survey is an induction XY probe survey
        :return: bool
        """
        if not self.is_borehole or self.is_fluxgate():
            return False
        else:
            components = self.data.Component.unique()
            if len(components) == 2:
                if 'X' in components and 'Y' in components:
                    return True
                else:
                    return False
            else:
                return False

    def is_z(self):
        """
        If the survey is an induction Z probe survey
        :return: bool
        """
        if not self.is_borehole or self.is_fluxgate():
            return False
        else:
            components = self.data.Component.unique()
            if len(components) == 1:
                if 'Z' in components:
                    return True
                else:
                    return False
            else:
                return False

    def is_derotated(self):
        if self.is_borehole():
            filt = (self.data.Component == 'X') | (self.data.Component == 'Y')
            xy_data = self.data[filt]
            return xy_data['RAD_tool'].map(lambda x: x.derotated).all()
        else:
            return False

    def is_averaged(self):
        data = self.data[['Station', 'Component']]
        if any(data.duplicated()):
            return False
        else:
            return True

    def is_split(self):
        if self.channel_times.Remove.any():
            return False
        else:
            return True

    def is_pp(self):
        if self.channel_times.Width.max() < 10 ** -4:
            return True
        else:
            return False

    def is_mmr(self):
        # This is hacky as hell but currently our RX dumps the BH files as type BH-Flux so we just hope the
        # operator puts mmr or dipole somewhere in the loop name
        # TODO We need a fileheader survey type for MMR
        return 'mmr' in self.loop_name.casefold() or 'dipole' in self.loop_name.casefold()

    def has_collar_gps(self):
        if self.is_borehole():
            if not self.collar.df.dropna().empty and all(self.collar.df):
                return True
            else:
                return False
        else:
            return False

    def has_geometry(self):
        if self.is_borehole():
            if not self.segments.df.dropna().empty and all(self.segments.df):
                return True
            else:
                return False
        else:
            return False

    def has_loop_gps(self):
        if not self.loop.df.dropna().empty and all(self.loop.df):
            return True
        else:
            return False

    def has_station_gps(self):
        if not self.is_borehole():
            if not self.line.df.dropna().empty and all(self.line.df):
                return True
            else:
                return False
        else:
            return False

    def has_any_gps(self):
        if any([self.has_collar_gps(), self.has_geometry(), self.has_station_gps(), self.has_loop_gps()]):
            return True
        else:
            return False

    def has_all_gps(self):
        if self.is_borehole():
            if not all([self.has_loop_gps(), self.has_collar_gps(), self.has_geometry()]):
                return False
            else:
                return True
        else:
            if not all([self.has_loop_gps(), self.has_station_gps()]):
                return False
            else:
                return True

    def has_d7(self):
        return self.data.RAD_tool.map(lambda x: x.D == 'D7').all()

    def has_xy(self):
        components = self.get_components()
        if 'X' in components and 'Y' in components:
            return True
        else:
            return False

    def get_gps_units(self):
        """
        Return the type of units being used for GPS ('m' or 'ft')
        :return: str
        """
        unit = None
        if self.has_loop_gps():
            unit = self.loop.get_units()
        elif self.has_collar_gps():
            unit = self.collar.get_units()
        elif self.has_station_gps():
            unit = self.line.get_units()

        return unit

    def get_crs(self):
        """
        Return the PEMFile's CRS, or create one from the note in the PEM file if it exists.
        :return: Proj CRS object
        """

        pass

    def is_pp(self):
        # TODO THIS METHOD, RUN A PP THROUGH MAXWELL
        pass

    def is_mmr(self):
        pass

    def is_borehole(self):
        pass


if __name__ == "__main__":
    apem = PEMParser().parse("../../sample_files/Raglan/718-3701 XYZT.pem")
    print(apem)
    a = TEM("../../sample_files/TEM/718-3701 XYZT.tem")
    print(a)


class TemplateTEM:
    """
    Generates the bare minimum PEM file for the
    """

    def __init__(self, uni, opr, cur, lp_l, lp_w, client, grid, linehole,
                 loop, date, survtype, m_unit, synctype,
                 tb, ramp, num_chn, rds, rx_id, rx_ver, rx_verd, ppval, a_coil):
        # assert uni in ALLOWED_UNITS
        # assert survtype in ALLOWED_SURVTYPE
        # assert m_unit in ALLOWED_MUNITS
        # assert synctype in ALLOWED_SYNCTYPE
        self.uni = uni
        self.opr = opr
        self.cur = cur
        self.lp_l = lp_l
        self.lp_w = lp_w
        self.client = client
        self.grid = grid
        self.linehole = linehole
        self.loop = loop
        self.date = date
        self.survtype = survtype
        self.m_unit = m_unit
        self.synctype = synctype
        self.timebase = tb
        self.ramp = ramp
        self.num_chn = num_chn
        self.rds = rds
        self.rx_id = rx_id
        self.rx_ver = rx_ver
        self.rx_verd = rx_verd
        self.ppval = ppval
        self.a_coil = a_coil

    def compile_tem(self):
        return EMPTY_TEM_HEADER.format(uni=self.uni,
                                       opr=self.opr,
                                       cur=self.cur,
                                       lp_l=self.lp_l,
                                       lp_w=self.lp_w,
                                       client=self.client,
                                       grid=self.grid,
                                       linehole=self.linehole,
                                       loop=self.loop,
                                       date=self.date,
                                       survtype=self.survtype,
                                       m_unit=self.m_unit,
                                       synctype=self.synctype,
                                       tb=self.timebase,
                                       ramp=self.ramp,
                                       num_chn=self.num_chn,
                                       rds=self.rds,
                                       rx_id=self.rx_id,
                                       rx_ver=self.rx_ver,
                                       rx_verd=self.rx_verd,
                                       ppval=self.ppval,
                                       a_coil=self.a_coil)
