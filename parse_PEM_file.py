import re
import matplotlib.pyplot as plt
import numpy as np # Not used yet, not sure if it's needed yet.
from pem_parser import PEM_Parser
import pprint


def main():
    parser = PEM_Parser()
    ch = parser.parse("CH934ZM.PEM")
    z = parser.parse("Z.PEM")


    #print(z.get_headers())
    #pprint.pprint(ch.get_survey())
    pprint.pprint((z.get_headers()))
    pprint.pprint((ch.get_headers()))

    pprint.pprint(ch.get_tags())
    pprint.pprint(z.get_tags())

    pprint.pprint(ch.get_survey())
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

