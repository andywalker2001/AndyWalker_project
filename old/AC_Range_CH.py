import Myfuncs
import re
import itertools
import time
import ast
from collections import defaultdict
from functools import reduce
from operator import xor

Live = False #True
limit_range = "70"

if Live:
#Get data from the ADS-B API
    try:
        latitude, longitude, altitude, units = Myfuncs.read_gps_coordinates("COM6")
    except KeyboardInterrupt:
        print("Stopped reading GPS.")
    except Exception as exc:
        #latitude = 42.04425
        #longitude = -91.627306
        #altitude = 260.00
        #South of Heathrow
        latitude = 50.827276295494734
        longitude = 0.2060202678627942
        altitude = 50.00

        #print(exc)
    r = Myfuncs.call_api(str(latitude), str(longitude), altitude, limit_range)
    
else:
#Just use canned data from an old file
    with open(r"./Data/data.txt", "r", encoding="utf-8") as f:
        r = ast.literal_eval(f.read())
    # Set radar position (same as the fallback location used in Live mode)
    latitude = 50.827276295494734
    longitude = 0.2060202678627942
    altitude = 50.00

r_list = r["ac"] #Extract the list of aircraft from the API response

keys_to_keep = {"lat", "lon", "alt_geom", "flight"} #Only keep the keys we need for plotting and range calculations
filtered_r = [{k: v for k, v in d.items() if k in keys_to_keep} for d in r_list]
really_filtered_r = [
    d for d in filtered_r #Only keep entries that have the "alt_geom" key, since we need altitude for range calculations
    if "alt_geom" in d
    ]
r_list = really_filtered_r #Update r_list to only include the filtered entries

with open(r"./Data/output.txt", "w") as g:
    print(r_list, file=g) #Write the filtered list of aircraft to a file for debugging purposes

range_0 = Myfuncs.calculate_radar_range(rcs_sqm=1)
range_10 = Myfuncs.calculate_radar_range(rcs_sqm=10)
range_20 = Myfuncs.calculate_radar_range(rcs_sqm=100)
range_30 = Myfuncs.calculate_radar_range(rcs_sqm=1000)

# CH better: make the file name an argument here rather than in the function
# which is more consistent with how the other files are named
my_map = Myfuncs.plot_map (latitude, longitude, range_10, range_20, range_30)

slant_range = []
terrain_masking = []

# Print header row
print(f"{'Degrees (Az)':<15} {'Degrees (El)':<15} {'Slant Range (km)':<20} {'Masked?':<14} {'Received Time (ms)':<15}")
print("-" * 88)

for i in range(len(r_list)):
    radar = (latitude, longitude)
    plane = (r_list[i]["lat"], r_list[i]["lon"])
    Myfuncs.plot_plane (radar, plane, my_map, r_list[i])
    
    radar += ((altitude),)
    plane += ((r_list[i]["alt_geom"] * 0.3048),)

    slant_range.append(Myfuncs.calculate_slant_range(radar, plane))
    terrain_masking.append(Myfuncs.get_masking(radar, plane, 5))
    
    # Extract and format values for cleaner printing
    azimuth = round(slant_range[i][0], 3)
    elevation = round(slant_range[i][1], 3)
    range_km = round(slant_range[i][2] / 1000, 2)
    
    # XOR all masking values together (True if odd number of obstacles block the signal)
    masking_values = terrain_masking[i][0]
    is_masked = False
    for value in masking_values:
        is_masked ^= value  # XOR operation: flips is_masked if value is True
    
    timestamp_ms = time.time_ns() // 1000000
    
    print(f"{azimuth:<15} {elevation:<15} {range_km:<20} {is_masked:<14} {timestamp_ms:<15}")
    