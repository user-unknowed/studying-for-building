# Wiki — 部署架构与缓存加速原理

## 目录

- [1. 总体架构](#1-总体架构)
- [2. 为什么选择 Cloudflare Pages](#2-为什么选择-cloudflare-pages)
- [3. CDN 边缘缓存原理](#3-cdn-边缘缓存原理)
- [4. 缓存策略详解](#4-缓存策略详解)
- [5. 国内加速机制](#5-国内加速机制)
- [6. _headers 文件配置](#6-_headers-文件配置)
- [7. 部署流程](#7-部署流程)
- [8. 故障排查](#8-故障排查)

---

## 1. 总体架构

```
┌─────────────────────────────────────────────────────────────┐
│                        用户浏览器                            │
│   国内用户 (北京/上海/深圳)  ── DNS 解析 ──>  Cloudflare 边缘 PoP   │
└─────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────┐
│                  Cloudflare 边缘节点 (PoP)                   │
│                                                             │
│   ┌─────────────┐   ┌──────────────┐   ┌────────────────┐  │
│   │  CDN 缓存   │   │  TLS 终结    │   │  路由分发       │  │
│   │  (边缘存储) │   │  (SSL 证书)  │   │  (pages.dev)   │  │
│   └──────┬──────┘   └──────────────┘   └────────┬───────┘  │
│          │                                     │          │
│          ▼                                     ▼          │
│   ┌──────────────────────────────────────────────────────┐ │
│   │              缓存命中？                               │ │
│   │  是 → 直接返回缓存内容 (零回源)                       │ │
│   │  否 → 回源到 Pages 存储 → 缓存到边缘 → 返回用户       │ │
│   └──────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                                    │ (仅首次/缓存过期时)
                                    ▼
┌─────────────────────────────────────────────────────────────┐
│              Cloudflare Pages 存储 (源站)                    │
│                                                             │
│   site/                                                     │
│   ├── index.html        (6.9 KB)                           │
│   ├── 01.html ~ 08.html (8 章, 15~313 KB)                  │
│   ├── assets/style.css  (11 KB)                             │
│   └── _headers          (缓存规则)                          │
└─────────────────────────────────────────────────────────────┘
```

## 2. 为什么选择 Cloudflare Pages

### Workers vs Pages 对比

| 对比项 | Cloudflare Workers | Cloudflare Pages |
|--------|-------------------|------------------|
| 国内可达性 | `*.workers.dev` 常被 DNS 污染/TLS 阻断 | `*.pages.dev` 国内可达 |
| 静态文件服务 | 需嵌入 Worker 脚本 (gzip+base64) | 原生支持，直接上传 |
| 缓存控制 | 需在 Worker 代码中手动设置 | `_headers` 文件声明式配置 |
| 部署复杂度 | 高 (需构建嵌入脚本) | 低 (`wrangler pages deploy site`) |
| 构建集成 | 无 | 支持 Git 集成 / 直接上传 |
| 边缘缓存 | 需手动配置 `caches.default` | 内置 + `_headers` 增强 |

### 结论

对于纯静态教程网站，**Pages 是最优选择**：
- 部署简单：一行命令上传整个 `site/` 目录
- 缓存灵活：`_headers` 文件按文件类型设置不同缓存策略
- 国内可达：`pages.dev` 域名未被 DNS 污染

## 3. CDN 边缘缓存原理

### 什么是边缘缓存

Cloudflare 在全球 300+ 城市部署了边缘节点 (PoP, Point of Presence)。当用户首次请求时，边缘节点从源站 (Pages 存储) 获取内容并缓存。后续同区域用户的请求直接从边缘节点返回，无需回源。

```
首次请求 (冷缓存):
  用户 → 边缘 PoP → 未命中 → Pages 存储 → 返回内容
                                    ↓
                              缓存到边缘 PoP

后续请求 (热缓存):
  用户 → 边缘 PoP → 命中 → 直接返回 (零回源, 极快)
```

### 缓存层级

```
浏览器缓存 (客户端)
  ↓ 未命中
CDN 边缘缓存 (Cloudflare PoP)
  ↓ 未命中
Pages 源站存储
```

## 4. 缓存策略详解

### Cache-Control vs CDN-Cache-Control

| 头部 | 作用对象 | 说明 |
|------|---------|------|
| `Cache-Control` | 浏览器 | 控制浏览器本地缓存时长 |
| `CDN-Cache-Control` | Cloudflare 边缘节点 | 控制边缘 PoP 缓存时长，优先级高于 `Cache-Control` |

### 按文件类型的缓存策略

| 文件类型 | 浏览器缓存 | CDN 边缘缓存 | 策略说明 |
|---------|-----------|-------------|---------|
| **HTML 页面** | `max-age=3600` (1小时) + SWR 86400 (1天) | `max-age=604800` (7天) + SWR 2592000 (30天) | HTML 可能更新，短缓存 + SWR 保证新鲜 |
| **CSS/JS/图片** | `max-age=31536000` (1年) + `immutable` | `max-age=31536000` (1年) + `immutable` | 静态资源不变，长缓存 + immutable 零请求 |
| **其他** | `max-age=86400` (1天) + SWR 7天 | `max-age=604800` (7天) + SWR 30天 | 通用兜底 |

### immutable 的作用

标记 `immutable` 后，浏览器在缓存有效期内**不会发送条件请求** (304 验证)：

```
普通缓存:
  浏览器 → 服务器: "这个文件变了吗？" (304 请求, 需网络往返)

immutable 缓存:
  浏览器 → 本地缓存 → 直接使用 (零网络开销)
```

### stale-while-revalidate (SWR) 的作用

缓存过期后，不阻塞用户，先返回旧内容，后台异步刷新：

```
缓存过期时:
  用户请求 → 立即返回旧缓存 (用户零等待)
              ↓ 同时
              后台异步回源 → 更新缓存 → 下次请求为新鲜内容
```

## 5. 国内加速机制

### Cloudflare 国内 PoP 节点

Cloudflare 在中国大陆设有边缘节点（北京、上海、深圳、广州等），`pages.dev` 域名可以正常解析到这些节点。

```
国内用户 (北京)
  ↓ DNS 解析
  Cloudflare 上海 PoP (106.x.x.x)
  ↓ 检查缓存
  ├── 命中 → 直接返回 (延迟 < 10ms)
  └── 未命中 → 回源 (香港/日本节点) → 缓存 → 返回
```

### 为什么 workers.dev 在国内不可达

`*.workers.dev` 域名在国内常被 **DNS 污染** 或 **TLS 阻断**：
- DNS 污染：国内 DNS 返回错误 IP，无法解析到正确节点
- TLS 阻断：TLS 握手阶段被 RST 中断 (`ERR_CONNECTION_CLOSED`)

`*.pages.dev` 域名目前不受此影响，可以正常解析和连接。

### 进一步加速方案

如需更强国内加速，可绑定 **ICP 备案的自定义域名**：
1. 在 Cloudflare Dashboard 添加自定义域名
2. 域名需完成 ICP 备案
3. 可开通 Cloudflare China Network（与京东云合作）
4. 国内节点直接由京东云提供，延迟更低

## 6. _headers 文件配置

`_headers` 是 Cloudflare Pages 的声明式缓存配置文件，放在 `site/` 根目录：

```
/*
  Cache-Control: public, max-age=3600, stale-while-revalidate=86400
  CDN-Cache-Control: public, max-age=604800, stale-while-revalidate=2592000
  X-Content-Type-Options: nosniff
  X-Frame-Options: DENY
  Referrer-Policy: strict-origin-when-cross-origin

/*.css
  Cache-Control: public, max-age=31536000, immutable
  CDN-Cache-Control: public, max-age=31536000, immutable

/*.html
  Cache-Control: public, max-age=3600, stale-while-revalidate=86400
  CDN-Cache-Control: public, max-age=604800, stale-while-revalidate=2592000
```

### 匹配规则

- `/*` — 匹配所有文件（通用兜底）
- `/*.css` — 匹配所有 CSS 文件
- `/*.html` — 匹配所有 HTML 文件
- 更具体的规则**覆盖**更通用的规则

## 7. 部署流程

### 前置条件

- Cloudflare 账户已认领
- API Token 已创建（权限：Account → Workers Scripts → Edit，IP 限制留空）
- `wrangler` CLI 已安装

### 部署步骤

```bash
# 1. 设置环境变量
export CLOUDFLARE_API_TOKEN="your-token"
export CLOUDFLARE_ACCOUNT_ID="your-account-id"

# 2. 进入项目目录
cd /workspace

# 3. 部署到 Cloudflare Pages
npx wrangler pages deploy site \
  --project-name=java-sql-ai-tutorial \
  --branch=main \
  --commit-dirty=true

# 4. 验证部署
curl -I https://java-sql-ai-tutorial-b7y.pages.dev/
```

### 更新内容

修改 `site/` 目录下的 HTML/CSS 文件后，重新运行部署命令即可。Cloudflare Pages 会自动创建新的部署版本，边缘缓存会在 TTL 过期后更新。

### 手动清除缓存

如需立即更新边缘缓存：

```bash
# 通过 API 清除所有缓存
curl -X POST \
  "https://api.cloudflare.com/client/v4/accounts/$AID/pages/projects/java-sql-ai-tutorial/deployments" \
  -H "Authorization: Bearer $TOKEN"
```

## 8. 故障排查

### 常见问题

| 问题 | 可能原因 | 解决方案 |
|------|---------|---------|
| `ERR_CONNECTION_CLOSED` | workers.dev 被 DNS 污染 | 改用 pages.dev |
| `ERR_NAME_NOT_RESOLVED` | DNS 解析失败 | 检查域名是否正确 |
| 404 错误 | 文件路径错误 | 检查 site/ 目录结构 |
| 样式丢失 | CSS 未上传 | 确认 assets/ 目录完整 |
| 缓存不更新 | CDN 缓存未过期 | 等待 TTL 或手动清缓存 |

### 验证缓存头

```bash
# 检查首页响应头
curl -I https://java-sql-ai-tutorial-b7y.pages.dev/

# 检查 CSS 响应头
curl -I https://java-sql-ai-tutorial-b7y.pages.dev/assets/style.css

# 检查 HTML 页面响应头
curl -I https://java-sql-ai-tutorial-b7y.pages.dev/08.html
```

预期输出应包含：
- `CDN-Cache-Control: max-age=...`
- `Cache-Control: max-age=..., stale-while-revalidate=...`
- `X-Frame-Options: DENY`

---

## 技术参数

| 参数 | 值 |
|------|-----|
| 平台 | Cloudflare Pages |
| 项目名 | java-sql-ai-tutorial |
| 子域名 | java-sql-ai-tutorial-b7y.pages.dev |
| 部署分支 | main |
| 生产环境 | production |
| 缓存规则文件 | site/_headers |
| 文件总数 | 10 (index + 8章 + style.css) |
| 总大小 | ~600 KB (gzip: ~160 KB) |
