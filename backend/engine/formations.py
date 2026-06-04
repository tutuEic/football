"""
阵型因子 — 不同阵型的攻防加成和位置权重。
攻击系数 >1 表示偏进攻，<1 偏防守。
每个位置的权重之和决定球员属性对球队的贡献比例。
"""
FORMATIONS = {
    "4-3-3": {
        "name": "4-3-3",
        "label": "4-3-3 攻击",
        "positions": ["GK", "LB", "CB", "CB", "RB", "CM", "CM", "CM", "LW", "ST", "RW"],
        "attack_bonus": 1.10,
        "defense_bonus": 0.95,
        "position_weights": {
            "GK":  {"attack": 0.0,  "defense": 1.0},
            "CB":  {"attack": 0.1,  "defense": 0.9},
            "LB":  {"attack": 0.3,  "defense": 0.7},
            "RB":  {"attack": 0.3,  "defense": 0.7},
            "CM":  {"attack": 0.5,  "defense": 0.5},
            "LW":  {"attack": 0.9,  "defense": 0.1},
            "RW":  {"attack": 0.9,  "defense": 0.1},
            "ST":  {"attack": 1.0,  "defense": 0.0},
        }
    },
    "4-4-2": {
        "name": "4-4-2",
        "label": "4-4-2 均衡",
        "positions": ["GK", "LB", "CB", "CB", "RB", "LM", "CM", "CM", "RM", "ST", "ST"],
        "attack_bonus": 1.00,
        "defense_bonus": 1.00,
        "position_weights": {
            "GK":  {"attack": 0.0,  "defense": 1.0},
            "CB":  {"attack": 0.1,  "defense": 0.9},
            "LB":  {"attack": 0.2,  "defense": 0.8},
            "RB":  {"attack": 0.2,  "defense": 0.8},
            "CM":  {"attack": 0.5,  "defense": 0.5},
            "LM":  {"attack": 0.7,  "defense": 0.3},
            "RM":  {"attack": 0.7,  "defense": 0.3},
            "ST":  {"attack": 1.0,  "defense": 0.0},
        }
    },
    "3-5-2": {
        "name": "3-5-2",
        "label": "3-5-2 控场",
        "positions": ["GK", "CB", "CB", "CB", "LM", "CM", "CM", "CM", "RM", "ST", "ST"],
        "attack_bonus": 1.05,
        "defense_bonus": 1.00,
        "position_weights": {
            "GK":  {"attack": 0.0,  "defense": 1.0},
            "CB":  {"attack": 0.1,  "defense": 0.9},
            "CM":  {"attack": 0.5,  "defense": 0.5},
            "LM":  {"attack": 0.7,  "defense": 0.3},
            "RM":  {"attack": 0.7,  "defense": 0.3},
            "ST":  {"attack": 1.0,  "defense": 0.0},
        }
    },
    "5-4-1": {
        "name": "5-4-1",
        "label": "5-4-1 防守反击",
        "positions": ["GK", "LWB", "CB", "CB", "CB", "RWB", "CM", "CM", "LM", "RM", "ST"],
        "attack_bonus": 0.85,
        "defense_bonus": 1.15,
        "position_weights": {
            "GK":  {"attack": 0.0,  "defense": 1.0},
            "CB":  {"attack": 0.1,  "defense": 0.9},
            "LWB": {"attack": 0.3,  "defense": 0.7},
            "RWB": {"attack": 0.3,  "defense": 0.7},
            "CM":  {"attack": 0.4,  "defense": 0.6},
            "LM":  {"attack": 0.6,  "defense": 0.4},
            "RM":  {"attack": 0.6,  "defense": 0.4},
            "ST":  {"attack": 1.0,  "defense": 0.0},
        }
    },
    "4-2-3-1": {
        "name": "4-2-3-1",
        "label": "4-2-3-1 现代",
        "positions": ["GK", "LB", "CB", "CB", "RB", "CDM", "CDM", "CAM", "LW", "RW", "ST"],
        "attack_bonus": 1.08,
        "defense_bonus": 0.97,
        "position_weights": {
            "GK":  {"attack": 0.0,  "defense": 1.0},
            "CB":  {"attack": 0.1,  "defense": 0.9},
            "LB":  {"attack": 0.3,  "defense": 0.7},
            "RB":  {"attack": 0.3,  "defense": 0.7},
            "CDM": {"attack": 0.2,  "defense": 0.8},
            "CAM": {"attack": 0.8,  "defense": 0.2},
            "LW":  {"attack": 0.9,  "defense": 0.1},
            "RW":  {"attack": 0.9,  "defense": 0.1},
            "ST":  {"attack": 1.0,  "defense": 0.0},
        }
    },
}

def get_formation(name):
    """获取阵型配置，不存在返回默认 4-4-2"""
    return FORMATIONS.get(name, FORMATIONS["4-4-2"])

def list_formations():
    """列出所有可用阵型"""
    return [
        {"name": k, "label": v["label"], "positions": v["positions"]}
        for k, v in FORMATIONS.items()
    ]

def get_positions(formation_name):
    """获取某阵型的11个位置列表"""
    fm = get_formation(formation_name)
    return fm["positions"]
