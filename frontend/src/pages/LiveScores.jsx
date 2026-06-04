import { useState, useEffect, useCallback } from 'react';
import { get, WS_BASE } from '../api';

const LEAGUES = [
  { code: '', name: '全部联赛' },
  { code: 'E0', name: '英超' }, { code: 'SP1', name: '西甲' }, { code: 'D1', name: '德甲' },
  { code: 'I1', name: '意甲' }, { code: 'F1', name: '法甲' }, { code: 'E1', name: '英冠' },
  { code: 'N1', name: '荷甲' }, { code: 'P1', name: '葡超' }, { code: 'B1', name: '比甲' },
  { code: 'T1', name: '土超' }, { code: 'SC0', name: '苏超' }, { code: 'USA', name: 'MLS' },
  { code: 'JPN', name: 'J联赛' },
];

const STATUS_LABEL = {
  scheduled: '未开始', today: '今日', live: '⚡ 进行中',
  finished: '已结束', postponed: '延期',
};
const STATUS_COLOR = {
  scheduled: 'var(--fg-muted)', today: 'var(--accent)',
  live: 'var(--red)', finished: 'var(--green)', postponed: 'var(--yellow)',
};

export default function LiveScores() {
  const [matches, setMatches] = useState([]);
  const [loading, setLoading] = useState(true);
  const [league, setLeague] = useState('');
  const [view, setView] = useState('today');
  const [days, setDays] = useState(view === 'today' ? 0 : 7);
  const [liveCount, setLiveCount] = useState(0);

  const fetchMatches = useCallback(async () => {
    try {
      const params = { days };
      if (league) params.league_code = league;
      const data = await get('/fixtures/upcoming', params);
      setMatches(data.matches || []);
      const live = (data.matches || []).filter(m => m.status === 'live' || m.status === 'today');
      setLiveCount(live.length);
    } catch (e) {
      console.error('Failed to fetch matches:', e);
    } finally {
      setLoading(false);
    }
  }, [league, days]);

  // Initial load
  useEffect(() => { fetchMatches(); }, [fetchMatches]);

  // WebSocket for live updates
  useEffect(() => {
    const ws = new WebSocket(WS_BASE + '/live');
    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        if (data.type === 'initial' || data.type === 'update') {
          setMatches(data.matches || []);
          const live = (data.matches || []).filter(m => m.status === 'live' || m.status === 'today');
          setLiveCount(live.length);
        }
      } catch {}
    };
    return () => ws.close();
  }, []);

  const handleViewChange = (v) => {
    setView(v);
    setDays(v === 'today' ? 0 : v === 'upcoming' ? 7 : 30);
  };

  // Group matches by league
  const grouped = {};
  for (const m of matches) {
    const lc = m.league_code || '?';
    if (!grouped[lc]) grouped[lc] = [];
    grouped[lc].push(m);
  }

  return (
    <div>
      {/* Controls */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 20, alignItems: 'center', flexWrap: 'wrap' }}>
        {/* View tabs */}
        <div style={{ display: 'flex', background: 'var(--bg-card)', borderRadius: 8, border: '1px solid var(--border)' }}>
          {[['today', '今日'], ['upcoming', '未来赛程'], ['results', '近期结果']].map(([k, label]) => (
            <button key={k} onClick={() => handleViewChange(k)}
              style={{
                padding: '8px 16px', border: 'none', fontSize: 13, fontWeight: view === k ? 600 : 400,
                background: view === k ? 'var(--bg-input)' : 'transparent',
                color: view === k ? 'var(--fg-primary)' : 'var(--fg-muted)',
                borderRadius: k === 'today' ? '8px 0 0 8px' : k === 'results' ? '0 8px 8px 0' : 0,
                cursor: 'pointer', transition: 'all 0.15s',
              }}>
              {label}
              {k === 'today' && liveCount > 0 && (
                <span style={{ marginLeft: 6, background: 'var(--red)', color: '#fff', borderRadius: 10, padding: '1px 6px', fontSize: 11 }}>
                  {liveCount}
                </span>
              )}
            </button>
          ))}
        </div>

        {/* League filter */}
        <select value={league} onChange={e => { setLeague(e.target.value); setLoading(true); }}
          style={{
            background: 'var(--bg-card)', color: 'var(--fg-primary)', border: '1px solid var(--border)',
            padding: '8px 12px', borderRadius: 8, fontSize: 13, minWidth: 120,
          }}>
          {LEAGUES.map(l => (
            <option key={l.code} value={l.code}>{l.name}</option>
          ))}
        </select>

        {/* Match count */}
        <span style={{ fontSize: 13, color: 'var(--fg-muted)' }}>
          {matches.length} 场比赛
        </span>
      </div>

      {/* Stats bar */}
      {view === 'today' && (
        <div style={{
          display: 'flex', gap: 20, marginBottom: 16, padding: '12px 16px',
          background: 'var(--bg-card)', borderRadius: 8, border: '1px solid var(--border)',
          fontSize: 13, color: 'var(--fg-muted)',
        }}>
          <span>⚡ 进行中: <b style={{ color: 'var(--red)' }}>{liveCount}</b></span>
          <span>{'📅'} 未开始: <b style={{ color: 'var(--accent)' }}>{matches.filter(m => m.status === 'scheduled' || m.status === 'today').length - liveCount}</b></span>
          <span>✅ 已结束: <b style={{ color: 'var(--green)' }}>{matches.filter(m => m.status === 'finished').length}</b></span>
        </div>
      )}

      {/* Match list */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: 60, color: 'var(--fg-muted)' }}>加载中...</div>
      ) : matches.length === 0 ? (
        <div style={{
          textAlign: 'center', padding: 60, color: 'var(--fg-muted)',
          background: 'var(--bg-card)', borderRadius: 8, border: '1px solid var(--border)',
        }}>
          <div style={{ fontSize: 40, marginBottom: 12 }}>{'📭'}</div>
          <div style={{ fontSize: 15 }}>暂无比赛</div>
          <div style={{ fontSize: 13, marginTop: 4 }}>赛季间歇期，新赛季预计 8 月开始</div>
        </div>
      ) : (
        Object.entries(grouped).map(([lcode, leagueMatches]) => (
          <div key={lcode} style={{ marginBottom: 24 }}>
            <h3 style={{
              fontSize: 14, fontWeight: 600, color: 'var(--fg-primary)',
              marginBottom: 10, padding: '6px 12px',
              background: 'var(--bg-card)', borderRadius: 6,
              display: 'inline-block',
            }}>
              {LEAGUES.find(l => l.code === lcode)?.name || lcode}
              <span style={{ marginLeft: 8, color: 'var(--fg-muted)', fontWeight: 400 }}>
                {leagueMatches.length} 场
              </span>
            </h3>

            <div style={{
              display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))',
              gap: 8,
            }}>
              {leagueMatches.map(m => (
                <MatchCard key={m.id || `${m.home_team}-${m.away_team}`} match={m} />
              ))}
            </div>
          </div>
        ))
      )}
    </div>
  );
}

function MatchCard({ match: m }) {
  const isLive = m.status === 'live' || m.status === 'today';
  const isFinished = m.status === 'finished';
  const hasScore = m.home_score != null && m.away_score != null;

  return (
    <div style={{
      background: 'var(--bg-card)', borderRadius: 8, border: '1px solid var(--border)',
      padding: '14px 16px', transition: 'border-color 0.2s',
      borderColor: isLive ? 'var(--red)' : 'var(--border)',
      position: 'relative', overflow: 'hidden',
    }}>
      {/* Live pulse */}
      {isLive && (
        <span style={{
          position: 'absolute', top: 8, right: 10, width: 8, height: 8,
          borderRadius: '50%', background: 'var(--red)',
          animation: 'pulse 1.5s infinite',
        }} />
      )}

      {/* Status badge */}
      <div style={{ fontSize: 11, marginBottom: 8, display: 'flex', gap: 8, alignItems: 'center' }}>
        <span style={{ color: STATUS_COLOR[m.status] || 'var(--fg-muted)', fontWeight: 500 }}>
          {STATUS_LABEL[m.status] || m.status}
        </span>
        {m.match_time && <span style={{ color: 'var(--fg-muted)' }}>{m.match_time}</span>}
        {isLive && m.minute > 0 && (
          <span style={{
            background: 'var(--red)', color: '#fff', padding: '1px 6px', borderRadius: 4, fontSize: 11,
          }}>
            {m.minute}′
          </span>
        )}
      </div>

      {/* Teams + Score */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        {/* Home */}
        <div style={{ flex: 1, textAlign: 'right' }}>
          <div style={{ fontWeight: 600, fontSize: 15, color: 'var(--fg-primary)' }}>{m.home_team}</div>
        </div>

        {/* Score */}
        <div style={{
          minWidth: 64, textAlign: 'center',
          fontSize: 18, fontWeight: 700, color: 'var(--fg-primary)',
          letterSpacing: 2,
        }}>
          {hasScore ? `${m.home_score} - ${m.away_score}` : 'vs'}
        </div>

        {/* Away */}
        <div style={{ flex: 1, textAlign: 'left' }}>
          <div style={{ fontWeight: 600, fontSize: 15, color: 'var(--fg-primary)' }}>{m.away_team}</div>
        </div>
      </div>

      {/* Odds row */}
      {(m.odds_home || m.odds_draw || m.odds_away) && !isFinished && (
        <div style={{
          display: 'flex', gap: 8, marginTop: 10, paddingTop: 10,
          borderTop: '1px solid var(--border)', fontSize: 12,
          justifyContent: 'center',
        }}>
          <OddsBadge label="主胜" value={m.odds_home} />
          <OddsBadge label="平" value={m.odds_draw} />
          <OddsBadge label="客胜" value={m.odds_away} />
          {m.odds_over25 && <OddsBadge label="大2.5" value={m.odds_over25} />}
        </div>
      )}

      {/* Live stats row */}
      {isLive && (m.home_possession || m.home_shots) && (
        <div style={{
          marginTop: 10, paddingTop: 10, borderTop: '1px solid var(--border)',
          display: 'flex', gap: 20, fontSize: 11, color: 'var(--fg-muted)',
          justifyContent: 'center',
        }}>
          {m.home_possession > 0 && (
            <span>控球 {m.home_possession}% - {m.away_possession}%</span>
          )}
          {m.home_shots > 0 && (
            <span>射门 {m.home_shots} - {m.away_shots}</span>
          )}
          {m.home_corners > 0 && (
            <span>角球 {m.home_corners} - {m.away_corners}</span>
          )}
        </div>
      )}
    </div>
  );
}

function OddsBadge({ label, value }) {
  if (!value) return null;
  return (
    <span style={{
      background: 'var(--bg-input)', padding: '3px 8px', borderRadius: 4,
      color: 'var(--fg-body)', fontWeight: 500,
    }}>
      {label} <span style={{ color: 'var(--accent)', fontWeight: 600 }}>{Number(value).toFixed(2)}</span>
    </span>
  );
}
