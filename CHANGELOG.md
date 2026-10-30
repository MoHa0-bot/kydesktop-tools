# 版本记录

本项目的版本号遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)：
主版本号.次版本号.修订号。日期格式为 `YYYY-MM-DD`。

## [Unreleased]

- 计划中：下载并发/断点续传、图形化 SSH 导入。

## [0.3.4] - 2026-10-30

- 新增：baseline 列表（CLI `baseline list` / GUI 基线面板）新增 **内核（linux-generic）** 一列，显示基线里已安装内核元包 `linux-generic`（及其 hwe 变体）的版本；`baseline import` 结果与 `baseline show` 同步输出。meta.json 新增 `kernel_version` / `kernel_versions` 字段：新导入的基线导入时写入，旧基线在首次列表时自动从 status 回填。
- 变更：基于 2026-10-30 最新一批现场收集包更新内置数据。内置现场基线 5 份 → 7 份：新增 `sp1-2303-arm64` / `sp1-2403-arm64`；`sp1-2503-arm64` 用新收集包刷新（已安装包 2133 → 2084）；其余 x86 四份数据与原有一致。
- 变更：`xc-2303-实机` 预设合入 arm64（2303 的 x86 / arm64 现场源配置一致，合并为一条）；`xc-2403u2` 注明 2403 的 arm64 实机源配置同样逐行一致。源行内容无变化（45 个预设 / 218 条源行不变）。
- 修复：补上 0.3.3 漏更的 CHANGELOG compare / release 链接。

## [0.3.3] - 2026-10-29

- 变更：现场实测预设 ID 更名 `xc-2203-field` / `xc-2303-field` / `xc-2503-field` → `xc-2203-实机` / `xc-2303-实机` / `xc-2503-实机`；名称规则（`validate_name`）相应扩展为支持汉字。
- 变更：内置基线改为**启动时自动导入**（幂等，CLI 与 GUI 均生效），baseline 列表直接可见可用；移除 GUI「从内置导入」按钮。用户手动删除的内置基线不再自动恢复；内置数据随包更新后自动覆盖刷新；启动前已手工导入的同名基线不会被覆盖（同步标记：state `baselines/.builtin-sync.json`）。`baseline import --builtin` 保留，用于改名导入或手工恢复。后续新增内置基线只需向 `kylinpkg/resources/baselines/` 添加条目，无需改代码。

## [0.3.2] - 2026-10-29

### 新增：现场实测源预设与内置 dpkg 基线（0.3.1 之后的全部变更）

- 新增：随包分发 5 份**内置现场基线**（dpkg 初始状态，`sp1-2203-x86` / `sp1-2303-x86` / `sp1-2403-x86` / `sp1-2503-x86` / `sp1-2503-arm64`），数据来自同一批 5 台 XC 通用版现场主机的收集包（status 以 gzip 存储，共约 2.2 MB）。`baseline list` 显示内置条目（带 *）；`baseline import --builtin <名>` 一键创建可编辑副本（省略名称时以内置名命名）；GUI 新增「从内置导入」按钮。与现场源预设（`*-field`）配合可在离线环境还原现场主机的完整状态。注意 2503 的 x86 / arm64 两份包列表不同，不可互相替代。
- 新增：内置 3 条「现场实测」XC 通用版预设（`xc-2203-field` / `xc-2303-field` / `xc-2503-field`），数据来自 2026-10 用收集脚本在 5 台现场主机采集的配置包。已去重：sp1-2503 的 x86 / arm64 配置一致合并为一条；sp1-2403 与官方清单 `xc-2403u2` 逐行一致，不再单列。现场机器与官方清单的差异如实收录：2203 / 2303 的 archive2 走 `DEB/KYLIN_DEB` 入口且无 bugfix-limit suite，2503 实际使用 `10.1-2503-bugfix` suite、Pin-Priority 550 一档。预设总数 42 → 45，`docs/kylin-desktop-sources.md` 新增第九节。
- 打包：`pyproject.toml` 新增 `package-data` 配置，`resources/` 下的图标与内置基线随 wheel/sdist 分发（此前的 wheel 配置遗漏了资源文件）。

## [0.3.1] - 2026-10-28

### 变更：GUI 界面优化

- **导入其他主机配置**对话框重排：拆为「1 · 选择收集包」「2 · 导入设置」两个分组，各输入行的灰色提示移到输入框下方独立成行，避免窄窗口下被裁剪；「导入」按钮改用蓝色强调样式，与主界面「下载」按钮一致。
- 收集包文件选择窗口默认打开**当前用户的桌面目录**（麒麟的 `~/桌面`、通用环境的 `~/Desktop`，缺失时回退用户主目录），不用再翻目录找收集包。
- 架构下拉选项去掉别名括号：直接显示 `amd64`、`arm64`、`mips64el` 等 dpkg 架构名（`i386`、`amd64,i386` 保留说明文字）；删除下载参数行右侧的灰色别名提示「aarch64→arm64，mips64→mips64el」。
- 修复窄窗口下顶部按钮显示不全：把「隔离 apt root…状态目录」长说明从顶部移到底部状态栏（窄窗口时优先让位），顶部按钮行改为先布局，窗口最窄时按钮仍完整可点。

## [0.3.0] - 2026-10-28

### 新增：下载任务记录（查询 / 重新下载 / 套用配置）

- 新增 `kylinpkg/history.py`：每次 `download`（CLI 与 GUI 共用入口，`downloader.download`/`download_plans`）无论成功、失败还是中断都会把任务配置（profile、架构、基线、软件包、Recommends/依赖/离线源选项、输出目录）和结果写入状态目录的 `history.json`，默认保留最近 200 条。
- CLI 新增 `history` 子命令：
  - `history list [--limit N] [--json]`：查询任务记录；
  - `history show <ID>`：详情，并打印可直接复制的**等价命令**（把历史配置套用到当前任务）；
  - `history redo <ID> [-o DIR] [--force] [--repo|--no-repo]`：按历史任务的配置重新解析并下载，输出目录等默认沿用原任务；
  - `history remove <ID>`、`history clear --yes`：管理记录（不影响已下载的文件）。任务 ID 支持唯一前缀缩写。
- GUI 顶部新增 **“任务记录”** 按钮：对话框可查询任务的时间/状态/profile/架构/软件包/输出目录，支持 **重新下载**（后台执行，日志区显示过程）、**应用到当前参数**（自动填入下载表单，双击记录同效；profile/baseline 已删除时给出明确提示并回退全量闭包）和删除单条记录。
- README 新增“下载任务记录”章节；版本号更新为 0.3.0。

## [0.2.9] - 2026-10-28

### 新增：PDF 使用手册与帮助菜单入口

- 新增 `packaging/build-doc-pdf.py`：把 `README.md` 渲染成 PDF 使用手册（`docs/kylinpkg-manual.pdf`，markdown → HTML → weasyprint 打印，A4 版式、页脚页码，表格/代码块防跨页拆断）。
- GUI 菜单栏 **帮助 → 使用手册** 用系统默认程序打开该 PDF；源码运行从仓库 `docs/` 查找，deb 安装后从 `/opt/kylinpkg/docs/` 查找，缺失时提示重新生成。
- `build-deb.sh` 打包时校验手册 PDF 已生成；`CONTRIBUTING.md` 发布流程补充“README 有改动先重新生成手册”的步骤。
- 版本号更新为 0.2.9。

## [0.2.8] - 2026-10-28

### 变更：导入收集包界面改名并内置资料下载

- GUI 顶部按钮“导入收集包”更名为 **“导入其他主机配置”**，对话框标题同步调整；导入过程的状态栏与日志文案一并更新。
- “导入其他主机配置”对话框顶部新增 **“下载收集脚本”** 与 **“使用手册”** 按钮，可把内置的 `collector/kylinpkg-collect.sh` 与 `collector/README.md` 另存到任意位置；脚本保存后自动赋予执行权限（755）。
- 内置资料按“源码仓库根目录 → `/opt/kylinpkg/collector`”两路查找，源码运行与 deb 安装均可使用。
- 同步更新 `README.md`、`collector/README.md` 与收集脚本输出中的按钮文案。
- 版本号更新为 0.2.8。

## [0.2.7] - 2026-10-28

### 修复：GUI 窗口与任务栏没有图标

- 新增随包分发的多尺寸 PNG 图标（`kylinpkg/resources/icons/`，16–256px），GUI 启动时通过 `iconphoto` 设置 `_NET_WM_ICON`，标题栏与任务栏恢复正常显示。
- `tk.Tk(className="Kylinpkg")` 写入 WM_CLASS，`.desktop` 补充 `StartupWMClass=Kylinpkg`，启动器可正确关联窗口。
- deb 打包时同时安装 hicolor 各尺寸位图（`build-deb.sh`）。
- 版本号更新为 0.2.7。

## [0.2.6] - 2026-10-27

### 源预设按官方外网源清单整体重建

- 数据源换成《银河麒麟桌面外网源.xls》（在线推送使用的正式源，外网），取代已过时的《银河麒麟桌面版软件源地址汇总.md》；纯文本副本写入 `docs/kylin-desktop-sources.md`。
- 预设从 26 个 / 88 条源行扩到 **42 个 / 208 条源行**，按 xls 的产线划分：XC 通用版 6、HWE 硬件启用栈 10、Wayland 24（麒麟 990 / 9006C / 9000C、盘古 M900、华为 Pangux·Flemingx·Panguy·Panguw），另保留 V10 非 SP1 历史预设 2 条。
- 预设 ID 改为产线命名 `xc-*` / `hwe-*` / `wl-*`，旧的 `sp1-*` ID 全部移除（破坏性变更，见 README“与旧版源汇总的差异”）。
- 2503 的 bugfix suite 按 xls 统一为 `10.1-2503-bugfix-limit`；新增 `*-update3`、`10.1-2403-wayland-*` 等 suite。
- HWE 源不再使用 `archive2` 的 `KY-V10-SP1-$(ARCH)` 桌面源，`$(ARCH)` 占位逻辑随之移除。

### 新增：预设自带的 apt 优先级配置

- `SourcePreset` 增加 `preferences` 字段，收录 xls 中 11 条配置的 `/etc/apt/preferences.d/kylin.pref`（`Pin-Priority`）。
- `profile.create_from_preset()` 在有 `preferences` 时写入 profile 的 `preferences.d/kylin.pref`，并追加一条警告提示核对 Pin-Priority 与本机版本。
- `preset_text()` 输出优先级段落；GUI 预设列表新增“优先级”列，详情头里显示是否带 `kylin.pref`。
- 测试新增优先级落盘校验；`test_presets.py` 的 26/88 硬编码更新为 42/208。

### 其他

- `examples/sp1-2503.sources.list` 改名并按新源更新为 `examples/xc-2503.sources.list`。
- 版本号更新为 0.2.6。

## [0.2.5] - 2026-10-27

### 许可相关

- README 新增“许可证”“商标与免责”两节：说明 MIT 条款要点，并声明本项目是独立第三方工具、非麒麟官方产品，MIT 不含商标授权。
- 新增 `packaging/copyright`（DEP-5 机器可读格式），构建 deb 时用它作为 `/usr/share/doc/kylinpkg/copyright`，不再直接塞裸 LICENSE 文本。
- deb `control` 的 Maintainer 改为 `mohao <mohao@users.noreply.github.com>`，并补 `Homepage`。
- `pyproject.toml` 补齐 `[project.urls]`；`license` 字段保留 TOML 表写法（Python 3.8 环境下 PEP 639 的 SPDX 字符串写法会让 `[project]` 变成非法配置），已加注释说明。
- 所有源文件（含测试、入口脚本、collector 脚本）头部加 `SPDX-License-Identifier: MIT` 与版权行。
- GUI“关于”对话框补上许可信息与商标免责说明。
- 版本号更新为 0.2.5。

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
- Kirin/Pangwu 相关 partner/feature 路径由 `10.1-`/`PART-10.1-` 更新为 `10_1-`/`PART-10_1-`；
- 第 12 条按修正版文档保留 `10.1-kirin9a0` 的 partner suite；
- 保留盘古（Pangwu）= 华为海思 / ARM64 的已确认说明；修正版文档术语表仍写“飞腾”，仓库 `docs/` 与预设继续使用已确认版本；
- 版本号更新为 0.2.3，重新构建 deb。

## [0.2.2] - 2026-10-27

### 修复

- 纠正盘古（Pangwu）说明：盘古是华为海思的芯片产品线，ARM64 架构，不是飞腾平台；同步修正 `presets.py`、`docs/` 和 README。
- 移除预设中的 `_LEGACY_NOTE`。修正版源数据已无 OCR 空格，源地址直接使用 `PART-10.1-kirin...`，不再提示用户手工替换。
- 预设名称/描述中的“普通版”统一改为“通用版”（2303、2503）。
- 预设与文档一致性测试不再做 OCR 空格归一，只保留重复组件归一；新增“预设名称/描述不含‘普通版’”断言。

### 变更

- 按最新修正版重新对齐：源行 86 → 88，更新 V10SP1-2107/0521-HWE 的 KY desktop / partner / 基础源；`$(ARCH)` 在创建 profile 时替换为主架构（amd64/arm64 已验证）。
- 版本号更新为 0.2.2，重新构建 deb。

## [0.2.1] - 2026-10-27

### 变更

- 按修正版《银河麒麟桌面版软件源地址汇总.md》重新解析并逐行核对 26 个源预设 / 86 条 `deb` 源行；
- 补充盘古（Pangwu）平台说明，两个盘古预设继续按 arm64 处理；
- `docs/kylin-desktop-sources.md` 同步修正版原文；
- 新增 `test_presets_match_corrected_document`，防止文档与预设再次漂移；
- 版本号更新为 0.2.1，重新构建 deb。

## [0.2.0] - 2026-10-26

首个面向 GitHub 管理/可安装 deb 的发布版本。

### 新增

- **隔离 apt root**：所有 apt 操作在独立 `Dir` 中完成，不修改本机 `/etc/apt`、`/var/lib/dpkg`、`/var/lib/apt`。
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
- **CLI**：`profile`、`baseline`、`preset`、`bundle`、`versions`、`update`、`resolve`、`download`、`repo`、`verify`、`list`、`gui`、`doctor`、`gc`。
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
- **26 个内置源预设**：解析自《银河麒麟桌面版软件源地址汇总.md》，覆盖 V10、SP1 2107/2203/2303/2403/2503、海思麒麟、盘古等；对 OCR 空格、重复组件、404 suite、`bugfix`/`bugfix-limit` 差异做了注释。
- **原始主机收集包**：
  - `collector/kylinpkg-collect.sh`：收集完整 dpkg status、apt 源、preferences、keyrings、系统元数据，生成带 `SHA256SUMS` 的 tar.gz；
  - `bundle inspect/import`：一键导入 profile + baseline；
  - 支持跨架构导入和 `auth.conf`（显式 `--with-auth`）。
- **版本下载**：
  - `versions` 查询所有可用版本（解析 `apt-cache policy`）；
  - `pkg=version` 精确版本；
  - 同一软件包多个版本分别解析、合并去重到一个 `debs/`、manifest 和离线源；
  - `manifest.json` 增加 `version_plans`、`with_dependencies`。
- **离线源**：`apt-ftparchive` 生成 `Packages`/`Packages.gz`/`Release`/`sources.list`，支持多版本共存。
- **缓存管理**：`gc --cache` / `--roots`，GUI 一键清理隔离索引和包缓存，保留 profile、baseline 和下载结果。
- **打包**：
  - deb 安装到 `/opt/kylinpkg`；
  - `/usr/bin/kylinpkg`、`/usr/bin/kylinpkg-gui` 软链；
  - `/usr/share/applications/kylinpkg.desktop` 和图标；
  - `packaging/build-deb.sh`。
- **默认输出目录**：`/tmp/kylinpkg-out/<profile>-<架构>`，可用 `-o` 或 `KYLINPKG_OUTPUT_DIR` 覆盖。
- **CI/发布**：GitHub Actions 运行测试、构建 deb；tag `v*` 自动发布。

### 变更

- apt 默认使用 `Acquire::ForceIPv4=true`，降低 IPv6 路由导致的卡顿。
- profile 导入后自动物化 `Signed-By` keyring 并改写源文件，便于跨机器复用。
- GUI 默认输出目录从当前目录改为 `/tmp/kylinpkg-out`。
- GUI 源配置按钮从两行合并为一行：`从预设创建 / 从本机导入 / 编辑源配置 / 更多 / 删除`；`导入源配置` 与 `从 rootfs 导入` 收进“更多”菜单。
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

- 隔离 apt root 的核心验证：`Dir` 重定向、空 status 全量闭包、多 suite/多架构解析、`--print-uris` 计划、apt 下载与 hash 校验。
- 基础 profile/baseline 导入。
- `resolve` / `download` / `repo` / `verify` 的初版。
- 离线扁平 apt 源生成与 `file://` 回灌验证。
- 初步的单元测试与联网集成测试。

---

仓库地址：https://github.com/MoHa0-bot/kydesktop-tools

[Unreleased]: https://github.com/MoHa0-bot/kydesktop-tools/compare/v0.3.4...HEAD
[0.3.4]: https://github.com/MoHa0-bot/kydesktop-tools/releases/tag/v0.3.4
[0.3.3]: https://github.com/MoHa0-bot/kydesktop-tools/releases/tag/v0.3.3
[0.3.2]: https://github.com/MoHa0-bot/kydesktop-tools/releases/tag/v0.3.2
[0.3.1]: https://github.com/MoHa0-bot/kydesktop-tools/releases/tag/v0.3.1
[0.3.0]: https://github.com/MoHa0-bot/kydesktop-tools/releases/tag/v0.3.0
[0.2.9]: https://github.com/MoHa0-bot/kydesktop-tools/releases/tag/v0.2.9
[0.2.8]: https://github.com/MoHa0-bot/kydesktop-tools/releases/tag/v0.2.8
[0.2.7]: https://github.com/MoHa0-bot/kydesktop-tools/releases/tag/v0.2.7
[0.2.6]: https://github.com/MoHa0-bot/kydesktop-tools/releases/tag/v0.2.6
[0.2.5]: https://github.com/MoHa0-bot/kydesktop-tools/releases/tag/v0.2.5
[0.2.4]: https://github.com/MoHa0-bot/kydesktop-tools/releases/tag/v0.2.4
[0.2.3]: https://github.com/MoHa0-bot/kydesktop-tools/releases/tag/v0.2.3
[0.2.2]: https://github.com/MoHa0-bot/kydesktop-tools/releases/tag/v0.2.2
[0.2.1]: https://github.com/MoHa0-bot/kydesktop-tools/releases/tag/v0.2.1
[0.2.0]: https://github.com/MoHa0-bot/kydesktop-tools/releases/tag/v0.2.0
[0.1.0]: https://github.com/MoHa0-bot/kydesktop-tools/releases/tag/v0.1.0
