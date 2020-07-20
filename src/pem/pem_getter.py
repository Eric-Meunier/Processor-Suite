from src.pem.pem_file import PEMParser
import os


class PEMGetter:
    """
    Class to get a list of PEM files from a testing directory. Used for testing.
    """
    def __init__(self):
        self.parser = PEMParser

    def get_pems(self, client=None, number=None, selection=None, subfolder=None, file=None):
        """
        Retrieve a list of PEMFiles
        :param client: str, folder from which to retrieve files
        :param number: int, number of files to selected
        :param selection: int, index of file to select
        :return: list
        """
        sample_files_dir = os.path.join(
            os.path.dirname(
                os.path.dirname(
                    os.path.dirname(
                        os.path.abspath(__file__)))),
            'sample_files/PEMGetter files')
        if client:
            sample_files_dir = os.path.join(sample_files_dir, client)
            if subfolder:
                sample_files_dir = os.path.join(sample_files_dir, subfolder)

        file_names = [f for f in os.listdir(sample_files_dir) if
                      os.path.isfile(os.path.join(sample_files_dir, f)) and f.lower().endswith('.pem')]
        pem_files = []

        if number:
            for file in file_names[:number]:
                filepath = os.path.join(sample_files_dir, file)
                pem_file = self.parser().parse(filepath)
                print(f'PEMGetter: Getting File {os.path.basename(filepath)}')
                # pem_files.append((pem_file, None))  # Empty second item for ri_files
                pem_files.append(pem_file)
        elif selection is not None and not selection > len(file_names):
            filepath = os.path.join(sample_files_dir, file_names[selection])
            pem_file = self.parser().parse(filepath)
            print(f'PEMGetter: Getting File {os.path.basename(filepath)}')
            # pem_files.append((pem_file, None))  # Empty second item for ri_files
            pem_files.append(pem_file)
        elif file is not None:
            index = file_names.index(file)
            if index:
                filepath = os.path.join(sample_files_dir, file_names[index])
                pem_file = self.parser().parse(filepath)
                print(f'PEMGetter: Getting File {os.path.basename(filepath)}')
                pem_files.append(pem_file)
            else:
                print(f"Could not find file {file}")
        else:
            for file in file_names:
                filepath = os.path.join(sample_files_dir, file)
                pem_file = self.parser().parse(filepath)
                print(f'PEMGetter: Getting File {os.path.basename(filepath)}')
                # pem_files.append((pem_file, None))  # Empty second item for ri_files
                pem_files.append(pem_file)

        return pem_files