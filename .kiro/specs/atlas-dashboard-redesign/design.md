# Design Document: ATLAS Dashboard Redesign

## Overview

This design document specifies the technical architecture for redesigning the admin dashboard with ATLAS-style sidebar navigation. The redesign transforms the current horizontal header-based layout into a modern sidebar navigation system with community cards featuring circular progress indicators and action item counts.

## Architecture

### Component Hierarchy

```
Dashboard (dashboard.html)
├── Sidebar
│   ├── Logo
│   ├── UserWelcome
│   └── NavigationMenu (9 items)
├── MainContent
│   ├── CommunityGrid
│   │   └── CommunityCard[] (multiple)
│   │       ├── CommunityPhoto
│   │       ├── CommunityName
│   │       ├── LastVisitDate
│   │       ├── CircularProgressIndicator
│   │       └── ActionItemsCount
│   └── StartNewVisitButton
└── MobileMenuToggle (hamburger icon)
```

### Data Flow

```
1. Page Load
   └─> loadUserInfo()
       └─> fetch('/api/user-info')
           └─> Display username, role in Sidebar
           └─> loadCommunityData()
               └─> fetch('/api/inspections')
                   └─> Process inspection data
                       ├─> calculateCommunityScores()
                       ├─> countActionItems()
                       └─> renderCommunityCards()

2. Navigation Click
   └─> handleNavigation(menuItem)
       └─> Update active state
       └─> Navigate to route or filter view

3. Mobile Menu Toggle
   └─> toggleSidebar()
       └─> Add/remove 'open' class
       └─> Show/hide overlay
```

## HTML Structure

### Sidebar Component

```html
<div class="sidebar" id="sidebar">
  <div class="sidebar-logo">
    <img src="/static/icon-192.png" alt="Logo">
    <span>ATLAS</span>
  </div>
  
  <div class="user-welcome">
    <div class="welcome-text">Welcome back, <span id="userName"></span></div>
    <div class="user-role" id="userRole"></div>
  </div>
  
  <nav class="navigation-menu">
    <a href="#" class="nav-item active" data-view="dashboard">
      <i class="fas fa-home"></i>
      <span>Dashboard</span>
    </a>
    <a href="#" class="nav-item" data-view="my-visits">
      <i class="fas fa-file-alt"></i>
      <span>My Visits</span>
    </a>
    <a href="#" class="nav-item" data-view="communities">
      <i class="fas fa-building"></i>
      <span>Communities</span>
    </a>
    <a href="/questions/manage" class="nav-item" id="standardsLink">
      <i class="fas fa-clipboard-check"></i>
      <span>Standards</span>
    </a>
    <a href="#" class="nav-item" data-view="reports">
      <i class="fas fa-chart-bar"></i>
      <span>Reports</span>
    </a>
    <a href="#" class="nav-item" data-view="action-items">
      <i class="fas fa-check-circle"></i>
      <span>Action Items</span>
    </a>
    <a href="#" class="nav-item" data-view="resources">
      <i class="fas fa-book"></i>
      <span>Resources</span>
    </a>
    <a href="#" class="nav-item" data-view="settings">
      <i class="fas fa-cog"></i>
      <span>Settings</span>
    </a>
    <a href="/logout" class="nav-item">
      <i class="fas fa-sign-out-alt"></i>
      <span>Log Out</span>
    </a>
  </nav>
</div>
```

### Main Content Component

```html
<div class="main-content">
  <button class="mobile-menu-toggle" id="mobileMenuToggle">
    <i class="fas fa-bars"></i>
  </button>
  
  <div class="content-header">
    <h1>Dashboard</h1>
    <p>Community Performance Overview</p>
  </div>
  
  <div class="community-grid" id="communityGrid">
    <!-- Community cards will be rendered here -->
  </div>
  
  <button class="start-visit-btn" onclick="location.href='/'">
    <i class="fas fa-plus"></i>
    Start New Visit
  </button>
</div>

<div class="sidebar-overlay" id="sidebarOverlay"></div>
```

### Community Card Template

```html
<div class="community-card">
  <div class="card-image">
    <img src="{photoUrl}" alt="{communityName}">
  </div>
  <div class="card-content">
    <h3 class="card-title">{communityName}</h3>
    <p class="card-date">Last visit: {lastVisitDate}</p>
    
    <div class="circular-progress">
      <svg viewBox="0 0 100 100">
        <circle class="progress-bg" cx="50" cy="50" r="45"></circle>
        <circle class="progress-bar" cx="50" cy="50" r="45" 
                style="stroke-dashoffset: {offset}"></circle>
      </svg>
      <div class="progress-value">{score}%</div>
    </div>
    
    <div class="action-items {emphasisClass}">
      <i class="fas fa-exclamation-circle"></i>
      <span>{count} Open Actions</span>
    </div>
  </div>
</div>
```

## CSS Layout

### Grid System

```css
body {
  display: flex;
  height: 100vh;
  margin: 0;
  font-family: 'Inter', sans-serif;
}

.sidebar {
  width: 260px;
  background: #1e293b;
  color: white;
  display: flex;
  flex-direction: column;
  position: fixed;
  left: 0;
  top: 0;
  height: 100vh;
  overflow-y: auto;
  z-index: 1000;
}

.main-content {
  margin-left: 260px;
  flex: 1;
  padding: 40px;
  background: #f5f7fa;
  overflow-y: auto;
}

.community-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 24px;
  margin-top: 32px;
}
```

### Circular Progress Indicator

```css
.circular-progress {
  position: relative;
  width: 120px;
  height: 120px;
  margin: 20px auto;
}

.circular-progress svg {
  transform: rotate(-90deg);
}

.progress-bg {
  fill: none;
  stroke: #e5e7eb;
  stroke-width: 8;
}

.progress-bar {
  fill: none;
  stroke: #10b981;
  stroke-width: 8;
  stroke-linecap: round;
  stroke-dasharray: 283; /* 2 * π * 45 */
  transition: stroke-dashoffset 0.5s ease;
}

.progress-value {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  font-size: 24px;
  font-weight: 700;
  color: #111827;
}
```

### Mobile Responsive

```css
@media (max-width: 767px) {
  .sidebar {
    transform: translateX(-100%);
    transition: transform 0.3s ease;
  }
  
  .sidebar.open {
    transform: translateX(0);
  }
  
  .main-content {
    margin-left: 0;
  }
  
  .mobile-menu-toggle {
    display: block;
    position: fixed;
    top: 20px;
    left: 20px;
    z-index: 999;
  }
  
  .sidebar-overlay {
    display: none;
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.5);
    z-index: 999;
  }
  
  .sidebar-overlay.show {
    display: block;
  }
  
  .community-grid {
    grid-template-columns: 1fr;
  }
}

@media (min-width: 768px) {
  .mobile-menu-toggle {
    display: none;
  }
}
```

## JavaScript Modules

### Score Calculation Algorithm

```javascript
function calculateCommunityScore(responses) {
  if (!responses || responses.length === 0) {
    return null;
  }
  
  const scoreMap = {
    'Excellence': 100,
    'Pass': 75,
    'Opportunity': 50,
    'Fail': 0
  };
  
  let totalScore = 0;
  let count = 0;
  
  responses.forEach(response => {
    if (scoreMap.hasOwnProperty(response.condition)) {
      totalScore += scoreMap[response.condition];
      count++;
    }
  });
  
  return count > 0 ? Math.round(totalScore / count) : 0;
}
```

### Action Items Counter

```javascript
function countActionItems(responses) {
  if (!responses || responses.length === 0) {
    return 0;
  }
  
  const actionConditions = ['Fail', 'Opportunity', 'Needs Attention'];
  
  return responses.filter(response => 
    actionConditions.includes(response.condition)
  ).length;
}
```

### Community Data Processor

```javascript
async function loadCommunityData() {
  try {
    // Fetch all inspection submissions
    const response = await fetch('/api/inspections');
    const data = await response.json();
    
    if (data.status !== 'success') {
      throw new Error('Failed to load inspections');
    }
    
    // Group submissions by community
    const communityMap = {};
    
    data.submissions.forEach(submission => {
      const community = submission.community;
      
      if (!communityMap[community]) {
        communityMap[community] = {
          name: community,
          submissions: []
        };
      }
      
      communityMap[community].submissions.push(submission);
    });
    
    // Process each community
    const communityData = [];
    
    for (const [communityName, data] of Object.entries(communityMap)) {
      // Get most recent submission
      const sortedSubmissions = data.submissions.sort((a, b) => 
        new Date(b.submitted_at) - new Date(a.submitted_at)
      );
      
      const latestSubmission = sortedSubmissions[0];
      
      // Calculate score and action items
      const score = calculateCommunityScore(latestSubmission.responses);
      const actionItems = countActionItems(latestSubmission.responses);
      
      communityData.push({
        name: communityName,
        lastVisit: formatDate(latestSubmission.submitted_at),
        score: score,
        actionItems: actionItems,
        photoUrl: getRandomCommunityPhoto()
      });
    }
    
    // Render community cards
    renderCommunityCards(communityData);
    
  } catch (error) {
    console.error('Error loading community data:', error);
  }
}
```

### Navigation Handler

```javascript
function handleNavigation(view) {
  // Update active state
  document.querySelectorAll('.nav-item').forEach(item => {
    item.classList.remove('active');
  });
  
  event.target.closest('.nav-item').classList.add('active');
  
  // Handle view switching
  switch(view) {
    case 'dashboard':
      showDashboardView();
      break;
    case 'my-visits':
      showMyVisitsView();
      break;
    case 'communities':
      showCommunitiesView();
      break;
    case 'reports':
      showReportsView();
      break;
    case 'action-items':
      showActionItemsView();
      break;
    case 'resources':
      showResourcesView();
      break;
    case 'settings':
      showSettingsView();
      break;
  }
  
  // Close mobile menu if open
  if (window.innerWidth < 768) {
    closeSidebar();
  }
}
```

### Mobile Menu Toggle

```javascript
function toggleSidebar() {
  const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('sidebarOverlay');
  
  sidebar.classList.toggle('open');
  overlay.classList.toggle('show');
}

function closeSidebar() {
  const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('sidebarOverlay');
  
  sidebar.classList.remove('open');
  overlay.classList.remove('show');
}

// Event listeners
document.getElementById('mobileMenuToggle').addEventListener('click', toggleSidebar);
document.getElementById('sidebarOverlay').addEventListener('click', closeSidebar);

// Close sidebar on window resize to desktop
window.addEventListener('resize', () => {
  if (window.innerWidth >= 768) {
    closeSidebar();
  }
});
```

## Integration Points

### Flask Routes

- **GET /dashboard**: Render dashboard.html template
- **GET /api/user-info**: Return current user session data
- **GET /api/inspections**: Return all inspection submissions (filtered by user role)
- **GET /questions/manage**: Question Manager (admin only)
- **GET /logout**: Clear session and redirect to login

### Session Data

```python
session = {
    'user': 'john',
    'community': 'Community A',  # None for admin users
    'is_admin': False
}
```

### API Response Format

```json
{
  "status": "success",
  "submissions": [
    {
      "id": "sub_123",
      "username": "john",
      "community": "Community A",
      "submitted_at": "2024-05-08T10:30:00Z",
      "responses": [
        {
          "question_id": "q_1",
          "question_text": "Are hallways clean?",
          "condition": "Excellence",
          "description": "Spotless",
          "photo_path": "static/uploads/Community_A/photo.jpg",
          "answered_at": "2024-05-08T10:25:00Z"
        }
      ]
    }
  ]
}
```

## Performance Considerations

1. **Lazy Loading**: Load community photos on scroll for large community lists
2. **Caching**: Cache inspection data for 5 minutes to reduce API calls
3. **Debouncing**: Debounce window resize events for mobile menu handling
4. **Progressive Enhancement**: Ensure basic functionality works without JavaScript

## Accessibility

1. **Keyboard Navigation**: All nav items accessible via Tab key
2. **ARIA Labels**: Add aria-label to icon-only buttons
3. **Focus Indicators**: Visible focus states for all interactive elements
4. **Color Contrast**: Minimum 4.5:1 contrast ratio for text
5. **Screen Reader Support**: Semantic HTML with proper heading hierarchy

## Browser Compatibility

- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+
- Mobile Safari iOS 14+
- Chrome Android 90+
