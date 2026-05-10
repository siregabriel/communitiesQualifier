// PWA Install Prompt
// Shows a custom install button when the app can be installed

let deferredPrompt;
let installButton;

// Listen for the beforeinstallprompt event
window.addEventListener('beforeinstallprompt', (e) => {
    // Prevent the mini-infobar from appearing on mobile
    e.preventDefault();
    
    // Store the event so it can be triggered later
    deferredPrompt = e;
    
    // Show the install button
    showInstallPromotion();
});

function showInstallPromotion() {
    // Create install button if it doesn't exist
    if (!installButton) {
        installButton = document.createElement('button');
        installButton.id = 'pwa-install-btn';
        installButton.innerHTML = '<i class="fas fa-download"></i> Install App';
        installButton.style.cssText = `
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%);
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 25px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            box-shadow: 0 4px 12px rgba(76, 175, 80, 0.4);
            z-index: 9999;
            display: flex;
            align-items: center;
            gap: 8px;
            transition: all 0.3s ease;
            font-family: 'Inter', sans-serif;
        `;
        
        installButton.addEventListener('mouseenter', () => {
            installButton.style.transform = 'translateY(-2px)';
            installButton.style.boxShadow = '0 6px 16px rgba(76, 175, 80, 0.5)';
        });
        
        installButton.addEventListener('mouseleave', () => {
            installButton.style.transform = 'translateY(0)';
            installButton.style.boxShadow = '0 4px 12px rgba(76, 175, 80, 0.4)';
        });
        
        installButton.addEventListener('click', async () => {
            if (!deferredPrompt) return;
            
            // Show the install prompt
            deferredPrompt.prompt();
            
            // Wait for the user to respond to the prompt
            const { outcome } = await deferredPrompt.userChoice;
            
            console.log(`User response to the install prompt: ${outcome}`);
            
            // Clear the deferredPrompt
            deferredPrompt = null;
            
            // Hide the install button
            hideInstallPromotion();
        });
        
        document.body.appendChild(installButton);
    }
    
    installButton.style.display = 'flex';
}

function hideInstallPromotion() {
    if (installButton) {
        installButton.style.display = 'none';
    }
}

// Hide the install button if the app is already installed
window.addEventListener('appinstalled', () => {
    console.log('PWA was installed');
    hideInstallPromotion();
    deferredPrompt = null;
});

// Check if app is already installed (running in standalone mode)
if (window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true) {
    console.log('App is running in standalone mode');
    // Don't show install button if already installed
}
