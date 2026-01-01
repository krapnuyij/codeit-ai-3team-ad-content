/**
 * timing.js
 * 작업 시간 측정 및 예상 시간 계산
 */

/**
 * Format seconds to human-readable time string
 */
function formatETA(seconds) {
    if (seconds <= 0) return '-';

    if (seconds < 60) {
        return `${seconds}초`;
    }

    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;

    if (minutes < 60) {
        return remainingSeconds > 0
            ? `${minutes}분 ${remainingSeconds}초`
            : `${minutes}분`;
    }

    const hours = Math.floor(minutes / 60);
    const remainingMinutes = minutes % 60;
    return `${hours}시간 ${remainingMinutes}분`;
}

/**
 * Update ETA display from server-provided eta_seconds
 */
function updateETAFromServer(etaSeconds, stepEtaSeconds) {
    const etaText = formatETA(etaSeconds);
    let displayText = `전체 예상: ${etaText}`;

    if (stepEtaSeconds !== undefined && stepEtaSeconds !== null && stepEtaSeconds > 0) {
        const stepText = formatETA(stepEtaSeconds);
        displayText = `현재 단계 예상: ${stepText} (전체: ${etaText})`;
    } else {
        displayText = `예상 시간: ${etaText}`;
    }

    document.getElementById('eta_info').innerText = displayText;
}

/**
 * Update ETA (Estimated Time of Arrival) display - Legacy function
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
