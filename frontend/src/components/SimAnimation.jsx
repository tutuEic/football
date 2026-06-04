import { useState, useEffect, useRef } from 'react';

const BALL_EMOJIS = ['?', '??', '???', '??', '??', '?', '??', '??'];
const COMMENTARY = [
  '????????...',
  '??????...',
  '??????...',
  '???1??...',
  '??Dixon-Coles??...',
  '????????...',
  '??????...',
  '??????...',
  '??????...',
  '??????...',
  '??????...',
  '?????',
];

export default function SimAnimation({ onComplete }) {
  const [progress, setProgress] = useState(0);
  const [commentary, setCommentary] = useState('');
  const [ballPos, setBallPos] = useState(50);
  const [particles, setParticles] = useState([]);
  const frameRef = useRef(0);
  const startTime = useRef(Date.now());

  useEffect(() => {
    const duration = 3000; // 3???
    const startTimeMs = Date.now();
    
    const animate = () => {
      const elapsed = Date.now() - startTimeMs;
      const p = Math.min(elapsed / duration, 1);
      setProgress(p);
      
      // ???? (????)
      setBallPos(50 + Math.sin(elapsed / 200) * 30);
      
      // ???
      const ci = Math.min(Math.floor(p * COMMENTARY.length), COMMENTARY.length - 1);
      setCommentary(COMMENTARY[ci]);
      
      // ????
      if (Math.random() < 0.3) {
        setParticles(prev => [...prev.slice(-20), {
          id: Date.now() + Math.random(),
          x: Math.random() * 100,
          y: Math.random() * 100,
          emoji: BALL_EMOJIS[Math.floor(Math.random() * BALL_EMOJIS.length)],
          size: 12 + Math.random() * 16,
          opacity: 0.8,
        }]);
      }
      
      // ????
      setParticles(prev => prev
        .map(p => ({ ...p, opacity: p.opacity - 0.02 }))
        .filter(p => p.opacity > 0)
      );
      
      if (p < 1) {
        frameRef.current = requestAnimationFrame(animate);
      } else {
        setTimeout(() => onComplete && onComplete(), 300);
      }
    };
    
    frameRef.current = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(frameRef.current);
  }, [onComplete]);

  return (
    <div style={{
      position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
      background: 'rgba(0,0,0,0.85)', zIndex: 1000,
      display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      animation: 'fadeIn 0.3s ease',
    }}>
      {/* ??? */}
      <div style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, overflow: 'hidden', pointerEvents: 'none' }}>
        {particles.map(p => (
          <div key={p.id} style={{
            position: 'absolute',
            left: `${p.x}%`, top: `${p.y}%`,
            fontSize: p.size, opacity: p.opacity,
            transition: 'opacity 0.1s',
            transform: `rotate(${Math.random() * 360}deg)`,
          }}>
            {p.emoji}
          </div>
        ))}
      </div>

      {/* ?? */}
      <div style={{
        width: 400, height: 200, background: 'linear-gradient(to right, #1a472a, #2d6a4f, #1a472a)',
        borderRadius: 12, position: 'relative', overflow: 'hidden',
        border: '2px solid rgba(255,255,255,0.2)',
        boxShadow: '0 0 40px rgba(0,200,100,0.3)',
      }}>
        {/* ??? */}
        <div style={{ position: 'absolute', left: '50%', top: 0, bottom: 0, width: 2, background: 'rgba(255,255,255,0.3)' }} />
        <div style={{ position: 'absolute', left: '50%', top: '50%', width: 80, height: 80, border: '2px solid rgba(255,255,255,0.3)', borderRadius: '50%', transform: 'translate(-50%, -50%)' }} />
        
        {/* ? */}
        <div style={{
          position: 'absolute',
          left: `${ballPos}%`, top: '50%',
          transform: 'translate(-50%, -50%)',
          fontSize: 36,
          filter: 'drop-shadow(0 0 10px rgba(255,255,255,0.8))',
          transition: 'left 0.05s linear',
        }}>
          ?
        </div>
        
        {/* ?? */}
        <div style={{ position: 'absolute', left: '20%', top: '30%', fontSize: 20, opacity: 0.7 }}>??</div>
        <div style={{ position: 'absolute', left: '25%', top: '60%', fontSize: 20, opacity: 0.7 }}>??</div>
        <div style={{ position: 'absolute', left: '75%', top: '35%', fontSize: 20, opacity: 0.7 }}>??</div>
        <div style={{ position: 'absolute', left: '80%', top: '65%', fontSize: 20, opacity: 0.7 }}>??</div>
      </div>

      {/* ??? */}
      <div style={{ width: 400, marginTop: 30 }}>
        <div style={{ background: 'rgba(255,255,255,0.1)', borderRadius: 10, height: 8, overflow: 'hidden' }}>
          <div style={{
            width: `${progress * 100}%`, height: '100%',
            background: 'linear-gradient(90deg, var(--green), var(--accent))',
            borderRadius: 10,
            transition: 'width 0.1s linear',
            boxShadow: '0 0 10px var(--green)',
          }} />
        </div>
        
        {/* ??? */}
        <div style={{
          textAlign: 'center', marginTop: 16,
          color: 'var(--fg-body)', fontSize: 16, fontWeight: 'bold',
          textShadow: '0 0 10px rgba(255,255,255,0.5)',
          minHeight: 24,
        }}>
          {commentary}
        </div>
        
        {/* ??? */}
        <div style={{ textAlign: 'center', marginTop: 8, color: 'var(--fg-muted)', fontSize: 14 }}>
          {Math.round(progress * 100)}%
        </div>
      </div>
    </div>
  );
}
