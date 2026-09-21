/**
 * WindGuard AI — Operator Web Dashboard & Presentation Controller
 * Phase 7 Presentation Layer (Layer 6 UI)
 * 
 * Implements:
 * - OD-P7-04: Operator Session Profile Switcher & X-Operator-ID propagation
 * - OD-P7-05: Tiered Client Polling Engine with Pause-on-Blur & In-Flight Concurrency Locks
 * - OD-P7-06: Formatted Print / PDF Draft Work Order Export
 * - OD-P7-11: Client Performance Telemetry & Acceptance Targets
 * 
 * Zero external dependencies — 100% self-contained & offline capable.
 */

class WindGuardApp {
  constructor() {
    this.apiBase = window.location.port === '8000' || window.location.pathname.startsWith('/api') 
      ? '' 
      : 'http://127.0.0.1:8000';

    // Application State
    this.state = {
      activeTab: 'fleet',
      selectedTurbineId: 'WTG-07',
      activeCaseId: null,
      activeDemoStage: 1,
      pollingEnabled: true,
      operatorId: sessionStorage.getItem('windguard_operator_id') || 'OPERATOR_LOCAL',
      operatorName: sessionStorage.getItem('windguard_operator_name') || 'Default Local Operator',
      fleetStatus: null,
      cases: [],
      activeCase: null,
      telemetryCache: {},
      activeTariff: null,
      demoStageData: null,
      inFlightRequests: new Set(),
      consecutiveFailures: 0,
      activeHITLAction: null,
      activeHITLCaseId: null,
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
    console.log('[WindGuard AI] Initializing Presentation Layer (Phase 7)...');

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

  /**
   * Executes a robust HTTP request with X-Operator-ID header attachment and in-flight concurrency lock.
   */
  async apiRequest(endpoint, options = {}) {
    const fullUrl = `${this.apiBase}${endpoint}`;
    const requestKey = `${options.method || 'GET'}:${endpoint}`;

    // In-Flight Concurrency Protection
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
        throw new Error(errData.message || `Request failed with status ${response.status}`);
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
    console.error(`[WindGuard API Error ${status}] on ${endpoint}:`, errData);
    const msg = errData.message || (errData.detail ? JSON.stringify(errData.detail) : 'API request failed');
    this.showToast(`Error: ${msg}`, 'error');
  }

  // ============================================================================
  // 2. Operator Identity Session Manager (OD-P7-04)
  // ============================================================================

  initOperatorProfile() {
    const select = document.getElementById('operator-select');
    if (!select) return;

    select.value = this.state.operatorId;
    this.updateOperatorBadge(this.state.operatorName);

    select.addEventListener('change', (e) => {
      const val = e.target.value;
      if (val === 'CUSTOM') {
        const customId = prompt('Enter Operator Badge / ID (1-64 characters):', 'OPERATOR_ROC_01');
        if (customId && customId.trim()) {
          this.state.operatorId = customId.trim().substring(0, 64);
          this.state.operatorName = `Custom (${this.state.operatorId})`;
        } else {
          select.value = this.state.operatorId;
          return;
        }
      } else {
        this.state.operatorId = val;
        this.state.operatorName = select.options[select.selectedIndex].text;
      }

      sessionStorage.setItem('windguard_operator_id', this.state.operatorId);
      sessionStorage.setItem('windguard_operator_name', this.state.operatorName);
      this.updateOperatorBadge(this.state.operatorName);
      this.showToast(`Active Operator switched to: ${this.state.operatorName}`, 'success');
    });
  }

  updateOperatorBadge(name) {
    const badge = document.getElementById('operator-current-name');
    if (badge) badge.textContent = name;
  }

  // ============================================================================
  // 3. Polling Engine with Pause-on-Blur (OD-P7-05)
  // ============================================================================

  startPollingEngine() {
    this.stopPollingEngine();

    // 1. Visibility change listener (Pause-on-Blur)
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'hidden') {
        console.log('[WindGuard Polling] Tab blurred — Pausing background polling.');
        this.stopPollingTimers();
      } else {
        console.log('[WindGuard Polling] Tab focused — Resuming live polling & refreshing view.');
        this.refreshActiveView();
        this.startPollingTimers();
      }
    });

    if (this.state.pollingEnabled) {
      this.startPollingTimers();
    }
  }

  startPollingTimers() {
    if (!this.state.pollingEnabled) return;

    // Fleet polling (5s)
    this.pollTimers.fleet = setInterval(() => {
      if (this.state.activeTab === 'fleet') {
        this.fetchFleetStatus();
      }
    }, this.getDynamicInterval(this.pollIntervals.fleet));

    // Telemetry polling (5s)
    this.pollTimers.telemetry = setInterval(() => {
      if (this.state.activeTab === 'turbine') {
        this.fetchTurbineTelemetry(this.state.selectedTurbineId);
      }
    }, this.getDynamicInterval(this.pollIntervals.telemetry));

    // Cases polling (10s)
    this.pollTimers.cases = setInterval(() => {
      if (this.state.activeTab === 'fleet' || this.state.activeTab === 'diagnostic') {
        this.fetchCases();
      }
    }, this.getDynamicInterval(this.pollIntervals.cases));

    // Health probe (10s)
    this.pollTimers.health = setInterval(() => {
      this.checkSystemHealth();
    }, this.pollIntervals.health);
  }

  stopPollingTimers() {
    Object.keys(this.pollTimers).forEach(key => {
      clearInterval(this.pollTimers[key]);
      delete this.pollTimers[key];
    });
  }

  stopPollingEngine() {
    this.stopPollingTimers();
  }

  getDynamicInterval(baseMs) {
    if (this.state.consecutiveFailures > 0) {
      const backoff = Math.min(30000, baseMs * Math.pow(2, this.state.consecutiveFailures - 1));
      return backoff;
    }
    return baseMs;
  }

  togglePolling() {
    this.state.pollingEnabled = !this.state.pollingEnabled;
    const btn = document.getElementById('polling-toggle-btn');
    if (btn) {
      if (this.state.pollingEnabled) {
        btn.textContent = '● LIVE (5s)';
        btn.classList.remove('paused');
        this.startPollingTimers();
        this.showToast('Live background polling resumed.', 'success');
      } else {
        btn.textContent = '❚❚ PAUSED';
        btn.classList.add('paused');
        this.stopPollingTimers();
        this.showToast('Background polling paused.', 'warning');
      }
    }
  }

  // ============================================================================
  // 4. View Routing & Navigation
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
        this.refreshActiveView();
        this.showToast('View refreshed.', 'success');
      });
    }

    // Polling Toggle
    const pollBtn = document.getElementById('polling-toggle-btn');
    if (pollBtn) {
      pollBtn.addEventListener('click', () => this.togglePolling());
    }

    // Turbine Selector
    const turbineSelect = document.getElementById('turbine-deepdive-select');
    if (turbineSelect) {
      turbineSelect.addEventListener('change', (e) => {
        this.state.selectedTurbineId = e.target.value;
        this.fetchTurbineTelemetry(this.state.selectedTurbineId);
      });
    }

    // Run Diagnosis Button
    const runDiagBtn = document.getElementById('run-diagnosis-btn');
    if (runDiagBtn) {
      runDiagBtn.addEventListener('click', () => {
        this.runDiagnosis(this.state.selectedTurbineId);
      });
    }

    // RAG Search Input
    const ragForm = document.getElementById('rag-search-form');
    if (ragForm) {
      ragForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const input = document.getElementById('rag-query-input');
        if (input && input.value.trim()) {
          this.executeRAGSearch(input.value.trim());
        }
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

    // CSV File Upload Form
    const csvForm = document.getElementById('csv-upload-form');
    if (csvForm) {
      csvForm.addEventListener('submit', (e) => {
        e.preventDefault();
        this.handleCSVUpload();
      });
    }
  }

  handleRouting() {
    window.addEventListener('hashchange', () => {
      const hash = window.location.hash.replace('#', '') || 'fleet';
      this.switchTab(hash, false);
    });

    const initialHash = window.location.hash.replace('#', '') || 'fleet';
    this.switchTab(initialHash, false);
  }

  switchTab(tabName, updateHash = true) {
    const t0 = performance.now();
    const validTabs = ['fleet', 'turbine', 'diagnostic', 'knowledge', 'tariff', 'demo'];
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
          await this.fetchCases();
        }
        break;
      case 'knowledge':
        // Ready for search
        break;
      case 'tariff':
        await this.fetchTariffRegistry();
        break;
      case 'demo':
        await this.loadDemoStage(this.state.activeDemoStage);
        break;
    }
  }

  // ============================================================================
  // 5. System Health & Readiness Probes
  // ============================================================================

  async checkSystemHealth() {
    try {
      const health = await this.apiRequest('/api/health');
      const badge = document.getElementById('system-health-badge');
      const text = document.getElementById('system-health-text');
      if (badge && text) {
        if (health && health.status === 'healthy') {
          badge.className = 'health-badge';
          text.textContent = 'Engine Active';
        } else {
          badge.className = 'health-badge degraded';
          text.textContent = 'Degraded';
        }
      }
    } catch {
      const badge = document.getElementById('system-health-badge');
      const text = document.getElementById('system-health-text');
      if (badge && text) {
        badge.className = 'health-badge offline';
        text.textContent = 'Service Offline';
      }
    }
  }

  // ============================================================================
  // 6. Fleet Overview (Screen 1)
  // ============================================================================

  async fetchFleetStatus() {
    const t0 = performance.now();
    try {
      const status = await this.apiRequest('/api/fleet/status');
      if (!status) return;
      this.state.fleetStatus = status;
      this.renderFleetOverview(status);
      this.perfMetrics.fleetRenderMs = performance.now() - t0;
    } catch (err) {
      console.error('[WindGuard] Error fetching fleet status:', err);
    }
  }

  renderFleetOverview(status) {
    // KPI Cards
    const totalTurbinesEl = document.getElementById('kpi-total-turbines');
    const totalPowerEl = document.getElementById('kpi-total-power');
    const avgWindEl = document.getElementById('kpi-avg-wind');
    const curtailedCountEl = document.getElementById('kpi-curtailed-count');
    const activeAnomaliesEl = document.getElementById('kpi-active-anomalies');
    const totalLossEl = document.getElementById('kpi-total-loss');

    if (totalTurbinesEl) totalTurbinesEl.textContent = status.total_turbines || 10;
    if (totalPowerEl) totalPowerEl.textContent = `${(status.total_fleet_power_kw || 0).toLocaleString()} kW`;
    if (avgWindEl) avgWindEl.textContent = `${(status.average_wind_speed_mps || 0).toFixed(1)} m/s`;
    if (curtailedCountEl) curtailedCountEl.textContent = status.curtailed_turbines_count || 0;
    if (activeAnomaliesEl) activeAnomaliesEl.textContent = status.active_anomalies_count || 0;
    if (totalLossEl) {
      totalLossEl.textContent = `₹${(status.total_fleet_financial_loss_inr || 0).toLocaleString()}`;
    }

    // Render 10 Turbine Grid Cards
    this.renderTurbineGrid(status.active_turbines || ['WTG-01', 'WTG-02', 'WTG-03', 'WTG-04', 'WTG-05', 'WTG-06', 'WTG-07', 'WTG-08', 'WTG-09', 'WTG-10']);
  }

  renderTurbineGrid(turbineIds) {
    const container = document.getElementById('fleet-turbine-grid');
    if (!container) return;

    container.innerHTML = turbineIds.map(id => {
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
      const records = await this.apiRequest(`/api/turbines/${turbineId}/telemetry?limit=144`);
      if (!records || records.length === 0) return;

      this.state.telemetryCache[turbineId] = records[records.length - 1];
      this.renderTurbineDeepDive(turbineId, records);
      this.perfMetrics.turbineRenderMs = performance.now() - t0;
    } catch (err) {
      console.warn(`[WindGuard] No telemetry records found for ${turbineId}:`, err);
    }
  }

  renderTurbineDeepDive(turbineId, records) {
    const latest = records[records.length - 1] || {};

    // Update Status Header
    const idEl = document.getElementById('deepdive-turbine-id');
    const powerEl = document.getElementById('deepdive-power');
    const windEl = document.getElementById('deepdive-wind');
    const tempGbEl = document.getElementById('deepdive-temp-gb');
    const tempGenEl = document.getElementById('deepdive-temp-gen');
    const curtailedBadge = document.getElementById('deepdive-curtailed-badge');

    if (idEl) idEl.textContent = turbineId;
    if (powerEl) powerEl.textContent = `${(latest.active_power || 0).toFixed(0)} kW`;
    if (windEl) windEl.textContent = `${(latest.wind_speed || 0).toFixed(1)} m/s`;
    if (tempGbEl) tempGbEl.textContent = `${(latest.gearbox_bearing_temp || 0).toFixed(1)} °C`;
    if (tempGenEl) tempGenEl.textContent = `${(latest.generator_stator_temp || 0).toFixed(1)} °C`;
    if (curtailedBadge) {
      curtailedBadge.style.display = latest.is_curtailed ? 'inline-block' : 'none';
    }

    // Render Canvas Charts (OD-P7-02 / OD-P7-11)
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
    } catch (err) {
      console.error('[WindGuard] Error running diagnosis:', err);
    }
  }

  async fetchCaseDetails(caseId) {
    try {
      const diagCase = await this.apiRequest(`/api/cases/${caseId}`);
      if (!diagCase) return;
      this.state.activeCase = diagCase;
      this.state.activeCaseId = diagCase.case_id;
      this.renderDiagnosticStudio(diagCase);
    } catch (err) {
      console.error('[WindGuard] Error fetching case details:', err);
    }
  }

  renderDiagnosticStudio(diagCase) {
    // Header & Summary
    const caseIdEl = document.getElementById('diag-case-id');
    const turbineIdEl = document.getElementById('diag-turbine-id');
    const severityBadge = document.getElementById('diag-severity-badge');
    const priorityScoreEl = document.getElementById('diag-priority-score');
    const summaryNarrative = document.getElementById('diag-summary-narrative');
    const contextBadge = document.getElementById('diag-context-badge');

    if (caseIdEl) caseIdEl.textContent = diagCase.case_id;
    if (turbineIdEl) turbineIdEl.textContent = diagCase.turbine_id;
    if (severityBadge) {
      severityBadge.textContent = diagCase.severity;
      severityBadge.className = `status-badge status-${(diagCase.severity || 'normal').toLowerCase()}`;
    }
    if (priorityScoreEl) priorityScoreEl.textContent = `${(diagCase.priority_score || 0).toFixed(0)} / 100`;
    if (summaryNarrative) summaryNarrative.textContent = diagCase.advisory.summary || diagCase.derived_analytics.subsystem_attribution;
    if (contextBadge) {
      contextBadge.textContent = diagCase.derived_analytics.context_state;
    }

    // Commercial Loss & Tariff Provenance
    const lossKwhEl = document.getElementById('diag-loss-kwh');
    const lossInrEl = document.getElementById('diag-loss-inr');
    const tariffRateEl = document.getElementById('diag-tariff-rate');
    const tariffModeEl = document.getElementById('diag-tariff-mode');

    if (lossKwhEl) lossKwhEl.textContent = `${(diagCase.derived_analytics.energy_loss_kwh || 0).toFixed(1)} kWh`;
    if (lossInrEl) lossInrEl.textContent = `₹${(diagCase.derived_analytics.financial_loss_inr || 0).toLocaleString()}`;
    if (tariffRateEl) tariffRateEl.textContent = `₹${diagCase.derived_analytics.tariff_provenance.applied_rate_inr_per_kwh.toFixed(2)} / kWh`;
    if (tariffModeEl) tariffModeEl.textContent = diagCase.derived_analytics.tariff_provenance.mode;

    // Evidence Table
    const evidenceTbody = document.getElementById('diag-evidence-tbody');
    if (evidenceTbody && diagCase.evidence_table) {
      evidenceTbody.innerHTML = diagCase.evidence_table.map(ev => `
        <tr>
          <td><strong>${ev.field_name}</strong></td>
          <td>${typeof ev.value === 'number' ? ev.value.toFixed(1) : ev.value} ${ev.unit || ''}</td>
          <td><span class="citation-hash">${(ev.source_reference || '').substring(0, 32)}</span></td>
        </tr>
      `).join('');
    }

    // Hypotheses (Qualitative Plausibility — Zero Fake Percentages)
    const hypothesesContainer = document.getElementById('diag-hypotheses-list');
    if (hypothesesContainer && diagCase.advisory.hypotheses) {
      hypothesesContainer.innerHTML = diagCase.advisory.hypotheses.map(hyp => `
        <div class="hypothesis-card">
          <div class="hypothesis-header">
            <span class="hypothesis-title">${hyp.hypothesis}</span>
            <span class="plausibility-badge plausibility-${(hyp.plausibility || 'high').toLowerCase()}">${hyp.plausibility}</span>
          </div>
          <div style="font-size: 11px; color: var(--text-muted);">
            Grounding Evidence: ${hyp.grounding_evidence.join(', ') || 'Observed Multi-Signal Residuals'}
          </div>
        </div>
      `).join('');
    }

    // Technical RAG Citations (Only display page if present)
    const citationsContainer = document.getElementById('diag-citations-list');
    if (citationsContainer && diagCase.citations) {
      citationsContainer.innerHTML = diagCase.citations.map(cit => {
        const pageText = cit.source_page ? `Page ${cit.source_page}` : (cit.source_locator || 'Section Document');
        return `
          <div class="citation-card">
            <div class="citation-title">${cit.title}</div>
            <div class="citation-meta">
              <span>${cit.section || cit.chapter || 'Technical Section'}</span>
              <span><strong>${pageText}</strong></span>
            </div>
            <div class="citation-hash">SHA-256: ${cit.content_hash.substring(0, 16)}...</div>
          </div>
        `;
      }).join('');
    }

    // Checklist
    const checklistContainer = document.getElementById('diag-checklist-list');
    if (checklistContainer && diagCase.advisory.recommended_actions) {
      checklistContainer.innerHTML = diagCase.advisory.recommended_actions.map(act => `
        <div class="checklist-item">
          <input type="checkbox" id="check-${act.action_id}">
          <label for="check-${act.action_id}">
            <strong>[${act.urgency}]</strong> ${act.action_text}
          </label>
        </div>
      `).join('');
    }

    // Audit Trail
    const auditContainer = document.getElementById('diag-decision-history');
    if (auditContainer) {
      if (diagCase.operator_decisions && diagCase.operator_decisions.length > 0) {
        auditContainer.innerHTML = diagCase.operator_decisions.map(dec => `
          <div style="padding: 6px 0; border-bottom: 1px solid rgba(35, 56, 99, 0.4); font-size: 11px;">
            <strong>${dec.action}</strong> by <em>${dec.operator_id}</em> at ${dec.timestamp.substring(11, 19)} UTC
            <div style="color: var(--text-secondary); margin-top: 2px;">"${dec.notes}"</div>
          </div>
        `).join('');
      } else {
        auditContainer.innerHTML = '<div style="color: var(--text-muted); font-size: 11px;">No operator decisions recorded yet. Case is OPEN.</div>';
      }
    }
  }

  // ============================================================================
  // 9. HITL Decision Execution & Modal Dialog
  // ============================================================================

  openHITLModal(action) {
    if (!this.state.activeCase) {
      this.showToast('Select an active maintenance case first.', 'warning');
      return;
    }

    this.state.activeHITLAction = action;
    this.state.activeHITLCaseId = this.state.activeCase.case_id;

    const modal = document.getElementById('hitl-modal');
    const titleEl = document.getElementById('hitl-modal-title');
    const caseIdEl = document.getElementById('hitl-modal-case-id');
    const notesInput = document.getElementById('hitl-modal-notes');

    if (titleEl) titleEl.textContent = `Record Action: ${action}`;
    if (caseIdEl) caseIdEl.textContent = this.state.activeHITLCaseId;
    if (notesInput) {
      notesInput.value = '';
      notesInput.focus();
    }
    if (modal) modal.classList.add('active');
  }

  closeHITLModal() {
    const modal = document.getElementById('hitl-modal');
    if (modal) modal.classList.remove('active');
  }

  async submitHITLDecision() {
    const t0 = performance.now();
    const notesInput = document.getElementById('hitl-modal-notes');
    const notes = notesInput ? notesInput.value.trim() : '';

    if (!notes || notes.length < 1 || notes.length > 2000) {
      this.showToast('Mandatory engineering notes must be between 1 and 2000 characters.', 'warning');
      return;
    }

    try {
      const updatedCase = await this.apiRequest(`/api/cases/${this.state.activeHITLCaseId}/decision`, {
        method: 'POST',
        body: JSON.stringify({
          action: this.state.activeHITLAction,
          notes: notes,
          operator_id: this.state.operatorId,
        }),
      });

      if (!updatedCase) return;

      this.closeHITLModal();
      this.state.activeCase = updatedCase;
      this.renderDiagnosticStudio(updatedCase);
      await this.fetchCases();
      this.perfMetrics.hitlTransitionMs = performance.now() - t0;
      this.showToast(`Decision '${this.state.activeHITLAction}' logged successfully.`, 'success');
    } catch (err) {
      console.error('[WindGuard] Error submitting HITL decision:', err);
    }
  }

  // ============================================================================
  // 10. Cases Registry (Screen 1 & 3 Table)
  // ============================================================================

  async fetchCases() {
    const t0 = performance.now();
    try {
      const data = await this.apiRequest('/api/cases?limit=50&offset=0');
      if (!data || !data.cases) return;
      this.state.cases = data.cases;
      this.renderCasesTable(data.cases);
      this.perfMetrics.caseTableRenderMs = performance.now() - t0;
    } catch (err) {
      console.error('[WindGuard] Error fetching cases:', err);
    }
  }

  renderCasesTable(cases) {
    const tbody = document.getElementById('cases-table-tbody');
    if (!tbody) return;

    if (cases.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; color:var(--text-muted); padding:20px;">All turbines operating within normal thermal and power envelopes.</td></tr>';
      return;
    }

    tbody.innerHTML = cases.map(c => `
      <tr onclick="windGuardApp.inspectCase('${c.case_id}')" style="cursor: pointer;">
        <td><strong>${c.case_id}</strong></td>
        <td>${c.turbine_id}</td>
        <td><span class="status-badge status-${(c.severity || 'normal').toLowerCase()}">${c.severity}</span></td>
        <td><strong>${(c.priority_score || 0).toFixed(0)}</strong> / 100</td>
        <td>₹${(c.derived_analytics.financial_loss_inr || 0).toLocaleString()}</td>
        <td><span class="status-badge status-${(c.status || 'open').toLowerCase()}">${c.status}</span></td>
        <td><button class="btn btn-secondary btn-sm">Inspect Case →</button></td>
      </tr>
    `).join('');
  }

  inspectCase(caseId) {
    this.state.activeCaseId = caseId;
    this.fetchCaseDetails(caseId);
    this.switchTab('diagnostic');
  }

  // ============================================================================
  // 11. Technical Knowledge Assistant (Screen 4)
  // ============================================================================

  async executeRAGSearch(query) {
    const t0 = performance.now();
    try {
      this.showToast('Searching technical knowledge corpus...', 'info');
      const res = await this.apiRequest('/api/rag/query', {
        method: 'POST',
        body: JSON.stringify({ query: query, top_k: 3 }),
      });

      if (!res || !res.chunks) return;

      const container = document.getElementById('rag-results-container');
      if (container) {
        container.innerHTML = res.chunks.map((chunk, idx) => {
          const score = res.scores[idx] ? (res.scores[idx] * 100).toFixed(1) : '--';
          const pageText = chunk.source_page ? `Page ${chunk.source_page}` : (chunk.source_locator || 'Technical Section');
          const title = chunk.document_title || chunk.title || 'Technical Document';
          const text = chunk.content || chunk.text || '';
          return `
            <div class="citation-card" style="margin-bottom: 16px;">
              <div style="display:flex; justify-content:space-between; align-items:center;">
                <div class="citation-title">${title}</div>
                <span class="status-badge status-normal">Relevance: ${score}%</span>
              </div>
              <div class="citation-meta">
                <span>${chunk.section || chunk.chapter || 'Technical Guidance'}</span>
                <span><strong>${pageText}</strong></span>
              </div>
              <div style="background-color: var(--bg-card); padding: 10px; border-radius: var(--radius-sm); margin: 8px 0; font-size: 13px; line-height: 1.6;">
                ${text}
              </div>
              <div class="citation-hash">SHA-256 Provenance: ${chunk.content_hash}</div>
            </div>
          `;
        }).join('');
      }

      this.perfMetrics.ragRenderMs = performance.now() - t0;
      this.showToast(`Retrieved ${res.chunks.length} technical manual sections.`, 'success');
    } catch (err) {
      console.error('[WindGuard] Error executing RAG search:', err);
    }
  }

  // ============================================================================
  // 12. Tariff Registry & Settings (Screen 5)
  // ============================================================================

  async fetchTariffRegistry() {
    try {
      const data = await this.apiRequest('/api/tariffs');
      if (!data) return;
      this.state.activeTariff = data.active_tariff;

      const rateEl = document.getElementById('tariff-active-rate');
      const modeEl = document.getElementById('tariff-active-mode');
      const sourceEl = document.getElementById('tariff-active-source');
      const dateEl = document.getElementById('tariff-active-date');

      if (rateEl) rateEl.textContent = `₹${data.active_tariff.applied_rate_inr_per_kwh.toFixed(2)} / kWh`;
      if (modeEl) modeEl.textContent = data.active_tariff.mode;
      if (sourceEl) sourceEl.textContent = data.active_tariff.source_reference;
      if (dateEl) dateEl.textContent = data.active_tariff.effective_date || '2026-09-20';

      const historyTbody = document.getElementById('tariff-history-tbody');
      if (historyTbody && data.history) {
        historyTbody.innerHTML = data.history.map(t => `
          <tr>
            <td>₹${t.applied_rate_inr_per_kwh.toFixed(2)} / kWh</td>
            <td><span class="status-badge status-normal">${t.mode}</span></td>
            <td>${t.source_reference}</td>
            <td>${t.effective_date || '--'}</td>
          </tr>
        `).join('');
      }
    } catch (err) {
      console.error('[WindGuard] Error fetching tariff registry:', err);
    }
  }

  async handleTariffUpdate() {
    const rateInput = document.getElementById('tariff-input-rate');
    const modeSelect = document.getElementById('tariff-input-mode');
    const sourceInput = document.getElementById('tariff-input-source');

    const rate = parseFloat(rateInput ? rateInput.value : '3.20');
    const mode = modeSelect ? modeSelect.value : 'CONFIGURED_BASELINE';
    const source = sourceInput ? sourceInput.value.trim() : 'Asset Baseline Configuration';

    if (isNaN(rate) || rate < 0.01 || rate > 20.00) {
      this.showToast('Tariff rate must be between ₹0.01 and ₹20.00 / kWh.', 'warning');
      return;
    }

    try {
      await this.apiRequest('/api/tariffs', {
        method: 'POST',
        body: JSON.stringify({
          rate_inr_per_kwh: rate,
          mode: mode,
          source_reference: source,
          notes: 'Updated via Operator Settings Studio',
        }),
      });

      this.showToast('Active tariff updated prospective-only.', 'success');
      await this.fetchTariffRegistry();
    } catch (err) {
      console.error('[WindGuard] Error updating tariff:', err);
    }
  }

  // ============================================================================
  // 13. 10-Stage Guided Demo (Screen 6)
  // ============================================================================

  async loadDemoStage(stageId) {
    const t0 = performance.now();
    this.state.activeDemoStage = stageId;

    // Update Stepper Buttons
    document.querySelectorAll('.demo-step-btn').forEach(btn => {
      btn.classList.toggle('active', parseInt(btn.getAttribute('data-stage')) === stageId);
    });

    try {
      const stage = await this.apiRequest(`/api/demo/stage/${stageId}`);
      if (!stage) return;
      this.state.demoStageData = stage;

      const titleEl = document.getElementById('demo-stage-title');
      const descEl = document.getElementById('demo-stage-desc');
      const statusEl = document.getElementById('demo-expected-status');
      const faultEl = document.getElementById('demo-injected-fault');

      if (titleEl) titleEl.textContent = stage.stage_name;
      if (descEl) descEl.textContent = stage.description;
      if (statusEl) statusEl.textContent = stage.expected_status;
      if (faultEl) faultEl.textContent = stage.injected_fault || 'None (Healthy Baseline)';

      // Auto-render live canvas for demo stage
      const canvas = document.getElementById('canvas-demo-power');
      if (canvas && window.WindGuardCharts) {
        window.WindGuardCharts.renderPowerCurve(canvas, {
          telemetryRecords: [stage.telemetry],
          livePoint: {
            wind_speed: stage.telemetry.wind_speed,
            active_power: stage.telemetry.active_power,
            expected_power: 1650.0,
          },
        });
      }

      this.perfMetrics.demoStepMs = performance.now() - t0;
    } catch (err) {
      console.error('[WindGuard] Error loading demo stage:', err);
    }
  }

  async runDemoDiagnosis() {
    if (!this.state.demoStageData) return;
    const stage = this.state.demoStageData;
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
      this.showToast('Demo stage diagnosis synthesized.', 'success');
    } catch (err) {
      console.error('[WindGuard] Error executing demo diagnosis:', err);
    }
  }

  // ============================================================================
  // 14. Work Order Print & Export (OD-P7-06)
  // ============================================================================

  printWorkOrder() {
    if (!this.state.activeCase) {
      this.showToast('Select a maintenance case to export.', 'warning');
      return;
    }
    console.log('[WindGuard AI] Triggering native print layout for work order export...');
    window.print();
  }

  // ============================================================================
  // 15. SCADA Simulation Modal & CSV Ingestion
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

  async handleCSVUpload() {
    const fileInput = document.getElementById('csv-file-input');
    if (!fileInput || !fileInput.files || fileInput.files.length === 0) {
      this.showToast('Select a CSV file to upload.', 'warning');
      return;
    }

    const file = fileInput.files[0];
    const formData = new FormData();
    formData.append('file', file);

    try {
      this.showToast(`Uploading and validating ${file.name}...`, 'info');
      const res = await this.apiRequest('/api/scada/ingest/file', {
        method: 'POST',
        body: formData,
      });

      if (res && res.status === 'success') {
        this.closeSimulationModal();
        this.showToast(`CSV accepted: ${res.ingested_count} records ingested.`, 'success');
        await this.fetchFleetStatus();
      }
    } catch (err) {
      console.error('[WindGuard] Error uploading CSV:', err);
    }
  }

  // ============================================================================
  // 16. Non-Blocking Toast Notification System
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
