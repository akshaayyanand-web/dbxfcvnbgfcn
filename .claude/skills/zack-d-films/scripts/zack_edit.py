#!/usr/bin/env python3
"""Builds the ffmpeg punch/shake -vf expression from an edit_map.json.

edit_map.json is a flat list of events:
  {"type": "punch", "time": 6.2, "duration": 0.4, "peak": 0.08}
  {"type": "shake", "time": 9.6, "duration": 0.3, "amount": 0.01}
("peak"/"amount" are optional, defaulting to the values below.)

Punch = brief zoom-in pulse (crop window shrinks toward center then relaxes
back over `duration` seconds). Shake = brief position jitter (crop window
oscillates around center then settles). Both are windowed in time so they
only affect frames inside [time, time+duration], and multiple events combine
additively (they aren't expected to overlap in practice).

Usage:
  zack_edit.py --edit-map edit_map.json --print-vf
  zack_edit.py --edit-map edit_map.json --input in.mp4 --output out.mp4
"""
import argparse
import json
import subprocess
import sys

DEFAULT_PUNCH_PEAK = 0.08    # fraction zoomed in at the pulse's center
DEFAULT_SHAKE_AMOUNT = 0.01  # fraction of frame width/height
SHAKE_HZ = 10.0               # oscillations per second while shaking


def _triangle_envelope(t0, t1):
    """0 outside [t0,t1], ramping linearly up to 1 at the midpoint and back down."""
    tm = (t0 + t1) / 2
    rise = f"((t-{t0})/{tm - t0})"
    fall = f"(({t1}-t)/{t1 - tm})"
    return f"if(between(t,{t0},{tm}),{rise},if(between(t,{tm},{t1}),{fall},0))"


def build_zoom_expr(events):
    terms = []
    for e in events:
        if e["type"] != "punch" or e.get("duration", 0) <= 0:
            continue
        t0, t1 = e["time"], e["time"] + e["duration"]
        peak = e.get("peak", DEFAULT_PUNCH_PEAK)
        terms.append(f"({peak}*{_triangle_envelope(t0, t1)})")
    return "+".join(terms) if terms else "0"


def build_shake_expr(events, axis):
    terms = []
    for e in events:
        if e["type"] != "shake" or e.get("duration", 0) <= 0:
            continue
        t0, t1 = e["time"], e["time"] + e["duration"]
        amount = e.get("amount", DEFAULT_SHAKE_AMOUNT)
        phase = "0" if axis == "x" else "1.5708"  # quarter-turn offset so x/y don't move in lockstep
        osc = f"sin(2*PI*{SHAKE_HZ}*(t-{t0})+{phase})"
        terms.append(f"({amount}*{osc}*{_triangle_envelope(t0, t1)})")
    return "+".join(terms) if terms else "0"


def build_vf(events, width, height):
    zoom = build_zoom_expr(events)
    shake_x = build_shake_expr(events, "x")
    shake_y = build_shake_expr(events, "y")
    # Shrinking the crop window is a zoom-in; the trailing scale locks the
    # output back to a constant WxH since the crop's own w/h vary over time.
    crop_w = f"iw*(1-({zoom}))"
    crop_h = f"ih*(1-({zoom}))"
    crop_x = f"(in_w-out_w)/2+(in_w*({shake_x}))"
    crop_y = f"(in_h-out_h)/2+(in_h*({shake_y}))"
    return (
        f"crop=w='{crop_w}':h='{crop_h}':x='{crop_x}':y='{crop_y}',"
        f"scale={width}:{height},setsar=1"
    )


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--edit-map", required=True, help="path to edit_map.json")
    ap.add_argument("--width", type=int, default=1080)
    ap.add_argument("--height", type=int, default=1920)
    ap.add_argument("--print-vf", action="store_true",
                     help="print the -vf expression and exit (no ffmpeg call)")
    ap.add_argument("--input", help="input video (required unless --print-vf)")
    ap.add_argument("--output", help="output video (required unless --print-vf)")
    ap.add_argument("--fps", type=int, default=None,
                     help="normalize output fps (omit to keep source fps)")
    ap.add_argument("--preset", default="veryfast")
    ap.add_argument("--crf", default="16")
    args = ap.parse_args()

    with open(args.edit_map) as f:
        events = json.load(f)

    vf = build_vf(events, args.width, args.height)

    if args.print_vf:
        print(vf)
        return

    if not args.input or not args.output:
        sys.exit("--input and --output are required unless --print-vf is set")

    vf_chain = vf if args.fps is None else f"{vf},fps={args.fps}"
    cmd = [
        "ffmpeg", "-y", "-i", args.input,
        "-vf", vf_chain,
        "-c:v", "libx264", "-preset", args.preset, "-crf", str(args.crf),
        "-c:a", "copy",
        args.output,
    ]
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()
