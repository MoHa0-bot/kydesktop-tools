# kylinpkg-collect

在**原始主机**（其他版本的麒麟/Ubuntu 系机器）上运行，收集一套可以一键导入 kylinpkg 的数据。

## 用法

把脚本拷到目标机：

```bash
scp kylinpkg-collect.sh user@target:/tmp/
ssh user@target 'sudo bash /tmp/kylinpkg-collect.sh -o /tmp'
```

或者直接在目标机上：

```bash
sudo bash kylinpkg-collect.sh -o /tmp
# 输出：/tmp/kylinpkg-bundle-<hostname>-<时间>.tar.gz
```

选项：

- `-o, --output DIR`：输出目录，默认 `$TMPDIR` 或 `/tmp`
- `-n, --name NAME`：收集包名称前缀
- `--with-auth`：同时收集 `/etc/apt/auth.conf` 与 `auth.conf.d`（含明文凭据，谨慎使用）
- `-h, --help`

## 收集内容

```
bundle/
  bundle.json                    # 主机、系统、架构、时间、警告
  README.txt
  SHA256SUMS
  rootfs/
    var/lib/dpkg/status          # 完整 dpkg 状态
    etc/apt/sources.list
    etc/apt/sources.list.d/*.list|*.sources
    etc/apt/preferences(.d)
    etc/apt/trusted.gpg(.d)
    usr/share/keyrings/...       # Signed-By 引用的 keyring
  meta/
    os-release, dpkg-arch, dpkg-foreign-archs,
    apt-version, dpkg-version, uname, packages.list
```

脚本只读取系统文件，不修改原主机。

## 在下载器上导入

```bash
# 先看内容
kylinpkg bundle inspect kylinpkg-bundle-xxx.tar.gz

# 一键导入 profile + baseline（默认按主机名命名并绑定同架构基线）
kylinpkg bundle import kylinpkg-bundle-xxx.tar.gz \
  --profile sp1-2303 --baseline sp1-2303-default

# 跨架构使用（不绑定原基线）
kylinpkg bundle import kylinpkg-bundle-xxx.tar.gz \
  --profile sp1-2303-arm64 --arch arm64 --no-bind
```

图形界面：主界面点击 **“导入其他主机配置…”**，选择 tar.gz，填写名称即可；对话框内还可直接下载本脚本和使用手册。

## 注意

- 默认不收集 `auth.conf`；私有源需要凭据时，收集端加 `--with-auth`，导入端会一并使用。
- 收集包可能包含私有源地址/凭据，脚本会把输出文件权限设为 600，请妥善保管。
- `Signed-By` 引用的 keyring 会被复制进包内，导入时改写为 profile 内的路径，保证跨机器可用。
