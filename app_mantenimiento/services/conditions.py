"""
What a standard can be marked on a visit.

Pass and Fail are the score. "Not checked" was added in Nov 2026 at Greg
Crutcher's request: a walk where the kitchen was closed or a room was locked
used to leave two bad choices, a Pass nobody verified or a Fail nobody found.
Leaving it blank worked, but read as "forgot" and marked the visit partial.

A Not checked:
  * needs a reason, kept in the response's description — without one it is
    an easy way to turn a Fail into a higher score;
  * is left out of the score, exactly as an unanswered standard always was;
  * counts as answered, so it does not make the visit partial;
  * is shown everywhere the visit is (panel, history, emails, exports), so
    the regional can see what still needs a look.
"""

PASS = 'Pass'
FAIL = 'Fail'
NOT_CHECKED = 'Not checked'

SCORED = (PASS, FAIL)
ANSWERS = (PASS, FAIL, NOT_CHECKED)
