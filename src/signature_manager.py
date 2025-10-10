import requests
import msal
import logging
from typing import List, Dict, Optional
from src.config.config import Config

logging.basicConfig(level=Config.LOG_LEVEL)
logger = logging.getLogger(__name__)

class OutlookSignatureManager:
    def __init__(self):
        self.tenant_id = Config.TENANT_ID
        self.client_id = Config.CLIENT_ID
        self.certificate_path = Config.CERTIFICATE_PATH
        self.authority = f"https://login.microsoftonline.com/{self.tenant_id}"
        self.scope = ["https://graph.microsoft.com/.default"]
        Config.validate_config()
        
    def get_access_token(self) -> str:
        try:
            app = msal.ConfidentialClientApplication(
                self.client_id,
                authority=self.authority,
                client_credential={"private_key": open(self.certificate_path).read()},
            )
            result = app.acquire_token_for_client(scopes=self.scope)
            if "access_token" in result:
                return result["access_token"]
            else:
                raise Exception(f"Token acquisition failed: {result.get('error_description')}")
        except Exception as e:
            raise Exception(f"Error acquiring token: {str(e)}")
    
    def get_all_users(self) -> List[Dict]:
        try:
            access_token = self.get_access_token()
            headers = {"Authorization": f"Bearer {access_token}"}
            url = "https://graph.microsoft.com/v1.0/users?$select=displayName,userPrincipalName,mail,jobTitle,department"
            users = []
            
            while url:
                response = requests.get(url, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    users.extend(data.get("value", []))
                    url = data.get("@odata.nextLink")
                else:
                    raise Exception(f"Failed to get users: {response.status_code}")
            return users
        except Exception as e:
            raise Exception(f"Error getting users: {str(e)}")
    
    def set_user_signature(self, user_principal_name: str, signature_html: str) -> bool:
        try:
            access_token = self.get_access_token()
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            url = f"https://graph.microsoft.com/v1.0/users/{user_principal_name}/mailboxSettings"
            payload = {"signature": {"content": signature_html, "contentType": "html"}}
            response = requests.patch(url, headers=headers, json=payload)
            return response.status_code == 200
        except Exception as e:
            raise Exception(f"Error setting signature: {str(e)}")

SIGNATURE_TEMPLATES = {
    "standard": """
    <html><body>
    <div style="font-family: Arial, sans-serif; font-size: 10pt;">
        <p><strong>{{displayName}}</strong><br>
        {{jobTitle}} | {{department}}</p>
        <p>📞 {{businessPhones}}<br>✉️ {{mail}}</p>
    </div>
    </body></html>
    """
}