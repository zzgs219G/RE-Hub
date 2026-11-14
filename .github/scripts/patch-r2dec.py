#!/usr/bin/env python3
"""patch-r2dec.py — 让 r2dec 支持交叉编译（qjsc 用 host 编译器）

用法: patch-r2dec.py <r2dec 源码根目录>

问题：
  r2dec 的构建流程是「编 qjsc（quickjs 编译器工具）→ 运行 qjsc 生成
  bytecode.h → 用该头文件编插件」。

  交叉编译时 meson 默认把 qjsc 也按 target 架构编（ARM），
  于是构建中途执行 qjsc 这一步在 x86_64 的 CI runner 上失败：
      An exe_wrapper is needed for /tmp/r2dec/b/qjsc
  用 qemu 代跑也不行——NDK 的 Android 二进制依赖 /system/bin/linker64，
  该文件在系统镜像里，NDK sysroot 不含它。

修法：
  meson 支持为构建期工具单独指定 native 编译。
  给 qjsc 加 native: true，它就会用 host 编译器（runner 的 gcc/clang）
  编成 x86_64 并直接执行。
  同时要让它依赖的 quickjs 库也走 native，否则链接的是 ARM 版静态库。

  注意：libquickjs 是 subproject，需要单独拿一份 native 构建的
  quickjs_dep。meson 的 subproject fallback 支持 native: true 参数。
"""
import os
import re
import sys

MARK = '# [patched by patch-r2dec.py]'


def patch_meson_build(root: str) -> int:
    path = os.path.join(root, 'meson.build')
    if not os.path.isfile(path):
        print(f'✗ 找不到 {path}', file=sys.stderr)
        return 1
    text = open(path, encoding='utf-8', errors='replace').read()

    if MARK in text:
        print('  已打过补丁，跳过')
        return 0

    # 1) subproject 增加 native 版本（给 qjsc 用）
    old_sub = "libquickjs_proj = subproject('libquickjs', default_options: ['default_library=static'])"
    new_sub = (
        "# [patched by patch-r2dec.py] 交叉编译时 qjsc 必须用 host 编译器编，\n"
        "# 否则它会被编成 target 架构，构建中途无法执行。\n"
        "libquickjs_proj_native = subproject('libquickjs',\n"
        "  default_options: ['default_library=static'], native: true)\n"
        "libquickjs_dep_native = libquickjs_proj_native.get_variable('quickjs_dep')\n"
        "\n"
        + old_sub
    )
    if old_sub not in text:
        print('  ✗ 没匹配到 subproject 调用，上游可能改版', file=sys.stderr)
        return 1
    text = text.replace(old_sub, new_sub, 1)

    # 2) qjsc 用 native 编译
    old_qjsc = """qjsc = executable('qjsc', 'tools' / 'qjsc_mod.c',
  dependencies: libquickjs_dep,"""
    new_qjsc = """qjsc = executable('qjsc', 'tools' / 'qjsc_mod.c',
  native: true,
  dependencies: libquickjs_dep_native,"""
    if old_qjsc not in text:
        print('  ✗ 没匹配到 qjsc 定义，上游可能改版', file=sys.stderr)
        return 1
    text = text.replace(old_qjsc, new_qjsc, 1)

    open(path, 'w', encoding='utf-8').write(text)
    print('  ✓ meson.build 已改：qjsc 走 native 编译')
    return 0


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    return patch_meson_build(sys.argv[1])


if __name__ == '__main__':
    sys.exit(main())
