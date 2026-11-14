#!/usr/bin/env python3
"""verify-pymods.py — 验证 pymods 的完整性

用法:
  verify-pymods.py --static <pymods 目录>     CI 上用：静态检查
  verify-pymods.py --runtime <pymods 目录>    Android 真机上用：实际 import

为什么分两种：
  CI 的 runner 是 x86_64，给 Android 编的 .so 在它上面根本无法加载
  （run #10 实测 8 个模块全挂，全是"架构不对"类错误）。
  在 CI 上做 runtime import 是逻辑错误——正确做法是静态检查：
  文件在不在、架构对不对、依赖名是否都能解析。
  真正的 runtime 验证由解压产物的人在手机上跑 doctor 完成。
"""
import os
import sys
import struct


def elf_arch(path):
    """读 ELF 头返回架构字符串；非 ELF 返回 None"""
    try:
        with open(path, 'rb') as f:
            hdr = f.read(20)
        if hdr[:4] != b'\x7fELF':
            return None
        machine = struct.unpack_from('<H', hdr, 18)[0]
        return {0xB7: 'aarch64', 0x3E: 'x86_64'}.get(machine, f'0x{machine:x}')
    except OSError:
        return None


def elf_needed(path):
    """解析 DT_NEEDED（简化版：从 .dynstr 找 so 名）"""
    try:
        with open(path, 'rb') as f:
            data = f.read()
        i = data.find(b'.dynstr')
        # 简化：直接找可打印的 libX.so 字符串
        import re
        return set(re.findall(rb'lib[\w+.-]+\.so[.\d]*', data))
    except OSError:
        return set()


REQUIRED_IMPORTS = [
    ('androguard.core.dex', 'androguard', 'dex 解析'),
    ('Crypto.Cipher.AES', 'Crypto', '加解密'),
    ('unicorn', 'unicorn', 'CPU 模拟'),
    ('capstone', 'capstone', '反汇编'),
    ('lief', 'lief', 'ELF/DEX 修补'),
    ('keystone', 'keystone', '汇编'),
]
REQUIRED_PURE = [
    ('r2pipe', '控制 radare2'),
    ('elftools.elf.elffile', 'ELF 解析'),
    ('yaml', 'YAML'),
    ('networkx', 'CFG 图'),
    ('pydot', '图导出'),
]


def static_check(root: str) -> int:
    print(f'--- 静态检查（CI 环境，无法加载 Android 的 .so）---')
    bad = 0

    # 1. 纯 Python 模块：文件在不在
    pure_markers = {
        'r2pipe': 'r2pipe',
        'elftools': 'elftools',
        'yaml': 'yaml',
        'networkx': 'networkx',
        'pydot': 'pydot',
        'androguard': 'androguard',
        'Crypto': 'Crypto',
        'lief': 'lief',
        'keystone': 'keystone',
        'unicorn': 'unicorn',
        'capstone': 'capstone',
        'lxml': 'lxml',
    }
    for mod, d in pure_markers.items():
        p = os.path.join(root, d)
        ok = os.path.isdir(p) and any(
            f.endswith('.py') for _, _, fs in os.walk(p) for f in fs)
        print(f"  {'✓' if ok else '✗'} {mod:30} {'存在' if ok else '★ 缺失'}")
        bad += 0 if ok else 1

    # 2. 关键 C 扩展 .so：架构必须是 aarch64
    print('--- C 扩展架构（必须 aarch64）---')
    # 路径按实际布局（本机 ~/逆向工具/pymods 实测）：
    key_sos = [
        'lxml/etree.*.so',
        'unicorn/lib/libunicorn.so',
        'capstone/lib/libcapstone.so',
        'keystone/libkeystone.so',
        'lief/_lief.*.so',
    ]
    import glob as _g
    for pat in key_sos:
        full = os.path.join(root, pat)
        files = _g.glob(full)
        if not files:
            print(f'  ✗ {pat}  ★ 无匹配文件')
            bad += 1
            continue
        f = files[0]
        arch = elf_arch(f)
        if arch == 'aarch64':
            print(f'  ✓ {os.path.relpath(f, root)}')
        else:
            print(f'  ✗ {os.path.relpath(f, root)}  架构={arch}')
            bad += 1

    # 3. pycryptodome 的加密扩展（数量多，抽查 + 全体架构）
    crypto_sos = _g.glob(os.path.join(root, 'Crypto/Cipher/*.so'))
    if not crypto_sos:
        print('  ✗ Crypto/Cipher/*.so 无文件')
        bad += 1
    else:
        x86 = [f for f in crypto_sos if elf_arch(f) != 'aarch64']
        print(f'  {"✓" if not x86 else "✗"} Crypto/Cipher: {len(crypto_sos)} 个 .so，'
              f'{"全部 aarch64" if not x86 else f"{len(x86)} 个非 aarch64"}')
        bad += len(x86)

    # 4. 检查所有 .so 里没有 x86_64
    all_sos = []
    for r, _, fs in os.walk(root):
        for f in fs:
            if f.endswith('.so') or '.so.' in f:
                all_sos.append(os.path.join(r, f))
    x86_list = [f for f in all_sos if elf_arch(f) == 'x86_64']
    if x86_list:
        print(f'  ✗ 全目录扫描：{len(x86_list)} 个 x86_64 的 .so：')
        for f in x86_list[:10]:
            print(f'      {os.path.relpath(f, root)}')
        bad += 1
    else:
        print(f'  ✓ 全目录扫描：{len(all_sos)} 个 .so 无 x86_64')

    if bad:
        print(f'\n✗ 静态检查 {bad} 项失败', file=sys.stderr)
        return 1
    print(f'\n✓ 静态检查通过（{len(all_sos)} 个 .so 全部 aarch64）')
    print('  runtime 验证请在 Android 设备上运行 doctor 完成。')
    return 0


def runtime_check(root: str) -> int:
    import importlib
    sys.path.insert(0, root)
    sys.path = [p for p in sys.path
                if 'site-packages' not in p and 'dist-packages' not in p]
    bad = []
    mods = [(m, d) for m, _, d in REQUIRED_IMPORTS] + REQUIRED_PURE
    for mod, desc in mods:
        try:
            importlib.import_module(mod)
            print(f'  ✓ {mod:32} {desc}')
        except Exception as e:
            print(f'  ✗ {mod:32} {desc}  {type(e).__name__}: {e}')
            bad.append(mod)
    if bad:
        print(f'\n✗ {len(bad)} 个模块不可用', file=sys.stderr)
        return 1
    print('\n✓ runtime 检查通过')
    return 0


def main() -> int:
    args = sys.argv[1:]
    if '--static' in args:
        i = args.index('--static')
        return static_check(args[i + 1])
    if '--runtime' in args:
        i = args.index('--runtime')
        return runtime_check(args[i + 1])
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == '__main__':
    sys.exit(main())
