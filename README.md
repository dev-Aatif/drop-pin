# Drop-Pin 📌

A fully automated Pinterest posting bot powered by **Buffer** and **Gemini AI**.

## How It Works

1. **Upload images** to board-specific folders via the web dashboard
2. **Gemini AI** generates viral, SEO-optimized titles and descriptions
3. **Buffer** posts them to your Pinterest account on a randomized schedule
4. **Smart Jitter** ensures posts look human (20 posts/day with ±30min randomization)

## Stack

- **Backend:** Flask (Python)
- **Posting:** Buffer API (official Pinterest partner)
- **AI Content:** Google Gemini 2.0 Flash
- **Hosting:** PythonAnywhere
- **Scheduler:** Cron-Job.org → PythonAnywhere

## Setup

### 1. Environment Variables (`.env`)

```env
BUFFER_ACCESS_TOKEN=1/your_buffer_token
BUFFER_PROFILE_ID=your_pinterest_profile_id
BASE_URL=https://your-username.pythonanywhere.com
GEMINI_API_KEY=your_google_ai_studio_key
CRON_SECRET=your_random_secret_string
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Folder Structure

```
data/
├── pins/           # Board folders with images to post
│   ├── Nature/
│   ├── Architecture/
│   └── Aesthetic/
├── done/           # Successfully posted images
├── recent.json     # Activity log
└── titles.txt      # Fallback title phrases
```

### 4. Run Locally

```bash
python app.py
```

### 5. Cron Job (PythonAnywhere)

Set up a cron job on [cron-job.org](https://cron-job.org) to ping:
```
https://your-username.pythonanywhere.com/api/test_bot?token=YOUR_CRON_SECRET
```
Every **15 minutes**. The bot manages its own internal timer for randomized posting.

## Dashboard

Access at `https://your-username.pythonanywhere.com/`

- **Queue:** See how many images are waiting per board
- **Add:** Upload images and add title phrases
- **Recent:** View last 10 post results
- **Settings:** Clear completed uploads

## License

MIT
