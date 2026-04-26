import type { ActivityEvent } from '../types'

interface Props {
  events: ActivityEvent[]
}

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString('zh-CN', {
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    })
  } catch {
    return '--:--'
  }
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
    })
  } catch {
    return ''
  }
}

export function Timeline({ events }: Props) {
  let lastDate = ''

  return (
    <div className="space-y-1">
      <h2 className="text-xs font-medium uppercase tracking-widest text-gray-500 mb-3">
        Activity
      </h2>
      <div className="space-y-0.5 max-h-[480px] overflow-y-auto pr-1">
        {events.map((event, i) => {
          const date = formatDate(event.timestamp)
          const showDate = date !== lastDate
          lastDate = date

          return (
            <div key={i}>
              {showDate && (
                <div className="text-[10px] text-gray-600 font-mono pt-2 pb-1">
                  {date}
                </div>
              )}
              <div className="flex items-start gap-3 px-3 py-2 rounded-md hover:bg-surface-raised transition-colors animate-fade-in">
                <span className="text-[10px] font-mono text-gray-600 mt-0.5 shrink-0 w-10">
                  {formatTime(event.timestamp)}
                </span>
                {event.type === 'commit' ? (
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] font-mono text-accent px-1.5 py-0.5 rounded bg-accent-dim">
                        {event.sha}
                      </span>
                      <span className="text-sm text-gray-300 truncate">{event.message}</span>
                    </div>
                  </div>
                ) : (
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] font-mono text-blue-400 px-1.5 py-0.5 rounded bg-blue-400/10">
                        {event.pipeline}
                      </span>
                      <span className="text-sm text-gray-400">{event.status}</span>
                    </div>
                    {event.detail && (
                      <p className="text-xs text-gray-500 mt-0.5 truncate">{event.detail}</p>
                    )}
                  </div>
                )}
              </div>
            </div>
          )
        })}
        {events.length === 0 && (
          <div className="text-sm text-gray-600 text-center py-8">No recent activity</div>
        )}
      </div>
    </div>
  )
}
