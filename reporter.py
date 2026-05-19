"""Reporting and export functionality for rostering results."""

from datetime import datetime
from typing import Dict, List
import os
import json
import pandas as pd

from scheduler import Schedule
from constraints import ConstraintValidator


class Reporter:
    """Generates reports and exports schedule data."""

    def __init__(self, schedule: Schedule, validator: ConstraintValidator, config: Dict):
        """Initialize reporter.
        
        Args:
            schedule: Schedule object with assignments
            validator: ConstraintValidator for compliance checks
            config: Configuration dictionary
        """
        self.schedule = schedule
        self.validator = validator
        self.config = config
        self.reporting_config = config.get('reporting', {})

    def export_to_csv(self, output_dir: str = 'output') -> str:
        """Export rostered schedule to CSV file.
        
        Args:
            output_dir: Directory to save output
            
        Returns:
            Path to output file
        """
        os.makedirs(output_dir, exist_ok=True)
        
        df = self.schedule.to_dataframe()
        output_path = os.path.join(output_dir, 'rostered_schedule.csv')
        df.to_csv(output_path, index=False)
        
        return output_path

    def export_workload_to_csv(self, output_dir: str = 'output') -> str:
        """Export staff workload summary to CSV file.
        
        Args:
            output_dir: Directory to save output
            
        Returns:
            Path to output file
        """
        os.makedirs(output_dir, exist_ok=True)
        
        df = self.schedule.get_workload_summary()
        output_path = os.path.join(output_dir, 'staff_workload.csv')
        df.to_csv(output_path, index=False)
        
        return output_path

    def export_to_json(self, output_dir: str = 'output') -> str:
        """Export schedule to JSON format.
        
        Args:
            output_dir: Directory to save output
            
        Returns:
            Path to output file
        """
        os.makedirs(output_dir, exist_ok=True)
        
        schedule_data = []
        for vacancy in self.schedule.vacancies:
            schedule_data.append({
                'date': vacancy['date'].isoformat(),
                'day_of_week': vacancy['day_of_week'],
                'shift': vacancy['shift_type'],
                'role': vacancy['role'],
                'assigned_staff': vacancy['assigned_staff'],
                'hours': vacancy['hours']
            })
        
        output_path = os.path.join(output_dir, 'schedule.json')
        with open(output_path, 'w') as f:
            json.dump(schedule_data, f, indent=2)
        
        return output_path

    def generate_summary_report(self, output_dir: str = 'output',
                               optimization_results: Dict = None) -> str:
        """Generate comprehensive summary report.
        
        Args:
            output_dir: Directory to save output
            optimization_results: Results from optimizer
            
        Returns:
            Path to output file
        """
        os.makedirs(output_dir, exist_ok=True)
        
        report_lines = []
        report_lines.append("=" * 70)
        report_lines.append("AMBULANCE STATION RELIEF STAFF ROSTERING SUMMARY")
        report_lines.append("=" * 70)
        report_lines.append("")
        report_lines.append(f"Week: {self.schedule.week_start.date()} to {self.schedule.week_end.date()}")
        report_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append("")
        
        # Vacancy statistics
        report_lines.append("-" * 70)
        report_lines.append("VACANCY STATISTICS")
        report_lines.append("-" * 70)
        total = len(self.schedule.vacancies)
        assigned = self.schedule.get_assigned_count()
        unassigned = self.schedule.get_unassigned_count()
        success_rate = (assigned / total * 100) if total > 0 else 0
        
        report_lines.append(f"Total Vacancies: {total}")
        report_lines.append(f"Assigned: {assigned} ({success_rate:.1f}%)")
        report_lines.append(f"Unassigned: {unassigned}")
        report_lines.append(f"Total Hours Assigned: {self.schedule.get_total_hours_assigned():.1f}")
        report_lines.append("")
        
        # Staff workload
        report_lines.append("-" * 70)
        report_lines.append("STAFF WORKLOAD SUMMARY")
        report_lines.append("-" * 70)
        workload_df = self.schedule.get_workload_summary()
        report_lines.append(f"{'Staff ID':<20} {'Role':<12} {'Target':>7} {'Assigned':>8} {'Deviation':>9} {'Remaining':>9}")
        report_lines.append("-" * 70)
        
        for _, row in workload_df.iterrows():
            report_lines.append(
                f"{row['staff_id']:<20} {row['role']:<12} "
                f"{row['target_hours']:>7.1f} {row['assigned_hours']:>8.1f} "
                f"{row['deviation']:>+9.1f} {row['hours_remaining']:>9.1f}"
            )
        report_lines.append("")
        
        # Fairness metrics
        report_lines.append("-" * 70)
        report_lines.append("FAIRNESS METRICS")
        report_lines.append("-" * 70)
        
        deviations = workload_df['deviation'].abs().tolist()
        avg_deviation = sum(deviations) / len(deviations) if deviations else 0
        max_overload = workload_df['deviation'].max()
        max_underload = workload_df['deviation'].min()
        
        report_lines.append(f"Average Deviation: {avg_deviation:.2f} hours")
        report_lines.append(f"Most Overloaded: {max_overload:+.1f}h")
        report_lines.append(f"Most Underloaded: {max_underload:+.1f}h")
        report_lines.append("")
        
        # Compliance check
        if self.reporting_config.get('include_compliance_check', True):
            report_lines.append("-" * 70)
            report_lines.append("COMPLIANCE CHECK")
            report_lines.append("-" * 70)
            
            violations = self.validator.validate_final_schedule(self.schedule.assignments)
            if violations:
                for violation in violations:
                    report_lines.append(f"✗ {violation}")
            else:
                report_lines.append("✓ All rest periods respected")
                report_lines.append("✓ No constraint violations")
                report_lines.append("✓ Night-to-day transitions valid")
            report_lines.append("")
        
        # Optimization results
        if optimization_results:
            report_lines.append("-" * 70)
            report_lines.append("OPTIMIZATION RESULTS")
            report_lines.append("-" * 70)
            report_lines.append(f"Success Rate: {optimization_results.get('success_rate', 0)*100:.1f}%")
            if optimization_results.get('failed_assignments'):
                report_lines.append("Failed Assignments:")
                for failed in optimization_results['failed_assignments']:
                    report_lines.append(f"  - {failed}")
            report_lines.append("")
        
        report_lines.append("=" * 70)
        
        # Write report
        output_path = os.path.join(output_dir, 'summary_report.txt')
        with open(output_path, 'w') as f:
            f.write('\n'.join(report_lines))
        
        return output_path

    def print_summary(self, optimization_results: Dict = None) -> None:
        """Print summary report to console."""
        lines = self._generate_summary_lines(optimization_results)
        print('\n'.join(lines))

    def _generate_summary_lines(self, optimization_results: Dict = None) -> List[str]:
        """Generate summary report lines."""
        report_lines = []
        report_lines.append("=" * 70)
        report_lines.append("AMBULANCE STATION RELIEF STAFF ROSTERING SUMMARY")
        report_lines.append("=" * 70)
        report_lines.append("")
        report_lines.append(f"Week: {self.schedule.week_start.date()} to {self.schedule.week_end.date()}")
        report_lines.append("")
        
        # Vacancy statistics
        total = len(self.schedule.vacancies)
        assigned = self.schedule.get_assigned_count()
        success_rate = (assigned / total * 100) if total > 0 else 0
        
        report_lines.append(f"Vacancies: {assigned}/{total} assigned ({success_rate:.1f}%)")
        report_lines.append(f"Total Hours: {self.schedule.get_total_hours_assigned():.1f}")
        report_lines.append("")
        
        # Workload summary
        workload_df = self.schedule.get_workload_summary()
        report_lines.append("Staff Workload:")
        for _, row in workload_df.iterrows():
            report_lines.append(
                f"  {row['staff_id']:<20} {row['assigned_hours']:>5.1f}/{row['target_hours']:<5.1f}h "
                f"({row['deviation']:+.1f})"
            )
        
        return report_lines
