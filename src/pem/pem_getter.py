from src.pem.pem_file import PEMParser
import os
from pathlib import Path
from random import choices, randrange

import logging
import sys

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

file_format = logging.Formatter('\n%(asctime)s - %(filename)s (%(funcName)s)\n%(levelname)s: %(message)s',
                                datefmt='%m/%d/%Y %I:%M:%S %p')
stream_format = logging.Formatter('%(filename)s (%(funcName)s)\n%(levelname)s: %(message)s')

stream_handler = logging.StreamHandler(stream=sys.stdout)
stream_handler.setLevel(logging.INFO)
stream_handler.setFormatter(stream_format)

file_handler = logging.FileHandler(filename='err.log', mode='w')
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(file_format)

logger.addHandler(stream_handler)
logger.addHandler(file_handler)


class PEMGetter:
    """
    Class to get a list of PEM files from a testing directory. Used for testing.
    """
    def __init__(self):
        self.parser = PEMParser()

    def get_pems(self, client=None, number=None, selection=None, subfolder=None, file=None, random=False):
        """
        Retrieve a list of PEMFiles
        :param client: str, folder from which to retrieve files
        :param number: int, number of files to selected
        :param selection: int, index of file to select
        :param subfolder: str, name of the folder within the client folder to look into
        :param file: str, name the specific to open
        :param random: bool, select random files. If no number is passed, randomly selects the number too.
        :return: list of PEMFile objects.
        """

        def add_pem(filepath):
            """
            Parse and add the PEMFile to the list of pem_files.
            :param filepath: Path object of the PEMFile
            """
            logger.info(f'Getting File {filepath.name}.')

            try:
                pem_file = self.parser.parse(filepath)
            except Exception as e:
                logger.error(f"{str(e)}")
                return

            pem_files.append(pem_file)

        sample_files_dir = Path(__file__).parents[2].joinpath('sample_files/PEMGetter files')

        if client:
            sample_files_dir = sample_files_dir.joinpath(client)
            if subfolder:
                sample_files_dir = sample_files_dir.joinpath(subfolder)

        pem_files = []

        if random:
            # Pool of available files is all PEMFiles in PEMGetter files directory.
            available_files = list(sample_files_dir.rglob('*.PEM'))
            if not number:
                # Generate a random number of files to choose from
                number = randrange(5, min(len(available_files), 15))
            elif number > len(available_files):
                number = len(available_files)

            random_selection = choices(available_files, k=number)

            for file in random_selection:
                add_pem(file)

        else:
            available_files = list(sample_files_dir.glob('*.PEM'))

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
                if filepath.exists():
                    add_pem(filepath)
                else:
                    logger.info(f"File {filepath.name} does not exists.")

            else:
                for file in available_files:
                    filepath = sample_files_dir.joinpath(file)
                    # pem_files.append((pem_file, None))  # Empty second item for ri_files
                    add_pem(filepath)

        return pem_files