/**
 * IntelliWatch Operator Dashboard Logic
 * Connects to FastAPI backend endpoints via polling to provide real-time
 * industrial safety telemetry, scene understanding graphs, PPE compliance,
 * risk reasoning, early-warning alerts, and evidence inspection.
 */

// Configuration & Runtime State
const CONFIG = {
  apiBase: "",
  pollIntervalMs: 1000,
  maxCanvasWidth: 1280,
  maxCanvasHeight: 720,
};

let state = {
  isPolling: true,
  pollTimer: null,
  currentAssessment: null,
  incidents: [],
  systemStatus: null,
  activeTab: "scene",
  selectedIncident: null,

  // Media Upload & Analysis State
  uploadMode: "image", // "image" or "video"
  selectedFile: null,
  activeJobId: null,
  jobPollTimer: null,
  isSingleFrame: false,

  // Step 16: Interactive Safety Zones State
  zones: [],
  isDrawingZone: false,
  currentZonePoints: [],
  cursorPos: null,
  editingZoneId: null,

  // Step 17: Explainability, Evidence & Analytics State
  incidentFilters: {
    risk_level: "",
    event_type: "",
    track_id: "",
    zone: "",
  },
  analyticsSummary: null,
  activeExplanation: null,
};

// DOM Elements
const elements = {
  cpuBadge: document.getElementById("cpuBadge"),
  fpsBadge: document.getElementById("fpsBadge"),
  latencyBadge: document.getElementById("latencyBadge"),
  tracksBadge: document.getElementById("tracksBadge"),
  incidentsBadge: document.getElementById("incidentsBadge"),
  statusDot: document.getElementById("statusDot"),
  pollToggleBtn: document.getElementById("pollToggleBtn"),
  refreshBtn: document.getElementById("refreshBtn"),
  canvas: document.getElementById("sceneCanvas"),
  sceneRelationshipsList: document.getElementById("sceneRelationshipsList"),
  entitySummaryList: document.getElementById("entitySummaryList"),
  safetyEventContainer: document.getElementById("safetyEventContainer"),
  riskContainer: document.getElementById("riskContainer"),
  warningContainer: document.getElementById("warningContainer"),
  ppeContainer: document.getElementById("ppeContainer"),
  behaviorContainer: document.getElementById("behaviorContainer"),
  depthContainer: document.getElementById("depthContainer"),
  incidentTableBody: document.getElementById("incidentTableBody"),
  evidenceModal: document.getElementById("evidenceModal"),
  closeModalBtn: document.getElementById("closeModalBtn"),
  modalTitle: document.getElementById("modalTitle"),
  modalEvidenceImage: document.getElementById("modalEvidenceImage"),
  noEvidenceNotice: document.getElementById("noEvidenceNotice"),
  modalIncidentDetails: document.getElementById("modalIncidentDetails"),

  // Upload & Analysis Controls
  uploadSection: document.getElementById("uploadSection"),
  modeImageBtn: document.getElementById("modeImageBtn"),
  modeVideoBtn: document.getElementById("modeVideoBtn"),
  dropZone: document.getElementById("dropZone"),
  dropZoneIcon: document.getElementById("dropZoneIcon"),
  dropZoneText: document.getElementById("dropZoneText"),
  dropZoneHint: document.getElementById("dropZoneHint"),
  mediaFileInput: document.getElementById("mediaFileInput"),
  selectedFileCard: document.getElementById("selectedFileCard"),
  selectedFileIcon: document.getElementById("selectedFileIcon"),
  selectedFileName: document.getElementById("selectedFileName"),
  selectedFileType: document.getElementById("selectedFileType"),
  selectedFileSize: document.getElementById("selectedFileSize"),
  clearFileBtn: document.getElementById("clearFileBtn"),
  analyzeBtn: document.getElementById("analyzeBtn"),
  newAnalysisBtn: document.getElementById("newAnalysisBtn"),

  // Processing & Telemetry Card
  processingCard: document.getElementById("processingCard"),
  analysisStatusPill: document.getElementById("analysisStatusPill"),
  processingTitle: document.getElementById("processingTitle"),
  processingPct: document.getElementById("processingPct"),
  analysisProgressBar: document.getElementById("analysisProgressBar"),
  telFile: document.getElementById("telFile"),
  telFrames: document.getElementById("telFrames"),
  telFps: document.getElementById("telFps"),
  telRisk: document.getElementById("telRisk"),
  telTracks: document.getElementById("telTracks"),
  telIncidents: document.getElementById("telIncidents"),
  processingNotice: document.getElementById("processingNotice"),

  // Viewport Media Elements
  viewportStateBadge: document.getElementById("viewportStateBadge"),
  viewportContainer: document.getElementById("viewportContainer"),
  viewportImage: document.getElementById("viewportImage"),
  viewportVideo: document.getElementById("viewportVideo"),
  viewportCompletedSummary: document.getElementById("viewportCompletedSummary"),
  sumTotalFrames: document.getElementById("sumTotalFrames"),
  sumProcessedFrames: document.getElementById("sumProcessedFrames"),
  sumAvgFps: document.getElementById("sumAvgFps"),
  sumAvgLatency: document.getElementById("sumAvgLatency"),
  sumIncidents: document.getElementById("sumIncidents"),
  sumRisk: document.getElementById("sumRisk"),
  viewIncidentsBtn: document.getElementById("viewIncidentsBtn"),

  // Step 16: Interactive Safety Zones Controls
  zoneOverlayCanvas: document.getElementById("zoneOverlayCanvas"),
  tabZonesBtn: document.getElementById("tabZonesBtn"),
  startDrawZoneBtn: document.getElementById("startDrawZoneBtn"),
  zoneDrawForm: document.getElementById("zoneDrawForm"),
  zoneFormTitle: document.getElementById("zoneFormTitle"),
  zonePointCountBadge: document.getElementById("zonePointCountBadge"),
  zoneNameInput: document.getElementById("zoneNameInput"),
  zoneTypeSelect: document.getElementById("zoneTypeSelect"),
  zoneDwellInput: document.getElementById("zoneDwellInput"),
  saveZoneBtn: document.getElementById("saveZoneBtn"),
  clearPointsBtn: document.getElementById("clearPointsBtn"),
  cancelDrawBtn: document.getElementById("cancelDrawBtn"),
  configuredZoneCount: document.getElementById("configuredZoneCount"),
  configuredZonesList: document.getElementById("configuredZonesList"),

  // Step 17: Analytics & Filter Controls
  tabAnalyticsBtn: document.getElementById("tabAnalyticsBtn"),
  refreshAnalyticsBtn: document.getElementById("refreshAnalyticsBtn"),
  kpiTotalIncidents: document.getElementById("kpiTotalIncidents"),
  kpiCriticalIncidents: document.getElementById("kpiCriticalIncidents"),
  kpiZoneIntrusions: document.getElementById("kpiZoneIntrusions"),
  kpiPpeViolations: document.getElementById("kpiPpeViolations"),
  kpiAvgDuration: document.getElementById("kpiAvgDuration"),
  kpiActiveIncidents: document.getElementById("kpiActiveIncidents"),
  kpiProximityEvents: document.getElementById("kpiProximityEvents"),
  analyticsEventTypeDist: document.getElementById("analyticsEventTypeDist"),
  analyticsActiveZonesList: document.getElementById("analyticsActiveZonesList"),

  filterRiskTier: document.getElementById("filterRiskTier"),
  filterEventType: document.getElementById("filterEventType"),
  filterTrackId: document.getElementById("filterTrackId"),
  filterZone: document.getElementById("filterZone"),
  applyFiltersBtn: document.getElementById("applyFiltersBtn"),
  resetFiltersBtn: document.getElementById("resetFiltersBtn"),

  downloadPackageBtn: document.getElementById("downloadPackageBtn"),
  modalEvidenceBadge: document.getElementById("modalEvidenceBadge"),
  modalRiskTrendCanvas: document.getElementById("modalRiskTrendCanvas"),
  riskTrendStatus: document.getElementById("riskTrendStatus"),
  riskTrendNotice: document.getElementById("riskTrendNotice"),
  fwWho: document.getElementById("fwWho"),
  fwWhat: document.getElementById("fwWhat"),
  fwWhere: document.getElementById("fwWhere"),
  fwWhen: document.getElementById("fwWhen"),
  fwWhyList: document.getElementById("fwWhyList"),
  riskBreakdownBody: document.getElementById("riskBreakdownBody"),
  riskBreakdownFinal: document.getElementById("riskBreakdownFinal"),
  modalIncidentTimeline: document.getElementById("modalIncidentTimeline"),
  modalSceneAndWarnings: document.getElementById("modalSceneAndWarnings"),
};

// -------------------------------------------------------------
// INITIALIZATION
// -------------------------------------------------------------
document.addEventListener("DOMContentLoaded", () => {
  setupTabs();
  setupEventListeners();
  setupUploadControls();
  initCanvas();
  initZonesModule();
  fetchData();
  startPolling();
});


function setupTabs() {
  const tabs = document.querySelectorAll(".tab-btn");
  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      tabs.forEach((t) => t.classList.remove("active"));
      document.querySelectorAll(".tab-content").forEach((c) => c.classList.remove("active"));

      tab.classList.add("active");
      const targetId = tab.dataset.tab;
      const targetContent = document.getElementById(targetId);
      if (targetContent) targetContent.classList.add("active");
      state.activeTab = targetId;

      if (targetId === "tab-analytics") {
        fetchAnalytics();
      }
    });
  });
}

function setupEventListeners() {
  if (elements.pollToggleBtn) {
    elements.pollToggleBtn.addEventListener("click", () => {
      state.isPolling = !state.isPolling;
      elements.pollToggleBtn.textContent = state.isPolling ? "Pause Polling" : "Resume Polling";
      elements.pollToggleBtn.classList.toggle("btn-primary", !state.isPolling);
      if (state.isPolling) {
        startPolling();
      } else {
        stopPolling();
      }
    });
  }

  if (elements.refreshBtn) {
    elements.refreshBtn.addEventListener("click", () => {
      fetchData();
    });
  }

  if (elements.closeModalBtn) {
    elements.closeModalBtn.addEventListener("click", closeModal);
  }

  if (elements.evidenceModal) {
    elements.evidenceModal.addEventListener("click", (e) => {
      if (e.target === elements.evidenceModal) closeModal();
    });
  }

  // Step 17: Incident Filters
  if (elements.applyFiltersBtn) {
    elements.applyFiltersBtn.addEventListener("click", () => {
      state.incidentFilters.risk_level = elements.filterRiskTier ? elements.filterRiskTier.value : "";
      state.incidentFilters.event_type = elements.filterEventType ? elements.filterEventType.value : "";
      state.incidentFilters.track_id = elements.filterTrackId ? elements.filterTrackId.value.trim() : "";
      state.incidentFilters.zone = elements.filterZone ? elements.filterZone.value.trim() : "";
      fetchFilteredIncidents();
    });
  }

  if (elements.resetFiltersBtn) {
    elements.resetFiltersBtn.addEventListener("click", () => {
      if (elements.filterRiskTier) elements.filterRiskTier.value = "";
      if (elements.filterEventType) elements.filterEventType.value = "";
      if (elements.filterTrackId) elements.filterTrackId.value = "";
      if (elements.filterZone) elements.filterZone.value = "";
      state.incidentFilters = { risk_level: "", event_type: "", track_id: "", zone: "" };
      fetchFilteredIncidents();
    });
  }

  // Step 17: Analytics & Evidence Package
  if (elements.refreshAnalyticsBtn) {
    elements.refreshAnalyticsBtn.addEventListener("click", () => {
      fetchAnalytics();
    });
  }

  if (elements.downloadPackageBtn) {
    elements.downloadPackageBtn.addEventListener("click", () => {
      downloadEvidencePackage();
    });
  }
}

// -------------------------------------------------------------
// UPLOAD & ANALYSIS WORKFLOW
// -------------------------------------------------------------
function setupUploadControls() {
  if (!elements.uploadSection) return;

  // Mode toggling
  if (elements.modeImageBtn && elements.modeVideoBtn) {
    elements.modeImageBtn.addEventListener("click", () => setUploadMode("image"));
    elements.modeVideoBtn.addEventListener("click", () => setUploadMode("video"));
  }

  // File Picker Click
  if (elements.dropZone && elements.mediaFileInput) {
    elements.dropZone.addEventListener("click", () => {
      elements.mediaFileInput.click();
    });

    // Drag and Drop events
    elements.dropZone.addEventListener("dragover", (e) => {
      e.preventDefault();
      elements.dropZone.classList.add("dragover");
    });

    elements.dropZone.addEventListener("dragleave", (e) => {
      e.preventDefault();
      elements.dropZone.classList.remove("dragover");
    });

    elements.dropZone.addEventListener("drop", (e) => {
      e.preventDefault();
      elements.dropZone.classList.remove("dragover");
      if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        handleFileSelected(e.dataTransfer.files[0]);
      }
    });

    elements.mediaFileInput.addEventListener("change", (e) => {
      if (e.target.files && e.target.files.length > 0) {
        handleFileSelected(e.target.files[0]);
      }
    });
  }

  // Clear File Selection
  if (elements.clearFileBtn) {
    elements.clearFileBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      clearSelectedFile();
    });
  }

  // Analyze Button
  if (elements.analyzeBtn) {
    elements.analyzeBtn.addEventListener("click", () => {
      executeAnalysis();
    });
  }

  // New Analysis Button
  if (elements.newAnalysisBtn) {
    elements.newAnalysisBtn.addEventListener("click", () => {
      resetAnalysisState();
    });
  }

  // View Incidents Button
  if (elements.viewIncidentsBtn) {
    elements.viewIncidentsBtn.addEventListener("click", () => {
      const incTable = document.querySelector(".incident-panel");
      if (incTable) incTable.scrollIntoView({ behavior: "smooth" });
    });
  }
}

function getFileExtension(filename) {
  return (filename.substring(filename.lastIndexOf(".")) || "").toLowerCase();
}

function formatBytes(bytes) {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / (1024 * 1024)).toFixed(1) + " MB";
}

function setUploadMode(mode) {
  state.uploadMode = mode;
  if (elements.modeImageBtn && elements.modeVideoBtn) {
    elements.modeImageBtn.classList.toggle("active", mode === "image");
    elements.modeVideoBtn.classList.toggle("active", mode === "video");
  }

  if (elements.mediaFileInput) {
    elements.mediaFileInput.accept = mode === "image"
      ? ".jpg,.jpeg,.png"
      : ".mp4,.avi,.mov,.mkv";
  }

  if (elements.dropZoneHint) {
    elements.dropZoneHint.textContent = mode === "image"
      ? "Supported: JPG, JPEG, PNG (Max 25MB)"
      : "Supported: MP4, AVI, MOV, MKV (Max 100MB)";
  }

  // If already selected file doesn't match new mode, clear it
  if (state.selectedFile) {
    const ext = getFileExtension(state.selectedFile.name);
    const validImg = [".jpg", ".jpeg", ".png"].includes(ext);
    const validVid = [".mp4", ".avi", ".mov", ".mkv"].includes(ext);
    if ((mode === "image" && !validImg) || (mode === "video" && !validVid)) {
      clearSelectedFile();
    }
  }
}

function handleFileSelected(file) {
  const ext = getFileExtension(file.name);
  const isImageExt = [".jpg", ".jpeg", ".png"].includes(ext);
  const isVideoExt = [".mp4", ".avi", ".mov", ".mkv"].includes(ext);

  if (!isImageExt && !isVideoExt) {
    alert("Unsupported file type. Please upload JPG, PNG, MP4, AVI, MOV, or MKV.");
    return;
  }

  // Automatically sync mode with dropped media type
  if (isImageExt && state.uploadMode !== "image") {
    setUploadMode("image");
  } else if (isVideoExt && state.uploadMode !== "video") {
    setUploadMode("video");
  }

  state.selectedFile = file;

  // Update selected file card
  if (elements.selectedFileName) elements.selectedFileName.textContent = file.name;
  if (elements.selectedFileType) elements.selectedFileType.textContent = isImageExt ? "IMAGE" : "VIDEO";
  if (elements.selectedFileSize) elements.selectedFileSize.textContent = formatBytes(file.size);
  if (elements.selectedFileIcon) elements.selectedFileIcon.textContent = isImageExt ? "🖼️" : "🎬";

  if (elements.dropZone) elements.dropZone.style.display = "none";
  if (elements.selectedFileCard) elements.selectedFileCard.style.display = "flex";
  if (elements.analyzeBtn) elements.analyzeBtn.disabled = false;
  if (elements.viewportStateBadge) elements.viewportStateBadge.textContent = "[FILE SELECTED - READY]";
}

function clearSelectedFile() {
  state.selectedFile = null;
  if (elements.mediaFileInput) elements.mediaFileInput.value = "";
  if (elements.dropZone) elements.dropZone.style.display = "flex";
  if (elements.selectedFileCard) elements.selectedFileCard.style.display = "none";
  if (elements.analyzeBtn) elements.analyzeBtn.disabled = true;
  if (elements.viewportStateBadge) elements.viewportStateBadge.textContent = "[IDLE]";
}

async function executeAnalysis() {
  if (!state.selectedFile) return;

  const file = state.selectedFile;
  const isImage = state.uploadMode === "image";

  // Transition UI to PROCESSING state
  elements.analyzeBtn.disabled = true;
  elements.analyzeBtn.textContent = "Analyzing...";
  elements.processingCard.style.display = "block";
  elements.analysisStatusPill.className = "status-pill status-processing";
  elements.analysisStatusPill.textContent = "PROCESSING";
  elements.processingTitle.textContent = isImage
    ? "IntelliWatch is analyzing image..."
    : "IntelliWatch is analyzing video stream...";
  elements.processingPct.textContent = "0%";
  elements.analysisProgressBar.style.width = "0%";
  elements.processingNotice.style.display = "none";
  elements.viewportCompletedSummary.style.display = "none";
  elements.viewportStateBadge.textContent = "[PROCESSING]";

  elements.telFile.textContent = file.name;
  elements.telFrames.textContent = isImage ? "0 / 1" : "0 / --";
  elements.telFps.textContent = "-- FPS";
  elements.telRisk.textContent = "--";
  elements.telTracks.textContent = "--";
  elements.telIncidents.textContent = "--";

  const formData = new FormData();
  formData.append("file", file);

  if (isImage) {
    try {
      const res = await fetch(`${CONFIG.apiBase}/api/v1/analyze/image`, {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(errJson.detail || "Image analysis failed");
      }

      const result = await res.json();
      state.isSingleFrame = true;
      state.currentAssessment = result.assessment;

      // Update Viewport with annotated image
      elements.canvas.style.display = "none";
      elements.viewportVideo.style.display = "none";
      elements.viewportImage.src = result.annotated_media_url + "?t=" + Date.now();
      elements.viewportImage.style.display = "block";
      elements.viewportStateBadge.textContent = "[SINGLE-FRAME COMPLETE]";

      // Update Processing Card
      elements.analysisStatusPill.className = "status-pill status-completed";
      elements.analysisStatusPill.textContent = "COMPLETED";
      elements.processingTitle.textContent = "Image Analysis Complete";
      elements.processingPct.textContent = "100%";
      elements.analysisProgressBar.style.width = "100%";

      const fpsVal = result.assessment.processing_time_ms > 0
        ? (1000.0 / result.assessment.processing_time_ms).toFixed(1)
        : "N/A";
      elements.telFrames.textContent = "1 / 1";
      elements.telFps.textContent = `${fpsVal} FPS`;
      elements.telRisk.textContent = result.highest_risk_level;
      elements.telTracks.textContent = result.workers_count;
      elements.telIncidents.textContent = (result.new_incident_ids || []).length;

      // Render tab data
      renderAssessment(result.assessment);

      // Re-fetch incidents table so any triggered incident appears
      fetchData();

      // Show New Analysis button
      elements.analyzeBtn.style.display = "none";
      elements.newAnalysisBtn.style.display = "inline-flex";

    } catch (err) {
      elements.analysisStatusPill.className = "status-pill status-failed";
      elements.analysisStatusPill.textContent = "FAILED";
      elements.processingTitle.textContent = "Analysis Failed";
      elements.processingNotice.className = "processing-notice error";
      elements.processingNotice.textContent = err.message;
      elements.processingNotice.style.display = "block";
      elements.analyzeBtn.disabled = false;
      elements.analyzeBtn.textContent = "▶ ANALYZE MEDIA";
      elements.newAnalysisBtn.style.display = "inline-flex";
    }
  } else {
    // Video Analysis (Asynchronous)
    try {
      const res = await fetch(`${CONFIG.apiBase}/api/v1/analyze/video`, {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(errJson.detail || "Video upload failed");
      }

      const submitData = await res.json();
      state.activeJobId = submitData.job_id;
      state.isSingleFrame = false;

      // Start polling for video progress
      startJobPolling(submitData.job_id);

    } catch (err) {
      elements.analysisStatusPill.className = "status-pill status-failed";
      elements.analysisStatusPill.textContent = "FAILED";
      elements.processingTitle.textContent = "Analysis Failed";
      elements.processingNotice.className = "processing-notice error";
      elements.processingNotice.textContent = err.message;
      elements.processingNotice.style.display = "block";
      elements.analyzeBtn.disabled = false;
      elements.analyzeBtn.textContent = "▶ ANALYZE MEDIA";
      elements.newAnalysisBtn.style.display = "inline-flex";
    }
  }
}

function startJobPolling(jobId) {
  stopJobPolling();
  state.jobPollTimer = setInterval(() => pollJobStatus(jobId), 1000);
}

function stopJobPolling() {
  if (state.jobPollTimer) {
    clearInterval(state.jobPollTimer);
    state.jobPollTimer = null;
  }
}

async function pollJobStatus(jobId) {
  try {
    const res = await fetch(`${CONFIG.apiBase}/api/v1/analyze/status/${jobId}`);
    if (!res.ok) return;
    const st = await res.json();

    // Update Telemetry
    const pct = Math.min(100, Math.max(0, st.progress_pct || 0)).toFixed(0);
    elements.processingPct.textContent = `${pct}%`;
    elements.analysisProgressBar.style.width = `${pct}%`;

    elements.telFrames.textContent = `${st.current_frame} / ${st.total_frames || '?'}`;
    elements.telFps.textContent = `${(st.processing_fps || 0).toFixed(1)} FPS`;
    elements.telRisk.textContent = st.current_risk_level || "INFO";
    elements.telTracks.textContent = st.active_tracks || 0;
    elements.telIncidents.textContent = st.incidents_count || 0;

    // Live frame preview update
    if (st.latest_frame_url) {
      elements.canvas.style.display = "none";
      elements.viewportVideo.style.display = "none";
      elements.viewportImage.src = st.latest_frame_url + "?t=" + Date.now();
      elements.viewportImage.style.display = "block";
    }

    // Refresh current assessment and incidents
    fetchData();

    if (st.status === "COMPLETED") {
      stopJobPolling();
      handleVideoJobCompleted(jobId);
    } else if (st.status === "FAILED") {
      stopJobPolling();
      elements.analysisStatusPill.className = "status-pill status-failed";
      elements.analysisStatusPill.textContent = "FAILED";
      elements.processingTitle.textContent = "Analysis Failed";
      elements.processingNotice.className = "processing-notice error";
      elements.processingNotice.textContent = st.error_message || "Video processing encountered an error.";
      elements.processingNotice.style.display = "block";
      elements.analyzeBtn.style.display = "none";
      elements.newAnalysisBtn.style.display = "inline-flex";
    }
  } catch (err) {
    console.warn("Job polling error:", err);
  }
}

async function handleVideoJobCompleted(jobId) {
  try {
    const res = await fetch(`${CONFIG.apiBase}/api/v1/analyze/result/${jobId}`);
    if (!res.ok) throw new Error("Could not retrieve video analysis results");
    const result = await res.json();

    elements.analysisStatusPill.className = "status-pill status-completed";
    elements.analysisStatusPill.textContent = "COMPLETED";
    elements.processingTitle.textContent = "Video Stream Analysis Complete";
    elements.processingPct.textContent = "100%";
    elements.analysisProgressBar.style.width = "100%";

    // Display annotated video in viewport
    if (result.annotated_video_url) {
      elements.viewportImage.style.display = "none";
      elements.canvas.style.display = "none";
      elements.viewportVideo.src = result.annotated_video_url;
      elements.viewportVideo.style.display = "block";
      elements.viewportVideo.play().catch(() => {});
    }

    // Populate summary card
    elements.sumTotalFrames.textContent = result.total_frames;
    elements.sumProcessedFrames.textContent = result.processed_frames;
    elements.sumAvgFps.textContent = (result.average_fps || 0).toFixed(1) + " FPS";
    elements.sumAvgLatency.textContent = (result.average_latency_ms || 0).toFixed(1) + " ms";
    elements.sumIncidents.textContent = result.total_incidents;
    elements.sumRisk.textContent = result.highest_risk_tier;
    elements.viewportCompletedSummary.style.display = "flex";

    elements.viewportStateBadge.textContent = "[ANALYSIS COMPLETE]";
    elements.analyzeBtn.style.display = "none";
    elements.newAnalysisBtn.style.display = "inline-flex";

    fetchData();
  } catch (err) {
    console.error("Error retrieving completed video results:", err);
  }
}

function resetAnalysisState() {
  stopJobPolling();
  state.activeJobId = null;
  state.isSingleFrame = false;
  clearSelectedFile();

  // Reset viewport
  elements.viewportImage.style.display = "none";
  elements.viewportVideo.style.display = "none";
  elements.viewportVideo.pause();
  elements.viewportVideo.removeAttribute("src");
  elements.viewportVideo.load();
  elements.viewportCompletedSummary.style.display = "none";
  elements.canvas.style.display = "block";
  initCanvas();

  // Reset processing card
  elements.processingCard.style.display = "none";
  elements.processingNotice.style.display = "none";
  elements.analysisProgressBar.style.width = "0%";
  elements.analyzeBtn.style.display = "inline-flex";
  elements.analyzeBtn.disabled = true;
  elements.analyzeBtn.textContent = "▶ ANALYZE MEDIA";
  elements.newAnalysisBtn.style.display = "none";
  elements.viewportStateBadge.textContent = "[LIVE TELEMETRY]";
}


function initCanvas() {
  const ctx = elements.canvas.getContext("2d");
  ctx.fillStyle = "#0c1017";
  ctx.fillRect(0, 0, elements.canvas.width, elements.canvas.height);

  ctx.strokeStyle = "#1e293b";
  ctx.lineWidth = 1;
  for (let x = 0; x < elements.canvas.width; x += 40) {
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, elements.canvas.height);
    ctx.stroke();
  }
  for (let y = 0; y < elements.canvas.height; y += 40) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(elements.canvas.width, y);
    ctx.stroke();
  }

  ctx.fillStyle = "#475569";
  ctx.font = "14px monospace";
  ctx.textAlign = "center";
  ctx.fillText("INTELLIWATCH SCENE FEED READY — WAITING FOR FRAME TELEMETRY", elements.canvas.width / 2, elements.canvas.height / 2);
}

// -------------------------------------------------------------
// POLLING & DATA FETCHING
// -------------------------------------------------------------
function startPolling() {
  stopPolling();
  state.pollTimer = setInterval(fetchData, CONFIG.pollIntervalMs);
}

function stopPolling() {
  if (state.pollTimer) {
    clearInterval(state.pollTimer);
    state.pollTimer = null;
  }
}

function buildIncidentsUrl() {
  let url = `${CONFIG.apiBase}/api/v1/incidents?limit=50`;
  if (state.incidentFilters.risk_level) {
    url += `&risk_level=${encodeURIComponent(state.incidentFilters.risk_level)}`;
  }
  if (state.incidentFilters.event_type) {
    url += `&event_type=${encodeURIComponent(state.incidentFilters.event_type)}`;
  }
  if (state.incidentFilters.track_id) {
    url += `&track_id=${encodeURIComponent(state.incidentFilters.track_id)}`;
  }
  if (state.incidentFilters.zone) {
    url += `&zone=${encodeURIComponent(state.incidentFilters.zone)}`;
  }
  return url;
}

async function fetchFilteredIncidents() {
  try {
    const url = buildIncidentsUrl();
    const res = await fetch(url);
    if (res.ok) {
      state.incidents = await res.json();
      renderIncidents(state.incidents);
    }
  } catch (err) {
    console.warn("Could not fetch filtered incidents:", err);
  }
}

async function fetchData() {
  try {
    const incidentsUrl = buildIncidentsUrl();

    const [assessmentRes, incidentsRes, statusRes, temporalRes, zonesRes] = await Promise.all([
      fetch(`${CONFIG.apiBase}/api/v1/assessment/current`).catch(() => null),
      fetch(incidentsUrl).catch(() => null),
      fetch(`${CONFIG.apiBase}/api/v1/status`).catch(() => null),
      fetch(`${CONFIG.apiBase}/api/v1/temporal/timeline?n=30`).catch(() => null),
      fetch(`${CONFIG.apiBase}/api/v1/zones`).catch(() => null),
    ]);

    if (assessmentRes && assessmentRes.ok) {
      state.currentAssessment = await assessmentRes.json();
      renderAssessment(state.currentAssessment);
      elements.statusDot.className = "status-dot";
    }

    if (incidentsRes && incidentsRes.ok) {
      state.incidents = await incidentsRes.json();
      renderIncidents(state.incidents);
    }

    if (statusRes && statusRes.ok) {
      state.systemStatus = await statusRes.json();
      renderStatus(state.systemStatus);
    }

    if (temporalRes && temporalRes.ok) {
      const timeline = await temporalRes.json();
      renderTemporalTimeline(timeline);
    }

    if (zonesRes && zonesRes.ok) {
      state.zones = await zonesRes.json();
      renderConfiguredZonesList();
      renderZonesOverlay();
    }
  } catch (err) {
    console.warn("Polling warning:", err);
    elements.statusDot.className = "status-dot danger";
  }
}

// -------------------------------------------------------------
// RENDERING FUNCTIONS
// -------------------------------------------------------------
function renderStatus(status) {
  if (!status) return;
  if (elements.cpuBadge) elements.cpuBadge.textContent = status.is_cpu_mode ? "CPU Mode" : "GPU (CUDA)";
  if (elements.fpsBadge) elements.fpsBadge.textContent = `${status.processing_fps.toFixed(1)} FPS`;
  if (elements.latencyBadge) elements.latencyBadge.textContent = `${status.avg_latency_ms.toFixed(1)} ms`;
  if (elements.tracksBadge) elements.tracksBadge.textContent = `Tracks: ${status.active_tracks_count}`;
  if (elements.incidentsBadge) elements.incidentsBadge.textContent = `Incidents: ${status.total_recorded_incidents}`;
}

function renderAssessment(data) {
  if (!data) return;

  renderCanvas(data);
  renderSceneUnderstanding(data);
  renderRiskAndEvents(data);
  renderPPECompliance(data);
  renderBehaviorAndDepth(data);
  // Step 15: render temporal intelligence from inline assessment data
  if (data.entity_profiles || data.temporal_events) {
    renderTemporalIntelligence(data.entity_profiles || [], data.temporal_events || []);
  }
  // Step 16: sync safety zones overlay with frame resolution
  renderZonesOverlay();
}

function renderCanvas(data) {
  const ctx = elements.canvas.getContext("2d");
  const cw = elements.canvas.width;
  const ch = elements.canvas.height;
  const sw = data.frame_width || 1280;
  const sh = data.frame_height || 720;
  const sx = cw / sw;
  const sy = ch / sh;

  // Clear dark background with faint grid
  ctx.fillStyle = "#0a0e17";
  ctx.fillRect(0, 0, cw, ch);

  ctx.strokeStyle = "rgba(255, 255, 255, 0.04)";
  ctx.lineWidth = 1;
  for (let x = 0; x < cw; x += 40) {
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, ch);
    ctx.stroke();
  }
  for (let y = 0; y < ch; y += 40) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(cw, y);
    ctx.stroke();
  }

  // 1. Draw Zones
  if (data.zone_memberships && data.zone_memberships.length > 0) {
    const zoneMap = {};
    data.zone_memberships.forEach((zm) => {
      zoneMap[zm.zone_id] = zm;
    });
  }

  // 2. Draw Tracked Objects & Trajectories
  const tracks = data.tracks || [];
  tracks.forEach((trk) => {
    const bbox = trk.bbox;
    if (!bbox) return;

    const bx = bbox.x1 * sx;
    const by = bbox.y1 * sy;
    const bw = (bbox.x2 - bbox.x1) * sx;
    const bh = (bbox.y2 - bbox.y1) * sy;

    // Track color (deterministic based on class category)
    const cgroup = (trk.class_group || "").toUpperCase();
    const cname = (trk.class_name || "").toLowerCase();
    let boxColor = "#94a3b8"; // default slate
    if (cgroup === "PERSON" || cname === "person" || cname === "worker") {
      boxColor = "#3b82f6"; // blue
    } else if (cgroup === "VEHICLE" || ["forklift", "industrial vehicle", "forklift truck", "truck", "car", "vehicle", "agv", "van"].includes(cname)) {
      boxColor = "#f59e0b"; // amber
    } else if (cgroup === "MACHINE" || ["machine", "machinery", "robotic arm", "conveyor", "crane", "press"].includes(cname)) {
      boxColor = "#8b5cf6"; // purple
    } else if (cgroup === "INFRASTRUCTURE" || ["pallet", "safety barrier", "electrical cabinet", "guardrail"].includes(cname)) {
      boxColor = "#06b6d4"; // cyan
    } else if (cgroup === "PPE") {
      boxColor = "#10b981"; // emerald
    }

    // Trajectory trail
    if (trk.trajectory && trk.trajectory.length > 1) {
      ctx.beginPath();
      ctx.strokeStyle = boxColor;
      ctx.lineWidth = 1.5;
      trk.trajectory.forEach((pt, i) => {
        const px = pt.cx * sx;
        const py = pt.cy * sy;
        if (i === 0) ctx.moveTo(px, py);
        else ctx.lineTo(px, py);
      });
      ctx.stroke();
    }

    // Bounding Box
    ctx.strokeStyle = boxColor;
    ctx.lineWidth = 2;
    ctx.strokeRect(bx, by, bw, bh);

    // Label badge
    const label = `#${trk.track_id} ${trk.class_name || "obj"} ${(trk.confidence ? trk.confidence.toFixed(2) : "")}`;
    ctx.font = "10px monospace";
    const textWidth = ctx.measureText(label).width;

    ctx.fillStyle = boxColor;
    ctx.fillRect(bx, Math.max(0, by - 16), textWidth + 8, 16);
    ctx.fillStyle = "#ffffff";
    ctx.fillText(label, bx + 4, Math.max(12, by - 4));
  });

  // 3. Draw Scene Graph Relationships (Connecting Lines)
  if (data.scene && data.scene.relationships) {
    const nodeMap = {};
    (data.scene.nodes || []).forEach((n) => {
      nodeMap[n.node_id] = n;
    });

    data.scene.relationships.forEach((rel) => {
      const src = nodeMap[rel.source_node_id];
      const tgt = nodeMap[rel.target_node_id];
      if (src && tgt && src.centroid && tgt.centroid) {
        const x1 = src.centroid[0] * sx;
        const y1 = src.centroid[1] * sy;
        const x2 = tgt.centroid[0] * sx;
        const y2 = tgt.centroid[1] * sy;

        const relType = rel.relation_type;
        const isApproaching = relType === "APPROACHING";
        ctx.strokeStyle = isApproaching ? "#ef4444" : "#f59e0b";
        ctx.lineWidth = isApproaching ? 2 : 1;
        ctx.setLineDash([4, 4]);

        ctx.beginPath();
        ctx.moveTo(x1, y1);
        ctx.lineTo(x2, y2);
        ctx.stroke();
        ctx.setLineDash([]);

        // Midpoint badge
        const mx = (x1 + x2) / 2;
        const my = (y1 + y2) / 2;
        ctx.fillStyle = "rgba(10, 15, 25, 0.85)";
        ctx.fillRect(mx - 30, my - 8, 60, 16);
        ctx.strokeStyle = isApproaching ? "#ef4444" : "#f59e0b";
        ctx.strokeRect(mx - 30, my - 8, 60, 16);
        ctx.fillStyle = "#ffffff";
        ctx.font = "8px monospace";
        ctx.textAlign = "center";
        ctx.fillText(relType, mx, my + 3);
        ctx.textAlign = "start";
      }
    });
  }

  // 4. In-viewport Telemetry Banner
  ctx.fillStyle = "rgba(10, 15, 25, 0.85)";
  ctx.fillRect(10, 10, 260, 48);
  ctx.strokeStyle = "rgba(59, 130, 246, 0.4)";
  ctx.strokeRect(10, 10, 260, 48);

  ctx.fillStyle = "#94a3b8";
  ctx.font = "10px monospace";
  ctx.fillText(`FRAME: ${data.frame_id || 0} | TIME: ${(data.timestamp || 0).toFixed(2)}s`, 18, 26);
  ctx.fillText(`ACTIVE TRACKS: ${data.total_active_tracks || 0} | LATENCY: ${(data.processing_time_ms || 0).toFixed(1)}ms`, 18, 44);
}

function renderSceneUnderstanding(data) {
  if (!elements.sceneRelationshipsList) return;

  const scene = data.scene;
  if (!scene || !scene.relationships || scene.relationships.length === 0) {
    elements.sceneRelationshipsList.innerHTML = `
      <div style="color: var(--text-muted); font-size: 11px; padding: 12px; text-align: center;">
        No active scene relationships detected in current frame.
      </div>`;
  } else {
    elements.sceneRelationshipsList.innerHTML = scene.relationships
      .map((r) => {
        const srcLabel = r.source_node_id.replace("_", " #");
        const tgtLabel = r.target_node_id.replace("_", " #");
        const relType = r.relation_type;
        return `
          <div class="relationship-card">
            <span class="rel-node">${srcLabel}</span>
            <span class="rel-arrow">➔</span>
            <span class="rel-predicate">${relType}</span>
            <span class="rel-arrow">➔</span>
            <span class="rel-node">${tgtLabel}</span>
          </div>`;
      })
      .join("");
  }

  if (elements.entitySummaryList) {
    const s = (scene && scene.summary) ? scene.summary : {};
    const detections = data.detections || [];
    const sourceBreakdown = {};
    detections.forEach(d => {
      const src = d.source_model || "yolo11n";
      sourceBreakdown[src] = (sourceBreakdown[src] || 0) + 1;
    });

    elements.entitySummaryList.innerHTML = `
      <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; font-size: 11px;">
        <div style="background: rgba(0,0,0,0.3); padding: 6px; border-radius: 4px; text-align: center;">
          <div style="color: var(--text-muted); font-size: 8px;">WORKERS</div>
          <div style="font-weight: 700; color: #3b82f6;">${s.workers_count || 0}</div>
        </div>
        <div style="background: rgba(0,0,0,0.3); padding: 6px; border-radius: 4px; text-align: center;">
          <div style="color: var(--text-muted); font-size: 8px;">VEHICLES</div>
          <div style="font-weight: 700; color: #f59e0b;">${s.vehicles_count || 0}</div>
        </div>
        <div style="background: rgba(0,0,0,0.3); padding: 6px; border-radius: 4px; text-align: center;">
          <div style="color: var(--text-muted); font-size: 8px;">MACHINERY</div>
          <div style="font-weight: 700; color: #8b5cf6;">${s.machines_count || 0}</div>
        </div>
        <div style="background: rgba(0,0,0,0.3); padding: 6px; border-radius: 4px; text-align: center;">
          <div style="color: var(--text-muted); font-size: 8px;">DETECTIONS</div>
          <div style="font-weight: 700; color: #06b6d4;">${detections.length}</div>
        </div>
      </div>
      <div style="display: flex; gap: 6px; margin-top: 6px; font-size: 9px; flex-wrap: wrap;">
        <span style="background: rgba(59,130,246,0.15); border: 1px solid rgba(59,130,246,0.4); padding: 2px 6px; border-radius: 3px; color: #93c5fd;">
          YOLO11n: ${sourceBreakdown["yolo11n"] || 0}
        </span>
        <span style="background: rgba(245,158,11,0.15); border: 1px solid rgba(245,158,11,0.4); padding: 2px 6px; border-radius: 3px; color: #fcd34d;">
          YOLO-World: ${sourceBreakdown["yolo_world"] || 0}
        </span>
        <span style="background: rgba(16,185,129,0.15); border: 1px solid rgba(16,185,129,0.4); padding: 2px 6px; border-radius: 3px; color: #6ee7b7;">
          SafetyVision: ${sourceBreakdown["safetyvision_ppe"] || 0}
        </span>
      </div>`;
  }
}

function renderActiveSafetyEvent(data) {
  if (!elements.safetyEventContainer) return;

  const events = data.active_events || [];
  const compoundEvent = events.find(
    (e) => (e.metadata && e.metadata.audit_5w) || e.risk_level === "CRITICAL" || e.risk_level === "HIGH"
  );

  if (!compoundEvent && events.length === 0) {
    elements.safetyEventContainer.innerHTML = "";
    return;
  }

  const ev = compoundEvent || events[0];
  const riskTier = ev.risk_level || "MEDIUM";
  const meta = ev.metadata || {};
  const audit = meta.audit_5w || null;

  // Spatial Proximity badge
  let spatialState = meta.spatial_state || "UNKNOWN";
  if (spatialState === "UNKNOWN" && data.scene && data.scene.relationships) {
    const rel = data.scene.relationships.find((r) => r.proximity_state);
    if (rel) spatialState = rel.proximity_state;
  }

  // Zone info
  let zoneName = meta.zone_id || "Facility Floor";
  if (data.zone_memberships && data.zone_memberships.length > 0) {
    const activeZone = data.zone_memberships.find((z) => z.is_inside);
    if (activeZone) zoneName = activeZone.zone_id || zoneName;
  }

  // Involved relationship
  let relDisplay = "Personnel & Asset Interaction";
  if (data.scene && data.scene.relationships && data.scene.relationships.length > 0) {
    const firstRel = data.scene.relationships[0];
    relDisplay = `${firstRel.source_node_id.replace("_", " #")} ➔ [${firstRel.relation_type}] ➔ ${firstRel.target_node_id.replace("_", " #")}`;
  } else if (ev.involved_track_ids && ev.involved_track_ids.length >= 2) {
    relDisplay = `Worker #${ev.involved_track_ids[0]} ➔ [INTERACTION] ➔ Entity #${ev.involved_track_ids[1]}`;
  }

  // Contributing factors checklist
  const factors = ev.risk_factors || [];
  const factorTypes = factors.map((f) => (f.factor_type || "").toUpperCase());
  const hasProximity =
    factorTypes.some((t) => t.includes("PROXIMITY")) ||
    spatialState === "VERY_NEAR" ||
    spatialState === "NEAR";
  const hasApproaching = factorTypes.some((t) => t.includes("APPROACHING"));
  const hasZone =
    factorTypes.some((t) => t.includes("ZONE")) ||
    (data.zone_memberships && data.zone_memberships.some((z) => z.is_inside));
  const hasPpe =
    factorTypes.some((t) => t.includes("PPE")) ||
    (data.ppe_assessments && data.ppe_assessments.some((p) => !p.compliant));

  const whatText = audit ? audit.what : ev.explanation || ev.event_type;
  const whoText = audit ? audit.who : `Track #${(ev.involved_track_ids || []).join(", #")}`;
  const whereText = audit ? audit.where : zoneName;
  const whyText = audit ? audit.why : ev.deterministic_explanation || ev.explanation;

  elements.safetyEventContainer.innerHTML = `
    <div class="safety-event-card ${riskTier}">
      <div class="safety-event-header">
        <div class="safety-event-title">
          <span>⚡ INDUSTRIAL SAFETY EVENT</span>
          <span class="risk-badge badge-${riskTier}">${riskTier}</span>
        </div>
        <span class="spatial-badge spatial-badge-${spatialState}">${spatialState.replace(/_/g, " ")}</span>
      </div>

      <div class="safety-rel-flow">
        <span style="color: var(--text-muted); font-size: 10px;">RELATION:</span>
        <strong style="color: #93c5fd;">${relDisplay}</strong>
      </div>

      <div class="safety-factors-checklist">
        <div class="checklist-item ${hasProximity ? "active" : ""}">
          <span>${hasProximity ? "☑" : "☐"}</span> Proximity: ${spatialState.replace(/_/g, " ")}
        </div>
        <div class="checklist-item ${hasApproaching ? "active" : ""}">
          <span>${hasApproaching ? "☑" : "☐"}</span> Approaching Kinematics
        </div>
        <div class="checklist-item ${hasZone ? "active" : ""}">
          <span>${hasZone ? "☑" : "☐"}</span> Restricted Area (${zoneName})
        </div>
        <div class="checklist-item ${hasPpe ? "active" : ""}">
          <span>${hasPpe ? "☑" : "☐"}</span> PPE Non-Compliance
        </div>
      </div>

      <div class="audit-5w-grid">
        <div class="audit-field">
          <span class="audit-label">WHAT</span>
          <span class="audit-val">${whatText}</span>
        </div>
        <div class="audit-field">
          <span class="audit-label">WHO</span>
          <span class="audit-val">${whoText}</span>
        </div>
        <div class="audit-field">
          <span class="audit-label">WHERE</span>
          <span class="audit-val">${whereText}</span>
        </div>
        <div class="audit-field">
          <span class="audit-label">WHY</span>
          <span class="audit-val">${whyText}</span>
        </div>
      </div>
    </div>
  `;
}

function renderRiskAndEvents(data) {
  renderActiveSafetyEvent(data);
  if (!elements.riskContainer) return;

  const events = data.active_events || [];
  const riskTier = data.highest_risk_level || "INFO";
  const riskScore = data.highest_risk_score || 0.0;

  let riskHtml = `
    <div class="risk-card ${riskTier}">
      <div style="display: flex; justify-content: space-between; align-items: center;">
        <span class="risk-badge badge-${riskTier}">${riskTier} RISK TIER</span>
        <span style="font-family: var(--font-mono); font-weight: 700; font-size: 12px;">SCORE: ${riskScore.toFixed(1)}</span>
      </div>
  `;

  if (events.length === 0) {
    riskHtml += `
      <div style="color: var(--text-muted); font-size: 11px; padding: 6px 0;">
        Normal operational state. No active safety events confirmed.
      </div>
    `;
  } else {
    riskHtml += `<div style="display: flex; flex-direction: column; gap: 8px; margin-top: 4px;">`;
    events.forEach((ev) => {
      const factorsHtml = (ev.risk_factors || [])
        .map((f) => `<div class="factor-item">${f.explanation || f.factor_type}</div>`)
        .join("");

      riskHtml += `
        <div style="border-top: 1px solid var(--border-color); padding-top: 6px;">
          <div style="font-weight: 700; color: var(--text-primary); font-size: 11px;">
            ${ev.event_type.replace(/_/g, " ")}
          </div>
          <div class="risk-explanation">"${ev.explanation}"</div>
          ${factorsHtml ? `<div class="factors-list" style="margin-top: 4px;">${factorsHtml}</div>` : ""}
        </div>
      `;
    });
    riskHtml += `</div>`;
  }
  riskHtml += `</div>`;
  elements.riskContainer.innerHTML = riskHtml;

  // Early-Warning Indicators
  if (elements.warningContainer) {
    if (state.isSingleFrame) {
      elements.warningContainer.innerHTML = `
        <div class="single-frame-notice">
          <strong>Single-Frame Analysis:</strong> Trajectory forecasting and predictive safety escalation require multi-frame temporal video observations.
        </div>`;
    } else {
      const warnings = data.active_early_warnings || [];
      if (warnings.length === 0) {
        elements.warningContainer.innerHTML = `
          <div style="color: var(--text-muted); font-size: 11px; padding: 8px; text-align: center;">
            No predictive early warnings currently active.
          </div>`;
      } else {
        elements.warningContainer.innerHTML = warnings
          .map((w) => `
            <div style="background: rgba(249, 115, 22, 0.08); border: 1px solid rgba(249, 115, 22, 0.4); border-left: 3px solid #f97316; padding: 6px 10px; border-radius: 4px;">
              <div style="display: flex; justify-content: space-between; font-size: 10px; font-weight: 700; color: #f97316;">
                <span>⚠ ${w.indicator_type.replace(/_/g, " ")}</span>
                <span>[${w.severity}]</span>
              </div>
              <div style="font-size: 10px; color: var(--text-secondary); margin-top: 2px;">
                ${w.explanation}
              </div>
            </div>
          `)
          .join("");
      }
    }
  }
}

function renderPPECompliance(data) {
  if (!elements.ppeContainer) return;

  const inventories = data.worker_inventories || [];
  if (inventories.length === 0) {
    elements.ppeContainer.innerHTML = `
      <div style="color: var(--text-muted); font-size: 11px; padding: 12px; text-align: center;">
        No active workers detected in scene.
      </div>`;
    return;
  }

  elements.ppeContainer.innerHTML = inventories
    .map((inv) => {
      const statusClass = inv.compliance_status || "UNKNOWN";
      const ppeMap = inv.ppe_status || {};
      const items = ["Hardhat", "Safety Vest", "Gloves", "Goggles"];

      const slotsHtml = items
        .map((item) => {
          const state = ppeMap[item] || "UNKNOWN";
          return `
            <div class="ppe-slot ${state}">
              <span style="font-weight: 600;">${item}</span>
              <span>${state}</span>
            </div>`;
        })
        .join("");

      return `
        <div class="worker-ppe-card">
          <div class="worker-header">
            <span>Worker #${inv.track_id}</span>
            <span class="risk-badge badge-${statusClass === "COMPLIANT" ? "LOW" : statusClass === "NON_COMPLIANT" ? "CRITICAL" : "INFO"}">
              ${statusClass}
            </span>
          </div>
          <div class="ppe-grid">${slotsHtml}</div>
          <div style="font-size: 10px; color: var(--text-muted); font-style: italic;">
            ${inv.explanation || ""}
          </div>
        </div>`;
    })
    .join("");
}

function renderBehaviorAndDepth(data) {
  if (elements.behaviorContainer) {
    if (state.isSingleFrame) {
      elements.behaviorContainer.innerHTML = `
        <div class="single-frame-notice">
          <strong>Single-Frame Analysis:</strong> Velocity, trajectories, and temporal behavior are not available for single-frame images. Movement is not fabricated.
        </div>`;
    } else {
      const behaviors = data.behavior_states || [];
      if (behaviors.length === 0) {
        elements.behaviorContainer.innerHTML = `
          <div style="color: var(--text-muted); font-size: 11px; padding: 8px; text-align: center;">
            No behavior observations recorded.
          </div>`;
      } else {
        elements.behaviorContainer.innerHTML = behaviors
          .map((b) => `
            <div style="background: rgba(255,255,255,0.03); border: 1px solid var(--border-color); padding: 6px 10px; border-radius: 4px; display: flex; justify-content: space-between; font-size: 11px;">
              <span>Track #${b.track_id}</span>
              <span style="font-family: var(--font-mono); font-weight: 600; color: ${b.primary_behavior === "RAPID_MOVEMENT" ? "#ef4444" : "#60a5fa"};">
                ${b.primary_behavior}
              </span>
              <span style="color: var(--text-muted); font-size: 10px;">
                ${(b.image_speed_px_per_s || 0).toFixed(0)} px/s
              </span>
            </div>
          `)
          .join("");
      }
    }
  }

  if (elements.depthContainer) {
    elements.depthContainer.innerHTML = `
      <div style="background: rgba(0,0,0,0.3); border: 1px solid var(--border-color); border-radius: 4px; padding: 8px; font-size: 11px;">
        <div style="color: #94a3b8; font-weight: 600; margin-bottom: 4px;">Perception: Monocular Relative Depth</div>
        <div style="font-size: 10px; color: var(--text-muted); line-height: 1.4;">
          Depth values operate on inverse relative disparity. Higher values represent closer proximity to camera.
          <span style="color: #fbbf24;">(Non-metric: calibrated physical meters not claimed)</span>.
        </div>
      </div>`;
  }
}

function renderIncidents(incidents) {
  if (!elements.incidentTableBody) return;

  if (!incidents || incidents.length === 0) {
    elements.incidentTableBody.innerHTML = `
      <tr>
        <td colspan="6" style="text-align: center; color: var(--text-muted); padding: 16px;">
          No recorded safety incidents.
        </td>
      </tr>`;
    return;
  }

  elements.incidentTableBody.innerHTML = incidents
    .map((inc) => {
      const riskClass = inc.risk_level || "INFO";
      const tracksStr = (inc.involved_track_ids || []).map((t) => `#${t}`).join(", ") || "N/A";
      const timeStr = `${inc.timestamp.toFixed(2)}s (Frame ${inc.frame_id})`;

      return `
        <tr>
          <td style="font-family: var(--font-mono); font-size: 10px;">${timeStr}</td>
          <td><span class="risk-badge badge-${riskClass}">${riskClass}</span></td>
          <td style="font-weight: 600;">${inc.event_type.replace(/_/g, " ")}</td>
          <td>${tracksStr}</td>
          <td style="max-width: 280px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${inc.explanation}">
            ${inc.explanation}
          </td>
          <td>
            <button class="btn" style="padding: 2px 8px; font-size: 10px;" onclick="openIncidentModal('${inc.incident_id}')">
              Evidence
            </button>
          </td>
        </tr>`;
    })
    .join("");
}

// -------------------------------------------------------------
// STEP 17: EXPLAINABILITY, EVIDENCE & ANALYTICS
// -------------------------------------------------------------
function escapeHtml(str) {
  if (str == null) return "";
  return String(str)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

window.openIncidentModal = async function (incidentId) {
  try {
    const res = await fetch(`${CONFIG.apiBase}/api/v1/incidents/${incidentId}/explanation`);
    if (!res.ok) throw new Error("Could not retrieve incident explainability package");
    const expl = await res.json();
    state.activeExplanation = expl;
    state.selectedIncident = expl.incident;

    const inc = expl.incident;
    if (elements.modalTitle) {
      elements.modalTitle.textContent = `INCIDENT AUDIT: ${inc.incident_id} [${inc.risk_level} - ${inc.event_type.replace(/_/g, " ")}]`;
    }

    // Evidence Snapshot display
    if (expl.has_snapshot) {
      elements.modalEvidenceImage.src = `${CONFIG.apiBase}/api/v1/incidents/${incidentId}/evidence?t=${Date.now()}`;
      elements.modalEvidenceImage.style.display = "block";
      elements.noEvidenceNotice.style.display = "none";
      if (elements.modalEvidenceBadge) {
        elements.modalEvidenceBadge.innerHTML = '<span class="badge" style="background:#065f46;color:#34d399;font-weight:600;">Snapshot Available</span>';
      }
    } else {
      elements.modalEvidenceImage.style.display = "none";
      elements.noEvidenceNotice.style.display = "block";
      elements.noEvidenceNotice.textContent = "Metadata-Only Record: No image snapshot was captured for this event.";
      if (elements.modalEvidenceBadge) {
        elements.modalEvidenceBadge.innerHTML = '<span class="badge" style="background:#78350f;color:#fcd34d;font-weight:600;">Metadata Only</span>';
      }
    }

    // Five-W Structured Causation
    if (elements.fwWho) elements.fwWho.textContent = expl.five_w.who || "Unassigned Monitored Actor";
    if (elements.fwWhat) elements.fwWhat.textContent = expl.five_w.what || "Safety Event";
    if (elements.fwWhere) elements.fwWhere.textContent = expl.five_w.where || "Operational Monitored Zone";
    if (elements.fwWhen) elements.fwWhen.textContent = expl.five_w.when || "Recorded Timestamp";
    if (elements.fwWhyList) {
      const whyItems = expl.five_w.why || [];
      elements.fwWhyList.innerHTML = whyItems.length > 0
        ? whyItems.map((w) => `<li>${escapeHtml(w)}</li>`).join("")
        : "<li>No causal factors logged.</li>";
    }

    // Risk Score Breakdown Table
    if (elements.riskBreakdownBody) {
      let rows = "";
      (expl.risk_breakdown.base_contributions || []).forEach((item) => {
        rows += `
          <tr>
            <td style="font-weight:600; color:#cbd5e1;">${escapeHtml(item.factor_type.replace(/_/g, " "))}</td>
            <td style="font-family:var(--font-mono); color:#38bdf8;">+${item.score_contribution.toFixed(1)}</td>
            <td style="color:var(--text-secondary); font-size:10px;">${escapeHtml(item.explanation)}</td>
          </tr>`;
      });
      (expl.risk_breakdown.escalation_penalties || []).forEach((item) => {
        rows += `
          <tr style="background: rgba(239, 68, 68, 0.08);">
            <td style="font-weight:600; color:#f87171;">${escapeHtml(item.factor_type.replace(/_/g, " "))}</td>
            <td style="font-family:var(--font-mono); color:#f87171;">+${item.score_contribution.toFixed(1)}</td>
            <td style="color:#fca5a5; font-size:10px;">${escapeHtml(item.explanation)}</td>
          </tr>`;
      });
      if (!rows) {
        rows = `<tr><td colspan="3" style="text-align:center; color:var(--text-muted); padding:8px;">No risk factor breakdown available.</td></tr>`;
      }
      elements.riskBreakdownBody.innerHTML = rows;
    }

    if (elements.riskBreakdownFinal) {
      elements.riskBreakdownFinal.innerHTML = `
        <span>Final Calculated Risk: <strong style="color:#f87171;">${expl.risk_breakdown.final_calculated_score.toFixed(1)} / 100</strong></span>
        <span style="color:var(--text-muted); font-size:10px;">Classification Tier: <strong style="color:#38bdf8;">${inc.risk_level}</strong></span>
      `;
    }

    // Incident Timeline
    if (elements.modalIncidentTimeline) {
      const timelineEntries = expl.timeline || [];
      if (timelineEntries.length === 0) {
        elements.modalIncidentTimeline.innerHTML = '<div style="color:var(--text-muted); font-size:11px; padding:8px;">No temporal progression logged around this event window.</div>';
      } else {
        elements.modalIncidentTimeline.innerHTML = timelineEntries
          .map((entry) => {
            const phaseBadgeColor = entry.phase === "BEFORE" ? "#38bdf8" : entry.phase === "EVENT" ? "#ef4444" : "#a855f7";
            return `
              <div class="modal-timeline-item" style="border-left: 3px solid ${phaseBadgeColor}; margin-bottom: 8px; padding-left: 8px; background: rgba(255,255,255,0.02); border-radius: 2px;">
                <div style="display:flex; justify-content:space-between; align-items:center; font-size:10px; font-family:var(--font-mono); margin-bottom: 2px;">
                  <span style="font-weight:700; color:${phaseBadgeColor};">${entry.phase} [${entry.timestamp.toFixed(2)}s / Frame ${entry.frame_id}]</span>
                  <span style="color:var(--text-muted);">Risk: ${entry.risk_score.toFixed(1)}</span>
                </div>
                <div style="font-size:11px; color:#e2e8f0;">${escapeHtml(entry.summary)}</div>
              </div>`;
          })
          .join("");
      }
    }

    // Risk Trend Trajectory Sparkline
    renderRiskTrendChart(expl.risk_trend, inc.timestamp);

    // Scene Graph Relationships & Preceding Early Warnings
    if (elements.modalSceneAndWarnings) {
      const rels = inc.scene_relationships || [];
      const warnings = inc.early_warnings || [];
      let html = "";
      if (rels.length > 0) {
        html += '<div style="margin-bottom:8px;"><strong style="color:#94a3b8; font-size:10px; text-transform:uppercase;">Scene Spatial Relationships:</strong>';
        html += rels
          .map(
            (r) =>
              `<div style="font-size:11px; color:#cbd5e1; margin-top:2px;">• Track #${r.subject_track_id} ${escapeHtml(r.predicate)} Track #${r.object_track_id} (${escapeHtml(r.spatial_relation || "")}, distance: ${(r.distance_px || 0).toFixed(0)}px)</div>`
          )
          .join("");
        html += "</div>";
      }
      if (warnings.length > 0) {
        html += '<div><strong style="color:#f59e0b; font-size:10px; text-transform:uppercase;">Preceding Trajectory Warnings:</strong>';
        html += warnings
          .map(
            (w) =>
              `<div style="font-size:11px; color:#fde68a; margin-top:2px;">⚠ [${escapeHtml(w.indicator_type || "")}] ${escapeHtml(w.explanation || "")} (Horizon: ${(w.predicted_time_horizon_s || 0).toFixed(1)}s)</div>`
          )
          .join("");
        html += "</div>";
      }
      if (!html) {
        html = '<div style="color:var(--text-muted); font-size:11px;">No scene spatial relations or early-warning indicators recorded.</div>';
      }
      elements.modalSceneAndWarnings.innerHTML = html;
    }

    elements.evidenceModal.classList.add("open");
  } catch (err) {
    alert(`Could not load incident explanation: ${err.message}`);
  }
};

function closeModal() {
  if (elements.evidenceModal) {
    elements.evidenceModal.classList.remove("open");
  }
}

async function downloadEvidencePackage() {
  if (!state.selectedIncident) {
    alert("No incident selected for evidence package download.");
    return;
  }
  const incidentId = state.selectedIncident.incident_id;
  try {
    const res = await fetch(`${CONFIG.apiBase}/api/v1/incidents/${incidentId}/package`);
    if (!res.ok) throw new Error("Failed to export evidence package");
    const data = await res.json();
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `incident_${incidentId}_package.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  } catch (err) {
    alert(`Could not download evidence package: ${err.message}`);
  }
}

function renderRiskTrendChart(points, eventTimestamp) {
  const canvas = elements.modalRiskTrendCanvas;
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const w = canvas.width;
  const h = canvas.height;

  ctx.clearRect(0, 0, w, h);

  if (!points || points.length < 2) {
    if (elements.riskTrendStatus) elements.riskTrendStatus.textContent = "Insufficient Data";
    if (elements.riskTrendNotice) {
      elements.riskTrendNotice.textContent = "Insufficient temporal data for trend trajectory (< 2 data points).";
    }
    ctx.fillStyle = "rgba(148, 163, 184, 0.4)";
    ctx.font = "11px Inter, sans-serif";
    ctx.textAlign = "center";
    ctx.fillText("Insufficient temporal points (< 2) for trajectory curve", w / 2, h / 2);
    return;
  }

  const tVals = points.map((p) => p.timestamp);
  const sVals = points.map((p) => p.risk_score);
  const minT = Math.min(...tVals);
  const maxT = Math.max(...tVals);
  const maxS = Math.max(100, ...sVals);
  const minS = 0;

  const tSpan = maxT - minT || 1;
  const sSpan = maxS - minS || 1;

  // Background and Grid
  ctx.fillStyle = "#0c121e";
  ctx.fillRect(0, 0, w, h);

  ctx.strokeStyle = "rgba(255, 255, 255, 0.05)";
  ctx.lineWidth = 1;
  for (let y = 0; y <= h; y += h / 4) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(w, y);
    ctx.stroke();
  }

  // Margins
  const padX = 24;
  const padY = 16;
  const chartW = w - padX * 2;
  const chartH = h - padY * 2;

  function toX(t) {
    return padX + ((t - minT) / tSpan) * chartW;
  }
  function toY(s) {
    return padY + chartH - ((s - minS) / sSpan) * chartH;
  }

  // Gradient area under curve
  const grad = ctx.createLinearGradient(0, padY, 0, padY + chartH);
  grad.addColorStop(0, "rgba(239, 68, 68, 0.3)");
  grad.addColorStop(1, "rgba(239, 68, 68, 0.0)");

  ctx.beginPath();
  ctx.moveTo(toX(points[0].timestamp), padY + chartH);
  points.forEach((p) => {
    ctx.lineTo(toX(p.timestamp), toY(p.risk_score));
  });
  ctx.lineTo(toX(points[points.length - 1].timestamp), padY + chartH);
  ctx.closePath();
  ctx.fillStyle = grad;
  ctx.fill();

  // Trajectory line
  ctx.beginPath();
  ctx.strokeStyle = "#f87171";
  ctx.lineWidth = 2;
  points.forEach((p, i) => {
    const x = toX(p.timestamp);
    const y = toY(p.risk_score);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();

  // Nodes
  points.forEach((p) => {
    const x = toX(p.timestamp);
    const y = toY(p.risk_score);
    const isEvent = Math.abs(p.timestamp - eventTimestamp) < 0.15;

    ctx.beginPath();
    ctx.arc(x, y, isEvent ? 5 : 3, 0, Math.PI * 2);
    ctx.fillStyle = isEvent ? "#ef4444" : "#38bdf8";
    ctx.fill();
    ctx.strokeStyle = "#ffffff";
    ctx.lineWidth = 1;
    ctx.stroke();
  });

  // Trend direction
  const firstScore = points[0].risk_score;
  const lastScore = points[points.length - 1].risk_score;
  const diff = lastScore - firstScore;
  let statusText = "Stable Trajectory";
  if (diff > 4) statusText = `Escalating (+${diff.toFixed(1)})`;
  else if (diff < -4) statusText = `De-escalating (${diff.toFixed(1)})`;

  if (elements.riskTrendStatus) elements.riskTrendStatus.textContent = statusText;
  if (elements.riskTrendNotice) {
    elements.riskTrendNotice.textContent = `Monitored across ${points.length} frames (${minT.toFixed(2)}s to ${maxT.toFixed(2)}s). Red node indicates event frame.`;
  }
}

async function fetchAnalytics() {
  try {
    const res = await fetch(`${CONFIG.apiBase}/api/v1/analytics/summary`);
    if (!res.ok) throw new Error("Failed to fetch analytics");
    const data = await res.json();
    state.analyticsSummary = data;
    renderAnalytics(data);
  } catch (err) {
    console.warn("Could not fetch analytics:", err);
  }
}

function renderAnalytics(data) {
  if (!data) return;
  if (elements.kpiTotalIncidents) elements.kpiTotalIncidents.textContent = data.total_incidents;
  if (elements.kpiCriticalIncidents) elements.kpiCriticalIncidents.textContent = data.critical_incidents;
  if (elements.kpiZoneIntrusions) elements.kpiZoneIntrusions.textContent = data.zone_intrusions;
  if (elements.kpiPpeViolations) elements.kpiPpeViolations.textContent = data.ppe_violations;
  if (elements.kpiAvgDuration) elements.kpiAvgDuration.textContent = `${data.avg_incident_duration_s.toFixed(1)}s`;
  if (elements.kpiActiveIncidents) elements.kpiActiveIncidents.textContent = data.active_incidents;
  if (elements.kpiProximityEvents) elements.kpiProximityEvents.textContent = data.proximity_events;

  // Event Type Distribution
  if (elements.analyticsEventTypeDist) {
    const dist = data.event_type_distribution || {};
    const keys = Object.keys(dist);
    const total = data.total_incidents || 1;
    if (keys.length === 0) {
      elements.analyticsEventTypeDist.innerHTML = '<div style="color:var(--text-muted); font-size:12px; padding:12px;">No safety events recorded in distribution.</div>';
    } else {
      elements.analyticsEventTypeDist.innerHTML = keys
        .map((k) => {
          const count = dist[k];
          const pct = Math.min(100, Math.round((count / total) * 100));
          return `
            <div class="analytics-bar-row">
              <span class="analytics-bar-label">${escapeHtml(k.replace(/_/g, " "))}</span>
              <div class="analytics-bar-track">
                <div class="analytics-bar-fill" style="width: ${pct}%;"></div>
              </div>
              <span class="analytics-bar-val">${count} (${pct}%)</span>
            </div>`;
        })
        .join("");
    }
  }

  // Active Safety Zones
  if (elements.analyticsActiveZonesList) {
    const zones = data.active_zones || [];
    if (zones.length === 0) {
      elements.analyticsActiveZonesList.innerHTML = '<div style="color:var(--text-muted); font-size:12px; padding:12px;">No active safety zones configured or recorded.</div>';
    } else {
      elements.analyticsActiveZonesList.innerHTML = zones
        .map(
          (z) => `
          <div style="background: rgba(255,255,255,0.03); border: 1px solid var(--border-color); border-radius: 4px; padding: 10px 14px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center;">
            <div>
              <div style="font-weight: 600; color: #f1f5f9; font-size: 13px;">${escapeHtml(z.name || z.zone_id)}</div>
              <div style="font-size: 11px; color: var(--text-muted); margin-top: 2px;">Type: <span style="text-transform: capitalize;">${escapeHtml(z.zone_type || "restricted")}</span> | Max Dwell: ${z.max_dwell_seconds != null ? z.max_dwell_seconds + "s" : "N/A"}</div>
            </div>
            <div style="text-align: right;">
              <div style="font-family: var(--font-mono); font-weight: 700; color: ${z.incident_count > 0 ? "#ef4444" : "#10b981"}; font-size: 14px;">
                ${z.incident_count} Incidents
              </div>
              <div style="font-size: 10px; color: var(--text-muted);">Risk: ${escapeHtml(z.risk_tier || "LOW")}</div>
            </div>
          </div>
        `
        )
        .join("");
    }
  }
}

// -------------------------------------------------------------
// STEP 16: INTERACTIVE SAFETY ZONES & SCENE CONFIGURATION
// -------------------------------------------------------------
function initZonesModule() {
  if (elements.startDrawZoneBtn) {
    elements.startDrawZoneBtn.addEventListener("click", () => {
      startDrawingZone();
    });
  }

  if (elements.cancelDrawBtn) {
    elements.cancelDrawBtn.addEventListener("click", () => {
      cancelDrawingZone();
    });
  }

  if (elements.clearPointsBtn) {
    elements.clearPointsBtn.addEventListener("click", () => {
      clearDrawingPoints();
    });
  }

  if (elements.saveZoneBtn) {
    elements.saveZoneBtn.addEventListener("click", () => {
      saveZone();
    });
  }

  if (elements.zoneOverlayCanvas) {
    // Vertex placement on click
    elements.zoneOverlayCanvas.addEventListener("click", (e) => {
      if (!state.isDrawingZone) return;
      const [origX, origY] = displayToOriginal(e.clientX, e.clientY);
      state.currentZonePoints.push([origX, origY]);
      updatePointBadge();
      renderZonesOverlay();
    });

    // Real-time rubberband guideline on mousemove
    elements.zoneOverlayCanvas.addEventListener("mousemove", (e) => {
      if (!state.isDrawingZone || state.currentZonePoints.length === 0) return;
      state.cursorPos = [e.clientX, e.clientY];
      renderZonesOverlay();
    });

    elements.zoneOverlayCanvas.addEventListener("mouseleave", () => {
      if (state.cursorPos) {
        state.cursorPos = null;
        renderZonesOverlay();
      }
    });
  }

  window.addEventListener("resize", () => {
    renderZonesOverlay();
  });

  fetchZones();
}

function getZoneColor(zoneType) {
  switch ((zoneType || "").toLowerCase()) {
    case "restricted":
      return [239, 68, 68];
    case "hazard":
      return [245, 158, 11];
    case "machine":
      return [168, 85, 247];
    case "safety":
      return [16, 185, 129];
    case "monitored":
      return [56, 189, 248];
    case "safe":
      return [34, 197, 94];
    default:
      return [59, 130, 246];
  }
}

function getActiveMediaDimensions() {
  let targetEl = elements.canvas;
  let origW = elements.canvas ? elements.canvas.width || 1280 : 1280;
  let origH = elements.canvas ? elements.canvas.height || 720 : 720;

  if (elements.viewportVideo && elements.viewportVideo.style.display !== "none" && elements.viewportVideo.videoWidth > 0) {
    targetEl = elements.viewportVideo;
    origW = elements.viewportVideo.videoWidth;
    origH = elements.viewportVideo.videoHeight;
  } else if (elements.viewportImage && elements.viewportImage.style.display !== "none" && elements.viewportImage.naturalWidth > 0) {
    targetEl = elements.viewportImage;
    origW = elements.viewportImage.naturalWidth;
    origH = elements.viewportImage.naturalHeight;
  } else if (state.currentAssessment && state.currentAssessment.frame_width && state.currentAssessment.frame_height) {
    origW = state.currentAssessment.frame_width;
    origH = state.currentAssessment.frame_height;
  }

  return { targetEl, origW, origH };
}

function getViewportTransform() {
  const { targetEl, origW, origH } = getActiveMediaDimensions();
  const cRect = elements.viewportContainer
    ? elements.viewportContainer.getBoundingClientRect()
    : { left: 0, top: 0, width: origW, height: origH };

  const mRect = targetEl && targetEl.getBoundingClientRect
    ? targetEl.getBoundingClientRect()
    : cRect;

  const dispW = mRect.width > 0 ? mRect.width : cRect.width;
  const dispH = mRect.height > 0 ? mRect.height : cRect.height;
  const offX = mRect.left - cRect.left;
  const offY = mRect.top - cRect.top;

  const scale = Math.min(dispW / origW, dispH / origH);
  const renderedW = origW * scale;
  const renderedH = origH * scale;
  const padX = (dispW - renderedW) / 2.0;
  const padY = (dispH - renderedH) / 2.0;

  return { origW, origH, dispW, dispH, offX, offY, cRect, scale, padX, padY };
}

function displayToOriginal(clientX, clientY) {
  const { origW, origH, offX, offY, cRect, scale, padX, padY } = getViewportTransform();
  const clickX = clientX - cRect.left;
  const clickY = clientY - cRect.top;

  const relX = clickX - offX;
  const relY = clickY - offY;

  let origX = (relX - padX) / (scale || 1.0);
  let origY = (relY - padY) / (scale || 1.0);

  origX = Math.max(0, Math.min(origW, Math.round(origX)));
  origY = Math.max(0, Math.min(origH, Math.round(origY)));

  return [origX, origY];
}

function originalToDisplay(origX, origY) {
  const { offX, offY, scale, padX, padY } = getViewportTransform();
  const dispX = offX + padX + origX * (scale || 1.0);
  const dispY = offY + padY + origY * (scale || 1.0);
  return [dispX, dispY];
}

async function fetchZones() {
  try {
    const res = await fetch(`${CONFIG.apiBase}/api/v1/zones`);
    if (!res.ok) return;
    state.zones = await res.json();
    renderConfiguredZonesList();
    renderZonesOverlay();
  } catch (err) {
    console.warn("Could not fetch zones:", err);
  }
}

function renderConfiguredZonesList() {
  if (!elements.configuredZonesList) return;
  if (elements.configuredZoneCount) {
    elements.configuredZoneCount.textContent = (state.zones || []).length;
  }

  if (!state.zones || state.zones.length === 0) {
    elements.configuredZonesList.innerHTML = `
      <div style="color: var(--text-muted); font-size: 11px; padding: 12px; text-align: center;">
        No safety zones configured yet. Click "+ Draw Zone" to configure a zone.
      </div>`;
    return;
  }

  elements.configuredZonesList.innerHTML = state.zones
    .map((z) => {
      const zid = z.zone_id || z.id;
      const zType = (z.zone_type || "restricted").toLowerCase();
      const dwellVal = z.max_dwell_seconds != null ? z.max_dwell_seconds : z.max_dwell_time;
      const dwellText = dwellVal != null ? `Max Dwell: ${dwellVal}s` : "No Dwell Limit";
      const ptsCount = (z.polygon || []).length;

      return `
        <div class="zone-card">
          <div class="zone-card-header">
            <div class="zone-card-title">
              <span>${z.name}</span>
            </div>
            <span class="zone-badge zone-badge-${zType}">${zType}</span>
          </div>
          <div class="zone-card-meta">
            <span>ID: <code>${zid}</code></span>
            <span>•</span>
            <span>${ptsCount} Vertices</span>
            <span>•</span>
            <span>${dwellText}</span>
          </div>
          <div class="zone-card-actions" style="margin-top: 4px; justify-content: flex-end;">
            <button class="btn btn-sm" style="padding: 2px 8px; font-size: 10px;" onclick="window.editZone('${zid}')">
              ✎ Edit
            </button>
            <button class="btn btn-sm btn-danger" style="padding: 2px 8px; font-size: 10px;" onclick="window.deleteZone('${zid}')">
              ✕ Delete
            </button>
          </div>
        </div>
      `;
    })
    .join("");
}

function renderZonesOverlay() {
  if (!elements.zoneOverlayCanvas || !elements.viewportContainer) return;
  const canvas = elements.zoneOverlayCanvas;
  const container = elements.viewportContainer;

  const w = container.clientWidth;
  const h = container.clientHeight;
  if (w <= 0 || h <= 0) return;

  if (canvas.width !== w || canvas.height !== h) {
    canvas.width = w;
    canvas.height = h;
  }

  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, w, h);

  // 1. Render all configured zones
  (state.zones || []).forEach((z) => {
    if (!z.polygon || z.polygon.length < 3) return;
    const colorRgb = z.color && z.color.length === 3 ? z.color : getZoneColor(z.zone_type);
    const [r, g, b] = colorRgb;

    ctx.save();
    ctx.beginPath();
    let sumX = 0;
    let sumY = 0;

    z.polygon.forEach((pt, i) => {
      const [dx, dy] = originalToDisplay(pt[0], pt[1]);
      sumX += dx;
      sumY += dy;
      if (i === 0) ctx.moveTo(dx, dy);
      else ctx.lineTo(dx, dy);
    });

    ctx.closePath();
    ctx.fillStyle = `rgba(${r}, ${g}, ${b}, 0.22)`;
    ctx.fill();

    ctx.strokeStyle = `rgba(${r}, ${g}, ${b}, 0.85)`;
    ctx.lineWidth = 2;
    ctx.stroke();

    // Vertices
    z.polygon.forEach((pt) => {
      const [dx, dy] = originalToDisplay(pt[0], pt[1]);
      ctx.beginPath();
      ctx.arc(dx, dy, 3, 0, 2 * Math.PI);
      ctx.fillStyle = `rgb(${r}, ${g}, ${b})`;
      ctx.fill();
      ctx.strokeStyle = "#ffffff";
      ctx.lineWidth = 1;
      ctx.stroke();
    });

    // Centroid Label Badge
    const centroidX = sumX / z.polygon.length;
    const centroidY = sumY / z.polygon.length;
    const labelText = `${z.name} [${(z.zone_type || "").toUpperCase()}]`;

    ctx.font = "bold 9px monospace";
    const textMetrics = ctx.measureText(labelText);
    const pad = 4;
    const badgeW = textMetrics.width + pad * 2;
    const badgeH = 14;

    ctx.fillStyle = "rgba(10, 15, 25, 0.85)";
    ctx.strokeStyle = `rgba(${r}, ${g}, ${b}, 0.8)`;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.roundRect(centroidX - badgeW / 2, centroidY - badgeH / 2, badgeW, badgeH, 3);
    ctx.fill();
    ctx.stroke();

    ctx.fillStyle = `rgb(${r}, ${g}, ${b})`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(labelText, centroidX, centroidY);
    ctx.restore();
  });

  // 2. Render drawing-in-progress polygon
  if (state.isDrawingZone && state.currentZonePoints.length > 0) {
    ctx.save();
    ctx.setLineDash([4, 4]);
    ctx.strokeStyle = "#38bdf8";
    ctx.lineWidth = 2;

    ctx.beginPath();
    state.currentZonePoints.forEach((pt, idx) => {
      const [dx, dy] = originalToDisplay(pt[0], pt[1]);
      if (idx === 0) ctx.moveTo(dx, dy);
      else ctx.lineTo(dx, dy);
    });

    // Rubberband line to cursor
    if (state.cursorPos) {
      const cRect = container.getBoundingClientRect();
      const curX = state.cursorPos[0] - cRect.left;
      const curY = state.cursorPos[1] - cRect.top;
      ctx.lineTo(curX, curY);

      if (state.currentZonePoints.length >= 2) {
        // Guide back to first point
        const [firstDx, firstDy] = originalToDisplay(state.currentZonePoints[0][0], state.currentZonePoints[0][1]);
        ctx.strokeStyle = "rgba(56, 189, 248, 0.4)";
        ctx.stroke();
        ctx.beginPath();
        ctx.moveTo(curX, curY);
        ctx.lineTo(firstDx, firstDy);
      }
    }
    ctx.stroke();
    ctx.setLineDash([]);

    // Draw numbered vertices
    state.currentZonePoints.forEach((pt, idx) => {
      const [dx, dy] = originalToDisplay(pt[0], pt[1]);
      ctx.beginPath();
      ctx.arc(dx, dy, 6, 0, 2 * Math.PI);
      ctx.fillStyle = "#38bdf8";
      ctx.fill();
      ctx.strokeStyle = "#ffffff";
      ctx.lineWidth = 1.5;
      ctx.stroke();

      ctx.font = "bold 8px monospace";
      ctx.fillStyle = "#0f172a";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(`${idx + 1}`, dx, dy);
    });

    ctx.restore();
  }
}

function updatePointBadge() {
  if (!elements.zonePointCountBadge) return;
  const count = state.currentZonePoints.length;
  elements.zonePointCountBadge.textContent = `${count} points ${count < 3 ? "(min 3)" : "✓"}`;
  elements.zonePointCountBadge.style.color = count >= 3 ? "#34d399" : "#fbbf24";
}

function startDrawingZone() {
  state.isDrawingZone = true;
  state.currentZonePoints = [];
  state.cursorPos = null;
  state.editingZoneId = null;

  if (elements.zoneFormTitle) elements.zoneFormTitle.textContent = "NEW SAFETY ZONE";
  if (elements.zoneNameInput) elements.zoneNameInput.value = "";
  if (elements.zoneDwellInput) elements.zoneDwellInput.value = "";
  if (elements.zoneTypeSelect) elements.zoneTypeSelect.value = "restricted";
  if (elements.zoneDrawForm) elements.zoneDrawForm.style.display = "block";
  if (elements.zoneOverlayCanvas) elements.zoneOverlayCanvas.classList.add("drawing-active");

  updatePointBadge();
  renderZonesOverlay();
}

function cancelDrawingZone() {
  state.isDrawingZone = false;
  state.currentZonePoints = [];
  state.cursorPos = null;
  state.editingZoneId = null;

  if (elements.zoneDrawForm) elements.zoneDrawForm.style.display = "none";
  if (elements.zoneOverlayCanvas) elements.zoneOverlayCanvas.classList.remove("drawing-active");

  renderZonesOverlay();
}

function clearDrawingPoints() {
  state.currentZonePoints = [];
  state.cursorPos = null;
  updatePointBadge();
  renderZonesOverlay();
}

async function saveZone() {
  const name = elements.zoneNameInput ? elements.zoneNameInput.value.trim() : "";
  const zoneType = elements.zoneTypeSelect ? elements.zoneTypeSelect.value : "restricted";
  const dwellVal = elements.zoneDwellInput && elements.zoneDwellInput.value
    ? parseFloat(elements.zoneDwellInput.value)
    : null;

  if (!name) {
    alert("Please provide a name for this safety zone.");
    if (elements.zoneNameInput) elements.zoneNameInput.focus();
    return;
  }

  if (state.currentZonePoints.length < 3) {
    alert("Safety zones require at least 3 polygon vertices. Click on the scene image/video to place vertices.");
    return;
  }

  const { origW, origH } = getActiveMediaDimensions();
  const payload = {
    name: name,
    zone_type: zoneType,
    polygon: state.currentZonePoints,
    max_dwell_seconds: dwellVal,
    enabled: true,
    source_resolution: [origW, origH],
  };

  try {
    let res;
    if (state.editingZoneId) {
      res = await fetch(`${CONFIG.apiBase}/api/v1/zones/${state.editingZoneId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
    } else {
      res = await fetch(`${CONFIG.apiBase}/api/v1/zones`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
    }

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || "Failed to save safety zone");
    }

    cancelDrawingZone();
    await fetchZones();
  } catch (err) {
    alert(`Could not save zone: ${err.message}`);
  }
}

window.editZone = function (zoneId) {
  const zone = (state.zones || []).find((z) => (z.zone_id || z.id) === zoneId);
  if (!zone) return;

  const zid = zone.zone_id || zone.id;
  state.editingZoneId = zid;
  state.isDrawingZone = true;
  state.currentZonePoints = JSON.parse(JSON.stringify(zone.polygon || []));
  state.cursorPos = null;

  const dwellVal = zone.max_dwell_seconds != null ? zone.max_dwell_seconds : zone.max_dwell_time;
  if (elements.zoneFormTitle) elements.zoneFormTitle.textContent = `EDIT ZONE: ${zone.name}`;
  if (elements.zoneNameInput) elements.zoneNameInput.value = zone.name || "";
  if (elements.zoneTypeSelect) elements.zoneTypeSelect.value = (zone.zone_type || "restricted").toLowerCase();
  if (elements.zoneDwellInput) elements.zoneDwellInput.value = dwellVal != null ? dwellVal : "";
  if (elements.zoneDrawForm) elements.zoneDrawForm.style.display = "block";
  if (elements.zoneOverlayCanvas) elements.zoneOverlayCanvas.classList.add("drawing-active");

  // Activate Safety Zones tab
  const tabBtn = document.getElementById("tabZonesBtn");
  if (tabBtn) tabBtn.click();

  updatePointBadge();
  renderZonesOverlay();
};

window.deleteZone = async function (zoneId) {
  const confirmed = confirm(`Are you sure you want to delete safety zone '${zoneId}'?`);
  if (!confirmed) return;

  try {
    const res = await fetch(`${CONFIG.apiBase}/api/v1/zones/${zoneId}`, {
      method: "DELETE",
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || "Failed to delete safety zone");
    }

    if (state.editingZoneId === zoneId) {
      cancelDrawingZone();
    }

    await fetchZones();
  } catch (err) {
    alert(`Could not delete zone: ${err.message}`);
  }
};

