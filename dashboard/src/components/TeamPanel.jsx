import { useState } from 'react'

const STATUS = {
  ok:         { cls: 'bg-green-900/40 text-green-400 border border-green-800', label: 'OK' },
  downgraded: { cls: 'bg-amber-900/40 text-amber-400 border border-amber-800', label: 'DOWNGRADED' },
  blocked:    { cls: 'bg-red-900/40  text-red-400  border border-red-800',    label: 'BLOCKED' },
}
const BAR = { ok: 'bg-green-400', downgraded: 'bg-amber-400', blocked: 'bg-red-400' }
const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export default function TeamsPanel({ teams, onRefresh }) {
  const [newTeam,   setNewTeam]   = useState('')
  const [newTokens, setNewTokens] = useState('')
  const [newMember, setNewMember] = useState('')
  const [addTo,     setAddTo]     = useState('')
  const [expanded,  setExpanded]  = useState(null)

  async function createTeam() {
    if (!newTeam || !newTokens) return
    await fetch(`${BASE}/v1/sentinel/teams/${newTeam}/budget`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tokens: parseInt(newTokens) }),
    })
    setNewTeam(''); setNewTokens('')
    onRefresh()
  }

  async function addMember(team) {
    if (!newMember) return
    await fetch(`${BASE}/v1/sentinel/teams/${team}/members`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: newMember }),
    })
    setNewMember(''); setAddTo('')
    onRefresh()
  }

  async function removeMember(team, uid) {
    await fetch(`${BASE}/v1/sentinel/teams/${team}/members/${uid}`, { method: 'DELETE' })
    onRefresh()
  }

  async function resetTeam(team) {
    if (!confirm(`Reset usage for team ${team}?`)) return
    await fetch(`${BASE}/v1/sentinel/teams/${team}/reset`, { method: 'DELETE' })
    onRefresh()
  }

  return (
    <div className="bg-[#141714] border border-[#2a2e29] rounded p-5 mt-4">
      <p className="font-mono text-[11px] tracking-widest text-[#6b7a6e] uppercase border-b border-[#2a2e29] pb-2 mb-4">
        Team budget pools
      </p>

      {teams.length === 0 && (
        <p className="text-[#6b7a6e] font-mono text-xs text-center py-4 mb-4">
          no teams yet — create one below
        </p>
      )}

      {/* Team rows */}
      <div className="space-y-3 mb-4">
        {teams.map(t => {
          const s   = STATUS[t.status] || STATUS.ok
          const pct = Math.min(t.budget_pct, 100)
          const isOpen = expanded === t.team
          return (
            <div key={t.team} className="border border-[#2a2e29] rounded overflow-hidden">
              {/* Header row */}
              <div
                className="flex items-center gap-3 px-4 py-3 cursor-pointer hover:bg-[#1c201b]"
                onClick={() => setExpanded(isOpen ? null : t.team)}
              >
                <span className="font-mono text-xs text-green-400 font-medium min-w-[80px]">
                  {t.team}
                </span>
                <div className="flex-1">
                  <div className="flex justify-between font-mono text-xs mb-1">
                    <span className="text-[#e2e8df]">{t.used_tokens.toLocaleString()}</span>
                    <span className="text-[#6b7a6e]">{t.budget_tokens.toLocaleString()} tok</span>
                  </div>
                  <div className="h-1 bg-[#1c201b] rounded">
                    <div className={`h-1 rounded ${BAR[t.status]}`} style={{ width: `${pct}%` }} />
                  </div>
                </div>
                <span className={`text-[10px] px-2 py-0.5 rounded font-mono ${s.cls}`}>{s.label}</span>
                <span className="text-[#6b7a6e] font-mono text-[10px]">{t.members.length} members</span>
                <span className="text-[#6b7a6e] text-xs ml-auto">{isOpen ? '▲' : '▼'}</span>
              </div>

              {/* Expanded detail */}
              {isOpen && (
                <div className="border-t border-[#2a2e29] bg-[#0d0f0e] px-4 py-3">
                  {/* Members list */}
                  <p className="font-mono text-[10px] text-[#6b7a6e] uppercase tracking-widest mb-2">
                    Members
                  </p>
                  <div className="flex flex-wrap gap-2 mb-3">
                    {t.members.length === 0 && (
                      <span className="font-mono text-xs text-[#6b7a6e]">no members yet</span>
                    )}
                    {t.members.map(uid => (
                      <span
                        key={uid}
                        className="flex items-center gap-2 bg-[#1c201b] border border-[#2a2e29] rounded px-2 py-1 font-mono text-xs text-blue-400"
                      >
                        {uid}
                        <button
                          onClick={() => removeMember(t.team, uid)}
                          className="text-[#6b7a6e] hover:text-red-400 text-[10px]"
                        >✕</button>
                      </span>
                    ))}
                  </div>

                  {/* Add member form */}
                  <div className="flex gap-2 mb-3">
                    <input
                      placeholder="user id to add"
                      value={addTo === t.team ? newMember : ''}
                      onChange={e => { setAddTo(t.team); setNewMember(e.target.value) }}
                      className="bg-[#1c201b] border border-[#2a2e29] rounded px-3 py-1 text-xs font-mono text-[#e2e8df] flex-1 focus:border-green-500 outline-none"
                    />
                    <button
                      onClick={() => addMember(t.team)}
                      className="bg-green-900/30 border border-green-700 text-green-400 font-mono text-xs px-3 py-1 rounded hover:bg-green-900/50"
                    >ADD</button>
                  </div>

                  {/* Reset button */}
                  <button
                    onClick={() => resetTeam(t.team)}
                    className="font-mono text-[10px] px-3 py-1 border border-[#2a2e29] text-[#6b7a6e] rounded hover:bg-[#1c201b]"
                  >RESET USAGE</button>
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* Create team form */}
      <div className="border-t border-[#2a2e29] pt-3">
        <p className="font-mono text-[10px] text-[#6b7a6e] uppercase tracking-widest mb-2">
          Create team
        </p>
        <div className="flex gap-2">
          <input
            placeholder="team name (e.g. eng)"
            value={newTeam}
            onChange={e => setNewTeam(e.target.value)}
            className="bg-[#1c201b] border border-[#2a2e29] rounded px-3 py-1.5 text-xs font-mono text-[#e2e8df] flex-1 focus:border-green-500 outline-none"
          />
          <input
            type="number"
            placeholder="pool tokens"
            value={newTokens}
            onChange={e => setNewTokens(e.target.value)}
            className="bg-[#1c201b] border border-[#2a2e29] rounded px-3 py-1.5 text-xs font-mono text-[#e2e8df] w-36 focus:border-green-500 outline-none"
          />
          <button
            onClick={createTeam}
            className="bg-green-900/30 border border-green-700 text-green-400 font-mono text-xs px-4 py-1.5 rounded hover:bg-green-900/50"
          >CREATE</button>
        </div>
      </div>
    </div>
  )
}