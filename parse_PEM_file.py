import re
import matplotlib.pyplot as plt
import numpy as np # Not used yet, not sure if it's needed yet.
from pem_parser import PEM_Parser


def main():
    parser = PEM_Parser()
    z = parser.parse("Z.PEM")
    ch = parser.parse("CH934ZM.PEM")

    print(z.get_unique_stations())
    print(ch.get_unique_stations())

    """
     Plotting section below. Will probably create and call a plotter class in the future.
    """
    # x=station_number
    # y=[y[6] for y in decay]
    # plt.plot(x,y)
    # plt.show()


if __name__ == '__main__':
    main()

