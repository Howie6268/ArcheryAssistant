"""Frozen nas-entry-v1 CPU adapter. Coordinates are original pixel centers."""
from __future__ import annotations

import hashlib
import importlib.metadata
import time
from pathlib import Path

import numpy as np
from PIL import Image

CONTRACT_VERSION = "nas-entry-v1"
MODEL_SHA256 = "8a24d69fa5a0d6c2cadceafdcfac074cb739811c9cff3f54007754d9c5ff31f5"
REQUIRED_VERSIONS = {"ai-edge-litert": "2.3.0", "numpy": "2.4.3", "Pillow": "12.1.1"}


def digest(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def preprocess(photo):
    width, height = photo.size
    if width < 1 or height < 1:
        raise ValueError("Image dimensions must be positive")
    ratio = min(640 / width, 640 / height)
    rw, rh = max(1, round(width * ratio)), max(1, round(height * ratio))
    px, py = (640 - rw) // 2, (640 - rh) // 2
    image = Image.new("RGB", (640, 640), (114, 114, 114))
    image.paste(photo.convert("RGB").resize((rw, rh), Image.Resampling.BILINEAR), (px, py))
    array = np.asarray(image, dtype=np.float32)[:, :, ::-1] / np.float32(255)
    transform = dict(width=width, height=height, resized_width=rw, resized_height=rh,
                     pad_x=px, pad_y=py,
                     coordinate_convention="boxes are continuous xyxy edges; center points use half-pixel resize mapping")
    return np.ascontiguousarray(array[None]), transform


def nms(boxes, scores, indices, threshold=0.50):
    indices = sorted(indices, key=lambda i: (-float(scores[i]), int(i)))
    kept = []
    while indices:
        anchor = indices.pop(0)
        kept.append(anchor)
        if not indices:
            break
        other = np.asarray(indices)
        lt = np.maximum(boxes[anchor, :2], boxes[other, :2])
        rb = np.minimum(boxes[anchor, 2:], boxes[other, 2:])
        intersection = np.prod(np.maximum(rb - lt, 0), axis=1)
        area = np.prod(boxes[anchor, 2:] - boxes[anchor, :2])
        areas = np.prod(boxes[other, 2:] - boxes[other, :2], axis=1)
        overlap = intersection / np.maximum(area + areas - intersection, 1e-12)
        indices = other[overlap <= threshold].tolist()
    return kept


def decode(boxes, probabilities, transform):
    if boxes.shape != (8400, 4) or probabilities.shape != (8400, 3):
        raise ValueError("Unexpected NAS output shape")
    if not np.isfinite(boxes).all() or not np.isfinite(probabilities).all():
        raise ValueError("Nonfinite model output")
    if probabilities.min() < 0 or probabilities.max() > 1:
        raise ValueError("NAS scores must already be probabilities")
    width, height = transform["width"], transform["height"]
    sx, sy = transform["resized_width"] / width, transform["resized_height"] / height
    px, py = transform["pad_x"], transform["pad_y"]
    valid = (boxes[:, 2] > boxes[:, 0]) & (boxes[:, 3] > boxes[:, 1])
    scores = probabilities[:, 0]
    indices = np.flatnonzero(valid & (scores >= 0.25)).tolist()
    points = []
    for anchor in nms(boxes, scores, indices):
        box = boxes[anchor]
        original = [(float(box[0]) - px) / sx, (float(box[1]) - py) / sy,
                    (float(box[2]) - px) / sx, (float(box[3]) - py) / sy]
        x, y = (original[0] + original[2]) / 2 - 0.5, (original[1] + original[3]) / 2 - 0.5
        if 0 <= x < width and 0 <= y < height:
            points.append(dict(id=f"c0-a{anchor}", anchor=int(anchor), class_id=0,
                               score=float(scores[anchor]), x=x, y=y,
                               box_original=original))
    # Preserve reference result ordering; identity is the anchor-based id.
    return sorted(points, key=lambda point: (-point["score"], point["id"]))


class NasDetector:
    """One interpreter; callers must serialize all access."""

    def __init__(self, model_path, threads=4):
        if digest(model_path) != MODEL_SHA256:
            raise ValueError("Model SHA256 differs from nas-entry-v1")
        self.versions = {name: importlib.metadata.version(name) for name in REQUIRED_VERSIONS}
        if self.versions != REQUIRED_VERSIONS:
            raise ValueError(f"NAS dependency versions differ: {self.versions}")
        from ai_edge_litert.interpreter import Interpreter
        self.interpreter = Interpreter(model_path=str(model_path), num_threads=threads)
        self.interpreter.allocate_tensors()
        inputs, outputs = self.interpreter.get_input_details(), self.interpreter.get_output_details()
        if (len(inputs) != 1 or tuple(inputs[0]["shape"]) != (1, 640, 640, 3)
                or inputs[0]["dtype"] != np.float32):
            raise ValueError("Unexpected NAS input tensor")
        self.outputs = {tuple(output["shape"]): output for output in outputs}
        if len(outputs) != 2 or set(self.outputs) != {(1, 8400, 4), (1, 8400, 3)}:
            raise ValueError("Unexpected NAS output tensor shapes")
        if any(output["dtype"] != np.float32 for output in outputs):
            raise ValueError("Unexpected NAS output tensor dtype")
        self.input_index = inputs[0]["index"]
        self.threads = threads

    def infer_preprocessed(self, array):
        if array.shape != (1, 640, 640, 3) or array.dtype != np.float32:
            raise ValueError("Expected FLOAT32 NHWC [1,640,640,3]")
        if not np.isfinite(array).all() or array.min() < 0 or array.max() > 1:
            raise ValueError("Input must be finite and normalized")
        started = time.perf_counter()
        self.interpreter.set_tensor(self.input_index, np.ascontiguousarray(array))
        self.interpreter.invoke()
        boxes = self.interpreter.get_tensor(self.outputs[(1, 8400, 4)]["index"])[0]
        scores = self.interpreter.get_tensor(self.outputs[(1, 8400, 3)]["index"])[0]
        return boxes, scores, (time.perf_counter() - started) * 1000

    def infer_image(self, photo):
        array, transform = preprocess(photo)
        boxes, scores, elapsed = self.infer_preprocessed(array)
        points = decode(boxes, scores, transform)
        return dict(contract_version=CONTRACT_VERSION, model_sha256=MODEL_SHA256,
                    status="ok" if points else "no_candidates",
                    coordinate_space="original_pixel_centers",
                    image=dict(width=photo.width, height=photo.height), transform=transform,
                    points=points, review_required=True,
                    inference=dict(runtime="ai-edge-litert", runtime_version=self.versions["ai-edge-litert"],
                                   backend="CPU", threads=self.threads, inference_ms=elapsed))
