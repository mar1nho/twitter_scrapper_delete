import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import ElementClickInterceptedException, TimeoutException, StaleElementReferenceException
from webdriver_manager.chrome import ChromeDriverManager

# Prompt user for credentials at runtime
USERNAME = input("Enter your X (Twitter) username: ")
PASSWORD = input("Enter your password: ")
TARGET_PROFILE = f"https://x.com/{USERNAME}/with_replies"

# Configs
MAX_WAIT_TIME = 10
MIN_WAIT_TIME = 0.2
TWEET_PROCESS_BATCH = 5


def connect():
    options = webdriver.ChromeOptions()
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--log-level=3')

    # Mobile emulation speeds up loading
    mobile_emulation = {
        "userAgent": "Mozilla/5.0 (Linux; Android 10; SM-G975F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Mobile Safari/537.36"
    }
    options.add_experimental_option("mobileEmulation", mobile_emulation)

    # Disable image loading and notifications
    prefs = {
        "profile.default_content_setting_values.notifications": 2,
        "profile.managed_default_content_settings.images": 2,
    }
    options.add_experimental_option("prefs", prefs)

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(30)
    return driver


def login(driver, username, password):
    driver.get("https://x.com/login")
    wait = WebDriverWait(driver, MAX_WAIT_TIME)

    try:
        user_input = wait.until(EC.element_to_be_clickable((By.NAME, "text")))
        user_input.send_keys(username)
        user_input.send_keys(Keys.RETURN)
        time.sleep(1)

        password_input = wait.until(EC.element_to_be_clickable((By.NAME, "password")))
        password_input.send_keys(password)
        password_input.send_keys(Keys.RETURN)
        time.sleep(5)

    except Exception as e:
        print(f"Login error: {e}")
        driver.quit()
        exit()


def is_retweet(tweet):
    try:
        indicators = [
            ".//span[contains(text(), 'You reposted')]",
            "[data-testid='repostedIcon']"
        ]
        for indicator in indicators:
            elements = tweet.find_elements(By.XPATH, indicator) if indicator.startswith('.') else tweet.find_elements(By.CSS_SELECTOR, indicator)
            if elements:
                return True
        return False
    except Exception:
        return False


def safe_click(driver, element):
    try:
        driver.execute_script("arguments[0].click();", element)
        return True
    except Exception:
        try:
            element.click()
            return True
        except Exception:
            return False


def handle_tweet(driver, tweet, wait, is_rt):
    try:
        if is_rt:
            try:
                rt_button = tweet.find_element(By.CSS_SELECTOR, "[data-testid='unretweet'], [data-testid='retweet']")
                safe_click(driver, rt_button)
                time.sleep(MIN_WAIT_TIME)

                confirm_button = wait.until(EC.element_to_be_clickable((By.XPATH,
                    "//span[contains(text(), 'Undo repost')] | //span[contains(text(), 'Undo retweet')] | //div[@data-testid='unretweetConfirm']")))
                safe_click(driver, confirm_button)
                time.sleep(MIN_WAIT_TIME)
                return True
            except Exception:
                pass
        else:
            try:
                more_button = tweet.find_element(By.CSS_SELECTOR, "[aria-label='More']")
                safe_click(driver, more_button)
                time.sleep(MIN_WAIT_TIME)

                delete_button = wait.until(EC.element_to_be_clickable((By.XPATH,
                    "//span[text()='Delete'] | //span[contains(text(), 'Delete')]")))
                safe_click(driver, delete_button)
                time.sleep(MIN_WAIT_TIME)

                confirm_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='confirmationSheetConfirm']")))
                safe_click(driver, confirm_button)
                time.sleep(MIN_WAIT_TIME)
                return True
            except Exception:
                pass

        try:
            driver.find_element(By.CSS_SELECTOR, "body").send_keys(Keys.ESCAPE)
        except Exception:
            pass
        return False
    except Exception:
        return False


def delete_tweets(driver, profile_url):
    wait = WebDriverWait(driver, MAX_WAIT_TIME)
    driver.get(profile_url)
    time.sleep(2)

    deleted_count = 0
    retweet_count = 0
    total_processed = 0
    failed_attempts = 0
    max_failed_attempts = 10
    scroll_count = 0
    reload_interval = 30
    start_time = time.time()

    while failed_attempts < max_failed_attempts:
        tweets = driver.find_elements(By.CSS_SELECTOR, "[data-testid='tweet']")

        if not tweets:
            driver.execute_script("window.scrollBy(0, window.innerHeight * 2);")
            time.sleep(1)
            scroll_count += 1
            failed_attempts += 1

            if scroll_count % 5 == 0:
                driver.refresh()
                time.sleep(10)
            continue

        failed_attempts = 0
        batch_size = min(TWEET_PROCESS_BATCH, len(tweets))
        processed_this_cycle = 0

        for i in range(batch_size):
            try:
                tweet = tweets[i]

                try:
                    author_element = tweet.find_element(By.XPATH, ".//div[@data-testid='User-Name']//span[contains(text(), '@')]")
                    if author_element.text.strip().lower() != f"@{USERNAME.lower()}":
                        continue
                except Exception:
                    continue

                is_rt = is_retweet(tweet)
                result = handle_tweet(driver, tweet, wait, is_rt)

                if result:
                    if is_rt:
                        retweet_count += 1
                    else:
                        deleted_count += 1
                    total_processed += 1
                    processed_this_cycle += 1

                    if total_processed % 5 == 0:
                        elapsed = time.time() - start_time
                        rate = total_processed / elapsed if elapsed > 0 else 0
                        print(f"{deleted_count} tweets deleted, {retweet_count} reposts undone. Rate: {rate:.2f} tweets/sec")

            except (IndexError, StaleElementReferenceException):
                continue
            except Exception as e:
                print(f"Error processing tweet: {str(e)[:100]}...")

        if processed_this_cycle == 0:
            driver.execute_script("window.scrollBy(0, window.innerHeight * 1.5);")
            time.sleep(1)
        else:
            time.sleep(MIN_WAIT_TIME)

        if total_processed > 0 and total_processed % reload_interval == 0:
            driver.refresh()
            time.sleep(3)

    elapsed_time = time.time() - start_time
    rate = total_processed / elapsed_time if elapsed_time > 0 else 0

    print("\n=== SUMMARY ===")
    print(f"Tweets deleted: {deleted_count}")
    print(f"Reposts undone: {retweet_count}")
    print(f"Execution time: {elapsed_time:.2f} seconds")
    print(f"Average speed: {rate:.2f} tweets/sec")
    print("================")


if __name__ == "__main__":
    driver = connect()
    login(driver, USERNAME, PASSWORD)
    delete_tweets(driver, TARGET_PROFILE)
    driver.quit()
    print("Browser closed.")
