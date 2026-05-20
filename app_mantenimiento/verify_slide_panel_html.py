#!/usr/bin/env python3
"""
Verification script for Task 1: Set up HTML structure for slide panel and overlay
This script verifies that the HTML structure has been correctly added to dashboard.html
"""

import re
from pathlib import Path

def verify_slide_panel_html():
    """Verify the slide panel HTML structure exists in dashboard.html"""
    
    dashboard_path = Path(__file__).parent / 'templates' / 'dashboard.html'
    
    if not dashboard_path.exists():
        print("❌ dashboard.html not found")
        return False
    
    with open(dashboard_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    checks = {
        'Slide panel overlay element': r'<div\s+class="slide-panel-overlay"[^>]*id="slidePanelOverlay"',
        'Slide panel container': r'<aside\s+class="slide-panel"[^>]*id="slidePanel"',
        'Panel header section': r'<div\s+class="slide-panel-header"',
        'Panel title': r'<h2\s+id="slidePanelTitle"',
        'Panel subtitle': r'<p\s+class="slide-panel-subtitle"[^>]*id="slidePanelSubtitle"',
        'Close button': r'<button\s+class="slide-panel-close"[^>]*id="slidePanelClose"',
        'Close button icon': r'<i\s+class="fas fa-times"',
        'Panel body section': r'<div\s+class="slide-panel-body"[^>]*id="slidePanelBody"',
        'ARIA role dialog': r'role="dialog"',
        'ARIA modal': r'aria-modal="true"',
        'ARIA labelledby': r'aria-labelledby="slidePanelTitle"',
        'ARIA label on close button': r'aria-label="Close panel"',
        'ARIA hidden on overlay': r'aria-hidden="true"',
    }
    
    all_passed = True
    print("🔍 Verifying slide panel HTML structure...\n")
    
    for check_name, pattern in checks.items():
        if re.search(pattern, content, re.IGNORECASE):
            print(f"✅ {check_name}")
        else:
            print(f"❌ {check_name}")
            all_passed = False
    
    # Verify CSS styles exist
    print("\n🔍 Verifying CSS styles exist...\n")
    
    css_checks = {
        'slide-panel-overlay class': r'\.slide-panel-overlay\s*\{',
        'slide-panel class': r'\.slide-panel\s*\{',
        'slide-panel-header class': r'\.slide-panel-header\s*\{',
        'slide-panel-body class': r'\.slide-panel-body\s*\{',
        'slide-panel-close class': r'\.slide-panel-close\s*\{',
        'slide-panel-title class': r'\.slide-panel-title\s*\{',
        'slide-panel show state': r'\.slide-panel\.show\s*\{',
        'overlay show state': r'\.slide-panel-overlay\.show\s*\{',
    }
    
    for check_name, pattern in css_checks.items():
        if re.search(pattern, content):
            print(f"✅ {check_name}")
        else:
            print(f"❌ {check_name}")
            all_passed = False
    
    # Verify structure is after modal
    print("\n🔍 Verifying structure placement...\n")
    
    modal_match = re.search(r'<!-- Inspection Details Modal -->', content)
    panel_match = re.search(r'<!-- Community Details Slide Panel -->', content)
    
    if modal_match and panel_match:
        if panel_match.start() > modal_match.start():
            print("✅ Slide panel is placed after modal structure")
        else:
            print("❌ Slide panel should be after modal structure")
            all_passed = False
    else:
        print("❌ Could not find modal or panel comments")
        all_passed = False
    
    print("\n" + "="*60)
    if all_passed:
        print("✅ ALL CHECKS PASSED - Task 1 Complete!")
        print("="*60)
        print("\n📋 Summary:")
        print("  • Slide panel overlay element added")
        print("  • Slide panel container with semantic <aside> tag")
        print("  • Header section with title and subtitle")
        print("  • Close button with Font Awesome icon")
        print("  • Body section for dynamic content")
        print("  • All ARIA labels for accessibility")
        print("  • CSS styles already exist")
        print("  • Proper placement after modal structure")
        return True
    else:
        print("❌ SOME CHECKS FAILED - Please review")
        print("="*60)
        return False

if __name__ == '__main__':
    success = verify_slide_panel_html()
    exit(0 if success else 1)
