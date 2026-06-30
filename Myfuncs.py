from http.client import responses
from urllib import response
import pyproj
import requests
import numpy as np
import serial
import pynmea2
import math
import folium
import geopy
import openmeteo_requests

def calculate_slant_range(radar, plane):
    """
    Calculates the 3D slant range between two points.

    Parameters:
        lat1, lon1, lat2, lon2 : float (degrees)
        alt1, alt2 : float (meters)

    Returns:
        float: Slant range in meters
    """
    #Work on a spherical Earth model the az/el angles
    geod = pyproj.Geod(ellps='WGS84')
    fwd_azimuth, back_azimuth, distance = geod.inv(radar[1], radar[0], plane[1], plane[0])
    # Normalize negative azimuths (e.g., -10° becomes 350°)
    azimuth = (fwd_azimuth + 360) % 360
    
    # Calculate the difference in altitude
    delta_alt = plane[2] - radar[2]

    # Calculate the elevation angle (in radians, then converted to degrees)
    elevation_rad = math.atan2(delta_alt, distance)
    elevation = math.degrees(elevation_rad)
    
    #Work with Cartesion coordinates to get the slant range
    transformer = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:4978", always_xy=True) # WGS84 geodetic to ECEF Cartesian coordinates
    x1, y1, z1 = transformer.transform(radar[1], radar[0], radar[2]) # Note: transformer takes (lon, lat, alt)
    x2, y2, z2 = transformer.transform(plane[1], plane[0], plane[2])
    slant_range = np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2 + (z2 - z1) ** 2)
    
    output = [azimuth, elevation, slant_range]   
    return output

def read_gps_coordinates(serial_port='COM5', baud_rate=4800, timeout=1, max_attempts=50):
    """
    Read a GPS fix from a serial USB receiver.

    Parameters:
        serial_port: str - serial port for the GPS receiver
        baud_rate: int - communication speed (typically 4800 or 9600)
        timeout: float - read timeout in seconds
        max_attempts: int - maximum number of NMEA lines to try

    Returns:
        tuple: (latitude, longitude, altitude, altitude_units)

    Raises:
        RuntimeError: if the port cannot be opened or no valid GGA fix is read.
    """
    try:
        with serial.Serial(serial_port, baud_rate, timeout=timeout) as ser:
            for attempt in range(max_attempts):
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                if not line:
                    continue
                if line.startswith(('$GPGGA', '$GNGGA')):
                    try:
                        msg = pynmea2.parse(line)
                    except pynmea2.ParseError:
                        continue

                    if msg.latitude and msg.longitude:
                        altitude = float(msg.altitude) if msg.altitude not in (None, '') else None
                        return msg.latitude, msg.longitude, altitude, msg.altitude_units

            raise RuntimeError(f"No valid GPS fix read after {max_attempts} attempts.")
    except serial.SerialException as exc:
        raise RuntimeError(f"Could not open serial port {serial_port}: {exc}") from exc
    
def calculate_radar_range(pt_watts=250, gain_db=26, num_pulses=1000, freq_hz=2.45e9, rcs_sqm=1.0, s_min_watts=1e-13, loss_db=0):
    """
    Calculates the maximum radar range using coherent pulse integration.
    
    Parameters:
    pt_watts (float): Peak transmit power in Watts (W).
    gain_db (float): Antenna gain in decibels (dB).
    num_pulses (int): Number of coherently integrated pulses (N).
    freq_hz (float): Radar operating frequency in Hertz (Hz).
    rcs_sqm (float): Target Radar Cross Section (RCS) in square meters (m^2).
    s_min_watts (float): Minimum detectable signal power at the receiver in Watts (W).
    loss_db (float, optional): Total system/propagation losses in decibels (dB). Defaults to 0.
        
    Returns:
    float: Maximum radar detection range in meters (m).
    """
    # Speed of light in m/s
    c = 299792458 
    
    # Calculate wavelength (lambda = c / f)
    wavelength = c / freq_hz
    
    # Convert antenna gain from dB to linear scale: G_linear = 10^(G_dB / 10)
    gain_linear = 10 ** (gain_db / 10)
    
    # Convert system loss from dB to linear scale: L_linear = 10^(L_dB / 10)
    loss_linear = 10 ** (loss_db / 10)
    
    # Numerator: Pt * G^2 * lambda^2 * sigma * N
    numerator = pt_watts * (gain_linear ** 2) * (wavelength ** 2) * rcs_sqm * num_pulses
    
    # Denominator: (4 * pi)^3 * S_min * L
    denominator = ((4 * math.pi) ** 3) * s_min_watts * loss_linear
    
    # Calculate fourth root to solve for maximum Range (R)
    max_range = (numerator / denominator) ** 0.25
    
    return max_range

def call_api(latitude, longitude, altitude, limit_range="27", units="M"):
    """
    Pull aircraft data from the API 75 miles or less from the given GPS coordinates.
    The default location is the corner of the field by Bowman Woods in Cedar Rapids, IA
    Parameters:
        latitude, longitude : float (degrees)
        altitude : float (meters)
        units : str (measurement units)

    Returns:.
        r, the whole response from the API as a string
    """    
    url = "https://adsbexchange-com1.p.rapidapi.com/v2/lat/" + latitude + "/lon/" + longitude + "/dist/" + limit_range + "/"

    headers = {
	    "x-rapidapi-key": "a0fe71760fmsh977c0a9513c9347p10c707jsn8fa3607d5a53",
	    "x-rapidapi-host": "adsbexchange-com1.p.rapidapi.com",
	    "Content-Type": "application/json"
    }

    #Guard against bad/no response
    response = requests.get(url, headers=headers)

    # Check if the request was successful
    if response.status_code == 200:
        with open(r"./Data/data.txt", "w") as f:
            r = response.json()
            print(r, file=f)
        return r
    else:
        print(f"API request failed with status code: {response.status_code}")
        return None

def plot_map (latitude, longitude, range_10, range_20, range_30, my_map):
    """
    Plots the radar range circles on a map using Folium.
    
    Parameters:
    latitude (float): Latitude of the radar location.
    longitude (float): Longitude of the radar location.
    range_10 (float): Maximum radar range for 10 dBsm RCS in meters.
    range_20 (float): Maximum radar range for 20 dBsm RCS in meters.
    range_30 (float): Maximum radar range for 30 dBsm RCS in meters.
    
    Returns:
    my_map data item
    Saves an interactive map as "interactive_map.html".
    """
    # Define coordinates (Latitude, Longitude) for the center
    center_coordinates = [latitude, longitude]
    
    # Add a Circle for the radar location
    folium.Circle(
        location=[latitude, longitude],
        radius=10,
        color="purple",
        fill=True,
        fill_color="purple",
        popup="Radar Location",
    ).add_to(my_map)

    # Add Circles for the radar ranges
    folium.Circle(
        location=[latitude, longitude],
        radius=range_10,
        color="green",
        fill=False,
        popup="Calculated 10 dBsm Range",
    ).add_to(my_map)

    folium.Circle(
        location=[latitude, longitude],
        radius=range_20,
        color="yellow",
        fill=False,
        popup="Calculated 20 dBsm Range",
    ).add_to(my_map)

    folium.Circle(
        location=[latitude, longitude],
        radius=range_30,
        color="red",
        fill=False,
        popup="Calculated 30 dBsm Range",
    ).add_to(my_map)

    my_map.save(r"./Data/interactive_map.html")

    return(my_map)

def plot_plane (coord1, coord2, my_map, description, col = "blue"):
    """
    Plots a line on an existing map using Folium that is the vector from the sensor to the plane
    
    Parameters:
    coord1 (float): Latitude, Longitude of the radar location
    coord2 (float): Latitude, Longitude of the aircraft
    description (str): Description of the plane to show in the popup
    
    Returns:
    Nothing. Updates an interactive map called "interactive_map.html".
    """
    custom_string = "<br>".join(f"{k}={v}" for k, v in description.items())
    
    # Group the two points into a list for PolyLine
    points = [coord1, coord2]
    
    # Create the line layer and add it to the map
#    folium.PolyLine(
#        locations=points,
#        color=col,       # Line color
#        weight=3,           # Line thickness in pixels
#        opacity=0.8,        # Line transparency
#        tooltip=custom_string # Hover text
#    ).add_to(my_map)

    folium.Circle(
        location=coord2,
        radius=20,            # Radius explicitly set in meters
        color="green",
        fill=True,
        fill_color="green",
        fill_opacity=0.3,
        popup=custom_string # Hover text
    ).add_to(my_map)

    my_map.save(r"./Data/interactive_map.html")

def get_masking(coord1, coord2, num_segments):
    """
    Creates a line given 2 coordinates and divides it into "count" number of points.
    Then, it calls the OpenMeteo API to get the elevation at each point and returns a list of elevations.    
    
    Parameters:
    coord1 (float): Latitude, Longitude of the radar location
    coord2 (float): Latitude, Longitude of the aircraft
    count (int): Number of points to divide the line into

    Returns:
    list: A list of booleans indicating whether each point along the line is masked by terrain.
    """
    lat1, lon1, alt1 = coord1 #radar
    lat2, lon2, alt2 = coord2 #aircraft
    
    lats = []
    lons = []
    alts = []
    
    for i in range(num_segments + 1):
        fraction = i / num_segments
        # Linearly interpolate between the two points
        current_lat = lat1 + fraction * (lat2 - lat1)
        current_lon = lon1 + fraction * (lon2 - lon1)
        current_alt = alt1 + fraction * (alt2 - alt1)
        lats.append(current_lat)
        lons.append(current_lon)
        alts.append(current_alt)
    
    openmeteo = openmeteo_requests.Client()

    url = "https://api.open-meteo.com/v1/forecast"
    params = {
	    "latitude": lats,
    	"longitude": lons,
	    "hourly": ["temperature_2m", "precipitation", "wind_speed_10m"],
    	"current": ["temperature_2m", "relative_humidity_2m"],
    }

    try:
        responses = openmeteo.weather_api(url, params=params)

        terrain_masked = []

    # Process current data. The order of variables needs to be the same as requested.
        for i, response in enumerate(responses):
            current = response.Current()
            #current_temperature_2m = current.Variables(0).Value()
            #current_relative_humidity_2m = current.Variables(1).Value()
            if response.Elevation() < alts[i]:
                terrain_masked.append(False)
            else:
                terrain_masked.append(True)

        return (terrain_masked)
    except:
        #It's actually not that bad to return an incorrect False, it just means we look for a plane we can't sense
        return ([False])

def filter_list(r):
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
        
    return (r_list)