# 第 11 章《华为ICT大赛·网络赛道备赛实战》建设计划

## 一、Summary 摘要

为现有教程站点（https://user-unknowed.github.io/studying-for-building/，部署于 gh-pages 分支）新增第 11 章，主题为"华为ICT大赛·网络赛道备赛实战"。内容以 B 站视频合集 BV1tseyzCEoF（3 集：网络是怎么传输的/可靠的/安全的）为原理主线，每集下方提炼要点并补充华为 eNSP 模拟器对应实操命令，形成"原理 → 命令 → 赛道考点"完整备赛链路。复用第 09/10 章已验证的响应式骨架与 Pygments 高亮模式，构建脚本 `build_chapter11.py` 仿照 `build_chapter10.py`。最后推送 gh-pages 上线并验证。

## 二、Current State Analysis 现状分析

### 2.1 站点架构（基于 Phase 1 探索）

- **线上服务版本**：`gh-pages` 分支根目录的 `*.html` 与 `assets/`（GitHub Pages 配置：branch=gh-pages, path=/）。
- **工作副本**：`/workspace/site/` 目录是构建输出目标，根目录与 `site/` 需保持同步。
- **章节文件**：`01.html` ~ `10.html` + `index.html`，统一响应式骨架。
- **样式**：`/workspace/assets/style.css`（260 行，含 `.codehilite` Pygments 高亮、`.pager`、`.card`、`.sidebar`、`.topnav`、`.drawer-backdrop` 等全套 class）。
- **部署**：`gh` CLI 已认证（账号 user-unknowed），`gh auth setup-git` 已配置凭据助手，`git push origin gh-pages` 可直推。GitHub Actions 工作流 `.github/workflows/deploy-pages.yml` 存在但当前部署走 gh-pages 分支直推。

### 2.2 章节骨架模板（基于 09.html / 10.html）

每个章节页面统一结构：
```
<head> 响应式 meta + theme-color + assets/style.css
<body>
  <header class="topnav">
    <button class="nav-toggle">☰
    <div class="brand">
    <nav> 01..11 章链接，当前页 class="active"
    <a class="src" href="github 仓库">
  <div class="drawer-backdrop">
  <div class="layout">
    <aside class="sidebar" id="sidebar">
      <div class="sb-head">
      <div class="chapters-m"> 全部章节列表（含当前页 li class="active"）
      <h4>本节目录</h4><ul> 当前章节内部分节锚点
    <main class="content">
      <div class="meta">
      <h1>
      <h2 id="..."> 各分节
      ...
      <div class="pager"> 上一章 / 返回首页（或下一章）
  <script> 抽屉开关脚本（drawer-open / setOpen / ESC 关闭）
```

### 2.3 视频内容（基于 WebFetch）

BV1tseyzCEoF 是 UP 主"飞天闪客"的合集，共 4 项（3 集正文 + 1 个盗版说明）：
| 集 | 标题 | 时长 | 对应网络赛道方向 |
|---|---|---|---|
| P1 | 网络是怎么传输的？ | 12:19 | 数通基础、IP 路由 |
| P2 | 网络是怎么可靠的？ | 08:55 | TCP 可靠传输、OSPF/BFD |
| P3 | 网络是怎么安全的？ | 07:58 | 网络安全、ACL/防火墙 |

视频是网络原理科普动画，非 eNSP 实操录像。按用户决策：**仅放 B 站外链**（保留 vd_source 参数）+ **图文提炼要点** + **补充 eNSP 实操命令**。

### 2.4 09.html 已有网络赛道上下文

09.html L192-227 列出实践赛四条赛道表格，网络赛道 = eNSP 模拟器 + 数通/DCN/安全/WLAN。09 章聚焦云赛道，11 章做网络赛道正好形成姊妹篇。09 章末尾 pager 当前为"上一章 08 + 下一章 10"，10 章末尾 pager 为"上一章 09 + 返回首页"。

### 2.5 index.html 当前状态

- 首页 `.cards` 含 10 张卡片（01~10），最后一张是"第 10 章 · ✂️ 源码编辑与源码导读"。
- `.section-sub` 文案为"10 个递进章节…"。
- `.roadmap ol` 学习路线 7 步（① ~ ⑦）。
- 顶部 nav 与侧边栏 `chapters-m` 均含 01~10 链接。

## 三、Proposed Changes 提议变更

### 3.1 新增 `build_chapter11.py`（构建脚本）

仿照 `build_chapter10.py` 模式，单一脚本完成：生成 11.html + 全站导航更新 + 同步根目录与 site/ 副本。

**关键设计**：
- `SITE = "/workspace/site"`，输出到 `site/11.html`，再 `cp` 到根目录。
- 用 Pygments `HtmlFormatter` + `get_lexer_by_name('text')` 或 `('console')` 高亮 eNSP 命令块（华为 VRP 命令行）。
- 视频链接保留 `https://www.bilibili.com/video/BV1tseyzCEoF?vd_source=997b12c7ded5d6a7454620f3354f3bcb`，每集加 `&p=N` 参数指向具体分 P。
- 章节内嵌的 eNSP 命令字符串同时用于"命令清单"与"实操步骤"，保证一致性。

**导航更新函数**（仿 build_chapter10.py 的 `add_nav_links`）：
```python
NAV_11 = '<a href="11.html" class="">11 网络赛道</a>'
SIDEBAR_11 = '<li><a href="11.html">🌐 第 11 章 · 华为ICT大赛·网络赛道备赛实战</a></li>'

def add_nav_links(path):
    # 顶部 nav：在 10.html 链接后追加 11.html
    # 侧边栏 chapters-m：在 10 章 li 后追加 11 章 li
    # 10.html pager：把"返回首页"改为"下一章 → 11"
```

### 3.2 新增 `site/11.html`（章节页面）

**章节标题**：`11 华为ICT大赛·网络赛道备赛实战 · Java · SQL · Python AI 教程`

**章节目录树**（侧边栏"本节目录"）：
```
0. 导读：网络赛道 vs 云赛道
1. 网络是怎么传输的（视频 P1）
   1.1 视频要点提炼
   1.2 对应网络赛道考点：数通基础
   1.3 eNSP 实操：路由器接口 IP 与静态路由
2. 网络是怎么可靠的（视频 P2）
   2.1 视频要点提炼
   2.2 对应网络赛道考点：可靠性与路由协议
   2.3 eNSP 实操：OSPF 单区域配置
3. 网络是怎么安全的（视频 P3）
   3.1 视频要点提炼
   3.2 对应网络赛道考点：安全
   3.3 eNSP 实操：ACL 访问控制
4. eNSP 模拟器上手指南
   4.1 下载安装与拓扑搭建
   4.2 VRP 命令视图速查
5. 网络赛道赛题类型与备赛策略
6. 上线验证清单
```

**内容写法**（每集视频统一三段式）：
1. **视频区**：`<a href="B站链接&p=N" target="_blank" rel="noopener">📺 B 站观看 P1（12:19）</a>` + 一段简介。
2. **要点提炼**：用 `<ul>` 列出视频核心知识点（如 P1：包交换、IP/MAC/端口、路由跳转、TTL）。
3. **对应考点**：`<blockquote>` 说明该原理在华为 ICT 网络赛道的考察位置（如 P1 对应 HCIA-Datacom 的 IP 路由基础）。
4. **eNSP 实操**：`<div class="codehilite"><pre>` 包裹的 VRP 命令块，带行号与逐行注释。

**eNSP 命令示例**（P1 对应实操）：
```
system-view                     # 进入系统视图
sysname R1                      # 命名路由器
interface GigabitEthernet0/0/0  # 进入接口
ip address 192.168.1.1 24       # 配 IP
quit
ip route-static 10.0.0.0 255.0.0.0 192.168.1.2  # 静态路由
display ip routing-table        # 查路由表
```

**章节末尾 pager**：
```html
<div class="pager">
  <a href="10.html"><div class="dir">← 上一章</div><div class="ttl">源码编辑与源码导读</div></a>
  <a href="index.html" style="text-align:right"><div class="dir">返回首页 →</div><div class="ttl">Java · SQL · Python AI 教程</div></a>
</div>
```

**章节 meta**：`<div class="meta" style="color:#16a34a;font-weight:600">第 11 章 · 🌐</div>`（绿色，与 09 章蓝色云赛道区分）。

### 3.3 更新 `site/index.html`（首页）

1. **顶部 nav** 追加 `<a href="11.html">11 网络赛道</a>`。
2. **侧边栏 chapters-m** 在 10 章 li 后追加 `<li><a href="11.html">🌐 第 11 章 · 华为ICT大赛·网络赛道备赛实战</a></li>`。
3. **章节计数文案** `.section-sub` 由"10 个递进章节…"改为"11 个递进章节，覆盖从语言基础到工业应用、AI 大模型、ICT 竞赛实战与源码工程化的完整阶梯。"（追加"网络赛道"）。
4. **首页卡片** 在 10 章卡片后追加：
```html
<a class="card" href="11.html">
  <div class="num">第 11 章</div>
  <div class="icon">🌐</div>
  <h3>华为ICT大赛·网络赛道备赛实战</h3>
  <div class="sub">网络原理三部曲 · eNSP 模拟器实操 · 数通/安全 · 备赛策略</div>
  <p>用 3 集网络原理科普动画入门，对应到华为 ICT 网络赛道考点，每集配 eNSP 模拟器实操命令：从路由器接口配置到 OSPF、ACL，看完能上手。</p>
  <div class="cta" style="color:#16a34a">开始阅读 →</div>
</a>
```
5. **学习路线** `.roadmap ol` 追加第 ⑧ 步：
```html
<li><b>⑧ ICT 网络赛道</b> → 11 章（网络原理三部曲 + eNSP 实操：路由、OSPF、ACL）</li>
```

### 3.4 更新 `site/01.html` ~ `site/10.html`（全站导航）

每个章节页面：
1. **顶部 nav** 在 `<a href="10.html" class="">10 源码编辑</a>` 后追加 `<a href="11.html" class="">11 网络赛道</a>`。
2. **侧边栏 chapters-m** 在 `<li><a href="10.html">…第 10 章…</a></li>` 后追加 `<li><a href="11.html">🌐 第 11 章 · 华为ICT大赛·网络赛道备赛实战</a></li>`。

### 3.5 更新 `site/10.html`（pager 接入）

10.html 末尾 pager 当前为"上一章 09 + 返回首页"，改为：
```html
<div class="pager">
  <a href="09.html"><div class="dir">← 上一章</div><div class="ttl">华为ICT大赛·云赛道备赛实战</div></a>
  <a href="11.html" style="text-align:right"><div class="dir">下一章 →</div><div class="ttl">华为ICT大赛·网络赛道备赛实战</div></a>
</div>
```

### 3.6 同步根目录

构建脚本生成 `site/11.html` 并更新 `site/` 下各文件后，`cp` 把根目录所有受影响文件与 `site/` 对齐（根目录是线上版本）：
```bash
cp site/11.html site/index.html site/01..10.html site/10.html ./
cp site/assets/style.css assets/style.css  # 若有样式改动
```

### 3.7 部署

```bash
git add 11.html site/11.html site/index.html site/01..10.html site/10.html \
        index.html 01..10.html 10.html build_chapter11.py
git commit -m "feat: 新增第 11 章网络赛道备赛实战，全站导航接入"
git push origin gh-pages
# 等待 GitHub Pages 构建
gh api repos/user-unknowed/studying-for-building/pages/builds/latest --jq '.status'
```

## 四、Assumptions & Decisions 假设与决策

1. **章节编号**：11.html（自然延续 10 章）。✅ 决策完成。
2. **视频呈现**：仅放 B 站外链（每集 `?p=N` 参数）+ 图文要点提炼，不嵌入 iframe。✅ 用户确认。
3. **实操深度**：原理 + eNSP 实操命令（VRP 命令块带行号 + 逐行注释）。✅ 用户确认。
4. **章节主色**：绿色 `#16a34a`（与 09 章蓝色云赛道区分，呼应"网络"赛道视觉）。✅ 决策完成。
5. **章节图标**：🌐（与 09 章云赛道 ☁️ 区分）。✅ 决策完成。
6. **eNSP 命令高亮**：用 Pygments `get_lexer_by_name('text')` + 自定义行号，避免用 console lexer 把华为 VRP 命令误判为 shell。✅ 决策完成。
7. **不创建新 CSS**：复用 `assets/style.css` 现有 class（`.codehilite`、`.pager`、`.card`、`.blockquote`）。若 11 章需要新样式（如视频卡片框），用内联 `<style>` 在 11.html `<head>` 里，避免污染全站样式。✅ 决策完成。
8. **构建脚本模式**：仿 `build_chapter10.py`，单一 `build_chapter11.py` 完成生成 + 导航更新 + 同步，便于复现。✅ 决策完成。
9. **视频链接**：保留原 `vd_source` 参数（用户提供的分销来源参数）。✅ 决策完成。
10. **不修改 09.html 内容**：09 章是云赛道，11 章是网络赛道，互不干扰。仅 09.html 顶部 nav 与侧边栏追加 11 链接。✅ 决策完成。

## 五、Verification 验证步骤

### 5.1 构建期静态验证（本地）

1. `python3 build_chapter11.py` 执行无异常。
2. `python3 -c "..."` 检查 `11.html`：
   - DOCTYPE 与 `</html>` 闭合
   - `nav-toggle`、`drawer-backdrop`、`sb-close`、`drawer-open`、`setOpen`、`ESC 关闭` 齐备
   - `chapters-m` 含"第 11 章 · 华为ICT大赛·网络赛道备赛实战"
   - 三段视频链接均含 `bilibili.com/video/BV1tseyzCEoF`
   - 三处 eNSP 命令块（`codehilite` + `interface`/`ospf`/`acl` 关键命令）
   - pager 含"上一章 10"与"返回首页"
   - 无"网络赛道"以外章节误改
3. 全站导航计数：
   ```bash
   for f in index 01 02 03 04 05 06 07 08 09 10 11; do
     printf "%s:%s " $f $(grep -c 'href="11.html"' $f.html)
   done
   ```
   预期：index=3（nav+sidebar+card），01~10=2（nav+sidebar），10=3（含pager），11=2。

### 5.2 上线后线上验证（curl 四连 + 浏览器）

部署完成后对 `https://user-unknowed.github.io/studying-for-building/`：

```bash
U=https://user-unknowed.github.io/studying-for-building
# ① 11.html 可访问
curl -s -o /dev/null -w "%{http_code}\n" $U/11.html        # 期望 200
# ② 三段视频链接存在
curl -s $U/11.html | grep -c 'bilibili.com/video/BV1tseyzCEoF'  # 期望 ≥3
# ③ 三处 eNSP 命令块
curl -s $U/11.html | grep -c 'class="codehilite"'           # 期望 ≥3
# ④ 全站导航接入
for i in 01 02 03 04 05 06 07 08 09 10; do
  printf "%s:%s " $i $(curl -s $U/$i.html | grep -c 'href="11.html"')
done
# 期望每个 ≥2
```

浏览器验证（用 browser subagent）：
1. 页面加载，标题为"11 华为ICT大赛·网络赛道备赛实战"。
2. 三段视频链接可点击（新窗口打开 B 站）。
3. 三处 eNSP 命令块带行号渲染。
4. 顶部 nav 含"11 网络赛道"。
5. 10.html 底部 pager 有"下一章 → 华为ICT大赛·网络赛道备赛实战"。
6. 首页第 11 章卡片可点击跳转 11.html。
7. 移动端窄窗口汉堡菜单展开抽屉含第 11 章。

### 5.3 验证标准

全部 PASS 后视为上线成功。任一 FAIL 则定位修复（优先修 `build_chapter11.py` 重新生成 + 重推）。

## 六、实施顺序（todo 清单）

1. 写 `build_chapter11.py`（章节内容字符串 + 导航更新函数 + 同步逻辑）
2. 运行 `python3 build_chapter11.py` 生成 `site/11.html` 并更新全站
3. 同步根目录（cp site/* 到根）
4. 本地静态验证（5.1）
5. `git add` + `commit` + `push origin gh-pages`
6. 等 GitHub Pages 构建（`gh api .../pages/builds/latest` status=built）
7. curl 四连线上验证（5.2）
8. 浏览器最终功能验证（5.2 后半）
9. 输出总结报告给用户
