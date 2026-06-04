# World Cup Prediction Engine v3 — Design Document

参照联赛预测引擎架构，重新设计世界杯预测模块。

---

## 1. 架构对比

```
联赛引擎                              世界杯引擎 (新设计)
─────────────────────────────         ─────────────────────────────
matches 表 (联赛比赛)                  tm_games + tm_appearances (国际赛)
feature_store (联赛特征)               wc_feature_store (国际赛特征)
Elo 系统 (联赛 Elo)                    wc_player_elo (球员 Elo)
Dixon-Coles (训练 per league)          Dixon-Coles (训练 on all internationals)
Poisson Regression                     Poisson Regression (国际赛特征)
XGBoost                               XGBoost (国际赛特征)
Stacking Ensemble                      Stacking Ensemble
Monte Carlo Simulator                  WC Tournament Simulator
training/pipeline.py                   wc_training/pipeline.py
models/registry.py                     wc_models/registry.py
```

---

## 2. 数据层

### 2.1 数据源
- `tm_games`: 国际比赛 (FIWC, EURO, COPA, AFAC, AFCN, WCQL, EUCON, UNL, FR...)
- `tm_appearances`: 球员出场 (进球、助攻、上场时间、红黄牌)
- `tm_players`: 球员元数据 (位置、国籍、市场价值)
- `wc_groups`: 世界杯分组、FIFA 排名、联盟信息

### 2.2 数据查询接口
```
backend/data/wc_match_repo.py  ← 新建
├── get_intl_matches(start_date, end_date, comp_ids)  → 比赛列表
├── get_team_intl_history(team, n_matches)            → 某队近期国际赛
├── get_head_to_head(team_a, team_b)                  → 交锋记录
└── get_tournament_matches(tournament, year)          → 某届赛事比赛
```

---

## 3. 特征工程

### 3.1 球员 Elo 特征 (已有 wc_player_elo.py)
- `team_avg_elo`: 队伍平均 Elo
- `top11_elo`: 最佳 11 人平均 Elo
- `gk_elo`, `df_elo`, `mf_elo`, `fw_elo`: 各位置 Elo
- `elo_depth`: 板凳深度 (top23 vs top11 差异)

### 3.2 队伍状态特征
```
backend/engine/wc_features.py  ← 新建
├── calc_intl_form(team, n=10)           → 近 N 场国际赛积分率
├── calc_intl_momentum(team, n=5)        → 近 5 场加权状态
├── calc_attack_strength(team)           → 近 10 场场均进球
├── calc_defense_strength(team)          → 近 10 场场均失球
├── calc_clean_sheet_rate(team)          → 零封率
├── calc_goal_diff_trend(team)           → 净胜球趋势
└── calc_discipline(team)                → 纪律评分 (红黄牌)
```

### 3.3 对阵特征
```
├── calc_head_to_head(team_a, team_b)    → 交锋历史
├── calc_confederation_diff(team_a, team_b) → 联盟实力差
├── calc_fifa_ranking_diff(team_a, team_b)  → FIFA 排名差
└── calc_style_matchup(team_a, team_b)   → 风格相克
```

### 3.3 赛事特征
```
├── calc_tournament_experience(team)     → 大赛经验
├── calc_stage_importance(stage)         → 比赛重要性
└── calc_host_advantage(team, venue)     → 主场优势
```

### 3.4 特征列表 (FEATURE_NAMES)
```python
WC_FEATURE_NAMES = [
    # 球员 Elo (8)
    'team_avg_elo', 'top11_elo', 'elo_depth',
    'gk_elo_diff', 'df_elo_diff', 'mf_elo_diff', 'fw_elo_diff',
    'star_player_elo',

    # 队伍状态 (8)
    'intl_form', 'intl_momentum',
    'attack_strength', 'defense_strength',
    'clean_sheet_rate', 'goal_diff_trend',
    'discipline', 'intl_experience',

    # 对阵 (4)
    'h2h_advantage', 'confed_diff',
    'fifa_ranking_diff', 'style_matchup',

    # 赛事 (3)
    'tournament_exp', 'stage_importance', 'home_advantage',
]
# Total: 23 features
```

---

## 4. 预测模型

### 4.1 Dixon-Coles (国际赛训练版)
```
backend/engine/wc_dixon_coles.py  ← 新建
```
- 在所有国际赛数据上训练 (10,000+ 场)
- 球队参数: attack/defense strength per team
- 用 Elo 作为先验 (Bayesian prior)
- rho 校准: group=0.10, knockout=-0.15
- gamma (主场优势): 从数据中学习

**训练策略:**
- 数据: 2014-2026 所有国际比赛
- 时间衰减: 近期比赛权重更高
- 分组: 按联盟分组训练 (UEFA, CONMEBOL, CAF...)
- 交叉验证: 按赛事类型留出验证

### 4.2 Elo-Poisson 模型
```
backend/engine/wc_elo_poisson.py  ← 新建
```
- 不需要训练，直接从 Elo 推导
- lambda = exp(alpha_home + beta_away + gamma)
- alpha/beta 从球员 Elo 计算
- 优势: 冷启动友好，新球队也能预测
- 劣势: 不如训练模型精确

### 4.3 Poisson Regression
```
backend/models/wc_poisson_regression.py  ← 新建
```
- 使用 23 个特征
- 训练数据: 国际比赛
- 输出: lambda_home, lambda_away → WDL 概率

### 4.4 XGBoost (可选)
```
backend/models/wc_xgboost.py  ← 新建
```
- 使用 23 个特征
- 直接预测 WDL 概率
- 需要足够训练数据 (1000+ 场)

---

## 5. 集成策略

### 5.1 Stacking Ensemble
```
backend/models/wc_stacking.py  ← 新建
```
- Meta-learner: Logistic Regression 或 Ridge
- 输入: 各基础模型的 WDL 预测
- 输出: 最终 WDL 概率

### 5.2 权重分配 (Fallback)
```python
WC_MODEL_WEIGHTS = {
    'wc_dc':        0.25,  # Dixon-Coles (训练版)
    'elo_poisson':  0.25,  # Elo-Poisson (无训练)
    'wc_poisson':   0.25,  # Poisson Regression
    'wc_xgboost':   0.15,  # XGBoost (如果可用)
    'tournament':   0.10,  # 赛事因素调整
}
```

### 5.3 预测流程
```
输入: home_team, away_team, context
    │
    ├── wc_features.py → 23 个特征
    │
    ├── wc_dixon_coles.predict()    → WDL_1
    ├── wc_elo_poisson.predict()    → WDL_2
    ├── wc_poisson.predict(features) → WDL_3
    ├── wc_xgboost.predict(features) → WDL_4 (可选)
    │
    ├── wc_stacking.predict([WDL_1, WDL_2, WDL_3, WDL_4])
    │   或 weighted_average(WDL_1, WDL_2, WDL_3, WDL_4)
    │
    └── 输出: final WDL, xG, score_distribution, factors
```

---

## 6. WC Tournament Simulator

### 6.1 小组赛模拟
```
backend/engine/wc_simulator.py  ← 已有，需升级
```
- Monte Carlo 模拟 10,000 次
- 每场比赛使用集成预测
- 计算: 晋级概率、小组排名分布、夺冠概率

### 6.2 淘汰赛模拟
- 16 强 → 8 强 → 4 强 → 决赛
- 加时赛/点球大战逻辑
- 淘汰赛 rho 调整 (-0.15)

### 6.3 夺冠概率
- 基于小组赛晋级概率 × 淘汰赛胜率
- 考虑对阵签表

---

## 7. 训练流水线

### 7.1 数据准备
```
backend/wc_training/pipeline.py  ← 新建
├── prepare_intl_dataset(start_date, end_date)
│   → X (features), y_home, y_away, matches
├── train_test_split (temporal: 2014-2024 train, 2024-2026 test)
└── feature_scaling (StandardScaler)
```

### 7.2 模型训练
```
├── train_wc_dixon_coles(matches)
│   → 保存 wc_models/dc_intl_2526.json
├── train_wc_poisson(X, y_home, y_away)
│   → 保存 wc_models/poisson_intl_2526.json
├── train_wc_xgboost(X, y_home, y_away)  (可选)
│   → 保存 wc_models/xgboost_intl_2526.json
└── train_wc_stacking(base_predictions, y)
    → 保存 wc_models/stacking_intl_2526.json
```

### 7.3 评估
```
├── Brier Score (WDL 概率准确性)
├── Log Loss
├── 校准图 (Calibration Plot)
└── 按赛事类型分组评估
```

---

## 8. API 接口

### 8.1 预测接口 (已有，需升级)
```
POST /api/predict/wc
{
    "home_team": "France",
    "away_team": "Brazil",
    "context": {"stage": "group", "matchday": 1}
}

Response:
{
    "wdl": {"home_win": 0.45, "draw": 0.22, "away_win": 0.33},
    "expected_goals": {"home": 1.35, "away": 1.10},
    "score_distribution": {...},
    "factors": {
        "elo": {...},
        "form": {...},
        "tournament": {...},
        "models": {"dc": {...}, "elo_poisson": {...}, ...}
    },
    "model_version": "wc_v3_ensemble"
}
```

### 8.2 模拟接口 (已有，需升级)
```
POST /api/simulate/wc
{
    "n_simulations": 10000
}

Response:
{
    "group_standings": {...},
    "knockout_bracket": {...},
    "champion_probabilities": {
        "France": 0.12,
        "Brazil": 0.10,
        "England": 0.09,
        ...
    }
}
```

---

## 9. 目录结构

```
backend/
├── data/
│   └── wc_match_repo.py          ← 新建: 国际比赛数据查询
│
├── features/
│   └── wc_features.py            ← 新建: 国际赛特征计算
│
├── engine/
│   ├── wc_predictor.py           ← 重构: 集成入口
│   ├── wc_dixon_coles.py         ← 新建: 训练版 DC
│   ├── wc_elo_poisson.py         ← 新建: Elo-Poisson 模型
│   ├── wc_player_elo.py          ← 已有: 球员 Elo
│   ├── wc_elo_adapter.py         ← 已有: Elo 适配层
│   ├── wc_data.py                ← 已有: 队伍元数据
│   └── wc_simulator.py           ← 升级: 赛事模拟器
│
├── models/
│   ├── wc_poisson_regression.py  ← 新建: Poisson 回归
│   ├── wc_xgboost.py             ← 新建: XGBoost (可选)
│   └── wc_stacking.py            ← 新建: Stacking 集成
│
├── wc_models/                    ← 新建: WC 模型存储
│   ├── dc_intl_2526.json
│   ├── poisson_intl_2526.json
│   ├── stacking_intl_2526.json
│   └── registry.json
│
└── wc_training/
    └── pipeline.py               ← 新建: 训练流水线
```

---

## 10. 实施计划

### Phase 1: 数据层 + 特征 (优先)
1. `wc_match_repo.py` — 国际比赛数据查询
2. `wc_features.py` — 23 个特征计算

### Phase 2: 基础模型
3. `wc_dixon_coles.py` — 训练版 DC
4. `wc_elo_poisson.py` — Elo-Poisson 模型

### Phase 3: 高级模型 + 集成
5. `wc_poisson_regression.py` — Poisson 回归
6. `wc_stacking.py` — Stacking 集成
7. 重构 `wc_predictor.py` — 统一入口

### Phase 4: 训练 + 评估
8. `wc_training/pipeline.py` — 训练流水线
9. 模型评估和调优

### Phase 5: 模拟器升级
10. 升级 `wc_simulator.py` — 使用集成预测

---

## 11. 与联赛引擎的关键差异

| 方面 | 联赛引擎 | 世界杯引擎 |
|------|----------|------------|
| 训练数据 | 每联赛 500+ 场/赛季 | 全球 10,000+ 场国际赛 |
| 球队数量 | 18-20 队/联赛 | 200+ 国家队 |
| 比赛频率 | 每周 1 场 | 每年 10-15 场 |
| 球员数据 | 俱乐部出场 | 俱乐部 + 国际赛出场 |
| 主场优势 | 明确 (固定球场) | 模糊 (中立场多) |
| 球队稳定性 | 高 (同一赛季) | 低 (大名单常变) |
| 特征重点 | 近期状态 + 交锋 | 球员质量 + 大赛经验 |
| rho 参数 | -0.13 (联赛) | 0.10/-0.15 (阶段不同) |
