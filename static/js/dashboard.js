// ============================================================
// AI TRAFFIC SIGNAL OPTIMIZER - DASHBOARD CONTROLLER (v3.5)
// Real-Time Instant Detection & Continuous Telemetry Synchronization
// ============================================================

const ROAD_IDS = ["road1", "road2", "road3", "road4"];
let dashboardData = {};
let trafficChart = null;

// Tracking loops and pending state per road
const frameDetectionLoops = {};
const frameDetectionPending = {};
const roadPlaybackListeners = {};

// ============================================================
// INITIALIZATION
// ============================================================
document.addEventListener("DOMContentLoaded", () => {
    console.log("[DASHBOARD] Initializing AI Traffic Signal Dashboard v3.5...");

    initializeVideoPlayers();
    initTrafficChart();

    // Initial fetch and continuous 1-second synchronization with backend
    fetchTrafficStatus();
    setInterval(fetchTrafficStatus, 1000);
});

function initializeVideoPlayers() {
    ROAD_IDS.forEach(roadId => {
        clearCanvasOverlay(roadId);
        const video = document.getElementById(`${roadId}-video`);
        if (video) {
            video.controls = true;
            video.muted = true;
            video.loop = true;
            video.playsInline = true;

            // Bind playback time synchronization
            bindVideoPlaybackSync(roadId, video);
        }
    });
}

function bindVideoPlaybackSync(roadId, video) {
    if (roadPlaybackListeners[roadId]) return;

    video.addEventListener("timeupdate", () => {
        // Only synchronize metrics timeline when video processing has completed
        if (dashboardData[roadId]?.status === "COMPLETED") {
            syncMetricsWithTimeline(roadId, video.currentTime);
        }
    });

    video.addEventListener("play", () => {
        // Ensure no bounding boxes are drawn on the canvas during playback
        clearCanvasOverlay(roadId);
    });

    roadPlaybackListeners[roadId] = true;
}

// ============================================================
// VIDEO UPLOAD HANDLER
// ============================================================
function uploadRoadVideo(roadId) {
    const input = document.getElementById(`${roadId}-input`);
    if (!input || !input.files || input.files.length === 0) {
        console.warn(`[UPLOAD] No file selected for ${roadId}`);
        return;
    }

    const file = input.files[0];
    console.log(`[UPLOAD] Selected ${file.name} for ${roadId} (${(file.size / (1024 * 1024)).toFixed(1)} MB)`);

    // Reset local road data state for fresh upload - metrics withheld until processing finishes
    if (!dashboardData[roadId]) {
        dashboardData[roadId] = {};
    }
    dashboardData[roadId].telemetry_timeline = [];
    dashboardData[roadId].processed_video = null;
    dashboardData[roadId].status = "PROCESSING";

    // Stop any live canvas detection loops and clear overlay
    stopRealTimeDetection(roadId);
    clearCanvasOverlay(roadId);
    resetPendingTelemetryDisplay(roadId, "PROCESSING");

    const video = document.getElementById(`${roadId}-video`);
    if (video) {
        const localURL = URL.createObjectURL(file);
        video.src = localURL;
        video.dataset.source = localURL;
        video.style.display = "block";
        video.controls = true;
        video.muted = true;
        video.loop = true;
        video.playsInline = true;

        clearCanvasOverlay(roadId);

        // Preview raw video cleanly without any bounding boxes
        const playPromise = video.play();
        if (playPromise !== undefined) {
            playPromise.catch(e => {
                console.log(`[VIDEO] Autoplay notice for ${roadId}:`, e);
            });
        }
    }

    // Hide upload button overlay
    const overlay = document.getElementById(`${roadId}-upload-overlay`);
    if (overlay) overlay.style.display = "none";

    const progressBar = document.getElementById(`${roadId}-progress-bar`);
    const progressContainer = document.getElementById(`${roadId}-progress-container`);
    if (progressContainer) progressContainer.style.display = "block";
    if (progressBar) progressBar.style.width = "20%";

    updateRoadStatusBadge(roadId, "PROCESSING");
    addSystemLog(`[${roadId.toUpperCase()}] Video '${file.name}' uploaded. Background AI analysis in progress (metrics and signal timing withheld until complete).`);

    const formData = new FormData();
    formData.append("video", file);

    const xhr = new XMLHttpRequest();
    xhr.open("POST", `/upload/${roadId}`, true);

    xhr.upload.onprogress = function(e) {
        if (e.lengthComputable && progressBar) {
            const pct = Math.round((e.loaded / e.total) * 90);
            progressBar.style.width = `${pct}%`;
        }
    };

    xhr.onload = function() {
        if (progressContainer) progressContainer.style.display = "none";
        if (xhr.status === 200) {
            try {
                const res = JSON.parse(xhr.responseText);
                if (res.success) {
                    addSystemLog(`[${roadId.toUpperCase()}] Upload confirmed. Processing full video in background.`);
                    fetchTrafficStatus();
                } else {
                    addSystemLog(`[${roadId.toUpperCase()}] Upload error: ${res.error || 'Server error'}`);
                    updateRoadStatusBadge(roadId, "ERROR");
                }
            } catch (err) {
                console.error("[UPLOAD] JSON parse error:", err);
            }
        } else {
            addSystemLog(`[${roadId.toUpperCase()}] Server returned status ${xhr.status}.`);
            updateRoadStatusBadge(roadId, "ERROR");
        }
    };

    xhr.onerror = function() {
        if (progressContainer) progressContainer.style.display = "none";
        addSystemLog(`[${roadId.toUpperCase()}] Network error during upload.`);
        updateRoadStatusBadge(roadId, "ERROR");
    };

    xhr.send(formData);
}

// ============================================================
// REAL-TIME INSTANT DETECTION ON PLAYING VIDEO
// ============================================================
async function captureAndDetectSingleFrame(roadId) {
    if (frameDetectionPending[roadId]) return;

    // Do NOT run live frame detection or draw bounding boxes unless processing is COMPLETED
    if (!dashboardData[roadId] || dashboardData[roadId].status !== "COMPLETED") {
        clearCanvasOverlay(roadId);
        return;
    }

    const video = document.getElementById(`${roadId}-video`);
    if (!video || video.paused || video.ended) return;

    // Wait until video has rendered at least one frame
    if (video.readyState < 2 && video.videoWidth === 0) return;

    // If processed video is loaded AND timeline is driving telemetry, skip duplicate HTTP detection
    const isProcessed = video.src && video.src.includes("_detected");
    const hasTimeline = dashboardData[roadId]?.telemetry_timeline?.length > 0;
    if (isProcessed && hasTimeline) {
        stopRealTimeDetection(roadId);
        clearCanvasOverlay(roadId);
        return;
    }

    const nativeW = video.videoWidth || 640;
    const nativeH = video.videoHeight || 360;

    // Draw video frame to small offscreen canvas for fast transmission (480x270)
    const tempCanvas = document.createElement("canvas");
    tempCanvas.width = 480;
    tempCanvas.height = 270;

    const ctx = tempCanvas.getContext("2d");
    try {
        ctx.drawImage(video, 0, 0, tempCanvas.width, tempCanvas.height);
    } catch (e) {
        return;
    }

    const imageData = tempCanvas.toDataURL("image/jpeg", 0.70);
    if (!imageData || imageData.length < 50) return;

    frameDetectionPending[roadId] = true;

    try {
        const response = await fetch("/api/traffic/detect_frame", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ image: imageData, road_id: roadId })
        });

        frameDetectionPending[roadId] = false;
        if (!response.ok) return;

        const result = await response.json();
        if (result.success && Array.isArray(result.detections)) {
            // Draw bounding boxes on canvas overlay immediately
            renderInstantOverlayBoxes(roadId, result.detections, result.frame_width, result.frame_height);

            // Directly update live telemetry fields from real calculation
            updateLiveTelemetryDisplay(roadId, {
                current_vehicles: result.current_vehicles,
                line_crossed_count: result.line_crossed_count,
                unique_vehicle_count: result.unique_vehicle_count,
                occupied_area_m2: result.occupied_area_m2,
                road_area_m2: result.road_area_m2,
                density_percentage: result.density_percentage,
                density: result.density_category,
                density_category: result.density_category,
                congestion: result.congestion,
                stopped_vehicles: result.stopped_vehicles
            });
        }
    } catch (err) {
        frameDetectionPending[roadId] = false;
    }
}

function startRealTimeDetection(roadId) {
    stopRealTimeDetection(roadId);

    const video = document.getElementById(`${roadId}-video`);
    if (video && video.src && video.src.includes("_detected")) {
        const hasTimeline = dashboardData[roadId]?.telemetry_timeline?.length > 0;
        if (hasTimeline) {
            clearCanvasOverlay(roadId);
            return;
        }
    }

    frameDetectionPending[roadId] = false;

    // Trigger first frame check immediately
    captureAndDetectSingleFrame(roadId);

    // Run responsive detection loop every 250ms (~4 FPS inference)
    frameDetectionLoops[roadId] = setInterval(() => {
        captureAndDetectSingleFrame(roadId);
    }, 250);
}

function stopRealTimeDetection(roadId) {
    if (frameDetectionLoops[roadId]) {
        clearInterval(frameDetectionLoops[roadId]);
        delete frameDetectionLoops[roadId];
        frameDetectionPending[roadId] = false;
    }
}

function clearCanvasOverlay(roadId) {
    const canvas = document.getElementById(`${roadId}-canvas`);
    if (canvas) {
        const ctx = canvas.getContext("2d");
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        canvas.style.display = "none";
    }
}

function renderInstantOverlayBoxes(roadId, detections, frameWidth, frameHeight) {
    const canvas = document.getElementById(`${roadId}-canvas`);
    const video = document.getElementById(`${roadId}-video`);
    if (!canvas || !video) return;

    // Do NOT draw bounding boxes during processing or while not COMPLETED
    if (!dashboardData[roadId] || dashboardData[roadId].status !== "COMPLETED") {
        clearCanvasOverlay(roadId);
        return;
    }

    // If processed video is active, boxes are already in the video stream
    if (video.src && video.src.includes("_detected")) {
        clearCanvasOverlay(roadId);
        return;
    }

    const clientW = video.clientWidth || 320;
    const clientH = video.clientHeight || 180;
    canvas.width = clientW;
    canvas.height = clientH;
    canvas.style.display = "block";

    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    if (!detections || detections.length === 0) return;

    const nativeW = frameWidth || video.videoWidth || 480;
    const nativeH = frameHeight || video.videoHeight || 270;
    const scaleX = clientW / nativeW;
    const scaleY = clientH / nativeH;

    const classColors = {
        car: "#00f0ff",
        motorcycle: "#00e676",
        bus: "#ffaa00",
        truck: "#ff7700",
        bicycle: "#e040fb"
    };

    detections.forEach(det => {
        const x1 = det.x1 * scaleX;
        const y1 = det.y1 * scaleY;
        const w = (det.x2 - det.x1) * scaleX;
        const h = (det.y2 - det.y1) * scaleY;
        const className = (det.class_name || "car").toLowerCase();
        const color = classColors[className] || "#00f0ff";
        const trackId = det.track_id ? `#${det.track_id} ` : "";

        // Bounding box
        ctx.strokeStyle = color;
        ctx.lineWidth = 2;
        ctx.strokeRect(x1, y1, w, h);

        // Label
        const label = `${trackId}${className.toUpperCase()} ${(det.confidence * 100).toFixed(0)}%`;
        ctx.font = '10px "Inter", sans-serif';
        const tw = ctx.measureText(label).width;

        ctx.fillStyle = color;
        ctx.fillRect(x1, Math.max(0, y1 - 16), tw + 8, 16);
        ctx.fillStyle = "#06090e";
        ctx.fillText(label, x1 + 4, Math.max(12, y1 - 4));

        // Centroid dot
        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.arc(x1 + w / 2, y1 + h / 2, 3, 0, 2 * Math.PI);
        ctx.fill();
    });
}

// ============================================================
// CONTINUOUS VIDEO PLAYBACK TELEMETRY SYNCHRONIZATION
// ============================================================
function syncMetricsWithTimeline(roadId, currentTime) {
    const road = dashboardData[roadId];
    if (!road || !road.telemetry_timeline || road.telemetry_timeline.length === 0) {
        return;
    }

    const timeline = road.telemetry_timeline;
    // Find closest recorded frame to currentTime
    let best = timeline[0];
    let minDiff = Math.abs(currentTime - best.t);

    for (let i = 1; i < timeline.length; i++) {
        const diff = Math.abs(currentTime - timeline[i].t);
        if (diff < minDiff) {
            minDiff = diff;
            best = timeline[i];
        } else if (diff > minDiff && timeline[i].t > currentTime) {
            break;
        }
    }

    if (best) {
        updateLiveTelemetryDisplay(roadId, best);
    }
}

function updateLiveTelemetryDisplay(roadId, snapshot) {
    if (!snapshot) return;

    // 1. Vehicle counts
    const activeEl = document.getElementById(`${roadId}-active`);
    if (activeEl && snapshot.current_vehicles !== undefined) {
        activeEl.textContent = snapshot.current_vehicles;
    }

    const crossedEl = document.getElementById(`${roadId}-crossed`);
    if (crossedEl && snapshot.line_crossed_count !== undefined) {
        crossedEl.textContent = snapshot.line_crossed_count;
    }

    const uniqueEl = document.getElementById(`${roadId}-vehicles`);
    if (uniqueEl && snapshot.unique_vehicle_count !== undefined) {
        uniqueEl.textContent = snapshot.unique_vehicle_count;
    }

    // 2. Physical area density
    const densityEl = document.getElementById(`${roadId}-density`);
    if (densityEl && (snapshot.density || snapshot.density_category)) {
        const cat = String(snapshot.density || snapshot.density_category).toUpperCase();
        densityEl.textContent = cat;
        if (cat === "VERY HIGH" || cat === "HIGH") densityEl.style.color = "#ff334b";
        else if (cat === "MEDIUM") densityEl.style.color = "#ffaa00";
        else densityEl.style.color = "#00e676";
    }

    const densityDetailEl = document.getElementById(`${roadId}-density-detail`);
    if (densityDetailEl && snapshot.occupied_area_m2 !== undefined) {
        const occ = Number(snapshot.occupied_area_m2).toFixed(1);
        const rArea = Number(snapshot.road_area_m2 || 350).toFixed(0);
        const pct = Number(snapshot.density_percentage || 0).toFixed(1);
        densityDetailEl.textContent = `Area: ${occ} m² / ${rArea} m² (${pct}%)`;
    }

    // 3. Congestion status
    const congEl = document.getElementById(`${roadId}-congestion`);
    if (congEl && snapshot.congestion) {
        const cVal = String(snapshot.congestion).toUpperCase();
        congEl.textContent = cVal;
        if (cVal === "HIGH") congEl.style.color = "#ff334b";
        else if (cVal === "MODERATE") congEl.style.color = "#ffaa00";
        else congEl.style.color = "#00e676";
    }

    const congDetailEl = document.getElementById(`${roadId}-congestion-detail`);
    if (congDetailEl && snapshot.stopped_vehicles !== undefined) {
        congDetailEl.textContent = `Stopped: ${snapshot.stopped_vehicles} vehicles in queue`;
    }

    // Sync state for comparison chart
    if (dashboardData[roadId]) {
        dashboardData[roadId].current_vehicles = snapshot.current_vehicles;
        dashboardData[roadId].active_vehicles = snapshot.current_vehicles;
        dashboardData[roadId].density_percentage = snapshot.density_percentage;
        updateTrafficChart(dashboardData);
    }
}

// ============================================================
// SERVER SYNCHRONIZATION (POLLING /api/traffic/status)
// ============================================================
async function fetchTrafficStatus() {
    try {
        const response = await fetch("/api/traffic/status", { cache: "no-store" });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const data = await response.json();
        dashboardData = data;

        // Update overall junction active phase header
        if (data.meta) {
            const activePhaseEl = document.getElementById("active-phase-indicator");
            if (activePhaseEl) {
                if (!data.meta.is_active) {
                    activePhaseEl.textContent = "STANDBY (AWAITING PROCESSED VIDEO)";
                    activePhaseEl.className = "status-val";
                    activePhaseEl.style.color = "#8b949e";
                } else {
                    const rName = (data.meta.active_road || "road1").toUpperCase();
                    const rState = data.meta.active_state || "GREEN";
                    activePhaseEl.textContent = `${rName} (${rState})`;
                    activePhaseEl.className = rState === "GREEN" ? "status-val online" : "status-val";
                    if (rState === "YELLOW") activePhaseEl.style.color = "#ffaa00";
                    else if (rState === "GREEN") activePhaseEl.style.color = "#00e676";
                }
            }
        }

        // Update each of the four road panels
        ROAD_IDS.forEach(roadId => {
            if (data[roadId]) {
                updateRoadCard(roadId, data[roadId]);
            }
        });

        // Update real comparison chart
        updateTrafficChart(data);

    } catch (err) {
        console.error("[TRAFFIC API] Status fetch error:", err);
    }
}

function resetPendingTelemetryDisplay(roadId, status) {
    const isProcessing = String(status || "").toUpperCase() === "PROCESSING";

    // 1. Vehicle counts: show -- until processing completes
    const activeEl = document.getElementById(`${roadId}-active`);
    if (activeEl) activeEl.textContent = "--";

    const crossedEl = document.getElementById(`${roadId}-crossed`);
    if (crossedEl) crossedEl.textContent = "--";

    const uniqueEl = document.getElementById(`${roadId}-vehicles`);
    if (uniqueEl) uniqueEl.textContent = "--";

    // 2. Traffic Density: show placeholder until processing completes
    const densityEl = document.getElementById(`${roadId}-density`);
    if (densityEl) {
        densityEl.textContent = isProcessing ? "PROCESSING..." : "--";
        densityEl.style.color = "#8b949e";
    }

    const densityDetailEl = document.getElementById(`${roadId}-density-detail`);
    if (densityDetailEl) {
        densityDetailEl.textContent = isProcessing ? "Calculating road density..." : "Area: -- m² / 350 m² (--%)";
    }

    // 3. Congestion: show placeholder until processing completes
    const congEl = document.getElementById(`${roadId}-congestion`);
    if (congEl) {
        congEl.textContent = isProcessing ? "PROCESSING..." : "--";
        congEl.style.color = "#8b949e";
    }

    const congDetailEl = document.getElementById(`${roadId}-congestion-detail`);
    if (congDetailEl) {
        congDetailEl.textContent = isProcessing ? "Analyzing vehicle motion..." : "Queue flow analysis";
    }
}

function updateRoadCard(roadId, road) {
    if (!road) return;

    const video = document.getElementById(`${roadId}-video`);

    // Strictly withhold vehicle count, density, and congestion until processing is COMPLETED!
    if (road.status === "COMPLETED") {
        const isPlaying = video && !video.paused && !video.ended;
        if (!isPlaying || !road.telemetry_timeline || road.telemetry_timeline.length === 0) {
            updateLiveTelemetryDisplay(roadId, road);
        }
    } else {
        resetPendingTelemetryDisplay(roadId, road.status);
    }

    // Emergency Feature Status
    const emgEl = document.getElementById(`${roadId}-emergency`);
    if (emgEl) {
        emgEl.textContent = "NOT CONFIGURED";
        emgEl.className = "emg-unconfigured";
    }

    // Decision Reason Callout
    const reasonEl = document.getElementById(`${roadId}-reason`);
    if (reasonEl) {
        if (road.status === "PROCESSING") {
            reasonEl.textContent = "Video processing in progress... Calculating vehicle count, density, and congestion.";
        } else if (road.status === "IDLE") {
            reasonEl.textContent = "Awaiting video upload to calculate traffic parameters.";
        } else {
            reasonEl.textContent = road.decision_reason || "Waiting for signal phase assignment...";
        }
    }

    // Signal Light States & Countdown
    const redLight = document.getElementById(`${roadId}-light-red`);
    const yellowLight = document.getElementById(`${roadId}-light-yellow`);
    const greenLight = document.getElementById(`${roadId}-light-green`);
    const timerEl = document.getElementById(`${roadId}-timer`);
    const cardEl = document.getElementById(`card-${roadId}`);

    const isSystemActive = Boolean(dashboardData.meta && dashboardData.meta.is_active);

    if (redLight && yellowLight && greenLight) {
        redLight.classList.remove("active");
        yellowLight.classList.remove("active");
        greenLight.classList.remove("active");
        if (cardEl) cardEl.classList.remove("active-lane");

        if (!isSystemActive) {
            // Intersection in standby: all lights stay RED, no switching occurs
            redLight.classList.add("active");
        } else {
            const sig = String(road.signal || "RED").toUpperCase();
            if (sig === "GREEN") {
                greenLight.classList.add("active");
                if (cardEl) cardEl.classList.add("active-lane");
            } else if (sig === "YELLOW") {
                yellowLight.classList.add("active");
                if (cardEl) cardEl.classList.add("active-lane");
            } else {
                redLight.classList.add("active");
            }
        }
    }

    if (timerEl) {
        if (isSystemActive && road.remaining_time !== undefined && road.remaining_time !== null) {
            timerEl.textContent = Math.max(0, Math.round(road.remaining_time));
            const sig = String(road.signal || "RED").toUpperCase();
            if (sig === "GREEN") {
                timerEl.style.color = "var(--light-green-active, #00ff88)";
                timerEl.style.textShadow = "0 0 12px rgba(0, 255, 136, 0.6)";
            } else if (sig === "YELLOW") {
                timerEl.style.color = "var(--light-yellow-active, #ffcc00)";
                timerEl.style.textShadow = "0 0 12px rgba(255, 204, 0, 0.6)";
            } else {
                timerEl.style.color = "var(--light-red-active, #ff3344)";
                timerEl.style.textShadow = "0 0 12px rgba(255, 51, 68, 0.6)";
            }
        } else {
            timerEl.textContent = "--";
            timerEl.style.color = "#ffffff";
            timerEl.style.textShadow = "none";
        }
    }

    // Status Badge
    updateRoadStatusBadge(roadId, road.status);

    // Processed Video playback switchover
    if (road.processed_video && video) {
        const targetSrc = road.processed_video;
        if (video.dataset.source !== targetSrc) {
            console.log(`[VIDEO] Switching to processed video stream for ${roadId}: ${targetSrc}`);
            video.dataset.source = targetSrc;
            video.src = `${targetSrc}?t=${Date.now()}`;
            video.load();
            video.play().catch(() => {});

            // Stop canvas drawing since boxes are now rendered into the video
            stopRealTimeDetection(roadId);
            clearCanvasOverlay(roadId);

            addSystemLog(`[${roadId.toUpperCase()}] Processed video loaded with annotations & telemetry HUD.`);
        }
    }
}

function updateRoadStatusBadge(roadId, status) {
    const badge = document.getElementById(`${roadId}-status-badge`);
    if (!badge) return;

    const s = String(status || "IDLE").toUpperCase();
    badge.textContent = s;
    badge.className = `road-status-badge ${s.toLowerCase()}`;
}

// ============================================================
// SYSTEM LOGS HELPER
// ============================================================
function addSystemLog(message) {
    const container = document.getElementById("system-logs-container");
    if (!container) return;

    const item = document.createElement("div");
    item.className = "log-item";
    const time = new Date().toLocaleTimeString();
    item.textContent = `[${time}] ${message}`;

    container.prepend(item);
    while (container.children.length > 25) {
        container.removeChild(container.lastChild);
    }
}

// ============================================================
// INTERSECTION TRAFFIC LOAD COMPARISON CHART
// ============================================================
function initTrafficChart() {
    const canvas = document.getElementById("dashboardChart");
    if (!canvas || typeof Chart === "undefined") return;

    const ctx = canvas.getContext("2d");
    trafficChart = new Chart(ctx, {
        type: "bar",
        data: {
            labels: ["Road 1 (North)", "Road 2 (East)", "Road 3 (South)", "Road 4 (West)"],
            datasets: [
                {
                    label: "Current Vehicles (ROI)",
                    data: [0, 0, 0, 0],
                    backgroundColor: "rgba(0, 240, 255, 0.75)",
                    borderColor: "#00f0ff",
                    borderWidth: 1,
                    borderRadius: 4
                },
                {
                    label: "Density (%)",
                    data: [0, 0, 0, 0],
                    backgroundColor: "rgba(0, 230, 118, 0.75)",
                    borderColor: "#00e676",
                    borderWidth: 1,
                    borderRadius: 4
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    labels: { color: "#8fa0dd", font: { family: "Inter", size: 11 } }
                }
            },
            scales: {
                x: {
                    ticks: { color: "#8fa0dd", font: { family: "Inter", size: 10 } },
                    grid: { color: "rgba(255, 255, 255, 0.04)" }
                },
                y: {
                    beginAtZero: true,
                    suggestedMax: 20,
                    ticks: { color: "#8fa0dd", font: { family: "Inter", size: 10 } },
                    grid: { color: "rgba(255, 255, 255, 0.04)" }
                }
            }
        }
    });
}

function updateTrafficChart(data) {
    if (!trafficChart || !data) return;

    const activeCounts = ROAD_IDS.map(rid => {
        const r = data[rid] || {};
        return Number(r.current_vehicles ?? r.active_vehicles ?? 0);
    });

    const densities = ROAD_IDS.map(rid => {
        const r = data[rid] || {};
        return Number(r.density_percentage ?? 0);
    });

    trafficChart.data.datasets[0].data = activeCounts;
    trafficChart.data.datasets[1].data = densities;
    trafficChart.update("none");
}