const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const KEY  = import.meta.env.VITE_API_KEY || ''

const headers = () => ({
  'Content-Type': 'application/json',
  ...(KEY ? { 'X-API-Key': KEY } : {}),
})

export async function fetchHealth()   { return fetch(`${BASE}/health`).then(r => r.json()) }
export async function fetchUsers()    { return fetch(`${BASE}/v1/sentinel/users`,   { headers: headers() }).then(r => r.json()) }
export async function fetchTeams()    { return fetch(`${BASE}/v1/sentinel/teams`,   { headers: headers() }).then(r => r.json()) }
export async function fetchUsage(uid) { return fetch(`${BASE}/v1/sentinel/usage/${uid}`, { headers: headers() }).then(r => r.json()) }

export async function fetchWsToken(user_id) {
  return fetch(`${BASE}/v1/sentinel/auth/ws-token`, {
    method:  'POST',
    headers: headers(),
    body:    JSON.stringify({ user_id }),
  }).then(r => r.json())
}

export async function setBudget(uid, tokens) {
  return fetch(`${BASE}/v1/sentinel/budget/${uid}`, {
    method: 'PUT', headers: headers(),
    body: JSON.stringify({ tokens }),
  }).then(r => r.json())
}

export async function resetUsage(uid) {
  return fetch(`${BASE}/v1/sentinel/usage/${uid}/reset`, {
    method: 'DELETE', headers: headers(),
  }).then(r => r.json())
}

export { BASE }  // ← export so useWebSocket can build the WS URL