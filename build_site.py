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

# ── 模块元数据（与仓库 01~09 对应，顺序即学习顺序） ──
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
    {"num": "09", "file": "09-华为ICT大赛网络赛道-备赛实战教程.md",
     "title": "华为ICT大赛·网络赛道备赛实战",
     "subtitle": "赛制赛程 · 路由器与交换机原理 · VLAN/OSPF/STP · eNSP 实验 · 备赛策略",
     "accent": "#0d9488", "icon": "🏆",
     "desc": "华为ICT大赛实践赛网络赛道全攻略：从路由器/交换机通俗原理，到 VLAN、OSPF、STP 等核心协议配置，再到 eNSP 实验入门与分阶段备赛计划。"},
]