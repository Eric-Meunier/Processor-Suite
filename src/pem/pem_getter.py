from src.pem.pem_parser import PEMParser
import os


class PEMGetter:
    """
    Class to get a list of PEM files from a testing directory. Used for testing.
    """
    def __init__(self):
        self.parser = PEMParser

    def get_pems(self):
        # # sample_files = os.path.join(os.path.dirname(os.path.dirname(application_path)), "sample_files")
        sample_files_dir = r'C:\_Data\2019\_Mowgli Testing'
        file_names = [f for f in os.listdir(sample_files_dir) if
                  os.path.isfile(os.path.join(sample_files_dir, f)) and f.lower().endswith('.pem')]
        pem_files = []

        # file = os.path.join(sample_files, file_names[0])
        for file in file_names:
            filepath = os.path.join(sample_files_dir, file)
            pem_file = self.parser().parse(filepath)
            print(f'PEMGetter: Getting File {filepath}')
            # pem_files.append((pem_file, None))  # Empty second item for ri_files
            pem_files.append(pem_file)

        return pem_files