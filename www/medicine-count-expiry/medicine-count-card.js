/**
 * Medicine Count & Expiry - Lovelace Custom Card
 * Displays medicine inventory with expiry tracking, search, and add/delete functionality.
 */

const BASE_URL = "/api/medicine_count_expiry";

class MedicineCountCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._medicines = [];
    this._filteredMedicines = [];
    this._summary = { total: 0, expired: 0, expiring_soon: 0, good: 0 };
    this._searchTerm = "";
    this._filterStatus = "all";
    this._filterLocation = "all";
    this._showAddForm = false;
    this._scanResult = null;
    this._loading = false;
    this._error = null;
    this._hass = null;
    this._config = {};
  }

  setConfig(config) {
    this._config = config;
    this.render();
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._initialized) {
      this._initialized = true;
      this._fetchData();
      // Refresh every 5 minutes
      this._refreshInterval = setInterval(() => this._fetchData(), 300000);
    }
  }

  disconnectedCallback() {
    if (this._refreshInterval) {
      clearInterval(this._refreshInterval);
    }
  }

  getCardSize() {
    return 6;
  }

  // ── Data fetching ─────────────────────────────────────────────────────────

  async _apiFetch(path, options = {}) {
    if (!this._hass) throw new Error("HA not connected");
    const response = await this._hass.fetchWithAuth(BASE_URL + path, options);
    if (!response.ok) {
      const err = await response.json().catch(() => ({ error: response.statusText }));
      throw new Error(err.error || `HTTP ${response.status}`);
    }
    return response.json();
  }

  async _fetchData() {
    this._loading = true;
    this._error = null;
    this.render();
    try {
      const [medicines, summary] = await Promise.all([
        this._apiFetch("/medicines"),
        this._apiFetch("/summary"),
      ]);
      this._medicines = medicines;
      this._summary = summary;
      this._applyFilters();
    } catch (e) {
      this._error = `Failed to load: ${e.message}`;
    } finally {
      this._loading = false;
      this.render();
    }
  }

  _applyFilters() {
    let result = [...this._medicines];
    if (this._searchTerm) {
      const term = this._searchTerm.toLowerCase();
      result = result.filter(
        (m) =>
          m.medicine_name.toLowerCase().includes(term) ||
          (m.description || "").toLowerCase().includes(term) ||
          (m.location || "").toLowerCase().includes(term)
      );
    }
    if (this._filterStatus !== "all") {
      result = result.filter((m) => m.status === this._filterStatus);
    }
    if (this._filterLocation !== "all") {
      result = result.filter((m) => m.location === this._filterLocation);
    }
    this._filteredMedicines = result;
  }

  // ── Actions ───────────────────────────────────────────────────────────────

  async _addMedicine(formData) {
    try {
      await this._apiFetch("/medicines", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(formData),
      });
      this._showAddForm = false;
      this._scanResult = null;
      await this._fetchData();
    } catch (e) {
      this._error = `Failed to add: ${e.message}`;
      this.render();
    }
  }

  async _deleteMedicine(id, name) {
    if (!confirm(`Delete "${name}"?`)) return;
    try {
      await this._apiFetch(`/medicines/${id}`, { method: "DELETE" });
      await this._fetchData();
    } catch (e) {
      this._error = `Failed to delete: ${e.message}`;
      this.render();
    }
  }

  async _scanImage(file) {
    this._loading = true;
    this._error = null;
    this.render();
    try {
      const result = await this._apiFetch("/scan", {
        method: "POST",
        headers: { "Content-Type": file.type || "image/jpeg" },
        body: file,
      });
      this._scanResult = result;
      this._showAddForm = true;
    } catch (e) {
      this._error = `Scan failed: ${e.message}`;
    } finally {
      this._loading = false;
      this.render();
    }
  }

  // ── Rendering ─────────────────────────────────────────────────────────────

  render() {
    const root = this.shadowRoot;
    root.innerHTML = `
      <style>${this._getStyles()}</style>
      <ha-card>
        <div class="card-header">
          <span class="card-title">${this._config.title || "💊 Medicine Inventory"}</span>
          <div class="header-actions">
            <button class="icon-btn refresh-btn" title="Refresh">⟳</button>
            <button class="icon-btn add-btn" title="Add Medicine">＋</button>
          </div>
        </div>
        <div class="card-content">
          ${this._loading ? '<div class="spinner-container"><div class="spinner"></div></div>' : ""}
          ${this._error ? `<div class="error-banner">${this._escHtml(this._error)}<button class="dismiss-error">✕</button></div>` : ""}
          ${this._renderSummary()}
          ${this._renderSearchBar()}
          ${this._renderMedicineList()}
        </div>
      </ha-card>
      ${this._showAddForm ? this._renderModal() : ""}
    `;
    this._attachEventListeners();
  }

  _renderModal() {
    const sr = this._scanResult || {};
    return `
      <div class="modal-backdrop">
        <div class="modal-dialog" role="dialog" aria-modal="true" aria-labelledby="modal-title">
          <div class="modal-header">
            <h3 class="modal-title" id="modal-title">Add Medicine</h3>
            <button class="icon-btn cancel-add" title="Close dialog">✕</button>
          </div>
          <div class="modal-body">
            ${sr.medicine_name || sr.expiry_date ? '<div class="scan-notice">✅ Pre-filled from scan result</div>' : ""}
            <div class="form-grid">
              <label class="form-label">
                Name <span class="required">*</span>
                <input class="form-input" name="medicine_name" type="text" required
                  value="${this._escHtml(sr.medicine_name || "")}" placeholder="e.g. Paracetamol 500mg" />
              </label>
              <label class="form-label">
                Expiry Date <span class="required">*</span>
                <input class="form-input" name="expiry_date" type="date" required
                  value="${this._escHtml(sr.expiry_date || "")}" />
              </label>
              <label class="form-label">
                Description
                <input class="form-input" name="description" type="text"
                  value="${this._escHtml(sr.description || "")}" placeholder="e.g. 500mg tablets" />
              </label>
              <label class="form-label">
                Quantity
                <input class="form-input" name="quantity" type="number" min="1" value="1" />
              </label>
              <label class="form-label">
                Location
                <input class="form-input" name="location" type="text"
                  value="" placeholder="e.g. bathroom" list="location-list" />
                <datalist id="location-list">
                  <option value="bathroom"/>
                  <option value="kitchen"/>
                  <option value="bedroom"/>
                  <option value="living room"/>
                  <option value="other"/>
                </datalist>
              </label>
              <label class="form-label">
                Unit
                <input class="form-input" name="unit" type="text"
                  value="" placeholder="e.g. tablets" list="unit-list" />
                <datalist id="unit-list">
                  <option value="tablets"/>
                  <option value="pills"/>
                  <option value="ml"/>
                  <option value="mg"/>
                  <option value="capsules"/>
                  <option value="drops"/>
                  <option value="units"/>
                </datalist>
              </label>
            </div>
          </div>
          <div class="modal-footer">
            <label class="scan-btn-label" title="Scan medicine label with camera">
              📷 Scan Label
              <input class="scan-input" type="file" accept="image/*" capture="environment" />
            </label>
            <div class="modal-actions">
              <button class="btn btn-secondary cancel-add">Cancel</button>
              <button class="btn btn-primary submit-add">Add Medicine</button>
            </div>
          </div>
        </div>
      </div>
    `;
  }

  _renderSummary() {
    const s = this._summary;
    return `
      <div class="summary-grid">
        <div class="summary-card total" data-filter="all">
          <div class="summary-value">${s.total}</div>
          <div class="summary-label">Total</div>
        </div>
        <div class="summary-card expired" data-filter="expired">
          <div class="summary-value">${s.expired}</div>
          <div class="summary-label">Expired</div>
        </div>
        <div class="summary-card expiring" data-filter="expiring_soon">
          <div class="summary-value">${s.expiring_soon}</div>
          <div class="summary-label">Expiring Soon</div>
        </div>
        <div class="summary-card good" data-filter="good">
          <div class="summary-value">${s.good}</div>
          <div class="summary-label">Good</div>
        </div>
      </div>
    `;
  }

  _renderSearchBar() {
    const locations = ["all", ...new Set(this._medicines.map((m) => m.location).filter(Boolean))];
    return `
      <div class="search-bar">
        <input
          class="search-input"
          type="text"
          placeholder="🔍 Search medicines..."
          value="${this._escHtml(this._searchTerm)}"
        />
        <select class="filter-select status-filter">
          <option value="all" ${this._filterStatus === "all" ? "selected" : ""}>All Status</option>
          <option value="good" ${this._filterStatus === "good" ? "selected" : ""}>Good</option>
          <option value="expiring_soon" ${this._filterStatus === "expiring_soon" ? "selected" : ""}>Expiring Soon</option>
          <option value="expired" ${this._filterStatus === "expired" ? "selected" : ""}>Expired</option>
        </select>
        <select class="filter-select location-filter">
          ${locations
            .map(
              (loc) =>
                `<option value="${this._escHtml(loc)}" ${this._filterLocation === loc ? "selected" : ""}>${this._escHtml(loc === "all" ? "All Locations" : loc)}</option>`
            )
            .join("")}
        </select>
      </div>
    `;
  }

  _renderMedicineList() {
    if (!this._loading && this._filteredMedicines.length === 0) {
      return `<div class="empty-state">
        <div class="empty-icon">💊</div>
        <p>${
          this._medicines.length === 0
            ? "No medicines tracked yet. Click ＋ to add one."
            : "No medicines match your search."
        }</p>
      </div>`;
    }

    return `
      <div class="medicine-list">
        <div class="list-header">
          <span>${this._filteredMedicines.length} medicine${this._filteredMedicines.length !== 1 ? "s" : ""}</span>
        </div>
        ${this._filteredMedicines.map((m) => this._renderMedicineItem(m)).join("")}
      </div>
    `;
  }

  _renderMedicineItem(m) {
    const statusClass = m.status === "expired" ? "status-expired"
      : m.status === "expiring_soon" ? "status-expiring"
      : "status-good";
    const statusLabel = m.status === "expired" ? "Expired"
      : m.status === "expiring_soon" ? "Expiring Soon"
      : "Good";
    const daysInfo = this._getDaysInfo(m.expiry_date);

    return `
      <div class="medicine-item ${statusClass}" data-id="${m.medicine_id}">
        <div class="medicine-status-bar"></div>
        <div class="medicine-body">
          <div class="medicine-main">
            <div class="medicine-name">${this._escHtml(m.medicine_name)}</div>
            <div class="medicine-meta">
              ${m.description ? `<span class="meta-chip">${this._escHtml(m.description)}</span>` : ""}
              <span class="meta-chip">📍 ${this._escHtml(m.location || "unknown")}</span>
              <span class="meta-chip">📦 ×${m.quantity}</span>
              ${m.ai_verified ? `<span class="meta-chip ai-verified" title="AI verified (${Math.round((m.confidence_score || 0) * 100)}% confidence)">🤖 Verified</span>` : ""}
            </div>
          </div>
          <div class="medicine-expiry">
            <div class="expiry-date">${this._escHtml(m.expiry_date)}</div>
            <div class="expiry-days ${statusClass}">${daysInfo}</div>
            <span class="status-badge ${statusClass}">${statusLabel}</span>
          </div>
          <button class="delete-btn icon-btn" data-id="${m.medicine_id}" data-name="${this._escHtml(m.medicine_name)}" title="Delete">🗑</button>
        </div>
      </div>
    `;
  }

  _getDaysInfo(expiryDate) {
    try {
      const today = new Date();
      today.setHours(0, 0, 0, 0);
      const expiry = new Date(expiryDate);
      expiry.setHours(0, 0, 0, 0);
      const days = Math.round((expiry - today) / 86400000);
      if (days < 0) return `${Math.abs(days)}d overdue`;
      if (days === 0) return "Expires today";
      if (days === 1) return "1 day left";
      return `${days} days left`;
    } catch {
      return "";
    }
  }

  _escHtml(str) {
    if (str == null) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  // ── Event listeners ───────────────────────────────────────────────────────

  _attachEventListeners() {
    const root = this.shadowRoot;

    root.querySelector(".refresh-btn")?.addEventListener("click", () => this._fetchData());
    root.querySelector(".add-btn")?.addEventListener("click", () => {
      this._showAddForm = !this._showAddForm;
      this._scanResult = null;
      this.render();
    });
    root.querySelector(".cancel-add")?.addEventListener("click", () => {
      this._showAddForm = false;
      this._scanResult = null;
      this.render();
    });

    root.querySelector(".dismiss-error")?.addEventListener("click", () => {
      this._error = null;
      this.render();
    });

    // Summary cards as filters
    root.querySelectorAll(".summary-card[data-filter]").forEach((el) => {
      el.addEventListener("click", () => {
        this._filterStatus = el.dataset.filter;
        this._applyFilters();
        this.render();
      });
    });

    // Search
    root.querySelector(".search-input")?.addEventListener("input", (e) => {
      this._searchTerm = e.target.value;
      this._applyFilters();
      this.render();
    });

    // Status filter
    root.querySelector(".status-filter")?.addEventListener("change", (e) => {
      this._filterStatus = e.target.value;
      this._applyFilters();
      this.render();
    });

    // Location filter
    root.querySelector(".location-filter")?.addEventListener("change", (e) => {
      this._filterLocation = e.target.value;
      this._applyFilters();
      this.render();
    });

    // Delete buttons
    root.querySelectorAll(".delete-btn").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        this._deleteMedicine(btn.dataset.id, btn.dataset.name);
      });
    });

    // Scan image
    root.querySelector(".scan-input")?.addEventListener("change", (e) => {
      const file = e.target.files[0];
      if (file) this._scanImage(file);
    });

    // Submit add form
    root.querySelector(".submit-add")?.addEventListener("click", () => {
      const form = root.querySelector(".modal-body") || root.querySelector(".add-form");
      const getValue = (name) => form.querySelector(`[name="${name}"]`)?.value?.trim() || "";

      const name = getValue("medicine_name");
      const expiry = getValue("expiry_date");
      if (!name || !expiry) {
        this._error = "Medicine name and expiry date are required.";
        this.render();
        return;
      }

      this._addMedicine({
        medicine_name: name,
        expiry_date: expiry,
        description: getValue("description"),
        quantity: parseInt(getValue("quantity") || "1", 10),
        location: getValue("location") || "unknown",
        unit: getValue("unit") || "tablets",
      });
    });
  }

  _getStyles() {
    return `
      ha-card {
        font-family: var(--paper-font-body1_-_font-family, sans-serif);
        --color-expired: #e53935;
        --color-expiring: #f57c00;
        --color-good: #43a047;
        --color-total: #1e88e5;
      }
      .card-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 16px 16px 8px;
        border-bottom: 1px solid var(--divider-color, #e0e0e0);
      }
      .card-title { font-size: 1.1rem; font-weight: 600; }
      .header-actions { display: flex; gap: 8px; }
      .card-content { padding: 12px 16px 16px; }

      /* Spinner */
      .spinner-container { display: flex; justify-content: center; padding: 16px; }
      .spinner {
        width: 32px; height: 32px;
        border: 3px solid var(--divider-color, #e0e0e0);
        border-top-color: var(--primary-color, #03a9f4);
        border-radius: 50%;
        animation: spin 0.8s linear infinite;
      }
      @keyframes spin { to { transform: rotate(360deg); } }

      /* Error */
      .error-banner {
        display: flex; align-items: center; justify-content: space-between;
        background: #fdecea; color: #b71c1c;
        padding: 8px 12px; border-radius: 6px; margin-bottom: 12px;
        font-size: 0.875rem;
      }

      /* Summary */
      .summary-grid {
        display: grid; grid-template-columns: repeat(4, 1fr);
        gap: 8px; margin-bottom: 16px;
      }
      .summary-card {
        text-align: center; padding: 10px 4px; border-radius: 8px;
        cursor: pointer; transition: transform 0.1s, box-shadow 0.1s;
        border: 2px solid transparent;
      }
      .summary-card:hover { transform: translateY(-1px); box-shadow: 0 2px 8px rgba(0,0,0,.12); }
      .summary-card.total { background: #e3f2fd; border-color: #1e88e5; }
      .summary-card.expired { background: #ffebee; border-color: #e53935; }
      .summary-card.expiring { background: #fff3e0; border-color: #f57c00; }
      .summary-card.good { background: #e8f5e9; border-color: #43a047; }
      .summary-value { font-size: 1.6rem; font-weight: 700; }
      .summary-label { font-size: 0.7rem; color: #555; margin-top: 2px; text-transform: uppercase; letter-spacing: 0.04em; }
      .summary-card.total .summary-value { color: var(--color-total); }
      .summary-card.expired .summary-value { color: var(--color-expired); }
      .summary-card.expiring .summary-value { color: var(--color-expiring); }
      .summary-card.good .summary-value { color: var(--color-good); }

      /* Search bar */
      .search-bar {
        display: flex; gap: 8px; margin-bottom: 12px; flex-wrap: wrap;
      }
      .search-input {
        flex: 1; min-width: 140px;
        padding: 7px 10px; border: 1px solid var(--divider-color, #ccc);
        border-radius: 6px; font-size: 0.875rem;
        background: var(--card-background-color, #fff);
        color: var(--primary-text-color, #212121);
      }
      .filter-select {
        padding: 7px 8px; border: 1px solid var(--divider-color, #ccc);
        border-radius: 6px; font-size: 0.8rem;
        background: var(--card-background-color, #fff);
        color: var(--primary-text-color, #212121);
        cursor: pointer;
      }

      /* Buttons */
      .icon-btn {
        background: none; border: none; cursor: pointer;
        font-size: 1.1rem; padding: 4px 8px; border-radius: 4px;
        color: var(--secondary-text-color, #555);
        transition: background 0.15s;
      }
      .icon-btn:hover { background: var(--secondary-background-color, #f5f5f5); }
      .btn {
        padding: 8px 16px; border: none; border-radius: 6px;
        font-size: 0.875rem; cursor: pointer; font-weight: 500;
        transition: opacity 0.15s;
      }
      .btn:hover { opacity: 0.85; }
      .btn-primary { background: var(--primary-color, #03a9f4); color: #fff; }

      /* Modal */
      .modal-backdrop {
        position: fixed; inset: 0;
        background: rgba(0, 0, 0, 0.5);
        display: flex; align-items: center; justify-content: center;
        z-index: 999; padding: 16px; box-sizing: border-box;
      }
      .modal-dialog {
        background: var(--card-background-color, #fff);
        border-radius: 12px;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.24);
        width: 100%; max-width: 520px;
        max-height: 90vh; overflow-y: auto;
        display: flex; flex-direction: column;
      }
      .modal-header {
        display: flex; align-items: center; justify-content: space-between;
        padding: 16px 20px 12px;
        border-bottom: 1px solid var(--divider-color, #e0e0e0);
        position: sticky; top: 0;
        background: var(--card-background-color, #fff);
        z-index: 1;
      }
      .modal-title { margin: 0; font-size: 1.1rem; font-weight: 600; }
      .modal-body { padding: 16px 20px; flex: 1; }
      .modal-footer {
        display: flex; align-items: center; justify-content: space-between;
        padding: 12px 20px 16px;
        border-top: 1px solid var(--divider-color, #e0e0e0);
        flex-wrap: wrap; gap: 10px;
        position: sticky; bottom: 0;
        background: var(--card-background-color, #fff);
      }
      .modal-actions { display: flex; gap: 10px; }
      .btn-secondary {
        background: var(--secondary-background-color, #f5f5f5);
        color: var(--primary-text-color, #212121);
        border: 1px solid var(--divider-color, #ccc);
      }

      /* Add form (used inside modal) */
      .add-form {
        background: var(--secondary-background-color, #f9f9f9);
        border: 1px solid var(--divider-color, #ddd);
        border-radius: 8px; padding: 14px; margin-bottom: 16px;
      }
      .form-header {
        display: flex; align-items: center; justify-content: space-between;
        margin-bottom: 12px;
      }
      .form-header h3 { margin: 0; font-size: 1rem; }
      .scan-notice {
        background: #e8f5e9; color: #2e7d32;
        padding: 6px 10px; border-radius: 4px; font-size: 0.8rem; margin-bottom: 10px;
      }
      .form-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 12px; margin-bottom: 12px; }
      .form-grid label, .form-label { display: flex; flex-direction: column; font-size: 0.85rem; color: var(--secondary-text-color, #555); gap: 5px; }
      .form-input {
        padding: 7px 9px; border: 1px solid var(--divider-color, #ccc);
        border-radius: 5px; font-size: 0.875rem;
        background: var(--card-background-color, #fff);
        color: var(--primary-text-color, #212121);
      }
      .required { color: #e53935; }
      .form-actions { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
      .scan-btn-label {
        display: inline-flex; align-items: center; gap: 6px;
        padding: 7px 14px; border: 1px solid var(--divider-color, #ccc);
        border-radius: 6px; font-size: 0.8rem; cursor: pointer;
        background: var(--card-background-color, #fff);
        transition: background 0.15s;
      }
      .scan-btn-label:hover { background: var(--secondary-background-color, #f5f5f5); }
      .scan-input { display: none; }

      /* Medicine list */
      .list-header {
        font-size: 0.75rem; color: var(--secondary-text-color, #777);
        margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.05em;
      }
      .medicine-list { display: flex; flex-direction: column; gap: 8px; }
      .medicine-item {
        display: flex; align-items: stretch;
        border-radius: 8px; overflow: hidden;
        border: 1px solid var(--divider-color, #e0e0e0);
        background: var(--card-background-color, #fff);
        transition: box-shadow 0.15s;
      }
      .medicine-item:hover { box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
      .medicine-status-bar { width: 5px; flex-shrink: 0; }
      .status-expired .medicine-status-bar { background: var(--color-expired); }
      .status-expiring .medicine-status-bar { background: var(--color-expiring); }
      .status-good .medicine-status-bar { background: var(--color-good); }
      .medicine-body {
        display: flex; align-items: center; flex: 1;
        padding: 10px 12px; gap: 8px;
      }
      .medicine-main { flex: 1; min-width: 0; }
      .medicine-name {
        font-weight: 600; font-size: 0.95rem;
        white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
      }
      .medicine-meta { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 4px; }
      .meta-chip {
        font-size: 0.7rem; padding: 2px 7px; border-radius: 12px;
        background: var(--secondary-background-color, #f0f0f0);
        color: var(--secondary-text-color, #555);
      }
      .ai-verified { background: #e8f5e9; color: #2e7d32; }
      .medicine-expiry { text-align: right; flex-shrink: 0; margin-right: 8px; }
      .expiry-date { font-size: 0.8rem; color: var(--secondary-text-color, #666); }
      .expiry-days { font-size: 0.75rem; font-weight: 600; margin-top: 2px; }
      .expiry-days.status-expired { color: var(--color-expired); }
      .expiry-days.status-expiring { color: var(--color-expiring); }
      .expiry-days.status-good { color: var(--color-good); }
      .status-badge {
        display: inline-block; font-size: 0.65rem; padding: 2px 7px;
        border-radius: 12px; margin-top: 3px; font-weight: 600; text-transform: uppercase;
      }
      .status-badge.status-expired { background: #ffebee; color: var(--color-expired); }
      .status-badge.status-expiring { background: #fff3e0; color: var(--color-expiring); }
      .status-badge.status-good { background: #e8f5e9; color: var(--color-good); }
      .delete-btn { color: #bbb; font-size: 0.95rem; }
      .delete-btn:hover { color: var(--color-expired); background: #ffebee; }

      /* Empty state */
      .empty-state { text-align: center; padding: 32px 16px; color: var(--secondary-text-color, #888); }
      .empty-icon { font-size: 2.5rem; margin-bottom: 8px; }

      @media (max-width: 400px) {
        .summary-grid { grid-template-columns: repeat(2, 1fr); }
        .search-bar { flex-direction: column; }
        .form-grid { grid-template-columns: 1fr; }
      }
    `;
  }

  static getConfigElement() {
    return document.createElement("medicine-count-card-editor");
  }

  static getStubConfig() {
    return { type: "medicine-count-card" };
  }
}

customElements.define("medicine-count-card", MedicineCountCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "medicine-count-card",
  name: "Medicine Count & Expiry",
  description: "Track your medicine inventory and expiry dates",
  preview: true,
});
