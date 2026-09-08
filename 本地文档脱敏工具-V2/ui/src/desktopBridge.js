let bridgePromise;

function unavailable() {
  return {
    ok: false,
    error: {
      code: "DESKTOP_BRIDGE_UNAVAILABLE",
      message: "当前未连接本地桌面桥接。",
      retryable: false,
      returnAction: "restart",
    },
  };
}

function parseResult(value) {
  if (typeof value !== "string") return value ?? unavailable();
  try {
    return JSON.parse(value);
  } catch {
    return {
      ok: false,
      error: {
        code: "INVALID_BRIDGE_RESPONSE",
        message: "本地桥接返回了无法识别的结果。",
        retryable: true,
        returnAction: "retry",
      },
    };
  }
}

function connect() {
  if (bridgePromise) return bridgePromise;
  bridgePromise = new Promise((resolve) => {
    if (!window.qt?.webChannelTransport || typeof window.QWebChannel !== "function") {
      resolve(null);
      return;
    }
    new window.QWebChannel(window.qt.webChannelTransport, (channel) => {
      resolve(channel.objects.desktopBridge ?? null);
    });
  });
  return bridgePromise;
}

async function invoke(method, ...args) {
  const bridge = await connect();
  if (!bridge || typeof bridge[method] !== "function") return unavailable();
  return new Promise((resolve) => {
    bridge[method](...args, (value) => resolve(parseResult(value)));
  });
}

export const desktopBridge = {
  runtimeInfo: () => invoke("get_runtime_info"),
  chooseFile: () => invoke("choose_file"),
  createTask: (payload) => invoke("create_task", JSON.stringify(payload)),
  startScan: (taskId) => invoke("start_scan", taskId),
  taskSnapshot: (taskId) => invoke("get_task_snapshot", taskId),
  resolveFinding: (taskId, findingId, action, value = "") => invoke("resolve_finding", taskId, findingId, action, value),
  addManualFinding: (taskId, payload) => invoke("add_manual_finding", taskId, JSON.stringify(payload)),
  previewTask: (taskId) => invoke("preview_task", taskId),
  exportTask: (taskId, outputRoot = "") => invoke("export_task", taskId, outputRoot),
  listHistory: () => invoke("list_history"),
  openHistory: (entryId) => invoke("open_history", entryId),
  listRules: () => invoke("list_rules"),
  saveRule: (payload) => invoke("save_rule", JSON.stringify(payload)),
  deleteRule: (ruleId) => invoke("delete_rule", ruleId),
  setRuleEnabled: (ruleId, enabled) => invoke("set_rule_enabled", ruleId, enabled),
  chooseRuleImportFile: () => invoke("choose_rule_import_file"),
  previewRuleImport: (importId) => invoke("preview_rule_import", importId),
  commitRuleImport: (importId, conflictPolicy) => invoke("commit_rule_import", importId, conflictPolicy),
  restoreDefaultRules: () => invoke("restore_default_rules"),
  applyRulesIncrementally: (taskId) => invoke("apply_rules_incrementally", taskId),
};
