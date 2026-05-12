import os
import time
import threading
import logging
from database import get_all_email_accounts, update_last_sync_time
from gmail_service import fetch_and_process_emails
from retrieval import build_collection
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

_scheduler_thread = None
_stop_event = threading.Event()
_is_syncing = False
_last_sync_log = "No sync performed yet."

def run_sync_job():
    global _is_syncing, _last_sync_log
    
    if _is_syncing:
        logger.info("Sync already in progress. Skipping.")
        return False
        
    _is_syncing = True
    logger.info("Starting email sync job.")
    
    try:
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            _last_sync_log = "Sync failed: GOOGLE_API_KEY not set."
            logger.error(_last_sync_log)
            return False

        # Get accounts
        accounts = get_all_email_accounts()
        active_accounts = [a for a in accounts if a['is_active']]
        
        if not active_accounts:
            _last_sync_log = "No active email accounts to sync."
            logger.info(_last_sync_log)
            return True

        collection = build_collection()
        success_count = 0
        error_logs = []
        
        for account in active_accounts:
            logger.info(f"Syncing account: {account['email']}")
            success, error_msg = fetch_and_process_emails(account, collection, api_key)
            if success:
                success_count += 1
            else:
                error_logs.append(f"[{account['email']}] Error: {error_msg}")
                
        _last_sync_log = f"Sync completed successfully for {success_count}/{len(active_accounts)} accounts."
        if error_logs:
            _last_sync_log += "\n\nErrors:\n" + "\n".join(error_logs)
            
        logger.info(_last_sync_log)
        return True
        
    except Exception as e:
        _last_sync_log = f"Sync encountered an error: {str(e)}"
        logger.error(_last_sync_log)
        return False
    finally:
        _is_syncing = False

def _sync_loop():
    logger.info("Scheduler thread started.")
    while not _stop_event.is_set():
        # Run the sync
        run_sync_job()
        
        # Sleep for 1 hour (3600 seconds)
        # We break it down to check the stop event more frequently
        for _ in range(3600):
            if _stop_event.is_set():
                break
            time.sleep(1)
            
    logger.info("Scheduler thread stopped.")

def start_scheduler():
    global _scheduler_thread
    if _scheduler_thread is None or not _scheduler_thread.is_alive():
        _stop_event.clear()
        _scheduler_thread = threading.Thread(target=_sync_loop, daemon=True)
        _scheduler_thread.start()
        logger.info("Email sync scheduler initialized.")

def stop_scheduler():
    if _scheduler_thread and _scheduler_thread.is_alive():
        _stop_event.set()
        _scheduler_thread.join(timeout=5)
        logger.info("Email sync scheduler stopped.")

def get_sync_status():
    global _is_syncing, _last_sync_log
    return {
        "is_syncing": _is_syncing,
        "last_log": _last_sync_log
    }
