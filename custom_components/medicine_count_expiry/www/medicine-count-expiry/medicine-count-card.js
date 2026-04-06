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
    this._scanCount = 0;
    this._loading = false;
    this._error = null;
    this._hass = null;
    this._config = {};
    this._selectedMedicine = null;
    this._leafletLoading = false;
    // Opening date tracking state
    this._showOpenDateSection = false;
    this._pendingOpenDate = "";
    this._pendingOpenDays = "";
    this._extractingOpenDays = false;
    // Multi-step form state
    this._addStep = 1;
    this._labelScanning = false;
    this._expiryScanning = false;
    this._expiryInputMethod = "manual";
    this._formData = {};
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
      this._scanCount = 0;
      this._addStep = 1;
      this._labelScanning = false;
      this._expiryScanning = false;
      this._expiryInputMethod = "manual";
      this._formData = {};
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
      if (this._scanResult && this._scanCount > 0) {
        // Merge: keep value from scan with highest confidence for each field
        this._scanResult = this._mergeScans(this._scanResult, result);
      } else {
        this._scanResult = result;
      }
      this._scanCount += 1;
      this._showAddForm = true;
    } catch (e) {
      this._error = `Scan failed: ${e.message}`;
    } finally {
      this._loading = false;
      this.render();
    }
  }

  async _scanLabelImage(file) {
    this._labelScanning = true;
    this._error = null;
    this.render();
    try {
      const result = await this._apiFetch("/scan/label", {
        method: "POST",
        headers: { "Content-Type": file.type || "image/jpeg" },
        body: file,
      });
      this._formData = {
        ...this._formData,
        medicine_name: result.medicine_name || this._formData.medicine_name || "",
        description: result.description || this._formData.description || "",
        labelConfidence: result.confidence || {},
      };
    } catch (e) {
      this._error = `Label scan failed: ${e.message}`;
    } finally {
      this._labelScanning = false;
      this.render();
    }
  }

  async _scanExpiryImage(file) {
    this._expiryScanning = true;
    this._error = null;
    this.render();
    try {
      const result = await this._apiFetch("/scan/expiry", {
        method: "POST",
        headers: { "Content-Type": file.type || "image/jpeg" },
        body: file,
      });
      this._formData = {
        ...this._formData,
        expiry_date: result.expiry_date || this._formData.expiry_date || "",
        rawExpiryText: result.raw_expiry_text || "",
        expiryConfidence: result.confidence || {},
      };
    } catch (e) {
      this._error = `Expiry scan failed: ${e.message}`;
    } finally {
      this._expiryScanning = false;
      this.render();
    }
  }

  _mergeScans(prev, next) {
    const prevConf = prev.confidence || {};
    const nextConf = next.confidence || {};
    const merged = { ...prev };
    const mergedConf = { ...prevConf };
    const fields = ["medicine_name", "expiry_date", "description"];
    for (const field of fields) {
      const pc = prevConf[field] || 0;
      const nc = nextConf[field] || 0;
      if (nc > pc && next[field] !== null && next[field] !== undefined) {
        merged[field] = next[field];
        mergedConf[field] = nc;
      }
    }
    merged.confidence = mergedConf;
    // Keep verification data from whichever scan has higher overall confidence
    const prevOverall = prev.overall_confidence || 0;
    const nextOverall = next.overall_confidence || 0;
    if (nextOverall >= prevOverall && next.verification) {
      merged.verification = next.verification;
      merged.verified = next.verified;
      merged.overall_confidence = nextOverall;
    }
    return merged;
  }

  async _openDetail(medicine) {
    this._selectedMedicine = medicine;
    this._leafletLoading = false;
    this._showOpenDateSection = false;
    this._pendingOpenDate = medicine.date_opened || "";
    this._pendingOpenDays = medicine.days_valid_after_opening != null ? String(medicine.days_valid_after_opening) : "";
    this._extractingOpenDays = false;
    this.render();
  }

  _closeDetail() {
    this._selectedMedicine = null;
    this._leafletLoading = false;
    this._showOpenDateSection = false;
    this._pendingOpenDate = "";
    this._pendingOpenDays = "";
    this._extractingOpenDays = false;
    this.render();
  }

  async _saveOpenDate(medicineId) {
    const dateOpened = this._pendingOpenDate;
    if (!dateOpened) {
      this._error = "Please select a date opened.";
      this.render();
      return;
    }
    const days = this._pendingOpenDays ? parseInt(this._pendingOpenDays, 10) : null;
    if (this._pendingOpenDays && (isNaN(days) || days < 1)) {
      this._error = "Days valid after opening must be a positive number.";
      this.render();
      return;
    }
    try {
      const updated = await this._apiFetch(`/medicines/${medicineId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          date_opened: dateOpened,
          days_valid_after_opening: days,
        }),
      });
      this._selectedMedicine = updated;
      this._medicines = this._medicines.map((m) =>
        m.medicine_id === medicineId ? updated : m
      );
      this._applyFilters();
      this._showOpenDateSection = false;
    } catch (e) {
      this._error = `Failed to save opening date: ${e.message}`;
    }
    this.render();
  }

  async _extractOpenDays(medicineId) {
    this._extractingOpenDays = true;
    this.render();
    try {
      const result = await this._apiFetch(`/medicines/${medicineId}/extract_open_days`, {
        method: "POST",
      });
      if (result.days_valid_after_opening != null) {
        this._pendingOpenDays = String(result.days_valid_after_opening);
      } else {
        this._error = "Claude could not determine the days valid after opening for this medicine.";
      }
    } catch (e) {
      this._error = `Failed to extract days: ${e.message}`;
    } finally {
      this._extractingOpenDays = false;
      this.render();
    }
  }

  async _clearOpenDate(medicineId) {
    try {
      const updated = await this._apiFetch(`/medicines/${medicineId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          date_opened: null,
          days_valid_after_opening: null,
        }),
      });
      this._selectedMedicine = updated;
      this._medicines = this._medicines.map((m) =>
        m.medicine_id === medicineId ? updated : m
      );
      this._applyFilters();
      this._pendingOpenDate = "";
      this._pendingOpenDays = "";
      this._showOpenDateSection = false;
    } catch (e) {
      this._error = `Failed to clear opening date: ${e.message}`;
    }
    this.render();
  }

  async _generateLeaflet(medicineId) {
    this._leafletLoading = true;
    this.render();
    try {
      const result = await this._apiFetch(`/medicines/${medicineId}/leaflet`, {
        method: "POST",
      });
      // Update the selected medicine and the medicines list with fresh data
      const updated = await this._apiFetch(`/medicines/${medicineId}`);
      this._selectedMedicine = updated;
      this._medicines = this._medicines.map((m) =>
        m.medicine_id === medicineId ? updated : m
      );
      this._applyFilters();
    } catch (e) {
      this._error = `Failed to generate leaflet: ${e.message}`;
    } finally {
      this._leafletLoading = false;
      this.render();
    }
  }

  _computeOverallConfidence() {
    const lc = this._formData.labelConfidence || {};
    const ec = this._formData.expiryConfidence || {};
    const nameConf = lc.medicine_name || 0.0;
    const descConf = lc.description || 0.0;
    const expiryConf = ec.expiry_date || 0.0;
    // Weighted average: name 40%, description 30%, expiry 30%
    return nameConf * 0.4 + descConf * 0.3 + expiryConf * 0.3;
  }

  _getConfidenceBadge(score) {
    if (score === null || score === undefined || isNaN(score)) return "";
    const pct = Math.round(score * 100);
    const cls = score >= 0.95 ? "conf-excellent"
      : score >= 0.85 ? "conf-good"
      : score >= 0.75 ? "conf-fair"
      : "conf-low-badge";
    return `<span class="confidence-badge ${cls}" title="AI confidence: ${pct}%">${pct}%</span>`;
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
      ${this._selectedMedicine ? this._renderDetailPanel() : ""}
    `;
    this._attachEventListeners();
  }

  _renderModal() {
    const stepTitles = ["Scan Medicine Label", "Enter Expiry Date", "Other Details"];
    const title = stepTitles[this._addStep - 1] || "Add Medicine";
    return `
      <div class="modal-backdrop">
        <div class="modal-dialog" role="dialog" aria-modal="true" aria-labelledby="modal-title">
          <div class="modal-header">
            <h3 class="modal-title" id="modal-title">Add Medicine</h3>
            <button class="icon-btn cancel-add" title="Close dialog">✕</button>
          </div>
          <div class="modal-body">
            ${this._renderStepProgress()}
            <div class="step-title">${title}</div>
            ${this._addStep === 1 ? this._renderStep1() : ""}
            ${this._addStep === 2 ? this._renderStep2() : ""}
            ${this._addStep === 3 ? this._renderStep3() : ""}
          </div>
          <div class="modal-footer">
            <div class="modal-nav">
              ${this._addStep > 1 ? '<button class="btn btn-secondary step-back-btn">← Back</button>' : '<div></div>'}
              ${this._addStep < 3
                ? '<button class="btn btn-primary step-next-btn">Next Step →</button>'
                : '<button class="btn btn-primary submit-add">Add Medicine</button>'}
            </div>
          </div>
        </div>
      </div>
    `;
  }

  _renderStepProgress() {
    const labels = ["Label", "Expiry", "Details"];
    return `
      <div class="step-progress">
        ${labels.map((label, i) => {
          const step = i + 1;
          const cls = step < this._addStep ? "done" : step === this._addStep ? "active" : "";
          return `
            ${i > 0 ? `<div class="step-line ${step <= this._addStep ? 'active' : ''}"></div>` : ""}
            <div class="step-dot ${cls}">
              <span>${step < this._addStep ? "✓" : step}</span>
              <div class="step-dot-label">${label}</div>
            </div>`;
        }).join("")}
      </div>
    `;
  }

  _renderStep1() {
    const fd = this._formData;
    const nameConf = Math.round(((fd.labelConfidence || {}).medicine_name || 0) * 100);
    const descConf = Math.round(((fd.labelConfidence || {}).description || 0) * 100);
    const hasLabelScan = !!(fd.medicine_name || fd.description);

    return `
      <div class="step-content">
        <p class="step-instruction">Take a photo of the medicine box/label. Claude will extract the name and description automatically.</p>
        <div class="scan-row">
          <label class="scan-btn-label${this._labelScanning ? " loading" : ""}">
            ${this._labelScanning
              ? '<div class="spinner spinner-sm"></div> Scanning…'
              : hasLabelScan ? "📷 Re-scan Label" : "📷 Scan Label"}
            <input class="label-scan-input" type="file" accept="image/*" capture="environment"
              ${this._labelScanning ? "disabled" : ""} />
          </label>
        </div>
        ${hasLabelScan ? `<div class="scan-notice">✅ Extracted from label scan</div>` : ""}
        <div class="form-grid">
          <label class="form-label">
            Medicine Name <span class="required">*</span>
            <input class="form-input" name="medicine_name" type="text"
              value="${this._escHtml(fd.medicine_name || "")}"
              placeholder="Scan label to extract name" />
            ${nameConf > 0 ? `<span class="conf-indicator${nameConf < 70 ? " conf-low" : " conf-ok"}">${nameConf}% confidence${nameConf < 70 ? " ⚠️" : " ✓"}</span>` : ""}
          </label>
          <label class="form-label">
            Description
            <input class="form-input" name="description" type="text"
              value="${this._escHtml(fd.description || "")}"
              placeholder="e.g. 500mg tablets" />
            ${descConf > 0 ? `<span class="conf-indicator${descConf < 70 ? " conf-low" : " conf-ok"}">${descConf}% confidence${descConf < 70 ? " ⚠️" : " ✓"}</span>` : ""}
          </label>
        </div>
      </div>
    `;
  }

  _renderStep2() {
    const fd = this._formData;
    const expiryConf = Math.round(((fd.expiryConfidence || {}).expiry_date || 0) * 100);
    const isScanMode = this._expiryInputMethod === "scan";

    return `
      <div class="step-content">
        <p class="step-instruction">Enter the expiry date for <strong>${this._escHtml(fd.medicine_name || "this medicine")}</strong>.</p>
        <div class="expiry-tabs">
          <button class="expiry-tab${!isScanMode ? " active" : ""}" data-method="manual">📅 Enter Manually</button>
          <button class="expiry-tab${isScanMode ? " active" : ""}" data-method="scan">📷 Scan Expiry</button>
        </div>
        ${!isScanMode ? `
          <div class="form-grid">
            <label class="form-label">
              Expiry Date <span class="required">*</span>
              <input class="form-input" name="expiry_date" type="date"
                value="${this._escHtml(fd.expiry_date || "")}" />
            </label>
          </div>
        ` : `
          <div class="scan-row">
            <label class="scan-btn-label${this._expiryScanning ? " loading" : ""}">
              ${this._expiryScanning
                ? '<div class="spinner spinner-sm"></div> Scanning…'
                : fd.expiry_date ? "📷 Re-scan Expiry" : "📷 Scan Expiry Date"}
              <input class="expiry-scan-input" type="file" accept="image/*" capture="environment"
                ${this._expiryScanning ? "disabled" : ""} />
            </label>
          </div>
          ${fd.expiry_date ? `
            <div class="scan-notice">
              ✅ Extracted: <strong>${this._escHtml(fd.expiry_date)}</strong>
              ${fd.rawExpiryText ? ` <span class="raw-text">(${this._escHtml(fd.rawExpiryText)})</span>` : ""}
              ${expiryConf > 0 ? `<span class="conf-indicator${expiryConf < 70 ? " conf-low" : " conf-ok"}">${expiryConf}%${expiryConf < 70 ? " ⚠️" : " ✓"}</span>` : ""}
            </div>
            <div class="form-grid">
              <label class="form-label">
                Confirm Expiry Date <span class="required">*</span>
                <input class="form-input" name="expiry_date" type="date"
                  value="${this._escHtml(fd.expiry_date || "")}" />
              </label>
            </div>
          ` : `<p class="step-hint">📷 Take a close-up photo of the expiry date on the medicine box.</p>`}
        `}
      </div>
    `;
  }

  _renderStep3() {
    return `
      <div class="step-content">
        <p class="step-instruction">Optionally add location, quantity and unit information.</p>
        <div class="form-grid">
          <label class="form-label">
            Location
            <input class="form-input" name="location" type="text"
              value="${this._escHtml(this._formData.location || "")}"
              placeholder="e.g. bathroom" list="location-list" />
            <datalist id="location-list">
              <option value="bathroom"/>
              <option value="kitchen"/>
              <option value="bedroom"/>
              <option value="living room"/>
              <option value="other"/>
            </datalist>
          </label>
          <label class="form-label">
            Quantity
            <input class="form-input" name="quantity" type="number" min="1"
              value="${parseInt(this._formData.quantity || "1", 10) || 1}" />
          </label>
          <label class="form-label">
            Unit
            <input class="form-input" name="unit" type="text"
              value="${this._escHtml(this._formData.unit || "")}"
              placeholder="e.g. tablets" list="unit-list" />
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
    `;
  }

  _renderScanNotice(hasScanned, scanResult) {
    if (!hasScanned && !scanResult.medicine_name && !scanResult.expiry_date) return "";
    const confidence = scanResult.overall_confidence || 0;
    const isLowConfidence = scanResult.verification && confidence < 0.7;
    const confidenceHtml = scanResult.verification
      ? `<div class="confidence-display">
           Confidence: ${Math.round(confidence * 100)}%
           ${isLowConfidence ? '<span class="confidence-warning">⚠️ Low confidence – please verify</span>' : ""}
         </div>`
      : "";
    const label = hasScanned
      ? `✅ Pre-filled from scan result (scan #${this._scanCount})`
      : "✅ Pre-filled from scan result";
    return `<div class="scan-notice">${label}${confidenceHtml}</div>`;
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
      : m.status === "opened_too_long" ? "status-opened-too-long"
      : "status-good";
    const statusLabel = m.status === "expired" ? "Expired"
      : m.status === "expiring_soon" ? "Expiring Soon"
      : m.status === "opened_too_long" ? "Opened Too Long"
      : "Good";
    const daysInfo = this._getDaysInfo(m.expiry_date);
    const hasLeaflet = m.ai_leaflet ? ' title="Leaflet available – click for details"' : "";
    const confidenceBadge = m.confidence_score != null ? this._getConfidenceBadge(m.confidence_score) : "";

    return `
      <div class="medicine-item ${statusClass} clickable-item" data-id="${this._escHtml(m.medicine_id)}"${hasLeaflet}>
        <div class="medicine-status-bar"></div>
        <div class="medicine-body">
          <div class="medicine-main">
            <div class="medicine-name">${this._escHtml(m.medicine_name)}${confidenceBadge}</div>
            <div class="medicine-meta">
              ${m.description ? `<span class="meta-chip">${this._escHtml(m.description)}</span>` : ""}
              <span class="meta-chip">📍 ${this._escHtml(m.location || "unknown")}</span>
              <span class="meta-chip">📦 ×${m.quantity}</span>
              ${m.ai_verified ? `<span class="meta-chip ai-verified" title="AI verified (${Math.round((m.confidence_score || 0) * 100)}% confidence)">🤖 Verified</span>` : ""}
              ${m.ai_leaflet ? '<span class="meta-chip leaflet-chip">🇸🇰 Leaflet</span>' : ""}
              ${m.date_opened ? '<span class="meta-chip opened-chip">📂 Opened</span>' : ""}
            </div>
          </div>
          <div class="medicine-expiry">
            <div class="expiry-date">${this._escHtml(m.expiry_date)}</div>
            <div class="expiry-days ${statusClass}">${daysInfo}</div>
            <span class="status-badge ${statusClass}">${statusLabel}</span>
          </div>
          <button class="delete-btn icon-btn" data-id="${this._escHtml(m.medicine_id)}" data-name="${this._escHtml(m.medicine_name)}" title="Delete">🗑</button>
        </div>
      </div>
    `;
  }

  _renderDetailPanel() {
    const m = this._selectedMedicine;
    if (!m) return "";
    const statusClass = m.status === "expired" ? "status-expired"
      : m.status === "expiring_soon" ? "status-expiring"
      : m.status === "opened_too_long" ? "status-opened-too-long"
      : "status-good";
    const statusLabel = m.status === "expired" ? "❌ Expired"
      : m.status === "expiring_soon" ? "⚠️ Expiring Soon"
      : m.status === "opened_too_long" ? "⚠️ Opened Too Long"
      : "✅ Good";
    const daysInfo = this._getDaysInfo(m.expiry_date);

    return `
      <div class="modal-backdrop detail-backdrop">
        <div class="modal-dialog detail-dialog" role="dialog" aria-modal="true" aria-labelledby="detail-title">
          <div class="modal-header">
            <h3 class="modal-title" id="detail-title">💊 ${this._escHtml(m.medicine_name)}</h3>
            <button class="icon-btn close-detail" title="Close">✕</button>
          </div>
          <div class="modal-body detail-body">
            <div class="detail-info-grid">
              <div class="detail-field">
                <span class="detail-label">Expiry Date</span>
                <span class="detail-value">${this._escHtml(m.expiry_date)}</span>
              </div>
              <div class="detail-field">
                <span class="detail-label">Status</span>
                <span class="status-badge ${statusClass}">${statusLabel}</span>
              </div>
              <div class="detail-field">
                <span class="detail-label">Days</span>
                <span class="detail-value expiry-days ${statusClass}">${daysInfo}</span>
              </div>
              <div class="detail-field">
                <span class="detail-label">Location</span>
                <span class="detail-value">📍 ${this._escHtml(m.location || "unknown")}</span>
              </div>
              <div class="detail-field">
                <span class="detail-label">Quantity</span>
                <span class="detail-value">📦 ${m.quantity}${m.unit ? " " + this._escHtml(m.unit) : ""}</span>
              </div>
              ${m.description ? `<div class="detail-field detail-field-wide">
                <span class="detail-label">Description</span>
                <span class="detail-value">${this._escHtml(m.description)}</span>
              </div>` : ""}
              ${m.ai_verified || m.confidence_score > 0 || m.ai_extraction_source ? `<div class="detail-field detail-field-wide">
                <span class="detail-label">AI Extraction Info</span>
                <div class="ai-info-section">
                  ${m.confidence_score > 0 ? `<div class="ai-info-row">🎯 Confidence: ${this._getConfidenceBadge(m.confidence_score)}</div>` : ""}
                  ${m.ai_extraction_source ? `<div class="ai-info-row">📡 Source: <strong>${this._escHtml(m.ai_extraction_source === "scanned_label" ? "Scanned Label" : m.ai_extraction_source === "manual" ? "Manual Entry" : m.ai_extraction_source)}</strong></div>` : ""}
                  ${m.ai_extraction_timestamp ? `<div class="ai-info-row">🕐 Extracted: ${this._escHtml(m.ai_extraction_timestamp.substring(0, 19).replace("T", " "))}</div>` : ""}
                  ${m.ai_verified ? `<div class="ai-info-row">🤖 AI Verified: ✅</div>` : ""}
                </div>
              </div>` : ""}
            </div>

            ${this._renderOpeningDateSection(m)}

            <div class="leaflet-section">
              <div class="leaflet-header">
                <span class="leaflet-title">🇸🇰 Príbalový leták (AI)</span>
                ${!m.ai_leaflet && !this._leafletLoading
                  ? `<button class="btn btn-primary generate-leaflet-btn" data-id="${this._escHtml(m.medicine_id)}">Generate Leaflet</button>`
                  : ""}
                ${this._leafletLoading ? '<span class="leaflet-loading"><div class="spinner spinner-sm"></div> Generating…</span>' : ""}
              </div>
              ${m.ai_leaflet ? this._renderLeaflet(m.ai_leaflet, m.ai_leaflet_generated_at) : (!this._leafletLoading ? '<p class="leaflet-placeholder">Click "Generate Leaflet" to create a Slovak package leaflet summary using Claude AI.</p>' : "")}
            </div>
          </div>
          <div class="modal-footer">
            <div></div>
            <button class="btn btn-secondary close-detail">Close</button>
          </div>
        </div>
      </div>
    `;
  }

  _renderOpeningDateSection(m) {
    const openExpiry = m.open_expiry_date;
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    let openExpiryStatus = "";
    let openExpiryLabel = "";
    if (openExpiry) {
      const exp = new Date(openExpiry);
      exp.setHours(0, 0, 0, 0);
      const delta = Math.round((exp - today) / 86400000);
      if (delta < 0) {
        openExpiryStatus = "status-opened-too-long";
        openExpiryLabel = `⚠️ Opened Too Long (${Math.abs(delta)}d ago)`;
      } else if (delta <= 3) {
        openExpiryStatus = "status-expiring";
        openExpiryLabel = delta === 0 ? "⚠️ Expires Today" : `⚠️ ${delta}d left`;
      } else {
        openExpiryStatus = "status-good";
        openExpiryLabel = `✅ ${delta} days left`;
      }
    }

    if (this._showOpenDateSection || !m.date_opened) {
      // Show the edit / entry form
      return `
        <div class="opening-date-section">
          <div class="opening-date-header">
            <span class="opening-date-title">📅 Opening Date &amp; Validity</span>
            ${m.date_opened && !this._showOpenDateSection ? "" :
              m.date_opened ? `<button class="btn btn-secondary btn-sm cancel-open-date">Cancel</button>` : ""}
          </div>
          ${!m.date_opened && !this._showOpenDateSection ? `
            <button class="btn btn-primary btn-sm mark-opened-btn" data-id="${this._escHtml(m.medicine_id)}">
              ✏️ Mark as Opened
            </button>
          ` : `
            <div class="opening-form">
              <div class="opening-form-row">
                <label class="opening-form-label">Date Opened</label>
                <input class="form-input open-date-input" type="date"
                  value="${this._escHtml(this._pendingOpenDate)}" />
              </div>
              <div class="opening-form-row">
                <label class="opening-form-label">Valid After Opening (days)</label>
                <div class="opening-days-row">
                  <input class="form-input open-days-input" type="number" min="1" max="730"
                    value="${this._escHtml(this._pendingOpenDays)}"
                    placeholder="e.g. 14" />
                  <button class="btn btn-secondary btn-sm extract-open-days-btn" data-id="${this._escHtml(m.medicine_id)}"
                    ${this._extractingOpenDays ? "disabled" : ""}>
                    ${this._extractingOpenDays
                      ? '<div class="spinner spinner-sm"></div>'
                      : "🤖 Extract"}
                  </button>
                </div>
              </div>
              <div class="opening-form-actions">
                <button class="btn btn-primary btn-sm save-open-date-btn" data-id="${this._escHtml(m.medicine_id)}">
                  Save
                </button>
                ${m.date_opened ? `
                  <button class="btn btn-secondary btn-sm cancel-open-date">Cancel</button>
                  <button class="btn btn-danger btn-sm clear-open-date-btn" data-id="${this._escHtml(m.medicine_id)}">
                    🗑 Clear
                  </button>
                ` : `
                  <button class="btn btn-secondary btn-sm cancel-open-date">Cancel</button>
                `}
              </div>
            </div>
          `}
        </div>
      `;
    }

    // Show existing opening date info
    return `
      <div class="opening-date-section">
        <div class="opening-date-header">
          <span class="opening-date-title">📅 Opening Date &amp; Validity</span>
          <button class="btn btn-secondary btn-sm edit-open-date-btn" data-id="${this._escHtml(m.medicine_id)}">
            ✏️ Edit
          </button>
        </div>
        <div class="opening-info-grid">
          <div class="opening-info-row">
            <span class="opening-info-label">Date Opened</span>
            <span class="opening-info-value">${this._escHtml(m.date_opened)}</span>
          </div>
          <div class="opening-info-row">
            <span class="opening-info-label">Valid After Opening</span>
            <span class="opening-info-value">${m.days_valid_after_opening != null ? m.days_valid_after_opening + " days" : "—"}</span>
          </div>
          ${openExpiry ? `
          <div class="opening-info-row">
            <span class="opening-info-label">Open Expiry Date</span>
            <span class="opening-info-value">${this._escHtml(openExpiry)}
              <span class="status-badge ${openExpiryStatus}">${openExpiryLabel}</span>
            </span>
          </div>
          ` : ""}
        </div>
      </div>
    `;
  }

  _renderLeaflet(leaflet, generatedAt) {
    if (!leaflet) return "";
    const sections = [
      { key: "pouzitie", icon: "📝", label: "Použitie" },
      { key: "davkovanie", icon: "💊", label: "Dávkovanie" },
      { key: "vedlajsie_ucinky", icon: "⚠️", label: "Vedľajšie účinky" },
      { key: "varovania", icon: "🚨", label: "Varovania" },
      { key: "skladovanie", icon: "📦", label: "Skladovanie" },
      { key: "interakcie", icon: "🔄", label: "Interakcie" },
    ];

    const rows = sections
      .filter((s) => leaflet[s.key])
      .map((s) => {
        const value = leaflet[s.key];
        const content = this._renderLeafletValue(value);
        return `
        <div class="leaflet-row">
          <div class="leaflet-row-header">${s.icon} ${s.label}</div>
          <div class="leaflet-row-text">${content}</div>
        </div>`;
      })
      .join("");

    const genInfo = generatedAt
      ? `<div class="leaflet-generated-at">Generated: ${this._escHtml(generatedAt.substring(0, 10))}</div>`
      : "";

    return `<div class="leaflet-content">${rows}${genInfo}</div>`;
  }

  _renderLeafletValue(value) {
    if (!value) return "";
    // Render structured dosing table
    if (typeof value === "object" && value.type === "table" && Array.isArray(value.headers) && Array.isArray(value.rows)) {
      const headerCells = value.headers.map((h) => `<th>${this._escHtml(h)}</th>`).join("");
      const bodyRows = value.rows
        .map((row) => `<tr>${Array.isArray(row) ? row.map((cell) => `<td>${this._escHtml(cell)}</td>`).join("") : ""}</tr>`)
        .join("");
      return `<div class="dosing-table-wrapper"><table class="dosing-table"><thead><tr>${headerCells}</tr></thead><tbody>${bodyRows}</tbody></table></div>`;
    }
    // Plain text (string or fallback)
    return this._escHtml(String(value));
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
    if (str === null || str === undefined) return "";
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
      this._scanCount = 0;
      this._addStep = 1;
      this._labelScanning = false;
      this._expiryScanning = false;
      this._expiryInputMethod = "manual";
      this._formData = {};
      this.render();
    });
    root.querySelectorAll(".cancel-add").forEach((btn) => {
      btn.addEventListener("click", () => {
        this._showAddForm = false;
        this._scanResult = null;
        this._scanCount = 0;
        this._addStep = 1;
        this._labelScanning = false;
        this._expiryScanning = false;
        this._expiryInputMethod = "manual";
        this._formData = {};
        this.render();
      });
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

    // Search – preserve focus and cursor position across re-render
    root.querySelector(".search-input")?.addEventListener("input", (e) => {
      const cursorPos = e.target.selectionStart;
      this._searchTerm = e.target.value;
      this._applyFilters();
      this.render();
      const newInput = this.shadowRoot.querySelector(".search-input");
      if (newInput) {
        newInput.focus();
        newInput.setSelectionRange(cursorPos, cursorPos);
      }
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

    // Click on medicine item to open detail panel
    root.querySelectorAll(".clickable-item").forEach((item) => {
      item.addEventListener("click", () => {
        const id = item.dataset.id;
        const medicine = this._medicines.find((m) => m.medicine_id === id);
        if (medicine) this._openDetail(medicine);
      });
    });

    // Close detail panel
    root.querySelectorAll(".close-detail").forEach((btn) => {
      btn.addEventListener("click", () => this._closeDetail());
    });

    // Generate leaflet
    root.querySelector(".generate-leaflet-btn")?.addEventListener("click", (e) => {
      e.stopPropagation();
      this._generateLeaflet(e.currentTarget.dataset.id);
    });

    // Opening date: Mark as Opened button
    root.querySelector(".mark-opened-btn")?.addEventListener("click", (e) => {
      e.stopPropagation();
      this._showOpenDateSection = true;
      this.render();
    });

    // Opening date: Edit button
    root.querySelector(".edit-open-date-btn")?.addEventListener("click", (e) => {
      e.stopPropagation();
      const m = this._selectedMedicine;
      this._pendingOpenDate = m.date_opened || "";
      this._pendingOpenDays = m.days_valid_after_opening != null ? String(m.days_valid_after_opening) : "";
      this._showOpenDateSection = true;
      this.render();
    });

    // Opening date: Cancel button
    root.querySelectorAll(".cancel-open-date").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        this._showOpenDateSection = false;
        this.render();
      });
    });

    // Opening date: input changes (sync state without re-render)
    root.querySelector(".open-date-input")?.addEventListener("change", (e) => {
      this._pendingOpenDate = e.target.value;
    });
    root.querySelector(".open-days-input")?.addEventListener("input", (e) => {
      this._pendingOpenDays = e.target.value;
    });

    // Opening date: Extract days with Claude
    root.querySelector(".extract-open-days-btn")?.addEventListener("click", (e) => {
      e.stopPropagation();
      this._extractOpenDays(e.currentTarget.dataset.id);
    });

    // Opening date: Save
    root.querySelector(".save-open-date-btn")?.addEventListener("click", (e) => {
      e.stopPropagation();
      // Sync inputs before saving
      const dateInput = root.querySelector(".open-date-input");
      const daysInput = root.querySelector(".open-days-input");
      if (dateInput) this._pendingOpenDate = dateInput.value;
      if (daysInput) this._pendingOpenDays = daysInput.value;
      this._saveOpenDate(e.currentTarget.dataset.id);
    });

    // Opening date: Clear
    root.querySelector(".clear-open-date-btn")?.addEventListener("click", (e) => {
      e.stopPropagation();
      if (confirm("Clear the opening date for this medicine?")) {
        this._clearOpenDate(e.currentTarget.dataset.id);
      }
    });

    // Legacy scan input (kept for backward compatibility)
    root.querySelector(".scan-input")?.addEventListener("change", (e) => {
      const file = e.target.files[0];
      if (file) this._scanImage(file);
    });

    // Step 1: label scan
    root.querySelector(".label-scan-input")?.addEventListener("change", (e) => {
      const file = e.target.files[0];
      if (file) this._scanLabelImage(file);
    });

    // Step 2: expiry scan
    root.querySelector(".expiry-scan-input")?.addEventListener("change", (e) => {
      const file = e.target.files[0];
      if (file) this._scanExpiryImage(file);
    });

    // Step 2: expiry method tabs
    root.querySelectorAll(".expiry-tab").forEach((btn) => {
      btn.addEventListener("click", () => {
        this._expiryInputMethod = btn.dataset.method;
        this.render();
      });
    });

    // Step navigation: Next
    root.querySelector(".step-next-btn")?.addEventListener("click", () => {
      const getValue = (name) =>
        root.querySelector(`[name="${name}"]`)?.value?.trim() || "";

      if (this._addStep === 1) {
        const name = getValue("medicine_name");
        if (!name) {
          this._error = "Medicine name is required. Please scan the label or enter a name.";
          this.render();
          return;
        }
        this._formData = {
          ...this._formData,
          medicine_name: name,
          description: getValue("description"),
        };
      } else if (this._addStep === 2) {
        const expiry = getValue("expiry_date");
        if (!expiry) {
          this._error = "Expiry date is required.";
          this.render();
          return;
        }
        this._formData = {
          ...this._formData,
          expiry_date: expiry,
        };
      }

      this._addStep++;
      this._error = null;
      this.render();
    });

    // Step navigation: Back
    root.querySelector(".step-back-btn")?.addEventListener("click", () => {
      this._addStep = Math.max(1, this._addStep - 1);
      this._error = null;
      this.render();
    });

    // Submit add form (step 3)
    root.querySelector(".submit-add")?.addEventListener("click", () => {
      const getValue = (name) =>
        root.querySelector(`[name="${name}"]`)?.value?.trim() || "";

      const name = this._formData.medicine_name || "";
      const expiry = this._formData.expiry_date || "";
      if (!name || !expiry) {
        this._error = "Medicine name and expiry date are required.";
        this.render();
        return;
      }

      this._addMedicine({
        medicine_name: name,
        expiry_date: expiry,
        description: this._formData.description || "",
        quantity: parseInt(getValue("quantity") || "1", 10) || 1,
        location: getValue("location") || "unknown",
        unit: getValue("unit") || "",
        ai_verified: !!(this._formData.labelConfidence && this._formData.labelConfidence.medicine_name),
        confidence_score: this._computeOverallConfidence(),
        ai_extraction_source: (this._formData.labelConfidence || this._formData.expiryConfidence) ? "scanned_label" : "manual",
        ai_extraction_timestamp: new Date().toISOString(),
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
      .confidence-display { margin-top: 4px; font-size: 0.78rem; }
      .confidence-warning { margin-left: 8px; color: #e65100; font-weight: 600; }
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
      .status-opened-too-long .medicine-status-bar { background: #e65100; }
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
      .expiry-days.status-opened-too-long { color: #e65100; }
      .status-badge {
        display: inline-block; font-size: 0.65rem; padding: 2px 7px;
        border-radius: 12px; margin-top: 3px; font-weight: 600; text-transform: uppercase;
      }
      .status-badge.status-expired { background: #ffebee; color: var(--color-expired); }
      .status-badge.status-expiring { background: #fff3e0; color: var(--color-expiring); }
      .status-badge.status-good { background: #e8f5e9; color: var(--color-good); }
      .status-badge.status-opened-too-long { background: #fff3e0; color: #e65100; }
      .delete-btn { color: #bbb; font-size: 0.95rem; }
      .delete-btn:hover { color: var(--color-expired); background: #ffebee; }

      /* Empty state */
      .empty-state { text-align: center; padding: 32px 16px; color: var(--secondary-text-color, #888); }
      .empty-icon { font-size: 2.5rem; margin-bottom: 8px; }

      /* Clickable medicine item */
      .clickable-item { cursor: pointer; }
      .clickable-item:hover { box-shadow: 0 2px 12px rgba(0,0,0,0.14); }

      /* Confidence badge */
      .confidence-badge {
        display: inline-block; font-size: 0.65rem; padding: 2px 6px;
        border-radius: 10px; margin-left: 6px; font-weight: 600;
        vertical-align: middle;
      }
      .conf-excellent { background: #e8f5e9; color: #2e7d32; }
      .conf-good { background: #e3f2fd; color: #1565c0; }
      .conf-fair { background: #fff3e0; color: #e65100; }
      .conf-low-badge { background: #ffebee; color: #c62828; }

      /* AI info section in detail panel */
      .ai-info-section {
        display: flex; flex-direction: column; gap: 4px;
        padding: 8px 10px; border-radius: 6px;
        background: var(--secondary-background-color, #f5f5f5);
        font-size: 0.85rem;
      }
      .ai-info-row { color: var(--primary-text-color, #212121); }

      /* Leaflet chip */
      .leaflet-chip { background: #e8eaf6; color: #3949ab; }

      /* Detail panel */
      .detail-dialog { max-width: 580px; }
      .detail-body { display: flex; flex-direction: column; gap: 16px; }
      .detail-info-grid {
        display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
        gap: 10px;
      }
      .detail-field { display: flex; flex-direction: column; gap: 3px; }
      .detail-field-wide { grid-column: 1 / -1; }
      .detail-label { font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--secondary-text-color, #777); }
      .detail-value { font-size: 0.9rem; font-weight: 500; }

      /* Leaflet section */
      .leaflet-section {
        border: 1px solid var(--divider-color, #e0e0e0);
        border-radius: 8px; padding: 12px;
        background: var(--secondary-background-color, #f9f9f9);
      }
      .leaflet-header {
        display: flex; align-items: center; justify-content: space-between;
        margin-bottom: 10px; flex-wrap: wrap; gap: 8px;
      }
      .leaflet-title { font-weight: 600; font-size: 0.95rem; }
      .leaflet-placeholder { color: var(--secondary-text-color, #888); font-size: 0.85rem; margin: 0; }
      .leaflet-loading { display: flex; align-items: center; gap: 6px; font-size: 0.85rem; color: var(--secondary-text-color, #777); }
      .spinner-sm { width: 16px; height: 16px; border-width: 2px; }
      .leaflet-content { display: flex; flex-direction: column; gap: 8px; }
      .leaflet-row { padding: 6px 0; border-bottom: 1px solid var(--divider-color, #eee); }
      .leaflet-row:last-of-type { border-bottom: none; }
      .leaflet-row-header { font-weight: 600; font-size: 0.8rem; color: var(--secondary-text-color, #555); margin-bottom: 2px; }
      .leaflet-row-text { font-size: 0.875rem; }
      .leaflet-generated-at { font-size: 0.7rem; color: var(--secondary-text-color, #999); margin-top: 8px; text-align: right; }

      /* Scan actions */
      .scan-actions { display: flex; gap: 8px; align-items: center; }
      .scan-row { margin-bottom: 12px; }

      /* Multi-step form */
      .step-progress {
        display: flex; align-items: flex-start; justify-content: center;
        margin-bottom: 20px; padding: 4px 0;
      }
      .step-dot {
        display: flex; flex-direction: column; align-items: center; gap: 4px;
        position: relative;
      }
      .step-dot > span {
        width: 28px; height: 28px;
        border-radius: 50%;
        display: flex; align-items: center; justify-content: center;
        font-size: 0.8rem; font-weight: 700;
        background: var(--secondary-background-color, #e0e0e0);
        color: var(--secondary-text-color, #777);
        border: 2px solid var(--divider-color, #ccc);
        transition: background 0.2s, border-color 0.2s;
      }
      .step-dot.active > span {
        background: var(--primary-color, #03a9f4); color: #fff;
        border-color: var(--primary-color, #03a9f4);
      }
      .step-dot.done > span {
        background: #43a047; color: #fff; border-color: #43a047;
      }
      .step-dot-label {
        font-size: 0.65rem; color: var(--secondary-text-color, #777);
        text-transform: uppercase; letter-spacing: 0.04em;
      }
      .step-line {
        flex: 1; height: 2px; margin: 13px 4px 0;
        background: var(--divider-color, #e0e0e0); min-width: 30px;
        transition: background 0.2s;
      }
      .step-line.active { background: var(--primary-color, #03a9f4); }
      .step-title {
        font-weight: 600; font-size: 0.95rem; margin-bottom: 8px;
        color: var(--primary-text-color, #212121);
      }
      .step-content { display: flex; flex-direction: column; gap: 10px; }
      .step-instruction { margin: 0 0 8px; font-size: 0.85rem; color: var(--secondary-text-color, #666); }
      .step-hint { margin: 8px 0; font-size: 0.85rem; color: var(--secondary-text-color, #777); }
      .scan-btn-label.loading { opacity: 0.7; pointer-events: none; }
      .conf-indicator {
        font-size: 0.75rem; margin-top: 3px;
        padding: 2px 6px; border-radius: 10px; display: inline-block;
      }
      .conf-ok { background: #e8f5e9; color: #2e7d32; }
      .conf-low { background: #fff3e0; color: #e65100; }
      .raw-text { font-size: 0.78rem; color: var(--secondary-text-color, #888); }

      /* Expiry tabs */
      .expiry-tabs { display: flex; gap: 8px; margin-bottom: 14px; }
      .expiry-tab {
        flex: 1; padding: 8px 12px; border: 1px solid var(--divider-color, #ccc);
        border-radius: 6px; background: var(--card-background-color, #fff);
        color: var(--secondary-text-color, #555); cursor: pointer;
        font-size: 0.85rem; transition: background 0.15s, border-color 0.15s;
      }
      .expiry-tab.active {
        background: var(--primary-color, #03a9f4); color: #fff;
        border-color: var(--primary-color, #03a9f4); font-weight: 600;
      }
      .expiry-tab:hover:not(.active) { background: var(--secondary-background-color, #f5f5f5); }

      /* Modal navigation (step form) */
      .modal-nav {
        display: flex; align-items: center; justify-content: space-between;
        width: 100%;
      }

      /* Dosing table */
      .dosing-table-wrapper {
        overflow-x: auto; -webkit-overflow-scrolling: touch;
        border-radius: 6px; border: 1px solid var(--divider-color, #e0e0e0);
        margin-top: 4px;
      }
      .dosing-table {
        width: 100%; border-collapse: collapse;
        font-size: 0.82rem; background: var(--card-background-color, #fff);
      }
      .dosing-table th {
        background: var(--primary-color, #03a9f4); color: #fff;
        padding: 7px 10px; text-align: left; white-space: nowrap;
        font-weight: 600; font-size: 0.78rem; text-transform: uppercase;
        letter-spacing: 0.04em;
      }
      .dosing-table td {
        padding: 6px 10px; border-bottom: 1px solid var(--divider-color, #eee);
        color: var(--primary-text-color, #212121); white-space: nowrap;
      }
      .dosing-table tbody tr:last-child td { border-bottom: none; }
      .dosing-table tbody tr:hover { background: var(--secondary-background-color, #f5f5f5); }

      /* Opening date section */
      .opening-date-section {
        border: 1px solid var(--divider-color, #e0e0e0);
        border-radius: 8px; padding: 12px;
        background: var(--secondary-background-color, #f9f9f9);
        border-left: 4px solid #2196F3;
      }
      .opening-date-header {
        display: flex; align-items: center; justify-content: space-between;
        margin-bottom: 10px; flex-wrap: wrap; gap: 8px;
      }
      .opening-date-title { font-weight: 600; font-size: 0.95rem; }
      .opening-form { display: flex; flex-direction: column; gap: 10px; }
      .opening-form-row { display: flex; flex-direction: column; gap: 4px; }
      .opening-form-label { font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--secondary-text-color, #777); }
      .opening-days-row { display: flex; gap: 8px; align-items: center; }
      .opening-days-row .form-input { flex: 1; max-width: 100px; }
      .opening-form-actions { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 4px; }
      .opening-info-grid { display: flex; flex-direction: column; gap: 8px; }
      .opening-info-row { display: flex; gap: 10px; align-items: flex-start; font-size: 0.875rem; }
      .opening-info-label { font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--secondary-text-color, #777); min-width: 140px; padding-top: 2px; }
      .opening-info-value { flex: 1; font-weight: 500; display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }

      /* Small button variant */
      .btn-sm { padding: 5px 10px; font-size: 0.78rem; }
      .btn-danger { background: #ffebee; color: #c62828; border: 1px solid #e57373; }
      .btn-danger:hover { background: #ffcdd2; }

      /* Opened meta chip */
      .opened-chip { background: #e3f2fd; color: #1565c0; }

      @media (max-width: 400px) {
        .summary-grid { grid-template-columns: repeat(2, 1fr); }
        .search-bar { flex-direction: column; }
        .form-grid { grid-template-columns: 1fr; }
        .detail-info-grid { grid-template-columns: 1fr; }
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

// Register card AFTER page loads to ensure Home Assistant is ready
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", registerCard);
} else {
  registerCard();
}

function registerCard() {
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: "medicine-count-card",
    name: "Medicine Count & Expiry",
    description: "Track your medicine inventory and expiry dates",
    preview: true,
  });
}
