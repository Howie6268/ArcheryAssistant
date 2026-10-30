"""Local NAS smoke check; loads the pinned model without reading any user photos or scores."""
from pathlib import Path
import argparse
import json
import platform
import sys
import traceback


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app-root', type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    root = args.app_root.resolve()
    output = args.output or root / 'logs/nas-self-check.json'
    try:
        import numpy as np
        from nas_runtime import NasDetector, MODEL_SHA256
        detector = NasDetector(root / 'models/archery_yolo_nas_s_float16.tflite')
        boxes, scores, elapsed = detector.infer_preprocessed(np.zeros((1, 640, 640, 3), dtype=np.float32))
        if boxes.shape != (8400, 4) or scores.shape != (8400, 3) or not np.isfinite(boxes).all() or not np.isfinite(scores).all():
            raise ValueError('NAS output shape or finite-number check failed')
        report = dict(status='passed', platform=platform.platform(), python=sys.version,
                      model_sha256=MODEL_SHA256, dependency_versions=detector.versions,
                      output_shapes=[list(boxes.shape), list(scores.shape)], elapsed_ms=elapsed,
                      user_data_accessed=False)
    except Exception as error:
        report = dict(status='failed', platform=platform.platform(), error=str(error), traceback=traceback.format_exc(),
                      user_data_accessed=False)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
