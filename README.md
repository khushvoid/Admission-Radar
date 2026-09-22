# Admission Radar — 2027/2028

A deployable, mobile-friendly admissions dashboard for Science students, with Bengaluru prioritized.

## What it does
- Filters by year, stream, city and status.
- Uses official institution/exam links.
- Shows a conservative OPEN/WATCH state.
- Includes a GitHub Actions monitor that checks configured official pages every 30 minutes.
- Keeps a visible verification date.

## Deploy
1. Create a GitHub repository and upload this folder.
2. Enable **Settings → Pages → Deploy from branch → main → / (root)**.
3. The dashboard is then live on GitHub Pages.
4. Keep Actions enabled so the monitor can update `data/colleges.json`.

## Important
This is intentionally conservative. A keyword match is not proof that every programme at an institution is open. For critical deadlines, click the official application link and confirm the exact programme and cycle before paying/submitting.

The current snapshot was researched on 22 Sep 2026. 2028 dates are not invented; they should be added only when official institutions publish them.
