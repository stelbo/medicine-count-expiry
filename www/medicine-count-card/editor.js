/**
 * Medicine Count & Expiry Card - Editor
 * Lovelace card editor for Home Assistant UI configuration.
 */

class MedicineCountCardEditor extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
  }

  setConfig(config) {
    this._config = { ...config };
    this.render();
  }

  get _title() {
    return this._config.title || "";
  }

  render() {
    this.shadowRoot.innerHTML = `
      <style>
        .editor-form { padding: 16px; font-family: sans-serif; }
        label { display: flex; flex-direction: column; gap: 6px; margin-bottom: 14px; font-size: 0.9rem; color: #555; }
        input, select {
          padding: 8px 10px;
          border: 1px solid #ccc;
          border-radius: 5px;
          font-size: 0.875rem;
          background: #fff;
        }
        .hint { font-size: 0.75rem; color: #888; }
      </style>
      <div class="editor-form">
        <label>
          Card Title (optional)
          <input class="title-input" type="text" value="${this._escHtml(this._title)}" placeholder="Medicine Inventory" />
          <span class="hint">Leave blank to use the default title.</span>
        </label>
      </div>
    `;

    this.shadowRoot.querySelector(".title-input")?.addEventListener("input", (e) => {
      this._config = { ...this._config, title: e.target.value };
      this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: this._config } }));
    });
  }

  _escHtml(str) {
    if (str == null) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }
}

customElements.define("medicine-count-card-editor", MedicineCountCardEditor);
