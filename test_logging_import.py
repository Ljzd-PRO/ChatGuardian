#!/usr/bin/env python3
"""Quick test to verify services.py imports and basic logging setup."""

import asyncio
import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

async def main():
    """Test if services module imports correctly and loguru is configured."""
    try:
        print("🔍 Testing services.py import...")
        from chat_guardian import services
        print("✅ services module imported successfully")
        
        # Check that loguru is available
        from loguru import logger
        print("✅ loguru logger imported successfully")
        
        # Check key classes exist
        assert hasattr(services, 'LangChainLLMClient')
        assert hasattr(services, 'DetectionEngine')
        assert hasattr(services, 'RuleBatchScheduler')
        assert hasattr(services, 'SelfMessageMemoryService')
        assert hasattr(services, 'EmailNotifier')
        assert hasattr(services, 'ExternalHookDispatcher')
        print("✅ All key service classes available")
        
        # Test basic logger
        logger.info("🎯 Logger test: info level")
        logger.success("✅ Logger test: success level")
        logger.debug("🔍 Logger test: debug level")
        logger.warning("⚠️ Logger test: warning level")
        
        print("\n✅ All tests passed! Logging is properly integrated.")
        return 0
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
