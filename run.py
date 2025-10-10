from src.app import app
from src.config.config import Config

if __name__ == '__main__':
    print("=== Outlook Signature Manager ===")
    print("Starting application...")
    
    try:
        Config.validate_config()
        print("✓ Configuration is valid")
        print("✓ Server starting on http://localhost:5000")
        print("Press Ctrl+C to stop the server")
        
        app.run(debug=Config.DEBUG, host='0.0.0.0', port=5000)
        
    except Exception as e:
        print(f"✗ Error: {str(e)}")
        print("\nPlease check your .env file configuration")