# 示例

- `xc-2503.sources.list`：V10 SP1 XC-2503（产线通用版）的外网正式源组合——
  基础 `10.1-kylin` + 叠加更新 `10.1-kylin-2503` + 限定修复 `10.1-2503-bugfix-limit`
  + partner。同一套 URI 对 amd64/arm64/loongarch64/mips64el 都有效，只需导入时
  指定 `--arch`。

```bash
# 导入示例源（会复制本机 keyring）
../bin/kylinpkg profile import xc-2503 \
  --sources-file xc-2503.sources.list \
  --arch arm64

# arm64 全量闭包
../bin/kylinpkg download -p xc-2503 -a arm64 --full \
  -o ./out/arm64 --repo zlib1g

# x86 增量（先导入目标机基线）
../bin/kylinpkg baseline import target --from-ssh user@host
../bin/kylinpkg profile import xc-2503-x86 \
  --sources-file xc-2503.sources.list \
  --arch amd64,i386 \
  --baseline target
../bin/kylinpkg download -p xc-2503-x86 -o ./out/x86 zlib1g
```

等价的预设用法（`xc-2503` 预设还自带 `kylin.pref` 优先级配置，
会一并写入 profile 的 `preferences.d/kylin.pref`）：

```bash
../bin/kylinpkg preset create xc-2503 --profile xc-2503 --arch arm64
```

注意：`--sources-file` 导入时默认复制本机 `/etc/apt/trusted.gpg*`；
如果使用自定义 key，加 `--keyring` 或源行加 `[trusted=yes]`。
