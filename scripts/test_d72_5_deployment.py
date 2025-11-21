#!/usr/bin/env python3
"""
D72-5 Deployment Infrastructure Tests
Tests Docker build, compose orchestration, and systemd configuration
"""

import os
import sys
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Tuple

# Colors for output
RED = '\033[0;31m'
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
NC = '\033[0m'  # No Color

# Configuration
PROJECT_ROOT = Path(__file__).parent.parent
DOCKER_DIR = PROJECT_ROOT / "docker"
SYSTEMD_DIR = PROJECT_ROOT / "systemd"
DOCKERFILE_PATH = DOCKER_DIR / "Dockerfile"
COMPOSE_PATH = DOCKER_DIR / "docker-compose.yml"
ENTRYPOINT_PATH = DOCKER_DIR / "entrypoint.sh"
SYSTEMD_SERVICE_PATH = SYSTEMD_DIR / "arbitrage.service"

class TestResult:
    """Test result container"""
    def __init__(self, name: str, passed: bool, message: str = ""):
        self.name = name
        self.passed = passed
        self.message = message
    
    def __str__(self) -> str:
        status = f"{GREEN}PASS{NC}" if self.passed else f"{RED}FAIL{NC}"
        msg = f": {self.message}" if self.message else ""
        return f"[{status}] {self.name}{msg}"


def run_command(cmd: List[str], cwd: Path = None, timeout: int = 60) -> Tuple[int, str, str]:
    """Run shell command and return exit code, stdout, stderr"""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd or PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Command timed out"
    except Exception as e:
        return -1, "", str(e)


def test_dockerfile_exists() -> TestResult:
    """Test 1: Dockerfile exists"""
    if DOCKERFILE_PATH.exists():
        return TestResult("Dockerfile exists", True)
    else:
        return TestResult("Dockerfile exists", False, f"Not found at {DOCKERFILE_PATH}")


def test_dockerfile_syntax() -> TestResult:
    """Test 2: Dockerfile has valid syntax"""
    if not DOCKERFILE_PATH.exists():
        return TestResult("Dockerfile syntax", False, "File not found")
    
    try:
        with open(DOCKERFILE_PATH, 'r') as f:
            content = f.read()
        
        # Basic syntax checks
        required_keywords = ['FROM', 'WORKDIR', 'COPY', 'RUN', 'HEALTHCHECK']
        missing = [kw for kw in required_keywords if kw not in content]
        
        if missing:
            return TestResult("Dockerfile syntax", False, f"Missing keywords: {missing}")
        
        # Check for multi-stage build
        if content.count('FROM') < 2:
            return TestResult("Dockerfile syntax", False, "Multi-stage build not detected")
        
        return TestResult("Dockerfile syntax", True, "Valid multi-stage Dockerfile")
        
    except Exception as e:
        return TestResult("Dockerfile syntax", False, str(e))


def test_docker_compose_exists() -> TestResult:
    """Test 3: docker-compose.yml exists"""
    if COMPOSE_PATH.exists():
        return TestResult("docker-compose.yml exists", True)
    else:
        return TestResult("docker-compose.yml exists", False, f"Not found at {COMPOSE_PATH}")


def test_docker_compose_syntax() -> TestResult:
    """Test 4: docker-compose.yml has valid syntax"""
    if not COMPOSE_PATH.exists():
        return TestResult("docker-compose.yml syntax", False, "File not found")
    
    # Use docker-compose config to validate
    returncode, stdout, stderr = run_command(
        ['docker-compose', '-f', str(COMPOSE_PATH), 'config'],
        timeout=30
    )
    
    if returncode == 0:
        return TestResult("docker-compose.yml syntax", True, "Valid YAML")
    else:
        return TestResult("docker-compose.yml syntax", False, f"Invalid: {stderr}")


def test_docker_compose_services() -> TestResult:
    """Test 5: docker-compose.yml has required services"""
    if not COMPOSE_PATH.exists():
        return TestResult("docker-compose services", False, "File not found")
    
    try:
        import yaml
        with open(COMPOSE_PATH, 'r') as f:
            compose_data = yaml.safe_load(f)
        
        required_services = ['redis', 'postgres', 'arbitrage-engine']
        services = compose_data.get('services', {})
        
        missing = [svc for svc in required_services if svc not in services]
        
        if missing:
            return TestResult("docker-compose services", False, f"Missing services: {missing}")
        
        return TestResult("docker-compose services", True, f"All required services present: {required_services}")
        
    except Exception as e:
        return TestResult("docker-compose services", False, str(e))


def test_entrypoint_exists() -> TestResult:
    """Test 6: entrypoint.sh exists"""
    if ENTRYPOINT_PATH.exists():
        return TestResult("entrypoint.sh exists", True)
    else:
        return TestResult("entrypoint.sh exists", False, f"Not found at {ENTRYPOINT_PATH}")


def test_entrypoint_executable() -> TestResult:
    """Test 7: entrypoint.sh has shebang and functions"""
    if not ENTRYPOINT_PATH.exists():
        return TestResult("entrypoint.sh executable", False, "File not found")
    
    try:
        with open(ENTRYPOINT_PATH, 'r') as f:
            content = f.read()
        
        # Check shebang
        if not content.startswith('#!'):
            return TestResult("entrypoint.sh executable", False, "Missing shebang")
        
        # Check required functions
        required_functions = ['wait_for_redis', 'wait_for_postgres', 'shutdown_handler']
        missing = [fn for fn in required_functions if fn not in content]
        
        if missing:
            return TestResult("entrypoint.sh executable", False, f"Missing functions: {missing}")
        
        return TestResult("entrypoint.sh executable", True, "Valid entrypoint script")
        
    except Exception as e:
        return TestResult("entrypoint.sh executable", False, str(e))


def test_systemd_service_exists() -> TestResult:
    """Test 8: systemd service file exists"""
    if SYSTEMD_SERVICE_PATH.exists():
        return TestResult("systemd service exists", True)
    else:
        return TestResult("systemd service exists", False, f"Not found at {SYSTEMD_SERVICE_PATH}")


def test_systemd_service_syntax() -> TestResult:
    """Test 9: systemd service file has valid syntax"""
    if not SYSTEMD_SERVICE_PATH.exists():
        return TestResult("systemd service syntax", False, "File not found")
    
    try:
        with open(SYSTEMD_SERVICE_PATH, 'r') as f:
            content = f.read()
        
        # Check required sections
        required_sections = ['[Unit]', '[Service]', '[Install]']
        missing = [sec for sec in required_sections if sec not in content]
        
        if missing:
            return TestResult("systemd service syntax", False, f"Missing sections: {missing}")
        
        # Check required directives
        required_directives = ['Type=', 'ExecStart=', 'Restart=', 'WantedBy=']
        missing_dirs = [d for d in required_directives if d not in content]
        
        if missing_dirs:
            return TestResult("systemd service syntax", False, f"Missing directives: {missing_dirs}")
        
        return TestResult("systemd service syntax", True, "Valid systemd unit file")
        
    except Exception as e:
        return TestResult("systemd service syntax", False, str(e))


def test_healthcheck_script() -> TestResult:
    """Test 10: healthcheck.py exists and is valid"""
    healthcheck_path = PROJECT_ROOT / "healthcheck.py"
    
    if not healthcheck_path.exists():
        return TestResult("healthcheck.py", False, "File not found")
    
    # Try to run syntax check
    returncode, stdout, stderr = run_command(
        [sys.executable, '-m', 'py_compile', str(healthcheck_path)],
        timeout=10
    )
    
    if returncode == 0:
        return TestResult("healthcheck.py", True, "Valid Python script")
    else:
        return TestResult("healthcheck.py", False, f"Syntax error: {stderr}")


def test_dockerignore_exists() -> TestResult:
    """Test 11: .dockerignore exists"""
    dockerignore_path = DOCKER_DIR / ".dockerignore"
    
    if dockerignore_path.exists():
        return TestResult(".dockerignore exists", True)
    else:
        return TestResult(".dockerignore exists", False, "Not found")


def test_run_engine_script() -> TestResult:
    """Test 12: run_engine.sh exists"""
    run_engine_path = PROJECT_ROOT / "scripts" / "run_engine.sh"
    
    if run_engine_path.exists():
        return TestResult("run_engine.sh exists", True)
    else:
        return TestResult("run_engine.sh exists", False, "Not found")


def print_header(text: str):
    """Print test section header"""
    print(f"\n{BLUE}{'=' * 70}{NC}")
    print(f"{BLUE}{text:^70}{NC}")
    print(f"{BLUE}{'=' * 70}{NC}\n")


def main():
    """Run all tests"""
    print_header("D72-5 Deployment Infrastructure Tests")
    
    # Define all tests
    tests = [
        test_dockerfile_exists,
        test_dockerfile_syntax,
        test_docker_compose_exists,
        test_docker_compose_syntax,
        test_docker_compose_services,
        test_entrypoint_exists,
        test_entrypoint_executable,
        test_systemd_service_exists,
        test_systemd_service_syntax,
        test_healthcheck_script,
        test_dockerignore_exists,
        test_run_engine_script,
    ]
    
    # Run tests
    results: List[TestResult] = []
    for i, test_func in enumerate(tests, 1):
        print(f"{YELLOW}[{i}/{len(tests)}]{NC} Running {test_func.__name__}...")
        result = test_func()
        results.append(result)
        print(result)
        time.sleep(0.1)  # Brief pause for readability
    
    # Summary
    print_header("Test Summary")
    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed)
    total = len(results)
    
    print(f"Total Tests: {total}")
    print(f"{GREEN}Passed: {passed}{NC}")
    print(f"{RED}Failed: {failed}{NC}")
    print(f"Success Rate: {passed/total*100:.1f}%")
    
    if failed > 0:
        print(f"\n{RED}❌ SOME TESTS FAILED{NC}")
        print("\nFailed tests:")
        for r in results:
            if not r.passed:
                print(f"  - {r.name}: {r.message}")
        return 1
    else:
        print(f"\n{GREEN}✅ ALL TESTS PASSED{NC}")
        return 0


if __name__ == '__main__':
    sys.exit(main())
