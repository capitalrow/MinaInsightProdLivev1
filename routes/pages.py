# routes/pages.py
from flask import Blueprint, redirect, url_for, render_template
from flask_login import login_required, current_user

pages_bp = Blueprint("pages", __name__)


# Convenience redirects for common auth URLs
@pages_bp.route("/login")
def login_redirect():
    """Convenience redirect: /login -> /auth/login"""
    return redirect(url_for("auth.login"))


@pages_bp.route("/register")
def register_redirect():
    """Convenience redirect: /register -> /auth/register"""
    return redirect(url_for("auth.register"))


@pages_bp.route("/signup")
def signup_redirect():
    """Convenience redirect: /signup -> /auth/register"""
    return redirect(url_for("auth.register"))


@pages_bp.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))
    return render_template("marketing/landing_standalone.html")

@pages_bp.route("/app")
def app():
    """Intelligent entry point for users coming from marketing CTAs."""
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))
    else:
        # Route new users to registration with next parameter for smooth onboarding
        return redirect(url_for("auth.register", next=url_for("dashboard.index")))

@pages_bp.route("/live")
@login_required
def live():
    """Production live recording interface with all features consolidated"""
    return render_template("pages/live.html")

@pages_bp.route("/live-enhanced")
@login_required
def live_enhanced():
    """Legacy route - redirects to main live interface"""
    return redirect(url_for("pages.live"))

@pages_bp.route("/live-comprehensive")
@login_required
def live_comprehensive():
    """Legacy route - redirects to main live interface"""
    return redirect(url_for("pages.live"))

# Legal Pages
@pages_bp.route("/privacy")
def privacy():
    """Privacy Policy page"""
    return render_template("legal/privacy.html")

@pages_bp.route("/terms")
def terms():
    """Terms of Service page"""
    return render_template("legal/terms.html")

@pages_bp.route("/cookies")
def cookies():
    """Cookie Policy page"""
    return render_template("legal/cookies.html")

@pages_bp.route("/test-crown4")
def test_crown4():
    """CROWN⁴ Feature Test Suite"""
    from flask import send_from_directory
    return send_from_directory('.', 'test_crown4_features.html')

# Onboarding
@pages_bp.route("/onboarding")
@login_required
def onboarding():
    """Onboarding wizard for new users"""
    return render_template("onboarding/wizard.html")

@pages_bp.route("/onboarding/complete", methods=["POST"])
@login_required
def onboarding_complete():
    """Handle onboarding completion"""
    from flask import request
    
    # Get form data
    workspace_name = request.form.get('workspace_name', '')
    workspace_role = request.form.get('workspace_role', '')
    email_notifications = request.form.get('email_notifications') == 'on'
    meeting_reminders = request.form.get('meeting_reminders') == 'on'
    task_updates = request.form.get('task_updates') == 'on'
    
    # In production, save user preferences to database
    # For now, just log and redirect
    print(f"Onboarding completed: {workspace_name}, {workspace_role}")
    print(f"Preferences: email={email_notifications}, reminders={meeting_reminders}, tasks={task_updates}")
    
    return redirect(url_for("dashboard.index"))

@pages_bp.route("/clear-cache")
@login_required
def clear_cache():
    """Utility page to clear all browser cache and IndexedDB"""
    return """
<!DOCTYPE html>
<html>
<head>
    <title>Clear Cache - Mina</title>
    <style>
        body {
            font-family: system-ui, -apple-system, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            margin: 0;
            color: white;
        }
        .container {
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            padding: 3rem;
            text-align: center;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            max-width: 500px;
        }
        h1 { margin: 0 0 1rem; font-size: 2rem; }
        p { margin: 0 0 2rem; opacity: 0.9; }
        button {
            background: white;
            color: #667eea;
            border: none;
            padding: 1rem 2rem;
            font-size: 1.1rem;
            font-weight: 600;
            border-radius: 10px;
            cursor: pointer;
            transition: all 0.3s;
        }
        button:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }
        #status {
            margin-top: 1.5rem;
            font-weight: 600;
            min-height: 24px;
        }
        .success { color: #4ade80; }
        .loading { opacity: 0.7; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🧹 Clear Cache</h1>
        <p>This will clear all cached data and reload the application with a fresh state.</p>
        <button onclick="clearAll()">Clear All Cache</button>
        <div id="status"></div>
    </div>
    
    <script>
    async function clearAll() {
        const status = document.getElementById('status');
        status.textContent = 'Clearing cache...';
        status.className = 'loading';
        
        try {
            // Clear IndexedDB databases
            const databases = ['MinaCache', 'mina-cache', 'MinaTasks', 'mina-tasks'];
            for (const db of databases) {
                try {
                    await new Promise((resolve, reject) => {
                        const req = indexedDB.deleteDatabase(db);
                        req.onsuccess = resolve;
                        req.onerror = reject;
                        req.onblocked = resolve; // Continue even if blocked
                    });
                    console.log(`Deleted ${db}`);
                } catch (e) {
                    console.warn(`Could not delete ${db}:`, e);
                }
            }
            
            // Clear localStorage
            localStorage.clear();
            
            // Clear sessionStorage
            sessionStorage.clear();
            
            status.textContent = '✅ Cache cleared! Redirecting...';
            status.className = 'success';
            
            setTimeout(() => {
                window.location.href = '/dashboard/meetings';
            }, 1000);
            
        } catch (error) {
            status.textContent = '❌ Error: ' + error.message;
            console.error('Clear cache error:', error);
        }
    }
    </script>
</body>
</html>
    """