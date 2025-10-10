from flask import Flask, render_template, request, jsonify
import logging
from src.signature_manager import OutlookSignatureManager, SIGNATURE_TEMPLATES
from src.config.config import Config

logging.basicConfig(level=Config.LOG_LEVEL)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = Config.SECRET_KEY

@app.route('/')
def dashboard():
    return render_template('dashboard.html')

@app.route('/api/health')
def health_check():
    try:
        signature_manager = OutlookSignatureManager()
        token = signature_manager.get_access_token()
        return jsonify({"status": "healthy", "message": "Service is running"})
    except Exception as e:
        return jsonify({"status": "unhealthy", "message": str(e)}), 500

@app.route('/api/users')
def get_users():
    try:
        signature_manager = OutlookSignatureManager()
        users = signature_manager.get_all_users()
        user_list = []
        for user in users:
            user_list.append({
                "displayName": user.get("displayName", ""),
                "userPrincipalName": user.get("userPrincipalName", ""),
                "mail": user.get("mail", ""),
                "jobTitle": user.get("jobTitle", ""),
                "department": user.get("department", "")
            })
        return jsonify({"users": user_list})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/signature', methods=['POST'])
def set_user_signature():
    try:
        data = request.json
        user_principal_name = data.get('userPrincipalName')
        signature_html = data.get('signature')
        
        if not user_principal_name:
            return jsonify({"error": "userPrincipalName is required"}), 400
        
        signature_manager = OutlookSignatureManager()
        signature_manager.set_user_signature(user_principal_name, signature_html)
        return jsonify({"success": True, "message": "Signature updated"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=Config.DEBUG, host='0.0.0.0', port=5000)