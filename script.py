import json
import time
import os
import logging
from datetime import datetime
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException,
    ElementClickInterceptedException, StaleElementReferenceException
)
from webdriver_manager.chrome import ChromeDriverManager

# ──────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────
load_dotenv()
EMAIL    = os.getenv("VTU_EMAIL")
PASSWORD = os.getenv("VTU_PASS")

BASE_URL   = "https://vtu.internyet.in/dashboard/student/student-diary"
WAIT_SECS  = 20          # explicit-wait timeout
RETRY_MAX  = 3           # per-entry retry attempts
SAVE_DELAY = 4           # seconds to wait after clicking Save

# ──────────────────────────────────────────────
# LOGGING
# ──────────────────────────────────────────────
log_filename = f"diary_automation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_filename),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# DRIVER SETUP
# ──────────────────────────────────────────────
def setup_driver(headless: bool = False) -> webdriver.Chrome:
    opts = Options()
    opts.add_argument("--start-maximized")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    opts.add_experimental_option("detach", True)
    if headless:
        opts.add_argument("--headless=new")
        opts.add_argument("--window-size=1920,1080")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=opts)
    # Mask navigator.webdriver to avoid bot-detection
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"}
    )
    return driver


# ──────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────
def safe_click(driver: webdriver.Chrome, element, retries: int = 3):
    """Click with JS fallback on interception / stale ref."""
    for attempt in range(retries):
        try:
            element.click()
            return
        except ElementClickInterceptedException:
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", element)
            time.sleep(0.5)
        except StaleElementReferenceException:
            log.warning("Stale element on click – retrying…")
            time.sleep(0.5)
    # Final fallback: JS click
    driver.execute_script("arguments[0].click();", element)


def wait_and_find(wait: WebDriverWait, by: By, value: str):
    return wait.until(EC.presence_of_element_located((by, value)))


def wait_and_click(wait: WebDriverWait, driver: webdriver.Chrome, by: By, value: str):
    el = wait.until(EC.element_to_be_clickable((by, value)))
    safe_click(driver, el)
    return el


def load_entries(filepath: str) -> list:
    if not os.path.exists(filepath):
        log.error(f"Data file not found: '{filepath}'")
        raise FileNotFoundError(f"'{filepath}' does not exist.")
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("diary_data.json must be a JSON array of entry objects.")
    log.info(f"Loaded {len(data)} entries from '{filepath}'.")
    return data


def validate_entry(entry: dict, idx: int) -> bool:
    required = ["date", "summary", "learnings"]
    missing  = [k for k in required if not entry.get(k, "").strip()]
    if missing:
        log.warning(f"Entry #{idx} (date={entry.get('date','?')}) missing fields: {missing}. Skipping.")
        return False
    # Basic date format check
    try:
        datetime.strptime(entry["date"], "%Y-%m-%d")
    except ValueError:
        log.warning(f"Entry #{idx} has invalid date format '{entry['date']}' (expected YYYY-MM-DD). Skipping.")
        return False
    return True


# ──────────────────────────────────────────────
# STEP: LOGIN
# ──────────────────────────────────────────────
def login(driver: webdriver.Chrome, wait: WebDriverWait):
    log.info("Navigating to diary page…")
    driver.get(BASE_URL)
    time.sleep(2)

    if "login" not in driver.current_url.lower() and "signin" not in driver.current_url.lower():
        log.info("Already logged in – skipping login step.")
        return

    if not EMAIL or not PASSWORD:
        raise EnvironmentError("VTU_EMAIL or VTU_PASS not set in .env file.")

    log.info("Login page detected. Entering credentials…")
    email_field = wait.until(EC.presence_of_element_located(
        (By.XPATH, "//input[@type='email' or contains(@placeholder,'Email') or contains(@name,'email')]")
    ))
    email_field.clear()
    email_field.send_keys(EMAIL)

    pass_field = driver.find_element(By.XPATH, "//input[@type='password']")
    pass_field.clear()
    pass_field.send_keys(PASSWORD)

    wait_and_click(wait, driver, By.XPATH, "//button[@type='submit']")
    time.sleep(3)

    if "login" in driver.current_url.lower():
        raise RuntimeError("Login failed – please check your credentials in the .env file.")
    log.info("Login successful.")


# ──────────────────────────────────────────────
# STEP: INTERNSHIP DROPDOWN
# ──────────────────────────────────────────────
def select_internship(driver: webdriver.Chrome, wait: WebDriverWait):
    log.info("Selecting internship from dropdown…")
    dropdown = wait.until(EC.element_to_be_clickable((By.ID, "internship_id")))
    safe_click(driver, dropdown)
    time.sleep(1)

    # Try multiple selectors for dropdown options
    option_xpaths = [
        "//div[@role='option']",
        "//*[contains(@class,'select-item')]",
        "//*[contains(@class,'option')]",
        "//li[@role='option']",
    ]
    for xpath in option_xpaths:
        try:
            option = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
            safe_click(driver, option)
            log.info("Internship selected.")
            return
        except TimeoutException:
            continue

    raise RuntimeError("Could not find any internship option in the dropdown.")


# ──────────────────────────────────────────────
# STEP: DATE SELECTION
# ──────────────────────────────────────────────
def set_date(driver: webdriver.Chrome, date_str: str):
    log.info(f"Setting date: {date_str}")
    script = """
    const selectors = [
        'input[type="date"]',
        'input[name="date"]',
        'input[placeholder*="date"]',
        'input[placeholder*="Date"]'
    ];
    let dateInput = null;
    for (const sel of selectors) {
        dateInput = document.querySelector(sel);
        if (dateInput) break;
    }
    if (dateInput) {
        const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
            window.HTMLInputElement.prototype, 'value'
        ).set;
        nativeInputValueSetter.call(dateInput, arguments[0]);
        dateInput.dispatchEvent(new Event('input',  { bubbles: true }));
        dateInput.dispatchEvent(new Event('change', { bubbles: true }));
        return true;
    }
    return false;
    """
    result = driver.execute_script(script, date_str)
    if not result:
        log.warning("Date input not found via JS injection – trying direct Selenium fill.")
        try:
            date_input = driver.find_element(By.CSS_SELECTOR, 'input[type="date"]')
            date_input.clear()
            date_input.send_keys(date_str)
        except NoSuchElementException:
            log.error("Could not locate date input field.")


# ──────────────────────────────────────────────
# STEP: FILL FORM FIELDS
# ──────────────────────────────────────────────
def fill_form(driver: webdriver.Chrome, wait: WebDriverWait, entry: dict):
    log.info("Waiting for form to load…")
    wait.until(EC.presence_of_element_located((By.TAG_NAME, "textarea")))
    time.sleep(1)  # allow React to settle

    summary   = entry.get("summary", "")
    ref_link  = entry.get("reference_link", "")
    learnings = entry.get("learnings", "")
    hours     = str(entry.get("hours", ""))

    # ── Textareas via React's native setter (works with controlled components) ──
    script = """
    const data = arguments[0];
    const nativeSetter = Object.getOwnPropertyDescriptor(
        window.HTMLTextAreaElement.prototype, 'value'
    ).set;
    const nativeInputSetter = Object.getOwnPropertyDescriptor(
        window.HTMLInputElement.prototype, 'value'
    ).set;
    const fire = (el) => {
        el.dispatchEvent(new Event('input',  { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
        el.dispatchEvent(new Event('blur',   { bubbles: true }));
    };

    const textareas = document.querySelectorAll('textarea');
    if (textareas[0]) { nativeSetter.call(textareas[0], data.summary);   fire(textareas[0]); }
    if (textareas[1]) { nativeSetter.call(textareas[1], data.ref_link);   fire(textareas[1]); }
    if (textareas[2]) { nativeSetter.call(textareas[2], data.learnings);  fire(textareas[2]); }

    // Hours input: prefer number type or placeholder hint
    const inputs = Array.from(document.querySelectorAll('input'));
    const hoursInput = inputs.find(el =>
        el.type === 'number' ||
        (el.placeholder && (el.placeholder.includes('6.5') || el.placeholder.toLowerCase().includes('hour')))
    );
    if (hoursInput && data.hours) {
        nativeInputSetter.call(hoursInput, data.hours);
        fire(hoursInput);
    }
    """
    payload = {
        "summary":   summary,
        "ref_link":  ref_link,
        "learnings": learnings,
        "hours":     hours,
    }
    driver.execute_script(script, payload)
    log.info("Form fields injected.")


# ──────────────────────────────────────────────
# STEP: SKILLS
# ──────────────────────────────────────────────
def fill_skills(driver: webdriver.Chrome, skills: list):
    if not skills:
        return
    log.info(f"Adding skills: {skills}")

    # Try multiple possible react-select input IDs/classes
    skill_input = None
    selectors = [
        (By.ID, "react-select-2-input"),
        (By.ID, "react-select-3-input"),
        (By.CSS_SELECTOR, "input[id*='react-select']"),
        (By.XPATH, "//input[contains(@id,'react-select')]"),
    ]
    for by, value in selectors:
        try:
            skill_input = driver.find_element(by, value)
            break
        except NoSuchElementException:
            continue

    if not skill_input:
        log.warning("Skill input field not found. Skipping skills.")
        return

    for skill in skills:
        try:
            skill_input.click()
            skill_input.send_keys(skill)
            time.sleep(0.5)
            # Try pressing Enter or clicking the dropdown option
            try:
                option = driver.find_element(
                    By.XPATH,
                    f"//div[contains(@class,'option') and contains(text(),'{skill}')]"
                )
                safe_click(driver, option)
            except NoSuchElementException:
                skill_input.send_keys(Keys.ENTER)
            time.sleep(0.3)
        except Exception as e:
            log.warning(f"Could not add skill '{skill}': {e}")


# ──────────────────────────────────────────────
# STEP: SAVE
# ──────────────────────────────────────────────
def save_entry(driver: webdriver.Chrome, wait: WebDriverWait, date_str: str) -> bool:
    log.info(f"Saving entry for {date_str}…")
    save_xpaths = [
        "//button[normalize-space()='Save']",
        "//button[contains(text(),'Save')]",
        "//button[@type='submit' and contains(text(),'Save')]",
    ]
    for xpath in save_xpaths:
        try:
            btn = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
            safe_click(driver, btn)
            time.sleep(SAVE_DELAY)
            log.info(f"✅ Entry saved for {date_str}.")
            return True
        except TimeoutException:
            continue
    log.error(f"Save button not found for {date_str}.")
    return False


# ──────────────────────────────────────────────
# CORE: PROCESS ONE ENTRY (WITH RETRIES)
# ──────────────────────────────────────────────
def process_entry(driver: webdriver.Chrome, wait: WebDriverWait, entry: dict) -> bool:
    date_str = entry["date"]
    for attempt in range(1, RETRY_MAX + 1):
        try:
            log.info(f"\n{'='*50}")
            log.info(f"Entry: {date_str}  (attempt {attempt}/{RETRY_MAX})")
            driver.get(BASE_URL)
            time.sleep(2)

            select_internship(driver, wait)
            time.sleep(0.5)

            set_date(driver, date_str)
            time.sleep(0.5)

            wait_and_click(wait, driver, By.XPATH, "//button[contains(text(),'Continue')]")
            time.sleep(1)

            fill_form(driver, wait, entry)
            fill_skills(driver, entry.get("skills", []))

            if save_entry(driver, wait, date_str):
                return True

        except Exception as e:
            log.error(f"Attempt {attempt} failed for {date_str}: {e}")
            if attempt < RETRY_MAX:
                log.info("Retrying…")
                time.sleep(2)

    log.error(f"❌ All {RETRY_MAX} attempts failed for {date_str}.")
    return False


# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────
def automate_diary(data_file: str = "diary_data.json", headless: bool = False):
    entries = load_entries(data_file)

    # Validate all entries upfront and filter bad ones
    valid_entries = [e for i, e in enumerate(entries) if validate_entry(e, i + 1)]
    if not valid_entries:
        log.error("No valid entries to process. Exiting.")
        return

    driver = setup_driver(headless=headless)
    wait   = WebDriverWait(driver, WAIT_SECS, poll_frequency=0.5,
                           ignored_exceptions=[StaleElementReferenceException])

    results = {"success": [], "failed": []}

    try:
        login(driver, wait)

        for entry in valid_entries:
            ok = process_entry(driver, wait, entry)
            (results["success"] if ok else results["failed"]).append(entry["date"])

    except Exception as e:
        log.critical(f"Fatal error: {e}", exc_info=True)
    finally:
        # ── Summary ──
        log.info("\n" + "="*50)
        log.info(f"DONE. Success: {len(results['success'])}  |  Failed: {len(results['failed'])}")
        if results["success"]:
            log.info(f"  ✅ Saved:  {', '.join(results['success'])}")
        if results["failed"]:
            log.info(f"  ❌ Failed: {', '.join(results['failed'])}")
        log.info(f"Full log saved to: {log_filename}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="VTU Internship Diary Automation")
    parser.add_argument("--data",     default="diary_data.json", help="Path to diary JSON file")
    parser.add_argument("--headless", action="store_true",        help="Run browser in headless mode")
    args = parser.parse_args()
    automate_diary(data_file=args.data, headless=args.headless)