"""Allows `python -m bandcamp_aotd <command>`."""
import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
