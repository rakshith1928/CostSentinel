import { useEffect, useRef, useCallback } from 'react'

const WS_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000')
  .replace(/^http/, 'ws') + '/ws/feed'

export function useWebSocket(onEvent) {
  const ws        = useRef(null)
  const retryMs   = useRef(1000)
  const unmounted = useRef(false)
  const onEventRef = useRef(onEvent)
  onEventRef.current = onEvent

  const connect = useCallback(() => {
    if (unmounted.current) return

    const socket = new WebSocket(WS_URL)
    ws.current = socket

    socket.onopen = () => {
      retryMs.current = 1000   // reset backoff on success
    }

    socket.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data)
        onEventRef.current(data)
      } catch {}
    }

    socket.onclose = () => {
      if (unmounted.current) return
      // Exponential backoff — max 30s
      setTimeout(() => {
        retryMs.current = Math.min(retryMs.current * 2, 30_000)
        connect()
      }, retryMs.current)
    }

    socket.onerror = () => socket.close()
  }, [])

  useEffect(() => {
    unmounted.current = false
    connect()
    return () => {
      unmounted.current = true
      ws.current?.close()
    }
  }, [connect])
}