# 瓒崇悆棰勬祴娌欑洏绯荤粺 鈥?鍏ㄦ爤寮€鍙戣鍒?v2

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** 浠庨浂鎼缓涓€涓甫娌欑洏鎺ㄦ紨鐨勫叏鏍堣冻鐞冮娴嬬郴缁熲€斺€旇嚜瀹氫箟闃靛瀷/鐞冨憳 鈫?钂欑壒鍗℃礇妯℃嫙 鈫?鑳滃钩璐熸鐜?+ 姣斿垎鍒嗗竷 + EV+ 鎵弿銆?
**Architecture:** Python FastAPI 鍚庣 + React 鍓嶇銆傚悗绔粺涓€鐢?`soccerdata` 搴撴浛浠ｆ墜鍔ㄧ埇铏紙SoFIFA 鎻愪緵 FIFA 0-99 鐞冨憳璇勫垎锛夛紝鏍稿績寮曟搸鑷爺 MonteCarloSimulator 鐢?Dixon-Coles + 娉婃澗鎶芥牱銆傚墠绔敤 `react-soccer-lineup` 鐢婚樀鍨嬨€乣campos-react` 鐢荤儹鍔涘浘/闆疯揪鍥俱€?
**Tech Stack:** Python 3.13 (Windows) + FastAPI + scipy/numpy + soccerdata + MySQL | React 18 + Vite + TailwindCSS + react-soccer-lineup + campos-react + recharts

---

## 鎬昏

```
Phase 1 鈻堚枅鈻堚枅鈻堚枅鈻堚枅鈻堚枅鈻堚枅鈻堚枅鈻堚枅  椤圭洰楠ㄦ灦 + 鏁版嵁灞?         3h
Phase 2 鈻堚枅鈻堚枅鈻堚枅鈻堚枅鈻堚枅鈻堚枅鈻堚枅鈻堚枅  FastAPI 鍚庣鍏ㄦ帴鍙?        4h
Phase 3 鈻堚枅鈻堚枅鈻堚枅鈻堚枅鈻堚枅鈻堚枅鈻堚枅鈻堚枅  妯℃嫙寮曟搸 (MonteCarlo)       4h
Phase 4 鈻堚枅鈻堚枅鈻堚枅鈻堚枅鈻堚枅鈻堚枅鈻堚枅鈻堚枅  React 鍓嶇 5 椤甸潰          6h
Phase 5 鈻堚枅鈻堚枅鈻堚枅鈻堚枅鈻堚枅鈻堚枅鈻堚枅鈻堚枅  妯″瀷鍗囩骇 + 鍥炴祴             4h
                        鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
                        鍚堣 ~21h
```

---

## 绯荤粺鏋舵瀯

```
鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?鈹?                   React Frontend  :5173                     鈹?鈹?                                                            鈹?鈹? 馃搳浠〃鐩? 馃搮棰勬祴  馃幃娌欑洏  馃搱鐞冮槦  馃挵EV                    鈹?鈹?                                                            鈹?鈹? 缁勪欢搴?                                                    鈹?鈹? react-soccer-lineup  鈫?闃靛瀷鍙鍖栵紙娌欑洏椤电悆鍦猴級             鈹?鈹? campos-react         鈫?shot map / heatmap / radar          鈹?鈹? recharts             鈫?鎶樼嚎鍥?/ 鏌辩姸鍥?                    鈹?鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?                       鈹?REST JSON
                       鈻?鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?鈹?                 FastAPI Backend  :8000                      鈹?鈹?                                                            鈹?鈹? /api/sandbox/simulate  鈫?鏍稿績锛氳窇 N 娆¤挋鐗瑰崱娲?            鈹?鈹? /api/predict           鈫?蹇€熼娴嬶紙鏁版嵁搴撶悆闃燂級            鈹?鈹? /api/players/search    鈫?鐞冨憳鎼滅储锛圖B 鈫?SoFIFA 鈫?web锛?   鈹?鈹? /api/players/custom    鈫?鍒涘缓鑷畾涔夌悆鍛?                  鈹?鈹? /api/odds/*            鈫?璧旂巼瀵规瘮 + EV 鎵弿               鈹?鈹? /api/teams/*           鈫?鐞冮槦鍒嗘瀽                         鈹?鈹?                                                            鈹?鈹? 鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?  鈹?鈹? 鈹? MonteCarloSimulator                                鈹?  鈹?鈹? 鈹? 鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹? 鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹? 鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹? 鈹?  鈹?鈹? 鈹? 鈹?SquadA    鈹? 鈹?Strength   鈹? 鈹?Poisson        鈹? 鈹?  鈹?鈹? 鈹? 鈹?Formation 鈹傗啋 鈹?Calculator 鈹傗啋 鈹?Sampler        鈹? 鈹?  鈹?鈹? 鈹? 鈹?Players[] 鈹? 鈹?伪, 尾       鈹? 鈹?(位,渭) 鈫?score  鈹? 鈹?  鈹?鈹? 鈹? 鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹? 鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹? 鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹攢鈹€鈹€鈹€鈹€鈹€鈹€鈹? 鈹?  鈹?鈹? 鈹?                                        鈹?x N      鈹?  鈹?鈹? 鈹? 鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?         鈹?  鈹?鈹? 鈹? 鈹? Aggregator                                    鈹?  鈹?鈹? 鈹? 鈹? W/D/L% + avg_goals + score_dist               鈹?  鈹?鈹? 鈹? 鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?  鈹?鈹? 鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?  鈹?鈹?                                                            鈹?鈹? 鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?  鈹?鈹? 鈹? PlayerResolver (鐞冨憳瑙ｆ瀽涓夐€氶亾)                     鈹?  鈹?鈹? 鈹? 鈶?MySQL (football_odds.teams + transfermarkt)       鈹?  鈹?鈹? 鈹? 鈶?SoFIFA (FIFA 0-99 璇勫垎锛寁ia soccerdata)           鈹?  鈹?鈹? 鈹? 鈶?Web search (ESPN / Transfermarkt 鍏滃簳)            鈹?  鈹?鈹? 鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?  鈹?鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?                       鈹?                       鈻?鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?鈹?             Data Layer                                     鈹?鈹?                                                            鈹?鈹? soccerdata (Python)          MySQL 8.0 (Windows)           鈹?鈹? 鈹溾攢鈹€ SoFIFA 鈫?鐞冨憳璇勫垎       鈹溾攢鈹€ football_odds (鍙)       鈹?鈹? 鈹溾攢鈹€ FBref 鈫?璧涘缁熻        鈹?  578K matches + odds        鈹?鈹? 鈹溾攢鈹€ Understat 鈫?xG/xA       鈹斺攢鈹€ football_pred (鏂板缓)       鈹?鈹? 鈹溾攢鈹€ ESPN 鈫?璧涚▼/绉垎姒?         models | predictions       鈹?鈹? 鈹斺攢鈹€ ClubElo 鈫?Elo 璇勫垎           ev_scans | custom_players 鈹?鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?```

---

## 鍏抽敭搴撹鏄庯紙涓轰粈涔堥€夊畠浠級

| 搴?| 浣滅敤 | 鏇夸唬浜嗕綘鐜版湁鐨勪粈涔?|
|---|------|-------------------|
| `soccerdata` | 缁熶竴鎶?SoFIFA/FBref/Understat/ESPN/WhoScored | `D:\xiaoli\scripts\` 涓?30+ 涓埇铏?|
| `react-soccer-lineup` | SVG 鐞冨満 + 11 浜洪樀鍨嬬珯浣?| 鎵嬪啓 SVG锛堢渷 200+ 琛岋級 |
| `@withqwerty/campos-react` | xG 鐑姏鍥?/ shot map / 闆疯揪鍥?/ pass network | 鎵嬪啓 D3/Canvas |
| `recharts` | 浠〃鐩樻姌绾垮浘/鏌辩姸鍥撅紙姣斿垎鍒嗗竷鐩存柟鍥撅級 | 鎵嬪啓 chart |

---

## 鐞冨憳鏁版嵁妯″瀷 (PlayerCard)

```python
# 鏁版嵁搴撳瓨鍌ㄦ牸寮?{
  "id": "sofifa:231747",           # 鍞竴鏍囪瘑
  "name": "Erling Haaland",
  "source": "sofifa",              # "mysql" | "sofifa" | "custom" | "web"
  
  # 鏍稿績灞炴€?(0-99锛孲oFIFA 鏍囧噯)
  "att": {
    "pace": 89,        "shooting": 94,    "passing": 72,
    "dribbling": 82,   "defending": 35,   "physical": 88
  },
  
  # 浣嶇疆
  "position": "ST",
  "positions": ["ST", "CF"],        # 鍙墦浣嶇疆
  
  # 琛嶇敓灞炴€э紙浠?att 璁＄畻锛?  "attack_rating": 94,             # = shooting * 0.6 + dribbling * 0.3 + pace * 0.1
  "defense_rating": 35,            # = defending * 0.8 + physical * 0.2
  "overall": 91,
  
  # 鍏冩暟鎹?  "market_value": "鈧?80M",
  "club": "Manchester City",
  "league": "Premier League",
  "data_url": "https://sofifa.com/player/231747"
}
```

---

## 椤圭洰鐩綍缁撴瀯

```
D:\xiaoli\football-pred-system\
鈹?鈹溾攢鈹€ backend\
鈹?  鈹溾攢鈹€ main.py                     # FastAPI 鍏ュ彛
鈹?  鈹溾攢鈹€ config.py                   # 鏁版嵁搴?璺緞閰嶇疆
鈹?  鈹?鈹?  鈹溾攢鈹€ api\
鈹?  鈹?  鈹溾攢鈹€ __init__.py
鈹?  鈹?  鈹溾攢鈹€ matches.py              # GET /api/matches, /api/leagues
鈹?  鈹?  鈹溾攢鈹€ predict.py              # POST /api/predict
鈹?  鈹?  鈹溾攢鈹€ sandbox.py              # POST /api/sandbox/simulate  馃啎
鈹?  鈹?  鈹溾攢鈹€ players.py              # GET /api/players/search  馃啎
鈹?  鈹?  鈹溾攢鈹€ teams.py                # GET /api/teams
鈹?  鈹?  鈹溾攢鈹€ odds.py                 # GET /api/odds/compare, /scan
鈹?  鈹?  鈹斺攢鈹€ models.py               # GET /api/models
鈹?  鈹?鈹?  鈹溾攢鈹€ engine\
鈹?  鈹?  鈹溾攢鈹€ __init__.py
鈹?  鈹?  鈹溾攢鈹€ simulator.py            # 馃啎 MonteCarloSimulator
鈹?  鈹?  鈹溾攢鈹€ strength.py             # 馃啎 鐞冨憳鈫掔悆闃熷己搴﹁绠楀櫒
鈹?  鈹?  鈹溾攢鈹€ formations.py           # 馃啎 闃靛瀷閰嶇疆 (4-3-3 / 4-4-2 / 3-5-2...)
鈹?  鈹?  鈹溾攢鈹€ predictor.py            # DixonColes 棰勬祴鍣紙蹇€熸ā寮忥級
鈹?  鈹?  鈹溾攢鈹€ trainer.py              # 妯″瀷璁粌鍣?鈹?  鈹?  鈹溾攢鈹€ backtest.py             # 鍥炴祴妗嗘灦
鈹?  鈹?  鈹斺攢鈹€ ev_scanner.py           # EV+ 鎵弿
鈹?  鈹?鈹?  鈹溾攢鈹€ data\
鈹?  鈹?  鈹溾攢鈹€ __init__.py
鈹?  鈹?  鈹溾攢鈹€ mysql_client.py         # MySQL 杩炴帴姹?鈹?  鈹?  鈹溾攢鈹€ match_repo.py           # 姣旇禌鏁版嵁鏌ヨ
鈹?  鈹?  鈹溾攢鈹€ odds_repo.py            # 璧旂巼鏁版嵁鏌ヨ
鈹?  鈹?  鈹溾攢鈹€ sofifa_client.py        # 馃啎 SoFIFA 鏁版嵁鑾峰彇锛堝皝瑁?soccerdata锛?鈹?  鈹?  鈹斺攢鈹€ player_repo.py          # 馃啎 鐞冨憳 CRUD
鈹?  鈹?鈹?  鈹溾攢鈹€ models\                     # 璁粌濂界殑妯″瀷鍙傛暟 JSON
鈹?  鈹?  鈹斺攢鈹€ dc_E0_2425.json
鈹?  鈹?鈹?  鈹斺攢鈹€ tests\
鈹?      鈹溾攢鈹€ test_strength.py
鈹?      鈹斺攢鈹€ test_simulator.py
鈹?鈹溾攢鈹€ frontend\
鈹?  鈹溾攢鈹€ index.html
鈹?  鈹溾攢鈹€ package.json
鈹?  鈹溾攢鈹€ vite.config.js
鈹?  鈹斺攢鈹€ src\
鈹?      鈹溾攢鈹€ main.jsx
鈹?      鈹溾攢鈹€ App.jsx
鈹?      鈹溾攢鈹€ index.css
鈹?      鈹溾攢鈹€ api.js                  # axios/fetch 灏佽
鈹?      鈹溾攢鈹€ pages\
鈹?      鈹?  鈹溾攢鈹€ Dashboard.jsx
鈹?      鈹?  鈹溾攢鈹€ Predictions.jsx
鈹?      鈹?  鈹溾攢鈹€ Sandbox.jsx         # 馃啎 娌欑洏鎺ㄦ紨锛堟牳蹇冮〉闈級
鈹?      鈹?  鈹溾攢鈹€ TeamAnalysis.jsx
鈹?      鈹?  鈹斺攢鈹€ EVScanner.jsx
鈹?      鈹斺攢鈹€ components\
鈹?          鈹溾攢鈹€ PitchFormation.jsx  # 馃啎 鐞冨満闃靛瀷锛堝寘瑁?react-soccer-lineup锛?鈹?          鈹溾攢鈹€ PlayerSlot.jsx      # 馃啎 鍙紪杈戠悆鍛樻Ы浣?鈹?          鈹溾攢鈹€ PlayerSearch.jsx    # 馃啎 鐞冨憳鎼滅储寮圭獥
鈹?          鈹溾攢鈹€ CustomPlayerModal.jsx  # 馃啎 鑷畾涔夌悆鍛樺脊绐?鈹?          鈹溾攢鈹€ ScoreHeatmap.jsx    # 姣斿垎姒傜巼鐑姏鍥?鈹?          鈹溾攢鈹€ MatchCard.jsx       # 姣旇禌鍗＄墖
鈹?          鈹溾攢鈹€ SortableEVList.jsx  # EV+ 鎺掑簭鍒楄〃
鈹?          鈹斺攢鈹€ ProbBar.jsx         # 姒傜巼鏉?鈹?鈹溾攢鈹€ start.bat                       # 涓€閿惎鍔?鈹溾攢鈹€ create_pred_db.sql              # football_pred 寤哄簱鑴氭湰
鈹斺攢鈹€ DEVELOPMENT_PLAN.md
```

---

## Phase 1锛氶」鐩鏋?+ 鏁版嵁灞傦紙~3h锛?
> 浜у嚭锛歅ython 鑳借繛 MySQL 璇绘暟鎹紝soccerdata 鑳芥姄鍒?SoFIFA 鐞冨憳璇勫垎銆?
### Task 1.1 鈥?鍒涘缓椤圭洰鐩綍缁撴瀯

```bash
mkdir -p /mnt/d/xiaoli/football-pred-system/backend/{api,engine,data,models,tests}
mkdir -p /mnt/d/xiaoli/football-pred-system/frontend/src/{pages,components}
```

楠岃瘉锛歚ls -R /mnt/d/xiaoli/football-pred-system/backend/`

### Task 1.2 鈥?Windows 渚у畨瑁?Python 渚濊禆

鍦?Windows 鍛戒护琛岋紙闈?WSL锛変腑杩愯锛?
```cmd
cd D:\xiaoli\football-pred-system
pip install fastapi uvicorn mysql-connector-python numpy scipy pandas soccerdata
```

楠岃瘉锛歚python -c "import soccerdata; print('soccerdata OK')"`

### Task 1.3 鈥?閰嶇疆鏂囦欢 `backend/config.py`

```python
"""鍏ㄥ眬閰嶇疆鏂囦欢"""
import os

# MySQL锛圵indows 鏈湴锛?MYSQL_HOST = "localhost"
MYSQL_PORT = 3306
MYSQL_USER = "root"
MYSQL_PASS = "123456"
MYSQL_DB_SOURCE = "football_odds"
MYSQL_DB_PRED  = "football_pred"

# 妯″瀷瀛樺偍
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, "models")
os.makedirs(MODEL_DIR, exist_ok=True)

# SoFIFA 缂撳瓨
SOFIFA_CACHE = os.path.join(os.path.dirname(BASE_DIR), "data", "sofifa_cache")
```

### Task 1.4 鈥?MySQL 杩炴帴姹?`backend/data/mysql_client.py`

```python
"""MySQL 杩炴帴绠＄悊"""
import mysql.connector
from mysql.connector import pooling
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASS

_pool = None

def get_pool():
    global _pool
    if _pool is None:
        _pool = pooling.MySQLConnectionPool(
            pool_name="fb_pool", pool_size=5,
            host=MYSQL_HOST, port=MYSQL_PORT,
            user=MYSQL_USER, password=MYSQL_PASS,
            charset="utf8mb4"
        )
    return _pool

def query(sql, params=None, db="football_odds"):
    conn = get_pool().get_connection()
    conn.database = db
    cursor = conn.cursor(dictionary=True)
    cursor.execute(sql, params or ())
    rows = cursor.fetchall()
    cursor.close(); conn.close()
    return rows

def execute(sql, params=None, db="football_pred"):
    conn = get_pool().get_connection()
    conn.database = db
    cursor = conn.cursor()
    cursor.execute(sql, params or ())
    conn.commit()
    last_id = cursor.lastrowid
    cursor.close(); conn.close()
    return last_id
```

楠岃瘉锛歚python -c "from backend.data.mysql_client import query; print(query('SELECT 1 AS ok'))"`

### Task 1.5 鈥?鍒涘缓棰勬祴鏁版嵁搴?`create_pred_db.sql`

```sql
CREATE DATABASE IF NOT EXISTS football_pred
    DEFAULT CHARACTER SET utf8mb4 DEFAULT COLLATE utf8mb4_unicode_ci;
USE football_pred;

-- 妯″瀷鐗堟湰
CREATE TABLE model_versions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    version VARCHAR(20) NOT NULL,
    model_type VARCHAR(20) NOT NULL,
    league_code VARCHAR(10),
    season VARCHAR(10),
    params_json LONGTEXT NOT NULL,
    metrics_json JSON,
    is_active BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- 棰勬祴璁板綍
CREATE TABLE predictions (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    model_id INT NOT NULL,
    match_id BIGINT,
    home_team VARCHAR(100), away_team VARCHAR(100),
    league_code VARCHAR(10),
    home_win DECIMAL(6,4), draw DECIMAL(6,4), away_win DECIMAL(6,4),
    exp_home_goals DECIMAL(6,4), exp_away_goals DECIMAL(6,4),
    score_probs_json LONGTEXT,
    actual_result CHAR(1),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (model_id) REFERENCES model_versions(id)
) ENGINE=InnoDB;

-- 鑷畾涔夌悆鍛?CREATE TABLE custom_players (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    source VARCHAR(20) DEFAULT 'custom',
    position VARCHAR(5),
    pace TINYINT, shooting TINYINT, passing TINYINT,
    dribbling TINYINT, defending TINYINT, physical TINYINT,
    attack_rating TINYINT, defense_rating TINYINT, overall TINYINT,
    data_json JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- EV 鎵弿璁板綍
CREATE TABLE ev_scans (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    prediction_id BIGINT NOT NULL,
    bookmaker VARCHAR(20),
    model_prob DECIMAL(6,4), market_odds DECIMAL(8,2),
    fair_odds DECIMAL(8,2), ev DECIMAL(8,4),
    is_value BOOLEAN,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;
```

鎵ц锛歚mysql -u root -p123456 < create_pred_db.sql`

### Task 1.6 鈥?SoFIFA 鏁版嵁瀹㈡埛绔?`backend/data/sofifa_client.py`

```python
"""SoFIFA 鐞冨憳鏁版嵁瀹㈡埛绔?鈥?灏佽 soccerdata"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import SOFIFA_CACHE
import pandas as pd
import json

def get_player_ratings(league="Premier League", version="latest"):
    """
    鑾峰彇鏌愯仈璧涙墍鏈夌悆鍛樼殑 FIFA 璇勫垎
    杩斿洖 DataFrame锛屽垪: name, age, overall, pace, shooting, passing,
                        dribbling, defending, physical, position, club
    """
    from soccerdata import SoFIFA
    sofifa = SoFIFA(
        leagues=league,
        versions=version,
        data_dir=SOFIFA_CACHE
    )
    return sofifa.read_players()

def search_player(name, league=None):
    """
    鎼滅储鐞冨憳锛岃繑鍥?PlayerCard dict
    鍏堝湪 SoFIFA 缂撳瓨鎵撅紝鎵句笉鍒版爣璁颁负闇€瑕?web 鎼滅储
    """
    # 璇诲彇 SoFIFA 缂撳瓨鏁版嵁
    import glob
    cache_files = glob.glob(os.path.join(SOFIFA_CACHE, "**", "players*.csv"), recursive=True)
    if not cache_files:
        return None
    
    df = pd.concat([pd.read_csv(f) for f in cache_files])
    matches = df[df["name"].str.contains(name, case=False)]
    if matches.empty:
        return None
    
    row = matches.iloc[0]
    return _row_to_playercard(row, "sofifa")

def _row_to_playercard(row, source):
    """灏?SoFIFA DataFrame 琛岃浆涓?PlayerCard"""
    att = {
        "pace": int(row.get("pace", 50)), "shooting": int(row.get("shooting", 50)),
        "passing": int(row.get("passing", 50)), "dribbling": int(row.get("dribbling", 50)),
        "defending": int(row.get("defending", 50)), "physical": int(row.get("physical", 50)),
    }
    return {
        "name": row["name"],
        "source": source,
        "position": row.get("position", "CM"),
        "att": att,
        "attack_rating": round(att["shooting"] * 0.6 + att["dribbling"] * 0.3 + att["pace"] * 0.1),
        "defense_rating": round(att["defending"] * 0.8 + att["physical"] * 0.2),
        "overall": int(row.get("overall", 50)),
        "club": row.get("club", ""),
        "market_value": row.get("value", ""),
    }
```

楠岃瘉锛歚python -c "from backend.data.sofifa_client import search_player; print(search_player('Haaland'))"`

### Task 1.7 鈥?宸叉湁鏁版嵁璇诲彇 `backend/data/match_repo.py`

```python
"""姣旇禌鏁版嵁浠撳簱 鈥?浠?football_odds 璇诲彇"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from data.mysql_client import query

def get_matches_for_training(league_code, seasons):
    if isinstance(seasons, str): seasons = [seasons]
    placeholders = ','.join(['%s'] * len(seasons))
    sql = f"""
        SELECT home_team AS home, away_team AS away,
               fthg AS home_goals, ftag AS away_goals
        FROM matches
        WHERE league_code=%s AND season IN ({placeholders})
          AND fthg IS NOT NULL AND ftag IS NOT NULL
    """
    return query(sql, [league_code] + list(seasons))

def get_all_leagues():
    return query("SELECT DISTINCT league_code FROM matches ORDER BY league_code")

def get_upcoming_matches(league_code, limit=20):
    return query("""
        SELECT m.*, o.b365h, o.b365d, o.b365a, o.psh, o.psd, o.psa
        FROM matches m LEFT JOIN odds o ON m.id=o.match_id
        WHERE m.league_code=%s AND m.match_date IS NULL
        LIMIT %s
    """, [league_code, limit])
```

---

## Phase 2锛欶astAPI 鍚庣鍏ㄦ帴鍙ｏ紙~4h锛?
### Task 2.1 鈥?FastAPI 鍏ュ彛 `backend/main.py`

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api import matches, predict, sandbox, players, teams, odds, models

app = FastAPI(title="Football Sandbox API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"], allow_headers=["*"],
)

app.include_router(matches.router, prefix="/api")
app.include_router(predict.router, prefix="/api")
app.include_router(sandbox.router, prefix="/api")
app.include_router(players.router, prefix="/api")
app.include_router(teams.router, prefix="/api")
app.include_router(odds.router, prefix="/api")
app.include_router(models.router, prefix="/api")

@app.get("/api/health")
def health(): return {"status": "ok", "version": "0.1.0"}
```

鍚姩楠岃瘉锛歚uvicorn backend.main:app --reload`锛屾祻瑙堝櫒鎵撳紑 `localhost:8000/docs`

### Task 2.2 鈥?鐞冨憳鎼滅储 API `backend/api/players.py`

```python
from fastapi import APIRouter, Query
from pydantic import BaseModel
from data.sofifa_client import search_player as sofifa_search
from data.mysql_client import query, execute

router = APIRouter()

class CustomPlayerRequest(BaseModel):
    name: str
    position: str
    pace: int = 50; shooting: int = 50; passing: int = 50
    dribbling: int = 50; defending: int = 50; physical: int = 50

@router.get("/players/search")
def search_player(q: str = Query(..., min_length=1)):
    """涓夐€氶亾鐞冨憳鎼滅储"""
    # 1. MySQL 鑷畾涔夌悆鍛?    custom = query(
        "SELECT * FROM custom_players WHERE name LIKE %s LIMIT 5",
        [f"%{q}%"], db="football_pred"
    )
    if custom:
        return {"source": "custom", "players": custom}

    # 2. SoFIFA
    result = sofifa_search(q)
    if result:
        return {"source": "sofifa", "players": [result]}

    # 3. Web 鎼滅储锛堣繑鍥炴彁绀猴紝鍓嶇瑙﹀彂锛?    return {"source": "web_needed", "players": [], "hint": f"鏈壘鍒?'{q}'锛岃浣跨敤鑷畾涔夊垱寤烘垨纭鎷煎啓"}

@router.post("/players/custom")
def create_custom_player(req: CustomPlayerRequest):
    execute("""
        INSERT INTO custom_players (name, source, position, pace, shooting, passing,
            dribbling, defending, physical)
        VALUES (%s, 'custom', %s, %s, %s, %s, %s, %s, %s)
    """, [req.name, req.position, req.pace, req.shooting, req.passing,
          req.dribbling, req.defending, req.physical], db="football_pred")
    return {"status": "created", "name": req.name}
```

### Task 2.3 鈥?蹇€熼娴?API `backend/api/predict.py`

```python
from fastapi import APIRouter
from pydantic import BaseModel
from engine.predictor import predict_match as do_predict

router = APIRouter()

class PredictRequest(BaseModel):
    home_team: str; away_team: str; league: str = "E0"

@router.post("/predict")
def predict(req: PredictRequest):
    return do_predict(req.home_team, req.away_team, req.league)
```

### Task 2.4 鈥?娌欑洏妯℃嫙 API锛堟牳蹇冿級`backend/api/sandbox.py`

```python
from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional
from engine.simulator import MonteCarloSimulator

router = APIRouter()

class PlayerSlot(BaseModel):
    name: str
    position: str
    att: Optional[dict] = None           # 鎵嬪姩瑕嗙洊灞炴€?    source: str = "db"                    # db | sofifa | custom | web

class SquadConfig(BaseModel):
    formation: str = "4-3-3"              # 4-3-3 | 4-4-2 | 3-5-2 | 5-4-1 | ...
    players: List[PlayerSlot]             # 11 浜?
class SimulateRequest(BaseModel):
    team_a: SquadConfig
    team_b: SquadConfig
    simulations: int = 1000                # 妯℃嫙娆℃暟
    home_advantage: bool = True

@router.post("/sandbox/simulate")
def simulate(req: SimulateRequest):
    sim = MonteCarloSimulator()
    result = sim.run(
        squad_a=req.team_a.dict(),
        squad_b=req.team_b.dict(),
        n=req.simulations,
        home_advantage=req.home_advantage
    )
    return result

@router.get("/sandbox/formations")
def list_formations():
    """杩斿洖鎵€鏈夊彲鐢ㄩ樀鍨嬪強閰嶇疆"""
    from engine.formations import FORMATIONS
    return FORMATIONS
```

---

## Phase 3锛氭ā鎷熷紩鎿庯紙~4h锛?
### Task 3.1 鈥?闃靛瀷閰嶇疆 `backend/engine/formations.py`

```python
"""
闃靛瀷鍥犲瓙 鈥?涓嶅悓闃靛瀷鐨勬敾闃插姞鎴愬拰浣嶇疆鏉冮噸銆?鏀诲嚮绯绘暟 >1 琛ㄧず闃靛瀷鍋忚繘鏀伙紝<1 鍋忛槻瀹堛€?"""
FORMATIONS = {
    "4-3-3": {
        "name": "4-3-3",
        "label": "4-3-3 鏀诲嚮",
        "positions": ["GK", "LB", "CB", "CB", "RB", "CM", "CM", "CM", "LW", "ST", "RW"],
        "attack_bonus": 1.10,
        "defense_bonus": 0.95,
        "position_weights": {
            "GK": {"attack": 0.0, "defense": 1.0},
            "CB": {"attack": 0.1, "defense": 0.9},
            "LB": {"attack": 0.3, "defense": 0.7},
            "RB": {"attack": 0.3, "defense": 0.7},
            "CM": {"attack": 0.5, "defense": 0.5},
            "LW": {"attack": 0.9, "defense": 0.1},
            "RW": {"attack": 0.9, "defense": 0.1},
            "ST": {"attack": 1.0, "defense": 0.0},
        }
    },
    "4-4-2": {
        "name": "4-4-2",
        "label": "4-4-2 鍧囪　",
        "positions": ["GK", "LB", "CB", "CB", "RB", "LM", "CM", "CM", "RM", "ST", "ST"],
        "attack_bonus": 1.00,
        "defense_bonus": 1.00,
        "position_weights": {
            "GK": {"attack": 0.0, "defense": 1.0},
            "CB": {"attack": 0.1, "defense": 0.9},
            "LB": {"attack": 0.2, "defense": 0.8},
            "RB": {"attack": 0.2, "defense": 0.8},
            "CM": {"attack": 0.5, "defense": 0.5},
            "LM": {"attack": 0.7, "defense": 0.3},
            "RM": {"attack": 0.7, "defense": 0.3},
            "ST": {"attack": 1.0, "defense": 0.0},
        }
    },
    "3-5-2": {
        "name": "3-5-2",
        "label": "3-5-2 鎺у満",
        "positions": ["GK", "CB", "CB", "CB", "LM", "CM", "CM", "CM", "RM", "ST", "ST"],
        "attack_bonus": 1.05,
        "defense_bonus": 1.00,
        "position_weights": {
            "GK": {"attack": 0.0, "defense": 1.0},
            "CB": {"attack": 0.1, "defense": 0.9},
            "CM": {"attack": 0.5, "defense": 0.5},
            "LM": {"attack": 0.7, "defense": 0.3},
            "RM": {"attack": 0.7, "defense": 0.3},
            "ST": {"attack": 1.0, "defense": 0.0},
        }
    },
    "5-4-1": {
        "name": "5-4-1",
        "label": "5-4-1 闃插畧鍙嶅嚮",
        "positions": ["GK", "LWB", "CB", "CB", "CB", "RWB", "CM", "CM", "LM", "RM", "ST"],
        "attack_bonus": 0.85,
        "defense_bonus": 1.15,
        "position_weights": {
            "GK": {"attack": 0.0, "defense": 1.0},
            "CB": {"attack": 0.1, "defense": 0.9},
            "LWB": {"attack": 0.3, "defense": 0.7},
            "RWB": {"attack": 0.3, "defense": 0.7},
            "CM": {"attack": 0.4, "defense": 0.6},
            "LM": {"attack": 0.6, "defense": 0.4},
            "RM": {"attack": 0.6, "defense": 0.4},
            "ST": {"attack": 1.0, "defense": 0.0},
        }
    },
}
```

### Task 3.2 鈥?鐞冮槦寮哄害璁＄畻鍣?`backend/engine/strength.py`

```python
"""
灏?11 涓悆鍛?+ 闃靛瀷 鈫?鐞冮槦杩涙敾寮哄害 伪 + 闃插畧寮哄害 尾
"""
from .formations import FORMATIONS

def calc_team_strength(squad: dict) -> tuple:
    """
    squad = {formation: "4-3-3", players: [{name, position, att:{...}}, ...]}
    杩斿洖 (attack_strength, defense_strength)
    """
    formation = FORMATIONS.get(squad["formation"], FORMATIONS["4-4-2"])
    weights = formation["position_weights"]

    total_attack = 0.0
    total_defense = 0.0

    for i, player in enumerate(squad["players"]):
        expected_pos = formation["positions"][i] if i < len(formation["positions"]) else "CM"
        w = weights.get(player.get("position", expected_pos), {"attack": 0.5, "defense": 0.5})

        # 鐞冨憳灞炴€э紙鏉ユ簮鍙兘鏄?sofifa/custom/db锛?        att = player.get("att", {})
        attack_rating = player.get("attack_rating", att.get("shooting", 50))
        defense_rating = player.get("defense_rating", att.get("defending", 50))

        total_attack += attack_rating * w["attack"] / 100
        total_defense += defense_rating * w["defense"] / 100

    # 闃靛瀷鍏ㄥ眬鍔犳垚
    total_attack *= formation["attack_bonus"]
    total_defense *= formation["defense_bonus"]

    return round(total_attack, 4), round(total_defense, 4)
```

楠岃瘉锛?```python
test_squad = {
    "formation": "4-3-3",
    "players": [{"name": f"Player{i}", "position": "CM", "attack_rating": 75, "defense_rating": 60} for i in range(11)]
}
assert calc_team_strength(test_squad)[0] > 0
```

### Task 3.3 鈥?钂欑壒鍗℃礇妯℃嫙鍣?`backend/engine/simulator.py`

```python
"""
钂欑壒鍗℃礇妯℃嫙寮曟搸
杈撳叆: SquadA + SquadB + 妯℃嫙娆℃暟
杈撳嚭: W/D/L% + 骞冲潎杩涚悆 + 姣斿垎鍒嗗竷
"""
import numpy as np
from collections import Counter
from .strength import calc_team_strength

class MonteCarloSimulator:
    def __init__(self, home_gamma=0.2):
        """
        home_gamma: 涓诲満浼樺娍鍔犳垚 (log 绌洪棿锛屽吀鍨嬪€?0.1-0.3)
        Dixon-Coles 鍏紡: 位 = exp(伪_h + 尾_a + 纬)
        """
        self.gamma = home_gamma

    def run(self, squad_a: dict, squad_b: dict, n: int = 1000, home_advantage: bool = True):
        # 璁＄畻涓ら槦寮哄害
        att_a, def_a = calc_team_strength(squad_a)
        att_b, def_b = calc_team_strength(squad_b)

        # Dixon-Coles 棰勬湡杩涚悆锛堝鏁扮┖闂达級
        gamma = self.gamma if home_advantage else 0
        lam = np.exp(att_a - def_b + gamma)   # 涓婚槦棰勬湡杩涚悆
        mu  = np.exp(att_b - def_a)            # 瀹㈤槦棰勬湡杩涚悆

        # 璺?N 娆?        home_goals = np.random.poisson(lam, n)
        away_goals = np.random.poisson(mu, n)

        # 缁熻
        results = []
        for h, a in zip(home_goals, away_goals):
            if h > a:   results.append("H")
            elif h < a: results.append("A")
            else:       results.append("D")

        wdl = {
            "home_win": round(results.count("H") / n, 4),
            "draw": round(results.count("D") / n, 4),
            "away_win": round(results.count("A") / n, 4),
        }

        # 姣斿垎鍒嗗竷
        scores = [f"{h}-{a}" for h, a in zip(home_goals, away_goals)]
        score_counts = Counter(scores)
        score_dist = {
            s: round(c / n, 4)
            for s, c in score_counts.most_common(15)
        }

        return {
            "wdl": wdl,
            "avg_goals": {
                "home": round(float(np.mean(home_goals)), 2),
                "away": round(float(np.mean(away_goals)), 2),
                "total": round(float(np.mean(home_goals + away_goals)), 2),
            },
            "expected_goals": {"home": round(float(lam), 2), "away": round(float(mu), 2)},
            "most_likely_score": max(score_counts, key=score_counts.get),
            "score_distribution": score_dist,
            "sim_count": n,
        }
```

楠岃瘉锛?```python
from backend.engine.simulator import MonteCarloSimulator
sim = MonteCarloSimulator()
sq = {"formation": "4-3-3", "players": [{"name": f"P{i}","position":"CM","attack_rating":80,"defense_rating":60} for i in range(11)]}
r = sim.run(sq, sq, n=500)
assert abs(sum(r["wdl"].values()) - 1.0) < 0.01
print(r["wdl"])
```

### Task 3.4 鈥?DixonColes 棰勬祴鍣紙蹇€熸ā寮忥級`backend/engine/predictor.py`

浠?`D:\xiaoli\scripts\dixon_coles_model.py` 澶嶇敤 `DixonColes` 绫伙細

```python
import json, os, sys
sys.path.insert(0, r"D:\xiaoli\scripts")
from dixon_coles_model import DixonColes
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import MODEL_DIR

def load_model(league_code):
    models = [f for f in os.listdir(MODEL_DIR) if f.startswith(f"dc_{league_code}_")]
    if not models:
        raise FileNotFoundError(f"No model for {league_code}")
    with open(os.path.join(MODEL_DIR, sorted(models)[-1])) as f:
        data = json.load(f)
    model = DixonColes()
    model.teams = data["teams"]
    model.params = data["params"]
    model.fitted = True
    return model

def predict_match(home_team, away_team, league_code="E0"):
    model = load_model(league_code)
    probs = model.get_match_probs(home_team, away_team)
    return {
        "home_team": home_team, "away_team": away_team, "league": league_code,
        "home_win": round(probs["home_win"], 4),
        "draw": round(probs["draw"], 4),
        "away_win": round(probs["away_win"], 4),
        "exp_home_goals": round(probs["expected_goals"]["home"], 2),
        "exp_away_goals": round(probs["expected_goals"]["away"], 2),
    }
```

---

## Phase 4锛歊eact 鍓嶇 5 椤甸潰锛垀6h锛?
### Task 4.1 鈥?椤圭洰鍒濆鍖?
```bash
cd /mnt/d/xiaoli/football-pred-system
npm create vite@latest frontend -- --template react
cd frontend
npm install
npm install tailwindcss @tailwindcss/vite recharts react-soccer-lineup @withqwerty/campos-react
```

### Task 4.2 鈥?Vite 閰嶇疆 `vite.config.js`

```javascript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { port: 5173 }
})
```

### Task 4.3 鈥?鍏ㄥ眬鏍峰紡 `src/index.css`

```css
@import "tailwindcss";

:root {
  --bg-page: #0d1117; --bg-card: #161b22; --bg-hover: #1c2129;
  --bg-input: #21262d; --border: #30363d;
  --fg-primary: #e6edf3; --fg-body: #c9d1d9; --fg-muted: #8b949e;
  --accent: #58a6ff; --green: #3fb950; --red: #f85149; --yellow: #d2991d;
}
body { background: var(--bg-page); color: var(--fg-body); margin: 0; font-family: system-ui, sans-serif; }
```

### Task 4.4 鈥?API 灏佽 `src/api.js`

```javascript
const BASE = 'http://localhost:8000/api';

export async function get(url, params = {}) {
  const qs = new URLSearchParams(params).toString();
  const r = await fetch(BASE + url + (qs ? '?' + qs : ''));
  return r.json();
}

export async function post(url, body) {
  const r = await fetch(BASE + url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  return r.json();
}
```

### Task 4.5 鈥?鍏ㄥ眬甯冨眬 `src/App.jsx`

```jsx
import { useState } from 'react';
import Dashboard from './pages/Dashboard';
import Predictions from './pages/Predictions';
import Sandbox from './pages/Sandbox';
import TeamAnalysis from './pages/TeamAnalysis';
import EVScanner from './pages/EVScanner';

const TABS = [
  { key: 'dashboard', label: '馃搳 浠〃鐩? },
  { key: 'predictions', label: '馃搮 棰勬祴' },
  { key: 'sandbox', label: '馃幃 娌欑洏' },
  { key: 'teams', label: '馃搱 鐞冮槦' },
  { key: 'ev', label: '馃挵 EV' },
];

export default function App() {
  const [tab, setTab] = useState('dashboard');

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <header style={styles.header}>
        <h1 style={styles.title}>鈿?灏忔潕瓒崇悆棰勬祴绯荤粺</h1>
        <nav style={{ display: 'flex', gap: 4 }}>
          {TABS.map(t => (
            <button key={t.key} onClick={() => setTab(t.key)}
              style={{ ...styles.tab, ...(tab === t.key ? styles.tabActive : {}) }}>
              {t.label}
            </button>
          ))}
        </nav>
      </header>
      <main style={{ flex: 1, padding: 24 }}>
        {tab === 'dashboard' && <Dashboard />}
        {tab === 'predictions' && <Predictions />}
        {tab === 'sandbox' && <Sandbox />}
        {tab === 'teams' && <TeamAnalysis />}
        {tab === 'ev' && <EVScanner />}
      </main>
      <footer style={styles.footer}>
        <span>妯″瀷 v1.0</span><span style={{ color: 'var(--green)' }}>API 馃煝</span>
      </footer>
    </div>
  );
}

const styles = {
  header: { background: 'var(--bg-card)', borderBottom: '1px solid var(--border)', padding: '12px 24px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' },
  title: { color: 'var(--fg-primary)', fontSize: 18, fontWeight: 'bold', margin: 0 },
  tab: { background: 'transparent', color: 'var(--fg-muted)', border: 'none', padding: '8px 16px', cursor: 'pointer', fontSize: 14, borderRadius: 6 },
  tabActive: { background: 'var(--bg-input)', color: 'var(--fg-primary)' },
  footer: { background: 'var(--bg-card)', borderTop: '1px solid var(--border)', padding: '8px 24px', fontSize: 12, color: 'var(--fg-muted)', display: 'flex', gap: 16 },
};
```

### Task 4.6 鈥?娌欑洏鎺ㄦ紨椤碉紙鏍稿績锛塦src/pages/Sandbox.jsx`

```jsx
import { useState } from 'react';
import { get, post } from '../api';
import PitchFormation from '../components/PitchFormation';
import PlayerSlot from '../components/PlayerSlot';
import ScoreHeatmap from '../components/ScoreHeatmap';

const DEFAULT_FORMATION = '4-3-3';
const emptySlot = (pos) => ({ name: '', position: pos, source: 'custom', att: {} });

export default function Sandbox() {
  const [formationA, setFormationA] = useState(DEFAULT_FORMATION);
  const [formationB, setFormationB] = useState('4-4-2');
  const [playersA, setPlayersA] = useState(defaultPlayers(DEFAULT_FORMATION));
  const [playersB, setPlayersB] = useState(defaultPlayers('4-4-2'));
  const [simCount, setSimCount] = useState(1000);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  async function runSimulation() {
    setLoading(true);
    const r = await post('/sandbox/simulate', {
      team_a: { formation: formationA, players: playersA.map(p => ({ name: p.name || '鏈煡', position: p.position, att: p.att, source: p.source })) },
      team_b: { formation: formationB, players: playersB.map(p => ({ name: p.name || '鏈煡', position: p.position, att: p.att, source: p.source })) },
      simulations: simCount,
      home_advantage: true,
    });
    setResult(r);
    setLoading(false);
  }

  return (
    <div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24, marginBottom: 24 }}>
        <SquadPanel label="涓婚槦" formation={formationA} setFormation={setFormationA} players={playersA} setPlayers={setPlayersA} />
        <SquadPanel label="瀹㈤槦" formation={formationB} setFormation={setFormationB} players={playersB} setPlayers={setPlayersB} />
      </div>

      <div style={{ textAlign: 'center', marginBottom: 24 }}>
        <label style={{ color: 'var(--fg-muted)', marginRight: 8 }}>妯℃嫙娆℃暟:</label>
        <select value={simCount} onChange={e => setSimCount(+e.target.value)}
          style={{ background: 'var(--bg-input)', color: 'var(--fg-body)', border: '1px solid var(--border)', padding: '6px 12px', borderRadius: 6 }}>
          {[100, 500, 1000, 5000, 10000].map(n => <option key={n} value={n}>{n.toLocaleString()}</option>)}
        </select>
        <button onClick={runSimulation} disabled={loading}
          style={{ marginLeft: 16, padding: '8px 24px', background: loading ? 'var(--bg-input)' : 'var(--green)', border: 'none', borderRadius: 6, color: '#fff', cursor: 'pointer', fontSize: 16 }}>
          {loading ? '妯℃嫙涓?..' : '鈻?寮€濮嬫ā鎷?}
        </button>
      </div>

      {result && <SimulationResult result={result} />}
    </div>
  );
}

// 瀛愮粍浠剁渷鐣ワ紙瀹屾暣浠ｇ爜鍦?plan 闄勫綍锛?```

### Task 4.7 鈥?鐞冨満闃靛瀷缁勪欢 `src/components/PitchFormation.jsx`

```jsx
import { SoccerLineup } from 'react-soccer-lineup';

export default function PitchFormation({ formation, players, away = false }) {
  // 杞崲鏁版嵁鏍煎紡涓?react-soccer-lineup 瑕佹眰鐨勬牸寮?  const lineup = players.map((p, i) => ({
    name: p.name || '?',
    number: i + 1,
    position: p.position,
  }));

  return (
    <div style={{ background: 'var(--bg-card)', borderRadius: 8, padding: 16 }}>
      <div style={{ color: 'var(--fg-muted)', fontSize: 13, marginBottom: 8 }}>
        闃靛瀷: {formation}
      </div>
      <SoccerLineup
        lineup={lineup}
        formation={formation}
        away={away}
        size="small"
        color={away ? '#f85149' : '#3fb950'}
      />
    </div>
  );
}
```

### Task 4.8 鈥?鍚庡洓涓〉闈紙浠〃鐩?棰勬祴/鐞冮槦/EV锛?
瑙?v1 鐗堣鍒?`DEVELOPMENT_PLAN.md` 涓殑 Task 4.2~4.5锛屼繚鐣欏師璁捐锛屽彧琛ュ厖锛?
- **浠〃鐩?*澧炲姞涓€涓?蹇嵎娌欑洏鍏ュ彛"鍗＄墖
- **棰勬祴椤?*鐨勮鎯呴潰鏉垮鍔?鍦ㄦ矙鐩樹腑妯℃嫙杩欏満姣旇禌"鎸夐挳
- **鐞冮槦椤?*鐨勭悆鍛樺崱鐗囧鍔犲睘鎬ф潯锛坧ace/shooting/passing/dribbling/defending/physical 鍏釜鑹叉潯锛?- **EV 椤?*澧炲姞鎸夋渶鏂版矙鐩樻ā鎷熺粨鏋滆绠?EV 鐨勯€夐」

---

## Phase 5锛氭ā鍨嬪崌绾?+ 鍥炴祴锛垀4h锛?
### Task 5.1 鈥?妯″瀷璁粌鍣?`backend/engine/trainer.py`

```python
import json, os, sys
sys.path.insert(0, r"D:\xiaoli\scripts")
from dixon_coles_model import DixonColes
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from data.match_repo import get_matches_for_training
from config import MODEL_DIR

def train_league(league_code, seasons=None):
    if seasons is None:
        from data.match_repo import query
        seasons = [r['season'] for r in query(
            "SELECT DISTINCT season FROM matches WHERE league_code=%s ORDER BY season", [league_code])]
        seasons = seasons[-2:]  # 鏈€杩?涓禌瀛?    matches = get_matches_for_training(league_code, seasons)
    model = DixonColes()
    model.fit(matches)
    fname = os.path.join(MODEL_DIR, f"dc_{league_code}_{seasons[-1]}.json")
    with open(fname, 'w', encoding='utf-8') as f:
        json.dump({
            "league": league_code, "seasons": seasons,
            "teams": model.teams,
            "params": {k: v if isinstance(v, dict) else float(v) for k, v in model.params.items()}
        }, f, indent=2)
    return model, fname
```

### Task 5.2 鈥?鍥炴祴妗嗘灦 `backend/engine/backtest.py`

```python
from .trainer import train_league
from data.match_repo import get_matches_for_training, query

def backtest(league_code, test_season):
    # 鑾峰彇璇ヨ禌瀛ｄ箣鍓嶇殑鎵€鏈夎禌瀛?    all_seasons = [r['season'] for r in query(
        "SELECT DISTINCT season FROM matches WHERE league_code=%s ORDER BY season", [league_code])]
    train_seasons = [s for s in all_seasons if s < test_season][-3:]

    model, _ = train_league(league_code, train_seasons)
    test_matches = get_matches_for_training(league_code, [test_season])
    if not test_matches:
        return {"error": "No test data"}

    correct = 0
    for m in test_matches:
        probs = model.get_match_probs(m['home'], m['away'])
        predicted = max(probs, key=lambda k: probs[k] if k in ['home_win','draw','away_win'] else 0)
        actual = 'H' if m['home_goals'] > m['away_goals'] else 'A' if m['home_goals'] < m['away_goals'] else 'D'
        mapping = {'home_win': 'H', 'draw': 'D', 'away_win': 'A'}
        if mapping.get(predicted) == actual:
            correct += 1

    accuracy = correct / len(test_matches)
    return {
        "league": league_code,
        "test_season": test_season,
        "train_seasons": train_seasons,
        "test_matches": len(test_matches),
        "correct": correct,
        "accuracy": round(accuracy, 4),
    }
```

### Task 5.3 鈥?xG 澧炲己锛堜簲澶ц仈璧涳級

鍒╃敤 `soccerdata.Understat` 鏇夸唬鐜版湁鎵嬪姩鐖櫕锛岃缁?`xGEnhancedDC`銆?
### Task 5.4 鈥?DC 鎵╁睍锛圫armanov 鏃忥級

鍙傝€?`arxiv 2307.02139`锛屽皢 `tau_correction` 浠?4 涓瘮鍒嗘墿灞曞埌鏇村姣斿垎鐐癸紝鐢ㄨ礋浜岄」鍒嗗竷鏇夸唬娉婃澗锛堜綆杩涚悆鑱旇禌鏇村噯锛夈€?
---

## 楠岃瘉娓呭崟

姣忎釜 Phase 缁撴潫鏃剁殑楠岃瘉锛?
| Phase | 楠岃瘉鍛戒护 | 棰勬湡缁撴灉 |
|-------|---------|---------|
| 1 | `python -c "from backend.data.sofifa_client import search_player; print(search_player('Haaland'))"` | 杈撳嚭鍝堝叞寰峰睘鎬?JSON |
| 2 | 娴忚鍣?`localhost:8000/docs` 鈫?娴嬭瘯 `/api/sandbox/simulate` | 杩斿洖 200 + 妯℃嫙缁撴灉 |
| 3 | `python -c "from backend.engine.simulator import MonteCarloSimulator; ..."` | 妯℃嫙 1000 娆?< 1 绉?|
| 4 | `npm run dev` 鈫?娴忚鍣?`localhost:5173` 鈫?娌欑洏椤垫帓闃靛瀷 鈫?鐐规ā鎷?| 鐪嬪埌 W/D/L% + 姣斿垎鍒嗗竷 |
| 5 | `python -c "from backend.engine.backtest import backtest; print(backtest('E0','2425'))"` | 鍑嗙‘鐜?> 45% |

---

*璁″垝鐢熸垚锛?026-05-23 路 鏇存柊锛氬姞鍏?soccerdata / react-soccer-lineup / campos-react / SoFIFA 鐞冨憳璇勫垎 / Sarmanov 鎵╁睍*



> 当前实现说明：阵型已改用自研 PitchFormation.jsx（SVG）绘制，暂未使用 eact-soccer-lineup / campos-react；如需切换回计划中的库，再补充安装与接入。

