# Iroas — your AI personal trainer on Telegram

Iroas is a personal trainer you text. It learns your history and goals, builds
you a program, puts it straight into the **Hevy** workout app, checks in every
evening to ask how training went, reads what you actually lifted in Hevy, and
raises your targets when you've earned it. It runs on your own Windows PC and
uses your own Claude subscription.

**What it does** (you choose which of these to switch on during setup, and can
change your mind any time):

| Feature | What happens |
|---|---|
| **Daily review** | Each evening Iroas messages you: "How did training go?" You reply, it reads the session from Hevy, logs the day, and calls out PRs and stalls. |
| **Hevy progression** | When you hit the top of a rep range, Iroas raises the target (more reps, or more weight) directly in your Hevy routine, so next session is already set. |
| **Weekly weigh-in** | Once a week it asks for your scale numbers (weight, body fat %, muscle %) and tracks the trend. |
| **Nudges** | A heads-up when something looks off, like lots of rest days or a lift stuck for 3 sessions. |

---

## What you need before you start

1. **A Windows 10 or 11 PC** that's on (and awake) in the evenings.
2. **A Claude subscription** (Pro or Max) from [claude.ai](https://claude.ai).
   Iroas uses this subscription and never an API key, so there are no per-message charges.
3. **Hevy Pro** on your phone ([hevy.com](https://www.hevy.com)). Iroas needs
   Pro to read and update your workouts.
4. **Telegram** on your phone ([telegram.org](https://telegram.org)). Install it
   from the App Store / Play Store and sign up with your phone number.

Nothing else needs to be installed. Setup installs the rest for you.

---

## Install (about 15 minutes)

### Step 1 — Download Iroas

1. On this page, click the green **Code** button (top right), then **Download ZIP**.
2. Open your **Downloads** folder, right-click **Iroas-main.zip** → **Extract All…**
3. Change the location to your **Documents** folder and click **Extract**.
   You now have a folder `Documents\Iroas-main`. That's Iroas's home, so don't
   delete, move or rename it.

### Step 2 — Run setup

1. Open the Iroas folder and double-click **`setup.bat`**.
2. If a blue box says **"Windows protected your PC"**, click **More info** →
   **Run anyway**. (Windows says this about any downloaded script.)
3. A black window opens and walks you through 5 steps. Just answer what it asks:

   | Step | What happens |
   |---|---|
   | 1. Programs | Installs Python and Git if missing. Click **Yes** if Windows asks for permission. If it says to close and run setup.bat again, do that. |
   | 2. Packages | Installs Iroas's parts. Takes a few minutes; just wait. |
   | 3. Claude login | Press Enter → your browser opens → sign in to Claude → **Authorize**. Back in the black window, a long code starting with `sk-ant-oat` appears. Select it with the mouse, press **Ctrl+C**, then click in the window and press **Ctrl+V** (or right-click) where it asks, and press Enter. |
   | 4. Telegram bot | You create your own private bot. On your phone in Telegram: search **@BotFather** (blue check mark) → **Start** → send `/newbot` → give it a name (e.g. `Iroas`) → then a username that ends in `bot` (e.g. `dave_iroas_bot`). BotFather replies with a token like `123456789:AAH…`. The easiest way to get it onto the PC is to open [web.telegram.org](https://web.telegram.org) on the PC, log in, open the BotFather chat, and copy it from there. Paste it into the setup window. |
   | 5. Hevy | Your browser opens Hevy's developer settings page. Log in, generate an API key, copy it, and paste it into the setup window. |

4. Setup finishes with a health check and shows a line like:

   ```
   /start 482913
   ```

   Write down that number. It's your pairing code.

### Step 3 — Start Iroas

1. In the Iroas folder, double-click **`start_iroas.bat`**.
2. A window titled **"Iroas"** opens. **Leave it open.** Minimizing it is fine.
   If you close it, Iroas stops.

### Step 4 — Say hello

1. In Telegram, search for your bot's username (the one you made in step 2) and open it.
2. Send `/start` followed by your pairing code, e.g. `/start 482913`.
3. Iroas introduces itself and starts getting to know you. It asks about your
   training, any injuries, your goals, your schedule and equipment, and which
   features you want. Then it designs a program with you and puts it in Hevy.
   Take your time; you can finish this over a few conversations.

The pairing code locks the bot to your Telegram account, so nobody else can use it.

---

## Using Iroas

Just text it like you'd text a coach:

- "Just finished legs, felt strong, left knee a bit achy on lunges"
- "I only have 30 minutes today, what should I do?"
- "Why are we doing 3 sets instead of 5?"
- "Turn off the weekly weigh-in"  ·  "Check in at 8pm instead"
- "I'm travelling next week with only a hotel gym"

Log your workouts in **Hevy** as normal. Iroas reads them from there.

**Commands** (type them in the chat):

| Command | Does |
|---|---|
| `/settings` | Shows which features are on and your check-in time |
| `/checkin` | Runs tonight's check-in right now |
| `/new` | Starts a fresh conversation (Iroas keeps all its notes about you) |
| `/help` | Reminder of the above |

**Changing settings:** the easiest way is to ask Iroas. Or open `settings.json`
in the Iroas folder with Notepad, change `true`/`false` or the time, and save.
Changes apply within a minute.

---

## Keeping it running

- Iroas only works while the **Iroas window is open** and the PC is **on and awake**.
- If the PC is off at check-in time, Iroas sends the check-in as soon as you
  start it again that evening. Missed days get caught up in the next conversation.
- Stop Windows from sleeping too early: **Settings → System → Power** → set
  "put my device to sleep" to **Never** (when plugged in), or at least later than
  your check-in time.

### Optional: start Iroas automatically when you log in

Instead of double-clicking `start_iroas.bat` every time, you can have Claude
Code set Iroas up to start by itself:

1. Press the **Windows key**, type **PowerShell**, and open it.
2. Paste this line and press Enter to install Claude Code (you only do this once):
   ```
   irm https://claude.ai/install.ps1 | iex
   ```
3. Close PowerShell, open it again, then go to the Iroas folder and start Claude Code:
   ```
   cd "$HOME\Documents\Iroas-main"
   claude
   ```
   Sign in with your Claude account if asked.
4. Type this and press Enter:
   > Set up Iroas to start automatically when I log in to Windows, following the instructions in CLAUDE.md. Then check that it's running.

Claude Code creates a Windows scheduled task for it. After that you don't need
`start_iroas.bat` any more. Don't run both; Iroas will refuse to start twice anyway.

---

## If something goes wrong

**First, double-click `doctor.bat`.** It checks Claude, Telegram and Hevy, and
tells you what's broken.

| Problem | Fix |
|---|---|
| Iroas says its **Claude login expired** | Double-click **`refresh_claude_login.bat`**, sign in again, paste the new token. Iroas picks it up right away; no restart needed. (The token lasts about a year.) |
| Iroas doesn't reply at all | Is the Iroas window open? If not, double-click `start_iroas.bat`. Is the PC awake and online? |
| "Iroas is already running in another window" | It's already on (perhaps via the auto-start task). Nothing to do. |
| Hevy errors / "401" | Hevy Pro may have lapsed, or the key was regenerated. Run `setup.bat` again; it re-checks the key and asks for a new one if needed. |
| "Usage limit" message | Your Claude plan's limit was reached. It resets after a few hours. |
| Anything else | Look in the `logs` folder: `iroas.log` has the details. Send it to whoever set this up for you. |

Running **`setup.bat` again is always safe.** It keeps everything that works
and only asks about what's missing or broken.

---

## Updating to a new version

1. Close the Iroas window. Download the ZIP again and extract it to your
   **Documents** folder exactly like step 1, choosing **Replace the files in the
   destination** when Windows asks.
2. Double-click `setup.bat` (to install any new parts), then `start_iroas.bat`.

Your notes, settings and keys are **not** in the ZIP, so they're never overwritten.

---

## Your data

- Everything Iroas knows about you lives in the **`data`** folder on your PC:
  `profile.md`, `routine.md`, `log.md`, `measurements.md`. They're plain text,
  so you can open them in Notepad. Back up that folder if you like.
- Your keys are in the `.env` file. Don't share it.
- Your messages go through Telegram, and Iroas's thinking happens with Claude
  (Anthropic) under your subscription. Workout data comes from Hevy.

---

## For the technically curious

| File | What it is |
|---|---|
| `bot.py` | The Telegram bot: pairing, messages, the evening check-in loop |
| `agent.py` | Talks to Claude via the Claude Agent SDK; builds the prompt from the persona + your files |
| `persona/IROAS.md` | Iroas's instructions and personality. Edit to taste |
| `skills/personal-trainer/` | The training knowledge base Iroas reads when designing programs |
| `hevy.py` | Hevy API client + command-line tool (`python hevy.py --help`) |
| `settings.py` / `scheduler.py` | Feature switches, and when to check in |
| `doctor.py`, `setup.ps1` | Health check and installer |

Run the tests with `.venv\Scripts\python -m pip install -r requirements-dev.txt`
then `.venv\Scripts\python -m pytest -q`.

Iroas started life as one agent inside a larger personal-assistant project and
was split out to stand on its own. Licensed MIT; see [LICENSE](LICENSE).
