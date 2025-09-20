#!/usr/bin/env python3
"""
CARLA Scenario Cycling Script
Automatically runs all converted scenarios in CARLA ScenarioRunner
"""

import os
import subprocess
import glob
import time
import json
import argparse
from pathlib import Path
import signal
import sys

class ScenarioCycler:
    def __init__(self, scenario_dir="converted_rebuilt_scenarios", carla_root="/opt/carla-simulator", 
                 scenario_runner_root="../scenario_runner"):
        self.scenario_dir = scenario_dir
        self.carla_root = carla_root
        self.scenario_runner_root = scenario_runner_root
        self.current_process = None
        self.results = []
        self.start_time = None
        
        # Setup signal handler for clean exit
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def signal_handler(self, signum, frame):
        """Handle Ctrl+C gracefully"""
        print(f"\n🛑 Received signal {signum}, stopping current scenario...")
        if self.current_process:
            self.current_process.terminate()
            try:
                self.current_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.current_process.kill()
        self.save_results()
        sys.exit(0)
    
    def find_scenarios(self):
        """Find all XOSC files in the scenario directory"""
        pattern = os.path.join(self.scenario_dir, "*.xosc")
        scenarios = glob.glob(pattern)
        scenarios.sort()  # Sort for consistent ordering
        return scenarios
    
    def check_carla_server(self):
        """Check if CARLA server is running"""
        try:
            result = subprocess.run(['pgrep', '-f', 'CarlaUE4'], 
                                  capture_output=True, text=True, timeout=5)
            return len(result.stdout.strip()) > 0
        except:
            return False
    
    def start_carla_server(self):
        """Start CARLA server if not running"""
        if not self.check_carla_server():
            print("🚗 Starting CARLA server...")
            carla_cmd = [
                os.path.join(self.carla_root, "CarlaUE4.sh"),
                "-RenderOffScreen",  # No graphics for faster execution
                "-nosound",
                "-benchmark",
                "-fps=20"
            ]
            
            try:
                self.carla_process = subprocess.Popen(
                    carla_cmd, 
                    stdout=subprocess.DEVNULL, 
                    stderr=subprocess.DEVNULL
                )
                print("⏳ Waiting for CARLA server to initialize...")
                time.sleep(15)  # Give CARLA time to start
                
                if self.check_carla_server():
                    print("✅ CARLA server started successfully")
                    return True
                else:
                    print("❌ Failed to start CARLA server")
                    return False
            except Exception as e:
                print(f"❌ Error starting CARLA server: {e}")
                return False
        else:
            print("✅ CARLA server already running")
            return True
    
    def run_scenario(self, scenario_path, timeout=120):
        """Run a single scenario using ScenarioRunner"""
        scenario_name = Path(scenario_path).stem
        
        print(f"\n🎬 Running scenario: {scenario_name}")
        print(f"📁 File: {scenario_path}")
        
        # Build ScenarioRunner command
        cmd = [
            "python3",
            os.path.join(self.scenario_runner_root, "scenario_runner.py"),
            "--openscenario", scenario_path,
            "--host", "127.0.0.1",
            "--port", "2000",
            "--timeout", str(timeout),
            "--output",
            "--file",
            "--junit"
        ]
        
        start_time = time.time()
        
        try:
            print("⏳ Starting scenario execution...")
            self.current_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=self.scenario_runner_root
            )
            
            # Wait for process to complete
            stdout, stderr = self.current_process.communicate(timeout=timeout + 10)
            end_time = time.time()
            execution_time = end_time - start_time
            
            # Analyze results
            result = self.analyze_scenario_result(
                scenario_name, self.current_process.returncode, 
                stdout, stderr, execution_time
            )
            
            self.results.append(result)
            self.print_scenario_result(result)
            
            return result
            
        except subprocess.TimeoutExpired:
            print("⏰ Scenario timed out")
            self.current_process.kill()
            result = {
                'scenario': scenario_name,
                'status': 'TIMEOUT',
                'execution_time': timeout,
                'error': 'Execution timed out'
            }
            self.results.append(result)
            return result
            
        except Exception as e:
            print(f"❌ Error running scenario: {e}")
            result = {
                'scenario': scenario_name,
                'status': 'ERROR',
                'execution_time': 0,
                'error': str(e)
            }
            self.results.append(result)
            return result
        finally:
            self.current_process = None
    
    def analyze_scenario_result(self, scenario_name, return_code, stdout, stderr, execution_time):
        """Analyze scenario execution results"""
        
        # Determine status based on return code and output
        if return_code == 0:
            status = 'SUCCESS'
        elif return_code == 1:
            status = 'FAILED'
        else:
            status = 'ERROR'
        
        # Extract key information from output
        collision_detected = 'collision' in stdout.lower() or 'collision' in stderr.lower()
        timeout_reached = 'timeout' in stdout.lower() or 'timeout' in stderr.lower()
        distance_completed = self.extract_distance(stdout)
        
        # Check for specific error patterns
        error_msg = ""
        if "Unable to add actors" in stderr:
            error_msg = "Actor spawn failure"
        elif "AssertionError" in stderr:
            error_msg = "ScenarioRunner assertion error"
        elif "segmentation fault" in stderr.lower():
            error_msg = "Segmentation fault"
        elif stderr and len(stderr.strip()) > 0:
            error_msg = stderr.strip()[:200]  # First 200 chars of stderr
        
        return {
            'scenario': scenario_name,
            'status': status,
            'execution_time': round(execution_time, 2),
            'return_code': return_code,
            'collision_detected': collision_detected,
            'timeout_reached': timeout_reached,
            'distance_completed': distance_completed,
            'error': error_msg,
            'stdout_snippet': stdout[:500] if stdout else "",
            'stderr_snippet': stderr[:500] if stderr else ""
        }
    
    def extract_distance(self, output):
        """Extract completed distance from scenario output"""
        try:
            # Look for distance patterns in output
            import re
            distance_patterns = [
                r'distance[:\s]+(\d+\.?\d*)',
                r'traveled[:\s]+(\d+\.?\d*)',
                r'completed[:\s]+(\d+\.?\d*)'
            ]
            
            for pattern in distance_patterns:
                matches = re.findall(pattern, output, re.IGNORECASE)
                if matches:
                    return float(matches[-1])  # Return last match
            return None
        except:
            return None
    
    def print_scenario_result(self, result):
        """Print formatted result for a single scenario"""
        status_emoji = {
            'SUCCESS': '✅',
            'FAILED': '❌', 
            'ERROR': '💥',
            'TIMEOUT': '⏰'
        }
        
        emoji = status_emoji.get(result['status'], '❓')
        print(f"{emoji} {result['status']} - {result['execution_time']}s")
        
        if result['collision_detected']:
            print("   ⚠️  Collision detected")
        if result['distance_completed']:
            print(f"   📏 Distance: {result['distance_completed']}m")
        if result['error']:
            print(f"   🐛 Error: {result['error']}")
    
    def print_summary(self):
        """Print execution summary"""
        if not self.results:
            return
        
        total = len(self.results)
        success = len([r for r in self.results if r['status'] == 'SUCCESS'])
        failed = len([r for r in self.results if r['status'] == 'FAILED'])
        errors = len([r for r in self.results if r['status'] == 'ERROR'])
        timeouts = len([r for r in self.results if r['status'] == 'TIMEOUT'])
        
        total_time = sum([r['execution_time'] for r in self.results])
        avg_time = total_time / total if total > 0 else 0
        
        print("\n" + "="*60)
        print("SCENARIO EXECUTION SUMMARY")
        print("="*60)
        print(f"📊 Total scenarios: {total}")
        print(f"✅ Successful: {success} ({success/total*100:.1f}%)")
        print(f"❌ Failed: {failed} ({failed/total*100:.1f}%)")
        print(f"💥 Errors: {errors} ({errors/total*100:.1f}%)")
        print(f"⏰ Timeouts: {timeouts} ({timeouts/total*100:.1f}%)")
        print(f"⏱️  Total time: {total_time:.1f}s ({total_time/60:.1f} minutes)")
        print(f"📈 Average time per scenario: {avg_time:.1f}s")
        
        # Show problematic scenarios
        problematic = [r for r in self.results if r['status'] != 'SUCCESS']
        if problematic:
            print(f"\n⚠️  Problematic scenarios ({len(problematic)}):")
            for result in problematic[:10]:  # Show first 10
                print(f"   {result['scenario']}: {result['status']} - {result['error']}")
            if len(problematic) > 10:
                print(f"   ... and {len(problematic) - 10} more")
    
    def save_results(self):
        """Save results to JSON file"""
        if self.results:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"scenario_results_{timestamp}.json"
            
            with open(filename, 'w') as f:
                json.dump({
                    'summary': {
                        'total_scenarios': len(self.results),
                        'execution_time': time.time() - self.start_time if self.start_time else 0,
                        'success_rate': len([r for r in self.results if r['status'] == 'SUCCESS']) / len(self.results) * 100
                    },
                    'results': self.results
                }, f, indent=2)
            
            print(f"💾 Results saved to: {filename}")
    
    def run_all_scenarios(self, start_from=None, max_scenarios=None, timeout=120):
        """Run all scenarios in the directory"""
        scenarios = self.find_scenarios()
        
        if not scenarios:
            print(f"❌ No scenarios found in {self.scenario_dir}")
            return
        
        print(f"🎯 Found {len(scenarios)} scenarios to run")
        
        # Filter scenarios if start_from specified
        if start_from:
            start_idx = 0
            for i, scenario in enumerate(scenarios):
                if start_from in Path(scenario).stem:
                    start_idx = i
                    break
            scenarios = scenarios[start_idx:]
            print(f"📍 Starting from scenario {start_idx + 1}: {Path(scenarios[0]).stem}")
        
        # Limit number of scenarios if specified
        if max_scenarios:
            scenarios = scenarios[:max_scenarios]
            print(f"🔢 Limited to first {max_scenarios} scenarios")
        
        # Start CARLA server
        if not self.start_carla_server():
            print("❌ Cannot start CARLA server. Exiting.")
            return
        
        self.start_time = time.time()
        
        print(f"\n🚀 Starting scenario execution cycle...")
        print(f"⏰ Timeout per scenario: {timeout}s")
        print(f"🛑 Press Ctrl+C to stop at any time")
        
        try:
            for i, scenario_path in enumerate(scenarios, 1):
                print(f"\n{'='*60}")
                print(f"[{i:3d}/{len(scenarios):3d}] SCENARIO BATCH PROGRESS")
                
                self.run_scenario(scenario_path, timeout)
                
                # Small delay between scenarios
                time.sleep(2)
                
            self.print_summary()
            self.save_results()
            
        except KeyboardInterrupt:
            print(f"\n🛑 Execution stopped by user")
            self.print_summary()
            self.save_results()

def main():
    parser = argparse.ArgumentParser(description="Cycle through CARLA scenarios")
    parser.add_argument("--scenario-dir", default="converted_rebuilt_scenarios",
                       help="Directory containing XOSC files")
    parser.add_argument("--carla-root", default="/opt/carla-simulator", 
                       help="CARLA installation directory")
    parser.add_argument("--scenario-runner", default="../scenario_runner",
                       help="ScenarioRunner directory")
    parser.add_argument("--start-from", help="Start from specific scenario name")
    parser.add_argument("--max-scenarios", type=int, help="Maximum number of scenarios to run")
    parser.add_argument("--timeout", type=int, default=120, help="Timeout per scenario in seconds")
    parser.add_argument("--check-only", action="store_true", help="Only check setup, don't run scenarios")
    
    args = parser.parse_args()
    
    cycler = ScenarioCycler(
        scenario_dir=args.scenario_dir,
        carla_root=args.carla_root, 
        scenario_runner_root=args.scenario_runner
    )
    
    if args.check_only:
        print("🔍 Checking setup...")
        scenarios = cycler.find_scenarios()
        print(f"✅ Found {len(scenarios)} scenarios in {args.scenario_dir}")
        print(f"🚗 CARLA server running: {cycler.check_carla_server()}")
        return
    
    cycler.run_all_scenarios(
        start_from=args.start_from,
        max_scenarios=args.max_scenarios,
        timeout=args.timeout
    )

if __name__ == "__main__":
    main()