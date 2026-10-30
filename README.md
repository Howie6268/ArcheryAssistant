# ArcheryAssistant

**ArcheryAssistant** is a desktop application that brings automatic scoring to archery training: take a photo of the target face, and the app detects every arrow, locates its entry-point on the target, and computes the ring score — replacing manual score entry and click-by-click placement on a virtual target.

**How it works**

- **Entry-point localization**: a custom heatmap model (YOLOX Nano feature network + heatmap head, ~0.83M parameters), trained from scratch on manually annotated data (116 photos · 829 reference points), scores every pixel location and peaks at each arrow's entry-point. A candidate verifier filters false positives.
- **Baseline comparison**: the pretrained **YOLO-NAS** detection model was rebuilt as a trainable PyTorch network and benchmarked against the heatmap approach on the same photos (Recall / Precision / localization error), including fine-tuning experiments with a knowledge-distillation-style "teacher" constraint.
- **Automatic scoring**: target-face calibration (center, ring lines, rotation and aspect ratio) converts entry-point positions into ring scores geometrically, with yellow prompts for points near ring boundaries that need human verification.

This repository contains the Windows test build of the app. See the sections below for setup and usage.

---

## Windows Test Build

Build: 20261025-autoscore-r2; includes NAS-based arrow entry-point detection, target-face matching, automatic scoring, and optional manual verification.

## Quick Start

1. Extract the archive completely into a new folder and double-click `ArcheryAssistant.exe`. Java, Python, models, and C++ DLLs are bundled — no internet connection or additional installation is required.
2. This test package ships with an empty `data/` and `config/`. A local test account is created on first launch; no accounts or training history from the development machine are included.
3. Precise Recording → upload a photo for detection/scoring → confirm the main target and target type → check "verified" → confirm calibration. Automatic scoring can then be applied directly; points highlighted in yellow near ring boundaries do not need to be confirmed one by one.
4. Adjust the adopted score or exclude points on neighboring targets as needed, then apply to the group, finish the group, and save the session; check total scores and photos under History. Points outside the target default to "M" (miss).
5. Verify: photo draft retention, saving drafts, closing and restarting, reopening, and manual score edits / restoring automatic scores.

## Migrating Existing Data

To migrate existing data, close the app first and back up the old entire `data` folder, then place a copy into the new test directory. Do not overwrite the original installation directory. Automatic scoring does not recompute historical scores when loading old records.

## Troubleshooting

If model loading fails, double-click `NAS运行环境检查.bat` (NAS runtime self-check), and send back `logs/nas-self-check.log` and `logs/nas-self-check.json` for diagnosis. The self-check runs on blank input only; it does not read photos, training data, or any network services.

## Build Notes

This package was compiled and assembled on macOS: it reuses the existing Windows x64 jpackage launcher and Java 25 runtime, and the application jar comes from the latest Java 17 build. Static DLL/symbol checks, archive integrity checks, and cross-platform Java regression tests have been completed; it has not yet been run on a physical Windows machine. Please verify on Windows x64.

## Documentation

- Detailed user guide (Chinese): 文档/使用说明.md
- Build source and file summary: build-info.json, FILE_MANIFEST.json
- Chinese version of this README: README.zh.md
