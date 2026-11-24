"""Entry point PyInstaller bundles into the desktop app."""
import sys

from token_meter.app import main

if __name__ == "__main__":
    sys.exit(main())
