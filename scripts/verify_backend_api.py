#!/usr/bin/env python3
"""
Backend API Endpoint Verification Script
Validates that all required API endpoints exist and are functioning
"""

import requests
import json
from typing import Dict, List, Tuple

# Configuration
BASE_URL = "http://127.0.0.1:8000"
TEST_EC_NUMBER = "EC123456"
TEST_PASSWORD = "test123"
TEST_EMAIL = "test@zetdc.co.zw"

class APITester:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.token = None
        self.results = {
            "passed": [],
            "failed": [],
            "warnings": []
        }
    
    def test_endpoint(self, method: str, path: str, data: Dict = None, 
                     expect_auth: bool = True, expect_status: int = 200) -> bool:
        """Test a single API endpoint"""
        url = f"{self.base_url}{path}"
        headers = {}
        
        if expect_auth and self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        
        try:
            if method == "GET":
                resp = requests.get(url, headers=headers, timeout=5)
            elif method == "POST":
                resp = requests.post(url, json=data, headers=headers, timeout=5)
            elif method == "PUT":
                resp = requests.put(url, json=data, headers=headers, timeout=5)
            elif method == "DELETE":
                resp = requests.delete(url, headers=headers, timeout=5)
            else:
                return False
            
            success = resp.status_code == expect_status
            
            if success:
                self.results["passed"].append(f"{method} {path}")
            else:
                self.results["failed"].append(
                    f"{method} {path} - Got {resp.status_code}, expected {expect_status}"
                )
            
            return success
        
        except Exception as e:
            self.results["failed"].append(f"{method} {path} - {str(e)}")
            return False
    
    def run_all_tests(self):
        """Run complete endpoint validation suite"""
        
        print("🧪 Starting API Endpoint Verification...\n")
        
        # ── Authentication Endpoints ──
        print("📌 Testing Authentication Endpoints...")
        
        # Login test
        print("  • Testing POST /auth/login...")
        login_data = {"ec_number": TEST_EC_NUMBER, "password": TEST_PASSWORD}
        if self.test_endpoint("POST", "/auth/login", login_data, expect_auth=False):
            print("    ✅ Login endpoint works")
        else:
            print("    ❌ Login endpoint failed")
        
        # Email OTP test
        print("  • Testing POST /auth/email/request...")
        if self.test_endpoint("POST", "/auth/email/request", 
                            {"email": TEST_EMAIL}, expect_auth=False):
            print("    ✅ Email OTP request works")
        else:
            print("    ❌ Email OTP request failed")
        
        print()
        
        # ── User Endpoints ──
        print("📌 Testing User Endpoints...")
        
        endpoints_to_test = [
            ("GET", "/users/me", "User info"),
            ("GET", "/api/settings/ui", "UI Settings"),
            ("GET", "/users/me/history", "User history"),
            ("GET", "/users/me/summary-history", "Summary history"),
        ]
        
        for method, path, desc in endpoints_to_test:
            print(f"  • Testing {method} {path} ({desc})...")
            if self.test_endpoint(method, path):
                print(f"    ✅ {desc} endpoint works")
            else:
                print(f"    ⚠️  {desc} endpoint may need authentication or be unavailable")
        
        print()
        
        # ── Project Endpoints ──
        print("📌 Testing Project Endpoints...")
        
        project_endpoints = [
            ("GET", "/projects", "List projects"),
            ("GET", "/api/me/projects", "My projects"),
            ("GET", "/api/me/documents", "My documents"),
        ]
        
        for method, path, desc in project_endpoints:
            print(f"  • Testing {method} {path} ({desc})...")
            if self.test_endpoint(method, path):
                print(f"    ✅ {desc} endpoint works")
            else:
                print(f"    ⚠️  {desc} endpoint may need authentication")
        
        print()
        
        # ── Model Endpoints ──
        print("📌 Testing Model Endpoints...")
        
        model_endpoints = [
            ("GET", "/api/models/available", "Available models"),
            ("GET", "/api/models/labels", "Model labels"),
        ]
        
        for method, path, desc in model_endpoints:
            print(f"  • Testing {method} {path} ({desc})...")
            if self.test_endpoint(method, path):
                print(f"    ✅ {desc} endpoint works")
            else:
                print(f"    ⚠️  {desc} endpoint may need authentication")
        
        print()
        
        # ── System Endpoints ──
        print("📌 Testing System Endpoints...")
        
        system_endpoints = [
            ("GET", "/api/bootstrap/status", "Bootstrap status"),
        ]
        
        for method, path, desc in system_endpoints:
            print(f"  • Testing {method} {path} ({desc})...")
            if self.test_endpoint(method, path):
                print(f"    ✅ {desc} endpoint works")
            else:
                print(f"    ⚠️  {desc} endpoint may be unavailable")
        
        print()
        
        # Print Summary
        self._print_summary()
    
    def _print_summary(self):
        """Print test summary"""
        print("\n" + "="*60)
        print("📊 TEST SUMMARY")
        print("="*60)
        
        passed = len(self.results["passed"])
        failed = len(self.results["failed"])
        total = passed + failed
        
        print(f"\n✅ Passed: {passed}/{total}")
        print(f"❌ Failed: {failed}/{total}")
        
        if self.results["failed"]:
            print("\n⚠️  Failed Endpoints:")
            for failure in self.results["failed"]:
                print(f"  • {failure}")
        
        if self.results["warnings"]:
            print("\n🔔 Warnings:")
            for warning in self.results["warnings"]:
                print(f"  • {warning}")
        
        print("\n" + "="*60)
        
        if failed == 0:
            print("✅ All endpoints are functioning!")
        else:
            print(f"⚠️  {failed} endpoint(s) need attention")
        
        print("="*60 + "\n")


def main():
    """Main entry point"""
    print("\n🔗 DOCINTEL BACKEND API VERIFICATION")
    print("="*60)
    print(f"Testing backend at: {BASE_URL}")
    print("="*60 + "\n")
    
    tester = APITester(BASE_URL)
    
    # Check if backend is running
    try:
        resp = requests.get(f"{BASE_URL}/api/bootstrap/status", timeout=5)
        print(f"✅ Backend is reachable (HTTP {resp.status_code})\n")
    except Exception as e:
        print(f"❌ Cannot reach backend at {BASE_URL}")
        print(f"   Error: {str(e)}")
        print("\n   Make sure to run: python -m uvicorn app.main:app --host 127.0.0.1 --port 8000\n")
        return
    
    # Run tests
    tester.run_all_tests()


if __name__ == "__main__":
    main()
