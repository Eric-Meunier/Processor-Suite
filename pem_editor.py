from pem_parser import PEM_Parser, PEM_File


class PEMFileEditor:
    """
    Class for making edits and generating plots from PEM_Files
    """
    def __init__(self):
        self.active_file = None
        self.parser = PEM_Parser()

    def open_file(self, file_path):
        self.active_file = self.parser.parse(file_path)

    def generate_plot(self):
        raise NotImplementedError
