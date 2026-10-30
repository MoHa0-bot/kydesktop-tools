# 开发与发布说明

## 目录结构

```
kylinpkg/             # Python 源码（CLI、GUI、apt 隔离 root、下载器等）
bin/                  # 源码树入口：kylinpkg、kylinpkg-gui
collector/            # 在原始主机运行的收集脚本
docs/                 # 麒麟软件源汇总原始文档
examples/             # 示例源配置
packaging/            # deb 打包脚本、desktop 文件、图标
tests/                # unittest 测试
CHANGELOG.md          # 版本记录
```

## 本地开发

```bash
cd kydesktop-tools   # 仓库根目录

./bin/kylinpkg --version
./bin/kylinpkg doctor
./bin/kylinpkg-gui
```

运行单元测试（有 DISPLAY 时会包含 GUI 冒烟测试）：

```bash
python3 -m unittest discover -s tests -v
```

联网集成测试（会访问麒麟镜像，默认跳过）：

```bash
KYLINPKG_NET_TESTS=1 python3 -m unittest tests.test_integration -v
```

构建 deb：

```bash
./packaging/build-deb.sh
# 输出 dist/kylinpkg_<version>_all.deb
```

## 版本迭代流程

版本号以 `kylinpkg/__init__.py` 的 `__version__` 为唯一来源；`pyproject.toml` 通过 `setuptools.dynamic` 自动读取。

1. 更新 `kylinpkg/__init__.py`：
   ```python
   __version__ = "0.2.1"
   ```
2. 如果收集脚本有改动，同步更新 `collector/kylinpkg-collect.sh` 里的 `VERSION`。
3. 更新 `README.md`、`packaging/README.md` 中出现的 deb 文件名。
4. 更新 `CHANGELOG.md`：
   - 把 `[Unreleased]` 内容整理到新的 `[x.y.z] - YYYY-MM-DD`；
   - 补充 Added / Changed / Fixed / Security；
   - 更新底部 compare/release 链接（把 `OWNER` 换成实际 GitHub 账号）。
5. 运行全部测试并构建 deb：
   ```bash
   python3 -m unittest discover -s tests -v
   ./packaging/build-deb.sh
   ```
   如果 `README.md` 有改动，先重新生成 PDF 使用手册（随 deb 分发、GUI“帮助→使用手册”打开）：
   ```bash
   python3 packaging/build-doc-pdf.py
   ```
6. 提交并打 tag：
   ```bash
   git add -A
   git commit -m "release: v0.2.1"
   git tag -a v0.2.1 -m "kylinpkg v0.2.1"
   git push origin main
   git push origin v0.2.1
   ```

推 tag 后，GitHub Actions 的 release workflow 会构建 deb 并挂到 Release 附件。发布前请确认 tag 与 `__version__` 一致（workflow 会校验）。

## 新增源预设

1. 在 `kylinpkg/presets.py` 的 `PRESETS` 中增加 `_p(...)` 条目；
2. 更新分组/架构/注意事项；
3. 在 `tests/test_presets.py` 中确认数量、ID 唯一、每行可解析；
4. 如文档有更新，同步 `docs/kylin-desktop-sources.md`。

## 代码约定

- Python 3.8 兼容，优先标准库，不引入运行时第三方依赖；
- apt 操作必须走隔离 `AptRoot`，不要直接调用系统 `/etc/apt`；
- 下载相关代码必须保留 hash 校验、取消令牌和部分下载标记；
- GUI 文案不加省略号，按钮尽量单行；
- 新增命令/选项要补 `README.md` 和 `CHANGELOG.md`。

## 安全

- 不默认收集 `auth.conf`；凭据相关功能必须显式开启；
- 收集包必须校验 `SHA256SUMS`；
- 状态目录保持 0700、文件 0600；
- 不修改宿主 `/etc/apt`、`/var/lib/dpkg`、`/var/lib/apt`。

## 提交与 PR

- 一个 PR 聚焦一个功能/修复；
- 说明复现步骤、测试结果和影响范围；
- 涉及 UI 的改动附截图或文字说明；
- 涉及版本号/发布流程的改动请同时更新 CHANGELOG。
