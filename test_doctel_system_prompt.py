#!/usr/bin/env python3
"""
Test script to verify DocTel system prompt is correctly loaded and configured.
Run this to diagnose system prompt loading issues.
"""

import sys
import os
from pathlib import Path

# Add app directory to path
app_dir = Path(__file__).resolve().parent / "app"
sys.path.insert(0, str(app_dir.parent))

def test_config_loading():
    """Test that config.yaml is properly loaded."""
    print("\n" + "="*70)
    print("TEST 1: Config YAML Loading")
    print("="*70)
    
    try:
        from app.config import settings, _load_yaml_config
        
        # Check YAML file exists
        yaml_path = Path(__file__).resolve().parent / "app" / "config.yaml"
        print(f"✓ Config path: {yaml_path}")
        print(f"✓ Config exists: {yaml_path.exists()}")
        
        # Load YAML directly
        yaml_data = _load_yaml_config(str(yaml_path))
        print(f"✓ YAML loaded: {bool(yaml_data)}")
        print(f"✓ YAML keys: {list(yaml_data.keys())[:5]}...")
        
        return True
    except Exception as e:
        print(f"✗ Error loading config: {e}")
        return False


def test_system_prompt():
    """Test that system_prompt is correctly configured."""
    print("\n" + "="*70)
    print("TEST 2: System Prompt Configuration")
    print("="*70)
    
    try:
        from app.config import settings
        
        # Check system_prompt exists
        sys_prompt = settings.zetdc.system_prompt
        print(f"✓ System prompt loaded: {bool(sys_prompt)}")
        print(f"✓ System prompt length: {len(sys_prompt)} characters")
        
        # Check key content
        checks = [
            ("DocTel name", "DocTel Large Language Model" in sys_prompt),
            ("Who are you? response", "I am DocTel Large Language Model" in sys_prompt),
            ("What is ZETDC? response", "ZETDC is the Zimbabwe" in sys_prompt),
            ("ZETDC organization context", "Zimbabwe Electricity" in sys_prompt),
            ("Multilingual support", "Shona" in sys_prompt),
            ("Document handling", "WORKING WITH PROJECTS" in sys_prompt),
            ("Core responsibilities", "CORE RESPONSIBILITIES" in sys_prompt),
        ]
        
        all_passed = True
        for check_name, check_result in checks:
            status = "✓" if check_result else "✗"
            print(f"{status} {check_name}: {check_result}")
            if not check_result:
                all_passed = False
        
        return all_passed
    except Exception as e:
        print(f"✗ Error checking system prompt: {e}")
        return False


def test_gemini_service():
    """Test that Gemini service can use the system prompt."""
    print("\n" + "="*70)
    print("TEST 3: Gemini Service Configuration")
    print("="*70)
    
    try:
        from app.services.gemini_service import is_configured, _api_key, _model_name
        
        gemini_key = _api_key()
        print(f"✓ Gemini API key configured: {bool(gemini_key)}")
        print(f"✓ Gemini model: {_model_name()}")
        print(f"✓ Gemini is_configured: {is_configured()}")
        
        if not is_configured():
            print("⚠ WARNING: Gemini API key not configured. Set GEMINI_API_KEY in .env to test.")
            return False
        
        return True
    except Exception as e:
        print(f"✗ Error checking Gemini service: {e}")
        return False


def test_ollama_service():
    """Test that Ollama service can use the system prompt."""
    print("\n" + "="*70)
    print("TEST 4: Ollama Service Configuration")
    print("="*70)
    
    try:
        from app.config import settings
        from app.utils.ollama_client import ollama
        
        print(f"✓ Ollama base URL: {settings.ollama_base_url}")
        print(f"✓ Text model: {settings.text_model}")
        print(f"✓ Embedding model: {settings.embed_model}")
        
        return True
    except Exception as e:
        print(f"✗ Error checking Ollama service: {e}")
        return False


def test_main_endpoint():
    """Test that main.py will use the system prompt."""
    print("\n" + "="*70)
    print("TEST 5: Main Endpoint Integration")
    print("="*70)
    
    try:
        # Check that main.py imports settings correctly
        import app.main as main_module
        
        # Verify the ask_global function exists
        has_ask_global = hasattr(main_module, 'ask_global')
        print(f"✓ ask_global endpoint exists: {has_ask_global}")
        
        # Verify settings are imported
        has_settings = hasattr(main_module, 'settings')
        print(f"✓ settings imported in main: {has_settings}")
        
        return has_ask_global and has_settings
    except Exception as e:
        print(f"✗ Error checking main endpoint: {e}")
        return False


def print_system_prompt_preview():
    """Print a preview of the system prompt."""
    print("\n" + "="*70)
    print("SYSTEM PROMPT PREVIEW (First 500 chars)")
    print("="*70)
    
    try:
        from app.config import settings
        
        prompt = settings.zetdc.system_prompt
        preview = prompt[:500] if prompt else "[EMPTY]"
        print(preview)
        print("...")
    except Exception as e:
        print(f"Error: {e}")


def main():
    """Run all tests."""
    print("\n" + "#"*70)
    print("# DocTel System Prompt Verification Tests")
    print("#"*70)
    
    results = []
    
    # Run tests
    results.append(("Config Loading", test_config_loading()))
    results.append(("System Prompt", test_system_prompt()))
    results.append(("Gemini Service", test_gemini_service()))
    results.append(("Ollama Service", test_ollama_service()))
    results.append(("Main Endpoint", test_main_endpoint()))
    
    # Print system prompt preview
    print_system_prompt_preview()
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✅ All tests passed! System is ready.")
        print("\nNext steps:")
        print("1. Restart the server: python run_dev.py")
        print("2. Test with: 'Who are you?' and 'What is ZETDC?'")
        print("3. Verify DocTel responses are returned")
        return 0
    else:
        print("\n⚠️  Some tests failed. Please check the output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
