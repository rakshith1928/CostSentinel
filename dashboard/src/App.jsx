import { useState, useEffect, useCallback } from 'react'
import { fetchHealth, fetchUsers, fetchUsage, fetchTeams } from './api'
import { useWebSocket } from './hooks/useWebSocket'
import MetricCards from './components/MetricCards'
import UserTable   from './components/UserTable'
import UsageChart  from './components/UsageChart'
import RequestLog  from './components/RequestLog'
import TeamsPanel  from './components/TeamsPanel'

export default function App() {
  const [users,   setUsers]   = useState([])
  const [teams,   setTeams]   = useState([])
  const [history, setHistory] = useState([])
  const [online,  setOnline]  = useState(false)
  const [wsLive,  setWsLive]  = useState(false)
  const [clients, setClients] = useState(0)

  const refresh = useCallback(async () => {
    try {
      const h = await fetchHealth()
      setOnline(h.status === 'ok')
    } catch { setOnline(false) }

    try {
      const { users: u } = await fetchUsers()
      setUsers(u || [])
      const allHistory = []
      for (const user of (u || []).slice(0, 8)) {
        try {
          const d = await fetchUsage(user.user_id)
          ;(d.recent_requests || []).forEach(r => {
            r._user = user.user_id
            allHistory.push(r)
          })
        } catch {}
      }
      allHistory.sort((a, b) => b.ts.localeCompare(a.ts))
      setHistory(allHistory)
    } catch {}

    try {
      const { teams: t } = await fetchTeams()
      setTeams(t || [])
    } catch {}
  }, [])

  const handleEvent = useCallback((event) => {
    if (event.type === 'snapshot') {
      setWsLive(true)
      setClients(event.connected_clients || 1)

      if (event.scope === 'global') {
        // Admin — full picture
        setUsers(event.users || [])
        setTeams(event.teams || [])
      } else if (event.scope === 'team') {
        // Member — only their team's data
        // Map member usage into the same shape as list_users() returns
        const teamUsers = (event.members || []).map(d => ({
          user_id:          d.user_id,
          used_tokens:      d.used_tokens,
          budget_tokens:    d.budget_tokens,
          hard_limit_tokens: d.hard_limit_tokens,
          budget_pct:       d.budget_pct,
          status:           d.status,
        }))
        setUsers(teamUsers)
        setTeams(event.team_detail ? [event.team_detail] : [])
      } else {
        // Fallback — just do a full refresh
        refresh()
      }
      return
    }

    if (event.type === 'request_completed' || event.type === 'request_blocked') {
      setWsLive(true)

      setUsers(prev => {
        const existing = prev.find(u => u.user_id === event.user_id)
        if (existing) {
          return prev.map(u => u.user_id !== event.user_id ? u : {
            ...u,
            used_tokens: event.tokens_used_today ?? u.used_tokens,
            budget_pct:  event.budget_pct        ?? u.budget_pct,
            status:      event.status             ?? u.status,
          })
        }
        refresh()
        return prev
      })

      if (event.type === 'request_completed') {
        setHistory(prev => [{
          ts:             new Date().toISOString(),
          _user:          event.user_id,
          model:          event.model_used,
          original_model: event.original_model,
          total_tokens:   event.total_tokens,
          blocked:        false,
          downgraded:     event.downgraded,
          team:           event.team ?? null,
        }, ...prev].slice(0, 100))

        fetchTeams()
          .then(({ teams: t }) => setTeams(t || []))
          .catch(() => {})
      }
    }
  }, [refresh])

  useWebSocket(handleEvent)
  useEffect(() => { refresh() }, [refresh])

  return (
    <div className="min-h-screen bg-[#0d0f0e] text-[#e2e8df] font-sans">
      <header className="flex items-center justify-between px-7 py-4 border-b border-[#2a2e29] bg-[#141714]">
        <span className="font-mono font-semibold tracking-widest text-green-400">
          COST<span className="text-[#6b7a6e] font-normal">SENTINEL</span>
        </span>
        <div className="flex items-center gap-4 font-mono text-xs text-[#6b7a6e]">
          <span className="flex items-center gap-2">
            <span
              className={`w-2 h-2 rounded-full transition-colors duration-300 ${wsLive ? 'bg-green-400' : 'bg-amber-400'}`}
              style={wsLive ? { boxShadow: '0 0 6px #4ade80' } : {}}
            />
            {wsLive ? `live · ${clients} client${clients !== 1 ? 's' : ''}` : 'connecting…'}
          </span>
          <span className={`w-2 h-2 rounded-full ${online ? 'bg-green-400' : 'bg-red-400'}`} />
          <span>{online ? 'api online' : 'api offline'}</span>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-7 py-6">
        <p className="font-mono text-[10px] tracking-widest text-[#6b7a6e] uppercase mb-3">
          today's overview
        </p>
        <MetricCards users={users} />

        <div className="grid grid-cols-[1fr_1.4fr] gap-4 mb-0">
          <UserTable users={users} onRefresh={refresh} />
          <UsageChart users={users} />
        </div>

        <TeamsPanel teams={teams} onRefresh={refresh} />
        <RequestLog users={users} history={history} />

        <p className="font-mono text-[11px] text-[#6b7a6e] text-right mt-3">
          {wsLive ? '⚡ real-time via websocket' : '⟳ connecting…'}
        </p>
      </main>
    </div>
  )
}