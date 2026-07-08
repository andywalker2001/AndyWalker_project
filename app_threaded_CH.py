from flask import Flask, render_template, request, send_file, jsonify
import ast
import os
import threading
import folium
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import Myfuncs

app = Flask(__name__)

# Defaults (from AC_Range.py)
defaults = Myfuncs.set_location("COM5")

DATA_DIR = os.path.join(os.path.dirname(__file__), "Data")
MAP_PATH = os.path.join(DATA_DIR, "interactive_map.html")

# Prevents two masking threads from writing the map file simultaneously
_map_lock = threading.Lock()
_masking_status = {"running": False, "last": "never"}

@app.route("/")
def index():
    return render_template("index.html", defaults=defaults)


def _apply_masking_background(r_list, ts, snap, range_10, range_20, range_30):
    """
    Runs in a daemon thread after /update returns.
    Redraws the map with terrain-masking colours (red = masked, blue = clear)
    and overwrites the map file. The browser's /map_ts polling picks it up
    automatically when the file timestamp changes.
    """
    _masking_status["running"] = True
    try:
        lat, lon, alt = snap["latitude"], snap["longitude"], snap["altitude"]

        my_map = folium.Map(location=[lat, lon], zoom_start=9)
        my_map = Myfuncs.plot_map(lat, lon, range_10, range_20, range_30, my_map)

        def mask_one(item):
            radar3 = (lat, lon, alt)
            plane3 = (item["lat"], item["lon"], item["alt_geom"] * 0.3048)
            sr = Myfuncs.calculate_slant_range(radar3, plane3)
            num_seg = max(1, int(sr[3] / 1000))
            masked = any(Myfuncs.get_masking(radar3, plane3, num_seg))
            return item, masked

        # Run all masking calls in parallel — wait for slowest one only
        with ThreadPoolExecutor() as executor:
            results = list(executor.map(mask_one, r_list))

        radar2 = (lat, lon)
        for item, masked in results:
            col = "red" if masked else "blue"
            plane2 = (item["lat"], item["lon"])
            Myfuncs.plot_plane(radar2, plane2, my_map, item, col, item.get("nav_heading", 0))

        with _map_lock:
            my_map.save(MAP_PATH)

        _masking_status["last"] = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
    except Exception as exc:
        _masking_status["last"] = f"error: {exc}"
    finally:
        _masking_status["running"] = False

@app.route("/defaults", methods=["GET"])
def get_defaults():
    return jsonify(defaults)

@app.route("/update", methods=["POST"])
def update():
    payload = request.get_json() or {}
    # Update defaults with provided values
    try:
        if "live" in payload:
            defaults["live"] = bool(payload.get("live"))
        if "range_limit" in payload:
            defaults["range_limit"] = float(payload.get("range_limit"))
        if "latitude" in payload:
            defaults["latitude"] = float(payload.get("latitude"))
        if "longitude" in payload:
            defaults["longitude"] = float(payload.get("longitude"))
        if "altitude" in payload:
            defaults["altitude"] = float(payload.get("altitude"))

        # Recalculate ranges
        range_10 = Myfuncs.calculate_radar_range(rcs_sqm=10)
        range_20 = Myfuncs.calculate_radar_range(rcs_sqm=100)
        range_30 = Myfuncs.calculate_radar_range(rcs_sqm=1000)

        # Create a fresh map and draw range circles
        my_map = folium.Map(location=[defaults["latitude"], defaults["longitude"]], zoom_start=9)
        my_map = Myfuncs.plot_map(defaults["latitude"], defaults["longitude"], range_10, range_20, range_30, my_map)

        # Fetch aircraft data
        if defaults["live"]:
            r = Myfuncs.call_api(str(defaults["latitude"]), str(defaults["longitude"]), defaults["altitude"], str(defaults["range_limit"]))
        else:
            with open(os.path.join(DATA_DIR, "data.txt"), "r", encoding="utf-8") as f:
                r = ast.literal_eval(f.read())

        # Plot all aircraft immediately in blue and save — returns fast
        r_list = Myfuncs.filter_list(r)
        ts = datetime.fromtimestamp(r["now"] / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        radar = (defaults["latitude"], defaults["longitude"])
        for item in r_list:
            item["time"] = ts
            plane = (item["lat"], item["lon"])
            Myfuncs.plot_plane(radar, plane, my_map, item, "blue", item.get("nav_heading", 0))

        with _map_lock:
            my_map.save(MAP_PATH)

        # Kick off background thread to recolor with terrain masking
        threading.Thread(
            target=_apply_masking_background,
            args=(r_list, ts, defaults.copy(), range_10, range_20, range_30),
            daemon=True
        ).start()

        return jsonify({"status": "ok", "aircraft": len(r_list)})
    except Exception as exc:
        return jsonify({"status": "error", "error": str(exc)}), 500

@app.route("/masking_status")
def masking_status():
    """Let the client check whether background masking is still running."""
    return jsonify(_masking_status)

@app.route("/map")
def map_view():
    # Serve the generated folium map
    if os.path.exists(MAP_PATH):
        return send_file(MAP_PATH)
    else:
        return "Map not generated yet. Press Update.", 404

@app.route('/map_ts')
def map_timestamp():
    """Return the last-modified timestamp of the generated map file (ms since epoch)."""
    if os.path.exists(MAP_PATH):
        ts = int(os.path.getmtime(MAP_PATH) * 1000)
        return jsonify({"ts": ts})
    else:
        return jsonify({"ts": 0})

if __name__ == "__main__":
    app.run(debug=False)
