# Cleaning Service Quote & Crew Dispatch CLI (Lite)

Zero-dependency **Python 3.9+** CLI calculator for **cleaning companies**, **maid services**, and **home-service dispatchers**. Estimate job pricing by square meters, cleaning tier (`standard`, `deep`, `post_renovation`, `move_in_out`, `office`), bathrooms, windows, and appliances, calculate man-hours, balance crew schedules, and export to **Text**, **JSON**, or **CSV**.

## Features

- **100% Python 3.9+ Standard Library** — zero external packages, instant setup.
- **Multi-tier Quote Engine** — area-based pricing with minimum job floors, bathroom/window/appliance add-ons, urgency multipliers (`normal`, `same_day`, `weekend`), and recurring frequency discounts (`weekly`, `biweekly`, `monthly`).
- **Man-Hour & Crew Sizing** — estimates total labor hours, recommended crew size, and on-site duration.
- **Zone-Aware Crew Dispatch** — balances batch jobs across available crews using LPT (Longest Processing Time) scheduling with zone affinity.
- **Structured Exports** — `--format text`, `--format json`, and `--format csv`.

## Quick Start

```bash
# Calculate a single quote
python cleaning_dispatch.py quote --area 95 --type deep --bathrooms 2 --windows 6 --oven --urgency same_day

# Export quote as JSON
python cleaning_dispatch.py quote --area 120 --type office --frequency weekly --format json

# Run built-in multi-job dispatch demo
python cleaning_dispatch.py demo --crews 2

# Dispatch a batch of jobs from a JSON file to CSV
python cleaning_dispatch.py schedule --input jobs.json --crews 3 --format csv
```

## Running Tests

```bash
python -m unittest discover -s tests -v
```

---

## Need the Pro Version? (Telegram Bot + Web Dispatcher Panel)

Looking for a production-ready **Pro** system for your cleaning or home-service business?
Get the **Pro Telegram Bot + Web Dispatcher Panel** (live client quote intake, instant PDF/invoice generation, crew GPS/status tracking, Google Calendar / CRM sync, and multi-crew dispatch dashboard) here:

- **Order / Details:** [https://funpay.com/users/20096179/](https://funpay.com/users/20096179/)

## License

MIT License — see [LICENSE](LICENSE) for details.
