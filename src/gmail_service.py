import os
import imaplib
import email
from email.header import decode_header
import datetime
import tempfile
import logging

from src.document_processor import extract_text_from_pdf, extract_text_from_docx, extract_text_from_image
from src.agent_workflow import agentic_matching_workflow
from src.retrieval import build_collection, index_tasks
from src.database import get_all_tasks, update_last_sync_time

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_text_from_email(msg):
    text_content = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))
            if content_type == "text/plain" and "attachment" not in content_disposition:
                try:
                    text_content += part.get_payload(decode=True).decode()
                except:
                    pass
    else:
        content_type = msg.get_content_type()
        if content_type == "text/plain":
            try:
                text_content = msg.get_payload(decode=True).decode()
            except:
                pass
    return text_content

def process_attachments(msg):
    attachment_text = ""
    if not msg.is_multipart():
        return attachment_text

    for part in msg.walk():
        if part.get_content_maintype() == 'multipart':
            continue
        if part.get('Content-Disposition') is None:
            continue

        file_name = part.get_filename()
        if bool(file_name):
            # Decode filename
            file_name, encoding = decode_header(file_name)[0]
            if isinstance(file_name, bytes):
                file_name = file_name.decode(encoding if encoding else 'utf-8')
            
            # Save to temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file_name)[1]) as temp_file:
                temp_file.write(part.get_payload(decode=True))
                temp_file_path = temp_file.name

            try:
                ext = temp_file_path.split('.')[-1].lower()
                logger.info(f"Extracting text from attachment: {file_name} ({ext})")
                if ext == 'pdf':
                    # Document processor functions usually take a file-like object with a name attribute, or streamlit UploadedFile.
                    # Since we are passing a path, we might need to modify or just open it.
                    with open(temp_file_path, "rb") as f:
                        attachment_text += f"\n--- Attachment: {file_name} ---\n"
                        attachment_text += extract_text_from_pdf(f)
                elif ext == 'docx':
                    with open(temp_file_path, "rb") as f:
                        attachment_text += f"\n--- Attachment: {file_name} ---\n"
                        attachment_text += extract_text_from_docx(f)
                elif ext in ['png', 'jpg', 'jpeg']:
                    from PIL import Image
                    img = Image.open(temp_file_path)
                    attachment_text += f"\n--- Attachment: {file_name} ---\n"
                    # We might need to mock a file for extract_text_from_image, it takes a file-like.
                    with open(temp_file_path, "rb") as f:
                        attachment_text += extract_text_from_image(f)
            except Exception as e:
                logger.error(f"Error processing attachment {file_name}: {e}")
            finally:
                os.remove(temp_file_path)

    return attachment_text

def fetch_and_process_emails(account, collection, api_key):
    email_address = account['email']
    app_password = account['app_password']
    last_sync_time = account.get('last_sync_time')

    try:
        # Connect to Gmail
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(email_address, app_password)
        mail.select("inbox")

        # Create search query
        # Fetch UNSEEN emails. We also exclude promotions via X-GM-RAW.
        # Alternatively, if we just sync last hour, we use SINCE.
        # It's better to fetch UNSEEN, then mark them as seen.
        
        # Format date for IMAP
        # search_criteria = '(UNSEEN X-GM-RAW "-category:promotions")'
        # Sometimes X-GM-RAW requires specific syntax. Let's use UNSEEN and exclude promotions
        status, messages = mail.uid('search', None, 'UNSEEN', 'X-GM-RAW', '"-category:promotions"')
        
        if status != 'OK':
            error_msg = f"Failed to search emails for {email_address}"
            logger.error(error_msg)
            return False, error_msg

        email_ids = messages[0].split()
        logger.info(f"Found {len(email_ids)} new emails for {email_address}")

        processed_count = 0
        for e_id in email_ids:
            status, msg_data = mail.uid('fetch', e_id, '(RFC822)')
            if status == 'OK':
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])
                        
                        subject, encoding = decode_header(msg["Subject"])[0]
                        if isinstance(subject, bytes):
                            subject = subject.decode(encoding if encoding else "utf-8")
                            
                        logger.info(f"Processing email: {subject}")
                        
                        body_text = get_text_from_email(msg)
                        attachment_text = process_attachments(msg)
                        
                        full_text = f"Subject: {subject}\n\n{body_text}\n\n{attachment_text}"
                        
                        # Process with AI
                        if full_text.strip():
                            upload_date = datetime.datetime.now().strftime("%Y-%m-%d")
                            logger.info("Sending to agentic workflow...")
                            result = agentic_matching_workflow(
                                api_key=api_key,
                                db_collection=collection,
                                raw_text=full_text,
                                upload_date=upload_date,
                                top_k=5,
                                use_reranker=True
                            )
                            logger.info(f"Workflow result: {result.get('status')}")
                        
                        processed_count += 1
                        
                        # Note: By default, fetching with (RFC822) marks the email as seen.
                        # If we used (BODY.PEEK[]), it wouldn't. We want it marked as seen.

        update_last_sync_time(account['id'])
        mail.logout()
        return True, ""

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error syncing account {email_address}: {error_msg}")
        return False, error_msg
