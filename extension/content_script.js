(() => {
  window.__strikleContentScriptVersion = "3.0.0";

  // ws_hook.js 现在由 manifest 以 world:"MAIN" + run_at:"document_start"
  // 原生注入到页面上下文，既绕开了页面CSP对 chrome-extension: 脚本的拦截，
  // 又由浏览器保证在页面自身脚本创建WebSocket之前完成hook（消除注入时机竞态）。
  //
  // 注意：manifest 的 matches 同时覆盖大厅页 /multiplayer 和房间页 /multiplayer/*。
  // 原因：从大厅「创建房间」是 SPA 客户端路由跳转（pushState，无文档重载），
  // content script 不会二次注入；只匹配 /multiplayer/* 会导致「自己建房→加入」时
  // 插件不出现、必须刷新。让脚本在大厅页就注入，WebSocket hook 提前就位，
  // 之后 SPA 跳进房间新建的游戏连接依然会被 hook 捕获。

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
      <img id="strikle-helper-logo" src="${chrome.runtime.getURL("icon.png")}" alt="玩机器 machine" />
      <span id="strikle-helper-title">弗一把小助手</span>
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
    <div id="strikle-helper-db">
      <button id="strikle-db-update" title="猜不到选手时，一键从官方重新抓取选手数据库">
        ⟳ 更新选手库
      </button>
      <span id="strikle-db-status"></span>
    </div>
    <div id="strikle-helper-meme" title="点击复制 · 来自 sb6657.cn 玩机器直播间">
      <span id="strikle-meme-icon">🎤</span>
      <span id="strikle-meme-text">6657 烂梗加载中…</span>
      <button id="strikle-meme-refresh" title="换一条">⟳</button>
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
    const id = event.target.id || (event.target.closest("button") || {}).id;
    if (id === "strikle-mode-assist") setMode("assist");
    else if (id === "strikle-mode-auto") setMode("auto");
    else if (id === "strikle-db-update") updateDatabase();
    else if (id === "strikle-meme-refresh") loadMeme();
    else if (event.target.closest("#strikle-helper-meme")) copyMeme();
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

  // ---- 手动更新选手数据库 ---- //
  // 当出现「猜不到的新选手」时，用户点一下就从官方 API 重新抓全量选手，
  // 结果存进 chrome.storage.local，之后长期生效（下次进房自动读新库）。
  const STORAGE_KEY = "players_data";
  const API_PLAYERS = "https://api.blast.tv/v1/counterstrikle/multiplayer/players?difficulty=pro";
  const API_GUESSES = "https://api.blast.tv/v1/counterstrikle/guesses";
  let updating = false;

  function setDbStatus(text, kind = "") {
    const el = panel.querySelector("#strikle-db-status");
    if (el) {
      el.textContent = text;
      el.className = kind; // "" | "ok" | "err" | "busy"
    }
  }

  // 抓单个选手详情，抽取与 players_data.json 一致的字段
  async function fetchPlayerDetail(id) {
    const res = await fetch(API_GUESSES, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ playerId: id, timestamp: new Date().toISOString() }),
    });
    if (!res.ok) throw new Error(`guesses ${res.status}`);
    const d = await res.json();
    return {
      id: d.id,
      nickname: d.nickname,
      firstName: d.firstName,
      lastName: d.lastName,
      isRetired: d.isRetired,
      nationality: d.nationality ? d.nationality.value : null,
      team: d.team && d.team.data ? d.team.data.name : null,
      age: d.age ? d.age.value : null,
      majorAppearances: d.majorAppearances ? d.majorAppearances.value : null,
      role: d.role ? d.role.value : null,
    };
  }

  async function updateDatabase() {
    if (updating) return;
    updating = true;
    const btn = panel.querySelector("#strikle-db-update");
    if (btn) btn.disabled = true;

    try {
      setDbStatus("获取列表…", "busy");
      const listRes = await fetch(API_PLAYERS, { headers: { Accept: "application/json" } });
      if (!listRes.ok) throw new Error(`players ${listRes.status}`);
      const list = await listRes.json();

      // 按 id 去重
      const ids = [...new Set(list.map((p) => p.id).filter(Boolean))];
      const total = ids.length;
      if (!total) throw new Error("空列表");

      // 小批量并发 + 批间停顿，既快又不至于触发限流
      const BATCH = 6;
      const players = [];
      for (let i = 0; i < total; i += BATCH) {
        const chunk = ids.slice(i, i + BATCH);
        const results = await Promise.allSettled(chunk.map(fetchPlayerDetail));
        for (const r of results) {
          if (r.status === "fulfilled" && r.value.id) players.push(r.value);
        }
        setDbStatus(`抓取中 ${Math.min(i + BATCH, total)}/${total}`, "busy");
        if (i + BATCH < total) await new Promise((r) => setTimeout(r, 250));
      }

      if (!players.length) throw new Error("未抓到任何选手");

      await chrome.storage.local.set({ [STORAGE_KEY]: players });
      analyzer = new CSPlayerAnalyzer(players); // 立即热更新当前分析器
      setDbStatus(`✓ 已更新 ${players.length} 人`, "ok");
    } catch (err) {
      setDbStatus(`✗ 更新失败：${err.message}`, "err");
    } finally {
      updating = false;
      if (btn) btn.disabled = false;
    }
  }

  // ---- 玩机器直播间烂梗（联动 sb6657.cn，纯彩蛋，失败静默） ---- //
  const MEME_URL = "https://hguofichp.cn:10086/machine/getRandOne";
  let currentMeme = "";
  let memeLoading = false;

  async function loadMeme() {
    if (memeLoading) return;
    memeLoading = true;
    const textEl = panel.querySelector("#strikle-meme-text");
    try {
      const res = await fetch(MEME_URL, { headers: { Accept: "application/json" } });
      const json = await res.json();
      const barrage = json && json.data ? json.data.barrage : "";
      if (barrage) {
        currentMeme = barrage;
        if (textEl) textEl.textContent = barrage;
      } else if (textEl) {
        textEl.textContent = "暂时没抢到烂梗";
      }
    } catch {
      if (textEl) textEl.textContent = "烂梗加载失败";
    } finally {
      memeLoading = false;
    }
  }

  function copyMeme() {
    if (!currentMeme) return;
    const iconEl = panel.querySelector("#strikle-meme-icon");
    const done = () => {
      if (!iconEl) return;
      const prev = iconEl.textContent;
      iconEl.textContent = "✅";
      setTimeout(() => { iconEl.textContent = prev; }, 900);
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(currentMeme).then(done, () => {});
    }
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

  // 加载选手库：优先用户手动更新过的 chrome.storage.local，其次回落内置 JSON
  async function loadPlayers() {
    try {
      const stored = await chrome.storage.local.get(STORAGE_KEY);
      if (Array.isArray(stored[STORAGE_KEY]) && stored[STORAGE_KEY].length) {
        return { players: stored[STORAGE_KEY], source: "local" };
      }
    } catch {
      /* storage 不可用则回落 */
    }
    const res = await fetch(chrome.runtime.getURL("players_data.json"));
    return { players: await res.json(), source: "bundled" };
  }

  loadPlayers().then(({ players, source }) => {
    analyzer = new CSPlayerAnalyzer(players);
    setDbStatus(
      source === "local" ? `已加载本地库 ${players.length} 人` : `内置库 ${players.length} 人`,
      "dim"
    );
    if (pendingState) {
      const state = pendingState;
      pendingState = null;
      handleState(state);
    }
  });

  loadMeme(); // 面板就绪即抓一条烂梗（失败静默）
})();
