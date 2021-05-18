from src.pem.pem_file import PEMParser
import os
from pathlib import Path
from random import choices, randrange

import logging
import sys

logger = logging.getLogger(__name__)


class PEMGetter:
    """
    Class to get a list of PEM files from a testing directory. Used for testing.
    """
    def __init__(self):
        self.pem_parser = PEMParser()

    def get_pems(self, folder=None, subfolder=None, number=None, selection=None,  file=None, random=False,
                 incl=None):
        """
        Retrieve a list of PEMFiles
        :param folder: str, folder from which to retrieve files
        :param number: int, number of files to selected
        :param selection: int, index of file to select
        :param subfolder: str, name of the folder within the client folder to look into
        :param file: str, name the specific to open
        :param random: bool, select random files. If no number is passed, randomly selects the number too.
        :param incl: str, text to include in the file name.
        :return: list of PEMFile objects.
        """

        def add_pem(filepath):
            """
            Parse and add the PEMFile to the list of pem_files.
            :param filepath: Path object of the PEMFile
            """
            if not filepath.exists():
                raise ValueError(f"File {filepath.name} does not exists.")

            logger.info(f'Getting File {filepath.name}.')

            try:
                pem_file = self.pem_parser.parse(filepath)
            except Exception as e:
                logger.error(f"{str(e)}")
                return

            pem_files.append(pem_file)

        sample_files_dir = Path(__file__).parents[2].joinpath('sample_files')

        if folder:
            sample_files_dir = sample_files_dir.joinpath(folder)
            if not sample_files_dir.exists():
                raise ValueError(f"Folder {folder} does not exist.")
            if subfolder:
                sample_files_dir = sample_files_dir.joinpath(subfolder)
                if not sample_files_dir.exists():
                    raise ValueError(f"Subfolder {subfolder} does not exist.")

        pem_files = []

        # Pool of available files is all PEMFiles in PEMGetter files directory.
        if incl is not None:
            available_files = list(sample_files_dir.rglob(f'*{incl}*.PEM'))
        else:
            available_files = list(sample_files_dir.rglob(f'*.PEM'))
        # print(f"Available files: {', '.join([str(a) for a in available_files])}")

        if random:
            if not number:
                # Generate a random number of files to choose from
                number = randrange(5, min(len(available_files), 15))
            elif number > len(available_files):
                number = len(available_files)

            random_selection = choices(available_files, k=number)

            for file in random_selection:
                add_pem(file)

        else:
            if number:
                for file in available_files[:number]:
                    filepath = sample_files_dir.joinpath(file)
                    add_pem(filepath)
                    # pem_files.append((pem_file, None))  # Empty second item for ri_files

            elif selection is not None and not selection > len(available_files):
                filepath = sample_files_dir.joinpath(available_files[selection])
                add_pem(filepath)
                # pem_files.append((pem_file, None))  # Empty second item for ri_files

            elif file is not None:
                filepath = sample_files_dir.joinpath(file)
                add_pem(filepath)

            else:
                for file in available_files:
                    filepath = sample_files_dir.joinpath(file)
                    add_pem(filepath)
                    # pem_files.append((pem_file, None))  # Empty second item for ri_files

        pem_list = '\n'.join([str(f.filepath) for f in pem_files])
        if not pem_list:
            raise ValueError(f"No PEM files found in {sample_files_dir}.")
        logger.info(f"Collected PEM files: {pem_list}")
        return pem_files
