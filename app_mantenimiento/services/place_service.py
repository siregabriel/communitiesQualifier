"""
Where a community is, and how sure we are about it.

Lives in data/community_places.json, seeded from data/seeds/ like the regions
and the questions: the seed ships in git, the live copy is git-ignored, and a
deploy never overwrites it.

It started out as a file in the repository, on the argument that a pin in the
wrong state is the failure this cannot have and a diff is the cheapest guard.
That was an argument for review, and it cost more than it bought: placing a
new community meant a deploy, a rename left the position behind under the old
name, and `verified` could never become true because there was no act of
confirming. Somebody looking at the pin and agreeing with it is better review
than somebody reading two numbers in a diff.

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
from datetime import datetime
from typing import Dict, List, Optional

# Anything outside this box is not one of ours. The communities run from
# south Florida to Maryland and west to central Texas; a coordinate outside
# that is a typo — a swapped sign or a transposed digit — and a typo that
# lands a pin in the Atlantic is better caught here than seen on screen.
_LAT_RANGE = (24.0, 42.0)
_LNG_RANGE = (-100.0, -74.0)

_DEFAULT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'data', 'community_places.json')


def in_range(lat, lng) -> bool:
    """Whether a position could plausibly be one of ours.

    Checked on the way in as well as on the way out. A coordinate typed or
    pasted by hand is the likeliest place for a swapped sign or a transposed
    digit, and the reading check alone would catch it a day later, on screen,
    as a community that quietly stopped being on the map.
    """
    if not isinstance(lat, (int, float)) or isinstance(lat, bool):
        return False
    if not isinstance(lng, (int, float)) or isinstance(lng, bool):
        return False
    return (_LAT_RANGE[0] < lat < _LAT_RANGE[1]
            and _LNG_RANGE[0] < lng < _LNG_RANGE[1])


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
            if not isinstance(rec, dict) or not in_range(rec.get('lat'), rec.get('lng')):
                bad.append(name)
                continue
            lat, lng = float(rec['lat']), float(rec['lng'])
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

    # -------------------------------------------------------------- writing

    def _write(self) -> None:
        """Atomically replace the file with what is held now."""
        tmp = self.path + '.tmp'
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        payload = {'version': 1, 'places': {}}
        for name, rec in sorted(self._places.items()):
            out = {'lat': rec['lat'], 'lng': rec['lng'],
                   'city': rec['city'], 'state': rec['state'],
                   'verified': rec['verified']}
            for extra in ('note', 'verified_by', 'verified_at'):
                if rec.get(extra):
                    out[extra] = rec[extra]
            payload['places'][name] = out
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        os.replace(tmp, self.path)
        self._mtime = os.path.getmtime(self.path)

    def set(self, community, lat, lng, city='', state='', by='') -> Optional[Dict]:
        """Place a community, or move it. Returns the record, or None if the
        position is not plausible.

        Refusing rather than storing is the whole point: a swapped sign puts a
        Florida pin in China, and the alternative to refusing here is finding
        out on the map tomorrow.

        Saving marks it verified, because somebody did the confirming — that
        is the act the flag was always waiting for, and until this existed
        every position was a proposal with no way to stop being one.
        """
        community = (community or '').strip()
        if not community or not in_range(lat, lng):
            return None
        self._load()
        rec = dict(self._places.get(community) or {})
        rec.update({
            'lat': float(lat), 'lng': float(lng),
            'city': (city or rec.get('city') or '').strip(),
            'state': (state or rec.get('state') or '').strip(),
            'verified': True,
            'verified_by': (by or '').strip(),
            'verified_at': datetime.now().isoformat(),
        })
        # The note explained a guess. Once a person has placed the pin it is
        # no longer a guess, and leaving it would argue with the flag above.
        rec.pop('note', None)
        self._places[community] = rec
        self._write()
        return dict(rec, community=community)

    def rename(self, old_name: str, new_name: str) -> bool:
        """Carry a position across a rename.

        Everything else the rename touches keys on the community's name, and
        this is the one that used to be left behind — the map would report the
        community as unplaced and name the file it was still filed under. That
        note is still there for renames done before this was, and for anything
        else that goes missing.
        """
        old_name, new_name = (old_name or '').strip(), (new_name or '').strip()
        if not old_name or not new_name or old_name == new_name:
            return False
        self._load()
        rec = self._places.pop(old_name, None)
        if rec is None:
            return False
        self._places[new_name] = rec
        self._write()
        return True

    def rejected(self) -> List[str]:
        """Entries thrown out for having an impossible position."""
        self._load()
        return list(self._rejected)
