# Drop-Pin (Pinterest Automation Bot)

An automated Pinterest bot that posts one image per hour from folder-based queues, featuring a sleek, mobile-friendly dashboard.

## Overview

This bot uses a FIFO (First-In, First-Out) queue system. You place images inside folders named after your Pinterest Boards in `data/pins/`. The bot will wake up every hour, pick the absolute oldest image, attach a randomized title, upload it to Pinterest, and move it to `data/done/`.

You can monitor the queue, add new images, and view recent activity via the built-in mobile-first dashboard.

---

## 1. Getting Your Pinterest API Keys

To post automatically, you need a Pinterest Developer App.

1. Go to [Pinterest Developers](https://developers.pinterest.com/) and log in.
2. Click **Create App** and fill in the basic details.
3. Once created, go to the **Credentials** section of your app.
4. Generate an **Access Token** with the following scopes:
   - `boards:read`
   - `pins:read`
   - `pins:write`
5. Create a file named `.env` in this directory and add your token, as well as a secret string to protect your bot's trigger endpoint:
   ```env
   PINTEREST_ACCESS_TOKEN=your_access_token_here
   CRON_SECRET=my_super_secret_password
   ```

_(Note: The folder names in `data/pins/` MUST exactly match the names of your existing Pinterest boards. The bot will automatically find the corresponding Board ID.)_

---

## 2. Deployment: PythonAnywhere + Cron-Job.org (100% Free)

Since you want this fully automated without providing a credit card, you can use a combination of two free tools that only require an email.

### Step A: Host the Dashboard on PythonAnywhere
1. Sign up for a free account at [PythonAnywhere](https://www.pythonanywhere.com/).
2. Go to the **Files** tab and upload your `drop-pin` project files.
3. Open a **Bash Console** and install the requirements: `pip install --user -r requirements.txt`.
4. Go to the **Web** tab, add a new web app, choose **Flask**, and point it to your `app.py` file.
5. Create your `.env` file via their file manager to include your API keys.
6. Your dashboard is now live at `https://your-username.pythonanywhere.com`!

### Step B: Automate the 1-Hour Timer with Cron-Job.org
PythonAnywhere's free tier does not allow internal background timers, so we use an external service to "wake it up" and trigger the post.
1. Sign up for free at [Cron-Job.org](https://cron-job.org/).
2. Create a new cron job.
3. Set the URL to: `https://your-username.pythonanywhere.com/api/test_bot?token=YOUR_CRON_SECRET`
   *(Replace `YOUR_CRON_SECRET` with whatever you put in your `.env` file).*
4. Set the schedule to run **Every 1 hour**.
5. Save it! The cron job will now automatically ping your app every hour to trigger the next Pinterest upload!

---

## 3. Running Locally (Development)

**Disclaimer**: Do not run intensive build commands using the Gemini Agent. Please run these locally in your terminal.

### Setup Environment

```bash
# 1. Create a virtual environment
python3 -m venv venv

# 2. Activate the virtual environment
source venv/bin/activate  # On Windows use: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt
```

### Start the Bot & Dashboard

```bash
python app.py
```

The dashboard will be available at `http://localhost:5000`. Open it on your phone or browser to start managing your queue!
