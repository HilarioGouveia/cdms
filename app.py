import sys
import os

# Garante a resolução dos pacotes 'cdms' e 'cgs' em 'src'
sys.path.insert(0, os.path.abspath("src"))

from cdms.adapters.ui.studio import run_studio


def main():
    run_studio()


if __name__ == "__main__":
    main()
