#!/usr/bin/env python3
"""
Google Ads Change History Impact Dashboard Generator
────────────────────────────────────────────────────
Usage:
  python generate_dashboard.py <metrics.csv> <changes.csv> [output.html]

If no arguments are provided, the script auto-discovers CSVs in the
current working directory by matching filename patterns.

Metrics CSV expected columns (Google Ads → Reports → Campaigns export):
  Day, Campaign type, Campaign subtype, Campaign, Cost, Conv. value,
  Conversions, ROAS, Conv. rate

Change History CSV expected columns (Google Ads → Tools → Change History):
  Date & time, Account, User, Campaign, Ad group, Changes
"""

import pandas as pd
import json
import os
import sys
import re
import glob

# ─── Paths (fully generic — no hardcoded paths) ────────────────────────────────
def auto_find(patterns):
    for p in patterns:
        m = glob.glob(p)
        if m:
            return m[0]
    return None

if len(sys.argv) >= 3:
    METRICS_PATH = sys.argv[1]
    CHANGES_PATH = sys.argv[2]
    OUTPUT_PATH  = sys.argv[3] if len(sys.argv) > 3 else "change_impact_dashboard.html"
else:
    METRICS_PATH = auto_find([
        "*[Mm]etric*.csv", "*[Pp]erformance*.csv",
        "*[Cc]ampaign*[Pp]erf*.csv", "*google*ads*.csv",
    ])
    CHANGES_PATH = auto_find([
        "*[Cc]hange*[Hh]istory*.csv", "*[Cc]hange*[Rr]eport*.csv",
        "*[Cc]hange*.csv",
    ])
    OUTPUT_PATH = "change_impact_dashboard.html"
    if not METRICS_PATH or not CHANGES_PATH:
        print("Usage: python generate_dashboard.py <metrics.csv> <changes.csv> [output.html]")
        print()
        print("Or place CSVs in the current directory with recognisable names:")
        print("  Metrics  → file containing 'metric', 'performance', or 'campaign'")
        print("  Changes  → file containing 'change history' or 'change report'")
        sys.exit(1)
    print(f"Auto-discovered:\n  Metrics : {METRICS_PATH}\n  Changes : {CHANGES_PATH}")

# ─── 1. Load & aggregate metrics ──────────────────────────────────────────────
print("Loading metrics CSV…")

# Detect how many header rows to skip (Google Ads exports have 2 title rows)
def detect_skip(path, header_keywords):
    """Read raw lines and find first row whose first cell matches known column names."""
    with open(path, 'r', encoding='utf-8-sig', errors='replace') as f:
        for i, line in enumerate(f):
            if i >= 6:
                break
            first = line.split(',')[0].strip().strip('"').lower()
            if first in header_keywords:
                return i
    return 2  # Google Ads default

skip = detect_skip(METRICS_PATH, {"day", "date", "campaign", "campaign type"})
df_m = pd.read_csv(METRICS_PATH, skiprows=skip, encoding="utf-8-sig")

# Normalise column names (strip spaces, handle case variations)
df_m.columns = df_m.columns.str.strip()

df_m["cost"]          = pd.to_numeric(df_m["Cost"].astype(str).str.replace(",",""), errors="coerce").fillna(0)
df_m["conv_value"]    = pd.to_numeric(df_m["Conv. value"].astype(str).str.replace(",",""), errors="coerce").fillna(0)
df_m["conversions"]   = pd.to_numeric(df_m["Conversions"].astype(str).str.replace(",",""), errors="coerce").fillna(0)
df_m["day"]           = pd.to_datetime(df_m["Day"], errors="coerce")
df_m                  = df_m.dropna(subset=["day"])

# Campaign type / subtype (present in newer exports)
if "Campaign type" in df_m.columns:
    df_m["campaign_type"]    = df_m["Campaign type"].fillna("Unknown").astype(str).str.strip()
else:
    df_m["campaign_type"]    = "Unknown"

if "Campaign subtype" in df_m.columns:
    df_m["campaign_subtype"] = df_m["Campaign subtype"].fillna("").astype(str).str.strip()
else:
    df_m["campaign_subtype"] = ""

if "Campaign" in df_m.columns:
    df_m["campaign_name"]    = df_m["Campaign"].fillna("").astype(str).str.strip()
else:
    df_m["campaign_name"]    = ""

# Overall daily aggregation (all campaign types)
daily = (
    df_m.groupby("day")
    .agg(cost=("cost","sum"), conv_value=("conv_value","sum"), conversions=("conversions","sum"))
    .reset_index()
    .sort_values("day")
)
daily["roas"]    = (daily["conv_value"] / daily["cost"].replace(0, float("nan")) * 100).fillna(0).round(2)
daily["day_str"] = daily["day"].dt.strftime("%Y-%m-%d")

print(f"  → {len(daily)} daily rows, {daily['day'].min().date()} → {daily['day'].max().date()}")

# Per-campaign-type daily aggregation (for chart filter)
daily_ct = (
    df_m.groupby(["day", "campaign_type"])
    .agg(cost=("cost","sum"), conv_value=("conv_value","sum"), conversions=("conversions","sum"))
    .reset_index()
)
daily_ct["roas"]    = (daily_ct["conv_value"] / daily_ct["cost"].replace(0, float("nan")) * 100).fillna(0).round(2)
daily_ct["day_str"] = daily_ct["day"].dt.strftime("%Y-%m-%d")

# Build lookup: {campaign_type: {day_str: {cost, cv, conv, roas}}}
ctype_daily = {}
for ct, grp in daily_ct.groupby("campaign_type"):
    ctype_daily[ct] = {
        row["day_str"]: {
            "cost": round(row["cost"], 2),
            "cv":   round(row["conv_value"], 2),
            "conv": round(row["conversions"], 2),
            "roas": round(row["roas"], 2),
        }
        for _, row in grp.iterrows()
    }

all_ctypes = sorted(ctype_daily.keys())
print(f"  Campaign types: {', '.join(all_ctypes)}")

# Campaign name → type mapping (for enriching changes)
camp_to_ctype = df_m.groupby("campaign_name")["campaign_type"].first().to_dict()

# ─── 2. Load & process change history ─────────────────────────────────────────
print("Loading change history CSV…")

skip_c = detect_skip(CHANGES_PATH, {"date & time", "date", "datetime", "time", "date and time"})
df_c = pd.read_csv(CHANGES_PATH, skiprows=skip_c, encoding="utf-8-sig")
df_c.columns = df_c.columns.str.strip()

# Detect date column
date_col = next((c for c in df_c.columns if "date" in c.lower()), None)
if not date_col:
    date_col = df_c.columns[0]

df_c["datetime"] = pd.to_datetime(df_c[date_col], errors="coerce")
df_c["date"]     = df_c["datetime"].dt.date
df_c["date_str"] = df_c["datetime"].dt.strftime("%Y-%m-%d")

for col in ["Campaign", "Ad group", "Changes", "User", "Account"]:
    if col in df_c.columns:
        df_c[col] = df_c[col].fillna("").astype(str)
    else:
        df_c[col] = ""

# Enrich with campaign type from metrics
df_c["campaign_type_change"] = df_c["Campaign"].map(camp_to_ctype).fillna("Account-level")

# ─── 3. Categorise changes ────────────────────────────────────────────────────
def categorise(row):
    changes = row["Changes"].lower()
    bid_kw    = ["bid strategy","target roas","troas","target cpa","tcpa","max conv","maximize conv",
                 "cpc","roas target","bidding","budget","mac cpc","tolerance","bid limit",
                 "portfolio strategy","target roas portfolio"]
    conv_kw   = ["conversion","convert"]
    access_kw = ["access","invitation","granted","removed user","permission","activated for",
                 "read only","reports only","standard","admin","notification setting"]
    script_kw = ["rule created","script","automated rule","rule name","negative keyword script",
                 "negative keyword","negative broad","negative phrase","negative exact"]
    report_kw = ["report created","download format","email recipients","report name",
                 "report changed","report removed"]

    if any(k in changes for k in report_kw):   return "Report"
    if any(k in changes for k in script_kw):   return "Script/Rule"
    if any(k in changes for k in access_kw):   return "Access/Users"
    if any(k in changes for k in conv_kw):     return "Conversion"
    if any(k in changes for k in bid_kw):      return "Bid Strategy"
    return "Other"

df_c["type"] = df_c.apply(categorise, axis=1)

type_colors = {
    "Bid Strategy": "#f59e0b",
    "Conversion":   "#8b5cf6",
    "Access/Users": "#06b6d4",
    "Script/Rule":  "#10b981",
    "Report":       "#64748b",
    "Other":        "#e94560",
}

print("  Change types:")
for t, cnt in df_c["type"].value_counts().items():
    print(f"    {t}: {cnt}")

# ─── 4. Parse before/after values from change text ─────────────────────────────
def parse_before_after(text):
    """Extract field → (before, after) pairs from Google Ads change text."""
    results = []
    cleaned = text.replace('""', '"').replace('\r', '')
    # Match patterns like "Field changed/increased/decreased from X to Y"
    # Also handles "Field set to Y" (no before)
    pattern = re.compile(
        r'([^\n"]{2,60}?)\s+(?:changed|increased|decreased)\s+from\s+'
        r'"?([^"\n]{1,60}?)"?\s+to\s+"?([^"\n]{1,60}?)"?(?=\s*\n|$)',
        re.IGNORECASE | re.MULTILINE
    )
    for m in pattern.finditer(cleaned):
        field  = re.sub(r'^"[^"]+"\s*:\s*', '', m.group(1)).strip().lstrip('\n ')
        before = m.group(2).strip().rstrip('.,')
        after  = m.group(3).strip().rstrip('.,')
        if field and before and after and len(field) <= 60:
            results.append({"field": field, "before": before, "after": after})
    return results

# ─── 5. Impact scoring (7-day window before vs after) ─────────────────────────
print("Computing impact scores…")
daily_idx = daily.set_index("day")

def window_mean(center, before, col, w=7):
    if before:
        start, end = center - pd.Timedelta(days=w), center - pd.Timedelta(days=1)
    else:
        start, end = center + pd.Timedelta(days=1), center + pd.Timedelta(days=w)
    sub = daily_idx[(daily_idx.index >= start) & (daily_idx.index <= end)]
    return sub[col].mean() if len(sub) > 0 else None

impact_rows = []
for _, row in df_c.iterrows():
    if pd.isnull(row["datetime"]):
        continue
    cd = row["datetime"].normalize()
    b_cv   = window_mean(cd, True,  "conv_value")
    a_cv   = window_mean(cd, False, "conv_value")
    b_cost = window_mean(cd, True,  "cost")
    a_cost = window_mean(cd, False, "cost")
    b_conv = window_mean(cd, True,  "conversions")
    a_conv = window_mean(cd, False, "conversions")

    pct = (a_cv - b_cv) / b_cv * 100 if (b_cv and a_cv is not None and b_cv > 0) else None

    impact_rows.append({
        "datetime":     row["datetime"].isoformat(),
        "date_str":     row["date_str"],
        "user":         row["User"],
        "campaign":     row["Campaign"] if row["Campaign"] else "Account-level",
        "campaign_type": row["campaign_type_change"],
        "type":         row["type"],
        "changes":      row["Changes"][:300].replace("\n", " ").strip() + ("…" if len(row["Changes"]) > 300 else ""),
        "changes_full": row["Changes"],
        "before_after": parse_before_after(row["Changes"]),
        "before_cv":    round(b_cv, 2)   if b_cv   is not None else None,
        "after_cv":     round(a_cv, 2)   if a_cv   is not None else None,
        "impact_pct":   round(pct, 2)    if pct    is not None else None,
        "before_cost":  round(b_cost, 2) if b_cost is not None else None,
        "after_cost":   round(a_cost, 2) if a_cost is not None else None,
        "before_conv":  round(b_conv, 2) if b_conv is not None else None,
        "after_conv":   round(a_conv, 2) if a_conv is not None else None,
    })

impact_df = pd.DataFrame(impact_rows)
impact_df = impact_df.sort_values("impact_pct", key=lambda x: x.abs(), ascending=False, na_position="last")
top10 = impact_df.head(10).to_dict(orient="records")
print(f"  → {len(impact_df)} scored changes")

# ─── 6. Prepare chart / annotation data ──────────────────────────────────────
labels    = daily["day_str"].tolist()
cost_data = daily["cost"].round(2).tolist()
cv_data   = daily["conv_value"].round(2).tolist()
conv_data = daily["conversions"].round(2).tolist()
roas_data = daily["roas"].tolist()

# Annotations: one entry per change (all, not just top 10)
annotations = []
for _, row in df_c.dropna(subset=["datetime"]).sort_values("datetime").iterrows():
    ds = row["date_str"]
    if ds in labels:
        ba = parse_before_after(row["Changes"])
        annotations.append({
            "date":          ds,
            "type":          row["type"],
            "color":         type_colors[row["type"]],
            "user":          row["User"],
            "campaign":      row["Campaign"] if row["Campaign"] else "Account-level",
            "campaign_type": row["campaign_type_change"],
            "changes":       row["Changes"][:400].replace("\n", " ").strip(),
            "before_after":  ba,
        })

# Full changelog (newest first)
changelog = []
for _, row in df_c.sort_values("datetime", ascending=False).iterrows():
    changelog.append({
        "date":          row["date_str"],
        "type":          row["type"],
        "color":         type_colors[row["type"]],
        "user":          row["User"],
        "campaign":      row["Campaign"] if row["Campaign"] else "Account-level",
        "campaign_type": row["campaign_type_change"],
        "changes":       row["Changes"].replace("\n", " ").strip()[:500],
    })

# Summary stats
total_cost    = round(daily["cost"].sum(), 2)
total_cv      = round(daily["conv_value"].sum(), 2)
total_conv    = round(daily["conversions"].sum(), 2)
avg_roas      = round(daily["roas"].mean(), 2)
total_changes = len(df_c)
all_users     = sorted(df_c["User"].unique().tolist())
all_types     = list(type_colors.keys())
all_campaigns = sorted(df_c["Campaign"].replace("", "Account-level").unique().tolist())

# ─── 7. Serialise to JSON ─────────────────────────────────────────────────────
print("Building HTML dashboard…")

J = lambda x: json.dumps(x, ensure_ascii=False)


html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Google Ads Change Impact Dashboard</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/apexcharts@3.54.0/dist/apexcharts.min.js"></script>
<style>
  :root {{
    --bg:          #080812;
    --surface:     #0f0f1e;
    --surface2:    #14142a;
    --surface3:    #1a1a38;
    --accent:      #06b6d4;
    --accent2:     #8b5cf6;
    --accent3:     #e94560;
    --text:        #e2e8f0;
    --muted:       #64748b;
    --border:      #1e1e3a;
    --border-glow: rgba(6,182,212,0.2);
    --green:       #10b981;
    --red:         #ef4444;
    --amber:       #f59e0b;
  }}
  *{{ box-sizing:border-box; margin:0; padding:0; }}
  body {{
    background: var(--bg);
    background-image:
      radial-gradient(ellipse at 15% 5%,  rgba(6,182,212,0.06) 0%, transparent 50%),
      radial-gradient(ellipse at 85% 90%, rgba(139,92,246,0.06) 0%, transparent 50%);
    color: var(--text);
    font-family: 'Inter', system-ui, sans-serif;
    min-height: 100vh;
    padding-bottom: 80px;
    font-size: 14px;
  }}

  /* ── Header ── */
  .header {{
    background: linear-gradient(135deg, #0c0c20, #111128, #0c0c20);
    border-bottom: 1px solid var(--border);
    padding: 26px 40px 22px;
    display: flex; align-items: center; justify-content: space-between;
    flex-wrap: wrap; gap: 16px;
    position: relative; overflow: hidden;
  }}
  .header::after {{
    content: ''; position: absolute; bottom: 0; left: 0; right: 0; height: 1px;
    background: linear-gradient(90deg, transparent, var(--accent) 30%, var(--accent2) 70%, transparent);
    opacity: 0.5;
  }}
  .header h1 {{
    font-size: 1.55rem; font-weight: 700; letter-spacing: -0.04em;
    background: linear-gradient(90deg, var(--accent), var(--accent2));
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  }}
  .header p {{ color: var(--muted); font-size: 0.82rem; margin-top: 4px; }}

  /* ── KPI Cards ── */
  .kpi-row {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(175px, 1fr));
    gap: 14px; padding: 28px 40px 0;
  }}
  .kpi {{
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 14px; padding: 18px 20px;
    position: relative; overflow: hidden;
    transition: transform .2s, border-color .2s, box-shadow .2s; cursor: default;
  }}
  .kpi:hover {{ transform: translateY(-2px); }}
  .kpi::before {{
    content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px;
    border-radius: 14px 14px 0 0;
  }}
  .kpi.cost::before    {{ background: var(--accent3); }}
  .kpi.cv::before      {{ background: var(--accent); }}
  .kpi.conv::before    {{ background: var(--green); }}
  .kpi.roas::before    {{ background: var(--amber); }}
  .kpi.changes::before {{ background: var(--accent2); }}
  .kpi.cost:hover    {{ border-color:rgba(233,69,96,.3); box-shadow:0 0 24px rgba(233,69,96,.1); }}
  .kpi.cv:hover      {{ border-color:rgba(6,182,212,.3); box-shadow:0 0 24px rgba(6,182,212,.1); }}
  .kpi.conv:hover    {{ border-color:rgba(16,185,129,.3); box-shadow:0 0 24px rgba(16,185,129,.1); }}
  .kpi.roas:hover    {{ border-color:rgba(245,158,11,.3); box-shadow:0 0 24px rgba(245,158,11,.1); }}
  .kpi.changes:hover {{ border-color:rgba(139,92,246,.3); box-shadow:0 0 24px rgba(139,92,246,.1); }}
  .kpi-label {{ font-size: 0.68rem; color: var(--muted); text-transform: uppercase; letter-spacing: 1.2px; font-weight: 600; }}
  .kpi-value {{ font-size: 1.7rem; font-weight: 700; margin-top: 7px; letter-spacing: -0.04em;
                font-variant-numeric: tabular-nums; font-family: 'JetBrains Mono', monospace; }}
  .kpi-sub   {{ font-size: 0.72rem; color: var(--muted); margin-top: 4px; }}
  .kpi.cost .kpi-value    {{ color: var(--accent3); }}
  .kpi.cv .kpi-value      {{ color: var(--accent); }}
  .kpi.conv .kpi-value    {{ color: var(--green); }}
  .kpi.roas .kpi-value    {{ color: var(--amber); }}
  .kpi.changes .kpi-value {{ color: var(--accent2); }}

  /* ── Section ── */
  .section {{ padding: 28px 40px 0; }}
  .section-title {{
    font-size: 0.68rem; font-weight: 700; color: var(--accent);
    text-transform: uppercase; letter-spacing: 2px; margin-bottom: 14px;
    display: flex; align-items: center; gap: 10px;
  }}
  .section-title::after {{
    content: ''; flex: 1; height: 1px;
    background: linear-gradient(90deg, var(--border), transparent);
  }}

  /* ── Chart filter ── */
  .chart-filter-bar {{
    display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 12px; align-items: center;
  }}
  .chart-filter-bar label {{ font-size: 0.7rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.8px; }}
  .chart-filter-bar select {{
    background: var(--surface2); border: 1px solid var(--border);
    border-radius: 8px; color: var(--text); padding: 6px 12px;
    font-size: 0.8rem; outline: none; cursor: pointer; font-family: 'Inter', sans-serif;
    transition: border-color .2s;
  }}
  .chart-filter-bar select:focus, .chart-filter-bar input[type=date]:focus {{ border-color: var(--accent); }}
  .chart-filter-bar input[type=date] {{
    background: var(--surface2); border: 1px solid var(--border);
    border-radius: 8px; color: var(--text); font-family: 'Inter', sans-serif;
    cursor: pointer; transition: border-color .2s;
    color-scheme: dark;
  }}
  .chart-tip {{ margin-left: auto; font-size: 0.68rem; color: var(--muted); }}

  /* ── Annotation type toggles ── */
  .annot-legend {{ display: flex; flex-wrap: wrap; gap: 9px; margin-bottom: 12px; }}
  .annot-item {{
    display: flex; align-items: center; gap: 6px;
    background: var(--surface2); border: 1px solid var(--border);
    border-radius: 20px; padding: 4px 12px;
    font-size: 0.71rem; font-weight: 600; cursor: pointer;
    transition: all .2s; user-select: none;
  }}
  .annot-item:hover {{ border-color: var(--border-glow); }}
  .annot-item.inactive {{ opacity: 0.28; }}
  .annot-swatch {{ width: 8px; height: 8px; border-radius: 2px; flex-shrink: 0; }}
  .annot-count {{
    background: rgba(255,255,255,.07); border-radius: 10px;
    padding: 1px 5px; font-size: 0.65rem;
  }}

  /* ── Chart cards ── */
  .chart-card {{
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 16px; padding: 20px 22px 10px; margin-bottom: 20px;
    transition: border-color .25s;
  }}
  .chart-card:hover {{ border-color: var(--border-glow); }}
  .chart-card h3 {{
    font-size: 0.69rem; color: var(--muted); font-weight: 600;
    text-transform: uppercase; letter-spacing: 1.5px; margin-bottom: 4px;
  }}
  .chart-wrap {{ position: relative; overflow: visible; }}

  /* ── Change markers (HTML overlay on charts) ── */
  .change-marker {{
    position: absolute; z-index: 10; cursor: pointer;
    display: flex; justify-content: center; align-items: flex-start;
  }}
  .change-marker:hover .cm-line {{ opacity: 1; }}
  .change-marker:hover .cm-dot {{ transform: translateX(-50%) scale(1.25); }}
  .cm-line {{
    width: 2px; height: 100%;
    opacity: 0.7; transition: opacity .15s;
    border-radius: 1px;
  }}
  .cm-dot {{
    position: absolute; top: -6px; left: 50%; transform: translateX(-50%);
    border-radius: 50%; border: 2px solid #080812;
    display: flex; align-items: center; justify-content: center;
    font-size: 7px; font-weight: 800; color: #080812;
    transition: transform .15s;
    font-family: 'JetBrains Mono', monospace;
    box-shadow: 0 0 8px var(--cm-color);
  }}
  .legend-row {{
    display: flex; flex-wrap: wrap; gap: 14px;
    padding-top: 8px; border-top: 1px solid var(--border); margin-top: 4px;
  }}
  .legend-item {{ display: flex; align-items: center; gap: 6px; font-size: 0.72rem; color: var(--muted); }}
  .legend-line {{ width: 16px; height: 2px; border-radius: 2px; flex-shrink: 0; }}
  .legend-dot  {{ width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }}

  /* ── Tables ── */
  .table-container {{
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 16px; overflow: hidden; margin-bottom: 20px;
  }}
  .table-scroll {{ overflow-x: auto; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.8rem; }}
  thead th {{
    background: var(--surface2); padding: 12px 14px; text-align: left;
    font-size: 0.66rem; text-transform: uppercase; letter-spacing: 1px;
    color: var(--muted); border-bottom: 1px solid var(--border); white-space: nowrap;
  }}
  tbody tr {{ border-bottom: 1px solid var(--border); transition: background .12s; }}
  tbody tr:last-child {{ border-bottom: none; }}
  tbody tr:hover {{ background: rgba(255,255,255,.022); }}
  tbody td {{ padding: 11px 14px; vertical-align: middle; color: var(--text); }}
  .impact-pill {{
    display: inline-flex; align-items: center; gap: 3px;
    padding: 2px 9px; border-radius: 20px; font-size: 0.74rem; font-weight: 700;
    font-family: 'JetBrains Mono', monospace;
  }}
  .impact-pos {{ background: rgba(16,185,129,.12); color: var(--green); }}
  .impact-neg {{ background: rgba(239,68,68,.12); color: var(--red); }}
  .impact-neu {{ background: rgba(100,116,139,.12); color: var(--muted); }}
  .type-badge {{
    display: inline-block; padding: 2px 9px; border-radius: 20px;
    font-size: 0.67rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.4px;
  }}
  .change-text {{
    color: var(--muted); font-size: 0.74rem; max-width: 340px;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis; cursor: pointer;
  }}
  .change-text:hover {{ color: var(--text); }}
  .mono {{ font-family: 'JetBrains Mono', monospace; font-size: 0.77rem; }}

  /* ── Filter bar ── */
  .filter-bar {{
    display: flex; flex-wrap: wrap; gap: 10px;
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 12px; padding: 13px 17px; margin-bottom: 13px; align-items: center;
  }}
  .filter-bar label {{ font-size: 0.67rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.8px; font-weight: 600; }}
  .filter-bar select, .filter-bar input {{
    background: var(--surface2); border: 1px solid var(--border);
    border-radius: 8px; color: var(--text); padding: 6px 12px;
    font-size: 0.79rem; outline: none; font-family: 'Inter', sans-serif;
    transition: border-color .2s;
  }}
  .filter-bar select:focus, .filter-bar input:focus {{ border-color: var(--accent); }}
  .filter-bar input {{ min-width: 190px; }}
  .filter-sep {{ height: 22px; width: 1px; background: var(--border); }}
  .reset-btn {{
    background: transparent; border: 1px solid var(--border); border-radius: 8px;
    color: var(--muted); padding: 6px 12px; font-size: 0.75rem; cursor: pointer;
    font-family: 'Inter', sans-serif; transition: all .2s;
  }}
  .reset-btn:hover {{ border-color: var(--accent3); color: var(--accent3); }}
  .row-count {{ margin-left: auto; font-size: 0.73rem; color: var(--muted); }}

  /* ── Pagination ── */
  .pagination {{
    display: flex; align-items: center; justify-content: center; gap: 6px; padding: 14px 0 4px;
  }}
  .page-btn {{
    background: var(--surface2); border: 1px solid var(--border); border-radius: 8px;
    color: var(--text); padding: 5px 11px; font-size: 0.74rem; cursor: pointer;
    font-family: 'Inter', sans-serif; transition: all .2s;
  }}
  .page-btn:hover {{ border-color: var(--accent); color: var(--accent); }}
  .page-btn.active {{ background: var(--surface3); border-color: var(--accent); color: var(--accent); font-weight: 700; }}
  .page-btn:disabled {{ opacity: .3; cursor: not-allowed; }}
  .page-info {{ font-size: 0.73rem; color: var(--muted); padding: 0 6px; }}

  /* ── Change annotation hover popup ── */
  #annotPopup {{
    display: none; position: fixed; z-index: 9999;
    background: #0d0d22;
    border: 1px solid rgba(6,182,212,0.25);
    border-radius: 14px; padding: 15px 17px;
    max-width: 370px; min-width: 250px;
    box-shadow: 0 16px 48px rgba(0,0,0,.8), 0 0 0 1px rgba(255,255,255,.04), 0 0 20px rgba(6,182,212,.06);
    pointer-events: none; line-height: 1.55; font-size: 0.79rem;
  }}
  #annotPopup.visible {{ display: block; }}
  .popup-date {{
    font-family: 'JetBrains Mono', monospace; font-size: 0.7rem;
    color: var(--accent); font-weight: 700; margin-bottom: 9px; letter-spacing: 0.5px;
  }}
  .popup-change {{
    border-top: 1px solid rgba(30,30,58,0.8); padding: 8px 0 3px; margin-bottom: 1px;
  }}
  .popup-change:first-of-type {{ border-top: none; padding-top: 0; }}
  .popup-change-header {{ display: flex; align-items: center; gap: 7px; margin-bottom: 4px; flex-wrap: wrap; }}
  .popup-user {{ color: var(--muted); font-size: 0.7rem; }}
  .popup-campaign {{ color: var(--muted); font-size: 0.68rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 210px; }}
  .popup-summary {{ color: #b0bac9; font-size: 0.74rem; line-height: 1.45; margin-top: 3px; }}
  .popup-ba {{ margin-top: 6px; }}
  .popup-ba-row {{
    display: flex; align-items: center; gap: 5px; margin-bottom: 3px; flex-wrap: wrap;
    font-family: 'JetBrains Mono', monospace; font-size: 0.7rem;
  }}
  .popup-ba-field  {{ color: var(--muted); flex-shrink: 0; max-width: 140px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
  .popup-ba-before {{ color: #475569; text-decoration: line-through; }}
  .popup-ba-arrow  {{ color: #334155; }}
  .popup-ba-after  {{ color: var(--green); font-weight: 700; }}
  .popup-more      {{ color: var(--muted); font-size: 0.67rem; margin-top: 5px; font-style: italic; }}

  /* ── ApexCharts dark theme overrides ── */
  .apexcharts-canvas {{ background: transparent !important; }}
  .apexcharts-tooltip {{
    background: #0d0d22 !important;
    border: 1px solid rgba(6,182,212,0.25) !important;
    border-radius: 10px !important;
    box-shadow: 0 8px 32px rgba(0,0,0,.6) !important;
    font-family: 'Inter', sans-serif !important;
  }}
  .apexcharts-tooltip-title {{
    background: #14142a !important;
    border-bottom: 1px solid var(--border) !important;
    font-family: 'JetBrains Mono', monospace !important;
    color: var(--accent) !important;
    font-size: 0.74rem !important;
  }}
  .apexcharts-tooltip-series-group {{ padding: 6px 12px !important; }}
  .apexcharts-xaxistooltip {{ display: none !important; }}

  /* ── Scrollbar ── */
  ::-webkit-scrollbar {{ width: 5px; height: 5px; }}
  ::-webkit-scrollbar-track {{ background: var(--bg); }}
  ::-webkit-scrollbar-thumb {{ background: var(--border); border-radius: 3px; }}
  ::-webkit-scrollbar-thumb:hover {{ background: var(--muted); }}

  @media (max-width: 768px) {{
    .header, .kpi-row, .section {{ padding-left: 16px; padding-right: 16px; }}
    .kpi-value {{ font-size: 1.35rem; }}
    #annotPopup {{ max-width: calc(100vw - 32px); }}
  }}
</style>
</head>
<body>

<!-- ── HEADER ── -->
<div class="header">
  <div>
    <h1>Google Ads Change Impact</h1>
    <p>Account changes vs performance &nbsp;·&nbsp; {daily['day'].min().strftime('%b %d, %Y')} – {daily['day'].max().strftime('%b %d, %Y')}</p>
  </div>
</div>

<!-- ── KPI CARDS ── -->
<div class="kpi-row">
  <div class="kpi cost">
    <div class="kpi-label">Total Spend</div>
    <div class="kpi-value">&euro;{total_cost:,.0f}</div>
    <div class="kpi-sub">All campaigns</div>
  </div>
  <div class="kpi cv">
    <div class="kpi-label">Conv. Value</div>
    <div class="kpi-value">&euro;{total_cv:,.0f}</div>
    <div class="kpi-sub">Revenue from conversions</div>
  </div>
  <div class="kpi conv">
    <div class="kpi-label">Conversions</div>
    <div class="kpi-value">{total_conv:,.0f}</div>
    <div class="kpi-sub">All conversion events</div>
  </div>
  <div class="kpi roas">
    <div class="kpi-label">Avg ROAS</div>
    <div class="kpi-value">{avg_roas:.1f}%</div>
    <div class="kpi-sub">Conv. value / Cost</div>
  </div>
  <div class="kpi changes">
    <div class="kpi-label">Changes</div>
    <div class="kpi-value">{total_changes}</div>
    <div class="kpi-sub">Logged account events</div>
  </div>
</div>

<!-- ── CHARTS ── -->
<div class="section">
  <div class="section-title">Performance Timeline</div>

  <div class="chart-filter-bar">
    <label>Campaign type</label>
    <select id="ctypeFilter">
      <option value="all">All types</option>
      {''.join(f'<option value="{ct}">{ct}</option>' for ct in all_ctypes)}
    </select>
    <div class="filter-sep" style="height:22px;width:1px;background:var(--border)"></div>
    <label>Date range</label>
    <select id="rangePicker">
      <option value="30">Last 30 days</option>
      <option value="60">Last 60 days</option>
      <option value="90">Last 90 days</option>
      <option value="180">Last 180 days</option>
      <option value="all" selected>All data</option>
      <option value="custom">Custom</option>
    </select>
    <input type="date" id="dateFrom" value="{daily['day'].min().strftime('%Y-%m-%d')}" style="font-size:.75rem;padding:5px 8px">
    <span style="color:var(--muted);font-size:.75rem">→</span>
    <input type="date" id="dateTo" value="{daily['day'].max().strftime('%Y-%m-%d')}" style="font-size:.75rem;padding:5px 8px">
    <span class="chart-tip" id="rangeLbl">{daily['day'].min().strftime('%Y-%m-%d')} → {daily['day'].max().strftime('%Y-%m-%d')}  ({len(daily)} days)</span>
  </div>

  <div class="annot-legend" id="typeLegend"></div>

  <div class="chart-card">
    <h3>Daily Spend vs Conversion Value (€)</h3>
    <div class="chart-wrap"><div id="chart1"></div></div>
    <div class="legend-row">
      <div class="legend-item"><div class="legend-line" style="background:var(--accent3)"></div> Cost (€)</div>
      <div class="legend-item"><div class="legend-line" style="background:var(--accent)"></div> Conv. Value (€)</div>
    </div>
  </div>

  <div class="chart-card">
    <h3>Daily Conversions &amp; ROAS (%)</h3>
    <div class="chart-wrap"><div id="chart2"></div></div>
    <div class="legend-row">
      <div class="legend-item"><div class="legend-dot" style="background:var(--green)"></div> Conversions</div>
      <div class="legend-item"><div class="legend-dot" style="background:var(--amber)"></div> ROAS %</div>
    </div>
  </div>
</div>

<!-- ── TOP 10 IMPACT ── -->
<div class="section">
  <div class="section-title">Top 10 Most Impactful Changes</div>
  <div class="table-container">
    <div class="table-scroll">
      <table>
        <thead>
          <tr>
            <th>#</th><th>Date</th><th>Type</th><th>User</th>
            <th>Conv. Value Impact</th>
            <th>7d CV Before → After</th>
            <th>7d Cost Before → After</th>
            <th>7d Convs Before → After</th>
            <th>Change Summary</th>
          </tr>
        </thead>
        <tbody id="impactBody"></tbody>
      </table>
    </div>
  </div>
</div>

<!-- ── CHANGE LOG ── -->
<div class="section">
  <div class="section-title">Full Change Log</div>
  <div class="filter-bar">
    <label>Type</label>
    <select id="filterType"><option value="">All types</option></select>
    <div class="filter-sep"></div>
    <label>Cmpn Type</label>
    <select id="filterCampaignType"><option value="">All</option></select>
    <div class="filter-sep"></div>
    <label>User</label>
    <select id="filterUser"><option value="">All users</option></select>
    <div class="filter-sep"></div>
    <input type="text" id="filterSearch" placeholder="Search changes, campaign, user…">
    <button class="reset-btn" onclick="resetFilters()">Reset</button>
    <span class="row-count" id="rowCount"></span>
  </div>
  <div class="table-container">
    <div class="table-scroll">
      <table>
        <thead>
          <tr>
            <th>Date</th><th>Type</th><th>Cmpn Type</th>
            <th>User</th><th>Campaign</th><th>Changes</th>
          </tr>
        </thead>
        <tbody id="changelogBody"></tbody>
      </table>
    </div>
    <div class="pagination" id="pagination"></div>
  </div>
</div>

<!-- ── ANNOTATION HOVER POPUP ── -->
<div id="annotPopup"></div>

<script>
// ── DATA ──────────────────────────────────────────────────────────────────────
const LABELS      = {J(labels)};
const COST_DATA   = {J(cost_data)};
const CV_DATA     = {J(cv_data)};
const CONV_DATA   = {J(conv_data)};
const ROAS_DATA   = {J(roas_data)};
const CTYPE_DAILY = {J(ctype_daily)};
const ANNOTATIONS = {J(annotations)};
const TOP10       = {J(top10)};
const CHANGELOG   = {J(changelog)};
const TYPE_COLORS = {J(type_colors)};
const ALL_USERS   = {J(all_users)};
const ALL_TYPES   = {J(all_types)};

// ── ANNOTATION STATE ──────────────────────────────────────────────────────────
const activeTypes = new Set(ALL_TYPES);

// Group annotations by date
const annotByDate = {{}};
ANNOTATIONS.forEach(a => {{
  if (!annotByDate[a.date]) annotByDate[a.date] = [];
  annotByDate[a.date].push(a);
}});

// ── (ApexCharts annotations removed — using HTML overlay markers instead) ────

// ── APEX CHART BASE CONFIG ────────────────────────────────────────────────────
const darkTheme = {{
  mode: 'dark',
  palette: 'palette1',
  monochrome: {{ enabled: false }},
}};
const gridCfg = {{
  borderColor: '#1e1e3a',
  strokeDashArray: 0,
  xaxis: {{ lines: {{ show: false }} }},
  yaxis: {{ lines: {{ show: true }} }},
}};
// (xaxis built dynamically via buildXaxis() to respect date range)

// ── DATE RANGE STATE ─────────────────────────────────────────────────────────
let rangeStart = 0;          // index into LABELS
let rangeEnd   = LABELS.length - 1;

function getVisibleLabels() {{ return LABELS.slice(rangeStart, rangeEnd + 1); }}
function getVisibleData(arr) {{ return arr.slice(rangeStart, rangeEnd + 1); }}

// ── POPUP HELPERS ─────────────────────────────────────────────────────────────
const popup = document.getElementById('annotPopup');

function buildPopupHTML(date) {{
  const changes = (annotByDate[date] || []).filter(c => activeTypes.has(c.type));
  if (!changes.length) return '';
  let h = `<div class="popup-date">${{date}}</div>`;
  changes.slice(0, 5).forEach(c => {{
    h += `<div class="popup-change">
      <div class="popup-change-header">
        <span class="type-badge" style="background:${{c.color}}20;color:${{c.color}};border:1px solid ${{c.color}}40;font-size:.6rem">${{c.type}}</span>
        <span class="popup-user">${{c.user}}</span>
      </div>`;
    if (c.campaign && c.campaign !== 'Account-level')
      h += `<div class="popup-campaign">&#128193; ${{c.campaign}}</div>`;
    if (c.before_after && c.before_after.length) {{
      h += `<div class="popup-ba">`;
      c.before_after.slice(0, 4).forEach(ba => {{
        h += `<div class="popup-ba-row">
          <span class="popup-ba-field">${{ba.field}}</span>
          <span class="popup-ba-before">${{ba.before}}</span>
          <span class="popup-ba-arrow">&#8594;</span>
          <span class="popup-ba-after">${{ba.after}}</span>
        </div>`;
      }});
      h += `</div>`;
    }} else {{
      const s = c.changes.replace(/\\s+/g,' ').trim().slice(0,150);
      h += `<div class="popup-summary">${{s}}${{c.changes.length > 150 ? '&#8230;' : ''}}</div>`;
    }}
    h += `</div>`;
  }});
  if (changes.length > 5)
    h += `<div class="popup-more">+ ${{changes.length - 5}} more changes this day</div>`;
  return h;
}}

function showPopup(e, date) {{
  const html = buildPopupHTML(date);
  if (!html) {{ popup.classList.remove('visible'); return; }}
  popup.innerHTML = html;
  popup.classList.add('visible');
  const W = window.innerWidth, H = window.innerHeight;
  const pw = popup.offsetWidth || 320, ph = popup.offsetHeight || 200;
  let x = e.clientX + 16, y = e.clientY - 10;
  if (x + pw > W - 10) x = e.clientX - pw - 16;
  if (y + ph > H - 10) y = H - ph - 10;
  if (y < 10) y = 10;
  popup.style.left = x + 'px';
  popup.style.top  = y + 'px';
}}

function hidePopup() {{ popup.classList.remove('visible'); }}

// ── CREATE HTML OVERLAY MARKERS ON CHARTS ─────────────────────────────────────
function createChangeMarkers(chartDivId, chartInstance) {{
  const chartEl = document.getElementById(chartDivId);
  if (!chartEl) return;
  const wrapper = chartEl.closest('.chart-wrap');
  if (!wrapper) return;

  // Remove old markers
  wrapper.querySelectorAll('.change-marker').forEach(el => el.remove());

  let plotLeft, plotTop, plotWidth, plotHeight;

  // Method 1: Use horizontal grid lines to find exact plot bounds
  // ApexCharts always renders these — they span the full plot width
  const hLines = chartEl.querySelectorAll('.apexcharts-gridlines-horizontal line');
  const svgEl = chartEl.querySelector('svg');

  if (hLines.length >= 2 && svgEl) {{
    // Grid lines have x1, y1, x2, y2 in SVG coords — convert via getBoundingClientRect
    const wrapperRect = wrapper.getBoundingClientRect();
    // The grid group holds all lines — its bounding box IS the plot area
    const gridGroup = chartEl.querySelector('.apexcharts-gridlines-horizontal');
    const gridRect = gridGroup.getBoundingClientRect();
    plotLeft   = gridRect.left - wrapperRect.left;
    plotTop    = gridRect.top  - wrapperRect.top;
    plotWidth  = gridRect.width;
    plotHeight = gridRect.height;
  }}
  // Method 2: Try the inner graphical group
  else if (svgEl) {{
    const inner = chartEl.querySelector('.apexcharts-inner');
    if (inner) {{
      const wrapperRect = wrapper.getBoundingClientRect();
      const innerRect = inner.getBoundingClientRect();
      plotLeft   = innerRect.left - wrapperRect.left;
      plotTop    = innerRect.top  - wrapperRect.top;
      plotWidth  = innerRect.width;
      plotHeight = innerRect.height;
    }}
  }}
  // Method 3: Estimate from SVG dimensions (last resort)
  if ((!plotWidth || plotWidth < 10) && svgEl) {{
    const wrapperRect = wrapper.getBoundingClientRect();
    const svgRect = svgEl.getBoundingClientRect();
    // Typical ApexCharts padding: ~65px left (y-axis), ~15px right, ~30px top, ~45px bottom
    plotLeft   = svgRect.left - wrapperRect.left + 65;
    plotTop    = svgRect.top  - wrapperRect.top  + 30;
    plotWidth  = svgRect.width - 80;
    plotHeight = svgRect.height - 75;
    console.log('createChangeMarkers: using SVG dimension estimate for', chartDivId);
  }}

  if (!plotWidth || plotWidth < 10) {{
    console.warn('createChangeMarkers: could not determine plot area for', chartDivId);
    return;
  }}

  const visLabels = getVisibleLabels();
  const numPoints = visLabels.length;
  if (numPoints < 2) return;

  // Find unique dates with changes in visible range
  visLabels.forEach((label, i) => {{
    const changes = (annotByDate[label] || []).filter(a => activeTypes.has(a.type));
    if (!changes.length) return;

    const x = plotLeft + (i / (numPoints - 1)) * plotWidth;
    const color = changes[0].color;
    const count = changes.length;

    // Marker container (wider hit area for easy hover)
    const marker = document.createElement('div');
    marker.className = 'change-marker';
    marker.style.cssText = `left:${{x-8}}px; top:${{plotTop}}px; width:16px; height:${{plotHeight}}px;`;

    // Visible line
    const line = document.createElement('div');
    line.className = 'cm-line';
    line.style.background = `linear-gradient(to bottom, ${{color}}, ${{color}}50)`;
    marker.appendChild(line);

    // Dot at top
    const dot = document.createElement('div');
    dot.className = 'cm-dot';
    const size = count > 1 ? 18 : 10;
    dot.style.cssText = `width:${{size}}px; height:${{size}}px; background:${{color}}; --cm-color:${{color}};`;
    if (count > 1) dot.textContent = count;
    marker.appendChild(dot);

    // Hover events
    marker.addEventListener('mouseenter', (e) => showPopup(e, label));
    marker.addEventListener('mousemove',  (e) => showPopup(e, label));
    marker.addEventListener('mouseleave', hidePopup);

    wrapper.appendChild(marker);
  }});
}}

// ── CHART HELPERS ────────────────────────────────────────────────────────────
function buildXaxis() {{
  const vis = getVisibleLabels();
  return {{
    type: 'category',
    categories: vis,
    tickAmount: Math.min(20, vis.length),
    labels: {{
      rotate: -45,
      style: {{ colors: '#64748b', fontFamily: 'Inter', fontSize: '11px' }},
      formatter: val => val ? val.slice(5) : '',
    }},
    axisBorder: {{ color: '#1e1e3a' }},
    axisTicks: {{ color: '#1e1e3a' }},
    tooltip: {{ enabled: false }},
  }};
}}

// (visibleAnnotations removed — HTML overlay markers handle this)

// ── CHART 1: Spend vs Conv. Value (dual Y-axis) ─────────────────────────────
const chart1Cfg = {{
  chart: {{
    type: 'area', height: 320, background: 'transparent',
    toolbar: {{ show: false }},
    zoom: {{ enabled: false }},
    animations: {{ enabled: true, easing: 'easeinout', speed: 500 }},
    dropShadow: {{
      enabled: true, top: 4, left: 0, blur: 12,
      color: ['#e94560', '#06b6d4'], opacity: 0.3,
    }},
    fontFamily: 'Inter, sans-serif',
  }},
  series: [
    {{ name: 'Cost (€)',        data: getVisibleData(COST_DATA) }},
    {{ name: 'Conv. Value (€)', data: getVisibleData(CV_DATA)   }},
  ],
  colors: ['#e94560', '#06b6d4'],
  stroke: {{ curve: 'smooth', width: [2, 2.5] }},
  fill: {{
    type: 'gradient',
    gradient: {{ type: 'vertical', shadeIntensity: 1, opacityFrom: 0.32, opacityTo: 0.02, stops: [0, 100] }},
  }},
  dataLabels: {{ enabled: false }},
  markers: {{ size: 0, hover: {{ size: 5 }} }},
  xaxis: buildXaxis(),
  yaxis: [
    {{
      seriesName: 'Cost (€)',
      labels: {{
        style: {{ colors: '#e94560', fontFamily: 'Inter', fontSize: '11px' }},
        formatter: v => '€' + (v >= 1000 ? (v/1000).toFixed(1)+'k' : v.toFixed(0)),
      }},
      title: {{ text: 'Cost (€)', style: {{ color: '#e94560', fontSize: '10px', fontFamily: 'Inter' }} }},
    }},
    {{
      seriesName: 'Conv. Value (€)',
      opposite: true,
      labels: {{
        style: {{ colors: '#06b6d4', fontFamily: 'Inter', fontSize: '11px' }},
        formatter: v => '€' + (v >= 1000 ? (v/1000).toFixed(1)+'k' : v.toFixed(0)),
      }},
      title: {{ text: 'Conv. Value (€)', style: {{ color: '#06b6d4', fontSize: '10px', fontFamily: 'Inter' }} }},
    }},
  ],
  grid: gridCfg,
  tooltip: {{
    theme: 'dark', shared: true, intersect: false,
    y: {{ formatter: v => v == null ? '—' : '€' + Number(v).toLocaleString('en',{{minimumFractionDigits:2,maximumFractionDigits:2}}) }},
  }},
  legend: {{ show: false }},
  theme: darkTheme,
}};
const chart1 = new ApexCharts(document.getElementById('chart1'), chart1Cfg);
chart1.render();

// ── CHART 2: Conversions & ROAS (dual Y-axis) ───────────────────────────────
const chart2Cfg = {{
  chart: {{
    type: 'area', height: 320, background: 'transparent',
    toolbar: {{ show: false }},
    zoom: {{ enabled: false }},
    animations: {{ enabled: true, easing: 'easeinout', speed: 500 }},
    dropShadow: {{
      enabled: true, top: 4, left: 0, blur: 12,
      color: ['#10b981', '#f59e0b'], opacity: 0.28,
    }},
    fontFamily: 'Inter, sans-serif',
  }},
  series: [
    {{ name: 'Conversions', data: getVisibleData(CONV_DATA) }},
    {{ name: 'ROAS (%)',    data: getVisibleData(ROAS_DATA) }},
  ],
  colors: ['#10b981', '#f59e0b'],
  stroke: {{ curve: 'smooth', width: [2, 2] }},
  fill: {{
    type: 'gradient',
    gradient: {{ type: 'vertical', shadeIntensity: 1, opacityFrom: 0.28, opacityTo: 0.02, stops: [0, 100] }},
  }},
  dataLabels: {{ enabled: false }},
  markers: {{ size: 0, hover: {{ size: 5 }} }},
  xaxis: buildXaxis(),
  yaxis: [
    {{
      seriesName: 'Conversions',
      labels: {{
        style: {{ colors: '#10b981', fontFamily: 'Inter', fontSize: '11px' }},
        formatter: v => v == null ? '—' : v.toFixed(0),
      }},
    }},
    {{
      seriesName: 'ROAS (%)',
      opposite: true,
      labels: {{
        style: {{ colors: '#f59e0b', fontFamily: 'Inter', fontSize: '11px' }},
        formatter: v => v == null ? '—' : v.toFixed(0) + '%',
      }},
    }},
  ],
  grid: gridCfg,
  tooltip: {{
    theme: 'dark', shared: true, intersect: false,
    y: [
      {{ formatter: v => v == null ? '—' : v.toFixed(1) + ' convs' }},
      {{ formatter: v => v == null ? '—' : v.toFixed(1) + '%' }},
    ],
  }},
  legend: {{ show: false }},
  theme: darkTheme,
}};
const chart2 = new ApexCharts(document.getElementById('chart2'), chart2Cfg);
chart2.render();

// ── DRAW CHANGE MARKERS (multiple timing attempts for reliability) ────────────
function drawAllMarkers() {{
  createChangeMarkers('chart1', chart1);
  createChangeMarkers('chart2', chart2);
}}
// Attempt at multiple intervals to ensure charts are fully rendered
setTimeout(drawAllMarkers, 300);
setTimeout(drawAllMarkers, 800);
setTimeout(drawAllMarkers, 1500);
// Also redraw on window resize (chart geometry changes)
window.addEventListener('resize', () => setTimeout(drawAllMarkers, 200));

// ── CAMPAIGN TYPE + DATE RANGE FILTER ─────────────────────────────────────────
function getSeriesData(ctype) {{
  if (ctype === 'all') return {{ cost: COST_DATA, cv: CV_DATA, conv: CONV_DATA, roas: ROAS_DATA }};
  const d = CTYPE_DAILY[ctype] || {{}};
  return {{
    cost: LABELS.map(l => d[l]?.cost ?? 0),
    cv:   LABELS.map(l => d[l]?.cv   ?? 0),
    conv: LABELS.map(l => d[l]?.conv  ?? 0),
    roas: LABELS.map(l => d[l]?.roas  ?? 0),
  }};
}}

function refreshCharts() {{
  const ctype = document.getElementById('ctypeFilter').value;
  const d = getSeriesData(ctype);
  const vis = getVisibleLabels();
  const sliceD = (arr) => arr.slice(rangeStart, rangeEnd + 1);
  chart1.updateOptions({{ xaxis: {{ ...buildXaxis() }} }}, false, false);
  chart1.updateSeries([
    {{ name:'Cost (€)',        data: sliceD(d.cost) }},
    {{ name:'Conv. Value (€)', data: sliceD(d.cv) }},
  ]);
  chart2.updateOptions({{ xaxis: {{ ...buildXaxis() }} }}, false, false);
  chart2.updateSeries([
    {{ name:'Conversions', data: sliceD(d.conv) }},
    {{ name:'ROAS (%)',    data: sliceD(d.roas) }},
  ]);
  // Recreate markers after chart redraws
  setTimeout(() => drawAllMarkers(), 300);
  setTimeout(() => drawAllMarkers(), 800);
  // Update range label
  const lbl = document.getElementById('rangeLbl');
  if (lbl) lbl.textContent = `${{vis[0]}} → ${{vis[vis.length-1]}}  (${{vis.length}} days)`;
}}

document.getElementById('ctypeFilter').addEventListener('change', refreshCharts);

// Date range presets
document.getElementById('rangePicker').addEventListener('change', function() {{
  const val = this.value;
  if (val === 'all') {{ rangeStart = 0; rangeEnd = LABELS.length - 1; }}
  else {{
    const days = parseInt(val, 10);
    rangeStart = Math.max(0, LABELS.length - days);
    rangeEnd = LABELS.length - 1;
  }}
  refreshCharts();
}});

// Custom date inputs
document.getElementById('dateFrom').addEventListener('change', applyCustomRange);
document.getElementById('dateTo').addEventListener('change', applyCustomRange);
function applyCustomRange() {{
  const from = document.getElementById('dateFrom').value;
  const to   = document.getElementById('dateTo').value;
  if (!from && !to) return;
  document.getElementById('rangePicker').value = 'custom';
  let s = 0, e = LABELS.length - 1;
  if (from) {{ const idx = LABELS.indexOf(from); if (idx >= 0) s = idx; }}
  if (to)   {{ const idx = LABELS.indexOf(to);   if (idx >= 0) e = idx; }}
  if (s > e) {{ const tmp = s; s = e; e = tmp; }}
  rangeStart = s; rangeEnd = e;
  refreshCharts();
}}

// ── ANNOTATION TYPE LEGEND (toggles) ─────────────────────────────────────────
(function buildTypeLegend() {{
  const container = document.getElementById('typeLegend');
  const counts = {{}};
  ANNOTATIONS.forEach(a => {{ counts[a.type] = (counts[a.type]||0)+1; }});
  ALL_TYPES.forEach(type => {{
    const color = TYPE_COLORS[type], cnt = counts[type]||0;
    const div = document.createElement('div');
    div.className = 'annot-item';
    div.innerHTML = `<div class="annot-swatch" style="background:${{color}}"></div>${{type}}<span class="annot-count">${{cnt}}</span>`;
    div.addEventListener('click', () => {{
      activeTypes.has(type) ? activeTypes.delete(type) : activeTypes.add(type);
      div.classList.toggle('inactive');
      drawAllMarkers();
    }});
    container.appendChild(div);
  }});
}})();

// ── TOP 10 TABLE ──────────────────────────────────────────────────────────────
(function renderImpactTable() {{
  const tbody = document.getElementById('impactBody');
  TOP10.forEach((row, i) => {{
    const pct = row.impact_pct;
    const cls = pct===null ? 'impact-neu' : pct>=0 ? 'impact-pos' : 'impact-neg';
    const arrow = pct===null ? '' : pct>=0 ? '▲' : '▼';
    const pctTxt = pct===null ? '—' : `${{arrow}} ${{Math.abs(pct).toFixed(1)}}%`;
    const color = TYPE_COLORS[row.type] || '#64748b';
    const fmt = (v,p='€') => v===null ? '—' : p+Number(v).toLocaleString('en',{{minimumFractionDigits:2,maximumFractionDigits:2}});
    const pctColor = pct===null ? 'var(--muted)' : pct>=0 ? 'var(--green)' : 'var(--red)';
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td class="mono" style="color:var(--muted)">${{i+1}}</td>
      <td class="mono" style="color:var(--accent)">${{row.date_str}}</td>
      <td><span class="type-badge" style="background:${{color}}20;color:${{color}};border:1px solid ${{color}}40">${{row.type}}</span></td>
      <td style="color:var(--muted);font-size:.73rem;max-width:140px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${{row.user}}</td>
      <td><span class="impact-pill ${{cls}}">${{pctTxt}}</span></td>
      <td class="mono" style="font-size:.73rem">
        <span style="color:var(--muted)">${{fmt(row.before_cv)}}</span>
        <span style="color:#334155"> → </span>
        <span style="color:${{pctColor}}">${{fmt(row.after_cv)}}</span>
      </td>
      <td class="mono" style="font-size:.73rem">
        <span style="color:var(--muted)">${{fmt(row.before_cost)}}</span>
        <span style="color:#334155"> → </span>
        <span style="color:var(--text)">${{fmt(row.after_cost)}}</span>
      </td>
      <td class="mono" style="font-size:.73rem">
        <span style="color:var(--muted)">${{(row.before_conv??'—').toString()}}</span>
        <span style="color:#334155"> → </span>
        <span style="color:var(--text)">${{(row.after_conv??'—').toString()}}</span>
      </td>
      <td><div class="change-text" title="${{row.changes.replace(/"/g,'&quot;')}}">${{row.changes}}</div></td>
    `;
    tbody.appendChild(tr);
  }});
}})();

// ── CHANGE LOG ────────────────────────────────────────────────────────────────
const typeSelect = document.getElementById('filterType');
ALL_TYPES.forEach(t => {{ const o=document.createElement('option'); o.value=t; o.textContent=t; typeSelect.appendChild(o); }});

const ctypeSelect = document.getElementById('filterCampaignType');
const logCtypes = [...new Set(CHANGELOG.map(r=>r.campaign_type).filter(Boolean))].sort();
logCtypes.forEach(t => {{ const o=document.createElement('option'); o.value=t; o.textContent=t; ctypeSelect.appendChild(o); }});

const userSelect = document.getElementById('filterUser');
ALL_USERS.forEach(u => {{ const o=document.createElement('option'); o.value=u; o.textContent=u; userSelect.appendChild(o); }});

const PAGE_SIZE = 20;
let currentPage = 1;

function getFiltered() {{
  const type   = document.getElementById('filterType').value;
  const ctype  = document.getElementById('filterCampaignType').value;
  const user   = document.getElementById('filterUser').value;
  const search = document.getElementById('filterSearch').value.toLowerCase();
  return CHANGELOG.filter(r =>
    (!type   || r.type === type) &&
    (!ctype  || r.campaign_type === ctype) &&
    (!user   || r.user === user) &&
    (!search || r.changes.toLowerCase().includes(search) ||
                r.campaign.toLowerCase().includes(search) ||
                r.user.toLowerCase().includes(search))
  );
}}

function renderChangelog() {{
  const filtered = getFiltered();
  const total = filtered.length;
  const pages = Math.ceil(total / PAGE_SIZE) || 1;
  if (currentPage > pages) currentPage = 1;
  const slice = filtered.slice((currentPage-1)*PAGE_SIZE, currentPage*PAGE_SIZE);

  document.getElementById('rowCount').textContent = `${{total}} change${{total!==1?'s':''}} found`;
  const tbody = document.getElementById('changelogBody');
  tbody.innerHTML = '';
  slice.forEach(row => {{
    const color = TYPE_COLORS[row.type] || '#64748b';
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td class="mono" style="color:var(--accent);white-space:nowrap">${{row.date}}</td>
      <td><span class="type-badge" style="background:${{color}}20;color:${{color}};border:1px solid ${{color}}40">${{row.type}}</span></td>
      <td style="color:var(--muted);font-size:.73rem;white-space:nowrap">${{row.campaign_type||'—'}}</td>
      <td style="color:var(--muted);font-size:.73rem;white-space:nowrap;max-width:160px;overflow:hidden;text-overflow:ellipsis">${{row.user}}</td>
      <td style="color:var(--muted);font-size:.73rem;max-width:140px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${{row.campaign}}</td>
      <td><div class="change-text" style="max-width:460px" title="${{row.changes.replace(/"/g,'&quot;')}}">${{row.changes}}</div></td>
    `;
    tbody.appendChild(tr);
  }});

  // Pagination
  const pag = document.getElementById('pagination');
  pag.innerHTML = '';
  if (pages <= 1) return;
  const addBtn = (lbl, pg, dis, act) => {{
    const btn = document.createElement('button');
    btn.className = 'page-btn' + (act ? ' active' : '');
    btn.textContent = lbl; btn.disabled = dis;
    btn.addEventListener('click', () => {{ currentPage = pg; renderChangelog(); }});
    pag.appendChild(btn);
  }};
  addBtn('‹', currentPage-1, currentPage===1, false);
  const s = Math.max(1,currentPage-2), e2 = Math.min(pages,currentPage+2);
  if (s>1) {{ addBtn('1',1,false,false); if(s>2) pag.insertAdjacentHTML('beforeend','<span class="page-info">…</span>'); }}
  for (let p=s; p<=e2; p++) addBtn(p,p,false,p===currentPage);
  if (e2<pages) {{ if(e2<pages-1) pag.insertAdjacentHTML('beforeend','<span class="page-info">…</span>'); addBtn(pages,pages,false,false); }}
  addBtn('›', currentPage+1, currentPage===pages, false);
  const info = document.createElement('span');
  info.className='page-info'; info.textContent=`Page ${{currentPage}} of ${{pages}}`;
  pag.appendChild(info);
}}

function resetFilters() {{
  ['filterType','filterCampaignType','filterUser'].forEach(id => document.getElementById(id).value='');
  document.getElementById('filterSearch').value='';
  currentPage=1; renderChangelog();
}}

['filterType','filterCampaignType','filterUser'].forEach(id =>
  document.getElementById(id).addEventListener('change', () => {{ currentPage=1; renderChangelog(); }})
);
document.getElementById('filterSearch').addEventListener('input', () => {{ currentPage=1; renderChangelog(); }});

document.addEventListener('click', e => {{
  if (e.target.classList.contains('change-text')) {{
    const full = e.target.getAttribute('title');
    if (full) alert(full);
  }}
}});

renderChangelog();
</script>
</body>
</html>"""

# ─── 8. Write output ───────────────────────────────────────────────────────────
with open(OUTPUT_PATH, "w", encoding="utf-8") as fh:
    fh.write(html)

size_kb = os.path.getsize(OUTPUT_PATH) / 1024
print(f"\nDashboard → {OUTPUT_PATH} ({size_kb:.1f} KB)")
print("Done. Open in browser to view.")
