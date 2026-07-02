(() => {
  window.__strikleWebSocketHookVersion = "2.1.0";

  if (window.__strikleWebSocketHooked) return;
  window.__strikleWebSocketHooked = true;

  const NativeWebSocket = window.WebSocket;
  let gameSocket = null;

  function isGameSocketUrl(url) {
    const value = typeof url === "string" ? url : String(url);
    return value.includes("minigames-ws.blast.tv/parties/game/");
  }

  function HookedWebSocket(url, protocols) {
    const ws = protocols === undefined
      ? new NativeWebSocket(url)
      : new NativeWebSocket(url, protocols);

    if (isGameSocketUrl(url)) {
      gameSocket = ws;

      ws.addEventListener("message", (event) => {
        window.postMessage({ __strikleFeed: true, direction: "in", data: event.data }, "*");
      });

      ws.addEventListener("close", () => {
        if (gameSocket === ws) gameSocket = null;
      });
    }

    return ws;
  }

  HookedWebSocket.prototype = NativeWebSocket.prototype;
  Object.setPrototypeOf(HookedWebSocket, NativeWebSocket);

  for (const key of ["CONNECTING", "OPEN", "CLOSING", "CLOSED"]) {
    Object.defineProperty(HookedWebSocket, key, {
      configurable: true,
      enumerable: true,
      value: NativeWebSocket[key],
    });
  }

  window.WebSocket = HookedWebSocket;

  window.addEventListener("message", (event) => {
    if (event.source !== window) return;
    const msg = event.data;
    if (!msg || !msg.__strikleSend) return;
    if (gameSocket && gameSocket.readyState === NativeWebSocket.OPEN) {
      gameSocket.send(msg.data);
    }
  });
})();
