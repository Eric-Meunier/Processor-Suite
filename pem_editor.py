from pem_parser import PEM_Parser, PEM_File
import matplotlib.pyplot as plt
from matplotlib.figure import Figure


class PEMFileEditor:
    """
    Class for making edits and generating plots from PEM_Files
    """
    def __init__(self):
        self.active_file = None
        self.parser = PEM_Parser()

    def open_file(self, file_path):
        self.active_file = self.parser.parse(file_path)

    def generate_placeholder_plots(self):
        # Temporary placeholder plots
        # Use as guide for creating generate_plots
        plots_dict = {}

        for reading in self.active_file.get_survey():
            station_number = reading['station_number']

            if station_number not in plots_dict:
                fig = Figure()
                ax = fig.add_subplot(111)
                ax.set_title('Station Number ' + str(station_number))
                ax.set_xlabel('Channel Number (By Index)')
                ax.set_ylabel('Amplitude (' + self.active_file.get_tags()['Unit'] + ')')
                fig.subplots_adjust(bottom=0.15)

                plots_dict[station_number] = {'fig': fig}
                plots_dict[station_number]['ax'] = ax

            ax = plots_dict[station_number]['ax']
            y = reading['decay']
            ax.plot(range(len(y)), y, '-', linewidth=0.8)

        plots = [plot_data['fig'] for station_number, plot_data in plots_dict.items()]

        return plots

    def generate_plots(self):
        """
        :return: A list of Figure objects representing plots of the data found inside active_file
        """
        raise NotImplementedError


if __name__ == "__main__":
    # Code to test PEMFileEditor
    editor = PEMFileEditor()
    editor.open_file('CH934ZM.PEM')
    editor.generate_placeholder_plots()