import { useState } from 'react';
import { PlayerSearch } from './SearchDropdown';

export default function PlayerSlot({ player, index, onChange }) {
  const [showSearch, setShowSearch] = useState(false);

  function handlePlayerSelect(p) {
    onChange({
      ...player,
      player_id: parseInt(p.id?.split(':')[1]) || null,
      name: p.name,
      position: p.position,
      attack_rating: p.attack_rating,
      defense_rating: p.defense_rating,
      overall: p.overall,
      att: p.att,
      source: p.source || 'transfermarkt',
    });
    setShowSearch(false);
  }

  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 8, padding: '4px 8px',
      background: 'var(--bg-input)', borderRadius: 6, fontSize: 13, position: 'relative'
    }}>
      <span style={{ color: 'var(--fg-muted)', width: 28, textAlign: 'center', flexShrink: 0 }}>
        {index + 1}
      </span>

      {showSearch ? (
        <PlayerSearch
          value={player.name}
          onChange={v => onChange({ ...player, name: v })}
          onSelect={handlePlayerSelect}
          placeholder="搜索球员..."
          style={{ flex: 1 }}
        />
      ) : (
        <>
          <span onClick={() => setShowSearch(true)}
            style={{
              color: player.name ? 'var(--fg-body)' : 'var(--fg-muted)', flex: 1, cursor: 'pointer',
              whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis'
            }}>
            {player.name || '🔍 点击搜索球员'}
          </span>
          {player.overall != null && (
            <span style={{
              width: 28, height: 28, borderRadius: '50%',
              background: player.overall > 80 ? 'var(--green)' : player.overall > 70 ? 'var(--accent)' : 'var(--bg-hover)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: '#fff', fontSize: 11, fontWeight: 'bold', flexShrink: 0
            }}>{player.overall}</span>
          )}
          <span style={{ color: 'var(--fg-muted)', width: 40, textAlign: 'center', flexShrink: 0, fontSize: 11 }}>
            {player.position}
          </span>
          <span style={{ color: 'var(--green)', width: 26, textAlign: 'center', flexShrink: 0, fontSize: 12 }}>
            {player.attack_rating || '-'}
          </span>
          <span style={{ color: 'var(--red)', width: 26, textAlign: 'center', flexShrink: 0, fontSize: 12 }}>
            {player.defense_rating || '-'}
          </span>
        </>
      )}

      <button onClick={() => setShowSearch(!showSearch)}
        style={{
          background: 'transparent', border: 'none', color: 'var(--fg-muted)',
          fontSize: 14, padding: '2px 4px', cursor: 'pointer', flexShrink: 0
        }}>
        {showSearch ? '✕' : '🔍'}
      </button>
    </div>
  );
}
