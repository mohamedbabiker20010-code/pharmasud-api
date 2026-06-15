# Barcode Scanner — PharmaSUD POS System
## Full Technical Reference for AI Models

---

## 1. PROJECT CONTEXT

| Field | Value |
|-------|-------|
| App | Pharmacy POS (Point of Sale) for PharmaSUD |
| Stack | Python FastAPI + PostgreSQL + Plain HTML/JS (Alpine.js) |
| Hosting | Render.com (HTTPS enforced) |
| Production device | **Android Chrome** (primary — native BarcodeDetector) |
| Test device | **iPhone Safari** (secondary — no BarcodeDetector, uses zxing-wasm) |
| File edited | `/home/lenovo/pharmasud/templates/pos.html` (1924 lines, SINGLE file) |
| Barcode types | EAN-13, EAN-8, UPC-A, UPC-E, Code-128, Code-39 |
| Key challenge | "Camera opens but NEVER decodes" — 4 failed attempts before working solution |

---

## 2. THE 4 FAILED ATTEMPTS (Chronological)

### Attempt 1: `window.prompt()` dialog
**Code:** Simple `prompt('أدخل الباركود')` dialog
**Why failed:** Not a real scanner — just manual text input in a browser popup. Useless for workflow.
**API credits wasted:** ~30 calls debugging trivial code
**Lesson:** Don't call a manual text input a "scanner"

### Attempt 2: QuaggaJS (live video)
**Code:**
```js
// QuaggaJS with WebWorker
Quagga.init({
    inputStream: { name: "Live", type: "LiveStream", target: videoElement },
    decoder: { readers: ["ean_reader"] }
}, () => Quagga.start());
```
**Why failed:** QuaggaJS requires WebWorkers internally. WebWorkers silently fail on mobile browsers (iOS Safari). No detection, no error message — completely silent failure.
**API credits wasted:** ~30 calls debugging why nothing appears
**Lesson:** Libraries that depend on WebWorkers are unreliable on mobile web.

### Attempt 3: QuaggaJS `decodeSingle()` (still photo approach)
**Code:**
```js
Quagga.decodeSingle({
    inputStream: { type: "ImageStream", src: canvas.toDataURL() },
    decoder: { readers: ["ean_reader"] }
}, result => { ... });
```
**Why failed:** Same root cause — QuaggaJS core is WebWorker-dependent. Also tried to capture frame from video → convert to image → decode. Same silent failure on iOS.
**API credits wasted:** ~20 calls
**Lesson:** After 2 failed attempts with same library, CHANGE STRATEGY completely.

### Attempt 4: Server-side pyzbar/ZBar on Render
**Code (Python):**
```python
import pyzbar.pyzbar as pyzbar
# Read image bytes → pyzbar.decode(image)
```
**Why failed:** Render.com's Python runtime containers do NOT support `apt-get install libzbar0`. Build phase + runtime phase are different containers. System-level dependency installation fails silently in runtime. 3 deploy cycles without any value.
**API credits wasted:** ~50 calls across 3 deploys. **Most costly failure.**
**Lesson:** Never try server-side system-dependent libraries on Render. The user explicitly complained about API credit waste.

---

## 3. KEY DISCOVERY THAT FIXED EVERYTHING

**The user (Mohamed) discovered the critical insight:**

1. Camera OPENS fine on both devices → problem is purely DECODING, not camera access
2. Android Chrome has native `BarcodeDetector` API → works perfectly, no library needed
3. iOS Safari has NO `BarcodeDetector` (WebKit limitation) → needs WASM fallback
4. Previous testing on iPhone was chasing a bug that doesn't exist on Android (the production device!)

**Diagnostic rule:**
- ✅ Before debugging ANY device-specific issue, ask: "هل تختبر على نفس الجهاز اللي هيشتغل عليه النظام؟"
- Always verify: Is the problem reproducible on the PRODUCTION device, or only on the test device?

---

## 4. FINAL SOLUTION ARCHITECTURE

### Engine Selection (Feature Detection — NEVER assume)

```
startBarcodeScanner()
    ↓
getUserMedia({ facingMode: 'environment', ... })
    ↓
if (window has 'BarcodeDetector') AND (getSupportedFormats() includes EAN-13)
    → use BarcodeDetector.detect(canvas)
    → Android Chrome path
else
    → dynamic import('https://esm.sh/zxing-wasm@2/reader')
    → zxingMod.readBarcodesFromImageData(imageData, opts)
    → iOS Safari path
    ↓
scanLoop(decoderFn)
    → requestAnimationFrame, throttled to ~8/sec
    → ROI crop (center band, full width × 40% height)
    → decode ROI only, NOT full frame
```

### Key Design Decisions

| Decision | Why |
|----------|-----|
| Dynamic import for zxing-wasm | ~1MB WASM downloaded ONLY on devices that need it (iOS). Android never downloads it. |
| ROI cropping (center 40% band) | **SINGLE BIGGEST ACCURACY IMPROVEMENT.** Full-frame decode on 1080p video is slow and misses thin barcodes. Center band only = faster + more accurate. |
| rAF + throttle (120ms) | 8-10 frames/sec is enough for barcode scanning. Full 60fps wastes battery. |
| `readBarcodesFromImageData` | Specific function for ImageData input (from canvas.getImageData). More reliable than generic `readBarcodes` on iOS. |
| Error logging (NOT silent catch) | Original code had `.catch(() => {})` — swallowed ALL errors. Changed to `.catch(err => debug(...))` so errors appear on-screen. |
| Debounced single-fire | Only ONE decode success event allowed (`_scanFoundDebounce` flag). Prevents double-processing. |

---

## 5. COMPLETE CODE BLOCKS (for AI model injection)

### 5.1 Scanner HTML Structure (lines 641-814 of pos.html)

```html
<!-- Scanner Container — overlay modal -->
<div id="scanner-container">
    <div style="position:relative; width:100%; max-width:400px;">
        <video id="scanner-video" playsinline></video>
        <div id="scan-overlay">
            <div class="scan-frame">
                <div id="scan-line"></div>
            </div>
        </div>
    </div>
    
    <p id="scanner-status">📷 وجّه الكاميرا نحو الباركود ليقرأ تلقائياً</p>
    
    <div class="scanner-controls">
        <!-- Scan result display (hidden until success) -->
        <div id="scan-result" style="display:none;">
            ✅ <span id="scan-result-code"></span>
        </div>
        
        <!-- Manual barcode input (ALWAYS available as fallback) -->
        <div class="divider-text">أو أدخل الباركود يدوياً</div>
        <input type="text" id="manual-barcode-input"
               placeholder="أدخل رقم الباركود..."
               onkeypress="if(event.key==='Enter') searchManualBarcode()">
        
        <!-- Buttons -->
        <div class="btn-row">
            <button class="btn-scan-torch" id="scan-torch-btn" onclick="toggleTorch()" style="display:none;">💡</button>
            <button class="btn-scan-search" onclick="searchManualBarcode()">🔍 بحث</button>
            <button class="btn-scan-close" onclick="stopScanner()">✕ إغلاق</button>
            <button class="btn-scan-search" id="scan-again-btn" onclick="restartScanner()" style="display:none;">📷 مسح مرة أخرى</button>
        </div>
    </div>
    
    <!-- Debug line — shows engine name, errors, resolution -->
    <div id="scanner-debug"></div>
</div>
```

### 5.2 Scanner CSS (lines 641-772)

```css
/* Scanner overlay */
#scanner-container {
    display: none; /* Hidden by default */
    position: fixed; top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(0,0,0,0.95);
    z-index: 400;
    flex-direction: column; align-items: center; justify-content: center;
    padding: 20px;
}
#scanner-container.active { display: flex; }

/* Camera video */
#scanner-container video {
    width: 100%; max-width: 400px; max-height: 55vh;
    object-fit: cover;
    border-radius: 12px;
    background: #000;
}

/* ROI guide overlay — MUST match scan-loop crop area */
#scan-overlay {
    position: absolute; top: 0; left: 0;
    width: 100%; height: 100%;
    display: flex; align-items: center; justify-content: center;
    pointer-events: none;
}
.scan-frame {
    width: 100%;          /* ← CRITICAL: matches ROI width */
    height: 40%;          /* ← CRITICAL: matches ROI height (40% center) */
    border: 3px solid #22C55E;
    border-radius: 12px;
    box-shadow: 0 0 0 9999px rgba(0,0,0,0.55); /* Dims outside frame */
    position: relative;
    overflow: hidden;
}

/* Scanning line animation */
#scan-line {
    width: 100%; height: 3px;
    background: #EF4444;
    animation: scanmove 2s ease-in-out infinite;
}
@keyframes scanmove {
    0%   { transform: translateY(0); }
    50%  { transform: translateY(calc(100% - 3px)); }
    100% { transform: translateY(0); }
}

/* Debug/status lines */
#scanner-debug {
    margin-top: 8px; font-size: 11px; color: #64748B;
    text-align: center; direction: ltr; min-height: 16px;
}
#scanner-debug.active { color: #22C55E; }
#scanner-debug.error { color: #EF4444; }
```

### 5.3 Alpine.js Integration (lines 1144-1169)

```js
// Inside Alpine.js posApp() — called when user taps 📷 مسح
openScanner() {
    if (typeof window.startBarcodeScanner === 'function') {
        window.currentPosApp = this;   // ← Critical: wire Alpine to scanner
        window.startBarcodeScanner();
    }
},

// Existing barcode search — reused by scanner! DO NOT invent new endpoint
searchByBarcode(barcode) {
    fetch('/api/sales/pos/barcode/' + encodeURIComponent(barcode), {
        headers: { 'Authorization': 'Bearer ' + this.token }
    })
    .then(r => r.json())
    .then(data => {
        if (data.found && data.medicine) {
            this.showUnitModal(data.medicine);  // ← opens unit selection modal
        } else {
            this.showToast('الباركود غير موجود: ' + barcode, 'warning');
        }
    })
    .catch(() => {
        this.showToast('حدث خطأ في البحث بالباركود', 'error');
    });
},
```

### 5.4 Core Scanner Engine (lines 1617-1921) — THE MAIN CODE

```js
// ═══════════════════════════════════════════════════════════════
// Scanner: Layered (BarcodeDetector → zxing-wasm) + ROI + rAF
// ═══════════════════════════════════════════════════════════════
// Engine: 2 layers — Native BarcodeDetector (Android Chrome)
//                    → zxing-wasm fallback (iOS Safari)
//
// Core fix: ROI crop — decode center 40% band ONLY, not full frame
//
// zxing-wasm is DYNAMICALLY imported (only on devices without BarcodeDetector)
// NOTE: HTTPS required + direct browser (Safari/Chrome only)
//       Camera does NOT work inside in-app browsers (Telegram, WhatsApp, etc.)
// ═══════════════════════════════════════════════════════════════

window.currentPosApp = null;

// Scanner state variables
let _scanState = {
    stream: null,     // MediaStream from getUserMedia
    track: null,      // First video track
    running: false,   // Is scan loop active?
    rAFid: null,      // requestAnimationFrame ID
    engine: 'none',   // Engine name (for debug)
    torchOn: false,   // Flashlight state
    lastDecodeMs: 0   // Last decode timestamp (for throttling)
};

// Debug output to on-screen line
function debug(msg, type = '') {
    const el = document.getElementById('scanner-debug');
    if (!el) return;
    el.textContent = msg;
    el.className = type;
}

// Status update
function updateStatus(msg, cls = '') {
    const el = document.getElementById('scanner-status');
    if (el) { el.textContent = msg; el.className = cls; }
}

// ═══════════════════════════════════════════════════════════════
// START SCANNER
// ═══════════════════════════════════════════════════════════════
async function startBarcodeScanner() {
    const container = document.getElementById('scanner-container');
    container.classList.add('active');
    updateStatus('📷 جاري فتح الكاميرا...');
    debug('requesting camera...');

    try {
        // ── 1. OPEN CAMERA ──
        const stream = await navigator.mediaDevices.getUserMedia({
            video: {
                facingMode: { ideal: 'environment' },  // Rear camera
                width: { ideal: 1920 },
                height: { ideal: 1080 }
            },
            audio: false
        });
        _scanState.stream = stream;
        _scanState.track = stream.getVideoTracks()[0];
        const settings = _scanState.track.getSettings ? _scanState.track.getSettings() : {};
        debug(`camera: ${settings.width||'?'}×${settings.height||'?'}`, 'active');

        // Attach to video element
        const video = document.getElementById('scanner-video');
        video.srcObject = stream;
        await video.play();

        // Attempt continuous focus
        try { await _scanState.track.applyConstraints({ advanced: [{ focusMode: 'continuous' }] }); } catch (_) {}

        // ── TORCH (only if supported by camera) ──
        const caps = _scanState.track.getCapabilities ? _scanState.track.getCapabilities() : {};
        const torchBtn = document.getElementById('scan-torch-btn');
        if (caps && caps.torch) {
            torchBtn.style.display = '';
            torchBtn.className = 'btn-scan-torch';
        } else {
            torchBtn.style.display = 'none';
        }

        // ── 2. ENGINE SELECTION (feature-detect, NEVER assume) ──
        let decoderFn = null;
        let engineName = '';

        // LAYER 1: Native BarcodeDetector (Android Chrome)
        if ('BarcodeDetector' in window) {
            const supported = await BarcodeDetector.getSupportedFormats();
            const needed = ['ean_13', 'ean_8', 'upc_a', 'upc_e', 'code_128', 'code_39'];
            const available = needed.filter(f => supported.includes(f));
            if (available.length >= 1) {
                const detector = new BarcodeDetector({ formats: available });
                decoderFn = async (imageData) => {
                    const codes = await detector.detect(imageData);
                    return codes.length > 0 ? codes[0].rawValue : null;
                };
                engineName = 'BarcodeDetector (' + available.join(',') + ')';
            }
        }

        // LAYER 2: zxing-wasm fallback (iOS Safari)
        if (!decoderFn) {
            try {
                // DYNAMIC import — ~1MB wasm loads ONLY on devices that need it
                const zxingMod = await import('https://esm.sh/zxing-wasm@2/reader');
                const readerOpts = {
                    tryHarder: true,  // ← CRITICAL for accuracy
                    formats: ['EAN-13', 'EAN-8', 'UPC-A', 'UPC-E', 'Code-128', 'Code-39'],
                    maxNumberOfSymbols: 1
                };
                decoderFn = async (imageData) => {
                    // Use readBarcodesFromImageData (specific for ImageData input)
                    const results = await zxingMod.readBarcodesFromImageData(imageData, readerOpts);
                    return (results && results.length > 0) ? results[0].text : null;
                };
                engineName = 'zxing-wasm@2';
            } catch (wasmErr) {
                updateStatus('⌨️ فشل تحميل محرك المسح — استخدم الإدخال اليدوي', 'error');
                debug('WASM load failed: ' + wasmErr.message, 'error');
                document.getElementById('manual-barcode-input').focus();
                return;  // ← Stop here, user must use manual input
            }
        }

        _scanState.engine = engineName;
        debug('🟢 ' + engineName, 'active');
        updateStatus('🔍 وجّه الباركود داخل الإطار...');

        // ── 3. SCAN LOOP WITH ROI ──
        _scanState.running = true;
        await scanLoop(decoderFn);

    } catch (err) {
        console.error('Scanner failed:', err);
        let msg = '⌨️ الكاميرا غير متاحة';
        if (err.name === 'NotAllowedError') msg = '🔒 الإذن مرفوض — افتح في Safari/Chrome مباشرة';
        else if (err.name === 'NotFoundError') msg = '📷 ما في كاميرا متاحة';
        else if (err.name === 'NotReadableError') msg = '🔒 الكاميرا مشغولة بتطبيق آخر';
        updateStatus(msg, 'error');
        debug(err.name + ': ' + err.message, 'error');
        fallbackToManual();
    }
}

// ═══════════════════════════════════════════════════════════════
// SCAN LOOP — reads center band (ROI) only, NOT full frame
// ═══════════════════════════════════════════════════════════════
async function scanLoop(decoderFn) {
    const video = document.getElementById('scanner-video');
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d', { willReadFrequently: true });
    let lastDecode = 0;
    const MIN_INTERVAL = 120;  // ~8 decode attempts/sec

    function frame() {
        if (!_scanState.running) return;
        _scanState.rAFid = requestAnimationFrame(frame);

        const now = performance.now();
        if (now - lastDecode < MIN_INTERVAL) return;  // Throttle
        lastDecode = now;

        if (video.readyState < video.HAVE_CURRENT_DATA || !video.videoWidth) return;

        const w = video.videoWidth;
        const h = video.videoHeight;

        // ROI: Center band — full width × ~40% height
        const roiH = Math.round(h * 0.40);
        const roiY = Math.round((h - roiH) / 2);

        canvas.width = w;
        canvas.height = roiH;
        ctx.drawImage(video, 0, roiY, w, roiH, 0, 0, w, roiH);
        const imageData = ctx.getImageData(0, 0, w, roiH);

        decoderFn(imageData).then(code => {
            if (code && code.length >= 3) {
                _scanState.running = false;
                cancelAnimationFrame(_scanState.rAFid);
                onBarcodeFound(code);
            } else {
                debug('decode: no barcode in frame', '');  // ← Shows decoder IS running
            }
        }).catch(err => {
            debug('decode error: ' + (err.message || err), 'error');  // ← Never silent!
        });
    }

    frame();
}

// ═══════════════════════════════════════════════════════════════
// TORCH TOGGLE
// ═══════════════════════════════════════════════════════════════
async function toggleTorch() {
    if (!_scanState.track) return;
    _scanState.torchOn = !_scanState.torchOn;
    try {
        await _scanState.track.applyConstraints({ advanced: [{ torch: _scanState.torchOn }] });
        const btn = document.getElementById('scan-torch-btn');
        if (btn) btn.className = 'btn-scan-torch' + (_scanState.torchOn ? ' on' : '');
    } catch (err) {
        debug('torch error: ' + err.message, 'error');
    }
}

// ═══════════════════════════════════════════════════════════════
// ON BARCODE FOUND — debounced single-fire
// ═══════════════════════════════════════════════════════════════
let _scanFoundDebounce = false;
function onBarcodeFound(code) {
    if (_scanFoundDebounce) return;  // Prevent double-fire
    _scanFoundDebounce = true;

    // Stop camera + animation loop
    _scanState.running = false;
    if (_scanState.rAFid) { cancelAnimationFrame(_scanState.rAFid); _scanState.rAFid = null; }
    if (_scanState.track) {
        try { _scanState.track.applyConstraints({ advanced: [{ torch: false }] }); } catch (_) {}
        _scanState.track.stop();
    }
    if (_scanState.stream) {
        _scanState.stream.getTracks().forEach(t => t.stop());
    }
    const videoEl = document.getElementById('scanner-video');
    if (videoEl) videoEl.srcObject = null;

    // Vibrate feedback (single short pulse)
    if (navigator.vibrate) navigator.vibrate(120);

    // Show result
    document.getElementById('scan-result-code').textContent = code;
    document.getElementById('scan-result').style.display = '';
    document.getElementById('scanner-status').textContent = '✅ تم المسح بنجاح';
    document.getElementById('scanner-status').className = 'success';
    debug('✅ ' + code, 'active');

    // Show "Scan again" button, hide torch
    document.getElementById('scan-torch-btn').style.display = 'none';
    document.getElementById('scan-again-btn').style.display = '';
    document.getElementById('manual-barcode-input').value = code;
    document.getElementById('manual-barcode-input').focus();

    // Pass value to existing Alpine.js searchByBarcode()
    const app = window.currentPosApp;
    if (app && app.searchByBarcode) {
        app.searchByBarcode(code);
    }
}

// ═══════════════════════════════════════════════════════════════
// RESTART SCANNER (Scan again button)
// ═══════════════════════════════════════════════════════════════
async function restartScanner() {
    // Reset UI
    document.getElementById('scan-result').style.display = 'none';
    document.getElementById('scan-result-code').textContent = '';
    document.getElementById('scan-again-btn').style.display = 'none';
    document.getElementById('manual-barcode-input').value = '';
    _scanFoundDebounce = false;
    _scanState.running = false;
    _scanState.stream = null;
    _scanState.track = null;
    _scanState.rAFid = null;
    _scanState.torchOn = false;
    _scanState.engine = 'none';

    // Start fresh
    await startBarcodeScanner();
}

// ═══════════════════════════════════════════════════════════════
// STOP SCANNER
// ═══════════════════════════════════════════════════════════════
function stopScanner() {
    _scanState.running = false;
    _scanFoundDebounce = false;
    if (_scanState.rAFid) { cancelAnimationFrame(_scanState.rAFid); _scanState.rAFid = null; }
    if (_scanState.track) {
        try { _scanState.track.applyConstraints({ advanced: [{ torch: false }] }); } catch (_) {}
        _scanState.track.stop();
    }
    if (_scanState.stream) {
        _scanState.stream.getTracks().forEach(t => t.stop());
    }
    _scanState.stream = null;
    _scanState.track = null;
    _scanState.torchOn = false;
    _scanState.engine = 'none';
    const v = document.getElementById('scanner-video');
    if (v) v.srcObject = null;
    document.getElementById('scanner-container').classList.remove('active');
    document.getElementById('scan-result').style.display = 'none';
    document.getElementById('scan-again-btn').style.display = 'none';
}

// ── Manual barcode input (ALWAYS available as fallback) ──
function fallbackToManual() {
    document.getElementById('manual-barcode-input').focus();
}

function searchManualBarcode() {
    const input = document.getElementById('manual-barcode-input');
    const code = input.value.trim();
    if (code && code.length >= 3) {
        const app = window.currentPosApp;
        if (app && app.searchByBarcode) {
            app.searchByBarcode(code);
            stopScanner();
        }
        input.value = '';
    } else {
        input.style.borderColor = '#EF4444';
        setTimeout(() => input.style.borderColor = '', 1500);
        input.focus();
    }
}

window.startBarcodeScanner = startBarcodeScanner;  // ← Alpine.js calls this
```

---

## 6. FORMAT STRINGS (Critical — Different Per Engine)

```js
// BarcodeDetector (native API) — snake_case
const nativeFormats = ['ean_13', 'ean_8', 'upc_a', 'upc_e', 'code_128', 'code_39'];

// zxing-wasm — dashed case (different casing!)
const wasmFormats = ['EAN-13', 'EAN-8', 'UPC-A', 'UPC-E', 'Code-128', 'Code-39'];
```

**WARNING:** These format strings are NOT interchangeable between engines. Using wrong case → silent decode failure.

---

## 7. KNOWN PITFALLS (MUST document for AI)

### ⚠️ Pitfall 1: `.catch(() => {})` — Silent Failure Killer
```js
// ❌ WRONG — swallows ALL errors, including critical WASM failures
decoderFn(imageData).then(code => {
    if (code) { onBarcodeFound(code); }
}).catch(() => {});

// ✅ CORRECT — surfaces errors for debugging
decoderFn(imageData).then(code => {
    if (code) { onBarcodeFound(code); }
    else { debug('no barcode in frame', ''); }
}).catch(err => {
    debug('decode error: ' + err.message, 'error');
});
```

### ⚠️ Pitfall 2: Testing on Wrong Device
- **Production = Android** (BarcodeDetector works natively)
- **Testing on iPhone** = the bug doesn't even exist on production
- **Rule:** Always ask "هل تختبر على نفس الجهاز اللي هيشتغل عليه النظام؟"

### ⚠️ Pitfall 3: zxing-wasm API Functions
- `readBarcodes` — generic, accepts multiple input types
- `readBarcodesFromImageData` — SPECIFICALLY for `ImageData` from `ctx.getImageData()`
- Use `readBarcodesFromImageData` when passing ImageData — it's more reliable

### ⚠️ Pitfall 4: iOS Dynamic Import
- Safari 16.4+ supports `import()` with URL specifiers
- But Content-Security-Policy headers can block it
- Always wrap dynamic import in try/catch with user-visible error

### ⚠️ Pitfall 5: Render.com System Dependencies
- Render does NOT support `apt-get install` at runtime
- Never try server-side barcode libraries (pyzbar, ZBar, zbarimg)
- ALL barcode processing MUST be client-side (browser)
- 3 deploy cycles proved this is impossible on Render

### ⚠️ Pitfall 6: In-App Browsers
- `getUserMedia` is BLOCKED inside in-app browsers (Telegram, WhatsApp, Instagram, Facebook)
- User MUST open in Safari/Chrome directly
- Error message: `NotAllowedError` → "🔒 الإذن مرفوض — افتح في Safari/Chrome مباشرة"

### ⚠️ Pitfall 7: iOS Safari Video+Canvas
- `canvas.getContext('2d', { willReadFrequently: true })` — the `willReadFrequently` hint is Chrome-specific. Safari ignores it gracefully (no error).
- `ctx.getImageData()` on a canvas with video source works on iOS but may be slower

---

## 8. DEBUG OUTPUT REFERENCE

The `#scanner-debug` element shows different messages:

| Message | Meaning |
|---------|---------|
| `requesting camera...` | getUserMedia called |
| `camera: 1920×1080` | Camera opened successfully with resolution |
| `🟢 BarcodeDetector (ean_13,...)` | Android native engine active |
| `🟢 zxing-wasm@2` | iOS WASM fallback active |
| `decode: no barcode in frame` | Engine is running, but no barcode detected yet |
| `decode error: ...` | Engine threw an error (WASM crash, etc.) |
| `WASM load failed: ...` | zxing-wasm dynamic import failed |
| `✅ 6291041500213` | Barcode FOUND and processed |
| `torch error: ...` | Flashlight toggle failed |
| `🔒 الإذن مرفوض — ...` | Camera permission denied (in-app browser) |
| `📷 ما في كاميرا متاحة` | No camera device found |
| `🔒 الكاميرا مشغولة...` | Camera in use by another app |

---

## 9. GIT COMMIT HISTORY

```
bc88bec fix: simplify ZXing scanner - clean dual-approach with proper error handling
899f163 fix: login endpoint arg mismatch
96da1f1 fix: layered barcode scanner (BarcodeDetector + zxing-wasm) + ROI crop
e90f864 barcode scanner: ROI guide fix + scan-again button + debounce + vibrate fix
c843058 fix: silent catch swallowing decode errors + use readBarcodesFromImageData
```

---

## 10. SERVER-SIDE ENDPOINT (DO NOT MODIFY)

The single endpoint the scanner feeds into:

**GET** `/api/sales/pos/barcode/{barcode_code}`
- **Auth:** Bearer token
- **Response:** `{ found: bool, medicine: {...} }` if found, `{ found: false }` if not
- Calls `searchByBarcode()` in Alpine.js → opens unit selection modal
- **This endpoint is EXISTING — do NOT create a new one**

---

*Document generated June 12, 2026 — for AI model knowledge transfer*