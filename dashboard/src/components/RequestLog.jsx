const STATUS_BADGE = {
  true:  'bg-red-900/40  text-red-400  border border-red-800',
  false: 'bg-green-900/40 text-green-400 border border-green-800',
}

export default function RequestLog({ users, history }) {
  const userMap = Object.fromEntries(users.map(u => [u.user_id, u]))

  return (
    <div className="bg-[#141714] border border-[#2a2e29] rounded p-5 mt-4">
      <p className="font-mono text-[11px] tracking-widest text-[#6b7a6e] uppercase border-b border-[#2a2e29] pb-2 mb-3">
        Recent requests
      </p>
      {history.length === 0 ? (
        <p className="text-[#6b7a6e] font-mono text-xs text-center py-6">
          no requests yet — send one to http://localhost:8000/v1/chat/completions
        </p>
      ) : (
        <div className="space-y-0">
          {history.slice(0, 40).map((r, i) => (
            <div key={i} className="grid grid-cols-[56px_90px_1fr_90px_100px] gap-3 items-center py-2 border-b border-[#1a1e19] font-mono text-xs hover:bg-[#1c201b]">
              <span className="text-[#6b7a6e]">{r.ts.slice(11,19)}</span>
              <span className="text-blue-400 truncate">{r._user}</span>
              <span className="text-[#6b7a6e] truncate">{r.model !== r.original_model ? `${r.model} (was ${r.original_model})` : r.model}</span>
              <span className="text-green-400">+{r.total_tokens.toLocaleString()} tok</span>
              <span className={`text-[10px] px-2 py-0.5 rounded text-center ${r.blocked ? STATUS_BADGE.true : STATUS_BADGE.false}`}>
                {r.blocked ? 'BLOCKED' : r.downgraded ? 'DOWNGRADED' : 'OK'}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}