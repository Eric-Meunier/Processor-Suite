from pem.pem_parser import PEMParser, PEMFile
from matplotlib.figure import Figure
from collections import OrderedDict


class PEMFileEditor:
    """
    Class for making edits to and generating plots from PEM_Files
    """
    def __init__(self):
        self.active_file = None
        self.parser = PEMParser()

    def open_file(self, file_path):
        """
        Sets the active file. All subsequent operations will be done on the file contained at file_path.
        :param file_path: string containing path to a PEM file
        """
        self.active_file = self.parser.parse(file_path)

    def generate_placeholder_plots(self):
        """
        :return: A list of matplotlib.figure objects representing the data found inside of the active file
        """
        # Temporary placeholder plots
        # Use as guide for creating generate_plots
        plots_dict = OrderedDict()
        print(self.active_file.get_data())

        for reading in self.active_file.get_data():
            station_number = reading['Station']
            print('hi')

            if station_number not in plots_dict:
                fig = Figure()
                ax = fig.add_subplot(111)
                ax.set_title('Station ' + str(station_number))
                ax.set_xlabel('Channel Number (By Index)')
                ax.set_ylabel('Amplitude (' + self.active_file.get_tags()['Units'] + ')')
                fig.subplots_adjust(bottom=0.15)

                plots_dict[station_number] = {'fig': fig}
                plots_dict[station_number]['ax'] = ax

            ax = plots_dict[station_number]['ax']
            y = reading['Data']
            ax.plot(range(len(y)), y, '-', linewidth=0.8)

        plots = [plot_data['fig'] for station_number, plot_data in plots_dict.items()]
        return plots

    def generate_plots(self):
        """
        :return: A list of matplotlib.figure objects representing the data found inside of the active file
        """
        raise NotImplementedError


if __name__ == "__main__":
    # Code to test PEMFileEditor
    editor = PEMFileEditor()
    editor.open_file('CH934ZM.PEM')
    editor.generate_placeholder_plots()