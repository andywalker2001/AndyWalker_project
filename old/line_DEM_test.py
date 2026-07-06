import time
import requests
import pandas as pd
from shapely.geometry import LineString
from shapely.ops import transform
from pyproj import Transformer


EPQS_URL = "https://epqs.nationalmap.gov/v1/json"


def densify_line_iowa(lonlat_coords, spacing_m=120):
    """
    Densify a lon/lat line at approximately spacing_m intervals.
    Uses NAD83 / UTM zone 15N, appropriate for most of Iowa.
    
    Parameters
    ----------
    lonlat_coords : list of tuple
        [(lon, lat), (lon, lat), ...]
    spacing_m : float
        Sampling interval in meters.
    
    Returns
    -------
    list of dict
        Each dict has distance_m, lon, lat.
    """

    # Iowa is mostly UTM Zone 15N
    to_utm = Transformer.from_crs("EPSG:4326", "EPSG:26915", always_xy=True)
    to_lonlat = Transformer.from_crs("EPSG:26915", "EPSG:4326", always_xy=True)

    line_lonlat = LineString(lonlat_coords)
    line_utm = transform(to_utm.transform, line_lonlat)

    total_length = line_utm.length

    distances = list(range(0, int(total_length), spacing_m))
    if distances[-1] != int(total_length):
        distances.append(total_length)

    samples = []

    for d in distances:
        pt_utm = line_utm.interpolate(d)
        lon, lat = to_lonlat.transform(pt_utm.x, pt_utm.y)

        samples.append({
            "distance_m": float(d),
            "lon": lon,
            "lat": lat
        })

    return samples


def get_usgs_elevation(lon, lat, units="Meters", timeout=30):
    """
    Query USGS EPQS for elevation at one lon/lat point.
    """
    
    params = {
        "x": lon,
        "y": lat,
        "units": units,
        "output": "json"
    }

    r = requests.get(EPQS_URL, params=params, timeout=timeout)
    r.raise_for_status()

    data = r.json()
  

    # Current EPQS response usually has:
    # data["value"] = elevation
    # data["unit"] = "Meters" or "Feet"
    elev = data.get("value")
    print(lon, lat, elev)
    
    if elev is None:
        return None

    elev = float(elev)

    # USGS services sometimes use very negative values for missing data
    if elev < -999999:
        return None

    return elev


def elevation_profile_from_line(lonlat_coords, spacing_m=30, sleep_s=0.05):
    """
    Build an elevation profile from a lon/lat line.
    """

    samples = densify_line_iowa(lonlat_coords, spacing_m=spacing_m)

    rows = []

    for sample in samples:
        elev_m = get_usgs_elevation(sample["lon"], sample["lat"], units="Meters")

        rows.append({
            "distance_m": sample["distance_m"],
            "lon": sample["lon"],
            "lat": sample["lat"],
            "elevation_m": elev_m
        })

        # Be polite to the public API
        time.sleep(sleep_s)
        

    return pd.DataFrame(rows)


# must be long/lat !!!!
line_coords = [(-92.378556, 42.529313),  (-92.609251, 42.307843)]

df = elevation_profile_from_line(line_coords, 1500)
print(df)