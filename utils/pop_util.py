import os
import ssl
import poplib
from email import parser
from email.header import decode_header
from typing import Optional, Dict
from datetime import datetime
from loguru import logger
from better_proxy import Proxy

from models import OperationResult

os.environ['SSLKEYLOGFILE'] = ''


class PopClient:
    def __init__(
            self,
            host: str,
            email: str,
            password: str,
            *,
            port: int = 995,
            proxy: Optional[Proxy] = None,
            timeout: int = 30
    ):
        self.host = host
        self.email = email
        self.password = password
        self.port = port
        self.proxy = proxy
        self.timeout = timeout
        self._server = None

    def _decode_header(self, header):
        """Decode email header."""
        decoded_header = decode_header(header)
        header_parts = []
        for content, charset in decoded_header:
            if isinstance(content, bytes):
                try:
                    content = content.decode(charset or 'utf-8')
                except:
                    content = content.decode('utf-8', 'ignore')
            header_parts.append(str(content))
        return ' '.join(header_parts)

    def _parse_email(self, raw_email: bytes) -> Dict:
        """Parse raw email content into structured format."""
        email_parser = parser.BytesParser()
        email_message = email_parser.parsebytes(raw_email)

        # Get subject
        subject = self._decode_header(email_message.get('Subject', ''))

        # Get sender
        from_header = email_message.get('From', '')
        sender = self._decode_header(from_header)

        # Get date
        date_str = email_message.get('Date', '')
        try:
            date = datetime.strptime(date_str, '%a, %d %b %Y %H:%M:%S %z')
        except:
            date = datetime.now()

        # Get content
        content = ""
        if email_message.is_multipart():
            for part in email_message.walk():
                if part.get_content_type() == "text/plain":
                    try:
                        content = part.get_payload(decode=True).decode()
                        break
                    except:
                        continue
        else:
            try:
                content = email_message.get_payload(decode=True).decode()
            except:
                content = email_message.get_payload()

        return {
            "subject": subject,
            "from": sender,
            "date": date,
            "text": content
        }

    def connect(self):
        """Connect to POP3 server."""
        try:
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE

            self._server = poplib.POP3_SSL(
                host=self.host,
                port=self.port,
                timeout=self.timeout,
                context=context
            )
            self._server.user(self.email)
            self._server.pass_(self.password)
            return True
        except Exception as e:
            logger.error(f"Failed to connect to POP3 server: {str(e)}")
            return False

    def disconnect(self):
        """Disconnect from POP3 server."""
        if self._server:
            try:
                self._server.quit()
            except:
                pass
            self._server = None

    def get_latest_email(self) -> OperationResult:
        """Get the latest email from the mailbox."""
        try:
            if not self.connect():
                return {
                    "status": False,
                    "identifier": self.email,
                    "data": "Failed to connect to POP3 server"
                }

            # Get number of emails
            num_messages = len(self._server.list()[1])
            if num_messages == 0:
                return {
                    "status": False,
                    "identifier": self.email,
                    "data": "No emails found"
                }

            # Get the latest email
            raw_email = b'\n'.join(self._server.retr(num_messages)[1])
            email_data = self._parse_email(raw_email)

            return {
                "status": True,
                "identifier": self.email,
                "data": email_data
            }

        except Exception as error:
            return {
                "status": False,
                "identifier": self.email,
                "data": f"Failed to get latest email: {str(error)}"
            }
        finally:
            self.disconnect()