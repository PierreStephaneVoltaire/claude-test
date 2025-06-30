#!/usr/bin/env python3
"""
Jenkins History CLI Tool

A command-line tool to interact with Jenkins instances and retrieve job information.
Supports listing jobs in workspaces and displaying build history.
"""

import argparse
import sys
import requests
from requests.auth import HTTPBasicAuth
from datetime import datetime
from typing import List, Dict, Any, Optional


class JenkinsClient:
    """Jenkins API client for making authenticated requests."""
    
    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url.rstrip('/')
        self.auth = HTTPBasicAuth(username, password)
        self.session = requests.Session()
        self.session.auth = self.auth
    
    def get(self, endpoint: str) -> Dict[Any, Any]:
        """Make GET request to Jenkins API endpoint."""
        url = f"{self.base_url}{endpoint}"
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error making request to {url}: {e}")
            sys.exit(1)
        except ValueError as e:
            print(f"Error parsing JSON response: {e}")
            sys.exit(1)


class JenkinsHistoryCLI:
    """Main CLI application class."""
    
    def __init__(self):
        # Hardcoded Jenkins configuration
        self.jenkins_url = "http://localhost:8080"  # Change this to your Jenkins URL
        self.username = "admin"  # Change this to your Jenkins username
        self.password = "admin"  # Change this to your Jenkins password
        
        self.client = JenkinsClient(self.jenkins_url, self.username, self.password)
    
    def list_jobs(self, workspace: str) -> None:
        """List all jobs under a specific workspace."""
        workspace = workspace.strip('/')
        endpoint = f"/job/{workspace}/api/json?tree=jobs[name,url,color]"
        
        try:
            data = self.client.get(endpoint)
            jobs = data.get('jobs', [])
            
            if not jobs:
                print(f"No jobs found in workspace: /{workspace}")
                return
            
            print(f"\nJobs in workspace /{workspace}:")
            print("-" * 60)
            print(f"{'Job Name':<40} {'Status':<15}")
            print("-" * 60)
            
            for job in jobs:
                name = job.get('name', 'Unknown')
                color = job.get('color', 'unknown')
                status = self._color_to_status(color)
                print(f"{name:<40} {status:<15}")
            
            print(f"\nTotal jobs: {len(jobs)}")
            
        except Exception as e:
            print(f"Error listing jobs in workspace /{workspace}: {e}")
            sys.exit(1)
    
    def job_history(self, job_path: str) -> None:
        """Show build history for a specific job."""
        job_path = job_path.strip('/')
        
        # Get job info first
        job_endpoint = f"/job/{job_path.replace('/', '/job/')}/api/json?tree=builds[number,url]"
        
        try:
            job_data = self.client.get(job_endpoint)
            builds = job_data.get('builds', [])
            
            if not builds:
                print(f"No build history found for job: {job_path}")
                return
            
            print(f"\nBuild history for job: {job_path}")
            print("-" * 120)
            print(f"{'Build#':<8} {'Status':<12} {'Triggered By':<20} {'Timestamp':<20} {'Parameters':<30}")
            print("-" * 120)
            
            # Get details for each build (limit to last 20 builds)
            for build in builds[:20]:
                build_number = build.get('number')
                self._display_build_details(job_path, build_number)
            
            if len(builds) > 20:
                print(f"\n... and {len(builds) - 20} more builds (showing last 20)")
            
        except Exception as e:
            print(f"Error getting build history for job {job_path}: {e}")
            sys.exit(1)
    
    def _display_build_details(self, job_path: str, build_number: int) -> None:
        """Display details for a specific build."""
        build_endpoint = f"/job/{job_path.replace('/', '/job/')}/{build_number}/api/json"
        
        try:
            build_data = self.client.get(build_endpoint)
            
            # Extract build information
            result = build_data.get('result', 'UNKNOWN')
            timestamp = build_data.get('timestamp', 0)
            duration = build_data.get('duration', 0)
            
            # Get who triggered the build
            causes = build_data.get('actions', [])
            triggered_by = self._extract_trigger_info(causes)
            
            # Get build parameters
            parameters = self._extract_parameters(build_data.get('actions', []))
            
            # Format timestamp
            if timestamp:
                build_time = datetime.fromtimestamp(timestamp / 1000).strftime('%Y-%m-%d %H:%M:%S')
            else:
                build_time = "Unknown"
            
            # Format parameters for display
            params_str = self._format_parameters(parameters)
            
            print(f"{build_number:<8} {result:<12} {triggered_by:<20} {build_time:<20} {params_str:<30}")
            
        except Exception as e:
            print(f"Error getting details for build #{build_number}: {e}")
    
    def _color_to_status(self, color: str) -> str:
        """Convert Jenkins color code to readable status."""
        color_map = {
            'blue': 'SUCCESS',
            'red': 'FAILURE',
            'yellow': 'UNSTABLE',
            'grey': 'NOT_BUILT',
            'disabled': 'DISABLED',
            'aborted': 'ABORTED',
            'blue_anime': 'BUILDING',
            'red_anime': 'BUILDING',
            'yellow_anime': 'BUILDING'
        }
        return color_map.get(color, 'UNKNOWN')
    
    def _extract_trigger_info(self, actions: List[Dict]) -> str:
        """Extract who/what triggered the build."""
        for action in actions:
            if action.get('_class') == 'hudson.model.CauseAction':
                causes = action.get('causes', [])
                for cause in causes:
                    if 'userId' in cause:
                        return cause.get('userId', 'Unknown User')
                    elif 'shortDescription' in cause:
                        desc = cause.get('shortDescription', '')
                        if 'Started by user' in desc:
                            return desc.replace('Started by user ', '')
                        elif 'Started by' in desc:
                            return desc.replace('Started by ', '')
                        return 'SCM/Timer'
        return 'Unknown'
    
    def _extract_parameters(self, actions: List[Dict]) -> Dict[str, str]:
        """Extract build parameters."""
        parameters = {}
        for action in actions:
            if action.get('_class') == 'hudson.model.ParametersAction':
                params = action.get('parameters', [])
                for param in params:
                    name = param.get('name', '')
                    value = param.get('value', '')
                    if name and value:
                        parameters[name] = str(value)
        return parameters
    
    def _format_parameters(self, parameters: Dict[str, str]) -> str:
        """Format parameters for display."""
        if not parameters:
            return "None"
        
        param_strs = [f"{k}={v}" for k, v in parameters.items()]
        result = ", ".join(param_strs)
        
        # Truncate if too long
        if len(result) > 25:
            return result[:22] + "..."
        
        return result


def main():
    """Main entry point for the CLI application."""
    parser = argparse.ArgumentParser(
        description="Jenkins History CLI Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python jenkins-history.py list-jobs --workspace dev
  python jenkins-history.py job-history --job-path dev/my-project/main
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # list-jobs command
    list_parser = subparsers.add_parser('list-jobs', help='List jobs in a workspace')
    list_parser.add_argument(
        '--workspace',
        required=True,
        help='Workspace name (e.g., dev, prod)'
    )
    
    # job-history command
    history_parser = subparsers.add_parser('job-history', help='Show build history for a job')
    history_parser.add_argument(
        '--job-path',
        required=True,
        help='Full job path (e.g., dev/my-project/main)'
    )
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Initialize CLI application
    cli = JenkinsHistoryCLI()
    
    # Execute command
    try:
        if args.command == 'list-jobs':
            cli.list_jobs(args.workspace)
        elif args.command == 'job-history':
            cli.job_history(args.job_path)
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()