#!/bin/bash
# =============================================================================
#  kylinpkg-collect.sh
#
#  在“原始主机”（其他版本的麒麟/Ubuntu 系机器）上运行，收集：
#    - 完整 /var/lib/dpkg/status（不是 dpkg --get-selections）
#    - /etc/apt/sources.list 与 sources.list.d
#    - /etc/apt/preferences 与 preferences.d
#    - /etc/apt/trusted.gpg 与 trusted.gpg.d
#    - Signed-By 引用的 keyring（从 /usr/share/keyrings 等绝对路径复制）
#    - 系统元数据（os-release、架构、apt/dpkg 版本、uname）
#
#  产出一个 tar.gz，可直接在下载器上执行：
#     kylinpkg bundle import <file.tar.gz> --profile <名称> --baseline <名称>
#  或在 GUI 里点“导入收集包…”。
#
#  用法：
#     sudo bash kylinpkg-collect.sh [-o 输出目录] [-n 名称前缀] [--with-auth]
#
#  默认不收集 /etc/apt/auth.conf；如确需收集私有源凭据，加 --with-auth，
#  并妥善保管生成的收集包（脚本会把收集包权限设为 600）。
# =============================================================================

set -u
shopt -s nullglob

VERSION="0.2.0"
OUT_DIR="${TMPDIR:-/tmp}"
PREFIX=""
WITH_AUTH=0
WARNINGS=()

usage() {
    cat <<'EOF'
用法: kylinpkg-collect.sh [选项]

  -o, --output DIR   输出目录（默认 $TMPDIR 或 /tmp）
  -n, --name NAME    收集包名称前缀（默认 kylinpkg-bundle-<host>-<时间>）
      --with-auth    同时收集 /etc/apt/auth.conf 与 auth.conf.d（含明文凭据）
  -h, --help         显示帮助

收集完成后会把 tar.gz 路径和导入命令打印出来。
EOF
}

while [ $# -gt 0 ]; do
    case "$1" in
        -o|--output)
            [ $# -ge 2 ] || { echo "缺少 --output 参数" >&2; exit 1; }
            OUT_DIR="$2"; shift 2 ;;
        -n|--name)
            [ $# -ge 2 ] || { echo "缺少 --name 参数" >&2; exit 1; }
            PREFIX="$2"; shift 2 ;;
        --with-auth)
            WITH_AUTH=1; shift ;;
        -h|--help)
            usage; exit 0 ;;
        *)
            echo "未知参数：$1" >&2; usage >&2; exit 1 ;;
    esac
done

for cmd in tar sha256sum dpkg date hostname find sort; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "缺少命令：$cmd" >&2
        exit 1
    fi
done

if [ ! -r /var/lib/dpkg/status ]; then
    echo "无法读取 /var/lib/dpkg/status；请在正常的 dpkg 系统上运行。" >&2
    exit 1
fi

umask 077
mkdir -p "$OUT_DIR" 2>/dev/null || { echo "无法创建输出目录：$OUT_DIR" >&2; exit 1; }
[ -w "$OUT_DIR" ] || { echo "输出目录不可写：$OUT_DIR" >&2; exit 1; }
OUT_DIR="$(cd "$OUT_DIR" && pwd)" || { echo "无法解析输出目录" >&2; exit 1; }

HOST_RAW="$(hostname 2>/dev/null || echo unknown)"
HOST_SAFE="$(printf '%s' "$HOST_RAW" | tr -c 'A-Za-z0-9._-' '-' | sed -e 's/-\+/-/g' -e 's/^[-._]*//' -e 's/[-._]*$//' | cut -c1-40)"
[ -n "$HOST_SAFE" ] || HOST_SAFE="unknown"
TS="$(date +%Y%m%d-%H%M%S)"
if [ -n "$PREFIX" ]; then
    NAME_SAFE="$(printf '%s' "$PREFIX" | tr -c 'A-Za-z0-9._-' '-' | sed -e 's/-\+/-/g' -e 's/^[-._]*//' -e 's/[-._]*$//' | cut -c1-60)"
    [ -n "$NAME_SAFE" ] || NAME_SAFE="kylinpkg-bundle-$HOST_SAFE-$TS"
else
    NAME_SAFE="kylinpkg-bundle-$HOST_SAFE-$TS"
fi
BUNDLE_NAME="$NAME_SAFE"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/kylinpkg-collect.XXXXXX")" || { echo "无法创建临时目录" >&2; exit 1; }
trap 'rm -rf "$WORK"' EXIT
B="$WORK/$BUNDLE_NAME"
ROOT="$B/rootfs"

mkdir -p \
    "$ROOT/etc/apt/sources.list.d" \
    "$ROOT/etc/apt/preferences.d" \
    "$ROOT/var/lib/dpkg" \
    "$ROOT/usr/share/keyrings" \
    "$B/meta"

add_warning() {
    local candidate="$1"
    local existing
    for existing in ${WARNINGS[@]+"${WARNINGS[@]}"}; do
        [ "$existing" = "$candidate" ] && return 0
    done
    WARNINGS+=("$candidate")
}

copy_file() { # src dest
    [ -f "$1" ] || return 0
    mkdir -p "$(dirname "$2")" || return 1
    cp -L -- "$1" "$2"
}

copy_tree_files() { # src_dir dest_dir patterns...
    local src="$1" dest="$2"
    shift 2
    local pattern file base
    for pattern in "$@"; do
        for file in "$src"/$pattern; do
            [ -f "$file" ] || continue
            base="$(basename "$file")"
            case "$base" in
                .*|*.bak|*.save|*.disabled|*~) continue ;;
            esac
            copy_file "$file" "$dest/$base" || return 1
        done
    done
    return 0
}

# ---------------------------------------------------------------------------
# 1. 核心数据
# ---------------------------------------------------------------------------
cp -- /var/lib/dpkg/status "$ROOT/var/lib/dpkg/status" || {
    echo "复制 /var/lib/dpkg/status 失败" >&2
    exit 1
}

copy_file /etc/apt/sources.list "$ROOT/etc/apt/sources.list" || exit 1
copy_tree_files /etc/apt/sources.list.d "$ROOT/etc/apt/sources.list.d" '*.list' '*.sources' || exit 1
copy_file /etc/apt/preferences "$ROOT/etc/apt/preferences" || exit 1
copy_tree_files /etc/apt/preferences.d "$ROOT/etc/apt/preferences.d" '*' || exit 1
copy_file /etc/apt/trusted.gpg "$ROOT/etc/apt/trusted.gpg" || exit 1
copy_tree_files /etc/apt/trusted.gpg.d "$ROOT/etc/apt/trusted.gpg.d" '*' || exit 1

if [ "$WITH_AUTH" -eq 1 ]; then
    auth_found=0
    if [ -f /etc/apt/auth.conf ]; then
        copy_file /etc/apt/auth.conf "$ROOT/etc/apt/auth.conf" || exit 1
        auth_found=1
    fi
    if [ -d /etc/apt/auth.conf.d ]; then
        copy_tree_files /etc/apt/auth.conf.d "$ROOT/etc/apt/auth.conf.d" '*' || exit 1
        auth_found=1
    fi
    if [ "$auth_found" -eq 1 ]; then
        add_warning "已收集 apt 凭据文件（auth.conf / auth.conf.d），请妥善保管收集包"
    else
        add_warning "指定了 --with-auth，但未找到 auth.conf / auth.conf.d"
    fi
fi

# ---------------------------------------------------------------------------
# 2. 收集 Signed-By 引用的 keyring
# ---------------------------------------------------------------------------
source_files=()
[ -f "$ROOT/etc/apt/sources.list" ] && source_files+=("$ROOT/etc/apt/sources.list")
for file in "$ROOT"/etc/apt/sources.list.d/*; do
    [ -f "$file" ] && source_files+=("$file")
done

if [ ${#source_files[@]} -eq 0 ]; then
    add_warning "没有收集到任何 apt 源文件（sources.list / sources.list.d）"
fi

declare -A SEEN_KEYS=()
for file in ${source_files[@]+"${source_files[@]}"}; do
    # 一行式：signed-by=/path
    while IFS= read -r keypath; do
        [ -n "$keypath" ] || continue
        [ -n "${SEEN_KEYS[$keypath]:-}" ] && continue
        if [ ! -f "$keypath" ]; then
            add_warning "Signed-By 引用的 keyring 不存在：$keypath"
            continue
        fi
        SEEN_KEYS[$keypath]=1
        dest="$ROOT/${keypath#/}"
        mkdir -p "$(dirname "$dest")" || exit 1
        cp -L -- "$keypath" "$dest" || exit 1
    done < <(
        sed -e 's/^[[:space:]]*//' "$file" 2>/dev/null \
            | grep -v '^#' \
            | grep -hoiE 'signed-by=[^[:space:]]+' \
            | sed -E 's/^[Ss]igned-[Bb]y=//; s/\]$//' || true
    )

    # deb822：Signed-By: /path1 /path2（含缩进续行）
    while IFS= read -r keypath; do
        [ -n "$keypath" ] || continue
        [ -n "${SEEN_KEYS[$keypath]:-}" ] && continue
        if [ ! -f "$keypath" ]; then
            add_warning "Signed-By 引用的 keyring 不存在：$keypath"
            continue
        fi
        SEEN_KEYS[$keypath]=1
        dest="$ROOT/${keypath#/}"
        mkdir -p "$(dirname "$dest")" || exit 1
        cp -L -- "$keypath" "$dest" || exit 1
    done < <(
        awk '
            BEGIN { in_sb = 0 }
            {
                if ($0 ~ /^[ \t]*#/) next
                lower = tolower($0)
                if (lower ~ /^signed-by:/) {
                    in_sb = 1
                    sub(/^[Ss]igned-[Bb]y:[ \t]*/, "")
                    print
                    next
                }
                if (in_sb && $0 ~ /^[ \t]/) { print; next }
                in_sb = 0
            }
        ' "$file" 2>/dev/null | tr ' \t' '\n\n' | sed -e 's/\]$//' | grep '^/' || true
    )
done

# ---------------------------------------------------------------------------
# 3. 元数据与告警
# ---------------------------------------------------------------------------
cp /etc/os-release "$B/meta/os-release" 2>/dev/null || true
dpkg --print-architecture > "$B/meta/dpkg-arch" 2>/dev/null || true
dpkg --print-foreign-architectures > "$B/meta/dpkg-foreign-archs" 2>/dev/null || true
apt-get --version 2>/dev/null | head -n 1 > "$B/meta/apt-version" || true
dpkg --version 2>/dev/null | head -n 1 > "$B/meta/dpkg-version" || true
uname -a > "$B/meta/uname" 2>/dev/null || true
printf '%s\n' "$HOST_RAW" > "$B/meta/hostname"
dpkg-query -W -f='${Package}\t${Version}\t${Architecture}\n' > "$B/meta/packages.list" 2>/dev/null || true

if [ "$(id -u)" -ne 0 ]; then
    add_warning "未以 root 运行；auth.conf 等 600 权限文件可能没有收集到"
fi
if grep -rqiE '://[^/[:space:]]+:[^/[:space:]]+@' "$ROOT/etc/apt" 2>/dev/null; then
    add_warning "apt 源中包含明文凭据，请妥善保管收集包"
fi

PRIMARY_ARCH="$(dpkg --print-architecture 2>/dev/null || echo unknown)"
ARCHS=()
[ -n "$PRIMARY_ARCH" ] && ARCHS+=("$PRIMARY_ARCH")
while IFS= read -r arch; do
    [ -n "$arch" ] || continue
    [ "$arch" = "$PRIMARY_ARCH" ] && continue
    ARCHS+=("$arch")
done < <(dpkg --print-foreign-architectures 2>/dev/null || true)

json_escape() {
    printf '%s' "$1" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g'
}

OS_NAME=""
OS_VERSION=""
if [ -r /etc/os-release ]; then
    # shellcheck disable=SC1091
    . /etc/os-release
    OS_NAME="${NAME:-}"
    OS_VERSION="${VERSION:-}"
fi

ARCH_JSON=""
for arch in ${ARCHS[@]+"${ARCHS[@]}"}; do
    [ -n "$ARCH_JSON" ] && ARCH_JSON+=", "
    ARCH_JSON+="\"$(json_escape "$arch")\""
done

WARN_JSON=""
for warning in ${WARNINGS[@]+"${WARNINGS[@]}"}; do
    [ -n "$WARN_JSON" ] && WARN_JSON+=", "
    WARN_JSON+="\"$(json_escape "$warning")\""
done

CREATED_AT="$(date -Iseconds 2>/dev/null || date)"

cat > "$B/bundle.json" <<JSON
{
  "schema": 1,
  "tool": "kylinpkg-collect",
  "tool_version": "$VERSION",
  "created_at": "$(json_escape "$CREATED_AT")",
  "hostname": "$(json_escape "$HOST_RAW")",
  "os_name": "$(json_escape "$OS_NAME")",
  "os_version": "$(json_escape "$OS_VERSION")",
  "primary_arch": "$(json_escape "$PRIMARY_ARCH")",
  "architectures": [$ARCH_JSON],
  "with_auth": $WITH_AUTH,
  "warnings": [$WARN_JSON]
}
JSON

cat > "$B/README.txt" <<'EOF'
kylinpkg 原始主机收集包

本包包含：
  rootfs/var/lib/dpkg/status       完整 dpkg 状态
  rootfs/etc/apt/...               apt 源、preferences、keyrings
  rootfs/usr/share/keyrings/...    Signed-By 引用的 keyring
  meta/                            系统与版本元数据
  bundle.json、SHA256SUMS

在下载器上导入：
  kylinpkg bundle inspect <本文件.tar.gz>
  kylinpkg bundle import <本文件.tar.gz> --profile <名称> --baseline <名称>
或在图形界面中点击“导入收集包…”。

注意：收集包可能包含 apt 私有源凭据，请妥善保管。
EOF

# ---------------------------------------------------------------------------
# 4. 校验和与打包
# ---------------------------------------------------------------------------
(
    cd "$B" || exit 1
    find rootfs meta bundle.json README.txt -type f -exec sha256sum {} + | sort -k2 > SHA256SUMS
) || { echo "生成 SHA256SUMS 失败" >&2; exit 1; }

OUT_FILE="$OUT_DIR/$BUNDLE_NAME.tar.gz"
( cd "$WORK" && tar -czf "$OUT_FILE" "$BUNDLE_NAME" ) || {
    echo "打包失败：$OUT_FILE" >&2
    exit 1
}
chmod 600 "$OUT_FILE"
# sudo 运行时把输出交还给调用者，否则普通用户 scp 不出去
if [ -n "${SUDO_USER:-}" ] && [ "$SUDO_USER" != "root" ]; then
    SUDO_GROUP="$(id -gn "$SUDO_USER" 2>/dev/null || printf '%s' "$SUDO_USER")"
    chown "$SUDO_USER":"$SUDO_GROUP" "$OUT_FILE" 2>/dev/null || true
fi
if ! tar -tzf "$OUT_FILE" >/dev/null 2>&1; then
    echo "收集包自检失败：$OUT_FILE" >&2
    exit 1
fi

ARCH_DISPLAY="${ARCHS[*]:-unknown}"
echo "收集完成：$OUT_FILE"
echo "  主机：$HOST_RAW"
echo "  系统：${OS_NAME:-unknown} ${OS_VERSION:-}"
echo "  架构：$ARCH_DISPLAY"
echo "  dpkg status：$(wc -c < "$ROOT/var/lib/dpkg/status" 2>/dev/null || echo '?') 字节"
echo "  源文件：${#source_files[@]} 个"
if [ ${#WARNINGS[@]} -gt 0 ]; then
    echo "  警告："
    for warning in "${WARNINGS[@]}"; do
        echo "    - $warning"
    done
fi
echo
echo "在下载器上导入："
echo "  kylinpkg bundle import \"$OUT_FILE\" --profile <名称> --baseline <名称>"
echo "或 GUI：导入收集包…"
