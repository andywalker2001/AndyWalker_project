from flask import Flask, render_template, request, send_file, jsonify
import os
import Myfuncs

app = Flask(__name__)

# Defaults (from AC_Range.py)
defaults = Myfuncs.set_location("COM5")

DATA_DIR = os.path.join(os.path.dirname(__file__), "Data")
MAP_PATH = os.path.join(DATA_DIR, "interactive_map.html")

@app.route("/")
def index():
    return render_template("index.html", defaults=defaults)

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

        # Generate the map (Myfuncs.plot_map saves to Data/interactive_map.html)
        Myfuncs.plot_map(defaults["latitude"], defaults["longitude"], range_10, range_20, range_30)

        return jsonify({"status": "ok"})
    except Exception as exc:
        return jsonify({"status": "error", "error": str(exc)}), 500

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
    app.run(debug=True)
