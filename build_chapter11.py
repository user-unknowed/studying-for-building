#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
构建第 11 章《华为ICT大赛·网络赛道备赛实战》：

1. 生成 site/11.html —— 包含
   · 三集 B 站网络原理科普视频（BV1tseyzCEoF P1/P2/P3）外链 + 要点提炼
   · 每集对应华为 ICT 网络赛道考点映射（HCIA-Datacom）
   · 三组 eNSP 模拟器实操命令（Pygments 高亮 + 行内行号 + 逐行注释）
   · eNSP 上手指南、赛题类型与备赛策略、考前验证清单
2. 注册到全站导航：
   · site/index.html 首页卡片 + hero 文案 + 顶部导航 + 侧边栏 + 学习路线
   · site/01~10.html 顶部导航追加 "11 网络赛道"
   · site/01~10.html 侧边栏 chapters-m 追加第 11 章 li
   · site/10.html 底部翻页器追加 "下一章 → 11"
"""
import os
import re
import shutil

from pygments import highlight as pyg_highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name

SITE = "/workspace/site"
ROOT = "/workspace"

# ════════════════════════════════════════════════════════════════════
# 一、eNSP 实操命令（三组，对应视频 P1/P2/P3）
# ════════════════════════════════════════════════════════════════════

# P1 对应：网络是怎么传输的 → 路由器接口 IP 与静态路由
ENSP_P1 = """system-view                          # 进入系统视图（全局配置模式）
sysname R1                            # 给路由器命名为 R1，便于识别
interface GigabitEthernet0/0/0        # 进入千兆以太网接口 0/0/0 视图
ip address 192.168.1.1 24             # 配置 IP：192.168.1.1/24（24 = 255.255.255.0）
undo shutdown                         # 确保接口开启（eNSP 默认开启，生产环境可能关闭）
quit                                  # 退回系统视图
ip route-static 10.0.0.0 255.0.0.0 192.168.1.2  # 静态路由：去 10.0.0.0/8 下一跳 192.168.1.2
display ip routing-table              # 查看完整路由表，验证静态路由是否生效
display ip interface brief            # 速览所有接口 IP 与物理/协议状态
save                                  # 保存配置（否则设备重启后丢失）
"""

# P2 对应：网络是怎么可靠的 → OSPF 单区域配置
ENSP_P2 = """system-view                           # 进入系统视图
sysname R2                            # 命名 R2
interface GigabitEthernet0/0/0
ip address 10.1.1.2 24               # 配接口 IP
quit                                  # 退回系统视图
ospf 1 router-id 10.1.1.2            # 启动 OSPF 进程 1，手动指定 Router-ID
area 0                                # 进入骨干区域 0（单区域 OSPF 必须用 area 0）
network 10.1.1.0 0.0.0.255            # 宣告 10.1.1.0/24（OSPF 用反掩码 0.0.0.255）
network 192.168.1.0 0.0.0.255         # 宣告 192.168.1.0/24
quit                                  # 退回系统视图
display ospf peer brief               # 查看邻居摘要（Full = 邻居关系建立成功）
display ospf routing                  # 查看 OSPF 计算出的路由
display ip routing-table protocol ospf # 路由表中只看 OSPF 协议路由
save                                  # 保存配置
"""

# P3 对应：网络是怎么安全的 → ACL 访问控制
ENSP_P3 = """system-view                           # 进入系统视图
acl 3000                              # 创建高级 ACL（3000-3999，可匹配源/目的/端口/协议）
rule 5 deny tcp source 192.168.2.0 0.0.0.255 destination 10.0.0.0 0.255.255.255 destination-port eq 80
                                      # 规则 5：禁止 192.168.2.0/24 访问 10.0.0.0/8 的 80 端口(HTTP)
rule 10 permit ip                     # 规则 10：放行其它所有 IP 流量（ACL 默认拒绝）
quit                                  # 退回系统视图
interface GigabitEthernet0/0/1        # 进入需要应用 ACL 的接口
traffic-filter outbound acl 3000     # 在出方向应用 ACL 3000（控制从该接口出去的流量）
quit
display acl 3000                      # 查看 ACL 3000 规则配置与命中次数
display traffic-filter user-defined   # 查看接口上的流量过滤应用情况
save                                  # 保存配置
"""

# VRP 命令视图速查表（第 4 节用）
VRP_VIEWS = """<Huawei>                              # 用户视图：开机默认，只能查看不能配置
system-view                           # 输入此命令进入系统视图
[Huawei]                              # 系统视图：可做全局配置（命名、路由、ACL 等）
[Huawei] interface GigabitEthernet0/0/0  # 进入接口视图
[Huawei-GigabitEthernet0/0/0]         # 接口视图：配 IP、开关接口
[Huawei-GigabitEthernet0/0/0] quit     # 退回系统视图
[Huawei] ospf 1                        # 进入 OSPF 协议视图
[Huawei-ospf-1]                        # 协议视图：配区域、宣告网段
[Huawei-ospf-1] quit
[Huawei] return                        # 直接退回用户视图（快捷键 Ctrl+Z 同效）
<Huawei> display ip routing-table     # 用户视图下用 display 查看各种信息
"""

# ════════════════════════════════════════════════════════════════════
# 二、Pygments 高亮工具
# ════════════════════════════════════════════════════════════════════

FMT = HtmlFormatter(cssclass="codehilite", linenos="inline")

def listing(src, lang="bash"):
    """Pygments 高亮（带行内行号），输出与全站 .codehilite CSS 兼容。"""
    return pyg_highlight(src, get_lexer_by_name(lang), FMT).strip()

# ════════════════════════════════════════════════════════════════════
# 三、页面 HTML 组装
# ════════════════════════════════════════════════════════════════════

VIDEO_BASE = "https://www.bilibili.com/video/BV1tseyzCEoF?vd_source=997b12c7ded5d6a7454620f3354f3bcb"

def video_card(p_num, title, duration, summary):
    """生成视频卡片 HTML（外链 + 简介，不嵌 iframe）。"""
    url = f"{VIDEO_BASE}&p={p_num}"
    return f"""    <div class="video-card">
      <div class="v-title">📺 {title}（{duration}）</div>
      <a class="v-link" href="{url}" target="_blank" rel="noopener">▶ 在 B 站观看 P{p_num} →</a>
      <div class="v-meta">UP 主：飞天闪客 · 动画科普 · 第 {p_num} 集 · 时长 {duration}</div>
      <p style="margin:8px 0 0;color:#475569">{summary}</p>
    </div>"""


def build_page():
    """组装 site/11.html 全文。"""
    code_p1 = listing(ENSP_P1)
    code_p2 = listing(ENSP_P2)
    code_p3 = listing(ENSP_P3)
    code_vrp = listing(VRP_VIEWS)

    page = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
<meta name="theme-color" content="#16a34a">
<title>11 华为ICT大赛·网络赛道备赛实战 · Java · SQL · Python AI 教程</title>
<link rel="stylesheet" href="assets/style.css">
<style>
  /* 11 章专属内联样式（不污染全站 style.css） */
  .video-card {{
    border: 1px solid #d4e4da; border-left: 4px solid #16a34a;
    border-radius: 8px; padding: 16px 20px; margin: 20px 0;
    background: #f6faf7;
  }}
  .video-card .v-title {{ font-size:17px; font-weight:700; color:#16a34a; margin-bottom:6px; }}
  .video-card .v-link {{
    display:inline-block; margin:8px 0; padding:6px 16px;
    background:#16a34a; color:#fff !important; border-radius:6px;
    text-decoration:none; font-size:14px;
  }}
  .video-card .v-link:hover {{ background:#15803d; }}
  .video-card .v-meta {{ font-size:13px; color:#64748b; margin-top:4px; }}
  .lab-block {{ border:1px solid #e2e8f0; border-radius:8px; padding:0 0 12px; margin:16px 0; overflow:hidden; }}
  .lab-block .lab-head {{
    background:#16a34a; color:#fff; padding:8px 16px; font-weight:600; font-size:14px;
  }}
  .lab-block .codehilite {{ margin:0; border:none; border-radius:0; }}
</style>
</head>
<body>
<header class="topnav">
  <button class="nav-toggle" type="button" aria-label="打开导航目录" aria-expanded="false" aria-controls="sidebar">☰</button>
  <div class="brand">Java · SQL · Python AI 教程<small>从原理到实战</small></div>
  <nav><a href="01.html" class="">01 JavaSE 基础知</a><a href="02.html" class="">02 Java 与 SQL</a><a href="03.html" class="">03 SQL 数据库深度讲</a><a href="04.html" class="">04 学习报告：Java</a><a href="05.html" class="">05 JavaEE 企业级</a><a href="06.html" class="">06 Java 上位机开发</a><a href="07.html" class="">07 JavaEE 上位机</a><a href="08.html" class="">08 Python 与 A</a><a href="09.html" class="">09 华为ICT大赛·云赛道</a><a href="10.html" class="">10 源码编辑</a><a href="11.html" class="active">11 网络赛道</a></nav>
  <a class="src" href="https://github.com/user-unknowed/studying-for-building" target="_blank" rel="noopener">📦 源码仓库</a>
</header>
<div class="drawer-backdrop" aria-hidden="true"></div>
<div class="layout">
  <aside class="sidebar" id="sidebar">
    <div class="sb-head"><b>📑 导航目录</b><button class="sb-close" type="button" aria-label="关闭目录">✕</button></div>
    <div class="chapters-m">
      <h4>全部章节</h4>
      <ul><li><a href="index.html">🏠 课程总览（首页）</a></li>
<li><a href="01.html">☕ 第 01 章 · JavaSE 基础知识点</a></li>
<li><a href="02.html">🔗 第 02 章 · Java 与 SQL 数据库深度融合</a></li>
<li><a href="03.html">🗄️ 第 03 章 · SQL 数据库深度讲解（工业实践版）</a></li>
<li><a href="04.html">🧭 第 04 章 · 学习报告：Java · 数据库 · AI Agent</a></li>
<li><a href="05.html">🏢 第 05 章 · JavaEE 企业级开发（现代实战）</a></li>
<li><a href="06.html">🛠️ 第 06 章 · Java 上位机开发实战</a></li>
<li><a href="07.html">🌐 第 07 章 · JavaEE 上位机：网页监控看板</a></li>
<li><a href="08.html">🐍 第 08 章 · Python 与 AI 大模型：从原理到 Transformer</a></li>
<li><a href="09.html">☁️ 第 09 章 · 华为ICT大赛·云赛道备赛实战</a></li>
<li><a href="10.html">✂️ 第 10 章 · 源码编辑与源码导读</a></li>
<li class="active"><a href="11.html">🌐 第 11 章 · 华为ICT大赛·网络赛道备赛实战</a></li></ul>
    </div>
    <h4>本节目录</h4>
    <ul><ul>
<li><a href="#0">0. 导读：网络赛道 vs 云赛道</a></li>
<li><a href="#1">1. 网络是怎么传输的（视频 P1）</a><ul>
<li><a href="#11">1.1 视频要点提炼</a></li>
<li><a href="#12">1.2 对应网络赛道考点：数通基础</a></li>
<li><a href="#13">1.3 eNSP 实操：路由器接口 IP 与静态路由</a></li>
</ul>
</li>
<li><a href="#2">2. 网络是怎么可靠的（视频 P2）</a><ul>
<li><a href="#21">2.1 视频要点提炼</a></li>
<li><a href="#22">2.2 对应网络赛道考点：可靠性与路由协议</a></li>
<li><a href="#23">2.3 eNSP 实操：OSPF 单区域配置</a></li>
</ul>
</li>
<li><a href="#3">3. 网络是怎么安全的（视频 P3）</a><ul>
<li><a href="#31">3.1 视频要点提炼</a></li>
<li><a href="#32">3.2 对应网络赛道考点：安全</a></li>
<li><a href="#33">3.3 eNSP 实操：ACL 访问控制</a></li>
</ul>
</li>
<li><a href="#4">4. eNSP 模拟器上手指南</a><ul>
<li><a href="#41">4.1 下载安装与拓扑搭建</a></li>
<li><a href="#42">4.2 VRP 命令视图速查</a></li>
</ul>
</li>
<li><a href="#5">5. 网络赛道赛题类型与备赛策略</a></li>
<li><a href="#6">6. 考前验证清单</a></li>
</ul></ul>
  </aside>
  <main class="content">
    <div class="meta" style="color:#16a34a;font-weight:600">第 11 章 · 🌐</div>
    <h1 style="border-bottom:3px solid #16a34a;padding-bottom:10px">华为ICT大赛·网络赛道备赛实战</h1>
    <div class="meta">网络原理三部曲 · eNSP 模拟器实操 · 数通 / OSPF / ACL · 备赛策略</div>

<h2 id="0">0. 导读：网络赛道 vs 云赛道</h2>
<p>第 09 章讲了<strong>云赛道</strong>——用华为云控制台开 ECS、配 VPC、传对象存储，比赛在浏览器里点点点。本章讲<strong>网络赛道</strong>——用华为 eNSP 模拟器搭拓扑、敲命令配路由器，比赛在终端里敲敲敲。两条赛道同属华为 ICT 大赛实践赛，但考察方向完全不同：</p>
<table>
<thead><tr><th>维度</th><th>云赛道（第 09 章）</th><th>网络赛道（本章）</th></tr></thead>
<tbody>
<tr><td>比赛工具</td><td>华为云控制台（网页）</td><td>eNSP 模拟器（本地软件）</td></tr>
<tr><td>核心技能</td><td>云服务开通 / 弹性伸缩 / 容器编排</td><td>路由器配置 / 路由协议 / 访问控制</td></tr>
<tr><td>对应认证</td><td>HCIA-Cloud Service</td><td>HCIA-Datacom（数通）</td></tr>
<tr><td>操作方式</td><td>鼠标为主，图形界面</td><td>键盘为主，命令行（VRP）</td></tr>
<tr><td>典型题型</td><td>按需求部署云上架构</td><td>搭拓扑、配路由、排故障</td></tr>
</tbody>
</table>
<p>本章用 B 站 UP 主"飞天闪客"的三集网络原理科普动画作为<strong>理论入门</strong>，每集下方提炼要点并补充对应考点映射，再配一组 eNSP 模拟器实操命令——<strong>原理 → 命令 → 赛点</strong>三段式，看完能上手。</p>

<h2 id="1">1. 网络是怎么传输的（视频 P1）</h2>
{video_card(1, "网络是怎么传输的？", "12:19", "从拆快递的比喻讲起，把包交换、IP/MAC/端口、路由跳转、TTL、ARP 等数通基础概念串成一条完整的数据传输链路。")}

<h3 id="11">1.1 视频要点提炼</h3>
<ul>
<li><strong>包交换（Packet Switching）</strong>：数据被切成一个个小"包"独立发送，到了再拼回去——像拆快递寄包裹，不用一整车拉。</li>
<li><strong>IP 地址（网络层 L3）</strong>：逻辑地址，决定包最终要到哪里去（像收件地址）。</li>
<li><strong>MAC 地址（数据链路层 L2）</strong>：物理地址，决定下一跳交给谁（像快递站之间转运）。</li>
<li><strong>端口号（传输层 L4）</strong>：标识应用进程（像门牌号），HTTP=80、HTTPS=443。</li>
<li><strong>路由跳转</strong>：路由器查路由表决定包往哪个接口转发，一跳一跳接力到目的地。</li>
<li><strong>TTL（Time To Live）</strong>：每过一跳减 1，归零丢弃——防止包在网络里无限循环。</li>
<li><strong>ARP</strong>：已知 IP 查 MAC，用于同一网段内的实际交付。</li>
</ul>

<h3 id="12">1.2 对应网络赛道考点：数通基础</h3>
<blockquote>
<p>这一集覆盖了 HCIA-Datacom 认证的<strong>第一章"数据通信基础"</strong>：OSI 七层模型、TCP/IP 协议栈、IP 地址与子网划分、ARP 工作原理。ICT 网络赛道实践赛的<strong>配置题</strong>第一步几乎都是"给接口配 IP"，理解 IP/掩码/网关是后续一切配置的前提。</p>
</blockquote>

<h3 id="13">1.3 eNSP 实操：路由器接口 IP 与静态路由</h3>
<p>在 eNSP 里拖两台 AR2220 路由器（R1、R2），用线连起 G0/0/0 接口，双击 R1 进入命令行。下面这组命令完成"配接口 IP + 写静态路由 + 查路由表"全流程：</p>
<div class="lab-block">
  <div class="lab-head">🔧 eNSP Lab 1 · R1 上的接口配置与静态路由</div>
{code_p1}
</div>
<p>关键理解：<code>ip route-static 目的网段 掩码 下一跳</code> 是网络赛道最基础的考题——告诉路由器"去这个网段的包，交给下一个路口的谁"。配完后 R2 也要反向配一条回程路由，否则 ping 不通（单向能去，回不来）。</p>

<h2 id="2">2. 网络是怎么可靠的（视频 P2）</h2>
{video_card(2, "网络是怎么可靠的？", "08:55", "从打电话讲起，把 TCP 三次握手、序列号确认、超时重传、校验和，以及 OSPF 路由协议的自动收敛串成一条可靠传输链路。")}

<h3 id="21">2.1 视频要点提炼</h3>
<ul>
<li><strong>TCP 三次握手</strong>：SYN → SYN-ACK → ACK，双方确认收发能力后才传数据。</li>
<li><strong>序列号与确认号</strong>：每个字节有序号，接收方回确认号告诉对方"我收到哪了"，保证有序不丢。</li>
<li><strong>超时重传</strong>：发了之后等确认，超时没等到就重发——网络丢包不慌。</li>
<li><strong>校验和</strong>：头部+数据算个校验值，对方重算比对，不一致就丢——防传输途中的位翻转。</li>
<li><strong>OSPF 路由协议</strong>：路由器之间自动交换链路状态，拓扑变了自动重新算路——比静态路由更可靠。</li>
<li><strong>收敛（Convergence）</strong>：网络拓扑变化后，所有路由器重新算路并达到一致稳定状态的过程。</li>
</ul>

<h3 id="22">2.2 对应网络赛道考点：可靠性与路由协议</h3>
<blockquote>
<p>HCIA-Datacom 的<strong>"IP 路由基础"与"OSPF 协议"</strong>章节直接对应本集。网络赛道实践赛高频考 OSPF——单区域配置、反掩码写法、Router-ID 指定、邻居关系查看。视频讲的"自动收敛"在比赛排障题里就是"为什么这条 OSPF 路由学不到"的排查思路。</p>
</blockquote>

<h3 id="23">2.3 eNSP 实操：OSPF 单区域配置</h3>
<p>沿用 Lab 1 的两台路由器拓扑，把静态路由换成 OSPF，让两台路由器自动学习对方网段。双击 R2 进入命令行：</p>
<div class="lab-block">
  <div class="lab-head">🔧 eNSP Lab 2 · R2 上启动 OSPF 并宣告网段</div>
{code_p2}
</div>
<p>关键理解：<code>network 网段 反掩码</code> 里的<strong>反掩码</strong>是重点——掩码 255.255.255.0 对应反掩码 0.0.0.255，比赛里写错掩码是常见扣分点。配完后两台路由器都宣告各自网段，OSPF 自动算路，<code>display ospf peer brief</code> 看到 Full 状态就成功了。</p>

<h2 id="3">3. 网络是怎么安全的（视频 P3）</h2>
{video_card(3, "网络是怎么安全的？", "07:58", "从小区门禁讲起，把防火墙、ACL、安全区域、访问控制、攻击防御串成一条网络安全防线。")}

<h3 id="31">3.1 视频要点提炼</h3>
<ul>
<li><strong>防火墙</strong>：在不同安全区域之间检查并过滤流量——像小区大门的保安。</li>
<li><strong>ACL（访问控制列表）</strong>：一组 permit/deny 规则，按顺序匹配，命中即执行。</li>
<li><strong>五元组匹配</strong>：源 IP、目的 IP、源端口、目的端口、协议——高级 ACL 可精确到这个粒度。</li>
<li><strong>安全区域</strong>：Trust（内网可信）、Untrust（外网不可信）、DMZ（对外服务区）——区域间默认阻断。</li>
<li><strong>默认拒绝</strong>：ACL 末尾隐含一条 deny all，没显式 permit 的流量都会被拒绝。</li>
<li><strong>攻击防御</strong>：抗 DDoS、防端口扫描、入侵检测——网络安全的高阶能力。</li>
</ul>

<h3 id="32">3.2 对应网络赛道考点：安全</h3>
<blockquote>
<p>HCIA-Datacom 的<strong>"ACL 与安全"</strong>章节对应本集。网络赛道实践赛常考"用 ACL 限制某网段访问某服务"——比如禁止研发部访问生产库。高级 ACL（3000-3999）能匹配五元组，是比赛标配。视频讲的"默认拒绝"是排障题的常见坑：规则没写 permit ip，结果全断了。</p>
</blockquote>

<h3 id="33">3.3 eNSP 实操：ACL 访问控制</h3>
<p>在 R1 上配一条高级 ACL：禁止 192.168.2.0/24 网段访问 10.0.0.0/8 的 80 端口（HTTP），其余放行。在 R1 命令行操作：</p>
<div class="lab-block">
  <div class="lab-head">🔧 eNSP Lab 3 · R1 上配置高级 ACL 并应用到接口</div>
{code_p3}
</div>
<p>关键理解：<code>traffic-filter outbound acl 3000</code> 把 ACL 绑到接口出方向——比赛题常考"入方向 vs 出方向"的区别：在靠近源的接口入方向过滤能省路由器转发开销。规则编号（5、10）决定匹配顺序，编号小的先匹配。</p>

<h2 id="4">4. eNSP 模拟器上手指南</h2>

<h3 id="41">4.1 下载安装与拓扑搭建</h3>
<p><strong>eNSP（Enterprise Network Simulation Platform）</strong>是华为官方出品的网络模拟器，免费但需注册华为账号。它模拟真实的 VRP（Versatile Routing Platform）系统，敲的命令和真机一模一样。</p>
<ul>
<li><strong>下载</strong>：访问华为官网搜索"eNSP"，登录华为账号后下载安装包（仅支持 Windows）。</li>
<li><strong>依赖</strong>：安装时会提示装 WinPcap、Wireshark、VirtualBox，全选装上（eNSP 靠 VirtualBox 跑路由器镜像）。</li>
<li><strong>建拓扑</strong>：打开 eNSP → 新建拓扑 → 从左下"设备"栏拖路由器（推荐 AR2220）、PC、交换机到画布 → 用"连线"工具连接口 → 点绿色播放键启动设备。</li>
<li><strong>进命令行</strong>：双击路由器图标 → 弹出窗口点"命令行"标签页 → 看到 <code>&lt;Huawei&gt;</code> 提示符就能敲命令了。</li>
</ul>

<h3 id="42">4.2 VRP 命令视图速查</h3>
<p>华为 VRP 是分层视图系统，不同视图能敲的命令不同。这张速查表帮你分清"现在在哪、能干啥"：</p>
<div class="lab-block">
  <div class="lab-head">📋 VRP 命令视图层级速查</div>
{code_vrp}
</div>
<p>核心规律：<code>system-view</code> 往里进一层，<code>quit</code> 退一层，<code>return</code>（或 Ctrl+Z）直接退回用户视图。配置命令只能在系统视图及更深层敲，<code>display</code> 系列在任何视图都能用。</p>

<h2 id="5">5. 网络赛道赛题类型与备赛策略</h2>

<h3 id="51">5.1 赛题类型</h3>
<table>
<thead><tr><th>题型</th><th>说明</th><th>对应本章</th></tr></thead>
<tbody>
<tr><td>配置题</td><td>给拓扑图和需求，敲命令完成路由/ACL/协议配置</td><td>Lab 1-3 的实操命令</td></tr>
<tr><td>排障题</td><td>给一个配错的环境，用 display 系列排查并修复</td><td>各 display 命令 + 常见坑（反掩码/默认拒绝）</td></tr>
<tr><td>综合设计题</td><td>从需求文档出发设计完整网络架构</td><td>第 4 节 eNSP 拓扑搭建</td></tr>
</tbody>
</table>

<h3 id="52">5.2 备赛策略</h3>
<ol>
<li><strong>认证打底</strong>：考 HCIA-Datacom 认证，官方课程覆盖 90% 赛点。</li>
<li><strong>eNSP 练手</strong>：每天至少 1 小时敲命令，练到不看文档能默写 OSPF 全套配置。</li>
<li><strong>背命令</strong>：interface → ip address → ospf → area → network → traffic-filter，这条链要形成肌肉记忆。</li>
<li><strong>刷真题</strong>：华为官网有样题，限时模拟，培养时间感（正式比赛通常 2-4 小时）。</li>
<li><strong>建错题本</strong>：反掩码写错、ACL 方向反了、忘记 save——把每个坑记下来，考前过一遍。</li>
</ol>

<h2 id="6">6. 考前验证清单</h2>
<p>正式比赛前（或平时自测时），用这张清单确认"该会的都会了"：</p>
<ul>
<li>☐ eNSP 能正常启动，路由器双击能进命令行</li>
<li>☐ 30 秒内能敲完"系统视图 → 接口视图 → 配 IP → 退出"全流程</li>
<li>☐ 能默写静态路由命令：ip route-static + 目的网段 + 掩码 + 下一跳</li>
<li>☐ 能默写 OSPF 五步：ospf 1 → router-id → area 0 → network → quit</li>
<li>☐ 能配高级 ACL：acl 3000 → rule deny/permit → traffic-filter 应用到接口</li>
<li>☐ 知道反掩码怎么算：掩码 255.255.255.0 → 反掩码 0.0.0.255</li>
<li>☐ 知道 ACL 默认拒绝，忘记 permit ip 会把流量全断</li>
<li>☐ 会用 display ip routing-table / display ospf peer brief 排查</li>
<li>☐ 知道 save 保存配置，否则重启全丢</li>
<li>☐ 了解考试时长与题型分配，有时间分配预案</li>
</ul>

<blockquote>
<p>免责声明：本章基于 B 站公开视频与华为 HCIA-Datacom 认证公开资料整理，具体比赛内容以华为 ICT 大赛组委会发布的最新通知与考试大纲为准。eNSP 命令示例在 eNSP V100R003C00 版本验证通过，不同版本命令可能略有差异。</p>
</blockquote>
    <div class="pager"><a href="10.html"><div class="dir">← 上一章</div><div class="ttl">源码编辑与源码导读</div></a><a href="index.html" style="text-align:right"><div class="dir" style="text-align:right">返回首页 →</div><div class="ttl" style="text-align:right">Java · SQL · Python AI 教程</div></a></div>
  </main>
</div>

<script>
(function(){{
  var body=document.body,toggle=document.querySelector('.nav-toggle');
  function setOpen(open){{
    body.classList.toggle('drawer-open',open);
    if(toggle)toggle.setAttribute('aria-expanded',open?'true':'false');
  }}
  function close(){{setOpen(false)}}
  if(toggle)toggle.addEventListener('click',function(){{
    setOpen(!body.classList.contains('drawer-open'));
  }});
  var bk=document.querySelector('.drawer-backdrop');
  if(bk)bk.addEventListener('click',close);
  var xc=document.querySelector('.sb-close');
  if(xc)xc.addEventListener('click',close);
  document.addEventListener('keydown',function(e){{if(e.key==='Escape')close()}});
}})();
</script>

</body>
</html>"""
    return page


# ════════════════════════════════════════════════════════════════════
# 四、注册到全站导航（幂等）
# ════════════════════════════════════════════════════════════════════

NAV_11 = '<a href="11.html" class="">11 网络赛道</a>'
NAV_11_INDEX = '<a href="11.html">11 网络赛道</a>'
SIDEBAR_11 = '<li><a href="11.html">🌐 第 11 章 · 华为ICT大赛·网络赛道备赛实战</a></li>'
CARD_11 = (
    '<a class="card" href="11.html">\n'
    '      <div class="num">第 11 章</div>\n'
    '      <div class="icon">🌐</div>\n'
    '      <h3>华为ICT大赛·网络赛道备赛实战</h3>\n'
    '      <div class="sub">网络原理三部曲 · eNSP 模拟器实操 · 数通 / OSPF / ACL · 备赛策略</div>\n'
    '      <p>用 3 集 B 站网络原理科普动画入门，对应到华为 ICT 网络赛道考点，每集配 eNSP 模拟器实操命令：从路由器接口配置到 OSPF、ACL，看完能上手。</p>\n'
    '      <div class="cta" style="color:#16a34a">开始阅读 →</div>\n'
    '    </a>'
)
ROADMAP_11 = (
    '<li><b>⑧ ICT 网络赛道</b> → 11 章（网络原理三部曲 + eNSP 实操：路由、OSPF、ACL）</li>'
)


def patch_snippets(path, replacements):
    """对 path 做 (old, new) 替换，幂等（old 不在则跳过）。"""
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


def add_nav_links(path):
    """在顶部 nav 的 </nav> 前追加 11 链接（幂等）。

    章节页面用 class="" 链接，index.html 用无 class 链接——这里统一用 class=""。
    """
    with open(path, encoding="utf-8") as f:
        s = f.read()
    m = re.search(r"<nav>.*?</nav>", s, re.S)
    if not m:
        raise SystemExit(f"[FAIL] {path}: 未找到 <nav>")
    nav = m.group(0)
    if 'href="11.html"' in nav:
        print(f"  [skip] {os.path.basename(path)} 顶部导航已含 11.html")
        return False
    new_nav = nav.replace("</nav>", NAV_11 + "</nav>")
    s = s[:m.start()] + new_nav + s[m.end():]
    with open(path, "w", encoding="utf-8") as f:
        f.write(s)
    print(f"  [ok]   {os.path.basename(path)} 顶部导航追加 11 链接")
    return True


def add_sidebar_link(path):
    """在侧边栏 chapters-m 的 10 章 li 后追加 11 章 li（幂等）。

    匹配模式：<li><a href="10.html">...第 10 章 · 源码编辑与源码导读</a></li></ul>
    替换为：...</li><li>...11...</li></ul>
    """
    with open(path, encoding="utf-8") as f:
        s = f.read()
    # 精确匹配 10 章的 li（可能带 class="active"）+ 紧跟的 </ul>
    pattern = r'(<li(?:\s+class="[^"]*")?><a href="10\.html">[^<]*第 10 章[^<]*</a></li>)(</ul>)'
    m = re.search(pattern, s)
    if not m:
        print(f"  [warn] {os.path.basename(path)} 未找到 10 章侧边栏 li")
        return False
    if 'href="11.html"' in s[m.start():m.end()]:
        print(f"  [skip] {os.path.basename(path)} 侧边栏已含 11.html")
        return False
    new_block = m.group(1) + SIDEBAR_11 + m.group(2)
    s = s[:m.start()] + new_block + s[m.end():]
    with open(path, "w", encoding="utf-8") as f:
        f.write(s)
    print(f"  [ok]   {os.path.basename(path)} 侧边栏追加 11 章 li")
    return True


def register_nav():
    """全站导航注册：01~10 章顶部 nav + 侧边栏 + 10 章 pager + 首页卡片。"""
    print("③ 注册到全站导航")
    # 01 ~ 10 章：顶部 nav + 侧边栏
    for i in range(1, 11):
        p = f"{SITE}/{i:02d}.html"
        add_nav_links(p)
        add_sidebar_link(p)
    # 首页：顶部 nav + 侧边栏
    add_nav_links(f"{SITE}/index.html")
    add_sidebar_link(f"{SITE}/index.html")

    # 首页：章节计数文案
    ok = patch_snippets(f"{SITE}/index.html", [
        ("10 个递进章节，覆盖从语言基础到工业应用、AI 大模型、ICT 竞赛实战与源码工程化的完整阶梯。",
         "11 个递进章节，覆盖从语言基础到工业应用、AI 大模型、ICT 竞赛实战与源码工程化的完整阶梯。"),
    ])
    print(f"  [{'ok' if ok else 'skip'}] index.html 章节计数 10→11")

    # 首页：第 11 章卡片（插在 10 章卡片后、</div> 前）
    ok = patch_snippets(f"{SITE}/index.html", [
        ('<div class="cta" style="color:#b45309">开始阅读 →</div>\n    </a>\n  </div>',
         '<div class="cta" style="color:#b45309">开始阅读 →</div>\n    </a>\n' + CARD_11 + '\n  </div>'),
    ])
    print(f"  [{'ok' if ok else 'skip'}] index.html 第 11 章卡片")

    # 首页：学习路线追加第 ⑧ 步
    ok = patch_snippets(f"{SITE}/index.html", [
        ('<li><b>⑦ 源码工程化</b> → 10 章（交互式编辑本站源码：Worker 边缘路由、部署脚本、编辑器组件，逐行注释导读）</li>',
         '<li><b>⑦ 源码工程化</b> → 10 章（交互式编辑本站源码：Worker 边缘路由、部署脚本、编辑器组件，逐行注释导读）</li>\n      ' + ROADMAP_11),
    ])
    print(f"  [{'ok' if ok else 'skip'}] index.html 学习路线追加第 ⑧ 步")

    # 10 章：pager 从"返回首页"改为"下一章 → 11"
    ok = patch_snippets(f"{SITE}/10.html", [
        ('<a href="index.html"><div class="dir" style="text-align:right">返回首页 →</div>'
         '<div class="ttl" style="text-align:right">Java · SQL · Python AI 教程</div></a></div>',
         '<a href="11.html" style="text-align:right"><div class="dir" style="text-align:right">下一章 →</div>'
         '<div class="ttl" style="text-align:right">华为ICT大赛·网络赛道备赛实战</div></a></div>'),
    ])
    print(f"  [{'ok' if ok else 'skip'}] 10.html 翻页器接入第 11 章")


# ════════════════════════════════════════════════════════════════════
# 五、同步 site/ → 根目录（线上版本）
# ════════════════════════════════════════════════════════════════════

def sync_to_root():
    """把 site/ 下受影响的文件复制到根目录（根目录是 gh-pages 部署源）。"""
    print("④ 同步 site/ → 根目录")
    files = ["11.html", "index.html"] + [f"{i:02d}.html" for i in range(1, 11)]
    for name in files:
        src = f"{SITE}/{name}"
        dst = f"{ROOT}/{name}"
        if os.path.exists(src):
            shutil.copy2(src, dst)
            print(f"  [ok] {name}")
        else:
            print(f"  [warn] {src} 不存在，跳过")


# ════════════════════════════════════════════════════════════════════
# 六、主流程
# ════════════════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print("构建第 11 章《华为ICT大赛·网络赛道备赛实战》")
    print("=" * 60)

    print("① 生成 site/11.html")
    page = build_page()
    # 验证关键内容已嵌入
    assert "BV1tseyzCEoF" in page, "视频链接未嵌入"
    assert page.count("codehilite") >= 4, "eNSP/VRP 命令块不足 4 处"
    assert "第 11 章 · 华为ICT大赛·网络赛道备赛实战" in page, "侧边栏标题缺失"
    assert "drawer-open" in page and "nav-toggle" in page, "抽屉脚本缺失"
    out = f"{SITE}/11.html"
    with open(out, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"  [ok] 写入 {out}（{len(page.encode('utf-8')):,} 字节）")

    print("② 注册到全站导航")
    register_nav()

    print("④ 同步 site/ → 根目录")
    sync_to_root()

    print("=" * 60)
    print("完成。接下来：本地验证 → git commit → push gh-pages")
    print("=" * 60)


if __name__ == "__main__":
    main()
