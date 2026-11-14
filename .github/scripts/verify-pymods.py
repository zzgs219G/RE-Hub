#!/usr/bin/env python3
"""verify-pymods.py — 验证 pymods 目录里的库能否真正 import

用法: verify-pymods.py <pymods 目录>

为什么需要：
  pip 装上了不等于能用。例如 androguard 缺 dataset 时，
  import androguard 本身成功，但 import androguard.core.dex 才报错。
  这种问题要等到真机上才暴露，白跑一轮 CI。

为什么不用内联 heredoc：
  GitHub Actions 的 YAML 里写多行 Python heredoc 会破坏缩进结构。
  实测两次都失败（line 581 / line 228 scanner error）。
  所以一律拆成独立脚本文件。
"""
import importlib
import os
import sys

# 需要验证的模块。分两类：
#   必需 = 纯 Python 步骤装完后就应该存在，缺了算失败
#   可选 = 由后续步骤（C 扩展 / lief / keystone）放入，此时可能还没有
REQUIRED = [
    ('androguard.core.dex', 'dex 解析'),
    ('androguard.core.apk', 'apk 解析'),
    ('r2pipe', '控制 radare2'),
    ('elftools.elf.elffile', 'ELF 解析'),
    ('yaml', 'YAML'),
    ('networkx', 'CFG 图'),
    ('pydot', '图导出'),
    ('asn1crypto', 'ASN.1'),
    ('click', 'CLI'),
    ('colorama', '终端着色'),
    ('loguru', '日志'),
    ('pyasn1', 'ASN.1'),
]
OPTIONAL = [
    ('lief', 'ELF/DEX 修补'),
    ('keystone', '汇编'),
    ('unicorn', 'CPU 模拟'),
    ('capstone', '反汇编'),
    ('Crypto.Cipher.AES', '加解密'),
    ('cryptography.hazmat.primitives', '证书'),
]


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    pymods = os.path.abspath(sys.argv[1])
    if not os.path.isdir(pymods):
        print(f'✗ 目录不存在: {pymods}', file=sys.stderr)
        return 1

    # ⚠️ 关键：先插入目标目录，再剔除 site-packages。
    # 不剔除的话，runner 上已装的同名包会被"借用"，
    # 空目录也能报成功（本机模拟时实测踩过）。
    sys.path.insert(0, pymods)
    sys.path = [
        p for p in sys.path
        if 'site-packages' not in p and 'dist-packages' not in p
    ]

    bad = []

    print('--- 必需（纯 Python 库）---')
    for mod, desc in REQUIRED:
        try:
            importlib.import_module(mod)
            print(f'  ✓ {mod:28} {desc}')
        except Exception as e:
            # 必需库任何异常都算失败
            print(f'  ✗ {mod:28} {desc}  {type(e).__name__}: {e}')
            bad.append(mod)

    print('--- 可选（后续步骤产出）---')
    for mod, desc in OPTIONAL:
        try:
            importlib.import_module(mod)
            print(f'  ✓ {mod:28} {desc}')
        except ModuleNotFoundError:
            print(f'  - {mod:28} {desc}（尚未放入）')
        except Exception as e:
            # 存在但坏了，这也要报
            print(f'  ✗ {mod:28} {desc}  {type(e).__name__}: {e}')
            bad.append(mod)

    if bad:
        print(f'\n✗ {len(bad)} 个模块不可用: {bad}', file=sys.stderr)
        return 1
    print('\n✓ 检查通过')
    return 0


if __name__ == '__main__':
    sys.exit(main())
