import type { ClientFrame, ServerEvent } from "@/types/realtime";

const PING_INTERVAL_MS = 25_000; // keeps proxies from dropping an idle socket
const MAX_BACKOFF_MS = 30_000;
const UNAUTHORIZED_CLOSE_CODE = 4401;

type Handlers = {
  onEvent: (event: ServerEvent) => void;
  onReconnect: () => void; // after a drop: refetch what was missed
  onUnauthorized: () => void;
};

/**
 * One WebSocket per tab to `${wsUrl}/ws?token=...`. Reconnects with exponential backoff
 * (1s, 2s, 4s ... 30s, with jitter so many clients don't retry in lockstep).
 */
export class RealtimeClient {
  private socket: WebSocket | null = null;
  private stopped = true;
  private attempts = 0;
  private connectedBefore = false;
  private pingTimer: ReturnType<typeof setInterval> | null = null;
  private retryTimer: ReturnType<typeof setTimeout> | null = null;

  constructor(
    private readonly wsUrl: string,
    private readonly token: string,
    private readonly handlers: Handlers,
  ) {}

  start(): void {
    this.stopped = false;
    this.open();
  }

  stop(): void {
    this.stopped = true;
    this.clearTimers();
    this.socket?.close(1000);
    this.socket = null;
  }

  send(frame: ClientFrame): void {
    if (this.socket?.readyState === WebSocket.OPEN) this.socket.send(JSON.stringify(frame));
  }

  private open(): void {
    const socket = new WebSocket(`${this.wsUrl}/ws?token=${encodeURIComponent(this.token)}`);
    this.socket = socket;

    socket.onopen = () => {
      this.attempts = 0;
      if (this.connectedBefore) this.handlers.onReconnect();
      this.connectedBefore = true;
      this.pingTimer = setInterval(() => this.send({ type: "ping", payload: {} }), PING_INTERVAL_MS);
    };
    socket.onmessage = (message: MessageEvent<string>) => {
      try {
        this.handlers.onEvent(JSON.parse(message.data) as ServerEvent);
      } catch {
        // Ignore a malformed frame rather than breaking the connection.
      }
    };
    socket.onclose = (event) => {
      this.clearTimers();
      if (this.socket === socket) this.socket = null;
      if (event.code === UNAUTHORIZED_CLOSE_CODE) {
        this.stopped = true;
        this.handlers.onUnauthorized();
      } else if (!this.stopped) {
        this.scheduleReconnect();
      }
    };
  }

  private scheduleReconnect(): void {
    const base = Math.min(MAX_BACKOFF_MS, 1000 * 2 ** this.attempts);
    this.attempts += 1;
    const jittered = base * (0.8 + Math.random() * 0.4);
    this.retryTimer = setTimeout(() => !this.stopped && this.open(), jittered);
  }

  private clearTimers(): void {
    if (this.pingTimer) clearInterval(this.pingTimer);
    if (this.retryTimer) clearTimeout(this.retryTimer);
    this.pingTimer = null;
    this.retryTimer = null;
  }
}

/** The tab's active client, so components (e.g. the composer) can send typing frames. */
let active: RealtimeClient | null = null;

export function setActiveRealtimeClient(client: RealtimeClient | null): void {
  active = client;
}

export function sendRealtime(frame: ClientFrame): void {
  active?.send(frame);
}
