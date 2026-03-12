# Google Ads Change Impact Dashboard

**Analyze which Google Ads changes had the biggest impact on your performance.**

Stop spending hours trying to correlate change history with performance drops. This tool does it in minutes.

---

## What It Does

Creates an interactive dashboard showing:
- **Dual-axis timeline charts** — Cost vs Conv. Value, Conversions vs ROAS
- **Change markers on charts** — vertical lines + dots with hover popups showing before/after values
- **Impact scores** for each change (7-day before vs after comparison)
- **Top 10 changes** ranked by revenue impact
- **Full change log** with type, campaign type, user filters + search
- **Date range picker** — 30/60/90/180 days, All, or custom range
- **Campaign type filter** — slice data by Search, Shopping, Performance Max, etc.

![Dashboard Preview](https://via.placeholder.com/1200x600/1E293B/3B82F6?text=Dashboard+Preview)
*Example: Timeline showing budget increase on Feb 15th correlating with +45% conversion value spike*

---

## Quick Start

### 1. Download Your Data from Google Ads

**Change History:**
1. Google Ads → Tools & Settings → Change History
2. Set date range (90-180 days recommended)
3. Click Download → CSV

**Performance Metrics:**
1. Google Ads → Reports → Predefined Reports → Campaigns
2. Date range: Match your change history range
3. Add columns: `Date`, `Spend`, `Conversions`, `Conv. value`, `Conv. rate`
4. Download as CSV

### 2. Run the Dashboard Generator

```bash
# Install dependencies (one-time)
pip install pandas

# Generate dashboard
python generate_dashboard.py metrics.csv change_history.csv
```

### 3. Open the Dashboard

The script creates `change_impact_dashboard.html` (or specify a custom name as 3rd argument).

Open it in your browser — no server needed, works offline once loaded.

---

## CSV Format Requirements

### Change History CSV
Must include these columns:
- `Change date and time` - When the change happened
- `Change` - Description of what changed
- `User` - Who made the change (optional)

### Performance CSV
Must include these columns:
- `date` - Date (YYYY-MM-DD format)
- `spend` - Daily ad spend
- `conversions` - Number of conversions
- `conversion_value` - Total conversion value
- `conversion_rate` - Conversion rate (as decimal, e.g., 0.05 for 5%)

**Example:**
```csv
date,spend,conversions,conversion_value,conversion_rate
2026-02-01,1500.00,25,5000.00,0.042
2026-02-02,1600.00,28,5600.00,0.045
```

---

## How Impact Scores Work

For each change, the tool:
1. **Looks 7 days before** the change (baseline performance)
2. **Looks 7 days after** the change (new performance)
3. **Calculates percent change** in conversions, conversion value, and conversion rate
4. **Computes weighted impact score:**
   - 50% weight on conversion value change
   - 30% weight on conversions change
   - 20% weight on conversion rate change

**Example:**
- Change: Budget increased from €50 to €100 on Feb 15th
- Before: €3,000 conv. value/day
- After: €4,500 conv. value/day
- Impact Score: +50 (strong positive impact)

---

## Change Categories

The dashboard automatically categorizes changes:

| Category | Color | Examples |
|----------|-------|----------|
| **Bid Strategy** | Amber | Bid strategy, target ROAS/CPA, budget, max CPC |
| **Conversion** | Purple | Conversion actions, tracking, attribution |
| **Access/Users** | Cyan | User permissions, invitations, access grants |
| **Script/Rule** | Green | Automated rules, scripts, negative keywords |
| **Report** | Gray | Report creation, scheduling, format changes |
| **Other** | Red | Everything else |

---

## Use Cases

### 1. Client Asks: "Why Did Performance Drop?"
Instead of spending hours in Excel, run this tool and say:
> "The bid strategy change on Feb 22nd correlated with a 20% drop in conversions. Let's test reverting it."

### 2. Account Audit
Identify which historical changes to replicate or avoid:
> "Budget increases drove +30% revenue last quarter. Let's do more of that."

### 3. Performance Review
Build a data-driven story for client reports:
> "Here's exactly what we changed and the impact it had on your business."

### 4. Optimization Insights
Find patterns in what works:
> "Every time we added negative keywords, conversion rate improved. Let's make that a weekly task."

---

## Tips for Best Results

### Data Quality
- ✅ **Use 90-180 days of data** for meaningful trends
- ✅ **Include 2 weeks before first change** for baseline
- ✅ **Match date ranges** between change history and performance CSVs
- ✅ **Filter out minor changes** (e.g., +€1 budget adjustments)

### Interpretation
- 🧠 **Correlation ≠ Causation** - Consider external factors (seasonality, promotions, market changes)
- 🧠 **Statistical significance** - Small accounts may show noise, not true impact
- 🧠 **Multiple changes** - If several changes happen the same day, impact scores combine
- 🧠 **Lag effects** - Some changes (like new campaigns) take >7 days to show full impact

### Advanced Usage
- **Filter by user** - See impact of changes by team member
- **Filter by category** - Isolate bid vs budget vs creative changes
- **Export insights** - Screenshot the dashboard for client reports
- **Time-based analysis** - Run monthly to track change effectiveness over time

---

## Troubleshooting

**"KeyError: 'Change date and time'"**
- Your change history CSV is missing required columns
- Re-download from Google Ads using instructions above

**"No data in chart"**
- Check that your CSV date formats match (YYYY-MM-DD)
- Ensure date ranges overlap between both CSVs

**"Impact scores are all near zero"**
- Your account may have stable performance (good!)
- Try a longer date range to capture more volatile periods
- Check if changes are too minor to measure

**"Dashboard shows too many annotations"**
- Use the change type toggles to show/hide specific categories
- Use the date range picker to narrow the view

---

## What's Next?

Future improvements:
- [ ] Statistical significance testing (p-values)
- [ ] Multi-account comparison
- [ ] Direct Google Ads API integration (no manual CSV download)
- [ ] Exportable PDF reports
- [ ] Slack/email alerts when high-impact changes detected

---

## About

Created by **Denis Capko** ([@deniscapko](https://linkedin.com/in/deniscapko))
Part of the "AI for PPC Managers" series

### Want More?
- 📺 [Watch the video tutorial](https://linkedin.com/in/deniscapko)
- 🧠 [Learn vibe coding for PPC](https://linkedin.com/in/deniscapko)
- 💬 [Get help with your account](https://linkedin.com/in/deniscapko)

---

## License

MIT - Use freely, share widely, attribute nicely.

---

**Questions?** Open an issue or DM me on LinkedIn.

**Found this useful?** Share it with your PPC friends!
