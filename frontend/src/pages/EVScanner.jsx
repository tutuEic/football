import { useState } from 'react';
import { get } from '../api';

const LEAGUES = [
  { code: 'E0', name: '英超' }, { code: 'SP1', name: '西甲' },
  { code: 'D1', name: '德甲' }, { code: 'I1', name: '意甲' },
  { code: 'F1', name: '法甲' },
];

export default function EVScanner() {
  const [league, setLeague] = useState('E0');
  const [minEV, setMinEV] = useState(0);
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  async function scan() {
    setLoading(true);
    setResults(null);
    setError(null);
    try {
      const d = await get('/odds/scan', { league, min_ev: minEV });
      setResults(d);
    } catch (e) {
      setError('扫描失败: ' + e.message);
    }
    setLoading(false);
  }

  return (
    <div>
      <h2 style={{ color: 'var(--fg-primary)', fontSize: 18, marginBottom: 20 }}>{'💰'} EV 价值扫描</h2>

      <div style={{ display: 'flex', gap: 8, marginBottom: 24, alignItems: 'center' }}>
        <select value={league} onChange={e => setLeague(e.target.value)}
          style={selectStyle}>
          {LEAGUES.map(l => <option key={l.code} value={l.code}>{l.name}</option>)}
        </select>
        <label style={{ color: 'var(--fg-muted)', fontSize: 13 }}>
          最低 EV:
          <input type="number" value={minEV} onChange={e => setMinEV(+e.target.value)}
            step="0.01" style={{ ...inputStyle, width: 70, marginLeft: 6 }} />
        </label>
        <button onClick={scan} disabled={loading}
          style={{ padding: '8px 24px', background: 'var(--green)', border: 'none', borderRadius: 6, color: '#fff', fontWeight: 'bold' }}>
          {loading ? '扫描中...' : '⚡ 开始扫描'}
        </button>
      </div>

      {results && (
        <div>
          <div style={{ color: 'var(--fg-muted)', fontSize: 13, marginBottom: 12 }}>
            扫描 {results.scanned || 0} 场 · EV+ 共 {results.ev_positive || 0} 场
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {(results.results || []).map((item, i) => (
              <div key={i} style={{
                background: 'var(--bg-card)', border: '1px solid var(--border)',
                borderRadius: 8, padding: '12px 16px',
                display: 'flex', alignItems: 'center', gap: 12
              }}>
                <div style={{
                  width: 36, height: 36, borderRadius: '50%',
                  background: item.ev > 0.03 ? 'var(--green)' : 'var(--accent)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  color: '#fff', fontSize: 16
                }}>
                  {item.ev > 0.03 ? '⭐' : '•'}
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ color: 'var(--fg-body)', fontSize: 14 }}>{item.match}</div>
                  <div style={{ color: 'var(--fg-muted)', fontSize: 12 }}>
                    {item.outcome === 'home' ? '主胜' : item.outcome === 'draw' ? '平局' : '客胜'}
                    {' '}模型 {item.model_prob.toFixed(3)} | 赔率 @{item.market_odds}
                  </div>
                </div>
                <div style={{
                  background: item.ev > 0 ? 'var(--green)' : 'var(--bg-input)',
                  color: item.ev > 0 ? '#fff' : 'var(--fg-muted)',
                  padding: '4px 10px', borderRadius: 6, fontSize: 13, fontWeight: 'bold'
                }}>
                  EV {(item.ev * 100).toFixed(1)}%
                </div>
              </div>
            ))}
          </div>

          {(!results.results || results.results.length === 0) && (
            <div style={{ color: 'var(--fg-muted)', textAlign: 'center', padding: 40 }}>
              未找到符合条件的 EV 信号
            </div>
          )}
        </div>
      )}
    </div>
  );
}

const selectStyle = {
  background: 'var(--bg-input)', color: 'var(--fg-body)',
  border: '1px solid var(--border)', borderRadius: 6, padding: '8px 12px', fontSize: 14
};

const inputStyle = {
  background: 'var(--bg-input)', color: 'var(--fg-body)',
  border: '1px solid var(--border)', borderRadius: 6, padding: '6px 8px', fontSize: 13
};
