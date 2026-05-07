const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export async function fetchHealth()       { return fetch(`${BASE}/health`).then(r => r.json()) }
export async function fetchUsers()        { return fetch(`${BASE}/v1/sentinel/users`).then(r => r.json()) }
export async function fetchUsage(uid)     { return fetch(`${BASE}/v1/sentinel/usage/${uid}`).then(r => r.json()) }
export async function setBudget(uid, tokens) {
  return fetch(`${BASE}/v1/sentinel/budget/${uid}`, {
    method: 'PUT', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tokens }),
  }).then(r => r.json())
}
export async function resetUsage(uid) {
  return fetch(`${BASE}/v1/sentinel/usage/${uid}/reset`, { method: 'DELETE' }).then(r => r.json())
}