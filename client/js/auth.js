// Session côté client : l'utilisateur connecté (les tokens sont dans des cookies HttpOnly,
// jamais accessibles en JavaScript).
import { api } from './api.js';

let currentUser = null;
const listeners = new Set();

export function getUser() {
  return currentUser;
}

export function setUser(user) {
  currentUser = user;
  listeners.forEach((fn) => fn(user));
}

export function onUserChange(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export async function loadSession() {
  try {
    setUser(await api('/me'));
  } catch {
    setUser(null);
  }
  return currentUser;
}

export async function login(loginName, password) {
  const user = await api('/auth/login', { method: 'POST', json: { login: loginName, password } });
  setUser(user);
  return user;
}

export async function logout() {
  try {
    await api('/auth/logout', { method: 'POST' });
  } finally {
    setUser(null);
  }
}

export const ROLE_LABEL = { user: 'User', artist: 'Artist', admin: 'Admin' };

export function homeFor(role) {
  return { user: '/home', artist: '/artist/tracks', admin: '/admin/artists' }[role] || '/login';
}

// Mémoire courte entre deux écrans d'authentification (email à qui renvoyer le lien, motif de refus)
export const authMemo = {
  set(key, value) { try { sessionStorage.setItem(`musicapp.${key}`, value); } catch { /* stockage indisponible */ } },
  get(key) { try { return sessionStorage.getItem(`musicapp.${key}`); } catch { return null; } },
};
