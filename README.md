# 逆向工具

Termux (Android arm64) 上的逆向工具集。设计目标：**整个目录拷到另一部手机，
装好 pkg 依赖后即可用**。

```bash
export PATH="$HOME/逆向工具/bin:$PATH"
export PYTHONPATH="$HOME/逆向工具/pymods${PYTHONPATH:+:$PYTHONPATH}"
```

加进 `~/.bashrc`。之后：

```bash
doctor        # 自检：所有工具是否可用
```

---

## 目录

```
~/逆向工具/  287M
├── README.md          本文件
├── bin/               所有命令入口（9 个）
├── jadx/              75M   dex/apk → Java
├── pymods/           135M   Python 库
├── radare2/           44M   二进制分析（含 r2dec 插件）
├── android-tools/     19M   aapt/aapt2/zipalign/adb
└── apktool.jar        15M   资源反编译/回编译
```

---

## bin/ 里的命令

| 命令 | 干什么 |
|---|---|
| `jadx` | dex/apk → Java 源码（只读分析） |
| `apktool` | 资源反编译 + **回编译**（改 APK 必需） |
| `r2` | 交互式二进制分析，含 `pdd` 反编译 |
| `rabin2` | ELF 信息/字符串/导入/符号 |
| `aapt` `zipalign` `adb` | Android 打包与调试 |
| `repy` | 用本目录的 Python 库跑脚本 |
| `doctor` | 自检 |

**为什么删掉了 java/python3/nm/readelf 那些 wrapper**：
它们原本只是 `exec /data/data/com.termux/files/usr/bin/xxx`，而这个路径
在任何 Termux 上都是同一个。多一层转发的副作用是让人误以为工具是自带的。
现在用系统命令直接调即可（`nm`、`readelf`、`strings` 来自
`pkg install binutils`；`java`、`python3`、`apksigner` 见下方
「外部依赖」）。`doctor` 会检查这几个必需的外部命令。

---

## pymods/ 里的库

**13 个主库**（你实际会用到的）：

| 库 | 干什么 | 典型场景 |
|---|---|---|
| `unicorn` | CPU 模拟执行 | 跑壳 so 的 init_array，静态解出加密数据 |
| `capstone` | 反汇编 | 扫描 adrp+add 找段引用 |
| `keystone` | 汇编（capstone 的反向） | 写补丁代码、构造 shellcode |
| `lief` | ELF/DEX 修补 | 改段表、加段、改 ELF 头 |
| `elftools` | ELF 结构解析 | 读段名/符号表（比 readelf 灵活） |
| `androguard` | dex/apk 解析 | 遍历类与方法 |
| `r2pipe` | 脚本控制 radare2 | 批量分析 |
| `Crypto` | AES/RSA | 解密资源、验签 |
| `cryptography` | 证书/TLS | 解析证书链 |
| `lxml` | XML | 解析 AndroidManifest |
| `yaml` | YAML | 解析配置 |
| `networkx` `pydot` | 图算法/导出 | Dex2C 的 CFG |

其余 12 个（`cffi` `_cffi_backend.so` `loguru` `asn1crypto` `apkInspector`
`apkInspectorCLI` `mutf8` `click` `colorama` `future` `past` `pyasn1`）
是上面这些的**依赖**，不要单独删。

---

## 常用命令

### 反编译 APK 看代码

```bash
jadx --single-class 'com.xxx.Yyy' -d out/ classes.dex
jadx -d out/ app.apk                      # 全量
```

### 改 APK（反编译 → 改 → 回编 → 签名）

```bash
apktool d app.apk -o work/
# ... 改 work/ 里的 smali 或资源 ...
apktool b work/ -o new.apk
zipalign -p -f 4 new.apk aligned.apk
apksigner sign --ks my.keystore --out signed.apk aligned.apk
```

⚠️ `apktool` 回编已知限制：AGP 生成的资源名带 `$`
（如 `drawable/$ic_launcher_foreground__0`）时会报
`invalid entry name` 失败。这是 apktool 3.0.3 与 AGP 的不兼容，
不是环境问题。

### 分析 so

```bash
r2 -qc "aaa; s sym.main; pdd" lib.so     # pdd = 反编译成伪代码
r2 -qc "aaa; s sym.main; pdf" lib.so     # pdf = 反汇编
rabin2 -I lib.so                          # ELF 头
rabin2 -z lib.so                          # 字符串
```

### 用 Python 跑模拟执行

```bash
repy myscript.py lib.so
```

`repy` 做的事就是把 `PYTHONPATH` 指到 `pymods/`，所以任何脚本
不用改代码，用 `repy` 跑就优先用本目录的库。

---

## 外部依赖（不随文件夹走）

这些来自 `pkg`，换手机要重装：

```bash
pkg install openjdk-21 python apksigner binutils
```

| 命令 | 被谁用 | 缺了会怎样 |
|---|---|---|
| `java` | jadx、apktool | 两者都启动不了 |
| `python3` | repy | 所有 Python 库用不了 |
| `apksigner` | 改 APK 后签名 | 签不了名，装不上手机 |
| `readelf` `nm` `strings` `objdump` | 分析 so | 手工查二进制时没有工具 |

`doctor` 会检查这四项。`zipalign` 不需要装——本目录 `android-tools/`
里已经自带。

---

## 两个装不上的

| 库 | 原因 | 替代 |
|---|---|---|
| **frida** | 手机没 root，用不了 | 不需要 |
| **z3-solver** | 要源码编译，Android 无预编译包 | 现有脚本不依赖它 |

`dexdump`（在 `android-tools/` 里）在 Termux 上崩溃
（`libdl.a is a stub`），用 jadx 或 androguard 代替。

---

## 维护记录

- 2026-11-14：整理目录。`lib/apktool.jar` 提到顶层（去掉空壳目录）、
  删掉 11 个纯转发的 wrapper、新增 `doctor` 自检、
  MANIFEST.md + TOOLS.md 合并为本文件。
- 2026-11-14：装上 `lief`（CI 交叉编译，见
  https://github.com/zzgs219G/termux-build）、`keystone`（本机编）、
  `r2dec`（r2 插件）。
- 2026-11-05：Python 库从系统路径实体搬进 `pymods/`，实现可移植。
