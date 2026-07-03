"""Rule-based "best time to buy" windows, derived from the sourced harvest calendar.

This is deliberately NOT a fitted/statistical model. No public source has a month-level
retail matcha price time series (checked: Japan's official retail price survey tracks
generic "green tea," not matcha powder; industry bodies publish annual wholesale
auction figures at best), and our own scrape history is nowhere near long enough to
fit anything on yet. Until one of those changes, "best time to buy" is expressed as
two sourced, explainable windows rather than a number with false precision:

  1. Fresh harvest window: the flush's own harvest months, plus a short grace period
     for freshly milled matcha to reach shelves.
  2. Kuradashi window: for regions whose notes describe an autumn "kuradashi" release
     of summer-aged premium lots (a real, sourced practice, not a guess).
"""

FRESHNESS_GRACE_MONTHS = 2
KURADASHI_MONTHS = (9, 11)


def best_buy_windows(row: dict) -> list:
    if not row.get("used_for_matcha"):
        return []

    windows = [{
        "start_month": row["start_month"],
        "end_month": min(row["end_month"] + FRESHNESS_GRACE_MONTHS, 12),
        "reason": "Freshly harvested and milled — newest stock of the year.",
    }]

    if "kuradashi" in (row.get("notes") or "").lower():
        windows.append({
            "start_month": KURADASHI_MONTHS[0],
            "end_month": KURADASHI_MONTHS[1],
            "reason": "Kuradashi: premium lots aged over summer are released, often prized as peak flavor.",
        })

    return windows
