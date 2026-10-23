# GNN × 超表面阵列：文献检索与脉络梳理

- 检索日期：2026-10-23
- 数据来源：OpenAlex（题录/引文网络）、Crossref（作者与摘要）、arXiv、出版商页面、GitHub
- 说明：中文库（CNKI/万方）需订阅，未做系统检索；中文文献线索见第 7 节

---

## 0. 一句话结论

这个交叉方向**总量还很小但正在快速升温**：真正把「超表面阵列」显式建成图、用 GNN 学单元间耦合的工作，标题/摘要精确命中仅约 **20 篇**（OpenAlex，2026-10-23），但已形成清晰的三段式脉络——
**① 证明 GNN 能替代全波仿真刻画阵列耦合（2022–2024）→ ② 用图结构反过来发现新物理（长程耦合、多维复用，2025–2026）→ ③ 走向大孔径/可编程阵列的系统级设计（2025–2026）**。

若「超表面阵列」指的是**超表面天线阵/反射阵/相控阵**，则另有微波与光学相控阵的 GNN 文献簇（第 6 节），方法同构、可直接迁移。

---

## 1. 检索方法与体量

| 检索式（OpenAlex，title_and_abstract） | 命中数 |
|---|---|
| `graph neural network` + `metasurface` | 19 |
| `graph neural network` + `metamaterial` | 42 |
| `graph neural network` + `reconfigurable intelligent surface` | 86 |
| `graph neural network` + `antenna array` | 63 |
| `graph` + `metasurface`（宽口径，含图论/图样混淆） | 58 |

- 全文字段检索 `graph neural network metasurface` 有 2401 条，但绝大多数只是参考文献里顺带一提，**不能**当作相关文献量。
- 最有效的两条追引文路径：
  - Khoram 2022（ACS Photonics）被引 27 次 → 后续工作几乎都在这条线上；
  - Wu 2024（Laser Photonics Rev）被引 23 次 → 智能超表面/长程耦合支线。
- 核心作者群高度集中：**Zongfu Yu / Erfan Khoram（UW–Madison）**、**Chao Qian / Hongsheng Chen（浙江大学）**、**Sensong An（UNT，原 UMass Lowell）**、**Jun-Jun Xiao 组（GAT-Net）**、**天津大学（复数域 GNN 阵列天线）**、**北京理工大学（物理信息 GCN 平面阵）**。

---

## 2. 核心奠基：把 meta-atom 阵列建成图

### 2.1 Graph Neural Networks for Metasurface Modeling
**E. Khoram, Z. Wu, Y. Qu, M. Zhou, Z. Yu.** *ACS Photonics* **10**(4), 892 (2023；2022-11-23 在线). DOI: [10.1021/acsphotonics.2c01019](https://doi.org/10.1021/acsphotonics.2c01019)

- 开源仓库的原始题名把贡献说得更直白：*“Graph Neural Networks to Model the Coupling between Scattering Elements in Metasurfaces of Varying Sizes”*（[GitHub](https://github.com/erfan6511/GNN-for-Metasurfaces)）。
- **做法**：散射体（meta-atom）作节点、单元间近场耦合作边，用 GNN 代理 FDTD 预测整阵响应；关键卖点是**跨阵列尺寸泛化**——小阵训练、大阵推理。
- **为什么必读**：这是本方向的“定义性工作”，后续论文的 baseline 与图构造范式基本都源自这里；仓库含 Tidy3D 造数据脚本 + 训练 + 逆向设计代码，是目前少见的可复现资源。

### 2.2 General Characterization of Intelligent Metasurfaces with Graph Coupling Network
**O. Wu, C. Qian, Z. Fan, X. Zhu, H. Chen.** *Laser & Photonics Reviews* **19**(1), 2400979 (2025；2024-08-20 在线). DOI: [10.1002/lpor.202400979](https://doi.org/10.1002/lpor.202400979)

- **做法**：提出通用 GNN 框架（graph coupling network），**把超表面内部的耦合效应显式纳入**，支持任意大尺寸；结合衍射理论与近–远场变换精确建模散射场；用微波实验验证。
- **为什么必读**：摘要明确点出痛点——“全波仿真太慢，而解析模型为了可解通常忽略耦合”。这篇是把“耦合”从误差项变成一等公民的代表作，且给出了实验闭环。

---

## 3. 前沿：长程耦合、大孔径、非局域

### 3.1 Revealing the Long-Range Coupling for Multi-Dimensional Metasurface Multiplexer
**O. Wu, C. Qian, G. You, H. Chen.** *Advanced Functional Materials* (2026), 75288. DOI: [10.1002/adfm.75288](https://doi.org/10.1002/adfm.75288)｜预印本 [arXiv:2601.11875](https://arxiv.org/abs/2601.11875)

- **核心发现**：存在一种**长程耦合，作用距离比倏逝波高一个量级**，且“表现出显著的图拓扑特征”——这句话是本方向的理论支点：**耦合的物理范围恰好由图结构承载**。
- **做法**：定制 GNN 抽象该物理；通过增强耦合把离散响应“抹平”成连续态，从而解锁多路复用通道；再把 GNN 嵌入逆向设计 agent，实现**角度 + 频率 + 偏振三维同时复用**；实验做出 8 通道紧凑复用器。
- **为什么必读**：目前把“图拓扑 ↔ 电磁耦合物理”讲得最深的一篇，也是从“代理模型”升级为“设计引擎”的范例。

### 3.2 Graph neural network-assisted optimization of large-aperture metalenses
**W. Mo, T. Zhu, N. Zhang, K. Liu, H. Sun.** *Optics & Laser Technology* (2026), 114359. DOI: [10.1016/j.optlastec.2025.114359](https://doi.org/10.1016/j.optlastec.2025.114359)

- **问题**：大孔径超透镜单元数上万，传统“单元独立设计 + 局部周期近似”在边缘/大角度入射下失效。
- **做法**：GNN 代理 + 优化，把整孔径当成耦合阵列来优化。
- **价值**：与 2.2 同属“大规模阵列可扩展性”主线，工程味更重，适合看它如何处理口径–算力权衡。

### 3.3 Nonlocal Interactions in Metasurfaces Harnessed by Neural Networks
**Y. Zhou, Q. Xu, Y. Liu, E. R. Martins, H. Liang, J. Li.** *Photonics* **12**(7), 738 (2025). DOI: [10.3390/photonics12070738](https://doi.org/10.3390/photonics12070738)

- 用神经网络刻画超表面中的**非局域（长程）相互作用**；与 3.1 讨论的是同一物理问题，可对照看“长程耦合到底该怎么参数化”。

---

## 4. 逆向设计：从 CNN 到图注意力

### 4.1 GAT-Net: Inverse design of multifunctional metasurface based on graph attention network
**Q. Bao, D. Zhang, X. Liu, T. Ma, J.-J. Xiao.** *Optics & Laser Technology* **183**, 112273 (2025). DOI: [10.1016/j.optlastec.2024.112273](https://doi.org/10.1016/j.optlastec.2024.112273)

- **做法**：用**图注意力网络（GAT）**替代 CNN/MLP 做多功能（多通道）超表面逆向设计；注意力机制自适应聚合邻域单元信息，天然适配非均匀阵列。
- **为什么读**：如果你想做“非周期/非均匀阵列”的逆向设计，GAT 比固定卷积核的 CNN 更合适；这篇是该路线的直接模板。其参考文献同时覆盖 Khoram 2022 与 An 2022（CNN 预测互耦），顺着它的引文表就能把这个子领域摸一遍。

---

## 5. 物理信息与可解释性

### 5.1 Physics-Informed GNNs for Interpretable Metasurface Near-Field Interaction Prediction
**J. Gu, W. Chen, C. Chen, X. Zhang, S. An.** *IEEE DCAS* (2026). DOI: [10.1109/dcas69364.2026.11544578](https://doi.org/10.1109/dcas69364.2026.11544578)

- 会议论文，很新：在 GNN 里加物理约束，预测超表面**近场相互作用**并强调可解释性。
- **价值**：代表“从黑箱代理走向物理一致”的趋势；Sensong An 组此前做过 CNN 预测互耦（*Adv. Opt. Mater.* 2022），这条线可以串起来看。

### 5.2 Physics-aware graph neural networks for optically interacting plasmonic nanoparticle assemblies
**A. A. Davidi, T. Pakizeh.** *Optics Express* (2026). DOI: [10.1364/oe.586635](https://doi.org/10.1364/oe.586635)

- 对象是**等离激元纳米颗粒组装体**——本质也是“颗粒阵列 + 光学相互作用”，与 meta-atom 阵列同构。
- **价值**：物理感知的图构造方式（谁和谁连边、边特征放什么）写得比光学超表面文献更细，可作为图设计参考。

### 5.3 Exploiting graph neural networks to perform finite-difference time-domain based optical simulations
**L. Kuhn, T. Repän, C. Rockstuhl.** *APL Photonics* **8**(3) (2023). DOI: [10.1063/5.0139004](https://doi.org/10.1063/5.0139004)

- 不学“输入→输出”映射，而是让 GNN **学 FDTD 的单步更新**（学算符而非学数据）。
- **价值**：这是提升外推能力最本质的一条思路，目前超表面 GNN 大多还是数据驱动，这里留了一个明显的方法学缺口。

---

## 6. 若“阵列”指天线阵/相控阵：另一条同构支线

### 6.1 Efficient Radiation Pattern Prediction of Array Antennas Based on Complex-Valued Graph Neural Networks
**J. Jin, Q. Su, Y. Xu, Z. He, Y. Lu.** *IEEE Antennas and Wireless Propagation Letters* **21**(12) (2022). DOI: [10.1109/lawp.2022.3197441](https://doi.org/10.1109/lawp.2022.3197441)

- **复数域 GNN**：直接处理幅度+相位（电磁场天然是复数），阵元作节点预测方向图。
- **价值**：复数算子是 EM 领域 GNN 与 CV 领域 GNN 的最大区别，这篇是最早把这点做对的之一。

### 6.2 Efficient 2-D Pattern Synthesis for Planar Series-Fed Microstrip Antenna Arrays Using Physics-Informed Graph Convolutional Networks
**Z. Bao, Y. Liu, Y. Li, C. Liang.** *IEEE Trans. Antennas Propag.* (2026). DOI: [10.1109/tap.2026.3652247](https://doi.org/10.1109/tap.2026.3652247)

- 物理信息 GCN 做**平面串馈阵的二维方向图综合**（综合 = 给定方向图反求激励，与超表面逆向设计同构）。

### 6.3 An efficient pattern prediction method of array antenna using graph neural network
**D. Li, F. Shi, Y. Zhao, S. Cai, Y. Li, D. Su.** *AEU – Int. J. Electron. Commun.* (2026). DOI: [10.1016/j.aeue.2026.156455](https://doi.org/10.1016/j.aeue.2026.156455)

- 工程化方向图预测；适合看 GNN 相对传统阵因子法的精度/速度折衷。

### 6.4 Physics-informed graph transformer for fast beam steering in a 128-channel optical phased array
**Y. Liu et al.** *Optics Express* (2026). DOI: [10.1364/oe.604264](https://doi.org/10.1364/oe.604264)

- **图 Transformer + 物理信息**，128 通道光学相控阵快速波束偏转。
- **价值**：把“图 + 注意力”推到 OPA 这种典型大规模阵列上，是 GNN→Graph Transformer 的趋势信号。

---

## 7. 可编程超表面 / RIS：GNN 用于“配置阵列”

这类工作不设计单元结构，而是**给定超表面阵列，用 GNN 求每个单元的相位/开关状态**（组合优化）。与器件物理距离远一些，但“阵列规模泛化 + 置换等变”的技巧可直接借用。

- **Investigating Large-Scale RIS-Assisted Wireless Communications Using GNN** — S. Lyu, L. Peng, S. Y. Chang. *IEEE Trans. Consumer Electron.* **70**(1) (2024). DOI: [10.1109/tce.2023.3349153](https://doi.org/10.1109/tce.2023.3349153)
- **A Graph Neural Network Learning Approach to Optimize RIS-Assisted Federated Learning** — Z. Wang, Y. Zhou, Y. Zou, Q. An, Y. Shi, M. Bennis. *IEEE Trans. Wireless Commun.* **22**, 6092–6106 (2023). DOI: [10.1109/twc.2023.3239400](https://doi.org/10.1109/twc.2023.3239400)
- **Graph Neural Network-Based Energy-Efficient Optimization for RIS-Assisted Wireless Networks** — B. Yin, J. Schampheleer, W. Joseph, M. Deruyck. *IEEE Trans. Wireless Commun.* **25**, 664–680 (2026). DOI: [10.1109/twc.2025.3585772](https://doi.org/10.1109/twc.2025.3585772)
- **Beamforming Design and Association Scheme for Multi-RIS Multi-User mmWave Systems Through Graph Neural Networks** — M. Liu, C. Huang, A. Alhammadi, M. Di Renzo, M. Debbah, C. Yuen. *IEEE Trans. Wireless Commun.* **24**, 7940–7954 (2025). DOI: [10.1109/twc.2025.3563529](https://doi.org/10.1109/twc.2025.3563529)

> 提示：这一支线体量很大（86 篇），但多数是通信优化问题，**不涉及单元间电磁耦合**。若你的兴趣是“器件级阵列”，读 2–3 篇了解 GNN 如何做规模泛化即可，不必深挖。

---

## 8. 综述与入门（先读这几篇定位）

| 文献 | 出处 | 用途 |
|---|---|---|
| **Deep learning in metasurfaces: from automated design to adaptive metadevices** — Y. Saifullah, N. Wu, H. Wang, B. Zheng, C. Qian, H. Chen | *Advanced Photonics* **7**(3), 034005 (2025). [DOI](https://doi.org/10.1117/1.ap.7.3.034005) | 最新、最对口的综述（被引 64），浙大陈红胜组，GNN 部分可信度高 |
| **From performance to structure: a comprehensive survey of advanced metasurface design for next-generation imaging** — Y. Zeng et al. | *npj Nanophotonics* (2025). [DOI](https://doi.org/10.1038/s44310-025-00081-6) | 内含专图 “Applications of graph-based methods in metasurface design”，可直接引用作“图方法已被综述承认”的证据 |
| **A newcomer's guide to deep learning for inverse design in nano-photonics** — A. Khaireh-Walieh et al. | *Nanophotonics* **12**(24) (2023). [DOI](https://doi.org/10.1515/nanoph-2023-0527) | 教程向，含 GNN 用于纳米光子逆向设计的入门章节 |
| **Large-scale photonic inverse design: computational challenges and breakthroughs** — C. Kang et al. | *Nanophotonics* **13**, 3765–3792 (2024). [DOI](https://doi.org/10.1515/nanoph-2024-0127) | 讲“规模”这件事：为什么阵列级设计必须换范式，GNN 是候选之一 |
| **Machine learning-based methods for frequency selective surfaces and metasurfaces** — B. Rana, I.-P. Hong | *J. Electromagn. Waves Appl.* **40**, 979–1012 (2026). [DOI](https://doi.org/10.1080/09205071.2025.2612299) | 微波 FSS 视角的 ML 综述，补全“周期阵列”的工程侧 |
| **Physics-informed learning in artificial electromagnetic materials** — Y. Deng, K. Fan, B. Jin, J. Malof, W. J. Padilla | *Applied Physics Reviews* **12** (2025). [DOI](https://doi.org/10.1063/5.0232675) | 物理信息学习的框架性综述，适合给 5.1 找理论定位 |

---

## 9. 相邻可借鉴（非 EM 超表面，但方法论直接可用）

- **Graph-based metamaterials: Deep learning of structure-property relations** — P. P. Meyer, C. Bonatti, T. Tancogne-Dejean, D. Mohr. *Materials & Design* **223**, 111175 (2022). [DOI](https://doi.org/10.1016/j.matdes.2022.111175)
  力学超材料，图表示 + 结构–性能映射；**如何把“几何”变成“图”**讲得比光学文献清楚。
- **A Tutorial on Controlling Metasurfaces from the Network Perspective** — C. Liaskos et al. arXiv:[2601.12118](https://arxiv.org/abs/2601.12118) (2026)
  把超表面当“波路由器”，用图论做系统级优化。**注意：是图论而非 GNN**，但“超表面 = 图”的世界观值得一读。
- **Physics-informed graph neural networks 用于 GHz 可重构天线逆向设计** — C. Pan, N. Verma, J. C. Sturm. *EuCAP* (2025). [DOI](https://doi.org/10.23919/eucap63536.2025.10999666)
  可重构天线（PIN/变容管）与可编程超表面单元同构，物理信息 GNN 的做法可平移。

---

## 10. 研究脉络（时间线）

```
2022  Khoram (ACS Photonics) ── GNN 代理阵列耦合，跨尺寸泛化   ← 范式确立
      Jin (AWPL) ── 复数域 GNN 预测阵列天线方向图
2023  Kuhn (APL Photonics) ── GNN 学 FDTD 算子（而非学数据）
      Khaireh-Walieh (Nanophotonics) ── 入门教程
2024  Wu (LPR) ── graph coupling network，任意尺寸 + 实验验证
      Bao (OLT) ── GAT-Net，图注意力做多功能逆向设计
      RIS 支线爆发（TWC/TCE 多篇）
2025  Mo (OLT) ── GNN 优化大孔径超透镜
      Zhou (Photonics) ── 非局域相互作用
      Saifullah (Adv. Photonics) ── 综述定性
2026  Wu (AFM) ── 长程耦合 + 图拓扑 + 8 通道复用器   ← 从“建模”到“发现物理”
      Gu/An (DCAS) ── 物理信息 + 可解释
      Davidi (Opt. Express) ── 物理感知 GNN 颗粒组装体
      Liu (Opt. Express) ── 图 Transformer + 128 通道 OPA
      Bao (TAP) ── 物理信息 GCN 做平面阵方向图综合
```

**读法**：2022 那篇决定“能不能做”，2024 LPR 决定“做得准不准”，2026 AFM 决定“能拿它发现什么”。三篇连读，这个方向就通了。

---

## 11. 相对空白（可作为选题切口）

> 以下为基于检索结果的判断，措辞为“较少见/相对空白”，不是绝对断言。

1. **异质图编码不同物理机制**。现有工作基本是“一种边 = 近场耦合”。但阵列里同时存在准静态近场、表面波、衍射级次间耦合，**长程耦合（3.1）已证明可超倏逝波一个量级**——用多种边类型/多层图分别编码，尚少系统研究。
2. **GNN 与严格求解器混合**。纯数据驱动外推差；Kuhn 的“学算子”路线在超表面阵列上几乎没人做。GNN 代理 + 伴随法梯度 / 区域分解（domain decomposition）是明显空位。
3. **制造误差与不确定性**。阵列越大误差累积越致命，但 GNN 的贝叶斯/集成不确定性量化在超表面设计中**几乎空白**；这对“大孔径”“晶圆级”应用是硬需求。
4. **等变性与对称性**。阵列有平移/旋转/周期对称性，E(3)/SE(2) 等变 GNN 在力学超材料已用（第 9 节），**在电磁超表面阵列上很少见**——理论上能大幅提升样本效率。
5. **可重构阵列的器件–物理–算法端到端**。RIS 支线的 GNN 大多停在通信指标（速率/能耗），输入是信道矩阵而非器件状态；把 PIN/液晶/相变材料的物理模型接进 GNN，“数字编码超表面 + GNN + 实测闭环”仍是空白。
6. **公开基准缺失**。除 Khoram 的 Tidy3D 数据集外，没有像 MetaNet/PIGMOS 那样被广泛接受的阵列耦合基准；**做数据集本身**就是可发表的工作。
7. **多物理场**。高功率下的热–力–电磁耦合阵列，GNN 代理几乎无人涉足。

---

## 12. 建议精读顺序（约 2 周）

| 顺序 | 文献 | 目的 |
|---|---|---|
| 1 | Khoram 2022 (ACS Photonics) + 其 GitHub | 搞清“图怎么建、边特征放什么、怎么跨尺寸” |
| 2 | Wu 2024 (LPR) | 看耦合如何被显式建模 + 实验怎么验 |
| 3 | Wu 2026 (AFM) + arXiv 全文 | 看“图拓扑 → 新物理 → 设计引擎”的完整链条 |
| 4 | Bao 2025 (GAT-Net) | 看 GAT 在非均匀阵列上的实现细节 |
| 5 | Saifullah 2025 (Adv. Photonics) 综述 | 定位自己的问题在版图里的位置 |
| 6 | Kuhn 2023 (APL Photonics) | 补“学算子”这条可能更有前途的技术路线 |
| 7 | 按需：阵列天线 4 篇 / RIS 2–3 篇 | 若你的“阵列”偏天线或可编程口径 |

---

## 13. 如何持续跟踪

- **OpenAlex 追引文**（无需订阅，最有效）：
  - `https://api.openalex.org/works?filter=cites:W4309791287`（Khoram 2022 的施引文献）
  - `https://api.openalex.org/works?filter=cites:W4401976209`（Wu 2024 的施引文献）
- **arXiv 订阅**：`physics.optics` + 关键词 `graph neural network`；该方向预印本通常先上 arXiv（3.1 即先 arXiv 后 AFM）。
- **Google Scholar 提醒**：对 Khoram 2022、Wu 2024 设 “Cited by” 提醒。
- **盯人**：Chao Qian / Hongsheng Chen（浙大）、Zongfu Yu（UW–Madison）、Sensong An（UNT）、Jun-Jun Xiao 组。

---

## 14. 局限说明

1. **中文文献未系统覆盖**：CNKI/万方需订阅，OpenAlex 对中文摘要索引很差（检索“图神经网络 + 超表面”返回大量无关结果）。建议在 CNKI 用「图神经网络」×「超表面 / 超构表面 / 反射阵列 / 超表面天线」自行补检，重点看《光学学报》《激光与光电子学进展》《物理学报》《红外与毫米波学报》。
2. **引文数仅供参考**：2025–2026 的新论文被引数尚不能反映影响力；个别低质量期刊的论文（如某些 GNN + 6G 超表面文章）被引数异常，已主动剔除。
3. **摘要可得性**：ACS/Wiley 部分论文的摘要在开放接口中缺失，相关评述依据题名、作者公开代码与引文上下文，已在正文中避免过度具体化。
4. **“超表面阵列”歧义**：已按「meta-atom 阵列」与「超表面天线阵/相控阵」两种理解分别给出（第 2–5 节 vs 第 6 节）。
