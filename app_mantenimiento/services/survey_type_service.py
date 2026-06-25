"""
Survey Type Service
Manages survey type data and operations
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Optional


class SurveyTypeService:
    """
    Service for managing survey types
    
    Handles loading, validation, and retrieval of survey type data
    from the survey_types.json file.
    """
    
    def __init__(self, survey_types_file: str):
        """
        Initialize the SurveyTypeService
        
        Args:
            survey_types_file: Path to the survey_types.json file
        """
        self.survey_types_file = survey_types_file
        self._ensure_file_exists()
    
    def _ensure_file_exists(self) -> None:
        """
        Create survey_types.json if it doesn't exist
        
        Creates the file with default survey type definitions
        if the file is not found.
        """
        if not os.path.exists(self.survey_types_file):
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(self.survey_types_file), exist_ok=True)
            
            # Default survey types
            default_data = {
                "version": "1.0",
                "last_modified": datetime.utcnow().isoformat() + "Z",
                "survey_types": [
                    {
                        "id": "full-regional",
                        "name": "Full Regional Review",
                        "icon": "fa-sitemap",
                        "color": "#3b82f6",
                        "description": "Comprehensive review covering all aspects",
                        "is_active": True,
                        "created_at": datetime.utcnow().isoformat() + "Z"
                    },
                    {
                        "id": "operational",
                        "name": "Operational Review",
                        "icon": "fa-search-plus",
                        "color": "#10b981",
                        "description": "Focus on operational procedures and efficiency",
                        "is_active": True,
                        "created_at": datetime.utcnow().isoformat() + "Z"
                    },
                    {
                        "id": "sales-marketing",
                        "name": "Sales & Marketing",
                        "icon": "fa-chart-line",
                        "color": "#8b5cf6",
                        "description": "Review of sales processes and marketing materials",
                        "is_active": True,
                        "created_at": datetime.utcnow().isoformat() + "Z"
                    },
                    {
                        "id": "clinical",
                        "name": "Clinical Review",
                        "icon": "fa-user-md",
                        "color": "#ef4444",
                        "description": "Medical and clinical standards review",
                        "is_active": True,
                        "created_at": datetime.utcnow().isoformat() + "Z"
                    },
                    {
                        "id": "dining",
                        "name": "Dining Review",
                        "icon": "fa-utensils",
                        "color": "#f59e0b",
                        "description": "Food service and dining area inspection",
                        "is_active": True,
                        "created_at": datetime.utcnow().isoformat() + "Z"
                    },
                    {
                        "id": "life-safety",
                        "name": "Life Safety Review",
                        "icon": "fa-exclamation-triangle",
                        "color": "#eab308",
                        "description": "Safety equipment and emergency procedures",
                        "is_active": True,
                        "created_at": datetime.utcnow().isoformat() + "Z"
                    }
                ]
            }
            
            with open(self.survey_types_file, 'w') as f:
                json.dump(default_data, f, indent=2)
    
    def _load_data(self) -> Dict:
        """
        Load survey types data from file
        
        Returns:
            Dictionary containing survey types data
            
        Raises:
            IOError: If file cannot be read
            json.JSONDecodeError: If file contains invalid JSON
        """
        try:
            with open(self.survey_types_file, 'r') as f:
                return json.load(f)
        except IOError as e:
            raise IOError(f"Failed to read survey types file: {str(e)}")
        except json.JSONDecodeError as e:
            raise json.JSONDecodeError(f"Invalid JSON in survey types file: {str(e)}", e.doc, e.pos)
    
    def _save(self, data: Dict) -> None:
        data['last_modified'] = datetime.utcnow().isoformat() + 'Z'
        tmp = self.survey_types_file + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, self.survey_types_file)

    @staticmethod
    def _slug(name: str) -> str:
        import re
        s = re.sub(r'[^a-z0-9]+', '-', (name or '').strip().lower()).strip('-')
        return s or 'type'

    def create_survey_type(self, name, description='', icon='fa-clipboard-list', color='#1f6fe5') -> Dict:
        name = (name or '').strip()
        if not name:
            raise ValueError('Name is required')
        data = self._load_data()
        types = data.setdefault('survey_types', [])
        existing = {t['id'] for t in types}
        base = self._slug(name)
        sid, n = base, 2
        while sid in existing:
            sid = f'{base}-{n}'
            n += 1
        rec = {
            'id': sid, 'name': name,
            'icon': (icon or 'fa-clipboard-list').strip(),
            'color': (color or '#1f6fe5').strip(),
            'description': (description or '').strip(),
            'is_active': True,
            'created_at': datetime.utcnow().isoformat() + 'Z',
        }
        types.append(rec)
        self._save(data)
        return rec

    def update_survey_type(self, sid, name=None, description=None, icon=None, color=None) -> Optional[Dict]:
        data = self._load_data()
        t = next((x for x in data.get('survey_types', []) if x['id'] == sid), None)
        if not t:
            return None
        if name is not None and name.strip():
            t['name'] = name.strip()
        if description is not None:
            t['description'] = description.strip()
        if icon is not None and icon.strip():
            t['icon'] = icon.strip()
        if color is not None and color.strip():
            t['color'] = color.strip()
        self._save(data)
        return t

    def delete_survey_type(self, sid) -> bool:
        data = self._load_data()
        types = data.get('survey_types', [])
        kept = [x for x in types if x['id'] != sid]
        if len(kept) == len(types):
            return False
        data['survey_types'] = kept
        self._save(data)
        return True

    def get_all_survey_types(self) -> List[Dict]:
        """
        Get all active survey types
        
        Returns:
            List of survey type dictionaries (only active types)
            
        Example:
            [
                {
                    "id": "full-regional",
                    "name": "Full Regional Review",
                    "icon": "fa-sitemap",
                    "color": "#3b82f6",
                    "description": "Comprehensive review...",
                    "is_active": True
                },
                ...
            ]
        """
        data = self._load_data()
        survey_types = data.get('survey_types', [])
        
        # Filter only active survey types
        return [st for st in survey_types if st.get('is_active', True)]
    
    def get_survey_type_by_id(self, survey_type_id: str) -> Optional[Dict]:
        """
        Get specific survey type by ID
        
        Args:
            survey_type_id: The ID of the survey type to retrieve
            
        Returns:
            Survey type dictionary if found, None otherwise
            
        Example:
            {
                "id": "full-regional",
                "name": "Full Regional Review",
                ...
            }
        """
        survey_types = self.get_all_survey_types()
        return next((st for st in survey_types if st['id'] == survey_type_id), None)
    
    def validate_survey_type(self, survey_type_id: str) -> bool:
        """
        Check if survey type ID is valid
        
        Args:
            survey_type_id: The ID to validate
            
        Returns:
            True if survey type exists and is active, False otherwise
            
        Example:
            >>> service.validate_survey_type("full-regional")
            True
            >>> service.validate_survey_type("invalid-type")
            False
        """
        if not survey_type_id:
            return False
        
        return self.get_survey_type_by_id(survey_type_id) is not None
    
    def get_survey_type_ids(self) -> List[str]:
        """
        Get list of all active survey type IDs
        
        Returns:
            List of survey type ID strings
            
        Example:
            ["full-regional", "operational", "sales-marketing", ...]
        """
        survey_types = self.get_all_survey_types()
        return [st['id'] for st in survey_types]
    
    def get_survey_type_name(self, survey_type_id: str) -> Optional[str]:
        """
        Get the display name for a survey type
        
        Args:
            survey_type_id: The ID of the survey type
            
        Returns:
            Survey type name if found, None otherwise
            
        Example:
            >>> service.get_survey_type_name("full-regional")
            "Full Regional Review"
        """
        survey_type = self.get_survey_type_by_id(survey_type_id)
        return survey_type['name'] if survey_type else None
