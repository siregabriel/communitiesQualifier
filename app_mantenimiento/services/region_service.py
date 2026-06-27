"""
Region Service
Loads the regional structure (leadership rosters + community assignments)
from data/regions.json and provides lookups. This underpins the dashboard
Regions view and, later, post-visit report email routing.
"""

import json
import os
from datetime import datetime

from services.json_store import JsonFileBacked


class RegionService(JsonFileBacked):
    def __init__(self, storage_path: str):
        self.storage_path = storage_path
        self.regions = []
        self.notes = ""
        self._init_store()
        self.load_from_file()
        self._mark_loaded()

    def load_from_file(self) -> None:
        """Load regions from JSON; initialize empty on any error."""
        try:
            if os.path.exists(self.storage_path):
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if isinstance(data, dict) and isinstance(data.get('regions'), list):
                    self.regions = data['regions']
                    self.notes = data.get('notes', "")
                else:
                    self.regions = []
            else:
                self.regions = []
        except (json.JSONDecodeError, OSError):
            self.regions = []

    def save_to_file(self) -> None:
        """Persist regions to JSON (atomic write)."""
        data = {
            'version': '1.0',
            'last_modified': datetime.now().isoformat(),
            'notes': self.notes,
            'regions': self.regions
        }
        self._atomic_write(data, indent=2)

    def get_all_regions(self) -> list:
        """Return all regions (leadership + community lists)."""
        self._ensure_fresh()
        return self.regions

    def get_region_for_community(self, community: str):
        """Return the region dict that contains the given community, or None."""
        if not community:
            return None
        self._ensure_fresh()
        for region in self.regions:
            if community in region.get('communities', []):
                return region
        return None

    def _detach(self, community: str) -> None:
        """Remove a community from every region's list."""
        for region in self.regions:
            region['communities'] = [c for c in region.get('communities', []) if c != community]

    def assign_community(self, community: str, region_id: str) -> bool:
        """
        Ensure `community` belongs only to the region with `region_id`.
        Works for moving an existing community, adding a brand-new one, or
        restoring from Unassigned. Returns False if the target region is unknown.
        """
        self._ensure_fresh()
        community = (community or '').strip()
        if not community:
            return False
        target = next((r for r in self.regions if r.get('id') == region_id), None)
        if target is None:
            return False
        self._detach(community)
        target.setdefault('communities', []).append(community)
        self.save_to_file()
        return True

    def remove_community(self, community: str) -> bool:
        """Remove a community from the regional structure entirely.
        Returns True if it was present in any region."""
        self._ensure_fresh()
        community = (community or '').strip()
        if not community:
            return False
        present = any(community in r.get('communities', []) for r in self.regions)
        self._detach(community)
        if present:
            self.save_to_file()
        return present

    def rename_community(self, old_name: str, new_name: str) -> bool:
        """Rename a community everywhere it appears in the regional structure."""
        old_name = (old_name or '').strip()
        new_name = (new_name or '').strip()
        if not old_name or not new_name or old_name == new_name:
            return False
        with self._lock:
            self._ensure_fresh()
            changed = False
            for region in self.regions:
                comms = region.get('communities', [])
                new_list = []
                for c in comms:
                    val = new_name if c == old_name else c
                    if val == old_name:
                        changed = True
                    if val not in new_list:  # avoid duplicates
                        new_list.append(val)
                    if c == old_name:
                        changed = True
                region['communities'] = new_list
            if changed:
                self.save_to_file()
            return changed

    def rename_region(self, region_id: str, new_name: str) -> bool:
        """Change a region's display name. The region id (used for user scoping)
        is unchanged, so this is purely cosmetic and safe."""
        new_name = (new_name or '').strip()
        if not region_id or not new_name or region_id == 'unassigned':
            return False
        with self._lock:
            self._ensure_fresh()
            region = next((r for r in self.regions if r.get('id') == region_id), None)
            if region is None or region.get('name') == new_name:
                return False
            region['name'] = new_name
            self.save_to_file()
            return True

    # --- Leadership CRUD ---
    def _get_region(self, region_id: str):
        self._ensure_fresh()
        return next((r for r in self.regions if r.get('id') == region_id), None)

    def add_leader(self, region_id: str, name: str, role: str, email: str = "") -> bool:
        region = self._get_region(region_id)
        if region is None:
            return False
        region.setdefault('leadership', []).append({
            'name': (name or '').strip(),
            'role': (role or '').strip(),
            'email': (email or '').strip()
        })
        self.save_to_file()
        return True

    def update_leader(self, region_id: str, index: int, name: str, role: str, email: str = "") -> bool:
        region = self._get_region(region_id)
        if region is None:
            return False
        leaders = region.get('leadership', [])
        if not isinstance(index, int) or index < 0 or index >= len(leaders):
            return False
        leaders[index] = {
            'name': (name or '').strip(),
            'role': (role or '').strip(),
            'email': (email or '').strip()
        }
        self.save_to_file()
        return True

    def remove_leader(self, region_id: str, index: int) -> bool:
        region = self._get_region(region_id)
        if region is None:
            return False
        leaders = region.get('leadership', [])
        if not isinstance(index, int) or index < 0 or index >= len(leaders):
            return False
        leaders.pop(index)
        self.save_to_file()
        return True

    def move_leader(self, from_region_id: str, from_index: int,
                    to_region_id: str, to_index=None):
        """
        Move a leader from one region to another, or reorder within a region.
        Returns the moved leader dict on success, or None on failure.
        """
        with self._lock:
            self._ensure_fresh()
            src = next((r for r in self.regions if r.get('id') == from_region_id), None)
            dst = next((r for r in self.regions if r.get('id') == to_region_id), None)
            if src is None or dst is None:
                return None
            s_leaders = src.get('leadership', [])
            if not isinstance(from_index, int) or from_index < 0 or from_index >= len(s_leaders):
                return None

            leader = s_leaders.pop(from_index)
            d_leaders = dst.setdefault('leadership', [])

            # If reordering within the same region and inserting after the old
            # spot, account for the index shift caused by the pop above.
            if src is dst and isinstance(to_index, int) and to_index > from_index:
                to_index -= 1

            if isinstance(to_index, int) and 0 <= to_index <= len(d_leaders):
                d_leaders.insert(to_index, leader)
            else:
                d_leaders.append(leader)

            self.save_to_file()
            return leader
