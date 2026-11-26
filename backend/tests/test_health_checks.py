#!/usr/bin/env python3
"""
Test script to verify health checks functionality.
"""

import asyncio
import sys
from pathlib import Path

# Add the backend directory to Python path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

async def test_health_checks():
    """Test health check functionality."""
    try:
        from app.core.health_checks import HealthChecker
        
        print("Testing Health Check System...")
        
        # Create health checker instance
        health_checker = HealthChecker()
        
        # Run individual checks
        print("\n1. Testing Database Health Check...")
        db_result = await health_checker.check_database()
        print(f"   Status: {'PASS' if db_result.success else 'FAIL'}")
        print(f"   Message: {db_result.message}")
        
        print("\n2. Testing Qdrant Health Check...")
        qdrant_result = await health_checker.check_qdrant()
        print(f"   Status: {'PASS' if qdrant_result.success else 'FAIL'}")
        print(f"   Message: {qdrant_result.message}")
        
        print("\n3. Testing OpenAI Health Check...")
        openai_result = await health_checker.check_openai()
        print(f"   Status: {'PASS' if openai_result.success else 'FAIL'}")
        print(f"   Message: {openai_result.message}")
        
        print("\n4. Testing Embedding Service Health Check...")
        embedding_result = await health_checker.check_embedding_service()
        print(f"   Status: {'PASS' if embedding_result.success else 'FAIL'}")
        print(f"   Message: {embedding_result.message}")
        
        print("\n5. Testing Email Service Health Check...")
        email_result = await health_checker.check_email_service()
        print(f"   Status: {'PASS' if email_result.success else 'FAIL'}")
        print(f"   Message: {email_result.message}")
        
        # Get summary
        print("\nHealth Check Summary:")
        summary = health_checker.get_summary()
        print(f"   Overall Status: {summary['status']}")
        print(f"   Successful Services: {summary['successful_services']}/{summary['total_services']}")
        
        # Show service details
        print("\nService Details:")
        for service, details in summary['services'].items():
            status_text = "HEALTHY" if details['status'] == 'healthy' else "UNHEALTHY"
            print(f"   {status_text} {service}: {details['message']}")
        
        print("\nHealth check test completed!")
        
        # Test startup health checks
        print("\nTesting Startup Health Checks...")
        try:
            from app.core.health_checks import run_startup_health_checks
            startup_results = await run_startup_health_checks()
            
            print("Startup health checks completed successfully!")
            return True
            
        except Exception as e:
            print(f"Startup health checks failed: {str(e)}")
            return False
        
    except Exception as e:
        print(f"Error testing health checks: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_health_checks())
    sys.exit(0 if success else 1)
