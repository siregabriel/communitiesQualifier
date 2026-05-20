# Requirements Document

## Introduction

This document specifies the requirements for redesigning the admin dashboard with ATLAS-style sidebar navigation. The redesign transforms the current horizontal header-based dashboard into a modern sidebar navigation layout with improved visual hierarchy, user experience, and mobile responsiveness. The new design features a persistent left sidebar with navigation menu, user welcome section, and a main content area displaying community cards with circular progress indicators and action item counts.

## Glossary

- **Dashboard**: The admin interface for viewing maintenance reports and inspection submissions
- **Sidebar**: The persistent left navigation panel containing logo, user info, and menu items
- **Community_Card**: A visual card component displaying community information, visit data, score, and action items
- **Navigation_Menu**: The list of clickable menu items in the sidebar for navigating between dashboard sections
- **Progress_Indicator**: A circular visual element showing the community score as a percentage
- **Action_Item**: An inspection response or maintenance report requiring attention (Fail, Opportunity, or Needs Attention condition)
- **Session**: The Flask session object containing authenticated user data (username, community, is_admin)
- **Admin_User**: A user with community set to None who can view all communities and access all features
- **Staff_User**: A user assigned to a specific community who can only view their own community data
- **Mobile_Layout**: The responsive layout displayed on screens narrower than 768px with collapsible sidebar
- **Desktop_Layout**: The default layout displayed on screens 768px or wider with persistent sidebar

## Requirements

### Requirement 1: Sidebar Navigation Structure

**User Story:** As an admin user, I want a persistent sidebar navigation, so that I can quickly access different dashboard sections without scrolling.

#### Acceptance Criteria

1. THE Dashboard SHALL render a left sidebar with dark background color (#1e293b or similar)
2. THE Sidebar SHALL display the application logo at the top
3. THE Sidebar SHALL display a user welcome message showing the authenticated username from Session
4. THE Sidebar SHALL contain a Navigation_Menu with exactly 9 menu items in order: Dashboard, My Visits, Communities, Standards, Reports, Action Items, Resources, Settings, Log Out
5. THE Navigation_Menu SHALL display an icon for each menu item using Font Awesome or similar icon library
6. WHEN a Navigation_Menu item is clicked, THE Dashboard SHALL navigate to the corresponding route or trigger the corresponding action
7. THE Sidebar SHALL have a fixed width of 240px to 280px on Desktop_Layout
8. THE Sidebar SHALL maintain its position when the main content area is scrolled

### Requirement 2: Community Card Redesign

**User Story:** As an admin user, I want to see community information in visually enhanced cards, so that I can quickly assess community status and recent activity.

#### Acceptance Criteria

1. THE Dashboard SHALL display Community_Card components in a responsive grid layout
2. THE Community_Card SHALL display a community photo at the top with dimensions of at least 200px height
3. THE Community_Card SHALL display the community name as a prominent heading
4. THE Community_Card SHALL display the last visit date in a readable format (e.g., "May 8, 2024")
5. THE Community_Card SHALL display a Progress_Indicator showing the community score as a percentage
6. THE Progress_Indicator SHALL be rendered as a circular element with the percentage value centered inside
7. THE Community_Card SHALL display the count of open Action_Item entries for that community
8. THE Community_Card SHALL use consistent spacing, typography, and visual hierarchy matching the ATLAS design style

### Requirement 3: Community Score Calculation

**User Story:** As an admin user, I want to see an accurate community score, so that I can evaluate overall community performance.

#### Acceptance Criteria

1. WHEN calculating a community score, THE Dashboard SHALL retrieve all inspection responses for that community from the most recent submission
2. THE Dashboard SHALL assign point values to each condition: Excellence = 100, Pass = 75, Opportunity = 50, Fail = 0
3. THE Dashboard SHALL calculate the average score across all responses in the most recent submission
4. THE Dashboard SHALL round the calculated score to the nearest whole number
5. THE Progress_Indicator SHALL display the calculated score as a percentage value
6. IF no inspection submissions exist for a community, THEN THE Dashboard SHALL display "N/A" or 0% in the Progress_Indicator

### Requirement 4: Action Items Count

**User Story:** As an admin user, I want to see the number of open action items per community, so that I can prioritize follow-up work.

#### Acceptance Criteria

1. WHEN counting Action_Item entries for a community, THE Dashboard SHALL retrieve all inspection responses with condition "Fail", "Opportunity", or "Needs Attention"
2. THE Dashboard SHALL count only responses from the most recent inspection submission for that community
3. THE Community_Card SHALL display the Action_Item count as a numeric value with label "Open Actions"
4. IF the Action_Item count is zero, THEN THE Community_Card SHALL display "0 Open Actions"
5. IF the Action_Item count is greater than zero, THEN THE Community_Card SHALL visually emphasize the count using color or styling

### Requirement 5: Start New Visit Button

**User Story:** As a staff user, I want to start a new inspection visit from the dashboard, so that I can quickly begin data collection.

#### Acceptance Criteria

1. THE Dashboard SHALL display a "Start New Visit" button at the bottom of the main content area
2. WHEN the "Start New Visit" button is clicked, THE Dashboard SHALL navigate to the inspection form route (/reporte)
3. THE "Start New Visit" button SHALL use prominent styling with high contrast colors
4. THE "Start New Visit" button SHALL be accessible via keyboard navigation
5. WHERE the user is an Admin_User, THE Dashboard SHALL display the "Start New Visit" button

### Requirement 6: Responsive Mobile Layout

**User Story:** As an admin user on a mobile device, I want the sidebar to collapse into a hamburger menu, so that I can view content on smaller screens.

#### Acceptance Criteria

1. WHEN the viewport width is less than 768px, THE Dashboard SHALL hide the Sidebar by default
2. WHEN the viewport width is less than 768px, THE Dashboard SHALL display a hamburger menu icon in the top-left corner
3. WHEN the hamburger menu icon is clicked, THE Dashboard SHALL slide the Sidebar into view from the left edge
4. WHEN the Sidebar is open in Mobile_Layout, THE Dashboard SHALL display a close icon or overlay to dismiss the Sidebar
5. WHEN the overlay is clicked or a Navigation_Menu item is selected, THE Dashboard SHALL hide the Sidebar
6. THE Mobile_Layout SHALL maintain all Sidebar functionality including navigation and user information

### Requirement 7: User Welcome Section

**User Story:** As an authenticated user, I want to see my name and role displayed in the sidebar, so that I can confirm I'm logged in with the correct account.

#### Acceptance Criteria

1. THE Sidebar SHALL display a welcome message in the format "Welcome back, [username]"
2. THE Sidebar SHALL retrieve the username from the Session object
3. WHERE the user is an Admin_User, THE Sidebar SHALL display "Admin" or similar role indicator below the username
4. WHERE the user is a Staff_User, THE Sidebar SHALL display the assigned community name below the username
5. THE welcome section SHALL be positioned below the logo and above the Navigation_Menu

### Requirement 8: Navigation Menu Routing

**User Story:** As an admin user, I want navigation menu items to route to the correct pages, so that I can access different dashboard features.

#### Acceptance Criteria

1. WHEN the "Dashboard" menu item is clicked, THE Dashboard SHALL navigate to the main dashboard view showing Community_Card components
2. WHEN the "My Visits" menu item is clicked, THE Dashboard SHALL navigate to a view showing the current user's inspection submissions
3. WHEN the "Communities" menu item is clicked, THE Dashboard SHALL navigate to a view listing all communities
4. WHEN the "Standards" menu item is clicked, THE Dashboard SHALL navigate to the Question Manager route (/questions/manage)
5. WHEN the "Reports" menu item is clicked, THE Dashboard SHALL navigate to a view showing all maintenance reports and inspections
6. WHEN the "Action Items" menu item is clicked, THE Dashboard SHALL navigate to a filtered view showing only Action_Item entries
7. WHEN the "Resources" menu item is clicked, THE Dashboard SHALL navigate to a resources or documentation page
8. WHEN the "Settings" menu item is clicked, THE Dashboard SHALL navigate to a user settings page
9. WHEN the "Log Out" menu item is clicked, THE Dashboard SHALL call the logout route (/logout) and clear the Session

### Requirement 9: Backward Compatibility

**User Story:** As a system administrator, I want the redesigned dashboard to maintain existing functionality, so that no features are lost during the redesign.

#### Acceptance Criteria

1. THE Dashboard SHALL continue to display both maintenance reports and inspection submissions
2. THE Dashboard SHALL continue to support filtering by report type (maintenance, inspection, all)
3. THE Dashboard SHALL continue to support filtering by condition (Excellence, Pass, Opportunity, Fail, Good, Needs Attention)
4. THE Dashboard SHALL continue to enforce authentication using the @login_required decorator
5. THE Dashboard SHALL continue to restrict Question Manager access to Admin_User accounts
6. THE Dashboard SHALL continue to retrieve user information from the Session object
7. THE Dashboard SHALL continue to use the existing Flask routes and API endpoints

### Requirement 10: Visual Design Consistency

**User Story:** As an admin user, I want the dashboard to match the ATLAS design style, so that the interface feels cohesive and professional.

#### Acceptance Criteria

1. THE Dashboard SHALL use a dark sidebar background color (e.g., #1e293b, #0f172a, or similar)
2. THE Dashboard SHALL use white or light gray text color for sidebar content for sufficient contrast
3. THE Navigation_Menu SHALL highlight the active menu item with a background color or border indicator
4. THE Navigation_Menu items SHALL display hover effects when the cursor is over them
5. THE Community_Card components SHALL use rounded corners (border-radius of 12px to 16px)
6. THE Community_Card components SHALL use subtle shadows for depth (box-shadow with low opacity)
7. THE Dashboard SHALL use consistent spacing between components (16px to 24px gaps)
8. THE Dashboard SHALL use a modern sans-serif font family (e.g., Inter, Poppins, or system fonts)

### Requirement 11: Desktop-First Design Approach

**User Story:** As a system administrator, I want the dashboard optimized for desktop use, so that admin users have the best experience on their primary work devices.

#### Acceptance Criteria

1. THE Dashboard SHALL render the Desktop_Layout by default on viewport widths of 768px or greater
2. THE Dashboard SHALL allocate the full viewport height to the Sidebar and main content area
3. THE Dashboard SHALL position the Sidebar on the left side occupying 240px to 280px width
4. THE Dashboard SHALL position the main content area to the right of the Sidebar occupying the remaining viewport width
5. THE Community_Card grid SHALL display 2 to 4 cards per row depending on available width
6. THE Dashboard SHALL prioritize readability and information density appropriate for desktop screens

### Requirement 12: Community Data Integration

**User Story:** As an admin user, I want community cards to display real data from the system, so that I can make informed decisions based on actual inspection results.

#### Acceptance Criteria

1. WHEN rendering Community_Card components, THE Dashboard SHALL retrieve inspection submissions from the InspectionService
2. THE Dashboard SHALL retrieve the list of communities from the ALL_COMMUNITIES constant or database
3. WHERE the user is a Staff_User, THE Dashboard SHALL filter Community_Card components to show only the user's assigned community
4. WHERE the user is an Admin_User, THE Dashboard SHALL display Community_Card components for all communities
5. THE Dashboard SHALL retrieve the most recent inspection submission for each community to calculate scores and action items
6. IF a community has no inspection submissions, THEN THE Community_Card SHALL display placeholder values for score and last visit date
