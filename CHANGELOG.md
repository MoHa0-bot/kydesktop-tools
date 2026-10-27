# 版本记录

本项目的版本号遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)：
主版本号.次版本号.修订号。日期格式为 `YYYY-MM-DD`。

## [Unreleased]

- 计划中：更多麒麟小版本预设、下载并发/断点续传、图形化 SSH 导入。

## [0.2.4] - 2026-10-27

### 变更

- 同步最新修正版文档的命名：
  - 2303 / 2403 / 2503 统一使用“通用版”；
  - Kirin 990 原“新版”按新文档改为“2107版”；
  - 盘古归入“海思麒麟 · 盘古（Pangwu）”分组。
- 盘古术语更新为“华为海思的另一款芯片产品线，ARM64 架构，有专用版本分支”；
- 源行仍为 26 个预设 / 88 条 `deb` 源行，地址无变化；
- 版本号更新为 0.2.4，重新构建 deb。

## [0.2.3] - 2026-10-27

### 变更

- 按最新修正版源汇总重新同步 26 个预设 / 88 条 `deb` 源行；
- Kirin/Pangwu 相关 partner/feature 路径由 `10.1-`/`PART-10.1-`
  更新为 `10_1-`/`PART-10_1-`；
- 第 12 条按修正版文档保留 `10.1-kirin9a0` 的 partner suite；
- 保留盘古（Pangwu）= 华为海思 / ARM64 的已确认说明；修正版文档术语表
  仍写“飞腾”，仓库 `docs/` 与预设继续使用已确认版本；
- 版本号更新为 0.2.3，重新构建 deb。

## [0.2.2] - 2026-10-27

### 修复

- 纠正盘古（Pangwu）说明：盘古是华为海思的芯片产品线，ARM64 架构，
  不是飞腾平台；同步修正 `presets.py`、`docs/` 和 README。
- 移除预设中的 `_LEGACY_NOTE`。修正版源数据已无 OCR 空格，源地址直接使用
  `PART-10.1-kirin...`，不再提示用户手工替换。
- 预设名称/描述中的“普通版”统一改为“通用版”（2303、2503）。
- 预设与文档一致性测试不再做 OCR 空格归一，只保留重复组件归一；
  新增“预设名称/描述不含‘普通版’”断言。

### 变更

- 按最新修正版重新对齐：源行 86 → 88，更新 V10SP1-2107/0521-HWE
  的 KY desktop / partner / 基础源；`$(ARCH)` 在创建 profile 时替换为主架构
  （amd64/arm64 已验证）。
- 版本号更新为 0.2.2，重新构建 deb。

## [0.2.1] - 2026-10-27

### 变更

- 按修正版《银河麒麟桌面版软件源地址汇总.md》重新解析并逐行核对
  26 个源预设 / 86 条 `deb` 源行；
- 补充盘古（Pangwu）平台说明，两个盘古预设继续按 arm64 处理；
- `docs/kylin-desktop-sources.md` 同步修正版原文；
- 新增 `test_presets_match_corrected_document`，防止文档与预设再次漂移；
- 版本号更新为 0.2.1，重新构建 deb。

## [0.2.0] - 2026-10-26

首个面向 GitHub 管理/可安装 deb 的发布版本。

### 新增

- **隔离 apt root**：所有 apt 操作在独立 `Dir` 中完成，不修改本机
  `/etc/apt`、`/var/lib/dpkg`、`/var/lib/apt`。
- **profile（apt 源配置）**：
  - 从本机、SSH、rootfs、导出的 `sources.list`/`sources.list.d` 导入；
  - 支持 `.list`、deb822 `.sources`、`preferences`/pin、keyring、`auth.conf`；
  - 源配置查看/编辑：GUI 编辑器和 `profile files/cat/set/edit/rm-file`；
  - `Signed-By` keyring 自动复制并改写为 profile 内路径；
  - 源配置指纹变化后自动刷新隔离索引。
- **baseline（dpkg status）**：
  - 从 status 文件、本机、SSH、rootfs、空基线导入；
  - 全量闭包与增量补包两种模式；
  - 基线架构与目标架构不一致时明确报错。
- **CLI**：`profile`、`baseline`、`preset`、`bundle`、`versions`、
  `update`、`resolve`、`download`、`repo`、`verify`、`list`、`gui`、
  `doctor`、`gc`。
- **GUI（tkinter）**：
  - profile/baseline 导入、绑定、删除；
  - 26 个麒麟源预设，支持预览和创建；
  - 架构下拉选择（amd64、arm64、mips64el、loongarch64、i386、amd64,i386）；
  - apt policy 版本查询、多选、指定版本/多版本下载；
  - “下载依赖”开关，可只下载当前包；
  - 解析/下载后台线程 + **中断**按钮；
  - **清理缓存**按钮；
  - 导入原始主机收集包；
  - 按钮文案去省略号、源配置按钮单行显示、删除按钮收窄。
- **26 个内置源预设**：解析自《银河麒麟桌面版软件源地址汇总.md》，
  覆盖 V10、SP1 2107/2203/2303/2403/2503、海思麒麟、盘古等；
  对 OCR 空格、重复组件、404 suite、`bugfix`/`bugfix-limit` 差异做了注释。
- **原始主机收集包**：
  - `collector/kylinpkg-collect.sh`：收集完整 dpkg status、apt 源、
    preferences、keyrings、系统元数据，生成带 `SHA256SUMS` 的 tar.gz；
  - `bundle inspect/import`：一键导入 profile + baseline；
  - 支持跨架构导入和 `auth.conf`（显式 `--with-auth`）。
- **版本下载**：
  - `versions` 查询所有可用版本（解析 `apt-cache policy`）；
  - `pkg=version` 精确版本；
  - 同一软件包多个版本分别解析、合并去重到一个 `debs/`、manifest 和离线源；
  - `manifest.json` 增加 `version_plans`、`with_dependencies`。
- **离线源**：`apt-ftparchive` 生成 `Packages`/`Packages.gz`/`Release`/
  `sources.list`，支持多版本共存。
- **缓存管理**：`gc --cache` / `--roots`，GUI 一键清理隔离索引和包缓存，
  保留 profile、baseline 和下载结果。
- **打包**：
  - deb 安装到 `/opt/kylinpkg`；
  - `/usr/bin/kylinpkg`、`/usr/bin/kylinpkg-gui` 软链；
  - `/usr/share/applications/kylinpkg.desktop` 和图标；
  - `packaging/build-deb.sh`。
- **默认输出目录**：`/tmp/kylinpkg-out/<profile>-<架构>`，
  可用 `-o` 或 `KYLINPKG_OUTPUT_DIR` 覆盖。
- **CI/发布**：GitHub Actions 运行测试、构建 deb；tag `v*` 自动发布。

### 变更

- apt 默认使用 `Acquire::ForceIPv4=true`，降低 IPv6 路由导致的卡顿。
- profile 导入后自动物化 `Signed-By` keyring 并改写源文件，便于跨机器复用。
- GUI 默认输出目录从当前目录改为 `/tmp/kylinpkg-out`。
- GUI 源配置按钮从两行合并为一行：`从预设创建 / 从本机导入 / 编辑源配置 /
  更多 / 删除`；`导入源配置` 与 `从 rootfs 导入` 收进“更多”菜单。
- `pyproject.toml` 版本改为从 `kylinpkg.__version__` 动态读取。

### 修复

- 基线架构兼容性检查使用实际生效架构，而不是 profile 中记录的完整架构。
- 拒绝覆盖已有 baseline 时不再误删原数据。
- GUI 对话框在窗口尚未映射时 `grab_set` 失败的问题。
- GUI 任务取消、下载部分文件重试、索引指纹失效等问题。

### 安全

- 默认不收集/使用 `/etc/apt/auth.conf`，需要显式 `--with-auth`。
- 收集包默认权限 600，并在导入时校验 `SHA256SUMS`。
- 状态目录 0700，文件 0600；`profile show` 默认脱敏源里的凭据。
- 下载后按 apt 提供的哈希复核；本地 `file:` 源由工具复制并复核。

## [0.1.0] - 2026-10-26

内部初始版本。

### 新增

- 隔离 apt root 的核心验证：`Dir` 重定向、空 status 全量闭包、
  多 suite/多架构解析、`--print-uris` 计划、apt 下载与 hash 校验。
- 基础 profile/baseline 导入。
- `resolve` / `download` / `repo` / `verify` 的初版。
- 离线扁平 apt 源生成与 `file://` 回灌验证。
- 初步的单元测试与联网集成测试。

---

仓库地址：https://github.com/MoHa0-bot/kydesktop-tools

[Unreleased]: https://github.com/MoHa0-bot/kydesktop-tools/compare/v0.2.4...HEAD
[0.2.4]: https://github.com/MoHa0-bot/kydesktop-tools/releases/tag/v0.2.4
[0.2.3]: https://github.com/MoHa0-bot/kydesktop-tools/releases/tag/v0.2.3
[0.2.2]: https://github.com/MoHa0-bot/kydesktop-tools/releases/tag/v0.2.2
[0.2.1]: https://github.com/MoHa0-bot/kydesktop-tools/releases/tag/v0.2.1
[0.2.0]: https://github.com/MoHa0-bot/kydesktop-tools/releases/tag/v0.2.0
[0.1.0]: https://github.com/MoHa0-bot/kydesktop-tools/releases/tag/v0.1.0
