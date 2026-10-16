#!/bin/sh
set -eu
rm -rf build dist
python3 -m pip wheel . --no-deps --wheel-dir dist