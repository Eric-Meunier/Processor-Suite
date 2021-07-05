import re


def convert_station(station):
    """
    Converts a single station name into a number, negative if the stations was S or W
    :return: Integer station number
    """
    # Ensure station is a string
    station = str(station).upper()
    if re.match(r"-?\d+(S|W)", station):
        station = (-int(re.sub(r"[SW]", "", station)))
    else:
        station = (int(re.sub(r"[EN]", "", station)))
    return station
