#!/usr/bin/env python3
"""
Simple script to test if the Gemini API key from .env file is working.
"""

import os
import sys
from pathlib import Path

# Try to load .env file
def load_env_file(env_path):
    """Load environment variables from .env file"""
    if not os.path.exists(env_path):
        print(f"❌ .env file not found at: {env_path}")
        return False
    
    try:
        # Try using python-dotenv if available
        try:
            from dotenv import load_dotenv
            load_dotenv(env_path)
            print(f"✓ Loaded .env file using python-dotenv")
            return True
        except ImportError:
            # Fallback: manually parse .env file
            print("⚠ python-dotenv not available, parsing .env manually...")
            with open(env_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        os.environ[key] = value
            print(f"✓ Loaded .env file manually")
            return True
    except Exception as e:
        print(f"❌ Error loading .env file: {e}")
        return False

def test_gemini_api():
    """Test the Gemini API key with a simple request"""
    # Get the project root directory
    project_root = Path(__file__).parent
    env_path = project_root / '.env'
    
    print("=" * 60)
    print("Testing Gemini API Key")
    print("=" * 60)
    print()
    
    # Load .env file
    if not load_env_file(env_path):
        return False
    
    # Get API key
    api_key = os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY')
    
    if not api_key:
        print("❌ GEMINI_API_KEY or GOOGLE_API_KEY not found in environment")
        print("   Please check your .env file contains one of these keys")
        return False
    
    # Mask the API key for display (show first 10 and last 4 chars)
    masked_key = f"{api_key[:10]}...{api_key[-4:]}" if len(api_key) > 14 else "***"
    print(f"✓ Found API key: {masked_key}")
    print()
    
    # Test the API
    print("Testing API connection...")
    try:
        from google import genai
        from google.genai import types
        
        # Initialize client and request config
        client = genai.Client(api_key=api_key)
        model_name = os.environ.get("GEMINI_TEST_MODEL", "gemini-3-pro-preview")
        prompt = (
            "Say 'Hello, Gemini 3 Pro test successful!' in exactly those words. "
            "Then give me a unique 10-word micro joke."
        )
        generation_config = types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_level="low")
        )
        
        print(f"  Target model : {model_name}")
        print(f"  Test calls   : 10 (low thinking level)")
        
        successes = 0
        for attempt in range(1, 11):
            print(f"  ▶️  Call {attempt}/10 ...", end="", flush=True)
            response = client.models.generate_content(
                model=model_name,
                contents=[
                    types.Content(
                        role="user",
                        parts=[types.Part(text=prompt)],
                    )
                ],
                config=generation_config,
            )
            result_text = response.text.strip()
            usage = getattr(response, "usage_metadata", None)
            billable = getattr(usage, "billable_token_count", None) if usage else None
            successes += 1
            print(" success!")
            print(f"    📝 Response : {result_text}")
            if billable is not None:
                print(f"    💳 Billable tokens: {billable}")
        
        print()
        print("=" * 60)
        print(f"✅ Gemini 3 Pro responded successfully {successes}/10 times!")
        print("=" * 60)
        return successes == 10
        
    except ImportError:
        print("❌ Error: google-genai package not installed")
        print("   Please install it with: pip install google-genai")
        return False
    except Exception as e:
        print(f"❌ API test failed: {e}")
        print()
        error_type = type(e).__name__
        if "API_KEY_INVALID" in str(e) or "401" in str(e) or "403" in str(e):
            print("   This looks like an authentication error.")
            print("   Please check that your API key is valid and has proper permissions.")
        elif "429" in str(e):
            print("   This looks like a rate limit error.")
            print("   The API key is valid but you've hit rate limits.")
        else:
            print(f"   Error type: {error_type}")
        return False

if __name__ == "__main__":
    success = test_gemini_api()
    sys.exit(0 if success else 1)

