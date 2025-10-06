#!/usr/bin/env python3
"""
Test script to validate that the modular ECR simulator is ready for Windows build
Run this before building to catch any issues early
"""
import sys
import os
import importlib.util

def test_imports():
    """Test that all modules can be imported successfully"""
    print("Testing module imports...")
    
    modules_to_test = [
        'src.routes.ecr',
        'src.routes.ecr_core', 
        'src.routes.serial_comm',
        'src.routes.socket_comm',
        'src.routes.ecr_config',
        'src.routes.message_protocol'
    ]
    
    failed_imports = []
    
    for module_name in modules_to_test:
        try:
            # Convert module path to file path
            module_path = module_name.replace('.', os.sep) + '.py'
            
            if not os.path.exists(module_path):
                failed_imports.append(f"{module_name} - File not found: {module_path}")
                continue
                
            # Test import
            spec = importlib.util.spec_from_file_location(module_name, module_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            print(f"✓ {module_name}")
            
        except Exception as e:
            failed_imports.append(f"{module_name} - {str(e)}")
            print(f"✗ {module_name} - {str(e)}")
    
    return failed_imports

def test_flask_app():
    """Test that Flask application can be created"""
    print("\nTesting Flask application...")
    
    try:
        from src.main import app
        print("✓ Flask app created successfully")
        
        # Test that ECR blueprint is registered
        if 'ecr' in app.blueprints:
            print("✓ ECR blueprint registered")
        else:
            print("✗ ECR blueprint not registered")
            return False
            
        # Count routes
        with app.app_context():
            ecr_routes = [rule for rule in app.url_map.iter_rules() if 'ecr' in rule.endpoint]
            print(f"✓ Found {len(ecr_routes)} ECR routes")
            
        return True
        
    except Exception as e:
        print(f"✗ Flask app creation failed: {e}")
        return False

def test_core_functionality():
    """Test core module functionality"""
    print("\nTesting core functionality...")
    
    try:
        # Test EcrCore
        from src.routes.ecr_core import EcrCore
        ecr_core = EcrCore('src/routes')
        
        # Test LRC calculation
        test_data = b'\x02\x00\x03'
        lrc = ecr_core.calculate_lrc(test_data)
        print(f"✓ LRC calculation works: {lrc:02X}")
        
        # Test EcrConfig
        from src.routes.ecr_config import EcrConfig, EcrUtils
        config = EcrConfig('src/routes')
        
        # Test transaction mapping
        name = EcrUtils.get_transaction_name_from_code('01')
        if name == 'SALE':
            print("✓ Transaction mapping works")
        else:
            print(f"✗ Transaction mapping failed: expected SALE, got {name}")
            return False
            
        # Test SerialComm
        from src.routes.serial_comm import SerialComm, get_available_ports
        serial_comm = SerialComm(ecr_core)
        ports = get_available_ports()
        print(f"✓ Serial communication initialized, found {len(ports)} ports")
        
        # Test SocketComm
        from src.routes.socket_comm import SocketComm
        socket_comm = SocketComm()
        print("✓ Socket communication initialized")
        
        return True
        
    except Exception as e:
        print(f"✗ Core functionality test failed: {e}")
        return False

def test_build_requirements():
    """Test that all build requirements are present"""
    print("\nTesting build requirements...")
    
    required_files = [
        'src/main.py',
        'cimb_ecr.spec', 
        'build_requirements.txt',
        'requirements.txt',
        'src/static',
        'src/routes/__init__.py'
    ]
    
    missing_files = []
    
    for file_path in required_files:
        if not os.path.exists(file_path):
            missing_files.append(file_path)
            print(f"✗ Missing: {file_path}")
        else:
            print(f"✓ Found: {file_path}")
    
    return missing_files

def main():
    """Run all tests"""
    print("ECR Simulator Build Readiness Test")
    print("=" * 40)
    
    # Test imports
    failed_imports = test_imports()
    
    # Test Flask app
    flask_ok = test_flask_app()
    
    # Test core functionality 
    core_ok = test_core_functionality()
    
    # Test build requirements
    missing_files = test_build_requirements()
    
    # Summary
    print("\n" + "=" * 40)
    print("BUILD READINESS SUMMARY")
    print("=" * 40)
    
    all_good = True
    
    if failed_imports:
        print(f"✗ {len(failed_imports)} import failures:")
        for failure in failed_imports:
            print(f"  - {failure}")
        all_good = False
    else:
        print("✓ All modules import successfully")
    
    if not flask_ok:
        print("✗ Flask application issues")
        all_good = False
    else:
        print("✓ Flask application working")
    
    if not core_ok:
        print("✗ Core functionality issues")
        all_good = False
    else:
        print("✓ Core functionality working")
    
    if missing_files:
        print(f"✗ {len(missing_files)} missing build files:")
        for file in missing_files:
            print(f"  - {file}")
        all_good = False
    else:
        print("✓ All build files present")
    
    if all_good:
        print("\n🎉 READY FOR WINDOWS BUILD! 🎉")
        print("You can safely run build_windows.cmd")
        return 0
    else:
        print("\n⚠️  BUILD NOT READY")
        print("Please fix the issues above before building")
        return 1

if __name__ == '__main__':
    sys.exit(main())