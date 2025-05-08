import os
import sys
import exifread
import folium
from datetime import datetime
from branca.colormap import LinearColormap
from folium.plugins import MarkerCluster
import glob
import pandas as pd
from progress.bar import Bar
import warnings

output_file = "map.html"

# function to decode google maps format
def dms_to_decimal(dms: str):
    import re
    
    # Regular expression to extract DMS components
    dms_pattern = re.compile(r'(\d+)[°](\d+)[\' ](\d+\.\d+)["]?([NSEW])')
    
    # Find all matches
    matches = dms_pattern.findall(dms)
    
    # Function to convert DMS to decimal degrees
    def convert_to_decimal(degrees, minutes, seconds, direction):
        decimal = float(degrees) + float(minutes)/60 + float(seconds)/3600
        if direction in ['S', 'W']:
            decimal = -decimal
        return decimal
    
    # Extract and convert latitude and longitude
    latitude = None
    longitude = None
    
    for match in matches:
        degrees, minutes, seconds, direction = match
        decimal = convert_to_decimal(degrees, minutes, seconds, direction)
        if direction in ['N', 'S']:
            latitude = decimal
        elif direction in ['E', 'W']:
            longitude = decimal
    
    return latitude, longitude

def get_import_path(file_name: str):
    if getattr(sys, 'frozen', False):
        base_dir = sys._MEIPASS  # PyInstaller sets this for bundled apps
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))

    path = os.path.join(base_dir, file_name)
    return os.path.normpath(path)

def getExcelMarker(file_name: str):
    try:
        df = pd.read_excel(file_name, sheet_name=None, header=0, engine='openpyxl')
    except FileNotFoundError:
        print(f"The additional file for makers with name '{file_name}' was not found.")
        return pd.DataFrame()
    
    # add sheetname as row
    for sheet in df:
        df[sheet]['type'] = sheet
    
    # concat to one big table
    result = pd.concat(df.values(), ignore_index=True)
    return result

def extract_geotags(photo_path: str):
    extended_path = u"\\\\?\\" + photo_path     # no 256 file limit with prefix
    with open(extended_path, 'rb') as f:
        try:
            tags = exifread.process_file(f, details=False)
        except:
            print("Could not read EXIF Data.")
            return None, None, None
        
    latitude = tags.get('GPS GPSLatitude')
    longitude = tags.get('GPS GPSLongitude')
    date_taken = tags.get('EXIF DateTimeOriginal')
    if latitude and longitude and date_taken:

        lat_ref_tag = tags.get('GPS GPSLatitudeRef')
        lon_ref_tag = tags.get('GPS GPSLongitudeRef')

        # check for non existing fields
        if lat_ref_tag:
            lat_ref = lat_ref_tag.values
        else:
            lat_ref = 'N'   # standard for GER

        if lon_ref_tag:
            lon_ref = lon_ref_tag.values
        else:
            lon_ref = 'E'   # standard for GER

        # exit for empty values - lat and lon are 0 in this case
        if lat_ref == '' or lon_ref == '':
            return None, None, None
        
        # Extracting degrees, minutes, and seconds for latitude
        degrees_num = latitude.values[0].num
        degrees_den = latitude.values[0].den
        minutes_num = latitude.values[1].num
        minutes_den = latitude.values[1].den
        seconds_num = latitude.values[2].num
        seconds_den = latitude.values[2].den
        
        # Converting to decimal degrees
        lat_degrees = float(degrees_num) / float(degrees_den)
        lat_minutes = float(minutes_num) / float(minutes_den) / 60.0
        lat_seconds = float(seconds_num) / float(seconds_den) / 3600.0
        lat_value = lat_degrees + lat_minutes + lat_seconds

        # Adjusting latitude based on reference direction
        if lat_ref == 'S':
            lat_value *= -1
        
        # Extracting degrees, minutes, and seconds for longitude
        degrees_num = longitude.values[0].num
        degrees_den = longitude.values[0].den
        minutes_num = longitude.values[1].num
        minutes_den = longitude.values[1].den
        seconds_num = longitude.values[2].num
        seconds_den = longitude.values[2].den
        
        # Converting to decimal degrees
        lon_degrees = float(degrees_num) / float(degrees_den)
        lon_minutes = float(minutes_num) / float(minutes_den) / 60.0
        lon_seconds = float(seconds_num) / float(seconds_den) / 3600.0
        lon_value = lon_degrees + lon_minutes + lon_seconds

        # Adjusting longitude based on reference direction
        if lon_ref == 'W':
            lon_value *= -1

        # Extracting capture date
        date_taken_str = str(date_taken)
        date_taken_obj = datetime.strptime(date_taken_str, '%Y:%m:%d %H:%M:%S')
        
        return lat_value, lon_value, date_taken_obj
    else:
        return None, None, None

def search_photos(directories: list[str]):
    photo_paths = []
    for directory in directories:
        # Search for .jpg, .jpeg and .heic files
        patterns = ['**/*.jpg', '**/*.jpeg', '**/*.heic']
        for pattern in patterns:
            full_pattern = os.path.join(directory, pattern)
            new_paths = glob.glob(full_pattern, recursive=True)
            photo_paths.extend(new_paths)
        print('Found {} photos in path {}'.format(len(photo_paths), directory))
    return photo_paths

def html_icon(short_name: str):
    html = f'''
                <div style="
                    display: inline-block;
                    width: 20px; height: 20px;
                    background-color: gray;
                    color: white;
                    border-radius: 50%;
                    text-align: center;
                    line-height: 20px;
                    font-family: Arial;
                    font-size: 7pt;
                ">{short_name}</div>
            '''
    return html

def show_on_map(geotags_dates: list[tuple[float,float,datetime]], photo_paths: list[str], marker_file_name: str):
    
    # create empty map
    map = folium.Map(tiles=None, max_zoom=21)

    # use two tilesets
    tilesetOSMG = r'https://tile.openstreetmap.de/{z}/{x}/{y}.png'
    tilesetOPNV = r'https://tileserver.memomaps.de/tilegen/{z}/{x}/{y}.png'
    folium.TileLayer(tiles=tilesetOSMG, name="Open Street Map Deutschland", overlay=False, max_zoom=21, attr='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors', show=True).add_to(map)
    folium.TileLayer(tiles=tilesetOPNV, name="ÖPNV Karte", overlay=False, max_zoom=18, attr='Map <a href="https://memomaps.de/">memomaps.de</a> <a href="http://creativecommons.org/licenses/by-sa/2.0/">CC-BY-SA</a>, map data &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors', show=False).add_to(map)

    # create custom grey cluster icon with inline css
    icon_create_function = """
    function(cluster) {
    var childCount = cluster.getChildCount(); 
    return new L.DivIcon({ html: '<div style="background-color: rgba(131, 131, 131, 0.91);"> <span> ' + childCount + '</span></div>', className: 'marker-cluster', iconSize: new L.Point(40, 40) });
    }
    """

    # change options to more cluster and showing all pics at highest zoom
    clusterOptions = {
        "maxClusterRadius": 40,
        "disableClusteringAtZoom": 19
    }
    
    marker_cluster = MarkerCluster(name="Fotos", icon_create_function=icon_create_function, options=clusterOptions).add_to(map)

    # Define color map for the time range
    colormap = LinearColormap(['violet', 'indigo', 'blue', 'green', 'yellow', 'orange', 'red'], vmin=0, vmax=1)

    # count not shown geotags
    notShownCounter = 0

    # insert geotags
    for geotag_date, photo_path in zip(geotags_dates, photo_paths):
        lat, lon, date_taken = geotag_date
        photo_path_4web = "\\" + photo_path.replace("\\","/")
        popup_html = f"<img src='{photo_path_4web}' style='width:200px;height:200px;'><br> <a>{date_taken} </a> <a href='{photo_path_4web} 'target='_blank'> -> Link</a>"

        # Determine marker color based on capture date
        if date_taken:
            delta_days = (datetime.now() - date_taken).days
            normalized_delta = min(1, max(0, delta_days / 2190))  # Normalize to range [0, 1] for the colormap
            marker_color = colormap(normalized_delta)
        else:
            marker_color = 'gray'

        if lat is None or date_taken is None:
            notShownCounter += 1
        else:
            folium.Marker(location=[lat, lon], popup=folium.Popup(popup_html, max_width=300, lazy=True), tooltip="Bild",
                        icon=folium.Icon(color = 'gray', icon_color=marker_color)).add_to(marker_cluster)
        
    # load excel file with markers
    fg = folium.FeatureGroup(name="Standorte", show=True).add_to(map)
    addMarkersExcel = getExcelMarker(marker_file_name)

    if not addMarkersExcel.empty:
        for row in addMarkersExcel.iterrows():
            title = row[1]["title"]
            coordMaps = row[1]["location"]
            lat, lon = dms_to_decimal(coordMaps)
            text = row[1]["text"]
            type = row[1]["type"]

            custom_icon = folium.DivIcon(html_icon(type))
            folium.Marker(location=[lat, lon],popup=folium.Popup(text), tooltip=title, icon=custom_icon).add_to(fg)
    
    # Add legend as horizontal color bar
    with open(get_import_path('legend.html'), 'r') as file: 
        legend_html = file.read()

    map.get_root().html.add_child(folium.Element(legend_html))

    map.get_root().header.add_child(folium.CssLink(get_import_path('custom_marker_cluster.css')))
    
    # add layer control after everything is added
    folium.LayerControl().add_to(map)

    # save map
    map.save(output_file)
    print(f"Map generated with {len(geotags_dates)-notShownCounter} geotags. Check {output_file} for the result.")

def main():
    # manual
    print("\nThis program searches for *.jpg and *.jpeg pictures in a specified path, extracts the geotags information and shows the location on a map. It loads the excel file 'standorte.xlsx' in the same folder with a specific format and shows the additional locations on the map.\n \n")

    # Prompt user for folder paths
    folder_paths_input = input("Please copy a folder path from your explorer or several folder paths separated by commas to search for photos: ")
    folder_paths = folder_paths_input.split(',')
    
    # Search for photos in the specified folders
    print("Searching...")
    photo_paths = search_photos(folder_paths)

    # extract geotags and show progress bar
    geotags = []
    bar = Bar('Collecting GPS Data', max=len(photo_paths))
    warnings.filterwarnings('ignore') 
    for photo_path in photo_paths:
        geotag = extract_geotags(photo_path)
        bar.next()
        if geotag:
            geotags.append(geotag)
    bar.finish()
    warnings.filterwarnings('default')

    marker_file_name = folder_paths_input = input("\nDo you have additional locations you want to show? Enter excel file name in the same directory:")

    print("Creating map...")
    if geotags:
        show_on_map(geotags, photo_paths, marker_file_name)
    else:
        print("No geotagged photos found.")

    input("\nYou can close the window now or type enter.")

if __name__ == "__main__":
    main()