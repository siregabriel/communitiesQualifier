#!/bin/bash
# QUICK START GUIDE

cat << 'EOF'

╔═══════════════════════════════════════════════════════════════════════╗
║                                                                       ║
║   🏢 ASSISTED LIVING MAINTENANCE APP - QUICK START                   ║
║                                                                       ║
║   ✅ Login System         - User authentication                       ║
║   ✅ Auto Community       - Automatic community detection             ║
║   ✅ Photo Upload         - Mobile camera integration                 ║
║                                                                       ║
╚═══════════════════════════════════════════════════════════════════════╝

📂 PROJECT LOCATION:
   /Users/GabrielRosales/Projects/CommunitiesQualifier

🚀 START THE APP:

   Option 1 (Easiest):
   $ ./start_app.sh

   Option 2 (Manual):
   $ cd app_mantenimiento
   $ python3 app.py

🌐 ACCESS:
   http://localhost:5001/login

🔐 TEST CREDENTIALS:

   👤 john        | 🔑 pass123   | → Community A
   👤 maria       | 🔑 pass123   | → Community B
   👤 carlos      | 🔑 pass123   | → Community C
   👤 admin       | 🔑 admin123  | → All Communities ⭐

📋 WHAT YOU CAN DO:

   ✓ Login with user/password
   ✓ See your assigned community auto-filled
   ✓ Take/upload photo from mobile
   ✓ Submit maintenance report
   ✓ Photos saved with timestamp
   ✓ Admin can see all 38 communities

📸 PHOTO STORAGE:
   uploads/Community A/john_Community A_20260508_143022.jpg
   uploads/Community B/maria_Community B_20260508_144533.jpg
   etc...

💾 DATABASE:
   - Users stored in USERS_DB (app.py)
   - Photos stored in static/uploads/ by community
   - Sessions with Flask

📚 DOCUMENTATION:
   - SETUP_GUIDE.md - Complete setup instructions
   - IMPLEMENTATION_SUMMARY.md - Technical details

⚡ FEATURES:

   1️⃣  LOGIN
      • Secure user authentication
      • Session management
      • Automatic community assignment
      • Role-based access (admin vs normal user)

   2️⃣  AUTO COMMUNITY DETECTION
      • Reads from user database
      • Non-admin: shows only assigned community
      • Admin: shows all 38 communities
      • Pre-filled dropdown for normal users

   3️⃣  PHOTO UPLOAD
      • Mobile camera access (capture="environment")
      • Accept all image formats (jpg, png, gif, webp)
      • Max 16MB per file
      • Preview before upload
      • Stored with timestamp: username_community_datetime.ext
      • Organized by community folder

🔧 CUSTOMIZE:

   Add more users in app.py (USERS_DB):
   
   'newuser': {
       'password': 'password123',
       'community': 'Community D'
   }

   Then restart the app.

⚠️  REQUIREMENTS:
   • Python 3.6+
   • Flask (auto-installed by start_app.sh)
   • Modern web browser

🆘 TROUBLESHOOTING:

   Port already in use?
   → Edit app.py, change port from 5001 to 5002

   Flask not installed?
   → Run: pip3 install flask

   Can't login?
   → Check USERS_DB in app.py
   → Clear browser cookies
   → Check Flask logs for errors

   Photos not uploading?
   → Check uploads/ folder permissions
   → Verify browser allows file upload
   → Check Flask logs for errors

📞 NEXT STEPS:

   Optional Enhancements:
   • Integrate real database (PostgreSQL, MySQL)
   • Add more users
   • Setup admin dashboard with reports
   • Email notifications
   • Photo gallery/history
   • Advanced filtering

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Ready? Start with: ./start_app.sh

Then go to: http://localhost:5001/login

Login with: john / pass123

Happy testing! 🎉

EOF
