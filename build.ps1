# Build dist\speeddisk.exe (Windows). Requires Python 3.
$v = "$env:TEMP\sd-venv"
if (-not (Test-Path "$v\Scripts\python.exe")) { python -m venv $v }
& "$v\Scripts\python.exe" -m pip install -q windows-curses pyinstaller
& "$v\Scripts\pyinstaller.exe" -F -n speeddisk --distpath dist --workpath "$env:TEMP\sd-build" --specpath "$env:TEMP\sd-build" --icon "$PSScriptRoot\assets\speeddisk.ico" speeddisk.py
