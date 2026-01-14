/**
 * storage.js
 * LocalStorage 관리 모듈
 */

// Global state cache
const appCache = {
    step1_image: null,
    step2_image: null
};

// Step timing history (in seconds)
const stepTimingHistory = {
    step1: [], // Background generation times
    step2: [], // Text generation times
    step3: []  // Composition times
};

/**
 * Save current state to localStorage
 */
function saveToLocalStorage() {
    try {
        const data = {
            start_step: document.querySelector('input[name="start_step"]:checked')?.value || '1',
            test_mode: document.getElementById('test_mode')?.checked || false,
            text_content: document.getElementById('text_content')?.value || '',
            bg_prompt: document.getElementById('bg_prompt')?.value || '',
            bg_negative_prompt: document.getElementById('bg_negative_prompt')?.value || '',
            text_prompt: document.getElementById('text_prompt')?.value || '',
            text_negative_prompt: document.getElementById('text_negative_prompt')?.value || '',
            font_name: document.getElementById('font_name')?.value || '',
            strength: document.getElementById('strength')?.value || '0.6',
            guidance_scale: document.getElementById('guidance_scale')?.value || '3.5',
            seed: document.getElementById('seed')?.value || '',
            input_image_b64: document.getElementById('input_image_b64')?.value || '',
            step1_result: appCache.step1_image || null,
            step2_result: appCache.step2_image || null
        };
        localStorage.setItem('ai_ad_generator_state', JSON.stringify(data));
    } catch (e) {
        console.error('Failed to save to localStorage:', e);
    }
}

/**
 * Restore state from localStorage
 */
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
        const fields = ['text_content', 'bg_prompt', 'bg_negative_prompt', 'text_prompt', 'text_negative_prompt', 'seed'];
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
            appCache.step1_image = data.step1_result;
            showImage('container_step1', data.step1_result);
        }
        if (data.step2_result) {
            appCache.step2_image = data.step2_result;
            showImage('container_step2', data.step2_result);
        }
        
    } catch (e) {
        console.error('Failed to restore from localStorage:', e);
    }
}

/**
 * Clear all stored data
 */
function clearAllStorage() {
    appCache.step1_image = null;
    appCache.step2_image = null;
    localStorage.removeItem('ai_ad_generator_state');
    localStorage.removeItem('ai_ad_font_name');
    localStorage.removeItem('ai_ad_step_timing');
}

/**
 * Load step timing history from localStorage
 */
function loadStepTimingHistory() {
    try {
        const saved = localStorage.getItem('ai_ad_step_timing');
        if (saved) {
            const loaded = JSON.parse(saved);
            Object.assign(stepTimingHistory, loaded);
        }
    } catch (e) {
        console.error('Failed to load timing history:', e);
    }
}

/**
 * Record step execution timing
 */
function recordStepTiming(stepName, duration) {
    try {
        if (stepName.includes('step1')) {
            stepTimingHistory.step1.push(duration);
            if (stepTimingHistory.step1.length > 10) stepTimingHistory.step1.shift();
        } else if (stepName.includes('step2')) {
            stepTimingHistory.step2.push(duration);
            if (stepTimingHistory.step2.length > 10) stepTimingHistory.step2.shift();
        } else if (stepName.includes('step3')) {
            stepTimingHistory.step3.push(duration);
            if (stepTimingHistory.step3.length > 10) stepTimingHistory.step3.shift();
        }
        
        localStorage.setItem('ai_ad_step_timing', JSON.stringify(stepTimingHistory));
    } catch (e) {
        console.error('Failed to record timing:', e);
    }
}

/**
 * Get average execution time for a step
 */
function getAverageStepTime(stepKey) {
    const times = stepTimingHistory[stepKey];
    if (!times || times.length === 0) {
        // Default: 5 minutes per step
        return 300;
    }
    const sum = times.reduce((a, b) => a + b, 0);
    return sum / times.length;
}
