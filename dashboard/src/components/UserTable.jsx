import { useState } from 'react'
import { setBudget, resetUsage } from '../api'

const STATUS = {
  ok:         { cls: 'bg-green-900/40 text-green-400 border border-green-800', label: 'OK' },
  downgraded: { cls: 'bg-amber-900/40 text-amber-400 border border-amber-800', label: 'DOWNGRADED' },
  blocked:    { cls: 'bg-red-900/40  text-red-400  border border-red-800',    label: 'BLOCKED' },
}

const BAR_COLOR = { ok: 'bg-green-400', downgraded: 'bg-amber-400', blocked: 'bg-red-400' }

export default function UserTable({ users, onRefresh }) {
  const [budgetUser,   setBudgetUser]   = useState('')
  const [budgetTokens, setBudgetTokens] = useState('')

  async function handleSetBudget() {
    if (!budgetUser || !budgetTokens) return
    await setBudget(budgetUser, parseInt(budgetTokens))
    setBudgetUser(''); setBudgetTokens('')
    onRefresh()
  }

  async function handleReset(uid) {
    if (!confirm(`Reset usage for ${uid}?`)) return
    await resetUsage(uid)
    onRefresh()
  }

  return (
    <div className="bg-[#141714] border border-[#2a2e29] rounded p-5">
      <p className="font-mono text-[11px] tracking-widest text-[#6b7a6e] uppercase border-b border-[#2a2e29] pb-2 mb-4">
        User budget status
      </p>

      <table className="w-full text-xs font-mono">
        <thead>
          <tr className="text-[#6b7a6e] text-[10px] tracking-widest uppercase">
            <th className="text-left pb-2 pr-4">User</th>
            <th className="text-left pb-2 pr-4">Used / budget</th>
            <th className="text-left pb-2 pr-4">Status</th>
            <th className="text-left pb-2">Action</th>
          </tr>
        </thead>
        <tbody>
          {users.length === 0 && (
            <tr><td colSpan={4} className="text-center py-5 text-[#6b7a6e]">no active users today</td></tr>
          )}
          {users.map(u => {
            const pct = Math.min(u.budget_pct, 100)
            const s   = STATUS[u.status] || STATUS.ok
            return (
              <tr key={u.user_id} className="border-t border-[#1a1e19] hover:bg-[#1c201b]">
                <td className="py-2 pr-4 text-blue-400">{u.user_id}</td>
                <td className="py-2 pr-4 min-w-[160px]">
                  <span className="text-[#e2e8df]">{u.used_tokens.toLocaleString()}</span>
                  <span className="text-[#6b7a6e]"> / {u.budget_tokens.toLocaleString()}</span>
                  <div className="mt-1 h-1 bg-[#1c201b] rounded">
                    <div className={`h-1 rounded ${BAR_COLOR[u.status]}`} style={{ width: `${pct}%` }} />
                  </div>
                </td>
                <td className="py-2 pr-4">
                  <span className={`text-[10px] px-2 py-0.5 rounded ${s.cls}`}>{s.label}</span>
                </td>
                <td className="py-2">
                  <button
                    onClick={() => handleReset(u.user_id)}
                    className="text-[10px] px-2 py-0.5 border border-[#2a2e29] text-[#6b7a6e] rounded hover:bg-[#1c201b]"
                  >RESET</button>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>

      <div className="flex gap-2 mt-4">
        <input
          placeholder="user id"
          value={budgetUser}
          onChange={e => setBudgetUser(e.target.value)}
          className="bg-[#1c201b] border border-[#2a2e29] rounded px-3 py-1.5 text-xs font-mono text-[#e2e8df] w-28 focus:border-green-500 outline-none"
        />
        <input
          type="number"
          placeholder="tokens"
          value={budgetTokens}
          onChange={e => setBudgetTokens(e.target.value)}
          className="bg-[#1c201b] border border-[#2a2e29] rounded px-3 py-1.5 text-xs font-mono text-[#e2e8df] flex-1 focus:border-green-500 outline-none"
        />
        <button
          onClick={handleSetBudget}
          className="bg-green-900/30 border border-green-700 text-green-400 font-mono text-xs px-4 py-1.5 rounded hover:bg-green-900/50"
        >SET</button>
      </div>
    </div>
  )
}