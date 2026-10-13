/**
 * TradePulse — Antigravity Spatial Terminal Engine
 * Powered by GSAP, Canvas Particle Physics, 3D Tilt & NOSIBLE Qwen-0.6B LLM
 */

document.addEventListener("DOMContentLoaded", () => {
  // DOM References
  const tabUrlBtn = document.getElementById("tab-url-btn");
  const tabTextBtn = document.getElementById("tab-text-btn");
  const paneUrl = document.getElementById("pane-url");
  const paneText = document.getElementById("pane-text");

  const inputUrl = document.getElementById("input-article-url");
  const btnClearUrl = document.getElementById("btn-clear-url");
  const btnAnalyzeUrl = document.getElementById("btn-analyze-url");

  const inputText = document.getElementById("input-article-text");
  const btnAnalyzeText = document.getElementById("btn-analyze-text");

  const liveClock = document.getElementById("live-clock");
  const beaconDot = document.getElementById("beacon-dot");
  const deviceTelemetry = document.getElementById("device-telemetry");

  const verdictContainer = document.getElementById("verdict-container");
  const cardVerdict = document.getElementById("card-verdict");
  const verdictTitle = document.getElementById("verdict-title");
  const verdictIcon = document.getElementById("verdict-icon");
  const verdictBadge = document.getElementById("verdict-badge");
  const convictionPct = document.getElementById("conviction-pct");
  const verdictLatency = document.getElementById("verdict-latency");
  const gaugeCircleProgress = document.getElementById("gauge-circle-progress");

  const barBullish = document.getElementById("bar-bullish");
  const barNeutral = document.getElementById("bar-neutral");
  const barBearish = document.getElementById("bar-bearish");
  const valBullish = document.getElementById("val-bullish");
  const valNeutral = document.getElementById("val-neutral");
  const valBearish = document.getElementById("val-bearish");

  const cotStreamText = document.getElementById("cot-stream-text");
  const articleTitleDisplay = document.getElementById("article-title-display");
  const articleUrlLink = document.getElementById("article-url-link");
  const verdictReasoning = document.getElementById("verdict-reasoning");
  const articleSnippetDisplay = document.getElementById("article-snippet-display");
  const snippetContainer = document.getElementById("snippet-container");
  const btnCopyResult = document.getElementById("btn-copy-result");

  let latestAnalysisData = null;

  // ==========================================================================
  // 1. Live Terminal Telemetry Clock
  // ==========================================================================
  function updateClock() {
    const now = new Date();
    const utcHours = String(now.getUTCHours()).padStart(2, '0');
    const utcMinutes = String(now.getUTCMinutes()).padStart(2, '0');
    const utcSeconds = String(now.getUTCSeconds()).padStart(2, '0');
    if (liveClock) {
      liveClock.textContent = `${utcHours}:${utcMinutes}:${utcSeconds} UTC`;
    }
  }
  updateClock();
  setInterval(updateClock, 1000);

  // ==========================================================================
  // 2. Ambient Canvas Star Dust Particles
  // ==========================================================================
  const canvas = document.getElementById("ambient-canvas");
  if (canvas) {
    const ctx = canvas.getContext("2d");
    let width = canvas.width = window.innerWidth;
    let height = canvas.height = window.innerHeight;

    window.addEventListener("resize", () => {
      width = canvas.width = window.innerWidth;
      height = canvas.height = window.innerHeight;
    });

    const particles = [];
    const PARTICLE_COUNT = 45;

    for (let i = 0; i < PARTICLE_COUNT; i++) {
      particles.push({
        x: Math.random() * width,
        y: Math.random() * height,
        vx: (Math.random() - 0.5) * 0.4,
        vy: (Math.random() - 0.5) * 0.4,
        radius: Math.random() * 1.5 + 0.5,
        alpha: Math.random() * 0.5 + 0.2
      });
    }

    function renderParticles() {
      ctx.clearRect(0, 0, width, height);

      for (let i = 0; i < particles.length; i++) {
        const p = particles[i];
        p.x += p.vx;
        p.y += p.vy;

        if (p.x < 0) p.x = width;
        if (p.x > width) p.x = 0;
        if (p.y < 0) p.y = height;
        if (p.y > height) p.y = 0;

        ctx.beginPath();
        ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(0, 229, 255, ${p.alpha})`;
        ctx.fill();

        // Connect nearby nodes
        for (let j = i + 1; j < particles.length; j++) {
          const p2 = particles[j];
          const dx = p.x - p2.x;
          const dy = p.y - p2.y;
          const dist = Math.sqrt(dx * dx + dy * dy);

          if (dist < 110) {
            ctx.beginPath();
            ctx.moveTo(p.x, p.y);
            ctx.lineTo(p2.x, p2.y);
            ctx.strokeStyle = `rgba(0, 229, 255, ${0.12 * (1 - dist / 110)})`;
            ctx.lineWidth = 0.6;
            ctx.stroke();
          }
        }
      }
      requestAnimationFrame(renderParticles);
    }
    renderParticles();
  }

  // ==========================================================================
  // 3. 3D Spatial Tilt Physics
  // ==========================================================================
  const tiltCards = document.querySelectorAll(".floating-card-3d, .card-3d-tilt");

  tiltCards.forEach((card) => {
    card.addEventListener("mousemove", (e) => {
      const rect = card.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;

      const centerX = rect.width / 2;
      const centerY = rect.height / 2;

      const rotateX = ((y - centerY) / centerY) * -5;
      const rotateY = ((x - centerX) / centerX) * 5;

      card.style.transform = `perspective(1200px) rotateX(${rotateX.toFixed(2)}deg) rotateY(${rotateY.toFixed(2)}deg) translateZ(6px)`;
    });

    card.addEventListener("mouseleave", () => {
      card.style.transform = "perspective(1200px) rotateX(0deg) rotateY(0deg) translateZ(0px)";
    });
  });

  // ==========================================================================
  // 4. API Health Check Telemetry
  // ==========================================================================
  async function checkHealth() {
    try {
      const res = await fetch("/api/health");
      if (res.ok) {
        const data = await res.json();
        if (beaconDot) {
          beaconDot.style.backgroundColor = "var(--glow-bullish)";
          beaconDot.style.boxShadow = "0 0 10px var(--glow-bullish)";
        }
        if (deviceTelemetry) {
          deviceTelemetry.textContent = `${data.device} • ${data.device_name || "Active"}`;
        }
      } else {
        if (deviceTelemetry) deviceTelemetry.textContent = "API Initializing...";
      }
    } catch (err) {
      if (deviceTelemetry) deviceTelemetry.textContent = "Connecting...";
    }
  }
  checkHealth();
  setInterval(checkHealth, 25000);

  // ==========================================================================
  // 5. Capsule Tab Navigation
  // ==========================================================================
  tabUrlBtn.addEventListener("click", () => {
    tabUrlBtn.classList.add("active");
    tabUrlBtn.setAttribute("aria-selected", "true");
    tabTextBtn.classList.remove("active");
    tabTextBtn.setAttribute("aria-selected", "false");
    paneUrl.classList.remove("hidden");
    paneText.classList.add("hidden");
    if (window.gsap) {
      gsap.fromTo(paneUrl, { opacity: 0, y: 12 }, { opacity: 1, y: 0, duration: 0.35, ease: "power2.out" });
    }
  });

  tabTextBtn.addEventListener("click", () => {
    tabTextBtn.classList.add("active");
    tabTextBtn.setAttribute("aria-selected", "true");
    tabUrlBtn.classList.remove("active");
    tabUrlBtn.setAttribute("aria-selected", "false");
    paneText.classList.remove("hidden");
    paneUrl.classList.add("hidden");
    if (window.gsap) {
      gsap.fromTo(paneText, { opacity: 0, y: 12 }, { opacity: 1, y: 0, duration: 0.35, ease: "power2.out" });
    }
  });

  // Clear URL input
  if (btnClearUrl) {
    btnClearUrl.addEventListener("click", () => {
      inputUrl.value = "";
      inputUrl.focus();
    });
  }

  // Satellite Preset Chips
  document.querySelectorAll(".satellite-pill").forEach((pill) => {
    pill.addEventListener("click", () => {
      if (pill.dataset.url) {
        inputUrl.value = pill.dataset.url;
        btnAnalyzeUrl.click();
      } else if (pill.dataset.text) {
        inputText.value = pill.dataset.text;
        btnAnalyzeText.click();
      }
    });
  });

  // Keyboard Shortcuts (Ctrl + Enter to trigger)
  window.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      if (!paneUrl.classList.contains("hidden")) {
        btnAnalyzeUrl.click();
      } else {
        btnAnalyzeText.click();
      }
    }
  });

  // Button Loading State
  function setLoading(btn, isLoading) {
    const textEl = btn.querySelector(".btn-content");
    const loader = btn.querySelector(".btn-loader");
    if (isLoading) {
      btn.disabled = true;
      textEl.classList.add("hidden");
      loader.classList.remove("hidden");
    } else {
      btn.disabled = false;
      textEl.classList.remove("hidden");
      loader.classList.add("hidden");
    }
  }

  // ==========================================================================
  // 6. Dynamic Spatial Result Rendering
  // ==========================================================================
  function renderResults(data, isUrlMode) {
    latestAnalysisData = data;
    verdictContainer.classList.remove("hidden");

    const sentiment = (data.sentiment || "NEUTRAL").toUpperCase();
    const conf = Math.round((data.confidence || 0.5) * 100);
    const probs = data.probabilities || { bullish: 0.33, neutral: 0.34, bearish: 0.33 };

    const bullPct = Math.round((probs.bullish || 0) * 100);
    const neutPct = Math.round((probs.neutral || 0) * 100);
    const bearPct = Math.round((probs.bearish || 0) * 100);

    // Apply Verdict Glow Styles
    cardVerdict.classList.remove("verdict-bullish", "verdict-bearish", "verdict-neutral");
    verdictBadge.style.background = "";
    verdictBadge.style.color = "";
    verdictBadge.style.boxShadow = "";

    let ringColor = "#00E5FF";

    if (sentiment === "BULLISH") {
      cardVerdict.classList.add("verdict-bullish");
      verdictTitle.textContent = "BULLISH";
      verdictIcon.textContent = "🟢";
      verdictBadge.style.background = "var(--glow-bullish-bg)";
      verdictBadge.style.color = "var(--glow-bullish)";
      verdictBadge.style.boxShadow = "0 0 28px var(--glow-bullish-halo)";
      ringColor = "#00F59B";
    } else if (sentiment === "BEARISH") {
      cardVerdict.classList.add("verdict-bearish");
      verdictTitle.textContent = "BEARISH";
      verdictIcon.textContent = "🔴";
      verdictBadge.style.background = "var(--glow-bearish-bg)";
      verdictBadge.style.color = "var(--glow-bearish)";
      verdictBadge.style.boxShadow = "0 0 28px var(--glow-bearish-halo)";
      ringColor = "#FF2E63";
    } else {
      cardVerdict.classList.add("verdict-neutral");
      verdictTitle.textContent = "NEUTRAL";
      verdictIcon.textContent = "🟡";
      verdictBadge.style.background = "var(--glow-neutral-bg)";
      verdictBadge.style.color = "var(--glow-neutral)";
      verdictBadge.style.boxShadow = "0 0 28px var(--glow-neutral-halo)";
      ringColor = "#00E5FF";
    }

    // Animate Circular Gauge
    const circumference = 2 * Math.PI * 48; // ~301.6
    const offset = circumference - (conf / 100) * circumference;
    if (gaugeCircleProgress) {
      gaugeCircleProgress.style.stroke = ringColor;
      gaugeCircleProgress.style.strokeDashoffset = offset;
    }

    // Animate Number Counter
    if (window.gsap) {
      const obj = { val: 0 };
      gsap.to(obj, {
        val: conf,
        duration: 0.8,
        ease: "power2.out",
        onUpdate: () => {
          convictionPct.textContent = `${Math.round(obj.val)}%`;
        }
      });
    } else {
      convictionPct.textContent = `${conf}%`;
    }

    verdictLatency.textContent = `⚡ ${data.latency_ms || 120} ms`;

    // Probability Bars
    barBullish.style.width = `${bullPct}%`;
    barNeutral.style.width = `${neutPct}%`;
    barBearish.style.width = `${bearPct}%`;

    valBullish.textContent = `${bullPct}%`;
    valNeutral.textContent = `${neutPct}%`;
    valBearish.textContent = `${bearPct}%`;

    // Chain of Thought Details
    if (cotStreamText) {
      cotStreamText.textContent = data.raw_response || "No Chain-of-Thought scratchpad generated.";
    }

    // Article Metadata
    articleTitleDisplay.textContent = data.title || (isUrlMode ? "Financial News Story" : "Custom Headline Text");
    verdictReasoning.textContent = data.reasoning || "Neural sentiment parsed successfully.";

    if (isUrlMode && data.url) {
      articleUrlLink.href = data.url;
      articleUrlLink.style.display = "inline-flex";
    } else {
      articleUrlLink.style.display = "none";
    }

    if (data.text_snippet) {
      snippetContainer.classList.remove("hidden");
      articleSnippetDisplay.textContent = data.text_snippet;
    } else {
      snippetContainer.classList.add("hidden");
    }

    // Staggered Entrance Animation via GSAP
    if (window.gsap) {
      gsap.fromTo(
        "#card-verdict, .insights-halo-card",
        { opacity: 0, y: 30, scale: 0.97 },
        { opacity: 1, y: 0, scale: 1, duration: 0.6, stagger: 0.15, ease: "power3.out" }
      );
    }

    verdictContainer.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  // ==========================================================================
  // 7. URL Scraping & Inference Handler
  // ==========================================================================
  btnAnalyzeUrl.addEventListener("click", async () => {
    const url = inputUrl.value.trim();
    if (!url || !url.startsWith("http")) {
      alert("Please enter a valid HTTP/HTTPS financial news link.");
      inputUrl.focus();
      return;
    }

    setLoading(btnAnalyzeUrl, true);
    try {
      const response = await fetch("/api/sentiment/url", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url })
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Server returned error (${response.status})`);
      }

      const data = await response.json();
      renderResults(data, true);
    } catch (err) {
      alert(`Scraping / Analysis Error: ${err.message}`);
    } finally {
      setLoading(btnAnalyzeUrl, false);
    }
  });

  // ==========================================================================
  // 8. Raw Text Inference Handler
  // ==========================================================================
  btnAnalyzeText.addEventListener("click", async () => {
    const text = inputText.value.trim();
    if (!text) {
      alert("Please enter a financial headline or market notice.");
      inputText.focus();
      return;
    }

    setLoading(btnAnalyzeText, true);
    try {
      const response = await fetch("/api/sentiment/text", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text })
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Server returned error (${response.status})`);
      }

      const data = await response.json();
      renderResults(data, false);
    } catch (err) {
      alert(`Inference Error: ${err.message}`);
    } finally {
      setLoading(btnAnalyzeText, false);
    }
  });

  // ==========================================================================
  // 9. Copy Result to Clipboard
  // ==========================================================================
  if (btnCopyResult) {
    btnCopyResult.addEventListener("click", () => {
      if (!latestAnalysisData) return;
      const copyText = `TradePulse Spatial Analysis:\nVerdict: ${latestAnalysisData.sentiment} (${Math.round((latestAnalysisData.confidence || 0) * 100)}% Conviction)\nLatency: ${latestAnalysisData.latency_ms}ms\nModel: ${latestAnalysisData.model}\nReasoning: ${latestAnalysisData.reasoning}`;
      
      navigator.clipboard.writeText(copyText).then(() => {
        const originalHtml = btnCopyResult.innerHTML;
        btnCopyResult.innerHTML = `<span>✓ Signal Copied</span>`;
        setTimeout(() => {
          btnCopyResult.innerHTML = originalHtml;
        }, 2200);
      });
    });
  }
});
