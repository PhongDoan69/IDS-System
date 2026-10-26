"""Compatibility entry point: đọc đúng header Label trong Lable.csv."""
import runpy
import sys
from pathlib import Path

if __name__ == '__main__':
    sys.argv[1:1] = ['--dataset', 'CIC-UNSW-NB15']
    runpy.run_path(str(Path(__file__).with_name('07_inspect_external.py')), run_name='__main__')
