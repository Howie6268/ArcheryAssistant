# NAS 本地识别组件

Java Swing 通过私有子进程调用固定版本的 LiteRT CPU 运行时。候选坐标属于规范 PNG 的像素中心坐标；本组件不标定靶面，也不计算环数。没有候选和推理失败有不同状态，用户仍可人工校对。

`nas_runtime.py`实现`nas-entry-v1`：BGR/255、FLOAT32 NHWC、640居中114填充、半偶舍入、class0≥0.25、输入xyxy框NMS IoU>0.50、坐标还原减0.5。不会按组箭数截断，不经过旧40%箭杆偏移或旧靶圆过滤。

`worker.py`在加载原生库前重定向stdout文件描述符，协议输出独占一条JSON Lines通道，Python和原生诊断写stderr。启动验证模型SHA、依赖版本、输入输出shape/type。一个进程只加载一次模型并串行处理请求。

正常识别统一应用EXIF方向，原始候选、预览及用户校对使用同一RGB规范栅格。请求包含`request_id`和源文件SHA；响应包含源文件SHA、规范PNG SHA、RGB栅格SHA和实际宽高。`apply_exif=false`只供交付样例保持原始栅格重放。模型契约在`models/archery_yolo_nas_s_float16.contract.json`，原始交付包保持不变。

## 开发运行

使用Python3.12，在项目内建立隔离环境：

```sh
python3.12 -m venv inference/.venv
inference/.venv/bin/python -m pip install -r inference/requirements-lock.txt
inference/.venv/bin/python tools/validation/run_nas_validation.py --output inference/validation-macos.json
```

Java默认使用Windows的`inference/python/python.exe`或本机开发的`inference/.venv/bin/python`。开发者可用`ARCHERY_NAS_PYTHON`显式指定Python3.12解释器。应用不会自行下载或执行pip。

Java入口是`NasWorkerClient(Path appRoot).recognize(Path source, Path normalizedPng)`；必须在Swing后台任务执行。默认启动与单次请求超时各60秒，`cancel()`终止当前进程并允许下次显式识别重启，`close()`永久关闭客户端。异常或超时不触发其他识别算法。结果`isSuccess()`允许`no_candidates`，这只表示推理成功，不表示已有可计分落点。

## Windows 离线发行准备

以下命令仅供开发或发行构建。`download`明确联网，`verify/assemble`完全离线：

```sh
python inference/prepare_windows_bundle.py download
python inference/prepare_windows_bundle.py verify
python inference/prepare_windows_bundle.py assemble
```

下载固定Python3.12.10嵌入式x64发行包及完整固定版本Windows wheels，分别核对官方Python Sigstore摘要和PyPI SHA256，并记录来源、版本、文件名、SHA到`windows-bundle/manifest.json`。下载可在失败后继续；已完成的bundle拒绝覆盖。组装拒绝覆盖已有`inference/python`，展开wheel而不在最终用户机器运行pip，并配置嵌入式Python的私有模块路径与Windows DLL加载钩子。

发行打包复制`inference/python/`、`worker.py`、`nas_runtime.py`、`check_runtime.py`和模型/契约，并将`inference/windows-crt/`中的同版本x64 DLL复制到发行包的`inference/python/`。保留`nas-runtime-manifest.json`与`windows-crt-manifest.json`以记录运行时来源。不要复制`.venv/`、训练数据和下载缓存。

LiteRT的CPU封装间接依赖`MSVCP140.dll`、`VCRUNTIME140_THREADS.dll`，Python嵌入式发行包本身不提供完整C++运行时。`windows-crt/manifest.json`记录从微软官方固定资产提取的12个DLL及逐文件摘要，来源与恢复方法见该目录README。`tools/copy-nas-runtime.bat`与`tools/package-windows-test.py`会将这些DLL合并到发行包的私有Python目录，无需更改用户的系统运行时。

已有Windows启动程序和Java运行时可用时，可在macOS或其他开发主机编译最新Java17 jar并组装Windows测试包：

```sh
python3 tools/package-windows-test.py --build-id <新的构建标识>
```

该命令复用`release/staging/ArcheryAssistant`中的Windows exe与runtime，只读取指定的软件资产，不携带源码目录的data/config，不覆盖同名构建。输出位于`release/dist/`。静态PE依赖、CRT导出与ZIP检查不代表Windows实机验收；最终用户可运行包内`NAS运行环境检查.bat`，检查记录在`logs/`，不读取用户照片和训练数据。

Windows CPU必须在最终发行环境通过四组固定输入重放、完整图片预处理、Java子进程调用、取消/超时、中文与空格路径、离线启动验收。组装出Windows文件并不证明已在Windows运行通过。当前`validation-macos.json`只记录macOS arm64真实推理，GPU/NPU也未验收。

官方来源：

- [Python3.12.10官方嵌入式发行包](https://www.python.org/downloads/release/python-31210/)
- [LiteRT2.3.0官方Windows Python wheels](https://pypi.org/project/ai-edge-litert/2.3.0/#files)
- [LiteRT官方平台接入](https://developers.google.com/edge/litert/overview)

四组样例的期望文件是测试包封套（`expected_points/expected_total_class0`），不是业务响应。验证脚本显式核对封套到业务`points/status/image/transform`的适配。期望候选数3/8/4/5描述模型基线，不是人工真值；S078保留已知漏检。
