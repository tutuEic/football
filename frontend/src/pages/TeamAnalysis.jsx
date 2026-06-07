import { useState, useEffect } from 'react';
import { get } from '../api';
import { TeamSearch } from '../components/SearchDropdown';

export default function TeamAnalysis() {
  const [league, setLeague] = useState('E0');
  const [leagues, setLeagues] = useState([]);
  const [team, setTeam] = useState('');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    get('/matches/leagues').then(d => {
      const all = (d.leagues || []).map(c => ({ code: c, name: MAP[c] || c }));
      setLeagues(all);
    }).catch(() => {});
  }, []);

  async function analyze(name) {
    if (!name) return;
    setTeam(name);
    setLoading(true);
    try {
      const [stats, form] = await Promise.all([
        get(`/teams/${name}/stats`, { league }),
        get('/matches/recent', { team: name, league }),
      ]);
      setData({ stats, form });
    } catch (e) { setData({ error: e.message }); }
    setLoading(false);
  }

  return (
    <div style={{ maxWidth: 900, margin: '0 auto' }}>
      <h2 style={{ color: 'var(--fg-primary)', fontSize: 18, marginBottom: 20 }}>{'📈'} 球队分析</h2>

      <div style={{ display: 'flex', gap: 8, marginBottom: 24 }}>
        <select value={league} onChange={e => { setLeague(e.target.value); setTeam(''); setData(null); }}
          style={selectStyle}>
          {leagues.map(l => <option key={l.code} value={l.code}>{l.name}</option>)}
        </select>
        <TeamSearch value={team} onChange={setTeam} onSelect={analyze} league={league}
          placeholder="输入球队名搜索..." style={{ flex: 1 }} />
        <button onClick={() => analyze(team)} disabled={loading || !team}
          style={{ padding: '8px 20px', background: 'var(--accent)', border: 'none', borderRadius: 6, color: '#fff' }}>
          分析
        </button>
      </div>

      {data?.stats && (
        <div style={{ display: 'grid', gap: 16 }}>
          <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8, padding: 20 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 16 }}>
              <h3 style={{ color: 'var(--fg-primary)', fontSize: 20 }}>{data.stats.team}</h3>
              {data.stats.tm_club_name && <span style={{ color: 'var(--fg-muted)', fontSize: 13 }}>{data.stats.tm_club_name}</span>}
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: 12 }}>
              {data.stats.attack != null && <Stat label="进攻强度" value={data.stats.attack} color="var(--green)" />}
              {data.stats.defence != null && <Stat label="防守强度" value={data.stats.defence} color="var(--red)" />}
              {data.stats.total_market_value != null && <Stat label="总身价" value={`€${(data.stats.total_market_value / 1e6).toFixed(0)}M`} color="var(--accent)" />}
              {data.stats.squad_size != null && <Stat label="阵容人数" value={data.stats.squad_size} color="var(--fg-body)" />}
              {data.stats.coach && <Stat label="主教练" value={data.stats.coach} color="var(--purple)" />}
              {data.stats.stadium && <Stat label="球场" value={data.stats.stadium} color="var(--fg-muted)" />}
            </div>
          </div>

          {data.form?.recent && (
            <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8, padding: 16 }}>
              <div style={{ color: 'var(--fg-muted)', fontSize: 13, marginBottom: 8 }}>{'📅'} 近期战绩 · {data.form.summary}</div>
              <div style={{ display: 'flex', gap: 4 }}>
                {data.form.recent.slice(0, 10).reverse().map((r, i) => (
                  <div key={i} style={{
                    width: 34, height: 34, borderRadius: 6, display: 'flex', alignItems: 'center', justifyContent: 'center',
                    background: r.outcome === 'W' ? 'var(--green)' : r.outcome === 'D' ? 'var(--yellow)' : 'var(--red)',
                    color: '#fff', fontSize: 12, fontWeight: 'bold', flexDirection: 'column'
                  }} title={`${r.opponent} ${r.score}`}>
                    <span>{r.outcome}</span><span style={{ fontSize: 8 }}>{r.score}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {data.stats.squad?.length > 0 && (
            <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8, padding: 16 }}>
              <div style={{ color: 'var(--fg-muted)', fontSize: 13, marginBottom: 12 }}>{'👥'} 球员阵容 ({data.stats.squad.length}人)</div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 8 }}>
                {data.stats.squad.map((p, i) => (
                  <div key={i} style={{ background: 'var(--bg-input)', borderRadius: 6, padding: '8px 12px', display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{
                      width: 32, height: 32, borderRadius: '50%',
                      background: p.overall > 85 ? 'var(--green)' : p.overall > 75 ? 'var(--accent)' : 'var(--bg-hover)',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      color: '#fff', fontSize: 12, fontWeight: 'bold', flexShrink: 0
                    }}>{p.overall}</span>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ color: 'var(--fg-body)', fontSize: 13, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{p.name}</div>
                      <div style={{ color: 'var(--fg-muted)', fontSize: 11 }}>{p.position} · 攻{p.attack_rating} 守{p.defense_rating}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
      {data?.error && <div style={{ color: 'var(--red)', textAlign: 'center', padding: 40 }}>⚠️ {data.error}</div>}
    </div>
  );
}

function Stat({ label, value, color }) {
  return (
    <div style={{ textAlign: 'center' }}>
      <div style={{ color: 'var(--fg-muted)', fontSize: 11, marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 18, fontWeight: 'bold', color }}>{typeof value === 'number' ? value.toFixed(2) : value}</div>
    </div>
  );
}

const selectStyle = { background: 'var(--bg-input)', color: 'var(--fg-body)', border: '1px solid var(--border)', borderRadius: 6, padding: '8px 12px', fontSize: 14 };

const MAP = {E0:'英超',SP1:'西甲',D1:'德甲',I1:'意甲',F1:'法甲',N1:'荷甲',P1:'葡超',B1:'比甲',T1:'土超',G1:'希腊超',SC0:'苏超',USA:'MLS',JPN:'J联赛',BRA:'巴甲',ARG:'阿甲',MEX:'墨超',CHN:'中超',AUT:'奥甲',SWE:'瑞典超',NOR:'挪超',DEN:'丹超',FIN:'芬超',POL:'波甲',ROU:'罗甲',RUS:'俄超',IRL:'爱超',E1:'英冠',E2:'英甲',E3:'英乙',SP2:'西乙',D2:'德乙',I2:'意乙',F2:'法乙',SC1:'苏冠'};
