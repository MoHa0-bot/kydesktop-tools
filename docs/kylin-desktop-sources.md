# 银河麒麟（Kylin）桌面操作系统软件源地址汇总

> 本文档汇总了银河麒麟 V10 / V10 SP1 各版本、各硬件平台对应的 apt 软件源配置，可直接用于 `/etc/apt/sources.list` 配置。

---

## 一、V10 基础版（非 SP1）

### 1. V10-2107 / 2101.0710 等

```deb
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.0 main restricted universe multiverse
deb http://archive.kylinos.cn/kylin/partner juniper main
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.0-fixs main
```

### 2. V10-2203（X86_64, ARM64, MIPS64el）

```deb
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.0 main restricted universe multiverse
deb http://archive.kylinos.cn/kylin/partner juniper main
deb http://archive2.kylinos.cn/deb/kylin/production/PART-V10/custom/partner/V10 default all
```

---

## 二、V10 SP1 - 2107 / 211217 / 0521 / 0326 系列

### 3. V10SP1-2107&211217-HWE

```deb
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-hwe main restricted universe multiverse
deb http://archive.kylinos.cn/kylin/partner 10.1-hwe main
```

### 4. V10SP1-2107&211217&0521（X86_64, ARM64, MIPS64el, ...）

```deb
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1 main universe multiverse restricted
deb http://archive2.kylinos.cn/deb/kylin/production/PART-V10-SP1/custom/partner/V10-SP1 default all
```

---

## 三、V10 SP1 - 2203 系列

### 5. V10SP1-2203（X86_64, ARM64, MIPS64el, LoongArch64）

```deb
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1 main restricted universe multiverse
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2203-updates main restricted universe multiverse
deb http://archive2.kylinos.cn/deb/kylin/production/PART-V10-SP1/custom/partner/V10-SP1 default all
```

### 6. V10SP1-2203-HWE

```deb
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1 main restricted universe multiverse
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2203-hwe-updates main restricted universe multiverse
deb http://archive2.kylinos.cn/deb/kylin/production/PART-V10-SP1/custom/partner/V10-SP1 default all
```

---

## 四、V10 SP1 - 2303 系列

### 7. V10SP1-2303 & update2（普通版）

```deb
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1 main restricted universe universe multiverse
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2303-updates main restricted universe multiverse
deb http://archive2.kylinos.cn/deb/kylin/production/PART-V10-SP1/custom/partner/V10-SP1 default all
```

### 8. V10SP1-2303-HWE & update2

```deb
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1 main restricted universe multiverse
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2303-updates main restricted universe multiverse
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2303-hwe-updates main restricted universe multiverse
deb http://archive2.kylinos.cn/deb/kylin/production/PART-V10-SP1/custom/partner/V10-SP1 default all
```

### 9. V10SP1-2303-HWE-PP

```deb
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1 main restricted universe multiverse
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2303-updates main restricted universe multiverse
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2303-hwe-pp-updates main restricted universe multiverse
deb http://archive2.kylinos.cn/deb/kylin/production/PART-V10-SP1/custom/partner/V10-SP1 default all
```

---

## 五、V10 SP1 - 海思麒麟（Kirin）专用版本

### 10. V10SP1 - 海思麒麟990（早期版）

```deb
deb http://archive1.kylinos.cn/kylin/KYLIN-ALL 10.1-pv main restricted universe multiverse
deb http://archive2.kylinos.cn/deb/kylin/production/PART-10 1-kirin990/custom/partner/10.1-kirin990 default all
```

### 11. V10SP1 - 海思麒麟990（新版）

```deb
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-kv main restricted universe multiverse
deb https://archive2.kylinos.cn/deb/kylin/production/PART-10 1-kirin9a0/custom/partner/10.1-kirin9a0 default all
```

### 12. V10SP1-2203 - 海思麒麟990

```deb
deb https://archive.kylinos.cn/kylin/KYLIN-ALL/ 10.1-wayland-2203-updates main universe restricted multiverse
deb https://archive.kylinos.cn/kylin/KYLIN-ALL/ 10.1-kirin990-feature main
deb https://archive2.kylinos.cn/deb/kylin/production/PART-10 1-kirin9a0/custom/partner/10.1-kirin9a0 default all
```

### 13. V10SP1-2203 - 海思麒麟9006C

```deb
deb https://archive.kylinos.cn/kylin/KYLIN-ALL/ 10.1-wayland-2203-updates main universe restricted multiverse
deb https://archive.kylinos.cn/kylin/KYLIN-ALL/ 10.1-kirin9006c-feature main
deb https://archive2.kylinos.cn/deb/kylin/production/PART-10 1-kirin9a0/custom/partner/10.1-kirin9a0 default all
```

### 14. V10SP1-2303 - 海思麒麟990

```deb
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1 main restricted universe multiverse
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-wayland-2303-updates main restricted universe multiverse
deb http://archive.kylinos.cn/kylin/KYLIN-ALL/ 10.1-kirin990-2303-feature main
deb http://archive2.kylinos.cn/deb/kylin/production/PART-10 1-kirin9a0/custom/partner/10.1-kirin9a0 default all
```

### 15. V10SP1-2303 - 海思麒麟9006C

```deb
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1 main restricted universe multiverse
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-wayland-2303-updates main universe restricted multiverse
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-kirin9006c-2303-feature main
deb https://archive2.kylinos.cn/deb/kylin/production/PART-10 1-kirin9a0/custom/partner/10.1-kirin9a0 default all
```

### 16. V10SP1-2303-update2 - 海思麒麟9006C

```deb
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1 main restricted universe multiverse
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-wayland-2303-updates main universe restricted multiverse
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-kirin9006c-2303-feature main
deb https://archive2.kylinos.cn/deb/kylin/production/PART-10 1-kirin9a0/custom/partner/10.1-kirin9a0 default all
```

### 17. V10SP1-2303-update2 - 海思麒麟990

```deb
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1 main restricted universe multiverse
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-wayland-2303-updates main universe restricted multiverse
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-kirin990-2303-feature main
deb https://archive2.kylinos.cn/deb/kylin/production/PART-10 1-kirin9a0/custom/partner/10.1-kirin9a0 default all
```

### 18. V10SP1-2403 - 海思麒麟9000C

> 对应镜像：Kylin-Desktop-V10-SP1-2403-Wayland-Release-Retail-pangux-b-20251215-ARM64

```deb
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1 main restricted universe multiverse
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-wayland-2403-updates main universe restricted multiverse
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-kirin9000C-2403-feature main
deb https://archive2.kylinos.cn/deb/kylin/production/PART-10 1-kirin9a0/custom/partner/10.1-kirin9a0 default all
```

---

## 六、V10 SP1 - 盘古（Pangwu）专用版本

### 19. V10SP1-2203 - 盘古M900

```deb
deb https://archive.kylinos.cn/kylin/KYLIN-ALL/ 10.1-wayland-2203-pangwu main universe restricted multiverse
deb https://archive2.kylinos.cn/deb/kylin/production/PART-10 1-kirin9a0/custom/partner/10.1-kirin9a0 default all
```

### 20. V10SP1-2303 - 盘古M900

```deb
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1 main restricted universe multiverse
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-wayland-2303-updates main universe restricted multiverse
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-kirinM900-2303-feature main
deb https://archive2.kylinos.cn/deb/kylin/production/PART-10 1-kirin9a0/custom/partner/10.1-kirin9a0 default all
```

---

## 七、V10 SP1 - 2403 系列

### 21. V10SP1-2403（基础版）

```deb
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1 main restricted universe multiverse
deb http://archive2.kylinos.cn/DEB/KYLIN_DEB V10-SP1 main all
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2403-updates main restricted universe multiverse
```

### 22. V10SP1-2403-update1

```deb
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1 main restricted universe multiverse
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2403-update1 main restricted universe multiverse
deb http://archive2.kylinos.cn/deb/kylin/production/PART-V10-SP1/custom/partner/V10-SP1 default all
```

### 23. V10SP1-2403-HWE & update1

```deb
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1 main restricted universe multiverse
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2403-update1 main restricted universe multiverse
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2403-hwe-update1 main
deb http://archive2.kylinos.cn/deb/kylin/production/PART-V10-SP1/custom/partner/V10-SP1 default all
```

### 24. V10SP1-2403-update2

```deb
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1 main restricted universe multiverse
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2403-update2 main restricted universe multiverse
deb http://archive2.kylinos.cn/deb/kylin/production/PART-V10-SP1/custom/partner/V10-SP1 default all
```

---

## 八、V10 SP1 - 2503 系列

### 25. V10SP1-2503-HWE

```deb
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-kylin main restricted universe multiverse
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-kylin-2503 main restricted universe multiverse
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-kylin-2503-hwe main
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2503-bugfix main restricted universe multiverse
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2503-hwe-bugfix main restricted universe multiverse
deb http://archive2.kylinos.cn/deb/kylin/production/PART-V10-SP1/custom/partner/V10-SP1 default all
```

### 26. V10SP1-2503（普通版）

```deb
deb http://archive2.kylinos.cn/deb/kylin/production/PART-V10-SP1/custom/partner/V10-SP1 default all
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-kylin main restricted universe multiverse
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-kylin-2503 main restricted universe multiverse
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2503-bugfix main restricted universe multiverse
```

---

## 附录：术语说明

| 术语 | 说明 |
|------|------|
| **HWE** | Hardware Enablement，硬件启用栈，针对新硬件的内核和图形栈更新 |
| **PP** | 特定硬件平台或项目分支 |
| **Wayland** | 新一代显示服务器协议，替代 X11 |
| **bugfix** | 专门的问题修复更新通道 |
| **feature** | 芯片/平台专属特性分支 |
| **main / restricted / universe / multiverse** | Debian 软件仓库分类：main=官方免费软件，restricted=私有驱动，universe=社区维护，multiverse=版权受限软件 |
| **海思麒麟（kirin）** | 针对华为海思芯片（990、9006C、9000C等）的专用版本 |
| **盘古（pangwu）** | 针对飞腾平台的专用版本分支 |

---

> 整理自银河麒麟官方软件源对照表截图，共 4 张图片，26 个版本配置。
