const BASE = 'http://127.0.0.1:8000/api';

export async function get(url, params = {}) {
  const qs = new URLSearchParams(params).toString();
  const r = await fetch(BASE + url + (qs ? '?' + qs : ''));
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}

export async function post(url, body) {
  const r = await fetch(BASE + url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}
