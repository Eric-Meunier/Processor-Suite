class PEMFile:
    """
    Class for storing PEM file data for easy access
    """

    # Constructor
    def __init__(self, tags, loop_coords, line_coords, notes, header, data):
        self.tags = tags
        self.loop_coords = loop_coords
        self.line_coords = line_coords
        self.notes = notes
        self.header = header
        self.data = data

    def get_tags(self):
        return self.tags

    def get_loop_coords(self):
        return self.loop_coords

    def get_line_coords(self):
        return self.line_coords

    def get_notes(self):
        return self.notes

    def get_header(self):
        return self.header

    def get_data(self):
        return self.data

    def get_components(self):
        components = [reading['component'] for reading in self.data]
        return components

    def get_unique_stations(self):
        unique_stations = {n for n in
                           [reading['Station'] for reading in self.data]}
        return unique_stations