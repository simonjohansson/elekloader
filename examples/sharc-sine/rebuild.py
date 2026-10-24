# SPDX-License-Identifier: GPL-2.0-or-later
"""Rebuild this prelinked sine from pinned Selache source and checked H1 inputs."""
import argparse
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'sharc-sine-probe'))
from h1 import build  # noqa: E402


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('selache', type=Path)
    parser.add_argument('--source-dir', type=Path, default=HERE)
    parser.add_argument('--out', type=Path, default=HERE / 'sine.sharc.json')
    args = parser.parse_args()
    try:
        build(args.selache, args.source_dir / 'sine.c', args.source_dir / 'entry.c', args.out)
        print('BUILT:', args.out)
    except (ValueError, OSError) as error:
        sys.exit('FAIL: %s' % error)
