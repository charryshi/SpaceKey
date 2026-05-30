ADMIN_CONSOLE_HTML = """
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Permission Gateway Admin</title>
  <style>
    :root {
      color-scheme: light;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      --bg: #f6f7f9;
      --panel: #ffffff;
      --line: #d8dee8;
      --text: #1f2933;
      --muted: #607083;
      --primary: #176c5f;
      --primary-weak: #e4f3ef;
      --blue: #215a9d;
      --amber: #9a5b00;
      --red: #b42318;
      --red-weak: #fde7e3;
    }
    * { box-sizing: border-box; }
    body { margin: 0; background: var(--bg); color: var(--text); }
    button, input, select, textarea { font: inherit; }
    button { border: 1px solid var(--primary); background: var(--primary); color: white; border-radius: 6px; padding: 8px 11px; cursor: pointer; font-weight: 650; }
    button.secondary { background: white; color: var(--text); border-color: var(--line); }
    button.danger { background: var(--red); border-color: var(--red); }
    button.ghost { background: transparent; color: var(--text); border-color: transparent; }
    button.small { padding: 5px 8px; font-size: 12px; }
    input, select, textarea { width: 100%; border: 1px solid var(--line); border-radius: 6px; padding: 8px 9px; background: white; color: var(--text); }
    textarea { min-height: 82px; resize: vertical; }
    label { display: grid; gap: 5px; color: var(--muted); font-size: 12px; }
    table { width: 100%; border-collapse: collapse; font-size: 13px; }
    th, td { border-bottom: 1px solid var(--line); padding: 9px 8px; text-align: left; vertical-align: top; }
    th { color: var(--muted); font-size: 12px; font-weight: 700; background: #fafbfc; }
    .hidden { display: none !important; }
    .login { min-height: 100vh; display: grid; place-items: center; padding: 24px; }
    .login-box { width: min(440px, 100%); background: white; border: 1px solid var(--line); border-radius: 8px; padding: 24px; display: grid; gap: 16px; }
    .login-box h1 { margin: 0; font-size: 22px; }
    .app { min-height: 100vh; display: grid; grid-template-columns: 248px 1fr; }
    .sidebar { background: #15222d; color: white; padding: 18px 14px; display: grid; align-content: start; gap: 14px; }
    .brand { padding: 4px 8px 12px; border-bottom: 1px solid rgba(255,255,255,.16); }
    .brand strong { display: block; font-size: 16px; }
    .brand span { display: block; color: #b8c6d6; font-size: 12px; margin-top: 4px; }
    .nav { display: grid; gap: 4px; }
    .nav button { width: 100%; text-align: left; background: transparent; border-color: transparent; color: #dce7f3; font-weight: 600; }
    .nav button.active { background: #243746; color: white; }
    .main { min-width: 0; display: grid; grid-template-rows: auto 1fr; }
    .topbar { background: white; border-bottom: 1px solid var(--line); padding: 14px 22px; display: flex; align-items: center; justify-content: space-between; gap: 12px; }
    .topbar h1 { margin: 0; font-size: 19px; }
    .content { padding: 22px; display: grid; gap: 18px; align-content: start; }
    .panel { background: white; border: 1px solid var(--line); border-radius: 8px; padding: 16px; }
    .panel h2 { margin: 0 0 14px; font-size: 16px; }
    .panel h3 { margin: 12px 0 10px; font-size: 13px; color: var(--muted); }
    .grid { display: grid; gap: 14px; }
    .grid.cols-2 { grid-template-columns: minmax(280px, 360px) 1fr; align-items: start; }
    .grid.cols-3 { grid-template-columns: repeat(3, minmax(0, 1fr)); }
    .grid.cols-4 { grid-template-columns: repeat(4, minmax(0, 1fr)); }
    .form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
    .row { display: flex; align-items: center; gap: 9px; flex-wrap: wrap; }
    .between { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
    .muted { color: var(--muted); }
    .note { padding: 10px 12px; border: 1px solid var(--line); background: #fafbfc; border-radius: 6px; color: var(--muted); font-size: 13px; }
    .warning { border-color: #f0c36d; background: #fff7e6; color: #674000; }
    .danger-note { border-color: #f1aaa2; background: var(--red-weak); color: #7a271a; }
    .metric { background: white; border: 1px solid var(--line); border-radius: 8px; padding: 14px; min-height: 92px; }
    .metric b { display: block; font-size: 28px; line-height: 1.1; margin-top: 8px; }
    .metric span { color: var(--muted); font-size: 12px; }
    .tree { display: grid; gap: 4px; }
    .tree-node { border: 1px solid transparent; background: transparent; color: var(--text); text-align: left; width: 100%; padding: 6px 8px; border-radius: 6px; font-weight: 600; }
    .tree-node.active { background: var(--primary-weak); border-color: #b8dcd3; color: #0f554b; }
    .indent { margin-left: 18px; }
    .list { display: grid; gap: 6px; }
    .list button { width: 100%; text-align: left; }
    .chips { display: flex; gap: 6px; flex-wrap: wrap; min-height: 34px; padding: 5px; border: 1px solid var(--line); border-radius: 6px; background: #fafbfc; }
    .chip { display: inline-flex; gap: 6px; align-items: center; border: 1px solid var(--line); background: white; color: var(--text); border-radius: 999px; padding: 4px 8px; font-size: 12px; }
    .chip button { border: 0; background: transparent; color: var(--muted); padding: 0; font-weight: 800; }
    .badge { display: inline-flex; align-items: center; border-radius: 999px; padding: 3px 7px; font-size: 12px; font-weight: 700; background: #eef2f6; color: #3d4a58; }
    .badge.ok { background: #e4f3ef; color: #0f554b; }
    .badge.warn { background: #fff1d6; color: var(--amber); }
    .badge.bad { background: var(--red-weak); color: var(--red); }
    .qr-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 14px; }
    .qr-card { border: 1px solid var(--line); border-radius: 8px; padding: 14px; display: grid; gap: 10px; }
    .qr-card img { width: 160px; height: 160px; border: 1px solid var(--line); border-radius: 6px; background: white; }
    .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px; word-break: break-all; }
    .toolbar { display: flex; gap: 8px; flex-wrap: wrap; align-items: end; margin-bottom: 12px; }
    .toolbar > * { min-width: 160px; }
    .timeline { display: grid; gap: 8px; }
    .timeline-item { border-left: 3px solid var(--line); padding: 6px 0 8px 12px; }
    .toast { position: fixed; right: 18px; bottom: 18px; background: #15222d; color: white; padding: 10px 12px; border-radius: 8px; box-shadow: 0 8px 28px rgba(0,0,0,.18); max-width: min(420px, calc(100vw - 36px)); }
    @media (max-width: 920px) {
      .app { grid-template-columns: 1fr; }
      .sidebar { position: sticky; top: 0; z-index: 2; }
      .nav { grid-template-columns: repeat(3, 1fr); }
      .grid.cols-2, .grid.cols-3, .grid.cols-4, .form-grid { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <section id="login" class="login">
    <form class="login-box" onsubmit="login(event)">
      <div>
        <h1>权限网关管理后台</h1>
        <p class="muted">使用管理员令牌登录后会创建浏览器会话，不需要每次在页面里重复输入 token。</p>
      </div>
      <label>管理员令牌
        <input id="loginToken" type="password" autocomplete="current-password" required>
      </label>
      <button type="submit">登录</button>
      <div id="loginError" class="note danger-note hidden"></div>
    </form>
  </section>

  <section id="app" class="app hidden">
    <aside class="sidebar">
      <div class="brand">
        <strong>Permission Gateway</strong>
        <span>Home Assistant scoped access</span>
      </div>
      <nav class="nav" id="nav">
        <button data-view="dashboard" class="active">仪表盘</button>
        <button data-view="places">场所</button>
        <button data-view="templates">权限模板</button>
        <button data-view="qr">二维码</button>
        <button data-view="keys">Active Keys</button>
        <button data-view="ha">HA 浏览器</button>
        <button data-view="audit">审计日志</button>
      </nav>
    </aside>
    <main class="main">
      <header class="topbar">
        <div>
          <h1 id="viewTitle">仪表盘</h1>
          <div class="muted" id="viewSubtitle">运行状态、授权风险和最近事件</div>
        </div>
        <div class="row">
          <button class="secondary" onclick="loadAll()">刷新</button>
          <button class="secondary" onclick="logout()">退出</button>
        </div>
      </header>

      <div class="content">
        <section id="view-dashboard" class="view grid"></section>
        <section id="view-places" class="view hidden"></section>
        <section id="view-templates" class="view hidden"></section>
        <section id="view-qr" class="view hidden"></section>
        <section id="view-keys" class="view hidden"></section>
        <section id="view-ha" class="view hidden"></section>
        <section id="view-audit" class="view hidden"></section>
      </div>
    </main>
  </section>

  <div id="toast" class="toast hidden"></div>

  <script>
    const state = {
      view: "dashboard",
      dashboard: null,
      places: [],
      templates: [],
      grants: [],
      audit: [],
      notifications: [],
      browser: {areas: [], devices: [], entities: []},
      selectedPlaceId: null,
      selectedTemplateId: null,
      templateDraftScope: emptyScope()
    };

    const titles = {
      dashboard: ["仪表盘", "运行状态、授权风险和最近事件"],
      places: ["场所管理", "维护项目 / 楼栋 / 楼层 / 房间树，并绑定 HA Area"],
      templates: ["权限模板", "用表单配置二维码授权范围、有效期和高风险白名单"],
      qr: ["二维码管理", "预览、下载、复制激活信息、启用或禁用二维码"],
      keys: ["Active Keys", "查看、过滤、延期、缩短或吊销已激活授权"],
      ha: ["HA 设备/实体浏览器", "检查 HA Area、Device、Entity 和模板覆盖关系"],
      audit: ["审计日志", "追踪扫码、拒绝访问和管理员权限修改"]
    };

    function emptyScope() {
      return {
        area_node_ids: [],
        include_device_ids: [],
        include_entity_ids: [],
        exclude_device_ids: [],
        exclude_entity_ids: [],
        allowed_script_entity_ids: [],
        allowed_scene_entity_ids: [],
        allowed_automation_entity_ids: [],
        can_read: true,
        can_control: true
      };
    }

    document.querySelectorAll("#nav button").forEach(button => {
      button.addEventListener("click", () => setView(button.dataset.view));
    });

    boot();

    async function boot() {
      const session = await fetchJson("/v1/admin/session", {suppressAuthRedirect: true});
      if (session && session.authenticated) {
        showApp();
        await loadAll();
      } else {
        showLogin();
      }
    }

    async function login(event) {
      event.preventDefault();
      document.getElementById("loginError").classList.add("hidden");
      try {
        await fetchJson("/v1/admin/session", {
          method: "POST",
          body: JSON.stringify({admin_token: document.getElementById("loginToken").value})
        });
        showApp();
        await loadAll();
      } catch (error) {
        const box = document.getElementById("loginError");
        box.textContent = "登录失败：" + readableError(error);
        box.classList.remove("hidden");
      }
    }

    async function logout() {
      await fetchJson("/v1/admin/session", {method: "DELETE", suppressAuthRedirect: true});
      showLogin();
    }

    function showLogin() {
      document.getElementById("login").classList.remove("hidden");
      document.getElementById("app").classList.add("hidden");
    }

    function showApp() {
      document.getElementById("login").classList.add("hidden");
      document.getElementById("app").classList.remove("hidden");
    }

    async function loadAll() {
      const [dashboard, places, templates, grants, audit, notifications, browser] = await Promise.all([
        fetchJson("/v1/admin/dashboard"),
        fetchJson("/v1/admin/places"),
        fetchJson("/v1/admin/qr-templates"),
        fetchJson("/v1/admin/grants"),
        fetchJson("/v1/admin/audit"),
        fetchJson("/v1/admin/notifications"),
        fetchJson("/v1/admin/ha-browser")
      ]);
      Object.assign(state, {dashboard, places, templates, grants, audit, notifications, browser});
      if (!state.selectedPlaceId && places.length) state.selectedPlaceId = places[0].id;
      if (!state.selectedTemplateId && templates.length) {
        selectTemplate(templates[0].id, false);
      }
      render();
      toast("已刷新");
    }

    async function fetchJson(path, options = {}) {
      const {suppressAuthRedirect, ...fetchOptions} = options;
      const response = await fetch(path, {
        credentials: "same-origin",
        headers: {"Content-Type": "application/json", ...(fetchOptions.headers || {})},
        ...fetchOptions
      });
      const text = await response.text();
      let body = text;
      try { body = text ? JSON.parse(text) : {}; } catch (_) {}
      if (!response.ok) {
        if ((response.status === 401 || response.status === 403) && !suppressAuthRedirect) showLogin();
        throw body;
      }
      return body;
    }

    function setView(view) {
      state.view = view;
      document.querySelectorAll("#nav button").forEach(button => button.classList.toggle("active", button.dataset.view === view));
      document.querySelectorAll(".view").forEach(viewEl => viewEl.classList.add("hidden"));
      document.getElementById("view-" + view).classList.remove("hidden");
      document.getElementById("viewTitle").textContent = titles[view][0];
      document.getElementById("viewSubtitle").textContent = titles[view][1];
      render();
    }

    function render() {
      renderDashboard();
      renderPlaces();
      renderTemplates();
      renderQr();
      renderKeys();
      renderHaBrowser();
      renderAudit();
    }

    function renderDashboard() {
      const root = document.getElementById("view-dashboard");
      const d = state.dashboard || {counts: {}, home_assistant: {}, recent_activations: [], recent_denials: [], expiring_grants: []};
      root.innerHTML = `
        <div class="grid cols-4">
          ${metric("Active keys", d.counts.active_keys || 0, "当前有效授权")}
          ${metric("即将过期", d.counts.expiring_keys || 0, "24 小时内过期")}
          ${metric("权限模板", d.counts.templates || 0, "二维码模板数量")}
          ${metric("HA 实体", d.counts.entities || 0, "手动同步 snapshot")}
        </div>
        <div class="grid cols-2">
          <div class="panel">
            <div class="between"><h2>Home Assistant 状态</h2><button class="secondary small" onclick="syncRegistry()">同步 HA Registry</button></div>
            <div class="grid">
              ${statusLine("HOME_ASSISTANT_TOKEN", d.home_assistant.token_configured ? "已配置" : "未配置", d.home_assistant.token_configured ? "ok" : "bad")}
              ${statusLine("HA 连接", d.home_assistant.connection_status || "unknown", d.home_assistant.connection_status === "ok" ? "ok" : "warn")}
              ${statusLine("Registry 同步", d.home_assistant.registry_synced ? "已同步" : "未同步", d.home_assistant.registry_synced ? "ok" : "bad")}
              ${statusLine("最近同步", d.home_assistant.registry_last_synced_at ? fmtDate(d.home_assistant.registry_last_synced_at) : "从未同步", d.home_assistant.registry_last_synced_at ? "ok" : "warn")}
            </div>
            <p class="note ${d.home_assistant.token_configured && d.home_assistant.registry_synced ? "" : "warning"}">Registry 不需要高频同步。仅在 HA 的 Area、Device、Entity 结构变化后手动同步；未同步时，网关可登录管理台，但无法完整计算按场所授权结果。</p>
          </div>
          <div class="panel">
            <h2>即将过期 keys</h2>
            ${simpleGrantList(d.expiring_grants || [])}
          </div>
        </div>
        <div class="grid cols-2">
          <div class="panel"><h2>最近扫码激活</h2>${timeline(d.recent_activations || [])}</div>
          <div class="panel"><h2>最近拒绝访问</h2>${timeline(d.recent_denials || [])}</div>
        </div>
      `;
    }

    function renderPlaces() {
      const root = document.getElementById("view-places");
      const selected = state.places.find(place => place.id === state.selectedPlaceId) || null;
      root.innerHTML = `
        <div class="grid cols-2">
          <div class="panel">
            <div class="between"><h2>场所树</h2><button class="secondary small" onclick="newPlace()">新增节点</button></div>
            <div class="tree">${renderPlaceTree(null)}</div>
          </div>
          <div class="panel">
            <h2>${selected ? "编辑场所" : "新增场所"}</h2>
            <div class="form-grid">
              <label>名称<input id="placeName" value="${escapeAttr(selected?.name || "")}"></label>
              <label>父级<select id="placeParent">${placeParentOptions(selected?.parent_id || "", selected?.id || "")}</select></label>
              <label>绑定 HA Area<select id="placeAreas" multiple size="6">${haAreaOptions(selected?.ha_area_ids || [])}</select></label>
              ${selected ? `<label>系统 ID<input value="${escapeAttr(selected.id)}" readonly></label>` : `<div class="note">系统会自动生成场所 ID，管理员只需要维护名称、层级和 HA Area 绑定。</div>`}
            </div>
            <div class="row" style="margin-top:14px">
              <button onclick="savePlace()">保存场所</button>
              ${selected ? `<button class="danger" onclick="deletePlace('${escapeAttr(selected.id)}')">删除场所</button>` : ""}
            </div>
            <p class="note">移动层级：选择新的父级后保存。删除场所前必须先移走或删除子节点。</p>
          </div>
        </div>
      `;
    }

    function renderTemplates() {
      const root = document.getElementById("view-templates");
      const selected = state.templates.find(template => template.id === state.selectedTemplateId) || null;
      root.innerHTML = `
        <div class="grid cols-2">
          <div class="panel">
            <div class="between"><h2>模板列表</h2><button class="secondary small" onclick="newTemplate()">新增模板</button></div>
            <div class="list">${state.templates.map(template => `
              <button class="secondary ${template.id === state.selectedTemplateId ? "active" : ""}" onclick="selectTemplate('${escapeAttr(template.id)}')">
                <strong>${escapeHtml(template.name)}</strong><br>
                <span class="muted">${template.enabled ? "启用" : "禁用"} · 默认 ${secondsToDays(template.default_ttl_seconds)} 天</span>
              </button>`).join("") || `<p class="muted">暂无模板</p>`}
            </div>
          </div>
          <div class="panel">
            <h2>${selected ? "编辑权限模板" : "新增权限模板"}</h2>
            <div class="form-grid">
              <label>模板名称<input id="templateName" value="${escapeAttr(selected?.name || "")}"></label>
              <label>验证码<input id="templateCode" type="password" placeholder="${selected ? "留空则保留原验证码" : "请输入验证码"}"></label>
              <label>状态<select id="templateEnabled"><option value="true" ${selected?.enabled !== false ? "selected" : ""}>启用</option><option value="false" ${selected?.enabled === false ? "selected" : ""}>禁用</option></select></label>
              <label>默认有效期（天）<input id="templateDefaultDays" type="number" min="1" value="${secondsToDays(selected?.default_ttl_seconds || 86400)}"></label>
              <label>最长有效期（天）<input id="templateMaxDays" type="number" min="1" value="${secondsToDays(selected?.max_ttl_seconds || 604800)}"></label>
              ${selected ? `<label>系统 ID<input value="${escapeAttr(selected.id)}" readonly></label>` : `<div class="note">系统会自动生成模板 ID，二维码会绑定到这个模板。</div>`}
            </div>
            <h3>场所范围</h3>
            <div class="panel" style="padding:10px">${renderScopePlaceTree(null)}</div>
            <h3>设备/实体例外</h3>
            ${scopePicker("include_device_ids", "追加设备", "deviceInput", deviceOptions())}
            ${scopePicker("include_entity_ids", "追加实体", "entityInput", entityOptions())}
            ${scopePicker("exclude_device_ids", "排除设备", "excludeDeviceInput", deviceOptions())}
            ${scopePicker("exclude_entity_ids", "排除实体", "excludeEntityInput", entityOptions())}
            <h3>脚本 / 场景 / 自动化</h3>
            <p class="note">如果脚本、场景、自动化实体本身属于已授权场所，用户会自动拥有访问权限。下面只用于跨场所额外允许，谨慎使用。</p>
            ${scopePicker("allowed_script_entity_ids", "跨场所额外允许 script", "scriptInput", entityOptions("script."))}
            ${scopePicker("allowed_scene_entity_ids", "跨场所额外允许 scene", "sceneInput", entityOptions("scene."))}
            ${scopePicker("allowed_automation_entity_ids", "跨场所额外允许 automation", "automationInput", entityOptions("automation."))}
            <div id="templatePreview" class="note" style="margin-top:12px">保存前会显示最终授权实体数量。</div>
            <div class="row" style="margin-top:14px">
              <button onclick="previewTemplate()">预览授权范围</button>
              <button onclick="saveTemplate()">保存模板</button>
            </div>
          </div>
        </div>
      `;
    }

    function renderQr() {
      const root = document.getElementById("view-qr");
      root.innerHTML = `
        <div class="panel">
          <h2>二维码管理</h2>
          <p class="note">二维码只包含 gateway_url 和 qr_id，不等于授权密钥。客人扫码后仍必须输入验证码，网关才会生成限时 key。</p>
          <div class="qr-grid">${state.templates.map(template => qrCard(template)).join("") || `<p class="muted">暂无二维码模板</p>`}</div>
        </div>
      `;
    }

    function renderKeys() {
      const root = document.getElementById("view-keys");
      const filter = document.getElementById("keyFilter")?.value || "all";
      const placeFilter = document.getElementById("keyPlaceFilter")?.value || "";
      const rows = state.grants.filter(grant => {
        const status = grantStatus(grant);
        if (filter !== "all" && filter !== status) return false;
        if (placeFilter && !(grant.scope?.area_node_ids || []).includes(placeFilter)) return false;
        return true;
      });
      root.innerHTML = `
        <div class="panel">
          <div class="toolbar">
            <label>状态<select id="keyFilter" onchange="renderKeys()">
              ${option("all", "全部", filter)}${option("active", "有效", filter)}${option("expiring", "即将过期", filter)}${option("expired", "已过期", filter)}${option("revoked", "已吊销", filter)}
            </select></label>
            <label>场所<select id="keyPlaceFilter" onchange="renderKeys()">${option("", "全部场所", placeFilter)}${state.places.map(p => option(p.id, p.name, placeFilter)).join("")}</select></label>
          </div>
          <table>
            <thead><tr><th>用户/设备标识</th><th>模板</th><th>授权场所</th><th>激活时间</th><th>过期时间</th><th>状态</th><th>操作</th></tr></thead>
            <tbody>${rows.map(grant => keyRow(grant)).join("") || `<tr><td colspan="7" class="muted">没有匹配的 key</td></tr>`}</tbody>
          </table>
        </div>
      `;
      document.getElementById("keyFilter").value = filter;
      document.getElementById("keyPlaceFilter").value = placeFilter;
    }

    function renderHaBrowser() {
      const root = document.getElementById("view-ha");
      const missing = state.browser.devices.filter(device => !device.area_id);
      root.innerHTML = `
        <div class="grid">
          <div class="panel">
            <div class="between"><h2>HA Area / Device / Entity</h2><button class="secondary small" onclick="syncRegistry()">同步 HA Registry</button></div>
            <p class="note">这是手动低频操作：只有 Home Assistant 里新增/移动 Area、Device、Entity 后才需要同步。</p>
            ${missing.length ? `<p class="note warning">${missing.length} 个设备未绑定 Area，会影响按场所授权。请先在 Home Assistant 中补齐 Area，或在权限模板中用设备/实体例外处理。</p>` : `<p class="note">当前 registry 中的设备都有 Area 信息。</p>`}
          </div>
          <div class="panel"><h2>Areas</h2>${areaTable()}</div>
          <div class="panel"><h2>Devices</h2>${deviceTable()}</div>
          <div class="panel"><h2>Entities</h2>${entityTable()}</div>
        </div>
      `;
    }

    function renderAudit() {
      const root = document.getElementById("view-audit");
      const typeFilter = document.getElementById("auditType")?.value || "";
      const search = (document.getElementById("auditSearch")?.value || "").toLowerCase();
      const events = state.audit.filter(event => {
        if (typeFilter && event.event_type !== typeFilter) return false;
        if (!search) return true;
        return JSON.stringify(event).toLowerCase().includes(search);
      });
      const types = [...new Set(state.audit.map(event => event.event_type))].sort();
      root.innerHTML = `
        <div class="panel">
          <div class="toolbar">
            <label>事件类型<select id="auditType" onchange="renderAudit()">${option("", "全部事件", typeFilter)}${types.map(type => option(type, type, typeFilter)).join("")}</select></label>
            <label>搜索 key / 模板 / 场所 / 详情<input id="auditSearch" value="${escapeAttr(search)}" oninput="renderAudit()"></label>
          </div>
          <div class="timeline">${events.map(event => auditItem(event)).join("") || `<p class="muted">没有匹配的审计事件</p>`}</div>
        </div>
      `;
    }

    function metric(label, value, hint) {
      return `<div class="metric"><span>${escapeHtml(hint)}</span><b>${escapeHtml(String(value))}</b><span>${escapeHtml(label)}</span></div>`;
    }

    function statusLine(label, value, kind) {
      return `<div class="between"><span>${escapeHtml(label)}</span><span class="badge ${kind}">${escapeHtml(value)}</span></div>`;
    }

    function timeline(events) {
      return `<div class="timeline">${events.map(auditItem).join("") || `<p class="muted">暂无记录</p>`}</div>`;
    }

    function auditItem(event) {
      return `<div class="timeline-item">
        <div class="between"><strong>${escapeHtml(event.event_type)}</strong><span class="muted">${fmtDate(event.created_at)}</span></div>
        <div class="muted">${escapeHtml(event.actor)} → ${escapeHtml(event.target)}</div>
        <div class="mono">${escapeHtml(JSON.stringify(event.details || {}))}</div>
      </div>`;
    }

    function simpleGrantList(grants) {
      return grants.length ? `<table><tbody>${grants.map(grant => `<tr><td class="mono">${escapeHtml(grant.id)}</td><td>${fmtDate(grant.expires_at)}</td></tr>`).join("")}</tbody></table>` : `<p class="muted">未来 24 小时没有即将过期 key</p>`;
    }

    function renderPlaceTree(parentId) {
      const children = state.places.filter(place => (place.parent_id || null) === parentId);
      return children.map(place => `
        <div>
          <button class="tree-node ${place.id === state.selectedPlaceId ? "active" : ""}" onclick="selectPlace('${escapeAttr(place.id)}')">
            ${escapeHtml(place.name)}
            ${place.ha_area_ids?.length ? `<br><span class="muted">${place.ha_area_ids.map(haAreaLabel).map(escapeHtml).join(" / ")}</span>` : ""}
          </button>
          <div class="indent">${renderPlaceTree(place.id)}</div>
        </div>
      `).join("");
    }

    function renderScopePlaceTree(parentId) {
      const children = state.places.filter(place => (place.parent_id || null) === parentId);
      return children.map(place => `
        <div>
          <label style="display:flex;align-items:center;gap:8px;color:var(--text);font-size:13px">
            <input type="checkbox" style="width:auto" ${state.templateDraftScope.area_node_ids.includes(place.id) ? "checked" : ""} onchange="toggleScopeValue('area_node_ids','${escapeAttr(place.id)}',this.checked)">
            ${escapeHtml(placePath(place.id))}
            ${place.ha_area_ids?.length ? `<span class="muted">${place.ha_area_ids.map(haAreaLabel).map(escapeHtml).join(" / ")}</span>` : ""}
          </label>
          <div class="indent">${renderScopePlaceTree(place.id)}</div>
        </div>
      `).join("") || `<p class="muted">暂无场所</p>`;
    }

    function selectPlace(id) {
      state.selectedPlaceId = id;
      renderPlaces();
    }

    function newPlace() {
      state.selectedPlaceId = null;
      renderPlaces();
    }

    async function savePlace() {
      const name = document.getElementById("placeName").value.trim();
      if (!name) return toast("场所名称必填");
      const parent = document.getElementById("placeParent").value || null;
      const areas = selectedValues("placeAreas");
      const payload = {name, parent_id: parent, ha_area_ids: areas};
      if (state.selectedPlaceId) payload.id = state.selectedPlaceId;
      const saved = await fetchJson("/v1/admin/places", {method: "POST", body: JSON.stringify(payload)});
      state.selectedPlaceId = saved.id;
      await loadAll();
    }

    async function deletePlace(id) {
      if (!confirm("确认删除这个场所？该操作不能删除仍有子节点的场所。")) return;
      await fetchJson("/v1/admin/places/" + encodeURIComponent(id), {method: "DELETE"});
      state.selectedPlaceId = null;
      await loadAll();
    }

    function placeParentOptions(selected, currentId) {
      return option("", "无父级", selected) + state.places
        .filter(place => place.id !== currentId)
        .map(place => option(place.id, placePath(place.id), selected))
        .join("");
    }

    function haAreaOptions(selectedAreas) {
      const selected = new Set(selectedAreas || []);
      return allHaAreas().map(areaId => `<option value="${escapeAttr(areaId)}" ${selected.has(areaId) ? "selected" : ""}>${escapeHtml(haAreaLabel(areaId))}</option>`).join("");
    }

    function allHaAreas() {
      return [...new Set([
        ...state.browser.areas.map(area => area.area_id),
        ...state.browser.devices.map(device => device.area_id).filter(Boolean),
        ...state.browser.entities.map(entity => entity.area_id).filter(Boolean)
      ])].sort();
    }

    function haAreaLabel(areaId) {
      if (!areaId) return "-";
      const area = state.browser.areas.find(item => item.area_id === areaId);
      const localPlaces = state.places.filter(place => (place.ha_area_ids || []).includes(areaId)).map(place => placePath(place.id));
      const name = area?.name || areaId;
      const suffix = localPlaces.length ? ` · ${localPlaces.join(" / ")}` : ` · ${areaId}`;
      return name + suffix;
    }

    function placePath(id) {
      const place = state.places.find(item => item.id === id);
      if (!place) return id;
      const names = [place.name];
      let parentId = place.parent_id;
      const guard = new Set([id]);
      while (parentId && !guard.has(parentId)) {
        guard.add(parentId);
        const parent = state.places.find(item => item.id === parentId);
        if (!parent) break;
        names.unshift(parent.name);
        parentId = parent.parent_id;
      }
      return names.join(" / ");
    }

    function deviceOptions() {
      return state.browser.devices.map(device => ({
        id: device.id,
        label: deviceLabel(device.id)
      }));
    }

    function entityOptions(prefix = "") {
      return state.browser.entities
        .filter(entity => !prefix || entity.entity_id.startsWith(prefix))
        .map(entity => ({
          id: entity.entity_id,
          label: entityLabel(entity.entity_id)
        }));
    }

    function deviceLabel(deviceId) {
      const device = state.browser.devices.find(item => item.id === deviceId);
      if (!device) return deviceId;
      const name = device.name || device.id;
      return `${name} · ${haAreaLabel(device.area_id)} · ${device.id}`;
    }

    function entityLabel(entityId) {
      const entity = state.browser.entities.find(item => item.entity_id === entityId);
      if (!entity) return entityId;
      const areaId = entity.effective_area_id || entity.area_id || deviceArea(entity.device_id);
      const name = entity.display_name || entity.name || entity.entity_id;
      const category = entityCategoryLabel(entity);
      const categoryPart = category === "主实体" ? "" : ` · ${category}`;
      return `${name} · ${haAreaLabel(areaId)}${categoryPart} · ${entity.entity_id}`;
    }

    function resourceChipLabel(field, value) {
      const isDevice = field.includes("device");
      const label = isDevice ? deviceLabel(value) : entityLabel(value);
      const parts = label.split(" · ");
      const title = parts.shift() || value;
      const meta = parts.join(" · ");
      return `${escapeHtml(title)}<span class="muted">${escapeHtml(meta)}</span>`;
    }

    function deviceArea(deviceId) {
      const device = state.browser.devices.find(item => item.id === deviceId);
      return device?.area_id || null;
    }

    function deviceName(deviceId) {
      if (!deviceId) return "-";
      const device = state.browser.devices.find(item => item.id === deviceId);
      return device ? `${device.name || device.id} (${device.id})` : deviceId;
    }

    function placesForHaArea(areaId) {
      return state.places
        .filter(place => (place.ha_area_ids || []).includes(areaId))
        .map(place => placePath(place.id));
    }

    function selectTemplate(id, shouldRender = true) {
      state.selectedTemplateId = id;
      const template = state.templates.find(item => item.id === id);
      state.templateDraftScope = normalizeScope(template?.scope);
      if (shouldRender) renderTemplates();
    }

    function newTemplate() {
      state.selectedTemplateId = null;
      state.templateDraftScope = emptyScope();
      renderTemplates();
    }

    function normalizeScope(scope) {
      return {...emptyScope(), ...(scope || {})};
    }

    function toggleScopeValue(field, value, checked) {
      const values = new Set(state.templateDraftScope[field] || []);
      checked ? values.add(value) : values.delete(value);
      state.templateDraftScope[field] = [...values].sort();
    }

    function addScopeValue(field, inputId) {
      const input = document.getElementById(inputId);
      const value = input.value.trim();
      if (!value) return;
      toggleScopeValue(field, value, true);
      input.value = "";
      renderTemplates();
    }

    function removeScopeValue(field, value) {
      toggleScopeValue(field, value, false);
      renderTemplates();
    }

    function scopePicker(field, label, inputId, options) {
      return `<label>${escapeHtml(label)}
        <div class="row">
          <input id="${inputId}" list="${inputId}-list" placeholder="搜索名称、场所或 ID">
          <button class="secondary small" type="button" onclick="addScopeValue('${field}','${inputId}')">添加</button>
        </div>
        <datalist id="${inputId}-list">${options.map(item => `<option value="${escapeAttr(item.id)}" label="${escapeAttr(item.label)}"></option>`).join("")}</datalist>
        <div class="chips">${(state.templateDraftScope[field] || []).map(value => `<span class="chip">${resourceChipLabel(field, value)}<button onclick="removeScopeValue('${field}','${escapeAttr(value)}')">x</button></span>`).join("") || `<span class="muted">未设置</span>`}</div>
      </label>`;
    }

    function buildTemplatePayload() {
      const selected = state.templates.find(template => template.id === state.selectedTemplateId);
      const code = document.getElementById("templateCode").value;
      const payload = {
        name: document.getElementById("templateName").value.trim(),
        enabled: document.getElementById("templateEnabled").value === "true",
        default_ttl_seconds: Number(document.getElementById("templateDefaultDays").value || 1) * 86400,
        max_ttl_seconds: Number(document.getElementById("templateMaxDays").value || 1) * 86400,
        scope: state.templateDraftScope
      };
      if (selected) payload.id = selected.id;
      if (code) payload.verification_code = code;
      else if (selected?.verification_code_hash) payload.verification_code_hash = selected.verification_code_hash;
      return payload;
    }

    async function previewTemplate() {
      const payload = buildTemplatePayload();
      const preview = await fetchJson("/v1/admin/qr-templates/preview", {method: "POST", body: JSON.stringify({scope: payload.scope})});
      document.getElementById("templatePreview").className = "note " + (preview.has_high_risk_allowlist ? "warning" : "");
      document.getElementById("templatePreview").innerHTML = `最终授权 <strong>${preview.entity_count}</strong> 个实体、<strong>${preview.device_count}</strong> 个设备、<strong>${preview.ha_area_count}</strong> 个 HA Area。${preview.has_high_risk_allowlist ? "包含跨场所脚本/场景/自动化额外允许项，请确认影响范围。" : "授权场所内的脚本/场景/自动化会随场所自动可用。"}`;
      return preview;
    }

    async function saveTemplate() {
      const payload = buildTemplatePayload();
      if (!payload.name) return toast("模板名称必填");
      if (!payload.verification_code && !payload.verification_code_hash) return toast("新模板必须设置验证码");
      const preview = await previewTemplate();
      if (preview.has_high_risk_allowlist && !confirm("该模板包含跨场所脚本、场景或自动化额外允许项。确认保存？")) return;
      const saved = await fetchJson("/v1/admin/qr-templates", {method: "POST", body: JSON.stringify(payload)});
      state.selectedTemplateId = saved.id;
      await loadAll();
    }

    function qrCard(template) {
      const activationPayload = JSON.stringify({gateway_url: location.origin, qr_id: template.id});
      return `<div class="qr-card">
        <div class="between"><strong>${escapeHtml(template.name)}</strong><span class="badge ${template.enabled ? "ok" : "bad"}">${template.enabled ? "启用" : "禁用"}</span></div>
        <img alt="QR ${escapeAttr(template.id)}" src="/v1/admin/qr-templates/${encodeURIComponent(template.id)}/qr.png?ts=${Date.now()}">
        <div class="mono">${escapeHtml(activationPayload)}</div>
        <div class="row">
          <button class="secondary small" onclick='copyText(${JSON.stringify(activationPayload)})'>复制激活信息</button>
          <a class="badge" href="/v1/admin/qr-templates/${encodeURIComponent(template.id)}/qr.png" download="${escapeAttr(template.id)}.png">下载 PNG</a>
          <button class="${template.enabled ? "danger" : "secondary"} small" onclick="toggleTemplate('${escapeAttr(template.id)}')">${template.enabled ? "禁用" : "启用"}</button>
        </div>
      </div>`;
    }

    async function toggleTemplate(id) {
      const template = state.templates.find(item => item.id === id);
      if (!template) return;
      if (template.enabled && !confirm("确认禁用这个二维码？已激活 key 不会自动吊销。")) return;
      await fetchJson("/v1/admin/qr-templates", {
        method: "POST",
        body: JSON.stringify({...template, enabled: !template.enabled})
      });
      await loadAll();
    }

    function keyRow(grant) {
      const template = state.templates.find(item => item.id === grant.template_id);
      return `<tr>
        <td><div class="mono">${escapeHtml(grant.app_instance_id)}</div><div class="muted mono">${escapeHtml(grant.id)}</div></td>
        <td>${escapeHtml(template?.name || grant.template_id || "-")}</td>
        <td>${(grant.scope?.area_node_ids || []).map(id => `<span class="badge">${escapeHtml(placeName(id))}</span>`).join(" ") || "-"}</td>
        <td>${fmtDate(grant.issued_at)}</td>
        <td>${fmtDate(grant.expires_at)}</td>
        <td>${statusBadge(grantStatus(grant))}</td>
        <td><div class="row">
          <button class="secondary small" onclick="viewGrantSummary('${escapeAttr(grant.id)}')">权限摘要</button>
          <button class="secondary small" onclick="shiftGrant('${escapeAttr(grant.id)}',1)">延长 1 天</button>
          <button class="secondary small" onclick="shortenGrant('${escapeAttr(grant.id)}')">缩短到 1 天</button>
          <button class="danger small" onclick="revokeGrant('${escapeAttr(grant.id)}')">吊销</button>
        </div></td>
      </tr>`;
    }

    async function viewGrantSummary(id) {
      const grant = state.grants.find(item => item.id === id);
      const preview = await fetchJson("/v1/admin/qr-templates/preview", {method: "POST", body: JSON.stringify({scope: grant.scope || {}})});
      alert(`授权摘要\\n实体：${preview.entity_count}\\n设备：${preview.device_count}\\nHA Area：${preview.ha_area_count}\\n高风险白名单：${preview.has_high_risk_allowlist ? "有" : "无"}`);
    }

    async function shiftGrant(id, days) {
      const grant = state.grants.find(item => item.id === id);
      const base = grant?.expires_at ? Math.max(new Date(grant.expires_at).getTime(), Date.now()) : Date.now();
      await updateGrant(id, {expires_at: new Date(base + days * 86400 * 1000).toISOString()});
    }

    async function shortenGrant(id) {
      if (!confirm("确认把这个 key 的过期时间缩短到 1 天后？")) return;
      await updateGrant(id, {expires_at: new Date(Date.now() + 86400 * 1000).toISOString()});
    }

    async function revokeGrant(id) {
      if (!confirm("确认立即吊销这个 key？客户端会失去访问权限。")) return;
      await updateGrant(id, {revoke: true});
    }

    async function updateGrant(id, patch) {
      await fetchJson("/v1/admin/grants/" + encodeURIComponent(id), {method: "PATCH", body: JSON.stringify(patch)});
      await loadAll();
    }

    async function syncRegistry() {
      if (!confirm("Registry 同步是低频管理操作。确认现在从 Home Assistant 拉取 Area、Device、Entity registry？")) return;
      toast("正在同步 HA Registry...");
      try {
        const result = await fetchJson("/v1/admin/ha-registry-sync", {method: "POST"});
        await loadAll();
        toast(`同步完成：${result.counts.areas} areas / ${result.counts.devices} devices / ${result.counts.entities} entities`);
      } catch (error) {
        toast("同步失败：" + readableError(error));
      }
    }

    function areaTable() {
      return `<table><thead><tr><th>名称</th><th>绑定场所</th><th>系统 ID</th><th>设备数</th><th>主实体 / 总实体</th></tr></thead><tbody>${state.browser.areas.map(area => `<tr><td>${escapeHtml(area.name || area.area_id)}</td><td>${escapeHtml(placesForHaArea(area.area_id).join(" / ") || "-")}</td><td class="mono">${escapeHtml(area.area_id)}</td><td>${area.device_count}</td><td>${area.default_visible_entity_count ?? area.entity_count} / ${area.entity_count}</td></tr>`).join("") || `<tr><td colspan="5" class="muted">暂无 Area</td></tr>`}</tbody></table>`;
    }

    function deviceTable() {
      return `<table><thead><tr><th>设备</th><th>所属场所 / HA Area</th><th>主实体 / 总实体</th><th>模板覆盖</th><th>警告</th></tr></thead><tbody>${state.browser.devices.map(device => `<tr><td>${escapeHtml(device.name || device.id)}<div class="muted mono">${escapeHtml(device.id)}</div></td><td>${escapeHtml(haAreaLabel(device.area_id))}</td><td>${device.default_visible_entity_count ?? device.entity_count} / ${device.entity_count}</td><td>${coverage(device.covered_by_templates)}</td><td>${warnings(device.warnings)}</td></tr>`).join("") || `<tr><td colspan="5" class="muted">暂无设备</td></tr>`}</tbody></table>`;
    }

    function entityTable() {
      return `<table><thead><tr><th>实体</th><th>类别</th><th>设备</th><th>所属场所 / HA Area</th><th>模板覆盖</th><th>警告</th></tr></thead><tbody>${state.browser.entities.map(entity => `<tr><td>${escapeHtml(entity.display_name || entity.name || entity.entity_id)}<div class="muted mono">${escapeHtml(entity.entity_id)}</div></td><td>${entityCategoryBadge(entity)}</td><td>${escapeHtml(deviceName(entity.device_id))}</td><td>${escapeHtml(haAreaLabel(entity.effective_area_id || entity.area_id || deviceArea(entity.device_id)))}</td><td>${coverage(entity.covered_by_templates)}</td><td>${warnings(entity.warnings)}</td></tr>`).join("") || `<tr><td colspan="6" class="muted">暂无实体</td></tr>`}</tbody></table>`;
    }

    function entityCategoryLabel(entity) {
      if (entity.disabled_by) return "已禁用";
      if (entity.hidden_by) return "已隐藏";
      if (entity.entity_category === "config") return "配置实体";
      if (entity.entity_category === "diagnostic") return "诊断实体";
      if (entity.entity_category) return `附属实体：${entity.entity_category}`;
      return "主实体";
    }

    function entityCategoryBadge(entity) {
      const label = entityCategoryLabel(entity);
      const css = label === "主实体" ? "ok" : "warn";
      return `<span class="badge ${css}">${escapeHtml(label)}</span>`;
    }

    function coverage(templateIds) {
      return (templateIds || []).map(id => `<span class="badge">${escapeHtml(id)}</span>`).join(" ") || "-";
    }

    function warnings(items) {
      return (items || []).map(item => `<span class="badge warn">${escapeHtml(warningLabel(item))}</span>`).join(" ") || "";
    }

    function warningLabel(item) {
      if (item === "missing_area") return "未绑定 Area";
      if (item === "hidden") return "已隐藏";
      if (item === "disabled") return "已禁用";
      if (item === "entity_category:config") return "配置实体默认不授权";
      if (item === "entity_category:diagnostic") return "诊断实体默认不授权";
      if (item.startsWith("entity_category:")) return "附属实体默认不授权";
      return item;
    }

    function selectedValues(id) {
      return [...document.getElementById(id).selectedOptions].map(option => option.value);
    }

    function option(value, label, selected) {
      return `<option value="${escapeAttr(value)}" ${value === selected ? "selected" : ""}>${escapeHtml(label)}</option>`;
    }

    function secondsToDays(seconds) {
      return Math.max(1, Math.round(Number(seconds || 86400) / 86400));
    }

    function grantStatus(grant) {
      if (grant.revoked_at) return "revoked";
      if (grant.expires_at && new Date(grant.expires_at).getTime() <= Date.now()) return "expired";
      if (grant.expires_at && new Date(grant.expires_at).getTime() <= Date.now() + 24 * 3600 * 1000) return "expiring";
      return "active";
    }

    function statusBadge(status) {
      const map = {active: ["有效", "ok"], expiring: ["即将过期", "warn"], expired: ["已过期", "bad"], revoked: ["已吊销", "bad"]};
      return `<span class="badge ${map[status]?.[1] || ""}">${map[status]?.[0] || status}</span>`;
    }

    function placeName(id) {
      const place = state.places.find(item => item.id === id);
      return place ? place.name : id;
    }

    function fmtDate(value) {
      if (!value) return "-";
      const date = new Date(value);
      if (Number.isNaN(date.getTime())) return value;
      return date.toLocaleString();
    }

    function copyText(value) {
      navigator.clipboard.writeText(value).then(() => toast("已复制"));
    }

    function toast(message) {
      const el = document.getElementById("toast");
      el.textContent = message;
      el.classList.remove("hidden");
      clearTimeout(window.toastTimer);
      window.toastTimer = setTimeout(() => el.classList.add("hidden"), 2200);
    }

    function readableError(error) {
      return error?.detail || error?.message || JSON.stringify(error);
    }

    function escapeHtml(value) {
      const replacements = {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"};
      return String(value ?? "").replace(/[&<>"']/g, char => replacements[char]);
    }

    function escapeAttr(value) {
      return escapeHtml(value);
    }
  </script>
</body>
</html>
"""
