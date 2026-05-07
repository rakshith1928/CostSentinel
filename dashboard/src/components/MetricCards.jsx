export default function MetricCards({ users }) {
  const total      = users.reduce((s, u) => s + u.used_tokens, 0)
  const downgraded = users.filter(u => u.status === 'downgraded').length
  const blocked    = users.filter(u => u.status === 'blocked').length

  const cards = [
    { label: 'Total tokens used',  value: total >= 1000 ? `${(total/1000).toFixed(1)}k` : total, color: 'text-green-400' },
    { label: 'Active users',       value: users.length,  color: 'text-blue-400' },
    { label: 'Downgraded',         value: downgraded,    color: 'text-amber-400' },
    { label: 'Blocked',            value: blocked,       color: 'text-red-400' },
  ]

  return (
    <div className="grid grid-cols-4 gap-3 mb-6">
      {cards.map(c => (
        <div key={c.label} className="bg-[#141714] border border-[#2a2e29] rounded p-4">
          <p className="text-[10px] tracking-widest text-[#6b7a6e] uppercase mb-2">{c.label}</p>
          <p className={`font-mono text-2xl font-semibold ${c.color}`}>{c.value}</p>
        </div>
      ))}
    </div>
  )
}