/**
 * api.js
 * API 호출 및 작업 관리
 */

let currentJobId = null;
let jobStartTime = null;
let pollingInterval = null;

/**
 * Fetch available fonts from server
 */
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

/**
 * Reset all state and cancel current job
 */
async function resetAll() {
    // Cancel current job if running
    if (currentJobId) {
        await cancelJob();
    }

    clearInterval(pollingInterval);
    pollingInterval = null;
    currentJobId = null;
    jobStartTime = null;

    resetUI();
    clearAllStorage();
}

/**
 * Cancel current running job
 */
async function cancelJob() {
    if (!currentJobId) return;

    try {
        const res = await fetch(`/stop/${currentJobId}`, { method: 'POST' });
        const data = await res.json();

        if (data.status === 'stopped') {
            document.getElementById('status_text').innerText = '작업 취소됨';
            document.getElementById('status_icon').style.color = '#ff9800';
            document.getElementById('error_msg').innerText = '사용자가 작업을 취소했습니다.';
        }
    } catch (e) {
        console.error('Cancel job error:', e);
        document.getElementById('error_msg').innerText = '작업 취소 실패: ' + e.message;
    } finally {
        clearInterval(pollingInterval);
        pollingInterval = null;
        currentJobId = null;
        jobStartTime = null;
        document.getElementById('btn_cancel').style.display = 'none';
    }
}

/**
 * Start generation process
 */
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
        bg_composition_prompt: document.getElementById('bg_composition_prompt')?.value || null,
        bg_composition_negative_prompt: document.getElementById('bg_composition_negative_prompt')?.value || null,
        text_model_prompt: document.getElementById('text_model_prompt').value,
        negative_prompt: document.getElementById('negative_prompt').value,
        font_name: document.getElementById('font_name').value,
        strength: parseFloat(document.getElementById('strength').value),
        guidance_scale: parseFloat(document.getElementById('guidance_scale').value),
        seed: document.getElementById('seed').value ? parseInt(document.getElementById('seed').value) : null,
        // Step 3 텍스트 합성 파라미터
        composition_mode: document.getElementById('composition_mode').value,
        text_position: document.getElementById('text_position').value,
        composition_prompt: document.getElementById('composition_prompt')?.value || null,
        composition_negative_prompt: document.getElementById('composition_negative_prompt')?.value || null,
        composition_strength: parseFloat(document.getElementById('composition_strength').value),
        composition_steps: parseInt(document.getElementById('composition_steps').value),
        composition_guidance_scale: parseFloat(document.getElementById('composition_guidance_scale').value)
    };

    // Requirement Checks
    if (startStep === 1) {
        const img = document.getElementById('input_image_b64').value;
        if (isDummy) req.input_image = "DUMMY_IMAGE_DATA";
        else if (img)
            req.input_image = img;
        else
            req.input_image = null;
    }

    if (startStep >= 2) {
        if (!appCache.step1_image && !isDummy) {
            alert("1단계 결과 이미지가 없습니다! 1단계를 먼저 실행해주세요.");
            return;
        }
        req.step1_image = appCache.step1_image || "DUMMY_S1";
    }
    if (startStep === 3) {
        if (!appCache.step2_image && !isDummy) {
            alert("2단계 결과 이미지가 없습니다! 2단계를 먼저 실행해주세요.");
            return;
        }
        req.step2_image = appCache.step2_image || "DUMMY_S2";
    }

    console.log("Sending Request:", req);
    document.getElementById('status_icon').style.color = 'var(--primary-color)';
    document.getElementById('status_text').innerText = "시작 중...";
    document.getElementById('error_msg').innerText = "";
    document.getElementById('btn_cancel').style.display = 'inline-block';

    try {
        const res = await fetch('/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(req)
        });
        const data = await res.json();

        if (res.status === 503) {
            document.getElementById('status_text').innerText = `서버 혼잡. ${data.retry_after}초 후 재시도`;
            document.getElementById('btn_cancel').style.display = 'none';
            return;
        }

        if (data.job_id) {
            currentJobId = data.job_id;
            jobStartTime = Date.now();
            loadStepTimingHistory();
            pollStatus(data.job_id, startStep);
        } else {
            document.getElementById('error_msg').innerText = "작업 시작 실패";
            document.getElementById('btn_cancel').style.display = 'none';
        }

    } catch (e) {
        document.getElementById('error_msg').innerText = "네트워크 오류: " + e.message;
        document.getElementById('btn_cancel').style.display = 'none';
    }
}

/**
 * Poll job status
 */
function pollStatus(jobId, startStep) {
    if (pollingInterval) clearInterval(pollingInterval);

    let lastStep = null;
    let stepStartTime = Date.now();

    pollingInterval = setInterval(async () => {
        try {
            const res = await fetch(`/status/${jobId}`);
            if (res.status === 404) {
                clearInterval(pollingInterval);
                return;
            }
            const data = await res.json();

            // Track step changes for timing
            if (data.current_step && data.current_step !== lastStep) {
                if (lastStep) {
                    const stepDuration = (Date.now() - stepStartTime) / 1000;
                    recordStepTiming(lastStep, stepDuration);
                }
                lastStep = data.current_step;
                stepStartTime = Date.now();
            }

            // Update UI
            updateProgressUI(data);

            // Update ETA from server
            if (data.eta_seconds !== undefined) {
                updateETAFromServer(data.eta_seconds, data.step_eta_seconds);
            } else {
                updateETA(startStep, data.progress_percent, data.current_step);
            }

            // Update system metrics
            if (data.system_metrics) {
                updateMetricsDisplay(data.system_metrics);
            }

            // Update Images
            if (data.step1_result) {
                showImage('container_step1', data.step1_result);
                appCache.step1_image = data.step1_result;
                saveToLocalStorage();
            }
            if (data.step2_result) {
                showImage('container_step2', data.step2_result);
                appCache.step2_image = data.step2_result;
                saveToLocalStorage();
            }
            if (data.final_result) {
                showImage('container_final', data.final_result);
            }

            if (['completed', 'stopped', 'failed', 'error'].includes(data.status)) {
                // Record final step timing
                if (lastStep) {
                    const stepDuration = (Date.now() - stepStartTime) / 1000;
                    recordStepTiming(lastStep, stepDuration);
                }

                clearInterval(pollingInterval);
                pollingInterval = null;
                currentJobId = null;
                jobStartTime = null;
                document.getElementById('btn_cancel').style.display = 'none';
                document.getElementById('eta_info').innerText = '완료';
                
                // 에러 상태 처리
                if (data.status === 'error' || data.status === 'failed') {
                    document.getElementById('error_msg').innerText = data.message || '알 수 없는 오류가 발생했습니다.';
                    document.getElementById('status_icon').style.color = '#d32f2f';
                    document.getElementById('status_text').innerText = 'ERROR';
                }

                // Hide metrics panel when done
                setTimeout(() => {
                    document.getElementById('metrics_panel').style.display = 'none';
                }, 3000);
            }

        } catch (e) {
            console.error("Polling error", e);
        }
    }, 3000);
}
