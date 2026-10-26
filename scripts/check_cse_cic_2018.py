"""Compatibility entry point: native CSE schema audit; không chạy khi import."""
import runpy
import sys
from pathlib import Path

if __name__ == '__main__':
    sys.argv[1:1] = ['--dataset', 'CSE-CIC-IDS2018']
    runpy.run_path(str(Path(__file__).with_name('07_inspect_external.py')), run_name='__main__')
