/**
 * ui.js
 * UI 업데이트 및 표시 관련 함수들
 */

// Loaded fonts cache
const loadedFonts = {};

/**
 * Show message to user
 * @param {string} message - Message to display
 * @param {string} type - Message type: 'info', 'error', 'warning', 'success'
 */
function showMessage(message, type = 'info') {
    const errorMsg = document.getElementById('error_msg');
    const statusText = document.getElementById('status_text');
    const statusIcon = document.getElementById('status_icon');
    
    if (errorMsg) {
        errorMsg.innerText = message;
    }
    
    if (statusText && type === 'error') {
        statusText.innerText = 'ERROR';
    }
    
    if (statusIcon) {
        const colors = {
            'info': 'var(--primary-color)',
            'error': '#d32f2f',
            'warning': '#ff9800',
            'success': '#4caf50'
        };
        statusIcon.style.color = colors[type] || colors['info'];
    }
}

/**
 * Initialize UI event listeners
 */
function initializeUI() {
    // Slider listeners
    document.getElementById('strength').addEventListener('input', e => {
        document.getElementById('strength_val').innerText = e.target.value;
        saveToLocalStorage();
    });
    document.getElementById('guidance_scale').addEventListener('input', e => {
        document.getElementById('guidance_val').innerText = e.target.value;
        saveToLocalStorage();
    });
    
    // Step 3 composition sliders
    document.getElementById('composition_strength').addEventListener('input', e => {
        document.getElementById('composition_strength_val').innerText = e.target.value;
        saveToLocalStorage();
    });
    document.getElementById('composition_steps').addEventListener('input', e => {
        document.getElementById('composition_steps_val').innerText = e.target.value;
        saveToLocalStorage();
    });
    document.getElementById('composition_guidance_scale').addEventListener('input', e => {
        document.getElementById('composition_guidance_val').innerText = e.target.value;
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
    ['bg_prompt', 'bg_negative_prompt', 'bg_composition_prompt', 'bg_composition_negative_prompt', 
     'text_model_prompt', 'negative_prompt', 'seed', 
     'composition_mode', 'text_position', 'composition_prompt', 'composition_negative_prompt'].forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener('input', saveToLocalStorage);
            if (el.tagName === 'SELECT') {
                el.addEventListener('change', saveToLocalStorage);
            }
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
}

/**
 * Update font preview
 */
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
        const fontUrl = `/fonts/${encodeURI(fontPath)}`;
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

/**
 * Encode uploaded image to base64
 */
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

/**
 * Display image in container
 */
function showImage(containerId, b64Data) {
    const container = document.getElementById(containerId);
    container.innerHTML = `<img src="data:image/png;base64,${b64Data}">`;
}

/**
 * Update system metrics display
 */
function updateMetricsDisplay(metrics) {
    const metricsPanel = document.getElementById('metrics_panel');
    metricsPanel.style.display = 'block';
    
    const cpuEl = document.getElementById('cpu_usage');
    const ramEl = document.getElementById('ram_usage');
    
    cpuEl.innerText = metrics.cpu_percent.toFixed(1) + '%';
    ramEl.innerText = `RAM ${metrics.ram_used_gb.toFixed(1)}GB / ${metrics.ram_total_gb.toFixed(1)}GB (${metrics.ram_percent.toFixed(1)}%)`;
    
    // GPU metrics
    const gpuContainer = document.getElementById('gpu_metrics_container');
    if (metrics.gpu_info && metrics.gpu_info.length > 0) {
        gpuContainer.innerHTML = metrics.gpu_info.map((gpu, idx) => {
            return `
            <div>
                <div style="font-size: 11px; color: var(--text-muted); margin-bottom: 3px;">GPU ${idx} - ${gpu.name}</div>
                <div style="font-size: 10px;">${gpu.gpu_util}%</div>
                <div style="font-size: 16px; color: #ff9800; margin-top: 2px;">
                    VRAM: ${gpu.vram_used_gb.toFixed(1)}GB / ${gpu.vram_total_gb.toFixed(1)}GB (${gpu.vram_percent.toFixed(1)}%)
                </div>
            </div>
            `;
        }).join('');
    } else {
        gpuContainer.innerHTML = '<div style="font-size: 12px; color: var(--text-muted);">GPU 정보 없음</div>';
    }
}

/**
 * Update progress bar and status
 */
function updateProgressUI(data) {
    document.getElementById('status_text').innerText = data.status.toUpperCase();
    document.getElementById('progress_info').innerText = data.progress_percent + "%";
    document.getElementById('progress_text').innerText = data.progress_percent + "%";
    document.getElementById('progress_bar').style.width = data.progress_percent + "%";
    document.getElementById('step_info').innerText = data.message || data.current_step;
    
    if (data.sub_step) {
        document.getElementById('sub_step_info').innerText = data.sub_step;
    }
}

/**
 * Reset all UI elements
 */
function resetUI() {
    document.getElementById('status_icon').style.color = '#666';
    document.getElementById('status_text').innerText = "준비됨 (Ready)";
    document.getElementById('progress_info').innerText = "0%";
    document.getElementById('progress_text').innerText = "0%";
    document.getElementById('progress_bar').style.width = "0%";
    document.getElementById('sub_step_info').innerText = "-";
    document.getElementById('eta_info').innerText = "예상 시간: -";
    document.getElementById('step_info').innerText = "단계: -";
    document.getElementById('metrics_panel').style.display = 'none';
    document.getElementById('btn_cancel').style.display = 'none';
    document.getElementById('error_msg').innerText = "";
    document.querySelectorAll('.image-container').forEach(el => el.innerHTML = '<span class="placeholder">대기 중...</span>');
    
    // Reset input image
    document.getElementById('input_image_b64').value = '';
    document.getElementById('input_image_file').value = '';
    document.getElementById('input_preview').style.display = 'none';
}

/**
 * Placeholder for updateUI (can be extended later)
 */
function updateUI() {
    // Can hide/show panels based on start_step selection
    // For now, keep all visible for editing parameters
}
