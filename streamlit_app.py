import streamlit as st
import time
import subprocess
import sys
from pathlib import Path
import Myfuncs

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "Data"
MAP_PATH = DATA_DIR / "interactive_map.html"

st.set_page_config(layout="wide", page_title="AC Range — Streamlit")
#42.044323003948186, -91.62728056174687, 260.00 - Bowman Woods
st.sidebar.title("AC Range Controls")
live = st.sidebar.checkbox("Live", value=True)
range_limit = st.sidebar.number_input("Range limit (miles)", value=50, step=1)
latitude = st.sidebar.text_input("Latitude", value=str(50.827276295494734))
longitude = st.sidebar.text_input("Longitude", value=str(0.2060202678627942))
altitude = st.sidebar.number_input("Altitude (m)", value=50.0, step=0.1)
refresh_interval = st.sidebar.slider("Auto-refresh interval (seconds, 0=off)", 0, 30, 0)
update_btn = st.sidebar.button("Update Map")

st.sidebar.markdown("---")
st.sidebar.write("Map is saved to: ")
st.sidebar.write(str(MAP_PATH))

# Controls to run AC_Range.py continuously as a background process
start_acr = st.sidebar.button("Start AC_Range")
stop_acr = st.sidebar.button("Stop AC_Range")

LOG_PATH = DATA_DIR / "ac_range.log"

status = st.sidebar.empty()

def acr_is_running():
    proc = st.session_state.get("acr_proc")
    if proc is None:
        return False
    return proc.poll() is None

def tail_log(path, n=50):
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        return "".join(lines[-n:])
    except FileNotFoundError:
        return "(no log yet)"

# Start/stop handling
if start_acr:
    if not acr_is_running():
        # open log file for append
        logf = open(LOG_PATH, "a", encoding="utf-8")
        # launch AC_Range.py with same python executable
        proc = subprocess.Popen([sys.executable, str(BASE_DIR / "AC_Range.py")], cwd=str(BASE_DIR), stdout=logf, stderr=logf)
        st.session_state["acr_proc"] = proc
        st.session_state["acr_logf"] = logf

if stop_acr:
    proc = st.session_state.get("acr_proc")
    logf = st.session_state.get("acr_logf")
    if proc is not None:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except Exception:
            proc.kill()
    if logf is not None:
        try:
            logf.close()
        except Exception:
            pass
    st.session_state["acr_proc"] = None
    st.session_state["acr_logf"] = None

# Show AC_Range status and tail of log
if acr_is_running():
    proc = st.session_state.get("acr_proc")
    status.success(f"AC_Range running (pid {proc.pid})")
else:
    status.info("AC_Range not running")

st.sidebar.markdown("### AC_Range Log")
st.sidebar.text_area("log", value=tail_log(LOG_PATH, n=50), height=200)

def generate_map():
    try:
        # Acquire aircraft data
        if live:
            r = Myfuncs.call_api(str(latitude), str(longitude), altitude, str(range_limit))
        else:
            with open(DATA_DIR / "data.txt", "r", encoding="utf-8") as f:
                r = eval(f.read())

        # Calculate range circles
        range_10 = Myfuncs.calculate_radar_range(rcs_sqm=10)
        range_20 = Myfuncs.calculate_radar_range(rcs_sqm=100)
        range_30 = Myfuncs.calculate_radar_range(rcs_sqm=1000)

        my_map = Myfuncs.plot_map(float(latitude), float(longitude), range_10, range_20, range_30)

        r_list = Myfuncs.filter_list(r)

        for item in r_list:
            radar = (float(latitude), float(longitude), float(altitude))
            plane = (item["lat"], item["lon"], item["alt_geom"] * 0.3048)
            masking = Myfuncs.get_masking(radar, plane, 5)
            if any(masking):
                Myfuncs.plot_plane(radar[0:2], plane[0:2], my_map, item, "red")
            else:
                Myfuncs.plot_plane(radar[0:2], plane[0:2], my_map, item, "blue")

        return True, f"Updated map with {len(r_list)} aircraft"
    except Exception as exc:
        return False, str(exc)


# Trigger map generation when Update pressed or first load
if update_btn or "last_generated" not in st.session_state:
    ok, msg = generate_map()
    st.session_state["last_generated"] = time.time()
    if ok:
        status.success(msg)
    else:
        status.error(msg)

# Display map (controls live in sidebar)
st.header("Map")
if MAP_PATH.exists():
    with open(MAP_PATH, "r", encoding="utf-8") as f:
        map_html = f.read()
    st.iframe(map_html, height=700)
else:
    st.info("Map not generated yet. Click Update Map or Manual Refresh.")


if refresh_interval > 0:
    # Auto-refresh using streamlit-autorefresh if available
    try:
        from streamlit_autorefresh import st_autorefresh
        st_autorefresh(interval=refresh_interval * 1000, limit=None, key="auto")
    except Exception:
        st.sidebar.warning("Install streamlit-autorefresh for automatic polling")
