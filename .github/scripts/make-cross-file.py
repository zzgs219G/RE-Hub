#!/usr/bin/env python3
"""make-cross-file.py — 生成 meson 交叉编译配置文件

用法: make-cross-file.py <输出路径> <clang 路径> [sysroot]

坑位记录：
  meson 的 machine file 语法像 Python 但不是 ini。
  cpu_family/system 的值必须带引号，否则 meson 会先当【常量名】
  解析（它有一张内置常量表如 x86_64/aarch64，查不到就报
  "Undefined constant 'aarch64'"——报错信息极易误导人以为
  值写错了，实际是引号丢了）。
  用 shell printf 生成时转义层次太多（YAML→bash→printf 三层），
  引号极易丢，所以用 Python 直接写文件。
"""
import sys


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__, file=sys.stderr)
        return 2
    out, cc = sys.argv[1], sys.argv[2]
    sysroot = ''
    if len(sys.argv) > 3 and not sys.argv[3].startswith('--'):
        sysroot = sys.argv[3]

    content = f"""[binaries]
c = '{cc}'
cpp = '{cc}++'
ar = '{cc.rsplit('/', 1)[0]}/llvm-ar'
strip = '{cc.rsplit('/', 1)[0]}/llvm-strip'
pkg-config = 'pkg-config'

[host_machine]
system = 'android'
cpu_family = 'aarch64'
cpu = 'aarch64'
endian = 'little'

[properties]
needs_exe_wrapper = true
"""
    if sysroot:
        content += f"c_args = ['-I{sysroot}/usr/include']\n"

    # 交叉编译时 meson 会尝试运行编译期工具（如 quickjs 的 qjsc），
    # 它们被编成了 ARM 的可执行文件，runner 上跑不了。
    # qemu-aarch64-static 可以直接运行 ARM 二进制，作为 exe_wrapper。
    if '--with-qemu' in sys.argv:
        content = content.replace('[binaries]',
                                  "[binaries]\nexe_wrapper = 'qemu-aarch64'")
    with open(out, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'✓ cross file: {out}')
    print(content)
    return 0


if __name__ == '__main__':
    sys.exit(main())
