#!/usr/bin/env python3
"""patch-keystone.py — 给 keystone 的 CMake 配置打补丁

用法: patch-keystone.py <keystone 源码根目录>

为什么需要：
  keystone 0.9.2（2020 年发布）的 CMakeLists 里有：

      if (POLICY CMP0051)
        cmake_policy(SET CMP0051 OLD)
      endif()

  CMP0051 是 CMake 3.1 引入的策略。新版 CMake（3.27+）已彻底移除
  对 OLD 行为的支持，执行到这行直接报错：

      Policy CMP0051 may not be set to OLD behavior because this version
      of CMake no longer supports it.

  修法：删掉整块。新版 CMake 默认就是 NEW 行为，且 keystone 的
  注释里说这个 OLD 行为只是为了绕过某些 SOURCES 属性的问题，
  在只编静态/共享库（BUILD_LIBS_ONLY=ON）的场景下不影响。
"""
import os
import re
import sys

# 匹配整个 if (POLICY CMP0051) ... endif() 块
BLOCK = re.compile(
    r'if\s*\(\s*POLICY\s+CMP0051\s*\).*?cmake_policy\s*\(\s*SET\s+CMP0051\s+OLD\s*\).*?endif\s*\(\s*\)',
    re.S,
)
REPLACEMENT = (
    '# CMP0051 的 OLD 行为已被新版 CMake 移除，用默认即可\n'
    '# （由 patch-keystone.py 自动修改）\n'
)

TARGETS = ['src/CMakeLists.txt', 'src/llvm/CMakeLists.txt']


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    root = sys.argv[1]
    changed = 0

    for rel in TARGETS:
        path = os.path.join(root, rel)
        if not os.path.isfile(path):
            print(f'  跳过（不存在）: {rel}')
            continue
        text = open(path, encoding='utf-8', errors='replace').read()
        new_text, n = BLOCK.subn(REPLACEMENT, text)
        if n:
            open(path, 'w', encoding='utf-8').write(new_text)
            print(f'  ✓ 已改 {rel}（替换 {n} 处）')
            changed += 1
        else:
            # 可能上游已修，或格式变了 —— 不静默跳过，要说出来
            if 'CMP0051' in text:
                print(f'  ⚠ {rel} 里还有 CMP0051 但没匹配到预期格式，请人工检查')
            else:
                print(f'  无需修改: {rel}')

    if changed == 0:
        # 检查是否残留
        for rel in TARGETS:
            path = os.path.join(root, rel)
            if os.path.isfile(path) and 'CMP0051 OLD' in open(path, encoding='utf-8', errors='replace').read():
                print('✗ 补丁未生效，CMP0051 OLD 仍存在', file=sys.stderr)
                return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
