# 📓 Daily Diary Automation

Automates filling the [VTU Internship Diary](https://vtu.internyet.in) using Selenium. Reads entries from a JSON file and submits them one by one.

---

## Prerequisites

- [Python 3.8+](https://www.python.org/downloads/)
- [Google Chrome](https://www.google.com/chrome/)

---

## Setup & Installation

**1. Install dependencies**

```bash
pip install selenium webdriver-manager python-dotenv
```

**2. Configure your credentials (not needed now)**

Create a `.env` file in the project root:

```env
VTU_EMAIL=your@email.com
VTU_PASS=yourpassword
```

**3. Fill in your diary entries**

Edit `diary_data.json` with your internship details using the format below:

```json
[
  {
    "date": "2026-02-03",
    "summary": "Worked on REST API integration and tested endpoints using Postman.",
    "reference_link": "https://docs.example.com/api",
    "learnings": "Understood how to handle authentication headers and parse JSON responses.",
    "hours": "6.5",
    "skills": ["Python", "REST API", "Postman"]
  },
  {
    "date": "2026-02-04",
    "summary": "Set up CI/CD pipeline using GitHub Actions.",
    "reference_link": "https://docs.github.com/actions",
    "learnings": "Learned how to write workflow YAML files and trigger automated deployments.",
    "hours": "7",
    "skills": ["GitHub Actions", "DevOps", "YAML"]
  }
]
```

> **Note:** `date` must be in `YYYY-MM-DD` format. `reference_link` and `skills` are optional.

---

## Running the Script

```bash
python script.py
```

---

## How It Works

1. Browser window opens and logs in automatically using your `.env` credentials
2. For each diary entry in `diary_data.json`, the script:
   - Navigates to the diary page
   - Selects the internship from the dropdown
   - Picks the correct date from the calendar
   - Fills in summary, reference link, learnings, and hours
   - Adds skills
   - Clicks **Save**
3. A timestamped log file is saved in the project folder after each run
4. Press `Ctrl+C` in the terminal at any time to stop execution

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `diary_data.json not found` | Make sure the file exists in the same folder as the script |
| Login fails | Double-check your `.env` credentials |
| Entry skipped with warning | Check that `date`, `summary`, and `learnings` fields are not empty |
| Chrome version mismatch | Run `pip install --upgrade webdriver-manager` |

---

## Project Structure

```
.
├── automate_diary.py     # Main automation script
├── diary_data.json       # Your diary entries
├── .env                  # Credentials (never commit this!)
└── *.log                 # Auto-generated run logs
```

---
