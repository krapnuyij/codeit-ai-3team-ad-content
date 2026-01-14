/**
 * main.js
 * 메인 초기화 및 이벤트 등록
 */

document.addEventListener('DOMContentLoaded', () => {
    // Restore from localStorage
    restoreFromLocalStorage();
    
    // Fetch available fonts
    fetchFonts();

    // Initialize UI event listeners
    initializeUI();
});
