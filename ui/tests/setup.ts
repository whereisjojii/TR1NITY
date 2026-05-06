import "@testing-library/jest-dom/vitest";

// jsdom doesn't ship with WebSocket; tests that need it provide their own stub.
class _StubWebSocket {
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSING = 2;
  static readonly CLOSED = 3;
  url: string;
  readyState = _StubWebSocket.CONNECTING;
  constructor(url: string) {
    this.url = url;
  }
  addEventListener(): void {}
  removeEventListener(): void {}
  send(): void {}
  close(): void {
    this.readyState = _StubWebSocket.CLOSED;
  }
}

if (typeof globalThis.WebSocket === "undefined") {
  // @ts-expect-error -- node test runtime polyfill
  globalThis.WebSocket = _StubWebSocket;
}
