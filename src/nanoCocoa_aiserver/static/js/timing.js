/**
 * timing.js
 * 작업 시간 측정 및 예상 시간 계산
 */

/**
 * Update ETA (Estimated Time of Arrival) display
 */
function updateETA(startStep, progressPercent, currentStep) {
    if (!jobStartTime || progressPercent >= 100) return;
    
    const elapsed = (Date.now() - jobStartTime) / 1000; // seconds
    
    // Calculate total estimated time based on which steps are running
    let totalEstimated = 0;
    if (startStep === 1) {
        totalEstimated = getAverageStepTime('step1') + getAverageStepTime('step2') + getAverageStepTime('step3');
    } else if (startStep === 2) {
        totalEstimated = getAverageStepTime('step2') + getAverageStepTime('step3');
    } else if (startStep === 3) {
        totalEstimated = getAverageStepTime('step3');
    }
    
    // Calculate remaining time
    let remaining;
    if (progressPercent > 0) {
        const estimatedTotal = (elapsed / progressPercent) * 100;
        remaining = Math.max(0, estimatedTotal - elapsed);
    } else {
        remaining = totalEstimated;
    }
    
    // Format time
    const minutes = Math.floor(remaining / 60);
    const seconds = Math.floor(remaining % 60);
    
    let etaText = '예상 시간: ';
    if (minutes > 0) {
        etaText += `${minutes}분 ${seconds}초`;
    } else {
        etaText += `${seconds}초`;
    }
    
    document.getElementById('eta_info').innerText = etaText;
}
