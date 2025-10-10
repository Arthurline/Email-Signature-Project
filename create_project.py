import requests
import msal
import json
import os
from typing import List, Dict

class OutlookSignatureManager:
    def __init__(self, tenant_id: str, client_id: str, certificate_path: str, certificate_password: str = None):
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.certificate_path = certificate_path
        self.certificate_password = certificate_password
        self.authority = f"https://login.microsoftonline.com/{tenant_id}"
        self.scope = ["https://graph.microsoft.com/.default"]
        
    def get_access_token(self) -> str:
        """Acquire access token using certificate authentication"""
        app = msal.ConfidentialClientApplication(
            self.client_id,
            authority=self.authority,
            client_credential={
                "thumbprint": self._get_certificate_thumbprint(),
                "private_key": open(self.certificate_path).read(),
            },
        )
        
        result = app.acquire_token_for_client(scopes=self.scope)
        
        if "access_token" in result:
            return result["access_token"]
        else:
            raise Exception(f"Token acquisition failed: {result.get('error_description', 'Unknown error')}")
    
    def _get_certificate_thumbprint(self) -> str:
        """Extract thumbprint from certificate (simplified - implement proper extraction)"""
        # In production, use proper certificate parsing library
        return "YOUR_CERTIFICATE_THUMBPRINT"
    
    def get_user_signature(self, user_principal_name: str) -> Dict:
        """Get current signature for a user"""
        access_token = self.get_access_token()
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        url = f"https://graph.microsoft.com/v1.0/users/{user_principal_name}/mailboxSettings"
        
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Failed to get signature: {response.status_code} - {response.text}")
    
    def set_user_signature(self, user_principal_name: str, signature_html: str) -> bool:
        """Set signature for a specific user"""
        access_token = self.get_access_token()
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        url = f"https://graph.microsoft.com/v1.0/users/{user_principal_name}/mailboxSettings"
        
        payload = {
            "signature": {
                "content": signature_html,
                "contentType": "html"
            }
        }
        
        response = requests.patch(url, headers=headers, json=payload)
        
        if response.status_code == 200:
            return True
        else:
            raise Exception(f"Failed to set signature: {response.status_code} - {response.text}")
    
    def set_automatic_reply(self, user_principal_name: str, message: str, start_time: str = None, end_time: str = None) -> bool:
        """Set automatic reply (out of office) message"""
        access_token = self.get_access_token()
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        url = f"https://graph.microsoft.com/v1.0/users/{user_principal_name}/mailboxSettings/automaticRepliesSetting"
        
        payload = {
            "status": "scheduled",
            "externalAudience": "all",
            "internalReplyMessage": message,
            "externalReplyMessage": message
        }
        
        if start_time and end_time:
            payload["scheduledStartDateTime"] = {"dateTime": start_time, "timeZone": "UTC"}
            payload["scheduledEndDateTime"] = {"dateTime": end_time, "timeZone": "UTC"}
        
        response = requests.patch(url, headers=headers, json=payload)
        
        return response.status_code == 200
    
    def get_all_users(self) -> List[Dict]:
        """Get all users in the organization"""
        access_token = self.get_access_token()
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        url = "https://graph.microsoft.com/v1.0/users"
        users = []
        
        while url:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                data = response.json()
                users.extend(data.get("value", []))
                url = data.get("@odata.nextLink")
            else:
                raise Exception(f"Failed to get users: {response.status_code} - {response.text}")
        
        return users
    
    def apply_standard_signature_to_all(self, signature_template: str) -> Dict:
        """Apply standard signature to all users in the organization"""
        users = self.get_all_users()
        results = {
            "success": [],
            "failed": []
        }
        
        for user in users:
            user_principal_name = user.get("userPrincipalName")
            if user_principal_name:
                try:
                    # Personalize signature template
                    personalized_signature = self._personalize_signature(
                        signature_template, 
                        user
                    )
                    
                    self.set_user_signature(user_principal_name, personalized_signature)
                    results["success"].append(user_principal_name)
                    print(f"✓ Signature set for {user_principal_name}")
                    
                except Exception as e:
                    results["failed"].append({
                        "user": user_principal_name,
                        "error": str(e)
                    })
                    print(f"✗ Failed for {user_principal_name}: {str(e)}")
        
        return results
    
    def _personalize_signature(self, template: str, user: Dict) -> str:
        """Personalize signature template with user data"""
        replacements = {
            "{{displayName}}": user.get("displayName", ""),
            "{{jobTitle}}": user.get("jobTitle", ""),
            "{{department}}": user.get("department", ""),
            "{{officeLocation}}": user.get("officeLocation", ""),
            "{{businessPhones}}": ", ".join(user.get("businessPhones", [])),
            "{{mail}}": user.get("mail", ""),
            "{{userPrincipalName}}": user.get("userPrincipalName", "")
        }
        
        personalized = template
        for placeholder, value in replacements.items():
            personalized = personalized.replace(placeholder, value)
        
        return personalized

# Example usage
def main():
    # Configuration
    TENANT_ID = "your-tenant-id"
    CLIENT_ID = "your-client-id"
    CERTIFICATE_PATH = "path/to/your/certificate.pem"
    
    # Initialize the signature manager
    signature_manager = OutlookSignatureManager(
        tenant_id=TENANT_ID,
        client_id=CLIENT_ID,
        certificate_path=CERTIFICATE_PATH
    )
    
    # Define your standard signature template
    STANDARD_SIGNATURE_TEMPLATE = """
    <html>
    <body>
        <div style="font-family: Arial, sans-serif; font-size: 10pt; color: #333;">
            <p><strong>{{displayName}}</strong><br>
            {{jobTitle}} | {{department}}<br>
            {{officeLocation}}</p>
            <p>📞 {{businessPhones}}<br>
            ✉️ {{mail}}</p>
            <p><img src="https://yourcompany.com/logo.png" alt="Company Logo" width="150"></p>
            <p style="font-size: 8pt; color: #666;">
                Confidentiality Notice: This message and any attachments are confidential.
            </p>
        </div>
    </body>
    </html>
    """
    
    try:
        # Apply to all users
        results = signature_manager.apply_standard_signature_to_all(STANDARD_SIGNATURE_TEMPLATE)
        
        print(f"\nResults:")
        print(f"Successful: {len(results['success'])} users")
        print(f"Failed: {len(results['failed'])} users")
        
        if results['failed']:
            print("\nFailed users:")
            for failure in results['failed']:
                print(f"- {failure['user']}: {failure['error']}")
                
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    main()