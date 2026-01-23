import json
import os
import time
from pathlib import Path

from rpi_ws281x import PixelStrip, Color

# ======================
# HARDWARE CONFIG
# ======================
# Two rings, both 22 LEDs
LED1_COUNT = 22
LED1_PIN = 18
LED1_DMA = 10
LED1_CHANNEL = 0

LED2_COUNT = 22
LED2_PIN = 13
LED2_DMA = 11
LED2_CHANNEL = 1

LED_FREQ_HZ = 800000
LED_INVERT = False

# Default brightness (can be overridden by command)
DEFAULT_BRIGHTNESS = 160

# Where Streamlit writes the command
CMD_PATH = Path("/tmp/lighthouse_cmd.json")

OFF = Color(0, 0, 0)

# ======================
# COLOR HELPERS
# ======================
def parse_colour(c: str) -> Color:
    v = (c or "").strip().lower()
    # common OSM/Seamark values: white, red, green, yellow
    if v in ("white", "w"):
        return Color(255, 255, 255)
    if v in ("red", "r"):
        return Color(255, 0, 0)
    if v in ("green", "g"):
        return Color(0, 255, 0)
    if v in ("yellow", "y"):
        # yellow looks strong; slightly warmer amber
        return Color(255, 180, 0)
    # fallback: orange (your chosen look)
    return Color(255, 45, 0)

def clamp01(x: float) -> float:
    return 0.0 if x < 0 else (1.0 if x > 1.0 else x)

def scale_color(col: Color, scale: float) -> Color:
    # rpi_ws281x Color packs GRB internally, but we cannot unpack safely here.
    # Instead we scale by selecting typical channels via construction.
    # We only use a few fixed colors, so approximate scaling:
    # Use per-color presets by mapping based on identity is hard.
    # Practical approach: rebuild from intended RGB values in command (see below).
    return col

# ======================
# RING / SECTOR MAPPING
# ======================
def deg_to_idx(deg: float, n: int) -> int:
    # 0..360 -> 0..n-1
    d = deg % 360.0
    return int((d / 360.0) * n) % n

def fill_sector(pixels, n, start_deg, end_deg, col):
    """
    Fill inclusive sector on a ring.
    Handles wrap-around (e.g. 300..40).
    """
    try:
        s = float(start_deg)
        e = float(end_deg)
    except Exception:
        return

    s_idx = deg_to_idx(s, n)
    e_idx = deg_to_idx(e, n)

    if s_idx == e_idx:
        # could mean very small or full ring; assume small and set one
        pixels[s_idx] = col
        return

    if s_idx < e_idx:
        for i in range(s_idx, e_idx + 1):
            pixels[i] = col
    else:
        # wrap
        for i in range(s_idx, n):
            pixels[i] = col
        for i in range(0, e_idx + 1):
            pixels[i] = col

def render_sectors(n, sectors, default_col):
    # base ring is dark/off unless sectors specify
    pixels = [OFF for _ in range(n)]
    if not sectors:
        # no sector data, fill whole ring with default color
        for i in range(n):
            pixels[i] = default_col
        return pixels

    # If sectors exist, paint them
    for s in sectors:
        col = parse_colour(s.get("colour", "")) or default_col
        start_deg = s.get("sector_start", "")
        end_deg = s.get("sector_end", "")
        fill_sector(pixels, n, start_deg, end_deg, col)
    return pixels

# ======================
# BLINK ENGINE
# ======================
def blink_gate(t_in_period: float, on_fraction: float) -> float:
    """
    Simple lighthouse blink gate: on for (period * on_fraction), off otherwise.
    Returns 1.0 (on) or 0.0 (off).
    """
    on_time = max(0.05, on_fraction)  # ensure some visible on time
    return 1.0 if t_in_period < on_time else 0.0

def apply_brightness_rgb(rgb, brightness_0_255: int) -> Color:
    b = clamp01(brightness_0_255 / 255.0)
    r = int(rgb[0] * b)
    g = int(rgb[1] * b)
    bl = int(rgb[2] * b)
    return Color(r, g, bl)

def color_to_rgb_like(col: Color):
    # We do not unpack Color safely; instead we keep RGB in command for scaling.
    return (255, 45, 0)

# ======================
# MAIN
# ======================
def main():
    # Initialize strips with default brightness
    strip1 = PixelStrip(LED1_COUNT, LED1_PIN, LED_FREQ_HZ, LED1_DMA, LED_INVERT, DEFAULT_BRIGHTNESS, LED1_CHANNEL)
    strip2 = PixelStrip(LED2_COUNT, LED2_PIN, LED_FREQ_HZ, LED2_DMA, LED_INVERT, DEFAULT_BRIGHTNESS, LED2_CHANNEL)
    strip1.begin()
    strip2.begin()

    last_cmd_mtime = 0.0
    cmd = None

    # current animation state
    t0 = time.monotonic()

    while True:
        # Reload command if changed
        try:
            st = CMD_PATH.stat()
            if st.st_mtime > last_cmd_mtime:
                last_cmd_mtime = st.st_mtime
                with CMD_PATH.open("r", encoding="utf-8") as f:
                    cmd = json.load(f)
                # reset blink phase when new lighthouse selected
                t0 = time.monotonic()
        except FileNotFoundError:
            cmd = None
        except Exception:
            # ignore malformed command, keep last good
            pass

        # If no command, keep off
        if not cmd:
            for i in range(LED1_COUNT):
                strip1.setPixelColor(i, OFF)
            for i in range(LED2_COUNT):
                strip2.setPixelColor(i, OFF)
            strip1.show()
            strip2.show()
            time.sleep(0.2)
            continue

        # Read parameters
        period = float(cmd.get("period_s", 3.0) or 3.0)
        on_fraction = float(cmd.get("on_fraction", 0.18) or 0.18)  # 18% on-time
        brightness = int(cmd.get("brightness", DEFAULT_BRIGHTNESS) or DEFAULT_BRIGHTNESS)

        default_rgb = cmd.get("default_rgb", [255, 45, 0])
        default_col = apply_brightness_rgb(default_rgb, brightness)

        sectors = cmd.get("sectors", []) or []

        # Render sector base colors (unscaled RGB provided per sector if possible)
        # If Streamlit sends only "colour", we map via parse_colour.
        base1 = render_sectors(LED1_COUNT, sectors, parse_colour(cmd.get("main_colour", "")) or default_col)
        base2 = render_sectors(LED2_COUNT, sectors, parse_colour(cmd.get("main_colour", "")) or default_col)

        # Blink gate
        now = time.monotonic()
        t = (now - t0) % period
        gate = blink_gate(t, period * on_fraction)

        # Apply gate: when off, set all OFF
        if gate < 0.5:
            for i in range(LED1_COUNT):
                strip1.setPixelColor(i, OFF)
            for i in range(LED2_COUNT):
                strip2.setPixelColor(i, OFF)
        else:
            # show sector colors during "on"
            for i in range(LED1_COUNT):
                strip1.setPixelColor(i, base1[i])
            for i in range(LED2_COUNT):
                strip2.setPixelColor(i, base2[i])

        strip1.show()
        strip2.show()
        time.sleep(0.01)

if __name__ == "__main__":
    # Must run as root because ws281x uses /dev/mem on many setups
    if os.geteuid() != 0:
        print("Run with sudo: sudo env_lighthouse/bin/python led_controller.py")
        raise SystemExit(1)
    main()
