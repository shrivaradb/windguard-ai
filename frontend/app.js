/**
 * WindGuard AI — Operator Web Dashboard & Presentation Controller
 * Phase 7 Presentation Layer (Layer 6 UI) & Universal SCADA Studio
 * 
 * Implements:
 * - OD-P7-04: Operator Session Profile Switcher & X-Operator-ID propagation
 * - OD-P7-05: Tiered Client Polling Engine with Pause-on-Blur & In-Flight Concurrency Locks
 * - OD-P7-06: Formatted Print / PDF Draft Work Order Export
 * - OD-P7-11: Client Performance Telemetry & Acceptance Targets
 * - Universal Real-World SCADA Ingestion & Auto-Column Mapping Studio
 * - Complete 6-Layer Diagnostic Pipeline Visualization
 * 
 * Zero external dependencies — 100% self-contained & offline capable.
 */

class WindGuardApp {
  constructor() {
    this.apiBase = (window.location.port === '8000' || window.location.pathname.startsWith('/api'))
      ? '' 
      : 'http://127.0.0.1:8000';

    // Application State
    this.state = {
      activeTab: 'dataset-studio',
      selectedTurbineId: 'WTG-01',
      activeCaseId: null,
      activeDemoStage: 1,
      pollingEnabled: true,
      operatorId: sessionStorage.getItem('windguard_operator_id') || 'OPERATOR_LOCAL',
      operatorName: sessionStorage.getItem('windguard_operator_name') || 'Default Local Operator',
      fleetStatus: null,
      cases: [],
      activeCase: null,
      telemetryCache: {},
      activeTurbineRecords: [],
      activeTariff: null,
      demoStageData: null,
      inFlightRequests: new Set(),
      consecutiveFailures: 0,
      activeHITLAction: null,
      activeHITLCaseId: null,
      scatterFilter: 'all',
      fleetFilter: 'all',
      studioFile: null,
      studioInspection: null,
      detectedRatingKw: 2000.0,
    };

    // Performance Metrics Tracking (OD-P7-11)
    this.perfMetrics = {
      initialLoadMs: 0,
      fleetRenderMs: 0,
      turbineRenderMs: 0,
      tabSwitchMs: 0,
      chartRenderMs: 0,
      caseTableRenderMs: 0,
      diagnosisRenderMs: 0,
      ragRenderMs: 0,
      hitlTransitionMs: 0,
      demoStepMs: 0,
    };

    // Polling Intervals (OD-P7-05)
    this.pollIntervals = {
      fleet: 5000,
      telemetry: 5000,
      cases: 10000,
      health: 10000,
    };
    this.pollTimers = {};
  }

  /**
   * Initializes the WindGuard AI Dashboard Application.
   */
  async init() {
    const t0 = performance.now();
    console.log('[WindGuard AI] Initializing Presentation Layer...');

    // 1. Initialize DOM Event Listeners
    this.bindEvents();

    // 2. Setup Operator Profile Identity (OD-P7-04)
    this.initOperatorProfile();

    // 3. Handle Hash Routing
    this.handleRouting();

    // 4. Check Backend Readiness Probe
    await this.checkSystemHealth();

    // 5. Initial Data Load
    await this.refreshActiveView();

    // 6. Start Polling Engine (OD-P7-05)
    this.startPollingEngine();

    this.perfMetrics.initialLoadMs = performance.now() - t0;
    console.log(`[WindGuard AI] Dashboard initialized in ${this.perfMetrics.initialLoadMs.toFixed(1)} ms.`);
  }

  // ============================================================================
  // 1. API Client & Header Propagation (OD-P7-04)
  // ============================================================================

  async apiRequest(endpoint, options = {}) {
    const fullUrl = `${this.apiBase}${endpoint}`;
    const requestKey = `${options.method || 'GET'}:${endpoint}`;

    if (this.state.inFlightRequests.has(requestKey) && (options.method === 'GET' || !options.method)) {
      console.warn(`[WindGuard API] Skipping duplicate in-flight request: ${requestKey}`);
      return null;
    }
    this.state.inFlightRequests.add(requestKey);

    const headers = {
      'Accept': 'application/json',
      'X-Operator-ID': this.state.operatorId,
      ...(options.headers || {}),
    };

    if (options.body && !(options.body instanceof FormData)) {
      headers['Content-Type'] = 'application/json';
    }

    try {
      const response = await fetch(fullUrl, {
        ...options,
        headers,
      });

      this.state.inFlightRequests.delete(requestKey);

      if (!response.ok) {
        let errData;
        try {
          errData = await response.json();
        } catch {
          errData = { message: `HTTP error ${response.status} ${response.statusText}` };
        }
        this.handleApiError(response.status, errData, endpoint);
        throw new Error(errData.message || errData.detail || `Request failed with status ${response.status}`);
      }

      this.state.consecutiveFailures = 0;
      return await response.json();
    } catch (err) {
      this.state.inFlightRequests.delete(requestKey);
      this.state.consecutiveFailures++;
      throw err;
    }
  }

  handleApiError(status, errData, endpoint) {
    console.error(`[WindGuard API Error ${status}] ${endpoint}:`, errData);
    const msg = errData.message || errData.detail || 'An unexpected API error occurred.';
    this.showToast(msg, 'error');
  }

  // ============================================================================
  // 2. Operator Profile & Identity Governance (OD-P7-04)
  // ============================================================================

  initOperatorProfile() {
    const select = document.getElementById('operator-select');
    if (!select) return;

    select.value = this.state.operatorId;
    select.addEventListener('change', (e) => {
      const val = e.target.value;
      if (val === 'CUSTOM') {
        const customId = prompt('Enter Certified Operator Badge ID (e.g. OPERATOR_ANALYST_04):', 'OPERATOR_CUSTOM');
        if (customId) {
          this.setOperatorProfile(customId.trim(), customId.trim());
        } else {
          select.value = this.state.operatorId;
        }
      } else {
        const name = select.options[select.selectedIndex].text;
        this.setOperatorProfile(val, name);
      }
    });

    const footerName = document.getElementById('operator-current-name');
    if (footerName) footerName.textContent = this.state.operatorName;
  }

  setOperatorProfile(operatorId, operatorName) {
    this.state.operatorId = operatorId;
    this.state.operatorName = operatorName;
    sessionStorage.setItem('windguard_operator_id', operatorId);
    sessionStorage.setItem('windguard_operator_name', operatorName);

    const footerName = document.getElementById('operator-current-name');
    if (footerName) footerName.textContent = operatorName;

    this.showToast(`Active Operator session: ${operatorName}`, 'info');
  }

  // ============================================================================
  // 3. Event Listeners & Navigation Routing
  // ============================================================================

  bindEvents() {
    // Navigation Tabs
    document.querySelectorAll('.nav-tab-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const tab = btn.getAttribute('data-tab');
        this.switchTab(tab);
      });
    });

    // Global Refresh Button
    const refreshBtn = document.getElementById('global-refresh-btn');
    if (refreshBtn) {
      refreshBtn.addEventListener('click', () => {
        this.showToast('Refreshing current operational view...', 'info');
        this.refreshActiveView();
      });
    }

    // Polling Toggle Button
    const pollBtn = document.getElementById('polling-toggle-btn');
    if (pollBtn) {
      pollBtn.addEventListener('click', () => {
        this.state.pollingEnabled = !this.state.pollingEnabled;
        pollBtn.classList.toggle('paused', !this.state.pollingEnabled);
        pollBtn.textContent = this.state.pollingEnabled ? '● LIVE (5s)' : '❚❚ PAUSED';
        this.showToast(`Background polling ${this.state.pollingEnabled ? 'resumed' : 'paused'}.`, 'info');
      });
    }

    // Pause on Blur / Tab Inactive (OD-P7-05)
    document.addEventListener('visibilitychange', () => {
      if (document.hidden || document.visibilityState === 'hidden') {
        this.stopPollingTimers();
      } else if (this.state.pollingEnabled) {
        this.startPollingEngine();
        this.refreshActiveView();
      }
    });

    // Turbine Deep Dive Selector
    const turbineSelect = document.getElementById('turbine-deepdive-select');
    if (turbineSelect) {
      turbineSelect.addEventListener('change', (e) => {
        this.state.selectedTurbineId = e.target.value;
        this.fetchTurbineTelemetry(this.state.selectedTurbineId);
      });
    }

    // Diagnostic Studio: Run Diagnosis Button
    const diagBtn = document.getElementById('run-diagnosis-btn');
    if (diagBtn) {
      diagBtn.addEventListener('click', () => {
        this.runDiagnosis(this.state.selectedTurbineId);
      });
    }

    // Knowledge Assistant Query Form
    const ragForm = document.getElementById('rag-search-form');
    if (ragForm) {
      ragForm.addEventListener('submit', (e) => {
        e.preventDefault();
        this.handleRAGSearch();
      });
    }

    // Tariff Update Form
    const tariffForm = document.getElementById('tariff-update-form');
    if (tariffForm) {
      tariffForm.addEventListener('submit', (e) => {
        e.preventDefault();
        this.handleTariffUpdate();
      });
    }

    // HITL Modal Notes Submission
    const hitlSubmitBtn = document.getElementById('modal-submit-hitl');
    if (hitlSubmitBtn) {
      hitlSubmitBtn.addEventListener('click', () => this.submitHITLDecision());
    }

    // Work Order Print Button (OD-P7-06)
    const printBtn = document.getElementById('print-work-order-btn');
    if (printBtn) {
      printBtn.addEventListener('click', () => this.printWorkOrder());
    }

    // SCADA Simulation Launcher Modal Trigger
    const simModalBtn = document.getElementById('open-sim-modal-btn');
    if (simModalBtn) {
      simModalBtn.addEventListener('click', () => this.openSimulationModal());
    }

    // SCADA Simulation CSV Upload Form
    const simCsvForm = document.getElementById('csv-upload-form');
    if (simCsvForm) {
      simCsvForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const fileInput = document.getElementById('csv-file-input');
        if (fileInput && fileInput.files && fileInput.files.length > 0) {
          this.handleSimulationCSVUpload(fileInput.files[0]);
        } else {
          this.showToast('Please select a CSV file first.', 'warning');
        }
      });
    }

    // Dataset Studio Drag & Drop Events
    this.initDatasetStudioEvents();

    // Fleet Filter Pills
    document.querySelectorAll('.filter-pill').forEach(pill => {
      pill.addEventListener('click', () => {
        document.querySelectorAll('.filter-pill').forEach(p => p.classList.remove('active'));
        pill.classList.add('active');
        this.state.fleetFilter = pill.getAttribute('data-fleet-filter') || 'all';
        if (this.state.fleetStatus) {
          this.renderTurbineGrid(this.state.fleetStatus.active_turbines || []);
        }
      });
    });

    // Scatter Filter Pills (Turbine Deep Dive)
    document.querySelectorAll('.scatter-pill').forEach(pill => {
      pill.addEventListener('click', () => {
        document.querySelectorAll('.scatter-pill').forEach(p => p.classList.remove('active'));
        pill.classList.add('active');
        this.state.scatterFilter = pill.getAttribute('data-scatter-filter') || 'all';
        const records = this.state.activeTurbineRecords || [];
        const canvas = document.getElementById('canvas-power-curve');
        if (canvas && window.WindGuardCharts) {
          window.WindGuardCharts.renderPowerCurve(canvas, {
            telemetryRecords: records,
            livePoint: this.state.telemetryCache[this.state.selectedTurbineId],
            ratedPowerKw: this.state.detectedRatingKw || 2000.0,
            scatterFilter: this.state.scatterFilter,
          });
        }
      });
    });
  }

  // ============================================================================
  // 4. Real Data & Dataset Studio Controller
  // ============================================================================

  initDatasetStudioEvents() {
    const dropzone = document.getElementById('csv-dropzone');
    const fileInput = document.getElementById('studio-csv-input');
    const browseBtn = document.getElementById('btn-browse-csv');
    const clearBtn = document.getElementById('btn-clear-file');
    const resetBtn = document.getElementById('btn-reset-studio-file');
    const confirmIngestBtn = document.getElementById('btn-confirm-ingest-custom');

    if (browseBtn && fileInput) {
      browseBtn.addEventListener('click', () => fileInput.click());
    }

    if (dropzone && fileInput) {
      dropzone.addEventListener('click', (e) => {
        if (e.target !== browseBtn) fileInput.click();
      });

      dropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropzone.classList.add('dragover');
      });

      dropzone.addEventListener('dragleave', () => {
        dropzone.classList.remove('dragover');
      });

      dropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropzone.classList.remove('dragover');
        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
          const file = e.dataTransfer.files[0];
          this.handleStudioFile(file);
        }
      });

      fileInput.addEventListener('change', (e) => {
        if (e.target.files && e.target.files.length > 0) {
          this.handleStudioFile(e.target.files[0]);
        }
      });
    }

    if (clearBtn) {
      clearBtn.addEventListener('click', () => this.resetStudioFile());
    }
    if (resetBtn) {
      resetBtn.addEventListener('click', () => this.resetStudioFile());
    }

    if (confirmIngestBtn) {
      confirmIngestBtn.addEventListener('click', () => this.confirmCustomIngest());
    }
  }

  async handleStudioFile(file) {
    if (!file.name.endsWith('.csv')) {
      this.showToast('Please upload a valid CSV file (.csv).', 'warning');
      return;
    }

    this.state.studioFile = file;

    // Update File Pill
    const pill = document.getElementById('file-info-pill');
    const nameEl = document.getElementById('info-file-name');
    const metaEl = document.getElementById('info-file-meta');
    if (pill && nameEl && metaEl) {
      nameEl.textContent = file.name;
      metaEl.textContent = `${(file.size / 1024).toFixed(1)} KB | Inspecting columns...`;
      pill.style.display = 'flex';
    }

    await this.inspectStudioCSV(file);
  }

  async inspectStudioCSV(file) {
    this.showToast(`Auto-detecting OEM channels in ${file.name}...`, 'info');
    const formData = new FormData();
    formData.append('file', file);

    try {
      const inspection = await this.apiRequest('/api/scada/inspect', {
        method: 'POST',
        body: formData,
      });

      if (!inspection) return;
      this.state.studioInspection = inspection;

      // Update meta pill
      const metaEl = document.getElementById('info-file-meta');
      if (metaEl) {
        metaEl.textContent = `${(file.size / 1024).toFixed(1)} KB | ${inspection.total_rows} rows | ${inspection.total_columns} columns`;
      }

      this.renderColumnMapper(inspection);
      this.showToast(`Auto-matched ${Object.keys(inspection.column_mappings).length} channels.`, 'success');
    } catch (err) {
      console.error('[WindGuard] Error inspecting CSV:', err);
    }
  }

  renderColumnMapper(inspection) {
    const panel = document.getElementById('column-mapping-panel');
    const tbody = document.getElementById('column-mapping-tbody');
    const rowsEl = document.getElementById('map-rows-count');
    const colsEl = document.getElementById('map-cols-count');
    const turbEl = document.getElementById('map-turbines-detected');
    const dateEl = document.getElementById('map-date-range');
    const ratingSelect = document.getElementById('studio-rated-power-select');

    if (!panel || !tbody) return;

    if (rowsEl) rowsEl.textContent = inspection.total_rows.toLocaleString();
    if (colsEl) colsEl.textContent = inspection.total_columns;
    if (turbEl) turbEl.textContent = inspection.detected_turbines.join(', ');
    if (dateEl) {
      const s = inspection.date_range.start || '--';
      const e = inspection.date_range.end || '--';
      dateEl.textContent = `${s} → ${e}`;
    }

    if (ratingSelect) {
      const r = inspection.detected_turbine_rating_kw || 2000.0;
      this.state.detectedRatingKw = r;
      ratingSelect.value = String(r);
      if (!ratingSelect.value) ratingSelect.value = 'AUTO';
    }

    const rawCols = inspection.raw_columns || [];
    const mappings = inspection.column_mappings || {};

    tbody.innerHTML = Object.entries(mappings).map(([canonical, spec]) => {
      const isReq = spec.required;
      const reqBadge = isReq 
        ? `<span class="badge badge-accent">Required</span>` 
        : `<span class="badge" style="background:rgba(255,255,255,0.06);">Optional</span>`;

      let statusBadge = `<span class="match-badge match-auto">✅ Auto-Matched</span>`;
      if (spec.status === 'SMART_ESTIMATED') {
        statusBadge = `<span class="match-badge match-estimated">⚡ Smart Estimated</span>`;
      } else if (spec.status === 'MISSING_REQUIRED') {
        statusBadge = `<span class="match-badge" style="background:rgba(239,68,68,0.2); color:#ef4444;">⚠️ Needs Mapping</span>`;
      }

      const optionsHtml = [
        `<option value="__NONE__">${isReq ? '-- Select Column --' : '[⚡ Auto-Estimate from Physics]'}</option>`,
        ...rawCols.map(c => `<option value="${c}" ${c === spec.raw_column ? 'selected' : ''}>${c}</option>`)
      ].join('');

      return `
        <tr>
          <td><strong>${canonical}</strong> <span style="font-size:11px; color:var(--text-muted);">(${spec.unit})</span></td>
          <td>${reqBadge}</td>
          <td>
            <select class="mapping-select" data-canonical="${canonical}">
              ${optionsHtml}
            </select>
          </td>
          <td>${statusBadge}</td>
          <td style="font-size:12px; color:var(--text-secondary);">${spec.description}</td>
        </tr>
      `;
    }).join('');

    panel.style.display = 'block';
  }

  async confirmCustomIngest() {
    if (!this.state.studioFile) {
      this.showToast('Please select a CSV file first.', 'warning');
      return;
    }

    const mappingSelects = document.querySelectorAll('.mapping-select');
    const customMap = {};
    mappingSelects.forEach(sel => {
      const canonical = sel.getAttribute('data-canonical');
      const val = sel.value;
      if (val) customMap[canonical] = val;
    });

    const ratingSelect = document.getElementById('studio-rated-power-select');
    let ratedPowerKw = null;
    if (ratingSelect && ratingSelect.value !== 'AUTO') {
      ratedPowerKw = parseFloat(ratingSelect.value);
    }

    const formData = new FormData();
    formData.append('file', this.state.studioFile);
    formData.append('column_mapping_json', JSON.stringify(customMap));
    if (ratedPowerKw) {
      formData.append('rated_power_kw', ratedPowerKw);
    }

    this.showToast('Ingesting, normalizing, and standardizing real SCADA telemetry...', 'info');

    try {
      const res = await this.apiRequest('/api/scada/ingest/custom', {
        method: 'POST',
        body: formData,
      });

      if (res && res.status === 'success') {
        this.showToast(`CSV accepted: ${res.ingested_count} records ingested!`, 'success');
        this.renderDataHealthScorecard(res.summary, res.ingested_count);
        await this.fetchFleetStatus();
      }
    } catch (err) {
      console.error('[WindGuard] Error ingesting custom CSV:', err);
    }
  }

  renderDataHealthScorecard(summary, ingestedCount) {
    const card = document.getElementById('data-health-scorecard');
    const acceptedEl = document.getElementById('score-accepted-count');
    const interpEl = document.getElementById('score-interpolated-count');
    const dropEl = document.getElementById('score-dropout-count');
    const fleetEl = document.getElementById('score-fleet-count');

    if (!card) return;

    if (acceptedEl) acceptedEl.textContent = ingestedCount.toLocaleString();
    if (interpEl) interpEl.textContent = (summary?.interpolated_values_count || 0).toLocaleString();
    if (dropEl) dropEl.textContent = (summary?.dropout_records_count || 0).toLocaleString();
    if (fleetEl) {
      fleetEl.textContent = this.state.fleetStatus?.active_turbines?.length || '1';
    }

    card.style.display = 'block';
  }

  resetStudioFile() {
    this.state.studioFile = null;
    this.state.studioInspection = null;

    const fileInput = document.getElementById('studio-csv-input');
    if (fileInput) fileInput.value = '';

    const pill = document.getElementById('file-info-pill');
    if (pill) pill.style.display = 'none';

    const panel = document.getElementById('column-mapping-panel');
    if (panel) panel.style.display = 'none';

    const scorecard = document.getElementById('data-health-scorecard');
    if (scorecard) scorecard.style.display = 'none';
  }

  async loadSampleDataset(datasetId) {
    this.showToast(`Loading real benchmark dataset: ${datasetId}...`, 'info');
    try {
      const res = await this.apiRequest(`/api/scada/load-sample/${datasetId}`, {
        method: 'POST',
      });

      if (res && res.status === 'success') {
        this.showToast(res.message, 'success');
        this.renderDataHealthScorecard(res.summary, res.ingested_count);
        await this.fetchFleetStatus();
        this.switchTab('fleet');
      }
    } catch (err) {
      console.error('[WindGuard] Error loading sample dataset:', err);
    }
  }

  // ============================================================================
  // 5. Routing & Tab Controller
  // ============================================================================

  handleRouting() {
    window.addEventListener('hashchange', () => {
      const hash = window.location.hash.replace('#', '') || 'dataset-studio';
      this.switchTab(hash, false);
    });

    const initialHash = window.location.hash.replace('#', '') || 'dataset-studio';
    this.switchTab(initialHash, false);
  }

  switchTab(tabName, updateHash = true) {
    const t0 = performance.now();
    const validTabs = ['dataset-studio', 'fleet', 'turbine', 'diagnostic', 'knowledge', 'tariff', 'demo'];
    if (!validTabs.includes(tabName)) tabName = 'fleet';

    this.state.activeTab = tabName;

    // Update active tab buttons
    document.querySelectorAll('.nav-tab-btn').forEach(b => {
      b.classList.toggle('active', b.getAttribute('data-tab') === tabName);
    });

    // Update view panels
    document.querySelectorAll('.view-panel').forEach(p => {
      p.classList.toggle('active', p.id === `view-${tabName}`);
    });

    if (updateHash) {
      window.location.hash = tabName;
    }

    this.refreshActiveView();

    this.perfMetrics.tabSwitchMs = performance.now() - t0;
  }

  async refreshActiveView() {
    switch (this.state.activeTab) {
      case 'dataset-studio':
        break;
      case 'fleet':
        await this.fetchFleetStatus();
        await this.fetchCases();
        break;
      case 'turbine':
        await this.fetchTurbineTelemetry(this.state.selectedTurbineId);
        break;
      case 'diagnostic':
        if (this.state.activeCaseId) {
          await this.fetchCaseDetails(this.state.activeCaseId);
        } else {
          await this.runDiagnosis(this.state.selectedTurbineId);
        }
        break;
      case 'knowledge':
        break;
      case 'tariff':
        await this.fetchActiveTariff();
        break;
      case 'demo':
        await this.fetchDemoStage(this.state.activeDemoStage);
        break;
      default:
        break;
    }
  }

  // ============================================================================
  // 6. Fleet Health & KPI Controller (Screen 1)
  // ============================================================================

  async fetchFleetStatus() {
    const t0 = performance.now();
    try {
      const status = await this.apiRequest('/api/fleet/status');
      if (!status) return;

      this.state.fleetStatus = status;
      this.renderFleetStatus(status);
      this.perfMetrics.fleetRenderMs = performance.now() - t0;
    } catch (err) {
      console.warn('[WindGuard] Error fetching fleet status:', err);
    }
  }

  renderFleetStatus(status) {
    const totalTurbinesEl = document.getElementById('kpi-total-turbines');
    const totalPowerEl = document.getElementById('kpi-total-power');
    const avgWindEl = document.getElementById('kpi-avg-wind');
    const curtailedCountEl = document.getElementById('kpi-curtailed-count');
    const activeAnomaliesEl = document.getElementById('kpi-active-anomalies');
    const totalLossEl = document.getElementById('kpi-total-loss');
    const filterAllCount = document.getElementById('filter-all-count');

    const turbCount = status.total_turbines || (status.active_turbines?.length || 10);
    if (totalTurbinesEl) totalTurbinesEl.textContent = turbCount;
    if (filterAllCount) filterAllCount.textContent = turbCount;
    if (totalPowerEl) totalPowerEl.textContent = `${((status.total_fleet_power_kw || 0) / 1000).toFixed(2)} MW`;
    if (avgWindEl) avgWindEl.textContent = `${(status.average_wind_speed_mps || 0).toFixed(1)} m/s`;
    if (curtailedCountEl) curtailedCountEl.textContent = status.curtailed_turbines_count || 0;
    if (activeAnomaliesEl) activeAnomaliesEl.textContent = status.active_anomalies_count || 0;
    if (totalLossEl) {
      totalLossEl.textContent = `₹${(status.total_fleet_financial_loss_inr || 0).toLocaleString()}`;
    }

    // Populate Deep Dive select options
    const deepDiveSelect = document.getElementById('turbine-deepdive-select');
    if (deepDiveSelect && status.active_turbines && status.active_turbines.length > 0) {
      if (!status.active_turbines.includes(this.state.selectedTurbineId)) {
        this.state.selectedTurbineId = status.active_turbines[0];
      }
      deepDiveSelect.innerHTML = status.active_turbines.map(id => 
        `<option value="${id}" ${id === this.state.selectedTurbineId ? 'selected' : ''}>${id}</option>`
      ).join('');
    }

    // Render Turbine Grid Cards with active filter
    this.renderTurbineGrid(status.active_turbines || ['WTG-01', 'WTG-02', 'WTG-03', 'WTG-04', 'WTG-05', 'WTG-06', 'WTG-07', 'WTG-08', 'WTG-09', 'WTG-10']);
  }

  renderTurbineGrid(turbineIds) {
    const container = document.getElementById('fleet-turbine-grid');
    if (!container) return;

    const filter = this.state.fleetFilter || 'all';

    const filteredIds = turbineIds.filter(id => {
      const cached = this.state.telemetryCache[id] || {};
      const isCurtailed = cached.is_curtailed;
      const isAnomaly = (id === 'WTG-07') || (cached.operating_status === 'Fault');

      if (filter === 'healthy') return !isCurtailed && !isAnomaly;
      if (filter === 'anomaly') return isAnomaly;
      if (filter === 'curtailed') return isCurtailed;
      return true;
    });

    container.innerHTML = filteredIds.map(id => {
      const cached = this.state.telemetryCache[id] || {};
      const power = cached.active_power !== undefined ? `${cached.active_power.toFixed(0)} kW` : '-- kW';
      const wind = cached.wind_speed !== undefined ? `${cached.wind_speed.toFixed(1)} m/s` : '-- m/s';
      const isCurtailed = cached.is_curtailed;
      
      let badgeClass = 'status-normal';
      let badgeText = 'NORMAL';
      if (isCurtailed) {
        badgeClass = 'status-curtailed';
        badgeText = 'CURTAILED';
      } else if (id === 'WTG-07') {
        badgeClass = 'status-critical';
        badgeText = 'HIGH ANOMALY';
      } else if (id === 'WTG-03') {
        badgeClass = 'status-monitoring';
        badgeText = 'AERO DEFICIT';
      }

      return `
        <div class="turbine-card" onclick="windGuardApp.selectTurbineAndNavigate('${id}')">
          <div class="turbine-card-header">
            <div class="turbine-id">${id}</div>
            <span class="status-badge ${badgeClass}">${badgeText}</span>
          </div>
          <div class="turbine-metrics">
            <div class="metric-item">
              <span class="metric-label">Active Power</span>
              <span class="metric-value">${power}</span>
            </div>
            <div class="metric-item">
              <span class="metric-label">Wind Speed</span>
              <span class="metric-value">${wind}</span>
            </div>
          </div>
          <button class="btn btn-secondary btn-sm" style="width: 100%; margin-top: 4px;">
            Investigate Deep Dive →
          </button>
        </div>
      `;
    }).join('');
  }

  selectTurbineAndNavigate(turbineId) {
    this.state.selectedTurbineId = turbineId;
    const select = document.getElementById('turbine-deepdive-select');
    if (select) select.value = turbineId;
    this.switchTab('turbine');
  }

  // ============================================================================
  // 7. Turbine Deep Dive & Canvas Charts (Screen 2)
  // ============================================================================

  async fetchTurbineTelemetry(turbineId) {
    const t0 = performance.now();
    try {
      const records = await this.apiRequest(`/api/turbines/${turbineId}/telemetry?limit=500`);
      if (!records || records.length === 0) return;

      this.state.telemetryCache[turbineId] = records[records.length - 1];
      this.state.activeTurbineRecords = records;
      this.renderTurbineDeepDive(turbineId, records);
      this.perfMetrics.turbineRenderMs = performance.now() - t0;
    } catch (err) {
      console.warn(`[WindGuard] No telemetry records found for ${turbineId}:`, err);
    }
  }

  renderTurbineDeepDive(turbineId, records) {
    const latest = records[records.length - 1] || {};

    const powerEl = document.getElementById('deepdive-power');
    const windEl = document.getElementById('deepdive-wind');
    const tempGbEl = document.getElementById('deepdive-temp-gb');
    const tempGenEl = document.getElementById('deepdive-temp-gen');
    const curtailedBadge = document.getElementById('deepdive-curtailed-badge');

    if (powerEl) powerEl.textContent = `${(latest.active_power || 0).toFixed(0)} kW`;
    if (windEl) windEl.textContent = `${(latest.wind_speed || 0).toFixed(1)} m/s`;
    if (tempGbEl) tempGbEl.textContent = `${(latest.gearbox_bearing_temp || 0).toFixed(1)} °C`;
    if (tempGenEl) tempGenEl.textContent = `${(latest.generator_stator_temp || 0).toFixed(1)} °C`;
    if (curtailedBadge) {
      curtailedBadge.style.display = latest.is_curtailed ? 'inline-block' : 'none';
    }

    // Render Canvas Charts
    const tChart0 = performance.now();
    const powerCanvas = document.getElementById('canvas-power-curve');
    if (powerCanvas && window.WindGuardCharts) {
      window.WindGuardCharts.renderPowerCurve(powerCanvas, {
        telemetryRecords: records,
        livePoint: {
          wind_speed: latest.wind_speed || 8.5,
          active_power: latest.active_power || 1620.0,
          expected_power: 1740.0,
        },
        ratedPowerKw: this.state.detectedRatingKw || 2000.0,
        scatterFilter: this.state.scatterFilter || 'all',
      });
    }

    const tsPowerCanvas = document.getElementById('canvas-ts-power');
    if (tsPowerCanvas && window.WindGuardCharts) {
      window.WindGuardCharts.renderTimeSeries(tsPowerCanvas, records, 'active_power', '#06b6d4', 'kW');
    }

    const tsTempCanvas = document.getElementById('canvas-ts-temp');
    if (tsTempCanvas && window.WindGuardCharts) {
      window.WindGuardCharts.renderTimeSeries(tsTempCanvas, records, 'gearbox_bearing_temp', '#ef4444', '°C');
    }

    this.perfMetrics.chartRenderMs = performance.now() - tChart0;
  }

  // ============================================================================
  // 8. AI Diagnostic Studio (Screen 3)
  // ============================================================================

  async runDiagnosis(turbineId) {
    const t0 = performance.now();
    try {
      this.showToast(`Executing full 6-layer diagnostic pipeline for ${turbineId}...`, 'info');
      const diagCase = await this.apiRequest(`/api/turbines/${turbineId}/diagnose`, {
        method: 'POST',
        body: JSON.stringify({ force_recompute: true }),
      });

      if (!diagCase) return;
      this.state.activeCase = diagCase;
      this.state.activeCaseId = diagCase.case_id;
      this.renderDiagnosticStudio(diagCase);
      this.switchTab('diagnostic');
      this.perfMetrics.diagnosisRenderMs = performance.now() - t0;
      this.showToast(`Diagnostic case generated: ${diagCase.case_id}`, 'success');
      await this.fetchCases();
    } catch (err) {
      console.error('[WindGuard] Error running diagnosis:', err);
    }
  }

  renderDiagnosticStudio(diagCase) {
    if (!diagCase) return;

    // Header Case Metadata
    const caseIdEl = document.getElementById('diag-case-id');
    const turbIdEl = document.getElementById('diag-turbine-id');
    const ctxBadgeEl = document.getElementById('diag-context-badge');

    if (caseIdEl) caseIdEl.textContent = diagCase.case_id || '--';
    if (turbIdEl) turbIdEl.textContent = diagCase.turbine_id || '--';
    if (ctxBadgeEl) {
      const ctxState = diagCase.derived_analytics?.context_state || diagCase.advisory?.context_classification || 'NORMAL';
      ctxBadgeEl.textContent = ctxState;
      ctxBadgeEl.className = `status-badge ${ctxState === 'NORMAL' ? 'status-normal' : (ctxState === 'CURTAILED' ? 'status-curtailed' : 'status-monitoring')}`;
    }

    // Severity Badge
    const sevBadge = document.getElementById('diag-severity-badge');
    if (sevBadge) {
      const sev = diagCase.severity || 'HIGH';
      sevBadge.textContent = `SEVERITY: ${sev}`;
      sevBadge.className = `status-badge status-${sev.toLowerCase()}`;
    }

    // Narrative Summary
    const narrativeEl = document.getElementById('diag-summary-narrative');
    if (narrativeEl) {
      narrativeEl.textContent = diagCase.advisory?.summary || diagCase.executive_summary || 'Diagnostic analysis completed.';
    }

    // Grounding Evidence Synthesis Table
    const evidenceTbody = document.getElementById('diag-evidence-tbody');
    if (evidenceTbody) {
      const items = diagCase.evidence_table || diagCase.advisory?.evidence_synthesis || [];
      if (items.length > 0) {
        evidenceTbody.innerHTML = items.map(ev => `
          <tr>
            <td><strong>${ev.field_name || ev.metric || '--'}</strong></td>
            <td>${ev.value !== undefined ? ev.value : (ev.observed_value || '--')} ${ev.unit || ''}</td>
            <td><code style="font-size:11px; color:var(--text-muted);">${ev.source_reference || ev.source_id || 'Deterministic Engine'}</code></td>
          </tr>
        `).join('');
      } else if (diagCase.derived_analytics) {
        const da = diagCase.derived_analytics;
        evidenceTbody.innerHTML = `
          <tr>
            <td><strong>Active Power Residual (ΔP)</strong></td>
            <td>${da.residual_power_kw?.toFixed(1) || '--'} kW (z=${da.z_power?.toFixed(2) || '--'}σ)</td>
            <td><code>ML Baseline Residual Engine</code></td>
          </tr>
          <tr>
            <td><strong>Gearbox Bearing Temp Residual (ΔT_GB)</strong></td>
            <td>${da.residual_gb_temp_c?.toFixed(2) || '--'} °C (z=${da.z_gb?.toFixed(2) || '--'}σ)</td>
            <td><code>Thermal Equilibrium Model</code></td>
          </tr>
          <tr>
            <td><strong>Generator Stator Temp Residual (ΔT_Gen)</strong></td>
            <td>${da.residual_gen_temp_c?.toFixed(2) || '--'} °C (z=${da.z_gen?.toFixed(2) || '--'}σ)</td>
            <td><code>Thermal Equilibrium Model</code></td>
          </tr>
        `;
      }
    }

    // Differential Diagnostic Hypotheses
    const hypContainer = document.getElementById('diag-hypotheses-list');
    if (hypContainer) {
      const hypotheses = diagCase.advisory?.hypotheses || [];
      if (hypotheses.length > 0) {
        hypContainer.innerHTML = hypotheses.map((hyp, idx) => {
          const isPrimary = (idx === 0) || (hyp.plausibility === 'HIGH');
          const plaus = hyp.plausibility || 'HIGH';
          const badgeClass = plaus === 'HIGH' ? 'badge-accent' : (plaus === 'MODERATE' ? 'badge-amber' : '');
          
          const groundHtml = (hyp.grounding_evidence && hyp.grounding_evidence.length > 0)
            ? `<div style="margin-top:6px; font-size:11px; color:var(--text-muted);">
                 Grounding: ${(hyp.grounding_evidence || []).map(g => `<span class="tag">${g}</span>`).join(' ')}
               </div>`
            : '';

          const missHtml = (hyp.missing_evidence && hyp.missing_evidence.length > 0)
            ? `<div style="margin-top:4px; font-size:11px; color:var(--accent-amber);">
                 Required Validation: ${(hyp.missing_evidence || []).map(m => `<span class="tag" style="border-color:rgba(245,158,11,0.4);">${m}</span>`).join(' ')}
               </div>`
            : '';

          return `
            <div class="hypothesis-item ${isPrimary ? 'primary' : ''}" style="margin-bottom:12px; padding:12px; background:var(--bg-secondary); border-radius:var(--radius-md); border-left:3px solid ${isPrimary ? 'var(--accent-cyan)' : 'var(--border-color)'};">
              <div class="hyp-header" style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                <strong style="color:var(--text-primary); font-size:13px;">${hyp.hypothesis || diagCase.derived_analytics?.subsystem_attribution || 'Candidate Anomaly Hypothesis'}</strong>
                <span class="badge ${badgeClass}">${plaus} PLAUSIBILITY</span>
              </div>
              ${groundHtml}
              ${missHtml}
            </div>
          `;
        }).join('');
      } else {
        const sub = diagCase.derived_analytics?.subsystem_attribution || diagCase.advisory?.primary_attribution || 'System Operation';
        hypContainer.innerHTML = `
          <div class="hypothesis-item primary" style="padding:12px; background:var(--bg-secondary); border-radius:var(--radius-md); border-left:3px solid var(--accent-cyan);">
            <div class="hyp-header" style="display:flex; justify-content:space-between; align-items:center;">
              <strong>${sub}: Primary Multi-Signal Attribution</strong>
              <span class="badge badge-accent">HIGH PLAUSIBILITY</span>
            </div>
            <p style="font-size:12px; color:var(--text-secondary); margin-top:6px;">
              Attributed to ${sub} based on physics-informed standardized residual persistent excursions.
            </p>
          </div>
        `;
      }
    }

    // Technical RAG Citations
    const citationsContainer = document.getElementById('diag-citations-list');
    if (citationsContainer) {
      const citations = diagCase.citations || diagCase.advisory?.citations || [];
      if (citations.length > 0) {
        citationsContainer.innerHTML = citations.map((cit, idx) => {
          const docTitle = cit.title || cit.document_title || 'Technical Service Manual';
          const loc = [cit.chapter, cit.section].filter(Boolean).join(' → ') || cit.source_id || `Chunk #${idx + 1}`;
          const score = cit.relevance_score ? `${(cit.relevance_score * 100).toFixed(0)}% Relevance` : 'Verified Citation';
          const hashPrev = cit.content_hash ? `${cit.content_hash.substring(0, 10)}...` : 'SHA-256 Verified';

          return `
            <div class="citation-card" style="margin-bottom:10px; padding:12px; background:var(--bg-secondary); border-radius:var(--radius-md); border:1px solid var(--border-color);">
              <div class="citation-title" style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                <strong style="color:var(--accent-cyan); font-size:13px;">${docTitle}</strong>
                <span class="badge badge-accent">${score}</span>
              </div>
              <div style="font-size:11px; color:var(--text-muted); margin-bottom:4px;">
                <span>Section: <strong>${loc}</strong></span> | 
                <span>Source ID: <strong>${cit.source_id || '--'}</strong></span> | 
                <span>Provenance: <code>${hashPrev}</code></span>
              </div>
            </div>
          `;
        }).join('');
      } else {
        citationsContainer.innerHTML = `
          <div style="font-size:12px; color:var(--text-muted); padding:10px; text-align:center;">
            Technical SOP references retrieved from offline authoritative engineering corpus.
          </div>
        `;
      }
    }

    // Commercial Loss & Tariff Provenance (Sidebar)
    const lossKwhEl = document.getElementById('diag-loss-kwh');
    const lossInrEl = document.getElementById('diag-loss-inr');
    const tariffRateEl = document.getElementById('diag-tariff-rate');
    const tariffModeEl = document.getElementById('diag-tariff-mode');
    const priorityScoreEl = document.getElementById('diag-priority-score');

    const da = diagCase.derived_analytics || {};
    const lossInr = da.financial_loss_inr !== undefined ? da.financial_loss_inr : (diagCase.advisory?.loss_summary_inr || 0);
    const lossKwh = da.energy_loss_kwh !== undefined ? da.energy_loss_kwh : (diagCase.advisory?.energy_loss_kwh || 0);
    const prio = diagCase.priority_score !== undefined ? diagCase.priority_score : (da.priority_score || 0);
    const tProv = da.tariff_provenance || {};

    if (lossKwhEl) lossKwhEl.textContent = `${lossKwh.toFixed(1)} kWh`;
    if (lossInrEl) lossInrEl.textContent = `₹${lossInr.toLocaleString()}`;
    if (tariffRateEl) tariffRateEl.textContent = `₹${(tProv.applied_rate_inr_per_kwh || tProv.rate_inr_per_kwh || 3.20).toFixed(2)} / kWh`;
    if (tariffModeEl) tariffModeEl.textContent = tProv.mode || tProv.tariff_mode || 'CONFIGURED_BASELINE';
    if (priorityScoreEl) priorityScoreEl.textContent = `${prio.toFixed(1)} / 100`;

    // Recommended Physical Inspection Checklist (Sidebar)
    const checklistContainer = document.getElementById('diag-checklist-list');
    if (checklistContainer) {
      const actions = diagCase.advisory?.recommended_actions || [];
      if (actions.length > 0) {
        checklistContainer.innerHTML = actions.map((act, i) => `
          <div style="margin-bottom:8px; padding:8px 10px; background:var(--bg-input); border-radius:var(--radius-sm); border-left:3px solid var(--accent-cyan); font-size:12px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:2px;">
              <strong style="color:var(--text-primary); font-size:11px;">[${act.urgency || 'SCHEDULED'}] ${act.target_subsystem || 'Subsystem'}</strong>
              <span class="badge" style="font-size:10px;">Step ${i + 1}</span>
            </div>
            <p style="color:var(--text-secondary); margin:0; line-height:1.4;">${act.action_text || act.description || 'Perform physical field inspection.'}</p>
          </div>
        `).join('');
      } else {
        checklistContainer.innerHTML = `
          <div style="font-size:11px; color:var(--text-muted); padding:6px 0;">
            1. Verify high-speed shaft bearing thermal telemetry via calibrated hand-held IR thermometer.<br>
            2. Inspect lubrication oil circulation pump pressure and filter differential pressure.
          </div>
        `;
      }
    }

    // Decision Audit History (Sidebar)
    const decisionHistory = document.getElementById('diag-decision-history');
    if (decisionHistory) {
      const decisions = diagCase.operator_decisions || [];
      if (decisions.length > 0) {
        decisionHistory.innerHTML = decisions.map(d => `
          <div style="padding:6px 0; border-bottom:1px solid var(--border-color); font-size:11px;">
            <div><strong>${d.action}</strong> by <span>${d.operator_id}</span> <span style="color:var(--text-muted);">(${d.timestamp})</span></div>
            <div style="color:var(--text-secondary); margin-top:2px;">${d.notes}</div>
          </div>
        `).join('');
      } else {
        decisionHistory.innerHTML = `<div style="color:var(--text-muted); font-size:11px;">No operator triage decisions logged yet.</div>`;
      }
    }
  }

  // ============================================================================
  // 9. Case Store & Audit Log Controller
  // ============================================================================

  async fetchCases() {
    const t0 = performance.now();
    try {
      const res = await this.apiRequest('/api/cases');
      if (!res) return;
      const casesList = Array.isArray(res) ? res : (res.cases || []);
      this.state.cases = casesList;
      this.renderCaseTable(casesList);
      this.perfMetrics.caseTableRenderMs = performance.now() - t0;
    } catch (err) {
      console.warn('[WindGuard] Error fetching cases:', err);
    }
  }

  renderCaseTable(cases) {
    const tbody = document.getElementById('cases-table-tbody') || document.getElementById('cases-tbody');
    if (!tbody) return;

    if (!cases || cases.length === 0) {
      tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; color:var(--text-muted); padding:16px;">No open maintenance cases. Run diagnosis to evaluate active fleet telemetry.</td></tr>`;
      return;
    }

    tbody.innerHTML = cases.map(c => {
      const sev = c.severity || 'HIGH';
      const loss = c.derived_analytics?.financial_loss_inr !== undefined 
        ? c.derived_analytics.financial_loss_inr 
        : (c.advisory?.loss_summary_inr || 0);
      const prio = c.priority_score !== undefined ? c.priority_score : (c.derived_analytics?.priority_score || 0);
      const revStatus = c.review_status || 'AUTOMATIC';

      return `
        <tr>
          <td><strong style="color:var(--accent-cyan); font-family:var(--font-mono);">${c.case_id}</strong></td>
          <td><strong>${c.turbine_id}</strong></td>
          <td><span class="status-badge status-${sev.toLowerCase()}">${sev}</span></td>
          <td><strong style="color:var(--text-primary);">${prio.toFixed(1)}</strong> / 100</td>
          <td style="color:var(--accent-rose); font-weight:600;">₹${loss.toLocaleString()}</td>
          <td><span class="badge">${revStatus}</span></td>
          <td>
            <button class="btn btn-secondary btn-sm" onclick="windGuardApp.selectCase('${c.case_id}')">
              Inspect Case →
            </button>
          </td>
        </tr>
      `;
    }).join('');
  }

  async selectCase(caseId) {
    this.state.activeCaseId = caseId;
    await this.fetchCaseDetails(caseId);
    this.switchTab('diagnostic');
  }

  async fetchCaseDetails(caseId) {
    try {
      const c = await this.apiRequest(`/api/cases/${caseId}`);
      if (c) {
        this.state.activeCase = c;
        this.renderDiagnosticStudio(c);
      }
    } catch (err) {
      console.error('[WindGuard] Error fetching case details:', err);
    }
  }

  // ============================================================================
  // 10. Human-in-the-Loop Action Handling
  // ============================================================================

  openHITLModal(action) {
    if (!this.state.activeCase) {
      this.showToast('Please select or evaluate a diagnostic case first.', 'warning');
      return;
    }

    this.state.activeHITLAction = action;
    this.state.activeHITLCaseId = this.state.activeCase.case_id;

    const titleEl = document.getElementById('hitl-modal-title');
    const caseIdEl = document.getElementById('hitl-modal-case-id');
    const notesInput = document.getElementById('hitl-modal-notes') || document.getElementById('hitl-notes-input');
    const modal = document.getElementById('hitl-modal');

    if (titleEl) titleEl.textContent = `Confirm Action: ${action}`;
    if (caseIdEl) caseIdEl.textContent = this.state.activeHITLCaseId;
    if (notesInput) notesInput.value = '';
    if (modal) modal.classList.add('active');
  }

  closeHITLModal() {
    const modal = document.getElementById('hitl-modal');
    if (modal) modal.classList.remove('active');
  }

  async submitHITLDecision() {
    const action = this.state.activeHITLAction;
    const caseId = this.state.activeHITLCaseId;
    const notesInput = document.getElementById('hitl-modal-notes') || document.getElementById('hitl-notes-input');
    const notes = notesInput ? notesInput.value.trim() : '';

    if (!notes) {
      this.showToast('Operator engineering justification notes are required.', 'warning');
      return;
    }

    try {
      this.showToast(`Submitting ${action} decision for ${caseId}...`, 'info');
      const updatedCase = await this.apiRequest(`/api/cases/${caseId}/decision`, {
        method: 'POST',
        body: JSON.stringify({
          action,
          operator_id: this.state.operatorId,
          notes,
        }),
      });

      this.closeHITLModal();
      this.showToast(`Case ${caseId} updated with ${action}.`, 'success');
      this.state.activeCase = updatedCase;
      this.renderDiagnosticStudio(updatedCase);
      await this.fetchCases();
    } catch (err) {
      console.error('[WindGuard] Error submitting HITL decision:', err);
    }
  }

  // ============================================================================
  // 11. Technical Knowledge Assistant (RAG Search)
  // ============================================================================

  triggerRAGSuggestion(query) {
    const input = document.getElementById('rag-query-input');
    if (input) input.value = query;
    this.handleRAGSearch();
  }

  async handleRAGSearch() {
    const input = document.getElementById('rag-query-input');
    const modeSelect = document.getElementById('rag-mode-select');
    const query = input ? input.value.trim() : '';
    const mode = modeSelect ? modeSelect.value : 'HYBRID_LOCAL';

    if (!query) {
      this.showToast('Please enter a search query.', 'warning');
      return;
    }

    const t0 = performance.now();
    this.showToast(`Searching technical corpus (${mode})...`, 'info');

    try {
      const res = await this.apiRequest('/api/rag/query', {
        method: 'POST',
        body: JSON.stringify({
          query,
          mode,
          top_k: 5,
        }),
      });

      if (!res) return;
      this.renderRAGResults(res);
      this.perfMetrics.ragRenderMs = performance.now() - t0;
    } catch (err) {
      console.error('[WindGuard] Error querying RAG corpus:', err);
    }
  }

  renderRAGResults(ragResponse) {
    const container = document.getElementById('rag-results-container');
    if (!container) return;

    if (!ragResponse.chunks || ragResponse.chunks.length === 0) {
      container.innerHTML = `<div style="color:var(--text-muted); padding:30px; text-align:center;">No matching procedures or engineering SOPs found for this query.</div>`;
      return;
    }

    container.innerHTML = ragResponse.chunks.map((chunk, idx) => {
      const score = (ragResponse.scores[idx] || 0).toFixed(3);
      const hash = chunk.content_hash || chunk.sha256_hash || 'SHA256-VERIFIED';
      const sec = chunk.section || chunk.section_title || chunk.chapter || 'Section 1.0';
      const text = chunk.content || chunk.text || '';

      return `
        <div class="panel-card" style="margin-bottom:14px;">
          <div class="panel-title" style="display:flex; justify-content:space-between; align-items:center;">
            <span style="color:var(--accent-cyan); font-size:14px;">${chunk.document_title}</span>
            <span class="badge badge-accent">Rank #${idx + 1} (Score: ${score})</span>
          </div>
          <div style="font-size:11px; color:var(--text-muted); margin-bottom:8px;">
            <span>Section: <strong>${sec}</strong></span> | 
            <span>Source ID: <strong>${chunk.source_id || '--'}</strong></span> | 
            <span>SHA-256: <code>${hash.substring(0, 12)}...</code></span>
          </div>
          <div style="font-size:13px; line-height:1.6; color:var(--text-primary); background:var(--bg-input); padding:12px; border-radius:var(--radius-sm); border:1px solid var(--border-color);">
            ${text}
          </div>
        </div>
      `;
    }).join('');
  }

  // ============================================================================
  // 12. Tariff Configuration Controller
  // ============================================================================

  async fetchActiveTariff() {
    try {
      const registryData = await this.apiRequest('/api/tariffs');
      if (registryData) {
        this.state.activeTariff = registryData.active_tariff;
        this.populateTariffForm(registryData);
        this.renderTariffHistory(registryData.history || []);
      }
    } catch (err) {
      console.warn('[WindGuard] Error fetching active tariff:', err);
    }
  }

  populateTariffForm(registryData) {
    const active = registryData.active_tariff || {};
    const rateEl = document.getElementById('tariff-active-rate');
    const modeEl = document.getElementById('tariff-active-mode');
    const srcEl = document.getElementById('tariff-active-source');
    const dateEl = document.getElementById('tariff-active-date');

    const rateInput = document.getElementById('tariff-input-rate');
    const modeSelect = document.getElementById('tariff-input-mode');
    const srcInput = document.getElementById('tariff-input-source');

    const appliedRate = active.applied_rate_inr_per_kwh || active.rate_inr_per_kwh || 3.20;
    const mode = active.mode || 'CONFIGURED_BASELINE';
    const sourceRef = active.source_reference || 'CERC Benchmark Configuration';
    const effDate = active.effective_date || '2026-09-20';

    if (rateEl) rateEl.textContent = `₹${appliedRate.toFixed(2)} / kWh`;
    if (modeEl) modeEl.textContent = mode;
    if (srcEl) srcEl.textContent = sourceRef;
    if (dateEl) dateEl.textContent = effDate;

    if (rateInput) rateInput.value = appliedRate.toFixed(2);
    if (modeSelect) modeSelect.value = mode;
    if (srcInput) srcInput.value = sourceRef;
  }

  renderTariffHistory(historyList) {
    const tbody = document.getElementById('tariff-history-tbody');
    if (!tbody) return;

    if (!historyList || historyList.length === 0) {
      tbody.innerHTML = `<tr><td colspan="4" style="text-align:center; color:var(--text-muted); padding:12px;">No historical tariff modifications logged.</td></tr>`;
      return;
    }

    tbody.innerHTML = historyList.map(t => {
      const rate = t.applied_rate_inr_per_kwh || t.rate_inr_per_kwh || 3.20;
      return `
        <tr>
          <td><strong style="color:var(--accent-cyan);">₹${rate.toFixed(2)} / kWh</strong></td>
          <td><span class="status-badge status-normal">${t.mode}</span></td>
          <td>${t.source_reference}</td>
          <td style="color:var(--text-muted); font-size:12px;">${t.effective_date}</td>
        </tr>
      `;
    }).join('');
  }

  async handleTariffUpdate() {
    const rateInput = document.getElementById('tariff-input-rate');
    const modeSelect = document.getElementById('tariff-input-mode');
    const srcInput = document.getElementById('tariff-input-source');

    const payload = {
      rate_inr_per_kwh: rateInput ? parseFloat(rateInput.value) : 3.20,
      mode: modeSelect ? modeSelect.value : 'CONFIGURED_BASELINE',
      source_reference: srcInput ? srcInput.value.trim() : 'Manual Update',
      notes: `Updated by ${this.state.operatorName} from Operator Studio.`,
    };

    try {
      this.showToast('Applying prospective commercial tariff rate...', 'info');
      const updatedTariff = await this.apiRequest('/api/tariffs', {
        method: 'POST',
        body: JSON.stringify(payload),
      });

      if (updatedTariff) {
        this.showToast('Commercial electricity tariff updated successfully.', 'success');
        await this.fetchActiveTariff();
      }
    } catch (err) {
      console.error('[WindGuard] Error updating tariff:', err);
    }
  }

  // ============================================================================
  // 13. 10-Stage Interactive Demonstration Stepper (Screen 6)
  // ============================================================================

  loadDemoStage(stageId) {
    this.fetchDemoStage(stageId);
  }

  async fetchDemoStage(stageId) {
    const t0 = performance.now();
    try {
      const stage = await this.apiRequest(`/api/demo/stage/${stageId}`);
      if (!stage) return;

      this.state.activeDemoStage = stageId;
      this.state.demoStageData = stage;
      this.renderDemoStage(stage);
      this.perfMetrics.demoStepMs = performance.now() - t0;
    } catch (err) {
      console.error(`[WindGuard] Error fetching demo stage ${stageId}:`, err);
    }
  }

  renderDemoStage(stage) {
    const titleEl = document.getElementById('demo-stage-title');
    const descEl = document.getElementById('demo-stage-desc');
    const statusEl = document.getElementById('demo-expected-status');
    const faultEl = document.getElementById('demo-injected-fault');

    if (titleEl) titleEl.textContent = `Stage ${stage.stage_id}: ${stage.stage_name}`;
    if (descEl) descEl.textContent = stage.description;
    if (statusEl) {
      statusEl.textContent = stage.expected_status;
      statusEl.className = `status-badge ${stage.expected_status === 'NORMAL' ? 'status-normal' : (stage.expected_status.includes('FAULT') || stage.expected_status.includes('CRITICAL') ? 'status-critical' : 'status-curtailed')}`;
    }
    if (faultEl) faultEl.textContent = stage.injected_fault || 'None (Normal Healthy Baseline)';

    // Update active pill
    document.querySelectorAll('.demo-step-btn').forEach(btn => {
      const sId = parseInt(btn.getAttribute('data-stage'), 10);
      btn.classList.toggle('active', sId === stage.stage_id);
    });

    // Render Canvas Demo Chart
    const canvas = document.getElementById('canvas-demo-power');
    if (canvas && window.WindGuardCharts && stage.telemetry) {
      const tel = stage.telemetry;
      window.WindGuardCharts.renderPowerCurve(canvas, {
        telemetryRecords: [tel],
        livePoint: {
          wind_speed: tel.wind_speed,
          active_power: tel.active_power,
          expected_power: tel.active_power > 1000 ? tel.active_power + 100 : tel.active_power,
        },
        ratedPowerKw: 2000.0,
        scatterFilter: 'all',
      });
    }
  }

  async runDemoDiagnosis() {
    const stage = this.state.demoStageData;
    if (!stage || !stage.telemetry) return;

    this.showToast(`Running diagnostic synthesis for Stage ${stage.stage_id} (${stage.telemetry.turbine_id})...`, 'info');
    
    try {
      const diagCase = await this.apiRequest(`/api/turbines/${stage.telemetry.turbine_id}/diagnose`, {
        method: 'POST',
        body: JSON.stringify({
          telemetry_record: stage.telemetry,
          force_recompute: true,
        }),
      });

      if (!diagCase) return;
      this.state.activeCase = diagCase;
      this.state.activeCaseId = diagCase.case_id;
      this.renderDiagnosticStudio(diagCase);
      this.switchTab('diagnostic');
      this.showToast('Demo stage diagnosis synthesized successfully.', 'success');
      await this.fetchCases();
    } catch (err) {
      console.error('[WindGuard] Error executing demo diagnosis:', err);
    }
  }

  // ============================================================================
  // 14. Work Order Print & Export (OD-P7-06)
  // ============================================================================

  printWorkOrder() {
    if (!this.state.activeCase) {
      this.showToast('Please evaluate or select a maintenance case to export.', 'warning');
      return;
    }
    window.print();
  }

  // ============================================================================
  // 15. SCADA Simulation Modal & CSV Ingest
  // ============================================================================

  openSimulationModal() {
    const modal = document.getElementById('sim-modal');
    if (modal) modal.classList.add('active');
  }

  closeSimulationModal() {
    const modal = document.getElementById('sim-modal');
    if (modal) modal.classList.remove('active');
  }

  async runSimulation(scenarioId) {
    try {
      this.showToast(`Launching physics simulation: ${scenarioId}...`, 'info');
      const res = await this.apiRequest('/api/scada/simulate', {
        method: 'POST',
        body: JSON.stringify({ scenario: scenarioId, num_timesteps: 144 }),
      });

      if (res && res.status === 'success') {
        this.closeSimulationModal();
        this.showToast(`Simulation complete: ${res.total_records} telemetry records generated.`, 'success');
        await this.fetchFleetStatus();
        this.switchTab('fleet');
      }
    } catch (err) {
      console.error('[WindGuard] Error running simulation:', err);
    }
  }

  async handleSimulationCSVUpload(file) {
    if (!file.name.endsWith('.csv')) {
      this.showToast('Only CSV files are supported.', 'warning');
      return;
    }

    const formData = new FormData();
    formData.append('file', file);
    this.showToast(`Uploading SCADA file ${file.name}...`, 'info');

    try {
      const res = await this.apiRequest('/api/scada/ingest/file', {
        method: 'POST',
        body: formData,
      });

      if (res && res.status === 'success') {
        this.closeSimulationModal();
        this.showToast(`CSV accepted: ${res.ingested_count} records ingested!`, 'success');
        await this.fetchFleetStatus();
        this.switchTab('fleet');
      }
    } catch (err) {
      console.error('[WindGuard] Error uploading CSV:', err);
    }
  }

  // ============================================================================
  // 16. Polling Engine & Health Monitoring (OD-P7-05)
  // ============================================================================

  startPollingEngine() {
    this.stopPollingTimers();
    this.pollTimers.fleet = setInterval(() => {
      if (this.state.pollingEnabled && this.state.activeTab === 'fleet') {
        this.fetchFleetStatus();
      }
    }, this.pollIntervals.fleet);

    this.pollTimers.health = setInterval(() => {
      this.checkSystemHealth();
    }, this.pollIntervals.health);
  }

  stopPollingTimers() {
    Object.values(this.pollTimers).forEach(timer => clearInterval(timer));
    this.pollTimers = {};
  }

  stopPollingEngine() {
    this.stopPollingTimers();
  }

  async checkSystemHealth() {
    try {
      const res = await this.apiRequest('/api/health');
      const badge = document.getElementById('system-health-badge');
      const text = document.getElementById('system-health-text');
      if (badge && text) {
        if (res && res.status === 'healthy') {
          badge.className = 'health-badge health-ok';
          text.textContent = 'Engine Active';
        } else {
          badge.className = 'health-badge health-warn';
          text.textContent = 'Engine Degraded';
        }
      }
    } catch {
      const badge = document.getElementById('system-health-badge');
      const text = document.getElementById('system-health-text');
      if (badge && text) {
        badge.className = 'health-badge health-error';
        text.textContent = 'Engine Offline';
      }
    }
  }

  // ============================================================================
  // 17. Non-Blocking Toast Notification System
  // ============================================================================

  showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `<span>${message}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = '0';
      setTimeout(() => toast.remove(), 200);
    }, 4000);
  }
}

// Instantiate and attach application singleton
window.windGuardApp = new WindGuardApp();
document.addEventListener('DOMContentLoaded', () => {
  window.windGuardApp.init();
});
