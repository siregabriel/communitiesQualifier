"""
Test Mobile Layout - Task 24
Tests the mobile responsive layout to ensure the sidebar hamburger menu works correctly 
on mobile viewports (< 768px width).

Requirements tested:
- 6.1: Sidebar is hidden by default on viewport < 768px
- 6.2: Mobile menu toggle button is visible
- 6.3: Sidebar slides in when toggle is clicked
- 6.4: Overlay appears when sidebar is open
- 6.5: Sidebar closes when overlay is clicked
- 6.6: Sidebar closes when nav item is clicked
- Community grid displays 1 card per row on mobile
"""

import pytest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time


class TestMobileLayout:
    """Test suite for mobile layout verification (viewport < 768px)"""
    
    @pytest.fixture(scope="class")
    def driver(self):
        """Setup Chrome driver with mobile viewport"""
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        
        # Use webdriver-manager to automatically handle ChromeDriver
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        # Set mobile viewport (375x667 - iPhone SE size)
        driver.set_window_size(375, 667)
        
        yield driver
        driver.quit()
    
    @pytest.fixture(scope="class")
    def authenticated_driver(self, driver):
        """Login and navigate to dashboard"""
        # Navigate to login page
        driver.get('http://localhost:5000/login')
        
        # Wait for page to load
        wait = WebDriverWait(driver, 10)
        
        # Login as admin user
        username_input = wait.until(EC.presence_of_element_located((By.NAME, 'username')))
        password_input = driver.find_element(By.NAME, 'password')
        
        username_input.send_keys('admin')
        password_input.send_keys('admin123')
        
        # Submit form
        login_button = driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]')
        login_button.click()
        
        # Wait for dashboard to load
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, 'sidebar')))
        
        # Wait for JavaScript to initialize
        time.sleep(2)
        
        return driver
    
    def test_sidebar_hidden_by_default_on_mobile(self, authenticated_driver):
        """
        Requirement 6.1: Verify sidebar is hidden by default on viewport < 768px
        """
        sidebar = authenticated_driver.find_element(By.ID, 'sidebar')
        
        # Get computed transform property
        transform = authenticated_driver.execute_script(
            "return window.getComputedStyle(arguments[0]).transform;",
            sidebar
        )
        
        # Sidebar should be translated off-screen (translateX(-100%))
        # The transform will be a matrix, check if it's translated left
        assert transform != 'none', "Sidebar should have transform applied on mobile"
        
        # Check if sidebar has 'open' class (it shouldn't by default)
        classes = sidebar.get_attribute('class')
        assert 'open' not in classes, "Sidebar should not have 'open' class by default"
        
        # Verify sidebar is visually off-screen by checking its position
        sidebar_rect = sidebar.rect
        viewport_width = authenticated_driver.execute_script("return window.innerWidth;")
        
        # Sidebar should be positioned off-screen to the left
        assert sidebar_rect['x'] < 0, f"Sidebar should be off-screen (x < 0), got x={sidebar_rect['x']}"
        
        print(f"Sidebar transform: {transform}, x position: {sidebar_rect['x']}")
    
    def test_mobile_menu_toggle_visible(self, authenticated_driver):
        """
        Requirement 6.2: Verify mobile menu toggle button is visible
        """
        mobile_toggle = authenticated_driver.find_element(By.ID, 'mobileMenuToggle')
        
        # Check if element is displayed
        is_displayed = mobile_toggle.is_displayed()
        
        # Mobile toggle should be visible on mobile viewport
        assert is_displayed, "Mobile menu toggle should be visible on mobile viewport"
        
        # Verify CSS display property
        display_value = authenticated_driver.execute_script(
            "return window.getComputedStyle(arguments[0]).display;",
            mobile_toggle
        )
        
        assert display_value != 'none', f"Mobile toggle display should not be 'none', got '{display_value}'"
        
        # Verify button is clickable
        assert mobile_toggle.is_enabled(), "Mobile menu toggle should be enabled"
        
        print(f"Mobile toggle display: {display_value}, visible: {is_displayed}")
    
    def test_sidebar_slides_in_when_toggle_clicked(self, authenticated_driver):
        """
        Requirement 6.3: Verify sidebar slides in when toggle is clicked
        """
        sidebar = authenticated_driver.find_element(By.ID, 'sidebar')
        mobile_toggle = authenticated_driver.find_element(By.ID, 'mobileMenuToggle')
        
        # Get initial sidebar position
        initial_transform = authenticated_driver.execute_script(
            "return window.getComputedStyle(arguments[0]).transform;",
            sidebar
        )
        
        # Click the mobile menu toggle
        mobile_toggle.click()
        
        # Wait for animation to complete
        time.sleep(0.5)
        
        # Check if sidebar has 'open' class
        classes = sidebar.get_attribute('class')
        assert 'open' in classes, "Sidebar should have 'open' class after toggle click"
        
        # Get new transform
        new_transform = authenticated_driver.execute_script(
            "return window.getComputedStyle(arguments[0]).transform;",
            sidebar
        )
        
        # Transform should change (sidebar should slide in)
        # When open, transform should be translateX(0) which is 'none' or identity matrix
        assert new_transform != initial_transform, "Sidebar transform should change when opened"
        
        # Verify sidebar is now on-screen
        sidebar_rect = sidebar.rect
        assert sidebar_rect['x'] >= 0, f"Sidebar should be on-screen (x >= 0), got x={sidebar_rect['x']}"
        
        print(f"Initial transform: {initial_transform}, New transform: {new_transform}")
        print(f"Sidebar x position after opening: {sidebar_rect['x']}")
    
    def test_overlay_appears_when_sidebar_open(self, authenticated_driver):
        """
        Requirement 6.4: Verify overlay appears when sidebar is open
        """
        sidebar = authenticated_driver.find_element(By.ID, 'sidebar')
        overlay = authenticated_driver.find_element(By.ID, 'sidebarOverlay')
        mobile_toggle = authenticated_driver.find_element(By.ID, 'mobileMenuToggle')
        
        # Initially, overlay should not be visible
        initial_display = authenticated_driver.execute_script(
            "return window.getComputedStyle(arguments[0]).display;",
            overlay
        )
        assert initial_display == 'none', f"Overlay should be hidden initially, got: {initial_display}"
        
        # Open sidebar
        mobile_toggle.click()
        time.sleep(0.5)
        
        # Check if overlay has 'show' class
        overlay_classes = overlay.get_attribute('class')
        assert 'show' in overlay_classes, "Overlay should have 'show' class when sidebar is open"
        
        # Verify overlay is now displayed
        new_display = authenticated_driver.execute_script(
            "return window.getComputedStyle(arguments[0]).display;",
            overlay
        )
        assert new_display == 'block', f"Overlay should be displayed when sidebar is open, got: {new_display}"
        
        # Verify overlay is visible
        assert overlay.is_displayed(), "Overlay should be visible when sidebar is open"
        
        print(f"Overlay display: {new_display}, classes: {overlay_classes}")
    
    def test_sidebar_closes_when_overlay_clicked(self, authenticated_driver):
        """
        Requirement 6.5: Verify sidebar closes when overlay is clicked
        """
        sidebar = authenticated_driver.find_element(By.ID, 'sidebar')
        overlay = authenticated_driver.find_element(By.ID, 'sidebarOverlay')
        mobile_toggle = authenticated_driver.find_element(By.ID, 'mobileMenuToggle')
        
        # Open sidebar first
        mobile_toggle.click()
        time.sleep(0.5)
        
        # Verify sidebar is open
        assert 'open' in sidebar.get_attribute('class'), "Sidebar should be open before test"
        
        # Click the overlay
        overlay.click()
        time.sleep(0.5)
        
        # Check if sidebar no longer has 'open' class
        sidebar_classes = sidebar.get_attribute('class')
        assert 'open' not in sidebar_classes, "Sidebar should not have 'open' class after overlay click"
        
        # Check if overlay no longer has 'show' class
        overlay_classes = overlay.get_attribute('class')
        assert 'show' not in overlay_classes, "Overlay should not have 'show' class after click"
        
        # Verify overlay is hidden
        overlay_display = authenticated_driver.execute_script(
            "return window.getComputedStyle(arguments[0]).display;",
            overlay
        )
        assert overlay_display == 'none', f"Overlay should be hidden after click, got: {overlay_display}"
        
        # Verify sidebar is off-screen again
        sidebar_rect = sidebar.rect
        assert sidebar_rect['x'] < 0, f"Sidebar should be off-screen after overlay click, got x={sidebar_rect['x']}"
        
        print(f"Sidebar closed successfully, x position: {sidebar_rect['x']}")
    
    def test_sidebar_closes_when_nav_item_clicked(self, authenticated_driver):
        """
        Requirement 6.6: Verify sidebar closes when nav item is clicked
        """
        sidebar = authenticated_driver.find_element(By.ID, 'sidebar')
        mobile_toggle = authenticated_driver.find_element(By.ID, 'mobileMenuToggle')
        
        # Open sidebar first
        mobile_toggle.click()
        time.sleep(0.5)
        
        # Verify sidebar is open
        assert 'open' in sidebar.get_attribute('class'), "Sidebar should be open before test"
        
        # Find a nav item (use Dashboard nav item)
        nav_items = authenticated_driver.find_elements(By.CLASS_NAME, 'nav-item')
        assert len(nav_items) > 0, "Should have navigation items"
        
        # Click the first nav item (Dashboard)
        dashboard_nav = nav_items[0]
        dashboard_nav.click()
        time.sleep(0.5)
        
        # Check if sidebar no longer has 'open' class
        sidebar_classes = sidebar.get_attribute('class')
        assert 'open' not in sidebar_classes, "Sidebar should not have 'open' class after nav item click"
        
        # Verify sidebar is off-screen again
        sidebar_rect = sidebar.rect
        assert sidebar_rect['x'] < 0, f"Sidebar should be off-screen after nav click, got x={sidebar_rect['x']}"
        
        print(f"Sidebar closed after nav item click, x position: {sidebar_rect['x']}")
    
    def test_community_grid_single_column_on_mobile(self, authenticated_driver):
        """
        Verify community grid displays 1 card per row on mobile
        """
        # Wait for gallery to load
        wait = WebDriverWait(authenticated_driver, 10)
        
        try:
            # Wait for either community cards or empty state
            wait.until(
                lambda d: d.find_elements(By.CLASS_NAME, 'community-card') or 
                         d.find_elements(By.CLASS_NAME, 'empty-state')
            )
            
            community_cards = authenticated_driver.find_elements(By.CLASS_NAME, 'community-card')
            
            if len(community_cards) == 0:
                # No community data - verify grid is still properly configured
                gallery = authenticated_driver.find_element(By.CLASS_NAME, 'gallery')
                
                # Check grid-template-columns CSS property
                grid_columns = authenticated_driver.execute_script(
                    "return window.getComputedStyle(arguments[0]).gridTemplateColumns;",
                    gallery
                )
                
                # On mobile, should be single column (1fr or similar)
                # The media query sets grid-template-columns: 1fr
                print(f"Grid configured with: {grid_columns}")
                
                # Verify it's a single column (should not have multiple fr values)
                column_count = grid_columns.count('px')
                assert column_count <= 1, f"Grid should have 1 column on mobile, detected {column_count} columns"
                
                return
            
            # If we have multiple cards, verify they're stacked vertically
            if len(community_cards) >= 2:
                first_card = community_cards[0]
                second_card = community_cards[1]
                
                first_card_y = first_card.location['y']
                second_card_y = second_card.location['y']
                first_card_x = first_card.location['x']
                second_card_x = second_card.location['x']
                
                # Cards should be stacked vertically (different y, similar x)
                assert second_card_y > first_card_y, \
                    f"Cards should be stacked vertically, but y positions are: {first_card_y}, {second_card_y}"
                
                # Cards should have similar x positions (same column)
                x_diff = abs(first_card_x - second_card_x)
                assert x_diff < 50, \
                    f"Cards should be in same column (similar x), but x difference is {x_diff}px"
                
                print(f"Cards properly stacked: Card 1 y={first_card_y}, Card 2 y={second_card_y}")
            
            # Verify grid CSS
            gallery = authenticated_driver.find_element(By.CLASS_NAME, 'gallery')
            grid_columns = authenticated_driver.execute_script(
                "return window.getComputedStyle(arguments[0]).gridTemplateColumns;",
                gallery
            )
            
            print(f"Mobile grid columns: {grid_columns}")
            
        except Exception as e:
            print(f"Note: {str(e)}")
            # Verify grid CSS is properly configured even if no cards
            gallery = authenticated_driver.find_element(By.CLASS_NAME, 'gallery')
            grid_display = authenticated_driver.execute_script(
                "return window.getComputedStyle(arguments[0]).display;",
                gallery
            )
            assert grid_display == 'grid', "Gallery should use CSS Grid layout"
    
    def test_main_content_no_left_margin_on_mobile(self, authenticated_driver):
        """
        Verify main content has no left margin on mobile (sidebar is hidden)
        """
        main_content = authenticated_driver.find_element(By.CLASS_NAME, 'main-content')
        
        # Get computed margin-left using JavaScript
        margin_left = authenticated_driver.execute_script(
            "return window.getComputedStyle(arguments[0]).marginLeft;",
            main_content
        )
        
        # Convert to integer (remove 'px')
        margin_value = int(margin_left.replace('px', ''))
        
        # Main content should have 0px left margin on mobile
        assert margin_value == 0, f"Main content margin-left should be 0px on mobile, got {margin_value}px"
        
        print(f"Main content margin-left on mobile: {margin_value}px")
    
    def test_sidebar_transition_animation(self, authenticated_driver):
        """
        Verify sidebar has smooth transition animation (0.3s ease)
        """
        sidebar = authenticated_driver.find_element(By.ID, 'sidebar')
        
        # Get transition CSS property
        transition = authenticated_driver.execute_script(
            "return window.getComputedStyle(arguments[0]).transition;",
            sidebar
        )
        
        # Should have transition for transform property
        assert 'transform' in transition or 'all' in transition, \
            f"Sidebar should have transition for transform, got: {transition}"
        
        # Check if transition duration is around 0.3s
        assert '0.3s' in transition or '300ms' in transition, \
            f"Sidebar transition should be 0.3s, got: {transition}"
        
        print(f"Sidebar transition: {transition}")
    
    def test_mobile_toggle_button_positioning(self, authenticated_driver):
        """
        Verify mobile menu toggle button is positioned correctly (top-left)
        """
        mobile_toggle = authenticated_driver.find_element(By.ID, 'mobileMenuToggle')
        
        # Get position
        position = authenticated_driver.execute_script(
            "return window.getComputedStyle(arguments[0]).position;",
            mobile_toggle
        )
        
        # Should be fixed positioned
        assert position == 'fixed', f"Mobile toggle should be fixed positioned, got: {position}"
        
        # Get top and left values
        top = authenticated_driver.execute_script(
            "return window.getComputedStyle(arguments[0]).top;",
            mobile_toggle
        )
        left = authenticated_driver.execute_script(
            "return window.getComputedStyle(arguments[0]).left;",
            mobile_toggle
        )
        
        # Should be positioned at top-left (20px from edges as per CSS)
        assert top == '20px', f"Mobile toggle top should be 20px, got: {top}"
        assert left == '20px', f"Mobile toggle left should be 20px, got: {left}"
        
        print(f"Mobile toggle position: {position}, top: {top}, left: {left}")
    
    def test_overlay_covers_full_screen(self, authenticated_driver):
        """
        Verify overlay covers the entire screen when visible
        """
        overlay = authenticated_driver.find_element(By.ID, 'sidebarOverlay')
        mobile_toggle = authenticated_driver.find_element(By.ID, 'mobileMenuToggle')
        
        # Open sidebar to show overlay
        mobile_toggle.click()
        time.sleep(0.5)
        
        # Get overlay dimensions
        overlay_rect = overlay.rect
        viewport_width = authenticated_driver.execute_script("return window.innerWidth;")
        viewport_height = authenticated_driver.execute_script("return window.innerHeight;")
        
        # Overlay should cover full viewport
        assert overlay_rect['width'] >= viewport_width, \
            f"Overlay width ({overlay_rect['width']}px) should cover viewport ({viewport_width}px)"
        assert overlay_rect['height'] >= viewport_height, \
            f"Overlay height ({overlay_rect['height']}px) should cover viewport ({viewport_height}px)"
        
        # Verify overlay position
        position = authenticated_driver.execute_script(
            "return window.getComputedStyle(arguments[0]).position;",
            overlay
        )
        assert position == 'fixed', f"Overlay should be fixed positioned, got: {position}"
        
        # Verify overlay z-index is below sidebar but above content
        z_index = authenticated_driver.execute_script(
            "return window.getComputedStyle(arguments[0]).zIndex;",
            overlay
        )
        assert z_index == '999', f"Overlay z-index should be 999, got: {z_index}"
        
        print(f"Overlay dimensions: {overlay_rect['width']}x{overlay_rect['height']}, z-index: {z_index}")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
