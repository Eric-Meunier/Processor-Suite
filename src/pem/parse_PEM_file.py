"""
Module for testing the parser. This is not used in the Crone Plots application.
"""
import os
import sys
# TODO: Add separate scripts or tests directory and move there to avoid needing these
src_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.append(src_dir)

# import numpy as np # Not used yet, not sure if it's needed yet.
from pem.pem_parser import PEMParser
from pem.pem_serializer import PEMSerializer
import pprint


def main():
    parser = PEMParser()
    # Note: This script must be run from repository's root directory
    ch = parser.parse("sample_files/CH934ZM.PEM")
    z = parser.parse("sample_files/Z.PEM")

    # pprint.pprint((z.get_headers()))
    # # pprint.pprint((ch.get_headers()))
    #
    # # pprint.pprint(ch.get_tags())
    # pprint.pprint(z.get_tags())
    #
    # # pprint.pprint(ch.get_survey())
    # pprint.pprint(z.get_survey())

    serializer = PEMSerializer()

    print(serializer.serialize(z))

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

