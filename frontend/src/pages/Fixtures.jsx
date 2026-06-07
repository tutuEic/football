import { useState, useEffect } from 'react';
import { get, post } from '../api';

const LEAGUE_NAMES = {
  CL: '欧冠', E0: '英超', SP1: '西甲', I1: '意甲', D1: '德甲', F1: '法甲',
  E1: '英冠', SP2: '西乙', I2: '意乙', D2: '德乙', F2: '法乙',
  N1: '荷甲', B1: '比甲', P1: '葡超', T1: '土超',
  SC0: '苏超', SC1: '苏冠', G1: '希腊超',
};

export default function Fixtures({ onSimulate }) {
  const [fixtures, setFixtures] = useState([]);
  const [loading, setLoading] = useState(false);
  const [league, setLeague] = useState('');
  const [editingOdds, setEditingOdds] = useState(null);
  const [oddsForm, setOddsForm] = useState({ home: '', draw: '', away: '' });
  const [toast, setToast] = useState(null);

  async function loadFixtures() {
    setLoading(true);
    try {
      const params = league ? '?league=' + league + '&limit=30' : '?limit=30';
      const data = await get('/fixtures/predictions' + params);
      setFixtures(data.fixtures || []);
    } catch (e) {
      console.error(e);
      setFixtures([]);
    }
    setLoading(false);
  }

  useEffect(() => { loadFixtures(); }, [league]);

  async function saveOdds(fixtureId) {
    try {
      await post('/fixtures/update-odds', {
        fixture_id: fixtureId,
        odds_home: parseFloat(oddsForm.home),
        odds_draw: parseFloat(oddsForm.draw),
        odds_away: parseFloat(oddsForm.away),
      });
      setEditingOdds(null);
      loadFixtures();
    } catch (e) {
      setToast('保存失败: ' + e.message);
      setTimeout(() => setToast(null), 4000);
    }
  }

  function getConfidenceBadge(conf) {
    const colors = { high: 'var(--green)', medium: 'var(--yellow)', low: 'var(--fg-muted)' };
    const labels = { high: '高', medium: '中', low: '低' };
    return (
      <span style={{ background: colors[conf] || 'var(--fg-muted)', color: '#000', padding: '2px 8px', borderRadius: 4, fontSize: 11, fontWeight: 'bold' }}>
        {labels[conf] || '低'}
      </span>
    );
  }

  function formatOdds(v) {
    return v != null ? v.toFixed(2) : '-';
  }

  function formatEv(v) {
    if (v == null) return '-';
    const pct = (v * 100).toFixed(1);
    return v > 0 ? '+' + pct + '%' : pct + '%';
  }

  return (
    <div>
      {toast && <div style={{ position: 'fixed', top: 16, right: 16, zIndex: 9999, background: 'var(--red)', color: '#fff', padding: '10px 16px', borderRadius: 8, fontSize: 13, boxShadow: '0 4px 12px rgba(0,0,0,0.3)' }}>{toast}</div>}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
        <h2 style={{ color: 'var(--fg-primary)', fontSize: 20, margin: 0 }}>{'赛程'} + {'预测'} + {'盘口'}</h2>
        <select value={league} onChange={e => setLeague(e.target.value)}
          style={{ background: 'var(--bg-input)', color: 'var(--fg-body)', border: '1px solid var(--border)', borderRadius: 6, padding: '6px 10px', fontSize: 13 }}>
          <option value="">{'全部联赛'}</option>
          {Object.entries(LEAGUE_NAMES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        <button onClick={loadFixtures} disabled={loading}
          style={{ background: 'var(--accent)', color: '#fff', border: 'none', borderRadius: 6, padding: '6px 16px', cursor: 'pointer', fontSize: 13 }}>
          {loading ? '加载中...' : '刷新'}
        </button>
      </div>

      {fixtures.length === 0 && !loading && (
        <div style={{ textAlign: 'center', color: 'var(--fg-muted)', padding: 40 }}>
          {'暂无即将比赛'}
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {fixtures.map((f, i) => (
          <div key={f.fixture_id || i} style={{
            background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 10,
            padding: '16px 20px', display: 'grid', gridTemplateColumns: '1fr 2fr 1.5fr 1.5fr 1fr',
            alignItems: 'center', gap: 16
          }}>
            {/* 联赛 & 时间 */}
            <div>
              <div style={{ color: 'var(--accent)', fontSize: 13, fontWeight: 'bold' }}>
                {LEAGUE_NAMES[f.league] || f.league}
              </div>
              <div style={{ color: 'var(--fg-muted)', fontSize: 12 }}>{f.date}</div>
              {f.time && <div style={{ color: 'var(--fg-muted)', fontSize: 11 }}>{f.time}</div>}
            </div>

            {/* 对阵 */}
            <div style={{ fontSize: 16 }}>
              <span style={{ color: 'var(--fg-primary)', fontWeight: 'bold' }}>{f.home_team}</span>
              <span style={{ color: 'var(--fg-muted)', margin: '0 8px' }}>vs</span>
              <span style={{ color: 'var(--fg-primary)', fontWeight: 'bold' }}>{f.away_team}</span>
              <button onClick={() => onSimulate && onSimulate(f.home_team, f.away_team)}
                style={{ marginLeft: 12, background: 'var(--accent)', color: '#fff', border: 'none', borderRadius: 6, padding: '4px 12px', fontSize: 12, cursor: 'pointer', whiteSpace: 'nowrap' }}>
                {'模拟'}
              </button>
            </div>

            {/* 预测 */}
            {f.prediction ? (
              <>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  {getConfidenceBadge(f.confidence)}
                  <div style={{ display: 'flex', gap: 6, fontSize: 13 }}>
                    <span style={{ color: 'var(--green)', fontWeight: f.prediction.home_win > 0.45 ? 'bold' : 'normal' }}>
                      {(f.prediction.home_win * 100).toFixed(1)}%
                    </span>
                    <span style={{ color: 'var(--yellow)' }}>
                      {(f.prediction.draw * 100).toFixed(1)}%
                    </span>
                    <span style={{ color: 'var(--red)', fontWeight: f.prediction.away_win > 0.45 ? 'bold' : 'normal' }}>
                      {(f.prediction.away_win * 100).toFixed(1)}%
                    </span>
                  </div>
                  {f.prediction.xg_home != null && (
                    <span style={{ color: 'var(--fg-muted)', fontSize: 11 }}>
                      xG {f.prediction.xg_home}-{f.prediction.xg_away}
                    </span>
                  )}
                </div>

                {/* 盘口信息 */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12 }}>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <span style={{ color: 'var(--fg-muted)' }}>{'公平'}:</span>
                    <span>{formatOdds(f.fair_odds?.home)}</span>
                    <span>{formatOdds(f.fair_odds?.draw)}</span>
                    <span>{formatOdds(f.fair_odds?.away)}</span>
                  </div>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <span style={{ color: 'var(--fg-muted)' }}>{'市场'}:</span>
                    {editingOdds === f.fixture_id ? (
                      <>
                        <input value={oddsForm.home} onChange={e => setOddsForm({...oddsForm, home: e.target.value})} style={{ width: 50, fontSize: 12, padding: '2px 4px', background: 'var(--bg-input)', color: 'var(--fg-body)', border: '1px solid var(--border)', borderRadius: 3 }} />
                        <input value={oddsForm.draw} onChange={e => setOddsForm({...oddsForm, draw: e.target.value})} style={{ width: 50, fontSize: 12, padding: '2px 4px', background: 'var(--bg-input)', color: 'var(--fg-body)', border: '1px solid var(--border)', borderRadius: 3 }} />
                        <input value={oddsForm.away} onChange={e => setOddsForm({...oddsForm, away: e.target.value})} style={{ width: 50, fontSize: 12, padding: '2px 4px', background: 'var(--bg-input)', color: 'var(--fg-body)', border: '1px solid var(--border)', borderRadius: 3 }} />
                        <button onClick={() => saveOdds(f.fixture_id)} style={{ background: 'var(--green)', color: '#fff', border: 'none', borderRadius: 3, padding: '2px 8px', fontSize: 11, cursor: 'pointer' }}>{'保存'}</button>
                        <button onClick={() => setEditingOdds(null)} style={{ background: 'transparent', color: 'var(--fg-muted)', border: 'none', fontSize: 11, cursor: 'pointer' }}>{'取消'}</button>
                      </>
                    ) : (
                      <>
                        <span>{formatOdds(f.market_odds?.home)}</span>
                        <span>{formatOdds(f.market_odds?.draw)}</span>
                        <span>{formatOdds(f.market_odds?.away)}</span>
                        <button onClick={() => { setEditingOdds(f.fixture_id); setOddsForm({ home: f.market_odds?.home || '', draw: f.market_odds?.draw || '', away: f.market_odds?.away || '' }); }}
                          style={{ background: 'transparent', color: 'var(--accent)', border: 'none', fontSize: 11, cursor: 'pointer', textDecoration: 'underline' }}>
                          {f.market_odds?.home ? '编辑' : '添加盘口'}
                        </button>
                      </>
                    )}
                  </div>
                  {/* EV */}
                  {f.market_odds?.home && (
                    <div style={{ display: 'flex', gap: 8 }}>
                      <span style={{ color: 'var(--fg-muted)' }}>EV:</span>
                      {['home', 'draw', 'away'].map(out => (
                        <span key={out} style={{ color: f.ev?.[out] > 0 ? 'var(--green)' : 'var(--red)', fontWeight: f.ev?.[out] > 0 ? 'bold' : 'normal' }}>
                          {formatEv(f.ev?.[out])}
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                {/* 价值投注 */}
                <div>
                  {f.best_value?.is_value && (
                    <div style={{ background: 'rgba(63,185,80,0.15)', border: '1px solid var(--green)', borderRadius: 6, padding: '4px 10px', fontSize: 12, color: 'var(--green)' }}>
                      {'价值'}: {f.best_value.outcome === 'home' ? '主胜' : f.best_value.outcome === 'draw' ? '平局' : '客胜'} EV+{(f.best_value.ev * 100).toFixed(1)}%
                    </div>
                  )}
                </div>
              </>
            ) : (
              <div style={{ color: 'var(--fg-muted)', fontSize: 12, gridColumn: 'span 3' }}>{'正在计算预测...'}</div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
