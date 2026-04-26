interface Props {
  connected: boolean
  collectedAt: string
}

export function Header({ connected, collectedAt }: Props) {
  const time = collectedAt
    ? new Date(collectedAt).toLocaleTimeString('zh-CN', { hour12: false })
    : '--:--:--'

  return (
    <header className="flex items-center justify-between px-6 py-4 border-b border-border-subtle">
      <div className="flex items-center gap-3">
        <h1 className="text-xl font-semibold tracking-tight text-white">
          BEATLESS
        </h1>
        <span className="text-xs text-gray-500 font-mono">constellation v3</span>
      </div>
      <div className="flex items-center gap-4 text-sm">
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${connected ? 'bg-emerald-400 animate-pulse-dot' : 'bg-red-400'}`} />
          <span className="text-gray-500">{connected ? 'live' : 'disconnected'}</span>
        </div>
        <span className="text-gray-600 font-mono">{time}</span>
      </div>
    </header>
  )
}
