import { StrictMode, Component } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'

class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }
  static getDerivedStateFromError(error) {
    return { error };
  }
  render() {
    if (this.state.error) {
      return (
        <div style={{ color: '#f85149', padding: 24, fontFamily: 'monospace', fontSize: 14, whiteSpace: 'pre-wrap', background: '#0d1117', minHeight: '100vh' }}>
          <div style={{ fontSize: 18, marginBottom: 12 }}>React Error:</div>
          <div>{this.state.error.message}</div>
          <div style={{ marginTop: 8, color: '#8b949e', fontSize: 12 }}>{this.state.error.stack}</div>
        </div>
      );
    }
    return this.props.children;
  }
}

const root = createRoot(document.getElementById('root'));
root.render(
  <StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </StrictMode>,
);

window.addEventListener('error', (e) => {
  const el = document.getElementById('root');
  if (el && (!el.textContent || el.textContent.trim().length < 10)) {
    el.style.cssText = 'color:#f85149;padding:24px;font-family:monospace;font-size:14px;white-space:pre-wrap;background:#0d1117;min-height:100vh';
    el.innerHTML = '<b>Runtime Error:</b><br/>' + e.message + '<br/><span style="color:#8b949e">' + e.filename + ':' + e.lineno + '</span>';
  }
});
window.addEventListener('unhandledrejection', (e) => {
  const el = document.getElementById('root');
  if (el && (!el.textContent || el.textContent.trim().length < 10)) {
    el.style.cssText = 'color:#f85149;padding:24px;font-family:monospace;font-size:14px;white-space:pre-wrap;background:#0d1117;min-height:100vh';
    el.innerHTML = '<b>Unhandled Promise Rejection:</b><br/>' + (e.reason?.message || e.reason || 'Unknown');
  }
});
