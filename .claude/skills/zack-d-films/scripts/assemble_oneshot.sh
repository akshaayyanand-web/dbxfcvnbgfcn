#!/usr/bin/env bash
# One-shot final assembly for Phase 8: download blocks + narration, concat at
# a uniform fps, apply the punch/shake edit map, mix narration over ducked
# composite audio, trim, and PUT the result to a presigned URL -- all inside
# a single sandbox_exec call, since sandbox files aren't guaranteed to
# survive between separate calls.
#
# Usage: assemble_oneshot.sh <config.json> [workdir]
#
# config.json shape:
# {
#   "block_urls": ["https://.../block01.mp4", "https://.../block02.mp4", ...],
#   "narration_url": "https://.../narration.wav",
#   "edit_map": [{"type": "punch", "time": 6.2, "duration": 0.4}, ...],
#   "width": 1080, "height": 1920,
#   "output_path": "zack/output/final.mp4",
#   "presigned_put_url": "https://...",
#   "content_type": "video/mp4"
# }
set -euo pipefail

CONFIG="$1"
WORKDIR="${2:-zack}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

mkdir -p "$WORKDIR/blocks" "$WORKDIR/audio" "$WORKDIR/output"

WIDTH=$(jq -r '.width // 1080' "$CONFIG")
HEIGHT=$(jq -r '.height // 1920' "$CONFIG")
NARRATION_URL=$(jq -r '.narration_url' "$CONFIG")
OUTPUT_PATH=$(jq -r --arg d "$WORKDIR/output/final.mp4" '.output_path // $d' "$CONFIG")
PUT_URL=$(jq -r '.presigned_put_url' "$CONFIG")
CONTENT_TYPE=$(jq -r '.content_type // "video/mp4"' "$CONFIG")
jq -c '.edit_map' "$CONFIG" > "$WORKDIR/edit_map.json"

mapfile -t BLOCK_URLS < <(jq -r '.block_urls[]' "$CONFIG")

# --- download blocks + narration in parallel ---
pids=()
for i in "${!BLOCK_URLS[@]}"; do
  n=$(printf "%02d" $((i + 1)))
  curl -fsSL -o "$WORKDIR/blocks/block${n}.mp4" "${BLOCK_URLS[$i]}" &
  pids+=($!)
done
curl -fsSL -o "$WORKDIR/audio/narration.wav" "$NARRATION_URL" &
pids+=($!)
for p in "${pids[@]}"; do wait "$p"; done

# --- probe fps from the first block, never hardcode ---
RAW_FPS=$(ffprobe -v error -select_streams v:0 \
  -of default=noprint_wrappers=1:nokey=1 -show_entries stream=r_frame_rate \
  "$WORKDIR/blocks/block01.mp4")
FPS=$(python3 -c "n,d=('$RAW_FPS'.split('/')+['1'])[:2]; print(round(float(n)/float(d)))")

# --- pass 1: concat blocks at a uniform fps ---
: > "$WORKDIR/concat.txt"
for f in "$WORKDIR"/blocks/block*.mp4; do
  echo "file '$(cd "$(dirname "$f")" && pwd)/$(basename "$f")'" >> "$WORKDIR/concat.txt"
done
ffmpeg -y -f concat -safe 0 -i "$WORKDIR/concat.txt" -r "$FPS" \
  -c:v libx264 -preset veryfast -crf 16 -c:a aac \
  "$WORKDIR/composite.mp4"

# --- pass 2: punch/shake vf + narration mix + trim, single encode ---
VF=$(python3 "$SCRIPT_DIR/zack_edit.py" --edit-map "$WORKDIR/edit_map.json" \
  --width "$WIDTH" --height "$HEIGHT" --print-vf)

NARR_DUR=$(ffprobe -v error -show_entries format=duration \
  -of default=noprint_wrappers=1:nokey=1 "$WORKDIR/audio/narration.wav")
TRIM_END=$(python3 -c "print(float('$NARR_DUR') + 0.4)")

mkdir -p "$(dirname "$OUTPUT_PATH")"
ffmpeg -y -i "$WORKDIR/composite.mp4" -i "$WORKDIR/audio/narration.wav" \
  -filter_complex "[0:v]${VF}[v];[0:a]volume=0.25[sfx];[1:a][sfx]amix=inputs=2:duration=longest:dropout_transition=0[araw];[araw]loudnorm=I=-16:TP=-1.5[a]" \
  -map "[v]" -map "[a]" -t "$TRIM_END" \
  -c:v libx264 -preset veryfast -crf 16 -c:a aac \
  "$OUTPUT_PATH"

# --- QC probe (surface it; the caller checks dimensions/duration/audio) ---
ffprobe -v error -show_entries stream=width,height,codec_type \
  -show_entries format=duration -of json "$OUTPUT_PATH"

# --- upload to the presigned URL from media_upload (same call as assembly) ---
curl -f -X PUT -H "Content-Type: $CONTENT_TYPE" --data-binary "@$OUTPUT_PATH" "$PUT_URL"

echo "DONE output=$OUTPUT_PATH"
