const API_BASE = "http://127.0.0.1:8000/api";
const PAY_URL = "http://127.0.0.1:8000/pay";

const elements = {
  apiStatus: document.getElementById("apiStatus"),
  geminiStatus: document.getElementById("geminiStatus"),
  networkValue: document.getElementById("networkValue"),
  registryCount: document.getElementById("registryCount"),
  walletValue: document.getElementById("walletValue"),
  indexerValue: document.getElementById("indexerValue"),
  heroCapValue: document.getElementById("heroCapValue"),
  heroSpentValue: document.getElementById("heroSpentValue"),
  heroReceiptCount: document.getElementById("heroReceiptCount"),
  serviceGrid: document.getElementById("serviceGrid"),
  spendCapInput: document.getElementById("spendCapInput"),
  saveCapButton: document.getElementById("saveCapButton"),
  spentValue: document.getElementById("spentValue"),
  capValue: document.getElementById("capValue"),
  budgetFill: document.getElementById("budgetFill"),
  intentInput: document.getElementById("intentInput"),
  generateIntentButton: document.getElementById("generateIntentButton"),
  intentOutput: document.getElementById("intentOutput"),
  transactionCard: document.getElementById("transactionCard"),
  timeline: document.getElementById("timeline"),
  receiptTableBody: document.getElementById("receiptTableBody"),
  clearLogButton: document.getElementById("clearLogButton"),
  serviceCardTemplate: document.getElementById("serviceCardTemplate")
};

const appState = {
  services: [],
  config: null,
  state: null,
  selectedServiceId: null
};

bootstrap();

async function bootstrap() {
  bindEvents();
  await hydrateApp();
}

function bindEvents() {
  elements.saveCapButton.addEventListener("click", saveSpendCap);
  elements.clearLogButton.addEventListener("click", clearReceipts);
  elements.generateIntentButton.addEventListener("click", generateIntent);
}

async function hydrateApp() {
  try {
    const [config, servicesPayload, runtimeState] = await Promise.all([
      apiGet("/config"),
      apiGet("/services"),
      apiGet("/state")
    ]);

    appState.config = config;
    appState.services = servicesPayload.services;
    appState.state = runtimeState;

    elements.apiStatus.textContent = "Backend online";
    elements.geminiStatus.textContent = config.gemini_enabled ? "Gemini configured" : "Gemini fallback mode";

    renderConfig();
    renderServices();
    syncStateViews();
    renderReceipts();
  } catch (error) {
    elements.apiStatus.textContent = "Backend offline";
    elements.geminiStatus.textContent = "Start backend/app.py";
    updateTransactionCard(
      "Backend connection required",
      "The frontend is ready, but it needs the Python API running on port 8000 to load services and execute purchases.",
      "blocked"
    );
    setTimeline([{ step: "Boot", detail: String(error.message || error) }]);
  }
}

function renderConfig() {
  const { config } = appState;
  elements.networkValue.textContent = config.network;
  elements.walletValue.textContent = truncateMiddle(config.payment_wallet);
  elements.indexerValue.textContent = readableEndpoint(config.indexer_server);
  elements.registryCount.textContent = `${appState.services.length} services`;
}

function renderServices() {
  elements.serviceGrid.innerHTML = "";

  appState.services.forEach((service) => {
    const fragment = elements.serviceCardTemplate.content.cloneNode(true);
    fragment.querySelector(".service-card__name").textContent = service.name;
    fragment.querySelector(".service-card__description").textContent = service.description;
    fragment.querySelector(".service-card__price").textContent = formatAlgo(service.price);
    fragment.querySelector(".service-card__category").textContent = service.category;
    fragment.querySelector(".service-card__address").textContent = `Pay to ${truncateMiddle(service.payment_address, 10, 6)}`;
    fragment.querySelector(".service-card__latency").textContent = service.latency_target;
    fragment.querySelector(".service-card__settlement").textContent = service.settlement_mode;
    fragment.querySelector(".service-card__action").addEventListener("click", () => purchaseService(service.id));
    elements.serviceGrid.appendChild(fragment);
  });
}

function syncStateViews() {
  const runtimeState = appState.state;
  elements.spendCapInput.value = runtimeState.spend_cap;
  elements.spentValue.textContent = formatAlgo(runtimeState.spent);
  elements.capValue.textContent = formatAlgo(runtimeState.spend_cap);
  elements.heroCapValue.textContent = formatAlgo(runtimeState.spend_cap);
  elements.heroSpentValue.textContent = formatAlgo(runtimeState.spent);
  elements.heroReceiptCount.textContent = String(runtimeState.receipts.length);

  const width = Math.min((runtimeState.spent / runtimeState.spend_cap) * 100 || 0, 100);
  elements.budgetFill.style.width = `${width}%`;
}

async function saveSpendCap() {
  const spendCap = Number(elements.spendCapInput.value);

  if (!Number.isFinite(spendCap) || spendCap <= 0) {
    updateTransactionCard("Policy rejected", "Enter a spend cap greater than zero before saving the rule.", "blocked");
    setTimeline([{ step: "Policy", detail: "Spend cap update failed validation in the browser." }]);
    return;
  }

  try {
    const payload = await apiPost("/policy", { spend_cap: spendCap });
    appState.state = payload.state;
    syncStateViews();
    updateTransactionCard("Policy updated", `Session cap is now ${formatAlgo(spendCap)}.`, "active");
    setTimeline([{ step: "Policy", detail: payload.message }]);
  } catch (error) {
    handleApiError(error, "Unable to save the spend cap.");
  }
}

async function generateIntent() {
  const objective = elements.intentInput.value.trim();

  if (!objective) {
    elements.intentOutput.textContent = "Add an objective first so Gemini can generate a compact purchase brief.";
    return;
  }

  try {
    elements.generateIntentButton.disabled = true;
    elements.intentOutput.textContent = "Generating a buyer brief...";
    const payload = await apiPost("/gemini/brief", {
      objective,
      service_id: appState.selectedServiceId
    });
    elements.intentOutput.textContent = payload.brief;
  } catch (error) {
    elements.intentOutput.textContent = `Unable to generate brief: ${error.message || error}`;
  } finally {
    elements.generateIntentButton.disabled = false;
  }
}

// ✅ Purchase flow — calls /api/purchase which triggers real blockchain payment
async function purchaseService(serviceId) {
  appState.selectedServiceId = serviceId;
  const service = appState.services.find((entry) => entry.id === serviceId);

  // Client-side policy pre-check
  const state = appState.state;
  if (state.spent + service.price > state.spend_cap) {
    updateTransactionCard(
      "Policy blocked",
      `Purchasing ${service.name} (${formatAlgo(service.price)}) would exceed your cap of ${formatAlgo(state.spend_cap)}.`,
      "blocked"
    );
    setTimeline([
      { step: "Discover", detail: `Selected ${service.name} — ${formatAlgo(service.price)}.` },
      { step: "Policy", detail: `Blocked: projected spend ${formatAlgo(state.spent + service.price)} exceeds cap ${formatAlgo(state.spend_cap)}.` }
    ]);
    return;
  }

  // Show pending state
  updateTransactionCard(
    "Payment in progress...",
    `Submitting on-chain ALGO payment for ${service.name}. Please wait.`,
    "active"
  );
  setTimeline([
    { step: "Discover", detail: `Selected ${service.name} from registry.` },
    { step: "Policy", detail: `Spend cap OK — within budget.` },
    { step: "Payment", detail: "Sending transaction to Algorand testnet..." }
  ]);

  try {
    // ✅ Call /api/purchase — backend handles payment + receipt + state update
    const payload = await apiPost("/purchase", {
      service_id: serviceId,
      objective: elements.intentInput.value.trim()
    });

    // Update local state from backend response
    appState.state = payload.state;
    syncStateViews();
    renderReceipts();
    updateTransactionCard(payload.summary.title, payload.summary.copy, payload.summary.tone);
    setTimeline(payload.timeline);

  } catch (error) {
    // If /api/purchase fails, fall back to direct /pay call
    console.warn("Purchase endpoint failed, trying direct /pay...", error.message);

    try {
      const payResponse = await fetch(PAY_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ address: service.payment_address })
      });
      const payResult = await payResponse.json();

      if (!payResponse.ok || payResult.status !== "success") {
        throw new Error(payResult.message || "Payment failed.");
      }

      const txId = payResult.txId;

      // Update state locally since backend didn't do it
      appState.state.spent += service.price;
      appState.state.receipts.unshift({
        service_name: service.name,
        cost: service.price,
        tx_id: txId,
        status: "Confirmed",
        response: service.response_preview,
        timestamp: new Date().toISOString()
      });

      syncStateViews();
      renderReceipts();

      updateTransactionCard(
        "Payment confirmed ✅",
        `${service.name} purchased. Transaction: ${truncateMiddle(txId, 8, 6)}`,
        "active"
      );
      setTimeline([
        { step: "Discover", detail: `Selected ${service.name}.` },
        { step: "Policy", detail: "Cap OK — within budget." },
        { step: "Payment", detail: `Sent ${formatAlgo(service.price)} on Algorand testnet.` },
        { step: "Confirm", detail: `Transaction ID: ${txId}` },
        { step: "Consume", detail: service.response_preview },
        { step: "Receipt", detail: `Logged at ${new Date().toLocaleTimeString()}.` }
      ]);

    } catch (payError) {
      updateTransactionCard(
        "Payment failed",
        `Could not complete purchase for ${service.name}: ${payError.message}`,
        "blocked"
      );
      setTimeline([
        { step: "Discover", detail: `Selected ${service.name}.` },
        { step: "Payment", detail: `Failed: ${payError.message}` }
      ]);
    }
  }
}

async function clearReceipts() {
  try {
    const payload = await apiPost("/receipts/clear", {});
    appState.state = payload.state;
    syncStateViews();
    renderReceipts();
    updateTransactionCard("Receipts cleared", "Receipt history and spend totals were reset on the backend.", "active");
    setTimeline([{ step: "Log", detail: payload.message }]);
  } catch (error) {
    handleApiError(error, "Unable to clear receipts.");
  }
}

function renderReceipts() {
  const receipts = appState.state.receipts;
  elements.receiptTableBody.innerHTML = "";

  if (!receipts.length) {
    elements.receiptTableBody.innerHTML = '<tr><td colspan="6" class="empty-state">No receipts yet. Complete a purchase to create an auditable log entry.</td></tr>';
    return;
  }

  receipts.forEach((receipt) => {
    const row = document.createElement("tr");
    const statusClass = receipt.status === "Confirmed" ? "status-badge--confirmed" : "status-badge--rejected";
    row.innerHTML = `
      <td>${receipt.service_name}</td>
      <td>${formatAlgo(receipt.cost)}</td>
      <td><code>${receipt.tx_id}</code></td>
      <td><span class="status-badge ${statusClass}">${receipt.status}</span></td>
      <td>${receipt.response}</td>
      <td>${formatTimestamp(receipt.timestamp)}</td>
    `;
    elements.receiptTableBody.appendChild(row);
  });
}

function updateTransactionCard(title, copy, tone) {
  elements.transactionCard.className = `transaction-card transaction-card--${tone}`;
  elements.transactionCard.innerHTML = `
    <p class="transaction-card__title">${title}</p>
    <p class="transaction-card__copy">${copy}</p>
  `;
}

function setTimeline(items) {
  elements.timeline.innerHTML = "";
  items.forEach(({ step, detail }) => appendTimelineStep(step, detail));
}

function appendTimelineStep(step, detail) {
  const item = document.createElement("li");
  item.innerHTML = `
    <span class="timeline__step">${step}</span>
    <div>${detail}</div>
  `;
  elements.timeline.appendChild(item);
}

async function apiGet(path) {
  const response = await fetch(`${API_BASE}${path}`);
  return parseResponse(response);
}

async function apiPost(path, body) {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
  return parseResponse(response);
}

async function parseResponse(response) {
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.error || `Request failed with status ${response.status}`);
  }
  return payload;
}

function handleApiError(error, fallbackMessage) {
  updateTransactionCard("Request failed", fallbackMessage, "blocked");
  setTimeline([{ step: "Error", detail: String(error.message || error) }]);
}

function formatAlgo(value) {
  return `${Number(value).toFixed(0)} ALGO`;
}

function formatTimestamp(isoString) {
  return new Date(isoString).toLocaleString("en-IN", {
    dateStyle: "medium",
    timeStyle: "short"
  });
}

function truncateMiddle(value, front = 6, back = 4) {
  if (!value || value.length <= front + back + 3) return value || "";
  return `${value.slice(0, front)}...${value.slice(-back)}`;
}

function readableEndpoint(url) {
  return url.replace(/^https?:\/\//, "").replace(/\/$/, "");
}
