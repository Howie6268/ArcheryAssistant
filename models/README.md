# 箭靶识别模型（用户使用）

> **当前源码（2026-10-25）**：精确记录已接通本地 NAS 照片候选、校对、标定与确认计分；旧 ONNX 和手动记录保留。完整实现和验证边界见 [接入说明](../docs/nas-photo-integration-2026-10-25.md)。

普通用户无需训练模型。本目录保存推理模型；NAS 需要发行包内的 `inference` 私有运行时。

## 模型文件

| 文件 | 说明 |
|------|------|
| `archery_yolo_nas_s_float16.tflite` | 新照片候选，固定 `nas-entry-v1` 契约，不可由 ONNX Runtime 直接加载 |
| `archery-arrow-in-target.onnx` | 在靶箭检测（推荐） |
| `archery-yolox.onnx` | 通用备用名 |
| `archery.onnx` | 旧文件名，仍支持 |

## 使用注意

1. 识别结果请在虚拟靶上 **人工核对** 后再保存  
2. 请勿删除 `data/` 文件夹（训练记录）  
3. 若落点不准，在虚拟靶上 **拖动** 修正  

## 许可证

| 组件 | 许可证 |
|------|--------|
| YOLOX 模型架构 | Apache 2.0 |
| ONNX Runtime | MIT |

## 开发验证（2026-10-22）

现有单类模型的输入输出契约记录在 `archery-arrow-in-target.contract.json`。Java 推理已修复通道、数值范围、输出解析及候选过滤；上传按钮仍未接通，框到入靶点、靶面标定和计分仍需后续完善。`archery-yolox.onnx` / `archery.onnx` 作为别名时必须遵守同一单类契约，旧六类环区导出不在当前适配范围。

离线验证结果与人工复核入口见 [推理修复说明](../docs/inference-repair-2026-10-22.md)。原有 `.onnx` 文件未修改。
