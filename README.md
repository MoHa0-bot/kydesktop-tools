# kylinpkg

在银河麒麟桌面操作系统 V10 SP1 上，按需从**任意 apt 源配置**、**任意架构**下载 deb 包及其依赖，并生成可直接给目标机使用的离线 apt 源。

核心特点：所有 apt 操作都在隔离的 `Dir` 里进行，**不会修改本机的 `/etc/apt`、`/var/lib/dpkg`、`/var/lib/apt`**。

当前版本：**0.2.3**。版本记录见 [CHANGELOG.md](CHANGELOG.md)，
开发/测试/发布流程见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## apt 到底依赖哪些信息

apt 求解"要装哪些包、下哪些包"时，输入是四类信息：

| 输入 | 位置 | 作用 |
| --- | --- | --- |
| 源索引 | `/var/lib/apt/lists/*_Packages` | 源里有哪些包、版本、依赖、文件名、哈希 |
| 已安装状态 | `/var/lib/dpkg/status` | 哪些包已存在、版本、架构 |
| 源与版本策略 | `sources.list` / `sources.list.d` + `preferences` | 从哪取、选哪个版本、pin 优先级 |
| 架构集合 | `APT::Architecture(s)` | 为哪个架构求解 |

`/var/cache/apt/archives` 只是已下载 `.deb` 的缓存，不参与依赖求解。

因此本工具为每个 `profile × 架构` 建一个隔离 root，把上述四类输入全部指到自己的目录，再调用本机 apt-get 求解、下载、校验。

### 需要提前收集什么

- **源配置**：需要。按目标小版本保存为 profile（含 suite、组件、pin、keyring）。
- **dpkg status**：
  - 做**全量闭包**（目标机可能是裸系统、或要建离线仓库）：用**空基线**，apt 会把 libc6 等基础依赖全部算进来，**不需要**每个版本的 status。
  - 做**增量补包**（目标机已经是某小版本默认安装）：需要该版本的基线 status，且必须来自**对应版本的干净 VM/镜像**，不是本机当前状态（本机可能已经装了额外软件、或版本已被更新）。
- 麒麟的"小版本"通常不是单独一套源，而是**基础 suite + 叠加 suite + 修复合集**，例如：
  - `10.1-kylin`（基础）
  - `10.1-kylin-2503`（叠加更新）
  - `10.1-2503-bugfix-limit`（限定修复）
  - partner：`archive2.kylinos.cn/.../partner/V10-SP1`
  只挂叠加 suite 会缺基础包（实测 `libgcc-s1` 就会解析失败）。

## 环境要求

- 银河麒麟 V10 SP1 / 其他 Debian、Ubuntu 系发行版
- Python 3.8+
- `apt-get`、`dpkg`、`dpkg-deb`、`apt-ftparchive`（或 `dpkg-scanpackages`）
- 可选：`ssh`（从目标机抓取配置）、`tar`

不需要 root；以普通用户运行即可。状态目录默认 `~/.local/share/kylinpkg`。

```bash
git clone https://github.com/MoHa0-bot/kydesktop-tools.git
cd kydesktop-tools
./bin/kylinpkg --version
./bin/kylinpkg doctor
```

也可以把 `bin/kylinpkg` 软链到 `~/bin` 或 `/usr/local/bin`。

## 安装 deb（推荐）

从 [Releases](https://github.com/MoHa0-bot/kydesktop-tools/releases) 下载最新 deb 直接安装：

```bash
sudo dpkg -i ./kylinpkg_0.2.3_all.deb
```

也可以在源码目录自行构建（产物在 `dist/`，不进版本库）：

```bash
./packaging/build-deb.sh
sudo dpkg -i ./kylinpkg_0.2.3_all.deb
```

安装后的路径：

| 内容 | 路径 |
| --- | --- |
| 主程序 | `/opt/kylinpkg/` |
| 命令行 | `/usr/bin/kylinpkg` → `/opt/kylinpkg/bin/kylinpkg` |
| 图形界面 | `/usr/bin/kylinpkg-gui` → `/opt/kylinpkg/bin/kylinpkg-gui` |
| 桌面文件 | `/usr/share/applications/kylinpkg.desktop` |
| 图标 | `/usr/share/icons/hicolor/scalable/apps/kylinpkg.svg` |
| 收集脚本 | `/opt/kylinpkg/collector/kylinpkg-collect.sh` |

默认下载输出目录是 `/tmp/kylinpkg-out/<profile>-<架构>`，可用 `-o` 或环境变量
`KYLINPKG_OUTPUT_DIR` 覆盖。运行状态仍保存在 `~/.local/share/kylinpkg`。

卸载：`sudo apt remove kylinpkg`。

## 图形界面

```bash
./bin/kylinpkg-gui
# 或
./bin/kylinpkg gui
```

GUI 与 CLI 共用同一个状态目录（默认 `~/.local/share/kylinpkg`），
在 GUI 里导入的 profile/baseline 可以直接被命令行使用，反之亦然。

界面分三块（顶部另有 **“导入收集包”** 和 **“清理缓存”** 按钮）：

1. **apt 源配置（profile）**：按钮行保持 `从预设创建`、`从本机导入`、
   `编辑源配置`、`更多`、`删除` 一行显示；`导入源配置`（自定义
   `sources.list`/`sources.list.d`/preferences/keyring/auth.conf）和
   `从 rootfs 导入` 收在 **“更多”** 菜单里。支持同名资源的管理和删除。
2. **dpkg 初始状态（baseline）**：`导入 status 文件` 支持选择目标机的
   `/var/lib/dpkg/status`，或从本机/rootfs/空基线导入，并命名保存。
3. **下载参数**：选择 profile + baseline（或“全量闭包”），填写软件包名
   （空格或逗号分隔），可用 **“选择版本”** 查看 `apt policy` 里的所有版本；
   默认勾选 **“下载依赖”**，取消后只下载当前包本身；选择输出目录，然后：
   - `解析计划`：只做依赖求解，在下方日志里显示包清单、版本、大小；
   - `下载`：复用同一套隔离 apt root，执行 `apt-get install --download-only`，
     校验哈希、生成 `manifest.json`，可选择同时生成离线 apt 源。

**架构是下拉选择**：`amd64`、`arm64`（aarch64）、`mips64el`（mips64）、
`loongarch64`、`i386`，以及 `amd64,i386` 组合。已有的 profile 若带其他架构，
选中时会动态显示，但默认选项只保留上述几个。

解析/下载在后台线程执行，界面不会卡住；日志区会显示 apt 的解析结果、下载结果和警告。
任务运行时旁边会出现 **“中断”** 按钮：点击会终止正在运行的 apt 及其子进程，
不会修改本机；已下载的部分文件会保留，下次可继续/重试。
命令行下按 `Ctrl+C` 也会中断当前 apt 子进程。
图形界面需要 `python3-tk`（麒麟一般已自带）；没有图形环境时请使用 CLI。

安装 deb 后会自动出现在开始菜单；源码运行时直接用 `./bin/kylinpkg-gui`。
桌面文件源码在 `packaging/kylinpkg.desktop`，安装后位于
`/usr/share/applications/kylinpkg.desktop`。

## 从原始主机收集（bundle）

如果无法直接访问目标版本的原始主机，可以先在原始主机上收集一个包，
再拿回下载器一键导入。收集脚本在 `collector/kylinpkg-collect.sh`。

```bash
# 1) 拷到原始主机并运行（建议 sudo，能读到 auth.conf 等 600 文件）
scp collector/kylinpkg-collect.sh user@target:/tmp/
ssh user@target 'sudo bash /tmp/kylinpkg-collect.sh -o /tmp'
# 输出：/tmp/kylinpkg-bundle-<hostname>-<时间>.tar.gz

# 2) 拿回下载器
scp user@target:/tmp/kylinpkg-bundle-*.tar.gz ./

# 3) 先看内容
./bin/kylinpkg bundle inspect ./kylinpkg-bundle-xxx.tar.gz

# 4) 一键导入 profile + baseline（默认按主机名命名并绑定同架构基线）
./bin/kylinpkg bundle import ./kylinpkg-bundle-xxx.tar.gz \
  --profile sp1-2303 --baseline sp1-2303-default

# 5) 之后就可以正常解析/下载
./bin/kylinpkg resolve -p sp1-2303 zlib1g
```

也可以直接在 GUI 顶部点 **“导入收集包”**，选择 tar.gz 并填写名称。

收集包包含：

- 完整 `rootfs/var/lib/dpkg/status`
- `rootfs/etc/apt` 下的 sources、sources.list.d、preferences、trusted keyrings
- `Signed-By` 引用的 keyring（复制到包内，导入时自动改写为 profile 内路径）
- `meta/` 中的 os-release、架构、apt/dpkg 版本、uname、包列表
- `SHA256SUMS` 与 `bundle.json`

注意：

- 默认**不收集** `/etc/apt/auth.conf`（私有源凭据）。需要时收集端加 `--with-auth`，
  导入时 `bundle import` 会自动带上，`profile import --with-auth` 也支持。
- 收集包可能包含私有源地址/凭据，脚本会把文件权限设为 600，请妥善保管；
  用 `sudo` 运行时脚本会把 tar.gz 的属主改回 `SUDO_USER`，方便直接 scp。
- 跨架构使用：`bundle import ... --profile xxx-arm64 --arch arm64 --no-bind`
  （原基线是 amd64 时不能绑定到 arm64 profile）。
- 更多细节见 `collector/README.md`。

## 内置源预设（26 个）

数据解析自 `docs/kylin-desktop-sources.md`（原始文件：
`~/下载/银河麒麟桌面版软件源地址汇总.md`），已内置到 `kylinpkg/presets.py`。

```bash
# 查看全部预设
./bin/kylinpkg preset list

# 查看某个预设的源地址和注意事项
./bin/kylinpkg preset show sp1-2503

# 从预设创建一个可编辑的 profile
./bin/kylinpkg preset create sp1-2503 --profile sp1-2503 --arch amd64
# 也可以直接绑定已有 baseline
./bin/kylinpkg preset create sp1-2503 --profile sp1-2503 \
  --arch amd64 --baseline sp1-2503-default
```

图形界面：源配置面板点 **“从预设创建”**，左侧选预设、右侧看源预览，
填写名称/架构/基线后创建。

预设分组：

| 分组 | ID |
| --- | --- |
| V10 基础版 | `v10-2107`、`v10-2203` |
| V10 SP1 2107 / 0521 | `sp1-2107-hwe`、`sp1-2107-0521` |
| V10 SP1 2203 | `sp1-2203`、`sp1-2203-hwe` |
| V10 SP1 2303 | `sp1-2303`、`sp1-2303-hwe`、`sp1-2303-hwe-pp` |
| 海思麒麟 | `sp1-kirin990-old`、`sp1-kirin990-new`、`sp1-2203-kirin990`、`sp1-2203-kirin9006c`、`sp1-2303-kirin990`、`sp1-2303-kirin9006c`、`sp1-2303u2-kirin9006c`、`sp1-2303u2-kirin990`、`sp1-2403-kirin9000c` |
| 盘古 | `sp1-2203-pangwu-m900`、`sp1-2303-pangwu-m900` |
| V10 SP1 2403 | `sp1-2403`、`sp1-2403-u1`、`sp1-2403-hwe-u1`、`sp1-2403-u2` |
| V10 SP1 2503 | `sp1-2503-hwe`、`sp1-2503` |

架构缺省规则：

- 预设只对应单一平台（Kirin/Pangwu）时用该架构（`arm64`）；
- 预设列出多个架构时，优先选本机架构（例如 amd64 机器选 `amd64`）；
- 预设没有架构标注时，用本机 dpkg 架构；
- 始终可以用 `--arch` 或 GUI 下拉框覆盖。

### 文档里的几处修正/说明

- 修正版源数据已无 OCR 空格，预设直接使用 `PART-10.1-kirin...` 路径；
- 2107/0521 HWE 的 KY 桌面源含 `$(ARCH)`，创建 profile 时替换为目标主架构（amd64/arm64 已验证）；
- V10SP1-2303 通用版文档重复写了 `universe`，预设已去重；
- 盘古（Pangwu）是华为海思的芯片产品线，ARM64 架构，不是飞腾平台；
  原始汇总表术语仍写“飞腾”，仓库 `docs/` 与预设使用已确认的华为海思说明；
- 最新源数据将 Kirin partner/feature 路径更新为 `10_1-`/`PART-10_1-`；
  第 12 条按文档保留 `10.1-kirin9a0` 的 partner suite；
- 第 16/17 条与第 14/15 条在文档中完全相同，update2 的差异未体现；
- 部分 Kirin/Pangwu partner、`10.1-kirinM900-2303-feature`、`partner/10.1-hwe`
  在当前公网镜像上未验证到（404/超时）；预设会保留文档地址并带警告，
  创建后可在源配置编辑器里改成目标机实际地址；
- 2503 预设在文档中写 `10.1-2503-bugfix`，部分机器实际是
  `10.1-2503-bugfix-limit`，预设带注释提醒。

每次修改 `docs/kylin-desktop-sources.md` 后运行测试，
`tests/test_presets.py` 会逐行校验预设与文档一致（允许重复组件归一）。

## 查看和编辑源配置

图形界面：选中一个 profile，点 **“编辑源配置”**。左侧是文件列表，
右侧是文本编辑器，可 **保存 / 还原 / 新建源文件 / 删除 / 验证**。
保存时会：

- 校验 `.list` / `.sources` 语法；
- 拒绝删除最后一个源（避免 profile 变成空壳）；
- 重新计算文件清单、源摘要、警告和索引指纹，下次解析会自动刷新 apt 索引；
- keyring 文件只读（由导入/收集包管理）。

命令行：

```bash
# 列出文件（可编辑=是/否）
./bin/kylinpkg profile files sp1-2503

# 查看
./bin/kylinpkg profile cat sp1-2503 sources.list
./bin/kylinpkg profile cat sp1-2503 --all

# 用 $EDITOR 交互编辑
./bin/kylinpkg profile edit sp1-2503 sources.list

# 用文件/管道覆盖
./bin/kylinpkg profile set sp1-2503 sources.list --from ./new-sources.list
cat ./preferences | ./bin/kylinpkg profile set sp1-2503 preferences

# 删除或清空（删除最后一个源会被拒绝）
./bin/kylinpkg profile rm-file sp1-2503 sources.list.d/extra.list
```

可编辑文件：`sources.list`、`sources.list.d/*.list|*.sources`、`preferences`、
`preferences.d/*`、`auth.conf`、`auth.conf.d/*`。`keyrings/*` 和 `profile.json`
不可编辑。`profile show --raw` 仍可用于一次性打印全部文本文件。

## 两个一等公民

### profile：一套 apt 源配置

支持四种导入方式，源文件原样保存：

```bash
# 1) 从本机 /etc/apt 抓取
./bin/kylinpkg profile import sp1-2503-x86 --from-system --arch amd64,i386

# 2) 从干净目标机抓取（需要 SSH 免密）
./bin/kylinpkg profile import sp1-2503-arm64 --from-ssh mohao@172.16.101.137 --arch arm64

# 3) 从解开的 rootfs 抓取
./bin/kylinpkg profile import sp1-2503-img --from-rootfs /mnt/kylin-rootfs --arch amd64

# 4) 从导出的 sources 文件/目录导入
./bin/kylinpkg profile import sp1-2503-custom \
  --sources-file ./sources.list \
  --sources-dir ./sources.list.d \
  --preferences-dir ./preferences.d \
  --keyring ./kylin-archive-keyring.gpg \
  --arch amd64,i386
```

- `.list` 与 deb822 `.sources` 都支持。
- `--from-system/ssh/rootfs` 会同时抓取 `preferences`、`preferences.d` 和 `trusted.gpg*`。
- `--capture-baseline NAME` 可以在抓源的同时抓 `dpkg status`，一次完成 profile + baseline。
- `Signed-By` 引用的 keyring 会被复制进 profile 并改写路径（`keyrings/signed-by/`），
  便于跨机器复用；源里内嵌的凭据请用 `--with-auth`/`--auth-file` 显式导入。
- 架构可以写 `x86_64`/`aarch64` 别名，工具会归一成 `amd64`/`arm64`。
- 还提供按 Kylin suite 快捷生成的 `profile add`（适合源结构已知时）：

```bash
./bin/kylinpkg profile add sp1-2503 --kylin-suite 10.1-kylin-2503 --arch arm64
```

### baseline：一份目标机 dpkg status

```bash
# 从目标机导出的 status 文件
./bin/kylinpkg baseline import sp1-2503-default --status-file ./status.sp1-2503

# 从目标机/ rootfs / 本机直接抓
./bin/kylinpkg baseline import sp1-2503-default --from-ssh mohao@172.16.101.137
./bin/kylinpkg baseline import sp1-2503-default --from-rootfs /mnt/kylin-rootfs
./bin/kylinpkg baseline import host-current --from-system
```

导入时会校验 Deb822 结构，统计已安装包数和架构；如果 baseline 中有 profile 未启用的架构，解析时会直接报错，避免"看起来成功、实际结果不对"。

> baseline 必须是完整的 `/var/lib/dpkg/status`（含 Version/Architecture/Status/依赖字段）。
> `dpkg --get-selections` 只有包名和状态，不能用于 apt 依赖求解。
> 跨架构下载时 baseline 也必须同架构：amd64 的基线不能用于 arm64；此时用 `--full`，或导入 arm64 目标机的 status。

绑定与覆盖：

```bash
./bin/kylinpkg profile bind sp1-2503-x86 --baseline sp1-2503-default
./bin/kylinpkg profile bind sp1-2503-x86 --baseline empty   # 解除绑定，回到全量闭包
```

## 选择版本与多版本下载

apt 的 `policy` 里常能看到一个包有多个版本（基础源 / update / bugfix / 不同 suite）。
现在可以：

```bash
# 查看某个 profile/架构下该包的所有版本、优先级、是否可下载、来源
./bin/kylinpkg versions -p sp1-2503 zlib1g

# 只要某个版本
./bin/kylinpkg download -p sp1-2503 -o ./out zlib1g=1:1.2.11.dfsg-2kylin1.5k0.2

# 同时下载同一软件包的多个版本（会分别解析依赖，最后合并）
./bin/kylinpkg download -p sp1-2503 -o ./out --repo \
  zlib1g=1:1.2.11.dfsg-2kylin1.5k0.2 \
  zlib1g=1:1.2.11.dfsg-2kylin1.5k0.3update1
```

图形界面：在“软件包”输入框旁点 **“选择版本”**，输入包名后查询；
版本列表支持 Ctrl/Shift 多选，点 **“加入软件包列表”** 后正常解析/下载。

实现方式：

- 同一软件包的多个版本无法在一个 apt 事务里同时安装，工具会**每个版本单独跑一次**
  `apt-get install --download-only pkg=version`；
- 每个版本的依赖闭包分别解析，最终把 `.deb` 去重合并到同一个 `debs/`，
  生成一个 `manifest.json` 和一个包含多个版本的离线 apt 源；
- `manifest.json` 的 `version_plans` 记录每个版本请求组及其文件；
- 离线源里同时存在多个版本，目标机可用 `apt install pkg=版本` 精确安装，
  但 `apt` 默认候选仍按 pin/优先级选择最高版本；
- 不同版本的单次下载仍沿用当前 profile/架构/baseline/Recommends 设置；
  多版本合并时要求这些设置一致；
- 版本查询也会走隔离 apt root，支持 **中断**；查询结果来自 `apt-cache policy`，
  因此先 `update` 一次索引更准确。

## 解析与下载

```bash
# 只看计划，不下载
./bin/kylinpkg resolve -p sp1-2503-x86 zlib1g
./bin/kylinpkg resolve -p sp1-2503-arm64 -a arm64 --full --json zlib1g

# 下载到指定目录，并生成离线 apt 源
./bin/kylinpkg download -p sp1-2503-arm64 -a arm64 --full \
  -o ./out/arm64 --repo zlib1g

# 不指定 -o 时默认输出到 /tmp/kylinpkg-out/<profile>-<架构>
./bin/kylinpkg download -p sp1-2503-x86 zlib1g

# 只下载 zlib1g 本身，不下载依赖
./bin/kylinpkg download -p sp1-2503-x86 --no-deps \
  -o ./out/only zlib1g
```

闭包模式：

- profile 绑定了 baseline → 默认**增量**：只下载目标机缺失/需要升级的包；
- 没有绑定 baseline → 默认**全量**；
- `--full` 强制全量；`--baseline NAME` 临时指定基线；`--baseline empty` 等价于全量。

其他常用参数：

- `--no-deps`：只下载请求的包本身，**不解析也不下载依赖**（对应 GUI 取消勾选“下载依赖”）。
- `--no-recommends`：不拉 Recommends（默认与 `apt install` 一致，会拉；`--no-deps` 时无影响）。
- `--no-update`：复用 12 小时内的索引（源配置指纹变化时会自动失效）。
- `--force-update`：清空隔离索引后重新下载。
- `-a amd64,arm64`：目标架构集合；第一个是"本机架构"，决定无架构限定的依赖如何解析。

### 只下载当前包（不含依赖）

勾选/取消 GUI 的 **“下载依赖”**，或命令行加 `--no-deps`：

- 带依赖（默认）：`apt-get install --download-only`，下载完整依赖闭包；
- 不带依赖：改用 `apt-get download pkg=版本`，只取请求包本身，
  即使 baseline 显示已安装也会下载（适合单独归档/替换某个 `.deb`）；
- 此时 `manifest.json` 中 `with_dependencies` 为 `false`；
- 生成的离线源只含请求包；目标机安装前必须已经具备依赖，
  否则 `apt install` 仍会报缺依赖；
- 与“选择版本/多版本”可组合：

```bash
./bin/kylinpkg download -p sp1-2503 --no-deps -o ./out \
  zlib1g=1:1.2.11.dfsg-2kylin1.5k0.2 \
  zlib1g=1:1.2.11.dfsg-2kylin1.5k0.3update1
```

下载完成后目录结构：

```
out/arm64/
  debs/*.deb
  manifest.json          # 包名、版本、架构、大小、SHA256、来源、with_dependencies
  Packages / Packages.gz # 离线源索引
  Release
  sources.list           # 目标机可直接使用的源片段
```

`manifest.json` 是自校验清单；`kylinpkg verify DIR` 会逐包重算 SHA256，并核对 Packages 索引。

## 目标机怎么用

**方式一：离线 apt 源**

```bash
# 把整个目录拷到目标机，例如 /opt/kylinpkg/arm64
# 修改 sources.list 中的路径：
# deb [trusted=yes] file:/opt/kylinpkg/arm64 ./
sudo cp sources.list /etc/apt/sources.list.d/kylinpkg-local.list
sudo apt update
sudo apt install zlib1g
```

**方式二：直接装 deb**

把 `debs/*.deb` 拷到目标机同一目录，用你现有的 `deb-install.run` 双击安装即可（它会调 `dpkg -i` + `apt-get -f install`）。

## 常见失败原因（麒麟实测）

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| `libc6` 没有候选 | `libc6` 在 **universe**，源里只挂了 main | 四个组件都挂上 |
| `libgcc-s1` 无法安装 | 只挂了叠加 suite，缺基础 suite | 同时挂 `10.1-kylin` |
| 解析出的版本和目标机不同 | 没带 `preferences`（pin） | `--from-system` 或 `--preferences-*` 导入 |
| `NO_PUBKEY` / 签名失败 | keyring 没导入 | `--keyring`、`--from-system`，或源加 `trusted=yes` |
| `does not have a Release file` | suite 名称不对 | 对照目标机 `apt-cache policy` 或源文件 |
| 增量模式直接报架构不一致 | baseline 有 i386/arm64 等额外架构 | 用 `-a` 补齐，或换匹配的 baseline |
| root 运行时下载失败 | `/home` 权限 700，apt 的 `_apt` 沙箱进不去 | 工具已自动加 `APT::Sandbox::User=root` |
| SSH 抓取失败 | `ssh` 需要交互输密码 | 先配置 SSH key；工具使用 `BatchMode=yes` |
| `apt update` 长时间卡住 | IPv6 路由或第三方源不可达 | 点 GUI 的“中断”终止任务；工具默认 `Acquire::ForceIPv4=true`；仍卡住就编辑源去掉不可用地址；纯 IPv6 环境可在 profile 的 `apt_options` 里覆盖 |

## 状态目录与安全

```
~/.local/share/kylinpkg/
  profiles/<name>/       # sources、preferences、keyrings、profile.json
  baselines/<name>/      # status、meta.json
  roots/<profile>/<arch>/# 隔离 apt root（可随时 gc）
  downloads/             # 预留
```

- 目录 0700，文件 0600；源里若内嵌凭据，`profile show` 默认脱敏，`--raw` 才显示原文。
- 下载由 apt 自身完成并校验哈希；`file:` 源由工具复制并复核。
- 离线源默认写 `[trusted=yes]`，生产环境建议改用签名源或把 keyring 一并下发。
- `kylinpkg gc --cache` 可清理可重建的隔离索引/包缓存。

## 清理缓存

图形界面顶部有 **“清理缓存”** 按钮（“文件”菜单里也有）。命令行：

```bash
# 清理全部 profile 的隔离 apt 索引和包缓存
./bin/kylinpkg gc --cache

# 只清理某个 profile
./bin/kylinpkg gc --cache --profile sp1-2503
```

清理内容：

- `~/.local/share/kylinpkg/roots/` 下的 apt 包索引（lists）、apt archives 缓存、
  pkgcache、partial 下载等可重建数据；
- **不会删除** profile、baseline、已下载到输出目录的 `.deb`/manifest/离线源；
- 清理后会显示释放的空间；下次解析会自动重建索引。

`--roots` 是 `--cache` 的别名。任务运行期间 GUI 按钮会自动置灰，避免误删正在使用的索引。

## 测试

```bash
# 单元测试（不联网；有 DISPLAY 时会顺带做 GUI 冒烟测试）
# test_bundle 会实际运行 collector 并导入临时状态；
# test_versions 用本地双版本 deb 仓库验证版本查询、多版本合并和离线源回读；
# test_no_deps 验证“仅当前包”与完整依赖两种模式；
# test_cache 验证缓存清理不会动 profile/baseline
python3 -m unittest discover -s tests -v

# 联网集成测试：arm64 全量闭包、下载、离线源回灌、增量零下载、宿主未被修改
KYLINPKG_NET_TESTS=1 python3 -m unittest tests.test_integration -v
```

## 边界

- 镜像上旧版本包可能被删除；需要精确复现时应在 profile 中固定 suite，必要时配合快照源（本版未实现）。
- 跨架构只做依赖求解和下载，不执行目标架构二进制；`--download-only` 不需要 qemu。
- 第三方源的 `Signed-By: /绝对路径` 在本机可用；跨机器复用时需要把对应 keyring 一并导入。
- 依赖求解使用的是**运行工具这台机器上的 apt 版本与解析器**。目标机与工具机跨大版本（例如 SP1 与 SP3）时，建议在对应版本的系统上运行，或至少用同版本基线核对结果。
