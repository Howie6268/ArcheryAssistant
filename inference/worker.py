#!/usr/bin/env python3
"""Private JSON-lines worker. stdout is reserved for protocol, including native code."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import warnings

PROTOCOL_VERSION = 1
MAX_REQUEST_BYTES = 65536


def main():
    # Redirect descriptor 1 before importing the native runtime. A Python-only redirect
    # cannot prevent native libraries from corrupting the JSON-lines channel.
    protocol = os.fdopen(os.dup(sys.stdout.fileno()), "w", encoding="utf-8", buffering=1)
    os.dup2(sys.stderr.fileno(), sys.stdout.fileno())
    sys.stdout = sys.stderr
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, type=Path)
    args = parser.parse_args()

    def emit(payload):
        protocol.write(json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n")
        protocol.flush()

    try:
        if sys.version_info[:2] != (3, 12):
            raise RuntimeError("NAS requires the bundled Python 3.12 runtime")
        from PIL import Image, ImageOps
        from nas_runtime import NasDetector, MODEL_SHA256, digest
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        detector = NasDetector(args.model)
        emit(dict(protocol_version=PROTOCOL_VERSION, type="ready", model_sha256=MODEL_SHA256,
                  versions=detector.versions))
    except Exception as exc:
        emit(dict(protocol_version=PROTOCOL_VERSION, type="startup_error",
                  error=dict(code=type(exc).__name__, message=str(exc))))
        return 2

    while True:
        line = sys.stdin.buffer.readline(MAX_REQUEST_BYTES + 1)
        if not line:
            return 0
        if len(line) > MAX_REQUEST_BYTES:
            # An overlong frame cannot safely be resynchronized.
            return 3
        request_id = None
        image_hash = None
        try:
            request = json.loads(line)
            request_id = request.get("request_id")
            if request.get("protocol_version") != PROTOCOL_VERSION or not isinstance(request_id, str):
                raise ValueError("Unsupported request protocol")
            if request.get("operation") != "recognize":
                raise ValueError("Unsupported operation")
            source = Path(request["source"]).resolve(strict=True)
            normalized = Path(request["normalized_png"]).resolve()
            if source == normalized:
                raise ValueError("Normalized PNG must not overwrite the source")
            image_hash = digest(source)
            if image_hash != request.get("image_sha256"):
                raise ValueError("Source image changed after request creation")
            apply_exif = request.get("apply_exif", True)
            if not isinstance(apply_exif, bool):
                raise ValueError("apply_exif must be boolean")
            with Image.open(source) as original:
                original_size = original.size
                exif_orientation = original.getexif().get(274, 1)
                photo = (ImageOps.exif_transpose(original) if apply_exif else original).convert("RGB")
                photo.load()
            normalized.parent.mkdir(parents=True, exist_ok=True)
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(dir=normalized.parent, prefix=".nas-", suffix=".png", delete=False) as output:
                    temporary = Path(output.name)
                photo.save(temporary, format="PNG")
                os.replace(temporary, normalized)
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
            result = detector.infer_image(photo)
            result["image"].update(orientation="exif_normalized" if apply_exif else "decoded_raster_no_exif_autorotate",
                                   source_width=original_size[0], source_height=original_size[1],
                                   source_exif_orientation=exif_orientation)
            result["image_sha256"] = image_hash
            result["normalized_sha256"] = digest(normalized)
            result["raster_sha256"] = hashlib.sha256(b"RGB" + struct.pack("<II", photo.width, photo.height) + photo.tobytes()).hexdigest()
            result["message"] = (f"检测到 {len(result['points'])} 个候选，请核对、补点或删除。"
                                 if result["points"] else "未检测到候选；请补点或重新拍摄，无候选不代表零分。")
        except Exception as exc:
            result = dict(contract_version="nas-entry-v1", model_sha256=MODEL_SHA256,
                          coordinate_space="original_pixel_centers", status="inference_error", points=[],
                          image_sha256=image_hash, message=f"识别失败：{exc}",
                          error=dict(code=type(exc).__name__, message=str(exc)))
        emit(dict(protocol_version=PROTOCOL_VERSION, type="result", request_id=request_id, result=result))


if __name__ == "__main__":
    raise SystemExit(main())
