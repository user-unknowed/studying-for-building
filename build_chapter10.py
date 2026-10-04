#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
构建第 10 章《源码编辑与源码导读》：

1. 生成 site/10.html —— 包含
   · 交互式源码编辑器（零依赖，纯原生 JS）
   · 三份带详尽注释的源码全文清单（Pygments 高亮 + 行号 + 逐行讲解表）
   · 三份源码同时以 <script type="text/plain"> 形式内嵌，供编辑器加载
     （编辑器内容与清单内容逐字节一致：来自同一份源码字符串）
2. 注册到全站导航：
   · site/index.html 首页卡片 + hero 文案 + 顶部导航
   · site/01~09.html 顶部导航追加 "10 源码编辑"
   · site/09.html 底部翻页器追加 "下一章"
3. 构建前对三份源码做真实语法检查（node --check / py_compile）
"""
import os
import re
import subprocess
import sys
import tempfile

from pygments import highlight as pyg_highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name

SITE = "/workspace/site"

# ════════════════════════════════════════════════════════════════════
# 一、三份源码（唯一数据源：编辑器与清单都从这里生成）
# ════════════════════════════════════════════════════════════════════

WORKER_JS = r'''// =====================================================================
// worker.js —— 本站 Cloudflare Worker 边缘路由（教学注释版）
// ---------------------------------------------------------------------
// 真实文件：/workspace/worker_kv.js（内容存 KV）；本版把 KV 换成内存表，
// 路由 / 404 / 缓存头逻辑与线上完全一致，可以直接在本页编辑器里改着玩。
//
// 执行模型：请求到达全球 300+ 个边缘节点之一，节点上的 V8 isolate
// 调用一次下面的 fetch() 并返回响应。没有"服务器进程"——
// 每个请求都是一次独立的函数调用，冷启动以毫秒计。
// =====================================================================

// ── 1. 路由表：路径 → Content-Type ─────────────────────────────────
// Content-Type 决定浏览器如何处理响应体：
//   text/html → 解析成 DOM；text/css → 当样式表应用；其余按二进制下载
const ROUTES = {
  "/":                 "text/html; charset=utf-8",
  "/index.html":       "text/html; charset=utf-8",
  "/01.html":          "text/html; charset=utf-8",
  "/02.html":          "text/html; charset=utf-8",
  "/03.html":          "text/html; charset=utf-8",
  "/04.html":          "text/html; charset=utf-8",
  "/05.html":          "text/html; charset=utf-8",
  "/06.html":          "text/html; charset=utf-8",
  "/07.html":          "text/html; charset=utf-8",
  "/08.html":          "text/html; charset=utf-8",
  "/09.html":          "text/html; charset=utf-8",
  "/10.html":          "text/html; charset=utf-8",
  "/assets/style.css": "text/css; charset=utf-8",
};

// ── 2. 入口：导出一个带 fetch 方法的对象 ────────────────────────────
// Workers 模块语法约定：default 导出对象上的 fetch 就是请求处理函数
export default {
  async fetch(request) {
    // 2.1 解析请求 URL，只取路径部分（?查询参数 和 #锚点 都不参与路由）
    const { pathname } = new URL(request.url);

    // 2.2 路径归一化：访问根路径等价于访问 /index.html
    //     用户直接敲域名不带文件名时，也能落到首页
    const key = pathname === "/" ? "/index.html" : pathname;

    // 2.3 查路由表（白名单思路：默认拒绝，命中才放行）
    const type = ROUTES[key];
    if (!type) {
      // 404 也要显式声明 Content-Type，
      // 防止浏览器把错误文本当 HTML 渲染出奇怪的页面
      return new Response("Not Found: " + key, {
        status: 404,
        headers: { "Content-Type": "text/plain; charset=utf-8" },
      });
    }

    // 2.4 真实站点在这里从 KV 读出 gzip+base64 内容并解压后返回
    //     （完整解压流程见下方"逐行讲解"表）；教学版返回占位页面
    const body = "<!DOCTYPE html><p>这里本应返回 " + key + " 的真实内容</p>";

    // 2.5 构造响应：缓存头让边缘节点替源站挡住重复流量
    //     public        → 浏览器和 CDN 都可以缓存
    //     max-age=3600  → 缓存 1 小时，期间命中缓存不再回源
    return new Response(body, {
      headers: {
        "Content-Type": type,
        "Cache-Control": "public, max-age=3600",
      },
    });
  },
};
'''

DEPLOY_PY = r'''# -*- coding: utf-8 -*-
# =====================================================================
# deploy.py —— 把 site/ 目录一键发布到 Cloudflare Pages（教学注释版）
# ---------------------------------------------------------------------
# 真实文件：/workspace/deploy_pages.py；本版保留完整流程，
# 删去少量工程细节，聚焦"一次发布到底发生了什么"。
#
# 发布静态站到边缘网络只需三步：
#   ① 指纹：算出每个文件的 SHA-256（内容寻址——改一个字符指纹就变）
#   ② 上传：把文件本体按批次送进 Pages 资产仓库（同指纹自动去重）
#   ③ 装订：提交"路径 → 指纹"清单，Cloudflare 把资产装订成一次新部署
# =====================================================================
import base64          # 把二进制文件编码成可放进 JSON 的文本
import hashlib         # 计算 SHA-256 内容指纹
import json            # 序列化上传清单
import mimetypes       # 按扩展名推断 Content-Type（.html → text/html）
import os              # 遍历目录、读取环境变量
import sys             # 出错时以非零码退出

import requests        # 唯一的第三方依赖：同步 HTTP 客户端

# ── 配置区：改这两行就能发布别的站点 ────────────────────────────────
SITE_DIR = "site"                  # 待发布的静态文件目录
PROJECT  = "java-sql-ai-tutorial"  # Pages 项目名（决定最终域名）
API      = "https://api.cloudflare.com/client/v4"   # Cloudflare API 根地址
ACCOUNT  = os.environ["CLOUDFLARE_ACCOUNT_ID"]      # 账号 ID（环境变量传入）


def sha256_of(path):
    """流式计算文件指纹：每次只读 1MB，大文件也不会撑爆内存。"""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        # iter(callable, sentinel)：反复调用 f.read，直到读到空字节串 b""
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()           # 64 位十六进制字符串，即文件指纹


def collect_assets():
    """遍历 SITE_DIR，返回 (待上传资产列表, 路径→指纹 清单)。"""
    assets, manifest = [], {}
    for root, _, files in os.walk(SITE_DIR):       # os.walk 递归下钻子目录
        for name in files:
            full = os.path.join(root, name)
            # 逻辑路径必须以 / 开头且用正斜杠——这是 Pages 清单的硬性约定
            rel = "/" + os.path.relpath(full, SITE_DIR).replace(os.sep, "/")
            with open(full, "rb") as f:
                raw = f.read()
            ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
            # 注意：key 是内容指纹，不是文件名！
            # 同一文件在多次部署间天然去重，改过的文件指纹不同才需重新上传
            assets.append({
                "key": sha256_of(full),
                "value": base64.b64encode(raw).decode(),   # 二进制 → base64 文本
                "base64": True,       # 告诉 API value 字段是 base64 编码
                "contentType": ctype,
            })
            manifest[rel] = assets[-1]["key"]       # 清单：路径 → 指纹
            print(f"  {rel:32s} {assets[-1]['key'][:12]}...")
    return assets, manifest


def main():
    token = os.environ.get("CLOUDFLARE_API_TOKEN")
    if not token:
        sys.exit("请先设置环境变量 CLOUDFLARE_API_TOKEN")
    auth = {"Authorization": "Bearer " + token}

    assets, manifest = collect_assets()

    # ── ① 用长效令牌换一次性上传令牌（JWT，约 30 分钟有效）──────────
    #      资产上传走专门的资产接口，只认这个短命 JWT，缩小凭证暴露面
    r = requests.get(
        f"{API}/accounts/{ACCOUNT}/pages/projects/{PROJECT}/upload-token",
        headers=auth,
    )
    r.raise_for_status()               # 4xx/5xx 直接抛异常，不带病往下走
    jwt = r.json()["result"]["jwt"]

    # ── ② 分批上传：单批请求体控制在 ~240KB，避免超过网关限制 ───────
    batch, batch_size = [], 0
    for a in assets:
        if batch and batch_size + len(a["value"]) > 240 * 1024:
            requests.post(f"{API}/pages/assets/upload",
                          headers={"Authorization": "Bearer " + jwt},
                          json=batch).raise_for_status()
            batch, batch_size = [], 0   # 清空，开始攒下一批
        batch.append(a)
        batch_size += len(a["value"])
    if batch:                           # 循环结束后别忘了最后一批
        requests.post(f"{API}/pages/assets/upload",
                      headers={"Authorization": "Bearer " + jwt},
                      json=batch).raise_for_status()

    # ── ③ 提交清单：Cloudflare 按清单把资产"装订"成一次新部署 ────────
    #      files 参数传 (文件名, 内容, 类型) → 以 multipart 表单发送
    r = requests.post(
        f"{API}/accounts/{ACCOUNT}/pages/projects/{PROJECT}/deployments",
        headers=auth,
        files={"manifest": (None, json.dumps(manifest))},
    )
    r.raise_for_status()
    print("部署完成 →", r.json()["result"]["url"])


if __name__ == "__main__":
    main()
'''

EDITOR_JS = r'''/* =====================================================================
 * editor.js —— 本页"交互式源码编辑器"组件（零依赖）
 * ---------------------------------------------------------------------
 * 功能：多文件标签页 / 行号同步 / 光标位置 / 高亮预览 /
 *       复制 / 重置 / 下载 / 修改自动保存（localStorage）
 * 数据来源：页面里所有 <script type="text/plain" data-file="...">
 *           标签的内容即编辑器的初始源码——不执行的 script
 *           正好当作"嵌在页面里的纯文本文件仓库"，无需任何转义。
 * ===================================================================== */
(function () {
  "use strict";

  /* ── 1. 迷你语法高亮器 ───────────────────────────────────────────
   * 一条正则、四个捕获组，从左到右优先级递减：
   * 注释 > 字符串 > 数字 > 关键字。
   * 顺序是关键——注释和字符串必须排在关键字前，
   * 否则字符串里的 "function" 也会被当成关键字染色。 */
  const JS_RE = /(\/\/[^\n]*|\/\*[\s\S]*?\*\/)|("(?:[^"\\\n]|\\.)*"|'(?:[^'\\\n]|\\.)*'|`(?:[^`\\]|\\.)*`)|\b(\d+(?:\.\d+)?)\b|\b(const|let|var|function|return|if|else|for|while|do|switch|case|break|continue|new|class|extends|export|import|from|default|async|await|of|in|typeof|instanceof|try|catch|finally|throw|this|super|null|true|false|undefined|delete|void|yield|static)\b/g;
  const PY_RE = /(#[^\n]*)|("""[\s\S]*?"""|"(?:[^"\\\n]|\\.)*"|'(?:[^'\\\n]|\\.)*')|\b(\d+(?:\.\d+)?)\b|\b(def|class|return|if|elif|else|for|while|in|not|and|or|is|None|True|False|try|except|finally|raise|with|as|import|from|lambda|pass|break|continue|self|global|nonlocal|assert|del|yield|async|await)\b/g;

  /* HTML 转义：& 必须最先替换。
   * 若先替换 <，产生的 &lt; 里的 & 会被二次转义成 &amp;lt;。 */
  function esc(s) {
    return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  function highlight(code, lang) {
    const re = lang === "py" ? PY_RE : JS_RE;
    re.lastIndex = 0;            // 带 g 标志的正则是"有状态"的，用前必须归零
    let out = "", last = 0, m;
    while ((m = re.exec(code)) !== null) {
      out += esc(code.slice(last, m.index));              // 词元之间的普通文本
      const cls = m[1] ? "c" : m[2] ? "s" : m[3] ? "m" : "k";  // 注释/字符串/数字/关键字
      out += '<span class="' + cls + '">' + esc(m[0]) + "</span>";
      last = m.index + m[0].length;
    }
    return out + esc(code.slice(last));
  }

  /* ── 2. 收集要编辑的源码文件 ──────────────────────────────────── */
  const FILES = [];
  const nodes = document.querySelectorAll('script[type="text/plain"][data-file]');
  for (let i = 0; i < nodes.length; i++) {
    const name = nodes[i].getAttribute("data-file");
    FILES.push({
      name: name,
      lang: /\.py$/.test(name) ? "py" : "js",
      original: nodes[i].textContent.replace(/^\n/, ""),  // 去掉紧贴标签的首个换行
    });
  }

  /* ── 3. 抓取页面元素 ──────────────────────────────────────────── */
  function $(id) { return document.getElementById(id); }
  const editor  = $("sce-code");      // 可编辑的 textarea
  const gutter  = $("sce-gutter");    // 行号列
  const preview = $("sce-preview");   // 高亮预览区
  let current = null;                 // 当前打开的文件对象

  /* ── 4. 行号 / 统计 / 光标位置 ────────────────────────────────── */
  function refreshGutter() {
    const lines = editor.value.split("\n").length;
    let html = "";
    for (let i = 1; i <= lines; i++) html += i + "\n";
    gutter.textContent = html;
    $("sce-lines").textContent = lines;
    $("sce-chars").textContent = editor.value.length;
  }

  function refreshCursor() {
    const rows = editor.value.slice(0, editor.selectionStart).split("\n");
    $("sce-pos").textContent =
      "行 " + rows.length + "，列 " + (rows[rows.length - 1].length + 1);
  }

  /* ── 5. 高亮预览：把编辑区当前内容渲染成带颜色的 HTML ─────────── */
  function renderPreview() {
    preview.innerHTML = "<code>" + highlight(editor.value, current.lang) + "</code>";
  }

  /* ── 6. 打开文件：初始化编辑区（优先恢复本地草稿）──────────────── */
  function openFile(file) {
    current = file;
    let saved = null;
    try { saved = localStorage.getItem("sce:" + file.name); } catch (e) {}
    editor.value = saved !== null ? saved : file.original;
    const tabs = document.querySelectorAll(".sce-tab");
    for (let i = 0; i < tabs.length; i++) {
      tabs[i].classList.toggle("active", tabs[i].getAttribute("data-file") === file.name);
    }
    $("sce-filename").textContent = file.name + (saved !== null ? "（含本地修改）" : "");
    refreshGutter();
    refreshCursor();
    renderPreview();
  }

  /* ── 7. 事件绑定 ──────────────────────────────────────────────── */
  editor.addEventListener("input", function () {
    // 自动保存：每次按键都写 localStorage，刷新页面不丢
    try { localStorage.setItem("sce:" + current.name, editor.value); } catch (e) {}
    refreshGutter();
    renderPreview();
  });
  editor.addEventListener("keyup", refreshCursor);
  editor.addEventListener("click", refreshCursor);

  /* 行号列与编辑区 / 预览区纵向滚动保持同步（单向驱动，避免抖动） */
  editor.addEventListener("scroll", function () { gutter.scrollTop = editor.scrollTop; });
  preview.addEventListener("scroll", function () { gutter.scrollTop = preview.scrollTop; });

  /* 按 Tab 插入两个空格而不是把焦点切走——编辑器的基本礼仪 */
  editor.addEventListener("keydown", function (e) {
    if (e.key === "Tab") {
      e.preventDefault();
      const s = editor.selectionStart, t = editor.selectionEnd;
      editor.value = editor.value.slice(0, s) + "  " + editor.value.slice(t);
      editor.selectionStart = editor.selectionEnd = s + 2;
      editor.dispatchEvent(new Event("input"));   // 手动触发，走统一的保存+刷新
    }
  });

  $("sce-copy").onclick = function () {
    const btn = this;
    const done = function () {
      btn.textContent = "已复制 ✓";
      setTimeout(function () { btn.textContent = "复制"; }, 1200);
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(editor.value).then(done);
    } else {                       // 老浏览器退化方案：选中全文再复制
      editor.select();
      document.execCommand("copy");
      editor.setSelectionRange(0, 0);
      done();
    }
  };

  $("sce-reset").onclick = function () {
    if (!confirm("放弃本地修改，恢复本章原始源码？")) return;
    try { localStorage.removeItem("sce:" + current.name); } catch (e) {}
    openFile(current);
  };

  $("sce-download").onclick = function () {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([editor.value], { type: "text/plain" }));
    a.download = current.name;
    a.click();
    URL.revokeObjectURL(a.href);   // 用完立刻释放，避免内存泄漏
  };

  /* 在"可编辑纯文本"与"高亮预览"两个视图之间切换 */
  $("sce-toggle").onclick = function () {
    const on = document.body.classList.toggle("sce-preview-on");
    this.textContent = on ? "返回编辑" : "高亮预览";
  };

  /* 文件标签页切换 */
  const tabs = document.querySelectorAll(".sce-tab");
  for (let i = 0; i < tabs.length; i++) {
    tabs[i].onclick = function () {
      const want = this.getAttribute("data-file");
      for (let j = 0; j < FILES.length; j++) {
        if (FILES[j].name === want) { openFile(FILES[j]); return; }
      }
    };
  }

  if (FILES.length) openFile(FILES[0]);   // 默认打开第一个文件
})();
'''

SOURCES = [
    ("worker.js", "js", WORKER_JS, "JavaScript · Cloudflare Worker · 运行在离用户最近的边缘节点"),
    ("deploy.py", "py", DEPLOY_PY, "Python · 部署脚本 · 运行在开发机上，把 site/ 发布到边缘"),
    ("editor.js", "js", EDITOR_JS, "JavaScript · 前端组件 · 运行在浏览器里，就是本章的编辑器"),
]

# ════════════════════════════════════════════════════════════════════
# 二、语法检查：三份源码必须真实可编译
# ════════════════════════════════════════════════════════════════════

def syntax_check():
    for name, lang, src, _ in SOURCES:
        with tempfile.NamedTemporaryFile(
                "w", suffix=".mjs" if lang == "js" else ".py",
                delete=False, encoding="utf-8") as f:
            f.write(src)
            path = f.name
        try:
            if lang == "js":
                r = subprocess.run(["node", "--check", path],
                                   capture_output=True, text=True)
            else:
                compile(src, name, "exec")   # py 语法检查不需要子进程
                r = None
            if r is not None and r.returncode != 0:
                sys.exit(f"[FAIL] {name} 语法错误:\n{r.stderr}")
            print(f"  [ok] {name} 语法检查通过")
        finally:
            os.unlink(path)

# ════════════════════════════════════════════════════════════════════
# 三、工具函数
# ════════════════════════════════════════════════════════════════════

FMT = HtmlFormatter(cssclass="codehilite", linenos="inline")

def listing(src, lang):
    """Pygments 高亮（带行内行号），输出与全站 .codehilite CSS 兼容。"""
    return pyg_highlight(src, get_lexer_by_name(lang), FMT).strip()

def lineno(src, needle):
    """返回 needle 所在行号（用于讲解表精确引用）。"""
    for i, line in enumerate(src.splitlines(), 1):
        if needle in line:
            return i
    raise SystemExit(f"anchor not found: {needle!r}")

def nlines(src):
    return len(src.splitlines())

# ════════════════════════════════════════════════════════════════════
# 四、页面组装
# ════════════════════════════════════════════════════════════════════

NAV = ('<nav><a href="01.html" class="">01 JavaSE 基础知</a>'
       '<a href="02.html" class="">02 Java 与 SQL</a>'
       '<a href="03.html" class="">03 SQL 数据库深度讲</a>'
       '<a href="04.html" class="">04 学习报告：Java </a>'
       '<a href="05.html" class="">05 JavaEE 企业级</a>'
       '<a href="06.html" class="">06 Java 上位机开发</a>'
       '<a href="07.html" class="">07 JavaEE 上位机</a>'
       '<a href="08.html" class="">08 Python 与 A</a>'
       '<a href="09.html" class="">09 华为ICT大赛·网络</a>'
       '<a href="10.html" class="active">10 源码编辑</a></nav>')

PAGE_CSS = """
/* ===== 第 10 章专属：交互式源码编辑器 ===== */
.sce { border:1px solid var(--border); border-radius:10px; overflow:hidden; margin:20px 0; background:#fff; }
.sce-tabs { display:flex; align-items:flex-end; gap:4px; padding:10px 12px 0; background:#f8fafc; border-bottom:1px solid var(--border); flex-wrap:wrap; }
.sce-tab { border:1px solid var(--border); border-bottom:none; background:#fff; color:var(--muted);
  font:12px/1.4 ui-monospace,SFMono-Regular,Consolas,monospace; padding:7px 14px;
  border-radius:8px 8px 0 0; cursor:pointer; }
.sce-tab.active { color:var(--accent); font-weight:700; box-shadow:inset 0 -2px 0 var(--accent); }
.sce-hint { font-size:12px; color:var(--muted); margin-left:auto; padding:6px 2px 8px; }
.sce-toolbar { display:flex; gap:8px; align-items:center; padding:8px 12px; background:#f8fafc;
  border-bottom:1px solid var(--border); flex-wrap:wrap; }
.sce-toolbar button { font-size:12px; padding:5px 14px; border-radius:6px; border:1px solid var(--border);
  background:#fff; color:var(--text); cursor:pointer; }
.sce-toolbar button:hover { border-color:var(--accent); color:var(--accent); }
.sce-file { margin-left:auto; font:12px/1.4 ui-monospace,SFMono-Regular,Consolas,monospace; color:var(--accent); }
.sce-stage { display:flex; background:var(--code-bg); height:480px; }
.sce-gutter { width:52px; flex-shrink:0; overflow:hidden; padding:12px 10px 12px 0; text-align:right;
  color:#585b70; background:#181825; border-right:1px solid #313244; user-select:none;
  font:13px/1.55 ui-monospace,SFMono-Regular,Consolas,"Liberation Mono",monospace; }
#sce-code { flex:1; height:100%; border:none; outline:none; resize:none; background:var(--code-bg);
  color:var(--code-text); padding:12px 16px; white-space:pre; overflow:auto; tab-size:2;
  font:13px/1.55 ui-monospace,SFMono-Regular,Consolas,"Liberation Mono",monospace; }
.sce-preview { display:none; flex:1; height:100%; margin:0; padding:12px 16px; white-space:pre;
  overflow:auto; border-radius:0;
  font:13px/1.55 ui-monospace,SFMono-Regular,Consolas,"Liberation Mono",monospace; }
.sce-preview code { font-size:13px; background:none; padding:0; color:inherit; }
body.sce-preview-on #sce-code { display:none; }
body.sce-preview-on .sce-preview { display:block; }
.sce-status { display:flex; gap:18px; padding:7px 12px; background:#f8fafc; border-top:1px solid var(--border);
  font:12px/1.6 ui-monospace,SFMono-Regular,Consolas,monospace; color:var(--muted); flex-wrap:wrap; }
@media (max-width:900px) { .sce-stage { height:380px; } .sce-gutter { width:44px; } .sce-hint { display:none; } }
/* ===== 第 10 章专属：源码清单盒子 ===== */
.srcbox { border:1px solid var(--border); border-radius:10px; overflow:hidden; margin:18px 0; }
.srcbox-head { display:flex; align-items:center; gap:12px; padding:10px 14px; background:#f8fafc;
  border-bottom:1px solid var(--border); flex-wrap:wrap; }
.srcbox-name { font:600 13px/1.4 ui-monospace,SFMono-Regular,Consolas,monospace; color:var(--accent); }
.srcbox-meta { font-size:12px; color:var(--muted); }
.srcbox-open { margin-left:auto; font-size:12px; color:var(--accent); text-decoration:none;
  border:1px solid var(--accent); border-radius:6px; padding:3px 10px; white-space:nowrap; }
.srcbox-open:hover { background:var(--accent-soft); }
.srcbox .codehilite { margin:0; }
.srcbox .codehilite pre { margin:0; border-radius:0; }
.codehilite .linenos { color:#585b70; user-select:none; }
/* 讲解表里的代码列用等宽字体 */
table.srcline td code { font-size:12px; }
"""

def build_editor_widget():
    tabs = "".join(
        f'<button class="sce-tab{" active" if i == 0 else ""}" data-file="{name}">{name}</button>'
        for i, (name, _, _, _) in enumerate(SOURCES))
    data_blocks = "\n".join(
        f'<script type="text/plain" data-file="{name}">\n{src}</script>'
        for name, _, src, _ in SOURCES)
    return tabs, data_blocks

def build_srcbox(name, lang, src, desc, anchor_note):
    head = (f'<div class="srcbox-head"><span class="srcbox-name">{name}</span>'
            f'<span class="srcbox-meta">{desc} · {nlines(src)} 行</span>'
            f'<a class="srcbox-open" href="#widget">↑ 在编辑器中打开</a></div>')
    return f'<div class="srcbox">{head}{listing(src, lang)}</div>\n<p>{anchor_note}</p>'

# ── 讲解表数据（行号动态计算，保证与源码永远对齐） ──
def explain_table(rows):
    out = ['<table class="srcline"><thead><tr><th style="width:64px">行号</th>'
           '<th style="width:220px">代码</th><th>讲解</th></tr></thead><tbody>']
    for src, needle, code, why in rows:
        out.append(f'<tr><td>{lineno(src, needle)}</td><td><code>{code}</code></td>'
                   f'<td>{why}</td></tr>')
    out.append('</tbody></table>')
    return "\n".join(out)

WORKER_ROWS = [
    (WORKER_JS, "const ROUTES = {", "const ROUTES = {...}",
     "路由表是全站白名单：路径 → Content-Type。白名单意味着“默认拒绝”——没列出的路径一律 404，比黑名单安全得多，新增页面必须在这里登记"),
    (WORKER_JS, "export default {", "export default {",
     "Cloudflare Workers 的模块入口约定：default 导出对象上的 fetch 就是请求处理函数，每个请求触发一次调用"),
    (WORKER_JS, "const { pathname } = new URL", "new URL(request.url)",
     "解析请求行 URL，只取 pathname；查询参数与锚点不参与路由"),
    (WORKER_JS, 'const key = pathname === "/"', 'pathname === "/" ? ...',
     "路径归一化：根路径等价于 /index.html，用户直接敲域名也能落到首页"),
    (WORKER_JS, "if (!type) {", "if (!type) → 404",
     "查表未命中就构造 404 响应。注意连错误响应也显式声明了 Content-Type: text/plain，防止浏览器把错误文本当 HTML 渲染"),
    (WORKER_JS, "const body =", "const body = ...",
     "教学版返回占位内容；真实站点（worker_kv.js）在这一步从 KV 读出 gzip+base64 数据，用 DecompressionStream 解压后返回"),
    (WORKER_JS, '"Cache-Control"', '"Cache-Control"',
     "缓存头：public 表示浏览器与 CDN 都可缓存；max-age=3600 表示 1 小时内命中缓存不再回源，把流量挡在离用户最近的边缘节点"),
]

DEPLOY_ROWS = [
    (DEPLOY_PY, "import requests", "import requests",
     "唯一的第三方依赖。部署脚本不需要异步并发，同步 HTTP 客户端最简单可靠"),
    (DEPLOY_PY, 'SITE_DIR = "site"', 'SITE_DIR = "site"',
     "配置区集中放在文件顶部：改两个字符串就能发布另一个站点，这是脚本可复用的最低成本设计"),
    (DEPLOY_PY, "def sha256_of(path):", "def sha256_of(path)",
     "流式读取（每次 1MB）计算指纹。iter(callable, sentinel) 是 Python 惯用的“读到空值为止”循环，大文件不会撑爆内存"),
    (DEPLOY_PY, 'rel = "/" + os.path.relpath', 'rel = "/" + ...',
     "逻辑路径必须以 / 开头且用正斜杠——这是 Pages 清单的硬性约定；Windows 下的反斜杠必须换掉"),
    (DEPLOY_PY, '"key": sha256_of(full)', '"key": sha256_of(full)',
     "上传资产的 key 是内容指纹而不是文件名——同一文件在多次部署间天然去重，本次上线只需真正上传改动过的文件"),
    (DEPLOY_PY, "upload-token", "upload-token",
     "用长效 API 令牌换取一次性 JWT（约 30 分钟有效）。资产上传接口只认这个短命令牌，缩小长效凭证的暴露面"),
    (DEPLOY_PY, "240 * 1024", "240 * 1024",
     "单批请求体上限的经验值。分批上传避免超过网关对请求体大小的限制"),
    (DEPLOY_PY, 'files={"manifest":', 'files={"manifest": ...}',
     "创建部署是 multipart 表单：manifest 字段是“路径 → 指纹”的 JSON，Cloudflare 按清单把已上传资产“装订”成一次新部署"),
]

EDITOR_ROWS = [
    (EDITOR_JS, "const JS_RE =", "const JS_RE = /.../g",
     "迷你高亮器的全部秘密：一条正则四个捕获组，从左到右优先级递减——注释、字符串、数字、关键字。顺序错了，字符串里的关键字会被误染色"),
    (EDITOR_JS, "re.lastIndex = 0;", "re.lastIndex = 0",
     "带 g 标志的正则是“有状态”的：上次 exec 停在哪，这次就从哪继续。复用前不归零，第二次高亮就会错乱——这是高亮器最常见的隐性 bug"),
    (EDITOR_JS, "function esc(s)", "function esc(s)",
     "HTML 转义顺序：& 最先。如果先替换 <，第一次产生的 &lt; 里的 & 会被二次转义成 &amp;lt;"),
    (EDITOR_JS, 'script[type="text/plain"]', 'script[type="text/plain"]',
     "用不执行的 script 标签当数据仓库：浏览器不渲染也不执行它，把源码原样存在 DOM 里，比塞进 JS 字符串干净——无需转义引号和反斜杠"),
    (EDITOR_JS, "localStorage.setItem", "localStorage.setItem",
     "“自动保存”的实现就一行：每次输入都写 localStorage，写入成本远低于按键频率，不需要防抖"),
    (EDITOR_JS, "gutter.scrollTop = editor.scrollTop", "gutter.scrollTop = ...",
     "行号列 overflow:hidden 隐藏滚动条，由编辑区的 scroll 事件单向驱动。单向同步避免双向绑定造成的抖动循环"),
    (EDITOR_JS, 'e.key === "Tab"', 'e.key === "Tab"',
     "拦截 Tab 键插入两个空格。preventDefault 是关键，否则焦点会跳到下一个控件， textarea 就“打不了字”了"),
    (EDITOR_JS, "URL.revokeObjectURL", "URL.revokeObjectURL(a.href)",
     "下载完成后立刻释放 Blob URL。不释放的话，每次下载都在内存里漏一个对象"),
]

FLOW_DIAGRAM = """<div class="codehilite"><pre><span></span><code>① 修改源码
   site/10.html（本章页面）或任意章节页
   ── 也可以先在本章编辑器里改出草稿，满意后再抄回仓库
        │
        ▼
② 重新构建（本章专用）
   python3 build_chapter10.py
   ── 从三份带注释源码重新生成本章页面，
      保证"编辑器内容"与"源码清单"逐字节一致
        │
        ▼
③ 一键部署
   export CLOUDFLARE_API_TOKEN=xxx
   python3 deploy_pages.py
   ── 指纹 → 上传 → 装订，输出本次部署的专属预览 URL
        │
        ▼
④ 验收
   先打开返回的预览 URL 检查
   ── 每次部署有独立子域，验收不影响线上用户
        │
        ▼
⑤ 切生产
   main 分支部署自动成为生产版本
   https://java-sql-ai-tutorial.pages.dev</code></pre></div>"""

CHECK_CURL = """<div class="codehilite"><pre><span></span><code># ① 页面可访问
curl -s -o /dev/null -w "%{http_code}\\n" https://java-sql-ai-tutorial.pages.dev/10.html
# 期望输出：200

# ② 编辑器组件已渲染（可编辑的 textarea 存在）
curl -s https://java-sql-ai-tutorial.pages.dev/10.html | grep -c 'id="sce-code"'
# 期望输出：1

# ③ 三份源码以文本形式内嵌在页面里
curl -s https://java-sql-ai-tutorial.pages.dev/10.html | grep -o 'data-file="[^"]*"'
# 期望输出：data-file="worker.js" / deploy.py / editor.js 各一行

# ④ 详尽注释确实存在（统计注释与讲解标记）
curl -s https://java-sql-ai-tutorial.pages.dev/10.html | grep -c "讲解"
# 期望输出：大于 20</code></pre></div>"""


def build_page():
    tabs, data_blocks = build_editor_widget()
    import datetime
    stamp = datetime.date.today().isoformat()

    feat_table = """<table>
<thead><tr><th style="width:130px">功能</th><th>说明</th></tr></thead>
<tbody>
<tr><td><strong>多文件切换</strong></td><td>顶部标签页在 worker.js / deploy.py / editor.js 之间切换，每个文件独立保存草稿</td></tr>
<tr><td><strong>行号</strong></td><td>左侧行号列与内容纵向滚动严格同步（共用 13px/1.55 行高保证逐行对齐）</td></tr>
<tr><td><strong>光标位置</strong></td><td>状态栏实时显示"行 x，列 y"，随点击与键盘移动更新</td></tr>
<tr><td><strong>语法高亮预览</strong></td><td>一键在"可编辑纯文本"与"高亮渲染"两个视图间切换，预览内容实时跟随编辑</td></tr>
<tr><td><strong>自动保存</strong></td><td>每次按键都把当前文件写入 localStorage，刷新页面不丢；标题栏会标注"（含本地修改）"</td></tr>
<tr><td><strong>复制 / 下载</strong></td><td>一键复制全文，或把当前文件下载为 .js / .py</td></tr>
<tr><td><strong>重置</strong></td><td>清除本地修改，恢复本章原始源码</td></tr>
<tr><td><strong>Tab 缩进</strong></td><td>按 Tab 插入两个空格（而不是把焦点切走），符合真实编辑器的肌肉记忆</td></tr>
</tbody></table>"""

    how_list = """<ul>
<li><strong>数据来源</strong>：<code>&lt;script type="text/plain" data-file="..."&gt;</code>——浏览器不执行这种 script，正好当"嵌入页面的纯文本文件仓库"用，避免把源码塞进 JS 字符串里的转义地狱。全页共 3 个数据块、1 个可执行脚本。</li>
<li><strong>高亮器</strong>：一条正则 + 四个捕获组（注释 &gt; 字符串 &gt; 数字 &gt; 关键字）。优先级顺序是关键——注释和字符串必须先于关键字匹配，否则字符串里的 <code>"function"</code> 会被误染色。</li>
<li><strong>状态复位</strong>：带 <code>g</code> 标志的正则对象是有状态的（<code>lastIndex</code>），复用前必须归零，这是高亮器最常见的隐性 bug。</li>
<li><strong>转义顺序</strong>：HTML 转义必须先替换 <code>&amp;</code>，再替换 <code>&lt;</code> 和 <code>&gt;</code>，否则会把第一次替换产生的实体再转义一次。</li>
<li><strong>滚动同步</strong>：行号列、编辑区、预览区三者共用 13px/1.55 的行高，保证每行严格对齐；scroll 事件单向驱动行号列，避免双向同步的抖动。</li>
<li><strong>本地保存</strong>：localStorage 以 <code>sce:文件名</code> 为键，一个文件一份草稿；重置即删键。</li>
</ul>"""

    srcbox_worker = build_srcbox(
        "worker.js", "js", WORKER_JS,
        "JavaScript · Cloudflare Worker · 运行在边缘节点",
        "真实文件是 <code>/workspace/worker_kv.js</code>（内容存 KV）。上表所列行为与线上完全一致；"
        "把上面的 <code>ROUTES</code> 表删掉一行，再访问对应路径就会得到 404——可以在编辑器里改了之后对照第 3 节的流程在本地跑起来验证。")
    srcbox_deploy = build_srcbox(
        "deploy.py", "py", DEPLOY_PY,
        "Python · 部署脚本 · 运行在开发机",
        "真实文件是 <code>/workspace/deploy_pages.py</code>。本章上线用的就是同一套"
        "「指纹 → 上传 → 装订」三步流程，只是把 requests 调用换成了等价的 API 直调。")
    srcbox_editor = build_srcbox(
        "editor.js", "js", EDITOR_JS,
        "JavaScript · 前端组件 · 运行在浏览器",
        "这一份清单就是本页上方编辑器的<strong>完整源码</strong>（共 " + str(nlines(EDITOR_JS)) +
        " 行）——你现在看到的编辑器行为，全部由这份代码驱动；"
        "它同时也原样嵌在本页 HTML 里（查看源代码可搜 <code>data-file=\"editor.js\"</code>）。")

    check_table = """<table>
<thead><tr><th style="width:48px">#</th><th style="width:150px">位置</th><th style="width:280px">怎么到达</th><th>应该看到</th></tr></thead>
<tbody>
<tr><td>1</td><td><strong>首页卡片</strong></td><td><a href="https://java-sql-ai-tutorial.pages.dev/">https://java-sql-ai-tutorial.pages.dev/</a></td><td>"第 10 章 · ✂️ 源码编辑与源码导读"卡片，点击进入本章</td></tr>
<tr><td>2</td><td><strong>全站导航</strong></td><td>任意章节页（01~09）顶部导航</td><td>"10 源码编辑"链接，点击直达本章</td></tr>
<tr><td>3</td><td><strong>交互式编辑器</strong></td><td><a href="#widget">/10.html#widget</a></td><td>三个文件标签页、行号列、可编辑文本、高亮预览、复制 / 下载 / 重置 / 光标位置</td></tr>
<tr><td>4</td><td><strong>worker.js 源码全文</strong></td><td><a href="#sec-worker">/10.html#sec-worker</a></td><td>带行号的边缘路由源码全文 + 逐行讲解表（7 条）</td></tr>
<tr><td>5</td><td><strong>deploy.py 源码全文</strong></td><td><a href="#sec-deploy">/10.html#sec-deploy</a></td><td>带行号的部署脚本源码全文 + 逐行讲解表（8 条）</td></tr>
<tr><td>6</td><td><strong>editor.js 源码全文</strong></td><td><a href="#sec-editor">/10.html#sec-editor</a></td><td>带行号的编辑器组件源码全文 + 逐行讲解表（8 条）</td></tr>
<tr><td>7</td><td><strong>网页源代码</strong></td><td>在 /10.html 上按 Ctrl+U（查看网页源代码）</td><td>三份源码以 <code>&lt;script type="text/plain"&gt;</code> 原文内嵌在 HTML 里，可搜索 <code>data-file="worker.js"</code> 定位</td></tr>
<tr><td>8</td><td><strong>命令行验证</strong></td><td>见下方 curl 命令</td><td>四条命令各自的期望输出</td></tr>
</tbody></table>"""

    page = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>10 源码编辑与源码导读 · Java · SQL · Python AI 教程</title>
<link rel="stylesheet" href="assets/style.css">
<style>{PAGE_CSS}</style>
</head>
<body>
<header class="topnav">
  <div class="brand">Java · SQL · Python AI 教程<small>从原理到实战</small></div>
  {NAV}
  <a class="src" href="https://github.com/user-unknowed/studying-for-building" target="_blank">📦 源码仓库</a>
</header>
<div class="layout">
  <aside class="sidebar">
    <h4>本节目录</h4>
    <ul>
<li><a href="#intro">0. 导读：为什么专门做一章"源码编辑"</a></li>
<li><a href="#editor">1. 交互式源码编辑器</a><ul>
<li><a href="#feat">1.1 功能一览</a></li>
<li><a href="#widget">1.2 编辑器（可直接编辑）</a></li>
<li><a href="#how">1.3 实现要点</a></li>
</ul>
</li>
<li><a href="#src">2. 本站源码全文导读（带详尽注释）</a><ul>
<li><a href="#sec-worker">2.1 worker.js —— 边缘路由</a></li>
<li><a href="#sec-deploy">2.2 deploy.py —— 部署脚本</a></li>
<li><a href="#sec-editor">2.3 editor.js —— 编辑器自身</a></li>
</ul>
</li>
<li><a href="#flow">3. 修改源码 → 重新上线：完整流程</a></li>
<li><a href="#check">4. 上线验证清单：在哪里看到这些源码</a></li>
</ul>
  </aside>
  <main class="content">
    <div class="meta" style="color:#b45309;font-weight:600">第 10 章 · ✂️</div>
    <h1 style="border-bottom:3px solid #b45309;padding-bottom:10px">源码编辑与源码导读</h1>
    <div class="meta">交互式源码编辑器 · Worker / 部署脚本 / 编辑器组件源码全文 · 逐行详尽注释</div>
    <h2 id="intro">0. 导读：为什么专门做一章"源码编辑"</h2>
<p>前九章都在教"怎么写代码"，这一章换个视角：<strong>怎么读、怎么改一个已经跑在线上的真实项目</strong>。材料不用虚构——就用本站自己的源码：</p>
<ul>
<li><strong>worker.js</strong> —— 在 Cloudflare 边缘节点上运行，决定 <code>/10.html</code> 这类请求返回什么；</li>
<li><strong>deploy.py</strong> —— 在开发机上运行，把 <code>site/</code> 目录一键发布上线；</li>
<li><strong>editor.js</strong> —— 在浏览器里运行，就是本章那个可以直接改代码的编辑器。</li>
</ul>
<p>三份源码恰好覆盖一个最小 Web 项目的三层：<strong>边缘路由层、发布流水线层、前端交互层</strong>。每份都是完整可运行的代码（构建时经过真实语法检查），并以两种形式同时呈现在本章：</p>
<ol>
<li>第 1 节的<strong>编辑器</strong>里，它们是可以直接修改的纯文本；</li>
<li>第 2 节的<strong>源码清单</strong>里，它们是带行号、带详尽注释的全文。</li>
</ol>
<p>两处内容<strong>逐字节一致</strong>——由同一个构建脚本（<code>build_chapter10.py</code>）从同一份源码字符串生成，不存在"演示代码与实际代码对不上"的问题。</p>
    <h2 id="editor">1. 交互式源码编辑器</h2>
<h3 id="feat">1.1 功能一览</h3>
{feat_table}
<h3 id="widget">1.2 编辑器（可直接编辑）</h3>
<p>下面这个编辑器就是本章新增的"源码编辑"能力本体——纯原生 JavaScript 实现，零依赖，完整源码见 <a href="#sec-editor">2.3 节</a>。随便改：加注释、删路由、改高亮规则，改坏了点"重置"即可恢复。</p>
<div class="sce" id="sce">
  <div class="sce-tabs">{tabs}<span class="sce-hint">改动自动保存在浏览器本地 · 重置可恢复</span></div>
  <div class="sce-toolbar">
    <button id="sce-copy" type="button">复制</button>
    <button id="sce-reset" type="button">重置</button>
    <button id="sce-download" type="button">下载</button>
    <button id="sce-toggle" type="button">高亮预览</button>
    <span class="sce-file" id="sce-filename"></span>
  </div>
  <div class="sce-stage">
    <div class="sce-gutter" id="sce-gutter" aria-hidden="true"></div>
    <textarea id="sce-code" spellcheck="false" wrap="off" aria-label="源码编辑区"></textarea>
    <pre class="sce-preview codehilite" id="sce-preview" tabindex="0"><code></code></pre>
  </div>
  <div class="sce-status">
    <span id="sce-pos">行 1，列 1</span>
    <span><span id="sce-lines">0</span> 行 · <span id="sce-chars">0</span> 字符</span>
    <span>高亮预览与编辑区内容实时同步</span>
  </div>
</div>
<h3 id="how">1.3 实现要点</h3>
{how_list}
    <h2 id="src">2. 本站源码全文导读（带详尽注释）</h2>
<p>三份源码一份在<strong>边缘</strong>跑、一份在<strong>开发机</strong>跑、一份在<strong>浏览器</strong>跑。下面每小节都是：完整源码清单（带行号）+ 逐行讲解表。行号由构建脚本从源码实时计算，与清单严格对齐。</p>
<h3 id="sec-worker">2.1 worker.js —— Cloudflare Worker 边缘路由</h3>
{srcbox_worker}
{explain_table(WORKER_ROWS)}
<h3 id="sec-deploy">2.2 deploy.py —— 一键部署脚本</h3>
{srcbox_deploy}
{explain_table(DEPLOY_ROWS)}
<h3 id="sec-editor">2.3 editor.js —— 本页编辑器组件自身</h3>
{srcbox_editor}
{explain_table(EDITOR_ROWS)}
    <h2 id="flow">3. 修改源码 → 重新上线：完整流程</h2>
<p>本章本身就是走完这条流程上线的：构建脚本生成页面 → 部署脚本发布 → 第 4 节的清单逐项核验。以后任何人想给本站加一章、改一处样式，照着走即可。</p>
{FLOW_DIAGRAM}
<p>几个容易踩的坑：</p>
<ul>
<li><strong>清单路径必须带前导斜杠</strong>（<code>/10.html</code> 而不是 <code>10.html</code>），这是 Pages 的硬性约定，写错会 404；</li>
<li><strong>资产 key 是内容指纹</strong>，所以只有真正改动过的文件才会重新上传，全量清单每次都要提交；</li>
<li><strong>预览 URL 先验收</strong>：每次部署有独立子域，确认无误再让它成为生产版本，线上用户全程无感。</li>
</ul>
    <h2 id="check">4. 上线验证清单：在哪里看到这些源码</h2>
<p>本章上线后，按下表逐项检查——每一项都对应"要求展示的源码"出现的一个"合适的地方"。</p>
{check_table}
<h3>4.1 命令行验证（curl 四连）</h3>
{CHECK_CURL}
<blockquote>
<p>提示：Pages 每次新部署会自动清除 pages.dev 域名的边缘缓存；若浏览器仍显示旧版，强制刷新（Ctrl+Shift+R）即可。<br>
本章构建记录：构建时间 {stamp} · 生成脚本 <code>build_chapter10.py</code> · 编辑器内容与源码清单来自同一份源码字符串（逐字节一致）。</p>
</blockquote>
    <div class="pager"><a href="09.html"><div class="dir">← 上一章</div><div class="ttl">华为ICT大赛·网络赛道备赛实战</div></a><a href="index.html"><div class="dir" style="text-align:right">返回首页 →</div><div class="ttl" style="text-align:right">Java · SQL · Python AI 教程</div></a></div>
  </main>
</div>
{data_blocks}
<script>
{EDITOR_JS}</script>
</body>
</html>
"""
    return page

# ════════════════════════════════════════════════════════════════════
# 五、注册到全站导航（幂等）
# ════════════════════════════════════════════════════════════════════

NAV_09 = '<a href="09.html" class="">09 华为ICT大赛·网络</a>'
NAV_10 = '<a href="10.html" class="">10 源码编辑</a>'
CARD_10 = ('<a class="card" href="10.html" style="--accent:#b45309">'
           '<div class="num">第 10 章 · ✂️</div>'
           '<div class="ttl">源码编辑与源码导读</div>'
           '<div class="sub">交互式编辑器 · Worker/部署脚本/编辑器源码全文 · 逐行注释</div>'
           '<div class="bar" style="background:#b45309"></div></a>')

def add_nav_links(path):
    """在页面顶部导航的 </nav> 前补齐缺失的章节链接（幂等）。

    历史遗留：01~08 章构建时第 09 章尚未存在，导航里没有 09 链接，
    这里一并补上，让全站导航统一到 01~10。
    """
    with open(path, encoding="utf-8") as f:
        s = f.read()
    m = re.search(r"<nav>.*?</nav>", s, re.S)
    if not m:
        raise SystemExit(f"[FAIL] {path}: 未找到 <nav>")
    nav = m.group(0)
    if 'href="10.html"' in nav:
        print(f"  [skip] {os.path.basename(path)} 导航已含 10.html 链接")
        return False
    add = ""
    if 'href="09.html"' not in nav:
        add += NAV_09
    add += NAV_10
    new_nav = nav.replace("</nav>", add + "</nav>")
    s = s[:m.start()] + new_nav + s[m.end():]
    with open(path, "w", encoding="utf-8") as f:
        f.write(s)
    fixed = "09+" if NAV_09 in add else ""
    print(f"  [ok]   {os.path.basename(path)} 导航已追加 {fixed}10 链接")
    return True

def patch_snippets(path, replacements):
    with open(path, encoding="utf-8") as f:
        s = f.read()
    changed = False
    for old, new in replacements:
        if old in s:
            s = s.replace(old, new)
            changed = True
    if changed:
        with open(path, "w", encoding="utf-8") as f:
            f.write(s)
    return changed

def register_nav():
    # 01 ~ 09 章：导航补齐（09 缺失的一并补上）
    for i in range(1, 10):
        add_nav_links(f"{SITE}/{i:02d}.html")
    # 首页：导航 + hero 文案 + 卡片
    add_nav_links(f"{SITE}/index.html")
    ok = patch_snippets(f"{SITE}/index.html", [
        ("9 个模块 · 从语言原理到工业实战 · 持续更新中",
         "10 个模块 · 从语言原理到工业实战 · 持续更新中"),
        ('<div class="bar" style="background:#0d9488"></div></a>\n  </div>',
         '<div class="bar" style="background:#0d9488"></div></a>' + CARD_10 + '\n  </div>'),
    ])
    print(f"  [{'ok' if ok else 'skip'}] index.html hero 文案 / 第 10 章卡片")
    # 09 章：翻页器加"下一章 → 第 10 章"
    ok = patch_snippets(f"{SITE}/09.html", [
        ('<div class="pager"><a href="08.html"><div class="dir">← 上一章</div>'
         '<div class="ttl">Python 与 AI 大模型：从原理到 Transformer</div></a></div>',
         '<div class="pager"><a href="08.html"><div class="dir">← 上一章</div>'
         '<div class="ttl">Python 与 AI 大模型：从原理到 Transformer</div></a>'
         '<a href="10.html"><div class="dir" style="text-align:right">下一章 →</div>'
         '<div class="ttl" style="text-align:right">源码编辑与源码导读</div></a></div>'),
    ])
    print(f"  [{'ok' if ok else 'skip'}] 09.html 翻页器已加\"下一章\"链接")

# ════════════════════════════════════════════════════════════════════
# 六、主流程
# ════════════════════════════════════════════════════════════════════

def main():
    print("① 源码语法检查")
    syntax_check()
    print("② 生成 site/10.html")
    page = build_page()
    for name, _, src, _ in SOURCES:
        assert f'data-file="{name}"' in page
        # 编辑器数据块中必须能找到源码原文的首行（保证逐字节一致地嵌入了）
        first_line = src.lstrip("\n").splitlines()[0]
        assert first_line in page, f"{name} 源码未嵌入"
    out = f"{SITE}/10.html"
    with open(out, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"  [ok] 写入 {out}（{len(page.encode('utf-8')):,} 字节）")
    print("③ 注册到全站导航 / 首页卡片 / 翻页器")
    register_nav()
    print("完成。")

if __name__ == "__main__":
    main()
