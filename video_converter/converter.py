#!/usr/bin/env python3

import subprocess
import json
from pathlib import Path

# Supported video extensions
VIDEO_EXTENSIONS = [
    ".mov", ".avi", ".mkv", ".mpg", ".mp4", ".wmv",
    ".flv", ".webm", ".vob", ".m4v", ".ts", ".m2ts", ".rm", ".rmvb", ".ogv"
]

# Audio codec groups
EFFICIENT_CODECS = ["aac", "opus", "vorbis"]
LEGACY_LOSSY_CODECS = ["mp3", "wma", "wma2", "ac3", "eac3", "dts", "atrac3"]
LOSSLESS_CODECS = ["flac", "alac", "pcm_s16le", "pcm_s24le", "pcm_s32le", "mlp"]


def get_streams(file_path):
    """Return all streams info using ffprobe"""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "stream=index,codec_type,codec_name,channels,bit_rate",
        "-of", "json",
        str(file_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        streams = json.loads(result.stdout).get("streams", [])
    except json.JSONDecodeError:
        streams = []
    return streams


def equivalent_aac_bitrate(codec, bitrate, channels):
    # Compute the target AAC LC bitrate with scaling and channel caps
    if not bitrate or bitrate <= 0:
        if channels == 1:
            return 128000
        elif channels == 2:
            return 320000
        else:
            return 512000

    if codec in EFFICIENT_CODECS:
        scale = 1.0
    elif codec in LEGACY_LOSSY_CODECS:
        scale = 0.8
    elif codec in LOSSLESS_CODECS:
        scale = 1.5
    else:
        scale = 1.0

    target = int(bitrate * scale)

    # Channel caps
    if channels == 1:
        target = min(max(32000, target), 128000)
    elif channels == 2:
        target = min(max(64000, target), 320000)
    else:
        target = min(max(192000, target), 512000)

    return target


def build_ffmpeg_command(input_file, output_file, crf=18, preset="slow"):
    # ffmpeg command for all streams
    streams = get_streams(input_file)
    cmd = ["ffmpeg", "-y", "-i", str(input_file)]
    v_map_idx = 0
    a_map_idx = 0
    has_audio = False

    for stream in streams:
        stype = stream.get("codec_type")
        idx = stream.get("index")

        if stype == "video":
            codec = stream.get("codec_name", "")
            cmd += ["-map", f"0:{idx}"]
            if codec == "h264":
                cmd += [f"-c:v:{v_map_idx}", "copy"]
            else:
                cmd += [f"-c:v:{v_map_idx}", "libx264", "-crf", str(crf), "-preset", preset]
            v_map_idx += 1

        elif stype == "audio":
            has_audio = True
            channels = stream.get("channels", 2)
            codec = stream.get("codec_name", "")
            try:
                bitrate = int(stream.get("bit_rate", 0) or 0)
            except ValueError:
                bitrate = 0

            target_bitrate = equivalent_aac_bitrate(codec, bitrate, channels)
            cmd += ["-map", f"0:{idx}"]

            if codec == "aac" and bitrate >= target_bitrate:
                cmd += [f"-c:a:{a_map_idx}", "copy"]
            else:
                cmd += [f"-c:a:{a_map_idx}", "aac", "-profile:a", "aac_low", f"-b:a:{a_map_idx}", str(target_bitrate)]
            a_map_idx += 1

    if not has_audio:
        print(f"No audio streams found in {input_file}; output will be video-only")

    cmd += ["-movflags", "+faststart", str(output_file)]
    return cmd


def convert_file(input_file, output_file, progress_callback=None):
    #Convert a single file with progress reporting
    input_file = Path(input_file)
    output_file = Path(output_file)

    if output_file.exists():
        print(f"Skipping {input_file}, output already exists.")
        return

    cmd = build_ffmpeg_command(input_file, output_file)

    # Run ffmpeg while capturing stderr for progress
    process = subprocess.Popen(cmd, stderr=subprocess.PIPE, universal_newlines=True)

    if progress_callback:
        import re
        duration = None
        for line in process.stderr:
            if "Duration" in line and duration is None:
                match = re.search(r"Duration: (\d+):(\d+):(\d+).(\d+)", line)
                if match:
                    h, m, s, ms = map(int, match.groups())
                    duration = h * 3600 + m * 60 + s + ms / 100
            elif "time=" in line and duration:
                match = re.search(r"time=(\d+):(\d+):(\d+).(\d+)", line)
                if match:
                    h, m, s, ms = map(int, match.groups())
                    elapsed = h * 3600 + m * 60 + s + ms / 100
                    percent = min(elapsed / duration * 100, 100)
                    progress_callback(percent)
    process.wait()

    if process.returncode != 0:
        print(f"FFmpeg failed for {input_file}")
    else:
        if progress_callback:
            progress_callback(100)


def batch_convert(folder_path, progress_callback=None):
    # Convert all video files in a folder with optional progress callback
    folder = Path(folder_path)
    # Recursively find all files with supported extensions
    files = [f for f in folder.rglob("*") if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS]
    total_files = len(files)

    for i, file in enumerate(files, start=1):
        output_file = file.with_suffix(".mp4")

        def file_progress(percent):
            if progress_callback:
                overall = (i - 1 + percent / 100) / total_files * 100
                progress_callback(overall)

        convert_file(file, output_file, progress_callback=file_progress)

