#!/bin/bash


sleep 2
CALL_DIR=$PWD
SCRIPT_RELATIVE_PATH=$(dirname "$0")
CURDIR="$CALL_DIR/$SCRIPT_RELATIVE_PATH"

python3 "$SCRIPT_RELATIVE_PATH/Ohana_fileServer.py" &
exit 0
