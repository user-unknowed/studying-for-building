#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
构建第 12 章《华为ICT大赛·昇腾AI赛道备赛实战》：

1. 生成 site/12.html —— 包含
   · 昇腾 AI 赛道全景：赛制 / 实验平台（华为云 + 香橙派）/ 考点地图
   · MindSpore 入门：思维框架 + 手写最简训练（Pygments 高亮 + 行内行号 + 逐行注释）
   · Ascend C 算子开发：算子编程模型 + Add 算子示例（C++ 内核 + Python Custom 表达）
   · 香橙派开发板推理部署：交叉编译 + 模型转换 + acl 推理命令清单
   · 备赛策略 + 8 小时综合实验打法 + 考前验证清单
2. 注册到全站导航：
   · site/index.html 首页卡片 + hero 文案 + 顶部导航 + 侧边栏 + 学习路线
   · site/01~11.html 顶部导航追加 "12 昇腾AI"
   · site/01~11.html 侧边栏 chapters-m 追加第 12 章 li
   · site/11.html 底部翻页器追加 "下一章 → 12"
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
# 一、实操代码（三组 + 一组速查，覆盖赛道三层能力）
# ════════════════════════════════════════════════════════════════════

# 第 2 节：MindSpore 最简训练（线性回归，5 行就能跑通）
MINDSPORE_TRAIN = """import mindspore as ms                       # 引入 MindSpore 主包
from mindspore import nn, ops              # nn=网络层，ops=算子
ms.set_context(mode=ms.PYNATIVE_MODE)     # 动态图模式，便于调试（默认静态图更快但难调试）

# 1. 构造数据：y = 2x + 1 的样本
x = ms.Tensor([0.0, 1.0, 2.0, 3.0, 4.0])  # 输入张量
y = ms.Tensor([1.0, 3.0, 5.0, 7.0, 9.0])  # 标签（2x+1）

# 2. 定义模型：单层线性 y = w*x + b（一个标量参数就够拟合这个关系）
class LinearModel(nn.Cell):               # 所有模型类继承 nn.Cell（类似 PyTorch nn.Module）
    def __init__(self):
        super().__init__()
        self.fc = nn.Dense(1, 1, weight_init=0.0, bias_init=0.0)  # 1维→1维线性层，初始 w=0,b=0
    def construct(self, x):               # MindSpore 用 construct 而非 forward 定义前向
        return self.fc(x.reshape(-1, 1))  # reshape 成 (5,1) 才能喂给 Dense

net = LinearModel()                       # 实例化网络
loss_fn = nn.MSELoss()                     # 均方误差损失：拟合回归任务的标配
opt = nn.SGD(net.trainable_params(), learning_rate=0.01)  # 随机梯度下降，学习率 0.01

# 3. 装配训练步骤（前向 → 损失 → 反向 → 更新）
def train_step(x, y):
    pred = net(x)                          # 前向算预测
    loss = loss_fn(pred, y.reshape(-1, 1)) # 算损失
    grad = ms.grad(loss, net.trainable_params())(x, y)  # 自动微分求梯度
    opt(grad)                             # 用梯度更新参数
    return loss

# 4. 训练 200 步，看损失收敛
for step in range(200):
    l = train_step(x, y)
    if step % 50 == 0:
        print(f"step {step}, loss = {l.asnumpy():.4f}")  # asnumpy() 把张量转 numpy 数值
print("w =", net.fc.weight.asnumpy(), "b =", net.fc.bias.asnumpy())  # 预期 w≈2.0, b≈1.0
"""

# 第 3 节：Ascend C 自定义 Add 算子（C++ 内核 + Python Custom 表达）
ASCENDC_ADD_CPP = """// add_custom.cpp —— Ascend C 自定义 Add 算子内核（教学版）
// 在 Ascend C 里写算子像写 CUDA：每个线程算一个元素，向量加法天然并行
#include "kernel_operator.h"               // Ascend C 算子开发主头文件
using namespace AscendC;                   // 引入算子命名空间（Kernel/Tiling/Buffer 等）

template <typename T>                      // 模板：支持 FP16/FP32 多种数据类型
class KernelAdd {
public:
    __global__ __aic__ void Compute(GM_ADDR x, GM_ADDR y, GM_ADDR z) {
        // 1. 在 Global Memory 上初始化 buf（x,y 输入；z 输出）
        int32_t blockLength = GetTilingKey() / 1;  // 每个核处理的元素数
        xGm.SetGlobalBuffer((__gm__ T*)x + blockIdx * blockLength, blockLength);
        yGm.SetGlobalBuffer((__gm__ T*)y + blockIdx * blockLength, blockLength);
        zGm.SetGlobalBuffer((__gm__ T*)z + blockIdx * blockLength, blockLength);
        // 2. 通过 DataCachePadIn 进行数据搬运（GM→UB，AI Core 只能算 UB 里的数据）
        LocalTensor<T> xUb = inQueueX.AllocTensor<T>();
        LocalTensor<T> yUb = inQueueY.AllocTensor<T>();
        DataCopy(xUb, xGm, blockLength);   // GM → UB 搬运
        DataCopy(yUb, yGm, blockLength);
        // 3. 执行 Add：z = x + y（Element-wise 向量加，AI Core 硬件指令）
        LocalTensor<T> zUb = outQueueZ.AllocTensor<T>();
        Add(zUb, xUb, yUb, blockLength);   // Ascend C 内置向量加算子
        // 4. 把结果从 UB 搬回 GM，同步后才能给下游用
        outQueueZ.EnQue(zUb);              // 入队标记完成
        DataCopy(zGm, zUb, blockLength);   // UB → GM 搬运
        outQueueZ.DeQue<T>();              // 出队释放资源
    }
private:
    GlobalTensor<T> xGm, yGm, zGm;         // GM 上的张量句柄
    TQue<QuePosition::VECIN, 1> inQueueX, inQueueY;  // 输入队列（UB 上）
    TQue<QuePosition::VECOUT, 1> outQueueZ;          // 输出队列（UB 上）
};
"""

ASCENDC_ADD_PY = """import mindspore as ms                       # MindSpore 主包
from mindspore import ops                  # 算子库
from mindspore.common import dtype as mstype  # 数据类型枚举

# 1. 注册 Ascend C 自定义算子（指向 .cpp 内核 + 算子信息表）
add_reg_info = ops.CustomRegInfo() \\      # 构造算子注册信息
    .input(0, "x", "required") \\           # 第 0 输入：x
    .input(1, "y", "required") \\           # 第 1 输入：y
    .output(0, "z", "required") \\          # 第 0 输出：z
    .dtype_format(DataType.F16_Default, DataType.F16_Default, DataType.F16_Default) \\
    .target("Ascend") \\                    # 仅在 Ascend 平台生效
    .get_op_info()

# 2. 用 ops.Custom 把内核接进 MindSpore 计算图
class AddNet(ms.nn.Cell):
    def __init__(self):
        super().__init__()
        func = "add_custom.cpp:KernelAdd"  # 文件名:类名
        out_shape = lambda x, y: x         # 输出形状跟 x 一致
        out_dtype = lambda x, y: x          # 输出类型跟 x 一致
        self.add = ops.Custom(func=func, out_shape=out_shape,
                             out_dtype=out_dtype, func_type="aot",
                             bprop=None, reg_info=add_reg_info)
    def construct(self, x, y):
        return self.add(x, y)              # 调用自定义算子

# 3. 实测：x=[1,2,3], y=[4,5,6] → z=[5,7,9]
net = AddNet()
x = ms.Tensor([1.0, 2.0, 3.0], mstype.float16)
y = ms.Tensor([4.0, 5.0, 6.0], mstype.float16)
z = net(x, y)
print("z =", z.asnumpy())                   # 预期输出 [5.0, 7.0, 9.0]
"""

# 第 4 节：香橙派开发板推理部署命令清单（Linux 命令 + acl Python）
ORANGEPI_DEPLOY = """# 1. 在华为云 ModelArts 上把 MindSpore 模型导出为 .air 或 .om
#    （.air 是 Ascend 中间表示，.om 是香橙派最终推理格式）
from mindspore import export                # MindSpore 模型导出 API
export(net, x, file_name="add_model", file_format="AIR")  # 导出 add_model.air

# 2. 用 ATC 工具把 .air 转成香橙派能跑的 .om（在华为云昇腾环境执行）
atc --framework=1 \\                        # 1 表示 AIR 框架
    --model=add_model.air \\                 # 输入文件
    --output=add_model.om \\                 # 输出 .om 文件
    --soc_version=Ascend310 \\               # 香橙派用 Ascend 310 芯片
    --input_shape="x:1,3"                    # 指定推理时的输入形状

# 3. 把 .om 拷到香橙派（先装好昇腾 CANN 软件包）
scp add_model.om HwHiAiUser@orangepi:~/      # 用 scp 传文件到板子

# 4. 在香橙派上写 ACL Python 推理脚本（aclruntime 加载模型推理）
#    acl_infer.py
import acl                                  # 香橙派 ACL Python 接口
acl.init()                                  # 初始化 ACL 运行时
context, ret = acl.rt.set_device(0)         # 选用 NPU 0 号设备
stream, ret = acl.rt.create_stream()        # 创建计算流
model_id, ret = acl.mdl.load_from_file("add_model.om", stream)  # 加载 .om 模型
# 5. 准备输入数据 → 推理 → 取输出
import numpy as np
input_data = np.array([1.0, 2.0, 3.0], dtype=np.float16)
output = acl.mdl.execute(model_id, [input_data])   # 执行推理
print("推理结果:", output)                  # 预期 [5.0, 7.0, 9.0]
acl.finalize()                              # 释放资源
"""

# VRP 视图速查改成昇腾"赛道三层能力速查"
TRACK_LAYER_VIEW = """昇腾AI赛道三层能力
├─ ① MindSpore 模型训练（华为云）        ← 在云上用 Python 训模型
├─ ② Ascend C 算子开发（华为云）          ← 用 C++ 写底层算子内核
└─ ③ 香橙派推理部署（开发板）              ← 把训练好的模型部署到板子上跑

比赛综合实验（8 小时）会同时用到三层：
  训练→ 模型导出→ ATC 转换→ 香橙派部署→ 验证推理结果

对应实验平台：
  · ① 在华为云 ModelArts / KooLabs 云实验
  · ② 在华为云昇腾开发环境（MindStudio）
  · ③ 在香橙派开发板（自带 Ascend 310 NPU）
"""

# ════════════════════════════════════════════════════════════════════
# 二、Pygments 高亮工具
# ════════════════════════════════════════════════════════════════════

FMT = HtmlFormatter(cssclass="codehilite", linenos="inline")

def listing(src, lang="python"):
    """Pygments 高亮（带行内行号），输出与全站 .codehilite CSS 兼容。"""
    return pyg_highlight(src, get_lexer_by_name(lang), FMT).strip()


# ════════════════════════════════════════════════════════════════════
# 三、页面 HTML 组装
# ════════════════════════════════════════════════════════════════════

ACCENT = "#7c3aed"  # 紫色，与 09 蓝、10 棕、11 绿区分

def build_page():
    """组装 site/12.html 全文。"""
    code_ms = listing(MINDSPORE_TRAIN, "python")
    code_cpp = listing(ASCENDC_ADD_CPP, "cpp")
    code_py = listing(ASCENDC_ADD_PY, "python")
    code_dep = listing(ORANGEPI_DEPLOY, "bash")
    code_view = listing(TRACK_LAYER_VIEW, "text")

    page = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
<meta name="theme-color" content="{ACCENT}">
<title>12 华为ICT大赛·昇腾AI赛道备赛实战 · Java · SQL · Python AI 教程</title>
<link rel="stylesheet" href="assets/style.css">
<style>
  /* 12 章专属内联样式（不污染全站 style.css） */
  .lab-block {{ border:1px solid #e9d5ff; border-radius:8px; padding:0 0 12px; margin:16px 0; overflow:hidden; }}
  .lab-block .lab-head {{
    background:{ACCENT}; color:#fff; padding:8px 16px; font-weight:600; font-size:14px;
  }}
  .lab-block .codehilite {{ margin:0; border:none; border-radius:0; }}
  .track-tree {{
    border:1px solid #e9d5ff; border-left:4px solid {ACCENT};
    border-radius:8px; padding:14px 18px; margin:14px 0;
    background:#faf5ff; font-family:ui-monospace,Menlo,Consolas,monospace;
    font-size:13px; white-space:pre; overflow-x:auto; color:#1f2937;
  }}
</style>
</head>
<body>
<header class="topnav">
  <button class="nav-toggle" type="button" aria-label="打开导航目录" aria-expanded="false" aria-controls="sidebar">☰</button>
  <div class="brand">Java · SQL · Python AI 教程<small>从原理到实战</small></div>
  <nav><a href="01.html" class="">01 JavaSE 基础知</a><a href="02.html" class="">02 Java 与 SQL</a><a href="03.html" class="">03 SQL 数据库深度讲</a><a href="04.html" class="">04 学习报告：Java</a><a href="05.html" class="">05 JavaEE 企业级</a><a href="06.html" class="">06 Java 上位机开发</a><a href="07.html" class="">07 JavaEE 上位机</a><a href="08.html" class="">08 Python 与 A</a><a href="09.html" class="">09 华为ICT大赛·云赛道</a><a href="10.html" class="">10 源码编辑</a><a href="11.html" class="">11 网络赛道</a><a href="12.html" class="active">12 昇腾AI</a></nav>
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
<li><a href="11.html">🌐 第 11 章 · 华为ICT大赛·网络赛道备赛实战</a></li>
<li class="active"><a href="12.html">🚀 第 12 章 · 华为ICT大赛·昇腾AI赛道备赛实战</a></li></ul>
    </div>
    <h4>本节目录</h4>
    <ul><ul>
<li><a href="#0">0. 导读：昇腾AI赛道 vs 其他赛道</a></li>
<li><a href="#1">1. 昇腾AI赛道全景</a><ul>
<li><a href="#11">1.1 赛制与赛程</a></li>
<li><a href="#12">1.2 实验平台：华为云 + 香橙派</a></li>
<li><a href="#13">1.3 赛道三层能力地图</a></li>
<li><a href="#14">1.4 对应认证与官方资源</a></li>
</ul>
</li>
<li><a href="#2">2. MindSpore 入门：手写最简训练</a><ul>
<li><a href="#21">2.1 思维框架：MindSpore vs PyTorch</a></li>
<li><a href="#22">2.2 实操：线性回归训练</a></li>
<li><a href="#23">2.3 对应考点</a></li>
</ul>
</li>
<li><a href="#3">3. Ascend C 算子开发：算子赛主战场</a><ul>
<li><a href="#31">3.1 算子编程模型</a></li>
<li><a href="#32">3.2 实操：手写 Add 算子</a></li>
<li><a href="#33">3.3 对应考点</a></li>
</ul>
</li>
<li><a href="#4">4. 香橙派开发板推理部署</a><ul>
<li><a href="#41">4.1 板卡介绍与部署流程</a></li>
<li><a href="#42">4.2 实操：从云上模型到板上推理</a></li>
<li><a href="#43">4.3 对应考点</a></li>
</ul>
</li>
<li><a href="#5">5. 备赛策略与 8 小时综合实验打法</a></li>
<li><a href="#6">6. 考前验证清单</a></li>
</ul></ul>
  </aside>
  <main class="content">
    <div class="meta" style="color:{ACCENT};font-weight:600">第 12 章 · 🚀</div>
    <h1 style="border-bottom:3px solid {ACCENT};padding-bottom:10px">华为ICT大赛·昇腾AI赛道备赛实战</h1>
    <div class="meta">MindSpore 训练 · Ascend C 算子 · 香橙派推理部署 · 8 小时综合实验打法</div>

<h2 id="0">0. 导读：昇腾AI赛道 vs 其他赛道</h2>
<p>华为 ICT 大赛实践赛下设四条赛道——<strong>网络、云、基础软件、昇腾 AI</strong>。前三条赛道已在 09、11 章覆盖，本章专攻昇腾 AI 赛道。它和云赛道一样在华为云上跑，但加了<strong>算子开发</strong>和<strong>开发板部署</strong>两层——前者让你深入底层硬件，后者让你模型真正落地到端侧设备。</p>
<table>
<thead><tr><th>维度</th><th>云赛道（第 09 章）</th><th>网络赛道（第 11 章）</th><th>昇腾AI赛道（本章）</th></tr></thead>
<tbody>
<tr><td>实验平台</td><td>华为云控制台</td><td>eNSP 模拟器</td><td>华为云 + 香橙派开发板</td></tr>
<tr><td>核心技能</td><td>云服务开通</td><td>路由器配置</td><td>MindSpore 训练 / Ascend 算子 / 端侧部署</td></tr>
<tr><td>对应认证</td><td>HCIA-Cloud Service</td><td>HCIA-Datacom</td><td>HCIA-AI / Ascend 算子认证</td></tr>
<tr><td>典型题型</td><td>部署云上架构</td><td>配路由排故障</td><td>训模型 / 写算子 / 部板子</td></tr>
<tr><td>开放范围</td><td>全球</td><td>全球</td><td>仅中国大陆</td></tr>
</tbody>
</table>
<p>本章按"训练 → 算子 → 部署"三层结构展开，每层都配实操代码——这三层加起来正好是<strong>8 小时综合实验</strong>的完整链路。资料综合自华为 ICT 大赛官网、华为云 KooLabs 实验平台、MindSpore 官方教程与高校公开备赛经验。</p>

<h2 id="1">1. 昇腾AI赛道全景</h2>

<h3 id="11">1.1 赛制与赛程</h3>
<p>昇腾 AI 赛道是 ICT 大赛实践赛四赛道中<strong>唯一仅面向中国大陆</strong>的赛道，原因是要发香橙派开发板（涉及硬件物流）。第十一届（2026-2027）赛程大致为：</p>
<ul>
<li><strong>省赛</strong>（9-11 月）：理论考试 + 上机实验（华为云），筛选晋级队伍。</li>
<li><strong>全国总决赛</strong>（12 月-次年 1 月）：8 小时综合实验，理论与实操结合。</li>
<li><strong>全球总决赛</strong>（次年 5-6 月）：8 小时综合实验，全程华为云 + 香橙派开发板，赛题全英文。</li>
</ul>
<p>昇腾 AI 赛道下还设<strong>算子赛</strong>专项——主要考察基于 Ascend C 的自定义算子开发、精度调试、性能优化，分资格赛、决赛、全球总决赛三阶段，资格赛需完成两项算子开发认证。</p>

<h3 id="12">1.2 实验平台：华为云 + 香橙派</h3>
<p>昇腾 AI 赛道用了两套环境，分清"在哪做什么"很关键：</p>
<table>
<thead><tr><th>环境</th><th>用途</th><th>典型操作</th></tr></thead>
<tbody>
<tr><td>华为云 ModelArts</td><td>训练 + 算子开发</td><td>MindSpore 训模型、MindStudio 写 Ascend C 算子</td></tr>
<tr><td>华为云 KooLabs 云实验</td><td>练手</td><td>每日免费名额做昇腾实验、做算子实验</td></tr>
<tr><td>香橙派开发板</td><td>端侧推理部署</td><td>scp 传 .om 模型、ACL Python 跑推理</td></tr>
</tbody>
</table>
<blockquote>
<p>华为云 KooLabs 提供"昇腾"实验方向，覆盖 MindSpore 学习、模型训练、部署——每日 0 点限量免费名额，是备赛主战场。</p>
</blockquote>

<h3 id="13">1.3 赛道三层能力地图</h3>
<div class="track-tree">{TRACK_LAYER_VIEW}</div>
<p>这张图把赛道拆成三层。综合实验会贯穿三层——训完模型，导出转换，再部署到香橙派验证。任何一层掉链子整条链就断，所以<strong>三层都得练</strong>。</p>

<h3 id="14">1.4 对应认证与官方资源</h3>
<ul>
<li><strong>HCIA-AI 认证</strong>：覆盖昇腾 AI 赛道 60% 赛点（神经网络、MindSpore 框架、深度学习应用）。</li>
<li><strong>Ascend 算子认证</strong>：覆盖算子赛考点，资格赛必考。</li>
<li><strong>官方资源</strong>：华为 ICT 学院官网（e.huawei.com/cn/talent/ict-academy）、华为云 KooLabs 云实验（lab.huaweicloud.com）、MindSpore 官方教程（mindspore.cn）。</li>
</ul>

<h2 id="2">2. MindSpore 入门：手写最简训练</h2>

<h3 id="21">2.1 思维框架：MindSpore vs PyTorch</h3>
<p>第 08 章我们用了 PyTorch。MindSpore 是华为自研的深度学习框架，专为昇腾 NPU 优化。核心差异：</p>
<table>
<thead><tr><th>维度</th><th>PyTorch</th><th>MindSpore</th></tr></thead>
<tbody>
<tr><td>前向定义</td><td><code>def forward(self, x)</code></td><td><code>def construct(self, x)</code></td></tr>
<tr><td>自动微分</td><td>动态图，backward() 隐式</td><td><code>ms.grad(fn, params)(x, y)</code> 显式</td></tr>
<tr><td>设备</td><td>主要是 GPU/CPU</td><td>原生支持 Ascend NPU</td></tr>
<tr><td>静态图</td><td>torch.jit.script</td><td><code>ms.GRAPH_MODE</code>（默认更快）</td></tr>
<tr><td>生态</td><td>全球主流</td><td>华为生态（昇腾/鲲鹏/鸿蒙）</td></tr>
</tbody>
</table>

<h3 id="22">2.2 实操：线性回归训练</h3>
<p>下面这段代码在华为云 ModelArts（选昇腾镜像）里能直接跑——一个完整的 MindSpore 线性回归训练，5 行数据 + 一个 Dense 层 + 自动微分 + 200 步收敛。看懂这段，MindSpore 训练范式就吃透了：</p>
<div class="lab-block">
  <div class="lab-head">🧪 Lab 1 · MindSpore 线性回归训练（Python）</div>
{code_ms}
</div>
<p>关键理解：<code>ms.grad(loss, params)(x, y)</code> 是 MindSpore 的显式微分 API——和 PyTorch 的 <code>loss.backward()</code> 思路完全不同：MindSpore 把"求梯度"当成函数，输入是数据，输出是各参数梯度。这是 MindSpore 静态图设计哲学，与函数式编程一脉相承。</p>

<h3 id="23">2.3 对应考点</h3>
<blockquote>
<p>HCIA-AI 认证第三章"深度学习预备知识"和第五章"MindSpore 概览"直接对应本节。综合实验里"<strong>模型训练</strong>"环节占 1-2 小时，要求在 ModelArts 里跑通一个 MindSpore 训练脚本，输出 .ckpt 权重文件——本节代码就是这个流程的最简版。</p>
</blockquote>

<h2 id="3">3. Ascend C 算子开发：算子赛主战场</h2>

<h3 id="31">3.1 算子编程模型</h3>
<p>Ascend C 是华为为昇腾 NPU 设计的算子开发语言，类似 CUDA 之于 NVIDIA GPU。核心抽象：</p>
<ul>
<li><strong>AI Core</strong>：昇腾芯片上的计算核心，所有算子最终跑在这。</li>
<li><strong>Global Memory（GM）</strong>：芯片外的大显存，存输入输出张量。</li>
<li><strong>Unified Buffer（UB）</strong>：AI Core 内部高速缓存，算子从这里取数据算。</li>
<li><strong>数据搬运</strong>：算子开发核心工作是"GM↔UB 搬运 + 在 UB 上算"——和 CUDA 的 GM↔Shared Memory 模式同构。</li>
<li><strong>向量加（Add）</strong>：内置算子，演示用最简单。</li>
</ul>

<h3 id="32">3.2 实操：手写 Add 算子</h3>
<p>算子分两半写：C++ 内核（在 AI Core 上跑）+ Python 接入（让 MindSpore 能调用）。下面是 Ascend C Add 算子的最简实现：</p>
<div class="lab-block">
  <div class="lab-head">🧪 Lab 2a · Ascend C Add 算子内核（C++）</div>
{code_cpp}
</div>
<p>关键理解：算子内核 = "搬数据 → 算 → 搬回去"三步。<code>DataCopy(xUb, xGm, ...)</code> 把数据从 GM 搬到 UB；<code>Add(zUb, xUb, yUb, ...)</code> 在 UB 上做向量加；<code>DataCopy(zGm, zUb, ...)</code> 把结果搬回 GM。这是所有算子的统一骨架——复杂算子只是"算"那步换成更复杂的运算。</p>
<div class="lab-block">
  <div class="lab-head">🧪 Lab 2b · 用 ops.Custom 把算子接进 MindSpore（Python）</div>
{code_py}
</div>
<p>关键理解：<code>ops.Custom(func="add_custom.cpp:KernelAdd", func_type="aot")</code> 的 <code>aot</code> 表示"Ahead-Of-Time"——先编译 C++ 内核成 .so，MindSpore 运行时调用。这是 Ascend C 算子接入 MindSpore 的标准模式，比"hybrid"（即时编译）更适合性能敏感场景。</p>

<h3 id="33">3.3 对应考点</h3>
<blockquote>
<p>算子赛考点 100% 覆盖本节。综合实验里"<strong>算子开发</strong>"环节占 2-3 小时，要求写一个自定义算子（典型题：矩阵乘、卷积、激活函数），用 ACL 接进 MindSpore，并通过精度测试（与 numpy 计算结果对比误差 &lt; 1e-3）。</p>
</blockquote>

<h2 id="4">4. 香橙派开发板推理部署</h2>

<h3 id="41">4.1 板卡介绍与部署流程</h3>
<p>香橙派（Orange Pi AIPro）是华为与香橙派联合推出的开发板，搭载<strong>昇腾 Ascend 310B</strong> NPU，4-8 TOPS 算力。综合实验发的就是这块板。部署流程：</p>
<ol>
<li><strong>云上训练</strong>：MindSpore 训出模型 → 导出 <code>.air</code> 文件。</li>
<li><strong>ATC 转换</strong>：用 <code>atc</code> 工具把 <code>.air</code> 转成香橙派能跑的 <code>.om</code> 格式。</li>
<li><strong>传输部署</strong>：<code>scp</code> 把 <code>.om</code> 拷到香橙派（板子要预装 CANN 软件）。</li>
<li><strong>ACL 推理</strong>：在香橙派上写 ACL Python 脚本加载 <code>.om</code>，喂数据跑推理。</li>
</ol>

<h3 id="42">4.2 实操：从云上模型到板上推理</h3>
<p>下面这串命令把第 2 节训出来的 MindSpore 模型一路部署到香橙派并跑通推理——8 小时实验里"<strong>部署环节</strong>"占 1-2 小时：</p>
<div class="lab-block">
  <div class="lab-head">🧪 Lab 3 · 从 MindSpore 模型到香橙派推理（命令清单）</div>
{code_dep}
</div>
<p>关键理解：<code>atc</code> 是 Ascend Tensor Compiler——把 MindSpore/PyTorch 模型转成昇腾 NPU 优化的 <code>.om</code> 格式。 <code>--soc_version=Ascend310</code> 必须和香橙派实际芯片一致，错了推理会报错。<code>acl.mdl.load_from_file</code> 是 ACL（Ascend Computing Language）运行时 API，加载模型后用 <code>execute</code> 推理。</p>

<h3 id="43">4.3 对应考点</h3>
<blockquote>
<p>综合实验"<strong>端侧部署</strong>"环节占 1-2 小时。常见题型：给定一个训练好的 MindSpore 模型，要求转换、部署到香橙派，跑通推理并报告精度和耗时。<strong>性能优化</strong>是拉开差距的关键——升 NPU 利用率、降推理延迟。</p>
</blockquote>

<h2 id="5">5. 备赛策略与 8 小时综合实验打法</h2>

<h3 id="51">5.1 8 小时综合实验时间分配建议</h3>
<table>
<thead><tr><th>环节</th><th>时长</th><th>关键动作</th><th>常见坑</th></tr></thead>
<tbody>
<tr><td>读题 + 环境验证</td><td>0.5h</td><td>看英文题、连香橙派、确认 NPU 可用</td><td>香橙派 CANN 未装好</td></tr>
<tr><td>模型训练</td><td>1.5-2h</td><td>跑通 MindSpore 训练脚本</td><td>静态图调试难，改成 PYNATIVE</td></tr>
<tr><td>算子开发</td><td>2-3h</td><td>写 C++ 内核 + Custom 接入</td><td>GM↔UB 搬运写错，结果乱码</td></tr>
<tr><td>模型导出 + ATC 转换</td><td>0.5h</td><td>导 .air，atc 转 .om</td><td>atc 参数 soc_version 写错</td></tr>
<tr><td>香橙派部署 + 推理</td><td>1-2h</td><td>scp 传 .om，写 ACL 推理脚本</td><td>板子算力和云上不一致</td></tr>
<tr><td>精度验证 + 性能优化</td><td>1-1.5h</td><td>对比 numpy 结果，调 batch size</td><td>精度不够，可能 NPU 与 CPU 数值类型不一致</td></tr>
<tr><td>留 buffer</td><td>0.5-1h</td><td>修问题、写报告</td><td>没时间检查就交</td></tr>
</tbody>
</table>

<h3 id="52">5.2 备赛策略</h3>
<ol>
<li><strong>认证打底</strong>：考 HCIA-AI + Ascend 算子认证，覆盖 80% 赛点。</li>
<li><strong>三人分工</strong>：一人主训模型，一人主写算子，一人主端侧部署——8 小时单线干不完。</li>
<li><strong>KooLabs 刷实验</strong>：每日 0 点抢免费名额，覆盖昇腾实验、算子实验。</li>
<li><strong>用香橙派练手</strong>：比赛发的板子一定要提前拿到（学校 ICT 学院可申请），别在比赛现场第一次摸板。</li>
<li><strong>建代码模板库</strong>：MindSpore 训练模板、Ascend C 算子模板、ACL 推理模板——比赛现场改比从零写快 10 倍。</li>
<li><strong>查 Ascend C 文档</strong>：mindspore.cn 的算子开发教程，Add/Concat/Softmax 都有官方示例，参考写。</li>
</ol>

<h2 id="6">6. 考前验证清单</h2>
<p>正式比赛前用这张清单确认三层能力都齐：</p>
<ul>
<li>☐ 华为云账号能登录 ModelArts，能创建昇腾类型 Notebook</li>
<li>☐ MindSpore 最简训练脚本能跑通（线性回归 200 步收敛）</li>
<li>☐ 能默写 <code>ms.grad(loss, params)(x, y)</code> 三段式（前向 → 损失 → 梯度）</li>
<li>☐ 能写 Ascend C Add 算子内核：DataCopy → Add → DataCopy 三步骨架</li>
<li>☐ 能用 <code>ops.Custom(func_type="aot")</code> 把算子接进 MindSpore</li>
<li>☐ 能用 <code>export(net, x, file_format="AIR")</code> 导出模型</li>
<li>☐ 能用 <code>atc</code> 把 .air 转 .om，知道 --soc_version 参数</li>
<li>☐ 香橙派能 ssh 登录，<code>acl.init()</code> 不报错</li>
<li>☐ 能写 ACL Python 推理脚本，加载 .om 并 execute</li>
<li>☐ 三人分工明确，每人有自己负责层的代码模板</li>
</ul>

<blockquote>
<p>免责声明：本章基于华为 ICT 大赛官网、华为云 KooLabs、MindSpore 官方教程与高校公开备赛资料整理，具体比赛内容以华为 ICT 大赛组委会发布的最新通知为准。Ascend C 算子示例代码为教学简化版，比赛实际题目的算子会更复杂（矩阵乘、卷积等），但代码骨架一致。</p>
</blockquote>
    <div class="pager"><a href="11.html"><div class="dir">← 上一章</div><div class="ttl">华为ICT大赛·网络赛道备赛实战</div></a><a href="index.html" style="text-align:right"><div class="dir" style="text-align:right">返回首页 →</div><div class="ttl" style="text-align:right">Java · SQL · Python AI 教程</div></a></div>
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

NAV_12 = '<a href="12.html" class="">12 昇腾AI</a>'
SIDEBAR_12 = '<li><a href="12.html">🚀 第 12 章 · 华为ICT大赛·昇腾AI赛道备赛实战</a></li>'
CARD_12 = (
    '<a class="card" href="12.html">\n'
    '      <div class="num">第 12 章</div>\n'
    '      <div class="icon">🚀</div>\n'
    '      <h3>华为ICT大赛·昇腾AI赛道备赛实战</h3>\n'
    '      <div class="sub">MindSpore 训练 · Ascend C 算子 · 香橙派推理部署 · 8 小时综合实验打法</div>\n'
    '      <p>昇腾 AI 赛道三层能力地图：MindSpore 训模型、Ascend C 写算子内核、香橙派部署推理——每层配实操代码，8 小时综合实验全链路打通。</p>\n'
    '      <div class="cta" style="color:#7c3aed">开始阅读 →</div>\n'
    '    </a>'
)
ROADMAP_12 = (
    '<li><b>⑨ ICT 昇腾AI赛道</b> → 12 章（MindSpore 训练 + Ascend C 算子 + 香橙派部署，承接第 08 章 Python/AI）</li>'
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
    """在顶部 nav 的 </nav> 前追加 12 链接（幂等）。"""
    with open(path, encoding="utf-8") as f:
        s = f.read()
    m = re.search(r"<nav>.*?</nav>", s, re.S)
    if not m:
        raise SystemExit(f"[FAIL] {path}: 未找到 <nav>")
    nav = m.group(0)
    if 'href="12.html"' in nav:
        print(f"  [skip] {os.path.basename(path)} 顶部导航已含 12.html")
        return False
    new_nav = nav.replace("</nav>", NAV_12 + "</nav>")
    s = s[:m.start()] + new_nav + s[m.end():]
    with open(path, "w", encoding="utf-8") as f:
        f.write(s)
    print(f"  [ok]   {os.path.basename(path)} 顶部导航追加 12 链接")
    return True


def add_sidebar_link(path):
    """在侧边栏 chapters-m 的 11 章 li 后追加 12 章 li（幂等）。

    匹配模式：<li>...<a href="11.html">...第 11 章.../a></li></ul>
    """
    with open(path, encoding="utf-8") as f:
        s = f.read()
    # 11 章侧边栏 li 可能带 class="active"
    pattern = r'(<li(?:\s+class="[^"]*")?><a href="11\.html">[^<]*第 11 章[^<]*</a></li>)(</ul>)'
    m = re.search(pattern, s)
    if not m:
        print(f"  [warn] {os.path.basename(path)} 未找到 11 章侧边栏 li")
        return False
    if 'href="12.html"' in s[m.start():m.end()]:
        print(f"  [skip] {os.path.basename(path)} 侧边栏已含 12.html")
        return False
    new_block = m.group(1) + SIDEBAR_12 + m.group(2)
    s = s[:m.start()] + new_block + s[m.end():]
    with open(path, "w", encoding="utf-8") as f:
        f.write(s)
    print(f"  [ok]   {os.path.basename(path)} 侧边栏追加 12 章 li")
    return True


def register_nav():
    """全站导航注册：01~11 章顶部 nav + 侧边栏 + 11 章 pager + 首页卡片。"""
    print("③ 注册到全站导航")
    # 01 ~ 11 章：顶部 nav + 侧边栏
    for i in range(1, 12):
        p = f"{SITE}/{i:02d}.html"
        if not os.path.exists(p):
            print(f"  [warn] {p} 不存在，跳过")
            continue
        add_nav_links(p)
        add_sidebar_link(p)
    # 首页：顶部 nav + 侧边栏
    add_nav_links(f"{SITE}/index.html")
    add_sidebar_link(f"{SITE}/index.html")

    # 首页：章节计数文案
    ok = patch_snippets(f"{SITE}/index.html", [
        ("11 个递进章节，覆盖从语言基础到工业应用、AI 大模型、ICT 竞赛实战与源码工程化的完整阶梯。",
         "12 个递进章节，覆盖从语言基础到工业应用、AI 大模型、ICT 竞赛实战与源码工程化的完整阶梯。"),
    ])
    print(f"  [{'ok' if ok else 'skip'}] index.html 章节计数 11→12")

    # 首页：第 12 章卡片（插在 11 章卡片后、</div> 前）
    # 11 章卡片结尾标志：<div class="cta" style="color:#16a34a">开始阅读 →</div>\n    </a>\n  </div>
    ok = patch_snippets(f"{SITE}/index.html", [
        ('<div class="cta" style="color:#16a34a">开始阅读 →</div>\n    </a>\n  </div>',
         '<div class="cta" style="color:#16a34a">开始阅读 →</div>\n    </a>\n' + CARD_12 + '\n  </div>'),
    ])
    print(f"  [{'ok' if ok else 'skip'}] index.html 第 12 章卡片")

    # 首页：学习路线追加第 ⑨ 步（在 ⑧ 后）
    ok = patch_snippets(f"{SITE}/index.html", [
        ('<li><b>⑧ ICT 网络赛道</b> → 11 章（网络原理三部曲 + eNSP 实操：路由、OSPF、ACL）</li>',
         '<li><b>⑧ ICT 网络赛道</b> → 11 章（网络原理三部曲 + eNSP 实操：路由、OSPF、ACL）</li>\n      ' + ROADMAP_12),
    ])
    print(f"  [{'ok' if ok else 'skip'}] index.html 学习路线追加第 ⑨ 步")

    # 11 章：pager 从"返回首页"改为"下一章 → 12"
    ok = patch_snippets(f"{SITE}/11.html", [
        ('<a href="index.html" style="text-align:right"><div class="dir" style="text-align:right">返回首页 →</div>'
         '<div class="ttl" style="text-align:right">Java · SQL · Python AI 教程</div></a></div>',
         '<a href="12.html" style="text-align:right"><div class="dir" style="text-align:right">下一章 →</div>'
         '<div class="ttl" style="text-align:right">华为ICT大赛·昇腾AI赛道备赛实战</div></a></div>'),
    ])
    print(f"  [{'ok' if ok else 'skip'}] 11.html 翻页器接入第 12 章")


# ════════════════════════════════════════════════════════════════════
# 五、同步 site/ → 根目录
# ════════════════════════════════════════════════════════════════════

def sync_to_root():
    print("④ 同步 site/ → 根目录")
    files = ["12.html", "index.html"] + [f"{i:02d}.html" for i in range(1, 12)]
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
    print("构建第 12 章《华为ICT大赛·昇腾AI赛道备赛实战》")
    print("=" * 60)

    print("① 生成 site/12.html")
    page = build_page()
    # 验证关键内容已嵌入
    assert "MindSpore" in page, "MindSpore 关键词未嵌入"
    assert page.count("codehilite") >= 4, "代码块不足 4 处"
    assert "第 12 章 · 华为ICT大赛·昇腾AI赛道备赛实战" in page, "侧边栏标题缺失"
    assert "drawer-open" in page and "nav-toggle" in page, "抽屉脚本缺失"
    assert "Ascend C" in page and "香橙派" in page, "赛道关键词缺失"
    out = f"{SITE}/12.html"
    with open(out, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"  [ok] 写入 {out}（{len(page.encode('utf-8')):,} 字节）")

    print("② 注册到全站导航")
    register_nav()

    print("③ 同步 site/ → 根目录")
    sync_to_root()

    print("=" * 60)
    print("完成。接下来：本地验证 → git commit → push gh-pages")
    print("=" * 60)


if __name__ == "__main__":
    main()
