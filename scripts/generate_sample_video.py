#!/usr/bin/env python3
import struct
import os

def create_valid_minimal_mp4(filepath: str, width: int = 1280, height: int = 720, duration_seconds: int = 10, extra_payload: bytes = b""):
    """
    Creates a syntactically valid minimal ISO BMFF / MP4 container with moov, mvhd, and tkhd boxes.
    """
    timescale = 1000
    duration_units = duration_seconds * timescale

    # 1. ftyp box
    ftyp_data = b"isom" + struct.pack(">I", 512) + b"isomiso2mp41"
    ftyp_box = struct.pack(">I", 8 + len(ftyp_data)) + b"ftyp" + ftyp_data

    # 2. mvhd box (Movie Header Box)
    # version (1 byte = 0), flags (3 bytes = 0)
    # creation_time (4), modification_time (4), timescale (4), duration (4)
    # rate (4 = 0x00010000), volume (2 = 0x0100), reserved (10), matrix (36), pre-defined (24), next_track_id (4 = 2)
    matrix = [0x00010000, 0, 0, 0, 0x00010000, 0, 0, 0, 0x40000000]
    matrix_bytes = b"".join(struct.pack(">I", m) for m in matrix)

    mvhd_payload = (
        struct.pack(">B3sIIII", 0, b"\x00\x00\x00", 0, 0, timescale, duration_units)
        + struct.pack(">Ih", 0x00010000, 0x0100)
        + (b"\x00" * 10)
        + matrix_bytes
        + (b"\x00" * 24)
        + struct.pack(">I", 2)
    )
    mvhd_box = struct.pack(">I", 8 + len(mvhd_payload)) + b"mvhd" + mvhd_payload

    # 3. tkhd box (Track Header Box)
    # width and height as 16.16 fixed point
    w_fixed = width << 16
    h_fixed = height << 16
    tkhd_payload = (
        struct.pack(">B3sIIII", 0, b"\x00\x00\x07", 0, 0, 1, 0)
        + struct.pack(">I", duration_units)
        + (b"\x00" * 8)
        + struct.pack(">hh", 0, 0)
        + matrix_bytes
        + struct.pack(">II", w_fixed, h_fixed)
    )
    tkhd_box = struct.pack(">I", 8 + len(tkhd_payload)) + b"tkhd" + tkhd_payload

    # 4. trak container
    trak_data = tkhd_box
    trak_box = struct.pack(">I", 8 + len(trak_data)) + b"trak" + trak_data

    # 5. moov container
    moov_data = mvhd_box + trak_box
    moov_box = struct.pack(">I", 8 + len(moov_data)) + b"moov" + moov_data

    # 6. mdat box with dummy media payload
    media_content = extra_payload + b"\x00" * max(0, 1024 * 64 - len(extra_payload))  # 64 KB payload
    mdat_box = struct.pack(">I", 8 + len(media_content)) + b"mdat" + media_content

    os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
    with open(filepath, "wb") as f:
        f.write(ftyp_box + moov_box + mdat_box)

    print(f"✅ Gerçek test MP4 dosyası oluşturuldu: {filepath} ({width}x{height}, {duration_seconds}s)")

if __name__ == "__main__":
    out_path = os.path.join(os.path.dirname(__file__), "..", "data", "temp", "sample_test_video.mp4")
    create_valid_minimal_mp4(out_path, width=1920, height=1080, duration_seconds=15)

