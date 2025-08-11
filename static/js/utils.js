// YouTube to Doc - Utility Functions

/**
 * Validate YouTube URL format
 */
function validateYouTubeURL(url) {
    const patterns = [
        /^(?:https?:\/\/)?(?:www\.)?youtube\.com\/watch\?v=([a-zA-Z0-9_-]{11})/,
        /^(?:https?:\/\/)?(?:www\.)?youtu\.be\/([a-zA-Z0-9_-]{11})/,
        /^(?:https?:\/\/)?(?:www\.)?youtube\.com\/embed\/([a-zA-Z0-9_-]{11})/
    ];
    
    return patterns.some(pattern => pattern.test(url));
}

/**
 * Extract video ID from YouTube URL
 */
function extractVideoId(url) {
    const patterns = [
        /(?:https?:\/\/)?(?:www\.)?youtube\.com\/watch\?v=([a-zA-Z0-9_-]{11})/,
        /(?:https?:\/\/)?(?:www\.)?youtu\.be\/([a-zA-Z0-9_-]{11})/,
        /(?:https?:\/\/)?(?:www\.)?youtube\.com\/embed\/([a-zA-Z0-9_-]{11})/
    ];
    
    for (const pattern of patterns) {
        const match = url.match(pattern);
        if (match) {
            return match[1];
        }
    }
    
    return null;
}

/**
 * Format duration from seconds to human readable format
 */
function formatDuration(seconds) {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    
    if (hours > 0) {
        return `${hours}h ${minutes}m ${secs}s`;
    } else if (minutes > 0) {
        return `${minutes}m ${secs}s`;
    } else {
        return `${secs}s`;
    }
}

/**
 * Format number with commas
 */
function formatNumber(num) {
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

/**
 * Debounce function for input validation
 */
function debounce(func, wait, immediate) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            timeout = null;
            if (!immediate) func(...args);
        };
        const callNow = immediate && !timeout;
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
        if (callNow) func(...args);
    };
}

/**
 * Show loading state on form submission
 */
function showLoadingState(form) {
    const submitButton = form.querySelector('button[type="submit"]');
    const originalText = submitButton.innerHTML;
    
    submitButton.disabled = true;
    submitButton.innerHTML = `
        <span class="inline-flex items-center gap-2">
            <svg class="animate-spin h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <span>Processing...</span>
        </span>
    `;
    
    return () => {
        submitButton.disabled = false;
        submitButton.innerHTML = originalText;
    };
}

/**
 * Initialize form validation
 */
function initializeFormValidation() {
    const form = document.querySelector('form[method="post"]');
    const urlInput = document.getElementById('input_text');
    
    if (!form || !urlInput) return;
    
    // Validate URL on input
    const validateURL = debounce(() => {
        const url = urlInput.value.trim();
        const isValid = url === '' || validateYouTubeURL(url);
        
        urlInput.classList.toggle('border-red-500', !isValid);
        urlInput.classList.toggle('border-gray-300', isValid);
        
        // Show/hide error message
        let errorMsg = urlInput.parentNode.querySelector('.url-error');
        if (!isValid && url !== '') {
            if (!errorMsg) {
                errorMsg = document.createElement('div');
                errorMsg.className = 'url-error text-sm text-red-600 mt-1';
                errorMsg.textContent = 'Please enter a valid YouTube URL';
                urlInput.parentNode.appendChild(errorMsg);
            }
        } else if (errorMsg) {
            errorMsg.remove();
        }
    }, 300);
    
    urlInput.addEventListener('input', validateURL);
    
    // Handle form submission
    form.addEventListener('submit', (e) => {
        const url = urlInput.value.trim();
        if (!validateYouTubeURL(url)) {
            e.preventDefault();
            urlInput.focus();
            return;
        }
        
        const resetLoading = showLoadingState(form);
        
        // Reset loading state if form submission fails
        setTimeout(() => {
            resetLoading();
        }, 30000); // 30 second timeout
    });
}

/**
 * Initialize mobile menu toggle
 */
function initializeMobileMenu() {
    const menuButton = document.querySelector('[aria-controls="mobile-menu"]');
    const mobileMenu = document.getElementById('mobile-menu');
    
    if (!menuButton || !mobileMenu) return;
    
    menuButton.addEventListener('click', () => {
        const isExpanded = menuButton.getAttribute('aria-expanded') === 'true';
        menuButton.setAttribute('aria-expanded', !isExpanded);
        mobileMenu.classList.toggle('hidden', isExpanded);
    });
}

/**
 * Initialize copy functionality
 */
function initializeCopyFeature() {
    // This function is called from the result template
    window.copyToClipboard = function() {
        const content = document.getElementById('content-area').textContent;
        navigator.clipboard.writeText(content).then(() => {
            showToast('Content copied to clipboard!', 'success');
        }).catch(() => {
            showToast('Failed to copy content', 'error');
        });
    };
}

/**
 * Show toast notification
 */
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `fixed top-4 right-4 p-4 rounded-lg shadow-lg z-50 transition-opacity duration-300 ${
        type === 'success' ? 'bg-green-500 text-white' :
        type === 'error' ? 'bg-red-500 text-white' :
        'bg-blue-500 text-white'
    }`;
    toast.textContent = message;
    
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => {
            document.body.removeChild(toast);
        }, 300);
    }, 3000);
}

/**
 * Initialize all features when DOM is ready
 */
document.addEventListener('DOMContentLoaded', () => {
    initializeFormValidation();
    initializeMobileMenu();
    initializeCopyFeature();
});

// Export functions for global use
window.YouTubeToDoc = {
    validateYouTubeURL,
    extractVideoId,
    formatDuration,
    formatNumber,
    showToast
}; 