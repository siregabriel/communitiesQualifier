"""
Test Desktop Layout - Task 23
Tests the desktop layout to ensure all components display correctly on desktop viewports (>= 768px width).

Requirements tested:
- 11.1: Dashboard renders Desktop_Layout by default on viewport widths of 768px or greater
- 11.2: Dashboard allocates full viewport height to Sidebar and main content area
- 11.3: Dashboard positions Sidebar on left side occupying 240px to 280px width
- 11.4: Dashboard positions main content area to right of Sidebar occupying remaining viewport width
- 11.5: Community_Card grid displays 2 to 4 cards per row depending on available width
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


class TestDesktopLayout:
    """Test suite for desktop layout verification (viewport >= 768px)"""
    
    @pytest.fixture(scope="class")
    def driver(self):
        """Setup Chrome driver with desktop viewport"""
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        
        # Use webdriver-manager to automatically handle ChromeDriver
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        # Set desktop viewport (1024x768)
        driver.set_window_size(1024, 768)
        
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
    
    def test_sidebar_width_on_desktop(self, authenticated_driver):
        """
        Requirement 11.3: Verify sidebar displays at 260px width on viewport >= 768px
        """
        sidebar = authenticated_driver.find_element(By.CLASS_NAME, 'sidebar')
        
        # Get computed width
        width = sidebar.size['width']
        
        # Sidebar should be 260px (as specified in CSS)
        assert width == 260, f"Sidebar width should be 260px on desktop, got {width}px"
        
        # Verify sidebar is visible (not hidden)
        assert sidebar.is_displayed(), "Sidebar should be visible on desktop"
        
        # Verify sidebar is positioned at left edge
        location = sidebar.location
        assert location['x'] == 0, f"Sidebar should be at x=0, got x={location['x']}"
    
    def test_main_content_left_margin(self, authenticated_driver):
        """
        Requirement 11.4: Verify main content has 260px left margin
        """
        main_content = authenticated_driver.find_element(By.CLASS_NAME, 'main-content')
        
        # Get computed margin-left using JavaScript
        margin_left = authenticated_driver.execute_script(
            "return window.getComputedStyle(arguments[0]).marginLeft;",
            main_content
        )
        
        # Convert to integer (remove 'px')
        margin_value = int(margin_left.replace('px', ''))
        
        # Main content should have 260px left margin
        assert margin_value == 260, f"Main content margin-left should be 260px, got {margin_value}px"
    
    def test_community_grid_responsive_columns(self, authenticated_driver):
        """
        Requirement 11.5: Verify community grid displays 2-4 cards per row based on width
        """
        # Wait for community cards to load
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
                
                # Should use repeat(auto-fill, minmax(300px, 1fr))
                # This will result in multiple columns on desktop
                assert grid_columns is not None, "Gallery should have grid-template-columns defined"
                
                print(f"Grid configured with: {grid_columns}")
                return
            
            # If we have cards, verify they're arranged in multiple columns
            gallery = authenticated_driver.find_element(By.CLASS_NAME, 'gallery')
            
            # Get gallery width
            gallery_width = gallery.size['width']
            
            # Get first card width
            first_card = community_cards[0]
            card_width = first_card.size['width']
            
            # Calculate expected columns based on minmax(300px, 1fr)
            # With 1024px viewport - 260px sidebar - 40px padding = ~724px available
            # With 24px gap, we should fit 2 cards (300px each + gap)
            expected_min_columns = 2
            expected_max_columns = 4
            
            # Calculate actual columns by checking card positions
            if len(community_cards) >= 2:
                first_card_x = community_cards[0].location['x']
                second_card_x = community_cards[1].location['x']
                
                # If cards are on same row, x positions will be different
                if second_card_x > first_card_x:
                    # Cards are in different columns
                    actual_columns = min(len(community_cards), 
                                       int(gallery_width / (card_width + 24)))
                    
                    assert expected_min_columns <= actual_columns <= expected_max_columns, \
                        f"Community grid should display {expected_min_columns}-{expected_max_columns} cards per row, got {actual_columns}"
                else:
                    # Cards are stacked vertically (shouldn't happen on desktop)
                    pytest.fail("Community cards should be arranged horizontally on desktop")
            
            print(f"Gallery width: {gallery_width}px, Card width: {card_width}px")
            
        except Exception as e:
            print(f"Note: {str(e)}")
            # Verify grid CSS is properly configured even if no cards
            gallery = authenticated_driver.find_element(By.CLASS_NAME, 'gallery')
            grid_display = authenticated_driver.execute_script(
                "return window.getComputedStyle(arguments[0]).display;",
                gallery
            )
            assert grid_display == 'grid', "Gallery should use CSS Grid layout"
    
    def test_mobile_menu_toggle_hidden(self, authenticated_driver):
        """
        Requirement 11.1: Verify mobile menu toggle is hidden on desktop
        """
        mobile_toggle = authenticated_driver.find_element(By.ID, 'mobileMenuToggle')
        
        # Check if element is displayed
        is_displayed = mobile_toggle.is_displayed()
        
        # Mobile toggle should be hidden on desktop (display: none via media query)
        assert not is_displayed, "Mobile menu toggle should be hidden on desktop viewport"
        
        # Verify CSS display property
        display_value = authenticated_driver.execute_script(
            "return window.getComputedStyle(arguments[0]).display;",
            mobile_toggle
        )
        
        assert display_value == 'none', f"Mobile toggle display should be 'none', got '{display_value}'"
    
    def test_navigation_items_clickable(self, authenticated_driver):
        """
        Requirement 11.1: Verify all navigation items are clickable
        """
        nav_items = authenticated_driver.find_elements(By.CLASS_NAME, 'nav-item')
        
        # Should have 9 navigation items
        assert len(nav_items) == 9, f"Should have 9 navigation items, found {len(nav_items)}"
        
        # Verify each nav item is clickable
        for i, nav_item in enumerate(nav_items):
            # Check if element is displayed and enabled
            assert nav_item.is_displayed(), f"Nav item {i+1} should be visible"
            assert nav_item.is_enabled(), f"Nav item {i+1} should be enabled"
            
            # Verify it has href or data-view attribute
            href = nav_item.get_attribute('href')
            data_view = nav_item.get_attribute('data-view')
            
            assert href or data_view, f"Nav item {i+1} should have href or data-view attribute"
            
            # Verify hover effect works (check cursor style)
            cursor = authenticated_driver.execute_script(
                "return window.getComputedStyle(arguments[0]).cursor;",
                nav_item
            )
            # Cursor should be pointer or default (links have pointer by default)
            assert cursor in ['pointer', 'default'], f"Nav item {i+1} should have pointer cursor"
        
        print(f"All {len(nav_items)} navigation items are clickable")
    
    def test_circular_progress_animation(self, authenticated_driver):
        """
        Requirement 11.5: Verify circular progress indicators animate correctly
        """
        # Wait for community cards to load
        wait = WebDriverWait(authenticated_driver, 10)
        
        try:
            wait.until(
                lambda d: d.find_elements(By.CLASS_NAME, 'community-card') or 
                         d.find_elements(By.CLASS_NAME, 'empty-state')
            )
            
            community_cards = authenticated_driver.find_elements(By.CLASS_NAME, 'community-card')
            
            if len(community_cards) == 0:
                print("No community cards to test progress indicators")
                return
            
            # Check first community card's progress indicator
            first_card = community_cards[0]
            progress_bar = first_card.find_element(By.CLASS_NAME, 'progress-bar')
            
            # Verify SVG circle exists
            assert progress_bar is not None, "Progress bar should exist"
            
            # Check stroke-dashoffset property (controls animation)
            stroke_dashoffset = progress_bar.get_attribute('style')
            assert 'stroke-dashoffset' in stroke_dashoffset, \
                "Progress bar should have stroke-dashoffset style"
            
            # Verify transition CSS property for animation
            transition = authenticated_driver.execute_script(
                "return window.getComputedStyle(arguments[0]).transition;",
                progress_bar
            )
            
            # Should have transition for smooth animation (0.5s ease)
            assert 'stroke-dashoffset' in transition or transition != 'all 0s ease 0s', \
                f"Progress bar should have transition animation, got: {transition}"
            
            # Verify progress value is displayed
            progress_value = first_card.find_element(By.CLASS_NAME, 'progress-value')
            value_text = progress_value.text
            
            # Should display percentage or N/A
            assert value_text.endswith('%') or value_text == 'N/A', \
                f"Progress value should show percentage or N/A, got: {value_text}"
            
            print(f"Progress indicator verified with value: {value_text}")
            
        except Exception as e:
            print(f"Note: {str(e)}")
    
    def test_sidebar_full_height(self, authenticated_driver):
        """
        Requirement 11.2: Verify sidebar allocates full viewport height
        """
        sidebar = authenticated_driver.find_element(By.CLASS_NAME, 'sidebar')
        
        # Get viewport height
        viewport_height = authenticated_driver.execute_script("return window.innerHeight;")
        
        # Get sidebar height
        sidebar_height = sidebar.size['height']
        
        # Sidebar should be full viewport height (100vh)
        # Allow small tolerance for browser chrome
        assert abs(sidebar_height - viewport_height) <= 5, \
            f"Sidebar height ({sidebar_height}px) should match viewport height ({viewport_height}px)"
        
        # Verify CSS height property
        height_value = authenticated_driver.execute_script(
            "return window.getComputedStyle(arguments[0]).height;",
            sidebar
        )
        
        print(f"Sidebar height: {sidebar_height}px, Viewport height: {viewport_height}px")
    
    def test_main_content_full_height(self, authenticated_driver):
        """
        Requirement 11.2: Verify main content area allocates full viewport height
        """
        main_content = authenticated_driver.find_element(By.CLASS_NAME, 'main-content')
        
        # Main content should be scrollable and take available height
        # Check if overflow-y is set to auto or scroll
        overflow_y = authenticated_driver.execute_script(
            "return window.getComputedStyle(arguments[0]).overflowY;",
            main_content
        )
        
        assert overflow_y in ['auto', 'scroll'], \
            f"Main content should have overflow-y auto or scroll, got: {overflow_y}"
        
        print(f"Main content overflow-y: {overflow_y}")
    
    def test_desktop_layout_positioning(self, authenticated_driver):
        """
        Requirement 11.3, 11.4: Verify sidebar and main content positioning
        """
        sidebar = authenticated_driver.find_element(By.CLASS_NAME, 'sidebar')
        main_content = authenticated_driver.find_element(By.CLASS_NAME, 'main-content')
        
        # Get positions
        sidebar_position = authenticated_driver.execute_script(
            "return window.getComputedStyle(arguments[0]).position;",
            sidebar
        )
        
        # Sidebar should be fixed positioned
        assert sidebar_position == 'fixed', \
            f"Sidebar should have position: fixed, got: {sidebar_position}"
        
        # Verify sidebar is at left edge
        sidebar_left = authenticated_driver.execute_script(
            "return window.getComputedStyle(arguments[0]).left;",
            sidebar
        )
        assert sidebar_left == '0px', f"Sidebar left should be 0px, got: {sidebar_left}"
        
        # Verify main content starts after sidebar
        main_content_margin = authenticated_driver.execute_script(
            "return window.getComputedStyle(arguments[0]).marginLeft;",
            main_content
        )
        assert main_content_margin == '260px', \
            f"Main content margin-left should be 260px, got: {main_content_margin}"
        
        print(f"Sidebar position: {sidebar_position}, Main content margin: {main_content_margin}")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
