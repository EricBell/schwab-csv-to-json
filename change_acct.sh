#!/bin/bash

if [ $# -ne 1 ]; then
    echo "Usage: $0 <account_number>"
    exit 1
fi

for f in *.csv; do
    sed -i "1s/$1/acct/" "$f"
done
