/**
 * WebSocket client for WS /ws/workflows/{workflow_id}. Connects to the
 * REAL backend socket, parses the real { type, timestamp, payload }
 * envelope, and exposes a plain subscribable pub/sub interface --
 * components/hooks never touch the raw WebSocket.
 *
 * Reconnects automatically with exponential backoff on an unexpected
 * close. The backend replays full history (events, audit entries, then
 * one state_change) on every fresh connect using the SAME four message
 * types as live updates (see backend/api/websocket.py's docstring) rather
 * than a distinct "snapshot" envelope -- so there is no separate snapshot
 * message type to special-case here. Consumers (see useWorkflowStream)
 * distinguish "still catching up on history" from "live" by tracking
 * whether any message has arrived yet, which is what actually matters for
 * the UI (show a loading state vs. a populated one).
 */
import { WS_BASE_URL } from './env'
import type { WsMessage } from '../types/websocket'

export type WsListener = (message: WsMessage) => void
export type ConnectionListener = (connected: boolean) => void

const INITIAL_RECONNECT_DELAY_MS = 1000
const MAX_RECONNECT_DELAY_MS = 15000

export class WorkflowSocket {
  private readonly workflowId: string
  private ws: WebSocket | null = null
  private readonly listeners = new Set<WsListener>()
  private readonly connectionListeners = new Set<ConnectionListener>()
  private shouldReconnect = true
  private reconnectDelay = INITIAL_RECONNECT_DELAY_MS
  private reconnectTimer: number | null = null

  constructor(workflowId: string) {
    this.workflowId = workflowId
  }

  connect(): void {
    this.shouldReconnect = true
    this.open()
  }

  disconnect(): void {
    this.shouldReconnect = false
    if (this.reconnectTimer !== null) {
      window.clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    this.ws?.close()
    this.ws = null
  }

  onMessage(listener: WsListener): () => void {
    this.listeners.add(listener)
    return () => this.listeners.delete(listener)
  }

  onConnectionChange(listener: ConnectionListener): () => void {
    this.connectionListeners.add(listener)
    return () => this.connectionListeners.delete(listener)
  }

  private open(): void {
    const url = `${WS_BASE_URL}/ws/workflows/${encodeURIComponent(this.workflowId)}`
    const ws = new WebSocket(url)
    this.ws = ws

    ws.onopen = () => {
      this.reconnectDelay = INITIAL_RECONNECT_DELAY_MS
      this.connectionListeners.forEach((l) => l(true))
    }

    ws.onmessage = (event: MessageEvent<string>) => {
      let message: WsMessage
      try {
        message = JSON.parse(event.data) as WsMessage
      } catch {
        return // malformed frame -- drop it, never crash the stream
      }
      this.listeners.forEach((l) => l(message))
    }

    ws.onclose = () => {
      this.connectionListeners.forEach((l) => l(false))
      if (this.shouldReconnect) {
        this.reconnectTimer = window.setTimeout(() => this.open(), this.reconnectDelay)
        this.reconnectDelay = Math.min(this.reconnectDelay * 2, MAX_RECONNECT_DELAY_MS)
      }
    }

    ws.onerror = () => {
      ws.close()
    }
  }
}
