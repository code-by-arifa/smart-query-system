from dotenv import load_dotenv
from app.gmail_service import gmail_client

load_dotenv()

service = gmail_client()
profile = service.users().getProfile(userId="me").execute()
print("This system is reading from and sending as:", profile["emailAddress"])