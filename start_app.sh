#!/bin/bash

# Assisted Living Maintenance App - Startup Script

echo "🚀 Starting Assisted Living Maintenance App..."
echo ""

# Navigate to app directory
cd /Users/GabrielRosales/Projects/CommunitiesQualifier/app_mantenimiento

# Check if Flask is installed
if ! python3 -c "import flask" 2>/dev/null; then
    echo "📦 Installing Flask..."
    pip3 install flask
fi

echo ""
echo "✅ Application starting..."
echo "📂 Location: /Users/GabrielRosales/Projects/CommunitiesQualifier/app_mantenimiento"
echo "🌐 URL: http://localhost:5001"
echo "🔑 Login page: http://localhost:5001/login"
echo ""
echo "🔐 Demo Credentials:"
echo "  👤 john / pass123 → Community A"
echo "  👤 maria / pass123 → Community B"
echo "  👤 admin / admin123 → All Communities"
echo ""
echo "Press Ctrl+C to stop the server"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Run Flask app
python3 app.py
