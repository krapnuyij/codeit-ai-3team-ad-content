#!/usr/bin/env python3
"""
Test script to validate the synthesizer fix
Tests that the AttributeError is resolved
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent))

from src import ObjectSynthesizer

print("=" * 60)
print("Testing ObjectSynthesizer initialization...")
print("=" * 60)

# Test 1: Initialize with enable_ip_adapter=True
print("\nTest 1: Initialize ObjectSynthesizer with IP-Adapter enabled")
synthesizer = ObjectSynthesizer(enable_ip_adapter=True)
print("✓ ObjectSynthesizer initialized successfully")

# Test 2: Try to load model with IP-Adapter (should show warning)
print("\nTest 2: Load FluxFillPipeline with IP-Adapter request")
print("Expected: Warning message that FluxFillPipeline doesn't support IP-Adapter")
print("-" * 60)
synthesizer._load_model(with_ip_adapter=True)
print("-" * 60)
print("✓ No AttributeError raised!")

# Test 3: Cleanup
print("\nTest 3: Cleanup")
synthesizer._unload_model()
print("✓ Model unloaded successfully")

print("\n" + "=" * 60)
print("All tests passed! The AttributeError is fixed.")
print("=" * 60)
print("\nSummary:")
print("  - FluxFillPipeline no longer tries to load IP-Adapter")
print("  - Warning message is displayed instead")
print("  - To use IP-Adapter, set use_two_stage=True")
print("=" * 60)
