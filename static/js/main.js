/**
 * Savyant Systems - General UI & Form Helpers
 */

document.addEventListener('DOMContentLoaded', () => {
    // 1. Duplicate submission prevention for standard POST forms
    const forms = document.querySelectorAll('form:not(#orderForm)');
    forms.forEach(form => {
        form.addEventListener('submit', (e) => {
            const submitBtn = form.querySelector('button[type="submit"]');
            if (submitBtn && !submitBtn.disabled) {
                // If it's a confirmed action
                const confirmMsg = submitBtn.getAttribute('data-confirm');
                if (confirmMsg && !window.confirm(confirmMsg)) {
                    e.preventDefault();
                    return false;
                }
                submitBtn.disabled = true;
                const originalText = submitBtn.innerHTML;
                submitBtn.innerHTML = 'Processing...';
                // Re-enable after 5s timeout in case of network issue
                setTimeout(() => {
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = originalText;
                }, 5000);
            }
        });
    });

    // 2. Global confirmation dialog for confirm/cancel action links/buttons
    const confirmButtons = document.querySelectorAll('[data-confirm]');
    confirmButtons.forEach(btn => {
        btn.addEventListener('click', (e) => {
            const msg = btn.getAttribute('data-confirm');
            if (!window.confirm(msg)) {
                e.preventDefault();
                e.stopPropagation();
                return false;
            }
        });
    });
});
