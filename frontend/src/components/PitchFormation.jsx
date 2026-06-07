/**
 * SVG 足球场阵型展示组件
 * 球场比例 105m × 68m → SVG viewBox "0 0 1050 680"
 */
const PITCH_COLOR = '#1a472a';
const LINE_COLOR = '#ffffff44';
const HOME_COLOR = '#3fb950';
const AWAY_COLOR = '#f85149';

export default function PitchFormation({ formation, players, away = false }) {
  const color = away ? AWAY_COLOR : HOME_COLOR;
  const label = away ? '客队' : '主队';

  // 根据阵型计算位置
  const positions = getPositions(formation);
  const playerPositions = players.map((p, i) => ({
    ...p,
    x: positions[i]?.x || 525,
    y: positions[i]?.y || 340,
  }));

  return (
    <div style={{ position: 'relative', width: '100%', aspectRatio: '1050/680' }}>
      <svg viewBox="0 0 1050 680" style={{ width: '100%', height: '100%' }}>
        {/* 草坪 */}
        <rect x="0" y="0" width="1050" height="680" fill={PITCH_COLOR} />

        {/* 边线 */}
        <rect x="20" y="20" width="1010" height="640" fill="none" stroke={LINE_COLOR} strokeWidth="2" />

        {/* 中线 */}
        <line x1="525" y1="20" x2="525" y2="660" stroke={LINE_COLOR} strokeWidth="2" />
        <circle cx="525" cy="340" r="60" fill="none" stroke={LINE_COLOR} strokeWidth="2" />
        <circle cx="525" cy="340" r="3" fill={LINE_COLOR} />

        {/* 禁区 */}
        {away ? (
          <>
            <rect x="20" y="140" width="165" height="400" fill="none" stroke={LINE_COLOR} strokeWidth="2" />
            <rect x="20" y="240" width="55" height="200" fill="none" stroke={LINE_COLOR} strokeWidth="2" />
          </>
        ) : (
          <>
            <rect x="865" y="140" width="165" height="400" fill="none" stroke={LINE_COLOR} strokeWidth="2" />
            <rect x="975" y="240" width="55" height="200" fill="none" stroke={LINE_COLOR} strokeWidth="2" />
          </>
        )}

        {/* 球员圆点 */}
        {playerPositions.map((p, i) => (
          <g key={i}>
            <circle cx={p.x} cy={p.y} r="18" fill={color} opacity="0.9" />
            <text x={p.x} y={p.y + 1} textAnchor="middle" dominantBaseline="central"
              fill="#fff" fontSize="11" fontWeight="bold">
              {p.name ? p.name[0] : i + 1}
            </text>
            <text x={p.x} y={p.y + 28} textAnchor="middle" fill={LINE_COLOR} fontSize="9">
              {p.name?.length > 6 ? p.name.slice(0, 6) + '..' : (p.name || '')}
            </text>
          </g>
        ))}
      </svg>

      <div style={{
        position: 'absolute', top: 8, left: '50%', transform: 'translateX(-50%)',
        color: 'var(--fg-muted)', fontSize: 12, background: 'var(--bg-card)',
        padding: '2px 12px', borderRadius: 4
      }}>
        {label} · {formation}
      </div>
    </div>
  );
}

/** 根据阵型名返回 11 个 SVG 坐标 */
function getPositions(formation) {
  const pitch = {
    GK:  { '4-3-3': [950,340], '4-4-2': [950,340], '3-5-2': [950,340], '5-4-1': [950,340], '4-2-3-1': [950,340], '5-3-2': [950,340], '4-1-4-1': [950,340] },
    LB:  { '4-3-3': [820,100], '4-4-2': [820,100], '3-5-2': [850,340], '5-4-1': [820,100], '4-2-3-1': [820,100], '4-1-4-1': [820,100] },
    CB:  { '4-3-3': [840,280], '4-4-2': [840,280], '3-5-2': [840,180], '5-4-1': [860,200], '4-2-3-1': [840,280], '5-3-2': [860,200], '4-1-4-1': [840,280] },
    RB:  { '4-3-3': [820,580], '4-4-2': [820,580], '3-5-2': [850,340], '5-4-1': [820,580], '4-2-3-1': [820,580], '4-1-4-1': [820,580] },
    LWB: { '5-4-1': [770,100], '5-3-2': [770,100] },
    RWB: { '5-4-1': [770,580], '5-3-2': [770,580] },
    CDM: { '4-2-3-1': [720,240], '4-1-4-1': [720,340] },
    CM:  { '4-3-3': [650,200], '4-4-2': [670,220], '3-5-2': [650,200], '5-4-1': [670,220], '4-2-3-1': [720,440], '5-3-2': [650,200] },
    CAM: { '4-2-3-1': [580,340] },
    LM:  { '4-4-2': [720,90],  '3-5-2': [720,90],  '5-4-1': [720,90], '4-1-4-1': [600,90] },
    RM:  { '4-4-2': [720,590], '3-5-2': [720,590], '5-4-1': [720,590], '4-1-4-1': [600,590] },
    LW:  { '4-3-3': [500,120], '4-2-3-1': [480,130], '4-1-4-1': [500,120] },
    RW:  { '4-3-3': [500,560], '4-2-3-1': [480,550], '4-1-4-1': [500,560] },
    ST:  { '4-3-3': [400,340], '4-4-2': [420,240], '3-5-2': [420,240], '5-4-1': [400,340], '4-2-3-1': [380,340], '5-3-2': [420,240], '4-1-4-1': [380,340] },
  };

  const positions = {
    '4-3-3': ['GK','LB','CB','CB','RB','CM','CM','CM','LW','ST','RW'],
    '4-4-2': ['GK','LB','CB','CB','RB','LM','CM','CM','RM','ST','ST'],
    '3-5-2': ['GK','CB','CB','CB','LM','CM','CM','CM','RM','ST','ST'],
    '5-4-1': ['GK','LWB','CB','CB','CB','RWB','CM','CM','LM','RM','ST'],
    '4-2-3-1': ['GK','LB','CB','CB','RB','CDM','CDM','CAM','LW','RW','ST'],
    '5-3-2': ['GK','LWB','CB','CB','CB','RWB','CM','CM','CM','ST','ST'],
    '4-1-4-1': ['GK','LB','CB','CB','RB','CDM','LM','CM','CM','RM','ST'],
  };

  const posList = positions[formation] || positions['4-4-2'];
  const result = [];

  for (let i = 0; i < 11; i++) {
    const pos = posList[i];
    const coords = pitch[pos]?.[formation] || pitch[pos]?.['4-4-2'] || [525, 340];
    // 处理重复位置（如双 CB、双 CM、双 ST）
    let [x, y] = Array.isArray(coords) ? coords : [525, 340];

    // 同名位置错开
    const sameCount = posList.slice(0, i).filter(p => p === pos).length;
    if (sameCount > 0) {
      const offsets = { CB: [[-30,0],[30,0]], CM: [[0,-80],[0,80],[0,0]], ST: [[0,-60],[0,60]], CDM: [[0,-60],[0,60]] };
      const off = offsets[pos]?.[sameCount - 1] || [0, sameCount * 40];
      x += off[0]; y += off[1];
    }

    result.push({ x, y });
  }

  return result;
}
