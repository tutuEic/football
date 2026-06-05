import { useState, useEffect } from 'react';
import { get, post } from '../api';

const SUB_TABS = [
  { key: 'groups',    label: '小组赛' },
  { key: 'rankings',  label: '排名' },
  { key: 'matches',   label: '赛程' },
  { key: 'custom',    label: '自定义预测' },
  { key: 'sandbox',   label: '沙盘模拟' },
  { key: 'simulate',  label: '蒙特卡洛' },
];

export default function WorldCup() {
  const [subTab, setSubTab] = useState('groups');
  return (
    <div style={{ maxWidth: 1200, margin: '0 auto' }}>
      <div style={{ display: 'flex', gap: 4, marginBottom: 20, flexWrap: 'wrap' }}>
        {SUB_TABS.map(t => (
          <button key={t.key} onClick={() => setSubTab(t.key)}
            style={{
              background: subTab === t.key ? 'var(--accent)' : 'var(--bg-input)',
              color: subTab === t.key ? '#fff' : 'var(--fg-muted)',
              border: 'none', padding: '8px 16px', cursor: 'pointer',
              fontSize: 13, borderRadius: 6, transition: 'all 0.15s'
            }}>
            {t.label}
          </button>
        ))}
      </div>
      {subTab === 'groups'    && <GroupStage />}
      {subTab === 'rankings'  && <Rankings />}
      {subTab === 'matches'   && <Matches />}
      {subTab === 'custom'    && <CustomPredict />}
      {subTab === 'sandbox'   && <WCSandbox />}
      {subTab === 'knockout'  && <KnockoutBracket />}
      {subTab === 'goldenball' && <GoldenBall />}
      {subTab === 'simulate'  && <Simulate />}
    </div>
  );
}


// ============================================================
// Group Stage
// ============================================================

function GroupStage() {
  const [groups, setGroups] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(null);
  const [groupDetail, setGroupDetail] = useState(null);

  useEffect(() => {
    get('/worldcup/groups').then(d => {
      setGroups(d.groups || []);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  async function loadGroupDetail(gn) {
    if (expanded === gn) { setExpanded(null); return; }
    setExpanded(gn);
    try {
      const d = await get(`/worldcup/groups/${gn}`);
      setGroupDetail(d);
    } catch {}
  }

  if (loading) return <div style={{ color: 'var(--fg-muted)', textAlign: 'center', padding: 40 }}>Loading...</div>;

  return (
    <div>
      <h2 style={{ color: 'var(--fg-primary)', fontSize: 16, marginBottom: 16 }}>2026 WC - 12 Groups 48 Teams</h2>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 12 }}>
        {groups.map(g => (
          <div key={g.group} style={cardStyle}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <span style={{ color: 'var(--accent)', fontWeight: 'bold', fontSize: 14 }}>Group {g.group}</span>
              <button onClick={() => loadGroupDetail(g.group)} style={smallBtn}>
                {expanded === g.group ? 'Close' : 'Details'}
              </button>
            </div>
            <table style={{ width: '100%', fontSize: 12 }}>
              <thead>
                <tr style={{ color: 'var(--fg-muted)' }}>
                  <th style={thStyle}>Team</th>
                  <th style={thStyle}>Rank</th>
                  <th style={thStyle}>Elo</th>
                  <th style={thStyle}>XI</th>
                  <th style={thStyle}>Bonus</th>
                </tr>
              </thead>
              <tbody>
                {g.teams.map(t => (
                  <tr key={t.team} style={{ borderTop: '1px solid var(--border)' }}>
                    <td style={tdStyle}>
                      {t.is_host && <span title="Host" style={{ marginRight: 4 }}>H</span>}
                      {t.team}
                    </td>
                    <td style={tdStyle}>{t.fifa_ranking}</td>
                    <td style={tdStyle}>{t.elo_rating}</td>
                    <td style={tdStyle}>{t.starting_xi?.toFixed(1)}</td>
                    <td style={{ ...tdStyle, color: t.elo_bonus >= 0 ? 'var(--green)' : 'var(--red)' }}>
                      {t.elo_bonus >= 0 ? '+' : ''}{t.elo_bonus?.toFixed(1)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {expanded === g.group && groupDetail && (
              <div style={{ marginTop: 12, paddingTop: 8, borderTop: '1px solid var(--border)' }}>
                <div style={{ color: 'var(--fg-muted)', fontSize: 11, marginBottom: 6 }}>Head-to-Head Predictions</div>
                {groupDetail.predictions?.map((p, i) => (
                  <div key={i} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, padding: '3px 0', color: 'var(--fg-body)' }}>
                    <span style={{ flex: 1 }}>{p.home}</span>
                    <span style={{ color: 'var(--fg-muted)', margin: '0 8px', minWidth: 30, textAlign: 'center' }}>
                      {p.expected_goals?.home?.toFixed(2)} - {p.expected_goals?.away?.toFixed(2)}
                    </span>
                    <span style={{ flex: 1, textAlign: 'right' }}>{p.away}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}


// ============================================================
// Rankings
// ============================================================

function Rankings() {
  const [rankings, setRankings] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    get('/worldcup/rankings').then(d => {
      setRankings(d.rankings || []);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  if (loading) return <div style={{ color: 'var(--fg-muted)', textAlign: 'center', padding: 40 }}>Loading...</div>;

  return (
    <div>
      <h2 style={{ color: 'var(--fg-primary)', fontSize: 16, marginBottom: 16 }}>48-Team Power Rankings</h2>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', fontSize: 12, borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ color: 'var(--fg-muted)', borderBottom: '2px solid var(--border)' }}>
              <th style={thStyle}>#</th>
              <th style={{ ...thStyle, textAlign: 'left' }}>Team</th>
              <th style={thStyle}>XI</th>
              <th style={thStyle}>ATK</th>
              <th style={thStyle}>DEF</th>
              <th style={thStyle}>Depth</th>
              <th style={thStyle}>League</th>
              <th style={thStyle}>Coh</th>
              <th style={thStyle}>SetP</th>
              <th style={thStyle}>Elo</th>
              <th style={{ ...thStyle, textAlign: 'left' }}>Key Players</th>
            </tr>
          </thead>
          <tbody>
            {rankings.map(r => (
              <tr key={r.team} style={{ borderTop: '1px solid var(--border)', background: r.rank <= 8 ? 'rgba(88,166,255,0.05)' : 'transparent' }}>
                <td style={tdStyle}>{r.rank}</td>
                <td style={{ ...tdStyle, textAlign: 'left', fontWeight: 'bold', color: 'var(--fg-primary)' }}>{r.team}</td>
                <td style={tdStyle}>{r.starting_xi?.toFixed(1)}</td>
                <td style={tdStyle}>{r.attack_quality?.toFixed(1)}</td>
                <td style={tdStyle}>{r.defense_quality?.toFixed(1)}</td>
                <td style={tdStyle}>{r.squad_depth?.toFixed(1)}</td>
                <td style={tdStyle}>{r.league_quality?.toFixed(1)}</td>
                <td style={tdStyle}>{r.cohesion?.toFixed(3)}</td>
                <td style={tdStyle}>{r.set_piece_strength?.toFixed(3)}</td>
                <td style={{ ...tdStyle, color: r.elo_bonus >= 0 ? 'var(--green)' : 'var(--red)', fontWeight: 'bold' }}>
                  {r.elo_bonus >= 0 ? '+' : ''}{r.elo_bonus?.toFixed(1)}
                </td>
                <td style={{ ...tdStyle, textAlign: 'left', color: 'var(--fg-muted)', fontSize: 11, maxWidth: 200, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {r.top_players?.join(', ')}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}


// ============================================================
// Matches
// ============================================================

function Matches() {
  const [matches, setMatches] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null);
  const [prediction, setPrediction] = useState(null);
  const [predLoading, setPredLoading] = useState(false);

  useEffect(() => {
    get('/worldcup/matches', { limit: 72 }).then(d => {
      setMatches(d.matches || []);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  async function loadPrediction(fixtureId) {
    if (selected === fixtureId) { setSelected(null); return; }
    setSelected(fixtureId);
    setPredLoading(true);
    try {
      const d = await get(`/worldcup/matches/${fixtureId}`);
      setPrediction(d);
    } catch {}
    setPredLoading(false);
  }

  if (loading) return <div style={{ color: 'var(--fg-muted)', textAlign: 'center', padding: 40 }}>Loading...</div>;

  const byDate = {};
  matches.forEach(m => {
    if (!byDate[m.date]) byDate[m.date] = [];
    byDate[m.date].push(m);
  });

  return (
    <div>
      <h2 style={{ color: 'var(--fg-primary)', fontSize: 16, marginBottom: 16 }}>Group Stage - 72 Matches</h2>
      {Object.entries(byDate).map(([date, ms]) => (
        <div key={date} style={{ marginBottom: 20 }}>
          <div style={{ color: 'var(--accent)', fontSize: 13, fontWeight: 'bold', marginBottom: 8 }}>{date}</div>
          <div style={{ display: 'grid', gap: 6 }}>
            {ms.map(m => (
              <div key={m.fixture_id}>
                <div style={{ ...cardStyle, display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 12px', cursor: 'pointer' }}
                  onClick={() => loadPrediction(m.fixture_id)}>
                  <span style={{ flex: 1, textAlign: 'right', color: 'var(--fg-primary)', fontWeight: 500 }}>{m.home_team}</span>
                  <span style={{ margin: '0 16px', color: 'var(--fg-muted)', fontSize: 13, minWidth: 60, textAlign: 'center' }}>
                    {m.home_score != null ? `${m.home_score} - ${m.away_score}` : 'vs'}
                  </span>
                  <span style={{ flex: 1, color: 'var(--fg-primary)', fontWeight: 500 }}>{m.away_team}</span>
                  <span style={{ fontSize: 11, color: 'var(--fg-muted)', marginLeft: 12 }}>{m.status}</span>
                </div>
                {selected === m.fixture_id && (
                  <div style={{ ...cardStyle, marginTop: 4, padding: 12 }}>
                    {predLoading ? <div style={{ color: 'var(--fg-muted)', fontSize: 12 }}>Loading...</div> : prediction && <PredictionCard pred={prediction} />}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}


// ============================================================
// Custom Predict — select any two WC teams + stage
// ============================================================

function CustomPredict() {
  const [teams, setTeams] = useState([]);
  const [home, setHome] = useState('');
  const [away, setAway] = useState('');
  const [stage, setStage] = useState('group');
  const [matchday, setMatchday] = useState(1);
  const [isHost, setIsHost] = useState(false);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    get('/worldcup/rankings').then(d => {
      setTeams((d.rankings || []).map(r => r.team));
    }).catch(() => {});
  }, []);

  async function handlePredict() {
    if (!home || !away || home === away) return;
    setLoading(true);
    setResult(null);
    try {
      const d = await post('/worldcup/predict', {
        home_team: home, away_team: away,
        stage, matchday, is_host: isHost,
      });
      setResult(d);
    } catch (err) {
      setResult({ status: 'error', message: err.message });
    }
    setLoading(false);
  }

  const stages = [
    { value: 'group', label: 'Group Stage' },
    { value: 'r32', label: 'Round of 32' },
    { value: 'r16', label: 'Round of 16' },
    { value: 'qf', label: 'Quarter-Final' },
    { value: 'sf', label: 'Semi-Final' },
    { value: 'final', label: 'Final' },
  ];

  return (
    <div>
      <h2 style={{ color: 'var(--fg-primary)', fontSize: 16, marginBottom: 16 }}>Custom WC Match Prediction</h2>

      {/* Controls */}
      <div style={{ ...cardStyle, marginBottom: 16, display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
        <select value={home} onChange={e => setHome(e.target.value)} style={selectStyle}>
          <option value="">Home Team</option>
          {teams.filter(t => t !== away).map(t => <option key={t} value={t}>{t}</option>)}
        </select>
        <span style={{ color: 'var(--fg-muted)', fontWeight: 'bold' }}>vs</span>
        <select value={away} onChange={e => setAway(e.target.value)} style={selectStyle}>
          <option value="">Away Team</option>
          {teams.filter(t => t !== home).map(t => <option key={t} value={t}>{t}</option>)}
        </select>
        <select value={stage} onChange={e => setStage(e.target.value)} style={selectStyle}>
          {stages.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
        </select>
        {stage === 'group' && (
          <select value={matchday} onChange={e => setMatchday(Number(e.target.value))} style={selectStyle}>
            <option value={1}>Matchday 1</option>
            <option value={2}>Matchday 2</option>
            <option value={3}>Matchday 3</option>
          </select>
        )}
        <label style={{ display: 'flex', alignItems: 'center', gap: 4, color: 'var(--fg-muted)', fontSize: 12, cursor: 'pointer' }}>
          <input type="checkbox" checked={isHost} onChange={e => setIsHost(e.target.checked)} />
          Host Advantage
        </label>
        <button onClick={handlePredict} disabled={loading || !home || !away}
          style={{ background: loading ? 'var(--bg-input)' : 'var(--green)', color: '#fff', border: 'none', padding: '8px 20px', borderRadius: 6, cursor: 'pointer', fontSize: 13 }}>
          {loading ? 'Predicting...' : 'Predict'}
        </button>
      </div>

      {/* Result */}
      {result?.status === 'ok' && (
        <div style={cardStyle}>
          <PredictionCard pred={result} full={true} />
        </div>
      )}
      {result?.status === 'error' && (
        <div style={{ color: 'var(--red)', padding: 12, background: 'rgba(248,81,73,0.1)', borderRadius: 6 }}>{result.message}</div>
      )}
    </div>
  );
}


// ============================================================
// WC Sandbox — detailed match simulation with factor breakdown
// ============================================================

function WCSandbox() {
  const [teams, setTeams] = useState([]);
  const [home, setHome] = useState('');
  const [away, setAway] = useState('');
  const [stage, setStage] = useState('group');
  const [isHost, setIsHost] = useState(false);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [simCount, setSimCount] = useState(1000);

  useEffect(() => {
    get('/worldcup/rankings').then(d => {
      setTeams((d.rankings || []).map(r => ({ name: r.team, xi: r.starting_xi, elo: r.elo_bonus, top: r.top_players })));
    }).catch(() => {});
  }, []);

  async function handleSim() {
    if (!home || !away || home === away) return;
    setLoading(true);
    setResult(null);
    try {
      const d = await post('/worldcup/predict', {
        home_team: home, away_team: away,
        stage, matchday: 1, is_host: isHost,
      });
      setResult(d);
    } catch (err) {
      setResult({ status: 'error', message: err.message });
    }
    setLoading(false);
  }

  function swapTeams() {
    setHome(away);
    setAway(home);
  }

  const stages = [
    { value: 'group', label: 'Group' },
    { value: 'r32', label: 'R32' },
    { value: 'r16', label: 'R16' },
    { value: 'qf', label: 'QF' },
    { value: 'sf', label: 'SF' },
    { value: 'final', label: 'Final' },
  ];

  const homeInfo = teams.find(t => t.name === home);
  const awayInfo = teams.find(t => t.name === away);

  return (
    <div>
      <h2 style={{ color: 'var(--fg-primary)', fontSize: 16, marginBottom: 16 }}>WC Sandbox Simulation</h2>

      {/* Team selectors */}
      <div style={{ ...cardStyle, marginBottom: 16 }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr auto 1fr', gap: 16, alignItems: 'start' }}>
          {/* Home */}
          <div>
            <div style={{ color: 'var(--green)', fontSize: 12, fontWeight: 'bold', marginBottom: 6 }}>HOME</div>
            <select value={home} onChange={e => setHome(e.target.value)} style={{ ...selectStyle, width: '100%' }}>
              <option value="">Select team...</option>
              {teams.filter(t => t.name !== away).map(t => <option key={t.name} value={t.name}>{t.name}</option>)}
            </select>
            {homeInfo && (
              <div style={{ marginTop: 8, fontSize: 11, color: 'var(--fg-muted)' }}>
                <div>XI: <b style={{ color: 'var(--fg-primary)' }}>{homeInfo.xi?.toFixed(1)}</b></div>
                <div>Elo: <b style={{ color: homeInfo.elo >= 0 ? 'var(--green)' : 'var(--red)' }}>{homeInfo.elo >= 0 ? '+' : ''}{homeInfo.elo?.toFixed(1)}</b></div>
                <div style={{ marginTop: 4 }}>{homeInfo.top?.join(', ')}</div>
              </div>
            )}
          </div>

          {/* Swap + Controls */}
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8, paddingTop: 24 }}>
            <button onClick={swapTeams} style={{ background: 'var(--bg-input)', color: 'var(--fg-muted)', border: 'none', padding: '6px 12px', borderRadius: 4, cursor: 'pointer', fontSize: 16 }} title="Swap">⇄</button>
            <select value={stage} onChange={e => setStage(e.target.value)} style={{ ...selectStyle, width: 80, textAlign: 'center', fontSize: 11 }}>
              {stages.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
            </select>
            <label style={{ display: 'flex', alignItems: 'center', gap: 3, color: 'var(--fg-muted)', fontSize: 10, cursor: 'pointer' }}>
              <input type="checkbox" checked={isHost} onChange={e => setIsHost(e.target.checked)} />
              Host
            </label>
          </div>

          {/* Away */}
          <div>
            <div style={{ color: 'var(--red)', fontSize: 12, fontWeight: 'bold', marginBottom: 6 }}>AWAY</div>
            <select value={away} onChange={e => setAway(e.target.value)} style={{ ...selectStyle, width: '100%' }}>
              <option value="">Select team...</option>
              {teams.filter(t => t.name !== home).map(t => <option key={t.name} value={t.name}>{t.name}</option>)}
            </select>
            {awayInfo && (
              <div style={{ marginTop: 8, fontSize: 11, color: 'var(--fg-muted)' }}>
                <div>XI: <b style={{ color: 'var(--fg-primary)' }}>{awayInfo.xi?.toFixed(1)}</b></div>
                <div>Elo: <b style={{ color: awayInfo.elo >= 0 ? 'var(--green)' : 'var(--red)' }}>{awayInfo.elo >= 0 ? '+' : ''}{awayInfo.elo?.toFixed(1)}</b></div>
                <div style={{ marginTop: 4 }}>{awayInfo.top?.join(', ')}</div>
              </div>
            )}
          </div>
        </div>

        <div style={{ display: 'flex', justifyContent: 'center', marginTop: 16, gap: 8 }}>
          <button onClick={handleSim} disabled={loading || !home || !away}
            style={{ background: loading ? 'var(--bg-input)' : 'var(--accent)', color: '#fff', border: 'none', padding: '10px 28px', borderRadius: 6, cursor: 'pointer', fontSize: 14, fontWeight: 'bold' }}>
            {loading ? 'Simulating...' : 'Run Simulation'}
          </button>
        </div>
      </div>

      {/* Result */}
      {result?.status === 'ok' && (
        <div style={{ display: 'grid', gap: 12 }}>
          <SandboxResultCard result={result} />
        </div>
      )}
      {result?.status === 'error' && (
        <div style={{ color: 'var(--red)', padding: 12, background: 'rgba(248,81,73,0.1)', borderRadius: 6 }}>{result.message}</div>
      )}
    </div>
  );
}


function SandboxResultCard({ result }) {
  const p = result;
  const wdl = p.wdl || {};
  const xg = p.expected_goals || {};
  const factors = p.factors || {};
  const player = p.player_analysis || {};
  const scores = p.score_distribution || {};

  const topScores = Object.entries(scores)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6);

  return (
    <div style={{ display: 'grid', gap: 12 }}>
      {/* Score + WDL */}
      <div style={cardStyle}>
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 20, marginBottom: 12 }}>
          <div style={{ textAlign: 'center' }}>
            <div style={{ color: 'var(--fg-primary)', fontWeight: 'bold', fontSize: 16 }}>{p.home_team}</div>
            <div style={{ color: 'var(--accent)', fontSize: 28, fontWeight: 'bold' }}>{xg.home?.toFixed(2)}</div>
            <div style={{ color: 'var(--fg-muted)', fontSize: 11 }}>xG</div>
          </div>
          <div style={{ color: 'var(--fg-muted)' }}>vs</div>
          <div style={{ textAlign: 'center' }}>
            <div style={{ color: 'var(--fg-primary)', fontWeight: 'bold', fontSize: 16 }}>{p.away_team}</div>
            <div style={{ color: 'var(--accent)', fontSize: 28, fontWeight: 'bold' }}>{xg.away?.toFixed(2)}</div>
            <div style={{ color: 'var(--fg-muted)', fontSize: 11 }}>xG</div>
          </div>
        </div>

        {/* WDL Bar */}
        <div style={{ display: 'flex', height: 10, borderRadius: 5, overflow: 'hidden', background: 'var(--bg-input)' }}>
          <div style={{ width: `${(wdl.home_win || 0) * 100}%`, background: 'var(--green)' }} />
          <div style={{ width: `${(wdl.draw || 0) * 100}%`, background: 'var(--yellow)' }} />
          <div style={{ width: `${(wdl.away_win || 0) * 100}%`, background: 'var(--red)' }} />
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 6, fontSize: 13 }}>
          <span style={{ color: 'var(--green)', fontWeight: 'bold' }}>Home {(wdl.home_win * 100)?.toFixed(1)}%</span>
          <span style={{ color: 'var(--yellow)', fontWeight: 'bold' }}>Draw {(wdl.draw * 100)?.toFixed(1)}%</span>
          <span style={{ color: 'var(--red)', fontWeight: 'bold' }}>Away {(wdl.away_win * 100)?.toFixed(1)}%</span>
        </div>
      </div>

      {/* Score Distribution + Details */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <div style={cardStyle}>
          <div style={{ color: 'var(--accent)', fontWeight: 'bold', fontSize: 13, marginBottom: 8 }}>Most Likely Scores</div>
          {topScores.map(([score, prob]) => (
            <div key={score} style={{ display: 'flex', justifyContent: 'space-between', padding: '3px 0', fontSize: 12 }}>
              <span style={{ color: 'var(--fg-primary)', fontWeight: score === p.most_likely_score ? 'bold' : 'normal' }}>{score}</span>
              <span style={{ color: 'var(--fg-muted)' }}>{(prob * 100).toFixed(1)}%</span>
            </div>
          ))}
        </div>
        <div style={cardStyle}>
          <div style={{ color: 'var(--accent)', fontWeight: 'bold', fontSize: 13, marginBottom: 8 }}>Match Details</div>
          <div style={{ fontSize: 12, display: 'grid', gap: 4 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--fg-muted)' }}>Most Likely</span>
              <span style={{ color: 'var(--fg-primary)', fontWeight: 'bold' }}>{p.most_likely_score} ({(p.most_likely_prob * 100)?.toFixed(1)}%)</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--fg-muted)' }}>Over 2.5</span>
              <span style={{ color: 'var(--green)' }}>{(p.over_under?.over_25 * 100)?.toFixed(1)}%</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--fg-muted)' }}>Under 2.5</span>
              <span style={{ color: 'var(--red)' }}>{(p.over_under?.under_25 * 100)?.toFixed(1)}%</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--fg-muted)' }}>Confidence</span>
              <span style={{ color: 'var(--fg-primary)' }}>{p.confidence}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--fg-muted)' }}>Elo Diff</span>
              <span style={{ color: factors.elo?.diff > 0 ? 'var(--green)' : 'var(--red)' }}>{factors.elo?.diff?.toFixed(1)}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Factor Breakdown */}
      {factors.elo && (
        <div style={cardStyle}>
          <div style={{ color: 'var(--accent)', fontWeight: 'bold', fontSize: 13, marginBottom: 8 }}>Factor Breakdown</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 8, fontSize: 12 }}>
            <FactorBox label="FIFA Elo" home={factors.elo.home_fifa} away={factors.elo.away_fifa} />
            <FactorBox label="Player Elo" home={factors.elo.player_elo?.home} away={factors.elo.player_elo?.away} color />
            <FactorBox label="Combined Elo" home={factors.elo.combined?.home} away={factors.elo.combined?.away} />
            <FactorBox label="Form" home={factors.form?.home} away={factors.form?.away} color signed />
            <FactorBox label="WC History" home={factors.tournament?.wc_history?.home} away={factors.tournament?.wc_history?.away} />
            <FactorBox label="Curse" home={factors.tournament?.curse?.home} away={factors.tournament?.curse?.away} color />
          </div>
        </div>
      )}

      {/* Squad Comparison */}
      {player.home && player.away && (
        <div style={cardStyle}>
          <div style={{ color: 'var(--accent)', fontWeight: 'bold', fontSize: 13, marginBottom: 8 }}>Squad Comparison</div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <SquadMini label={p.home_team} data={player.home} />
            <SquadMini label={p.away_team} data={player.away} />
          </div>
        </div>
      )}
    </div>
  );
}


function FactorBox({ label, home, away, color, signed }) {
  const fmt = (v) => {
    if (v == null) return '-';
    if (signed) return (v >= 0 ? '+' : '') + v.toFixed(1);
    return typeof v === 'number' ? v.toFixed(1) : v;
  };
  return (
    <div style={{ background: 'var(--bg-input)', borderRadius: 4, padding: '6px 8px' }}>
      <div style={{ color: 'var(--fg-muted)', fontSize: 10, marginBottom: 3 }}>{label}</div>
      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
        <span style={{ color: color ? (home >= 0 ? 'var(--green)' : 'var(--red)') : 'var(--fg-primary)', fontWeight: 'bold' }}>{fmt(home)}</span>
        <span style={{ color: 'var(--fg-muted)' }}>vs</span>
        <span style={{ color: color ? (away >= 0 ? 'var(--green)' : 'var(--red)') : 'var(--fg-primary)', fontWeight: 'bold' }}>{fmt(away)}</span>
      </div>
    </div>
  );
}


function SquadMini({ label, data }) {
  return (
    <div>
      <div style={{ color: 'var(--fg-primary)', fontWeight: 'bold', fontSize: 12, marginBottom: 6 }}>{label}</div>
      <div style={{ fontSize: 11, display: 'grid', gap: 2 }}>
        <Row label="Starting XI" val={data.starting_xi} />
        <Row label="Attack" val={data.attack_quality} />
        <Row label="Defense" val={data.defense_quality} />
        <Row label="Squad Depth" val={data.squad_depth} />
        <Row label="Avg Age" val={data.avg_age} />
        <Row label="League Quality" val={data.league_quality} />
        <Row label="Cohesion" val={data.cohesion} fix={3} />
        <Row label="Set Piece" val={data.set_piece_strength} fix={3} />
      </div>
      <div style={{ marginTop: 6, color: 'var(--fg-muted)', fontSize: 10 }}>
        {data.top_players?.join(', ')}
      </div>
    </div>
  );
}

function Row({ label, val, fix = 1 }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
      <span style={{ color: 'var(--fg-muted)' }}>{label}</span>
      <span style={{ color: 'var(--fg-primary)' }}>{val?.toFixed(fix)}</span>
    </div>
  );
}


// ============================================================
// Prediction Card (compact)
// ============================================================

function PredictionCard({ pred, full }) {
  if (!pred || pred.prediction_error) {
    return <div style={{ color: 'var(--red)', fontSize: 12 }}>Error: {pred?.prediction_error || 'Unknown'}</div>;
  }

  const p = pred.prediction || pred;
  const wdl = p.wdl || {};
  const xg = p.expected_goals || {};
  const models = p.models || {};
  const playerH = p.player_analysis?.home || {};
  const playerA = p.player_analysis?.away || {};
  const confidence = p.confidence || 0;

  const confColor = confidence > 0.6 ? 'var(--green)' : confidence > 0.3 ? 'var(--yellow)' : 'var(--red)';

  return (
    <div style={{ display: 'grid', gap: 12, fontSize: 12 }}>
      {/* Header: Teams + xG */}
      <div style={{ display: 'flex', justifyContent: 'center', gap: 24, alignItems: 'center' }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ color: 'var(--fg-primary)', fontWeight: 'bold', fontSize: 15 }}>{pred.home_team || p.home_team}</div>
          <div style={{ color: 'var(--accent)', fontSize: 22, fontWeight: 'bold' }}>{xg.home?.toFixed(2)}</div>
          <div style={{ color: 'var(--fg-muted)', fontSize: 11 }}>xG</div>
          {playerH.elo_bonus != null && (
            <div style={{ color: playerH.elo_bonus > 0 ? 'var(--green)' : 'var(--red)', fontSize: 11, marginTop: 2 }}>
              Elo: {playerH.elo_bonus > 0 ? '+' : ''}{playerH.elo_bonus?.toFixed(1)}
            </div>
          )}
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
          <div style={{ color: 'var(--fg-muted)', fontSize: 11 }}>{p.stage || 'Group'}</div>
          <div style={{ color: 'var(--fg-muted)', fontSize: 16, fontWeight: 'bold' }}>vs</div>
          <div style={{ color: confColor, fontSize: 10 }}>Confidence: {(confidence * 100).toFixed(0)}%</div>
        </div>
        <div style={{ textAlign: 'center' }}>
          <div style={{ color: 'var(--fg-primary)', fontWeight: 'bold', fontSize: 15 }}>{pred.away_team || p.away_team}</div>
          <div style={{ color: 'var(--accent)', fontSize: 22, fontWeight: 'bold' }}>{xg.away?.toFixed(2)}</div>
          <div style={{ color: 'var(--fg-muted)', fontSize: 11 }}>xG</div>
          {playerA.elo_bonus != null && (
            <div style={{ color: playerA.elo_bonus > 0 ? 'var(--green)' : 'var(--red)', fontSize: 11, marginTop: 2 }}>
              Elo: {playerA.elo_bonus > 0 ? '+' : ''}{playerA.elo_bonus?.toFixed(1)}
            </div>
          )}
        </div>
      </div>

      {/* WDL Bar */}
      <div>
        <div style={{ display: 'flex', height: 10, borderRadius: 5, overflow: 'hidden', background: 'var(--bg-input)' }}>
          <div style={{ width: `${(wdl.home_win || 0) * 100}%`, background: 'var(--green)' }} />
          <div style={{ width: `${(wdl.draw || 0) * 100}%`, background: 'var(--yellow)' }} />
          <div style={{ width: `${(wdl.away_win || 0) * 100}%`, background: 'var(--red)' }} />
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4, fontSize: 11 }}>
          <span style={{ color: 'var(--green)', fontWeight: 'bold' }}>Home {(wdl.home_win * 100)?.toFixed(1)}%</span>
          <span style={{ color: 'var(--yellow)', fontWeight: 'bold' }}>Draw {(wdl.draw * 100)?.toFixed(1)}%</span>
          <span style={{ color: 'var(--red)', fontWeight: 'bold' }}>Away {(wdl.away_win * 100)?.toFixed(1)}%</span>
        </div>
      </div>

      {/* Score + Over/Under */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, textAlign: 'center' }}>
        <div style={{ background: 'var(--bg-hover)', borderRadius: 6, padding: '8px 4px' }}>
          <div style={{ color: 'var(--fg-muted)', fontSize: 10 }}>Predicted Score</div>
          <div style={{ color: 'var(--fg-primary)', fontSize: 18, fontWeight: 'bold' }}>{p.most_likely_score}</div>
        </div>
        <div style={{ background: 'var(--bg-hover)', borderRadius: 6, padding: '8px 4px' }}>
          <div style={{ color: 'var(--fg-muted)', fontSize: 10 }}>Over 2.5</div>
          <div style={{ color: 'var(--green)', fontSize: 18, fontWeight: 'bold' }}>{(p.over_under?.over_25 * 100)?.toFixed(0)}%</div>
        </div>
        <div style={{ background: 'var(--bg-hover)', borderRadius: 6, padding: '8px 4px' }}>
          <div style={{ color: 'var(--fg-muted)', fontSize: 10 }}>Under 2.5</div>
          <div style={{ color: 'var(--red)', fontSize: 18, fontWeight: 'bold' }}>{(p.over_under?.under_25 * 100)?.toFixed(0)}%</div>
        </div>
      </div>

      {/* Top Players */}
      {(playerH.top_players?.length > 0 || playerA.top_players?.length > 0) && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
          <div>
            <div style={{ color: 'var(--fg-muted)', fontSize: 10, marginBottom: 4 }}>Top Players</div>
            {playerH.top_players?.slice(0, 5).map((tp, i) => {
              const parts = tp.match(/(.+?)\s*\((\d+)\)/);
              return parts ? (
                <div key={i} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, padding: '2px 0' }}>
                  <span style={{ color: 'var(--fg-body)' }}>{parts[1]}</span>
                  <span style={{ color: parts[2] > 70 ? 'var(--green)' : 'var(--accent)', fontWeight: 'bold' }}>{parts[2]}</span>
                </div>
              ) : (
                <div key={i} style={{ fontSize: 11, color: 'var(--fg-body)' }}>{tp}</div>
              );
            })}
          </div>
          <div>
            <div style={{ color: 'var(--fg-muted)', fontSize: 10, marginBottom: 4 }}>Top Players</div>
            {playerA.top_players?.slice(0, 5).map((tp, i) => {
              const parts = tp.match(/(.+?)\s*\((\d+)\)/);
              return parts ? (
                <div key={i} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, padding: '2px 0' }}>
                  <span style={{ color: 'var(--fg-body)' }}>{parts[1]}</span>
                  <span style={{ color: parts[2] > 70 ? 'var(--green)' : 'var(--accent)', fontWeight: 'bold' }}>{parts[2]}</span>
                </div>
              ) : (
                <div key={i} style={{ fontSize: 11, color: 'var(--fg-body)' }}>{tp}</div>
              );
            })}
          </div>
        </div>
      )}

      {/* Model Breakdown */}
      {full && Object.keys(models).length > 0 && (
        <div>
          <div style={{ color: 'var(--fg-muted)', fontSize: 10, marginBottom: 6 }}>Model Breakdown ({p.method})</div>
          <div style={{ display: 'grid', gap: 4 }}>
            {Object.entries(models).map(([name, m]) => (
              <div key={name} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 11 }}>
                <span style={{ color: 'var(--fg-muted)', width: 90 }}>{name.replace('_', ' ')}</span>
                <div style={{ flex: 1, display: 'flex', height: 6, borderRadius: 3, overflow: 'hidden', background: 'var(--bg-input)' }}>
                  <div style={{ width: `${(m.wdl?.[0] || 0) * 100}%`, background: 'var(--green)' }} />
                  <div style={{ width: `${(m.wdl?.[1] || 0) * 100}%`, background: 'var(--yellow)' }} />
                  <div style={{ width: `${(m.wdl?.[2] || 0) * 100}%`, background: 'var(--red)' }} />
                </div>
                <span style={{ color: 'var(--fg-body)', width: 50, textAlign: 'right' }}>{(m.wdl?.[0] * 100)?.toFixed(0)}%</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}


// ============================================================
// Knockout Bracket Simulation
// ============================================================

function KnockoutBracket() {
  const [nSims, setNSims] = useState(100);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [sampleIdx, setSampleIdx] = useState(0);

  async function runSimulation() {
    setLoading(true);
    setResult(null);
    try {
      const d = await post('/worldcup/knockout', { n_sims: nSims });
      setResult(d);
    } catch (err) {
      setResult({ status: 'error', message: err.message });
    }
    setLoading(false);
  }

  if (!result || result.status === 'error') {
    return (
      <div>
        <h2 style={{ color: 'var(--fg-primary)', fontSize: 16, marginBottom: 16 }}>Knockout Bracket Prediction</h2>
        <p style={{ color: 'var(--fg-muted)', fontSize: 13, marginBottom: 16 }}>
          Simulate the full knockout bracket from Round of 32 to Final. Each simulation runs group stage to determine qualifiers, then knockout rounds.
        </p>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 16 }}>
          {[50, 100, 200, 500].map(n => (
            <button key={n} onClick={() => setNSims(n)}
              style={{
                background: nSims === n ? 'var(--accent)' : 'var(--bg-input)',
                color: nSims === n ? '#fff' : 'var(--fg-muted)',
                border: 'none', padding: '8px 16px', borderRadius: 6, cursor: 'pointer', fontSize: 12
              }}>
              {n} sims
            </button>
          ))}
          <button onClick={runSimulation} disabled={loading}
            style={{ background: loading ? 'var(--bg-input)' : 'var(--green)', color: '#fff', border: 'none', padding: '10px 24px', borderRadius: 6, cursor: 'pointer', fontSize: 13, fontWeight: 'bold' }}>
            {loading ? 'Simulating...' : 'Start Simulation'}
          </button>
        </div>
        {result?.message && <div style={{ color: 'var(--red)', padding: 12, background: 'rgba(248,81,73,0.1)', borderRadius: 6 }}>{result.message}</div>}
      </div>
    );
  }

  const r = result.result;
  const bracket = r.sample_bracket;

  const stageLabels = { r32: 'Round of 32', r16: 'Round of 16', qf: 'Quarter-Finals', sf: 'Semi-Finals', final: 'Final' };
  const stages = ['r32', 'r16', 'qf', 'sf', 'final'];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h2 style={{ color: 'var(--fg-primary)', fontSize: 16 }}>Knockout Bracket ({result.n_simulations} simulations)</h2>
        <button onClick={() => setResult(null)}
          style={{ background: 'var(--bg-input)', color: 'var(--fg-muted)', border: 'none', padding: '6px 12px', borderRadius: 6, cursor: 'pointer', fontSize: 12 }}>
          Reset
        </button>
      </div>

      {/* Champion & Finalist Probs */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 20 }}>
        <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8, padding: 16 }}>
          <div style={{ color: 'var(--fg-muted)', fontSize: 11, marginBottom: 8 }}>Champion Probability</div>
          {r.champion_probs.slice(0, 8).map((t, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
              <span style={{ color: i === 0 ? 'var(--green)' : 'var(--fg-body)', fontSize: 12, width: 140, fontWeight: i === 0 ? 'bold' : 'normal' }}>{t.team}</span>
              <div style={{ flex: 1, height: 8, background: 'var(--bg-input)', borderRadius: 4, overflow: 'hidden' }}>
                <div style={{ width: `${t.prob * 100}%`, height: '100%', background: i === 0 ? 'var(--green)' : 'var(--accent)', borderRadius: 4 }} />
              </div>
              <span style={{ color: 'var(--fg-muted)', fontSize: 11, width: 40, textAlign: 'right' }}>{(t.prob * 100).toFixed(1)}%</span>
            </div>
          ))}
        </div>
        <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8, padding: 16 }}>
          <div style={{ color: 'var(--fg-muted)', fontSize: 11, marginBottom: 8 }}>Reach Final Probability</div>
          {r.reach_final.slice(0, 8).map((t, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
              <span style={{ color: 'var(--fg-body)', fontSize: 12, width: 140 }}>{t.team}</span>
              <div style={{ flex: 1, height: 8, background: 'var(--bg-input)', borderRadius: 4, overflow: 'hidden' }}>
                <div style={{ width: `${t.prob * 100}%`, height: '100%', background: 'var(--yellow)', borderRadius: 4 }} />
              </div>
              <span style={{ color: 'var(--fg-muted)', fontSize: 11, width: 40, textAlign: 'right' }}>{(t.prob * 100).toFixed(1)}%</span>
            </div>
          ))}
        </div>
      </div>

      {/* Sample Bracket */}
      <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8, padding: 16 }}>
        <div style={{ color: 'var(--fg-muted)', fontSize: 11, marginBottom: 12 }}>Sample Bracket (one simulation)</div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 8 }}>
          {stages.map(stage => (
            <div key={stage}>
              <div style={{ color: 'var(--fg-primary)', fontSize: 12, fontWeight: 'bold', marginBottom: 8, textAlign: 'center' }}>{stageLabels[stage]}</div>
              {bracket[stage]?.map((m, i) => (
                <div key={i} style={{ background: 'var(--bg-hover)', borderRadius: 4, padding: '4px 6px', marginBottom: 4, fontSize: 11 }}>
                  <div style={{ color: m.winner === m.home ? 'var(--green)' : 'var(--fg-body)', fontWeight: m.winner === m.home ? 'bold' : 'normal' }}>{m.home}</div>
                  <div style={{ color: m.winner === m.away ? 'var(--green)' : 'var(--fg-body)', fontWeight: m.winner === m.away ? 'bold' : 'normal' }}>{m.away}</div>
                  <div style={{ color: 'var(--fg-muted)', fontSize: 9, textAlign: 'center' }}>{m.method}</div>
                </div>
              ))}
            </div>
          ))}
        </div>
        {bracket.champion && (
          <div style={{ textAlign: 'center', marginTop: 12, padding: 12, background: 'rgba(63,185,80,0.1)', borderRadius: 8 }}>
            <span style={{ color: 'var(--green)', fontSize: 16, fontWeight: 'bold' }}>Champion: {bracket.champion}</span>
          </div>
        )}
      </div>
    </div>
  );
}


// ============================================================
// Golden Ball Prediction
// ============================================================

function GoldenBall() {
  const [candidates, setCandidates] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    get('/worldcup/golden-ball').then(d => {
      setCandidates(d.candidates || []);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  if (loading) return <div style={{ color: 'var(--fg-muted)' }}>Loading...</div>;

  return (
    <div>
      <h2 style={{ color: 'var(--fg-primary)', fontSize: 16, marginBottom: 8 }}>Golden Ball Predictions</h2>
      <p style={{ color: 'var(--fg-muted)', fontSize: 12, marginBottom: 16 }}>
        Top players from WC2026 qualified teams, ranked by Elo rating. The Golden Ball award goes to the best player of the tournament.
      </p>

      <div style={{ display: 'grid', gap: 6 }}>
        {candidates.map((c, i) => {
          const medal = i === 0 ? '??' : i === 1 ? '??' : i === 2 ? '??' : `${i + 1}`;
          const eloColor = c.elo > 85 ? 'var(--green)' : c.elo > 75 ? 'var(--accent)' : 'var(--fg-muted)';
          return (
            <div key={i} style={{
              display: 'grid', gridTemplateColumns: '32px 1fr 100px 80px 120px 80px',
              alignItems: 'center', gap: 8,
              background: i < 3 ? 'rgba(63,185,80,0.05)' : 'var(--bg-card)',
              border: '1px solid var(--border)', borderRadius: 6, padding: '8px 12px',
              fontSize: 12,
            }}>
              <span style={{ fontSize: i < 3 ? 18 : 12, textAlign: 'center' }}>{medal}</span>
              <div>
                <div style={{ color: 'var(--fg-primary)', fontWeight: 'bold' }}>{c.player}</div>
                <div style={{ color: 'var(--fg-muted)', fontSize: 11 }}>{c.team} ? {c.club}</div>
              </div>
              <div style={{ textAlign: 'center' }}>
                <span style={{ color: eloColor, fontWeight: 'bold', fontSize: 14 }}>{c.elo?.toFixed(0)}</span>
                <div style={{ color: 'var(--fg-muted)', fontSize: 9 }}>Elo Rating</div>
              </div>
              <div style={{ color: 'var(--fg-muted)', textAlign: 'center', fontSize: 11 }}>{c.position}</div>
              <div style={{ color: 'var(--fg-muted)', textAlign: 'center', fontSize: 11 }}>
                {c.market_value ? `?${(c.market_value / 1000000).toFixed(0)}M` : '-'}
              </div>
              <div style={{ width: 60 }}>
                <div style={{ height: 4, background: 'var(--bg-input)', borderRadius: 2, overflow: 'hidden' }}>
                  <div style={{ width: `${Math.min(100, (c.elo / 100) * 100)}%`, height: '100%', background: eloColor, borderRadius: 2 }} />
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}


// ============================================================
// Monte Carlo Simulate
// ============================================================

function Simulate() {
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [nSims, setNSims] = useState(500);

  async function runSimulation() {
    setLoading(true);
    try {
      const d = await post('/worldcup/simulate', { n_sims: nSims });
      setResult(d);
    } catch (err) {
      setResult({ status: 'error', message: err.message });
    }
    setLoading(false);
  }

  async function loadCached() {
    try {
      const d = await get('/worldcup/simulate/result');
      if (d.status === 'ok') setResult(d);
    } catch {}
  }

  useEffect(() => { loadCached(); }, []);

  return (
    <div>
      <h2 style={{ color: 'var(--fg-primary)', fontSize: 16, marginBottom: 16 }}>Monte Carlo Tournament Simulation</h2>

      <div style={{ display: 'flex', gap: 8, marginBottom: 20, alignItems: 'center' }}>
        {[500, 1000, 2000].map(n => (
          <button key={n} onClick={() => setNSims(n)}
            style={{
              background: nSims === n ? 'var(--accent)' : 'var(--bg-input)',
              color: nSims === n ? '#fff' : 'var(--fg-muted)',
              border: 'none', padding: '6px 14px', borderRadius: 6, cursor: 'pointer', fontSize: 12
            }}>
            {n} runs
          </button>
        ))}
        <button onClick={runSimulation} disabled={loading}
          style={{ background: loading ? 'var(--bg-input)' : 'var(--green)', color: '#fff', border: 'none', padding: '8px 20px', borderRadius: 6, cursor: 'pointer', fontSize: 13 }}>
          {loading ? 'Running...' : 'Start Simulation'}
        </button>
      </div>

      {result?.status === 'ok' && result.result && (
        <SimResult data={result.result} duration={result.duration_seconds} />
      )}
      {result?.status === 'error' && (
        <div style={{ color: 'var(--red)', padding: 12, background: 'rgba(248,81,73,0.1)', borderRadius: 6 }}>{result.message}</div>
      )}
    </div>
  );
}


function SimResult({ data, duration }) {
  const champions = Object.entries(data.champion_probs || {}).slice(0, 10);
  const finalists = Object.entries(data.reach_final || {}).slice(0, 10);
  const advancing = Object.entries(data.group_advance || {}).slice(0, 15);

  return (
    <div style={{ display: 'grid', gap: 16 }}>
      {duration && (
        <div style={{ color: 'var(--fg-muted)', fontSize: 12 }}>
          {data.n_simulations} simulations - {duration}s
        </div>
      )}

      <div style={cardStyle}>
        <div style={{ color: 'var(--accent)', fontWeight: 'bold', fontSize: 14, marginBottom: 12 }}>Champion Probability</div>
        {champions.map(([team, prob], i) => (
          <div key={team} style={{ display: 'flex', alignItems: 'center', marginBottom: 6 }}>
            <span style={{ width: 20, color: 'var(--fg-muted)', fontSize: 11 }}>{i + 1}</span>
            <span style={{ width: 120, color: 'var(--fg-primary)', fontSize: 13, fontWeight: i === 0 ? 'bold' : 'normal' }}>{team}</span>
            <div style={{ flex: 1, background: 'var(--bg-input)', height: 16, borderRadius: 3, overflow: 'hidden', marginRight: 8 }}>
              <div style={{ width: `${prob * 100}%`, background: i === 0 ? 'var(--yellow)' : 'var(--accent)', height: '100%', borderRadius: 3, transition: 'width 0.3s' }} />
            </div>
            <span style={{ width: 50, textAlign: 'right', color: 'var(--fg-primary)', fontSize: 13, fontWeight: 'bold' }}>{(prob * 100).toFixed(1)}%</span>
          </div>
        ))}
      </div>

      <div style={cardStyle}>
        <div style={{ color: 'var(--accent)', fontWeight: 'bold', fontSize: 14, marginBottom: 12 }}>Reach Final</div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px 24px' }}>
          {finalists.map(([team, prob]) => (
            <div key={team} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
              <span style={{ color: 'var(--fg-primary)' }}>{team}</span>
              <span style={{ color: 'var(--fg-muted)' }}>{(prob * 100).toFixed(1)}%</span>
            </div>
          ))}
        </div>
      </div>

      <div style={cardStyle}>
        <div style={{ color: 'var(--accent)', fontWeight: 'bold', fontSize: 14, marginBottom: 12 }}>Group Advance</div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '4px 16px' }}>
          {advancing.map(([team, prob]) => (
            <div key={team} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
              <span style={{ color: 'var(--fg-primary)' }}>{team}</span>
              <span style={{ color: prob > 0.7 ? 'var(--green)' : prob > 0.4 ? 'var(--yellow)' : 'var(--red)' }}>
                {(prob * 100).toFixed(0)}%
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}


// ============================================================
// Styles
// ============================================================

const cardStyle = {
  background: 'var(--bg-card)',
  border: '1px solid var(--border)',
  borderRadius: 8,
  padding: 12,
};

const thStyle = { padding: '4px 6px', textAlign: 'center', fontWeight: 'normal', fontSize: 11, whiteSpace: 'nowrap' };
const tdStyle = { padding: '4px 6px', textAlign: 'center', fontSize: 12 };
const smallBtn = { background: 'var(--bg-input)', color: 'var(--fg-muted)', border: 'none', padding: '4px 10px', borderRadius: 4, cursor: 'pointer', fontSize: 11 };

const selectStyle = {
  background: 'var(--bg-input)', color: 'var(--fg-primary)', border: '1px solid var(--border)',
  padding: '6px 10px', borderRadius: 6, fontSize: 12, minWidth: 120,
};
