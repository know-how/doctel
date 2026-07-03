#!/usr/bin/env python
"""
Test OpenCode Go API Integration

This script tests:
1. Model listing and availability
2. API connectivity
3. Response generation (non-streaming)
4. Stream response generation
5. Model routing and fallbacks
"""

import asyncio
import json
import sys
import os
from dotenv import load_dotenv

# Load environment
load_dotenv()

async def test_opencode_config():
    """Test OpenCode configuration"""
    print("\n" + "="*60)
    print("1. Testing OpenCode Configuration")
    print("="*60)
    
    go_key = os.getenv("OPENCODE_GO_API_KEY", "").strip()
    go_url = os.getenv("OPENCODE_GO_BASE_URL", "").strip()
    zen_key = os.getenv("OPENCODE_ZEN_API_KEY", "").strip()
    
    print(f"✓ OPENCODE_GO_API_KEY: {go_key[:20]}..." if go_key else "✗ OPENCODE_GO_API_KEY: NOT SET")
    print(f"✓ OPENCODE_GO_BASE_URL: {go_url}" if go_url else "✗ OPENCODE_GO_BASE_URL: NOT SET")
    print(f"✓ OPENCODE_ZEN_API_KEY: {zen_key[:20]}..." if zen_key else "  OPENCODE_ZEN_API_KEY: NOT SET (deprecated)")
    
    return bool(go_key and go_url)

async def test_model_listing():
    """Test model listing from opencode_zen_service"""
    print("\n" + "="*60)
    print("2. Testing Available Models")
    print("="*60)
    
    try:
        from app.services.opencode_zen_service import (
            is_configured,
            get_available_models,
            get_display_name
        )
        
        if not is_configured():
            print("✗ OpenCode API is not configured")
            return False
        
        models = get_available_models()
        print(f"✓ Found {len(models)} available models:")
        
        # Group by tier
        tiers = {}
        for model in models:
            tier = model.get("tier", "unknown")
            if tier not in tiers:
                tiers[tier] = []
            tiers[tier].append(model)
        
        for tier, tier_models in sorted(tiers.items()):
            print(f"\n  {tier.upper()} TIER ({len(tier_models)} models):")
            for m in tier_models[:3]:  # Show first 3 of each tier
                display = get_display_name(m["id"])
                print(f"    - {m['id']}: {display}")
            if len(tier_models) > 3:
                print(f"    ... and {len(tier_models) - 3} more")
        
        return True
    except Exception as e:
        print(f"✗ Error listing models: {e}")
        return False

async def test_deepseek_generation():
    """Test DeepSeek API response generation"""
    print("\n" + "="*60)
    print("3. Testing DeepSeek API Generation")
    print("="*60)
    
    try:
        from app.services.deepseek_service import (
            is_configured,
            generate,
            _model_name,
            _base_url
        )
        
        if not is_configured():
            print("✗ DeepSeek API is not configured")
            return False
        
        model = _model_name()
        url = _base_url()
        print(f"✓ Configured model: {model}")
        print(f"✓ Base URL: {url}")
        
        print("\nTesting generation (this may take 10-30 seconds)...")
        response = await asyncio.wait_for(
            generate("What is machine learning in one sentence?"),
            timeout=45.0
        )
        
        print(f"✓ Generation successful!")
        print(f"  Response: {response[:100]}..." if len(response) > 100 else f"  Response: {response}")
        
        return True
    except asyncio.TimeoutError:
        print("✗ DeepSeek generation timed out")
        return False
    except Exception as e:
        print(f"✗ DeepSeek generation failed: {e}")
        return False

async def test_zen_generation():
    """Test OpenCode Go generation"""
    print("\n" + "="*60)
    print("4. Testing OpenCode Go Generation")
    print("="*60)
    
    try:
        from app.services.opencode_zen_service import (
            is_configured,
            generate,
            get_available_models
        )
        
        if not is_configured():
            print("✗ OpenCode Go API is not configured")
            return False
        
        models = get_available_models()
        if not models:
            print("✗ No models available")
            return False
        
        test_model = models[0]["id"]  # Use first available model
        print(f"Testing with model: {test_model}")
        
        print("\nTesting generation (this may take 10-30 seconds)...")
        response = await asyncio.wait_for(
            generate("What is deep learning?", model=test_model),
            timeout=45.0
        )
        
        print(f"✓ Generation successful!")
        print(f"  Response: {response[:100]}..." if len(response) > 100 else f"  Response: {response}")
        
        return True
    except asyncio.TimeoutError:
        print("✗ OpenCode Go generation timed out")
        return False
    except Exception as e:
        print(f"✗ OpenCode Go generation failed: {e}")
        return False

async def test_streaming():
    """Test streaming generation"""
    print("\n" + "="*60)
    print("5. Testing Streaming Generation")
    print("="*60)
    
    try:
        from app.services.opencode_zen_service import (
            is_configured,
            generate_stream,
            get_available_models
        )
        
        if not is_configured():
            print("✗ OpenCode Go API is not configured")
            return False
        
        models = get_available_models()
        if not models:
            print("✗ No models available")
            return False
        
        test_model = models[0]["id"]
        print(f"Testing streaming with model: {test_model}")
        print("\nStreaming response:")
        print("-" * 40)
        
        chunks = []
        async for chunk in asyncio.wait_for(
            generate_stream("Write a haiku about artificial intelligence", model=test_model),
            timeout=45.0
        ):
            chunks.append(chunk)
            print(chunk, end="", flush=True)
        
        print("\n" + "-" * 40)
        print(f"✓ Streaming successful! Received {len(chunks)} chunks")
        
        return True
    except asyncio.TimeoutError:
        print("\n✗ Streaming generation timed out")
        return False
    except Exception as e:
        print(f"\n✗ Streaming generation failed: {e}")
        return False

async def test_model_resolution():
    """Test model ID resolution"""
    print("\n" + "="*60)
    print("6. Testing Model ID Resolution")
    print("="*60)
    
    try:
        from app.services.opencode_zen_service import _resolve_model_id
        
        test_cases = [
            ("go/deepseek-v4-flash-free", "deepseek-v4-flash-free"),
            ("zen/deepseek-v4-flash-free", "deepseek-v4-flash-free"),
            ("deepseek-v4-flash-free", "deepseek-v4-flash-free"),
        ]
        
        all_pass = True
        for input_id, expected in test_cases:
            result = _resolve_model_id(input_id)
            status = "✓" if result == expected else "✗"
            print(f"{status} {input_id} -> {result} (expected: {expected})")
            if result != expected:
                all_pass = False
        
        return all_pass
    except Exception as e:
        print(f"✗ Model resolution test failed: {e}")
        return False

async def test_model_validation():
    """Test model validation in main.py"""
    print("\n" + "="*60)
    print("7. Testing Model Validation")
    print("="*60)
    
    try:
        # Import the validation function from main
        sys.path.insert(0, os.path.dirname(__file__))
        from app.main import _is_generation_model
        
        test_models = [
            ("go/deepseek-v4-flash-free", True),
            ("zen/deepseek-v4-flash-free", True),
            ("llama3.2:8b", True),
            ("nomic-embed-text", False),  # Embedding model
            ("gemini-api", True),
        ]
        
        all_pass = True
        for model, should_be_generation in test_models:
            is_gen = _is_generation_model(model)
            status = "✓" if is_gen == should_be_generation else "✗"
            result = "generation" if is_gen else "non-generation"
            expected = "generation" if should_be_generation else "non-generation"
            print(f"{status} {model}: {result} (expected: {expected})")
            if is_gen != should_be_generation:
                all_pass = False
        
        return all_pass
    except Exception as e:
        print(f"✗ Model validation test failed: {e}")
        return False

async def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("OPENCODE GO API INTEGRATION TEST SUITE")
    print("="*60)
    
    tests = [
        ("Configuration", test_opencode_config),
        ("Model Listing", test_model_listing),
        ("DeepSeek Generation", test_deepseek_generation),
        ("OpenCode Go Generation", test_zen_generation),
        ("Streaming", test_streaming),
        ("Model Resolution", test_model_resolution),
        ("Model Validation", test_model_validation),
    ]
    
    results = {}
    for name, test_func in tests:
        try:
            results[name] = await test_func()
        except Exception as e:
            print(f"\n✗ Test '{name}' crashed: {e}")
            results[name] = False
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for name, passed_test in results.items():
        status = "✓ PASS" if passed_test else "✗ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✓ All tests passed! OpenCode Go integration is working correctly.")
        return 0
    else:
        print(f"\n✗ {total - passed} test(s) failed. Please check the errors above.")
        return 1

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\nTests interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\nFatal error: {e}")
        sys.exit(1)
