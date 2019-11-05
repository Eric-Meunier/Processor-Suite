from src.pem.pem_parser import PEMParser
from src.pem.pem_serializer import PEMSerializer
import os


if __name__ == '__main__':
    parser = PEMParser
    saver = PEMSerializer
    # # sample_files = os.path.join(os.path.dirname(os.path.dirname(application_path)), "sample_files")
    sample_files_dir = r'C:\_Data\2019\Nantou BF\Surface\__Semapoun 115+\PEM'
    file_names = [f for f in os.listdir(sample_files_dir) if
                  os.path.isfile(os.path.join(sample_files_dir, f)) and f.lower().endswith('.pem')]
    pem_files = []

    for file in file_names:
        filepath = os.path.join(sample_files_dir, file)
        pem_file = parser().parse(filepath)
        print('File: ' + filepath)

        loop = pem_file.header.get('Loop')
        line = pem_file.header.get('LineHole')
        # new_name = f"{line.split('00E')[0]}EL{loop.split('-')[-1]}"
        new_name = f"{line.split('E')[0]}00E"
        print(f"Loop: {loop}\nLine: {line}\nNew Name: {new_name}\n\n")
        pem_file.header['LineHole'] = new_name

        pem_file.filepath = os.path.join(filepath)
        save_file = saver().serialize(pem_file)
        # print(save_file, file=open(pem_file.filepath, 'w+'))
