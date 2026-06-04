const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000/api';
const WS_BASE = import.meta.env.VITE_WS_BASE || 'ws://127.0.0.1:8000/ws';

export { API_BASE as BASE, WS_BASE };

export async function get(url, params = {}) {
  const qs = new URLSearchParams(params).toString();
  const r = await fetch(API_BASE + url + (qs ? '?' + qs : ''));
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}

export async function post(url, body) {
  const r = await fetch(API_BASE + url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}
