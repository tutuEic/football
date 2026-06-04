/**
 * 可搜索下拉组件
 * 输入文字 → 调 API → 下拉列表 → 点击选择
 */
import { useState, useEffect, useRef } from 'react';
import { get } from '../api';

export function ClubSearch({ value, onChange, onSelect, placeholder = '搜索俱乐部...', style = {} }) {
  const [results, setResults] = useState([]);
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    const handler = e => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  async function search(q) {
    onChange(q);
    if (q.length < 2) { setResults([]); setOpen(false); return; }
    try {
      const d = await get('/clubs/search', { q, limit: 8 });
      setResults(d.clubs || []);
      setOpen((d.clubs || []).length > 0);
    } catch { setResults([]); }
  }

  return (
    <div ref={ref} style={{ position: 'relative', ...style }}>
      <input value={value} onChange={e => search(e.target.value)}
        placeholder={placeholder}
        style={inputStyle} onFocus={() => value.length >= 2 && results.length > 0 && setOpen(true)} />
      {open && results.length > 0 && (
        <div style={dropdownStyle}>
          {results.map(c => (
            <div key={c.club_id} onClick={() => { onSelect(c); setOpen(false); onChange(c.name); }}
              style={itemStyle}>
              <span style={{ color: 'var(--fg-body)', fontSize: 13 }}>{c.name}</span>
              <span style={{ color: 'var(--fg-muted)', fontSize: 11 }}>
                {c.squad_size}人 · {c.stadium_name}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function PlayerSearch({ value, onChange, onSelect, placeholder = '搜索球员...', style = {} }) {
  const [results, setResults] = useState([]);
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    const handler = e => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  async function search(q) {
    onChange(q);
    if (q.length < 2) { setResults([]); setOpen(false); return; }
    try {
      const d = await get('/players/search', { q, limit: 8 });
      setResults(d.players || []);
      setOpen((d.players || []).length > 0);
    } catch { setResults([]); }
  }

  return (
    <div ref={ref} style={{ position: 'relative', ...style }}>
      <input value={value} onChange={e => search(e.target.value)}
        placeholder={placeholder}
        style={{ ...inputStyle, fontSize: 12 }}
        onFocus={() => value.length >= 2 && results.length > 0 && setOpen(true)} />
      {open && results.length > 0 && (
        <div style={dropdownStyle}>
          {results.map(p => (
            <div key={p.id} onClick={() => { onSelect(p); setOpen(false); onChange(p.name); }}
              style={itemStyle}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{
                  width: 26, height: 26, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center',
                  background: p.overall > 80 ? 'var(--green)' : p.overall > 70 ? 'var(--accent)' : 'var(--bg-hover)',
                  color: '#fff', fontSize: 11, fontWeight: 'bold', flexShrink: 0
                }}>{p.overall}</span>
                <div>
                  <div style={{ color: 'var(--fg-body)', fontSize: 13 }}>{p.name}</div>
                  <div style={{ color: 'var(--fg-muted)', fontSize: 11 }}>
                    {p.position} · {p.club} · {p.market_value}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function TeamSearch({ value, onChange, onSelect, league = 'E0', placeholder = '选择球队...', style = {} }) {
  const [teams, setTeams] = useState([]);
  const [open, setOpen] = useState(false);
  const [filtered, setFiltered] = useState([]);
  const ref = useRef(null);

  useEffect(() => {
    get('/teams', { league }).then(d => { setTeams(d.teams || []); setFiltered(d.teams || []); }).catch(() => {});
  }, [league]);

  useEffect(() => {
    const handler = e => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  function handleChange(v) {
    onChange(v);
    setFiltered(teams.filter(t => t.toLowerCase().includes(v.toLowerCase())));
    setOpen(true);
  }

  return (
    <div ref={ref} style={{ position: 'relative', ...style }}>
      <input value={value} onChange={e => handleChange(e.target.value)}
        placeholder={placeholder}
        style={inputStyle}
        onFocus={() => { setFiltered(teams.filter(t => t.toLowerCase().includes(value.toLowerCase()))); setOpen(true); }} />
      {open && filtered.length > 0 && (
        <div style={dropdownStyle}>
          {filtered.slice(0, 15).map(t => (
            <div key={t} onClick={() => { onSelect(t); setOpen(false); }}
              style={itemStyle}>
              <span style={{ color: 'var(--fg-body)', fontSize: 13 }}>{t}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

const inputStyle = {
  width: '100%', padding: '6px 10px', background: 'var(--bg-input)',
  border: '1px solid var(--border)', borderRadius: 6, color: 'var(--fg-primary)', fontSize: 14
};

const dropdownStyle = {
  position: 'absolute', top: '100%', left: 0, right: 0, zIndex: 100,
  background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 6,
  maxHeight: 300, overflowY: 'auto', marginTop: 4
};

const itemStyle = {
  padding: '8px 12px', cursor: 'pointer', borderBottom: '1px solid var(--border)',
  display: 'flex', flexDirection: 'column', gap: 2
};
