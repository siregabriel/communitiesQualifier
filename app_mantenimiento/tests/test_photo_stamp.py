"""
The caption strip added to a photo on its way out of Atlas Excellence.

Two things these tests exist to hold down:

  * the stored original is never rewritten — after the collision that lost
    three of Marissa's photos for good, with bucket versioning still off, an
    irreversible transform near the upload path is the thing to guard against;

  * the path arrives from the browser, so the route must refuse a community the
    signed-in person is not allowed to see, rather than trusting what it is
    handed.

Run locally, never on the server.
"""

import io
import os
import sys

import pytest

_APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

from PIL import Image  # noqa: E402
from werkzeug.utils import secure_filename  # noqa: E402

import app as A  # noqa: E402
from services.photo_stamp import stamp  # noqa: E402

_FAKE_USERS = ("smoke.photo",)


def teardown_module(module):
    for u in _FAKE_USERS:
        try:
            A.presence_service.forget(u)
        except Exception:
            pass


def _photo(w=900, h=600, colour=(200, 40, 40)):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), colour).save(buf, "JPEG")
    return buf.getvalue()


# --------------------------------------------------------------- the strip

def test_strip_is_added_below_not_over_the_photo():
    """These are photos of defects — an overlay would sit on the evidence."""
    original = _photo()
    out, _ = stamp(original, "The Oscar at Georgetown", "Jun 03, 2026 · Marissa Scott")
    res = Image.open(io.BytesIO(out))

    assert res.width == 900, "the photo is not resized"
    assert res.height > 600, "the strip is added underneath"
    assert 60 < res.height - 600 < 220, "and stays proportionate to the photo"

    top_left = res.crop((0, 0, 900, 600)).convert("RGB").getpixel((450, 300))
    assert top_left[0] > 150, "the photo itself is untouched"


def test_strip_carries_readable_text():
    out, _ = stamp(_photo(), "Fairview", "Jun 03, 2026 · Marissa Scott")
    res = Image.open(io.BytesIO(out))
    band = list(res.crop((0, 600, res.width, res.height)).convert("L").getdata())
    assert min(band) < 60, "the strip is dark"
    assert max(band) > 180, "with light text on it"


def test_the_stored_bytes_are_never_the_ones_that_change():
    original = _photo()
    out, _ = stamp(original, "Fairview", "Jun 03, 2026")
    assert out != original
    assert Image.open(io.BytesIO(original)).size == (900, 600), \
        "the original is still exactly what it was"


def test_a_portrait_phone_photo_is_stamped_too():
    out, _ = stamp(_photo(600, 900, (30, 120, 200)), "Fairview", "Jun 03, 2026")
    res = Image.open(io.BytesIO(out))
    assert res.width == 600 and res.height > 900


def test_a_long_community_name_does_not_overflow():
    out, _ = stamp(_photo(), "The Enclave at Round Rock Senior Living, Round Rock, TX",
                   "Jun 03, 2026 · Marissa Scott")
    assert Image.open(io.BytesIO(out)).width == 900


def test_an_unreadable_file_comes_back_whole_instead_of_erroring():
    """A photo without its caption beats a download that 500s."""
    junk = b"this is not an image"
    out, _ = stamp(junk, "Fairview", "Jun 03, 2026")
    assert out == junk


# ------------------------------------------------------- reading the path

def _first_communities(n=2):
    comms = A.all_communities()
    if len(comms) < n:
        pytest.skip("needs at least %d communities in the roster" % n)
    return comms[:n]


def test_community_date_and_author_come_out_of_the_stored_path():
    (community,) = _first_communities(1)[:1]
    path = f"{secure_filename(community)}/marissa.scott_20260603-193000_ab12cd34.jpg"
    comm, taken, user = A._photo_context(path)
    assert comm == community
    assert user == "marissa.scott"
    assert taken is not None and taken.strftime("%Y-%m-%d") == "2026-06-03"


def test_the_older_filenames_still_read():
    """Names written before the collision fix were "<user>_<unix seconds>"."""
    (community,) = _first_communities(1)[:1]
    comm, taken, user = A._photo_context(
        f"{secure_filename(community)}/marissa.scott_1717441800.jpg")
    assert comm == community and user == "marissa.scott" and taken is not None


def test_an_unknown_folder_resolves_to_no_community():
    assert A._photo_context("Invented_Place/x_20260603-193000_aa.jpg")[0] is None


def test_a_signed_s3_link_is_understood_as_well_as_a_path():
    """What the page hands over is often photo_url, not the stored path.

    Several views keep the signed link in the same field the <img> reads, so
    the download button sent a whole https://... and every download 404'd.
    """
    (community,) = _first_communities(1)[:1]
    folder = secure_filename(community)
    name = "marissa.scott_20260603-193000_ab12cd34.jpg"
    signed = (f"https://atlas-standards-uploads.s3.us-east-2.amazonaws.com/"
              f"uploads/{folder}/{name}"
              "?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Signature=deadbeef")
    comm, taken, user = A._photo_context(signed)
    assert comm == community
    assert user == "marissa.scott"
    assert taken is not None


@pytest.mark.parametrize("shape", [
    "{folder}/{name}",
    "uploads/{folder}/{name}",
    "/static/uploads/{folder}/{name}",
    "https://bucket.s3.us-east-2.amazonaws.com/uploads/{folder}/{name}?X-Amz-Signature=x",
    "https://s3.us-east-2.amazonaws.com/bucket/uploads/{folder}/{name}",
])
def test_every_shape_the_page_can_hand_over_resolves(shape):
    (community,) = _first_communities(1)[:1]
    path = shape.format(folder=secure_filename(community),
                        name="marissa.scott_20260603-193000_ab12cd34.jpg")
    assert A._photo_context(path)[0] == community


def test_a_url_encoded_folder_still_resolves():
    """Community names carry spaces and commas, so the link arrives escaped."""
    (community,) = _first_communities(1)[:1]
    from urllib.parse import quote
    folder = quote(secure_filename(community))
    path = f"https://b.s3.amazonaws.com/uploads/{folder}/x_20260603-193000_aa.jpg"
    assert A._photo_context(path)[0] == community


def test_the_host_in_a_link_is_ignored_not_fetched():
    """Only the key is taken from a link; bytes always come from our bucket."""
    (community,) = _first_communities(1)[:1]
    folder = secure_filename(community)
    hostile = f"https://evil.example.com/uploads/{folder}/x_20260603-193000_aa.jpg"
    assert A._normalize_photo_path(hostile) == f"{folder}/x_20260603-193000_aa.jpg"


# ------------------------------------------------------------ who may read

def _as_ed(client, community):
    with client.session_transaction() as s:
        s.update(user="smoke.photo", role="staff", community=community,
                 display_name="smoke.photo", region_id=None)


def test_an_ed_cannot_download_another_communitys_photo():
    mine, theirs = _first_communities(2)
    c = A.app.test_client()
    _as_ed(c, mine)
    r = c.get("/api/photo/download?path="
              f"{secure_filename(theirs)}/x_20260603-193000_aa.jpg")
    assert r.status_code == 403


def test_an_invented_path_is_refused():
    (mine,) = _first_communities(1)[:1]
    c = A.app.test_client()
    _as_ed(c, mine)
    assert c.get("/api/photo/download?path=Nowhere/x_20260603-193000_aa.jpg"
                 ).status_code == 404


def test_the_path_cannot_climb_out_of_the_uploads_folder():
    (mine,) = _first_communities(1)[:1]
    c = A.app.test_client()
    _as_ed(c, mine)
    assert c.get("/api/photo/download?path=../../etc/passwd").status_code in (400, 403, 404)


def test_signed_out_gets_nothing():
    r = A.app.test_client().get("/api/photo/download?path=x/y.jpg")
    assert r.status_code in (302, 401, 403)


# ------------------------------------------------------- the whole journey

def test_a_real_download_comes_back_as_a_stamped_image():
    """End to end through the route, because the pieces passing alone is what
    let the first version ship broken."""
    if A.file_upload_handler.use_s3:
        pytest.skip("this one writes a file; S3 mode is exercised in production")

    (community,) = _first_communities(1)[:1]
    folder = os.path.join(_APP_DIR, "static", "uploads", secure_filename(community))
    os.makedirs(folder, exist_ok=True)
    name = "smoke.photo_20260603-193000_ab12cd34.jpg"
    full = os.path.join(folder, name)
    with open(full, "wb") as fh:
        fh.write(_photo())

    try:
        c = A.app.test_client()
        with c.session_transaction() as s:
            s.update(user="smoke.photo", role="admin", community=None,
                     display_name="smoke.photo", region_id=None)
        r = c.get("/api/photo/download?path="
                  f"{secure_filename(community)}/{name}")
        assert r.status_code == 200, r.data[:200]
        assert r.mimetype.startswith("image/"), "an image, never a JSON error"

        got = Image.open(io.BytesIO(r.data))
        assert got.width == 900 and got.height > 600, "it came back stamped"
        assert "attachment" in r.headers.get("Content-Disposition", "")

        # And the file on disk is byte-for-byte what it was.
        with open(full, "rb") as fh:
            assert fh.read() == _photo(), "the stored photo was not rewritten"
    finally:
        try:
            os.remove(full)
        except OSError:
            pass
