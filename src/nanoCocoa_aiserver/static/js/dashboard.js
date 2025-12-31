// Store previous results to use as inputs for next steps if needed
let cache = {
    step1_image: null,
    step2_image: null
};
let pollingInterval = null;
let loadedFonts = {}; // Cache for loaded fonts

// --- Initialization ---
document.addEventListener('DOMContentLoaded', () => {
    // Restore from localStorage
    restoreFromLocalStorage();
    
    fetchFonts();

    // Slider listeners
    document.getElementById('strength').addEventListener('input', e => {
        document.getElementById('strength_val').innerText = e.target.value;
        saveToLocalStorage();
    });
    document.getElementById('guidance_scale').addEventListener('input', e => {
        document.getElementById('guidance_val').innerText = e.target.value;
        saveToLocalStorage();
    });
    
    // Font selection listener
    document.getElementById('font_name').addEventListener('change', (e) => {
        updateFontPreview(e.target.value);
        saveToLocalStorage();
    });
    
    // Text content change listener
    document.getElementById('text_content').addEventListener('input', (e) => {
        const preview = document.getElementById('font_preview');
        preview.innerText = e.target.value || 'ABC 가나다';
        saveToLocalStorage();
    });
    
    // Add change listeners for all input fields
    ['bg_prompt', 'bg_negative_prompt', 'text_model_prompt', 'negative_prompt', 'seed'].forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener('input', saveToLocalStorage);
        }
    });
    
    // Radio button listener
    document.querySelectorAll('input[name="start_step"]').forEach(radio => {
        radio.addEventListener('change', saveToLocalStorage);
    });
    
    // Test mode checkbox
    const testModeCheckbox = document.getElementById('test_mode');
    if (testModeCheckbox) {
        testModeCheckbox.addEventListener('change', saveToLocalStorage);
    }
});

async function fetchFonts() {
    try {
        const res = await fetch('/fonts');
        const data = await res.json();
        const select = document.getElementById('font_name');
        if (data.fonts && data.fonts.length > 0) {
            data.fonts.forEach(font => {
                const opt = document.createElement('option');
                opt.value = font;
                opt.innerText = font;
                select.appendChild(opt);
            });
            
            // Restore saved font or use first font
            const saved = localStorage.getItem('ai_ad_font_name');
            if (saved && data.fonts.includes(saved)) {
                select.value = saved;
                updateFontPreview(saved);
            } else if (data.fonts[0]) {
                updateFontPreview(data.fonts[0]);
            }
        }
    } catch (e) { 
        console.error("Font fetch error", e); 
    }
}

function saveToLocalStorage() {
    try {
        const data = {
            start_step: document.querySelector('input[name="start_step"]:checked')?.value || '1',
            test_mode: document.getElementById('test_mode')?.checked || false,
            text_content: document.getElementById('text_content')?.value || '',
            bg_prompt: document.getElementById('bg_prompt')?.value || '',
            bg_negative_prompt: document.getElementById('bg_negative_prompt')?.value || '',
            text_model_prompt: document.getElementById('text_model_prompt')?.value || '',
            negative_prompt: document.getElementById('negative_prompt')?.value || '',
            font_name: document.getElementById('font_name')?.value || '',
            strength: document.getElementById('strength')?.value || '0.6',
            guidance_scale: document.getElementById('guidance_scale')?.value || '3.5',
            seed: document.getElementById('seed')?.value || '',
            input_image_b64: document.getElementById('input_image_b64')?.value || '',
            step1_result: cache.step1_image || null,
            step2_result: cache.step2_image || null
        };
        localStorage.setItem('ai_ad_generator_state', JSON.stringify(data));
    } catch (e) {
        console.error('Failed to save to localStorage:', e);
    }
}

function restoreFromLocalStorage() {
    try {
        const saved = localStorage.getItem('ai_ad_generator_state');
        if (!saved) return;
        
        const data = JSON.parse(saved);
        
        // Restore radio buttons
        if (data.start_step) {
            const radio = document.querySelector(`input[name="start_step"][value="${data.start_step}"]`);
            if (radio) radio.checked = true;
        }
        
        // Restore checkbox
        if (data.test_mode !== undefined) {
            const checkbox = document.getElementById('test_mode');
            if (checkbox) checkbox.checked = data.test_mode;
        }
        
        // Restore text inputs and textareas
        const fields = ['text_content', 'bg_prompt', 'bg_negative_prompt', 'text_model_prompt', 'negative_prompt', 'seed'];
        fields.forEach(id => {
            if (data[id] !== undefined) {
                const el = document.getElementById(id);
                if (el) el.value = data[id];
            }
        });
        
        // Restore sliders
        if (data.strength !== undefined) {
            const el = document.getElementById('strength');
            if (el) {
                el.value = data.strength;
                document.getElementById('strength_val').innerText = data.strength;
            }
        }
        if (data.guidance_scale !== undefined) {
            const el = document.getElementById('guidance_scale');
            if (el) {
                el.value = data.guidance_scale;
                document.getElementById('guidance_val').innerText = data.guidance_scale;
            }
        }
        
        // Restore font (will be set after fetchFonts completes)
        if (data.font_name) {
            localStorage.setItem('ai_ad_font_name', data.font_name);
        }
        
        // Restore input image
        if (data.input_image_b64) {
            document.getElementById('input_image_b64').value = data.input_image_b64;
            const previewBox = document.getElementById('input_preview');
            if (previewBox) {
                previewBox.style.display = 'flex';
                const img = previewBox.querySelector('img');
                if (img) img.src = 'data:image/png;base64,' + data.input_image_b64;
            }
        }
        
        // Restore cached results
        if (data.step1_result) {
            cache.step1_image = data.step1_result;
            showImage('container_step1', data.step1_result);
        }
        if (data.step2_result) {
            cache.step2_image = data.step2_result;
            showImage('container_step2', data.step2_result);
        }
        
    } catch (e) {
        console.error('Failed to restore from localStorage:', e);
    }
}

async function updateFontPreview(fontPath) {
    if (!fontPath) return;
    
    const preview = document.getElementById('font_preview');
    const fontName = fontPath.replace(/[\/\\.]/g, '_'); // Sanitize for CSS
    
    // Check if already loaded
    if (loadedFonts[fontName]) {
        preview.style.fontFamily = `"${fontName}", sans-serif`;
        return;
    }
    
    try {
        // Show loading state
        const originalText = preview.innerText;
        preview.innerText = '로딩 중...';
        
        // Load font using FontFace API
        const fontUrl = `/fonts/${fontPath}`;
        const fontFace = new FontFace(fontName, `url(${fontUrl})`);
        
        await fontFace.load();
        document.fonts.add(fontFace);
        
        // Cache it
        loadedFonts[fontName] = true;
        
        // Apply font
        preview.innerText = originalText;
        preview.style.fontFamily = `"${fontName}", sans-serif`;
        
    } catch (e) {
        console.error("Font loading error:", e);
        preview.innerText = 'ABC 가나다';
        preview.style.fontFamily = 'sans-serif';
    }
}

// --- File Handling ---
function encodeImage(input, targetId) {
    if (input.files && input.files[0]) {
        const reader = new FileReader();
        reader.onload = function (e) {
            const raw = e.target.result.split(',')[1];
            document.getElementById(targetId).value = raw;

            // Preview
            const previewBox = document.getElementById('input_preview');
            previewBox.style.display = 'flex';
            previewBox.querySelector('img').src = e.target.result;
            
            // Save to localStorage
            saveToLocalStorage();
        }
        reader.readAsDataURL(input.files[0]);
    }
}

// --- Logic ---
function updateUI() {
    // Can hide/show panels based on start_step selection
    // For now, keep all visible for editing parameters
}

function resetAll() {
    clearInterval(pollingInterval);
    document.getElementById('status_text').innerText = "준비됨 (Ready)";
    document.getElementById('progress_info').innerText = "0%";
    document.querySelectorAll('.image-container').forEach(el => el.innerHTML = '<span class="placeholder">대기 중...</span>');
    
    // Clear cache and localStorage
    cache.step1_image = null;
    cache.step2_image = null;
    localStorage.removeItem('ai_ad_generator_state');
    localStorage.removeItem('ai_ad_font_name');
}

async function startGeneration() {
    const startStep = parseInt(document.querySelector('input[name="start_step"]:checked').value);
    const isDummy = document.getElementById('test_mode').checked;

    // Build Request
    const req = {
        start_step: startStep,
        test_mode: isDummy,
        text_content: document.getElementById('text_content').value,
        bg_prompt: document.getElementById('bg_prompt').value,
        bg_negative_prompt: document.getElementById('bg_negative_prompt').value,
        text_model_prompt: document.getElementById('text_model_prompt').value,
        negative_prompt: document.getElementById('negative_prompt').value,
        font_name: document.getElementById('font_name').value,
        strength: parseFloat(document.getElementById('strength').value),
        guidance_scale: parseFloat(document.getElementById('guidance_scale').value),
        seed: document.getElementById('seed').value ? parseInt(document.getElementById('seed').value) : null
    };

    // Requirement Checks
    if (startStep === 1) {
        const img = document.getElementById('input_image_b64').value;
        if (!img && !isDummy) {
            alert("1단계는 입력 이미지가 필수입니다!");
            return;
        }
        // For dummy mode, we can send empty if backend handles it, but better to send something if required.
        // If dummy mode and empty, backend might error if it checks existence first.
        // Let's assume user provides image even for dummy, or we send a dummy string if allowed.
        if (img) req.input_image = img;
        else if (isDummy) req.input_image = "DUMMY_IMAGE_DATA";
    }

    // If starting from 2 or 3, we need previous images. 
    // In this dashboard, we can reuse result of previous run if available in `cache`.
    if (startStep >= 2) {
        if (!cache.step1_image && !isDummy) {
            alert("1단계 결과 이미지가 없습니다! 1단계를 먼저 실행해주세요.");
            return;
        }
        req.step1_image = cache.step1_image || "DUMMY_S1";
    }
    if (startStep === 3) {
        if (!cache.step2_image && !isDummy) {
            alert("2단계 결과 이미지가 없습니다! 2단계를 먼저 실행해주세요.");
            return;
        }
        req.step2_image = cache.step2_image || "DUMMY_S2";
    }

    console.log("Sending Request:", req);
    document.getElementById('status_icon').style.color = 'var(--primary-color)';
    document.getElementById('status_text').innerText = "시작 중...";
    document.getElementById('error_msg').innerText = "";

    try {
        const res = await fetch('/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(req)
        });
        const data = await res.json();

        if (res.status === 503) {
            document.getElementById('status_text').innerText = `서버 혼잡. ${data.retry_after}초 후 재시도`;
            return;
        }

        if (data.job_id) {
            pollStatus(data.job_id);
        } else {
            document.getElementById('error_msg').innerText = "작업 시작 실패";
        }

    } catch (e) {
        document.getElementById('error_msg').innerText = "네트워크 오류: " + e.message;
    }
}

function pollStatus(jobId) {
    if (pollingInterval) clearInterval(pollingInterval);

    pollingInterval = setInterval(async () => {
        try {
            const res = await fetch(`/status/${jobId}`);
            if (res.status === 404) {
                clearInterval(pollingInterval);
                return;
            }
            const data = await res.json();

            // Update Status
            document.getElementById('status_text').innerText = data.status.toUpperCase();
            document.getElementById('progress_info').innerText = data.progress_percent + "%";
            document.getElementById('step_info').innerText = data.message || data.current_step;

            // Update Images
            if (data.step1_result) {
                showImage('container_step1', data.step1_result);
                cache.step1_image = data.step1_result;
                saveToLocalStorage();
            }
            if (data.step2_result) {
                showImage('container_step2', data.step2_result);
                cache.step2_image = data.step2_result;
                saveToLocalStorage();
            }
            if (data.final_result) {
                showImage('container_final', data.final_result);
            }

            if (['completed', 'stopped', 'failed'].includes(data.status)) {
                clearInterval(pollingInterval);
            }

        } catch (e) {
            console.error("Polling error", e);
        }
    }, 1000);
}

function showImage(containerId, b64Data) {
    const container = document.getElementById(containerId);
    // Verify if already showing this image to avoid flicker? 
    // Simple replace is fine.
    container.innerHTML = `<img src="data:image/png;base64,${b64Data}">`;
}
