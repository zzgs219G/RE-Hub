#!/usr/bin/env python3
"""fetch-termux-pkg.py — 从 Termux 仓库下载并解包一个 deb

用法: fetch-termux-pkg.py <包名> <输出目录> [--only-prefix <子路径>]

把 <包名> 的 data.tar 解到 <输出目录>。
--only-prefix python 表示只取 data/data/com.termux/files/usr 下的
python 相关内容（比如 python-lxml 会同时含 site-packages 和 bin）。

依赖: /tmp/Packages 索引（由 workflow 前面的步骤生成）
"""
import os
import subprocess
import sys
import urllib.request
import gzip

PACKAGES = os.environ.get('TERMUX_PACKAGES_INDEX', '/tmp/Packages')
TMPDIR = os.environ.get('FETCH_TMPDIR', '/tmp')
POOL = 'https://packages.termux.dev/apt/termux-main'


def find_pkg(name: str) -> str:
    """返回包的 Filename 字段"""
    with open(PACKAGES, encoding='utf-8', errors='replace') as f:
        lines = f.read().split('\n')
    for k, line in enumerate(lines):
        if line == f'Package: {name}':
            # Filename 在本条目内（下一个空行前）
            for l in lines[k:k + 30]:
                if l.startswith('Filename: '):
                    return l[len('Filename: '):]
                if l == '':
                    break
    print(f'✗ 索引里找不到 {name}', file=sys.stderr)
    sys.exit(1)


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__, file=sys.stderr)
        return 2
    pkg, outdir = sys.argv[1], sys.argv[2]
    only = None
    if '--only-prefix' in sys.argv:
        only = sys.argv[sys.argv.index('--only-prefix') + 1]

    rel = find_pkg(pkg)
    url = f'{POOL}/{rel}'
    deb = f'{TMPDIR}/_fetch_{pkg}.deb'
    print(f'  下载 {pkg}: {rel}')
    urllib.request.urlretrieve(url, deb)

    # 用 ar 解出 data.tar 再解开
    data = open(deb, 'rb').read()
    if data[:8] != b'!<arch>\n':
        print(f'✗ {deb} 不是 ar 归档', file=sys.stderr)
        return 1
    off, datapath = 8, None
    while off + 60 <= len(data):
        hdr = data[off:off + 60]
        name = hdr[0:16].decode('ascii', 'replace').strip().rstrip('/')
        size = int(hdr[48:58].decode('ascii').strip())
        if name.startswith('data.tar'):
            datapath = f'{TMPDIR}/_fetch_{pkg}.datatar'
            with open(datapath, 'wb') as f:
                f.write(data[off + 60:off + 60 + size])
        off += 60 + size + (size % 2)
    if not datapath:
        print('✗ 没有 data.tar', file=sys.stderr)
        return 1

    os.makedirs(outdir, exist_ok=True)
    with __import__('tarfile').open(datapath) as tf:
        tf.extractall(outdir)
    os.remove(datapath)

    # 找到 usr 目录报告关键内容
    usr = None
    for root, dirs, _ in os.walk(outdir):
        if root.endswith('com.termux/files/usr'):
            usr = root
            break
    if usr and only:
        sub = os.path.join(usr, only)
        if os.path.isdir(sub):
            print(f'  ✓ {pkg} → {only}/ ({sum(len(f) for _,_,f in os.walk(sub))} 个文件)')
        else:
            print(f'  ⚠ {pkg}: {only}/ 不存在', file=sys.stderr)
    else:
        print(f'  ✓ {pkg} 已解包')
    return 0


if __name__ == '__main__':
    sys.exit(main())
