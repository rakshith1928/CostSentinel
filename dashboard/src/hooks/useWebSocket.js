import { useEffect, useRef, useCallback } from 'react'
import { fetchWsToken } from '../api'

const BASE_WS = (import.meta.env.VITE_API_URL || 'http://localhost:8000')
  .replace(/^http/, 'ws')

const USER_ID = import.meta.env.VITE_USER_ID || 'admin'

export function useWebSocket(onEvent) {
  const ws        = useRef(null)
  const retryMs   = useRef(1000)
  const unmounted = useRef(false)
  const onEventRef = useRef(onEvent)
  onEventRef.current = onEvent

  const connect = useCallback(async () => {
    if (unmounted.current) return

    // Fetch a fresh short-lived token before every connect / reconnect
    let token = ''
    try {
      const data = await fetchWsToken(USER_ID)
      token = data.token || ''
    } catch {
      // If token fetch fails, retry after backoff
      setTimeout(() => {
        retryMs.current = Math.min(retryMs.current * 2, 30_000)
        connect()
      }, retryMs.current)
      return
    }

    const url    = `${BASE_WS}/ws/feed?token=${encodeURIComponent(token)}`
    const socket = new WebSocket(url)
    ws.current   = socket

    socket.onopen = () => {
      retryMs.current = 1000
    }

    socket.onmessage = (e) => {
      try {
        onEventRef.current(JSON.parse(e.data))
      } catch {}
    }

    socket.onclose = (e) => {
      if (unmounted.current) return
      // 4001 = rejected by server (bad token) — still retry, token may have
      // just expired mid-reconnect, a fresh one will be issued on next attempt
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