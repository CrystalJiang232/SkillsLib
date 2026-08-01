#!/bin/bash

source /etc/profile

mkdir -p bin
for dir in */; do
    base="${dir%/}"
    for i in tmp bak bin utils; do [[ "$base" == *"$i"* ]] && continue 2; done
    target="bin/${base}.skill"
    if [[ -e "$target" ]]; then
        n=1
        while [[ -e "${target}.bak.${n}" ]]; do
            ((n++))
        done
        mv "$target" "${target}.bak.${n}"
    fi
    python utils/package_skill.py $base bin/
    rm -rf utils/__pycache__/
done