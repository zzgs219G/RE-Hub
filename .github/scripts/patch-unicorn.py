#!/usr/bin/env python3
"""patch-unicorn.py — 给 unicorn 的 setup.py 打补丁，适配 Android 交叉编译

用法: patch-unicorn.py <unicorn 源码根目录>

两个问题：

1. setup.py:131 硬编码找 libunicorn.so.2（SOVERSION 文件名）。
   但 NDK toolchain 下 cmake 对 Android 目标不生成带版本号的
   SONAME 符号链接（Android 的 dlopen 机制和 Linux 不同，
   CMake 的 Android 平台模块跳过 VERSION/SOVERSION 属性），
   实际产出是 libunicorn.so（无版本号）。
   编译 100% 成功后 copy 那步报：
       FileNotFoundError: .../build_python/libunicorn.so.2
   （run 43615492065 实测）

   修法：copy 时先试 .so.2，失败回退 .so。

2. setup.py 直接调 ['cmake', ...] 不带工具链参数。
   这个由 workflow 里的 cmake wrapper 解决（PATH 前置），
   这里不用管。
"""
import os
import re
import sys

# 原代码（setup.py:127-131，非 Windows 分支）：
#     shutil.copy(os.path.join(BUILD_DIR, LIBRARY_FILE), LIBS_DIR)
#     shutil.copy(os.path.join(BUILD_DIR, STATIC_LIBRARY_FILE), LIBS_DIR)
# 改成：动态库找不到版本号文件名时回退到无版本号
OLD = (
    "        shutil.copy(os.path.join(BUILD_DIR, LIBRARY_FILE), LIBS_DIR)\n"
    "        shutil.copy(os.path.join(BUILD_DIR, STATIC_LIBRARY_FILE), LIBS_DIR)\n"
)
NEW = """        # Android NDK 下 cmake 不生成带 SOVERSION 的文件名，
        # 实际产出 libunicorn.so 而非 libunicorn.so.2 —— 回退查找
        _src = os.path.join(BUILD_DIR, LIBRARY_FILE)
        if not os.path.exists(_src):
            _fallback = _src.rsplit('.so', 1)[0] + '.so'
            if _fallback != _src and os.path.exists(_fallback):
                _src = _fallback
        shutil.copy(_src, LIBS_DIR)
        shutil.copy(os.path.join(BUILD_DIR, STATIC_LIBRARY_FILE), LIBS_DIR)
"""


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    root = sys.argv[1]
    path = os.path.join(root, 'setup.py')
    if not os.path.isfile(path):
        print(f'✗ 找不到 {path}', file=sys.stderr)
        return 1

    text = open(path, encoding='utf-8', errors='replace').read()

    if '_fallback' in text:
        print('  无需修改（已打过补丁）')
        return 0

    if OLD not in text:
        print('✗ 没匹配到预期代码块——上游 setup.py 可能已改版，请人工检查',
              file=sys.stderr)
        # 打印附近内容帮助诊断
        i = text.find('BUILD_DIR, LIBRARY_FILE')
        if i >= 0:
            print('--- 实际内容：', file=sys.stderr)
            print(text[max(0, i - 300):i + 300], file=sys.stderr)
        return 1

    open(path, 'w', encoding='utf-8').write(text.replace(OLD, NEW, 1))
    print('  ✓ setup.py 已打补丁：libunicorn.so.2 找不到时回退 libunicorn.so')
    return 0


if __name__ == '__main__':
    sys.exit(main())
