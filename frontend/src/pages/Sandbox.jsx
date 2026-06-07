import { useState, useEffect } from 'react';
import { get, post } from '../api';
import PitchFormation from '../components/PitchFormation';
import PlayerSlot from '../components/PlayerSlot';
import { ClubSearch } from '../components/SearchDropdown';
import SimAnimation from '../components/SimAnimation';

const FORMATIONS = ['4-3-3', '4-4-2', '3-5-2', '4-2-3-1', '5-3-2', '4-1-4-1'];

const SLOT_MAP = {
  '4-3-3': ['GK','LB','CB','CB','RB','CM','CM','CM','LW','ST','RW'],
  '4-4-2': ['GK','LB','CB','CB','RB','LM','CM','CM','RM','ST','ST'],
  '3-5-2': ['GK','CB','CB','CB','LM','CM','CM','CM','RM','ST','ST'],
  '4-2-3-1': ['GK','LB','CB','CB','RB','CDM','CDM','LW','CAM','RW','ST'],
  '5-3-2': ['GK','LWB','CB','CB','CB','RWB','CM','CM','CM','ST','ST'],
  '4-1-4-1': ['GK','LB','CB','CB','RB','CDM','LM','CM','CM','RM','ST'],
};

const MATCH_CONTEXTS = [
  { value: 'league', label: '联赛' },
  { value: 'derby', label: '德比' },
  { value: 'title_decider', label: '争冠' },
  { value: 'relegation', label: '保级' },
  { value: 'cup_ko', label: '杯赛淘汰' },
  { value: 'cup_final', label: '决赛' },
  { value: 'cl_knockout', label: '欧冠淘汰' },
  { value: 'cl_final', label: '欧冠决赛' },
  { value: 'friendly', label: '友谊赛' },
];

function emptySlot(pos) {
  return { name: '', position: pos, player_id: null, attack_rating: null, defense_rating: null, source: 'custom' };
}

export default function Sandbox({ prefill, onPrefillUsed }) {
  const [formA, setFormA] = useState('4-3-3');
  const [formB, setFormB] = useState('4-3-3');
  const [playersA, setPlayersA] = useState(SLOT_MAP['4-3-3'].map(emptySlot));
  const [playersB, setPlayersB] = useState(SLOT_MAP['4-3-3'].map(emptySlot));
  const [sims, setSims] = useState(1000);
  const [context, setContext] = useState('league');
  const [homeAdv, setHomeAdv] = useState(true);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [showAnim, setShowAnim] = useState(false);
  const [formations, setFormations] = useState(FORMATIONS);

  useEffect(() => {
    get('/sandbox/formations').then(d => {
      if (d.formations?.length) setFormations(d.formations);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (prefill) {
      // prefill from fixtures page
      onPrefillUsed?.();
    }
  }, [prefill]);

  async function handleSimulate() {
    const filledA = playersA.filter(p => p.name || p.player_id);
    const filledB = playersB.filter(p => p.name || p.player_id);
    if (filledA.length < 7 || filledB.length < 7) {
      alert('每队至少需要 7 名球员');
      return;
    }
    setLoading(true);
    setShowAnim(true);
  }

  function onAnimComplete() {
    setShowAnim(false);
    doSimulate();
  }

  async function doSimulate() {
    const filledA = playersA.filter(p => p.name || p.player_id);
    const filledB = playersB.filter(p => p.name || p.player_id);
    try {
      const d = await post('/sandbox/simulate', {
        team_a: { formation: formA, players: filledA },
        team_b: { formation: formB, players: filledB },
        simulations: sims,
        home_advantage: homeAdv,
        match_context: context,
      });
      setResult(d);
    } catch (err) {
      setResult({ error: err.message });
    }
    setLoading(false);
  }

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto' }}>
      <h2 style={{ color: 'var(--fg-primary)', fontSize: 16, marginBottom: 16 }}>{'⚽'} {'沙盘模拟器'}</h2>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}>
        <TeamPanel
          label={"🏠 主队"}
          formation={formA}
          players={playersA}
          setPlayers={setPlayersA}
          onChangeForm={f => { setFormA(f); setPlayersA(SLOT_MAP[f].map(emptySlot)); }}
          formations={formations}
        />
        <TeamPanel
          label={"🛫 客队"}
          formation={formB}
          players={playersB}
          setPlayers={setPlayersB}
          onChangeForm={f => { setFormB(f); setPlayersB(SLOT_MAP[f].map(emptySlot)); }}
          formations={formations}
        />
      </div>

      {/* Controls */}
      <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap', marginBottom: 16 }}>
        <select value={context} onChange={e => setContext(e.target.value)} style={selectStyle}>
          {MATCH_CONTEXTS.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
        </select>
        <select value={sims} onChange={e => setSims(Number(e.target.value))} style={selectStyle}>
          <option value={1000}>1000 sims</option>
          <option value={5000}>5000 sims</option>
          <option value={10000}>10000 sims</option>
        </select>
        <label style={{ display: 'flex', alignItems: 'center', gap: 4, color: 'var(--fg-muted)', fontSize: 12 }}>
          <input type="checkbox" checked={homeAdv} onChange={e => setHomeAdv(e.target.checked)} />
          {'主场优势'}
        </label>
        <button onClick={handleSimulate} disabled={loading}
          style={{ background: loading ? 'var(--bg-input)' : 'var(--green)', color: '#fff', border: 'none', padding: '10px 24px', borderRadius: 6, cursor: 'pointer', fontSize: 14, fontWeight: 'bold' }}>
          {loading ? '模拟中...' : '▶ 开始模拟'}
        </button>
      </div>

      {/* Animation */}
      {showAnim && <SimAnimation onComplete={onAnimComplete} />}

      {/* Results */}
      {result && !result.error && <SimResult data={result} sims={sims} teamA={playersA[0]?.name || '主队'} teamB={playersB[0]?.name || '客队'} />}
      {result?.error && (
        <div style={{ color: 'var(--red)', padding: 12, background: 'rgba(248,81,73,0.1)', borderRadius: 6 }}>{result.error}</div>
      )}
    </div>
  );
}


function TeamPanel({ label, formation, players, setPlayers, onChangeForm, formations }) {
  const [step, setStep] = useState('league');
  const [selectedLeague, setSelectedLeague] = useState('');
  const [clubLeagues, setClubLeagues] = useState([]);
  const [clubs, setClubs] = useState([]);
  const [selectedClub, setSelectedClub] = useState(null);

  useEffect(() => {
    get('/clubs/leagues').then(d => {
      const leagues = Array.isArray(d) ? d : (d.leagues || []);
      setClubLeagues(leagues);
    }).catch(() => {});
  }, []);

  async function selectLeague(lg) {
    setSelectedLeague(lg);
    setStep('club');
    try {
      const d = await get('/clubs/by-league', { competition_id: lg });
      setClubs(d.clubs || []);
    } catch { setClubs([]); }
  }

  async function selectClub(club) {
    setSelectedClub(club);
    setStep('squad');
    try {
      const d = await get(`/clubs/${club.club_id || club.name}/squad`);
      const squad = d.players || [];
      const newPlayers = SLOT_MAP[formation].map((pos, i) => {
        const p = squad[i];
        if (p) {
          return {
            name: p.name || '',
            position: pos,
            player_id: p.player_id || null,
            attack_rating: p.attack_rating || null,
            defense_rating: p.defense_rating || null,
            source: 'transfermarkt',
          };
        }
        return emptySlot(pos);
      });
      setPlayers(newPlayers);
    } catch {}
  }

  function updatePlayer(index, data) {
    const next = [...players];
    next[index] = { ...next[index], ...data };
    setPlayers(next);
  }

  return (
    <div style={cardStyle}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <span style={{ color: 'var(--fg-primary)', fontWeight: 'bold', fontSize: 14 }}>{label}</span>
        <select value={formation} onChange={e => onChangeForm(e.target.value)} style={{ ...selectStyle, width: 100 }}>
          {formations.map(f => {
            const name = typeof f === 'string' ? f : f.name;
            return <option key={name} value={name}>{name}</option>;
          })}
        </select>
      </div>

      {/* Step indicator */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 10, fontSize: 11 }}>
        {['league','club','squad'].map((s, i) => (
          <span key={s} style={{ color: step === s ? 'var(--accent)' : 'var(--fg-muted)', fontWeight: step === s ? 'bold' : 'normal' }}>
            {i > 0 && <span style={{ margin: '0 4px' }}>{'→'}</span>}
            {({league:'① League', club:'② Club', squad:'③ Squad'}[s])}
          </span>
        ))}
      </div>

      {/* Step 1: League */}
      {step === 'league' && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 8 }}>
          {clubLeagues.map(lg => {
            const id = typeof lg === 'string' ? lg : lg.id;
            const name = typeof lg === 'string' ? lg : (lg.name || lg.id);
            return (
              <button key={id} onClick={() => selectLeague(id)}
                style={{ background: selectedLeague === id ? 'var(--accent)' : 'var(--bg-input)', color: selectedLeague === id ? '#fff' : 'var(--fg-muted)', border: 'none', padding: '4px 10px', borderRadius: 4, cursor: 'pointer', fontSize: 11 }}>
                {name}
              </button>
            );
          })}
          <button onClick={() => setStep('club')}
            style={{ background: 'var(--bg-input)', color: 'var(--fg-muted)', border: 'none', padding: '4px 10px', borderRadius: 4, cursor: 'pointer', fontSize: 11 }}>
            {'← Skip'}
          </button>
        </div>
      )}

      {/* Step 2: Club */}
      {step === 'club' && (
        <div style={{ marginBottom: 8 }}>
          <div style={{ display: 'flex', gap: 4, marginBottom: 6 }}>
            <button onClick={() => setStep('league')}
              style={{ background: 'var(--bg-input)', color: 'var(--fg-muted)', border: 'none', padding: '4px 8px', borderRadius: 4, cursor: 'pointer', fontSize: 11 }}>
              {'←'}
            </button>
            <ClubSearch onSelect={selectClub} placeholder={'搜索俱乐部...'} />
          </div>
          <div style={{ maxHeight: 150, overflowY: 'auto' }}>
            {clubs.map(c => (
              <div key={c.club_id || c.name} onClick={() => selectClub(c)}
                style={{ padding: '6px 8px', cursor: 'pointer', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--fg-body)' }}>{c.name}</span>
                <span style={{ color: 'var(--fg-muted)' }}>{(c.squad_size || c.source === 'fixtures') ? '🏟' : ''}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Step 3: Squad */}
      {step === 'squad' && (
        <div>
          {selectedClub && (
            <div style={{ fontSize: 11, color: 'var(--fg-muted)', marginBottom: 6 }}>
              <span style={{ fontWeight: 'bold', color: 'var(--fg-primary)' }}>{selectedClub.name}</span>
              <button onClick={() => setStep('club')} style={{ marginLeft: 8, background: 'none', border: 'none', color: 'var(--accent)', cursor: 'pointer', fontSize: 11 }}>{'← 换俱乐部'}</button>
            </div>
          )}
          <PitchFormation formation={formation} players={players} />
          <div style={{ marginTop: 8, display: 'grid', gap: 4 }}>
            {players.map((p, i) => (
              <PlayerSlot key={i} player={p} index={i} onChange={data => updatePlayer(i, data)} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}


function SimResult({ data, sims, teamA, teamB }) {
  if (!data || data.error) {
    return <div style={{ color: 'var(--red)', fontSize: 12 }}>Error: {data?.error || 'Unknown'}</div>;
  }

  const r = data.result || data;
  const wdl = r.wdl || {};
  const goals = r.goals || {};
  const scores = r.score_distribution || {};
  const topScores = Object.entries(scores).sort((a, b) => b[1] - a[1]).slice(0, 6);

  return (
    <div style={{ display: 'grid', gap: 12, marginTop: 16 }}>
      {/* Score + WDL */}
      <div style={cardStyle}>
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 20, marginBottom: 12 }}>
          <div style={{ textAlign: 'center' }}>
            <div style={{ color: 'var(--fg-primary)', fontWeight: 'bold', fontSize: 14 }}>{teamA}</div>
            <div style={{ color: 'var(--accent)', fontSize: 24, fontWeight: 'bold' }}>{goals.home?.toFixed(2)}</div>
            <div style={{ color: 'var(--fg-muted)', fontSize: 11 }}>xG</div>
          </div>
          <div style={{ color: 'var(--fg-muted)' }}>vs</div>
          <div style={{ textAlign: 'center' }}>
            <div style={{ color: 'var(--fg-primary)', fontWeight: 'bold', fontSize: 14 }}>{teamB}</div>
            <div style={{ color: 'var(--accent)', fontSize: 24, fontWeight: 'bold' }}>{goals.away?.toFixed(2)}</div>
            <div style={{ color: 'var(--fg-muted)', fontSize: 11 }}>xG</div>
          </div>
        </div>

        <div style={{ display: 'flex', height: 10, borderRadius: 5, overflow: 'hidden', background: 'var(--bg-input)' }}>
          <div style={{ width: `${(wdl.home_win || 0) * 100}%`, background: 'var(--green)' }} />
          <div style={{ width: `${(wdl.draw || 0) * 100}%`, background: 'var(--yellow)' }} />
          <div style={{ width: `${(wdl.away_win || 0) * 100}%`, background: 'var(--red)' }} />
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 6, fontSize: 13 }}>
          <span style={{ color: 'var(--green)', fontWeight: 'bold' }}>{'主胜'} {(wdl.home_win * 100)?.toFixed(1)}%</span>
          <span style={{ color: 'var(--yellow)', fontWeight: 'bold' }}>{'平局'} {(wdl.draw * 100)?.toFixed(1)}%</span>
          <span style={{ color: 'var(--red)', fontWeight: 'bold' }}>{'客胜'} {(wdl.away_win * 100)?.toFixed(1)}%</span>
        </div>
      </div>

      {/* Score Distribution */}
      <div style={cardStyle}>
        <div style={{ color: 'var(--accent)', fontWeight: 'bold', fontSize: 13, marginBottom: 8 }}>{'最可能比分'}</div>
        {topScores.map(([score, prob]) => (
          <div key={score} style={{ display: 'flex', justifyContent: 'space-between', padding: '3px 0', fontSize: 12 }}>
            <span style={{ color: 'var(--fg-primary)' }}>{score}</span>
            <span style={{ color: 'var(--fg-muted)' }}>{(prob * 100).toFixed(1)}%</span>
          </div>
        ))}
      </div>

      {data.duration_seconds && (
        <div style={{ color: 'var(--fg-muted)', fontSize: 11 }}>
          {data.simulations || sims} simulations {'·'} {data.duration_seconds}s
        </div>
      )}
    </div>
  );
}


const cardStyle = {
  background: 'var(--bg-card)',
  border: '1px solid var(--border)',
  borderRadius: 8,
  padding: 12,
};

const selectStyle = {
  background: 'var(--bg-input)',
  color: 'var(--fg-primary)',
  border: '1px solid var(--border)',
  padding: '6px 10px',
  borderRadius: 6,
  fontSize: 12,
  minWidth: 100,
};
