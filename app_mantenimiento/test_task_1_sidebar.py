"""
Test Task 1: Verify sidebar navigation structure implementation
"""

import os
import re

def test_sidebar_structure():
    """Test that the sidebar HTML structure is correctly implemented"""
    
    dashboard_path = os.path.join(os.path.dirname(__file__), 'templates', 'dashboard.html')
    
    with open(dashboard_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Test 1: Sidebar container exists
    assert 'class="sidebar"' in content, "Sidebar container not found"
    assert 'id="sidebar"' in content, "Sidebar ID not found"
    print("✓ Sidebar container exists")
    
    # Test 2: Logo section exists
    assert 'class="sidebar-logo"' in content, "Sidebar logo section not found"
    assert '/static/icon-192.png' in content, "Logo image not found"
    assert '<span>ATLAS</span>' in content, "ATLAS text not found"
    print("✓ Logo section exists")
    
    # Test 3: User welcome section exists
    assert 'class="user-welcome"' in content, "User welcome section not found"
    assert 'Welcome back' in content, "Welcome message not found"
    assert 'id="userName"' in content, "Username span not found"
    assert 'id="userRole"' in content, "User role div not found"
    print("✓ User welcome section exists")
    
    # Test 4: Navigation menu exists
    assert 'class="navigation-menu"' in content, "Navigation menu not found"
    print("✓ Navigation menu exists")
    
    # Test 5: All 9 menu items exist
    menu_items = [
        ('Dashboard', 'fa-home'),
        ('My Visits', 'fa-file-alt'),
        ('Communities', 'fa-building'),
        ('Standards', 'fa-clipboard-check'),
        ('Reports', 'fa-chart-bar'),
        ('Action Items', 'fa-check-circle'),
        ('Resources', 'fa-book'),
        ('Settings', 'fa-cog'),
        ('Log Out', 'fa-sign-out-alt')
    ]
    
    for item_name, icon_class in menu_items:
        assert item_name in content, f"Menu item '{item_name}' not found"
        assert icon_class in content, f"Icon '{icon_class}' not found"
    
    print("✓ All 9 menu items exist with Font Awesome icons")
    
    # Test 6: Sidebar CSS styling exists
    assert '.sidebar {' in content, "Sidebar CSS not found"
    assert 'width: 260px' in content, "Sidebar width not set to 260px"
    assert 'background: #1e293b' in content, "Sidebar background color not set"
    assert 'position: fixed' in content, "Sidebar position not fixed"
    assert 'height: 100vh' in content, "Sidebar height not full viewport"
    print("✓ Sidebar CSS styling exists with correct properties")
    
    # Test 7: Main content area exists
    assert 'class="main-content"' in content, "Main content area not found"
    assert 'margin-left: 260px' in content, "Main content margin not set"
    print("✓ Main content area exists with correct margin")
    
    # Test 8: Mobile menu toggle exists
    assert 'class="mobile-menu-toggle"' in content, "Mobile menu toggle not found"
    assert 'id="mobileMenuToggle"' in content, "Mobile menu toggle ID not found"
    print("✓ Mobile menu toggle exists")
    
    # Test 9: Sidebar overlay exists
    assert 'class="sidebar-overlay"' in content, "Sidebar overlay not found"
    assert 'id="sidebarOverlay"' in content, "Sidebar overlay ID not found"
    print("✓ Sidebar overlay exists")
    
    # Test 10: Mobile responsive CSS exists
    assert '@media (max-width: 768px)' in content, "Mobile media query not found"
    assert 'transform: translateX(-100%)' in content, "Sidebar mobile transform not found"
    print("✓ Mobile responsive CSS exists")
    
    # Test 11: JavaScript functions exist
    assert 'toggleSidebar()' in content, "toggleSidebar function not found"
    assert 'closeSidebar()' in content, "closeSidebar function not found"
    print("✓ Mobile menu JavaScript functions exist")
    
    # Test 12: User info population exists
    assert "document.getElementById('userName')" in content, "Username population not found"
    assert "document.getElementById('userRole')" in content, "User role population not found"
    print("✓ User info population JavaScript exists")
    
    print("\n✅ All Task 1 requirements verified successfully!")
    return True

if __name__ == '__main__':
    try:
        test_sidebar_structure()
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        exit(1)
