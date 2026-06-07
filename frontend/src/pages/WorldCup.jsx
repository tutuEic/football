import { useState, useEffect, Component } from 'react';
import { get, post } from '../api';

class ErrorBoundary extends Component {
  constructor(props) { super(props); this.state = { error: null }; }
  static getDerivedStateFromError(error) { return { error }; }
  render() {
    if (this.state.error) {
      return (
        <div style={{ padding: 24, textAlign: 'center' }}>
          <h3 style={{ color: 'var(--red, #ef4444)' }}>Something went wrong</h3>
          <p style={{ color: 'var(--fg-muted)', fontSize: 13 }}>{this.state.error.message}</p>
          <button onClick={() => this.setState({ error: null })} style={{
            background: 'var(--bg-input)', color: 'var(--fg-primary)',
            border: 'none', padding: '6px 16px', borderRadius: 4, cursor: 'pointer', marginTop: 8,
          }}>Retry</button>
        </div>
      );
    }
    return this.props.children;
  }
}


const SUB_TABS = [
  { key: 'groups',    label: '小组赛' },
  { key: 'rankings',  label: '排名' },
  { key: 'matches',   label: '赛程' },
  { key: 'sandbox',   label: '沙盘模拟' },
  { key: 'knockout',  label: '淘汰赛预测' },
  { key: 'analysis',  label: '形势分析' },
];

export default function WorldCup() {
  const [subTab, setSubTab] = useState('groups');
  return (
    <ErrorBoundary>
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
      {subTab === 'sandbox'   && <Simulate />}
      {subTab === 'knockout'  && <KnockoutBracket />}
      {subTab === 'analysis'  && <TeamAnalysis />}
    </div>
    </ErrorBoundary>
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
    } catch (err) { console.error('API error:', err); }
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
    } catch (err) { console.error('API error:', err); }
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
  const [bracket, setBracket] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [simResult, setSimResult] = useState(null);
  const [simLoading, setSimLoading] = useState(false);
  const [nSims, setNSims] = useState(200);
  const [alerts, setAlerts] = useState(null);
  const [alertsLoading, setAlertsLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    get(`/worldcup/bracket?t=${Date.now()}`).then(d => {
      if (d.status === 'ok') setBracket(d.bracket);
      else setError(d.detail || 'Failed to load bracket');
      setLoading(false);
    }).catch(err => {
      setError(err.message);
      setLoading(false);
    });
    // Load upset alerts (with cache busting)
    setAlertsLoading(true);
    get(`/worldcup/upset-alerts?t=${Date.now()}`).then(d => {
      if (d.status === 'ok') setAlerts(d);
      setAlertsLoading(false);
    }).catch(() => setAlertsLoading(false));
  }, []);

  async function runSimulation() {
    setSimLoading(true);
    setSimResult(null);
    try {
      const d = await post('/worldcup/knockout', { n_sims: nSims });
      setSimResult(d);
    } catch (err) {
      setSimResult({ status: 'error', message: err.message });
    }
    setSimLoading(false);
  }

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 40 }}>
        <div style={{ color: 'var(--fg-muted)', fontSize: 14 }}>正在生成淘汰赛对阵图...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ color: 'var(--red)', padding: 12, background: 'rgba(248,81,73,0.1)', borderRadius: 6 }}>
        {error}
      </div>
    );
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h2 style={{ color: 'var(--fg-primary)', fontSize: 16 }}>🏆 淘汰赛晋级之路预测</h2>
        <div style={{ display: 'flex', gap: 8 }}>
          <button onClick={() => { setLoading(true); get('/worldcup/bracket').then(d => { setBracket(d.bracket); setLoading(false); }); }}
            style={{ background: 'var(--bg-input)', color: 'var(--fg-muted)', border: 'none', padding: '6px 12px', borderRadius: 6, cursor: 'pointer', fontSize: 12 }}>
            重新预测
          </button>
        </div>
      </div>

      {/* Monte Carlo Simulation Controls */}
      <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8, padding: 12, marginBottom: 16 }}>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <span style={{ color: 'var(--fg-muted)', fontSize: 12 }}>蒙特卡洛模拟:</span>
          {[100, 200, 500, 1000].map(n => (
            <button key={n} onClick={() => setNSims(n)}
              style={{
                background: nSims === n ? 'var(--accent)' : 'var(--bg-input)',
                color: nSims === n ? '#fff' : 'var(--fg-muted)',
                border: 'none', padding: '4px 10px', borderRadius: 4, cursor: 'pointer', fontSize: 11
              }}>
              {n}次
            </button>
          ))}
          <button onClick={runSimulation} disabled={simLoading}
            style={{ background: simLoading ? 'var(--bg-input)' : 'var(--green)', color: '#fff', border: 'none', padding: '6px 16px', borderRadius: 4, cursor: 'pointer', fontSize: 12 }}>
            {simLoading ? '模拟中...' : '开始模拟'}
          </button>
          {simLoading && <span style={{ color: 'var(--fg-muted)', fontSize: 11 }}>预计10-30秒</span>}
        </div>
      </div>

      {/* Simulation Results */}
      {simResult && simResult.status === 'ok' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 16 }}>
          <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8, padding: 12 }}>
            <div style={{ color: 'var(--fg-muted)', fontSize: 11, marginBottom: 8 }}>🏅 夺冠概率 ({simResult.n_simulations}次模拟)</div>
            {simResult.result.champion_probs.slice(0, 8).map((t, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3 }}>
                <span style={{ color: i === 0 ? 'var(--green)' : 'var(--fg-body)', fontSize: 11, width: 120, fontWeight: i === 0 ? 'bold' : 'normal' }}>{t.team}</span>
                <div style={{ flex: 1, height: 6, background: 'var(--bg-input)', borderRadius: 3, overflow: 'hidden' }}>
                  <div style={{ width: `${t.prob * 100}%`, height: '100%', background: i === 0 ? 'var(--green)' : 'var(--accent)', borderRadius: 3 }} />
                </div>
                <span style={{ color: 'var(--fg-muted)', fontSize: 10, width: 35, textAlign: 'right' }}>{(t.prob * 100).toFixed(1)}%</span>
              </div>
            ))}
          </div>
          <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8, padding: 12 }}>
            <div style={{ color: 'var(--fg-muted)', fontSize: 11, marginBottom: 8 }}>🥈 进决赛概率</div>
            {simResult.result.reach_final.slice(0, 8).map((t, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3 }}>
                <span style={{ color: 'var(--fg-body)', fontSize: 11, width: 120 }}>{t.team}</span>
                <div style={{ flex: 1, height: 6, background: 'var(--bg-input)', borderRadius: 3, overflow: 'hidden' }}>
                  <div style={{ width: `${t.prob * 100}%`, height: '100%', background: 'var(--yellow)', borderRadius: 3 }} />
                </div>
                <span style={{ color: 'var(--fg-muted)', fontSize: 10, width: 35, textAlign: 'right' }}>{(t.prob * 100).toFixed(1)}%</span>
              </div>
            ))}
          </div>
        </div>
      )}
      {simResult && simResult.status === 'error' && (
        <div style={{ color: 'var(--red)', padding: 8, background: 'rgba(248,81,73,0.1)', borderRadius: 6, marginBottom: 16, fontSize: 12 }}>
          {simResult.message}
        </div>
      )}

      {/* Bracket Visualization */}
      {simResult?.result?.sample_bracket ? (
        <BracketView bracket={simResult.result.sample_bracket} />
      ) : bracket ? (
        <BracketView bracket={bracket} />
      ) : null}

      {/* Upset Alerts Panel */}
      {alerts && alerts.alerts && alerts.alerts.length > 0 && (
        <div style={{ marginTop: 16, background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8, padding: 12 }}>
          <div style={{ color: 'var(--fg-primary)', fontSize: 14, fontWeight: 'bold', marginBottom: 10 }}>
            ⚠️ 爆冷预警
          </div>

          {/* Penalty ranking */}
          {alerts.penalty_ranking && (
            <div style={{ marginBottom: 12 }}>
              <div style={{ color: 'var(--fg-muted)', fontSize: 11, marginBottom: 6 }}>🎯 点球大战能力排名</div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 4 }}>
                {alerts.penalty_ranking.slice(0, 10).map((t, i) => (
                  <div key={i} style={{
                    background: i < 3 ? 'rgba(63,185,80,0.08)' : 'var(--bg-input)',
                    border: `1px solid ${i < 3 ? 'rgba(63,185,80,0.2)' : 'var(--border)'}`,
                    borderRadius: 4, padding: '4px 6px', textAlign: 'center'
                  }}>
                    <div style={{ color: i === 0 ? 'var(--green)' : 'var(--fg-body)', fontSize: 10, fontWeight: i === 0 ? 'bold' : 'normal' }}>
                      {FLAGS[t.team] || '🏳️'} {t.team}
                    </div>
                    <div style={{ color: 'var(--accent)', fontSize: 11, fontWeight: 'bold' }}>{t.penalty}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Alert categories */}
          {['tanking_risk', 'penalty_strength'].map(type => {
            const typeAlerts = alerts.alerts.filter(a => a.type === type);
            if (typeAlerts.length === 0) return null;
            const labels = { dark_horse: '🐴 黑马潜质', upset_possible: '💥 爆冷预警', tanking_risk: '🤔 放水风险', penalty_strength: '🎯 点球优势' };
            const colors = { dark_horse: 'var(--yellow)', upset_possible: 'var(--red)', tanking_risk: 'var(--fg-muted)', penalty_strength: 'var(--green)' };
            return (
              <div key={type} style={{ marginBottom: 8 }}>
                <div style={{ color: colors[type], fontSize: 11, fontWeight: 'bold', marginBottom: 4 }}>{labels[type]}</div>
                {typeAlerts.map((a, i) => (
                  <div key={i} style={{
                    display: 'flex', alignItems: 'center', gap: 6, padding: '3px 6px',
                    background: a.impact === 'high' ? 'rgba(248,81,73,0.06)' : 'transparent',
                    borderRadius: 4, marginBottom: 2
                  }}>
                    <span style={{
                      background: a.impact === 'high' ? 'var(--red)' : a.impact === 'medium' ? 'var(--yellow)' : 'var(--bg-input)',
                      color: a.impact === 'low' ? 'var(--fg-muted)' : '#fff',
                      padding: '1px 4px', borderRadius: 3, fontSize: 8, fontWeight: 'bold'
                    }}>{a.impact?.toUpperCase()}</span>
                    {a.group && a.partner_group && (
                      <span style={{ color: 'var(--accent)', fontSize: 9, fontWeight: 'bold', background: 'rgba(201,169,110,0.1)', padding: '1px 4px', borderRadius: 3 }}>
                        {a.group}组↔{a.partner_group}组
                      </span>
                    )}
                    <span style={{ color: 'var(--fg-body)', fontSize: 11, flex: 1 }}>{a.description}</span>
                  </div>
                ))}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}


// ============================================================
// TeamAnalysis - 形势分析
// ============================================================

function TeamAnalysis() {
  const [teams, setTeams] = useState([]);
  const [selectedTeam, setSelectedTeam] = useState('');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [groupAnalysis, setGroupAnalysis] = useState({});
  const [selectedGroup, setSelectedGroup] = useState('');

  useEffect(() => {
    get('/worldcup/rankings').then(d => {
      if (d.rankings) setTeams(d.rankings.map(t => t.team));
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (!selectedTeam) { setData(null); return; }
    setLoading(true);
    get(`/worldcup/team-analysis/${encodeURIComponent(selectedTeam)}?t=${Date.now()}`).then(d => {
      if (d.status === 'ok') {
        setData(d);
        // Load group analysis
        if (d.group && !groupAnalysis[d.group]) {
          get(`/worldcup/group-analysis/${d.group}?t=${Date.now()}`).then(g => {
            if (g.status === 'ok') {
              setGroupAnalysis(prev => ({...prev, [d.group]: g.text}));
            }
          }).catch(() => {});
        }
      }
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [selectedTeam]);

  const a = data?.analysis;

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
        {selectedTeam ? (
          <button onClick={() => setSelectedTeam('')}
            style={{ background: 'var(--bg-input)', border: 'none', padding: '6px 12px', borderRadius: 6, cursor: 'pointer', color: 'var(--fg-muted)', fontSize: 12 }}>← 返回</button>
        ) : null}
        <h2 style={{ color: 'var(--fg-primary)', fontSize: 16, margin: 0 }}>
          {selectedTeam ? `${FLAGS[selectedTeam] || '🏳️'} ${selectedTeam} 形势分析` : '📊 球队形势分析'}
        </h2>
        {selectedTeam && data && <span style={{ color: 'var(--fg-muted)', fontSize: 11 }}>{data.group}组 · {data.squad_size}人</span>}
      </div>

      {/* Team Selection Grid (shown when no team selected) */}
      {!selectedTeam && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(100px, 1fr))', gap: 6 }}>
          {teams.map(t => (
            <button key={t} onClick={() => setSelectedTeam(t)}
              style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 6, padding: '8px 4px', cursor: 'pointer', fontSize: 11, color: 'var(--fg-body)' }}>
              {FLAGS[t] || '🏳️'} {t}
            </button>
          ))}
        </div>
      )}

      {/* Loading */}
      {selectedTeam && loading && (
        <div style={{ color: 'var(--fg-muted)', padding: 20 }}>正在分析 {selectedTeam}...</div>
      )}

      {/* Analysis Content */}
      {selectedTeam && !loading && data && (
        <div>
          {/* Team Card */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
            {/* Basic Info */}
            <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8, padding: 12 }}>
              <div style={{ color: 'var(--fg-muted)', fontSize: 11, marginBottom: 8 }}>📋 球队基础信息</div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 4, fontSize: 11 }}>
                <div><span style={{ color: 'var(--fg-muted)' }}>所属小组:</span> <span style={{ color: 'var(--accent)' }}>{data.group}组</span></div>
                <div><span style={{ color: 'var(--fg-muted)' }}>阵容评分:</span> <span style={{ color: 'var(--fg-primary)' }}>{a?.starting_xi?.toFixed(0)}</span></div>
                <div><span style={{ color: 'var(--fg-muted)' }}>进攻质量:</span> <span style={{ color: '#e74c3c' }}>{a?.attack_quality?.toFixed(0)}</span></div>
                <div><span style={{ color: 'var(--fg-muted)' }}>防守质量:</span> <span style={{ color: '#3498db' }}>{a?.defense_quality?.toFixed(0)}</span></div>
                <div><span style={{ color: 'var(--fg-muted)' }}>平均年龄:</span> <span>{a?.avg_age}</span></div>
                <div><span style={{ color: 'var(--fg-muted)' }}>定位球:</span> <span>{a?.set_piece}%</span></div>
                <div><span style={{ color: 'var(--fg-muted)' }}>战术风格:</span> <span style={{ color: 'var(--accent)' }}>{data.tactical_style}</span></div>
                <div><span style={{ color: 'var(--fg-muted)' }}>阵容:</span> <span>{data.formation_tendency}</span></div>
              </div>
              <div style={{ color: 'var(--fg-body)', fontSize: 11, marginTop: 8, padding: '6px 8px', background: 'rgba(201,169,110,0.06)', borderRadius: 4 }}>
                {data.style_description}
              </div>
            </div>

            {/* Qualification Prediction */}
            <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8, padding: 12 }}>
              <div style={{ color: 'var(--fg-muted)', fontSize: 11, marginBottom: 8 }}>🎯 出线预测 (100次模拟)</div>
              {data.qualification && (
                <div>
                  <div style={{ display: 'flex', gap: 4, marginBottom: 8 }}>
                    {[{k: 1, l: '第1', v: data.qualification.as_1st, c: 'var(--green)'},
                      {k: 2, l: '第2', v: data.qualification.as_2nd, c: 'var(--yellow)'},
                      {k: 3, l: '第3', v: data.qualification.as_3rd, c: 'var(--fg-muted)'},
                      {k: 0, l: '淘汰', v: data.qualification.eliminated, c: 'var(--red)'}
                    ].map(item => (
                      <div key={item.k} style={{ flex: 1, textAlign: 'center', padding: '6px 4px', background: 'var(--bg-input)', borderRadius: 4 }}>
                        <div style={{ color: item.c, fontSize: 16, fontWeight: 'bold' }}>{item.v}%</div>
                        <div style={{ color: 'var(--fg-muted)', fontSize: 9 }}>{item.l}</div>
                      </div>
                    ))}
                  </div>
                  <div style={{ color: 'var(--fg-body)', fontSize: 11 }}>
                    总出线概率: <span style={{ color: 'var(--green)', fontWeight: 'bold' }}>{data.qualification.total_pct}%</span>
                  </div>
                </div>
              )}

              {/* Strategy */}
              {data.strategy && data.strategy.length > 0 && (
                <div style={{ marginTop: 8 }}>
                  {data.strategy.map((s, i) => (
                    <div key={i} style={{ color: 'var(--accent)', fontSize: 11, padding: '3px 0' }}>💡 {s}</div>
                  ))}
                </div>
              )}

              {/* Knockout Path */}
              {data.knockout_path && data.knockout_path.length > 0 && (
                <div style={{ marginTop: 8 }}>
                  <div style={{ color: 'var(--fg-muted)', fontSize: 10, marginBottom: 4 }}>淘汰赛可能对手:</div>
                  {data.knockout_path.slice(0, 3).map((k, i) => (
                    <div key={i} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, padding: '2px 0' }}>
                      <span style={{ color: 'var(--fg-body)' }}>{FLAGS[k.opponent] || '🏳️'} {k.opponent}</span>
                      <span style={{ color: 'var(--fg-muted)' }}>ELO {k.elo?.toFixed(0)} · {k.probability}%</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Core Players */}
          <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8, padding: 12, marginBottom: 12 }}>
            <div style={{ color: 'var(--fg-muted)', fontSize: 11, marginBottom: 8 }}>⭐ 核心球员</div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 6 }}>
              {(data.core_players || []).map((p, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 8px', background: 'var(--bg-input)', borderRadius: 4 }}>
                  <span style={{ color: 'var(--accent)', fontSize: 11, fontWeight: 'bold', width: 28, textAlign: 'right' }}>{p.elo}</span>
                  <div style={{ flex: 1 }}>
                    <div style={{ color: 'var(--fg-primary)', fontSize: 11, fontWeight: 'bold' }}>{p.name}</div>
                    <div style={{ color: 'var(--fg-muted)', fontSize: 9 }}>{p.position} · {p.club}</div>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ color: 'var(--fg-muted)', fontSize: 9 }}>{p.age ? `${p.age}岁` : ''}</div>
                    {p.goals_per_90 > 0 && <div style={{ color: 'var(--green)', fontSize: 9 }}>G/90 {p.goals_per_90}</div>}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Risks */}
          {(data.risks || []).length > 0 && (
            <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8, padding: 12, marginBottom: 12 }}>
              <div style={{ color: 'var(--fg-muted)', fontSize: 11, marginBottom: 8 }}>⚠️ 风险因素</div>
              {data.risks.map((r, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '3px 0', fontSize: 11 }}>
                  <span style={{ color: 'var(--red)', fontSize: 9 }}>●</span>
                  <span style={{ color: 'var(--fg-body)' }}>{r}</span>
                </div>
              ))}
            </div>
          )}

          {/* Group Analysis Article */}
          {data.group && groupAnalysis[data.group] && (
            <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8, padding: 12 }}>
              <div style={{ color: 'var(--fg-muted)', fontSize: 11, marginBottom: 8 }}>📰 {data.group}组形势分析</div>
              <div style={{ color: 'var(--fg-body)', fontSize: 12, lineHeight: 1.8, whiteSpace: 'pre-wrap' }}>
                {groupAnalysis[data.group]}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}


// ============================================================
// BracketView - FIFA-style knockout bracket
// ============================================================

function BracketView({ bracket }) {
  const stageGap = [8, 16, 28, 44];

  const splitHalf = (matches) => {
    if (!matches) return [[], []];
    const mid = Math.ceil(matches.length / 2);
    return [matches.slice(0, mid), matches.slice(mid)];
  };

  const [r32L, r32R] = splitHalf(bracket.r32);
  const [r16L, r16R] = splitHalf(bracket.r16);
  const [qfL, qfR] = splitHalf(bracket.qf);
  const [sfL, sfR] = splitHalf(bracket.sf);

  // Split groups into left half (first 6) and right half (last 6)
  const groups = bracket.groups || [];
  const midG = Math.ceil(groups.length / 2);
  const groupsL = groups.slice(0, midG);
  const groupsR = groups.slice(midG);

  return (
    <div style={{
      background: 'linear-gradient(135deg, #2d0a0a 0%, #1a0f0f 30%, #0f0a1a 60%, #0a1a2d 100%)',
      border: '2px solid #c9a96e', borderRadius: 12, padding: 16,
      position: 'relative', overflow: 'auto'
    }}>
      {/* Header */}
      <div style={{ textAlign: 'center', marginBottom: 12 }}>
        <div style={{ color: '#c9a96e', fontSize: 18, fontWeight: 'bold', letterSpacing: 3 }}>2026美加墨世界杯</div>
        <div style={{ color: 'rgba(201,169,110,0.5)', fontSize: 10, marginTop: 2, letterSpacing: 2 }}>FIFA WORLD CUP 2026 · 淘汰赛晋级之路</div>
        <div style={{ width: 160, height: 1, background: 'linear-gradient(90deg, transparent, #c9a96e, transparent)', margin: '6px auto' }} />
      </div>

      <div style={{ display: 'flex', alignItems: 'stretch', gap: 2 }}>

        {/* LEFT: Groups → R32 → R16 → QF → SF */}
        {/* Groups */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4, minWidth: 90 }}>
          <div style={{ color: '#c9a96e', fontSize: 8, textAlign: 'center', fontWeight: 'bold', letterSpacing: 1, marginBottom: 2 }}>小组赛</div>
          {groupsL.map(g => (
            <div key={g.group} style={{ background: 'rgba(201,169,110,0.04)', border: '1px solid rgba(201,169,110,0.15)', borderRadius: 3, padding: '2px 4px' }}>
              <div style={{ color: '#c9a96e', fontSize: 8, fontWeight: 'bold', marginBottom: 1 }}>组{g.group}</div>
              {g.teams.map(t => (
                <div key={t.team} style={{ display: 'flex', alignItems: 'center', gap: 2, fontSize: 9, padding: '1px 0' }}>
                  <span style={{ color: t.rank === 1 ? '#c9a96e' : 'rgba(255,255,255,0.5)', fontWeight: t.rank === 1 ? 'bold' : 'normal' }}>
                    {FLAGS[t.team] || '🏳️'} {t.team}
                  </span>
                  <span style={{ color: 'rgba(255,255,255,0.3)', fontSize: 7, marginLeft: 'auto' }}>{t.pts || t.points}分</span>
                </div>
              ))}
            </div>
          ))}
        </div>

        {/* R32 Left */}
        <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: stageGap[0] }}>
          <div style={{ color: '#c9a96e', fontSize: 8, textAlign: 'center', fontWeight: 'bold', letterSpacing: 1, marginBottom: 2 }}>1/16决赛</div>
          {r32L.map((m, i) => <MatchCard key={i} match={m} half="left" />)}
        </div>

        {/* R16 Left */}
        <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: stageGap[1] }}>
          <div style={{ color: '#c9a96e', fontSize: 8, textAlign: 'center', fontWeight: 'bold', letterSpacing: 1, marginBottom: 2 }}>1/8决赛</div>
          {r16L.map((m, i) => <MatchCard key={i} match={m} half="left" />)}
        </div>

        {/* QF Left */}
        <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: stageGap[2] }}>
          <div style={{ color: '#c9a96e', fontSize: 8, textAlign: 'center', fontWeight: 'bold', letterSpacing: 1, marginBottom: 2 }}>1/4决赛</div>
          {qfL.map((m, i) => <MatchCard key={i} match={m} half="left" />)}
        </div>

        {/* SF Left */}
        <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: stageGap[3] }}>
          <div style={{ color: '#c9a96e', fontSize: 8, textAlign: 'center', fontWeight: 'bold', letterSpacing: 1, marginBottom: 2 }}>半决赛</div>
          {sfL.map((m, i) => <MatchCard key={i} match={m} half="left" />)}
        </div>

        {/* CENTER - Trophy + Final + Third-place */}
        <div style={{ width: 100, textAlign: 'center', flexShrink: 0, display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center' }}>
          <div style={{ fontSize: 32, filter: 'drop-shadow(0 0 10px rgba(201,169,110,0.5))' }}>🏆</div>
          {bracket.final?.[0] && (
            <div style={{ marginTop: 6 }}>
              <MatchCard match={bracket.final[0]} half="center" />
            </div>
          )}
          {bracket.champion && (
            <div style={{ marginTop: 4 }}>
              <div style={{ color: '#c9a96e', fontSize: 12, fontWeight: 'bold', textShadow: '0 0 6px rgba(201,169,110,0.3)' }}>{bracket.champion}</div>
              <div style={{ color: 'rgba(201,169,110,0.4)', fontSize: 7, letterSpacing: 2 }}>CHAMPION</div>
            </div>
          )}
          {/* Third-place match */}
          {bracket.third?.[0] && (
            <div style={{ marginTop: 10, paddingTop: 8, borderTop: '1px solid rgba(201,169,110,0.2)' }}>
              <div style={{ color: 'rgba(201,169,110,0.4)', fontSize: 7, marginBottom: 4, letterSpacing: 1 }}>三四名决赛</div>
              <MatchCard match={bracket.third[0]} half="center" />
            </div>
          )}
        </div>

        {/* SF Right */}
        <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: stageGap[3] }}>
          <div style={{ color: '#4a9eff', fontSize: 8, textAlign: 'center', fontWeight: 'bold', letterSpacing: 1, marginBottom: 2 }}>半决赛</div>
          {sfR.map((m, i) => <MatchCard key={i} match={m} half="right" />)}
        </div>

        {/* QF Right */}
        <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: stageGap[2] }}>
          <div style={{ color: '#4a9eff', fontSize: 8, textAlign: 'center', fontWeight: 'bold', letterSpacing: 1, marginBottom: 2 }}>1/4决赛</div>
          {qfR.map((m, i) => <MatchCard key={i} match={m} half="right" />)}
        </div>

        {/* R16 Right */}
        <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: stageGap[1] }}>
          <div style={{ color: '#4a9eff', fontSize: 8, textAlign: 'center', fontWeight: 'bold', letterSpacing: 1, marginBottom: 2 }}>1/8决赛</div>
          {r16R.map((m, i) => <MatchCard key={i} match={m} half="right" />)}
        </div>

        {/* R32 Right */}
        <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: stageGap[0] }}>
          <div style={{ color: '#4a9eff', fontSize: 8, textAlign: 'center', fontWeight: 'bold', letterSpacing: 1, marginBottom: 2 }}>1/16决赛</div>
          {r32R.map((m, i) => <MatchCard key={i} match={m} half="right" />)}
        </div>

        {/* RIGHT: Groups */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4, minWidth: 90 }}>
          <div style={{ color: '#4a9eff', fontSize: 8, textAlign: 'center', fontWeight: 'bold', letterSpacing: 1, marginBottom: 2 }}>小组赛</div>
          {groupsR.map(g => (
            <div key={g.group} style={{ background: 'rgba(74,158,255,0.04)', border: '1px solid rgba(74,158,255,0.15)', borderRadius: 3, padding: '2px 4px' }}>
              <div style={{ color: '#4a9eff', fontSize: 8, fontWeight: 'bold', marginBottom: 1 }}>组{g.group}</div>
              {g.teams.map(t => (
                <div key={t.team} style={{ display: 'flex', alignItems: 'center', gap: 2, fontSize: 9, padding: '1px 0' }}>
                  <span style={{ color: t.rank === 1 ? '#4a9eff' : 'rgba(255,255,255,0.5)', fontWeight: t.rank === 1 ? 'bold' : 'normal' }}>
                    {FLAGS[t.team] || '🏳️'} {t.team}
                  </span>
                  <span style={{ color: 'rgba(255,255,255,0.3)', fontSize: 7, marginLeft: 'auto' }}>{t.pts || t.points}分</span>
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}


// Country flag emoji mapping
const FLAGS = {
  'Argentina': '🇦🇷', 'Australia': '🇦🇺', 'Belgium': '🇧🇪', 'Brazil': '🇧🇷',
  'Cameroon': '🇨🇲', 'Canada': '🇨🇦', 'Chile': '🇨🇱', 'China': '🇨🇳',
  'Colombia': '🇨🇴', 'Costa Rica': '🇨🇷', 'Croatia': '🇭🇷', 'Denmark': '🇩🇰',
  'Ecuador': '🇪🇨', 'Egypt': '🇪🇬', 'England': '🏴󠁧󠁢󠁥󠁮󠁧󠁿', 'France': '🇫🇷',
  'Germany': '🇩🇪', 'Ghana': '🇬🇭', 'Iran': '🇮🇷', 'Iraq': '🇮🇶',
  'Italy': '🇮🇹', 'Jamaica': '🇯🇲', 'Japan': '🇯🇵', 'Jordan': '🇯🇴',
  'Korea Republic': '🇰🇷', 'Korea': '🇰🇷', 'Mexico': '🇲🇽', 'Morocco': '🇲🇦',
  'Netherlands': '🇳🇱', 'New Zealand': '🇳🇿', 'Nigeria': '🇳🇬', 'Norway': '🇳🇴',
  'Panama': '🇵🇦', 'Paraguay': '🇵🇾', 'Peru': '🇵🇪', 'Poland': '🇵🇱',
  'Portugal': '🇵🇹', 'Qatar': '🇶🇦', 'Russia': '🇷🇺', 'Saudi Arabia': '🇸🇦',
  'Scotland': '🇸🇰', 'Senegal': '🇸🇳', 'Serbia': '🇷🇸', 'Slovakia': '🇸🇰',
  'Slovenia': '🇸🇮', 'South Africa': '🇿🇦', 'Spain': '🇪🇸', 'Sweden': '🇸🇪',
  'Switzerland': '🇨🇭', 'Tunisia': '🇹🇳', 'Turkey': '🇹🇷', 'Ukraine': '🇺🇦',
  'United States': '🇺🇸', 'USA': '🇺🇸', 'Uruguay': '🇺🇾', 'Wales': '🏴󠁧󠁢󠁷󠁬󠁳󠁿',
};

function MatchCard({ match, half }) {
  if (!match) return null;
  const isHomeWin = match.winner === match.home;
  const isAwayWin = match.winner === match.away;
  const isCenter = half === 'center';

  const bgBase = half === 'left' ? 'rgba(201,169,110,0.06)' : half === 'right' ? 'rgba(74,158,255,0.06)' : 'rgba(201,169,110,0.12)';
  const borderColor = half === 'left' ? 'rgba(201,169,110,0.25)' : half === 'right' ? 'rgba(74,158,255,0.25)' : '#c9a96e';
  const winColor = '#c9a96e';
  const flag = (name) => FLAGS[name] || '🏳️';

  return (
    <div style={{
      background: isCenter ? 'linear-gradient(135deg, rgba(201,169,110,0.15), rgba(201,169,110,0.05))' : bgBase,
      border: `1px solid ${borderColor}`,
      borderRadius: isCenter ? 6 : 3,
      padding: isCenter ? '6px 10px' : '3px 6px',
      fontSize: isCenter ? 12 : 10,
      minWidth: 0,
      boxShadow: isCenter ? '0 0 12px rgba(201,169,110,0.2)' : 'none'
    }}>
      <div style={{
        display: 'flex', alignItems: 'center', gap: 3,
        color: isHomeWin ? winColor : 'rgba(255,255,255,0.85)',
        fontWeight: isHomeWin ? 'bold' : 'normal',
        padding: '1px 0'
      }}>
        <span style={{ fontSize: isCenter ? 13 : 10 }}>{flag(match.home)}</span>
        <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{match.home}</span>
        {isHomeWin && <span style={{ color: winColor, fontSize: 9 }}>✓</span>}
      </div>
      <div style={{
        display: 'flex', alignItems: 'center', gap: 3,
        color: isAwayWin ? winColor : 'rgba(255,255,255,0.45)',
        fontWeight: isAwayWin ? 'bold' : 'normal',
        padding: '1px 0'
      }}>
        <span style={{ fontSize: isCenter ? 13 : 10 }}>{flag(match.away)}</span>
        <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{match.away}</span>
        {isAwayWin && <span style={{ color: winColor, fontSize: 9 }}>✓</span>}
      </div>
    </div>
  );
}


// ============================================================
// Knockout Bracket Component
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

const FORMATIONS = {
  '4-3-3': { GK: 1, DF: 4, MF: 3, FW: 3, label: '4-3-3' },
  '4-4-2': { GK: 1, DF: 4, MF: 4, FW: 2, label: '4-4-2' },
  '3-5-2': { GK: 1, DF: 3, MF: 5, FW: 2, label: '3-5-2' },
  '4-2-3-1': { GK: 1, DF: 4, MF: 3, FW: 1, extra: { CAM: 1, CDM: 2 }, label: '4-2-3-1' },
  '5-3-2': { GK: 1, DF: 5, MF: 3, FW: 2, label: '5-3-2' },
  '4-1-4-1': { GK: 1, DF: 4, MF: 5, FW: 1, extra: { CDM: 1 }, label: '4-1-4-1' },
};

function Simulate() {
  const [teams, setTeams] = useState([]);
  const [homeTeam, setHomeTeam] = useState('');
  const [awayTeam, setAwayTeam] = useState('');
  const [homeSquad, setHomeSquad] = useState(null);
  const [awaySquad, setAwaySquad] = useState(null);
  const [homeLineup, setHomeLineup] = useState([]);
  const [awayLineup, setAwayLineup] = useState([]);
  const [homeFormation, setHomeFormation] = useState('4-3-3');
  const [awayFormation, setAwayFormation] = useState('4-3-3');
  const [prediction, setPrediction] = useState(null);
  const [loading, setLoading] = useState(false);
  const [nSims, setNSims] = useState(1000);

  useEffect(() => {
    get('/worldcup/rankings').then(d => {
      if (d.rankings) setTeams(d.rankings.map(t => t.team));
    }).catch(() => {});
  }, []);

  // Auto-select XI when team or formation changes
  useEffect(() => {
    if (homeSquad) {
      const sorted = [...homeSquad.players].sort((a, b) => b.elo - a.elo);
      setHomeLineup(selectByFormation(sorted, homeFormation));
    }
  }, [homeTeam, homeFormation, homeSquad]);

  useEffect(() => {
    if (awaySquad) {
      const sorted = [...awaySquad.players].sort((a, b) => b.elo - a.elo);
      setAwayLineup(selectByFormation(sorted, awayFormation));
    }
  }, [awayTeam, awayFormation, awaySquad]);

  useEffect(() => {
    if (homeTeam) {
      get(`/worldcup/squad/${encodeURIComponent(homeTeam)}`).then(d => {
        if (d.status === 'ok') setHomeSquad(d);
      }).catch(() => {});
    }
  }, [homeTeam]);

  useEffect(() => {
    if (awayTeam) {
      get(`/worldcup/squad/${encodeURIComponent(awayTeam)}`).then(d => {
        if (d.status === 'ok') setAwaySquad(d);
      }).catch(() => {});
    }
  }, [awayTeam]);

  function selectByFormation(players, formationKey) {
    const form = FORMATIONS[formationKey] || FORMATIONS['4-3-3'];
    const need = { GK: form.GK || 0, DF: form.DF || 0, MF: form.MF || 0, FW: form.FW || 0 };
    const xi = [];
    for (const p of players) {
      const cat = p.pos_category || 'MF';
      if ((need[cat] || 0) > 0) { xi.push(p.player_id); need[cat]--; }
      if (xi.length >= 11) break;
    }
    // Fill remaining if needed
    if (xi.length < 11) {
      for (const p of players) {
        if (!xi.includes(p.player_id)) { xi.push(p.player_id); if (xi.length >= 11) break; }
      }
    }
    return xi.slice(0, 11); // Strict 11 limit
  }

  function togglePlayer(team, playerId) {
    const lineup = team === 'home' ? [...homeLineup] : [...awayLineup];
    const idx = lineup.indexOf(playerId);
    if (idx >= 0) {
      lineup.splice(idx, 1);
    } else {
      if (lineup.length >= 11) return; // Strict 11 limit - can't add more
      lineup.push(playerId);
    }
    if (team === 'home') setHomeLineup(lineup);
    else setAwayLineup(lineup);
  }

  async function runPredict() {
    if (!homeTeam || !awayTeam) return;
    if (homeLineup.length !== 11 || awayLineup.length !== 11) return;
    setLoading(true);
    setPrediction(null);
    try {
      const d = await post('/worldcup/predict', {
        home_team: homeTeam, away_team: awayTeam,
        home_lineup: homeLineup, away_lineup: awayLineup,
        n_sims: nSims,
      });
      setPrediction(d);
    } catch (err) {
      setPrediction({ status: 'error', message: err.message });
    }
    setLoading(false);
  }

  const homeXI = homeLineup.length;
  const awayXI = awayLineup.length;
  const canPredict = homeTeam && awayTeam && homeXI === 11 && awayXI === 11;

  return (
    <div>
      <h2 style={{ color: 'var(--fg-primary)', fontSize: 16, marginBottom: 12 }}>⚔️ 世界杯沙盘模拟</h2>

      {/* Team + Formation Selection */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr auto 1fr', gap: 12, marginBottom: 12, alignItems: 'start' }}>
        {/* Home */}
        <div>
          <select value={homeTeam} onChange={e => setHomeTeam(e.target.value)}
            style={{ width: '100%', background: 'var(--bg-input)', color: 'var(--fg-primary)', border: '1px solid var(--border)', borderRadius: 6, padding: '8px 12px', fontSize: 14, marginBottom: 6 }}>
            <option value="">选择主队</option>
            {teams.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
          <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
            {Object.keys(FORMATIONS).map(f => (
              <button key={f} onClick={() => setHomeFormation(f)}
                style={{
                  background: homeFormation === f ? 'var(--accent)' : 'var(--bg-input)',
                  color: homeFormation === f ? '#fff' : 'var(--fg-muted)',
                  border: 'none', padding: '3px 8px', borderRadius: 4, cursor: 'pointer', fontSize: 10
                }}>{f}</button>
            ))}
          </div>
          <div style={{ color: homeXI === 11 ? 'var(--green)' : 'var(--red)', fontSize: 11, marginTop: 4 }}>
            首发 {homeXI}/11 {homeXI !== 11 ? '— 请选择11人' : '✓'}
          </div>
        </div>
        {/* VS */}
        <div style={{ paddingTop: 8, textAlign: 'center' }}>
          <div style={{ color: 'var(--fg-muted)', fontSize: 18, fontWeight: 'bold' }}>VS</div>
          <div style={{ color: 'var(--fg-muted)', fontSize: 10, marginTop: 4 }}>阵型</div>
        </div>
        {/* Away */}
        <div>
          <select value={awayTeam} onChange={e => setAwayTeam(e.target.value)}
            style={{ width: '100%', background: 'var(--bg-input)', color: 'var(--fg-primary)', border: '1px solid var(--border)', borderRadius: 6, padding: '8px 12px', fontSize: 14, marginBottom: 6 }}>
            <option value="">选择客队</option>
            {teams.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
          <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
            {Object.keys(FORMATIONS).map(f => (
              <button key={f} onClick={() => setAwayFormation(f)}
                style={{
                  background: awayFormation === f ? 'var(--accent)' : 'var(--bg-input)',
                  color: awayFormation === f ? '#fff' : 'var(--fg-muted)',
                  border: 'none', padding: '3px 8px', borderRadius: 4, cursor: 'pointer', fontSize: 10
                }}>{f}</button>
            ))}
          </div>
          <div style={{ color: awayXI === 11 ? 'var(--green)' : 'var(--red)', fontSize: 11, marginTop: 4 }}>
            首发 {awayXI}/11 {awayXI !== 11 ? '— 请选择11人' : '✓'}
          </div>
        </div>
      </div>

      {/* Simulation Controls */}
      {homeTeam && awayTeam && (
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 12, padding: '8px 12px', background: 'var(--bg-card)', borderRadius: 6 }}>
          <span style={{ color: 'var(--fg-muted)', fontSize: 12 }}>模拟次数:</span>
          <input type="range" min={100} max={5000} step={100} value={nSims}
            onChange={e => setNSims(Number(e.target.value))}
            style={{ flex: 1, accentColor: 'var(--accent)' }} />
          <span style={{ color: 'var(--accent)', fontSize: 13, fontWeight: 'bold', minWidth: 50 }}>{nSims}</span>
          <button onClick={runPredict} disabled={loading || !canPredict}
            style={{ background: !canPredict ? 'var(--bg-input)' : loading ? 'var(--bg-input)' : 'var(--green)', color: '#fff', border: 'none', padding: '8px 20px', borderRadius: 6, cursor: canPredict ? 'pointer' : 'not-allowed', fontSize: 13, fontWeight: 'bold' }}>
            {!canPredict ? '请选择11人' : loading ? '预测中...' : '开始预测'}
          </button>
        </div>
      )}

      {/* Prediction Results */}
      {prediction && prediction.status === 'ok' && <PredictionResult pred={prediction} homeTeam={homeTeam} awayTeam={awayTeam} />}

      {/* Squad Display */}
      {homeSquad && awaySquad && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginTop: 12 }}>
          <SandboxSquad squad={homeSquad} lineup={homeLineup} onToggle={id => togglePlayer('home', id)} label={homeTeam} formation={homeFormation} />
          <SandboxSquad squad={awaySquad} lineup={awayLineup} onToggle={id => togglePlayer('away', id)} label={awayTeam} formation={awayFormation} />
        </div>
      )}
    </div>
  );
}


function PredictionResult({ pred, homeTeam, awayTeam }) {
  const [tab, setTab] = useState('wdl');
  const tabs = [
    { key: 'wdl', label: '胜负' },
    { key: 'scorers', label: '进球球员' },
    { key: 'scores', label: '比分' },
    { key: 'factors', label: '关键因素' },
  ];

  return (
    <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8, padding: 12, marginBottom: 12 }}>
      {/* WDL Header */}
      <div style={{ display: 'flex', justifyContent: 'space-around', alignItems: 'center', marginBottom: 12 }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ color: 'var(--fg-primary)', fontSize: 14, fontWeight: 'bold' }}>{homeTeam}</div>
          <div style={{ color: 'var(--fg-muted)', fontSize: 11 }}>XI {pred.home_xi} {pred.home_chemistry > 0 ? `· 组织+${pred.home_chemistry}%` : ''} {pred.home_setpiece > 0 ? `· 定位球${pred.home_setpiece}%` : ''}</div>
          <div style={{ color: 'var(--green)', fontSize: 24, fontWeight: 'bold' }}>{(pred.wdl.home_win * 100).toFixed(1)}%</div>
        </div>
        <div style={{ textAlign: 'center' }}>
          <div style={{ color: 'var(--fg-muted)', fontSize: 11 }}>平局</div>
          <div style={{ color: 'var(--yellow)', fontSize: 18 }}>{(pred.wdl.draw * 100).toFixed(1)}%</div>
          <div style={{ color: 'var(--fg-muted)', fontSize: 10, marginTop: 4 }}>xG {pred.expected_goals.home} - {pred.expected_goals.away}</div>
        </div>
        <div style={{ textAlign: 'center' }}>
          <div style={{ color: 'var(--fg-primary)', fontSize: 14, fontWeight: 'bold' }}>{awayTeam}</div>
          <div style={{ color: 'var(--fg-muted)', fontSize: 11 }}>XI {pred.away_xi} {pred.away_chemistry > 0 ? `· 组织+${pred.away_chemistry}%` : ''} {pred.away_setpiece > 0 ? `· 定位球${pred.away_setpiece}%` : ''}</div>
          <div style={{ color: 'var(--green)', fontSize: 24, fontWeight: 'bold' }}>{(pred.wdl.away_win * 100).toFixed(1)}%</div>
        </div>
      </div>

      {/* Key Factors - always visible */}
      {pred.key_factors?.length > 0 && (
        <div style={{ marginBottom: 10 }}>
          {pred.key_factors.map((f, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '3px 0', fontSize: 11 }}>
              <span style={{
                background: f.impact === 'high' ? 'var(--red)' : f.impact === 'medium' ? 'var(--yellow)' : 'var(--bg-input)',
                color: f.impact === 'low' ? 'var(--fg-muted)' : '#fff',
                padding: '1px 5px', borderRadius: 3, fontSize: 9, fontWeight: 'bold'
              }}>{f.impact === 'high' ? 'HIGH' : f.impact === 'medium' ? 'MED' : 'LOW'}</span>
              <span style={{ color: 'var(--fg-primary)', fontWeight: 'bold' }}>{f.factor}</span>
              <span style={{ color: 'var(--fg-body)', flex: 1 }}>{f.description}</span>
              <span style={{ color: f.direction === 'home' ? 'var(--green)' : 'var(--accent)', fontSize: 10 }}>
                {f.direction === 'home' ? '→主' : '←客'}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 10 }}>
        {tabs.map(t => (
          <button key={t.key} onClick={() => setTab(t.key)}
            style={{
              background: tab === t.key ? 'var(--accent)' : 'var(--bg-input)',
              color: tab === t.key ? '#fff' : 'var(--fg-muted)',
              border: 'none', padding: '4px 10px', borderRadius: 4, cursor: 'pointer', fontSize: 11
            }}>{t.label}</button>
        ))}
      </div>

      {/* Tab Content */}
      {tab === 'wdl' && (
        <div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, textAlign: 'center' }}>
            <div><div style={{ color: 'var(--fg-muted)', fontSize: 10 }}>大1.5</div><div style={{ color: 'var(--green)', fontSize: 14 }}>{((pred.over_under?.over_1_5 || 0) * 100).toFixed(0)}%</div></div>
            <div><div style={{ color: 'var(--fg-muted)', fontSize: 10 }}>大2.5</div><div style={{ color: 'var(--accent)', fontSize: 14 }}>{((pred.over_under?.over_2_5 || 0) * 100).toFixed(0)}%</div></div>
            <div><div style={{ color: 'var(--fg-muted)', fontSize: 10 }}>双方进球</div><div style={{ color: 'var(--yellow)', fontSize: 14 }}>{((pred.over_under?.btts || 0) * 100).toFixed(0)}%</div></div>
          </div>
        </div>
      )}

      {tab === 'scorers' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
          <div>
            <div style={{ color: 'var(--fg-muted)', fontSize: 10, marginBottom: 4 }}>{homeTeam} 进球球员</div>
            {(pred.goal_scorers?.home || []).map((s, i) => (
              <div key={i} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, padding: '2px 0' }}>
                <span style={{ color: 'var(--fg-body)' }}>{s.name}</span>
                <span style={{ color: 'var(--green)' }}>{(s.prob_anytime * 100).toFixed(0)}%</span>
              </div>
            ))}
          </div>
          <div>
            <div style={{ color: 'var(--fg-muted)', fontSize: 10, marginBottom: 4 }}>{awayTeam} 进球球员</div>
            {(pred.goal_scorers?.away || []).map((s, i) => (
              <div key={i} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, padding: '2px 0' }}>
                <span style={{ color: 'var(--fg-body)' }}>{s.name}</span>
                <span style={{ color: 'var(--green)' }}>{(s.prob_anytime * 100).toFixed(0)}%</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {tab === 'scores' && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 4 }}>
          {(pred.score_distribution || []).map((s, i) => (
            <div key={i} style={{ textAlign: 'center', padding: '4px', background: i === 0 ? 'rgba(63,185,80,0.1)' : 'transparent', borderRadius: 4 }}>
              <div style={{ color: i === 0 ? 'var(--green)' : 'var(--fg-body)', fontSize: 13, fontWeight: i === 0 ? 'bold' : 'normal' }}>{s.score}</div>
              <div style={{ color: 'var(--fg-muted)', fontSize: 10 }}>{(s.prob * 100).toFixed(1)}%</div>
            </div>
          ))}
        </div>
      )}

      {tab === 'factors' && (
        <div>
          {(pred.key_factors || []).length === 0 && <div style={{ color: 'var(--fg-muted)', fontSize: 12 }}>双方实力接近，无明显关键因素</div>}
          {(pred.key_factors || []).map((f, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '4px 0', borderBottom: '1px solid var(--border)' }}>
              <span style={{
                background: f.impact === 'high' ? 'var(--red)' : f.impact === 'medium' ? 'var(--yellow)' : 'var(--bg-input)',
                color: f.impact === 'low' ? 'var(--fg-muted)' : '#fff',
                padding: '1px 6px', borderRadius: 3, fontSize: 9, fontWeight: 'bold'
              }}>{f.impact.toUpperCase()}</span>
              <span style={{ color: 'var(--fg-primary)', fontSize: 12, fontWeight: 'bold', minWidth: 70 }}>{f.factor}</span>
              <span style={{ color: 'var(--fg-body)', fontSize: 11, flex: 1 }}>{f.description}</span>
              <span style={{ color: f.direction === 'home' ? 'var(--green)' : 'var(--accent)', fontSize: 10 }}>{f.direction === 'home' ? '→主' : '←客'}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}


function SandboxSquad({ squad, lineup, onToggle, label, formation }) {
  const analysis = squad.analysis || {};
  const players = squad.players || [];
  const lineupSet = new Set(lineup);

  // Group by position category
  const grouped = { GK: [], DF: [], MF: [], FW: [] };
  for (const p of players) {
    const cat = ['GK','DF','MF','FW'].includes(p.pos_category) ? p.pos_category : 'MF';
    grouped[cat].push(p);
  }

  const posLabels = { GK: '门将', DF: '后卫', MF: '中场', FW: '前锋' };

  return (
    <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8, padding: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <span style={{ color: 'var(--fg-primary)', fontWeight: 'bold', fontSize: 14 }}>{label} ({formation || '4-3-3'})</span>
        <span style={{ color: 'var(--fg-muted)', fontSize: 11 }}>
          XI评分 {analysis.starting_xi?.toFixed(0) || '-'} | 年龄 {analysis.avg_age?.toFixed(1) || '-'}
        </span>
      </div>
      <div style={{ color: 'var(--fg-muted)', fontSize: 10, marginBottom: 8 }}>
        已选 {lineup.length}/11 人，点击球员切换
      </div>
      {/* Column headers */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 4, padding: '2px 6px', fontSize: 9, color: 'var(--fg-muted)', borderBottom: '1px solid var(--border)', marginBottom: 4 }}>
        <span style={{ width: 12 }}></span>
        <span style={{ minWidth: 100 }}>球员</span>
        <span style={{ width: 42, textAlign: 'center' }}>角色</span>
        <span style={{ width: 45 }}>俱乐部</span>
        <span style={{ width: 28, textAlign: 'right' }}>ELO</span>
        <span style={{ width: 24, textAlign: 'right', color: '#e74c3c' }}>攻击</span>
        <span style={{ width: 24, textAlign: 'right', color: '#3498db' }}>防守</span>
        <span style={{ width: 24, textAlign: 'right', color: '#f39c12' }}>进球</span>
        <span style={{ width: 24, textAlign: 'right' }}>G/90</span>
      </div>
      {['GK', 'DF', 'MF', 'FW'].map(cat => (
        <div key={cat} style={{ marginBottom: 6 }}>
          <div style={{ color: 'var(--fg-muted)', fontSize: 10, marginBottom: 2, borderBottom: '1px solid var(--border)', paddingBottom: 2 }}>
            {posLabels[cat]} ({grouped[cat].length})
          </div>
          {grouped[cat].map(p => {
            const selected = lineupSet.has(p.player_id);
            return (
              <div key={p.player_id || p.name} onClick={() => onToggle(p.player_id)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 4, padding: '3px 6px', cursor: 'pointer',
                  background: selected ? 'rgba(63,185,80,0.1)' : 'transparent',
                  border: selected ? '1px solid rgba(63,185,80,0.3)' : '1px solid transparent',
                  borderRadius: 4, fontSize: 11, transition: 'all 0.1s'
                }}>
                <span style={{ width: 12, textAlign: 'center', color: selected ? 'var(--green)' : 'var(--fg-muted)' }}>
                  {selected ? '✓' : ''}
                </span>
                <span style={{ color: selected ? 'var(--green)' : 'var(--fg-body)', fontWeight: selected ? 'bold' : 'normal', minWidth: 100 }}>
                  {p.jersey_number ? `#${p.jersey_number} ` : ''}{p.name}
                </span>
                <span style={{ color: 'var(--yellow)', fontSize: 9, width: 42, textAlign: 'center', background: 'rgba(243,156,18,0.1)', borderRadius: 3, padding: '0 2px' }} title={p.role}>{p.role_cn || '-'}</span>
                <span style={{ color: 'var(--fg-muted)', fontSize: 9, width: 45 }}>{p.club?.slice(0,8) || '-'}</span>
                {/* Detailed stats */}
                <span style={{ color: 'var(--accent)', fontSize: 10, width: 28, textAlign: 'right' }} title="综合ELO">{p.elo > 0 ? p.elo.toFixed(0) : '-'}</span>
                <span style={{ color: '#e74c3c', fontSize: 9, width: 24, textAlign: 'right' }} title="攻击">{p.attack_rating?.toFixed(0) || '-'}</span>
                <span style={{ color: '#3498db', fontSize: 9, width: 24, textAlign: 'right' }} title="防守">{p.defense_rating?.toFixed(0) || '-'}</span>
                <span style={{ color: '#f39c12', fontSize: 9, width: 24, textAlign: 'right' }} title="进球期望">{p.goal_expectation > 0 ? p.goal_expectation.toFixed(2) : '-'}</span>
                <span style={{ color: 'var(--fg-muted)', fontSize: 9, width: 24, textAlign: 'right' }} title="场均进球">{p.goals_per_90 > 0 ? p.goals_per_90.toFixed(2) : '-'}</span>
              </div>
            );
          })}
        </div>
      ))}
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
