import { useEffect, useRef, useState } from 'react'
import type { DashboardData } from './types'

const INITIAL: DashboardData = {
  agents: [],
  pipelines: [],
  activity: [],
  experiments: [],
  system: { hermesGateway: false, gpu: null, timestamp: '' },
  collectedAt: '',
}

export function useDashboard() {
  const [data, setData] = useState<DashboardData>(INITIAL)
  const [connected, setConnected] = useState(false)
  const retryRef = useRef(0)

  useEffect(() => {
    fetch('/api/status')
      .then(r => r.json())
      .then(d => { setData(d); setConnected(true) })
      .catch(() => {})

    let es: EventSource | null = null
    function connect() {
      es = new EventSource('/api/events')
      es.onmessage = (e) => {
        try {
          setData(JSON.parse(e.data))
          setConnected(true)
          retryRef.current = 0
        } catch {}
      }
      es.onerror = () => {
        setConnected(false)
        es?.close()
        const delay = Math.min(1000 * 2 ** retryRef.current, 30000)
        retryRef.current++
        setTimeout(connect, delay)
      }
    }
    connect()

    return () => { es?.close() }
  }, [])

  return { data, connected }
}
