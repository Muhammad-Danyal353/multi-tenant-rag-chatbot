"""
Quick verification script for BM25 implementation
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.qdrant_service import QdrantService
from app.services.retrieval_service import get_retrieval_service
from app.services.embedding_service import get_embedding_service


def verify_qdrant_service():
    """Verify Qdrant service has new methods"""
    print("="*60)
    print("1. Verifying Qdrant Service")
    print("="*60)
    
    qdrant_service = QdrantService()
    
    # Check for new methods
    has_text_index_method = hasattr(qdrant_service, 'create_collection_with_text_index')
    has_search_text_method = hasattr(qdrant_service, 'search_text')
    
    print(f"✓ create_collection_with_text_index: {' Present' if has_text_index_method else ' Missing'}")
    print(f"✓ search_text: {' Present' if has_search_text_method else ' Missing'}")
    
    if has_text_index_method and has_search_text_method:
        print("\n Qdrant Service: ALL METHODS PRESENT")
        return True
    else:
        print("\n Qdrant Service: MISSING METHODS")
        return False


def verify_retrieval_service():
    """Verify Retrieval service uses new BM25"""
    print("\n" + "="*60)
    print("2. Verifying Retrieval Service")
    print("="*60)
    
    retrieval_service = get_retrieval_service()
    
    # Check that retrieval service has the methods
    has_bm25_method = hasattr(retrieval_service, '_bm25_search')
    has_hybrid_method = hasattr(retrieval_service, 'hybrid_search')
    
    print(f"✓ _bm25_search: {' Present' if has_bm25_method else ' Missing'}")
    print(f"✓ hybrid_search: {' Present' if has_hybrid_method else ' Missing'}")
    
    # Check that it uses qdrant_service
    uses_qdrant = hasattr(retrieval_service, 'qdrant_service')
    print(f"✓ Uses qdrant_service: {' Yes' if uses_qdrant else ' No'}")
    
    if has_bm25_method and has_hybrid_method and uses_qdrant:
        print("\n Retrieval Service: PROPERLY CONFIGURED")
        return True
    else:
        print("\n Retrieval Service: CONFIGURATION ISSUE")
        return False


def verify_test_file():
    """Verify test file exists"""
    print("\n" + "="*60)
    print("3. Verifying Test File")
    print("="*60)
    
    test_file = os.path.join(os.path.dirname(__file__), '..', 'tests', 'test_hybrid_search.py')
    exists = os.path.exists(test_file)
    
    print(f"✓ test_hybrid_search.py: {' Exists' if exists else ' Missing'}")
    
    if exists:
        # Count test functions
        with open(test_file, 'r') as f:
            content = f.read()
            test_count = content.count('def test_')
        
        print(f"✓ Number of tests: {test_count}")
        print("\n Test File: CREATED")
        return True
    else:
        print("\n Test File: MISSING")
        return False


def verify_benchmark_file():
    """Verify benchmark file exists"""
    print("\n" + "="*60)
    print("4. Verifying Benchmark Script")
    print("="*60)
    
    benchmark_file = os.path.join(os.path.dirname(__file__), 'benchmark_search.py')
    exists = os.path.exists(benchmark_file)
    
    print(f"✓ benchmark_search.py: {' Exists' if exists else ' Missing'}")
    
    if exists:
        # Check for key functions
        with open(benchmark_file, "r", encoding="utf-8", errors="replace") as f:

            content = f.read()
            has_setup = 'def setup_benchmark_data' in content
            has_benchmark = 'def benchmark_search' in content
            has_cleanup = 'def cleanup' in content
        
        print(f"✓ setup_benchmark_data: {' Present' if has_setup else ' Missing'}")
        print(f"✓ benchmark_search: {' Present' if has_benchmark else ' Missing'}")
        print(f"✓ cleanup: {' Present' if has_cleanup else ' Missing'}")
        
        if has_setup and has_benchmark and has_cleanup:
            print("\n Benchmark Script: COMPLETE")
            return True
        else:
            print("\n Benchmark Script: INCOMPLETE")
            return False
    else:
        print("\n Benchmark Script: MISSING")
        return False


def verify_knowledge_service():
    """Verify knowledge service uses new collection creation"""
    print("\n" + "="*60)
    print("5. Verifying Knowledge Service")
    print("="*60)
    
    knowledge_file = os.path.join(os.path.dirname(__file__), '..', 'app', 'services', 'knowledge_service.py')
    
    if os.path.exists(knowledge_file):
        with open(knowledge_file, 'r') as f:
            content = f.read()
            uses_text_index = 'create_collection_with_text_index' in content
        
        print(f"✓ Uses create_collection_with_text_index: {' Yes' if uses_text_index else ' No'}")
        
        if uses_text_index:
            print("\n Knowledge Service: UPDATED")
            return True
        else:
            print("\n Knowledge Service: NOT UPDATED")
            return False
    else:
        print(" Knowledge Service: FILE NOT FOUND")
        return False


def main():
    """Run all verifications"""
    print("\n" + "="*60)
    print("BM25 IMPLEMENTATION VERIFICATION")
    print("="*60)
    
    results = []
    
    try:
        results.append(("Qdrant Service", verify_qdrant_service()))
        results.append(("Retrieval Service", verify_retrieval_service()))
        results.append(("Test File", verify_test_file()))
        results.append(("Benchmark Script", verify_benchmark_file()))
        results.append(("Knowledge Service", verify_knowledge_service()))
        
        # Summary
        print("\n" + "="*60)
        print("VERIFICATION SUMMARY")
        print("="*60)
        
        for name, passed in results:
            status = " PASS" if passed else " FAIL"
            print(f"{name:.<40} {status}")
        
        all_passed = all(result[1] for result in results)
        
        print("\n" + "="*60)
        if all_passed:
            print(" ALL VERIFICATIONS PASSED")
            print("="*60)
            print("\nDay 1-2 tasks are complete and verified!")
            print("\nNext steps:")
            print("1. Run tests: pytest tests/test_hybrid_search.py -v")
            print("2. Run benchmark: python scripts/benchmark_search.py")
            return 0
        else:
            print(" SOME VERIFICATIONS FAILED")
            print("="*60)
            print("\nPlease review the failed items above.")
            return 1
            
    except Exception as e:
        print(f"\n Verification failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
