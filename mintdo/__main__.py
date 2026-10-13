"""Entry point: python3 -m mintdo"""
import sys

from mintdo.app import run

if __name__ == "__main__":
    sys.exit(run(sys.argv))
