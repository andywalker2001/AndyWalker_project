import Myfuncs
import re
import itertools
import time
import ast
import folium
from collections import defaultdict
from functools import reduce
from operator import or_

#=================================================
#Initialization
#=================================================
slant_range = []
terrain_masking = []

default = {
    "live": True,
    "range_limit": 50,
    "latitude": 50.827276295494734,
    "longitude": 0.2060202678627942,
    "altitude": 50.00,
    "frame_delay": .1
}

# Create the map object
my_map = folium.Map(location=[default["latitude"], default["longitude"]], zoom_start=7)

range_0 = Myfuncs.calculate_radar_range(rcs_sqm=1)
range_10 = Myfuncs.calculate_radar_range(rcs_sqm=10)
range_20 = Myfuncs.calculate_radar_range(rcs_sqm=100)
range_30 = Myfuncs.calculate_radar_range(rcs_sqm=1000)

# Print terminal header row
print(f"{'Degrees (Az)':<15} {'Degrees (El)':<15} {'Slant Range (km)':<20} {'Masked?':<14} {'Received Time (ms)':<15}")
print("-" * 88)

#=================================================
#Loop
#=================================================
while True:
    if (default["live"]):
        try:
            latitude, longitude, altitude, units = Myfuncs.read_gps_coordinates("COM6")
        except KeyboardInterrupt:
            print("Stopped reading GPS.")
        except Exception as exc:
            latitude = default["latitude"]
            longitude=default["longitude"]
            altitude=default["altitude"]
        r = Myfuncs.call_api(str(latitude), str(longitude), altitude, str(default["range_limit"]))
    else:
        with open(r"./Data/data.txt", "r", encoding="utf-8") as f:
            r_str = f.read()
            r = ast.literal_eval(r_str)
            latitude = default["latitude"]
            longitude=default["longitude"]
            altitude=default["altitude"]

    my_map = Myfuncs.plot_map (latitude, longitude, range_10, range_20, range_30, my_map)

    r_list = Myfuncs.filter_list(r)
    for i in range(len(r_list)):
        
        radar = (latitude, longitude)
        plane = (r_list[i]["lat"], r_list[i]["lon"])
        
        radar += ((altitude),)
        plane += ((r_list[i]["alt_geom"] * 0.3048),)
        
        slant_range.append(Myfuncs.calculate_slant_range(radar, plane))
        terrain_masking.append(Myfuncs.get_masking(radar, plane, 5))
        
        print(f"{(str(round(slant_range[i][0], 3))):<15} {(str(round(slant_range[i][1], 3))):<7} \
            {(str(round(slant_range[i][2] / 1000, 2))):<20} {(str(reduce(or_, terrain_masking[i]))):<6} \
            {(time.time_ns() // 1_000_000):<15} ")

        if (reduce(or_, terrain_masking[i])):
            Myfuncs.plot_plane (radar[0:2], plane[0:2], my_map, r_list[i], "red")
        else:
            Myfuncs.plot_plane (radar[0:2], plane[0:2], my_map, r_list[i], "blue")
    print("-" * 88)
    time.sleep(default["frame_delay"])