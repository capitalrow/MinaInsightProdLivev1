/**
 * File: /static/js/live.js
 * Purpose: Mina Live Recording Controller (NON-REGRESSIVE)
 * Notes:
 *  - This is your original file wrapped with a minimal finalize step.
 *  - All existing behavior (socket, start/stop, UI updates) is preserved.
 *  - Adds a safe POST to /api/sessions/<external_id>/complete after onstop.
 */

(() => {
  // === Utility shims (unchanged) ===========================================
  const $ = (id) => document.getElementById(id);
  const dlog = (msg) => { const el = $("debug"); if (el) el.textContent += msg + "\n"; };

  // === NEW: Resolve session external_id safely =============================
  // Prefer <body data-session-external-id="...">, fallback to <meta name="mina-session-external-id">
  function resolveExternalId() {
    const bodyAttr = document.body?.dataset?.sessionExternalId;
    if (bodyAttr && bodyAttr.trim()) return bodyAttr.trim();
    const meta = document.querySelector('meta[name="mina-session-external-id"]');
    const metaVal = meta?.getAttribute('content');
    return metaVal && metaVal.trim() ? metaVal.trim() : null;
  }
  const SESSION_EXTERNAL_ID = resolveExternalId();

  // === Socket.IO (unchanged) ===============================================
  const socket = io({
    path: '/socket.io',
    transports: ['websocket', 'polling'],
    reconnection: true,
    reconnectionAttempts: Infinity,
    reconnectionDelay: 1000,
    reconnectionDelayMax: 5000,
    timeout: 20000,
    upgrade: true
  });

  let mediaRecorder, stream, chunks = [];

  socket.on("connect", () => {
    if ($("conn")) {
      $("conn").textContent = "Connected";
      $("conn").className = "pill pill-ok";
    }
    dlog("socket connected");
  });

  socket.on("server_status", (p) => dlog(p.message));

  // === Bind UI (unchanged) =================================================
  if ($("btnStart")) $("btnStart").addEventListener("click", start);
  if ($("btnStop"))  $("btnStop").addEventListener("click", stop);

  // === Start recording (unchanged, with iOS MIME handling) =================
  async function start() {
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (e) {
      dlog("ERR mic: " + e.message);
      return;
    }

    let mime = "audio/webm;codecs=opus";
    if (!MediaRecorder.isTypeSupported(mime)) {
      if (MediaRecorder.isTypeSupported('audio/webm')) {
        mime = 'audio/webm';
      } else if (MediaRecorder.isTypeSupported('audio/mp4')) {
        mime = 'audio/mp4'; // iOS Safari fallback
      } else if (MediaRecorder.isTypeSupported('audio/aac')) {
        mime = 'audio/aac'; // iOS Safari fallback
      } else if (MediaRecorder.isTypeSupported('audio/ogg;codecs=opus')) {
        mime = 'audio/ogg;codecs=opus';
      } else {
        mime = ''; // Let browser decide
      }
    }

    dlog("Using MIME type: " + (mime || "browser default"));
    mediaRecorder = new MediaRecorder(stream, mime ? { mimeType: mime } : {});

    mediaRecorder.ondataavailable = (e) => {
      if (!e.data.size) return;
      chunks.push(e.data);
      e.data.arrayBuffer().then((buf) => {
        socket.emit("audio_chunk", buf);
      });
    };

    mediaRecorder.onstart = () => {
      if ($("btnStart")) $("btnStart").disabled = true;
      if ($("btnStop"))  $("btnStop").disabled = false;
      dlog("MediaRecorder started");
    };

    // === onstop: original behavior + NEW finalize call =====================
    mediaRecorder.onstop = async () => {
      const full = new Blob(chunks, { type: mediaRecorder.mimeType || mime || 'application/octet-stream' });
      chunks = [];
      full.arrayBuffer().then((buf) => {
        // 1) ORIGINAL: tell server audio stream ended
        socket.emit("audio_end", buf);
      });

      if ($("btnStart")) $("btnStart").disabled = false;
      if ($("btnStop"))  $("btnStop").disabled = true;
      dlog("MediaRecorder stopped");

      // 2) Show quick saving indicator
      console.log("🛑 Stop pressed, SESSION_EXTERNAL_ID:", SESSION_EXTERNAL_ID);
      showQuickSaveIndicator();

      // 3) Finalize session and redirect immediately (industry-standard approach)
      // Insights will continue processing in background - user sees transcript immediately
      const success = await finalizeSessionSafe(SESSION_EXTERNAL_ID);
      
      // 4) Redirect to session view immediately - don't wait for insights
      console.log("🚀 Redirecting to transcript view immediately...");
      if (SESSION_EXTERNAL_ID) {
        window.location.href = `/sessions/${SESSION_EXTERNAL_ID}/refined`;
      }
    };

    // Chunk every 3s (unchanged)
    mediaRecorder.start(3000);
  }

  // === Stop recording (unchanged) =========================================
  function stop() {
    if (mediaRecorder && mediaRecorder.state !== "inactive") {
      mediaRecorder.stop();
    }
    if (stream) {
      stream.getTracks().forEach(t => t.stop());
    }
  }

  // === Transcript UI - Enhanced with speaker info ========================
  let interimBuffer = "";
  let finalBuffer = "";
  
  socket.on("transcription_result", (data) => {
    const text = (data.text || "").trim();
    if (!text) return;
    
    const isFinal = data.is_final || false;
    const speakerName = data.speaker_name || "";
    
    if (isFinal) {
      // Final result - append to final transcript
      finalBuffer = finalBuffer ? finalBuffer + " " + text : text;
      if ($("final")) $("final").textContent = finalBuffer;
      
      // Clear interim
      interimBuffer = "";
      if ($("interim")) $("interim").textContent = "";
      
      dlog(`✅ Final: ${text.substring(0, 50)}...`);
    } else {
      // Interim result - show in interim area
      interimBuffer = text;
      if ($("interim")) {
        $("interim").textContent = speakerName ? `${speakerName}: ${text}` : text;
      }
    }
  });

  // === CROWN+ Event Listeners for Post-Transcription Pipeline ============
  socket.on("transcript_finalized", (data) => {
    dlog(`📝 Transcript finalized: ${data.word_count} words`);
    updateProcessingState("Finalizing transcript...", 12.5);
  });

  socket.on("transcript_refined", (data) => {
    dlog(`✨ Transcript refined: ${data.word_count} words`);
    updateProcessingState("Polishing transcript...", 25);
  });

  socket.on("insights_generate", (data) => {
    if (data.status === 'processing') {
      dlog(`🎯 ${data.message}`);
      updateProcessingState("Crafting highlights...", 37.5);
    } else if (data.status === 'completed') {
      dlog(`✅ Insights generated: ${data.action_count} actions`);
      updateProcessingState("Insights ready...", 50);
    }
  });

  // Progress updates for chunked analysis (long transcripts)
  socket.on("insights_progress", (data) => {
    const { current_chunk, total_chunks, progress_percent, status, message } = data;
    
    if (status === 'started') {
      dlog(`📊 ${message}`);
      updateProcessingState(message, 30);
    } else if (status === 'processing') {
      dlog(`📊 Chunk ${current_chunk}/${total_chunks} (${progress_percent}%)`);
      // Map chunk progress (0-100%) to the insights phase (30-50% of total)
      const mappedProgress = 30 + (progress_percent * 0.2);
      updateProcessingState(message, mappedProgress);
    } else if (status === 'merging') {
      dlog(`🔄 ${message}`);
      updateProcessingState(message, 48);
    } else if (status === 'completed') {
      dlog(`✅ ${message}`);
      updateProcessingState("Insights ready...", 50);
    } else if (status === 'failed') {
      dlog(`❌ ${message}`);
    }
  });

  socket.on("analytics_update", (data) => {
    dlog(`📊 Analytics updated`);
    updateProcessingState("Analyzing metrics...", 62.5);
  });

  socket.on("tasks_generation", (data) => {
    dlog(`✅ ${data.message}`);
    updateProcessingState("Extracting action items...", 75);
  });

  socket.on("post_transcription_reveal", (data) => {
    dlog(`🎬 Post-transcription complete! Redirecting...`);
    updateProcessingState("Preparing your insights...", 87.5);
    
    // Event-driven navigation (replaces timeout)
    setTimeout(() => {
      window.location.href = data.redirect_url || `/sessions/${SESSION_EXTERNAL_ID}/refined`;
    }, 800);
  });

  socket.on("session_finalized", (data) => {
    dlog(`✅ Session finalized: ${data.session_id}`);
    updateProcessingState("Finalizing session...", 100);
  });

  socket.on("dashboard_refresh", (data) => {
    dlog(`🔄 Dashboard refresh triggered`);
  });

  // === NEW: finalize helper with graceful fallbacks ========================
  async function finalizeSessionSafe(externalId) {
    console.log("🎬 finalizeSessionSafe called with:", externalId);
    
    if (!externalId) {
      console.warn("⚠️ No external session id found; skipping finalize.");
      dlog("⚠️ No external session id found; skipping finalize.");
      return false;
    }

    // Small debounce to let server finish last chunk processing
    await sleep(350);

    const url = `/api/sessions/${encodeURIComponent(externalId)}/complete`;
    console.log("🔄 Calling finalization endpoint:", url);
    
    try {
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ force: false })
      });
      
      console.log("📥 Finalization response status:", res.status);
      
      if (!res.ok) {
        const errorText = await res.text();
        console.warn(`⚠️ finalize returned ${res.status}: ${errorText}`);
        dlog(`⚠️ finalize returned ${res.status}; will retry once...`);
        
        // One retry after a short delay, in case of race with final segment write
        await sleep(500);
        const retry = await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ force: true })
        });
        
        console.log("📥 Retry response status:", retry.status);
        
        if (!retry.ok) {
          const retryErrorText = await retry.text();
          console.error(`❌ finalize retry failed: ${retry.status} - ${retryErrorText}`);
          dlog(`❌ finalize retry failed: ${retry.status}`);
          return false;
        } else {
          const retryData = await retry.json();
          console.log("✅ finalize retry succeeded:", retryData);
          dlog("✅ finalize retry succeeded.");
          return true;
        }
      } else {
        const data = await res.json();
        console.log("✅ session finalized:", data);
        dlog("✅ session finalized.");
        return true;
      }
    } catch (e) {
      console.error("❌ finalize error:", e);
      dlog("❌ finalize error: " + e.message);
      // Do not throw; we never want to break navigation
      return false;
    }
  }
  
  // === Quick Save Indicator (replaces long processing shimmer) ==============
  function showQuickSaveIndicator() {
    // Prevent duplicate overlays
    const existing = document.getElementById('save-indicator');
    if (existing) return;
    
    const indicator = document.createElement('div');
    indicator.id = 'save-indicator';
    indicator.style.cssText = `
      position: fixed;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
      background: rgba(0, 0, 0, 0.9);
      backdrop-filter: blur(10px);
      padding: 24px 40px;
      border-radius: 16px;
      border: 1px solid rgba(99, 102, 241, 0.3);
      z-index: 9999;
      display: flex;
      align-items: center;
      gap: 16px;
      box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
      animation: fadeIn 0.2s ease-out;
    `;
    
    indicator.innerHTML = `
      <div style="
        width: 24px;
        height: 24px;
        border: 3px solid rgba(99, 102, 241, 0.3);
        border-top-color: #6366f1;
        border-radius: 50%;
        animation: spin 0.8s linear infinite;
      "></div>
      <span style="
        color: white;
        font-size: 16px;
        font-weight: 500;
      ">Saving your recording...</span>
    `;
    
    // Add spin animation
    const style = document.createElement('style');
    style.textContent = `
      @keyframes spin { to { transform: rotate(360deg); } }
      @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
    `;
    document.head.appendChild(style);
    document.body.appendChild(indicator);
  }

  function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

  // === CROWN+ Processing Shimmer UI =====================================
  function showProcessingShimmer() {
    console.log("🎨 Creating processing shimmer overlay...");
    
    // Prevent duplicate overlays
    const existing = document.getElementById('processing-overlay');
    if (existing) {
      console.log("⚠️ Shimmer overlay already exists, skipping creation");
      return;
    }
    
    // Create overlay
    const overlay = document.createElement('div');
    overlay.id = 'processing-overlay';
    overlay.style.cssText = `
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background: rgba(0, 0, 0, 0.85);
      backdrop-filter: blur(10px);
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 9999;
      animation: fadeIn 0.3s ease-out;
    `;

    // Create content container
    const content = document.createElement('div');
    content.style.cssText = `
      text-align: center;
      max-width: 400px;
      padding: 40px;
      background: linear-gradient(135deg, rgba(99, 102, 241, 0.1), rgba(147, 51, 234, 0.1));
      border: 1px solid rgba(99, 102, 241, 0.3);
      border-radius: 16px;
      box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
    `;

    // Title
    const title = document.createElement('h2');
    title.textContent = 'Processing Your Meeting';
    title.style.cssText = `
      font-size: 24px;
      font-weight: 600;
      background: linear-gradient(135deg, #6366f1, #9333ea);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
      margin-bottom: 20px;
    `;

    // Status message
    const status = document.createElement('p');
    status.id = 'processing-status';
    status.textContent = 'Initializing...';
    status.style.cssText = `
      color: #a1a1aa;
      font-size: 14px;
      margin-bottom: 24px;
    `;

    // Progress bar container
    const progressContainer = document.createElement('div');
    progressContainer.style.cssText = `
      width: 100%;
      height: 4px;
      background: rgba(255, 255, 255, 0.1);
      border-radius: 2px;
      overflow: hidden;
    `;

    // Progress bar
    const progressBar = document.createElement('div');
    progressBar.id = 'processing-progress';
    progressBar.style.cssText = `
      width: 0%;
      height: 100%;
      background: linear-gradient(90deg, #6366f1, #9333ea);
      border-radius: 2px;
      transition: width 0.5s ease-out;
      box-shadow: 0 0 10px rgba(99, 102, 241, 0.5);
    `;

    progressContainer.appendChild(progressBar);
    content.appendChild(title);
    content.appendChild(status);
    content.appendChild(progressContainer);
    overlay.appendChild(content);
    document.body.appendChild(overlay);

    // Add CSS animation
    const style = document.createElement('style');
    style.textContent = `
      @keyframes fadeIn {
        from { opacity: 0; }
        to { opacity: 1; }
      }
    `;
    document.head.appendChild(style);
    
    console.log("✅ Processing shimmer overlay added to DOM");
  }

  function updateProcessingState(message, progress) {
    const statusEl = document.getElementById('processing-status');
    const progressEl = document.getElementById('processing-progress');
    
    if (statusEl) statusEl.textContent = message;
    if (progressEl) progressEl.style.width = `${progress}%`;
  }
})();