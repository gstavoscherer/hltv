const BASE = '/hltv/api';

export async function fetchApi(path) {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

// CartolaCS API
const CARTOLA_BASE = '/hltv/api/cartola';

export function getToken() {
  return localStorage.getItem('cartola_token');
}

export function setToken(token) {
  localStorage.setItem('cartola_token', token);
}

export function removeToken() {
  localStorage.removeItem('cartola_token');
}

export async function fetchCartola(path, options = {}) {
  const token = getToken();
  const headers = { 'Content-Type': 'application/json', ...options.headers };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const res = await fetch(`${CARTOLA_BASE}${path}`, { ...options, headers });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'API error');
  }
  return res.json();
}
