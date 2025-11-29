"""
D76-4: Incident Simulation CLI Script

This script executes 12+ incident simulations to validate
the D75/D76 alerting infrastructure end-to-end.

Usage:
    python scripts/run_d76_4_incident_simulation.py --env production
    python scripts/run_d76_4_incident_simulation.py --env development --incidents all
    python scripts/run_d76_4_incident_simulation.py --env production --incidents redis,latency
"""

import os
import sys
import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from arbitrage.alerting import AlertManager, RuleEngine, Environment
from arbitrage.alerting.simulation import get_all_incidents, IncidentResult


def setup_alert_manager(environment: Environment) -> AlertManager:
    """
    Set up AlertManager with RuleEngine for the specified environment
    
    Note: This is a simulation setup. No actual notifiers are registered
    to avoid sending real alerts during testing.
    """
    rule_engine = RuleEngine(environment=environment)
    manager = AlertManager(rule_engine=rule_engine)
    
    # Note: We intentionally do NOT register notifiers here
    # This ensures alerts are evaluated by RuleEngine but not actually sent
    # Storage can be optionally registered for verification
    
    print(f"✓ AlertManager initialized for environment: {environment.value}")
    print(f"✓ RuleEngine configured with Telegram-first policy")
    print(f"✓ Notifiers: NONE (simulation mode)")
    print()
    
    return manager


def run_incident(
    name: str,
    incident_func,
    manager: AlertManager,
    environment: Environment,
) -> Dict[str, Any]:
    """Run a single incident simulation and return results"""
    print(f"Running: {name}...")
    
    try:
        result: IncidentResult = incident_func(manager, environment)
        
        # Validate dispatch plan against Telegram-first policy
        validation = validate_dispatch_plan(result, environment)
        
        print(f"  ✓ Rule ID: {result.rule_id}")
        print(f"  ✓ Severity: {result.severity.value}")
        print(f"  ✓ Dispatch Plan: Telegram={result.dispatch_plan.telegram}, "
              f"Slack={result.dispatch_plan.slack}, Email={result.dispatch_plan.email}, "
              f"PostgreSQL={result.dispatch_plan.postgres}")
        print(f"  ✓ Validation: {validation['status']}")
        if validation['status'] == 'FAIL':
            print(f"    ⚠️  Errors: {validation['errors']}")
        print()
        
        return {
            "name": name,
            "success": True,
            "result": result.to_dict(),
            "validation": validation,
        }
    
    except Exception as e:
        print(f"  ✗ ERROR: {str(e)}")
        print()
        return {
            "name": name,
            "success": False,
            "error": str(e),
        }


def validate_dispatch_plan(
    result: IncidentResult,
    environment: Environment,
) -> Dict[str, Any]:
    """
    Validate dispatch plan against Telegram-first policy
    
    Returns:
        {
            "status": "PASS" or "FAIL",
            "errors": [list of validation errors],
        }
    """
    errors = []
    severity = result.severity
    plan = result.dispatch_plan
    
    if environment == Environment.PROD:
        # PROD: Telegram-first policy
        if severity.value in ["P0", "P1"]:
            if not plan.telegram:
                errors.append(f"PROD {severity.value}: Expected Telegram=True")
            if not plan.postgres:
                errors.append(f"PROD {severity.value}: Expected PostgreSQL=True")
            if plan.slack:
                errors.append(f"PROD {severity.value}: Expected Slack=False")
            if plan.email:
                errors.append(f"PROD {severity.value}: Expected Email=False")
        
        elif severity.value == "P2":
            if not plan.postgres:
                errors.append(f"PROD P2: Expected PostgreSQL=True")
            # Telegram is opt-in, so we don't validate it
            if plan.slack:
                errors.append(f"PROD P2: Expected Slack=False")
            if plan.email:
                errors.append(f"PROD P2: Expected Email=False")
        
        elif severity.value == "P3":
            if not plan.postgres:
                errors.append(f"PROD P3: Expected PostgreSQL=True")
            if plan.telegram:
                errors.append(f"PROD P3: Expected Telegram=False")
            if plan.slack:
                errors.append(f"PROD P3: Expected Slack=False")
            if plan.email:
                errors.append(f"PROD P3: Expected Email=False (unless daily summary)")
    
    else:
        # DEV/TEST: All channels available
        if severity.value in ["P0", "P1"]:
            if not plan.telegram:
                errors.append(f"DEV {severity.value}: Expected Telegram=True")
            if not plan.slack:
                errors.append(f"DEV {severity.value}: Expected Slack=True")
            if not plan.postgres:
                errors.append(f"DEV {severity.value}: Expected PostgreSQL=True")
        
        elif severity.value == "P2":
            if not plan.telegram:
                errors.append(f"DEV P2: Expected Telegram=True")
            if not plan.slack:
                errors.append(f"DEV P2: Expected Slack=True")
            if not plan.email:
                errors.append(f"DEV P2: Expected Email=True")
            if not plan.postgres:
                errors.append(f"DEV P2: Expected PostgreSQL=True")
        
        elif severity.value == "P3":
            if not plan.email:
                errors.append(f"DEV P3: Expected Email=True")
            if not plan.postgres:
                errors.append(f"DEV P3: Expected PostgreSQL=True")
    
    return {
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
    }


def print_summary(results: List[Dict[str, Any]], environment: Environment):
    """Print execution summary"""
    total = len(results)
    success = sum(1 for r in results if r["success"])
    failed = total - success
    
    # Count validation results
    validation_pass = sum(
        1 for r in results 
        if r["success"] and r.get("validation", {}).get("status") == "PASS"
    )
    validation_fail = sum(
        1 for r in results 
        if r["success"] and r.get("validation", {}).get("status") == "FAIL"
    )
    
    print("=" * 80)
    print("INCIDENT SIMULATION SUMMARY")
    print("=" * 80)
    print(f"Environment: {environment.value}")
    print(f"Total Incidents: {total}")
    print(f"Successful Executions: {success}")
    print(f"Failed Executions: {failed}")
    print(f"Validation PASS: {validation_pass}")
    print(f"Validation FAIL: {validation_fail}")
    print()
    
    if validation_fail > 0:
        print("⚠️  VALIDATION FAILURES DETECTED:")
        for result in results:
            if result["success"] and result.get("validation", {}).get("status") == "FAIL":
                print(f"  - {result['name']}")
                for error in result["validation"]["errors"]:
                    print(f"      {error}")
        print()
    
    # Severity breakdown
    severity_counts = {"P0": 0, "P1": 0, "P2": 0, "P3": 0}
    for result in results:
        if result["success"]:
            severity = result["result"]["severity"]
            severity_counts[severity] += 1
    
    print("Severity Breakdown:")
    for sev, count in severity_counts.items():
        print(f"  {sev}: {count} incidents")
    print()
    
    # Channel routing summary
    if success > 0:
        telegram_count = sum(
            1 for r in results 
            if r["success"] and r["result"]["dispatch_plan"]["telegram"]
        )
        slack_count = sum(
            1 for r in results 
            if r["success"] and r["result"]["dispatch_plan"]["slack"]
        )
        email_count = sum(
            1 for r in results 
            if r["success"] and r["result"]["dispatch_plan"]["email"]
        )
        postgres_count = sum(
            1 for r in results 
            if r["success"] and r["result"]["dispatch_plan"]["postgres"]
        )
        
        print("Channel Routing Summary:")
        print(f"  Telegram: {telegram_count}/{success} ({telegram_count*100//success}%)")
        print(f"  Slack: {slack_count}/{success} ({slack_count*100//success}%)")
        print(f"  Email: {email_count}/{success} ({email_count*100//success}%)")
        print(f"  PostgreSQL: {postgres_count}/{success} ({postgres_count*100//success}%)")
        print()
    
    print("=" * 80)
    
    # Final status
    if failed == 0 and validation_fail == 0:
        print("✅ ALL INCIDENTS PASSED")
    else:
        print("❌ SOME INCIDENTS FAILED")
    
    return failed == 0 and validation_fail == 0


def save_results(results: List[Dict[str, Any]], output_file: str):
    """Save results to JSON file"""
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "results": results,
        }, f, indent=2, ensure_ascii=False)
    print(f"✓ Results saved to: {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description="D76-4 Incident Simulation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--env",
        type=str,
        choices=["production", "development", "test", "staging"],
        default="production",
        help="Target environment for simulation (default: production)",
    )
    parser.add_argument(
        "--incidents",
        type=str,
        default="all",
        help="Comma-separated incident names to run, or 'all' (default: all)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="incident_simulation_results.json",
        help="Output JSON file for results (default: incident_simulation_results.json)",
    )
    
    args = parser.parse_args()
    
    # Map environment string to enum
    env_map = {
        "production": Environment.PROD,
        "development": Environment.DEV,
        "test": Environment.TEST,
        "staging": Environment.STAGING,
    }
    environment = env_map[args.env]
    
    # Get all incidents
    all_incidents = get_all_incidents()
    
    # Filter incidents if specified
    if args.incidents != "all":
        requested = [name.strip().lower() for name in args.incidents.split(",")]
        all_incidents = [
            (name, func) for name, func in all_incidents
            if any(req in name.lower() for req in requested)
        ]
    
    if not all_incidents:
        print("❌ No incidents matched the filter criteria")
        sys.exit(1)
    
    # Print header
    print("=" * 80)
    print("D76-4: INCIDENT SIMULATION")
    print("=" * 80)
    print(f"Environment: {environment.value}")
    print(f"Incidents to run: {len(all_incidents)}")
    print(f"Output file: {args.output}")
    print("=" * 80)
    print()
    
    # Set up alert manager
    manager = setup_alert_manager(environment)
    
    # Run all incidents
    results = []
    for name, incident_func in all_incidents:
        result = run_incident(name, incident_func, manager, environment)
        results.append(result)
    
    # Print summary
    all_passed = print_summary(results, environment)
    
    # Save results
    save_results(results, args.output)
    
    # Exit with appropriate code
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
