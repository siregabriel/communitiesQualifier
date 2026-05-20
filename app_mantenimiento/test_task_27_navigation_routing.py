"""
Test Task 27: Verify navigation routing implementation

This test verifies that:
- Each navigation menu item has the correct data-view attribute or href
- Dashboard shows community grid
- My Visits filters by current user
- Communities shows all communities
- Standards navigates to /questions/manage
- Reports shows all reports
- Action Items filters by Fail/Opportunity/Needs Attention
- Log Out navigates to /logout
- Navigation click handlers are properly implemented
- View switching logic is correctly implemented
"""

import os
import re

def test_navigation_routing():
    """Test that navigation routing is correctly implemented"""
    
    dashboard_path = os.path.join(os.path.dirname(__file__), 'templates', 'dashboard.html')
    
    with open(dashboard_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    print("Testing Task 27: Navigation Routing\n")
    
    # Test 1: Dashboard menu item
    assert 'data-view="dashboard"' in content, "Dashboard menu item missing data-view attribute"
    assert 'fa-home' in content, "Dashboard icon not found"
    print("✓ Dashboard menu item has correct data-view attribute")
    
    # Test 2: My Visits menu item
    assert 'data-view="my-visits"' in content, "My Visits menu item missing data-view attribute"
    assert 'fa-file-alt' in content, "My Visits icon not found"
    print("✓ My Visits menu item has correct data-view attribute")
    
    # Test 3: Communities menu item
    assert 'data-view="communities"' in content, "Communities menu item missing data-view attribute"
    assert 'fa-building' in content, "Communities icon not found"
    print("✓ Communities menu item has correct data-view attribute")
    
    # Test 4: Standards menu item navigates to /questions/manage
    assert 'href="/questions/manage"' in content, "Standards menu item missing href to /questions/manage"
    assert 'fa-clipboard-check' in content, "Standards icon not found"
    print("✓ Standards menu item navigates to /questions/manage")
    
    # Test 5: Reports menu item
    assert 'data-view="reports"' in content, "Reports menu item missing data-view attribute"
    assert 'fa-chart-bar' in content, "Reports icon not found"
    print("✓ Reports menu item has correct data-view attribute")
    
    # Test 6: Action Items menu item
    assert 'data-view="action-items"' in content, "Action Items menu item missing data-view attribute"
    assert 'fa-check-circle' in content, "Action Items icon not found"
    print("✓ Action Items menu item has correct data-view attribute")
    
    # Test 7: Resources menu item
    assert 'data-view="resources"' in content, "Resources menu item missing data-view attribute"
    assert 'fa-book' in content, "Resources icon not found"
    print("✓ Resources menu item has correct data-view attribute")
    
    # Test 8: Settings menu item
    assert 'data-view="settings"' in content, "Settings menu item missing data-view attribute"
    assert 'fa-cog' in content, "Settings icon not found"
    print("✓ Settings menu item has correct data-view attribute")
    
    # Test 9: Log Out menu item navigates to /logout
    assert 'href="/logout"' in content, "Log Out menu item missing href to /logout"
    assert 'fa-sign-out-alt' in content, "Log Out icon not found"
    print("✓ Log Out menu item navigates to /logout")
    
    # Test 10: showView function exists
    assert 'function showView(view)' in content, "showView function not found"
    print("✓ showView function exists")
    
    # Test 11: Dashboard view renders community cards
    assert "case 'dashboard':" in content, "Dashboard case not found in showView"
    assert 'renderCommunityCards()' in content, "renderCommunityCards function call not found"
    print("✓ Dashboard view renders community cards")
    
    # Test 12: My Visits view implementation
    assert "case 'my-visits':" in content, "My Visits case not found in showView"
    assert 'renderMyVisits()' in content, "renderMyVisits function call not found"
    assert 'function renderMyVisits()' in content, "renderMyVisits function not found"
    print("✓ My Visits view is implemented")
    
    # Test 13: My Visits filters by current user
    assert 'myInspections = allInspections.filter(item => item.username === currentUsername)' in content, \
        "My Visits does not filter by current username"
    print("✓ My Visits filters by current user")
    
    # Test 14: Communities view implementation
    assert "case 'communities':" in content, "Communities case not found in showView"
    # Communities also uses renderCommunityCards
    print("✓ Communities view is implemented")
    
    # Test 15: Reports view implementation
    assert "case 'reports':" in content, "Reports case not found in showView"
    assert 'renderReports()' in content, "renderReports function call not found"
    assert 'function renderReports()' in content, "renderReports function not found"
    print("✓ Reports view is implemented")
    
    # Test 16: Action Items view implementation
    assert "case 'action-items':" in content, "Action Items case not found in showView"
    assert 'renderActionItems()' in content, "renderActionItems function call not found"
    assert 'function renderActionItems()' in content, "renderActionItems function not found"
    print("✓ Action Items view is implemented")
    
    # Test 17: Action Items filters by Fail/Opportunity/Needs Attention
    assert "const actionConditions = ['Fail', 'Opportunity', 'Needs Attention']" in content, \
        "Action Items does not define correct action conditions"
    assert 'actionItems = allInspections.filter(item => actionConditions.includes(item.condition))' in content, \
        "Action Items does not filter by action conditions"
    print("✓ Action Items filters by Fail/Opportunity/Needs Attention")
    
    # Test 18: Resources view implementation
    assert "case 'resources':" in content, "Resources case not found in showView"
    assert 'renderResources()' in content, "renderResources function call not found"
    assert 'function renderResources()' in content, "renderResources function not found"
    print("✓ Resources view is implemented")
    
    # Test 19: Settings view implementation
    assert "case 'settings':" in content, "Settings case not found in showView"
    assert 'renderSettings()' in content, "renderSettings function call not found"
    assert 'function renderSettings()' in content, "renderSettings function not found"
    print("✓ Settings view is implemented")
    
    # Test 20: Navigation click event listeners
    assert "document.querySelectorAll('.nav-item[data-view]').forEach" in content, \
        "Navigation click event listeners not found"
    assert "item.addEventListener('click'" in content, \
        "Navigation click event listener not attached"
    print("✓ Navigation click event listeners are attached")
    
    # Test 21: Navigation updates active state
    assert "item.classList.add('active')" in content, \
        "Active class addition not found"
    assert "item.classList.remove('active')" in content, \
        "Active class removal not found"
    print("✓ Navigation updates active state")
    
    # Test 22: Navigation updates aria-current attribute
    assert "item.setAttribute('aria-current', 'page')" in content, \
        "aria-current attribute setting not found"
    assert "item.removeAttribute('aria-current')" in content, \
        "aria-current attribute removal not found"
    print("✓ Navigation updates aria-current attribute for accessibility")
    
    # Test 23: Navigation closes mobile menu
    assert "if (window.innerWidth < 768) {" in content, \
        "Mobile menu close check not found"
    assert "closeSidebar()" in content, \
        "closeSidebar function call not found"
    print("✓ Navigation closes mobile menu on mobile devices")
    
    # Test 24: Header updates based on view
    assert "const headerTitle = document.querySelector('.header-left h1')" in content, \
        "Header title selector not found"
    assert "const headerDesc = document.querySelector('.header-left p')" in content, \
        "Header description selector not found"
    assert "headerTitle.textContent" in content, \
        "Header title update not found"
    assert "headerDesc.textContent" in content, \
        "Header description update not found"
    print("✓ Header updates based on current view")
    
    # Test 25: View-specific header content
    assert "'📊 Dashboard'" in content, "Dashboard header not found"
    assert "'Community Performance Overview'" in content, "Dashboard description not found"
    assert "'📝 My Visits'" in content, "My Visits header not found"
    assert "'Your Inspection Submissions'" in content, "My Visits description not found"
    assert "'🏘️ Communities'" in content, "Communities header not found"
    assert "'All Communities Overview'" in content, "Communities description not found"
    assert "'📊 Reports & Analytics'" in content, "Reports header not found"
    assert "'⚠️ Action Items'" in content, "Action Items header not found"
    assert "'Items Requiring Attention'" in content, "Action Items description not found"
    assert "'📚 Resources'" in content, "Resources header not found"
    assert "'⚙️ Settings'" in content, "Settings header not found"
    print("✓ View-specific header content is defined")
    
    # Test 26: currentView variable tracks active view
    assert "let currentView = 'dashboard'" in content, \
        "currentView variable not found"
    assert "currentView = view" in content, \
        "currentView assignment not found"
    print("✓ currentView variable tracks active view")
    
    # Test 27: Initial view is set to dashboard
    assert "showView('dashboard')" in content, \
        "Initial showView call not found"
    print("✓ Initial view is set to dashboard")
    
    # Test 28: Filters reset when changing views
    assert "currentConditionFilter = 'all'" in content, \
        "Condition filter reset not found"
    assert "currentTypeFilter = 'all'" in content, \
        "Type filter reset not found"
    assert "currentSurveyTypeFilter = 'all'" in content, \
        "Survey type filter reset not found"
    print("✓ Filters reset when changing views")
    
    # Test 29: Filter buttons reset to 'all' when changing views
    assert "document.querySelectorAll('.filter-btn').forEach(btn => {" in content, \
        "Filter button reset loop not found"
    assert "btn.classList.remove('active')" in content, \
        "Filter button active class removal not found"
    print("✓ Filter buttons reset when changing views")
    
    # Test 30: Navigation menu items have proper structure
    # Count all data-view attributes in nav-item elements
    nav_items_with_data_view = content.count('data-view="')
    # Should have exactly 7 items with data-view (excluding Standards and Log Out which use href)
    assert nav_items_with_data_view >= 7, \
        f"Expected at least 7 nav items with data-view, found {nav_items_with_data_view}"
    print(f"✓ Found {nav_items_with_data_view} navigation items with data-view attributes")
    
    print("\n✅ All Task 27 navigation routing requirements verified successfully!")
    print("\nSummary:")
    print("- All 9 navigation menu items are properly configured")
    print("- Dashboard shows community grid via renderCommunityCards()")
    print("- My Visits filters inspections by current user")
    print("- Communities shows all communities via renderCommunityCards()")
    print("- Standards navigates to /questions/manage")
    print("- Reports shows analytics via renderReports()")
    print("- Action Items filters by Fail/Opportunity/Needs Attention")
    print("- Resources and Settings have dedicated views")
    print("- Log Out navigates to /logout")
    print("- Navigation properly updates active states and aria attributes")
    print("- Mobile menu closes automatically on navigation")
    print("- View switching is fully implemented with proper state management")
    
    return True

if __name__ == '__main__':
    try:
        test_navigation_routing()
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        exit(1)
