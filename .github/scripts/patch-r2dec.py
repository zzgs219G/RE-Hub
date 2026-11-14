#!/usr/bin/env python3
"""patch-r2dec.py — 让 r2dec 支持交叉编译（qjsc 用 host 编译器）

用法: patch-r2dec.py <r2dec 源码根目录>

## 问题

r2dec 的构建流程：
  编译 qjsc（quickjs 编译器工具）→ 运行它生成 bytecode.h → 编译插件

qjsc 是【构建期工具】，必须在构建机上能跑。交叉编译时 meson 把它也按
target 架构（ARM）编，构建中途执行就失败：
    An exe_wrapper is needed for /tmp/r2dec/b/qjsc
qemu 代跑也不行：Android 二进制依赖 /system/bin/linker64，
该文件在系统镜像里，NDK sysroot 不含。

## 修法（以及踩过的两个坑）

坑 1：subproject(..., native: true) → meson 报 unknown keyword。
坑 2：主项目直接 files('subprojects/libquickjs/cutils.c')
     → meson 报 Sandbox violation，不容许跨 subproject 取文件。

正确做法：改【子项目】的 meson.build，让它同时产出 target 版和 native
版两个库/依赖，再在主项目里取用。这是 meson 官方支持的 subproject
内部建模方式。
"""
import os
import sys

MARK = '# [patched by patch-r2dec.py]'


def patch_quickjs_subproject(root: str) -> int:
    """在 libquickjs 子项目里增加 native 版 quickjs 库"""
    path = os.path.join(root, 'subprojects', 'libquickjs', 'meson.build')
    if not os.path.isfile(path):
        print(f'✗ 找不到 {path}（submodule 没拉下来？）', file=sys.stderr)
        return 1
    text = open(path, encoding='utf-8', errors='replace').read()
    if MARK in text:
        print('  libquickjs 已打过补丁，跳过')
        return 0

    # 在 quickjs_dep = declare_dependency(...) 之后插入 native 版本
    anchor = """quickjs_dep = declare_dependency(
  link_with: quickjs,
  include_directories: include_directories('.'),
)"""
    if anchor not in text:
        print('  ✗ libquickjs/meson.build 里没找到 quickjs_dep 定义', file=sys.stderr)
        return 1

    extra = anchor + f"""

{MARK}
# ── native 版本：给构建期工具（qjsc）用 ──────────────────────────
# 交叉编译时 qjsc 必须在构建机上运行，所以它依赖的库也得用 host 编译器。
# meson 不允许主项目跨 subproject 取源文件（Sandbox violation），
# 因此 native 库必须在这里、即子项目内部定义并导出。
_native_cc = meson.get_compiler('c', native: true)
quickjs_native = static_library('quickjs_native', sources,
  native: true,
  dependencies: [atomic_dep, threads_dep, dl_dep, m_dep],
  c_args: _native_cc.get_supported_arguments(
    '-D_GNU_SOURCE', '-DCONFIG_BIGNUM', '-funsigned-char',
  ),
  pic: true,
  gnu_symbol_visibility: 'hidden',
  implicit_include_directories: false,
  install: false,
)
quickjs_dep_native = declare_dependency(
  link_with: quickjs_native,
  include_directories: include_directories('.'),
)
"""
    open(path, 'w', encoding='utf-8').write(text.replace(anchor, extra, 1))
    print('  ✓ libquickjs/meson.build 增加 native 库')
    return 0


def patch_main(root: str) -> int:
    path = os.path.join(root, 'meson.build')
    if not os.path.isfile(path):
        print(f'✗ 找不到 {path}', file=sys.stderr)
        return 1
    text = open(path, encoding='utf-8', errors='replace').read()
    if MARK in text:
        print('  主项目已打过补丁，跳过')
        return 0

    # 1) 取 native dep
    old = "libquickjs_dep = libquickjs_proj.get_variable('quickjs_dep')"
    new = (old + "\n"
           + MARK + "\n"
           "# 构建期工具（qjsc）用 native 版，见 patch-r2dec.py 说明\n"
           "libquickjs_dep_native = libquickjs_proj.get_variable('quickjs_dep_native')")
    if old not in text:
        print('  ✗ 没匹配到 get_variable(quickjs_dep)', file=sys.stderr)
        return 1
    text = text.replace(old, new, 1)

    # 2) 构建期工具全部改 native
    #    r2dec 有两个：qjsc（quickjs 编译器）和 modjs_gen（JS 模块清单生成器）
    old_modjs = """modjs_gen = executable('modjs_gen', 'tools' / 'modjs_gen.c',
  dependencies: [],"""
    new_modjs = """modjs_gen = executable('modjs_gen', 'tools' / 'modjs_gen.c',
  native: true,
  dependencies: [],"""
    if old_modjs in text:
        text = text.replace(old_modjs, new_modjs, 1)
        print('  ✓ 主 meson.build：modjs_gen 改为 native')
    else:
        print('  ⚠ 没匹配到 modjs_gen，跳过（上游可能改版）')

    old_qjsc = """qjsc = executable('qjsc', 'tools' / 'qjsc_mod.c',
  dependencies: libquickjs_dep,"""
    new_qjsc = """qjsc = executable('qjsc', 'tools' / 'qjsc_mod.c',
  native: true,
  dependencies: libquickjs_dep_native,"""
    if old_qjsc not in text:
        print('  ✗ 没匹配到 qjsc 定义', file=sys.stderr)
        return 1
    text = text.replace(old_qjsc, new_qjsc, 1)

    open(path, 'w', encoding='utf-8').write(text)
    print('  ✓ 主 meson.build：qjsc 改为 native')
    return 0


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    root = sys.argv[1]
    rc = patch_quickjs_subproject(root)
    if rc != 0:
        return rc
    return patch_main(root)


if __name__ == '__main__':
    sys.exit(main())
