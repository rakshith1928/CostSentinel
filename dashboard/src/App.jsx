import { useState, useEffect, useCallback } from 'react'
import { fetchHealth, fetchUsers, fetchUsage } from './api'
import MetricCards from './components/MetricCards'
import UserTable   from './components/UserTable'
import UsageChart  from './components/UsageChart'
import RequestLog  from './components/RequestLog'

export default function App() {
  const [users,   setUsers]   = useState([])
  const [history, setHistory] = useState([])
  const [status,  setStatus]  = useState('connecting…')
  const [online,  setOnline]  = useState(false)
  const [lastRefresh, setLastRefresh] = useState('')

  const refresh = useCallback(async () => {
    try {
      const h = await fetchHealth()
      setOnline(h.status === 'ok')
      setStatus(h.status === 'ok' ? 'online' : 'degraded')
    } catch { setOnline(false); setStatus('offline') }

    try {
      const { users: u } = await fetchUsers()
      setUsers(u || [])

      const allHistory = []
      for (const user of (u || []).slice(0, 8)) {
        try {
          const d = await fetchUsage(user.user_id)
          ;(d.recent_requests || []).forEach(r => { r._user = user.user_id; allHistory.push(r) })
        } catch {}
      }
      allHistory.sort((a, b) => b.ts.localeCompare(a.ts))
      setHistory(allHistory)
    } catch {}

    setLastRefresh(new Date().toLocaleTimeString())
  }, [])

  useEffect(() => { refresh(); const id = setInterval(refresh, 5000); return () => clearInterval(id) }, [refresh])

  return (
    <div className="min-h-screen bg-[#0d0f0e] text-[#e2e8df] font-sans">
      {/* Header */}
      <header className="flex items-center justify-between px-7 py-4 border-b border-[#2a2e29] bg-[#141714]">
        <span className="font-mono font-semibold tracking-widest text-green-400">
          COST<span className="text-[#6b7a6e] font-normal">SENTINEL</span>
        </span>
        <div className="flex items-center gap-4 font-mono text-xs text-[#6b7a6e]">
          <span className="flex items-center gap-2">
            <span className={`w-2 h-2 rounded-full ${online ? 'bg-green-400' : 'bg-red-400'}`} style={online ? {boxShadow:'0 0 6px #4ade80'} : {}} />
            {status}
          </span>
          <span>{new Date().toUTCString().slice(5,25).replace('GMT','UTC')}</span>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-7 py-6">
        <p className="font-mono text-[10px] tracking-widest text-[#6b7a6e] uppercase mb-3">today's overview</p>
        <MetricCards users={users} />

        <div className="grid grid-cols-[1fr_1.4fr] gap-4 mb-0">
          <UserTable users={users} onRefresh={refresh} />
          <UsageChart users={users} />
        </div>

        <RequestLog users={users} history={history} />

        <p className="font-mono text-[11px] text-[#6b7a6e] text-right mt-3">
          last refreshed {lastRefresh} · auto-refresh every 5s
        </p>
      </main>
    </div>
  )
}