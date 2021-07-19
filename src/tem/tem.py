# PEMPRO_VER = "0.11.6"
#
# EMPTY_TEM_HEADER = \
#     "TEM File Created by Crone PEMPro {ver}\n" \
#     "LINE: {linehole} DATATYPE:TEM CONFIG:FIXEDLOOP ELEV:{elev} UNITS:{uni} CURRENT:{cur} " \
#     "TXTURNS:{tx_turns} BFREQ:{bfreq} DUTYCYCLE:50.000 ONTIME:{tb_ms} OFFTIME:{tb_ms} &\n" \
#     "TURNON:0.000 TURNOFF:{ramp_ms} TIMINGMARK:{tmemark} RXAREAZ:{a_coil} RXAREAX:{a_coil} RXAREAY:{a_coil} RXDIPOLE:YES TXDIPOLE:NO &"
#
# def EMPTY_TEM_LOOP(lst_of_coords):
#     for i, coord in enumerate(lst_of_coords):
#         s = f"LV{i+1}X:}"
#
# EMPTY_TEM_LOOP = \
#     "LV1X:50.00 LV1Y:50.00 LV1Z:0.00 & \n"
#     "LV2X:50.00 LV2Y:-50.00 LV2Z:0.00 & \n"
#     "LV3X:-50.00 LV3Y:-50.00 LV3Z:0.00 & \n"
#     "LV4X:-50.00 LV4Y:50.00 LV4Z:0.00"
# TEMPLATE_DEFAULT = {"uni": 'nT/s',
#                     "cur": "1000",
#                     "lp_l": "100",
#                     "lp_w": "100",
#                     "client": "NAME_CLIENT",
#                     "grid": "NAME_GRID",
#                     "linehole": "NAME_SURVEYLINE",
#                     "loop": "NAME_LOOP",
#                     "date": "January 01, 1900",
#                     "m_unit": 'Metric',
#                     "survtype": "Surface",
#                     "synctype": "Crystal-Master",
#                     "tb": "100",
#                     "ramp": "1500",
#                     "num_chn": "66",
#                     "rds": "100",
#                     "rx_id": "999",
#                     "rx_ver": "9.99",
#                     "rx_verd": "Jan01,1990",
#                     "ppval": "1000",
#                     "a_coil": "500"}
#
# TEMPLATE_BHFLUX = {"uni": 'picoTeslas',
#                    "m_unit": 'Metric',
#                    "survtype": "BH-FLUX",
#                    "ppval": "1000",
#                    "a_coil": "500"}
#
# TEMPLATE_BHXY = {"uni": 'nanoTesla/sec',
#                  "m_unit": 'Metric',
#                  "survtype": "Borehole",
#                  "ppval": "1000",
#                  "a_coil": "2800"}
#
# def TEM_CHANNELS(ch_times):
#     return "/TIMES(ms)=" + ", ".join(ch_times)
#
# class PEM2TEM:
#
#     pass
#
# class TemplateTEM:
#     """
#     Generates the bare minimum PEM file for the
#     """
#     def __init__(self, uni, opr, cur, lp_l, lp_w, client, grid, linehole,
#                  loop, date, survtype, m_unit, synctype,
#                  tb, ramp, num_chn, rds, rx_id, rx_ver, rx_verd, ppval, a_coil):
#         # assert uni in ALLOWED_UNITS
#         # assert survtype in ALLOWED_SURVTYPE
#         # assert m_unit in ALLOWED_MUNITS
#         # assert synctype in ALLOWED_SYNCTYPE
#         self.uni = uni
#         self.opr = opr
#         self.cur = cur
#         self.lp_l = lp_l
#         self.lp_w = lp_w
#         self.client = client
#         self.grid = grid
#         self.linehole = linehole
#         self.loop = loop
#         self.date = date
#         self.survtype = survtype
#         self.m_unit = m_unit
#         self.synctype = synctype
#         self.timebase = tb
#         self.ramp = ramp
#         self.num_chn = num_chn
#         self.rds = rds
#         self.rx_id = rx_id
#         self.rx_ver = rx_ver
#         self.rx_verd = rx_verd
#         self.ppval = ppval
#         self.a_coil = a_coil
#
#     @classmethod
#     def compile_empty_pem_metric_bh(cls, survey='flux'):
#         """
#         Compile an empty pem file
#         :param survey: anyof str ('flux', 'induction')
#         """
#         d = deepcopy(TEMPLATE_DEFAULT)
#         if survey == 'flux':
#             for k in TEMPLATE_BHFLUX.keys():
#                 d[k] = TEMPLATE_BHFLUX[k]
#             return cls(**d)
#         else:
#             for k in TEMPLATE_BHFLUX.keys():
#                 d[k] = TEMPLATE_BHFLUX[k]
#             return cls(**d)
#
#     def compile_pem(self):
#         return EMPTY_PEM_HEADER.format(uni=self.uni,
#                                        opr=self.opr,
#                                        cur=self.cur,
#                                        lp_l=self.lp_l,
#                                        lp_w=self.lp_w,
#                                        client=self.client,
#                                        grid=self.grid,
#                                        linehole=self.linehole,
#                                        loop=self.loop,
#                                        date=self.date,
#                                        survtype=self.survtype,
#                                        m_unit=self.m_unit,
#                                        synctype=self.synctype,
#                                        tb=self.timebase,
#                                        ramp=self.ramp,
#                                        num_chn=self.num_chn,
#                                        rds=self.rds,
#                                        rx_id=self.rx_id,
#                                        rx_ver=self.rx_ver,
#                                        rx_verd=self.rx_verd,
#                                        ppval=self.ppval,
#                                        a_coil=self.a_coil)