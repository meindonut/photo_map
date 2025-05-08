photo_map is a a simple console based app to show the geotags of photos on a map.

How it works:
- start the exe file
- type or copy one ore more folder into console
- create an excel file like the example to show more information on the map
- open map.html and embed it

Technically:
- uses exifread to get the geotag
- optionally loads an excel file for additional tags
- use folium to show the map

Was coded in vsode/windows.

PS commands for Windows in virtual venv:
python -m venv .venv
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process -Force # when problems with admin rights
.venv/Scripts/activate.ps1
pip install -r requirements.txt

PS commands for dist:
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process -Force # when problems with admin rights
.venv/Scripts/activate.ps1 # if not already activated
pyinstaller --clean --onefile --name photo_map main.py