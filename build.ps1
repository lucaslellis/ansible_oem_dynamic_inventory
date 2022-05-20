$git_tag = git describe --tags --abbrev=0

New-Item -Path "." -ItemType "directory" -Name "build" -Force

Compress-Archive -Path ".\ansible_oem_inventory.py", ".\config.ini.template", ".\LICENSE", `
                       ".\README.md", ".\static_vars.json.template" `
                 -DestinationPath ".\build\ansible_oem_inventory_${git_tag}.zip" `
                 -Force
