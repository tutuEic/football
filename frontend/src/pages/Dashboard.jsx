import { useState, useEffect } from 'react';
import { get } from '../api';

const MAP = {E0:'英超',SP1:'西甲',D1:'德甲',I1:'意甲',F1:'法甲',N1:'荷甲',P1:'葡超',B1:'比甲',T1:'土超',G1:'希腊超',SC0:'苏超',USA:'MLS',JPN:'J联赛',BRA:'巴甲',ARG:'阿甲',MEX:'墨超',CHN:'中超',AUT:'奥甲',SWE:'瑞典超',NOR:'挪超',DEN:'丹超',FIN:'芬超',POL:'波甲',ROU:'罗甲',RUS:'俄超',IRL:'爱超',E1:'英冠',E2:'英甲',E3:'英乙',SP2:'西乙',D2:'德乙',I2:'意乙',F2:'法乙',SC1:'苏冠'};

export default function Dashboard() {
  const [leagues, setLeagues] = useState([]);
  const [standings, setStandings] = useState(null);
  const [league, setLeague] = useState('E0');
  const [modelCount, setModelCount] = useState(0);

  useEffect(() => {
    get('/matches/leagues').then(d => setLeagues(d.leagues || [])).catch(() => {});
    get('/models').then(d => setModelCount(d.length || 0)).catch(() => {});
  }, []);

  async function loadStandings(lg) {
    setLeague(lg);
    try { const d = await get('/matches/standings', { league: lg }); setStandings(d); }
    catch { setStandings(null); }
  }

  useEffect(() => { loadStandings('E0'); }, []);

  return (
    <div>
      <h2 style={{ color: 'var(--fg-primary)', fontSize: 18, marginBottom: 20 }}>{'📊'} 仪表盘</h2>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 12, marginBottom: 20 }}>
        <StatCard label="数据库比赛" value="578K" sub="场" color="var(--accent)" />
        <StatCard label="覆盖联赛" value={leagues.length || 33} sub="个" color="var(--green)" />
        <StatCard label="球员数据" value="4.7万" sub="Transfermarkt" color="var(--purple)" />
        <StatCard label="已训练模型" value={modelCount || 35} sub="DC Dixon-Coles" color="var(--green)" />
      </div>

      {/* 联赛选择 — 动态 */}
      <div style={{ display: 'flex', gap: 6, marginBottom: 16, flexWrap: 'wrap' }}>
        {leagues.map(lc => (
          <button key={lc} onClick={() => loadStandings(lc)}
            style={{ ...tabBtn, background: league === lc ? 'var(--accent)' : 'var(--bg-input)',
              color: league === lc ? '#fff' : 'var(--fg-muted)' }}>
            {MAP[lc] || lc}
          </button>
        ))}
      </div>

      {/* 积分榜 */}
      {standings?.standings && (
        <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8, overflow: 'hidden' }}>
          <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border)', color: 'var(--fg-muted)', fontSize: 13 }}>
            {'📋'} {standings.league} 积分榜 · {standings.season} 赛季
          </div>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ color: 'var(--fg-muted)', borderBottom: '1px solid var(--border)' }}>
                <th style={th}>#</th><th style={{...th,textAlign:'left'}}>球队</th>
                <th style={th}>赛</th><th style={th}>胜</th><th style={th}>平</th><th style={th}>负</th>
                <th style={th}>进球</th><th style={th}>净胜</th><th style={th}>积分</th>
              </tr>
            </thead>
            <tbody>
              {standings.standings.slice(0, 20).map((t, i) => (
                <tr key={t.team} style={{ borderBottom: '1px solid var(--border)', color: 'var(--fg-body)' }}>
                  <td style={{...td,color:'var(--fg-muted)'}}>{t.pos}</td>
                  <td style={{...td,fontWeight:i<4?'bold':'normal',textAlign:'left'}}>{t.team}</td>
                  <td style={td}>{t.P}</td>
                  <td style={{...td,color:'var(--green)'}}>{t.W}</td>
                  <td style={{...td,color:'var(--yellow)'}}>{t.D}</td>
                  <td style={{...td,color:'var(--red)'}}>{t.L}</td>
                  <td style={td}>{t.GF}-{t.GA}</td>
                  <td style={{...td,color:t.GD>0?'var(--green)':'var(--red)'}}>{t.GD>0?'+':''}{t.GD}</td>
                  <td style={{...td,fontWeight:'bold'}}>{t.Pts}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function StatCard({ label, value, sub, color }) {
  return (
    <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8, padding: 16 }}>
      <div style={{ color: 'var(--fg-muted)', fontSize: 12, marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 26, fontWeight: 'bold', color }}>{value}</div>
      <div style={{ color: 'var(--fg-muted)', fontSize: 11, marginTop: 2 }}>{sub}</div>
    </div>
  );
}

const th = { padding: '6px 10px', textAlign: 'center', color: 'var(--fg-muted)' };
const td = { padding: '5px 10px', textAlign: 'center', fontSize: 12 };
const tabBtn = { border: 'none', borderRadius: 6, padding: '5px 10px', fontSize: 12, cursor: 'pointer' };
