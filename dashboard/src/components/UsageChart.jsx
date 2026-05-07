import {
  BarChart, Bar, XAxis, YAxis, Tooltip,
  ResponsiveContainer, Cell, Legend
} from 'recharts'

const COLORS = ['#4ade80','#60a5fa','#fbbf24','#f87171','#a78bfa','#34d399']

// Custom tooltip — replaces the broken default one
const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div style={{
      background: '#1c201b',
      border: '1px solid #2a2e29',
      borderRadius: 4,
      padding: '8px 12px',
      fontFamily: 'monospace',
      fontSize: 12,
    }}>
      <p style={{ color: '#e2e8df', marginBottom: 4 }}>{label}</p>
      {payload.map((p, i) => (
        <p key={i} style={{ color: p.color || '#6b7a6e', margin: '2px 0' }}>
          {p.name}: {p.value?.toLocaleString()}
        </p>
      ))}
    </div>
  )
}

export default function UsageChart({ users }) {
  const data = users.map(u => ({
    name:      u.user_id,
    used:      Math.min(u.used_tokens, u.budget_tokens),
    remaining: Math.max(0, u.budget_tokens - u.used_tokens),
  }))

  if (data.length === 0) {
    return (
      <div className="bg-[#141714] border border-[#2a2e29] rounded p-5">
        <p className="font-mono text-[11px] tracking-widest text-[#6b7a6e] uppercase border-b border-[#2a2e29] pb-2 mb-4">
          Token usage by user
        </p>
        <p className="text-[#6b7a6e] font-mono text-xs text-center py-10">no data yet</p>
      </div>
    )
  }

  return (
    <div className="bg-[#141714] border border-[#2a2e29] rounded p-5">
      <p className="font-mono text-[11px] tracking-widest text-[#6b7a6e] uppercase border-b border-[#2a2e29] pb-2 mb-4">
        Token usage by user
      </p>

      {/* Fix: explicit pixel height wrapper, not % height */}
      <div style={{ width: '100%', height: 180 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={data}
            barSize={24}
            margin={{ top: 4, right: 8, left: -16, bottom: 0 }}
          >
            <XAxis
              dataKey="name"
              tick={{ fill: '#6b7a6e', fontSize: 11, fontFamily: 'monospace' }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              tick={{ fill: '#6b7a6e', fontSize: 10, fontFamily: 'monospace' }}
              axisLine={false}
              tickLine={false}
              tickFormatter={v => v >= 1000 ? `${(v/1000).toFixed(0)}k` : v}
            />
            <Tooltip
              content={<CustomTooltip />}
              cursor={{ fill: '#2a2e29', opacity: 0.5 }}
            />
            <Bar dataKey="used" stackId="a" name="used" radius={[0, 0, 2, 2]}>
              {data.map((_, i) => (
                <Cell key={i} fill={COLORS[i % COLORS.length] + 'cc'} />
              ))}
            </Bar>
            <Bar
              dataKey="remaining"
              stackId="a"
              name="remaining"
              fill="#1c201b"
              radius={[2, 2, 0, 0]}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}