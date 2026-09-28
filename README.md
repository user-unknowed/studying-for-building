# Java · SQL · Python AI 系统化教程

> 从 JavaSE 基础 → Java×SQL 融合 → SQL 工业实践 → JavaEE 服务端 → 上位机（工业采集）→ Python 与 AI 大模型，递进式六阶梯。
> 所有演示代码均经过真实编译、运行、验证。

## 线上访问

**https://java-sql-ai-tutorial-b7y.pages.dev**

> 部署在 Cloudflare Pages，国内可通过边缘节点加速访问。

## 课程模块

| 章节 | 标题 | 关键词 |
|------|------|--------|
| 01 | [JavaSE 基础知识点](https://java-sql-ai-tutorial-b7y.pages.dev/01.html) | JVM · 语法 · OOP · 集合 · 并发 · IO · 现代语法 |
| 02 | [Java 与 SQL 数据库深度融合](https://java-sql-ai-tutorial-b7y.pages.dev/02.html) | JDBC · SQL 注入攻防 · 事务转账 · 批处理性能 |
| 03 | [SQL 数据库深度讲解（工业实践版）](https://java-sql-ai-tutorial-b7y.pages.dev/03.html) | 关系模型 · 窗口函数 · 索引 · 事务并发 · 架构前沿 |
| 04 | [学习报告：Java · 数据库 · AI Agent](https://java-sql-ai-tutorial-b7y.pages.dev/04.html) | 三大方向知识地图 · 2025-2026 动态 · 12 周计划 |
| 05 | [JavaEE 企业级开发（现代实战）](https://java-sql-ai-tutorial-b7y.pages.dev/05.html) | Servlet · DAO · 事务 · REST · 防超卖 · Spring Boot |
| 06 | [Java 上位机开发实战](https://java-sql-ai-tutorial-b7y.pages.dev/06.html) | 串口 · Modbus · 数据采集 · 入库 · 控制与报警 |
| 07 | [JavaEE 上位机：网页监控看板](https://java-sql-ai-tutorial-b7y.pages.dev/07.html) | Servlet · 嵌入式 Tomcat · REST · 零依赖 SVG 看板 |
| 08 | [Python 与 AI 大模型：从原理到 Transformer](https://java-sql-ai-tutorial-b7y.pages.dev/08.html) | 张量 · Autograd · 注意力 · GPU 并行 · 推理服务化 |

## 建议学习路线

1. **JavaSE 基础** → 01 章（字节码、类型陷阱、OOP、集合、并发、现代语法）
2. **Java × SQL 融合** → 02 章（JDBC、注入攻防、转账事务、批处理）
3. **SQL 工业实践** → 03 章（窗口函数、EXPLAIN、索引、MVCC）
4. **JavaEE 服务端** → 05 章（先原生 Jakarta EE，后 Spring Boot）
5. **上位机 / 工业采集** → 06、07 章（先桌面版，再网页版）
6. **Python 与 AI 大模型** → 08 章（张量、Autograd、手写 MiniGPT、GPU 并行、vLLM 服务化）

每一步遵循同一原则：**先读文档懂原理，再跑代码看真实结果**。

## 技术栈

- **Java**：JavaSE / JDBC / Jakarta EE / Spring Boot
- **SQL**：MySQL / PostgreSQL / 窗口函数 / 索引优化 / MVCC
- **Python**：PyTorch / NumPy / Transformer / vLLM
- **工业**：Modbus TCP/RTU / 串口通信 / 数据采集 / SVG 看板
- **部署**：Cloudflare Pages（边缘 CDN 加速 + 缓存策略）

## 部署架构

```
源码 (/workspace/site/)
  ├── index.html          # 首页
  ├── 01.html ~ 08.html   # 8 章教程
  ├── assets/style.css    # 样式
  └── _headers            # Cloudflare Pages 缓存规则
        │
        ▼
  wrangler pages deploy
        │
        ▼
  Cloudflare Pages (pages.dev)
  ├── 边缘 CDN 缓存（国内 PoP 节点）
  ├── HTML: 缓存 7 天 + SWR 30 天
  └── CSS/JS: 缓存 1 年 + immutable
```

详细架构说明和缓存原理请参考 [Wiki 文档](./WIKI.md)。

## 本地运行

```bash
# 克隆仓库
git clone https://github.com/user-unknowed/studying-for-building.git
cd studying-for-building/site

# 用任意静态文件服务器启动
python3 -m http.server 8080
# 浏览器打开 http://localhost:8080
```

## 关于

这是一个学习的地方，请勿用于商业用途。

可以看一下我的收藏夹：https://github.com/stars/user-unknowed/lists/good-things

里面有我收藏的项目和自己的一些笔记，你可以参考一下，也可以 fork 到自己的仓库里面。

然后如果有其他的问题和需求，请提 issue，我会尽快回复。
