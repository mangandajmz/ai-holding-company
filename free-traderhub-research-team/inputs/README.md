# inputs/

This folder holds data files the research team reads at run time.

## Google Search Console Export

### How to export

1. Open [Google Search Console](https://search.google.com/search-console).
2. Select your property (freetraderhub.com).
3. Click **Performance** → **Search results**.
4. Set your desired date range (last 28 days is recommended for weekly runs).
5. Click **Export** (top right) → **Download CSV**.
6. Rename the downloaded file to exactly `gsc_export.csv`.
7. Drop it into this `inputs/` folder.

### When to do this

Do this every **Friday** before the weekly run so the Growth Strategy Analyst
has fresh data for the coming week's plan.

### What happens if the file is missing

The crew will continue without GSC data. The Growth Strategy Analyst will note
that the file is absent and will base the weekly strategy on Reddit and market
research data instead. You will see instructions in `03_weekly_strategy.md`
reminding you to add the file next time.

---

*This folder is in `.gitignore`. Your GSC data will never be committed to git.*
