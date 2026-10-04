#!/usr/bin/env python3
"""
构建 Java & SQL 学习教程网站。
读取 /workspace/docs-src/*.md，输出到 /workspace/site/
"""
import os, re, html
import markdown
from markdown.extensions.toc import TocExtension
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name, guess_lexer, guess_lexer_for_filename
from pygments.util import ClassNotFound

SRC = "/workspace/docs-src"
OUT = "/workspace/site"
os.makedirs(f"{OUT}/assets", exist_ok=True)

# ── 模块元数据（与仓库 01~07 对应，顺序即学习顺序） ──
MODULES = [
    {"num": "01", "file": "01-JavaSE基础知识点-完整梳理.md",
     "title": "JavaSE 基础知识点",
     "subtitle": "运行机制 · 语法 · OOP · 集合 · 并发 · IO · 现代语法",
     "accent": "#2563eb", "icon": "☕",
     "desc": "Java 语言地基，从 JVM 运行机制到现代语法全家桶，每个知识点从'为什么'讲起。"},
    {"num": "02", "file": "02-Java与SQL数据库-深度融合教学.md",
     "title": "Java 与 SQL 数据库深度融合",
     "subtitle": "JDBC · SQL 注入攻防 · 事务转账 · 批处理性能",
     "accent": "#0ea5e9", "icon": "🔗",
     "desc": "Java 与数据库如何分工协作，契约是 SQL + 事务。含真实运行的注入攻击与 600 倍性能实测。"},
    {"num": "03", "file": "03-SQL数据库深度讲解-工业实践版.md",
     "title": "SQL 数据库深度讲解（工业实践版）",
     "subtitle": "关系模型 · 窗口函数 · 索引 · 事务并发 · 架构前沿",
     "accent": "#16a34a", "icon": "🗄️",
     "desc": "工业级 SQL 能力三件套：写得出、跑得快、不出事。含窗口函数模板、EXPLAIN、MVCC。"},
    {"num": "04", "file": "04-学习报告-Java-数据库-AI-Agent.md",
     "title": "学习报告：Java · 数据库 · AI Agent",
     "subtitle": "三大方向知识地图 · 2025-2026 动态 · 12 周计划",
     "accent": "#9333ea", "icon": "🧭",
     "desc": "Java / 数据库 / AI Agent 三大方向的知识地图、最新动态与可执行的 12 周学习计划。"},
    {"num": "05", "file": "05-JavaEE企业级开发-现代实战教程.md",
     "title": "JavaEE 企业级开发（现代实战）",
     "subtitle": "Servlet · DAO · 事务 · REST · 防超卖 · Spring Boot",
     "accent": "#ea580c", "icon": "🏢",
     "desc": "从原生 Jakarta EE 到 Spring Boot，含防超卖并发压测、幂等、与原生版逐行对照。"},
    {"num": "06", "file": "06-Java上位机开发实战-串口Modbus数据采集与监控.md",
     "title": "Java 上位机开发实战",
     "subtitle": "串口 · Modbus · 数据采集 · 入库 · 控制与报警",
     "accent": "#dc2626", "icon": "🛠️",
     "desc": "手写 Modbus TCP/RTU 帧、CRC16、串口抽象、数据入库、控制闭环、报警上升沿。"},
    {"num": "07", "file": "07-JavaEE上位机实战-网页监控看板与远程控制.md",
     "title": "JavaEE 上位机：网页监控看板",
     "subtitle": "Servlet · 嵌入式 Tomcat · REST · 零依赖 SVG 看板",
     "accent": "#0891b2", "icon": "🌐",
     "desc": "网页版上位机：Poller 采集与断线自愈、4 个 REST 端点、SVG 看板、控制下发闭环。"},
    {"num": "08", "file": "08-Python与AI大模型-从原理到Transformer实战.md",
     "title": "Python 与 AI 大模型：从原理到 Transformer",
     "subtitle": "张量 · Autograd · 注意力 · GPU 并行 · 推理服务化",
     "accent": "#7c3aed", "icon": "🐍",
     "desc": "搞懂 Python 如何让 Transformer 跑起来：从张量与自动求导，到手写 MiniGPT 训练生成，再到 GPU 并行与 vLLM 服务化。"},
    {"num": "09", "file": "09-华为ICT大赛云赛道-备赛实战教程.md",
     "title": "华为ICT大赛·云赛道备赛实战",
     "subtitle": "赛制赛程 · 华为云核心服务 · ECS/VPC/OBS/RDS/CCE · 控制台实操 · 备赛策略",
     "accent": "#0284c7", "icon": "☁️",
     "navtitle": "华为ICT大赛·云赛道",
     "desc": "华为ICT大赛实践赛云赛道全攻略：从云计算通俗原理，到 ECS、VPC、OBS、RDS、CCE 等核心服务控制台实操，再到 8 小时综合实验的备赛策略与分阶段计划。"},
]

# ── Pygments 生成的 CSS（浅色主题） ──
formatter = HtmlFormatter(style="friendly", linenos=False, cssclass="codehilite")
pygments_css = formatter.get_style_defs(".codehilite")

# ── 共享 CSS ──
CSS = """
:root{
  --bg:#ffffff; --fg:#1f2328; --muted:#57606a; --accent:#2563eb; --accent-soft:#eff6ff;
  --border:#e4e7eb; --code-bg:#f6f8fa; --sidebar-bg:#fafbfc;
}
*{box-sizing:border-box}
html{scroll-behavior:smooth;-webkit-text-size-adjust:100%;text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--fg);
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Hiragino Sans GB","Microsoft YaHei",Roboto,"Noto Sans SC",Helvetica,Arial,sans-serif;
  line-height:1.75;font-size:16px;-webkit-font-smoothing:antialiased}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
img{max-width:100%;height:auto}

/* ── 顶部导航 ── */
.topnav{position:sticky;top:0;z-index:50;background:rgba(255,255,255,.92);
  -webkit-backdrop-filter:blur(8px);backdrop-filter:blur(8px);border-bottom:1px solid var(--border);
  display:flex;align-items:center;padding:10px 24px;gap:20px}
.topnav .brand{font-weight:800;font-size:17px;color:#0b2a6b;white-space:nowrap;min-width:0}
.topnav .brand small{color:var(--muted);font-weight:400;font-size:12px;margin-left:6px}
.topnav nav{display:flex;gap:6px;flex-wrap:wrap;flex:1;overflow-x:auto}
.topnav nav a{font-size:13px;padding:5px 10px;border-radius:6px;color:#334155;white-space:nowrap}
.topnav nav a:hover{background:var(--accent-soft);color:var(--accent);text-decoration:none}
.topnav nav a.active{background:var(--accent);color:#fff}
.topnav .src{font-size:12px;color:var(--muted);white-space:nowrap}
.nav-toggle{display:none;flex:0 0 auto;width:38px;height:38px;border:1px solid var(--border);
  border-radius:8px;background:#fff;color:#0b2a6b;font-size:17px;line-height:1;cursor:pointer;
  align-items:center;justify-content:center}
.nav-toggle:active{background:var(--accent-soft)}

/* ── 布局 ── */
.layout{display:grid;grid-template-columns:260px 1fr;max-width:1280px;margin:0 auto}
.sidebar{position:sticky;top:56px;height:calc(100vh - 56px);overflow-y:auto;
  background:var(--sidebar-bg);border-right:1px solid var(--border);padding:16px 12px 40px;
  overscroll-behavior:contain}
.sidebar h4{margin:12px 4px 8px;font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.5px}
.sidebar ul{list-style:none;margin:0;padding:0}
.sidebar li a{display:block;padding:5px 10px;border-radius:5px;color:#475569;font-size:13.5px;line-height:1.4}
.sidebar li a:hover{background:#eef2ff;color:var(--accent);text-decoration:none}
.sidebar li.active>a{background:var(--accent-soft);color:var(--accent);font-weight:600}
.sidebar .toc-l2{padding-left:14px}
.sidebar .toc-l3{padding-left:28px}

/* 抽屉部件：桌面隐藏，≤860px 时变为左侧抽屉 */
.drawer-backdrop{display:none}
.sb-head{display:none}
.sb-close{display:none}
.chapters-m{display:none}
.sidebar.m-only{display:none}

.content{padding:28px 40px 80px;min-width:0;overflow-wrap:break-word}
.content h1{font-size:clamp(22px,2.4vw,30px);margin:0 0 6px;line-height:1.3}
.content .meta{color:var(--muted);font-size:13px;margin-bottom:24px}
.content h2{font-size:clamp(19px,2vw,24px);margin:44px 0 12px;padding-bottom:8px;border-bottom:2px solid var(--accent);color:#0b2a6b}
.content h3{font-size:clamp(16px,1.5vw,19px);margin:30px 0 8px;color:#16325f}
.content h4{font-size:16px;margin:22px 0 6px;color:#333}
.content p{margin:10px 0}
.content ul,.content ol{margin:8px 0;padding-left:24px}
.content li{margin:4px 0}
.content blockquote{margin:14px 0;padding:12px 16px;border-left:4px solid #ffd56a;
  background:#fff8e6;border-radius:0 8px 8px 0;color:#5b4a00}
.content blockquote p{margin:4px 0}
.content hr{border:none;border-top:1px solid var(--border);margin:28px 0}
.content table{border-collapse:collapse;width:100%;margin:14px 0;font-size:14px;
  box-shadow:0 1px 2px rgba(0,0,0,.03),0 4px 12px rgba(0,0,0,.04)}
.content th,.content td{border:1px solid var(--border);padding:8px 12px;text-align:left;vertical-align:top}
.content th{background:#f1f5f9;font-weight:650}
.content tr:nth-child(even) td{background:#fbfcfd}
.content img{max-width:100%;border-radius:8px}

/* 行内代码 */
.content code{font-family:"JetBrains Mono","SFMono-Regular",Consolas,"Liberation Mono",Menlo,monospace;
  background:var(--code-bg);padding:1px 6px;border-radius:4px;font-size:13.5px;color:#1f2328}
/* 代码块 */
.content pre{background:#f6f8fa;border:1px solid var(--border);border-radius:8px;
  padding:14px 16px;overflow-x:auto;-webkit-overflow-scrolling:touch;margin:14px 0;font-size:13px;line-height:1.6;max-width:100%}
.content pre code{background:none;padding:0;font-size:13px;color:inherit}

/* 上一章/下一章 */
.pager{display:flex;gap:12px;margin-top:48px;padding-top:20px;border-top:1px solid var(--border)}
.pager a{flex:1;min-width:0;border:1px solid var(--border);border-radius:10px;padding:14px 18px;
  color:#334155;transition:all .15s}
.pager a:hover{border-color:var(--accent);background:var(--accent-soft);text-decoration:none}
.pager .dir{font-size:12px;color:var(--muted)}
.pager .ttl{font-weight:650;color:#0b2a6b;margin-top:2px}

/* ── 首页 ── */
.hero{background:linear-gradient(135deg,#1e3a8a 0%,#2563eb 60%,#3b82f6 100%);color:#fff;padding:60px 24px}
.hero .inner{max-width:900px;margin:0 auto}
.hero h1{font-size:clamp(27px,4.6vw,40px);margin:0 0 12px;line-height:1.2;font-weight:800}
.hero .lead{font-size:clamp(15px,1.6vw,18px);opacity:.92;margin:0 0 18px}
.hero .tags{display:flex;gap:8px;flex-wrap:wrap}
.hero .tag{background:rgba(255,255,255,.15);border:1px solid rgba(255,255,255,.25);
  padding:4px 12px;border-radius:999px;font-size:13px}
.container{max-width:1100px;margin:0 auto;padding:36px 24px 80px}
.section-title{font-size:24px;font-weight:700;color:#0b2a6b;margin:0 0 6px}
.section-sub{color:var(--muted);margin:0 0 20px}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(320px,100%),1fr));gap:16px}
.card{background:#fff;border:1px solid var(--border);border-radius:14px;padding:20px;
  box-shadow:0 1px 2px rgba(0,0,0,.03),0 4px 12px rgba(0,0,0,.04);
  transition:transform .15s,box-shadow .15s;display:flex;flex-direction:column}
.card:hover{transform:translateY(-3px);box-shadow:0 4px 12px rgba(0,0,0,.06),0 12px 28px rgba(0,0,0,.08)}
.card .num{font-size:12px;font-weight:700;letter-spacing:1px;color:var(--muted)}
.card .icon{font-size:30px;margin:6px 0 4px}
.card h3{margin:0 0 6px;font-size:19px;color:#0b2a6b}
.card .sub{color:var(--accent);font-size:13px;margin-bottom:10px}
.card p{margin:0;color:#475569;font-size:14px;flex:1}
.card .cta{margin-top:14px;font-size:13px;font-weight:600}
.roadmap{background:#f8fafc;border:1px solid var(--border);border-radius:14px;padding:24px;margin-top:24px}
.roadmap ol{margin:0;padding-left:22px}
.roadmap li{margin:8px 0}
.roadmap li b{color:#0b2a6b}
.footnote{text-align:center;color:var(--muted);font-size:12px;margin-top:40px}

/* ── 响应式：平板 ── */
@media(max-width:1100px){
  .layout{grid-template-columns:220px 1fr}
  .content{padding:26px 26px 70px}
}

/* ── 响应式：手机（左侧抽屉导航） ── */
@media(max-width:860px){
  .nav-toggle{display:inline-flex}
  .topnav{padding:8px 12px;gap:10px}
  .topnav .brand{flex:1;overflow:hidden;text-overflow:ellipsis}
  .topnav .brand small{display:none}
  .topnav nav,.topnav .src{display:none}
  .layout{grid-template-columns:1fr}

  .drawer-backdrop{display:block;position:fixed;inset:0;z-index:98;background:rgba(15,23,42,.45);
    opacity:0;pointer-events:none;transition:opacity .22s ease}
  body.drawer-open .drawer-backdrop{opacity:1;pointer-events:auto}
  body.drawer-open{overflow:hidden}

  .sidebar{position:fixed;top:0;left:0;width:min(84vw,320px);height:100vh;height:100dvh;
    max-height:100vh;transform:translateX(-105%);transition:transform .25s ease;z-index:99;
    border-right:1px solid var(--border);border-radius:0 14px 14px 0;
    box-shadow:8px 0 30px rgba(0,0,0,.15);padding:12px 14px 40px}
  body.drawer-open .sidebar{transform:translateX(0)}
  .sidebar.m-only{display:block}

  .sb-head{display:flex;align-items:center;justify-content:space-between;
    padding-bottom:10px;margin-bottom:6px;border-bottom:1px solid var(--border)}
  .sb-head b{font-size:15px;color:#0b2a6b}
  .sb-close{display:inline-flex;align-items:center;justify-content:center;border:none;background:none;
    font-size:16px;color:var(--muted);cursor:pointer;padding:6px 9px;border-radius:6px}
  .chapters-m{display:block}
  .sidebar li a{padding:12px 10px;font-size:14px}

  .content{padding:20px 16px 60px}
  .content h1{font-size:clamp(21px,5.6vw,26px)}
  .content h2{margin:34px 0 10px;font-size:clamp(18px,4.4vw,21px)}
  .content h3{font-size:16.5px}
  .content pre{font-size:12.5px;padding:12px}
  .content code{font-size:12.8px}
  .content table{display:block;overflow-x:auto;-webkit-overflow-scrolling:touch}
  .content ul,.content ol{padding-left:20px}
  .pager{flex-direction:column;gap:10px}

  .hero{padding:44px 16px}
  .hero h1{font-size:clamp(25px,7vw,32px)}
  .container{padding:28px 16px 60px}
  .roadmap{padding:18px}
}

/* ── 响应式：小屏手机 ── */
@media(max-width:480px){
  body{font-size:15px}
  .content{padding:16px 13px 50px}
  .card{padding:16px}
  .hero .tag{font-size:12px}
}

/* ── 响应式：手机横屏 ── */
@media(max-width:920px) and (orientation:landscape){
  .sidebar{width:min(62vw,300px)}
}

/* ── 无障碍：偏好减少动画 ── */
@media(prefers-reduced-motion:reduce){
  html{scroll-behavior:auto}
  *,*::before,*::after{transition-duration:.01ms!important;animation-duration:.01ms!important}
}
"""

# ── 自定义 Markdown 处理器：代码块用 Pygments 高亮 ──
import markdown.extensions.codehilite
md = markdown.Markdown(
    extensions=[
        "fenced_code", "tables", "sane_lists", "toc",
        TocExtension(toc_depth="2-3", permalink=False),
    ],
    output_format="html5",
)

# Pygments 高亮替换：markdown 的 codehilite 需要 pygments，这里手动处理 fenced code
# 直接用 markdown + codehilite 扩展更简单
md2 = markdown.Markdown(
    extensions=["fenced_code","tables","sane_lists",
                TocExtension(toc_depth="2-3", permalink=False),
                markdown.extensions.codehilite.CodeHiliteExtension(
                    guess_lang=False, css_class="codehilite", pygments_style="friendly")],
    output_format="html5",
)

def render_markdown(text):
    md2.reset()
    body = md2.convert(text)
    toc_html = md2.toc  # 完整 TOC HTML（<div class="toc"><ul>...</ul></div>）
    # 取最外层 ul 作为侧边栏
    m = re.search(r'<ul>.*</ul>', toc_html, re.S)
    sidebar_toc = m.group(0) if m else ""
    return body, sidebar_toc

# ── 移动端抽屉导航：章节列表与交互脚本（零依赖，三端通用） ──
def drawer_chapters(cur=None):
    lis = ['<li><a href="index.html">🏠 课程总览（首页）</a></li>']
    for m in MODULES:
        cls = ' class="active"' if m["num"] == cur else ''
        lis.append(
            f'<li{cls}><a href="{m["num"].lower()}.html">{m["icon"]} 第 {m["num"]} 章 · {m["title"]}</a></li>'
        )
    return "\n".join(lis)

JS = """
<script>
(function(){
  var body=document.body,toggle=document.querySelector('.nav-toggle');
  function setOpen(open){
    body.classList.toggle('drawer-open',open);
    if(toggle)toggle.setAttribute('aria-expanded',open?'true':'false');
  }
  function close(){setOpen(false)}
  if(toggle)toggle.addEventListener('click',function(){
    setOpen(!body.classList.contains('drawer-open'));
  });
  var bk=document.querySelector('.drawer-backdrop');
  if(bk)bk.addEventListener('click',close);
  var xc=document.querySelector('.sb-close');
  if(xc)xc.addEventListener('click',close);
  document.addEventListener('keydown',function(e){if(e.key==='Escape')close()});
})();
</script>
"""

def page_template(mod, body_html, toc_html, prev_mod, next_mod):
    acc = mod["accent"]
    nav_links = "".join(
        f'<a href="{m["num"].lower()}.html" class="{"active" if m["num"]==mod["num"] else ""}">{m["num"]} {m.get("navtitle", m["title"][:10])}</a>'
        for m in MODULES
    )
    pager = ""
    if prev_mod:
        pager += f'<a href="{prev_mod["num"].lower()}.html"><div class="dir">← 上一章</div><div class="ttl">{prev_mod["title"]}</div></a>'
    else:
        pager += f'<a href="index.html"><div class="dir">← 首页</div><div class="ttl">回到课程总览</div></a>'
    if next_mod:
        pager += f'<a href="{next_mod["num"].lower()}.html" style="text-align:right"><div class="dir">下一章 →</div><div class="ttl">{next_mod["title"]}</div></a>'

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
<meta name="theme-color" content="#1e3a8a">
<title>{mod['num']} {mod['title']} · Java · SQL · Python AI 教程</title>
<link rel="stylesheet" href="assets/style.css">
</head>
<body>
<header class="topnav">
  <button class="nav-toggle" type="button" aria-label="打开导航目录" aria-expanded="false" aria-controls="sidebar">☰</button>
  <div class="brand">Java · SQL · Python AI 教程<small>从原理到实战</small></div>
  <nav>{nav_links}</nav>
  <a class="src" href="https://github.com/user-unknowed/studying-for-building" target="_blank" rel="noopener">📦 源码仓库</a>
</header>
<div class="drawer-backdrop" aria-hidden="true"></div>
<div class="layout">
  <aside class="sidebar" id="sidebar">
    <div class="sb-head"><b>📑 导航目录</b><button class="sb-close" type="button" aria-label="关闭目录">✕</button></div>
    <div class="chapters-m">
      <h4>全部章节</h4>
      <ul>{drawer_chapters(mod['num'])}</ul>
    </div>
    <h4>本节目录</h4>
    <ul>{toc_html}</ul>
  </aside>
  <main class="content">
    <div class="meta" style="color:{acc};font-weight:600">第 {mod['num']} 章 · {mod['icon']}</div>
    <h1 style="border-bottom:3px solid {acc};padding-bottom:10px">{mod['title']}</h1>
    <div class="meta">{mod['subtitle']}</div>
    {body_html}
    <div class="pager">{pager}</div>
  </main>
</div>
{JS}
</body>
</html>"""

def build_toc(items):
    out = []
    for level, title, slug in items:
        cls = "toc-l2" if level == 2 else "toc-l3"
        out.append(f'<li class="{cls}"><a href="#{slug}">{html.escape(title)}</a></li>')
    return "\n".join(out)

# ── 生成 7 个内容页 ──
for i, mod in enumerate(MODULES):
    src_path = os.path.join(SRC, mod["file"])
    with open(src_path, "r", encoding="utf-8") as f:
        md_text = f.read()
    body, sidebar_toc = render_markdown(md_text)
    prev_mod = MODULES[i - 1] if i > 0 else None
    next_mod = MODULES[i + 1] if i < len(MODULES) - 1 else None
    page = page_template(mod, body, sidebar_toc, prev_mod, next_mod)
    out_path = os.path.join(OUT, f"{mod['num'].lower()}.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"  ✓ {out_path}  ({len(md_text)} chars → {len(page)} html)")

# ── 写入 CSS ──
with open(f"{OUT}/assets/style.css", "w", encoding="utf-8") as f:
    f.write(CSS + "\n\n/* ── Pygments 代码高亮 ── */\n" + pygments_css)

# ── 生成首页 ──
cards_html = ""
for mod in MODULES:
    cards_html += f'''
    <a class="card" href="{mod["num"].lower()}.html">
      <div class="num">第 {mod["num"]} 章</div>
      <div class="icon">{mod["icon"]}</div>
      <h3>{mod["title"]}</h3>
      <div class="sub">{mod["subtitle"]}</div>
      <p>{mod["desc"]}</p>
      <div class="cta" style="color:{mod["accent"]}">开始阅读 →</div>
    </a>'''

index_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
<meta name="theme-color" content="#1e3a8a">
<title>Java · SQL · Python AI 系统化教程 · 从原理到实战</title>
<link rel="stylesheet" href="assets/style.css">
</head>
<body>
<header class="topnav">
  <button class="nav-toggle" type="button" aria-label="打开章节导航" aria-expanded="false" aria-controls="sidebar">☰</button>
  <div class="brand">Java · SQL · Python AI 教程<small>从原理到实战</small></div>
  <nav>{"".join(f'<a href="{m["num"].lower()}.html">{m["num"]} {m.get("navtitle", m["title"][:10])}</a>' for m in MODULES)}</nav>
  <a class="src" href="https://github.com/user-unknowed/studying-for-building" target="_blank" rel="noopener">📦 源码仓库</a>
</header>
<div class="drawer-backdrop" aria-hidden="true"></div>
<aside class="sidebar m-only" id="sidebar" aria-label="章节导航">
  <div class="sb-head"><b>📑 章节导航</b><button class="sb-close" type="button" aria-label="关闭导航">✕</button></div>
  <div class="chapters-m">
    <h4>全部章节</h4>
    <ul>{drawer_chapters()}</ul>
  </div>
</aside>

<section class="hero">
  <div class="inner">
    <h1>Java · SQL · Python AI 系统化教程</h1>
    <p class="lead">从 JavaSE 基础 → Java×SQL 融合 → SQL 工业实践 → JavaEE 服务端 → 上位机（工业采集）→ Python 与 AI 大模型，递进式六阶梯。所有演示代码均经过真实编译、运行、验证。</p>
    <div class="tags">
      <span class="tag">JavaSE</span><span class="tag">JDBC</span><span class="tag">SQL</span>
      <span class="tag">索引优化</span><span class="tag">事务并发</span><span class="tag">Jakarta EE</span>
      <span class="tag">Spring Boot</span><span class="tag">Modbus</span><span class="tag">上位机</span>
      <span class="tag">Python</span><span class="tag">Transformer</span><span class="tag">PyTorch</span><span class="tag">vLLM</span>
    </div>
  </div>
</section>

<div class="container">
  <h2 class="section-title">课程模块</h2>
  <p class="section-sub">9 个递进章节，覆盖从语言基础到工业应用、AI 大模型与 ICT 竞赛实战的完整阶梯。</p>
  <div class="cards">{cards_html}
  </div>

  <div class="roadmap">
    <h2 class="section-title" style="font-size:20px">建议学习路线</h2>
    <ol>
      <li><b>① JavaSE 基础</b> → 01 章 + javase-demo（字节码、类型陷阱、OOP、集合、并发、现代语法）</li>
      <li><b>② Java × SQL 融合</b> → 02 章 + java-sql-demo（JDBC、注入攻防、转账事务、批处理）</li>
      <li><b>③ SQL 工业实践</b> → 03 章 + sql-demo（窗口函数、EXPLAIN、索引、MVCC）</li>
      <li><b>④ JavaEE 服务端</b> → 05 章 + demos（先原生 Jakarta EE，后 Spring Boot）</li>
      <li><b>⑤ 上位机 / 工业采集</b> → 06、07 章 + demos（先桌面版 device-monitor，再网页版 web-monitor）</li>
      <li><b>⑥ Python 与 AI 大模型</b> → 08 章 + py-ai-demo（张量、Autograd、手写 MiniGPT、GPU 并行、vLLM 服务化）</li>
    </ol>
    <p style="color:var(--muted);font-size:13px;margin:12px 0 0">每一步遵循同一原则：<b>先读文档懂原理，再跑代码看真实结果</b>。</p>
  </div>

  <p class="footnote">基于开源仓库 studying-for-building 整理 · 所有代码与运行结果均经真实编译运行验证 · AI 辅助整理，请结合实际工程判断</p>
</div>
{JS}
</body>
</html>"""

with open(f"{OUT}/index.html", "w", encoding="utf-8") as f:
    f.write(index_html)
print("\n  ✓ index.html")
print(f"\n✅ 网站构建完成 → {OUT}/")
