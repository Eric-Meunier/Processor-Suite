"""
Module for testing the parser. This is not used in the Crone Plots application.
"""

# import numpy as np # Not used yet, not sure if it's needed yet.
from legacy_pem_parser import PEMParser
import pprint


def main():
    parser = PEMParser()
    # Note: This script must be run from repository's root directory
    ch = parser.parse("sample_files/CH934ZM.PEM")
    z = parser.parse("sample_files/Z.PEM")

    pprint.pprint((z.get_headers()))
    # pprint.pprint((ch.get_headers()))

    # pprint.pprint(ch.get_tags())
    pprint.pprint(z.get_tags())

    # pprint.pprint(ch.get_survey())
    pprint.pprint(z.get_survey())

    #z.get_unique_stations()

    """
     Plotting section below. Will probably create and call a plotter class in the future.
    """
    # x=station_number
    # y=[y[6] for y in decay]
    # plt.plot(x,y)
    # plt.show()


if __name__ == '__main__':
    main()

