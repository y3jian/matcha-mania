"""Pantry inventory, usage logging, and a photo log.

A pantry item is a physical tin you own — independent of what's currently being scraped
or tracked (you may own tins from stores that aren't tracked, or that have since sold
out). Usage logging records grams used per session against a pantry item; status
computation turns that into a consumption rate and a "days until empty" estimate. The
photo log is a chronological visual record per tin — color is a real quality signal for
matcha (vibrant green vs. dull/yellowish), so it's worth tracking alongside the numbers.
"""
import io
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

from PIL import Image, ImageOps

from data.pipelines.db import REPO_ROOT, connect

DB_PATH = REPO_ROOT / "db" / "matcha_mania.db"
PHOTOS_DIR = REPO_ROOT / "web" / "data" / "photos"

# Uploaded photos are downscaled to this on the long edge and re-saved as JPEG — keeps a
# gallery you're meant to scroll through from being weighed down by full phone-camera-sized
# originals, and normalizes format so every photo displays the same way.
MAX_PHOTO_DIMENSION = 1600
PHOTO_JPEG_QUALITY = 85

# Ceremonial matcha is generally recommended to be used within about 4-6 weeks of
# opening (flavor/color degrade after that even if stored well) — flagged as "stale"
# past this many days since opening.
STALE_AFTER_DAYS = 45

# "Needs reorder" if projected to run out this soon, or already down to this little.
REORDER_DAYS_THRESHOLD = 7
REORDER_GRAMS_THRESHOLD = 10

_PANTRY_UPDATABLE_COLUMNS = {
    "product_name", "store", "url", "size_grams", "grade", "cultivar", "region",
    "acquired_date", "opened_date", "finished_date", "notes",
}


class PantryError(Exception):
    """Raised for any user-facing pantry/usage failure (unknown item, bad input, etc.)."""


def add_pantry_item(
    product_name: str,
    size_grams: int,
    store: Optional[str] = None,
    url: Optional[str] = None,
    grade: Optional[str] = None,
    cultivar: Optional[str] = None,
    region: Optional[str] = None,
    acquired_date: Optional[str] = None,
    opened_date: Optional[str] = None,
    notes: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> int:
    """Add a tin to the pantry. Returns its new id. Raises PantryError on bad input."""
    if not product_name or not product_name.strip():
        raise PantryError("A product name is required.")
    if not isinstance(size_grams, int) or size_grams <= 0:
        raise PantryError("size_grams must be a positive whole number.")

    conn = connect(db_path or DB_PATH)
    try:
        cur = conn.execute(
            """
            INSERT INTO pantry_items
                (product_name, store, url, size_grams, grade, cultivar, region, acquired_date, opened_date, finished_date, notes)
            VALUES
                (:product_name, :store, :url, :size_grams, :grade, :cultivar, :region, :acquired_date, :opened_date, NULL, :notes)
            """,
            {
                "product_name": product_name.strip(),
                "store": store,
                "url": url,
                "size_grams": size_grams,
                "grade": grade,
                "cultivar": cultivar,
                "region": region,
                "acquired_date": acquired_date or date.today().isoformat(),
                "opened_date": opened_date,
                "notes": notes,
            },
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def edit_pantry_item(item_id: int, db_path: Optional[Path] = None, **fields) -> None:
    """Update one or more fields on a pantry item — e.g. opened_date, finished_date, notes."""
    unknown = set(fields) - _PANTRY_UPDATABLE_COLUMNS
    if unknown:
        raise PantryError(f"Not editable: {sorted(unknown)}")
    if not fields:
        return

    conn = connect(db_path or DB_PATH)
    try:
        existing = conn.execute("SELECT id FROM pantry_items WHERE id = ?", (item_id,)).fetchone()
        if not existing:
            raise PantryError(f"No pantry item with id {item_id}.")
        set_clause = ", ".join(f"{column} = :{column}" for column in fields)
        conn.execute(f"UPDATE pantry_items SET {set_clause} WHERE id = :id", {**fields, "id": item_id})
        conn.commit()
    finally:
        conn.close()


def remove_pantry_item(item_id: int, db_path: Optional[Path] = None) -> None:
    """Remove a pantry item and its usage history."""
    conn = connect(db_path or DB_PATH)
    try:
        existing = conn.execute("SELECT id FROM pantry_items WHERE id = ?", (item_id,)).fetchone()
        if not existing:
            raise PantryError(f"No pantry item with id {item_id}.")
        conn.execute("DELETE FROM usage_log WHERE pantry_item_id = ?", (item_id,))
        conn.execute("DELETE FROM pantry_items WHERE id = ?", (item_id,))
        conn.commit()
    finally:
        conn.close()


def log_usage(item_id: int, grams_used: float, logged_at: Optional[str] = None, db_path: Optional[Path] = None) -> int:
    """Record a usage session against a pantry item. Opens the tin automatically (sets
    opened_date to today) if it hadn't been marked opened yet — you can't use matcha
    from a tin you haven't opened, and it's easy to forget the separate step. Returns the
    new usage_log row's id."""
    if not isinstance(grams_used, (int, float)) or grams_used <= 0:
        raise PantryError("grams_used must be a positive number.")

    logged_at = logged_at or datetime.now(timezone.utc).isoformat()
    logged_date = datetime.fromisoformat(logged_at).date()  # the day the usage happened, not "today" — matters when backfilling a past session

    conn = connect(db_path or DB_PATH)
    try:
        item = conn.execute("SELECT id, opened_date FROM pantry_items WHERE id = ?", (item_id,)).fetchone()
        if not item:
            raise PantryError(f"No pantry item with id {item_id}.")
        if item[1] is None:
            conn.execute("UPDATE pantry_items SET opened_date = ? WHERE id = ?", (logged_date.isoformat(), item_id))

        cur = conn.execute(
            "INSERT INTO usage_log (pantry_item_id, grams_used, logged_at) VALUES (?, ?, ?)",
            (item_id, grams_used, logged_at),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def _status_for(item: dict, total_used: float, today: date) -> dict:
    size_grams = item["size_grams"]
    remaining_grams = max(size_grams - total_used, 0)
    is_finished = item["finished_date"] is not None or remaining_grams <= 0

    opened_date = date.fromisoformat(item["opened_date"]) if item["opened_date"] else None
    days_since_opened = (today - opened_date).days if opened_date else None

    daily_rate = None
    if opened_date and days_since_opened and days_since_opened > 0 and total_used > 0:
        daily_rate = total_used / days_since_opened

    days_until_empty = round(remaining_grams / daily_rate) if daily_rate else None

    is_stale = (
        not is_finished
        and days_since_opened is not None
        and days_since_opened > STALE_AFTER_DAYS
    )
    needs_reorder = not is_finished and opened_date is not None and (
        (days_until_empty is not None and days_until_empty <= REORDER_DAYS_THRESHOLD)
        or remaining_grams <= REORDER_GRAMS_THRESHOLD
    )

    return {
        **item,
        "total_used_grams": round(total_used, 1),
        "remaining_grams": round(remaining_grams, 1),
        "days_since_opened": days_since_opened,
        "daily_rate_grams": round(daily_rate, 2) if daily_rate else None,
        "days_until_empty": days_until_empty,
        "is_finished": is_finished,
        "is_stale": is_stale,
        "needs_reorder": needs_reorder,
    }


def list_pantry_status(db_path: Optional[Path] = None, today: Optional[date] = None) -> list:
    """Every pantry item plus computed status (remaining grams, consumption rate, days
    until empty, stale/reorder flags)."""
    today = today or date.today()

    conn = connect(db_path or DB_PATH)
    try:
        conn.row_factory = None
        columns = [
            "id", "product_name", "store", "url", "size_grams", "grade", "cultivar",
            "region", "acquired_date", "opened_date", "finished_date", "notes",
        ]
        items = [dict(zip(columns, row)) for row in conn.execute(f"SELECT {', '.join(columns)} FROM pantry_items")]
        usage_totals = dict(conn.execute("SELECT pantry_item_id, SUM(grams_used) FROM usage_log GROUP BY pantry_item_id"))
    finally:
        conn.close()

    return [_status_for(item, usage_totals.get(item["id"], 0.0), today) for item in items]


def add_photo(
    pantry_item_id: int,
    image_bytes: bytes,
    caption: Optional[str] = None,
    taken_at: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> dict:
    """Save a photo against a pantry item — downscaled and normalized to JPEG, written
    under web/data/photos/ where it's servable directly as a static file (no separate
    "fetch the blob" endpoint needed on the frontend, just an <img src>).

    Returns {"id", "filename", "url", "caption", "taken_at"}. Raises PantryError if the
    item doesn't exist or the bytes can't be read as an image.
    """
    conn = connect(db_path or DB_PATH)
    try:
        item = conn.execute("SELECT id FROM pantry_items WHERE id = ?", (pantry_item_id,)).fetchone()
        if not item:
            raise PantryError(f"No pantry item with id {pantry_item_id}.")

        try:
            image = Image.open(io.BytesIO(image_bytes))
            image = ImageOps.exif_transpose(image)  # phones store rotation as EXIF metadata, not rotated pixels
            image = image.convert("RGB")
        except Exception as exc:
            raise PantryError(f"Couldn't read that as an image ({exc}) — try a JPG or PNG.") from exc

        image.thumbnail((MAX_PHOTO_DIMENSION, MAX_PHOTO_DIMENSION))

        PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
        filename = f"{pantry_item_id}-{uuid.uuid4().hex[:12]}.jpg"
        image.save(PHOTOS_DIR / filename, "JPEG", quality=PHOTO_JPEG_QUALITY)

        taken_at = taken_at or datetime.now(timezone.utc).isoformat()
        cur = conn.execute(
            "INSERT INTO photo_log (pantry_item_id, filename, caption, taken_at) VALUES (?, ?, ?, ?)",
            (pantry_item_id, filename, caption, taken_at),
        )
        conn.commit()
        return {"id": cur.lastrowid, "filename": filename, "url": f"data/photos/{filename}", "caption": caption, "taken_at": taken_at}
    finally:
        conn.close()


def list_photos(pantry_item_id: Optional[int] = None, db_path: Optional[Path] = None) -> list:
    """Every photo, newest first — optionally filtered to one pantry item."""
    columns = ["id", "pantry_item_id", "filename", "caption", "taken_at", "product_name"]
    query = (
        "SELECT photo_log.id, photo_log.pantry_item_id, photo_log.filename, photo_log.caption, photo_log.taken_at, "
        "pantry_items.product_name "
        "FROM photo_log JOIN pantry_items ON pantry_items.id = photo_log.pantry_item_id"
    )
    params = ()
    if pantry_item_id is not None:
        query += " WHERE photo_log.pantry_item_id = ?"
        params = (pantry_item_id,)
    query += " ORDER BY photo_log.taken_at DESC"

    conn = connect(db_path or DB_PATH)
    try:
        rows = [dict(zip(columns, row)) for row in conn.execute(query, params)]
    finally:
        conn.close()

    for row in rows:
        row["url"] = f"data/photos/{row['filename']}"
    return rows


def remove_photo(photo_id: int, db_path: Optional[Path] = None) -> None:
    """Delete a photo's database row and its file on disk. Raises PantryError if unknown."""
    conn = connect(db_path or DB_PATH)
    try:
        row = conn.execute("SELECT filename FROM photo_log WHERE id = ?", (photo_id,)).fetchone()
        if not row:
            raise PantryError(f"No photo with id {photo_id}.")
        conn.execute("DELETE FROM photo_log WHERE id = ?", (photo_id,))
        conn.commit()
    finally:
        conn.close()

    (PHOTOS_DIR / row[0]).unlink(missing_ok=True)
