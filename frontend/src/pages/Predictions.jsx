import { useState, useEffect } from 'react';
import { post, get } from '../api';
import { TeamSearch } from '../components/SearchDropdown';

const SIM_OPTIONS = [1000, 2000, 5000];

const LEAGUE_MAP = {
  E0:'英超',E1:'英冠',E2:'英甲',E3:'英乙',SP1:'西甲',SP2:'西乙',D1:'德甲',D2:'德乙',
  I1:'意甲',I2:'意乙',F1:'法甲',F2:'法乙',N1:'荷甲',B1:'比甲',P1:'葡超',T1:'土超',
  G1:'希腊超',SC0:'苏超',SC1:'苏冠',USA:'MLS',JPN:'J联赛',BRA:'巴甲',ARG:'阿甲',
  MEX:'墨超',CHN:'中超',AUT:'奥甲',SWE:'瑞典超',NOR:'挪超',DEN:'丹超',FIN:'芬超',
  POL:'波甲',ROU:'罗甲',RUS:'俄超',IRL:'爱超',
};

export default function Predictions() {
  const [home, setHome] = useState('');
  const [away, setAway] = useState('');
  const [league, setLeague] = useState('E0');
  const [leagues, setLeagues] = useState([]);
  const [ensembleLeagues, setEnsembleLeagues] = useState({});
  const [sims, setSims] = useState(2000);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    get('/matches/leagues').then(d => {
      const all = (d.leagues || []).map(c => ({ code: c, name: LEAGUE_MAP[c] || c }));
      all.sort((a, b) => a.name.localeCompare(b.name, 'zh'));
      setLeagues(all);
    }).catch(() => {});
    get('/models/ensemble').then(d => {
      setEnsembleLeagues(d.leagues || {});
    }).catch(() => {});
  }, []);

  async function handlePredict() {
    if (!home || !away) return;
    setLoading(true);
    try {
      const r = await post('/predict/full?simulations=' + sims, { home_team: home, away_team: away, league });
      setResult(r);
    } catch (err) { setResult({ status: 'error', message: err.message }); }
    setLoading(false);
  }

  const hasEnsemble = ensembleLeagues[league];

  return (
    <div style={{ maxWidth: 960, margin: '0 auto' }}>
      <h2 style={{ color: 'var(--fg-primary)', fontSize: 18, marginBottom: 20 }}>{'比赛预测'}</h2>

      <div style={{ display: 'flex', gap: 8, marginBottom: 24, alignItems: 'center', flexWrap: 'wrap' }}>
        <div style={{ position: 'relative' }}>
          <select value={league} onChange={e => setLeague(e.target.value)} style={selectStyle}>
            {leagues.map(l => (
              <option key={l.code} value={l.code}>
                {l.name}{ensembleLeagues[l.code] ? ' ★' : ''}
              </option>
            ))}
          </select>
          {hasEnsemble && (
            <span style={{
              position: 'absolute', top: -6, right: -6, background: 'var(--green)',
              color: '#fff', fontSize: 9, padding: '1px 4px', borderRadius: 4, fontWeight: 'bold'
            }}>ML</span>
          )}
        </div>
        <TeamSearch value={home} onChange={setHome} onSelect={setHome} league={league} placeholder={'主队'} style={{ flex: 1, minWidth: 160 }} />
        <span style={{ color: 'var(--fg-muted)', fontWeight: 'bold' }}>vs</span>
        <TeamSearch value={away} onChange={setAway} onSelect={setAway} league={league} placeholder={'客队'} style={{ flex: 1, minWidth: 160 }} />
        {SIM_OPTIONS.map(n => (
          <button key={n} onClick={() => setSims(n)}
            style={{ ...chipBtn, background: sims === n ? 'var(--accent)' : 'var(--bg-input)', color: sims === n ? '#fff' : 'var(--fg-muted)' }}>
            {(n / 1000) + 'k'}
          </button>
        ))}
        <button onClick={handlePredict} disabled={loading || !home || !away}
          style={{ ...btnStyle, background: loading ? 'var(--bg-input)' : 'var(--green)' }}>
          {loading ? '分析中..' : '预测'}
        </button>
      </div>

      {result?.status === 'ok' && (
        <div style={{ display: 'grid', gap: 20 }}>
          <div style={{ textAlign: 'center' }}>
            <span style={{ color: 'var(--fg-primary)', fontSize: 20, fontWeight: 'bold' }}>{result.home_team}</span>
            <span style={{ color: 'var(--fg-muted)', margin: '0 16px', fontSize: 18 }}>vs</span>
            <span style={{ color: 'var(--fg-primary)', fontSize: 20, fontWeight: 'bold' }}>{result.away_team}</span>
          </div>

          <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 10, padding: 24 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
              <div style={{ color: 'var(--fg-muted)', fontSize: 12 }}>
                {'蒙特卡洛模拟'} {'·'} {result.simulations} {'次'}
              </div>
              <EnsembleBadge ensemble={result.ensemble} />
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 20, marginBottom: 20 }}>
              {[{ label: '主胜', val: (result.wdl || result.monte_carlo?.wdl)?.home_win || 0, color: 'var(--green)' },
                { label: '平局', val: (result.wdl || result.monte_carlo?.wdl)?.draw || 0, color: 'var(--yellow)' },
                { label: '客胜', val: (result.wdl || result.monte_carlo?.wdl)?.away_win || 0, color: 'var(--red)' }].map(item => (
                <div key={item.label} style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: 32, fontWeight: 'bold', color: item.color }}>{(item.val * 100).toFixed(1)}%</div>
                  <div style={{ color: 'var(--fg-muted)', fontSize: 13 }}>{item.label}</div>
                  <div style={{ marginTop: 8, height: 6, background: 'var(--bg-input)', borderRadius: 3, overflow: 'hidden' }}>
                    <div style={{ height: '100%', width: (item.val * 100) + '%', background: item.color, borderRadius: 3, transition: 'width 0.5s' }} />
                  </div>
                </div>
              ))}
            </div>

            <div style={{ display: 'flex', justifyContent: 'center', gap: 40, marginBottom: 20 }}>
              <div style={{ textAlign: 'center' }}>
                <div style={{ color: 'var(--fg-muted)', fontSize: 11 }}>{'平均进球'}</div>
                <span style={{ color: 'var(--green)', fontSize: 20, fontWeight: 'bold' }}>{result.avg_goals?.home || result.monte_carlo?.avg_goals?.home}</span>
                <span style={{ color: 'var(--fg-muted)', margin: '0 8px' }}>-</span>
                <span style={{ color: 'var(--red)', fontSize: 20, fontWeight: 'bold' }}>{result.avg_goals?.away || result.monte_carlo?.avg_goals?.away}</span>
              </div>
              <div style={{ textAlign: 'center' }}>
                <div style={{ color: 'var(--fg-muted)', fontSize: 11 }}>{'最可能比分'}</div>
                <div style={{ fontSize: 22, fontWeight: 'bold', color: 'var(--accent)' }}>{result.most_likely_score || result.monte_carlo?.most_likely_score}</div>
              </div>
              {result.over_under && (
                <div style={{ textAlign: 'center' }}>
                  <div style={{ color: 'var(--fg-muted)', fontSize: 11 }}>{'大小球 2.5'}</div>
                  <div style={{ display: 'flex', gap: 12 }}>
                    <span style={{ color: 'var(--green)', fontWeight: 'bold' }}>{'大'} {(result.over_under.over_2_5*100).toFixed(0)}%</span>
                    <span style={{ color: 'var(--red)', fontWeight: 'bold' }}>{'小'} {(result.over_under.under_2_5*100).toFixed(0)}%</span>
                  </div>
                </div>
              )}
            </div>

            <div>
              <div style={{ color: 'var(--fg-muted)', fontSize: 12, marginBottom: 8 }}>{'比分概率分布'}</div>
              <ScoreMatrix distribution={result.score_distribution || result.monte_carlo?.score_distribution || {}} />
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 16 }}>
            {result.key_players?.home?.length > 0 && (
              <KeyPlayersCard label={result.home_team + ' 关键球员'} players={result.key_players.home} />
            )}
            {result.factors?.length > 0 && <FactorsCard factors={result.factors} />}
            {result.key_players?.away?.length > 0 && (
              <KeyPlayersCard label={result.away_team + ' 关键球员'} players={result.key_players.away} away />
            )}
          </div>

          {result.odds_history && <OddsHistoryCard data={result.odds_history} />}

          {(result.injuries?.home?.injured?.length > 0 || result.injuries?.away?.injured?.length > 0) && (
            <InjuriesCard injuries={result.injuries} home={result.home_team} away={result.away_team} />
          )}
        </div>
      )}

      {result?.status === 'error' && (
        <div style={{ color: 'var(--red)', textAlign: 'center', padding: 40 }}>{result.message}</div>
      )}
    </div>
  );
}

function EnsembleBadge({ ensemble }) {
  if (!ensemble) return null;
  const method = ensemble.method || 'unknown';
  const labels = { stacking: 'Stacking集成', weighted_avg: '加权平均', fallback: '基础模型' };
  const colors = { stacking: 'var(--green)', weighted_avg: 'var(--accent)', fallback: 'var(--fg-muted)' };
  const models = ensemble.models_used || [];
  const modelLabels = { dc: 'Dixon-Coles', tw_dc: 'TW-DC', pr: 'Poisson回归', xgb: 'XGBoost' };

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <span style={{
        background: colors[method] || 'var(--fg-muted)',
        color: '#fff', fontSize: 10, padding: '2px 8px', borderRadius: 4, fontWeight: 'bold'
      }}>
        {labels[method] || method}
      </span>
      <span style={{ color: 'var(--fg-muted)', fontSize: 10 }}>
        {models.map(m => modelLabels[m] || m).join(' + ')}
      </span>
    </div>
  );
}

function ScoreMatrix({ distribution }) {
  const scores = Object.entries(distribution).slice(0, 25);
  const maxProb = Math.max(...scores.map(s => s[1]), 0.001);

  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
      {scores.map(([score, prob]) => {
        const intensity = prob / maxProb;
        return (
          <div key={score} title={score + ': ' + (prob * 100).toFixed(1) + '%'}
            style={{
              background: 'rgba(88, 166, 255, ' + (0.15 + intensity * 0.85) + ')',
              border: prob === maxProb ? '1px solid var(--accent)' : '1px solid transparent',
              borderRadius: 6, padding: '6px 12px', display: 'flex', gap: 10, alignItems: 'center',
              fontSize: 13, fontWeight: prob === maxProb ? 'bold' : 'normal',
              color: intensity > 0.5 ? '#fff' : 'var(--fg-body)',
            }}>
            <span>{score}</span>
            <span style={{ opacity: 0.8 }}>{(prob * 100).toFixed(1)}%</span>
          </div>
        );
      })}
    </div>
  );
}

function KeyPlayersCard({ label, players, away }) {
  return (
    <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8, padding: 16 }}>
      <div style={{ color: 'var(--fg-muted)', fontSize: 13, marginBottom: 12 }}>{label}</div>
      {players.map((p, i) => (
        <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: i < players.length - 1 ? 10 : 0 }}>
          <span style={{
            width: 36, height: 36, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center',
            background: p.overall > 85 ? 'var(--green)' : p.overall > 75 ? 'var(--accent)' : 'var(--bg-hover)',
            color: '#fff', fontSize: 13, fontWeight: 'bold', flexShrink: 0
          }}>{p.overall}</span>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ color: 'var(--fg-body)', fontSize: 13, fontWeight: 'bold' }}>{p.name}</div>
            <div style={{ color: 'var(--fg-muted)', fontSize: 11 }}>
              {p.position} {'·'} {'攻'}{p.attack_rating} {'守'}{p.defense_rating}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

function FactorsCard({ factors }) {
  return (
    <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8, padding: 16 }}>
      <div style={{ color: 'var(--fg-muted)', fontSize: 13, marginBottom: 12 }}>{'影响因素'}</div>
      {factors.map((f, i) => (
        <div key={i} style={{ marginBottom: i < factors.length - 1 ? 10 : 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
            <span>{f.icon}</span>
            <span style={{ color: 'var(--fg-body)', fontSize: 13, fontWeight: 'bold' }}>{f.name}</span>
            <span style={{
              marginLeft: 'auto', padding: '2px 8px', borderRadius: 4, fontSize: 11,
              background: f.impact === 'positive' ? 'rgba(63,185,80,0.2)' : f.impact === 'negative' ? 'rgba(248,81,73,0.2)' : 'var(--bg-input)',
              color: f.impact === 'positive' ? 'var(--green)' : f.impact === 'negative' ? 'var(--red)' : 'var(--fg-muted)',
            }}>{f.value}</span>
          </div>
          <div style={{ color: 'var(--fg-muted)', fontSize: 11, paddingLeft: 22 }}>{f.detail}</div>
        </div>
      ))}
    </div>
  );
}

const selectStyle = { background: 'var(--bg-input)', color: 'var(--fg-body)', border: '1px solid var(--border)', borderRadius: 6, padding: '8px 12px', fontSize: 14 };
const btnStyle = { padding: '8px 20px', border: 'none', borderRadius: 6, color: '#fff', fontSize: 14, fontWeight: 'bold' };
const chipBtn = { border: 'none', borderRadius: 6, padding: '6px 12px', fontSize: 12, cursor: 'pointer' };

function InjuriesCard({ injuries, home, away }) {
  return (
    <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 10, padding: 24 }}>
      <div style={{ color: 'var(--fg-muted)', fontSize: 12, marginBottom: 16 }}>{'伤病报告'}</div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 }}>
        {['home', 'away'].map(side => {
          const data = injuries[side];
          const team = side === 'home' ? home : away;
          if (!data?.injured?.length) return <div key={side} />;
          return (
            <div key={side}>
              <div style={{ color: 'var(--fg-body)', fontSize: 14, fontWeight: 'bold', marginBottom: 8 }}>
                {team}
                <span style={{ color: 'var(--red)', fontSize: 12, marginLeft: 8 }}>
                  {'战力'} {data.team_impact * 100}%
                </span>
              </div>
              {data.injured.map((p, i) => (
                <div key={i} style={{
                  display: 'flex', alignItems: 'center', gap: 8, padding: '6px 0',
                  borderBottom: i < data.injured.length - 1 ? '1px solid var(--border)' : 'none'
                }}>
                  <span style={{
                    width: 28, height: 28, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center',
                    background: 'var(--red)', color: '#fff', fontSize: 11, fontWeight: 'bold', flexShrink: 0
                  }}>{p.overall}</span>
                  <div style={{ flex: 1 }}>
                    <div style={{ color: 'var(--fg-body)', fontSize: 13 }}>{p.name}</div>
                    <div style={{ color: 'var(--fg-muted)', fontSize: 11 }}>
                      {p.position} {'·'} {'最近'}{p.recent_apps}/5{'场出场'}
                    </div>
                  </div>
                  <span style={{ color: 'var(--red)', fontSize: 11 }}>-{Math.round(p.impact * 100)}%</span>
                </div>
              ))}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function OddsHistoryCard({ data }) {
  const { current_odds, similar_count, outcomes, avg_goals, top_scores, threshold, sample_matches } = data;

  return (
    <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 10, padding: 24 }}>
      <div style={{ color: 'var(--fg-muted)', fontSize: 12, marginBottom: 16 }}>
        {'历史相似盘口'} {'·'} {'赔率'} {current_odds.home}/{current_odds.draw}/{current_odds.away} {'·'} {threshold} {'·'} {'匹配'} {similar_count} {'场'}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 24, marginBottom: 20 }}>
        <div>
          <div style={{ color: 'var(--fg-muted)', fontSize: 11, marginBottom: 8 }}>{'历史结果'}</div>
          <div style={{ display: 'flex', gap: 12 }}>
            {[
              { label: '主胜', val: outcomes.home_win, n: outcomes.home_count, color: 'var(--green)' },
              { label: '平局', val: outcomes.draw, n: outcomes.draw_count, color: 'var(--yellow)' },
              { label: '客胜', val: outcomes.away_win, n: outcomes.away_count, color: 'var(--red)' },
            ].map(item => (
              <div key={item.label} style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 22, fontWeight: 'bold', color: item.color }}>{(item.val * 100).toFixed(0)}%</div>
                <div style={{ color: 'var(--fg-muted)', fontSize: 11 }}>{item.label} {item.n}{'场'}</div>
              </div>
            ))}
          </div>
        </div>

        <div style={{ textAlign: 'center' }}>
          <div style={{ color: 'var(--fg-muted)', fontSize: 11, marginBottom: 8 }}>{'历史平均进球'}</div>
          <span style={{ color: 'var(--green)', fontSize: 22, fontWeight: 'bold' }}>{avg_goals.home}</span>
          <span style={{ color: 'var(--fg-muted)', margin: '0 8px' }}>-</span>
          <span style={{ color: 'var(--red)', fontSize: 22, fontWeight: 'bold' }}>{avg_goals.away}</span>
        </div>

        <div>
          <div style={{ color: 'var(--fg-muted)', fontSize: 11, marginBottom: 8 }}>{'历史常见比分'}</div>
          {top_scores.map((s, i) => (
            <div key={i} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, padding: '2px 0', color: i === 0 ? 'var(--accent)' : 'var(--fg-muted)' }}>
              <span style={{ fontWeight: i === 0 ? 'bold' : 'normal' }}>{s.score}</span>
              <span>{s.count}{'场'} ({(s.pct * 100).toFixed(0)}%)</span>
            </div>
          ))}
        </div>
      </div>

      {sample_matches?.length > 0 && (
        <div>
          <div style={{ color: 'var(--fg-muted)', fontSize: 11, marginBottom: 8 }}>{'相似比赛样本'}</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {sample_matches.map((m, i) => (
              <div key={i} style={{
                background: m.result === 'H' ? 'rgba(63,185,80,0.15)' : m.result === 'D' ? 'rgba(210,153,29,0.15)' : 'rgba(248,81,73,0.15)',
                borderRadius: 6, padding: '6px 10px', fontSize: 11
              }}>
                <div style={{ color: 'var(--fg-body)' }}>{m.home} {m.score} {m.away}</div>
                <div style={{ color: 'var(--fg-muted)' }}>{m.odds} {'·'} {m.date?.slice(0, 10)}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
