# Test Users - 38 Communities

## Admin User
- **Username**: `admin`
- **Password**: `admin123`
- **Community**: All (Admin access)

## Test Users by Community

### Georgia (8 users)
| Username | Password | Community |
|----------|----------|-----------|
| user1 | test123 | Kelley Place, Enterprise |
| user2 | test123 | Madison Heights Enterprise, Enterprise |
| user3 | test123 | Monark Grove Madison |
| user4 | test123 | Monark Grove Greystone |
| user5 | test123 | Legacy Ridge Trussville, Trussville |
| user6 | test123 | Madison at The Range, Madison |
| user7 | test123 | The Goldton at Athens |
| user8 | test123 | The Goldton at Jones Farm |

### Florida (8 users)
| Username | Password | Community |
|----------|----------|-----------|
| user9 | test123 | Madison at Clermont, Clermont |
| user10 | test123 | Madison at Ocoee, Ocoee |
| user11 | test123 | Madison at Oviedo, Oviedo |
| user12 | test123 | The Goldton at Venice, Venice |
| user13 | test123 | The Goldton at St. Petersburg, St. Petersburg |
| user14 | test123 | Lake Howard Heights, Winter Haven |
| user15 | test123 | The Canopy At Beacon Woods |
| user16 | test123 | The Goldton At Lake Nona |

### North Carolina (8 users)
| Username | Password | Community |
|----------|----------|-----------|
| user17 | test123 | Madison Heights Evans, Evans |
| user18 | test123 | Legacy at Savannah Quarters, Pooler |
| user19 | test123 | Legacy Reserve at Old Town, Columbus |
| user20 | test123 | Legacy Ridge at Alpharetta, Alpharetta |
| user21 | test123 | Legacy Ridge at Buckhead, Atlanta |
| user22 | test123 | Legacy Ridge at Marietta, Marietta |
| user23 | test123 | The Canopy at Westridge, McDonough |
| user24 | test123 | The Overlook at Suwanee, Suwanee |

### Ohio (1 user)
| Username | Password | Community |
|----------|----------|-----------|
| user25 | test123 | Legacy Reserve at Fritz Farm, Lexington |

### Mississippi (2 users)
| Username | Password | Community |
|----------|----------|-----------|
| user26 | test123 | The Goldton at Southaven, Southaven |
| user27 | test123 | The Goldton at Adelaide, Starkville |

### South Carolina (4 users)
| Username | Password | Community |
|----------|----------|-----------|
| user28 | test123 | Oakview Park, Greenville |
| user29 | test123 | Spring Park, Travelers Rest |
| user30 | test123 | Legacy Reserve Fairview Park, Simpsonville |
| user31 | test123 | Wildcat Senior Living, Summerville |

### Tennessee (1 user)
| Username | Password | Community |
|----------|----------|-----------|
| user32 | test123 | The Goldton at Spring Hill, Spring Hill |

### Texas (2 users)
| Username | Password | Community |
|----------|----------|-----------|
| user33 | test123 | The Oscar at Georgetown |
| user34 | test123 | The Oscar at Veramendi (June 2026) |

### Maryland (2 users)
| Username | Password | Community |
|----------|----------|-----------|
| user35 | test123 | Tribute at Black Hill |
| user36 | test123 | Tribute at Melford |

### Virginia (2 users)
| Username | Password | Community |
|----------|----------|-----------|
| user37 | test123 | Tribute at One Loudoun |
| user38 | test123 | Tribute at The Glen |

---

## Quick Reference

**Total Users**: 39 (1 admin + 38 community users)

**Login Format**:
- Username: `user1` through `user38` (or `admin`)
- Password: `test123` (or `admin123` for admin)

## Testing Workflow

1. **Login** with any user (e.g., `user1` / `test123`)
2. **View Questions** - User will see only questions for their assigned community
3. **Complete Inspection** - Fill out questionnaire for their community
4. **View Results** - Check "My Visits" to see their submissions
5. **Admin View** - Login as `admin` to see all communities in dashboard

## Future Expansion

The system supports multiple users per community. To add more users:
1. Add new entry to `USERS_DB` in `app.py`
2. Assign same community name
3. Multiple users can work on the same community independently

## Notes

- All test users have the same password (`test123`) for easy testing
- Each user sees only their assigned community's questions
- Admin user (`admin` / `admin123`) can see all 38 communities
- System supports 2-3 users per community (can be expanded)

---

**Created**: May 18, 2026
**Purpose**: Testing questionnaires across all 38 communities
