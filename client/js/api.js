// fetch centralisé : base URL /api, JSON, gestion 401 (renouvellement de session) et 403.
// Le client ne parle qu'à l'API (couche métier), jamais directement à la base de données.

const BASE = '/api';

export class ApiError extends Error {
  constructor(status, code, message, details = {}) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

let refreshing = null;
let onUnauthorized = () => {};

export function setUnauthorizedHandler(fn) {
  onUnauthorized = fn;
}

// Un seul renouvellement à la fois, même si plusieurs requêtes échouent ensemble
export function refreshSession() {
  if (!refreshing) {
    refreshing = fetch(`${BASE}/auth/refresh`, { method: 'POST', credentials: 'same-origin' })
      .then((res) => res.ok)
      .catch(() => false)
      .finally(() => setTimeout(() => { refreshing = null; }, 0));
  }
  return refreshing;
}

async function parse(res) {
  if (res.status === 204) return null;
  const text = await res.text();
  let data = null;
  if (text) {
    try { data = JSON.parse(text); } catch { data = null; }
  }
  if (!res.ok) {
    const err = (data && data.error) || {};
    const message = res.status === 429 && !err.message ? 'Too many requests, please wait a moment.' : err.message;
    throw new ApiError(res.status, err.code || (res.status === 429 ? 'TOO_MANY_REQUESTS' : 'HTTP_ERROR'), message || res.statusText, err);
  }
  return data;
}

function needsRefresh(status, path) {
  return status === 401 && !path.startsWith('/auth/');
}

export async function api(path, { method = 'GET', json, form, signal } = {}, retry = true) {
  const options = { method, credentials: 'same-origin', signal, headers: {} };
  if (json !== undefined) {
    options.headers['Content-Type'] = 'application/json';
    options.body = JSON.stringify(json);
  } else if (form) {
    options.body = form;
  }
  const res = await fetch(BASE + path, options);
  if (retry && needsRefresh(res.status, path)) {
    if (await refreshSession()) return api(path, { method, json, form, signal }, false);
    onUnauthorized();
  }
  return parse(res);
}

// fetch() ne donne pas la progression d'un envoi : XMLHttpRequest + upload.onprogress
export function upload(path, form, { method = 'POST', onProgress } = {}, retry = true) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open(method, BASE + path);
    xhr.withCredentials = true;
    xhr.upload.onprogress = (e) => { if (e.lengthComputable && onProgress) onProgress(e.loaded / e.total); };
    xhr.onerror = () => reject(new ApiError(0, 'NETWORK_ERROR', 'Network error'));
    xhr.onload = async () => {
      if (retry && needsRefresh(xhr.status, path)) {
        if (await refreshSession()) {
          upload(path, form, { method, onProgress }, false).then(resolve, reject);
          return;
        }
        onUnauthorized();
      }
      const res = new Response(xhr.status === 204 ? null : xhr.responseText, { status: xhr.status });
      parse(res).then(resolve, reject);
    };
    xhr.send(form);
  });
}
