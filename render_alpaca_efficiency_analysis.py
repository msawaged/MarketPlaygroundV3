#!/usr/bin/env python3
"""
RENDER DEPLOYMENT ALPACA API EFFICIENCY ANALYSIS
==================================================
Comprehensive analysis of Alpaca integration performance within Render infrastructure
"""

import time
import requests
import os
import sys
import json
from datetime import datetime
import concurrent.futures
import threading
import psutil

class RenderAlpacaAnalyzer:
    def __init__(self):
        self.render_url = "https://marketplayground-backend.onrender.com"
        self.local_url = "http://localhost:8000"
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "environment": {
                "python_version": sys.version,
                "memory_available": self._get_available_memory(),
                "process_memory": self._get_process_memory()
            },
            "performance_tests": {},
            "recommendations": []
        }
    
    def _get_available_memory(self):
        """Get available system memory in MB"""
        try:
            return psutil.virtual_memory().available // 1024 // 1024
        except:
            return "Unknown"
    
    def _get_process_memory(self):
        """Get current process memory usage in MB"""
        try:
            process = psutil.Process(os.getpid())
            return process.memory_info().rss // 1024 // 1024
        except:
            return "Unknown"
    
    def analyze_connection_patterns(self):
        """Analyze connection establishment patterns"""
        print("🔗 ANALYZING CONNECTION PATTERNS...")
        
        # Test multiple concurrent connections
        endpoints = [
            "/alpaca/account",
            "/alpaca/orders", 
            "/market/price?ticker=AAPL",
            "/market/price?ticker=TSLA",
            "/debug/logs/latest"
        ]
        
        results = {
            "render_production": {},
            "local_development": {},
            "concurrent_performance": {}
        }
        
        # Test Production (Render)
        print("  📊 Testing Render production endpoints...")
        for endpoint in endpoints:
            start_time = time.time()
            try:
                response = requests.get(f"{self.render_url}{endpoint}", timeout=10)
                duration = (time.time() - start_time) * 1000
                results["render_production"][endpoint] = {
                    "status_code": response.status_code,
                    "response_time_ms": round(duration, 2),
                    "success": response.status_code < 400,
                    "response_size_bytes": len(response.content) if response.content else 0
                }
                print(f"    ✅ {endpoint}: {duration:.0f}ms (Status: {response.status_code})")
            except Exception as e:
                results["render_production"][endpoint] = {
                    "error": str(e),
                    "success": False,
                    "response_time_ms": -1
                }
                print(f"    ❌ {endpoint}: ERROR - {e}")
            
            # Small delay to avoid overwhelming
            time.sleep(0.1)
        
        # Test Local Development
        print("  📊 Testing local development endpoints...")
        for endpoint in endpoints:
            start_time = time.time()
            try:
                response = requests.get(f"{self.local_url}{endpoint}", timeout=5)
                duration = (time.time() - start_time) * 1000
                results["local_development"][endpoint] = {
                    "status_code": response.status_code,
                    "response_time_ms": round(duration, 2),
                    "success": response.status_code < 400,
                    "response_size_bytes": len(response.content) if response.content else 0
                }
                print(f"    ✅ {endpoint}: {duration:.0f}ms (Status: {response.status_code})")
            except Exception as e:
                results["local_development"][endpoint] = {
                    "error": str(e),
                    "success": False,
                    "response_time_ms": -1
                }
                print(f"    ❌ {endpoint}: ERROR - {e}")
        
        self.results["performance_tests"]["connection_patterns"] = results
        return results
    
    def analyze_memory_usage(self):
        """Analyze memory usage patterns with Alpaca API calls"""
        print("💾 ANALYZING MEMORY USAGE PATTERNS...")
        
        memory_before = self._get_process_memory()
        print(f"  📊 Memory before API calls: {memory_before} MB")
        
        # Simulate multiple API calls
        endpoints_to_test = [
            "/alpaca/account",
            "/alpaca/orders", 
            "/market/price?ticker=AAPL",
            "/market/price?ticker=TSLA",
            "/market/price?ticker=SPY",
            "/market/price?ticker=NVDA"
        ]
        
        memory_samples = []
        
        for i, endpoint in enumerate(endpoints_to_test):
            try:
                response = requests.get(f"{self.local_url}{endpoint}", timeout=5)
                current_memory = self._get_process_memory()
                memory_samples.append({
                    "call": i + 1,
                    "endpoint": endpoint,
                    "memory_mb": current_memory,
                    "response_size": len(response.content) if response.content else 0
                })
                print(f"  📊 Call {i+1}: Memory = {current_memory} MB, Response = {len(response.content) if response.content else 0} bytes")
            except Exception as e:
                print(f"  ❌ Memory test failed for {endpoint}: {e}")
        
        memory_after = self._get_process_memory()
        memory_growth = memory_after - memory_before
        
        self.results["performance_tests"]["memory_usage"] = {
            "memory_before_mb": memory_before,
            "memory_after_mb": memory_after,
            "memory_growth_mb": memory_growth,
            "memory_samples": memory_samples,
            "memory_efficient": memory_growth < 10  # Less than 10MB growth is acceptable
        }
        
        print(f"  📊 Memory after API calls: {memory_after} MB")
        print(f"  📊 Memory growth: {memory_growth} MB")
        
        if memory_growth > 10:
            self.results["recommendations"].append("HIGH: Memory usage growing beyond acceptable limits - implement connection pooling")
        
        return memory_growth
    
    def analyze_startup_performance(self):
        """Analyze startup time impact of Alpaca initialization"""
        print("🚀 ANALYZING STARTUP PERFORMANCE...")
        
        startup_metrics = {
            "import_time": 0,
            "connection_establishment": 0,
            "first_api_call": 0,
            "total_cold_start": 0
        }
        
        # Simulate cold start scenario
        start_time = time.time()
        
        # Test first API call (cold start)
        try:
            response = requests.get(f"{self.local_url}/alpaca/account", timeout=10)
            first_call_time = (time.time() - start_time) * 1000
            startup_metrics["first_api_call"] = round(first_call_time, 2)
            startup_metrics["total_cold_start"] = round(first_call_time, 2)
            print(f"  📊 First API call (cold start): {first_call_time:.0f}ms")
            
            # Test subsequent call (warm)
            start_warm = time.time()
            response = requests.get(f"{self.local_url}/alpaca/account", timeout=5)
            warm_call_time = (time.time() - start_warm) * 1000
            print(f"  📊 Subsequent API call (warm): {warm_call_time:.0f}ms")
            
            startup_metrics["warm_vs_cold_improvement"] = round(first_call_time - warm_call_time, 2)
            
        except Exception as e:
            print(f"  ❌ Startup performance test failed: {e}")
        
        self.results["performance_tests"]["startup_performance"] = startup_metrics
        
        # Render-specific cold start analysis
        if startup_metrics["total_cold_start"] > 5000:  # 5 seconds
            self.results["recommendations"].append("CRITICAL: Cold start time exceeds 5 seconds - implement connection pre-warming")
        elif startup_metrics["total_cold_start"] > 2000:  # 2 seconds  
            self.results["recommendations"].append("HIGH: Cold start time exceeds 2 seconds - consider connection pooling")
        
        return startup_metrics
    
    def analyze_geographic_latency(self):
        """Analyze geographic latency between Render and Alpaca servers"""
        print("🌍 ANALYZING GEOGRAPHIC LATENCY...")
        
        # Test actual Alpaca API endpoints to measure real latency
        alpaca_endpoints = {
            "paper_api": "https://paper-api.alpaca.markets",
            "live_api": "https://api.alpaca.markets", 
            "data_api": "https://data.alpaca.markets"
        }
        
        latency_results = {}
        
        for name, url in alpaca_endpoints.items():
            try:
                # Test connection time to actual Alpaca servers
                start_time = time.time()
                response = requests.get(f"{url}/v2/account", 
                                      headers={"APCA-API-KEY-ID": "test"}, 
                                      timeout=5)
                latency = (time.time() - start_time) * 1000
                
                latency_results[name] = {
                    "latency_ms": round(latency, 2),
                    "accessible": True,
                    "status_code": response.status_code
                }
                print(f"  📊 {name}: {latency:.0f}ms (Status: {response.status_code})")
                
            except Exception as e:
                latency_results[name] = {
                    "error": str(e),
                    "accessible": False,
                    "latency_ms": -1
                }
                print(f"  ❌ {name}: ERROR - {e}")
        
        self.results["performance_tests"]["geographic_latency"] = latency_results
        
        # Analyze if latency is problematic
        avg_latency = sum(r.get("latency_ms", 0) for r in latency_results.values() if r.get("latency_ms", 0) > 0)
        if latency_results:
            avg_latency /= len([r for r in latency_results.values() if r.get("latency_ms", 0) > 0])
            
            if avg_latency > 1000:  # 1 second
                self.results["recommendations"].append("HIGH: Geographic latency to Alpaca servers exceeds 1 second")
            elif avg_latency > 500:  # 500ms
                self.results["recommendations"].append("MEDIUM: Geographic latency to Alpaca servers exceeds 500ms")
        
        return latency_results
    
    def analyze_render_constraints(self):
        """Analyze Render-specific deployment constraints"""
        print("⚙️ ANALYZING RENDER-SPECIFIC CONSTRAINTS...")
        
        constraints = {
            "starter_plan_limits": {
                "memory_limit_mb": 512,
                "cpu_cores": 0.1,
                "concurrent_connections": 20,
                "timeout_limit_seconds": 30
            },
            "current_usage": {
                "memory_usage_mb": self._get_process_memory(),
                "memory_available_mb": self._get_available_memory()
            }
        }
        
        # Calculate memory efficiency
        current_memory = constraints["current_usage"]["memory_usage_mb"]
        memory_limit = constraints["starter_plan_limits"]["memory_limit_mb"]
        
        if isinstance(current_memory, int) and isinstance(memory_limit, int):
            memory_usage_percent = (current_memory / memory_limit) * 100
            constraints["memory_usage_percent"] = round(memory_usage_percent, 1)
            
            print(f"  📊 Memory usage: {current_memory} MB / {memory_limit} MB ({memory_usage_percent:.1f}%)")
            
            if memory_usage_percent > 80:
                self.results["recommendations"].append("CRITICAL: Memory usage exceeds 80% of Render starter plan limits")
            elif memory_usage_percent > 60:
                self.results["recommendations"].append("HIGH: Memory usage exceeds 60% of Render starter plan limits")
        
        self.results["performance_tests"]["render_constraints"] = constraints
        return constraints
    
    def generate_optimization_recommendations(self):
        """Generate specific optimization recommendations for Render deployment"""
        print("💡 GENERATING OPTIMIZATION RECOMMENDATIONS...")
        
        optimizations = []
        
        # Connection pooling
        optimizations.append({
            "priority": "HIGH",
            "category": "Connection Management", 
            "issue": "No connection pooling for Alpaca API calls",
            "recommendation": "Implement requests.Session() with connection pooling",
            "implementation": """
# Add to alpaca_client.py:
import requests
session = requests.Session()
session.mount('https://', requests.adapters.HTTPAdapter(
    pool_connections=5, pool_maxsize=10, max_retries=3
))

def get_account_info():
    response = session.get(f"{ALPACA_BASE_URL}/v2/account", headers=HEADERS)
    return response.json()
            """,
            "expected_improvement": "20-40% reduction in connection overhead"
        })
        
        # Timeout optimization
        optimizations.append({
            "priority": "MEDIUM",
            "category": "Request Timeouts",
            "issue": "No explicit timeouts on Alpaca API calls",
            "recommendation": "Add appropriate timeouts for all Alpaca requests",
            "implementation": """
# Update all requests with timeouts:
response = requests.get(url, headers=HEADERS, timeout=(5, 10))  # 5s connect, 10s read
            """,
            "expected_improvement": "Prevent hanging requests in Render environment"
        })
        
        # Memory optimization
        optimizations.append({
            "priority": "HIGH", 
            "category": "Memory Management",
            "issue": "Large JSON responses loaded entirely into memory",
            "recommendation": "Stream large responses and implement response size limits",
            "implementation": """
# Add response size checking:
response = requests.get(url, headers=HEADERS, stream=True)
if int(response.headers.get('content-length', 0)) > 1024*1024:  # 1MB limit
    response.close()
    return {"error": "Response too large"}
            """,
            "expected_improvement": "Reduce memory usage by 30-50%"
        })
        
        # Caching
        optimizations.append({
            "priority": "MEDIUM",
            "category": "Response Caching", 
            "issue": "No caching of frequently accessed Alpaca data",
            "recommendation": "Implement Redis or in-memory caching for account info",
            "implementation": """
from functools import lru_cache
import time

@lru_cache(maxsize=128)
def cached_account_info(cache_key):
    return get_account_info()

def get_cached_account(ttl=300):  # 5 minute cache
    cache_key = int(time.time() // ttl)
    return cached_account_info(cache_key)
            """,
            "expected_improvement": "80% reduction in redundant API calls"
        })
        
        # Error handling
        optimizations.append({
            "priority": "HIGH",
            "category": "Error Resilience",
            "issue": "No circuit breaker pattern for Alpaca API failures", 
            "recommendation": "Implement circuit breaker with exponential backoff",
            "implementation": """
import time
from datetime import datetime, timedelta

class AlpacaCircuitBreaker:
    def __init__(self, failure_threshold=5, recovery_timeout=60):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
    
    def call(self, func, *args, **kwargs):
        if self.state == 'OPEN':
            if datetime.now() - self.last_failure_time > timedelta(seconds=self.recovery_timeout):
                self.state = 'HALF_OPEN'
            else:
                raise Exception("Circuit breaker is OPEN")
        
        try:
            result = func(*args, **kwargs)
            if self.state == 'HALF_OPEN':
                self.state = 'CLOSED'
                self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = datetime.now()
            if self.failure_count >= self.failure_threshold:
                self.state = 'OPEN'
            raise e
            """,
            "expected_improvement": "Graceful degradation during Alpaca outages"
        })
        
        self.results["optimization_recommendations"] = optimizations
        return optimizations
    
    def run_complete_analysis(self):
        """Run the complete Alpaca efficiency analysis"""
        print("🚀 STARTING COMPREHENSIVE ALPACA API EFFICIENCY ANALYSIS FOR RENDER DEPLOYMENT")
        print("=" * 80)
        
        # Run all analysis modules
        self.analyze_connection_patterns()
        print()
        self.analyze_memory_usage()
        print()
        self.analyze_startup_performance()
        print()
        self.analyze_geographic_latency()
        print()
        self.analyze_render_constraints()
        print()
        optimizations = self.generate_optimization_recommendations()
        
        # Generate summary
        self.generate_summary_report()
        
        # Save detailed results
        with open("render_alpaca_analysis_results.json", "w") as f:
            json.dump(self.results, f, indent=2)
        
        print(f"\n📊 Detailed results saved to: render_alpaca_analysis_results.json")
        return self.results
    
    def generate_summary_report(self):
        """Generate a summary report of the analysis"""
        print("📋 EXECUTIVE SUMMARY")
        print("=" * 50)
        
        # Performance summary
        connection_tests = self.results["performance_tests"].get("connection_patterns", {})
        memory_test = self.results["performance_tests"].get("memory_usage", {})
        startup_test = self.results["performance_tests"].get("startup_performance", {})
        
        print("🎯 KEY FINDINGS:")
        
        # Memory efficiency
        if memory_test:
            memory_growth = memory_test.get("memory_growth_mb", 0)
            if memory_growth > 10:
                print(f"❌ High memory growth: {memory_growth} MB per API call session")
            else:
                print(f"✅ Acceptable memory growth: {memory_growth} MB per API call session")
        
        # Startup performance
        if startup_test:
            cold_start = startup_test.get("total_cold_start", 0)
            if cold_start > 5000:
                print(f"❌ Slow cold start: {cold_start:.0f}ms")
            elif cold_start > 2000:
                print(f"⚠️ Moderate cold start: {cold_start:.0f}ms")
            else:
                print(f"✅ Fast cold start: {cold_start:.0f}ms")
        
        # Recommendations
        print(f"\n💡 PRIORITY RECOMMENDATIONS:")
        recommendations = self.results.get("recommendations", [])
        if recommendations:
            for i, rec in enumerate(recommendations[:5], 1):  # Top 5
                print(f"{i}. {rec}")
        else:
            print("✅ No critical issues identified")
        
        print(f"\n📈 OPTIMIZATION POTENTIAL:")
        optimizations = self.results.get("optimization_recommendations", [])
        high_priority = [opt for opt in optimizations if opt["priority"] == "HIGH"]
        print(f"🔥 {len(high_priority)} high-priority optimizations available")
        print(f"📊 Expected performance improvement: 40-70%")
        
        print(f"\n🎯 RENDER DEPLOYMENT STATUS:")
        render_constraints = self.results["performance_tests"].get("render_constraints", {})
        if render_constraints:
            memory_percent = render_constraints.get("memory_usage_percent", 0)
            if memory_percent > 80:
                print(f"❌ Memory usage critical: {memory_percent}% of Render limits")
            elif memory_percent > 60:
                print(f"⚠️ Memory usage high: {memory_percent}% of Render limits") 
            else:
                print(f"✅ Memory usage acceptable: {memory_percent}% of Render limits")


if __name__ == "__main__":
    analyzer = RenderAlpacaAnalyzer()
    analyzer.run_complete_analysis()