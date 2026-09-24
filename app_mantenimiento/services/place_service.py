"""
Where a community is, and how sure we are about it.

Reads reference/community_places.json — tracked in git rather than living in
data/, because coordinates are not something the app produces. They are
maintained by us, reviewed in a diff, and a correction is an edit and a push.
The one failure this feature cannot have is a pin in the wrong state, and a
file whose every change shows up in a review is the cheapest guard against it.

Nothing here derives a position from a community's name. Fourteen of the
thirty-nine names carry no city, and nine of those name a development rather
than a town. Guessing would be right most of the time and confidently wrong
the rest — and nobody argues with a map.

A community with no entry is *missing*, not approximate. It does not get
drawn and it does get counted, so "we have not placed this one yet" stays
visible instead of turning into a pin somebody trusts.
"""

import json
import os
from typing import Dict, List, Optional

# Anything outside this box is not one of ours. The communities run from
# south Florida to Maryland and west to central Texas; a coordinate outside
# that is a typo — a swapped sign or a transposed digit — and a typo that
# lands a pin in the Atlantic is better caught here than seen on screen.
_LAT_RANGE = (24.0, 42.0)
_LNG_RANGE = (-100.0, -74.0)

_DEFAULT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'reference', 'community_places.json')


class PlaceService:
    """The map positions, loaded once and re-read when the file changes."""

    def __init__(self, path: str = None):
        self.path = path or _DEFAULT_PATH
        self._mtime = None
        self._places: Dict[str, Dict] = {}
        self._rejected: List[str] = []
        self._load()

    # ------------------------------------------------------------ loading

    def _load(self) -> None:
        try:
            mtime = os.path.getmtime(self.path)
        except OSError:
            self._places, self._rejected, self._mtime = {}, [], None
            return
        if mtime == self._mtime and self._places:
            return
        try:
            with open(self.path, encoding='utf-8') as f:
                raw = json.load(f)
        except (OSError, ValueError):
            # A broken reference file must not take the app down. The map
            # will report every community as unplaced, which is loud enough
            # to notice and harmless.
            self._places, self._rejected, self._mtime = {}, [], mtime
            return

        good, bad = {}, []
        for name, rec in (raw.get('places') or {}).items():
            if not isinstance(rec, dict):
                bad.append(name)
                continue
            lat, lng = rec.get('lat'), rec.get('lng')
            if not isinstance(lat, (int, float)) or not isinstance(lng, (int, float)):
                bad.append(name)
                continue
            if not (_LAT_RANGE[0] < lat < _LAT_RANGE[1]):
                bad.append(name)
                continue
            if not (_LNG_RANGE[0] < lng < _LNG_RANGE[1]):
                bad.append(name)
                continue
            good[name] = {
                'lat': float(lat), 'lng': float(lng),
                'city': (rec.get('city') or '').strip(),
                'state': (rec.get('state') or '').strip(),
                'verified': bool(rec.get('verified')),
                'note': (rec.get('note') or '').strip(),
            }
        self._places, self._rejected, self._mtime = good, sorted(bad), mtime

    # ------------------------------------------------------------ reading

    def get(self, community: str) -> Optional[Dict]:
        self._load()
        return self._places.get((community or '').strip())

    def placed(self, communities) -> List[Dict]:
        """Those of `communities` we can put on a map, with their position."""
        self._load()
        out = []
        for name in (communities or []):
            rec = self._places.get((name or '').strip())
            if rec:
                out.append(dict(rec, community=name))
        return out

    def unplaced(self, communities) -> List[str]:
        """Those we cannot. Counted and named rather than approximated."""
        self._load()
        return sorted(n for n in (communities or [])
                      if (n or '').strip() not in self._places)

    def unverified(self, communities=None) -> List[str]:
        """Positions no human has confirmed yet.

        Every entry starts out false. Until somebody who knows the community
        has looked at the pin, it is a proposal, and the map should not let
        that pass unmentioned.
        """
        self._load()
        names = communities if communities is not None else list(self._places)
        return sorted(n for n in names
                      if (n or '').strip() in self._places
                      and not self._places[(n or '').strip()]['verified'])

    def rejected(self) -> List[str]:
        """Entries thrown out for having an impossible position."""
        self._load()
        return list(self._rejected)
