#!/usr/bin/env bash

git_tag=`git describe --tags --abbrev=0`

cp "ansible_oem_inventory.py" "config.ini.template" "LICENSE" "README.md" build/

cd build/
echo $git_tag
sed -i -E -e "s/[\$]Id[\$]/${git_tag}/g" ansible_oem_inventory.py

zip --junk-paths --move ansible_oem_inventory_${git_tag}.zip \
"ansible_oem_inventory.py" \
"config.ini.template" \
"LICENSE" \
"README.md"
