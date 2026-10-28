#!/bin/bash
# 构建 kylinpkg 的 .deb 包（安装到 /opt/kylinpkg）
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PACKAGE="kylinpkg"
VERSION="$(python3 -c "import sys; sys.path.insert(0, '${PROJECT_DIR}'); import kylinpkg; print(kylinpkg.__version__)")"
ARCH="all"
DIST_DIR="${PROJECT_DIR}/dist"
BUILD_DIR="${PROJECT_DIR}/build"
STAGE="${BUILD_DIR}/${PACKAGE}_${VERSION}_${ARCH}"
OUT="${DIST_DIR}/${PACKAGE}_${VERSION}_${ARCH}.deb"

for cmd in dpkg-deb python3; do
    command -v "$cmd" >/dev/null 2>&1 || { echo "缺少命令：$cmd" >&2; exit 1; }
done

rm -rf "$STAGE"
mkdir -p \
    "$STAGE/DEBIAN" \
    "$STAGE/opt/kylinpkg" \
    "$STAGE/usr/bin" \
    "$STAGE/usr/share/applications" \
    "$STAGE/usr/share/doc/kylinpkg" \
    "$STAGE/usr/share/icons/hicolor/scalable/apps" \
    "$DIST_DIR"

# 主程序放 /opt/kylinpkg（只复制两个入口脚本，避免把 bin/ 下的下载结果打进包）
mkdir -p "$STAGE/opt/kylinpkg/bin"
cp -a "$PROJECT_DIR/kylinpkg" "$STAGE/opt/kylinpkg/"
install -m 755 "$PROJECT_DIR/bin/kylinpkg" "$STAGE/opt/kylinpkg/bin/kylinpkg"
install -m 755 "$PROJECT_DIR/bin/kylinpkg-gui" "$STAGE/opt/kylinpkg/bin/kylinpkg-gui"
cp -a "$PROJECT_DIR/collector" "$STAGE/opt/kylinpkg/"
cp -a "$PROJECT_DIR/docs" "$STAGE/opt/kylinpkg/"
cp -a "$PROJECT_DIR/examples" "$STAGE/opt/kylinpkg/"
cp "$PROJECT_DIR/README.md" "$STAGE/opt/kylinpkg/"
cp "$PROJECT_DIR/CHANGELOG.md" "$STAGE/opt/kylinpkg/"
cp "$PROJECT_DIR/CONTRIBUTING.md" "$STAGE/opt/kylinpkg/"
cp "$PROJECT_DIR/LICENSE" "$STAGE/opt/kylinpkg/"

find "$STAGE/opt/kylinpkg" -type d -name '__pycache__' -prune -exec rm -rf {} +
find "$STAGE/opt/kylinpkg" -type f -name '*.pyc' -delete
find "$STAGE/opt/kylinpkg" -type d -exec chmod 755 {} +
find "$STAGE/opt/kylinpkg" -type f -exec chmod 644 {} +
chmod 755 \
    "$STAGE/opt/kylinpkg/bin/kylinpkg" \
    "$STAGE/opt/kylinpkg/bin/kylinpkg-gui" \
    "$STAGE/opt/kylinpkg/collector/kylinpkg-collect.sh"

# /usr/bin 快捷入口
ln -s /opt/kylinpkg/bin/kylinpkg "$STAGE/usr/bin/kylinpkg"
ln -s /opt/kylinpkg/bin/kylinpkg-gui "$STAGE/usr/bin/kylinpkg-gui"

# 桌面文件与图标（SVG 供应用菜单使用；PNG 供 tkinter 窗口/任务栏
# 通过 iconphoto 加载，并补充 hicolor 位图尺寸）
install -m 644 "$PROJECT_DIR/packaging/kylinpkg.desktop" \
    "$STAGE/usr/share/applications/kylinpkg.desktop"
install -m 644 "$PROJECT_DIR/packaging/kylinpkg.svg" \
    "$STAGE/usr/share/icons/hicolor/scalable/apps/kylinpkg.svg"
for sz in 16 32 48 64 128 256; do
    png="$PROJECT_DIR/kylinpkg/resources/icons/kylinpkg-${sz}.png"
    [ -f "$png" ] || { echo "缺少图标：$png" >&2; exit 1; }
    dir="$STAGE/usr/share/icons/hicolor/${sz}x${sz}/apps"
    mkdir -p "$dir"
    install -m 644 "$png" "$dir/kylinpkg.png"
done

# 文档
install -m 644 "$PROJECT_DIR/README.md" "$STAGE/usr/share/doc/kylinpkg/README.md"
install -m 644 "$PROJECT_DIR/CHANGELOG.md" "$STAGE/usr/share/doc/kylinpkg/CHANGELOG.md"
install -m 644 "$PROJECT_DIR/CONTRIBUTING.md" "$STAGE/usr/share/doc/kylinpkg/CONTRIBUTING.md"
# copyright 用 DEP-5 机器可读格式（Debian Policy 12.5），不用裸 LICENSE 文本
install -m 644 "$PROJECT_DIR/packaging/copyright" "$STAGE/usr/share/doc/kylinpkg/copyright"

find "$STAGE" -type d -exec chmod 755 {} +
INSTALLED_SIZE="$(du -sk "$STAGE" | awk '{print $1}')"
cat > "$STAGE/DEBIAN/control" <<EOF
Package: ${PACKAGE}
Version: ${VERSION}
Architecture: ${ARCH}
Maintainer: mohao <mohao@users.noreply.github.com>
Installed-Size: ${INSTALLED_SIZE}
Homepage: https://github.com/MoHa0-bot/kydesktop-tools
Depends: python3 (>= 3.8), python3-tk, apt, apt-utils, dpkg
Recommends: ca-certificates, openssh-client
Section: admin
Priority: optional
Description: Kylin deb offline package downloader
 kylinpkg downloads .deb packages and dependencies from selectable
 apt source profiles and architectures using an isolated apt root,
 without modifying the host's /etc/apt or /var/lib/dpkg.
 .
 Features: tkinter GUI, offline apt repository generation, bundle
 import from original hosts, built-in source presets, exact version
 selection, dependency on/off, cache cleanup and cancellable tasks.
EOF

cat > "$STAGE/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -e
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database -q /usr/share/applications || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -q /usr/share/icons/hicolor || true
fi
exit 0
EOF
chmod 755 "$STAGE/DEBIAN/postinst"

BUILD_OPTS=(--root-owner-group)
rm -f "$OUT"
dpkg-deb --build "${BUILD_OPTS[@]}" "$STAGE" "$OUT" >/dev/null

echo "已生成：$OUT"
dpkg-deb --info "$OUT" | sed -n '1,20p'
echo
echo "安装："
echo "  sudo apt install \"$OUT\""
echo "或："
echo "  sudo dpkg -i \"$OUT\" && sudo apt -f install"
echo
echo "安装后："
echo "  主程序：/opt/kylinpkg"
echo "  命令：  /usr/bin/kylinpkg、/usr/bin/kylinpkg-gui"
echo "  桌面：  /usr/share/applications/kylinpkg.desktop"
