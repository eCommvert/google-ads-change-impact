# Claude Code Prompt for Google Ads Change Impact Analysis

Copy this prompt and paste it into Claude Code after uploading your two CSVs.

---

## The Prompt

```
I have two CSVs from Google Ads:

1. Change History CSV with columns:
   - Change date and time
   - Change (description)
   - User

2. Performance CSV with columns:
   - date
   - spend
   - conversions
   - conversion_value
   - conversion_rate

Please create an interactive HTML dashboard that:

1. Shows a timeline chart with:
   - Conversion value (line chart, left Y-axis)
   - Conversions (line chart, right Y-axis)
   - Conversion rate % (line chart, hidden Y-axis for scale)
   - X-axis: dates

2. Annotates major changes on the timeline:
   - Vertical lines on dates where changes occurred
   - Color-coded by change type:
     * Blue: Budget changes
     * Purple: Bid strategy changes
     * Red: Status changes (paused/enabled)
     * Green: Creative/ad changes
     * Orange: Targeting changes
     * Cyan: Campaign creation
     * Pink: Ad group changes
     * Gray: Other

3. Calculates impact scores for each change:
   - Compare 7 days before vs 7 days after each change
   - Calculate % change in conversions, conversion value, and conversion rate
   - Weighted impact score:
     * 50% weight: conversion value change
     * 30% weight: conversions change
     * 20% weight: conversion rate change

4. Shows a table below the chart with:
   - Top 20 changes ranked by absolute impact score
   - Columns: Date | Category | Change Description | Impact Score | Conv Δ% | Value Δ% | Rate Δ%
   - Color-code positive (green) and negative (red) changes

5. Dashboard design (Revolut-Fintech from /web-design):
   - Dark mode (#080812 background, #0f0f1e cards)
   - Inter font (UI) + JetBrains Mono (data values)
   - Neon accents: cyan #06b6d4 primary, purple #8b5cf6 secondary
   - KPI cards with per-metric glow on hover
   - Glassmorphism header with gradient accent border
   - Use ApexCharts for the timeline (gradient area fills, glow effects)
   - Responsive layout
   - No agency branding
   - Summary metrics at the top:
     * Total changes analyzed
     * Positive impact changes (score > 5)
     * Negative impact changes (score < -5)
     * Date range

6. Make it self-contained:
   - Single HTML file
   - Include all JS/CSS via CDN
   - No external dependencies
   - Works offline once loaded

Output the dashboard as a single HTML file named: google_ads_change_impact_dashboard.html
```

---

## Usage

1. **Open Claude Code**
   ```bash
   claude
   ```

2. **Upload your CSVs**
   - Drag and drop both files into the chat
   - Or use the attachment button

3. **Paste the prompt above**
   - Copy the entire prompt
   - Paste into Claude Code
   - Hit Enter

4. **Wait for Claude to generate**
   - It will create the HTML file
   - Should take 30-60 seconds

5. **Open the dashboard**
   - Find `google_ads_change_impact_dashboard.html` in your current directory
   - Double-click to open in browser
   - Or: `open google_ads_change_impact_dashboard.html` (Mac)

---

## Customization Prompts

After you have the dashboard, you can ask Claude to modify it:

### Change the lookback window:
```
Can you change the impact analysis to use 14 days before/after each change instead of 7?
```

### Show more changes on the timeline:
```
Please show the top 20 changes as annotations on the timeline instead of top 10.
```

### Add spend to the chart:
```
Add spend as a fourth line on the timeline chart with its own Y-axis.
```

### Export summary:
```
Add a "Download Summary" button that exports the top 20 changes as a CSV file.
```

### Filter by category:
```
Add dropdown filters at the top to show only specific change categories (Budget, Bid, Creative, etc.)
```

### Statistical significance:
```
Add p-value calculations to determine if the performance changes are statistically significant.
```

---

## Example Conversation

**You:**
> [Upload change_history.csv and performance.csv]
>
> [Paste the main prompt]

**Claude:**
> I'll create an interactive dashboard analyzing your Google Ads changes. Let me process both CSVs...
>
> [Generates the dashboard]
>
> I've created google_ads_change_impact_dashboard.html with:
> - Timeline showing conversions, conversion value, and conversion rate
> - 47 changes analyzed
> - Top 10 changes annotated on the timeline
> - Impact scores calculated for each change
> - Top 20 changes displayed in the table
>
> Key findings:
> - Budget increase on 2026-02-15: +45% conversion value (strongest positive impact)
> - Bid strategy change on 2026-02-22: -20% conversions (strongest negative impact)
> - 12 changes had positive impact (score > 5)
> - 8 changes had negative impact (score < -5)

**You:**
> Can you also add a section showing which category of changes (Budget, Bid, Creative, etc.) had the best average impact?

**Claude:**
> [Updates the dashboard with category analysis]

---

## Tips for Better Results

### Data Preparation
- ✅ Download 90-180 days of data for meaningful trends
- ✅ Ensure date formats are consistent (YYYY-MM-DD)
- ✅ Remove header rows if Google Ads adds them
- ✅ Check that conversion_rate is in decimal format (0.05 not 5%)

### Asking Follow-ups
- Be specific: "Add X to the chart" vs "Make it better"
- Ask for one change at a time if making multiple modifications
- Request examples: "Show me an example of what that would look like"

### Debugging
If Claude says it can't read the CSV:
```
Here's what the first few rows of my change_history.csv look like:
[Paste 3-5 rows]

Can you try again?
```

---

## Advanced: Combine with Google Ads MCP

If you have the Google Ads MCP server set up, you can skip manual CSV downloads:

```
Using the Google Ads MCP server:

1. Fetch change history for account [ACCOUNT_ID] for the past 90 days
2. Fetch campaign performance metrics for the same period
3. Create the change impact dashboard as described above

Use these GAQL queries:
- Change history: [provide GAQL for change history]
- Performance: [provide GAQL for campaign metrics]
```

(Note: This requires Google Ads MCP server setup)

---

## What You'll Get

A beautiful, interactive dashboard showing:

### Visual Timeline
- See performance trends over time
- Spot correlations between changes and metric shifts
- Color-coded annotations for quick scanning

### Data-Backed Insights
- Quantified impact scores (not just gut feeling)
- Percentage changes for all key metrics
- Ranked list of what moved the needle

### Shareable Results
- Single HTML file you can email to clients
- Screenshots for reports/presentations
- Evidence-based recommendations

---

**Want the Python version?** See `README.md` in this folder
