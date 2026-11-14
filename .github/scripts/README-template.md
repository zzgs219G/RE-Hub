# RE-Hub 工具集

Termux (Android arm64) 上的逆向工具集，由 CI 从仓库源码自动构建产出。

## 安装

```bash
tar xzf re-tools-arm64.tar.gz -C ~
export PATH="$HOME/re-tools/bin:$PATH"
export PYTHONPATH="$HOME/re-tools/pymods"
```

加进 `~/.bashrc` 后长期生效。然后自检：

```bash
doctor
```

## 外部依赖

这些不随包提供，需用 `pkg` 安装：

```bash
pkg install openjdk-21 python apksigner
```

| 命令 | 被谁用 | 缺了会怎样 |
|---|---|---|
| `java` | jadx、apktool | 两者都启动不了 |
| `python3` | repy | 所有 Python 库用不了 |
| `apksigner` | 改 APK 后签名 | 签不了名，装不上手机 |

## 内容

| 路径 | 是什么 |
|---|---|
| `bin/` | 命令入口（9 个） |
| `jadx/` | dex/apk → Java 反编译器 1.5.6 |
| `pymods/` | Python 库（13 个主库 + 依赖） |
| `radare2/` | 二进制分析 6.2.6 |
| `android-tools/` | aapt/aapt2/zipalign/adb |
| `apktool.jar` | 资源反编译/回编译 3.0.3 |

## bin 里的命令

| 命令 | 干什么 |
|---|---|
| `jadx` | dex/apk → Java 源码（只读分析） |
| `apktool` | 资源反编译 + 回编译（改 APK 必需） |
| `r2` | 交互式二进制分析（`pdf` 反汇编；`pdd` 反编译需 r2dec，见下） |
| `rabin2` | ELF 信息/字符串/导入/符号 |
| `aapt` `zipalign` `adb` | Android 打包与调试 |
| `repy` | 用本目录的 Python 库跑脚本 |
| `doctor` | 自检 29 项 |

## Python 库

**13 个主库**：

`unicorn`（CPU 模拟执行）、`capstone`（反汇编）、`keystone`（汇编）、
`lief`（ELF/DEX 修补）、`elftools`（ELF 解析）、`androguard`（dex/apk 解析）、
`r2pipe`（控制 radare2）、`Crypto`（AES/RSA）、`cryptography`（证书）、
`lxml`（XML）、`yaml`、`networkx` + `pydot`（CFG 图）

其余是它们的依赖，不要单独删。

## 常用命令

### 反编译 APK

```bash
jadx --single-class 'com.xxx.Yyy' -d out/ classes.dex
jadx -d out/ app.apk
```

### 改 APK（反编译 → 改 → 回编 → 签名）

```bash
apktool d app.apk -o work/
# 改 work/ 里的 smali 或资源
apktool b work/ -o new.apk
zipalign -p -f 4 new.apk aligned.apk
apksigner sign --ks my.keystore --out signed.apk aligned.apk
```

### 分析 so

```bash
r2 -qc "aaa; s sym.main; pdd" lib.so    # 反编译成伪代码
r2 -qc "aaa; s sym.main; pdf" lib.so    # 反汇编
rabin2 -I lib.so                         # ELF 头
```

### 用 Python 跑模拟执行

```bash
repy myscript.py lib.so
```

`repy` 会把 `PYTHONPATH` 指到本目录的 `pymods/`，所以任何脚本
不用改代码，用 `repy` 跑就优先用这里的库。

## 构建信息

- 构建日期：{{BUILD_DATE}}
- 目标：Python {{PYTHON_VERSION}} / Android arm64
- 构建脚本：仓库里的 `.github/workflows/build-re-tools.yml`

工具来源：

| 组件 | 来源 |
|---|---|
| jadx / apktool | 上游 GitHub Release |
| radare2 / android-tools | Termux 官方包（aarch64 原生） |
| unicorn / capstone / pycryptodome / lxml | 从源码交叉编译 |
| lief | 已构建产物（PyPI 的 sdist 是空壳） |
| keystone | 从源码交叉编译（需给 CMake 打补丁） |
| r2dec | **未包含**（交叉编译受限，见"已知限制"） |

## 已知限制

**r2dec 插件（pdd 反编译命令）没有包含。**
原因：r2dec 构建过程要运行自己编出来的 `qjsc`（quickjs 编译器），
它是 ARM 二进制，在 x86_64 的 CI runner 上无法执行；用 qemu 代跑也不行
——Android 二进制需要 `/system/bin/linker64`，NDK 里没有这个文件。

替代方案：

```bash
r2 -qc "aaa; s sym.main; pdf" lib.so    # 反汇编
r2 -qc "aaa; s sym.main; pdc" lib.so    # r2 内置伪反编译器
```

需要完整 r2dec 时，可在 Android 设备上本地编译，或从 r2pm 安装：

```bash
r2pm -ci r2dec   # 需要设备上有编译工具链
```
