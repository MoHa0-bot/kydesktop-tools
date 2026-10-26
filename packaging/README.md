# deb 打包

```bash
cd kydesktop-tools   # 仓库根目录
./packaging/build-deb.sh
```

输出：`dist/kylinpkg_0.2.0_all.deb`

安装：

```bash
sudo apt install ./dist/kylinpkg_0.2.0_all.deb
# 或
sudo dpkg -i ./dist/kylinpkg_0.2.0_all.deb
sudo apt -f install
```

安装后的路径：

| 内容 | 路径 |
| --- | --- |
| 主程序 | `/opt/kylinpkg/` |
| CLI | `/usr/bin/kylinpkg` → `/opt/kylinpkg/bin/kylinpkg` |
| GUI | `/usr/bin/kylinpkg-gui` → `/opt/kylinpkg/bin/kylinpkg-gui` |
| 桌面文件 | `/usr/share/applications/kylinpkg.desktop` |
| 图标 | `/usr/share/icons/hicolor/scalable/apps/kylinpkg.svg` |
| 文档 | `/usr/share/doc/kylinpkg/` |
| 收集脚本 | `/opt/kylinpkg/collector/kylinpkg-collect.sh` |

运行时状态目录仍是 `~/.local/share/kylinpkg`，默认下载输出目录是
`/tmp/kylinpkg-out/<profile>-<arch>`（可用 `KYLINPKG_OUTPUT_DIR` 覆盖）。

卸载：

```bash
sudo apt remove kylinpkg
```

依赖说明：

- `python3`、`python3-tk`：程序与图形界面；
- `apt`、`apt-utils`、`dpkg`：隔离 apt root、`apt-ftparchive`；
- `ca-certificates`、`openssh-client` 为 Recommends。
