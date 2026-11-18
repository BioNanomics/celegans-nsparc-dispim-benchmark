"""Prepare a new local annotation session from the finalized 151-frame AML18 movie.

This reads the source, verifies its existing SHA-256 baseline, and exports
full-resolution lossless PNG display planes. It never connects to NIS or changes
the ND2. The PNGs are fixed linear 8-bit display transforms, not raw intensities.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

import nd2
import numpy as np
from PIL import Image

from celegans_benchmark.checksum import sha256_file
import celegans_benchmark.spot_annotation as plan_module
from celegans_benchmark.spot_annotation import (
    build_frame_plan, plan_digest, annotation_fieldnames, frame_review_fieldnames,
)

TEMPLATE = Path(__file__).parent/"assets/spot_annotation.html"
EXPECTED_NAME = "Celegans_01_stack_timing1111.nd2"


def source_signature(path):
    stat = Path(path).stat()
    return stat.st_size, stat.st_mtime_ns


def baseline_row(manifest, source):
    with Path(manifest).open(encoding="utf-8-sig", newline="") as stream:
        rows = [row for row in csv.DictReader(stream) if row["file_name"] == source.name]
    if len(rows) != 1:
        raise ValueError("The source must have exactly one entry in the baseline manifest")
    row = rows[0]
    if int(row["size_bytes"]) != source.stat().st_size:
        raise ValueError("Source byte size differs from the baseline manifest")
    return row


def display_plane(plane, low, high):
    """Keep source geometry, applying one fixed linear LUT per channel."""
    if not np.isfinite([low, high]).all() or high <= low:
        raise ValueError("Invalid fixed display range")
    values = np.rint(np.clip((plane.astype(np.float32)-low)/(high-low), 0, 1)*255).astype(np.uint8)
    return Image.fromarray(values)


def write_csv(path, fields, rows):
    with Path(path).open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)


def prepare(source, manifest, out, seed=20261118):
    source, manifest, out = Path(source), Path(manifest), Path(out)
    if out.exists():
        raise ValueError("Output exists; choose a new directory to preserve annotations")
    if source.name != EXPECTED_NAME:
        raise ValueError(f"This session protocol is for {EXPECTED_NAME}")
    template = TEMPLATE.read_text(encoding="utf-8") if TEMPLATE.is_file() else ""
    if template.count("__ANNOTATION_MANIFEST__") != 1:
        raise ValueError("The annotation viewer template is missing or invalid")
    before = source_signature(source)
    baseline = baseline_row(manifest, source)
    print(f"Verifying source SHA-256 ({before[0]:,} bytes)", flush=True)
    digest = sha256_file(source)
    if digest.lower() != baseline["raw_sha256"].lower():
        raise ValueError("Source SHA-256 differs from baseline; no annotation session was created")
    with nd2.ND2File(source) as reader:
        if dict(reader.sizes) != {"T":151,"C":3,"Y":1024,"X":1024}:
            raise ValueError("Expected the single-plane, single-position 151x3x1024x1024 recording")
        channels = [channel.channel.name for channel in reader.metadata.channels]
        if channels != ["GFP","RFP","TD"]:
            raise ValueError("Expected GFP, RFP and TD in stored order")
        indices = {}
        for index, coordinates in enumerate(reader.loop_indices):
            t = coordinates.get("T", 0)
            if t in indices:
                raise ValueError("Multiple stored planes at one time point are not supported")
            indices[t] = index
        if sorted(indices) != list(range(151)):
            raise ValueError("Missing or noncontiguous time indices")
        times = [reader.frame_metadata(indices[t]).channels[0].time.relativeTimeMs/1000 for t in range(151)]
        pixel = float(reader.voxel_size().x)
        plan = build_frame_plan(times, digest, pixel, seed=seed)
        first = reader.read_frame(indices[0]).copy()
        ranges = [list(map(float,np.percentile(first[c],[1,99.8]))) for c in range(3)]
        for c, (low, high) in enumerate(ranges):
            if high <= low:
                ranges[c][1] = low+1
        capturing = reader.text_info.get("capturing", "")
        mode_match = re.search(r"NSPARC Mode:[ \t]*([^\r\n]+)",capturing)
        mode = mode_match.group(1).strip() if mode_match else "not recorded"
        colors = ["#00ff00","#ffaa00","#ffffff"]
        channel_info = [{"name":name,"color":colors[c],"display_lo":ranges[c][0],"display_hi":ranges[c][1]}
                        for c,name in enumerate(channels)]
        plan["display"] = {"channels":channel_info,"saved_mode":mode,"source_significant_bits":reader.attributes.bitsPerComponentSignificant,
                           "transform":"Fixed first-frame 1st/99.8th percentile linear LUT to 8-bit; no resize"}
        plan_sha = plan_digest(plan)
        out.mkdir(parents=True)
        (out/"frames").mkdir()
        (out/"plan.json").write_text(json.dumps(plan,indent=2,allow_nan=False)+"\n",encoding="utf-8")
        frames = []
        for frame in plan["frames"]:
            t = frame["frame_index"]
            values = first if t==0 else reader.read_frame(indices[t])
            images, image_hashes = {}, {}
            for c, name in enumerate(channels):
                relative = f"frames/{t:04d}_{name}.png"
                path = out/relative
                display_plane(values[c], *ranges[c]).save(path, format="PNG", compress_level=3)
                images[name] = relative
                image_hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
            frames.append({**frame,"images":images,"image_sha256":image_hashes})
            if t%25==0 or t==150:
                print(f"Exported {t+1}/151 time points",flush=True)
    if before != source_signature(source):
        raise ValueError("Source changed during export; do not use this incomplete session")
    payload = {"schema_version":1,"source_name":source.name,"source_sha256":digest,"plan_sha256":plan_sha,
               "pixel_um":pixel,"width":1024,"height":1024,"channels":channel_info,"frames":frames,
               "annotation_fields":annotation_fieldnames(),"frame_review_fields":frame_review_fieldnames(),
               "saved_mode":mode,"display_transform":"First-frame 1st/99.8th percentile, fixed linear 12-bit to 8-bit display; no resize",
               "initial_annotation_count":0,"initial_reviewed_frames":0}
    (out/"manifest.json").write_text(json.dumps(payload,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    payload_json = json.dumps(payload,ensure_ascii=True,allow_nan=False).replace("<","\\u003c")
    (out/"index.html").write_text(template.replace("__ANNOTATION_MANIFEST__",payload_json),encoding="utf-8")
    write_csv(out/"annotations.csv",annotation_fieldnames(),[])
    reviews = [{"source_sha256":digest,"plan_sha256":plan_sha,"reviewer_id":"",
                "frame_index":f["frame_index"],"time_s":f["time_s"],"split":f["split"],
                "review_status":"not_reviewed","notes":"","reviewed_at":""}for f in plan["frames"]]
    write_csv(out/"frame_review.csv",frame_review_fieldnames(),reviews)
    provenance = {"created_at":datetime.now(timezone.utc).isoformat(),"source_name":source.name,
                  "source_sha256":digest,"source_sha256_freshly_verified":True,"source_bytes":before[0],
                  "source_unchanged_during_export":True,"prior_manifest_sha256":sha256_file(manifest),
                  "plan_sha256":plan_sha,"builder_sha256":sha256_file(Path(__file__)),
                  "frame_plan_module_sha256":sha256_file(Path(plan_module.__file__)),
                  "viewer_template_sha256":hashlib.sha256(template.encode("utf-8")).hexdigest(),"nd2_version":nd2.__version__,
                  "display_transform":payload["display_transform"],"saved_mode":mode,
                  "annotations_completed":0,"frames_reviewed":0,
                  "status":"Prepared for manual review; no human reference annotations yet"}
    (out/"session_provenance.json").write_text(json.dumps(provenance,indent=2)+"\n",encoding="utf-8")
    print(f"Ready: {out/'index.html'}; zero completed annotations",flush=True)
    return payload


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nd2",type=Path,required=True)
    parser.add_argument("--manifest",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    parser.add_argument("--seed",type=int,default=20261118)
    args=parser.parse_args(argv)
    try:
        prepare(args.nd2,args.manifest,args.out,args.seed)
    except (OSError,ValueError) as error:
        parser.exit(1,f"{error}\n")


if __name__=="__main__":
    main()
