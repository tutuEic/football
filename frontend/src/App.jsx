import { useState, useCallback } from 'react';
import Dashboard from './pages/Dashboard';
import Predictions from './pages/Predictions';
import Sandbox from './pages/Sandbox';
import TeamAnalysis from './pages/TeamAnalysis';
import EVScanner from './pages/EVScanner';
import LiveScores from './pages/LiveScores';
import Fixtures from './pages/Fixtures';
import WorldCup from './pages/WorldCup';

const TABS = [
  { key: 'live',       label: '实时' },
  { key: 'dashboard',  label: '仪表盘' },
  { key: 'predictions', label: '预测' },
  { key: 'fixtures',   label: '赛程' },
  { key: 'worldcup',   label: '世界杯' },
  { key: 'sandbox',    label: '沙盘' },
  { key: 'teams',      label: '球队' },
  { key: 'ev',         label: 'EV' },
];

export default function App() {
  const [tab, setTab] = useState('sandbox');
  const [sandboxPrefill, setSandboxPrefill] = useState(null);

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <header style={{
        background: 'var(--bg-card)', borderBottom: '1px solid var(--border)',
        padding: '10px 24px', display: 'flex', alignItems: 'center',
        justifyContent: 'space-between', position: 'sticky', top: 0, zIndex: 10
      }}>
        <h1 style={{ color: 'var(--fg-primary)', fontSize: 18, fontWeight: 'bold', margin: 0 }}>
          足球预测系统
        </h1>
        <nav style={{ display: 'flex', gap: 4 }}>
          {TABS.map(t => (
            <button key={t.key} onClick={() => setTab(t.key)}
              style={{
                background: tab === t.key ? 'var(--bg-input)' : 'transparent',
                color: tab === t.key ? 'var(--fg-primary)' : 'var(--fg-muted)',
                border: 'none', padding: '8px 14px', cursor: 'pointer',
                fontSize: 13, borderRadius: 6, transition: 'all 0.15s'
              }}>
              {t.label}
            </button>
          ))}
        </nav>
      </header>

      {/* Content */}
      <main style={{ flex: 1, padding: 24, maxWidth: 1400, margin: '0 auto', width: '100%' }}>
        {tab === 'live' && <LiveScores />}
        {tab === 'dashboard' && <Dashboard />}
        {tab === 'predictions' && <Predictions />}
        {tab === 'fixtures' && <Fixtures onSimulate={(home, away) => {
          setSandboxPrefill({ home, away });
          setTab('sandbox');
        }} />}
        {tab === 'teams' && <TeamAnalysis />}
        {tab === 'ev' && <EVScanner />}
        {tab === 'worldcup' && <WorldCup />}
        {tab === 'sandbox' && <Sandbox prefill={sandboxPrefill} onPrefillUsed={() => setSandboxPrefill(null)} />}
      </main>

      {/* Footer */}
      <footer style={{
        background: 'var(--bg-card)', borderTop: '1px solid var(--border)',
        padding: '8px 24px', fontSize: 12, color: 'var(--fg-muted)',
        display: 'flex', gap: 16, justifyContent: 'center'
      }}>
        <span>Dixon-Coles + Monte Carlo</span>
        <span>|</span>
        <span>足球预测系统</span>
        <span>|</span>
        <span style={{ color: 'var(--green)' }}>API 在线</span>
      </footer>
    </div>
  );
}
