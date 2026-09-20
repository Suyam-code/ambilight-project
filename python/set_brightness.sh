#!/bin/bash
# Usage: ./set_brightness.sh 0.4
DIR="$HOME/ambilight-project/python"
TMP="$DIR/.brightness.tmp"
echo "$1" > "$TMP"
mv "$TMP" "$DIR/brightness.txt"
