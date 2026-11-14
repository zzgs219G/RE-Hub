#!/usr/bin/env python3
"""extract-deb.py — 手工解析 .deb 并解出 data.tar.*

用法: extract-deb.py <deb文件> <输出目录>

为什么不用 ar/dpkg：CI runner 上这两个命令不一定有，
而 .deb 的 ar 格式极简单（60 字节头 + 数据 + 2 字节对齐），
用 Python 解析零依赖、跨平台行为一致。
"""
import os
import sys
import tarfile

AR_MAGIC = b'!<arch>\n'


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    deb, outdir = sys.argv[1], sys.argv[2]

    data = open(deb, 'rb').read()
    if data[:8] != AR_MAGIC:
        print(f'✗ {deb} 不是 ar 归档（开头是 {data[:8]!r}）', file=sys.stderr)
        return 1

    os.makedirs(outdir, exist_ok=True)
    off = 8
    members = []
    while off + 60 <= len(data):
        hdr = data[off:off + 60]
        name = hdr[0:16].decode('ascii', 'replace').strip().rstrip('/')
        try:
            size = int(hdr[48:58].decode('ascii').strip())
        except ValueError:
            break
        body = data[off + 60:off + 60 + size]
        members.append((name, size))
        if name.startswith('data.tar'):
            path = os.path.join(outdir, name)
            with open(path, 'wb') as f:
                f.write(body)
            print(f'  提取 {name} ({size} 字节)')
            # 立刻解开，只留解开后的树
            with tarfile.open(path) as tf:
                tf.extractall(outdir)
            print(f'  已解压到 {outdir}')
        # ar 成员按 2 字节对齐
        off += 60 + size + (size % 2)

    if not any(n.startswith('data.tar') for n, _ in members):
        print('✗ 归档里没有 data.tar.*，成员有: ' + str([n for n, _ in members]), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
