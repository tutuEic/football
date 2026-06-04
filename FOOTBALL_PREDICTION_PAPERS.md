# 足球预测论文调研

## 核心论文

### 1. Dixon & Coles (1997) — 奠基之作
**"Modelling Association Football Scores and Inefficiencies in the Football Betting Market"**
- DOI: 10.1111/1467-9876.00065
- 方法: Poisson 分布 + rho 修正参数（低比分相关性）
- 贡献: 建立了 football prediction 的标准框架
- 参数: attack strength (alpha), defence strength (beta), home advantage (gamma), rho

### 2. Groll, Schauberger, Tutz (2015) — 世界杯预测专用 ⭐
**"Prediction of major international soccer tournaments based on team-specific regularized Poisson regression: An application to the FIFA World Cup 2014"**
- DOI: 10.1515/jqas-2014-0051
- 方法: 正则化 Poisson 回归 + 多种协变量
- 特征: FIFA 排名、博彩赔率、主场优势、球员市场价值、联赛质量等
- 训练: 历届世界杯数据
- 贡献: **直接适用于世界杯预测**，包含赛事模拟

### 3. Schauberger & Groll (2018) — 随机森林世界杯预测 ⭐
**"Predicting matches in international football tournaments with random forests"**
- DOI: 10.1177/1471082x18799934
- 方法: Random Forest vs Poisson 回归 vs 排序模型
- 数据: 2002-2014 四届世界杯
- 结论: Random Forest 在世界杯预测上优于传统 Poisson
- 贡献: **机器学习方法在国际赛事预测中的应用**

### 4. Baio & Blangiardo (2010) — Bayesian 层级模型
**"Bayesian hierarchical model for the prediction of football results"**
- DOI: 10.1080/02664760802684177
- 方法: Bayesian 层级 Poisson 模型
- 贡献: 攻防参数的贝叶斯估计，处理小样本问题
- 适用: **国家队比赛样本少，Bayesian 方法更稳健**

### 5. Zou, Song, Shi (2020) — 动态 Bayesian 预测
**"A Bayesian In-Play Prediction Model for Association Football Outcomes"**
- DOI: 10.3390/app10082904
- 方法: 动态强度模型 + Bayesian 更新
- 贡献: 比赛中实时更新球队强度估计
- 适用: **可以借鉴实时更新思路用于赛事进程中**

### 6. Chen (2025) — 混合 ML 框架 + Bivariate Poisson ⭐
**"A Hybrid Machine Learning Framework for Soccer Match Outcome Prediction: Incorporating Bivariate Poisson Distribution"**
- DOI: 10.1051/itmconf/20257003020
- 方法: Bivariate Poisson + 机器学习集成
- 贡献: **最新研究，结合统计模型和 ML**

### 7. Fischer & Heuer (2025) — ML vs Poisson 对比
**"Match Predictions in Soccer: Machine Learning vs. Poisson Approaches"**
- DOI: 10.1007/978-3-662-70155-3_7
- 方法: 系统对比 ML 和 Poisson 方法
- 贡献: **方法论对比，帮助选择最佳方案**

### 8. Berrar, Lopes, Dubitzky (2019) — 领域知识 + ML
**"Incorporating domain knowledge in machine learning for soccer outcome prediction"**
- DOI: 10.1007/s10994-018-5747-8
- 方法: 将足球领域知识融入 ML 模型
- 贡献: **特征工程指导**

### 9. Jung & Jung (2025) — Elo 评级趋势分析
**"Data-driven understanding on soccer team tactics and ranking trends: Elo rating-based trends on European soccer leagues"**
- DOI: 10.1371/journal.pone.0318485
- 方法: Elo 评级 + 战术趋势分析
- 贡献: **Elo 系统在足球中的应用**

### 10. Wang (2010) — 世界杯 Poisson 模拟
**"Soccer tournament simulation and analysis for South Africa World Cup with Poisson model of goal probability"**
- DOI: 10.1109/ccdc.2010.5498512
- 方法: Poisson 模型 + 赛事模拟
- 贡献: **世界杯赛制模拟方法**

---

## 方法论总结

### 统计模型
| 模型 | 优点 | 缺点 | 代表论文 |
|------|------|------|----------|
| Dixon-Coles | 经典、可解释 | 需要大量联赛数据 | Dixon & Coles 1997 |
| Poisson 回归 | 简单、可加协变量 | 假设独立 | Groll et al. 2015 |
| Bayesian 层级 | 处理小样本、不确定性 | 计算复杂 | Baio & Blangiardo 2010 |
| Bivariate Poisson | 考虑进球相关性 | 参数估计难 | Chen 2025 |

### 机器学习模型
| 模型 | 优点 | 缺点 | 代表论文 |
|------|------|------|----------|
| Random Forest | 非线性、特征重要性 | 需要大量特征 | Schauberger & Groll 2018 |
| XGBoost | 高精度、正则化 | 黑箱 | 通用方法 |
| Neural Network | 捕捉复杂模式 | 需要大数据、过拟合 | 通用方法 |
| Stacking Ensemble | 结合多个模型 | 复杂 | Chen 2025 |

### 关键发现
1. **世界杯预测的特殊性**: 样本少（每队每届 3-7 场），需要 Bayesian 或正则化方法
2. **特征重要性**: FIFA 排名、博彩赔率、球员市场价值是最强预测因子
3. **集成方法**: Stacking 通常优于单一模型
4. **主场优势**: 国际赛事中主场优势较小（中立场多）
5. **赛事模拟**: Monte Carlo 模拟是标准方法

---

## 对我们设计的启示

### 1. 数据层面
- 国际比赛样本少 → 需要 Bayesian 方法或正则化
- 球员数据是独特优势 → 市场价值、联赛质量
- 博彩赔率是强特征 → 如果可用应该加入

### 2. 模型层面
- **基础**: Dixon-Coles + Bayesian prior (from Elo)
- **进阶**: Poisson 回归 + 23 个特征 (参照 Groll 2015)
- **高级**: Random Forest / XGBoost (参照 Schauberger 2018)
- **集成**: Stacking (参照 Chen 2025)

### 3. 赛事模拟
- Monte Carlo 模拟是标准方法 (参照 Wang 2010)
- 需要考虑赛制: 小组赛 + 淘汰赛 + 加时/点球

### 4. 评估
- Brier Score、Log Loss 是标准指标
- 需要按赛事阶段分组评估
