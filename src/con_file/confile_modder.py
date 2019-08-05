import re
import os
from os.path import isfile, join

samples_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "sample_files")

class ConFile:
    def __init__(self, filepath):
        self.filepath = filepath

        self.re_line = re.compile(r'(?:Line|Hole)\s(.*?)\s+[ZXY]\s+Component',)
        self.re_section = re.compile('')
        self.name = os.path.splitext(os.path.basename(self.filepath))[0]

    # def


def read_file(filepath):
    pass


def main():
    file_names = [f for f in os.listdir(samples_path) if isfile(join(samples_path, f)) and f.split('.')[-1].lower() =='con']
    file_paths = []

    for file in file_names:
        file_paths.append(join(samples_path, file))

    confile = ConFile

    for file in file_paths:
        confile(file)

if __name__ == '__main__':
    main()