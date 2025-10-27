# -*- coding: utf-8 -*-
import h5py
import argparse

import h5py

filename_hdf = 'resnet.h5'

def h5_tree(val, pre=''):
    items = len(val)
    for key, val in val.items():
        items -= 1
        if items == 0:
            # the last item
            if type(val) == h5py._hl.group.Group:
                print(pre + '└── ' + key)
                h5_tree(val, pre+'    ')
            else:
                try:
                    print(pre + '└── ' + key + ' (%d)' % len(val))
                except TypeError:
                    print(pre + '└── ' + key + ' (scalar)')
        else:
            if type(val) == h5py._hl.group.Group:
                print(pre + '├── ' + key)
                h5_tree(val, pre+'│   ')
            else:
                try:
                    print(pre + '├── ' + key + ' (%d)' % len(val))
                except TypeError:
                    print(pre + '├── ' + key + ' (scalar)')

def main(filename_hdf):
    """Open the HDF5 file and print its structure."""
    try:
        with h5py.File(filename_hdf, 'r') as hf:
            print(f"File structure of '{filename_hdf}':")
            h5_tree(hf)
    except OSError as e:
        print(f"Error opening file '{filename_hdf}': {e}")

if __name__ == "__main__":
    # Set up argument parser to take the HDF5 file as a parameter
    parser = argparse.ArgumentParser(description="Display the structure of an HDF5 file.")
    parser.add_argument("filename", type=str, help="Path to the HDF5 (.h5) file.")
    
    # Parse the argument
    args = parser.parse_args()

    # Call the main function with the filename
    main(args.filename)
