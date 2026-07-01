(() => {
  window.__strikleContentScriptVersion = "2.1.0";

  // ws_hook.js 现在由 manifest 以 world:"MAIN" + run_at:"document_start"
  // 原生注入到页面上下文，既绕开了页面CSP对 chrome-extension: 脚本的拦截，
  // 又由浏览器保证在页面自身脚本创建WebSocket之前完成hook（消除注入时机竞态）。

  let analyzer = null;
  let pendingState = null;
  let myPlayerId = null;
  let lastRound = null;
  let mode = "assist"; // "assist" 提示弗 | "auto" 自动弗
  let awaitingResult = false;

  // 用不含"panel/helper/ad"等敏感词的宿主元素+Shadow DOM，
  // 让内部结构对页面级/浏览器广告拦截的CSS选择器规则不可见，避免被误判成广告浮层
  const host = document.createElement("div");
  host.id = "csgpx-" + Math.random().toString(36).slice(2, 10);
  host.style.all = "initial";
  const shadow = host.attachShadow({ mode: "open" });

  const styleLink = document.createElement("link");
  styleLink.rel = "stylesheet";
  styleLink.href = chrome.runtime.getURL("panel.css");
  shadow.appendChild(styleLink);

  const panel = document.createElement("div");
  panel.id = "strikle-helper-panel";
  panel.innerHTML = `
    <div id="strikle-helper-header">
      <span id="strikle-helper-logo">弗</span>
      <span id="strikle-helper-title">弗一把助手</span>
      <button id="strikle-helper-collapse" title="折叠 / 展开">–</button>
    </div>
    <div id="strikle-helper-mode-switch">
      <button id="strikle-mode-assist" class="strikle-mode-btn active">提示弗</button>
      <button id="strikle-mode-auto" class="strikle-mode-btn">自动弗</button>
    </div>
    <div id="strikle-helper-status" class="strikle-status-waiting">
      <span id="strikle-status-dot"></span>
      <span id="strikle-status-text">等待对局开始...</span>
    </div>
    <div id="strikle-helper-body">
      <div class="strikle-row-label">建议猜测</div>
      <div id="strikle-helper-suggestion" class="strikle-idle">-</div>
      <div id="strikle-helper-remaining"></div>
    </div>
  `;
  shadow.appendChild(panel);

  // 折叠 / 展开
  const collapseBtn = panel.querySelector("#strikle-helper-collapse");
  collapseBtn.addEventListener("click", () => {
    const collapsed = panel.classList.toggle("strikle-collapsed");
    collapseBtn.textContent = collapsed ? "+" : "–";
  });

  // 拖动标题栏可移动面板
  const header = panel.querySelector("#strikle-helper-header");
  let dragging = false;
  let dragOffsetX = 0;
  let dragOffsetY = 0;
  header.addEventListener("mousedown", (e) => {
    if (e.target === collapseBtn) return;
    dragging = true;
    const rect = panel.getBoundingClientRect();
    dragOffsetX = e.clientX - rect.left;
    dragOffsetY = e.clientY - rect.top;
    e.preventDefault();
  });
  window.addEventListener("mousemove", (e) => {
    if (!dragging) return;
    panel.style.left = e.clientX - dragOffsetX + "px";
    panel.style.top = e.clientY - dragOffsetY + "px";
    panel.style.right = "auto";
  });
  window.addEventListener("mouseup", () => { dragging = false; });

  function mountPanel() {
    if (!document.body) return;
    if (host.parentElement !== document.body) {
      document.body.appendChild(host);
    }
  }

  // 页面用React做SSR+hydration，若面板过早插入document.body会导致
  // hydration时DOM结构对不上（React错误#418/#423），页面甚至可能整体重建。
  // 这里等hydration大概率完成后（load事件之后再延迟一小段）才开始挂载和监控。
  function startMounting() {
    mountPanel();
    new MutationObserver(mountPanel).observe(document.documentElement, {
      childList: true,
      subtree: true,
    });
  }

  if (document.readyState === "complete") {
    setTimeout(startMounting, 1000);
  } else {
    window.addEventListener("load", () => setTimeout(startMounting, 1000));
  }

  panel.addEventListener("click", (event) => {
    if (event.target.id === "strikle-mode-assist") setMode("assist");
    else if (event.target.id === "strikle-mode-auto") setMode("auto");
  });

  function setMode(newMode) {
    mode = newMode;
    const assistBtn = panel.querySelector("#strikle-mode-assist");
    const autoBtn = panel.querySelector("#strikle-mode-auto");
    if (assistBtn) assistBtn.classList.toggle("active", mode === "assist");
    if (autoBtn) autoBtn.classList.toggle("active", mode === "auto");
  }

  // state: "normal" 建议猜测 | "win" 命中 | "idle" 等待/计算中 | "error" 出错/无候选
  function updatePanel(round, suggestion, remaining, state = "normal") {
    // 面板可能正处于被SPA框架移除、还未被MutationObserver重新挂载的瞬间，直接查子元素更保险
    const statusEl = panel.querySelector("#strikle-helper-status");
    const statusTextEl = panel.querySelector("#strikle-status-text");
    const suggestionEl = panel.querySelector("#strikle-helper-suggestion");
    const remainingEl = panel.querySelector("#strikle-helper-remaining");
    if (!statusEl || !statusTextEl || !suggestionEl || !remainingEl) return;
    statusTextEl.textContent = round;
    statusEl.className =
      state === "error" ? "strikle-status-error" :
      state === "normal" || state === "win" ? "strikle-status-active" :
      "strikle-status-waiting";
    suggestionEl.textContent = suggestion;
    suggestionEl.className =
      state === "win" ? "strikle-win" :
      state === "idle" ? "strikle-idle" :
      state === "error" ? "strikle-error" :
      "";
    remainingEl.textContent = remaining;
  }

  function resetRound() {
    analyzer.reset();
    awaitingResult = false;
  }

  function applyGuesses(guesses) {
    for (let i = analyzer.guessHistory.length; i < guesses.length; i++) {
      const g = guesses[i];
      analyzer.submitFeedback({
        nickname: g.nickname,
        nationality: g.nationality,
        team: g.team,
        age: g.age,
        majorAppearances: g.majorAppearances,
        role: g.role,
      });
    }
    awaitingResult = false;
  }

  function sendGuess(playerId) {
    const payload = JSON.stringify({
      type: "GUESS",
      payload: { playerId, connectionId: "" },
    });
    window.postMessage({ __strikleSend: true, data: payload }, "*");
    awaitingResult = true;
  }

  function handleState(state) {
    if (!state || state.phase !== "game") return;
    if (!analyzer) {
      pendingState = state;
      return;
    }

    if (myPlayerId === null && state.meta && state.meta.userId) {
      myPlayerId = state.meta.userId;
    }
    if (myPlayerId === null) return;

    const currentRound = state.meta.currentRound;
    if (currentRound !== lastRound) {
      lastRound = currentRound;
      resetRound();
      updatePanel(`第${currentRound}轮`, "计算中…", "", "idle");
    }

    const me = (state.players || []).find((p) => p.id === myPlayerId);
    if (!me) return;

    const myGuesses = me.guesses || [];
    if (myGuesses.length !== analyzer.guessHistory.length) {
      applyGuesses(myGuesses);
    }

    if (myGuesses.length && myGuesses[myGuesses.length - 1].isSuccess) {
      updatePanel(`第${currentRound}轮`, `✅ 命中 ${myGuesses[myGuesses.length - 1].nickname}`, "", "win");
      return;
    }

    if (analyzer.possiblePlayers.length === 0) {
      updatePanel(`第${currentRound}轮`, "无候选选手", "", "error");
      return;
    }

    if (awaitingResult) return; // 上一次猜测的反馈还没到，先不重复猜

    const guess = analyzer.chooseNextGuess();
    if (!guess) return;

    updatePanel(`第${currentRound}轮`, guess.nickname, `🎯 剩余候选 ${analyzer.possiblePlayers.length}`, "normal");

    if (mode === "auto") {
      sendGuess(guess.id);
    }
  }

  window.addEventListener("message", (event) => {
    if (event.source !== window) return;
    const msg = event.data;
    if (!msg || !msg.__strikleFeed || msg.direction !== "in") return;

    let data;
    try {
      data = JSON.parse(msg.data);
    } catch {
      return;
    }
    if (data && "phase" in data) handleState(data);
  });

  fetch(chrome.runtime.getURL("players_data.json"))
    .then((res) => res.json())
    .then((players) => {
      analyzer = new CSPlayerAnalyzer(players);
      if (pendingState) {
        const state = pendingState;
        pendingState = null;
        handleState(state);
      }
    });
})();
