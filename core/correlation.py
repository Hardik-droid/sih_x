"""Multi-representation and secondary-stream correlation engine.

Searches evidence records for surviving primary (main) and secondary (substream)
representations, aligns them temporally and spatially by camera channel, and
maps surviving secondary coverage across primary gaps without synthesizing pixels.
"""
import math


def correlate_representations(fragments):
    """Correlates primary and secondary stream fragments across channels.

    Args:
        fragments: list of dicts, each with keys like:
                   channel, representation ('main' or 'substream'),
                   timestamp_start, timestamp_end, id (or offset_start/end).

    Returns:
        dict with channels, total_gaps, covered_gaps, and forensic rationale.
    """
    by_channel = {}
    for frag in fragments:
        channel = frag.get("channel")
        if not channel:
            continue
        by_channel.setdefault(channel, []).append(frag)

    channel_reports = {}
    total_gaps = 0
    covered_gaps = 0

    for channel, items in by_channel.items():
        main_frags = [f for f in items if f.get("representation") in ("main", None) and f.get("timestamp_start") is not None]
        sub_frags = [f for f in items if f.get("representation") == "substream" and f.get("timestamp_start") is not None]

        # Sort by timestamps
        main_frags.sort(key=lambda f: f["timestamp_start"])
        sub_frags.sort(key=lambda f: f["timestamp_start"])

        # Detect gaps between adjacent main fragments
        gaps = []
        for left, right in zip(main_frags, main_frags[1:]):
            l_end = left.get("timestamp_end")
            r_start = right.get("timestamp_start")
            if l_end is not None and r_start is not None and (r_start - l_end) > 0.08:
                gap_start = round(l_end, 3)
                gap_end = round(r_start, 3)
                gap_duration = round(gap_end - gap_start, 3)

                # Check if any substream covers this gap
                covering = []
                for sub in sub_frags:
                    s_start = sub["timestamp_start"]
                    s_end = sub.get("timestamp_end", s_start)
                    # Check overlap: sub spans partially or fully over [gap_start, gap_end]
                    overlap_start = max(gap_start, s_start)
                    overlap_end = min(gap_end, s_end)
                    if overlap_end > overlap_start:
                        coverage_pct = round(min(1.0, (overlap_end - overlap_start) / max(gap_duration, 0.001)) * 100, 1)
                        covering.append({
                            "substream_id": sub.get("id") or f"offset_{sub.get('offset_start')}",
                            "substream_range": [s_start, s_end],
                            "overlap_range": [overlap_start, overlap_end],
                            "coverage_percent": coverage_pct
                        })

                is_covered = len(covering) > 0
                if is_covered:
                    covered_gaps += 1
                total_gaps += 1

                gaps.append({
                    "gap_start": gap_start,
                    "gap_end": gap_end,
                    "duration_seconds": gap_duration,
                    "covered_by_substream": is_covered,
                    "covering_substreams": covering
                })

        # Overall alignment status for channel
        if not sub_frags:
            status = "PRIMARY_ONLY"
        elif gaps and any(g["covered_by_substream"] for g in gaps):
            status = "CORRELATED_WITH_GAPS_COVERED"
        elif gaps:
            status = "CORRELATED_UNCOVERED_GAPS"
        else:
            status = "CORRELATED_CONCURRENT"

        channel_reports[channel] = {
            "channel": channel,
            "main_fragment_count": len(main_frags),
            "substream_fragment_count": len(sub_frags),
            "status": status,
            "gaps_in_primary": gaps,
            "main_intervals": [
                {"start": f["timestamp_start"], "end": f.get("timestamp_end"), "id": f.get("id") or f.get("offset_start")}
                for f in main_frags
            ],
            "substream_intervals": [
                {"start": f["timestamp_start"], "end": f.get("timestamp_end"), "id": f.get("id") or f.get("offset_start")}
                for f in sub_frags
            ]
        }

    return {
        "status": "MULTI_REPRESENTATION_CORRELATED" if any(r["substream_fragment_count"] > 0 for r in channel_reports.values()) else "PRIMARY_ONLY",
        "channels": channel_reports,
        "total_primary_gaps": total_gaps,
        "gaps_covered_by_substreams": covered_gaps,
        "forensic_policy": {
            "pixel_synthesis": "REFUSED",
            "rationale": "Surviving substreams provide investigative timeline and visual context across primary stream gaps; original high-resolution pixels are not synthesized or hallucinated."
        }
    }
