# 银河麒麟（Kylin）桌面操作系统外网软件源清单

> 原始数据来自《银河麒麟桌面外网源.xls》——**在线推送使用的正式源（外网）**，
> 按产线版本组织：XC 通用版、HWE 硬件启用栈、Wayland（麒麟 990 / 9006C / 9000C /
> 盘古 M900 / 华为 Pangux·Flemingx·Panguy·Panguw）。
> 本文档是清单的纯文本副本，`kylinpkg/presets.py` 与本文逐行对应，
> `tests/test_presets.py` 会校验两者一致。

总计 42 条配置 / 208 条 `deb` 源行，其中 11 条附带的
`/etc/apt/preferences.d/kylin.pref` 优先级（Pin-Priority）设置也已收录。

---

## 一、XC 产线（通用版）

### V10 SP1 XC-2107（xc-2107）

```
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1 main restricted universe multiverse
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2107-updates main
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2107-bugfix-limit main restricted universe multiverse
deb http://archive2.kylinos.cn/deb/kylin/production/PART-V10-SP1/custom/partner/V10-SP1 default all
```

### V10 SP1 XC-2203（xc-2203）

```
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1 main restricted universe multiverse
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2203-updates-preview main restricted universe multiverse
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2203-bugfix-limit main restricted universe multiverse
deb http://archive2.kylinos.cn/deb/kylin/production/PART-V10-SP1/custom/partner/V10-SP1 default all
```

### V10 SP1 XC-2303（xc-2303）

```
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1 main restricted universe multiverse
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2303-updates main restricted universe multiverse
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2303-bugfix-limit main restricted universe multiverse
deb http://archive2.kylinos.cn/deb/kylin/production/PART-V10-SP1/custom/partner/V10-SP1 default all
```

### V10 SP1 XC-2303-update2（xc-2303u2）

```
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1 main restricted universe multiverse
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2303-update3 main restricted universe multiverse
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2303-update2-bugfix-limit main restricted universe multiverse
deb http://archive2.kylinos.cn/deb/kylin/production/PART-V10-SP1/custom/partner/V10-SP1 default all
```

### V10 SP1 XC-2403-update2（xc-2403u2）

```
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1 main restricted universe multiverse
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2403-update2 main restricted universe multiverse
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2403-bugfix-limit main restricted universe multiverse
deb http://archive2.kylinos.cn/deb/kylin/production/PART-V10-SP1/custom/partner/V10-SP1 default all
```

### V10 SP1 XC-2503（xc-2503）

```
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-kylin main restricted universe multiverse
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2503-bugfix-limit main restricted universe multiverse
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-kylin-2503 main restricted universe multiverse
deb http://archive2.kylinos.cn/deb/kylin/production/PART-V10-SP1/custom/partner/V10-SP1 default all
```

优先级设置【/etc/apt/preferences.d/kylin.pref】：

```
Package: *
Pin: origin "archive.kylinos.cn"
Pin: release a=10.1-kylin
Pin-Priority: 500

Package: *
Pin: origin "archive.kylinos.cn"
Pin: release a=10.1-kylin-2503
Pin-Priority: 600

Package: *
Pin: origin "archive.kylinos.cn"
Pin: release a=10.1-2503-bugfix-limit
Pin-Priority: 600

Package: *
Pin: origin "archive2.kylinos.cn"
Pin-Priority: 600
```

## 二、HWE 硬件启用栈

### V10 SP1 HWE-2107（hwe-2107）

```
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1 main restricted universe multiverse
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-hwe main
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2107-hwe-updates main
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2107-hwe-bugfix-limit main restricted universe multiverse
deb http://archive2.kylinos.cn/deb/kylin/production/PART-V10-SP1/custom/partner/V10-SP1 default all
```

### V10 SP1 HWE-2203（hwe-2203）

```
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1 main restricted universe multiverse
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2203-hwe-updates-preview main restricted universe multiverse
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2203-hwe-bugfix-limit main restricted universe multiverse
deb http://archive2.kylinos.cn/deb/kylin/production/PART-V10-SP1/custom/partner/V10-SP1 default all
```

### V10 SP1 HWE-2303（hwe-2303）

```
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1 main restricted universe multiverse
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2303-updates main restricted universe multiverse
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2303-bugfix-limit main restricted universe multiverse
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2303-hwe-updates main universe multiverse restricted
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2303-hwe-bugfix-limit main restricted universe multiverse
deb http://archive2.kylinos.cn/deb/kylin/production/PART-V10-SP1/custom/partner/V10-SP1 default all
```

### V10 SP1 HWE-2303-update2（hwe-2303u2）

```
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1 main restricted universe multiverse
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2303-update3 main restricted universe multiverse
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2303-update2-bugfix-limit main restricted universe multiverse
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2303-hwe-update3 main
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2303-hwe-update2-bugfix-limit main restricted universe multiverse
deb http://archive2.kylinos.cn/deb/kylin/production/PART-V10-SP1/custom/partner/V10-SP1 default all
```

### V10 SP1 HWE-2403-update2（hwe-2403u2）

```
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1 main restricted universe multiverse
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2403-update2 main restricted universe multiverse
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2403-bugfix-limit main restricted universe multiverse
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2403-hwe-update2 main universe multiverse restricted
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2403-hwe-bugfix-limit main
deb http://archive2.kylinos.cn/deb/kylin/production/PART-V10-SP1/custom/partner/V10-SP1 default all
```

### V10 SP1 HWE-2503（hwe-2503）

```
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-kylin main restricted universe multiverse
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2503-bugfix-limit main restricted universe multiverse
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-kylin-2503 main restricted universe multiverse
deb http://archive2.kylinos.cn/deb/kylin/production/PART-V10-SP1/custom/partner/V10-SP1 default all
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2503-hwe-bugfix-limit main restricted universe multiverse
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-kylin-2503-hwe main
```

优先级设置【/etc/apt/preferences.d/kylin.pref】：

```
Package: *
Pin: origin "archive.kylinos.cn"
Pin: release a=10.1-kylin
Pin-Priority: 500

Package: *
Pin: origin "archive.kylinos.cn"
Pin: release a=10.1-kylin-2503
Pin-Priority: 600

Package: *
Pin: origin "archive.kylinos.cn"
Pin: release a=10.1-2503-bugfix-limit
Pin-Priority: 600

Package: *
Pin: origin "archive.kylinos.cn"
Pin: release a=10.1-kylin-2503-hwe
Pin-Priority: 700

Package: *
Pin: origin "archive.kylinos.cn"
Pin: release a=10.1-2503-hwe-bugfix-limit
Pin-Priority: 700

Package: *
Pin: origin "archive2.kylinos.cn"
Pin-Priority: 600
```

### V10 SP1 HWE-PP-2303（hwe-pp-2303）

```
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1 main restricted universe multiverse
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2303-updates main restricted universe multiverse
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2303-bugfix-limit main restricted universe multiverse
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2303-hwe-pp-updates main
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2303-hwe-pp-bugfix-limit main restricted universe multiverse
deb http://archive2.kylinos.cn/deb/kylin/production/PART-V10-SP1/custom/partner/V10-SP1 default all
```

### V10 SP1 HWE-PP-2303-update2（hwe-pp-2303u2）

```
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1 main restricted universe multiverse
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2303-update3 main restricted universe multiverse
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2303-update2-bugfix-limit main restricted universe multiverse
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2303-hwe-pp-update3 main
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2303-hwe-pp-update2-bugfix-limit main restricted universe multiverse
deb http://archive2.kylinos.cn/deb/kylin/production/PART-V10-SP1/custom/partner/V10-SP1 default all
```

### V10 SP1 HWE-PP-2403-update2（hwe-pp-2403u2）

```
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1 main restricted universe multiverse
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2403-update2 main restricted universe multiverse
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2403-bugfix-limit main restricted universe multiverse
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2403-hwe-pp-update2 main
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2403-hwe-pp-bugfix-limit main
deb http://archive2.kylinos.cn/deb/kylin/production/PART-V10-SP1/custom/partner/V10-SP1 default all
```

### V10 SP1 HWE-PP-2503（hwe-pp-2503）

```
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-kylin main restricted universe multiverse
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2503-bugfix-limit main restricted universe multiverse
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-kylin-2503 main restricted universe multiverse
deb http://archive2.kylinos.cn/deb/kylin/production/PART-V10-SP1/custom/partner/V10-SP1 default all
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2503-hwe-pp-bugfix-limit main restricted universe multiverse
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-kylin-2503-hwe-pp main
```

优先级设置【/etc/apt/preferences.d/kylin.pref】：

```
Package: *
Pin: origin "archive.kylinos.cn"
Pin: release a=10.1-kylin
Pin-Priority: 500

Package: *
Pin: origin "archive.kylinos.cn"
Pin: release a=10.1-kylin-2503
Pin-Priority: 600

Package: *
Pin: origin "archive.kylinos.cn"
Pin: release a=10.1-2503-bugfix-limit
Pin-Priority: 600

Package: *
Pin: origin "archive.kylinos.cn"
Pin: release a=10.1-kylin-2503-hwe-pp
Pin-Priority: 700

Package: *
Pin: origin "archive.kylinos.cn"
Pin: release a=10.1-2503-hwe-pp-bugfix-limit
Pin-Priority: 700

Package: *
Pin: origin "archive2.kylinos.cn"
Pin-Priority: 600
```

## 三、Wayland · 麒麟 990

### Wayland 2107 · 麒麟 990（wl-2107-990）

```
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-pv main restricted universe multiverse
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2107-wayland-kirin990-bugfix-limit main restricted universe multiverse
deb http://archive2.kylinos.cn/deb/kylin/production/PART-10_1-kirin990/custom/partner/10_1-kirin990 default all
```

### Wayland 2203 · 麒麟 990（wl-2203-990）

```
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-wayland-2203-updates main universe restricted multiverse
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-kirin990-feature main
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2203-wayland-bugfix-limit main restricted universe multiverse
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2203-wayland-kirin990-bugfix-limit main
deb https://archive2.kylinos.cn/deb/kylin/production/PART-10_1-kirin9a0/custom/partner/10_1-kirin9a0 default all
```

### Wayland 2303 · 麒麟 990（wl-2303-990）

```
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1 main restricted universe multiverse
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-wayland-2303-updates main universe restricted multiverse
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-kirin990-2303-feature main
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2303-wayland-bugfix-limit main restricted universe multiverse
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2303-wayland-kirin990-bugfix-limit main
deb https://archive2.kylinos.cn/deb/kylin/production/PART-10_1-kirin9a0/custom/partner/10_1-kirin9a0 default all
```

### Wayland 2303-update2 · 麒麟 990（wl-2303u2-990）

```
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1 main restricted universe multiverse
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2303-wayland-update3 main restricted universe multiverse
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2303-wayland-update3-kirin990 main
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2303-wayland-update2-bugfix-limit main restricted universe multiverse
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2303-wayland-update2-kirin990-bugfix-limit main
deb https://archive2.kylinos.cn/deb/kylin/production/PART-10_1-kirin9a0/custom/partner/10_1-kirin9a0 default all
```

### Wayland 2403-update2 · 麒麟 990（wl-2403u2-990）

```
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1 main restricted universe multiverse
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2403-wayland-update2 main universe restricted multiverse
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2403-wayland-update2-kirin990 main
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2403-wayland-bugfix-limit main restricted universe multiverse
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2403-wayland-kirin990-bugfix-limit main
deb https://archive2.kylinos.cn/deb/kylin/production/PART-10_1-kirin9a0/custom/partner/10_1-kirin9a0 default all
```

### Wayland 2503 · 麒麟 990（wl-2503-990）

```
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-kylin main restricted universe multiverse
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-kylin-2503-wayland main universe restricted multiverse
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2503-wayland-bugfix-limit main universe restricted multiverse
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-kylin-2503-wayland-kirin990 main
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-kylin-2503-wayland-kirin990-bugfix main universe restricted multiverse
deb http://archive2.kylinos.cn/deb/kylin/production/PART-10_1-kirin9a0/custom/partner/10_1-kirin9a0 default all
```

优先级设置【/etc/apt/preferences.d/kylin.pref】：

```
Package: *
Pin: origin "archive.kylinos.cn"
Pin: release a=10.1-kylin
Pin-Priority: 500

Package: *
Pin: origin "archive.kylinos.cn"
Pin: release a=10.1-kylin-2503-wayland
Pin-Priority: 600

Package: *
Pin: origin "archive.kylinos.cn"
Pin: release a=10.1-2503-wayland-bugfix-limit
Pin-Priority: 600

Package: *
Pin: origin "archive.kylinos.cn"
Pin: release a=10.1-kylin-2503-wayland-kirin990
Pin-Priority: 700

Package: *
Pin: origin "archive.kylinos.cn"
Pin: release a=10.1-kylin-2503-wayland-kirin990-bugfix
Pin-Priority: 700

Package: *
Pin: origin "archive2.kylinos.cn"
Pin-Priority: 600
```

## 四、Wayland · 麒麟 9006C

### Wayland 2107 · 麒麟 9006C（wl-2107-9006c）

```
deb https://archive2.kylinos.cn/deb/kylin/production/PART-10_1-kirin9a0/custom/partner/10_1-kirin9a0 default all
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2107-wayland-kirin9006c-bugfix-limit main restricted universe multiverse
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-kv main restricted universe multiverse
```

### Wayland 2203 · 麒麟 9006C（wl-2203-9006c）

```
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2203-wayland-bugfix-limit main restricted universe multiverse
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2203-wayland-kirin9006c-bugfix-limit main
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-kirin9006C-feature main
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-wayland-2203-updates main universe restricted multiverse
deb https://archive2.kylinos.cn/deb/kylin/production/PART-10_1-kirin9a0/custom/partner/10_1-kirin9a0 default all
```

### Wayland 2303 · 麒麟 9006C（wl-2303-9006c）

```
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1 main restricted universe multiverse
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-wayland-2303-updates main universe restricted multiverse
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-kirin9006C-2303-feature main
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2303-wayland-bugfix-limit main restricted universe multiverse
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2303-wayland-kirin9006c-bugfix-limit main
deb https://archive2.kylinos.cn/deb/kylin/production/PART-10_1-kirin9a0/custom/partner/10_1-kirin9a0 default all
```

### Wayland 2303-update2 · 麒麟 9006C（wl-2303u2-9006c）

```
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1 main restricted universe multiverse
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2303-wayland-update3 main restricted universe multiverse
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2303-wayland-update3-kirin9006C main
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2303-wayland-update2-bugfix-limit main restricted universe multiverse
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2303-wayland-update2-kirin9006c-bugfix-limit main
deb https://archive2.kylinos.cn/deb/kylin/production/PART-10_1-kirin9a0/custom/partner/10_1-kirin9a0 default all
```

### Wayland 2403-update2 · 麒麟 9006C（wl-2403u2-9006c）

```
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1 main restricted universe multiverse
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2403-wayland-update2 main universe restricted multiverse
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2403-wayland-update2-kirin9006C main
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2403-wayland-bugfix-limit main restricted universe multiverse
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2403-wayland-kirin9006c-bugfix-limit main
deb https://archive2.kylinos.cn/deb/kylin/production/PART-10_1-kirin9a0/custom/partner/10_1-kirin9a0 default all
```

### Wayland 2503 · 麒麟 9006C（wl-2503-9006c）

```
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-kylin main restricted universe multiverse
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-kylin-2503-wayland main universe restricted multiverse
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2503-wayland-bugfix-limit main universe restricted multiverse
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-kylin-2503-wayland-kirin9006C main
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-kylin-2503-wayland-kirin9006C-bugfix main universe restricted multiverse
deb http://archive2.kylinos.cn/deb/kylin/production/PART-10_1-kirin9a0/custom/partner/10_1-kirin9a0 default all
```

优先级设置【/etc/apt/preferences.d/kylin.pref】：

```
Package: *
Pin: origin "archive.kylinos.cn"
Pin: release a=10.1-kylin
Pin-Priority: 500

Package: *
Pin: origin "archive.kylinos.cn"
Pin: release a=10.1-kylin-2503-wayland
Pin-Priority: 600

Package: *
Pin: origin "archive.kylinos.cn"
Pin: release a=10.1-2503-wayland-bugfix-limit
Pin-Priority: 600

Package: *
Pin: origin "archive.kylinos.cn"
Pin: release a=10.1-kylin-2503-wayland-kirin9006C
Pin-Priority: 700

Package: *
Pin: origin "archive.kylinos.cn"
Pin: release a=10.1-kylin-2503-wayland-kirin9006C-bugfix
Pin-Priority: 700

Package: *
Pin: origin "archive2.kylinos.cn"
Pin-Priority: 600
```

## 五、Wayland · 盘古 M900（Pangwu）

### Wayland 2303-update2 · 盘古 M900（wl-2303u2-m900）

```
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1 main restricted universe multiverse
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2303-wayland-update3 main restricted universe multiverse
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2303-wayland-update3-m900 main
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2303-wayland-update2-bugfix-limit main restricted universe multiverse
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2303-wayland-update2-kirinM900-bugfix-limit main
deb http://archive2.kylinos.cn/deb/kylin/production/PART-10_1-kirin9a0/custom/partner/10_1-kirin9a0 default all
```

### Wayland 2403-update2 · 盘古 M900（wl-2403u2-m900）

```
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1 main restricted universe multiverse
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2403-wayland-update2 main universe restricted multiverse
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2403-wayland-update2-kirinM900 main
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2403-wayland-bugfix-limit main restricted universe multiverse
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2403-wayland-kirinM900-bugfix-limit main
deb https://archive2.kylinos.cn/deb/kylin/production/PART-10_1-kirin9a0/custom/partner/10_1-kirin9a0 default all
```

### Wayland 2503 · 盘古 M900（wl-2503-m900）

```
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-kylin main restricted universe multiverse
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-kylin-2503-wayland main universe restricted multiverse
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2503-wayland-bugfix-limit main universe restricted multiverse
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-kylin-2503-wayland-kirinM900 main
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-kylin-2503-wayland-kirinM900-bugfix main universe restricted multiverse
deb http://archive2.kylinos.cn/deb/kylin/production/PART-10_1-kirin9a0/custom/partner/10_1-kirin9a0 default all
```

优先级设置【/etc/apt/preferences.d/kylin.pref】：

```
Package: *
Pin: origin "archive.kylinos.cn"
Pin: release a=10.1-kylin
Pin-Priority: 500

Package: *
Pin: origin "archive.kylinos.cn"
Pin: release a=10.1-kylin-2503-wayland
Pin-Priority: 600

Package: *
Pin: origin "archive.kylinos.cn"
Pin: release a=10.1-2503-wayland-bugfix-limit
Pin-Priority: 600

Package: *
Pin: origin "archive.kylinos.cn"
Pin: release a=10.1-kylin-2503-wayland-kirinM900
Pin-Priority: 700

Package: *
Pin: origin "archive.kylinos.cn"
Pin: release a=10.1-kylin-2503-wayland-kirinM900-bugfix
Pin-Priority: 700

Package: *
Pin: origin "archive2.kylinos.cn"
Pin-Priority: 600
```

## 六、Wayland · 麒麟 9000C

### Wayland 2403 · 麒麟 9000C（wl-2403-9000c）

```
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1 main restricted universe multiverse
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-wayland-2403-updates main universe restricted multiverse
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-kirin9000C-2403-feature main
deb https://archive2.kylinos.cn/deb/kylin/production/PART-10_1-kirin9a0/custom/partner/10_1-kirin9a0 default all
```

### Wayland 2403-update1 · 麒麟 9000C（wl-2403u1-9000c）

```
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1 main restricted universe multiverse
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2403-wayland-update1 main universe restricted multiverse
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2403-wayland-update1-kirin9000C main
deb https://archive2.kylinos.cn/deb/kylin/production/PART-10_1-kirin9a0/custom/partner/10_1-kirin9a0 default all
```

### Wayland 2403-update2 · 麒麟 9000C（wl-2403u2-9000c）

```
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1 main restricted universe multiverse
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2403-wayland-update2 main universe restricted multiverse
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2403-wayland-update2-kirin9000C main
deb https://archive2.kylinos.cn/deb/kylin/production/PART-10_1-kirin9a0/custom/partner/10_1-kirin9a0 default all
```

### Wayland 2503 · 麒麟 9000C（wl-2503-9000c）

```
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-kylin main restricted universe multiverse
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-kylin-2503-wayland main universe restricted multiverse
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2503-wayland-bugfix-limit main universe restricted multiverse
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-kylin-2503-wayland-kirin9000C main
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-kylin-2503-wayland-kirin9000C-bugfix main universe restricted multiverse
deb http://archive2.kylinos.cn/deb/kylin/production/PART-10_1-kirin9a0/custom/partner/10_1-kirin9a0 default all
```

优先级设置【/etc/apt/preferences.d/kylin.pref】：

```
Package: *
Pin: origin "archive.kylinos.cn"
Pin: release a=10.1-kylin
Pin-Priority: 500

Package: *
Pin: origin "archive.kylinos.cn"
Pin: release a=10.1-kylin-2503-wayland
Pin-Priority: 600

Package: *
Pin: origin "archive.kylinos.cn"
Pin: release a=10.1-2503-wayland-bugfix-limit
Pin-Priority: 600

Package: *
Pin: origin "archive.kylinos.cn"
Pin: release a=10.1-kylin-2503-wayland-kirin9000C
Pin-Priority: 700

Package: *
Pin: origin "archive.kylinos.cn"
Pin: release a=10.1-kylin-2503-wayland-kirin9000C-bugfix
Pin-Priority: 700

Package: *
Pin: origin "archive2.kylinos.cn"
Pin-Priority: 600
```

### Wayland 2403 · 华为 Pangux-a（wl-pangux-a-2403）

```
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-kirin9000C-2403-feature-bugfix-limit main universe restricted multiverse
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-kirin9000C-2403-feature main
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-wayland-2403-updates main universe restricted multiverse
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1 main restricted universe multiverse
deb http://archive2.kylinos.cn/deb/kylin/production/PART-10_1-kirin9a0/custom/partner/10_1-kirin9a0 default all
```

优先级设置【/etc/apt/preferences.d/kylin.pref】：

```
Package: *
Pin: origin "archive.kylinos.cn"
Pin: release a=10.1-kylin
Pin-Priority: 500

Package: *
Pin: origin "archive.kylinos.cn"
Pin: release a=10.1-wayland-2403-updates
Pin-Priority: 500

Package: *
Pin: origin "archive.kylinos.cn"
Pin: release a=10.1-kirin9000C-2403-feature-bugfix-limit
Pin-Priority: 600

Package: *
Pin: origin "archive.kylinos.cn"
Pin: release a=10.1-kirin9000C-2403-feature
Pin-Priority: 600

Package: *
Pin: origin "archive2.kylinos.cn"
Pin-Priority: 500
```

### Wayland · 华为 Pangux-b（wl-pangux-b）

```
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-kirin9000C-2403-feature-bugfix-limit main universe restricted multiverse
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-kirin9000C-b-2403-feature main
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-wayland-2403-updates main universe restricted multiverse
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1 main restricted universe multiverse
deb http://archive2.kylinos.cn/deb/kylin/production/PART-10_1-kirin9a0/custom/partner/10_1-kirin9a0 default all
```

优先级设置【/etc/apt/preferences.d/kylin.pref】：

```
Package: *
Pin: origin "archive.kylinos.cn"
Pin: release a=10.1-kylin
Pin-Priority: 500

Package: *
Pin: origin "archive.kylinos.cn"
Pin: release a=10.1-wayland-2403-updates
Pin-Priority: 500

Package: *
Pin: origin "archive.kylinos.cn"
Pin: release a=10.1-kirin9000C-2403-feature-bugfix-limit
Pin-Priority: 600

Package: *
Pin: origin "archive.kylinos.cn"
Pin: release a=10.1-kirin9000C-b-2403-feature
Pin-Priority: 600

Package: *
Pin: origin "archive2.kylinos.cn"
Pin-Priority: 500
```

## 七、Wayland · 华为其他平台

### Wayland · 华为 Flemingx（wl-flemingx）

```
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2403-wayland-update2-kirin9000C-pre-bugfix-limit main universe restricted multiverse
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1 main restricted universe multiverse
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2403-wayland-update2 main universe restricted multiverse
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2403-wayland-update2-kirin9000C-pre main
deb https://archive2.kylinos.cn/deb/kylin/production/PART-10_1-kirin9a0/custom/partner/10_1-kirin9a0 default all
```

优先级设置【/etc/apt/preferences.d/kylin.pref】：

```
Package: *
Pin: origin "archive.kylinos.cn"
Pin: release a=10.1-kylin
Pin-Priority: 500

Package: *
Pin: origin "archive.kylinos.cn"
Pin: release a=10.1-2403-wayland-update2
Pin-Priority: 500

Package: *
Pin: origin "archive.kylinos.cn"
Pin: release a=10.1-2403-wayland-update2-kirin9000C-pre
Pin-Priority: 600

Package: *
Pin: origin "archive.kylinos.cn"
Pin: release a=10.1-2403-wayland-update2-kirin9000C-pre-bugfix-limit
Pin-Priority: 600

Package: *
Pin: origin "archive2.kylinos.cn"
Pin-Priority: 500
```

### Wayland · 华为 Panguy（麒麟 9000X）（wl-panguy）

```
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2403-wayland-update2-kirin9000X-bugfix-limit main universe restricted multiverse
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1 main restricted universe multiverse
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2403-wayland-update2 main universe restricted multiverse
deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2403-wayland-update2-kirin9000X main
deb https://archive2.kylinos.cn/deb/kylin/production/PART-10_1-kirin9a0/custom/partner/10_1-kirin9a0 default all
```

优先级设置【/etc/apt/preferences.d/kylin.pref】：

```
Package: *
Pin: origin "archive.kylinos.cn"
Pin: release a=10.1-kylin
Pin-Priority: 500

Package: *
Pin: origin "archive.kylinos.cn"
Pin: release a=10.1-2403-wayland-update2
Pin-Priority: 500

Package: *
Pin: origin "archive.kylinos.cn"
Pin: release a=10.1-2403-wayland-update2-kirin9000X
Pin-Priority: 600

Package: *
Pin: origin "archive.kylinos.cn"
Pin: release a=10.1-2403-wayland-update2-kirin9000X-bugfix-limit
Pin-Priority: 600

Package: *
Pin: origin "archive2.kylinos.cn"
Pin-Priority: 500
```

### Wayland 2107 · 华为 Panguw（wl-2107-panguw）

```
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-pw main restricted universe multiverse
```

## 八、V10 基础版（非 SP1，历史）

### V10-2107 / 2101 / 0710 等（旧版，非 SP1）（v10-2107）

```
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.0 main restricted universe multiverse
deb http://archive.kylinos.cn/kylin/partner juniper main
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.0-fixs main
```

### V10-2203（X86_64 / ARM64 / MIPS64el，旧版，非 SP1）（v10-2203）

```
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.0 main restricted universe multiverse
deb http://archive.kylinos.cn/kylin/partner juniper main
deb http://archive2.kylinos.cn/deb/kylin/production/PART-V10/custom/partner/V10 default all
```

---

## 附录：术语说明

| 术语 | 说明 |
|------|------|
| **XC** | 产线通用版分支，对应 X86 / ARM / MIPS / LoongArch 等通用桌面版本 |
| **HWE** | Hardware Enablement，硬件启用栈，针对新硬件的内核和图形栈更新 |
| **PP** | 特定硬件平台或项目分支 |
| **Wayland** | 新一代显示服务器协议，替代 X11 |
| **updates / updateN** | 版本叠加更新层，数字越大越新 |
| **bugfix-limit** | 限定范围的问题修复通道，替代早期的 bugfix 命名 |
| **feature** | 芯片/平台专属特性分支（kirin990 / kirin9006C / kirin9000C / kirinM900 等） |
| **preview** | 预览更新通道，稳定性低于正式 updates |
| **main / restricted / universe / multiverse** | Debian 软件仓库分类：main=官方免费软件，restricted=私有驱动，universe=社区维护，multiverse=版权受限软件 |
| **海思麒麟（kirin）** | 华为海思芯片（990、9006C、9000C 等）的专用版本 |
| **盘古（pangwu / M900）** | 华为海思的另一款芯片产品线，ARM64 架构，有专用版本分支 |
| **Pangux / Flemingx / Panguy / Panguw** | 华为整机平台代号，各有专属 wayland 分支 |

