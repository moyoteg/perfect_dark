#!/usr/bin/env python3
"""Seg builder for learn_29_custom_seg_script — curriculum SEG_SCRIPT demo."""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tools.pdmap.seg import write_box_seg

NAME = "learn_29_custom_seg_script"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"bg_{NAME}.seg")


def main():
    write_box_seg(OUT, half=2500, height=2000)
    print(f"wrote {OUT} ({os.path.getsize(OUT)} bytes)")


if __name__ == "__main__":
    main()
