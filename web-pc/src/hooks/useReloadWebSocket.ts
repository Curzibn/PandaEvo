import { useEffect, useRef } from 'react'

const MAX_DELAY_MS = 30000

export function useReloadWebSocket() {
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout>>()
  const wsRef = useRef<WebSocket | null>(null)
  const delayRef = useRef(1000)
  const mountedRef = useRef(true)

  useEffect(() => {
    mountedRef.current = true

    function connect() {
      if (!mountedRef.current) return

      const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
      const ws = new WebSocket(`${protocol}//${location.host}/ws`)
      wsRef.current = ws

      ws.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data) as { type?: string }
          if (data?.type === 'reload') {
            location.reload()
          }
        } catch {
          // ignore parse errors
        }
      }

      ws.onclose = () => {
        wsRef.current = null
        if (!mountedRef.current) return
        reconnectTimeoutRef.current = setTimeout(() => {
          delayRef.current = Math.min(delayRef.current * 2, MAX_DELAY_MS)
          connect()
        }, delayRef.current)
      }

      ws.onopen = () => {
        delayRef.current = 1000
      }
    }

    connect()

    return () => {
      mountedRef.current = false
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
        reconnectTimeoutRef.current = undefined
      }
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
    }
  }, [])
}
