# 示例

- `sp1-2503.sources.list`：V10 SP1 2503 的基础 + 叠加 + 修复 + partner 源。
  同一套 URI 对 amd64/arm64/loongarch64/mips64el 都有效，只需导入时指定 `--arch`。

```bash
# 导入示例源（会复制本机 keyring）
../bin/kylinpkg profile import sp1-2503 \
  --sources-file sp1-2503.sources.list \
  --arch arm64

# arm64 全量闭包
../bin/kylinpkg download -p sp1-2503 -a arm64 --full \
  -o ./out/arm64 --repo zlib1g

# x86 增量（先导入目标机基线）
../bin/kylinpkg baseline import target --from-ssh user@host
../bin/kylinpkg profile import sp1-2503-x86 \
  --sources-file sp1-2503.sources.list \
  --arch amd64,i386 \
  --baseline target
../bin/kylinpkg download -p sp1-2503-x86 -o ./out/x86 zlib1g
```

注意：`--sources-file` 导入时默认复制本机 `/etc/apt/trusted.gpg*`；
如果使用自定义 key，加 `--keyring` 或源行加 `[trusted=yes]`。
