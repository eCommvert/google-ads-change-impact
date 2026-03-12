---
name: google-ads-change-impact
description: Analyzes Google Ads change history against performance metrics to identify which changes had the biggest impact on revenue, conversions, and other KPIs
version: 1.2.0
triggers:
  - "analyze google ads changes"
  - "change history impact"
  - "which changes affected performance"
  - "google ads timeline"
design: Revolut-Fintech (from /web-design skill)
---

# Google Ads Change Impact Analyzer

Creates an interactive dashboard showing Google Ads change history overlaid with performance metrics to identify which changes drove the biggest impact.

## What It Does

1. **Accepts two CSVs:**
   - Change History export from Google Ads
   - Performance metrics (date, spend, conversions, conv. value, conv. rate, etc.)

2. **Analyzes:**
   - Correlates changes with performance shifts
   - Identifies statistically significant impacts
   - Categorizes changes by type (bid, budget, campaign status, creative, targeting)

3. **Generates:**
   - Interactive HTML dashboard with:
     - Dual-axis timeline charts (Cost vs Conv. Value, Conversions vs ROAS)
     - HTML overlay change markers with hover popups (before/after values)
     - Color-coded change annotations by type (Bid, Conversion, Access, Script, Report, Other)
     - Impact scores for each change (7-day before vs after)
     - Top 10 changes ranked by impact
     - Full change log with filters (type, campaign type, user, search)
     - Date range picker (30/60/90/180 days, All, Custom)
     - Campaign type filter

## Usage

```
/google-ads-change-impact
```

Then upload:
1. Change history CSV from Google Ads
2. Performance metrics CSV with columns: date, spend, conversions, conversion_value, conversion_rate

## Example Use Cases

- **Client asks:** "Why did performance drop last month?"
- **Account audit:** Identify which historical changes to replicate or avoid
- **Reporting:** Show data-driven story of account evolution
- **Optimization:** Find which bid/budget changes had best ROI

## Output

Self-contained HTML file with interactive ApexCharts dashboard:
- Dual-axis area charts with gradient fills and glow effects
- HTML overlay change markers with hover popups
- Filterable by change type, campaign type, date range
- Paginated full change log with search

## Requirements

- Google Ads change history CSV
- Performance data CSV with date + metrics
- Minimum 30 days of data recommended
- Works best with 90+ days for trend analysis

## Design System

Uses the **Revolut-Fintech** template from `/web-design` with **ApexCharts** for charts:
- Dark mode: `#080812` background with radial ambient glows
- Neon accents: cyan `#06b6d4` (primary) + purple `#8b5cf6` (secondary)
- Typography: Inter (UI) + JetBrains Mono (data/numbers)
- KPI cards with per-metric accent colors and hover glow
- Glassmorphism header with gradient border line
- Data-dense tables with tight spacing
- No agency branding — clean, client-presentable output
- **Charts**: ApexCharts (`cdn.jsdelivr.net/npm/apexcharts@3.54.0`) — gradient area fills + drop-shadow glow for Evil Charts aesthetic

## Tips

**Getting Change History:**
1. Google Ads → Tools & Settings → Change History
2. Filter by date range (90-180 days recommended)
3. Download as CSV

**Getting Performance Metrics:**
1. Reports → Predefined Reports → Campaigns
2. Add columns: Date, Spend, Conversions, Conv. Value, Conv. Rate
3. Date range: Match change history
4. Download as CSV

**Best Practices:**
- Use consistent date ranges for both CSVs
- Include at least 2 weeks before first change for baseline
- Focus on significant changes (ignore minor bid adjustments)
- Consider external factors (seasonality, promotions) in interpretation
